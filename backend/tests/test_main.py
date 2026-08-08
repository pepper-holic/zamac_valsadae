import pytest

from app.main import recover_interrupted_projects
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


@pytest.mark.parametrize("status", ["uploaded", "transcribed", "translated", "error"])
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
