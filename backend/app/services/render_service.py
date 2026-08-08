import re
import subprocess
from collections.abc import Callable
from pathlib import Path

from app.core.config import get_settings
from app.models.schemas import Segment, SubtitleStyle
from app.services.subtitle_format import format_ass_timestamp, pick_text

ProgressCallback = Callable[[float], None]
CancelCallback = Callable[[], bool]

_TIME_RE = re.compile(r"time=(\d+):(\d+):(\d+)\.(\d+)")


class RenderCancelled(Exception):
    """사용자가 번인 렌더링을 취소했을 때 발생하는 예외"""


class RenderError(Exception):
    """ffmpeg 실행이 실패했을 때 발생하는 예외"""


def _hex_to_ass_color(hex_color: str, alpha: int = 0) -> str:
    hex_color = hex_color.lstrip("#")
    r, g, b = hex_color[0:2], hex_color[2:4], hex_color[4:6]
    return f"&H{alpha:02X}{b}{g}{r}".upper()


def _alignment_for(position: str) -> int:
    return 8 if position == "top" else 2


def _karaoke_text_from_words(segment: Segment) -> str:
    parts = []
    for word in segment.words:
        word_text = word.text.strip()
        if not word_text:
            continue
        duration_cs = max(round((word.end - word.start) * 100), 1)
        parts.append(f"{{\\k{duration_cs}}}{word_text} ")
    return "".join(parts).strip()


def _karaoke_text(segment: Segment, text: str, duration_seconds: float) -> str:
    # 단어별 타임스탬프는 원문(segment.text)에만 대응되므로, 번역문을 렌더링할
    # 때는 words가 있어도 균등 분할 폴백을 사용한다.
    if segment.words and text == segment.text:
        return _karaoke_text_from_words(segment)
    words = text.split()
    if not words:
        return text
    per_word_cs = max(round((duration_seconds * 100) / len(words)), 1)
    return "".join(f"{{\\k{per_word_cs}}}{word} " for word in words).strip()


def build_ass(segments: list[Segment], style: SubtitleStyle, use_translation: bool = False) -> str:
    alignment = _alignment_for(style.position)
    bold = 1 if style.font_weight == "bold" else 0
    primary = _hex_to_ass_color(style.color)

    if style.background:
        border_style = 3
        outline_colour = _hex_to_ass_color(style.background, alpha=0x40)
        back_colour = outline_colour
        outline = 0
    else:
        border_style = 1
        outline_colour = _hex_to_ass_color(style.outline_color)
        back_colour = "&H00000000"
        outline = style.outline_width

    header = (
        "[Script Info]\n"
        "Title: Zamak_Valsadae Render\n"
        "ScriptType: v4.00+\n\n"
        "[V4+ Styles]\n"
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, "
        "BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, "
        "BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding\n"
        f"Style: Default,{style.font_family},{style.font_size},{primary},&H000000FF,"
        f"{outline_colour},{back_colour},{bold},0,0,0,100,100,0,0,{border_style},{outline},0,"
        f"{alignment},10,10,20,1\n\n"
        "[Events]\n"
        "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text"
    )

    lines = [header]
    for segment in segments:
        text = pick_text(segment, use_translation)
        if not text:
            continue
        start = format_ass_timestamp(segment.start)
        end = format_ass_timestamp(segment.end)
        override = ""
        if style.fade_in_ms > 0 or style.fade_out_ms > 0:
            override = f"{{\\fad({style.fade_in_ms},{style.fade_out_ms})}}"
        body = (
            _karaoke_text(segment, text, segment.end - segment.start)
            if style.karaoke_highlight
            else text
        )
        body = body.replace("\n", "\\N")
        lines.append(f"Dialogue: 0,{start},{end},Default,,0,0,0,,{override}{body}")
    return "\n".join(lines) + "\n"


def _parse_progress_seconds(line: str) -> float | None:
    match = _TIME_RE.search(line)
    if not match:
        return None
    hours, minutes, seconds, centis = match.groups()
    return int(hours) * 3600 + int(minutes) * 60 + int(seconds) + int(centis) / 100


def probe_duration_seconds(media_path: Path) -> float:
    result = subprocess.run(
        [
            get_settings().ffprobe_path,
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "default=noprint_wrappers=1:nokey=1",
            str(media_path),
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    return float(result.stdout.strip())


def render(
    media_path: Path,
    ass_path: Path,
    output_path: Path,
    duration_seconds: float,
    on_progress: ProgressCallback | None = None,
    should_cancel: CancelCallback | None = None,
) -> None:
    ffmpeg_path = get_settings().ffmpeg_path
    # ffmpeg's ass filter argument is parsed by libavfilter's own escaping
    # rules, where ':' is a key=value separator - a Windows drive-letter
    # colon (C:\...) breaks that parser even when backslash-escaped. Running
    # ffmpeg with cwd set to the .ass file's directory lets us pass just its
    # filename, sidestepping the escaping problem entirely.
    command = [
        str(Path(ffmpeg_path).resolve()) if Path(ffmpeg_path).is_file() else ffmpeg_path,
        "-y",
        "-i",
        str(media_path.resolve()),
        "-vf",
        f"ass={ass_path.name}",
        str(output_path.resolve()),
    ]

    process = subprocess.Popen(
        command,
        cwd=ass_path.parent,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    assert process.stderr is not None

    stderr_tail: list[str] = []
    for line in process.stderr:
        stderr_tail.append(line)
        if len(stderr_tail) > 40:
            stderr_tail.pop(0)
        if should_cancel is not None and should_cancel():
            process.terminate()
            process.wait()
            raise RenderCancelled("영상 렌더링이 취소되었습니다.")
        if on_progress is not None and duration_seconds > 0:
            elapsed = _parse_progress_seconds(line)
            if elapsed is not None:
                on_progress(min(elapsed / duration_seconds, 1.0))

    return_code = process.wait()
    if return_code != 0:
        raise RenderError("ffmpeg 렌더링이 실패했습니다:\n" + "".join(stderr_tail))
