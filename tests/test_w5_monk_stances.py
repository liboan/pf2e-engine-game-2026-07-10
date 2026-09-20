"""Focused W5 source/play checks for Tiger and Wolf stance content."""

from __future__ import annotations

from pathlib import Path
import json
from dataclasses import replace

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


def _high_hp_dog_setup(monkeypatch: pytest.MonkeyPatch, setup_id: str, *, dog_position: Position) -> EncounterSetup:
    definition = replace(
        content.get_definition("guard_dog_mc2924"),
        definition_id=f"{setup_id}_dog",
        hp=30,
    )
    monkeypatch.setattr(content, "CREATURES", content.CREATURES | {definition.definition_id: definition})
    return _setup(
        monkeypatch,
        setup_id,
        (
            CreaturePlacement("monk", "monk_tiger_stance_level_1", "Tiger Monk", "blue", Position(1, 1)),
            CreaturePlacement("dog", definition.definition_id, "Dog", "red", dog_position),
        ),
    )


def test_tiger_stance_preserves_fists_and_adds_critical_bleed_after_damage(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    setup = _high_hp_dog_setup(monkeypatch, "w5_tiger_basic", dog_position=Position(2, 1))
    game = Encounter.start(setup, rolls=(20, 20, 20, 6) + (20,) * 36)
    _monk_turn(game)
    game._state.creatures["monk"].hero_points = 0
    game._state.creatures["dog"].position = Position(2, 1)
    game._state.creatures["dog"].hp = 30
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


def test_wolf_jaws_critical_failure_falls_prone_without_weapon_choice_and_round_trips(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    setup = _setup(
        monkeypatch,
        "w5_wolf_trip_critical_failure",
        (
            CreaturePlacement("monk", "monk_wolf_stance_level_1", "Wolf Monk", "blue", Position(3, 2)),
            CreaturePlacement("flanker", "guard_dog_mc2924", "Flanker", "blue", Position(5, 2)),
            CreaturePlacement("dog", "guard_dog_mc2924", "Dog", "red", Position(4, 2)),
        ),
    )
    game = Encounter.start(setup, rolls=(20, 20, 20, 1) + (20,) * 36)
    _monk_turn(game)
    game._state.creatures["monk"].hero_points = 0
    assert game.execute(WolfStance()).status is ResultStatus.COMPLETED
    result = game.execute(Trip("dog", maneuver_attack_id="wolf_jaws"))
    assert result.status is ResultStatus.COMPLETED
    assert game.inspect().choice is None
    assert game._state.creatures["monk"].prone
    assert any(event.kind == "condition_applied" and event.actor_id == "monk" for event in result.events)

    saved = tmp_path / "wolf-critical-failure.json"
    game.save(saved)
    restored = Encounter.load(saved)
    assert restored.inspect().choice is None
    assert restored._state.creatures["monk"].prone


def test_tiger_bleed_saved_choice_rejects_tampered_options(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    dog_definition = replace(
        content.get_definition("guard_dog_mc2924"),
        definition_id="w5_tiger_bleed_saved_choice_dog",
        hp=30,
    )
    monkeypatch.setattr(content, "CREATURES", content.CREATURES | {dog_definition.definition_id: dog_definition})
    setup = _setup(
        monkeypatch,
        "w5_tiger_bleed_saved_choice",
        (
            CreaturePlacement("monk", "monk_tiger_stance_level_1", "Tiger Monk", "blue", Position(1, 1)),
            CreaturePlacement("wizard", "wizard_battle_magic_level_1_staged", "Wizard", "blue", Position(6, 1)),
            CreaturePlacement("dog", "w5_tiger_bleed_saved_choice_dog", "Dog", "red", Position(2, 1)),
        ),
    )
    game = Encounter.start(setup, rolls=(20, 20, 20, 20, 6) + (20,) * 35)
    _monk_turn(game)
    game._state.creatures["monk"].hero_points = 0
    game.execute(TigerStance())
    wizard = game._state.creatures["wizard"]
    dog = game._state.creatures["dog"]
    dog.hp = 30
    game._apply_persistent_effect(game._state, wizard, dog, "gouging_claw", "bleed", flat=2)
    paused = game.execute(Strike("dog", "tiger_claws"))
    assert paused.status is ResultStatus.PAUSED
    assert paused.inspection.choice is not None
    saved = tmp_path / "tiger-bleed-choice.json"
    game.save(saved)

    payload = json.loads(saved.read_text(encoding="utf-8"))
    payload["state"]["pending_choice"]["options"] = [["existing", "Keep existing bleed"]]
    saved.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ValueError, match="invalid Tiger bleed choice"):
        Encounter.load(saved)


def test_tiger_critical_finish_clears_stance_without_lingering_bleed() -> None:
    game = Encounter.start(content.get_setup("w5_tiger_stance_vs_guard_dog"), rolls=(20, 20, 20, 6) + (20,) * 36)
    _monk_turn(game)
    monk = game._state.creatures["monk"]
    dog = game._state.creatures["dog"]
    monk.hero_points = 0
    dog.position = Position(2, 1)
    dog.hp = 1
    assert game.execute(TigerStance()).status is ResultStatus.COMPLETED
    result = game.execute(Strike("dog", "tiger_claws"))
    assert result.status is ResultStatus.COMPLETED
    assert not game.inspect().in_progress
    assert game.inspect().winner_team == "blue"
    assert game._state.persistent_effects == []
    assert game._state.martial_stances == {}
