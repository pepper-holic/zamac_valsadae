import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services import auth_state


@pytest.fixture(autouse=True)
def _clear_session():
    auth_state.clear_session()
    yield
    auth_state.clear_session()


@pytest.fixture
def client():
    with TestClient(app) as test_client:
        yield test_client


def test_get_session_reports_logged_out_by_default(client):
    response = client.get("/auth/session")

    assert response.status_code == 200
    assert response.json() == {"logged_in": False, "email": None}


def test_post_session_logs_in_and_is_reflected_by_get(client):
    response = client.post(
        "/auth/session", json={"access_token": "jwt-abc", "email": "a@b.com"}
    )

    assert response.status_code == 200
    assert response.json() == {"logged_in": True, "email": "a@b.com"}
    assert client.get("/auth/session").json() == {"logged_in": True, "email": "a@b.com"}


def test_delete_session_logs_out(client):
    client.post("/auth/session", json={"access_token": "jwt-abc", "email": "a@b.com"})

    response = client.delete("/auth/session")

    assert response.status_code == 200
    assert response.json() == {"logged_in": False, "email": None}
    assert client.get("/auth/session").json() == {"logged_in": False, "email": None}
