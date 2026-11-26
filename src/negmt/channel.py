"""Translation channel: decides per message whether and how it is translated, and records it."""

from __future__ import annotations

import time
from typing import Mapping

from negmt.schemas import ChannelRecord, ChannelSpec
from negmt.translation.base import Translator
from negmt.translation.roundtrip import RoundTripTranslator


class ChannelError(ValueError):
    pass


class Channel:
    def __init__(self, spec: ChannelSpec, translators: Mapping[str, Translator] | None = None):
        self.spec = spec
        translators = translators or {}
        self._translator: Translator | None = None
        if spec.mode in ("mt", "roundtrip"):
            if spec.system not in translators:
                raise ChannelError(f"no translator registered for system {spec.system!r}")
            inner = translators[spec.system]
            if spec.mode == "roundtrip":
                if not spec.pivot:
                    raise ChannelError("round trip needs a pivot language")
                self._translator = RoundTripTranslator(inner, spec.pivot)
            else:
                self._translator = inner

    def deliver(self, text: str, src: str, tgt: str) -> ChannelRecord:
        mode = self.spec.mode
        if mode == "none":
            if src != tgt:
                raise ChannelError(f"no channel but sender writes {src} and receiver reads {tgt}")
            return ChannelRecord(mode=mode, system=None, src=src, tgt=tgt, source_text=text, delivered_text=text)
        if mode == "mt" and src == tgt:
            raise ChannelError("MT channel between agents with the same dialogue language")
        if mode == "roundtrip" and src != tgt:
            raise ChannelError("round-trip channel between agents with different dialogue languages")

        t0 = time.perf_counter()
        res = self._translator.translate(text, src, tgt)
        ms = res.ms or (time.perf_counter() - t0) * 1000
        return ChannelRecord(
            mode=mode,
            system=res.system,
            src=src,
            tgt=tgt,
            source_text=text,
            delivered_text=res.text,
            pivot_text=res.meta.get("pivot_text"),
            ms=ms,
        )
