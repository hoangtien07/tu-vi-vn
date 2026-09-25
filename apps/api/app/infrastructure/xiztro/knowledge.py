"""KnowledgeRegistry — sole access point for the built-in zh-CN knowledge pack.

Chart facts come from the engine (language=vi-VN); the knowledge pack is zh-CN
lore for the LLM to read-and-rephrase, never chart data (SPEC §7–9).
"""

import dataclasses
import json
import threading
from pathlib import Path
from typing import TYPE_CHECKING, Any, cast

if TYPE_CHECKING:
    from x_iztro.astro import LanguageType

from x_iztro import KnowledgePack
from x_iztro.knowledge import PatternEntry, StarEntry

PACK_LANGUAGE = cast("LanguageType", "zh-CN")
EXCERPT_MAX_CHARS = 300


def _excerpt(text: str, limit: int = EXCERPT_MAX_CHARS) -> str:
    """Cut at a sentence boundary within `limit` chars."""
    if len(text) <= limit:
        return text
    cut = text[:limit]
    for sep in ("。", "；", "，", ".", ";", ",", " "):
        idx = cut.rfind(sep)
        if idx >= limit // 3:
            return cut[: idx + 1]
    return cut


class KnowledgeRegistry:
    """Lazy singleton; pack source is explicit (SPEC_V04 I17).

    `configure()` selects the lore source once per process:
    "builtin" (default) → zh-CN builtin pack; "none" → ablation provider
    (every excerpt returns None); otherwise a path to a `from_dict` pack
    file (eval/packs/*.json). Callers use the class methods — the
    composer does not need to know which source is active.
    """

    _lock = threading.Lock()
    _source = "builtin"
    _pack: KnowledgePack | None = None
    _none = False

    @classmethod
    def configure(cls, source: str) -> None:
        """Select the pack source; resets any cached pack."""
        with cls._lock:
            cls._source = source or "builtin"
            cls._pack = None
            cls._none = cls._source == "none"

    @classmethod
    def active_pack(cls) -> KnowledgePack:
        with cls._lock:
            if cls._pack is None:
                if cls._source == "none":
                    raise RuntimeError("knowledge pack disabled (KNOWLEDGE_PACK=none)")
                if cls._source in ("", "builtin"):
                    cls._pack = KnowledgePack.builtin(PACK_LANGUAGE)
                else:
                    cls._pack = KnowledgePack.from_dict(
                        json.loads(Path(cls._source).read_text())
                    )
            return cls._pack

    @classmethod
    def version_info(cls) -> dict[str, Any]:
        if cls._none:
            return {
                "id": "none",
                "version": "0",
                "language": "none",
                "sourceUrl": "",
                "sourceCommit": "",
                "license": "",
            }
        pack = cls.active_pack()
        return {
            "id": pack.id,
            "version": pack.version,
            "language": pack.language,
            "sourceUrl": pack.source.url,
            "sourceCommit": pack.source.commit,
            "license": pack.source.license,
        }

    @classmethod
    def star_excerpt(cls, star_key: str) -> dict[str, Any] | None:
        if cls._none:
            return None
        entry: StarEntry | None = cls.active_pack().star(star_key)
        if entry is None:
            return None
        return {
            "key": entry.key,
            "name": entry.name,
            "category": entry.category,
            "attributes": (
                dataclasses.asdict(entry.attributes)
                if entry.attributes is not None
                else None
            ),
            "excerpt": _excerpt(entry.intro or ""),
        }

    @classmethod
    def pattern_excerpt(cls, pattern_key: str) -> dict[str, Any] | None:
        if cls._none:
            return None
        entry: PatternEntry | None = cls.active_pack().pattern(pattern_key)
        if entry is None:
            return None
        return {
            "key": entry.key,
            "name": entry.name,
            "quotes": (getattr(entry, "quotes", None) or [])[:3],
        }

    @classmethod
    def palace_excerpt(cls, palace_key: str) -> dict[str, Any] | None:
        if cls._none:
            return None
        entry = cls.active_pack().palace(palace_key)
        if entry is None:
            return None
        intro = getattr(entry, "intro", "") or ""
        return {
            "key": getattr(entry, "key", palace_key),
            "name": getattr(entry, "name", ""),
            "excerpt": _excerpt(intro),
        }
