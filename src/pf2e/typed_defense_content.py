"""A fully authored living diagnostic foe for typed-damage encounters.

The Waystone Sentinel is original local test content, not a copied bestiary
creature. Its defenses are intentionally visible and exercise one physical
weakness, a broad damage resistance, and one damage-type immunity.
Damage ordering and broad-choice behavior follow Player Core pp. 408–409 as
revised by the Spring 2026 errata:
https://2e.aonprd.com/Rules.aspx?ID=2265
https://paizo.com/blog/spring-errata-2026
"""

from __future__ import annotations

from dataclasses import replace
from types import MappingProxyType
from typing import Mapping

from .barbarian_content import BARBARIAN_SLICE1_CHARACTER, DRAGON_BARBARIAN_CHARACTERS
from .damage import DamageDefense
from .model import (
    AttackDefinition,
    CreatureDefinition,
    CreaturePlacement,
    EncounterSetup,
    HealthMode,
    Position,
)


WAYSTONE_SENTINEL = CreatureDefinition(
    definition_id="typed_defense_waystone_sentinel",
    name="Waystone Sentinel",
    hp=30,
    ac=16,
    perception=4,
    land_speed_ft=25,
    attacks=(
        AttackDefinition(
            attack_id="cinderbrand_strike",
            name="Cinderbrand Strike",
            modifier=6,
            reach_ft=5,
            traits=frozenset({"attack", "melee", "magical"}),
            damage_type="fire",
            damage_dice=(6,),
            damage_modifier=2,
        ),
    ),
    kind="ordinary_npc",
    health_mode=HealthMode.ORDINARY,
    ability_modifiers=(("str", 2), ("dex", 2), ("con", 3), ("int", 0), ("wis", 1), ("cha", 0)),
    skills=(("athletics", "trained", 5), ("crafting", "trained", 4)),
    saves=(("fortitude", "trained", 7), ("reflex", "trained", 6), ("will", "trained", 4)),
    proficiencies=(("armor", "trained"), ("simple_weapons", "trained")),
    senses=("low-light vision",),
    sheet_notes=(
        "Original living level 1 diagnostic opponent; not a published creature.",
        "Its ward grants resistance 2 to all damage; its cracked flank has slashing weakness 3.",
        "A separate ward makes it immune to void damage.",
    ),
    size="medium",
    level=1,
    languages=("Common",),
    damage_defenses=(
        DamageDefense("weakness", "slashing", 3, source="cracked flank"),
        DamageDefense("resistance", "all", 2, source="waystone ward"),
        DamageDefense("immunity", "void", source="void ward"),
    ),
)

# A lower-HP diagnostic variant lets the legal level-1 Warpriest complete a
# healthy defended-spell encounter without changing spell damage or injecting
# damage before play.
WAYSTONE_SPELL_SENTINEL = replace(
    WAYSTONE_SENTINEL,
    definition_id="typed_defense_waystone_spell_sentinel",
    name="Waystone Spell Sentinel",
    hp=14,
    sheet_notes=WAYSTONE_SENTINEL.sheet_notes + (
        "Spell-path diagnostic variant with 14 maximum HP; it starts healthy.",
    ),
)


_diabolic = DRAGON_BARBARIAN_CHARACTERS["diabolic"]
TYPED_DEFENSE_DRAGON_SETUP = EncounterSetup(
    setup_id="typed_defenses_diabolic_dragon_test",
    name="Diabolic Dragon Barbarian vs. Waystone Sentinel",
    width=7,
    height=5,
    placements=(
        CreaturePlacement(
            "dragon_barbarian",
            _diabolic.definition.definition_id,
            "Diabolic Dragon Barbarian",
            "blue",
            Position(2, 2),
        ),
        CreaturePlacement(
            "waystone_sentinel",
            WAYSTONE_SENTINEL.definition_id,
            "Waystone Sentinel",
            "red",
            Position(3, 2),
        ),
    ),
)

TYPED_DEFENSE_BEAR_SETUP = EncounterSetup(
    setup_id="typed_defenses_bear_temp_hp_test",
    name="Bear Barbarian vs. Waystone Sentinel",
    width=7,
    height=5,
    placements=(
        CreaturePlacement(
            "barbarian_test",
            BARBARIAN_SLICE1_CHARACTER.definition.definition_id,
            "Bear Barbarian",
            "blue",
            Position(2, 2),
        ),
        CreaturePlacement(
            "waystone_sentinel",
            WAYSTONE_SENTINEL.definition_id,
            "Waystone Sentinel",
            "red",
            Position(3, 2),
        ),
    ),
)

TYPED_DEFENSE_SPELL_SETUP = EncounterSetup(
    setup_id="typed_defenses_warpriest_spell_test",
    name="Warpriest vs. Waystone Sentinel Spell Test",
    width=7,
    height=5,
    placements=(
        CreaturePlacement(
            "cleric_c",
            "warpriest_c_level_1",
            "Warpriest C",
            "blue",
            Position(2, 2),
        ),
        CreaturePlacement(
            "waystone_sentinel",
            WAYSTONE_SPELL_SENTINEL.definition_id,
            "Waystone Spell Sentinel",
            "red",
            Position(3, 2),
        ),
    ),
)

TYPED_DEFENSE_HEROIC_SETUP = EncounterSetup(
    setup_id="typed_defenses_heroic_recovery_test",
    name="Diabolic Dragon Barbarian vs. Ward-Granted Warpriest Test",
    width=7,
    height=5,
    placements=(
        CreaturePlacement(
            "dragon_barbarian",
            _diabolic.definition.definition_id,
            "Diabolic Dragon Barbarian",
            "blue",
            Position(2, 2),
        ),
        CreaturePlacement(
            "warded_warpriest",
            "warpriest_c_typed_defense_test_grant",
            "Ward-Granted Warpriest",
            "red",
            Position(3, 2),
        ),
    ),
)

TYPED_DEFENSE_SETUPS: Mapping[str, EncounterSetup] = MappingProxyType(
    {
        TYPED_DEFENSE_DRAGON_SETUP.setup_id: TYPED_DEFENSE_DRAGON_SETUP,
        TYPED_DEFENSE_BEAR_SETUP.setup_id: TYPED_DEFENSE_BEAR_SETUP,
        TYPED_DEFENSE_SPELL_SETUP.setup_id: TYPED_DEFENSE_SPELL_SETUP,
        TYPED_DEFENSE_HEROIC_SETUP.setup_id: TYPED_DEFENSE_HEROIC_SETUP,
    }
)
