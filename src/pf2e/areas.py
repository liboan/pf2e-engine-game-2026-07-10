"""Finite PF2e grid-footprint and area geometry helpers.

Area templates follow Player Core's grid rules: areas use the same distance
measure as movement, emanations start at the edges of the source space, bursts
start at a grid intersection, cones start at an edge or corner, and lines are
5 feet wide unless a rule says otherwise. These helpers return candidate ground
cells only; they do not clip to a map or resolve line of effect, cover,
eligibility, or sharing occupancy.

Rules: https://2e.aonprd.com/Rules.aspx?ID=2263 (Areas, Player Core p. 428)
      https://2e.aonprd.com/Rules.aspx?ID=2359 (Size, Space, and Reach)
      https://2e.aonprd.com/Rules.aspx?ID=2356 (Grid Movement)
"""

from __future__ import annotations

from dataclasses import dataclass

from .model import Position
from .space import grid_distance_feet


@dataclass(frozen=True)
class Footprint:
    """A rectangular set of grid cells, anchored at its south-west cell.

    ``width_cells`` and ``height_cells`` describe occupied map squares, not a
    creature's rules-defined size or permission to share a square. Tiny
    creatures still need core occupancy rules to allow their source-defined
    sharing behavior; this geometric record does not encode it.
    """

    origin: Position
    width_cells: int = 1
    height_cells: int = 1

    def __post_init__(self) -> None:
        _require_position(self.origin)
        if type(self.width_cells) is not int or self.width_cells < 1:
            raise ValueError("footprint width must be a positive integer")
        if type(self.height_cells) is not int or self.height_cells < 1:
            raise ValueError("footprint height must be a positive integer")


def occupied_cells(footprint: Footprint) -> tuple[Position, ...]:
    """Return occupied cells in row-major order (south to north, west to east)."""
    _require_footprint(footprint)
    return tuple(
        Position(footprint.origin.x + x, footprint.origin.y + y)
        for y in range(footprint.height_cells)
        for x in range(footprint.width_cells)
    )


def footprint_distance_ft(first: Footprint, second: Footprint) -> int:
    """Return ordinary grid distance between the nearest occupied cells.

    This query is independent of movement parity. Its constant-time rectangle
    calculation is equivalent to comparing every pair of cells because grid
    distance is monotonic in each axis.
    """
    _require_footprint(first)
    _require_footprint(second)

    first_right = first.origin.x + first.width_cells - 1
    first_top = first.origin.y + first.height_cells - 1
    second_right = second.origin.x + second.width_cells - 1
    second_top = second.origin.y + second.height_cells - 1
    dx = max(0, first.origin.x - second_right, second.origin.x - first_right)
    dy = max(0, first.origin.y - second_top, second.origin.y - first_top)
    return grid_distance_feet(Position(0, 0), Position(dx, dy))


def emanation_cells(origin: Footprint, radius_ft: int) -> frozenset[Position]:
    """Return cells within ``radius_ft`` of any cell of the source footprint.

    Distances are measured between cell centers with the movement-independent
    grid-distance rule. Including the source footprint is intentional: the
    rules let the creator choose whether to affect itself, which is resolved by
    the caller.
    """
    _require_footprint(origin)
    _require_radius(radius_ft)

    span = radius_ft // 5
    cells: set[Position] = set()
    for y in range(origin.origin.y - span, origin.origin.y + origin.height_cells + span):
        for x in range(origin.origin.x - span, origin.origin.x + origin.width_cells + span):
            cell = Position(x, y)
            if footprint_distance_ft(origin, Footprint(cell)) <= radius_ft:
                cells.add(cell)
    return frozenset(cells)


def burst_cells(origin: Position, radius_ft: int) -> frozenset[Position]:
    """Return cells in a burst centered at a grid intersection.

    ``origin`` is the integer coordinate of a grid intersection, not a
    creature's cell center. The candidate cell is tested at its center, whose
    doubled coordinate is odd on both axes. The doubled lattice lets us reuse
    the movement-independent grid-distance rule without floating point.
    Boundary cells are included. This follows the AoN/Player Core area template
    convention; a burst's range to its origin is a separate targeting check.
    """
    _require_position(origin)
    _require_radius(radius_ft)

    span = radius_ft // 5 + 1
    doubled_origin = Position(2 * origin.x, 2 * origin.y)
    cells: set[Position] = set()
    for y in range(origin.y - span, origin.y + span + 1):
        for x in range(origin.x - span, origin.x + span + 1):
            cell = Position(x, y)
            doubled_center = Position(2 * x + 1, 2 * y + 1)
            doubled_distance = grid_distance_feet(doubled_origin, doubled_center)
            if doubled_distance <= 2 * radius_ft:
                cells.add(cell)
    return frozenset(cells)


def freezing_rime_cells(familiar_square: Position) -> frozenset[Position]:
    """Return the fixed 5-foot burst cells for Familiar of Freezing Rime.

    Unlike an ordinary burst, this patron ability centers its burst on a square
    in the familiar's space. ``familiar_square`` is therefore a cell coordinate
    whose center is the burst origin, not a grid intersection. Its 5-foot
    radius includes the selected square and its eight neighbors under the
    ordinary grid-distance rule. The caller chooses a square from the familiar
    footprint and records this returned set when the ability triggers.

    Source: https://2e.aonprd.com/Patrons.aspx?ID=15 (Silence in Snow,
    Familiar of Freezing Rime); area distances:
    https://2e.aonprd.com/Rules.aspx?ID=2263
    """
    _require_position(familiar_square)
    return frozenset(
        Position(x, y)
        for y in range(familiar_square.y - 1, familiar_square.y + 2)
        for x in range(familiar_square.x - 1, familiar_square.x + 2)
        if grid_distance_feet(familiar_square, Position(x, y)) <= 5
    )


def cone_cells(
    origin: Footprint, direction: Position, radius_ft: int
) -> frozenset[Position]:
    """Return cells in a quarter-circle cone directed along a grid octant.

    ``direction`` is one of the eight adjacent-cell vectors. Orthogonal cones
    originate at the midpoint of the corresponding footprint edge; diagonal
    cones originate at the corresponding footprint corner. Candidate cell
    centers inside the 90-degree sector and within the movement-independent
    grid radius are included. Cells occupied by the source itself are excluded.
    """
    _require_footprint(origin)
    _require_direction(direction)
    _require_radius(radius_ft)

    point_x2, point_y2 = _origin_point_doubled(origin, direction)
    span = radius_ft // 5 + 2
    min_x = origin.origin.x - span
    max_x = origin.origin.x + origin.width_cells + span
    min_y = origin.origin.y - span
    max_y = origin.origin.y + origin.height_cells + span
    source_cells = set(occupied_cells(origin))
    cells: set[Position] = set()

    for y in range(min_y, max_y + 1):
        for x in range(min_x, max_x + 1):
            cell = Position(x, y)
            if cell in source_cells:
                continue
            dx2, dy2 = 2 * x + 1 - point_x2, 2 * y + 1 - point_y2
            dot = dx2 * direction.x + dy2 * direction.y
            cross = dx2 * direction.y - dy2 * direction.x
            if dot <= 0 or abs(cross) > dot:
                continue
            doubled_distance = grid_distance_feet(Position(0, 0), Position(dx2, dy2))
            if doubled_distance <= 2 * radius_ft:
                cells.add(cell)
    return frozenset(cells)


def line_cells(
    origin: Footprint,
    direction: Position,
    length_ft: int,
    width_ft: int = 5,
) -> frozenset[Position]:
    """Return centerline cells in a directed area line.

    ``direction`` uses the same eight grid vectors and edge/corner origin
    convention as :func:`cone_cells`. Candidate cell centers must lie within
    the line segment and its width. The default width is the rules' 5 feet;
    lines with a different printed width can pass it explicitly.
    """
    _require_footprint(origin)
    _require_direction(direction)
    _require_radius(length_ft, name="line length")
    if type(width_ft) is not int or width_ft < 1:
        raise ValueError("line width must be a positive integer")

    point_x2, point_y2 = _origin_point_doubled(origin, direction)
    span = length_ft // 5 + 2
    min_x = origin.origin.x - span
    max_x = origin.origin.x + origin.width_cells + span
    min_y = origin.origin.y - span
    max_y = origin.origin.y + origin.height_cells + span
    source_cells = set(occupied_cells(origin))
    cells: set[Position] = set()

    for y in range(min_y, max_y + 1):
        for x in range(min_x, max_x + 1):
            cell = Position(x, y)
            if cell in source_cells:
                continue
            dx2, dy2 = 2 * x + 1 - point_x2, 2 * y + 1 - point_y2
            dot = dx2 * direction.x + dy2 * direction.y
            cross = dx2 * direction.y - dy2 * direction.x
            if dot <= 0:
                continue
            doubled_distance = grid_distance_feet(Position(0, 0), Position(dx2, dy2))
            if doubled_distance > 2 * length_ft:
                continue
            if direction.x == 0 or direction.y == 0:
                within_width = 5 * abs(cross) <= width_ft
            else:
                within_width = 25 * cross * cross <= 2 * width_ft * width_ft
            if within_width:
                cells.add(cell)
    return frozenset(cells)


def _origin_point_doubled(origin: Footprint, direction: Position) -> tuple[int, int]:
    left, bottom = origin.origin.x, origin.origin.y
    right = left + origin.width_cells
    top = bottom + origin.height_cells

    if direction.x == 0:
        x2 = 2 * left + origin.width_cells
        y2 = 2 * top if direction.y > 0 else 2 * bottom
    elif direction.y == 0:
        x2 = 2 * right if direction.x > 0 else 2 * left
        y2 = 2 * bottom + origin.height_cells
    else:
        x2 = 2 * right if direction.x > 0 else 2 * left
        y2 = 2 * top if direction.y > 0 else 2 * bottom
    return x2, y2


def _require_footprint(footprint: Footprint) -> None:
    if not isinstance(footprint, Footprint):
        raise ValueError("expected a Footprint")


def _require_position(position: Position) -> None:
    if (
        not isinstance(position, Position)
        or type(position.x) is not int
        or type(position.y) is not int
    ):
        raise ValueError("expected an integer Position")


def _require_direction(direction: Position) -> None:
    _require_position(direction)
    if direction.x not in (-1, 0, 1) or direction.y not in (-1, 0, 1):
        raise ValueError("direction must be an adjacent-cell vector")
    if direction.x == 0 and direction.y == 0:
        raise ValueError("direction cannot be zero")


def _require_radius(radius_ft: int, *, name: str = "radius") -> None:
    if type(radius_ft) is not int or radius_ft < 0:
        raise ValueError(f"{name} must be a non-negative integer")
