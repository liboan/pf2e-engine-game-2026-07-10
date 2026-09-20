"""Independent public checks for the W4 offensive class-feat group.

Rules: https://2e.aonprd.com/Feats.aspx?ID=4769,
https://2e.aonprd.com/Feats.aspx?ID=4864, and
https://2e.aonprd.com/Feats.aspx?ID=4921.
"""

from pathlib import Path

import pytest

from pf2e import Strike
from pf2e.content import get_definition, get_setup
from pf2e.encounter import Encounter
from pf2e.model import PairedStrikeSelection, Release, ResultStatus
from pf2e.terminal import run_terminal
from pf2e.w4_offensive import DoubleSlice, ExactingStrike, TwinFeint
from terminal_test_helpers import BoundedInput, BoundedTranscript


def _ready(setup_id: str) -> Encounter:
    game = Encounter.start(get_setup(setup_id), rolls=(20, 1, 6, 1, 6, 1, 6, 1))
    for _ in range(6):
        choice = game.inspect().choice
        if choice is None:
            return game
        option_id = "keep" if any(option.option_id == "keep" for option in choice.options) else choice.options[0].option_id
        assert game.choose(choice.choice_id, option_id, choice.owner_actor_id).status in {
            ResultStatus.PAUSED, ResultStatus.COMPLETED,
        }
    raise AssertionError("initiative choices did not settle")


def test_level_one_sheets_replace_the_selected_class_feat() -> None:
    ranger = get_definition(get_setup("w4_ranger_twin_takedown_vs_guard_dog").placements[0].definition_id)
    rogue = get_definition(get_setup("w4_rogue_twin_feint_vs_guard_dog").placements[0].definition_id)
    assert "Twin Takedown" in ranger.feats
    assert "Hunted Shot" not in ranger.feats
    assert "hunted_shot" not in ranger.abilities
    assert "Twin Feint" in rogue.feats
    assert "Nimble Dodge" not in rogue.feats
    assert "nimble_dodge" not in rogue.abilities


def test_two_weapon_activities_reject_an_unarmed_first_strike() -> None:
    fighter = _ready("w4_fighter_double_slice_vs_guard_dog")
    rogue = _ready("w4_rogue_twin_feint_vs_guard_dog")
    assert fighter.execute(DoubleSlice(PairedStrikeSelection("dog", "fist"))).status is ResultStatus.REJECTED
    assert rogue.execute(TwinFeint(PairedStrikeSelection("dog", "fist"))).status is ResultStatus.REJECTED


def test_released_dagger_cannot_make_the_rogues_dagger_strike() -> None:
    game = _ready("w4_rogue_twin_feint_vs_guard_dog")
    assert game.execute(Release("dagger")).status is ResultStatus.COMPLETED
    assert "dagger" not in game._state.creatures["rogue"].held_items
    assert "dagger" not in {strike.attack_id for strike in game.options().strikes}


def test_double_slice_second_non_agile_strike_reloads(tmp_path: Path) -> None:
    game = _ready("w4_fighter_double_slice_vs_guard_dog")
    assert game.execute(DoubleSlice(PairedStrikeSelection("dog", "shortsword"))).status is ResultStatus.PAUSED
    for _ in range(6):
        choice = game.inspect().choice
        assert choice is not None
        if choice.kind == "family_action":
            break
        assert game.choose(choice.choice_id, "keep", choice.owner_actor_id).status in {
            ResultStatus.PAUSED, ResultStatus.COMPLETED,
        }
    else:
        raise AssertionError("second Strike was not offered")
    second = next(option for option in choice.options if "Longsword" in option.label and "lethal" in option.label)
    assert game.choose(choice.choice_id, second.option_id, choice.owner_actor_id).status is ResultStatus.PAUSED
    assert game.inspect().choice is not None
    path = tmp_path / "double-slice-second.json"
    game.save(path)
    loaded = Encounter.load(path)
    assert loaded.inspect().choice is not None


def test_exacting_strike_success_offers_the_press_failure_effect() -> None:
    game = Encounter.start(
        get_setup("w4_fighter_exacting_strike_vs_guard_dog"),
        rolls=(20, 1, 2, 15, 1),
    )
    for _ in range(6):
        choice = game.inspect().choice
        if choice is None:
            break
        game.choose(choice.choice_id, "keep" if any(option.option_id == "keep" for option in choice.options) else choice.options[0].option_id, choice.owner_actor_id)
    assert game.execute(Strike("dog", "longsword")).status is ResultStatus.PAUSED
    choice = game.inspect().choice
    assert choice is not None and choice.kind == "attack_hero_reroll"
    assert game.choose(choice.choice_id, "keep", choice.owner_actor_id).status is ResultStatus.COMPLETED
    assert game.execute(ExactingStrike("dog", "longsword")).status is ResultStatus.PAUSED
    choice = game.inspect().choice
    assert choice is not None and choice.kind == "attack_hero_reroll"
    assert game.choose(choice.choice_id, "keep", choice.owner_actor_id).status is ResultStatus.PAUSED
    choice = game.inspect().choice
    assert choice is not None and choice.kind == "family_action"
    assert {option.option_id for option in choice.options} >= {"full_hit", "failure_effect"}


def test_terminal_double_slice_first_weapon_menu_excludes_fist() -> None:
    class MenuInspected(Exception):
        pass

    transcript = BoundedTranscript(max_lines=120, max_chars=20_000)
    seen = {"menu": "", "prompt": ""}

    def output(line: str) -> None:
        transcript.append(line)
        if line.startswith("1. "):
            seen["menu"] = line
        if line.endswith((":", "?")):
            seen["prompt"] = line

    def menu_number(label: str) -> str:
        for row in seen["menu"].splitlines():
            number, text = row.split(". ", 1)
            if label in text:
                return number
        raise AssertionError(f"missing menu item {label!r}: {seen['menu']!r}")

    def scripted_input() -> str:
        prompt = seen["prompt"]
        if prompt == "Choice prompt action:":
            return menu_number("Resolve this choice")
        if prompt == "Choice option number:":
            return menu_number("Keep")
        if prompt == "Choice:":
            return menu_number("Double Slice")
        if prompt == "Weapon / attack number:":
            assert "Fist" not in seen["menu"]
            raise MenuInspected
        raise AssertionError(f"unexpected terminal prompt: {prompt!r}")

    with pytest.raises(MenuInspected):
        run_terminal(
            setup=get_setup("w4_fighter_double_slice_vs_guard_dog"),
            rolls=(20, 1, 6, 1, 6, 1),
            input_fn=BoundedInput(scripted_input, max_calls=12), output_fn=output,
        )
