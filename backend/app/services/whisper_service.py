import importlib
import logging
import os
import uuid
from collections.abc import Callable, Iterable
from pathlib import Path
from typing import Protocol

from app.core.config import WHISPER_MODEL_SIZES
from app.models.schemas import Segment, Word
from app.services.readability_service import MAX_DURATION_SEC, MIN_DURATION_SEC

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
# a reliable signal that a model directory is a complete download (same
# "check one file" approach LocalTranslator.is_cached uses for CT2 models).
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


class WhisperModel(Protocol):
    def transcribe(self, audio_path: str, **kwargs: object) -> tuple[Iterable[object], object]: ...


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
    multilingual: bool,
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
    # that switches languages partway through. multilingual=True re-detects
    # the language for every ~30s window instead; language=<code> forces one
    # language for the whole file (used to force a specific language pass).
    raw_segments, info = active_model.transcribe(
        str(media_path),
        word_timestamps=True,
        vad_filter=True,
        language=language,
        multilingual=multilingual,
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
    return _split_long_segments(segments)


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
        return _run_transcribe(
            model, media_path, on_progress, should_cancel, language, multilingual, report_progress=False
        )

    report_progress = on_progress is not None
    device = _detect_device()
    try:
        active_model = _get_model_on_device(
            model_size, device, on_stage=on_stage, on_progress=on_progress, download_root=download_root
        )
        return _run_transcribe(
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
        return _run_transcribe(
            cpu_model, media_path, on_progress, should_cancel, language, multilingual, report_progress
        )
