"""Fake LLMs for free, deterministic tests.

FakeNegotiator writes offers into its message as '#' followed by one digit per issue,
e.g. 'Our proposal: #040432'. A fake on the other side parses that from the delivered
text, so translation (or corruption) of the message really changes what it understands.
"""

from __future__ import annotations

import json
import re
from typing import Any, Optional

from negmt.llm.base import LLMResponse

_OFFER = re.compile(r"#(\d+)")
_ACCEPT_WORDS = ("accept", "принимаем")

PHRASES = {
    "en": {"propose": "Our proposal: #{d}", "accept": "We accept: #{d}", "leave": "We are leaving the talks."},
    "ru": {"propose": "Наше предложение: #{d}", "accept": "Мы принимаем: #{d}", "leave": "Мы покидаем переговоры."},
}


def encode(deal: dict[str, int], issue_ids: list[str]) -> str:
    return "".join(str(deal[i]) for i in issue_ids)


def decode(text: str, issue_ids: list[str]) -> Optional[dict[str, int]]:
    found = _OFFER.findall(text)
    if not found or len(found[-1]) != len(issue_ids):
        return None
    return {i: int(c) for i, c in zip(issue_ids, found[-1])}


class FakeNegotiator:
    """Deterministic negotiator.

    Proposes `target` until `accept_from_turn`; after that it accepts whatever it understood.
    When the other side's message says it accepts, it confirms with its own last offer.
    """

    def __init__(
        self,
        issue_ids: list[str],
        dialog_lang: str,
        target: dict[str, int],
        accept_from_turn: int = 1,
        walk_away_at: Optional[int] = None,
        never_accept: bool = False,
        model: str = "fake-negotiator",
    ):
        self.issue_ids = issue_ids
        self.lang = dialog_lang
        self.target = target
        self.accept_from_turn = accept_from_turn
        self.walk_away_at = walk_away_at
        self.never_accept = never_accept
        self.model = model
        self.own_turns = 0

    def generate(self, system, messages, schema, *, seed=None, temperature=None) -> LLMResponse:
        self.own_turns += 1
        incoming = messages[-1]["content"] if messages else ""
        heard = self._extract_incoming(incoming)
        understood = decode(heard, self.issue_ids) if heard else None
        p = PHRASES[self.lang]
        mine = encode(self.target, self.issue_ids)

        if self.walk_away_at is not None and self.own_turns >= self.walk_away_at:
            out = self._out(p["leave"], self.target, understood, "walk_away", None)
        elif heard and any(w in heard.lower() for w in _ACCEPT_WORDS) and not self.never_accept:
            out = self._out(p["accept"].format(d=mine), self.target, understood, "accept", self.target)
        elif understood and not self.never_accept and self.own_turns >= self.accept_from_turn:
            out = self._out(p["accept"].format(d=encode(understood, self.issue_ids)), self.target,
                            understood, "accept", understood)
        else:
            out = self._out(p["propose"].format(d=mine), self.target, understood, "continue", None)
        return LLMResponse(text=json.dumps(out, ensure_ascii=False), model=self.model,
                           input_tokens=sum(len(m["content"]) for m in messages) // 4, output_tokens=50)

    @staticmethod
    def _extract_incoming(turn_message: str) -> str:
        marker = "<<<"
        if marker in turn_message:
            return turn_message.split(marker, 1)[1].split(">>>", 1)[0]
        return ""

    def _out(self, message, offer, understood, decision, accepted) -> dict[str, Any]:
        return {
            "message": message,
            "my_offer": dict(offer),
            "their_offer_as_understood": dict(understood) if understood else {i: None for i in self.issue_ids},
            "decision": decision,
            "accepted_terms": dict(accepted) if accepted else None,
            "plan": "fake plan",
        }


class ScriptedLLM:
    """Returns pre-written raw responses in order (for validation and retry tests)."""

    def __init__(self, responses: list[str], model: str = "scripted"):
        self.responses = list(responses)
        self.model = model
        self.calls: list[list[dict[str, str]]] = []

    def generate(self, system, messages, schema, *, seed=None, temperature=None) -> LLMResponse:
        self.calls.append([dict(m) for m in messages])
        if not self.responses:
            raise RuntimeError("ScriptedLLM ran out of responses")
        return LLMResponse(text=self.responses.pop(0), model=self.model)
