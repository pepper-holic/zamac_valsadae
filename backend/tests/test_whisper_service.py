from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.models.schemas import Segment, Word
from app.services.whisper_service import (
    TranscriptionCancelled,
    _assess_transcription_quality,
    _detect_device,
    _get_model_on_device,
    _join_words,
    _split_long_segment,
    get_transcribe_device,
    is_model_cached,
    transcribe,
)


@pytest.fixture(autouse=True)
def _clear_model_cache():
    """`_MODEL_CACHE` is module-level global state keyed by "model_size:device"
    - without resetting it, a fake model cached under model_size="small" by
    one test would leak into and break every later test using that same
    size."""
    from app.services import whisper_service

    whisper_service._MODEL_CACHE.clear()
    yield
    whisper_service._MODEL_CACHE.clear()


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


def test_transcribe_splits_a_long_segment_at_the_largest_pause():
    words = [
        FakeRawWord(word="one", start=0.0, end=1.0),
        FakeRawWord(word="two", start=1.0, end=2.0),
        FakeRawWord(word="three", start=2.0, end=3.0),
        FakeRawWord(word="four", start=5.0, end=6.0),
        FakeRawWord(word="five", start=6.0, end=7.0),
        FakeRawWord(word="six", start=7.0, end=10.0),
    ]
    fake_model = FakeWhisperModel(
        [FakeRawSegment(start=0.0, end=10.0, text="one two three four five six", words=words)]
    )

    segments = transcribe(Path("video.mp4"), model_size="small", model=fake_model)

    assert len(segments) == 2
    assert segments[0].text == "one two three"
    assert segments[0].end == 3.0
    assert segments[1].text == "four five six"
    assert segments[1].start == 5.0
    assert segments[0].id != segments[1].id


def test_transcribe_recursively_splits_a_very_long_segment_into_parts_under_the_limit():
    words = [FakeRawWord(word=f"w{i}", start=float(i), end=float(i + 1)) for i in range(21)]
    fake_model = FakeWhisperModel(
        [FakeRawSegment(start=0.0, end=21.0, text=" ".join(w.word for w in words), words=words)]
    )

    segments = transcribe(Path("video.mp4"), model_size="small", model=fake_model)

    assert len(segments) >= 3
    for segment in segments:
        assert segment.end - segment.start <= 7.0


def test_transcribe_leaves_a_long_segment_unsplit_without_word_timestamps():
    fake_model = FakeWhisperModel(
        [FakeRawSegment(start=0.0, end=10.0, text="a very long run-on sentence", words=None)]
    )

    segments = transcribe(Path("video.mp4"), model_size="small", model=fake_model)

    assert len(segments) == 1
    assert segments[0].end == 10.0


def test_split_long_segment_returns_unchanged_when_under_max_duration():
    segment = Segment(
        id="x", start=0.0, end=5.0, text="short", words=[Word(text="short", start=0.0, end=5.0)]
    )

    assert _split_long_segment(segment, max_duration=7.0, min_duration=5 / 6) == [segment]


def test_split_long_segment_returns_unchanged_with_fewer_than_two_words():
    segment = Segment(
        id="x", start=0.0, end=10.0, text="one", words=[Word(text="one", start=0.0, end=10.0)]
    )

    assert _split_long_segment(segment, max_duration=7.0, min_duration=5 / 6) == [segment]


def test_split_long_segment_skips_a_boundary_that_would_leave_a_sliver():
    segment = Segment(
        id="x",
        start=0.0,
        end=9.0,
        text="a b c",
        words=[
            Word(text="a", start=0.0, end=0.3),
            Word(text="b", start=8.0, end=8.5),
            Word(text="c", start=8.5, end=9.0),
        ],
    )

    # Splitting after "a" leaves a 0.3s left half, and splitting after "b"
    # leaves a 0.5s right half - both under min_duration, so neither is a
    # valid boundary and the segment stays whole rather than producing a
    # sliver segment that would just trip the "too short" flag instead.
    assert _split_long_segment(segment, max_duration=7.0, min_duration=5 / 6) == [segment]


def test_join_words_attaches_leading_punctuation_without_a_space():
    words = [
        Word(text="Hello", start=0.0, end=1.0),
        Word(text=",", start=1.0, end=1.0),
        Word(text="world", start=1.0, end=2.0),
    ]

    assert _join_words(words) == "Hello, world"


def test_detect_device_returns_cuda_when_a_gpu_is_reported(monkeypatch):
    import ctranslate2

    monkeypatch.setattr(ctranslate2, "get_cuda_device_count", lambda: 1)

    assert _detect_device() == "cuda"


def test_detect_device_returns_cpu_when_no_gpu_is_reported(monkeypatch):
    import ctranslate2

    monkeypatch.setattr(ctranslate2, "get_cuda_device_count", lambda: 0)

    assert _detect_device() == "cpu"


def test_detect_device_returns_cpu_when_detection_raises(monkeypatch):
    import ctranslate2

    def boom():
        raise RuntimeError("no CUDA driver")

    monkeypatch.setattr(ctranslate2, "get_cuda_device_count", boom)

    assert _detect_device() == "cpu"


def test_get_model_on_device_caches_separately_per_device(monkeypatch, tmp_path):
    from app.services import whisper_service

    monkeypatch.setattr(whisper_service, "is_model_cached", lambda model_size, download_root=None: True)
    calls = []

    def fake_load_model(model_dir, device):
        calls.append(device)
        return f"model-on-{device}"

    monkeypatch.setattr(whisper_service, "_load_model", fake_load_model)

    gpu_model = _get_model_on_device("small", "cuda", download_root=tmp_path)
    cpu_model = _get_model_on_device("small", "cpu", download_root=tmp_path)
    gpu_model_again = _get_model_on_device("small", "cuda", download_root=tmp_path)

    assert gpu_model == "model-on-cuda"
    assert cpu_model == "model-on-cpu"
    assert gpu_model_again == "model-on-cuda"
    # the second "cuda" request was served from cache, not reloaded
    assert calls == ["cuda", "cpu"]


def test_transcribe_retries_on_cpu_when_gpu_fails_at_runtime(monkeypatch, tmp_path):
    """Covers a missing cuBLAS/cuDNN DLL - faster-whisper's transcribe() call
    can succeed at model *construction* but only fail once a kernel actually
    runs, which happens inside this call, not at _load_model() time."""
    from app.services import whisper_service

    monkeypatch.setattr(whisper_service, "_detect_device", lambda: "cuda")
    monkeypatch.setattr(whisper_service, "is_model_cached", lambda model_size, download_root=None: True)

    class FakeCudaModel:
        def transcribe(self, audio_path, **kwargs):
            raise RuntimeError("Library cublas64_12.dll is not found or cannot be loaded")

    cpu_model = FakeWhisperModel([FakeRawSegment(start=0.0, end=1.0, text="hello")])

    def fake_load_model(model_dir, device):
        return FakeCudaModel() if device == "cuda" else cpu_model

    monkeypatch.setattr(whisper_service, "_load_model", fake_load_model)

    segments = transcribe(Path("video.mp4"), model_size="small", download_root=tmp_path)

    assert len(segments) == 1
    assert segments[0].text == "hello"


def test_transcribe_raises_without_retry_when_cpu_itself_fails(monkeypatch, tmp_path):
    from app.services import whisper_service

    monkeypatch.setattr(whisper_service, "_detect_device", lambda: "cpu")
    monkeypatch.setattr(whisper_service, "is_model_cached", lambda model_size, download_root=None: True)

    class FakeFailingModel:
        def transcribe(self, audio_path, **kwargs):
            raise RuntimeError("boom")

    monkeypatch.setattr(whisper_service, "_load_model", lambda model_dir, device: FakeFailingModel())

    with pytest.raises(RuntimeError, match="boom"):
        transcribe(Path("video.mp4"), model_size="small", download_root=tmp_path)


def test_transcribe_does_not_treat_cancellation_as_a_gpu_failure(monkeypatch, tmp_path):
    from app.services import whisper_service

    monkeypatch.setattr(whisper_service, "_detect_device", lambda: "cuda")
    monkeypatch.setattr(whisper_service, "is_model_cached", lambda model_size, download_root=None: True)

    cpu_load_calls = []

    def fake_load_model(model_dir, device):
        if device == "cpu":
            cpu_load_calls.append(1)
        return FakeWhisperModel([FakeRawSegment(start=0.0, end=1.0, text="x")])

    monkeypatch.setattr(whisper_service, "_load_model", fake_load_model)

    with pytest.raises(TranscriptionCancelled):
        transcribe(
            Path("video.mp4"),
            model_size="small",
            download_root=tmp_path,
            should_cancel=lambda: True,
        )

    assert cpu_load_calls == []


def test_get_transcribe_device_reports_detected_device(monkeypatch):
    from app.services import whisper_service

    monkeypatch.setattr(whisper_service, "_detect_device", lambda: "cuda")
    assert get_transcribe_device() == "cuda"

    monkeypatch.setattr(whisper_service, "_detect_device", lambda: "cpu")
    assert get_transcribe_device() == "cpu"


def test_register_gpu_dll_dirs_adds_existing_bin_dirs_to_dll_search_and_path(monkeypatch, tmp_path):
    """Covers the pip-only install case: nvidia-cublas-cu12/nvidia-cudnn-cu12
    put their DLLs under site-packages, not a system PATH location, and
    ctranslate2's own LoadLibrary call doesn't discover them on its own."""
    import os
    import types

    from app.services import whisper_service

    monkeypatch.setattr(whisper_service, "_gpu_dll_dirs_registered", False)

    cublas_pkg = tmp_path / "cublas_pkg"
    (cublas_pkg / "bin").mkdir(parents=True)
    cudnn_pkg_without_bin = tmp_path / "cudnn_pkg"  # no bin dir - must be skipped, not error

    def fake_import_module(name):
        if name == "nvidia.cublas":
            return types.SimpleNamespace(__path__=[str(cublas_pkg)])
        if name == "nvidia.cudnn":
            return types.SimpleNamespace(__path__=[str(cudnn_pkg_without_bin)])
        raise ImportError(name)

    monkeypatch.setattr(whisper_service.importlib, "import_module", fake_import_module)

    added_dirs = []
    monkeypatch.setattr(os, "add_dll_directory", lambda path: added_dirs.append(path), raising=False)
    monkeypatch.setattr(os, "environ", dict(os.environ))
    original_path = os.environ.get("PATH", "")

    whisper_service._register_gpu_dll_dirs()

    expected_bin_dir = str(cublas_pkg / "bin")
    assert added_dirs == [expected_bin_dir]
    assert os.environ["PATH"] == expected_bin_dir + os.pathsep + original_path


def test_register_gpu_dll_dirs_is_a_no_op_the_second_time(monkeypatch, tmp_path):
    import os

    from app.services import whisper_service

    monkeypatch.setattr(whisper_service, "_gpu_dll_dirs_registered", True)
    calls = []
    monkeypatch.setattr(whisper_service.importlib, "import_module", lambda name: calls.append(name))

    whisper_service._register_gpu_dll_dirs()

    assert calls == []
