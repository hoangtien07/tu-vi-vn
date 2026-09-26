#!/bin/sh
# Render free tier has no preDeployCommand — migrate at boot (idempotent).
set -e
uv run --no-dev alembic upgrade head
exec uv run --no-dev uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}"
