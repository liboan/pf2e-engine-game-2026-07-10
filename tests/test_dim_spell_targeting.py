"""Focused dim-light targeting checks for the admitted spell routes."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from types import MappingProxyType

import pytest

import pf2e.content as content
from pf2e import Cast, Encounter, ResultStatus
from pf2e.content import ANGELIC_FIRST_CAST_SETUP
from pf2e.model import EndTurn, Position, Strike


def _dim_setup(monkeypatch: pytest.MonkeyPatch, setup_id: str):
    setup = replace(
        ANGELIC_FIRST_CAST_SETUP,
        setup_id=setup_id,
        ambient_light="dim",
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
        result = game.choose(choice.choice_id, "keep", choice.owner_actor_id)
        assert result.status is ResultStatus.COMPLETED


def _actor(game: Encounter, actor_id: str):
    return next(actor for actor in game.inspect().actors if actor.actor_id == actor_id)


def test_divine_lance_saved_flat_reroll_then_saved_attack_choice(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    game = Encounter.start(
        _dim_setup(monkeypatch, "dim_divine_lance_saved"),
        rolls=(20, 1, 1, 4, 5, 10, 1, 1),
    )
    _settle_initiative(game)
    caster_state = game._state.creatures["angelic_sorcerer"]
    caster_state.hero_points = 2
    before_dice = game._dice._index

    flat = game.execute(Cast("divine_lance", target_id="sorcerer_dog"))
    assert flat.status is ResultStatus.PAUSED
    assert [event.kind for event in flat.events] == [
        "cast_started", "concealment_flat_check",
    ]
    assert flat.events[-1].check is not None and flat.events[-1].check.die == 4
    assert game._dice._index == before_dice + 1
    assert _actor(game, "angelic_sorcerer").actions_remaining == 1
    assert _actor(game, "angelic_sorcerer").strikes_this_turn == 1

    flat_path = tmp_path / "divine-lance-flat.json"
    game.save(flat_path)
    restored = Encounter.load(flat_path)
    assert restored.inspect() == flat.inspection

    rerolled_flat = restored.choose(
        restored.inspect().choice.choice_id,
        "spend_hero_point",
        restored.inspect().choice.owner_actor_id,
    )
    assert rerolled_flat.status is ResultStatus.PAUSED
    assert rerolled_flat.inspection.choice is not None
    assert rerolled_flat.inspection.choice.kind == "spell_attack_hero_reroll"
    assert [event.kind for event in rerolled_flat.events] == [
        "hero_reroll", "concealment_passed", "spell_attack",
    ]
    assert rerolled_flat.events[0].check is not None
    assert rerolled_flat.events[0].check.die == 5
    assert rerolled_flat.events[-1].check is not None
    assert rerolled_flat.events[-1].check.die == 10
    assert rerolled_flat.events[-1].check.attack_count == 1
    assert rerolled_flat.events[-1].check.map_penalty == 0
    assert not any(event.kind == "concealment_flat_check" for event in rerolled_flat.events)

    attack_path = tmp_path / "divine-lance-attack.json"
    restored.save(attack_path)
    attack_restored = Encounter.load(attack_path)
    result = attack_restored.choose(
        attack_restored.inspect().choice.choice_id,
        "keep",
        attack_restored.inspect().choice.owner_actor_id,
    )
    assert result.status is ResultStatus.COMPLETED
    assert [event.kind for event in result.events].count("spell_attack") == 1
    assert not any(event.kind == "concealment_flat_check" for event in result.events)


def test_targeted_heal_saved_concealment_failure_spends_slot_without_healing_die(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    game = Encounter.start(
        _dim_setup(monkeypatch, "dim_targeted_heal_saved"),
        rolls=(20, 1, 1, 4),
    )
    _settle_initiative(game)
    game._state.creatures["angelic_sorcerer"].hero_points = 1
    game._state.creatures["sorcerer_ally"].hp = 5

    started = game.execute(
        Cast("heal", "sorcerer_ally", actions=2, slot_id="angelic_rank1")
    )
    assert started.status is ResultStatus.PAUSED
    blood = started.inspection.choice
    assert blood is not None and blood.kind == "spell_blood_magic_recipient"
    assert _actor(game, "angelic_sorcerer").actions_remaining == 1
    assert _actor(game, "angelic_sorcerer").spontaneous_slots[0].remaining == 2

    flat = game.choose(blood.choice_id, "angelic_sorcerer", blood.owner_actor_id)
    assert flat.status is ResultStatus.PAUSED
    assert flat.inspection.choice is not None
    assert flat.inspection.choice.kind == "concealment_hero_reroll"
    assert flat.events[-1].check is not None and flat.events[-1].check.die == 4
    assert not any(event.kind == "heal_roll" for event in flat.events)

    path = tmp_path / "targeted-heal-flat.json"
    game.save(path)
    restored = Encounter.load(path)
    assert restored.inspect() == flat.inspection
    result = restored.choose(
        restored.inspect().choice.choice_id,
        "keep",
        restored.inspect().choice.owner_actor_id,
    )
    assert result.status is ResultStatus.COMPLETED
    assert any(event.kind == "concealment_failed" for event in result.events)
    assert not any(event.kind == "heal_roll" for event in result.events)
    assert _actor(restored, "sorcerer_ally").hp == 5
    assert _actor(restored, "angelic_sorcerer").actions_remaining == 1
    assert _actor(restored, "angelic_sorcerer").spontaneous_slots[0].remaining == 2


def test_self_heal_bypasses_dim_concealment_gate(monkeypatch: pytest.MonkeyPatch) -> None:
    game = Encounter.start(
        _dim_setup(monkeypatch, "dim_self_heal"),
        rolls=(20, 1, 1, 4),
    )
    _settle_initiative(game)
    game._state.creatures["angelic_sorcerer"].hp = 5

    started = game.execute(
        Cast("heal", "angelic_sorcerer", actions=1, slot_id="angelic_rank1")
    )
    blood = started.inspection.choice
    assert blood is not None and blood.kind == "spell_blood_magic_recipient"
    willingness = game.choose(
        blood.choice_id, "angelic_sorcerer", blood.owner_actor_id
    )
    assert willingness.status is ResultStatus.PAUSED
    assert willingness.inspection.choice is not None
    assert willingness.inspection.choice.kind == "spell_willingness"
    assert not any(event.kind == "concealment_flat_check" for event in willingness.events)


def test_fear_dim_flat_failure_keeps_costs_without_will_save(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    game = Encounter.start(
        _dim_setup(monkeypatch, "dim_fear_flat_failure"),
        rolls=(20, 1, 1, 4),
    )
    _settle_initiative(game)
    caster = game._state.creatures["angelic_sorcerer"]
    caster.hero_points = 1

    started = game.execute(Cast("fear", "sorcerer_dog", slot_id="angelic_rank1"))
    assert started.status is ResultStatus.PAUSED
    assert [event.kind for event in started.events] == [
        "cast_started", "concealment_flat_check",
    ]
    assert started.events[-1].check is not None and started.events[-1].check.die == 4
    assert _actor(game, "angelic_sorcerer").actions_remaining == 1
    assert _actor(game, "angelic_sorcerer").spontaneous_slots[0].remaining == 2
    assert game._dice._index == 4

    path = tmp_path / "fear-flat-failure.json"
    game.save(path)
    restored = Encounter.load(path)
    choice = restored.inspect().choice
    assert choice is not None and choice.kind == "concealment_hero_reroll"
    result = restored.choose(choice.choice_id, "keep", choice.owner_actor_id)
    assert result.status is ResultStatus.COMPLETED
    assert any(event.kind == "concealment_failed" for event in result.events)
    assert not any(event.kind == "spell_save" for event in result.events)
    assert not any(event.kind == "condition_applied" for event in result.events)
    assert _actor(restored, "angelic_sorcerer").actions_remaining == 1
    assert _actor(restored, "angelic_sorcerer").spontaneous_slots[0].remaining == 2


def test_void_warp_saved_flat_failure_has_no_fortitude_save_or_damage(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    game = Encounter.start(
        _dim_setup(monkeypatch, "dim_void_warp_flat_failure"),
        rolls=(20, 1, 1, 4),
    )
    _settle_initiative(game)
    game._state.creatures["angelic_sorcerer"].hero_points = 1
    before_hp = _actor(game, "sorcerer_dog").hp

    started = game.execute(Cast("void_warp", "sorcerer_dog"))
    assert started.status is ResultStatus.PAUSED
    assert started.inspection.choice is not None
    assert started.inspection.choice.kind == "concealment_hero_reroll"
    assert started.events[-1].check is not None and started.events[-1].check.die == 4
    assert _actor(game, "angelic_sorcerer").actions_remaining == 1
    assert game._dice._index == 4

    path = tmp_path / "void-warp-flat-failure.json"
    game.save(path)
    restored = Encounter.load(path)
    choice = restored.inspect().choice
    assert choice is not None
    result = restored.choose(choice.choice_id, "keep", choice.owner_actor_id)
    assert result.status is ResultStatus.COMPLETED
    assert any(event.kind == "concealment_failed" for event in result.events)
    assert not any(event.kind in {"spell_save", "damage", "effect_applied"} for event in result.events)
    assert _actor(restored, "sorcerer_dog").hp == before_hp


def test_guidance_flat_failure_does_not_consume_existing_caster_guidance(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    game = Encounter.start(
        _dim_setup(monkeypatch, "dim_guidance_flat_failure"),
        rolls=(20, 1, 1, 4),
    )
    _settle_initiative(game)
    self_cast = game.execute(Cast("guidance", "angelic_sorcerer"))
    assert self_cast.status is ResultStatus.COMPLETED
    assert any(effect.kind == "guidance" for effect in game._state.active_effects)
    game._state.creatures["angelic_sorcerer"].hero_points = 1

    started = game.execute(Cast("guidance", "sorcerer_ally"))
    assert started.status is ResultStatus.PAUSED
    flat = started.events[-1].check
    assert flat is not None and flat.die == 4 and flat.modifier == 0
    assert started.inspection.choice is not None
    assert started.inspection.choice.kind == "concealment_hero_reroll"

    path = tmp_path / "guidance-flat-failure.json"
    game.save(path)
    restored = Encounter.load(path)
    choice = restored.inspect().choice
    assert choice is not None
    result = restored.choose(choice.choice_id, "keep", choice.owner_actor_id)
    assert result.status is ResultStatus.COMPLETED
    assert any(event.kind == "concealment_failed" for event in result.events)
    assert not any(event.kind == "effect_applied" for event in result.events)
    assert any(
        effect.kind == "guidance" and effect.target_actor_id == "angelic_sorcerer"
        for effect in restored._state.active_effects
    )


def test_stabilize_saved_flat_success_uses_public_dying_target(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    target_definition = replace(
        content.WEAPON_IDENTITY_FIGHTER_M,
        definition_id="dim_stabilize_target",
        hp=6,
    )
    setup = replace(
        ANGELIC_FIRST_CAST_SETUP,
        setup_id="dim_stabilize_public_target",
        ambient_light="dim",
        placements=tuple(
            replace(
                placement,
                definition_id=(
                    target_definition.definition_id
                    if placement.actor_id == "sorcerer_ally"
                    else placement.definition_id
                ),
                position=Position(3, 2) if placement.actor_id == "sorcerer_dog" else placement.position,
            )
            for placement in ANGELIC_FIRST_CAST_SETUP.placements
        ),
    )
    monkeypatch.setattr(
        content,
        "CREATURES",
        MappingProxyType({**content.CREATURES, target_definition.definition_id: target_definition}),
    )
    monkeypatch.setattr(
        content,
        "_STAGED_SETUPS",
        MappingProxyType({**content._STAGED_SETUPS, setup.setup_id: setup}),
    )
    game = Encounter.start(setup, rolls=(1, 1, 20, 20, 4, 5))
    _settle_initiative(game)
    injury = game.execute(Strike("sorcerer_ally", attack_id="jaws"))
    assert injury.status is ResultStatus.PAUSED
    health_choice = injury.inspection.choice
    assert health_choice is not None and health_choice.kind == "heroic_recovery_damage"
    game.choose(health_choice.choice_id, "normal", health_choice.owner_actor_id)
    target = _actor(game, "sorcerer_ally")
    assert (target.hp, target.dying, target.unconscious, target.dead) == (0, 2, True, False)
    assert game.inspect().turn_actor_id == "sorcerer_dog"
    assert game.execute(EndTurn()).status is ResultStatus.COMPLETED
    assert game.inspect().turn_actor_id == "angelic_sorcerer"
    game._state.creatures["angelic_sorcerer"].hero_points = 1

    started = game.execute(Cast("stabilize", "sorcerer_ally"))
    assert started.status is ResultStatus.PAUSED
    assert started.inspection.choice is not None
    assert started.inspection.choice.kind == "concealment_hero_reroll"
    assert started.events[-1].check is not None and started.events[-1].check.die == 5

    path = tmp_path / "stabilize-flat-success.json"
    game.save(path)
    restored = Encounter.load(path)
    choice = restored.inspect().choice
    assert choice is not None
    result = restored.choose(choice.choice_id, "keep", choice.owner_actor_id)
    assert result.status is ResultStatus.COMPLETED
    assert any(event.kind == "stabilize" for event in result.events)
    assert not any(event.kind in {"spell_save", "concealment_failed"} for event in result.events)
    target = _actor(restored, "sorcerer_ally")
    assert (target.hp, target.dying, target.wounded, target.unconscious, target.dead) == (
        0, 0, 1, True, False,
    )
