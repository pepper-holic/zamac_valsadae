import time
from collections import defaultdict, deque

from fastapi import Depends, HTTPException

from app.auth import verify_supabase_jwt
from app.core.config import get_settings

_WINDOW_SECONDS = 60.0
_DAILY_WINDOW_SECONDS = 86400.0

# In-memory only — correct because the relay runs as a single uvicorn
# process (server/deploy/relay.service has no --workers flag, so there is
# exactly one event loop and this dict is never shared/duplicated). Would
# need a shared store (Redis) if the service is ever scaled to multiple
# workers or processes.
_request_log: dict[str, deque[float]] = defaultdict(deque)
# Separate from _request_log (different window/prune cadence): the
# per-minute log alone still allows a near-unlimited number of requests
# spread across a day, so this bounds total daily cost per account.
_daily_request_log: dict[str, deque[float]] = defaultdict(deque)
# Request *count* alone doesn't bound cost - a single request's prompt can
# be as large as CHAT_MAX_BODY_BYTES regardless of how many requests remain
# in the daily count budget. This tracks actual (timestamp, total_tokens)
# usage reported by the upstream provider's response.
_daily_token_log: dict[str, deque[tuple[float, int]]] = defaultdict(deque)


def reset_rate_limit_state() -> None:
    """Test-only helper: clears in-memory rate limit counters between tests."""
    _request_log.clear()
    _daily_request_log.clear()
    _daily_token_log.clear()


def _prune_expired(timestamps: deque[float], now: float, window_seconds: float) -> None:
    while timestamps and now - timestamps[0] > window_seconds:
        timestamps.popleft()


def _prune_expired_tokens(entries: deque[tuple[float, int]], now: float, window_seconds: float) -> None:
    while entries and now - entries[0][0] > window_seconds:
        entries.popleft()


def record_token_usage(user_id: str, tokens: int) -> None:
    """Called after a successful upstream response to record its actual
    prompt+completion token cost against the user's rolling daily budget.

    Not part of check_rate_limit() because the token count for a request is
    only known after the upstream call returns, not before it - the
    pre-request check in check_rate_limit() can only look at usage recorded
    by *previous* requests.
    """
    if tokens <= 0:
        return
    _daily_token_log[user_id].append((time.monotonic(), tokens))


def check_rate_limit(user_id: str = Depends(verify_supabase_jwt)) -> str:
    """FastAPI dependency: enforces a per-user sliding-window request limit.

    Runs after JWT verification so limits are keyed by the authenticated
    user, not by IP (multiple users can share an IP; one user can't burn
    another user's quota).
    """
    settings = get_settings()
    now = time.monotonic()

    limit = settings.chat_rate_limit_per_minute
    if limit > 0:
        timestamps = _request_log[user_id]
        _prune_expired(timestamps, now, _WINDOW_SECONDS)
        if len(timestamps) >= limit:
            raise HTTPException(
                status_code=429,
                detail=f"Rate limit exceeded: max {limit} requests per minute",
            )

    daily_limit = settings.chat_daily_limit_per_user
    if daily_limit > 0:
        daily_timestamps = _daily_request_log[user_id]
        _prune_expired(daily_timestamps, now, _DAILY_WINDOW_SECONDS)
        if len(daily_timestamps) >= daily_limit:
            raise HTTPException(
                status_code=429,
                detail=f"Daily limit exceeded: max {daily_limit} requests per day",
            )

    daily_token_limit = settings.chat_daily_token_limit_per_user
    if daily_token_limit > 0:
        token_entries = _daily_token_log[user_id]
        _prune_expired_tokens(token_entries, now, _DAILY_WINDOW_SECONDS)
        used_tokens = sum(tokens for _, tokens in token_entries)
        if used_tokens >= daily_token_limit:
            raise HTTPException(
                status_code=429,
                detail=f"Daily token budget exceeded: max {daily_token_limit} tokens per day",
            )

    if limit > 0:
        _request_log[user_id].append(now)
    if daily_limit > 0:
        _daily_request_log[user_id].append(now)
    return user_id
