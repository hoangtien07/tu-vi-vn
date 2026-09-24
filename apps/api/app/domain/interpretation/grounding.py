"""GroundingValidator — 4 deterministic checks (SPEC §12).

1. ref-existence: every [E###] must exist in the bundle.
2. closed-world entity: any glossary star/palace/mutagen/pattern name in the
   output must belong to the bundle's entity vocab.
3. evidence-type ↔ claim-scope: temporal claims must cite ≥1 horoscope_fact.
4. orphan-claim flag: entity mention without [E###] → flag, not reject.
"""

import re
from pathlib import Path
from typing import NamedTuple

from app.domain.evidence.builder import EvidenceBundle

REF_RE = re.compile(r"\[E(\d{3})\]")
SENTENCE_SPLIT = re.compile(r"(?<=[.!?…。；\n])\s*")
TEMPORAL_RE = re.compile(
    r"(?i)(năm\s+\d{4}|tháng\s+\d{1,2}|đại hạn|lưu niên|vận hạn|tiểu hạn|"
    r"sắp tới|tương lai|hiện tại)"
)

GLOSSARY_PATH = (
    Path(__file__).resolve().parents[4] / "packages" / "knowledge" / "glossary-vi.md"
)


def _load_vi_names() -> dict[str, str]:
    """key → vi surface name from the generated glossary."""
    names: dict[str, str] = {}
    if not GLOSSARY_PATH.exists():
        return names
    for line in GLOSSARY_PATH.read_text(encoding="utf-8").splitlines():
        if not line.startswith("|") or line.startswith("| key") or "---" in line:
            continue
        cells = [c.strip() for c in line.strip("|").split("|")]
        if len(cells) >= 3 and cells[2]:
            names[cells[0]] = cells[2]
    return names


_VI_NAMES = _load_vi_names()


def bundle_vocab(bundle: EvidenceBundle) -> set[str]:
    keys: set[str] = set()
    for item in bundle.items:
        if item.entity_key:
            keys.add(item.entity_key)
        for field in ("majorStars", "minorStars", "stars"):
            for star in item.data.get(field, []) or []:
                if isinstance(star, dict) and star.get("key"):
                    keys.add(star["key"])
    return keys


def _bundle_names(bundle: EvidenceBundle) -> set[str]:
    names: set[str] = set()
    for item in bundle.items:
        for field in ("majorStars", "minorStars", "stars"):
            for star in item.data.get(field, []) or []:
                if isinstance(star, dict) and star.get("name"):
                    names.add(star["name"])
        if item.data.get("name"):
            names.add(str(item.data["name"]))
        if item.data.get("starName"):
            names.add(str(item.data["starName"]))
    return names


class ValidationResult(NamedTuple):
    ok: bool
    unknown_refs: list[str]
    invented_entities: list[str]
    temporal_unverified: list[str]
    orphan_claims: list[str]

    @property
    def violations(self) -> list[str]:
        out = []
        if self.unknown_refs:
            out.append("tham chiếu không tồn tại: " + ", ".join(self.unknown_refs))
        if self.invented_entities:
            out.append(
                "thực thể không có trong bằng chứng: "
                + ", ".join(self.invented_entities)
            )
        if self.temporal_unverified:
            out.append(
                "nhận định vận hạn thiếu horoscope_fact: "
                + ", ".join(self.temporal_unverified)
            )
        return out


def _sentences(text: str) -> list[str]:
    return [s.strip() for s in SENTENCE_SPLIT.split(text) if s.strip()]


def validate(output: str, bundle: EvidenceBundle) -> ValidationResult:
    known_ids = {item.id for item in bundle.items}
    horoscope_ids = {i.id for i in bundle.items if i.kind == "horoscope_fact"}
    vocab = bundle_vocab(bundle)
    entity_names = _bundle_names(bundle)

    refs = {f"E{m}" for m in REF_RE.findall(output)}
    unknown = sorted(refs - known_ids)

    invented: set[str] = set()
    for key, vi_name in _VI_NAMES.items():
        if key in vocab or len(vi_name) < 3:
            continue
        if vi_name in output:
            invented.add(f"{vi_name}({key})")

    temporal: list[str] = []
    orphans: list[str] = []
    for sentence in _sentences(output):
        s_refs = {f"E{m}" for m in REF_RE.findall(sentence)}
        if TEMPORAL_RE.search(sentence) and not (s_refs & horoscope_ids):
            temporal.append(sentence[:120])
        if not s_refs and any(name in sentence for name in entity_names):
            orphans.append(sentence[:120])

    return ValidationResult(
        ok=not unknown and not invented and not temporal,
        unknown_refs=unknown,
        invented_entities=sorted(invented),
        temporal_unverified=temporal[:10],
        orphan_claims=orphans[:10],
    )


def extract_claims(output: str) -> list[dict[str, object]]:
    """Post-stream claim↔evidence pairs for the InterpretationRun."""
    return [
        {"text": s, "refs": [f"E{m}" for m in REF_RE.findall(s)]}
        for s in _sentences(output)
        if REF_RE.search(s)
    ]
