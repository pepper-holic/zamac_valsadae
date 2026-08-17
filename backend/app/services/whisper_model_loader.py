"""Whisper checkpoint download/cache and device (CPU/GPU) selection.

Split out of whisper_service.py: this is the "get me a loaded model"
concern, independent of anything about transcribing or post-processing
segments once you have one.
"""

import importlib
import logging
import os
from collections.abc import Callable
from pathlib import Path

from app.core.config import WHISPER_MODEL_SIZES
from app.services.whisper_types import ProgressCallback, WhisperModel

logger = logging.getLogger(__name__)

_MODEL_CACHE: dict[str, object] = {}

# faster-whisper's compute_type: int8 quantization keeps CPU inference fast
# and low-memory while staying close to the fp32 model's accuracy. On GPU,
# float16 is both faster and more accurate than int8 quantization would be,
# and modern CUDA cards handle it natively.
_CPU_COMPUTE_TYPE = "int8"
_GPU_COMPUTE_TYPE = "float16"

# ctranslate2 defaults cpu_threads=0 to min(4, core_count) regardless of how
# many cores are actually available, silently leaving most of a modern CPU
# idle. Use all logical cores instead.
_CPU_THREADS = os.cpu_count() or 4

# Weight file faster-whisper always writes last/largest, so its presence is
# a reliable signal that a model directory is a complete download.
_MODEL_WEIGHTS_FILENAME = "model.bin"

# Files faster-whisper needs from the model repo (mirrors faster_whisper.utils
# .download_model's allow_patterns, kept in sync manually since we call
# huggingface_hub directly below instead of going through that helper - doing
# so is what lets us plug in a progress-reporting tqdm_class).
_MODEL_ALLOW_PATTERNS = [
    "config.json",
    "preprocessor_config.json",
    "model.bin",
    "tokenizer.json",
    "vocabulary.*",
]


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


def _download_model_with_progress(
    model_size: str, output_dir: str, on_progress: ProgressCallback | None
) -> None:
    """Downloads the CT2 whisper checkpoint, reporting real byte-level progress.

    faster_whisper.utils.download_model() wraps huggingface_hub.snapshot_download,
    which hardcodes an internal `_AggregatedTqdm` for the actual per-file byte
    tracking and only ever hands the caller's tqdm_class the outer "N files"
    counter (unit="it", not "B") - so a tqdm_class passed to snapshot_download
    never observes real download bytes, only firing once the whole thing is
    done. hf_hub_download() does not have that indirection: it hands tqdm_class
    straight to the per-file byte-progress bar, so downloading each allowed
    file individually is what actually lets on_progress track real bytes.
    """
    import io
    from fnmatch import fnmatch

    import huggingface_hub
    from faster_whisper.utils import _MODELS
    from tqdm.auto import tqdm

    repo_id = _MODELS.get(model_size, model_size)
    all_files = huggingface_hub.list_repo_files(repo_id)
    files = [
        path
        for path in all_files
        if any(fnmatch(path, pattern) for pattern in _MODEL_ALLOW_PATTERNS)
    ]

    totals: dict[int, int] = {}
    currents: dict[int, int] = {}

    def _report() -> None:
        if on_progress is None or not totals:
            return
        total = sum(totals.values())
        if total > 0:
            on_progress(min(sum(currents.values()) / total, 1.0))

    class _ProgressTqdm(tqdm):
        """tqdm subclass that reports bytes instead of rendering a bar.

        `disable=True` would also short-circuit tqdm's own counter updates
        (not just its console output), so instead this writes to a throwaway
        buffer - safe even under pythonw, where stdout/stderr don't exist -
        and overrides display() to skip rendering entirely.
        """

        def __init__(self, *args: object, **kwargs: object) -> None:
            kwargs.setdefault("file", io.StringIO())
            super().__init__(*args, **kwargs)
            if self.unit == "B" and self.total:
                totals[id(self)] = self.total
                currents[id(self)] = 0

        def display(self, *args: object, **kwargs: object) -> None:
            return None

        def update(self, n: float = 1) -> bool | None:
            result = super().update(n)
            if id(self) in totals:
                currents[id(self)] = self.n
                _report()
            return result

        def close(self) -> None:
            super().close()
            totals.pop(id(self), None)
            currents.pop(id(self), None)

    for path in files:
        huggingface_hub.hf_hub_download(
            repo_id,
            filename=path,
            local_dir=output_dir,
            tqdm_class=_ProgressTqdm,
        )


def _detect_device() -> str:
    """"cuda" if ctranslate2 can see a usable GPU, otherwise "cpu".

    Any detection failure (no driver, no CUDA/cuDNN libs, etc.) falls back to
    "cpu" instead of raising, so machines without a GPU behave exactly as
    before.
    """
    try:
        import ctranslate2

        return "cuda" if ctranslate2.get_cuda_device_count() > 0 else "cpu"
    except Exception:
        return "cpu"


def get_transcribe_device() -> str:
    """Public wrapper around `_detect_device` for API/status reporting - this
    only reports which device *would* be tried first. `transcribe()` still
    falls back to CPU on its own if that device fails, at load time or at
    actual run time (e.g. a missing cuBLAS/cuDNN DLL only surfacing once a
    kernel actually runs)."""
    return _detect_device()


# pip-installed nvidia-cublas-cu12 / nvidia-cudnn-cu12 wheels bundle the CUDA
# DLLs under their own site-packages directory rather than a system PATH
# location. torch registers that directory for you via a custom import hook;
# ctranslate2 doesn't, so ctranslate2's lazy LoadLibrary("cublas64_12.dll")
# fails even though the file is right there on disk. os.add_dll_directory
# only covers loads that opt into the "extended" DLL search (AddDllDirectory
# API); ctranslate2's own LoadLibrary call may not, so this also prepends the
# directories to PATH, which the classic search order always honors.
_gpu_dll_dirs_registered = False


def _register_gpu_dll_dirs() -> None:
    global _gpu_dll_dirs_registered
    if _gpu_dll_dirs_registered or os.name != "nt":
        return
    _gpu_dll_dirs_registered = True
    for package in ("nvidia.cublas", "nvidia.cudnn", "nvidia.cuda_nvrtc"):
        try:
            module = importlib.import_module(package)
            bin_dir = Path(module.__path__[0]) / "bin"
            if not bin_dir.is_dir():
                continue
            os.add_dll_directory(str(bin_dir))
            os.environ["PATH"] = str(bin_dir) + os.pathsep + os.environ.get("PATH", "")
        except Exception:
            logger.debug("Could not register GPU DLL directory for %s", package, exc_info=True)


def _load_model(model_dir: Path, device: str) -> WhisperModel:
    from faster_whisper import WhisperModel as FasterWhisperModel

    if device == "cuda":
        _register_gpu_dll_dirs()

    compute_type = _GPU_COMPUTE_TYPE if device == "cuda" else _CPU_COMPUTE_TYPE
    return FasterWhisperModel(
        str(model_dir), device=device, compute_type=compute_type, cpu_threads=_CPU_THREADS
    )


# Which model_size is currently cached for a given device - lets
# _get_model_on_device evict a stale size for that device instead of
# accumulating every model size a user has ever picked in memory (each
# checkpoint is hundreds of MB to a few GB, and GPU memory in particular is
# scarce). Keyed separately from _MODEL_CACHE since the cache itself is
# keyed by "size:device", not by device alone.
_CACHED_MODEL_SIZE_BY_DEVICE: dict[str, str] = {}


def _get_model_on_device(
    model_size: str,
    device: str,
    on_stage: Callable[[str], None] | None = None,
    on_progress: ProgressCallback | None = None,
    download_root: Path | None = None,
) -> WhisperModel:
    # Cached per (model_size, device) rather than just model_size - a GPU
    # instance that turns out to be unusable (see transcribe()'s fallback)
    # must not shadow a working CPU instance for the same model, and vice
    # versa.
    cache_key = f"{model_size}:{device}"
    if cache_key not in _MODEL_CACHE:
        # Only one model_size is ever actually in use per device at a time
        # in practice - evict whatever was loaded before so switching
        # sizes (e.g. "small" -> "large-v3") doesn't leave the old
        # multi-hundred-MB/GB checkpoint sitting in memory unused.
        stale_size = _CACHED_MODEL_SIZE_BY_DEVICE.get(device)
        if stale_size is not None and stale_size != model_size:
            _MODEL_CACHE.pop(f"{stale_size}:{device}", None)

        root = download_root if download_root is not None else _default_download_root()
        model_dir = _model_dir(model_size, root)
        if not is_model_cached(model_size, download_root=root):
            if on_stage is not None:
                on_stage("downloading_model")
            model_dir.mkdir(parents=True, exist_ok=True)
            _download_model_with_progress(model_size, str(model_dir), on_progress)
        _MODEL_CACHE[cache_key] = _load_model(model_dir, device)
        _CACHED_MODEL_SIZE_BY_DEVICE[device] = model_size
        if on_stage is not None:
            on_stage("processing")
    return _MODEL_CACHE[cache_key]
