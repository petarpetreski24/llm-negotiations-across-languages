"""Briefing corpora: load per-role documents and split them into retrieval chunks.

Layout: configs/corpora/<role>/<lang>/<NN-topic>.md, one "# Title" and one or more
"## Section" headings per file. Each section is a chunk with ID "<role>/<stem>#c<n>".
The EN and RU versions of a file must have the same stem and the same number of
sections, so a chunk ID points to the same content in both languages.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Chunk:
    id: str
    role: str
    lang: str
    doc: str
    title: str
    heading: str
    text: str

    def as_excerpt(self) -> str:
        return f"{self.title}: {self.heading}. {self.text}"


def load_corpus(root: str | Path, role: str, lang: str) -> list[Chunk]:
    folder = Path(root) / role / lang
    if not folder.is_dir():
        raise FileNotFoundError(folder)
    chunks: list[Chunk] = []
    for path in sorted(folder.glob("*.md")):
        chunks.extend(_split(path, role, lang))
    if not chunks:
        raise ValueError(f"no chunks in {folder}")
    return chunks


def _split(path: Path, role: str, lang: str) -> list[Chunk]:
    title, heading, body, out = "", None, [], []

    def flush():
        if heading is not None:
            text = " ".join(" ".join(body).split())
            if not text:
                raise ValueError(f"{path}: empty section '{heading}'")
            out.append(Chunk(f"{role}/{path.stem}#c{len(out) + 1}", role, lang, path.stem, title, heading, text))

    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith("## "):
            flush()
            heading, body = line[3:].strip(), []
        elif line.startswith("# "):
            title = line[2:].strip()
        elif heading is not None:
            body.append(line.strip())
    flush()
    if not title or not out:
        raise ValueError(f"{path}: needs a '# Title' and at least one '## Section'")
    return out


def check_parallel(root: str | Path, role: str, langs: tuple[str, str] = ("en", "ru")) -> list[str]:
    """Return problems that would break cross-language chunk alignment (empty list = aligned)."""
    a, b = (load_corpus(root, role, lang) for lang in langs)
    ids_a, ids_b = [c.id for c in a], [c.id for c in b]
    problems = []
    for cid in sorted(set(ids_a) - set(ids_b)):
        problems.append(f"{cid} missing in {langs[1]}")
    for cid in sorted(set(ids_b) - set(ids_a)):
        problems.append(f"{cid} missing in {langs[0]}")
    return problems
