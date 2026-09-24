"""ContextComposer — mandatory selective subgraph (SPEC §9).

No full-chart dumps for topic questions: topic → main palace → 三方四正 →
relevant patterns → relevant horoscope scopes → knowledge excerpts.
Overview is the deliberate exception (compact full-chart + đại hạn summary).
"""

import datetime as dt
from typing import Any, Literal

from pydantic import BaseModel

from app.domain.birth.contracts import NormalizedBirthMoment
from app.domain.chart.contracts import (
    CanonicalChartDTO,
    DomainContext,
    EngineProfile,
    ZiweiEngine,
)

Topic = Literal[
    "overview", "career", "wealth", "love", "health",
    "family", "children", "move", "friends", "home", "spirit", "parents",
]

TOPIC_POLICY: dict[Topic, str | None] = {
    "overview": None,  # compact full chart + đại hạn summary
    "career": "careerPalace",
    "wealth": "wealthPalace",
    "love": "spousePalace",
    "health": "healthPalace",
    "family": "siblingsPalace",
    "children": "childrenPalace",
    "move": "surfacePalace",
    "friends": "friendsPalace",
    "home": "propertyPalace",
    "spirit": "spiritPalace",
    "parents": "parentsPalace",
}

V1_TOPICS = {"overview", "career", "wealth", "love", "health"}

TemporalScope = Literal["decadal", "yearly", "monthly", "daily", "hourly", "age"]

_SIHUA_KEYS = ("sihuaLu", "sihuaQuan", "sihuaKe", "sihuaJi")


class ContextItem(BaseModel):
    """One deterministic unit of context — becomes an EvidenceBundle item."""

    kind: Literal[
        "chart_fact", "palace_fact", "pattern", "mutagen",
        "knowledge", "horoscope_fact",
    ]
    scope: str = "natal"
    palace_key: str = ""
    entity_key: str = ""
    data: dict[str, Any]


class ComposedContext(BaseModel):
    topic: str
    target_date: dt.date | None = None
    scopes_included: list[str] = []
    items: list[ContextItem]


def temporal_scopes_for(target: dt.date | None) -> list[TemporalScope]:
    """SPEC §9: year topic → yearly+decadal+age; month → +monthly; day → +daily."""
    if target is None:
        return []
    return ["decadal", "yearly", "monthly", "daily", "age"]


class ContextComposer:
    def __init__(self, engine: ZiweiEngine) -> None:
        self._engine = engine

    def compose(
        self,
        normalized: NormalizedBirthMoment,
        profile: EngineProfile,
        dto: CanonicalChartDTO,
        topic: Topic = "overview",
        target_date: dt.date | None = None,
        knowledge: Any | None = None,
    ) -> ComposedContext:
        items: list[ContextItem] = []
        scopes: list[TemporalScope] = temporal_scopes_for(target_date)

        if normalized.provisional:
            items.append(
                ContextItem(
                    kind="chart_fact",
                    scope="natal",
                    entity_key="provisional_chart",
                    data={
                        "warning": (
                            "Giờ sinh không rõ — lá số tạm thời, "
                            "giả định giờ Ngọ (12:00)."
                        )
                    },
                )
            )

        main_key = TOPIC_POLICY[topic]
        if main_key is None:
            items.extend(self._overview_items(dto))
        else:
            items.extend(self._palace_items(dto, main_key))
            items.extend(self._surrounded_items(normalized, profile, main_key))

        items.extend(self._pattern_items(dto, main_key))
        items.extend(self._mutagen_items(dto, main_key))

        if scopes:
            items.extend(
                self._horoscope_items(normalized, profile, target_date, scopes)  # type: ignore[arg-type]
            )

        if knowledge is not None:
            items.extend(self._knowledge_items(dto, items, knowledge))

        return ComposedContext(
            topic=topic,
            target_date=target_date,
            scopes_included=list(scopes),
            items=items,
        )

    def _overview_items(self, dto: CanonicalChartDTO) -> list[ContextItem]:
        c = dto.chart
        return [
            ContextItem(
                kind="chart_fact",
                scope="natal",
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
                    "palaces": [
                        {
                            "index": p["index"],
                            "nameKey": p["nameKey"],
                            "name": p["name"],
                            "stemBranch": p["heavenlyStem"] + " " + p["earthlyBranch"],
                            "isBodyPalace": p["isBodyPalace"],
                            "majorStars": [
                                {
                                    "key": s["key"],
                                    "name": s["name"],
                                    "brightness": s.get("brightness") or None,
                                    "mutagen": s.get("mutagen") or None,
                                }
                                for s in p["majorStars"]
                            ],
                            "minorStars": [
                                {"key": s["key"], "name": s["name"]}
                                for s in p["minorStars"]
                            ],
                            "decadal": p.get("decadal"),
                        }
                        for p in c["palaces"]
                    ],
                },
            )
        ]

    def _palace_items(
        self, dto: CanonicalChartDTO, palace_key: str
    ) -> list[ContextItem]:
        palace = next(
            p for p in dto.chart["palaces"] if p["nameKey"] == palace_key
        )
        return [
            ContextItem(
                kind="palace_fact",
                scope="natal",
                palace_key=palace_key,
                entity_key=palace_key,
                data={
                    "index": palace["index"],
                    "name": palace["name"],
                    "stemBranch": palace["heavenlyStem"] + " " + palace["earthlyBranch"],
                    "isBodyPalace": palace["isBodyPalace"],
                    "majorStars": [
                        {
                            "key": s["key"],
                            "name": s["name"],
                            "brightness": s.get("brightness") or None,
                            "mutagen": s.get("mutagen") or None,
                        }
                        for s in palace["majorStars"]
                    ],
                    "minorStars": [
                        {
                            "key": s["key"],
                            "name": s["name"],
                            "mutagen": s.get("mutagen") or None,
                        }
                        for s in palace["minorStars"]
                    ],
                    "decadal": palace.get("decadal"),
                    "ages": palace.get("ages", []),
                },
            )
        ]

    def _surrounded_items(
        self,
        normalized: NormalizedBirthMoment,
        profile: EngineProfile,
        palace_key: str,
    ) -> list[ContextItem]:
        ctx: DomainContext = self._engine.get_surrounded_context(
            normalized, profile, palace_key
        )
        items = []
        for role in ("career", "wealth", "opposite"):
            palace = ctx.context[role]
            items.append(
                ContextItem(
                    kind="palace_fact",
                    scope=f"surrounded:{role}",
                    palace_key=palace["nameKey"],
                    entity_key=palace["nameKey"],
                    data={
                        "index": palace["index"],
                        "name": palace["name"],
                        "stemBranch": palace["heavenlyStem"]
                        + " "
                        + palace["earthlyBranch"],
                        "majorStars": [
                            {"key": s["key"], "name": s["name"]}
                            for s in palace["majorStars"]
                        ],
                        "minorStars": [
                            {"key": s["key"], "name": s["name"]}
                            for s in palace["minorStars"]
                        ],
                    },
                )
            )
        return items

    def _pattern_items(
        self, dto: CanonicalChartDTO, palace_key: str | None
    ) -> list[ContextItem]:
        patterns = dto.chart.get("patterns", [])
        if palace_key is not None:
            target_index = next(
                p["index"] for p in dto.chart["palaces"] if p["nameKey"] == palace_key
            )
            # 三方四正 indices: target, ±4, opposite(+6)
            related = {
                target_index,
                (target_index + 4) % 12,
                (target_index - 4) % 12,
                (target_index + 6) % 12,
            }
            patterns = [
                p
                for p in patterns
                if p.get("palace_index") in related or p.get("scope") == "global"
            ]
        return [
            ContextItem(
                kind="pattern",
                scope="natal",
                entity_key=p["key"],
                data={
                    "name": p.get("name"),
                    "scope": p.get("scope"),
                    "broken": p.get("broken"),
                    "stars": p.get("stars"),
                },
            )
            for p in patterns
        ]

    def _mutagen_items(
        self, dto: CanonicalChartDTO, palace_key: str | None
    ) -> list[ContextItem]:
        items = []
        for palace in dto.chart["palaces"]:
            if palace_key is not None and palace["nameKey"] != palace_key:
                continue
            for star in palace["majorStars"] + palace["minorStars"]:
                if star.get("mutagen"):
                    items.append(
                        ContextItem(
                            kind="mutagen",
                            scope="natal",
                            palace_key=palace["nameKey"],
                            entity_key=star["key"],
                            data={
                                "starName": star["name"],
                                "starKey": star["key"],
                                "mutagen": star["mutagen"],
                                "mutagenKey": star.get("mutagenKey"),
                                "palace": palace["name"],
                                "palaceKey": palace["nameKey"],
                            },
                        )
                    )
        return items

    def _horoscope_items(
        self,
        normalized: NormalizedBirthMoment,
        profile: EngineProfile,
        target_date: dt.date | None,
        scopes: list[TemporalScope],
    ) -> list[ContextItem]:
        assert target_date is not None
        horoscope = self._engine.get_horoscope(normalized, profile, target_date)
        items = []
        for scope in scopes:
            if scope not in horoscope.context:
                continue
            data = dict(horoscope.context[scope])
            if data.get("mutagen"):
                # 四化 surface names (Lộc/Quyền/Khoa/Kỵ) are citable for any
                # mutagenized scope — the year's hóa set is bounded to these.
                data["sihuaKeys"] = list(_SIHUA_KEYS)
            items.append(
                ContextItem(
                    kind="horoscope_fact",
                    scope=f"{scope}:{target_date.isoformat()}",
                    entity_key=scope,
                    data=data,
                )
            )
        return items

    def _knowledge_items(
        self,
        dto: CanonicalChartDTO,
        fact_items: list[ContextItem],
        knowledge: Any,
    ) -> list[ContextItem]:
        """Knowledge excerpts for every entity already in context (SPEC §9)."""
        items: list[ContextItem] = []
        seen: set[tuple[str, str]] = set()
        for item in fact_items:
            candidates: list[tuple[str, str]] = []
            if item.kind == "pattern":
                candidates.append(("pattern", item.entity_key))
            if item.kind == "palace_fact":
                candidates.append(("palace", item.entity_key))
                for star in item.data.get("majorStars", []):
                    candidates.append(("star", star["key"]))
            for star in item.data.get("minorStars", []):
                if isinstance(star, dict) and star.get("key", "").endswith(
                    ("Maj", "Min")
                ):
                    candidates.append(("star", star["key"]))
            for type_, key in candidates:
                if (type_, key) in seen:
                    continue
                seen.add((type_, key))
                excerpt = (
                    knowledge.star_excerpt(key)
                    if type_ == "star"
                    else knowledge.pattern_excerpt(key)
                    if type_ == "pattern"
                    else knowledge.palace_excerpt(key)
                )
                if excerpt is not None:
                    items.append(
                        ContextItem(
                            kind="knowledge",
                            entity_key=key,
                            data=excerpt,
                        )
                    )
        return items
