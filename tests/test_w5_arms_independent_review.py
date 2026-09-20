"""Independent public review of W5 Arms content.

Rules: https://2e.aonprd.com/Feats.aspx?ID=5811,
https://2e.aonprd.com/Feats.aspx?ID=4927,
https://2e.aonprd.com/Feats.aspx?ID=6128.
"""

import json
from dataclasses import replace
from pathlib import Path
from time import perf_counter

import pytest

import pf2e.content as content
from pf2e import Encounter, EndTurn, ExtravagantParry, Interact, Release, Strike
from pf2e.barbarian import rage_damage_bonus
from pf2e.barbarian_content import BARBARIAN_INITIAL_STATES, BARBARIAN_LOADOUTS
from pf2e.content import get_definition, get_setup
from pf2e.model import CreaturePlacement, EncounterSetup, Position, ResultStatus
from pf2e.swashbuckler import ConfidentFinisher
from pf2e.terminal import run_terminal
from terminal_test_helpers import BoundedInput, BoundedTranscript


def _ready(setup_id: str, rolls: tuple[int, ...] | None = None, *, seed: int = 0) -> Encounter:
    game = Encounter.start(get_setup(setup_id), rolls=rolls, seed=seed)
    for _ in range(8):
        choice = game.inspect().choice
        if choice is None:
            return game
        ids = {option.option_id for option in choice.options}
        answer = "accept" if "accept" in ids else "keep" if "keep" in ids else choice.options[0].option_id
        assert game.choose(choice.choice_id, answer, choice.owner_actor_id).status in {
            ResultStatus.PAUSED, ResultStatus.COMPLETED,
        }
    raise AssertionError("initiative choice did not settle")


def _finish_choices(game: Encounter):
    for _ in range(8):
        choice = game.inspect().choice
        if choice is None:
            return
        ids = {option.option_id for option in choice.options}
        answer = "keep" if "keep" in ids else choice.options[0].option_id
        result = game.choose(choice.choice_id, answer, choice.owner_actor_id)
        assert result.status in {ResultStatus.PAUSED, ResultStatus.COMPLETED}
    raise AssertionError("resolution choice did not settle")


def test_raging_thrower_public_grant_and_authorized_damage() -> None:
    definition = get_definition("barbarian_fury_raging_thrower")
    state = BARBARIAN_INITIAL_STATES[definition.definition_id]
    loadout = BARBARIAN_LOADOUTS[definition.definition_id]
    assert "Raging Thrower" in definition.feats
    assert "Moment of Clarity" in definition.feats
    assert state.class_feat_id == "raging_thrower" and state.bonus_feat_id == "moment_of_clarity"
    assert [item.item_id for item in loadout.items] == ["breastplate", "dagger_1", "dagger_2", "dagger_3"]
    assert loadout.remaining_money_sp == 64
    melee, thrown, _fist = definition.attacks
    assert (melee.modifier, melee.damage_modifier, melee.attack_attribute) == (7, 4, "strength")
    assert (thrown.modifier, thrown.damage_modifier, thrown.attack_attribute) == (4, 4, "dexterity")

    game = _ready("w5_raging_thrower_vs_guard", (20, 1))
    rage = game._state.creatures["raging_thrower"].barbarian_state
    assert rage is not None and rage.rage is not None
    assert rage_damage_bonus(rage, attack_traits=thrown.traits, is_melee=False) == 1
    assert rage_damage_bonus(rage, attack_traits=frozenset({"ranged", "weapon"}), is_melee=False) == 0
    assert rage_damage_bonus(rage, attack_traits=frozenset({"ranged", "thrown", "weapon"}), is_melee=False) == 3


def test_strong_arm_exact_range_boundary_pending_save_and_bounded_menu(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    definition = get_definition("rogue_thief_warrior_level_2_strong_arm")
    melee, ranged, _fist = definition.attacks
    assert (melee.damage_modifier, melee.damage_attribute) == (4, "dexterity")
    assert (ranged.damage_modifier, ranged.damage_attribute) == (0, "strength")
    base = get_setup("w5_strong_arm_vs_guard")
    actor, guard = base.placements
    at_max = EncounterSetup("review_strong_arm_120", "Strong Arm exact maximum", 26, 3, (
        replace(actor, position=Position(0, 1)), replace(guard, position=Position(24, 1)),
    ))
    beyond = EncounterSetup("review_strong_arm_125", "Strong Arm over maximum", 26, 3, (
        replace(actor, position=Position(0, 1)), replace(guard, position=Position(25, 1)),
    ))
    monkeypatch.setattr(content, "_STAGED_SETUPS", content._STAGED_SETUPS | {
        at_max.setup_id: at_max, beyond.setup_id: beyond,
    })
    game = _ready(at_max.setup_id, (20, 1, 20, 1))
    start = perf_counter()
    for _ in range(50):
        options = game.options()
    assert perf_counter() - start < 2.0
    thrown = next(option for option in options.strikes if option.attack_id == "dagger_thrown")
    assert "strong_arm_guard" in thrown.targets
    pending = game.execute(Strike("strong_arm_guard", "dagger_thrown", item_id="dagger"))
    assert pending.status is ResultStatus.PAUSED
    assert game._state.pending_choice.ranged_penalty == -10
    path = tmp_path / "strong-arm-pending.json"
    game.save(path)
    payload = json.loads(path.read_text())
    payload["state"]["pending_choice"]["ranged_penalty"] = 0
    path.write_text(json.dumps(payload))
    with pytest.raises(ValueError):
        Encounter.load(path)
    game.save(path)
    game = Encounter.load(path)
    assert game.inspect().choice is not None
    _finish_choices(game)
    assert game._state.creatures["strong_arm"].actions_remaining == 2

    too_far = _ready(beyond.setup_id, (20, 1))
    thrown = next(option for option in too_far.options().strikes if option.attack_id == "dagger_thrown")
    assert "strong_arm_guard" not in thrown.targets
    before = too_far.inspect()
    assert too_far.execute(Strike("strong_arm_guard", "dagger_thrown", item_id="dagger")).status is ResultStatus.REJECTED
    assert too_far.inspect() == before


def test_extravagant_parry_two_weapons_guard_save_and_no_revival(tmp_path: Path) -> None:
    game = _ready("w5_extravagant_parry_vs_guard", (20, 1))
    assert game.execute(Interact("draw", "parry_swashbuckler:dagger_2")).status is ResultStatus.COMPLETED
    assert game.execute(ExtravagantParry()).status is ResultStatus.COMPLETED
    actor = game._state.creatures["parry_swashbuckler"]
    assert game._effective_ac(actor, state=game._state) == 19
    path = tmp_path / "two-weapon-parry.json"
    game.save(path)
    game = Encounter.load(path)
    actor = game._state.creatures["parry_swashbuckler"]
    assert game._effective_ac(actor, state=game._state) == 19

    payload = json.loads(path.read_text())
    effect = next(row for row in payload["state"]["active_effects"] if row[1] == "extravagant_parry")
    effect[4] = 3
    path.write_text(json.dumps(payload))
    with pytest.raises(ValueError):
        Encounter.load(path)

    assert game.execute(Release("parry_swashbuckler:dagger_1")).status is ResultStatus.COMPLETED
    assert game._effective_ac(game._state.creatures["parry_swashbuckler"], state=game._state) == 19
    assert game.execute(Release("parry_swashbuckler:dagger_2")).status is ResultStatus.COMPLETED
    assert not any(effect.kind == "extravagant_parry" for effect in game._state.active_effects)
    assert game.execute(Interact("retrieve", "parry_swashbuckler:dagger_1")).status is ResultStatus.COMPLETED
    assert game._effective_ac(game._state.creatures["parry_swashbuckler"], state=game._state) == 18


def test_parry_miss_to_panache_finisher_and_continuous_victory(tmp_path: Path) -> None:
    game = _ready("w5_extravagant_parry_vs_guard", seed=0)
    assert game.execute(ExtravagantParry()).status is ResultStatus.COMPLETED
    assert game.execute(EndTurn()).status is ResultStatus.COMPLETED
    result = game.execute(Strike("parry_swashbuckler", "guard_spear"))
    _finish_choices(game)
    assert any(event.kind == "extravagant_parry_panache" for event in result.events) or game._state.creatures["parry_swashbuckler"].panache
    path = tmp_path / "parry-panache.json"
    game.save(path)
    game = Encounter.load(path)
    assert game._state.creatures["parry_swashbuckler"].panache
    finisher_seen = False
    for _ in range(60):
        if not game.inspect().in_progress:
            break
        turn = game.inspect().turn_actor_id
        if turn == "parry_swashbuckler":
            if game._state.creatures[turn].finisher_used_this_turn:
                result = game.execute(EndTurn())
            elif game._state.creatures[turn].panache and "confident_finisher" in game.options().available_actions:
                result = game.execute(ConfidentFinisher("parry_guard", "dagger"))
                finisher_seen = True
            elif "parry_guard" in next(option for option in game.options().strikes if option.attack_id == "dagger").targets:
                result = game.execute(Strike("parry_guard", "dagger"))
            else:
                result = game.execute(EndTurn())
        else:
            result = game.execute(EndTurn())
        assert result.status in {ResultStatus.PAUSED, ResultStatus.COMPLETED}
        _finish_choices(game)
        if game.inspect().in_progress and game.options().actions_remaining == 0:
            assert game.execute(EndTurn()).status is ResultStatus.COMPLETED
    assert finisher_seen
    assert not game.inspect().in_progress and game.inspect().winner_team == "blue"


def test_numbered_terminal_executes_extravagant_parry() -> None:
    transcript = BoundedTranscript(max_lines=120, max_chars=20_000)
    seen = {"menu": "", "prompt": "", "phase": "parry"}

    def output(line: str) -> None:
        transcript.append(line)
        if line.startswith("1. "):
            seen["menu"] = line
        if line.endswith((":", "?")):
            seen["prompt"] = line

    def number(label: str) -> str:
        for row in seen["menu"].splitlines():
            index, text = row.split(". ", 1)
            if label in text:
                return index
        raise AssertionError((label, seen["menu"]))

    def answer() -> str:
        prompt = seen["prompt"]
        if prompt == "Choice prompt action:":
            return number("Resolve this choice")
        if prompt == "Choice option number:":
            return number("Keep")
        if prompt == "Choice:":
            if seen["phase"] == "parry":
                seen["phase"] = "quit"
                return number("Extravagant Parry")
            return number("Quit")
        raise AssertionError(prompt)

    assert run_terminal(
        setup=get_setup("w5_extravagant_parry_vs_guard"), rolls=(20, 1),
        input_fn=BoundedInput(answer, max_calls=12), output_fn=output,
    ) == 0
    assert "uses Extravagant Parry" in "\n".join(transcript)


@pytest.mark.parametrize(
    ("setup_id", "target"),
    (
        ("w5_raging_thrower_vs_guard", "Guard"),
        ("w5_strong_arm_vs_guard", "Guard"),
    ),
)
def test_numbered_terminal_throws_new_family_daggers(setup_id: str, target: str) -> None:
    transcript = BoundedTranscript(max_lines=150, max_chars=25_000)
    seen = {"menu": "", "prompt": "", "phase": "strike"}

    def output(line: str) -> None:
        transcript.append(line)
        if line.startswith("1. "):
            seen["menu"] = line
        if line.endswith((":", "?")):
            seen["prompt"] = line

    def number(label: str) -> str:
        for row in seen["menu"].splitlines():
            index, text = row.split(". ", 1)
            if label in text:
                return index
        raise AssertionError((label, seen["menu"]))

    def answer() -> str:
        prompt = seen["prompt"]
        if prompt == "Choice prompt action:":
            return number("Resolve this choice")
        if prompt == "Choice option number:":
            if "Use Quick-Tempered" in seen["menu"]:
                return number("Use Quick-Tempered")
            return number("Keep")
        if prompt == "Choice:":
            if seen["phase"] == "strike":
                seen["phase"] = "quit"
                return number("Strike")
            return number("Quit")
        if prompt == "Weapon / attack number:":
            return number("Dagger (Thrown)")
        if prompt == "Target number:":
            return number(target)
        if prompt == "Damage intent:":
            return number("Use attack default")
        if prompt == "Item number:":
            return number("dagger")
        raise AssertionError(prompt)

    assert run_terminal(
        setup=get_setup(setup_id), rolls=(20, 1, 20, 1, 1),
        input_fn=BoundedInput(answer, max_calls=25), output_fn=output,
    ) == 0
    rendered = "\n".join(transcript)
    assert "Dagger (Thrown)" in rendered and "lands at" in rendered
