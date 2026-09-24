from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.domain.chart.fortune import (
    FortuneService,
    FortuneTargetBeforeBirthError,
)
from app.infrastructure.db.models import ChartSnapshot
from app.infrastructure.db.session import get_session

router = APIRouter(prefix="/api/charts", tags=["fortune"])


@router.get("/{chart_id}/fortune/year/{year}")
def fortune_year(
    chart_id: str,
    year: int,
    request: Request,
    session: Session = Depends(get_session),
) -> dict:
    snapshot = session.get(ChartSnapshot, chart_id)
    if snapshot is None:
        raise HTTPException(status_code=404, detail="chart not found")
    service = FortuneService(request.app.state.ziwei_engine)
    try:
        return service.yearly(session, snapshot, year)
    except FortuneTargetBeforeBirthError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except LookupError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
