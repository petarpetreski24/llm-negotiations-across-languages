# LLM negotiations across languages

Code and data for the MIPRO 2027 paper *Lost in Translation? Native-Language versus Lingua-Franca Negotiation Between LLM Agents*.

Two retrieval-grounded LLM agents with personas negotiate a fictional multi-issue water treaty (the "Ostra River crisis"). We compare English–English and Russian–Russian negotiations with mixed English–Russian pairs connected by machine translation, vary the instruction and dialogue languages separately, and use back-translation to locate where meaning is lost.

- [PLAN.md](PLAN.md): study design, budget, timeline
- [ARCHITECTURE.md](ARCHITECTURE.md): software design
- [CHECKLIST.md](CHECKLIST.md): progress

## Setup

```bash
python -m venv .venv
.venv/Scripts/activate        # Windows; use .venv/bin/activate on Linux
pip install -e ".[dev]"
pytest
```

Copy `.env.example` to `.env` and fill in the keys. `.env` is never committed.

## Layout

```
configs/    scenario, cells, personas, prompts, briefing corpora, models, experiments
src/negmt/  negotiation engine (scenario, agents, protocol, channel, runner)
analysis/   metrics, translation-error analysis, statistics, figures
infra/      FINKI deployment (Apptainer, SLURM, tunnel, MT service)
planning/   calibration and cost scripts
tests/      unit and end-to-end tests
paper/      LaTeX source
```
