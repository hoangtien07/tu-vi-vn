import httpx
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import SQLAlchemyError

from app.infrastructure.xiztro.knowledge import KnowledgeRegistry

router = APIRouter(tags=["health"])


def check_db(engine: Engine) -> bool:
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except SQLAlchemyError:
        return False


@router.get("/health")
def health(request: Request) -> JSONResponse:
    """App health: API + DB only. AI dependency state must NOT block this."""
    db_ok = check_db(request.app.state.db_engine)
    status_code = 200 if db_ok else 503
    return JSONResponse(
        status_code=status_code,
        content={
            "status": "ok" if db_ok else "degraded",
            "api": "up",
            "db": "up" if db_ok else "down",
            "knowledgePack": KnowledgeRegistry.version_info()["id"],
        },
    )


@router.get("/health/dependencies")
def dependencies(request: Request) -> dict[str, object]:
    """External dependency state (OpenAI-compatible AI endpoint). Informational only."""
    settings = request.app.state.settings
    if not settings.ai_base_url:
        return {"ai": {"configured": False, "reachable": None}}

    try:
        resp = httpx.get(f"{settings.ai_base_url.rstrip('/')}/models", timeout=5.0)
        reachable = resp.status_code < 500
    except httpx.HTTPError:
        reachable = False

    return {"ai": {"configured": True, "reachable": reachable}}
