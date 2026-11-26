# Guide for the Russian reviewer

Thank you for helping. This study tests how AI agents negotiate when they work in different languages and their messages pass through machine translation. Some of our AI agents read their instructions in Russian. For the comparison with English to be fair, the Russian texts must say **exactly the same thing** as the English ones, in natural, formal diplomatic Russian. Your review is what makes that claim credible in the paper.

You do not need GitHub or any programming. You will receive one **review spreadsheet** with English and Russian side by side.

## Your two tasks

| Task | When | Time |
|---|---|---|
| 1. Proofread the Russian versions of the agents' instructions and briefing documents | by **Wed 2 Dec** | 3–4 hours |
| 2. Label about 150 machine-translated negotiation messages for translation errors | **9–14 Dec**, after a 30-minute calibration call | 5–6 hours |
| (small) Check the 2–3 Russian examples quoted in the paper | by 17 Dec | 30 minutes |

## Task 1: what you will proofread (~3,800 words)

| Text | What it is | Size | File in the repository |
|---|---|---|---|
| Issue and option labels | The six negotiation issues and their options, e.g. «Срок заполнения водохранилища: 3 года» | 36 short labels | `configs/scenario/ostra.yaml` (already drafted) |
| Instructions template | Tells the agent its role, its private score table, the rules of the talks and the reply format | ~600 words | `configs/prompts/system.ru.j2`, `turn.ru.j2`, `retry.ru.j2` |
| Two personas | "Hawk" (hard-line) and "Dove" (pragmatic) negotiating styles | ~200 words | `configs/personas/hawk.ru.md`, `dove.ru.md` |
| Two country briefs | Each country's view of the crisis | ~500 words | `configs/roles/aldoria.ru.md`, `veskaria.ru.md` |
| 24 briefing documents | Background each side can look up: hydrology studies, legal positions, finances, politics | ~2,300 words | `configs/corpora/aldoria/ru/*.md`, `configs/corpora/veskaria/ru/*.md` |

**Status (26 Nov):** only the labels exist in Russian so far. The other files will be drafted next, from the approved English. We will produce two independent machine drafts, compare them, and mark every place where they disagree, so you can focus on those. You will get everything in one spreadsheet with these columns:

`ID | English | Russian draft | Flag (why we're unsure) | Your corrected Russian | Comment`

Leave "Your corrected Russian" empty when the draft is fine.

### What to check

1. **Same meaning.** Nothing added, dropped or softened. Numbers, units, names and dates must match exactly.
2. **Natural, formal diplomatic Russian.** Use the formal «вы» throughout and the register of a foreign-ministry document.
3. **Consistent terms.** Each English term must always get the same Russian term (see the glossary below), so retrieval and comparisons stay consistent.
4. **The six statement formulas must stay clearly different.** This matters most: the negotiation is partly about these exact words.

   | English | Draft Russian |
   |---|---|
   | recognizes Veskaria's historical rights | признаёт исторические права Вескарии |
   | acknowledges Veskaria's historical use of the river | отмечает историческое водопользование Вескарии |
   | takes note of the positions of both parties | принимает к сведению позиции обеих сторон |
   | affirms the principle of equitable and reasonable utilization | подтверждает принцип справедливого и разумного использования |
   | no reference to the treaty | без упоминания договора |

   Please check that each matches the usual Russian diplomatic or international-law wording, and that no two can be read as the same thing.
5. **Nothing about translation.** The instructions must never mention translation or interpreters.

### Glossary (draft, please correct)

| English | Russian |
|---|---|
| reservoir filling period | срок заполнения водохранилища |
| guaranteed minimum release (in drought years) | гарантированный минимальный попуск воды (в засушливые годы) |
| bcm (billion cubic metres) | млрд м³ |
| compensation fund | фонд компенсаций |
| discounted electricity | электроэнергия по льготной цене |
| joint technical commission | совместная техническая комиссия |
| walk-away value (points if there is no agreement) | баллы при отсутствии соглашения (please suggest a better term) |
| delegation | делегация |
| equitable and reasonable utilization | справедливое и разумное использование |
| no significant harm | непричинение значительного ущерба |

## Task 2: labelling messages (later)

You will see about 150 short negotiation messages. Each comes with its source text (English or Russian), its machine translation, and an English back-translation. For each message you mark:
- whether meaning was lost, using three categories with examples on one page:
  - **semantic:** wrong number, option, negation or term;
  - **pragmatic:** tone or commitment changed, e.g. "must" became "could", or a demand became a suggestion; or the formality changed;
  - **cultural:** idioms or diplomatic formulas rendered literally;
- how serious it is: minor, major or critical.

We hold a 30-minute call with 10 worked examples first. Your labels are compared with an AI judge's, to show how far the judge can be trusted.

## Credit

You will be thanked in the paper's acknowledgements, or offered co-authorship if your contribution goes further (e.g. shaping the error categories). Please tell us which you prefer.
