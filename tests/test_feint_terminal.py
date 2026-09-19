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


def test_terminal_feint_saves_hero_choice_then_strikes_through_opening(
    tmp_path: Path,
) -> None:
    setup = get_setup("s3_feint_fighter_duel")
    save_path = tmp_path / "feint-hero-choice.json"
    state = {
        "menu": "",
        "prompt": "",
        "inspection": "",
        "choice_block": "",
        "target_context": "",
        "did_feint": False,
        "did_strike": False,
        "pending_save_stage": 0,
        "saved": False,
        "loaded": False,
        "unexpected": [],
    }
    transcript = BoundedTranscript()

    def output(line: str) -> None:
        transcript.append(line)
        if line.startswith("Round ") and "\nMap:" in line:
            state["inspection"] = line
        if "choice owner:" in line:
            state["choice_block"] = line
        if line in {"Feint target:", "Longsword target:"}:
            state["target_context"] = line
        if line.startswith("1. "):
            state["menu"] = line
        if line.endswith(":") or line.startswith(("Save file [", "Load file [")):
            state["prompt"] = line

    def feinter_is_active() -> bool:
        headline = state["inspection"].splitlines()[0]
        return "Fighter M (Deception)" in headline

    def choose(label: str, *, prefix: bool = False) -> str:
        return _menu_number(state["menu"], label, prefix=prefix)

    def scripted_input() -> str:
        prompt = state["prompt"]
        choice_block = state["choice_block"]
        if prompt == "Choice prompt action:":
            if (
                state["did_feint"]
                and "may spend a Hero Point to reroll this check" in choice_block
                and not state["saved"]
            ):
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
            for label in ("Keep initiative", "Keep result"):
                try:
                    return choose(label, prefix=True)
                except EOFError:
                    continue
            state["unexpected"].append(f"Unrecognized choice: {choice_block!r}")
            raise EOFError
        if prompt.startswith("Save file [") or prompt.startswith("Load file ["):
            return str(save_path)
        if prompt == "Choice:":
            if feinter_is_active():
                if not state["did_feint"]:
                    state["did_feint"] = True
                    return choose("Feint")
                if not state["did_strike"]:
                    state["did_strike"] = True
                    return choose("Strike")
            return choose("Quit")
        if prompt == "Weapon / attack number:":
            return choose("Longsword", prefix=True)
        if prompt == "Target number:":
            if state["target_context"] in {"Feint target:", "Longsword target:"}:
                return choose("Fighter M", prefix=True)
        if prompt == "Damage type:":
            return choose("Slashing")
        if prompt == "Damage intent:":
            return choose("Use attack default", prefix=True)
        state["unexpected"].append(f"Unexpected prompt: {prompt!r}")
        raise EOFError

    result = run_terminal(
        setup=setup,
        rolls=(20, 1, 15, 8, 8),
        save_path=save_path,
        input_fn=scripted_input,
        output_fn=output,
    )

    rendered = "\n".join(transcript)
    assert result == 0
    assert state["unexpected"] == []
    assert state["did_feint"] and state["did_strike"]
    assert state["pending_save_stage"] == 2, rendered
    assert state["saved"] and state["loaded"]
    assert "Saved encounter to" in rendered and "Loaded encounter from" in rendered
    assert "Fighter M (Deception) attempts Feint against Fighter M: Success" in rendered
    assert "Fighter M is off-guard to Fighter M (Deception)'s next melee attack this turn." in rendered
    assert "Attack: d20 8 + 9 = 17 vs AC 16; success." in rendered
