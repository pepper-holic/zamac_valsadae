import importlib
import logging
import os
import re
import uuid
from collections.abc import Callable, Iterable
from pathlib import Path
from types import SimpleNamespace
from typing import TYPE_CHECKING, Protocol

from app.core.config import WHISPER_MODEL_SIZES
from app.models.schemas import Segment, Word
from app.services.readability_service import MAX_DURATION_SEC, MIN_DURATION_SEC

if TYPE_CHECKING:
    import numpy as np

logger = logging.getLogger(__name__)

_MODEL_CACHE: dict[str, object] = {}

ProgressCallback = Callable[[float], None]

# Same default thresholds openai-whisper itself uses to decide whether a
# decoded segment is unreliable enough to warrant a fallback re-decode.
_NO_SPEECH_THRESHOLD = 0.6
_LOGPROB_THRESHOLD = -1.0
_COMPRESSION_RATIO_THRESHOLD = 2.4

# faster-whisper's compute_type: int8 quantization keeps CPU inference fast
# and low-memory while staying close to the fp32 model's accuracy. On GPU,
# float16 is both faster and more accurate than int8 quantization would be,
# and modern CUDA cards handle it natively.
_CPU_COMPUTE_TYPE = "int8"
_GPU_COMPUTE_TYPE = "float16"

# ctranslate2 defaults cpu_threads=0 to min(4, core_count) regardless of how
# many cores are actually available, silently leaving most of a modern CPU
# idle. Use all logical cores instead.
_CPU_THREADS = os.cpu_count() or 4

# Weight file faster-whisper always writes last/largest, so its presence is
# a reliable signal that a model directory is a complete download.
_MODEL_WEIGHTS_FILENAME = "model.bin"

# Files faster-whisper needs from the model repo (mirrors faster_whisper.utils
# .download_model's allow_patterns, kept in sync manually since we call
# huggingface_hub directly below instead of going through that helper - doing
# so is what lets us plug in a progress-reporting tqdm_class).
_MODEL_ALLOW_PATTERNS = [
    "config.json",
    "preprocessor_config.json",
    "model.bin",
    "tokenizer.json",
    "vocabulary.*",
]

CancelCallback = Callable[[], bool]


class TranscriptionCancelled(Exception):
    """Raised mid-transcribe when the caller's should_cancel() reports True."""


def _assess_transcription_quality(raw_segment: object) -> tuple[str, str | None]:
    reasons = []

    no_speech_prob = getattr(raw_segment, "no_speech_prob", None)
    if no_speech_prob is not None and no_speech_prob > _NO_SPEECH_THRESHOLD:
        reasons.append("무음/배경음일 가능성이 높습니다")

    avg_logprob = getattr(raw_segment, "avg_logprob", None)
    if avg_logprob is not None and avg_logprob < _LOGPROB_THRESHOLD:
        reasons.append("인식 신뢰도가 낮습니다")

    compression_ratio = getattr(raw_segment, "compression_ratio", None)
    if compression_ratio is not None and compression_ratio > _COMPRESSION_RATIO_THRESHOLD:
        reasons.append("반복되거나 비정상적인 패턴이 감지되었습니다")

    if reasons:
        return "check", " / ".join(reasons)
    return "good", None


def _extract_words(raw_segment: object) -> list[Word]:
    raw_words = getattr(raw_segment, "words", None)
    if not raw_words:
        return []
    return [
        Word(text=raw_word.word.strip(), start=float(raw_word.start), end=float(raw_word.end))
        for raw_word in raw_words
    ]


# Split long segments back down to the same threshold `readability_service`
# already flags as "too long" - otherwise every run-on sentence Whisper
# decodes as one segment lands in the review list needing a manual split.
_LEADING_PUNCTUATION = set(",.!?;:)]}'\"”’")


def _join_words(words: list[Word]) -> str:
    parts: list[str] = []
    for word in words:
        text = word.text
        if parts and text and text[0] in _LEADING_PUNCTUATION:
            parts[-1] = parts[-1] + text
        elif text:
            parts.append(text)
    return " ".join(parts).strip()


def _split_long_segment(segment: Segment, max_duration: float, min_duration: float) -> list[Segment]:
    duration = segment.end - segment.start
    if duration <= max_duration or len(segment.words) < 2:
        return [segment]

    words = segment.words
    mid_time = (segment.start + segment.end) / 2

    # Split at the word boundary with the longest silence gap (a natural
    # pause), preferring whichever such gap sits closest to the midpoint so
    # both halves come out reasonably balanced rather than a tiny sliver.
    best_index: int | None = None
    best_score: tuple[float, float] | None = None
    for i in range(len(words) - 1):
        left_duration = words[i].end - segment.start
        right_duration = segment.end - words[i + 1].start
        if left_duration < min_duration or right_duration < min_duration:
            continue
        gap = words[i + 1].start - words[i].end
        boundary_time = (words[i].end + words[i + 1].start) / 2
        score = (gap, -abs(boundary_time - mid_time))
        if best_score is None or score > best_score:
            best_score = score
            best_index = i

    if best_index is None:
        return [segment]

    left_words = words[: best_index + 1]
    right_words = words[best_index + 1 :]
    left = segment.model_copy(
        update={
            "id": uuid.uuid4().hex,
            "start": segment.start,
            "end": left_words[-1].end,
            "text": _join_words(left_words),
            "words": left_words,
        }
    )
    right = segment.model_copy(
        update={
            "id": uuid.uuid4().hex,
            "start": right_words[0].start,
            "end": segment.end,
            "text": _join_words(right_words),
            "words": right_words,
        }
    )
    return _split_long_segment(left, max_duration, min_duration) + _split_long_segment(
        right, max_duration, min_duration
    )


def _split_long_segments(segments: list[Segment]) -> list[Segment]:
    result: list[Segment] = []
    for segment in segments:
        result.extend(_split_long_segment(segment, MAX_DURATION_SEC, MIN_DURATION_SEC))
    return result


# Whisper occasionally hallucinates the same sentence several times in a row
# as separate back-to-back segments - a well-known repetition failure mode,
# distinct from genuine repeated speech (which doesn't usually recur this
# fast). Collapsing them into one segment (rather than leaving the reader to
# spot and delete N duplicate lines) is safe because dropping a merged
# segment's transcription_quality to "check" still surfaces it for review if
# the repeat turns out to be real.
_MAX_REPEAT_MERGE_GAP_SEC = 2.5
_REPEATED_TEXT_QUALITY_REASON = "동일 문장이 반복 인식되어 병합되었습니다 - 실제 반복 발화인지 확인해 주세요"


def _normalize_for_repeat_check(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip().lower()


def _collapse_repeated_segments(segments: list[Segment]) -> list[Segment]:
    if not segments:
        return segments

    collapsed: list[Segment] = [segments[0]]
    for segment in segments[1:]:
        previous = collapsed[-1]
        is_repeat = (
            bool(previous.text)
            and _normalize_for_repeat_check(segment.text) == _normalize_for_repeat_check(previous.text)
            and segment.start - previous.end <= _MAX_REPEAT_MERGE_GAP_SEC
        )
        if is_repeat:
            collapsed[-1] = previous.model_copy(
                update={
                    "end": segment.end,
                    "words": previous.words + segment.words,
                    "transcription_quality": "check",
                    "transcription_quality_reason": _REPEATED_TEXT_QUALITY_REASON,
                }
            )
        else:
            collapsed.append(segment)
    return collapsed


class WhisperModel(Protocol):
    def transcribe(self, audio_path: str, **kwargs: object) -> tuple[Iterable[object], object]: ...
    def detect_language(self, **kwargs: object) -> tuple[str, float, list[tuple[str, float]]]: ...


def _default_download_root() -> Path:
    from app.core.config import get_settings

    return get_settings().whisper_model_cache_dir


def _model_dir(model_size: str, download_root: Path) -> Path:
    return download_root / model_size


def is_model_cached(model_size: str, download_root: Path | None = None) -> bool:
    """Whether the given faster-whisper checkpoint has already been downloaded."""
    if model_size in _MODEL_CACHE:
        return True
    if model_size not in WHISPER_MODEL_SIZES:
        return False
    root = download_root if download_root is not None else _default_download_root()
    return (_model_dir(model_size, root) / _MODEL_WEIGHTS_FILENAME).is_file()


def _download_model_with_progress(
    model_size: str, output_dir: str, on_progress: ProgressCallback | None
) -> None:
    """Downloads the CT2 whisper checkpoint, reporting real byte-level progress.

    faster_whisper.utils.download_model() wraps huggingface_hub.snapshot_download,
    which hardcodes an internal `_AggregatedTqdm` for the actual per-file byte
    tracking and only ever hands the caller's tqdm_class the outer "N files"
    counter (unit="it", not "B") - so a tqdm_class passed to snapshot_download
    never observes real download bytes, only firing once the whole thing is
    done. hf_hub_download() does not have that indirection: it hands tqdm_class
    straight to the per-file byte-progress bar, so downloading each allowed
    file individually is what actually lets on_progress track real bytes.
    """
    import io
    from fnmatch import fnmatch

    import huggingface_hub
    from faster_whisper.utils import _MODELS
    from tqdm.auto import tqdm

    repo_id = _MODELS.get(model_size, model_size)
    all_files = huggingface_hub.list_repo_files(repo_id)
    files = [
        path
        for path in all_files
        if any(fnmatch(path, pattern) for pattern in _MODEL_ALLOW_PATTERNS)
    ]

    totals: dict[int, int] = {}
    currents: dict[int, int] = {}

    def _report() -> None:
        if on_progress is None or not totals:
            return
        total = sum(totals.values())
        if total > 0:
            on_progress(min(sum(currents.values()) / total, 1.0))

    class _ProgressTqdm(tqdm):
        """tqdm subclass that reports bytes instead of rendering a bar.

        `disable=True` would also short-circuit tqdm's own counter updates
        (not just its console output), so instead this writes to a throwaway
        buffer - safe even under pythonw, where stdout/stderr don't exist -
        and overrides display() to skip rendering entirely.
        """

        def __init__(self, *args: object, **kwargs: object) -> None:
            kwargs.setdefault("file", io.StringIO())
            super().__init__(*args, **kwargs)
            if self.unit == "B" and self.total:
                totals[id(self)] = self.total
                currents[id(self)] = 0

        def display(self, *args: object, **kwargs: object) -> None:
            return None

        def update(self, n: float = 1) -> bool | None:
            result = super().update(n)
            if id(self) in totals:
                currents[id(self)] = self.n
                _report()
            return result

        def close(self) -> None:
            super().close()
            totals.pop(id(self), None)
            currents.pop(id(self), None)

    for path in files:
        huggingface_hub.hf_hub_download(
            repo_id,
            filename=path,
            local_dir=output_dir,
            tqdm_class=_ProgressTqdm,
        )


def _detect_device() -> str:
    """"cuda" if ctranslate2 can see a usable GPU, otherwise "cpu".

    Any detection failure (no driver, no CUDA/cuDNN libs, etc.) falls back to
    "cpu" instead of raising, so machines without a GPU behave exactly as
    before.
    """
    try:
        import ctranslate2

        return "cuda" if ctranslate2.get_cuda_device_count() > 0 else "cpu"
    except Exception:
        return "cpu"


def get_transcribe_device() -> str:
    """Public wrapper around `_detect_device` for API/status reporting - this
    only reports which device *would* be tried first. `transcribe()` still
    falls back to CPU on its own if that device fails, at load time or at
    actual run time (e.g. a missing cuBLAS/cuDNN DLL only surfacing once a
    kernel actually runs)."""
    return _detect_device()


# pip-installed nvidia-cublas-cu12 / nvidia-cudnn-cu12 wheels bundle the CUDA
# DLLs under their own site-packages directory rather than a system PATH
# location. torch registers that directory for you via a custom import hook;
# ctranslate2 doesn't, so ctranslate2's lazy LoadLibrary("cublas64_12.dll")
# fails even though the file is right there on disk. os.add_dll_directory
# only covers loads that opt into the "extended" DLL search (AddDllDirectory
# API); ctranslate2's own LoadLibrary call may not, so this also prepends the
# directories to PATH, which the classic search order always honors.
_gpu_dll_dirs_registered = False


def _register_gpu_dll_dirs() -> None:
    global _gpu_dll_dirs_registered
    if _gpu_dll_dirs_registered or os.name != "nt":
        return
    _gpu_dll_dirs_registered = True
    for package in ("nvidia.cublas", "nvidia.cudnn", "nvidia.cuda_nvrtc"):
        try:
            module = importlib.import_module(package)
            bin_dir = Path(module.__path__[0]) / "bin"
            if not bin_dir.is_dir():
                continue
            os.add_dll_directory(str(bin_dir))
            os.environ["PATH"] = str(bin_dir) + os.pathsep + os.environ.get("PATH", "")
        except Exception:
            logger.debug("Could not register GPU DLL directory for %s", package, exc_info=True)


def _load_model(model_dir: Path, device: str) -> WhisperModel:
    from faster_whisper import WhisperModel as FasterWhisperModel

    if device == "cuda":
        _register_gpu_dll_dirs()

    compute_type = _GPU_COMPUTE_TYPE if device == "cuda" else _CPU_COMPUTE_TYPE
    return FasterWhisperModel(
        str(model_dir), device=device, compute_type=compute_type, cpu_threads=_CPU_THREADS
    )


def _get_model_on_device(
    model_size: str,
    device: str,
    on_stage: Callable[[str], None] | None = None,
    on_progress: ProgressCallback | None = None,
    download_root: Path | None = None,
) -> WhisperModel:
    # Cached per (model_size, device) rather than just model_size - a GPU
    # instance that turns out to be unusable (see transcribe()'s fallback)
    # must not shadow a working CPU instance for the same model, and vice
    # versa.
    cache_key = f"{model_size}:{device}"
    if cache_key not in _MODEL_CACHE:
        root = download_root if download_root is not None else _default_download_root()
        model_dir = _model_dir(model_size, root)
        if not is_model_cached(model_size, download_root=root):
            if on_stage is not None:
                on_stage("downloading_model")
            model_dir.mkdir(parents=True, exist_ok=True)
            _download_model_with_progress(model_size, str(model_dir), on_progress)
        _MODEL_CACHE[cache_key] = _load_model(model_dir, device)
        if on_stage is not None:
            on_stage("processing")
    return _MODEL_CACHE[cache_key]


def _run_transcribe(
    active_model: WhisperModel,
    media_path: Path,
    on_progress: ProgressCallback | None,
    should_cancel: CancelCallback | None,
    language: str | None,
    report_progress: bool,
) -> list[Segment]:
    # word_timestamps=True runs faster-whisper's cross-attention/DTW word
    # alignment pass, which re-derives segment start/end times from the
    # actual audio instead of just estimating them from token position.
    # Without it, segment boundaries can drift locally (e.g. around silence,
    # music, or repeated speech) even though the overall transcript stays
    # correct.
    # vad_filter=True runs faster-whisper's built-in Silero VAD pass before
    # decoding, skipping silent/non-speech stretches instead of wastefully
    # decoding them - speeds up transcription with no extra dependency.
    # language=None (default) makes faster-whisper detect the language once
    # from the first 30s and decode the whole file under it - wrong for audio
    # that switches languages partway through (use the adaptive multilingual
    # path below for that case); language=<code> forces one language for the
    # whole file (used to force a specific language pass, including a single
    # already-detected region from the adaptive path).
    raw_segments, info = active_model.transcribe(
        str(media_path),
        word_timestamps=True,
        vad_filter=True,
        language=language,
    )

    # transcribe() returns a lazy generator - progress must be derived by
    # tracking how far each yielded segment's end time is into the audio,
    # rather than a callback hook (faster-whisper has no equivalent of
    # openai-whisper's tqdm-based progress bar).
    total_duration = getattr(info, "duration", None) if report_progress else None

    segments = []
    for raw_segment in raw_segments:
        if should_cancel is not None and should_cancel():
            raise TranscriptionCancelled("전사가 취소되었습니다.")
        if report_progress and total_duration:
            on_progress(min(raw_segment.end / total_duration, 1.0))
        quality, reason = _assess_transcription_quality(raw_segment)
        segments.append(
            Segment(
                id=uuid.uuid4().hex,
                start=float(raw_segment.start),
                end=float(raw_segment.end),
                text=raw_segment.text.strip(),
                transcription_quality=quality,
                transcription_quality_reason=reason,
                words=_extract_words(raw_segment),
            )
        )
    return _collapse_repeated_segments(_split_long_segments(segments))


# Whisper's encoder always consumes a fixed 30s mel window, so detect_language
# can't be asked to look at anything finer than that in a single call - the
# only way to get tighter language boundaries is to feed it shorter audio
# slices ourselves. Splitting every window down to the floor regardless of
# confidence would multiply transcribe() calls (and mis-detect more often,
# since short slices are inherently less reliable) for no benefit on
# single-language audio, so a region is only split further when its top
# language guess isn't confident enough to trust as-is. Below the floor, a
# language-ID guess on a couple seconds of audio is inherently shaky, so
# instead of trusting it outright, both of its top candidate languages get
# an actual trial decode and the one the decoder itself is more confident in
# (higher avg_logprob) wins - real decode quality is a better signal than
# the classifier once the window is this short.
_LANG_DETECT_THRESHOLD = 0.6
_LANG_DETECT_MIN_WINDOW_SEC = 4.0
# detect_language() pads/trims to this internally regardless of how much
# audio it's handed, so a single call can never faithfully represent more
# than this much of the timeline - top-level windows must respect that cap.
_LANG_DETECT_TOP_WINDOW_SEC = 30.0
_WHISPER_SAMPLE_RATE = 16000
# Per-segment language re-verification (_verify_and_patch_segments) is only
# worth its cost - an extra detect_language() call per segment - below this
# duration. A long, fluently-decoded segment is very unlikely to secretly be
# an entirely different language start-to-finish; the actual failure modes
# this exists to catch (a quick interjection, a short reply, a hallucinated
# filler sentence) are all short.
_VERIFY_MAX_DURATION_SEC = 6.0
# Caps how large _merge_adjacent_regions is allowed to grow a run of
# same-language confident windows into - without this, a long, uniformly
# one-language file collapses into a single region spanning the whole
# file, and _verify_and_patch_segments then re-checks every sentence in it
# individually since it operates per-segment within whatever region it's
# handed.
_MAX_MERGED_REGION_SEC = 60.0

# This app is built around Korean content that occasionally switches to
# English, not general-purpose multilingual transcription - detect_language's
# raw top-1 pick is unconstrained across all ~100 Whisper languages, so on
# noisy/musical audio it can confidently (and wrongly) land on something
# entirely unexpected (e.g. Japanese, which shares enough prosody with
# Korean to get confused for it). Once that happens, every other check in
# this file - which all work by comparing candidates against each other -
# has nothing to compare against, since nothing else ever proposes Korean as
# an alternative. Restricting the candidate pool to what this app actually
# mixes closes that hole entirely rather than trying to out-guess the
# classifier's own top-1 choice.
_ALLOWED_LANGUAGES = ("ko", "en")

# (start, end, top language, top language's confidence, runner-up language)
LanguageRegion = tuple[float, float, str, float, str | None]


def _language_probability(language: str, all_probs: list[tuple[str, float]]) -> float:
    for candidate_language, candidate_probability in all_probs:
        if candidate_language == language:
            return candidate_probability
    return 0.0


def _best_allowed_language(all_probs: list[tuple[str, float]]) -> tuple[str, float, str]:
    """Picks the best-scoring language among _ALLOWED_LANGUAGES, ignoring
    whatever detect_language's own unconstrained top-1 pick is."""
    scored = [(lang, _language_probability(lang, all_probs)) for lang in _ALLOWED_LANGUAGES]
    scored.sort(key=lambda item: item[1], reverse=True)
    best_language, best_probability = scored[0]
    other_language, _other_probability = scored[1]
    return best_language, best_probability, other_language


def _detect_language_regions(
    active_model: WhisperModel,
    audio: "np.ndarray",
    start: float,
    end: float,
) -> list[LanguageRegion]:
    """Recursively splits [start, end) into language regions.

    A region is accepted once detect_language's top guess (restricted to
    _ALLOWED_LANGUAGES) clears the confidence threshold or the region has
    been split down to the floor window size; otherwise it's bisected and
    each half is checked again.
    """
    start_sample = int(start * _WHISPER_SAMPLE_RATE)
    end_sample = int(end * _WHISPER_SAMPLE_RATE)
    chunk = audio[start_sample:end_sample]
    if chunk.size == 0:
        return []

    _raw_language, _raw_probability, all_probs = active_model.detect_language(audio=chunk)
    language, probability, second_language = _best_allowed_language(all_probs)

    duration = end - start
    if probability >= _LANG_DETECT_THRESHOLD or duration <= _LANG_DETECT_MIN_WINDOW_SEC:
        return [(start, end, language, probability, second_language)]

    mid = start + duration / 2
    return _detect_language_regions(active_model, audio, start, mid) + _detect_language_regions(
        active_model, audio, mid, end
    )


def _merge_adjacent_regions(regions: list[LanguageRegion]) -> list[LanguageRegion]:
    """Merges consecutive same-language regions to cut down transcribe() calls.

    Only merges regions that were each independently confident. Gluing an
    unconfirmed (floor-window) region onto its neighbors would grow the
    span the decode-quality check below has to average over - a localized
    wrong-language chunk buried inside an otherwise-fine multi-second region
    gets diluted into a passable average and slips past verification.
    Keeping unconfirmed regions small and separate is what lets that check
    actually catch them.
    Merging is also capped at _MAX_MERGED_REGION_SEC regardless of how
    confidently uniform the language stays - _verify_and_patch_segments
    re-checks every segment inside whatever region it's handed, so merging
    without a cap turns a long homogeneous file into one giant region and
    ends up re-verifying every single sentence in it one by one, completely
    negating the point of merging (fewer, larger transcribe() calls) in
    the first place.
    """
    merged: list[LanguageRegion] = []
    for start, end, language, probability, second_language in regions:
        prev = merged[-1] if merged else None
        can_merge = (
            prev is not None
            and prev[2] == language
            and prev[1] == start
            and prev[3] >= _LANG_DETECT_THRESHOLD
            and probability >= _LANG_DETECT_THRESHOLD
            and end - prev[0] <= _MAX_MERGED_REGION_SEC
        )
        if can_merge:
            prev_start, _prev_end, prev_language, prev_probability, prev_second = merged[-1]
            merged[-1] = (prev_start, end, prev_language, min(prev_probability, probability), prev_second)
        else:
            merged.append((start, end, language, probability, second_language))
    return merged


def _weighted_avg_logprob(raw_segments: list[object]) -> float:
    weighted_sum = 0.0
    total_duration = 0.0
    for raw_segment in raw_segments:
        duration = max(float(raw_segment.end) - float(raw_segment.start), 0.0)
        logprob = getattr(raw_segment, "avg_logprob", None)
        if logprob is None or duration == 0.0:
            continue
        weighted_sum += logprob * duration
        total_duration += duration
    return weighted_sum / total_duration if total_duration > 0.0 else float("-inf")


def _transcribe_forced(
    active_model: WhisperModel, region_audio: "np.ndarray", language: str
) -> list[object]:
    raw_segments, _info = active_model.transcribe(
        region_audio,
        word_timestamps=True,
        vad_filter=True,
        language=language,
    )
    return list(raw_segments)


def _shift_raw_segment(raw_segment: object, offset: float) -> object:
    words = getattr(raw_segment, "words", None) or []
    shifted_words = [
        SimpleNamespace(word=word.word, start=word.start + offset, end=word.end + offset)
        for word in words
    ]
    return SimpleNamespace(
        start=float(raw_segment.start) + offset,
        end=float(raw_segment.end) + offset,
        text=raw_segment.text,
        no_speech_prob=getattr(raw_segment, "no_speech_prob", None),
        avg_logprob=getattr(raw_segment, "avg_logprob", None),
        compression_ratio=getattr(raw_segment, "compression_ratio", None),
        words=shifted_words,
    )


def _verify_and_patch_segments(
    active_model: WhisperModel,
    region_audio: "np.ndarray",
    primary_segments: list[object],
    language: str,
    second_language: str,
) -> list[object]:
    """Re-checks every segment in a confident region and re-decodes the ones
    that turn out wrong, splicing the result back in place - a whole-region
    swap would throw away segments that already decoded fine just because a
    different segment nearby didn't.

    A segment is flagged two ways:
    - avg_logprob < threshold: the decoder itself wasn't confident.
    - re-running detect_language() on just that segment's own audio prefers
      a different language than the region's assigned one: this catches
      what avg_logprob can't. A short foreign phrase forced into the wrong
      language can still decode into perfectly fluent, confident text (a
      well-formed but wrong sentence, not garbled output) - avg_logprob
      measures how fluent the decoded *text* is, which tells you nothing
      about whether it matches the audio. detect_language() classifies
      from the encoder's acoustic features instead, so it isn't fooled by
      a confident hallucination the same way. The comparison is relative
      (does the classifier prefer some other language over the assigned
      one for *this* audio) rather than an absolute confidence floor - a
      segment this short is only a couple of words padded out to
      detect_language's 30s window, so its confidence reads lower across
      the board even when it clearly leans the right way; requiring it to
      clear the same bar as a full 30s window would miss exactly the short
      segments this check exists to catch.
    """
    patched: list[object] = []
    for raw_segment in primary_segments:
        start_sample = int(float(raw_segment.start) * _WHISPER_SAMPLE_RATE)
        end_sample = int(float(raw_segment.end) * _WHISPER_SAMPLE_RATE)
        sub_audio = region_audio[start_sample:end_sample]
        if sub_audio.size == 0:
            patched.append(raw_segment)
            continue

        avg_logprob = getattr(raw_segment, "avg_logprob", None)
        is_bad = avg_logprob is not None and avg_logprob < _LOGPROB_THRESHOLD
        retry_language = second_language
        duration = float(raw_segment.end) - float(raw_segment.start)

        # A couple of words has thin acoustic evidence, so detect_language's
        # own unconstrained top-1 pick for just this segment can be noisy -
        # it may not even land on the correct alternate language (or, on
        # noisy/musical audio, on an entirely unexpected third language).
        # With only two languages this app ever mixes, the question that
        # actually matters is simpler: for this specific clip, does the
        # *other* one directly outscore the assigned one - whether or not
        # it happens to be detect_language's own argmax. Every failure mode
        # this check exists to catch (a quick interjection in the other
        # language, a short reply, a hallucinated filler sentence) has shown
        # up on short segments - calling detect_language on every single
        # segment regardless of length, including long, clearly-fine ones,
        # was adding real per-region time without catching anything new, so
        # it's skipped past the floor window where the risk actually lives.
        if duration <= _VERIFY_MAX_DURATION_SEC:
            _raw_language, _raw_probability, all_probs = active_model.detect_language(audio=sub_audio)
            assigned_probability = _language_probability(language, all_probs)
            alternative_probability = _language_probability(second_language, all_probs)

            if alternative_probability > assigned_probability:
                is_bad = True
                retry_language = second_language

        if not is_bad:
            patched.append(raw_segment)
            continue

        logger.info(
            "다국어 전사: 세그먼트 %.1fs~%.1fs 재검증 트리거 (%s -> %s)",
            float(raw_segment.start),
            float(raw_segment.end),
            language,
            retry_language,
        )
        retry_segments = _transcribe_forced(active_model, sub_audio, retry_language)
        if retry_segments and (
            avg_logprob is None or _weighted_avg_logprob(retry_segments) >= avg_logprob
        ):
            offset = float(raw_segment.start)
            patched.extend(_shift_raw_segment(retry, offset) for retry in retry_segments)
        else:
            patched.append(raw_segment)
    return patched


_MIN_GAP_RETRY_SEC = 1.5


def _find_time_gaps(primary_segments: list[object], region_duration: float) -> list[tuple[float, float]]:
    gaps: list[tuple[float, float]] = []
    cursor = 0.0
    for raw_segment in sorted(primary_segments, key=lambda s: float(s.start)):
        start = float(raw_segment.start)
        if start - cursor > _MIN_GAP_RETRY_SEC:
            gaps.append((cursor, start))
        cursor = max(cursor, float(raw_segment.end))
    if region_duration - cursor > _MIN_GAP_RETRY_SEC:
        gaps.append((cursor, region_duration))
    return gaps


def _fill_missing_gaps(
    active_model: WhisperModel,
    region_audio: "np.ndarray",
    region_duration: float,
    primary_segments: list[object],
    second_language: str,
) -> list[object]:
    """A wrong-language forced decode doesn't always mis-transcribe foreign
    speech - it sometimes just never emits a segment for it at all (e.g. a
    trailing English sentence after a Korean-forced decode gives up on
    it), which no per-segment quality check can catch since there's no
    segment there to inspect. Any stretch of the region not covered by a
    primary segment, long enough to plausibly be real speech rather than a
    VAD-trimmed pause, gets retried under the runner-up language - retries
    that come back near-silent (which most such gaps genuinely are) are
    discarded so this doesn't paper over real silence with junk text.
    """
    gaps = _find_time_gaps(primary_segments, region_duration)
    if not gaps:
        return primary_segments

    filled = list(primary_segments)
    for gap_start, gap_end in gaps:
        logger.info(
            "다국어 전사: 시간 공백 %.1fs~%.1fs 발견, %s로 복구 시도",
            gap_start,
            gap_end,
            second_language,
        )
        start_sample = int(gap_start * _WHISPER_SAMPLE_RATE)
        end_sample = int(gap_end * _WHISPER_SAMPLE_RATE)
        sub_audio = region_audio[start_sample:end_sample]
        if sub_audio.size == 0:
            continue
        for retry in _transcribe_forced(active_model, sub_audio, second_language):
            no_speech_prob = getattr(retry, "no_speech_prob", None)
            if no_speech_prob is not None and no_speech_prob > _NO_SPEECH_THRESHOLD:
                continue
            if not str(getattr(retry, "text", "")).strip():
                continue
            filled.append(_shift_raw_segment(retry, gap_start))
    return sorted(filled, key=lambda s: float(s.start))


def _transcribe_region(
    active_model: WhisperModel,
    region_audio: "np.ndarray",
    language: str,
    probability: float,
    second_language: str | None,
) -> list[object]:
    primary_segments = _transcribe_forced(active_model, region_audio, language)
    if second_language is None:
        return primary_segments

    winner_language, winner_segments, loser_language = language, primary_segments, second_language

    if probability < _LANG_DETECT_THRESHOLD:
        # Small, already-uncertain floor window (detect_language itself
        # wasn't confident) - compare two full decodes of the whole thing
        # wholesale first, since at this size the *dominant* language is
        # genuinely in doubt. Whichever wins still goes through the same
        # per-segment and gap checks below: even the winner can be locally
        # wrong (e.g. only part of this 4s window is actually the winning
        # language), same as a region detect_language was confident about.
        secondary_segments = _transcribe_forced(active_model, region_audio, second_language)
        if _weighted_avg_logprob(secondary_segments) > _weighted_avg_logprob(primary_segments):
            winner_language, winner_segments, loser_language = second_language, secondary_segments, language

    # Re-check every segment and only patch the one(s) that turn out wrong
    # (e.g. an English question immediately followed by a Korean answer
    # inside one window - whichever language "wins" the region still gets
    # force-decoded onto the other speaker's turn) rather than discarding
    # segments that already decoded fine, then retry any stretch of the
    # region the winning decode never produced a segment for at all.
    patched = _verify_and_patch_segments(
        active_model, region_audio, winner_segments, winner_language, loser_language
    )
    region_duration = region_audio.shape[0] / _WHISPER_SAMPLE_RATE
    return _fill_missing_gaps(active_model, region_audio, region_duration, patched, loser_language)


def _run_transcribe_multilingual(
    active_model: WhisperModel,
    media_path: Path,
    on_progress: ProgressCallback | None,
    should_cancel: CancelCallback | None,
    report_progress: bool,
) -> list[Segment]:
    from faster_whisper.audio import decode_audio

    logger.info("다국어 전사: 오디오 디코딩 시작 (%s)", media_path.name)
    audio = decode_audio(str(media_path))
    total_duration = audio.shape[0] / _WHISPER_SAMPLE_RATE
    if total_duration <= 0:
        return []

    # detect_language() always pads/trims whatever audio it's given down to a
    # single 30s mel window internally - calling it once on the full file
    # would silently only ever look at the first 30s and (if that's
    # confident) lock that language in for the entire duration, exactly the
    # bug this whole adaptive scheme exists to avoid. So the file is tiled
    # into <=30s top-level windows first, and each is independently
    # bisected/verified from there.
    raw_regions: list[LanguageRegion] = []
    window_start = 0.0
    while window_start < total_duration:
        window_end = min(window_start + _LANG_DETECT_TOP_WINDOW_SEC, total_duration)
        raw_regions.extend(_detect_language_regions(active_model, audio, window_start, window_end))
        window_start = window_end

    regions = _merge_adjacent_regions(raw_regions)
    logger.info(
        "다국어 전사: 오디오 %.1fs를 %d개 구간으로 분할 (모델 캐시 로딩이 끝나면 여기서부터 실제 처리 시작)",
        total_duration,
        len(regions),
    )

    segments: list[Segment] = []
    for region_index, (region_start, region_end, language, probability, second_language) in enumerate(
        regions, start=1
    ):
        if should_cancel is not None and should_cancel():
            raise TranscriptionCancelled("전사가 취소되었습니다.")
        start_sample = int(region_start * _WHISPER_SAMPLE_RATE)
        end_sample = int(region_end * _WHISPER_SAMPLE_RATE)
        region_audio = audio[start_sample:end_sample]

        logger.info(
            "다국어 전사: 구간 %d/%d (%.1fs~%.1fs) 언어=%s 확신도=%.2f 처리 중",
            region_index,
            len(regions),
            region_start,
            region_end,
            language,
            probability,
        )
        raw_segments = _transcribe_region(active_model, region_audio, language, probability, second_language)
        for raw_segment in raw_segments:
            if should_cancel is not None and should_cancel():
                raise TranscriptionCancelled("전사가 취소되었습니다.")
            if report_progress:
                on_progress(min((region_start + raw_segment.end) / total_duration, 1.0))
            quality, reason = _assess_transcription_quality(raw_segment)
            words = [
                word.model_copy(update={"start": region_start + word.start, "end": region_start + word.end})
                for word in _extract_words(raw_segment)
            ]
            segments.append(
                Segment(
                    id=uuid.uuid4().hex,
                    start=region_start + float(raw_segment.start),
                    end=region_start + float(raw_segment.end),
                    text=raw_segment.text.strip(),
                    transcription_quality=quality,
                    transcription_quality_reason=reason,
                    words=words,
                )
            )
    return _collapse_repeated_segments(_split_long_segments(segments))


def _dispatch_transcribe(
    active_model: WhisperModel,
    media_path: Path,
    on_progress: ProgressCallback | None,
    should_cancel: CancelCallback | None,
    language: str | None,
    multilingual: bool,
    report_progress: bool,
) -> list[Segment]:
    if multilingual:
        return _run_transcribe_multilingual(
            active_model, media_path, on_progress, should_cancel, report_progress
        )
    return _run_transcribe(active_model, media_path, on_progress, should_cancel, language, report_progress)


def transcribe(
    media_path: Path,
    model_size: str,
    model: WhisperModel | None = None,
    on_progress: ProgressCallback | None = None,
    on_stage: Callable[[str], None] | None = None,
    download_root: Path | None = None,
    should_cancel: CancelCallback | None = None,
    language: str | None = None,
    multilingual: bool = False,
) -> list[Segment]:
    if model is not None:
        return _dispatch_transcribe(
            model, media_path, on_progress, should_cancel, language, multilingual, report_progress=False
        )

    report_progress = on_progress is not None
    device = _detect_device()
    try:
        active_model = _get_model_on_device(
            model_size, device, on_stage=on_stage, on_progress=on_progress, download_root=download_root
        )
        return _dispatch_transcribe(
            active_model, media_path, on_progress, should_cancel, language, multilingual, report_progress
        )
    except TranscriptionCancelled:
        raise
    except Exception:
        if device == "cpu":
            raise
        # GPU can fail at model construction *or* only once a kernel actually
        # runs (e.g. a missing cuBLAS/cuDNN DLL) - either way, retry once on
        # CPU instead of failing the whole transcription over a GPU problem.
        logger.warning(
            "GPU transcription failed for model=%s - retrying on CPU.", model_size, exc_info=True
        )
        cpu_model = _get_model_on_device(
            model_size, "cpu", on_stage=on_stage, on_progress=on_progress, download_root=download_root
        )
        return _dispatch_transcribe(
            cpu_model, media_path, on_progress, should_cancel, language, multilingual, report_progress
        )
