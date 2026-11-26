import itertools

import pytest

from negmt import langcheck, textcheck
from negmt.cells import build_run_spec
from negmt.errors import CODES, InvalidReply
from negmt.llm.fake import FakeNegotiator
from negmt.orchestrator import run_negotiation
from negmt.prompts import TemplatePromptBuilder, plural_ru
from negmt.schemas import AgentSpec
from negmt.translation.fake import TaggingTranslator
from tests.conftest import ROOT


@pytest.fixture(scope="module")
def builder():
    return TemplatePromptBuilder(ROOT / "configs")


@pytest.mark.parametrize("role, persona, dialog", list(itertools.product(["aldoria", "veskaria"], ["hawk", "dove"], ["en", "ru"])))
def test_english_system_prompt(builder, scenario, role, persona, dialog):
    spec = AgentSpec(role=role, persona=persona, instr_lang="en", dialog_lang=dialog, model="x")
    text = builder.system_prompt(spec, scenario, max_rounds=10)
    other = "veskaria" if role == "aldoria" else "aldoria"

    assert scenario.roles[role].name["en"] in text
    assert "walk-away value of 45 points" in text
    assert "at most 10 messages" in text
    assert f"written in {'English' if dialog == 'en' else 'Russian'}" in text
    for issue in scenario.issues:
        assert issue.label["en"] in text
        for k, opt in enumerate(issue.options):
            assert f"option {k}: {opt['en']} — {issue.points[role][k]} points" in text
    # the other side's score table must not leak
    leaked = [f"option {k}: {o['en']} — {issue.points[other][k]} points"
              for issue in scenario.issues for k, o in enumerate(issue.options)
              if issue.points[other][k] != issue.points[role][k]]
    assert not any(line in text for line in leaked)
    assert "translat" not in text.lower()  # agents are never told about translation
    assert ("hard-line" in text) == (persona == "hawk")


def test_turn_messages(builder):
    spec = AgentSpec(role="aldoria", persona="dove", instr_lang="en", dialog_lang="en", model="x")
    opening = builder.turn_message(spec, 1, 10, None, [])
    assert "You open the talks" in opening and "<<<" not in opening
    reply = builder.turn_message(spec, 3, 10, "We propose X.", ["Doc: A. text"])
    assert "Message 3 of 10" in reply and "<<<We propose X.>>>" in reply and "[1] Doc: A. text" in reply
    assert "could not be used: bad" in builder.retry_message(spec, "bad")


def test_full_run_with_real_templates(builder, scenario, cells):
    variants, pairings = cells
    v = next(v for v in variants if v.name == "C1")
    spec = build_run_spec(experiment="t", variant=v, pairing_name="P2", pairing=pairings["P2"], rep=0,
                          model="fake", mt_systems={"MT1": "m1", "MT2": "m2"})
    llms = {r: FakeNegotiator(scenario.issue_ids, "en", scenario.nash_point().deal) for r in scenario.roles}
    res = run_negotiation(spec, scenario, llms, builder, {"m1": TaggingTranslator("m1"), "m2": TaggingTranslator("m2")})
    assert res.outcome.status == "deal"


def test_confirmation_turn_after_limit(builder):
    spec = AgentSpec(role="aldoria", persona="dove", instr_lang="en", dialog_lang="en", model="x")
    text = builder.turn_message(spec, 11, 10, "We accept.", [])
    assert "used all 10 messages" in text and "Message 11 of 10" not in text


# ---------------------------------------------------------------- Russian


@pytest.mark.parametrize("role, persona, dialog", list(itertools.product(["aldoria", "veskaria"], ["hawk", "dove"], ["en", "ru"])))
def test_russian_system_prompt(builder, scenario, role, persona, dialog):
    spec = AgentSpec(role=role, persona=persona, instr_lang="ru", dialog_lang=dialog, model="x")
    text = builder.system_prompt(spec, scenario, max_rounds=10)
    other = "veskaria" if role == "aldoria" else "aldoria"
    names = scenario.roles[role]

    assert text.startswith(f"Вы — глава делегации {names.name_gen['ru']} на экстренных переговорах")
    assert f"{names.name['ru']} получит 45 баллов" in text
    assert "не более 10 сообщений" in text
    assert f"написанное {'на английском языке' if dialog == 'en' else 'на русском языке'}" in text
    for issue in scenario.issues:
        assert f'{issue.label["ru"]} (ключ "{issue.id}")' in text
        for k, opt in enumerate(issue.options):
            p = issue.points[role][k]
            assert f"вариант {k}: {opt['ru']} — {p} {plural_ru(p, 'балл', 'балла', 'баллов')}" in text
    leaked = [f"вариант {k}: {o['ru']} — {issue.points[other][k]} " for issue in scenario.issues
              for k, o in enumerate(issue.options) if issue.points[other][k] != issue.points[role][k]]
    assert not any(line in text for line in leaked)
    assert not textcheck.mentions_translation(text, "ru")
    assert textcheck.latin_words(text) == []  # only JSON names in quotes, "JSON" and "null"
    assert langcheck.detect(text) == "ru"
    assert ("жёстк" in text) == (persona == "hawk")


@pytest.mark.parametrize("role, persona", list(itertools.product(["aldoria", "veskaria"], ["hawk", "dove"])))
def test_english_and_russian_prompts_match(builder, scenario, role, persona):
    """Same numbers, headings and bullet points in both instruction languages."""
    texts = {lang: builder.system_prompt(AgentSpec(role=role, persona=persona, instr_lang=lang, dialog_lang=lang, model="x"),
                                         scenario, max_rounds=10) for lang in ("en", "ru")}
    assert textcheck.numbers(texts["en"], "en") == textcheck.numbers(texts["ru"], "ru")
    for prefix in ("# ", "- ", "   - "):
        assert sum(line.startswith(prefix) for line in texts["en"].split("\n")) == \
               sum(line.startswith(prefix) for line in texts["ru"].split("\n")), prefix


def test_english_prompt_names_issue_keys_and_reads_correctly(builder, scenario):
    spec = AgentSpec(role="aldoria", persona="dove", instr_lang="en", dialog_lang="en", model="x")
    text = builder.system_prompt(spec, scenario, max_rounds=10)
    assert '1. Reservoir filling period (key "filling")' in text
    assert "worth to the Republic of Aldoria" in text and "the Republic of Aldoria gets its walk-away value" in text


@pytest.mark.parametrize("n, word", [(0, "баллов"), (1, "балл"), (2, "балла"), (4, "балла"), (5, "баллов"), (11, "баллов"),
                                     (12, "баллов"), (14, "баллов"), (21, "балл"), (22, "балла"), (25, "баллов"),
                                     (45.0, "баллов"), (45.5, "балла"), (101, "балл"), (111, "баллов")])
def test_russian_plural(n, word):
    assert plural_ru(n, "балл", "балла", "баллов") == word


def test_russian_turn_messages(builder):
    spec = AgentSpec(role="aldoria", persona="dove", instr_lang="ru", dialog_lang="ru", model="x")
    opening = builder.turn_message(spec, 1, 10, None, [])
    assert "Вы открываете переговоры" in opening and "<<<" not in opening
    reply = builder.turn_message(spec, 3, 10, "Мы предлагаем X.", ["Док: А. текст"])
    assert "Сообщение 3 из 10" in reply and "<<<Мы предлагаем X.>>>" in reply and "[1] Док: А. текст" in reply
    last = builder.turn_message(spec, 11, 10, "Мы принимаем.", [])
    assert "использовала все 10 сообщений" in last and "11 из 10" not in last
    for text in (opening, last):
        assert textcheck.latin_words(text) == [] and langcheck.detect(text) == "ru"


@pytest.mark.parametrize("lang, expected", [
    ("en", 'could not be used: "message" must be written in Russian. Reply again'),
    ("ru", 'не может быть использован: сообщение в поле "message" должно быть написано на русском языке. Ответьте ещё раз'),
])
def test_retry_message_uses_the_instruction_language(builder, lang, expected):
    spec = AgentSpec(role="aldoria", persona="dove", instr_lang=lang, dialog_lang="ru", model="x")
    assert expected in builder.retry_message(spec, InvalidReply("wrong_language", expected="ru", detected="en"))


def test_every_error_code_is_worded_in_both_languages(builder):
    params = {"schema": {"field": "my_offer"}, "invalid_offer": {"field": "accepted_terms"},
              "invalid_option": {"issue": "filling", "option": 7}, "wrong_language": {"expected": "en", "detected": "ru"}}
    for lang in ("en", "ru"):
        assert set(builder.errors[lang]) == set(CODES)
        for code in CODES:
            text = builder.error_text(lang, InvalidReply(code, **params.get(code, {})))
            assert "{" not in text and text
    assert langcheck.detect(builder.error_text("ru", InvalidReply("not_json"))) == "ru"
