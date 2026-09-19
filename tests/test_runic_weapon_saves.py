"""Saved Runic Weapon continuations and strict item-effect persistence."""

from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path
from types import MappingProxyType

import pytest

import pf2e.content as content
from pf2e.content import ANGELIC_FIRST_CAST_SETUP, GUARD_DOG
from pf2e.encounter import Encounter
from pf2e.model import Cast, EndTurn, Position, ResultStatus, Strike, Stride
from pf2e.persistence import load_encounter


def _finish_start_choices(game: Encounter) -> None:
    while (choice := game.inspect().choice) is not None:
        option_id = (
            "keep"
            if any(option.option_id == "keep" for option in choice.options)
            else choice.options[0].option_id
        )
        result = game.choose(choice.choice_id, option_id, choice.owner_actor_id)
        assert result.status is ResultStatus.COMPLETED


def _runic_pending(*, rolls: tuple[int, ...] = (20, 1, 1, 20, 4, 7)) -> Encounter:
    game = Encounter.start(ANGELIC_FIRST_CAST_SETUP, rolls=rolls)
    _finish_start_choices(game)
    offered = game.execute(
        Cast("runic_weapon", item_id="sorcerer_ally:longsword", slot_id="angelic_rank1")
    )
    assert offered.status is ResultStatus.PAUSED
    choice = offered.inspection.choice
    assert choice is not None and choice.kind == "spell_willingness"
    return game


def _read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _write(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_runic_willingness_and_active_effect_round_trip_then_enhances_strike(
    tmp_path: Path,
) -> None:
    game = _runic_pending()
    caster = game._state.creatures["angelic_sorcerer"]
    assert caster.actions_remaining == 1
    assert caster.spontaneous_slots[0].remaining == 2

    pending_path = tmp_path / "runic-pending-willingness.json"
    game.save(pending_path)
    restored = Encounter.load(pending_path)
    assert restored.inspect() == game.inspect()
    pending = restored.inspect().choice
    assert pending is not None
    pending_data = _read(pending_path)["state"]["pending_choice"]
    assert pending_data["spell_target_item_id"] == "sorcerer_ally:longsword"

    accepted = restored.choose(pending.choice_id, "willing", pending.owner_actor_id)
    assert accepted.status is ResultStatus.COMPLETED
    # Willingness is a decision after the cast commitment.  It must not spend
    # another action or slot when the saved continuation resumes.
    caster = restored._state.creatures["angelic_sorcerer"]
    assert caster.actions_remaining == 1
    assert caster.spontaneous_slots[0].remaining == 2
    effects = restored._state.active_item_effects
    assert len(effects) == 1
    assert effects[0].item_id == "sorcerer_ally:longsword"

    active_path = tmp_path / "runic-active-effect.json"
    restored.save(active_path)
    resumed = Encounter.load(active_path)
    assert resumed._state.active_item_effects == effects
    assert resumed._state.creatures["angelic_sorcerer"].spontaneous_slots[0].remaining == 2

    assert resumed.execute(EndTurn()).status is ResultStatus.COMPLETED
    assert resumed.execute(Stride((Position(4, 2), Position(3, 2)))).status is ResultStatus.COMPLETED
    assert resumed.execute(EndTurn()).status is ResultStatus.COMPLETED
    strike = resumed.execute(Strike("sorcerer_dog", attack_id="longsword"))
    assert strike.status is ResultStatus.PAUSED
    choice = strike.inspection.choice
    assert choice is not None and choice.kind == "attack_hero_reroll"
    check = strike.events[0].check
    assert check is not None and check.modifier == 10
    completed = resumed.choose(choice.choice_id, "keep", choice.owner_actor_id)
    assert completed.status is ResultStatus.COMPLETED
    damage = next(event.damage for event in completed.events if event.damage is not None)
    assert damage is not None
    assert damage.total == 30
    assert damage.components[0].dice == (8, 8)


@pytest.mark.parametrize("mutation", ("caster", "item", "kind", "deadline", "duplicate", "shape"))
def test_runic_active_effect_save_rejects_adversarial_rows(tmp_path: Path, mutation: str) -> None:
    game = _runic_pending()
    pending = game.inspect().choice
    assert pending is not None
    accepted = game.choose(pending.choice_id, "willing", pending.owner_actor_id)
    assert accepted.status is ResultStatus.COMPLETED
    path = tmp_path / f"runic-forged-{mutation}.json"
    game.save(path)
    payload = _read(path)
    effects = payload["state"]["active_item_effects"]
    if mutation == "caster":
        effects[0][2] = "missing-caster"
    elif mutation == "item":
        effects[0][3] = "missing-item"
    elif mutation == "kind":
        effects[0][1] = "guidance"
    elif mutation == "deadline":
        effects[0][4] = 12
    elif mutation == "duplicate":
        effects.append(list(effects[0]))
    else:
        effects[0].append(True)
    _write(path, payload)

    with pytest.raises(ValueError, match="Runic Weapon|active item spell effects"):
        Encounter.load(path)


def test_runic_active_effect_save_rejects_a_caster_definition_without_runic_weapon(
    tmp_path: Path,
) -> None:
    game = _runic_pending()
    pending = game.inspect().choice
    assert pending is not None
    assert game.choose(pending.choice_id, "willing", pending.owner_actor_id).status is ResultStatus.COMPLETED
    path = tmp_path / "runic-forged-definition.json"
    game.save(path)
    payload = _read(path)
    payload["state"]["creatures"]["angelic_sorcerer"]["definition_id"] = "fighter_m_level_1"
    _write(path, payload)
    with pytest.raises(ValueError, match="definition|Runic Weapon|active item"):
        Encounter.load(path)


def test_runic_willingness_save_rejects_a_forged_item_before_direct_state_load(
    tmp_path: Path,
) -> None:
    game = _runic_pending()
    path = tmp_path / "runic-forged-pending-item.json"
    game.save(path)
    payload = _read(path)
    payload["state"]["pending_choice"]["spell_target_item_id"] = "missing-item"
    _write(path, payload)
    with pytest.raises(ValueError, match="Runic Weapon|item"):
        load_encounter(path)


def test_saved_runic_critical_manipulate_reaction_keeps_cost_and_no_effect(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    # The regular first-cast room has no hostile Reactive Strike.  Add a
    # test-only staged dog definition and room entry so this remains a public
    # command probe without changing the delivered content catalog.
    reactive_dog = replace(
        GUARD_DOG,
        definition_id="runic_reactive_dog",
        abilities=("reactive_strike",),
        hp=30,
    )
    setup = replace(
        ANGELIC_FIRST_CAST_SETUP,
        setup_id="runic_reaction_save_setup",
        name="Runic Weapon saved reaction setup",
        placements=tuple(
            replace(placement, definition_id=reactive_dog.definition_id, position=Position(1, 1))
            if placement.actor_id == "sorcerer_dog" else placement
            for placement in ANGELIC_FIRST_CAST_SETUP.placements
        ),
    )
    monkeypatch.setattr(
        content,
        "_STAGED_CREATURES",
        MappingProxyType({**content._STAGED_CREATURES, reactive_dog.definition_id: reactive_dog}),
    )
    monkeypatch.setattr(
        content,
        "_STAGED_SETUPS",
        MappingProxyType({**content._STAGED_SETUPS, setup.setup_id: setup}),
    )

    game = Encounter.start(setup, rolls=(20, 1, 1, 20, 1))
    _finish_start_choices(game)
    offered = game.execute(
        Cast("runic_weapon", item_id="sorcerer_ally:longsword", slot_id="angelic_rank1")
    )
    assert offered.status is ResultStatus.PAUSED
    willingness = offered.inspection.choice
    assert willingness is not None and willingness.kind == "spell_willingness"
    assert game.choose(willingness.choice_id, "willing", willingness.owner_actor_id).status is ResultStatus.PAUSED
    reaction = game.inspect().choice
    assert reaction is not None and reaction.kind == "reaction"

    path = tmp_path / "runic-pending-critical-reaction.json"
    game.save(path)
    resumed = Encounter.load(path)
    reaction = resumed.inspect().choice
    assert reaction is not None and reaction.kind == "reaction"
    result = resumed.choose(reaction.choice_id, "accept", reaction.owner_actor_id)
    assert result.status is ResultStatus.COMPLETED
    assert any(event.kind == "disrupted" for event in result.events)
    assert not resumed._state.active_item_effects
    caster = resumed._state.creatures["angelic_sorcerer"]
    assert caster.actions_remaining == 1
    assert caster.spontaneous_slots[0].remaining == 2
