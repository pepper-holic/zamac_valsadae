from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.services.whisper_service import (
    TranscriptionCancelled,
    _assess_transcription_quality,
    is_model_cached,
    transcribe,
)


@dataclass
class FakeRawWord:
    word: str
    start: float
    end: float


@dataclass
class FakeRawSegment:
    start: float
    end: float
    text: str
    no_speech_prob: float | None = None
    avg_logprob: float | None = None
    compression_ratio: float | None = None
    words: list[FakeRawWord] | None = None


class FakeWhisperModel:
    def __init__(self, segments: list[FakeRawSegment], duration: float | None = None):
        self._segments = segments
        self._duration = duration if duration is not None else (
            segments[-1].end if segments else 0.0
        )
        self.received_path = None
        self.received_kwargs: dict = {}

    def transcribe(self, audio_path: str, **kwargs):
        self.received_path = audio_path
        self.received_kwargs = kwargs
        return iter(self._segments), SimpleNamespace(duration=self._duration)


def test_transcribe_converts_raw_segments_to_segment_models():
    fake_model = FakeWhisperModel(
        [
            FakeRawSegment(start=0.0, end=1.2, text=" 안녕하세요 "),
            FakeRawSegment(start=1.2, end=2.5, text="반갑습니다"),
        ]
    )

    segments = transcribe(Path("video.mp4"), model_size="small", model=fake_model)

    assert len(segments) == 2
    assert segments[0].text == "안녕하세요"
    assert segments[0].start == 0.0
    assert segments[0].end == 1.2
    assert segments[1].text == "반갑습니다"
    assert segments[0].id != segments[1].id


def test_transcribe_carries_quality_signals_from_raw_segment():
    fake_model = FakeWhisperModel(
        [
            FakeRawSegment(
                start=0.0,
                end=1.0,
                text="정상적인 문장",
                no_speech_prob=0.05,
                avg_logprob=-0.2,
                compression_ratio=1.4,
            ),
            FakeRawSegment(
                start=1.0,
                end=2.0,
                text="이상한 문장",
                no_speech_prob=0.9,
                avg_logprob=-0.2,
                compression_ratio=1.4,
            ),
        ]
    )

    segments = transcribe(Path("video.mp4"), model_size="small", model=fake_model)

    assert segments[0].transcription_quality == "good"
    assert segments[0].transcription_quality_reason is None
    assert segments[1].transcription_quality == "check"
    assert "무음" in segments[1].transcription_quality_reason


def test_assess_transcription_quality_flags_high_no_speech_prob():
    quality, reason = _assess_transcription_quality(
        FakeRawSegment(start=0.0, end=1.0, text="x", no_speech_prob=0.9, avg_logprob=-0.2, compression_ratio=1.5)
    )
    assert quality == "check"
    assert "무음" in reason


def test_assess_transcription_quality_flags_low_logprob():
    quality, reason = _assess_transcription_quality(
        FakeRawSegment(start=0.0, end=1.0, text="x", no_speech_prob=0.1, avg_logprob=-1.5, compression_ratio=1.5)
    )
    assert quality == "check"
    assert "신뢰도" in reason


def test_assess_transcription_quality_flags_high_compression_ratio():
    quality, reason = _assess_transcription_quality(
        FakeRawSegment(start=0.0, end=1.0, text="x", no_speech_prob=0.1, avg_logprob=-0.2, compression_ratio=3.0)
    )
    assert quality == "check"
    assert "반복" in reason


def test_assess_transcription_quality_good_when_all_signals_fine():
    quality, reason = _assess_transcription_quality(
        FakeRawSegment(start=0.0, end=1.0, text="x", no_speech_prob=0.1, avg_logprob=-0.2, compression_ratio=1.5)
    )
    assert quality == "good"
    assert reason is None


def test_transcribe_enables_vad_filter_by_default():
    fake_model = FakeWhisperModel([FakeRawSegment(start=0.0, end=1.0, text="x")])

    transcribe(Path("video.mp4"), model_size="small", model=fake_model)

    assert fake_model.received_kwargs["vad_filter"] is True


def test_assess_transcription_quality_defaults_to_good_when_signals_missing():
    quality, reason = _assess_transcription_quality(SimpleNamespace())
    assert quality == "good"
    assert reason is None


def test_transcribe_passes_media_path_as_string_to_model():
    fake_model = FakeWhisperModel([])

    transcribe(Path("some/video.mp4"), model_size="small", model=fake_model)

    assert fake_model.received_path == str(Path("some/video.mp4"))


def test_transcribe_requests_word_timestamps_for_accurate_sync():
    fake_model = FakeWhisperModel([])

    transcribe(Path("video.mp4"), model_size="small", model=fake_model)

    assert fake_model.received_kwargs.get("word_timestamps") is True


def test_whisper_model_sizes_includes_large_v3_turbo():
    from app.core.config import WHISPER_MODEL_SIZES

    assert "large-v3-turbo" in WHISPER_MODEL_SIZES


def test_is_model_cached_false_for_unknown_size():
    assert is_model_cached("not-a-real-model-size") is False


def test_is_model_cached_true_when_file_present_in_download_root(tmp_path):
    model_dir = tmp_path / "small"
    model_dir.mkdir(parents=True, exist_ok=True)
    (model_dir / "model.bin").write_bytes(b"fake-checkpoint")

    assert is_model_cached("small", download_root=tmp_path) is True


def test_is_model_cached_false_when_download_root_empty(tmp_path):
    assert is_model_cached("small", download_root=tmp_path) is False


def test_is_model_cached_defaults_to_project_local_cache_dir(monkeypatch, tmp_path):
    from app.core import config

    monkeypatch.setattr(config, "get_settings", lambda: config.Settings(whisper_model_cache_dir=tmp_path))

    assert is_model_cached("not-a-real-model-size") is False


def test_transcribe_with_injected_model_ignores_on_progress():
    fake_model = FakeWhisperModel([FakeRawSegment(start=0.0, end=1.0, text="hi")])
    calls = []

    segments = transcribe(
        Path("video.mp4"), model_size="small", model=fake_model, on_progress=calls.append
    )

    assert len(segments) == 1
    assert calls == []


def test_transcribe_raises_when_cancelled_before_first_segment():
    fake_model = FakeWhisperModel([FakeRawSegment(start=0.0, end=1.0, text="hi")])

    with pytest.raises(TranscriptionCancelled):
        transcribe(
            Path("video.mp4"), model_size="small", model=fake_model, should_cancel=lambda: True
        )


def test_transcribe_stops_between_segments_when_cancelled():
    fake_model = FakeWhisperModel(
        [
            FakeRawSegment(start=0.0, end=1.0, text="first"),
            FakeRawSegment(start=1.0, end=2.0, text="second"),
        ]
    )
    calls = {"n": 0}

    def should_cancel() -> bool:
        calls["n"] += 1
        return calls["n"] > 1  # let the first segment through, cancel before the second

    with pytest.raises(TranscriptionCancelled):
        transcribe(
            Path("video.mp4"), model_size="small", model=fake_model, should_cancel=should_cancel
        )


def test_transcribe_maps_raw_words_to_segment_words():
    fake_model = FakeWhisperModel(
        [
            FakeRawSegment(
                start=0.0,
                end=1.0,
                text="안녕 하세요",
                words=[
                    FakeRawWord(word="안녕", start=0.0, end=0.4),
                    FakeRawWord(word="하세요", start=0.4, end=1.0),
                ],
            )
        ]
    )

    segments = transcribe(Path("video.mp4"), model_size="small", model=fake_model)

    assert len(segments[0].words) == 2
    assert segments[0].words[0].text == "안녕"
    assert segments[0].words[0].start == 0.0
    assert segments[0].words[0].end == 0.4
    assert segments[0].words[1].text == "하세요"


def test_transcribe_leaves_words_empty_when_raw_segment_has_none():
    fake_model = FakeWhisperModel([FakeRawSegment(start=0.0, end=1.0, text="hi", words=None)])

    segments = transcribe(Path("video.mp4"), model_size="small", model=fake_model)

    assert segments[0].words == []


def test_transcribe_with_injected_model_ignores_on_stage():
    fake_model = FakeWhisperModel([FakeRawSegment(start=0.0, end=1.0, text="hi")])
    stage_calls = []

    transcribe(Path("video.mp4"), model_size="small", model=fake_model, on_stage=stage_calls.append)

    assert stage_calls == []


def test_download_model_with_progress_reports_byte_level_fraction(monkeypatch):
    from app.services.whisper_service import _download_model_with_progress

    file_sizes = {"model.bin": 90, "config.json": 10}

    def fake_list_repo_files(repo_id):
        return list(file_sizes)

    def fake_hf_hub_download(repo_id, *, filename, local_dir, tqdm_class):
        bar = tqdm_class(total=file_sizes[filename], unit="B")
        bar.update(file_sizes[filename])
        bar.close()
        return f"{local_dir}/{filename}"

    monkeypatch.setattr("huggingface_hub.list_repo_files", fake_list_repo_files)
    monkeypatch.setattr("huggingface_hub.hf_hub_download", fake_hf_hub_download)

    calls = []
    _download_model_with_progress("small", "/fake/output", calls.append)

    assert calls[-1] == pytest.approx(1.0, abs=0.01)


def test_download_model_with_progress_ignores_non_byte_bars(monkeypatch):
    from app.services.whisper_service import _download_model_with_progress

    def fake_list_repo_files(repo_id):
        return ["config.json"]

    def fake_hf_hub_download(repo_id, *, filename, local_dir, tqdm_class):
        bar = tqdm_class(total=5, unit="files")
        bar.update(5)
        bar.close()
        return f"{local_dir}/{filename}"

    monkeypatch.setattr("huggingface_hub.list_repo_files", fake_list_repo_files)
    monkeypatch.setattr("huggingface_hub.hf_hub_download", fake_hf_hub_download)

    calls = []
    _download_model_with_progress("small", "/fake/output", calls.append)

    assert calls == []
