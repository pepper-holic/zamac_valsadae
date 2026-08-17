from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.models.schemas import Segment, Word
from app.services.whisper_service import (
    TranscriptionCancelled,
    _assess_transcription_quality,
    _collapse_repeated_segments,
    _detect_device,
    _detect_language_regions,
    _find_time_gaps,
    _get_model_on_device,
    _join_words,
    _language_probability,
    _merge_adjacent_regions,
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
    def __init__(
        self,
        segments: list[FakeRawSegment],
        duration: float | None = None,
        detect_language_results: list[tuple[str, float, list]] | None = None,
    ):
        self._segments = segments
        self._duration = duration if duration is not None else (
            segments[-1].end if segments else 0.0
        )
        self.received_path = None
        self.received_kwargs: dict = {}
        self._detect_language_results = list(detect_language_results or [])
        self._detect_call_count = 0
        self.detect_language_calls: list = []
        self.transcribe_calls: list = []

    def transcribe(self, audio_path: str, **kwargs):
        self.received_path = audio_path
        self.received_kwargs = kwargs
        self.transcribe_calls.append((audio_path, kwargs))
        return iter(self._segments), SimpleNamespace(duration=self._duration)

    def detect_language(self, audio, **kwargs):
        self.detect_language_calls.append(audio)
        index = self._detect_call_count
        self._detect_call_count += 1
        if index < len(self._detect_language_results):
            return self._detect_language_results[index]
        # any call beyond what the test explicitly scripted (typically a
        # per-segment verify check) gets a neutral, empty distribution -
        # every language scores 0.0, which can never beat another 0.0, so
        # this never triggers a mismatch retry on its own
        return ("ko", 0.0, [])


class FakeAudioArray:
    """Stand-in for a decoded numpy audio array - avoids a hard test-time
    dependency on numpy actually being importable while still supporting the
    slicing/size/shape operations whisper_service performs on it."""

    def __init__(self, n_samples: int):
        self._n = max(n_samples, 0)

    def __getitem__(self, item: slice) -> "FakeAudioArray":
        start, stop, _step = item.indices(self._n)
        return FakeAudioArray(max(stop - start, 0))

    @property
    def size(self) -> int:
        return self._n

    @property
    def shape(self) -> tuple[int]:
        return (self._n,)


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


def test_transcribe_collapses_consecutive_identical_hallucinated_segments():
    fake_model = FakeWhisperModel(
        [
            FakeRawSegment(start=0.0, end=1.0, text="I'm very nervous."),
            FakeRawSegment(start=1.0, end=2.0, text="I'm very nervous."),
            FakeRawSegment(start=2.0, end=3.0, text="I'm very nervous."),
        ]
    )

    segments = transcribe(Path("video.mp4"), model_size="small", model=fake_model)

    assert len(segments) == 1
    assert segments[0].text == "I'm very nervous."
    assert segments[0].start == 0.0
    assert segments[0].end == 3.0
    assert segments[0].transcription_quality == "check"
    assert "반복" in segments[0].transcription_quality_reason


def test_collapse_repeated_segments_ignores_repeats_separated_by_a_long_gap():
    segments = [
        Segment(id="a", start=0.0, end=1.0, text="hi"),
        Segment(id="b", start=5.0, end=6.0, text="hi"),
    ]

    assert _collapse_repeated_segments(segments) == segments


def test_collapse_repeated_segments_ignores_different_text():
    segments = [
        Segment(id="a", start=0.0, end=1.0, text="hi"),
        Segment(id="b", start=1.0, end=2.0, text="bye"),
    ]

    assert _collapse_repeated_segments(segments) == segments


def test_transcribe_collapses_repeats_even_when_their_combined_span_exceeds_the_split_limit():
    """Collapsing repeated segments must run *after* the length-based
    resplit, not before - merging first and splitting second would hand the
    merged (now overlong) segment straight back to the pause-based splitter,
    which would fragment it right back into near-duplicate pieces."""
    fake_model = FakeWhisperModel(
        [
            FakeRawSegment(start=i * 1.5, end=i * 1.5 + 1.4, text="I'm very nervous.")
            for i in range(6)  # spans 0.0 - 8.9s, over the 7.0s split threshold
        ]
    )

    segments = transcribe(Path("video.mp4"), model_size="small", model=fake_model)

    assert len(segments) == 1
    assert segments[0].text == "I'm very nervous."
    assert segments[0].start == 0.0
    assert segments[0].end == 8.9


def test_collapse_repeated_segments_is_case_and_whitespace_insensitive():
    segments = [
        Segment(id="a", start=0.0, end=1.0, text="Hi  there"),
        Segment(id="b", start=1.0, end=2.0, text="hi there"),
    ]

    collapsed = _collapse_repeated_segments(segments)

    assert len(collapsed) == 1
    assert collapsed[0].end == 2.0


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


def test_detect_language_regions_accepts_whole_range_when_confident():
    fake_model = FakeWhisperModel([], detect_language_results=[("ko", 0.9, [("ko", 0.9), ("en", 0.05)])])

    regions = _detect_language_regions(fake_model, FakeAudioArray(40 * 16000), 0.0, 40.0)

    assert regions == [(0.0, 40.0, "ko", 0.9, "en")]
    assert len(fake_model.detect_language_calls) == 1


def test_detect_language_regions_splits_low_confidence_window_in_half():
    # First call (whole 20s range) is ambiguous, so it's bisected into two
    # 10s halves, each of which is confident enough to accept as-is.
    fake_model = FakeWhisperModel(
        [],
        detect_language_results=[
            ("ko", 0.4, [("ko", 0.4), ("en", 0.3)]),
            ("ko", 0.95, [("ko", 0.95)]),
            ("en", 0.95, [("en", 0.95)]),
        ],
    )

    regions = _detect_language_regions(fake_model, FakeAudioArray(20 * 16000), 0.0, 20.0)

    assert regions == [(0.0, 10.0, "ko", 0.95, "en"), (10.0, 20.0, "en", 0.95, "ko")]


def test_detect_language_regions_stops_splitting_at_the_floor_window():
    # Every call stays ambiguous, but recursion must still bottom out once a
    # region reaches the 4s floor instead of splitting forever.
    fake_model = FakeWhisperModel([], detect_language_results=[("ko", 0.1, [("ko", 0.1), ("en", 0.08)])] * 3)

    regions = _detect_language_regions(fake_model, FakeAudioArray(8 * 16000), 0.0, 8.0)

    assert regions == [(0.0, 4.0, "ko", 0.1, "en"), (4.0, 8.0, "ko", 0.1, "en")]


def test_merge_adjacent_regions_combines_same_language_neighbors():
    regions = [
        (0.0, 10.0, "ko", 0.9, None),
        (10.0, 20.0, "ko", 0.8, "en"),
        (20.0, 30.0, "en", 0.9, None),
    ]

    assert _merge_adjacent_regions(regions) == [
        (0.0, 20.0, "ko", 0.8, "en"),
        (20.0, 30.0, "en", 0.9, None),
    ]


def test_merge_adjacent_regions_keeps_non_adjacent_same_language_regions_separate():
    regions = [(0.0, 10.0, "ko", 0.9, None), (15.0, 20.0, "ko", 0.9, None)]

    assert _merge_adjacent_regions(regions) == regions


def test_merge_adjacent_regions_does_not_merge_an_unconfirmed_region():
    # Gluing a low-confidence floor-window onto a confident neighbor would
    # grow the span the decode-quality check has to average over, diluting
    # any localized wrong-language chunk hiding inside it - so it must stay
    # separate even though the language guess matches and it's adjacent.
    regions = [
        (0.0, 10.0, "ko", 0.9, None),
        (10.0, 14.0, "ko", 0.3, "en"),
    ]

    assert _merge_adjacent_regions(regions) == regions


def test_merge_adjacent_regions_stops_growing_past_the_max_merged_size():
    # Without a cap, a long uniformly-one-language file collapses into a
    # single region, and per-segment verification (which operates on
    # whatever region it's handed) then ends up re-checking every sentence
    # in the entire file individually - defeating the point of merging.
    regions = [
        (0.0, 30.0, "ko", 0.9, "en"),
        (30.0, 60.0, "ko", 0.9, "en"),
        (60.0, 90.0, "ko", 0.9, "en"),
    ]

    merged = _merge_adjacent_regions(regions)

    assert merged == [
        (0.0, 60.0, "ko", 0.9, "en"),
        (60.0, 90.0, "ko", 0.9, "en"),
    ]


def test_transcribe_multilingual_forces_detected_language_per_region(monkeypatch):
    from app.services import whisper_service

    # matches the single segment's own coverage exactly - no trailing gap
    # for the gap-fill pass to (correctly) flag and retry
    monkeypatch.setattr(
        "faster_whisper.audio.decode_audio", lambda path: FakeAudioArray(int(1 * 16000))
    )

    fake_model = FakeWhisperModel(
        [FakeRawSegment(start=0.0, end=1.0, text="hello")],
        detect_language_results=[("en", 0.9, [("en", 0.9)])],
    )

    segments = whisper_service.transcribe(
        Path("video.mp4"), model_size="small", model=fake_model, multilingual=True
    )

    assert len(segments) == 1
    assert fake_model.transcribe_calls[0][1]["language"] == "en"
    assert fake_model.transcribe_calls[0][1]["vad_filter"] is True
    # confident detection - no second trial decode needed
    assert len(fake_model.transcribe_calls) == 1


def test_transcribe_multilingual_offsets_segment_times_by_region_start(monkeypatch):
    from app.services import whisper_service

    monkeypatch.setattr(
        "faster_whisper.audio.decode_audio", lambda path: FakeAudioArray(int(8 * 16000))
    )

    # Ambiguous whole-range detection forces a split into two 4s regions
    # (the floor window) with different languages, each transcribed as its
    # own model.transcribe call, fully covering its own region so gap-fill
    # has nothing to flag - segment times coming back from the second call
    # are relative to its own region and must be shifted by the region's
    # start (4.0) to land on the full-audio timeline.
    call_segments = {
        "ko": [FakeRawSegment(start=0.0, end=4.0, text="ko-seg", avg_logprob=-0.1)],
        "en": [FakeRawSegment(start=0.0, end=4.0, text="en-seg", avg_logprob=-0.1)],
    }

    class SplittingFakeModel:
        def __init__(self):
            self._detect_results = [
                ("ko", 0.3, [("ko", 0.3), ("en", 0.2)]),
                ("ko", 0.95, [("ko", 0.95)]),
                ("en", 0.95, [("en", 0.95)]),
            ]
            self._detect_call_count = 0

        def detect_language(self, audio, **kwargs):
            index = self._detect_call_count
            self._detect_call_count += 1
            if index < len(self._detect_results):
                return self._detect_results[index]
            # per-segment verify calls beyond the scripted top-level/floor
            # detections: an empty distribution scores every language 0.0,
            # which can never beat the assigned language's own 0.0 default -
            # a neutral no-op regardless of which region is asking
            return ("ko", 0.0, [])

        def transcribe(self, audio, **kwargs):
            language = kwargs["language"]
            return iter(call_segments[language]), SimpleNamespace(duration=4.0)

    segments = whisper_service.transcribe(
        Path("video.mp4"), model_size="small", model=SplittingFakeModel(), multilingual=True
    )

    assert [(s.text, s.start, s.end) for s in segments] == [
        ("ko-seg", 0.0, 4.0),
        ("en-seg", 4.0, 8.0),
    ]


def test_transcribe_multilingual_tiles_detection_into_30s_windows_for_long_audio(monkeypatch):
    """detect_language() pads/trims whatever audio it's given down to a single
    30s window internally, so a single call spanning the whole (say, 50s)
    file would only ever look at the first 30s - and if that's confident,
    would wrongly lock that language in for the entire file. The top level
    must tile into <=30s windows before handing anything to detect_language."""
    from app.services import whisper_service

    total_duration = 50.0
    monkeypatch.setattr(
        "faster_whisper.audio.decode_audio",
        lambda path: FakeAudioArray(int(total_duration * 16000)),
    )

    class TilingFakeModel:
        def __init__(self):
            self._detect_results = [
                ("ko", 0.9, [("ko", 0.9)]),
                ("en", 0.9, [("en", 0.9)]),
            ]
            self._detect_call_count = 0
            self.detect_language_calls: list = []
            self.transcribe_calls: list = []

        def detect_language(self, audio, **kwargs):
            self.detect_language_calls.append(audio)
            index = self._detect_call_count
            self._detect_call_count += 1
            if index < len(self._detect_results):
                return self._detect_results[index]
            return ("ko", 0.0, [])  # neutral no-op for the per-segment verify calls

        def transcribe(self, audio, **kwargs):
            language = kwargs["language"]
            self.transcribe_calls.append((audio, kwargs))
            # fully covers whatever audio it's handed, so gap-fill never
            # has anything to flag regardless of the region's size - text
            # varies by language so the two regions' segments don't look
            # like an accidental repeat to _collapse_repeated_segments
            duration = audio.size / 16000
            segment = FakeRawSegment(start=0.0, end=duration, text=f"{language}-window", avg_logprob=-0.1)
            return iter([segment]), SimpleNamespace(duration=duration)

    fake_model = TilingFakeModel()

    segments = whisper_service.transcribe(
        Path("video.mp4"), model_size="small", model=fake_model, multilingual=True
    )

    # one detect_language call per 30s top-level window: [0, 30) and [30, 50)
    # - each region's segment fully spans the region (30s, then 20s), well
    # over _VERIFY_MAX_DURATION_SEC, so the per-segment verify pass skips
    # its own detect_language call for both.
    assert len(fake_model.detect_language_calls) == 2
    assert all(call.size <= 30 * 16000 for call in fake_model.detect_language_calls)
    assert [call[1]["language"] for call in fake_model.transcribe_calls] == ["ko", "en"]
    # second window's segment times are offset by its region start (30.0),
    # and each segment fully spans its own region (30s, then 20s)
    assert [(s.start, s.end) for s in segments] == [(0.0, 30.0), (30.0, 50.0)]


def test_transcribe_multilingual_retries_with_second_language_when_confident_decode_is_poor(monkeypatch):
    """Covers a quick English-question / Korean-answer exchange inside one
    window: detect_language confidently picks the dominant language (English,
    from the question), but force-decoding the Korean reply under English
    produces a bad avg_logprob - that alone must trigger a second-language
    retry even though the classifier's confidence cleared the threshold."""
    from app.services import whisper_service

    monkeypatch.setattr(
        "faster_whisper.audio.decode_audio", lambda path: FakeAudioArray(int(4 * 16000))
    )

    class ConfidentButWrongFakeModel:
        def __init__(self):
            self.transcribe_calls: list[tuple[str, float]] = []

        def detect_language(self, audio, **kwargs):
            return ("en", 0.9, [("en", 0.9), ("ko", 0.1)])

        def transcribe(self, audio, **kwargs):
            language = kwargs["language"]
            avg_logprob = -0.1 if language == "ko" else -2.0  # forcing "en" decodes badly
            self.transcribe_calls.append((language, avg_logprob))
            segment = FakeRawSegment(start=0.0, end=4.0, text=f"{language}-guess", avg_logprob=avg_logprob)
            return iter([segment]), SimpleNamespace(duration=4.0)

    fake_model = ConfidentButWrongFakeModel()

    segments = whisper_service.transcribe(
        Path("video.mp4"), model_size="small", model=fake_model, multilingual=True
    )

    assert len(fake_model.transcribe_calls) == 2  # confidence alone didn't skip the second opinion
    assert segments[0].text == "ko-guess"


def test_transcribe_multilingual_patches_only_the_bad_segment_not_the_whole_region(monkeypatch):
    """A confident region with mostly-good segments and one badly
    wrong-language segment must patch just that segment under the runner-up
    language, not discard the good segments along with it - and the trigger
    must look at the *worst* segment, not the region's average (which the
    good segments would otherwise pull up enough to mask the bad one)."""
    from app.services import whisper_service

    monkeypatch.setattr(
        "faster_whisper.audio.decode_audio", lambda path: FakeAudioArray(int(10 * 16000))
    )

    class MixedQualityFakeModel:
        def __init__(self):
            self.transcribe_calls: list[str] = []

        def detect_language(self, audio, **kwargs):
            return ("en", 0.9, [("en", 0.9), ("ko", 0.1)])

        def transcribe(self, audio, **kwargs):
            language = kwargs["language"]
            self.transcribe_calls.append(language)
            if language == "en":
                # two long, well-decoded "en" segments and one short, badly
                # wrong-language segment sandwiched between them
                segments = [
                    FakeRawSegment(start=0.0, end=4.0, text="fine one", avg_logprob=-0.1),
                    FakeRawSegment(start=4.0, end=5.0, text="en-guess", avg_logprob=-2.5),
                    FakeRawSegment(start=5.0, end=9.0, text="fine two", avg_logprob=-0.1),
                ]
            else:
                # retry call receives just the bad segment's 1s sub-slice,
                # so its own segment is relative to that slice (starts at 0)
                segments = [FakeRawSegment(start=0.0, end=1.0, text="ko-guess", avg_logprob=-0.1)]
            return iter(segments), SimpleNamespace(duration=10.0)

    fake_model = MixedQualityFakeModel()

    segments = whisper_service.transcribe(
        Path("video.mp4"), model_size="small", model=fake_model, multilingual=True
    )

    assert fake_model.transcribe_calls == ["en", "ko"]  # only the bad segment triggered a retry
    assert [(s.text, s.start, s.end) for s in segments] == [
        ("fine one", 0.0, 4.0),
        ("ko-guess", 4.0, 5.0),
        ("fine two", 5.0, 9.0),
    ]


def test_language_probability_returns_the_matching_entry():
    assert _language_probability("en", [("ko", 0.4), ("en", 0.35)]) == 0.35


def test_language_probability_defaults_to_zero_when_language_is_absent():
    assert _language_probability("ja", [("ko", 0.4), ("en", 0.35)]) == 0.0


def test_find_time_gaps_flags_uncovered_stretches_longer_than_the_floor():
    segments = [
        FakeRawSegment(start=0.0, end=4.0, text="a"),
        FakeRawSegment(start=4.0, end=5.0, text="b"),
        # gap: 5.0 - 8.0 (2.5s, over the 1.5s floor)
    ]

    assert _find_time_gaps(segments, region_duration=8.0) == [(5.0, 8.0)]


def test_find_time_gaps_ignores_short_pauses():
    segments = [
        FakeRawSegment(start=0.0, end=4.0, text="a"),
        FakeRawSegment(start=5.0, end=6.0, text="b"),  # 1.0s gap - within floor
    ]

    assert _find_time_gaps(segments, region_duration=6.5) == []  # trailing 0.5s also under floor


def test_transcribe_multilingual_recovers_speech_the_primary_decode_dropped_entirely(monkeypatch):
    """Covers a Korean sentence immediately followed by an English one: the
    Korean-forced decode can simply never emit a segment for the trailing
    English speech (rather than mis-transcribing it), leaving a gap no
    per-segment quality check can see since there's nothing there to
    inspect - the gap itself must be retried under the runner-up language."""
    from app.services import whisper_service

    monkeypatch.setattr(
        "faster_whisper.audio.decode_audio", lambda path: FakeAudioArray(int(9 * 16000))
    )

    class DroppingFakeModel:
        def __init__(self):
            self.transcribe_calls: list[str] = []

        def detect_language(self, audio, **kwargs):
            return ("ko", 0.9, [("ko", 0.9), ("en", 0.1)])

        def transcribe(self, audio, **kwargs):
            language = kwargs["language"]
            self.transcribe_calls.append(language)
            if language == "ko":
                # only covers 0-5s of the 9s region - the trailing English
                # sentence never gets a segment at all
                segments = [FakeRawSegment(start=0.0, end=5.0, text="ko-part", avg_logprob=-0.1)]
            else:
                # retry call receives just the gap's sub-slice, so its own
                # segment is relative to that slice (starts at 0)
                segments = [
                    FakeRawSegment(
                        start=0.0, end=4.0, text="en-part", avg_logprob=-0.1, no_speech_prob=0.05
                    )
                ]
            return iter(segments), SimpleNamespace(duration=9.0)

    fake_model = DroppingFakeModel()

    segments = whisper_service.transcribe(
        Path("video.mp4"), model_size="small", model=fake_model, multilingual=True
    )

    assert fake_model.transcribe_calls == ["ko", "en"]
    assert [(s.text, s.start, s.end) for s in segments] == [
        ("ko-part", 0.0, 5.0),
        ("en-part", 5.0, 9.0),
    ]


def test_transcribe_multilingual_discards_near_silent_gap_retries(monkeypatch):
    """A gap that really is just a VAD-trimmed pause must not get papered
    over with junk text from the retry decode."""
    from app.services import whisper_service

    monkeypatch.setattr(
        "faster_whisper.audio.decode_audio", lambda path: FakeAudioArray(int(9 * 16000))
    )

    class SilentGapFakeModel:
        def __init__(self):
            self.transcribe_calls: list[str] = []

        def detect_language(self, audio, **kwargs):
            return ("ko", 0.9, [("ko", 0.9), ("en", 0.1)])

        def transcribe(self, audio, **kwargs):
            language = kwargs["language"]
            self.transcribe_calls.append(language)
            if language == "ko":
                segments = [FakeRawSegment(start=0.0, end=5.0, text="ko-part", avg_logprob=-0.1)]
            else:
                segments = [
                    FakeRawSegment(start=0.0, end=4.0, text="", avg_logprob=-3.0, no_speech_prob=0.95)
                ]
            return iter(segments), SimpleNamespace(duration=9.0)

    fake_model = SilentGapFakeModel()

    segments = whisper_service.transcribe(
        Path("video.mp4"), model_size="small", model=fake_model, multilingual=True
    )

    assert [(s.text, s.start, s.end) for s in segments] == [("ko-part", 0.0, 5.0)]


def test_transcribe_multilingual_catches_a_fluent_wrong_language_hallucination(monkeypatch):
    """avg_logprob alone can't catch this: a short English phrase forced
    into Korean can decode into perfectly fluent, confident Korean text (a
    well-formed but wrong sentence) rather than garbled output. Re-running
    detect_language() on just that segment's own audio - an acoustic
    judgment, not a decoder-fluency one - is what actually catches it, even
    though the whole region was confidently (and correctly, for its other
    segment) classified as Korean."""
    from app.services import whisper_service

    monkeypatch.setattr(
        "faster_whisper.audio.decode_audio", lambda path: FakeAudioArray(int(4 * 16000))
    )

    class FluentHallucinationFakeModel:
        def __init__(self):
            self.transcribe_calls: list[str] = []
            self._detect_call_count = 0

        def detect_language(self, audio, **kwargs):
            self._detect_call_count += 1
            # call 1: whole-region check (confidently "ko")
            # call 2: first segment's per-segment recheck (still "ko" - correct)
            # call 3: second segment's per-segment recheck - the audio was
            #         actually English, so the acoustic classifier correctly
            #         says "en" even though its "ko" decode's avg_logprob
            #         looked perfectly fine
            if self._detect_call_count == 3:
                return ("en", 0.8, [("en", 0.8), ("ko", 0.2)])
            return ("ko", 0.9, [("ko", 0.9), ("en", 0.1)])

        def transcribe(self, audio, **kwargs):
            language = kwargs["language"]
            self.transcribe_calls.append(language)
            if language == "ko":
                segments = [
                    FakeRawSegment(start=0.0, end=2.0, text="우리 밴드가 15년이 지났네요.", avg_logprob=-0.1),
                    FakeRawSegment(start=2.0, end=4.0, text="근데 너무 부끄러웠어요.", avg_logprob=-0.15),
                ]
            else:
                segments = [FakeRawSegment(start=0.0, end=2.0, text="I'm too lazy.", avg_logprob=-0.1)]
            return iter(segments), SimpleNamespace(duration=4.0)

    fake_model = FluentHallucinationFakeModel()

    segments = whisper_service.transcribe(
        Path("video.mp4"), model_size="small", model=fake_model, multilingual=True
    )

    assert fake_model.transcribe_calls == ["ko", "en"]  # only the mismatched segment was retried
    assert [s.text for s in segments] == ["우리 밴드가 15년이 지났네요.", "I'm too lazy."]


def test_transcribe_multilingual_catches_a_weak_but_relatively_preferred_mismatch(monkeypatch):
    """A couple of words padded out to detect_language's 30s window reads
    lower-confidence across the board, even when the audio is genuinely
    English - so the per-segment recheck's top guess for a short segment may
    never clear an absolute confidence bar. What matters is whether the
    classifier prefers a *different* language than the one assigned, even
    weakly - here "en" only scores 0.35 (well under any reasonable absolute
    threshold) but still clearly beats "ko"'s own 0.1 share for that same
    clip, which is enough to trigger the retry."""
    from app.services import whisper_service

    monkeypatch.setattr(
        "faster_whisper.audio.decode_audio", lambda path: FakeAudioArray(int(4 * 16000))
    )

    class WeakMismatchFakeModel:
        def __init__(self):
            self.transcribe_calls: list[str] = []
            self._detect_call_count = 0

        def detect_language(self, audio, **kwargs):
            self._detect_call_count += 1
            # call 1: whole-region check (confidently "ko")
            # call 2: first segment's per-segment recheck (still "ko" - correct)
            # call 3: second segment's per-segment recheck - low absolute
            #         confidence for "en" (well under any reasonable
            #         absolute threshold), but still clearly beats "ko"'s
            #         own 0.1 share for that same clip
            if self._detect_call_count == 3:
                return ("en", 0.35, [("en", 0.35), ("ko", 0.1)])
            return ("ko", 0.9, [("ko", 0.9), ("en", 0.1)])

        def transcribe(self, audio, **kwargs):
            language = kwargs["language"]
            self.transcribe_calls.append(language)
            if language == "ko":
                segments = [
                    FakeRawSegment(start=0.0, end=2.0, text="우리 밴드가 15년이 지났네요.", avg_logprob=-0.1),
                    FakeRawSegment(start=2.0, end=4.0, text="근데 너무 부끄러웠어요.", avg_logprob=-0.15),
                ]
            else:
                segments = [FakeRawSegment(start=0.0, end=2.0, text="I'm too lazy.", avg_logprob=-0.1)]
            return iter(segments), SimpleNamespace(duration=4.0)

    fake_model = WeakMismatchFakeModel()

    segments = whisper_service.transcribe(
        Path("video.mp4"), model_size="small", model=fake_model, multilingual=True
    )

    assert fake_model.transcribe_calls == ["ko", "en"]
    assert [s.text for s in segments] == ["우리 밴드가 15년이 지났네요.", "I'm too lazy."]


def test_transcribe_multilingual_skips_per_segment_verify_for_long_segments(monkeypatch):
    """detect_language() per segment is only worth its cost below
    _VERIFY_MAX_DURATION_SEC - every reported failure mode has been a short
    interjection or reply, not an entire long segment secretly being a
    different language. A long segment's own decode-confidence check
    (avg_logprob) still applies; only the extra detect_language reclassify
    call is skipped."""
    from app.services import whisper_service

    monkeypatch.setattr(
        "faster_whisper.audio.decode_audio", lambda path: FakeAudioArray(int(10 * 16000))
    )

    class LongSegmentFakeModel:
        def __init__(self):
            self.detect_language_calls: list = []
            self.transcribe_calls: list[str] = []

        def detect_language(self, audio, **kwargs):
            self.detect_language_calls.append(audio)
            return ("ko", 0.9, [("ko", 0.9), ("en", 0.1)])

        def transcribe(self, audio, **kwargs):
            language = kwargs["language"]
            self.transcribe_calls.append(language)
            # 10s, well over _VERIFY_MAX_DURATION_SEC, decoded confidently
            segments = [FakeRawSegment(start=0.0, end=10.0, text="long-ko", avg_logprob=-0.1)]
            return iter(segments), SimpleNamespace(duration=10.0)

    fake_model = LongSegmentFakeModel()

    segments = whisper_service.transcribe(
        Path("video.mp4"), model_size="small", model=fake_model, multilingual=True
    )

    # only the region-level detection call - no per-segment verify call for
    # a segment this long
    assert len(fake_model.detect_language_calls) == 1
    assert fake_model.transcribe_calls == ["ko"]
    assert segments[0].text == "long-ko"


def test_transcribe_multilingual_picks_the_language_with_the_better_decode_when_ambiguous(monkeypatch):
    """Below the confidence threshold, both candidate languages get a trial
    decode and the one the decoder is more confident in (avg_logprob) wins -
    even though detect_language's own top guess was "ko". The winner then
    still goes through the per-segment re-check, which - since this fake's
    detect_language keeps weakly favoring "ko" for any audio - fires one
    more confirmatory trial decode under "ko" that ends up discarded because
    its avg_logprob is worse than the already-chosen "en" decode's."""
    from app.services import whisper_service

    monkeypatch.setattr(
        "faster_whisper.audio.decode_audio", lambda path: FakeAudioArray(int(4 * 16000))
    )

    class AmbiguousFakeModel:
        def __init__(self):
            self.transcribe_calls: list[tuple[str, float]] = []

        def detect_language(self, audio, **kwargs):
            return ("ko", 0.4, [("ko", 0.4), ("en", 0.35)])

        def transcribe(self, audio, **kwargs):
            language = kwargs["language"]
            avg_logprob = -0.1 if language == "en" else -1.2
            self.transcribe_calls.append((language, avg_logprob))
            segment = FakeRawSegment(start=0.0, end=4.0, text=f"{language}-guess", avg_logprob=avg_logprob)
            return iter([segment]), SimpleNamespace(duration=4.0)

    fake_model = AmbiguousFakeModel()

    segments = whisper_service.transcribe(
        Path("video.mp4"), model_size="small", model=fake_model, multilingual=True
    )

    # "ko" x2 (wholesale compare + the discarded confirmatory retry) + "en" x1
    assert len(fake_model.transcribe_calls) == 3
    assert segments[0].text == "en-guess"  # en had the better avg_logprob, so it still won


def test_transcribe_multilingual_fills_gaps_in_the_uncertain_branch_too(monkeypatch):
    """Gap-filling isn't limited to already-confident regions - a small,
    ambiguous floor window that picks a winning language via the wholesale
    dual-decode comparison can still have that winning decode drop part of
    the window entirely, and that gap must get the same runner-up-language
    recovery pass as a confident region would."""
    from app.services import whisper_service

    monkeypatch.setattr(
        "faster_whisper.audio.decode_audio", lambda path: FakeAudioArray(int(4 * 16000))
    )

    class AmbiguousDroppingFakeModel:
        def __init__(self):
            self.transcribe_calls: list[str] = []
            self._ko_call_count = 0
            self._detect_call_count = 0

        def detect_language(self, audio, **kwargs):
            self._detect_call_count += 1
            if self._detect_call_count == 1:
                # top-level region detection: genuinely ambiguous
                return ("ko", 0.4, [("ko", 0.4), ("en", 0.35)])
            # per-segment re-check on the winning "en" decode's own audio:
            # confirms "en" so this test stays focused on gap-filling rather
            # than also exercising the per-segment mismatch retry
            return ("en", 0.5, [("en", 0.5), ("ko", 0.3)])

        def transcribe(self, audio, **kwargs):
            language = kwargs["language"]
            self.transcribe_calls.append(language)
            if language == "en":
                # wins the wholesale comparison but only covers the first 2s
                # of the 4s window, leaving the rest as a gap
                segments = [FakeRawSegment(start=0.0, end=2.0, text="en-part", avg_logprob=-0.1)]
                return iter(segments), SimpleNamespace(duration=4.0)

            self._ko_call_count += 1
            if self._ko_call_count == 1:
                # wholesale-comparison baseline: covers the whole window
                # but with a worse score, so it loses
                segments = [FakeRawSegment(start=0.0, end=4.0, text="ko-full", avg_logprob=-0.9)]
            else:
                # gap-fill retry: receives just the 2s gap sub-slice, so its
                # own segment is relative to that slice (starts at 0)
                segments = [FakeRawSegment(start=0.0, end=2.0, text="ko-gap", avg_logprob=-0.1)]
            return iter(segments), SimpleNamespace(duration=4.0)

    fake_model = AmbiguousDroppingFakeModel()

    segments = whisper_service.transcribe(
        Path("video.mp4"), model_size="small", model=fake_model, multilingual=True
    )

    assert fake_model.transcribe_calls == ["ko", "en", "ko"]  # wholesale compare, then gap retry
    assert [(s.text, s.start, s.end) for s in segments] == [
        ("en-part", 0.0, 2.0),
        ("ko-gap", 2.0, 4.0),
    ]


def test_register_gpu_dll_dirs_is_a_no_op_the_second_time(monkeypatch, tmp_path):
    import os

    from app.services import whisper_service

    monkeypatch.setattr(whisper_service, "_gpu_dll_dirs_registered", True)
    calls = []
    monkeypatch.setattr(whisper_service.importlib, "import_module", lambda name: calls.append(name))

    whisper_service._register_gpu_dll_dirs()

    assert calls == []
