import json

import pytest
from fastapi.testclient import TestClient

from app.api.deps import get_store
from app.main import app
from app.models.schemas import Segment
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


def _upload_project(client) -> dict:
    response = client.post(
        "/projects",
        files={"file": ("sample.wav", b"fake-audio-bytes", "audio/wav")},
    )
    assert response.status_code == 200
    return response.json()


def test_upload_project_creates_uploaded_status(client):
    project = _upload_project(client)

    assert project["filename"] == "sample.wav"
    assert project["status"] == "uploaded"
    assert project["segments"] == []


def test_delete_project_removes_it_from_list(client):
    created = _upload_project(client)

    response = client.delete(f"/projects/{created['id']}")
    assert response.status_code == 204

    assert client.get(f"/projects/{created['id']}").status_code == 404
    assert created["id"] not in [p["id"] for p in client.get("/projects").json()]


def test_delete_missing_project_returns_404(client):
    response = client.delete("/projects/does-not-exist")

    assert response.status_code == 404


def test_get_project_returns_created_project(client):
    created = _upload_project(client)

    response = client.get(f"/projects/{created['id']}")

    assert response.status_code == 200
    assert response.json()["id"] == created["id"]


def test_get_missing_project_returns_404(client):
    response = client.get("/projects/does-not-exist")

    assert response.status_code == 404


def test_transcribe_runs_background_task_and_updates_segments(client, monkeypatch):
    created = _upload_project(client)

    fake_segments = [Segment(id="s1", start=0.0, end=1.0, text="hello")]
    monkeypatch.setattr(
        "app.api.transcribe.whisper_service.transcribe", lambda *a, **k: fake_segments
    )

    response = client.post(f"/projects/{created['id']}/transcribe", json={"model": "small"})
    assert response.status_code == 200

    project = client.get(f"/projects/{created['id']}").json()
    assert project["status"] == "transcribed"
    assert project["segments"][0]["text"] == "hello"


def test_transcribe_reports_final_progress_and_calls_on_progress(client, monkeypatch):
    created = _upload_project(client)

    fake_segments = [Segment(id="s1", start=0.0, end=1.0, text="hello")]

    def fake_transcribe(media_path, model_size, on_progress=None, **kwargs):
        if on_progress:
            on_progress(0.5)
            on_progress(1.0)
        return fake_segments

    monkeypatch.setattr("app.api.transcribe.whisper_service.transcribe", fake_transcribe)

    client.post(f"/projects/{created['id']}/transcribe", json={"model": "small"})

    project = client.get(f"/projects/{created['id']}").json()
    assert project["status"] == "transcribed"
    assert project["progress"] == 1.0


def test_transcribe_rejects_unknown_model(client):
    created = _upload_project(client)

    response = client.post(f"/projects/{created['id']}/transcribe", json={"model": "huge"})

    assert response.status_code == 400


def test_transcribe_marks_error_status_on_failure(client, monkeypatch):
    created = _upload_project(client)

    def _boom(*a, **k):
        raise RuntimeError("model exploded")

    monkeypatch.setattr("app.api.transcribe.whisper_service.transcribe", _boom)

    client.post(f"/projects/{created['id']}/transcribe", json={"model": "small"})

    project = client.get(f"/projects/{created['id']}").json()
    assert project["status"] == "error"
    assert "model exploded" in project["error"]


def test_transcribe_reports_downloading_model_stage(client, monkeypatch):
    created = _upload_project(client)

    def fake_transcribe(media_path, model_size, on_progress=None, on_stage=None, **kwargs):
        if on_stage:
            on_stage("downloading_model")
        return [Segment(id="s1", start=0.0, end=1.0, text="hello")]

    monkeypatch.setattr("app.api.transcribe.whisper_service.transcribe", fake_transcribe)

    client.post(f"/projects/{created['id']}/transcribe", json={"model": "small"})

    project = client.get(f"/projects/{created['id']}").json()
    # stage is cleared once the background task finishes successfully
    assert project["status"] == "transcribed"
    assert project["stage"] is None


def test_transcribe_stopped_via_should_cancel_marks_error_with_cancel_message(client, monkeypatch):
    created = _upload_project(client)

    def fake_transcribe(media_path, model_size, should_cancel=None, **kwargs):
        from app.services import cancellation
        from app.services.whisper_service import TranscriptionCancelled

        # simulates an external POST /cancel arriving while transcribe() is running
        cancellation.request_cancel(created["id"])
        if should_cancel and should_cancel():
            raise TranscriptionCancelled("취소")
        return []

    monkeypatch.setattr("app.api.transcribe.whisper_service.transcribe", fake_transcribe)

    client.post(f"/projects/{created['id']}/transcribe", json={"model": "small"})

    project = client.get(f"/projects/{created['id']}").json()
    assert project["status"] == "error"
    assert "취소" in project["error"]
    assert project["progress"] is None


def test_cancel_endpoint_accepts_busy_project(client, store):
    created = _upload_project(client)
    project = store.get(created["id"])
    project.status = "transcribing"
    store.save(project)

    response = client.post(f"/projects/{created['id']}/cancel")

    assert response.status_code == 200
    from app.services import cancellation

    assert cancellation.is_cancelled(created["id"]) is True
    cancellation.clear_cancel(created["id"])


def test_cancel_endpoint_rejects_non_busy_project(client):
    created = _upload_project(client)

    response = client.post(f"/projects/{created['id']}/cancel")

    assert response.status_code == 400


def test_cancel_endpoint_missing_project_returns_404(client):
    response = client.post("/projects/does-not-exist/cancel")

    assert response.status_code == 404


def test_models_status_reports_uncached_models(client):
    response = client.get("/models/status")

    assert response.status_code == 200
    body = response.json()
    assert set(body["whisper"]) == {
        "tiny",
        "base",
        "small",
        "medium",
        "large",
        "large-v2",
        "large-v3",
    }
    assert set(body["translation"]) == {"ko->en", "en->ko"}
    assert all(isinstance(cached, bool) for cached in body["whisper"].values())
    assert all(isinstance(cached, bool) for cached in body["translation"].values())


def test_translate_requires_existing_segments(client):
    created = _upload_project(client)

    response = client.post(f"/projects/{created['id']}/translate", json={"direction": "ko->en"})

    assert response.status_code == 400


def test_translate_fills_translation_field(client, monkeypatch):
    created = _upload_project(client)
    monkeypatch.setattr(
        "app.api.transcribe.whisper_service.transcribe",
        lambda *a, **k: [Segment(id="s1", start=0.0, end=1.0, text="안녕")],
    )
    client.post(f"/projects/{created['id']}/transcribe", json={"model": "small"})

    class FakeTranslator:
        def translate(self, texts, direction):
            return [f"[{direction}] {t}" for t in texts]

    monkeypatch.setattr(
        "app.api.translate.translation_service.get_translator", lambda *a, **k: FakeTranslator()
    )

    response = client.post(
        f"/projects/{created['id']}/translate", json={"direction": "ko->en", "engine": "local"}
    )
    assert response.status_code == 200

    project = client.get(f"/projects/{created['id']}").json()
    assert project["status"] == "translated"
    assert project["segments"][0]["translation"] == "[ko->en] 안녕"


def test_update_segment_patches_text(client, monkeypatch):
    created = _upload_project(client)
    monkeypatch.setattr(
        "app.api.transcribe.whisper_service.transcribe",
        lambda *a, **k: [Segment(id="s1", start=0.0, end=1.0, text="원문")],
    )
    client.post(f"/projects/{created['id']}/transcribe", json={"model": "small"})

    response = client.patch(
        f"/projects/{created['id']}/segments/s1", json={"text": "수정된 원문"}
    )

    assert response.status_code == 200
    assert response.json()["text"] == "수정된 원문"


def test_update_missing_segment_returns_404(client):
    created = _upload_project(client)

    response = client.patch(f"/projects/{created['id']}/segments/missing", json={"text": "x"})

    assert response.status_code == 404


def test_update_segment_rejects_start_after_end(client, monkeypatch):
    created = _upload_project(client)
    monkeypatch.setattr(
        "app.api.transcribe.whisper_service.transcribe",
        lambda *a, **k: [Segment(id="s1", start=1.0, end=2.0, text="원문")],
    )
    client.post(f"/projects/{created['id']}/transcribe", json={"model": "small"})

    response = client.patch(f"/projects/{created['id']}/segments/s1", json={"start": 5.0})

    assert response.status_code == 400


def test_delete_segment_removes_it_from_project(client, monkeypatch):
    created = _upload_project(client)
    monkeypatch.setattr(
        "app.api.transcribe.whisper_service.transcribe",
        lambda *a, **k: [
            Segment(id="s1", start=0.0, end=1.0, text="keep"),
            Segment(id="s2", start=1.0, end=2.0, text="delete me"),
        ],
    )
    client.post(f"/projects/{created['id']}/transcribe", json={"model": "small"})

    response = client.delete(f"/projects/{created['id']}/segments/s2")
    assert response.status_code == 204

    project = client.get(f"/projects/{created['id']}").json()
    assert [s["id"] for s in project["segments"]] == ["s1"]


def test_delete_missing_segment_returns_404(client):
    created = _upload_project(client)

    response = client.delete(f"/projects/{created['id']}/segments/missing")

    assert response.status_code == 404


def test_export_srt(client, monkeypatch):
    created = _upload_project(client)
    monkeypatch.setattr(
        "app.api.transcribe.whisper_service.transcribe",
        lambda *a, **k: [Segment(id="s1", start=0.0, end=1.5, text="안녕하세요")],
    )
    client.post(f"/projects/{created['id']}/transcribe", json={"model": "small"})

    response = client.get(f"/projects/{created['id']}/export", params={"format": "srt"})

    assert response.status_code == 200
    assert "안녕하세요" in response.text
    assert "00:00:00,000 --> 00:00:01,500" in response.text


def test_review_package_download(client, monkeypatch):
    created = _upload_project(client)
    monkeypatch.setattr(
        "app.api.transcribe.whisper_service.transcribe",
        lambda *a, **k: [Segment(id="s1", start=0.0, end=1.5, text="안녕하세요", translation="Hello")],
    )
    client.post(f"/projects/{created['id']}/transcribe", json={"model": "small"})

    response = client.get(f"/projects/{created['id']}/review-package")

    assert response.status_code == 200
    payload = json.loads(response.text)
    assert payload["project_id"] == created["id"]
    assert payload["segments"][0]["text"] == "안녕하세요"


def test_review_import_returns_diff(client, monkeypatch):
    created = _upload_project(client)
    monkeypatch.setattr(
        "app.api.transcribe.whisper_service.transcribe",
        lambda *a, **k: [Segment(id="s1", start=0.0, end=1.5, text="안녕하세요", translation="Hello")],
    )
    client.post(f"/projects/{created['id']}/transcribe", json={"model": "small"})

    corrected = {
        "segments": [
            {"id": "s1", "start": 0.0, "end": 1.5, "text": "안녕하세요", "translation": "Hi there"}
        ]
    }
    response = client.post(
        f"/projects/{created['id']}/review-import",
        files={"file": ("review.json", json.dumps(corrected), "application/json")},
    )

    assert response.status_code == 200
    diffs = response.json()["diffs"]
    assert len(diffs) == 1
    assert diffs[0]["field"] == "translation"
    assert diffs[0]["new_value"] == "Hi there"
