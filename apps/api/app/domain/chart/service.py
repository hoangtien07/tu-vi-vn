import secrets
import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain.birth.contracts import NormalizedBirthMoment
from app.domain.chart.contracts import DTO_SCHEMA_VERSION, EngineProfile, ZiweiEngine
from app.domain.chart.hashing import chart_hash
from app.infrastructure.db.models import (
    BirthProfile,
    ChartSnapshot,
    EngineProfileRow,
    NormalizedBirthMomentRow,
    RawBirthInputRow,
)


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:24]}"


def load_engine_profile(session: Session, profile_id: str = "iztro-default-v1") -> EngineProfile:
    row = session.get(EngineProfileRow, profile_id)
    if row is None:
        raise LookupError(f"engine profile not found: {profile_id}")
    return EngineProfile.model_validate(row.content)


class ChartService:
    def __init__(self, engine: ZiweiEngine) -> None:
        self._engine = engine

    def cast_and_persist(
        self,
        session: Session,
        raw_payload: dict[str, Any],
        normalized: NormalizedBirthMoment,
        profile: EngineProfile,
    ) -> ChartSnapshot:
        """Persist birth chain + immutable chart snapshot (SPEC §6).

        Idempotent on chart_hash: re-casting the same normalized birth under the
        same profile returns the existing snapshot.
        """
        digest = chart_hash(normalized, profile)
        existing = session.scalar(
            select(ChartSnapshot).where(ChartSnapshot.chart_hash == digest)
        )
        if existing is not None:
            return existing

        dto = self._engine.cast_chart(normalized, profile)

        birth_profile = BirthProfile(id=new_id("bp"))
        raw = RawBirthInputRow(
            id=new_id("rb"), birth_profile_id=birth_profile.id, payload=raw_payload
        )
        norm = NormalizedBirthMomentRow(
            id=new_id("nb"),
            raw_birth_input_id=raw.id,
            payload=normalized.model_dump(mode="json"),
        )
        snapshot = ChartSnapshot(
            id=new_id("cs"),
            birth_profile_id=birth_profile.id,
            normalized_birth_moment_id=norm.id,
            engine=profile.engine,
            engine_version=profile.engineVersion,
            engine_profile_id=profile.id,
            chart_hash=digest,
            dto_schema_version=DTO_SCHEMA_VERSION,
            chart_json=dto.model_dump(mode="json"),
            pattern_hits=dto.chart.get("patterns", []),
            share_token=secrets.token_urlsafe(24),
        )
        session.add_all([birth_profile, raw, norm, snapshot])
        session.commit()
        return snapshot
