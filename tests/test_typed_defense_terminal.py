from __future__ import annotations

import re
from pathlib import Path

from pf2e.content import get_setup
from pf2e.terminal import run_terminal
from terminal_test_helpers import BoundedTranscript


def _menu_number(menu: str, label: str, *, prefix: bool = False) -> str:
    for row in menu.splitlines():
        match = re.match(r"(\d+)\.\s+(.*)", row)
        if match and (
            match.group(2).casefold().startswith(label.casefold())
            if prefix
            else match.group(2).casefold() == label.casefold()
        ):
            return match.group(1)
    raise EOFError(f"Menu label missing: {label!r} in {menu!r}")


def test_diabolic_dragon_terminal_saves_and_resolves_defender_damage_choice(
    tmp_path: Path,
) -> None:
    setup = get_setup("typed_defenses_diabolic_dragon_test")
    save_path = tmp_path / "typed-defense-terminal.json"
    state = {
        "menu": "",
        "prompt": "",
        "inspection": "",
        "choice_block": "",
        "transcript": BoundedTranscript(),
        "defense_save_load_stage": 0,
        "rage_action_selected": False,
        "rage_mode_selected": False,
        "strike_selected": False,
        "defense_option_selected": False,
        "unexpected": [],
    }

    def output(line: str) -> None:
        state["transcript"].append(line)
        if line.startswith("Round ") and "\nMap:" in line:
            state["inspection"] = line
        if "choice owner:" in line:
            state["choice_block"] = line
        if line.startswith("1. "):
            state["menu"] = line
        if line.endswith(":") or line.startswith(("Save file [", "Load file [")):
            state["prompt"] = line

    def choose(label: str, *, prefix: bool = False) -> str:
        return _menu_number(str(state["menu"]), label, prefix=prefix)

    def active_actor() -> str:
        first_line = str(state["inspection"]).splitlines()[0]
        match = re.match(r"Round \d+ · ([^(]+)", first_line)
        return match.group(1).strip() if match else ""

    def scripted_input() -> str:
        prompt = str(state["prompt"])
        choice_block = str(state["choice_block"])
        is_defense_choice = "chooses which damage type" in choice_block

        if prompt == "Choice prompt action:":
            if is_defense_choice:
                stage = int(state["defense_save_load_stage"])
                state["defense_save_load_stage"] = stage + 1
                return choose(("Save", "Load", "Resolve this choice")[min(stage, 2)])
            return choose("Resolve this choice")
        if prompt == "Choice option number:":
            labels = tuple(
                match.group(1)
                for row in str(state["menu"]).splitlines()
                if (match := re.match(r"\d+\.\s+(.*)", row))
            )
            if is_defense_choice:
                state["defense_option_selected"] = True
                return choose("Resist Fire")
            if "may keep initiative or spend 1 Hero Point to reroll" in choice_block:
                return choose("Keep initiative")
            if "Use Quick-Tempered" in labels:
                return choose("Decline")
            if "Choose how this Rage changes its damage." in choice_block:
                state["rage_mode_selected"] = True
                return choose("Draconic Rage", prefix=True)
            if "may keep this Strike check" in choice_block:
                return choose("Keep", prefix=True)
            raise EOFError(f"No scripted choice for {choice_block!r}: {labels!r}")

        if prompt.startswith(("Save file [", "Load file [")):
            return str(save_path)
        if prompt == "Choice:":
            if active_actor() == "Diabolic Dragon Barbarian":
                if not state["rage_action_selected"]:
                    state["rage_action_selected"] = True
                    return choose("Rage")
                if not state["strike_selected"]:
                    state["strike_selected"] = True
                    return choose("Strike")
                return choose("Quit")
            return choose("Quit")
        if prompt == "Weapon / attack number:":
            return choose("Longsword", prefix=True)
        if prompt == "Target number:":
            return choose("Waystone Sentinel", prefix=True)
        if prompt == "Damage type:":
            return choose("Slashing")
        if prompt == "Damage intent:":
            return choose("Use attack default", prefix=True)

        state["unexpected"].append(f"Unexpected input prompt: {prompt!r}")
        raise EOFError

    result = run_terminal(
        setup=setup,
        rolls=(20, 1, 20, 8),
        save_path=save_path,
        input_fn=scripted_input,
        output_fn=output,
    )

    transcript = "\n".join(state["transcript"])
    defense_prompt = str(state["choice_block"])
    assert result == 0
    assert state["unexpected"] == []
    assert state["rage_action_selected"] and state["rage_mode_selected"]
    assert state["strike_selected"]
    assert "Draconic Rage (fire)" in transcript
    assert "Fixed local encounter" in transcript
    assert "S1 prototype" not in transcript
    assert state["defense_save_load_stage"] == 3
    assert state["defense_option_selected"]
    assert "choice owner: Waystone Sentinel" in transcript
    assert "Waystone Sentinel chooses which damage type" in transcript
    assert "24 slashing" in transcript and "8 fire" in transcript
    assert "Resist slashing" in transcript and "Resist fire" in transcript
    assert f"Saved encounter to {save_path}." in transcript
    assert f"Loaded encounter from {save_path}." in transcript
    assert "Waystone Sentinel chooses fire" in transcript
    assert "damage after defenses: slashing 27, fire 6; 33 total (was 32 before defenses)" in transcript
    assert "target defeated" in transcript
    assert "Encounter finished." in transcript
    assert "Waystone Sentinel (red) — HP 0/30" in transcript
    assert "Waystone Sentinel" in defense_prompt
