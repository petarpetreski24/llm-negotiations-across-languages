"""Pass-through translator, used for the A/A test (channel present but changes nothing)."""

from negmt.translation.base import TranslationResult


class IdentityTranslator:
    name = "identity"

    def translate(self, text: str, src: str, tgt: str) -> TranslationResult:
        return TranslationResult(text=text, system=self.name)
