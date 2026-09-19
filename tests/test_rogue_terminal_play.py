"""Numbered terminal play for the admitted Thief Rogue encounter."""

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
    raise AssertionError(f"Menu label missing: {label!r} in {menu!r}")


def test_terminal_thief_completes_deception_surprise_nimble_and_later_round(
    tmp_path: Path,
) -> None:
    """A bounded numbered route saves and loads the defender-owned Nimble choice."""
    save_path = tmp_path / "rogue-terminal-nimble.json"
    transcript = BoundedTranscript()
    state = {
        "menu": "",
        "prompt": "",
        "choice_block": "",
        "target_context": "",
        "phase": "rogue_first",
        "saved": False,
        "loaded": False,
        "unexpected": [],
    }

    def output(line: str) -> None:
        transcript.append(line)
        if "choice owner:" in line:
            state["choice_block"] = line
        if line.startswith("1. "):
            state["menu"] = line
        if line in {"Shortsword target:", "Jaws target:"}:
            state["target_context"] = line
        if line.endswith(":"):
            state["prompt"] = line
        elif line.startswith(("Save file [", "Load file [")):
            state["prompt"] = line

    def choose(label: str, *, prefix: bool = False) -> str:
        return _menu_number(state["menu"], label, prefix=prefix)

    def scripted_input() -> str:
        prompt = state["prompt"]
        choice_block = state["choice_block"]

        if prompt == "Choice prompt action:":
            if "Nimble Dodge" in choice_block:
                if not state["saved"]:
                    return choose("Save")
                if not state["loaded"]:
                    return choose("Load")
            return choose("Resolve this choice")

        if prompt == "Choice option number:":
            if "Nimble Dodge" in choice_block:
                return choose("Use Nimble Dodge (+2 AC)")
            if "initiative" in choice_block:
                return choose("Keep initiative")
            if "Strike check" in choice_block:
                return choose("Keep result")
            state["unexpected"].append(f"Unknown pending choice: {choice_block!r}")
            raise EOFError

        if prompt.startswith("Save file ["):
            state["saved"] = True
            return str(save_path)
        if prompt.startswith("Load file ["):
            state["loaded"] = True
            return str(save_path)

        if prompt == "Choice:":
            phase = state["phase"]
            if phase == "rogue_first":
                state["phase"] = "rogue_end"
                return choose("Strike")
            if phase == "rogue_end":
                state["phase"] = "dog_strike"
                return choose("End Turn")
            if phase == "dog_strike":
                state["phase"] = "dog_strike_input"
                return choose("Strike")
            if phase == "dog_end":
                state["phase"] = "rogue_second"
                return choose("End Turn")
            if phase == "rogue_second":
                state["phase"] = "finished"
                return choose("Strike")
            if phase == "finished":
                return choose("Quit")
            state["unexpected"].append(f"Unknown action phase: {phase!r}")
            raise EOFError

        if prompt == "Weapon / attack number:":
            attack = "Jaws" if state["phase"] == "dog_strike_input" else "Shortsword"
            return choose(attack, prefix=True)
        if prompt == "Target number:":
            target = "Guard Dog" if state["target_context"] == "Shortsword target:" else "Thief Rogue"
            return choose(target, prefix=True)
        if prompt == "Damage type:":
            return choose("Piercing")
        if prompt == "Damage intent:":
            if state["phase"] == "dog_strike_input":
                state["phase"] = "dog_end"
            return choose("Use attack default", prefix=True)

        state["unexpected"].append(f"Unexpected prompt: {prompt!r}")
        raise EOFError

    result = run_terminal(
        setup=get_setup("rogue_thief_vs_guard_dog"),
        rolls=(20, 1, 12, 1, 1, 1, 12, 1),
        save_path=save_path,
        input_fn=scripted_input,
        output_fn=output,
    )

    rendered = "\n".join(transcript)
    assert result == 0
    assert state["unexpected"] == [], rendered
    assert state["phase"] == "finished"
    assert state["saved"] and state["loaded"]
    assert "Initiative: Deception (observed social confrontation)." in rendered
    assert "rogue_sneak_attack" in rendered
    assert "Saved encounter to" in rendered
    assert "Loaded encounter from" in rendered
    assert "Thief Rogue uses Nimble Dodge; +2 circumstance AC against this attack." in rendered
    assert "Attack: d20 12 + 7 = 19 vs AC 15; success." in rendered
    assert "Guard Dog is defeated." in rendered
