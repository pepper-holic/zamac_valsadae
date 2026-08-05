import pytest

from app.services.project_store import ProjectNotFoundError, ProjectStore


@pytest.fixture
def store(tmp_path):
    return ProjectStore(root_dir=tmp_path)


def test_create_project_saves_media_and_metadata(store):
    project = store.create(filename="video.mp4", media_bytes=b"fake-bytes")

    assert project.filename == "video.mp4"
    assert project.status == "uploaded"
    assert project.segments == []

    media_file = store.media_path(project.id)
    assert media_file.exists()
    assert media_file.read_bytes() == b"fake-bytes"


def test_get_returns_saved_project(store):
    created = store.create(filename="a.wav", media_bytes=b"123")

    fetched = store.get(created.id)

    assert fetched.id == created.id
    assert fetched.filename == "a.wav"


def test_get_missing_project_raises(store):
    with pytest.raises(ProjectNotFoundError):
        store.get("does-not-exist")


def test_save_persists_updates(store):
    project = store.create(filename="a.wav", media_bytes=b"123")
    project.status = "transcribed"

    store.save(project)
    reloaded = store.get(project.id)

    assert reloaded.status == "transcribed"


def test_list_returns_all_created_projects(store):
    store.create(filename="a.wav", media_bytes=b"1")
    store.create(filename="b.wav", media_bytes=b"2")

    projects = store.list()

    assert {p.filename for p in projects} == {"a.wav", "b.wav"}


def test_delete_removes_project_directory_entirely(store):
    project = store.create(filename="a.wav", media_bytes=b"123")
    project_dir = store.media_path(project.id).parent

    store.delete(project.id)

    assert not project_dir.exists()
    assert store.list() == []


def test_delete_missing_project_raises(store):
    with pytest.raises(ProjectNotFoundError):
        store.delete("does-not-exist")


def test_delete_does_not_affect_other_projects(store):
    keep = store.create(filename="keep.wav", media_bytes=b"1")
    remove = store.create(filename="remove.wav", media_bytes=b"2")

    store.delete(remove.id)

    assert [p.filename for p in store.list()] == ["keep.wav"]
    assert store.get(keep.id).id == keep.id
