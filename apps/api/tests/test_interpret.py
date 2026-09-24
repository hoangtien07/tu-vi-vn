import asyncio
import datetime as dt
from collections.abc import AsyncIterator
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.domain.birth.contracts import NormalizedBirthMoment
from app.domain.chart.contracts import EngineProfile
from app.domain.chart.service import ChartService
from app.domain.context.composer import ContextComposer
from app.domain.evidence.builder import EvidenceBuilder
from app.domain.interpretation.grounding import extract_claims, validate
from app.domain.interpretation.service import InterpretationService
from app.infrastructure.db.models import (
    Base,
    EngineProfileRow,
    InterpretationRun,
)
from app.infrastructure.db.session import get_session
from app.infrastructure.xiztro.engine import XiztroEngine
from app.main import create_app


class FakeProvider:
    model = "fake-1"

    def __init__(self, chunks: list[str], repair_output: str | None = None) -> None:
        self._chunks = chunks
        self._repair = repair_output
        self.complete_calls = 0

    async def stream(
        self, messages: list[dict[str, str]], **kw: Any
    ) -> AsyncIterator[str]:
        for c in self._chunks:
            yield c

    async def complete(self, messages: list[dict[str, str]], **kw: Any) -> str:
        self.complete_calls += 1
        if self._repair is not None:
            return self._repair
        return "".join(self._chunks)


def _normalized() -> NormalizedBirthMoment:
    return NormalizedBirthMoment(
        civilDateTime=dt.datetime(1990, 6, 15, 14, 30),
        normalizedDateTime=dt.datetime(1990, 6, 15, 14, 18),
        gender="male",
        timezoneOffsetMinutes=420,
        correctedSolarDate=dt.date(1990, 6, 15),
        timeIndex=4,
        tzKey="Asia/Ho_Chi_Minh",
        tzdataVersion="test",
        resolvedOffsetMinutes=420,
        normalizationMode="true-solar",
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
def snapshot(session: Session):
    return ChartService(XiztroEngine()).cast_and_persist(
        session, {"calendar": "solar"}, _normalized(), _profile()
    )


@pytest.fixture()
def bundle():
    engine = XiztroEngine()
    dto = engine.cast_chart(_normalized(), _profile())
    ctx = ContextComposer(engine).compose(
        _normalized(), _profile(), dto, "career", target_date=dt.date(2028, 3, 1)
    )
    return EvidenceBuilder().build(ctx, "ev_t")


def _collect(
    service: InterpretationService, session: Session, snapshot, topic="career"
) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []

    async def go() -> None:
        async for ev in service.run(session, snapshot, topic, None):
            events.append(ev)

    asyncio.run(go())
    return events


def test_run_streams_and_persists(session: Session, snapshot) -> None:
    service = InterpretationService(
        ContextComposer(XiztroEngine()),
        FakeProvider(["Mệnh Thất Sát ", "độc lập [E001]."]),
    )
    events = _collect(service, session, snapshot)
    kinds = [e["event"] for e in events]
    assert kinds[0] == "metadata" and kinds[1] == "evidence"
    assert "delta" in kinds and kinds[-1] == "done"

    run = session.scalar(
        select(InterpretationRun).where(
            InterpretationRun.chart_snapshot_id == snapshot.id
        )
    )
    assert run is not None
    assert run.status == "completed"
    assert run.version_meta["contextComposerVersion"] == "v1"
    assert run.version_meta["promptVersion"] == "career-v1"
    assert run.claims


def test_idempotent_replay(session: Session, snapshot) -> None:
    service = InterpretationService(
        ContextComposer(XiztroEngine()), FakeProvider(["ok [E001]."])
    )
    _collect(service, session, snapshot)
    events = _collect(service, session, snapshot)
    assert events[0]["data"]["replay"] is True
    assert events[-1]["data"]["replay"] is True


def test_unconfigured_provider(session: Session, snapshot) -> None:
    service = InterpretationService(ContextComposer(XiztroEngine()), None)
    events = _collect(service, session, snapshot)
    assert events[-1]["event"] == "error"
    assert events[-1]["data"]["type"] == "llm_unconfigured"


def test_endpoint_streams_sse(session: Session, snapshot) -> None:
    app = create_app()
    app.state.llm_provider = FakeProvider(["Mệnh [E001] tốt."])
    app.dependency_overrides[get_session] = lambda: session
    client = TestClient(app)

    resp = client.post(
        f"/api/charts/{snapshot.id}/interpret", json={"topic": "career"}
    )
    assert resp.status_code == 200
    assert "event: metadata" in resp.text
    assert "event: done" in resp.text

    bad = client.post(
        f"/api/charts/{snapshot.id}/interpret", json={"topic": "parents"}
    )
    assert bad.status_code == 422

    missing = client.post("/api/charts/cs_none/interpret", json={"topic": "career"})
    assert missing.status_code == 404


def test_grounding_unknown_ref(bundle) -> None:
    some_id = bundle.items[0].id
    assert validate(f"Luận giải [{some_id}].", bundle).unknown_refs == []
    assert validate("Luận giải [E999].", bundle).unknown_refs == ["E999"]


def test_grounding_temporal_requires_horoscope(bundle) -> None:
    horo = next(i for i in bundle.items if i.kind == "horoscope_fact")
    natal = next(i for i in bundle.items if i.kind == "palace_fact")

    ok = validate(f"Năm 2028 sự nghiệp tốt [{horo.id}].", bundle)
    assert ok.temporal_unverified == []
    bad = validate(f"Năm 2028 sự nghiệp tốt [{natal.id}].", bundle)
    assert bad.temporal_unverified


def test_extract_claims() -> None:
    claims = extract_claims("Câu một [E001]. Câu hai. Câu ba [E002] [E003].")
    assert len(claims) == 2
    assert claims[1]["refs"] == ["E002", "E003"]
