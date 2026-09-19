"""Bounded route selection for the first closed-map Flee implementation.

This module deliberately contains no encounter or condition state.  It chooses
one route on a finite, rectangular, one-cell grid so a future Flee action can
submit the returned ``path`` to the ordinary :class:`~pf2e.model.Stride`
procedure.  The closed-board convention is the GM choice for the first Fear
scene; this helper does not infer or model exits from the board.

The Fleeing condition requires each action to pursue escape as expediently as
possible (Player Core p. 444):
https://2e.aonprd.com/Conditions.aspx?ID=74

Within that broad requirement, this helper uses the selected local GM
convention: among legally reachable in-map cells, choose one with greatest
movement-independent grid distance from ``fear_source``; find a shortest legal
route to it; and return the prefix affordable by ``speed_ft``.  Equal-distance
goals use ``Position``'s lexicographic ``(x, y)`` order, matching the existing
engine's deterministic candidate ordering.  Equal-cost predecessor choices use
the same order of adjacent destinations.  A route may therefore detour toward
the source while reaching a more distant goal.
"""

from __future__ import annotations

from dataclasses import dataclass
import heapq
from typing import Iterable

from .model import Position
from .space import grid_distance_feet, in_bounds, step_cost


# Position order is (x, y), and this order makes tie behavior independent of
# the order in which a caller supplied occupancy iterables.
_NEIGHBOR_DELTAS: tuple[tuple[int, int], ...] = tuple(
    (dx, dy)
    for dx, dy in sorted(
        ((dx, dy) for dx in (-1, 0, 1) for dy in (-1, 0, 1) if (dx, dy) != (0, 0)),
    )
)


@dataclass(frozen=True)
class FleeRoute:
    """The selected escape destination and one executable route prefix.

    ``full_path`` is the shortest path to ``goal``.  ``path`` is its prefix
    whose ordinary movement cost is at most ``speed_ft``; it is suitable for a
    single ordinary ``Stride`` action.  ``destination`` is the endpoint after
    that action, or ``start`` when no step can be submitted.

    ``stop_reason`` is one of ``"route"``, ``"speed_limit"``,
    ``"physical_boundary"``, or ``"occupied_blocker"``.  The last two values
    are intentionally facts for a runtime policy: the helper cannot perform
    Tumble Through or decide whether some other action opens an exit.  When an
    occupied square is relevant, ``blocked_positions`` reports those literal
    positions in deterministic order.
    """

    start: Position
    goal: Position
    path: tuple[Position, ...]
    full_path: tuple[Position, ...]
    destination: Position
    movement_cost_ft: int
    goal_cost_ft: int
    separation_ft: int
    stop_reason: str
    blocked_positions: tuple[Position, ...] = ()

    @property
    def moved(self) -> bool:
        """Whether the returned prefix contains a movement step."""

        return bool(self.path)


def choose_flee_route(
    start: Position,
    fear_source: Position,
    width: int,
    height: int,
    speed_ft: int,
    *,
    diagonals_already_made: int = 0,
    occupied_positions: Iterable[Position] = (),
    body_positions: Iterable[Position] = (),
    ally_positions: Iterable[Position] = (),
    illegal_final_positions: Iterable[Position] = (),
) -> FleeRoute:
    """Choose one bounded closed-board Flee route.

    The map has no terrain: every in-map cell is traversable except an
    ``occupied_positions`` cell that is neither an explicit ``body_positions``
    nor ``ally_positions`` cell.  Body and ally cells are allowed as route
    intermediates, matching the current ordinary movement model's distinction
    between movement through an occupied ally/body and unsupported movement
    through an unwilling living creature.  Endpoint legality is governed only
    by ``illegal_final_positions``; callers should include every occupied cell
    that the current actor may not legally occupy at the end of this action.
    Additional unoccupied cells may also be listed there (for example, a
    closed door represented as an endpoint restriction).

    ``occupied_positions`` is the complete set of other creature cells.  The
    body/ally sets are unioned into it for convenience, but are required to be
    disjoint.  A normal hostile creature should be supplied only through
    ``occupied_positions``; if it blocks the selected escape the returned
    ``stop_reason`` is ``"occupied_blocker"`` and the caller can apply its
    unsupported Tumble Through policy.

    The search has exactly one best cost and predecessor for each
    ``(Position, diagonal-parity)`` state, at most ``2 * width * height``
    states.  It does not enumerate paths or future actions.  Diagonal parity
    is retained because :func:`pf2e.space.step_cost` alternates diagonal costs
    between 5 and 10 feet.
    """

    _validate_dimensions(width, height)
    _validate_position(start, width, height, name="start")
    _validate_position(fear_source, width, height, name="fear_source")
    if type(speed_ft) is not int or speed_ft < 0:
        raise ValueError("speed_ft must be a non-negative integer")
    if type(diagonals_already_made) is not int or diagonals_already_made < 0:
        raise ValueError("diagonals_already_made must be a non-negative integer")

    occupied = _positions(occupied_positions, width, height, name="occupied_positions")
    body = _positions(body_positions, width, height, name="body_positions")
    allies = _positions(ally_positions, width, height, name="ally_positions")
    illegal_final = _positions(
        illegal_final_positions,
        width,
        height,
        name="illegal_final_positions",
    )
    if body & allies:
        raise ValueError("body_positions and ally_positions must be disjoint")
    occupied |= body | allies

    # The actor's own square is naturally occupied by the actor; callers may
    # include it while passing a snapshot of all creature positions.  Remove
    # it from the other-actor sets so it never blocks the initial state.
    occupied.discard(start)
    body.discard(start)
    allies.discard(start)

    # A route may pass through a body or ally.  Every other occupant is an
    # unwilling creature and is a hard route blocker for this pure helper.
    hard_blockers = occupied - body - allies
    # A body or living ally can be a legal endpoint under the ordinary movement
    # contract in some contexts.  The pure helper has no actor size or action
    # ledger, so the caller explicitly supplies endpoint restrictions instead
    # of having this function guess them.
    final_forbidden = illegal_final
    final_forbidden.discard(start)

    initial_parity = diagonals_already_made % 2
    initial_state = (start, initial_parity)
    best_cost: dict[tuple[Position, int], int] = {initial_state: 0}
    predecessor: dict[tuple[Position, int], tuple[Position, int] | None] = {
        initial_state: None,
    }
    # A monotonically increasing queue sequence resolves equal-cost heap keys
    # without comparing state records and preserves deterministic discovery.
    queue: list[tuple[int, int, int, int, int, tuple[Position, int]]] = [
        (0, 0, start.x, start.y, initial_parity, initial_state)
    ]
    sequence = 1
    while queue:
        cost, _order, _x, _y, _parity, state = heapq.heappop(queue)
        if best_cost.get(state) != cost:
            continue
        current, parity = state
        for dx, dy in _NEIGHBOR_DELTAS:
            destination = Position(current.x + dx, current.y + dy)
            if not in_bounds(destination, width, height) or destination in hard_blockers:
                continue
            step, diagonal_count = step_cost(current, destination, parity)
            next_state = (destination, (parity + diagonal_count) % 2)
            next_cost = cost + step
            if next_cost >= best_cost.get(next_state, 10**18):
                continue
            best_cost[next_state] = next_cost
            predecessor[next_state] = state
            heapq.heappush(
                queue,
                (
                    next_cost,
                    sequence,
                    destination.x,
                    destination.y,
                    next_state[1],
                    next_state,
                ),
            )
            sequence += 1

    # Pick the furthest legal cell first.  Equal separation uses Position's
    # stable (x, y) order, then shortest movement cost and parity as a final
    # deterministic tie.  Starting square is always retained as a fallback.
    state_by_position: dict[Position, tuple[Position, int]] = {}
    for state, cost in best_cost.items():
        position, parity = state
        if position != start and position in final_forbidden:
            continue
        prior = state_by_position.get(position)
        if prior is None or (cost, parity) < (best_cost[prior], prior[1]):
            state_by_position[position] = state

    if start not in state_by_position:
        # This cannot happen because initial_state is never removed, but keep
        # the invariant explicit if the search changes in a future edit.
        state_by_position[start] = initial_state

    goal = max(
        state_by_position,
        key=lambda position: (
            grid_distance_feet(fear_source, position),
            -position.x,
            -position.y,
        ),
    )
    goal_state = state_by_position[goal]
    full_path = _reconstruct_path(goal_state, predecessor)
    goal_cost = best_cost[goal_state]

    candidate_path: list[Position] = []
    candidate_cost = 0
    last_legal_index = 0
    last_legal_cost = 0
    current = start
    parity = initial_parity
    prefix_stop: str | None = None
    prefix_blocker: Position | None = None
    for destination in full_path:
        step, diagonal_count = step_cost(current, destination, parity)
        if candidate_cost + step > speed_ft:
            prefix_stop = "speed_limit"
            break
        # A body/ally may be traversed.  If the Speed prefix runs out while
        # inside one, trim the submitted path back to its latest legal endpoint
        # so ordinary Stride never finishes in a forbidden occupied square.
        candidate_path.append(destination)
        candidate_cost += step
        if destination not in final_forbidden:
            last_legal_index = len(candidate_path)
            last_legal_cost = candidate_cost
        else:
            prefix_blocker = destination
        parity = (parity + diagonal_count) % 2
        current = destination

    path = candidate_path[:last_legal_index]
    movement_cost = last_legal_cost
    if len(path) != len(candidate_path):
        prefix_stop = "occupied_blocker"

    if prefix_stop is None:
        stop_reason = "route" if path else _no_route_reason(
            start=start,
            fear_source=fear_source,
            width=width,
            height=height,
            occupied=occupied,
            goal=goal,
            separation=grid_distance_feet(fear_source, goal),
        )
    else:
        stop_reason = prefix_stop

    blocked_positions = _relevant_blockers(
        fear_source=fear_source,
        start=start,
        goal=goal,
        separation=grid_distance_feet(fear_source, goal),
        occupied=occupied,
        hard_blockers=hard_blockers,
        final_forbidden=final_forbidden,
        width=width,
        height=height,
    )
    if prefix_stop == "occupied_blocker" and prefix_blocker is not None:
        blocked_positions = tuple(sorted(set(blocked_positions) | {prefix_blocker}))
    if stop_reason != "occupied_blocker":
        blocked_positions = ()

    destination = path[-1] if path else start
    return FleeRoute(
        start=start,
        goal=goal,
        path=tuple(path),
        full_path=full_path,
        destination=destination,
        movement_cost_ft=movement_cost,
        goal_cost_ft=goal_cost,
        separation_ft=grid_distance_feet(fear_source, goal),
        stop_reason=stop_reason,
        blocked_positions=blocked_positions,
    )


def _validate_dimensions(width: int, height: int) -> None:
    if type(width) is not int or width < 1:
        raise ValueError("width must be a positive integer")
    if type(height) is not int or height < 1:
        raise ValueError("height must be a positive integer")


def _validate_position(position: Position, width: int, height: int, *, name: str) -> None:
    if not isinstance(position, Position) or not in_bounds(position, width, height):
        raise ValueError(f"{name} must be an in-map Position")


def _positions(
    values: Iterable[Position],
    width: int,
    height: int,
    *,
    name: str,
) -> set[Position]:
    try:
        positions = set(values)
    except TypeError as error:
        raise ValueError(f"{name} must be an iterable of Position values") from error
    for position in positions:
        _validate_position(position, width, height, name=name)
    return positions


def _reconstruct_path(
    state: tuple[Position, int],
    predecessor: dict[tuple[Position, int], tuple[Position, int] | None],
) -> tuple[Position, ...]:
    path: list[Position] = []
    current: tuple[Position, int] | None = state
    while current is not None:
        path.append(current[0])
        current = predecessor[current]
    path.reverse()
    return tuple(path[1:])


def _no_route_reason(
    *,
    start: Position,
    fear_source: Position,
    width: int,
    height: int,
    occupied: set[Position],
    goal: Position,
    separation: int,
) -> str:
    if goal != start:
        return "route"
    maximum_in_map_separation = max(
        grid_distance_feet(fear_source, Position(x, y))
        for x in range(width)
        for y in range(height)
    )
    if maximum_in_map_separation > separation and occupied:
        return "occupied_blocker"
    return "physical_boundary"


def _relevant_blockers(
    *,
    fear_source: Position,
    start: Position,
    goal: Position,
    separation: int,
    occupied: set[Position],
    hard_blockers: set[Position],
    final_forbidden: set[Position],
    width: int,
    height: int,
) -> tuple[Position, ...]:
    """Return literal occupied facts when no farther legal goal was found."""

    if goal != start:
        return ()
    maximum_in_map_separation = max(
        grid_distance_feet(fear_source, Position(x, y))
        for x in range(width)
        for y in range(height)
    )
    if maximum_in_map_separation <= separation:
        return ()
    farther_occupied = {
        position
        for position in occupied
        if grid_distance_feet(fear_source, position) > separation
    }
    # If the only farther cells are passable bodies/allies but illegal as final
    # cells, report those facts too; the caller must decide whether another
    # action or an unsupported maneuver can resolve them.
    farther_occupied |= {
        position
        for position in final_forbidden
        if position in occupied and grid_distance_feet(fear_source, position) > separation
    }
    if farther_occupied:
        return tuple(sorted(farther_occupied))
    # A hard blocker at the reachable frontier may be nearer to the source than
    # the first unreachable square. Include it as a useful policy fact while
    # preserving the physical-vs-occupied distinction.
    frontier = {
        blocked
        for blocked in hard_blockers
        if any(
            in_bounds(Position(blocked.x + dx, blocked.y + dy), width, height)
            and Position(blocked.x + dx, blocked.y + dy) not in hard_blockers
            for dx, dy in _NEIGHBOR_DELTAS
        )
    }
    return tuple(sorted(frontier))


__all__ = ["FleeRoute", "choose_flee_route"]
