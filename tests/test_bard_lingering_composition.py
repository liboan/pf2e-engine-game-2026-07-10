"""Source-grounded staged Maestro Lingering Composition play.

Sources: https://2e.aonprd.com/Spells.aspx?ID=1769 and
https://2e.aonprd.com/Classes.aspx?ID=32.  Every target in this finite
fixture is level 1, so its standard-difficulty Performance DC is 15.
"""

from __future__ import annotations

import pytest

from pf2e.content import get_setup
from pf2e.encounter import Encounter
from pf2e.model import Cast, Choose, EndTurn, LingeringComposition, ResultStatus, Strike
from pf2e.terminal import run_terminal
from terminal_test_helpers import BoundedInput, BoundedTranscript


SETUP = "staged_maestro_bard_courageous_anthem_vs_guard_dog"


def _finish_start_choices(game: Encounter) -> None:
    while (choice := game.inspect().choice) is not None:
        option = "keep" if any(row.option_id == "keep" for row in choice.options) else choice.options[0].option_id
        assert game.choose(choice.choice_id, option, choice.owner_actor_id).status in {
            ResultStatus.PAUSED, ResultStatus.COMPLETED,
        }


def _keep_pending_result(game: Encounter, result):
    while result.status is ResultStatus.PAUSED:
        choice = game.inspect().choice
        assert choice is not None
        assert any(option.option_id == "keep" for option in choice.options)
        result = game.execute(Choose(choice.choice_id, "keep", choice.owner_actor_id))
    return result


@pytest.mark.parametrize(
    ("die", "rounds", "remaining_focus"),
    ((20, 4, 1), (8, 3, 1), (7, 1, 2), (1, 1, 2)),
)
def test_lingering_performance_result_controls_duration_and_failure_refund(die, rounds, remaining_focus) -> None:
    game = Encounter.start(get_setup(SETUP), rolls=(20, 1, 1, die))
    _finish_start_choices(game)
    assert game.execute(LingeringComposition()).status is ResultStatus.COMPLETED
    resolved = _keep_pending_result(game, game.execute(Cast("courageous_anthem")))
    assert resolved.status is ResultStatus.COMPLETED
    check = next(event.check for event in resolved.events if event.kind == "lingering_composition_resolved")
    assert check is not None and (check.modifier, check.dc) == (7, 15)
    assert game._state.creatures["maestro_bard"].focus_points == remaining_focus
    assert {
        effect.expires_at_source_start
        for effect in game._state.active_effects
        if effect.kind == "courageous_anthem"
    } == {1 + rounds}


def test_lingering_saved_hero_choice_preserves_pending_check_and_can_keep(tmp_path) -> None:
    game = Encounter.start(get_setup(SETUP), rolls=(20, 1, 1, 8))
    _finish_start_choices(game)
    game._state.creatures["maestro_bard"].hero_points = 1
    assert game.execute(LingeringComposition()).status is ResultStatus.COMPLETED
    paused = game.execute(Cast("courageous_anthem"))
    assert paused.status is ResultStatus.PAUSED
    path = tmp_path / "lingering-check.json"
    game.save(path)
    game = Encounter.load(path)
    choice = game.inspect().choice
    assert choice is not None and choice.kind == "lingering_composition_hero_reroll"
    resolved = game.execute(Choose(choice.choice_id, "keep", choice.owner_actor_id))
    assert resolved.status is ResultStatus.COMPLETED
    assert game._state.creatures["maestro_bard"].focus_points == 1
    assert {effect.expires_at_source_start for effect in game._state.active_effects if effect.kind == "courageous_anthem"} == {4}


def test_lingering_rejects_zero_focus_atomically_and_an_intervening_action_consumes_it() -> None:
    game = Encounter.start(get_setup(SETUP), rolls=(20, 1, 1))
    _finish_start_choices(game)
    bard = game._state.creatures["maestro_bard"]
    bard.focus_points = 0
    before = game.inspect()
    assert game.execute(LingeringComposition()).status is ResultStatus.REJECTED
    assert game.inspect() == before
    bard.focus_points = 1
    assert game.execute(LingeringComposition()).status is ResultStatus.COMPLETED
    assert game.execute(EndTurn()).status is ResultStatus.COMPLETED
    assert not game._state.creatures["maestro_bard"].lingering_composition_pending


def test_lingering_success_carries_anthem_to_a_later_round_and_improves_real_strike() -> None:
    # Initiative; Performance success; later allied Strike and damage.
    game = Encounter.start(get_setup(SETUP), rolls=(20, 1, 1, 8, 10, 4))
    _finish_start_choices(game)
    assert game.execute(LingeringComposition()).status is ResultStatus.COMPLETED
    assert _keep_pending_result(game, game.execute(Cast("courageous_anthem"))).status is ResultStatus.COMPLETED
    assert game.execute(EndTurn()).status is ResultStatus.COMPLETED
    assert game.execute(EndTurn()).status is ResultStatus.COMPLETED
    strike = game.execute(Strike("bard_dog", "longsword"))
    if strike.status is ResultStatus.PAUSED:
        choice = game.inspect().choice
        assert choice is not None
        strike = game.execute(Choose(choice.choice_id, "keep", choice.owner_actor_id))
    damage = next(event.damage for event in strike.events if event.damage is not None)
    assert damage is not None and damage.total == 9
    assert {effect.expires_at_source_start for effect in game._state.active_effects if effect.kind == "courageous_anthem"} == {4}


def test_resolved_extended_anthem_round_trips_its_source_and_absolute_deadlines(tmp_path) -> None:
    game = Encounter.start(get_setup(SETUP), rolls=(20, 1, 1, 8))
    _finish_start_choices(game)
    assert game.execute(LingeringComposition()).status is ResultStatus.COMPLETED
    assert _keep_pending_result(game, game.execute(Cast("courageous_anthem"))).status is ResultStatus.COMPLETED
    effect = next(effect for effect in game._state.active_effects if effect.kind == "courageous_anthem")
    assert (effect.expires_at_source_start, effect.expires_at_world_time) == (4, 18)
    path = tmp_path / "extended-anthem.json"
    game.save(path)
    restored = Encounter.load(path)
    restored_effect = next(effect for effect in restored._state.active_effects if effect.kind == "courageous_anthem")
    assert (restored_effect.expires_at_source_start, restored_effect.expires_at_world_time) == (4, 18)


def test_bounded_terminal_can_use_lingering_then_cast_anthem() -> None:
    transcript = BoundedTranscript(max_lines=300, max_chars=50_000)
    state = {"menu": "", "prompt": "", "phase": "lingering"}

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
        raise AssertionError(f"missing {label!r}: {state['menu']!r}")

    def scripted_input() -> str:
        prompt = state["prompt"]
        if prompt == "Choice prompt action:":
            return choose("Resolve this choice")
        if prompt == "Choice option number:":
            for label in ("Keep initiative", "Keep result"):
                try:
                    return choose(label, prefix=True)
                except AssertionError:
                    pass
            raise AssertionError(f"unexpected choice menu: {state['menu']!r}")
        if prompt == "Choice:":
            if state["phase"] == "lingering":
                state["phase"] = "cast"
                return choose("Lingering Composition")
            if state["phase"] == "cast":
                state["phase"] = "quit"
                return choose("Cast")
            return choose("Quit")
        if prompt == "Spell number:":
            return choose("Courageous Anthem", prefix=True)
        if prompt == "Casting mode:":
            return choose("1 action")
        raise AssertionError(f"unexpected terminal prompt: {prompt!r}")

    assert run_terminal(
        setup=get_setup(SETUP), rolls=(20, 1, 1, 8),
        input_fn=BoundedInput(scripted_input, max_calls=35), output_fn=output,
    ) == 0
    assert "Lingering Composition" in "\n".join(transcript)
