"""Compare a project's current translation against a reference SRT.

Not a pytest test - one-off quality comparison tool: matches segments to
reference SRT cues by timing and writes a side-by-side diff to a text file
(Korean-safe, since this repo's Windows console mangles UTF-8 otherwise).

Usage:
    python scripts/compare_translation_quality.py \
        --project 391bcf11cdff4188925593f913c3ee9d --item a831768af6fe4bcd83c8a48e6fff177b \
        --reference "C:/path/to/reference_translated.srt" \
        --out D:/sw_work/zamac_valsadae/backend/scripts/_compare_out.txt
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.config import DATA_DIR  # noqa: E402

_TIMESTAMP_RE = re.compile(
    r"(\d{2}):(\d{2}):(\d{2}),(\d{3})\s*-->\s*(\d{2}):(\d{2}):(\d{2}),(\d{3})"
)


def _to_seconds(h: str, m: str, s: str, ms: str) -> float:
    return int(h) * 3600 + int(m) * 60 + int(s) + int(ms) / 1000


def parse_srt(path: Path) -> list[tuple[float, float, str]]:
    blocks = path.read_text(encoding="utf-8-sig").strip().split("\n\n")
    cues = []
    for block in blocks:
        lines = block.strip().splitlines()
        if len(lines) < 2:
            continue
        match = _TIMESTAMP_RE.search(lines[1]) if not _TIMESTAMP_RE.search(lines[0]) else _TIMESTAMP_RE.search(lines[0])
        # timestamp line is usually line[1] (line[0] is the cue number), but
        # be lenient in case numbering is missing
        timestamp_line_idx = 1 if _TIMESTAMP_RE.search(lines[1]) else 0
        match = _TIMESTAMP_RE.search(lines[timestamp_line_idx])
        if not match:
            continue
        start = _to_seconds(*match.groups()[0:4])
        end = _to_seconds(*match.groups()[4:8])
        text = " ".join(lines[timestamp_line_idx + 1 :]).strip()
        cues.append((start, end, text))
    return cues


def load_current_segments(project_id: str, item_id: str) -> list[dict]:
    project_path = DATA_DIR / "projects" / project_id / "project.json"
    data = json.loads(project_path.read_text(encoding="utf-8"))
    for item in data["items"]:
        if item["id"] == item_id:
            return item["segments"]
    raise SystemExit(f"item {item_id} not found in project {project_id}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project", required=True)
    parser.add_argument("--item", required=True)
    parser.add_argument("--reference", required=True, help="path to reference *_translated.srt")
    parser.add_argument("--out", required=True)
    parser.add_argument("--tolerance", type=float, default=0.05, help="seconds, for start-time matching")
    args = parser.parse_args()

    reference_cues = parse_srt(Path(args.reference))
    segments = load_current_segments(args.project, args.item)

    out_lines = []
    out_lines.append(f"reference cues: {len(reference_cues)}, current segments: {len(segments)}\n")

    matched = 0
    unmatched_segments = []
    ref_by_start = [(start, end, text) for start, end, text in reference_cues]

    for segment in segments:
        seg_start = segment["start"]
        best = None
        for start, end, text in ref_by_start:
            if abs(start - seg_start) <= args.tolerance:
                best = (start, end, text)
                break
        if best is None:
            unmatched_segments.append(segment)
            continue
        matched += 1
        ref_text = best[2]
        new_text = segment.get("translation") or ""
        out_lines.append(f"[{seg_start:8.2f}s] 원문: {segment['text']}")
        out_lines.append(f"           기존(최종): {ref_text}")
        out_lines.append(f"           신규(API):   {new_text}")
        if ref_text.strip() == new_text.strip():
            out_lines.append("           -> 동일")
        out_lines.append("")

    out_lines.append(f"\n매칭됨: {matched} / {len(segments)}, 레퍼런스에서 못 찾은 세그먼트: {len(unmatched_segments)}")

    Path(args.out).write_text("\n".join(out_lines), encoding="utf-8")
    print(f"Wrote comparison to {args.out} (matched {matched}/{len(segments)})")


if __name__ == "__main__":
    main()
