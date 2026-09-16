from __future__ import annotations

import re
from pathlib import Path

import pytest

from pf2e.content import get_setup
from pf2e.encounter import Encounter
from pf2e.terminal import run_terminal
from terminal_test_helpers import BoundedTranscript


def _labels(menu: str) -> tuple[str, ...]:
    return tuple(
        match.group(1)
        for row in menu.splitlines()
        if (match := re.match(r"\d+\.\s+(.*)", row))
    )


def _number(menu: str, label: str, *, contains: bool = False) -> str:
    for index, candidate in enumerate(_labels(menu), 1):
        matches = label.casefold() in candidate.casefold() if contains else candidate == label
        if matches:
            return str(index)
    raise EOFError(f"Menu label missing: {label!r} in {menu!r}")


def _actor_line(inspection: str, label: str, team: str) -> str:
    prefix = f"{label} ({team}) —"
    return next(line for line in inspection.splitlines() if line.startswith(prefix))


@pytest.mark.parametrize("response", ["block", "decline"])
def test_terminal_saves_and_resolves_the_real_shield_block_choice(
    tmp_path: Path,
    response: str,
) -> None:
    setup = get_setup("steel_shield_test")
    rolls = (20, 1, 5, 20, 4, 20, 8, 8)
    initial = Encounter.start(setup=setup, rolls=rolls).inspect()
    shield_fighter = next(actor for actor in initial.actors if actor.shields)
    guard_dog = next(actor for actor in initial.actors if actor.team != shield_fighter.team)
    save_path = tmp_path / f"shield-block-{response}.json"

    state: dict[str, object] = {
        "menu": "",
        "prompt": "",
        "inspection": "",
        "inspection_after_raise": "",
        "inspection_after_choice": "",
        "choice_block": "",
        "shield_choice_block": "",
        "did_raise": False,
        "did_attack": False,
        "did_finish_strike": False,
        "choice_resolved": False,
        "saved": False,
        "loaded": False,
        "save_stage": 0,
        "unexpected": [],
    }
    transcript = BoundedTranscript()

    def output(line: str) -> None:
        transcript.append(line)
        if line.startswith("Round ") and "\nMap:" in line:
            state["inspection"] = line
            if (
                state["did_raise"]
                and not state["did_attack"]
                and not state["inspection_after_raise"]
            ):
                state["inspection_after_raise"] = line
            if state["choice_resolved"] and not state["inspection_after_choice"]:
                state["inspection_after_choice"] = line
        if "choice owner:" in line:
            state["choice_block"] = line
            if "Shield Block" in line:
                state["shield_choice_block"] = line
        if line.startswith("1. "):
            state["menu"] = line
        if line.endswith(":") or line.startswith(("Save file [", "Load file [")):
            state["prompt"] = line

    def choose_shield_response() -> str:
        menu = str(state["menu"])
        wanted = "block" if response == "block" else "decline"
        return _number(menu, wanted, contains=True)

    def scripted_input() -> str:
        prompt = str(state["prompt"])
        menu = str(state["menu"])
        choice_block = str(state["choice_block"])
        is_shield_block = "Shield Block" in choice_block and "choice owner:" in choice_block

        if prompt == "Choice prompt action:":
            if is_shield_block and state["save_stage"] == 0:
                state["save_stage"] = 1
                return _number(menu, "Save")
            if is_shield_block and state["save_stage"] == 1:
                state["save_stage"] = 2
                state["saved"] = True
                return _number(menu, "Load")
            return _number(menu, "Resolve this choice")

        if prompt == "Choice option number:":
            if is_shield_block:
                selected = choose_shield_response()
                state["choice_resolved"] = True
                return selected
            for label in ("Keep initiative", "Keep result"):
                try:
                    return _number(menu, label, contains=True)
                except EOFError:
                    pass
            return "1"

        if prompt.startswith(("Save file [", "Load file [")):
            if prompt.startswith("Load file ["):
                state["loaded"] = True
            return str(save_path)

        if prompt == "Choice:":
            if not state["did_raise"] and "Raise a Shield" in _labels(menu):
                state["did_raise"] = True
                return _number(menu, "Raise a Shield")
            headline = str(state["inspection"]).splitlines()[0]
            active = re.match(r"Round \d+ · ([^(]+)", headline)
            active_label = active.group(1).strip() if active else ""
            if active_label == guard_dog.label and not state["did_attack"]:
                state["did_attack"] = True
                return _number(menu, "Strike")
            if state["choice_resolved"]:
                if active_label == guard_dog.label:
                    return _number(menu, "End Turn")
                if not active_label:
                    return _number(menu, "Quit")
                if "Strike" in _labels(menu) and not state["did_finish_strike"]:
                    state["did_finish_strike"] = True
                    return _number(menu, "Strike")
            if not state["did_raise"]:
                state["unexpected"].append(f"Shield action was not offered: {menu!r}")
                raise EOFError
            if "End Turn" in _labels(menu):
                return _number(menu, "End Turn")
            return _number(menu, "Quit")

        if prompt == "Weapon / attack number:":
            return "1"
        if prompt == "Target number:":
            target_id = (
                guard_dog.actor_id
                if state["choice_resolved"] and state["did_finish_strike"]
                else shield_fighter.actor_id
            )
            return _number(menu, f"({target_id})", contains=True)
        if prompt == "Damage type:":
            for damage_type in ("Bludgeoning", "Piercing", "Slashing"):
                try:
                    return _number(menu, damage_type, contains=True)
                except EOFError:
                    continue
            return "1"
        if prompt == "Damage intent:":
            return "1"

        state["unexpected"].append(f"Unexpected prompt: {prompt!r}")
        raise EOFError

    status = run_terminal(
        setup=setup,
        rolls=rolls,
        save_path=save_path,
        input_fn=scripted_input,
        output_fn=output,
    )

    rendered = "\n".join(transcript)
    before_line = _actor_line(
        str(state["inspection_after_raise"]), shield_fighter.label, shield_fighter.team
    )
    after_line = _actor_line(
        str(state["inspection_after_choice"]), shield_fighter.label, shield_fighter.team
    )
    before_hp = int(re.search(r"HP (\d+)/", before_line).group(1))
    after_hp = int(re.search(r"HP (\d+)/", after_line).group(1))
    before_shield_hp = int(re.search(r"Steel Shield \(HP (\d+)/", before_line).group(1))
    after_shield_hp = int(re.search(r"Steel Shield \(HP (\d+)/", after_line).group(1))

    assert status == 0
    assert state["unexpected"] == []
    assert state["did_raise"] and state["did_attack"]
    assert state["did_finish_strike"]
    assert state["saved"] and state["loaded"]
    assert "Saved encounter to" in rendered and "Loaded encounter from" in rendered
    assert "Round 1 · Shield Fighter (blue)" in str(state["inspection_after_raise"])
    assert "Steel Shield (HP 20/20; raised; intact; AC +2)" in before_line
    assert "shield_fighter:steel_shield" not in str(state["inspection_after_raise"])
    assert "Shield Fighter equipment: held longsword, Steel Shield · worn breastplate" in str(
        state["inspection_after_raise"]
    )
    assert "choice owner: Shield Fighter" in str(state["shield_choice_block"])
    assert "Block" in str(state["shield_choice_block"])
    assert "Decline" in str(state["shield_choice_block"])
    assert "choice_id" not in str(state["shield_choice_block"])
    assert "instance_id" not in str(state["shield_choice_block"])
    assert after_hp < before_hp, f"before={before_line!r}; after={after_line!r}"

    if response == "block":
        assert after_shield_hp < before_shield_hp
        assert "reaction spent" in after_line
        assert "Shield Block" in rendered
    else:
        assert after_shield_hp == before_shield_hp
        assert "reaction ready" in after_line
    assert "Encounter finished." in rendered
    assert f"{guard_dog.label} ({guard_dog.team}) — HP 0/8" in str(state["inspection"])
