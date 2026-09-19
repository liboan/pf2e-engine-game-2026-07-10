from __future__ import annotations

import pytest

from pf2e.model import Position
from pf2e.space import flanking_geometry, segment_crosses_cell_interior


@pytest.mark.parametrize(
    ("first", "second"),
    [
        (Position(-1, 0), Position(1, 0)),  # Opposite orthogonal sides.
        (Position(-1, -1), Position(1, 1)),  # Opposite corners.
        (Position(-1, 0), Position(3, 1)),  # Near diagonal, west to east.
    ],
)
def test_flanking_geometry_crosses_opposite_sides_or_corners_symmetrically(first, second) -> None:
    target = Position(0, 0)
    assert flanking_geometry(first, second, target)
    assert flanking_geometry(second, first, target)


def test_flanking_geometry_rejects_adjacent_side_intercept() -> None:
    # This segment enters through the west side and exits through the north.
    first, second, target = Position(-1, 0), Position(1, 1), Position(0, 0)
    assert not flanking_geometry(first, second, target)
    assert not flanking_geometry(second, first, target)


@pytest.mark.parametrize(
    ("first", "second", "target"),
    [
        (Position(-2, 0), Position(-1, 0), Position(0, 0)),
        (Position(-1, 0), Position(-1, 0), Position(0, 0)),
        (Position(0, 0), Position(1, 0), Position(0, 0)),
        (Position(-1, 0), Position(1, 0), Position(1, 0)),
    ],
)
def test_flanking_geometry_rejects_same_side_or_coincident_positions(first, second, target) -> None:
    assert not flanking_geometry(first, second, target)
    assert not flanking_geometry(second, first, target)


def test_segment_crosses_intervening_straight_and_diagonal_cells() -> None:
    blocker = Position(0, 0)
    assert segment_crosses_cell_interior(Position(-2, 0), Position(2, 0), blocker)
    assert segment_crosses_cell_interior(Position(-2, -2), Position(2, 2), blocker)


def test_segment_does_not_cross_an_off_line_cell_or_a_corner_tangent() -> None:
    start, end = Position(-2, 0), Position(2, 0)
    assert not segment_crosses_cell_interior(start, end, Position(0, 1))
    assert not segment_crosses_cell_interior(Position(0, 0), Position(0, 0), Position(0, 0))

    # The segment touches only the target's north-west corner. With integer
    # cell-center endpoints, an edge-only tangent cannot occur without also
    # entering the square; the strict interior check excludes both cases.
    assert not segment_crosses_cell_interior(Position(-1, 0), Position(0, 1), Position(0, 0))


@pytest.mark.parametrize(
    ("start", "end", "cell"),
    [
        (Position(-2, 0), Position(2, 0), Position(0, 0)),
        (Position(-1, 0), Position(0, 1), Position(0, 0)),
        (Position(-2, -2), Position(2, 2), Position(0, 0)),
    ],
)
def test_segment_cell_interior_is_symmetric_under_endpoint_reversal(start, end, cell) -> None:
    forward = segment_crosses_cell_interior(start, end, cell)
    reverse = segment_crosses_cell_interior(end, start, cell)
    assert forward == reverse
