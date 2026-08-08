from app.models.schemas import Segment
from app.services.subtitle_format import to_ass, to_json, to_srt, to_ttml, to_vtt


def make_segments() -> list[Segment]:
    return [
        Segment(id="1", start=0.0, end=1.5, text="안녕하세요", translation="Hello"),
        Segment(id="2", start=1.5, end=3.25, text="반갑습니다", translation="Nice to meet you"),
    ]


def test_to_srt_formats_index_and_timestamps():
    srt = to_srt(make_segments())

    assert "1\n00:00:00,000 --> 00:00:01,500\n안녕하세요\n" in srt
    assert "2\n00:00:01,500 --> 00:00:03,250\n반갑습니다\n" in srt


def test_to_srt_uses_translation_when_requested():
    srt = to_srt(make_segments(), use_translation=True)

    assert "Hello" in srt
    assert "안녕하세요" not in srt


def test_to_srt_falls_back_to_text_when_translation_missing():
    segments = [Segment(id="1", start=0.0, end=1.0, text="원문만 있음", translation=None)]

    srt = to_srt(segments, use_translation=True)

    assert "원문만 있음" in srt


def test_to_vtt_starts_with_header_and_uses_dot_separator():
    vtt = to_vtt(make_segments())

    assert vtt.startswith("WEBVTT\n\n")
    assert "00:00:00.000 --> 00:00:01.500" in vtt


def test_to_json_round_trips_segment_fields():
    data = to_json(make_segments())

    assert data[0]["id"] == "1"
    assert data[0]["text"] == "안녕하세요"
    assert data[0]["translation"] == "Hello"
    assert data[1]["end"] == 3.25


def test_to_srt_empty_segments_returns_empty_string():
    assert to_srt([]) == ""


def test_to_ass_includes_header_sections_and_dialogue_lines():
    ass = to_ass(make_segments())

    assert "[Script Info]" in ass
    assert "[V4+ Styles]" in ass
    assert "[Events]" in ass
    assert "Dialogue: 0,0:00:00.00,0:00:01.50,Default,,0,0,0,,안녕하세요" in ass
    assert "Dialogue: 0,0:00:01.50,0:00:03.25,Default,,0,0,0,,반갑습니다" in ass


def test_to_ass_uses_translation_when_requested():
    ass = to_ass(make_segments(), use_translation=True)

    assert "Hello" in ass
    assert "안녕하세요" not in ass


def test_to_ass_empty_segments_still_has_headers():
    ass = to_ass([])

    assert "[Events]" in ass


def test_to_ttml_wraps_segments_in_p_tags_with_timestamps():
    ttml = to_ttml(make_segments())

    assert '<p begin="00:00:00.000" end="00:00:01.500">안녕하세요</p>' in ttml
    assert '<p begin="00:00:01.500" end="00:00:03.250">반갑습니다</p>' in ttml
    assert ttml.startswith('<?xml version="1.0" encoding="UTF-8"?>')


def test_to_ttml_escapes_special_characters():
    segments = [Segment(id="1", start=0.0, end=1.0, text="A & B < C")]

    ttml = to_ttml(segments)

    assert "A &amp; B &lt; C" in ttml
    assert "A & B < C" not in ttml


def test_to_ttml_empty_segments_returns_valid_shell():
    ttml = to_ttml([])

    assert "<body>" in ttml
    assert "<div>" in ttml
