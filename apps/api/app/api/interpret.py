import datetime as dt
import json
from collections.abc import AsyncIterator
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field, model_validator
from sqlalchemy.orm import Session

from app.domain.birth.contracts import NormalizedBirthMoment
from app.domain.context.composer import (
    ContextComposer,
    TargetScope,
    Topic,
    target_anchor,
)
from app.domain.interpretation.service import InterpretationService
from app.infrastructure.db.models import (
    ChartSnapshot,
    NormalizedBirthMomentRow,
)
from app.infrastructure.db.session import get_session

router = APIRouter(prefix="/api/charts", tags=["interpret"])

ALLOWED_TOPICS = {"overview", "career", "wealth", "love", "health"}


class InterpretTarget(BaseModel):
    """SPEC §16: scope drives which horoscope layers enter context — never
    inferred from a bare date."""

    scope: Literal["yearly", "monthly", "daily"]
    year: int = Field(ge=1583, le=9999)
    month: int | None = Field(default=None, ge=1, le=12)
    day: int | None = Field(default=None, ge=1, le=31)

    @model_validator(mode="after")
    def _scope_fields(self) -> "InterpretTarget":
        if self.scope == "yearly" and (self.month is not None or self.day is not None):
            raise ValueError("yearly scope takes year only")
        if self.scope == "monthly" and (self.month is None or self.day is not None):
            raise ValueError("monthly scope requires month and no day")
        if self.scope == "daily" and (self.month is None or self.day is None):
            raise ValueError("daily scope requires month and day")
        return self


class InterpretRequest(BaseModel):
    topic: Topic
    target: InterpretTarget | None = None
    # Distinct ikey namespace → fresh run instead of replaying a completed
    # one with the same key (used by the eval benchmark).
    namespace: str | None = Field(default=None, max_length=64)


def _resolve_target(
    target: InterpretTarget | None,
) -> tuple[dt.date | None, TargetScope | None]:
    if target is None:
        return None, None
    return (
        target_anchor(target.scope, target.year, target.month, target.day),
        target.scope,
    )


@router.post("/{chart_id}/interpret")
async def interpret(
    chart_id: str,
    body: InterpretRequest,
    request: Request,
    session: Session = Depends(get_session),
) -> StreamingResponse:
    """Stream an evidence-grounded interpretation (SPEC §16).

    Events: metadata → evidence → delta* → done | error.
    """
    if body.topic not in ALLOWED_TOPICS:
        raise HTTPException(
            status_code=422, detail=f"topic must be one of {sorted(ALLOWED_TOPICS)}"
        )
    snapshot = session.get(ChartSnapshot, chart_id)
    if snapshot is None:
        raise HTTPException(status_code=404, detail="chart not found")

    try:
        target_date, target_scope = _resolve_target(body.target)
    except Exception as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    if target_date is not None:
        row = session.get(
            NormalizedBirthMomentRow, snapshot.normalized_birth_moment_id
        )
        if row is None:
            raise HTTPException(status_code=500, detail="normalized birth missing")
        normalized = NormalizedBirthMoment.model_validate(row.payload)
        if target_date < normalized.correctedSolarDate:
            raise HTTPException(
                status_code=422, detail="target date precedes birth date"
            )

    service = InterpretationService(
        ContextComposer(request.app.state.ziwei_engine),
        request.app.state.llm_provider,
    )

    async def event_stream() -> AsyncIterator[str]:
        try:
            async for ev in service.run(
                session,
                snapshot,
                body.topic,
                target_date,
                target_scope=target_scope,
                namespace=body.namespace,
            ):
                payload = json.dumps(ev["data"], ensure_ascii=False)
                yield f"event: {ev['event']}\ndata: {payload}\n\n"
        except Exception:  # last-resort: error event, never partial-as-done
            # Typed errors carry their own events — raw exception text leaks
            # internals, so the catch-all stays generic.
            yield 'event: error\ndata: {"type": "internal"}\n\n'

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )
