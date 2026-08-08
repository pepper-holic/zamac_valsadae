from app.models.schemas import Segment
from app.services.review_service import build_review_package, diff_review_import


def make_segments() -> list[Segment]:
    return [
        Segment(id="1", start=0.0, end=1.5, text="안녕하세요", translation="Hello"),
        Segment(id="2", start=1.5, end=3.25, text="반갑습니다", translation="Nice to meet you"),
    ]


def test_build_review_package_includes_instructions_and_segments():
    package = build_review_package(
        item_id="p1", media_filename="video.mp4", segments=make_segments()
    )

    assert package.item_id == "p1"
    assert package.media_filename == "video.mp4"
    assert len(package.segments) == 2
    assert package.instructions
    assert package.segments[0].id == "1"


def test_diff_review_import_detects_text_and_translation_changes():
    current = make_segments()
    imported = [
        {"id": "1", "start": 0.0, "end": 1.5, "text": "안녕하세요", "translation": "Hi there"},
        {"id": "2", "start": 1.5, "end": 3.25, "text": "반갑습니다", "translation": "Nice to meet you"},
    ]

    result = diff_review_import(current, imported)

    assert len(result.diffs) == 1
    diff = result.diffs[0]
    assert diff.id == "1"
    assert diff.field == "translation"
    assert diff.old_value == "Hello"
    assert diff.new_value == "Hi there"
    assert result.unknown_segment_ids == []


def test_diff_review_import_detects_timing_changes():
    current = make_segments()
    imported = [
        {"id": "1", "start": 0.2, "end": 1.5, "text": "안녕하세요", "translation": "Hello"},
        {"id": "2", "start": 1.5, "end": 3.25, "text": "반갑습니다", "translation": "Nice to meet you"},
    ]

    result = diff_review_import(current, imported)

    assert len(result.diffs) == 1
    assert result.diffs[0].field == "start"
    assert result.diffs[0].old_value == 0.0
    assert result.diffs[0].new_value == 0.2


def test_diff_review_import_flags_unknown_segment_ids():
    current = make_segments()
    imported = [
        {"id": "1", "start": 0.0, "end": 1.5, "text": "안녕하세요", "translation": "Hello"},
        {"id": "99", "start": 0.0, "end": 1.0, "text": "ghost", "translation": None},
    ]

    result = diff_review_import(current, imported)

    assert result.unknown_segment_ids == ["99"]
    assert result.diffs == []


def test_diff_review_import_no_changes_returns_empty_diffs():
    current = make_segments()
    imported = [s.model_dump() for s in current]

    result = diff_review_import(current, imported)

    assert result.diffs == []
    assert result.unknown_segment_ids == []
