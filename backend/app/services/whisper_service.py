import os
import uuid
from collections.abc import Callable, Iterable
from pathlib import Path
from typing import Protocol

from app.core.config import WHISPER_MODEL_SIZES
from app.models.schemas import Segment, Word

_MODEL_CACHE: dict[str, object] = {}

ProgressCallback = Callable[[float], None]

# Same default thresholds openai-whisper itself uses to decide whether a
# decoded segment is unreliable enough to warrant a fallback re-decode.
_NO_SPEECH_THRESHOLD = 0.6
_LOGPROB_THRESHOLD = -1.0
_COMPRESSION_RATIO_THRESHOLD = 2.4

# faster-whisper's compute_type: int8 quantization keeps CPU inference fast
# and low-memory while staying close to the fp32 model's accuracy.
_COMPUTE_TYPE = "int8"

# ctranslate2 defaults cpu_threads=0 to min(4, core_count) regardless of how
# many cores are actually available, silently leaving most of a modern CPU
# idle. Use all logical cores instead.
_CPU_THREADS = os.cpu_count() or 4

# Weight file faster-whisper always writes last/largest, so its presence is
# a reliable signal that a model directory is a complete download (same
# "check one file" approach LocalTranslator.is_cached uses for CT2 models).
_MODEL_WEIGHTS_FILENAME = "model.bin"

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


def _get_model(
    model_size: str,
    on_stage: Callable[[str], None] | None = None,
    download_root: Path | None = None,
) -> WhisperModel:
    from faster_whisper import WhisperModel as FasterWhisperModel
    from faster_whisper.utils import download_model

    if model_size not in _MODEL_CACHE:
        root = download_root if download_root is not None else _default_download_root()
        model_dir = _model_dir(model_size, root)
        if on_stage is not None and not is_model_cached(model_size, download_root=root):
            on_stage("downloading_model")
        model_dir.mkdir(parents=True, exist_ok=True)
        if not (model_dir / _MODEL_WEIGHTS_FILENAME).is_file():
            download_model(model_size, output_dir=str(model_dir))
        _MODEL_CACHE[model_size] = FasterWhisperModel(
            str(model_dir), device="cpu", compute_type=_COMPUTE_TYPE, cpu_threads=_CPU_THREADS
        )
        if on_stage is not None:
            on_stage("processing")
    return _MODEL_CACHE[model_size]


def transcribe(
    media_path: Path,
    model_size: str,
    model: WhisperModel | None = None,
    on_progress: ProgressCallback | None = None,
    on_stage: Callable[[str], None] | None = None,
    download_root: Path | None = None,
    should_cancel: CancelCallback | None = None,
) -> list[Segment]:
    active_model = model or _get_model(model_size, on_stage=on_stage, download_root=download_root)

    # word_timestamps=True runs faster-whisper's cross-attention/DTW word
    # alignment pass, which re-derives segment start/end times from the
    # actual audio instead of just estimating them from token position.
    # Without it, segment boundaries can drift locally (e.g. around silence,
    # music, or repeated speech) even though the overall transcript stays
    # correct.
    # vad_filter=True runs faster-whisper's built-in Silero VAD pass before
    # decoding, skipping silent/non-speech stretches instead of wastefully
    # decoding them - speeds up transcription with no extra dependency.
    raw_segments, info = active_model.transcribe(
        str(media_path), word_timestamps=True, vad_filter=True
    )

    # transcribe() returns a lazy generator - progress must be derived by
    # tracking how far each yielded segment's end time is into the audio,
    # rather than a callback hook (faster-whisper has no equivalent of
    # openai-whisper's tqdm-based progress bar).
    report_progress = on_progress is not None and model is None
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
    return segments
