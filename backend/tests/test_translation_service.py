import httpx
import pytest

from app.core.config import Settings
from app.models.schemas import Segment
from app.services import translation_service
from app.services.translation_service import (
    ApiTranslator,
    TranslationCancelled,
    _build_prompt,
    get_translator,
    translate_segments,
)


class FakeTranslator:
    def __init__(self, mapping: dict[str, str], context: str = ""):
        self._mapping = mapping
        self._context = context
        self.batches: list[list[str]] = []
        self.glossaries: list[dict[str, str] | None] = []
        self.contexts: list[str | None] = []
        self.windows_before: list[list[str] | None] = []
        self.windows_after: list[list[str] | None] = []
        self.context_calls: list[list[str]] = []

    def translate_with_correction(
        self, texts, glossary=None, context=None, window_before=None, window_after=None
    ):
        self.batches.append(list(texts))
        self.glossaries.append(glossary)
        self.contexts.append(context)
        self.windows_before.append(window_before)
        self.windows_after.append(window_after)
        return list(texts), [self._mapping[text] for text in texts]

    def extract_context(self, texts):
        self.context_calls.append(list(texts))
        return self._context


def test_translate_segments_fills_translation_field():
    segments = [
        Segment(id="1", start=0.0, end=1.0, text="안녕하세요"),
        Segment(id="2", start=1.0, end=2.0, text="반갑습니다"),
    ]
    translator = FakeTranslator({"안녕하세요": "Hello", "반갑습니다": "Nice to meet you"})

    result = translate_segments(segments, translator=translator)

    assert result[0].translation == "Hello"
    assert result[1].translation == "Nice to meet you"
    # original segments must stay untouched (immutability)
    assert segments[0].translation is None


def test_translate_segments_handles_mixed_language_batch():
    # the API auto-detects each line's language and translates into the
    # other one, so a batch can freely mix Korean and English lines - the
    # local code makes no language judgment of its own.
    segments = [
        Segment(id="1", start=0.0, end=1.0, text="안녕하세요"),
        Segment(id="2", start=1.0, end=2.0, text="Hello there"),
    ]
    translator = FakeTranslator({"안녕하세요": "Hello", "Hello there": "안녕하세요"})

    result = translate_segments(segments, translator=translator)

    assert result[0].translation == "Hello"
    assert result[1].translation == "안녕하세요"
    assert translator.batches == [["안녕하세요", "Hello there"]]


def test_translate_segments_sends_symbol_only_text_to_translator_too():
    # no local skip heuristic - even symbol-only lines are sent, and the
    # prompt instructs the model to leave them unchanged.
    segments = [Segment(id="1", start=0.0, end=1.0, text="...")]
    translator = FakeTranslator({"...": "..."})

    result = translate_segments(segments, translator=translator)

    assert result[0].translation == "..."
    assert translator.batches == [["..."]]


def test_translate_segments_processes_in_batches_and_reports_progress():
    segments = [
        Segment(id=str(i), start=float(i), end=float(i + 1), text=f"문장{i}") for i in range(5)
    ]
    translator = FakeTranslator({f"문장{i}": f"trans{i}" for i in range(5)})
    progress_calls = []

    result = translate_segments(
        segments,
        translator=translator,
        on_progress=progress_calls.append,
        batch_size=2,
    )

    assert [s.translation for s in result] == ["trans0", "trans1", "trans2", "trans3", "trans4"]
    assert translator.batches == [["문장0", "문장1"], ["문장2", "문장3"], ["문장4"]]
    assert progress_calls == [pytest.approx(0.4), pytest.approx(0.8), pytest.approx(1.0)]


class SplittingRetryTranslator:
    """Simulates the API returning malformed JSON (e.g. an unescaped quote
    inside a translated line) whenever more than one line is requested at
    once, succeeding only once the batch has been split down to one line."""

    def __init__(self, mapping: dict[str, str]):
        self._mapping = mapping
        self.batches: list[list[str]] = []

    def translate_with_correction(
        self, texts, glossary=None, context=None, window_before=None, window_after=None
    ):
        self.batches.append(list(texts))
        if len(texts) > 1:
            raise ValueError("simulated malformed JSON for a multi-line batch")
        return list(texts), [self._mapping[text] for text in texts]

    def extract_context(self, texts):
        return ""


def test_translate_segments_retries_as_smaller_batches_on_parse_failure():
    segments = [
        Segment(id=str(i), start=float(i), end=float(i + 1), text=f"문장{i}") for i in range(4)
    ]
    translator = SplittingRetryTranslator({f"문장{i}": f"trans{i}" for i in range(4)})

    result = translate_segments(segments, translator=translator, batch_size=4)

    assert [s.translation for s in result] == ["trans0", "trans1", "trans2", "trans3"]
    # the initial 4-line batch failed and was recursively halved (through a
    # failing 2-line attempt) down to single-line calls, each of which
    # eventually succeeded
    assert translator.batches[0] == ["문장0", "문장1", "문장2", "문장3"]
    single_line_batches = [batch for batch in translator.batches if len(batch) == 1]
    assert sorted(batch[0] for batch in single_line_batches) == ["문장0", "문장1", "문장2", "문장3"]


def test_translate_segments_empty_list_returns_empty():
    result = translate_segments([], translator=FakeTranslator({}))

    assert result == []


def test_translate_segments_raises_when_cancelled_before_first_batch():
    segments = [Segment(id="1", start=0.0, end=1.0, text="안녕하세요")]
    translator = FakeTranslator({"안녕하세요": "Hello"})

    with pytest.raises(TranslationCancelled):
        translate_segments(segments, translator=translator, should_cancel=lambda: True)


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
            translator=translator,
            batch_size=2,
            should_cancel=should_cancel,
        )

    assert translator.batches == [["문장0", "문장1"]]


def test_translate_segments_applies_stt_correction_to_text_field():
    segments = [Segment(id="1", start=0.0, end=1.0, text="안뇽하세요")]

    class CorrectingTranslator:
        def translate_with_correction(
            self, texts, glossary=None, context=None, window_before=None, window_after=None
        ):
            return ["안녕하세요" for _ in texts], ["Hello" for _ in texts]

        def extract_context(self, texts):
            return ""

    result = translate_segments(segments, translator=CorrectingTranslator())

    assert result[0].text == "안녕하세요"
    assert result[0].translation == "Hello"
    # original segment must stay untouched (immutability)
    assert segments[0].text == "안뇽하세요"


def test_translate_segments_quality_is_none_for_freshly_translated_segments():
    segments = [Segment(id="1", start=0.0, end=1.0, text="안녕하세요")]
    translator = FakeTranslator({"안녕하세요": "Hello"})

    result = translate_segments(segments, translator=translator)

    assert result[0].translation_quality is None
    assert result[0].translation_quality_reason is None


def test_translate_segments_passes_glossary_through_to_translator():
    # glossary enforcement is no longer a local string-replace - it's sent
    # to the LLM as a prompt instruction, so translate_segments just has to
    # pass it through untouched.
    segments = [Segment(id="1", start=0.0, end=1.0, text="Zamak을 소개합니다")]
    translator = FakeTranslator({"Zamak을 소개합니다": "I'll introduce Zamak Corp"})

    result = translate_segments(
        segments,
        translator=translator,
        glossary={"Zamak": "Zamak Corp"},
    )

    assert result[0].translation == "I'll introduce Zamak Corp"
    assert translator.glossaries == [{"Zamak": "Zamak Corp"}]


def test_translate_segments_without_glossary_passes_none():
    segments = [Segment(id="1", start=0.0, end=1.0, text="안녕하세요")]
    translator = FakeTranslator({"안녕하세요": "Hello"})

    translate_segments(segments, translator=translator, glossary=None)

    assert translator.glossaries == [None]


def test_translate_segments_reuses_translation_memory_without_calling_translator():
    segments = [
        Segment(id="1", start=0.0, end=1.0, text="안녕하세요"),
        Segment(id="2", start=1.0, end=2.0, text="처음 보는 문장"),
    ]
    translator = FakeTranslator({"처음 보는 문장": "A brand new sentence"})

    result = translate_segments(
        segments,
        translator=translator,
        translation_memory={"안녕하세요": "Hello (cached)"},
    )

    assert result[0].translation == "Hello (cached)"
    assert result[0].translation_quality == "good"
    assert result[1].translation == "A brand new sentence"
    # only the uncached segment should have been sent to the translator
    assert translator.batches == [["처음 보는 문장"]]


class TestContextAndWindow:
    """File-level topic/proper-noun context (extracted once) plus a
    sliding window of neighboring lines around each batch - added so
    nuance decisions aren't blind to what's just outside a batch's own
    boundaries, without resending the whole file on every batch call.
    """

    def test_extract_context_called_once_across_multiple_batches(self):
        segments = [
            Segment(id=str(i), start=float(i), end=float(i + 1), text=f"문장{i}") for i in range(5)
        ]
        translator = FakeTranslator({f"문장{i}": f"trans{i}" for i in range(5)})

        translate_segments(segments, translator=translator, batch_size=2)

        assert len(translator.context_calls) == 1
        assert translator.context_calls[0] == [f"문장{i}" for i in range(5)]

    def test_context_result_is_passed_to_every_batch(self):
        segments = [
            Segment(id=str(i), start=float(i), end=float(i + 1), text=f"문장{i}") for i in range(5)
        ]
        translator = FakeTranslator(
            {f"문장{i}": f"trans{i}" for i in range(5)}, context="topic: interview"
        )

        translate_segments(segments, translator=translator, batch_size=2)

        assert translator.contexts == ["topic: interview"] * 3  # 3 batches for 5 items / size 2

    def test_extract_context_skipped_when_everything_is_cached(self):
        segments = [Segment(id="1", start=0.0, end=1.0, text="안녕하세요")]
        translator = FakeTranslator({})

        translate_segments(
            segments, translator=translator, translation_memory={"안녕하세요": "Hello (cached)"}
        )

        assert translator.context_calls == []

    def test_sliding_window_includes_neighbors_outside_the_batch(self, monkeypatch):
        monkeypatch.setattr(translation_service, "_WINDOW_SIZE", 1)
        segments = [
            Segment(id=str(i), start=float(i), end=float(i + 1), text=f"문장{i}") for i in range(6)
        ]
        translator = FakeTranslator({f"문장{i}": f"trans{i}" for i in range(6)})

        translate_segments(segments, translator=translator, batch_size=2)

        # batch 0: [문장0, 문장1] -> no preceding neighbor, one following (문장2)
        assert translator.windows_before[0] == []
        assert translator.windows_after[0] == ["문장2"]
        # batch 1: [문장2, 문장3] -> one on each side
        assert translator.windows_before[1] == ["문장1"]
        assert translator.windows_after[1] == ["문장4"]
        # batch 2: [문장4, 문장5] -> one preceding, no following
        assert translator.windows_before[2] == ["문장3"]
        assert translator.windows_after[2] == []


def test_build_prompt_includes_numbered_lines_and_item_count():
    prompt = _build_prompt(["안녕", "hello"], glossary=None)

    assert "1. 안녕" in prompt
    assert "2. hello" in prompt
    assert "exactly 2 entries" in prompt


def test_build_prompt_includes_glossary_terms_when_given():
    prompt = _build_prompt(["문장"], glossary={"Zamak": "Zamak Corp"})

    assert "Zamak → Zamak Corp" in prompt


def test_build_prompt_omits_glossary_block_when_empty():
    prompt_none = _build_prompt(["문장"], glossary=None)
    prompt_empty = _build_prompt(["문장"], glossary={})

    assert "Whenever one of these source terms" not in prompt_none
    assert "Whenever one of these source terms" not in prompt_empty


def test_build_prompt_includes_context_when_given():
    prompt = _build_prompt(["문장"], glossary=None, context="Topic: a music interview")

    assert "Topic: a music interview" in prompt


def test_build_prompt_omits_context_block_when_absent():
    prompt = _build_prompt(["문장"], glossary=None, context=None)

    assert "Background context" not in prompt


def test_build_prompt_includes_window_lines_marked_context_only():
    prompt = _build_prompt(
        ["문장3"],
        glossary=None,
        window_before=["문장1", "문장2"],
        window_after=["문장4"],
    )

    assert "문장1" in prompt
    assert "문장2" in prompt
    assert "문장4" in prompt
    assert "do NOT translate" in prompt


def test_build_prompt_omits_window_block_when_absent():
    prompt = _build_prompt(["문장"], glossary=None)

    assert "context only" not in prompt


class TestExtractContext:
    def test_returns_empty_string_for_no_texts(self):
        translator = ApiTranslator(api_key="test-key")

        assert translator.extract_context([]) == ""

    def test_returns_model_response_content(self, monkeypatch):
        monkeypatch.setattr(
            translation_service.httpx,
            "post",
            lambda *a, **k: _FakeResponse(200, _chat_response("  Topic: a music interview.  ")),
        )

        translator = ApiTranslator(api_key="test-key")
        result = translator.extract_context(["안녕", "hello"])

        assert result == "Topic: a music interview."


def test_get_translator_without_key_raises():
    settings = Settings(translation_api_key=None)

    with pytest.raises(ValueError, match="TRANSLATION_API_KEY"):
        get_translator(settings)


def test_get_translator_with_key_returns_api_translator():
    settings = Settings(translation_api_key="sk-test")

    translator = get_translator(settings)

    assert translator.__class__.__name__ == "ApiTranslator"


def test_get_translator_with_session_token_ignores_missing_static_key():
    settings = Settings(translation_api_key=None, hosted_relay_base_url="https://relay.example/v1")

    translator = get_translator(settings, session_token="user-jwt")

    assert translator.__class__.__name__ == "ApiTranslator"
    assert translator._api_key == "user-jwt"
    assert translator._base_url == "https://relay.example/v1"


def test_get_translator_prefers_session_token_over_static_key():
    settings = Settings(translation_api_key="sk-static")

    translator = get_translator(settings, session_token="user-jwt")

    assert translator._api_key == "user-jwt"


class _FakeResponse:
    def __init__(self, status_code: int, body: dict | None = None, headers: dict | None = None):
        self.status_code = status_code
        self._body = body or {}
        self.headers = headers or {}

    def json(self):
        return self._body

    def raise_for_status(self):
        if self.status_code >= 400:
            raise httpx.HTTPStatusError(
                f"status {self.status_code}", request=None, response=self
            )


def _chat_response(text: str) -> dict:
    return {"choices": [{"message": {"content": text}}]}


class TestApiTranslatorRetry:
    def test_retries_on_429_then_succeeds(self, monkeypatch):
        monkeypatch.setattr(translation_service.time, "sleep", lambda _seconds: None)
        responses = [
            _FakeResponse(429, headers={"Retry-After": "0"}),
            _FakeResponse(429, headers={"Retry-After": "0"}),
            _FakeResponse(200, _chat_response('{"items": [{"text": "안녕", "translation": "Hi"}]}')),
        ]
        calls = {"n": 0}

        def fake_post(*args, **kwargs):
            response = responses[calls["n"]]
            calls["n"] += 1
            return response

        monkeypatch.setattr(translation_service.httpx, "post", fake_post)

        translator = ApiTranslator(api_key="test-key")
        corrected, translated = translator.translate_with_correction(["안녕"])

        assert corrected == ["안녕"]
        assert translated == ["Hi"]
        assert calls["n"] == 3

    def test_gives_up_after_max_attempts(self, monkeypatch):
        monkeypatch.setattr(translation_service.time, "sleep", lambda _seconds: None)
        calls = {"n": 0}

        def fake_post(*args, **kwargs):
            calls["n"] += 1
            return _FakeResponse(429)

        monkeypatch.setattr(translation_service.httpx, "post", fake_post)

        translator = ApiTranslator(api_key="test-key")
        with pytest.raises(httpx.HTTPStatusError):
            translator.translate_with_correction(["안녕"])

        assert calls["n"] == translation_service._MAX_ATTEMPTS

    def test_does_not_retry_non_retryable_status(self, monkeypatch):
        calls = {"n": 0}

        def fake_post(*args, **kwargs):
            calls["n"] += 1
            return _FakeResponse(400)

        monkeypatch.setattr(translation_service.httpx, "post", fake_post)

        translator = ApiTranslator(api_key="test-key")
        with pytest.raises(httpx.HTTPStatusError):
            translator.translate_with_correction(["안녕"])

        assert calls["n"] == 1
