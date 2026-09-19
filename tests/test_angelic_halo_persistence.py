"""Focused persistence checks for the staged Angelic Sorcerer focus path."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from pf2e.content import ANGELIC_FIRST_CAST_SETUP
from pf2e.encounter import Encounter
from pf2e.model import Cast, EndTurn, ResultStatus


def _first_cast_game() -> Encounter:
    game = Encounter.start(ANGELIC_FIRST_CAST_SETUP, rolls=(20, 1, 1))
    while (choice := game.inspect().choice) is not None:
        option_id = (
            "keep"
            if any(option.option_id == "keep" for option in choice.options)
            else choice.options[0].option_id
        )
        result = game.choose(choice.choice_id, option_id, choice.owner_actor_id)
        assert result.status is ResultStatus.COMPLETED
    assert game.inspect().turn_actor_id == "angelic_sorcerer"
    return game


def _halo_game() -> Encounter:
    game = _first_cast_game()
    result = game.execute(Cast("angelic_halo", actions=1))
    assert result.status is ResultStatus.PAUSED
    choice = result.inspection.choice
    assert choice is not None and choice.kind == "spell_blood_magic_recipient"
    result = game.choose(choice.choice_id, "sorcerer_ally", choice.owner_actor_id)
    assert result.status is ResultStatus.COMPLETED
    assert game.inspect().choice is None
    return game


def _read_save(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_save(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_focus_pool_and_pending_halo_resource_provenance_round_trip(tmp_path: Path) -> None:
    game = _first_cast_game()
    result = game.execute(Cast("angelic_halo", actions=1))
    assert result.status is ResultStatus.PAUSED

    path = tmp_path / "pending-halo.json"
    game.save(path)
    payload = _read_save(path)
    actor = payload["state"]["creatures"]["angelic_sorcerer"]
    assert actor["focus_points"] == 0
    assert actor["focus_capacity"] == 1
    pending = payload["state"]["pending_choice"]
    continuation = pending["continuation"]
    assert continuation["spell_id"] == "angelic_halo"
    assert continuation["spell_source_kind"] == "focus"
    assert continuation["slot_id"] == "actor_focus_pool"
    assert continuation["sorcerous_potency"] == 0
    assert continuation["blood_magic_recipient_id"] is None

    restored = Encounter.load(path)
    assert restored.inspect() == result.inspection
    restored_choice = restored.inspect().choice
    assert restored_choice is not None
    completed = restored.choose(
        restored_choice.choice_id,
        "sorcerer_ally",
        restored_choice.owner_actor_id,
    )
    assert completed.status is ResultStatus.COMPLETED
    assert restored._state.creatures["angelic_sorcerer"].focus_points == 0


def test_pending_rank_heal_preserves_spontaneous_resource_provenance(
    tmp_path: Path,
) -> None:
    game = _first_cast_game()
    result = game.execute(Cast("heal", "sorcerer_ally", actions=2))
    assert result.status is ResultStatus.PAUSED
    path = tmp_path / "pending-heal.json"
    game.save(path)
    payload = _read_save(path)
    continuation = payload["state"]["pending_choice"]["continuation"]
    assert continuation["spell_source_kind"] == "spontaneous"
    assert continuation["slot_id"] == "angelic_rank1"
    assert continuation["sorcerous_potency"] == 1
    assert continuation["blood_magic_recipient_id"] is None
    assert Encounter.load(path).inspect() == result.inspection


@pytest.mark.parametrize(
    ("field", "value"),
    (("slot_id", "angelic_rank1"), ("sorcerous_potency", 1)),
)
def test_pending_halo_rejects_rank_resource_or_potency_provenance_tampering(
    tmp_path: Path, field: str, value: object
) -> None:
    game = _first_cast_game()
    result = game.execute(Cast("angelic_halo", actions=1))
    assert result.status is ResultStatus.PAUSED
    path = tmp_path / f"tampered-halo-{field}.json"
    game.save(path)
    payload = _read_save(path)
    payload["state"]["pending_choice"]["continuation"][field] = value
    _write_save(path, payload)

    with pytest.raises(ValueError, match="focus cast resource provenance"):
        Encounter.load(path)


def test_halo_effect_round_trips_with_absolute_expiry_after_time_advances(
    tmp_path: Path,
) -> None:
    game = _halo_game()
    effect = next(
        effect for effect in game._state.active_effects if effect.kind == "angelic_halo"
    )
    assert effect.value == 2
    assert effect.expires_at_source_start == 11
    assert effect.expires_at_world_time == 60

    # One later caster turn must preserve the fixed deadline while the
    # remaining source-start interval decreases.
    game.execute(EndTurn())
    game.execute(EndTurn())
    game.execute(EndTurn())
    assert game.inspect().turn_actor_id == "angelic_sorcerer"
    assert game._state.actor_start_counts["angelic_sorcerer"] == 2
    assert game._state.world_time_seconds == 6
    path = tmp_path / "halo-after-time.json"
    game.save(path)
    restored = Encounter.load(path)
    restored_effect = next(
        effect
        for effect in restored._state.active_effects
        if effect.kind == "angelic_halo"
    )
    assert restored_effect.expires_at_source_start == 11
    assert restored_effect.expires_at_world_time == 60
    assert restored_effect.expires_at_source_start > restored._state.actor_start_counts[
        "angelic_sorcerer"
    ]


def test_halo_effect_rejects_reset_absolute_deadline_after_time_advances(
    tmp_path: Path,
) -> None:
    game = _halo_game()
    game.execute(EndTurn())
    game.execute(EndTurn())
    game.execute(EndTurn())
    path = tmp_path / "reset-halo-deadline.json"
    game.save(path)
    payload = _read_save(path)
    halo = next(
        row for row in payload["state"]["active_effects"] if row[1] == "angelic_halo"
    )
    halo[6] = payload["state"]["world_time_seconds"] + 60
    _write_save(path, payload)

    with pytest.raises(ValueError, match="active spell effect"):
        Encounter.load(path)


@pytest.mark.parametrize("mutation", ("short", "expired", "wrong_target"))
def test_halo_effect_rejects_invalid_saved_shape_or_expiry(
    tmp_path: Path, mutation: str
) -> None:
    game = _halo_game()
    path = tmp_path / f"invalid-halo-{mutation}.json"
    game.save(path)
    payload = _read_save(path)
    effects = payload["state"]["active_effects"]
    halo_index = next(
        index for index, row in enumerate(effects) if row[1] == "angelic_halo"
    )
    if mutation == "short":
        effects[halo_index] = effects[halo_index][:6]
    elif mutation == "expired":
        effects[halo_index][6] = payload["state"]["world_time_seconds"]
    else:
        effects[halo_index][3] = "sorcerer_ally"
    _write_save(path, payload)

    with pytest.raises(ValueError, match="active spell effect"):
        Encounter.load(path)


def test_focus_pool_rejects_capacity_or_remaining_value_outside_definition(
    tmp_path: Path,
) -> None:
    game = _first_cast_game()
    path = tmp_path / "invalid-focus-pool.json"
    game.save(path)
    payload = _read_save(path)
    actor = payload["state"]["creatures"]["angelic_sorcerer"]
    actor["focus_capacity"] = 0
    actor["focus_points"] = 1
    _write_save(path, payload)

    with pytest.raises(ValueError, match="focus pool"):
        Encounter.load(path)
