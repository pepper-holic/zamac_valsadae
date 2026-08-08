from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from app.models.schemas import Segment

_PIPELINE_CACHE: dict[str, object] = {}

# pyannote's HuggingFace-gated speaker diarization pipeline. Using it requires
# the user to accept the model's terms on HuggingFace and provide an HF_TOKEN.
_DIARIZATION_MODEL = "pyannote/speaker-diarization-3.1"


@dataclass(frozen=True)
class SpeakerTurn:
    start: float
    end: float
    speaker: str


class DiarizationPipeline(Protocol):
    def __call__(self, audio_path: str) -> object: ...


def _get_pipeline(
    hf_token: str, on_stage: Callable[[str], None] | None = None
) -> DiarizationPipeline:
    from pyannote.audio import Pipeline

    if _DIARIZATION_MODEL not in _PIPELINE_CACHE:
        if on_stage is not None:
            on_stage("downloading_model")
        _PIPELINE_CACHE[_DIARIZATION_MODEL] = Pipeline.from_pretrained(
            _DIARIZATION_MODEL, use_auth_token=hf_token
        )
        if on_stage is not None:
            on_stage("processing")
    return _PIPELINE_CACHE[_DIARIZATION_MODEL]  # type: ignore[return-value]


def diarize(
    media_path: Path,
    hf_token: str,
    pipeline: DiarizationPipeline | None = None,
    on_stage: Callable[[str], None] | None = None,
) -> list[SpeakerTurn]:
    active_pipeline = pipeline or _get_pipeline(hf_token, on_stage=on_stage)
    result = active_pipeline(str(media_path))
    return [
        SpeakerTurn(start=float(turn.start), end=float(turn.end), speaker=str(speaker))
        for turn, _, speaker in result.itertracks(yield_label=True)
    ]


def _overlap_seconds(a_start: float, a_end: float, b_start: float, b_end: float) -> float:
    return max(0.0, min(a_end, b_end) - max(a_start, b_start))


def assign_speakers(segments: list[Segment], turns: list[SpeakerTurn]) -> list[Segment]:
    """Labels each segment with the speaker turn it overlaps most with.

    Segment and speaker-turn boundaries rarely align exactly (diarization and
    transcription are independent passes over the audio), so this picks the
    turn with the greatest time overlap rather than requiring an exact match.
    """
    updated = []
    for segment in segments:
        best_speaker: str | None = None
        best_overlap = 0.0
        for turn in turns:
            overlap = _overlap_seconds(segment.start, segment.end, turn.start, turn.end)
            if overlap > best_overlap:
                best_overlap = overlap
                best_speaker = turn.speaker
        updated.append(segment.model_copy(update={"speaker": best_speaker}))
    return updated
