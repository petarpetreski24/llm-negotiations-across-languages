"""LLM client interface shared by the real adapters (step 4) and the fakes."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional, Protocol


@dataclass
class LLMResponse:
    text: str  # raw model output, expected to be JSON
    model: str
    input_tokens: int = 0
    output_tokens: int = 0
    usd: float = 0.0
    ms: float = 0.0
    meta: dict[str, Any] = field(default_factory=dict)


class LLMClient(Protocol):
    model: str

    def generate(
        self,
        system: str,
        messages: list[dict[str, str]],
        schema: dict[str, Any],
        *,
        seed: Optional[int] = None,
        temperature: Optional[float] = None,
    ) -> LLMResponse: ...
