"""Committed Runic Weapon refusal still follows the manipulate trigger path."""

from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path
from types import MappingProxyType

import pytest

import pf2e.content as content
from pf2e import Cast, Encounter, Position, ResultStatus
from pf2e.content import ANGELIC_FIRST_CAST_SETUP, GUARD_DOG


def _reactive_setup(monkeypatch: pytest.MonkeyPatch):
    reactive_dog = replace(
        GUARD_DOG,
        definition_id="runic_refusal_reactive_dog",
        abilities=("reactive_strike",),
        hp=30,
    )
    setup = replace(
        ANGELIC_FIRST_CAST_SETUP,
        setup_id="runic_refusal_reaction_setup",
        placements=tuple(
            replace(
                placement,
                definition_id=reactive_dog.definition_id,
                position=Position(1, 1),
            )
            if placement.actor_id == "sorcerer_dog"
            else placement
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
    return setup


def _settle_initiative(game: Encounter) -> None:
    while (choice := game.inspect().choice) is not None:
        assert choice.kind == "initiative_hero_reroll"
        game.choose(choice.choice_id, "keep", choice.owner_actor_id)


def _refused_runic_reaction(game: Encounter):
    _settle_initiative(game)
    offered = game.execute(
        Cast("runic_weapon", item_id="sorcerer_ally:longsword", slot_id="angelic_rank1")
    )
    assert offered.status is ResultStatus.PAUSED
    willingness = offered.inspection.choice
    assert willingness is not None and willingness.kind == "spell_willingness"
    refused = game.choose(willingness.choice_id, "unwilling", willingness.owner_actor_id)
    assert refused.status is ResultStatus.PAUSED
    reaction = refused.inspection.choice
    assert reaction is not None and reaction.kind == "reaction"
    assert reaction.owner_actor_id == "sorcerer_dog"
    return refused, reaction


def _caster(game: Encounter):
    return game._state.creatures["angelic_sorcerer"]


def test_options_project_runic_weapon_as_two_action_item_cast(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    setup = _reactive_setup(monkeypatch)
    game = Encounter.start(setup, rolls=(20, 1, 1))
    _settle_initiative(game)

    runic = next(spell for spell in game.options().spells if spell.spell_id == "runic_weapon")
    assert runic.action_costs == (2,)
    assert runic.unavailable_reason is None
    assert tuple(option.actions for option in runic.target_options) == (2,)
    assert runic.target_options[0].targets == ()


def test_refusal_declining_reaction_finishes_without_effect_or_extra_willingness(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    setup = _reactive_setup(monkeypatch)
    game = Encounter.start(setup, rolls=(20, 1, 1))
    _refused, reaction = _refused_runic_reaction(game)

    caster = _caster(game)
    assert caster.actions_remaining == 1
    assert caster.spontaneous_slots[0].remaining == 2
    path = tmp_path / "refused-runic-reaction.json"
    game.save(path)
    restored = Encounter.load(path)
    assert restored.inspect() == game.inspect()

    completed = restored.choose(reaction.choice_id, "decline", reaction.owner_actor_id)
    assert completed.status is ResultStatus.COMPLETED
    assert completed.inspection.choice is None
    assert not any(event.kind in {"item_effect_applied", "spell_willingness"} for event in completed.events)
    assert not restored._state.active_item_effects
    assert _caster(restored).actions_remaining == 1
    assert _caster(restored).spontaneous_slots[0].remaining == 2


def test_refusal_saved_reaction_accept_critical_disrupts_without_effect(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    setup = _reactive_setup(monkeypatch)
    # Three initiative checks, then a critical Reactive Strike and its d4.
    game = Encounter.start(setup, rolls=(20, 1, 1, 20, 1))
    _refused, reaction = _refused_runic_reaction(game)

    path = tmp_path / "refused-runic-critical-reaction.json"
    game.save(path)
    saved = json.loads(path.read_text(encoding="utf-8"))
    continuation = saved["state"]["pending_choice"]["continuation"]
    assert continuation["stage"] == "refused"
    assert continuation["reaction_trigger"] == "manipulate"
    assert continuation["spell_target_item_id"] == "sorcerer_ally:longsword"

    restored = Encounter.load(path)
    result = restored.choose(reaction.choice_id, "accept", reaction.owner_actor_id)
    assert result.status is ResultStatus.COMPLETED
    assert any(event.kind == "disrupted" for event in result.events)
    assert not any(event.kind in {"item_effect_applied", "spell_willingness"} for event in result.events)
    assert not restored._state.active_item_effects
    assert _caster(restored).actions_remaining == 1
    assert _caster(restored).spontaneous_slots[0].remaining == 2
