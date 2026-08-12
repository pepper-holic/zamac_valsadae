import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    openai_api_key: str | None = os.environ.get("OPENAI_API_KEY")
    openai_base_url: str = os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1")
    # The desktop app always requests "gpt-4o-mini" (see ApiTranslator in
    # backend/app/services/translation_service.py) since it was written
    # against OpenAI. When the server relays to a different OpenAI-compatible
    # provider (Gemini, Groq, ...) that model name is meaningless there, so
    # this lets the server swap in whatever model name that provider expects
    # without the client needing to know or care which provider is behind it.
    openai_model_override: str | None = os.environ.get("OPENAI_MODEL_OVERRIDE")
    supabase_url: str | None = os.environ.get("SUPABASE_URL")
    supabase_jwt_secret: str | None = os.environ.get("SUPABASE_JWT_SECRET")


def get_settings() -> Settings:
    return Settings()
