import os
from dataclasses import dataclass
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[2]
DATA_DIR = Path(os.environ.get("APP_DATA_DIR", BACKEND_DIR.parent / "data"))
PROJECTS_DIR = DATA_DIR / "projects"
CT2_MODEL_CACHE_DIR = Path(
    os.environ.get("CT2_MODEL_CACHE_DIR", DATA_DIR / "ct2models")
)

WHISPER_MODEL_SIZES = (
    "tiny",
    "base",
    "small",
    "medium",
    "large",
    "large-v2",
    "large-v3",
)


@dataclass(frozen=True)
class Settings:
    data_dir: Path = DATA_DIR
    projects_dir: Path = PROJECTS_DIR
    ct2_model_cache_dir: Path = CT2_MODEL_CACHE_DIR
    translation_api_key: str | None = os.environ.get("TRANSLATION_API_KEY")
    translation_api_base_url: str | None = os.environ.get("TRANSLATION_API_BASE_URL")


def get_settings() -> Settings:
    return Settings()
