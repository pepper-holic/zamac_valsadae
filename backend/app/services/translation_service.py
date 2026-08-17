import json
import random
import time
from collections.abc import Callable

import httpx

from app.core.config import Settings
from app.models.schemas import Segment

# Free-tier / shared relay providers (Gemini free tier, in particular) rate
# limit aggressively - without a retry, one batch tripping the limit fails
# the whole translation job even though the request itself was fine.
_MAX_ATTEMPTS = 5
_RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 504}
_BASE_DELAY_SEC = 1.0
_MAX_DELAY_SEC = 30.0

# How many neighboring segments (each side) to include as read-only context
# around a batch, so nuance decisions aren't blind to what's just outside
# the batch's own boundaries.
_WINDOW_SIZE = 6


def _retry_delay_seconds(attempt: int, retry_after_header: str | None) -> float:
    if retry_after_header:
        try:
            return float(retry_after_header)
        except ValueError:
            pass
    delay = min(_BASE_DELAY_SEC * (2**attempt), _MAX_DELAY_SEC)
    return delay + random.uniform(0, delay * 0.25)


class ApiTranslator:
    """Calls an OpenAI-compatible chat endpoint to translate segments.

    Combines STT-error correction and translation into a single call (same
    intent as the manual AI-검수 prompt in review_service.py) instead of a
    separate review pass, so API users get both without a second round trip.
    """

    def __init__(self, api_key: str, base_url: str = "https://api.openai.com/v1"):
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")

    def translate_with_correction(
        self,
        texts: list[str],
        glossary: dict[str, str] | None = None,
        context: str | None = None,
        window_before: list[str] | None = None,
        window_after: list[str] | None = None,
    ) -> tuple[list[str], list[str]]:
        if not texts:
            return [], []

        prompt = _build_prompt(texts, glossary, context, window_before, window_after)

        response = self._post_chat_completion(prompt)
        content = response.json()["choices"][0]["message"]["content"]
        return _parse_json_items(content, expected_count=len(texts))

    def extract_context(self, texts: list[str]) -> str:
        """One cheap call over the whole file's raw text to get a topic
        summary and recurring proper nouns/terms, so every batch call below
        can stay consistent without re-sending the whole file every time.
        """
        if not texts:
            return ""

        prompt = (
            "Below is the full text of a video's subtitles (Korean and/or English, "
            "possibly with STT errors), in order. In 3-5 sentences, note: (1) the "
            "topic/genre of the video, (2) recurring proper nouns, names, or jargon "
            "and how they should be spelled/translated consistently. Be concise - "
            "this will be reused as background context for translating the file in "
            "batches, not shown to an end user. Reply with plain text only, no JSON, "
            "no markdown.\n\n" + "\n".join(texts)
        )
        response = self._post_chat_completion(prompt)
        return response.json()["choices"][0]["message"]["content"].strip()

    def _post_chat_completion(self, prompt: str) -> httpx.Response:
        response: httpx.Response | None = None
        for attempt in range(_MAX_ATTEMPTS):
            response = httpx.post(
                f"{self._base_url}/chat/completions",
                headers={"Authorization": f"Bearer {self._api_key}"},
                json={
                    "model": "gpt-4o-mini",
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0,
                },
                timeout=60,
            )
            if response.status_code not in _RETRYABLE_STATUS_CODES:
                break
            if attempt < _MAX_ATTEMPTS - 1:
                time.sleep(_retry_delay_seconds(attempt, response.headers.get("Retry-After")))
        response.raise_for_status()
        return response


def _build_prompt(
    texts: list[str],
    glossary: dict[str, str] | None,
    context: str | None = None,
    window_before: list[str] | None = None,
    window_after: list[str] | None = None,
) -> str:
    glossary_block = ""
    if glossary:
        terms = "\n".join(f"- {source} → {target}" for source, target in glossary.items() if source)
        if terms:
            glossary_block = (
                "\nWhenever one of these source terms appears, use exactly the given "
                f"translation for it:\n{terms}\n"
            )

    context_block = ""
    if context:
        context_block = f"\nBackground context for this video, for consistency:\n{context}\n"

    window_block = ""
    if window_before or window_after:
        parts = []
        if window_before:
            parts.append(
                "Immediately preceding lines, for context only - do NOT translate "
                "or include these in your output:\n"
                + "\n".join(f"- {t}" for t in window_before)
            )
        if window_after:
            parts.append(
                "Immediately following lines, for context only - do NOT translate "
                "or include these in your output:\n"
                + "\n".join(f"- {t}" for t in window_after)
            )
        window_block = "\n" + "\n\n".join(parts) + "\n"

    return (
        "You are correcting speech-to-text output and translating it. This app only "
        "handles Korean and English, so for each numbered line below:\n"
        "1. Detect whether the line is Korean or English. If a line has no "
        "translatable content (symbols only, empty, non-verbal), leave both the "
        "corrected text and translation identical to the original line.\n"
        "2. Fix obvious STT misrecognitions/typos in the source line if you spot any "
        "(keep the same language and meaning - do not rephrase for style). "
        "Leave low-confidence proper nouns/jargon as-is rather than guessing.\n"
        "3. Produce a natural, idiomatic translation into the OTHER of the two "
        "languages (Korean lines translate to English, English lines translate to "
        "Korean). If a line is already a mix of both or already reads naturally in "
        "the other language, use your judgment on the most useful translation.\n"
        "4. Use the surrounding context below (if given) to pick the right nuance - "
        "e.g. a short line like an interjection or a repeated phrase may need a "
        "different translation depending on what comes right before/after it.\n"
        f"{glossary_block}"
        f"{context_block}"
        f"{window_block}\n"
        "Reply with ONLY a JSON object of this exact shape, no markdown fences, no "
        'commentary: {"items": [{"text": "<corrected source>", "translation": '
        '"<translation>"}, ...]}. The items array must have exactly '
        f"{len(texts)} entries, in the same order as the input - the lines to "
        "translate now are:\n\n"
        + "\n".join(f"{index + 1}. {text}" for index, text in enumerate(texts))
    )


def _parse_json_items(content: str, expected_count: int) -> tuple[list[str], list[str]]:
    cleaned = content.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.strip("`")
        cleaned = cleaned.removeprefix("json").strip()
    try:
        parsed = json.loads(cleaned)
        items = parsed["items"]
        texts = [str(item["text"]) for item in items]
        translations = [str(item["translation"]) for item in items]
    except (json.JSONDecodeError, KeyError, TypeError) as exc:
        raise ValueError(f"API translation returned unparseable content: {content!r}") from exc
    if len(items) != expected_count:
        raise ValueError(
            f"API translation returned {len(items)} items, expected {expected_count}"
        )
    return texts, translations


def get_translator(settings: Settings, session_token: str | None = None) -> ApiTranslator:
    # A logged-in session routes through our hosted relay (which holds its
    # own provider key server-side) instead of requiring the user to supply
    # their own TRANSLATION_API_KEY.
    if session_token:
        return ApiTranslator(api_key=session_token, base_url=settings.hosted_relay_base_url)
    if not settings.translation_api_key:
        raise ValueError("번역을 사용하려면 로그인하거나 TRANSLATION_API_KEY 설정이 필요합니다.")
    base_url = settings.translation_api_base_url or "https://api.openai.com/v1"
    return ApiTranslator(api_key=settings.translation_api_key, base_url=base_url)


class TranslationCancelled(Exception):
    """Raised mid-translate when the caller's should_cancel() reports True."""


def _translate_batch_with_retry(
    translator: ApiTranslator,
    batch_texts: list[str],
    glossary: dict[str, str] | None,
    context: str,
    window_before: list[str],
    window_after: list[str],
) -> tuple[list[str], list[str]]:
    """A larger batch gives the API more chances to emit malformed JSON -
    most often an unescaped double quote inside a translated line of
    dialogue breaking the surrounding JSON string. On a parse failure,
    retry as two smaller batches (each with the other half as extra local
    context) instead of failing the whole batch - this isolates whichever
    half (and eventually which single line) is actually causing trouble,
    instead of one bad line taking the rest of the batch down with it.
    """
    try:
        return translator.translate_with_correction(batch_texts, glossary, context, window_before, window_after)
    except ValueError:
        if len(batch_texts) <= 1:
            raise
        mid = len(batch_texts) // 2
        left_texts, right_texts = batch_texts[:mid], batch_texts[mid:]
        left_corrected, left_translations = _translate_batch_with_retry(
            translator, left_texts, glossary, context, window_before, right_texts
        )
        right_corrected, right_translations = _translate_batch_with_retry(
            translator, right_texts, glossary, context, left_texts, window_after
        )
        return left_corrected + right_corrected, left_translations + right_translations


def translate_segments(
    segments: list[Segment],
    translator: ApiTranslator,
    on_progress: Callable[[float], None] | None = None,
    batch_size: int = 24,
    should_cancel: Callable[[], bool] | None = None,
    glossary: dict[str, str] | None = None,
    translation_memory: dict[str, str] | None = None,
) -> list[Segment]:
    if not segments:
        return []

    total = len(segments)
    updated: list[Segment | None] = [None] * total
    pending_indices: list[int] = []
    pending_segments: list[Segment] = []
    tm = translation_memory or {}

    for index, segment in enumerate(segments):
        if segment.text in tm:
            # 이전에 같은 원문을 번역한 적이 있으면 모델 호출 없이 재사용합니다
            # (이미 나온 API 응답을 그대로 재사용하는 것일 뿐, 번역이 필요한지
            # 자체를 판단하는 것은 아님 - 그 판단은 전부 프롬프트를 통해 LLM이 함).
            updated[index] = segment.model_copy(
                update={"translation": tm[segment.text], "translation_quality": "good"}
            )
        else:
            pending_indices.append(index)
            pending_segments.append(segment)

    done_count = total - len(pending_segments)
    if on_progress and done_count:
        on_progress(min(done_count / total, 1.0))

    corrected_text_by_index: dict[int, str] = {}
    translations_by_index: dict[int, str] = {}

    # 배치 하나가 볼 수 있는 문맥은 그 배치 안 문장들뿐이라, 같은 문장이 배치
    # 경계 너머 다른 문맥에서 반복될 때 뉘앙스를 놓칠 수 있다. 파일 전체를
    # 매번 보내는 대신 (1) 파일당 1회만 도는 저렴한 주제/고유명사 요약과
    # (2) 배치 앞뒤 몇 문장씩의 슬라이딩 윈도우로 그 손실을 보완한다.
    context = translator.extract_context([segment.text for segment in segments]) if pending_segments else ""

    for start in range(0, len(pending_segments), batch_size):
        if should_cancel is not None and should_cancel():
            raise TranslationCancelled("번역이 취소되었습니다.")
        batch = pending_segments[start : start + batch_size]
        batch_indices = pending_indices[start : start + batch_size]
        batch_texts = [segment.text for segment in batch]
        window_before = [s.text for s in pending_segments[max(0, start - _WINDOW_SIZE) : start]]
        window_after = [
            s.text for s in pending_segments[start + batch_size : start + batch_size + _WINDOW_SIZE]
        ]
        # STT 오탈자 교정 + 번역을 한 번의 호출로 함께 받는다 (수동 AI 검수
        # 패키지 왕복을 없애기 위함) - review_service.py의 검수 프롬프트와
        # 같은 의도를 번역 API 요청에 합쳐 넣은 것. 용어집 강제 치환도 로컬
        # 후처리가 아니라 프롬프트에 지시사항으로 실어서 LLM이 반영하게 한다.
        corrected_texts, translations = _translate_batch_with_retry(
            translator, batch_texts, glossary, context, window_before, window_after
        )
        for index, corrected_text, translation in zip(batch_indices, corrected_texts, translations):
            corrected_text_by_index[index] = corrected_text
            translations_by_index[index] = translation
        done_count += len(batch)
        if on_progress:
            on_progress(min(done_count / total, 1.0))

    for index in pending_indices:
        segment = segments[index]
        updated[index] = segment.model_copy(
            update={
                "text": corrected_text_by_index[index],
                "translation": translations_by_index[index],
            }
        )

    return updated  # type: ignore[return-value]
