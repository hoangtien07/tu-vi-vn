"""Hợp bàn (SPEC_COMPATIBILITY) — gates A (API), B (determinism/cross_link),
C-compat (side-aware grounding), D (routing isolation), SSE contract."""

import datetime as dt
import json
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.domain.birth.contracts import NormalizedBirthMoment
from app.domain.chart.contracts import EngineProfile
from app.domain.chart.service import ChartService
from app.domain.context.comparison import ComparisonComposer, chi_relations
from app.domain.evidence.builder import EvidenceBuilder, EvidenceBundle
from app.domain.interpretation import grounding
from app.domain.interpretation.service import _context_hash, _live_pending
from app.infrastructure.db.models import Base, EngineProfileRow, InterpretationRun
from app.infrastructure.db.session import get_session
from app.infrastructure.xiztro.engine import XiztroEngine
from app.main import create_app

CASES_DIR = Path(__file__).resolve().parents[3] / "eval" / "cases"


class FakeProvider:
    model = "fake-1"

    def __init__(self, reply: str = "Người A và Người B tâm tính bổ sung nhau.") -> None:
        self._reply = reply

    async def stream(self, messages: list[dict[str, str]], **kw: Any) -> AsyncIterator[str]:
        yield self._reply

    async def complete(self, messages: list[dict[str, str]], **kw: Any) -> str:
        return self._reply


def _normalized(year: int, month: int, day: int, time_index: int) -> NormalizedBirthMoment:
    d = dt.date(year, month, day)
    return NormalizedBirthMoment(
        civilDateTime=dt.datetime.combine(d, dt.time(12, 0)),
        normalizedDateTime=dt.datetime.combine(d, dt.time(12, 0)),
        gender="male",
        timezoneOffsetMinutes=420,
        correctedSolarDate=d,
        timeIndex=time_index,
        tzKey="Asia/Ho_Chi_Minh",
        tzdataVersion="test",
        resolvedOffsetMinutes=420,
        normalizationMode="civil",
    )


def _profile() -> EngineProfile:
    return EngineProfile(id="iztro-default-v1", engineVersion="0.6.1")


@pytest.fixture()
def session() -> Session:
    eng = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(eng)
    with Session(eng) as s:
        s.add(
            EngineProfileRow(
                id="iztro-default-v1",
                content=_profile().model_dump(mode="json"),
            )
        )
        s.commit()
        yield s


@pytest.fixture()
def engine() -> XiztroEngine:
    return XiztroEngine()


NORM_A = _normalized(1990, 6, 15, 4)
NORM_B = _normalized(1992, 10, 2, 8)


@pytest.fixture()
def pair(session: Session):
    svc = ChartService(XiztroEngine())
    a = svc.cast_and_persist(session, {"calendar": "solar"}, NORM_A, _profile())
    b = svc.cast_and_persist(session, {"calendar": "solar"}, NORM_B, _profile())
    return a, b


def _client(session: Session, provider=None) -> TestClient:
    app = create_app()
    app.state.llm_provider = provider
    app.dependency_overrides[get_session] = lambda: session
    return TestClient(app)


def _sse_events(resp) -> list[tuple[str, dict]]:
    events = []
    event = None
    for line in resp.text.splitlines():
        if line.startswith("event: "):
            event = line[7:]
        elif line.startswith("data: "):
            events.append((event, json.loads(line[6:])))
    return events


# ---------- Gate B: deterministic pair context + cross_link correctness ----


def test_compose_pair_deterministic(engine):
    dto_a = engine.cast_chart(NORM_A, _profile())
    dto_b = engine.cast_chart(NORM_B, _profile())
    composer = ComparisonComposer(engine)
    ctx1 = composer.compose_pair(NORM_A, _profile(), dto_a, NORM_B, _profile(), dto_b)
    ctx3 = composer.compose_pair(NORM_A, _profile(), dto_a, NORM_B, _profile(), dto_b)

    assert ctx1.topic == "compatibility"
    h1 = _context_hash(EvidenceBuilder().build(ctx1, "ev_x"))
    h3 = _context_hash(EvidenceBuilder().build(ctx3, "ev_x"))
    assert h1 == h3  # same (a,b) order → same bundle ids/hash


def test_cross_link_tu_hoa(engine):
    """Every natal mutagen of A lands in a real palace of B (and vice versa)."""
    dto_a = engine.cast_chart(NORM_A, _profile())
    dto_b = engine.cast_chart(NORM_B, _profile())
    ctx = ComparisonComposer(engine).compose_pair(
        NORM_A, _profile(), dto_a, NORM_B, _profile(), dto_b
    )
    cross = [i for i in ctx.items if i.kind == "cross_link"]

    a_mutagens = [
        s["key"]
        for p in dto_a.chart["palaces"]
        for s in p["majorStars"] + p["minorStars"]
        if s.get("mutagen")
    ]
    b_mutagens = [
        s["key"]
        for p in dto_b.chart["palaces"]
        for s in p["majorStars"] + p["minorStars"]
        if s.get("mutagen")
    ]
    links_ab = [i for i in cross if i.scope == "cross:a→b"]
    links_ba = [i for i in cross if i.scope == "cross:b→a"]
    chi = [i for i in cross if i.scope == "cross:chi"]

    assert len(links_ab) == len(a_mutagens) <= 4
    assert len(links_ba) == len(b_mutagens) <= 4
    assert len(chi) == 1

    for item in links_ab:
        lands = item.data["lands_in"]
        assert lands is not None
        palace = next(p for p in dto_b.chart["palaces"] if p["nameKey"] == lands["palaceKey"])
        star_keys = {s["key"] for s in palace["majorStars"] + palace["minorStars"]}
        assert item.data["starKey"] in star_keys

    rel = chi[0].data["relations"]
    assert rel == chi_relations(
        dto_a.chart["earthlyBranchOfSoulPalaceKey"],
        dto_b.chart["earthlyBranchOfSoulPalaceKey"],
    )


def test_side_tags(engine):
    dto_a = engine.cast_chart(NORM_A, _profile())
    dto_b = engine.cast_chart(NORM_B, _profile())
    ctx = ComparisonComposer(engine).compose_pair(
        NORM_A,
        _profile(),
        dto_a,
        NORM_B,
        _profile(),
        dto_b,
        dt.date(2028, 3, 1),
        "yearly",
    )
    scopes = {i.scope for i in ctx.items}
    assert any(s.endswith(":a") for s in scopes)
    assert any(s.endswith(":b") for s in scopes)
    # both sides got horoscope evidence for the yearly scope set
    a_horo = {
        i.scope.split(":")[0]
        for i in ctx.items
        if i.kind == "horoscope_fact" and i.scope.endswith(":a")
    }
    b_horo = {
        i.scope.split(":")[0]
        for i in ctx.items
        if i.kind == "horoscope_fact" and i.scope.endswith(":b")
    }
    assert a_horo == b_horo == {"decadal", "yearly", "age"}


def test_chi_relations_table():
    assert chi_relations("ziEarthly", "ziEarthly") == ["dong_chi"]
    assert chi_relations("ziEarthly", "chouEarthly") == ["luc_hop"]
    assert chi_relations("ziEarthly", "wuEarthly") == ["xung"]
    assert chi_relations("shenEarthly", "chenEarthly") == ["tam_hop"]
    assert chi_relations("ziEarthly", "weiEarthly") == ["luc_hai"]
    assert chi_relations("ziEarthly", "maoEarthly") == ["neutral"]


# ---------- Gate C: side-aware grounding (eval/cases/compatibility.json) ----


@pytest.mark.parametrize(
    "case",
    json.loads((CASES_DIR / "compatibility.json").read_text())["cases"],
    ids=lambda c: c["id"],
)
def test_gate_c_compat(case: dict) -> None:
    bundle = EvidenceBundle(
        id="eval",
        topic=case["bundle"].get("topic", "eval"),
        items=case["bundle"]["items"],
    )
    result = grounding.validate(case["output"], bundle)
    assert result.ok is case["expect"]["ok"], result
    for field in case["expect"].get("violations", []):
        assert getattr(result, field), f"{field} should be non-empty"


# ---------- Gate A + SSE contract -------------------------------------------


def test_self_pair_422(session: Session, pair) -> None:
    a, _ = pair
    client = _client(session)
    resp = client.post("/api/compatibility", json={"chart_a_id": a.id, "chart_b_id": a.id})
    assert resp.status_code == 422
    assert resp.json()["detail"]["type"] == "self_pair"


def test_missing_chart_404(session: Session, pair) -> None:
    a, _ = pair
    client = _client(session)
    resp = client.post("/api/compatibility", json={"chart_a_id": a.id, "chart_b_id": "cs_nope"})
    assert resp.status_code == 404


def test_bad_target_422(session: Session, pair) -> None:
    a, b = pair
    client = _client(session)
    resp = client.post(
        "/api/compatibility",
        json={
            "chart_a_id": a.id,
            "chart_b_id": b.id,
            "target": {"scope": "monthly", "year": 2028},
        },
    )
    assert resp.status_code == 422


def test_target_before_birth_422_per_side(session: Session, pair) -> None:
    a, b = pair
    client = _client(session)
    resp = client.post(
        "/api/compatibility",
        json={
            "chart_a_id": a.id,
            "chart_b_id": b.id,
            "target": {"scope": "yearly", "year": 1991},
        },
    )
    assert resp.status_code == 422
    assert resp.json()["detail"]["type"] == "target_before_birth"
    assert resp.json()["detail"]["side"] == "b"


def test_sse_contract_and_run_row(session: Session, pair) -> None:
    a, b = pair
    client = _client(session, FakeProvider())
    resp = client.post("/api/compatibility", json={"chart_a_id": a.id, "chart_b_id": b.id})
    assert resp.status_code == 200
    events = _sse_events(resp)
    names = [e for e, _ in events]
    assert names[0] == "metadata"
    assert "evidence" in names
    assert "delta" in names
    assert names[-1] == "done"

    evidence = next(d for e, d in events if e == "evidence")
    kinds = {i["kind"] for i in evidence["items"]}
    assert "cross_link" in kinds
    scopes = {i["scope"] for i in evidence["items"]}
    assert any(s.endswith(":a") for s in scopes)

    done = next(d for e, d in events if e == "done")
    run = session.get(InterpretationRun, done["runId"])
    assert run is not None
    assert run.status == "completed"
    assert run.topic == "compatibility"
    assert run.chart_snapshot_id == a.id
    assert run.partner_chart_snapshot_id == b.id
    assert run.version_meta["sides"] == {"a": a.id, "b": b.id}


def test_idempotency_request_order(session: Session, pair) -> None:
    a, b = pair
    client = _client(session, FakeProvider())
    r1 = client.post("/api/compatibility", json={"chart_a_id": a.id, "chart_b_id": b.id})
    done1 = next(d for e, d in _sse_events(r1) if e == "done")

    # same order → replay
    r2 = client.post("/api/compatibility", json={"chart_a_id": a.id, "chart_b_id": b.id})
    ev2 = _sse_events(r2)
    assert any(d.get("replay") for e, d in ev2 if e == "done")

    # reversed order → fresh run with its own labels (different ikey)
    r3 = client.post("/api/compatibility", json={"chart_a_id": b.id, "chart_b_id": a.id})
    done3 = next(d for e, d in _sse_events(r3) if e == "done")
    assert not done3.get("replay")
    assert done3["runId"] != done1["runId"]
    run3 = session.get(InterpretationRun, done3["runId"])
    assert run3.chart_snapshot_id == b.id
    assert run3.partner_chart_snapshot_id == a.id


def test_get_run(session: Session, pair) -> None:
    a, b = pair
    client = _client(session, FakeProvider())
    r = client.post("/api/compatibility", json={"chart_a_id": a.id, "chart_b_id": b.id})
    done = next(d for e, d in _sse_events(r) if e == "done")
    resp = client.get(f"/api/compatibility/{done['runId']}")
    assert resp.status_code == 200
    body = resp.json()
    assert body["chartAId"] == a.id
    assert body["chartBId"] == b.id
    assert body["status"] == "completed"


def test_pending_run_signals_in_progress(session: Session, pair) -> None:
    # A duplicate request while the first run is still streaming must not
    # spawn a second LLM stream — the API reports run_in_progress instead.
    a, b = pair
    client = _client(session, FakeProvider())
    r1 = client.post("/api/compatibility", json={"chart_a_id": a.id, "chart_b_id": b.id})
    done1 = next(d for e, d in _sse_events(r1) if e == "done")
    run = session.get(InterpretationRun, done1["runId"])
    run.status = "pending"  # pretend it's still in flight
    session.commit()

    r2 = client.post("/api/compatibility", json={"chart_a_id": a.id, "chart_b_id": b.id})
    err = next(d for e, d in _sse_events(r2) if e == "error")
    assert err["type"] == "run_in_progress"
    assert err["runId"] == run.id


def test_live_pending_ttl() -> None:
    fresh = InterpretationRun(created_at=dt.datetime.now(dt.UTC).replace(tzinfo=None))
    assert _live_pending(fresh)
    stale = InterpretationRun(
        created_at=dt.datetime.now(dt.UTC).replace(tzinfo=None) - dt.timedelta(minutes=15)
    )
    assert not _live_pending(stale)


# ---------- Gate D: routing isolation ---------------------------------------


def test_interpret_rejects_compatibility_topic(session: Session, pair) -> None:
    a, _ = pair
    client = _client(session, FakeProvider())
    resp = client.post(
        f"/api/charts/{a.id}/interpret",
        json={"topic": "compatibility"},
    )
    assert resp.status_code == 422
