"""Source-grounded public expectations for Pursue a Lead and Clue In.

Rules references checked 2026-09-16:

* https://2e.aonprd.com/Classes.aspx?ID=59 (On the Case)
* https://2e.aonprd.com/Actions.aspx?ID=2813 (Devise a Stratagem)
"""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest

import pf2e.content as content
from pf2e.encounter import Encounter
from pf2e.investigator import ATTACK_STRATAGEM, DeviseStratagem, InvestigationCheck, PursueLead
from pf2e.investigator_content import (
    FORENSIC_INVESTIGATOR_VS_TWO_DOGS,
    INVESTIGATOR_CLUE_ROOM,
)
from pf2e.model import ResultStatus
from pf2e.terminal import build_action_menu, run_terminal
from terminal_test_helpers import BoundedInput, BoundedTranscript


def _finished_game(monkeypatch: pytest.MonkeyPatch, *, rolls=(20, 1, 2, 11)) -> Encounter:
    setup = FORENSIC_INVESTIGATOR_VS_TWO_DOGS
    monkeypatch.setattr(content, "_STAGED_SETUPS", content._STAGED_SETUPS | {setup.setup_id: setup})
    game = Encounter.start(setup, rolls=rolls)
    while (choice := game.inspect().choice) is not None:
        option_id = "keep" if any(option.option_id == "keep" for option in choice.options) else choice.options[0].option_id
        result = game.choose(choice.choice_id, option_id, choice.owner_actor_id)
        assert result.status in {ResultStatus.COMPLETED, ResultStatus.PAUSED}
    for actor_id in ("investigator_guard_dog_a", "investigator_guard_dog_b"):
        dog = game._state.creatures[actor_id]
        dog.hp = 0
        dog.dead = True
    game._state.in_progress = False
    game._state.winner_team = "blue"
    for actor in game._state.creatures.values():
        actor.actions_remaining = 0
        actor.strikes_this_turn = 0
        actor.diagonals_this_turn = 0
    return game


def test_pursue_lead_advances_one_minute_and_saves_applicable_bonus(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    setup = replace(FORENSIC_INVESTIGATOR_VS_TWO_DOGS, investigations=(INVESTIGATOR_CLUE_ROOM,))
    monkeypatch.setattr(content, "_STAGED_SETUPS", content._STAGED_SETUPS | {setup.setup_id: setup})
    game = _finished_game(monkeypatch)
    game._state.setup_id = setup.setup_id
    before = game.inspect().world_time_seconds

    pursued = game.pursue_lead("forensic_investigator", "guard_dog_case", "bloodied_collar")

    assert pursued.status is ResultStatus.COMPLETED
    assert game.inspect().world_time_seconds - before == 60
    actor = game._state.creatures["forensic_investigator"]
    assert actor.investigator_active_cases == {"guard_dog_case"}
    assert actor.investigator_lead_cooldown_until == before + 60 + 600
    assert actor.investigator_awareness == {"investigator_guard_dog_a"}

    path = tmp_path / "lead.json"
    game.save(path)
    restored = Encounter.load(path)
    assert restored._state.creatures["forensic_investigator"].investigator_active_cases == {"guard_dog_case"}
    assert restored.inspect().world_time_seconds == before + 60


def test_authored_lead_expectations_are_explicit() -> None:
    assert INVESTIGATOR_CLUE_ROOM.case_id == "guard_dog_case"
    assert INVESTIGATOR_CLUE_ROOM.clues[0].clue_key == "bloodied_collar"
    assert INVESTIGATOR_CLUE_ROOM.larger_mystery_fact
    assert INVESTIGATOR_CLUE_ROOM.relevant_checks
    assert INVESTIGATOR_CLUE_ROOM.known_helper_actor_ids == ("investigator_guard_dog_a",)


@pytest.mark.parametrize(("clue_option", "expected_modifier"), (("use", 7), ("decline", 6)))
def test_clue_in_pauses_ally_check_and_save_load_preserves_typed_reaction(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, clue_option: str, expected_modifier: int
) -> None:
    setup = replace(FORENSIC_INVESTIGATOR_VS_TWO_DOGS, setup_id="investigator_lead_followup")
    monkeypatch.setattr(content, "_STAGED_SETUPS", content._STAGED_SETUPS | {setup.setup_id: setup})
    game = Encounter.start(setup, rolls=(20, 1, 2, 11, 14))
    while (choice := game.inspect().choice) is not None:
        option_id = "keep" if any(option.option_id == "keep" for option in choice.options) else choice.options[0].option_id
        result = game.choose(choice.choice_id, option_id, choice.owner_actor_id)
        assert result.status in {ResultStatus.COMPLETED, ResultStatus.PAUSED}
    investigator = game._state.creatures["forensic_investigator"]
    investigator.investigator_active_cases = {"guard_dog_case"}
    # Clue In follows the authored relevant-check binding.  Free Devise's
    # separate target awareness gate does not apply to the ally recipient.
    investigator.investigator_awareness = set()
    investigator.reaction_available = True
    game._state.active_index = game._state.initiative_order.index("investigator_guard_dog_a")
    for actor in game._state.creatures.values():
        actor.actions_remaining = 0
        actor.strikes_this_turn = 0
        actor.diagonals_this_turn = 0
    game._state.creatures["investigator_guard_dog_a"].actions_remaining = 3

    started = game.execute(InvestigationCheck("guard_dog_handler_tracks", target_id="investigator_guard_dog_a"))

    assert started.status is ResultStatus.PAUSED
    assert started.inspection.choice is not None
    assert started.inspection.choice.kind == "reaction"
    assert started.inspection.choice.owner_actor_id == "forensic_investigator"
    pending_path = tmp_path / "clue-in.json"
    game.save(pending_path)
    restored = Encounter.load(pending_path)
    choice = restored.inspect().choice
    assert choice is not None
    used = restored.choose(choice.choice_id, clue_option, choice.owner_actor_id)

    assert used.status is ResultStatus.COMPLETED
    check_event = next(event for event in used.events if event.kind == "investigation_check")
    assert check_event.check is not None
    assert check_event.check.modifier == expected_modifier
    investigator = restored._state.creatures["forensic_investigator"]
    assert investigator.reaction_available is (clue_option == "decline")
    assert investigator.investigator_clue_in_cooldown_until == (600 if clue_option == "use" else 0)


def test_free_devise_requires_authored_awareness_and_preserves_zero_action_cost(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    setup = FORENSIC_INVESTIGATOR_VS_TWO_DOGS
    monkeypatch.setattr(content, "_STAGED_SETUPS", content._STAGED_SETUPS | {setup.setup_id: setup})
    game = _finished_game(monkeypatch)
    for actor_id in ("investigator_guard_dog_a", "investigator_guard_dog_b"):
        dog = game._state.creatures[actor_id]
        dog.hp = 8
        dog.dead = False
    game._state.in_progress = True
    game._state.winner_team = None
    investigator = game._state.creatures["forensic_investigator"]
    investigator.investigator_active_cases = {"guard_dog_case"}
    investigator.investigator_awareness = {"investigator_guard_dog_a"}
    game._state.active_index = game._state.initiative_order.index("forensic_investigator")
    for actor in game._state.creatures.values():
        actor.actions_remaining = 0
        actor.strikes_this_turn = 0
        actor.diagonals_this_turn = 0
    investigator.actions_remaining = 3
    before = investigator.actions_remaining

    result = game.execute(DeviseStratagem("investigator_guard_dog_a", mode=ATTACK_STRATAGEM, free_action=True))

    assert result.status is ResultStatus.COMPLETED
    updated = game._state.creatures["forensic_investigator"]
    assert updated.actions_remaining == before
    assert updated.investigator_stratagem is not None


def test_free_known_weaknesses_save_load_keeps_free_intent_and_draws_once(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    setup = FORENSIC_INVESTIGATOR_VS_TWO_DOGS
    monkeypatch.setattr(content, "_STAGED_SETUPS", content._STAGED_SETUPS | {setup.setup_id: setup})
    game = _finished_game(monkeypatch, rolls=(20, 1, 2, 11, 14, 20))
    for actor_id in ("investigator_guard_dog_a", "investigator_guard_dog_b"):
        dog = game._state.creatures[actor_id]
        dog.hp = 8
        dog.dead = False
    game._state.in_progress = True
    game._state.winner_team = None
    investigator_id = "forensic_investigator"
    investigator = game._state.creatures[investigator_id]
    investigator.investigator_active_cases = {"guard_dog_case"}
    investigator.investigator_awareness = {"investigator_guard_dog_a"}
    game._state.active_index = game._state.initiative_order.index(investigator_id)
    for actor in game._state.creatures.values():
        actor.actions_remaining = 0
        actor.strikes_this_turn = 0
        actor.diagonals_this_turn = 0
    investigator.actions_remaining = 3
    before_dice = game._dice.to_data()
    opened = game.execute(DeviseStratagem("investigator_guard_dog_a", mode=ATTACK_STRATAGEM, free_action=True, known_weaknesses=True))

    assert opened.status is ResultStatus.PAUSED
    pending_path = tmp_path / "free-known.json"
    game.save(pending_path)
    restored = Encounter.load(pending_path)
    pending = restored._state.pending_choice
    assert pending is not None and pending.continuation is not None
    assert pending.continuation.mode == "free_devise"
    kept = restored.choose(pending.choice_id, "keep", pending.owner_actor_id)

    assert kept.status is ResultStatus.COMPLETED
    updated = restored._state.creatures[investigator_id]
    assert updated.actions_remaining == 3
    assert updated.investigator_stratagem is not None
    assert updated.investigator_knowledge_attempts["guard_dog"] == 1
    assert restored._dice.to_data() != before_dice


def test_investigation_check_applies_one_typed_lead_bonus_to_owner(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    setup = FORENSIC_INVESTIGATOR_VS_TWO_DOGS
    monkeypatch.setattr(content, "_STAGED_SETUPS", content._STAGED_SETUPS | {setup.setup_id: setup})
    game = _finished_game(monkeypatch, rolls=(20, 1, 2, 11, 14))
    for actor_id in ("investigator_guard_dog_a", "investigator_guard_dog_b"):
        dog = game._state.creatures[actor_id]
        dog.hp = 8
        dog.dead = False
    game._state.in_progress = True
    game._state.winner_team = None
    investigator_id = "forensic_investigator"
    investigator = game._state.creatures[investigator_id]
    investigator.investigator_active_cases = {"guard_dog_case"}
    investigator.investigator_awareness = {"investigator_guard_dog_a"}
    game._state.active_index = game._state.initiative_order.index(investigator_id)
    for actor in game._state.creatures.values():
        actor.actions_remaining = 0
        actor.strikes_this_turn = 0
        actor.diagonals_this_turn = 0
    investigator.actions_remaining = 3

    result = game.execute(InvestigationCheck("guard_dog_handler_marks", target_id="investigator_guard_dog_a"))

    assert result.status is ResultStatus.COMPLETED
    check_event = next(event for event in result.events if event.kind == "investigation_check")
    assert check_event.check is not None
    assert check_event.check.modifier == 8
    assert any(item == ("circumstance", "Pursue a Lead") for item in (
        (modifier.modifier_type, modifier.source) for modifier in check_event.check.modifier_breakdown
    ))


def test_inconsequential_clue_has_no_cooldown_and_invalid_pursuit_is_atomic(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    setup = FORENSIC_INVESTIGATOR_VS_TWO_DOGS
    monkeypatch.setattr(content, "_STAGED_SETUPS", content._STAGED_SETUPS | {setup.setup_id: setup})
    game = _finished_game(monkeypatch)
    before = game.inspect()
    invalid = game.pursue_lead("forensic_investigator", "unknown_case", "bloodied_collar")
    assert invalid.status is ResultStatus.REJECTED
    assert game.inspect() == before

    declined_game = _finished_game(monkeypatch)
    declined_before = declined_game.inspect().world_time_seconds
    declined = declined_game.pursue_lead(
        "forensic_investigator", "guard_dog_case", "bloodied_collar", open_investigation=False
    )
    assert declined.status is ResultStatus.COMPLETED
    declined_actor = declined_game._state.creatures["forensic_investigator"]
    assert declined_actor.investigator_active_cases == set()
    assert declined_actor.investigator_lead_cooldown_until == declined_before + 660
    declined_snapshot = declined_game.inspect()
    blocked = declined_game.pursue_lead("forensic_investigator", "guard_dog_case", "bloodied_collar")
    assert blocked.status is ResultStatus.REJECTED
    assert declined_game.inspect() == declined_snapshot

    confirmed = game.pursue_lead("forensic_investigator", "guard_dog_case", "bloodied_collar")
    assert confirmed.status is ResultStatus.COMPLETED
    actor = game._state.creatures["forensic_investigator"]
    cooldown = actor.investigator_lead_cooldown_until
    inconsequential = game.pursue_lead(
        "forensic_investigator", "guard_dog_case", "loose_thread", open_investigation=False
    )

    assert inconsequential.status is ResultStatus.COMPLETED
    assert game.inspect().world_time_seconds == cooldown - 600 + 60
    assert game._state.creatures["forensic_investigator"].investigator_lead_cooldown_until == cooldown


def test_two_active_cases_need_explicit_replacement_and_daily_prepare_reopens_abandoned(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    cases = tuple(
        replace(INVESTIGATOR_CLUE_ROOM, case_id=case_id)
        for case_id in ("guard_dog_case", "second_case", "third_case")
    )
    setup = replace(
        FORENSIC_INVESTIGATOR_VS_TWO_DOGS,
        setup_id="investigator_lead_case_limits",
        investigations=cases,
    )
    monkeypatch.setattr(content, "_STAGED_SETUPS", content._STAGED_SETUPS | {setup.setup_id: setup})
    game = _finished_game(monkeypatch)
    game._state.setup_id = setup.setup_id

    assert game.pursue_lead("forensic_investigator", "guard_dog_case", "bloodied_collar").status is ResultStatus.COMPLETED
    game._state.creatures["forensic_investigator"].investigator_lead_cooldown_until = game._state.world_time_seconds
    assert game.pursue_lead("forensic_investigator", "second_case", "bloodied_collar").status is ResultStatus.COMPLETED
    game._state.creatures["forensic_investigator"].investigator_lead_cooldown_until = game._state.world_time_seconds

    before = game.inspect()
    third_without_replacement = game.pursue_lead("forensic_investigator", "third_case", "bloodied_collar")
    assert third_without_replacement.status is ResultStatus.REJECTED
    assert game.inspect() == before
    replaced = game.pursue_lead(
        "forensic_investigator", "third_case", "bloodied_collar", replace_case_id="guard_dog_case"
    )
    assert replaced.status is ResultStatus.COMPLETED
    actor = game._state.creatures["forensic_investigator"]
    assert actor.investigator_active_cases == {"second_case", "third_case"}
    assert actor.investigator_abandoned_cases == {"guard_dog_case"}

    game._state.creatures["forensic_investigator"].investigator_lead_cooldown_until = game._state.world_time_seconds
    before_prepare = game.inspect().world_time_seconds
    assert game.record_rested(("forensic_investigator",), day_number=2, elapsed_seconds=1).status is ResultStatus.COMPLETED
    assert game.daily_prepare(("forensic_investigator",)).status is ResultStatus.COMPLETED
    assert game.inspect().world_time_seconds == before_prepare + 3601
    assert not game._state.creatures["forensic_investigator"].investigator_abandoned_cases
    reopened = game.pursue_lead(
        "forensic_investigator", "guard_dog_case", "bloodied_collar", replace_case_id="second_case"
    )
    assert reopened.status is ResultStatus.COMPLETED
    solved = game.mark_investigation_solved("forensic_investigator", "guard_dog_case")
    assert solved.status is ResultStatus.COMPLETED
    actor = game._state.creatures["forensic_investigator"]
    assert actor.investigator_solved_cases == {"guard_dog_case"}
    assert actor.investigator_active_cases == {"guard_dog_case", "third_case"}
    closed = game.close_investigation("forensic_investigator", "guard_dog_case")
    assert closed.status is ResultStatus.COMPLETED
    assert game._state.creatures["forensic_investigator"].investigator_solved_cases == set()
    assert game._state.creatures["forensic_investigator"].investigator_active_cases == {"third_case"}


def test_terminal_finished_menu_runs_authored_pursue_lead(monkeypatch: pytest.MonkeyPatch) -> None:
    finished = _finished_game(monkeypatch)
    entries = build_action_menu(
        finished.options().available_actions,
        include_refocus=True,
        include_downtime=True,
        include_examination=True,
        include_lead=True,
    )
    lead_index = next(index for index, (action_id, _label) in enumerate(entries, 1) if action_id == "pursue_lead")
    quit_index = next(index for index, (action_id, _label) in enumerate(entries, 1) if action_id == "quit")
    monkeypatch.setattr(Encounter, "start", classmethod(lambda _cls, *args, **kwargs: finished))

    inputs = iter((str(lead_index), "1", "1", str(quit_index)))
    transcript = BoundedTranscript(max_lines=500, max_chars=100_000)
    bounded_input = BoundedInput(lambda: next(inputs), max_calls=20)
    status = run_terminal(
        setup=FORENSIC_INVESTIGATOR_VS_TWO_DOGS,
        input_fn=bounded_input,
        output_fn=transcript.append,
    )

    rendered = "\n".join(transcript)
    assert status == 0
    assert "Pursue a Lead" in rendered
    assert "The Bloodied Collar" in rendered
    assert "Larger mystery:" in rendered
    assert "Goodbye." in rendered
    assert bounded_input.calls == 4


def test_active_lead_carries_through_saved_next_encounter(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    setup = FORENSIC_INVESTIGATOR_VS_TWO_DOGS
    monkeypatch.setattr(content, "_STAGED_SETUPS", content._STAGED_SETUPS | {setup.setup_id: setup})
    game = _finished_game(monkeypatch, rolls=(20, 1, 2, 11, 20, 1, 2))
    pursued = game.pursue_lead("forensic_investigator", "guard_dog_case", "bloodied_collar")
    assert pursued.status is ResultStatus.COMPLETED

    save_path = tmp_path / "lead-next-scene.json"
    game.save(save_path)
    loaded = Encounter.load(save_path)
    next_setup = replace(
        setup,
        setup_id="investigator_lead_next_scene",
        name="Forensic Investigator lead next scene",
        placements=tuple(
            replace(
                placement,
                actor_id={
                    "investigator_guard_dog_a": "next_lead_guard_dog_a",
                    "investigator_guard_dog_b": "next_lead_guard_dog_b",
                }.get(placement.actor_id, placement.actor_id),
            )
            for placement in setup.placements
        ),
    )
    monkeypatch.setattr(content, "_STAGED_SETUPS", content._STAGED_SETUPS | {next_setup.setup_id: next_setup})

    transitioned = loaded.next_encounter(next_setup)

    assert transitioned.status in {ResultStatus.COMPLETED, ResultStatus.PAUSED}
    actor = loaded._state.creatures["forensic_investigator"]
    assert actor.investigator_active_cases == {"guard_dog_case"}
    assert actor.investigator_lead_cooldown_until > loaded.inspect().world_time_seconds
