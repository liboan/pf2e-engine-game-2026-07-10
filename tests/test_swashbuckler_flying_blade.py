"""Public Flying Blade throws for the staged Braggart.

Rules checked 2026-09-16:

* Flying Blade: https://2e.aonprd.com/Feats.aspx?ID=6130
* Precise Strike and Panache: https://2e.aonprd.com/Classes.aspx?ID=63
* Confident Finisher: https://2e.aonprd.com/Actions.aspx?ID=2818
* Dagger: https://2e.aonprd.com/Weapons.aspx?ID=358
"""

from pathlib import Path

import pytest

import pf2e.content as content
from pf2e.content import get_definition
from pf2e.encounter import Encounter
from pf2e.model import Choose, CreaturePlacement, EncounterSetup, EndTurn, Interact, Position, ResultStatus, Step, Strike
from pf2e.skill_actions import Demoralize
from pf2e.swashbuckler import ConfidentFinisher, precise_strike_damage_term
from pf2e.terminal import run_terminal
from terminal_test_helpers import BoundedInput, BoundedTranscript


SETUP_ID = "staged_braggart_swashbuckler_vs_guard_dog"


def _setup(setup_id: str, *, dog_position: Position, second_dog: bool = False) -> EncounterSetup:
    base = content.get_setup(SETUP_ID)
    placements = [
        CreaturePlacement(
            "braggart", base.placements[0].definition_id, "Braggart Swashbuckler", "blue", Position(1, 1)
        ),
        CreaturePlacement(
            "braggart_dog", base.placements[1].definition_id, "Guard Dog", "red", dog_position
        ),
    ]
    if second_dog:
        placements.append(
            CreaturePlacement(
                "reserve_dog", base.placements[1].definition_id, "Reserve Guard Dog", "red", Position(5, 1)
            )
        )
    return EncounterSetup(setup_id, "Flying Blade public play", 6, 3, tuple(placements))


def _admit(monkeypatch: pytest.MonkeyPatch, setup: EncounterSetup) -> EncounterSetup:
    monkeypatch.setattr(content, "_STAGED_SETUPS", content._STAGED_SETUPS | {setup.setup_id: setup})
    return setup


def _settle(game: Encounter) -> None:
    for _ in range(8):
        choice = game.inspect().choice
        if choice is None:
            return
        option = "keep" if any(item.option_id == "keep" for item in choice.options) else choice.options[0].option_id
        result = game.choose(choice.choice_id, option, choice.owner_actor_id)
        assert result.status in {ResultStatus.PAUSED, ResultStatus.COMPLETED}
    raise AssertionError("initiative did not settle")


def _choose_keep(game: Encounter):
    choice = game.inspect().choice
    assert choice is not None
    return game.choose(choice.choice_id, "keep", choice.owner_actor_id)


def _actor(game: Encounter, actor_id: str):
    return next(actor for actor in game.inspect().actors if actor.actor_id == actor_id)


def _gain_panache(game: Encounter, target_id: str) -> None:
    result = game.execute(Demoralize(target_id, use_intimidating_glare=True))
    if result.inspection.choice is not None:
        result = _choose_keep(game)
    assert result.status is ResultStatus.COMPLETED
    assert _actor(game, "braggart").panache


def test_flying_blade_content_uses_strength_damage_and_first_increment_precision_only() -> None:
    definition = get_definition("swashbuckler_braggart_level_1")
    melee, thrown = definition.attacks
    assert melee.attack_id == "dagger"
    assert thrown.attack_id == "dagger_thrown"
    assert thrown.range_increment_ft == 10 and thrown.max_range_ft == 60
    assert thrown.damage_attribute == "strength" and thrown.damage_modifier == 2
    assert precise_strike_damage_term(definition, melee) is not None
    assert precise_strike_damage_term(definition, thrown, distance_ft=10) is not None
    assert precise_strike_damage_term(definition, thrown, distance_ft=15) is None
    assert precise_strike_damage_term(definition, thrown, distance_ft=10, finisher=True).dice == (6, 6)


def test_far_ordinary_throw_has_range_penalty_no_precision_and_lands_selected_dagger(monkeypatch: pytest.MonkeyPatch) -> None:
    setup = _admit(monkeypatch, _setup("flying_blade_far_throw", dog_position=Position(4, 1)))
    game = Encounter.start(setup, rolls=(20, 1, 10, 2))
    _settle(game)
    result = game.execute(Strike("braggart_dog", "dagger_thrown", item_id="braggart:dagger_1"))
    assert result.status is ResultStatus.PAUSED
    result = _choose_keep(game)
    check = next(event.check for event in result.events if event.kind == "strike")
    damage = next(event.damage for event in result.events if event.damage is not None)
    assert check is not None and (check.die, check.modifier, check.total, check.dc) == (10, 5, 15, 15)
    assert damage is not None and damage.total == 4
    assert [component.source for component in damage.components] == ["dagger_thrown"]
    assert _actor(game, "braggart").held_items == ()
    assert result.inspection.ground_items == ((Position(4, 1), ("braggart:dagger_1",)),)

    before, dice_before = game.inspect(), game._dice.to_data()
    rejected = game.execute(Strike("braggart_dog", "dagger_thrown", item_id="braggart:dagger_1"))
    assert rejected.status is ResultStatus.REJECTED
    assert rejected.inspection == before and game._dice.to_data() == dice_before


def test_missed_thrown_dagger_still_lands_in_the_target_cell(monkeypatch: pytest.MonkeyPatch) -> None:
    setup = _admit(monkeypatch, _setup("flying_blade_missed_throw", dog_position=Position(4, 1)))
    game = Encounter.start(setup, rolls=(20, 1, 1))
    _settle(game)
    result = game.execute(Strike("braggart_dog", "dagger_thrown", item_id="braggart:dagger_1"))
    assert result.status is ResultStatus.PAUSED
    result = _choose_keep(game)
    assert any(event.kind == "thrown_item_landed" for event in result.events)
    assert not any(event.damage is not None for event in result.events)
    assert result.inspection.ground_items == ((Position(4, 1), ("braggart:dagger_1",)),)


def test_first_increment_thrown_finisher_saves_landed_identity_and_far_finisher_rejects_atomically(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    near_setup = _admit(monkeypatch, _setup("flying_blade_near_finisher", dog_position=Position(3, 1)))
    near = Encounter.start(near_setup, rolls=(20, 1, 8, 7, 1, 1, 1))
    _settle(near)
    _gain_panache(near, "braggart_dog")
    result = near.execute(ConfidentFinisher("braggart_dog", "dagger_thrown", item_id="braggart:dagger_1"))
    assert result.status is ResultStatus.PAUSED
    if result.inspection.choice is not None and result.inspection.choice.kind == "attack_hero_reroll":
        result = _choose_keep(near)
    choice = result.inspection.choice
    assert choice is not None and choice.kind == "family_action"
    assert _actor(near, "braggart").held_items == ()
    assert result.inspection.ground_items == ((Position(3, 1), ("braggart:dagger_1",)),)
    path = tmp_path / "saved-thrown-finisher.json"
    near.save(path)
    restored = Encounter.load(path)
    assert restored.inspect() == result.inspection
    resolved = restored.execute(Choose(choice.choice_id, "full_damage", "braggart"))
    assert resolved.status is ResultStatus.COMPLETED
    assert _actor(restored, "braggart_dog").hp == 3

    far_setup = _admit(monkeypatch, _setup("flying_blade_far_finisher", dog_position=Position(4, 1)))
    far = Encounter.start(far_setup, rolls=(20, 1, 8))
    _settle(far)
    _gain_panache(far, "braggart_dog")
    before, dice_before = far.inspect(), far._dice.to_data()
    rejected = far.execute(ConfidentFinisher("braggart_dog", "dagger_thrown", item_id="braggart:dagger_1"))
    assert rejected.status is ResultStatus.REJECTED
    assert "first range increment" in rejected.message
    assert rejected.inspection == before and far._dice.to_data() == dice_before


def test_thrown_dagger_can_be_recovered_after_target_falls_while_another_enemy_remains(monkeypatch: pytest.MonkeyPatch) -> None:
    setup = _admit(monkeypatch, _setup("flying_blade_recovery", dog_position=Position(3, 1), second_dog=True))
    game = Encounter.start(
        setup,
        rolls=(20, 1, 1, 8, 7, 4, 1, 1),
    )
    _settle(game)
    _gain_panache(game, "braggart_dog")
    result = game.execute(ConfidentFinisher("braggart_dog", "dagger_thrown", item_id="braggart:dagger_1"))
    if result.inspection.choice is not None and result.inspection.choice.kind == "attack_hero_reroll":
        result = _choose_keep(game)
    choice = game.inspect().choice
    assert choice is not None and choice.kind == "family_action"
    result = game.execute(Choose(choice.choice_id, "full_damage", "braggart"))
    assert result.status is ResultStatus.COMPLETED and result.inspection.in_progress
    assert _actor(game, "braggart_dog").defeated
    assert game.execute(EndTurn()).status is ResultStatus.COMPLETED
    for _ in range(3):
        if game.inspect().turn_actor_id == "braggart":
            break
        assert game.execute(EndTurn()).status is ResultStatus.COMPLETED
    assert game.inspect().turn_actor_id == "braggart"
    assert game.execute(Step(Position(2, 1))).status is ResultStatus.COMPLETED
    assert game.inspect().ground_items == ((Position(3, 1), ("braggart:dagger_1",)),)
    assert ("retrieve", "braggart:dagger_1") in game.options().interact_options
    recovered = game.execute(Interact("retrieve", "braggart:dagger_1"))
    assert recovered.status is ResultStatus.COMPLETED
    assert _actor(game, "braggart").held_items == ("braggart:dagger_1",)


def test_terminal_far_throw_draw_step_and_first_increment_finisher_win(monkeypatch: pytest.MonkeyPatch) -> None:
    transcript = BoundedTranscript()
    state = {"menu": "", "prompt": "", "choice": "", "phase": "throw"}

    def output(line: str) -> None:
        transcript.append(line)
        if line.startswith("1. "):
            state["menu"] = line
        if "choice owner:" in line:
            state["choice"] = line
        if line.endswith(":"):
            state["prompt"] = line

    def choose(label: str, *, prefix: bool = False) -> str:
        for row in state["menu"].splitlines():
            parts = row.split(". ", 1)
            if len(parts) == 2 and (parts[1].startswith(label) if prefix else parts[1] == label):
                return parts[0]
        raise AssertionError(f"menu label missing: {label!r} in {state['menu']!r}")

    def scripted_input() -> str:
        prompt = state["prompt"]
        if prompt == "Choice prompt action:":
            return choose("Resolve this choice")
        if prompt == "Choice option number:":
            if "Apply full Strike damage" in state["menu"]:
                return choose("Apply full Strike damage")
            if "Keep result" in state["menu"]:
                return choose("Keep result")
            if "Keep initiative" in state["menu"]:
                return choose("Keep initiative")
            return choose("Keep the current result")
        if prompt == "Choice:":
            phase = state["phase"]
            if phase == "throw":
                state["phase"] = "draw"
                return choose("Strike")
            if phase == "draw":
                state["phase"] = "step"
                return choose("Interact")
            if phase == "step":
                state["phase"] = "dog_end"
                return choose("Step")
            if phase == "dog_end":
                state["phase"] = "demoralize"
                return choose("End Turn")
            if phase == "demoralize":
                state["phase"] = "finisher"
                return choose("Demoralize")
            if phase == "finisher":
                state["phase"] = "done"
                return choose("Confident Finisher")
            return choose("Quit")
        if prompt == "Weapon / attack number:":
            return choose("Dagger (Thrown)", prefix=True)
        if prompt.endswith("target:") or prompt == "Target number:":
            return choose("Guard Dog", prefix=True)
        if prompt == "Damage intent:":
            return choose("Use attack default", prefix=True)
        if prompt == "Interact option:":
            return choose("Draw: braggart:dagger_2")
        if prompt == "Step destination:":
            return "C2"
        if prompt.startswith("Use Intimidating Glare"):
            return "y"
        raise AssertionError(f"unexpected terminal prompt: {prompt!r}")

    setup = _admit(monkeypatch, _setup("flying_blade_terminal", dog_position=Position(4, 1)))
    result = run_terminal(
        setup=setup,
        rolls=(20, 1, 10, 2, 8, 7, 1, 1, 1),
        input_fn=BoundedInput(scripted_input, max_calls=80),
        output_fn=output,
    )
    rendered = "\n".join(transcript)
    assert result == 0
    assert "Dagger (Thrown)" in rendered
    assert "Guard Dog (red) — HP 0/8" in rendered
