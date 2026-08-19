import json

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request, Response

from app.core.config import get_settings
from app.rate_limit import check_rate_limit, record_token_usage

router = APIRouter()


@router.post("/v1/chat/completions")
async def chat_completions(
    request: Request,
    user_id: str = Depends(check_rate_limit),
) -> Response:
    settings = get_settings()
    if not settings.openai_api_key:
        raise HTTPException(status_code=503, detail="Server has no OpenAI API key configured yet")

    body = await request.body()
    if len(body) > settings.chat_max_body_bytes:
        raise HTTPException(status_code=413, detail="Request body too large")

    try:
        payload = json.loads(body)
    except ValueError as error:
        raise HTTPException(status_code=400, detail="Request body must be JSON") from error
    if not isinstance(payload, dict):
        raise HTTPException(status_code=400, detail="Request body must be a JSON object")
    if settings.openai_model_override:
        payload["model"] = settings.openai_model_override
    # The desktop client never sends max_tokens, leaving completion length
    # (and thus cost) unbounded upstream - inject the ceiling when absent,
    # clamp it down when the client sends something larger.
    requested_max_tokens = payload.get("max_tokens", settings.chat_max_completion_tokens)
    if not isinstance(requested_max_tokens, int) or isinstance(requested_max_tokens, bool):
        raise HTTPException(status_code=400, detail="max_tokens must be an integer")
    payload["max_tokens"] = min(requested_max_tokens, settings.chat_max_completion_tokens)
    body = json.dumps(payload).encode("utf-8")

    async with httpx.AsyncClient(timeout=60) as client:
        upstream = await client.post(
            f"{settings.openai_base_url}/chat/completions",
            headers={
                "Authorization": f"Bearer {settings.openai_api_key}",
                "Content-Type": "application/json",
            },
            content=body,
        )

    if upstream.status_code < 400:
        # Best-effort: the daily count/rate limits above still apply even if
        # this provider's response doesn't include `usage` (or is malformed),
        # so a missing field here degrades to those limits rather than failing
        # the request - the client already has its answer at this point.
        try:
            total_tokens = upstream.json()["usage"]["total_tokens"]
        except (ValueError, KeyError, TypeError, AttributeError):
            total_tokens = None
        if isinstance(total_tokens, int):
            record_token_usage(user_id, total_tokens)

    return Response(
        content=upstream.content,
        status_code=upstream.status_code,
        media_type=upstream.headers.get("content-type", "application/json"),
    )
