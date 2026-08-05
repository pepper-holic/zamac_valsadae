from app.models.schemas import Segment


def _format_timestamp(seconds: float, decimal_separator: str) -> str:
    total_ms = round(seconds * 1000)
    hours, remainder_ms = divmod(total_ms, 3_600_000)
    minutes, remainder_ms = divmod(remainder_ms, 60_000)
    secs, millis = divmod(remainder_ms, 1_000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}{decimal_separator}{millis:03d}"


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
