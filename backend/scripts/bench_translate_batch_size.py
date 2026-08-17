"""Empirically find a good translate_segments batch_size.

Not a pytest test - hits the real relay/API with a real project's subtitle
text to compare a few candidate batch sizes on latency and JSON-parse
reliability. Requires a bearer token (session JWT or TRANSLATION_API_KEY).

Usage:
    TRANSLATE_BENCH_TOKEN=<jwt or api key> python scripts/bench_translate_batch_size.py \
        --project 391bcf11cdff4188925593f913c3ee9d --sample 64
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.config import DATA_DIR  # noqa: E402
from app.services.translation_service import ApiTranslator  # noqa: E402

DEFAULT_BASE_URL = os.environ.get(
    "HOSTED_RELAY_BASE_URL", "https://168-110-107-78.nip.io/v1"
)


def load_sample_texts(project_id: str, sample: int) -> list[str]:
    project_path = DATA_DIR / "projects" / project_id / "project.json"
    data = json.loads(project_path.read_text(encoding="utf-8"))
    texts: list[str] = []
    for item in data.get("items", []):
        for segment in item.get("segments", []):
            text = segment.get("text")
            if text:
                texts.append(text)
            if len(texts) >= sample:
                return texts[:sample]
    return texts[:sample]


def run_batch_size(translator: ApiTranslator, texts: list[str], batch_size: int) -> dict:
    call_count = 0
    failures = 0
    failure_messages: list[str] = []
    started = time.monotonic()
    for start in range(0, len(texts), batch_size):
        chunk = texts[start : start + batch_size]
        call_count += 1
        try:
            corrected, translated = translator.translate_with_correction(chunk)
            if len(corrected) != len(chunk) or len(translated) != len(chunk):
                failures += 1
                failure_messages.append(f"call {call_count}: length mismatch")
        except Exception as exc:  # noqa: BLE001 - want to record any failure kind
            failures += 1
            failure_messages.append(f"call {call_count}: {exc}")
    elapsed = time.monotonic() - started
    return {
        "batch_size": batch_size,
        "total_texts": len(texts),
        "calls": call_count,
        "failures": failures,
        "failure_messages": failure_messages,
        "elapsed_sec": round(elapsed, 2),
        "avg_sec_per_call": round(elapsed / call_count, 2) if call_count else 0.0,
        "avg_sec_per_text": round(elapsed / len(texts), 3) if texts else 0.0,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project", required=True, help="project id under data/projects/")
    parser.add_argument("--sample", type=int, default=64, help="number of segments to use")
    parser.add_argument(
        "--batch-sizes", default="4,8,16,24,32", help="comma-separated batch sizes to test"
    )
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL)
    args = parser.parse_args()

    token = os.environ.get("TRANSLATE_BENCH_TOKEN")
    if not token:
        raise SystemExit("Set TRANSLATE_BENCH_TOKEN (session JWT or API key) first.")

    texts = load_sample_texts(args.project, args.sample)
    if not texts:
        raise SystemExit(f"No segments found for project {args.project}")
    print(f"Loaded {len(texts)} sample segments from project {args.project}")

    translator = ApiTranslator(api_key=token, base_url=args.base_url)
    batch_sizes = [int(b) for b in args.batch_sizes.split(",")]

    results = []
    for batch_size in batch_sizes:
        print(f"\n== batch_size={batch_size} ==")
        result = run_batch_size(translator, texts, batch_size)
        results.append(result)
        print(json.dumps(result, ensure_ascii=False, indent=2))

    print("\n== summary ==")
    header = f"{'batch':>6} | {'calls':>5} | {'fail':>4} | {'total_sec':>9} | {'sec/call':>8} | {'sec/text':>8}"
    print(header)
    print("-" * len(header))
    for r in results:
        print(
            f"{r['batch_size']:>6} | {r['calls']:>5} | {r['failures']:>4} | "
            f"{r['elapsed_sec']:>9} | {r['avg_sec_per_call']:>8} | {r['avg_sec_per_text']:>8}"
        )


if __name__ == "__main__":
    main()
