"""ComparisonComposer — hợp bàn context for two charts (SPEC_COMPATIBILITY §2).

Deterministic pairing evidence: per-side natal facts (soul palace, spouse
palace, 三方四正, natal mutagens, chart-level cục) + `cross_link` items
(birth-stem tứ hóa of A landing in B's palaces, both directions, + soul-branch
chi relation). Scope carries a side tag (`natal:a`, `cross:a→b`,
`yearly:…:b`) so the validator can enforce per-side citations.

LLM ≠ compatibility scorer — this module emits facts only.
"""

import datetime as dt
from typing import Any, Literal

from app.domain.birth.contracts import NormalizedBirthMoment
from app.domain.chart.contracts import (
    CanonicalChartDTO,
    EngineProfile,
)
from app.domain.context.composer import (
    ComposedContext,
    ContextComposer,
    ContextItem,
    TargetScope,
    temporal_scopes_for,
)

Side = Literal["a", "b"]

COMPATIBILITY_TOPIC = "compatibility"

# earthlyBranchKey values end with "Earthly" (e.g. "xuEarthly") — strip it.
_BRANCH_KEYS = [
    "zi",
    "chou",
    "yin",
    "mao",
    "chen",
    "si",
    "wu",
    "wei",
    "shen",
    "you",
    "xu",
    "hai",
]
_BRANCH_LABEL = {
    "zi": "Tý",
    "chou": "Sửu",
    "yin": "Dần",
    "mao": "Mão",
    "chen": "Thìn",
    "si": "Tỵ",
    "wu": "Ngọ",
    "wei": "Mùi",
    "shen": "Thân",
    "you": "Dậu",
    "xu": "Tuất",
    "hai": "Hợi",
}
_TAM_HOP = [
    {"shen", "zi", "chen"},
    {"yin", "wu", "xu"},
    {"hai", "mao", "wei"},
    {"si", "you", "chou"},
]
_LUC_HOP = {
    frozenset(p)
    for p in (
        ("zi", "chou"),
        ("yin", "hai"),
        ("mao", "xu"),
        ("chen", "you"),
        ("si", "shen"),
        ("wu", "wei"),
    )
}
_XUNG = {
    frozenset(p)
    for p in (
        ("zi", "wu"),
        ("chou", "wei"),
        ("yin", "shen"),
        ("mao", "you"),
        ("chen", "xu"),
        ("si", "hai"),
    )
}
_LUC_HAI = {
    frozenset(p)
    for p in (
        ("zi", "wei"),
        ("chou", "wu"),
        ("yin", "si"),
        ("mao", "chen"),
        ("shen", "hai"),
        ("you", "xu"),
    )
}


def _branch_key(raw: str | None) -> str:
    return (raw or "").removesuffix("Earthly")


def chi_relations(branch_a: str | None, branch_b: str | None) -> list[str]:
    """Deterministic soul-branch relation tags (traditional pairing)."""
    a, b = _branch_key(branch_a), _branch_key(branch_b)
    if a not in _BRANCH_KEYS or b not in _BRANCH_KEYS:
        return ["unknown"]
    relations: list[str] = []
    if a == b:
        return ["dong_chi"]
    if any(a in g and b in g for g in _TAM_HOP):
        relations.append("tam_hop")
    if frozenset((a, b)) in _LUC_HOP:
        relations.append("luc_hop")
    if frozenset((a, b)) in _XUNG:
        relations.append("xung")
    if frozenset((a, b)) in _LUC_HAI:
        relations.append("luc_hai")
    return relations or ["neutral"]


def _find_star_palace(dto: CanonicalChartDTO, star_key: str) -> dict[str, Any] | None:
    palace: dict[str, Any] | None = None
    for p in dto.chart["palaces"]:
        for star in p["majorStars"] + p["minorStars"]:
            if star["key"] == star_key:
                palace = p
    return palace


class ComparisonComposer(ContextComposer):
    """compose_pair(dto_a, dto_b) → side-tagged ComposedContext."""

    def compose_pair(
        self,
        normalized_a: NormalizedBirthMoment,
        profile_a: EngineProfile,
        dto_a: CanonicalChartDTO,
        normalized_b: NormalizedBirthMoment,
        profile_b: EngineProfile,
        dto_b: CanonicalChartDTO,
        target_date: dt.date | None = None,
        target_scope: TargetScope | None = None,
        knowledge: Any | None = None,
    ) -> ComposedContext:
        items: list[ContextItem] = []
        scopes = temporal_scopes_for(target_scope)

        sides: list[tuple[Side, NormalizedBirthMoment, EngineProfile, CanonicalChartDTO]] = [
            ("a", normalized_a, profile_a, dto_a),
            ("b", normalized_b, profile_b, dto_b),
        ]
        for side, normalized, profile, dto in sides:
            side_items = self._side_items(side, normalized, profile, dto)
            if scopes:
                side_items += self._horoscope_items(
                    normalized,
                    profile,
                    target_date,
                    scopes,  # type: ignore[arg-type]
                )
            items.extend(self._tag(side_items, side))

        items.extend(self._cross_items(dto_a, dto_b))
        items.extend(self._chi_item(dto_a, dto_b))

        if knowledge is not None:
            items.extend(self._knowledge_items(dto_a, items, knowledge))

        return ComposedContext(
            topic=COMPATIBILITY_TOPIC,
            target_date=target_date,
            scopes_included=list(scopes),
            items=items,
        )

    def _side_items(
        self,
        side: Side,
        normalized: NormalizedBirthMoment,
        profile: EngineProfile,
        dto: CanonicalChartDTO,
    ) -> list[ContextItem]:
        items: list[ContextItem] = []
        if normalized.provisional:
            items.append(
                ContextItem(
                    kind="chart_fact",
                    entity_key="provisional_chart",
                    data={
                        "warning": ("Giờ sinh không rõ — lá số tạm thời, giả định giờ Ngọ (12:00).")
                    },
                )
            )

        c = dto.chart
        items.append(
            ContextItem(
                kind="chart_fact",
                entity_key="astrolabe",
                data={
                    "sign": c.get("sign"),
                    "signKey": c.get("signKey"),
                    "zodiac": c.get("zodiac"),
                    "zodiacKey": c.get("zodiacKey"),
                    "fiveElementsClass": c.get("fiveElementsClass"),
                    "fiveElementsClassKey": c.get("fiveElementsClassKey"),
                    "soul": c.get("soul"),
                    "soulKey": c.get("soulKey"),
                    "body": c.get("body"),
                    "bodyKey": c.get("bodyKey"),
                    "solarDate": c.get("solarDate"),
                    "lunarDate": c.get("rawDates", {}).get("lunarDate"),
                    "soulPalaceBranch": c.get("earthlyBranchOfSoulPalace"),
                    "soulPalaceBranchKey": c.get("earthlyBranchOfSoulPalaceKey"),
                },
            )
        )

        for palace_key in ("soulPalace", "spousePalace"):
            items.extend(self._palace_items(dto, palace_key))
            items.extend(self._surrounded_items(normalized, profile, palace_key))

        items.extend(self._mutagen_items(dto))
        return items

    @staticmethod
    def _tag(items: list[ContextItem], side: Side) -> list[ContextItem]:
        for item in items:
            item.scope = f"{item.scope}:{side}"
        return items

    def _cross_items(self, dto_a: CanonicalChartDTO, dto_b: CanonicalChartDTO) -> list[ContextItem]:
        """Tứ hóa chéo: A's birth-stem mutagens → palace they land in B (and back)."""
        items: list[ContextItem] = []
        for frm, to in (("a", "b"), ("b", "a")):
            source, target = (dto_a, dto_b) if frm == "a" else (dto_b, dto_a)
            for palace in source.chart["palaces"]:
                for star in palace["majorStars"] + palace["minorStars"]:
                    if not star.get("mutagen"):
                        continue
                    lands = _find_star_palace(target, star["key"])
                    lands_key = lands["nameKey"] if lands else "none"
                    items.append(
                        ContextItem(
                            kind="cross_link",
                            scope=f"cross:{frm}→{to}",
                            entity_key=f"{frm}:{star['key']}→{to}:{lands_key}",
                            data={
                                "from_side": frm,
                                "star": star["name"],
                                "starKey": star["key"],
                                "mutagen": star["mutagen"],
                                "mutagenKey": star.get("mutagenKey"),
                                "lands_in": (
                                    {
                                        "palaceKey": lands["nameKey"],
                                        "palaceName": lands["name"],
                                        "branch": lands["earthlyBranch"],
                                        "branchKey": lands["earthlyBranchKey"],
                                    }
                                    if lands
                                    else None
                                ),
                                "note": (None if lands else "không đóng vào cung nào"),
                            },
                        )
                    )
        return items

    def _chi_item(self, dto_a: CanonicalChartDTO, dto_b: CanonicalChartDTO) -> list[ContextItem]:
        branch_a = dto_a.chart.get("earthlyBranchOfSoulPalace")
        branch_b = dto_b.chart.get("earthlyBranchOfSoulPalace")
        key_a = dto_a.chart.get("earthlyBranchOfSoulPalaceKey")
        key_b = dto_b.chart.get("earthlyBranchOfSoulPalaceKey")
        return [
            ContextItem(
                kind="cross_link",
                scope="cross:chi",
                entity_key="soul_branch_relation",
                data={
                    "branchA": branch_a,
                    "branchAKey": key_a,
                    "branchB": branch_b,
                    "branchBKey": key_b,
                    "relations": chi_relations(key_a, key_b),
                },
            )
        ]
