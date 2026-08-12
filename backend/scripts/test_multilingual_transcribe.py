"""Manual review script for mixed-language transcription strategies.

Not a pytest test - run directly against a real media file that switches
languages mid-way to compare two approaches:

  1. single pass with multilingual=True: faster-whisper re-detects the
     spoken language every ~30s window instead of once for the whole file.
  2. --dual: two full passes, each with the language forced (e.g. ko, en),
     compared window-by-window on decode confidence (avg_logprob).

Usage:
    python scripts/test_multilingual_transcribe.py <media_path> [--model small]
    python scripts/test_multilingual_transcribe.py <media_path> --dual --languages ko,en
"""

from __future__ import annotations

import argparse
import logging
import sys
import time
from collections.abc import Iterable
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.config import WHISPER_MODEL_SIZES  # noqa: E402
from app.services import whisper_service  # noqa: E402

logger = logging.getLogger("test_multilingual_transcribe")

WINDOW_SECONDS = 30.0


def _setup_logging(log_path: Path) -> None:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler(log_path, encoding="utf-8"),
        ],
    )


def _run_pass(
    media_path: Path, model_size: str, *, language: str | None, multilingual: bool
) -> tuple[list[object], float]:
    model = whisper_service._get_model(model_size)  # noqa: SLF001 - internal reuse for a dev script
    raw_segments, info = model.transcribe(
        str(media_path),
        word_timestamps=False,
        vad_filter=True,
        language=language,
        multilingual=multilingual,
    )
    return list(raw_segments), float(getattr(info, "duration", 0.0))


def _log_pass(label: str, segments: Iterable[object]) -> None:
    for seg in segments:
        logger.info(
            "[%s] %6.2f-%6.2f logprob=%+.3f no_speech=%.2f :: %s",
            label,
            seg.start,
            seg.end,
            seg.avg_logprob,
            seg.no_speech_prob,
            seg.text.strip(),
        )


def _window_index(t: float) -> int:
    return int(t // WINDOW_SECONDS)


def _windowed_avg_logprob(segments: list[object], window: int) -> float | None:
    window_start = window * WINDOW_SECONDS
    window_end = window_start + WINDOW_SECONDS
    overlapping = [s for s in segments if s.start < window_end and s.end > window_start]
    if not overlapping:
        return None
    return sum(s.avg_logprob for s in overlapping) / len(overlapping)


def run_multilingual(media_path: Path, model_size: str) -> None:
    logger.info("=== 단일 패스 (multilingual=True) ===")
    started = time.monotonic()
    segments, duration = _run_pass(media_path, model_size, language=None, multilingual=True)
    logger.info("오디오 길이 %.1fs, 세그먼트 %d개, 소요 %.1fs", duration, len(segments), time.monotonic() - started)
    _log_pass("multilingual", segments)


def run_dual(media_path: Path, model_size: str, languages: list[str]) -> None:
    logger.info("=== 이중 전사 비교 (강제 언어: %s) ===", ", ".join(languages))
    passes: dict[str, list[object]] = {}
    duration = 0.0
    for lang in languages:
        started = time.monotonic()
        segments, duration = _run_pass(media_path, model_size, language=lang, multilingual=False)
        logger.info(
            "[%s] 세그먼트 %d개, 소요 %.1fs", lang, len(segments), time.monotonic() - started
        )
        _log_pass(lang, segments)
        passes[lang] = segments

    logger.info("--- 윈도우(%.0fs)별 신뢰도 비교 ---", WINDOW_SECONDS)
    window_count = _window_index(duration) + 1
    for window in range(window_count):
        scores = {lang: _windowed_avg_logprob(segs, window) for lang, segs in passes.items()}
        present = {lang: score for lang, score in scores.items() if score is not None}
        if not present:
            continue
        winner = max(present, key=lambda lang: present[lang])
        window_start = window * WINDOW_SECONDS
        logger.info(
            "윈도우 %6.1f-%6.1fs 승자=%s (%s)",
            window_start,
            window_start + WINDOW_SECONDS,
            winner,
            ", ".join(f"{lang}={score:+.3f}" for lang, score in scores.items() if score is not None),
        )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("media_path", type=Path)
    parser.add_argument("--model", default="small", choices=WHISPER_MODEL_SIZES)
    parser.add_argument("--dual", action="store_true", help="언어 강제 이중 전사 비교 실행")
    parser.add_argument("--languages", default="ko,en", help="이중 전사에 사용할 언어 코드 (쉼표 구분)")
    parser.add_argument("--log-dir", type=Path, default=Path(__file__).resolve().parents[2] / "data" / "test_logs")
    args = parser.parse_args()

    if not args.media_path.is_file():
        parser.error(f"파일을 찾을 수 없습니다: {args.media_path}")

    log_path = args.log_dir / f"transcribe_test_{time.strftime('%Y%m%d_%H%M%S')}.log"
    _setup_logging(log_path)
    logger.info("미디어: %s, 모델: %s", args.media_path, args.model)

    if args.dual:
        run_dual(args.media_path, args.model, args.languages.split(","))
    else:
        run_multilingual(args.media_path, args.model)

    logger.info("로그 저장 위치: %s", log_path)


if __name__ == "__main__":
    main()
