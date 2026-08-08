import pytest

from app.models.schemas import Segment
from app.services.segment_edit_service import find_replace, merge_segments, split_segment


def test_split_segment_divides_time_range_at_split_point():
    segment = Segment(id="1", start=0.0, end=10.0, text="a")

    first, second = split_segment(segment, split_at=4.0)

    assert first.start == 0.0
    assert first.end == 4.0
    assert second.start == 4.0
    assert second.end == 10.0
    assert first.id != second.id
    assert first.id != segment.id


def test_split_segment_divides_text_by_word_ratio():
    segment = Segment(id="1", start=0.0, end=10.0, text="one two three four")

    first, second = split_segment(segment, split_at=5.0)

    assert first.text == "one two"
    assert second.text == "three four"


def test_split_segment_splits_translation_when_present():
    segment = Segment(
        id="1", start=0.0, end=10.0, text="one two three four", translation="a b c d"
    )

    first, second = split_segment(segment, split_at=5.0)

    assert first.translation == "a b"
    assert second.translation == "c d"


def test_split_segment_leaves_translation_none_when_absent():
    segment = Segment(id="1", start=0.0, end=10.0, text="one two three four")

    first, second = split_segment(segment, split_at=5.0)

    assert first.translation is None
    assert second.translation is None


def test_split_segment_rejects_point_outside_range():
    segment = Segment(id="1", start=0.0, end=10.0, text="one two")

    with pytest.raises(ValueError):
        split_segment(segment, split_at=10.0)
    with pytest.raises(ValueError):
        split_segment(segment, split_at=0.0)
    with pytest.raises(ValueError):
        split_segment(segment, split_at=15.0)


def test_split_segment_single_word_splits_by_character():
    segment = Segment(id="1", start=0.0, end=10.0, text="abcdefgh")

    first, second = split_segment(segment, split_at=5.0)

    assert first.text + second.text == "abcdefgh"
    assert first.text != ""
    assert second.text != ""


def test_split_segment_recomputes_readability():
    segment = Segment(id="1", start=0.0, end=10.0, text="one two three four")

    first, second = split_segment(segment, split_at=5.0)

    assert first.readability_flag is not None
    assert second.readability_flag is not None


def test_merge_segments_combines_text_in_time_order():
    segments = [
        Segment(id="2", start=2.0, end=3.0, text="world"),
        Segment(id="1", start=0.0, end=1.0, text="hello"),
    ]

    merged = merge_segments(segments)

    assert merged.text == "hello world"
    assert merged.start == 0.0
    assert merged.end == 3.0
    assert merged.id not in ("1", "2")


def test_merge_segments_joins_translations_when_all_present():
    segments = [
        Segment(id="1", start=0.0, end=1.0, text="a", translation="hi"),
        Segment(id="2", start=1.0, end=2.0, text="b", translation="there"),
    ]

    merged = merge_segments(segments)

    assert merged.translation == "hi there"


def test_merge_segments_translation_none_when_any_missing():
    segments = [
        Segment(id="1", start=0.0, end=1.0, text="a", translation="hi"),
        Segment(id="2", start=1.0, end=2.0, text="b", translation=None),
    ]

    merged = merge_segments(segments)

    assert merged.translation is None


def test_merge_segments_keeps_speaker_when_all_match():
    segments = [
        Segment(id="1", start=0.0, end=1.0, text="a", speaker="SPEAKER_00"),
        Segment(id="2", start=1.0, end=2.0, text="b", speaker="SPEAKER_00"),
    ]

    merged = merge_segments(segments)

    assert merged.speaker == "SPEAKER_00"


def test_merge_segments_speaker_none_when_mismatched():
    segments = [
        Segment(id="1", start=0.0, end=1.0, text="a", speaker="SPEAKER_00"),
        Segment(id="2", start=1.0, end=2.0, text="b", speaker="SPEAKER_01"),
    ]

    merged = merge_segments(segments)

    assert merged.speaker is None


def test_merge_segments_requires_at_least_two():
    with pytest.raises(ValueError):
        merge_segments([Segment(id="1", start=0.0, end=1.0, text="a")])


def test_find_replace_replaces_matching_text_field():
    segments = [
        Segment(id="1", start=0.0, end=1.0, text="hello world"),
        Segment(id="2", start=1.0, end=2.0, text="goodbye"),
    ]

    updated = find_replace(segments, field="text", find="world", replace="earth")

    assert updated[0].text == "hello earth"
    assert updated[1].text == "goodbye"


def test_find_replace_replaces_matching_translation_field():
    segments = [Segment(id="1", start=0.0, end=1.0, text="x", translation="hello world")]

    updated = find_replace(segments, field="translation", find="world", replace="earth")

    assert updated[0].translation == "hello earth"


def test_find_replace_skips_segments_with_none_translation():
    segments = [Segment(id="1", start=0.0, end=1.0, text="x", translation=None)]

    updated = find_replace(segments, field="translation", find="world", replace="earth")

    assert updated[0].translation is None


def test_find_replace_empty_find_returns_segments_unchanged():
    segments = [Segment(id="1", start=0.0, end=1.0, text="hello")]

    updated = find_replace(segments, field="text", find="", replace="x")

    assert updated[0].text == "hello"


def test_find_replace_does_not_mutate_original_segments():
    segments = [Segment(id="1", start=0.0, end=1.0, text="hello world")]

    find_replace(segments, field="text", find="world", replace="earth")

    assert segments[0].text == "hello world"
