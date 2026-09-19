"""One-cell open-grid movement, targeting geometry, and ordinary reach.

Rules checked 2026-09-15 against Player Core pp. 421–425:
https://2e.aonprd.com/Rules.aspx?ID=2356
https://2e.aonprd.com/Rules.aspx?ID=2359
https://2e.aonprd.com/Rules.aspx?ID=2372
https://2e.aonprd.com/Rules.aspx?ID=2375
"""

from fractions import Fraction

from .model import Position


def in_bounds(position: Position, width: int, height: int) -> bool:
    return (
        type(position.x) is int
        and type(position.y) is int
        and 0 <= position.x < width
        and 0 <= position.y < height
    )


def is_adjacent(first: Position, second: Position) -> bool:
    dx, dy = abs(first.x - second.x), abs(first.y - second.y)
    return max(dx, dy) == 1


def grid_distance_feet(first: Position, second: Position) -> int:
    """Measure independent of a creature's movement parity for reach queries."""
    dx, dy = abs(first.x - second.x), abs(first.y - second.y)
    diagonals = min(dx, dy)
    straight = max(dx, dy) - diagonals
    diagonal_feet = sum(5 if index % 2 == 0 else 10 for index in range(diagonals))
    return diagonal_feet + 5 * straight


def diagonal_step_cost(diagonals_already_made: int) -> int:
    if diagonals_already_made < 0:
        raise ValueError("diagonal movement count cannot be negative")
    return 5 if diagonals_already_made % 2 == 0 else 10


def step_cost(first: Position, second: Position, diagonals_already_made: int) -> tuple[int, int]:
    """Return movement cost in feet and the number of new diagonals (0 or 1)."""
    dx, dy = abs(first.x - second.x), abs(first.y - second.y)
    if max(dx, dy) != 1 or (dx == 0 and dy == 0):
        raise ValueError("a grid step must move to one adjacent cell")
    if dx == 1 and dy == 1:
        return diagonal_step_cost(diagonals_already_made), 1
    return 5, 0


def occupied(position: Position, positions: tuple[Position, ...], *, except_position: Position | None = None) -> bool:
    return position != except_position and position in positions


def _cell_segment_interval(
    start: Position, end: Position, cell: Position
) -> tuple[Fraction, Fraction] | None:
    """Clip a center-to-center segment against a one-cell square exactly."""
    # Doubled coordinates put cell edges at integers and cell centers at even
    # integers, avoiding both floating point and half-integer arithmetic.
    origin = (2 * start.x, 2 * start.y)
    delta = (2 * (end.x - start.x), 2 * (end.y - start.y))
    lower = (2 * cell.x - 1, 2 * cell.y - 1)
    upper = (2 * cell.x + 1, 2 * cell.y + 1)
    entering, leaving = Fraction(0), Fraction(1)

    for axis in range(2):
        if delta[axis] == 0:
            if not lower[axis] <= origin[axis] <= upper[axis]:
                return None
            continue

        near = Fraction(lower[axis] - origin[axis], delta[axis])
        far = Fraction(upper[axis] - origin[axis], delta[axis])
        if near > far:
            near, far = far, near
        entering = max(entering, near)
        leaving = min(leaving, far)
        if entering > leaving:
            return None

    return entering, leaving


def _point_on_open_cell_interior(
    start: Position, end: Position, cell: Position, parameter: Fraction
) -> bool:
    """Return whether a rational segment point is strictly inside a cell."""
    x = 2 * start.x + 2 * (end.x - start.x) * parameter
    y = 2 * start.y + 2 * (end.y - start.y) * parameter
    return 2 * cell.x - 1 < x < 2 * cell.x + 1 and 2 * cell.y - 1 < y < 2 * cell.y + 1


def segment_crosses_cell_interior(start: Position, end: Position, cell: Position) -> bool:
    """Whether a center-to-center segment passes through a cell's open interior.

    The cell is the unit square centered at ``cell``. Touching only an edge or
    corner does not count as cover; that boundary choice follows the documented
    GM policy for lesser-creature-cover geometry. Callers decide which cells
    are candidate blockers and whether they are actually intervening.
    """
    if start == end:
        return False
    interval = _cell_segment_interval(start, end, cell)
    if interval is None:
        return False
    entering, leaving = interval
    if entering >= leaving:
        return False
    return _point_on_open_cell_interior(start, end, cell, (entering + leaving) / 2)


def _boundary_faces(
    start: Position, end: Position, cell: Position, parameter: Fraction
) -> frozenset[str]:
    x = 2 * start.x + 2 * (end.x - start.x) * parameter
    y = 2 * start.y + 2 * (end.y - start.y) * parameter
    faces: set[str] = set()
    if x == 2 * cell.x - 1:
        faces.add("west")
    if x == 2 * cell.x + 1:
        faces.add("east")
    if y == 2 * cell.y - 1:
        faces.add("south")
    if y == 2 * cell.y + 1:
        faces.add("north")
    return frozenset(faces)


def flanking_geometry(first: Position, second: Position, target: Position) -> bool:
    """Whether two centers' segment crosses the target square oppositely.

    This is only the geometric part of flanking under Player Core p. 425.
    Callers must separately establish ally status, consciousness, valid melee
    attacks, and reach. All three positions must be distinct; square-edge
    intersections count when the segment passes through the square interior.
    """
    if first == second or first == target or second == target:
        return False
    if not segment_crosses_cell_interior(first, second, target):
        return False

    interval = _cell_segment_interval(first, second, target)
    assert interval is not None  # The interior-crossing check established it.
    entering, leaving = interval
    entry_faces = _boundary_faces(first, second, target, entering)
    exit_faces = _boundary_faces(first, second, target, leaving)
    opposite_pairs = (("west", "east"), ("south", "north"))
    return any(
        (first_face in entry_faces and second_face in exit_faces)
        or (second_face in entry_faces and first_face in exit_faces)
        for first_face, second_face in opposite_pairs
    )
