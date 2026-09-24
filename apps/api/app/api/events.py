"""SPEC_V02 §7 — append-only product events, no third-party analytics."""

from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.infrastructure.db.models import ProductEvent
from app.infrastructure.db.session import get_session

router = APIRouter(prefix="/api/events", tags=["events"])

ALLOWED_EVENTS = {
    "chart_created",
    "profile_created",
    "interpret_started",
    "interpret_completed",
    "compat_started",
    "temporal_opened",
    "reading_reopened",
}


class EventIn(BaseModel):
    event: str
    profileId: str | None = None
    chartId: str | None = None
    # Client-supplied dedupe key — re-posts of the same event are ignored.
    clientEventId: str | None = Field(default=None, max_length=64)
    meta: dict = Field(default_factory=dict)


@router.post("", status_code=202)
def track_event(body: EventIn, session: Session = Depends(get_session)) -> dict[str, str]:
    if body.event not in ALLOWED_EVENTS:
        raise HTTPException(status_code=422, detail="unknown event")
    session.add(
        ProductEvent(
            id=body.clientEventId or f"ev_{uuid4().hex[:16]}",
            event=body.event,
            profile_id=body.profileId,
            chart_snapshot_id=body.chartId,
            meta=body.meta,
        )
    )
    try:
        session.commit()
    except Exception:
        session.rollback()
    return {"status": "ok"}
