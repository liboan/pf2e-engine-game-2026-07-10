"""Pure closed-map Flee route selection checks."""

from __future__ import annotations

import time
import tracemalloc

from pf2e.fleeing import choose_flee_route
from pf2e.model import Position


P = Position


def test_furthest_goal_tie_is_stable_and_source_occupancy_is_not_a_false_blocker() -> None:
    # All four corners are equally distant from the center under the existing
    # alternating-diagonal grid metric.  Position order chooses (0, 0), and
    # listing the fear source as an occupied creature does not change the
    # physical-boundary result when the actor already occupies a furthest cell.
    route = choose_flee_route(
        P(0, 0),
        P(1, 1),
        2,
        2,
        25,
        occupied_positions=(P(1, 1),),
    )

    assert route.goal == P(0, 0)
    assert route.path == ()
    assert route.destination == P(0, 0)
    assert route.stop_reason == "physical_boundary"
    assert route.blocked_positions == ()


def test_shortest_route_uses_existing_diagonal_parity_and_speed_prefix() -> None:
    first_diagonal = choose_flee_route(P(1, 1), P(0, 0), 5, 5, 15)
    second_diagonal = choose_flee_route(
        P(1, 1),
        P(0, 0),
        5,
        5,
        15,
        diagonals_already_made=1,
    )

    assert first_diagonal.goal == P(4, 4)
    assert first_diagonal.full_path == (P(2, 2), P(3, 3), P(4, 4))
    assert first_diagonal.path == (P(2, 2), P(3, 3))
    assert first_diagonal.movement_cost_ft == 15
    assert first_diagonal.goal_cost_ft == 20
    assert second_diagonal.path == first_diagonal.path
    assert second_diagonal.movement_cost_ft == 15
    assert second_diagonal.goal_cost_ft == 25
    assert second_diagonal.stop_reason == "speed_limit"


def test_legal_detour_can_temporarily_approach_the_fear_source() -> None:
    # The actor's only exit from the pocket first reduces separation from the
    # source, then reaches the furthest far corner.
    blocked = (P(4, 1), P(4, 2), P(4, 3), P(3, 1), P(3, 3))
    route = choose_flee_route(
        P(3, 2),
        P(0, 0),
        5,
        5,
        100,
        occupied_positions=blocked,
    )

    assert route.goal == P(4, 4)
    assert route.full_path[0] == P(2, 3)
    assert route.separation_ft > 20  # start separation is 20 feet
    assert route.stop_reason == "route"


def test_body_and_ally_cells_are_intermediate_only_when_final_cell_is_illegal() -> None:
    body_route = choose_flee_route(
        P(0, 0),
        P(0, 0),
        4,
        1,
        100,
        body_positions=(P(1, 0),),
        illegal_final_positions=(P(1, 0),),
    )
    ally_route = choose_flee_route(
        P(0, 0),
        P(0, 0),
        4,
        1,
        100,
        ally_positions=(P(1, 0),),
        illegal_final_positions=(P(1, 0),),
    )

    assert body_route.goal == P(3, 0)
    assert body_route.full_path == (P(1, 0), P(2, 0), P(3, 0))
    assert body_route.path == body_route.full_path
    assert body_route.destination == P(3, 0)
    assert ally_route.path == body_route.path
    assert ally_route.destination == P(3, 0)


def test_only_hostile_occupied_route_reports_blocker_facts() -> None:
    route = choose_flee_route(
        P(1, 0),
        P(0, 0),
        3,
        1,
        25,
        occupied_positions=(P(2, 0),),
    )

    assert route.goal == P(1, 0)
    assert route.path == ()
    assert route.stop_reason == "occupied_blocker"
    assert route.blocked_positions == (P(2, 0),)


def test_speed_prefix_never_finishes_in_an_illegal_final_cell() -> None:
    route = choose_flee_route(
        P(0, 0),
        P(0, 0),
        4,
        1,
        5,
        body_positions=(P(1, 0),),
        illegal_final_positions=(P(1, 0),),
    )

    assert route.full_path == (P(1, 0), P(2, 0), P(3, 0))
    assert route.path == ()
    assert route.destination == P(0, 0)
    assert route.stop_reason == "occupied_blocker"
    assert route.blocked_positions == (P(1, 0),)


def test_large_map_stays_bounded_in_time_and_memory() -> None:
    width, height = 80, 60
    tracemalloc.start()
    started = time.perf_counter()
    route = choose_flee_route(
        P(width // 2, height // 2),
        P(0, 0),
        width,
        height,
        25,
    )
    elapsed = time.perf_counter() - started
    _current, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()

    assert route.path
    assert elapsed < 2.0
    assert peak < 12 * 1024 * 1024
