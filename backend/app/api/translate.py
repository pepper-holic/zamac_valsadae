import logging
import time

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException

from app.api.deps import get_store
from app.core.config import get_settings
from app.models.schemas import MediaItem
from app.services import auth_state, cancellation, readability_service, translation_service
from app.services.progress_reporter import make_progress_reporter
from app.services.project_store import ProjectNotFoundError, ProjectStore

router = APIRouter(prefix="/projects", tags=["translate"])
logger = logging.getLogger(__name__)


def _run_translation(project_id: str, item_id: str, store: ProjectStore) -> None:
    project = store.get(project_id)
    item = next(i for i in project.items if i.id == item_id)
    try:
        session = auth_state.get_session()
        translator = translation_service.get_translator(
            get_settings(),
            session_token=session.access_token if session else None,
        )
        # 용어집은 프로젝트(파일 모음) 전체에서 공유하며, 번역 메모리도 같은
        # 프로젝트 안에서 반복 번역되는 문장을 재사용하기 위해 프로젝트
        # 단위로 캐시합니다(파일 단위가 아님) - 시리즈 안의 다른 파일과도
        # 재사용됩니다. 언어를 자동 감지해서 번역하므로 방향 구분은 없습니다.
        translation_memory = store.load_translation_memory(project_id)
        translated_segments = translation_service.translate_segments(
            item.segments,
            translator=translator,
            on_progress=make_progress_reporter(project, item, store),
            should_cancel=lambda: cancellation.is_cancelled(item_id),
            glossary=project.glossary,
            translation_memory=translation_memory,
        )
        store.save_translation_memory(
            project_id,
            {
                segment.text: segment.translation
                for segment in translated_segments
                if segment.translation
            },
        )
        item.segments = readability_service.apply_readability(
            translated_segments, use_translation=True
        )
        item.status = "translated"
        item.progress = 1.0
        item.stage = None
        item.started_at = None
        item.error = None
    except translation_service.TranslationCancelled:
        item.status = "error"
        item.stage = None
        item.started_at = None
        item.progress = None
        item.error = "사용자가 번역을 취소했습니다."
    except Exception as exc:  # pragma: no cover - depends on optional heavy deps / network
        logger.exception("Translation failed for item %s", item_id)
        item.status = "error"
        item.stage = None
        item.started_at = None
        item.error = str(exc)
    finally:
        cancellation.clear_cancel(item_id)
    store.save(project)


@router.post("/{project_id}/items/{item_id}/translate", response_model=MediaItem)
async def translate_item(
    project_id: str,
    item_id: str,
    background_tasks: BackgroundTasks,
    store: ProjectStore = Depends(get_store),
) -> MediaItem:
    try:
        project = store.get(project_id)
    except ProjectNotFoundError as exc:
        raise HTTPException(status_code=404, detail="프로젝트를 찾을 수 없습니다.") from exc
    item = next((i for i in project.items if i.id == item_id), None)
    if item is None:
        raise HTTPException(status_code=404, detail="파일을 찾을 수 없습니다.")
    if not item.segments:
        raise HTTPException(status_code=400, detail="번역할 세그먼트가 없습니다. 먼저 전사를 실행하세요.")

    cancellation.clear_cancel(item_id)
    item.status = "translating"
    item.progress = 0.0
    item.stage = None
    item.started_at = time.time()
    item.error = None
    store.save(project)

    background_tasks.add_task(_run_translation, project_id, item_id, store)
    return item
