# Project checklist

Tracks every step from planning to submission. Updated after each step. Legend: `[x]` done, `[~]` in progress, `[ ]` to do, **(you)** needs the team.

Deadline: **Mon 21 Dec 2026** (MIPRO 2027, AIS track). Target submission: Sun 20 Dec.

## 0. Planning (done 25 Nov)

- [x] Confirm MIPRO deadline and format (6 pages incl. references, LaTeX template)
- [x] Related-work search and novelty check
- [x] Study design: 12 conditions × 2 persona pairings, metrics, statistics ([PLAN.md](PLAN.md))
- [x] Scenario "Ostra River crisis" calibrated by script ([planning/scenario_check.py](planning/scenario_check.py))
- [x] $20 budget plan and cost model ([planning/cost_model.py](planning/cost_model.py))
- [x] Architecture spec ([ARCHITECTURE.md](ARCHITECTURE.md))

## 1. Blockers to clear by Mon 30 Nov

- [ ] **(you)** FINKI OSC lab: is the CIIT account active? Job limits, outbound internet on GPU nodes, vLLM allowed?
- [ ] **(you)** Share the CIIT framework code
- [ ] **(you)** Find a Russian validator (~10 h)
- [ ] **(you)** Anthropic account with $20 prepaid credits, auto-reload off; API key in local `.env`
- [ ] **(you)** Hugging Face account; accept licences for gated models (CometKiwi, Gemma/TranslateGemma)
- [ ] **(you)** Author list; Overleaf or local LaTeX

## 2. Build: step 1, repo and scenario (Thu 26 Nov)

- [x] Git repo initialised, personal identity set for this repo only, remote `origin` added
- [x] `.gitignore` (secrets, venv, logs, model weights), `.env.example`, `README.md`
- [x] Repo layout from ARCHITECTURE.md §3 (`configs/`, `src/negmt/`, `analysis/`, `infra/`, `tests/`, `paper/`)
- [x] `pyproject.toml` and local virtual environment `.venv`
- [x] `configs/scenario/ostra.yaml`: 6 issues, EN/RU labels (RU to be checked by validator), points, BATNAs
- [x] `src/negmt/scenario.py`: load scenario, utility of a deal, Pareto frontier, Nash point, ZOPA
- [x] `tests/test_scenario.py`: reproduces planning numbers (15,625 deals, 32 Pareto-optimal, split 55/50, max joint 140, Nash 68/72, ZOPA 32.7%); 16 tests passing
- [x] First commit (26 Nov)
- [ ] **(you)** Push to GitHub (remote `origin` is set; push needs your go-ahead and GitHub login)

## 3. Build: step 2, protocol and orchestrator with fakes (Fri 27 Nov)

- [ ] `configs/cells.yaml`: A1–A4, B1–B3 (with role swap), C1–C2
- [ ] Data models for run spec, agent output, turn record, outcome (`logio.py`)
- [ ] `protocol.py`: OPEN / PENDING / DEAL / ILLUSORY / WALK_AWAY / TIMEOUT / ERROR
- [ ] `channel.py`: routing per cell (pass, translate, round-trip)
- [ ] `llm/fake.py` and `translation/fake.py`
- [ ] `agent.py` shell: build context, call model, validate JSON, retry
- [ ] `orchestrator.py`: one full negotiation → JSONL log
- [ ] Tests: protocol transitions, routing per cell, end-to-end run for every cell with fakes

## 4. Build: step 3, English materials (Fri 27 – Sat 28 Nov)

- [ ] System and turn prompt templates (EN)
- [ ] Hawk and Dove personas (EN)
- [ ] Briefing books: 10–15 documents per country (EN), chunked with stable IDs
- [ ] **(you)** Team review of materials

## 5. Build: step 4, model clients (Sat 28 – Sun 29 Nov)

- [ ] `llm/openai_compat.py` (vLLM / Ollama), JSON schema output, thinking off, seeds
- [ ] `llm/anthropic_client.py` (Claude Haiku/Sonnet), structured outputs, Batch API
- [ ] `budget.py` envelopes ($8 reserved for analysis) and `cache.py`
- [ ] One real Haiku negotiation (a few cents)

## 6. Build: step 5, retrieval (Sun 29 Nov)

- [ ] Chunking, BGE-M3 embeddings stored on disk, top-3 retrieval
- [ ] Tests: deterministic retrieval, chunk IDs aligned across EN/RU

## 7. Build: step 6, translation (Mon 30 Nov)

- [ ] `translation/identity.py`, `roundtrip.py`
- [ ] `translation/nllb.py` + `infra/mt_service.py` (sentence splitting, language codes)
- [ ] `translation/translategemma.py` (confirm HF ID and prompt format)
- [ ] Number-preservation check
- [ ] NLLB tested on laptop CPU (distilled-600M)

## 8. Russian materials (Sat 28 Nov – Wed 2 Dec)

- [ ] Two independent LLM drafts of all RU prompts, personas, labels, briefings
- [ ] Back-translation diff to flag disagreements
- [ ] **(you)** Validator review and sign-off by Wed 2 Dec

## 9. FINKI setup (Mon 30 Nov – Wed 2 Dec)

- [ ] **(you)** eduVPN + SSH key working
- [ ] Apptainer vLLM image, model weights downloaded
- [ ] `infra/slurm/serve_models.sbatch`, `run_grid.sbatch`, `infra/tunnel.sh`
- [ ] Smoke run: 1 real negotiation per cell

## 10. Runner (Tue 1 Dec)

- [ ] Grid expansion, ~32 concurrent negotiations, resume after crash
- [ ] Test: 50 fake runs in parallel, kill and resume

## 11. Pilot and freeze (Thu 3 – Fri 4 Dec)

- [ ] ~10 runs per key cell; A/A test with identity channel
- [ ] Calibrate BATNAs to 60–80% EN–EN agreement
- [ ] Choose negotiator (Qwen3.8-27B or Gemma 4 31B); measure real token cost
- [ ] Freeze design and analysis plan, git tag `v1.0-frozen`

## 12. Main runs (Sat 5 – Thu 10 Dec)

- [ ] Qwen grid: 960 runs
- [ ] Claude Haiku replication: 240 runs (capped at $8)
- [ ] Reruns of failed runs; error rate reported

## 13. Analysis (Sat 5 – Tue 15 Dec)

- [ ] Outcome metrics, concessions (DANS), comprehension
- [ ] Back-translation, CometKiwi, chrF/BERTScore, number check
- [ ] LLM judge (Haiku batch)
- [ ] **(you)** Validator labels 150 messages (9–14 Dec); Sonnet check; Cohen's κ
- [ ] Error→outcome linking
- [ ] Statistics and figures into `paper/`

## 14. Paper (1 – 20 Dec)

- [ ] MIPRO LaTeX template in `paper/`
- [ ] Intro, related work, method drafted by Wed 9 Dec
- [ ] Results and discussion 14–17 Dec; full draft Thu 17 Dec
- [ ] OSC lab acknowledgement sentence included
- [ ] Internal review, trim to 6 pages, template check (18–19 Dec)
- [ ] **(you)** Submit via MIPRO portal, Sun 20 Dec
- [ ] Make repo public, tag release
