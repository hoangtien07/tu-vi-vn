"""SPEC_V02 §7 — append-only product events, no third-party analytics."""

import json
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, model_validator
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


_MAX_META_BYTES = 4096


class EventIn(BaseModel):
    event: str
    profileId: str | None = None
    chartId: str | None = None
    # Client-supplied dedupe key — re-posts of the same event are ignored.
    clientEventId: str | None = Field(default=None, max_length=64)
    meta: dict = Field(default_factory=dict)

    @model_validator(mode="after")
    def _meta_bounded(self) -> "EventIn":
        if len(json.dumps(self.meta, ensure_ascii=False)) > _MAX_META_BYTES:
            raise ValueError("meta too large")
        return self


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
    except Exception as exc:
        session.rollback()
        # Unique-constraint = a repost of the same clientEventId — fine.
        # Anything else means the event was lost; say so instead of
        # reporting success.
        if not _is_unique_violation(exc):
            raise HTTPException(
                status_code=503, detail="event store unavailable"
            ) from exc
    return {"status": "ok"}


def _is_unique_violation(exc: Exception) -> bool:
    msg = str(getattr(exc, "orig", exc)).lower()
    return "unique" in msg or "duplicate" in msg
