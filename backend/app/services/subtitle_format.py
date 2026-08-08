from xml.sax.saxutils import escape

from app.models.schemas import Segment


def _format_timestamp(seconds: float, decimal_separator: str) -> str:
    total_ms = round(seconds * 1000)
    hours, remainder_ms = divmod(total_ms, 3_600_000)
    minutes, remainder_ms = divmod(remainder_ms, 60_000)
    secs, millis = divmod(remainder_ms, 1_000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}{decimal_separator}{millis:03d}"


def _format_ass_timestamp(seconds: float) -> str:
    # ASS uses centisecond precision and an unpadded hour field.
    total_cs = round(seconds * 100)
    hours, remainder_cs = divmod(total_cs, 360_000)
    minutes, remainder_cs = divmod(remainder_cs, 6_000)
    secs, centis = divmod(remainder_cs, 100)
    return f"{hours}:{minutes:02d}:{secs:02d}.{centis:02d}"


def _pick_text(segment: Segment, use_translation: bool) -> str:
    if use_translation and segment.translation:
        return segment.translation
    return segment.text


def to_srt(segments: list[Segment], use_translation: bool = False) -> str:
    blocks = []
    for index, segment in enumerate(segments, start=1):
        start = _format_timestamp(segment.start, ",")
        end = _format_timestamp(segment.end, ",")
        text = _pick_text(segment, use_translation)
        blocks.append(f"{index}\n{start} --> {end}\n{text}\n")
    return "\n".join(blocks)


def to_vtt(segments: list[Segment], use_translation: bool = False) -> str:
    lines = ["WEBVTT", ""]
    for segment in segments:
        start = _format_timestamp(segment.start, ".")
        end = _format_timestamp(segment.end, ".")
        text = _pick_text(segment, use_translation)
        lines.append(f"{start} --> {end}")
        lines.append(text)
        lines.append("")
    return "\n".join(lines)


def to_json(segments: list[Segment]) -> list[dict]:
    return [segment.model_dump() for segment in segments]


_ASS_HEADER = """[Script Info]
Title: Zamak_Valsadae Export
ScriptType: v4.00+

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,Arial,20,&H00FFFFFF,&H000000FF,&H00000000,&H00000000,0,0,0,0,100,100,0,0,1,2,0,2,10,10,10,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text"""


def to_ass(segments: list[Segment], use_translation: bool = False) -> str:
    lines = [_ASS_HEADER]
    for segment in segments:
        start = _format_ass_timestamp(segment.start)
        end = _format_ass_timestamp(segment.end)
        text = _pick_text(segment, use_translation).replace("\n", "\\N")
        lines.append(f"Dialogue: 0,{start},{end},Default,,0,0,0,,{text}")
    return "\n".join(lines) + "\n"


def to_ttml(segments: list[Segment], use_translation: bool = False) -> str:
    paragraphs = []
    for segment in segments:
        start = _format_timestamp(segment.start, ".")
        end = _format_timestamp(segment.end, ".")
        text = escape(_pick_text(segment, use_translation))
        paragraphs.append(f'      <p begin="{start}" end="{end}">{text}</p>')
    body = "\n".join(paragraphs)

    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<tt xmlns="http://www.w3.org/ns/ttml">',
        "  <body>",
        "    <div>",
    ]
    if body:
        lines.append(body)
    lines.extend(["    </div>", "  </body>", "</tt>", ""])
    return "\n".join(lines)
