"""JSONL run logs: one file per negotiation (spec line, one line per turn, outcome line)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable

from pydantic import BaseModel

from negmt.schemas import Outcome, RunSpec, TurnRecord


def log_path(root: str | Path, run_id: str) -> Path:
    return Path(root) / (run_id.replace("/", "__") + ".jsonl")


def write_run(path: str | Path, spec: RunSpec, turns: Iterable[TurnRecord], outcome: Outcome, meta: dict | None = None) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".jsonl.tmp")
    with tmp.open("w", encoding="utf-8") as f:
        head = {"type": "spec", **spec.model_dump(mode="json"), "meta": meta or {}}
        f.write(json.dumps(head, ensure_ascii=False) + "\n")
        for rec in turns:
            f.write(_line(rec))
        f.write(_line(outcome))
    tmp.replace(path)  # atomic: a log file exists only if the run finished
    return path


def read_run(path: str | Path) -> tuple[dict, list[TurnRecord], Outcome]:
    lines = [json.loads(l) for l in Path(path).read_text(encoding="utf-8").splitlines() if l.strip()]
    if not lines or lines[0].get("type") != "spec" or lines[-1].get("type") != "outcome":
        raise ValueError(f"{path}: incomplete run log")
    turns = [TurnRecord.model_validate(l) for l in lines[1:-1]]
    return lines[0], turns, Outcome.model_validate(lines[-1])


def _line(model: BaseModel) -> str:
    return json.dumps(model.model_dump(mode="json"), ensure_ascii=False) + "\n"
