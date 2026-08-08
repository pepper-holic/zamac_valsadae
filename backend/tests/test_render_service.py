from pathlib import Path

import pytest

from app.models.schemas import Segment, SubtitleStyle, Word
from app.services import render_service


def _segment(text: str = "안녕하세요", start: float = 0.0, end: float = 2.0) -> Segment:
    return Segment(id="s1", start=start, end=end, text=text)


def test_build_ass_includes_default_style_values():
    ass = render_service.build_ass([_segment()], SubtitleStyle())

    assert "Style: Default,Pretendard,32" in ass
    assert "Dialogue: 0,0:00:00.00,0:00:02.00,Default" in ass
    assert "안녕하세요" in ass


def test_build_ass_uses_translation_when_requested():
    segment = _segment(text="hello")
    segment = segment.model_copy(update={"translation": "안녕"})

    ass = render_service.build_ass([segment], SubtitleStyle(), use_translation=True)

    assert "안녕" in ass
    assert "hello" not in ass


def test_build_ass_skips_segments_with_no_text_for_selected_field():
    segment = _segment(text="")

    ass = render_service.build_ass([segment], SubtitleStyle())

    assert "Dialogue:" not in ass


def test_build_ass_top_position_uses_alignment_8():
    ass = render_service.build_ass([_segment()], SubtitleStyle(position="top"))

    style_line = next(line for line in ass.splitlines() if line.startswith("Style:"))
    fields = style_line.split(",")
    assert fields[-5] == "8"


def test_build_ass_bottom_position_uses_alignment_2():
    ass = render_service.build_ass([_segment()], SubtitleStyle(position="bottom"))

    style_line = next(line for line in ass.splitlines() if line.startswith("Style:"))
    fields = style_line.split(",")
    assert fields[-5] == "2"


def test_build_ass_with_background_uses_opaque_box_border_style():
    ass = render_service.build_ass([_segment()], SubtitleStyle(background="#112233"))

    style_line = next(line for line in ass.splitlines() if line.startswith("Style:"))
    fields = style_line.split(",")
    assert fields[15] == "3"  # BorderStyle


def test_build_ass_without_background_uses_outline_border_style():
    ass = render_service.build_ass([_segment()], SubtitleStyle(background=None))

    style_line = next(line for line in ass.splitlines() if line.startswith("Style:"))
    fields = style_line.split(",")
    assert fields[15] == "1"  # BorderStyle


def test_build_ass_applies_fade_override_tag():
    ass = render_service.build_ass(
        [_segment()], SubtitleStyle(fade_in_ms=200, fade_out_ms=300)
    )

    assert "\\fad(200,300)" in ass


def test_build_ass_karaoke_splits_text_into_k_tagged_words():
    ass = render_service.build_ass(
        [_segment(text="one two three")], SubtitleStyle(karaoke_highlight=True)
    )

    assert ass.count("\\k") == 3


def test_build_ass_karaoke_uses_real_word_durations_when_available():
    segment = _segment(text="one two", start=0.0, end=3.0).model_copy(
        update={
            "words": [
                Word(text="one", start=0.0, end=1.0),
                Word(text="two", start=1.0, end=3.0),
            ]
        }
    )

    ass = render_service.build_ass([segment], SubtitleStyle(karaoke_highlight=True))

    assert "{\\k100}one" in ass
    assert "{\\k200}two" in ass


def test_build_ass_karaoke_falls_back_to_equal_split_when_words_absent():
    ass = render_service.build_ass(
        [_segment(text="one two", start=0.0, end=2.0)], SubtitleStyle(karaoke_highlight=True)
    )

    assert "{\\k100}one" in ass
    assert "{\\k100}two" in ass


def test_build_cut_list_returns_each_segment_range_sorted_by_start():
    segments = [
        _segment(text="b", start=5.0, end=6.0),
        _segment(text="a", start=0.0, end=2.0),
    ]

    cut_list = render_service.build_cut_list(segments)

    assert cut_list == [(0.0, 2.0), (5.0, 6.0)]


def test_build_cut_list_merges_touching_ranges():
    segments = [
        _segment(text="a", start=0.0, end=2.0),
        _segment(text="b", start=2.0, end=4.0),
    ]

    cut_list = render_service.build_cut_list(segments)

    assert cut_list == [(0.0, 4.0)]


def test_build_cut_list_empty_for_no_segments():
    assert render_service.build_cut_list([]) == []


def test_build_ass_remaps_timestamps_to_output_timeline_when_cut_list_given():
    segment = _segment(text="kept after gap", start=6.0, end=8.0)
    cut_list = [(0.0, 3.0), (6.0, 9.0)]

    ass = render_service.build_ass(
        [segment], SubtitleStyle(), cut_list=cut_list
    )

    # 원본 6.0-8.0초 구간은 (0-3초, 6-9초) 컷 목록에서 두 번째 구간에 속하며,
    # 첫 번째 유지 구간 길이(3초)만큼 앞당겨져 출력 타임라인에서는 3.0-5.0초.
    assert "Dialogue: 0,0:00:03.00,0:00:05.00,Default" in ass


def test_build_ass_empty_cut_list_falls_back_to_original_timestamps():
    ass = render_service.build_ass([_segment(start=6.0, end=8.0)], SubtitleStyle(), cut_list=[])

    assert "Dialogue: 0,0:00:06.00,0:00:08.00,Default" in ass


def test_build_ass_without_cut_list_uses_original_timestamps():
    ass = render_service.build_ass([_segment(start=6.0, end=8.0)], SubtitleStyle())

    assert "Dialogue: 0,0:00:06.00,0:00:08.00,Default" in ass


def test_build_ass_karaoke_ignores_words_when_rendering_translation_text():
    segment = _segment(text="hello", start=0.0, end=2.0).model_copy(
        update={
            "translation": "안녕 하세요",
            "words": [Word(text="hello", start=0.0, end=2.0)],
        }
    )

    ass = render_service.build_ass(
        [segment], SubtitleStyle(karaoke_highlight=True), use_translation=True
    )

    assert ass.count("\\k") == 2


def test_hex_to_ass_color_converts_rgb_to_bgr_with_alpha():
    assert render_service._hex_to_ass_color("#FF0000") == "&H000000FF"
    assert render_service._hex_to_ass_color("#00FF00", alpha=0x80) == "&H8000FF00"


def test_parse_progress_seconds_extracts_ffmpeg_time():
    line = "frame=  120 fps= 30 time=00:00:04.50 bitrate=..."

    assert render_service._parse_progress_seconds(line) == pytest.approx(4.5)


def test_parse_progress_seconds_returns_none_when_no_time_field():
    assert render_service._parse_progress_seconds("frame=1 fps=30") is None


def test_probe_duration_seconds_parses_ffprobe_output(monkeypatch, tmp_path):
    class _FakeResult:
        stdout = "12.345000\n"

    monkeypatch.setattr(
        render_service.subprocess, "run", lambda *a, **k: _FakeResult()
    )

    assert render_service.probe_duration_seconds(tmp_path / "in.mp4") == pytest.approx(12.345)


class _FakeProcess:
    def __init__(self, stderr_lines: list[str], return_code: int = 0):
        self.stderr = iter(stderr_lines)
        self._return_code = return_code
        self.terminated = False

    def wait(self) -> int:
        return self._return_code

    def terminate(self) -> None:
        self.terminated = True


def test_render_reports_progress_from_ffmpeg_stderr(monkeypatch, tmp_path):
    lines = ["time=00:00:01.00 x\n", "time=00:00:02.00 x\n"]
    monkeypatch.setattr(
        render_service.subprocess, "Popen", lambda *a, **k: _FakeProcess(lines)
    )
    progress_values = []

    render_service.render(
        media_path=tmp_path / "in.mp4",
        ass_path=tmp_path / "styled.ass",
        output_path=tmp_path / "out.mp4",
        duration_seconds=2.0,
        on_progress=progress_values.append,
    )

    assert progress_values == [0.5, 1.0]


def test_render_raises_on_nonzero_exit_code(monkeypatch, tmp_path):
    monkeypatch.setattr(
        render_service.subprocess,
        "Popen",
        lambda *a, **k: _FakeProcess(["error: bad codec\n"], return_code=1),
    )

    with pytest.raises(render_service.RenderError):
        render_service.render(
            media_path=tmp_path / "in.mp4",
            ass_path=tmp_path / "styled.ass",
            output_path=tmp_path / "out.mp4",
            duration_seconds=2.0,
        )


def test_render_cancels_when_should_cancel_returns_true(monkeypatch, tmp_path):
    fake = _FakeProcess(["time=00:00:01.00 x\n", "time=00:00:02.00 x\n"])
    monkeypatch.setattr(render_service.subprocess, "Popen", lambda *a, **k: fake)

    with pytest.raises(render_service.RenderCancelled):
        render_service.render(
            media_path=tmp_path / "in.mp4",
            ass_path=tmp_path / "styled.ass",
            output_path=tmp_path / "out.mp4",
            duration_seconds=2.0,
            should_cancel=lambda: True,
        )
    assert fake.terminated


def test_build_cut_filter_complex_trims_and_concats_each_kept_range():
    filter_complex = render_service._build_cut_filter_complex(
        [(0.0, 3.0), (6.0, 9.0)], "styled.ass"
    )

    assert "[0:v]trim=start=0.0:end=3.0,setpts=PTS-STARTPTS[v0]" in filter_complex
    assert "[0:a]atrim=start=0.0:end=3.0,asetpts=PTS-STARTPTS[a0]" in filter_complex
    assert "[0:v]trim=start=6.0:end=9.0,setpts=PTS-STARTPTS[v1]" in filter_complex
    assert "[0:a]atrim=start=6.0:end=9.0,asetpts=PTS-STARTPTS[a1]" in filter_complex
    assert "[v0][a0][v1][a1]concat=n=2:v=1:a=1[vcat][acat]" in filter_complex
    assert "[vcat]ass=styled.ass[vout]" in filter_complex


def test_render_uses_filter_complex_when_cut_list_given(monkeypatch, tmp_path):
    fake = _FakeProcess(["time=00:00:01.00 x\n"])
    captured_command = {}

    def fake_popen(command, **kwargs):
        captured_command["command"] = command
        return fake

    monkeypatch.setattr(render_service.subprocess, "Popen", fake_popen)

    render_service.render(
        media_path=tmp_path / "in.mp4",
        ass_path=tmp_path / "styled.ass",
        output_path=tmp_path / "out.mp4",
        duration_seconds=1.0,
        cut_list=[(0.0, 1.0)],
    )

    command = captured_command["command"]
    assert "-filter_complex" in command
    assert "-map" in command
    assert "[vout]" in command
    assert "[acat]" in command
    assert "-vf" not in command


def test_render_uses_simple_vf_when_no_cut_list(monkeypatch, tmp_path):
    fake = _FakeProcess(["time=00:00:01.00 x\n"])
    captured_command = {}

    def fake_popen(command, **kwargs):
        captured_command["command"] = command
        return fake

    monkeypatch.setattr(render_service.subprocess, "Popen", fake_popen)

    render_service.render(
        media_path=tmp_path / "in.mp4",
        ass_path=tmp_path / "styled.ass",
        output_path=tmp_path / "out.mp4",
        duration_seconds=1.0,
    )

    command = captured_command["command"]
    assert "-vf" in command
    assert "-filter_complex" not in command
