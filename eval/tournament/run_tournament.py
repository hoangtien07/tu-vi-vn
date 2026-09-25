"""SPEC_V04 — knowledge-pack tournament runner.

Spawns one uvicorn per variant (same sqlite DB → identical chart ids), runs the
frozen bench corpus through eval/bench/run_bench.py, then compares variants:

    winner ⇔ 0 grounding failures AND rubric mean ≥ baseline (builtin).

Variants (I17 explicit selection):
    none        KNOWLEDGE_PACK=none   (ablation — no pack excerpts)
    builtin     KNOWLEDGE_PACK=builtin (baseline — zh-CN x-iztro pack)
    vn-seed-v1  KNOWLEDGE_PACK=eval/packs/vn-seed-v1.json

I18 gate is advisory — this script never switches the production pack (I17);
the human reviews eval/tournament/reports/tournament-*.md and decides.

Usage:
    python eval/tournament/run_tournament.py --smoke
    python eval/tournament/run_tournament.py --suite static \\
        --judge --judge-base-url ... --judge-api-key ... --judge-model ...
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
API_DIR = REPO / "apps" / "api"
BENCH = REPO / "eval" / "bench" / "run_bench.py"
DB = "/tmp/tournament.db"

VARIANTS = {
    "none": "none",
    "builtin": "builtin",
    "vn-seed-v1": str(REPO / "eval" / "packs" / "vn-seed-v1.json"),
}
EXPECTED_PACK_ID = {"none": "none", "builtin": None, "vn-seed-v1": "vn-seed-v1"}
BASELINE = "builtin"


def _wait_health(port: int, timeout: float = 60.0) -> dict | None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(
                f"http://127.0.0.1:{port}/health", timeout=3
            ) as r:
                return json.loads(r.read().decode())
        except Exception:  # noqa: BLE001
            time.sleep(0.5)
    return None


def _spawn(variant: str, port: int) -> subprocess.Popen:
    env = dict(os.environ)
    env["KNOWLEDGE_PACK"] = VARIANTS[variant]
    env["DATABASE_URL"] = f"sqlite+pysqlite:///{DB}"
    return subprocess.Popen(
        ["uv", "run", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", str(port)],
        cwd=API_DIR,
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def _run_bench(args: argparse.Namespace, variant: str, port: int, stamp: str) -> int:
    out = REPO / "eval" / "tournament" / "reports" / f"{stamp}" / variant
    cmd = [
        "uv", "run", "python", str(BENCH),
        "--api", f"http://127.0.0.1:{port}",
        "--suite", args.suite,
        "--out", str(out),
        "--concurrency", str(args.concurrency),
    ]
    if args.suite == "yearly":
        cmd += ["--year", str(args.year)]
    if args.judge:
        cmd += [
            "--judge",
            "--judge-base-url", args.judge_base_url,
            "--judge-api-key", args.judge_api_key,
            "--judge-model", args.judge_model,
        ]
    # each bench invocation stamps its own namespace → fresh runs per variant
    # even on the shared DB
    return subprocess.call(cmd, cwd=REPO)


def _latest_raw(variant_dir: Path) -> list[dict]:
    raws = sorted(variant_dir.glob("raw-*.json"))
    return json.loads(raws[-1].read_text()) if raws else []


def _summarize(results: list[dict]) -> dict:
    done = [r for r in results if r["status"] == "done"]
    grounding_fails = sum(
        1 for r in done if (r.get("grounding") or {}).get("unknownEvidenceReferences", 0)
    )
    judged = [r["judge"]["mean"] for r in done if (r.get("judge") or {}).get("mean")]
    return {
        "runs": len(results),
        "done": len(done),
        "groundingFailures": grounding_fails,
        "rubricMean": round(sum(judged) / len(judged), 3) if judged else None,
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--variants", nargs="+", default=list(VARIANTS))
    ap.add_argument("--suite", default="static", choices=["static", "yearly", "compat"])
    ap.add_argument("--year", type=int, default=2028)
    ap.add_argument("--concurrency", type=int, default=2)
    ap.add_argument("--base-port", type=int, default=8400)
    ap.add_argument("--smoke", action="store_true", help="boot + health-check only")
    ap.add_argument("--judge", action="store_true")
    ap.add_argument("--judge-base-url", default=os.environ.get("AI_BASE_URL", ""))
    ap.add_argument("--judge-api-key", default=os.environ.get("AI_API_KEY", ""))
    ap.add_argument("--judge-model", default=os.environ.get("AI_MODEL", ""))
    args = ap.parse_args()

    stamp = dt.datetime.now(dt.UTC).strftime("%Y%m%d-%H%M%S")
    report_dir = REPO / "eval" / "tournament" / "reports" / stamp
    report_dir.mkdir(parents=True, exist_ok=True)

    env_db = dict(os.environ, DATABASE_URL=f"sqlite+pysqlite:///{DB}")
    rc = subprocess.call(["uv", "run", "alembic", "upgrade", "head"], cwd=API_DIR, env=env_db)
    if rc != 0:
        sys.exit("alembic upgrade head failed")

    for i, variant in enumerate(args.variants):
        port = args.base_port + i
        print(f"[{variant}] spawning :{port} KNOWLEDGE_PACK={VARIANTS[variant]}")
        proc = _spawn(variant, port)
        try:
            health = _wait_health(port)
            if health is None:
                print(f"[{variant}] FAILED to boot")
                continue
            pack_id = health.get("knowledgePack")
            expected = EXPECTED_PACK_ID[variant]
            ok = expected is None or pack_id == expected
            print(f"[{variant}] health={health.get('status')} pack={pack_id} {'OK' if ok else 'MISMATCH'}")
            if not ok:
                continue
            if not args.smoke:
                rc = _run_bench(args, variant, port, stamp)
                print(f"[{variant}] bench rc={rc}")
        finally:
            proc.terminate()
            try:
                proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                proc.kill()

    if args.smoke:
        return

    summaries = {}
    for variant in args.variants:
        summaries[variant] = _summarize(_latest_raw(report_dir / variant))
    base = summaries.get(BASELINE, {})
    lines = [f"# Knowledge tournament — {stamp}", "", f"suite={args.suite} corpus=24 charts", ""]
    lines.append("| variant | runs | done | grounding fails | rubric mean | verdict |")
    lines.append("|---|---|---|---|---|---|")
    winner = None
    for variant, s in summaries.items():
        verdict = "—"
        if variant != BASELINE:
            rubric_ok = s["rubricMean"] is None or base.get("rubricMean") is None or s["rubricMean"] >= base["rubricMean"]
            wins = s["groundingFailures"] == 0 and s["done"] == s["runs"] and rubric_ok
            verdict = "WINNER" if wins else "no"
            if wins and winner is None:
                winner = variant
        lines.append(
            f"| {variant} | {s['runs']} | {s['done']} | {s['groundingFailures']} | {s['rubricMean']} | {verdict} |"
        )
    lines += [
        "",
        f"decision: {'candidate=' + winner + ' (advisory — human approves pack switch)' if winner else 'no winner — keep ' + BASELINE}",
        "note: I18 gate = 0 grounding fails AND rubric >= baseline on the frozen corpus.",
    ]
    md = report_dir / f"tournament-{stamp}.md"
    md.write_text("\n".join(lines))
    print("\n".join(lines))
    print(f"\nreport: {md}")


if __name__ == "__main__":
    main()
