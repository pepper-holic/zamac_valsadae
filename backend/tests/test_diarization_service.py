from dataclasses import dataclass
from pathlib import Path

import pytest

from app.models.schemas import Segment
from app.services import diarization_service
from app.services.diarization_service import SpeakerTurn, assign_speakers, diarize


@dataclass
class FakeTurn:
    start: float
    end: float


class FakeDiarizationResult:
    def __init__(self, tracks: list[tuple[FakeTurn, str]]):
        self._tracks = tracks

    def itertracks(self, yield_label: bool):
        for turn, speaker in self._tracks:
            yield turn, None, speaker


class FakeDiarizationPipeline:
    def __init__(self, tracks: list[tuple[FakeTurn, str]]):
        self._tracks = tracks
        self.received_path = None

    def __call__(self, audio_path: str):
        self.received_path = audio_path
        return FakeDiarizationResult(self._tracks)


def test_diarize_converts_pipeline_tracks_to_speaker_turns():
    pipeline = FakeDiarizationPipeline(
        [(FakeTurn(0.0, 1.5), "SPEAKER_00"), (FakeTurn(1.5, 3.0), "SPEAKER_01")]
    )

    turns = diarize(Path("video.mp4"), hf_token="fake-token", pipeline=pipeline)

    assert turns == [
        SpeakerTurn(start=0.0, end=1.5, speaker="SPEAKER_00"),
        SpeakerTurn(start=1.5, end=3.0, speaker="SPEAKER_01"),
    ]
    assert pipeline.received_path == "video.mp4"


def test_assign_speakers_picks_turn_with_greatest_overlap():
    segments = [
        Segment(id="1", start=0.0, end=1.0, text="a"),
        Segment(id="2", start=1.0, end=3.0, text="b"),
    ]
    turns = [
        SpeakerTurn(start=0.0, end=1.2, speaker="SPEAKER_00"),
        SpeakerTurn(start=1.2, end=3.0, speaker="SPEAKER_01"),
    ]

    updated = assign_speakers(segments, turns)

    assert updated[0].speaker == "SPEAKER_00"
    assert updated[1].speaker == "SPEAKER_01"
    # originals must stay untouched
    assert segments[0].speaker is None


def test_assign_speakers_leaves_speaker_none_when_no_overlap():
    segments = [Segment(id="1", start=10.0, end=11.0, text="a")]
    turns = [SpeakerTurn(start=0.0, end=1.0, speaker="SPEAKER_00")]

    updated = assign_speakers(segments, turns)

    assert updated[0].speaker is None


def test_assign_speakers_empty_turns_returns_none_speakers():
    segments = [Segment(id="1", start=0.0, end=1.0, text="a")]

    updated = assign_speakers(segments, [])

    assert updated[0].speaker is None


def test_get_pipeline_wraps_gated_model_error_with_friendly_korean_message(monkeypatch):
    import pyannote.audio

    def boom(*args, **kwargs):
        raise RuntimeError("401 Client Error: Repository Not Found for url ... gated")

    monkeypatch.setattr(pyannote.audio.Pipeline, "from_pretrained", boom)
    diarization_service._PIPELINE_CACHE.clear()

    with pytest.raises(ValueError, match="이용약관"):
        diarize(Path("video.mp4"), hf_token="fake-token")
