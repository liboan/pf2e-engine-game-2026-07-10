from __future__ import annotations

from pf2e.content import (
    CREATURES,
    GUARD_DOG,
    MELEE_FIGHTER_M,
    S2_PC_DUEL_SETUP,
    S2_READY,
    S2_SETUP,
    S3_READY,
    S3_SETUP,
    SHORTBOW_FIGHTER_R,
    WARPRIEST_C,
    get_setup,
)
from pf2e.model import HealthMode


def test_fighter_r_sheet_preserves_shortbow_build_and_ammunition() -> None:
    fighter = SHORTBOW_FIGHTER_R

    assert fighter.health_mode is HealthMode.PC
    assert (fighter.hp, fighter.ac, fighter.perception, fighter.land_speed_ft) == (21, 18, 6, 25)
    assert dict(fighter.ability_modifiers) == {
        "strength": 1,
        "dexterity": 4,
        "constitution": 3,
        "intelligence": 0,
        "wisdom": 1,
        "charisma": 0,
    }
    assert fighter.saves == (
        ("fortitude", "expert", 8),
        ("reflex", "expert", 9),
        ("will", "trained", 4),
    )
    bow = next(attack for attack in fighter.attacks if attack.attack_id == "shortbow")
    assert (bow.modifier, bow.damage_dice, bow.damage_modifier, bow.damage_type) == (9, (6,), 0, "piercing")
    assert bow.attack_attribute == "dexterity"
    assert bow.damage_attribute is None
    assert (bow.range_increment_ft, bow.max_range_ft) == (60, 360)
    assert {"deadly", "deadly-d10"} <= bow.traits
    assert not {"propulsive", "volley"} & bow.traits
    assert (bow.hands_required, bow.free_hands_required, bow.ammunition_id, bow.deadly_die) == (
        1,
        1,
        "arrow",
        10,
    )
    assert fighter.held_items == ("shortbow",)
    assert fighter.worn_items == ("leather_armor", "longsword")
    assert fighter.ammunition == (("arrow", 20),)
    assert fighter.abilities == ("reactive_strike", "shield_block", "vicious_swing")
    assert ("advanced_weapons", "trained") in fighter.proficiencies
    assert ("unarmored_defense", "trained") in fighter.proficiencies
    assert dict((name, modifier) for name, _rank, modifier in fighter.skills) == {
        "acrobatics": 7,
        "athletics": 4,
        "crafting": 3,
        "farming_lore": 3,
        "intimidation": 3,
        "medicine": 4,
        "nature": 4,
        "society": 3,
        "survival": 4,
    }
    assert any("Longsword is carried" in note and "melee only" in note for note in fighter.sheet_notes)
    assert any("reload 0" in note for note in fighter.sheet_notes)
    assert any("neither propulsive nor volley" in note for note in fighter.sheet_notes)


def test_warpriest_sheet_keeps_fixed_divine_preparations_and_iomedae_choices() -> None:
    cleric = WARPRIEST_C

    assert cleric.health_mode is HealthMode.PC
    assert (cleric.hp, cleric.ac, cleric.perception, cleric.land_speed_ft) == (17, 18, 7, 25)
    assert (cleric.spell_attack, cleric.spell_dc, cleric.spell_attribute, cleric.spell_sanctification) == (
        7,
        17,
        "wisdom",
        "holy",
    )
    assert (cleric.ancestry, cleric.heritage, cleric.background, cleric.class_name, cleric.deity) == (
        "Human",
        "Skilled Human",
        "Farmhand",
        "Cleric",
        "Iomedae",
    )
    assert cleric.abilities == ("shield_block",)
    assert cleric.held_items == ("longsword",)
    assert cleric.worn_items == ("breastplate",)
    assert ("unarmored_defense", "trained") in cleric.proficiencies
    assert dict((name, modifier) for name, _rank, modifier in cleric.skills) == {
        "athletics": 6,
        "crafting": 3,
        "farming_lore": 3,
        "intimidation": 3,
        "medicine": 7,
        "nature": 7,
        "religion": 7,
        "society": 3,
        "survival": 7,
    }
    assert len([spell for spell in cleric.prepared_spells if spell.cantrip]) == 5
    assert {spell.spell_id for spell in cleric.prepared_spells if spell.cantrip} == {
        "divine_lance",
        "void_warp",
        "guidance",
        "stabilize",
        "read_aura",
    }
    ordinary = [spell for spell in cleric.prepared_spells if spell.source == "ordinary"]
    font = [spell for spell in cleric.prepared_spells if spell.source == "font"]
    assert len(ordinary) == 2 and {spell.spell_id for spell in ordinary} == {"heal"}
    assert len(font) == 4 and {spell.spell_id for spell in font} == {"heal"}
    assert len({spell.slot_id for spell in cleric.prepared_spells}) == 11
    assert all(spell.rank == 1 for spell in cleric.prepared_spells)
    assert any("Heal font" in note and "holy sanctification" in note for note in cleric.sheet_notes)
    assert any("cantrips are repeatable" in note for note in cleric.sheet_notes)
    assert any("No Deadly Simplicity" in note for note in cleric.sheet_notes)


def test_s3_setup_uses_the_existing_m_build_and_three_real_guard_dogs() -> None:
    assert MELEE_FIGHTER_M.definition_id in CREATURES
    assert GUARD_DOG.definition_id in CREATURES
    assert S2_READY is True
    assert S3_READY is True
    assert S2_SETUP.setup_id == "s2_fighters_vs_guard_dogs"
    assert S2_PC_DUEL_SETUP.setup_id == "s2_pc_duel_fixture"
    assert get_setup(S3_SETUP.setup_id) == S3_SETUP
    assert [placement.definition_id for placement in S3_SETUP.placements] == [
        MELEE_FIGHTER_M.definition_id,
        SHORTBOW_FIGHTER_R.definition_id,
        WARPRIEST_C.definition_id,
        GUARD_DOG.definition_id,
        GUARD_DOG.definition_id,
        GUARD_DOG.definition_id,
    ]
    assert [placement.team for placement in S3_SETUP.placements] == [
        "blue",
        "blue",
        "blue",
        "red",
        "red",
        "red",
    ]
