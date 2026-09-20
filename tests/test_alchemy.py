from dataclasses import replace

import pytest

from pf2e.alchemy import (
    FIELD_BOMBER,
    FIELD_CHIRURGEON,
    FIELD_MUTAGENIST,
    FIELD_TOXICOLOGIST,
    AlchemyBuildChoices,
    AlchemyRuleError,
    QuickAlchemyRequest,
    advanced_alchemy_capacity,
    bomber_splash_targets,
    build_alchemy_state,
    daily_prepare_alchemy,
    field_vial_profile,
    gain_mutagenist_temporary_hp,
    perform_quick_alchemy,
    quick_alchemy_effect_duration,
    recover_versatile_vials,
    validate_alchemy_activation_window,
)
from pf2e.alchemy_content import (
    ALCHEMIST_LEVEL_1_FEATS_BY_ID,
    ALCHEMIST_LEVEL_1_FEAT_MENU,
    ALCHEMIST_FORMULAS,
    ALCHEMIST_FORMULAS_BY_ID,
    BombFacts,
    ElixirFacts,
    MutagenFacts,
    PoisonFacts,
)


FIELD_PAIRS = {
    FIELD_BOMBER: ("acid_flask_lesser", "bottled_lightning_lesser"),
    FIELD_CHIRURGEON: ("antidote_lesser", "antiplague_lesser"),
    FIELD_MUTAGENIST: ("bestial_mutagen_lesser", "cognitive_mutagen_lesser"),
    FIELD_TOXICOLOGIST: ("arsenic", "giant_centipede_venom"),
}


def build_state(field=FIELD_BOMBER, *, intelligence=4, feat=None):
    field_formulas = FIELD_PAIRS[field]
    all_formulas = tuple(ALCHEMIST_FORMULAS_BY_ID)
    known = tuple(dict.fromkeys((*field_formulas, *all_formulas)))[:8]
    return build_alchemy_state(
        AlchemyBuildChoices(
            research_field=field,
            field_formula_ids=field_formulas,
            known_formula_ids=known,
            intelligence_modifier=intelligence,
            selected_level_1_feat=feat,
        )
    )


def test_catalog_is_the_selected_w2_formula_catalog_with_source_links():
    assert len(ALCHEMIST_FORMULAS) == 14
    assert len(ALCHEMIST_FORMULAS_BY_ID) == 14
    assert all(formula.source_url.startswith("https://2e.aonprd.com/") for formula in ALCHEMIST_FORMULAS)
    assert {formula.level for formula in ALCHEMIST_FORMULAS} == {1, 2}
    assert {formula.category for formula in ALCHEMIST_FORMULAS} == {"bomb", "healing_elixir", "elixir", "mutagen", "poison"}
    assert set(ALCHEMIST_LEVEL_1_FEAT_MENU) == {"quick_bomber", "far_lobber"}
    quick_bomber = ALCHEMIST_LEVEL_1_FEATS_BY_ID["quick_bomber"]
    far_lobber = ALCHEMIST_LEVEL_1_FEATS_BY_ID["far_lobber"]
    assert quick_bomber.action_cost == 1 and quick_bomber.includes_strike
    assert quick_bomber.only_strike_advances_map and quick_bomber.quick_vial_eligible
    assert far_lobber.bomb_range_increment_ft == 30


@pytest.mark.parametrize("field", tuple(FIELD_PAIRS))
def test_each_field_requires_two_matching_known_formulas_and_builds_literal_state(field):
    state = build_state(field, feat="quick_bomber")
    assert state.research_field == field
    assert state.field_formula_ids == FIELD_PAIRS[field]
    assert set(state.field_formula_ids) <= set(state.known_formula_ids)
    assert state.vial_capacity == state.stored_vials == 6
    assert advanced_alchemy_capacity(state) == 8


def test_build_rejects_missing_field_formula_wrong_category_and_unselected_formula_count():
    valid = build_state()
    with pytest.raises(AlchemyRuleError) as missing:
        build_alchemy_state(
            AlchemyBuildChoices(
                FIELD_BOMBER,
                ("acid_flask_lesser", "frost_vial_lesser"),
                ("acid_flask_lesser", "bottled_lightning_lesser", "elixir_of_life_minor", "antidote_lesser", "antiplague_lesser", "bestial_mutagen_lesser", "cognitive_mutagen_lesser", "giant_centipede_venom"),
                4,
            )
        )
    assert missing.value.reason == "field_formula_not_known"

    with pytest.raises(AlchemyRuleError) as wrong:
        build_alchemy_state(
            AlchemyBuildChoices(FIELD_CHIRURGEON, ("acid_flask_lesser", "antiplague_lesser"), valid.known_formula_ids, 4)
        )
    assert wrong.value.reason == "wrong_field_formula"

    with pytest.raises(AlchemyRuleError) as count:
        build_alchemy_state(AlchemyBuildChoices(FIELD_BOMBER, FIELD_PAIRS[FIELD_BOMBER], valid.known_formula_ids[:7], 4))
    assert count.value.reason == "invalid_formula_book_size"


def test_daily_preparation_spends_only_advanced_alchemy_capacity_and_refreshes_vials():
    state = build_state()
    quick = perform_quick_alchemy(
        state,
        QuickAlchemyRequest("create_consumable", "alchemist", 100, True, True, "acid_flask_lesser", creator_turn_occurrence=1),
    )
    assert quick.state.stored_vials == 5
    prepared = daily_prepare_alchemy(
        quick.state,
        ("acid_flask_lesser",) * 8,
        creator_actor_id="alchemist",
        preparation_id="day-2",
        now_seconds=200,
    )
    assert prepared.state.stored_vials == 6
    assert prepared.state.daily_preparation_id == "day-2"
    assert prepared.expired_preparation_id == "initial"
    assert len(prepared.items) == 8
    assert len({item.instance_id for item in prepared.items}) == 8
    assert all(item.creation_kind == "advanced_alchemy" and item.expires_at_seconds == 200 + 86400 for item in prepared.items)
    assert advanced_alchemy_capacity(state) == 8

    with pytest.raises(AlchemyRuleError) as over:
        daily_prepare_alchemy(
            state,
            ("acid_flask_lesser",) * 9,
            creator_actor_id="alchemist",
            preparation_id="day-over",
            now_seconds=200,
        )
    assert over.value.reason == "advanced_alchemy_capacity_exceeded"


def test_daily_preparation_rejects_unknown_formula_without_changing_state():
    state = build_state()
    with pytest.raises(AlchemyRuleError) as error:
        daily_prepare_alchemy(
            state,
            ("not_known",),
            creator_actor_id="alchemist",
            preparation_id="day-2",
            now_seconds=200,
        )
    assert error.value.reason == "unknown_formula"
    assert state.stored_vials == state.vial_capacity
    assert state.daily_preparation_id == "initial"


def test_vials_recover_two_per_ten_exploration_minutes_with_partial_progress_and_cap():
    state = replace(build_state(), stored_vials=0)
    state = recover_versatile_vials(state, 599)
    assert state.stored_vials == 0
    assert state.exploration_seconds_toward_vial_recovery == 599
    state = recover_versatile_vials(state, 1)
    assert state.stored_vials == 2
    assert state.exploration_seconds_toward_vial_recovery == 0
    state = recover_versatile_vials(state, 1200)
    assert state.stored_vials == 6
    assert state.exploration_seconds_toward_vial_recovery == 0
    assert recover_versatile_vials(state, 599) == replace(state, exploration_seconds_toward_vial_recovery=0)


def test_quick_consumable_requires_toolkit_and_hand_then_spends_one_stored_vial():
    state = build_state()
    request = QuickAlchemyRequest("create_consumable", "alchemist", 100, True, True, "acid_flask_lesser", creator_turn_occurrence=3)
    result = perform_quick_alchemy(state, request)
    assert result.action_cost == 1
    assert result.action_traits == frozenset({"alchemist", "manipulate"})
    assert result.state.stored_vials == 5
    assert result.item.activation_deadline == "creator_next_turn_start"
    assert result.item.creator_turn_occurrence == 3

    for invalid in (
        replace(request, worn_or_held_toolkit=False),
        replace(request, free_hand=False),
        replace(request, formula_id="arsenic"),
    ):
        with pytest.raises(AlchemyRuleError):
            perform_quick_alchemy(state, invalid)
    assert state.stored_vials == 6


def test_quick_vial_does_not_spend_stock_and_expires_at_current_turn_end():
    state = build_state()
    result = perform_quick_alchemy(
        state,
        QuickAlchemyRequest("quick_vial", "alchemist", 100, True, True, creator_turn_id="turn-7"),
    )
    assert result.state.stored_vials == state.stored_vials
    assert result.state.next_creation_sequence == state.next_creation_sequence + 1
    assert result.item.temporary_vial is True
    assert result.item.activation_deadline == "creator_current_turn_end"
    validate_alchemy_activation_window(
        result.item,
        active_preparation_id="initial",
        now_seconds=101,
        current_turn_id="turn-7",
        creator_current_turn_active=True,
    )
    with pytest.raises(AlchemyRuleError) as expired:
        validate_alchemy_activation_window(
            result.item,
            active_preparation_id="initial",
            now_seconds=101,
            current_turn_id="turn-7",
            creator_current_turn_active=False,
        )
    assert expired.value.reason == "quick_vial_activation_expired"


def test_activation_windows_expire_quick_consumables_at_next_start_or_preparation_or_24_hours():
    state = build_state()
    quick = perform_quick_alchemy(
        state,
        QuickAlchemyRequest("create_consumable", "alchemist", 100, True, True, "acid_flask_lesser", creator_turn_occurrence=4),
    ).item
    validate_alchemy_activation_window(
        quick,
        active_preparation_id="initial",
        now_seconds=100 + 86399,
        creator_turn_occurrence=4,
    )
    for facts in (
        {"creator_turn_occurrence": 5},
        {"creator_turn_occurrence": 4, "active_preparation_id": "day-2"},
        {"creator_turn_occurrence": 4, "now_seconds": 100 + 86400},
    ):
        args = {"active_preparation_id": "initial", "now_seconds": 101, "creator_turn_occurrence": 4, **facts}
        with pytest.raises(AlchemyRuleError):
            validate_alchemy_activation_window(quick, **args)


def test_quick_alchemy_caps_only_long_effect_durations():
    assert quick_alchemy_effect_duration(60) == 60
    assert quick_alchemy_effect_duration(600) == 600
    assert quick_alchemy_effect_duration(6 * 60 * 60) == 600


def test_formula_facts_preserve_bomb_damage_elixir_and_mutagen_details():
    fire = ALCHEMIST_FORMULAS_BY_ID["alchemists_fire_lesser"].facts
    acid = ALCHEMIST_FORMULAS_BY_ID["acid_flask_lesser"].facts
    lightning = ALCHEMIST_FORMULAS_BY_ID["bottled_lightning_lesser"].facts
    frost = ALCHEMIST_FORMULAS_BY_ID["frost_vial_lesser"].facts
    assert isinstance(fire, BombFacts) and (fire.initial_damage_dice, fire.persistent_damage_flat, fire.splash_damage) == ((8,), 1, 1)
    assert isinstance(acid, BombFacts) and (acid.initial_damage_flat, acid.persistent_damage_dice, acid.splash_damage) == (1, (6,), 1)
    assert isinstance(lightning, BombFacts) and lightning.on_hit_effect_deadline == "thrower_next_turn_start"
    assert isinstance(frost, BombFacts) and frost.on_hit_effect_deadline == "target_next_turn_end"
    assert fire.strength_damage is acid.strength_damage is False

    life = ALCHEMIST_FORMULAS_BY_ID["elixir_of_life_minor"].facts
    bestial = ALCHEMIST_FORMULAS_BY_ID["bestial_mutagen_lesser"].facts
    cognitive = ALCHEMIST_FORMULAS_BY_ID["cognitive_mutagen_lesser"].facts
    assert isinstance(life, ElixirFacts) and life.healing_dice == (6,) and not life.coagulant
    assert isinstance(bestial, MutagenFacts) and bestial.duration_seconds == 60
    assert bestial.granted_attacks[0].damage_dice == (4,) and bestial.granted_attacks[0].agile
    assert bestial.granted_attacks[0].striking_applies is False
    assert "ac:-2:untyped" not in bestial.drawbacks
    assert isinstance(cognitive, MutagenFacts) and cognitive.encumbrance_threshold_penalty_bulk == 2
    assert cognitive.maximum_carry_penalty_bulk == 4


def test_poison_records_preserve_stage_dc_delivery_and_independent_clocks():
    centipede = ALCHEMIST_FORMULAS_BY_ID["giant_centipede_venom"].facts
    arsenic = ALCHEMIST_FORMULAS_BY_ID["arsenic"].facts
    assert isinstance(centipede, PoisonFacts)
    assert (centipede.delivery, centipede.save_dc, centipede.maximum_duration_seconds) == ("injury", 17, 36)
    assert centipede.stages[1].conditions == (("fatigued", 1),)
    assert centipede.stages[2].conditions == (("fatigued", 1), ("clumsy", 1))
    assert isinstance(arsenic, PoisonFacts)
    assert (arsenic.delivery, arsenic.save_dc, arsenic.onset_seconds, arsenic.maximum_duration_seconds) == ("ingested", 18, 600, 300)
    assert arsenic.prevents_sickened_reduction_while_active is True
    assert arsenic.stages[0].conditions == (("sickened", 1),)


def test_four_field_vials_have_direct_non_scripted_conversions():
    bomber = field_vial_profile(FIELD_BOMBER, damage_type="electricity")
    assert (bomber.damage_type, bomber.initial_damage_dice, bomber.splash_damage, bomber.attack_roll_required) == ("electricity", (6,), 1, True)
    with pytest.raises(AlchemyRuleError) as damage_type:
        field_vial_profile(FIELD_BOMBER, damage_type="poison")
    assert damage_type.value.reason == "invalid_vial_damage_type"

    chirurgeon = field_vial_profile(FIELD_CHIRURGEON, use_mode="healing_throw")
    assert chirurgeon.healing_dice == (6,)
    assert chirurgeon.thrown_healing_range_ft == 20
    assert chirurgeon.living_target_only and chirurgeon.coagulant and not chirurgeon.attack_roll_required
    assert "elixir" not in chirurgeon.traits
    assert "elixir" in field_vial_profile(FIELD_CHIRURGEON).traits
    mutagenist = field_vial_profile(FIELD_MUTAGENIST)
    assert mutagenist.suppression_seconds == 60
    toxic_bomb = field_vial_profile(FIELD_TOXICOLOGIST)
    toxic_coating = field_vial_profile(FIELD_TOXICOLOGIST, use_mode="injury_coating")
    assert toxic_bomb.damage_type == "poison" and toxic_bomb.splash_damage == 0
    assert toxic_coating.injury_strike_damage_dice == (6,)
    assert toxic_coating.injury_expires_at == "creator_current_turn_end"
    assert toxic_coating.injury_requires_piercing_or_slashing_damage


def test_bomber_splash_choice_is_per_throw_and_mutagenist_temp_hp_has_a_one_minute_lock():
    bomber = build_state(FIELD_BOMBER)
    assert bomber_splash_targets(bomber, "enemy", ("ally", "other-enemy"), only_primary_target=False) == (
        "enemy",
        "ally",
        "other-enemy",
    )
    assert bomber_splash_targets(bomber, "enemy", ("ally",), only_primary_target=True) == ("enemy",)
    with pytest.raises(AlchemyRuleError):
        bomber_splash_targets(build_state(FIELD_CHIRURGEON), "enemy", (), only_primary_target=True)

    mutagenist = build_state(FIELD_MUTAGENIST)
    grant = gain_mutagenist_temporary_hp(mutagenist, now_seconds=100, active_mutagen_expires_at_seconds=130)
    assert grant.amount == 4
    assert grant.expires_at_seconds == 130
    assert grant.state.mutagen_temp_hp_available_at_seconds == 160
    with pytest.raises(AlchemyRuleError) as cooldown:
        gain_mutagenist_temporary_hp(grant.state, now_seconds=159, active_mutagen_expires_at_seconds=200)
    assert cooldown.value.reason == "mutagen_temp_hp_cooldown"
    next_grant = gain_mutagenist_temporary_hp(grant.state, now_seconds=160, active_mutagen_expires_at_seconds=220)
    assert next_grant.amount == 4 and next_grant.expires_at_seconds == 220
