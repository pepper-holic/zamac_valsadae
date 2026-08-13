from fastapi import APIRouter, Depends, HTTPException

from app.api.deps import get_store
from app.core.config import WHISPER_MODEL_SIZES
from app.models.schemas import MediaItem, Project, TranscribeRequest
from app.services import cancellation
from app.services.project_store import ItemNotFoundError, ProjectNotFoundError, ProjectStore
from app.services.transcription_queue import TranscribeJob, enqueue

router = APIRouter(prefix="/projects", tags=["transcribe"])


@router.post("/{project_id}/items/{item_id}/transcribe", response_model=MediaItem)
async def transcribe_item(
    project_id: str,
    item_id: str,
    request: TranscribeRequest,
    store: ProjectStore = Depends(get_store),
) -> MediaItem:
    if request.model not in WHISPER_MODEL_SIZES:
        raise HTTPException(status_code=400, detail=f"지원하지 않는 모델입니다: {request.model}")

    def mark_queued(project: Project) -> None:
        item = next((i for i in project.items if i.id == item_id), None)
        if item is None:
            raise ItemNotFoundError(item_id)
        item.status = "queued"
        item.whisper_model = request.model
        item.progress = None
        item.stage = None
        item.started_at = None
        item.error = None

    cancellation.clear_cancel(item_id)
    try:
        updated_project = store.update(project_id, mark_queued)
    except ProjectNotFoundError as exc:
        raise HTTPException(status_code=404, detail="프로젝트를 찾을 수 없습니다.") from exc
    except ItemNotFoundError as exc:
        raise HTTPException(status_code=404, detail="파일을 찾을 수 없습니다.") from exc

    enqueue(
        TranscribeJob(
            project_id=project_id,
            item_id=item_id,
            model_size=request.model,
            diarize=request.diarize,
            multilingual=request.multilingual,
        ),
        store,
    )
    return next(i for i in updated_project.items if i.id == item_id)
