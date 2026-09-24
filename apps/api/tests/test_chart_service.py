from datetime import date, datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.domain.birth.contracts import NormalizedBirthMoment
from app.domain.chart.contracts import EngineProfile
from app.domain.chart.service import ChartService, load_engine_profile
from app.infrastructure.db.models import Base, EngineProfileRow
from app.infrastructure.db.session import get_session
from app.infrastructure.xiztro.engine import XiztroEngine
from app.main import create_app


@pytest.fixture()
def session() -> Session:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    with Session(engine) as s:
        s.add(
            EngineProfileRow(
                id="iztro-default-v1",
                content=EngineProfile(
                    id="iztro-default-v1", engineVersion="0.6.1"
                ).model_dump(mode="json"),
            )
        )
        s.commit()
        yield s


@pytest.fixture()
def normalized() -> NormalizedBirthMoment:
    return NormalizedBirthMoment(
        civilDateTime=datetime(1990, 6, 15, 14, 30),
        normalizedDateTime=datetime(1990, 6, 15, 14, 18),
        gender="male",
        timezoneOffsetMinutes=420,
        correctedSolarDate=date(1990, 6, 15),
        timeIndex=4,
        tzKey="Asia/Ho_Chi_Minh",
        tzdataVersion="test",
        resolvedOffsetMinutes=420,
        normalizationMode="true-solar",
    )


def test_cast_and_persist_idempotent(
    session: Session, normalized: NormalizedBirthMoment
) -> None:
    profile = load_engine_profile(session)
    service = ChartService(XiztroEngine())

    snap1 = service.cast_and_persist(session, {"calendar": "solar"}, normalized, profile)
    snap2 = service.cast_and_persist(session, {"calendar": "solar"}, normalized, profile)

    assert snap1.id == snap2.id
    assert snap1.chart_hash == snap2.chart_hash
    assert snap1.chart_json["meta"]["engineVersion"] == "0.6.1"
    assert len(snap1.share_token) > 20
    assert snap1.pattern_hits


def test_get_chart_endpoints(session: Session, normalized: NormalizedBirthMoment) -> None:
    profile = load_engine_profile(session)
    snapshot = ChartService(XiztroEngine()).cast_and_persist(
        session, {"calendar": "solar"}, normalized, profile
    )

    app = create_app()
    app.dependency_overrides[get_session] = lambda: session
    client = TestClient(app)

    resp = client.get(f"/api/charts/{snapshot.id}")
    assert resp.status_code == 200
    body = resp.json()
    assert body["id"] == snapshot.id
    assert body["chartHash"] == snapshot.chart_hash
    assert "config" not in body["chart"]["chart"]

    shared = client.get(f"/s/{snapshot.share_token}")
    assert shared.status_code == 200
    assert shared.json()["id"] == snapshot.id
    assert "shareToken" not in shared.json()

    assert client.get("/api/charts/cs_missing").status_code == 404
    assert client.get("/s/unknown-token").status_code == 404
