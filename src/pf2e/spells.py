"""Pure numeric helpers and fixed rank-1 spell metadata for the S3 roster.

The reviewed rules sources are recorded in
``docs/implementation/s1-s3-rules.md`` and in each spell definition below.
Basic saving throw outcomes follow Player Core p. 404:
https://2e.aonprd.com/Rules.aspx?ID=2297
Area and emanation measurement follow Player Core p. 428:
https://2e.aonprd.com/Rules.aspx?ID=2384

These helpers do not choose targets, spend actions or prepared slots, mutate
health, or store ongoing effects. They cover the fixed ordinary-living S3
roster only. Heal's undead vitality effects and Void Warp against anything
other than a living creature are unsupported here. Read Aura remains on the
prepared list but its one-minute cast is unavailable during encounters.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from types import MappingProxyType
from typing import Callable, Mapping

from .checks import DegreeOfSuccess
from .damage import DamagePacket, DamageResult, resolve_damage
from .model import Position
from .space import grid_distance_feet


@dataclass(frozen=True, slots=True)
class SpellDefinition:
    """Fixed reviewed spell facts needed by the current S3 roster."""

    spell_id: str
    name: str
    action_costs: tuple[int, ...]
    traits: frozenset[str]
    range_ft: int | None
    cantrip: bool
    source_url: str
    unavailable_reason: str | None = None


SPELLS: Mapping[str, SpellDefinition] = MappingProxyType(
    {
        spell.spell_id: spell
        for spell in (
            SpellDefinition(
                "divine_lance",
                "Divine Lance",
                (2,),
                frozenset({"attack", "cantrip", "concentrate", "manipulate", "sanctified", "spirit"}),
                60,
                True,
                "https://2e.aonprd.com/Spells.aspx?ID=1498",
            ),
            SpellDefinition(
                "void_warp",
                "Void Warp",
                (2,),
                frozenset({"cantrip", "concentrate", "manipulate", "void"}),
                30,
                True,
                "https://2e.aonprd.com/Spells.aspx?ID=1745",
            ),
            SpellDefinition(
                "guidance",
                "Guidance",
                (1,),
                frozenset({"cantrip", "concentrate"}),
                30,
                True,
                "https://2e.aonprd.com/Spells.aspx?ID=1549",
            ),
            SpellDefinition(
                "stabilize",
                "Stabilize",
                (2,),
                frozenset({"cantrip", "concentrate", "healing", "manipulate", "vitality"}),
                30,
                True,
                "https://2e.aonprd.com/Spells.aspx?ID=1689",
            ),
            SpellDefinition(
                "read_aura",
                "Read Aura",
                (),
                frozenset({"cantrip", "concentrate", "detection", "manipulate"}),
                30,
                True,
                "https://2e.aonprd.com/Spells.aspx?ID=1646",
                unavailable_reason="Its one-minute cast is unavailable during encounters.",
            ),
            SpellDefinition(
                "heal",
                "Heal",
                (1, 2, 3),
                frozenset({"healing", "manipulate", "vitality"}),
                None,
                False,
                "https://2e.aonprd.com/Spells.aspx?ID=1554",
            ),
            SpellDefinition(
                "soothe",
                "Soothe",
                (2,),
                frozenset({"concentrate", "emotion", "healing", "mental"}),
                30,
                False,
                "https://2e.aonprd.com/Spells.aspx?ID=1678",
            ),
            SpellDefinition(
                "angelic_halo",
                "Angelic Halo",
                (1,),
                frozenset({"aura", "concentrate", "focus", "holy"}),
                None,
                False,
                "https://2e.aonprd.com/Spells.aspx?ID=2093",
            ),
            # These entries are part of the staged Angelic repertoire ledger.
            # Light's point cast is admitted by the first orb slice; other
            # entries still require their own explicit encounter procedures.
            SpellDefinition(
                "light",
                "Light",
                (2,),
                frozenset({"cantrip", "concentrate", "manipulate", "light"}),
                120,
                True,
                "https://2e.aonprd.com/Spells.aspx?ID=1585",
            ),
            SpellDefinition(
                "fear",
                "Fear",
                (2,),
                frozenset({"auditory", "concentrate", "emotion", "fear", "mental"}),
                30,
                False,
                "https://2e.aonprd.com/Spells.aspx?ID=1524",
            ),
            SpellDefinition(
                "runic_weapon",
                "Runic Weapon",
                (2,),
                frozenset({"concentrate", "manipulate"}),
                None,
                False,
                "https://2e.aonprd.com/Spells.aspx?ID=1658",
            ),
            SpellDefinition(
                "sure_strike",
                "Sure Strike",
                (1,),
                frozenset({"concentrate", "fortune"}),
                None,
                False,
                "https://2e.aonprd.com/Spells.aspx?ID=1709",
            ),
        )
    }
)


def spell_traits(spell_id: str, actions: int | None = None) -> frozenset[str]:
    """Return fixed traits, including Heal's action-specific concentrate trait."""
    spell = SPELLS[spell_id]
    if actions is not None:
        if type(actions) is not int:
            raise TypeError("spell actions must be an integer")
        if actions not in spell.action_costs:
            raise ValueError(f"{actions!r} actions is not a supported mode for {spell.name}")
    traits = set(spell.traits)
    if spell_id == "heal" and actions in (2, 3):
        traits.add("concentrate")
    return frozenset(traits)


def heal_range_ft(actions: int) -> int | None:
    """Return Heal's range for a mode; ``None`` means touch or emanation."""
    _check_heal_actions(actions)
    return 30 if actions == 2 else None


@dataclass(frozen=True, slots=True)
class HealingResult:
    """One rank-1 living-target Heal die, before health-state transitions."""

    rolls: tuple[int, ...]
    modifier: int
    total: int


def heal_roll(actions: int, roll: Callable[[int], int]) -> HealingResult:
    """Roll Heal's 1d8, adding 8 only for the two-action living-heal mode.

    The three-action mode produces one shared roll for all selected living
    targets. This function deliberately does not inspect or alter those targets.
    """
    _check_heal_actions(actions)
    face = roll(8)
    if type(face) is not int or not 1 <= face <= 8:
        raise ValueError("healing die result is outside the d8 range")
    modifier = 8 if actions == 2 else 0
    return HealingResult((face,), modifier, face + modifier)


def soothe_roll(roll: Callable[[int], int]) -> HealingResult:
    """Roll rank-1 Soothe's 1d10+4 healing."""
    face = roll(10)
    if type(face) is not int or not 1 <= face <= 10:
        raise ValueError("Soothe healing die result is outside the d10 range")
    return HealingResult((face,), 4, face + 4)


@dataclass(frozen=True, slots=True)
class VoidWarpEffect:
    """Post-save numeric damage and the critical-failure condition value."""

    damage: DamageResult
    enfeebled: int


def divine_lance_damage(
    degree: DegreeOfSuccess,
    roll: Callable[[int], int],
) -> DamageResult | None:
    """Roll Divine Lance damage on a hit; a miss does not roll damage."""
    _check_degree(degree)
    if degree < DegreeOfSuccess.SUCCESS:
        return None
    return resolve_damage(
        DamagePacket("Divine Lance", "spirit", dice_sides=4, dice_count=2, modifier=0),
        roll,
        critical=degree is DegreeOfSuccess.CRITICAL_SUCCESS,
    )


def basic_save_damage(total: int, degree: DegreeOfSuccess) -> int:
    """Apply a basic save: none, half down, full, or double damage."""
    if type(total) is not int:
        raise TypeError("damage total must be an integer")
    if total < 0:
        raise ValueError("damage total cannot be negative")
    _check_degree(degree)
    if degree is DegreeOfSuccess.CRITICAL_SUCCESS:
        return 0
    if degree is DegreeOfSuccess.SUCCESS:
        return 1 if total == 1 else total // 2
    if degree is DegreeOfSuccess.FAILURE:
        return total
    return total * 2


def void_warp_effect(
    degree: DegreeOfSuccess,
    roll: Callable[[int], int],
) -> VoidWarpEffect:
    """Roll Void Warp, apply its basic-save damage, and report enfeebled 1."""
    _check_degree(degree)
    rolled = resolve_damage(
        DamagePacket("Void Warp", "void", dice_sides=4, dice_count=2, modifier=0),
        roll,
    )
    total = basic_save_damage(rolled.total, degree)
    component = replace(rolled.components[0], amount=total)
    # Preserve the raw dice sum. `multiplier` continues to mean critical
    # damage doubling; the save-adjusted amount is recorded in total/component.
    damage = DamageResult(
        components=(component,),
        rolled_total=rolled.rolled_total,
        multiplier=rolled.multiplier,
        total=total,
    )
    return VoidWarpEffect(
        damage=damage,
        enfeebled=1 if degree is DegreeOfSuccess.CRITICAL_FAILURE else 0,
    )


def in_heal_emanation(origin: Position, target: Position) -> bool:
    """Return whether a one-cell target lies within Heal's 30-foot emanation.

    The caster's self-inclusion is a separate choice. This pure geometry helper
    has no creature identity, team, willingness, or target eligibility context.
    """
    return grid_distance_feet(origin, target) <= 30


def _check_heal_actions(actions: int) -> None:
    if type(actions) is not int:
        raise TypeError("Heal actions must be an integer")
    if actions not in (1, 2, 3):
        raise ValueError("Heal supports one, two, or three actions")


def _check_degree(degree: DegreeOfSuccess) -> None:
    if type(degree) is not DegreeOfSuccess:
        raise TypeError("degree must be a DegreeOfSuccess")
