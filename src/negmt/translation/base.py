"""Translator interface."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol


@dataclass
class TranslationResult:
    text: str
    system: str
    ms: float = 0.0
    meta: dict[str, Any] = field(default_factory=dict)


class Translator(Protocol):
    name: str

    def translate(self, text: str, src: str, tgt: str) -> TranslationResult: ...
