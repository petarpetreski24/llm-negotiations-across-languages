"""Prompt building.

`PromptBuilder` is the interface the agent uses. `PlainPromptBuilder` is a minimal
English placeholder for tests and step 2; step 3 adds the Jinja templates in
configs/prompts (one per instruction language) with the real personas and rules.

The other side's latest message is wrapped in <<< >>> so it is clearly delimited.
"""

from __future__ import annotations

from pathlib import Path
from typing import Protocol

from negmt.scenario import Scenario
from negmt.schemas import AgentSpec


class PromptBuilder(Protocol):
    def system_prompt(self, spec: AgentSpec, scenario: Scenario, max_rounds: int) -> str: ...

    def turn_message(
        self, spec: AgentSpec, round_no: int, max_rounds: int, incoming: str | None, excerpts: list[str]
    ) -> str: ...

    def retry_message(self, spec: AgentSpec, error: str) -> str: ...


class TemplatePromptBuilder:
    """Renders prompts from configs/ in the agent's instruction language.

    Layers (as in the CIIT framework): role situation + persona archetype + score table + rules.
    Files: prompts/{system,turn,retry}.<lang>.j2, personas/<persona>.<lang>.md,
    roles/<role>.<lang>.md, prompts/languages.yaml.
    """

    def __init__(self, config_root: str | Path):
        import jinja2
        import yaml

        self.root = Path(config_root)
        self.env = jinja2.Environment(
            loader=jinja2.FileSystemLoader(str(self.root / "prompts")),
            undefined=jinja2.StrictUndefined,
            keep_trailing_newline=False,
            trim_blocks=True,
        )
        self.language_names = yaml.safe_load((self.root / "prompts" / "languages.yaml").read_text(encoding="utf-8"))

    def _text(self, *parts: str) -> str:
        return (self.root.joinpath(*parts)).read_text(encoding="utf-8").strip()

    def system_prompt(self, spec: AgentSpec, scenario: Scenario, max_rounds: int) -> str:
        lang = spec.instr_lang
        issues = [
            {
                "label": issue.label[lang],
                "options": [
                    {"id": k, "label": opt[lang], "points": issue.points[spec.role][k]}
                    for k, opt in enumerate(issue.options)
                ],
            }
            for issue in scenario.issues
        ]
        role = scenario.roles[spec.role]
        return self.env.get_template(f"system.{lang}.j2").render(
            country=role.name[lang],
            situation=self._text("roles", f"{spec.role}.{lang}.md"),
            persona=self._text("personas", f"{spec.persona}.{lang}.md"),
            issues=issues,
            batna=int(role.batna) if float(role.batna).is_integer() else role.batna,
            max_rounds=max_rounds,
            dialog_language=self.language_names[lang][spec.dialog_lang],
        ).strip()

    def turn_message(self, spec, round_no, max_rounds, incoming, excerpts) -> str:
        return self.env.get_template(f"turn.{spec.instr_lang}.j2").render(
            round_no=round_no, max_rounds=max_rounds, incoming=incoming, excerpts=excerpts
        ).strip()

    def retry_message(self, spec, error: str) -> str:
        return self.env.get_template(f"retry.{spec.instr_lang}.j2").render(error=error).strip()


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
