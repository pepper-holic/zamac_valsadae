"""Shared types for the whisper_service package split.

Kept dependency-free (no imports from sibling whisper_* modules) so both
whisper_model_loader.py and whisper_service.py can depend on it without
creating an import cycle between them.
"""

from collections.abc import Callable, Iterable
from typing import Protocol

ProgressCallback = Callable[[float], None]
CancelCallback = Callable[[], bool]


class TranscriptionCancelled(Exception):
    """Raised mid-transcribe when the caller's should_cancel() reports True."""


class WhisperModel(Protocol):
    def transcribe(self, audio_path: str, **kwargs: object) -> tuple[Iterable[object], object]: ...
    def detect_language(self, **kwargs: object) -> tuple[str, float, list[tuple[str, float]]]: ...
