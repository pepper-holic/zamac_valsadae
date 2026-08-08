from app.models.schemas import MediaItem, Project
from app.services.progress_reporter import make_progress_reporter
from app.services.project_store import ProjectStore


def make_project_and_item(tmp_path) -> tuple[Project, MediaItem, ProjectStore]:
    store = ProjectStore(root_dir=tmp_path)
    project = store.create_project()
    item = store.add_item(project.id, filename="a.wav", media_bytes=b"x")
    project = store.get(project.id)
    return project, project.items[0], store


def test_reporter_always_saves_on_completion(tmp_path):
    project, item, store = make_project_and_item(tmp_path)
    on_progress = make_progress_reporter(project, item, store)

    on_progress(1.0)

    assert item.progress == 1.0
    assert store.get(project.id).items[0].progress == 1.0


def test_reporter_throttles_rapid_small_updates(tmp_path):
    project, item, store = make_project_and_item(tmp_path)
    on_progress = make_progress_reporter(project, item, store)

    on_progress(0.001)

    # below the minimum delta and not yet complete: should not persist
    assert store.get(project.id).items[0].progress is None
