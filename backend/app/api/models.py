from fastapi import APIRouter

from app.core.config import WHISPER_MODEL_SIZES, get_settings
from app.models.schemas import ModelStatus, TranslationDirection
from app.services import whisper_service
from app.services.translation_service import LocalTranslator

router = APIRouter(prefix="/models", tags=["models"])

_TRANSLATION_DIRECTIONS: tuple[TranslationDirection, ...] = ("ko->en", "en->ko")


@router.get("/status", response_model=ModelStatus)
async def get_model_status() -> ModelStatus:
    translator = LocalTranslator(cache_dir=get_settings().ct2_model_cache_dir)
    return ModelStatus(
        whisper={size: whisper_service.is_model_cached(size) for size in WHISPER_MODEL_SIZES},
        translation={
            direction: translator.is_cached(direction) for direction in _TRANSLATION_DIRECTIONS
        },
    )
