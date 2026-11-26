# Guide for the Russian reviewer

Thank you for helping. This study tests how AI agents negotiate when they work in different languages and their messages pass through machine translation. Some of our AI agents read their instructions in Russian. For the comparison with English to be fair, the Russian texts must say **exactly the same thing** as the English ones, in natural, formal diplomatic Russian. Your review is what makes that claim credible in the paper.

You do not need GitHub or any programming. Everything is in one spreadsheet: **[review-sheet.xlsx](review-sheet.xlsx)** (in this folder). Fill it in and send it back; we import your corrections automatically.

## Your two tasks

| Task | When | Time |
|---|---|---|
| 1. Proofread the Russian versions of the agents' instructions and briefing documents | by **Wed 2 Dec** | 3–4 hours |
| 2. Label about 150 machine-translated negotiation messages for translation errors | **9–14 Dec**, after a 30-minute calibration call | 5–6 hours |
| (small) Check the 2–3 Russian examples quoted in the paper | by 17 Dec | 30 minutes |

## Task 1: what you will proofread (~3,400 Russian words, 205 rows)

| Text | What it is | Rows | Russian words | File in the repository |
|---|---|---|---|---|
| Country names, issue and option labels | The six negotiation issues and their options, e.g. «Срок заполнения водохранилища: 3 года» | 35 | ~140 | `configs/scenario/ostra.yaml` |
| Instructions | The agent's role, its private score table, the rules of the talks, the reply format, and the messages it gets each turn or after an invalid reply | 40 | ~520 | `configs/prompts/system.ru.j2`, `turn.ru.j2`, `retry.ru.j2`, `errors.yaml` |
| Two personas | "Hawk" (hard-line) and "Dove" (pragmatic) negotiating styles | 2 | ~170 | `configs/personas/hawk.ru.md`, `dove.ru.md` |
| Two country briefs | Each country's view of the crisis | 8 | ~400 | `configs/roles/aldoria.ru.md`, `veskaria.ru.md` |
| 24 briefing documents | Background each side can look up: hydrology studies, legal positions, finances, politics | 120 | ~2,140 | `configs/corpora/aldoria/ru/*.md`, `configs/corpora/veskaria/ru/*.md` |

**Status (27 Nov):** everything is drafted. The Russian was written from the approved English and then checked in two ways before it reaches you:
- **Automatic checks** on every row: the numbers match the English, the template code is intact, the fixed terms from the glossary are used, no English words are left, and nothing mentions translation. All rows pass.
- **Machine back-translation:** a separate translation system (Opus-MT, which the study itself does not use) translated the Russian back into English. Where the back-translation of a longer row differs a lot from the English, the row is flagged for a closer look. This also caught five ambiguous phrasings, which are already fixed. The back-translation makes its own mistakes (it calls the farmers "Hungarian" in places), so treat it only as a pointer.

### The spreadsheet

Tab **Review** has these columns:

`ID | Where | English | Russian draft | Back-translation (machine) | chrF | Flags and notes | Your corrected Russian | Comment`

- Leave **Your corrected Russian** empty when the draft is fine. Otherwise write the **full corrected text of that row** there.
- Use **Comment** for questions, doubts or alternatives.
- **Flags and notes** tells you why we are unsure: automatic flags, plus our own notes on choices we would like you to confirm. Rows marked **KEY** matter most.
- **Back-translation** and **chrF** (0–100, how close the back-translation is to the English) are only for orientation; you can ignore them.

Tab **Glossary** lists the fixed terms (please correct them too). Tab **Example prompt** shows a complete instruction text in both languages, as an agent sees it.

### What to check

1. **Same meaning.** Nothing added, dropped or softened. Numbers, units, names and dates must match exactly.
2. **Natural, formal diplomatic Russian.** The register of a foreign-ministry document. The drafts address the agent with lower-case «вы»; tell us if «Вы» would be better.
3. **Consistent terms.** Each English term always gets the same Russian term (see the glossary), so retrieval and comparisons stay consistent.
4. **The five statement formulas must stay clearly different.** This matters most: the negotiation is partly about these exact words, and their strength must decrease in this order.

   | # | English | Draft Russian |
   |---|---|---|
   | 0 | recognizes Veskaria's historical rights | признаёт исторические права Вескарии |
   | 1 | acknowledges Veskaria's historical use of the river | констатирует историческое водопользование Вескарии |
   | 2 | takes note of the positions of both parties | принимает к сведению позиции обеих сторон |
   | 3 | affirms the principle of equitable and reasonable utilization | подтверждает принцип справедливого и разумного использования |
   | 4 | no reference to the treaty | без упоминания договора |

   Russian UN texts often render both "recognizes" and "acknowledges" as «признаёт», so option 1 needs a different verb. The draft uses «констатирует»; alternatives are «отмечает» (weaker, close to option 2) or «признаёт факт исторического водопользования». Please check that each formula matches the usual Russian diplomatic or international-law wording, and that no two can be read as the same thing.
5. **Nothing about translation.** The texts must never mention translation or interpreters.
6. **Keep the code.** Anything in `{{ ... }}` or `{% ... %}` is filled in automatically, and words in straight quotes such as `"decision"` or `"accept"` are code that stays in English.

### Glossary (main terms; the full list is in the spreadsheet)

| English | Russian |
|---|---|
| Ostra Grand Dam | Большая плотина на Остре (or «Великая»?) |
| reservoir filling period | срок заполнения водохранилища |
| guaranteed minimum release (in drought years) | гарантированный минимальный попуск воды (в засушливые годы) |
| bcm (billion cubic metres) | млрд м³ |
| compensation fund | компенсационный фонд |
| discounted electricity | электроэнергия по льготной цене |
| joint technical commission | совместная техническая комиссия |
| walk-away value (points if there is no agreement) | explained in words: «столько для неё стоит выход из переговоров без соглашения» (please suggest a better term) |
| delegation | делегация |
| equitable and reasonable utilization | справедливое и разумное использование |
| (obligation not to cause) significant harm | (обязательство не наносить) значительного ущерба |
| UN Watercourses Convention | Конвенция ООН по водотокам |

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

## For the team: rebuilding and importing the sheet

```bash
pip install -e ".[review]"                 # openpyxl
python -m negmt.review check               # automatic checks (exit code 1 on errors)
python -m negmt.review export              # rebuilds review-sheet.xlsx
python -m negmt.review apply returned.xlsx # writes the reviewer's corrections into configs/
```

`backtranslate` re-runs the machine back-translation; it needs PyTorch (CPU) and the `localmt` extra and downloads the Opus-MT model (~300 MB) once. Translator's notes for the reviewer live in [notes.yaml](notes.yaml).
