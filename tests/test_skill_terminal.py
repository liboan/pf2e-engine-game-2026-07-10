from __future__ import annotations

import re
from pathlib import Path
from types import SimpleNamespace

from pf2e.content import get_setup
from pf2e.model import HealthMode, Position
from pf2e.terminal import _choose_escape_inputs, build_action_menu, render_inspection, run_terminal
from terminal_test_helpers import BoundedTranscript


def _menu_number(menu: str, label: str, *, prefix: bool = False) -> str:
    for row in menu.splitlines():
        match = re.match(r"(\d+)\.\s+(.*)", row)
        if match and (match.group(2).startswith(label) if prefix else match.group(2) == label):
            return match.group(1)
    raise EOFError(f"Menu label missing: {label!r} in {menu!r}")


def test_skill_actions_appear_in_numbered_menu_when_engine_offers_them() -> None:
    actions = ("trip", "grapple", "escape", "demoralize")

    menu = build_action_menu(actions)

    assert tuple(label for action_id, label in menu if action_id in actions) == (
        "Trip",
        "Grapple",
        "Escape",
        "Demoralize",
    )
    assert not set(actions) & {action_id for action_id, _ in build_action_menu(("end_turn",))}


def test_inspection_renders_sourced_skill_condition_values() -> None:
    actors = (
        SimpleNamespace(
            actor_id="fighter_a",
            label="Fighter A",
            team="blue",
            position=Position(1, 1),
            hp=20,
            max_hp=20,
            defeated=False,
            initiative=20,
            actions_remaining=3,
            health_mode=HealthMode.PC,
            dying=0,
            wounded=0,
            unconscious=False,
            dead=False,
            prone=False,
            hero_points=1,
            reaction_available=True,
            condition_effects=(),
        ),
        SimpleNamespace(
            actor_id="fighter_b",
            label="Fighter B",
            team="red",
            position=Position(2, 1),
            hp=20,
            max_hp=20,
            defeated=False,
            initiative=10,
            actions_remaining=3,
            health_mode=HealthMode.PC,
            dying=0,
            wounded=0,
            unconscious=False,
            dead=False,
            prone=False,
            hero_points=1,
            reaction_available=True,
            condition_effects=(
                SimpleNamespace(kind="frightened", value=2, source_actor_id="fighter_a"),
                SimpleNamespace(kind="grabbed", value=1, source_actor_id="fighter_a"),
            ),
        ),
    )
    inspection = SimpleNamespace(
        actors=actors,
        turn_actor_id="fighter_a",
        round_number=1,
        map_width=5,
        map_height=3,
        ground_items=(),
    )

    rendered = render_inspection(inspection)

    assert "conditions: frightened 2 (from Fighter A), grabbed (from Fighter A)" in rendered


def test_escape_input_menu_can_select_an_unarmed_check_profile() -> None:
    effect = SimpleNamespace(
        effect_id="grapple:fighter_a:fighter_b",
        kind="grabbed",
        value=1,
        source_actor_id="fighter_a",
    )
    inspection = SimpleNamespace(
        actors=(
            SimpleNamespace(actor_id="fighter_a", label="Fighter A"),
            SimpleNamespace(actor_id="fighter_b", label="Fighter B", condition_effects=(effect,)),
        )
    )
    engine_options = SimpleNamespace(
        actor_id="fighter_b",
        strikes=(SimpleNamespace(name="Fist", attack_id="fist"),),
    )
    answers = iter(("1", "3", "1"))
    output: list[str] = []

    inputs = _choose_escape_inputs(
        inspection,
        engine_options,
        lambda: next(answers),
        output.append,
    )

    assert inputs == ("grapple:fighter_a:fighter_b", "unarmed_attack", "fist")
    assert any("engine verifies" in line for line in output)


def test_terminal_routes_all_four_skill_actions_and_resumes_saved_trip_choice(
    tmp_path: Path,
) -> None:
    setup = get_setup("s2_pc_duel_fixture")
    save_path = tmp_path / "skill-choice.json"
    state = {
        "menu": "",
        "prompt": "",
        "inspection": "",
        "choice_block": "",
        "pending_save_stage": 0,
        "saved": False,
        "loaded": False,
        "did_trip": False,
        "did_grapple": False,
        "did_demoralize": False,
        "did_escape": False,
        "unexpected": [],
    }
    transcript = BoundedTranscript()

    def output(line: str) -> None:
        transcript.append(line)
        if line.startswith("Round ") and "\nMap:" in line:
            state["inspection"] = line
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
                stage = state["pending_save_stage"]
                if not state["saved"]:
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
            for label in ("Keep initiative", "Keep result", "Stay here", "Keep the current result"):
                try:
                    return choose(label, prefix=True)
                except EOFError:
                    continue
            return "1"
        if prompt.startswith("Save file [") or prompt.startswith("Load file ["):
            return str(save_path)
        if prompt == "Choice:":
            actor = active_actor()
            if actor == "Fighter A":
                for action in ("Trip", "Grapple", "Demoralize"):
                    if not state[f"did_{action.lower()}"]:
                        state[f"did_{action.lower()}"] = True
                        return choose(action)
                return choose("End Turn")
            if actor == "Fighter B" and not state["did_escape"]:
                state["did_escape"] = True
                return choose("Escape")
            return choose("Quit")
        if prompt == "Target number:":
            return choose("Fighter B" if active_actor() == "Fighter A" else "Fighter A", prefix=True)
        if prompt == "Maneuver option:":
            return choose("Use a free hand / no weapon")
        if prompt == "Condition effect number:":
            return choose("restrained", prefix=True)
        if prompt == "Escape check method:":
            return choose("Athletics")
        state["unexpected"].append(f"Unexpected prompt: {prompt!r}")
        raise EOFError

    result = run_terminal(
        setup=setup,
        rolls=(20, 1, 10, 20, 14, 20, 1),
        save_path=save_path,
        input_fn=scripted_input,
        output_fn=output,
    )

    rendered = "\n".join(transcript)
    assert result == 0
    assert state["unexpected"] == []
    for action in ("Trip", "Grapple", "Demoralize", "Escape"):
        assert f"Fighter {'A' if action != 'Escape' else 'B'} attempts {action}" in rendered
    assert state["pending_save_stage"] == 2
    assert state["saved"] and state["loaded"]
    assert "Saved encounter to" in rendered and "Loaded encounter from" in rendered
