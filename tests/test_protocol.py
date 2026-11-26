import pytest

from negmt.protocol import Protocol, State
from negmt.schemas import AgentOutput

ROLES = ("aldoria", "veskaria")
T1 = {"filling": 0, "release": 4, "compensation": 0, "electricity": 4, "monitoring": 3, "communique": 2}
T2 = {**T1, "filling": 1}


def out(decision, terms=None):
    return AgentOutput(message="x", my_offer=T1, decision=decision, accepted_terms=terms)


def test_continue_keeps_open_and_alternates():
    p = Protocol(ROLES, "aldoria", max_rounds=10)
    assert p.step("aldoria", out("continue")) == State.OPEN
    assert p.next_speaker == "veskaria"
    with pytest.raises(RuntimeError):
        p.step("aldoria", out("continue"))


def test_accept_then_matching_accept_is_deal():
    p = Protocol(ROLES, "aldoria", 10)
    p.step("aldoria", out("continue"))
    assert p.step("veskaria", out("accept", T1)) == State.PENDING
    assert p.step("aldoria", out("accept", T1)) == State.DEAL
    assert p.terms == {"aldoria": T1, "veskaria": T1}
    assert not p.needs_turn()


def test_accept_with_different_terms_is_illusory():
    p = Protocol(ROLES, "aldoria", 10)
    p.step("aldoria", out("accept", T1))
    assert p.step("veskaria", out("accept", T2)) == State.ILLUSORY
    assert p.terms == {"aldoria": T1, "veskaria": T2}


def test_counter_offer_lapses_acceptance():
    p = Protocol(ROLES, "aldoria", 10)
    p.step("aldoria", out("accept", T1))
    assert p.step("veskaria", out("continue")) == State.OPEN
    assert p.pending_terms is None


def test_walk_away():
    p = Protocol(ROLES, "veskaria", 10)
    assert p.step("veskaria", out("walk_away")) == State.WALK_AWAY
    assert not p.needs_turn()


def test_timeout_after_round_limit():
    p = Protocol(ROLES, "aldoria", max_rounds=2)
    speaker = "aldoria"
    for _ in range(4):
        state = p.step(speaker, out("continue"))
        speaker = p.other(speaker)
    assert state == State.TIMEOUT and p.turns == 4 and p.rounds == 2


def test_pending_at_limit_gets_one_reply():
    p = Protocol(ROLES, "aldoria", max_rounds=1)
    p.step("aldoria", out("continue"))
    assert p.step("veskaria", out("accept", T1)) == State.PENDING
    assert p.needs_turn()
    assert p.step("aldoria", out("accept", T1)) == State.DEAL


def test_pending_at_limit_rejected_is_timeout():
    p = Protocol(ROLES, "aldoria", max_rounds=1)
    p.step("aldoria", out("continue"))
    p.step("veskaria", out("accept", T1))
    assert p.step("aldoria", out("continue")) == State.TIMEOUT
