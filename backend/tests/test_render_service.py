from pathlib import Path

import pytest

from app.models.schemas import Segment, SubtitleStyle
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
