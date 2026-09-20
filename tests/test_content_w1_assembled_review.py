"""Independent assembled encounter across the three Content W1 families."""

from dataclasses import replace
from types import MappingProxyType

import pytest

import pf2e.content as content
from pf2e.encounter import Encounter
from pf2e.fighter import IntimidatingStrike
from pf2e.model import (
    Cast, Choose, CreaturePlacement, EncounterSetup, EndTurn, Position,
    QuickAlchemy, QuickBomber, ResultStatus,
)


def _settle(game: Encounter) -> None:
    for _ in range(8):
        choice = game.inspect().choice
        if choice is None:
            return
        assert game.execute(Choose(choice.choice_id, "keep", choice.owner_actor_id)).status in {
            ResultStatus.PAUSED, ResultStatus.COMPLETED,
        }
    raise AssertionError("initiative did not settle")


def _keep(game: Encounter) -> None:
    choice = game.inspect().choice
    assert choice is not None
    assert game.execute(Choose(choice.choice_id, "keep", choice.owner_actor_id)).status is ResultStatus.COMPLETED


def test_daze_fear_and_bomb_persistence_survive_two_saved_attack_choices(
    monkeypatch: pytest.MonkeyPatch, tmp_path,
) -> None:
    durable_dog = replace(
        content.get_definition("guard_dog_mc2924"),
        definition_id="review_w1_durable_dog", hp=100,
    )
    setup = EncounterSetup(
        "review_w1_three_families", "Content W1 combined encounter", 15, 5,
        (
            CreaturePlacement("witch", "faiths_flamekeeper_witch_level_1_daze_prepared", "Witch", "blue", Position(1, 2)),
            CreaturePlacement("fighter", "fighter_m_level_2_intimidating_strike", "Fighter", "blue", Position(3, 2)),
            CreaturePlacement("alchemist", "bomber_alchemist_level_2_far_lobber", "Bomber", "blue", Position(1, 1)),
            CreaturePlacement("dog", durable_dog.definition_id, "Dog", "red", Position(4, 2)),
        ),
    )
    monkeypatch.setattr(
        content, "_STAGED_CREATURES",
        MappingProxyType({**content._STAGED_CREATURES, durable_dog.definition_id: durable_dog}),
    )
    monkeypatch.setattr(
        content, "_STAGED_SETUPS",
        MappingProxyType({**content._STAGED_SETUPS, setup.setup_id: setup}),
    )
    game = Encounter.start(
        setup, rolls=(20, 15, 10, 1, 1, 1, 12, 1, 15, 1, 20),
    )
    _settle(game)
    assert game.inspect().turn_actor_id == "witch"

    assert game.execute(Cast("daze", "dog")).status is ResultStatus.COMPLETED
    assert game._state.creatures["dog"].stunned == 1
    assert game.execute(EndTurn()).status is ResultStatus.COMPLETED
    assert game.inspect().turn_actor_id == "fighter"

    assert game.execute(IntimidatingStrike("dog", "longsword")).status is ResultStatus.PAUSED
    path = tmp_path / "combined-after-fighter-attack.json"
    game.save(path)
    game = Encounter.load(path)
    assert game._state.creatures["dog"].stunned == 1
    _keep(game)
    assert any(
        effect.kind == "frightened" and effect.target_actor_id == "dog"
        for effect in game._state.condition_effects
    )
    assert game.execute(EndTurn()).status is ResultStatus.COMPLETED
    assert game.inspect().turn_actor_id == "alchemist"

    assert game.execute(QuickAlchemy("create_consumable", "alchemists_fire_lesser")).status is ResultStatus.COMPLETED
    assert game.execute(QuickBomber("dog", "alchemists_fire_lesser")).status is ResultStatus.PAUSED
    path = tmp_path / "combined-after-bomb-attack.json"
    game.save(path)
    game = Encounter.load(path)
    _keep(game)
    assert len(game._state.persistent_effects) == 1
    assert game._state.persistent_effects[0].spell_id == "alchemists_fire_lesser"

    game.save(path)
    loaded = Encounter.load(path)
    assert loaded._state.creatures["dog"].stunned == 1
    assert any(effect.kind == "frightened" for effect in loaded._state.condition_effects)
    assert loaded._state.persistent_effects == game._state.persistent_effects

    assert loaded.execute(EndTurn()).status is ResultStatus.COMPLETED
    assert loaded.inspect().turn_actor_id == "dog"
    assert loaded._state.creatures["dog"].actions_remaining == 2
    tick = loaded.execute(EndTurn())
    assert tick.status is ResultStatus.COMPLETED
    assert any(event.kind == "persistent_damage" for event in tick.events)
    assert any(event.kind == "persistent_recovered" for event in tick.events)
    assert not loaded._state.persistent_effects
