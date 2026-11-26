# Lost in Translation? Working plan (v2, $20 API budget)

Draft for team review. Last updated Wed 25 Nov 2026. Paper due **Mon 21 Dec 2026** (MIPRO 2027, AIS track).

## 1. Constraints

- **MIPRO 2027 dates:** the full paper is due 21 Dec 2026. Notification is 1 Feb 2027, camera-ready is 1 Mar 2027, and the conference runs 31 May to 4 Jun 2027 in Opatija.
- **Format:** 6 pages including figures and references (each extra page costs EUR 50), using the MIPRO LaTeX template, A4, with no page numbers.
- **Submission rules:** papers are plagiarism-checked before review, so we cite the CIIT 2026 paper and do not reuse its text. One author must sign the IEEE copyright form, and one must present in person.
- **Budget:** $20 for all paid APIs. Everything open-weight runs on FINKI's GPU cluster (OSC lab).
- **Abstract commitments** (every one must appear in the paper):
  - EN-EN and RU-RU negotiations compared with mixed EN-RU pairs connected by MT
  - instruction language and dialogue language varied separately
  - retrieval-grounded agents with personas, in a multi-issue diplomatic scenario
  - agreement rate, rounds to agreement, per-side utility and concession patterns
  - back-translation with semantic, pragmatic and cultural error categories
  - two MT systems
- **Decisions made:** the paper is written in LaTeX, the code lives in a GitHub repo, and agents are **not** told that their messages are translated.

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

Checked with `planning/scenario_check.py`:
- There are 15,625 possible deals, of which 32 are Pareto-optimal.
- Splitting every issue down the middle gives 55/50 (joint 105).
- The best joint deal reaches 140.
- The Nash point is 68/72: fill in 3 years, guarantee 45 bcm in droughts, pay $0 in cash but 40% of the power as electricity, set up a joint technical commission, and "take note" in the statement.
- With walk-away values (BATNAs) of 45/45, 32.7% of deals are acceptable to both sides. The pilot tunes the BATNAs until English-English agreement lands at about 60-80%.

Translation trap: MT often renders both "recognizes" and "acknowledges" as the same Russian verb (*признавать*).

## 4. Personas

Personas reuse the CIIT layering: a country briefing, plus an archetype, plus task rules.

| Pairing | Aldoria | Veskaria |
|---|---|---|
| P1 | Dove | Dove |
| P2 | **Hawk** | Dove |

- **Hawk:** opens with maximal demands, concedes slowly and only for something in return, appeals to sovereignty and history, and issues legal or economic warnings, but still prefers a deal that respects its red lines.
- **Dove:** explores trade-offs, concedes when the other side concedes, and stays firm but polite.

Personas carry no nationality and are identical in both languages.

## 5. Agents and protocol

- **Turns:** agents alternate, 10 turns each (20 messages). The first mover alternates across runs, and messages are capped at about 150 words.
- **RAG:** each role has 10-15 briefing documents (priorities, red lines, rival hydrology studies, legal opinions, domestic pressure) written in that agent's instruction language. Retrieval uses BGE-M3 embeddings and returns the top 3 chunks per turn. Chunk IDs are shared between the EN and RU versions.
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

The channel has four modes: `none`, `MT1`, `MT2`, and `roundtrip(MT)`. Every translation is logged with its source, output, system and timing.

- **MT1: NLLB-200 3.3B.** Classic open neural MT, applied sentence by sentence. It runs on a FINKI GPU and is free.
- **MT2: TranslateGemma 27B.** An open LLM-based translator. It runs on a FINKI GPU and is free.

The pair contrasts classic MT with LLM translation and a weaker system with a stronger one. Both are open and reproducible.

## 7. Conditions

| Cell | Agent 1 instr / dialogue | Agent 2 instr / dialogue | Channel | Purpose |
|---|---|---|---|---|
| A1 | EN / EN | EN / EN | none | English baseline |
| A2 | RU / RU | RU / RU | none | Russian baseline |
| A3 | EN / RU | EN / RU | none | 2x2 design |
| A4 | RU / EN | RU / EN | none | 2x2 design |
| B1 x2 | EN / EN | RU / EN | none | lingua franca |
| B2 x2 | EN / EN | RU / RU | MT1 (NLLB) | native language + NLLB |
| B3 x2 | EN / EN | RU / RU | MT2 (TranslateGemma) | native language + TranslateGemma |
| C1 | EN / EN | EN / EN | EN->RU->EN via NLLB | translation noise only |
| C2 | EN / EN | EN / EN | EN->RU->EN via TranslateGemma | translation noise only |

- In the B cells, Agent 2 is the Russian-home agent. "x2" means the cell is run twice, with the Russian-home agent playing Aldoria once and Veskaria once.
- **Main grid:** 12 cells x 2 persona pairings x N=40 = **960 runs** with Qwen3.8-27B. This is free on FINKI.
- **Replication:** Claude Haiku 5.5 on A1, A2, B1x2, B2x2 and B3x2 with P2 only, N=30, giving **240 runs** (about $4).

## 8. Models

| Role | Model | Where | Cost |
|---|---|---|---|
| Main negotiator | Qwen3.8-27B (open weights, Apache 2.0, Aug 2026), BF16, thinking off | FINKI, vLLM | $0 |
| Replication negotiator | Claude Haiku 5.5, thinking off | Anthropic API | ~$4 |
| MT1 | NLLB-200 3.3B | FINKI | $0 |
| MT2 | TranslateGemma 27B | FINKI | $0 |
| Back-translation | Claude Haiku 5.5 (independent of both MT systems) | API, batch | ~$1 |
| Error judge | Claude Haiku 5.5, low effort | API, batch | ~$3 |
| Judge check | Claude Sonnet 5.5 on the 150 human-labelled messages | API, batch | ~$1.4 |
| Embeddings and QE | BGE-M3, CometKiwi (gated on Hugging Face), chrF/BERTScore | FINKI or laptop | $0 |

The pilot can rule out Qwen3.8-27B if it deadlocks (as Qwen3-32B did in the CIIT paper), writes poor Russian, or breaks the JSON format. In that case **Gemma 4 31B** negotiates instead and **Qwen3.8-27B replaces TranslateGemma** as the LLM translator, so the same model family never sits on both sides of the channel. Llama 4 is out because its model card does not list Russian.

## 9. Metrics

- **Outcomes:**
  - agreement rate (valid deals only), illusory-agreement rate and walk-away rate
  - rounds to agreement, analysed as time-to-event
  - each side's normalized utility, joint utility, Nash product, distance to the Pareto frontier, and the share won by the RU-home side
  - lose-lose rate on the shared monitoring issue, trade-off success, and deals below BATNA
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
- **Secondary:** persona adherence across languages, reusing the CIIT consistency and strategic-coherence rubric.

## 10. Translation error analysis

1. **Back-translation** of every MT-mediated message with Claude Haiku 5.5, which is independent of both MT systems.
2. **Automatic scores:**
   - CometKiwi quality estimate between the source and the translation
   - chrF/BERTScore between the original and its back-translation
   - the round-trip control cells (C) are scored automatically only
3. **LLM judge** (Haiku 5.5, batch). It sees the source, the translation and the back-translation, and labels error spans:
   - *Semantic:* number, unit or option; omission or addition; negation; entity; term (e.g., quota vs tariff); changed condition.
   - *Pragmatic:* commitment strength (must -> may), stance softened or hardened, speech act (offer / suggestion / demand), formality (вы/ты), hedges.
   - *Cultural:* literal idioms, diplomatic formulas, culture-specific references, register.

   Each label also gets a severity and an offer-relevance flag. The judge also rates the tone (assertiveness, politeness, commitment, each 1-5) of the source and of the translation, which gives the pragmatic drift.
4. **Validation:**
   - A Russian validator labels 150 stratified messages, and we report Cohen's kappa against the Haiku judge.
   - Sonnet 5.5 labels the same 150 messages.
   - If Haiku's kappa is clearly below Sonnet's, we re-judge the offer-bearing messages with Sonnet using the budget reserve (about $9 per 1,000 messages).
5. **Linking errors to outcomes:**
   - event analysis of the 1-2 turns after an error (misread offer? changed move type?)
   - negotiation-level regression of outcomes on error counts per category

## 11. Infrastructure (FINKI OSC lab)

- **Hardware:** 2 GPU nodes, each with 4x A100 80 GB, 2x EPYC 7413 and 1 TB RAM. Jobs run under SLURM; access is through eduVPN plus SSH to the front node, and software runs in Apptainer/Singularity images built from NVIDIA NGC images.
- **Access:** through open calls reviewed every two months. **First check whether the CIIT account is still active.** Publications must include the lab's acknowledgement sentence.
- **Request:** 2-4 A100 GPUs for about 5 days between 3 and 12 Dec, about 250 GB of storage, and jobs of up to 48 h.
- **Layout:** vLLM runs in an Apptainer container. GPU0 serves Qwen3.8-27B; GPU1 serves TranslateGemma 27B plus NLLB, BGE-M3 and CometKiwi.
- **Runtime:** the full Qwen grid should take about 5-8 h with roughly 32 negotiations in parallel.
- **Unknowns to ask the lab:**
  - job and GPU limits
  - **outbound internet from the GPU nodes** (needed for the Anthropic API; otherwise we use an SSH tunnel)
  - whether a server can run inside a job
  - whether we can build images on the cluster
- **Fallback if there is no FINKI access by Wed 2 Dec:**
  - a cheap hosted Qwen model (~$5 for the grid)
  - NLLB distilled-1.3B on the laptop CPU
  - Claude Haiku 5.5 as the LLM translator
  - no Haiku replication

  Total about $10-12. This is less reproducible, but it fits the budget.

## 12. Budget ($20)

From `planning/cost_model.py`. It assumes 20 messages per negotiation, about 6k input and 450 output tokens per negotiator call, and Claude list prices as of 2026-11-03.

| Item | Expected | +50% tokens | x2 tokens |
|---|---|---|---|
| Haiku replication (240 runs) | $3.96 | $5.94 | $7.92 |
| Back-translation (8,800 msgs, batch) | $1.14 | $1.72 | $2.29 |
| Error judge (8,800 msgs, batch) | $3.08 | $4.62 | $6.16 |
| Sonnet judge check (150 msgs) | $1.35 | $2.02 | $2.70 |
| Pilot | $0.43 | $0.65 | $0.87 |
| **Total** | **$9.97** | **$14.95** | **$19.94** |

Spend controls:
- Buy $20 of prepaid Anthropic credits and leave auto-reload off.
- The runner tracks spend from usage counts.
- Envelopes: **reserve $8 for back-translation, the judge and the check before any Haiku runs.** Haiku runs stop at $8.

These options do **not** fit the budget:
- Sonnet as the main judge (~$79)
- Haiku on the full grid (~$16)
- a commercial MT1 such as DeepL or Azure (4.5M characters, beyond the free tiers)

The $20 covers APIs only. The Russian validator would be unpaid (acknowledged, or a co-author), and the MIPRO registration fee is separate.

## 13. Statistics and power

- **Unit:** one negotiation.
- **Agreement:** logistic regression on condition x persona, plus role and first mover; Wilson confidence intervals.
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
  - N=40: detects about 30-point agreement gaps, or d of about 0.63.
  - Pooled B cells (n=80): about 22 points, or d of about 0.45.
  - Haiku replication (N=30; pooled n=60): about 25 points, or d of about 0.51. It checks the direction of effects; it is not a standalone test.
  - Qwen runs are free, so N can rise to 50 if pilot variance is high. That adds only about $0.6 of judging.

## 14. Testing and validation

- **Software:**
  - pytest for utilities, Pareto and Nash; agreement and illusory-agreement detection; JSON validation and retries; turn order and termination; translation routing; deterministic retrieval
  - fake-LLM and fake-translator end-to-end runs at zero cost
  - one real smoke run per cell
- **Experimental validity:**
  - an A/A test: EN-EN with a pass-through translator must match plain EN-EN
  - language ID on every message
  - MT sanity: output non-empty, actually translated, numbers preserved
  - a sample check that each structured offer matches its message text
- **Pilot:** about 10 runs per key cell to calibrate BATNAs, choose the negotiator and measure real token use. Then **freeze the design and analysis plan in the repo** before the main runs.

## 15. Timeline

| Dates | Work | Milestone |
|---|---|---|
| Wed 25 - Mon 30 Nov | Confirm FINKI access, the Russian validator, the Anthropic account and the CIIT code. Build the scenario files, personas, EN prompts and briefings, the LaTeX skeleton and the bibliography. | All blockers cleared |
| Fri 27 Nov - Wed 2 Dec | Extend the CIIT code and add tests; set up vLLM/Apptainer on FINKI; draft RU materials, then have the validator check them | Pipeline passing |
| Thu 3 - Fri 4 Dec | Pilot, calibration, negotiator choice | Design frozen |
| Sat 5 - Thu 10 Dec | Main Qwen grid (about 1 GPU-day), Haiku replication (capped), reruns | All runs done |
| Wed 9 - Mon 14 Dec | Back-translation, QE, judge batches, human sample and kappa, Sonnet check | Error analysis done |
| Fri 11 - Tue 15 Dec | Statistics, figures, examples | Results frozen |
| Tue 1 - Thu 17 Dec | Writing, in parallel with the above | Full draft Thu 17 Dec |
| Fri 18 - Sun 20 Dec | Review, trim to 6 pages, template check | **Submit Sun 20 Dec** |

If we are behind on Thu 10 Dec, cut in this order: C2, then N from 40 to 30, then the Haiku replication, then P1.

## 16. People and tasks

- **Russian validator** (find by **Mon 30 Nov**, about 10 h in total):
  - check the RU prompts, personas, option labels and briefings by Wed 2 Dec (3-4 h)
  - label 150 messages between 9 and 14 Dec (5-6 h, after a 30-minute calibration)
  - check the paper's RU examples by 17 Dec (30 min)

  Where to look: the UKIM Faculty of Philology (Slavic studies), professional translators, Russian-speaking students, or remote freelancers. If nobody is found, we rely on agreement with a second judge and state the limitation.
- **Infrastructure:** the CIIT co-author who ran Ollama (account, machine, code).
- **Writing:** section owners still to be assigned.

## 17. Risks

| Risk | Mitigation |
|---|---|
| FINKI access late | Decide by Wed 2 Dec; the fallback costs about $10-12 |
| Spend overrun | Prepaid $20, budget envelopes, runner guard |
| Haiku judge too weak | Sonnet check on 150 messages; reserve for re-judging offer messages |
| Open models weak in Russian | Pilot, validator spot checks, Gemma 4 as backup |
| Agreement rate at ceiling or floor | BATNA calibration in the pilot |
| NLLB mangles numbers or formatting | Number-preservation check; such errors count as semantic errors (a finding) |
| No Russian validator | Second-judge agreement plus a stated limitation |
| 6-page limit | Plan the figures early; one extra page at EUR 50 as a last resort |

## 18. Verification status

**Verified:**
- MIPRO deadline and format.
- FINKI hardware and access process.
- The Gemma 4 and Qwen3.8-27B model cards: Apache 2.0, about 256K context, thinking can be switched off, vLLM support.
- Llama 4 does not list Russian.
- TranslateGemma comes in 4B/12B/27B and covers 55 languages.
- Claude prices: Haiku 5.5 at $0.10/$0.50, Sonnet 5.5 at $2/$10 per M tokens, batch at -50%.
- Scenario properties and costs (scripts in `planning/`).

**Not yet verified:**
- Russian quality of Qwen3.8-27B, Gemma 4 and TranslateGemma (their cards don't list languages by name), to be checked in the pilot.
- FINKI limits and internet access.
- Haiku 5.5's minimum cacheable prompt length. The budget assumes no caching, so caching would only save money.
- The Anthropic minimum credit purchase.
- The CometKiwi and TranslateGemma licence terms.

**Changes from earlier chat estimates:**
- MT1 is now NLLB, not DeepL/Azure.
- The judge is now Haiku 5.5 with a Sonnet check, instead of Sonnet throughout.
- Claude is now a 240-run replication, not a full second grid.
- The earlier $150-250 estimate assumed paid MT and a Sonnet judge.

## 19. Open items

1. Where is the CIIT code?
2. FINKI: is the account active, what are the limits, is there internet on the GPU nodes?
3. A Russian validator, by Mon 30 Nov.
4. An Anthropic account with $20 of prepaid credits; a Hugging Face account for the gated models.
5. Who is on the author list? Overleaf or local LaTeX?

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
- FINKI OSC lab GPU cluster: https://osc-lab.finki.ukim.mk/en/usage-of-gpgpu-cluster/
- FINKI OSC lab access: https://osc-lab.finki.ukim.mk/en/access-to-the-resources/
- Qwen3.8-27B: https://huggingface.co/Qwen/Qwen3.8-27B
- Gemma 4 31B: https://huggingface.co/google/gemma-4-31B-it
- Llama 4 Scout: https://huggingface.co/meta-llama/Llama-4-Scout-17B-16E-Instruct
- TranslateGemma: https://blog.google/innovation-and-ai/technology/developers-tools/translategemma/
- Related work: arXiv 2601.04387, 2611.00300, 2510.08098, 2609.15079; MandateBench (NeurIPS 2026); LLM-Deliberation (arXiv 2309.17234)
