import json

import pytest
from fastapi.testclient import TestClient

from app.api import chat
from app.auth import verify_supabase_jwt
from app.core.config import Settings
from app.main import app
from app.rate_limit import reset_rate_limit_state


@pytest.fixture(autouse=True)
def _clear_overrides():
    reset_rate_limit_state()
    yield
    app.dependency_overrides.clear()
    reset_rate_limit_state()


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
    assert json.loads(captured["content"])["model"] == "gpt-4o-mini"


def test_chat_completions_overrides_model_for_a_different_provider(monkeypatch):
    app.dependency_overrides[verify_supabase_jwt] = lambda: "user-1"
    monkeypatch.setattr(
        chat,
        "get_settings",
        lambda: Settings(
            openai_api_key="gemini-key",
            openai_base_url="https://generativelanguage.googleapis.com/v1beta/openai",
            openai_model_override="gemini-2.0-flash",
        ),
    )

    captured = {}

    class FakeUpstreamResponse:
        status_code = 200
        content = b'{"choices": []}'
        headers = {"content-type": "application/json"}

    class FakeAsyncClient:
        def __init__(self, timeout):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return None

        async def post(self, url, headers, content):
            captured["content"] = content
            return FakeUpstreamResponse()

    monkeypatch.setattr(chat.httpx, "AsyncClient", FakeAsyncClient)
    client = TestClient(app)

    response = client.post("/v1/chat/completions", json={"model": "gpt-4o-mini", "messages": []})

    assert response.status_code == 200
    sent_body = json.loads(captured["content"])
    assert sent_body["model"] == "gemini-2.0-flash"
    assert sent_body["messages"] == []


def test_chat_completions_rejects_oversized_body(monkeypatch):
    app.dependency_overrides[verify_supabase_jwt] = lambda: "user-1"
    monkeypatch.setattr(
        chat,
        "get_settings",
        lambda: Settings(openai_api_key="sk-test", chat_max_body_bytes=10),
    )
    client = TestClient(app)

    response = client.post("/v1/chat/completions", json={"model": "gpt-4o-mini", "messages": []})

    assert response.status_code == 413


def test_chat_completions_enforces_per_user_rate_limit(monkeypatch):
    app.dependency_overrides[verify_supabase_jwt] = lambda: "user-1"
    monkeypatch.setattr(
        chat,
        "get_settings",
        lambda: Settings(openai_api_key="sk-test", chat_rate_limit_per_minute=2),
    )
    monkeypatch.setattr(
        "app.rate_limit.get_settings",
        lambda: Settings(openai_api_key="sk-test", chat_rate_limit_per_minute=2),
    )

    class FakeUpstreamResponse:
        status_code = 200
        content = b'{"choices": []}'
        headers = {"content-type": "application/json"}

    class FakeAsyncClient:
        def __init__(self, timeout):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return None

        async def post(self, url, headers, content):
            return FakeUpstreamResponse()

    monkeypatch.setattr(chat.httpx, "AsyncClient", FakeAsyncClient)
    client = TestClient(app)
    payload = {"model": "gpt-4o-mini", "messages": []}

    assert client.post("/v1/chat/completions", json=payload).status_code == 200
    assert client.post("/v1/chat/completions", json=payload).status_code == 200
    third = client.post("/v1/chat/completions", json=payload)

    assert third.status_code == 429


def test_chat_completions_rate_limit_is_per_user(monkeypatch):
    monkeypatch.setattr(
        "app.rate_limit.get_settings",
        lambda: Settings(chat_rate_limit_per_minute=1),
    )
    monkeypatch.setattr(
        chat,
        "get_settings",
        lambda: Settings(openai_api_key="sk-test", chat_rate_limit_per_minute=1),
    )

    class FakeUpstreamResponse:
        status_code = 200
        content = b'{"choices": []}'
        headers = {"content-type": "application/json"}

    class FakeAsyncClient:
        def __init__(self, timeout):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return None

        async def post(self, url, headers, content):
            return FakeUpstreamResponse()

    monkeypatch.setattr(chat.httpx, "AsyncClient", FakeAsyncClient)
    client = TestClient(app)
    payload = {"model": "gpt-4o-mini", "messages": []}

    app.dependency_overrides[verify_supabase_jwt] = lambda: "user-a"
    assert client.post("/v1/chat/completions", json=payload).status_code == 200
    assert client.post("/v1/chat/completions", json=payload).status_code == 429

    app.dependency_overrides[verify_supabase_jwt] = lambda: "user-b"
    assert client.post("/v1/chat/completions", json=payload).status_code == 200
