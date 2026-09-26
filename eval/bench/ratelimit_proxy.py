"""Rate-limiting proxy for Gemini OpenAI-compat free tier (eval only).

Free-tier quota is per minute per model per project (~15-20 RPM). The app's
retry backoff (1s/2s) never outlasts a 429 window, so this proxy serializes
requests per upstream model, paces them at GAP_SECONDS, and retries 429/503
internally honoring RetryInfo.retryDelay — callers see a stable endpoint.

    UPSTREAM_KEY=<gemini key> uv run uvicorn eval.bench.ratelimit_proxy:app --port 8590
    AI_BASE_URL=http://127.0.0.1:8590  (OpenAI-compat path appended)
"""

from __future__ import annotations

import asyncio
import json
import os
import time

import httpx
from fastapi import FastAPI, Request
from fastapi.responses import Response, StreamingResponse

UPSTREAM_BASE = "https://generativelanguage.googleapis.com/v1beta/openai"
GAP_SECONDS = float(os.environ.get("PROXY_GAP_SECONDS", "4.5"))
MAX_ATTEMPTS = 8

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
        for d in resp.json().get("error", {}).get("details", []):
            if d.get("@type", "").endswith("RetryInfo"):
                return float(d["retryDelay"].rstrip("s")) + 1.0
    except Exception:  # noqa: BLE001
        pass
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


@app.post("/chat/completions")
async def chat(request: Request) -> Response:
    body = await request.body()
    try:
        model = json.loads(body).get("model", "?")
    except json.JSONDecodeError:
        return Response(status_code=400, content=b'{"error":"bad json"}')
    lock = _locks.setdefault(model, asyncio.Lock())
    async with lock:  # serialize per model → pacing is real, not advisory
        for attempt in range(MAX_ATTEMPTS):
            gap = GAP_SECONDS - (time.monotonic() - _last_call.get(model, -1e9))
            if gap > 0:
                await asyncio.sleep(gap)
            _last_call[model] = time.monotonic()
            resp = await _forward(body)
            if resp.status_code == 429 or resp.status_code >= 500:
                if attempt < MAX_ATTEMPTS - 1:
                    await asyncio.sleep(_retry_delay(resp))
                    continue
            break
        if json.loads(body).get("stream"):
            async def gen():
                yield resp.content
            # upstream SSE already buffered by httpx — replay as stream
            return StreamingResponse(gen(), status_code=resp.status_code,
                                     media_type="text/event-stream")
        return Response(status_code=resp.status_code, content=resp.content,
                        media_type="application/json")


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}
