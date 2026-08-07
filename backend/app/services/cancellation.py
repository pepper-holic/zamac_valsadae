"""In-memory cancellation flags for running background transcribe/translate tasks.

Background tasks run in-process (FastAPI BackgroundTasks), so a simple
in-memory registry - checked periodically by the long-running loop itself -
is enough. It intentionally does not survive a server restart: an orphaned
task from a previous process is handled separately by the startup recovery
in app.main, not by this module.
"""

_cancelled_project_ids: set[str] = set()


def request_cancel(project_id: str) -> None:
    _cancelled_project_ids.add(project_id)


def is_cancelled(project_id: str) -> bool:
    return project_id in _cancelled_project_ids


def clear_cancel(project_id: str) -> None:
    _cancelled_project_ids.discard(project_id)
