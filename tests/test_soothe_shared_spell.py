"""Bounded public rank-1 Soothe behavior over the shared casting engine.

Rules reference:
- Soothe: https://2e.aonprd.com/Spells.aspx?ID=1678
- The checked-in divine rules packet records the same remaster traits,
  willing-target range, 1d10+4 healing, and one-minute mental-save bonus.
"""

from __future__ import annotations

import re
from dataclasses import replace
from pathlib import Path

from pf2e.checks import combine_modifiers
import pf2e.content as content
from pf2e.content import SOOTHE_TEST_CASTER, SOOTHE_TEST_SETUP
from pf2e.encounter import Encounter
from pf2e.model import ActionContinuation, Cast, EndTurn, Position, ResultStatus, Strike
from pf2e.terminal import run_terminal
from terminal_test_helpers import BoundedInput, BoundedTranscript


def _actor(game: Encounter, actor_id: str):
    return next(actor for actor in game.inspect().actors if actor.actor_id == actor_id)


def _settle_initiative(game: Encounter) -> None:
    choice = game.inspect().choice
    assert choice is not None and choice.kind == "initiative_hero_reroll"
    result = game.choose(choice.choice_id, "keep", choice.owner_actor_id)
    assert result.status is ResultStatus.COMPLETED
    assert game.inspect().turn_actor_id == "soothe_caster"


def _injured_soothe_game() -> Encounter:
    # Initiative d20s, Guard Dog critical jaws d20 and d6, then Soothe d10.
    game = Encounter.start(SOOTHE_TEST_SETUP, rolls=(10, 10, 20, 3, 4, 20, 4))
    _settle_initiative(game)
    assert game.execute(EndTurn()).status is ResultStatus.COMPLETED
    result = game.execute(Strike("soothe_caster", "jaws"))
    assert result.status is ResultStatus.COMPLETED
    assert _actor(game, "soothe_caster").hp == 9
    assert game.execute(EndTurn()).status is ResultStatus.COMPLETED
    assert game.inspect().turn_actor_id == "soothe_caster"
    return game


def _cast_soothe(game: Encounter):
    result = game.execute(Cast("soothe", "soothe_caster", 2, "soothe_1"))
    assert result.status is ResultStatus.PAUSED
    choice = result.inspection.choice
    assert choice is not None and choice.kind == "spell_willingness"
    assert {option.option_id for option in choice.options} == {"willing", "unwilling"}
    return choice


def test_soothe_heals_genuine_damage_spends_slot_and_round_trips_pending_choice(tmp_path: Path) -> None:
    assert SOOTHE_TEST_CASTER.spell_tradition == "occult"
    assert tuple(spell.spell_id for spell in SOOTHE_TEST_CASTER.prepared_spells) == ("soothe",)
    game = _injured_soothe_game()
    choice = _cast_soothe(game)
    assert _actor(game, "soothe_caster").actions_remaining == 1
    slot = next(slot for slot in _actor(game, "soothe_caster").prepared_slots if slot.slot_id == "soothe_1")
    assert slot.spent is True

    save_path = tmp_path / "soothe-pending.json"
    game.save(save_path)
    restored = Encounter.load(save_path)
    pending = restored.inspect().choice
    assert pending is not None and pending.kind == "spell_willingness"
    assert pending.prompt == "Is Soothe Caster willing to receive Soothe?"
    accepted = restored.choose(pending.choice_id, "willing", pending.owner_actor_id)
    assert accepted.status is ResultStatus.COMPLETED
    assert any(event.kind == "healing" for event in accepted.events)
    assert any(event.kind == "soothe_protection_applied" for event in accepted.events)
    assert _actor(restored, "soothe_caster").hp == 17  # 9 + (1d10=4 + 4)
    effect = next(effect for effect in restored._state.active_effects if effect.kind == "soothe")
    assert (effect.value, effect.expires_at_source_start, effect.expires_at_world_time) == (2, 12, 66)
    assert effect.source_actor_id == effect.target_actor_id == "soothe_caster"
    active_save = tmp_path / "soothe-active.json"
    restored.save(active_save)
    active_loaded = Encounter.load(active_save)
    loaded_effect = next(effect for effect in active_loaded._state.active_effects if effect.kind == "soothe")
    assert loaded_effect == effect


def test_soothe_adds_only_mental_save_status_bonus_and_expires_at_source_start() -> None:
    game = _injured_soothe_game()
    choice = _cast_soothe(game)
    game.choose(choice.choice_id, "willing", choice.owner_actor_id)
    target = game._state.creatures["soothe_caster"]
    continuation = ActionContinuation(
        kind="cast",
        actor_id="soothe_caster",
        target_id="soothe_caster",
        spell_id="fear",
        spell_actions=2,
    )
    mental = game._spell_save_modifier_breakdown(game._state, target, continuation, "fear", "will")
    nonmental = game._spell_save_modifier_breakdown(game._state, target, continuation, "void_warp", "fortitude")
    assert [(item.amount, item.modifier_type, item.source) for item in mental if item.source == "Soothe"] == [(2, "status", "Soothe")]
    assert not any(item.source == "Soothe" for item in nonmental)
    guided = game._spell_save_modifier_breakdown(
        game._state,
        target,
        ActionContinuation(
            kind="cast",
            actor_id="soothe_caster",
            target_id="soothe_caster",
            spell_id="fear",
            spell_actions=2,
            guidance_bonus=1,
        ),
        "fear",
        "will",
    )
    assert combine_modifiers(tuple(item for item in guided if item.modifier_type == "status")) == 2

    # The one-minute protection remains through source start 11 and is removed
    # exactly when the caster reaches its source-start deadline 12.
    while game._state.actor_start_counts["soothe_caster"] < 11:
        assert game.execute(EndTurn()).status is ResultStatus.COMPLETED
    assert any(effect.kind == "soothe" for effect in game._state.active_effects)
    while game._state.actor_start_counts["soothe_caster"] < 12:
        assert game.execute(EndTurn()).status is ResultStatus.COMPLETED
    assert game._state.world_time_seconds == 66
    assert not any(effect.kind == "soothe" for effect in game._state.active_effects)


def test_soothe_rejects_invalid_cast_atomically_and_fight_can_finish_after_healing() -> None:
    game = _injured_soothe_game()
    choice = _cast_soothe(game)
    game.choose(choice.choice_id, "willing", choice.owner_actor_id)
    before = game.inspect()
    dice_index = game._dice._index
    rejected = game.execute(Cast("soothe", "soothe_caster", 1, "soothe_1"))
    assert rejected.status is ResultStatus.REJECTED
    assert game.inspect() == before
    assert game._dice._index == dice_index

    # The actual encounter remains playable through a victory after the
    # injured target is restored; the final supplied d20/d8 are a critical
    # longsword hit that defeats the dog.
    assert game.execute(EndTurn()).status is ResultStatus.COMPLETED
    assert game.execute(EndTurn()).status is ResultStatus.COMPLETED
    strike = game.execute(Strike("soothe_dog", "longsword"))
    assert strike.status is ResultStatus.PAUSED
    assert strike.inspection.choice is not None and strike.inspection.choice.kind == "attack_hero_reroll"
    finished = game.choose(strike.inspection.choice.choice_id, "keep", strike.inspection.choice.owner_actor_id)
    assert finished.status is ResultStatus.COMPLETED
    assert finished.inspection.in_progress is False
    assert finished.inspection.winner_team == "blue"


def test_soothe_enforces_30_foot_range_and_preserves_state_and_dice_on_rejection(monkeypatch) -> None:
    far_setup = replace(
        SOOTHE_TEST_SETUP,
        setup_id="soothe_staged_divine_caster_far_guard_dog",
        width=10,
        placements=tuple(
            replace(placement, position=Position(9, 1))
            if placement.actor_id == "soothe_dog" else placement
            for placement in SOOTHE_TEST_SETUP.placements
        ),
    )
    monkeypatch.setattr(
        content,
        "_STAGED_SETUPS",
        content._STAGED_SETUPS | {far_setup.setup_id: far_setup},
    )
    game = Encounter.start(far_setup, rolls=(10, 10))
    _settle_initiative(game)
    assert "soothe_dog" not in game._spell_targets_for_cast(
        game._state, game._state.creatures["soothe_caster"], "soothe", 2
    )
    before = game.inspect()
    dice_index = game._dice._index
    rejected = game.execute(Cast("soothe", "soothe_dog", 2, "soothe_1"))
    assert rejected.status is ResultStatus.REJECTED
    assert game.inspect() == before
    assert game._dice._index == dice_index


def test_dim_soothe_saved_concealment_and_willingness_resume_is_atomic(tmp_path: Path, monkeypatch) -> None:
    dim_setup = replace(
        SOOTHE_TEST_SETUP,
        setup_id="soothe_staged_divine_caster_dim",
        ambient_light="dim",
    )
    monkeypatch.setattr(
        content,
        "_STAGED_SETUPS",
        content._STAGED_SETUPS | {dim_setup.setup_id: dim_setup},
    )
    game = Encounter.start(dim_setup, rolls=(10, 10, 5, 4))
    _settle_initiative(game)
    started = game.execute(Cast("soothe", "soothe_dog", 2, "soothe_1"))
    assert started.status is ResultStatus.PAUSED
    concealment = started.inspection.choice
    assert concealment is not None and concealment.kind == "concealment_hero_reroll"
    assert concealment.details == ("Original flat check: d20 5 vs DC 5.",)

    saved_concealment = tmp_path / "soothe-dim-concealment.json"
    game.save(saved_concealment)
    restored = Encounter.load(saved_concealment)
    pending = restored.inspect().choice
    assert pending is not None and pending.kind == "concealment_hero_reroll"
    before = restored.inspect()
    dice_index = restored._dice._index
    invalid = restored.choose(pending.choice_id, "willing", pending.owner_actor_id)
    assert invalid.status is ResultStatus.REJECTED
    assert restored.inspect() == before
    assert restored._dice._index == dice_index

    passed = restored.choose(pending.choice_id, "keep", pending.owner_actor_id)
    assert passed.status is ResultStatus.PAUSED
    willingness = passed.inspection.choice
    assert willingness is not None and willingness.kind == "spell_willingness"
    assert willingness.prompt == "Is Guard Dog willing to receive Soothe?"
    saved_willingness = tmp_path / "soothe-dim-willingness.json"
    restored.save(saved_willingness)
    resumed = Encounter.load(saved_willingness)
    willingness = resumed.inspect().choice
    assert willingness is not None and willingness.kind == "spell_willingness"
    before = resumed.inspect()
    dice_index = resumed._dice._index
    invalid = resumed.choose(willingness.choice_id, "invalid", willingness.owner_actor_id)
    assert invalid.status is ResultStatus.REJECTED
    assert resumed.inspect() == before
    assert resumed._dice._index == dice_index
    accepted = resumed.choose(willingness.choice_id, "willing", willingness.owner_actor_id)
    assert accepted.status is ResultStatus.COMPLETED
    assert any(event.kind == "concealment_passed" for event in passed.events)
    assert any(event.kind == "soothe_protection_applied" for event in accepted.events)
    assert _actor(resumed, "soothe_caster").actions_remaining == 1
    slot = next(slot for slot in _actor(resumed, "soothe_caster").prepared_slots if slot.slot_id == "soothe_1")
    assert slot.spent is True
    effect = next(effect for effect in resumed._state.active_effects if effect.kind == "soothe")
    assert effect.target_actor_id == "soothe_dog"


def _menu_choice(menu: str, label: str, *, prefix: bool = False) -> str:
    for line in menu.splitlines():
        match = re.match(r"(\d+)\.\s+(.*)", line)
        if match and (match.group(2).startswith(label) if prefix else match.group(2) == label):
            return match.group(1)
    raise AssertionError(f"menu label missing: {label!r}\n{menu}")


def test_terminal_runs_real_damaged_soothe_save_load_path_with_bounded_io(tmp_path: Path) -> None:
    save_path = tmp_path / "soothe-terminal.json"
    transcript = BoundedTranscript(max_lines=500, max_chars=100_000)
    state: dict[str, str | bool] = {
        "menu": "",
        "prompt": "",
        "choice_block": "",
        "phase": "damage_setup",
        "saved": False,
        "loaded": False,
    }

    def output(line: str) -> None:
        transcript.append(line)
        if line.startswith("1. "):
            state["menu"] = line
        if "choice owner:" in line:
            state["choice_block"] = line
        if line == "Choice:" or line.endswith(":") or line.startswith(("Save file [", "Load file [")):
            state["prompt"] = line

    def scripted_input() -> str:
        prompt = state["prompt"]
        menu = str(state["menu"])
        phase = state["phase"]
        if prompt == "Choice prompt action:":
            if "initiative" in str(state["choice_block"]):
                return _menu_choice(menu, "Resolve this choice")
            if not state["saved"]:
                state["saved"] = True
                return _menu_choice(menu, "Save")
            if not state["loaded"]:
                state["loaded"] = True
                return _menu_choice(menu, "Load")
            return _menu_choice(menu, "Resolve this choice")
        if prompt == "Choice option number:":
            if "initiative" in str(state["choice_block"]):
                return _menu_choice(menu, "Keep initiative")
            return _menu_choice(menu, "Willing")
        if prompt.startswith("Save file [") or prompt.startswith("Load file ["):
            return str(save_path)
        if prompt == "Choice:":
            if phase == "damage_setup":
                state["phase"] = "dog_strike"
                return _menu_choice(menu, "End Turn")
            if phase == "dog_strike":
                state["phase"] = "dog_end"
                return _menu_choice(menu, "Strike")
            if phase == "dog_end":
                state["phase"] = "cast"
                return _menu_choice(menu, "End Turn")
            if phase == "cast":
                state["phase"] = "done"
                return _menu_choice(menu, "Cast")
            return _menu_choice(menu, "Quit")
        if prompt == "Target number:":
            return _menu_choice(menu, "Soothe Caster", prefix=True)
        if prompt == "Weapon / attack number:":
            return _menu_choice(menu, "Jaws", prefix=True)
        if prompt == "Damage intent:":
            return _menu_choice(menu, "Use attack default", prefix=True)
        if prompt == "Spell number:":
            return next(
                line.split(". ", 1)[0]
                for line in menu.splitlines()
                if ". Soothe (" in line
            )
        if prompt == "Casting mode:":
            return _menu_choice(menu, "2 actions")
        if prompt == "Prepared slot:":
            return _menu_choice(menu, "soothe_1 (ordinary)")
        raise AssertionError(f"unexpected terminal prompt: {prompt!r}")

    status = run_terminal(
        setup=SOOTHE_TEST_SETUP,
        rolls=(10, 10, 20, 3, 4),
        save_path=save_path,
        input_fn=BoundedInput(scripted_input, max_calls=80),
        output_fn=output,
    )
    rendered = "\n".join(transcript)
    assert status == 0
    assert state["saved"] is True and state["loaded"] is True
    assert "Soothe" in rendered
    assert "Saved encounter" in rendered and "Loaded encounter" in rendered
    assert "heals" in rendered
