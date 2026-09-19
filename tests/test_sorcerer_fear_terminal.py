"""Numbered terminal coverage for the staged Angelic Sorcerer Fear/Flee path."""

from __future__ import annotations

import re
from pathlib import Path

from pf2e.content import ANGELIC_FEAR_SETUP
from pf2e.terminal import build_action_menu, run_terminal


def _menu_choice(menu: str, label: str) -> str:
    for line in menu.splitlines():
        match = re.match(r"(\d+)\.\s+(.*)", line)
        if match and match.group(2) == label:
            return match.group(1)
    raise AssertionError(f"menu label missing: {label!r}\n{menu}")


def test_dynamic_menu_exposes_engine_flee_label_and_global_controls() -> None:
    assert build_action_menu(("flee",)) == (
        ("inspect", "Inspect"),
        ("flee", "Flee"),
        ("save", "Save"),
        ("load", "Load"),
        ("restart", "Restart"),
        ("quit", "Quit"),
    )


def test_terminal_dispatches_flee_and_round_trips_the_saved_position(tmp_path: Path) -> None:
    save_path = tmp_path / "fear-flee-terminal.json"
    state: dict[str, object] = {
        "inspection": "",
        "menu": "",
        "prompt": "",
        "fear_cast": False,
        "flee_count": 0,
        "saved": False,
        "loaded": False,
        "menus": [],
        "output": [],
    }

    def output(line: str) -> None:
        state["output"].append(line)  # type: ignore[union-attr]
        if line.startswith("Round "):
            state["inspection"] = line
        if line.startswith("1. "):
            state["menu"] = line
            state["menus"].append((state["inspection"], line))  # type: ignore[union-attr]
        if line == "Choice:" or line.endswith(":") or line.startswith(("Save file [", "Load file [")):
            state["prompt"] = line

    def scripted_input() -> str:
        prompt = state["prompt"]
        if prompt == "Choice prompt action:":
            return _menu_choice(state["menu"], "Resolve this choice")  # type: ignore[arg-type]
        if prompt == "Choice option number:":
            return "1"
        if prompt.startswith("Save file [") or prompt.startswith("Load file ["):
            return str(save_path)
        if prompt == "Spell number:":
            for line in state["menu"].splitlines():
                match = re.match(r"(\d+)\.\s+(.*)", line)
                if match and match.group(2).startswith("Fear ("):
                    return match.group(1)
            raise AssertionError(f"Fear missing from spell menu:\n{state['menu']}")
        if prompt in {"Casting mode:", "Prepared slot:", "Fear target:"}:
            return "1"
        if prompt == "Target number:":
            return "2"  # Guard Dog; the engine also lists the caster as a target.
        if prompt == "Choice:":
            header = state["inspection"].splitlines()[0]
            active = header.split(" · ", 2)[1].split(" (", 1)[0]
            if active == "Angelic Sorcerer":
                if state["flee_count"] >= 3:
                    return _menu_choice(state["menu"], "Quit")
                next_action = "Cast" if not state["fear_cast"] else "End Turn"
                if not state["fear_cast"]:
                    state["fear_cast"] = True
                return _menu_choice(state["menu"], next_action)
            if active == "Guard Dog":
                flee_count = state["flee_count"]
                if flee_count == 0:
                    state["flee_count"] = 1
                    return _menu_choice(state["menu"], "Flee")
                if not state["saved"]:
                    state["saved"] = True
                    return _menu_choice(state["menu"], "Save")
                if not state["loaded"]:
                    state["loaded"] = True
                    return _menu_choice(state["menu"], "Load")
                state["flee_count"] = flee_count + 1
                return _menu_choice(state["menu"], "Flee")
            return _menu_choice(state["menu"], "Quit")
        raise AssertionError(f"unexpected terminal prompt: {prompt!r}")

    status = run_terminal(
        setup=ANGELIC_FEAR_SETUP,
        rolls=(20, 1, 1),
        save_path=save_path,
        input_fn=scripted_input,
        output_fn=output,
    )

    assert status == 0
    assert state["fear_cast"] is True
    assert state["saved"] is True and state["loaded"] is True
    dog_menus = [
        menu
        for inspection, menu in state["menus"]  # type: ignore[misc]
        if inspection.startswith("Round ") and "· Guard Dog (" in inspection.splitlines()[0]
    ]
    assert dog_menus
    fleeing_menu = next(menu for menu in dog_menus if "2. Flee" in menu)
    assert "Flee" in fleeing_menu
    assert "Strike" not in fleeing_menu
    assert "End Turn" not in fleeing_menu
    transcript = "\n".join(state["output"])  # type: ignore[arg-type]
    assert "is fleeing" in transcript
    assert "finishes moving at E1" in transcript
    assert "cannot move farther" in transcript
    assert "Saved encounter to" in transcript
    assert "Loaded encounter from" in transcript
