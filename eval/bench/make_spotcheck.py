#!/usr/bin/env python3
"""Human spot-check pack (EVALUATION.md Gate E): render N full interpretation
outputs from a bench raw-*.json into one reviewable markdown file.

LLM-judge scores are not release evidence alone — a human reads these.

Usage:
    python eval/bench/make_spotcheck.py eval/bench/reports/raw-static-<stamp>.json \
        --n 24 --out eval/bench/reports/spotcheck-<stamp>.md
"""
from __future__ import annotations

import argparse
import json
import random
from pathlib import Path


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("raw", help="raw-<suite>-<stamp>.json from run_bench.py")
    ap.add_argument("--n", type=int, default=24)
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--out", default="")
    args = ap.parse_args()

    results = json.loads(Path(args.raw).read_text())
    done = [r for r in results if r.get("status") == "done" and r.get("output")]
    random.Random(args.seed).shuffle(done)
    sample = done[: args.n]

    lines = [
        f"# Human spot-check pack — {Path(args.raw).name}",
        "",
        f"- sampled: {len(sample)} / {len(done)} completed outputs "
        f"(seed {args.seed})",
        "- checklist per output: đúng thuật ngữ VN? có Barnum? có nhận định "
        "vận hạn không cite? có sao/cung không có trong lá số? có overclaim?",
        "",
    ]
    for i, r in enumerate(sample, 1):
        lines += [
            f"## {i}. {r['chart']} · {r['topic']}",
            "",
            r["output"].strip(),
            "",
            "---",
            "",
        ]
    out = Path(args.out) if args.out else Path(args.raw).with_name(
        Path(args.raw).name.replace("raw-", "spotcheck-").replace(".json", ".md")
    )
    out.write_text("\n".join(lines), encoding="utf-8")
    print(f"wrote {out} ({len(sample)} outputs)")


if __name__ == "__main__":
    main()
