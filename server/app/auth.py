import jwt
from fastapi import Header, HTTPException

from app.core.config import get_settings


def _extract_bearer_token(authorization: str | None) -> str:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Missing bearer token")
    return authorization.split(" ", 1)[1].strip()


def verify_supabase_jwt(authorization: str | None = Header(default=None)) -> str:
    """FastAPI dependency that verifies a Supabase-issued JWT and returns the
    user id (the `sub` claim).

    Supabase signs its JWTs with the project's JWT secret (HS256) - this
    checks the signature and expiry against that shared secret rather than
    fetching a JWKS, since it's the simpler option and matches how Supabase
    issues tokens by default.
    """
    settings = get_settings()
    if not settings.supabase_jwt_secret:
        raise HTTPException(status_code=501, detail="Supabase auth not configured on this server yet")

    token = _extract_bearer_token(authorization)
    try:
        payload = jwt.decode(
            token,
            settings.supabase_jwt_secret,
            algorithms=["HS256"],
            audience="authenticated",
        )
    except jwt.InvalidTokenError as error:
        raise HTTPException(status_code=401, detail=f"Invalid token: {error}") from error

    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(status_code=401, detail="Token missing subject")
    return user_id
