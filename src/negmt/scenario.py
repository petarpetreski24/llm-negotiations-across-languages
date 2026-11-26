"""Scenario definition and scoring.

A deal assigns one option index to every issue. Each role scores a deal by summing
its points for the chosen options (maximum 100). This module also enumerates the
outcome space and computes the Pareto frontier, the Nash bargaining point and the
zone of possible agreement (ZOPA), which the analysis uses as ground truth.
"""

from __future__ import annotations

import itertools
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator, Mapping

import yaml

LANGS = ("en", "ru")

Deal = dict[str, int]  # issue id -> option index


@dataclass(frozen=True)
class Issue:
    id: str
    label: Mapping[str, str]
    options: tuple[Mapping[str, str], ...]
    points: Mapping[str, tuple[int, ...]]  # role -> points per option

    @property
    def n_options(self) -> int:
        return len(self.options)


@dataclass(frozen=True)
class Role:
    id: str
    name: Mapping[str, str]
    position: str
    batna: float
    # Russian prompts need the genitive ("делегация Республики Альдория"); falls back to `name`.
    name_gen: Mapping[str, str] = None  # type: ignore[assignment]

    def __post_init__(self):
        if self.name_gen is None:
            object.__setattr__(self, "name_gen", dict(self.name))


@dataclass(frozen=True)
class ScoredDeal:
    deal: Deal
    utility: Mapping[str, int]  # role -> utility


class Scenario:
    def __init__(self, scenario_id: str, roles: Mapping[str, Role], issues: list[Issue]):
        self.id = scenario_id
        self.roles = dict(roles)
        self.issues = list(issues)
        self.issue_ids = [i.id for i in self.issues]
        self._validate()

    # ---------- loading and validation ----------

    @classmethod
    def from_yaml(cls, path: str | Path) -> "Scenario":
        data = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
        roles = {
            rid: Role(
                id=rid,
                name=r["name"],
                position=r["position"],
                batna=float(r["batna"]),
                name_gen={**r["name"], **r.get("name_gen", {})},
            )
            for rid, r in data["roles"].items()
        }
        issues = [
            Issue(
                id=i["id"],
                label=i["label"],
                options=tuple(i["options"]),
                points={rid: tuple(p) for rid, p in i["points"].items()},
            )
            for i in data["issues"]
        ]
        return cls(data["id"], roles, issues)

    def _validate(self) -> None:
        if len(self.roles) != 2:
            raise ValueError("a bilateral scenario needs exactly two roles")
        if len(set(self.issue_ids)) != len(self.issue_ids):
            raise ValueError("duplicate issue ids")
        for role in self.roles.values():
            for lang in LANGS:
                if lang not in role.name or lang not in role.name_gen:
                    raise ValueError(f"role {role.id}: missing '{lang}' name")
        for issue in self.issues:
            for lang in LANGS:
                if lang not in issue.label:
                    raise ValueError(f"issue {issue.id}: missing '{lang}' label")
                for k, opt in enumerate(issue.options):
                    if lang not in opt:
                        raise ValueError(f"issue {issue.id} option {k}: missing '{lang}' label")
            for rid in self.roles:
                pts = issue.points.get(rid)
                if pts is None or len(pts) != issue.n_options:
                    raise ValueError(f"issue {issue.id}: points for {rid} must match option count")
        for rid in self.roles:
            total = sum(max(i.points[rid]) for i in self.issues)
            if total != 100:
                raise ValueError(f"role {rid}: issue maxima sum to {total}, expected 100")

    # ---------- scoring ----------

    def validate_deal(self, deal: Mapping[str, int]) -> None:
        missing = set(self.issue_ids) - set(deal)
        extra = set(deal) - set(self.issue_ids)
        if missing or extra:
            raise ValueError(f"deal must cover exactly the issues; missing={sorted(missing)} extra={sorted(extra)}")
        for issue in self.issues:
            k = deal[issue.id]
            if not isinstance(k, int) or isinstance(k, bool) or not 0 <= k < issue.n_options:
                raise ValueError(f"issue {issue.id}: invalid option {k!r}")

    def utility(self, role: str, deal: Mapping[str, int]) -> int:
        self.validate_deal(deal)
        return sum(issue.points[role][deal[issue.id]] for issue in self.issues)

    def utilities(self, deal: Mapping[str, int]) -> dict[str, int]:
        return {rid: self.utility(rid, deal) for rid in self.roles}

    def describe(self, deal: Mapping[str, int], lang: str = "en") -> dict[str, str]:
        """Human-readable option labels for a deal."""
        self.validate_deal(deal)
        return {i.id: i.options[deal[i.id]][lang] for i in self.issues}

    # ---------- outcome space ----------

    def all_deals(self) -> Iterator[ScoredDeal]:
        """Every deal, in itertools.product order (stable, used for tie-breaking)."""
        ranges = [range(i.n_options) for i in self.issues]
        role_ids = list(self.roles)
        for combo in itertools.product(*ranges):
            deal = dict(zip(self.issue_ids, combo))
            util = {
                rid: sum(issue.points[rid][k] for issue, k in zip(self.issues, combo)) for rid in role_ids
            }
            yield ScoredDeal(deal, util)

    def pareto_frontier(self) -> list[ScoredDeal]:
        """All deals not weakly dominated by another deal (ties at a frontier point are all kept)."""
        if getattr(self, "_frontier", None) is None:
            self._frontier = self._compute_frontier()
        return self._frontier

    def _compute_frontier(self) -> list[ScoredDeal]:
        a, b = list(self.roles)
        deals = list(self.all_deals())
        points = sorted({(d.utility[a], d.utility[b]) for d in deals}, key=lambda p: (-p[0], -p[1]))
        frontier_points, best_b = set(), float("-inf")
        for pa, pb in points:
            if pb > best_b:
                frontier_points.add((pa, pb))
                best_b = pb
        return [d for d in deals if (d.utility[a], d.utility[b]) in frontier_points]

    def zopa(self, batnas: Mapping[str, float] | None = None) -> list[ScoredDeal]:
        """Deals at least as good as the walk-away value for both roles."""
        batnas = batnas or {rid: r.batna for rid, r in self.roles.items()}
        return [d for d in self.all_deals() if all(d.utility[r] >= batnas[r] for r in self.roles)]

    def nash_point(self, batnas: Mapping[str, float] | None = None) -> ScoredDeal:
        """Deal in the ZOPA maximising the product of gains over BATNA (first in product order on ties)."""
        batnas = batnas or {rid: r.batna for rid, r in self.roles.items()}
        candidates = self.zopa(batnas)
        if not candidates:
            raise ValueError("empty ZOPA: no deal beats both BATNAs")

        def gain(d: ScoredDeal) -> float:
            result = 1.0
            for r in self.roles:
                result *= d.utility[r] - batnas[r]
            return result

        return max(candidates, key=gain)

    def pareto_distance(self, deal: Mapping[str, int]) -> float:
        """Euclidean distance in utility space from a deal to the nearest Pareto-optimal point."""
        a, b = list(self.roles)
        u = self.utilities(deal)
        return min(
            ((u[a] - p.utility[a]) ** 2 + (u[b] - p.utility[b]) ** 2) ** 0.5 for p in self.pareto_frontier()
        )
