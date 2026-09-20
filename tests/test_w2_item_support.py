"""Public W2 item-support lane: healing-adjacent timed elixirs and mutagen."""

from pf2e.alchemist_content import BOMBER_LEVEL_2_ITEM_SUPPORT_FORMULA_IDS
from pf2e.alchemy_content import FORMULAS_BY_ID, ElixirFacts, MutagenFacts
from pf2e.content import get_setup
from pf2e.encounter import Encounter
from pf2e.model import ActivateAlchemy, Choose, EndTurn, QuickAlchemy, ResultStatus
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
