"""Round-trip translator: src -> pivot -> src with the same inner system (control cells C1/C2)."""

from __future__ import annotations

from negmt.translation.base import TranslationResult, Translator


class RoundTripTranslator:
    def __init__(self, inner: Translator, pivot: str):
        self.inner = inner
        self.pivot = pivot
        self.name = f"roundtrip({inner.name})"

    def translate(self, text: str, src: str, tgt: str) -> TranslationResult:
        if src != tgt:
            raise ValueError("round trip expects the same source and target language")
        there = self.inner.translate(text, src, self.pivot)
        back = self.inner.translate(there.text, self.pivot, src)
        return TranslationResult(
            text=back.text, system=self.name, ms=there.ms + back.ms, meta={"pivot_text": there.text}
        )
