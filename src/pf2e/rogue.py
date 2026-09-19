"""Level-1 Rogue class rules and racket calculations.

These helpers are deliberately pure. Encounter and skill-action owners supply
the current target, initiative, weapon, and condition facts, then apply the
returned modifier, damage term, or effect through their existing transaction.
This module does not infer off-guard status from prose or actor names.

Rules checked 2026-09-15 against the current Player Core entries on Archives
of Nethys:

* Rogue class: https://2e.aonprd.com/Classes.aspx?ID=37
* Rogue rackets: https://2e.aonprd.com/Rackets.aspx
* Weapon groups: https://2e.aonprd.com/Rules.aspx?ID=2203
* Club weapon (club critical specialization):
  https://2e.aonprd.com/Weapons.aspx?ID=166
* Nimble Dodge: https://2e.aonprd.com/Feats.aspx?ID=4916
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol, TypeGuard

from .checks import DegreeOfSuccess, Modifier
from .damage import DamageTerm


class _AttackProfile(Protocol):
    """Minimal read-only Strike facts accepted from the encounter core."""

    traits: frozenset[str]
    item_id: str | None
    damage_dice: tuple[int, ...]


class RogueRacket(StrEnum):
    MASTERMIND = "mastermind"
    RUFFIAN = "ruffian"
    SCOUNDREL = "scoundrel"
    THIEF = "thief"


class WeaponCategory(StrEnum):
    SIMPLE = "simple"
    MARTIAL = "martial"
    ADVANCED = "advanced"


class OffGuardScope(StrEnum):
    ROGUE_ATTACKS = "rogue_attacks"
    ROGUE_MELEE_ATTACKS = "rogue_melee_attacks"
    ALL_MELEE_ATTACKS = "all_melee_attacks"


class OffGuardExpiry(StrEnum):
    ROGUE_NEXT_TURN_START = "rogue_next_turn_start"
    ROGUE_NEXT_TURN_END = "rogue_next_turn_end"
    SIXTY_SECONDS = "sixty_seconds"


@dataclass(frozen=True)
class RacketOffGuardGrant:
    """The source and duration facts for an off-guard contribution.

    The state owner must keep the grant source-relative and scope it to the
    listed attacks. It must not project these grants as an unconditional AC
    penalty against unrelated attackers.
    """

    scope: OffGuardScope
    expiry: OffGuardExpiry


@dataclass(frozen=True)
class ScoundrelFeintBenefits:
    off_guard: RacketOffGuardGrant | None
    can_free_step: bool


@dataclass(frozen=True)
class CriticalSpecializationEffect:
    """One supported weapon-group specialization, before movement is applied."""

    weapon_group: str
    effect: str
    maximum_distance_ft: int
    direction: str
    forced_movement: bool


def rogue_racket(abilities: tuple[str, ...] | list[str]) -> RogueRacket | None:
    """Read the one explicit racket ability encoded in a definition."""

    if not isinstance(abilities, (tuple, list)):
        raise ValueError("abilities must be a tuple or list of strings")
    selected = tuple(
        racket
        for racket in RogueRacket
        if f"rogue_racket_{racket.value}" in abilities
    )
    if len(selected) > 1:
        raise ValueError("a Rogue definition can have only one racket")
    return selected[0] if selected else None


def is_thrown_melee_weapon(
    attack: _AttackProfile,
    attacks: tuple[_AttackProfile, ...],
) -> bool:
    """Resolve whether a ranged thrown profile represents a melee weapon.

    A thrown dagger's ranged profile carries the same ``item_id`` as its
    melee profile. A thrown ranged weapon, such as a dart, has no matching
    melee profile and doesn't need agile or finesse for Sneak Attack.
    """

    if not _is_attack_profile(attack) or not isinstance(attacks, tuple):
        raise ValueError("attack and attacks must be a Strike profile and a tuple")
    if any(not _is_attack_profile(item) for item in attacks):
        raise ValueError("attacks must contain only Strike profiles")
    if "ranged" not in attack.traits or "thrown" not in attack.traits or attack.item_id is None:
        return False
    return any(
        item.item_id == attack.item_id
        and "melee" in item.traits
        and "unarmed" not in item.traits
        for item in attacks
    )


def sneak_attack_is_eligible(
    attack: _AttackProfile,
    *,
    target_is_off_guard: bool,
    racket: RogueRacket | str,
    weapon_category: WeaponCategory | str | None = None,
    adjusted_weapon_die_sides: int | None = None,
    thrown_melee_weapon: bool,
) -> bool:
    """Whether a specific Strike qualifies for the level-1 Sneak Attack.

    ``adjusted_weapon_die_sides`` is the weapon's ordinary base die after
    effects that change its size. Do not pass a fatal die here. A thrown melee
    weapon is identified explicitly because the ranged Strike profile alone
    does not say whether the underlying weapon is melee or ranged.
    """

    if not _is_attack_profile(attack):
        raise ValueError("attack must provide valid Strike profile facts")
    if type(target_is_off_guard) is not bool or type(thrown_melee_weapon) is not bool:
        raise ValueError("off-guard and thrown-melee facts must be booleans")
    selected_racket = _racket(racket)
    traits = attack.traits
    if "off_guard" in traits:
        raise ValueError("target off-guard status is a separate context fact")
    if not target_is_off_guard:
        return False

    category = _weapon_category(weapon_category)
    agile_or_finesse = bool({"agile", "finesse"} & traits)
    is_unarmed = "unarmed" in traits
    is_melee_strike = "melee" in traits and "ranged" not in traits
    is_ranged_strike = "ranged" in traits

    if is_melee_strike and agile_or_finesse:
        return True
    if is_ranged_strike:
        if "thrown" in traits and thrown_melee_weapon:
            if agile_or_finesse:
                return True
        elif not ("thrown" in traits and thrown_melee_weapon):
            # All ranged weapons and ranged unarmed attacks qualify.
            return True

    # Ruffian expands the weapon list, subject to the printed category and die
    # caps. This is weapon-only; it does not turn an otherwise ineligible
    # unarmed attack into a qualifying weapon.
    if selected_racket is RogueRacket.RUFFIAN and not is_unarmed:
        return ruffian_weapon_is_eligible(
            attack,
            weapon_category=category,
            adjusted_weapon_die_sides=adjusted_weapon_die_sides,
        )
    return False


def ruffian_weapon_is_eligible(
    attack: _AttackProfile,
    *,
    weapon_category: WeaponCategory | str | None,
    adjusted_weapon_die_sides: int | None = None,
) -> bool:
    """Whether Ruffian's broader Sneak Attack applies to this weapon.

    The normal die, after die-size adjustments, must be at most d8 for a
    simple weapon or d6 for a martial/advanced weapon. Fatal's critical die
    change is deliberately excluded from this input and cannot change the
    result.
    """

    if not _is_attack_profile(attack):
        raise ValueError("attack must provide valid Strike profile facts")
    if "unarmed" in attack.traits or attack.item_id is None:
        return False
    category = _weapon_category(weapon_category)
    if category is None:
        return False
    die_sides = _weapon_die_sides(attack, adjusted_weapon_die_sides)
    maximum = 8 if category is WeaponCategory.SIMPLE else 6
    return die_sides <= maximum


def sneak_attack_damage_term(
    attack: _AttackProfile,
    *,
    damage_type: str,
    target_is_off_guard: bool,
    racket: RogueRacket | str,
    weapon_category: WeaponCategory | str | None = None,
    adjusted_weapon_die_sides: int | None = None,
    thrown_melee_weapon: bool,
) -> DamageTerm | None:
    """Return this Strike's separate, critical-doubling precision damage.

    There is intentionally no once-per-turn state: every qualifying Strike
    can deal this term. The shared damage pipeline combines defenses against
    the attack's damage components.
    """

    if not isinstance(damage_type, str) or not damage_type.strip():
        raise ValueError("damage_type must be a non-empty string")
    if not sneak_attack_is_eligible(
        attack,
        target_is_off_guard=target_is_off_guard,
        racket=racket,
        weapon_category=weapon_category,
        adjusted_weapon_die_sides=adjusted_weapon_die_sides,
        thrown_melee_weapon=thrown_melee_weapon,
    ):
        return None
    return DamageTerm(
        source="rogue_sneak_attack",
        damage_type=damage_type,
        dice=(6,),
        tags=frozenset({"precision"}),
        critical_mode="double",
    )


def surprise_attack_applies(
    *,
    round_number: int,
    initiative_skill: str,
    target_has_acted: bool,
    has_surprise_attack: bool,
) -> bool:
    """Whether Surprise Attack makes this target off-guard to this Rogue."""

    if type(round_number) is not int or round_number < 1:
        raise ValueError("round_number must be a positive integer")
    if not isinstance(initiative_skill, str) or not initiative_skill:
        raise ValueError("initiative_skill must be a non-empty string")
    if type(target_has_acted) is not bool or type(has_surprise_attack) is not bool:
        raise ValueError("target/feature context facts must be booleans")
    return (
        has_surprise_attack
        and round_number == 1
        and initiative_skill.casefold() in {"stealth", "deception"}
        and not target_has_acted
    )


def mastermind_recall_knowledge_grant(
    degree: DegreeOfSuccess,
    *,
    identified_creature: bool,
) -> RacketOffGuardGrant | None:
    """Return Mastermind's source-relative grant for creature identification.

    The explicit ``identified_creature`` context prevents unrelated Recall
    Knowledge results from activating the racket. Critical success lasts one
    minute; ordinary success lasts until the Rogue's next turn starts.
    """

    if not isinstance(degree, DegreeOfSuccess):
        raise ValueError("degree must be a DegreeOfSuccess")
    if type(identified_creature) is not bool:
        raise ValueError("identified_creature must be a boolean")
    if not identified_creature or degree < DegreeOfSuccess.SUCCESS:
        return None
    return RacketOffGuardGrant(
        scope=OffGuardScope.ROGUE_ATTACKS,
        expiry=(
            OffGuardExpiry.SIXTY_SECONDS
            if degree is DegreeOfSuccess.CRITICAL_SUCCESS
            else OffGuardExpiry.ROGUE_NEXT_TURN_START
        ),
    )


def scoundrel_feint_benefits(
    degree: DegreeOfSuccess,
    *,
    wielding_agile_or_finesse_melee_weapon: bool,
) -> ScoundrelFeintBenefits:
    """Return Scoundrel's Feint off-guard scope and optional free Step."""

    if not isinstance(degree, DegreeOfSuccess):
        raise ValueError("degree must be a DegreeOfSuccess")
    if type(wielding_agile_or_finesse_melee_weapon) is not bool:
        raise ValueError("weapon fact must be a boolean")
    if degree < DegreeOfSuccess.SUCCESS:
        # The Step follows the Feint check; its availability isn't limited to
        # a successful Feint.
        return ScoundrelFeintBenefits(
            None,
            wielding_agile_or_finesse_melee_weapon,
        )
    scope = (
        OffGuardScope.ALL_MELEE_ATTACKS
        if degree is DegreeOfSuccess.CRITICAL_SUCCESS
        else OffGuardScope.ROGUE_MELEE_ATTACKS
    )
    return ScoundrelFeintBenefits(
        RacketOffGuardGrant(scope, OffGuardExpiry.ROGUE_NEXT_TURN_END),
        wielding_agile_or_finesse_melee_weapon,
    )


def thief_damage_attribute(
    attack: _AttackProfile,
    *,
    racket: RogueRacket | str,
) -> str | None:
    """Return the damage attribute replacement granted by Thief, if any.

    Thief applies Dexterity only to finesse melee Strikes. A thrown attack is
    ranged even though the underlying melee weapon has finesse.
    """

    if not _is_attack_profile(attack):
        raise ValueError("attack must provide valid Strike profile facts")
    if _racket(racket) is not RogueRacket.THIEF:
        return None
    if (
        "melee" in attack.traits
        and "ranged" not in attack.traits
        and "finesse" in attack.traits
    ):
        return "dexterity"
    return None


def thief_damage_modifier(
    attack: _AttackProfile,
    *,
    racket: RogueRacket | str,
    strength_modifier: int,
    dexterity_modifier: int,
) -> int:
    """Return the Strength-based damage ability or Thief Dexterity value."""

    _require_modifier(strength_modifier, "strength_modifier")
    _require_modifier(dexterity_modifier, "dexterity_modifier")
    if thief_damage_attribute(attack, racket=racket) == "dexterity":
        return dexterity_modifier
    return strength_modifier


def nimble_dodge_modifier(
    *,
    has_feat: bool,
    reaction_available: bool,
    attacker_visible: bool,
    encumbered: bool,
    attacker_targets_rogue_with_attack: bool,
) -> Modifier | None:
    """Return Nimble Dodge's +2 AC modifier when its trigger is legal."""

    facts = (
        has_feat,
        reaction_available,
        attacker_visible,
        encumbered,
        attacker_targets_rogue_with_attack,
    )
    if any(type(value) is not bool for value in facts):
        raise ValueError("Nimble Dodge context facts must be booleans")
    if not all((has_feat, reaction_available, attacker_visible, attacker_targets_rogue_with_attack)):
        return None
    if encumbered:
        return None
    return Modifier(2, "circumstance", "Nimble Dodge")


def ruffian_critical_specialization(
    attack: _AttackProfile,
    *,
    racket: RogueRacket | str,
    weapon_category: WeaponCategory | str | None,
    weapon_group: str,
    target_is_off_guard: bool,
    critical_hit: bool,
    adjusted_weapon_die_sides: int | None = None,
) -> CriticalSpecializationEffect | None:
    """Return Ruffian's supported critical specialization for a qualifying hit.

    This slice implements the Club group effect used by the admitted Ruffian
    definition: choose a direction away from the striker and push the target
    up to 10 feet as forced movement. Other groups fail closed so a caller
    cannot claim a playable Ruffian weapon whose critical effect is absent.
    """

    if not _is_attack_profile(attack):
        raise ValueError("attack must provide valid Strike profile facts")
    if type(target_is_off_guard) is not bool or type(critical_hit) is not bool:
        raise ValueError("critical-specialization context facts must be booleans")
    if not isinstance(weapon_group, str) or not weapon_group.strip():
        raise ValueError("weapon_group must be a non-empty string")
    if _racket(racket) is not RogueRacket.RUFFIAN or not critical_hit or not target_is_off_guard:
        return None
    if not ruffian_weapon_is_eligible(
        attack,
        weapon_category=weapon_category,
        adjusted_weapon_die_sides=adjusted_weapon_die_sides,
    ):
        return None
    normalized_group = weapon_group.casefold()
    if normalized_group != "club":
        raise NotImplementedError(
            f"Ruffian critical specialization for {weapon_group!r} is not admitted in this slice."
        )
    return CriticalSpecializationEffect(
        weapon_group="club",
        effect="push target away from the striker",
        maximum_distance_ft=10,
        direction="away_from_striker",
        forced_movement=True,
    )


def _racket(value: RogueRacket | str) -> RogueRacket:
    if isinstance(value, RogueRacket):
        return value
    if isinstance(value, str):
        try:
            return RogueRacket(value.casefold())
        except ValueError:
            pass
    raise ValueError(f"unsupported Rogue racket: {value!r}")


def _weapon_category(value: WeaponCategory | str | None) -> WeaponCategory | None:
    if value is None:
        return None
    if isinstance(value, WeaponCategory):
        return value
    if isinstance(value, str):
        try:
            return WeaponCategory(value.casefold())
        except ValueError:
            pass
    raise ValueError(f"unsupported weapon category: {value!r}")


def _weapon_die_sides(attack: _AttackProfile, adjusted: int | None) -> int:
    sides = adjusted if adjusted is not None else (attack.damage_dice[0] if attack.damage_dice else None)
    if type(sides) is not int or sides not in {4, 6, 8, 10, 12}:
        raise ValueError("weapon damage die must be an ordinary d4, d6, d8, d10, or d12")
    return sides


def _require_modifier(value: int, name: str) -> None:
    if type(value) is not int:
        raise ValueError(f"{name} must be an integer")


def _is_attack_profile(value: object) -> TypeGuard[_AttackProfile]:
    """Validate core-provided Strike facts without importing model.py."""

    if not hasattr(value, "traits") or not hasattr(value, "item_id") or not hasattr(value, "damage_dice"):
        return False
    traits = value.traits
    item_id = value.item_id
    damage_dice = value.damage_dice
    return (
        isinstance(traits, frozenset)
        and all(isinstance(trait, str) for trait in traits)
        and (item_id is None or isinstance(item_id, str))
        and isinstance(damage_dice, tuple)
        and all(type(die) is int and die > 0 for die in damage_dice)
    )
