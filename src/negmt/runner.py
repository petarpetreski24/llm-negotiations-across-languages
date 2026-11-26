"""Experiment runner: expands the grid, runs negotiations concurrently, resumes after crashes.

    python -m negmt.runner configs/experiments/pilot.yaml --dry-run
    python -m negmt.runner configs/experiments/pilot.yaml

A run whose log file exists is skipped, so killing and restarting the runner is safe.
Logs are written atomically (see logio.write_run), so a crashed run leaves no log and is redone.
"""

from __future__ import annotations

import argparse
import os
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Mapping, Optional

import yaml

from negmt.cache import CachedLLM, ResponseCache
from negmt.cells import CellVariant, build_run_spec, load_cells
from negmt.logio import log_path
from negmt.orchestrator import run_negotiation
from negmt.prompts import PromptBuilder, TemplatePromptBuilder
from negmt.scenario import Scenario
from negmt.schemas import RunSpec

ROOT = Path(__file__).resolve().parents[2]

LLMFactory = Callable[[str, str, RunSpec], Any]  # (model name, role, spec) -> LLM client
TranslatorFactory = Callable[[str], Any]  # system name -> translator


@dataclass
class Experiment:
    id: str
    model: str
    reps: int
    cells: list[str] | str = "all"
    persona_pairings: list[str] = field(default_factory=lambda: ["P1", "P2"])
    max_rounds: int = 10
    temperature: Optional[float] = 0.7
    mt_systems: dict[str, str] = field(default_factory=dict)
    concurrency: int = 32
    log_dir: str = "logs"
    cache_dir: Optional[str] = "cache"

    @classmethod
    def from_yaml(cls, path: str | Path) -> "Experiment":
        return cls(**yaml.safe_load(Path(path).read_text(encoding="utf-8")))


def plan_runs(exp: Experiment, variants: list[CellVariant], pairings: Mapping[str, Mapping[str, str]]) -> list[RunSpec]:
    wanted = None if exp.cells == "all" else set(exp.cells)
    chosen = [v for v in variants if wanted is None or v.base in wanted or v.name in wanted]
    if wanted is not None:
        unknown = wanted - {v.base for v in variants} - {v.name for v in variants}
        if unknown:
            raise ValueError(f"unknown cells: {sorted(unknown)}")
    specs = []
    for v in chosen:
        for p in exp.persona_pairings:
            for rep in range(exp.reps):
                specs.append(build_run_spec(
                    experiment=exp.id, variant=v, pairing_name=p, pairing=pairings[p], rep=rep, model=exp.model,
                    mt_systems=exp.mt_systems, max_rounds=exp.max_rounds, temperature=exp.temperature,
                ))
    return specs


@dataclass
class RunSummary:
    planned: int = 0
    skipped: int = 0
    finished: int = 0
    crashed: list[tuple[str, str]] = field(default_factory=list)
    status_counts: dict[str, int] = field(default_factory=dict)
    seconds: float = 0.0


def run_experiment(
    exp: Experiment,
    scenario: Scenario,
    specs: list[RunSpec],
    llm_factory: LLMFactory,
    translator_factory: TranslatorFactory,
    prompts: PromptBuilder,
    progress: Optional[Callable[[RunSummary], None]] = None,
) -> RunSummary:
    summary = RunSummary(planned=len(specs))
    todo = [s for s in specs if not log_path(exp.log_dir, s.run_id).exists()]
    summary.skipped = len(specs) - len(todo)
    cache = ResponseCache(exp.cache_dir) if exp.cache_dir else None
    systems = {s.channel.system for s in todo if s.channel.system}
    translators = {name: translator_factory(name) for name in systems}

    def one(spec: RunSpec):
        llms = {}
        for role in scenario.roles:
            client = llm_factory(spec.agents[role].model, role, spec)
            llms[role] = CachedLLM(client, cache) if cache else client
        return run_negotiation(spec, scenario, llms, prompts, translators, log_dir=exp.log_dir)

    t0 = time.perf_counter()
    with ThreadPoolExecutor(max_workers=max(1, exp.concurrency)) as pool:
        futures = {pool.submit(one, s): s for s in todo}
        for fut in as_completed(futures):
            spec = futures[fut]
            try:
                res = fut.result()
                summary.finished += 1
                summary.status_counts[res.outcome.status] = summary.status_counts.get(res.outcome.status, 0) + 1
            except Exception as err:  # infrastructure failure: no log written, rerun later
                summary.crashed.append((spec.run_id, f"{type(err).__name__}: {err}"))
            if progress:
                progress(summary)
    summary.seconds = time.perf_counter() - t0
    return summary


# ---------------- command line ----------------

def _clients_from_config(models_cfg: Mapping[str, Any]) -> tuple[LLMFactory, TranslatorFactory]:
    from negmt.llm.openai_compat import OpenAICompatClient
    from negmt.translation.identity import IdentityTranslator

    shared: dict[str, Any] = {}

    def llm_factory(model: str, role: str, spec: RunSpec):
        if model not in shared:
            cfg = models_cfg["models"][model]
            if cfg["kind"] != "openai_compat":
                raise ValueError(f"model {model}: unsupported kind {cfg['kind']}")
            shared[model] = OpenAICompatClient(
                base_url=os.environ.get(cfg.get("base_url_env", ""), cfg.get("base_url", "")),
                served_name=cfg["served_name"], model=model, sampling=cfg.get("sampling"),
                extra_body=cfg.get("extra_body"), max_tokens=cfg.get("max_tokens", 1024),
            )
        return shared[model]

    def translator_factory(name: str):
        cfg = models_cfg["translators"][name]
        if cfg["kind"] == "identity":
            return IdentityTranslator()
        raise NotImplementedError(f"translator {name}: kind {cfg['kind']} is added in build step 6")

    return llm_factory, translator_factory


def main(argv: Optional[list[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("experiment")
    ap.add_argument("--config-root", default=str(ROOT / "configs"))
    ap.add_argument("--dry-run", action="store_true", help="only list the planned runs")
    args = ap.parse_args(argv)

    root = Path(args.config_root)
    exp = Experiment.from_yaml(args.experiment)
    scenario = Scenario.from_yaml(root / "scenario" / "ostra.yaml")
    variants, pairings = load_cells(root / "cells.yaml")
    specs = plan_runs(exp, variants, pairings)
    done = sum(1 for s in specs if log_path(exp.log_dir, s.run_id).exists())
    print(f"{exp.id}: {len(specs)} runs planned, {done} already logged, model {exp.model}")
    if args.dry_run:
        for s in specs[:20]:
            print("  ", s.run_id, s.channel.mode, s.channel.system or "")
        if len(specs) > 20:
            print(f"   … {len(specs) - 20} more")
        return 0

    models_cfg = yaml.safe_load((root / "models.yaml").read_text(encoding="utf-8"))
    llm_factory, translator_factory = _clients_from_config(models_cfg)

    def progress(s: RunSummary):
        n = s.finished + len(s.crashed)
        if n % 10 == 0 or n == s.planned - s.skipped:
            print(f"  {n}/{s.planned - s.skipped} done, crashed {len(s.crashed)}, {s.status_counts}", flush=True)

    summary = run_experiment(exp, scenario, specs, llm_factory, translator_factory,
                             TemplatePromptBuilder(root), progress)
    print(f"finished {summary.finished}, skipped {summary.skipped}, crashed {len(summary.crashed)} "
          f"in {summary.seconds:.0f}s; outcomes {summary.status_counts}")
    for run_id, err in summary.crashed[:10]:
        print("  crashed:", run_id, err)
    return 1 if summary.crashed else 0


if __name__ == "__main__":
    raise SystemExit(main())
