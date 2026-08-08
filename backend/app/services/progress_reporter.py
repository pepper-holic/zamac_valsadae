import time
from collections.abc import Callable

from app.models.schemas import MediaItem, Project
from app.services.project_store import ProjectStore

_SAVE_MIN_DELTA = 0.01
_SAVE_MIN_INTERVAL_SECONDS = 1.0


def make_progress_reporter(
    project: Project, item: MediaItem, store: ProjectStore
) -> Callable[[float], None]:
    state = {"last_progress": 0.0, "last_saved_at": 0.0}

    def on_progress(fraction: float) -> None:
        now = time.monotonic()
        progressed_enough = fraction - state["last_progress"] >= _SAVE_MIN_DELTA
        waited_enough = now - state["last_saved_at"] >= _SAVE_MIN_INTERVAL_SECONDS
        if not (progressed_enough and waited_enough) and fraction < 1.0:
            return
        state["last_progress"] = fraction
        state["last_saved_at"] = now
        item.progress = fraction
        store.save(project)

    return on_progress


def make_stage_reporter(project: Project, item: MediaItem, store: ProjectStore) -> Callable[[str], None]:
    def on_stage(stage: str) -> None:
        item.stage = stage
        item.progress = None if stage == "downloading_model" else 0.0
        store.save(project)

    return on_stage
