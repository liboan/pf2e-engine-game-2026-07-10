"""Reload-0 bow boundary while Manipulate adjudication is pending."""

from copy import deepcopy
from dataclasses import FrozenInstanceError, replace

import pytest

from pf2e.content import SHORTBOW_FIGHTER_R, get_definition, get_setup
from pf2e.encounter import Encounter
from pf2e.model import (
    ActiveConditionEffect,
    EffectExpiration,
    Position,
    ResultStatus,
    Strike,
)
from pf2e.ranger_monk_content import RANGER_DEFINITIONS


def _game(*, defender_id="guard_dog_a", rolls=(10, 19, 11, 12, 13, 14, 10, 4)) -> Encounter:
    game = Encounter.start(
        get_setup("s3_mixed_party_vs_three_guard_dogs"), rolls=rolls
    )
    while game.inspect().choice is not None:
        choice = game.inspect().choice
        assert choice is not None
        option_id = "keep" if any(option.option_id == "keep" for option in choice.options) else choice.options[0].option_id
        game.choose(choice.choice_id, option_id, choice.owner_actor_id)
    assert game.inspect().turn_actor_id == "fighter_r"
    positions = {
        "fighter_m": Position(6, 0),
        "fighter_r": Position(0, 0),
        "cleric_c": Position(6, 1),
        "guard_dog_a": Position(6, 2),
        "guard_dog_b": Position(6, 3),
        "guard_dog_c": Position(6, 4),
    }
    positions[defender_id] = Position(1, 0)
    for actor_id, position in positions.items():
        game._state.creatures[actor_id].position = position
    return game


def _grab_archer(game: Encounter, kind: str = "grabbed") -> None:
    game._state.condition_effects.append(ActiveConditionEffect(
        "test-grapple",
        kind,
        "guard_dog_a",
        "fighter_r",
        1,
        EffectExpiration("guard_dog_a", "end", 1),
    ))


def test_reload_profile_is_numeric_immutable_and_validated() -> None:
    fighter_bow = next(attack for attack in SHORTBOW_FIGHTER_R.attacks if attack.attack_id == "shortbow")
    ranger_bows = [
        next(attack for attack in definition.attacks if attack.attack_id == "shortbow")
        for definition in RANGER_DEFINITIONS.values()
    ]
    longsword = next(
        attack for attack in SHORTBOW_FIGHTER_R.attacks if attack.attack_id == "longsword"
    )

    assert fighter_bow.reload == 0
    assert all(attack.reload == 0 for attack in ranger_bows)
    assert longsword.reload is None
    assert replace(fighter_bow, modifier=fighter_bow.modifier + 1).reload == 0
    with pytest.raises(FrozenInstanceError):
        fighter_bow.reload = 1
    with pytest.raises(ValueError, match="non-negative integer"):
        replace(fighter_bow, reload=-1)
    with pytest.raises(ValueError, match="non-negative integer"):
        replace(fighter_bow, reload=True)


def test_reload_profile_survives_encounter_save_and_load(tmp_path) -> None:
    game = _game()
    path = tmp_path / "reload-profile.json"

    game.save(path)
    loaded = Encounter.load(path)
    archer_definition = get_definition(
        loaded._state.creatures["fighter_r"].definition_id
    )
    loaded_bow = next(
        attack for attack in archer_definition.attacks if attack.attack_id == "shortbow"
    )

    assert loaded_bow.reload == 0


def test_grabbed_reload_zero_bow_strike_is_unsupported_without_spending_anything() -> None:
    game = _game()
    _grab_archer(game)
    before_state = deepcopy(game._state)
    before_dice = game._dice.to_data()

    result = game.execute(Strike("guard_dog_a", "shortbow"))

    assert result.status is ResultStatus.UNSUPPORTED
    assert "Grabbed" in result.message
    assert "reload-0" in result.message
    assert "awaits adjudication" in result.message
    assert game._state == before_state
    assert game._dice.to_data() == before_dice
    archer = game._state.creatures["fighter_r"]
    assert archer.actions_remaining == before_state.creatures["fighter_r"].actions_remaining
    assert archer.strikes_this_turn == 0
    assert archer.ammunition["arrow"] == 20


def test_restrained_bow_strike_keeps_the_existing_attack_prohibition_first() -> None:
    game = _game()
    _grab_archer(game, kind="restrained")
    before_dice = game._dice.to_data()

    result = game.execute(Strike("guard_dog_a", "shortbow"))

    assert result.status is ResultStatus.REJECTED
    assert "restrained_attack_or_manipulate_prohibited" in result.message
    assert game._dice.to_data() == before_dice
    assert game._state.creatures["fighter_r"].ammunition["arrow"] == 20


def test_ungrabbed_reload_zero_bow_strike_keeps_normal_attack_costs_and_damage() -> None:
    game = _game()

    result = game.execute(Strike("guard_dog_a", "shortbow"))
    if result.inspection.choice is not None:
        assert result.inspection.choice.kind == "attack_hero_reroll"
        result = game.choose(result.inspection.choice.choice_id, "keep")

    assert result.status is ResultStatus.COMPLETED
    assert any(event.kind == "strike" for event in result.events)
    assert game._state.creatures["fighter_r"].actions_remaining == 2
    assert game._state.creatures["fighter_r"].strikes_this_turn == 1
    assert game._state.creatures["fighter_r"].ammunition["arrow"] == 19
    assert game._state.creatures["guard_dog_a"].hp == 4
    assert game._dice.to_data()["index"] == 8


def test_ungrabbed_ranged_strike_still_offers_the_existing_reactive_strike() -> None:
    game = _game(defender_id="fighter_m")
    game._state.creatures["fighter_m"].team = "red"
    game._state.creatures["fighter_m"].reaction_available = True

    result = game.execute(Strike("fighter_m", "shortbow"))

    assert result.status is ResultStatus.PAUSED
    assert result.inspection.choice is not None
    assert result.inspection.choice.kind == "reaction"
    assert result.inspection.choice.owner_actor_id == "fighter_m"
    assert game._state.creatures["fighter_r"].actions_remaining == 2
    assert game._state.creatures["fighter_r"].ammunition["arrow"] == 19
