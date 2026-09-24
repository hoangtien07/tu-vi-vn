"""GroundingValidator — 4 deterministic checks (SPEC §12).

1. ref-existence: every [E###] must exist in the bundle.
2. closed-world entity: any glossary star/palace/mutagen/pattern name in the
   output must belong to the bundle's entity vocab.
3. evidence-type ↔ claim-scope: temporal claims must cite ≥1 horoscope_fact.
4. orphan-claim flag: entity mention without [E###] → flag, not reject.
"""

import re
from typing import NamedTuple

from app.domain.evidence.builder import EvidenceBundle
from app.repo_root import repo_file

# Citations appear as [E001], [E001, E007], [E001][E007] — a ref is any E###
# token inside a bracketed group.
_REF_GROUP_RE = re.compile(r"\[([^\]]*)\]")
_REF_TOKEN_RE = re.compile(r"\bE(\d{3})\b")


def _refs(text: str) -> set[str]:
    return {
        f"E{n}"
        for group in _REF_GROUP_RE.findall(text)
        for n in _REF_TOKEN_RE.findall(group)
    }
SENTENCE_SPLIT = re.compile(r"(?<=[.!?…。；\n])\s*")
# Scope-specific temporal terms only — the generic words "vận hạn" and
# "tương lai" appear in boilerplate ("chỉ mang tính tham khảo về xu hướng",
# "không ấn định bất biến tương lai") where a ref is meaningless; only
# scope-bearing claims (đại hạn/lưu niên/tiểu hạn/năm NNNN/tháng N/sắp tới)
# are the ones zero-tolerance applies to.
TEMPORAL_RE = re.compile(
    r"(?i)(năm\s+\d{4}|tháng\s+\d{1,2}|đại hạn|lưu niên|tiểu hạn|sắp tới)"
)

# Glossary surface forms that double as ordinary Vietnamese words — flagging
# them as "invented" would false-positive (e.g. "Miếu" = temple or brightness
# grade; "Hạn" = limit; "Bệnh" = illness). All 10 heavenly stems / 12 earthly
# branches are single syllables that legitimately compose palace names
# ("Mậu Ngọ", "Giáp Thân") — exempting them keeps the closed-world check on
# what matters: star/palace/pattern names the model could hallucinate.
_AMBIGUOUS_NAMES = {
    "Hạn", "Miếu", "Vượng", "Bình", "Hãm", "Lợi", "Đắc", "Địa", "Bất", "Bệnh",
    "Cục", "Thân", "Dưỡng", "Thai",
    "Giáp", "Ất", "Bính", "Đinh", "Mậu", "Kỷ", "Canh", "Tân", "Nhâm", "Quý",
    "Tý", "Sửu", "Dần", "Mão", "Thìn", "Tỵ", "Ngọ", "Mùi", "Dậu", "Tuất", "Hợi",
}

# Fixed boilerplate tail ("## Lưu ý …") and the school name "Tử Vi Đẩu Số" are
# template text, not entity citations — "Tử Vi" there names the art, not the
# star in this chart's bundle.
_BOILERPLATE_RE = re.compile(r"(?m)^\s*[-#*]*\s*Lưu ý\b.*$")
_SCHOOL_NAME = "Tử Vi Đẩu Số"


def _scannable_text(output: str) -> str:
    m = _BOILERPLATE_RE.search(output)
    text = output[: m.start()] if m else output
    return text.replace(_SCHOOL_NAME, "")

GLOSSARY_PATH = repo_file("packages", "knowledge", "glossary-vi.md")


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


_VOCAB_KEY_FIELDS = {
    "key",
    "nameKey",
    "starKey",
    "mutagenKey",
    "patternKey",
    "palaceKey",
    "stemKey",
    "branchKey",
    "entity_key",
}
_NAME_FIELDS = {"name", "starName", "palaceName"}


def _walk(obj: object) -> tuple[set[str], set[str]]:
    """Recursively collect (vocab keys, display names) from nested data."""
    keys: set[str] = set()
    names: set[str] = set()
    if isinstance(obj, dict):
        for field, value in obj.items():
            if isinstance(value, str):
                if field in _VOCAB_KEY_FIELDS or (
                    len(field) > 3 and field.endswith(("Key", "Keys"))
                ):
                    keys.add(value)
                elif field in _NAME_FIELDS:
                    names.add(value)
            elif isinstance(value, list) and field.endswith(("Key", "Keys")):
                for elem in value:
                    if isinstance(elem, str):
                        keys.add(elem)
                    else:
                        k2, n2 = _walk(elem)
                        keys |= k2
                        names |= n2
            else:
                k2, n2 = _walk(value)
                keys |= k2
                names |= n2
    elif isinstance(obj, list):
        for value in obj:
            k2, n2 = _walk(value)
            keys |= k2
            names |= n2
    return keys, names


def bundle_vocab(bundle: EvidenceBundle) -> set[str]:
    keys: set[str] = set()
    for item in bundle.items:
        if item.entity_key:
            keys.add(item.entity_key)
        keys |= _walk(item.data)[0]
    return keys


def _bundle_names(bundle: EvidenceBundle) -> set[str]:
    names: set[str] = set()
    for item in bundle.items:
        names |= _walk(item.data)[1]
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


_BOLD_LABEL_RE = re.compile(r"[-*\s]*\*\*[^*\n]+\*\*:?")


def _sentences(text: str) -> list[str]:
    # Markdown headings, bold pseudo-headings ("- **Lưu Niên:**"), and
    # lead-in sentences ending with a colon are labels, not claims.
    body = "\n".join(
        line for line in text.splitlines() if not line.lstrip().startswith("#")
    )
    return [
        s.strip()
        for s in SENTENCE_SPLIT.split(body)
        if s.strip()
        and not _BOLD_LABEL_RE.fullmatch(s.strip())
        and not s.rstrip().endswith(":")
    ]


def validate(output: str, bundle: EvidenceBundle) -> ValidationResult:
    known_ids = {item.id for item in bundle.items}
    horoscope_ids = {i.id for i in bundle.items if i.kind == "horoscope_fact"}
    vocab = bundle_vocab(bundle)
    entity_names = _bundle_names(bundle)

    refs = _refs(output)
    unknown = sorted(refs - known_ids)

    invented: set[str] = set()
    scan = _scannable_text(output)
    for key, vi_name in _VI_NAMES.items():
        if key in vocab or len(vi_name) < 3 or vi_name in _AMBIGUOUS_NAMES:
            continue
        if vi_name in scan:
            invented.add(f"{vi_name}({key})")

    temporal: list[str] = []
    orphans: list[str] = []
    for sentence in _sentences(output):
        s_refs = _refs(sentence)
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
        {"text": s, "refs": sorted(_refs(s))}
        for s in _sentences(output)
        if _refs(s)
    ]
