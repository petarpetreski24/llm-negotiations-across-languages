import pytest

from negmt.cells import CellVariant, _check_cell, build_run_spec

MT = {"MT1": "nllb-200-3.3b", "MT2": "translategemma-27b"}


def test_twelve_variants(cells):
    variants, pairings = cells
    names = [v.name for v in variants]
    assert names == ["A1", "A2", "A3", "A4", "B1", "B1-swap", "B2", "B2-swap", "B3", "B3-swap", "C1", "C2"]
    assert set(pairings) == {"P1", "P2"}


def test_swap_exchanges_languages(cells):
    variants, _ = cells
    b2 = next(v for v in variants if v.name == "B2")
    b2s = next(v for v in variants if v.name == "B2-swap")
    assert b2.langs["aldoria"] == b2s.langs["veskaria"] == {"instr": "en", "dialog": "en"}
    assert b2.langs["veskaria"] == b2s.langs["aldoria"] == {"instr": "ru", "dialog": "ru"}


def test_2x2_block_a(cells):
    variants, _ = cells
    combos = {(v.langs["aldoria"]["instr"], v.langs["aldoria"]["dialog"]) for v in variants if v.base.startswith("A")}
    assert combos == {("en", "en"), ("ru", "ru"), ("en", "ru"), ("ru", "en")}


def test_run_spec(cells):
    variants, pairings = cells
    v = next(v for v in variants if v.name == "B3-swap")
    spec = build_run_spec(experiment="main", variant=v, pairing_name="P2", pairing=pairings["P2"],
                          rep=7, model="qwen3.8-27b", mt_systems=MT)
    assert spec.run_id == "main/qwen3.8-27b/B3-swap/P2/007"
    assert spec.channel.system == "translategemma-27b"
    assert spec.first_mover == "veskaria"  # odd rep
    assert spec.agents["aldoria"].persona == "hawk" and spec.agents["aldoria"].dialog_lang == "ru"
    assert spec.seed == build_run_spec(experiment="main", variant=v, pairing_name="P2", pairing=pairings["P2"],
                                       rep=7, model="qwen3.8-27b", mt_systems=MT).seed


@pytest.mark.parametrize(
    "langs, channel",
    [
        ({"aldoria": {"instr": "en", "dialog": "en"}, "veskaria": {"instr": "ru", "dialog": "ru"}}, {"mode": "none"}),
        ({"aldoria": {"instr": "en", "dialog": "en"}, "veskaria": {"instr": "en", "dialog": "en"}}, {"mode": "mt"}),
        ({"aldoria": {"instr": "en", "dialog": "en"}, "veskaria": {"instr": "en", "dialog": "en"}}, {"mode": "roundtrip"}),
    ],
)
def test_inconsistent_cells_rejected(langs, channel):
    with pytest.raises(ValueError):
        _check_cell(CellVariant("X", "X", langs, channel))
