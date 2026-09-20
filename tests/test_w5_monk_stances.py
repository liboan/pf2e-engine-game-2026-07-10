"""Focused W5 source/play checks for Tiger and Wolf stance content."""

from __future__ import annotations

from pathlib import Path

import pytest

import pf2e.content as content
from pf2e.encounter import Encounter
from pf2e.model import Choose, CreaturePlacement, EncounterSetup, Position, ResultStatus, Step, Strike
from pf2e.monk_stances import TigerStance, WolfStance
from pf2e.skill_actions import Trip


def _settle(game: Encounter) -> None:
    for _ in range(20):
        choice = game.inspect().choice
        if choice is None:
            return
        option = next((item for item in choice.options if item.option_id == "keep"), choice.options[0])
        game.choose(choice.choice_id, option.option_id, choice.owner_actor_id)
    raise AssertionError("initiative did not settle")


def _monk_turn(game: Encounter) -> None:
    _settle(game)
    for _ in range(20):
        if game.inspect().turn_actor_id == "monk":
            return
        game.execute(__import__("pf2e").EndTurn())
    raise AssertionError("Monk turn did not arrive")


def _setup(monkeypatch: pytest.MonkeyPatch, setup_id: str, placements) -> EncounterSetup:
    setup = EncounterSetup(setup_id, setup_id, 8, 5, tuple(placements))
    monkeypatch.setattr(content, "_STAGED_SETUPS", content._STAGED_SETUPS | {setup_id: setup})
    return setup


def test_tiger_stance_preserves_fists_and_adds_critical_bleed_after_damage(tmp_path: Path) -> None:
    game = Encounter.start(content.get_setup("w5_tiger_stance_vs_guard_dog"), rolls=(20, 20, 20, 6) + (20,) * 36)
    _monk_turn(game)
    game._state.creatures["monk"].hero_points = 0
    game._state.creatures["dog"].position = Position(2, 1)
    assert game.execute(TigerStance()).status is ResultStatus.COMPLETED
    assert {item.attack_id for item in game.options().strikes} == {"fist", "tiger_claws"}

    saved = tmp_path / "tiger.json"
    game.save(saved)
    game = Encounter.load(saved)
    result = game.execute(Strike("dog", "tiger_claws"))
    assert result.status is ResultStatus.COMPLETED
    assert any(event.kind == "persistent_applied" for event in result.events)
    bleed = [effect for effect in game._state.persistent_effects if effect.spell_id == "tiger_stance"]
    assert len(bleed) == 1 and bleed[0].dice == (4,) and bleed[0].flat == 0


def test_tiger_two_square_step_rejects_occupied_intermediate_square(monkeypatch: pytest.MonkeyPatch) -> None:
    setup = _setup(
        monkeypatch,
        "w5_tiger_step_blocked",
        (
            CreaturePlacement("monk", "monk_tiger_stance_level_1", "Tiger Monk", "blue", Position(1, 2)),
            CreaturePlacement("blocker", "guard_dog_mc2924", "Blocker", "blue", Position(2, 2)),
            CreaturePlacement("dog", "guard_dog_mc2924", "Dog", "red", Position(7, 2)),
        ),
    )
    game = Encounter.start(setup, rolls=(20,) * 40)
    _monk_turn(game)
    assert game.execute(TigerStance()).status is ResultStatus.COMPLETED
    before = game._state.creatures["monk"].position
    rejected = game.execute(Step(Position(3, 2), (Position(2, 2), Position(3, 2))))
    assert rejected.status is ResultStatus.REJECTED
    assert game._state.creatures["monk"].position == before


def test_wolf_jaws_trip_requires_actual_flanking_and_uses_unarmed_selector(monkeypatch: pytest.MonkeyPatch) -> None:
    setup = _setup(
        monkeypatch,
        "w5_wolf_trip_flanking",
        (
            CreaturePlacement("monk", "monk_wolf_stance_level_1", "Wolf Monk", "blue", Position(3, 2)),
            CreaturePlacement("flanker", "guard_dog_mc2924", "Flanker", "blue", Position(5, 1)),
            CreaturePlacement("dog", "guard_dog_mc2924", "Dog", "red", Position(4, 2)),
        ),
    )
    game = Encounter.start(setup, rolls=(20, 20, 20, 20, 6) + (20,) * 35)
    _monk_turn(game)
    game._state.creatures["monk"].hero_points = 0
    assert game.execute(WolfStance()).status is ResultStatus.COMPLETED
    not_flanked = game.execute(Trip("dog", maneuver_attack_id="wolf_jaws"))
    assert not_flanked.status is ResultStatus.REJECTED

    game._state.creatures["flanker"].position = Position(5, 2)
    tripped = game.execute(Trip("dog", maneuver_attack_id="wolf_jaws"))
    assert tripped.status is ResultStatus.COMPLETED
    assert game._state.creatures["dog"].prone
