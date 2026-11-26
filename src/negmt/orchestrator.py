"""Run one negotiation end to end and produce its log records."""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping, Optional

from negmt.agent import Agent, AgentFailure, Retriever
from negmt.channel import Channel
from negmt.llm.base import LLMClient
from negmt.logio import log_path, write_run
from negmt.prompts import PromptBuilder
from negmt.protocol import Protocol, State
from negmt.scenario import Scenario
from negmt.schemas import Outcome, RunSpec, TurnRecord
from negmt.translation.base import Translator


@dataclass
class RunResult:
    spec: RunSpec
    turns: list[TurnRecord]
    outcome: Outcome
    path: Optional[Path] = None


def run_negotiation(
    spec: RunSpec,
    scenario: Scenario,
    llms: Mapping[str, LLMClient],
    prompts: PromptBuilder,
    translators: Mapping[str, Translator] | None = None,
    retrievers: Mapping[str, Retriever] | None = None,
    log_dir: str | Path | None = None,
) -> RunResult:
    roles = tuple(scenario.roles)
    channel = Channel(spec.channel, translators)
    agents = {
        r: Agent(
            spec.agents[r], scenario, llms[r], prompts, spec.max_rounds,
            retriever=(retrievers or {}).get(r), seed=spec.seed, temperature=spec.temperature,
        )
        for r in roles
    }
    proto = Protocol(roles, spec.first_mover, spec.max_rounds)
    inbox: dict[str, Optional[str]] = {r: None for r in roles}  # latest delivered message per receiver
    last_offer: dict[str, Optional[dict[str, int]]] = {r: None for r in roles}
    records: list[TurnRecord] = []

    while proto.needs_turn():
        speaker = proto.next_speaker
        other = proto.other(speaker)
        agent = agents[speaker]
        try:
            turn = agent.act((proto.turns + 2) // 2, inbox[speaker])  # round of the turn about to happen
        except AgentFailure as err:
            proto.fail(str(err))
            break
        out = turn.output
        comprehension = _comprehension(out.their_offer_as_understood, last_offer[other])
        last_offer[speaker] = out.my_offer
        state = proto.step(speaker, out)

        chan = None
        if state not in (State.DEAL, State.ILLUSORY, State.WALK_AWAY, State.TIMEOUT):
            chan = channel.deliver(out.message, agent.spec.dialog_lang, agents[other].spec.dialog_lang)
            inbox[other] = chan.delivered_text

        records.append(
            TurnRecord(
                run_id=spec.run_id, turn=proto.turns, round=proto.rounds, speaker=speaker,
                model=agent.spec.model, instr_lang=agent.spec.instr_lang, dialog_lang=agent.spec.dialog_lang,
                retrieved=turn.retrieved, prompt_sha=turn.prompt_sha, raw=turn.raw, output=out,
                lang_detected=turn.lang_detected, retries=turn.retries, usage=turn.usage, ms=turn.ms,
                comprehension=comprehension, channel=chan,
            )
        )

    outcome = score_outcome(spec.run_id, proto, scenario)
    result = RunResult(spec, records, outcome)
    if log_dir is not None:
        result.path = write_run(log_path(log_dir, spec.run_id), spec, records, outcome, meta={"git": _git_rev()})
    return result


def _comprehension(understood: Mapping[str, Optional[int]], actual: Optional[Mapping[str, int]]) -> Optional[dict[str, int]]:
    if actual is None:
        return None
    correct = sum(1 for i, k in actual.items() if understood.get(i) == k)
    missing = sum(1 for i in actual if understood.get(i) is None)
    return {"correct": correct, "wrong": len(actual) - correct - missing, "missing": missing}


def score_outcome(run_id: str, proto: Protocol, scenario: Scenario) -> Outcome:
    batna = {r: scenario.roles[r].batna for r in scenario.roles}
    status = proto.state.value if proto.state != State.OPEN else "timeout"
    base = dict(run_id=run_id, status=status, turns=proto.turns, rounds=proto.rounds, terms=dict(proto.terms), error=proto.error)

    if proto.state == State.DEAL:
        terms = next(t for t in proto.terms.values() if t is not None)
        util = scenario.utilities(terms)
        product = 1.0
        for r in util:
            product *= util[r] - batna[r]
        return Outcome(**base, utility=util, joint=sum(util.values()),
                       pareto_distance=scenario.pareto_distance(terms), nash_product=product)

    believed = None
    if proto.state == State.ILLUSORY:
        believed = {r: float(scenario.utility(r, t)) for r, t in proto.terms.items() if t is not None}
    return Outcome(**base, utility=dict(batna), believed_utility=believed, joint=sum(batna.values()))


def _git_rev() -> str:
    try:
        return subprocess.run(["git", "rev-parse", "--short", "HEAD"], capture_output=True, text=True,
                              timeout=5).stdout.strip()
    except Exception:
        return "unknown"
