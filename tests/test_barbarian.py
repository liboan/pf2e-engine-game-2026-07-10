from dataclasses import replace

import pytest

from pf2e.barbarian import (
    ANIMALS_BY_ID,
    ANIMAL_INSTINCT,
    GAIN_NEW_RAGE_TEMP_HP,
    DRAGONS_BY_ID,
    DRAGON_CHOICES,
    DRAGON_INSTINCT,
    FURY_INSTINCT,
    GIANT_INSTINCT,
    GIANT_WEAPONS_BY_ID,
    KEEP_EXISTING_TEMP_HP,
    MOMENT_OF_CLARITY,
    RAGING_INTIMIDATION,
    SPIRIT_INSTINCT,
    SUPERSTITION_INSTINCT,
    BarbarianBuildChoices,
    BarbarianChoiceError,
    action_allowed_while_raging,
    activate_rage,
    action_traits_with_instinct_features,
    attack_allowed_during_rage,
    build_barbarian_state,
    end_rage,
    expire_rage,
    giant_clumsy_value,
    has_intimidating_glare,
    rage_action_traits,
    rage_damage_bonus,
    rage_strike_adjustment,
    rage_temporary_hp_choice_required,
    quick_tempered_eligible,
    record_spellcast_witness,
    record_superstition_anathema_violation,
    record_superstition_magic_acceptance,
    recenter_superstition,
    remove_superstition_magic_effect,
    superstition_abilities_enabled,
    superstition_frightened_floor,
    superstition_save_modifier,
    validate_barbarian_state,
    valid_rage_modes,
    witnessed_recent_spellcaster,
)
from pf2e.barbarian_content import (
    ANIMAL_BARBARIAN_CHARACTERS,
    ANIMAL_BARBARIAN_DEFINITIONS,
    ANIMAL_BARBARIAN_INITIAL_STATES,
    ANIMAL_BARBARIAN_SETUPS,
    BARBARIAN_DEFINITIONS,
    BARBARIAN_INITIAL_STATES,
    BARBARIAN_SAMPLE_CHARACTERS,
    BARBARIAN_SLICE1_CHARACTER,
    DRAGON_BARBARIAN_CHARACTERS,
    DRAGON_BARBARIAN_DEFINITIONS,
    DRAGON_BARBARIAN_INITIAL_STATES,
    DRAGON_BARBARIAN_SETUPS,
    build_barbarian,
)
from pf2e.checks import Modifier


def state_for(instinct: str, *, animal: str = "bear", dragon: str = "diabolic"):
    return build_barbarian_state(
        BarbarianBuildChoices(
            instinct,
            class_feat_id=RAGING_INTIMIDATION,
            animal_choice=animal if instinct == ANIMAL_INSTINCT else None,
            dragon_choice=dragon if instinct == DRAGON_INSTINCT else None,
            giant_weapon_id=("giant_large_longsword" if instinct == GIANT_INSTINCT else None),
            bonus_feat_id=MOMENT_OF_CLARITY if instinct == FURY_INSTINCT else None,
        )
    )


def rage(
    state,
    *,
    now=0,
    mode="base",
    current_temp=0,
    current_temp_source="spell:ward",
    current_temp_expiry=1000,
    temporary_hp_choice=None,
    hp=10,
    max_hp=23,
):
    return activate_rage(
        state,
        level=1,
        constitution_modifier=3,
        now_seconds=now,
        source_id=f"rage:barbarian:{state.next_rage_instance}" if temporary_hp_choice != KEEP_EXISTING_TEMP_HP else None,
        mode_id=mode,
        current_temporary_hp=current_temp,
        current_temporary_hp_source_id=current_temp_source if current_temp else None,
        current_temporary_hp_expires_at_seconds=current_temp_expiry if current_temp else None,
        temporary_hp_choice=temporary_hp_choice,
        current_hp=hp,
        maximum_hp=max_hp,
    )


def test_all_six_instinct_builds_have_valid_fixed_level_one_choices_and_stats():
    assert set(BARBARIAN_SAMPLE_CHARACTERS) == {
        "animal", "dragon", "fury", "giant", "spirit", "superstition"
    }
    for character in BARBARIAN_SAMPLE_CHARACTERS.values():
        validate_barbarian_state(character.barbarian_state)
        assert character.definition.level == 1
        assert character.definition.class_name == "Barbarian"
        assert character.definition.hp == 23
        assert character.definition.proficiencies
        assert character.definition.abilities[0:2] == ("rage", "quick_tempered")
    fury = BARBARIAN_SAMPLE_CHARACTERS["fury"].barbarian_state
    assert fury.class_feat_id == RAGING_INTIMIDATION
    assert fury.bonus_feat_id == MOMENT_OF_CLARITY
    assert not has_intimidating_glare(fury)
    assert has_intimidating_glare(fury, intimidation_trained=True)
    assert not has_intimidating_glare(fury, intimidation_trained=False)
    assert has_intimidating_glare(
        BARBARIAN_SAMPLE_CHARACTERS["animal"].barbarian_state,
        intimidation_trained=True,
    )
    with pytest.raises(BarbarianChoiceError, match="requires its additional"):
        build_barbarian_state(
            BarbarianBuildChoices(FURY_INSTINCT, class_feat_id=RAGING_INTIMIDATION)
        )


def test_bear_and_dragon_runtime_definitions_keep_the_reviewed_legal_sheets():
    bear = BARBARIAN_SLICE1_CHARACTER
    definition = bear.definition
    assert definition.ancestry == "Human"
    assert definition.heritage == "Skilled Human"
    assert definition.background == "Warrior"
    assert definition.languages == ("Common",)
    assert definition.feats == (
        "Natural Skill", "Intimidating Glare", "Raging Intimidation"
    )
    assert definition.hp == 23 and definition.ac == 18
    assert definition.ability_modifiers == (
        ("strength", 4), ("dexterity", 1), ("constitution", 3),
        ("intelligence", 0), ("wisdom", 1), ("charisma", 0),
    )
    assert dict((name, modifier) for name, _rank, modifier in definition.skills) == {
        "acrobatics": 4,
        "athletics": 7,
        "crafting": 3,
        "intimidation": 3,
        "medicine": 4,
        "nature": 4,
        "society": 3,
        "survival": 4,
        "warfare_lore": 3,
    }
    assert definition.carried_item_bulk == (("breastplate", 2), ("longsword", 1))
    assert definition.armor_category == "medium"
    assert bear.loadout.remaining_money_gp == 6
    assert bear.loadout.total_bulk == 3
    assert BARBARIAN_DEFINITIONS == (
        definition,
        *DRAGON_BARBARIAN_DEFINITIONS,
        *ANIMAL_BARBARIAN_DEFINITIONS,
    )
    assert tuple(BARBARIAN_INITIAL_STATES) == (
        definition.definition_id,
        *DRAGON_BARBARIAN_INITIAL_STATES,
        *ANIMAL_BARBARIAN_INITIAL_STATES,
    )
    fist = next(attack for attack in definition.attacks if attack.attack_id == "fist")
    assert {"agile", "finesse", "nonlethal", "unarmed"} <= fist.traits
    assert fist.damage_modifier == 4
    assert fist.attack_attribute == fist.damage_attribute == "strength"
    jaws = next(attack for attack in definition.attacks if attack.attack_id == "animal_bear_jaws")
    claw = next(attack for attack in definition.attacks if attack.attack_id == "animal_bear_claw")
    assert jaws.damage_dice == (10,) and jaws.damage_modifier == 4
    assert claw.damage_dice == (6,) and "agile" in claw.traits
    assert BARBARIAN_SAMPLE_CHARACTERS["fury"].definition.feats[-2:] == (
        "Raging Intimidation", "Moment of Clarity"
    )

    assert tuple(DRAGON_BARBARIAN_CHARACTERS) == tuple(
        dragon.dragon_id for dragon in DRAGON_CHOICES
    )
    assert len(DRAGON_BARBARIAN_SETUPS) == len(DRAGON_CHOICES) == 8
    for dragon_id, character in DRAGON_BARBARIAN_CHARACTERS.items():
        dragon = DRAGONS_BY_ID[dragon_id]
        dragon_definition = character.definition
        assert dragon_definition.definition_id == f"barbarian_dragon_{dragon_id}"
        assert character.barbarian_state.dragon_choice == dragon_id
        assert character.barbarian_state.class_feat_id == RAGING_INTIMIDATION
        assert dragon_definition.class_name == "Barbarian"
        assert dragon_definition.level == 1
        assert (dragon_definition.ancestry, dragon_definition.heritage, dragon_definition.background) == (
            "Human", "Skilled Human", "Warrior"
        )
        assert dragon_definition.languages == ("Common",)
        assert dragon_definition.feats == (
            "Natural Skill", "Intimidating Glare", "Raging Intimidation"
        )
        assert (dragon_definition.hp, dragon_definition.ac) == (23, 18)
        assert dragon_definition.ability_modifiers == definition.ability_modifiers
        assert dragon_definition.skills == definition.skills
        assert dragon_definition.saves == definition.saves
        assert dragon_definition.proficiencies == definition.proficiencies
        assert dragon_definition.attacks == definition.attacks[:2]
        assert dragon_definition.armor_category == "medium"
        assert dragon_definition.held_items == ("longsword",)
        assert dragon_definition.worn_items == ("breastplate",)
        assert dragon_definition.carried_item_bulk == (("breastplate", 2), ("longsword", 1))
        assert set(dragon_definition.abilities) == {
            "rage", "quick_tempered", "barbarian_instinct:dragon", "draconic_rage"
        }
        assert character.loadout.starting_money_gp == 15
        assert [(item.item_id, item.paid_price_gp, item.bulk) for item in character.loadout.items] == [
            ("breastplate", 8, 2), ("longsword", 1, 1)
        ]
        assert character.loadout.remaining_money_gp == 6
        assert character.loadout.total_bulk == 3
        assert DRAGON_BARBARIAN_SETUPS[f"barbarian_dragon_{dragon_id}_rage_test"].setup_id == (
            f"barbarian_dragon_{dragon_id}_rage_test"
        )


def test_cat_and_frog_are_fixed_legal_animal_builds_with_brawling_metadata():
    assert tuple(ANIMAL_BARBARIAN_CHARACTERS) == ("cat", "frog")
    assert len(ANIMAL_BARBARIAN_SETUPS) == len(ANIMAL_BARBARIAN_DEFINITIONS) == 2
    for animal_id, character in ANIMAL_BARBARIAN_CHARACTERS.items():
        definition = character.definition
        state = character.barbarian_state
        assert definition.definition_id == f"barbarian_animal_{animal_id}"
        assert state.instinct_id == ANIMAL_INSTINCT and state.animal_choice == animal_id
        assert state.class_feat_id == RAGING_INTIMIDATION
        assert definition.class_name == "Barbarian" and definition.level == 1
        assert (definition.ancestry, definition.heritage, definition.background) == (
            "Human", "Skilled Human", "Warrior"
        )
        assert (definition.hp, definition.ac) == (23, 18)
        assert definition.ability_modifiers == BARBARIAN_SLICE1_CHARACTER.definition.ability_modifiers
        assert definition.skills == BARBARIAN_SLICE1_CHARACTER.definition.skills
        assert definition.saves == BARBARIAN_SLICE1_CHARACTER.definition.saves
        assert definition.proficiencies == BARBARIAN_SLICE1_CHARACTER.definition.proficiencies
        assert definition.feats == BARBARIAN_SLICE1_CHARACTER.definition.feats
        assert definition.armor_category == "medium"
        assert definition.held_items == ("longsword",)
        assert definition.worn_items == ("breastplate",)
        assert character.loadout.remaining_money_gp == 6
        animal_attacks = definition.attacks[2:]
        profiles = ANIMALS_BY_ID[animal_id].attacks
        assert len(animal_attacks) == len(profiles) == 2
        for attack, profile in zip(animal_attacks, profiles, strict=True):
            assert (attack.attack_id, attack.damage_type, attack.damage_dice) == (
                profile.attack_id, profile.damage_type, profile.damage_dice
            )
            assert attack.damage_modifier == 4
            assert attack.traits == frozenset({"attack", "melee", "unarmed", *profile.traits})
            assert profile.weapon_group == "brawling"
        assert any("brawling weapon group" in note for note in definition.sheet_notes)
        assert any("does not model level-5 Weapon Specialization" in note for note in definition.sheet_notes)
        setup_id = f"barbarian_animal_{animal_id}_rage_test"
        assert ANIMAL_BARBARIAN_SETUPS[setup_id].setup_id == setup_id
        assert ANIMAL_BARBARIAN_INITIAL_STATES[definition.definition_id] == state


def test_every_printed_animal_and_dragon_choice_has_its_correct_profile():
    assert len(ANIMALS_BY_ID) == 9
    assert len(DRAGONS_BY_ID) == 8
    assert all(
        attack.weapon_group == "brawling"
        for animal in ANIMALS_BY_ID.values()
        for attack in animal.attacks
    )
    assert ANIMALS_BY_ID["frog"].attacks[1].damage_dice == (6,)
    assert "agile" in ANIMALS_BY_ID["frog"].attacks[1].traits
    assert "grapple" in ANIMALS_BY_ID["deer"].attacks[0].traits
    assert "grapple" in ANIMALS_BY_ID["shark"].attacks[0].traits
    assert "trip" in ANIMALS_BY_ID["wolf"].attacks[0].traits
    for dragon_id, dragon in DRAGONS_BY_ID.items():
        state = state_for(DRAGON_INSTINCT, dragon=dragon_id)
        mode = next(mode for mode in valid_rage_modes(state) if mode.mode_id == "dragon_damage")
        assert mode.damage_type == dragon.damage_type
        assert dragon.tradition in mode.action_traits
        assert dragon.damage_type in mode.action_traits
    with pytest.raises(BarbarianChoiceError, match="nine"):
        build_barbarian_state(BarbarianBuildChoices(ANIMAL_INSTINCT, animal_choice="elk"))
    with pytest.raises(BarbarianChoiceError, match="eight"):
        build_barbarian_state(BarbarianBuildChoices(DRAGON_INSTINCT, dragon_choice="red"))


def test_rage_activation_traits_modes_and_temporary_hp_lock():
    animal = rage(state_for(ANIMAL_INSTINCT))
    assert animal.temporary_hp_to_grant == 4
    assert animal.temporary_hp_source_id == "rage:barbarian:1"
    assert animal.rage_traits == frozenset(
        {"barbarian", "concentrate", "emotion", "mental", "morph", "primal"}
    )
    assert rage_action_traits(state_for(ANIMAL_INSTINCT), "base") == animal.rage_traits
    assert animal.state.rage.expires_at_seconds == 60
    assert action_allowed_while_raging(animal.state, "seek", frozenset({"concentrate"}))
    assert not action_allowed_while_raging(animal.state, "recall_knowledge", frozenset({"concentrate"}))
    demoralize_traits = frozenset({"concentrate", "emotion", "fear", "mental"})
    assert "rage" not in action_traits_with_instinct_features(
        animal.state, "demoralize", demoralize_traits
    )
    assert "rage" in action_traits_with_instinct_features(
        animal.state, "demoralize", demoralize_traits, intimidation_trained=True
    )

    ended = end_rage(animal.state, now_seconds=0)
    assert ended.temporary_hp_source_to_clear == "rage:barbarian:1"
    assert ended.state.rage_temp_hp_available_at_seconds == 60
    blocked = rage(ended.state, now=59)
    assert blocked.state.is_raging
    assert blocked.temporary_hp_to_grant == 0
    after_blocked = end_rage(blocked.state, now_seconds=59).state
    assert rage(after_blocked, now=118).temporary_hp_to_grant == 0
    regranted = rage(after_blocked, now=119)
    assert regranted.temporary_hp_to_grant == 4
    assert regranted.temporary_hp_source_id == "rage:barbarian:2"
    assert expire_rage(animal.state, now_seconds=59, unconscious=False, encounter_ended=False) is None
    assert expire_rage(animal.state, now_seconds=60, unconscious=False, encounter_ended=False).state.rage is None
    assert expire_rage(animal.state, now_seconds=1, unconscious=True, encounter_ended=False).state.rage is None
    with pytest.raises(BarbarianChoiceError, match="fatigued"):
        activate_rage(state_for(ANIMAL_INSTINCT), level=1, constitution_modifier=3,
                      now_seconds=0, source_id="r", fatigued=True)
    with pytest.raises(BarbarianChoiceError, match="already raging"):
        activate_rage(animal.state, level=1, constitution_modifier=3, now_seconds=1, source_id="r")

    dragon_state = state_for(DRAGON_INSTINCT)
    dragon = rage(dragon_state, mode="dragon_damage")
    assert dragon.state.rage.damage_type == "fire"
    assert {"divine", "fire"} <= dragon.rage_traits
    spirit = rage(state_for(SPIRIT_INSTINCT), mode="spirit_damage")
    assert spirit.state.rage.ghost_touch
    assert {"divine", "spirit"} <= spirit.rage_traits
    with pytest.raises(BarbarianChoiceError, match="not available"):
        rage(state_for(ANIMAL_INSTINCT), mode="spirit_damage")


def test_instinct_damage_is_a_real_typed_strike_adjustment():
    animal = rage(state_for(ANIMAL_INSTINCT)).state
    assert rage_damage_bonus(animal, attack_traits=frozenset(), is_melee=True) == 2
    assert rage_damage_bonus(animal, attack_traits=frozenset({"agile"}), is_melee=True) == 1
    assert rage_damage_bonus(animal, attack_traits=frozenset(), is_melee=False) == 0
    assert not attack_allowed_during_rage(animal, attack_is_weapon=True, attack_id="longsword")
    assert attack_allowed_during_rage(animal, attack_is_weapon=False, attack_id="animal_bear_jaws")
    locked = rage_strike_adjustment(
        animal,
        attack_id="longsword",
        attack_damage_type="bludgeoning",
        attack_traits=frozenset({"melee"}),
        attack_is_weapon=True,
        is_melee=True,
        wielded_item_id="longsword",
        target_actor_id="enemy",
        now_seconds=0,
    )
    assert not locked.allowed and locked.damage_term is None

    fury = rage(state_for(FURY_INSTINCT)).state
    assert rage_damage_bonus(fury, attack_traits=frozenset(), is_melee=True) == 3
    assert rage_damage_bonus(fury, attack_traits=frozenset({"agile"}), is_melee=True) == 1
    giant = rage(state_for(GIANT_INSTINCT)).state
    assert rage_damage_bonus(giant, attack_traits=frozenset(), is_melee=True,
                             wielded_item_id="giant_large_longsword") == 6
    assert rage_damage_bonus(giant, attack_traits=frozenset(), is_melee=True,
                             wielded_item_id="warhammer") == 2
    assert giant_clumsy_value(state_for(GIANT_INSTINCT), ("giant_large_longsword",), in_combat=True) == 1
    assert giant_clumsy_value(state_for(GIANT_INSTINCT), (), in_combat=True) == 0

    dragon = rage(state_for(DRAGON_INSTINCT), mode="dragon_damage").state
    dragon_strike = rage_strike_adjustment(
        dragon,
        attack_id="longsword",
        attack_damage_type="bludgeoning",
        attack_traits=frozenset({"melee", "agile"}),
        attack_is_weapon=True,
        is_melee=True,
        wielded_item_id="longsword",
        target_actor_id="enemy",
        now_seconds=0,
    )
    assert dragon_strike.damage_term.damage_type == "fire"
    assert dragon_strike.damage_term.modifier == 2
    assert dragon_strike.ghost_touch is False
    spirit = rage(state_for(SPIRIT_INSTINCT), mode="spirit_damage").state
    spirit_strike = rage_strike_adjustment(
        spirit,
        attack_id="fist",
        attack_damage_type="bludgeoning",
        attack_traits=frozenset({"melee", "unarmed"}),
        attack_is_weapon=False,
        is_melee=True,
        wielded_item_id=None,
        target_actor_id="enemy",
        now_seconds=0,
    )
    assert spirit_strike.damage_term.damage_type == "spirit"
    assert spirit_strike.damage_term.modifier == 3
    assert spirit_strike.ghost_touch


def test_superstition_temporary_hp_healing_magic_witness_and_anathema_context():
    state = state_for(SUPERSTITION_INSTINCT)
    activation = rage(state, hp=20, max_hp=23)
    assert activation.temporary_hp_to_grant == 4
    assert activation.healing_to_apply == 3
    assert activation.state.superstition_heal_available_at_seconds == 600
    assert superstition_save_modifier(activation.state, against_magic=True) == Modifier(
        2, "status", "Superstition Rage against magic"
    )
    assert superstition_save_modifier(activation.state, against_magic=False) is None

    assert rage_temporary_hp_choice_required(
        state, level=1, constitution_modifier=3, now_seconds=0, current_temporary_hp=5
    )
    with pytest.raises(BarbarianChoiceError, match="Choose whether"):
        rage(state, current_temp=5, hp=20)
    kept = rage(state, current_temp=5, temporary_hp_choice=KEEP_EXISTING_TEMP_HP, hp=20)
    assert kept.temporary_hp_to_grant == 0 and kept.healing_to_apply == 0
    gained_lower_pool = rage(state, current_temp=5, temporary_hp_choice=GAIN_NEW_RAGE_TEMP_HP, hp=20)
    assert gained_lower_pool.temporary_hp_to_grant == 4
    assert gained_lower_pool.healing_to_apply == 3
    gained_equal_pool = rage(state, current_temp=4, temporary_hp_choice=GAIN_NEW_RAGE_TEMP_HP, hp=20)
    assert gained_equal_pool.temporary_hp_to_grant == 4
    assert gained_equal_pool.temporary_hp_source_id == "rage:barbarian:1"
    assert gained_equal_pool.temporary_hp_expires_at_seconds == 60
    assert not rage_temporary_hp_choice_required(
        replace(state, rage_temp_hp_available_at_seconds=60),
        level=1,
        constitution_modifier=3,
        now_seconds=59,
        current_temporary_hp=5,
    )
    full_hp = rage(state, hp=23)
    assert full_hp.temporary_hp_to_grant == 4
    assert full_hp.healing_to_apply == 0
    assert full_hp.state.superstition_heal_available_at_seconds == 600

    witnessed = record_spellcast_witness(state, "wizard", now_seconds=100)
    assert witnessed_recent_spellcaster(witnessed, "wizard", now_seconds=3699)
    assert not witnessed_recent_spellcaster(witnessed, "wizard", now_seconds=3700)
    super_rage = rage(witnessed, now=100).state
    assert rage_damage_bonus(
        super_rage,
        attack_traits=frozenset(),
        is_melee=True,
        target_actor_id="wizard",
        now_seconds=200,
    ) == 4
    assert rage_damage_bonus(
        super_rage,
        attack_traits=frozenset(),
        is_melee=True,
        target_actor_id="wizard",
        now_seconds=3700,
    ) == 3

    accepted = record_superstition_magic_acceptance(
        super_rage,
        effect_id="accepted-bless",
        expires_at_seconds=500,
        while_raging=True,
        willing=True,
    )
    assert superstition_frightened_floor(accepted, "accepted-bless") == 1
    assert superstition_frightened_floor(remove_superstition_magic_effect(accepted, "accepted-bless"),
                                         "accepted-bless") == 0
    unwilling = record_superstition_magic_acceptance(
        super_rage,
        effect_id="unwanted",
        expires_at_seconds=500,
        while_raging=True,
        willing=False,
    )
    assert superstition_frightened_floor(unwilling, "unwanted") == 0

    violated = record_superstition_anathema_violation(state, downtime_day=4)
    assert not superstition_abilities_enabled(violated)
    assert superstition_save_modifier(rage(violated).state, against_magic=True) is None
    with pytest.raises(BarbarianChoiceError, match="full day"):
        recenter_superstition(violated, completed_downtime_day=4)
    restored = recenter_superstition(violated, completed_downtime_day=5)
    assert superstition_abilities_enabled(restored)
    validate_barbarian_state(restored)


def test_giant_oversized_weapon_grant_uses_a_reviewed_fixed_profile():
    weapon = GIANT_WEAPONS_BY_ID["giant_large_longsword"]
    assert weapon.price_gp == 1
    assert weapon.large_price_gp == 2
    assert weapon.bulk == 2
    assert weapon.hands_required == 1
    assert weapon.damage_dice == (8,)
    assert "versatile-p" in weapon.traits
    giant = build_barbarian(instinct_id=GIANT_INSTINCT, giant_weapon_id=weapon.weapon_id)
    assert giant.definition.held_items == (weapon.weapon_id,)
    assert giant.barbarian_state.giant_weapon_id == weapon.weapon_id
    assert "free Titan Mauler weapon" in giant.definition.attacks[0].name
    assert giant.definition.attacks[0].damage_dice == (8,)
    assert giant.definition.attacks[0].reach_ft == 5
    assert giant.loadout.remaining_money_gp == 7
    with pytest.raises(BarbarianChoiceError, match="reviewed"):
        build_barbarian_state(BarbarianBuildChoices(GIANT_INSTINCT, giant_weapon_id="large_uncommon_greataxe"))


def test_quick_tempered_rejects_an_actor_already_raging():
    assert quick_tempered_eligible(
        initiative_trigger=True,
        fatigued=False,
        encumbered=False,
        wearing_heavy_armor=False,
        is_raging=False,
    )
    assert not quick_tempered_eligible(
        initiative_trigger=True,
        fatigued=False,
        encumbered=False,
        wearing_heavy_armor=False,
        is_raging=True,
    )
