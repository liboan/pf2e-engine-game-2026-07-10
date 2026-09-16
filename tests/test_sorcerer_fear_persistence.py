"""Focused save/load checks for the staged Fear and Flee paths.

The Fear/Will Hero sequence below is public runtime evidence.  The Flee
reaction case is deliberately labelled as a constructed snapshot: the
two-actor staged room has no Reactive Strike reactor, so it exercises the
save-format path and persistence admission without claiming a public reaction
encounter.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from pf2e.content import ANGELIC_FEAR_SETUP, ANGELIC_FIRST_CAST_SETUP
from pf2e.encounter import Encounter
from pf2e.model import (
    ActionContinuation,
    Cast,
    ChoiceOption,
    EndTurn,
    Flee,
    PendingChoice,
    Position,
    ResultStatus,
)
from pf2e.persistence import load_encounter


def _finish_start_choices(game: Encounter) -> None:
    while (choice := game.inspect().choice) is not None:
        option_id = (
            "keep"
            if any(item.option_id == "keep" for item in choice.options)
            else choice.options[0].option_id
        )
        result = game.choose(choice.choice_id, option_id, choice.owner_actor_id)
        assert result.status is ResultStatus.COMPLETED


def _fear_room(*, die: int = 1) -> Encounter:
    game = Encounter.start(ANGELIC_FEAR_SETUP, rolls=(20, 1, die))
    _finish_start_choices(game)
    assert game.inspect().turn_actor_id == "angelic_sorcerer"
    return game


def _read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _write(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_public_fear_will_hero_choice_round_trips_without_a_second_slot_spend(
    tmp_path: Path,
) -> None:
    game = Encounter.start(ANGELIC_FIRST_CAST_SETUP, rolls=(20, 1, 1, 4, 20))
    _finish_start_choices(game)

    offered = game.execute(Cast("fear", "sorcerer_ally"))
    assert offered.status is ResultStatus.PAUSED
    choice = offered.inspection.choice
    assert choice is not None and choice.kind == "spell_save_hero_reroll"
    assert choice.owner_actor_id == "sorcerer_ally"
    assert "Will save" in choice.prompt
    assert game._state.creatures["angelic_sorcerer"].spontaneous_slots[0].remaining == 2

    path = tmp_path / "pending-fear-will.json"
    game.save(path)
    payload = _read(path)
    pending = payload["state"]["pending_choice"]
    continuation = pending["continuation"]
    assert continuation["spell_id"] == "fear"
    assert continuation["spell_actions"] == 2
    assert continuation["spell_source_kind"] == "spontaneous"
    assert continuation["slot_id"] == "angelic_rank1"
    assert continuation["sorcerous_potency"] == 0
    assert continuation["blood_magic_recipient_id"] is None
    assert pending["owner_actor_id"] == "sorcerer_ally"
    assert pending["check_owner_actor_id"] == "sorcerer_ally"
    assert pending["check_kind"] == "spell_save"

    restored = Encounter.load(path)
    assert restored.inspect() == offered.inspection
    restored_choice = restored.inspect().choice
    assert restored_choice is not None
    completed = restored.choose(
        restored_choice.choice_id,
        "keep",
        restored_choice.owner_actor_id,
    )
    assert completed.status is ResultStatus.COMPLETED
    assert any(event.kind == "condition_applied" for event in completed.events)
    assert restored._state.creatures["angelic_sorcerer"].spontaneous_slots[0].remaining == 2


@pytest.mark.parametrize(
    ("field", "value"),
    (
        ("spell_source_kind", "prepared"),
        ("slot_id", "wrong_rank_pool"),
        ("sorcerous_potency", 1),
        ("blood_magic_recipient_id", "angelic_sorcerer"),
    ),
)
def test_pending_fear_rejects_forged_resource_provenance(
    tmp_path: Path, field: str, value: object,
) -> None:
    game = Encounter.start(ANGELIC_FIRST_CAST_SETUP, rolls=(20, 1, 1, 4, 20))
    _finish_start_choices(game)
    offered = game.execute(Cast("fear", "sorcerer_ally"))
    assert offered.status is ResultStatus.PAUSED

    path = tmp_path / f"forged-fear-{field}.json"
    game.save(path)
    payload = _read(path)
    payload["state"]["pending_choice"]["continuation"][field] = value
    _write(path, payload)

    with pytest.raises(ValueError, match="Fear|Blood Magic provenance"):
        Encounter.load(path)


def test_pending_fear_rejects_a_forged_target_owner(tmp_path: Path) -> None:
    game = Encounter.start(ANGELIC_FIRST_CAST_SETUP, rolls=(20, 1, 1, 4, 20))
    _finish_start_choices(game)
    assert game.execute(Cast("fear", "sorcerer_ally")).status is ResultStatus.PAUSED
    path = tmp_path / "forged-fear-owner.json"
    game.save(path)
    payload = _read(path)
    payload["state"]["pending_choice"]["owner_actor_id"] = "angelic_sorcerer"
    _write(path, payload)

    with pytest.raises(ValueError, match="Fear Will Hero|spell save"):
        Encounter.load(path)


def test_pending_fear_rejects_a_check_with_a_changed_current_dc(tmp_path: Path) -> None:
    game = Encounter.start(ANGELIC_FIRST_CAST_SETUP, rolls=(20, 1, 1, 4, 20))
    _finish_start_choices(game)
    assert game.execute(Cast("fear", "sorcerer_ally")).status is ResultStatus.PAUSED
    path = tmp_path / "forged-fear-dc.json"
    game.save(path)
    payload = _read(path)
    payload["state"]["pending_choice"]["check"]["dc"] += 1
    _write(path, payload)

    with pytest.raises(ValueError, match="inconsistent fear DC"):
        Encounter.load(path)


def test_public_fear_fleeing_effect_round_trips_with_fixed_deadline(
    tmp_path: Path,
) -> None:
    game = _fear_room(die=1)
    result = game.execute(Cast("fear", "sorcerer_dog"))
    assert result.status is ResultStatus.COMPLETED
    effect = next(
        effect
        for effect in game._state.active_effects
        if effect.kind == "fleeing"
    )
    assert (
        effect.source_actor_id,
        effect.target_actor_id,
        effect.value,
        effect.expires_at_source_start,
        effect.expires_at_world_time,
    ) == ("angelic_sorcerer", "sorcerer_dog", 1, 2, 6)

    path = tmp_path / "fear-fleeing.json"
    game.save(path)
    restored = Encounter.load(path)
    restored_effect = next(
        effect
        for effect in restored._state.active_effects
        if effect.kind == "fleeing"
    )
    assert restored_effect == effect
    assert any(
        effect.kind == "frightened"
        and effect.value == 3
        and effect.expiration.anchor_actor_id == "sorcerer_dog"
        and effect.expiration.boundary == "end"
        for effect in restored._state.condition_effects
    )


@pytest.mark.parametrize(
    "mutation",
    ("wrong_value", "wrong_source_deadline", "refreshed_deadline", "wrong_source"),
)
def test_fleeing_effect_rejects_forged_source_or_deadline(
    tmp_path: Path, mutation: str,
) -> None:
    game = _fear_room(die=1)
    assert game.execute(Cast("fear", "sorcerer_dog")).status is ResultStatus.COMPLETED
    path = tmp_path / f"forged-fleeing-{mutation}.json"
    game.save(path)
    payload = _read(path)
    row = next(
        row
        for row in payload["state"]["active_effects"]
        if row[1] == "fleeing"
    )
    if mutation == "wrong_value":
        row[4] = 2
    elif mutation == "wrong_source_deadline":
        row[5] = 3
    elif mutation == "refreshed_deadline":
        row[6] = payload["state"]["world_time_seconds"] + 12
    else:
        row[2] = "sorcerer_dog"
        row[3] = "angelic_sorcerer"
    _write(path, payload)

    with pytest.raises(ValueError, match="active spell effect"):
        Encounter.load(path)


def test_constructed_flee_reaction_snapshot_round_trips_shape_only(
    tmp_path: Path,
) -> None:
    """Validate the public movement continuation shape without claiming a reaction encounter."""
    game = _fear_room(die=1)
    assert game.execute(Cast("fear", "sorcerer_dog")).status is ResultStatus.COMPLETED
    game.execute(EndTurn())
    dog = game._state.creatures["sorcerer_dog"]
    continuation = ActionContinuation(
        kind="movement",
        actor_id="sorcerer_dog",
        path=(Position(4, 0),),
        next_step=0,
        movement_kind="flee",
        reaction_trigger="movement",
    )
    game._state.pending_choice = PendingChoice(
        choice_id=game._state.next_choice_id,
        kind="reaction",
        owner_actor_id="angelic_sorcerer",
        prompt="The source may use Reactive Strike.",
        options=(ChoiceOption("decline", "Decline"),),
        actor_id=dog.actor_id,
        target_id=dog.actor_id,
        continuation=continuation,
    )
    game._state.next_choice_id += 1

    path = tmp_path / "constructed-flee-reaction.json"
    game.save(path)
    state, _dice = load_encounter(path)
    assert state.pending_choice is not None
    assert state.pending_choice.continuation is not None
    assert state.pending_choice.continuation.movement_kind == "flee"
    assert state.pending_choice.continuation.path == (Position(4, 0),)


@pytest.mark.parametrize("field", ("movement_kind", "path"))
def test_constructed_flee_reaction_snapshot_rejects_bad_path_admission(
    tmp_path: Path, field: str,
) -> None:
    game = _fear_room(die=1)
    assert game.execute(Cast("fear", "sorcerer_dog")).status is ResultStatus.COMPLETED
    game.execute(EndTurn())
    continuation = ActionContinuation(
        kind="movement",
        actor_id="sorcerer_dog",
        path=(Position(4, 0),),
        next_step=0,
        movement_kind="flee",
        reaction_trigger="movement",
    )
    game._state.pending_choice = PendingChoice(
        choice_id=game._state.next_choice_id,
        kind="reaction",
        owner_actor_id="angelic_sorcerer",
        prompt="The source may use Reactive Strike.",
        options=(ChoiceOption("decline", "Decline"),),
        actor_id="sorcerer_dog",
        target_id="sorcerer_dog",
        continuation=continuation,
    )
    game._state.next_choice_id += 1
    path = tmp_path / f"bad-constructed-flee-{field}.json"
    game.save(path)
    payload = _read(path)
    raw = payload["state"]["pending_choice"]["continuation"]
    raw[field] = "stride" if field == "movement_kind" else []
    _write(path, payload)

    with pytest.raises(ValueError, match="interrupted movement path|Flee movement reaction"):
        load_encounter(path)
