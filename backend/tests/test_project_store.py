import pytest

from app.models.schemas import Segment
from app.services.project_store import ItemNotFoundError, ProjectNotFoundError, ProjectStore


@pytest.fixture
def store(tmp_path):
    return ProjectStore(root_dir=tmp_path)


def test_create_project_starts_with_no_items(store):
    project = store.create_project(name="시리즈 A")

    assert project.name == "시리즈 A"
    assert project.items == []


def test_add_item_saves_media_and_appends_to_project(store):
    project = store.create_project()

    item = store.add_item(project.id, filename="video.mp4", media_bytes=b"fake-bytes")

    assert item.filename == "video.mp4"
    assert item.status == "uploaded"
    assert item.segments == []

    media_file = store.media_path(project.id, item.id)
    assert media_file.exists()
    assert media_file.read_bytes() == b"fake-bytes"

    reloaded = store.get(project.id)
    assert [i.id for i in reloaded.items] == [item.id]


def test_add_item_to_missing_project_raises(store):
    with pytest.raises(ProjectNotFoundError):
        store.add_item("does-not-exist", filename="a.wav", media_bytes=b"1")


def test_add_multiple_items_to_same_project(store):
    project = store.create_project()

    first = store.add_item(project.id, filename="a.wav", media_bytes=b"1")
    second = store.add_item(project.id, filename="b.wav", media_bytes=b"2")

    reloaded = store.get(project.id)
    assert [i.filename for i in reloaded.items] == ["a.wav", "b.wav"]
    assert first.id != second.id


def test_remove_item_deletes_media_and_entry(store):
    project = store.create_project()
    item = store.add_item(project.id, filename="a.wav", media_bytes=b"1")
    media_file = store.media_path(project.id, item.id)

    store.remove_item(project.id, item.id)

    assert not media_file.exists()
    assert store.get(project.id).items == []


def test_remove_missing_item_raises(store):
    project = store.create_project()

    with pytest.raises(ItemNotFoundError):
        store.remove_item(project.id, "does-not-exist")


def test_get_item_returns_matching_item(store):
    project = store.create_project()
    item = store.add_item(project.id, filename="a.wav", media_bytes=b"1")

    fetched = store.get_item(project.id, item.id)

    assert fetched.id == item.id
    assert fetched.filename == "a.wav"


def test_get_item_missing_raises(store):
    project = store.create_project()

    with pytest.raises(ItemNotFoundError):
        store.get_item(project.id, "does-not-exist")


def test_get_returns_saved_project(store):
    created = store.create_project(name="a")

    fetched = store.get(created.id)

    assert fetched.id == created.id
    assert fetched.name == "a"


def test_get_missing_project_raises(store):
    with pytest.raises(ProjectNotFoundError):
        store.get("does-not-exist")


def test_load_translation_memory_missing_returns_empty_dict(store):
    project = store.create_project()

    assert store.load_translation_memory(project.id, "ko->en") == {}


def test_save_and_load_translation_memory_round_trips(store):
    project = store.create_project()

    store.save_translation_memory(project.id, "ko->en", {"안녕": "Hi"})

    assert store.load_translation_memory(project.id, "ko->en") == {"안녕": "Hi"}


def test_save_translation_memory_merges_with_existing_entries(store):
    project = store.create_project()
    store.save_translation_memory(project.id, "ko->en", {"안녕": "Hi"})

    store.save_translation_memory(project.id, "ko->en", {"반가워": "Nice to meet you"})

    assert store.load_translation_memory(project.id, "ko->en") == {
        "안녕": "Hi",
        "반가워": "Nice to meet you",
    }


def test_translation_memory_is_scoped_by_direction(store):
    project = store.create_project()
    store.save_translation_memory(project.id, "ko->en", {"안녕": "Hi"})

    assert store.load_translation_memory(project.id, "en->ko") == {}


def test_save_persists_updates(store):
    project = store.create_project()
    item = store.add_item(project.id, filename="a.wav", media_bytes=b"123")
    project = store.get(project.id)
    project.items[0].status = "transcribed"

    store.save(project)
    reloaded = store.get(project.id)

    assert reloaded.items[0].id == item.id
    assert reloaded.items[0].status == "transcribed"


def test_list_returns_all_created_projects(store):
    store.create_project(name="a")
    store.create_project(name="b")

    projects = store.list()

    assert {p.name for p in projects} == {"a", "b"}


def test_delete_removes_project_directory_entirely(store):
    project = store.create_project()
    item = store.add_item(project.id, filename="a.wav", media_bytes=b"123")
    project_dir = store.media_path(project.id, item.id).parent

    store.delete(project.id)

    assert not project_dir.exists()
    assert store.list() == []


def test_delete_missing_project_raises(store):
    with pytest.raises(ProjectNotFoundError):
        store.delete("does-not-exist")


def test_delete_does_not_affect_other_projects(store):
    keep = store.create_project(name="keep")
    remove = store.create_project(name="remove")

    store.delete(remove.id)

    assert [p.name for p in store.list()] == ["keep"]
    assert store.get(keep.id).id == keep.id


def _segments(*texts: str) -> list[Segment]:
    return [Segment(id=str(i), text=text) for i, text in enumerate(texts)]


def test_undo_without_history_returns_none(store):
    assert store.undo("item-1", current_segments=_segments("a")) is None


def test_redo_without_history_returns_none(store):
    assert store.redo("item-1", current_segments=_segments("a")) is None


def test_undo_restores_previously_pushed_state(store):
    store.push_history("item-1", _segments("original"))

    restored = store.undo("item-1", current_segments=_segments("edited"))

    assert [s.text for s in restored] == ["original"]


def test_redo_restores_state_undone(store):
    store.push_history("item-1", _segments("original"))
    store.undo("item-1", current_segments=_segments("edited"))

    restored = store.redo("item-1", current_segments=_segments("original"))

    assert [s.text for s in restored] == ["edited"]


def test_undo_redo_round_trip_multiple_steps(store):
    store.push_history("item-1", _segments("v1"))
    store.push_history("item-1", _segments("v2"))

    assert [s.text for s in store.undo("item-1", _segments("v3"))] == ["v2"]
    assert [s.text for s in store.undo("item-1", _segments("v2"))] == ["v1"]
    assert store.undo("item-1", _segments("v1")) is None


def test_new_push_after_undo_clears_redo_stack(store):
    store.push_history("item-1", _segments("v1"))
    store.undo("item-1", current_segments=_segments("v2"))
    store.push_history("item-1", _segments("v2"))

    assert store.redo("item-1", current_segments=_segments("v3")) is None


def test_history_is_scoped_per_item(store):
    store.push_history("item-1", _segments("item-1-state"))

    assert store.undo("item-2", current_segments=_segments("x")) is None


def test_remove_item_discards_its_history(store):
    project = store.create_project()
    item = store.add_item(project.id, filename="a.wav", media_bytes=b"1")
    store.push_history(item.id, _segments("v1"))

    store.remove_item(project.id, item.id)

    assert store.undo(item.id, current_segments=_segments("current")) is None


def test_delete_project_discards_history_for_all_its_items(store):
    project = store.create_project()
    item = store.add_item(project.id, filename="a.wav", media_bytes=b"1")
    store.push_history(item.id, _segments("v1"))

    store.delete(project.id)

    assert store.undo(item.id, current_segments=_segments("current")) is None


def test_history_stack_evicts_oldest_beyond_max(store):
    for i in range(25):
        store.push_history("item-1", _segments(f"v{i}"))

    restored = []
    current = _segments("current")
    while True:
        previous = store.undo("item-1", current_segments=current)
        if previous is None:
            break
        restored.append(previous[0].text)
        current = previous

    assert len(restored) == 20
    assert restored[-1] == "v5"
