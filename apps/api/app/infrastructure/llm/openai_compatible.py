"""LLMGateway — OpenAI-compatible provider via httpx (SPEC §14).

Only implementation in V1: POST {AI_BASE_URL}/chat/completions.
Domain code never learns the provider's name. Never log the API key.
"""

import json
from collections.abc import AsyncIterator
from typing import Any, Protocol

import httpx


class LLMProvider(Protocol):
    async def complete(
        self, messages: list[dict[str, str]], **kw: Any
    ) -> str: ...
    def stream(
        self, messages: list[dict[str, str]], **kw: Any
    ) -> AsyncIterator[str]: ...


class LLMNotConfiguredError(RuntimeError):
    pass


class LLMUpstreamError(RuntimeError):
    def __init__(self, status: int | None, detail: str) -> None:
        super().__init__(detail)
        self.status = status


class OpenAICompatibleProvider:
    def __init__(
        self,
        base_url: str,
        api_key: str,
        model: str,
        timeout_seconds: float = 60.0,
    ) -> None:
        if not base_url or not model:
            raise LLMNotConfiguredError("AI_BASE_URL and AI_MODEL must be set")
        self._base_url = base_url.rstrip("/")
        self._api_key = api_key
        self.model = model
        self._timeout = timeout_seconds

    def _headers(self) -> dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if self._api_key:
            headers["Authorization"] = f"Bearer {self._api_key}"
        return headers

    def _payload(
        self, messages: list[dict[str, str]], stream: bool, kw: dict[str, Any]
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {"model": self.model, "messages": messages}
        if stream:
            payload["stream"] = True
        for key in ("temperature", "top_p", "seed", "max_tokens"):
            if kw.get(key) is not None:
                payload[key] = kw[key]
        return payload

    async def complete(self, messages: list[dict[str, str]], **kw: Any) -> str:
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            resp = await client.post(
                f"{self._base_url}/chat/completions",
                headers=self._headers(),
                json=self._payload(messages, stream=False, kw=kw),
            )
            if resp.status_code >= 400:
                raise LLMUpstreamError(resp.status_code, "LLM upstream error")
            data = resp.json()
            content: str = data["choices"][0]["message"]["content"]
            return content

    async def stream(
        self, messages: list[dict[str, str]], **kw: Any
    ) -> AsyncIterator[str]:
        client = httpx.AsyncClient(timeout=self._timeout)
        try:
            async with client.stream(
                "POST",
                f"{self._base_url}/chat/completions",
                headers=self._headers(),
                json=self._payload(messages, stream=True, kw=kw),
            ) as resp:
                if resp.status_code >= 400:
                    await resp.aread()
                    raise LLMUpstreamError(resp.status_code, "LLM upstream error")
                async for line in resp.aiter_lines():
                    if not line.startswith("data:"):
                        continue
                    payload = line[5:].strip()
                    if payload == "[DONE]":
                        break
                    try:
                        chunk = json.loads(payload)
                    except json.JSONDecodeError:
                        continue
                    delta = (
                        chunk.get("choices", [{}])[0]
                        .get("delta", {})
                        .get("content")
                    )
                    if delta:
                        yield delta
        finally:
            await client.aclose()
