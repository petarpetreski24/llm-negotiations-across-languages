import shutil

import pytest

from negmt import materials, review
from tests.conftest import ROOT

openpyxl = pytest.importorskip("openpyxl")


@pytest.fixture
def repo(tmp_path):
    shutil.copytree(ROOT / "configs", tmp_path / "configs")
    notes = tmp_path / review.NOTES_FILE
    notes.parent.mkdir(parents=True)
    shutil.copy(ROOT / review.NOTES_FILE, notes)
    return tmp_path


def test_where_names_each_place():
    seg = lambda sid: materials.Segment(sid, "text", "", "", "", 1)  # noqa: E731
    assert review.where(seg("scenario/issues.communique.1")) == "Option 1 of issue 'communique'"
    assert review.where(seg("prompts/system:L17")) == "Instructions, line 17"
    assert review.where(seg("roles/aldoria:P2")) == "Country brief: Aldoria, paragraph 2"
    assert review.where(seg("corpora/veskaria/07-monitoring:H2")) == "Veskaria briefing 07: heading 2"


def test_export_then_apply_corrections(repo):
    sheet = repo / "sheet.xlsx"
    review.export(repo, sheet)
    wb = openpyxl.load_workbook(sheet)
    assert wb.sheetnames == ["Read me", "Review", "Glossary", "Example prompt"]
    ws = wb["Review"]
    header = [c.value for c in ws[1]]
    assert header == review.COLUMNS
    rows = {r[0].value: r for r in ws.iter_rows(min_row=2)}
    assert len(rows) == len(materials.collect(repo))
    assert "KEY" in rows["scenario/issues.communique.1"][header.index("Flags and notes")].value

    fix, draft = header.index("Your corrected Russian"), header.index("Russian draft")
    rows["scenario/issues.communique.1"][fix].value = "отмечает историческое водопользование Вескарии"
    rows["corpora/aldoria/01-dam-project:H1"][fix].value = "О проекте"
    rows["prompts/system:L14"][fix].value = rows["prompts/system:L14"][draft].value.strip().replace("вариант", "вариант №")
    wb.save(sheet)

    changed, problems = review.apply(repo, sheet)
    assert problems == [] and sorted(changed) == sorted(
        ["scenario/issues.communique.1", "corpora/aldoria/01-dam-project:H1", "prompts/system:L14"])
    assert 'ru: "отмечает историческое водопользование Вескарии"' in (repo / "configs/scenario/ostra.yaml").read_text(encoding="utf-8")
    assert "\n## О проекте\n" in (repo / "configs/corpora/aldoria/ru/01-dam-project.md").read_text(encoding="utf-8")
    line14 = (repo / "configs/prompts/system.ru.j2").read_text(encoding="utf-8").split("\n")[13]
    assert line14.startswith("   - вариант № {{ opt.id }}")  # indentation kept
    assert materials.collect(repo)  # files still line up

    _, problems = review.apply(repo, sheet)  # the drafts in the sheet are now out of date
    assert len(problems) == 3


def test_example_sheet_shows_both_languages(repo):
    sheet = repo / "sheet.xlsx"
    review.export(repo, sheet)
    ws = openpyxl.load_workbook(sheet)["Example prompt"]
    english = "\n".join(str(c.value) for c in ws["A"] if c.value)
    russian = "\n".join(str(c.value) for c in ws["B"] if c.value)
    assert "head of the delegation of the Republic of Aldoria" in english
    assert "глава делегации Республики Альдория" in russian
