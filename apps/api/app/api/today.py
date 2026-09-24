"""SPEC_V03 §II — Today: deterministic daily facts on open, LLM on demand."""

import datetime as dt
import json
from collections.abc import AsyncIterator
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.api.temporal import _load_normalized
from app.domain.context.composer import ContextComposer
from app.domain.interpretation.service import InterpretationService
from app.infrastructure.db.models import ChartSnapshot
from app.infrastructure.db.session import get_session

router = APIRouter(prefix="/api/charts", tags=["today"])

# Fixed palace→topic map for highlight extraction (I13 — no heuristics, no LLM).
PALACE_TOPIC_HINT = {
    "menh": "overview",
    "quanLoc": "career",
    "taiBach": "wealth",
    "phuThe": "love",
    "tatAch": "health",
}
_TOPIC_LABEL = {
    "overview": "Tổng quan",
    "career": "Công việc",
    "wealth": "Tài chính",
    "love": "Quan hệ",
    "health": "Sức khỏe",
}


def _resolve_date(raw: str | None) -> dt.date:
    if raw is None:
        return dt.date.today()
    try:
        return dt.date.fromisoformat(raw)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail="date must be YYYY-MM-DD") from exc


def _highlights(daily: dict[str, Any], yearly: dict[str, Any]) -> list[dict[str, str]]:
    """≤3 rule-extracted highlights from the daily layer (I13)."""
    out: list[dict[str, str]] = []
    palace = str(daily.get("palace") or "")
    hint = PALACE_TOPIC_HINT.get(palace)
    if hint:
        mutagens = daily.get("mutagen") or []
        mut_txt = (
            " · tứ hóa lưu nhật: " + ", ".join(str(m) for m in mutagens)
            if mutagens
            else ""
        )
        out.append(
            {
                "palace": palace,
                "topicHint": hint,
                "summary": f"Lưu nhật tại cung {palace}{mut_txt}.",
            }
        )
    age_palace = str(yearly.get("palace") or "")
    y_hint = PALACE_TOPIC_HINT.get(age_palace)
    if y_hint and y_hint != hint:
        out.append(
            {
                "palace": age_palace,
                "topicHint": y_hint,
                "summary": f"Lưu niên tại cung {age_palace}.",
            }
        )
    return out[:3]


@router.get("/{chart_id}/today")
def get_today(
    chart_id: str,
    request: Request,
    date: str | None = None,
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    """Deterministic daily facts — no LLM call (I13)."""
    snapshot = session.get(ChartSnapshot, chart_id)
    if snapshot is None:
        raise HTTPException(status_code=404, detail="chart not found")
    day = _resolve_date(date)
    normalized, profile = _load_normalized(snapshot, session)
    if day < normalized.correctedSolarDate:
        raise HTTPException(status_code=422, detail="date precedes birth date")

    horoscope = request.app.state.ziwei_engine.get_horoscope(
        normalized, profile, day
    )
    ctx = horoscope.context
    daily = ctx.get("daily") or {}
    yearly = ctx.get("yearly") or {}
    return {
        "chartId": chart_id,
        "date": day.isoformat(),
        "facts": {
            "decadal": ctx.get("decadal"),
            "yearly": yearly,
            "monthly": ctx.get("monthly"),
            "daily": daily,
            "age": ctx.get("age"),
        },
        "highlights": _highlights(daily, yearly),
    }


@router.post("/{chart_id}/today/brief")
async def today_brief(
    chart_id: str,
    request: Request,
    date: str | None = None,
    session: Session = Depends(get_session),
) -> StreamingResponse:
    """On-demand LLM narrative for the day — SSE, persisted as a run."""
    snapshot = session.get(ChartSnapshot, chart_id)
    if snapshot is None:
        raise HTTPException(status_code=404, detail="chart not found")
    day = _resolve_date(date)
    normalized, _profile = _load_normalized(snapshot, session)
    if day < normalized.correctedSolarDate:
        raise HTTPException(status_code=422, detail="date precedes birth date")

    service = InterpretationService(
        ContextComposer(request.app.state.ziwei_engine),
        request.app.state.llm_provider,
    )

    async def event_stream() -> AsyncIterator[str]:
        try:
            async for ev in service.run(
                session,
                snapshot,
                "today",
                day,
                target_scope="daily",
            ):
                payload = json.dumps(ev["data"], ensure_ascii=False)
                yield f"event: {ev['event']}\ndata: {payload}\n\n"
        except Exception:
            yield 'event: error\ndata: {"type": "internal"}\n\n'

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
