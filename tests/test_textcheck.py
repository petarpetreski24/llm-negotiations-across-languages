import pytest

from negmt import textcheck as tc


def test_numbers_are_normalised_across_languages():
    en = "USD 6.8 billion, 1,200 people, 85 percent, the 1929 treaty, option 0"
    ru = "6,8 млрд долларов США, 1 200 человек, 85 процентов, договор 1929 года, вариант 0"
    assert tc.numbers(en, "en") == tc.numbers(ru, "ru")


def test_number_mismatch_reports_both_sides():
    assert tc.number_mismatch("35 bcm in 2023", "45 млрд м³ в 2023 году") == (["35"], ["45"])


def test_superscript_and_lists_are_handled():
    assert tc.numbers("25 млрд м³", "ru") == {"25": 1}
    assert sorted(tc.numbers("варианты 3, 5 и 7", "ru").elements()) == ["3", "5", "7"]
    assert tc.numbers("10.0 and 10", "en") == {"10": 2}


def test_chrf_bounds():
    assert tc.chrf("the same text", "the same text") == pytest.approx(100)
    assert tc.chrf("abc", "xyz") == 0
    assert 0 < tc.chrf("the reservoir fills in five years", "the reservoir is filled in five years") < 100


def test_jinja_parts_ignore_filters_and_the_genitive_alias():
    en = "   - option {{ opt.id }}: {{ opt.label }} — {{ opt.points }} points"
    ru = '   - вариант {{ opt.id }}: {{ opt.label }} — {{ opt.points }} {{ opt.points | plural_ru("балл", "балла", "баллов") }}'
    assert tc.jinja_parts(en) == tc.jinja_parts(ru)
    assert tc.jinja_parts("of the {{ country }}")[0] == tc.jinja_parts("делегации {{ country_gen }}")[0]
    assert tc.jinja_parts("{%- if x  %}a")[1] == ["if x"]
    assert tc.strip_jinja("Сообщение {{ round_no }} из {{ max_rounds }}{% if a %}") == "Сообщение [X] из [X]"


def test_latin_words_skip_code_and_placeholders():
    assert tc.latin_words('укажите в поле "decision" значение "accept"; JSON-объект; null') == []
    assert tc.latin_words("поле {field} пустое; {{ country_gen }}") == []
    assert tc.latin_words("гарантированный release воды") == ["release"]


def test_translation_mentions():
    assert tc.mentions_translation("Ваше сообщение будет переведено", "ru")
    assert tc.mentions_translation("через переводчика", "ru")
    assert not tc.mentions_translation("перевес сил на стороне Альдории", "ru")
    assert tc.mentions_translation("Messages are translated", "en")


def test_number_words():
    assert tc.number_words("in thirty days, within Six months, a third of workers") == ["thirty", "six", "third"]
