import hashlib
import json
from typing import Any

from app.domain.birth.contracts import NormalizedBirthMoment
from app.domain.chart.contracts import DTO_SCHEMA_VERSION, EngineProfile


def canonical_json(obj: Any) -> str:
    """Sorted keys + UTF-8 + no whitespace (SPEC §6 reproducibility contract)."""
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str)


def chart_hash(birth: NormalizedBirthMoment, profile: EngineProfile) -> str:
    """sha256 over the decision inputs — normalized birth + engine + profile versions."""
    parts = [
        canonical_json(birth.model_dump(mode="json")),
        profile.engineVersion,
        canonical_json(profile.model_dump(mode="json")),
        birth.normalizerVersion,
        str(DTO_SCHEMA_VERSION),
    ]
    return hashlib.sha256("\n".join(parts).encode("utf-8")).hexdigest()
