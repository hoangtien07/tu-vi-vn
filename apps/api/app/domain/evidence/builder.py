"""EvidenceBuilder — ComposedContext → EvidenceBundle with stable E### IDs.

Deterministic ordering: stable sort by (kind, palace_key, entity_key) — the
same context always yields the same IDs, so claims can be audited.
IDs are allocated per InterpretationRun/conversation — never reused across
context-build calls (SPEC §11).
"""

from typing import Any

from pydantic import BaseModel, Field

from app.domain.context.composer import ComposedContext, ContextItem

KIND_ORDER = [
    "chart_fact",
    "palace_fact",
    "mutagen",
    "pattern",
    "horoscope_fact",
    "cross_link",
    "knowledge",
]

_SOURCE_BY_KIND = {
    "chart_fact": "x-iztro",
    "palace_fact": "x-iztro",
    "mutagen": "x-iztro",
    "pattern": "x-iztro-pattern-engine",
    "horoscope_fact": "x-iztro",
    "cross_link": "x-iztro",
    "knowledge": "iztro-docs",
}


class EvidenceItem(BaseModel):
    id: str
    kind: str
    source: str
    scope: str = "natal"
    palace_key: str = ""
    entity_key: str = ""
    data: dict[str, Any]
    source_version: str | None = None


class EvidenceBundle(BaseModel):
    id: str
    topic: str
    items: list[EvidenceItem]
    knowledge_version: str | None = None
    context_hash: str = ""
    allocator_state: dict[str, int] = Field(default_factory=dict)


class EvidenceBuilder:
    """Deterministic builder — same ComposedContext in, same bundle out."""

    def __init__(self, knowledge_version: str | None = None) -> None:
        self._knowledge_version = knowledge_version

    @staticmethod
    def _sort_key(item: ContextItem) -> tuple[int, str, str]:
        return (
            KIND_ORDER.index(item.kind),
            item.palace_key,
            item.entity_key,
        )

    def build(self, context: ComposedContext, bundle_id: str) -> EvidenceBundle:
        items = [
            EvidenceItem(
                id=f"E{i:03d}",
                kind=item.kind,
                source=_SOURCE_BY_KIND[item.kind],
                scope=item.scope,
                palace_key=item.palace_key,
                entity_key=item.entity_key,
                data=item.data,
                source_version=(
                    self._knowledge_version if item.kind == "knowledge" else None
                ),
            )
            for i, item in enumerate(
                sorted(context.items, key=self._sort_key), start=1
            )
        ]
        return EvidenceBundle(
            id=bundle_id,
            topic=context.topic,
            items=items,
            knowledge_version=self._knowledge_version,
        )

    @staticmethod
    def vocab_keys(bundle: EvidenceBundle) -> set[str]:
        """Closed-world entity vocab for GroundingValidator (SPEC §12 check 2)."""
        keys: set[str] = set()
        for item in bundle.items:
            if item.entity_key:
                keys.add(item.entity_key)
            for star_list in ("majorStars", "minorStars"):
                for star in item.data.get(star_list, []):
                    if star.get("key"):
                        keys.add(star["key"])
        return keys
