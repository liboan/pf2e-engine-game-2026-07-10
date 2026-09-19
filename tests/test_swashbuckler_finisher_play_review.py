"""Independent public-play review of melee Confident Finisher.

Rules references:
- Confident Finisher: https://2e.aonprd.com/Actions.aspx?ID=2818
- Finisher trait: https://2e.aonprd.com/Traits.aspx?ID=802
- Swashbuckler and Precise Strike: https://2e.aonprd.com/Classes.aspx?ID=63
"""

from __future__ import annotations

from pathlib import Path

import pytest

import pf2e.content as content
from pf2e.encounter import Encounter
from pf2e.model import (
    Choose,
    CreaturePlacement,
    EncounterSetup,
    EndTurn,
    Position,
    ResultStatus,
    Strike,
)
from pf2e.skill_actions import Demoralize, Trip
from pf2e.swashbuckler import ConfidentFinisher
from pf2e.typed_defense_content import WAYSTONE_SENTINEL


SETUP_ID = "staged_braggart_swashbuckler_vs_guard_dog"


def _actor(game: Encounter, actor_id: str):
    return next(actor for actor in game.inspect().actors if actor.actor_id == actor_id)


def _choose(game: Encounter, option_id: str):
    choice = game.inspect().choice
    assert choice is not None
    return game.execute(Choose(choice.choice_id, option_id, choice.owner_actor_id))


def _start(setup: EncounterSetup, *rolls: int) -> Encounter:
    game = Encounter.start(setup, rolls=rolls)
    if game.inspect().choice is not None:
        assert _choose(game, "keep").status is ResultStatus.COMPLETED
    return game


def _gain_panache(game: Encounter, target_id: str) -> None:
    started = game.execute(Demoralize(target_id, use_intimidating_glare=True))
    assert started.status is ResultStatus.PAUSED
    resolved = _choose(game, "keep")
    assert resolved.status is ResultStatus.COMPLETED
    assert _actor(game, "braggart").panache


def test_healthy_second_attack_critical_finisher_saves_choice_and_voluntarily_uses_failure_effect(
    tmp_path: Path,
) -> None:
    # Initiatives; Demoralize; ordinary Strike and d4; second-attack Finisher,
    # then its d4 and 2d6. The natural 20 promotes the MAP attack to a critical
    # success, but the player deliberately selects the failure effect.
    game = _start(content.get_setup(SETUP_ID), 20, 1, 8, 8, 1, 20, 2, 3, 4)
    assert all(actor.hp == actor.max_hp for actor in game.inspect().actors)
    _gain_panache(game, "braggart_dog")

    first = game.execute(Strike("braggart_dog", attack_id="dagger"))
    assert first.status is ResultStatus.PAUSED
    first = _choose(game, "keep")
    first_check = next(event.check for event in first.events if event.kind == "strike")
    assert first_check is not None and first_check.modifier == 7
    assert _actor(game, "braggart_dog").hp == 3

    finisher = game.execute(ConfidentFinisher("braggart_dog", attack_id="dagger"))
    assert finisher.status is ResultStatus.PAUSED
    assert game.inspect().choice is not None
    assert game.inspect().choice.kind == "attack_hero_reroll"
    finisher = _choose(game, "keep")
    check = next(event.check for event in finisher.events if event.kind == "strike")
    assert check is not None
    assert (check.die, check.modifier, check.total, check.dc, check.degree.name) == (
        20,
        3,
        23,
        14,
        "CRITICAL_SUCCESS",
    )
    assert any(
        "multiple attack" in modifier.source.casefold() and modifier.amount == -4
        for modifier in check.modifier_breakdown
    )
    choice = game.inspect().choice
    assert choice is not None and choice.kind == "family_action"
    assert [option.option_id for option in choice.options] == ["full_damage", "failure_effect"]
    braggart = _actor(game, "braggart")
    assert not braggart.panache
    assert braggart.finisher_used_this_turn
    assert (braggart.actions_remaining, braggart.strikes_this_turn) == (0, 2)

    pending_path = tmp_path / "review-confident-finisher-choice.json"
    game.save(pending_path)
    game = Encounter.load(pending_path)
    saved_choice = game.inspect().choice
    assert saved_choice == choice

    before = game.inspect()
    dice_before = game._dice.to_data()
    invalid = game.execute(Choose(saved_choice.choice_id, "forged", "braggart"))
    assert invalid.status is ResultStatus.REJECTED
    assert game.inspect() == before
    assert game._dice.to_data() == dice_before

    resolved = game.execute(Choose(saved_choice.choice_id, "failure_effect", "braggart"))
    failure = next(
        event for event in resolved.events if event.kind == "confident_finisher_failure_effect"
    )
    assert failure.damage is not None
    assert failure.damage.total == 3
    assert len(failure.damage.components) == 1
    assert failure.damage.components[0].damage_type == "piercing"
    assert failure.damage.components[0].rolls == (3, 4)
    assert resolved.status is ResultStatus.COMPLETED
    assert not resolved.inspection.in_progress
    assert resolved.inspection.winner_team == "blue"

    final = game.inspect()
    dice_after = game._dice.to_data()
    stale = game.execute(Choose(saved_choice.choice_id, "full_damage", "braggart"))
    assert stale.status is ResultStatus.REJECTED
    assert game.inspect() == final
    assert game._dice.to_data() == dice_after


def test_failure_damage_is_typed_and_resisted_then_attack_trait_lockout_resets(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    setup = EncounterSetup(
        setup_id="review_confident_finisher_resistance",
        name="Review Confident Finisher resistance",
        width=5,
        height=3,
        placements=(
            CreaturePlacement(
                "braggart",
                content.get_definition("swashbuckler_braggart_level_1").definition_id,
                "Braggart Swashbuckler",
                "blue",
                Position(1, 1),
            ),
            CreaturePlacement(
                "waystone",
                WAYSTONE_SENTINEL.definition_id,
                "Waystone Sentinel",
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
    # Initiatives; Demoralize; failed Finisher and 2d6; next-turn Trip.
    game = _start(setup, 20, 1, 8, 7, 5, 4, 20, 1)
    _gain_panache(game, "waystone")
    result = game.execute(ConfidentFinisher("waystone", attack_id="dagger"))
    assert result.status is ResultStatus.PAUSED
    result = _choose(game, "keep")
    raw_failure = next(
        event for event in result.events if event.kind == "confident_finisher_failure"
    )
    assert raw_failure.damage is not None
    assert raw_failure.damage.total == 4
    assert raw_failure.damage.components[0].damage_type == "piercing"
    applied = next(event for event in result.events if event.kind == "damage")
    assert applied.damage is not None and applied.damage.total == 2
    assert _actor(game, "waystone").hp == 28
    braggart = _actor(game, "braggart")
    assert (braggart.actions_remaining, braggart.strikes_this_turn) == (1, 1)
    assert braggart.finisher_used_this_turn and not braggart.panache

    before = game.inspect()
    dice_before = game._dice.to_data()
    blocked = game.execute(Trip("waystone"))
    assert blocked.status is ResultStatus.REJECTED
    assert "finisher_attack_lockout" in blocked.message
    assert game.inspect() == before
    assert game._dice.to_data() == dice_before

    assert game.execute(EndTurn()).status is ResultStatus.COMPLETED
    assert game.execute(EndTurn()).status is ResultStatus.COMPLETED
    assert game.inspect().turn_actor_id == "braggart"
    assert not _actor(game, "braggart").finisher_used_this_turn
    trip = game.execute(Trip("waystone"))
    assert trip.status is ResultStatus.PAUSED
    trip = _choose(game, "keep")
    assert any(event.kind == "trip_check" for event in trip.events)


def test_critical_failure_consumes_panache_but_deals_no_failure_damage() -> None:
    game = _start(content.get_setup(SETUP_ID), 20, 1, 8, 1)
    _gain_panache(game, "braggart_dog")
    result = game.execute(ConfidentFinisher("braggart_dog", attack_id="dagger"))
    assert result.status is ResultStatus.PAUSED
    result = _choose(game, "keep")
    check = next(event.check for event in result.events if event.kind == "strike")
    assert check is not None and check.degree.name == "CRITICAL_FAILURE"
    assert any(event.kind == "confident_finisher_critical_failure" for event in result.events)
    assert not any(event.damage is not None for event in result.events)
    assert _actor(game, "braggart_dog").hp == 8
    braggart = _actor(game, "braggart")
    assert not braggart.panache and braggart.finisher_used_this_turn
    assert (braggart.actions_remaining, braggart.strikes_this_turn) == (1, 1)
