import json

import pytest

from negmt.agent import Agent, AgentFailure
from negmt.errors import InvalidReply
from negmt.llm.fake import ScriptedLLM
from negmt.prompts import PlainPromptBuilder
from negmt.schemas import AgentSpec

OFFER = {"filling": 0, "release": 4, "compensation": 0, "electricity": 4, "monitoring": 3, "communique": 2}


def reply(message="Our proposal.", decision="continue", offer=OFFER, accepted=None, **extra):
    return json.dumps({"message": message, "my_offer": offer, "their_offer_as_understood": {},
                       "decision": decision, "accepted_terms": accepted, "plan": "p", **extra}, ensure_ascii=False)


def make(scenario, responses, lang="en"):
    spec = AgentSpec(role="aldoria", persona="dove", instr_lang="en", dialog_lang=lang, model="scripted")
    llm = ScriptedLLM(responses)
    return Agent(spec, scenario, llm, PlainPromptBuilder(), max_rounds=10), llm


def test_valid_reply(scenario):
    agent, _ = make(scenario, [reply()])
    turn = agent.act(1, None)
    assert turn.retries == 0 and turn.output.my_offer == OFFER
    assert turn.output.their_offer_as_understood == {i: None for i in scenario.issue_ids}
    assert len(agent.history) == 2


@pytest.mark.parametrize(
    "bad",
    [
        "not json",
        reply(offer={**OFFER, "filling": 9}),
        reply(decision="accept", accepted=None),
        reply(accepted=OFFER),  # accepted_terms with decision continue
        reply(message="Наше предложение"),  # wrong language for an English speaker
        reply(message="   "),
    ],
)
def test_invalid_reply_is_retried(scenario, bad):
    agent, llm = make(scenario, [bad, reply()])
    turn = agent.act(1, None)
    assert turn.retries == 1
    assert "invalid" in llm.calls[1][-1]["content"]
    assert len(agent.history) == 2  # failed attempt not kept


def test_gives_up_after_three_bad_replies(scenario):
    agent, _ = make(scenario, ["x", "y", "z"])
    with pytest.raises(AgentFailure):
        agent.act(1, None)


def test_russian_speaker(scenario):
    agent, _ = make(scenario, [reply(message="Наше предложение: #040432")], lang="ru")
    assert agent.act(1, None).lang_detected == "ru"


@pytest.mark.parametrize(
    "bad, code",
    [
        ("not json", "not_json"),
        (json.dumps({"message": "x"}), "schema"),
        (reply(offer={**OFFER, "filling": 9}), "invalid_offer"),
        (reply(decision="accept", accepted=None), "accept_without_terms"),
        (reply(accepted=OFFER), "terms_without_accept"),
        (reply(their_offer_as_understood={"filling": 9}), "invalid_option"),
        (reply(their_offer_as_understood={"dam": 1}), "unknown_issue"),
        (reply(message="   "), "empty_message"),
        (reply(message="Наше предложение"), "wrong_language"),
    ],
)
def test_rejections_carry_a_code(scenario, bad, code):
    agent, _ = make(scenario, [])
    with pytest.raises(InvalidReply) as err:
        agent.validate(bad)
    assert err.value.code == code


def test_retry_is_worded_in_the_instruction_language(scenario):
    from negmt import langcheck
    from negmt.prompts import TemplatePromptBuilder
    from tests.conftest import ROOT

    spec = AgentSpec(role="aldoria", persona="dove", instr_lang="ru", dialog_lang="ru", model="scripted")
    llm = ScriptedLLM([reply(message="Our proposal."), reply(message="Наше предложение.")])
    agent = Agent(spec, scenario, llm, TemplatePromptBuilder(ROOT / "configs"), max_rounds=10)
    assert agent.act(1, None).retries == 1
    retry = llm.calls[1][-1]["content"]
    assert "должно быть написано на русском языке" in retry and langcheck.detect(retry) == "ru"
