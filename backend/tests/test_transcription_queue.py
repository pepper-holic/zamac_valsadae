import threading
import time

import pytest
from fastapi.testclient import TestClient

from app.api.deps import get_store
from app.core.config import Settings
from app.main import app
from app.models.schemas import Segment
from app.services import transcription_queue
from app.services.diarization_service import SpeakerTurn
from app.services.project_store import ProjectStore


@pytest.fixture
def store(tmp_path):
    return ProjectStore(root_dir=tmp_path)


@pytest.fixture
def client(store):
    app.dependency_overrides[get_store] = lambda: store
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def _create_project(client) -> dict:
    return client.post("/projects", json={}).json()


def _add_item(client, project_id: str, filename: str) -> dict:
    response = client.post(
        f"/projects/{project_id}/items",
        files={"file": (filename, b"fake-audio-bytes", "audio/wav")},
    )
    return response.json()


def _blocking_transcribe(release_event: threading.Event, blocked_item_id: str):
    """Fake whisper_service.transcribe that blocks only for one item, so tests
    can control exactly when the queue is allowed to move on to the next job."""

    def fake_transcribe(media_path, model_size, **kwargs):
        if str(media_path).endswith(blocked_item_id):
            assert release_event.wait(timeout=5), "queue never released the blocked job"
        return [Segment(id="s1", start=0.0, end=1.0, text="ok")]

    return fake_transcribe


def test_second_job_does_not_run_while_first_is_in_progress(client, monkeypatch):
    project = _create_project(client)
    first = _add_item(client, project["id"], filename="a.wav")
    second = _add_item(client, project["id"], filename="b.wav")

    release_first = threading.Event()
    monkeypatch.setattr(
        "app.services.transcription_queue.whisper_service.transcribe",
        _blocking_transcribe(release_first, first["id"]),
    )

    client.post(f"/projects/{project['id']}/items/{first['id']}/transcribe", json={"model": "small"})
    client.post(f"/projects/{project['id']}/items/{second['id']}/transcribe", json={"model": "small"})

    # The worker is a single sequential loop, so as long as the first job is
    # still blocked, the second one cannot have been picked up yet.
    time.sleep(0.2)
    items_while_blocked = client.get(f"/projects/{project['id']}").json()["items"]
    assert items_while_blocked[1]["status"] == "queued"

    release_first.set()
    transcription_queue.wait_until_idle()

    items = client.get(f"/projects/{project['id']}").json()["items"]
    assert items[0]["status"] == "transcribed"
    assert items[1]["status"] == "transcribed"


def test_cancelling_a_queued_item_skips_it_instead_of_running_it(client, monkeypatch):
    project = _create_project(client)
    first = _add_item(client, project["id"], filename="a.wav")
    second = _add_item(client, project["id"], filename="b.wav")

    release_first = threading.Event()
    monkeypatch.setattr(
        "app.services.transcription_queue.whisper_service.transcribe",
        _blocking_transcribe(release_first, first["id"]),
    )

    client.post(f"/projects/{project['id']}/items/{first['id']}/transcribe", json={"model": "small"})
    client.post(f"/projects/{project['id']}/items/{second['id']}/transcribe", json={"model": "small"})

    cancel_response = client.post(f"/projects/{project['id']}/items/{second['id']}/cancel")
    assert cancel_response.status_code == 200
    assert cancel_response.json()["status"] == "uploaded"

    release_first.set()
    transcription_queue.wait_until_idle()

    items = client.get(f"/projects/{project['id']}").json()["items"]
    assert items[0]["status"] == "transcribed"
    assert items[1]["status"] == "uploaded"


_SLOW_STEP_SECONDS = 0.3


def _slow_transcribe(media_path, model_size, **kwargs):
    time.sleep(_SLOW_STEP_SECONDS)
    return [Segment(id="s1", start=0.0, end=1.0, text="hello")]


def _slow_diarize(media_path, hf_token, **kwargs):
    time.sleep(_SLOW_STEP_SECONDS)
    return [SpeakerTurn(start=0.0, end=1.0, speaker="SPEAKER_00")]


def test_diarize_and_transcribe_run_concurrently_not_back_to_back(client, monkeypatch):
    project = _create_project(client)
    item = _add_item(client, project["id"], filename="a.wav")

    monkeypatch.setattr(
        "app.services.transcription_queue.get_settings", lambda: Settings(hf_token="fake-token")
    )
    monkeypatch.setattr("app.services.transcription_queue.whisper_service.transcribe", _slow_transcribe)
    monkeypatch.setattr("app.services.transcription_queue.diarization_service.diarize", _slow_diarize)

    started_at = time.monotonic()
    client.post(
        f"/projects/{project['id']}/items/{item['id']}/transcribe",
        json={"model": "small", "diarize": True},
    )
    transcription_queue.wait_until_idle()
    elapsed = time.monotonic() - started_at

    # Sequential would take >= 2 * _SLOW_STEP_SECONDS; concurrent should stay
    # close to a single step. Generous margin for scheduling/test-env noise.
    assert elapsed < _SLOW_STEP_SECONDS * 1.7

    items = client.get(f"/projects/{project['id']}").json()["items"]
    assert items[0]["status"] == "transcribed"
    assert items[0]["segments"][0]["speaker"] == "SPEAKER_00"


def test_diarize_without_hf_token_fails_the_job_without_running_diarize(client, monkeypatch):
    project = _create_project(client)
    item = _add_item(client, project["id"], filename="a.wav")

    monkeypatch.setattr(
        "app.services.transcription_queue.get_settings", lambda: Settings(hf_token=None)
    )
    monkeypatch.setattr("app.services.transcription_queue.whisper_service.transcribe", _slow_transcribe)
    diarize_calls = []
    monkeypatch.setattr(
        "app.services.transcription_queue.diarization_service.diarize",
        lambda *a, **k: diarize_calls.append(1) or _slow_diarize(*a, **k),
    )

    client.post(
        f"/projects/{project['id']}/items/{item['id']}/transcribe",
        json={"model": "small", "diarize": True},
    )
    transcription_queue.wait_until_idle()

    items = client.get(f"/projects/{project['id']}").json()["items"]
    assert items[0]["status"] == "error"
    assert "HF_TOKEN" in items[0]["error"]
    assert diarize_calls == []
