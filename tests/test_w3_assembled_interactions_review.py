"""Independent assembled W3 play across caster, Fighter, and bomb effects.

Rule references: https://2e.aonprd.com/Feats.aspx?ID=4715,
https://2e.aonprd.com/Feats.aspx?ID=4780,
https://2e.aonprd.com/Equipment.aspx?ID=3292, and
https://2e.aonprd.com/Equipment.aspx?ID=3295.
"""

from __future__ import annotations

from dataclasses import replace
from types import MappingProxyType

import pytest

import pf2e.content as content
from pf2e.encounter import Encounter
from pf2e.fighter import CombatGrab
from pf2e.model import (
    Cast,
    CreaturePlacement,
    EncounterSetup,
    EndTurn,
    Position,
    QuickAlchemy,
    QuickBomber,
    ResultStatus,
    Strike,
    WidenSpell,
)
from pf2e.skill_actions import Escape
from pf2e.terminal import run_terminal
from pf2e.w3_caster_content import BATTLE_MAGIC_WIZARD_L1_WIDEN
from terminal_test_helpers import BoundedInput, BoundedTranscript


def _setup(monkeypatch) -> tuple[EncounterSetup, object]:
    # More HP lets all three families act in one continuous public fight.
    dog = replace(content.GUARD_DOG, definition_id="w3_review_tough_dog", hp=50)
    monkeypatch.setattr(
        content, "CREATURES", MappingProxyType({**content.CREATURES, dog.definition_id: dog})
    )
    setup = EncounterSetup(
        "w3_review_assembled", "W3 assembled interaction review", 8, 5,
        (
            CreaturePlacement("alchemist", "bomber_alchemist_level_2_condition_bombs", "Alchemist", "blue", Position(1, 1)),
            CreaturePlacement("fighter", "fighter_m_level_2_combat_grab", "Fighter", "blue", Position(2, 2)),
            CreaturePlacement("wizard", BATTLE_MAGIC_WIZARD_L1_WIDEN.definition_id, "Wizard", "blue", Position(1, 3)),
            CreaturePlacement("dog", dog.definition_id, "Dog", "red", Position(3, 2)),
            CreaturePlacement("far_dog", dog.definition_id, "Far Dog", "red", Position(5, 3)),
        ),
    )
    monkeypatch.setattr(
        content, "_STAGED_SETUPS",
        MappingProxyType({**content._STAGED_SETUPS, setup.setup_id: setup}),
    )
    return setup, dog


def _settle(game: Encounter) -> None:
    for _ in range(20):
        choice = game.inspect().choice
        if choice is None:
            return
        option = "keep" if any(row.option_id == "keep" for row in choice.options) else choice.options[0].option_id
        result = game.choose(choice.choice_id, option, choice.owner_actor_id)
        assert result.status in {ResultStatus.PAUSED, ResultStatus.COMPLETED}
    raise AssertionError("choice sequence did not settle")


def test_dread_grab_and_widen_interact_through_saved_public_play(monkeypatch, tmp_path) -> None:
    setup, dog = _setup(monkeypatch)
    game = Encounter.start(
        setup, rolls=(20, 5, 5, 1, 1, 20, 1, 20, 1, 20, 1, 1, 1, 1, 1)
    )
    _settle(game)
    assert game.inspect().turn_actor_id == "alchemist"
    assert game.execute(QuickAlchemy("create_consumable", "dread_ampoule_lesser")).status is ResultStatus.COMPLETED
    bomb = game.execute(QuickBomber("dog", "dread_ampoule_lesser"))
    assert bomb.status is ResultStatus.PAUSED
    path = tmp_path / "assembled-w3.json"
    game.save(path)
    game = Encounter.load(path)
    _settle(game)
    assert any(
        effect.kind == "frightened" and effect.target_actor_id == "dog" and effect.value == 2
        for effect in game._state.condition_effects
    )

    assert game.execute(EndTurn()).status is ResultStatus.COMPLETED
    assert game.inspect().turn_actor_id == "fighter"
    first = game.execute(Strike("dog", "longsword"))
    assert first.status is ResultStatus.PAUSED
    assert next(event.check for event in first.events if event.kind == "strike").dc == dog.ac - 2
    _settle(game)
    grab = game.execute(CombatGrab("dog", "longsword"))
    assert grab.status is ResultStatus.PAUSED
    game.save(path)
    game = Encounter.load(path)
    _settle(game)
    assert any(
        effect.kind == "grabbed" and effect.effect_id.startswith("combat_grab:")
        for effect in game._state.condition_effects
    )

    assert game.execute(EndTurn()).status is ResultStatus.COMPLETED
    assert game.inspect().turn_actor_id == "wizard"
    assert game.execute(WidenSpell()).status is ResultStatus.COMPLETED
    game.save(path)
    game = Encounter.load(path)
    cast = game.execute(Cast(
        "breathe_fire", actions=2, area_direction=Position(1, 0),
        slot_id="wizard_breathe_fire",
    ))
    assert cast.status is ResultStatus.COMPLETED
    saves = {event.target_id: event.check for event in cast.events if event.kind == "spell_save"}
    assert saves["dog"] is not None and saves["far_dog"] is not None
    assert saves["far_dog"].total - saves["dog"].total == 2
    assert {event.target_id for event in cast.events if event.kind == "spell_damage"} >= {"dog", "far_dog"}


def test_glue_and_grab_keep_separate_escape_identity(monkeypatch, tmp_path) -> None:
    setup, _ = _setup(monkeypatch)
    game = Encounter.start(setup, rolls=(20, 5, 5, 1, 1, 20, 20, 1, 20, 1, 20))
    _settle(game)
    assert game.execute(QuickAlchemy("create_consumable", "glue_bomb_lesser")).status is ResultStatus.COMPLETED
    assert game.execute(QuickBomber("dog", "glue_bomb_lesser")).status is ResultStatus.PAUSED
    _settle(game)
    glue = next(effect for effect in game._state.active_effects if effect.kind == "alchemy_glue_bomb_lesser")
    assert game.execute(EndTurn()).status is ResultStatus.COMPLETED
    assert game.execute(Strike("dog", "longsword")).status is ResultStatus.PAUSED
    _settle(game)
    assert game.execute(CombatGrab("dog", "longsword")).status is ResultStatus.PAUSED
    _settle(game)
    grab = next(effect for effect in game._state.condition_effects if effect.effect_id.startswith("combat_grab:"))

    path = tmp_path / "glue-grab.json"
    game.save(path)
    game = Encounter.load(path)
    assert any(effect.effect_id == glue.effect_id for effect in game._state.active_effects)
    assert any(effect.effect_id == grab.effect_id for effect in game._state.condition_effects)
    for expected in ("wizard", "dog"):
        assert game.execute(EndTurn()).status is ResultStatus.COMPLETED
        assert game.inspect().turn_actor_id == expected
    escaped = game.execute(Escape(grab.effect_id, "athletics"))
    assert escaped.status in {ResultStatus.PAUSED, ResultStatus.COMPLETED}
    _settle(game)
    assert not any(effect.effect_id == grab.effect_id for effect in game._state.condition_effects)
    assert any(effect.effect_id == glue.effect_id for effect in game._state.active_effects)


@pytest.mark.parametrize(
    ("setup_id", "actions", "attack", "expected"),
    (
        ("staged_fighter_level_1_snagging_strike", ("Snagging Strike", "Quit"), "Longsword", "is off-guard to"),
        ("staged_fighter_level_2_combat_grab", ("Strike", "Combat Grab", "Quit"), "Longsword", "grabbed by Combat Grab"),
        ("staged_fighter_level_2_brutish_shove", ("Strike", "Brutish Shove", "Quit"), "Greatsword", "off-guard to Brutish Shove"),
    ),
)
def test_terminal_executes_each_new_fighter_rider(
    setup_id: str, actions: tuple[str, ...], attack: str, expected: str,
) -> None:
    transcript = BoundedTranscript(max_lines=210, max_chars=35_000)
    state = {"menu": "", "prompt": ""}
    action_queue = iter(actions)

    def output(line: str) -> None:
        transcript.append(line)
        if line.startswith("1. "):
            state["menu"] = line
        if line.endswith((":", "?")):
            state["prompt"] = line

    def choose(label: str) -> str:
        for row in state["menu"].splitlines():
            number, text = row.split(". ", 1)
            if label in text:
                return number
        raise AssertionError(f"missing terminal menu item {label!r}: {state['menu']!r}")

    def scripted_input() -> str:
        prompt = state["prompt"]
        if prompt == "Choice prompt action:":
            return choose("Resolve this choice")
        if prompt == "Choice option number:":
            return choose("Keep")
        if prompt == "Choice:":
            return choose(next(action_queue))
        if prompt == "Weapon / attack number:":
            return choose(attack)
        if prompt in {"Longsword target:", "Greatsword target:", "Target number:"}:
            return choose("Guard Dog")
        if prompt == "Damage type:":
            return choose("Slashing")
        if prompt == "Damage intent:":
            return choose("Use attack default")
        if prompt == "On a hit, use failure effect?":
            return choose("Failure effect: off-guard")
        raise AssertionError(f"unexpected terminal prompt: {prompt!r}")

    assert run_terminal(
        setup=content.get_setup(setup_id), rolls=(20, 1, 12, 1, 12, 1),
        input_fn=BoundedInput(scripted_input, max_calls=35), output_fn=output,
    ) == 0
    rendered = "\n".join(transcript)
    assert "Rejected:" not in rendered
    assert expected in rendered
