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

## v0.2 learnings

- Client-side `apiFetch` used to call the absolute `API_INTERNAL_URL` — cross-origin, browser blocks it (CORS preflight 405). Fixed: client calls use relative `/api/*` (same-origin rewrite), server calls keep the absolute URL. If you ever see `Failed to fetch` only in the browser while curl works, check this first. Workaround for diagnosing: `google-chrome --disable-web-security --user-data-dir=/tmp/chrome-nosec` (banner visible, transparent).
- `sqlite3` CLI is absent — use `uv run python -c "import sqlite3; …"` from apps/api to inspect `product_events`/`profiles`.
- Compatibility testing needs ≥2 saved profiles (create via chart page "Lưu vào hồ sơ" or `POST /api/profiles`).
- `reading_reopened` fires twice per page open in dev (React StrictMode double-effect) — prod fires once; expected, not a bug.
- Time Navigator facts render after clicking "Xem vận trình" (button-driven, not on open).

## v0.3 learnings (auth + today)

- `tv_session` cookie is `Path=/` (required so document/RSC GETs carry it — SSR apiFetch forwards it, giving server-rendered pages the logged-in merge view). Fixed from an earlier `Path=/api` bug that hid user-owned profiles on /profiles; expect `Max-Age=2592000` (30d), HttpOnly, SameSite=lax.
- `AuthNav` re-checks /api/auth/me on every `usePathname()` change (root layout persists across client nav) → header updates immediately after login/register redirect, no reload needed.
- GET /api/charts/{id}/today `facts.<scope>` objects expose `index` + `palaceNameKeys[]`/`palaceNames[]` arrays — the hosting palace is `palaceNameKeys[scope.index]` (there is no `palace` key). Highlights are derived via `PALACE_TOPIC_HINT` on the nameKey; on mapped palaces (soul/career/wealth/spouse/health) they render e.g. "Tổng quan — Lưu nhật tại cung Mệnh · tứ hóa lưu nhật: …".
- `chat_sent` product_event is committed BEFORE the LLM call → it lands in product_events even when chat 503s; assert via sqlite not just HTTP status.
- DevTools Application→Cookies may show an empty grid for localhost:3000 even when tv_session exists — prove the cookie via Network tab (any /api/* request 200 that requires auth, e.g. /api/auth/me) instead.
- Auth throttle: POST /api/auth/login is rate-limited 10 attempts/5min/IP → 429; keep wrong-password tests to 1-2 attempts per run.
- Register/login pages: email + password (min 8) inputs only; 401 → "Email hoặc mật khẩu chưa đúng.", 409 → "Email đã được đăng ký.", success → router.push("/profiles").

## K-line strip (Time Navigator, main ≥ f2776e1)

- `/chart/{id}/time` renders `KlineStrip` below controls whenever level ≠ "Đại hạn" — fetches `GET /api/charts/{id}/temporal/decade?year=<selectedYear>` on mount (no "Xem vận trình" needed). Decade buttons have aria-labels "Đại hạn trước"/"Đại hạn sau" shifting ±10y.
- Glyph = button `title="{year} · {stem} {branch} · {palaceName}"`; each chip has `title="{Lộc|Quyền|Khoa|Kỵ} — {star}"`. Chip tooltips are 16px targets — hover precisely or you'll get the glyph's title instead.
- Glyph click → `onSelectYear` updates the navigator's year select + clears facts; amber border marks selection, emerald dot marks current year.
- Known caveat (spec mismatch under review): `palaceName` on every glyph and the đại hạn header resolves to "Mệnh" because `_scope_brief` reads the REBASED temporal palace layout (the position hosting that scope's Mệnh is always named "Mệnh"). SPEC_KLINE's example shows varying natal palace names per glyph — when verifying, compare glyph labels against natal palace names, not just presence.
- The strip is deterministic — API log should show only `GET …/temporal/decade` + `GET …/temporal`; any interpret/chat call on render is a defect.
- Footer link clicks on the chart page are finicky — prefer direct URL nav to `/chart/{id}/time`.
