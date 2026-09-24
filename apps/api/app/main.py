from fastapi import FastAPI
from sqlalchemy import create_engine

from app.api import charts, chat, compatibility, fortune, health, interpret
from app.infrastructure.llm.openai_compatible import (
    LLMNotConfiguredError,
    OpenAICompatibleProvider,
)
from app.infrastructure.xiztro.engine import XiztroEngine
from app.settings import Settings


def create_app() -> FastAPI:
    settings = Settings()
    db_engine = create_engine(settings.database_url, pool_pre_ping=True)

    app = FastAPI(title="tu-vi-vn API", version="0.1.0")
    app.state.settings = settings
    app.state.db_engine = db_engine
    app.state.ziwei_engine = XiztroEngine()
    app.state.llm_provider = _llm_provider(settings)

    app.include_router(health.router)
    app.include_router(charts.router)
    app.include_router(charts.share_router)
    app.include_router(interpret.router)
    app.include_router(fortune.router)
    app.include_router(chat.router)
    app.include_router(compatibility.router)
    return app


def _llm_provider(settings: Settings) -> OpenAICompatibleProvider | None:
    try:
        return OpenAICompatibleProvider(
            settings.ai_base_url,
            settings.ai_api_key,
            settings.ai_model,
            settings.ai_timeout_seconds,
        )
    except LLMNotConfiguredError:
        return None


app = create_app()
