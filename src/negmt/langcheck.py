"""Cheap language check for EN vs RU messages: share of Cyrillic among letters.

Good enough to catch an agent that drifts into the wrong language. The analysis can
re-check with a full language identifier later.
"""

from __future__ import annotations


def detect(text: str) -> str:
    letters = [c for c in text if c.isalpha()]
    if not letters:
        return "unknown"
    cyr = sum(1 for c in letters if "Ѐ" <= c <= "ӿ")
    share = cyr / len(letters)
    if share >= 0.6:
        return "ru"
    if share <= 0.1:
        return "en"
    return "mixed"


def matches(text: str, lang: str) -> bool:
    found = detect(text)
    return found == lang or found == "unknown"
