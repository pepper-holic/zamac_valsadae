"""In-memory cancellation flags for running background transcribe/translate tasks.

Background tasks run in-process (FastAPI BackgroundTasks), so a simple
in-memory registry - checked periodically by the long-running loop itself -
is enough. It intentionally does not survive a server restart: an orphaned
task from a previous process is handled separately by the startup recovery
in app.main, not by this module.
"""

_cancelled_item_ids: set[str] = set()


def request_cancel(item_id: str) -> None:
    _cancelled_item_ids.add(item_id)


def is_cancelled(item_id: str) -> bool:
    return item_id in _cancelled_item_ids


def clear_cancel(item_id: str) -> None:
    _cancelled_item_ids.discard(item_id)
