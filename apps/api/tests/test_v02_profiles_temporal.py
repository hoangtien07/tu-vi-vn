"""SPEC_V02 — profiles CRUD, deterministic temporal facts, readings, events."""

import datetime as dt

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.domain.birth.contracts import NormalizedBirthMoment
from app.domain.chart.contracts import EngineProfile
from app.domain.chart.service import ChartService
from app.infrastructure.db.models import (
    Base,
    EngineProfileRow,
    InterpretationRun,
)
from app.infrastructure.db.session import get_session
from app.infrastructure.xiztro.engine import XiztroEngine
from app.main import create_app


def _normalized() -> NormalizedBirthMoment:
    d = dt.date(1990, 6, 15)
    return NormalizedBirthMoment(
        civilDateTime=dt.datetime.combine(d, dt.time(12, 0)),
        normalizedDateTime=dt.datetime.combine(d, dt.time(12, 0)),
        gender="male",
        timezoneOffsetMinutes=420,
        correctedSolarDate=d,
        timeIndex=6,
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
def chart(session: Session):
    return ChartService(XiztroEngine()).cast_and_persist(
        session, {"calendar": "solar"}, _normalized(), _profile()
    )


@pytest.fixture()
def client(session: Session) -> TestClient:
    app = create_app()
    app.dependency_overrides[get_session] = lambda: session
    return TestClient(app)


# ---------- profiles ----------


def test_profile_crud(client: TestClient, chart) -> None:
    created = client.post(
        "/api/profiles",
        json={
            "display_name": "Tiến",
            "relationship": "self",
            "chart_id": chart.id,
        },
    )
    assert created.status_code == 201, created.text
    pid = created.json()["id"]
    assert created.json()["chartId"] == chart.id
    assert created.json()["visibility"] == "private"

    listed = client.get("/api/profiles")
    assert [p["id"] for p in listed.json()] == [pid]

    got = client.get(f"/api/profiles/{pid}")
    assert got.json()["displayName"] == "Tiến"

    updated = client.patch(f"/api/profiles/{pid}", json={"display_name": "Mẹ"})
    assert updated.json()["displayName"] == "Mẹ"

    deleted = client.delete(f"/api/profiles/{pid}")
    assert deleted.status_code == 204
    assert client.get("/api/profiles").json() == []


def test_profile_unknown_chart_404(client: TestClient) -> None:
    resp = client.post(
        "/api/profiles", json={"display_name": "X", "chart_id": "cs_nope"}
    )
    assert resp.status_code == 404


def test_profile_bad_relationship_422(client: TestClient, chart) -> None:
    resp = client.post(
        "/api/profiles",
        json={
            "display_name": "X",
            "relationship": "boss",
            "chart_id": chart.id,
        },
    )
    assert resp.status_code == 422


# ---------- temporal ----------


def test_temporal_decadal_only(client: TestClient, chart) -> None:
    resp = client.get(f"/api/charts/{chart.id}/temporal")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["scopesIncluded"] == ["decadal"]
    assert body["decadal"] is not None
    assert body["yearly"] is None


def test_temporal_yearly(client: TestClient, chart) -> None:
    resp = client.get(f"/api/charts/{chart.id}/temporal?year=2028")
    body = resp.json()
    assert body["scopesIncluded"] == ["decadal", "yearly"]
    assert body["yearly"] is not None
    assert body["daily"] is None


def test_temporal_daily(client: TestClient, chart) -> None:
    resp = client.get(f"/api/charts/{chart.id}/temporal?year=2028&month=5&day=18")
    body = resp.json()
    assert body["scopesIncluded"] == ["decadal", "yearly", "monthly", "daily"]
    assert body["anchor"] == "2028-05-18"


def test_temporal_month_without_year_422(client: TestClient, chart) -> None:
    assert client.get(f"/api/charts/{chart.id}/temporal?month=5").status_code == 422


def test_temporal_before_birth_422(client: TestClient, chart) -> None:
    assert client.get(f"/api/charts/{chart.id}/temporal?year=1989").status_code == 422


def test_temporal_unknown_chart_404(client: TestClient) -> None:
    assert client.get("/api/charts/cs_nope/temporal").status_code == 404


def test_temporal_no_llm(client: TestClient, chart) -> None:
    """Deterministic endpoint must not need a provider (I9)."""
    client.app.state.llm_provider = None
    assert client.get(f"/api/charts/{chart.id}/temporal?year=2028").status_code == 200


# ---------- readings ----------


def test_readings_lists_runs(client: TestClient, session: Session, chart) -> None:
    session.add(
        InterpretationRun(
            id="ir_1",
            chart_snapshot_id=chart.id,
            topic="career",
            status="completed",
            version_meta={"targetDate": "2028-01-01"},
            claims=[],
        )
    )
    session.commit()
    runs = client.get(f"/api/charts/{chart.id}/readings").json()
    assert len(runs) == 1
    assert runs[0]["topic"] == "career"
    assert runs[0]["targetDate"] == "2028-01-01"
    assert runs[0]["isCompatibility"] is False


# ---------- events ----------


def test_event_track(client: TestClient, chart) -> None:
    resp = client.post(
        "/api/events",
        json={"event": "temporal_opened", "chartId": chart.id, "meta": {"scope": "yearly"}},
    )
    assert resp.status_code == 202
    assert client.post("/api/events", json={"event": "bogus"}).status_code == 422


def test_event_dedupe(client: TestClient) -> None:
    body = {"event": "chart_created", "clientEventId": "dedupe-1"}
    assert client.post("/api/events", json=body).status_code == 202
    assert client.post("/api/events", json=body).status_code == 202  # no 500


def test_temporal_invalid_day_is_422(client: TestClient, chart) -> None:
    r = client.get(
        f"/api/charts/{chart.id}/temporal",
        params={"year": 2028, "month": 2, "day": 31},
    )
    assert r.status_code == 422


def test_reading_detail_replay(client: TestClient, chart, session) -> None:
    from app.infrastructure.db.models import InterpretationRun

    session.add(
        InterpretationRun(
            id="rr_1",
            chart_snapshot_id=chart.id,
            topic="career",
            status="completed",
            output_text="Năm 2028 sự nghiệp hanh thông.",
            version_meta={"targetDate": "2028-01-01"},
        )
    )
    session.commit()
    r = client.get(f"/api/charts/{chart.id}/readings/rr_1")
    assert r.status_code == 200
    assert r.json()["outputText"] == "Năm 2028 sự nghiệp hanh thông."
    assert client.get(f"/api/charts/{chart.id}/readings/nope").status_code == 404


def test_event_meta_size_cap(client: TestClient) -> None:
    body = {"event": "chart_created", "meta": {"x": "y" * 5000}}
    assert client.post("/api/events", json=body).status_code == 422
