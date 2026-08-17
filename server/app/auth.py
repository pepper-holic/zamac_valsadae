import jwt
from fastapi import Header, HTTPException

from app.core.config import get_settings

# Newer Supabase projects sign JWTs with an asymmetric key (ES256) by
# default instead of the legacy shared HS256 secret, so verification has to
# go through Supabase's published JWKS rather than a static secret. One
# PyJWKClient per Supabase project URL, reused across requests so the JWKS
# document isn't re-fetched on every call (PyJWKClient caches internally).
_jwks_clients: dict[str, "jwt.PyJWKClient"] = {}


def _get_jwks_client(supabase_url: str) -> "jwt.PyJWKClient":
    if supabase_url not in _jwks_clients:
        jwks_url = f"{supabase_url.rstrip('/')}/auth/v1/.well-known/jwks.json"
        _jwks_clients[supabase_url] = jwt.PyJWKClient(jwks_url, cache_keys=True)
    return _jwks_clients[supabase_url]


def _extract_bearer_token(authorization: str | None) -> str:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Missing bearer token")
    return authorization.split(" ", 1)[1].strip()


def verify_supabase_jwt(authorization: str | None = Header(default=None)) -> str:
    """FastAPI dependency that verifies a Supabase-issued JWT and returns the
    user id (the `sub` claim).

    Prefers JWKS verification (SUPABASE_URL configured) since that's what
    current Supabase projects sign with (ES256/RS256, asymmetric). Falls
    back to the legacy shared HS256 secret (SUPABASE_JWT_SECRET) for
    projects that still use it and haven't set SUPABASE_URL.
    """
    settings = get_settings()
    token = _extract_bearer_token(authorization)

    if settings.supabase_url:
        try:
            signing_key = _get_jwks_client(settings.supabase_url).get_signing_key_from_jwt(token)
            payload = jwt.decode(
                token,
                signing_key.key,
                algorithms=["ES256", "RS256"],
                audience="authenticated",
            )
        except jwt.PyJWTError as error:
            raise HTTPException(status_code=401, detail=f"Invalid token: {error}") from error
    elif settings.supabase_jwt_secret:
        try:
            payload = jwt.decode(
                token,
                settings.supabase_jwt_secret,
                algorithms=["HS256"],
                audience="authenticated",
            )
        except jwt.PyJWTError as error:
            raise HTTPException(status_code=401, detail=f"Invalid token: {error}") from error
    else:
        raise HTTPException(status_code=501, detail="Supabase auth not configured on this server yet")

    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(status_code=401, detail="Token missing subject")
    return user_id
