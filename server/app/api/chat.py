import json

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request, Response

from app.auth import verify_supabase_jwt
from app.core.config import get_settings

router = APIRouter()


@router.post("/v1/chat/completions")
async def chat_completions(
    request: Request,
    user_id: str = Depends(verify_supabase_jwt),
) -> Response:
    settings = get_settings()
    if not settings.openai_api_key:
        raise HTTPException(status_code=503, detail="Server has no OpenAI API key configured yet")

    body = await request.body()
    if settings.openai_model_override:
        try:
            payload = json.loads(body)
        except ValueError as error:
            raise HTTPException(status_code=400, detail="Request body must be JSON") from error
        payload["model"] = settings.openai_model_override
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
    return Response(
        content=upstream.content,
        status_code=upstream.status_code,
        media_type=upstream.headers.get("content-type", "application/json"),
    )
