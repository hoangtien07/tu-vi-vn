from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


def _normalize_db_url(url: str) -> str:
    # Render/Heroku-style `postgres://` has no driver; psycopg is our driver.
    if url.startswith("postgres://"):
        return "postgresql+psycopg://" + url[len("postgres://"):]
    if url.startswith("postgresql://"):
        return "postgresql+psycopg://" + url[len("postgresql://"):]
    return url


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "sqlite+pysqlite:///:memory:"

    @field_validator("database_url", mode="before")
    @classmethod
    def _db_url(cls, v: object) -> object:
        return _normalize_db_url(v) if isinstance(v, str) else v
    ai_base_url: str = ""
    ai_api_key: str = ""
    ai_model: str = ""
    ai_timeout_seconds: float = 60.0
    # SPEC_V04 I17: "builtin" | "none" | path to an eval/packs/*.json file.
    knowledge_pack: str = "builtin"
