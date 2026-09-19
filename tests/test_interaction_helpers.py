"""Focused contract tests for the bounded public encounter harness."""

from pathlib import Path

import pytest

from interaction_helpers import EncounterHarness
from pf2e.content import S2_SETUP
from pf2e.encounter import Encounter
from pf2e.model import ResultStatus


def _game(*, max_commands: int = 160, max_rounds: int = 12) -> EncounterHarness:
    # Distinct fixed initiative faces avoid a tie; PC reroll prompts remain real.
    return EncounterHarness(
        Encounter.start(S2_SETUP, rolls=(20, 19, 10, 8)),
        "helper-contract",
        max_commands=max_commands,
        max_rounds=max_rounds,
    )


def test_harness_checks_choice_checkpoint_and_turn_continuation(tmp_path: Path) -> None:
    harness = _game()
    choice = harness.pending_choice(
        kind="initiative_hero_reroll", owner_actor_id="fighter_a", options=("keep",)
    )
    assert choice.choice_id > 0
    result = harness.choose(
        kind="initiative_hero_reroll",
        owner_actor_id="fighter_a",
        option_id="keep",
        expected_status=ResultStatus.PAUSED,
    )
    assert result.inspection.choice is not None
    assert result.inspection.choice.owner_actor_id == "fighter_b"

    harness.keep_initiative()
    assert harness.inspection.turn_actor_id == "fighter_a"
    harness.checkpoint(tmp_path / "initiative.json")
    harness.end_turn(expected_actor_id="fighter_b")
    assert harness.actor("fighter_b").actions_remaining == 3


def test_harness_bound_reports_scenario_and_can_continue_after_limit_is_raised() -> None:
    harness = _game(max_commands=1)

    with pytest.raises(AssertionError, match=r"\[helper-contract\].*command bound exceeded") as error:
        harness.keep_initiative()

    assert "commands=1/1" in str(error.value)
    assert harness.pending_choice(
        kind="initiative_hero_reroll", owner_actor_id="fighter_b", options=("keep",)
    )
    harness.max_commands = 4
    harness.keep_initiative()
    assert harness.inspection.turn_actor_id == "fighter_a"
