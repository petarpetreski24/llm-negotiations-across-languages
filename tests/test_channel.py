import pytest

from negmt.channel import Channel, ChannelError
from negmt.schemas import ChannelSpec
from negmt.translation.fake import TaggingTranslator
from negmt.translation.identity import IdentityTranslator


def test_none_passes_through():
    rec = Channel(ChannelSpec(mode="none")).deliver("hello", "en", "en")
    assert rec.delivered_text == "hello" and rec.system is None


def test_none_rejects_language_mismatch():
    with pytest.raises(ChannelError):
        Channel(ChannelSpec(mode="none")).deliver("hello", "en", "ru")


def test_mt_translates_in_the_right_direction():
    mt = TaggingTranslator("nllb")
    ch = Channel(ChannelSpec(mode="mt", system="nllb"), {"nllb": mt})
    rec = ch.deliver("Мы принимаем", "ru", "en")
    assert rec.delivered_text == "[nllb ru->en] Мы принимаем"
    assert mt.calls == [("Мы принимаем", "ru", "en")]
    with pytest.raises(ChannelError):
        ch.deliver("hi", "en", "en")


def test_roundtrip_goes_through_pivot():
    mt = TaggingTranslator("tg")
    ch = Channel(ChannelSpec(mode="roundtrip", system="tg", pivot="ru"), {"tg": mt})
    rec = ch.deliver("hello", "en", "en")
    assert rec.pivot_text == "[tg en->ru] hello"
    assert rec.delivered_text == "[tg ru->en] [tg en->ru] hello"
    assert rec.system == "roundtrip(tg)"


def test_missing_translator_is_an_error():
    with pytest.raises(ChannelError):
        Channel(ChannelSpec(mode="mt", system="nllb"), {})


def test_identity_translator_changes_nothing():
    ch = Channel(ChannelSpec(mode="mt", system="identity"), {"identity": IdentityTranslator()})
    assert ch.deliver("hello", "en", "ru").delivered_text == "hello"
