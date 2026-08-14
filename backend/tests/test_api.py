import json

import pytest
from fastapi.testclient import TestClient

from app.api.deps import get_store
from app.main import app
from app.models.schemas import Segment
from app.services import render_service
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


@pytest.fixture(autouse=True)
def run_transcription_queue_synchronously(monkeypatch):
    """Transcription now runs on a background queue worker thread (see
    app.services.transcription_queue) instead of finishing before the POST
    /transcribe response, as it used to with FastAPI BackgroundTasks. Most
    tests only care about the resulting item state, so run jobs inline on
    the calling thread here to keep them synchronous. Queue-specific
    ordering behavior is covered separately in test_transcription_queue.py.
    """
    from app.services import transcription_queue

    def _run_inline(job, store):
        transcription_queue._process(job, store)

    # transcribe.py imports `enqueue` by name, so the patch target must be
    # the imported reference in that module, not the defining module.
    monkeypatch.setattr("app.api.transcribe.enqueue", _run_inline)


def _create_project(client) -> dict:
    response = client.post("/projects", json={})
    assert response.status_code == 200
    return response.json()


def _add_item(client, project_id: str, filename: str = "sample.wav") -> dict:
    response = client.post(
        f"/projects/{project_id}/items",
        files={"file": (filename, b"fake-audio-bytes", "audio/wav")},
    )
    assert response.status_code == 200
    return response.json()


def _create_project_with_item(client, filename: str = "sample.wav") -> dict:
    """Convenience helper mirroring the old single-file-per-project flow:
    creates a project and immediately adds one item to it."""
    project = _create_project(client)
    item = _add_item(client, project["id"], filename=filename)
    return {"project_id": project["id"], "item_id": item["id"], "filename": filename}


def test_create_project_starts_empty(client):
    project = _create_project(client)

    assert project["items"] == []


def test_add_item_appends_to_project(client):
    project = _create_project(client)

    item = _add_item(client, project["id"], filename="sample.wav")

    assert item["filename"] == "sample.wav"
    assert item["status"] == "uploaded"
    assert item["segments"] == []

    reloaded = client.get(f"/projects/{project['id']}").json()
    assert [i["id"] for i in reloaded["items"]] == [item["id"]]


def test_add_multiple_items_are_managed_separately(client):
    project = _create_project(client)
    first = _add_item(client, project["id"], filename="a.wav")
    second = _add_item(client, project["id"], filename="b.wav")

    reloaded = client.get(f"/projects/{project['id']}").json()
    assert [i["filename"] for i in reloaded["items"]] == ["a.wav", "b.wav"]
    assert first["id"] != second["id"]


def test_add_item_to_missing_project_returns_404(client):
    response = client.post(
        "/projects/does-not-exist/items",
        files={"file": ("a.wav", b"x", "audio/wav")},
    )

    assert response.status_code == 404


def test_delete_item_removes_it_from_project(client):
    ctx = _create_project_with_item(client)

    response = client.delete(f"/projects/{ctx['project_id']}/items/{ctx['item_id']}")

    assert response.status_code == 204
    reloaded = client.get(f"/projects/{ctx['project_id']}").json()
    assert reloaded["items"] == []


def test_delete_missing_item_returns_404(client):
    project = _create_project(client)

    response = client.delete(f"/projects/{project['id']}/items/missing")

    assert response.status_code == 404


def test_delete_project_removes_it_from_list(client):
    project = _create_project(client)

    response = client.delete(f"/projects/{project['id']}")
    assert response.status_code == 204

    assert client.get(f"/projects/{project['id']}").status_code == 404
    assert project["id"] not in [p["id"] for p in client.get("/projects").json()]


def test_delete_missing_project_returns_404(client):
    response = client.delete("/projects/does-not-exist")

    assert response.status_code == 404


def test_get_project_returns_created_project(client):
    project = _create_project(client)

    response = client.get(f"/projects/{project['id']}")

    assert response.status_code == 200
    assert response.json()["id"] == project["id"]


def test_get_missing_project_returns_404(client):
    response = client.get("/projects/does-not-exist")

    assert response.status_code == 404


def test_update_glossary_persists_terms(client):
    project = _create_project(client)

    response = client.put(
        f"/projects/{project['id']}/glossary", json={"glossary": {"Zamak": "Zamak Corp"}}
    )

    assert response.status_code == 200
    assert response.json()["glossary"] == {"Zamak": "Zamak Corp"}
    reloaded = client.get(f"/projects/{project['id']}").json()
    assert reloaded["glossary"] == {"Zamak": "Zamak Corp"}


def test_project_starts_with_default_subtitle_style(client):
    project = _create_project(client)

    assert project["subtitle_style"]["font_family"] == "Pretendard"
    assert project["subtitle_style"]["position"] == "bottom"
    assert project["style_presets"] == []


def test_update_style_persists_changes(client):
    project = _create_project(client)

    response = client.put(
        f"/projects/{project['id']}/style",
        json={"font_size": 48, "color": "#00FF00", "position": "top"},
    )

    assert response.status_code == 200
    assert response.json()["subtitle_style"]["font_size"] == 48
    assert response.json()["subtitle_style"]["color"] == "#00FF00"
    reloaded = client.get(f"/projects/{project['id']}").json()
    assert reloaded["subtitle_style"]["position"] == "top"


def test_update_style_missing_project_returns_404(client):
    response = client.put("/projects/does-not-exist/style", json={})

    assert response.status_code == 404


def test_create_style_preset_appends_to_list(client):
    project = _create_project(client)

    response = client.post(
        f"/projects/{project['id']}/style/presets",
        json={"name": "노란자막", "style": {"color": "#FFFF00"}},
    )

    assert response.status_code == 200
    presets = response.json()["style_presets"]
    assert len(presets) == 1
    assert presets[0]["name"] == "노란자막"
    assert presets[0]["style"]["color"] == "#FFFF00"


def test_create_style_preset_with_same_name_replaces_it(client):
    project = _create_project(client)
    client.post(
        f"/projects/{project['id']}/style/presets",
        json={"name": "노란자막", "style": {"color": "#FFFF00"}},
    )

    response = client.post(
        f"/projects/{project['id']}/style/presets",
        json={"name": "노란자막", "style": {"color": "#EEEE00"}},
    )

    presets = response.json()["style_presets"]
    assert len(presets) == 1
    assert presets[0]["style"]["color"] == "#EEEE00"


def test_delete_style_preset_removes_it(client):
    project = _create_project(client)
    client.post(
        f"/projects/{project['id']}/style/presets",
        json={"name": "노란자막", "style": {"color": "#FFFF00"}},
    )

    response = client.delete(f"/projects/{project['id']}/style/presets/노란자막")

    assert response.status_code == 200
    assert response.json()["style_presets"] == []


def test_delete_missing_style_preset_returns_404(client):
    project = _create_project(client)

    response = client.delete(f"/projects/{project['id']}/style/presets/없음")

    assert response.status_code == 404


def test_transcribe_runs_background_task_and_updates_segments(client, monkeypatch):
    ctx = _create_project_with_item(client)

    fake_segments = [Segment(id="s1", start=0.0, end=1.0, text="hello")]
    monkeypatch.setattr(
        "app.services.transcription_queue.whisper_service.transcribe", lambda *a, **k: fake_segments
    )

    response = client.post(
        f"/projects/{ctx['project_id']}/items/{ctx['item_id']}/transcribe",
        json={"model": "small"},
    )
    assert response.status_code == 200

    project = client.get(f"/projects/{ctx['project_id']}").json()
    item = project["items"][0]
    assert item["status"] == "transcribed"
    assert item["segments"][0]["text"] == "hello"


def test_transcribe_reports_final_progress_and_calls_on_progress(client, monkeypatch):
    ctx = _create_project_with_item(client)

    fake_segments = [Segment(id="s1", start=0.0, end=1.0, text="hello")]

    def fake_transcribe(media_path, model_size, on_progress=None, **kwargs):
        if on_progress:
            on_progress(0.5)
            on_progress(1.0)
        return fake_segments

    monkeypatch.setattr("app.services.transcription_queue.whisper_service.transcribe", fake_transcribe)

    client.post(
        f"/projects/{ctx['project_id']}/items/{ctx['item_id']}/transcribe",
        json={"model": "small"},
    )

    item = client.get(f"/projects/{ctx['project_id']}").json()["items"][0]
    assert item["status"] == "transcribed"
    assert item["progress"] == 1.0


def test_transcribe_rejects_unknown_model(client):
    ctx = _create_project_with_item(client)

    response = client.post(
        f"/projects/{ctx['project_id']}/items/{ctx['item_id']}/transcribe",
        json={"model": "huge"},
    )

    assert response.status_code == 400


def test_transcribe_marks_error_status_on_failure(client, monkeypatch):
    ctx = _create_project_with_item(client)

    def _boom(*a, **k):
        raise RuntimeError("model exploded")

    monkeypatch.setattr("app.services.transcription_queue.whisper_service.transcribe", _boom)

    client.post(
        f"/projects/{ctx['project_id']}/items/{ctx['item_id']}/transcribe",
        json={"model": "small"},
    )

    item = client.get(f"/projects/{ctx['project_id']}").json()["items"][0]
    assert item["status"] == "error"
    assert "model exploded" in item["error"]


def test_transcribe_reports_downloading_model_stage(client, monkeypatch):
    ctx = _create_project_with_item(client)

    def fake_transcribe(media_path, model_size, on_progress=None, on_stage=None, **kwargs):
        if on_stage:
            on_stage("downloading_model")
        return [Segment(id="s1", start=0.0, end=1.0, text="hello")]

    monkeypatch.setattr("app.services.transcription_queue.whisper_service.transcribe", fake_transcribe)

    client.post(
        f"/projects/{ctx['project_id']}/items/{ctx['item_id']}/transcribe",
        json={"model": "small"},
    )

    item = client.get(f"/projects/{ctx['project_id']}").json()["items"][0]
    # stage is cleared once the background task finishes successfully
    assert item["status"] == "transcribed"
    assert item["stage"] is None


def test_transcribe_stopped_via_should_cancel_marks_error_with_cancel_message(client, monkeypatch):
    ctx = _create_project_with_item(client)

    def fake_transcribe(media_path, model_size, should_cancel=None, **kwargs):
        from app.services import cancellation
        from app.services.whisper_service import TranscriptionCancelled

        # simulates an external POST /cancel arriving while transcribe() is running
        cancellation.request_cancel(ctx["item_id"])
        if should_cancel and should_cancel():
            raise TranscriptionCancelled("취소")
        return []

    monkeypatch.setattr("app.services.transcription_queue.whisper_service.transcribe", fake_transcribe)

    client.post(
        f"/projects/{ctx['project_id']}/items/{ctx['item_id']}/transcribe",
        json={"model": "small"},
    )

    item = client.get(f"/projects/{ctx['project_id']}").json()["items"][0]
    assert item["status"] == "error"
    assert "취소" in item["error"]
    assert item["progress"] is None


def test_cancel_endpoint_accepts_busy_item(client, store):
    ctx = _create_project_with_item(client)
    project = store.get(ctx["project_id"])
    project.items[0].status = "transcribing"
    store.save(project)

    response = client.post(f"/projects/{ctx['project_id']}/items/{ctx['item_id']}/cancel")

    assert response.status_code == 200
    from app.services import cancellation

    assert cancellation.is_cancelled(ctx["item_id"]) is True
    cancellation.clear_cancel(ctx["item_id"])


def test_cancel_endpoint_rejects_non_busy_item(client):
    ctx = _create_project_with_item(client)

    response = client.post(f"/projects/{ctx['project_id']}/items/{ctx['item_id']}/cancel")

    assert response.status_code == 400


def test_cancel_endpoint_missing_project_returns_404(client):
    response = client.post("/projects/does-not-exist/items/missing/cancel")

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
        "large-v3-turbo",
    }
    assert set(body["translation"]) == {"ko->en", "en->ko"}
    assert all(isinstance(cached, bool) for cached in body["whisper"].values())
    assert body["whisper_device"] in ("cuda", "cpu")
    assert all(isinstance(cached, bool) for cached in body["translation"].values())


def test_translate_requires_existing_segments(client):
    ctx = _create_project_with_item(client)

    response = client.post(
        f"/projects/{ctx['project_id']}/items/{ctx['item_id']}/translate",
        json={"direction": "ko->en"},
    )

    assert response.status_code == 400


def test_translate_fills_translation_field(client, monkeypatch):
    ctx = _create_project_with_item(client)
    monkeypatch.setattr(
        "app.services.transcription_queue.whisper_service.transcribe",
        lambda *a, **k: [Segment(id="s1", start=0.0, end=1.0, text="안녕")],
    )
    client.post(
        f"/projects/{ctx['project_id']}/items/{ctx['item_id']}/transcribe",
        json={"model": "small"},
    )

    class FakeTranslator:
        def translate(self, texts, direction):
            return [f"[{direction}] {t}" for t in texts]

    monkeypatch.setattr(
        "app.api.translate.translation_service.get_translator", lambda *a, **k: FakeTranslator()
    )

    response = client.post(
        f"/projects/{ctx['project_id']}/items/{ctx['item_id']}/translate",
        json={"direction": "ko->en", "engine": "local"},
    )
    assert response.status_code == 200

    item = client.get(f"/projects/{ctx['project_id']}").json()["items"][0]
    assert item["status"] == "translated"
    assert item["segments"][0]["translation"] == "[ko->en] 안녕"


def test_translate_passes_logged_in_session_token_to_get_translator(client, monkeypatch):
    from app.services import auth_state

    ctx = _create_project_with_item(client)
    monkeypatch.setattr(
        "app.services.transcription_queue.whisper_service.transcribe",
        lambda *a, **k: [Segment(id="s1", start=0.0, end=1.0, text="안녕")],
    )
    client.post(
        f"/projects/{ctx['project_id']}/items/{ctx['item_id']}/transcribe",
        json={"model": "small"},
    )

    class FakeTranslator:
        def translate(self, texts, direction):
            return [f"[{direction}] {t}" for t in texts]

    captured = {}

    def fake_get_translator(*args, **kwargs):
        captured["session_token"] = kwargs.get("session_token")
        return FakeTranslator()

    monkeypatch.setattr("app.api.translate.translation_service.get_translator", fake_get_translator)

    auth_state.set_session(access_token="user-jwt", email="a@b.com")
    try:
        response = client.post(
            f"/projects/{ctx['project_id']}/items/{ctx['item_id']}/translate",
            json={"direction": "ko->en", "engine": "api"},
        )
    finally:
        auth_state.clear_session()

    assert response.status_code == 200
    assert captured["session_token"] == "user-jwt"


def _segments_url(ctx: dict, suffix: str = "") -> str:
    return f"/projects/{ctx['project_id']}/items/{ctx['item_id']}/segments{suffix}"


def test_update_segment_patches_text(client, monkeypatch):
    ctx = _create_project_with_item(client)
    monkeypatch.setattr(
        "app.services.transcription_queue.whisper_service.transcribe",
        lambda *a, **k: [Segment(id="s1", start=0.0, end=1.0, text="원문")],
    )
    client.post(
        f"/projects/{ctx['project_id']}/items/{ctx['item_id']}/transcribe",
        json={"model": "small"},
    )

    response = client.patch(_segments_url(ctx, "/s1"), json={"text": "수정된 원문"})

    assert response.status_code == 200
    assert response.json()["text"] == "수정된 원문"


def test_update_segment_clears_words_when_text_changes(client, monkeypatch):
    ctx = _create_project_with_item(client)
    monkeypatch.setattr(
        "app.services.transcription_queue.whisper_service.transcribe",
        lambda *a, **k: [
            Segment(
                id="s1",
                start=0.0,
                end=1.0,
                text="원문",
                words=[{"text": "원문", "start": 0.0, "end": 1.0}],
            )
        ],
    )
    client.post(
        f"/projects/{ctx['project_id']}/items/{ctx['item_id']}/transcribe",
        json={"model": "small"},
    )

    response = client.patch(_segments_url(ctx, "/s1"), json={"text": "수정된 원문"})

    assert response.status_code == 200
    assert response.json()["words"] == []


def test_update_segment_keeps_words_when_text_unchanged(client, monkeypatch):
    ctx = _create_project_with_item(client)
    monkeypatch.setattr(
        "app.services.transcription_queue.whisper_service.transcribe",
        lambda *a, **k: [
            Segment(
                id="s1",
                start=0.0,
                end=1.0,
                text="원문",
                words=[{"text": "원문", "start": 0.0, "end": 1.0}],
            )
        ],
    )
    client.post(
        f"/projects/{ctx['project_id']}/items/{ctx['item_id']}/transcribe",
        json={"model": "small"},
    )

    response = client.patch(_segments_url(ctx, "/s1"), json={"reviewed": True})

    assert response.status_code == 200
    assert response.json()["words"] == [{"text": "원문", "start": 0.0, "end": 1.0}]


def test_update_missing_segment_returns_404(client):
    ctx = _create_project_with_item(client)

    response = client.patch(_segments_url(ctx, "/missing"), json={"text": "x"})

    assert response.status_code == 404


def test_update_segment_rejects_start_after_end(client, monkeypatch):
    ctx = _create_project_with_item(client)
    monkeypatch.setattr(
        "app.services.transcription_queue.whisper_service.transcribe",
        lambda *a, **k: [Segment(id="s1", start=1.0, end=2.0, text="원문")],
    )
    client.post(
        f"/projects/{ctx['project_id']}/items/{ctx['item_id']}/transcribe",
        json={"model": "small"},
    )

    response = client.patch(_segments_url(ctx, "/s1"), json={"start": 5.0})

    assert response.status_code == 400


def test_delete_segment_removes_it_from_item(client, monkeypatch):
    ctx = _create_project_with_item(client)
    monkeypatch.setattr(
        "app.services.transcription_queue.whisper_service.transcribe",
        lambda *a, **k: [
            Segment(id="s1", start=0.0, end=1.0, text="keep"),
            Segment(id="s2", start=1.0, end=2.0, text="delete me"),
        ],
    )
    client.post(
        f"/projects/{ctx['project_id']}/items/{ctx['item_id']}/transcribe",
        json={"model": "small"},
    )

    response = client.delete(_segments_url(ctx, "/s2"))
    assert response.status_code == 204

    item = client.get(f"/projects/{ctx['project_id']}").json()["items"][0]
    assert [s["id"] for s in item["segments"]] == ["s1"]


def test_delete_missing_segment_returns_404(client):
    ctx = _create_project_with_item(client)

    response = client.delete(_segments_url(ctx, "/missing"))

    assert response.status_code == 404


def test_split_segment_replaces_it_with_two_segments(client, monkeypatch):
    ctx = _create_project_with_item(client)
    monkeypatch.setattr(
        "app.services.transcription_queue.whisper_service.transcribe",
        lambda *a, **k: [Segment(id="s1", start=0.0, end=10.0, text="one two three four")],
    )
    client.post(
        f"/projects/{ctx['project_id']}/items/{ctx['item_id']}/transcribe",
        json={"model": "small"},
    )

    response = client.post(_segments_url(ctx, "/s1/split"), json={"split_at": 5.0})

    assert response.status_code == 200
    pair = response.json()
    assert len(pair) == 2
    assert pair[0]["end"] == pair[1]["start"] == 5.0

    item = client.get(f"/projects/{ctx['project_id']}").json()["items"][0]
    assert len(item["segments"]) == 2
    assert "s1" not in [s["id"] for s in item["segments"]]


def test_split_segment_missing_returns_404(client):
    ctx = _create_project_with_item(client)

    response = client.post(_segments_url(ctx, "/missing/split"), json={"split_at": 1.0})

    assert response.status_code == 404


def test_split_segment_invalid_point_returns_400(client, monkeypatch):
    ctx = _create_project_with_item(client)
    monkeypatch.setattr(
        "app.services.transcription_queue.whisper_service.transcribe",
        lambda *a, **k: [Segment(id="s1", start=0.0, end=10.0, text="one two")],
    )
    client.post(
        f"/projects/{ctx['project_id']}/items/{ctx['item_id']}/transcribe",
        json={"model": "small"},
    )

    response = client.post(_segments_url(ctx, "/s1/split"), json={"split_at": 20.0})

    assert response.status_code == 400


def test_merge_segments_combines_them_into_one(client, monkeypatch):
    ctx = _create_project_with_item(client)
    monkeypatch.setattr(
        "app.services.transcription_queue.whisper_service.transcribe",
        lambda *a, **k: [
            Segment(id="s1", start=0.0, end=1.0, text="hello"),
            Segment(id="s2", start=1.0, end=2.0, text="world"),
        ],
    )
    client.post(
        f"/projects/{ctx['project_id']}/items/{ctx['item_id']}/transcribe",
        json={"model": "small"},
    )

    response = client.post(_segments_url(ctx, "/merge"), json={"segment_ids": ["s1", "s2"]})

    assert response.status_code == 200
    merged = response.json()
    assert merged["text"] == "hello world"
    assert merged["start"] == 0.0
    assert merged["end"] == 2.0

    item = client.get(f"/projects/{ctx['project_id']}").json()["items"][0]
    assert len(item["segments"]) == 1


def test_merge_segments_missing_id_returns_404(client, monkeypatch):
    ctx = _create_project_with_item(client)
    monkeypatch.setattr(
        "app.services.transcription_queue.whisper_service.transcribe",
        lambda *a, **k: [Segment(id="s1", start=0.0, end=1.0, text="hello")],
    )
    client.post(
        f"/projects/{ctx['project_id']}/items/{ctx['item_id']}/transcribe",
        json={"model": "small"},
    )

    response = client.post(
        _segments_url(ctx, "/merge"), json={"segment_ids": ["s1", "missing"]}
    )

    assert response.status_code == 404


def test_find_replace_updates_matching_segments(client, monkeypatch):
    ctx = _create_project_with_item(client)
    monkeypatch.setattr(
        "app.services.transcription_queue.whisper_service.transcribe",
        lambda *a, **k: [
            Segment(id="s1", start=0.0, end=1.0, text="hello world"),
            Segment(id="s2", start=1.0, end=2.0, text="goodbye"),
        ],
    )
    client.post(
        f"/projects/{ctx['project_id']}/items/{ctx['item_id']}/transcribe",
        json={"model": "small"},
    )

    response = client.post(
        _segments_url(ctx, "/find-replace"),
        json={"field": "text", "find": "world", "replace": "earth"},
    )

    assert response.status_code == 200
    texts = [s["text"] for s in response.json()]
    assert texts == ["hello earth", "goodbye"]


def test_detect_fillers_returns_filler_segment_ids_without_deleting(client, monkeypatch):
    ctx = _create_project_with_item(client)
    monkeypatch.setattr(
        "app.services.transcription_queue.whisper_service.transcribe",
        lambda *a, **k: [
            Segment(id="s1", start=0.0, end=1.0, text="음"),
            Segment(id="s2", start=1.0, end=2.0, text="안녕하세요"),
        ],
    )
    client.post(
        f"/projects/{ctx['project_id']}/items/{ctx['item_id']}/transcribe",
        json={"model": "small"},
    )

    response = client.post(_segments_url(ctx, "/detect-fillers"), json={"language": "ko"})

    assert response.status_code == 200
    assert response.json() == ["s1"]

    item = client.get(f"/projects/{ctx['project_id']}").json()["items"][0]
    assert len(item["segments"]) == 2


def test_detect_fillers_missing_item_returns_404(client):
    ctx = _create_project_with_item(client)

    response = client.post(
        f"/projects/{ctx['project_id']}/items/does-not-exist/segments/detect-fillers",
        json={"language": "ko"},
    )

    assert response.status_code == 404


def test_bulk_update_applies_all_entries_in_one_request(client, monkeypatch):
    ctx = _create_project_with_item(client)
    monkeypatch.setattr(
        "app.services.transcription_queue.whisper_service.transcribe",
        lambda *a, **k: [
            Segment(id="s1", start=0.0, end=1.0, text="one"),
            Segment(id="s2", start=1.0, end=2.0, text="two"),
            Segment(id="s3", start=2.0, end=3.0, text="three"),
        ],
    )
    client.post(
        f"/projects/{ctx['project_id']}/items/{ctx['item_id']}/transcribe",
        json={"model": "small"},
    )

    response = client.post(
        _segments_url(ctx, "/bulk-update"),
        json={"updates": [{"id": "s1", "update": {"reviewed": True}}, {"id": "s2", "update": {"reviewed": True}}]},
    )

    assert response.status_code == 200
    updated = response.json()
    assert {s["id"] for s in updated} == {"s1", "s2"}
    assert all(s["reviewed"] for s in updated)

    item = client.get(f"/projects/{ctx['project_id']}").json()["items"][0]
    by_id = {s["id"]: s for s in item["segments"]}
    assert by_id["s1"]["reviewed"] is True
    assert by_id["s2"]["reviewed"] is True
    assert by_id["s3"]["reviewed"] is False


def test_bulk_update_missing_id_returns_404_and_changes_nothing(client, monkeypatch):
    ctx = _create_project_with_item(client)
    monkeypatch.setattr(
        "app.services.transcription_queue.whisper_service.transcribe",
        lambda *a, **k: [Segment(id="s1", start=0.0, end=1.0, text="one")],
    )
    client.post(
        f"/projects/{ctx['project_id']}/items/{ctx['item_id']}/transcribe",
        json={"model": "small"},
    )

    response = client.post(
        _segments_url(ctx, "/bulk-update"),
        json={"updates": [{"id": "missing", "update": {"reviewed": True}}]},
    )

    assert response.status_code == 404
    item = client.get(f"/projects/{ctx['project_id']}").json()["items"][0]
    assert item["segments"][0]["reviewed"] is False


def test_bulk_delete_removes_all_given_ids_in_one_request(client, monkeypatch):
    ctx = _create_project_with_item(client)
    monkeypatch.setattr(
        "app.services.transcription_queue.whisper_service.transcribe",
        lambda *a, **k: [
            Segment(id="s1", start=0.0, end=1.0, text="one"),
            Segment(id="s2", start=1.0, end=2.0, text="two"),
            Segment(id="s3", start=2.0, end=3.0, text="three"),
        ],
    )
    client.post(
        f"/projects/{ctx['project_id']}/items/{ctx['item_id']}/transcribe",
        json={"model": "small"},
    )

    response = client.post(_segments_url(ctx, "/bulk-delete"), json={"segment_ids": ["s1", "s3"]})

    assert response.status_code == 200
    assert [s["id"] for s in response.json()] == ["s2"]

    item = client.get(f"/projects/{ctx['project_id']}").json()["items"][0]
    assert [s["id"] for s in item["segments"]] == ["s2"]


def test_undo_fully_reverts_a_bulk_delete_in_a_single_step(client, monkeypatch):
    ctx = _create_project_with_item(client)
    monkeypatch.setattr(
        "app.services.transcription_queue.whisper_service.transcribe",
        lambda *a, **k: [
            Segment(id="s1", start=0.0, end=1.0, text="one"),
            Segment(id="s2", start=1.0, end=2.0, text="two"),
            Segment(id="s3", start=2.0, end=3.0, text="three"),
        ],
    )
    client.post(
        f"/projects/{ctx['project_id']}/items/{ctx['item_id']}/transcribe",
        json={"model": "small"},
    )
    client.post(_segments_url(ctx, "/bulk-delete"), json={"segment_ids": ["s1", "s2", "s3"]})

    response = client.post(f"/projects/{ctx['project_id']}/items/{ctx['item_id']}/undo")

    assert response.status_code == 200
    body = response.json()
    assert [s["id"] for s in body["segments"]] == ["s1", "s2", "s3"]
    # a bulk op is one history entry, so one undo is enough regardless of how
    # many segments it touched - it must not still have a partial undo left
    assert body["can_undo"] is False


def test_undo_restores_segment_text_before_last_update(client, monkeypatch):
    ctx = _create_project_with_item(client)
    monkeypatch.setattr(
        "app.services.transcription_queue.whisper_service.transcribe",
        lambda *a, **k: [Segment(id="s1", start=0.0, end=1.0, text="원문")],
    )
    client.post(
        f"/projects/{ctx['project_id']}/items/{ctx['item_id']}/transcribe",
        json={"model": "small"},
    )
    client.patch(_segments_url(ctx, "/s1"), json={"text": "수정된 원문"})

    response = client.post(f"/projects/{ctx['project_id']}/items/{ctx['item_id']}/undo")

    assert response.status_code == 200
    body = response.json()
    assert body["segments"][0]["text"] == "원문"
    assert body["can_redo"] is True

    item = client.get(f"/projects/{ctx['project_id']}").json()["items"][0]
    assert item["segments"][0]["text"] == "원문"


def test_redo_reapplies_undone_change(client, monkeypatch):
    ctx = _create_project_with_item(client)
    monkeypatch.setattr(
        "app.services.transcription_queue.whisper_service.transcribe",
        lambda *a, **k: [Segment(id="s1", start=0.0, end=1.0, text="원문")],
    )
    client.post(
        f"/projects/{ctx['project_id']}/items/{ctx['item_id']}/transcribe",
        json={"model": "small"},
    )
    client.patch(_segments_url(ctx, "/s1"), json={"text": "수정된 원문"})
    client.post(f"/projects/{ctx['project_id']}/items/{ctx['item_id']}/undo")

    response = client.post(f"/projects/{ctx['project_id']}/items/{ctx['item_id']}/redo")

    assert response.status_code == 200
    body = response.json()
    assert body["segments"][0]["text"] == "수정된 원문"
    assert body["can_redo"] is False


def test_undo_without_history_returns_400(client):
    ctx = _create_project_with_item(client)

    response = client.post(f"/projects/{ctx['project_id']}/items/{ctx['item_id']}/undo")

    assert response.status_code == 400


def test_redo_without_history_returns_400(client):
    ctx = _create_project_with_item(client)

    response = client.post(f"/projects/{ctx['project_id']}/items/{ctx['item_id']}/redo")

    assert response.status_code == 400


def test_new_edit_after_undo_clears_redo_stack(client, monkeypatch):
    ctx = _create_project_with_item(client)
    monkeypatch.setattr(
        "app.services.transcription_queue.whisper_service.transcribe",
        lambda *a, **k: [Segment(id="s1", start=0.0, end=1.0, text="원문")],
    )
    client.post(
        f"/projects/{ctx['project_id']}/items/{ctx['item_id']}/transcribe",
        json={"model": "small"},
    )
    client.patch(_segments_url(ctx, "/s1"), json={"text": "v2"})
    client.post(f"/projects/{ctx['project_id']}/items/{ctx['item_id']}/undo")
    client.patch(_segments_url(ctx, "/s1"), json={"text": "v3"})

    response = client.post(f"/projects/{ctx['project_id']}/items/{ctx['item_id']}/redo")

    assert response.status_code == 400


def _transcribe_one_segment(client, ctx, monkeypatch, text: str = "안녕하세요") -> None:
    monkeypatch.setattr(
        "app.services.transcription_queue.whisper_service.transcribe",
        lambda *a, **k: [Segment(id="s1", start=0.0, end=1.5, text=text)],
    )
    client.post(
        f"/projects/{ctx['project_id']}/items/{ctx['item_id']}/transcribe",
        json={"model": "small"},
    )


def test_render_starts_and_marks_item_rendered(client, monkeypatch):
    ctx = _create_project_with_item(client)
    _transcribe_one_segment(client, ctx, monkeypatch)

    monkeypatch.setattr(
        "app.api.export.render_service.probe_duration_seconds", lambda *a, **k: 1.5
    )

    def fake_render(**kwargs):
        kwargs["on_progress"](1.0)

    monkeypatch.setattr("app.api.export.render_service.render", fake_render)

    response = client.post(
        f"/projects/{ctx['project_id']}/items/{ctx['item_id']}/render", json={}
    )

    assert response.status_code == 200
    item = client.get(f"/projects/{ctx['project_id']}").json()["items"][0]
    assert item["status"] == "rendered"
    assert item["rendered_path"] is not None
    assert item["progress"] == 1.0


def test_render_with_cut_deleted_passes_cut_list_and_uses_kept_duration(client, monkeypatch):
    ctx = _create_project_with_item(client)
    monkeypatch.setattr(
        "app.services.transcription_queue.whisper_service.transcribe",
        lambda *a, **k: [
            Segment(id="s1", start=0.0, end=1.0, text="one"),
            Segment(id="s2", start=3.0, end=5.0, text="two"),
        ],
    )
    client.post(
        f"/projects/{ctx['project_id']}/items/{ctx['item_id']}/transcribe",
        json={"model": "small"},
    )
    monkeypatch.setattr(
        "app.api.export.render_service.probe_duration_seconds", lambda *a, **k: 10.0
    )

    captured = {}

    def fake_render(**kwargs):
        captured.update(kwargs)
        kwargs["on_progress"](1.0)

    monkeypatch.setattr("app.api.export.render_service.render", fake_render)

    response = client.post(
        f"/projects/{ctx['project_id']}/items/{ctx['item_id']}/render",
        json={"cut_deleted": True},
    )

    assert response.status_code == 200
    assert captured["cut_list"] == [(0.0, 1.0), (3.0, 5.0)]
    assert captured["duration_seconds"] == pytest.approx(3.0)


def test_render_without_cut_deleted_uses_full_duration_and_no_cut_list(client, monkeypatch):
    ctx = _create_project_with_item(client)
    monkeypatch.setattr(
        "app.services.transcription_queue.whisper_service.transcribe",
        lambda *a, **k: [
            Segment(id="s1", start=0.0, end=1.0, text="one"),
            Segment(id="s2", start=3.0, end=5.0, text="two"),
        ],
    )
    client.post(
        f"/projects/{ctx['project_id']}/items/{ctx['item_id']}/transcribe",
        json={"model": "small"},
    )
    monkeypatch.setattr(
        "app.api.export.render_service.probe_duration_seconds", lambda *a, **k: 10.0
    )

    captured = {}

    def fake_render(**kwargs):
        captured.update(kwargs)
        kwargs["on_progress"](1.0)

    monkeypatch.setattr("app.api.export.render_service.render", fake_render)

    response = client.post(
        f"/projects/{ctx['project_id']}/items/{ctx['item_id']}/render", json={}
    )

    assert response.status_code == 200
    assert captured["cut_list"] is None
    assert captured["duration_seconds"] == pytest.approx(10.0)


def test_render_without_segments_returns_400(client):
    ctx = _create_project_with_item(client)

    response = client.post(
        f"/projects/{ctx['project_id']}/items/{ctx['item_id']}/render", json={}
    )

    assert response.status_code == 400


def test_render_marks_item_error_on_ffmpeg_failure(client, monkeypatch):
    ctx = _create_project_with_item(client)
    _transcribe_one_segment(client, ctx, monkeypatch)

    monkeypatch.setattr(
        "app.api.export.render_service.probe_duration_seconds", lambda *a, **k: 1.5
    )

    def fake_render(**kwargs):
        raise render_service.RenderError("ffmpeg exploded")

    monkeypatch.setattr("app.api.export.render_service.render", fake_render)

    client.post(f"/projects/{ctx['project_id']}/items/{ctx['item_id']}/render", json={})

    item = client.get(f"/projects/{ctx['project_id']}").json()["items"][0]
    assert item["status"] == "error"
    assert "ffmpeg exploded" in item["error"]


def test_render_cancelled_marks_item_error(client, monkeypatch):
    ctx = _create_project_with_item(client)
    _transcribe_one_segment(client, ctx, monkeypatch)

    monkeypatch.setattr(
        "app.api.export.render_service.probe_duration_seconds", lambda *a, **k: 1.5
    )

    def fake_render(**kwargs):
        raise render_service.RenderCancelled("취소됨")

    monkeypatch.setattr("app.api.export.render_service.render", fake_render)

    client.post(f"/projects/{ctx['project_id']}/items/{ctx['item_id']}/render", json={})

    item = client.get(f"/projects/{ctx['project_id']}").json()["items"][0]
    assert item["status"] == "error"
    assert "취소" in item["error"]


def test_download_rendered_video_missing_returns_404(client):
    ctx = _create_project_with_item(client)

    response = client.get(f"/projects/{ctx['project_id']}/items/{ctx['item_id']}/rendered")

    assert response.status_code == 404


def test_export_srt(client, monkeypatch):
    ctx = _create_project_with_item(client)
    monkeypatch.setattr(
        "app.services.transcription_queue.whisper_service.transcribe",
        lambda *a, **k: [Segment(id="s1", start=0.0, end=1.5, text="안녕하세요")],
    )
    client.post(
        f"/projects/{ctx['project_id']}/items/{ctx['item_id']}/transcribe",
        json={"model": "small"},
    )

    response = client.get(
        f"/projects/{ctx['project_id']}/items/{ctx['item_id']}/export", params={"format": "srt"}
    )

    assert response.status_code == 200
    assert "안녕하세요" in response.text
    assert "00:00:00,000 --> 00:00:01,500" in response.text


def test_review_package_download(client, monkeypatch):
    ctx = _create_project_with_item(client)
    monkeypatch.setattr(
        "app.services.transcription_queue.whisper_service.transcribe",
        lambda *a, **k: [Segment(id="s1", start=0.0, end=1.5, text="안녕하세요", translation="Hello")],
    )
    client.post(
        f"/projects/{ctx['project_id']}/items/{ctx['item_id']}/transcribe",
        json={"model": "small"},
    )

    response = client.get(f"/projects/{ctx['project_id']}/items/{ctx['item_id']}/review-package")

    assert response.status_code == 200
    payload = json.loads(response.text)
    assert payload["item_id"] == ctx["item_id"]
    assert payload["segments"][0]["text"] == "안녕하세요"


def test_review_import_returns_diff(client, monkeypatch):
    ctx = _create_project_with_item(client)
    monkeypatch.setattr(
        "app.services.transcription_queue.whisper_service.transcribe",
        lambda *a, **k: [Segment(id="s1", start=0.0, end=1.5, text="안녕하세요", translation="Hello")],
    )
    client.post(
        f"/projects/{ctx['project_id']}/items/{ctx['item_id']}/transcribe",
        json={"model": "small"},
    )

    corrected = {
        "segments": [
            {"id": "s1", "start": 0.0, "end": 1.5, "text": "안녕하세요", "translation": "Hi there"}
        ]
    }
    response = client.post(
        f"/projects/{ctx['project_id']}/items/{ctx['item_id']}/review-import",
        files={"file": ("review.json", json.dumps(corrected), "application/json")},
    )

    assert response.status_code == 200
    diffs = response.json()["diffs"]
    assert len(diffs) == 1
    assert diffs[0]["field"] == "translation"
    assert diffs[0]["new_value"] == "Hi there"
