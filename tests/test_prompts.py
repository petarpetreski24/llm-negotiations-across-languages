import itertools

import pytest

from negmt.cells import build_run_spec
from negmt.llm.fake import FakeNegotiator
from negmt.orchestrator import run_negotiation
from negmt.prompts import TemplatePromptBuilder
from negmt.schemas import AgentSpec
from negmt.translation.fake import TaggingTranslator
from tests.conftest import ROOT


@pytest.fixture(scope="module")
def builder():
    return TemplatePromptBuilder(ROOT / "configs")


@pytest.mark.parametrize("role, persona, dialog", list(itertools.product(["aldoria", "veskaria"], ["hawk", "dove"], ["en", "ru"])))
def test_english_system_prompt(builder, scenario, role, persona, dialog):
    spec = AgentSpec(role=role, persona=persona, instr_lang="en", dialog_lang=dialog, model="x")
    text = builder.system_prompt(spec, scenario, max_rounds=10)
    other = "veskaria" if role == "aldoria" else "aldoria"

    assert scenario.roles[role].name["en"] in text
    assert "walk-away value of 45 points" in text
    assert "at most 10 messages" in text
    assert f"written in {'English' if dialog == 'en' else 'Russian'}" in text
    for issue in scenario.issues:
        assert issue.label["en"] in text
        for k, opt in enumerate(issue.options):
            assert f"option {k}: {opt['en']} — {issue.points[role][k]} points" in text
    # the other side's score table must not leak
    leaked = [f"option {k}: {o['en']} — {issue.points[other][k]} points"
              for issue in scenario.issues for k, o in enumerate(issue.options)
              if issue.points[other][k] != issue.points[role][k]]
    assert not any(line in text for line in leaked)
    assert "translat" not in text.lower()  # agents are never told about translation
    assert ("hard-line" in text) == (persona == "hawk")


def test_turn_messages(builder):
    spec = AgentSpec(role="aldoria", persona="dove", instr_lang="en", dialog_lang="en", model="x")
    opening = builder.turn_message(spec, 1, 10, None, [])
    assert "You open the talks" in opening and "<<<" not in opening
    reply = builder.turn_message(spec, 3, 10, "We propose X.", ["Doc: A. text"])
    assert "Message 3 of 10" in reply and "<<<We propose X.>>>" in reply and "[1] Doc: A. text" in reply
    assert "could not be used: bad" in builder.retry_message(spec, "bad")


def test_full_run_with_real_templates(builder, scenario, cells):
    variants, pairings = cells
    v = next(v for v in variants if v.name == "C1")
    spec = build_run_spec(experiment="t", variant=v, pairing_name="P2", pairing=pairings["P2"], rep=0,
                          model="fake", mt_systems={"MT1": "m1", "MT2": "m2"})
    llms = {r: FakeNegotiator(scenario.issue_ids, "en", scenario.nash_point().deal) for r in scenario.roles}
    res = run_negotiation(spec, scenario, llms, builder, {"m1": TaggingTranslator("m1"), "m2": TaggingTranslator("m2")})
    assert res.outcome.status == "deal"
