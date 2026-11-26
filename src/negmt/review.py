"""Russian materials review: check, back-translate, export the reviewer's spreadsheet, apply corrections.

    python -m negmt.review check                  automatic checks; exit code 1 on errors
    python -m negmt.review backtranslate          Russian -> English with a local MT model the study
                                                  does not use (Opus-MT), for orientation and flags
    python -m negmt.review export                 docs/russian-review/review-sheet.xlsx
    python -m negmt.review apply RETURNED.xlsx    write the reviewer's corrections into configs/

export and apply need the `review` extra (openpyxl); backtranslate needs the `localmt` extra.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

import yaml

from negmt import materials, textcheck
from negmt.materials import Finding, Segment

REPO = Path(__file__).resolve().parents[2]
REVIEW_DIR = Path("docs") / "russian-review"
BT_FILE = REVIEW_DIR / "backtranslation.json"
SHEET_FILE = REVIEW_DIR / "review-sheet.xlsx"
NOTES_FILE = REVIEW_DIR / "notes.yaml"
BT_MODEL = "Helsinki-NLP/opus-mt-ru-en"
LOW_CHRF = 40.0  # back-translations scoring below this get a "look closely" flag ...
MIN_WORDS_FOR_CHRF = 8  # ... unless the English is this short: a synonym in a heading scores low

COLUMNS = ["ID", "Where", "English", "Russian draft", "Back-translation (machine, for orientation)", "chrF",
           "Flags and notes", "Your corrected Russian", "Comment"]
EDITABLE = ("Your corrected Russian", "Comment")


# ---------------------------------------------------------------- helpers


def where(seg: Segment) -> str:
    area, _, part = seg.id.partition(":")
    if area.startswith("scenario/"):
        bits = area.split(".")
        if bits[0] == "scenario/roles":
            return "Country name (genitive)" if bits[-1] == "name_gen" else "Country name"
        return f"Option {bits[2]} of issue '{bits[1]}'" if len(bits) == 3 else f"Issue '{bits[1]}'"
    if area == "prompts/errors":
        return f"Error message '{part}'"
    if area.startswith("prompts/"):
        name = {"prompts/system": "Instructions", "prompts/turn": "Turn message", "prompts/retry": "Retry message"}[area]
        return f"{name}, line {part[1:]}"
    if area.startswith("personas/"):
        return {"personas/hawk": "Persona: Hawk (hard-line)", "personas/dove": "Persona: Dove (pragmatic)"}.get(area, area)
    if area.startswith("roles/"):
        return f"Country brief: {area.split('/')[1].title()}, paragraph {part[1:]}"
    _, role, doc = area.split("/")
    piece = {"T": "title", "H": f"heading {part[1:]}", "P": f"paragraph {part[1:]}"}[part[0]]
    return f"{role.title()} briefing {doc[:2]}: {piece}"


def load_notes(repo: Path, segs: list[Segment]) -> dict[str, str]:
    path = repo / NOTES_FILE
    notes = yaml.safe_load(path.read_text(encoding="utf-8")) if path.exists() else {}
    stale = set(notes or {}) - {s.id for s in segs}
    if stale:
        raise ValueError(f"{path}: notes for unknown segments {sorted(stale)}")
    return notes or {}


def load_backtranslation(repo: Path) -> dict:
    path = repo / BT_FILE
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {"segments": {}}


# ---------------------------------------------------------------- commands


def run_check(repo: Path) -> int:
    results = materials.check_all(repo)
    counts: dict[str, int] = defaultdict(int)
    for sid, findings in results.items():
        for f in findings:
            counts[f.level] += 1
            if f.level in ("error", "warn"):
                print(f"{f.level.upper():5} {sid}: {f.message}")
    print(f"{len(results)} segments: {counts['error']} errors, {counts['warn']} warnings, {counts['info']} notes")
    return 1 if counts["error"] else 0


def backtranslate(repo: Path, model_name: str = BT_MODEL, batch: int = 8) -> dict:
    import torch
    from transformers import MarianMTModel, MarianTokenizer

    segs = materials.collect(repo)
    tok = MarianTokenizer.from_pretrained(model_name)
    model = MarianMTModel.from_pretrained(model_name).eval()
    sources = [textcheck.strip_jinja(s.ru) for s in segs]
    order = sorted(range(len(sources)), key=lambda i: len(sources[i]))  # similar lengths batch well
    back: dict[int, str] = {}
    with torch.inference_mode():
        for start in range(0, len(order), batch):
            idx = order[start:start + batch]
            enc = tok([sources[i] for i in idx], return_tensors="pt", padding=True, truncation=True, max_length=512)
            gen = model.generate(**enc, num_beams=4, max_new_tokens=400)
            for i, text in zip(idx, tok.batch_decode(gen, skip_special_tokens=True)):
                back[i] = text
    data = {
        "model": model_name,
        "date": dt.date.today().isoformat(),
        "note": "Machine back-translation of the Russian drafts, for orientation only. chrF compares it with the English source.",
        "segments": {
            s.id: {"ru": s.ru, "back": back[i], "chrf": round(textcheck.chrf(back[i], textcheck.strip_jinja(s.en)), 1)}
            for i, s in enumerate(segs)
        },
    }
    out = repo / BT_FILE
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(data, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    return data


def low_backtranslation(seg: Segment, chrf: float | None) -> bool:
    return chrf is not None and chrf < LOW_CHRF and len(textcheck.strip_jinja(seg.en).split()) >= MIN_WORDS_FOR_CHRF


def flag_text(findings: list[Finding], low_chrf: float | None, note: str | None) -> str:
    """low_chrf: the score, if the back-translation should be flagged."""
    lines = [f"{f.level.upper()}: {f.message}" for f in findings if f.level in ("error", "warn")]
    if low_chrf is not None:
        lines.append(f"Back-translation differs from the English (chrF {low_chrf:.0f}): please look closely.")
    lines += [f.message[0].upper() + f.message[1:] for f in findings if f.level == "info"]
    if note:
        lines.append(f"Note: {note}")
    return "\n".join(lines)


READ_ME = [
    "Russian review of the prompt materials",
    "",
    "Thank you for helping. AI agents in this study negotiate in English or Russian. The Russian texts below must say exactly what the English says, in natural, formal diplomatic Russian.",
    "",
    "What to do (tab 'Review'):",
    "1. Read the English and the Russian draft in each row.",
    "2. If the Russian is fine, leave 'Your corrected Russian' empty.",
    "3. If not, write the full corrected Russian text of that row in 'Your corrected Russian'. Use 'Comment' for questions or explanations.",
    "4. Rows marked KEY matter most: the five wordings of the joint statement must stay clearly different from each other.",
    "",
    "Please keep unchanged:",
    "- anything in {{ ... }} or {% ... %}: it is filled in automatically;",
    "- words in straight quotes such as \"decision\" or \"accept\": they are code and stay in English;",
    "- all numbers.",
    "Use the formal «вы». The texts must never mention translation or interpreters.",
    "",
    "Columns you can ignore: 'Back-translation' is a machine translation of the Russian draft back into English, and 'chrF' says how close it is to the original English (0-100). They are only there to point at places where the meaning may have shifted.",
    "",
    "Other tabs: 'Glossary' lists the fixed terms (please correct them too); 'Example prompt' shows a complete instruction text in both languages as an agent sees it.",
    "",
    "Please return the file by Wednesday 2 December.",
]


def export(repo: Path, out: Path) -> int:
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Font, PatternFill

    segs = materials.collect(repo)
    glossary = materials.load_glossary(repo / "configs" / "glossary.yaml")
    notes = load_notes(repo, segs)
    bt = load_backtranslation(repo)["segments"]

    wrap = Alignment(wrap_text=True, vertical="top")
    bold = Font(bold=True)
    head_fill = PatternFill("solid", fgColor="DDDDDD")
    edit_fill = PatternFill("solid", fgColor="D9EAD3")
    warn_fill = PatternFill("solid", fgColor="FFF2CC")
    error_fill = PatternFill("solid", fgColor="F4CCCC")
    key_fill = PatternFill("solid", fgColor="FCE5CD")

    wb = Workbook()
    ws = wb.active
    ws.title = "Read me"
    ws.column_dimensions["A"].width = 120
    for i, text in enumerate(READ_ME, start=1):
        cell = ws.cell(row=i, column=1, value=text)
        cell.alignment = wrap
    ws["A1"].font = Font(bold=True, size=14)

    ws = wb.create_sheet("Review")
    widths = [34, 26, 55, 55, 45, 7, 40, 55, 35]
    for col, (name, width) in enumerate(zip(COLUMNS, widths), start=1):
        cell = ws.cell(row=1, column=col, value=name)
        cell.font, cell.alignment = bold, wrap
        cell.fill = edit_fill if name in EDITABLE else head_fill
        ws.column_dimensions[cell.column_letter].width = width
    ws.freeze_panes = "C2"
    flagged = 0
    for r, seg in enumerate(segs, start=2):
        findings = materials.check(seg, glossary)
        entry = bt.get(seg.id)
        back, score = "", None
        if entry and entry["ru"] == seg.ru:
            back, score = entry["back"], entry["chrf"]
        elif entry:
            back = "(the Russian changed after the back-translation was made)"
        note = notes.get(seg.id)
        low = low_backtranslation(seg, score)
        flags = flag_text(findings, score if low else None, note)
        values = [seg.id, where(seg), seg.en, seg.ru, back, score, flags, None, None]
        for c, value in enumerate(values, start=1):
            ws.cell(row=r, column=c, value=value).alignment = wrap
        levels = {f.level for f in findings}
        if "error" in levels:
            ws.cell(row=r, column=7).fill = error_fill
        elif "warn" in levels or low:
            ws.cell(row=r, column=7).fill = warn_fill
        if levels & {"error", "warn"} or low:
            flagged += 1
        if note and note.startswith("KEY"):
            ws.cell(row=r, column=1).fill = key_fill
            ws.cell(row=r, column=1).font = bold
    ws.auto_filter.ref = f"A1:{ws.cell(row=1, column=len(COLUMNS)).column_letter}{len(segs) + 1}"

    ws = wb.create_sheet("Glossary")
    for col, (name, width) in enumerate(zip(["English", "Russian", "Note", "Your correction", "Comment"],
                                            [40, 45, 70, 40, 35]), start=1):
        cell = ws.cell(row=1, column=col, value=name)
        cell.font, cell.alignment = bold, wrap
        cell.fill = edit_fill if name in ("Your correction", "Comment") else head_fill
        ws.column_dimensions[cell.column_letter].width = width
    for r, term in enumerate(glossary, start=2):
        for c, value in enumerate([term.term_en, term.term_ru, term.note], start=1):
            ws.cell(row=r, column=c, value=value).alignment = wrap
    ws.freeze_panes = "A2"

    _example_sheet(wb.create_sheet("Example prompt"), repo, wrap, bold, head_fill)

    out.parent.mkdir(parents=True, exist_ok=True)
    wb.save(out)
    return flagged


def _example_sheet(ws, repo: Path, wrap, bold, head_fill) -> None:
    from negmt.corpus import load_corpus
    from negmt.errors import InvalidReply
    from negmt.prompts import TemplatePromptBuilder
    from negmt.scenario import Scenario
    from negmt.schemas import AgentSpec

    scenario = Scenario.from_yaml(repo / "configs" / "scenario" / "ostra.yaml")
    builder = TemplatePromptBuilder(repo / "configs")
    specs = {lang: AgentSpec(role="aldoria", persona="hawk", instr_lang=lang, dialog_lang=lang, model="example")
             for lang in ("en", "ru")}
    incoming = {"en": "We propose to fill the reservoir over ten years and to guarantee 45 bcm in drought years.",
                "ru": "Мы предлагаем заполнять водохранилище в течение десяти лет и гарантировать 45 млрд м³ в засушливые годы."}
    blocks: dict[str, list[tuple[str, str]]] = {}
    for lang, spec in specs.items():
        excerpt = load_corpus(repo / "configs" / "corpora", "aldoria", lang)[0].as_excerpt()
        blocks[lang] = [
            ("Instructions (system prompt), Aldoria, Hawk persona", builder.system_prompt(spec, scenario, 10)),
            ("First turn", builder.turn_message(spec, 1, 10, None, [])),
            ("A later turn, with a briefing excerpt and the other side's message",
             builder.turn_message(spec, 3, 10, incoming[lang], [excerpt])),
            ("Extra turn after the message limit", builder.turn_message(spec, 11, 10, incoming[lang], [])),
            ("Retry after a reply in the wrong language",
             builder.retry_message(spec, InvalidReply("wrong_language", expected=lang, detected="mixed"))),
        ]
    for col, (name, width) in enumerate(zip(["English", "Russian"], [90, 90]), start=1):
        cell = ws.cell(row=1, column=col, value=name)
        cell.font, cell.fill = bold, head_fill
        ws.column_dimensions[cell.column_letter].width = width
    row = 2
    for (title, en), (_, ru) in zip(blocks["en"], blocks["ru"]):
        ws.cell(row=row, column=1, value=title).font = bold
        row += 1
        en_lines, ru_lines = en.split("\n"), ru.split("\n")
        for i in range(max(len(en_lines), len(ru_lines))):
            for c, lines in ((1, en_lines), (2, ru_lines)):
                ws.cell(row=row, column=c, value=lines[i] if i < len(lines) else None).alignment = wrap
            row += 1
        row += 1
    ws.freeze_panes = "A2"


def _edit_line(line: str, seg: Segment, new: str) -> str:
    if seg.quoted:
        old_q = materials.yaml_quote(seg.ru)
        if line.count(old_q) != 1:
            raise ValueError(f"{seg.id}: cannot find the draft on line {seg.line} of {seg.path}")
        return line.replace(old_q, materials.yaml_quote(new))
    if seg.kind == "title":
        return f"# {new.strip()}"
    if seg.kind == "heading":
        return f"## {new.strip()}"
    if line != seg.ru:
        raise ValueError(f"{seg.id}: line {seg.line} of {seg.path} is not the draft")
    indent = re.match(r"\s*", line).group()
    return new if new[:1].isspace() else indent + new


def apply(repo: Path, sheet: Path) -> tuple[list[str], list[str]]:
    """Write the reviewer's corrections into the Russian files. Returns (changed ids, problems)."""
    from openpyxl import load_workbook

    ws = load_workbook(sheet, read_only=True)["Review"]
    rows = ws.iter_rows(values_only=True)
    header = list(next(rows))
    i_id, i_draft, i_new = (header.index(n) for n in ("ID", "Russian draft", "Your corrected Russian"))
    segs = {s.id: s for s in materials.collect(repo)}
    edits: dict[str, dict[int, tuple[Segment, str]]] = defaultdict(dict)
    changed, problems = [], []
    for row in rows:
        sid, draft, new = row[i_id], row[i_draft], row[i_new]
        if not sid or new is None or not str(new).strip():
            continue
        new = str(new).rstrip()
        seg = segs.get(sid)
        if seg is None:
            problems.append(f"{sid}: unknown ID")
        elif seg.ru != draft:
            problems.append(f"{sid}: the Russian file changed after the sheet was made; not applied")
        elif new.strip() != seg.ru.strip():
            edits[seg.path][seg.line] = (seg, new)
    for rel, by_line in edits.items():
        path = repo / rel
        lines = path.read_text(encoding="utf-8").split("\n")
        for line_no, (seg, new) in by_line.items():
            lines[line_no - 1] = _edit_line(lines[line_no - 1], seg, new)
            changed.append(seg.id)
        path.write_text("\n".join(lines), encoding="utf-8", newline="\n")
    return changed, problems


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m negmt.review", description=__doc__.split("\n")[0])
    parser.add_argument("--repo", type=Path, default=REPO)
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("check")
    bt = sub.add_parser("backtranslate")
    bt.add_argument("--model", default=BT_MODEL)
    ex = sub.add_parser("export")
    ex.add_argument("--out", type=Path, default=None)
    ap = sub.add_parser("apply")
    ap.add_argument("sheet", type=Path)
    args = parser.parse_args(argv)
    repo = args.repo.resolve()
    if hasattr(sys.stdout, "reconfigure"):  # Windows consoles default to cp1252
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    if args.cmd == "check":
        return run_check(repo)
    if args.cmd == "backtranslate":
        data = backtranslate(repo, args.model)
        scores = sorted(s["chrf"] for s in data["segments"].values())
        low = sum(1 for s in scores if s < LOW_CHRF)
        print(f"{len(scores)} segments back-translated with {args.model}; median chrF {scores[len(scores) // 2]:.1f}; "
              f"{low} below {LOW_CHRF:.0f}")
        return 0
    if args.cmd == "export":
        out = args.out or repo / SHEET_FILE
        flagged = export(repo, out)
        print(f"wrote {out} ({flagged} rows flagged)")
        return 0
    changed, problems = apply(repo, args.sheet)
    for p in problems:
        print("SKIPPED", p)
    print(f"applied {len(changed)} corrections; now run: python -m negmt.review check")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
