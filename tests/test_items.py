from dataclasses import FrozenInstanceError

import pytest

from pf2e.checks import Modifier, combine_modifiers
from pf2e.damage import DamageTerm, roll_damage_terms
from pf2e.items import (
    BUCKLER,
    MINOR_ELIXIR_OF_LIFE_ACTIVATION,
    STEEL_SHIELD,
    WOODEN_SHIELD,
    ArmorRuneProfile,
    ItemInstance,
    WeaponRuneProfile,
    armor_item_ac_bonus,
    armor_resilient_modifier,
    consume_item,
    item_after_activation,
    shield_ac_modifier,
    shield_block_result,
    shield_block_trigger_eligible,
    shield_integrity,
    weapon_potency_modifier,
    weapon_rune_dice,
)


def test_curated_common_shield_profiles_match_player_core() -> None:
    assert (BUCKLER.ac_bonus, BUCKLER.hardness, BUCKLER.max_hp, BUCKLER.broken_threshold) == (1, 3, 6, 3)
    assert (WOODEN_SHIELD.ac_bonus, WOODEN_SHIELD.hardness, WOODEN_SHIELD.max_hp, WOODEN_SHIELD.broken_threshold) == (
        2,
        3,
        12,
        6,
    )
    assert (STEEL_SHIELD.ac_bonus, STEEL_SHIELD.hardness, STEEL_SHIELD.max_hp, STEEL_SHIELD.broken_threshold) == (
        2,
        5,
        20,
        10,
    )
    assert BUCKLER.source_url == WOODEN_SHIELD.source_url == STEEL_SHIELD.source_url
    assert BUCKLER.source_url == "https://2e.aonprd.com/Shields.aspx"


def test_shield_ac_is_typed_and_only_available_when_raised_and_unbroken() -> None:
    assert shield_ac_modifier(STEEL_SHIELD, raised=False, shield_hp=20) is None
    assert shield_ac_modifier(STEEL_SHIELD, raised=True, shield_hp=10) is None
    shield_bonus = shield_ac_modifier(STEEL_SHIELD, raised=True, shield_hp=20)
    assert shield_bonus == Modifier(2, "circumstance", "steel_shield")
    assert combine_modifiers((shield_bonus, Modifier(1, "circumstance", "other circumstance bonus"))) == 2


def test_shield_block_requires_physical_attack_damage_not_energy_damage() -> None:
    # A magical weapon still deals physical damage with its Strike; the trigger
    # is gated on damage type and attack context, not a magic/nonmagic flag.
    assert shield_block_trigger_eligible("slashing", from_attack=True)
    assert shield_block_trigger_eligible("bludgeoning", from_attack=True)
    assert not shield_block_trigger_eligible("fire", from_attack=True)
    assert not shield_block_trigger_eligible("force", from_attack=True)
    assert not shield_block_trigger_eligible("piercing", from_attack=False)


def test_shield_block_applies_hardness_and_tracks_broken_shield_hp() -> None:
    result = shield_block_result(10, WOODEN_SHIELD, shield_hp=12)
    assert result.prevented == 3
    assert result.damage_to_actor == 7
    assert result.damage_to_shield == 7
    assert result.shield_hp == 5
    assert shield_integrity(WOODEN_SHIELD, result.shield_hp).broken
    assert not shield_integrity(WOODEN_SHIELD, result.shield_hp).destroyed
    with pytest.raises(ValueError, match="broken shield"):
        shield_block_result(1, WOODEN_SHIELD, shield_hp=result.shield_hp)


def test_shield_block_can_destroy_shield_while_actor_takes_same_remainder() -> None:
    result = shield_block_result(25, STEEL_SHIELD, shield_hp=20)
    assert (result.prevented, result.damage_to_actor, result.damage_to_shield, result.shield_hp) == (5, 20, 20, 0)
    integrity = shield_integrity(STEEL_SHIELD, result.shield_hp)
    assert integrity.broken and integrity.destroyed
    assert shield_ac_modifier(STEEL_SHIELD, raised=True, shield_hp=0) is None
    with pytest.raises(ValueError, match="broken shield"):
        shield_block_result(1, STEEL_SHIELD, shield_hp=0)


def test_object_immune_damage_contributes_to_actor_total_but_not_shield_hp() -> None:
    # GM convention: one Hardness reduction to the actor's post-IWR total;
    # object-immunity-filtered damage controls the shield's HP loss.
    mental = shield_block_result(12, STEEL_SHIELD, 20, shield_vulnerable_damage=8)
    assert (mental.damage_to_actor, mental.damage_to_shield, mental.shield_hp) == (7, 3, 17)
    poison = shield_block_result(11, STEEL_SHIELD, 20, shield_vulnerable_damage=3)
    assert (poison.damage_to_actor, poison.damage_to_shield, poison.shield_hp) == (6, 0, 20)
    fire = shield_block_result(12, STEEL_SHIELD, 20, shield_vulnerable_damage=12)
    assert (fire.damage_to_actor, fire.damage_to_shield, fire.shield_hp) == (7, 7, 13)


def test_armor_potency_augments_armor_item_bonus_and_resilient_stacks_by_type() -> None:
    runes = ArmorRuneProfile(potency=1, resilient_bonus=1)
    assert armor_item_ac_bonus(base_ac_bonus=4, profile=runes) == 5
    resilient = armor_resilient_modifier(runes)
    assert resilient == Modifier(1, "item", "resilient rune")
    assert combine_modifiers((resilient, Modifier(2, "item", "another save item"))) == 2


def test_weapon_potency_and_handwrap_striking_apply_to_unarmed_attack() -> None:
    wraps = WeaponRuneProfile(potency=1, striking_dice=2, handwraps=True)
    potency = weapon_potency_modifier(wraps, unarmed=True, source="handwraps")
    assert potency == Modifier(1, "item", "handwraps")
    assert weapon_rune_dice((4,), wraps, unarmed=True) == (4, 4)
    assert wraps.source_urls[-1] == "https://2e.aonprd.com/Equipment.aspx?ID=3086"
    ordinary_weapon_runes = WeaponRuneProfile(potency=1, striking_dice=2)
    assert weapon_potency_modifier(ordinary_weapon_runes, unarmed=True) is None
    assert weapon_rune_dice((4,), ordinary_weapon_runes, unarmed=True) == (4,)


def test_bestial_mutagen_keeps_handwrap_potency_but_excludes_striking_and_typed_bonuses_do_not_stack() -> None:
    wraps = WeaponRuneProfile(potency=1, striking_dice=2, handwraps=True)
    potency = weapon_potency_modifier(wraps, unarmed=True)
    mutagen_bonus = Modifier(1, "item", "bestial mutagen")
    assert combine_modifiers((potency, mutagen_bonus)) == 1
    assert weapon_rune_dice((4,), wraps, unarmed=True, striking_applies=False) == (4,)


def test_striking_adds_weapon_dice_that_remain_in_ordinary_critical_doubling() -> None:
    profile = WeaponRuneProfile(potency=1, striking_dice=2)
    dice = weapon_rune_dice((8,), profile)
    result = roll_damage_terms((DamageTerm("longsword", "slashing", dice, modifier=4),), lambda _sides: 8, critical=True)
    assert result.components[0].dice == (8, 8)
    assert result.components[0].amount == 40
    assert result.total == 40


def test_item_instances_are_frozen_and_reject_stacked_mutable_copies() -> None:
    item = ItemInstance("shield-1", "steel_shield", hp=20)
    with pytest.raises(FrozenInstanceError):
        item.hp = 5
    with pytest.raises(ValueError, match="quantity 1"):
        ItemInstance("wands", "charged_item", quantity=2, charges=4)


def test_elixir_activation_consumes_one_item_and_rejects_mismatches_or_reuse() -> None:
    elixir = ItemInstance("elixir-1", "elixir_of_life_minor")
    consumed = item_after_activation(elixir, MINOR_ELIXIR_OF_LIFE_ACTIVATION)
    assert consumed.quantity == 0
    assert elixir.quantity == 1
    assert MINOR_ELIXIR_OF_LIFE_ACTIVATION.action_cost == 1
    assert MINOR_ELIXIR_OF_LIFE_ACTIVATION.action == "Interact"
    assert MINOR_ELIXIR_OF_LIFE_ACTIVATION.hands_required == 1
    with pytest.raises(ValueError, match="does not match"):
        item_after_activation(ItemInstance("other", "lesser_antidote"), MINOR_ELIXIR_OF_LIFE_ACTIVATION)
    with pytest.raises(ValueError, match="insufficient item quantity"):
        item_after_activation(consumed, MINOR_ELIXIR_OF_LIFE_ACTIVATION)


def test_charge_consumption_is_exact_and_rejection_keeps_original_snapshot() -> None:
    wand = ItemInstance("wand-1", "wand_of_something", charges=2)
    after_one = consume_item(wand, charges=1)
    assert after_one.charges == 1
    assert wand.charges == 2
    assert consume_item(after_one, charges=1).charges == 0
    with pytest.raises(ValueError, match="insufficient charges"):
        consume_item(after_one, charges=2)
    with pytest.raises(ValueError, match="does not track charges"):
        consume_item(ItemInstance("potion-1", "potion"), charges=1)
    assert after_one.charges == 1
