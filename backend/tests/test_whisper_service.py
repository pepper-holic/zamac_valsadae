from pathlib import Path

from app.services.whisper_service import (
    _assess_transcription_quality,
    _progress_hook,
    is_model_cached,
    transcribe,
)


class FakeWhisperModel:
    def __init__(self, segments):
        self._segments = segments
        self.received_path = None

    def transcribe(self, audio_path: str) -> dict:
        self.received_path = audio_path
        return {"segments": self._segments}


def test_transcribe_converts_raw_segments_to_segment_models():
    fake_model = FakeWhisperModel(
        [
            {"start": 0.0, "end": 1.2, "text": " 안녕하세요 "},
            {"start": 1.2, "end": 2.5, "text": "반갑습니다"},
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
            {
                "start": 0.0,
                "end": 1.0,
                "text": "정상적인 문장",
                "no_speech_prob": 0.05,
                "avg_logprob": -0.2,
                "compression_ratio": 1.4,
            },
            {
                "start": 1.0,
                "end": 2.0,
                "text": "이상한 문장",
                "no_speech_prob": 0.9,
                "avg_logprob": -0.2,
                "compression_ratio": 1.4,
            },
        ]
    )

    segments = transcribe(Path("video.mp4"), model_size="small", model=fake_model)

    assert segments[0].transcription_quality == "good"
    assert segments[0].transcription_quality_reason is None
    assert segments[1].transcription_quality == "check"
    assert "무음" in segments[1].transcription_quality_reason


def test_assess_transcription_quality_flags_high_no_speech_prob():
    quality, reason = _assess_transcription_quality(
        {"no_speech_prob": 0.9, "avg_logprob": -0.2, "compression_ratio": 1.5}
    )
    assert quality == "check"
    assert "무음" in reason


def test_assess_transcription_quality_flags_low_logprob():
    quality, reason = _assess_transcription_quality(
        {"no_speech_prob": 0.1, "avg_logprob": -1.5, "compression_ratio": 1.5}
    )
    assert quality == "check"
    assert "신뢰도" in reason


def test_assess_transcription_quality_flags_high_compression_ratio():
    quality, reason = _assess_transcription_quality(
        {"no_speech_prob": 0.1, "avg_logprob": -0.2, "compression_ratio": 3.0}
    )
    assert quality == "check"
    assert "반복" in reason


def test_assess_transcription_quality_good_when_all_signals_fine():
    quality, reason = _assess_transcription_quality(
        {"no_speech_prob": 0.1, "avg_logprob": -0.2, "compression_ratio": 1.5}
    )
    assert quality == "good"
    assert reason is None


def test_assess_transcription_quality_defaults_to_good_when_signals_missing():
    quality, reason = _assess_transcription_quality({})
    assert quality == "good"
    assert reason is None


def test_transcribe_passes_media_path_as_string_to_model():
    fake_model = FakeWhisperModel([])

    transcribe(Path("some/video.mp4"), model_size="small", model=fake_model)

    assert fake_model.received_path == str(Path("some/video.mp4"))


def test_is_model_cached_false_for_unknown_size():
    assert is_model_cached("not-a-real-model-size") is False


def test_is_model_cached_true_when_file_present_on_disk(tmp_path, monkeypatch):
    import whisper

    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path))
    model_url = next(iter(whisper._MODELS.values()))
    model_size = next(iter(whisper._MODELS.keys()))
    cache_dir = tmp_path / "whisper"
    cache_dir.mkdir()
    (cache_dir / model_url.split("/")[-1]).write_bytes(b"fake-checkpoint")

    assert is_model_cached(model_size) is True


def test_transcribe_with_injected_model_ignores_on_progress():
    fake_model = FakeWhisperModel([{"start": 0.0, "end": 1.0, "text": "hi"}])
    calls = []

    segments = transcribe(
        Path("video.mp4"), model_size="small", model=fake_model, on_progress=calls.append
    )

    assert len(segments) == 1
    assert calls == []


def test_transcribe_with_injected_model_ignores_on_stage():
    fake_model = FakeWhisperModel([{"start": 0.0, "end": 1.0, "text": "hi"}])
    stage_calls = []

    transcribe(Path("video.mp4"), model_size="small", model=fake_model, on_stage=stage_calls.append)

    assert stage_calls == []


def test_progress_hook_reports_fractional_progress():
    import sys

    import whisper.transcribe  # noqa: F401

    whisper_transcribe_module = sys.modules["whisper.transcribe"]

    calls = []
    with _progress_hook(calls.append):
        pbar = whisper_transcribe_module.tqdm.tqdm(total=10, disable=False)
        pbar.update(5)
        pbar.update(5)

    assert calls == [0.5, 1.0]


def test_progress_hook_restores_original_tqdm_after_use():
    import sys

    import whisper.transcribe  # noqa: F401

    whisper_transcribe_module = sys.modules["whisper.transcribe"]

    original = whisper_transcribe_module.tqdm.tqdm
    with _progress_hook(lambda _: None):
        assert whisper_transcribe_module.tqdm.tqdm is not original

    assert whisper_transcribe_module.tqdm.tqdm is original
