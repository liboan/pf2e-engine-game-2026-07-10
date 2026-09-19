"""Focused item-location concealment checks for Runic Weapon."""

from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path
from types import MappingProxyType

import pytest

import pf2e.content as content
from pf2e import Cast, Encounter, Position, ResultStatus
from pf2e.content import ANGELIC_FIRST_CAST_SETUP, GUARD_DOG


def _setup(monkeypatch: pytest.MonkeyPatch, setup_id: str, *, ambient_light: str = "dim", caster_definition_id: str | None = None):
    setup = replace(
        ANGELIC_FIRST_CAST_SETUP,
        setup_id=setup_id,
        ambient_light=ambient_light,
        placements=tuple(
            replace(placement, definition_id=caster_definition_id)
            if placement.actor_id == "angelic_sorcerer" and caster_definition_id is not None
            else placement
            for placement in ANGELIC_FIRST_CAST_SETUP.placements
        ),
    )
    monkeypatch.setattr(
        content,
        "_STAGED_SETUPS",
        MappingProxyType({**content._STAGED_SETUPS, setup.setup_id: setup}),
    )
    return setup


def _settle(game: Encounter) -> None:
    while (choice := game.inspect().choice) is not None:
        assert choice.kind == "initiative_hero_reroll"
        result = game.choose(choice.choice_id, "keep", choice.owner_actor_id)
        assert result.status is ResultStatus.COMPLETED


def _actor(game: Encounter, actor_id: str):
    return game._state.creatures[actor_id]


def _ground_item(game: Encounter) -> None:
    state = game._state
    ally = state.creatures["sorcerer_ally"]
    ally.held_items.remove("sorcerer_ally:longsword")
    state.ground_items.setdefault(ally.position, []).append("sorcerer_ally:longsword")


def test_dim_ground_runic_saved_flat_failure_has_costs_and_no_effect(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    game = Encounter.start(_setup(monkeypatch, "dim_runic_ground_failure"), rolls=(20, 1, 1, 4))
    _settle(game)
    _ground_item(game)
    caster = _actor(game, "angelic_sorcerer")
    caster.hero_points = 1

    started = game.execute(Cast("runic_weapon", item_id="sorcerer_ally:longsword", slot_id="angelic_rank1"))
    assert started.status is ResultStatus.PAUSED
    assert started.inspection.choice is not None
    assert started.inspection.choice.kind == "concealment_hero_reroll"
    assert game._state.pending_choice is not None
    assert game._state.pending_choice.target_id is None
    assert game._state.pending_choice.spell_target_item_id == "sorcerer_ally:longsword"
    assert [event.kind for event in started.events] == ["cast_started", "concealment_flat_check"]
    assert started.events[-1].check is not None and started.events[-1].check.die == 4
    assert game._state.creatures["angelic_sorcerer"].actions_remaining == 1
    assert game._state.creatures["angelic_sorcerer"].spontaneous_slots[0].remaining == 2

    path = tmp_path / "dim-runic-ground-failure.json"
    game.save(path)
    saved = json.loads(path.read_text(encoding="utf-8"))
    assert saved["state"]["pending_choice"]["target_id"] is None
    assert saved["state"]["pending_choice"]["spell_target_item_id"] == "sorcerer_ally:longsword"
    restored = Encounter.load(path)
    choice = restored.inspect().choice
    assert choice is not None and choice.kind == "concealment_hero_reroll"
    result = restored.choose(choice.choice_id, "keep", choice.owner_actor_id)
    assert result.status is ResultStatus.COMPLETED
    assert any(event.kind == "concealment_failed" for event in result.events)
    assert not any(event.kind == "item_effect_applied" for event in result.events)
    assert not restored._state.active_item_effects
    assert _actor(restored, "angelic_sorcerer").actions_remaining == 1
    assert _actor(restored, "angelic_sorcerer").spontaneous_slots[0].remaining == 2


def test_dim_ground_runic_saved_flat_pass_applies_once(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    game = Encounter.start(_setup(monkeypatch, "dim_runic_ground_pass"), rolls=(20, 1, 1, 5))
    _settle(game)
    _ground_item(game)
    _actor(game, "angelic_sorcerer").hero_points = 1
    started = game.execute(Cast("runic_weapon", item_id="sorcerer_ally:longsword", slot_id="angelic_rank1"))
    assert started.status is ResultStatus.PAUSED
    path = tmp_path / "dim-runic-ground-pass.json"
    game.save(path)
    restored = Encounter.load(path)
    choice = restored.inspect().choice
    assert choice is not None and choice.kind == "concealment_hero_reroll"
    result = restored.choose(choice.choice_id, "keep", choice.owner_actor_id)
    assert result.status is ResultStatus.COMPLETED
    assert [event.kind for event in result.events] == [
        "concealment_kept", "concealment_passed", "item_effect_applied",
    ]
    assert len(restored._state.active_item_effects) == 1
    assert restored._state.active_item_effects[0].item_id == "sorcerer_ally:longsword"


def test_dim_held_runic_willingness_precedes_saved_item_gate(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    game = Encounter.start(_setup(monkeypatch, "dim_runic_held"), rolls=(20, 1, 1, 4))
    _settle(game)
    _actor(game, "angelic_sorcerer").hero_points = 1
    offered = game.execute(Cast("runic_weapon", item_id="sorcerer_ally:longsword", slot_id="angelic_rank1"))
    assert offered.status is ResultStatus.PAUSED
    willingness = offered.inspection.choice
    assert willingness is not None and willingness.kind == "spell_willingness"
    path = tmp_path / "dim-runic-held-willingness.json"
    game.save(path)
    restored = Encounter.load(path)
    accepted = restored.choose(willingness.choice_id, "willing", willingness.owner_actor_id)
    assert accepted.status is ResultStatus.PAUSED
    assert accepted.inspection.choice is not None
    assert accepted.inspection.choice.kind == "concealment_hero_reroll"
    assert accepted.events[-1].check is not None and accepted.events[-1].check.die == 4
    assert _actor(restored, "angelic_sorcerer").actions_remaining == 1
    assert _actor(restored, "angelic_sorcerer").spontaneous_slots[0].remaining == 2


def test_dim_runic_refusal_has_no_flat_check_or_effect(monkeypatch: pytest.MonkeyPatch) -> None:
    game = Encounter.start(_setup(monkeypatch, "dim_runic_refusal"), rolls=(20, 1, 1))
    _settle(game)
    offered = game.execute(Cast("runic_weapon", item_id="sorcerer_ally:longsword", slot_id="angelic_rank1"))
    willingness = offered.inspection.choice
    assert willingness is not None and willingness.kind == "spell_willingness"
    result = game.choose(willingness.choice_id, "unwilling", willingness.owner_actor_id)
    assert result.status is ResultStatus.COMPLETED
    assert not any(event.kind in {"concealment_flat_check", "item_effect_applied"} for event in result.events)
    assert _actor(game, "angelic_sorcerer").actions_remaining == 1
    assert _actor(game, "angelic_sorcerer").spontaneous_slots[0].remaining == 2


def test_dim_runic_critical_manipulate_reaction_disrupts_before_flat_check(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    reactive_id = "dim_runic_reactive_dog"
    reactive_dog = replace(
        GUARD_DOG,
        definition_id=reactive_id,
        abilities=("reactive_strike",),
        hp=30,
    )
    monkeypatch.setattr(
        content,
        "_STAGED_CREATURES",
        MappingProxyType({**content._STAGED_CREATURES, reactive_id: reactive_dog}),
    )
    setup = _setup(monkeypatch, "dim_runic_disruption")
    setup = replace(
        setup,
        placements=tuple(
            replace(placement, definition_id=reactive_id, position=Position(1, 1))
            if placement.actor_id == "sorcerer_dog" else placement
            for placement in setup.placements
        ),
    )
    monkeypatch.setattr(
        content,
        "_STAGED_SETUPS",
        MappingProxyType({**content._STAGED_SETUPS, setup.setup_id: setup}),
    )
    game = Encounter.start(setup, rolls=(20, 1, 1, 20, 1))
    _settle(game)
    offered = game.execute(Cast("runic_weapon", item_id="sorcerer_ally:longsword", slot_id="angelic_rank1"))
    willingness = offered.inspection.choice
    assert willingness is not None and willingness.kind == "spell_willingness"
    accepted = game.choose(willingness.choice_id, "willing", willingness.owner_actor_id)
    reaction = accepted.inspection.choice
    assert reaction is not None and reaction.kind == "reaction"
    result = game.choose(reaction.choice_id, "accept", reaction.owner_actor_id)
    assert result.status is ResultStatus.COMPLETED
    assert any(event.kind == "disrupted" for event in result.events)
    assert not any(event.kind == "concealment_flat_check" for event in result.events)
    assert not any(event.kind == "item_effect_applied" for event in result.events)
    assert _actor(game, "angelic_sorcerer").spontaneous_slots[0].remaining == 2


def test_dim_low_light_caster_skips_runic_item_gate(monkeypatch: pytest.MonkeyPatch) -> None:
    low_light_id = "dim_runic_low_light_caster"
    low_light = replace(content.ANGELIC_SORCERER_STAGED, definition_id=low_light_id, vision="low_light")
    monkeypatch.setattr(
        content,
        "_STAGED_CREATURES",
        MappingProxyType({**content._STAGED_CREATURES, low_light_id: low_light}),
    )
    game = Encounter.start(
        _setup(monkeypatch, "dim_runic_low_light", caster_definition_id=low_light_id),
        rolls=(20, 1, 1),
    )
    _settle(game)
    offered = game.execute(Cast("runic_weapon", item_id="sorcerer_ally:longsword", slot_id="angelic_rank1"))
    willingness = offered.inspection.choice
    assert willingness is not None and willingness.kind == "spell_willingness"
    result = game.choose(willingness.choice_id, "willing", willingness.owner_actor_id)
    assert result.status is ResultStatus.COMPLETED
    assert not any(event.kind == "concealment_flat_check" for event in result.events)
    assert len(game._state.active_item_effects) == 1


def test_dim_self_held_runic_bypasses_item_gate(monkeypatch: pytest.MonkeyPatch) -> None:
    game = Encounter.start(_setup(monkeypatch, "dim_runic_self_held"), rolls=(20, 1, 1))
    _settle(game)
    state = game._state
    caster = state.creatures["angelic_sorcerer"]
    ally = state.creatures["sorcerer_ally"]
    ally.held_items.remove("sorcerer_ally:longsword")
    caster.held_items.append("sorcerer_ally:longsword")
    result = game.execute(Cast("runic_weapon", item_id="sorcerer_ally:longsword", slot_id="angelic_rank1"))
    assert result.status is ResultStatus.COMPLETED
    assert not any(event.kind == "concealment_flat_check" for event in result.events)
    assert len(game._state.active_item_effects) == 1


def test_dim_runic_tampered_item_stops_saved_gate_without_consuming_dice(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    game = Encounter.start(_setup(monkeypatch, "dim_runic_tamper"), rolls=(20, 1, 1, 4))
    _settle(game)
    _ground_item(game)
    _actor(game, "angelic_sorcerer").hero_points = 1
    started = game.execute(Cast("runic_weapon", item_id="sorcerer_ally:longsword", slot_id="angelic_rank1"))
    choice = started.inspection.choice
    assert choice is not None and choice.kind == "concealment_hero_reroll"
    state = game._state
    ally = state.creatures["sorcerer_ally"]
    state.ground_items[ally.position].remove("sorcerer_ally:longsword")
    ally.held_items.append("sorcerer_ally:longsword")
    before_index = game._dice._index
    stopped = game.choose(choice.choice_id, "keep", choice.owner_actor_id)
    assert stopped.status is ResultStatus.REJECTED
    assert "wielder" in stopped.message
    assert game._dice._index == before_index
    assert not game._state.active_item_effects
