import pytest

from app.core.config import Settings
from app.models.schemas import Segment
from app.services.translation_service import (
    LocalTranslator,
    TranslationCancelled,
    _already_in_target_language,
    get_translator,
    translate_segments,
)


class FakeTranslator:
    def __init__(self, mapping: dict[str, str]):
        self._mapping = mapping
        self.received_direction = None
        self.batches: list[list[str]] = []

    def translate(self, texts, direction):
        self.received_direction = direction
        self.batches.append(list(texts))
        return [self._mapping[text] for text in texts]


def test_translate_segments_fills_translation_field():
    segments = [
        Segment(id="1", start=0.0, end=1.0, text="안녕하세요"),
        Segment(id="2", start=1.0, end=2.0, text="반갑습니다"),
    ]
    translator = FakeTranslator({"안녕하세요": "Hello", "반갑습니다": "Nice to meet you"})

    result = translate_segments(segments, direction="ko->en", translator=translator)

    assert result[0].translation == "Hello"
    assert result[1].translation == "Nice to meet you"
    assert translator.received_direction == "ko->en"
    # original segments must stay untouched (immutability)
    assert segments[0].translation is None


def test_translate_segments_processes_in_batches_and_reports_progress():
    segments = [
        Segment(id=str(i), start=float(i), end=float(i + 1), text=f"문장{i}") for i in range(5)
    ]
    translator = FakeTranslator({f"문장{i}": f"trans{i}" for i in range(5)})
    progress_calls = []

    result = translate_segments(
        segments,
        direction="ko->en",
        translator=translator,
        on_progress=progress_calls.append,
        batch_size=2,
    )

    assert [s.translation for s in result] == ["trans0", "trans1", "trans2", "trans3", "trans4"]
    assert translator.batches == [["문장0", "문장1"], ["문장2", "문장3"], ["문장4"]]
    assert progress_calls == [pytest.approx(0.4), pytest.approx(0.8), pytest.approx(1.0)]


def test_translate_segments_skips_segments_already_in_target_language_ko():
    segments = [
        Segment(id="1", start=0.0, end=1.0, text="Hello there"),
        Segment(id="2", start=1.0, end=2.0, text="이미 한국어입니다"),
    ]
    translator = FakeTranslator({"Hello there": "안녕하세요"})

    result = translate_segments(segments, direction="en->ko", translator=translator)

    assert result[0].translation == "안녕하세요"
    assert result[1].translation == "이미 한국어입니다"
    assert translator.batches == [["Hello there"]]


def test_translate_segments_skips_segments_already_in_target_language_en():
    segments = [
        Segment(id="1", start=0.0, end=1.0, text="안녕하세요"),
        Segment(id="2", start=1.0, end=2.0, text="This is already English"),
    ]
    translator = FakeTranslator({"안녕하세요": "Hello"})

    result = translate_segments(segments, direction="ko->en", translator=translator)

    assert result[0].translation == "Hello"
    assert result[1].translation == "This is already English"
    assert translator.batches == [["안녕하세요"]]


def test_translate_segments_preserves_order_when_skipping_mixed():
    segments = [
        Segment(id="1", start=0.0, end=1.0, text="already english text"),
        Segment(id="2", start=1.0, end=2.0, text="안녕하세요"),
        Segment(id="3", start=2.0, end=3.0, text="반갑습니다"),
    ]
    translator = FakeTranslator({"안녕하세요": "Hello", "반갑습니다": "Nice to meet you"})

    result = translate_segments(segments, direction="ko->en", translator=translator)

    assert [s.translation for s in result] == [
        "already english text",
        "Hello",
        "Nice to meet you",
    ]


def test_translate_segments_skips_symbol_only_text():
    segments = [Segment(id="1", start=0.0, end=1.0, text="...")]
    translator = FakeTranslator({})

    result = translate_segments(segments, direction="ko->en", translator=translator)

    assert result[0].translation == "..."
    assert translator.batches == []


def test_translate_segments_empty_list_returns_empty():
    result = translate_segments([], direction="ko->en", translator=FakeTranslator({}))

    assert result == []


def test_translate_segments_raises_when_cancelled_before_first_batch():
    segments = [Segment(id="1", start=0.0, end=1.0, text="안녕하세요")]
    translator = FakeTranslator({"안녕하세요": "Hello"})

    with pytest.raises(TranslationCancelled):
        translate_segments(
            segments, direction="ko->en", translator=translator, should_cancel=lambda: True
        )


def test_translate_segments_stops_between_batches_when_cancelled():
    segments = [
        Segment(id=str(i), start=float(i), end=float(i + 1), text=f"문장{i}") for i in range(5)
    ]
    translator = FakeTranslator({f"문장{i}": f"trans{i}" for i in range(5)})
    calls = {"n": 0}

    def should_cancel() -> bool:
        calls["n"] += 1
        return calls["n"] > 1  # let the first batch through, cancel before the second

    with pytest.raises(TranslationCancelled):
        translate_segments(
            segments,
            direction="ko->en",
            translator=translator,
            batch_size=2,
            should_cancel=should_cancel,
        )

    assert translator.batches == [["문장0", "문장1"]]


class FakeScoringTranslator:
    def __init__(self, mapping: dict[str, tuple[str, float | None]]):
        self._mapping = mapping

    def translate(self, texts, direction):
        return [self._mapping[text][0] for text in texts]

    def translate_with_scores(self, texts, direction):
        translations = [self._mapping[text][0] for text in texts]
        scores = [self._mapping[text][1] for text in texts]
        return translations, scores


def test_translate_segments_flags_relatively_low_score_as_check():
    segments = [
        Segment(id=str(i), start=float(i), end=float(i + 1), text=f"문장{i}") for i in range(6)
    ]
    # five very similar high scores, one clear outlier -> should be flagged
    mapping = {
        "문장0": ("t0", -0.1),
        "문장1": ("t1", -0.12),
        "문장2": ("t2", -0.11),
        "문장3": ("t3", -0.13),
        "문장4": ("t4", -0.1),
        "문장5": ("t5", -3.0),
    }
    translator = FakeScoringTranslator(mapping)

    result = translate_segments(segments, direction="ko->en", translator=translator)

    qualities = {s.id: s.translation_quality for s in result}
    assert qualities["5"] == "check"
    assert result[-1].translation_quality_reason is not None
    for i in range(5):
        assert qualities[str(i)] == "good"


def test_translate_segments_quality_none_when_translator_has_no_scores():
    segments = [Segment(id="1", start=0.0, end=1.0, text="안녕하세요")]
    translator = FakeTranslator({"안녕하세요": "Hello"})

    result = translate_segments(segments, direction="ko->en", translator=translator)

    assert result[0].translation_quality is None
    assert result[0].translation_quality_reason is None


def test_already_in_target_language_detects_korean():
    assert _already_in_target_language("이미 한국어입니다", "ko") is True
    assert _already_in_target_language("Hello there", "ko") is False


def test_already_in_target_language_detects_english():
    assert _already_in_target_language("This is English", "en") is True
    assert _already_in_target_language("안녕하세요", "en") is False


def test_already_in_target_language_uses_majority_for_code_switched_text():
    # mostly Korean with one English loanword embedded
    assert _already_in_target_language("오늘 정말 fun 했어요 진짜로", "ko") is True
    # mostly English with one Korean word embedded
    assert _already_in_target_language("I think 진짜 this is great", "en") is True


def test_already_in_target_language_treats_symbol_only_text_as_already_done():
    assert _already_in_target_language("... !!", "ko") is True
    assert _already_in_target_language("", "en") is True


def test_get_translator_local_returns_local_translator():
    translator = get_translator("local", Settings(translation_api_key=None))

    assert translator.__class__.__name__ == "LocalTranslator"


def test_local_translator_model_dir_includes_direction_and_model_name(tmp_path):
    translator = LocalTranslator(cache_dir=tmp_path)

    assert (
        translator._model_dir("ko->en", "Helsinki-NLP/opus-mt-ko-en")
        == tmp_path / "ko_to_en__Helsinki-NLP__opus-mt-ko-en"
    )


def test_local_translator_model_dir_changes_when_model_name_changes(tmp_path):
    translator = LocalTranslator(cache_dir=tmp_path)

    old_dir = translator._model_dir("en->ko", "Helsinki-NLP/opus-mt-tc-big-en-ko")
    new_dir = translator._model_dir("en->ko", "facebook/nllb-200-distilled-600M")

    assert old_dir != new_dir


def test_local_translator_is_cached_false_when_model_dir_missing(tmp_path):
    translator = LocalTranslator(cache_dir=tmp_path)

    assert translator.is_cached("ko->en") is False


def test_local_translator_is_cached_true_when_model_dir_exists(tmp_path):
    translator = LocalTranslator(cache_dir=tmp_path)
    translator._model_dir("ko->en", "Helsinki-NLP/opus-mt-ko-en").mkdir(parents=True)

    assert translator.is_cached("ko->en") is True


def test_local_translator_translate_of_empty_list_needs_no_model(tmp_path):
    translator = LocalTranslator(cache_dir=tmp_path)

    assert translator.translate([], direction="ko->en") == []


def test_get_translator_api_without_key_raises():
    settings = Settings(translation_api_key=None)

    with pytest.raises(ValueError, match="TRANSLATION_API_KEY"):
        get_translator("api", settings)


def test_get_translator_api_with_key_returns_api_translator():
    settings = Settings(translation_api_key="sk-test")

    translator = get_translator("api", settings)

    assert translator.__class__.__name__ == "ApiTranslator"


def test_get_translator_unknown_engine_raises():
    with pytest.raises(ValueError, match="알 수 없는"):
        get_translator("carrier-pigeon", Settings(translation_api_key=None))
