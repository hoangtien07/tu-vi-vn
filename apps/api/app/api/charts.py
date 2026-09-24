from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.infrastructure.db.models import ChartSnapshot
from app.infrastructure.db.session import get_session

router = APIRouter(prefix="/api/charts", tags=["charts"])
share_router = APIRouter(prefix="/s", tags=["share"])


def _serialize(snapshot: ChartSnapshot) -> dict[str, object]:
    return {
        "id": snapshot.id,
        "engine": snapshot.engine,
        "engineVersion": snapshot.engine_version,
        "engineProfileId": snapshot.engine_profile_id,
        "chartHash": snapshot.chart_hash,
        "dtoSchemaVersion": snapshot.dto_schema_version,
        "shareToken": snapshot.share_token,
        "chart": snapshot.chart_json,
        "patternHits": snapshot.pattern_hits,
        "createdAt": snapshot.created_at,
    }


@router.get("/{chart_id}")
def get_chart(chart_id: str, session: Session = Depends(get_session)) -> dict[str, object]:
    snapshot = session.get(ChartSnapshot, chart_id)
    if snapshot is None:
        raise HTTPException(status_code=404, detail="chart not found")
    return _serialize(snapshot)


@share_router.get("/{token}")
def get_shared_chart(token: str, session: Session = Depends(get_session)) -> dict[str, object]:
    """Read-only chart view by unguessable share token (SPEC §16)."""
    snapshot = session.scalar(
        select(ChartSnapshot).where(ChartSnapshot.share_token == token)
    )
    if snapshot is None:
        raise HTTPException(status_code=404, detail="chart not found")
    data = _serialize(snapshot)
    data.pop("shareToken")
    return data
