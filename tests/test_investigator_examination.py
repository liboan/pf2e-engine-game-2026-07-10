"""Public Forensic Acumen body examination coverage.

Rules references checked 2026-09-16:

* https://2e.aonprd.com/Skills.aspx?ID=42
* https://2e.aonprd.com/Feats.aspx?ID=6483
"""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest

import pf2e.content as content
from pf2e.encounter import Encounter
from pf2e.investigator import ATTACK_STRATAGEM, DeviseStratagem, RecallKnowledge
from pf2e.investigator_content import (
    FORENSIC_INJURY_CAUSE_KNOWLEDGE,
    FORENSIC_INVESTIGATOR_VS_TWO_DOGS,
)
from pf2e.model import EndTurn, ResultStatus, Strike
from pf2e.terminal import run_terminal
from terminal_test_helpers import BoundedInput, BoundedTranscript


def _settle_initiative(game: Encounter) -> None:
    for _ in range(8):
        choice = game.inspect().choice
        if choice is None:
            return
        option_id = "keep" if any(option.option_id == "keep" for option in choice.options) else choice.options[0].option_id
        result = game.choose(choice.choice_id, option_id, choice.owner_actor_id)
        assert result.status in {ResultStatus.COMPLETED, ResultStatus.PAUSED}
    raise AssertionError("initiative did not settle")


def _finished_game(monkeypatch: pytest.MonkeyPatch, rolls: tuple[int, ...] = (20, 1, 2, 11)) -> Encounter:
    setup = FORENSIC_INVESTIGATOR_VS_TWO_DOGS
    monkeypatch.setattr(content, "_STAGED_SETUPS", content._STAGED_SETUPS | {setup.setup_id: setup})
    game = Encounter.start(setup, rolls=rolls)
    _settle_initiative(game)
    dog = game._state.creatures["investigator_guard_dog_a"]
    dog.hp = 0
    dog.dead = True
    game._state.creatures["investigator_guard_dog_b"].hp = 0
    game._state.creatures["investigator_guard_dog_b"].dead = True
    game._state.in_progress = False
    game._state.winner_team = "blue"
    for actor in game._state.creatures.values():
        actor.actions_remaining = 0
        actor.strikes_this_turn = 0
        actor.diagonals_this_turn = 0
    assert dog.defeated
    return game


def _choose(game: Encounter, option_id: str):
    choice = game.inspect().choice
    assert choice is not None
    result = game.choose(choice.choice_id, option_id, choice.owner_actor_id)
    assert result.status in {ResultStatus.COMPLETED, ResultStatus.PAUSED}
    return result


def test_public_body_examination_saves_hero_decision_and_charges_time_once(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    game = _finished_game(monkeypatch)
    before = game.inspect().world_time_seconds

    started = game.forensic_examine(
        "forensic_investigator", body_key="forensic_guard_dog_body"
    )
    assert started.status is ResultStatus.PAUSED
    assert started.inspection.choice is not None
    assert game._state.pending_choice is not None
    assert game._state.pending_choice.procedure_id == "investigator:forensic_examination:medicine_hero_point"
    assert game.inspect().world_time_seconds - before == 300
    assert game._state.creatures["forensic_investigator"].investigator_knowledge_attempts == {}

    pending_path = tmp_path / "forensic-examination-pending.json"
    game.save(pending_path)
    game = Encounter.load(pending_path)
    choice = game.inspect().choice
    assert choice is not None
    resolved = game.choose(choice.choice_id, "keep", choice.owner_actor_id)
    assert resolved.status is ResultStatus.PAUSED
    examination = next(event for event in resolved.events if event.kind == "forensic_examination")
    assert examination.check is not None
    assert (examination.check.die, examination.check.total, examination.check.dc) == (11, 15, 15)
    assert game.inspect().world_time_seconds - before == 300
    actor = game._state.creatures["forensic_investigator"]
    assert actor.investigator_knowledge_attempts == {"forensic_guard_dog_body": 1}
    assert "forensic_guard_dog_body" in actor.investigator_examinations_completed
    assert game.inspect().choice is not None
    assert game._state.pending_choice is not None
    assert game._state.pending_choice.procedure_id == "investigator:forensic_examination:follow_up"


def test_terminal_body_examination_save_load_and_decline_are_bounded(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    finished = _finished_game(monkeypatch)
    monkeypatch.setattr(Encounter, "start", classmethod(lambda _cls, *args, **kwargs: finished))
    inputs = iter((
        "9", "1",       # Forensic Acumen Examination, Guard Dog Body
        "3", "", "4", "",  # save and load the Medicine Hero decision
        "2", "2",       # resolve choice, keep the check
        "2", "1",       # resolve follow-up choice, decline
        "6",            # quit from finished activity menu
    ))
    transcript = BoundedTranscript(max_lines=500, max_chars=100_000)
    bounded_input = BoundedInput(lambda: next(inputs), max_calls=40)
    status = run_terminal(
        setup=FORENSIC_INVESTIGATOR_VS_TWO_DOGS,
        rolls=(20, 1, 2, 11),
        save_path=tmp_path / "terminal-examination.json",
        input_fn=bounded_input,
        output_fn=transcript.append,
    )
    rendered = "\n".join(transcript)
    assert status == 0
    assert bounded_input.calls == 11
    assert "Forensic Acumen Examination" in rendered
    assert "Saved encounter to" in rendered
    assert "Loaded encounter from" in rendered
    assert "Guard Dog Body" in rendered
    assert "forensic_guard_dog_body" in rendered
    assert "declines immediate Recall Knowledge" in rendered
    assert "Goodbye." in rendered


def test_successful_examination_offers_saved_relevant_follow_up_with_typed_bonus(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    game = _finished_game(monkeypatch, rolls=(20, 1, 2, 20, 12))
    actor = game._state.creatures["forensic_investigator"]
    started = game.forensic_examine(actor.actor_id, "forensic_guard_dog_body")
    assert started.status is ResultStatus.PAUSED
    _choose(game, "keep")
    follow_up = game.inspect().choice
    assert follow_up is not None
    assert {option.option_id for option in follow_up.options} >= {
        "decline",
        "follow_up:forensic_injury_cause",
        "follow_up:forensic_creature_type",
    }
    selected = _choose(game, "follow_up:forensic_injury_cause")
    assert selected.status is ResultStatus.PAUSED
    assert game._state.pending_choice is not None
    assert game._state.pending_choice.procedure_id == "investigator:forensic_examination:follow_up:hero_point"
    saved = game._state.pending_choice.saved_check
    assert saved is not None
    assert any(
        item.amount == 2
        and item.modifier_type == "circumstance"
        and item.source == "Forensic Acumen"
        for item in saved.modifiers
    )
    path = tmp_path / "forensic-follow-up.json"
    game.save(path)
    game = Encounter.load(path)
    resolved = _choose(game, "keep")
    event = next(item for item in resolved.events if item.kind == "recall_knowledge")
    assert event.target_id is None
    assert event.check is not None
    assert (event.check.die, event.check.total, event.check.dc) == (12, 21, 16)
    assert "The wound pattern came from a hooked blade" in event.text
    actor = game._state.creatures["forensic_investigator"]
    assert actor.investigator_knowledge_attempts == {
        "forensic_guard_dog_body": 1,
        "forensic_injury_cause": 1,
    }
    assert actor.hero_points == 1
    assert game.inspect().world_time_seconds == 300


@pytest.mark.parametrize(
    ("die", "degree"),
    ((5, "FAILURE"), (1, "CRITICAL_FAILURE")),
)
def test_failed_examination_returns_no_information_and_exhausts_subject(
    monkeypatch: pytest.MonkeyPatch, die: int, degree: str
) -> None:
    game = _finished_game(monkeypatch, rolls=(20, 1, 2, die))
    game._state.creatures["forensic_investigator"].hero_points = 0
    result = game.forensic_examine("forensic_investigator", "forensic_guard_dog_body")
    assert result.status is ResultStatus.COMPLETED
    event = next(item for item in result.events if item.kind == "forensic_examination")
    assert event.check is not None and event.check.degree.name == degree
    assert any(item.kind == "forensic_examination_no_information" for item in result.events)
    actor = game._state.creatures["forensic_investigator"]
    assert actor.investigator_knowledge_attempts == {"forensic_guard_dog_body": 1}
    assert actor.investigator_knowledge_exhausted == {"forensic_guard_dog_body"}
    assert game.inspect().world_time_seconds == 300
    assert game.inspect().choice is None


def test_examination_hero_reroll_finalizes_replacement_before_history_and_clock(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    game = _finished_game(monkeypatch, rolls=(20, 1, 2, 1, 20))
    result = game.forensic_examine("forensic_investigator", "forensic_guard_dog_body")
    assert result.status is ResultStatus.PAUSED
    assert game.inspect().world_time_seconds == 300
    rerolled = _choose(game, "reroll")
    event = next(item for item in rerolled.events if item.kind == "forensic_examination")
    assert event.check is not None
    assert (event.check.die, event.check.degree.name) == (20, "CRITICAL_SUCCESS")
    actor = game._state.creatures["forensic_investigator"]
    assert actor.hero_points == 0
    assert actor.investigator_knowledge_attempts == {"forensic_guard_dog_body": 1}
    assert game.inspect().world_time_seconds == 300
    assert game._state.pending_choice is not None
    assert game._state.pending_choice.procedure_id == "investigator:forensic_examination:follow_up"


def test_examination_requires_accessible_nonliving_body_and_is_atomic(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    game = _finished_game(monkeypatch, rolls=(20, 1, 2, 11))
    dog = game._state.creatures["investigator_guard_dog_a"]
    dog.hp = 10
    dog.dead = False
    before_clock = game.inspect().world_time_seconds
    before_dice = game._dice.to_data()
    rejected = game.forensic_examine("forensic_investigator", "forensic_guard_dog_body")
    assert rejected.status is ResultStatus.REJECTED
    assert "accessible" in rejected.message
    assert game.inspect().world_time_seconds == before_clock
    assert game._dice.to_data() == before_dice

    unsupported = game.forensic_examine("investigator_guard_dog_b", "forensic_guard_dog_body")
    assert unsupported.status is ResultStatus.REJECTED
    assert game.inspect().world_time_seconds == before_clock
    assert game._dice.to_data() == before_dice


def test_examination_subject_history_carries_through_saved_next_encounter(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    game = _finished_game(monkeypatch, rolls=(20, 1, 2, 20, 20, 20, 1, 2, 20))
    assert game.forensic_examine("forensic_investigator", "forensic_guard_dog_body").status is ResultStatus.PAUSED
    _choose(game, "keep")
    _choose(game, "follow_up:forensic_injury_cause")
    _choose(game, "keep")
    path = tmp_path / "forensic-completed.json"
    game.save(path)
    game = Encounter.load(path)

    current = FORENSIC_INVESTIGATOR_VS_TWO_DOGS
    next_setup = replace(
        current,
        setup_id="investigator_forensic_examination_next_scene",
        name="Forensic Investigator examination next scene",
        knowledge=(FORENSIC_INJURY_CAUSE_KNOWLEDGE,),
        examinations=(),
        placements=tuple(
            replace(
                placement,
                actor_id={
                    "investigator_guard_dog_a": "next_guard_dog_a",
                    "investigator_guard_dog_b": "next_guard_dog_b",
                }.get(placement.actor_id, placement.actor_id),
            )
            for placement in current.placements
        ),
    )
    monkeypatch.setattr(
        content,
        "_STAGED_SETUPS",
        content._STAGED_SETUPS | {next_setup.setup_id: next_setup},
    )
    transitioned = game.next_encounter(next_setup)
    assert transitioned.status in {ResultStatus.COMPLETED, ResultStatus.PAUSED}
    _settle_initiative(game)
    actor = game._state.creatures["forensic_investigator"]
    assert actor.investigator_knowledge_attempts == {
        "forensic_guard_dog_body": 1,
        "forensic_injury_cause": 1,
    }
    result = game.execute(
        RecallKnowledge(
            subject_key="forensic_injury_cause",
            question=FORENSIC_INJURY_CAUSE_KNOWLEDGE.question,
            skill="crafting",
        )
    )
    assert result.status is ResultStatus.PAUSED
    resolved = _choose(game, "keep")
    event = next(item for item in resolved.events if item.kind == "recall_knowledge")
    assert event.check is not None and event.check.dc == 18
    actor = game._state.creatures["forensic_investigator"]
    assert actor.investigator_knowledge_attempts == {
        "forensic_guard_dog_body": 1,
        "forensic_injury_cause": 2,
    }
    assert actor.investigator_knowledge_exhausted == {"forensic_injury_cause"}


def test_healthy_fight_then_examination_and_saved_next_scene_have_legitimate_results(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    setup = FORENSIC_INVESTIGATOR_VS_TWO_DOGS
    monkeypatch.setattr(content, "_STAGED_SETUPS", content._STAGED_SETUPS | {setup.setup_id: setup})
    game = Encounter.start(
        setup,
        rolls=(20, 1, 2, 14, 10, 4, 3, 5, 1, 20, 1, 1, 20, 20, 20, 1, 2, 20),
    )
    _settle_initiative(game)
    assert all(actor.hp == actor.max_hp for actor in game.inspect().actors)
    assert game.execute(DeviseStratagem("investigator_guard_dog_a", mode=ATTACK_STRATAGEM)).status is ResultStatus.COMPLETED
    other = game.execute(Strike("investigator_guard_dog_b", attack_id="shortsword"))
    assert other.status is ResultStatus.PAUSED
    _choose(game, "keep")
    selected = game.execute(
        Strike("investigator_guard_dog_a", attack_id="shortsword", use_intelligence=True)
    )
    assert selected.status is ResultStatus.COMPLETED
    assert game.execute(Strike("forensic_investigator", attack_id="jaws")).status is ResultStatus.COMPLETED
    assert game.execute(EndTurn()).status is ResultStatus.COMPLETED
    assert game.execute(DeviseStratagem("investigator_guard_dog_b", mode=ATTACK_STRATAGEM)).status is ResultStatus.COMPLETED
    victory = game.execute(
        Strike("investigator_guard_dog_b", attack_id="shortsword", use_intelligence=True)
    )
    assert victory.status is ResultStatus.COMPLETED
    assert not game.inspect().in_progress and game.inspect().winner_team == "blue"
    assert all(actor.hp == actor.max_hp for actor in game.inspect().actors if actor.actor_id == "forensic_investigator")

    victory_path = tmp_path / "healthy-fight-victory.json"
    game.save(victory_path)
    game = Encounter.load(victory_path)
    examination = game.forensic_examine("forensic_investigator", "forensic_guard_dog_body")
    assert examination.status is ResultStatus.PAUSED
    assert _choose(game, "keep").status is ResultStatus.PAUSED
    assert _choose(game, "follow_up:forensic_injury_cause").status is ResultStatus.PAUSED
    assert _choose(game, "keep").status is ResultStatus.COMPLETED
    assert game._state.creatures["forensic_investigator"].investigator_examinations_completed == {
        "forensic_guard_dog_body"
    }

    examination_path = tmp_path / "healthy-fight-examination.json"
    game.save(examination_path)
    game = Encounter.load(examination_path)
    next_setup = replace(
        setup,
        setup_id="investigator_forensic_healthy_next_scene",
        name="Forensic Investigator healthy next scene",
        knowledge=(FORENSIC_INJURY_CAUSE_KNOWLEDGE,),
        examinations=(),
        placements=tuple(
            replace(
                placement,
                actor_id={
                    "investigator_guard_dog_a": "healthy_next_dog_a",
                    "investigator_guard_dog_b": "healthy_next_dog_b",
                }.get(placement.actor_id, placement.actor_id),
            )
            for placement in setup.placements
        ),
    )
    monkeypatch.setattr(
        content,
        "_STAGED_SETUPS",
        content._STAGED_SETUPS | {next_setup.setup_id: next_setup},
    )
    transitioned = game.next_encounter(next_setup)
    assert transitioned.status in {ResultStatus.PAUSED, ResultStatus.COMPLETED}
    _settle_initiative(game)
    actor = game._state.creatures["forensic_investigator"]
    assert actor.investigator_examinations_completed == {"forensic_guard_dog_body"}
    discovered = game.execute(
        RecallKnowledge(
            subject_key="forensic_injury_cause",
            question=FORENSIC_INJURY_CAUSE_KNOWLEDGE.question,
            skill="crafting",
        )
    )
    assert discovered.status is ResultStatus.PAUSED
    discovered = _choose(game, "keep")
    event = next(item for item in discovered.events if item.kind == "recall_knowledge")
    assert event.check is not None and event.check.degree.name == "CRITICAL_SUCCESS"
