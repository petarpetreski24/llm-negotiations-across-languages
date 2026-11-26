# Lost in Translation? Working plan (v3: open models on FINKI GPUs)

Draft for team review. Last updated Thu 26 Nov 2026. Paper due **Mon 21 Dec 2026** (MIPRO 2027, AIS track).

> **Status of the model choices: PROPOSED, NOT CONFIRMED.** They wait on two things: FINKI's answer to the GPU request ([docs/requests/finki-gpu-request.md](docs/requests/finki-gpu-request.md)) and the pilot on 3–4 Dec. Everything marked *(proposed)* below may still change. The $20 cloud-API plan (v2) is kept only as a fallback (§12).

## 1. Constraints

- **MIPRO 2027 dates:** the full paper is due 21 Dec 2026. Notification is 1 Feb 2027, camera-ready is 1 Mar 2027, and the conference runs 31 May to 4 Jun 2027 in Opatija.
- **Format:** 6 pages including figures and references (each extra page costs EUR 50), using the MIPRO LaTeX template, A4, with no page numbers.
- **Submission rules:** papers are plagiarism-checked before review. One author must sign the IEEE copyright form, and one must present in person.
- **Compute:** all models are open-weight and run on FCSE's GPU cluster (OSC lab), with no external AI services *(proposed)*. API cost is $0.
- **Abstract commitments** (every one must appear in the paper):
  - EN-EN and RU-RU negotiations compared with mixed EN-RU pairs connected by MT
  - instruction language and dialogue language varied separately
  - retrieval-grounded agents with personas, in a multi-issue diplomatic scenario
  - agreement rate, rounds to agreement, per-side utility and concession patterns
  - back-translation with semantic, pragmatic and cultural error categories
  - two MT systems
- **Decisions made:**
  - the paper is written in LaTeX and the code lives in a GitHub repo;
  - agents are **not** told that their messages are translated;
  - the English prompts, personas and briefings were approved on 26 Nov.

## 2. Research questions

| RQ | Question |
|---|---|
| RQ1 | In same-language pairs, which matters more: the instruction language or the dialogue language? (2x2) |
| RQ2 | Native language through MT versus English as a lingua franca: do outcomes differ? |
| RQ3 | Where is meaning lost (semantic, pragmatic, cultural), and does it predict misunderstandings, concessions or breakdowns? |
| RQ4 | Is it a language effect or an MT-system effect? (two systems) |

Hypotheses:
- H1: MT-mediated pairs agree less often, take more rounds, and misread more offers than EN-EN pairs.
- H2: with the stronger MT system, pragmatic errors outnumber semantic ones.
- H3: the weaker MT system amplifies every effect.
- H4 (exploratory): MT softens the Hawk's tone ("pragmatic drift").

## 3. Scenario: the Ostra River crisis (fictional)

Upstream **Aldoria** is about to fill a dam that is a national symbol. Downstream **Veskaria** gets 85% of its fresh water from the river, is in its third drought year, and has farmers protesting. A treaty from 1929 gave Veskaria a veto that Aldoria never accepted, and both countries face elections. If talks fail, Veskaria goes to the international court and freezes trade, and Aldoria loses World Bank financing. All escalation is legal or economic, never military.

| Issue | Options | Aldoria (weight, prefers) | Veskaria (weight, prefers) |
|---|---|---|---|
| Reservoir filling period | 3 / 5 / 7 / 10 / 15 years | 25, fast | 15, slow |
| Minimum release in drought years | 25 / 30 / 35 / 40 / 45 bcm | 20, low | 30, high |
| Compensation fund for farmers | $0 / 100M / 250M / 500M / 1000M | 25, none | 5, some |
| Discounted electricity for Veskaria | 0 / 10 / 20 / 30 / 40 % | 5, little | 25, a lot |
| Monitoring and data sharing | none / annual reports / real-time portal / joint technical commission / commission + observers | 10, joint commission | 10, joint commission (hidden shared interest) |
| Joint statement on the 1929 treaty | recognizes rights / acknowledges use / takes note / equitable utilization / no reference | 15, "equitable utilization" | 15, "recognizes rights" |

Checked with `planning/scenario_check.py` and the unit tests:
- There are 15,625 possible deals, of which 32 are Pareto-optimal.
- Splitting every issue down the middle gives 55/50 (joint 105).
- The best joint deal reaches 140.
- The Nash point is 68/72: fill in 3 years, guarantee 45 bcm in droughts, pay $0 in cash but 40% of the power as electricity, set up a joint technical commission, and "take note" in the statement.
- With walk-away values (BATNAs) of 45/45, 32.7% of deals are acceptable to both sides. The pilot tunes the BATNAs until English-English agreement lands at about 60-80%.

Translation trap: MT often renders both "recognizes" and "acknowledges" as the same Russian verb (*признавать*).

## 4. Personas

Each system prompt is built in layers: a country brief, plus a negotiating archetype, plus the task rules.

| Pairing | Aldoria | Veskaria |
|---|---|---|
| P1 | Dove | Dove |
| P2 | **Hawk** | Dove |

- **Hawk:** opens with maximal demands, concedes slowly and only for something in return, appeals to sovereignty and history, and issues legal or economic warnings, but still prefers a deal that respects its red lines.
- **Dove:** explores trade-offs, concedes when the other side concedes, and stays firm but polite.

Personas carry no nationality and are identical in both languages.

## 5. Agents and protocol

- **Turns:** agents alternate, 10 messages each (20 in total). The first mover alternates across runs, and messages are capped at about 150 words. If one side accepts on the very last message, the other side gets one extra reply to confirm.
- **RAG:** each role has 12 briefing documents (46 retrievable sections across both roles), written in that agent's instruction language. Retrieval uses BGE-M3 embeddings and returns the top 3 sections per turn. Section IDs are shared between the EN and RU versions.
- **Output per turn (JSON):**
  - `message`: the only field the other side sees
  - `my_offer`
  - `their_offer_as_understood`
  - `decision`: continue / accept / walk_away
  - `accepted_terms`
  - `plan`: at most 40 words, private
- **Agreement:** a deal counts only when both sides accept identical terms. An **illusory agreement** is when both accept but the terms differ.
- **Settings:** agents are not told about translation. Reasoning/thinking modes are off for every negotiator.

## 6. Translation layer

The channel has four modes: `none`, `MT1`, `MT2` and `roundtrip(MT)`. Every translation is logged with its source, output, system and timing.

- **MT1: NLLB-200 3.3B** *(proposed)*. Classic open translation model (Meta, 2022), applied sentence by sentence.
- **MT2: Hy-MT2-7B** *(proposed)*. LLM-based translation model (Tencent, May 2026, Apache 2.0). Tencent's earlier system won the WMT25 English→Russian constrained track.

The pair contrasts classic MT with LLM translation, and a weaker system with a stronger one. Both are open and reproducible. The pilot compares Hy-MT2-7B, TranslateGemma 27B and NLLB on about 200 English↔Russian sentences before MT2 is fixed, because Tencent's quality claims are self-reported.

## 7. Conditions

| Cell | Agent 1 instr / dialogue | Agent 2 instr / dialogue | Channel | Purpose |
|---|---|---|---|---|
| A1 | EN / EN | EN / EN | none | English baseline |
| A2 | RU / RU | RU / RU | none | Russian baseline |
| A3 | EN / RU | EN / RU | none | 2x2 design |
| A4 | RU / EN | RU / EN | none | 2x2 design |
| B1 x2 | EN / EN | RU / EN | none | lingua franca |
| B2 x2 | EN / EN | RU / RU | MT1 (NLLB) | native language + NLLB |
| B3 x2 | EN / EN | RU / RU | MT2 (Hy-MT2) | native language + Hy-MT2 |
| C1 | EN / EN | EN / EN | EN->RU->EN via MT1 | translation noise only |
| C2 | EN / EN | EN / EN | EN->RU->EN via MT2 | translation noise only |

- In the B cells, Agent 2 is the Russian-home agent. "x2" means the cell is run twice, with the Russian-home agent playing Aldoria once and Veskaria once.
- **Grid per model:** 12 cell variants x 2 persona pairings x N=40 = **960 runs**.
- **Both negotiator models run the full grid**, so there are **1,920 runs** in total. The same model always plays both sides of a negotiation.
- **A/A check:** cell C1 with a pass-through translator must behave like A1, which shows the channel itself changes nothing.

## 8. Models *(all proposed, not confirmed)*

| Role | Model | Family | Licence | Why |
|---|---|---|---|---|
| Negotiator 1 | Qwen3.8-27B, thinking off | Alibaba | Apache 2.0 | Strongest open model that fits on one GPU; Qwen leads the open models on Russia's MERA benchmark |
| Negotiator 2 | Gemma 4 31B, thinking off | Google | Apache 2.0 | Newest Google open model; strong multilingual; second family for generality |
| MT1 | NLLB-200 3.3B | Meta | CC-BY-NC (research use) | Standard classic MT baseline |
| MT2 | Hy-MT2-7B | Tencent | Apache 2.0 | Recent LLM-based MT; strong EN→RU track record |
| Back-translation | TranslateGemma 27B | Google | Gemma terms (gated) | Strong MT, independent of both forward systems |
| Error judge | Gemma 4 31B | Google | Apache 2.0 | WMT26: close to Gemini 3.6 Flash at finding translation errors, ahead of GPT-5.6 Sol |
| Second judge (150-message check) | Qwen3.8-27B | Alibaba | Apache 2.0 | A different family, for judge agreement |
| Retrieval | BGE-M3 | BAAI | MIT | Multilingual embeddings, small |
| Quality estimate | CometKiwi (wmt22) | Unbabel | CC-BY-NC-SA (gated) | Standard automatic score, reported alongside the judge |

- **Family separation:**
  - no negotiator is translated by its own family;
  - the judge never grades its own family's forward translations;
  - back-translation comes from a different system than the forward step.

  The one remaining overlap is that Gemma is both negotiator 2 and judge. That matters little, because the judge checks whether a translation kept the meaning, not who negotiated well.
- **Fallbacks:**
  - If Qwen3.8-27B deadlocks, writes poor Russian, or breaks the JSON format in the pilot, Gemma 4 31B becomes the main negotiator.
  - If Hy-MT2 underperforms, TranslateGemma becomes MT2, and Qwen3.8-27B takes over the judging (WMT26 rated a Qwen model nearly as good).
- **Rejected:**
  - Llama 4: Russian is not among its supported languages.
  - Frontier open models (Kimi, DeepSeek V4, GLM-5.x): too large for a 4-GPU node.
  - Russian-built models (GigaChat, T-pro): they would favour the Russian conditions, and Sber is under EU sanctions.
  - Hy-MT1.5: its licence excludes the EU.
- **Limitation to state:** no closed frontier model is included. The best open model is still about 14 points below the best closed one on the Artificial Analysis index.

## 9. Metrics

- **Outcomes:**
  - agreement rate (valid deals only), illusory-agreement rate and walk-away rate
  - rounds to agreement, analysed as time-to-event
  - each side's normalized utility, joint utility, distance to the Pareto frontier, and the share won by the RU-home side
  - the Nash product, only for deals both sides prefer to walking away; deals below a side's BATNA are flagged
  - lose-lose rate on the shared monitoring issue and trade-off success
- **Concessions:**
  - the utility of each side's offers over the rounds: first offer, slope and total concession
  - move types from the DANS framework (concession, selfish, fortunate, unfortunate, nice, silent)
  - reciprocity between the sides
- **Comprehension:** the share of issues where `their_offer_as_understood` matches the other side's actual `my_offer`.
- **Manipulation checks:**
  - language ID on every message
  - message length
  - politeness markers (вы/ты, hedges)
  - JSON validity rate
- **Secondary:** persona adherence across languages (does the Hawk stay a Hawk in Russian and after translation?), rated by the judge.

## 10. Translation error analysis

1. **Back-translation** of every MT-mediated message with TranslateGemma 27B.
2. **Automatic scores:**
   - CometKiwi quality estimate between the source and the translation
   - chrF/BERTScore between the original and its back-translation
   - a number-preservation check
   - the round-trip control cells (C) are scored automatically only
3. **LLM judge** (Gemma 4 31B). It sees the source, the translation and the back-translation, and labels error spans:
   - *Semantic:* number, unit or option; omission or addition; negation; entity; term (e.g., quota vs tariff); changed condition.
   - *Pragmatic:* commitment strength (must -> may), stance softened or hardened, speech act (offer / suggestion / demand), formality (вы/ты), hedges.
   - *Cultural:* literal idioms, diplomatic formulas, culture-specific references, register.

   Each label also gets a severity and an offer-relevance flag. The judge also rates the tone (assertiveness, politeness, commitment, each 1-5) of the source and of the translation, which gives the pragmatic drift.
4. **Validation:**
   - A Russian-speaking reviewer labels 150 stratified messages, and we report Cohen's kappa against the judge.
   - Qwen3.8-27B labels the same 150 messages, for agreement between judges.
5. **Linking errors to outcomes:**
   - event analysis of the 1-2 turns after an error (misread offer? changed move type?)
   - negotiation-level regression of outcomes on error counts per category

## 11. Infrastructure

Everything runs inside one SLURM job on one FINKI GPU node with 4x A100 80 GB:
- each model is its own server (vLLM, or a small service for NLLB) on a local port;
- the Python runner sends them HTTP requests;
- results are written as files to the project storage.

No internet is needed during the runs, only once beforehand to download the model weights. [ARCHITECTURE.md](ARCHITECTURE.md) §3–6 explains in plain language how the parts communicate, how much space they use, why there is no database, and how it is set up step by step.

If FINKI access is not ready by Wed 2 Dec, the fallbacks are:
- the same open models through a hosted provider (external, roughly $20–50);
- free Kaggle/Colab GPUs with smaller models (a weaker study);
- the v2 cloud-API plan (Claude Haiku replication and judge, about $10–20).

## 12. Compute, storage and cost

From `planning/compute_model.py`:

| Phase | GPU-hours on A100 (pessimistic / optimistic) |
|---|---|
| Pilot + translator comparison (~200 runs) | 2.3 / 0.8 |
| Negotiations, per model (the two models run in parallel on two GPUs) | 10.9 / 4.1 |
| Error judge (12,800 messages) | 13.5 / 5.1 |
| Back-translation (12,800 messages) | 4.6 / 1.7 |

- **Wall-clock:** about **10–27 hours** of one 4-GPU node. We request 4 GPUs for 5 days between 3 and 12 Dec, which leaves room for reruns.
- **The pessimistic case:** BF16 weights leave little GPU memory for the per-conversation working memory (the KV cache), so only a few negotiations run at once. FP8 weights, which the A100 supports via weight-only kernels, or two GPUs per model fix this. The pilot measures the real speed.
- **Disk:** about **234 GB**, of which model weights are about 210 GB, containers about 20 GB, and logs, cache and analysis about 2 GB. We request 300 GB.
- **Money:** $0 API cost. The only costs are the MIPRO registration and any extra pages.

## 13. Statistics and power

- **Unit:** one negotiation.
- **Agreement:** logistic regression on condition x persona x model, plus role and first mover; Wilson confidence intervals.
- **Rounds:** Kaplan-Meier curves and a Cox model.
- **Utility:** permutation tests and bootstrap intervals with effect sizes.
- **Concessions:** mixed model, offer utility ~ round x condition + (1|run).
- **Holm correction** across the planned contrasts:
  - A1 vs A2
  - the Block A 2x2
  - B1 vs B2/B3
  - B2 vs B3
  - C1 vs A1
  - persona x channel (pragmatic drift)
- **Power:**
  - Per model, N=40 per cell detects about 30-point agreement gaps (d of about 0.63).
  - The pooled role-swapped B cells (n=80) detect about 22 points (d of about 0.45).
  - If the two models behave alike, pooling them doubles n again.
  - Runs are free, so N can rise to 50 if the pilot shows high variance. The cost is about 20% more GPU time.

## 14. Testing and validation

- **Software (in place):** 107 pytest tests, covering:
  - scoring, Pareto and Nash; protocol rules, including the confirmation turn
  - translation routing per cell; agent validation and retries
  - end-to-end negotiations for all 12 cells x 2 pairings with fake models
  - illusory agreement from a corrupting translator; deals below BATNA
  - the vLLM/Ollama client against a mock server; response cache; runner resume and crash reporting
- **Before the pilot:** one real smoke run per cell on the FINKI servers.
- **Experimental validity:**
  - the A/A test (C1 with an identity translator must match A1)
  - language ID on every message
  - MT sanity: output non-empty, actually translated, numbers preserved
  - a sample check that each structured offer matches its message text
- **Pilot:**
  - about 10 runs per key cell, to calibrate BATNAs, choose the main negotiator and measure real speed;
  - the translator comparison (NLLB, Hy-MT2, TranslateGemma on about 200 sentences).

  Then **freeze the design and analysis plan in the repo** before the main runs.

## 15. Timeline

| Dates | Work | Milestone |
|---|---|---|
| Wed 25 - Thu 26 Nov | Design, scenario, protocol, orchestrator, EN materials, model client, runner (done) | Pipeline runs with fakes |
| Fri 27 - Mon 30 Nov | Send the FINKI request; find the Russian reviewer; RU drafts; retrieval; NLLB and Hy-MT2 adapters | Request sent; RU drafts ready for review |
| Tue 1 - Wed 2 Dec | FINKI setup (container, weights, SLURM scripts); RU review done | One real run per cell |
| Thu 3 - Fri 4 Dec | Pilot, calibration, translator comparison, negotiator choice | Design frozen; models confirmed |
| Sat 5 - Thu 10 Dec | Main runs (both models), reruns; analysis code written meanwhile | All runs done |
| Wed 9 - Mon 14 Dec | Back-translation, QE, judge, the reviewer's 150 labels, kappa | Error analysis done |
| Fri 11 - Tue 15 Dec | Statistics, figures, examples | Results frozen |
| Tue 1 - Thu 17 Dec | Writing, in parallel | Full draft Thu 17 Dec |
| Fri 18 - Sun 20 Dec | Review, trim to 6 pages, template check | **Submit Sun 20 Dec** |

If we are behind on Thu 10 Dec, cut in this order:
1. C2
2. N from 40 to 30
3. Gemma on the 8 key cells only
4. P1

## 16. People and tasks

- **Russian reviewer** (find by **Mon 30 Nov**, about 10 h in total). What they review and where it is: [docs/russian-review/README.md](docs/russian-review/README.md).
  - Proofread the Russian materials by Wed 2 Dec (3-4 h).
  - Label 150 messages between 9 and 14 Dec (5-6 h, after a 30-minute calibration).
  - Check the paper's Russian examples by 17 Dec (30 min).
- **FINKI access:** send the request (with the supervisor). Get eduVPN and an SSH key working.
- **Writing:** section owners still to be assigned.

## 17. Risks

| Risk | Mitigation |
|---|---|
| FINKI access late or denied | Decide by Wed 2 Dec; fallbacks in §11 |
| Too little GPU memory for many parallel negotiations | FP8 weights or two GPUs per model; measured in the pilot |
| Open models weak in Russian | Pilot, reviewer spot checks, swap negotiators |
| Hy-MT2 weaker than claimed | Translator comparison in the pilot; TranslateGemma as backup |
| Judge unreliable | Reviewer's 150 labels plus a second judge; message-level categories instead of exact spans |
| Agreement rate at ceiling or floor | BATNA calibration in the pilot |
| NLLB mangles numbers or formatting | Number-preservation check; such errors count as semantic errors (a finding) |
| No Russian reviewer found | Second-judge agreement plus a stated limitation |
| 6-page limit | Plan the figures early; one extra page at EUR 50 as a last resort |

## 18. Verification status

**Verified:**
- MIPRO deadline and format.
- FINKI hardware (2 nodes x 4 A100 80 GB, SLURM, eduVPN, Apptainer) and the access process (open calls, reviewed every two months).
- From the model cards: Qwen3.8-27B (Apache 2.0, thinking switchable, vLLM support), Gemma 4 31B (Apache 2.0, 35+ languages out of the box), TranslateGemma 27B (Gemma terms, gated, 55 languages), Hy-MT2-7B (Apache 2.0, Russian listed, vLLM documented), NLLB-200 (CC-BY-NC).
- WMT26 error-detection ranking (Gemma 4 31B F1 32.9 vs Gemini 3.6 Flash 34.1 vs GPT-5.6 Sol 32.0).
- vLLM structured outputs and prefix caching; FP8 weight-only on A100 through Marlin kernels.
- Llama 4 does not list Russian.
- Scenario properties (scripts and tests).

**Not yet verified:**
- The Russian quality of Qwen3.8-27B, Gemma 4 and TranslateGemma (their cards don't name Russian).
- Hy-MT2's quality claims (self-reported).
- How TranslateGemma's special prompt format works through vLLM's chat API.
- FINKI job limits, internet access and quotas.
- The real throughput on A100s.

## 19. Open items

1. Send the FINKI request and get an answer on access.
2. Confirm the model line-up after the pilot.
3. Find the Russian reviewer by Mon 30 Nov.
4. Hugging Face account and token; accept the TranslateGemma and CometKiwi licences.
5. Author list; Overleaf or local LaTeX.
6. Decide whether to cite any of our own earlier work (optional; not part of the study design).

## 20. Paper outline (6 pages including references)

| Section | Pages |
|---|---|
| Introduction | 0.6 |
| Related work | 0.6 |
| Framework and scenario (architecture figure, issue table) | 1.0 |
| Design and metrics (conditions table) | 0.8 |
| Results (outcome table, agreement/utility figure, concession curves, error-category and pragmatic-drift figure, 2-3 translated examples) | 1.6 |
| Discussion and limitations | 0.5 |
| Conclusion | 0.2 |
| References (about 20-25) | 0.6 |

## Sources

- MIPRO 2027 call for papers: https://mipro.hr/CallForPapers/tabid/176/language/en-US/Default.aspx
- MIPRO author instructions: https://mipro.hr/Uputezaautore/AuthorsInstructionsENMIPRO/tabid/191/language/en-US/Default.aspx
- FINKI OSC lab GPU cluster: https://osc-lab.finki.ukim.mk/en/usage-of-gpgpu-cluster/ and access: https://osc-lab.finki.ukim.mk/en/access-to-the-resources/
- WMT26 quality-evaluation findings: https://www2.statmt.org/wmt26/pdf/2026.wmt-1.49.pdf
- WMT25 general MT findings: https://aclanthology.org/anthology-files/pdf/wmt.real/2025.wmt-1.1.pdf
- Model cards: https://huggingface.co/Qwen/Qwen3.8-27B, https://huggingface.co/google/gemma-4-31B-it, https://huggingface.co/google/translategemma-27b-it, https://huggingface.co/tencent/Hy-MT2-7B, https://huggingface.co/facebook/nllb-200-3.3B, https://huggingface.co/meta-llama/Llama-4-Scout-17B-16E-Instruct
- vLLM FP8 on Ampere: https://github.com/vllm-project/vllm/pull/5975
- Related work: arXiv 2601.04387, 2611.00300, 2510.08098, 2609.15079; MandateBench (NeurIPS 2026); LLM-Deliberation (arXiv 2309.17234)
