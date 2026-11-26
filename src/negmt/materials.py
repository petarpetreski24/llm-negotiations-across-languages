"""The prompt materials as aligned English/Russian segments, and the checks run on them.

A segment is the smallest unit the Russian reviewer corrects: a scenario label, one
template line, one error message, one paragraph of a persona or country brief, or one
title, heading or paragraph of a briefing document. Each segment records the file and
line of its Russian text, so corrections can be written back (`negmt.review apply`).

The Russian files mirror the English ones: same line count for templates, same paragraph
count for personas and briefs, same headings for briefing documents. `collect()` raises
`StructureError` when they drift apart.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

import yaml

from negmt import textcheck


class StructureError(ValueError):
    pass


@dataclass
class Segment:
    id: str
    kind: str  # label | template | error | persona | role | title | heading | text
    en: str
    ru: str
    path: str  # Russian file, relative to the repo root
    line: int  # 1-based line of the Russian text
    quoted: bool = False  # the Russian text sits inside "double quotes" in a YAML file


@dataclass
class Finding:
    level: str  # error | warn | info
    message: str


@dataclass
class GlossaryTerm:
    term_en: str
    term_ru: str
    en: str  # regex on the English segment
    ru: str  # regex the Russian segment must then match
    note: str = ""
    _en_re: re.Pattern = field(init=False, repr=False)
    _ru_re: re.Pattern = field(init=False, repr=False)

    def __post_init__(self):
        self._en_re = re.compile(self.en, re.I)
        self._ru_re = re.compile(self.ru, re.I)

    def violated(self, en: str, ru: str) -> bool:
        return bool(self._en_re.search(en)) and not self._ru_re.search(ru)


def load_glossary(path: str | Path) -> list[GlossaryTerm]:
    return [GlossaryTerm(**t) for t in yaml.safe_load(Path(path).read_text(encoding="utf-8"))]


# ---------------------------------------------------------------- collection


def collect(repo: str | Path) -> list[Segment]:
    repo = Path(repo)
    cfg = repo / "configs"
    segs: list[Segment] = []
    segs += _scenario(repo, cfg / "scenario" / "ostra.yaml")
    for name in ("system", "turn", "retry"):
        segs += _template(repo, cfg / "prompts" / f"{name}.en.j2", cfg / "prompts" / f"{name}.ru.j2", f"prompts/{name}")
    segs += _errors(repo, cfg / "prompts" / "errors.yaml")
    for folder, kind in (("personas", "persona"), ("roles", "role")):
        for en_path in sorted((cfg / folder).glob("*.en.md")):
            stem = en_path.name[: -len(".en.md")]
            segs += _paragraphs(repo, en_path, en_path.with_name(f"{stem}.ru.md"), f"{folder}/{stem}", kind)
    for en_path in sorted((cfg / "corpora").glob("*/en/*.md")):
        role = en_path.parent.parent.name
        segs += _document(repo, en_path, en_path.parent.parent / "ru" / en_path.name, f"corpora/{role}/{en_path.stem}")
    ids = [s.id for s in segs]
    if len(ids) != len(set(ids)):
        raise StructureError("duplicate segment ids")
    return segs


def _rel(repo: Path, path: Path) -> str:
    return path.relative_to(repo).as_posix()


def _lines(path: Path) -> list[str]:
    if not path.exists():
        raise StructureError(f"missing file {path}")
    return path.read_text(encoding="utf-8").splitlines()


def yaml_quote(text: str) -> str:
    return '"' + text.replace("\\", "\\\\").replace('"', '\\"') + '"'


def _find_line(lines: list[str], needle: str, path: Path, start: int = 0) -> int:
    hits = [i for i, line in enumerate(lines) if i >= start and needle in line]
    if len(hits) != 1:
        raise StructureError(f"{path}: expected one line with {needle!r}, found {len(hits)}")
    return hits[0] + 1


def _scenario(repo: Path, path: Path) -> list[Segment]:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    lines = _lines(path)
    segs = []

    def add(sid: str, kind: str, en: str, ru: str):
        if ru == en and not re.search(r"[^\W\d_]", ru):  # "0%", "10%": nothing to translate
            return
        segs.append(Segment(sid, kind, en, ru, _rel(repo, path), _find_line(lines, f"ru: {yaml_quote(ru)}", path), True))

    for rid, role in data["roles"].items():
        add(f"scenario/roles.{rid}.name", "label", role["name"]["en"], role["name"]["ru"])
        if "name_gen" in role:
            add(f"scenario/roles.{rid}.name_gen", "label", role["name"]["en"], role["name_gen"]["ru"])
    for issue in data["issues"]:
        add(f"scenario/issues.{issue['id']}", "label", issue["label"]["en"], issue["label"]["ru"])
        for k, opt in enumerate(issue["options"]):
            add(f"scenario/issues.{issue['id']}.{k}", "label", opt["en"], opt["ru"])
    return segs


def _has_text(line: str) -> bool:
    return bool(re.search(r"[^\W\d_]", textcheck.strip_jinja(line, filler=" ")))


def _template(repo: Path, en_path: Path, ru_path: Path, sid: str) -> list[Segment]:
    en_lines, ru_lines = _lines(en_path), _lines(ru_path)
    if len(en_lines) != len(ru_lines):
        raise StructureError(f"{ru_path}: {len(ru_lines)} lines, the English template has {len(en_lines)}")
    segs = []
    for i, (en, ru) in enumerate(zip(en_lines, ru_lines), start=1):
        if _has_text(en):
            segs.append(Segment(f"{sid}:L{i}", "template", en, ru, _rel(repo, ru_path), i))
        elif en != ru:
            raise StructureError(f"{ru_path}:{i}: code-only line differs from the English template")
    return segs


def _errors(repo: Path, path: Path) -> list[Segment]:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    lines = _lines(path)
    if set(data["en"]) != set(data["ru"]):
        raise StructureError(f"{path}: English and Russian error codes differ")
    ru_start = lines.index("ru:")
    return [
        Segment(f"prompts/errors:{code}", "error", data["en"][code], data["ru"][code], _rel(repo, path),
                _find_line(lines, f"  {code}: ", path, start=ru_start), True)
        for code in data["en"]
    ]


def _paragraphs(repo: Path, en_path: Path, ru_path: Path, sid: str, kind: str) -> list[Segment]:
    en = [(i, t) for i, t in enumerate(_lines(en_path), start=1) if t.strip()]
    ru = [(i, t) for i, t in enumerate(_lines(ru_path), start=1) if t.strip()]
    if len(en) != len(ru):
        raise StructureError(f"{ru_path}: {len(ru)} paragraphs, the English file has {len(en)}")
    return [Segment(f"{sid}:P{n}", kind, e, r, _rel(repo, ru_path), line)
            for n, ((_, e), (line, r)) in enumerate(zip(en, ru), start=1)]


def _kind(line: str) -> tuple[str, str]:
    if line.startswith("## "):
        return "heading", line[3:].strip()
    if line.startswith("# "):
        return "title", line[2:].strip()
    return "text", line.strip()


def _document(repo: Path, en_path: Path, ru_path: Path, sid: str) -> list[Segment]:
    en = [_kind(t) for t in _lines(en_path) if t.strip()]
    ru = [(i, *_kind(t)) for i, t in enumerate(_lines(ru_path), start=1) if t.strip()]
    if [k for k, _ in en] != [k for _, k, _ in ru]:
        raise StructureError(f"{ru_path}: headings and paragraphs do not match the English document")
    segs, counters = [], {"heading": 0, "text": 0}
    for (kind, en_text), (line, _, ru_text) in zip(en, ru):
        if kind == "title":
            suffix = "T"
        else:
            counters[kind] += 1
            suffix = f"{'H' if kind == 'heading' else 'P'}{counters[kind]}"
        segs.append(Segment(f"{sid}:{suffix}", kind, en_text, ru_text, _rel(repo, ru_path), line))
    return segs


# ---------------------------------------------------------------- checks


def check(seg: Segment, glossary: list[GlossaryTerm]) -> list[Finding]:
    out: list[Finding] = []
    if not seg.ru.strip():
        return [Finding("error", "the Russian text is empty")]
    missing, extra = textcheck.number_mismatch(seg.en, seg.ru)
    if missing or extra:
        out.append(Finding("error", f"numbers differ: missing {missing or '-'}, extra {extra or '-'}"))
    if seg.kind == "template":
        en_vars, en_tags = textcheck.jinja_parts(seg.en)
        ru_vars, ru_tags = textcheck.jinja_parts(seg.ru)
        if en_vars != ru_vars or en_tags != ru_tags:
            out.append(Finding("error", f"template code differs: {sorted(en_vars)} {en_tags} vs {sorted(ru_vars)} {ru_tags}"))
    for field_name in ("{field}", "{issue}", "{option}", "{language}"):
        if seg.kind == "error" and (field_name in seg.en) != (field_name in seg.ru):
            out.append(Finding("error", f"placeholder {field_name} must appear in both languages"))
    latin = textcheck.latin_words(seg.ru)
    if latin:
        out.append(Finding("error", f"English words left in the Russian: {', '.join(latin)}"))
    if textcheck.mentions_translation(seg.ru, "ru") or textcheck.mentions_translation(seg.en, "en"):
        out.append(Finding("error", "mentions translation (agents must not be told about it)"))
    if seg.id.startswith("corpora/") and re.search(r"балл", seg.ru, re.I):
        out.append(Finding("error", "a briefing document mentions points («балл»)"))
    for term in glossary:
        if term.violated(seg.en, seg.ru):
            out.append(Finding("warn", f"glossary: '{term.term_en}' is usually «{term.term_ru}»"))
    en_words, ru_words = len(textcheck.strip_jinja(seg.en).split()), len(textcheck.strip_jinja(seg.ru).split())
    if en_words >= 12 and not 0.6 <= ru_words / en_words <= 1.4:
        out.append(Finding("warn", f"length differs a lot ({en_words} English words, {ru_words} Russian)"))
    words = textcheck.number_words(seg.en)
    if words:
        out.append(Finding("info", f"numbers in words, check by eye: {', '.join(words)}"))
    return out


def check_all(repo: str | Path) -> dict[str, list[Finding]]:
    repo = Path(repo)
    glossary = load_glossary(repo / "configs" / "glossary.yaml")
    return {s.id: check(s, glossary) for s in collect(repo)}
