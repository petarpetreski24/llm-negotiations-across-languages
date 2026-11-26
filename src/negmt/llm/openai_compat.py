"""Client for OpenAI-compatible chat servers: vLLM on the FINKI GPUs, or Ollama as in the CIIT paper.

Structured output is requested with `response_format` (JSON schema), which vLLM enforces
with guided decoding. Model-specific switches (e.g. Qwen's `chat_template_kwargs:
{"enable_thinking": false}`) and sampling defaults come from configs/models.yaml.
"""

from __future__ import annotations

import re
import time
from typing import Any, Optional

import httpx

from negmt.llm.base import LLMResponse

_THINK = re.compile(r"<think>.*?</think>\s*", re.S)
_RETRY_STATUS = {408, 409, 429, 500, 502, 503, 504}


class LLMServerError(RuntimeError):
    pass


class OpenAICompatClient:
    def __init__(
        self,
        base_url: str,
        served_name: str,
        model: Optional[str] = None,
        *,
        api_key: str = "EMPTY",
        sampling: Optional[dict[str, Any]] = None,
        extra_body: Optional[dict[str, Any]] = None,
        max_tokens: int = 1024,
        timeout: float = 180.0,
        max_retries: int = 4,
        backoff: float = 2.0,
        transport: Optional[httpx.BaseTransport] = None,
    ):
        self.base_url = base_url.rstrip("/")
        self.served_name = served_name
        self.model = model or served_name
        self.sampling = dict(sampling or {})
        self.extra_body = dict(extra_body or {})
        self.max_tokens = max_tokens
        self.max_retries = max_retries
        self.backoff = backoff
        self._http = httpx.Client(
            timeout=timeout, transport=transport, headers={"Authorization": f"Bearer {api_key}"}
        )

    # -- generic chat call (also used by LLM-based translators) --

    def chat(self, messages: list[dict[str, Any]], **params: Any) -> tuple[str, dict[str, int], float]:
        body = {"model": self.served_name, "messages": messages, "max_tokens": self.max_tokens}
        body.update(self.sampling)
        body.update(self.extra_body)
        body.update({k: v for k, v in params.items() if v is not None})

        t0 = time.perf_counter()
        last: Exception | None = None
        for attempt in range(self.max_retries + 1):
            try:
                r = self._http.post(f"{self.base_url}/chat/completions", json=body)
                if r.status_code in _RETRY_STATUS:
                    raise LLMServerError(f"HTTP {r.status_code}: {r.text[:200]}")
                if r.status_code >= 400:  # client errors are not retried
                    raise ValueError(f"HTTP {r.status_code}: {r.text[:500]}")
                data = r.json()
                text = data["choices"][0]["message"].get("content") or ""
                usage = data.get("usage") or {}
                return (
                    _THINK.sub("", text).strip(),
                    {"in": int(usage.get("prompt_tokens", 0)), "out": int(usage.get("completion_tokens", 0))},
                    (time.perf_counter() - t0) * 1000,
                )
            except (httpx.TransportError, LLMServerError) as err:
                last = err
                if attempt < self.max_retries:
                    time.sleep(self.backoff * (2**attempt))
        raise LLMServerError(f"{self.model}: gave up after {self.max_retries + 1} attempts: {last}")

    # -- negotiator interface --

    def generate(self, system, messages, schema, *, seed=None, temperature=None) -> LLMResponse:
        full = [{"role": "system", "content": system}] + list(messages)
        text, usage, ms = self.chat(
            full,
            response_format={"type": "json_schema", "json_schema": {"name": "agent_output", "schema": schema, "strict": True}},
            seed=seed,
            temperature=temperature,
        )
        return LLMResponse(text=text, model=self.model, input_tokens=usage["in"], output_tokens=usage["out"], ms=ms)

    def close(self) -> None:
        self._http.close()
