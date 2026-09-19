"""Bounded terminal coverage for the physical-item Runic Weapon cast."""

from __future__ import annotations

import re
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
from types import MappingProxyType

import pytest
import pf2e.content as content
from pf2e.content import ANGELIC_FIRST_CAST_SETUP
from pf2e.model import Position, SpellTargetOption
from pf2e.terminal import _choose_cast_inputs, run_terminal


def _menu_choice(menu: str, label: str) -> str:
    for line in menu.splitlines():
        match = re.match(r"(\d+)\.\s+(.*)", line)
        if match and match.group(2) == label:
            return match.group(1)
    raise AssertionError(f"menu label missing: {label!r}\n{menu}")


def test_runic_cast_selects_a_readable_held_or_ground_item_without_creature_target() -> None:
    spell = SimpleNamespace(
        spell_id="runic_weapon",
        name="Runic Weapon",
        traits=("concentrate", "manipulate"),
        action_costs=(2,),
        slots=(("angelic_rank1", "rank1"),),
        target_options=(SpellTargetOption(2, ()),),
        unavailable_reason=None,
    )
    inspection = SimpleNamespace(
        actors=(
            SimpleNamespace(
                actor_id="sorcerer_ally",
                label="Sorcerer's Ally",
                held_items=("sorcerer_ally:longsword",),
            ),
            SimpleNamespace(actor_id="fighter", label="Fighter", held_items=()),
        ),
        ground_items=((Position(3, 2), ("ground:shortsword", "ground:rock")),),
    )
    output: list[str] = []
    inputs = iter(("1", "1", "1", "2"))  # spell, mode, slot, ground shortsword.

    selection = _choose_cast_inputs((spell,), inspection, lambda: next(inputs), output.append)

    assert selection == ("runic_weapon", None, 2, "angelic_rank1", None, "ground:shortsword")
    transcript = "\n".join(output)
    assert "Held by Sorcerer's Ally: Longsword (sorcerer_ally:longsword)" in transcript
    assert "On ground at D3: Shortsword (ground:shortsword)" in transcript
    assert "On ground at D3: Rock (ground:rock)" in transcript
    assert "the engine checks weapon eligibility" in transcript


def test_terminal_casts_runic_weapon_on_selected_ally_item_and_round_trips_save(
    tmp_path: Path,
) -> None:
    save_path = tmp_path / "runic-weapon-terminal.json"
    state: dict[str, object] = {
        "inspection": "",
        "menu": "",
        "prompt": "",
        "choice_block": "",
        "cast": False,
        "saved": False,
        "loaded": False,
        "outputs": [],
    }

    def output(line: str) -> None:
        state["outputs"].append(line)  # type: ignore[union-attr]
        if line.startswith("Round "):
            state["inspection"] = line
        if line.startswith("1. "):
            state["menu"] = line
        if "choice owner:" in line:
            state["choice_block"] = line
        if (
            line == "Choice:"
            or line.endswith(":")
            or line.startswith(("Save file [", "Load file ["))
        ):
            state["prompt"] = line

    def scripted_input() -> str:
        prompt = state["prompt"]
        menu = state["menu"]
        if prompt == "Choice prompt action:":
            return _menu_choice(menu, "Resolve this choice")  # type: ignore[arg-type]
        if prompt == "Choice option number:":
            if "Runic Weapon" in str(state["choice_block"]):
                return _menu_choice(menu, "Willing")  # type: ignore[arg-type]
            return _menu_choice(menu, "Keep initiative")  # type: ignore[arg-type]
        if prompt.startswith("Save file [") or prompt.startswith("Load file ["):
            return str(save_path)
        if prompt == "Choice:":
            if not state["cast"]:
                state["cast"] = True
                return _menu_choice(menu, "Cast")  # type: ignore[arg-type]
            if not state["saved"]:
                state["saved"] = True
                return _menu_choice(menu, "Save")  # type: ignore[arg-type]
            if not state["loaded"]:
                state["loaded"] = True
                return _menu_choice(menu, "Load")  # type: ignore[arg-type]
            return _menu_choice(menu, "Quit")  # type: ignore[arg-type]
        if prompt == "Spell number:":
            return next(
                line.split(". ", 1)[0]
                for line in menu.splitlines()  # type: ignore[union-attr]
                if ". Runic Weapon (" in line
            )
        if prompt == "Casting mode:":
            return _menu_choice(menu, "2 actions")  # type: ignore[arg-type]
        if prompt == "Prepared slot:":
            return _menu_choice(menu, "angelic_rank1 (rank1)")  # type: ignore[arg-type]
        if prompt == "Item number:":
            return _menu_choice(
                menu, "Held by Sorcerer's Ally: Longsword (sorcerer_ally:longsword)"  # type: ignore[arg-type]
            )
        raise AssertionError(f"unexpected terminal prompt: {prompt!r}")

    status = run_terminal(
        setup=ANGELIC_FIRST_CAST_SETUP,
        rolls=(20, 1, 1),
        save_path=save_path,
        input_fn=scripted_input,
        output_fn=output,
    )

    transcript = "\n".join(state["outputs"])  # type: ignore[arg-type]
    assert status == 0
    assert state["cast"] is True
    assert state["saved"] is True and state["loaded"] is True
    assert "Angelic Sorcerer commits Runic Weapon (2 action(s)) on sorcerer_ally:longsword." in transcript
    assert "Sorcerer's Ally accepts Runic Weapon on sorcerer_ally:longsword." in transcript
    assert "Runic Weapon enchants sorcerer_ally:longsword" in transcript
    assert f"Saved encounter to {save_path}." in transcript
    assert f"Loaded encounter from {save_path}." in transcript


def test_terminal_dim_runic_saves_item_concealment_then_applies_effect(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    caster_id = "terminal_dim_runic_caster"
    caster = replace(
        content.ANGELIC_SORCERER_STAGED,
        definition_id=caster_id,
        hero_points=1,
    )
    setup = replace(
        ANGELIC_FIRST_CAST_SETUP,
        setup_id="terminal_dim_runic_saved_target",
        ambient_light="dim",
        placements=tuple(
            replace(placement, definition_id=caster_id)
            if placement.actor_id == "angelic_sorcerer" else placement
            for placement in ANGELIC_FIRST_CAST_SETUP.placements
        ),
    )
    monkeypatch.setattr(
        content,
        "_STAGED_CREATURES",
        MappingProxyType({**content._STAGED_CREATURES, caster_id: caster}),
    )
    monkeypatch.setattr(
        content,
        "_STAGED_SETUPS",
        MappingProxyType({**content._STAGED_SETUPS, setup.setup_id: setup}),
    )
    save_path = tmp_path / "dim-runic-terminal.json"
    state: dict[str, object] = {
        "menu": "",
        "prompt": "",
        "choice_block": "",
        "cast": False,
        "saved": False,
        "loaded": False,
        "resolved": False,
        "outputs": [],
    }

    def output(line: str) -> None:
        state["outputs"].append(line)  # type: ignore[union-attr]
        if line.startswith("1. "):
            state["menu"] = line
        if "choice owner:" in line:
            state["choice_block"] = line
        if (
            line == "Choice:"
            or line.endswith(":")
            or line.startswith(("Save file [", "Load file ["))
        ):
            state["prompt"] = line

    def scripted_input() -> str:
        prompt = state["prompt"]
        menu = state["menu"]
        choice_block = str(state["choice_block"])
        if prompt == "Choice prompt action:":
            if "concealment flat check" in choice_block and not state["saved"]:
                state["saved"] = True
                return _menu_choice(menu, "Save")  # type: ignore[arg-type]
            if "concealment flat check" in choice_block and not state["loaded"]:
                state["loaded"] = True
                return _menu_choice(menu, "Load")  # type: ignore[arg-type]
            if "concealment flat check" in choice_block and not state["resolved"]:
                state["resolved"] = True
            return _menu_choice(menu, "Resolve this choice")  # type: ignore[arg-type]
        if prompt == "Choice option number:":
            for label in ("Willing", "Keep result", "Keep initiative"):
                try:
                    return _menu_choice(menu, label)  # type: ignore[arg-type]
                except AssertionError:
                    continue
            raise AssertionError(f"unexpected choice options: {menu!r}")
        if prompt.startswith("Save file [") or prompt.startswith("Load file ["):
            return str(save_path)
        if prompt == "Choice:":
            if not state["cast"]:
                state["cast"] = True
                return _menu_choice(menu, "Cast")  # type: ignore[arg-type]
            return _menu_choice(menu, "Quit")  # type: ignore[arg-type]
        if prompt == "Spell number:":
            return next(
                line.split(". ", 1)[0]
                for line in menu.splitlines()  # type: ignore[union-attr]
                if ". Runic Weapon (" in line
            )
        if prompt == "Casting mode:":
            return _menu_choice(menu, "2 actions")  # type: ignore[arg-type]
        if prompt == "Prepared slot:":
            return _menu_choice(menu, "angelic_rank1 (rank1)")  # type: ignore[arg-type]
        if prompt == "Item number:":
            return _menu_choice(
                menu,
                "Held by Sorcerer's Ally: Longsword (sorcerer_ally:longsword)",  # type: ignore[arg-type]
            )
        raise AssertionError(f"unexpected terminal prompt: {prompt!r}")

    status = run_terminal(
        setup=setup,
        rolls=(20, 1, 1, 5),
        save_path=save_path,
        input_fn=scripted_input,
        output_fn=output,
    )
    transcript = "\n".join(state["outputs"])  # type: ignore[arg-type]
    assert status == 0
    assert state["saved"] is True and state["loaded"] is True
    assert state["resolved"] is True
    assert "DC 5 concealment flat check" in transcript
    assert f"Saved encounter to {save_path}." in transcript
    assert f"Loaded encounter from {save_path}." in transcript
    assert "Runic Weapon enchants sorcerer_ally:longsword" in transcript
