"""Fake translators for tests: they tag text instead of translating it, and can corrupt offers."""

from __future__ import annotations

import re

from negmt.translation.base import TranslationResult

_OFFER = re.compile(r"#(\d+)")


class TaggingTranslator:
    """Prefixes '[name src->tgt]' so tests can see exactly where translation happened."""

    def __init__(self, name: str = "fake-mt"):
        self.name = name
        self.calls: list[tuple[str, str, str]] = []

    def translate(self, text: str, src: str, tgt: str) -> TranslationResult:
        self.calls.append((text, src, tgt))
        return TranslationResult(text=f"[{self.name} {src}->{tgt}] {text}", system=self.name)


class CorruptingTranslator(TaggingTranslator):
    """Like TaggingTranslator, but shifts the first option digit of any '#ddd' offer: a semantic error."""

    def translate(self, text: str, src: str, tgt: str) -> TranslationResult:
        def corrupt(m: re.Match) -> str:
            digits = m.group(1)
            return "#" + str((int(digits[0]) + 1) % 5) + digits[1:]

        res = super().translate(text, src, tgt)
        res.text = _OFFER.sub(corrupt, res.text, count=1)
        return res
