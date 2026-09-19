"""Independent public-play review of Tumble Through.

Rules checked 2026-09-16:

* Tumble Through: https://2e.aonprd.com/Actions.aspx?ID=2370
* Bravado: https://2e.aonprd.com/Traits.aspx?ID=801
* Reactive Strike: https://2e.aonprd.com/Feats.aspx?ID=5832
"""

from pathlib import Path

import pytest

import pf2e.content as content
from pf2e.encounter import Encounter
from pf2e.model import CreaturePlacement, EncounterSetup, Position, ResultStatus, Strike
from pf2e.skill_actions import TumbleThrough


SETUP_ID = "staged_braggart_swashbuckler_vs_guard_dog"


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


def _actor(game: Encounter, actor_id: str):
    return next(actor for actor in game.inspect().actors if actor.actor_id == actor_id)


def test_saved_tumble_then_dagger_is_a_complete_healthy_public_fight(
    tmp_path: Path,
) -> None:
    # Initiative, Tumble check, dagger check, weapon die, precision die.
    game = Encounter.start(content.get_setup(SETUP_ID), rolls=(20, 1, 12, 20, 2, 3))
    assert all(actor.hp == actor.max_hp for actor in game.inspect().actors)
    _settle_initiative(game)
    actions_before = _actor(game, "braggart").actions_remaining

    started = game.execute(TumbleThrough((Position(2, 1), Position(3, 1))))
    assert started.status is ResultStatus.PAUSED
    choice = started.inspection.choice
    assert choice is not None and choice.kind == "family_action"
    assert _actor(game, "braggart").actions_remaining == actions_before - 1
    assert _actor(game, "braggart").strikes_this_turn == 0

    path = tmp_path / "review-saved-tumble.json"
    game.save(path)
    restored = Encounter.load(path)
    assert restored.inspect().choice == choice
    crossed = _choose(restored, "keep")
    check = next(event.check for event in crossed.events if event.kind == "tumble_through_check")
    assert check is not None
    assert (check.die, check.modifier, check.dc) == (12, 8, 17)
    assert _actor(restored, "braggart").position == Position(3, 1)
    assert _actor(restored, "braggart").panache
    assert restored.effective_speed_ft("braggart") == 30
    assert _actor(restored, "braggart").strikes_this_turn == 0

    stale = restored.choose(choice.choice_id, "reroll", choice.owner_actor_id)
    assert stale.status is ResultStatus.REJECTED
    final = restored.execute(Strike("braggart_dog", attack_id="dagger"))
    assert final.status is ResultStatus.PAUSED
    final = _choose(restored, "keep")
    assert final.status is ResultStatus.COMPLETED
    assert final.inspection.winner_team == "blue"
    assert not final.inspection.in_progress


def test_failed_tumble_after_a_clear_lead_in_square_keeps_completed_movement(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The check occurs on entering the foe; failure ends movement at that point."""

    base = content.get_setup(SETUP_ID)
    setup = EncounterSetup(
        setup_id="review_tumble_lead_in_failure",
        name="Review Tumble Through lead-in movement",
        width=5,
        height=3,
        placements=(
            CreaturePlacement(
                "braggart",
                base.placements[0].definition_id,
                "Braggart Swashbuckler",
                "blue",
                Position(0, 1),
            ),
            CreaturePlacement(
                "braggart_dog",
                base.placements[1].definition_id,
                "Guard Dog",
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
    game = Encounter.start(setup, rolls=(20, 1, 4))
    _settle_initiative(game)

    result = game.execute(
        TumbleThrough((Position(1, 1), Position(2, 1), Position(3, 1)))
    )
    assert result.status is ResultStatus.PAUSED
    # The clear first square is traversed before the check to enter the dog's
    # occupied square, so it is already committed while the Hero choice waits.
    assert _actor(game, "braggart").position == Position(1, 1)
    result = _choose(game, "keep")
    assert any(event.kind == "tumble_through_failed" for event in result.events)
    assert _actor(game, "braggart").position == Position(1, 1)
    assert _actor(game, "braggart").panache
    assert _actor(game, "braggart").panache_expires_at_end == 2
