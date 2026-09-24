import datetime as dt
import json
from collections.abc import AsyncIterator

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.interpret import InterpretTarget, _resolve_target
from app.domain.birth.contracts import NormalizedBirthMoment
from app.domain.context.composer import ContextComposer
from app.domain.interpretation.service import InterpretationService
from app.infrastructure.db.models import (
    ChartSnapshot,
    InterpretationRun,
    NormalizedBirthMomentRow,
)
from app.infrastructure.db.session import get_session

router = APIRouter(prefix="/api/compatibility", tags=["compatibility"])


class CompatibilityRequest(BaseModel):
    """SPEC_COMPATIBILITY §3.2 — pair order is part of the idempotency key."""

    chart_a_id: str
    chart_b_id: str
    target: InterpretTarget | None = None
    namespace: str | None = Field(default=None, max_length=64)


def _load_pair(session: Session, body: CompatibilityRequest) -> tuple[ChartSnapshot, ChartSnapshot]:
    if body.chart_a_id == body.chart_b_id:
        raise HTTPException(
            status_code=422,
            detail={"type": "self_pair", "detail": "chart_a_id == chart_b_id"},
        )
    snapshot_a = session.get(ChartSnapshot, body.chart_a_id)
    snapshot_b = session.get(ChartSnapshot, body.chart_b_id)
    missing = [side for side, snap in (("a", snapshot_a), ("b", snapshot_b)) if snap is None]
    if missing:
        raise HTTPException(
            status_code=404,
            detail={"type": "chart_not_found", "sides": missing},
        )
    assert snapshot_a is not None and snapshot_b is not None
    return snapshot_a, snapshot_b


def _check_target_vs_birth(
    session: Session,
    target_date: dt.date,
    snapshot: ChartSnapshot,
    side: str,
) -> None:
    row = session.get(NormalizedBirthMomentRow, snapshot.normalized_birth_moment_id)
    if row is None:
        raise HTTPException(status_code=500, detail="normalized birth missing")
    normalized = NormalizedBirthMoment.model_validate(row.payload)
    if target_date < normalized.correctedSolarDate:
        raise HTTPException(
            status_code=422,
            detail={
                "type": "target_before_birth",
                "side": side,
                "detail": f"target date precedes birth date of side {side.upper()}",
            },
        )


@router.post("")
async def compatibility(
    body: CompatibilityRequest,
    request: Request,
    session: Session = Depends(get_session),
) -> StreamingResponse:
    """Stream a two-chart (hợp bàn) interpretation.

    Events: metadata → evidence (side-tagged bundle) → delta* →
    (repair → replace)? → done | error; replay on idempotency hit.
    """
    snapshot_a, snapshot_b = _load_pair(session, body)

    try:
        target_date, target_scope = _resolve_target(body.target)
    except Exception as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    if target_date is not None:
        _check_target_vs_birth(session, target_date, snapshot_a, "a")
        _check_target_vs_birth(session, target_date, snapshot_b, "b")

    service = InterpretationService(
        ContextComposer(request.app.state.ziwei_engine),
        request.app.state.llm_provider,
    )

    async def event_stream() -> AsyncIterator[str]:
        try:
            async for ev in service.run_pair(
                session,
                snapshot_a,
                snapshot_b,
                target_date,
                target_scope=target_scope,
                namespace=body.namespace,
            ):
                payload = json.dumps(ev["data"], ensure_ascii=False)
                yield f"event: {ev['event']}\ndata: {payload}\n\n"
        except Exception as exc:
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


@router.get("/{run_id}")
def get_run(run_id: str, session: Session = Depends(get_session)) -> dict[str, object]:
    run = session.get(InterpretationRun, run_id)
    if run is None or run.topic != "compatibility":
        raise HTTPException(status_code=404, detail="compatibility run not found")
    return {
        "id": run.id,
        "chartAId": run.chart_snapshot_id,
        "chartBId": run.partner_chart_snapshot_id,
        "topic": run.topic,
        "status": run.status,
        "output": run.output_text,
        "claims": run.claims,
        "evidenceBundleId": run.evidence_bundle_id,
        "versionMeta": run.version_meta,
        "createdAt": run.created_at,
    }
