"""Focused runtime checks for Angelic Halo and its focus/Blood Magic path."""

from __future__ import annotations

from pf2e.content import ANGELIC_FIRST_CAST_SETUP
from pf2e.encounter import Encounter
from pf2e.model import Cast, EndTurn, Position, ResultStatus


def _first_cast_game(*, rolls: tuple[int, ...] = (20, 1, 1, 4)) -> Encounter:
    game = Encounter.start(ANGELIC_FIRST_CAST_SETUP, rolls=rolls)
    while game.inspect().choice is not None:
        choice = game.inspect().choice
        assert choice is not None
        option_id = (
            "keep"
            if any(option.option_id == "keep" for option in choice.options)
            else choice.options[0].option_id
        )
        result = game.choose(choice.choice_id, option_id, choice.owner_actor_id)
        assert result.status is ResultStatus.COMPLETED
    assert game.inspect().turn_actor_id == "angelic_sorcerer"
    return game


def _cast_halo(game: Encounter, recipient: str) -> None:
    offered = game.execute(Cast("angelic_halo"))
    assert offered.status is ResultStatus.PAUSED
    choice = offered.inspection.choice
    assert choice is not None and choice.kind == "spell_blood_magic_recipient"
    assert {option.option_id for option in choice.options} == {
        "angelic_sorcerer",
        "sorcerer_ally",
    }
    completed = game.choose(choice.choice_id, recipient, choice.owner_actor_id)
    assert completed.status is ResultStatus.COMPLETED


def _cast_two_action_heal(game: Encounter, target_id: str, *, blood_recipient: str) -> tuple:
    offered = game.execute(Cast("heal", target_id, actions=2))
    assert offered.status is ResultStatus.PAUSED
    blood = offered.inspection.choice
    assert blood is not None and blood.kind == "spell_blood_magic_recipient"
    willingness_result = game.choose(blood.choice_id, blood_recipient, blood.owner_actor_id)
    willingness = willingness_result.inspection.choice
    assert willingness is not None and willingness.kind == "spell_willingness"
    completed = game.choose(willingness.choice_id, "willing", willingness.owner_actor_id)
    assert completed.status is ResultStatus.COMPLETED
    return completed.events


def _return_to_sorcerer(game: Encounter) -> None:
    if game.inspect().turn_actor_id == "angelic_sorcerer":
        actor = game._state.creatures["angelic_sorcerer"]
        if actor.actions_remaining < 3:
            result = game.execute(EndTurn())
            assert result.status is ResultStatus.COMPLETED
    while game.inspect().turn_actor_id != "angelic_sorcerer":
        result = game.execute(EndTurn())
        assert result.status is ResultStatus.COMPLETED


def test_halo_prompts_for_ally_or_caster_and_spends_focus_once() -> None:
    game = _first_cast_game()
    offered = game.execute(Cast("angelic_halo"))

    assert offered.status is ResultStatus.PAUSED
    assert game._state.creatures["angelic_sorcerer"].focus_points == 0
    assert game._state.creatures["angelic_sorcerer"].actions_remaining == 2
    assert not any(effect.kind == "angelic_halo" for effect in game._state.active_effects)

    choice = offered.inspection.choice
    assert choice is not None
    completed = game.choose(choice.choice_id, "sorcerer_ally", choice.owner_actor_id)
    assert completed.status is ResultStatus.COMPLETED
    assert any(event.kind == "blood_magic_applied" for event in completed.events)
    assert any(event.kind == "angelic_halo_applied" for event in completed.events)
    assert {
        (effect.kind, effect.target_actor_id, effect.value)
        for effect in game._state.active_effects
    } == {
        ("blood_magic", "sorcerer_ally", 1),
        ("angelic_halo", "angelic_sorcerer", 2),
    }

    before = game.inspect()
    rejected = game.execute(Cast("angelic_halo"))
    assert rejected.status is ResultStatus.REJECTED
    assert "focus point" in rejected.message
    assert game.inspect() == before


def test_halo_rejects_target_and_self_inclusion_arguments_atomically() -> None:
    game = _first_cast_game()
    before = game.inspect()
    before_dice = game._dice._index

    rejected = game.execute(Cast("angelic_halo", "sorcerer_ally"))
    assert rejected.status is ResultStatus.REJECTED
    assert "does not take a target" in rejected.message
    rejected = game.execute(Cast("angelic_halo", include_self=True))
    assert rejected.status is ResultStatus.REJECTED
    assert "include_self" in rejected.message
    assert game.inspect() == before
    assert game._dice._index == before_dice


def test_halo_auto_selects_caster_when_no_ally_is_inside_fifteen_feet() -> None:
    game = _first_cast_game()
    game._state.creatures["sorcerer_ally"].position = Position(4, 4)

    completed = game.execute(Cast("angelic_halo"))

    assert completed.status is ResultStatus.COMPLETED
    assert completed.inspection.choice is None
    blood = next(effect for effect in game._state.active_effects if effect.kind == "blood_magic")
    assert blood.target_actor_id == "angelic_sorcerer"
    assert any(event.kind == "angelic_halo_applied" for event in completed.events)


def test_halo_uses_fifteen_foot_grid_boundary() -> None:
    game = _first_cast_game()
    origin = Position(1, 2)

    assert game._in_angelic_halo_emanation(origin, Position(4, 3))
    assert not game._in_angelic_halo_emanation(origin, Position(4, 4))


def test_halo_bonus_uses_source_position_at_heal_resolution_and_excludes_self() -> None:
    game = _first_cast_game(rolls=(20, 1, 1, 4, 4, 4))
    _cast_halo(game, "angelic_sorcerer")

    game._state.creatures["sorcerer_ally"].hp = 5
    first_events = _cast_two_action_heal(
        game, "sorcerer_ally", blood_recipient="angelic_sorcerer"
    )
    healing = next(event for event in first_events if event.kind == "healing")
    assert "+ Angelic Halo 2 status" in healing.text
    assert game._state.creatures["sorcerer_ally"].hp == 19

    # The aura follows its source. Move the source 20 feet away before the
    # next Heal resolves; the slot Heal retains Potency (+1) only.
    _return_to_sorcerer(game)
    game._state.creatures["sorcerer_ally"].position = Position(4, 4)
    game._state.creatures["sorcerer_ally"].hp = 5
    second_events = _cast_two_action_heal(
        game, "sorcerer_ally", blood_recipient="angelic_sorcerer"
    )
    healing = next(event for event in second_events if event.kind == "healing")
    assert "+ Sorcerous Potency 1 status" in healing.text
    assert "Angelic Halo" not in healing.text
    assert game._state.creatures["sorcerer_ally"].hp == 18

    # The aura caster is not their own ally, even when their Heal targets
    # themself; the slotted Heal still receives Potency (+1).
    _return_to_sorcerer(game)
    game._state.creatures["angelic_sorcerer"].hp = 5
    self_events = _cast_two_action_heal(
        game, "angelic_sorcerer", blood_recipient="angelic_sorcerer"
    )
    healing = next(event for event in self_events if event.kind == "healing")
    assert "+ Sorcerous Potency 1 status" in healing.text
    assert "Angelic Halo" not in healing.text
    assert game._state.creatures["angelic_sorcerer"].hp == 16


def test_halo_save_load_preserves_pending_blood_magic_choice(tmp_path) -> None:
    game = _first_cast_game()
    offered = game.execute(Cast("angelic_halo"))
    path = tmp_path / "angelic-halo.json"
    game.save(path)

    restored = Encounter.load(path)
    assert restored.inspect() == offered.inspection
    choice = restored.inspect().choice
    assert choice is not None
    completed = restored.choose(choice.choice_id, "sorcerer_ally", choice.owner_actor_id)
    assert completed.status is ResultStatus.COMPLETED
    assert restored._state.creatures["angelic_sorcerer"].focus_points == 0
