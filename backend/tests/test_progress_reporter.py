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
    on_progress = make_progress_reporter(project.id, item.id, store)

    on_progress(1.0)

    assert store.get(project.id).items[0].progress == 1.0


def test_reporter_throttles_rapid_small_updates(tmp_path):
    project, item, store = make_project_and_item(tmp_path)
    on_progress = make_progress_reporter(project.id, item.id, store)

    on_progress(0.001)

    # below the minimum delta and not yet complete: should not persist
    assert store.get(project.id).items[0].progress is None


def test_reporter_does_not_clobber_a_concurrent_edit_to_a_sibling_item(tmp_path):
    store = ProjectStore(root_dir=tmp_path)
    project = store.create_project()
    rendering_item = store.add_item(project.id, filename="a.wav", media_bytes=b"x")
    sibling_item = store.add_item(project.id, filename="b.wav", media_bytes=b"x")
    on_progress = make_progress_reporter(project.id, rendering_item.id, store)

    # Simulate an edit made to a sibling item while the render is in flight -
    # e.g. a segment edit routed through store.update() elsewhere.
    store.update_item(project.id, sibling_item.id, lambda item: setattr(item, "progress", 0.42))

    on_progress(1.0)

    saved = store.get(project.id)
    saved_items = {item.id: item for item in saved.items}
    assert saved_items[rendering_item.id].progress == 1.0
    assert saved_items[sibling_item.id].progress == 0.42
