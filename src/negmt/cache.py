"""Content-addressed cache of model responses, so reruns and re-analysis never call a model twice."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Optional

from negmt.llm.base import LLMResponse


def cache_key(**parts: Any) -> str:
    blob = json.dumps(parts, ensure_ascii=False, sort_keys=True, default=str)
    return hashlib.sha256(blob.encode()).hexdigest()


class ResponseCache:
    def __init__(self, root: str | Path):
        self.root = Path(root)

    def _path(self, key: str) -> Path:
        return self.root / key[:2] / f"{key}.json"

    def get(self, key: str) -> Optional[dict]:
        p = self._path(key)
        return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None

    def put(self, key: str, value: dict) -> None:
        p = self._path(key)
        p.parent.mkdir(parents=True, exist_ok=True)
        tmp = p.with_suffix(".tmp")
        tmp.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")
        tmp.replace(p)


class CachedLLM:
    """Wraps any LLM client. The key covers model, prompts, schema, seed and temperature.

    Because the seed is part of the key, each run (which has its own seed) gets its own
    responses; replaying the same run returns exactly the same negotiation.
    """

    def __init__(self, inner, cache: ResponseCache):
        self.inner = inner
        self.cache = cache
        self.model = inner.model
        self.hits = 0
        self.misses = 0

    def generate(self, system, messages, schema, *, seed=None, temperature=None) -> LLMResponse:
        key = cache_key(model=self.model, system=system, messages=messages, schema=schema, seed=seed,
                        temperature=temperature)
        hit = self.cache.get(key)
        if hit is not None:
            self.hits += 1
            return LLMResponse(**{**hit, "meta": {**hit.get("meta", {}), "cached": True}})
        self.misses += 1
        resp = self.inner.generate(system, messages, schema, seed=seed, temperature=temperature)
        self.cache.put(key, {"text": resp.text, "model": resp.model, "input_tokens": resp.input_tokens,
                             "output_tokens": resp.output_tokens, "usd": resp.usd, "ms": resp.ms, "meta": resp.meta})
        return resp
