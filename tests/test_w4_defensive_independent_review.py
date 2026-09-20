"""Independent public checks for W4 defensive class feats."""

import json
from pathlib import Path

import pytest

from pf2e import EndTurn, Strike
import pf2e.content as content
from pf2e.content import get_setup
from pf2e.encounter import Encounter
from pf2e.fighter import SnaggingStrike
from pf2e.martial_defense import PointBlankStance, point_blank_stance_is_active
from pf2e.model import CreaturePlacement, EncounterSetup, Position, Release, ResultStatus
from pf2e.skill_actions import Demoralize, Feint
from pf2e.terminal import run_terminal
from terminal_test_helpers import BoundedInput, BoundedTranscript


def _ready(setup_id: str, rolls: tuple[int, ...]) -> Encounter:
    game = Encounter.start(get_setup(setup_id), rolls=rolls)
    for _ in range(6):
        choice = game.inspect().choice
        if choice is None:
            return game
        option_id = "keep" if any(option.option_id == "keep" for option in choice.options) else choice.options[0].option_id
        assert game.choose(choice.choice_id, option_id, choice.owner_actor_id).status in {
            ResultStatus.PAUSED, ResultStatus.COMPLETED,
        }
    raise AssertionError("initiative choices did not settle")


def test_reactive_shield_is_not_offered_for_a_melee_miss() -> None:
    game = _ready("w4_reactive_shield_vs_guard_dog", (20, 1, 1))
    assert game.execute(EndTurn()).status is ResultStatus.COMPLETED
    result = game.execute(Strike("w4_actor", "jaws"))
    assert result.status is ResultStatus.COMPLETED
    assert game.inspect().choice is None
    assert game._state.creatures["w4_actor"].reaction_available
    assert "w4_actor" not in game._state.raised_shields


def test_point_blank_stance_ends_when_the_ranged_weapon_is_released(tmp_path: Path) -> None:
    game = _ready("w4_point_blank_stance_vs_guard_dog", (20, 1))
    assert game.execute(PointBlankStance()).status is ResultStatus.COMPLETED
    assert point_blank_stance_is_active(game._state, "w4_actor")
    assert game.execute(Release("shortbow")).status is ResultStatus.COMPLETED
    assert not point_blank_stance_is_active(game._state, "w4_actor")
    path = tmp_path / "point-blank-after-release.json"
    game.save(path)
    assert not point_blank_stance_is_active(Encounter.load(path)._state, "w4_actor")


def test_youre_next_reaction_demoralize_cannot_be_called_without_its_trigger() -> None:
    for setup_id in ("w4_youre_next_vs_guard_dog", "w4_overextending_feint_vs_guard_dog"):
        game = _ready(setup_id, (20, 1, 15))
        actor = game._state.creatures["w4_actor"]
        actions_before = actor.actions_remaining
        reaction_before = actor.reaction_available
        result = game.execute(Demoralize("w4_enemy", youre_next_reaction=True))
        assert result.status is ResultStatus.REJECTED
        assert actor.actions_remaining == actions_before
        assert actor.reaction_available == reaction_before


def test_reactive_shield_turns_an_ordinary_hit_into_a_miss_after_load(tmp_path: Path) -> None:
    game = _ready("w4_reactive_shield_vs_guard_dog", (20, 1, 12))
    assert game.execute(EndTurn()).status is ResultStatus.COMPLETED
    assert game.execute(Strike("w4_actor", "jaws")).status is ResultStatus.PAUSED
    choice = game.inspect().choice
    assert choice is not None and choice.kind == "reactive_shield"
    path = tmp_path / "reactive-shield-hit.json"
    game.save(path)
    loaded = Encounter.load(path)
    choice = loaded.inspect().choice
    assert choice is not None and choice.kind == "reactive_shield"
    before_hp = loaded._state.creatures["w4_actor"].hp
    assert loaded.choose(choice.choice_id, "use", choice.owner_actor_id).status is ResultStatus.COMPLETED
    assert loaded._state.creatures["w4_actor"].hp == before_hp
    assert not loaded._state.creatures["w4_actor"].reaction_available
    assert "w4_actor" in loaded._state.raised_shields


def test_reactive_shield_triggers_on_a_special_melee_strike(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    snagging = get_setup("staged_fighter_level_1_snagging_strike").placements[0]
    shield = get_setup("w4_reactive_shield_vs_guard_dog").placements[0]
    setup = EncounterSetup(
        "review_reactive_shield_special_strike", "Reactive Shield versus Snagging Strike", 5, 3,
        (
            CreaturePlacement("attacker", snagging.definition_id, "Attacker", "red", Position(1, 1)),
            CreaturePlacement("defender", shield.definition_id, "Defender", "blue", Position(2, 1)),
        ),
    )
    monkeypatch.setattr(content, "_STAGED_SETUPS", content._STAGED_SETUPS | {setup.setup_id: setup})
    game = Encounter.start(setup, rolls=(20, 1, 9, 1))
    for _ in range(6):
        choice = game.inspect().choice
        if choice is None:
            break
        game.choose(choice.choice_id, "keep" if any(option.option_id == "keep" for option in choice.options) else choice.options[0].option_id, choice.owner_actor_id)
    assert game.execute(SnaggingStrike("defender", "longsword")).status is ResultStatus.PAUSED
    choice = game.inspect().choice
    assert choice is not None and choice.kind == "attack_hero_reroll"
    assert game.choose(choice.choice_id, "keep", choice.owner_actor_id).status is ResultStatus.PAUSED
    assert game.inspect().choice is not None and game.inspect().choice.kind == "reactive_shield"
    path = tmp_path / "saved-special-strike-shield.json"
    game.save(path)
    loaded = Encounter.load(path)
    choice = loaded.inspect().choice
    assert choice is not None and choice.kind == "reactive_shield"
    original_hp = loaded._state.creatures["defender"].hp
    assert loaded.choose(choice.choice_id, "use", choice.owner_actor_id).status is ResultStatus.COMPLETED
    assert loaded._state.creatures["defender"].hp == original_hp
    assert not any(effect.effect_id.startswith("snagging_strike:") for effect in loaded._state.condition_effects)


def test_overextending_feint_offers_its_replacement_after_success() -> None:
    game = _ready("w4_overextending_feint_vs_guard_dog", (20, 1, 20))
    assert game.execute(Feint("w4_enemy")).status is ResultStatus.PAUSED
    choice = game.inspect().choice
    assert choice is not None and choice.kind == "family_action"
    assert game.choose(choice.choice_id, "keep", choice.owner_actor_id).status is ResultStatus.PAUSED
    choice = game.inspect().choice
    assert choice is not None and choice.kind == "family_action"
    assert any("Overextending Feint" in option.label for option in choice.options)


def test_reactive_shield_save_rejects_a_forged_attack_modifier(tmp_path: Path) -> None:
    game = _ready("w4_reactive_shield_vs_guard_dog", (20, 1, 12))
    assert game.execute(EndTurn()).status is ResultStatus.COMPLETED
    assert game.execute(Strike("w4_actor", "jaws")).status is ResultStatus.PAUSED
    path = tmp_path / "forged-reactive-shield.json"
    game.save(path)
    payload = json.loads(path.read_text(encoding="utf-8"))
    check = payload["state"]["pending_choice"]["check"]
    check["modifier"] = 100
    check["total"] = check["die"] + 100
    check["degree"] = 3
    check["degree_before_adjustments"] = 3
    check["modifier_breakdown"] = [[100, "untyped", "printed attack modifier"]]
    check["adjustments"] = []
    path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ValueError):
        Encounter.load(path)


@pytest.mark.parametrize(
    ("setup_id", "actions", "weapon", "target", "rolls", "event_text", "finishes"),
    (
        ("w4_reactive_shield_vs_guard_dog", ("End Turn", "Strike", "Quit"), "Jaws", "W4 Level 1 Fighter", (20, 1, 12, 1), "uses Reactive Shield", False),
        ("w4_point_blank_stance_vs_guard_dog", ("Point Blank Stance", "Strike", "Quit"), "Shortbow", "Guard Dog", (20, 1, 20, 6, 6), "enters Point Blank Stance", True),
        ("w4_overextending_feint_vs_guard_dog", ("Feint", "Quit"), "", "Guard Dog", (20, 1, 20), "takes a -2 circumstance penalty", False),
        ("w4_youre_next_vs_two_guard_dogs", ("Strike", "Quit"), "Shortsword", "Guard Dog A", (20, 1, 1, 20, 6, 15), "uses You're Next", False),
    ),
)
def test_terminal_executes_each_defensive_feat_and_point_blank_finishes_encounter(
    setup_id: str, actions: tuple[str, ...], weapon: str, target: str,
    rolls: tuple[int, ...], event_text: str, finishes: bool,
) -> None:
    transcript = BoundedTranscript(max_lines=300, max_chars=50_000)
    seen = {"menu": "", "prompt": ""}
    action_queue = iter(actions)

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
            if "Overextending Feint" in seen["menu"]:
                return menu_number("Overextending Feint")
            if "Keep" in seen["menu"]:
                return menu_number("Keep")
            if "Use Reactive Shield" in seen["menu"]:
                return menu_number("Use Reactive Shield")
            if "Demoralize Guard Dog B" in seen["menu"]:
                return menu_number("Demoralize Guard Dog B")
            raise AssertionError(f"unknown choice menu: {seen['menu']!r}")
        if prompt == "Choice:":
            return menu_number(next(action_queue))
        if prompt == "Weapon / attack number:":
            return menu_number(weapon)
        if prompt in {"Target number:", "Feint target:"}:
            return menu_number(target)
        if prompt == "Damage type:":
            return menu_number("Piercing")
        if prompt == "Damage intent:":
            return menu_number("Use attack default")
        raise AssertionError(f"unexpected terminal prompt: {prompt!r}")

    assert run_terminal(
        setup=get_setup(setup_id), rolls=rolls,
        input_fn=BoundedInput(scripted_input, max_calls=35), output_fn=output,
    ) == 0
    rendered = "\n".join(transcript)
    assert "Rejected:" not in rendered
    assert event_text in rendered
    if finishes:
        assert "Guard Dog is defeated" in rendered
        assert "Encounter finished" in rendered
