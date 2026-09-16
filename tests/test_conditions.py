"""Source-informed boundaries for the pure condition projections."""

import pytest

from pf2e.checks import Modifier, combine_modifiers
from pf2e.conditions import (
    ActionContext,
    CheckContext,
    ConditionValue,
    condition_modifiers,
    condition_restrictions,
    effective_condition_value,
)


def _condition(kind: str, value: int = 1, source_id: str | None = None) -> ConditionValue:
    return ConditionValue(kind, value, source_id or f"{kind}:source")


def _modifiers(conditions: tuple[ConditionValue, ...], statistic: str, attribute: str | None, *, traits=frozenset()):
    return condition_modifiers(conditions, CheckContext(statistic, attribute, traits))


def test_clumsy_and_enfeebled_use_explicit_abilities_not_attack_names() -> None:
    conditions = (_condition("clumsy", 1, "centipede_venom"), _condition("enfeebled", 2, "cosmos_curse"))

    strength_attack = _modifiers(conditions, "attack", "strength")
    dexterity_attack = _modifiers(conditions, "attack", "dexterity")
    strength_damage = _modifiers(conditions, "damage", "strength")
    dexterity_damage = _modifiers(conditions, "damage", "dexterity")
    untyped_attack = _modifiers(conditions, "attack", None)

    assert strength_attack == (Modifier(-2, "status", "condition:enfeebled:cosmos_curse"),)
    assert dexterity_attack == (Modifier(-1, "status", "condition:clumsy:centipede_venom"),)
    assert strength_damage == (Modifier(-2, "status", "condition:enfeebled:cosmos_curse"),)
    # Current errata extends clumsy to Dexterity-based damage rolls.
    assert dexterity_damage == (Modifier(-1, "status", "condition:clumsy:centipede_venom"),)
    # A missing ability stays missing; the helper never guesses from "attack".
    assert untyped_attack == ()


def test_clumsy_also_applies_to_reflex_and_ac_when_attribute_is_unspecified() -> None:
    clumsy = (_condition("clumsy", 2, "ancestors_curse"),)

    reflex = _modifiers(clumsy, "reflex", None)
    armor_class = _modifiers(clumsy, "armor_class", None)
    fortitude = _modifiers(clumsy, "fortitude", None)

    assert reflex == (Modifier(-2, "status", "condition:clumsy:ancestors_curse"),)
    assert armor_class == (Modifier(-2, "status", "condition:clumsy:ancestors_curse"),)
    assert fortitude == ()


def test_frightened_and_sickened_penalize_checks_and_dcs_but_not_damage() -> None:
    conditions = (_condition("frightened", 2, "fear"), _condition("sickened", 1, "arsenic"))

    attack = _modifiers(conditions, "attack", "strength")
    armor_class = _modifiers(conditions, "armor_class", "dexterity")
    damage = _modifiers(conditions, "damage", "strength")

    assert attack == (
        Modifier(-2, "status", "condition:frightened:fear"),
        Modifier(-1, "status", "condition:sickened:arsenic"),
    )
    assert combine_modifiers(attack) == -2  # same-type penalties use the worst value
    assert combine_modifiers(armor_class) == -2
    assert damage == ()


def test_drained_and_fatigued_have_their_exact_save_and_ac_scope() -> None:
    conditions = (_condition("drained", 2, "soul_siphon"), _condition("fatigued", 1, "centipede_venom"))

    fortitude = _modifiers(conditions, "fortitude", None)
    reflex = _modifiers(conditions, "reflex", None)
    will = _modifiers(conditions, "will", None)
    athletics = _modifiers(conditions, "athletics", "strength")
    ac = _modifiers(conditions, "armor_class", None)

    assert fortitude == (
        Modifier(-2, "status", "condition:drained:soul_siphon"),
        Modifier(-1, "status", "condition:fatigued:centipede_venom"),
    )
    assert combine_modifiers(fortitude) == -2
    assert reflex == (Modifier(-1, "status", "condition:fatigued:centipede_venom"),)
    assert will == (Modifier(-1, "status", "condition:fatigued:centipede_venom"),)
    assert athletics == ()
    assert ac == (Modifier(-1, "status", "condition:fatigued:centipede_venom"),)


def test_stupefied_tracks_mental_attributes_and_explicit_spell_statistics() -> None:
    stupefied = (_condition("stupefied", 2, "spell_effect"),)

    assert _modifiers(stupefied, "will", None) == (
        Modifier(-2, "status", "condition:stupefied:spell_effect"),
    )
    assert _modifiers(stupefied, "spell_attack", None) == (
        Modifier(-2, "status", "condition:stupefied:spell_effect"),
    )
    assert _modifiers(stupefied, "spell_dc", "charisma") == (
        Modifier(-2, "status", "condition:stupefied:spell_effect"),
    )
    assert _modifiers(stupefied, "fortitude", "constitution") == ()
    assert _modifiers(stupefied, "damage", "wisdom") == ()


def test_fascinated_penalizes_perception_and_skill_checks() -> None:
    fascinated = (_condition("fascinated", source_id="performance"),)

    assert _modifiers(fascinated, "perception", "wisdom") == (
        Modifier(-2, "status", "condition:fascinated:performance"),
    )
    assert _modifiers(fascinated, "stealth", "dexterity") == (
        Modifier(-2, "status", "condition:fascinated:performance"),
    )


def test_off_guard_retains_each_cause_and_typed_stacking_does_not_multiply_it() -> None:
    conditions = (
        _condition("off_guard", source_id="flanking:ally_a"),
        _condition("off_guard", source_id="feint:rogue_b"),
        _condition("prone", source_id="trip:rogue_b"),
    )

    ac_modifiers = _modifiers(conditions, "armor_class", None)
    attack_modifiers = _modifiers(conditions, "attack", "strength", traits=frozenset({"attack"}))

    assert {modifier.source for modifier in ac_modifiers} == {
        "condition:off_guard:flanking:ally_a",
        "condition:off_guard:feint:rogue_b",
        "condition:prone:trip:rogue_b",
    }
    assert all(modifier.modifier_type == "circumstance" for modifier in ac_modifiers)
    assert combine_modifiers(ac_modifiers) == -2
    assert attack_modifiers == (Modifier(-2, "circumstance", "condition:prone:trip:rogue_b"),)


def test_value_projection_uses_highest_retained_source_and_unknowns_fail_closed() -> None:
    conditions = (
        _condition("frightened", 1, "fear_a"),
        _condition("frightened", 2, "fear_b"),
        _condition("sickened", 3, "poison"),
    )

    assert effective_condition_value(conditions, "frightened") == 2
    assert effective_condition_value(conditions, "drained") == 0
    assert effective_condition_value(conditions, "sickened") == 3
    with pytest.raises(ValueError, match="unsupported condition kind"):
        effective_condition_value(conditions, "unconscious")
    with pytest.raises(ValueError, match="unsupported condition kind"):
        condition_modifiers((_condition("unconscious"),), CheckContext("armor_class", None))


def test_zero_valued_conditions_have_no_effect_and_presence_conditions_use_a_sentinel() -> None:
    zeroed = (_condition("sickened", 0, "removed"),)
    assert condition_modifiers(zeroed, CheckContext("athletics", "strength")) == ()
    assert condition_restrictions(zeroed, ActionContext("ingest")) == ()
    assert effective_condition_value(zeroed, "sickened") == 0

    with pytest.raises(ValueError, match="presence value"):
        condition_modifiers((_condition("off_guard", 2),), CheckContext("armor_class", None))


def test_restrictions_return_stable_reasons_without_rolling() -> None:
    conditions = (
        _condition("dazzled", source_id="spray_of_stars"),
        _condition("stupefied", 2, "spell_effect"),
        _condition("grabbed", source_id="grapple"),
    )

    reasons = condition_restrictions(
        conditions,
        ActionContext("cast_spell", frozenset({"manipulate", "concentrate"})),
    )

    assert reasons == (
        "dazzled_target_flat_check_dc5_required",
        "grabbed_manipulate_flat_check_dc5_required",
        "stupefied_cast_flat_check_dc5_plus_value_required",
    )


@pytest.mark.parametrize(
    ("conditions", "action", "traits", "expected"),
    [
        ((_condition("sickened", 1, "arsenic"),), "ingest", frozenset(), ("sickened_willing_ingestion_prohibited",)),
        ((_condition("fatigued", 1, "venom"),), "traveling_exploration_activity", frozenset(), ("fatigued_traveling_exploration_prohibited",)),
        ((_condition("prone", source_id="trip"),), "stride", frozenset({"move"}), ("prone_move_action_prohibited",)),
        ((_condition("prone", source_id="trip"),), "crawl", frozenset({"move"}), ()),
        ((_condition("prone", source_id="trip"),), "strike", frozenset({"attack"}), ()),
        ((_condition("immobilized", source_id="grab"),), "stride", frozenset({"move"}), ("immobilized_move_action_prohibited",)),
        ((_condition("grabbed", source_id="grapple"),), "stride", frozenset({"move"}), ("immobilized_move_action_prohibited",)),
        ((_condition("restrained", source_id="net"),), "strike", frozenset({"attack"}), ("restrained_attack_or_manipulate_prohibited",)),
        ((_condition("restrained", source_id="net"),), "stride", frozenset({"move"}), ("immobilized_move_action_prohibited",)),
        ((_condition("restrained", source_id="net"),), "escape", frozenset({"attack", "manipulate"}), ()),
        ((_condition("paralyzed", source_id="spell"),), "strike", frozenset({"attack"}), ("paralyzed_requires_mind_only_action",)),
        ((_condition("paralyzed", source_id="spell"),), "recall_knowledge", frozenset(), ()),
        ((_condition("fascinated", source_id="performance"),), "cast_spell", frozenset({"concentrate"}), ("fascinated_concentrate_subject_relation_required",)),
    ],
)
def test_action_restrictions_are_context_specific(conditions, action, traits, expected) -> None:
    assert condition_restrictions(conditions, ActionContext(action, traits)) == expected


def test_invalid_condition_records_are_rejected() -> None:
    with pytest.raises(ValueError, match="non-negative integers"):
        condition_modifiers((_condition("frightened", -1),), CheckContext("attack", "strength"))
    with pytest.raises(ValueError, match="source_id"):
        condition_modifiers((ConditionValue("frightened", 1, ""),), CheckContext("attack", "strength"))
