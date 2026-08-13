"""Sequential, single-worker queue for transcription jobs.

Whisper (and diarization) are CPU/GPU heavy, so running more than one job at
a time makes every job slower and risks out-of-memory failures. Every
"전사 시작" click enqueues a job here instead of running immediately; a single
background thread drains the queue one job at a time in submission order.

The queue itself is in-memory and does not survive a server restart - on
restart, `app.main.recover_interrupted_projects` marks any item still
"queued" as an error so the user can requeue it.

Each queued job can sit for a long time before its turn comes up, and other
items in the same project keep getting edited (queued, cancelled, etc.)
while it waits. So unlike the shared `progress_reporter` helpers used by the
translate/render flows (which hold one Project snapshot for their whole
run), every write here re-reads the project immediately before saving -
otherwise a save at the end of a multi-minute job would silently overwrite
whatever a sibling item's status changed to in the meantime.
"""

import logging
import queue
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from app.core.config import get_settings
from app.models.schemas import MediaItem, Project
from app.services import cancellation, diarization_service, readability_service, whisper_service
from app.services.project_store import ItemNotFoundError, ProjectNotFoundError, ProjectStore

logger = logging.getLogger(__name__)

_SAVE_MIN_DELTA = 0.01
_SAVE_MIN_INTERVAL_SECONDS = 1.0


@dataclass(frozen=True)
class TranscribeJob:
    project_id: str
    item_id: str
    model_size: str
    diarize: bool
    multilingual: bool


# Jobs carry the ProjectStore instance the request was made with (instead of
# looking one up via get_store()) so the queue keeps working under FastAPI's
# dependency_overrides in tests, where get_store()'s @lru_cache singleton
# would otherwise point at the wrong store.
_queue: "queue.Queue[tuple[TranscribeJob, ProjectStore]]" = queue.Queue()
_worker_lock = threading.Lock()
_worker_started = False


def enqueue(job: TranscribeJob, store: ProjectStore) -> None:
    _ensure_worker_started()
    _queue.put((job, store))


def wait_until_idle() -> None:
    """Block until every job enqueued so far has finished. Test-only helper -
    production code has no need to wait on the queue synchronously."""
    _queue.join()


def _ensure_worker_started() -> None:
    global _worker_started
    with _worker_lock:
        if _worker_started:
            return
        threading.Thread(target=_worker_loop, name="transcription-queue", daemon=True).start()
        _worker_started = True


def _worker_loop() -> None:
    while True:
        job, store = _queue.get()
        try:
            _process(job, store)
        except Exception:  # pragma: no cover - safety net so the worker never dies
            logger.exception("Queued transcription job crashed for item %s", job.item_id)
        finally:
            _queue.task_done()


def _update_item(
    store: ProjectStore, project_id: str, item_id: str, mutate: Callable[[MediaItem], None]
) -> MediaItem | None:
    def mutate_project(project: Project) -> None:
        item = next((i for i in project.items if i.id == item_id), None)
        if item is not None:
            mutate(item)

    try:
        project = store.update(project_id, mutate_project)
    except ProjectNotFoundError:
        return None
    return next((i for i in project.items if i.id == item_id), None)


def _make_progress_reporter(
    store: ProjectStore, project_id: str, item_id: str
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
        _update_item(store, project_id, item_id, lambda item: setattr(item, "progress", fraction))

    return on_progress


def _make_stage_reporter(store: ProjectStore, project_id: str, item_id: str) -> Callable[[str], None]:
    def on_stage(stage: str) -> None:
        def mutate(item: MediaItem) -> None:
            item.stage = stage
            item.progress = 0.0

        _update_item(store, project_id, item_id, mutate)

    return on_stage


def _process(job: TranscribeJob, store: ProjectStore) -> None:
    try:
        item = store.get_item(job.project_id, job.item_id)
    except ItemNotFoundError:
        return
    if item.status != "queued":
        # Item was deleted, or the user cancelled it while it was still waiting.
        return
    media_path = Path(item.media_path)

    def start(i: MediaItem) -> None:
        i.status = "transcribing"
        i.started_at = time.time()

    _update_item(store, job.project_id, job.item_id, start)

    on_progress = _make_progress_reporter(store, job.project_id, job.item_id)
    on_stage = _make_stage_reporter(store, job.project_id, job.item_id)

    try:
        segments = whisper_service.transcribe(
            media_path,
            model_size=job.model_size,
            on_progress=on_progress,
            on_stage=on_stage,
            should_cancel=lambda: cancellation.is_cancelled(job.item_id),
            multilingual=job.multilingual,
        )
        if job.diarize:
            hf_token = get_settings().hf_token
            if not hf_token:
                raise ValueError(
                    "화자 분리를 사용하려면 HF_TOKEN 설정이 필요합니다 "
                    "(HuggingFace에서 pyannote/speaker-diarization-3.1 모델 이용약관 동의 필요)."
                )
            turns = diarization_service.diarize(media_path, hf_token=hf_token, on_stage=on_stage)
            segments = diarization_service.assign_speakers(segments, turns)
        final_segments = readability_service.apply_readability(segments, use_translation=False)

        def finish(i: MediaItem) -> None:
            i.segments = final_segments
            i.status = "transcribed"
            i.progress = 1.0
            i.stage = None
            i.started_at = None
            i.error = None

        _update_item(store, job.project_id, job.item_id, finish)
    except whisper_service.TranscriptionCancelled:

        def cancelled(i: MediaItem) -> None:
            i.status = "error"
            i.stage = None
            i.started_at = None
            i.progress = None
            i.error = "사용자가 전사를 취소했습니다."

        _update_item(store, job.project_id, job.item_id, cancelled)
    except Exception as exc:  # pragma: no cover - depends on optional heavy deps
        logger.exception("Transcription failed for item %s", job.item_id)

        def failed(i: MediaItem) -> None:
            i.status = "error"
            i.stage = None
            i.started_at = None
            i.error = str(exc)

        _update_item(store, job.project_id, job.item_id, failed)
    finally:
        cancellation.clear_cancel(job.item_id)
