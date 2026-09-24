import datetime as dt
import json
from collections.abc import AsyncIterator

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.domain.context.composer import ContextComposer, Topic
from app.domain.interpretation.service import InterpretationService
from app.infrastructure.db.models import ChartSnapshot
from app.infrastructure.db.session import get_session

router = APIRouter(prefix="/api/charts", tags=["interpret"])

ALLOWED_TOPICS = {"overview", "career", "wealth", "love", "health"}


class InterpretRequest(BaseModel):
    topic: Topic
    target: dt.date | None = None


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

    service = InterpretationService(
        ContextComposer(request.app.state.ziwei_engine),
        request.app.state.llm_provider,
    )

    async def event_stream() -> AsyncIterator[str]:
        try:
            async for ev in service.run(
                session, snapshot, body.topic, body.target
            ):
                payload = json.dumps(ev["data"], ensure_ascii=False)
                yield f"event: {ev['event']}\ndata: {payload}\n\n"
        except Exception as exc:  # last-resort: error event, never partial-as-done
            yield (
                "event: error\ndata: "
                + json.dumps({"type": "internal", "detail": str(exc)[:200]})
                + "\n\n"
            )

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )
