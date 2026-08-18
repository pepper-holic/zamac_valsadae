import time
from collections import defaultdict, deque

from fastapi import Depends, HTTPException

from app.auth import verify_supabase_jwt
from app.core.config import get_settings

_WINDOW_SECONDS = 60.0

# In-memory only — correct because the relay runs as a single uvicorn
# process (server/deploy/relay.service has no --workers flag, so there is
# exactly one event loop and this dict is never shared/duplicated). Would
# need a shared store (Redis) if the service is ever scaled to multiple
# workers or processes.
_request_log: dict[str, deque[float]] = defaultdict(deque)


def reset_rate_limit_state() -> None:
    """Test-only helper: clears in-memory rate limit counters between tests."""
    _request_log.clear()


def _prune_expired(timestamps: deque[float], now: float) -> None:
    while timestamps and now - timestamps[0] > _WINDOW_SECONDS:
        timestamps.popleft()


def check_rate_limit(user_id: str = Depends(verify_supabase_jwt)) -> str:
    """FastAPI dependency: enforces a per-user sliding-window request limit.

    Runs after JWT verification so limits are keyed by the authenticated
    user, not by IP (multiple users can share an IP; one user can't burn
    another user's quota).
    """
    settings = get_settings()
    limit = settings.chat_rate_limit_per_minute
    if limit <= 0:
        return user_id

    now = time.monotonic()
    timestamps = _request_log[user_id]
    _prune_expired(timestamps, now)

    if len(timestamps) >= limit:
        raise HTTPException(
            status_code=429,
            detail=f"Rate limit exceeded: max {limit} requests per minute",
        )

    timestamps.append(now)
    return user_id
