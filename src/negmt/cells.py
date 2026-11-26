"""Load cells and persona pairings, expand role swaps, and build run specs."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Mapping

import yaml

from negmt.schemas import AgentSpec, ChannelSpec, RunSpec

ROLES = ("aldoria", "veskaria")


@dataclass(frozen=True)
class CellVariant:
    name: str  # e.g. "B2" or "B2-swap"
    base: str  # e.g. "B2"
    langs: Mapping[str, Mapping[str, str]]  # role -> {"instr": .., "dialog": ..}
    channel: Mapping[str, str | None]  # mode, system (MT1/MT2 placeholder), pivot


def load_cells(path: str | Path) -> tuple[list[CellVariant], dict[str, dict[str, str]]]:
    data = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    variants: list[CellVariant] = []
    for name, cell in data["cells"].items():
        slots = cell["agents"]
        if len(slots) != 2:
            raise ValueError(f"cell {name}: needs exactly two agent slots")
        channel = {"mode": cell["channel"]["mode"], "system": cell["channel"].get("system"),
                   "pivot": cell["channel"].get("pivot")}
        variants.append(CellVariant(name, name, {ROLES[0]: slots[0], ROLES[1]: slots[1]}, channel))
        if cell.get("swap_roles"):
            variants.append(CellVariant(f"{name}-swap", name, {ROLES[0]: slots[1], ROLES[1]: slots[0]}, channel))
    for v in variants:
        _check_cell(v)
    return variants, data["persona_pairings"]


def _check_cell(v: CellVariant) -> None:
    dialogs = {v.langs[r]["dialog"] for r in ROLES}
    mode = v.channel["mode"]
    if mode == "none" and len(dialogs) != 1:
        raise ValueError(f"cell {v.name}: no channel but dialogue languages differ")
    if mode == "mt" and len(dialogs) != 2:
        raise ValueError(f"cell {v.name}: MT channel but both agents speak the same language")
    if mode == "roundtrip" and (len(dialogs) != 1 or not v.channel.get("pivot")):
        raise ValueError(f"cell {v.name}: round trip needs one dialogue language and a pivot")


def build_run_spec(
    *,
    experiment: str,
    variant: CellVariant,
    pairing_name: str,
    pairing: Mapping[str, str],
    rep: int,
    model: str,
    mt_systems: Mapping[str, str],
    max_rounds: int = 10,
    temperature: float | None = 0.7,
) -> RunSpec:
    run_id = f"{experiment}/{model}/{variant.name}/{pairing_name}/{rep:03d}"
    system = variant.channel.get("system")
    channel = ChannelSpec(
        mode=variant.channel["mode"],
        system=mt_systems[system] if system else None,
        pivot=variant.channel.get("pivot"),
    )
    agents = {
        role: AgentSpec(
            role=role,
            persona=pairing[role],
            instr_lang=variant.langs[role]["instr"],
            dialog_lang=variant.langs[role]["dialog"],
            model=model,
        )
        for role in ROLES
    }
    return RunSpec(
        run_id=run_id,
        experiment=experiment,
        cell=variant.name,
        persona_pairing=pairing_name,
        rep=rep,
        seed=RunSpec.seed_for(run_id),
        first_mover=ROLES[rep % 2],
        max_rounds=max_rounds,
        temperature=temperature,
        agents=agents,
        channel=channel,
    )
