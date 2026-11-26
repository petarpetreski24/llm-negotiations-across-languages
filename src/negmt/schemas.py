"""Data models shared by the engine, the logs and the analysis."""

from __future__ import annotations

import hashlib
from typing import Any, Literal, Optional

from pydantic import BaseModel, Field

from negmt.scenario import Scenario

Lang = Literal["en", "ru"]
Decision = Literal["continue", "accept", "walk_away"]
Status = Literal["deal", "illusory", "walk_away", "timeout", "error"]


class AgentSpec(BaseModel):
    role: str
    persona: str
    instr_lang: Lang
    dialog_lang: Lang
    model: str


class ChannelSpec(BaseModel):
    mode: Literal["none", "mt", "roundtrip"]
    system: Optional[str] = None  # concrete MT system name, e.g. "nllb-200-3.3b"
    pivot: Optional[Lang] = None


class RunSpec(BaseModel):
    run_id: str
    experiment: str
    cell: str  # cell variant, e.g. "B2" or "B2-swap"
    persona_pairing: str
    rep: int
    seed: int
    first_mover: str
    max_rounds: int = 10  # turns per side
    temperature: Optional[float] = 0.7
    agents: dict[str, AgentSpec]  # role -> spec
    channel: ChannelSpec

    @staticmethod
    def seed_for(run_id: str) -> int:
        return int(hashlib.sha256(run_id.encode()).hexdigest()[:8], 16)


class AgentOutput(BaseModel):
    """What an agent returns every turn. Only `message` is shown to the other side."""

    message: str
    my_offer: dict[str, int]
    their_offer_as_understood: dict[str, Optional[int]] = Field(default_factory=dict)
    decision: Decision
    accepted_terms: Optional[dict[str, int]] = None
    plan: str = ""


class ChannelRecord(BaseModel):
    mode: str
    system: Optional[str]
    src: str
    tgt: str
    source_text: str
    delivered_text: str
    pivot_text: Optional[str] = None
    ms: float = 0.0


class Usage(BaseModel):
    input_tokens: int = 0
    output_tokens: int = 0
    usd: float = 0.0


class TurnRecord(BaseModel):
    type: Literal["turn"] = "turn"
    run_id: str
    turn: int
    round: int
    speaker: str
    model: str
    instr_lang: str
    dialog_lang: str
    retrieved: list[str] = Field(default_factory=list)
    prompt_sha: str
    raw: str
    output: AgentOutput
    lang_detected: str
    retries: int
    usage: Usage
    ms: float
    comprehension: Optional[dict[str, int]] = None  # correct / wrong / missing vs the other side's true offer
    channel: Optional[ChannelRecord] = None  # None when the message was not delivered (negotiation ended)


class Outcome(BaseModel):
    type: Literal["outcome"] = "outcome"
    run_id: str
    status: Status
    turns: int
    rounds: int
    terms: dict[str, Optional[dict[str, int]]]  # role -> terms that role believes were agreed
    utility: dict[str, float]  # realised utility (BATNA unless a valid deal)
    believed_utility: Optional[dict[str, float]] = None  # for illusory agreements
    joint: float
    pareto_distance: Optional[float] = None
    nash_product: Optional[float] = None
    error: Optional[str] = None


def agent_output_json_schema(scenario: Scenario) -> dict[str, Any]:
    """JSON schema for structured outputs, with option indices constrained per issue."""
    offer = {
        "type": "object",
        "properties": {i.id: {"type": "integer", "enum": list(range(i.n_options))} for i in scenario.issues},
        "required": scenario.issue_ids,
        "additionalProperties": False,
    }
    understood = {
        "type": "object",
        "properties": {
            i.id: {"anyOf": [{"type": "integer", "enum": list(range(i.n_options))}, {"type": "null"}]}
            for i in scenario.issues
        },
        "required": scenario.issue_ids,
        "additionalProperties": False,
    }
    return {
        "type": "object",
        "properties": {
            "message": {"type": "string"},
            "my_offer": offer,
            "their_offer_as_understood": understood,
            "decision": {"type": "string", "enum": ["continue", "accept", "walk_away"]},
            "accepted_terms": {"anyOf": [offer, {"type": "null"}]},
            "plan": {"type": "string"},
        },
        "required": ["message", "my_offer", "their_offer_as_understood", "decision", "accepted_terms", "plan"],
        "additionalProperties": False,
    }
