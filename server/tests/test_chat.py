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


def test_chat_completions_injects_max_tokens_when_client_omits_it(monkeypatch):
    app.dependency_overrides[verify_supabase_jwt] = lambda: "user-1"
    monkeypatch.setattr(
        chat,
        "get_settings",
        lambda: Settings(openai_api_key="sk-test", chat_max_completion_tokens=1024),
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
    assert json.loads(captured["content"])["max_tokens"] == 1024


def test_chat_completions_clamps_client_max_tokens_above_ceiling(monkeypatch):
    app.dependency_overrides[verify_supabase_jwt] = lambda: "user-1"
    monkeypatch.setattr(
        chat,
        "get_settings",
        lambda: Settings(openai_api_key="sk-test", chat_max_completion_tokens=1024),
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

    response = client.post(
        "/v1/chat/completions",
        json={"model": "gpt-4o-mini", "messages": [], "max_tokens": 999999},
    )

    assert response.status_code == 200
    assert json.loads(captured["content"])["max_tokens"] == 1024


def test_chat_completions_rejects_non_integer_max_tokens(monkeypatch):
    app.dependency_overrides[verify_supabase_jwt] = lambda: "user-1"
    monkeypatch.setattr(chat, "get_settings", lambda: Settings(openai_api_key="sk-test"))
    client = TestClient(app)

    response = client.post(
        "/v1/chat/completions",
        json={"model": "gpt-4o-mini", "messages": [], "max_tokens": "a lot"},
    )

    assert response.status_code == 400


def test_chat_completions_enforces_daily_limit_per_user(monkeypatch):
    app.dependency_overrides[verify_supabase_jwt] = lambda: "user-1"
    monkeypatch.setattr(
        chat,
        "get_settings",
        lambda: Settings(openai_api_key="sk-test", chat_rate_limit_per_minute=0, chat_daily_limit_per_user=2),
    )
    monkeypatch.setattr(
        "app.rate_limit.get_settings",
        lambda: Settings(chat_rate_limit_per_minute=0, chat_daily_limit_per_user=2),
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
    assert "Daily limit" in third.json()["detail"]


def test_chat_completions_daily_limit_is_per_user(monkeypatch):
    monkeypatch.setattr(
        "app.rate_limit.get_settings",
        lambda: Settings(chat_rate_limit_per_minute=0, chat_daily_limit_per_user=1),
    )
    monkeypatch.setattr(
        chat,
        "get_settings",
        lambda: Settings(openai_api_key="sk-test", chat_rate_limit_per_minute=0, chat_daily_limit_per_user=1),
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


def test_chat_completions_blocks_when_daily_token_budget_exhausted(monkeypatch):
    from app.rate_limit import record_token_usage

    app.dependency_overrides[verify_supabase_jwt] = lambda: "user-1"
    monkeypatch.setattr(
        chat,
        "get_settings",
        lambda: Settings(
            openai_api_key="sk-test",
            chat_rate_limit_per_minute=0,
            chat_daily_limit_per_user=0,
            chat_daily_token_limit_per_user=100,
        ),
    )
    monkeypatch.setattr(
        "app.rate_limit.get_settings",
        lambda: Settings(
            chat_rate_limit_per_minute=0, chat_daily_limit_per_user=0, chat_daily_token_limit_per_user=100
        ),
    )
    record_token_usage("user-1", 150)

    client = TestClient(app)
    response = client.post("/v1/chat/completions", json={"model": "gpt-4o-mini", "messages": []})

    assert response.status_code == 429
    assert "token budget" in response.json()["detail"]


def test_chat_completions_records_token_usage_from_upstream_response(monkeypatch):
    app.dependency_overrides[verify_supabase_jwt] = lambda: "user-1"
    monkeypatch.setattr(
        chat,
        "get_settings",
        lambda: Settings(
            openai_api_key="sk-test",
            chat_rate_limit_per_minute=0,
            chat_daily_limit_per_user=0,
            chat_daily_token_limit_per_user=150,
        ),
    )
    monkeypatch.setattr(
        "app.rate_limit.get_settings",
        lambda: Settings(
            chat_rate_limit_per_minute=0, chat_daily_limit_per_user=0, chat_daily_token_limit_per_user=150
        ),
    )

    class FakeUpstreamResponse:
        status_code = 200
        content = b'{"choices": [], "usage": {"total_tokens": 100}}'
        headers = {"content-type": "application/json"}

        def json(self):
            return json.loads(self.content)

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

    # First call reports 100 tokens used, leaving 50 of the 150 budget.
    assert client.post("/v1/chat/completions", json=payload).status_code == 200
    # Second call's own 100 tokens haven't happened yet, but the budget
    # check runs before the call and 100 already-used tokens < 150, so it
    # still goes through...
    assert client.post("/v1/chat/completions", json=payload).status_code == 200
    # ...now 200 used >= 150 budget, so a third call is blocked.
    third = client.post("/v1/chat/completions", json=payload)
    assert third.status_code == 429


def test_chat_completions_skips_recording_when_usage_field_missing(monkeypatch):
    app.dependency_overrides[verify_supabase_jwt] = lambda: "user-1"
    monkeypatch.setattr(
        chat,
        "get_settings",
        lambda: Settings(openai_api_key="sk-test", chat_daily_token_limit_per_user=100),
    )
    monkeypatch.setattr(
        "app.rate_limit.get_settings",
        lambda: Settings(chat_daily_token_limit_per_user=100),
    )

    class FakeUpstreamResponse:
        status_code = 200
        content = b'{"choices": []}'
        headers = {"content-type": "application/json"}

        def json(self):
            return json.loads(self.content)

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

    response = client.post("/v1/chat/completions", json={"model": "gpt-4o-mini", "messages": []})

    assert response.status_code == 200


def test_chat_completions_token_budget_is_per_user(monkeypatch):
    from app.rate_limit import record_token_usage

    monkeypatch.setattr(
        "app.rate_limit.get_settings",
        lambda: Settings(
            chat_rate_limit_per_minute=0, chat_daily_limit_per_user=0, chat_daily_token_limit_per_user=100
        ),
    )
    monkeypatch.setattr(
        chat,
        "get_settings",
        lambda: Settings(
            openai_api_key="sk-test",
            chat_rate_limit_per_minute=0,
            chat_daily_limit_per_user=0,
            chat_daily_token_limit_per_user=100,
        ),
    )
    record_token_usage("user-a", 150)

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
    assert client.post("/v1/chat/completions", json=payload).status_code == 429

    app.dependency_overrides[verify_supabase_jwt] = lambda: "user-b"
    assert client.post("/v1/chat/completions", json=payload).status_code == 200


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
