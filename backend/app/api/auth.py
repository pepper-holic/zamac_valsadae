from fastapi import APIRouter

from app.models.schemas import AuthSessionRequest, AuthStatus
from app.services import auth_state

router = APIRouter(prefix="/auth", tags=["auth"])


@router.get("/session", response_model=AuthStatus)
async def get_session() -> AuthStatus:
    session = auth_state.get_session()
    if session is None:
        return AuthStatus(logged_in=False)
    return AuthStatus(logged_in=True, email=session.email)


@router.post("/session", response_model=AuthStatus)
async def set_session(request: AuthSessionRequest) -> AuthStatus:
    auth_state.set_session(access_token=request.access_token, email=request.email)
    return AuthStatus(logged_in=True, email=request.email)


@router.delete("/session", response_model=AuthStatus)
async def clear_session() -> AuthStatus:
    auth_state.clear_session()
    return AuthStatus(logged_in=False)
