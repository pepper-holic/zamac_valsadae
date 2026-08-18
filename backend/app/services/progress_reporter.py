import time
from collections.abc import Callable

from app.services.project_store import ProjectStore

_SAVE_MIN_DELTA = 0.01
_SAVE_MIN_INTERVAL_SECONDS = 1.0


def make_progress_reporter(
    project_id: str, item_id: str, store: ProjectStore
) -> Callable[[float], None]:
    """Builds an on_progress callback that persists render progress.

    Routed through ProjectStore.update_item() (not a held Project/MediaItem
    reference + save()) so a long-running render can't silently clobber
    other edits made to the same project while it's in flight.
    """
    state = {"last_progress": 0.0, "last_saved_at": 0.0}

    def on_progress(fraction: float) -> None:
        now = time.monotonic()
        progressed_enough = fraction - state["last_progress"] >= _SAVE_MIN_DELTA
        waited_enough = now - state["last_saved_at"] >= _SAVE_MIN_INTERVAL_SECONDS
        if not (progressed_enough and waited_enough) and fraction < 1.0:
            return
        state["last_progress"] = fraction
        state["last_saved_at"] = now
        store.update_item(project_id, item_id, lambda item: setattr(item, "progress", fraction))

    return on_progress
