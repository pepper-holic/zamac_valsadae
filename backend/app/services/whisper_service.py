import contextlib
import uuid
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Protocol

from app.models.schemas import Segment

_MODEL_CACHE: dict[str, object] = {}

ProgressCallback = Callable[[float], None]

# Same default thresholds openai-whisper itself uses to decide whether a
# decoded segment is unreliable enough to warrant a fallback re-decode.
_NO_SPEECH_THRESHOLD = 0.6
_LOGPROB_THRESHOLD = -1.0
_COMPRESSION_RATIO_THRESHOLD = 2.4


def _assess_transcription_quality(raw_segment: dict) -> tuple[str, str | None]:
    reasons = []

    no_speech_prob = raw_segment.get("no_speech_prob")
    if no_speech_prob is not None and no_speech_prob > _NO_SPEECH_THRESHOLD:
        reasons.append("무음/배경음일 가능성이 높습니다")

    avg_logprob = raw_segment.get("avg_logprob")
    if avg_logprob is not None and avg_logprob < _LOGPROB_THRESHOLD:
        reasons.append("인식 신뢰도가 낮습니다")

    compression_ratio = raw_segment.get("compression_ratio")
    if compression_ratio is not None and compression_ratio > _COMPRESSION_RATIO_THRESHOLD:
        reasons.append("반복되거나 비정상적인 패턴이 감지되었습니다")

    if reasons:
        return "check", " / ".join(reasons)
    return "good", None


class WhisperModel(Protocol):
    def transcribe(self, audio_path: str) -> dict: ...


def is_model_cached(model_size: str) -> bool:
    """Whether the given Whisper checkpoint has already been downloaded.

    Mirrors whisper's own default download location/filename logic (via its
    `_MODELS` URL table) instead of hardcoding it, so this stays correct if
    whisper changes its naming scheme in a future version.
    """
    import os

    import whisper

    if model_size in _MODEL_CACHE:
        return True
    url = whisper._MODELS.get(model_size)
    if url is None:
        return False
    download_root = os.path.join(
        os.getenv("XDG_CACHE_HOME", os.path.join(os.path.expanduser("~"), ".cache")),
        "whisper",
    )
    return os.path.isfile(os.path.join(download_root, os.path.basename(url)))


def _get_model(
    model_size: str, on_stage: Callable[[str], None] | None = None
) -> WhisperModel:
    import whisper

    if model_size not in _MODEL_CACHE:
        if on_stage is not None and not is_model_cached(model_size):
            on_stage("downloading_model")
        _MODEL_CACHE[model_size] = whisper.load_model(model_size)
        if on_stage is not None:
            on_stage("processing")
    return _MODEL_CACHE[model_size]


@contextlib.contextmanager
def _progress_hook(on_progress: ProgressCallback) -> Iterator[None]:
    import sys

    import whisper.transcribe  # noqa: F401 - ensures the submodule is registered

    # whisper/__init__.py rebinds the `whisper.transcribe` attribute to the
    # `transcribe` function itself, shadowing the submodule, so the real
    # submodule must be fetched from sys.modules instead of via attribute access.
    whisper_transcribe_module = sys.modules["whisper.transcribe"]
    original_tqdm_class = whisper_transcribe_module.tqdm.tqdm

    class _ProgressTqdm(original_tqdm_class):
        def update(self, n: float = 1) -> None:
            super().update(n)
            if self.total:
                on_progress(min(self.n / self.total, 1.0))

    whisper_transcribe_module.tqdm.tqdm = _ProgressTqdm
    try:
        yield
    finally:
        whisper_transcribe_module.tqdm.tqdm = original_tqdm_class


def transcribe(
    media_path: Path,
    model_size: str,
    model: WhisperModel | None = None,
    on_progress: ProgressCallback | None = None,
    on_stage: Callable[[str], None] | None = None,
) -> list[Segment]:
    active_model = model or _get_model(model_size, on_stage=on_stage)

    if on_progress is not None and model is None:
        # verbose=False (rather than the default None) is required for whisper's
        # internal tqdm bar to actually count progress instead of being a no-op.
        with _progress_hook(on_progress):
            result = active_model.transcribe(str(media_path), verbose=False)
    else:
        result = active_model.transcribe(str(media_path))

    segments = []
    for raw_segment in result["segments"]:
        quality, reason = _assess_transcription_quality(raw_segment)
        segments.append(
            Segment(
                id=uuid.uuid4().hex,
                start=float(raw_segment["start"]),
                end=float(raw_segment["end"]),
                text=raw_segment["text"].strip(),
                transcription_quality=quality,
                transcription_quality_reason=reason,
            )
        )
    return segments
