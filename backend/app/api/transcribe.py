import logging
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException

from app.api.deps import get_store
from app.core.config import WHISPER_MODEL_SIZES
from app.models.schemas import Project, TranscribeRequest
from app.services import whisper_service
from app.services.progress_reporter import make_progress_reporter
from app.services.project_store import ProjectNotFoundError, ProjectStore

router = APIRouter(prefix="/projects", tags=["transcribe"])
logger = logging.getLogger(__name__)


def _run_transcription(project_id: str, model_size: str, store: ProjectStore) -> None:
    project = store.get(project_id)
    try:
        segments = whisper_service.transcribe(
            Path(project.media_path),
            model_size=model_size,
            on_progress=make_progress_reporter(project, store),
        )
        project.segments = segments
        project.status = "transcribed"
        project.progress = 1.0
        project.error = None
    except Exception as exc:  # pragma: no cover - depends on optional heavy deps
        logger.exception("Transcription failed for project %s", project_id)
        project.status = "error"
        project.error = str(exc)
    store.save(project)


@router.post("/{project_id}/transcribe", response_model=Project)
async def transcribe_project(
    project_id: str,
    request: TranscribeRequest,
    background_tasks: BackgroundTasks,
    store: ProjectStore = Depends(get_store),
) -> Project:
    if request.model not in WHISPER_MODEL_SIZES:
        raise HTTPException(status_code=400, detail=f"지원하지 않는 모델입니다: {request.model}")
    try:
        project = store.get(project_id)
    except ProjectNotFoundError as exc:
        raise HTTPException(status_code=404, detail="프로젝트를 찾을 수 없습니다.") from exc

    project.status = "transcribing"
    project.whisper_model = request.model
    project.progress = 0.0
    project.error = None
    store.save(project)

    background_tasks.add_task(_run_transcription, project_id, request.model, store)
    return project
