"""Public Battle Magic Shield cantrip behavior."""

from dataclasses import replace
from pathlib import Path

import pytest

import pf2e.content as content
from pf2e.content import get_definition, get_setup
from pf2e.encounter import Encounter
from pf2e.model import Cast, Choose, CreaturePlacement, EncounterSetup, EndTurn, Position, ResultStatus, Strike
from pf2e.typed_defense_content import WAYSTONE_SENTINEL
from pf2e.wizard_content import BATTLE_MAGIC_WIZARD
from pf2e.terminal import run_terminal
from terminal_test_helpers import BoundedInput, BoundedTranscript


def _choose(game: Encounter, option_id: str):
    choice = game.inspect().choice
    assert choice is not None
    return game.execute(Choose(choice.choice_id, option_id, choice.owner_actor_id))


def _settle_initiative(game: Encounter) -> None:
    while game.inspect().choice is not None:
        assert _choose(game, "keep").status in {ResultStatus.COMPLETED, ResultStatus.PAUSED}


def test_shield_is_hand_free_one_action_ac_and_expires_on_caster_turn() -> None:
    game = Encounter.start(get_setup("staged_battle_magic_wizard_vs_two_guard_dogs"), rolls=(20, 1, 1))
    _settle_initiative(game)
    shield_option = next(option for option in game.options().spells if option.spell_id == "shield")
    assert shield_option.target_options[0].targets == ()
    cast = game.execute(Cast("shield"))
    wizard = next(actor for actor in game.inspect().actors if actor.actor_id == "wizard")
    assert cast.status is ResultStatus.COMPLETED
    assert wizard.ac == 16 and wizard.actions_remaining == 2
    # Equal circumstance cover cannot stack; a stronger circumstance bonus
    # replaces the Shield bonus through the ordinary modifier combiner.
    wizard_state = game._state.creatures["wizard"]
    assert game._effective_ac(wizard_state, state=game._state, lesser_cover=True) == 16
    assert game._effective_ac(wizard_state, state=game._state, taking_cover=True) == 19
    assert game._state.creatures["wizard"].magic_shield_expires_at_start == 2
    game.execute(EndTurn())
    game.execute(EndTurn())
    game.execute(EndTurn())
    wizard = next(actor for actor in game.inspect().actors if actor.actor_id == "wizard")
    assert wizard.ac == 15 and game._state.creatures["wizard"].magic_shield_expires_at_start == 0


def test_magic_shield_block_saves_physical_damage_without_item_hp(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    setup = EncounterSetup(
        setup_id="test_magic_shield_physical",
        name="Magic Shield physical Block",
        width=4,
        height=3,
        placements=(
            CreaturePlacement("wizard", BATTLE_MAGIC_WIZARD.definition_id, "Wizard", "blue", Position(1, 1)),
            CreaturePlacement("dog", "guard_dog_mc2924", "Dog", "red", Position(2, 1)),
        ),
    )
    monkeypatch.setattr(content, "_STAGED_SETUPS", content._STAGED_SETUPS | {setup.setup_id: setup})
    game = Encounter.start(setup, rolls=(20, 1, 10, 4, 20, 4))
    _settle_initiative(game)
    assert "shield_cantrip" in get_definition(BATTLE_MAGIC_WIZARD.definition_id).abilities
    assert game._state.creatures["wizard"].reaction_available
    assert game.execute(Cast("shield")).status is ResultStatus.COMPLETED
    assert game.execute(EndTurn()).status is ResultStatus.COMPLETED
    paused = game.execute(Strike("wizard"))
    choice = paused.inspection.choice
    assert paused.status is ResultStatus.PAUSED
    assert choice is not None and choice.kind == "shield_block"
    declined = _choose(game, "decline")
    assert declined.status is ResultStatus.COMPLETED
    wizard = game._state.creatures["wizard"]
    assert wizard.magic_shield_expires_at_start == 2 and wizard.reaction_available
    paused = game.execute(Strike("wizard"))
    choice = paused.inspection.choice
    assert paused.status is ResultStatus.PAUSED
    assert choice is not None and choice.kind == "shield_block"
    saved = tmp_path / "magic-shield-physical.json"
    game.save(saved)
    game = Encounter.load(saved)
    resolved = _choose(game, "block")
    block = next(event.shield_block for event in resolved.events if event.shield_block is not None)
    assert block is not None and block.magic and block.hardness == 5 and block.damage_to_shield == 0
    wizard = game._state.creatures["wizard"]
    assert wizard.magic_shield_expires_at_start == 0
    assert wizard.shield_recast_available_at_seconds == 600
    assert game.execute(Cast("shield")).status is ResultStatus.REJECTED


def test_declined_magic_shield_survives_a_knockout_until_its_turn_expiry(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    knocked_wizard = replace(BATTLE_MAGIC_WIZARD, definition_id="test_shield_knockout_wizard", hp=5)
    setup = EncounterSetup(
        setup_id="test_magic_shield_knockout",
        name="Magic Shield knockout duration",
        width=4,
        height=3,
        placements=(
            CreaturePlacement("wizard", knocked_wizard.definition_id, "Wizard", "blue", Position(1, 1)),
            CreaturePlacement("dog", "guard_dog_mc2924", "Dog", "red", Position(2, 1)),
        ),
    )
    monkeypatch.setattr(
        content, "_STAGED_CREATURES",
        content._STAGED_CREATURES | {knocked_wizard.definition_id: knocked_wizard},
    )
    monkeypatch.setattr(content, "_STAGED_SETUPS", content._STAGED_SETUPS | {setup.setup_id: setup})
    game = Encounter.start(setup, rolls=(20, 1, 10, 4))
    _settle_initiative(game)
    assert game.execute(Cast("shield")).status is ResultStatus.COMPLETED
    assert game.execute(EndTurn()).status is ResultStatus.COMPLETED
    assert game.execute(Strike("wizard")).status is ResultStatus.PAUSED
    knockout = _choose(game, "decline")
    assert knockout.status is ResultStatus.PAUSED
    assert game.inspect().choice is not None and game.inspect().choice.kind == "heroic_recovery_damage"
    assert _choose(game, "normal").status is ResultStatus.COMPLETED
    wizard = game._state.creatures["wizard"]
    assert wizard.unconscious and not wizard.reaction_available
    assert wizard.magic_shield_expires_at_start == 2
    saved = tmp_path / "magic-shield-knockout.json"
    game.save(saved)
    assert Encounter.load(saved)._state.creatures["wizard"].magic_shield_expires_at_start == 2


def test_magic_shield_block_accepts_spell_damage(monkeypatch: pytest.MonkeyPatch) -> None:
    setup = EncounterSetup(
        setup_id="test_magic_shield_spell",
        name="Magic Shield spell Block",
        width=5,
        height=3,
        placements=(
            CreaturePlacement("blue", BATTLE_MAGIC_WIZARD.definition_id, "Blue Wizard", "blue", Position(1, 1)),
            CreaturePlacement("red", BATTLE_MAGIC_WIZARD.definition_id, "Red Wizard", "red", Position(3, 1)),
        ),
    )
    monkeypatch.setattr(content, "_STAGED_SETUPS", content._STAGED_SETUPS | {setup.setup_id: setup})
    game = Encounter.start(setup, rolls=(20, 1, 4))
    _settle_initiative(game)
    assert game._state.creatures["blue"].reaction_available
    assert game.execute(Cast("shield")).status is ResultStatus.COMPLETED
    assert game.execute(EndTurn()).status is ResultStatus.COMPLETED
    paused = game.execute(Cast("force_barrage", actions=1, target_ids=("blue",)))
    choice = paused.inspection.choice
    assert paused.status is ResultStatus.PAUSED
    assert choice is not None and choice.kind == "shield_block"
    resolved = _choose(game, "block")
    assert any(event.kind == "spell_damage" and event.shield_block is not None for event in resolved.events)


def test_magic_shield_does_not_offer_a_block_when_a_spell_save_prevents_all_damage(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    setup = EncounterSetup(
        setup_id="test_magic_shield_zero_spell_damage",
        name="Magic Shield zero spell damage",
        width=5,
        height=3,
        placements=(
            CreaturePlacement("blue", BATTLE_MAGIC_WIZARD.definition_id, "Blue Wizard", "blue", Position(1, 1)),
            CreaturePlacement("red", BATTLE_MAGIC_WIZARD.definition_id, "Red Wizard", "red", Position(3, 1)),
        ),
    )
    monkeypatch.setattr(content, "_STAGED_SETUPS", content._STAGED_SETUPS | {setup.setup_id: setup})
    game = Encounter.start(setup, rolls=(20, 1, 3, 4, 20))
    _settle_initiative(game)
    assert game.execute(Cast("shield")).status is ResultStatus.COMPLETED
    assert game.execute(EndTurn()).status is ResultStatus.COMPLETED
    paused = game.execute(Cast("breathe_fire", actions=2, area_direction=Position(-1, 0)))
    assert paused.status is ResultStatus.PAUSED
    assert game.inspect().choice is not None and game.inspect().choice.kind == "spell_save_hero_reroll"
    finished = _choose(game, "keep")
    assert finished.status is ResultStatus.COMPLETED
    assert game.inspect().choice is None
    assert game._state.creatures["blue"].magic_shield_expires_at_start == 2


def test_magic_shield_blocks_magical_nonphysical_damage_but_not_an_ordinary_fire_strike(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    magical = EncounterSetup(
        setup_id="test_magic_shield_magical_fire",
        name="Magic Shield magical fire",
        width=4,
        height=3,
        placements=(
            CreaturePlacement("wizard", BATTLE_MAGIC_WIZARD.definition_id, "Wizard", "blue", Position(1, 1)),
            CreaturePlacement("sentinel", WAYSTONE_SENTINEL.definition_id, "Sentinel", "red", Position(2, 1)),
        ),
    )
    nonmagical_definition = replace(
        WAYSTONE_SENTINEL,
        definition_id="test_nonmagical_fire_striker",
        attacks=(replace(WAYSTONE_SENTINEL.attacks[0], traits=frozenset({"attack", "melee"})),),
    )
    nonmagical = replace(
        magical,
        setup_id="test_magic_shield_nonmagical_fire",
        name="Magic Shield ordinary fire",
        placements=(
            magical.placements[0],
            CreaturePlacement("sentinel", nonmagical_definition.definition_id, "Sentinel", "red", Position(2, 1)),
        ),
    )
    monkeypatch.setattr(
        content, "_STAGED_CREATURES",
        content._STAGED_CREATURES | {nonmagical_definition.definition_id: nonmagical_definition},
    )
    monkeypatch.setattr(
        content, "_STAGED_SETUPS",
        content._STAGED_SETUPS | {magical.setup_id: magical, nonmagical.setup_id: nonmagical},
    )

    game = Encounter.start(magical, rolls=(20, 1, 10, 4))
    _settle_initiative(game)
    assert game.execute(Cast("shield")).status is ResultStatus.COMPLETED
    assert game.execute(EndTurn()).status is ResultStatus.COMPLETED
    assert game.execute(Strike("wizard")).status is ResultStatus.PAUSED
    assert game.inspect().choice is not None and game.inspect().choice.kind == "shield_block"
    assert _choose(game, "block").status is ResultStatus.COMPLETED

    game = Encounter.start(nonmagical, rolls=(20, 1, 10, 1))
    _settle_initiative(game)
    assert game.execute(Cast("shield")).status is ResultStatus.COMPLETED
    assert game.execute(EndTurn()).status is ResultStatus.COMPLETED
    ordinary = game.execute(Strike("wizard"))
    assert ordinary.status is ResultStatus.COMPLETED
    assert game.inspect().choice is None
    assert game._state.creatures["wizard"].magic_shield_expires_at_start == 2


def test_terminal_casts_battle_magic_shield() -> None:
    transcript = BoundedTranscript()
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
            return choose("Keep initiative")
        if prompt == "Choice:":
            if state["cast"]:
                state["cast"] = False
                return choose("Cast")
            return choose("Quit")
        if prompt == "Spell number:":
            return choose("Shield", prefix=True)
        if prompt == "Casting mode:":
            return choose("1 action")
        raise AssertionError(f"unexpected terminal prompt: {prompt!r}")

    assert run_terminal(
        setup=get_setup("staged_battle_magic_wizard_vs_two_guard_dogs"),
        rolls=(20, 1, 1),
        input_fn=BoundedInput(scripted_input), output_fn=output,
    ) == 0
    assert "raises a magical shield" in "\n".join(transcript)


def test_magic_shield_saves_through_multi_target_spell_continuation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Shield's saved Block resumes Breathe Fire's next recipient exactly once."""
    setup = EncounterSetup(
        setup_id="test_magic_shield_breathe_fire",
        name="Magic Shield Breathe Fire continuation",
        width=6,
        height=3,
        placements=(
            CreaturePlacement("blue", BATTLE_MAGIC_WIZARD.definition_id, "Blue Wizard", "blue", Position(1, 1)),
            CreaturePlacement("red", BATTLE_MAGIC_WIZARD.definition_id, "Red Wizard", "red", Position(4, 1)),
            CreaturePlacement("ally", BATTLE_MAGIC_WIZARD.definition_id, "Wizard Ally", "blue", Position(2, 1)),
        ),
    )
    monkeypatch.setattr(content, "_STAGED_SETUPS", content._STAGED_SETUPS | {setup.setup_id: setup})
    game = Encounter.start(setup, rolls=(20, 2, 1, 3, 4, 10, 10))
    _settle_initiative(game)
    assert game.execute(Cast("shield")).status is ResultStatus.COMPLETED
    assert game.execute(EndTurn()).status is ResultStatus.COMPLETED
    assert game._breathe_fire_targets(game._state, game._state.creatures["red"], Position(-1, 0)) == ("blue", "ally")

    paused = game.execute(Cast("breathe_fire", actions=2, area_direction=Position(-1, 0)))
    assert paused.status is ResultStatus.PAUSED
    assert game.inspect().choice is not None and game.inspect().choice.kind == "spell_save_hero_reroll"
    paused = _choose(game, "keep")
    assert paused.status is ResultStatus.PAUSED
    assert game.inspect().choice is not None and game.inspect().choice.kind == "shield_block"
    saved = tmp_path / "magic-shield-breathe-fire.json"
    game.save(saved)
    game = Encounter.load(saved)

    resumed = _choose(game, "block")
    assert resumed.status is ResultStatus.PAUSED
    assert game.inspect().choice is not None and game.inspect().choice.owner_actor_id == "ally"
    finished = _choose(game, "keep")
    assert finished.status is ResultStatus.COMPLETED
    spell_events = [event for event in (*resumed.events, *finished.events) if event.kind == "spell_damage"]
    assert [event.damage.total for event in spell_events if event.damage is not None] == [7, 7]
    assert spell_events[0].shield_block is not None and spell_events[0].shield_block.magic
    assert game._state.creatures["blue"].hp == 14
    assert game._state.creatures["ally"].hp == 9
    assert game._state.creatures["blue"].shield_recast_available_at_seconds == 600


def test_magic_shield_cooldown_survives_save_and_scene_then_clears_after_ten_minutes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    setup = EncounterSetup(
        setup_id="test_magic_shield_cooldown",
        name="Magic Shield cooldown",
        width=4,
        height=3,
        placements=(
            CreaturePlacement("wizard", BATTLE_MAGIC_WIZARD.definition_id, "Wizard", "blue", Position(1, 1)),
            CreaturePlacement("dog", "guard_dog_mc2924", "Dog", "red", Position(2, 1)),
        ),
    )
    next_setup = EncounterSetup(
        setup_id="test_magic_shield_cooldown_next",
        name="Magic Shield cooldown next scene",
        width=4,
        height=3,
        placements=(
            CreaturePlacement("wizard", BATTLE_MAGIC_WIZARD.definition_id, "Wizard", "blue", Position(1, 1)),
            CreaturePlacement("next_dog", "guard_dog_mc2924", "Next Dog", "red", Position(2, 1)),
        ),
    )
    monkeypatch.setattr(content, "_STAGED_SETUPS", content._STAGED_SETUPS | {setup.setup_id: setup, next_setup.setup_id: next_setup})
    game = Encounter.start(setup, rolls=(20, 1, 20, 4, 4, 4, 20, 1))
    _settle_initiative(game)
    assert game.execute(Cast("shield")).status is ResultStatus.COMPLETED
    assert game.execute(EndTurn()).status is ResultStatus.COMPLETED
    assert game.execute(Strike("wizard")).status is ResultStatus.PAUSED
    assert _choose(game, "block").status is ResultStatus.COMPLETED
    before, dice_before = game.inspect(), game._dice.to_data()
    assert game.execute(Cast("shield")).status is ResultStatus.REJECTED
    assert game.inspect() == before and game._dice.to_data() == dice_before
    assert game.execute(EndTurn()).status is ResultStatus.COMPLETED
    finished = game.execute(Cast("force_barrage", actions=2, target_ids=("dog", "dog")))
    assert finished.status is ResultStatus.COMPLETED and not game.inspect().in_progress
    saved = tmp_path / "magic-shield-cooldown.json"
    game.save(saved)

    scene_game = Encounter.load(saved)
    next_scene = scene_game.next_encounter(next_setup)
    assert next_scene.status in {ResultStatus.COMPLETED, ResultStatus.PAUSED}
    assert scene_game._state.creatures["wizard"].shield_recast_available_at_seconds == 600

    time_game = Encounter.load(saved)
    world_before = time_game._state.world_time_seconds
    assert time_game.refocus("wizard").status is ResultStatus.COMPLETED
    assert time_game._state.world_time_seconds == world_before + 600
    assert time_game._state.creatures["wizard"].shield_recast_available_at_seconds == 0
