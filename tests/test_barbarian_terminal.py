from __future__ import annotations

import re
from pathlib import Path

from pf2e.content import get_setup
from pf2e.terminal import run_terminal
from terminal_test_helpers import BoundedTranscript


def _menu_number(menu: str, label: str, *, prefix: bool = False) -> str:
    for row in menu.splitlines():
        match = re.match(r"(\d+)\.\s+(.*)", row)
        if match and (match.group(2).startswith(label) if prefix else match.group(2) == label):
            return match.group(1)
    raise EOFError(f"Menu label missing: {label!r} in {menu!r}")


def _menu_labels(menu: str) -> tuple[str, ...]:
    return tuple(
        match.group(1)
        for row in menu.splitlines()
        if (match := re.match(r"\d+\.\s+(.*)", row))
    )


def test_bear_barbarian_terminal_rages_and_resumes_saved_demoralize_choice(
    tmp_path: Path,
) -> None:
    setup = get_setup("barbarian_rage_test")
    save_path = tmp_path / "barbarian-demoralize-choice.json"
    state = {
        "menu": "",
        "prompt": "",
        "inspection": "",
        "rage_turn": "",
        "choice_block": "",
        "pending_save_stage": 0,
        "saved": False,
        "loaded": False,
        "did_rage": False,
        "did_demoralize": False,
        "unexpected": [],
    }
    transcript = BoundedTranscript()

    def output(line: str) -> None:
        transcript.append(line)
        if line.startswith("Round ") and "\nMap:" in line:
            state["inspection"] = line
            if "Rage active" in line and not state["rage_turn"]:
                state["rage_turn"] = line
        if "choice owner:" in line:
            state["choice_block"] = line
        if line.startswith("1. "):
            state["menu"] = line
        if line.endswith(":") or line.startswith(("Save file [", "Load file [")):
            state["prompt"] = line

    def active_actor() -> str:
        match = re.match(r"Round \d+ · ([^(]+)", state["inspection"].splitlines()[0])
        return match.group(1).strip() if match else ""

    def choose(label: str, *, prefix: bool = False) -> str:
        return _menu_number(state["menu"], label, prefix=prefix)

    def scripted_input() -> str:
        prompt = state["prompt"]
        choice_block = state["choice_block"]
        if prompt == "Choice prompt action:":
            if "may spend a Hero Point to reroll this check" in choice_block:
                if not state["saved"]:
                    stage = state["pending_save_stage"]
                    state["pending_save_stage"] = stage + 1
                    if stage == 0:
                        return choose("Save")
                    if stage == 1:
                        state["saved"] = True
                        state["loaded"] = True
                        return choose("Load")
            return choose("Resolve this choice")
        if prompt == "Choice option number:":
            if "may spend a Hero Point to reroll this check" in choice_block:
                return choose("Keep the current result")
            if "quick-tempered" in choice_block.casefold():
                labels = _menu_labels(state["menu"])
                for index, label in enumerate(labels, 1):
                    if any(word in label.casefold() for word in ("later", "decline", "skip", "not now", "don't rage")):
                        return str(index)
                return str(len(labels))
            for label in ("Keep initiative", "Keep result"):
                try:
                    return choose(label, prefix=True)
                except EOFError:
                    continue
            return "1"
        if prompt.startswith("Save file [") or prompt.startswith("Load file ["):
            return str(save_path)
        if prompt == "Choice:":
            actor = active_actor()
            if actor == "Barbarian":
                if not state["did_rage"]:
                    state["did_rage"] = True
                    return choose("Rage")
                if not state["did_demoralize"] and "Rage active" in state["inspection"]:
                    state["did_demoralize"] = True
                    return choose("Demoralize")
                return choose("Quit")
            return choose("End Turn")
        if prompt == "Target number:":
            return choose("Test Guard", prefix=True)
        state["unexpected"].append(f"Unexpected prompt: {prompt!r}")
        raise EOFError

    result = run_terminal(
        setup=setup,
        rolls=(20, 1, 10),
        save_path=save_path,
        input_fn=scripted_input,
        output_fn=output,
    )

    rendered = "\n".join(transcript)
    assert result == 0
    assert state["unexpected"] == []
    assert state["did_rage"]
    assert "Rage active (normal damage)" in rendered
    assert "temporary HP" in rendered and "(from Rage)" in rendered
    assert "2 actions" in state["rage_turn"]
    assert "rage:barbarian_test" not in rendered
    assert "Barbarian attempts Demoralize against Test Guard" in rendered
    assert state["did_demoralize"]
    assert state["pending_save_stage"] == 2
    assert state["saved"] and state["loaded"]
    assert "Saved encounter to" in rendered and "Loaded encounter from" in rendered


def test_quick_tempered_uses_the_live_initiative_offer_and_keeps_turn_actions(
    tmp_path: Path,
) -> None:
    setup = get_setup("barbarian_rage_test")
    save_path = tmp_path / "barbarian-quick-tempered.json"
    state = {
        "menu": "",
        "prompt": "",
        "inspection": "",
        "choice_block": "",
        "saw_quick_tempered": False,
        "accepted": False,
        "barbarian_turn": "",
        "unexpected": [],
    }
    transcript = BoundedTranscript()

    def output(line: str) -> None:
        transcript.append(line)
        if line.startswith("Round ") and "\nMap:" in line:
            state["inspection"] = line
        if "choice owner:" in line:
            state["choice_block"] = line
            if "Quick-Tempered" in line:
                state["saw_quick_tempered"] = True
        if line.startswith("1. "):
            state["menu"] = line
        if line.endswith(":") or line.startswith(("Save file [", "Load file [")):
            state["prompt"] = line

    def active_actor() -> str:
        match = re.match(r"Round \d+ · ([^(]+)", state["inspection"].splitlines()[0])
        return match.group(1).strip() if match else ""

    def choose(label: str, *, prefix: bool = False) -> str:
        return _menu_number(state["menu"], label, prefix=prefix)

    def scripted_input() -> str:
        prompt = state["prompt"]
        choice_block = state["choice_block"]
        if prompt == "Choice prompt action:":
            return choose("Resolve this choice")
        if prompt == "Choice option number:":
            if "Quick-Tempered" in choice_block:
                state["accepted"] = True
                return choose("Use Quick-Tempered")
            if "may keep initiative or spend 1 Hero Point to reroll" in choice_block:
                return choose("Keep initiative")
            return "1"
        if prompt == "Choice:":
            if active_actor() == "Barbarian":
                if "Rage active (normal damage)" in state["inspection"]:
                    state["barbarian_turn"] = state["inspection"]
                    return choose("Quit")
                state["unexpected"].append("Barbarian turn began without Quick-Tempered Rage.")
                return choose("Quit")
            return choose("End Turn")
        state["unexpected"].append(f"Unexpected prompt: {prompt!r}")
        raise EOFError

    result = run_terminal(
        setup=setup,
        rolls=(20, 1),
        save_path=save_path,
        input_fn=scripted_input,
        output_fn=output,
    )

    rendered = "\n".join(transcript)
    assert result == 0
    assert state["unexpected"] == []
    assert state["accepted"]
    assert state["saw_quick_tempered"]
    assert "Rage active (normal damage)" in state["barbarian_turn"]
    assert "temporary HP 4 (from Rage)" in state["barbarian_turn"]
    assert "3 actions" in state["barbarian_turn"]
    assert "rage:barbarian_test" not in rendered
    assert "Use Quick-Tempered" in rendered
