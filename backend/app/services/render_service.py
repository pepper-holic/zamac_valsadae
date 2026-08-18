import queue
import re
import subprocess
import threading
from collections.abc import Callable
from pathlib import Path

from app.core.config import get_settings
from app.models.schemas import Segment, SubtitleStyle
from app.services.subtitle_format import format_ass_timestamp, pick_text
from app.services.text_wrap import wrap_subtitle_text

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


def build_cut_list(segments: list[Segment]) -> list[tuple[float, float]]:
    """삭제되지 않고 남아있는 세그먼트들의 (start, end) 구간을 시간순으로 정렬해 반환.

    삭제=컷 정책: 세그먼트 목록에서 완전히 제거된 구간은 그대로 잘려나가고,
    남은 세그먼트들의 시간 구간만 이어붙여집니다(맞닿은 구간은 하나로 병합).
    """
    ranges = sorted((segment.start, segment.end) for segment in segments if segment.end > segment.start)

    merged: list[list[float]] = []
    for start, end in ranges:
        if merged and start <= merged[-1][1]:
            merged[-1][1] = max(merged[-1][1], end)
        else:
            merged.append([start, end])
    return [(start, end) for start, end in merged]


def _remap_time_for_cuts(time: float, cut_list: list[tuple[float, float]]) -> float:
    """원본 타임라인의 시각을 컷 목록 적용 후 출력 타임라인의 시각으로 변환."""
    output_time = 0.0
    for start, end in cut_list:
        if time <= start:
            return output_time
        if time < end:
            return output_time + (time - start)
        output_time += end - start
    return output_time


def _build_cut_filter_complex(cut_list: list[tuple[float, float]], ass_filename: str) -> str:
    # 유지 구간마다 trim/atrim 필터 쌍이 하나씩 생기므로, 구간 수가 매우 많아지면
    # (예: 문장이 매우 잘게 쪼개진 긴 영상) filter_complex 문자열과 명령줄 길이가
    # 함께 커집니다. Windows의 명령줄 길이 제한(~32K자)을 실무에서 넘길 정도로
    # 큰 편집은 아직 없었지만, 향후 문제가 되면 구간을 청크로 나눠 여러 단계로
    # 렌더링하거나 select/aselect 기반 필터로 교체하는 것을 검토해야 합니다.
    parts = []
    concat_inputs = []
    for index, (start, end) in enumerate(cut_list):
        parts.append(f"[0:v]trim=start={start}:end={end},setpts=PTS-STARTPTS[v{index}]")
        parts.append(f"[0:a]atrim=start={start}:end={end},asetpts=PTS-STARTPTS[a{index}]")
        concat_inputs.append(f"[v{index}][a{index}]")
    parts.append(f"{''.join(concat_inputs)}concat=n={len(cut_list)}:v=1:a=1[vcat][acat]")
    parts.append(f"[vcat]ass={ass_filename}[vout]")
    return ";".join(parts)


def build_ass(
    segments: list[Segment],
    style: SubtitleStyle,
    use_translation: bool = False,
    cut_list: list[tuple[float, float]] | None = None,
) -> str:
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
        if cut_list:
            start = format_ass_timestamp(_remap_time_for_cuts(segment.start, cut_list))
            end = format_ass_timestamp(_remap_time_for_cuts(segment.end, cut_list))
        else:
            start = format_ass_timestamp(segment.start)
            end = format_ass_timestamp(segment.end)
        override = ""
        if style.fade_in_ms > 0 or style.fade_out_ms > 0:
            override = f"{{\\fad({style.fade_in_ms},{style.fade_out_ms})}}"
        if style.karaoke_highlight:
            # 단어별 \k 타이밍 태그가 붙으므로 자동 줄바꿈은 적용하지 않는다
            # (줄바꿈 위치가 타이밍 경계와 어긋나면 카라오케 효과가 깨짐).
            body = _karaoke_text(segment, text, segment.end - segment.start)
        else:
            wrapped = wrap_subtitle_text(text, style.max_line_chars) if style.auto_line_break else text
            body = wrapped.replace("\n", "\\N")
        lines.append(f"Dialogue: 0,{start},{end},Default,,0,0,0,,{override}{body}")
    return "\n".join(lines) + "\n"


def _parse_progress_seconds(line: str) -> float | None:
    match = _TIME_RE.search(line)
    if not match:
        return None
    hours, minutes, seconds, centis = match.groups()
    return int(hours) * 3600 + int(minutes) * 60 + int(seconds) + int(centis) / 100


def probe_duration_seconds(media_path: Path) -> float:
    settings = get_settings()
    try:
        result = subprocess.run(
            [
                settings.ffprobe_path,
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
            timeout=settings.ffprobe_timeout_seconds,
        )
    except subprocess.TimeoutExpired as error:
        raise RenderError("ffprobe가 응답하지 않아 중단했습니다 (미디어 파일 확인 필요).") from error
    return float(result.stdout.strip())


def render(
    media_path: Path,
    ass_path: Path,
    output_path: Path,
    duration_seconds: float,
    on_progress: ProgressCallback | None = None,
    should_cancel: CancelCallback | None = None,
    cut_list: list[tuple[float, float]] | None = None,
) -> None:
    ffmpeg_path = get_settings().ffmpeg_path
    # ffmpeg's ass filter argument is parsed by libavfilter's own escaping
    # rules, where ':' is a key=value separator - a Windows drive-letter
    # colon (C:\...) breaks that parser even when backslash-escaped. Running
    # ffmpeg with cwd set to the .ass file's directory lets us pass just its
    # filename, sidestepping the escaping problem entirely.
    ffmpeg_binary = str(Path(ffmpeg_path).resolve()) if Path(ffmpeg_path).is_file() else ffmpeg_path
    if cut_list:
        filter_complex = _build_cut_filter_complex(cut_list, ass_path.name)
        command = [
            ffmpeg_binary,
            "-y",
            "-i",
            str(media_path.resolve()),
            "-filter_complex",
            filter_complex,
            "-map",
            "[vout]",
            "-map",
            "[acat]",
            str(output_path.resolve()),
        ]
    else:
        command = [
            ffmpeg_binary,
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

    # ffmpeg's stderr is read on a background thread and handed off through
    # a queue so the main loop can poll on a fixed interval instead of
    # blocking on `for line in process.stderr`. A plain blocking read means
    # should_cancel() only gets checked when ffmpeg happens to emit a line -
    # if it stalls (hung filter graph, waiting on stdin, ...) without
    # producing output, cancellation would never fire and this would hang
    # forever. Polling also lets us detect and abort a genuine stall.
    line_queue: "queue.Queue[str | None]" = queue.Queue()

    def _pump_stderr() -> None:
        assert process.stderr is not None
        try:
            for line in process.stderr:
                line_queue.put(line)
        finally:
            line_queue.put(None)

    threading.Thread(target=_pump_stderr, daemon=True).start()

    poll_interval_seconds = 1.0
    stall_timeout_seconds = get_settings().render_stall_timeout_seconds
    silence_elapsed_seconds = 0.0
    stderr_tail: list[str] = []

    while True:
        if should_cancel is not None and should_cancel():
            process.terminate()
            process.wait()
            raise RenderCancelled("영상 렌더링이 취소되었습니다.")

        try:
            line = line_queue.get(timeout=poll_interval_seconds)
        except queue.Empty:
            silence_elapsed_seconds += poll_interval_seconds
            if silence_elapsed_seconds >= stall_timeout_seconds:
                process.terminate()
                process.wait()
                raise RenderError(
                    f"ffmpeg가 {int(stall_timeout_seconds)}초 동안 응답이 없어 "
                    "렌더링을 중단했습니다."
                )
            continue

        silence_elapsed_seconds = 0.0
        if line is None:  # stderr pipe closed - ffmpeg has exited
            break

        stderr_tail.append(line)
        if len(stderr_tail) > 40:
            stderr_tail.pop(0)
        if on_progress is not None and duration_seconds > 0:
            elapsed = _parse_progress_seconds(line)
            if elapsed is not None:
                on_progress(min(elapsed / duration_seconds, 1.0))

    return_code = process.wait()
    if return_code != 0:
        raise RenderError("ffmpeg 렌더링이 실패했습니다:\n" + "".join(stderr_tail))
