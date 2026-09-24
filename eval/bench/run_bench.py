#!/usr/bin/env python3
"""Gate E model benchmark (EVALUATION.md): N charts x 5 topics through a real
AI_BASE_URL endpoint. Measures grounding violations, latency, output text and
produces a rubric report (LLM judge for quality dimensions).

Usage:
    python eval/bench/run_bench.py --api http://localhost:8000 \
        --charts eval/bench/charts.json --target 2028-03-01 \
        --out eval/bench/reports --topics overview career wealth love health \
        --concurrency 2 [--judge]
"""
from __future__ import annotations

import argparse
import asyncio
import datetime as dt
import json
import statistics
import time
from pathlib import Path

import httpx

TOPIC_VI = {
    "overview": "tổng quan",
    "career": "công việc",
    "wealth": "tài chính",
    "love": "tình duyện",
    "health": "sức khỏe",
}

JUDGE_PROMPT = """Chấm điểm luận giải tử vi tiếng Việt sau theo thang 1-5.
Trả JSON thuần {{"specificity": n, "relevance": n, "consistency": n, "vn_quality": n, "overclaim": true|false}}:
- specificity: cụ thể, gắn sao/cung, không phải câu Barnum áp dụng cho mọi người
- relevance: trả đúng chủ đề "{topic_vi}"
- consistency: không tự mâu thuẫn
- vn_quality: tiếng Việt tự nhiên, đúng thuật ngữ, không lọt chữ Hán/thuật ngữ kỹ thuật
- overclaim: true nếu dự đoán chắc chắn sự kiện lớn, tử vong/tai họa/tuổi thọ

Chỉ trả JSON, không giải thích.

LUẬN GIẢI:
{text}"""


def parse_sse(body: str) -> dict:
    events: list[dict] = []
    deltas: list[str] = []
    replaced = False
    for block in body.split("\n\n"):
        lines = [ln for ln in block.strip().splitlines() if ln.startswith(("event:", "data:"))]
        if not lines:
            continue
        ev = {}
        data_lines = []
        for ln in lines:
            k, _, v = ln.partition(":")
            if k.strip() == "data":
                data_lines.append(v.strip())
            else:
                ev[k.strip()] = v.strip()
        ev["data"] = "\n".join(data_lines)
        if ev.get("event") == "delta":
            try:
                deltas.append(json.loads(ev["data"]))
            except Exception:
                deltas.append(ev["data"])
        else:
            events.append(ev)
    last = events[-1] if events else {}
    out = {"status": last.get("event", "none"), "events": events, "replaced": replaced}
    for e in events:
        if e.get("event") == "replace":
            out["replaced"] = True
            try:
                out["output"] = json.loads(e["data"])
            except Exception:
                out["output"] = e["data"]
        if e.get("event") == "error":
            try:
                out["violations"] = json.loads(e["data"]).get("violations")
            except Exception:
                pass
    if "output" not in out:
        out["output"] = "".join(deltas)
    return out


async def run_one(client: httpx.AsyncClient, api: str, chart_id: str, topic: str, target: str) -> dict:
    t0 = time.monotonic()
    try:
        r = await client.post(
            f"{api}/api/charts/{chart_id}/interpret",
            json={"topic": topic, "target": target},
            timeout=180,
        )
        elapsed = time.monotonic() - t0
        if r.status_code != 200:
            return {"topic": topic, "status": f"http_{r.status_code}", "latency": elapsed, "detail": r.text[:200]}
        parsed = parse_sse(r.text)
        parsed["latency"] = elapsed
        parsed["topic"] = topic
        return parsed
    except Exception as exc:  # noqa: BLE001
        return {"topic": topic, "status": "client_error", "latency": time.monotonic() - t0, "detail": str(exc)[:200]}


# timeIndex 0..12 → representative civil times (branch midpoints)
_INDEX_TIME = [
    "23:30", "00:30", "02:00", "04:00", "06:00", "08:00", "10:00",
    "12:00", "14:00", "16:00", "18:00", "20:00", "22:00",
]


async def cast_chart(client: httpx.AsyncClient, api: str, c: dict) -> str:
    r = await client.post(
        f"{api}/api/charts",
        json={
            "date": c["solarDate"],
            "time": _INDEX_TIME[c["timeIndex"]],
            "gender": c["gender"],
            "birthRegion": c["birthRegion"],
            "longitude": c["longitude"],
            "trueSolarTimeEnabled": True,
        },
        timeout=30,
    )
    r.raise_for_status()
    return r.json()["id"]


async def judge(client: httpx.AsyncClient, base_url: str, api_key: str, model: str, topic: str, text: str) -> dict | None:
    if not text:
        return None
    try:
        r = await client.post(
            f"{base_url}/chat/completions",
            headers={"Authorization": f"Bearer {api_key}"},
            json={
                "model": model,
                "temperature": 0,
                "messages": [{"role": "user", "content": JUDGE_PROMPT.format(topic_vi=TOPIC_VI[topic], text=text[:12000])}],
            },
            timeout=120,
        )
        content = r.json()["choices"][0]["message"]["content"]
        content = content.strip().removeprefix("```json").removesuffix("```").strip()
        return json.loads(content)
    except Exception as exc:  # noqa: BLE001
        return {"judge_error": str(exc)[:120]}


async def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--api", default="http://localhost:8000")
    ap.add_argument("--charts", default="eval/bench/charts.json")
    ap.add_argument("--target", default="2028-03-01")
    ap.add_argument("--topics", nargs="+", default=["overview", "career", "wealth", "love", "health"])
    ap.add_argument("--concurrency", type=int, default=2)
    ap.add_argument("--out", default="eval/bench/reports")
    ap.add_argument("--judge", action="store_true")
    ap.add_argument("--judge-base-url", default="")
    ap.add_argument("--judge-api-key", default="")
    ap.add_argument("--judge-model", default="")
    args = ap.parse_args()

    charts = json.loads(Path(args.charts).read_text())
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    sem = asyncio.Semaphore(args.concurrency)
    results: list[dict] = []

    async with httpx.AsyncClient() as client:
        ids = await asyncio.gather(*[cast_chart(client, args.api, c) for c in charts])
        print(f"cast {len(ids)} charts")

        async def task(i: int, chart_id: str, topic: str) -> dict:
            async with sem:
                res = await run_one(client, args.api, chart_id, topic, args.target)
                res["chart"] = charts[i]["id"]
                res["chart_id"] = chart_id
                return res

        jobs = [task(i, cid, t) for i, cid in enumerate(ids) for t in args.topics]
        for i, coro in enumerate(asyncio.as_completed(jobs)):
            res = await coro
            results.append(res)
            print(f"[{i + 1}/{len(jobs)}] {res['chart']} {res['topic']}: {res['status']} {res['latency']:.1f}s", flush=True)

        if args.judge:
            judged = 0
            for res in results:
                if res["status"] == "done" and res.get("output"):
                    res["judge"] = await judge(
                        client, args.judge_base_url, args.judge_api_key, args.judge_model,
                        res["topic"], res["output"],
                    )
                    judged += 1
                    if judged % 10 == 0:
                        print(f"judged {judged}", flush=True)

    stamp = dt.datetime.now(dt.UTC).strftime("%Y%m%d-%H%M%S")
    raw_path = out_dir / f"raw-{stamp}.json"
    raw_path.write_text(json.dumps(results, ensure_ascii=False, indent=2))

    done = [r for r in results if r["status"] == "done"]
    failed = [r for r in results if r["status"] != "done"]
    replaced = [r for r in done if r.get("replaced")]
    lat = sorted(r["latency"] for r in results)
    viols = [v for r in results for v in (r.get("violations") or [])]

    lines = [
        f"# Gate E benchmark — {stamp}",
        "",
        f"- charts: {len(charts)}  topics: {len(args.topics)}  runs: {len(results)}",
        f"- done: {len(done)} (of which repaired/replaced: {len(replaced)})  failed: {len(failed)}",
        f"- latency s: p50={statistics.median(lat):.1f} p95={lat[int(len(lat) * 0.95) - 1]:.1f} max={max(lat):.1f}",
        "",
        "## Failures / violations",
    ]
    for r in failed:
        lines.append(f"- {r['chart']} {r['topic']}: {r['status']} {r.get('violations') or r.get('detail', '')}")
    if viols:
        lines.append(f"\nviolations total: {len(viols)}")
        for v in viols[:40]:
            lines.append(f"  - {v}")

    judged = [r for r in results if r.get("judge") and "judge_error" not in r["judge"]]
    if judged:
        dims = ["specificity", "relevance", "consistency", "vn_quality"]
        lines += ["", "## LLM-judge rubric (1-5, mean)"]
        for d in dims:
            vals = [r["judge"][d] for r in judged if isinstance(r["judge"].get(d), int | float)]
            if vals:
                lines.append(f"- {d}: {statistics.mean(vals):.2f} (n={len(vals)})")
        over = [r for r in judged if r["judge"].get("overclaim")]
        lines.append(f"- overclaim flags: {len(over)}")

    report = out_dir / f"gate-e-{stamp}.md"
    report.write_text("\n".join(lines))
    print(f"\nreport: {report}\nraw: {raw_path}")
    print("\n".join(lines[:30]))


if __name__ == "__main__":
    asyncio.run(main())
