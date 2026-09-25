"""SPEC_V05 D2 — candidates.jsonl -> eval/packs/vn-mined-v{N}.json.

Selects top-K phrases per entity (boilerplate filtered, near-dup deduped),
translates zh->vi via an OpenAI-compatible endpoint (offline eval use only —
AI_* env vars; the pack itself is pure data at runtime, I23), and emits a
KnowledgePack-schema file plus a coverage report.

Only schema-fitting entities are emitted today (star/pattern/palace);
parked composites (palaceStar, mutagenStar) stay in candidates.jsonl for a
future pack-schema extension.

Usage:
    cd apps/api && uv run python ../../eval/mining/pack.py \
        --out-pack eval/packs/vn-mined-v1.json
    # translation needs: AI_BASE_URL + AI_API_KEY + AI_MODEL (same env contract
    # as the app) — or --no-translate to keep zh phrases parked in sourceText.
"""

from __future__ import annotations

import argparse
import collections
import json
import os
import re
import sys
import urllib.request
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
DEFAULT_CANDIDATES = REPO / "eval" / "mining" / "out" / "candidates.jsonl"
DEFAULT_REPORT = REPO / "eval" / "mining" / "out" / "coverage.md"

# sentences that describe the dataset's own layout, not lore
BOILERPLATE = re.compile(
    r"当前大限|本宫主星|命盘推演|星曜深层特质|命盘特殊格局|命盘关键定制|"
    r"命格总览|性格特质|感情婚姻|事业职业|财富运势|健康状况|兄弟合伙|"
    r"子女缘分|迁移外出|人际贵人|田宅不动产|精神福德|父母长辈|"
    r"^\d+\.\s|—+$|倪师天纪\s*\d+明示|▍|年干四化|三合·|本命四化落|"
    r"大限三方四正"
)
SIMPLIFY = re.compile(r"[^\w一-鿿]+")

TOPIC_VI = {
    "overview": "tổng quan",
    "personality": "tính cách",
    "love": "tình cảm",
    "career": "sự nghiệp",
    "wealth": "tài chính",
    "health": "sức khỏe",
    "family": "anh chị em",
    "children": "con cái",
    "move": "di chuyển",
    "friends": "bạn bè",
    "home": "nhà cửa",
    "spirit": "tinh thần",
    "parents": "cha mẹ",
}

STAR_CATEGORY = {"major", "lucky", "sha", "minor", "adjective"}


def simplify(s: str) -> str:
    return SIMPLIFY.sub("", s).lower()


def pick_phrases(
    phrases: list[dict], k: int, max_share: float = 0.5, kept: int = 0
) -> list[dict]:
    """Top-K by count, dropping boilerplate and near-duplicates.

    Phrases present in >max_share of all kept samples are dataset template
    text (layout echoes), not entity lore — they out-rank real lore.
    """
    seen: set[str] = set()
    picked: list[dict] = []
    for p in phrases:
        text = p["text"]
        if BOILERPLATE.search(text):
            continue
        if kept and p["count"] > kept * max_share:
            continue
        key = simplify(text)
        if not key or len(key) < 8:
            continue
        if key in seen:
            continue
        # near-dup: skip if this phrase is a substring of a picked one
        if any(key in simplify(q["text"]) for q in picked):
            continue
        seen.add(key)
        picked.append(p)
        if len(picked) >= k:
            break
    return picked


def _chat(messages: list[dict], max_tokens: int = 4000) -> str:
    base = os.environ.get("AI_BASE_URL", "").rstrip("/")
    key = os.environ.get("AI_API_KEY", "")
    model = os.environ.get("AI_MODEL", "")
    if not (base and model):
        raise RuntimeError("AI_BASE_URL/AI_MODEL required for translation")
    body = json.dumps(
        {
            "model": model,
            "messages": messages,
            "temperature": 0.2,
            "max_tokens": max_tokens,
            "reasoning": {"enabled": False},
        }
    ).encode()
    req = urllib.request.Request(
        f"{base}/chat/completions",
        data=body,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {key}",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=300) as resp:
        data = json.loads(resp.read())
    return data["choices"][0]["message"]["content"]


TRANSLATE_SYS = (
    "Bạn là chuyên gia Tử Vi Đẩu Số Việt Nam. Dịch mỗi câu tiếng Trung sau "
    "sang tiếng Việt tự nhiên, giữ thuật ngữ Tử Vi chuẩn Việt (cung Mệnh, "
    "Hóa Lộc/Quyền/Khoa/Kỵ, tên sao Hán-Việt: 紫微=Tử Vi, 天机=Thiên Cơ, "
    "太阳=Thái Dương, 武曲=Vũ Khúc, 天同=Thiên Đồng, 廉贞=Liêm Trinh, "
    "天府=Thiên Phủ, 太阴=Thái Âm, 贪狼=Tham Lang, 巨门=Cự Môn, "
    "天相=Thiên Tướng, 天梁=Thiên Lương, 七杀=Thất Sát, 破军=Phá Quân, "
    "cung: 命宫=Mệnh, 兄弟=Huynh Đệ, 夫妻=Phu Thê, 子女=Tử Tức, "
    "财帛=Tài Bạch, 疾厄=Tật Ách, 迁移=Thiên Di, 仆役/交友=Nô Bộc, "
    "官禄=Quan Lộc, 田宅=Điền Trạch, 福德=Phúc Đức, 父母=Phụ Mẫu). "
    "Trả về JSON array các chuỗi dịch, cùng thứ tự input. Chỉ JSON, "
    "không giải thích."
)


def translate_batch(texts: list[str]) -> list[str]:
    """Translate a batch of zh phrases -> vi. Retries once on JSON parse."""
    user = json.dumps(texts, ensure_ascii=False)
    for attempt in range(2):
        out = _chat(
            [
                {"role": "system", "content": TRANSLATE_SYS},
                {"role": "user", "content": user},
            ],
            max_tokens=max(1000, len(texts) * 120),
        )
        try:
            arr = json.loads(out[out.index("[") : out.rindex("]") + 1])
            if len(arr) == len(texts) and all(isinstance(x, str) for x in arr):
                return arr
        except (ValueError, json.JSONDecodeError):
            pass
    raise RuntimeError(f"translation JSON mismatch ({len(texts)} items)")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--candidates", type=Path, default=DEFAULT_CANDIDATES)
    ap.add_argument("--out-pack", type=Path, required=True)
    ap.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    ap.add_argument("--top-k", type=int, default=5)
    ap.add_argument("--no-translate", action="store_true")
    ap.add_argument("--batch", type=int, default=25)
    args = ap.parse_args()

    rows = [
        json.loads(l)
        for l in args.candidates.open(encoding="utf-8")
        if l.strip()
    ]

    # star categories come from the builtin zh pack (schema truth)
    sys.path.insert(0, str(REPO / "apps" / "api"))
    from x_iztro.knowledge import KnowledgePack  # eval-only import

    _zh_pack = KnowledgePack.builtin("zh-CN")

    pack: dict = {
        "id": args.out_pack.stem,
        "version": "1",
        "language": "vi",
        "schema": 1,
        "source": {
            "url": "https://github.com/Renhuai123/ziwei-doushu",
            "commit": "v3.0-samples",
            "license": "Renhuai dataset v3 (free use w/ attribution) — "
            "aggregated phrases mined offline, translated to vi",
        },
        "stars": {},
        "patterns": {},
        "palaces": {},
        "mutagens": {},
        "concepts": {},
    }

    kept = 0
    stats_file = args.candidates.parent / "stats.json"
    if stats_file.exists():
        kept = json.loads(stats_file.read_text()).get("kept", 0)

    # curated VN display names (mined zh names are not user-facing)
    PALACE_VI_NAME = {
        "soulPalace": "Mệnh",
        "parentsPalace": "Phụ Mẫu",
        "spiritPalace": "Phúc Đức",
        "propertyPalace": "Điền Trạch",
        "careerPalace": "Quan Lộc",
        "friendsPalace": "Nô Bộc",
        "surfacePalace": "Thiên Di",
        "healthPalace": "Tật Ách",
        "wealthPalace": "Tài Bạch",
        "childrenPalace": "Tử Tức",
        "spousePalace": "Phu Thê",
        "siblingsPalace": "Huynh Đệ",
    }
    PATTERN_VI_NAME = {
        "huo_tan": "Hỏa Tham",
        "ji_yue_tong_liang": "Cơ Nguyệt Đồng Lương",
        "kui_yue_jia_ming": "Khôi Việt Giáp Mệnh",
        "ling_tan": "Linh Tham",
        "lu_ma_jiao_chi": "Lộc Mã Giao Trì",
        "qi_sha_chao_dou": "Thất Sát Triều Đẩu",
        "ri_yue_bing_ming": "Nhật Nguyệt Tịnh Minh",
        "ri_yue_jia_ming": "Nhật Nguyệt Giáp Mệnh",
        "ri_yue_tong_gong": "Nhật Nguyệt Đồng Cung",
        "sha_po_lang": "Sát Phá Lang",
        "yang_tuo_jia_ming": "Dương Đà Giáp Mệnh",
        "ying_xing_ru_miao": "Anh Tinh Nhập Miếu",
        "zi_fu_tong_gong": "Tử Phủ Đồng Cung",
    }
    STAR_VI_NAME = {
        "guasu": "Quả Tú",
        "jielu": "Tiết Lộ",
        "kongwang": "Không Vong",
        "tiangui": "Thiên Quý",
        "xunkong": "Tuần Không",
    }
    vi_name = {**PALACE_VI_NAME, **PATTERN_VI_NAME, **STAR_VI_NAME}

    coverage = collections.Counter()
    selected: list[dict] = []  # flat list for batched translation
    for r in rows:
        etype = r["entityType"]
        if etype not in ("star", "pattern", "palace"):
            coverage[f"parked_{etype}"] += 1
            continue
        phrases = pick_phrases(r["phrases"], args.top_k, kept=kept)
        if not phrases:
            coverage[f"empty_{etype}"] += 1
            continue
        coverage[etype] += 1
        for p in phrases:
            selected.append(
                {
                    "entityType": etype,
                    "key": r["key"],
                    "name": r.get("name") or "",
                    "zh": p["text"],
                    "count": p["count"],
                    "topics": p["topics"],
                    "vi": None,
                }
            )

    print(
        f"entities: {dict(coverage)} — {len(selected)} phrases to translate"
    )

    if not args.no_translate and selected:
        todo = selected
        for i in range(0, len(todo), args.batch):
            batch = todo[i : i + args.batch]
            try:
                vi = translate_batch([p["zh"] for p in batch])
            except Exception as exc:
                print(f"batch {i//args.batch} failed: {exc} — keep zh")
                vi = None
            for j, p in enumerate(batch):
                p["vi"] = vi[j] if vi else None
            if (i // args.batch) % 4 == 0:
                print(f"translated {i + len(batch)}/{len(todo)}", flush=True)

    for p in selected:
        entry_text = (p["vi"] or p["zh"]).strip()
        sec = {"star": "stars", "pattern": "patterns", "palace": "palaces"}[
            p["entityType"]
        ]
        cur = pack[sec].setdefault(
            p["key"], {"name": vi_name.get(p["key"], p["name"]), "intro": ""}
        )
        if not cur["name"]:
            cur["name"] = p["name"]
        if p["entityType"] == "pattern":
            # schema: pattern excerpts read `quotes`, not `intro`
            cur.setdefault("quotes", []).append(entry_text)
            cur["intro"] = cur["quotes"][0]
        else:
            cur["intro"] = (
                (cur["intro"] + " " + entry_text).strip()
                if cur["intro"]
                else entry_text
            )
        if p["entityType"] == "star" and "category" not in cur:
            e = _zh_pack.star(p["key"])
            cur["category"] = (
                e.category if e and e.category in STAR_CATEGORY else "major"
            )
            if not cur["name"] and e and e.name:
                cur["name"] = e.name

    args.out_pack.parent.mkdir(parents=True, exist_ok=True)
    args.out_pack.write_text(
        json.dumps(pack, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    lines = [
        f"# v0.5 mining coverage — {args.candidates.name}",
        "",
        f"- entities emitted: {dict(coverage)}",
        f"- pack entries: "
        + ", ".join(f"{k}={len(v)}" for k, v in pack.items() if isinstance(v, dict)),
        f"- translated: {sum(1 for p in selected if p['vi'])}/{len(selected)}",
        "",
        "Parked (composite) entities stay in candidates.jsonl for a later "
        "pack-schema extension.",
    ]
    args.report.write_text("\n".join(lines), encoding="utf-8")
    print(f"pack -> {args.out_pack}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
