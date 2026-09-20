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


# The encounter and persistence layers share this finite routing set so a
# targeted spell's dim-light flat-check continuation has the same live and
# saved validation boundary.
CONCEALMENT_TARGETED_SPELL_IDS = frozenset({
    "divine_lance", "daze", "heal", "soothe", "fear", "void_warp", "guidance", "stabilize",
    "runic_weapon", "runic_body", "force_bolt", "frostbite", "enfeeble",
    "telekinetic_projectile", "ignition", "gouging_claw", "tangle_vine",
    "tempest_surge",
    "life_link", "vitality_lash", "harm", "protection",
})


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
                "lingering_composition",
                "Lingering Composition",
                (0,),
                frozenset({"bard", "concentrate", "focus", "spellshape"}),
                None,
                False,
                "https://2e.aonprd.com/Spells.aspx?ID=1769",
            ),
            SpellDefinition(
                "counter_performance",
                "Counter Performance",
                (0,),
                frozenset({"auditory", "bard", "composition", "concentrate", "focus", "fortune", "mental"}),
                60,
                False,
                "https://2e.aonprd.com/Spells.aspx?ID=1762",
            ),
            SpellDefinition(
                "force_bolt",
                "Force Bolt",
                (1,),
                frozenset({"focus", "force", "manipulate", "wizard"}),
                30,
                False,
                "https://2e.aonprd.com/Spells.aspx?ID=1896",
            ),
            SpellDefinition(
                "tempest_surge", "Tempest Surge", (2,),
                frozenset({"air", "concentrate", "druid", "electricity", "focus", "manipulate", "uncommon"}), 30, False,
                "https://2e.aonprd.com/Spells.aspx?ID=1860",
            ),
            SpellDefinition(
                "life_link", "Life Link", (1,),
                frozenset({"focus", "healing", "manipulate", "oracle", "vitality", "uncommon"}), 30, False,
                "https://2e.aonprd.com/Spells.aspx?ID=2081",
            ),
            SpellDefinition(
                "vitality_lash", "Vitality Lash", (2,),
                frozenset({"cantrip", "concentrate", "manipulate", "vitality"}), 30, True,
                "https://2e.aonprd.com/Spells.aspx?ID=1744",
            ),
            SpellDefinition(
                "force_barrage",
                "Force Barrage",
                (1, 2, 3),
                frozenset({"concentrate", "force", "manipulate"}),
                120,
                False,
                "https://2e.aonprd.com/Spells.aspx?ID=1536",
            ),
            SpellDefinition(
                "breathe_fire",
                "Breathe Fire",
                (2,),
                frozenset({"concentrate", "fire", "manipulate"}),
                None,
                False,
                "https://2e.aonprd.com/Spells.aspx?ID=1457",
            ),
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
                "daze",
                "Daze",
                (2,),
                frozenset({"cantrip", "concentrate", "manipulate", "mental", "nonlethal"}),
                60,
                True,
                "https://2e.aonprd.com/Spells.aspx?ID=1482",
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
                "shield",
                "Shield",
                (1,),
                frozenset({"cantrip", "concentrate", "force"}),
                None,
                True,
                "https://2e.aonprd.com/Spells.aspx?ID=1671",
            ),
            SpellDefinition(
                "electric_arc",
                "Electric Arc",
                (2,),
                frozenset({"cantrip", "concentrate", "electricity", "manipulate"}),
                30,
                True,
                "https://2e.aonprd.com/Spells.aspx?ID=1509",
            ),
            SpellDefinition(
                "telekinetic_projectile", "Telekinetic Projectile", (2,),
                frozenset({"attack", "cantrip", "concentrate", "manipulate"}), 30, True,
                "https://2e.aonprd.com/Spells.aspx?ID=1718",
            ),
            SpellDefinition(
                "frostbite", "Frostbite", (2,),
                frozenset({"cantrip", "cold", "concentrate", "manipulate"}), 60, True,
                "https://2e.aonprd.com/Spells.aspx?ID=1539",
            ),
            SpellDefinition(
                "ignition", "Ignition", (2,),
                frozenset({"attack", "cantrip", "concentrate", "fire", "manipulate"}), 30, True,
                "https://2e.aonprd.com/Spells.aspx?ID=1565",
            ),
            SpellDefinition(
                "caustic_blast", "Caustic Blast", (2,),
                frozenset({"acid", "cantrip", "concentrate", "manipulate"}), 30, True,
                "https://2e.aonprd.com/Spells.aspx?ID=1461",
            ),
            SpellDefinition(
                "gouging_claw", "Gouging Claw", (2,),
                frozenset({"attack", "cantrip", "concentrate", "manipulate", "morph"}), 5, True,
                "https://2e.aonprd.com/Spells.aspx?ID=1546",
            ),
            SpellDefinition(
                "tangle_vine", "Tangle Vine", (2,),
                frozenset({"attack", "cantrip", "concentrate", "manipulate", "plant", "wood"}), 30, True,
                "https://2e.aonprd.com/Spells.aspx?ID=1713",
            ),
            SpellDefinition(
                "gale_blast", "Gale Blast", (2,),
                frozenset({"air", "cantrip", "concentrate", "manipulate"}), None, True,
                "https://2e.aonprd.com/Spells.aspx?ID=1994",
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
                "harm",
                "Harm",
                (2,),
                frozenset({"concentrate", "manipulate", "void"}),
                30,
                False,
                "https://2e.aonprd.com/Spells.aspx?ID=1552",
            ),
            SpellDefinition(
                "protection",
                "Protection",
                (2,),
                frozenset({"concentrate", "manipulate"}),
                5,
                False,
                "https://2e.aonprd.com/Spells.aspx?ID=1641",
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
            SpellDefinition(
                "courageous_anthem",
                "Courageous Anthem",
                (1,),
                frozenset({"bard", "cantrip", "composition", "concentrate", "emotion", "mental"}),
                None,
                True,
                "https://2e.aonprd.com/Spells.aspx?ID=1763",
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
                frozenset({"concentrate", "emotion", "fear", "manipulate", "mental"}),
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
            SpellDefinition(
                "enfeeble", "Enfeeble", (2,),
                frozenset({"concentrate", "manipulate"}), 30, False,
                "https://2e.aonprd.com/Spells.aspx?ID=1513",
            ),
            SpellDefinition(
                "runic_body", "Runic Body", (2,),
                frozenset({"concentrate", "manipulate"}), None, False,
                "https://2e.aonprd.com/Spells.aspx?ID=1657",
            ),
            SpellDefinition(
                "command", "Command", (2,),
                frozenset({"auditory", "concentrate", "linguistic", "manipulate", "mental"}), 30, False,
                "https://2e.aonprd.com/Spells.aspx?ID=1470",
            ),
            SpellDefinition(
                "stoke_the_heart", "Stoke the Heart", (1,),
                frozenset({"cantrip", "concentrate", "emotion", "hex", "witch"}), 30, True,
                "https://2e.aonprd.com/Spells.aspx?ID=1892",
            ),
            SpellDefinition(
                "forbidding_ward", "Forbidding Ward", (2,),
                frozenset({"cantrip", "concentrate", "manipulate"}), 30, True,
                "https://2e.aonprd.com/Spells.aspx?ID=1535",
            ),
            SpellDefinition(
                "sigil", "Sigil", (2,),
                frozenset({"cantrip", "concentrate", "manipulate"}), 5, True,
                "https://2e.aonprd.com/Spells.aspx?ID=1673",
            ),
            SpellDefinition(
                "detect_magic", "Detect Magic", (2,),
                frozenset({"cantrip", "concentrate", "detection", "manipulate"}), None, True,
                "https://2e.aonprd.com/Spells.aspx?ID=1485",
            ),
            SpellDefinition(
                "patrons_puppet", "Patron's Puppet", (0,),
                frozenset({"focus", "witch"}), None, False,
                "https://2e.aonprd.com/Spells.aspx?ID=1882",
            ),
        )
    }
)


# This direct-spell slice deliberately supports only the staged Wizard's
# ordinary loose staff.  Its one Bulk and bludgeoning profile are fixed facts
# of this finite content menu; other object shapes await authored Bulk/type
# data rather than receiving invented defaults.
TELEKINETIC_PROJECTILE_OBJECTS: Mapping[str, tuple[int, str]] = MappingProxyType(
    {"staff": (1, "bludgeoning")}
)


def telekinetic_projectile_object_profile(
    definition_id: str,
) -> tuple[int, str] | None:
    """Return the supported loose object's (Bulk, physical damage type)."""
    return TELEKINETIC_PROJECTILE_OBJECTS.get(definition_id)


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


def heal_roll(
    actions: int, roll: Callable[[int], int], *, die_sides: int = 8,
) -> HealingResult:
    """Roll Heal, adding 8 only for the two-action living-heal mode.

    The three-action mode produces one shared roll for all selected living
    targets. ``die_sides`` remains deliberately finite: ordinary Heal uses a
    d8, while the admitted Healing Hands Cleric rolls d10s.
    """
    _check_heal_actions(actions)
    if die_sides not in {8, 10}:
        raise ValueError("Heal supports only d8 or Healing Hands d10 dice")
    face = roll(die_sides)
    if type(face) is not int or not 1 <= face <= die_sides:
        raise ValueError(f"healing die result is outside the d{die_sides} range")
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
    modifier: int = 0,
) -> DamageResult | None:
    """Roll Divine Lance damage on a hit; a miss does not roll damage."""
    _check_degree(degree)
    if degree < DegreeOfSuccess.SUCCESS:
        return None
    return resolve_damage(
        DamagePacket("Divine Lance", "spirit", dice_sides=4, dice_count=2, modifier=modifier),
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


def basic_save_damage_result(raw: DamageResult, degree: DegreeOfSuccess) -> DamageResult:
    """Apply a basic save to one ordinary spell damage component.

    The admitted single-target spell resolvers all roll one typed component
    before their target saves.  Keeping the damage-result adjustment here
    gives those resolvers one literal record of the basic-save outcome while
    leaving multi-recipient and mixed-component effects explicitly owned by
    their distinct procedures.
    """
    if not isinstance(raw, DamageResult) or len(raw.components) != 1:
        raise ValueError("basic-save spell damage requires exactly one damage component")
    total = basic_save_damage(raw.total, degree)
    return replace(
        raw,
        components=(replace(raw.components[0], amount=total),),
        total=total,
        adjustment=f"basic_save:{degree.name.lower()}",
    )


def void_warp_effect(
    degree: DegreeOfSuccess,
    roll: Callable[[int], int],
    *,
    status_damage_bonus: int = 0,
) -> VoidWarpEffect:
    """Roll Void Warp, apply its basic-save damage, and report enfeebled 1.

    ``status_damage_bonus`` is a typed bonus already resolved by the
    encounter.  It joins the raw damage roll before the spell's basic-save
    adjustment, as status bonuses to damage rolls require.
    """
    _check_degree(degree)
    if type(status_damage_bonus) is not int or status_damage_bonus < 0:
        raise ValueError("Void Warp status damage bonus must be a non-negative integer")
    rolled = resolve_damage(
        DamagePacket(
            "Void Warp", "void", dice_sides=4, dice_count=2,
            modifier=status_damage_bonus,
        ),
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
