from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain.birth.contracts import RawBirthInput
from app.domain.birth.normalizer import SolarCoordinateRequiredError, civil_moment, normalize
from app.domain.birth.vn_timezone import BirthRegionRequiredError
from app.domain.chart.service import ChartService, load_engine_profile
from app.infrastructure.db.models import (
    ChartSnapshot,
    NormalizedBirthMomentRow,
)
from app.infrastructure.db.session import get_session
from app.infrastructure.xiztro.calendar import (
    InvalidLunarDateError,
    NotLeapMonthError,
    lunar_to_solar,
)

router = APIRouter(prefix="/api/charts", tags=["charts"])
share_router = APIRouter(prefix="/s", tags=["share"])


def get_chart_service(request: Request) -> ChartService:
    return ChartService(request.app.state.ziwei_engine)


def _serialize(
    snapshot: ChartSnapshot, session: Session
) -> dict[str, object]:
    norm = session.get(
        NormalizedBirthMomentRow, snapshot.normalized_birth_moment_id
    )
    normalized = norm.payload if norm is not None else None
    return {
        "id": snapshot.id,
        "engine": snapshot.engine,
        "engineVersion": snapshot.engine_version,
        "engineProfileId": snapshot.engine_profile_id,
        "chartHash": snapshot.chart_hash,
        "dtoSchemaVersion": snapshot.dto_schema_version,
        "shareToken": snapshot.share_token,
        "provisional": bool((normalized or {}).get("provisional")),
        "warnings": (normalized or {}).get("warnings", []),
        "chart": snapshot.chart_json,
        "patternHits": snapshot.pattern_hits,
        "createdAt": snapshot.created_at,
    }


def _unprocessable(exc: ValueError) -> HTTPException:
    return HTTPException(status_code=422, detail=str(exc))


@router.post("", status_code=201)
def create_chart(
    raw: RawBirthInput,
    session: Session = Depends(get_session),
    service: ChartService = Depends(get_chart_service),
) -> dict[str, object]:
    """Cast a chart: validate → normalize → cast → persist snapshot (idempotent)."""
    try:
        civil = civil_moment(raw, lunar_to_solar)
        normalized = normalize(raw, civil)
    except (
        BirthRegionRequiredError,
        SolarCoordinateRequiredError,
        InvalidLunarDateError,
        NotLeapMonthError,
    ) as exc:
        raise _unprocessable(exc) from exc

    snapshot = service.cast_and_persist(
        session, raw.model_dump(mode="json"), normalized, load_engine_profile(session)
    )
    data = _serialize(snapshot, session)
    data["birth"] = {
        "raw": raw.model_dump(mode="json"),
        "normalized": normalized.model_dump(mode="json"),
    }
    return data


@router.get("/{chart_id}")
def get_chart(chart_id: str, session: Session = Depends(get_session)) -> dict[str, object]:
    snapshot = session.get(ChartSnapshot, chart_id)
    if snapshot is None:
        raise HTTPException(status_code=404, detail="chart not found")
    return _serialize(snapshot, session)


class CompatibilityRequest(BaseModel):
    other_chart_id: str
    mode: Literal["spouse", "business"]


@router.post("/{chart_id}/compatibility", status_code=501)
def compatibility(chart_id: str, body: CompatibilityRequest) -> None:
    """V1.1 contract frozen now so Modes 1–2 don't break (SPEC §16)."""
    raise HTTPException(
        status_code=501, detail="compatibility ships in V1.1; contract is frozen"
    )


@share_router.get("/{token}")
def get_shared_chart(token: str, session: Session = Depends(get_session)) -> dict[str, object]:
    """Read-only chart view by unguessable share token (SPEC §16)."""
    snapshot = session.scalar(
        select(ChartSnapshot).where(ChartSnapshot.share_token == token)
    )
    if snapshot is None:
        raise HTTPException(status_code=404, detail="chart not found")
    data = _serialize(snapshot, session)
    data.pop("shareToken")
    return data
