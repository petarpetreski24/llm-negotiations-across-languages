"""Negotiation protocol: turn order, accept/confirm rules and termination.

States:
    OPEN     -- X continues --> OPEN
    OPEN     -- X accepts T_x --> PENDING(X, T_x)
    PENDING  -- Y accepts T_y, T_y == T_x --> DEAL
    PENDING  -- Y accepts T_y, T_y != T_x --> ILLUSORY (both believe they agreed)
    PENDING  -- Y continues --> OPEN (the acceptance lapses)
    any      -- walk_away --> WALK_AWAY
    turn limit reached --> TIMEOUT, except that a pending acceptance always gets one reply.
"""

from __future__ import annotations

from enum import Enum
from typing import Optional

from negmt.schemas import AgentOutput


class State(str, Enum):
    OPEN = "open"
    PENDING = "pending"
    DEAL = "deal"
    ILLUSORY = "illusory"
    WALK_AWAY = "walk_away"
    TIMEOUT = "timeout"
    ERROR = "error"


TERMINAL = {State.DEAL, State.ILLUSORY, State.WALK_AWAY, State.TIMEOUT, State.ERROR}


class Protocol:
    def __init__(self, roles: tuple[str, str], first_mover: str, max_rounds: int):
        if first_mover not in roles:
            raise ValueError(f"unknown first mover {first_mover}")
        self.roles = roles
        self.max_turns = 2 * max_rounds
        self.state = State.OPEN
        self.turns = 0
        self.next_speaker = first_mover
        self.pending_by: Optional[str] = None
        self.pending_terms: Optional[dict[str, int]] = None
        self.terms: dict[str, Optional[dict[str, int]]] = {r: None for r in roles}
        self.error: Optional[str] = None

    def other(self, role: str) -> str:
        return self.roles[1] if role == self.roles[0] else self.roles[0]

    @property
    def done(self) -> bool:
        return self.state in TERMINAL

    def needs_turn(self) -> bool:
        if self.done:
            return False
        if self.turns < self.max_turns:
            return True
        return self.state == State.PENDING  # one confirmation reply beyond the limit

    def step(self, speaker: str, out: AgentOutput) -> State:
        if self.done:
            raise RuntimeError("negotiation already finished")
        if speaker != self.next_speaker:
            raise RuntimeError(f"expected {self.next_speaker} to speak, got {speaker}")
        self.turns += 1

        if out.decision == "walk_away":
            self.state = State.WALK_AWAY
        elif out.decision == "accept":
            if out.accepted_terms is None:
                raise ValueError("accept without accepted_terms")
            if self.state == State.PENDING:
                self.terms[self.pending_by] = self.pending_terms
                self.terms[speaker] = dict(out.accepted_terms)
                self.state = State.DEAL if out.accepted_terms == self.pending_terms else State.ILLUSORY
            else:
                self.state = State.PENDING
                self.pending_by, self.pending_terms = speaker, dict(out.accepted_terms)
        else:  # continue: any pending acceptance lapses
            self.state = State.OPEN
            self.pending_by = self.pending_terms = None

        if not self.done and self.turns >= self.max_turns and self.state != State.PENDING:
            self.state = State.TIMEOUT
        if not self.done and self.turns > self.max_turns:  # the confirmation reply was not an accept
            self.state = State.TIMEOUT

        self.next_speaker = self.other(speaker)
        return self.state

    def fail(self, reason: str) -> None:
        self.state = State.ERROR
        self.error = reason

    @property
    def rounds(self) -> int:
        return (self.turns + 1) // 2
