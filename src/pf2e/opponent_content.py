"""Sourced, catalog-only Monster Core profiles for the S3i expansion.

The profiles retain published defenses and monster-only abilities alongside
the common ``CreatureDefinition`` shape.  They remain outside the playable
encounter registry until their runtime behavior is implemented.
"""

from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Mapping

from .model import AttackDefinition, CreatureDefinition, HealthMode


@dataclass(frozen=True)
class DamageAdjustment:
    """A printed resistance or weakness against one damage type."""

    damage_type: str
    value: int


@dataclass(frozen=True)
class MonsterActionProfile:
    """A monster-only rule that still needs an encounter procedure."""

    action_id: str
    name: str
    source_url: str
    action_cost: int | None = None
    trigger: str | None = None
    requirements: tuple[str, ...] = ()
    check: str | None = None
    increases_map: bool | None = None
    uses_current_map: bool | None = None
    strike_id: str | None = None
    extends_existing_grab_to_end_of_next_turn: bool = False


@dataclass(frozen=True)
class PublishedOpponentProfile:
    """Exact sourced profile fields that CreatureDefinition cannot yet hold."""

    definition: CreatureDefinition
    creature_traits: frozenset[str]
    equipment_ids: tuple[str, ...]
    condition_immunities: tuple[str, ...]
    damage_immunities: tuple[str, ...]
    resistances: tuple[DamageAdjustment, ...]
    weaknesses: tuple[DamageAdjustment, ...]
    void_healing: bool
    special_actions: tuple[MonsterActionProfile, ...]
    source_urls: tuple[str, ...]
    profile_notes: tuple[str, ...] = ()


SKELETON_GUARD_URL = "https://2e.aonprd.com/Monsters.aspx?ID=3193"
ZOMBIE_SHAMBLER_URL = "https://2e.aonprd.com/Monsters.aspx?ID=3249"
GRAB_URL = "https://2e.aonprd.com/MonsterAbilities.aspx?ID=45"


SKELETON_GUARD = PublishedOpponentProfile(
    definition=CreatureDefinition(
        definition_id="skeleton_guard_mc3193",
        name="Skeleton Guard",
        hp=4,
        ac=16,
        perception=2,
        land_speed_ft=25,
        attacks=(
            AttackDefinition(
                attack_id="scimitar",
                name="Scimitar",
                modifier=6,
                reach_ft=5,
                traits=frozenset({"attack", "melee", "forceful", "sweep"}),
                damage_type="slashing",
                damage_dice=(6,),
                damage_modifier=2,
                item_id="scimitar",
            ),
            AttackDefinition(
                attack_id="claw",
                name="Claw",
                modifier=6,
                reach_ft=5,
                traits=frozenset({"attack", "melee", "agile", "finesse"}),
                damage_type="slashing",
                damage_dice=(4,),
                damage_modifier=2,
                attack_attribute="dexterity",
                damage_attribute="strength",
                hands_required=0,
            ),
            AttackDefinition(
                attack_id="shortbow",
                name="Shortbow",
                modifier=6,
                reach_ft=0,
                traits=frozenset({"attack", "ranged", "deadly", "deadly-d10"}),
                damage_type="piercing",
                damage_dice=(6,),
                damage_modifier=0,
                item_id="shortbow",
                attack_attribute="dexterity",
                damage_attribute=None,
                range_increment_ft=60,
                max_range_ft=360,
                hands_required=1,
                free_hands_required=1,
                ammunition_id="arrow",
                deadly_die=10,
                reload=0,
            ),
        ),
        kind="ordinary_npc",
        health_mode=HealthMode.ORDINARY,
        abilities=("void_healing",),
        ability_modifiers=(
            ("strength", 2),
            ("dexterity", 4),
            ("constitution", 0),
            ("intelligence", -5),
            ("wisdom", 0),
            ("charisma", 0),
        ),
        skills=(("acrobatics", None, 6), ("athletics", None, 3)),
        saves=(("fortitude", None, 2), ("reflex", None, 8), ("will", None, 2)),
        senses=("darkvision",),
        sheet_notes=(
            "Monster Core level -1 Skeleton Guard; normal profile, not weak or elite.",
            "Scimitar carries forceful and sweep; neither trait is omitted from the profile.",
            "Fixed starter loadout: scimitar in hand; shortbow carried stowed with 20 arrows.",
            f"Source: {SKELETON_GUARD_URL}",
        ),
        size="medium",
        level=-1,
        ancestry="Skeleton",
        held_items=("scimitar",),
        stowed_items=("shortbow",),
        ammunition=(("arrow", 20),),
    ),
    creature_traits=frozenset({"mindless", "skeleton", "undead", "unholy"}),
    equipment_ids=("scimitar", "shortbow", "arrow"),
    condition_immunities=("bleed", "death_effects", "disease", "mental", "paralyzed", "poison", "unconscious"),
    damage_immunities=(),
    resistances=(
        DamageAdjustment("cold", 5),
        DamageAdjustment("electricity", 5),
        DamageAdjustment("fire", 5),
        DamageAdjustment("piercing", 5),
        DamageAdjustment("slashing", 5),
    ),
    weaknesses=(),
    void_healing=True,
    special_actions=(),
    source_urls=(SKELETON_GUARD_URL,),
    profile_notes=(
        "Perception +2; Acrobatics +6; Athletics +3.",
        "Mindless, Skeleton, Undead, and Unholy are creature traits; darkvision is a sense.",
        "Precision immunity and optional Collapse/Explosive Death are not part of this profile.",
        "Fixed starter loadout: scimitar in hand; shortbow carried stowed with 20 arrows.",
    ),
)


ZOMBIE_SHAMBLER = PublishedOpponentProfile(
    definition=CreatureDefinition(
        definition_id="zombie_shambler_mc3249",
        name="Zombie Shambler",
        hp=20,
        ac=12,
        perception=0,
        land_speed_ft=25,
        attacks=(
            AttackDefinition(
                attack_id="fist",
                name="Fist",
                modifier=7,
                reach_ft=5,
                traits=frozenset({"attack", "melee", "unarmed"}),
                damage_type="bludgeoning",
                damage_dice=(6,),
                damage_modifier=3,
                attack_attribute="strength",
                damage_attribute="strength",
                hands_required=0,
            ),
            AttackDefinition(
                attack_id="jaws",
                name="Zombie Bite (jaws)",
                modifier=7,
                reach_ft=5,
                traits=frozenset({"attack", "melee", "unarmed"}),
                damage_type="piercing",
                damage_dice=(8,),
                damage_modifier=3,
                attack_attribute="strength",
                damage_attribute="strength",
                hands_required=0,
            ),
        ),
        kind="ordinary_npc",
        health_mode=HealthMode.ORDINARY,
        abilities=("void_healing", "permanent_slowed_1", "cannot_react", "grab", "zombie_bite"),
        ability_modifiers=(
            ("strength", 3),
            ("dexterity", -2),
            ("constitution", 2),
            ("intelligence", -5),
            ("wisdom", 0),
            ("charisma", -2),
        ),
        skills=(("athletics", None, 7),),
        saves=(("fortitude", None, 6), ("reflex", None, 0), ("will", None, 2)),
        senses=("darkvision",),
        sheet_notes=(
            "Monster Core level -1 Zombie Shambler; normal profile, not weak or elite.",
            "Permanently slowed 1 and unable to use reactions.",
            "Fist is not the agile, nonlethal PC fist. A successful Fist Strike permits a separate Grab action.",
            "Zombie Bite is one action, requires a grabbed or restrained target, and makes the listed jaws Strike using normal MAP.",
            f"Sources: {ZOMBIE_SHAMBLER_URL}; Grab: {GRAB_URL}",
        ),
        size="medium",
        level=-1,
        ancestry="Zombie",
    ),
    creature_traits=frozenset({"mindless", "undead", "unholy", "zombie"}),
    equipment_ids=(),
    condition_immunities=("bleed", "death_effects", "disease", "mental", "paralyzed", "poison", "unconscious"),
    damage_immunities=(),
    resistances=(),
    weaknesses=(DamageAdjustment("slashing", 5), DamageAdjustment("vitality", 5)),
    void_healing=True,
    special_actions=(
        MonsterActionProfile(
            action_id="grab",
            name="Grab",
            source_url=GRAB_URL,
            action_cost=1,
            trigger="after_successful_fist_strike",
            requirements=("target_is_within_fist_reach",),
            check="athletics_vs_fortitude_dc",
            increases_map=False,
            uses_current_map=False,
            strike_id="fist",
            extends_existing_grab_to_end_of_next_turn=True,
        ),
        MonsterActionProfile(
            action_id="zombie_bite",
            name="Zombie Bite",
            source_url=ZOMBIE_SHAMBLER_URL,
            action_cost=1,
            requirements=("target_is_grabbed_or_restrained",),
            increases_map=True,
            uses_current_map=True,
            strike_id="jaws",
        ),
    ),
    source_urls=(ZOMBIE_SHAMBLER_URL, GRAB_URL),
    profile_notes=(
        "Perception +0; Athletics +7; speed 25 feet.",
        "Fist Strike has the separate Grab action; Grab attempts Athletics vs Fortitude DC and does not apply or increase MAP.",
        "Void damage does not itself heal undead; only an effect that says it heals undead does so.",
    ),
)


PUBLISHED_OPPONENT_PROFILES: Mapping[str, PublishedOpponentProfile] = MappingProxyType(
    {
        SKELETON_GUARD.definition.definition_id: SKELETON_GUARD,
        ZOMBIE_SHAMBLER.definition.definition_id: ZOMBIE_SHAMBLER,
    }
)

PUBLISHED_OPPONENT_DEFINITIONS: Mapping[str, CreatureDefinition] = MappingProxyType(
    {definition_id: profile.definition for definition_id, profile in PUBLISHED_OPPONENT_PROFILES.items()}
)
