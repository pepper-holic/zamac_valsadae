import re
import uuid

from app.core.config import FILLER_WORDS_EN, FILLER_WORDS_KO
from app.models.schemas import Segment
from app.services.readability_service import assess_readability

_PUNCTUATION_RE = re.compile(r"[.,!?…~\-'\"“”‘’、。！？:;]+")


def _with_readability(segment: Segment) -> Segment:
    flag, reason = assess_readability(segment, use_translation=bool(segment.translation))
    return segment.model_copy(update={"readability_flag": flag, "readability_reason": reason})


def _split_text(text: str, ratio: float) -> tuple[str, str]:
    words = text.split()
    if len(words) < 2:
        # single word (or empty) - fall back to a character-level split so
        # both halves still get *something*, rather than leaving one empty.
        cut = min(max(round(len(text) * ratio), 1), max(len(text) - 1, 1))
        return text[:cut].strip(), text[cut:].strip()
    cut = min(max(round(len(words) * ratio), 1), len(words) - 1)
    return " ".join(words[:cut]), " ".join(words[cut:])


def split_segment(segment: Segment, split_at: float) -> tuple[Segment, Segment]:
    if not (segment.start < split_at < segment.end):
        raise ValueError("분할 지점은 문장의 시작과 종료 시간 사이여야 합니다.")

    ratio = (split_at - segment.start) / (segment.end - segment.start)
    first_text, second_text = _split_text(segment.text, ratio)
    first_translation, second_translation = (None, None)
    if segment.translation:
        first_translation, second_translation = _split_text(segment.translation, ratio)

    first = Segment(
        id=uuid.uuid4().hex,
        start=segment.start,
        end=split_at,
        text=first_text,
        translation=first_translation,
        speaker=segment.speaker,
    )
    second = Segment(
        id=uuid.uuid4().hex,
        start=split_at,
        end=segment.end,
        text=second_text,
        translation=second_translation,
        speaker=segment.speaker,
    )
    return _with_readability(first), _with_readability(second)


def merge_segments(segments: list[Segment]) -> Segment:
    if len(segments) < 2:
        raise ValueError("병합하려면 문장이 2개 이상 필요합니다.")

    ordered = sorted(segments, key=lambda segment: segment.start)
    text = " ".join(segment.text for segment in ordered if segment.text)
    translation = (
        " ".join(segment.translation for segment in ordered)  # type: ignore[arg-type]
        if all(segment.translation for segment in ordered)
        else None
    )
    speakers = {segment.speaker for segment in ordered}
    speaker = next(iter(speakers)) if len(speakers) == 1 else None

    merged = Segment(
        id=uuid.uuid4().hex,
        start=ordered[0].start,
        end=ordered[-1].end,
        text=text,
        translation=translation,
        speaker=speaker,
    )
    return _with_readability(merged)


def find_replace(
    segments: list[Segment], field: str, find: str, replace: str
) -> list[Segment]:
    if not find:
        return list(segments)

    updated = []
    for segment in segments:
        current = getattr(segment, field)
        if current and find in current:
            new_value = current.replace(find, replace)
            change = {field: new_value}
            if field == "text":
                # 원문이 바뀌면 단어별 타임스탬프 정렬이 깨지므로 비운다
                # (부정확한 카라오케 강조보다 강조 없음이 안전).
                change["words"] = []
            updated.append(segment.model_copy(update=change))
        else:
            updated.append(segment)
    return updated


def _normalize_for_filler_match(text: str) -> str:
    stripped = _PUNCTUATION_RE.sub("", text).strip()
    return stripped.lower()


def find_filler_segments(segments: list[Segment], language: str) -> list[str]:
    """세그먼트 텍스트가 필러워드 사전과 완전히 일치하는(=문장 전체가 필러워드 단독인) 세그먼트 id 목록."""
    filler_words = FILLER_WORDS_KO if language == "ko" else FILLER_WORDS_EN
    normalized_fillers = {word.lower() for word in filler_words}

    return [
        segment.id
        for segment in segments
        if _normalize_for_filler_match(segment.text) in normalized_fillers
    ]
