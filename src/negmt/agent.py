"""A negotiating agent: builds its context, calls its model, validates the reply, retries."""

from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass, field
from typing import Optional, Protocol

from pydantic import ValidationError

from negmt import langcheck
from negmt.llm.base import LLMClient
from negmt.prompts import PromptBuilder
from negmt.scenario import Scenario
from negmt.schemas import AgentOutput, AgentSpec, Usage, agent_output_json_schema


class Retriever(Protocol):
    def retrieve(self, query: str, k: int = 3) -> list[tuple[str, str]]: ...  # [(chunk_id, text)]


class AgentFailure(RuntimeError):
    pass


@dataclass
class AgentTurn:
    output: AgentOutput
    raw: str
    retries: int
    usage: Usage
    ms: float
    lang_detected: str
    prompt_sha: str
    retrieved: list[str] = field(default_factory=list)


class Agent:
    def __init__(
        self,
        spec: AgentSpec,
        scenario: Scenario,
        llm: LLMClient,
        prompts: PromptBuilder,
        max_rounds: int,
        retriever: Optional[Retriever] = None,
        max_retries: int = 2,
        seed: Optional[int] = None,
        temperature: Optional[float] = None,
    ):
        self.spec = spec
        self.scenario = scenario
        self.llm = llm
        self.prompts = prompts
        self.max_rounds = max_rounds
        self.retriever = retriever
        self.max_retries = max_retries
        self.seed = seed
        self.temperature = temperature
        self.system = prompts.system_prompt(spec, scenario, max_rounds)
        self.schema = agent_output_json_schema(scenario)
        self.history: list[dict[str, str]] = []  # alternating user / assistant, append-only
        self.last_plan = ""

    def act(self, round_no: int, incoming: Optional[str]) -> AgentTurn:
        retrieved: list[tuple[str, str]] = []
        if self.retriever is not None:
            query = " ".join(x for x in (incoming, self.last_plan) if x)
            retrieved = self.retriever.retrieve(query, k=3) if query else []
        turn_msg = self.prompts.turn_message(
            self.spec, round_no, self.max_rounds, incoming, [text for _, text in retrieved]
        )

        messages = self.history + [{"role": "user", "content": turn_msg}]
        usage = Usage()
        t0 = time.perf_counter()
        last_error = ""
        for attempt in range(self.max_retries + 1):
            resp = self.llm.generate(self.system, messages, self.schema, seed=self.seed, temperature=self.temperature)
            usage.input_tokens += resp.input_tokens
            usage.output_tokens += resp.output_tokens
            usage.usd += resp.usd
            try:
                out = self.validate(resp.text)
            except ValueError as err:
                last_error = str(err)
                messages = messages + [
                    {"role": "assistant", "content": resp.text},
                    {"role": "user", "content": self.prompts.retry_message(self.spec, last_error)},
                ]
                continue
            # keep only the clean exchange in history
            self.history += [{"role": "user", "content": turn_msg}, {"role": "assistant", "content": resp.text}]
            self.last_plan = out.plan
            return AgentTurn(
                output=out,
                raw=resp.text,
                retries=attempt,
                usage=usage,
                ms=(time.perf_counter() - t0) * 1000,
                lang_detected=langcheck.detect(out.message),
                prompt_sha=_sha(self.system, messages),
                retrieved=[cid for cid, _ in retrieved],
            )
        raise AgentFailure(f"{self.spec.role}: no valid reply after {self.max_retries + 1} attempts: {last_error}")

    def validate(self, raw: str) -> AgentOutput:
        try:
            data = json.loads(raw)
        except json.JSONDecodeError as err:
            raise ValueError(f"not valid JSON ({err.msg})") from err
        try:
            out = AgentOutput.model_validate(data)
        except ValidationError as err:
            raise ValueError(f"schema error: {err.errors()[0]['msg']} at {err.errors()[0]['loc']}") from err

        self.scenario.validate_deal(out.my_offer)
        if out.decision == "accept":
            if out.accepted_terms is None:
                raise ValueError("decision is accept but accepted_terms is missing")
            self.scenario.validate_deal(out.accepted_terms)
        elif out.accepted_terms is not None:
            raise ValueError("accepted_terms must be null unless decision is accept")

        understood: dict[str, Optional[int]] = {}
        for issue in self.scenario.issues:
            k = out.their_offer_as_understood.get(issue.id)
            if k is not None and not 0 <= k < issue.n_options:
                raise ValueError(f"their_offer_as_understood.{issue.id}: invalid option {k}")
            understood[issue.id] = k
        if set(out.their_offer_as_understood) - set(self.scenario.issue_ids):
            raise ValueError("their_offer_as_understood has unknown issues")
        out.their_offer_as_understood = understood

        if not out.message.strip():
            raise ValueError("message is empty")
        if not langcheck.matches(out.message, self.spec.dialog_lang):
            raise ValueError(f"message must be written in {self.spec.dialog_lang}, got {langcheck.detect(out.message)}")
        return out


def _sha(system: str, messages: list[dict[str, str]]) -> str:
    blob = json.dumps({"system": system, "messages": messages}, ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(blob.encode()).hexdigest()[:16]
