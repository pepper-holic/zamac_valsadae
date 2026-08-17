import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import ec
from fastapi import HTTPException

from app import auth
from app.core.config import Settings


def test_verify_supabase_jwt_returns_501_when_not_configured(monkeypatch):
    monkeypatch.setattr(
        auth, "get_settings", lambda: Settings(supabase_url=None, supabase_jwt_secret=None)
    )

    with pytest.raises(HTTPException) as excinfo:
        auth.verify_supabase_jwt(authorization="Bearer whatever")

    assert excinfo.value.status_code == 501


def test_verify_supabase_jwt_rejects_missing_header(monkeypatch):
    monkeypatch.setattr(
        auth, "get_settings", lambda: Settings(supabase_url=None, supabase_jwt_secret="test-secret")
    )

    with pytest.raises(HTTPException) as excinfo:
        auth.verify_supabase_jwt(authorization=None)

    assert excinfo.value.status_code == 401


class TestLegacyHs256:
    """SUPABASE_URL not configured -> falls back to the shared HS256 secret."""

    def test_rejects_invalid_signature(self, monkeypatch):
        monkeypatch.setattr(
            auth, "get_settings", lambda: Settings(supabase_url=None, supabase_jwt_secret="test-secret")
        )
        token = jwt.encode({"sub": "user-1", "aud": "authenticated"}, "wrong-secret", algorithm="HS256")

        with pytest.raises(HTTPException) as excinfo:
            auth.verify_supabase_jwt(authorization=f"Bearer {token}")

        assert excinfo.value.status_code == 401

    def test_returns_user_id_for_valid_token(self, monkeypatch):
        monkeypatch.setattr(
            auth, "get_settings", lambda: Settings(supabase_url=None, supabase_jwt_secret="test-secret")
        )
        token = jwt.encode({"sub": "user-1", "aud": "authenticated"}, "test-secret", algorithm="HS256")

        assert auth.verify_supabase_jwt(authorization=f"Bearer {token}") == "user-1"


def _fake_jwks_client(monkeypatch, signing_key, raises: Exception | None = None):
    class FakeSigningKey:
        key = signing_key

    class FakeJwksClient:
        def __init__(self, uri, cache_keys=True):
            self.uri = uri

        def get_signing_key_from_jwt(self, token):
            if raises is not None:
                raise raises
            return FakeSigningKey()

    monkeypatch.setattr(jwt, "PyJWKClient", FakeJwksClient)
    auth._jwks_clients.clear()


class TestJwks:
    """SUPABASE_URL configured -> verifies against the project's published
    JWKS (what current Supabase projects sign with: ES256/RS256), instead
    of a shared secret.
    """

    def test_returns_user_id_for_valid_es256_token(self, monkeypatch):
        monkeypatch.setattr(
            auth,
            "get_settings",
            lambda: Settings(supabase_url="https://example.supabase.co", supabase_jwt_secret=None),
        )
        private_key = ec.generate_private_key(ec.SECP256R1())
        _fake_jwks_client(monkeypatch, private_key.public_key())

        token = jwt.encode(
            {"sub": "user-1", "aud": "authenticated"}, private_key, algorithm="ES256"
        )

        assert auth.verify_supabase_jwt(authorization=f"Bearer {token}") == "user-1"

    def test_rejects_when_jwks_client_raises(self, monkeypatch):
        monkeypatch.setattr(
            auth,
            "get_settings",
            lambda: Settings(supabase_url="https://example.supabase.co", supabase_jwt_secret=None),
        )
        _fake_jwks_client(monkeypatch, None, raises=jwt.PyJWKClientError("no matching key"))

        with pytest.raises(HTTPException) as excinfo:
            auth.verify_supabase_jwt(authorization="Bearer some-token")

        assert excinfo.value.status_code == 401

    def test_rejects_wrong_signing_key(self, monkeypatch):
        monkeypatch.setattr(
            auth,
            "get_settings",
            lambda: Settings(supabase_url="https://example.supabase.co", supabase_jwt_secret=None),
        )
        signing_key = ec.generate_private_key(ec.SECP256R1())
        wrong_key = ec.generate_private_key(ec.SECP256R1())
        _fake_jwks_client(monkeypatch, wrong_key.public_key())

        token = jwt.encode(
            {"sub": "user-1", "aud": "authenticated"}, signing_key, algorithm="ES256"
        )

        with pytest.raises(HTTPException) as excinfo:
            auth.verify_supabase_jwt(authorization=f"Bearer {token}")

        assert excinfo.value.status_code == 401

    def test_prefers_jwks_over_legacy_secret_when_both_configured(self, monkeypatch):
        monkeypatch.setattr(
            auth,
            "get_settings",
            lambda: Settings(
                supabase_url="https://example.supabase.co", supabase_jwt_secret="legacy-secret"
            ),
        )
        private_key = ec.generate_private_key(ec.SECP256R1())
        _fake_jwks_client(monkeypatch, private_key.public_key())

        # signed with the JWKS key, not the legacy secret - only decodable
        # if verify_supabase_jwt actually took the JWKS branch
        token = jwt.encode(
            {"sub": "user-1", "aud": "authenticated"}, private_key, algorithm="ES256"
        )

        assert auth.verify_supabase_jwt(authorization=f"Bearer {token}") == "user-1"
