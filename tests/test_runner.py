from pathlib import Path

import pytest

from negmt.cache import CachedLLM, ResponseCache
from negmt.llm.fake import FakeNegotiator, ScriptedLLM
from negmt.logio import log_path
from negmt.prompts import PlainPromptBuilder
from negmt.runner import Experiment, main, plan_runs, run_experiment
from negmt.translation.fake import TaggingTranslator
from tests.conftest import ROOT


def exp(tmp_path, **kw):
    base = dict(id="t", model="fake", reps=2, mt_systems={"MT1": "m1", "MT2": "m2"}, concurrency=8,
                log_dir=str(tmp_path / "logs"), cache_dir=None)
    base.update(kw)
    return Experiment(**base)


def factories(scenario, crash_on=None):
    def llm_factory(model, role, spec):
        if crash_on and crash_on in spec.run_id:
            raise ConnectionError("server down")
        return FakeNegotiator(scenario.issue_ids, spec.agents[role].dialog_lang, scenario.nash_point().deal)

    return llm_factory, lambda name: TaggingTranslator(name)


def test_plan_counts(cells, tmp_path):
    variants, pairings = cells
    assert len(plan_runs(exp(tmp_path, reps=40), variants, pairings)) == 12 * 2 * 40  # full grid: 960
    some = plan_runs(exp(tmp_path, reps=3, cells=["B2", "A1"], persona_pairings=["P2"]), variants, pairings)
    assert len(some) == 3 * 3  # A1, B2, B2-swap
    with pytest.raises(ValueError):
        plan_runs(exp(tmp_path, cells=["Z9"]), variants, pairings)


def test_parallel_run_and_resume(scenario, cells, tmp_path):
    variants, pairings = cells
    e = exp(tmp_path, reps=2)  # 48 runs
    specs = plan_runs(e, variants, pairings)
    prompts = PlainPromptBuilder()

    first = run_experiment(e, scenario, specs, *factories(scenario), prompts)
    assert first.finished == 48 and first.skipped == 0 and not first.crashed
    assert first.status_counts == {"deal": 48}

    # simulate a crash: lose a few logs, then restart
    lost = specs[:5]
    for s in lost:
        log_path(e.log_dir, s.run_id).unlink()
    again = run_experiment(e, scenario, specs, *factories(scenario), prompts)
    assert again.skipped == 43 and again.finished == 5


def test_infrastructure_failures_are_reported_not_logged(scenario, cells, tmp_path):
    variants, pairings = cells
    e = exp(tmp_path, reps=1, cells=["A1", "A2"], persona_pairings=["P1"])
    specs = plan_runs(e, variants, pairings)
    summary = run_experiment(e, scenario, specs, *factories(scenario, crash_on="/A2/"), PlainPromptBuilder())
    assert summary.finished == 1 and len(summary.crashed) == 1
    assert not log_path(e.log_dir, specs[1].run_id).exists()


def test_cache_serves_repeat_calls(tmp_path):
    inner = ScriptedLLM(['{"x": 1}'])
    cached = CachedLLM(inner, ResponseCache(tmp_path))
    a = cached.generate("s", [{"role": "user", "content": "u"}], {}, seed=1)
    b = cached.generate("s", [{"role": "user", "content": "u"}], {}, seed=1)
    assert a.text == b.text == '{"x": 1}' and b.meta["cached"] and cached.hits == 1 and cached.misses == 1
    with pytest.raises(RuntimeError):  # a different seed is a different request
        cached.generate("s", [{"role": "user", "content": "u"}], {}, seed=2)


@pytest.mark.parametrize("name", ["pilot.yaml", "aa-test.yaml"])
def test_shipped_experiment_configs_dry_run(name, capsys):
    assert main([str(ROOT / "configs" / "experiments" / name), "--dry-run"]) == 0
    assert "runs planned" in capsys.readouterr().out


def test_env_file_loader(tmp_path, monkeypatch):
    from negmt.runner import load_env_file

    monkeypatch.delenv("NEGMT_TEST_A", raising=False)
    monkeypatch.setenv("NEGMT_TEST_B", "kept")
    env = tmp_path / ".env"
    env.write_text("# comment\nNEGMT_TEST_A=http://x:1\nNEGMT_TEST_B=overridden\nEMPTY=\n", encoding="utf-8")
    loaded = load_env_file(env)
    import os
    assert os.environ["NEGMT_TEST_A"] == "http://x:1" and os.environ["NEGMT_TEST_B"] == "kept"
    assert loaded == {"NEGMT_TEST_A": "http://x:1"}
