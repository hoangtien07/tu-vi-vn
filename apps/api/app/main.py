from fastapi import FastAPI
from sqlalchemy import create_engine

from app.api import charts, health
from app.infrastructure.xiztro.engine import XiztroEngine
from app.settings import Settings


def create_app() -> FastAPI:
    settings = Settings()
    db_engine = create_engine(settings.database_url, pool_pre_ping=True)

    app = FastAPI(title="tu-vi-vn API", version="0.1.0")
    app.state.settings = settings
    app.state.db_engine = db_engine
    app.state.ziwei_engine = XiztroEngine()

    app.include_router(health.router)
    app.include_router(charts.router)
    app.include_router(charts.share_router)
    return app


app = create_app()
