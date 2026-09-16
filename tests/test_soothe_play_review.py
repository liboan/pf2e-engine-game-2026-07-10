"""Independent public-play review of the shared rank-1 Soothe spell.

Rules reference: https://2e.aonprd.com/Spells.aspx?ID=1678
"""

from __future__ import annotations

from pathlib import Path

import pytest

import pf2e.content as content
from pf2e.encounter import Encounter
from pf2e.model import Cast, CreaturePlacement, EncounterSetup, EndTurn, Position, ResultStatus, Strike


def _actor(game: Encounter, actor_id: str):
    return next(actor for actor in game.inspect().actors if actor.actor_id == actor_id)


def _choose(game: Encounter, option_id: str):
    choice = game.inspect().choice
    assert choice is not None
    return game.choose(choice.choice_id, option_id, choice.owner_actor_id)


def _settle_initiative(game: Encounter) -> None:
    for _ in range(8):
        choice = game.inspect().choice
        if choice is None:
            return
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
    raise AssertionError("initiative did not settle within eight choices")


def _cross_caster_setup(monkeypatch: pytest.MonkeyPatch, setup_id: str) -> EncounterSetup:
    setup = EncounterSetup(
        setup_id=setup_id,
        name="Review Soothe against live spell saves",
        width=5,
        height=3,
        placements=(
            CreaturePlacement(
                "soothe_caster",
                content.SOOTHE_TEST_CASTER.definition_id,
                "Soothe Caster",
                "blue",
                Position(1, 1),
            ),
            CreaturePlacement(
                "angelic_opponent",
                content.ANGELIC_SORCERER_STAGED.definition_id,
                "Angelic Opponent",
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


def _accept_soothe(game: Encounter) -> None:
    cast = game.execute(Cast("soothe", "soothe_caster", 2, "soothe_1"))
    assert cast.status is ResultStatus.PAUSED
    assert cast.inspection.choice is not None
    assert cast.inspection.choice.kind == "spell_willingness"
    accepted = _choose(game, "willing")
    assert accepted.status is ResultStatus.COMPLETED
    assert any(event.kind == "healing" for event in accepted.events)
    assert any(event.kind == "soothe_protection_applied" for event in accepted.events)


def test_injury_soothe_round_trip_then_actual_guided_mental_save_and_victory(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    setup = _cross_caster_setup(monkeypatch, "review_soothe_mental_save_victory")
    # Initiatives; enemy fist/damage; Soothe; Fear save; final longsword/damage.
    game = Encounter.start(setup, rolls=(10, 20, 13, 4, 4, 7, 20, 8))
    assert all(actor.hp == actor.max_hp for actor in game.inspect().actors)
    _settle_initiative(game)
    assert game.inspect().turn_actor_id == "angelic_opponent"

    strike = game.execute(Strike("soothe_caster", attack_id="fist"))
    if strike.status is ResultStatus.PAUSED:
        strike = _choose(game, "keep")
    assert strike.status is ResultStatus.COMPLETED
    injured_hp = _actor(game, "soothe_caster").hp
    assert injured_hp < _actor(game, "soothe_caster").max_hp
    assert game.execute(EndTurn()).status is ResultStatus.COMPLETED
    assert game.inspect().turn_actor_id == "soothe_caster"

    _accept_soothe(game)
    healed = _actor(game, "soothe_caster")
    assert healed.hp == min(healed.max_hp, injured_hp + 8)
    slot = next(slot for slot in healed.prepared_slots if slot.slot_id == "soothe_1")
    assert slot.spent
    effect = next(effect for effect in game._state.active_effects if effect.kind == "soothe")
    assert (effect.value, effect.source_actor_id, effect.target_actor_id) == (
        2,
        "soothe_caster",
        "soothe_caster",
    )

    active_path = tmp_path / "review-soothe-active.json"
    game.save(active_path)
    game = Encounter.load(active_path)
    assert next(
        effect for effect in game._state.active_effects if effect.kind == "soothe"
    ) == effect
    assert next(
        slot for slot in game._state.creatures["soothe_caster"].prepared_slots
        if slot.slot_id == "soothe_1"
    ).spent

    assert game.execute(EndTurn()).status is ResultStatus.COMPLETED
    assert game.inspect().turn_actor_id == "angelic_opponent"
    assert game.execute(Cast("guidance", "soothe_caster")).status is ResultStatus.COMPLETED
    fear = game.execute(Cast("fear", "soothe_caster", slot_id="angelic_rank1"))
    assert fear.status is ResultStatus.PAUSED
    assert fear.inspection.choice is not None
    assert fear.inspection.choice.kind == "guidance_use"
    guided = _choose(game, "use")
    assert guided.status is ResultStatus.PAUSED
    assert guided.inspection.choice is not None
    assert guided.inspection.choice.kind == "spell_save_hero_reroll"
    fear_path = tmp_path / "review-soothe-fear-save.json"
    game.save(fear_path)
    game = Encounter.load(fear_path)
    resolved = _choose(game, "keep")
    fear_check = next(event.check for event in resolved.events if event.kind == "spell_save")
    assert fear_check is not None
    base_will = dict(
        (name, modifier)
        for name, _rank, modifier in content.SOOTHE_TEST_CASTER.saves
    )["will"]
    assert fear_check.modifier == base_will + 2
    assert {
        (modifier.source, modifier.amount, modifier.modifier_type)
        for modifier in fear_check.modifier_breakdown
        if modifier.source in {"Soothe", "Guidance"}
    } == {("Soothe", 2, "status"), ("Guidance", 1, "status")}
    assert not any(
        effect.kind == "guidance" and effect.target_actor_id == "soothe_caster"
        for effect in game._state.active_effects
    )
    assert any(effect.kind == "soothe" for effect in game._state.active_effects)
    assert next(
        slot for slot in game._state.creatures["angelic_opponent"].spontaneous_slots
        if slot.slot_id == "angelic_rank1"
    ).remaining == 2

    assert game.inspect().turn_actor_id == "soothe_caster"
    final = game.execute(Strike("angelic_opponent", attack_id="longsword"))
    assert final.status is ResultStatus.PAUSED
    final = _choose(game, "keep")
    assert final.status is ResultStatus.COMPLETED
    assert not final.inspection.in_progress
    assert final.inspection.winner_team == "blue"


def test_nonmental_save_gets_no_soothe_bonus_spent_slot_is_atomic_and_effect_expires(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    setup = _cross_caster_setup(monkeypatch, "review_soothe_nonmental_expiry")
    # Initiatives; Soothe; Void Warp Fortitude save.
    game = Encounter.start(setup, rolls=(20, 1, 4, 20, 1, 1))
    _settle_initiative(game)
    assert game.inspect().turn_actor_id == "soothe_caster"
    _accept_soothe(game)
    effect = next(effect for effect in game._state.active_effects if effect.kind == "soothe")
    assert effect.expires_at_source_start == 11
    assert effect.expires_at_world_time == 60
    assert game.execute(EndTurn()).status is ResultStatus.COMPLETED

    void_warp = game.execute(Cast("void_warp", "soothe_caster"))
    assert void_warp.status is ResultStatus.PAUSED
    void_warp = _choose(game, "keep")
    save_events = [event for event in void_warp.events if event.kind == "spell_save"]
    assert save_events, (void_warp, game.inspect().choice)
    fortitude = save_events[0].check
    assert fortitude is not None
    assert not any(modifier.source == "Soothe" for modifier in fortitude.modifier_breakdown)
    assert any(effect.kind == "soothe" for effect in game._state.active_effects)
    assert game.execute(EndTurn()).status is ResultStatus.COMPLETED
    assert game.inspect().turn_actor_id == "soothe_caster"

    before = game.inspect()
    dice_before = game._dice.to_data()
    rejected = game.execute(Cast("soothe", "soothe_caster", 2, "soothe_1"))
    assert rejected.status is ResultStatus.REJECTED
    assert game.inspect() == before
    assert game._dice.to_data() == dice_before

    # The effect lasts through source-start count 10 and expires at count 11,
    # exactly 60 encounter seconds after the cast.
    for _ in range(24):
        if game._state.actor_start_counts["soothe_caster"] == 10:
            break
        assert game.execute(EndTurn()).status is ResultStatus.COMPLETED
    else:
        raise AssertionError("Soothe source did not reach start count 10")
    assert any(effect.kind == "soothe" for effect in game._state.active_effects)
    for _ in range(2):
        assert game.execute(EndTurn()).status is ResultStatus.COMPLETED
    assert game._state.actor_start_counts["soothe_caster"] == 11
    assert game._state.world_time_seconds == 60
    assert not any(effect.kind == "soothe" for effect in game._state.active_effects)
