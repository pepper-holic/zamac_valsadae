"""Whisper transcription orchestration: adaptive multilingual language
detection/verification and the single-language fast path.

Model loading/caching lives in whisper_model_loader.py; segment
post-processing (quality flags, splitting, repeat collapsing) lives in
whisper_segments.py. This module re-exports the names from both so existing
callers of `app.services.whisper_service` (and its test suite) don't need to
know about the split.
"""

import logging
import uuid
from collections.abc import Callable
from pathlib import Path
from types import SimpleNamespace
from typing import TYPE_CHECKING

from app.models.schemas import Segment
from app.services.whisper_model_loader import (  # noqa: F401 - re-exported for callers/tests
    _default_download_root,
    _detect_device,
    _download_model_with_progress,
    _get_model_on_device,
    _gpu_dll_dirs_registered,
    _load_model,
    _model_dir,
    _MODEL_CACHE,
    _register_gpu_dll_dirs,
    get_transcribe_device,
    importlib,
    is_model_cached,
)
from app.services.whisper_segments import (  # noqa: F401 - re-exported for callers/tests
    _assess_transcription_quality,
    _collapse_repeated_segments,
    _extract_words,
    _join_words,
    _LOGPROB_THRESHOLD,
    _NO_SPEECH_THRESHOLD,
    _split_long_segment,
    _split_long_segments,
)
from app.services.whisper_types import (
    CancelCallback,
    ProgressCallback,
    TranscriptionCancelled,
    WhisperModel,
)

if TYPE_CHECKING:
    import numpy as np

logger = logging.getLogger(__name__)


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
            # Carry forward the weaker part's own second_language along with
            # its probability - keeping prev_second unconditionally would
            # silently drop the incoming region's runner-up language even
            # when it's the incoming region that's actually less confident.
            if prev_probability <= probability:
                merged[-1] = (prev_start, end, prev_language, prev_probability, prev_second)
            else:
                merged[-1] = (prev_start, end, prev_language, probability, second_language)
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
