"""Numbered terminal coverage for the local post-combat Refocus activity."""

from __future__ import annotations

from pathlib import Path

from pf2e.content import ANGELIC_FIRST_CAST_SETUP
from pf2e.encounter import Encounter
from pf2e.model import Cast, EndTurn, ResultStatus
from pf2e.terminal import build_action_menu, run_terminal
from terminal_test_helpers import BoundedTranscript


def _keep_start_choices(game: Encounter) -> None:
    while game.inspect().choice is not None:
        choice = game.inspect().choice
        assert choice is not None
        option_id = "keep" if any(option.option_id == "keep" for option in choice.options) else choice.options[0].option_id
        result = game.choose(choice.choice_id, option_id, choice.owner_actor_id)
        assert result.status is ResultStatus.COMPLETED


def _finished_spent_focus_game() -> Encounter:
    """Finish a real Angelic Sorcerer fixture with its focus point spent."""
    game = Encounter.start(ANGELIC_FIRST_CAST_SETUP, rolls=(20, 1, 1, 20, 4, 4))
    _keep_start_choices(game)

    halo = game.execute(Cast("angelic_halo"))
    assert halo.status is ResultStatus.PAUSED
    choice = halo.inspection.choice
    assert choice is not None and choice.kind == "spell_blood_magic_recipient"
    assert game.choose(choice.choice_id, "angelic_sorcerer", choice.owner_actor_id).status is ResultStatus.COMPLETED
    assert next(actor for actor in game.inspect().actors if actor.actor_id == "angelic_sorcerer").focus_points == 0

    for _ in range(3):
        assert game.execute(EndTurn()).status is ResultStatus.COMPLETED
    assert game.execute(Cast("divine_lance", "sorcerer_dog")).status is ResultStatus.COMPLETED
    assert not game.inspect().in_progress
    return game


def test_post_combat_menu_exposes_only_the_real_refocus_activity() -> None:
    entries = build_action_menu((), include_refocus=True)
    labels = tuple(label for _action_id, label in entries)

    assert labels[:2] == ("Inspect", "Refocus (10 minutes)")
    assert "Save" in labels and "Load" in labels and "Quit" in labels
    assert not any(label in labels for label in ("Rest", "Prepare", "Read Aura"))


def test_terminal_refocus_reports_ten_minute_focus_only_recovery_and_round_trips_save(
    tmp_path: Path,
    monkeypatch,
) -> None:
    finished = _finished_spent_focus_game()
    sorcerer_index = next(
        index
        for index, actor in enumerate(finished.inspect().actors, 1)
        if actor.actor_id == "angelic_sorcerer"
    )
    save_path = tmp_path / "terminal-refocus.json"

    # run_terminal starts through the same public class method as normal play;
    # inject the already-finished public game solely to isolate the recovery
    # menu from another combat script.
    def start_finished(_cls, *args, **kwargs):
        return finished

    monkeypatch.setattr(Encounter, "start", classmethod(start_finished))
    inputs = iter(("2", str(sorcerer_index), "3", "", "4", "", "6"))
    transcript = BoundedTranscript()

    status = run_terminal(
        setup=ANGELIC_FIRST_CAST_SETUP,
        save_path=save_path,
        input_fn=lambda: next(inputs),
        output_fn=transcript.append,
    )

    rendered = "\n".join(transcript)
    assert status == 0
    assert "Refocus (10 minutes)" in rendered
    assert "Refocus takes 10 minutes and restores only 1 Focus Point" in rendered
    assert "HP, spell slots, and other resources are unchanged." in rendered
    assert "Refocuses for 10 minutes and regains 1 Focus Point." in rendered
    assert "Saved encounter to" in rendered
    assert "Loaded encounter from" in rendered
    assert "Goodbye." in rendered

    restored = Encounter.load(save_path).inspect()
    sorcerer = next(actor for actor in restored.actors if actor.actor_id == "angelic_sorcerer")
    assert restored.world_time_seconds == 606
    assert (sorcerer.focus_points, sorcerer.focus_capacity) == (1, 1)


def test_terminal_can_enter_the_staged_next_encounter_after_refocus(monkeypatch) -> None:
    finished = Encounter.start(
        ANGELIC_FIRST_CAST_SETUP,
        rolls=(20, 1, 1, 20, 4, 4, 20, 1, 1),
    )
    while (choice := finished.inspect().choice) is not None:
        option_id = "keep" if any(option.option_id == "keep" for option in choice.options) else choice.options[0].option_id
        finished.choose(choice.choice_id, option_id, choice.owner_actor_id)
    finished.execute(Cast("angelic_halo"))
    choice = finished.inspect().choice
    assert choice is not None and choice.kind == "spell_blood_magic_recipient"
    finished.choose(choice.choice_id, "angelic_sorcerer", choice.owner_actor_id)
    for _ in range(3):
        finished.execute(EndTurn())
    assert not finished.execute(Cast("divine_lance", "sorcerer_dog")).inspection.in_progress
    assert finished.refocus("angelic_sorcerer").status is ResultStatus.COMPLETED

    monkeypatch.setattr(Encounter, "start", classmethod(lambda _cls, *args, **kwargs: finished))
    # Post-combat entries keep Save/Load/Restart/Quit stable; Next Encounter
    # is the final entry. Resolve the fresh initiative Hero choice, then let
    # EOF end the terminal smoke run while scene B is active.
    inputs = iter(("7", "2", "1"))
    transcript = BoundedTranscript()
    status = run_terminal(
        setup=ANGELIC_FIRST_CAST_SETUP,
        input_fn=lambda: next(inputs),
        output_fn=transcript.append,
    )

    rendered = "\n".join(transcript)
    assert status == 0
    assert "Next Encounter" in rendered
    assert "Staged Angelic Sorcerer Next Encounter begins at world time 606 seconds." in rendered
    assert "Guard Dog B" in rendered
