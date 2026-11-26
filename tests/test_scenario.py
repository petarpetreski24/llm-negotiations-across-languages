"""Scenario tests: must reproduce the calibration numbers from planning/scenario_check.py."""

from pathlib import Path

import pytest

from negmt.scenario import Scenario

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def sc() -> Scenario:
    return Scenario.from_yaml(ROOT / "configs" / "scenario" / "ostra.yaml")


SPLIT = {i: 2 for i in ["filling", "release", "compensation", "electricity", "monitoring", "communique"]}


def test_structure(sc):
    assert sc.id == "ostra-v1"
    assert list(sc.roles) == ["aldoria", "veskaria"]
    assert sc.issue_ids == ["filling", "release", "compensation", "electricity", "monitoring", "communique"]
    assert all(i.n_options == 5 for i in sc.issues)


def test_every_label_has_both_languages(sc):
    for issue in sc.issues:
        assert issue.label["en"] and issue.label["ru"]
        for opt in issue.options:
            assert opt["en"] and opt["ru"]


def test_outcome_space_size(sc):
    assert sum(1 for _ in sc.all_deals()) == 15_625


def test_split_everything_deal(sc):
    assert sc.utilities(SPLIT) == {"aldoria": 55, "veskaria": 50}


def test_each_side_can_reach_100(sc):
    for role in sc.roles:
        best = {i.id: max(range(5), key=lambda k: i.points[role][k]) for i in sc.issues}
        assert sc.utility(role, best) == 100


def test_pareto_frontier(sc):
    frontier = sc.pareto_frontier()
    assert len(frontier) == 32
    assert len({(d.utility["aldoria"], d.utility["veskaria"]) for d in frontier}) == 31
    assert max(d.utility["aldoria"] + d.utility["veskaria"] for d in frontier) == 140


def test_nash_point(sc):
    nash = sc.nash_point()
    assert nash.utility == {"aldoria": 68, "veskaria": 72}
    assert sc.describe(nash.deal) == {
        "filling": "3 years",
        "release": "45 bcm per year",
        "compensation": "no fund",
        "electricity": "40%",
        "monitoring": "joint technical commission",
        "communique": "takes note of the positions of both parties",
    }


@pytest.mark.parametrize(
    "batnas, share",
    [({"aldoria": 40, "veskaria": 40}, 0.510), ({"aldoria": 45, "veskaria": 45}, 0.327), ({"aldoria": 50, "veskaria": 50}, 0.167)],
)
def test_zopa_share(sc, batnas, share):
    assert len(sc.zopa(batnas)) / 15_625 == pytest.approx(share, abs=0.001)


def test_monitoring_is_a_shared_interest(sc):
    mon = next(i for i in sc.issues if i.id == "monitoring")
    fav = {r: max(range(5), key=lambda k: mon.points[r][k]) for r in sc.roles}
    assert fav["aldoria"] == fav["veskaria"] == 3


def test_pareto_distance(sc):
    assert sc.pareto_distance(sc.nash_point().deal) == 0
    assert sc.pareto_distance(SPLIT) > 0


@pytest.mark.parametrize(
    "bad",
    [
        {**SPLIT, "filling": 5},  # option out of range
        {k: v for k, v in SPLIT.items() if k != "release"},  # missing issue
        {**SPLIT, "tariffs": 0},  # unknown issue
        {**SPLIT, "filling": True},  # bool is not an option index
    ],
)
def test_invalid_deals_rejected(sc, bad):
    with pytest.raises(ValueError):
        sc.utility("aldoria", bad)
