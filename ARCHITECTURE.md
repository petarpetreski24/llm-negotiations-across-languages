# Architecture: what we will build (v2: open models on FINKI GPUs)

This is the companion to [PLAN.md](PLAN.md), which covers the study design. This file covers the software: components, how they communicate, where they run, what space they use, how they are set up, data formats, the protocol, tests and the build order.

> **The model choices are PROPOSED, NOT CONFIRMED** until FINKI answers the GPU request and the pilot (3–4 Dec) has run. The software does not depend on them: any model served through an OpenAI-compatible API can be swapped in by editing `configs/models.yaml`.

## 1. In one paragraph

We are building a **research pipeline**, not an app. A Python program (the *runner*) plays about 2,000 negotiations between two LLM agents. Each agent has a role, a persona, a private score table and a private briefing it searches each turn. Every message goes through a pluggable **translation channel**, which either passes it on, translates it with one of two MT systems, or round-trips it. Everything is logged to files. A second set of scripts (the *analysis*) turns the logs into negotiation metrics and a translation-error analysis, then into the tables and figures for the paper. There is no UI and no fine-tuning; everything runs from the command line.

## 2. Components

| # | Component | What it does | Status |
|---|---|---|---|
| 1 | **Scenario and scoring** (`scenario.py`, `ostra.yaml`) | Issues, options with EN/RU labels, points, BATNAs; utility of any deal, Pareto frontier, Nash point | done |
| 2 | **Cells** (`cells.py`, `cells.yaml`) | The 12 experimental conditions and the 2 persona pairings → one run spec per negotiation | done |
| 3 | **Prompt builder** (`prompts.py`, `configs/prompts`) | Renders each agent's prompts in its *instruction language* from layers: situation, persona, score table, rules | EN done; RU drafted, with the reviewer |
| 4 | **Retriever** (`rag.py`, `corpus.py`) | Splits the briefing books into sections; returns the 3 most relevant per turn | loader done; search next |
| 5 | **Agent** (`agent.py`) | Builds the turn context, calls its model, checks the reply (format, options, language), retries | done |
| 6 | **Model client** (`llm/openai_compat.py`) | Talks to any OpenAI-compatible server (vLLM on FINKI, Ollama for local tests) | done |
| 7 | **Translation channel** (`channel.py`, `translation/`) | Decides per message whether and how to translate, and logs it | done; NLLB and Hy-MT2 adapters next |
| 8 | **Protocol** (`protocol.py`) | Turn order, accept/confirm rules, end of the talks | done |
| 9 | **Orchestrator** (`orchestrator.py`) | Plays one negotiation end to end and scores it | done |
| 10 | **Runner** (`runner.py`), **cache** (`cache.py`) | Runs the whole grid in parallel, resumes after crashes, stores every model reply | done |
| 11 | **Analysis** (`analysis/`) | Outcome metrics; back-translation, quality scores, LLM judge, human check; statistics and figures | Dec 5–9 |
| 12 | **Infrastructure** (`infra/`) | Container recipe, SLURM job scripts, NLLB service, SSH tunnel | Nov 30 – Dec 2 |

## 3. How the pieces talk to each other (plain language)

**The short version.** Every model runs as its own small web server on the GPU node. The runner, a normal Python program, sends it a question as an HTTP request and gets the answer back. The agents never talk to each other directly. Every message goes through the runner, which also decides whether it gets translated.

**Who holds what.**
- **A model server** (for example vLLM serving Qwen3.8-27B on GPU 0) holds only the model weights. It has no memory of earlier requests. Each request contains everything the model needs: the system prompt, the conversation so far as that agent saw it, and this turn's briefing excerpts. That is why one server can play *both* sides of a negotiation, and many negotiations at once, without mixing them up.
- **The runner** holds the agents. An "agent" is just a Python object: its persona, its score table, its conversation history and its language settings. The runner also holds the protocol state (whose turn it is, whether someone has accepted) and writes the log.
- **The translation servers** (NLLB and Hy-MT2) only translate. They receive text, a source language and a target language, and return the translation.

**What happens to one message**, here Aldoria (English) writing to Veskaria (Russian) in cell B3:
1. The runner asks the retriever for Aldoria's 3 most relevant briefing sections. This is a fast in-memory search on the CPU.
2. The runner sends the Qwen server Aldoria's system prompt, history and excerpts (`POST http://localhost:8000/v1/chat/completions`) and asks for a reply in a fixed JSON format.
3. The reply comes back with a public `message` and private fields (the offer, what Aldoria thinks Veskaria offered, accept or not). The runner checks it and retries if it is broken.
4. The runner sends only the `message` to the Hy-MT2 server (`localhost:8002`): "translate from English to Russian".
5. The Russian text is added to Veskaria's history. On Veskaria's turn, the same steps run in the other direction.
6. After every turn, the runner appends a record to the log: what was sent, what came back, the translation, timings and token counts.

**Many negotiations at once.** The runner plays about 32 negotiations in parallel threads. Each one waits for its own replies, while the vLLM servers batch the requests together on the GPU. That batching is what makes 2,000 negotiations take hours rather than weeks.

**Outside the node.** During the runs, nothing leaves the GPU node: no internet and no external AI service. The internet is needed only once, before the runs, to download the model weights. After the runs, the log files are copied to a laptop for analysis, or analysed on the cluster.

**The analysis phase** works the same way. The judge (Gemma 4 31B) and the back-translator (TranslateGemma 27B) are servers too. The analysis scripts send them every translated message in large parallel batches.

## 4. Where things run and what space they use

**Phase 1: negotiations.** One SLURM job on one node with 4 GPUs:

| GPU | Server (port) | Model | GPU memory |
|---|---|---|---|
| 0 | vLLM (8000) | Qwen3.8-27B, negotiator 1 | ~56 GB weights + working memory for parallel conversations |
| 1 | vLLM (8001) | Gemma 4 31B, negotiator 2 | ~62 GB weights + working memory |
| 2 | vLLM (8002) and NLLB service (8003) | Hy-MT2-7B and NLLB-200 3.3B | ~16 GB + ~7 GB |
| 3 | spare | second copy of a negotiator, or headroom | — |

**Phase 2: analysis.** The same node, a later job:

| GPU | Server (port) | Model |
|---|---|---|
| 0–1 | vLLM (8001) | Gemma 4 31B as error judge (split over 2 GPUs for speed) |
| 2 | vLLM (8004) | TranslateGemma 27B for back-translation |
| 3 | vLLM (8000) and in-process scorer | Qwen3.8-27B as second judge (150 messages); CometKiwi |

**GPU memory is the tight part.** Each conversation in progress needs working memory on the GPU (the "KV cache", about 1–2 GB for a long conversation with a 27–31B model). With BF16 weights, a 27–31B model leaves only 15–20 GB of an 80 GB A100 for this, so only a handful of negotiations fit at once. Two fixes, which the pilot will choose between:
- store the weights in FP8, which halves them; the A100 supports this through vLLM's weight-only kernels, with a very small quality loss;
- spread one model over two GPUs.

**Disk (project storage on the cluster):**

| What | Size |
|---|---|
| Model weights (Qwen 56, Gemma 4 62, TranslateGemma 55, Hy-MT2 16, NLLB 18, BGE-M3 and CometKiwi ~5) | ~210 GB |
| vLLM container image + a Python environment | ~20 GB |
| Run logs (~150 KB per negotiation × ~2,100) | ~0.3 GB |
| Response cache, analysis tables, figures | ~1–2 GB |
| **Total** | **~234 GB** (request 300 GB) |

- **CPU and RAM:** the runner, the retriever and the statistics are light, needing a few CPU cores and a few GB of RAM. The node has 48 cores and 1 TB of RAM.
- **Your laptop:** the code, tests and fake runs (the repo is a few MB; the virtual environment is about 0.3 GB). Later it also runs the analysis of the copied logs. NLLB-distilled-600M (~2.5 GB) can run on its CPU for local translation tests. No GPU is needed.

## 5. Is there a database? No, and here is why

Everything is stored as **plain files** in the project folder:

| What | Format | Why |
|---|---|---|
| One negotiation | `logs/<experiment>/<run-id>.jsonl`: one JSON line for the run settings (incl. both system prompts and the git version), one per turn, one for the outcome | Append-only, human-readable, easy to copy and archive; a file exists only when the run finished, which is what makes resuming safe |
| Model replies | `cache/<hash>.json`, one file per request | Re-running or re-analysing never calls a model twice |
| Analysis tables | Parquet/CSV in `results/` | Fast to load with pandas |
| Human labels | a spreadsheet (CSV/XLSX) exported for the reviewer and imported back | Easy for a non-programmer |

Why no database server:
- the data is small (well under 1 GB);
- it is written once and only read afterwards;
- a cluster job is not a good place to run a database service;
- files are trivial to version, copy, zip for the public release, and inspect by hand.

If we ever want SQL, **DuckDB** (a Python library with no server) can query the JSONL and Parquet files directly.

## 6. How it is set up, step by step

1. **Access (you and the supervisor).** OSC lab approval, an eduGAIN login, your SSH key added to the portal, and eduVPN installed on your laptop. You can then log in with `ssh <user>@<front node>`.
2. **Hugging Face (you).** A free account and a token. Accept the licences for TranslateGemma and CometKiwi; the token goes in `.env` on the cluster, never in git.
3. **Code.** On the front node, `git clone` the repository into the project folder and create the Python environment for the runner (or use the container from step 5).
4. **Model weights.** Download them once with `huggingface-cli download …` into `models/`, about 210 GB. If the GPU nodes have no internet, download on the front node; all nodes see the same storage.
5. **Container.** `apptainer pull` the official vLLM image, or build it on the laptop with Docker and upload it if the cluster can't pull. The same image serves every model.
6. **Test job.** `sbatch infra/slurm/serve_models.sbatch smoke` does the following:
   - starts the servers on their GPUs and waits until each answers its health check;
   - runs one negotiation per cell;
   - stops.
7. **Pilot and main jobs.** The same job script with `pilot`, then `main`. The runner runs inside the job next to the servers, so everything stays on `localhost`. If a job is killed or hits its time limit, resubmitting it continues where it stopped, because finished runs are skipped.
8. **Results.**
   - Logs are written to `logs/` in the project folder; we copy them to the laptop with `rsync` over eduVPN.
   - Raw logs are **not** committed to GitHub. Code, configs and summary tables are.
   - The full logs are published as a zipped release (Zenodo DOI) with the paper.

## 7. Repository layout

```
llm-negotiations-across-languages/
├── PLAN.md · ARCHITECTURE.md · CHECKLIST.md · README.md · .env.example (never commit .env)
├── configs/
│   ├── scenario/ostra.yaml            issues, options (EN/RU labels), points, BATNAs
│   ├── cells.yaml                     A1–A4, B1–B3, C1–C2 + persona pairings
│   ├── roles/{aldoria,veskaria}.{en,ru}.md      country briefs (system prompt layer)
│   ├── personas/{hawk,dove}.{en,ru}.md
│   ├── prompts/{system,turn,retry}.{en,ru}.j2 · languages.yaml · errors.yaml (retry reasons per language)
│   ├── glossary.yaml                  fixed EN→RU terms, checked automatically
│   ├── corpora/{aldoria,veskaria}/{en,ru}/*.md  briefing books (parallel files)
│   ├── models.yaml                    model servers and translators (proposed, not confirmed)
│   └── experiments/{pilot,aa-test,main}.yaml
├── src/negmt/
│   ├── scenario.py  cells.py  schemas.py  prompts.py  corpus.py  rag.py  agent.py  errors.py
│   ├── materials.py  textcheck.py  review.py      Russian materials: checks, review sheet
│   ├── protocol.py  orchestrator.py  channel.py  runner.py  cache.py  langcheck.py  logio.py
│   ├── llm/          base.py · openai_compat.py · fake.py
│   └── translation/  base.py · identity.py · roundtrip.py · nllb.py · openai_mt.py · fake.py
├── analysis/   metrics.py · stats.py · figures.py · translation_eval/
├── infra/      mt_service.py (NLLB) · slurm/serve_models.sbatch · tunnel.sh
├── docs/       requests/ (FINKI request) · russian-review/ (reviewer guide, review sheet, notes, back-translation)
├── planning/   scenario_check.py · compute_model.py
├── tests/      unit tests + end-to-end tests with fake models and translators
└── paper/      MIPRO LaTeX template · figures/ · tables/
```

## 8. Data formats

### 8.1 Agent output per turn (enforced with a JSON schema)

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
- every issue is present in `my_offer`, with valid option numbers;
- `accepted_terms` is required exactly when `decision` is `accept`;
- the language of `message` must match the agent's dialogue language.

On failure, the agent is re-asked with the error, at most twice. After that the run is marked `error`. Option numbers are language-neutral and the other side never sees them, which is how we measure comprehension.

### 8.2 Log file (`logs/<experiment>/<run-id>.jsonl`)

- **First line:** the run spec (cell, persona pairing, seed, first mover, languages, model, channel) plus `meta` with the git version and both agents' full system prompts.
- **One line per turn:**

  ```json
  {"type": "turn", "run_id": "main/qwen3.8-27b/B3-swap/P2/017", "turn": 7, "round": 4, "speaker": "veskaria",
   "model": "qwen3.8-27b", "instr_lang": "ru", "dialog_lang": "ru", "retrieved": ["veskaria/02-hydrology-study#c1"],
   "prompt_sha": "…", "turn_message": "…what the agent was shown this turn…", "raw": "…", "output": {…},
   "lang_detected": "ru", "retries": 0, "usage": {"input_tokens": 6120, "output_tokens": 402}, "ms": 2140,
   "comprehension": {"correct": 5, "wrong": 1, "missing": 0},
   "channel": {"mode": "mt", "system": "hy-mt2-7b", "src": "ru", "tgt": "en",
               "source_text": "…", "delivered_text": "…", "pivot_text": null, "ms": 840}}
  ```

- **Last line, the outcome:**

  ```json
  {"type": "outcome", "status": "deal | illusory | walk_away | timeout | error", "turns": 7, "rounds": 4,
   "terms": {"aldoria": {…}, "veskaria": {…}}, "utility": {"aldoria": 68, "veskaria": 72}, "joint": 140,
   "pareto_distance": 0, "nash_product": 621, "below_batna": []}
  ```

  `nash_product` is filled only when both sides beat their BATNA. `below_batna` lists any side that accepted a deal worse than walking away. Illusory agreements, walk-aways and timeouts pay each side its BATNA; for illusory agreements we also record the two believed deals.

### 8.3 Judge output (one per translated message)

```json
{"errors": [{"category": "semantic | pragmatic | cultural", "type": "number | omission | … | register",
             "severity": "minor | major | critical", "offer_relevant": true,
             "span_source": "…", "span_translation": "…", "note": "…"}],
 "tone": {"source": {"assertiveness": 4, "politeness": 2, "commitment": 5},
          "translation": {"assertiveness": 3, "politeness": 3, "commitment": 4}}}
```

## 9. The negotiation protocol

```
OPEN ──X: continue (counter-offer)──▶ OPEN  (other side's turn)
OPEN ──X: accept(T_x)──▶ PENDING(T_x) ──Y: accept(T_y), T_y == T_x──▶ DEAL
                                       ──Y: accept(T_y), T_y != T_x──▶ ILLUSORY  (both think they agreed)
                                       ──Y: continue──▶ OPEN       (acceptance lapses)
any state ──walk_away──▶ WALK_AWAY      after 2×10 messages ──▶ TIMEOUT      unrecoverable failure ──▶ ERROR
```

- Agents alternate, 10 messages each, and the first mover alternates by run.
- An acceptance on the last message gets one extra reply; the prompt tells that agent the limit has been reached.
- Agents know the message limit, their own scores and their own briefing. They do not know the other side's scores, and they are never told that messages are translated.

## 10. Translation channel and MT systems

| Cell type | Sender → receiver dialogue | Channel action |
|---|---|---|
| A1–A4, B1 | same language | pass through (we check the languages really are equal) |
| B2 / B3 | EN ↔ RU | translate with MT1 (NLLB) / MT2 (Hy-MT2) |
| C1 / C2 | EN → EN | EN→RU→EN round trip with MT1 / MT2 |

Every adapter implements `translate(text, src, tgt) -> TranslationResult{text, system, ms, meta}`:
- **NLLB-200 3.3B:**
  - runs behind `infra/mt_service.py`, a small web service on the GPU;
  - translates sentence by sentence (split with `razdel` for Russian and `pysbd` for English), using language codes `eng_Latn` / `rus_Cyrl`.
- **Hy-MT2-7B:** served by vLLM and called through the chat API with the prompt format from its model card. It translates one whole message, with no extra context.
- **TranslateGemma 27B** (analysis only, back-translation): its model card requires a structured chat format with language codes. We check in the setup step whether vLLM passes this through, and otherwise call it through a small script using the model card's recipe.
- **Number check:** after every translation we compare the numbers, percentages and amounts in the source and the output, handling the Russian decimal comma. A mismatch is flagged as a candidate semantic error. The check itself is built (`textcheck.numbers`, also used on the Russian materials); it is wired into the channel together with the MT adapters.

### 10.1 The Russian prompt materials

The Russian files mirror the English ones line for line (templates), paragraph for paragraph (personas, country briefs) and heading for heading (briefing documents), so every Russian segment pairs with its English source. `python -m negmt.review` then runs four steps:
- `check`: numbers, template code, glossary terms (`configs/glossary.yaml`), leftover English, no mention of translation, matching structure;
- `backtranslate`: machine back-translation with Opus-MT (ru→en), a system the study does not use, so the materials are not tuned towards our own MT systems; chrF against the English flags meaning shifts in longer segments;
- `export`: the reviewer's spreadsheet (`docs/russian-review/review-sheet.xlsx`) with flags, translator's notes, the glossary and a rendered example prompt;
- `apply`: writes the reviewer's corrections back into `configs/`, refusing rows whose draft changed after the export.

Retry messages are worded in the agent's instruction language: the agent rejects a reply with an error code (`errors.py`), and the prompt builder words it from `configs/prompts/errors.yaml`. Russian also needs plural endings after numbers (`plural_ru`) and the genitive of the country name (`name_gen` in `ostra.yaml`).

## 11. Models and settings (`configs/models.yaml`, proposed)

| Name | Server | Settings |
|---|---|---|
| `qwen3.8-27b` | vLLM :8000 | thinking off (`enable_thinking: false`), model card's non-thinking sampling (top_p 0.8, top_k 20, presence penalty 1.5), temperature 0.7, a fixed seed per run, JSON schema output |
| `gemma-4-31b` | vLLM :8001 | thinking off, temperature 0.7, seed, JSON schema output |
| `hy-mt2-7b` | vLLM :8002 | model card's translation prompt and sampling |
| `nllb-200-3.3b` | NLLB service :8003 | beam search, sentence by sentence |
| `translategemma-27b` | vLLM :8004 (analysis) | model card's structured prompt, greedy decoding |
| `ollama-small` | Ollama :11434 | small model for a laptop smoke test |

## 12. Runner

- **Grid:** `python -m negmt.runner configs/experiments/main.yaml` expands cells × persona pairings × repetitions (960 runs per model). `--dry-run` lists the plan without running anything.
- **Concurrency:** about 32 negotiations run in parallel threads, and the servers batch their requests.
- **Resume:** runs that already have a log file are skipped. A crashed run leaves no log and is redone; infrastructure failures are reported, not logged.
- **Cache:** every reply is stored by a hash of model, prompts, schema, seed and temperature, so replaying a run reproduces it exactly.
- **Settings:** server addresses come from `.env` or the SLURM job's environment.

## 13. Analysis pipeline

1. **Outcome metrics:**
   - status counts and rounds;
   - utilities, joint utility, Pareto distance, Nash product and below-BATNA flags;
   - lose-lose on the monitoring issue;
   - concession curves and DANS move types, computed from `my_offer`;
   - comprehension accuracy, language compliance, message length, politeness markers.
2. **Translation errors:**
   - extract every translated message;
   - back-translate it with TranslateGemma;
   - compute CometKiwi, chrF/BERTScore and the number check;
   - run the Gemma 4 judge (schema 8.3);
   - export a 150-message sample for the Russian reviewer and import the labels;
   - compute Cohen's kappa against the human labels, with Qwen3.8-27B as the second judge on the same 150.
3. **Linking errors to outcomes:**
   - turn-level: what happens in the 1–2 turns after an error;
   - run-level: regression of outcomes on error counts.
4. **Statistics and figures:** written straight into `paper/figures` and `paper/tables`.

## 14. Reproducibility and data release

- **Fully reproducible:** open weights with pinned revisions, fixed seeds, logged prompts and settings, the git version in every log, and cached replies.
- **Release:**
  - code and configs go on GitHub;
  - logs and annotations are zipped as a release, with a Zenodo DOI at camera-ready;
  - `.env` with the Hugging Face token is never committed.

## 15. Testing

| Level | What | Status |
|---|---|---|
| Unit | Scoring (Pareto 32 deals, Nash 68/72), protocol transitions incl. the confirmation turn, channel routing per cell, agent validation and retries, English and Russian prompts, corpus, Russian materials checks and review sheet, cache, client against a mock server, `.env` loading | 171 tests passing |
| End-to-end with fakes | A full negotiation for every cell × pairing; illusory agreement from a corrupting translator; timeout, walk-away, error, deal below BATNA; runner resume and crash reporting | passing |
| A/A | C1 with an identity translator must match A1 | pilot |
| Smoke | 1 real run per cell on the FINKI servers | Dec 1–2 |
| Pilot | ~10 runs per key cell: BATNA calibration, negotiator choice, real speed; translator comparison | Dec 3–4 |

## 16. Build plan

| When | Step | Status |
|---|---|---|
| Thu 26 Nov | 1. Repo, scenario and scoring | done |
| Thu 26 Nov | 2. Protocol, channel, orchestrator, with fakes | done |
| Thu 26 Nov | 3. English prompts, personas, country briefs, briefing books | done (approved) |
| Thu 26 Nov | 4. Model client (OpenAI-compatible), response cache | done |
| Thu 26 Nov | 9. Runner: grid, parallel runs, resume | done |
| Fri 27 – Sat 28 Nov | 5. Retrieval: BGE-M3 embeddings stored on disk, top-3 search | next |
| Fri 27 – Mon 30 Nov | 6. Translation adapters: NLLB service, Hy-MT2, number check | next |
| Fri 27 – Wed 2 Dec | 8. Russian drafts → reviewer → final | drafts and review sheet done 27 Nov; with the reviewer |
| Mon 30 Nov – Wed 2 Dec | 7. FINKI setup: container, weights, SLURM scripts | needs access |
| Thu 3 – Fri 4 Dec | 10. Pilot, translator comparison, freeze (git tag `v1.0-frozen`) | needs access |
| Sat 5 – Wed 9 Dec | 11. Analysis code, written while the main runs execute | — |

## 17. Open technical questions

- Do the GPU nodes have internet access, at least for the one-time download? Is there a storage quota?
- Can a vLLM server run inside a SLURM job? Can we build Apptainer images on the cluster?
- Does vLLM pass TranslateGemma's structured prompt through the chat API?
- The real speed and GPU-memory headroom on A100s: BF16 or FP8 weights, one or two GPUs per model.
- The Russian quality of the proposed negotiators, and Hy-MT2's real EN↔RU quality (pilot).
