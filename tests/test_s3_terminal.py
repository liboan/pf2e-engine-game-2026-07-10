from __future__ import annotations

import re
from types import SimpleNamespace
from pathlib import Path
import pytest

from pf2e.content import S3_READY, S3_SETUP, WARPRIEST_C
from pf2e.terminal import (
    _choose_cast_inputs,
    build_action_menu,
    render_actor_sheet,
    render_inspection,
    render_pending_choice,
    render_support_summary,
    run_terminal,
)
from pf2e.model import PreparedSlotView, SpellTargetOption
from terminal_test_helpers import BoundedTranscript


def _terminal_capture():
    state = {"outputs": BoundedTranscript(), "prompt": "", "menu": "", "inspection": "", "choice_block": ""}

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

    def menu_choice(label: str, *, prefix: bool = False) -> str:
        for row in state["menu"].splitlines():
            match = re.match(r"(\d+)\.\s+(.*)", row)
            if match and (match.group(2).startswith(label) if prefix else match.group(2) == label):
                return match.group(1)
        raise EOFError

    def active_actor() -> str:
        if not state["inspection"]:
            return ""
        match = re.match(r"Round \d+ · ([^(]+)", state["inspection"].splitlines()[0])
        return match.group(1).strip() if match else ""

    return state, output, menu_choice, active_actor


def test_s3_action_menu_only_adds_cast_and_cover_when_engine_offers_them() -> None:
    menu = build_action_menu(("cast", "take_cover", "end_turn"))

    assert menu == (
        ("inspect", "Inspect"),
        ("cast", "Cast"),
        ("take_cover", "Take Cover"),
        ("end_turn", "End Turn"),
        ("save", "Save"),
        ("load", "Load"),
        ("restart", "Restart"),
        ("quit", "Quit"),
    )


def test_caster_sheet_renders_individually_labeled_spell_slots_and_ammunition() -> None:
    cleric = WARPRIEST_C
    actor = SimpleNamespace(
        actor_id="cleric_c",
        label="Warpriest C",
        **{
            key: getattr(cleric, key)
            for key in (
                "ancestry",
                "heritage",
                "background",
                "class_name",
                "deity",
                "level",
                "size",
                "ability_modifiers",
                "skills",
                "saves",
                "proficiencies",
                "class_dc",
                "feats",
                "abilities",
                "languages",
                "senses",
                "held_items",
                "worn_items",
                "sheet_notes",
            )
        },
        hp=17,
        max_hp=17,
        ac=18,
        perception=7,
        ammunition=(),
        prepared_slots=tuple(
            PreparedSlotView(
                slot_id=spell.slot_id,
                source=spell.source,
                spell_id=spell.spell_id,
                rank=spell.rank,
                cantrip=spell.cantrip,
                spent=False,
            )
            for spell in cleric.prepared_spells
        ),
    )

    rendered = render_actor_sheet(actor)

    assert "Identity: Human · Skilled Human · Farmhand · Cleric · Iomedae" in rendered
    assert "Cantrip Read Aura: Read Aura (Cantrip, cantrip, ready)" in rendered
    assert "Ordinary Heal 1: Heal (Ordinary, rank 1, ready)" in rendered
    assert "Font Heal 4: Heal (Font, rank 1, ready)" in rendered
    assert "Shield Block" in rendered and "owns no shield" in rendered


def test_inspection_renders_ammo_prepared_slot_sources_active_effect_expiry_and_immunity() -> None:
    actor = SimpleNamespace(
        actor_id="cleric_c",
        label="Warpriest C",
        team="blue",
        hp=17,
        max_hp=17,
        ac=18,
        perception=7,
        position=SimpleNamespace(x=1, y=1),
        initiative=20,
        actions_remaining=2,
        defeated=False,
        health_mode="pc",
        dying=0,
        wounded=0,
        unconscious=False,
        dead=False,
        prone=False,
        hero_points=0,
        reaction_available=True,
        held_items=("longsword",),
        worn_items=("breastplate",),
        stowed_items=(),
        ammunition=(("arrow", 5),),
        prepared_slots=(
            PreparedSlotView("font_heal_1", "font", "heal", 1, False, True),
            PreparedSlotView("cantrip_guidance", "cantrip", "guidance", 1, True, False),
        ),
        effects=(
            SimpleNamespace(
                kind="guidance",
                source_actor_id="cleric_c",
                target_actor_id="fighter_r",
                value=1,
                expires_at_source_start=2,
            ),
        ),
        guidance_immune_until_round=5,
    )
    other = SimpleNamespace(
        actor_id="fighter_r",
        label="Fighter R",
        team="blue",
        hp=21,
        max_hp=21,
        ac=18,
        perception=6,
        position=SimpleNamespace(x=1, y=3),
        initiative=18,
        actions_remaining=3,
        defeated=False,
        health_mode="pc",
        dying=0,
        wounded=0,
        unconscious=False,
        dead=False,
        prone=False,
        hero_points=1,
        reaction_available=True,
        held_items=("shortbow",),
        worn_items=("leather_armor", "longsword"),
        stowed_items=(),
        ammunition=(("arrow", 20),),
        prepared_slots=(),
        effects=(),
        guidance_immune_until_round=None,
    )
    inspection = SimpleNamespace(
        in_progress=True,
        round_number=1,
        turn_actor_id=actor.actor_id,
        map_width=7,
        map_height=5,
        actors=(actor, other),
        ground_items=(),
    )

    rendered = render_inspection(inspection)

    assert "Warpriest C ammunition: arrow 5" in rendered
    assert "font_heal_1 = Heal (font, rank 1, spent)" in rendered
    assert "Active effect: Guidance +1 on Fighter R, from Warpriest C; expires at source start round 2." in rendered
    assert "Warpriest C Guidance immunity through round 5." in rendered
    assert "Warpriest C (blue) — HP 17/17; 2 actions; initiative 20; conditions: none · Hero Points 0" in rendered


def test_cast_prompts_use_engine_mode_targets_slots_and_surface_unavailable_read_aura() -> None:
    spells = (
        SimpleNamespace(
            spell_id="heal",
            name="Heal",
            traits=("healing", "manipulate", "vitality"),
            action_costs=(1, 2, 3),
            slots=(("ordinary_heal_1", "ordinary"), ("font_heal_1", "font")),
            target_options=(
                SpellTargetOption(1, ("fighter_m",)),
                SpellTargetOption(2, ("fighter_m", "fighter_r")),
                SpellTargetOption(3, ("fighter_m", "fighter_r"), include_self_available=True),
            ),
            unavailable_reason=None,
        ),
        SimpleNamespace(
            spell_id="read_aura",
            name="Read Aura",
            traits=("cantrip", "concentrate", "manipulate"),
            action_costs=(),
            slots=(),
            target_options=(),
            unavailable_reason="one-minute casting time is unavailable during encounters",
        ),
    )
    actors = tuple(
        SimpleNamespace(actor_id=actor_id, label=label)
        for actor_id, label in (
            ("fighter_m", "Fighter M"),
            ("fighter_r", "Fighter R"),
        )
    )
    inspection = SimpleNamespace(actors=actors)
    inputs = iter(("1", "3", "2"))  # Heal, 3 actions, font slot.
    output: list[str] = []

    selection = _choose_cast_inputs(spells, inspection, lambda: next(inputs), output.append)

    assert selection == ("heal", None, 3, "font_heal_1", None)
    rendered = "\n".join(output)
    assert "Unavailable: Read Aura — one-minute casting time is unavailable during encounters" in rendered
    assert "Other engine-listed recipients: Fighter M, Fighter R" in rendered
    assert "The engine will ask whether to include the caster." in rendered


def test_cast_single_target_uses_engine_targets_without_computing_range() -> None:
    spell = SimpleNamespace(
        spell_id="divine_lance",
        name="Divine Lance",
        traits=("attack", "cantrip", "ranged"),
        action_costs=(2,),
        slots=(),
        target_options=(SpellTargetOption(2, ("guard_dog_b",)),),
        unavailable_reason=None,
    )
    inspection = SimpleNamespace(
        actors=(SimpleNamespace(actor_id="guard_dog_b", label="Guard Dog B"),)
    )
    inputs = iter(("1", "1", "1"))  # spell, two-action mode, engine-provided target.
    output: list[str] = []

    selection = _choose_cast_inputs((spell,), inspection, lambda: next(inputs), output.append)

    assert selection == ("divine_lance", "guard_dog_b", 2, None, None)
    assert "Guard Dog B (guard_dog_b)" in "\n".join(output)


def test_s3_is_described_as_admitted_fixed_content() -> None:
    assert S3_READY is True
    summary = render_support_summary("s3_mixed_party_vs_three_guard_dogs")
    assert "S3 fixed encounter" in summary
    assert "Other class, creature, and PF2e actions remain outside this scope." in summary


def test_pending_spell_choice_shows_engine_owner_options_and_check_details() -> None:
    actor = SimpleNamespace(actor_id="fighter_r", label="Fighter R")
    inspection = SimpleNamespace(actors=(actor,))
    choice = SimpleNamespace(
        choice_id=14,
        kind="guidance_use",
        owner_actor_id=actor.actor_id,
        prompt="Fighter R may use Guidance before this attack check.",
        details=("Guidance: +1 status bonus; expires at Cleric C's start of round 2.",),
        options=(
            SimpleNamespace(option_id="use", label="Use Guidance"),
            SimpleNamespace(option_id="keep", label="Keep the Guidance bonus unused"),
        ),
    )

    rendered = render_pending_choice(choice, inspection)

    assert "choice owner: Fighter R" in rendered
    assert "expires at Cleric C's start of round 2" in rendered
    assert "1. Use Guidance" in rendered and "2. Keep the Guidance bonus unused" in rendered


def test_s3_terminal_guidance_effect_survives_save_load_and_next_die_is_consumed(tmp_path: Path) -> None:
    state = {
        "outputs": BoundedTranscript(),
        "prompt": "",
        "menu": "",
        "inspection": "",
        "choice_block": "",
        "cast": False,
        "inspect": False,
        "saved": False,
        "loaded": False,
        "cleric_stride": False,
        "cleric_end": False,
        "fighter_stride": False,
        "fighter_strike": False,
        "fighter_end": False,
        "guidance_used": False,
        "unexpected": [],
    }
    save_path = tmp_path / "s3-guidance.json"

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
            return menu_choice("Resolve this choice")
        if prompt == "Choice option number:":
            if "may keep initiative" in choice_block:
                return menu_choice("Keep initiative")
            if "choose the next tied PC" in choice_block.lower():
                if "initiative_tie_cleric" not in state:
                    state["initiative_tie_cleric"] = True
                    return menu_choice("Warpriest C")
                return menu_choice("Fighter M")
            if "may use Guidance" in choice_block:
                state["guidance_used"] = True
                return menu_choice("Use Guidance (+1 status)")
            return menu_choice(next(
                label for label in ("Keep result", "Keep the result", "Keep the attack result")
                if any(row.endswith(label) for row in state["menu"].splitlines())
            ))
        if prompt.startswith(("Save file [", "Load file [")):
            if prompt.startswith("Save file ["):
                state["saved"] = True
            else:
                state["loaded"] = True
            return str(save_path)
        if prompt == "Choice:":
            actor = active_actor()
            if actor == "Warpriest C":
                if not state["cast"]:
                    state["cast"] = True
                    return menu_choice("Cast")
                if not state["inspect"]:
                    state["inspect"] = True
                    return menu_choice("Inspect")
                if not state["saved"]:
                    return menu_choice("Save")
                if not state["loaded"]:
                    return menu_choice("Load")
                if not state["cleric_stride"]:
                    state["cleric_stride"] = True
                    return menu_choice("Stride")
                state["cleric_end"] = True
                return menu_choice("End Turn")
            if actor == "Fighter M":
                if not state["fighter_stride"]:
                    state["fighter_stride"] = True
                    return menu_choice("Stride")
                if not state["fighter_strike"]:
                    state["fighter_strike"] = True
                    return menu_choice("Strike")
                state["fighter_end"] = True
                return menu_choice("End Turn")
            if actor == "Fighter R":
                return menu_choice("Quit")
            state["unexpected"].append(f"Unexpected active actor: {actor!r}")
            raise EOFError
        if prompt == "Spell number:":
            return menu_choice(next(
                row.split(". ", 1)[1]
                for row in state["menu"].splitlines()
                if ". Guidance (" in row
            ))
        if prompt == "Casting mode:":
            return "1"
        if prompt == "Target number:":
            target = (
                "Fighter M (fighter_m)"
                if active_actor() == "Warpriest C"
                else "Guard Dog A (guard_dog_a)"
            )
            return menu_choice(target)
        if prompt == "Stride path, in order (for example B2 C2 D3):":
            return "C5" if active_actor() == "Warpriest C" else "C1 D1 E1"
        if prompt == "Weapon / attack number:":
            return menu_choice("Longsword (longsword)")
        if prompt == "Damage type:":
            return "1"  # Slashing.
        if prompt == "Damage intent:":
            return "1"  # Keep the engine-selected lethal default.
        state["unexpected"].append(f"Unexpected input prompt: {prompt!r}")
        raise EOFError

    result = run_terminal(
        setup=S3_SETUP,
        rolls=(20, 19, 20, 18, 17, 16, 20, 4),
        save_path=save_path,
        input_fn=scripted_input,
        output_fn=output,
    )

    transcript = "\n".join(state["outputs"])
    assert result == 0
    assert state["unexpected"] == []
    assert all(
        state[key]
        for key in (
            "cast",
            "inspect",
            "saved",
            "loaded",
            "cleric_stride",
            "cleric_end",
            "fighter_stride",
            "fighter_strike",
            "fighter_end",
            "guidance_used",
        )
    )
    assert "Unavailable: Read Aura" in transcript
    assert "Active effect: Guidance +1 on Fighter M, from Warpriest C; expires at source start round 2." in transcript
    assert f"Loaded encounter from {save_path}." in transcript
    assert "Original: d20 20 + 10 = 30 vs AC 15" in transcript
    assert "1d8 (4) + 4 = 8; critical doubles to 16 slashing; target defeated" in transcript


def test_s3_terminal_divine_lance_uses_spell_attack_choice_and_critical_damage() -> None:
    state = {"outputs": BoundedTranscript(), "prompt": "", "menu": "", "inspection": "", "choice_block": "", "cast": False}

    def output(line: str) -> None:
        state["outputs"].append(line)
        if line.startswith("Round ") and "\nMap:" in line:
            state["inspection"] = line
        if "choice owner:" in line:
            state["choice_block"] = line
        if line.startswith("1. "):
            state["menu"] = line
        if line.endswith(":"):
            state["prompt"] = line

    def menu_choice(label: str) -> str:
        for row in state["menu"].splitlines():
            match = re.match(r"(\d+)\.\s+(.*)", row)
            if match and match.group(2) == label:
                return match.group(1)
        raise EOFError

    def active_actor() -> str:
        match = re.match(r"Round \d+ · ([^(]+)", state["inspection"].splitlines()[0])
        return match.group(1).strip() if match else ""

    def scripted_input() -> str:
        prompt = state["prompt"]
        if prompt == "Choice prompt action:":
            return menu_choice("Resolve this choice")
        if prompt == "Choice option number:":
            if "may keep initiative" in state["choice_block"]:
                return menu_choice("Keep initiative")
            return menu_choice("Keep result")
        if prompt == "Choice:":
            if active_actor() == "Warpriest C" and not state["cast"]:
                state["cast"] = True
                return menu_choice("Cast")
            return menu_choice("Quit")
        if prompt == "Spell number:":
            return menu_choice(next(
                row.split(". ", 1)[1]
                for row in state["menu"].splitlines()
                if ". Divine Lance (" in row
            ))
        if prompt == "Casting mode:":
            return "1"
        if prompt == "Target number:":
            return menu_choice("Guard Dog C (guard_dog_c)")
        raise EOFError

    result = run_terminal(
        setup=S3_SETUP,
        rolls=(1, 2, 20, 3, 4, 5, 20, 4, 3),
        input_fn=scripted_input,
        output_fn=output,
    )

    transcript = "\n".join(state["outputs"])
    assert result == 0
    assert state["cast"]
    assert "Original: d20 20 + 7 = 27 vs AC 15" in transcript
    assert "Divine Lance deals 14 spirit to Guard Dog C." in transcript
    assert "Guard Dog C is defeated." in transcript


def test_s3_terminal_shortbow_save_load_hero_prompt_spends_one_arrow_and_deadly_d10(tmp_path: Path) -> None:
    state = {
        "outputs": BoundedTranscript(),
        "prompt": "",
        "menu": "",
        "inspection": "",
        "choice_block": "",
        "strike": False,
        "reaction_save_stage": 0,
        "unexpected": [],
    }
    save_path = tmp_path / "s3-bow-hero.json"

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
        match = re.match(r"Round \d+ · ([^(]+)", state["inspection"].splitlines()[0])
        return match.group(1).strip() if match else ""

    def scripted_input() -> str:
        prompt = state["prompt"]
        choice_block = state["choice_block"]
        if prompt == "Choice prompt action:":
            if "may keep initiative" in choice_block:
                return menu_choice("Resolve this choice")
            if "may keep this Strike" in choice_block:
                stage = state["reaction_save_stage"]
                state["reaction_save_stage"] += 1
                return (menu_choice("Save"), menu_choice("Load"), menu_choice("Resolve this choice"))[min(stage, 2)]
            return menu_choice("Resolve this choice")
        if prompt == "Choice option number:":
            if "may keep initiative" in choice_block:
                return menu_choice("Keep initiative")
            return menu_choice("Keep result")
        if prompt.startswith(("Save file [", "Load file [")):
            return str(save_path)
        if prompt == "Choice:":
            if active_actor() == "Fighter R" and not state["strike"]:
                state["strike"] = True
                return menu_choice("Strike")
            return menu_choice("Quit")
        if prompt == "Weapon / attack number:":
            return menu_choice("Shortbow (shortbow)")
        if prompt == "Target number:":
            return menu_choice("Guard Dog B (guard_dog_b)")
        if prompt == "Damage intent:":
            return "1"  # Use the engine-selected lethal default.
        state["unexpected"].append(f"Unexpected input prompt: {prompt!r}")
        raise EOFError

    result = run_terminal(
        setup=S3_SETUP,
        rolls=(1, 20, 2, 3, 4, 5, 20, 4, 7),
        save_path=save_path,
        input_fn=scripted_input,
        output_fn=output,
    )

    transcript = "\n".join(state["outputs"])
    assert result == 0
    assert state["unexpected"] == []
    assert state["strike"]
    assert state["reaction_save_stage"] == 3
    assert f"Saved encounter to {save_path}." in transcript
    assert f"Loaded encounter from {save_path}." in transcript
    assert "Fighter R ammunition: arrow 19" in transcript
    assert "Original: d20 20 + 9 = 29 vs AC 15" in transcript
    assert "critical doubles to 8, plus deadly 1d10 (7) = 15 piercing; target defeated" in transcript


def _menu_labels(state: dict[str, object]) -> tuple[str, ...]:
    labels = []
    for row in str(state.get("menu", "")).splitlines():
        match = re.match(r"\d+\.\s+(.*)", row)
        if match:
            labels.append(match.group(1))
    return tuple(labels)


def _menu_number(state: dict[str, object], label: str, *, prefix: bool = False) -> str:
    for row in str(state.get("menu", "")).splitlines():
        match = re.match(r"(\d+)\.\s+(.*)", row)
        if match and (match.group(2).startswith(label) if prefix else match.group(2) == label):
            return match.group(1)
    raise EOFError(f"Menu label missing: {label!r}")


def _answer_choice_option(state: dict[str, object]) -> str:
    labels = _menu_labels(state)
    preferred = (
        "Keep initiative",
        "Keep result",
        "Apply normal health outcome",
        "Willing",
        "Include self",
        "Spend 1 Hero Point and reroll",
    )
    for label in preferred:
        for current in labels:
            if current == label or current.startswith(label):
                return _menu_number(state, current)
    raise EOFError(f"No scripted resolution for choice options: {labels!r}")


@pytest.mark.parametrize(
    ("actions", "heal_roll", "expected_hp", "slot_id"),
    ((1, 8, 8, "ordinary_heal_1"), (2, 4, 12, "ordinary_heal_2")),
)
def test_s3_terminal_heal_single_target_modes_save_willingness_and_spend_slot(
    tmp_path: Path,
    actions: int,
    heal_roll: int,
    expected_hp: int,
    slot_id: str,
) -> None:
    state, output, menu_choice, active_actor = _terminal_capture()
    state["active_actor"] = active_actor
    state["choice_save_load_stage"] = 0
    state["healed"] = False
    state["cast"] = False
    state["heal_stride"] = False
    state["end_after_heal"] = False
    state["unexpected"] = []
    save_path = tmp_path / f"s3-heal-{actions}.json"

    def scripted_input() -> str:
        prompt = str(state["prompt"])
        choice_block = str(state["choice_block"])
        if prompt == "Choice prompt action:":
            if "Is Fighter R willing to receive Heal?" in choice_block:
                stage = int(state["choice_save_load_stage"])
                state["choice_save_load_stage"] = stage + 1
                return menu_choice(("Save", "Load", "Resolve this choice")[min(stage, 2)])
            return menu_choice("Resolve this choice")
        if prompt == "Choice option number:":
            if "Is Fighter R willing to receive Heal?" in choice_block:
                state["healed"] = True
                return menu_choice("Willing")
            return _answer_choice_option(state)
        if prompt.startswith(("Save file [", "Load file [")):
            return str(save_path)
        if prompt == "Choice:":
            actor = active_actor()
            if actor == "Fighter M":
                if not state.get("knockdown_stride"):
                    state["knockdown_stride"] = True
                    return menu_choice("Stride")
                if not state.get("knockdown_strike"):
                    state["knockdown_strike"] = True
                    return menu_choice("Strike")
                state["knockdown_end"] = True
                return menu_choice("End Turn")
            if actor == "Warpriest C":
                if actions == 1 and not state["heal_stride"]:
                    state["heal_stride"] = True
                    return menu_choice("Stride")
                if not state["cast"]:
                    state["cast"] = True
                    return menu_choice("Cast")
                if not state["end_after_heal"]:
                    state["end_after_heal"] = True
                    return menu_choice("End Turn")
            return menu_choice("Quit")
        if prompt == "Stride path, in order (for example B2 C2 D3):":
            return "B2" if active_actor() == "Fighter M" else "B4"
        if prompt == "Weapon / attack number:":
            return menu_choice("Longsword (longsword)")
        if prompt == "Target number:":
            return menu_choice("Fighter R (fighter_r)")
        if prompt == "Damage type:":
            return menu_choice("Slashing")
        if prompt == "Damage intent:":
            return menu_choice("Use attack default", prefix=True)
        if prompt == "Spell number:":
            return menu_choice("Heal (", prefix=True)
        if prompt == "Casting mode:":
            return menu_choice(f"{actions} action" + ("s" if actions != 1 else ""))
        if prompt == "Prepared slot:":
            return menu_choice(slot_id, prefix=True)
        state["unexpected"].append(f"Unexpected input prompt: {prompt!r}")
        raise EOFError

    result = run_terminal(
        setup=S3_SETUP,
        rolls=(20, 19, 10, 1, 2, 3, 20, 8, heal_roll),
        save_path=save_path,
        input_fn=scripted_input,
        output_fn=output,
    )

    transcript = "\n".join(state["outputs"])
    assert result == 0
    assert state["unexpected"] == []
    assert state["cast"] and state["healed"]
    assert state["choice_save_load_stage"] == 3
    assert f"Saved encounter to {save_path}." in transcript
    assert f"Loaded encounter from {save_path}." in transcript
    assert "choice owner: Fighter R" in transcript
    assert "Willing" in transcript and "Unwilling" in transcript
    assert f"{slot_id} = Heal (ordinary, rank 1, spent)" in transcript
    assert f"Fighter R (blue) — HP {expected_hp}/21" in transcript


def test_s3_terminal_three_action_heal_saves_self_inclusion_choice(tmp_path: Path) -> None:
    state, output, menu_choice, active_actor = _terminal_capture()
    state["active_actor"] = active_actor
    state["save_load_stage"] = 0
    state["cast"] = False
    state["unexpected"] = []
    save_path = tmp_path / "s3-heal-emanation.json"

    def scripted_input() -> str:
        prompt = str(state["prompt"])
        choice_block = str(state["choice_block"])
        if prompt == "Choice prompt action:":
            if "Include the caster in the three-action Heal emanation?" in choice_block:
                stage = int(state["save_load_stage"])
                state["save_load_stage"] = stage + 1
                return menu_choice(("Save", "Load", "Resolve this choice")[min(stage, 2)])
            return menu_choice("Resolve this choice")
        if prompt == "Choice option number:":
            return _answer_choice_option(state)
        if prompt.startswith(("Save file [", "Load file [")):
            return str(save_path)
        if prompt == "Choice:":
            actor = active_actor()
            if actor == "Fighter M":
                if not state.get("knockdown_stride"):
                    state["knockdown_stride"] = True
                    return menu_choice("Stride")
                if not state.get("knockdown_strike"):
                    state["knockdown_strike"] = True
                    return menu_choice("Strike")
                return menu_choice("End Turn")
            if actor == "Warpriest C" and not state["cast"]:
                state["cast"] = True
                return menu_choice("Cast")
            return menu_choice("Quit")
        if prompt == "Stride path, in order (for example B2 C2 D3):":
            return "B2"
        if prompt == "Weapon / attack number:":
            return menu_choice("Longsword (longsword)")
        if prompt == "Target number:":
            return menu_choice("Fighter R (fighter_r)")
        if prompt == "Damage type:":
            return menu_choice("Slashing")
        if prompt == "Damage intent:":
            return menu_choice("Use attack default", prefix=True)
        if prompt == "Spell number:":
            return menu_choice("Heal (", prefix=True)
        if prompt == "Casting mode:":
            return menu_choice("3 actions")
        if prompt == "Prepared slot:":
            return menu_choice("font_heal_1", prefix=True)
        state["unexpected"].append(f"Unexpected input prompt: {prompt!r}")
        raise EOFError

    result = run_terminal(
        setup=S3_SETUP,
        rolls=(20, 19, 10, 1, 2, 3, 20, 8, 4),
        save_path=save_path,
        input_fn=scripted_input,
        output_fn=output,
    )

    transcript = "\n".join(state["outputs"])
    assert result == 0
    assert state["unexpected"] == []
    assert state["save_load_stage"] == 3
    assert "choice owner: Warpriest C" in transcript
    assert "Other engine-listed recipients:" in transcript
    assert "The engine will ask whether to include the caster." in transcript
    assert "Include self" in transcript and "Exclude self" in transcript
    assert f"Saved encounter to {save_path}." in transcript
    assert f"Loaded encounter from {save_path}." in transcript
    assert "Three-action Heal rolls 1d8 (4) = 4" in transcript
    assert "Fighter R heals 4 HP (shared 1d8 4); now at 4 HP." in transcript
    assert "Warpriest C heals 4 HP (shared 1d8 4); now at 17 HP." in transcript
    assert "font_heal_1 = Heal (font, rank 1, spent)" in transcript


def test_s3_terminal_void_warp_save_hero_choice_is_owned_by_target_and_round_trips(
    tmp_path: Path,
) -> None:
    state, output, menu_choice, active_actor = _terminal_capture()
    state["active_actor"] = active_actor
    state["save_load_stage"] = 0
    state["cast"] = False
    state["end_turn"] = False
    state["unexpected"] = []
    save_path = tmp_path / "s3-void-warp-save.json"

    def scripted_input() -> str:
        prompt = str(state["prompt"])
        choice_block = str(state["choice_block"])
        if prompt == "Choice prompt action:":
            if "Fortitude save" in choice_block:
                stage = int(state["save_load_stage"])
                state["save_load_stage"] = stage + 1
                return menu_choice(("Save", "Load", "Resolve this choice")[min(stage, 2)])
            return menu_choice("Resolve this choice")
        if prompt == "Choice option number:":
            if "Fortitude save" in choice_block:
                return menu_choice("Spend 1 Hero Point and reroll")
            return _answer_choice_option(state)
        if prompt.startswith(("Save file [", "Load file [")):
            return str(save_path)
        if prompt == "Choice:":
            actor = active_actor()
            if actor == "Warpriest C":
                if not state["cast"]:
                    state["cast"] = True
                    return menu_choice("Cast")
                if not state["end_turn"]:
                    state["end_turn"] = True
                    return menu_choice("End Turn")
            return menu_choice("Quit")
        if prompt == "Spell number:":
            return menu_choice("Void Warp (", prefix=True)
        if prompt == "Casting mode:":
            return menu_choice("2 actions")
        if prompt == "Target number:":
            return menu_choice("Fighter M (fighter_m)")
        state["unexpected"].append(f"Unexpected input prompt: {prompt!r}")
        raise EOFError

    result = run_terminal(
        setup=S3_SETUP,
        rolls=(1, 2, 20, 3, 4, 5, 8, 20, 4, 3),
        save_path=save_path,
        input_fn=scripted_input,
        output_fn=output,
    )

    transcript = "\n".join(state["outputs"])
    assert result == 0
    assert state["unexpected"] == []
    assert state["save_load_stage"] == 3
    assert "choice owner: Fighter M" in transcript
    assert "Original: d20 8 + 8 = 16 vs DC 17." in transcript
    assert "Degree: Failure." in transcript
    assert "Spend 1 Hero Point and reroll" in transcript
    assert f"Saved encounter to {save_path}." in transcript
    assert f"Loaded encounter from {save_path}." in transcript
    assert "Fortitude save: d20 20" in transcript
    assert "Hero Point reroll: d20 20 + 8 = 28 vs DC 17; critical success." in transcript
    assert "Hero Points 0" in transcript


def test_s3_terminal_mixed_party_encounter_finishes_through_public_cli_actions() -> None:
    state, output, menu_choice, active_actor = _terminal_capture()
    state["active_actor"] = active_actor
    state["cast"] = False
    state["cleric_end"] = False
    state["fighter_m_stride"] = False
    state["fighter_m_strike"] = False
    state["fighter_m_end"] = False
    state["fighter_r_strike"] = False
    state["finished"] = False
    state["unexpected"] = []

    def scripted_input() -> str:
        prompt = str(state["prompt"])
        choice_block = str(state["choice_block"])
        if prompt == "Choice prompt action:":
            return menu_choice("Resolve this choice")
        if prompt == "Choice option number:":
            return _answer_choice_option(state)
        if prompt == "Choice:":
            actor = active_actor()
            if actor == "Warpriest C":
                if not state["cast"]:
                    state["cast"] = True
                    return menu_choice("Cast")
                state["cleric_end"] = True
                return menu_choice("End Turn")
            if actor == "Fighter M":
                if not state["fighter_m_stride"]:
                    state["fighter_m_stride"] = True
                    return menu_choice("Stride")
                if not state["fighter_m_strike"]:
                    state["fighter_m_strike"] = True
                    return menu_choice("Strike")
                state["fighter_m_end"] = True
                return menu_choice("End Turn")
            if actor == "Fighter R" and not state["fighter_r_strike"]:
                state["fighter_r_strike"] = True
                return menu_choice("Strike")
            state["finished"] = actor == "no active actor"
            return menu_choice("Quit")
        if prompt == "Spell number:":
            return menu_choice("Divine Lance (", prefix=True)
        if prompt == "Casting mode:":
            return menu_choice("2 actions")
        if prompt == "Stride path, in order (for example B2 C2 D3):":
            return "C1 D1 E1"
        if prompt == "Weapon / attack number:":
            actor = active_actor()
            return menu_choice("Longsword (longsword)" if actor == "Fighter M" else "Shortbow (shortbow)")
        if prompt == "Target number:":
            actor = active_actor()
            target = {
                "Warpriest C": "Guard Dog C (guard_dog_c)",
                "Fighter M": "Guard Dog A (guard_dog_a)",
                "Fighter R": "Guard Dog B (guard_dog_b)",
            }[actor]
            return menu_choice(target)
        if prompt == "Damage type:":
            return menu_choice("Slashing")
        if prompt == "Damage intent:":
            return menu_choice("Use attack default", prefix=True)
        state["unexpected"].append(f"Unexpected input prompt: {prompt!r}; choice={choice_block!r}")
        raise EOFError

    result = run_terminal(
        setup=S3_SETUP,
        rolls=(20, 19, 20, 1, 2, 3, 20, 4, 3, 20, 8, 20, 4, 7),
        input_fn=scripted_input,
        output_fn=output,
    )

    transcript = "\n".join(state["outputs"])
    assert result == 0
    assert state["unexpected"] == []
    assert all(
        state[key]
        for key in (
            "cast",
            "cleric_end",
            "fighter_m_stride",
            "fighter_m_strike",
            "fighter_m_end",
            "fighter_r_strike",
            "finished",
        )
    ), tuple((key, state[key]) for key in ("cast", "cleric_end", "fighter_m_stride", "fighter_m_strike", "fighter_m_end", "fighter_r_strike", "finished"))
    assert "Divine Lance deals 14 spirit to Guard Dog C." in transcript
    assert "1d8 (8) + 4 = 12; critical doubles to 24 slashing; target defeated" in transcript
    assert "critical doubles to 8, plus deadly 1d10 (7) = 15 piercing; target defeated" in transcript
    assert transcript.count("is defeated.") >= 3
    assert "Encounter finished." in transcript


def test_s3_terminal_repeating_bad_script_fails_at_bounded_capture_limit() -> None:
    output = BoundedTranscript(max_lines=32)

    with pytest.raises(AssertionError, match="transcript exceeded its capture limit"):
        run_terminal(
            setup=S3_SETUP,
            input_fn=lambda: "not a menu choice",
            output_fn=output.append,
        )

    assert len(output) == 32

    with pytest.raises(AssertionError, match="transcript exceeded its capture limit"):
        BoundedTranscript(max_chars=1).append("too much")
