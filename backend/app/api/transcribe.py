import logging
import time
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException

from app.api.deps import get_store
from app.core.config import WHISPER_MODEL_SIZES, get_settings
from app.models.schemas import MediaItem, TranscribeRequest
from app.services import cancellation, diarization_service, readability_service, whisper_service
from app.services.progress_reporter import make_progress_reporter, make_stage_reporter
from app.services.project_store import ProjectNotFoundError, ProjectStore

router = APIRouter(prefix="/projects", tags=["transcribe"])
logger = logging.getLogger(__name__)


def _run_transcription(
    project_id: str,
    item_id: str,
    model_size: str,
    diarize: bool,
    multilingual: bool,
    store: ProjectStore,
) -> None:
    project = store.get(project_id)
    item = next(i for i in project.items if i.id == item_id)
    try:
        segments = whisper_service.transcribe(
            Path(item.media_path),
            model_size=model_size,
            on_progress=make_progress_reporter(project, item, store),
            on_stage=make_stage_reporter(project, item, store),
            should_cancel=lambda: cancellation.is_cancelled(item_id),
            multilingual=multilingual,
        )
        if diarize:
            hf_token = get_settings().hf_token
            if not hf_token:
                raise ValueError(
                    "화자 분리를 사용하려면 HF_TOKEN 설정이 필요합니다 "
                    "(HuggingFace에서 pyannote/speaker-diarization-3.1 모델 이용약관 동의 필요)."
                )
            turns = diarization_service.diarize(
                Path(item.media_path),
                hf_token=hf_token,
                on_stage=make_stage_reporter(project, item, store),
            )
            segments = diarization_service.assign_speakers(segments, turns)
        item.segments = readability_service.apply_readability(segments, use_translation=False)
        item.status = "transcribed"
        item.progress = 1.0
        item.stage = None
        item.started_at = None
        item.error = None
    except whisper_service.TranscriptionCancelled:
        item.status = "error"
        item.stage = None
        item.started_at = None
        item.progress = None
        item.error = "사용자가 전사를 취소했습니다."
    except Exception as exc:  # pragma: no cover - depends on optional heavy deps
        logger.exception("Transcription failed for item %s", item_id)
        item.status = "error"
        item.stage = None
        item.started_at = None
        item.error = str(exc)
    finally:
        cancellation.clear_cancel(item_id)
    store.save(project)


@router.post("/{project_id}/items/{item_id}/transcribe", response_model=MediaItem)
async def transcribe_item(
    project_id: str,
    item_id: str,
    request: TranscribeRequest,
    background_tasks: BackgroundTasks,
    store: ProjectStore = Depends(get_store),
) -> MediaItem:
    if request.model not in WHISPER_MODEL_SIZES:
        raise HTTPException(status_code=400, detail=f"지원하지 않는 모델입니다: {request.model}")
    try:
        project = store.get(project_id)
    except ProjectNotFoundError as exc:
        raise HTTPException(status_code=404, detail="프로젝트를 찾을 수 없습니다.") from exc
    item = next((i for i in project.items if i.id == item_id), None)
    if item is None:
        raise HTTPException(status_code=404, detail="파일을 찾을 수 없습니다.")

    cancellation.clear_cancel(item_id)
    item.status = "transcribing"
    item.whisper_model = request.model
    item.progress = 0.0
    item.stage = None
    item.started_at = time.time()
    item.error = None
    store.save(project)

    background_tasks.add_task(
        _run_transcription,
        project_id,
        item_id,
        request.model,
        request.diarize,
        request.multilingual,
        store,
    )
    return item
