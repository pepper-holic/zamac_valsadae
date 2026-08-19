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
    # Per-user sliding-window limit on /v1/chat/completions. Set to 0 to
    # disable (e.g. for local dev). Default is generous enough for normal
    # subtitle-translation batches but blocks a single account from burning
    # the whole server's OpenAI/Gemini quota.
    chat_rate_limit_per_minute: int = int(os.environ.get("CHAT_RATE_LIMIT_PER_MINUTE", "20"))
    # Subtitle translation batches are small JSON payloads; this is a safety
    # ceiling against oversized/malicious request bodies, not a normal-use
    # constraint.
    chat_max_body_bytes: int = int(os.environ.get("CHAT_MAX_BODY_BYTES", str(300_000)))
    # The desktop client never sends max_tokens (see ApiTranslator in
    # backend/app/services/translation_service.py), so upstream completions
    # are otherwise unbounded - a single authenticated account could burn
    # unlimited output-token cost within the per-minute request limit. This
    # is injected/clamped onto every request regardless of what the client
    # sends.
    chat_max_completion_tokens: int = int(os.environ.get("CHAT_MAX_COMPLETION_TOKENS", "1024"))
    # Per-authenticated-user request count over a rolling 24h window,
    # independent of CHAT_RATE_LIMIT_PER_MINUTE (which alone still allows a
    # near-unlimited number of requests per day). 0 disables the limit.
    chat_daily_limit_per_user: int = int(os.environ.get("CHAT_DAILY_LIMIT_PER_USER", "300"))
    # Per-authenticated-user cumulative prompt+completion token count over a
    # rolling 24h window, read from each upstream response's `usage.total_tokens`.
    # CHAT_DAILY_LIMIT_PER_USER alone bounds request *count*, not actual cost -
    # a request's prompt can be up to CHAT_MAX_BODY_BYTES regardless of how
    # many requests remain in the daily count budget. 0 disables the limit.
    chat_daily_token_limit_per_user: int = int(
        os.environ.get("CHAT_DAILY_TOKEN_LIMIT_PER_USER", "200000")
    )


def get_settings() -> Settings:
    return Settings()
