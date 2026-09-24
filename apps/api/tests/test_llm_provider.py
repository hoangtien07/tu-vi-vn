"""OpenAICompatibleProvider: transient upstream errors are retried."""

import httpx
import pytest

from app.infrastructure.llm.openai_compatible import (
    LLMUpstreamError,
    OpenAICompatibleProvider,
)


def _provider(handler):
    return OpenAICompatibleProvider(
        "http://llm.test", "k", "m", transport=httpx.MockTransport(handler)
    )


@pytest.mark.asyncio
async def test_complete_retries_retryable_status():
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(1)
        if len(calls) < 3:
            return httpx.Response(429, json={"error": "rate limited"})
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": "ok"}}]},
        )

    out = await _provider(handler).complete([{"role": "user", "content": "x"}])
    assert out == "ok"
    assert len(calls) == 3


@pytest.mark.asyncio
async def test_complete_does_not_retry_permanent_status():
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(1)
        return httpx.Response(400, json={"error": "bad request"})

    with pytest.raises(LLMUpstreamError):
        await _provider(handler).complete([{"role": "user", "content": "x"}])
    assert len(calls) == 1


@pytest.mark.asyncio
async def test_complete_gives_up_after_max_attempts():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(503, json={"error": "overloaded"})

    with pytest.raises(LLMUpstreamError):
        await _provider(handler).complete([{"role": "user", "content": "x"}])


@pytest.mark.asyncio
async def test_stream_retries_until_first_delta():
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(1)
        if len(calls) == 1:
            return httpx.Response(429, json={"error": "rate limited"})
        return httpx.Response(
            200,
            text='data: {"choices":[{"delta":{"content":"chào"}}]}\n\ndata: [DONE]\n\n',
        )

    deltas = [
        d async for d in _provider(handler).stream([{"role": "user", "content": "x"}])
    ]
    assert deltas == ["chào"]
    assert len(calls) == 2
