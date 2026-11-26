# Project checklist

Tracks every step from planning to submission. Updated after each step. Legend: `[x]` done, `[~]` in progress, `[ ]` to do, **(you)** needs the team.

Deadline: **Mon 21 Dec 2026** (MIPRO 2027, AIS track). Target submission: Sun 20 Dec.

## 0. Planning (done 25 Nov)

- [x] Confirm MIPRO deadline and format (6 pages incl. references, LaTeX template)
- [x] Related-work search and novelty check
- [x] Study design: 12 conditions × 2 persona pairings, metrics, statistics ([PLAN.md](PLAN.md))
- [x] Scenario "Ostra River crisis" calibrated by script ([planning/scenario_check.py](planning/scenario_check.py))
- [x] ~~$20 budget plan~~ superseded on 26 Nov by the FINKI-only plan; compute and storage estimate in [planning/compute_model.py](planning/compute_model.py)
- [x] Architecture spec ([ARCHITECTURE.md](ARCHITECTURE.md))

## 1. Blockers to clear by Mon 30 Nov

- [x] FINKI-only model line-up researched (26 Nov); request drafted in [docs/requests/finki-gpu-request.md](docs/requests/finki-gpu-request.md)
- [x] PLAN.md (v3) and ARCHITECTURE.md (v2) rewritten for open models on FINKI GPUs, marked **proposed, not confirmed** (26 Nov)
- [ ] **(you)** Send Part A of the request to the OSC lab (with supervisor) and Part B to the supervisor/co-authors
- [ ] **(you)** FINKI answer: allocation, job limits, internet on GPU nodes, vLLM allowed, storage quota
- [ ] **(you)** Find a Russian reviewer (~10 h); guide in [docs/russian-review/README.md](docs/russian-review/README.md)
- [ ] Models confirmed after the pilot (3–4 Dec)
- [ ] ~~Anthropic account with $20 credits~~ not needed (no external AI services)
- [ ] **(you)** Hugging Face account; accept licences for gated models (CometKiwi, Gemma/TranslateGemma)
- [ ] **(you)** Author list; Overleaf or local LaTeX

## 2. Build: step 1, repo and scenario (Thu 26 Nov)

- [x] Git repo initialised, personal identity set for this repo only, remote `origin` added
- [x] `.gitignore` (secrets, venv, logs, model weights), `.env.example`, `README.md`
- [x] Repo layout from ARCHITECTURE.md §3 (`configs/`, `src/negmt/`, `analysis/`, `infra/`, `tests/`, `paper/`)
- [x] `pyproject.toml` and local virtual environment `.venv`
- [x] `configs/scenario/ostra.yaml`: 6 issues, EN/RU labels (RU to be checked by the reviewer), points, BATNAs
- [x] `src/negmt/scenario.py`: load scenario, utility of a deal, Pareto frontier, Nash point, ZOPA
- [x] `tests/test_scenario.py`: reproduces planning numbers (15,625 deals, 32 Pareto-optimal, split 55/50, max joint 140, Nash 68/72, ZOPA 32.7%); 16 tests passing
- [x] First commit (26 Nov)
- [x] Pushed to GitHub as petarpetreski24 (no Claude co-author line; repo-only git identity)

## 3. Build: step 2, protocol and orchestrator with fakes (done 26 Nov)

- [x] `configs/cells.yaml`: A1–A4, B1–B3 (with role swap → 12 variants), C1–C2, persona pairings P1/P2
- [x] `cells.py`: load and sanity-check cells, expand role swaps, build run specs (stable run IDs and seeds, first mover alternates)
- [x] `schemas.py`: run spec, agent output (+ JSON schema for structured outputs), turn record, outcome; `logio.py`: atomic JSONL logs
- [x] `protocol.py`: OPEN / PENDING / DEAL / ILLUSORY / WALK_AWAY / TIMEOUT / ERROR, plus one confirmation reply after the limit
- [x] `channel.py` + `translation/{base,identity,roundtrip,fake}.py`: pass, translate, round-trip, with every case logged
- [x] `llm/{base,fake}.py`: fake negotiator that reads offers from the delivered text; scripted LLM for retry tests
- [x] `agent.py`: context, model call, validation (schema, options, accept rules, message language), up to 2 retries; `langcheck.py`
- [x] `prompts.py`: prompt-builder interface + plain placeholder (real templates in step 3)
- [x] `orchestrator.py`: full negotiation → records, comprehension per turn, outcome scoring, JSONL log
- [x] Tests: 75 passing (protocol, routing, agent validation, cells, end-to-end for all 12 cells × 2 pairings, illusory agreement via corrupting translator, timeout, walk-away, error)

## 4. Build: step 3, English materials (done 26 Nov)

- [x] System, turn and retry prompt templates (EN) in `configs/prompts/`, rendered by `TemplatePromptBuilder` (layers: situation + persona + score table + rules; no mention of translation)
- [x] Hawk and Dove personas (EN) in `configs/personas/`
- [x] Role situation briefs (EN) in `configs/roles/`
- [x] Briefing books: 12 documents per country (EN, ~2,300 words, 46 chunks with IDs like `aldoria/07-world-bank#c2`); `corpus.py` loader and EN/RU alignment check
- [x] Tests: 92 passing (prompts for every role × persona × dialogue language, no leak of the other side's scores, briefings never state points, chunking)
- [ ] **(you)** Team review of materials: [configs/roles](configs/roles), [configs/personas](configs/personas), [configs/corpora](configs/corpora), [configs/prompts/system.en.j2](configs/prompts/system.en.j2)

## 5. Build: step 4, model clients (started 26 Nov)

- [x] `llm/openai_compat.py` for vLLM / Ollama: JSON-schema output, model-specific switches (thinking off), seeds, retries with backoff, `<think>` stripping
- [x] `cache.py`: content-addressed response cache (`CachedLLM`), keyed by model, prompts, schema, seed, temperature
- [x] `configs/models.yaml`: proposed FINKI models (not confirmed), plus an Ollama entry for a laptop smoke test
- [x] ~~`llm/anthropic_client.py` and `budget.py` envelopes~~ dropped (no external AI services)
- [ ] One real negotiation against a vLLM/Ollama server (needs FINKI access)

## 6. Build: step 5, retrieval (Sun 29 Nov)

- [ ] Chunking, BGE-M3 embeddings stored on disk, top-3 retrieval
- [ ] Tests: deterministic retrieval, chunk IDs aligned across EN/RU

## 7. Build: step 6, translation (Mon 30 Nov)

- [x] `translation/identity.py`, `roundtrip.py` (done in step 2)
- [ ] `translation/nllb.py` + `infra/mt_service.py` (sentence splitting, language codes)
- [ ] `translation/openai_mt.py` for Hy-MT2-7B (model card prompt format)
- [ ] Back-translation client for TranslateGemma 27B (check its structured prompt through vLLM)
- [ ] Number-preservation check
- [ ] NLLB tested on laptop CPU (distilled-600M)

## 8. Russian materials (Sat 28 Nov – Wed 2 Dec)

- [x] Reviewer guide: what to check, glossary, the five statement formulas ([docs/russian-review/README.md](docs/russian-review/README.md))
- [ ] Two independent drafts of all RU prompts, personas, briefs, briefing documents
- [ ] Diff of the two drafts to flag disagreements; side-by-side review spreadsheet
- [ ] **(you)** Reviewer's corrections by Wed 2 Dec

## 9. FINKI setup (Mon 30 Nov – Wed 2 Dec)

- [ ] **(you)** eduVPN + SSH key working
- [ ] Apptainer vLLM image, model weights downloaded
- [ ] `infra/slurm/serve_models.sbatch` (servers + runner in one job), `infra/tunnel.sh` (fallback)
- [ ] Smoke run: 1 real negotiation per cell

## 10. Runner (Tue 1 Dec)

- [x] `runner.py`: experiment YAML → grid (960 runs for the full design), ~32 concurrent negotiations, resume by skipping logged runs, crashes reported without logs, `--dry-run` CLI
- [x] `configs/experiments/pilot.yaml` (90 runs) and `aa-test.yaml` (C1 with identity translator)
- [x] Tests: 48 fake runs in parallel, lose 5 logs and resume, crash reporting; 103 tests passing in total
- [x] Recheck (26 Nov) fixed: logs now store both system prompts and every turn message; Nash product only for deals above both BATNAs, plus `below_batna` flag; extra confirmation turn no longer says "Message 11 of 10"; cache writes can't collide; runner reads `.env`; `.env.example` and ports aligned with `models.yaml`; 107 tests passing

## 11. Pilot and freeze (Thu 3 – Fri 4 Dec)

- [ ] ~10 runs per key cell; A/A test with identity channel
- [ ] Calibrate BATNAs to 60–80% EN–EN agreement
- [ ] Translator comparison: NLLB vs Hy-MT2 vs TranslateGemma on ~200 EN↔RU sentences
- [ ] Choose main negotiator (Qwen3.8-27B or Gemma 4 31B); measure real speed; BF16 or FP8
- [ ] Freeze design and analysis plan, git tag `v1.0-frozen`

## 12. Main runs (Sat 5 – Thu 10 Dec)

- [ ] Negotiator 1 grid: 960 runs
- [ ] Negotiator 2 grid: 960 runs
- [ ] Reruns of failed runs; error rate reported

## 13. Analysis (Sat 5 – Tue 15 Dec)

- [ ] Outcome metrics, concessions (DANS), comprehension
- [ ] Back-translation, CometKiwi, chrF/BERTScore, number check
- [ ] LLM judge (Gemma 4 31B on FINKI)
- [ ] **(you)** Reviewer labels 150 messages (9–14 Dec); second judge (Qwen3.8-27B); Cohen's κ
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
