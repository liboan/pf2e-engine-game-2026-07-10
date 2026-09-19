from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from pf2e.content import S1_SETUP
from pf2e.encounter import Encounter
from pf2e.model import Position, Step
from pf2e.terminal import (
    MAIN_MENU,
    format_coordinate,
    format_action_result,
    parse_coordinate,
    parse_menu_choice,
    parse_path,
    render_actor_lines,
    render_grid,
    render_inspection,
    render_menu,
    render_support_summary,
    run_terminal,
)


def test_main_menu_has_the_nine_required_numbered_controls() -> None:
    rendered = render_menu()

    assert MAIN_MENU == (
        "Inspect",
        "Stride",
        "Step",
        "Strike",
        "End Turn",
        "Save",
        "Load",
        "Restart",
        "Quit",
    )
    assert rendered.startswith("1. Inspect\n2. Stride\n3. Step")
    assert rendered.endswith("9. Quit")
    assert parse_menu_choice(" 9 ") == 9


@pytest.mark.parametrize("value", ["", "one", "0", "10", "1.5"])
def test_menu_choice_rejects_malformed_or_out_of_range_input(value: str) -> None:
    with pytest.raises(ValueError, match="Enter a number"):
        parse_menu_choice(value)


@pytest.mark.parametrize(
    ("text", "expected"),
    [("A1", (0, 0)), ("c2", (2, 1)), (" G5 ", (6, 4))],
)
def test_coordinate_round_trip(text: str, expected: tuple[int, int]) -> None:
    assert parse_coordinate(text) == expected
    assert format_coordinate(expected) == text.strip().upper()


@pytest.mark.parametrize("text", ["", "A0", "H1", "A6", "1A", "AA1", "C 2"])
def test_coordinate_rejects_malformed_or_out_of_bounds_input(text: str) -> None:
    with pytest.raises(ValueError):
        parse_coordinate(text)


def test_path_parser_accepts_only_the_explicit_squares_entered() -> None:
    assert parse_path("B2, C2 D3") == [(1, 1), (2, 1), (3, 2)]
    with pytest.raises(ValueError, match="one or more squares"):
        parse_path("   ")


def test_grid_and_roster_show_labels_and_current_actor_facts() -> None:
    board = render_grid(
        7,
        5,
        {"synthetic-one": (1, 1), "synthetic-two": (5, 3)},
        {"synthetic-one": "A", "synthetic-two": "B"},
    )
    actors = render_actor_lines(
        [
            {
                "name": "Synthetic Actor A",
                "team": "Blue",
                "hp": 11,
                "max_hp": 14,
                "conditions": [],
            },
            {
                "name": "Synthetic Actor B",
                "team": "Red",
                "hp": 9,
                "max_hp": 12,
                "conditions": ["off-guard"],
            },
        ]
    )

    assert "A B C D E F G" in board
    assert "2  . A . . . . ." in board
    assert "4  . . . . . B ." in board
    assert "Synthetic Actor A (Blue) — HP 11/14; conditions: none" in actors
    assert "Synthetic Actor B (Red) — HP 9/12; conditions: off-guard" in actors


def test_support_summary_does_not_claim_published_or_pc_support() -> None:
    summary = render_support_summary()
    assert "synthetic NPC-style" in summary
    assert "not published-creature or PC support" in summary
    assert "PC dying/recovery" in summary


def test_inspection_formats_active_actor_map_and_s1_condition_limit() -> None:
    view = SimpleNamespace(
        in_progress=True,
        round_number=2,
        turn_actor_id="a",
        map_width=7,
        map_height=5,
        actors=(
            SimpleNamespace(
                actor_id="a",
                label="Synthetic NPC A",
                team="blue",
                position=SimpleNamespace(x=1, y=2),
                hp=8,
                max_hp=12,
                defeated=False,
                initiative=19,
                actions_remaining=2,
            ),
            SimpleNamespace(
                actor_id="b",
                label="Synthetic NPC B",
                team="red",
                position=SimpleNamespace(x=5, y=2),
                hp=12,
                max_hp=12,
                defeated=False,
                initiative=14,
                actions_remaining=3,
            ),
        ),
    )

    rendered = render_inspection(view)

    assert "Round 2 · Synthetic NPC A (blue) · 2 actions · HP 8/12" in rendered
    assert "Conditions: not modeled in S1." in rendered
    assert "A = Synthetic NPC A (blue)" in rendered
    assert "Synthetic NPC B (red) — HP 12/12; 3 actions; initiative 14" in rendered


def test_engine_result_displays_rule_text_verbatim() -> None:
    result = SimpleNamespace(
        status=SimpleNamespace(value="completed"),
        message="Turn ended. Encounter finished.",
        events=(
            SimpleNamespace(text="Attack: d20 20 + 5 = 25 vs AC 15; critical success."),
            SimpleNamespace(text="Damage: 2d6 + 4 = 16 bludgeoning; target defeated."),
        ),
    )

    assert format_action_result(result) == (
        "Attack: d20 20 + 5 = 25 vs AC 15; critical success.",
        "Damage: 2d6 + 4 = 16 bludgeoning; target defeated.",
        "Turn ended. Encounter finished.",
    )


def _scripted_input(values: list[str]):
    iterator = iter(values)
    return lambda: next(iterator)


def _path_toward_other(actor_id: str) -> str:
    return "C3 D3 E3" if actor_id == "synthetic_a" else "E3 D3 C3"


@pytest.mark.parametrize("alternate", [False, True])
def test_terminal_plays_a_complete_engine_encounter(alternate: bool) -> None:
    initial = Encounter.start(setup=S1_SETUP, seed=7, rolls=(20, 20, 20, 6)).inspect()
    active_id = initial.turn_actor_id
    assert active_id in {"synthetic_a", "synthetic_b"}

    if alternate:
        first_step = "C3" if active_id == "synthetic_a" else "E3"
        second_path = "D3 E3" if active_id == "synthetic_a" else "D3 C3"
        inputs = ["3", first_step, "2", second_path, "4", "1", "9"]
    else:
        inputs = ["2", _path_toward_other(active_id), "4", "1", "9"]

    output: list[str] = []
    status = run_terminal(
        setup=S1_SETUP,
        seed=7,
        rolls=(20, 20, 20, 6),
        input_fn=_scripted_input(inputs),
        output_fn=output.append,
    )

    transcript = "\n".join(output)
    assert status == 0
    assert "critical success" in transcript.lower()
    assert "defeated" in transcript
    assert "Encounter finished." in transcript
    assert "Goodbye." in transcript
    if alternate:
        assert "Step destinations from engine:" in transcript


def test_terminal_malformed_input_does_not_break_scripted_dice_or_state(tmp_path: Path) -> None:
    initial = Encounter.start(setup=S1_SETUP, seed=11, rolls=(20, 20, 20, 6)).inspect()
    actor_id = initial.turn_actor_id
    assert actor_id is not None
    save_file = tmp_path / "invalid-input.json"
    inputs = [
        "not a number",
        "2",
        "A0",
        "2",
        _path_toward_other(actor_id),
        "4",
        "1",
        "6",
        str(save_file),
        "9",
    ]
    output: list[str] = []

    run_terminal(
        setup=S1_SETUP,
        seed=11,
        rolls=(20, 20, 20, 6),
        input_fn=_scripted_input(inputs),
        output_fn=output.append,
    )

    transcript = "\n".join(output)
    assert "Enter a number from 1 to 9." in transcript
    assert "Use a coordinate such as C2." in transcript
    assert "critical success" in transcript.lower()
    assert Encounter.load(save_file).inspect().in_progress is False


def test_terminal_save_load_and_restart_use_the_real_fixture(tmp_path: Path) -> None:
    save_file = tmp_path / "round-trip.json"
    initial = Encounter.start(setup=S1_SETUP, seed=13).inspect()
    active_id = initial.turn_actor_id
    assert active_id is not None
    step_destination = Position(2, 2) if active_id == "synthetic_a" else Position(4, 2)
    expected = Encounter.start(setup=S1_SETUP, seed=13)
    expected.execute(Step(destination=step_destination))
    saved_view = expected.inspect()
    output: list[str] = []

    run_terminal(
        setup=S1_SETUP,
        seed=13,
        save_path=save_file,
        input_fn=_scripted_input(
            [
                "3",
                format_coordinate((step_destination.x, step_destination.y)),
                "6",
                "",
                "5",
                "7",
                "",
                "8",
                "9",
            ]
        ),
        output_fn=output.append,
    )

    assert "Saved encounter to" in "\n".join(output)
    assert "Loaded encounter from" in "\n".join(output)
    assert "Encounter restarted." in "\n".join(output)
    assert Encounter.load(save_file).inspect() == saved_view
    saved_active_actor = next(actor for actor in saved_view.actors if actor.actor_id == active_id)
    initial_active_actor = next(actor for actor in initial.actors if actor.actor_id == active_id)
    assert saved_active_actor.actions_remaining == 2
    assert saved_active_actor.position == step_destination
    assert initial_active_actor.position != step_destination


def test_terminal_save_load_continues_scripted_dice_at_the_saved_position(tmp_path: Path) -> None:
    save_file = tmp_path / "dice-continuation.json"
    initial = Encounter.start(setup=S1_SETUP, seed=23, rolls=(15, 10, 8, 20, 6)).inspect()
    active_id = initial.turn_actor_id
    assert active_id == "synthetic_a"
    inputs = [
        "2",
        _path_toward_other(active_id),
        "4",
        "1",
        "6",
        str(save_file),
        "5",
        "7",
        str(save_file),
        "4",
        "1",
        "9",
    ]
    output: list[str] = []

    run_terminal(
        setup=S1_SETUP,
        seed=23,
        rolls=(15, 10, 8, 20, 6),
        input_fn=_scripted_input(inputs),
        output_fn=output.append,
    )

    transcript = "\n".join(output).lower()
    restored = Encounter.load(save_file).inspect()
    active_after_load = next(actor for actor in restored.actors if actor.actor_id == active_id)
    assert active_after_load.actions_remaining == 1
    assert active_after_load.hp == 12
    assert "d20 8" in transcript
    assert "d20 20" in transcript
    assert "critical success" in transcript
    assert "defeated" in transcript


def test_terminal_quits_cleanly_on_eof_and_explicit_quit() -> None:
    eof_output: list[str] = []

    def eof() -> str:
        raise EOFError

    assert run_terminal(seed=17, input_fn=eof, output_fn=eof_output.append) == 0
    assert "End of input; quitting." in "\n".join(eof_output)

    quit_output: list[str] = []
    assert run_terminal(
        seed=17,
        input_fn=_scripted_input(["9"]),
        output_fn=quit_output.append,
    ) == 0
    assert "Goodbye." in "\n".join(quit_output)
