"""SPEC_V02 §4 — deterministic temporal facts (no LLM) + reading history."""

import datetime as dt
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field, model_validator
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain.birth.contracts import NormalizedBirthMoment
from app.domain.chart.contracts import EngineProfile
from app.domain.chart.fortune import year_anchor
from app.infrastructure.db.models import (
    ChartSnapshot,
    EngineProfileRow,
    InterpretationRun,
    NormalizedBirthMomentRow,
)
from app.infrastructure.db.session import get_session

router = APIRouter(prefix="/api/charts", tags=["temporal"])


class TemporalQuery(BaseModel):
    """I10: scope fields mirror InterpretTarget; only provided layers return."""

    year: int | None = Field(default=None, ge=1583, le=9999)
    month: int | None = Field(default=None, ge=1, le=12)
    day: int | None = Field(default=None, ge=1, le=31)

    @model_validator(mode="after")
    def _fields_consistent(self) -> "TemporalQuery":
        if self.month is not None and self.year is None:
            raise ValueError("month requires year")
        if self.day is not None and self.month is None:
            raise ValueError("day requires month")
        return self


def _load_normalized(
    snapshot: ChartSnapshot, session: Session
) -> tuple[NormalizedBirthMoment, EngineProfile]:
    row = session.get(NormalizedBirthMomentRow, snapshot.normalized_birth_moment_id)
    if row is None:
        raise HTTPException(status_code=500, detail="normalized birth missing")
    ep = session.get(EngineProfileRow, snapshot.engine_profile_id)
    if ep is None:
        raise HTTPException(status_code=500, detail="engine profile missing")
    return (
        NormalizedBirthMoment.model_validate(row.payload),
        EngineProfile.model_validate(ep.content),
    )


@router.get("/{chart_id}/temporal")
def temporal_facts(
    chart_id: str,
    request: Request,
    year: int | None = None,
    month: int | None = None,
    day: int | None = None,
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    """Deterministic horoscope layers for the navigator — no LLM (SPEC_V02 §4).

    `decadal` always present; `yearly` needs ?year, `monthly` needs ?year&month,
    `daily` needs all three. Values are raw engine facts the FE renders.
    """
    snapshot = session.get(ChartSnapshot, chart_id)
    if snapshot is None:
        raise HTTPException(status_code=404, detail="chart not found")
    try:
        q = TemporalQuery(year=year, month=month, day=day)
    except Exception as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    normalized, profile = _load_normalized(snapshot, session)
    try:
        anchor = dt.date.today()
        if q.day is not None and q.month is not None and q.year is not None:
            anchor = dt.date(q.year, q.month, q.day)
        elif q.month is not None and q.year is not None:
            anchor = dt.date(q.year, q.month, 1)
        elif q.year is not None:
            # Yearly facts anchored at Tết Âm lịch — same anchor interpret uses.
            anchor = year_anchor(q.year)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    if anchor < normalized.correctedSolarDate:
        raise HTTPException(
            status_code=422, detail="target precedes birth date"
        )

    horoscope = request.app.state.ziwei_engine.get_horoscope(
        normalized, profile, anchor
    )
    ctx = horoscope.context
    layers = {
        "decadal": ctx.get("decadal"),
        "yearly": ctx.get("yearly") if q.year else None,
        "monthly": ctx.get("monthly") if q.month else None,
        "daily": ctx.get("daily") if q.day else None,
    }
    return {
        "chartId": chart_id,
        "anchor": anchor.isoformat(),
        **layers,
        "scopesIncluded": [s for s, v in layers.items() if v is not None],
    }


_DECADE_WALK = 12  # đại hạn spans ≤10 yrs; 12 probes always finds a boundary


def _scope_brief(
    scope: dict[str, Any], natal_palaces: list[dict[str, Any]] | None = None
) -> dict[str, Any]:
    idx = scope.get("index")
    if (
        isinstance(idx, int)
        and natal_palaces is not None
        and 0 <= idx < len(natal_palaces)
    ):
        # SPEC_KLINE: glyph label = natal palace hosting the scope's mệnh.
        # The scope's own palaceNames[] is the rebased temporal layout —
        # position `index` there is always the scope's Mệnh (constant, useless).
        host = {
            "palaceName": natal_palaces[idx].get("name"),
            "palaceNameKey": natal_palaces[idx].get("nameKey"),
        }
    else:
        names = scope.get("palaceNames") or []
        keys = scope.get("palaceNameKeys") or []
        host = (
            {"palaceName": names[idx], "palaceNameKey": keys[idx]}
            if isinstance(idx, int) and 0 <= idx < len(names) and idx < len(keys)
            else {"palaceName": None, "palaceNameKey": None}
        )
    return {
        "index": idx,
        "name": scope.get("name"),
        **host,
        "mutagen": scope.get("mutagen") or [],
        "mutagenStarKeys": scope.get("mutagenStarKeys") or [],
        "heavenlyStem": scope.get("heavenlyStem"),
        "earthlyBranch": scope.get("earthlyBranch"),
    }


@router.get("/{chart_id}/temporal/decade")
def temporal_decade(
    chart_id: str,
    request: Request,
    year: int,
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    """SPEC_KLINE — one K-line glyph per lưu niên across the đại hạn holding `year`.

    Boundary = where `decadal.index` changes (probed per-year), never tuổi-mụ
    arithmetic — no lunar-year off-by-one. Scope payloads are compact
    (`_scope_brief`); `stars` intentionally omitted.
    """
    if year < 1583 or year > 9999:
        raise HTTPException(status_code=422, detail="year out of range")
    snapshot = session.get(ChartSnapshot, chart_id)
    if snapshot is None:
        raise HTTPException(status_code=404, detail="chart not found")
    normalized, profile = _load_normalized(snapshot, session)
    birth = normalized.correctedSolarDate
    engine = request.app.state.ziwei_engine

    if year_anchor(year) < birth:
        raise HTTPException(status_code=422, detail="target precedes birth date")

    def dec_index(y: int) -> int | None:
        scope = engine.get_horoscope(normalized, profile, year_anchor(y)).context.get(
            "decadal"
        ) or {}
        return scope.get("index")

    palaces = (snapshot.chart_json.get("chart") or {}).get("palaces") or []

    host_idx = dec_index(year)
    y0 = year
    for y in range(year - 1, year - _DECADE_WALK, -1):
        if year_anchor(y) < birth or dec_index(y) != host_idx:
            break
        y0 = y
    y1 = year
    for y in range(year + 1, year + _DECADE_WALK):
        if dec_index(y) != host_idx:
            break
        y1 = y

    years = []
    for y in range(y0, y1 + 1):
        scope = engine.get_horoscope(normalized, profile, year_anchor(y)).context
        brief = _scope_brief(scope["yearly"], palaces)
        brief.pop("name", None)
        years.append({"year": y, "yearlyIndex": brief.pop("index"), **brief})

    decadal = _scope_brief(
        engine.get_horoscope(normalized, profile, year_anchor(year)).context["decadal"],
        palaces,
    )
    age_range = None
    if isinstance(host_idx, int) and 0 <= host_idx < len(palaces):
        age_range = (palaces[host_idx].get("decadal") or {}).get("range")
    return {
        "chartId": chart_id,
        "decadal": {**decadal, "ageRange": age_range},
        "years": years,
        "yearRange": [y0, y1],
    }


@router.get("/{chart_id}/readings/{run_id}")
def get_reading(
    chart_id: str, run_id: str, session: Session = Depends(get_session)
) -> dict[str, Any]:
    """Replay a saved run — same input + versions returns the stored output."""
    r = session.get(InterpretationRun, run_id)
    if r is None or (
        r.chart_snapshot_id != chart_id and r.partner_chart_snapshot_id != chart_id
    ):
        raise HTTPException(status_code=404, detail="reading not found")
    return {
        "id": r.id,
        "topic": r.topic,
        "status": r.status,
        "isCompatibility": r.partner_chart_snapshot_id is not None,
        "targetDate": (r.version_meta or {}).get("targetDate"),
        "outputText": r.output_text,
        "createdAt": r.created_at,
    }


@router.get("/{chart_id}/readings")
def list_readings(
    chart_id: str, session: Session = Depends(get_session)
) -> list[dict[str, Any]]:
    """InterpretationRun history for a chart — replay reads the stored output."""
    snapshot = session.get(ChartSnapshot, chart_id)
    if snapshot is None:
        raise HTTPException(status_code=404, detail="chart not found")
    runs = session.scalars(
        select(InterpretationRun)
        .where(
            (InterpretationRun.chart_snapshot_id == chart_id)
            | (InterpretationRun.partner_chart_snapshot_id == chart_id)
        )
        .order_by(InterpretationRun.created_at.desc())
    ).all()
    return [
        {
            "id": r.id,
            "topic": r.topic,
            "status": r.status,
            "isCompatibility": r.partner_chart_snapshot_id is not None,
            "targetDate": (r.version_meta or {}).get("targetDate"),
            "createdAt": r.created_at,
        }
        for r in runs
    ]
