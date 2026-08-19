import pytest
from fastapi.testclient import TestClient

from app.main import app, recover_interrupted_projects
from app.services.project_store import ProjectStore


def test_recover_interrupted_projects_marks_stuck_transcribing_item_as_error(tmp_path):
    store = ProjectStore(root_dir=tmp_path)
    project = store.create_project()
    store.add_item(project.id, filename="a.wav", media_bytes=b"x")
    project = store.get(project.id)
    project.items[0].status = "transcribing"
    project.items[0].progress = 0.42
    project.items[0].stage = None
    store.save(project)

    recover_interrupted_projects(store)

    recovered = store.get(project.id).items[0]
    assert recovered.status == "error"
    assert recovered.progress is None
    assert recovered.stage is None
    assert "재시작" in recovered.error


def test_recover_interrupted_projects_marks_stuck_translating_item_as_error(tmp_path):
    store = ProjectStore(root_dir=tmp_path)
    project = store.create_project()
    store.add_item(project.id, filename="a.wav", media_bytes=b"x")
    project = store.get(project.id)
    project.items[0].status = "translating"
    store.save(project)

    recover_interrupted_projects(store)

    assert store.get(project.id).items[0].status == "error"


def test_recover_interrupted_projects_marks_stuck_rendering_item_as_error(tmp_path):
    store = ProjectStore(root_dir=tmp_path)
    project = store.create_project()
    store.add_item(project.id, filename="a.wav", media_bytes=b"x")
    project = store.get(project.id)
    project.items[0].status = "rendering"
    store.save(project)

    recover_interrupted_projects(store)

    assert store.get(project.id).items[0].status == "error"


@pytest.mark.parametrize("status", ["uploaded", "transcribed", "translated", "rendered", "error"])
def test_recover_interrupted_projects_leaves_finished_items_untouched(tmp_path, status):
    store = ProjectStore(root_dir=tmp_path)
    project = store.create_project()
    store.add_item(project.id, filename="a.wav", media_bytes=b"x")
    project = store.get(project.id)
    project.items[0].status = status
    store.save(project)

    recover_interrupted_projects(store)

    assert store.get(project.id).items[0].status == status


def test_recover_interrupted_projects_handles_projects_with_multiple_items(tmp_path):
    store = ProjectStore(root_dir=tmp_path)
    project = store.create_project()
    store.add_item(project.id, filename="a.wav", media_bytes=b"x")
    store.add_item(project.id, filename="b.wav", media_bytes=b"y")
    project = store.get(project.id)
    project.items[0].status = "transcribing"
    project.items[1].status = "transcribed"
    store.save(project)

    recover_interrupted_projects(store)

    reloaded = store.get(project.id)
    assert reloaded.items[0].status == "error"
    assert reloaded.items[1].status == "transcribed"


def test_unhandled_exception_returns_structured_500_and_does_not_leak_trace():
    """Anything that isn't an HTTPException (FastAPI's default handlers
    already cover those) used to propagate as a bare, unlogged 500. The
    global handler in app.main should convert it into a stable JSON body
    instead - this test adds a route that deliberately raises, hits it, then
    removes the route again so it doesn't leak into other tests.
    """

    @app.get("/__test_unhandled_error__")
    def _boom():
        raise RuntimeError("boom")

    # The route was appended after the catch-all frontend StaticFiles mount
    # (registered in create_app()) - since Starlette matches routes in
    # registration order, a Mount("/") would swallow this path first if left
    # at the end. Move it to the front so it's tried before that mount.
    route = app.router.routes.pop()
    app.router.routes.insert(0, route)
    try:
        client = TestClient(app, raise_server_exceptions=False)
        response = client.get("/__test_unhandled_error__")

        assert response.status_code == 500
        assert response.json() == {"detail": "서버 오류가 발생했습니다."}
        assert "boom" not in response.text
    finally:
        app.router.routes.remove(route)
