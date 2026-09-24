import datetime as dt
from collections.abc import AsyncIterator
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.domain.birth.contracts import NormalizedBirthMoment
from app.domain.chart.contracts import EngineProfile
from app.domain.chart.fortune import year_anchor
from app.domain.chart.service import ChartService
from app.infrastructure.db.models import Base, EngineProfileRow
from app.infrastructure.db.session import get_session
from app.infrastructure.xiztro.engine import XiztroEngine
from app.main import create_app


class FakeProvider:
    model = "fake-1"

    def __init__(self, reply: str = "Lá số cho thấy...") -> None:
        self._reply = reply
        self.last_messages: list[dict[str, str]] | None = None

    async def stream(
        self, messages: list[dict[str, str]], **kw: Any
    ) -> AsyncIterator[str]:
        yield self._reply

    async def complete(self, messages: list[dict[str, str]], **kw: Any) -> str:
        self.last_messages = messages
        return self._reply


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


def _client(session: Session, provider=None) -> TestClient:
    app = create_app()
    app.state.llm_provider = provider
    app.dependency_overrides[get_session] = lambda: session
    return TestClient(app)


def test_year_anchor_is_tet() -> None:
    anchor = year_anchor(2028)
    assert anchor.month in (1, 2)


def test_fortune_year(session: Session, snapshot) -> None:
    client = _client(session)
    resp = client.get(f"/api/charts/{snapshot.id}/fortune/year/2028")
    assert resp.status_code == 200
    body = resp.json()
    assert body["year"] == 2028
    assert "yearly" in body["scopes"]
    assert body["anchorDate"] == year_anchor(2028).isoformat()


def test_fortune_before_birth_422(session: Session, snapshot) -> None:
    client = _client(session)
    resp = client.get(f"/api/charts/{snapshot.id}/fortune/year/1980")
    assert resp.status_code == 422


def test_chat_roundtrip(session: Session, snapshot) -> None:
    provider = FakeProvider("Mệnh cách độc lập.")
    client = _client(session, provider)

    resp = client.post(
        f"/api/charts/{snapshot.id}/chat",
        json={"message": "Sự nghiệp tôi thế nào?"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["reply"] == "Mệnh cách độc lập."
    convo = body["conversationId"]

    resp2 = client.post(
        f"/api/charts/{snapshot.id}/chat",
        json={"message": "Còn năm tới?", "conversation_id": convo},
    )
    assert resp2.status_code == 200
    assert provider.last_messages is not None
    roles = [m["role"] for m in provider.last_messages]
    assert roles[0] == "system"
    assert roles.count("user") == 2
    assert "assistant" in roles


def test_chat_unconfigured_503(session: Session, snapshot) -> None:
    client = _client(session, None)
    resp = client.post(
        f"/api/charts/{snapshot.id}/chat", json={"message": "hi"}
    )
    assert resp.status_code == 503


def test_interpret_yearly_target(session: Session, snapshot) -> None:
    provider = FakeProvider("Năm 2028 vận khí tốt [E001].")
    client = _client(session, provider)
    resp = client.post(
        f"/api/charts/{snapshot.id}/interpret",
        json={"topic": "career", "target": {"scope": "yearly", "year": 2028}},
    )
    assert resp.status_code == 200
    assert "horoscope_fact" in resp.text


def test_interpret_target_before_birth_422(session: Session, snapshot) -> None:
    client = _client(session, FakeProvider("x [E001]."))
    resp = client.post(
        f"/api/charts/{snapshot.id}/interpret",
        json={"topic": "career", "target": "1980-01-01"},
    )
    assert resp.status_code == 422
