"""Focused public Fear and Flee checks for the staged Angelic sheet."""

from __future__ import annotations

import pytest

from pf2e.content import ANGELIC_FEAR_SETUP, ANGELIC_FIRST_CAST_SETUP
from pf2e.encounter import Encounter
from pf2e.model import ActiveConditionEffect, Cast, EndTurn, EffectExpiration, Flee, Position, ResultStatus, Stride


def _finish_start_choices(game: Encounter) -> None:
    while (choice := game.inspect().choice) is not None:
        option = "keep" if any(item.option_id == "keep" for item in choice.options) else choice.options[0].option_id
        result = game.choose(choice.choice_id, option, choice.owner_actor_id)
        assert result.status is ResultStatus.COMPLETED


def _fear_game(*, die: int, rolls: tuple[int, ...] | None = None) -> Encounter:
    game = Encounter.start(
        ANGELIC_FEAR_SETUP,
        rolls=rolls if rolls is not None else (20, 1, die, 1, 1, 1),
    )
    _finish_start_choices(game)
    assert game.inspect().turn_actor_id == "angelic_sorcerer"
    return game


@pytest.mark.parametrize(
    ("die", "frightened", "fleeing"),
    [(20, 0, False), (13, 1, False), (4, 2, False), (1, 3, True)],
)
def test_public_fear_uses_will_and_maps_all_four_save_degrees(
    die: int, frightened: int, fleeing: bool,
) -> None:
    game = _fear_game(die=die)
    before_hp = game._state.creatures["sorcerer_dog"].hp

    result = game.execute(Cast("fear", "sorcerer_dog"))

    assert result.status is ResultStatus.COMPLETED
    save = next(event for event in result.events if event.kind == "spell_save")
    assert "Will save" in save.text
    assert game._state.creatures["sorcerer_dog"].hp == before_hp
    assert game._state.creatures["angelic_sorcerer"].spontaneous_slots[0].remaining == 2
    effects = [
        effect for effect in game._state.condition_effects
        if effect.target_actor_id == "sorcerer_dog" and effect.kind == "frightened"
    ]
    assert ([effect.value for effect in effects] or [0]) == [frightened]
    fleeing_effects = [
        effect for effect in game._state.active_effects
        if effect.kind == "fleeing" and effect.target_actor_id == "sorcerer_dog"
    ]
    assert bool(fleeing_effects) is fleeing
    if fleeing_effects:
        effect = fleeing_effects[0]
        assert effect.expires_at_source_start == 2
        assert effect.expires_at_world_time == 6


def test_fear_target_gets_final_hero_point_decision() -> None:
    game = Encounter.start(ANGELIC_FIRST_CAST_SETUP, rolls=(20, 1, 1, 4, 20))
    _finish_start_choices(game)

    offered = game.execute(Cast("fear", "sorcerer_ally"))
    assert offered.status is ResultStatus.PAUSED
    choice = offered.inspection.choice
    assert choice is not None and choice.kind == "spell_save_hero_reroll"
    assert "Will save" in choice.prompt

    kept = game.choose(choice.choice_id, "keep", choice.owner_actor_id)
    assert kept.status is ResultStatus.COMPLETED
    assert any(event.kind == "condition_applied" for event in kept.events)
    assert game._state.creatures["sorcerer_ally"].hero_points == 1

    game = Encounter.start(ANGELIC_FIRST_CAST_SETUP, rolls=(20, 1, 1, 4, 20))
    _finish_start_choices(game)
    offered = game.execute(Cast("fear", "sorcerer_ally"))
    choice = offered.inspection.choice
    assert choice is not None
    rerolled = game.choose(choice.choice_id, "spend_hero_point", choice.owner_actor_id)
    assert rerolled.status is ResultStatus.COMPLETED
    assert any("critical success" in event.text for event in rerolled.events if event.kind == "spell_save")
    assert not any(event.kind == "condition_applied" for event in rerolled.events)
    assert game._state.creatures["sorcerer_ally"].hero_points == 0


def test_flee_moves_to_closed_boundary_and_rejects_unrelated_actions() -> None:
    game = _fear_game(die=1)
    game.execute(Cast("fear", "sorcerer_dog"))
    game.execute(EndTurn())
    assert game.inspect().turn_actor_id == "sorcerer_dog"
    assert game.options().available_actions == ("flee",)

    result = game.execute(Flee())
    assert result.status is ResultStatus.COMPLETED
    assert any(event.kind == "flee" for event in result.events)
    dog = game._state.creatures["sorcerer_dog"]
    assert dog.position == Position(4, 0)
    assert dog.actions_remaining == 2

    before = (dog.position, dog.actions_remaining, game._dice._index)
    rejected = game.execute(Stride((Position(3, 0),)))
    assert rejected.status is ResultStatus.REJECTED
    assert "Fleeing requires" in rejected.message
    assert (dog.position, dog.actions_remaining, game._dice._index) == before

    blocked = game.execute(Flee())
    assert blocked.status is ResultStatus.COMPLETED
    assert any(event.kind == "flee_blocked" for event in blocked.events)
    dog = game._state.creatures["sorcerer_dog"]
    assert dog.position == Position(4, 0)
    assert dog.actions_remaining == 1

    finished = game.execute(Flee())
    assert finished.status is ResultStatus.COMPLETED
    assert any(event.kind == "turn_ended" for event in finished.events)
    assert not any(effect.kind == "fleeing" for effect in game._state.active_effects)
    frightened = [
        effect for effect in game._state.condition_effects
        if effect.kind == "frightened" and effect.target_actor_id == "sorcerer_dog"
    ]
    assert [effect.value for effect in frightened] == [2]


def test_flee_uses_existing_stand_procedure_when_prone() -> None:
    game = _fear_game(die=1)
    game.execute(Cast("fear", "sorcerer_dog"))
    game.execute(EndTurn())
    dog = game._state.creatures["sorcerer_dog"]
    dog.prone = True

    result = game.execute(Flee())

    assert result.status is ResultStatus.COMPLETED
    assert [event.kind for event in result.events] == ["stand_started", "stand"]
    dog = game._state.creatures["sorcerer_dog"]
    assert dog.prone is False
    assert dog.position == Position(3, 1)
    assert dog.actions_remaining == 2


def test_flee_uses_existing_escape_procedure_for_an_impediment() -> None:
    game = _fear_game(die=1, rolls=(20, 1, 1, 10, 1))
    game.execute(Cast("fear", "sorcerer_dog"))
    game.execute(EndTurn())
    dog = game._state.creatures["sorcerer_dog"]
    game._state.condition_effects.append(ActiveConditionEffect(
        effect_id="fixture:grabbed",
        kind="grabbed",
        source_actor_id="angelic_sorcerer",
        target_actor_id="sorcerer_dog",
        value=1,
        expiration=EffectExpiration("angelic_sorcerer", "start", 99),
        dc=5,
    ))

    result = game.execute(Flee())

    assert result.status is ResultStatus.COMPLETED
    assert any(event.kind == "escape_check" for event in result.events)
    assert not any(effect.effect_id == "fixture:grabbed" for effect in game._state.condition_effects)
    dog = game._state.creatures["sorcerer_dog"]
    assert dog.position == Position(3, 1)
    assert dog.actions_remaining == 2
