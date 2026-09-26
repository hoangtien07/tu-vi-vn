"""Rate-limiting proxy for Gemini OpenAI-compat free tier (eval only).

Free-tier quota is per minute per model per project (~15-20 RPM). The app's
retry backoff (1s/2s) never outlasts a 429 window, so this proxy serializes
requests per upstream model, paces them at GAP_SECONDS, and retries 429/503
internally honoring RetryInfo.retryDelay — callers see a stable endpoint.

    UPSTREAM_KEY=<gemini key> uv run uvicorn eval.bench.ratelimit_proxy:app --port 8590
    AI_BASE_URL=http://127.0.0.1:8590  (OpenAI-compat path appended)

Security: this proxy spends UPSTREAM_KEY quota on every request. It refuses
non-loopback clients unless PROXY_TOKEN is set — then callers must send
`Authorization: Bearer $PROXY_TOKEN`. Never bind it to a public interface.

Streaming: upstream responses are buffered (needed for internal retries), so
while pacing/retrying/waiting the client receives `: keepalive` SSE comments
every ~5s — spec-compliant parsers (incl. the app's, which skips non-`data:`
lines) ignore them and read timeouts never fire. A terminal upstream failure
is surfaced as `event: error` + data lines on the 200 stream.
"""

from __future__ import annotations

import asyncio
import json
import os
import time
from collections.abc import AsyncIterator

import httpx
from fastapi import FastAPI, Request
from fastapi.responses import Response, StreamingResponse

UPSTREAM_BASE = "https://generativelanguage.googleapis.com/v1beta/openai"
GAP_SECONDS = float(os.environ.get("PROXY_GAP_SECONDS", "4.5"))
PROXY_TOKEN = os.environ.get("PROXY_TOKEN", "")
MAX_ATTEMPTS = 8
KEEPALIVE_SECONDS = 5.0

_LOOPBACK = {"127.0.0.1", "::1"}
_KEEPALIVE = b": keepalive\n\n"

app = FastAPI()
_locks: dict[str, asyncio.Lock] = {}
_last_call: dict[str, float] = {}
_client: httpx.AsyncClient | None = None


def _client_once() -> httpx.AsyncClient:
    global _client
    if _client is None:
        _client = httpx.AsyncClient(timeout=600.0)
    return _client


def _retry_delay(resp: httpx.Response) -> float:
    try:
        details = resp.json().get("error", {}).get("details") or []
    except ValueError:
        details = []
    for d in details:
        try:
            if d.get("@type", "").endswith("RetryInfo"):
                return float(d["retryDelay"].rstrip("s")) + 1.0
        except (AttributeError, KeyError, ValueError):
            continue
    return 30.0


async def _forward(body: bytes) -> httpx.Response:
    return await _client_once().post(
        f"{UPSTREAM_BASE}/chat/completions",
        content=body,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {os.environ['UPSTREAM_KEY']}",
        },
    )


def _denied(request: Request) -> Response | None:
    if PROXY_TOKEN:
        if request.headers.get("authorization") != f"Bearer {PROXY_TOKEN}":
            return Response(status_code=401, content=b'{"error":"unauthorized"}')
        return None
    host = request.client.host if request.client else ""
    if host not in _LOOPBACK:
        return Response(status_code=403, content=b'{"error":"loopback only"}')
    return None


async def _paced_attempt(model: str, body: bytes) -> httpx.Response:
    gap = GAP_SECONDS - (time.monotonic() - _last_call.get(model, -1e9))
    if gap > 0:
        await asyncio.sleep(gap)
    _last_call[model] = time.monotonic()
    return await _forward(body)


async def _call(model: str, body: bytes) -> httpx.Response:
    lock = _locks.setdefault(model, asyncio.Lock())
    async with lock:  # serialize per model → pacing is real, not advisory
        resp = None
        for attempt in range(MAX_ATTEMPTS):
            resp = await _paced_attempt(model, body)
            if (
                resp.status_code == 429 or resp.status_code >= 500
            ) and attempt < MAX_ATTEMPTS - 1:
                await asyncio.sleep(_retry_delay(resp))
                continue
            break
        assert resp is not None
        return resp


async def _call_streaming(model: str, body: bytes) -> AsyncIterator[bytes]:
    """Same retry loop, but yields keepalives so the client's read timeout
    never fires during long paced waits or a slow upstream generation."""
    lock = _locks.setdefault(model, asyncio.Lock())
    async with lock:
        resp = None
        for attempt in range(MAX_ATTEMPTS):
            gap_end = _last_call.get(model, -1e9) + GAP_SECONDS
            while (left := gap_end - time.monotonic()) > 0:
                await asyncio.sleep(min(KEEPALIVE_SECONDS, left))
                yield _KEEPALIVE
            _last_call[model] = time.monotonic()
            task = asyncio.ensure_future(_forward(body))
            while not task.done():
                await asyncio.sleep(KEEPALIVE_SECONDS)
                yield _KEEPALIVE
            resp = task.result()
            if (
                resp.status_code == 429 or resp.status_code >= 500
            ) and attempt < MAX_ATTEMPTS - 1:
                delay_end = time.monotonic() + _retry_delay(resp)
                while (left := delay_end - time.monotonic()) > 0:
                    await asyncio.sleep(min(KEEPALIVE_SECONDS, left))
                    yield _KEEPALIVE
                continue
            break
    assert resp is not None
    if resp.status_code >= 400:
        yield b"event: error\n"
        for line in resp.content.splitlines() or [b"{}"]:
            yield b"data: " + line + b"\n"
        yield b"data: [DONE]\n\n"
        return
    yield resp.content


@app.post("/chat/completions")
async def chat(request: Request) -> Response:
    denied = _denied(request)
    if denied is not None:
        return denied
    body = await request.body()
    try:
        payload = json.loads(body)
        model = payload.get("model", "?")
    except json.JSONDecodeError:
        return Response(status_code=400, content=b'{"error":"bad json"}')
    if payload.get("stream"):
        return StreamingResponse(
            _call_streaming(model, body), media_type="text/event-stream"
        )
    resp = await _call(model, body)
    return Response(
        status_code=resp.status_code,
        content=resp.content,
        media_type="application/json",
    )


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}
