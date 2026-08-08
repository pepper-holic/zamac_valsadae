from app.models.schemas import Segment
from app.services.readability_service import apply_readability, assess_readability


def test_normal_segment_is_flagged_good():
    segment = Segment(id="1", start=0.0, end=2.0, text="짧고 적당한 문장입니다")

    flag, reason = assess_readability(segment, use_translation=False)

    assert flag == "good"
    assert reason is None


def test_segment_over_cps_threshold_is_flagged_check():
    # 40자 / 1초 = 40 CPS > 17 CPS 기준
    segment = Segment(id="1", start=0.0, end=1.0, text="가" * 40)

    flag, reason = assess_readability(segment, use_translation=False)

    assert flag == "check"
    assert "초당" in reason


def test_segment_over_line_length_is_flagged_check():
    segment = Segment(id="1", start=0.0, end=5.0, text="a" * 43)

    flag, reason = assess_readability(segment, use_translation=False)

    assert flag == "check"
    assert "글자" in reason


def test_segment_shorter_than_minimum_duration_is_flagged_check():
    segment = Segment(id="1", start=0.0, end=0.5, text="짧다")

    flag, reason = assess_readability(segment, use_translation=False)

    assert flag == "check"
    assert "지속시간" in reason


def test_segment_longer_than_maximum_duration_is_flagged_check():
    segment = Segment(id="1", start=0.0, end=8.0, text="너무 길게 떠있는 자막")

    flag, reason = assess_readability(segment, use_translation=False)

    assert flag == "check"
    assert "지속시간" in reason


def test_uses_translation_text_when_requested():
    segment = Segment(id="1", start=0.0, end=1.0, text="ok", translation="a" * 40)

    flag, reason = assess_readability(segment, use_translation=True)

    assert flag == "check"


def test_empty_text_is_flagged_good():
    segment = Segment(id="1", start=0.0, end=1.0, text="")

    flag, reason = assess_readability(segment, use_translation=False)

    assert flag == "good"
    assert reason is None


def test_apply_readability_sets_flag_and_reason_on_copies():
    segments = [Segment(id="1", start=0.0, end=1.0, text="가" * 40)]

    updated = apply_readability(segments, use_translation=False)

    assert updated[0].readability_flag == "check"
    assert updated[0].readability_reason is not None
    assert segments[0].readability_flag is None  # 원본은 불변
