from app.models.schemas import Project
from app.services.progress_reporter import make_progress_reporter
from app.services.project_store import ProjectStore


def make_project(tmp_path) -> tuple[Project, ProjectStore]:
    store = ProjectStore(root_dir=tmp_path)
    project = store.create(filename="a.wav", media_bytes=b"x")
    return project, store


def test_reporter_always_saves_on_completion(tmp_path):
    project, store = make_project(tmp_path)
    on_progress = make_progress_reporter(project, store)

    on_progress(1.0)

    assert project.progress == 1.0
    assert store.get(project.id).progress == 1.0


def test_reporter_throttles_rapid_small_updates(tmp_path):
    project, store = make_project(tmp_path)
    on_progress = make_progress_reporter(project, store)

    on_progress(0.001)

    # below the minimum delta and not yet complete: should not persist
    assert store.get(project.id).progress is None
