"""W3 finite condition-bomb family: Dread Ampoule and Glue Bomb.

Sources checked 2026-09-20:
* Dread Ampoule: https://2e.aonprd.com/Equipment.aspx?ID=3292
* Glue Bomb: https://2e.aonprd.com/Equipment.aspx?ID=3295
* Bomb splash: https://2e.aonprd.com/Rules.aspx?ID=236
* Alchemist formula grants: https://2e.aonprd.com/Classes.aspx?ID=56
"""

import json
from dataclasses import replace
from pathlib import Path
from types import MappingProxyType

import pytest

from pf2e.alchemist_content import (
    BOMBER_LEVEL_2_CONDITION_BOMB_FORMULA_IDS,
    admitted_bomber_bomb_facts,
)
from pf2e.alchemy_content import FORMULAS_BY_ID
import pf2e.content as content
from pf2e.content import get_setup
from pf2e.encounter import Encounter
from pf2e.model import (
    ActiveSpellEffect,
    Choose,
    CreaturePlacement,
    EndTurn,
    EncounterSetup,
    Interact,
    Position,
    QuickAlchemy,
    QuickBomber,
    ResultStatus,
)
from pf2e.skill_actions import Escape
from pf2e.terminal import run_terminal
from pf2e.opponent_content import SKELETON_GUARD


def _settle(game: Encounter) -> None:
    while game.inspect().choice is not None:
        choice = game.inspect().choice
        assert choice is not None
        option = "keep" if any(item.option_id == "keep" for item in choice.options) else choice.options[0].option_id
        assert game.execute(Choose(choice.choice_id, option, choice.owner_actor_id)).status in {
            ResultStatus.COMPLETED,
            ResultStatus.PAUSED,
        }


def _condition_bomb_game(*, rolls=(10, 1, 10, 20)) -> Encounter:
    game = Encounter.start(
        get_setup("l2_bomber_condition_bombs_vs_guard_dog"), rolls=rolls,
    )
    _settle(game)
    return game


def _throw(game: Encounter, formula_id: str) -> None:
    assert game.execute(QuickAlchemy("create_consumable", formula_id)).status is ResultStatus.COMPLETED
    result = game.execute(QuickBomber("dog", formula_id))
    assert result.status in {ResultStatus.COMPLETED, ResultStatus.PAUSED}
    _settle(game)


def test_w3_formula_book_admits_two_condition_bombs_and_skips_thunderstone() -> None:
    assert BOMBER_LEVEL_2_CONDITION_BOMB_FORMULA_IDS[-2:] == (
        "dread_ampoule_lesser", "glue_bomb_lesser",
    )
    assert admitted_bomber_bomb_facts("dread_ampoule_lesser", character_level=2) is FORMULAS_BY_ID["dread_ampoule_lesser"].facts
    assert admitted_bomber_bomb_facts("glue_bomb_lesser", character_level=2) is FORMULAS_BY_ID["glue_bomb_lesser"].facts
    assert admitted_bomber_bomb_facts("thunderstone_lesser", character_level=2) is None
    dread = FORMULAS_BY_ID["dread_ampoule_lesser"].facts
    glue = FORMULAS_BY_ID["glue_bomb_lesser"].facts
    assert (dread.initial_damage_dice, dread.splash_damage, dread.on_hit_effect, dread.on_critical_hit_value) == ((6,), 1, "frightened", 2)
    assert (glue.initial_damage_dice, glue.splash_damage, glue.on_hit_effect_value, glue.on_hit_effect_duration_seconds) == ((), 0, 10, 60)


def test_dread_ampoule_applies_critical_frightened_and_standard_decay(tmp_path: Path) -> None:
    game = _condition_bomb_game(rolls=(10, 1, 20, 1, 10, 1, 10, 1, 10, 1))
    _throw(game, "dread_ampoule_lesser")
    effect = next(effect for effect in game._state.condition_effects if effect.kind == "frightened")
    assert effect.value == 2
    assert effect.expiration.anchor_actor_id == "dog"
    path = tmp_path / "w3-dread.json"
    game.save(path)
    restored = Encounter.load(path)
    assert next(effect for effect in restored._state.condition_effects if effect.kind == "frightened").value == 2
    assert restored.execute(EndTurn()).status is ResultStatus.COMPLETED
    assert restored.execute(EndTurn()).status is ResultStatus.COMPLETED
    assert next(effect for effect in restored._state.condition_effects if effect.kind == "frightened").value == 1


def test_dread_respects_published_mental_and_poison_immunity(monkeypatch: pytest.MonkeyPatch) -> None:
    base = get_setup("l2_bomber_condition_bombs_vs_guard_dog")
    setup = replace(
        base,
        setup_id="w3_dread_skeleton_immunity",
        placements=(base.placements[0], CreaturePlacement(
            "skeleton", SKELETON_GUARD.definition.definition_id, "Skeleton Guard", "red", Position(7, 1),
        )),
    )
    monkeypatch.setattr(
        content,
        "_STAGED_CREATURES",
        MappingProxyType({**content._STAGED_CREATURES, SKELETON_GUARD.definition.definition_id: SKELETON_GUARD.definition}),
    )
    monkeypatch.setattr(
        content,
        "_STAGED_SETUPS",
        MappingProxyType({**content._STAGED_SETUPS, setup.setup_id: setup}),
    )
    game = Encounter.start(setup, rolls=(10, 1, 10, 1))
    _settle(game)
    assert game.execute(QuickAlchemy("create_consumable", "dread_ampoule_lesser")).status is ResultStatus.COMPLETED
    assert game.execute(QuickBomber("skeleton", "dread_ampoule_lesser")).status in {ResultStatus.COMPLETED, ResultStatus.PAUSED}
    _settle(game)
    assert not any(effect.kind == "frightened" for effect in game._state.condition_effects)


def test_glue_bomb_saves_active_minute_rider_and_escape_removes_it(tmp_path: Path) -> None:
    game = _condition_bomb_game()
    _throw(game, "glue_bomb_lesser")
    glue = next(effect for effect in game._state.active_effects if effect.kind == "alchemy_glue_bomb_lesser")
    assert glue.value == 10
    assert glue.expires_at_world_time == 60
    path = tmp_path / "w3-glue.json"
    game.save(path)
    restored = Encounter.load(path)
    assert any(effect.effect_id == glue.effect_id for effect in restored._state.active_effects)
    while restored.inspect().turn_actor_id != "dog":
        assert restored.execute(EndTurn()).status is ResultStatus.COMPLETED
    escaped = restored.execute(Escape(glue.effect_id, "athletics"))
    _settle(restored)
    assert escaped.status in {ResultStatus.COMPLETED, ResultStatus.PAUSED}
    assert not any(effect.effect_id == glue.effect_id for effect in restored._state.active_effects)


def test_glue_critical_immobilization_is_one_round_from_throwers_next_turn(tmp_path: Path) -> None:
    game = _condition_bomb_game(rolls=(10, 1, 20, 1))
    _throw(game, "glue_bomb_lesser")
    immobilized = next(effect for effect in game._state.condition_effects if effect.kind == "immobilized")
    assert (immobilized.expiration.anchor_actor_id, immobilized.expiration.boundary) == ("alchemist", "start")
    path = tmp_path / "w3-glue-critical.json"
    game.save(path)
    restored = Encounter.load(path)
    assert next(effect for effect in restored._state.condition_effects if effect.kind == "immobilized") == immobilized
    assert restored.execute(EndTurn()).status is ResultStatus.COMPLETED
    while restored.inspect().turn_actor_id != "alchemist":
        assert restored.execute(EndTurn()).status is ResultStatus.COMPLETED
    assert not any(effect.kind == "immobilized" for effect in restored._state.condition_effects)


def test_glue_three_interacts_remove_effects_and_allow_nonconsecutive_progress() -> None:
    game = _condition_bomb_game()
    _throw(game, "glue_bomb_lesser")
    glue = next(effect for effect in game._state.active_effects if effect.kind == "alchemy_glue_bomb_lesser")
    game._state.creatures["dog"].position = Position(2, 1)
    while game.inspect().turn_actor_id != "dog":
        assert game.execute(EndTurn()).status is ResultStatus.COMPLETED
    for expected in (1, 2):
        result = game.execute(Interact("remove_glue", glue.effect_id))
        assert result.status is ResultStatus.COMPLETED
        assert next(effect for effect in game._state.active_effects if effect.effect_id == glue.effect_id).glue_removal_actions == expected
        assert game.execute(EndTurn()).status is ResultStatus.COMPLETED
        while game.inspect().turn_actor_id != "dog":
            assert game.execute(EndTurn()).status is ResultStatus.COMPLETED
    assert game.execute(Interact("remove_glue", glue.effect_id)).status is ResultStatus.COMPLETED
    assert not any(effect.effect_id == glue.effect_id for effect in game._state.active_effects)


def test_glue_escape_does_not_remove_another_colon_item_or_target(monkeypatch: pytest.MonkeyPatch) -> None:
    base = get_setup("l2_bomber_condition_bombs_vs_guard_dog")
    setup = replace(
        base,
        setup_id="w3_glue_two_targets",
        placements=base.placements + (
            CreaturePlacement("dog_two", "guard_dog_mc2924", "Second Guard Dog", "red", Position(2, 1)),
        ),
    )
    monkeypatch.setattr(
        content,
        "_STAGED_SETUPS",
        MappingProxyType({**content._STAGED_SETUPS, setup.setup_id: setup}),
    )
    game = Encounter.start(setup, rolls=(10, 1, 20, 20, 20))
    _settle(game)
    game._state.creatures["dog"].position = Position(2, 1)
    game._state.active_effects.extend((
        ActiveSpellEffect("glue_bomb:alchemist:quick:1", "alchemy_glue_bomb_lesser", "alchemist", "dog", 10, 1, 60),
        ActiveSpellEffect("glue_bomb:alchemist:quick:2", "alchemy_glue_bomb_lesser", "alchemist", "dog_two", 10, 1, 60),
    ))
    while game.inspect().turn_actor_id != "dog":
        assert game.execute(EndTurn()).status is ResultStatus.COMPLETED
    result = game.execute(Escape("glue_bomb:alchemist:quick:1", "athletics"))
    _settle(game)
    assert result.status in {ResultStatus.COMPLETED, ResultStatus.PAUSED}
    assert not any(effect.effect_id == "glue_bomb:alchemist:quick:1" for effect in game._state.active_effects)
    assert any(effect.effect_id == "glue_bomb:alchemist:quick:2" for effect in game._state.active_effects)


def test_glue_bomb_saved_provenance_rejects_item_tampering(tmp_path: Path) -> None:
    game = _condition_bomb_game()
    _throw(game, "glue_bomb_lesser")
    path = tmp_path / "w3-glue-tamper.json"
    game.save(path)
    payload = json.loads(path.read_text())
    payload["state"]["active_effects"][0][0] = "glue_bomb:alchemist:quick:999"
    path.write_text(json.dumps(payload))
    with pytest.raises(ValueError, match="invalid active spell effect"):
        Encounter.load(path)


def test_terminal_lists_and_throws_glue_bomb() -> None:
    commands = iter((
        "2", "1",  # Keep initiative.
        "4", "10",  # Quick Alchemy -> Glue Bomb.
        "6", "1", "1",  # Quick Bomber -> prepared Glue Bomb -> Guard Dog.
        "2", "1",  # Resolve the saved Strike choice, then keep it.
        "x",
    ))
    output: list[str] = []
    assert run_terminal(
        setup=get_setup("l2_bomber_condition_bombs_vs_guard_dog"),
        rolls=(10, 1, 10, 1), input_fn=lambda: next(commands), output_fn=output.append,
    ) == 0
    transcript = "\n".join(output)
    assert "Dread Ampoule (lesser)" in transcript
    assert "Glue Bomb (lesser)" in transcript
    assert "creates glue bomb lesser" in transcript
    assert "uses Quick Bomber to draw glue bomb lesser" in transcript
