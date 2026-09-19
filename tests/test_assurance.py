"""Source-informed Assurance(Athletics) checks through public actions.

The fixed result and exclusion of other modifiers come from Player Core's
Assurance feat: https://2e.aonprd.com/Feats.aspx?ID=5121. Proficiency bonuses
come from the Player Core proficiency rules:
https://2e.aonprd.com/Rules.aspx?ID=2281.
"""

from pathlib import Path

import pytest

from pf2e.checks import DegreeOfSuccess, resolve_assurance_check
from pf2e.content import S2_SETUP, get_setup
from pf2e.encounter import Encounter
from pf2e.model import EndTurn, Position, ResultStatus, Strike, Stride
from pf2e.skill_actions import Demoralize, Escape, Grapple, Trip


def _ready_pc_duel(rolls: tuple[int, ...], *, first_actor: str = "fighter_a") -> Encounter:
    game = Encounter.start(get_setup("s2_pc_duel_fixture"), rolls=rolls)
    while game.inspect().choice is not None:
        choice = game.inspect().choice
        assert choice is not None and choice.kind == "initiative_hero_reroll"
        game.choose(choice.choice_id, "keep", choice.owner_actor_id)
    assert game.inspect().turn_actor_id == first_actor
    return game


def _keep_hero_choice(game: Encounter, result):
    if result.status is ResultStatus.PAUSED:
        choice = result.inspection.choice
        assert choice is not None
        if {option.option_id for option in choice.options} == {"keep", "reroll"}:
            return game.choose(choice.choice_id, "keep", choice.owner_actor_id)
        assert {option.option_id for option in choice.options} == {"keep", "spend_hero_point"}
        return game.choose(choice.choice_id, "keep", choice.owner_actor_id)
    return result


def _actor(game: Encounter, actor_id: str):
    return next(actor for actor in game.inspect().actors if actor.actor_id == actor_id)


@pytest.mark.parametrize(
    ("dc", "degree"),
    [
        (23, DegreeOfSuccess.CRITICAL_FAILURE),
        (14, DegreeOfSuccess.FAILURE),
        (13, DegreeOfSuccess.SUCCESS),
        (3, DegreeOfSuccess.CRITICAL_SUCCESS),
    ],
)
def test_assurance_uses_fixed_result_without_a_fake_die_or_natural_adjustment(
    dc: int,
    degree: DegreeOfSuccess,
) -> None:
    result = resolve_assurance_check(3, dc, traits=("attack",))

    assert result.method == "assurance"
    assert result.die is None
    assert result.modifier == 3
    assert result.total == 13
    assert result.dc == dc
    assert result.degree is result.degree_before_adjustments is degree
    assert result.adjustments == ()
    assert result.map_penalty == 0
    assert result.traits == ("attack",)


def test_public_trip_assurance_ignores_map_and_spends_action_and_attack_count() -> None:
    # Initiatives, then one ordinary attack misses. There is deliberately no
    # second check die: Assurance must not draw one or offer a Hero Point reroll.
    game = _ready_pc_duel((20, 1, 1, 1))
    result = _keep_hero_choice(
        game,
        game.execute(Strike("fighter_b", attack_id="longsword")),
    )
    assert result.status is ResultStatus.COMPLETED
    assert _actor(game, "fighter_a").strikes_this_turn == 1
    assert _actor(game, "fighter_a").actions_remaining == 2
    hero_points_before = _actor(game, "fighter_a").hero_points

    result = game.execute(Trip("fighter_b", use_assurance=True))

    assert result.status is ResultStatus.COMPLETED
    event = next(event for event in result.events if event.kind == "trip_check")
    check = event.check
    assert check is not None
    assert check.method == "assurance" and check.die is None
    assert (check.modifier, check.total, check.dc) == (3, 13, 16)
    assert check.attack_count == 2
    assert check.map_penalty == 0
    assert check.adjustments == ()
    assert "Assurance (Athletics)" in event.text and "d20" not in event.text
    assert result.inspection.choice is None
    assert _actor(game, "fighter_a").strikes_this_turn == 2
    assert _actor(game, "fighter_a").actions_remaining == 1
    assert _actor(game, "fighter_a").hero_points == hero_points_before


def test_public_assurance_ignores_user_condition_but_uses_target_current_reflex_dc() -> None:
    # Fighter B acts first and Demoralizes A. On A's turn, A Demoralizes B,
    # then uses Assurance while frightened. The target's frightened value
    # still lowers its Reflex DC; A's frightened penalty does not lower 13.
    game = _ready_pc_duel((1, 20, 11, 20), first_actor="fighter_b")
    b_demoralize = _keep_hero_choice(game, game.execute(Demoralize("fighter_a")))
    assert b_demoralize.status is ResultStatus.COMPLETED
    assert game.execute(EndTurn()).status is ResultStatus.COMPLETED
    assert _actor(game, "fighter_a").condition_effects[0].kind == "frightened"
    assert _actor(game, "fighter_a").condition_effects[0].value == 1

    a_demoralize = _keep_hero_choice(game, game.execute(Demoralize("fighter_b")))
    assert a_demoralize.status is ResultStatus.COMPLETED
    assert _actor(game, "fighter_b").condition_effects[0].kind == "frightened"
    assert _actor(game, "fighter_b").condition_effects[0].value == 2

    assured = game.execute(Trip("fighter_b", use_assurance=True))

    assert assured.status is ResultStatus.COMPLETED
    check = next(event.check for event in assured.events if event.kind == "trip_check")
    assert check is not None and check.method == "assurance" and check.die is None
    assert (check.modifier, check.total, check.dc) == (3, 13, 14)
    assert check.attack_count == 1 and check.map_penalty == 0
    assert _actor(game, "fighter_a").actions_remaining == 1
    assert _actor(game, "fighter_a").strikes_this_turn == 1


def test_public_assurance_grapple_and_athletics_escape_do_not_roll(tmp_path: Path) -> None:
    # Assurance Grapple is the first maneuver after initiative, so no d20 is
    # available after the two initiative dice.
    game = _ready_pc_duel((20, 1))
    grapple = game.execute(Grapple("fighter_b", use_assurance=True))
    assert grapple.status is ResultStatus.COMPLETED
    grapple_check = next(event.check for event in grapple.events if event.kind == "grapple_check")
    assert grapple_check is not None and grapple_check.method == "assurance"
    assert grapple_check.die is None and grapple_check.total == 13
    assert grapple_check.degree is DegreeOfSuccess.FAILURE
    assert not any(event.kind == "condition_applied" for event in grapple.events)
    assert _actor(game, "fighter_a").strikes_this_turn == 1
    assert _actor(game, "fighter_a").actions_remaining == 2
    assert grapple.inspection.choice is None

    # Use an ordinary Grapple to create a real impediment, save/load the live
    # encounter, then use Assurance(Athletics) for Escape on the target's turn.
    game = _ready_pc_duel((20, 1, 20))
    ordinary = _keep_hero_choice(game, game.execute(Grapple("fighter_b")))
    assert ordinary.status is ResultStatus.COMPLETED
    game_path = tmp_path / "assurance-escape.json"
    game.save(game_path)
    game = Encounter.load(game_path)
    assert game.execute(EndTurn()).status is ResultStatus.COMPLETED

    before = game.inspect()
    invalid = game.execute(Escape("grapple:fighter_a:fighter_b", "acrobatics", use_assurance=True))
    assert invalid.status is ResultStatus.REJECTED
    assert game.inspect() == before

    escaped = game.execute(Escape("grapple:fighter_a:fighter_b", "athletics", use_assurance=True))
    assert escaped.status is ResultStatus.COMPLETED
    escape_check = next(event.check for event in escaped.events if event.kind == "escape_check")
    assert escape_check is not None and escape_check.method == "assurance"
    assert escape_check.die is None and escape_check.total == 13
    assert escape_check.dc == 17
    assert _actor(game, "fighter_b").strikes_this_turn == 1
    assert _actor(game, "fighter_b").actions_remaining == 2


def test_public_assurance_rejects_nonowner_without_changing_state() -> None:
    game = Encounter.start(S2_SETUP, rolls=(1, 1, 20, 1))
    while game.inspect().choice is not None:
        choice = game.inspect().choice
        assert choice is not None
        if choice.kind == "initiative_tie":
            game.choose(choice.choice_id, "fighter_a")
        else:
            assert choice.kind == "initiative_hero_reroll"
            game.choose(choice.choice_id, "keep", choice.owner_actor_id)
    assert game.inspect().turn_actor_id == "guard_dog_a"

    moved = game.execute(Stride((Position(4, 1), Position(3, 1), Position(2, 1))))
    assert moved.status is ResultStatus.COMPLETED
    before = game.inspect()

    rejected = game.execute(Trip("fighter_a", use_assurance=True))

    assert rejected.status is ResultStatus.REJECTED
    assert "does not have Assurance (Athletics)" in rejected.message
    assert game.inspect() == before
