import pytest
from fastapi.testclient import TestClient

from app.api import chat
from app.auth import verify_supabase_jwt
from app.core.config import Settings
from app.main import app


@pytest.fixture(autouse=True)
def _clear_overrides():
    yield
    app.dependency_overrides.clear()


def test_chat_completions_requires_auth(monkeypatch):
    monkeypatch.setattr(
        "app.auth.get_settings", lambda: Settings(supabase_jwt_secret="test-secret")
    )
    client = TestClient(app)
    response = client.post("/v1/chat/completions", json={"model": "gpt-4o-mini"})
    assert response.status_code == 401


def test_chat_completions_returns_503_without_openai_key(monkeypatch):
    app.dependency_overrides[verify_supabase_jwt] = lambda: "user-1"
    monkeypatch.setattr(chat, "get_settings", lambda: Settings(openai_api_key=None))
    client = TestClient(app)

    response = client.post("/v1/chat/completions", json={"model": "gpt-4o-mini"})

    assert response.status_code == 503


def test_chat_completions_proxies_to_openai(monkeypatch):
    app.dependency_overrides[verify_supabase_jwt] = lambda: "user-1"
    monkeypatch.setattr(
        chat,
        "get_settings",
        lambda: Settings(openai_api_key="sk-test", openai_base_url="https://api.openai.com/v1"),
    )

    captured = {}

    class FakeUpstreamResponse:
        status_code = 200
        content = b'{"choices": []}'
        headers = {"content-type": "application/json"}

    class FakeAsyncClient:
        def __init__(self, timeout):
            captured["timeout"] = timeout

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return None

        async def post(self, url, headers, content):
            captured["url"] = url
            captured["headers"] = headers
            captured["content"] = content
            return FakeUpstreamResponse()

    monkeypatch.setattr(chat.httpx, "AsyncClient", FakeAsyncClient)
    client = TestClient(app)

    response = client.post("/v1/chat/completions", json={"model": "gpt-4o-mini"})

    assert response.status_code == 200
    assert response.json() == {"choices": []}
    assert captured["url"] == "https://api.openai.com/v1/chat/completions"
    assert captured["headers"]["Authorization"] == "Bearer sk-test"
