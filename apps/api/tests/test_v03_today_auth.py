"""SPEC_V03 — Today card determinism, auth flow, ownership merge, chat target."""

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
    ProductEvent,
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


# ---------- today ----------


def test_today_facts_deterministic(client: TestClient, chart) -> None:
    # TestClient app has llm_provider=None; a successful response proves
    # no LLM was touched (I13).
    r = client.get(f"/api/charts/{chart.id}/today", params={"date": "2026-09-24"})
    assert r.status_code == 200
    body = r.json()
    assert body["date"] == "2026-09-24"
    assert body["facts"]["daily"] is not None
    assert body["facts"]["yearly"] is not None
    for h in body["highlights"]:
        assert h["topicHint"] in {"overview", "career", "wealth", "love", "health"}
    assert len(body["highlights"]) <= 3


def test_today_invalid_date(client: TestClient, chart) -> None:
    assert (
        client.get(f"/api/charts/{chart.id}/today", params={"date": "nope"}).status_code
        == 422
    )
    assert client.get("/api/charts/cs_nope/today").status_code == 404


def test_today_brief_streams(client: TestClient, chart) -> None:
    # llm_provider is None → SSE error event (llm_unconfigured), not a 5xx.
    r = client.post(f"/api/charts/{chart.id}/today/brief", params={"date": "2026-09-24"})
    assert r.status_code == 200
    assert "event: error" in r.text or '"type"' in r.text


# ---------- auth ----------


def test_auth_flow(client: TestClient) -> None:
    r = client.post(
        "/api/auth/register",
        json={"email": "A@X.com", "password": "password123"},
    )
    assert r.status_code == 201
    assert r.json()["email"] == "a@x.com"  # lowered
    assert "tv_session" in r.cookies

    assert client.get("/api/auth/me").json()["email"] == "a@x.com"
    assert client.post("/api/auth/logout").status_code == 204
    assert client.get("/api/auth/me").status_code == 401

    r2 = client.post(
        "/api/auth/login", json={"email": "a@x.com", "password": "password123"}
    )
    assert r2.status_code == 200
    assert client.post(
        "/api/auth/login", json={"email": "a@x.com", "password": "wrong-pass"}
    ).status_code == 401
    assert client.post(
        "/api/auth/register",
        json={"email": "a@x.com", "password": "password123"},
    ).status_code == 409


def test_auth_events(client: TestClient, session: Session) -> None:
    client.post(
        "/api/auth/register", json={"email": "e@x.com", "password": "password123"}
    )
    events = {e.event for e in session.query(ProductEvent).all()}
    assert "auth_registered" in events
    client.post("/api/auth/logout")
    client.post(
        "/api/auth/login", json={"email": "e@x.com", "password": "password123"}
    )
    events = {e.event for e in session.query(ProductEvent).all()}
    assert "auth_login" in events


# ---------- ownership merge ----------


def test_ownership_merge_view(client: TestClient, chart) -> None:
    # anonymous profile
    anon = client.post(
        "/api/profiles",
        json={"display_name": "anon", "chart_id": chart.id},
    ).json()

    client.post(
        "/api/auth/register", json={"email": "o@x.com", "password": "password123"}
    )
    owned = client.post(
        "/api/profiles",
        json={"display_name": "owned", "chart_id": chart.id},
    ).json()
    assert owned["id"] != anon["id"]

    # logged-in sees both
    ids = {p["id"] for p in client.get("/api/profiles").json()}
    assert {anon["id"], owned["id"]} <= ids

    # anonymous no longer sees the owned profile (new client = no cookie)
    anon_client = TestClient(client.app)
    ids2 = {p["id"] for p in anon_client.get("/api/profiles").json()}
    assert anon["id"] in ids2 and owned["id"] not in ids2

    # anonymous cannot patch/delete the owned profile
    assert (
        anon_client.patch(
            f"/api/profiles/{owned['id']}", json={"display_name": "x"}
        ).status_code
        == 404
    )
    assert anon_client.delete(f"/api/profiles/{owned['id']}").status_code == 404


# ---------- chat target ----------


def test_chat_sent_event_with_target(
    client: TestClient, chart, session: Session
) -> None:
    # No LLM provider → 503, but the event row lands first.
    r = client.post(
        f"/api/charts/{chart.id}/chat",
        json={
            "message": "Tháng này thế nào?",
            "target": {"scope": "daily", "year": 2026, "month": 9, "day": 24},
        },
    )
    assert r.status_code == 503
    ev = session.query(ProductEvent).filter_by(event="chat_sent").first()
    assert ev is not None and ev.meta == {"hasTarget": True}


def test_chat_target_invalid(client: TestClient, chart) -> None:
    r = client.post(
        f"/api/charts/{chart.id}/chat",
        json={"message": "x", "target": {"scope": "monthly", "year": 2026}},
    )
    assert r.status_code == 422
