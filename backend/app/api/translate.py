import logging

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException

from app.api.deps import get_store
from app.core.config import get_settings
from app.models.schemas import Project, TranslateRequest
from app.services import translation_service
from app.services.progress_reporter import make_progress_reporter, make_stage_reporter
from app.services.project_store import ProjectNotFoundError, ProjectStore

router = APIRouter(prefix="/projects", tags=["translate"])
logger = logging.getLogger(__name__)


def _run_translation(project_id: str, request: TranslateRequest, store: ProjectStore) -> None:
    project = store.get(project_id)
    try:
        translator = translation_service.get_translator(
            request.engine, get_settings(), on_stage=make_stage_reporter(project, store)
        )
        project.segments = translation_service.translate_segments(
            project.segments,
            direction=request.direction,
            translator=translator,
            on_progress=make_progress_reporter(project, store),
        )
        project.status = "translated"
        project.progress = 1.0
        project.stage = None
        project.error = None
    except Exception as exc:  # pragma: no cover - depends on optional heavy deps / network
        logger.exception("Translation failed for project %s", project_id)
        project.status = "error"
        project.stage = None
        project.error = str(exc)
    store.save(project)


@router.post("/{project_id}/translate", response_model=Project)
async def translate_project(
    project_id: str,
    request: TranslateRequest,
    background_tasks: BackgroundTasks,
    store: ProjectStore = Depends(get_store),
) -> Project:
    try:
        project = store.get(project_id)
    except ProjectNotFoundError as exc:
        raise HTTPException(status_code=404, detail="프로젝트를 찾을 수 없습니다.") from exc
    if not project.segments:
        raise HTTPException(status_code=400, detail="번역할 세그먼트가 없습니다. 먼저 전사를 실행하세요.")

    project.status = "translating"
    project.progress = 0.0
    project.stage = None
    project.error = None
    store.save(project)

    background_tasks.add_task(_run_translation, project_id, request, store)
    return project
