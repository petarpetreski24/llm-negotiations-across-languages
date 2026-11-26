"""Why an agent's reply was rejected.

The agent raises `InvalidReply` with a code and parameters instead of an English sentence,
so the retry message can be worded in the agent's instruction language
(catalog: configs/prompts/errors.yaml). `str()` gives a short form for logs.
"""

from __future__ import annotations

CODES = (
    "not_json",
    "schema",
    "invalid_offer",
    "accept_without_terms",
    "terms_without_accept",
    "invalid_option",
    "unknown_issue",
    "empty_message",
    "wrong_language",
)


class InvalidReply(ValueError):
    def __init__(self, code: str, **params: object):
        if code not in CODES:
            raise ValueError(f"unknown reply error code {code!r}")
        self.code = code
        self.params = params
        detail = ", ".join(f"{k}={v}" for k, v in params.items())
        super().__init__(f"{code} ({detail})" if detail else code)
