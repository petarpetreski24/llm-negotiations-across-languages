"""A negotiating agent: builds its context, calls its model, validates the reply, retries."""

from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass, field
from typing import Optional, Protocol

from pydantic import ValidationError

from negmt import langcheck
from negmt.errors import InvalidReply
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
    turn_message: str = ""
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
            except InvalidReply as err:
                last_error = str(err)
                messages = messages + [
                    {"role": "assistant", "content": resp.text},
                    {"role": "user", "content": self.prompts.retry_message(self.spec, err)},
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
                turn_message=turn_msg,
                retrieved=[cid for cid, _ in retrieved],
            )
        raise AgentFailure(f"{self.spec.role}: no valid reply after {self.max_retries + 1} attempts: {last_error}")

    def validate(self, raw: str) -> AgentOutput:
        """Parse and check one reply; raises InvalidReply (a ValueError) with a code."""
        try:
            data = json.loads(raw)
        except json.JSONDecodeError as err:
            raise InvalidReply("not_json") from err
        try:
            out = AgentOutput.model_validate(data)
        except ValidationError as err:
            loc = err.errors()[0]["loc"]
            raise InvalidReply("schema", field=".".join(str(x) for x in loc) or "reply") from err

        self._check_deal(out.my_offer, "my_offer")
        if out.decision == "accept":
            if out.accepted_terms is None:
                raise InvalidReply("accept_without_terms")
            self._check_deal(out.accepted_terms, "accepted_terms")
        elif out.accepted_terms is not None:
            raise InvalidReply("terms_without_accept")

        if set(out.their_offer_as_understood) - set(self.scenario.issue_ids):
            raise InvalidReply("unknown_issue")
        understood: dict[str, Optional[int]] = {}
        for issue in self.scenario.issues:
            k = out.their_offer_as_understood.get(issue.id)
            if k is not None and not 0 <= k < issue.n_options:
                raise InvalidReply("invalid_option", issue=issue.id, option=k)
            understood[issue.id] = k
        out.their_offer_as_understood = understood

        if not out.message.strip():
            raise InvalidReply("empty_message")
        if not langcheck.matches(out.message, self.spec.dialog_lang):
            raise InvalidReply("wrong_language", expected=self.spec.dialog_lang, detected=langcheck.detect(out.message))
        return out

    def _check_deal(self, deal: dict[str, int], field_name: str) -> None:
        try:
            self.scenario.validate_deal(deal)
        except ValueError as err:
            raise InvalidReply("invalid_offer", field=field_name) from err


def _sha(system: str, messages: list[dict[str, str]]) -> str:
    blob = json.dumps({"system": system, "messages": messages}, ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(blob.encode()).hexdigest()[:16]
