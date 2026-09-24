from fastapi import FastAPI
from sqlalchemy import create_engine

from app.api import health
from app.settings import Settings


def create_app() -> FastAPI:
    settings = Settings()
    engine = create_engine(settings.database_url, pool_pre_ping=True)

    app = FastAPI(title="tu-vi-vn API", version="0.1.0")
    app.state.settings = settings
    app.state.engine = engine

    app.include_router(health.router)
    return app


app = create_app()
