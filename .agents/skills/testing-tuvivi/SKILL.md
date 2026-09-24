---
name: testing-tuvivi
description: How to stand up tu-vi-vn (FastAPI + Next.js) locally for E2E testing without docker-compose — alembic-first, env vars, known gotchas.
---

# Testing tu-vi-vn locally

## Dev servers (direct, no docker)

```bash
# 1. API — database file must be migrated FIRST; the app never runs create_all/migrations itself
cd apps/api
DATABASE_URL='sqlite+pysqlite:////tmp/tuvivi.db' uv run alembic upgrade head
DATABASE_URL='sqlite+pysqlite:////tmp/tuvivi.db' uv run uvicorn app.main:app --port 8000

# 2. Web — proxies /api/* to API_INTERNAL_URL (default http://localhost:8000)
cd apps/web && pnpm dev --port 3000
```

- `DATABASE_URL` is read by BOTH `alembic/env.py` (`os.environ["DATABASE_URL"]` — crashes if unset) and `app/settings.py`. Default is `sqlite+pysqlite:///:memory:` which loses everything and skips migration unless you run alembic against the same URL — always use a file path for manual testing.
- Only ONE `next dev` may run per project dir. If `pnpm dev` exits with "Another next dev server is already running", check the stale server's env (`cat /proc/<pid>/environ | tr '\0' '\n' | grep API_INTERNAL_URL`) — a leftover dev server may proxy to a dead API port and every /api/* call 500s. Kill it and start fresh.
- Health endpoint is `GET /health` (NOT `/api/health`). `/api/charts/<bad-id>` → 404 is a good "is the API up" probe through the web proxy.
- Verify proxy: `curl -o /dev/null -w '%{http_code}' http://localhost:3000/api/charts/x` → 404 means proxy reaches the API (500 = proxy broken).

## AI / interpret degradation

`app.state.llm_provider` is `None` unless `AI_BASE_URL` + `AI_MODEL` are set (key optional). With no AI env:
- `POST /api/charts/{id}/interpret` SSE stream emits `metadata` → `evidence` → `error {type: "llm_unconfigured"}`; the web panel renders "AI endpoint chưa được cấu hình — thử lại sau."
- `POST /api/charts/{id}/chat` → 503 "AI endpoint not configured"
- `POST /api/compatibility` is the real hợp bàn endpoint (body `{chart_a_id, chart_b_id, target?, namespace?}`, same SSE contract as interpret); `GET /api/compatibility/{run_id}` reads a finished run. The old `POST /api/charts/{id}/compatibility` stub is gone (404). Web UI lives at `/compatibility` (accepts `?a=<cs_id>&b=<cs_id>`).

## Known form behavior (not bugs)

- "Điều chỉnh giờ chân thái dương" (trueSolarTimeEnabled) defaults CHECKED; TST requires longitude → a plain submit 422s with "trueSolarTimeEnabled requires longitude" shown in a rose banner. Golden-path tests must uncheck it or supply longitude.
- Form inputs are uncontrolled → a failed submit clears date/time (server-action re-render). Re-fill before retrying.
- VN timezone divergence windows requiring birthRegion: 1954-10-01→1955-07-01 and 1960-01-01→1975-06-12 23:00. Same date resolves +480 (south/central) vs +420 (north) → different chart ids.
- Charts are idempotent: identical birth input → identical `id`, `chartHash`, `shareToken` — useful for asserting determinism.
- Birth 23:00–23:59 → `timeIndex: 12` (late Tý); `POST` returns `birth.normalized` with full normalizer detail — curl is the fast way to assert normalizer behavior instead of reading the board.

## Browser specifics

- The radio labels "Dương lịch"/"Âm lịch" sit ~70px apart; click the label TEXT or the radio circle directly — clicks between them may land on the wrong label.
- `type=date` fields accept `MM/DD/YYYY` typed digits; `type=time` accepts 24-hour "1430" typed digits (renders as 02:30 PM).
