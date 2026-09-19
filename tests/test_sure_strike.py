"""Focused public play for the fixed Warpriest Sure Strike alternate."""

from __future__ import annotations

import json
import re
from pathlib import Path

from pf2e import Cast, Encounter, EndTurn, ResultStatus, Strike
from pf2e.content import SURE_STRIKE_WARPRIEST_SETUP
from pf2e.terminal import run_terminal


def _keep_start_choices(game: Encounter) -> None:
    while (choice := game.inspect().choice) is not None:
        option = "keep" if any(item.option_id == "keep" for item in choice.options) else choice.options[0].option_id
        result = game.choose(choice.choice_id, option, choice.owner_actor_id)
        assert result.status in {ResultStatus.PAUSED, ResultStatus.COMPLETED}


def test_sure_strike_public_cast_then_attack_uses_better_two_dice() -> None:
    # Initiative (Warpriest, dog), then Sure Strike's two attack faces and
    # the longsword damage die. The dim scene would normally require a
    # concealment flat check; Sure Strike bypasses that targeting gate.
    game = Encounter.start(SURE_STRIKE_WARPRIEST_SETUP, rolls=(20, 1, 3, 18, 4))
    _keep_start_choices(game)
    assert game.inspect().turn_actor_id == "cleric_c"

    cast = game.execute(Cast("sure_strike", slot_id="ordinary_sure_strike_1"))
    assert cast.status is ResultStatus.COMPLETED
    assert cast.inspection.choice is None
    assert any(effect.kind == "sure_strike" for effect in game._state.active_effects)
    assert next(slot for slot in game._state.creatures["cleric_c"].prepared_slots if slot.slot_id == "ordinary_sure_strike_1").spent

    attack = game.execute(Strike("guard_dog", attack_id="longsword", nonlethal=True))
    assert attack.status is ResultStatus.COMPLETED
    check = next(event.check for event in attack.events if event.check is not None)
    assert check is not None
    assert check.dice == (3, 18)
    assert check.die == 18
    assert check.total == 24
    assert not any(event.kind == "concealment_flat_check" for event in attack.events)
    assert not any(event.kind == "attack_hero_reroll" for event in attack.events)
    assert game._state.sure_strike_immunity_deadlines["cleric_c"] == game.inspect().world_time_seconds + 600


def test_sure_strike_effect_save_load_then_attack_preserves_faces_and_cooldown(tmp_path: Path) -> None:
    game = Encounter.start(SURE_STRIKE_WARPRIEST_SETUP, rolls=(20, 1, 3, 18, 4))
    _keep_start_choices(game)
    assert game.execute(Cast("sure_strike", slot_id="ordinary_sure_strike_1")).status is ResultStatus.COMPLETED
    save_path = tmp_path / "sure-strike-ready.json"
    game.save(save_path)
    payload = json.loads(save_path.read_text(encoding="utf-8"))
    assert any(row[1] == "sure_strike" for row in payload["state"]["active_effects"])
    assert payload["dice"]["index"] == game._dice._index
    restored = Encounter.load(save_path)
    assert restored.inspect() == game.inspect()

    attack = restored.execute(Strike("guard_dog", attack_id="longsword"))
    assert attack.status is ResultStatus.COMPLETED
    check = next(event.check for event in attack.events if event.check is not None)
    assert check is not None and check.dice == (3, 18)
    assert not restored._state.active_effects
    assert restored._state.sure_strike_immunity_deadlines["cleric_c"] == 600


def test_unused_sure_strike_expires_at_turn_end_without_cooldown() -> None:
    game = Encounter.start(SURE_STRIKE_WARPRIEST_SETUP, rolls=(20, 1, 3, 18, 4))
    _keep_start_choices(game)
    assert game.execute(Cast("sure_strike", slot_id="ordinary_sure_strike_1")).status is ResultStatus.COMPLETED
    assert game.execute(EndTurn()).status is ResultStatus.COMPLETED
    assert not any(effect.kind == "sure_strike" for effect in game._state.active_effects)
    assert "cleric_c" not in game._state.sure_strike_immunity_deadlines


def test_sure_strike_keeps_multiple_attack_penalty_while_ignoring_nonlethal_circumstance() -> None:
    # The first concealed normal Strike consumes the first two supplied faces
    # (flat check then attack) and deals damage, then leaves the actor with MAP
    # -5 for the Sure Strike attack. Its -2 nonlethal circumstance penalty is
    # ignored.
    game = Encounter.start(SURE_STRIKE_WARPRIEST_SETUP, rolls=(20, 1, 20, 10, 3, 18, 4))
    _keep_start_choices(game)
    first = game.execute(Strike("guard_dog", attack_id="longsword", nonlethal=True))
    assert first.status is ResultStatus.PAUSED
    assert game.inspect().choice is not None
    assert game.choose(game.inspect().choice.choice_id, "keep", game.inspect().choice.owner_actor_id).status is ResultStatus.PAUSED
    assert game.inspect().choice is not None
    assert game.choose(game.inspect().choice.choice_id, "keep", game.inspect().choice.owner_actor_id).status is ResultStatus.COMPLETED
    assert game.inspect().turn_actor_id == "cleric_c"
    assert game.execute(Cast("sure_strike", slot_id="ordinary_sure_strike_1")).status is ResultStatus.COMPLETED
    second = game.execute(Strike("guard_dog", attack_id="longsword", nonlethal=True))
    assert second.status is ResultStatus.COMPLETED
    check = next(event.check for event in second.events if event.check is not None)
    assert check is not None
    assert check.dice == (3, 18)
    assert check.attack_count == 2
    assert check.map_penalty == -5
    assert check.modifier == 1


def test_sure_strike_cooldown_rejection_is_atomic() -> None:
    game = Encounter.start(SURE_STRIKE_WARPRIEST_SETUP, rolls=(20, 1, 2, 3))
    _keep_start_choices(game)
    assert game.execute(Cast("sure_strike", slot_id="ordinary_sure_strike_1")).status is ResultStatus.COMPLETED
    assert game.execute(Strike("guard_dog", attack_id="longsword")).status is ResultStatus.COMPLETED
    before = game.inspect()
    dice_index = game._dice._index
    rejected = game.execute(Cast("sure_strike", slot_id="ordinary_sure_strike_1"))
    assert rejected.status is ResultStatus.REJECTED
    assert "immunity" in rejected.message
    assert game.inspect() == before
    assert game._dice._index == dice_index


def test_sure_strike_applies_to_divine_lance_and_preserves_spell_attack_map() -> None:
    game = Encounter.start(SURE_STRIKE_WARPRIEST_SETUP, rolls=(20, 1, 3, 18, 4, 4))
    _keep_start_choices(game)
    assert game.execute(Cast("sure_strike", slot_id="ordinary_sure_strike_1")).status is ResultStatus.COMPLETED
    result = game.execute(Cast("divine_lance", "guard_dog"))
    assert result.status is ResultStatus.COMPLETED
    check = next(event.check for event in result.events if event.check is not None)
    assert check is not None and check.dice == (3, 18)
    assert check.attack_id == "divine_lance"
    assert check.attack_count == 1 and check.map_penalty == 0
    assert not any(event.kind == "concealment_flat_check" for event in result.events)
    assert not any(event.kind == "spell_attack_hero_reroll" for event in result.events)


def test_sure_strike_terminal_cast_and_attack_path(tmp_path: Path) -> None:
    save_path = tmp_path / "sure-strike-terminal.json"
    state: dict[str, object] = {"prompt": "", "menu": "", "cast": False, "saved": False, "loaded": False, "strike": False, "outputs": []}

    def menu_choice(menu: str, label: str) -> str:
        for line in menu.splitlines():
            match = re.match(r"(\d+)\.\s+(.*)", line)
            if match and match.group(2) == label:
                return match.group(1)
        raise AssertionError(f"terminal menu lacks {label!r}: {menu}")

    def output(line: str) -> None:
        state["outputs"].append(line)  # type: ignore[union-attr]
        if line.startswith("1. "):
            state["menu"] = line
        if line == "Choice:" or line.endswith(":"):
            state["prompt"] = line

    def scripted_input() -> str:
        prompt = str(state["prompt"])
        menu = str(state["menu"])
        if prompt == "Choice prompt action:":
            return menu_choice(menu, "Resolve this choice")
        if prompt == "Choice option number:":
            if "Keep result" in menu:
                return menu_choice(menu, "Keep result")
            return menu_choice(menu, "Keep initiative")
        if prompt == "Choice:":
            if not state["cast"]:
                state["cast"] = True
                return menu_choice(menu, "Cast")
            if not state["saved"]:
                state["saved"] = True
                return menu_choice(menu, "Save")
            if not state["loaded"]:
                state["loaded"] = True
                return menu_choice(menu, "Load")
            if not state["strike"]:
                state["strike"] = True
                return menu_choice(menu, "Strike")
            return menu_choice(menu, "Quit")
        if prompt.startswith("Save file [") or prompt.startswith("Load file ["):
            return str(save_path)
        if prompt == "Spell number:":
            return next(
                line.split(".", 1)[0]
                for line in menu.splitlines()
                if ". Sure Strike (" in line
            )
        if prompt == "Casting mode:":
            return menu_choice(menu, "1 action")
        if prompt == "Prepared slot:":
            return menu_choice(menu, "ordinary_sure_strike_1 (ordinary)")
        if prompt == "Weapon / attack number:":
            return menu_choice(menu, "Longsword (longsword)")
        if prompt == "Longsword target:":
            return menu_choice(menu, "Guard Dog (guard_dog)")
        if prompt == "Target number:":
            return menu_choice(menu, "Guard Dog (guard_dog)")
        if prompt == "Damage intent:":
            return menu_choice(menu, "Use attack default (lethal)")
        if prompt == "Damage type:":
            return menu_choice(menu, "Slashing")
        raise AssertionError(f"unexpected terminal prompt {prompt!r}")

    status = run_terminal(
        setup=SURE_STRIKE_WARPRIEST_SETUP,
        rolls=(20, 1, 3, 18, 4),
        save_path=save_path,
        input_fn=scripted_input,
        output_fn=output,
    )
    transcript = "\n".join(state["outputs"])  # type: ignore[arg-type]
    assert status == 0
    assert state["cast"] and state["saved"] and state["loaded"] and state["strike"]
    assert "commits Sure Strike" in transcript
    assert "Attack: d20 3, 18" in transcript
    assert f"Saved encounter to {save_path}." in transcript
    assert f"Loaded encounter from {save_path}." in transcript


def test_saved_fortune_attack_choice_rejects_forged_sure_strike_dice(tmp_path: Path) -> None:
    game = Encounter.start(SURE_STRIKE_WARPRIEST_SETUP, rolls=(20, 1, 20, 18))
    _keep_start_choices(game)
    pending = game.execute(Strike("guard_dog", attack_id="longsword"))
    assert pending.status is ResultStatus.PAUSED
    assert pending.inspection.choice is not None
    if pending.inspection.choice.kind == "concealment_hero_reroll":
        kept = game.choose(
            pending.inspection.choice.choice_id,
            "keep",
            pending.inspection.choice.owner_actor_id,
        )
        assert kept.status is ResultStatus.PAUSED
        pending = kept
    assert pending.inspection.choice.kind == "attack_hero_reroll"
    save_path = tmp_path / "forged-sure-strike-choice.json"
    game.save(save_path)
    payload = json.loads(save_path.read_text(encoding="utf-8"))
    payload["state"]["pending_choice"]["check"]["dice"] = [3, 18]
    save_path.write_text(json.dumps(payload), encoding="utf-8")
    try:
        Encounter.load(save_path)
    except ValueError as error:
        assert "Sure Strike Hero Point" in str(error)
    else:
        raise AssertionError("forged Sure Strike Hero Point choice was accepted")
