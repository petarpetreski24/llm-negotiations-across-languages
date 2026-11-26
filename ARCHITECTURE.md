# Architecture: what we will build

This is the companion to [PLAN.md](PLAN.md), which covers the study design and budget. This file covers the software: components, data formats, the negotiation protocol, where each part runs, how we test it, and the order we build it in. Draft v1, 25 Nov 2026.

## 1. In one paragraph

We are building a **research pipeline**, not an app. A Python program (the *runner*) plays thousands of negotiations between two LLM agents. Each agent has a role, a persona, a private score table and a private briefing it searches each turn. Every message goes through a pluggable **translation channel** that either passes it through, translates it with one of two MT systems, or round-trips it. Everything is logged as JSONL. A second set of scripts (the *analysis*) turns the logs into negotiation metrics and a translation-error analysis, then into the tables and figures for the paper. There is no UI, no mediator agent and no fine-tuning; it runs from the command line.

## 2. Components

| # | Component | What it does | Where it runs |
|---|---|---|---|
| 1 | **Scenario and scoring** | Issues, options with EN and RU labels, each side's points and BATNA; computes the utility of any deal, the Pareto frontier and the Nash point | runner and analysis |
| 2 | **Prompt builder** | Renders each agent's system prompt in its *instruction language* from layers: situation, persona, score table, rules | runner |
| 3 | **Retriever (RAG)** | Per-role briefing corpus in the agent's instruction language; returns the top 3 chunks per turn, with chunk IDs shared across EN and RU | runner (CPU) |
| 4 | **Agent** | Builds the turn context, calls its model, validates the JSON and the message language, and retries if needed | runner |
| 5 | **LLM clients** | One interface with two adapters: OpenAI-compatible (vLLM on FINKI, or Ollama as in the CIIT paper) and the Anthropic SDK (Claude) | runner |
| 6 | **Translation channel** | Decides per message whether to translate, in which direction and with which system; logs every translation | runner, calling MT services |
| 7 | **MT adapters** | `identity`, `nllb` (NLLB-200 3.3B), `translategemma` (TranslateGemma 27B via vLLM), `roundtrip(inner)`, plus `fake` for tests | FINKI GPU |
| 8 | **Protocol engine** | Turn order, accept/confirm rules, termination: deal, illusory agreement, walk-away, timeout or error | runner |
| 9 | **Runner** | Expands the experiment grid, runs ~32 negotiations concurrently, resumes after crashes, caches responses, enforces the budget | FINKI node, front node or laptop |
| 10 | **Logger** | One JSONL file per negotiation, containing every prompt, retrieval, response, translation, token count and cost | runner |
| 11 | **Analysis** | Outcome metrics, concession and comprehension metrics, the translation-error pipeline (back-translation, QE, LLM judge, human check), statistics and figures | laptop, plus the Anthropic Batch API |

## 3. Repository layout

```
lost-in-translation/
├── PLAN.md · ARCHITECTURE.md · README.md · .env.example (never commit .env)
├── configs/
│   ├── scenario/ostra.yaml            issues, options (EN/RU labels), points, BATNAs
│   ├── cells.yaml                     A1–A4, B1–B3, C1–C2: languages per agent + channel
│   ├── personas/{hawk,dove}.{en,ru}.md
│   ├── prompts/{system,turn}.{en,ru}.j2   Jinja2 templates per instruction language
│   ├── corpora/{aldoria,veskaria}/{en,ru}/*.md   RAG briefings, parallel files
│   ├── models.yaml                    endpoints, served names, settings, prices
│   └── experiments/{pilot,main,replication}.yaml
├── src/negmt/
│   ├── scenario.py   cells.py   schemas.py   prompts.py   rag.py   agent.py   protocol.py
│   ├── orchestrator.py   channel.py   runner.py   budget.py   cache.py   langcheck.py   logio.py
│   ├── llm/          base.py · openai_compat.py · anthropic_client.py · fake.py
│   └── translation/  base.py · identity.py · nllb.py · translategemma.py · roundtrip.py · fake.py
├── analysis/
│   ├── metrics.py    stats.py    figures.py
│   └── translation_eval/  extract.py · backtranslate.py · autoscores.py · judge.py · human.py · agreement.py
├── infra/
│   ├── vllm.sif (built, not committed) · mt_service.py (FastAPI around NLLB)
│   ├── slurm/serve_models.sbatch · slurm/run_grid.sbatch
│   └── tunnel.sh                      SSH port-forward from runner to GPU node
├── planning/   cost_model.py · scenario_check.py
├── tests/      unit tests + end-to-end tests with fake LLM and fake translator
└── paper/      MIPRO LaTeX template · sections/ · figures/ · tables/
```

Estimated size: about 1.5–2k lines of Python, plus configs, materials and tests.

## 4. Data formats

### 4.1 Scenario (`configs/scenario/ostra.yaml`, excerpt)

```yaml
id: ostra-v1
roles:
  aldoria:  {batna: 45}
  veskaria: {batna: 45}
issues:
  - id: filling
    label: {en: "Reservoir filling period", ru: "Срок заполнения водохранилища"}
    options:
      - {id: 0, label: {en: "3 years",  ru: "3 года"}}
      - {id: 1, label: {en: "5 years",  ru: "5 лет"}}
      - {id: 2, label: {en: "7 years",  ru: "7 лет"}}
      - {id: 3, label: {en: "10 years", ru: "10 лет"}}
      - {id: 4, label: {en: "15 years", ru: "15 лет"}}
    points: {aldoria: [25, 19, 13, 7, 0], veskaria: [0, 4, 8, 12, 15]}
  # release, compensation, electricity, monitoring, communique …
```

A native speaker fixes the Russian option labels, so the agents' option lists are equivalent. MT is never applied to these labels; it only touches the messages agents write.

### 4.2 Cells (`configs/cells.yaml`, excerpt)

```yaml
A1: {agents: [{instr: en, dialog: en}, {instr: en, dialog: en}], channel: {mode: none}}
A3: {agents: [{instr: en, dialog: ru}, {instr: en, dialog: ru}], channel: {mode: none}}
B2: {agents: [{instr: en, dialog: en}, {instr: ru, dialog: ru}], channel: {mode: mt, system: MT1}, swap_roles: true}
C1: {agents: [{instr: en, dialog: en}, {instr: en, dialog: en}], channel: {mode: roundtrip, system: MT1, pivot: ru}}
```

### 4.3 Agent output per turn (enforced with a JSON schema)

```json
{
  "message": "text for the other delegation, in your dialogue language, ≤150 words",
  "my_offer": {"filling": 0, "release": 4, "compensation": 0, "electricity": 4, "monitoring": 3, "communique": 2},
  "their_offer_as_understood": {"filling": 1, "release": 3, "compensation": null, "electricity": 2, "monitoring": 3, "communique": 0},
  "decision": "continue",
  "accepted_terms": null,
  "plan": "private, ≤40 words, instruction language"
}
```

Validation rules:
- every issue is present in `my_offer`, with valid option IDs;
- `accepted_terms` is required exactly when `decision` is `accept`;
- the language of `message` must match the agent's dialogue language.

On failure, the agent is re-asked with the error, at most twice. After that the run is marked `error`, and error runs are counted and reported.

JSON keys and option IDs are language-neutral; only `message` (and `plan`) are natural language. That is how we measure comprehension: the counterpart only ever sees `message`, but we can compare its `their_offer_as_understood` with the true `my_offer`.

### 4.4 Turn log record (one line per turn in `logs/<run_id>.jsonl`)

```json
{"run_id": "main/qwen/B2-swap/P2/017", "turn": 7, "round": 4, "speaker": "veskaria",
 "model": "qwen3.8-27b", "instr_lang": "ru", "dialog_lang": "ru",
 "retrieved": ["ves-hydro-02#c3", "ves-law-01#c1", "ves-press-04#c2"],
 "prompt_sha": "…", "prompt": "…(compressed)…", "raw": "…", "output": {…},
 "lang_detected": "ru", "retries": 0, "usage": {"in": 6120, "out": 402, "usd": 0.0}, "ms": 2140,
 "channel": {"mode": "mt", "system": "nllb-200-3.3b", "src": "ru", "tgt": "en",
             "source_text": "…", "delivered_text": "…", "pivot_text": null, "ms": 840}}
```

The first line of each file is the full run spec: cell, persona pairing, seed, first mover, model settings, git commit and config hashes. The last line is the outcome:

```json
{"status": "deal | illusory | walk_away | timeout | error", "rounds": 7,
 "terms": {"aldoria": {…}, "veskaria": {…}}, "utility": {"aldoria": 68, "veskaria": 72},
 "joint": 140, "pareto_distance": 0, "nash_product": 621}
```

### 4.5 Judge output (translation-error analysis, one per translated message)

```json
{"errors": [{"category": "semantic | pragmatic | cultural",
             "type": "number | omission | addition | negation | entity | term | condition | commitment | stance | speech_act | formality | hedge | idiom | formula | reference | register",
             "severity": "minor | major | critical", "offer_relevant": true,
             "span_source": "…", "span_translation": "…", "note": "…"}],
 "tone": {"source":      {"assertiveness": 4, "politeness": 2, "commitment": 5},
          "translation": {"assertiveness": 3, "politeness": 3, "commitment": 4}}}
```

## 5. The negotiation protocol

```
OPEN ──X: continue (counter-offer)──▶ OPEN  (other side's turn)
OPEN ──X: accept(T_x)──▶ PENDING(T_x) ──Y: accept(T_y), T_y == T_x──▶ DEAL
                                       ──Y: accept(T_y), T_y != T_x──▶ ILLUSORY  (both think they agreed)
                                       ──Y: continue──▶ OPEN       (acceptance lapses)
any state ──walk_away──▶ WALK_AWAY      after 2×10 messages ──▶ TIMEOUT      unrecoverable failure ──▶ ERROR
```

- **Turns:** agents alternate, 10 each. The first mover alternates by run index.
- **Payoffs:** DEAL pays the utility of the terms. ILLUSORY, WALK_AWAY and TIMEOUT pay each side its BATNA, and for ILLUSORY we also record the two believed deals.
- **Knowledge:** agents know the round limit, their own scores and their own briefing. They do **not** know the other side's scores, and they are never told that messages are translated.

## 6. Inside one turn

1. **Who speaks.** The orchestrator picks speaker X in round r.
2. **What X sees.** X's history contains its own messages as written and the other side's messages as delivered, meaning after the channel, in X's dialogue language.
3. **Retrieve.** The query is the latest incoming message plus X's last plan, embedded with BGE-M3. X gets the top 3 chunks from its own corpus, in its instruction language, and the chunk IDs are logged.
4. **Prompt.** The system prompt is written in the instruction language: situation, persona, score table with BATNA, and rules, including "write `message` in <dialogue language>" and "don't reveal exact point values". It is followed by the retrieved excerpts and the history, then a turn note ("round r of 10").
5. **Call the model.** Structured output is forced by the JSON schema. Thinking/reasoning is off.
6. **Validate.** Check the schema, the option IDs and the message language, and retry up to 2 times.
7. **Channel.** If the receiver's dialogue language differs, translate with the cell's MT system. In C cells, round-trip through Russian. Otherwise pass the message through unchanged. Every case is logged.
8. **Deliver and update.** Append the delivered text to Y's history, update the protocol state, and write the turn record.

Example from cell B2 (NLLB):
- **Aldoria (English) writes:** "We can guarantee 40 bcm in drought years if Veskaria drops the cash compensation." Its private `my_offer` holds `release: 3` and `compensation: 0`.
- **The channel translates EN→RU:** «Мы можем гарантировать 40 млрд м³ в засушливые годы, если Вескария откажется от денежной компенсации.»
- **Veskaria's agent reads only that Russian text.** It searches its Russian hydrology brief, replies in Russian, and records `their_offer_as_understood`.
- **Afterwards we check:** did it understand `release: 3, compensation: 0`? And did the judge find any errors in the translation?

## 7. Translation channel and MT systems

| Cell type | Sender → receiver dialogue | Channel action |
|---|---|---|
| A1–A4, B1 | same language | pass through (we assert the languages really are equal) |
| B2 / B3 | EN ↔ RU | translate with MT1 (NLLB) / MT2 (TranslateGemma) |
| C1 / C2 | EN → EN | EN→RU→EN round trip with MT1 / MT2 |

Every adapter implements `translate(text, src, tgt) -> TranslationResult{text, system, ms, meta}`:

- **NLLB-200 3.3B** (`facebook/nllb-200-3.3B`, CC-BY-NC):
  - translates sentence by sentence (split with `razdel` for Russian and `pysbd` for English), using language codes `eng_Latn` / `rus_Cyrl`;
  - is served by `infra/mt_service.py`, a small FastAPI app on the GPU that batches requests.
- **TranslateGemma 27B:**
  - served by vLLM, using the prompt format from its model card (exact Hugging Face ID and template still to be checked);
  - always receives one whole message, with no extra context.
- **Number check:** after every translation we compare the numbers, percentages and amounts in the source and the output, handling the Russian decimal comma. A mismatch is flagged as a candidate semantic error.

## 8. Models and clients

| Name in `models.yaml` | Client | Settings |
|---|---|---|
| `qwen3.8-27b` (main negotiator) | OpenAI-compatible → vLLM `:8000` | BF16, `enable_thinking: false`, temperature 0.7, per-request seed, `response_format` = JSON schema |
| `gemma-4-31b` (fallback negotiator) | OpenAI-compatible → vLLM `:8000` | same; if used, Qwen becomes MT2 |
| `claude-haiku-5-5` (replication, back-translation, judge) | Anthropic Python SDK | thinking disabled for negotiation, low effort for the judge, structured outputs, no sampling parameters (the current API rejects them), prompt caching, Batch API for offline jobs |
| `claude-sonnet-5-5` (judge check, 150 messages) | Anthropic SDK, batch | |
| `translategemma-27b` | OpenAI-compatible → vLLM `:8001` | |
| `nllb-200-3.3b` | `mt_service` `:8002` | |

The CIIT code talked to Ollama through its OpenAI-compatible API. vLLM speaks the same API, so their client code should work with a different base URL. We can also fall back to Ollama if FINKI doesn't allow vLLM.

## 9. Runner

- **Grid:** `python -m negmt.runner configs/experiments/main.yaml` expands cells × persona pairings × repetitions. B cells are also run with roles swapped. Each run gets a stable ID, for example `main/qwen/B2-swap/P2/017`.
- **Concurrency:** asyncio runs about 32 negotiations at once against vLLM, which batches them. A separate small limit applies to Anthropic calls.
- **Resume:** finished run IDs are skipped. A crashed run restarts from the beginning, and partial logs are kept separately.
- **Cache:** responses are stored by a hash of model, prompt and settings, so reruns and analysis never pay twice.
- **Budget guard:**
  - every paid response is costed from its token counts;
  - spending is split into envelopes, and $8 is reserved for back-translation, judging and the Sonnet check before any Claude negotiations run;
  - the runner refuses to start a paid run that would overflow its envelope;
  - prepaid $20 credits with auto-reload off form the outer limit.

## 10. Deployment

```
┌──────── FINKI GPU node (SLURM job, Apptainer) ────────┐        ┌──── Anthropic API ────┐
│ GPU0  vLLM :8000  Qwen3.8-27B   (negotiator)          │        │ Claude Haiku 5.5      │
│ GPU1  vLLM :8001  TranslateGemma 27B   (MT2)          │        │ Claude Sonnet 5.5     │
│ GPU1  mt_service :8002  NLLB-200 3.3B  (MT1)          │        └───────────▲───────────┘
└───────────────▲───────────────────────────────────────┘                    │ HTTPS
                │ local ports, or SSH tunnel over eduVPN                      │
        ┌───────┴──────────── runner (Python) ────────────────────────────────┴┐
        │ on the GPU node if it has internet; otherwise on the front node / laptop │
        └───────────────────────────────┬───────────────────────────────────────┘
                                        ▼
                         logs/ (JSONL) → analysis on the laptop → paper/
```

- **GPU memory:** Qwen BF16 needs about 56 GB on GPU0. TranslateGemma (about 55 GB) and NLLB (about 7 GB) share GPU1, with vLLM capped at about 75% of that GPU's memory.
- **Storage:** about 140–200 GB for weights, the container and logs.
- **One SLURM job** (`serve_models.sbatch`) starts the three services and stays up for the run window.
- **The runner job** (`run_grid.sbatch`) runs on the same node if outbound HTTPS works. If not, `infra/tunnel.sh` forwards ports 8000–8002 to wherever the runner runs.
- **Fallback without FINKI:**
  - a cheap hosted Qwen model replaces vLLM;
  - NLLB-200 distilled-1.3B runs on the laptop CPU;
  - Claude Haiku becomes the LLM translator;
  - the Claude replication is dropped.

## 11. Analysis pipeline

1. **Outcome metrics** (`analysis/metrics.py`):
   - status counts and rounds;
   - utilities, joint utility, Pareto distance and Nash product;
   - lose-lose on the monitoring issue;
   - concession curves and DANS move types, computed from `my_offer` sequences;
   - comprehension accuracy (`their_offer_as_understood` against the true offer);
   - language compliance, message length and politeness markers.
2. **Translation errors** (`analysis/translation_eval/`):
   - extract every MT event;
   - back-translate with Claude Haiku (batch);
   - compute automatic scores: CometKiwi QE, plus chrF and BERTScore between the original and its back-translation, plus the number check;
   - run the LLM judge (Haiku, batch, schema 4.5);
   - export a 150-message stratified sample for the Russian validator and re-import the labels;
   - compute Cohen's κ against the human labels, and judge the same 150 with Sonnet.
3. **Linking errors to outcomes:**
   - turn-level: what happens in the 1–2 turns after an error (misread offer, change of move type);
   - run-level: regression of outcomes on error counts per category.
4. **Statistics and figures** (`analysis/stats.py`, `figures.py`):
   - models and tests as listed in PLAN.md §13;
   - figures and tables are written straight into `paper/figures` and `paper/tables`.

## 12. Reproducibility and data release

- **What each log records:** the config, the git commit, model IDs and revisions, prompt-template hashes, seeds and the full prompts.
- **Retrieval** is deterministic: the embeddings are computed once and stored.
- **Release:**
  - code and configs go on GitHub;
  - logs and annotations are zipped as a GitHub release, archived on Zenodo for a DOI at camera-ready;
  - `.env` with API keys and the HF token is never committed.

## 13. Testing

| Level | What | How |
|---|---|---|
| Unit | Utility, Pareto (32 deals), Nash (68/72); validators; protocol transitions; channel routing per cell; retrieval determinism; number check; budget envelopes | pytest |
| End-to-end, free | A full negotiation for every cell using a scripted `FakeLLM` and a tagging `FakeTranslator`; checks logs, outcomes and routing | pytest |
| A/A | EN–EN with an identity translator in the channel must match EN–EN with no channel | pilot |
| Smoke | 1 real run per cell and model | before the pilot |
| Manipulation checks | Language ID per message, JSON validity rate, MT output non-empty and actually translated, offer text matching the structured offer (sample) | runner and analysis |
| Pilot | ~10 runs per key cell: calibrate BATNAs (60–80% EN–EN agreement), choose Qwen or Gemma, measure real tokens and cost | 3–4 Dec |

## 14. Build plan

| When | Step | Done when |
|---|---|---|
| Thu 26 Nov | 1. Repo scaffold, `scenario.py`, `ostra.yaml`, unit tests | Pareto/Nash tests reproduce `planning/scenario_check.py` |
| Fri 27 Nov | 2. Protocol, orchestrator, channel, logger, with fakes | Every cell runs end-to-end with fakes and logs validate |
| Fri 27 – Sat 28 Nov | 3. EN materials: prompt templates, Hawk and Dove personas, 10–15 briefing docs per role | Team has reviewed them |
| Sat 28 – Sun 29 Nov | 4. LLM clients (OpenAI-compatible and Anthropic), JSON enforcement, retries, cache, budget guard | One real Haiku negotiation for a few cents |
| Sun 29 Nov | 5. RAG: chunking, BGE-M3 embeddings, retrieval | Retrieval tests pass; chunk IDs align across EN and RU |
| Mon 30 Nov | 6. MT adapters, `mt_service`, number check | NLLB works on the laptop CPU (distilled-600M) |
| Mon 30 Nov – Wed 2 Dec | 7. FINKI: container, SLURM scripts, services, tunnel | One smoke run per cell on real models |
| Sat 28 Nov – Wed 2 Dec | 8. RU materials: two LLM drafts plus a back-translation diff, then the validator's review | Validator signs off |
| Tue 1 Dec | 9. Runner: grid, concurrency, resume | 50 fake runs in parallel, then resumed after a kill |
| Thu 3 – Fri 4 Dec | 10. Pilot and calibration; freeze design and analysis plan (git tag `v1.0-frozen`) | Baseline agreement 60–80% |
| Sat 5 – Wed 9 Dec | 11. Analysis code, written while the main runs execute | Metrics and figures regenerate from logs with one command |

## 15. Reusing the CIIT code

| CIIT part | Becomes |
|---|---|
| Ollama client (OpenAI-compatible) | `llm/openai_compat.py`, with the base URL pointed at vLLM |
| Country prompt + archetype + task rules | `configs/personas/*`, `configs/prompts/*` |
| Alternating turn loop with full history | `orchestrator.py` + `protocol.py` (adds accept/confirm and the channel) |
| JSON-schema judge | Template for `translation_eval/judge.py`; its consistency/coherence rubric becomes the secondary persona-adherence measure |
| Run logging and failure flags | `logio.py` (extended with translations, retrievals and costs) |

If their code is easy to extend, we keep its structure and add the new modules. If not, we port its prompts and personas into this layout.

## 16. Open technical questions

- Do the FINKI GPU nodes have outbound internet? This decides where the runner lives.
- Can a long-running vLLM server sit inside a SLURM job? Can we build Apptainer images on the cluster?
- TranslateGemma's exact Hugging Face ID and prompt template, and its EN↔RU quality (check in the pilot).
- Qwen3.8-27B's Russian quality, and whether it deadlocks like Qwen3-32B did in the CIIT runs (check in the pilot).
- Haiku 5.5's minimum cacheable prompt length. The budget assumes no caching.
