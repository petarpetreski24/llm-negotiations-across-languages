import shutil

import pytest
import yaml

from negmt import materials
from negmt.materials import Segment, StructureError
from tests.conftest import ROOT


@pytest.fixture(scope="module")
def segments():
    return materials.collect(ROOT)


@pytest.fixture(scope="module")
def glossary():
    return materials.load_glossary(ROOT / "configs" / "glossary.yaml")


def test_collects_every_russian_text(segments):
    ids = {s.id for s in segments}
    assert {"prompts/system:L1", "prompts/turn:L2", "prompts/retry:L1", "prompts/errors:wrong_language",
            "scenario/roles.aldoria.name_gen", "scenario/issues.communique.1", "personas/hawk:P1",
            "roles/veskaria:P4", "corpora/veskaria/12-economy:P2"} <= ids
    assert sum(s.kind == "title" for s in segments) == 24
    assert sum(s.kind == "text" for s in segments) == 48
    assert not any(s.en == "0%" for s in segments)  # nothing to translate


def test_each_segment_points_at_its_russian_line(segments):
    for s in segments:
        line = (ROOT / s.path).read_text(encoding="utf-8").split("\n")[s.line - 1]
        assert (materials.yaml_quote(s.ru) if s.quoted else s.ru) in line, s.id


def test_drafts_pass_all_automatic_checks():
    """Errors and warnings must be fixed; if the reviewer changes a term, update configs/glossary.yaml."""
    results = materials.check_all(ROOT)
    problems = {sid: [f.message for f in fs if f.level in ("error", "warn")] for sid, fs in results.items()}
    assert {sid: msgs for sid, msgs in problems.items() if msgs} == {}


def test_reviewer_notes_refer_to_real_segments(segments):
    notes = yaml.safe_load((ROOT / "docs" / "russian-review" / "notes.yaml").read_text(encoding="utf-8"))
    assert set(notes) <= {s.id for s in segments}
    assert all(notes[f"scenario/issues.communique.{k}"].startswith("KEY") for k in range(5))


def test_statement_formulas_are_quoted_verbatim_in_the_briefings(scenario):
    """The briefing documents quote the five joint-statement options exactly as the score table names them."""
    communique = next(i for i in scenario.issues if i.id == "communique")
    for role in ("aldoria", "veskaria"):
        text = (ROOT / "configs" / "corpora" / role / "ru" / "06-treaty-1929.md").read_text(encoding="utf-8")
        for opt in communique.options[:4]:
            assert f"«{opt['ru']}»" in text, (role, opt["ru"])
    assert len({opt["ru"].split()[0] for opt in communique.options[:4]}) == 4  # four different verbs


def _copy(tmp_path):
    shutil.copytree(ROOT / "configs", tmp_path / "configs")
    return tmp_path


def test_template_lines_must_stay_aligned(tmp_path):
    repo = _copy(tmp_path)
    path = repo / "configs" / "prompts" / "turn.ru.j2"
    path.write_text(path.read_text(encoding="utf-8") + "Лишняя строка.\n", encoding="utf-8")
    with pytest.raises(StructureError):
        materials.collect(repo)


def test_documents_must_keep_their_headings(tmp_path):
    repo = _copy(tmp_path)
    path = repo / "configs" / "corpora" / "aldoria" / "ru" / "01-dam-project.md"
    path.write_text(path.read_text(encoding="utf-8").replace("## Проект\n", ""), encoding="utf-8")
    with pytest.raises(StructureError):
        materials.collect(repo)


def test_checks_catch_broken_drafts(glossary):
    def messages(seg, level):
        return [f.message for f in materials.check(seg, glossary) if f.level == level]

    wrong_number = Segment("corpora/x/01:P1", "text", "The fund holds USD 250 million.", "Фонд располагает 205 млн долларов США.", "f", 1)
    assert any("numbers differ" in m for m in messages(wrong_number, "error"))
    lost_code = Segment("prompts/turn:L4", "template", "Message {{ round_no }} of {{ max_rounds }}.", "Сообщение {{ round_no }}.", "f", 1)
    assert any("template code differs" in m for m in messages(lost_code, "error"))
    leak = Segment("corpora/x/01:P2", "text", "The reservoir is large.", "Водохранилище большое, это стоит баллов; текст переведён.", "f", 1)
    assert len(messages(leak, "error")) == 2  # points and translation
    english_left = Segment("roles/x:P1", "role", "A guaranteed release.", "Гарантированный release.", "f", 1)
    assert any("English words" in m for m in messages(english_left, "error"))
    off_glossary = Segment("corpora/x/02:P1", "text", "A joint technical commission would help.", "Помогла бы совместная комиссия экспертов.", "f", 1)
    assert messages(off_glossary, "warn") == ["glossary: 'joint technical commission' is usually «совместная техническая комиссия»"]
    assert materials.check(Segment("x", "text", "Text.", "  ", "f", 1), glossary)[0].level == "error"
