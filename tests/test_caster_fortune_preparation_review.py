"""Independent public-play review of Sure Strike and daily preparation.

Rules references:
- Sure Strike: https://2e.aonprd.com/Spells.aspx?ID=1709
- Fortune: https://2e.aonprd.com/Traits.aspx?ID=612
- Assurance: https://2e.aonprd.com/Feats.aspx?ID=5121
- Daily preparation: https://2e.aonprd.com/Rules.aspx?ID=2575
"""

from __future__ import annotations

from pathlib import Path

import pytest

import pf2e.content as content
from pf2e import Cast, Encounter, ResultStatus, Strike
from pf2e.model import CreaturePlacement, EncounterSetup, Position
from pf2e.skill_actions import Trip


def _actor(game: Encounter, actor_id: str):
    return next(actor for actor in game.inspect().actors if actor.actor_id == actor_id)


def _choose(game: Encounter, option_id: str):
    choice = game.inspect().choice
    assert choice is not None
    return game.choose(choice.choice_id, option_id, choice.owner_actor_id)


def _settle_initiative(game: Encounter) -> None:
    while (choice := game.inspect().choice) is not None:
        assert choice.kind in {"initiative_hero_reroll", "initiative_tie"}
        option_id = (
            "keep"
            if any(option.option_id == "keep" for option in choice.options)
            else choice.options[0].option_id
        )
        assert game.choose(choice.choice_id, option_id, choice.owner_actor_id).status in {
            ResultStatus.PAUSED,
            ResultStatus.COMPLETED,
        }


def _next_sure_strike_setup(monkeypatch: pytest.MonkeyPatch) -> EncounterSetup:
    """A second authored scene for the same real Warpriest build."""
    setup = EncounterSetup(
        setup_id="review_sure_strike_second_scene",
        name="Review Sure Strike second scene",
        width=5,
        height=3,
        ambient_light="dim",
        placements=(
            CreaturePlacement(
                "cleric_c",
                content.WARPRIEST_C_SURE_STRIKE.definition_id,
                "Warpriest C",
                "blue",
                Position(1, 1),
            ),
            CreaturePlacement(
                "review_dog_b",
                content.GUARD_DOG.definition_id,
                "Guard Dog B",
                "red",
                Position(2, 1),
            ),
        ),
    )
    monkeypatch.setattr(
        content,
        "_STAGED_SETUPS",
        content._STAGED_SETUPS | {setup.setup_id: setup},
    )
    return setup


def _sure_strike_nimble_setup(monkeypatch: pytest.MonkeyPatch) -> EncounterSetup:
    """A legal-definition diagnostic fixture, not a newly admitted class."""
    setup = EncounterSetup(
        setup_id="review_sure_strike_nimble",
        name="Review Sure Strike, Reactive Strike, and Nimble Dodge",
        width=4,
        height=4,
        placements=(
            CreaturePlacement(
                "cleric_c",
                content.WARPRIEST_C_SURE_STRIKE.definition_id,
                "Warpriest C",
                "blue",
                Position(1, 1),
            ),
            CreaturePlacement(
                "fighter_m",
                content.MELEE_FIGHTER_M.definition_id,
                "Fighter M",
                "red",
                Position(2, 1),
            ),
            CreaturePlacement(
                "thief_rogue",
                content.ROGUE_THIEF_PLAYABLE.definition_id,
                "Thief Rogue",
                "red",
                Position(1, 2),
            ),
        ),
    )
    monkeypatch.setattr(
        content,
        "_STAGED_SETUPS",
        content._STAGED_SETUPS | {setup.setup_id: setup},
    )
    return setup


def test_sure_strike_survives_assurance_then_preparation_restores_it_for_next_fight(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Two healthy-start fights cover fortune, MAP, recovery, and scene carry."""
    # Scene A initiative; failed concealed Trip targeting; Sure Strike faces
    # and damage; then scene B initiative, Sure Strike faces, and damage.
    game = Encounter.start(
        content.SURE_STRIKE_WARPRIEST_SETUP,
        rolls=(20, 1, 4, 1, 20, 4, 20, 1, 1, 20, 4),
    )
    assert all(actor.hp == actor.max_hp for actor in game.inspect().actors)
    _settle_initiative(game)

    cast = game.execute(Cast("sure_strike", slot_id="ordinary_sure_strike_1"))
    assert cast.status is ResultStatus.COMPLETED
    assert _actor(game, "cleric_c").actions_remaining == 2
    assert next(
        slot for slot in _actor(game, "cleric_c").prepared_slots
        if slot.slot_id == "ordinary_sure_strike_1"
    ).spent

    # Assurance fixes the Athletics result, but targeting in dim light still
    # rolls. This skill maneuver commits MAP once and leaves fortune armed.
    trip = game.execute(Trip("guard_dog", use_assurance=True))
    assert trip.status is ResultStatus.PAUSED
    assert trip.inspection.choice is not None
    assert trip.inspection.choice.kind == "concealment_hero_reroll"
    pending = game._state.pending_choice
    assert pending is not None and pending.saved_check is not None
    assert pending.saved_check.result is not None
    assert pending.saved_check.result.method == "assurance"
    assert pending.saved_check.result.die is None
    assert any(effect.kind == "sure_strike" for effect in game._state.active_effects)
    assert "cleric_c" not in game._state.sure_strike_immunity_deadlines

    path = tmp_path / "sure-strike-assurance-target.json"
    game.save(path)
    game = Encounter.load(path)
    assert _choose(game, "keep").status is ResultStatus.COMPLETED
    assert _actor(game, "cleric_c").strikes_this_turn == 1
    assert any(effect.kind == "sure_strike" for effect in game._state.active_effects)

    victory = game.execute(Strike("guard_dog", attack_id="longsword"))
    assert victory.status is ResultStatus.COMPLETED
    check = next(event.check for event in victory.events if event.check is not None)
    assert check is not None
    assert (check.dice, check.die) == ((1, 20), 20)
    assert (check.attack_count, check.map_penalty, check.modifier) == (2, -5, 1)
    assert not any(event.kind == "concealment_flat_check" for event in victory.events)
    assert not any(event.kind == "attack_hero_reroll" for event in victory.events)
    assert not game.inspect().in_progress and game.inspect().winner_team == "blue"
    assert _actor(game, "cleric_c").sure_strike_immune_until_seconds == 600

    before_prepare = _actor(game, "cleric_c")
    preserved = (
        before_prepare.hp,
        before_prepare.wounded,
        before_prepare.held_items,
        before_prepare.worn_items,
        before_prepare.stowed_items,
        before_prepare.ammunition,
    )
    assert game.record_rested(("cleric_c",), day_number=2, elapsed_seconds=1).status is ResultStatus.COMPLETED

    # Invalid grouping is atomic, including the deterministic dice cursor.
    inspection_before = game.inspect()
    dice_before = game._dice.to_data()
    assert game.daily_prepare(("cleric_c", "cleric_c")).status is ResultStatus.REJECTED
    assert game.inspect() == inspection_before
    assert game._dice.to_data() == dice_before

    prepared = game.daily_prepare(("cleric_c",))
    assert prepared.status is ResultStatus.COMPLETED
    assert game.inspect().world_time_seconds == 3601
    cleric = _actor(game, "cleric_c")
    assert (
        cleric.hp,
        cleric.wounded,
        cleric.held_items,
        cleric.worn_items,
        cleric.stowed_items,
        cleric.ammunition,
    ) == preserved
    assert cleric.sure_strike_immune_until_seconds is None
    assert not next(
        slot for slot in cleric.prepared_slots
        if slot.slot_id == "ordinary_sure_strike_1"
    ).spent
    repeat_before = game.inspect()
    repeat_dice = game._dice.to_data()
    assert game.daily_prepare(("cleric_c",)).status is ResultStatus.REJECTED
    assert game.inspect() == repeat_before and game._dice.to_data() == repeat_dice

    transitioned = game.next_encounter(_next_sure_strike_setup(monkeypatch))
    assert transitioned.status in {ResultStatus.PAUSED, ResultStatus.COMPLETED}
    _settle_initiative(game)
    assert game.inspect().world_time_seconds == 3601
    assert game.execute(Cast("sure_strike", slot_id="ordinary_sure_strike_1")).status is ResultStatus.COMPLETED
    second_victory = game.execute(Strike("review_dog_b", attack_id="longsword"))
    assert second_victory.status is ResultStatus.COMPLETED
    second_check = next(event.check for event in second_victory.events if event.check is not None)
    assert second_check is not None and second_check.dice == (1, 20)
    assert not game.inspect().in_progress and game.inspect().winner_team == "blue"


def test_sure_strike_cast_does_not_trigger_reaction_and_saved_nimble_keeps_ac(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    setup = _sure_strike_nimble_setup(monkeypatch)
    game = Encounter.start(setup, rolls=(20, 2, 1, 1, 20, 8, 10))
    assert all(actor.hp == actor.max_hp for actor in game.inspect().actors)
    _settle_initiative(game)

    cast = game.execute(Cast("sure_strike", slot_id="ordinary_sure_strike_1"))
    assert cast.status is ResultStatus.COMPLETED
    assert cast.inspection.choice is None
    assert _actor(game, "cleric_c").actions_remaining == 2
    assert _actor(game, "fighter_m").reaction_available

    attack = game.execute(Strike("thief_rogue", attack_id="longsword", nonlethal=True))
    assert attack.status is ResultStatus.PAUSED
    nimble = attack.inspection.choice
    assert nimble is not None and nimble.kind == "nimble_dodge"
    path = tmp_path / "sure-strike-nimble.json"
    game.save(path)
    restored = Encounter.load(path)
    assert restored.inspect() == attack.inspection

    resolved = restored.choose(nimble.choice_id, "use", nimble.owner_actor_id)
    assert resolved.status is ResultStatus.COMPLETED
    check = next(event.check for event in resolved.events if event.check is not None)
    assert check is not None
    assert (check.dice, check.die, check.dc) == ((1, 20), 20, 20)
    assert not any(event.kind == "attack_hero_reroll" for event in resolved.events)
    assert _actor(restored, "thief_rogue").reaction_available is False
    assert _actor(restored, "fighter_m").reaction_available is True
    assert _actor(restored, "cleric_c").actions_remaining == 1
    assert not any(effect.kind == "sure_strike" for effect in restored._state.active_effects)

    # Fortune is gone after that attack. A second, explicitly nonlethal Strike
    # again applies its circumstance penalty while keeping second-attack MAP.
    ordinary = restored.execute(
        Strike("fighter_m", attack_id="longsword", nonlethal=True)
    )
    assert ordinary.status is ResultStatus.PAUSED
    assert ordinary.inspection.choice is not None
    assert ordinary.inspection.choice.kind == "attack_hero_reroll"
    ordinary_check = next(
        event.check for event in ordinary.events if event.check is not None
    )
    assert ordinary_check is not None
    assert ordinary_check.dice == (10,)
    assert (ordinary_check.attack_count, ordinary_check.map_penalty) == (2, -5)
    assert any(
        modifier.modifier_type == "circumstance"
        and modifier.source == "nonlethal intent"
        and modifier.amount == -2
        for modifier in ordinary_check.modifier_breakdown
    )
