from pathlib import Path

import pytest

from negmt.cells import load_cells
from negmt.scenario import Scenario

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="session")
def scenario() -> Scenario:
    return Scenario.from_yaml(ROOT / "configs" / "scenario" / "ostra.yaml")


@pytest.fixture(scope="session")
def cells():
    return load_cells(ROOT / "configs" / "cells.yaml")
