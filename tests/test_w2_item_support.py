"""Public W2 item-support lane: healing-adjacent timed elixirs and mutagen."""

from pf2e.alchemist_content import BOMBER_LEVEL_2_ITEM_SUPPORT_FORMULA_IDS
from pf2e.alchemy_content import FORMULAS_BY_ID, ElixirFacts, MutagenFacts
from pf2e.content import get_setup
from pf2e.encounter import Encounter
from pf2e.model import ActiveSpellEffect, ActivateAlchemy, Choose, EndTurn, QuickAlchemy, QuickBomber, ResultStatus
from pf2e.terminal import build_action_menu


def _settle(game: Encounter) -> None:
    while game.inspect().choice is not None:
        choice = game.inspect().choice
        assert choice is not None
        assert game.execute(Choose(choice.choice_id, "keep", choice.owner_actor_id)).status in {
            ResultStatus.COMPLETED,
            ResultStatus.PAUSED,
        }


def _to_alchemist_turn(game: Encounter) -> None:
    for _ in range(8):
        _settle(game)
        if game.inspect().turn_actor_id == "alchemist":
            return
        assert game.execute(EndTurn()).status is ResultStatus.COMPLETED
    raise AssertionError("the item-support Bomber did not receive a turn")


def _use_item(formula_id: str) -> Encounter:
    game = Encounter.start(
        get_setup("l2_bomber_item_support_vs_guard_dog"),
        rolls=(20, 1) * 8,
    )
    _settle(game)
    _to_alchemist_turn(game)
    assert game.execute(QuickAlchemy("create_consumable", formula_id)).status is ResultStatus.COMPLETED
    assert game.execute(ActivateAlchemy("alchemist:quick:1", "alchemist")).status is ResultStatus.COMPLETED
    return game


def test_item_support_variant_is_a_legal_finite_l2_book_and_catalog_family() -> None:
    assert len(BOMBER_LEVEL_2_ITEM_SUPPORT_FORMULA_IDS) == 10
    assert all(FORMULAS_BY_ID[formula_id].level <= 2 for formula_id in BOMBER_LEVEL_2_ITEM_SUPPORT_FORMULA_IDS)
    assert BOMBER_LEVEL_2_ITEM_SUPPORT_FORMULA_IDS[-3:] == (
        "antiplague_lesser", "bestial_mutagen_lesser", "cognitive_mutagen_lesser",
    )
    assert isinstance(FORMULAS_BY_ID["cheetahs_elixir_lesser"].facts, ElixirFacts)
    assert isinstance(FORMULAS_BY_ID["bravos_brew_lesser"].facts, ElixirFacts)
    assert isinstance(FORMULAS_BY_ID["juggernaut_mutagen_lesser"].facts, MutagenFacts)


def test_cheetahs_elixir_projects_speed_and_expires_after_save_load(tmp_path) -> None:
    game = _use_item("cheetahs_elixir_lesser")
    assert game.effective_speed_ft("alchemist") == 35
    assert game._state.active_effects[0].kind == "alchemy_cheetahs_elixir_lesser"

    path = tmp_path / "w2-cheetah.json"
    game.save(path)
    restored = Encounter.load(path)
    assert restored.effective_speed_ft("alchemist") == 35

    # The same clock seam is used by the public recovery/resting activities;
    # this focused check keeps the encounter open so the item effect alone is
    # isolated from a combat-completion requirement.
    restored._advance_elapsed_time(restored._state, 60)
    assert restored.effective_speed_ft("alchemist") == 30
    assert not restored._state.active_effects


def test_juggernaut_grants_temporary_hp_and_printed_fortitude_bonus_then_cleans_up() -> None:
    game = _use_item("juggernaut_mutagen_lesser")
    actor = game._state.creatures["alchemist"]
    assert actor.temporary_hp == 5
    assert actor.temporary_hp_source_id == "alchemy:alchemist:quick:1"
    modifiers = game._mutagen_modifiers(game._state, actor, "fortitude")
    assert {(modifier.amount, modifier.modifier_type) for modifier in modifiers} == {(1, "item")}
    will_modifiers = game._mutagen_modifiers(game._state, actor, "will")
    assert {(modifier.amount, modifier.modifier_type) for modifier in will_modifiers} == {(-2, "untyped")}


def test_juggernaut_requires_explicit_temporary_hp_choice_before_consumption() -> None:
    game = Encounter.start(
        get_setup("l2_bomber_item_support_vs_guard_dog"),
        rolls=(20, 1) * 8,
    )
    _settle(game)
    _to_alchemist_turn(game)
    actor = game._state.creatures["alchemist"]
    actor.temporary_hp = 3
    actor.temporary_hp_source_id = "existing:pool"
    actor.temporary_hp_expires_at_seconds = 600
    assert game.execute(QuickAlchemy("create_consumable", "juggernaut_mutagen_lesser")).status is ResultStatus.COMPLETED
    actor = game._state.creatures["alchemist"]

    item_id = "alchemist:quick:1"
    rejected = game.execute(ActivateAlchemy(item_id, "alchemist"))
    assert rejected.status is ResultStatus.REJECTED
    assert item_id in actor.held_items
    assert item_id not in game._state.consumed_infused_item_ids
    assert actor.temporary_hp == 3

    kept = game.execute(ActivateAlchemy(item_id, "alchemist", "keep_existing"))
    assert kept.status is ResultStatus.COMPLETED
    actor = game._state.creatures["alchemist"]
    assert actor.temporary_hp == 3
    assert actor.temporary_hp_source_id == "existing:pool"


def test_juggernaut_gain_choice_replaces_even_a_larger_existing_pool() -> None:
    game = Encounter.start(
        get_setup("l2_bomber_item_support_vs_guard_dog"),
        rolls=(20, 1) * 8,
    )
    _settle(game)
    _to_alchemist_turn(game)
    actor = game._state.creatures["alchemist"]
    actor.temporary_hp = 8
    actor.temporary_hp_source_id = "existing:pool"
    actor.temporary_hp_expires_at_seconds = 600
    assert game.execute(QuickAlchemy("create_consumable", "juggernaut_mutagen_lesser")).status is ResultStatus.COMPLETED
    result = game.execute(ActivateAlchemy("alchemist:quick:1", "alchemist", "gain_new"))
    assert result.status is ResultStatus.COMPLETED
    actor = game._state.creatures["alchemist"]
    assert actor.temporary_hp == 5
    assert actor.temporary_hp_source_id == "alchemy:alchemist:quick:1"


def test_successful_mutagen_replacement_clears_counteracted_juggernaut_temp_hp() -> None:
    game = _use_item("juggernaut_mutagen_lesser")
    assert game.execute(EndTurn()).status is ResultStatus.COMPLETED
    _to_alchemist_turn(game)
    assert game.execute(QuickAlchemy("create_consumable", "bestial_mutagen_lesser")).status is ResultStatus.COMPLETED
    item_id = next(
        item_id for item_id, infused in game._state.infused_alchemy_items.items()
        if infused.formula_id == "bestial_mutagen_lesser" and item_id in game._state.creatures["alchemist"].held_items
    )
    result = game.execute(ActivateAlchemy(item_id, "alchemist"))
    assert result.status is ResultStatus.COMPLETED
    actor = game._state.creatures["alchemist"]
    assert actor.temporary_hp == 0
    assert actor.temporary_hp_source_id is None
    assert [effect.kind for effect in game._state.active_effects] == ["alchemy_bestial_mutagen_lesser"]


def test_keep_existing_cannot_keep_a_counteracted_juggernaut_pool() -> None:
    game = _use_item("juggernaut_mutagen_lesser")
    assert game.execute(EndTurn()).status is ResultStatus.COMPLETED
    _to_alchemist_turn(game)
    assert game.execute(QuickAlchemy("create_consumable", "juggernaut_mutagen_lesser")).status is ResultStatus.COMPLETED
    item_id = next(
        item_id for item_id, infused in game._state.infused_alchemy_items.items()
        if infused.formula_id == "juggernaut_mutagen_lesser" and item_id in game._state.creatures["alchemist"].held_items
    )
    result = game.execute(ActivateAlchemy(item_id, "alchemist", "keep_existing"))
    assert result.status is ResultStatus.COMPLETED
    actor = game._state.creatures["alchemist"]
    assert actor.temporary_hp == 5
    assert actor.temporary_hp_source_id == f"alchemy:{item_id}"
    assert [effect.kind for effect in game._state.active_effects] == ["alchemy_juggernaut_mutagen_lesser"]
    assert "grants 5 temporary HP" in result.events[-1].text


def test_w2_item_effects_carry_across_a_finished_scene_and_save_load(tmp_path) -> None:
    game = _use_item("cheetahs_elixir_lesser")
    # The first Bottled Lightning is already prepared.  Later turns create
    # additional copies through the public Quick Alchemy route until the
    # actual fight finishes, so next_encounter receives a real completed scene.
    for _ in range(4):
        _settle(game)
        if not game.inspect().in_progress:
            break
        if (
            game.inspect().turn_actor_id == "alchemist"
            and game._state.creatures["alchemist"].actions_remaining < 2
        ):
            assert game.execute(EndTurn()).status is ResultStatus.COMPLETED
            _settle(game)
        if game.inspect().turn_actor_id != "alchemist":
            assert game.execute(EndTurn()).status is ResultStatus.COMPLETED
            _settle(game)
        if game._state.creatures["dog"].hp < 8:
            assert game.execute(QuickAlchemy("create_consumable", "bottled_lightning_lesser")).status is ResultStatus.COMPLETED
        result = game.execute(QuickBomber("dog", "bottled_lightning_lesser"))
        assert result.status in {ResultStatus.COMPLETED, ResultStatus.PAUSED}
        _settle(game)
    assert game.inspect().winner_team == "blue"

    transitioned = game.next_encounter(get_setup("l2_bomber_item_support_next_vs_guard_dog"))
    assert transitioned.status in {ResultStatus.COMPLETED, ResultStatus.PAUSED}
    _settle(game)
    assert game.effective_speed_ft("alchemist") == 35
    assert any(effect.kind == "alchemy_cheetahs_elixir_lesser" for effect in game._state.active_effects)

    path = tmp_path / "w2-next-scene.json"
    game.save(path)
    restored = Encounter.load(path)
    assert restored.effective_speed_ft("alchemist") == 35
    assert any(effect.kind == "alchemy_cheetahs_elixir_lesser" for effect in restored._state.active_effects)


def test_cheetah_status_speed_bonus_does_not_stack_with_panache() -> None:
    game = Encounter.start(
        get_setup("staged_braggart_swashbuckler_vs_guard_dog"),
        rolls=(20, 1) * 8,
    )
    actor = game._state.creatures["braggart"]
    actor.panache = True
    game._state.active_effects.append(
        ActiveSpellEffect(
            "test:cheetah", "alchemy_cheetahs_elixir_lesser", "braggart", "braggart", 5,
            game._state.actor_start_counts["braggart"] + 1,
            game._state.world_time_seconds + 60,
        )
    )
    assert game.effective_speed_ft("braggart") == 30


def test_bravos_brew_projects_normal_and_fear_will_bonus() -> None:
    game = _use_item("bravos_brew_lesser")
    actor = game._state.creatures["alchemist"]
    normal = game._alchemy_save_modifiers(game._state, actor, "will", against=None)
    fear = game._alchemy_save_modifiers(game._state, actor, "will", against="fear")
    assert [(modifier.amount, modifier.modifier_type) for modifier in normal] == [(1, "item")]
    assert [(modifier.amount, modifier.modifier_type) for modifier in fear] == [(1, "item"), (2, "item")]


def test_terminal_exposes_the_new_formula_actions() -> None:
    game = Encounter.start(
        get_setup("l2_bomber_item_support_vs_guard_dog"),
        rolls=(20, 1) * 8,
    )
    _settle(game)
    _to_alchemist_turn(game)
    labels = dict(build_action_menu(game.options().available_actions))
    assert labels["quick_alchemy"] == "Quick Alchemy"
    assert game.execute(QuickAlchemy("create_consumable", "bravos_brew_lesser")).status is ResultStatus.COMPLETED
    labels = dict(build_action_menu(game.options().available_actions))
    assert labels["activate_alchemy"] == "Activate Alchemy Item"
