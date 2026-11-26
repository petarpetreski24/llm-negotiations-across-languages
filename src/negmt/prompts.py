"""Prompt building.

`PromptBuilder` is the interface the agent uses. `PlainPromptBuilder` is a minimal
English placeholder for tests and step 2; step 3 adds the Jinja templates in
configs/prompts (one per instruction language) with the real personas and rules.

The other side's latest message is wrapped in <<< >>> so it is clearly delimited.
"""

from __future__ import annotations

from typing import Protocol

from negmt.scenario import Scenario
from negmt.schemas import AgentSpec


class PromptBuilder(Protocol):
    def system_prompt(self, spec: AgentSpec, scenario: Scenario, max_rounds: int) -> str: ...

    def turn_message(
        self, spec: AgentSpec, round_no: int, max_rounds: int, incoming: str | None, excerpts: list[str]
    ) -> str: ...

    def retry_message(self, spec: AgentSpec, error: str) -> str: ...


class PlainPromptBuilder:
    def system_prompt(self, spec: AgentSpec, scenario: Scenario, max_rounds: int) -> str:
        role = scenario.roles[spec.role]
        lines = [
            f"You represent {role.name['en']} in a treaty negotiation. Persona: {spec.persona}.",
            f"You have {max_rounds} turns. Write `message` in {spec.dialog_lang}.",
            f"Your walk-away value is {role.batna} points. Your points per option:",
        ]
        for issue in scenario.issues:
            pts = ", ".join(f"{k}={issue.options[k]['en']}:{p}" for k, p in enumerate(issue.points[spec.role]))
            lines.append(f"- {issue.id}: {pts}")
        lines.append("Reply with JSON only.")
        return "\n".join(lines)

    def turn_message(self, spec, round_no, max_rounds, incoming, excerpts) -> str:
        parts = [f"Round {round_no} of {max_rounds}."]
        if excerpts:
            parts.append("Briefing excerpts:\n" + "\n".join(f"- {e}" for e in excerpts))
        if incoming is None:
            parts.append("You open the negotiation.")
        else:
            parts.append(f"The other delegation says: <<<{incoming}>>>")
        return "\n\n".join(parts)

    def retry_message(self, spec, error: str) -> str:
        return f"Your last reply was invalid: {error}. Reply again with valid JSON only."
