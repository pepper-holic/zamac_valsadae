from app.models.schemas import QualityFlag, Segment

# Netflix Timed Text Style Guide 기준값(권장 상한선)을 참고했습니다.
MAX_CPS = 17.0
MAX_CHARS_PER_LINE = 42
MIN_DURATION_SEC = 5 / 6
MAX_DURATION_SEC = 7.0


def _pick_text(segment: Segment, use_translation: bool) -> str:
    if use_translation and segment.translation:
        return segment.translation
    return segment.text


def assess_readability(
    segment: Segment, use_translation: bool = False
) -> tuple[QualityFlag, str | None]:
    text = _pick_text(segment, use_translation)
    if not text:
        return "good", None

    reasons = []
    duration = segment.end - segment.start

    if duration > 0:
        cps = len(text) / duration
        if cps > MAX_CPS:
            reasons.append(f"초당 글자 수가 기준({MAX_CPS:.0f} CPS)을 초과합니다 ({cps:.1f} CPS)")

    if len(text) > MAX_CHARS_PER_LINE:
        reasons.append(f"한 줄 글자 수가 기준({MAX_CHARS_PER_LINE}자)을 초과합니다 ({len(text)}자)")

    if duration < MIN_DURATION_SEC:
        reasons.append(f"지속시간이 너무 짧습니다 ({duration:.2f}초)")
    elif duration > MAX_DURATION_SEC:
        reasons.append(f"지속시간이 너무 깁니다 ({duration:.2f}초)")

    if reasons:
        return "check", " / ".join(reasons)
    return "good", None


def apply_readability(segments: list[Segment], use_translation: bool = False) -> list[Segment]:
    updated = []
    for segment in segments:
        flag, reason = assess_readability(segment, use_translation=use_translation)
        updated.append(
            segment.model_copy(update={"readability_flag": flag, "readability_reason": reason})
        )
    return updated
