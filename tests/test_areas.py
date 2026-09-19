from __future__ import annotations

import pytest

from pf2e.areas import (
    Footprint,
    burst_cells,
    cone_cells,
    emanation_cells,
    footprint_distance_ft,
    freezing_rime_cells,
    line_cells,
    occupied_cells,
)
from pf2e.model import Position


def test_occupied_cells_are_row_major_for_rectangular_footprints() -> None:
    footprint = Footprint(Position(-1, 3), width_cells=2, height_cells=3)

    assert occupied_cells(footprint) == (
        Position(-1, 3),
        Position(0, 3),
        Position(-1, 4),
        Position(0, 4),
        Position(-1, 5),
        Position(0, 5),
    )


@pytest.mark.parametrize(
    ("width_cells", "height_cells"),
    [(0, 1), (1, 0), (-1, 1), (1, -1), (True, 1), (1, False)],
)
def test_footprint_requires_positive_integer_dimensions(width_cells, height_cells) -> None:
    with pytest.raises(ValueError):
        Footprint(Position(0, 0), width_cells, height_cells)


def test_footprint_distance_uses_nearest_occupied_squares_for_reach() -> None:
    large = Footprint(Position(0, 0), width_cells=2, height_cells=2)

    assert footprint_distance_ft(large, Footprint(Position(2, 1))) == 5
    assert footprint_distance_ft(large, Footprint(Position(2, 2))) == 5
    assert footprint_distance_ft(large, Footprint(Position(3, 2))) == 10
    assert footprint_distance_ft(large, Footprint(Position(1, 1))) == 0


@pytest.mark.parametrize(
    ("offset", "expected_distance"),
    [((4, 4), 30), ((5, 3), 30), ((6, 1), 30), ((6, 2), 35)],
)
def test_footprint_distance_preserves_area_and_reach_grid_boundaries(
    offset: tuple[int, int], expected_distance: int
) -> None:
    # Player Core area/reach examples use the ordinary grid-distance rule,
    # independently of a creature's movement-parity counter.
    assert footprint_distance_ft(
        Footprint(Position(0, 0)), Footprint(Position(*offset))
    ) == expected_distance


def test_emanation_distance_is_from_every_origin_cell() -> None:
    origin = Footprint(Position(0, 0), width_cells=2, height_cells=2)
    cells = emanation_cells(origin, 5)

    # A 5-foot emanation from the whole 10-by-10-foot space reaches all
    # 16 neighboring/contact cells; using only its anchor would omit squares.
    assert len(cells) == 16
    assert Position(-1, -1) in cells
    assert Position(2, 2) in cells
    assert Position(3, 2) not in cells
    assert emanation_cells(origin, 0) == frozenset(occupied_cells(origin))


def test_30_foot_emanation_includes_exact_grid_boundary_offsets() -> None:
    cells = emanation_cells(Footprint(Position(0, 0)), 30)

    # The documented Player Core grid-distance examples are 30 feet; moving
    # one square farther on the latter diagonal makes the distance 35 feet.
    assert {Position(4, 4), Position(5, 3), Position(6, 1)} <= cells
    assert Position(6, 2) not in cells


def test_burst_uses_grid_intersection_origin_not_a_creature_cell_center() -> None:
    five_foot = burst_cells(Position(0, 0), 5)

    # A 5-foot burst at a corner reaches the four cells meeting at that point.
    assert five_foot == frozenset(
        {
            Position(-1, -1),
            Position(-1, 0),
            Position(0, -1),
            Position(0, 0),
        }
    )

    ten_foot = burst_cells(Position(0, 0), 10)
    assert len(ten_foot) == 16
    assert Position(1, 1) in ten_foot
    assert Position(-2, -2) in ten_foot
    assert Position(2, 0) not in ten_foot


def test_burst_translation_preserves_the_corner_template() -> None:
    origin = Position(5, -3)
    actual = burst_cells(origin, 5)
    expected = frozenset(
        Position(cell.x + origin.x, cell.y + origin.y)
        for cell in burst_cells(Position(0, 0), 5)
    )

    assert actual == expected


def test_freezing_rime_burst_is_centered_on_a_familiar_space_square() -> None:
    cells = freezing_rime_cells(Position(4, -2))

    # Silence in Snow's Familiar of Freezing Rime centers its 5-foot burst on
    # a chosen familiar-space square, so the ordinary corner-origin template
    # would affect a different set of cells.
    assert cells == frozenset(
        Position(x, y)
        for x in range(3, 6)
        for y in range(-3, 0)
    )


def test_15_foot_burst_includes_its_grid_boundary_but_not_the_next_ring() -> None:
    cells = burst_cells(Position(0, 0), 15)

    # The half-square positions are measured from the burst's grid-intersection
    # origin using the same alternating diagonal scale as grid movement.
    assert Position(2, 1) in cells
    assert Position(3, 1) not in cells


def test_15_foot_orthogonal_cone_is_a_quarter_circle_from_the_facing_edge() -> None:
    cells = cone_cells(Footprint(Position(0, 0)), Position(0, 1), 15)

    # Spray of Stars is a 15-foot cone. The facing edge is the source; the
    # template fans north, excludes the source's space, and includes its
    # 45-degree boundary cells.
    assert len(cells) == 7
    assert Position(0, 1) in cells
    assert Position(-1, 2) in cells
    assert Position(1, 2) in cells
    assert Position(-1, 3) in cells
    assert Position(1, 3) in cells
    assert Position(0, 0) not in cells
    assert Position(0, -1) not in cells
    assert Position(2, 3) not in cells


def test_diagonal_cone_origin_uses_the_facing_corner() -> None:
    cells = cone_cells(Footprint(Position(0, 0)), Position(1, 1), 15)

    assert Position(1, 1) in cells
    assert Position(0, 1) not in cells
    assert Position(1, 0) not in cells
    assert Position(-1, 1) not in cells


def test_lines_follow_an_eight_way_direction_and_printed_grid_length() -> None:
    east = line_cells(Footprint(Position(0, 0)), Position(1, 0), 30)
    assert east == frozenset(Position(x, 0) for x in range(1, 7))

    northeast = line_cells(Footprint(Position(0, 0)), Position(1, 1), 30)
    assert northeast == frozenset(Position(n, n) for n in range(1, 5))


def test_60_foot_line_includes_the_last_orthogonal_cell() -> None:
    cells = line_cells(Footprint(Position(0, 0)), Position(1, 0), 60)

    assert len(cells) == 12
    assert Position(12, 0) in cells
    assert Position(13, 0) not in cells


@pytest.mark.parametrize(
    "call",
    [
        lambda: emanation_cells(Footprint(Position(0, 0)), -5),
        lambda: burst_cells(Position(0, 0), -5),
        lambda: cone_cells(Footprint(Position(0, 0)), Position(0, 0), 15),
        lambda: line_cells(Footprint(Position(0, 0)), Position(2, 0), 30),
        lambda: line_cells(Footprint(Position(0, 0)), Position(1, 0), 30, 0),
    ],
)
def test_area_queries_reject_invalid_radii_directions_and_widths(call) -> None:
    with pytest.raises(ValueError):
        call()
