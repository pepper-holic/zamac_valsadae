import re
import statistics
from collections.abc import Callable
from pathlib import Path
from typing import NamedTuple, Protocol

import httpx

from app.core.config import Settings
from app.models.schemas import Segment, TranslationDirection

class LocalModelConfig(NamedTuple):
    model_name: str
    src_lang: str | None = None  # set on the tokenizer for multilingual models
    target_prefix: str | None = None  # CTranslate2 decoder-side language tag


_LOCAL_MODEL_CONFIGS: dict[TranslationDirection, LocalModelConfig] = {
    # Plain bilingual MarianMT model - no language tag needed.
    "ko->en": LocalModelConfig(model_name="Helsinki-NLP/opus-mt-ko-en"),
    # Helsinki-NLP has no direct bilingual en->ko model; its multi-target
    # tc-big variant requires an undocumented/unreliable ">>kor<<" tag and
    # produced garbled output in testing. NLLB-200 is multilingual with a
    # well-defined language-token API (kor_Hang) and gave correct, natural
    # translations instead.
    "en->ko": LocalModelConfig(
        model_name="facebook/nllb-200-distilled-600M",
        src_lang="eng_Latn",
        target_prefix="kor_Hang",
    ),
}

_LANGUAGE_NAMES = {"ko": "Korean", "en": "English"}

_HANGUL_PATTERN = re.compile(r"[가-힣ᄀ-ᇿ㄰-㆏]")
_LATIN_PATTERN = re.compile(r"[A-Za-z]")


def _already_in_target_language(text: str, target_lang: str) -> bool:
    """Heuristic for mixed-language videos: skip re-translating a segment that
    already looks like it's in the target language (e.g. a Korean aside inside
    an otherwise-English video), based on Hangul vs. Latin letter ratio.
    """
    hangul_count = len(_HANGUL_PATTERN.findall(text))
    latin_count = len(_LATIN_PATTERN.findall(text))
    letters = hangul_count + latin_count
    if letters == 0:
        return True  # no alphabetic content worth translating
    if target_lang == "ko":
        return hangul_count / letters >= 0.5
    if target_lang == "en":
        return latin_count / letters >= 0.5
    return False


class Translator(Protocol):
    def translate(self, texts: list[str], direction: TranslationDirection) -> list[str]: ...


class LocalTranslator:
    """Runs local translation models via CTranslate2 (int8) for fast CPU inference.

    Models are converted from the original transformers checkpoint once and
    cached on disk under `cache_dir`; subsequent runs load the cached
    CTranslate2 model directly instead of re-converting.
    """

    def __init__(self, cache_dir: Path, on_stage: Callable[[str], None] | None = None):
        self._cache_dir = cache_dir
        self._on_stage = on_stage
        self._loaded: dict[str, tuple[object, object, str | None]] = {}

    def _model_dir(self, direction: TranslationDirection, model_name: str) -> Path:
        # Include the model name so switching a direction to a different
        # model (as happened when tc-big was replaced by NLLB-200) can't
        # silently reuse a stale CTranslate2 conversion of the old model.
        safe_model_name = model_name.replace("/", "__")
        return self._cache_dir / f"{direction.replace('->', '_to_')}__{safe_model_name}"

    def is_cached(self, direction: TranslationDirection) -> bool:
        config = _LOCAL_MODEL_CONFIGS[direction]
        return self._model_dir(direction, config.model_name).exists()

    def _get_tokenizer_and_translator(self, direction: TranslationDirection):
        if direction not in self._loaded:
            import ctranslate2
            from ctranslate2.converters import TransformersConverter
            from transformers import AutoTokenizer

            config = _LOCAL_MODEL_CONFIGS[direction]
            model_dir = self._model_dir(direction, config.model_name)
            if not model_dir.exists():
                if self._on_stage is not None:
                    self._on_stage("downloading_model")
                TransformersConverter(config.model_name).convert(
                    str(model_dir), quantization="int8"
                )

            tokenizer_kwargs = {"src_lang": config.src_lang} if config.src_lang else {}
            tokenizer = AutoTokenizer.from_pretrained(config.model_name, **tokenizer_kwargs)
            ct2_translator = ctranslate2.Translator(str(model_dir))
            self._loaded[direction] = (tokenizer, ct2_translator, config.target_prefix)
            if self._on_stage is not None:
                self._on_stage("processing")
        return self._loaded[direction]

    def translate(self, texts: list[str], direction: TranslationDirection) -> list[str]:
        outputs, _scores = self._translate(texts, direction, with_scores=False)
        return outputs

    def translate_with_scores(
        self, texts: list[str], direction: TranslationDirection
    ) -> tuple[list[str], list[float | None]]:
        return self._translate(texts, direction, with_scores=True)

    def _translate(
        self, texts: list[str], direction: TranslationDirection, with_scores: bool
    ) -> tuple[list[str], list[float | None]]:
        if not texts:
            return [], []
        tokenizer, ct2_translator, target_prefix_token = self._get_tokenizer_and_translator(
            direction
        )
        tokenized = [tokenizer.convert_ids_to_tokens(tokenizer.encode(text)) for text in texts]
        target_prefix = (
            [[target_prefix_token] for _ in texts] if target_prefix_token else None
        )
        results = ct2_translator.translate_batch(
            tokenized, target_prefix=target_prefix, return_scores=with_scores
        )
        outputs = []
        scores: list[float | None] = []
        for result in results:
            hypothesis = result.hypotheses[0]
            token_ids = tokenizer.convert_tokens_to_ids(hypothesis)
            outputs.append(tokenizer.decode(token_ids, skip_special_tokens=True))
            if with_scores and result.scores:
                # normalize the cumulative log-prob by length so segments of
                # different lengths remain comparable to each other
                scores.append(result.scores[0] / max(len(hypothesis), 1))
            else:
                scores.append(None)
        return outputs, scores


class ApiTranslator:
    def __init__(self, api_key: str, base_url: str = "https://api.openai.com/v1"):
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")

    def translate(self, texts: list[str], direction: TranslationDirection) -> list[str]:
        if not texts:
            return []

        source, target = direction.split("->")
        prompt = (
            f"Translate each numbered line from {_LANGUAGE_NAMES[source]} to {_LANGUAGE_NAMES[target]}. "
            "Reply with only the translated lines, same order, same numbering, no extra commentary.\n\n"
            + "\n".join(f"{index + 1}. {text}" for index, text in enumerate(texts))
        )

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
        response.raise_for_status()
        content = response.json()["choices"][0]["message"]["content"]
        return _parse_numbered_lines(content, expected_count=len(texts))


def _parse_numbered_lines(content: str, expected_count: int) -> list[str]:
    lines = [line.strip() for line in content.strip().splitlines() if line.strip()]
    parsed = []
    for line in lines:
        _, _, rest = line.partition(".")
        parsed.append(rest.strip() if rest else line)
    if len(parsed) != expected_count:
        raise ValueError(
            f"API translation returned {len(parsed)} lines, expected {expected_count}"
        )
    return parsed


def get_translator(
    engine: str, settings: Settings, on_stage: Callable[[str], None] | None = None
) -> Translator:
    if engine == "local":
        return LocalTranslator(cache_dir=settings.ct2_model_cache_dir, on_stage=on_stage)
    if engine == "api":
        if not settings.translation_api_key:
            raise ValueError("API 번역을 사용하려면 TRANSLATION_API_KEY 설정이 필요합니다.")
        base_url = settings.translation_api_base_url or "https://api.openai.com/v1"
        return ApiTranslator(api_key=settings.translation_api_key, base_url=base_url)
    raise ValueError(f"알 수 없는 번역 엔진: {engine}")


_LOW_SCORE_STDEV_MULTIPLIER = 1.5
_MIN_SEGMENTS_FOR_RELATIVE_QUALITY = 3


class TranslationCancelled(Exception):
    """Raised mid-translate when the caller's should_cancel() reports True."""


def translate_segments(
    segments: list[Segment],
    direction: TranslationDirection,
    translator: Translator,
    on_progress: Callable[[float], None] | None = None,
    batch_size: int = 8,
    should_cancel: Callable[[], bool] | None = None,
) -> list[Segment]:
    if not segments:
        return []

    target_lang = direction.split("->")[1]
    total = len(segments)
    updated: list[Segment | None] = [None] * total
    pending_indices: list[int] = []
    pending_segments: list[Segment] = []

    for index, segment in enumerate(segments):
        if _already_in_target_language(segment.text, target_lang):
            updated[index] = segment.model_copy(update={"translation": segment.text})
        else:
            pending_indices.append(index)
            pending_segments.append(segment)

    done_count = total - len(pending_segments)
    if on_progress and done_count:
        on_progress(min(done_count / total, 1.0))

    supports_scores = hasattr(translator, "translate_with_scores")
    translations_by_index: dict[int, str] = {}
    scores_by_index: dict[int, float | None] = {}

    for start in range(0, len(pending_segments), batch_size):
        if should_cancel is not None and should_cancel():
            raise TranslationCancelled("번역이 취소되었습니다.")
        batch = pending_segments[start : start + batch_size]
        batch_indices = pending_indices[start : start + batch_size]
        batch_texts = [segment.text for segment in batch]
        if supports_scores:
            translations, scores = translator.translate_with_scores(batch_texts, direction)
        else:
            translations = translator.translate(batch_texts, direction)
            scores = [None] * len(translations)
        for index, translation, score in zip(batch_indices, translations, scores):
            translations_by_index[index] = translation
            scores_by_index[index] = score
        done_count += len(batch)
        if on_progress:
            on_progress(min(done_count / total, 1.0))

    # Flag segments whose translation confidence is a clear outlier relative
    # to the rest of *this* project - there's no universal "good" absolute
    # score across models/content, but a segment translated much less
    # confidently than its neighbors is worth a second look.
    valid_scores = [s for s in scores_by_index.values() if s is not None]
    low_score_threshold = None
    if len(valid_scores) >= _MIN_SEGMENTS_FOR_RELATIVE_QUALITY:
        mean = statistics.mean(valid_scores)
        stdev = statistics.pstdev(valid_scores)
        low_score_threshold = mean - _LOW_SCORE_STDEV_MULTIPLIER * stdev

    for index in pending_indices:
        segment = segments[index]
        score = scores_by_index[index]
        quality: str | None = None
        reason: str | None = None
        if score is not None:
            if low_score_threshold is not None and score < low_score_threshold:
                quality = "check"
                reason = "이 프로젝트의 다른 문장들에 비해 번역 신뢰도가 낮습니다"
            else:
                quality = "good"
        updated[index] = segment.model_copy(
            update={
                "translation": translations_by_index[index],
                "translation_quality": quality,
                "translation_quality_reason": reason,
            }
        )

    return updated  # type: ignore[return-value]
