import os
from dataclasses import dataclass
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[2]
DATA_DIR = Path(os.environ.get("APP_DATA_DIR", BACKEND_DIR.parent / "data"))
PROJECTS_DIR = DATA_DIR / "projects"
CT2_MODEL_CACHE_DIR = Path(
    os.environ.get("CT2_MODEL_CACHE_DIR", DATA_DIR / "ct2models")
)
WHISPER_MODEL_CACHE_DIR = Path(
    os.environ.get("WHISPER_MODEL_CACHE_DIR", DATA_DIR / "whisper_models")
)


def _default_binary_path(name: str) -> str:
    # run.bat/install.ps1 provision a portable ffmpeg/ffprobe under
    # <repo_root>/runtime/ffmpeg so the app works without a system-wide
    # install; fall back to PATH otherwise.
    bundled = BACKEND_DIR.parent / "runtime" / "ffmpeg" / "bin" / f"{name}.exe"
    return str(bundled) if bundled.is_file() else name


FFMPEG_PATH = os.environ.get("FFMPEG_PATH", _default_binary_path("ffmpeg"))
FFPROBE_PATH = os.environ.get("FFPROBE_PATH", _default_binary_path("ffprobe"))

WHISPER_MODEL_SIZES = (
    "tiny",
    "base",
    "small",
    "medium",
    "large",
    "large-v2",
    "large-v3",
    "large-v3-turbo",
)

FILLER_WORDS_KO = (
    "음",
    "어",
    "그",
    "저",
    "그니까",
    "그러니까",
    "아",
    "에",
    "뭐",
    "이제",
)

FILLER_WORDS_EN = (
    "um",
    "uh",
    "er",
    "ah",
    "like",
    "you know",
    "so",
    "well",
)


@dataclass(frozen=True)
class Settings:
    data_dir: Path = DATA_DIR
    projects_dir: Path = PROJECTS_DIR
    ct2_model_cache_dir: Path = CT2_MODEL_CACHE_DIR
    whisper_model_cache_dir: Path = WHISPER_MODEL_CACHE_DIR
    ffmpeg_path: str = FFMPEG_PATH
    ffprobe_path: str = FFPROBE_PATH
    translation_api_key: str | None = os.environ.get("TRANSLATION_API_KEY")
    translation_api_base_url: str | None = os.environ.get("TRANSLATION_API_BASE_URL")
    hf_token: str | None = os.environ.get("HF_TOKEN")


def get_settings() -> Settings:
    return Settings()
