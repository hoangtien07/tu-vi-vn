from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.interpret import InterpretTarget, _resolve_target
from app.domain.context.composer import ContextComposer
from app.domain.interpretation.chat import ChatService
from app.infrastructure.db.models import ChartSnapshot, ProductEvent
from app.infrastructure.db.session import get_session

router = APIRouter(prefix="/api/charts", tags=["chat"])


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=2000)
    conversation_id: str | None = None
    # I16 — same TemporalTarget contract as interpret; scopes chosen by
    # temporal_scopes_for, no separate chat pipeline.
    target: InterpretTarget | None = None


@router.post("/{chart_id}/chat")
async def chat(
    chart_id: str,
    body: ChatRequest,
    request: Request,
    session: Session = Depends(get_session),
) -> dict:
    snapshot = session.get(ChartSnapshot, chart_id)
    if snapshot is None:
        raise HTTPException(status_code=404, detail="chart not found")
    service = ChatService(
        ContextComposer(request.app.state.ziwei_engine),
        request.app.state.llm_provider,
    )
    try:
        target_date, target_scope = _resolve_target(body.target)
        session.add(
            ProductEvent(
                id=f"ev_{uuid4().hex[:16]}",
                event="chat_sent",
                chart_snapshot_id=chart_id,
                meta={"hasTarget": body.target is not None},
            )
        )
        session.commit()
        return await service.respond(
            session,
            snapshot,
            body.message,
            body.conversation_id,
            target_date=target_date,
            target_scope=target_scope,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except RuntimeError as exc:
        if str(exc) == "llm_unconfigured":
            raise HTTPException(
                status_code=503, detail="AI endpoint not configured"
            ) from exc
        raise
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
