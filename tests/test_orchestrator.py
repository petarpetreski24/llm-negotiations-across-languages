"""End-to-end negotiations with fake models and fake translators, for every cell."""

import pytest

from negmt.cells import build_run_spec
from negmt.llm.fake import FakeNegotiator, ScriptedLLM
from negmt.logio import read_run
from negmt.orchestrator import run_negotiation
from negmt.prompts import PlainPromptBuilder
from negmt.translation.fake import CorruptingTranslator, TaggingTranslator

MT = {"MT1": "fake-nllb", "MT2": "fake-tg"}


def fakes(scenario, spec, **kw):
    target = scenario.nash_point().deal
    return {
        r: FakeNegotiator(scenario.issue_ids, spec.agents[r].dialog_lang, target, **kw.get(r, {}))
        for r in scenario.roles
    }


def spec_for(cells, name, pairing="P2", rep=0, max_rounds=10):
    variants, pairings = cells
    v = next(v for v in variants if v.name == name)
    return build_run_spec(experiment="test", variant=v, pairing_name=pairing, pairing=pairings[pairing],
                          rep=rep, model="fake", mt_systems=MT, max_rounds=max_rounds)


def translators():
    return {"fake-nllb": TaggingTranslator("fake-nllb"), "fake-tg": TaggingTranslator("fake-tg")}


ALL = ["A1", "A2", "A3", "A4", "B1", "B1-swap", "B2", "B2-swap", "B3", "B3-swap", "C1", "C2"]


@pytest.mark.parametrize("cell", ALL)
@pytest.mark.parametrize("pairing", ["P1", "P2"])
def test_every_cell_reaches_a_deal_and_logs(scenario, cells, cell, pairing, tmp_path):
    spec = spec_for(cells, cell, pairing)
    res = run_negotiation(spec, scenario, fakes(scenario, spec), PlainPromptBuilder(), translators(), log_dir=tmp_path)

    assert res.outcome.status == "deal"
    assert res.outcome.utility == {"aldoria": 68, "veskaria": 72}
    assert res.outcome.pareto_distance == 0
    assert [t.speaker for t in res.turns] == ["aldoria", "veskaria", "aldoria"]

    delivered = [t.channel for t in res.turns if t.channel is not None]
    mode = spec.channel.mode
    for rec in delivered:
        assert rec.mode == mode
        if mode == "none":
            assert rec.delivered_text == rec.source_text
        elif mode == "mt":
            assert rec.src != rec.tgt and rec.delivered_text.startswith(f"[{spec.channel.system} {rec.src}->{rec.tgt}]")
        else:
            assert rec.pivot_text is not None and rec.src == rec.tgt == "en"
    for t in res.turns:
        assert t.lang_detected == t.dialog_lang

    head, turns, outcome = read_run(res.path)
    assert head["run_id"] == spec.run_id and len(turns) == 3 and outcome.status == "deal"


def test_comprehension_is_recorded(scenario, cells):
    spec = spec_for(cells, "A1")
    res = run_negotiation(spec, scenario, fakes(scenario, spec), PlainPromptBuilder(), translators())
    assert res.turns[0].comprehension is None  # nothing to understand yet
    assert res.turns[1].comprehension == {"correct": 6, "wrong": 0, "missing": 0}


def test_corrupted_translation_gives_illusory_agreement(scenario, cells):
    spec = spec_for(cells, "B2")
    trans = {"fake-nllb": CorruptingTranslator("fake-nllb"), "fake-tg": TaggingTranslator("fake-tg")}
    res = run_negotiation(spec, scenario, fakes(scenario, spec), PlainPromptBuilder(), trans)
    assert res.outcome.status == "illusory"
    assert res.outcome.terms["aldoria"] != res.outcome.terms["veskaria"]
    assert res.outcome.utility == {"aldoria": 45, "veskaria": 45}  # no valid deal: BATNA
    assert res.outcome.believed_utility is not None
    assert res.turns[1].comprehension["wrong"] == 1  # misread the corrupted issue


def test_timeout_when_nobody_accepts(scenario, cells):
    spec = spec_for(cells, "A2", max_rounds=3)
    llms = fakes(scenario, spec, aldoria={"never_accept": True}, veskaria={"never_accept": True})
    res = run_negotiation(spec, scenario, llms, PlainPromptBuilder(), translators())
    assert res.outcome.status == "timeout" and res.outcome.turns == 6
    assert res.outcome.utility == {"aldoria": 45, "veskaria": 45}


def test_walk_away(scenario, cells):
    spec = spec_for(cells, "A1")
    llms = fakes(scenario, spec, aldoria={"walk_away_at": 1})
    res = run_negotiation(spec, scenario, llms, PlainPromptBuilder(), translators())
    assert res.outcome.status == "walk_away" and res.outcome.turns == 1


def test_agent_failure_ends_run_as_error(scenario, cells):
    spec = spec_for(cells, "A1")
    llms = {"aldoria": ScriptedLLM(["bad", "bad", "bad"]), "veskaria": ScriptedLLM([])}
    res = run_negotiation(spec, scenario, llms, PlainPromptBuilder(), translators())
    assert res.outcome.status == "error" and "aldoria" in res.outcome.error


def test_logs_are_self_contained(scenario, cells, tmp_path):
    spec = spec_for(cells, "A1")
    res = run_negotiation(spec, scenario, fakes(scenario, spec), PlainPromptBuilder(), translators(), log_dir=tmp_path)
    head, turns, _ = read_run(res.path)
    assert set(head["meta"]["system_prompts"]) == {"aldoria", "veskaria"}
    assert "You open the negotiation" in turns[0].turn_message
    assert "<<<" in turns[1].turn_message  # the delivered message the agent actually saw


def test_deal_below_batna_is_flagged_without_nash_product(scenario, cells):
    spec = spec_for(cells, "A1")
    best_for_aldoria = {i.id: max(range(5), key=lambda k: i.points["aldoria"][k]) for i in scenario.issues}
    llms = {r: FakeNegotiator(scenario.issue_ids, "en", best_for_aldoria) for r in scenario.roles}
    res = run_negotiation(spec, scenario, llms, PlainPromptBuilder(), translators())
    assert res.outcome.status == "deal"
    assert res.outcome.utility["aldoria"] == 100 and res.outcome.below_batna == ["veskaria"]
    assert res.outcome.nash_product is None
