"""Focused public recovery and elapsed-clock checks."""

from __future__ import annotations

import json
from pathlib import Path

from pf2e.content import ANGELIC_FIRST_CAST_SETUP, DIM_TARGETING_SETUP
from pf2e.encounter import Encounter
from pf2e.model import Cast, EndTurn, Position, ResultStatus, Strike, Stride
from pf2e.skill_actions import Trip


def _keep_start_choices(game: Encounter) -> None:
    while game.inspect().choice is not None:
        choice = game.inspect().choice
        assert choice is not None
        option_id = "keep" if any(option.option_id == "keep" for option in choice.options) else choice.options[0].option_id
        result = game.choose(choice.choice_id, option_id, choice.owner_actor_id)
        assert result.status is ResultStatus.COMPLETED


def _finished_spent_focus_game() -> Encounter:
    """Finish a real healthy-start room after spending the Sorcerer's focus."""
    game = Encounter.start(ANGELIC_FIRST_CAST_SETUP, rolls=(20, 1, 1, 20, 4, 4))
    initial = game.inspect()
    assert all(actor.hp == actor.max_hp for actor in initial.actors)
    _keep_start_choices(game)

    halo = game.execute(Cast("angelic_halo"))
    assert halo.status is ResultStatus.PAUSED
    choice = halo.inspection.choice
    assert choice is not None and choice.kind == "spell_blood_magic_recipient"
    assert game.choose(choice.choice_id, "angelic_sorcerer", choice.owner_actor_id).status is ResultStatus.COMPLETED
    assert next(actor for actor in game.inspect().actors if actor.actor_id == "angelic_sorcerer").focus_points == 0

    # The enemy and ally turns pass through the public EndTurn path. The final
    # critical Divine Lance defeats the dog and closes the encounter.
    for _ in range(3):
        assert game.execute(EndTurn()).status is ResultStatus.COMPLETED
    final = game.execute(Cast("divine_lance", "sorcerer_dog"))
    assert final.status is ResultStatus.COMPLETED
    assert not game.inspect().in_progress
    return game


def test_refocus_advances_clock_restores_focus_and_round_trips_save(tmp_path: Path) -> None:
    game = _finished_spent_focus_game()
    before = game.inspect()
    assert before.world_time_seconds == 6
    result = game.refocus("angelic_sorcerer")
    assert result.status is ResultStatus.COMPLETED
    assert result.inspection.world_time_seconds == 606
    sorcerer = next(actor for actor in result.inspection.actors if actor.actor_id == "angelic_sorcerer")
    assert (sorcerer.focus_points, sorcerer.focus_capacity) == (1, 1)
    assert sorcerer.hp == next(actor for actor in before.actors if actor.actor_id == "angelic_sorcerer").hp
    assert not sorcerer.effects

    path = tmp_path / "refocus.json"
    game.save(path)
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["state"]["encounter_start_seconds"] == 0
    assert payload["state"]["world_time_seconds"] == 606
    assert payload["state"]["creatures"]["angelic_sorcerer"]["focus_points"] == 1
    restored = Encounter.load(path)
    assert restored.inspect() == game.inspect()


def test_refocus_rejects_in_combat_and_without_focus_pool_atomically() -> None:
    game = Encounter.start(ANGELIC_FIRST_CAST_SETUP, rolls=(20, 1, 1))
    before = game.inspect()
    rejected = game.refocus("angelic_sorcerer")
    assert rejected.status is ResultStatus.REJECTED
    assert game.inspect() == before

    finished = _finished_spent_focus_game()
    before = finished.inspect()
    rejected = finished.refocus("sorcerer_ally")
    assert rejected.status is ResultStatus.REJECTED
    assert finished.inspect() == before


def test_refocus_uses_guidance_actual_expiry_for_one_hour_cooldown() -> None:
    game = Encounter.start(ANGELIC_FIRST_CAST_SETUP, rolls=(20, 1, 1, 20, 4))
    _keep_start_choices(game)
    assert game.execute(Cast("guidance", "sorcerer_ally")).status is ResultStatus.COMPLETED
    assert game.execute(EndTurn()).status is ResultStatus.COMPLETED
    assert game.execute(EndTurn()).status is ResultStatus.COMPLETED
    assert game.execute(
        Stride((Position(3, 2), Position(4, 2)))
    ).status is ResultStatus.COMPLETED
    attack = game.execute(Strike("sorcerer_dog", attack_id="longsword"))
    assert attack.status is ResultStatus.PAUSED
    guidance = attack.inspection.choice
    assert guidance is not None and guidance.kind == "guidance_use"
    kept = game.choose(guidance.choice_id, "keep", guidance.owner_actor_id)
    if kept.inspection.choice is not None:
        assert kept.inspection.choice.kind == "attack_hero_reroll"
        kept = game.choose(kept.inspection.choice.choice_id, "keep", kept.inspection.choice.owner_actor_id)
    assert not game.inspect().in_progress
    assert game.refocus("angelic_sorcerer").status is ResultStatus.COMPLETED
    ally = next(actor for actor in game.inspect().actors if actor.actor_id == "sorcerer_ally")
    # Guidance expired at world time 6 while the 10-minute jump ended at 600;
    # the one-hour lockout therefore ends at 606 rather than being restarted
    # at the end of the jump (1200).
    assert ally.guidance_immune_until_seconds == 606


def test_dim_skill_targeting_reaches_assurance_after_target_flat_check(tmp_path: Path) -> None:
    game = Encounter.start(DIM_TARGETING_SETUP, rolls=(20, 1, 4))
    _keep_start_choices(game)
    started = game.execute(Trip("guard_dog_a", use_assurance=True))
    assert started.status is ResultStatus.PAUSED
    choice = started.inspection.choice
    assert choice is not None and choice.kind == "concealment_hero_reroll"

    path = tmp_path / "dim-assurance-targeting.json"
    game.save(path)
    restored = Encounter.load(path)
    result = restored.choose(choice.choice_id, "keep", choice.owner_actor_id)
    assert result.status is ResultStatus.COMPLETED
    assert [event.kind for event in result.events] == [
        "concealment_kept",
        "concealment_failed",
    ]
    assert not any(event.kind == "trip_check" for event in result.events)
