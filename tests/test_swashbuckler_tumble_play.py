"""Bounded public Tumble Through play for the staged Braggart.

Rules references checked 2026-09-16:

* Tumble Through: https://2e.aonprd.com/Actions.aspx?ID=2370
* Reactive Strike: https://2e.aonprd.com/Feats.aspx?ID=5832
* Bravado: https://2e.aonprd.com/Traits.aspx?ID=801
* Swashbuckler Panache and Stylish Combatant: https://2e.aonprd.com/Classes.aspx?ID=63
"""

from pathlib import Path

import pytest

import pf2e.content as content
from pf2e.encounter import Encounter
from pf2e.model import CreaturePlacement, EncounterSetup, Position, ResultStatus
from pf2e.skill_actions import TumbleThrough
from pf2e.skill_content import TUMBLE_THROUGH
from pf2e.terminal import run_terminal
from terminal_test_helpers import BoundedInput, BoundedTranscript


SETUP_ID = "staged_braggart_swashbuckler_vs_guard_dog"


def _choose(game: Encounter, option_id: str):
    choice = game.inspect().choice
    assert choice is not None
    return game.choose(choice.choice_id, option_id, choice.owner_actor_id)


def _started_game(*rolls: int) -> Encounter:
    game = Encounter.start(content.get_setup(SETUP_ID), rolls=rolls)
    for _ in range(8):
        choice = game.inspect().choice
        if choice is None:
            return game
        option_id = "keep" if any(option.option_id == "keep" for option in choice.options) else choice.options[0].option_id
        result = game.choose(choice.choice_id, option_id, choice.owner_actor_id)
        assert result.status in {ResultStatus.PAUSED, ResultStatus.COMPLETED}
    raise AssertionError("initiative did not settle")


def _actor(game: Encounter, actor_id: str):
    return game._state.creatures[actor_id]


def test_tumble_content_records_source_grounded_move_and_bravado_contract() -> None:
    assert TUMBLE_THROUGH.source_url == "https://2e.aonprd.com/Actions.aspx?ID=2370"
    assert TUMBLE_THROUGH.action_cost == 1
    assert TUMBLE_THROUGH.check_skill == "acrobatics"
    assert TUMBLE_THROUGH.target_dc == "reflex"
    assert TUMBLE_THROUGH.traits == frozenset({"move", "bravado"})
    assert TumbleThrough((Position(2, 1), Position(3, 1))).path[-1] == Position(3, 1)


def test_braggart_tumble_success_checks_reflex_moves_through_enemy_and_grants_panache() -> None:
    # Initiative d20s, Acrobatics d20. Stylish Combatant makes the check +8.
    game = _started_game(20, 1, 12)
    before = _actor(game, "braggart")
    result = game.execute(TumbleThrough((Position(2, 1), Position(3, 1))))
    assert result.status is ResultStatus.PAUSED
    result = _choose(game, "keep")
    check = next(event.check for event in result.events if event.kind == "tumble_through_check")
    assert check is not None
    assert (check.die, check.modifier, check.total, check.dc) == (12, 8, 20, 17)
    assert _actor(game, "braggart").position == Position(3, 1)
    assert _actor(game, "braggart").panache
    assert _actor(game, "braggart").panache_expires_at_end is None
    assert game.effective_speed_ft("braggart") == 30
    assert _actor(game, "braggart").actions_remaining == before.actions_remaining - 1
    assert _actor(game, "braggart").strikes_this_turn == 0
    assert any(event.kind == "move_step" and event.position == Position(2, 1) for event in result.events)


def test_tumble_failure_stops_in_start_square_and_grants_temporary_panache() -> None:
    # Initiative d20s, ordinary failure Acrobatics d20. No square is entered.
    game = _started_game(20, 1, 4)
    result = game.execute(TumbleThrough((Position(2, 1), Position(3, 1))))
    assert result.status is ResultStatus.PAUSED
    result = _choose(game, "keep")
    assert any(event.kind == "tumble_through_failed" for event in result.events)
    assert _actor(game, "braggart").position == Position(1, 1)
    assert _actor(game, "braggart").panache
    assert _actor(game, "braggart").panache_expires_at_end == 2


def test_tumble_critical_failure_stops_without_panache() -> None:
    game = _started_game(20, 1, 1)
    result = game.execute(TumbleThrough((Position(2, 1), Position(3, 1))))
    assert result.status is ResultStatus.PAUSED
    result = _choose(game, "keep")
    check = next(event.check for event in result.events if event.kind == "tumble_through_check")
    assert check is not None and check.degree.name == "CRITICAL_FAILURE"
    assert _actor(game, "braggart").position == Position(1, 1)
    assert not _actor(game, "braggart").panache


def test_tumble_skill_choice_saves_and_resolves_the_same_path(tmp_path: Path) -> None:
    game = _started_game(20, 1, 12)
    started = game.execute(TumbleThrough((Position(2, 1), Position(3, 1))))
    assert started.status is ResultStatus.PAUSED
    choice = started.inspection.choice
    assert choice is not None and choice.kind == "family_action"
    save_path = tmp_path / "tumble-skill-choice.json"
    game.save(save_path)
    restored = Encounter.load(save_path)
    assert restored.inspect().choice == choice
    result = _choose(restored, "keep")
    assert result.status is ResultStatus.COMPLETED
    assert _actor(restored, "braggart").position == Position(3, 1)
    assert _actor(restored, "braggart").panache


def test_tumble_reaction_choice_saves_and_declining_reaction_resumes_crossing(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    base = content.get_setup(SETUP_ID)
    setup = EncounterSetup(
        setup_id="review_braggart_tumble_reactive_fighter",
        name="Review Braggart Tumble Through reactive fighter",
        width=4,
        height=3,
        placements=(
            CreaturePlacement("braggart", base.placements[0].definition_id, "Braggart", "blue", Position(0, 1)),
            CreaturePlacement("reactive_fighter", content.MELEE_FIGHTER_M.definition_id, "Reactive Fighter", "red", Position(1, 1)),
        ),
    )
    monkeypatch.setattr(content, "_STAGED_SETUPS", content._STAGED_SETUPS | {setup.setup_id: setup})
    game = Encounter.start(setup, rolls=(20, 1, 12))
    for _ in range(8):
        choice = game.inspect().choice
        if choice is None:
            break
        game.choose(choice.choice_id, "keep", choice.owner_actor_id)
    assert game.inspect().turn_actor_id == "braggart"
    result = game.execute(TumbleThrough((Position(1, 1), Position(2, 1))))
    assert result.status is ResultStatus.PAUSED
    reaction = game.inspect().choice
    assert reaction is not None and reaction.kind == "reaction"
    save_path = tmp_path / "tumble-reaction.json"
    game.save(save_path)
    restored = Encounter.load(save_path)
    assert restored.inspect().choice == reaction
    declined = _choose(restored, "decline")
    assert declined.status is ResultStatus.PAUSED
    assert restored.inspect().choice is not None and restored.inspect().choice.kind == "family_action"
    resumed = _choose(restored, "keep")
    assert resumed.status is ResultStatus.COMPLETED
    assert _actor(restored, "braggart").position == Position(2, 1)
    assert _actor(restored, "braggart").panache
    assert _actor(restored, "reactive_fighter").reaction_available


def test_tumble_lead_in_reaction_saves_before_the_acrobatics_check(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    base = content.get_setup(SETUP_ID)
    setup = EncounterSetup(
        setup_id="review_braggart_tumble_lead_in_reaction",
        name="Review Braggart Tumble Through lead-in reaction",
        width=5,
        height=3,
        placements=(
            CreaturePlacement("braggart", base.placements[0].definition_id, "Braggart", "blue", Position(0, 1)),
            CreaturePlacement("reactive_fighter", content.MELEE_FIGHTER_M.definition_id, "Reactive Fighter", "red", Position(2, 1)),
        ),
    )
    monkeypatch.setattr(content, "_STAGED_SETUPS", content._STAGED_SETUPS | {setup.setup_id: setup})
    game = Encounter.start(setup, rolls=(20, 1, 12))
    for _ in range(8):
        choice = game.inspect().choice
        if choice is None:
            break
        game.choose(choice.choice_id, "keep", choice.owner_actor_id)
    started = game.execute(TumbleThrough((Position(1, 1), Position(2, 1), Position(3, 1))))
    assert started.status is ResultStatus.PAUSED
    reaction = started.inspection.choice
    assert reaction is not None and reaction.kind == "reaction"
    assert _actor(game, "braggart").position == Position(1, 1)

    save_path = tmp_path / "tumble-lead-in-reaction.json"
    game.save(save_path)
    restored = Encounter.load(save_path)
    assert restored.inspect().choice == reaction
    after_decline = _choose(restored, "decline")
    assert after_decline.status is ResultStatus.PAUSED
    skill_choice = after_decline.inspection.choice
    assert skill_choice is not None and skill_choice.kind == "family_action"
    assert any(event.kind == "move_step" and event.position == Position(1, 1) for event in started.events)
    crossed = _choose(restored, "keep")
    assert _actor(restored, "braggart").position == Position(3, 1)
    assert _actor(restored, "braggart").panache


def test_tumble_insufficient_speed_uses_failure_result_without_partial_movement(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    base = content.get_setup(SETUP_ID)
    setup = EncounterSetup(
        setup_id="review_braggart_tumble_insufficient_speed",
        name="Review Braggart Tumble Through insufficient Speed",
        width=8,
        height=3,
        placements=(
            CreaturePlacement("braggart", base.placements[0].definition_id, "Braggart", "blue", Position(0, 1)),
            CreaturePlacement("braggart_dog", base.placements[1].definition_id, "Guard Dog", "red", Position(1, 1)),
        ),
    )
    monkeypatch.setattr(content, "_STAGED_SETUPS", content._STAGED_SETUPS | {setup.setup_id: setup})
    game = Encounter.start(setup, rolls=(20, 1, 12))
    for _ in range(8):
        choice = game.inspect().choice
        if choice is None:
            break
        game.choose(choice.choice_id, "keep", choice.owner_actor_id)
    result = game.execute(TumbleThrough(tuple(Position(x, 1) for x in range(1, 8))))
    assert result.status is ResultStatus.PAUSED
    result = _choose(game, "keep")
    assert any(event.kind == "tumble_through_failed" for event in result.events)
    assert _actor(game, "braggart").position == Position(0, 1)
    assert _actor(game, "braggart").panache
    assert _actor(game, "braggart").panache_expires_at_end == 2


def test_ordinary_fighter_can_tumble_without_swash_bravado(monkeypatch: pytest.MonkeyPatch) -> None:
    base = content.get_setup(SETUP_ID)
    setup = EncounterSetup(
        setup_id="review_ordinary_fighter_tumble",
        name="Review ordinary Tumble Through",
        width=4,
        height=3,
        placements=(
            CreaturePlacement("fighter", content.MELEE_FIGHTER_M.definition_id, "Fighter", "blue", Position(0, 1)),
            CreaturePlacement("dog", base.placements[1].definition_id, "Guard Dog", "red", Position(1, 1)),
        ),
    )
    monkeypatch.setattr(content, "_STAGED_SETUPS", content._STAGED_SETUPS | {setup.setup_id: setup})
    game = Encounter.start(setup, rolls=(20, 1, 20))
    for _ in range(8):
        choice = game.inspect().choice
        if choice is None:
            break
        game.choose(choice.choice_id, "keep", choice.owner_actor_id)
    result = game.execute(TumbleThrough((Position(1, 1), Position(2, 1))))
    assert result.status is ResultStatus.PAUSED
    result = _choose(game, "keep")
    assert result.status is ResultStatus.COMPLETED
    assert _actor(game, "fighter").position == Position(2, 1)
    assert not _actor(game, "fighter").panache


def test_tumble_invalid_path_rejects_atomically() -> None:
    game = _started_game(20, 1, 12)
    before = game.inspect()
    dice_before = game._dice.to_data()
    result = game.execute(TumbleThrough((Position(3, 1), Position(4, 1))))
    assert result.status is ResultStatus.REJECTED
    assert "adjacent" in result.message
    assert game.inspect() == before
    assert game._dice.to_data() == dice_before

    result = game.execute(TumbleThrough((Position(2, 1),)))
    assert result.status is ResultStatus.REJECTED
    assert "continue beyond" in result.message
    assert game.inspect() == before


def test_terminal_exposes_bounded_tumble_path_and_completes_victory() -> None:
    transcript = BoundedTranscript()
    state = {"menu": "", "prompt": "", "choice_block": "", "phase": "tumble"}

    def output(line: str) -> None:
        transcript.append(line)
        if line.startswith("1. "):
            state["menu"] = line
        if "choice owner:" in line:
            state["choice_block"] = line
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
            if "initiative" in state["choice_block"]:
                return choose("Keep initiative")
            return choose("Keep the current result")
        if prompt == "Choice:":
            if state["phase"] == "tumble":
                state["phase"] = "done"
                return choose("Tumble Through")
            return choose("Quit")
        if prompt.startswith("Tumble Through path"):
            return "C2 D2"
        raise AssertionError(f"unexpected terminal prompt: {prompt!r}")

    result = run_terminal(
        setup=content.get_setup(SETUP_ID),
        rolls=(20, 1, 12),
        input_fn=BoundedInput(scripted_input, max_calls=20),
        output_fn=output,
    )
    assert result == 0
    rendered = "\n".join(transcript)
    assert "Tumble Through" in rendered


def test_terminal_tumble_then_dagger_reaches_public_victory() -> None:
    transcript = BoundedTranscript()
    state = {"menu": "", "prompt": "", "choice_block": "", "phase": "tumble"}

    def output(line: str) -> None:
        transcript.append(line)
        if line.startswith("1. "):
            state["menu"] = line
        if "choice owner:" in line:
            state["choice_block"] = line
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
            if "initiative" in state["choice_block"]:
                return choose("Keep initiative")
            if "Strike check" in state["choice_block"]:
                return choose("Keep result")
            return choose("Keep the current result")
        if prompt == "Choice:":
            if state["phase"] == "tumble":
                state["phase"] = "strike"
                return choose("Tumble Through")
            if state["phase"] == "strike":
                state["phase"] = "done"
                return choose("Strike")
            return choose("Quit")
        if prompt.startswith("Tumble Through path"):
            return "C2 D2"
        if prompt == "Weapon / attack number:":
            return choose("Dagger", prefix=True)
        if prompt in {"Target number:", "Dagger target:"}:
            return choose("Guard Dog", prefix=True)
        if prompt == "Damage intent:":
            return choose("Use attack default", prefix=True)
        raise AssertionError(f"unexpected terminal prompt: {prompt!r}")

    result = run_terminal(
        setup=content.get_setup(SETUP_ID),
        rolls=(20, 1, 12, 20, 2, 3),
        input_fn=BoundedInput(scripted_input, max_calls=30),
        output_fn=output,
    )
    assert result == 0
    rendered = "\n".join(transcript)
    assert "Guard Dog (red) — HP 0/8" in rendered
    assert "Tumble Through" in rendered
