"""Public W2 checks for the finite martial guard and stance alternatives.

Sources checked 2026-09-19: Dueling Parry (Player Core p. 141,
https://2e.aonprd.com/Feats.aspx?ID=4781) and Crane Stance (Player Core 2
p. 118, https://2e.aonprd.com/Feats.aspx?ID=5976).
"""

from __future__ import annotations

from pathlib import Path
import re

from pf2e import EndTurn, Release, Strike
from pf2e.content import get_setup
from pf2e.encounter import Encounter
from pf2e.martial_defense import CraneStance, DismissCraneStance, DuelingParry
from pf2e.model import ResultStatus
from pf2e.terminal import run_terminal
from terminal_test_helpers import BoundedInput, BoundedTranscript


def _settle_initiative(game: Encounter) -> None:
    for _ in range(8):
        choice = game.inspect().choice
        if choice is None:
            return
        option_id = "keep" if any(option.option_id == "keep" for option in choice.options) else choice.options[0].option_id
        assert game.choose(choice.choice_id, option_id, choice.owner_actor_id).status in {
            ResultStatus.PAUSED, ResultStatus.COMPLETED,
        }
    raise AssertionError("initiative did not settle")


def test_dueling_parry_has_live_hand_requirements_save_recovery_and_turn_expiry(tmp_path: Path) -> None:
    game = Encounter.start(get_setup("staged_fighter_level_2_dueling_parry"), rolls=(20, 1))
    _settle_initiative(game)
    fighter = game._state.creatures["fighter"]
    assert game.inspect().turn_actor_id == "fighter"
    assert "dueling_parry" in game.options().available_actions

    assert game.execute(DuelingParry("longsword")).status is ResultStatus.COMPLETED
    fighter = game._state.creatures["fighter"]
    assert fighter.actions_remaining == 2
    assert game._effective_ac(fighter, state=game._state) == 21

    save_path = tmp_path / "dueling-parry.json"
    game.save(save_path)
    game = Encounter.load(save_path)
    fighter = game._state.creatures["fighter"]
    assert game._effective_ac(fighter, state=game._state) == 21

    # The bonus is conditional rather than a flattened AC edit: releasing the
    # only held weapon removes it immediately, without spending an action.
    assert game.execute(Release("longsword")).status is ResultStatus.COMPLETED
    fighter = game._state.creatures["fighter"]
    assert fighter.actions_remaining == 2
    assert game._effective_ac(fighter, state=game._state) == 19

    expired = Encounter.start(get_setup("staged_fighter_level_2_dueling_parry"), rolls=(20, 1))
    _settle_initiative(expired)
    assert expired.execute(DuelingParry("longsword")).status is ResultStatus.COMPLETED
    assert expired.execute(EndTurn()).status is ResultStatus.COMPLETED
    assert expired.execute(EndTurn()).status is ResultStatus.COMPLETED
    fighter = expired._state.creatures["fighter"]
    assert expired.inspect().turn_actor_id == "fighter"
    assert expired._effective_ac(fighter, state=expired._state) == 19


def test_crane_stance_restricts_strikes_serializes_and_is_limited_to_one_stance_action_per_round(
    tmp_path: Path,
) -> None:
    game = Encounter.start(get_setup("staged_monk_crane_stance"), rolls=(20, 1, 2))
    _settle_initiative(game)
    monk = game._state.creatures["monk"]
    assert game.inspect().turn_actor_id == "monk"
    assert "crane_wing" not in {option.attack_id for option in game.options().strikes}
    rejected = game.execute(Strike("dog", "crane_wing"))
    assert rejected.status is ResultStatus.REJECTED and monk.actions_remaining == 3

    assert game.execute(CraneStance()).status is ResultStatus.COMPLETED
    monk = game._state.creatures["monk"]
    assert monk.actions_remaining == 2
    assert game._effective_ac(monk, state=game._state) == 20
    assert {option.attack_id for option in game.options().strikes} == {"crane_wing"}

    save_path = tmp_path / "crane-stance.json"
    game.save(save_path)
    game = Encounter.load(save_path)
    monk = game._state.creatures["monk"]
    assert game._effective_ac(monk, state=game._state) == 20
    assert game.execute(Strike("dog", "fist")).status is ResultStatus.REJECTED
    paused = game.execute(Strike("dog", "crane_wing"))
    assert paused.status is ResultStatus.PAUSED
    choice = game.inspect().choice
    assert choice is not None and choice.kind == "attack_hero_reroll"
    assert game.choose(choice.choice_id, "keep", choice.owner_actor_id).status is ResultStatus.COMPLETED

    assert game.execute(DismissCraneStance()).status is ResultStatus.COMPLETED
    monk = game._state.creatures["monk"]
    assert game._effective_ac(monk, state=game._state) == 19
    assert game.execute(CraneStance()).status is ResultStatus.REJECTED
    assert monk.actions_remaining == 1


def test_terminal_exposes_dueling_parry_and_its_concrete_held_weapon() -> None:
    transcript = BoundedTranscript(max_lines=120, max_chars=20_000)
    menu = {"text": "", "prompt": ""}
    main_actions = iter(("Dueling Parry", "Quit"))

    def output(line: str) -> None:
        transcript.append(line)
        if line.startswith("1. "):
            menu["text"] = line
        if line.endswith(":"):
            menu["prompt"] = line

    def menu_number_containing(label: str) -> str:
        for row in menu["text"].splitlines():
            match = re.match(r"(\d+)\.\s+(.*)", row)
            if match and label in match.group(2):
                return match.group(1)
        raise AssertionError(f"missing terminal menu item containing {label!r}: {menu['text']!r}")

    def script() -> str:
        prompt = menu["prompt"]
        if prompt == "Choice:":
            return menu_number_containing(next(main_actions))
        if prompt == "Choice prompt action:":
            return "2"
        if prompt == "Choice option number:":
            return menu_number_containing("Keep")
        if prompt == "Dueling weapon:":
            return menu_number_containing("Longsword")
        raise AssertionError(f"unexpected terminal prompt: {prompt!r}")

    assert run_terminal(
        setup=get_setup("staged_fighter_level_2_dueling_parry"), rolls=(20, 1),
        input_fn=BoundedInput(script, max_calls=20), output_fn=output,
    ) == 0
    rendered = "\n".join(transcript)
    assert "Dueling Parry" in rendered and "uses Dueling Parry" in rendered


def test_terminal_exposes_crane_stance() -> None:
    transcript = BoundedTranscript(max_lines=100, max_chars=16_000)
    menu = {"text": "", "prompt": ""}
    main_actions = iter(("Crane Stance", "Quit"))

    def output(line: str) -> None:
        transcript.append(line)
        if line.startswith("1. "):
            menu["text"] = line
        if line.endswith(":"):
            menu["prompt"] = line

    def menu_number_containing(label: str) -> str:
        for row in menu["text"].splitlines():
            match = re.match(r"(\d+)\.\s+(.*)", row)
            if match and label in match.group(2):
                return match.group(1)
        raise AssertionError(f"missing terminal menu item containing {label!r}: {menu['text']!r}")

    def script() -> str:
        prompt = menu["prompt"]
        if prompt == "Choice:":
            return menu_number_containing(next(main_actions))
        if prompt == "Choice prompt action:":
            return "2"
        if prompt == "Choice option number:":
            return menu_number_containing("Keep")
        raise AssertionError(f"unexpected terminal prompt: {prompt!r}")

    assert run_terminal(
        setup=get_setup("staged_monk_crane_stance"), rolls=(20, 1),
        input_fn=BoundedInput(script, max_calls=16), output_fn=output,
    ) == 0
    rendered = "\n".join(transcript)
    assert "Crane Stance" in rendered and "enters Crane Stance" in rendered
