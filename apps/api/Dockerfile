FROM python:3.12-slim

COPY --from=ghcr.io/astral-sh/uv:0.8.13 /uv /uvx /bin/

WORKDIR /srv/app
COPY apps/api /srv/app
COPY packages/knowledge /srv/packages/knowledge
RUN uv sync --frozen --no-dev

EXPOSE 8000
CMD ["uv", "run", "--no-dev", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
