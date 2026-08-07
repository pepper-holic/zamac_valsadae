import pytest

from app.main import recover_interrupted_projects
from app.services.project_store import ProjectStore


def test_recover_interrupted_projects_marks_stuck_transcribing_as_error(tmp_path):
    store = ProjectStore(root_dir=tmp_path)
    project = store.create(filename="a.wav", media_bytes=b"x")
    project.status = "transcribing"
    project.progress = 0.42
    project.stage = None
    store.save(project)

    recover_interrupted_projects(store)

    recovered = store.get(project.id)
    assert recovered.status == "error"
    assert recovered.progress is None
    assert recovered.stage is None
    assert "재시작" in recovered.error


def test_recover_interrupted_projects_marks_stuck_translating_as_error(tmp_path):
    store = ProjectStore(root_dir=tmp_path)
    project = store.create(filename="a.wav", media_bytes=b"x")
    project.status = "translating"
    store.save(project)

    recover_interrupted_projects(store)

    assert store.get(project.id).status == "error"


@pytest.mark.parametrize("status", ["uploaded", "transcribed", "translated", "error"])
def test_recover_interrupted_projects_leaves_finished_projects_untouched(tmp_path, status):
    store = ProjectStore(root_dir=tmp_path)
    project = store.create(filename="a.wav", media_bytes=b"x")
    project.status = status
    store.save(project)

    recover_interrupted_projects(store)

    assert store.get(project.id).status == status
