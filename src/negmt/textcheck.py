"""Small text checks shared by the Russian-materials review and the translation analysis.

- `numbers()`: the numbers in a text, normalised across English and Russian formats
  (1,200.5 vs 1 200,5), so a translation can be checked for dropped or changed numbers.
- `chrf()`: character n-gram F-score (orders 1-6, beta 2, averaged over orders as in
  sacrebleu), used to compare an English source with its back-translation.
- `jinja_parts()`, `latin_words()`, `mentions_translation()`, `number_words()`: checks
  for template lines and Russian drafts.
"""

from __future__ import annotations

import re
from collections import Counter

_NUMBER = {
    "en": re.compile(r"\d{1,3}(?:,\d{3})+(?:\.\d+)?|\d+(?:\.\d+)?"),
    "ru": re.compile(r"\d{1,3}(?:[   ]\d{3})+(?:,\d+)?|\d+(?:,\d+)?"),
}


def _canonical(raw: str, lang: str) -> str:
    if lang == "en":
        raw = raw.replace(",", "")
    else:
        raw = re.sub(r"[   ]", "", raw).replace(",", ".")
    if "." in raw:
        raw = raw.rstrip("0").rstrip(".")
    return str(int(raw)) if raw.isdigit() else raw


def numbers(text: str, lang: str) -> Counter[str]:
    """Numbers written with digits, e.g. "USD 6.8 billion" (en) and «6,8 млрд» (ru) both give 6.8."""
    return Counter(_canonical(m.group(), lang) for m in _NUMBER[lang].finditer(text))


def number_mismatch(en: str, ru: str) -> tuple[list[str], list[str]]:
    """(numbers missing from the Russian, numbers only in the Russian)."""
    a, b = numbers(en, "en"), numbers(ru, "ru")
    return sorted((a - b).elements()), sorted((b - a).elements())


def chrf(hypothesis: str, reference: str, order: int = 6, beta: float = 2.0) -> float:
    hyp, ref = "".join(hypothesis.split()), "".join(reference.split())
    total, used = 0.0, 0
    for n in range(1, order + 1):
        h = Counter(hyp[i:i + n] for i in range(len(hyp) - n + 1))
        r = Counter(ref[i:i + n] for i in range(len(ref) - n + 1))
        if not h or not r:
            continue
        match = sum((h & r).values())
        p, rc = match / sum(h.values()), match / sum(r.values())
        used += 1
        if p + rc:
            total += (1 + beta**2) * p * rc / (beta**2 * p + rc)
    return 100 * total / used if used else 0.0


_VAR = re.compile(r"\{\{-?\s*(.*?)\s*-?\}\}")
_TAG = re.compile(r"\{%-?\s*(.*?)\s*-?%\}")
_ALIASES = {"country_gen": "country"}  # the Russian template needs the genitive form


def jinja_parts(line: str) -> tuple[set[str], list[str]]:
    """(variable names used, control tags) in a template line; filters are ignored."""
    names = {_ALIASES.get(e.split("|")[0].strip(), e.split("|")[0].strip()) for e in _VAR.findall(line)}
    tags = [" ".join(t.split()) for t in _TAG.findall(line)]
    return names, tags


def strip_jinja(text: str, filler: str = "[X]") -> str:
    """Replace {{ ... }} with a filler and drop {% ... %}, e.g. before machine translation."""
    return _TAG.sub("", _VAR.sub(filler, text)).strip()


_ALLOWED_LATIN = {"JSON", "null"}


def latin_words(ru: str) -> list[str]:
    """Latin-script words left in a Russian text, ignoring template code and "quoted" JSON names."""
    text = _TAG.sub(" ", _VAR.sub(" ", ru))
    text = re.sub(r"\{[A-Za-z_]+\}", " ", text)  # {field}-style placeholders in errors.yaml
    text = re.sub(r'"[^"]*"', " ", text)
    return [w for w in re.findall(r"[A-Za-z][A-Za-z_]+", text) if w not in _ALLOWED_LATIN]


_TRANSLATION = {
    "en": re.compile(r"\btranslat|\binterpret", re.I),
    "ru": re.compile(r"перев[оеёа]д|толмач", re.I),
}


def mentions_translation(text: str, lang: str) -> bool:
    """Agents must never be told that messages are translated."""
    return bool(_TRANSLATION[lang].search(text))


_NUMBER_WORDS = re.compile(
    r"\b(?:one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|fifteen|twenty|thirty|forty|"
    r"fifty|hundred|thousand|million|billion|half|third|quarter|decade|single|first|second)\b",
    re.I,
)


def number_words(en: str) -> list[str]:
    """Numbers written as words in English; these are checked by eye, not automatically."""
    return [w.lower() for w in _NUMBER_WORDS.findall(en)]
