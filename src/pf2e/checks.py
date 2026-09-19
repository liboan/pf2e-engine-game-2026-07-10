"""Check and multiple-attack calculations used by the S1 engine.

Rules checked 2026-09-15 against Player Core pp. 401–402:
https://2e.aonprd.com/Rules.aspx?ID=2286
https://2e.aonprd.com/Rules.aspx?ID=2289
Assurance and the fixed 10 + proficiency result:
https://2e.aonprd.com/Feats.aspx?ID=5121
https://2e.aonprd.com/Rules.aspx?ID=2281
"""

from dataclasses import dataclass
from enum import IntEnum
from typing import Iterable, Literal


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
    die: int | None
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
    method: Literal["d20", "assurance"] = "d20"
    # Every supplied d20 face is retained. Ordinary checks have one face;
    # fortune effects such as Sure Strike retain both faces while ``die``
    # remains the selected face used for degree calculation.
    dice: tuple[int, ...] = ()


def _degree_from_total(total: int, dc: int) -> DegreeOfSuccess:
    if total >= dc + 10:
        return DegreeOfSuccess.CRITICAL_SUCCESS
    if total >= dc:
        return DegreeOfSuccess.SUCCESS
    if total <= dc - 10:
        return DegreeOfSuccess.CRITICAL_FAILURE
    return DegreeOfSuccess.FAILURE


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
    initial = _degree_from_total(total, dc)

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
        dice=(die,),
    )


def resolve_assurance_check(
    proficiency_bonus: int,
    dc: int,
    *,
    attack_id: str | None = None,
    attack_count: int | None = None,
    traits: Iterable[str] = (),
) -> CheckResult:
    """Resolve Assurance's fixed result without inventing a die roll.

    Assurance sets the check result to 10 plus the chosen skill's proficiency
    bonus and applies no other modifiers. It uses the normal degree thresholds
    but has no d20 or natural-die degree adjustment.
    """

    if type(proficiency_bonus) is not int or proficiency_bonus < 0:
        raise ValueError("Assurance needs a non-negative integer proficiency bonus")
    if type(dc) is not int or dc < 0:
        raise ValueError("Assurance needs a non-negative integer DC")
    if attack_id is not None and (not isinstance(attack_id, str) or not attack_id):
        raise ValueError("Assurance attack_id must be non-empty text or None")
    if attack_count is not None and (type(attack_count) is not int or attack_count < 1):
        raise ValueError("Assurance attack_count must be a positive integer or None")
    trait_tuple = tuple(traits)
    if any(not isinstance(item, str) or not item for item in trait_tuple):
        raise ValueError("Assurance traits must be non-empty strings")

    total = 10 + proficiency_bonus
    degree = _degree_from_total(total, dc)
    return CheckResult(
        die=None,
        modifier=proficiency_bonus,
        dc=dc,
        total=total,
        degree_before_adjustments=degree,
        degree=degree,
        attack_id=attack_id,
        attack_count=attack_count,
        map_penalty=0,
        traits=tuple(sorted(trait_tuple)),
        modifier_breakdown=(Modifier(proficiency_bonus, "untyped", "Assurance proficiency bonus"),),
        method="assurance",
        dice=(),
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
