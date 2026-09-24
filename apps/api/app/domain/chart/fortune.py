import datetime as dt
from typing import Any

from sqlalchemy.orm import Session

from app.domain.birth.contracts import NormalizedBirthMoment
from app.domain.chart.contracts import EngineProfile, ZiweiEngine
from app.infrastructure.db.models import (
    ChartSnapshot,
    EngineProfileRow,
    NormalizedBirthMomentRow,
)
from app.infrastructure.xiztro.calendar import lunar_to_solar

FORTUNE_SCOPES = ("decadal", "yearly", "age")


class FortuneTargetBeforeBirthError(ValueError):
    pass


def year_anchor(year: int) -> dt.date:
    """Anchor date convention (SPEC §16): Tết Âm lịch of the requested year."""
    return lunar_to_solar(dt.date(year, 1, 1), False)


class FortuneService:
    def __init__(self, engine: ZiweiEngine) -> None:
        self._engine = engine

    def yearly(
        self, session: Session, snapshot: ChartSnapshot, year: int
    ) -> dict[str, Any]:
        anchor = year_anchor(year)
        normalized = _load_normalized(session, snapshot)
        if anchor < normalized.correctedSolarDate:
            raise FortuneTargetBeforeBirthError(
                f"anchor {anchor} precedes birth {normalized.correctedSolarDate}"
            )
        profile = _load_profile(session, snapshot)
        context = self._engine.get_horoscope(normalized, profile, anchor).context
        return {
            "chartId": snapshot.id,
            "year": year,
            "anchorDate": anchor.isoformat(),
            "scopes": {k: context[k] for k in FORTUNE_SCOPES if k in context},
        }


def _load_normalized(
    session: Session, snapshot: ChartSnapshot
) -> NormalizedBirthMoment:
    row = session.get(
        NormalizedBirthMomentRow, snapshot.normalized_birth_moment_id
    )
    if row is None:
        raise LookupError("normalized birth moment missing")
    return NormalizedBirthMoment.model_validate(row.payload)


def _load_profile(session: Session, snapshot: ChartSnapshot) -> EngineProfile:
    row = session.get(EngineProfileRow, snapshot.engine_profile_id)
    if row is None:
        raise LookupError("engine profile missing")
    return EngineProfile.model_validate(row.content)
