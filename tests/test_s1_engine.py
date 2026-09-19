from __future__ import annotations

import json
from pathlib import Path

import pytest

from pf2e.checks import DegreeOfSuccess, multiple_attack_penalty, resolve_check
from pf2e.content import S1_SETUP
from pf2e.damage import DamagePacket, resolve_damage
from pf2e.encounter import Encounter
from pf2e.model import EndTurn, Position, ResultStatus, Step, Strike, Stride
from pf2e.space import diagonal_step_cost, grid_distance_feet, step_cost


@pytest.mark.parametrize(
    ("die", "modifier", "total", "degree"),
    [
        (2, 8, 10, DegreeOfSuccess.CRITICAL_FAILURE),
        (2, 9, 11, DegreeOfSuccess.FAILURE),
        (2, 17, 19, DegreeOfSuccess.FAILURE),
        (2, 18, 20, DegreeOfSuccess.SUCCESS),
        (2, 27, 29, DegreeOfSuccess.SUCCESS),
        (2, 28, 30, DegreeOfSuccess.CRITICAL_SUCCESS),
    ],
)
def test_degree_boundaries_at_dc_20(die, modifier, total, degree) -> None:
    result = resolve_check(die, modifier, 20)
    assert result.total == total
    assert result.degree_before_adjustments is degree
    assert result.degree is degree


def test_natural_roll_adjustments_apply_after_numbers_and_are_clamped() -> None:
    high_dc = resolve_check(20, 0, 40)
    high_modifier = resolve_check(1, 29, 20)
    natural_20_clamped = resolve_check(20, 30, 20)
    natural_1_clamped = resolve_check(1, 0, 20)

    assert high_dc.degree_before_adjustments is DegreeOfSuccess.CRITICAL_FAILURE
    assert high_dc.degree is DegreeOfSuccess.FAILURE
    assert high_modifier.degree_before_adjustments is DegreeOfSuccess.CRITICAL_SUCCESS
    assert high_modifier.degree is DegreeOfSuccess.SUCCESS
    assert natural_20_clamped.degree is DegreeOfSuccess.CRITICAL_SUCCESS
    assert natural_1_clamped.degree is DegreeOfSuccess.CRITICAL_FAILURE
    assert high_dc.adjustments[0].reason == "natural 20"
    assert high_modifier.adjustments[0].amount == -1


def test_map_uses_the_current_attacks_trait_and_misses_still_count() -> None:
    assert [multiple_attack_penalty(index) for index in range(5)] == [0, -5, -10, -10, -10]
    assert [multiple_attack_penalty(index, {"agile"}) for index in range(4)] == [0, -4, -8, -8]


def test_grid_diagonals_alternate_across_steps_and_reach_uses_fresh_distance() -> None:
    start = Position(0, 0)
    one_diagonal = Position(1, 1)
    two_diagonals = Position(2, 2)
    assert step_cost(start, one_diagonal, 0) == (5, 1)
    assert step_cost(one_diagonal, two_diagonals, 1) == (10, 1)
    assert sum(diagonal_step_cost(index) for index in range(4)) == 30
    assert grid_distance_feet(start, one_diagonal) == 5
    assert grid_distance_feet(start, two_diagonals) == 15


def test_critical_damage_doubles_the_rolled_die_plus_modifier() -> None:
    calls: list[int] = []

    def roll(sides: int) -> int:
        calls.append(sides)
        return 4

    result = resolve_damage(
        DamagePacket("fixture", "bludgeoning", dice_sides=4, dice_count=1, modifier=3),
        roll,
        critical=True,
    )
    assert calls == [4]
    assert result.rolled_total == 7
    assert result.multiplier == 2
    assert result.total == 14
    assert result.components[0].rolls == (4,)
    assert result.components[0].amount == 14


def test_fixture_has_ranked_perception_initiative_and_queries_are_pure(tmp_path: Path) -> None:
    game = Encounter.start(setup=S1_SETUP, rolls=(10, 10))
    before = game.inspect()
    before_file = tmp_path / "before.json"
    after_file = tmp_path / "after.json"
    game.save(before_file)

    options = game.options()
    after = game.inspect()
    game.save(after_file)

    assert (before.map_width, before.map_height) == (7, 5)
    assert [actor.actor_id for actor in before.actors] == ["synthetic_a", "synthetic_b"]
    assert [actor.label for actor in before.actors] == ["Synthetic NPC A", "Synthetic NPC B"]
    assert [actor.initiative for actor in before.actors] == [13, 13]
    assert before.turn_actor_id == "synthetic_a"  # NPC–NPC tie: documented setup order.
    assert options.actor_id == "synthetic_a"
    assert options.actions_remaining == 3
    assert options.can_stride and not options.can_strike
    assert after == before
    assert before_file.read_bytes() == after_file.read_bytes()


def test_first_diagonal_carries_to_later_movement_and_step_rejects_second_diagonal() -> None:
    game = Encounter.start(rolls=(15, 10))
    first = game.execute(Step(Position(2, 1)))
    assert first.status is ResultStatus.COMPLETED
    assert first.inspection.actors[0].diagonals_this_turn == 1

    before = game.inspect()
    second_step = game.execute(Step(Position(3, 0)))
    assert second_step.status is ResultStatus.REJECTED
    assert "cost 10 feet" in second_step.message
    assert second_step.inspection == before

    third = game.execute(Stride((Position(3, 1), Position(4, 0))))
    assert third.status is ResultStatus.COMPLETED
    # The orthogonal move does not reset the earlier diagonal; the next one
    # therefore costs 10 feet, even though it is in a later movement action.
    assert third.inspection.actors[0].diagonals_this_turn == 2
    ended = game.execute(EndTurn())
    actor_a = next(actor for actor in ended.inspection.actors if actor.actor_id == "synthetic_a")
    assert actor_a.diagonals_this_turn == 0


def test_three_actions_spend_and_refresh_attack_counts_after_misses() -> None:
    # A moves into reach, then misses with its first two Strikes. B then spends
    # its turn missing three times; the next round gives A three fresh actions.
    game = Encounter.start(rolls=(15, 10, 1, 1, 1, 1, 1))
    assert game.execute(Stride((Position(2, 2), Position(3, 2), Position(4, 2)))).status is ResultStatus.COMPLETED
    assert game.execute(Strike("synthetic_b")).events[0].check.map_penalty == 0
    second_a = game.execute(Strike("synthetic_b"))
    assert second_a.events[0].check.map_penalty == -5
    assert second_a.inspection.turn_actor_id == "synthetic_b"
    assert next(actor for actor in second_a.inspection.actors if actor.actor_id == "synthetic_b").actions_remaining == 3

    first_b = game.execute(Strike("synthetic_a"))
    assert first_b.events[0].check.map_penalty == 0
    assert game.execute(Strike("synthetic_a")).events[0].check.map_penalty == -5
    third_b = game.execute(Strike("synthetic_a"))
    assert third_b.events[0].check.map_penalty == -10
    assert third_b.inspection.round_number == 2
    assert third_b.inspection.turn_actor_id == "synthetic_a"
    actor_a = next(actor for actor in third_b.inspection.actors if actor.actor_id == "synthetic_a")
    assert actor_a.actions_remaining == 3
    assert actor_a.strikes_this_turn == 0
    assert actor_a.diagonals_this_turn == 0


def test_rejected_commands_preserve_state_and_supplied_roll_position(tmp_path: Path) -> None:
    game = Encounter.start(rolls=(15, 10, 20))
    assert game.execute(Stride((Position(2, 2), Position(3, 2), Position(4, 2)))).status is ResultStatus.COMPLETED
    before = tmp_path / "before.json"
    after = tmp_path / "after.json"
    game.save(before)

    exhausted = game.execute(Strike("synthetic_b"))
    game.save(after)
    assert exhausted.status is ResultStatus.REJECTED
    assert "exhausted" in exhausted.message
    assert "d6" in exhausted.message
    assert before.read_bytes() == after.read_bytes()

    out_of_range_game = Encounter.start(rolls=(15, 10, 21, 6))
    out_of_range_game.execute(Stride((Position(2, 2), Position(3, 2), Position(4, 2))))
    invalid_before = tmp_path / "invalid-before.json"
    invalid_after = tmp_path / "invalid-after.json"
    out_of_range_game.save(invalid_before)
    invalid = out_of_range_game.execute(Strike("synthetic_b"))
    out_of_range_game.save(invalid_after)
    assert invalid.status is ResultStatus.REJECTED
    assert "d20 requires a face from 1 through 20" in invalid.message
    assert invalid_before.read_bytes() == invalid_after.read_bytes()


def _approach_path(game: Encounter) -> tuple[Position, ...]:
    view = game.inspect()
    actor = next(item for item in view.actors if item.actor_id == view.turn_actor_id)
    target = next(item for item in view.actors if item.team != actor.team)
    x, y = actor.position.x, actor.position.y
    path: list[Position] = []
    while grid_distance_feet(Position(x, y), target.position) > 5:
        if x != target.position.x:
            x += 1 if target.position.x > x else -1
        elif y != target.position.y:
            y += 1 if target.position.y > y else -1
        path.append(Position(x, y))
    return tuple(path)


def _play_both_sides(game: Encounter) -> int:
    """Drive real public commands for both actors until one is defeated."""
    commands = 0
    while game.inspect().in_progress:
        options = game.options()
        actor = next(item for item in game.inspect().actors if item.actor_id == options.actor_id)
        if options.strike_targets:
            result = game.execute(Strike(options.strike_targets[0]))
        elif options.can_stride:
            result = game.execute(Stride(_approach_path(game)))
        else:
            result = game.execute(EndTurn())
        assert result.status is ResultStatus.COMPLETED, result.message
        commands += 1
        assert commands < 200, f"fight did not finish; actor={actor.actor_id}"
    return commands


def test_seeded_continuous_fight_finishes_through_public_commands() -> None:
    game = Encounter.start(setup=S1_SETUP, seed=47)
    commands = _play_both_sides(game)
    finished = game.inspect()
    assert commands >= 2
    assert not finished.in_progress
    assert finished.winner_team in {"blue", "red"}
    assert sum(actor.defeated for actor in finished.actors) == 1


def test_complete_alternate_path_and_save_restore_match_uninterrupted_run(tmp_path: Path) -> None:
    sequence = (15, 10, 20, 6)
    uninterrupted = Encounter.start(setup=S1_SETUP, rolls=sequence)
    restored = Encounter.start(setup=S1_SETUP, rolls=sequence)

    # This alternate route includes two diagonals in one Stride; at 20 feet it
    # reaches the same legal melee position as the straight route.
    alternate_path = (Position(2, 1), Position(3, 1), Position(4, 2))
    full_stride = uninterrupted.execute(Stride(alternate_path))
    save_stride = restored.execute(Stride(alternate_path))
    assert full_stride.inspection == save_stride.inspection
    assert save_stride.inspection.actors[0].diagonals_this_turn == 2

    save_path = tmp_path / "between-move-and-finishing-strike.json"
    restored.save(save_path)
    loaded = Encounter.load(save_path)
    assert loaded.inspect() == restored.inspect()

    expected = uninterrupted.execute(Strike("synthetic_b"))
    actual = loaded.execute(Strike("synthetic_b"))
    assert actual.status is ResultStatus.COMPLETED
    assert actual.events == expected.events
    assert actual.inspection == expected.inspection
    assert actual.inspection.in_progress is False
    assert actual.inspection.winner_team == "blue"
    target = next(actor for actor in actual.inspection.actors if actor.actor_id == "synthetic_b")
    assert target.hp == 0 and target.defeated
    assert actual.events[0].check is not None
    assert actual.events[0].check.attack_count == 1
    damage_event = next(event for event in actual.events if event.damage is not None)
    assert damage_event.damage.components[0].rolls == (6,)
    assert damage_event.damage.rolled_total == 8
    assert damage_event.damage.total == 16
    assert "critical doubles to 16" in damage_event.text


def test_saved_seeded_random_state_replays_the_same_critical_continuation(tmp_path: Path) -> None:
    original = Encounter.start(seed=2026)
    parallel = Encounter.start(seed=2026)
    for game in (original, parallel):
        active = game.inspect().turn_actor_id
        if active == "synthetic_a":
            path = (Position(2, 2), Position(3, 2), Position(4, 2))
        else:
            path = (Position(4, 2), Position(3, 2), Position(2, 2))
        assert game.execute(Stride(path)).status is ResultStatus.COMPLETED

    save_path = tmp_path / "seeded-random.json"
    parallel.save(save_path)
    loaded = Encounter.load(save_path)
    while original.inspect().in_progress:
        options = original.options()
        if options.strike_targets:
            command = Strike(options.strike_targets[0])
        elif options.can_stride:
            command = Stride(_approach_path(original))
        else:
            command = EndTurn()
        assert original.execute(command).status is ResultStatus.COMPLETED
        loaded_result = loaded.execute(command)
        assert loaded_result.status is ResultStatus.COMPLETED
    assert loaded.inspect() == original.inspect()


def test_save_is_json_and_preserves_sequence_cursor_and_counters(tmp_path: Path) -> None:
    game = Encounter.start(rolls=(15, 10, 1, 2, 3))
    assert game.execute(Step(Position(2, 1))).status is ResultStatus.COMPLETED
    save_path = tmp_path / "state.json"
    game.save(save_path)
    data = json.loads(save_path.read_text(encoding="utf-8"))
    assert data["dice"]["kind"] == "sequence"
    assert data["dice"]["index"] == 2
    assert data["dice"]["rolls"] == [15, 10, 1, 2, 3]
    assert data["state"]["creatures"]["synthetic_a"]["diagonals_this_turn"] == 1
    loaded = Encounter.load(save_path)
    assert loaded.inspect() == game.inspect()


def test_unknown_commands_and_attacks_are_reported_without_mutating_state(tmp_path: Path) -> None:
    game = Encounter.start(rolls=(15, 10, 20, 6))
    before = tmp_path / "before.json"
    after = tmp_path / "after.json"
    game.save(before)
    unsupported_command = game.execute(object())  # type: ignore[arg-type]
    game.save(after)
    assert unsupported_command.status is ResultStatus.UNSUPPORTED
    assert before.read_bytes() == after.read_bytes()

    unsupported_attack = game.execute(Strike("synthetic_b", attack_id="not_in_catalog"))
    assert unsupported_attack.status is ResultStatus.UNSUPPORTED
    assert "not supported in S1" in unsupported_attack.message


@pytest.mark.parametrize(
    "corruption",
    [
        "same_team",
        "defeated_but_in_progress",
        "inactive_actor_has_actions",
        "inactive_actor_has_attacks",
        "inactive_actor_has_diagonals",
        "reversed_initiative",
        "initiative_out_of_range",
        "winner_does_not_match_survivors",
        "sequence_cursor_before_initiative",
    ],
)
def test_loader_rejects_impossible_or_inconsistent_s1_saves(tmp_path: Path, corruption: str) -> None:
    game = Encounter.start(rolls=(10, 10))
    path = tmp_path / f"{corruption}.json"
    game.save(path)
    data = json.loads(path.read_text(encoding="utf-8"))
    state = data["state"]
    active_id = state["initiative_order"][state["active_index"]]
    inactive_id = next(actor_id for actor_id in state["initiative_order"] if actor_id != active_id)

    if corruption == "same_team":
        state["creatures"]["synthetic_b"]["team"] = "blue"
    elif corruption == "defeated_but_in_progress":
        state["creatures"]["synthetic_b"]["hp"] = 0
    elif corruption == "inactive_actor_has_actions":
        state["creatures"][inactive_id]["actions_remaining"] = 3
    elif corruption == "inactive_actor_has_attacks":
        state["creatures"][inactive_id]["strikes_this_turn"] = 1
    elif corruption == "inactive_actor_has_diagonals":
        state["creatures"][inactive_id]["diagonals_this_turn"] = 1
    elif corruption == "reversed_initiative":
        state["initiative_order"].reverse()
    elif corruption == "initiative_out_of_range":
        state["creatures"][active_id]["initiative"] = 999
    elif corruption == "winner_does_not_match_survivors":
        state["in_progress"] = False
        state["winner_team"] = "purple"
    elif corruption == "sequence_cursor_before_initiative":
        data["dice"]["index"] = 0
    path.write_text(json.dumps(data), encoding="utf-8")

    with pytest.raises(ValueError):
        Encounter.load(path)
