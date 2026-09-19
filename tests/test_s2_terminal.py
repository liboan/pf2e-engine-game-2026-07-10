from __future__ import annotations

import re
from types import SimpleNamespace
from pathlib import Path
import pytest

from pf2e.content import FIGHTER_M, S2_SETUP
from pf2e.terminal import (
    MAIN_MENU,
    build_action_menu,
    format_action_result,
    main,
    render_actor_sheet,
    render_inspection,
    render_pending_choice,
    render_support_summary,
    _choose_strike_inputs,
    _interact_label,
    run_terminal,
)
from terminal_test_helpers import BoundedTranscript


def _fighter_actor() -> SimpleNamespace:
    fighter = FIGHTER_M
    return SimpleNamespace(
        actor_id="fighter_a",
        label="Fighter A",
        team="blue",
        hp=21,
        max_hp=21,
        ancestry=fighter.ancestry,
        heritage=fighter.heritage,
        background=fighter.background,
        class_name=fighter.class_name,
        deity=fighter.deity,
        level=fighter.level,
        size=fighter.size,
        ac=18,
        perception=6,
        ability_modifiers=fighter.ability_modifiers,
        skills=fighter.skills,
        saves=fighter.saves,
        proficiencies=fighter.proficiencies,
        class_dc=fighter.class_dc,
        feats=fighter.feats,
        abilities=fighter.abilities,
        languages=fighter.languages,
        senses=fighter.senses,
        held_items=fighter.held_items,
        worn_items=fighter.worn_items,
        sheet_notes=fighter.sheet_notes,
        defeated=False,
        dying=0,
        wounded=1,
        unconscious=False,
        dead=False,
        prone=True,
        hero_points=1,
        reaction_available=False,
        health_mode="pc",
        position=SimpleNamespace(x=1, y=1),
        initiative=19,
        actions_remaining=2,
    )


def test_character_sheet_renderer_surfaces_build_resources_and_unsupported_limits() -> None:
    rendered = render_actor_sheet(_fighter_actor())

    assert "Human · Skilled Human · Farmhand · Fighter" in rendered
    assert "Level 1 · medium · HP 21/21 · AC 18 · Perception 6" in rendered
    assert "Strength +4" in rendered
    assert "Fortitude expert +8" in rendered
    assert "Athletics trained +7" in rendered
    assert "Class DC 17" in rendered
    assert "Assurance (Athletics)" in rendered
    assert "Shield Block" in rendered and "owns no shield" in rendered
    assert "Held: longsword" in rendered
    assert "Worn: breastplate" in rendered


def test_inspection_renders_health_resources_and_ground_items_without_inference() -> None:
    actor = _fighter_actor()
    view = SimpleNamespace(
        in_progress=True,
        round_number=1,
        turn_actor_id=actor.actor_id,
        map_width=7,
        map_height=5,
        actors=(actor,),
        ground_items=((actor.position, ("dropped shield",)),),
    )

    rendered = render_inspection(view)

    assert "conditions: wounded 1, prone" in rendered
    assert "Hero Points 1" in rendered
    assert "reaction spent" in rendered
    assert "held longsword" in rendered
    assert "worn breastplate" in rendered
    assert "ground B2: dropped shield" in rendered


def test_pending_choice_displays_owner_original_roll_and_engine_option_order() -> None:
    actor = _fighter_actor()
    inspection = SimpleNamespace(actors=(actor,))
    choice = SimpleNamespace(
        choice_id=14,
        kind="hero_point_reroll",
        owner_actor_id=actor.actor_id,
        prompt="Choose whether to reroll.",
        details=("Original check: d20 4 + 9 = 13; failure vs AC 18.",),
        options=(
            SimpleNamespace(option_id="keep", label="Keep result"),
            SimpleNamespace(option_id="spend_hero_point", label="Spend 1 Hero Point and reroll"),
        ),
    )

    rendered = render_pending_choice(choice, inspection)

    assert "choice owner: Fighter A" in rendered
    assert "Original check: d20 4 + 9 = 13; failure vs AC 18." in rendered
    assert rendered.index("1. Keep result") < rendered.index("2. Spend 1 Hero Point and reroll")


def test_s2_summary_and_cli_admit_the_reviewed_roster(monkeypatch) -> None:
    from pf2e import content, terminal

    summary = render_support_summary("s2_fighters_vs_guard_dogs")
    assert "S2 fixed encounter" in summary
    assert "selected actions and health procedures admitted" in summary
    calls = []
    monkeypatch.setattr(terminal, "run_terminal", lambda **kwargs: calls.append(kwargs) or 0)

    assert main(["play", "s2"]) == 0
    assert len(calls) == 1
    assert calls[0]["setup"] is content.S2_SETUP


def test_dynamic_menu_shows_only_engine_actions_and_keeps_global_controls() -> None:
    entries = build_action_menu(("stand", "vicious_swing", "end_turn"))

    assert entries == (
        ("inspect", "Inspect"),
        ("stand", "Stand"),
        ("vicious_swing", "Vicious Swing"),
        ("end_turn", "End Turn"),
        ("save", "Save"),
        ("load", "Load"),
        ("restart", "Restart"),
        ("quit", "Quit"),
    )
    assert tuple(label for _, label in build_action_menu((), preserve_s1=True)) == MAIN_MENU


def test_strike_prompt_uses_engine_weapon_targets_damage_types_and_intent_options() -> None:
    attack = SimpleNamespace(
        attack_id="longsword",
        name="Longsword",
        targets=("dog_a", "dog_b"),
        damage_types=("slashing", "piercing"),
        default_damage_type="slashing",
        default_nonlethal=False,
    )
    inspection = SimpleNamespace(
        actors=(
            SimpleNamespace(actor_id="dog_a", label="Guard Dog A"),
            SimpleNamespace(actor_id="dog_b", label="Guard Dog B"),
        )
    )
    inputs = iter(("1", "2", "2", "3"))
    output: list[str] = []

    selection = _choose_strike_inputs((attack,), inspection, lambda: next(inputs), output.append)

    assert selection == ("longsword", "dog_b", "piercing", True)
    transcript = "\n".join(output)
    assert "Longsword (longsword)" in transcript
    assert "Guard Dog B (dog_b)" in transcript
    assert "Slashing" in transcript and "Piercing" in transcript
    assert "Lethal damage" in transcript and "Nonlethal damage" in transcript


def test_single_damage_type_keeps_engine_default_and_default_intent_unmodified() -> None:
    attack = SimpleNamespace(
        attack_id="jaws",
        name="Jaws",
        targets=("fighter_a",),
        damage_types=("piercing",),
        default_damage_type="piercing",
        default_nonlethal=False,
    )
    inspection = SimpleNamespace(actors=(SimpleNamespace(actor_id="fighter_a", label="Fighter A"),))
    inputs = iter(("1", "1", "1"))

    selection = _choose_strike_inputs((attack,), inspection, lambda: next(inputs), lambda _line: None)

    assert selection == ("jaws", "fighter_a", None, None)


def test_interact_labels_and_engine_detail_rendering_are_literal() -> None:
    assert _interact_label("retrieve", "longsword") == "Retrieve: longsword"
    result = SimpleNamespace(
        status="completed",
        message="Action completed.",
        events=(
            SimpleNamespace(
                text="Reactive Strike: d20 16 + 9 = 25 vs AC 15; critical success.",
                details=("Damage: 2d4 + 2 = 7 piercing.",),
            ),
        ),
    )

    assert format_action_result(result) == (
        "Reactive Strike: d20 16 + 9 = 25 vs AC 15; critical success.",
        "Damage: 2d4 + 2 = 7 piercing.",
        "Action completed.",
    )


def test_s2_terminal_saves_reaction_and_nested_hero_choice_then_continues(tmp_path: Path) -> None:
    state = {
        "outputs": BoundedTranscript(),
        "prompt": "",
        "menu": "",
        "inspection": "",
        "choice_block": "",
        "a_stride": False,
        "a_swing": False,
        "b_stride": False,
        "dog_b_stride": False,
        "dog_a_stride": False,
        "reaction_save_stage": 0,
        "hero_save_stage": 0,
        "dog_b_reaction_accepted": False,
        "unexpected": [],
    }
    save_path = tmp_path / "s2-paused.json"

    def output(line: str) -> None:
        state["outputs"].append(line)
        if line.startswith("Round ") and "\nMap:" in line:
            state["inspection"] = line
        if "choice owner:" in line:
            state["choice_block"] = line
        if line.startswith("1. "):
            state["menu"] = line
        if line.endswith(":") or line.startswith(("Save file [", "Load file [")):
            state["prompt"] = line

    def menu_choice(label: str) -> str:
        for row in state["menu"].splitlines():
            match = re.match(r"(\d+)\.\s+(.*)", row)
            if match and match.group(2) == label:
                return match.group(1)
        state["unexpected"].append(f"Menu label missing: {label!r}")
        raise EOFError

    def active_actor() -> str:
        first_line = state["inspection"].splitlines()[0]
        match = re.match(r"Round \d+ · ([^(]+)", first_line)
        return match.group(1).strip() if match else ""

    def scripted_input() -> str:
        prompt = state["prompt"]
        choice_block = state["choice_block"]
        if prompt == "Choice prompt action:":
            if "initiative" in choice_block.lower():
                return menu_choice("Resolve this choice")
            if "may use Reactive Strike against Guard Dog B" in choice_block:
                stage = state["reaction_save_stage"]
                state["reaction_save_stage"] += 1
                return ("3", "4", "2")[min(stage, 2)]  # Save, reload, then resolve.
            if (
                state["dog_b_reaction_accepted"]
                and "Fighter B" in choice_block
                and "may keep" in choice_block
            ):
                stage = state["hero_save_stage"]
                state["hero_save_stage"] += 1
                return ("3", "4", "2")[min(stage, 2)]
            return menu_choice("Resolve this choice")
        if prompt == "Choice option number:":
            if "Reactive Strike against Guard Dog B" in choice_block:
                state["dog_b_reaction_accepted"] = True
                return "1"
            if "Reactive Strike against Guard Dog A" in choice_block:
                return menu_choice("Decline")
            return "1"  # Keep the initiative/check result explicitly.
        if prompt == "Choice:":
            actor = active_actor()
            if actor == "Fighter A":
                if not state["a_stride"]:
                    state["a_stride"] = True
                    return menu_choice("Stride")
                if not state["a_swing"]:
                    state["a_swing"] = True
                    return menu_choice("Vicious Swing")
                return menu_choice("Quit")  # Continue into round two, then stop.
            if actor == "Fighter B":
                if not state["b_stride"]:
                    state["b_stride"] = True
                    return menu_choice("Stride")
                return menu_choice("End Turn")
            if actor == "Guard Dog B":
                if not state["dog_b_stride"]:
                    state["dog_b_stride"] = True
                    return menu_choice("Stride")
                return menu_choice("End Turn")
            if actor == "Guard Dog A":
                if not state["dog_a_stride"]:
                    state["dog_a_stride"] = True
                    return menu_choice("Stride")
                return menu_choice("End Turn")
            state["unexpected"].append(f"Unexpected active actor: {actor!r}")
            raise EOFError
        if prompt.startswith(("Save file [", "Load file [")):
            return str(save_path)
        if prompt.startswith("Stride path"):
            return {
                "Fighter A": "C2 D2 E2",
                "Fighter B": "C4 D4 E4",
                "Guard Dog B": "G4",
                "Guard Dog A": "G2",
            }[active_actor()]
        if prompt == "Weapon / attack number:":
            return "1"  # Longsword.
        if prompt == "Target number:":
            target_label = {
                "Fighter A": "Guard Dog A (guard_dog_a)",
                "Fighter B": "Guard Dog B (guard_dog_b)",
            }.get(active_actor(), "")
            return menu_choice(target_label)
        if prompt == "Damage type:":
            return "2"  # Piercing, one of the engine-provided versatile choices.
        if prompt == "Damage intent:":
            return "3"  # Explicitly choose nonlethal intent.
        state["unexpected"].append(f"Unexpected prompt: {prompt!r}")
        raise EOFError

    status = run_terminal(
        setup=S2_SETUP,
        rolls=(20, 19, 1, 2, 1, 20, 4, 4, 4, 4, 4),
        save_path=save_path,
        input_fn=scripted_input,
        output_fn=output,
    )
    transcript = "\n".join(state["outputs"])

    assert status == 0
    assert state["unexpected"] == []
    assert state["reaction_save_stage"] == 3
    assert state["hero_save_stage"] == 3
    assert state["dog_b_reaction_accepted"] is True
    assert transcript.count("Saved encounter to") == 2
    assert transcript.count("Loaded encounter from") == 2
    assert "Vicious Swing" in transcript
    assert "Piercing" in transcript
    assert "Original: d20 1 + 7 = 8 vs AC 15." in transcript  # Nonlethal intent applies its modifier.
    assert "Fighter B uses Reactive Strike" in transcript
    assert "Original: d20 20 + 9 = 29 vs AC 15." in transcript
    assert "Damage: 1d8 (4) + 4 = 8; critical doubles to 16 slashing; target defeated." in transcript
    assert "Fighter A declines; the reaction remains available." in transcript
    assert "Round 2 · Fighter A" in transcript
    assert "Goodbye." in transcript


def test_s2_terminal_repeating_inspect_input_fails_at_bounded_capture_limit() -> None:
    output = BoundedTranscript(max_lines=32)

    with pytest.raises(AssertionError, match="transcript exceeded its capture limit"):
        run_terminal(
            setup=S2_SETUP,
            input_fn=lambda: "1",  # Repeatedly inspect the unresolved initiative choice.
            output_fn=output.append,
        )

    assert len(output) == 32
