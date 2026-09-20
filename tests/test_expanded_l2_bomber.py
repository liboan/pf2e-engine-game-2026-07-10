"""Bounded level-two Bomber progression before shared encounter wiring.

Rules sources: Player Core 2 Alchemist, including Formula Book and Advanced
Alchemy, https://2e.aonprd.com/Classes.aspx?ID=56; Quick Bomber,
https://2e.aonprd.com/Feats.aspx?ID=5764; Far Lobber,
https://2e.aonprd.com/Feats.aspx?ID=5763; Alchemist's Fire and Acid Flask,
https://2e.aonprd.com/Equipment.aspx?ID=3287 and
https://2e.aonprd.com/Equipment.aspx?ID=3286.
"""

import pytest

from pf2e.content import get_setup
from pf2e.encounter import Encounter
from pf2e.model import Choose, EndTurn, Position, QuickAlchemy, QuickBomber, ResultStatus
from pf2e.alchemy import (
    FAR_LOBBER,
    QUICK_BOMBER,
    AlchemyBuildChoices,
    AlchemyRuleError,
    bomber_bomb_range_increment,
    build_alchemy_state,
    daily_prepare_alchemy,
    perform_quick_alchemy,
    recover_versatile_vials,
    QuickAlchemyRequest,
)
from pf2e.alchemist_content import BOMBER_FIELD_FORMULA_IDS, BOMBER_FORMULA_IDS
from pf2e.alchemy_content import (
    ALCHEMIST_LEVEL_2_BOMBER_FEAT_MENU,
    ALCHEMIST_LEVEL_2_BOMBER_FEATS_BY_ID,
    FORMULAS_BY_ID,
)


LEVEL_TWO_ADDITIONS = ("alchemists_fire_lesser", "acid_flask_lesser")
LEVEL_TWO_BOMBER_FORMULAS = (*BOMBER_FORMULA_IDS, *LEVEL_TWO_ADDITIONS)


def level_two_bomber_state(*, level_one_feat: str = QUICK_BOMBER, level_two_feat: str = FAR_LOBBER):
    return build_alchemy_state(
        AlchemyBuildChoices(
            research_field="bomber",
            field_formula_ids=BOMBER_FIELD_FORMULA_IDS,
            known_formula_ids=LEVEL_TWO_BOMBER_FORMULAS,
            intelligence_modifier=4,
            selected_level_1_feat=level_one_feat,
            character_level=2,
            selected_level_2_feat=level_two_feat,
        )
    )


def _settle(game: Encounter) -> None:
    while game.inspect().choice is not None:
        choice = game.inspect().choice
        assert choice is not None
        assert game.execute(Choose(choice.choice_id, "keep", choice.owner_actor_id)).status in {
            ResultStatus.COMPLETED,
            ResultStatus.PAUSED,
        }


def _to_turn(game: Encounter, actor_id: str) -> None:
    for _ in range(8):
        _settle(game)
        if game.inspect().turn_actor_id == actor_id:
            return
        assert game.execute(EndTurn()).status is ResultStatus.COMPLETED
    raise AssertionError(f"{actor_id!r} did not receive a turn")


def test_level_two_bomber_adds_two_legal_known_formulas_and_retains_quick_bomber():
    state = level_two_bomber_state()

    assert state.character_level == 2
    assert state.known_formula_ids == LEVEL_TWO_BOMBER_FORMULAS
    assert state.selected_level_1_feat == QUICK_BOMBER
    assert state.selected_level_2_feat == FAR_LOBBER
    assert set(state.field_formula_ids) <= set(state.known_formula_ids)
    assert tuple(FORMULAS_BY_ID[formula_id].level for formula_id in LEVEL_TWO_ADDITIONS) == (1, 1)
    assert tuple(FORMULAS_BY_ID[formula_id].category for formula_id in LEVEL_TWO_ADDITIONS) == ("bomb", "bomb")


def test_level_two_formula_resources_keep_daily_capacity_and_vial_recovery_separate():
    state = level_two_bomber_state()
    quick = perform_quick_alchemy(
        state,
        QuickAlchemyRequest(
            "create_consumable", "alchemist", 100, True, True,
            "alchemists_fire_lesser", creator_turn_occurrence=1,
        ),
    )
    assert quick.state.stored_vials == 5
    assert quick.item.formula_id == "alchemists_fire_lesser"

    prepared = daily_prepare_alchemy(
        quick.state,
        ("bottled_lightning_lesser", "frost_vial_lesser", *LEVEL_TWO_ADDITIONS),
        creator_actor_id="alchemist",
        preparation_id="day-2",
        now_seconds=200,
    )
    assert prepared.state.stored_vials == 6
    assert {item.formula_id for item in prepared.items} == {
        "bottled_lightning_lesser", "frost_vial_lesser", *LEVEL_TWO_ADDITIONS,
    }
    assert prepared.state.selected_level_2_feat == FAR_LOBBER

    recovered = recover_versatile_vials(quick.state, 600)
    assert recovered.stored_vials == 6
    assert recovered.exploration_seconds_toward_vial_recovery == 0


def test_far_lobber_is_a_legal_level_two_slot_alternative_with_a_concrete_range_contract():
    state = level_two_bomber_state()

    assert set(ALCHEMIST_LEVEL_2_BOMBER_FEAT_MENU) == {QUICK_BOMBER, FAR_LOBBER}
    assert ALCHEMIST_LEVEL_2_BOMBER_FEATS_BY_ID[FAR_LOBBER].bomb_range_increment_ft == 30
    assert bomber_bomb_range_increment(state, 20) == 30
    assert bomber_bomb_range_increment(
        level_two_bomber_state(level_one_feat=FAR_LOBBER, level_two_feat=QUICK_BOMBER), 20
    ) == 30


def test_l2_bomber_spends_a_vial_then_saves_a_30_foot_quick_bomber_attack_and_wins(tmp_path):
    game = Encounter.start(
        get_setup("l2_bomber_far_lobber_vs_guard_dog"), rolls=(20, 1, 10, 6, 20, 6),
    )
    _settle(game)
    _to_turn(game, "alchemist")

    created = game.execute(QuickAlchemy("create_consumable", "bottled_lightning_lesser"))
    assert created.status is ResultStatus.COMPLETED
    assert game._state.alchemy_states["alchemist"].stored_vials == 5
    item_id = "alchemist:quick:1"
    assert item_id in game._state.creatures["alchemist"].held_items

    pending = game.execute(QuickBomber("dog", "bottled_lightning_lesser"))
    assert pending.status is ResultStatus.PAUSED
    assert pending.inspection.choice is not None
    assert pending.inspection.choice.kind == "attack_hero_reroll"
    assert game._state.pending_choice is not None
    assert game._state.pending_choice.ranged_penalty == 0
    path = tmp_path / "l2-bomber-far-lobber.json"
    game.save(path)

    restored = Encounter.load(path)
    assert restored._state.alchemy_states["alchemist"].selected_level_2_feat == FAR_LOBBER
    assert restored._state.alchemy_states["alchemist"].stored_vials == 5
    choice = restored.inspect().choice
    assert choice is not None
    result = restored.execute(Choose(choice.choice_id, "keep", choice.owner_actor_id))
    assert result.status is ResultStatus.COMPLETED
    finishing_attack = restored.execute(QuickBomber("dog", "frost_vial_lesser"))
    assert finishing_attack.status in {ResultStatus.COMPLETED, ResultStatus.PAUSED}
    _settle(restored)
    assert restored.inspect().winner_team == "blue"
    assert any(event.kind == "bomb_consumed" for event in result.events)
    assert item_id in restored._state.consumed_infused_item_ids


def test_terminal_selects_a_30_foot_far_lobber_bomb_target():
    from pf2e.terminal import run_terminal

    commands = iter((
        "2", "1",  # Resolve the Bomber's initiative choice by keeping it.
        "5", "1", "1",  # Quick Bomber, Bottled Lightning, Guard Dog at 30 feet.
        "1",  # Keep the saved attack result.
        "x",
    ))
    output: list[str] = []
    assert run_terminal(
        setup=get_setup("l2_bomber_far_lobber_vs_guard_dog"), rolls=(20, 1, 10, 6),
        input_fn=lambda: next(commands), output_fn=output.append,
    ) == 0
    transcript = "\n".join(output)
    assert "Bottled Lightning (lesser)" in transcript
    assert any("uses Quick Bomber" in line for line in output)


def test_l2_bomber_recovers_vials_prepares_legal_capacity_and_uses_day_two_stock(tmp_path):
    game = Encounter.start(
        get_setup("l2_bomber_far_lobber_vs_guard_dog"),
        rolls=(20, 1, 10, 6, 20, 6, 20, 6, 20, 6, 20, 6),
    )
    _settle(game)
    _to_turn(game, "alchemist")
    assert game.execute(QuickAlchemy("create_consumable", "bottled_lightning_lesser")).status is ResultStatus.COMPLETED
    first = game.execute(QuickBomber("dog", "bottled_lightning_lesser"))
    assert first.status is ResultStatus.PAUSED
    _settle(game)
    second = game.execute(QuickBomber("dog", "frost_vial_lesser"))
    assert second.status in {ResultStatus.COMPLETED, ResultStatus.PAUSED}
    _settle(game)
    assert game.inspect().winner_team == "blue"

    assert game.recover_versatile_vials("alchemist", elapsed_seconds=600).status is ResultStatus.COMPLETED
    assert game._state.alchemy_states["alchemist"].stored_vials == 6
    assert game.record_rested(("alchemist",), day_number=2, elapsed_seconds=8 * 60 * 60).status is ResultStatus.COMPLETED
    assert game.daily_prepare(("alchemist",), {"alchemist": {}}).status is ResultStatus.COMPLETED
    prepared = game._state.alchemy_states["alchemist"]
    assert prepared.daily_preparation_id == "day:2"
    assert prepared.selected_level_2_feat == FAR_LOBBER
    assert {
        item.formula_id for item in game._state.infused_alchemy_items.values()
        if item.daily_preparation_id == "day:2"
    } == set(BOMBER_FORMULA_IDS)
    assert set(LEVEL_TWO_ADDITIONS) <= set(prepared.known_formula_ids)

    path = tmp_path / "l2-bomber-day-two.json"
    game.save(path)
    restored = Encounter.load(path)
    advanced = restored.next_encounter(get_setup("l2_bomber_far_lobber_next_vs_guard_dog"))
    assert advanced.status in {ResultStatus.COMPLETED, ResultStatus.PAUSED}
    _settle(restored)
    _to_turn(restored, "alchemist")
    next_bomb = restored.execute(QuickBomber("next_dog", "bottled_lightning_lesser"))
    assert next_bomb.status in {ResultStatus.COMPLETED, ResultStatus.PAUSED}
    _settle(restored)
    assert any(event.kind == "bomb_consumed" for event in next_bomb.events) or "alchemist:bottled_lightning_lesser" in restored._state.consumed_infused_item_ids


def test_l2_bomber_rejects_unselected_poison_and_targets_beyond_far_lobber_range():
    game = Encounter.start(
        get_setup("l2_bomber_far_lobber_vs_guard_dog"), rolls=(20, 1, 10, 6),
    )
    _settle(game)
    _to_turn(game, "alchemist")
    before = game._state.alchemy_states["alchemist"].stored_vials
    poison = game.execute(QuickAlchemy("create_consumable", "black_adder_venom"))
    assert poison.status is ResultStatus.REJECTED
    assert game._state.alchemy_states["alchemist"].stored_vials == before

    game._state.creatures["dog"].position = Position(8, 1)  # 35 feet: one Far Lobber increment plus 5 feet.
    at_35_feet = game.execute(QuickBomber("dog", "bottled_lightning_lesser"))
    assert at_35_feet.status is ResultStatus.PAUSED
    assert game._state.pending_choice is not None
    assert game._state.pending_choice.ranged_penalty == -2

    far_game = Encounter.start(get_setup("l2_bomber_far_lobber_vs_guard_dog"), rolls=(20, 1))
    _settle(far_game)
    _to_turn(far_game, "alchemist")
    far_game._state.creatures["dog"].position = Position(38, 1)  # 185 feet: beyond six 30-foot increments.
    out_of_range = far_game.execute(QuickBomber("dog", "bottled_lightning_lesser"))
    assert out_of_range.status is ResultStatus.REJECTED


def test_level_two_progression_rejects_poison_expansion_and_invalid_feat_or_formula_selections():
    with pytest.raises(AlchemyRuleError) as poison:
        build_alchemy_state(
            AlchemyBuildChoices(
                "bomber", BOMBER_FIELD_FORMULA_IDS,
                (*BOMBER_FORMULA_IDS, "black_adder_venom", "acid_flask_lesser"), 4,
                QUICK_BOMBER, 2, FAR_LOBBER,
            )
        )
    assert poison.value.reason == "unsupported_formula"

    with pytest.raises(AlchemyRuleError) as size:
        build_alchemy_state(
            AlchemyBuildChoices(
                "bomber", BOMBER_FIELD_FORMULA_IDS, BOMBER_FORMULA_IDS, 4,
                QUICK_BOMBER, 2, FAR_LOBBER,
            )
        )
    assert size.value.reason == "invalid_formula_book_size"

    with pytest.raises(AlchemyRuleError) as missing_feat:
        build_alchemy_state(
            AlchemyBuildChoices(
                "bomber", BOMBER_FIELD_FORMULA_IDS, LEVEL_TWO_BOMBER_FORMULAS, 4,
                QUICK_BOMBER, 2,
            )
        )
    assert missing_feat.value.reason == "level_2_feat_required"

    with pytest.raises(AlchemyRuleError) as other_field:
        build_alchemy_state(
            AlchemyBuildChoices(
                "chirurgeon", ("antidote_lesser", "antiplague_lesser"),
                ("antidote_lesser", "antiplague_lesser", "elixir_of_life_minor", "bestial_mutagen_lesser", "cognitive_mutagen_lesser", "arsenic", "giant_centipede_venom", "acid_flask_lesser", "bottled_lightning_lesser", "frost_vial_lesser"),
                4, QUICK_BOMBER, 2, FAR_LOBBER,
            )
        )
    assert other_field.value.reason == "unsupported_l2_research_field"

    with pytest.raises(AlchemyRuleError) as duplicate:
        level_two_bomber_state(level_one_feat=QUICK_BOMBER, level_two_feat=QUICK_BOMBER)
    assert duplicate.value.reason == "duplicate_class_feat"

    with pytest.raises(AlchemyRuleError) as early:
        build_alchemy_state(
            AlchemyBuildChoices(
                "bomber", BOMBER_FIELD_FORMULA_IDS, BOMBER_FORMULA_IDS, 4,
                QUICK_BOMBER, 1, FAR_LOBBER,
            )
        )
    assert early.value.reason == "level_2_feat_too_early"
