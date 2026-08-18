import pytest

from app.models.schemas import Segment
from app.services.project_store import (
    ItemNotFoundError,
    ProjectNotFoundError,
    ProjectStore,
    UploadTooLargeError,
)


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


def test_add_item_rejects_stream_over_max_upload_bytes(store, monkeypatch):
    import io

    from app.core.config import Settings

    monkeypatch.setattr(
        "app.services.project_store.get_settings", lambda: Settings(max_upload_bytes=10)
    )
    project = store.create_project()
    oversized = io.BytesIO(b"x" * 11)

    with pytest.raises(UploadTooLargeError):
        store.add_item(project.id, filename="too-big.mp4", media_bytes=oversized)

    reloaded = store.get(project.id)
    assert reloaded.items == []
    leftover_media = list(store._project_dir(project.id).glob("media_*"))
    assert leftover_media == [], "partial upload should be cleaned up, not left on disk"


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


def test_path_traversal_project_id_is_rejected(store, tmp_path):
    """project_id/item_id are always server-generated uuid4().hex, but the
    API takes them from a URL path parameter with no format constraint - a
    crafted id must not be able to escape the store's root directory."""
    outside_secret = tmp_path.parent / "outside_secret.txt"
    outside_secret.write_text("should not be reachable")

    with pytest.raises(ProjectNotFoundError):
        store.get(f"../{outside_secret.name}")

    with pytest.raises(ItemNotFoundError):
        project = store.create_project()
        store.media_path(project.id, f"../../{outside_secret.name}")


def test_load_translation_memory_missing_returns_empty_dict(store):
    project = store.create_project()

    assert store.load_translation_memory(project.id) == {}


def test_save_and_load_translation_memory_round_trips(store):
    project = store.create_project()

    store.save_translation_memory(project.id, {"안녕": "Hi"})

    assert store.load_translation_memory(project.id) == {"안녕": "Hi"}


def test_save_translation_memory_merges_with_existing_entries(store):
    project = store.create_project()
    store.save_translation_memory(project.id, {"안녕": "Hi"})

    store.save_translation_memory(project.id, {"반가워": "Nice to meet you"})

    assert store.load_translation_memory(project.id) == {
        "안녕": "Hi",
        "반가워": "Nice to meet you",
    }


def test_load_translation_memory_migrates_and_merges_legacy_direction_files(store):
    project = store.create_project()
    project_dir = store._project_dir(project.id)
    project_dir.mkdir(parents=True, exist_ok=True)
    (project_dir / "tm_ko_to_en.json").write_text('{"안녕": "Hi"}', encoding="utf-8")
    (project_dir / "tm_en_to_ko.json").write_text('{"Hello": "안녕하세요"}', encoding="utf-8")

    memory = store.load_translation_memory(project.id)

    assert memory == {"안녕": "Hi", "Hello": "안녕하세요"}
    # migration should persist to the new single-file cache
    assert (project_dir / "tm.json").exists()


def test_save_persists_updates(store):
    project = store.create_project()
    item = store.add_item(project.id, filename="a.wav", media_bytes=b"123")
    project = store.get(project.id)
    project.items[0].status = "transcribed"

    store.save(project)
    reloaded = store.get(project.id)

    assert reloaded.items[0].id == item.id
    assert reloaded.items[0].status == "transcribed"


def test_save_is_atomic_no_leftover_tmp_file_on_success(store):
    project = store.create_project()

    store.save(project)

    metadata_dir = store._metadata_path(project.id).parent
    leftovers = list(metadata_dir.glob("*.tmp"))
    assert leftovers == []


def test_save_does_not_corrupt_existing_file_when_write_fails(store, monkeypatch):
    project = store.create_project()
    item = store.add_item(project.id, filename="a.wav", media_bytes=b"123")
    good_project = store.get(project.id)

    project = store.get(project.id)
    project.items[0].status = "should-not-be-persisted"
    original_write_text = type(store._metadata_path(project.id)).write_text

    def _boom(self, *args, **kwargs):
        if self.suffix == ".tmp":
            raise OSError("disk full (simulated)")
        return original_write_text(self, *args, **kwargs)

    monkeypatch.setattr("pathlib.Path.write_text", _boom)

    with pytest.raises(OSError):
        store.save(project)

    monkeypatch.undo()
    reloaded = store.get(project.id)
    assert reloaded.items[0].id == item.id
    assert reloaded.items[0].status == good_project.items[0].status
    metadata_dir = store._metadata_path(project.id).parent
    assert list(metadata_dir.glob("*.tmp")) == []


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


def test_save_persists_subtitle_style_and_presets(store):
    from app.models.schemas import NamedSubtitleStyle, SubtitleStyle

    project = store.create_project()
    project.subtitle_style = SubtitleStyle(font_size=40, color="#00FF00")
    project.style_presets = [NamedSubtitleStyle(name="preset-a", style=SubtitleStyle())]

    store.save(project)
    reloaded = store.get(project.id)

    assert reloaded.subtitle_style.font_size == 40
    assert reloaded.subtitle_style.color == "#00FF00"
    assert [p.name for p in reloaded.style_presets] == ["preset-a"]


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
