#!/usr/bin/env python3
"""Devin-session LLM worker shim — OpenAI-compatible /chat/completions backed
by persistent Devin sessions (bench-only tool; Gate E runs without a paid LLM
endpoint).

Workers are pre-created Devin sessions (e.g. swe-2-high) that obey a fixed
contract: each user message is a flattened chat request ([SYSTEM]/[USER]
parts) and the reply is the assistant content verbatim — no tools, no files.

    DEVIN_API_KEY    Sessions API key (apk_...)
    DEVIN_WORKER_IDS comma-separated session ids (devin-...)
    SHIM_PORT        default 8123

Round-robin across workers with a per-worker lock: turns serialize per worker
but parallelize across the pool. Polls GET /v1/sessions/{id} until a new
devin_message lands and the session settles (status_enum blocked /
waiting_for_user). stream=true emits the reply as a single SSE delta.
"""
from __future__ import annotations

import asyncio
import itertools
import json
import os
import time

import httpx
import uvicorn
from fastapi import FastAPI
from fastapi.responses import JSONResponse, StreamingResponse

DEVIN_API = "https://api.devin.ai/v1"
API_KEY = os.environ["DEVIN_API_KEY"]
WORKERS = [w.strip() for w in os.environ["DEVIN_WORKER_IDS"].split(",") if w.strip()]
POLL_SECONDS = 3.0
TURN_TIMEOUT = 420.0
SETTLED = {"blocked", "waiting_for_user", "sleeping", "finished", "expired", "suspended"}

app = FastAPI()
_locks = {w: asyncio.Lock() for w in WORKERS}
_cycle = itertools.cycle(WORKERS)


def _flatten(messages: list[dict]) -> str:
    parts = []
    for m in messages:
        role = str(m.get("role", "user")).upper()
        parts.append(f"[{role}]\n{m.get('content', '')}")
    return "\n\n".join(parts)


_MAX_MESSAGE = 28000  # sessions API rejects messages >= 30000 chars


async def _upload(client: httpx.AsyncClient, prompt: str) -> str:
    r = await client.post(
        f"{DEVIN_API}/attachments",
        headers={"Authorization": f"Bearer {API_KEY}"},
        files={"file": ("prompt.txt", prompt.encode())},
        timeout=60,
    )
    r.raise_for_status()
    return str(r.json())


async def _worker_turn(client: httpx.AsyncClient, worker: str, prompt: str) -> str:
    headers = {"Authorization": f"Bearer {API_KEY}"}
    base = f"{DEVIN_API}/sessions/{worker}"
    before = (await client.get(base, headers=headers)).json()
    n_devin = sum(1 for m in before.get("messages", []) if m.get("type") == "devin_message")
    message = prompt
    if len(prompt) > _MAX_MESSAGE:
        url = await _upload(client, prompt)
        message = (
            "Request nằm trong file attachment — đọc bằng download_attachment: "
            f"{url}\nĐọc kỹ phần [SYSTEM] trong file rồi trả lời đúng phần "
            "assistant output cho [USER] theo quy tắc worker."
        )
    resp = await client.post(f"{base}/message", headers=headers, json={"message": message})
    resp.raise_for_status()
    deadline = time.monotonic() + TURN_TIMEOUT
    while time.monotonic() < deadline:
        await asyncio.sleep(POLL_SECONDS)
        snap = (await client.get(base, headers=headers)).json()
        devins = [m for m in snap.get("messages", []) if m.get("type") == "devin_message"]
        if len(devins) > n_devin and snap.get("status_enum") in SETTLED:
            return devins[-1]["message"]
    raise TimeoutError(f"worker {worker} did not settle within {TURN_TIMEOUT}s")


async def _chat(messages: list[dict]) -> str:
    prompt = _flatten(messages)
    last_exc: Exception | None = None
    async with httpx.AsyncClient(timeout=30) as client:
        for _ in range(len(WORKERS)):
            worker = next(_cycle)
            async with _locks[worker]:
                try:
                    return await _worker_turn(client, worker, prompt)
                except Exception as exc:  # noqa: BLE001 — try next worker
                    last_exc = exc
    raise RuntimeError(f"all workers failed: {last_exc}")


def _completion(content: str, model: str) -> dict:
    return {
        "id": f"chatcmpl-devin-{int(time.time() * 1000)}",
        "object": "chat.completion",
        "created": int(time.time()),
        "model": model,
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": content},
                "finish_reason": "stop",
            }
        ],
        "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
    }


@app.post("/chat/completions")
@app.post("/v1/chat/completions")
async def chat_completions(body: dict) -> object:
    model = body.get("model") or "devin-worker"
    try:
        content = await _chat(body.get("messages") or [])
    except Exception as exc:  # noqa: BLE001
        return JSONResponse(
            status_code=502,
            content={"error": {"message": str(exc), "code": 502}},
        )

    if body.get("stream"):
        chunks = [
            {"id": "chatcmpl-devin", "object": "chat.completion.chunk",
             "choices": [{"index": 0, "delta": {"role": "assistant"}, "finish_reason": None}]},
            {"id": "chatcmpl-devin", "object": "chat.completion.chunk",
             "choices": [{"index": 0, "delta": {"content": content}, "finish_reason": None}]},
            {"id": "chatcmpl-devin", "object": "chat.completion.chunk",
             "choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}]},
        ]

        async def gen():
            for c in chunks:
                yield f"data: {json.dumps(c)}\n\n"
                await asyncio.sleep(0)
            yield "data: [DONE]\n\n"

        return StreamingResponse(gen(), media_type="text/event-stream")
    return _completion(content, model)


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "workers": len(WORKERS)}


if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=int(os.environ.get("SHIM_PORT", "8123")))
