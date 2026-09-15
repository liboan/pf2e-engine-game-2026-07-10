from __future__ import annotations

from pf2e.content import (
    CREATURES,
    FIGHTER_M,
    GUARD_DOG,
    S1_SETUP,
    S2_PACK_ATTACK_SETUP,
    S2_READY,
    S2_SETUP,
)
from pf2e.model import HealthMode


def test_s2_fighter_sheet_preserves_the_admitted_level_one_build() -> None:
    fighter = FIGHTER_M

    assert fighter.health_mode is HealthMode.PC
    assert (fighter.hp, fighter.ac, fighter.perception, fighter.land_speed_ft) == (21, 18, 6, 25)
    assert fighter.level == 1
    assert (fighter.ancestry, fighter.heritage, fighter.background, fighter.class_name) == (
        "Human",
        "Skilled Human",
        "Farmhand",
        "Fighter",
    )
    assert dict(fighter.ability_modifiers) == {
        "strength": 4,
        "dexterity": 1,
        "constitution": 3,
        "intelligence": 0,
        "wisdom": 1,
        "charisma": 0,
    }
    assert fighter.saves == (
        ("fortitude", "expert", 8),
        ("reflex", "expert", 6),
        ("will", "trained", 4),
    )
    assert fighter.hero_points == 1
    assert fighter.held_items == ("longsword",)
    assert fighter.worn_items == ("breastplate",)
    assert fighter.abilities == ("reactive_strike", "shield_block", "vicious_swing")
    assert fighter.feats == ("Natural Skill", "Assurance (Athletics)", "Vicious Swing")
    assert ("class_dc", "trained") in fighter.proficiencies
    assert any("Shield Block" in note and "no shield" in note for note in fighter.sheet_notes)


def test_fighter_attack_entries_keep_versatile_choice_and_fist_traits_visible() -> None:
    fighter = FIGHTER_M
    longsword, fist = fighter.attacks

    assert (longsword.attack_id, longsword.modifier, longsword.damage_dice, longsword.damage_modifier) == (
        "longsword",
        9,
        (8,),
        4,
    )
    assert longsword.damage_type == "slashing"
    assert longsword.item_id == "longsword"
    assert "versatile-p" in longsword.traits
    assert any("choose slashing or piercing for each Strike" in note for note in fighter.sheet_notes)
    assert (fist.attack_id, fist.modifier, fist.damage_type, fist.damage_dice, fist.damage_modifier) == (
        "fist",
        9,
        "bludgeoning",
        (4,),
        4,
    )
    assert {"agile", "finesse", "nonlethal", "unarmed"} <= fist.traits


def test_guard_dog_uses_printed_modifiers_and_has_no_pc_weapon_traits() -> None:
    dog = GUARD_DOG

    assert dog.health_mode is HealthMode.ORDINARY
    assert (dog.level, dog.size, dog.hp, dog.ac, dog.perception, dog.land_speed_ft) == (
        -1,
        "small",
        8,
        15,
        6,
        30,
    )
    assert dog.saves == (
        ("fortitude", None, 5),
        ("reflex", None, 7),
        ("will", None, 4),
    )
    assert dog.skills == (
        ("acrobatics", None, 5),
        ("athletics", None, 4),
        ("stealth", None, 5),
        ("survival", None, 4),
    )
    jaws = dog.attacks[0]
    assert (jaws.attack_id, jaws.modifier, jaws.damage_type, jaws.damage_dice, jaws.damage_modifier) == (
        "jaws",
        6,
        "piercing",
        (4,),
        1,
    )
    assert not {"agile", "finesse", "nonlethal"} & jaws.traits
    assert "pack_attack" in dog.abilities
    assert {"Low-light vision", "Imprecise scent 30 feet"} == set(dog.senses)


def test_s2_setup_and_three_dog_positioning_fixture_are_separate_from_s1() -> None:
    assert S1_SETUP.setup_id == "s1_duel"
    assert S2_SETUP.setup_id == "s2_fighters_vs_guard_dogs"
    assert [placement.definition_id for placement in S2_SETUP.placements] == [
        FIGHTER_M.definition_id,
        FIGHTER_M.definition_id,
        GUARD_DOG.definition_id,
        GUARD_DOG.definition_id,
    ]
    assert [placement.team for placement in S2_SETUP.placements] == ["blue", "blue", "red", "red"]
    assert len(S2_PACK_ATTACK_SETUP.placements) == 4
    target = next(item for item in S2_PACK_ATTACK_SETUP.placements if item.actor_id == "fighter_target")
    other_dogs = [item for item in S2_PACK_ATTACK_SETUP.placements if item.actor_id.startswith("guard_dog")]
    assert target.position == S2_PACK_ATTACK_SETUP.placements[0].position
    assert len(other_dogs) == 3
    assert all(max(abs(dog.position.x - target.position.x), abs(dog.position.y - target.position.y)) == 1 for dog in other_dogs)
    assert CREATURES[FIGHTER_M.definition_id] is FIGHTER_M
    assert CREATURES[GUARD_DOG.definition_id] is GUARD_DOG
    assert S2_READY is True
