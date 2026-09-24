from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.domain.context.composer import ContextComposer
from app.domain.interpretation.chat import ChatService
from app.infrastructure.db.models import ChartSnapshot
from app.infrastructure.db.session import get_session

router = APIRouter(prefix="/api/charts", tags=["chat"])


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=2000)
    conversation_id: str | None = None


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
        return await service.respond(
            session, snapshot, body.message, body.conversation_id
        )
    except RuntimeError as exc:
        if str(exc) == "llm_unconfigured":
            raise HTTPException(
                status_code=503, detail="AI endpoint not configured"
            ) from exc
        raise
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
