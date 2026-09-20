"""Finite W2 hostile/control spell-package checks.

Candidate assessment, checked 2026-09-20: Void Warp, Fear, Enfeeble, and
Command form a useful shared low-rank suppression package.  Each uses the
existing single-target save/condition routes, with distinct Fortitude/Will
and damage/action/condition outcomes.  Befuddle, Briny Bolt, and Kinetic Ram
were not selected because their distinctive stupefied, dazzled, or spell
attack-and-push behavior would require a new subsystem.

Sources: Void Warp (Player Core p. 366) https://2e.aonprd.com/Spells.aspx?ID=1745;
Fear (p. 331) https://2e.aonprd.com/Spells.aspx?ID=1524; Enfeeble (p. 329)
https://2e.aonprd.com/Spells.aspx?ID=1513; Command (p. 321)
https://2e.aonprd.com/Spells.aspx?ID=1470.
"""

from pathlib import Path

import pytest

from pf2e.content import get_definition, get_setup
from pf2e.encounter import Encounter
from pf2e.model import Cast, EndTurn, ResultStatus
from pf2e.terminal import run_terminal
from terminal_test_helpers import BoundedInput, BoundedTranscript


def _settle(game: Encounter) -> None:
    while (choice := game.inspect().choice) is not None:
        assert game.choose(choice.choice_id, "keep", choice.owner_actor_id).status in {
            ResultStatus.COMPLETED,
            ResultStatus.PAUSED,
        }


def test_suppression_alternates_preserve_finite_knowledge_and_slot_counts() -> None:
    standard_wizard = get_definition("wizard_battle_magic_level_1_staged")
    wizard = get_definition("wizard_battle_magic_level_1_suppression_spells_prepared")
    standard_witch = get_definition("faiths_flamekeeper_witch_level_1")
    witch = get_definition("faiths_flamekeeper_witch_level_1_suppression_spells_prepared")

    assert len(wizard.prepared_spells) == len(standard_wizard.prepared_spells)
    assert {slot.spell_id for slot in wizard.prepared_spells} >= {"void_warp", "fear", "command"}
    assert [entry.spell_id for entry in wizard.spell_substitution_book].count("command") == 1
    assert any("legally learned after the fixed starting spellbook" in note for note in wizard.sheet_notes)
    assert len(witch.prepared_spells) == len(standard_witch.prepared_spells)
    assert {slot.spell_id for slot in witch.prepared_spells} >= {"void_warp", "fear", "enfeeble"}
    assert "ten divine cantrips" in " ".join(witch.sheet_notes)
    assert "six rank-1 spells" in " ".join(witch.sheet_notes)


def test_witch_suppression_package_survives_save_then_finishes_public_encounter(tmp_path: Path) -> None:
    # Initiative; Fear failure; Enfeeble critical failure; Void Warp critical
    # failure, then its two d4 damage dice.
    game = Encounter.start(
        get_setup("faiths_flamekeeper_suppression_spells_vs_common_speaker"),
        rolls=(20, 1, 10, 1, 1, 1, 4, 4),
    )
    _settle(game)

    fear = game.execute(Cast("fear", "enemy"))
    assert fear.status is ResultStatus.COMPLETED
    assert any("frightened 2" in event.text for event in fear.events)
    assert game.execute(EndTurn()).status is ResultStatus.COMPLETED
    assert game.execute(EndTurn()).status is ResultStatus.COMPLETED

    enfeeble = game.execute(Cast("enfeeble", "enemy"))
    assert enfeeble.status is ResultStatus.COMPLETED
    assert any("enfeebled 3" in event.text for event in enfeeble.events)
    game.save(tmp_path / "suppression-effects.json")
    game = Encounter.load(tmp_path / "suppression-effects.json")
    # Fear's frightened value falls at the target's end turn; save the live
    # remaining one-point condition alongside Enfeeble's timed effect.
    assert any(effect.kind == "frightened" and effect.value == 1 for effect in game._state.condition_effects)
    assert any(effect.kind == "enfeebled" and effect.value == 3 for effect in game._state.active_effects)

    assert game.execute(EndTurn()).status is ResultStatus.COMPLETED
    assert game.execute(EndTurn()).status is ResultStatus.COMPLETED
    void_warp = game.execute(Cast("void_warp", "enemy"))
    assert void_warp.status is ResultStatus.COMPLETED
    assert not game.inspect().in_progress
    assert game._state.creatures["enemy"].defeated


def test_wizard_learned_command_is_playable_and_saved(tmp_path: Path) -> None:
    game = Encounter.start(
        get_setup("battle_magic_wizard_suppression_spells_vs_common_speaker"),
        rolls=(20, 1, 1),
    )
    _settle(game)

    result = game.execute(Cast("command", "enemy", spell_mode="stand"))
    assert result.status is ResultStatus.COMPLETED
    assert any(event.kind == "command_save" for event in result.events)
    game.save(tmp_path / "wizard-command.json")
    restored = Encounter.load(tmp_path / "wizard-command.json")
    command = next(effect for effect in restored._state.condition_effects if effect.kind == "commanded")
    assert (command.value, command.command_mode, command.source_actor_id) == (3, "stand", "wizard")


@pytest.mark.parametrize(
    ("setup_id", "caster_id"),
    (
        ("faiths_flamekeeper_suppression_spells_vs_common_speaker", "witch"),
        ("battle_magic_wizard_suppression_spells_vs_common_speaker", "wizard"),
    ),
)
def test_prepared_fear_critical_failure_fleeing_round_trips(
    tmp_path: Path,
    setup_id: str,
    caster_id: str,
) -> None:
    game = Encounter.start(get_setup(setup_id), rolls=(20, 1, 1))
    _settle(game)
    result = game.execute(Cast("fear", "enemy"))
    assert result.status is ResultStatus.COMPLETED
    assert any(effect.kind == "fleeing" for effect in game._state.active_effects)

    path = tmp_path / f"{caster_id}-prepared-fear.json"
    game.save(path)
    restored = Encounter.load(path)
    fleeing = next(effect for effect in restored._state.active_effects if effect.kind == "fleeing")
    assert (fleeing.source_actor_id, fleeing.target_actor_id, fleeing.value) == (caster_id, "enemy", 1)


def test_terminal_casts_wizard_suppression_fear() -> None:
    transcript = BoundedTranscript(max_lines=220, max_chars=30_000)
    state = {"menu": "", "prompt": "", "cast": True}

    def output(line: str) -> None:
        transcript.append(line)
        if line.startswith("1. "):
            state["menu"] = line
        if line.endswith(":"):
            state["prompt"] = line

    def choose(label: str, *, prefix: bool = False) -> str:
        for row in state["menu"].splitlines():
            number, text = row.split(". ", 1)
            if text.startswith(label) if prefix else text == label:
                return number
        raise AssertionError(f"missing terminal menu item {label!r}: {state['menu']!r}")

    def scripted_input() -> str:
        prompt = state["prompt"]
        if prompt == "Choice prompt action:":
            return choose("Resolve this choice")
        if prompt == "Choice option number:":
            return choose("Keep initiative") if "Keep initiative" in state["menu"] else choose("Keep result")
        if prompt == "Choice:":
            if state["cast"]:
                state["cast"] = False
                return choose("Cast")
            return choose("Quit")
        if prompt == "Spell number:":
            return choose("Fear", prefix=True)
        if prompt == "Casting mode:":
            return choose("2 actions")
        if prompt == "Prepared slot:":
            return choose("wizard_fear", prefix=True)
        if prompt == "Target number:":
            return "1"
        raise AssertionError(f"unexpected terminal prompt: {prompt!r}")

    assert run_terminal(
        setup=get_setup("battle_magic_wizard_suppression_spells_vs_common_speaker"),
        rolls=(20, 1, 1),
        input_fn=BoundedInput(scripted_input, max_calls=30),
        output_fn=output,
    ) == 0
    rendered = "\n".join(transcript)
    assert "Rejected:" not in rendered, rendered
    assert "commits Fear" in rendered
    assert "frightened 3" in rendered
