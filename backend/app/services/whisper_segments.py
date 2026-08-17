"""Post-processing for raw Whisper segments: quality flags, long-segment
splitting, and hallucinated-repeat collapsing.

Split out of whisper_service.py: everything here operates on already-decoded
segments and has no knowledge of models, devices, or language detection.
"""

import re
import uuid

from app.models.schemas import Segment, Word
from app.services.readability_service import MAX_DURATION_SEC, MIN_DURATION_SEC

# Same default thresholds openai-whisper itself uses to decide whether a
# decoded segment is unreliable enough to warrant a fallback re-decode.
_NO_SPEECH_THRESHOLD = 0.6
_LOGPROB_THRESHOLD = -1.0
_COMPRESSION_RATIO_THRESHOLD = 2.4


def _assess_transcription_quality(raw_segment: object) -> tuple[str, str | None]:
    reasons = []

    no_speech_prob = getattr(raw_segment, "no_speech_prob", None)
    if no_speech_prob is not None and no_speech_prob > _NO_SPEECH_THRESHOLD:
        reasons.append("무음/배경음일 가능성이 높습니다")

    avg_logprob = getattr(raw_segment, "avg_logprob", None)
    if avg_logprob is not None and avg_logprob < _LOGPROB_THRESHOLD:
        reasons.append("인식 신뢰도가 낮습니다")

    compression_ratio = getattr(raw_segment, "compression_ratio", None)
    if compression_ratio is not None and compression_ratio > _COMPRESSION_RATIO_THRESHOLD:
        reasons.append("반복되거나 비정상적인 패턴이 감지되었습니다")

    if reasons:
        return "check", " / ".join(reasons)
    return "good", None


def _extract_words(raw_segment: object) -> list[Word]:
    raw_words = getattr(raw_segment, "words", None)
    if not raw_words:
        return []
    return [
        Word(text=raw_word.word.strip(), start=float(raw_word.start), end=float(raw_word.end))
        for raw_word in raw_words
    ]


# Split long segments back down to the same threshold `readability_service`
# already flags as "too long" - otherwise every run-on sentence Whisper
# decodes as one segment lands in the review list needing a manual split.
_LEADING_PUNCTUATION = set(",.!?;:)]}'\"”’")


def _join_words(words: list[Word]) -> str:
    parts: list[str] = []
    for word in words:
        text = word.text
        if parts and text and text[0] in _LEADING_PUNCTUATION:
            parts[-1] = parts[-1] + text
        elif text:
            parts.append(text)
    return " ".join(parts).strip()


def _split_long_segment(segment: Segment, max_duration: float, min_duration: float) -> list[Segment]:
    duration = segment.end - segment.start
    if duration <= max_duration or len(segment.words) < 2:
        return [segment]

    words = segment.words
    mid_time = (segment.start + segment.end) / 2

    # Split at the word boundary with the longest silence gap (a natural
    # pause), preferring whichever such gap sits closest to the midpoint so
    # both halves come out reasonably balanced rather than a tiny sliver.
    best_index: int | None = None
    best_score: tuple[float, float] | None = None
    for i in range(len(words) - 1):
        left_duration = words[i].end - segment.start
        right_duration = segment.end - words[i + 1].start
        if left_duration < min_duration or right_duration < min_duration:
            continue
        gap = words[i + 1].start - words[i].end
        boundary_time = (words[i].end + words[i + 1].start) / 2
        score = (gap, -abs(boundary_time - mid_time))
        if best_score is None or score > best_score:
            best_score = score
            best_index = i

    if best_index is None:
        return [segment]

    left_words = words[: best_index + 1]
    right_words = words[best_index + 1 :]
    left = segment.model_copy(
        update={
            "id": uuid.uuid4().hex,
            "start": segment.start,
            "end": left_words[-1].end,
            "text": _join_words(left_words),
            "words": left_words,
        }
    )
    right = segment.model_copy(
        update={
            "id": uuid.uuid4().hex,
            "start": right_words[0].start,
            "end": segment.end,
            "text": _join_words(right_words),
            "words": right_words,
        }
    )
    return _split_long_segment(left, max_duration, min_duration) + _split_long_segment(
        right, max_duration, min_duration
    )


def _split_long_segments(segments: list[Segment]) -> list[Segment]:
    result: list[Segment] = []
    for segment in segments:
        result.extend(_split_long_segment(segment, MAX_DURATION_SEC, MIN_DURATION_SEC))
    return result


# Whisper occasionally hallucinates the same sentence several times in a row
# as separate back-to-back segments - a well-known repetition failure mode,
# distinct from genuine repeated speech (which doesn't usually recur this
# fast). Collapsing them into one segment (rather than leaving the reader to
# spot and delete N duplicate lines) is safe because dropping a merged
# segment's transcription_quality to "check" still surfaces it for review if
# the repeat turns out to be real.
_MAX_REPEAT_MERGE_GAP_SEC = 2.5
_REPEATED_TEXT_QUALITY_REASON = "동일 문장이 반복 인식되어 병합되었습니다 - 실제 반복 발화인지 확인해 주세요"


def _normalize_for_repeat_check(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip().lower()


def _collapse_repeated_segments(segments: list[Segment]) -> list[Segment]:
    if not segments:
        return segments

    collapsed: list[Segment] = [segments[0]]
    for segment in segments[1:]:
        previous = collapsed[-1]
        is_repeat = (
            bool(previous.text)
            and _normalize_for_repeat_check(segment.text) == _normalize_for_repeat_check(previous.text)
            and segment.start - previous.end <= _MAX_REPEAT_MERGE_GAP_SEC
        )
        if is_repeat:
            collapsed[-1] = previous.model_copy(
                update={
                    "end": segment.end,
                    "words": previous.words + segment.words,
                    "transcription_quality": "check",
                    "transcription_quality_reason": _REPEATED_TEXT_QUALITY_REASON,
                }
            )
        else:
            collapsed.append(segment)
    return collapsed
