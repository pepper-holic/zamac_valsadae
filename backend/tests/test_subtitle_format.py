from app.models.schemas import Segment
from app.services.subtitle_format import to_json, to_srt, to_vtt


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
