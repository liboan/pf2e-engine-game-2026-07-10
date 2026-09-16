"""Focused first-stage dim-light targeting checks."""

from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path
from types import MappingProxyType

import pytest
import pf2e.content as content

from pf2e import Cast, Encounter, EndTurn, Interact, ResultStatus, Strike, ViciousSwing
from pf2e.content import ANGELIC_FIRST_CAST_SETUP, DIM_REACTION_SETUP, DIM_TARGETING_SETUP


def _keep_initiative(game: Encounter) -> None:
    while game.inspect().choice is not None:
        choice = game.inspect().choice
        assert choice is not None and choice.kind == "initiative_hero_reroll"
        result = game.choose(choice.choice_id, "keep", choice.owner_actor_id)
        assert result.status in {ResultStatus.PAUSED, ResultStatus.COMPLETED}


def _actor(game: Encounter, actor_id: str):
    return next(actor for actor in game.inspect().actors if actor.actor_id == actor_id)


def test_dim_strike_flat_four_fails_without_attack_roll_or_guidance() -> None:
    game = Encounter.start(DIM_TARGETING_SETUP, rolls=(20, 1, 4))
    _keep_initiative(game)

    result = game.execute(Strike("guard_dog_a", attack_id="longsword"))
    assert result.status is ResultStatus.PAUSED
    assert result.inspection.choice is not None
    assert result.inspection.choice.kind == "concealment_hero_reroll"
    assert [event.kind for event in result.events] == ["concealment_flat_check"]
    assert result.events[0].check is not None and result.events[0].check.die == 4

    kept = game.choose(
        result.inspection.choice.choice_id,
        "keep",
        result.inspection.choice.owner_actor_id,
    )
    assert kept.status is ResultStatus.COMPLETED
    assert not any(event.kind == "strike" for event in kept.events)
    assert any(event.kind == "concealment_failed" for event in kept.events)
    fighter = _actor(game, "fighter_a")
    assert (fighter.actions_remaining, fighter.strikes_this_turn, fighter.hero_points) == (2, 1, 1)
    assert _actor(game, "guard_dog_a").hp == 8


def test_dim_concealment_save_rerolls_four_to_five_then_attacks_once_and_saves_load(
    tmp_path: Path,
) -> None:
    game = Encounter.start(DIM_TARGETING_SETUP, rolls=(20, 1, 4, 5, 10, 1))
    _keep_initiative(game)
    paused = game.execute(Strike("guard_dog_a", attack_id="longsword"))
    choice = paused.inspection.choice
    assert choice is not None and choice.kind == "concealment_hero_reroll"

    path = tmp_path / "dim-concealment.json"
    game.save(path)
    saved = json.loads(path.read_text(encoding="utf-8"))
    assert saved["state"]["ambient_light"] == "dim"
    assert saved["state"]["pending_choice"]["concealment_checked"] is True
    restored = Encounter.load(path)
    assert restored.inspect() == paused.inspection

    rerolled = restored.choose(choice.choice_id, "spend_hero_point", choice.owner_actor_id)
    assert rerolled.status is ResultStatus.COMPLETED
    flat = [
        event for event in rerolled.events
        if event.kind == "hero_reroll" and event.check is not None and event.check.dc == 5
    ]
    attacks = [event for event in rerolled.events if event.kind == "strike"]
    assert len(flat) == 1 and flat[0].check is not None and flat[0].check.die == 5
    assert len(attacks) == 1
    assert attacks[0].check is not None and attacks[0].check.die == 10
    fighter = _actor(restored, "fighter_a")
    assert (fighter.actions_remaining, fighter.strikes_this_turn, fighter.hero_points) == (2, 1, 0)
    assert _actor(restored, "guard_dog_a").hp == 3


def test_low_light_guard_dog_observer_skips_dim_concealment() -> None:
    game = Encounter.start(DIM_TARGETING_SETUP, rolls=(20, 1, 12, 1))
    _keep_initiative(game)
    assert game.execute(EndTurn()).status is ResultStatus.COMPLETED
    assert game.target_is_concealed("guard_dog_a", "fighter_a") is False

    result = game.execute(Strike("fighter_a", attack_id="jaws"))
    assert result.status is ResultStatus.COMPLETED
    assert [event.kind for event in result.events] == ["strike", "damage"]
    assert _actor(game, "fighter_a").hp == 19


def test_dim_vicious_swing_commits_two_actions_and_two_attack_count_before_gate() -> None:
    game = Encounter.start(DIM_TARGETING_SETUP, rolls=(20, 1, 5, 10, 1, 1))
    _keep_initiative(game)
    paused = game.execute(ViciousSwing("guard_dog_a", attack_id="longsword"))
    choice = paused.inspection.choice
    assert choice is not None and choice.kind == "concealment_hero_reroll"
    after_flat = game.choose(choice.choice_id, "keep", choice.owner_actor_id)
    assert after_flat.inspection.choice is not None
    assert after_flat.inspection.choice.kind == "attack_hero_reroll"
    result = game.choose(
        after_flat.inspection.choice.choice_id,
        "keep",
        after_flat.inspection.choice.owner_actor_id,
    )
    fighter = _actor(game, "fighter_a")
    assert result.status is ResultStatus.COMPLETED
    assert (fighter.actions_remaining, fighter.strikes_this_turn, fighter.hero_points) == (1, 2, 1)
    assert len([event for event in result.events if event.kind == "strike"]) == 1


def test_saved_reactive_strike_concealment_failure_resumes_interact() -> None:
    game = Encounter.start(DIM_REACTION_SETUP, rolls=(20, 1, 4))
    _keep_initiative(game)
    started = game.execute(Interact("stow", "longsword"))
    reaction = started.inspection.choice
    assert reaction is not None and reaction.kind == "reaction"
    accepted = game.choose(reaction.choice_id, "accept", reaction.owner_actor_id)
    concealment = accepted.inspection.choice
    assert concealment is not None and concealment.kind == "concealment_hero_reroll"

    result = game.choose(concealment.choice_id, "keep", concealment.owner_actor_id)
    assert result.status is ResultStatus.COMPLETED
    assert any(event.kind == "concealment_failed" for event in result.events)
    assert _actor(game, "fighter_a").held_items == ()
    assert _actor(game, "fighter_a").stowed_items == ("longsword",)
    assert _actor(game, "fighter_b").reaction_available is False


def test_dim_divine_lance_fails_concealment_before_spell_attack(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    setup = replace(
        ANGELIC_FIRST_CAST_SETUP,
        setup_id="dim_divine_lance_guard",
        ambient_light="dim",
    )
    monkeypatch.setattr(
        content,
        "_STAGED_SETUPS",
        MappingProxyType({**content._STAGED_SETUPS, setup.setup_id: setup}),
    )
    game = Encounter.start(setup, rolls=(20, 1, 1, 4))
    _keep_initiative(game)
    game._state.creatures["angelic_sorcerer"].hero_points = 1
    before = _actor(game, "angelic_sorcerer")
    result = game.execute(Cast("divine_lance", target_id="sorcerer_dog"))
    after = _actor(game, "angelic_sorcerer")
    assert result.status is ResultStatus.PAUSED
    assert [event.kind for event in result.events] == ["cast_started", "concealment_flat_check"]
    assert result.events[-1].check is not None and result.events[-1].check.die == 4
    assert result.inspection.choice is not None
    assert result.inspection.choice.kind == "concealment_hero_reroll"
    assert (after.actions_remaining, after.strikes_this_turn) == (
        before.actions_remaining - 2,
        before.strikes_this_turn + 1,
    )


def test_saved_scene_light_is_strictly_bound_to_setup(tmp_path: Path) -> None:
    game = Encounter.start(DIM_TARGETING_SETUP, rolls=(20, 1))
    _keep_initiative(game)
    path = tmp_path / "dim-scene.json"
    game.save(path)
    saved = json.loads(path.read_text(encoding="utf-8"))
    del saved["state"]["ambient_light"]
    path.write_text(json.dumps(saved), encoding="utf-8")
    with pytest.raises(ValueError, match="ambient_light"):
        Encounter.load(path)
