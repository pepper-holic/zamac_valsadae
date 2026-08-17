from fastapi import APIRouter

from app.core.config import WHISPER_MODEL_SIZES
from app.models.schemas import ModelStatus
from app.services import whisper_service

router = APIRouter(prefix="/models", tags=["models"])


@router.get("/status", response_model=ModelStatus)
async def get_model_status() -> ModelStatus:
    return ModelStatus(
        whisper={size: whisper_service.is_model_cached(size) for size in WHISPER_MODEL_SIZES},
        whisper_device=whisper_service.get_transcribe_device(),
    )
