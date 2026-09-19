from __future__ import annotations

import pytest

from pf2e.content import (
    CREATURES,
    EXPANSION_CREATURES,
    EXPANSION_INITIAL_STATES,
    EXPANSION_SETUPS,
    EXPANSION_SKILL_ACTIONS,
    FIRST_FAMILIES_UNDEAD_STARTER,
    SETUPS,
    get_definition,
    get_setup,
)
from pf2e.opponent_content import SKELETON_GUARD, ZOMBIE_SHAMBLER
from pf2e.ranger_monk_content import MONK, RANGER_MONK_SETUPS, RANGER_PRECISION
from pf2e.barbarian_content import (
    ANIMAL_BARBARIAN_DEFINITIONS,
    ANIMAL_BARBARIAN_INITIAL_STATES,
    ANIMAL_BARBARIAN_SETUPS,
    BARBARIAN_DEFINITIONS,
    BARBARIAN_SLICE1_CHARACTER,
    BARBARIAN_TEST_ENEMY,
    BARBARIAN_TEST_SETUP,
    DRAGON_BARBARIAN_SETUPS,
)


def test_expansion_catalog_excludes_the_accepted_bear_runtime_slice() -> None:
    assert not (set(EXPANSION_SETUPS) & set(SETUPS))
    assert not (set(EXPANSION_CREATURES) & set(CREATURES))
    assert set(DRAGON_BARBARIAN_SETUPS) <= set(SETUPS)
    assert set(ANIMAL_BARBARIAN_SETUPS) <= set(SETUPS)

    assert len(EXPANSION_SETUPS) == 2
    assert BARBARIAN_TEST_SETUP.setup_id not in EXPANSION_SETUPS
    assert get_setup(BARBARIAN_TEST_SETUP.setup_id) == BARBARIAN_TEST_SETUP
    assert BARBARIAN_SLICE1_CHARACTER.definition.definition_id in CREATURES
    assert BARBARIAN_TEST_ENEMY.definition_id in CREATURES
    for definition in BARBARIAN_DEFINITIONS:
        assert CREATURES[definition.definition_id] == definition
    for setup in DRAGON_BARBARIAN_SETUPS.values():
        assert SETUPS[setup.setup_id] == setup
    for definition in ANIMAL_BARBARIAN_DEFINITIONS:
        assert CREATURES[definition.definition_id] == definition
        assert definition.definition_id in ANIMAL_BARBARIAN_INITIAL_STATES
    for setup in ANIMAL_BARBARIAN_SETUPS.values():
        assert SETUPS[setup.setup_id] == setup
    assert RANGER_MONK_SETUPS[0].setup_id in EXPANSION_SETUPS
    assert RANGER_PRECISION.definition_id not in EXPANSION_CREATURES
    assert MONK.definition_id not in EXPANSION_CREATURES
    assert FIRST_FAMILIES_UNDEAD_STARTER.setup_id in EXPANSION_SETUPS
    assert EXPANSION_SETUPS[FIRST_FAMILIES_UNDEAD_STARTER.setup_id] == FIRST_FAMILIES_UNDEAD_STARTER
    assert EXPANSION_CREATURES[SKELETON_GUARD.definition.definition_id] == SKELETON_GUARD.definition

    with pytest.raises(ValueError, match="unknown encounter setup"):
        get_setup(FIRST_FAMILIES_UNDEAD_STARTER.setup_id)
    with pytest.raises(ValueError, match="unknown creature definition"):
        get_definition(SKELETON_GUARD.definition.definition_id)


def test_first_family_fixtures_are_fixed_and_start_with_full_definition_hp() -> None:
    for setup in EXPANSION_SETUPS.values():
        assert len({placement.actor_id for placement in setup.placements}) == len(setup.placements)
        for placement in setup.placements:
            definition = EXPANSION_CREATURES.get(placement.definition_id, CREATURES.get(placement.definition_id))
            assert definition is not None
            assert definition.hp > 0
            assert definition.health_mode.value in {"ordinary", "pc"}

    starter_ids = {placement.definition_id for placement in FIRST_FAMILIES_UNDEAD_STARTER.placements}
    assert len(FIRST_FAMILIES_UNDEAD_STARTER.placements) == 6
    assert SKELETON_GUARD.definition.definition_id in starter_ids
    assert ZOMBIE_SHAMBLER.definition.definition_id in starter_ids
    assert not EXPANSION_INITIAL_STATES


def test_skeleton_guard_profile_preserves_published_attacks_and_defenses() -> None:
    definition = SKELETON_GUARD.definition
    assert definition.level == -1
    assert (definition.hp, definition.ac, definition.perception, definition.land_speed_ft) == (4, 16, 2, 25)
    assert dict(definition.ability_modifiers) == {
        "strength": 2,
        "dexterity": 4,
        "constitution": 0,
        "intelligence": -5,
        "wisdom": 0,
        "charisma": 0,
    }
    assert dict((name, modifier) for name, _rank, modifier in definition.skills) == {
        "acrobatics": 6, "athletics": 3
    }
    assert {name: (rank, modifier) for name, rank, modifier in definition.saves} == {
        "fortitude": (None, 2), "reflex": (None, 8), "will": (None, 2)
    }
    assert {r.damage_type: r.value for r in SKELETON_GUARD.resistances} == {
        "cold": 5,
        "electricity": 5,
        "fire": 5,
        "piercing": 5,
        "slashing": 5,
    }
    assert SKELETON_GUARD.condition_immunities == (
        "bleed", "death_effects", "disease", "mental", "paralyzed", "poison", "unconscious"
    )
    assert SKELETON_GUARD.creature_traits == frozenset({"mindless", "skeleton", "undead", "unholy"})
    assert SKELETON_GUARD.equipment_ids == ("scimitar", "shortbow", "arrow")
    assert dict(definition.ammunition) == {"arrow": 20}
    assert definition.held_items == ("scimitar",)
    assert definition.stowed_items == ("shortbow",)
    assert any("shortbow carried stowed" in note for note in definition.sheet_notes)

    attacks = {attack.attack_id: attack for attack in definition.attacks}
    assert {"forceful", "sweep"} <= attacks["scimitar"].traits
    assert {"agile", "finesse"} <= attacks["claw"].traits
    bow = attacks["shortbow"]
    assert (bow.modifier, bow.damage_dice, bow.damage_modifier, bow.damage_type) == (6, (6,), 0, "piercing")
    assert (bow.range_increment_ft, bow.max_range_ft, bow.deadly_die, bow.ammunition_id) == (60, 360, 10, "arrow")
    assert bow.reload == 0
    assert "reload-0" not in bow.traits
    assert SKELETON_GUARD.void_healing is True
    assert all("Monsters.aspx?ID=3193" in source for source in SKELETON_GUARD.source_urls)


def test_zombie_shambler_keeps_slow_grab_bite_and_weakness_distinct() -> None:
    definition = ZOMBIE_SHAMBLER.definition
    assert definition.level == -1
    assert (definition.hp, definition.ac, definition.perception, definition.land_speed_ft) == (20, 12, 0, 25)
    assert dict(definition.ability_modifiers) == {
        "strength": 3,
        "dexterity": -2,
        "constitution": 2,
        "intelligence": -5,
        "wisdom": 0,
        "charisma": -2,
    }
    assert dict((name, modifier) for name, _rank, modifier in definition.skills) == {"athletics": 7}
    assert {name: modifier for name, _rank, modifier in definition.saves} == {
        "fortitude": 6, "reflex": 0, "will": 2
    }
    assert ZOMBIE_SHAMBLER.creature_traits == frozenset({"mindless", "undead", "unholy", "zombie"})
    assert definition.senses == ("darkvision",)
    assert definition.abilities == (
        "void_healing", "permanent_slowed_1", "cannot_react", "grab", "zombie_bite"
    )
    assert {(item.damage_type, item.value) for item in ZOMBIE_SHAMBLER.weaknesses} == {
        ("slashing", 5), ("vitality", 5)
    }
    assert "poison" in ZOMBIE_SHAMBLER.condition_immunities
    assert ZOMBIE_SHAMBLER.void_healing is True

    attacks = {attack.attack_id: attack for attack in definition.attacks}
    fist = attacks["fist"]
    assert (fist.damage_type, fist.damage_dice, fist.damage_modifier) == ("bludgeoning", (6,), 3)
    assert not {"agile", "nonlethal"} & fist.traits
    bite = attacks["jaws"]
    assert (bite.damage_type, bite.damage_dice, bite.damage_modifier) == ("piercing", (8,), 3)

    special = {ability.action_id: ability for ability in ZOMBIE_SHAMBLER.special_actions}
    grab = special["grab"]
    assert (
        grab.trigger,
        grab.check,
        grab.increases_map,
        grab.uses_current_map,
        grab.strike_id,
        grab.extends_existing_grab_to_end_of_next_turn,
    ) == (
        "after_successful_fist_strike", "athletics_vs_fortitude_dc", False, False, "fist", True
    )
    zombie_bite = special["zombie_bite"]
    assert zombie_bite.action_cost == 1
    assert zombie_bite.requirements == ("target_is_grabbed_or_restrained",)
    assert (zombie_bite.increases_map, zombie_bite.uses_current_map, zombie_bite.strike_id) == (
        True, True, "jaws"
    )
    assert any("Monsters.aspx?ID=3249" in source for source in ZOMBIE_SHAMBLER.source_urls)


def test_staged_setups_stay_out_of_the_playable_registry() -> None:
    assert set(EXPANSION_SETUPS).isdisjoint(SETUPS)
    assert set(EXPANSION_CREATURES).isdisjoint(CREATURES)
    with pytest.raises(ValueError, match="unknown encounter setup"):
        get_setup(FIRST_FAMILIES_UNDEAD_STARTER.setup_id)
    with pytest.raises(ValueError, match="unknown creature definition"):
        get_definition(SKELETON_GUARD.definition.definition_id)
    assert {"trip", "grapple", "escape", "demoralize"} == set(EXPANSION_SKILL_ACTIONS)
    assert {"void_healing", "permanent_slowed_1", "cannot_react", "grab", "zombie_bite"} <= set(
        ZOMBIE_SHAMBLER.definition.abilities
    )
