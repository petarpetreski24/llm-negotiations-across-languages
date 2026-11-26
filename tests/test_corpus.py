import re

import pytest

from negmt.corpus import check_parallel, load_corpus
from tests.conftest import ROOT

CORPORA = ROOT / "configs" / "corpora"


@pytest.mark.parametrize("role", ["aldoria", "veskaria"])
def test_english_corpus_loads(role):
    chunks = load_corpus(CORPORA, role, "en")
    assert len({c.doc for c in chunks}) == 12
    assert 20 <= len(chunks) <= 30
    assert len({c.id for c in chunks}) == len(chunks)
    for c in chunks:
        assert c.id.startswith(f"{role}/") and re.search(r"#c\d+$", c.id)
        assert 15 <= len(c.text.split()) <= 120, c.id


@pytest.mark.parametrize("role", ["aldoria", "veskaria"])
def test_briefings_never_reveal_points(role):
    for c in load_corpus(CORPORA, role, "en"):
        assert not re.search(r"\bpoints?\b", c.text, re.I), c.id
        assert "BATNA" not in c.text


def test_chunk_splitting(tmp_path):
    d = tmp_path / "aldoria" / "en"
    d.mkdir(parents=True)
    (d / "01-x.md").write_text("# Title\n\n## First\nOne two\nthree.\n\n## Second\nFour.\n", encoding="utf-8")
    chunks = load_corpus(tmp_path, "aldoria", "en")
    assert [c.id for c in chunks] == ["aldoria/01-x#c1", "aldoria/01-x#c2"]
    assert chunks[0].text == "One two three."
    assert chunks[0].as_excerpt() == "Title: First. One two three."


def test_parallel_check_reports_missing_chunks(tmp_path):
    for lang, body in [("en", "## A\nx\n## B\ny\n"), ("ru", "## A\nx\n")]:
        d = tmp_path / "aldoria" / lang
        d.mkdir(parents=True)
        (d / "01-x.md").write_text("# T\n" + body, encoding="utf-8")
    assert check_parallel(tmp_path, "aldoria") == ["aldoria/01-x#c2 missing in ru"]


def test_malformed_document_rejected(tmp_path):
    d = tmp_path / "aldoria" / "en"
    d.mkdir(parents=True)
    (d / "01-x.md").write_text("no headings here\n", encoding="utf-8")
    with pytest.raises(ValueError):
        load_corpus(tmp_path, "aldoria", "en")
