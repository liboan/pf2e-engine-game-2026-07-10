"""Bounded terminal coverage for Light point casting and carrier consent."""

from __future__ import annotations

import re
from pathlib import Path
from types import SimpleNamespace

from pf2e.content import ANGELIC_FIRST_CAST_SETUP
from pf2e.encounter import Encounter
from pf2e.model import LightOrb, Position
from pf2e.terminal import _choose_cast_inputs, build_action_menu, render_inspection, run_terminal

from terminal_test_helpers import BoundedTranscript


def _menu_choice(menu: str, label: str) -> str:
    for row in menu.splitlines():
        match = re.match(r"(\d+)\.\s+(.*)", row)
        if match and match.group(2) == label:
            return match.group(1)
    raise AssertionError(f"menu label missing: {label!r}\n{menu}")


def _menu_choice_prefix(menu: str, prefix: str) -> str:
    for row in menu.splitlines():
        match = re.match(r"(\d+)\.\s+(.*)", row)
        if match and match.group(2).startswith(prefix):
            return match.group(1)
    raise AssertionError(f"menu label prefix missing: {prefix!r}\n{menu}")


def test_light_terminal_advertises_canonical_sustain_and_dismiss_controls() -> None:
    menu = build_action_menu(("cast", "sustain_light", "dismiss_light", "end_turn"))

    assert [action_id for action_id, _label in menu] == [
        "inspect",
        "cast",
        "sustain_light",
        "dismiss_light",
        "end_turn",
        "save",
        "load",
        "restart",
        "quit",
    ]


def test_light_input_selects_point_color_and_optional_carrier() -> None:
    spell = SimpleNamespace(
        spell_id="light",
        name="Light",
        traits=("cantrip", "concentrate", "light", "manipulate"),
        action_costs=(2,),
        slots=(),
        target_options=(),
        unavailable_reason=None,
    )
    inspection = SimpleNamespace(
        map_width=7,
        map_height=5,
        actors=(
            SimpleNamespace(actor_id="sorcerer_ally", label="Sorcerer's Ally", position=Position(2, 2)),
            SimpleNamespace(actor_id="guard_dog", label="Guard Dog", position=Position(5, 2)),
        ),
    )
    output: list[str] = []
    inputs = iter(("1", "C3", "amber", "2"))

    selection = _choose_cast_inputs((spell,), inspection, lambda: next(inputs), output.append)

    assert selection == (
        "light",
        None,
        2,
        None,
        None,
        None,
        Position(2, 2),
        "amber",
        "sorcerer_ally",
    )
    transcript = "\n".join(output)
    assert "Optional Light carrier at this point" in transcript
    assert "Attach to Sorcerer's Ally (sorcerer_ally)" in transcript


def test_light_input_rejects_bad_coordinate_once_without_retry_loop() -> None:
    spell = SimpleNamespace(
        spell_id="light",
        name="Light",
        traits=("cantrip",),
        action_costs=(2,),
        slots=(),
        target_options=(),
        unavailable_reason=None,
    )
    inspection = SimpleNamespace(map_width=7, map_height=5, actors=())
    output: list[str] = []

    selection = _choose_cast_inputs(
        (spell,), inspection, iter(("1", "H3")) .__next__, output.append
    )

    assert selection is None
    assert output[-1] == "Choose a square from A1 to G5."


def test_inspection_lists_light_orb_identity_point_and_carrier_location() -> None:
    inspection = SimpleNamespace(
        in_progress=True,
        round_number=1,
        turn_actor_id="sorcerer",
        map_width=7,
        map_height=5,
        actors=(
            SimpleNamespace(
                actor_id="sorcerer",
                label="Angelic Sorcerer",
                team="blue",
                position=Position(1, 2),
                hp=16,
                max_hp=16,
                defeated=False,
                initiative=20,
                actions_remaining=1,
            ),
            SimpleNamespace(
                actor_id="ally",
                label="Sorcerer's Ally",
                team="blue",
                position=Position(2, 2),
                hp=21,
                max_hp=21,
                defeated=False,
                initiative=10,
                actions_remaining=0,
            ),
        ),
        light_orbs=(
            LightOrb(
                stable_id="light:sorcerer:1",
                caster_actor_id="sorcerer",
                rank=1,
                color="amber",
                attached_actor_id="ally",
            ),
        ),
    )

    rendered = render_inspection(inspection)

    assert "Light orbs:" in rendered
    assert "light:sorcerer:1: rank 1 amber; attached to Sorcerer's Ally (ally) at C3" in rendered


def test_terminal_casts_light_saves_and_loads_willingness_choice(tmp_path: Path) -> None:
    save_path = tmp_path / "light-terminal.json"
    state: dict[str, object] = {
        "outputs": BoundedTranscript(),
        "prompt": "",
        "menu": "",
        "choice_block": "",
        "cast": False,
        "saved": False,
        "loaded": False,
    }

    def output(line: str) -> None:
        state["outputs"].append(line)  # type: ignore[union-attr]
        if line.startswith("1. "):
            state["menu"] = line
        if "choice owner:" in line:
            state["choice_block"] = line
        if line.endswith(":") or line.startswith(("Save file [", "Load file [")):
            state["prompt"] = line

    def scripted_input() -> str:
        prompt = str(state["prompt"])
        menu = str(state["menu"])
        choice_block = str(state["choice_block"])
        if prompt == "Choice prompt action:":
            if "willing to carry the Light orb" in choice_block:
                if not state["saved"]:
                    state["saved"] = True
                    return _menu_choice(menu, "Save")
                if not state["loaded"]:
                    state["loaded"] = True
                    return _menu_choice(menu, "Load")
            return _menu_choice(menu, "Resolve this choice")
        if prompt.startswith("Save file [") or prompt.startswith("Load file ["):
            return str(save_path)
        if prompt == "Choice option number:":
            if "willing to carry the Light orb" in choice_block:
                return _menu_choice(menu, "Willing")
            return _menu_choice(menu, "Keep initiative")
        if prompt == "Choice:":
            if not state["cast"]:
                state["cast"] = True
                return _menu_choice(menu, "Cast")
            return _menu_choice(menu, "Quit")
        if prompt == "Spell number:":
            return next(row.split(".", 1)[0] for row in menu.splitlines() if ". Light (" in row)
        if prompt == "Light point (for example C3):":
            return "C3"
        if prompt == "Light color [white]:":
            return "amber"
        if prompt == "Carrier number:":
            return _menu_choice(menu, "Attach to Sorcerer's Ally (sorcerer_ally)")
        raise AssertionError(f"unexpected terminal prompt: {prompt!r}")

    status = run_terminal(
        setup=ANGELIC_FIRST_CAST_SETUP,
        rolls=(20, 1, 1, 20, 1, 1, 1),
        save_path=save_path,
        input_fn=scripted_input,
        output_fn=output,
    )

    transcript = "\n".join(state["outputs"])  # type: ignore[arg-type]
    assert status == 0
    assert state["cast"] is True
    assert state["saved"] is True and state["loaded"] is True
    assert "Angelic Sorcerer commits Light (2 action(s))." in transcript
    assert "Angelic Sorcerer creates a amber Light orb at C3" in transcript
    assert f"Saved encounter to {save_path}." in transcript
    assert f"Loaded encounter from {save_path}." in transcript
    assert "Sorcerer's Ally willingly carries Light orb light:angelic_sorcerer:1." in transcript
    assert "light:angelic_sorcerer:1: rank 1 amber; attached to Sorcerer's Ally (sorcerer_ally) at C3" in transcript


def test_terminal_sustains_light_to_carrier_and_saves_willingness_choice(tmp_path: Path) -> None:
    save_path = tmp_path / "light-sustain-terminal.json"
    state: dict[str, object] = {
        "outputs": BoundedTranscript(),
        "prompt": "",
        "menu": "",
        "choice_block": "",
        "cast": False,
        "sustain": False,
        "saved": False,
        "loaded": False,
    }

    def output(line: str) -> None:
        state["outputs"].append(line)  # type: ignore[union-attr]
        if line.startswith("1. "):
            state["menu"] = line
        if "choice owner:" in line:
            state["choice_block"] = line
        if line.endswith(":") or line.startswith(("Save file [", "Load file [")):
            state["prompt"] = line

    def scripted_input() -> str:
        prompt = str(state["prompt"])
        menu = str(state["menu"])
        choice_block = str(state["choice_block"])
        if prompt == "Choice prompt action:":
            if "willing to carry the Light orb" in choice_block:
                if not state["saved"]:
                    state["saved"] = True
                    return _menu_choice(menu, "Save")
                if not state["loaded"]:
                    state["loaded"] = True
                    return _menu_choice(menu, "Load")
                return _menu_choice(menu, "Resolve this choice")
            return _menu_choice(menu, "Resolve this choice")
        if prompt.startswith("Save file [") or prompt.startswith("Load file ["):
            return str(save_path)
        if prompt == "Choice option number:":
            if "willing to carry the Light orb" in choice_block:
                return _menu_choice(menu, "Willing")
            return _menu_choice(menu, "Keep initiative")
        if prompt == "Choice:":
            if not state["cast"]:
                state["cast"] = True
                return _menu_choice(menu, "Cast")
            if not state["sustain"]:
                state["sustain"] = True
                return _menu_choice(menu, "Sustain Light")
            return _menu_choice(menu, "Quit")
        if prompt == "Spell number:":
            return next(row.split(".", 1)[0] for row in menu.splitlines() if ". Light (" in row)
        if prompt == "Light point (for example C3):":
            return "A3"
        if prompt == "Light color [white]:":
            return ""
        if prompt == "Light orb to Sustain:":
            return _menu_choice_prefix(menu, "light:angelic_sorcerer:1")
        if prompt == "Sustain point (press Enter to keep current point or detach carrier):":
            return "C3"
        if prompt == "Carrier number:":
            return _menu_choice(menu, "Attach to Sorcerer's Ally (sorcerer_ally)")
        raise AssertionError(f"unexpected terminal prompt: {prompt!r}")

    status = run_terminal(
        setup=ANGELIC_FIRST_CAST_SETUP,
        rolls=(20, 1, 1, 20, 1, 1, 1),
        save_path=save_path,
        input_fn=scripted_input,
        output_fn=output,
    )

    transcript = "\n".join(state["outputs"])  # type: ignore[arg-type]
    assert status == 0
    assert state["cast"] is True and state["sustain"] is True
    assert state["saved"] is True and state["loaded"] is True
    assert "Angelic Sorcerer commits Light (2 action(s))." in transcript
    assert "Angelic Sorcerer sustains Light orb light:angelic_sorcerer:1 to C3." in transcript
    assert "Sorcerer's Ally willingly carries Light orb light:angelic_sorcerer:1." in transcript
    assert f"Saved encounter to {save_path}." in transcript
    assert f"Loaded encounter from {save_path}." in transcript
    assert "Angelic Sorcerer (blue) — HP 16/16; 0 actions" in transcript


def test_terminal_dismisses_selected_owned_light_orb() -> None:
    state: dict[str, object] = {
        "outputs": BoundedTranscript(),
        "prompt": "",
        "menu": "",
        "inspection": "",
        "cast": False,
        "dismiss": False,
    }

    def output(line: str) -> None:
        state["outputs"].append(line)  # type: ignore[union-attr]
        if line.startswith("1. "):
            state["menu"] = line
        if line.startswith("Round "):
            state["inspection"] = line
        if line.endswith(":"):
            state["prompt"] = line

    def active_actor() -> str:
        match = re.match(r"Round \d+ · ([^(]+)", str(state["inspection"]).splitlines()[0])
        return match.group(1).strip() if match else ""

    def scripted_input() -> str:
        prompt = str(state["prompt"])
        menu = str(state["menu"])
        if prompt == "Choice prompt action:":
            return _menu_choice(menu, "Resolve this choice")
        if prompt == "Choice option number:":
            return _menu_choice(menu, "Keep initiative")
        if prompt == "Choice:":
            if active_actor() == "Angelic Sorcerer":
                if not state["cast"]:
                    state["cast"] = True
                    return _menu_choice(menu, "Cast")
                if not state["dismiss"]:
                    state["dismiss"] = True
                    return _menu_choice(menu, "Dismiss Light")
                return _menu_choice(menu, "Quit")
            return _menu_choice(menu, "End Turn")
        if prompt == "Spell number:":
            return next(row.split(".", 1)[0] for row in menu.splitlines() if ". Light (" in row)
        if prompt == "Light point (for example C3):":
            return "A3"
        if prompt == "Light color [white]:":
            return ""
        if prompt == "Light orb to Dismiss:":
            return _menu_choice_prefix(menu, "light:angelic_sorcerer:1")
        raise AssertionError(f"unexpected terminal prompt: {prompt!r}")

    status = run_terminal(
        setup=ANGELIC_FIRST_CAST_SETUP,
        rolls=(20, 1, 1, 20, 1, 1, 1),
        input_fn=scripted_input,
        output_fn=output,
    )

    transcript = "\n".join(state["outputs"])  # type: ignore[arg-type]
    assert status == 0
    assert state["cast"] is True and state["dismiss"] is True
    assert "Angelic Sorcerer dismisses Light orb light:angelic_sorcerer:1." in transcript
    assert "Light orbs:" not in str(state["inspection"])


def test_terminal_selects_owned_orb_for_fifth_light_replacement() -> None:
    state: dict[str, object] = {
        "outputs": BoundedTranscript(),
        "prompt": "",
        "menu": "",
        "choice_block": "",
        "inspection": "",
        "cast_count": 0,
    }
    points = ("A3", "D3", "E3", "G3", "G2")

    def output(line: str) -> None:
        state["outputs"].append(line)  # type: ignore[union-attr]
        if line.startswith("1. "):
            state["menu"] = line
        if line.startswith("Round "):
            state["inspection"] = line
        if "choice owner:" in line:
            state["choice_block"] = line
        if line.endswith(":"):
            state["prompt"] = line

    def active_actor() -> str:
        match = re.match(r"Round \d+ · ([^(]+)", str(state["inspection"]).splitlines()[0])
        return match.group(1).strip() if match else ""

    def scripted_input() -> str:
        prompt = str(state["prompt"])
        menu = str(state["menu"])
        if prompt == "Choice prompt action:":
            return _menu_choice(menu, "Resolve this choice")
        if prompt == "Choice option number:":
            return _menu_choice(menu, "Keep initiative")
        if prompt == "Choice:":
            if active_actor() == "Angelic Sorcerer":
                if (
                    "3 actions" in str(state["inspection"]).splitlines()[0]
                    and "Cast" in menu
                    and int(state["cast_count"]) < 5
                ):
                    state["cast_count"] = int(state["cast_count"]) + 1
                    return _menu_choice(menu, "Cast")
            if int(state["cast_count"]) >= 5:
                return _menu_choice(menu, "Quit")
            return _menu_choice(menu, "End Turn")
        if prompt == "Spell number:":
            return next(row.split(".", 1)[0] for row in menu.splitlines() if ". Light (" in row)
        if prompt == "Light orb to replace:":
            return _menu_choice_prefix(menu, "light:angelic_sorcerer:1")
        if prompt == "Light point (for example C3):":
            return points[int(state["cast_count"]) - 1]
        if prompt == "Light color [white]:":
            return f"color-{state['cast_count']}"
        raise AssertionError(f"unexpected terminal prompt: {prompt!r}")

    status = run_terminal(
        setup=ANGELIC_FIRST_CAST_SETUP,
        rolls=(20, 1, 1, 20, 1, 1, 1) * 30,
        input_fn=scripted_input,
        output_fn=output,
    )

    transcript = "\n".join(state["outputs"])  # type: ignore[arg-type]
    final_inspection = str(state["inspection"])
    assert status == 0
    assert state["cast_count"] == 5
    assert transcript.count("Angelic Sorcerer commits Light (2 action(s)).") == 5
    assert "Four active Light orbs are present; choose the owned orb to replace" in transcript
    assert "light:angelic_sorcerer:5" in transcript
    assert all(
        f"light:angelic_sorcerer:{orb_number}:" in final_inspection
        for orb_number in (2, 3, 4, 5)
    )
    assert "light:angelic_sorcerer:1:" not in final_inspection
