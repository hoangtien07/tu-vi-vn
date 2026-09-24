
import pytest
from fastapi.testclient import TestClient


@pytest.fixture()
def client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setenv("DATABASE_URL", "sqlite+pysqlite:///:memory:")
    monkeypatch.setenv("AI_BASE_URL", "")
    from app.main import create_app

    return TestClient(create_app())


def test_health_ok_with_db(client: TestClient) -> None:
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok", "api": "up", "db": "up"}


def test_health_degraded_when_db_down(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://postgres:x@127.0.0.1:1/none")
    monkeypatch.setenv("AI_BASE_URL", "")
    from app.main import create_app

    resp = TestClient(create_app()).get("/health")
    assert resp.status_code == 503
    assert resp.json()["db"] == "down"


def test_dependencies_unconfigured(client: TestClient) -> None:
    resp = client.get("/health/dependencies")
    assert resp.status_code == 200
    assert resp.json() == {"ai": {"configured": False, "reachable": None}}
