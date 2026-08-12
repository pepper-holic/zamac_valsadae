import jwt
import pytest
from fastapi import HTTPException

from app import auth
from app.core.config import Settings


def test_verify_supabase_jwt_returns_501_when_not_configured(monkeypatch):
    monkeypatch.setattr(auth, "get_settings", lambda: Settings(supabase_jwt_secret=None))

    with pytest.raises(HTTPException) as excinfo:
        auth.verify_supabase_jwt(authorization="Bearer whatever")

    assert excinfo.value.status_code == 501


def test_verify_supabase_jwt_rejects_missing_header(monkeypatch):
    monkeypatch.setattr(auth, "get_settings", lambda: Settings(supabase_jwt_secret="test-secret"))

    with pytest.raises(HTTPException) as excinfo:
        auth.verify_supabase_jwt(authorization=None)

    assert excinfo.value.status_code == 401


def test_verify_supabase_jwt_rejects_invalid_signature(monkeypatch):
    monkeypatch.setattr(auth, "get_settings", lambda: Settings(supabase_jwt_secret="test-secret"))
    token = jwt.encode({"sub": "user-1", "aud": "authenticated"}, "wrong-secret", algorithm="HS256")

    with pytest.raises(HTTPException) as excinfo:
        auth.verify_supabase_jwt(authorization=f"Bearer {token}")

    assert excinfo.value.status_code == 401


def test_verify_supabase_jwt_returns_user_id_for_valid_token(monkeypatch):
    monkeypatch.setattr(auth, "get_settings", lambda: Settings(supabase_jwt_secret="test-secret"))
    token = jwt.encode({"sub": "user-1", "aud": "authenticated"}, "test-secret", algorithm="HS256")

    assert auth.verify_supabase_jwt(authorization=f"Bearer {token}") == "user-1"
