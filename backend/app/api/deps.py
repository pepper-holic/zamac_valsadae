from functools import lru_cache

from app.core.config import Settings, get_settings
from app.services.project_store import ProjectStore


@lru_cache
def get_store() -> ProjectStore:
    settings: Settings = get_settings()
    return ProjectStore(root_dir=settings.projects_dir)
