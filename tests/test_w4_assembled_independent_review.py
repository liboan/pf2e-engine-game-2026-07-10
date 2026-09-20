"""Independent continuous W4 play across the three delivered content lanes."""

from __future__ import annotations

from dataclasses import replace
from types import MappingProxyType

import pf2e.content as content
from pf2e.encounter import Encounter
from pf2e.martial_defense import PointBlankStance
from pf2e.model import (
    Cackle, Cast, CreaturePlacement, EncounterSetup, EndTurn, EnergyAblation,
    PairedStrikeSelection, Position, ResultStatus, Strike,
)
from pf2e.w4_offensive import DoubleSlice
from pf2e.terminal import run_terminal
from terminal_test_helpers import BoundedInput, BoundedTranscript


def _assembled_setup(monkeypatch) -> EncounterSetup:
    dog = replace(content.GUARD_DOG, definition_id="w4_review_tough_dog", hp=100)
    monkeypatch.setattr(
        content, "CREATURES", MappingProxyType({**content.CREATURES, dog.definition_id: dog})
    )
    setup = EncounterSetup(
        "w4_review_cross_family", "W4 assembled cross-family review", 8, 5,
        (
            CreaturePlacement("slice", "w4_fighter_double_slice_level_1", "Slice Fighter", "blue", Position(3, 1)),
            CreaturePlacement("point", "w4_fighter_point_blank_stance_level_1", "Point Blank Fighter", "blue", Position(2, 2)),
            CreaturePlacement("wizard", "wizard_battle_magic_level_2_energy_ablation", "Energy Wizard", "blue", Position(1, 2)),
            CreaturePlacement("cleric", "warpriest_c_domain_initiate_weapon_surge", "Domain Cleric", "blue", Position(2, 3)),
            CreaturePlacement("witch", "faiths_flamekeeper_witch_level_1_cackle", "Cackle Witch", "blue", Position(1, 3)),
            CreaturePlacement("fox", "faiths_flamekeeper_fox", "Fox", "blue", Position(1, 3)),
            CreaturePlacement("dog", dog.definition_id, "Tough Guard Dog", "red", Position(3, 2)),
        ),
    )
    monkeypatch.setattr(
        content, "_STAGED_SETUPS", MappingProxyType({**content._STAGED_SETUPS, setup.setup_id: setup})
    )
    return setup


def _settle(game: Encounter, save_path) -> tuple[Encounter, set[str]]:
    seen: set[str] = set()
    for _ in range(40):
        choice = game.inspect().choice
        if choice is None:
            return game, seen
        seen.add(choice.kind)
        if choice.kind == "family_action" or choice.kind == "reactive_shield":
            before = game.inspect()
            game.save(save_path)
            game = Encounter.load(save_path)
            assert game.inspect() == before
            choice = game.inspect().choice
            assert choice is not None
        options = {option.option_id for option in choice.options}
        selection = (
            "use" if choice.kind == "reactive_shield" else
            "after" if choice.kind == "witch_restored_spirit_timing" else
            "keep" if "keep" in options else choice.options[0].option_id
        )
        result = game.choose(choice.choice_id, selection, choice.owner_actor_id)
        assert result.status in {ResultStatus.PAUSED, ResultStatus.COMPLETED}
    raise AssertionError("assembled choice chain did not settle")


def test_w4_cross_family_play_reaches_a_winner_after_saved_choices(monkeypatch, tmp_path) -> None:
    game = Encounter.start(_assembled_setup(monkeypatch), seed=0)
    save_path = tmp_path / "w4-cross-family.json"
    seen_choices: set[str] = set()
    first_actions: set[str] = set()
    cackled = False
    for _ in range(70):
        game, choices = _settle(game, save_path)
        seen_choices.update(choices)
        if game.inspect().winner_team is not None:
            break
        actor = game.inspect().turn_actor_id
        assert actor is not None
        if actor not in first_actions:
            commands = {
                "slice": (DoubleSlice(PairedStrikeSelection("dog", "longsword")),),
                "point": (PointBlankStance(), Strike("dog", "shortbow")),
                "wizard": (EnergyAblation("fire"), Cast("electric_arc", target_ids=("dog",))),
                "cleric": (Cast("weapon_surge"), Strike("dog", item_id="longsword")),
                "witch": (Cast("stoke_the_heart", "slice"),),
                "dog": (Strike("point", "jaws"),),
            }[actor]
            for command in commands:
                result = game.execute(command)
                assert result.status in {ResultStatus.PAUSED, ResultStatus.COMPLETED}, result.message
                game, choices = _settle(game, save_path)
                seen_choices.update(choices)
            first_actions.add(actor)
        elif actor == "witch" and not cackled:
            result = game.execute(Cackle())
            assert result.status in {ResultStatus.PAUSED, ResultStatus.COMPLETED}, result.message
            game, choices = _settle(game, save_path)
            seen_choices.update(choices)
            cackled = True
        elif actor == "dog":
            game.execute(Strike("point", "jaws"))
            game, choices = _settle(game, save_path)
            seen_choices.update(choices)
        elif actor == "wizard":
            game.execute(Cast("electric_arc", target_ids=("dog",)))
            game, choices = _settle(game, save_path)
            seen_choices.update(choices)
        elif actor != "witch":
            attack = "shortbow" if actor == "point" else "longsword"
            game.execute(Strike("dog", attack))
            game, choices = _settle(game, save_path)
            seen_choices.update(choices)
        if game.inspect().winner_team is not None:
            break
        assert game.execute(EndTurn()).status is ResultStatus.COMPLETED
    assert {"slice", "point", "wizard", "cleric", "witch", "dog"} <= first_actions
    assert cackled
    assert "family_action" in seen_choices
    assert game.inspect().winner_team == "blue"


def test_double_slice_into_reactive_shield_resumes_second_strike_after_load(monkeypatch, tmp_path) -> None:
    setup = EncounterSetup(
        "w4_review_slice_into_shield", "W4 Double Slice versus Reactive Shield", 5, 3,
        (
            CreaturePlacement("attacker", "w4_fighter_double_slice_level_1", "Attacker", "red", Position(1, 1)),
            CreaturePlacement("defender", "w4_fighter_reactive_shield_level_1", "Defender", "blue", Position(2, 1)),
        ),
    )
    monkeypatch.setattr(
        content, "_STAGED_SETUPS", MappingProxyType({**content._STAGED_SETUPS, setup.setup_id: setup})
    )
    game = Encounter.start(setup, rolls=(20, 1, 9, 1, 1, 1, 1, 1, 1, 1))
    for _ in range(4):
        choice = game.inspect().choice
        if choice is None:
            break
        assert game.choose(choice.choice_id, "keep", choice.owner_actor_id).status in {
            ResultStatus.PAUSED, ResultStatus.COMPLETED,
        }
    assert game.inspect().turn_actor_id == "attacker"
    assert game.execute(DoubleSlice(PairedStrikeSelection("defender", "longsword"))).status is ResultStatus.PAUSED
    choice = game.inspect().choice
    assert choice is not None and choice.kind == "attack_hero_reroll"
    assert game.choose(choice.choice_id, "keep", choice.owner_actor_id).status is ResultStatus.PAUSED
    choice = game.inspect().choice
    assert choice is not None and choice.kind == "reactive_shield"
    path = tmp_path / "w4-slice-shield.json"
    game.save(path)
    game = Encounter.load(path)
    assert game.inspect().choice == choice
    original_hp = game._state.creatures["defender"].hp
    used = game.choose(choice.choice_id, "use", choice.owner_actor_id)
    assert used.status is ResultStatus.PAUSED
    assert game._state.creatures["defender"].hp == original_hp
    assert not game._state.creatures["defender"].reaction_available
    assert game.inspect().choice is not None and game.inspect().choice.kind == "family_action"
    game, seen = _settle(game, path)
    assert "family_action" in seen
    assert game.inspect().choice is None
    assert game._state.creatures["attacker"].strikes_this_turn == 2


def test_terminal_selects_energy_type_then_casts_electric_arc() -> None:
    transcript = BoundedTranscript(max_lines=240, max_chars=38_000)
    state = {"menu": "", "prompt": "", "phase": "energy"}

    def output(line: str) -> None:
        transcript.append(line)
        if line.startswith("1. "):
            state["menu"] = line
        if line.endswith((":", "?")):
            state["prompt"] = line

    def number(label: str) -> str:
        for row in state["menu"].splitlines():
            value, text = row.split(". ", 1)
            if label in text:
                return value
        raise AssertionError(f"missing {label!r} in {state['menu']!r}")

    def scripted_input() -> str:
        prompt = state["prompt"]
        if prompt == "Choice prompt action:":
            return number("Resolve this choice")
        if prompt == "Choice option number:":
            return number("Keep")
        if prompt == "Choice:":
            if state["phase"] == "energy":
                state["phase"] = "cast"
                return number("Energy Ablation")
            if state["phase"] == "cast":
                state["phase"] = "quit"
                return number("Cast")
            return number("Quit")
        if prompt == "Energy type number:":
            return number("fire")
        if prompt == "Spell number:":
            return number("Electric Arc")
        if prompt == "Casting mode:":
            return number("2 actions")
        if prompt == "Prepared slot:":
            return "1"
        if prompt == "Target number:":
            return "1"
        raise AssertionError(f"unexpected terminal prompt: {prompt!r}")

    assert run_terminal(
        setup=content.get_setup("w4_energy_ablation_vs_guard_dog"),
        rolls=(20, 1, 1, 4, 4),
        input_fn=BoundedInput(scripted_input, max_calls=30), output_fn=output,
    ) == 0
    rendered = "\n".join(transcript)
    assert "shapes the next qualifying spell against fire energy" in rendered
    assert "commits Electric Arc" in rendered
    assert "Rejected:" not in rendered
