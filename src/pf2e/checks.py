"""Check and multiple-attack calculations used by the S1 engine.

Rules checked 2026-09-15 against Player Core pp. 401–402:
https://2e.aonprd.com/Rules.aspx?ID=2286
https://2e.aonprd.com/Rules.aspx?ID=2289
"""

from dataclasses import dataclass
from enum import IntEnum
from typing import Iterable


class DegreeOfSuccess(IntEnum):
    CRITICAL_FAILURE = 0
    FAILURE = 1
    SUCCESS = 2
    CRITICAL_SUCCESS = 3

    def label(self) -> str:
        return self.name.replace("_", " ").title()


@dataclass(frozen=True)
class DegreeChange:
    stage: str
    amount: int
    reason: str


@dataclass(frozen=True)
class Modifier:
    """One typed contribution to an attack or defense modifier."""

    amount: int
    modifier_type: str
    source: str


@dataclass(frozen=True)
class CheckResult:
    die: int
    modifier: int
    dc: int
    total: int
    degree_before_adjustments: DegreeOfSuccess
    degree: DegreeOfSuccess
    adjustments: tuple[DegreeChange, ...] = ()
    attack_id: str | None = None
    attack_count: int | None = None
    map_penalty: int = 0
    traits: tuple[str, ...] = ()
    modifier_breakdown: tuple[Modifier, ...] = ()


def combine_modifiers(modifiers: Iterable[Modifier]) -> int:
    """Combine same-type bonuses and penalties using PF2e stacking rules.

    Untyped contributions stack. For every typed category, the highest bonus
    and the worst penalty apply; same-type off-guard causes therefore do not
    create duplicate penalties, while different types still combine.
    """
    untyped = 0
    typed: dict[tuple[str, int], int] = {}
    for modifier in modifiers:
        if type(modifier.amount) is not int or not modifier.modifier_type or not modifier.source:
            raise ValueError("modifiers need an integer amount, type, and source")
        if modifier.modifier_type == "untyped":
            untyped += modifier.amount
            continue
        if modifier.amount == 0:
            continue
        key = (modifier.modifier_type, 1 if modifier.amount > 0 else -1)
        if key not in typed:
            typed[key] = modifier.amount
        elif modifier.amount > 0:
            typed[key] = max(typed[key], modifier.amount)
        else:
            typed[key] = min(typed[key], modifier.amount)
    return untyped + sum(typed.values())


def resolve_check(
    die: int,
    modifier: int,
    dc: int,
    *,
    attack_id: str | None = None,
    attack_count: int | None = None,
    map_penalty: int = 0,
    traits: Iterable[str] = (),
) -> CheckResult:
    """Resolve a d20 check, applying natural 20/1 after the numeric degree."""
    if type(die) is not int or not 1 <= die <= 20:
        raise ValueError("a check die must be an integer from 1 through 20")
    total = die + modifier
    if total >= dc + 10:
        initial = DegreeOfSuccess.CRITICAL_SUCCESS
    elif total >= dc:
        initial = DegreeOfSuccess.SUCCESS
    elif total <= dc - 10:
        initial = DegreeOfSuccess.CRITICAL_FAILURE
    else:
        initial = DegreeOfSuccess.FAILURE

    degree = initial
    adjustments: list[DegreeChange] = []
    if die == 20:
        degree = DegreeOfSuccess(min(DegreeOfSuccess.CRITICAL_SUCCESS, degree + 1))
        adjustments.append(DegreeChange("natural_die", 1, "natural 20"))
    elif die == 1:
        degree = DegreeOfSuccess(max(DegreeOfSuccess.CRITICAL_FAILURE, degree - 1))
        adjustments.append(DegreeChange("natural_die", -1, "natural 1"))

    return CheckResult(
        die=die,
        modifier=modifier,
        dc=dc,
        total=total,
        degree_before_adjustments=initial,
        degree=degree,
        adjustments=tuple(adjustments),
        attack_id=attack_id,
        attack_count=attack_count,
        map_penalty=map_penalty,
        traits=tuple(sorted(traits)),
    )


def multiple_attack_penalty(attacks_already_made: int, traits: Iterable[str] = ()) -> int:
    """Return this attack's MAP; attack traits on this weapon set its rate."""
    if attacks_already_made < 0:
        raise ValueError("attacks_already_made cannot be negative")
    agile = "agile" in traits
    if attacks_already_made == 0:
        return 0
    if attacks_already_made == 1:
        return -4 if agile else -5
    return -8 if agile else -10
