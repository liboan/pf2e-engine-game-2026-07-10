"""Independent public-play review of Forensic Acumen examination.

Rules references:
- Medicine forensic examination: https://2e.aonprd.com/Skills.aspx?ID=42
- Forensic Acumen: https://2e.aonprd.com/Feats.aspx?ID=6483
"""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest

import pf2e.content as content
from pf2e.encounter import Encounter
from pf2e.investigator import BattleMedicine, RecallKnowledge
from pf2e.investigator_content import (
    FORENSIC_CREATURE_TYPE_KNOWLEDGE,
    FORENSIC_HEALING_DOG_EXAMINATION,
    FORENSIC_INVESTIGATOR_HEALING_SETUP,
)
from pf2e.model import EndTurn, Position, ResultStatus, Strike, Stride


def _actor(game: Encounter, actor_id: str):
    return next(actor for actor in game.inspect().actors if actor.actor_id == actor_id)


def _choose(game: Encounter, option_id: str):
    choice = game.inspect().choice
    assert choice is not None
    return game.choose(choice.choice_id, option_id, choice.owner_actor_id)


def _settle_initiative(game: Encounter) -> None:
    for _ in range(8):
        choice = game.inspect().choice
        if choice is None:
            return
        assert choice.kind in {"initiative_hero_reroll", "initiative_tie"}
        option_id = (
            "keep"
            if any(option.option_id == "keep" for option in choice.options)
            else choice.options[0].option_id
        )
        assert game.choose(choice.choice_id, option_id, choice.owner_actor_id).status in {
            ResultStatus.PAUSED,
            ResultStatus.COMPLETED,
        }
    raise AssertionError("initiative did not settle within eight choices")


def _finish_healthy_fight(
    monkeypatch: pytest.MonkeyPatch,
    setup,
    rolls: tuple[int, ...],
) -> Encounter:
    monkeypatch.setattr(
        content,
        "_STAGED_SETUPS",
        content._STAGED_SETUPS | {setup.setup_id: setup},
    )
    game = Encounter.start(setup, rolls=rolls)
    assert all(actor.hp == actor.max_hp for actor in game.inspect().actors)
    _settle_initiative(game)
    assert game.inspect().turn_actor_id == "healing_dog"
    assert game.execute(Stride((Position(3, 2),))).status is ResultStatus.COMPLETED
    assert game.execute(Strike("healing_ally", attack_id="jaws")).status is ResultStatus.COMPLETED
    assert _actor(game, "healing_ally").hp == 16
    assert game.execute(EndTurn()).status is ResultStatus.COMPLETED
    assert game.execute(EndTurn()).status is ResultStatus.COMPLETED
    assert game.inspect().turn_actor_id == "forensic_investigator"

    medicine = game.execute(BattleMedicine("healing_ally"))
    assert medicine.status is ResultStatus.PAUSED
    assert _choose(game, "keep").status is ResultStatus.COMPLETED
    assert _actor(game, "healing_ally").hp == 21
    assert game.execute(Stride((Position(2, 2),))).status is ResultStatus.COMPLETED
    investigator_strike = game.execute(Strike("healing_dog", attack_id="shortsword"))
    if investigator_strike.status is ResultStatus.PAUSED:
        investigator_strike = _choose(game, "keep")
    assert investigator_strike.status is ResultStatus.COMPLETED
    assert _actor(game, "healing_dog").hp == 4
    assert game.execute(EndTurn()).status is ResultStatus.COMPLETED
    ally_strike = game.execute(Strike("healing_dog", attack_id="longsword"))
    if ally_strike.status is ResultStatus.PAUSED:
        ally_strike = _choose(game, "keep")
    assert ally_strike.status is ResultStatus.COMPLETED
    assert not game.inspect().in_progress
    assert game.inspect().winner_team == "blue"
    assert _actor(game, "healing_dog").defeated
    return game


def test_healthy_fight_saved_creature_type_follow_up_carries_subject_history_to_next_scene(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    # Healthy fight rolls, examination/follow-up, then next-scene initiatives
    # and the second creature-type question.
    rolls = (
        1, 2, 20, 12, 4, 12, 3, 4, 10, 4, 10, 4,
        20, 14,
        20, 1, 2, 13,
    )
    game = _finish_healthy_fight(
        monkeypatch,
        FORENSIC_INVESTIGATOR_HEALING_SETUP,
        rolls,
    )
    before_time = game.inspect().world_time_seconds
    examination = game.forensic_examine(
        "forensic_investigator", body_key="forensic_guard_dog_body"
    )
    assert examination.status is ResultStatus.PAUSED
    assert game.inspect().world_time_seconds - before_time == 300
    assert _choose(game, "keep").status is ResultStatus.PAUSED
    offer = game.inspect().choice
    assert offer is not None
    assert offer.kind == "family_action"
    assert "follow_up:forensic_creature_type" in {
        option.option_id for option in offer.options
    }

    offer_path = tmp_path / "review-forensic-creature-follow-up-offer.json"
    game.save(offer_path)
    game = Encounter.load(offer_path)
    started = _choose(game, "follow_up:forensic_creature_type")
    assert started.status is ResultStatus.PAUSED
    pending = game._state.pending_choice
    assert pending is not None
    assert pending.procedure_id == "investigator:forensic_examination:follow_up:hero_point"
    assert pending.saved_check is not None
    assert any(
        modifier.source == "Forensic Acumen"
        and modifier.amount == 2
        and modifier.modifier_type == "circumstance"
        for modifier in pending.saved_check.modifiers
    )

    check_path = tmp_path / "review-forensic-creature-follow-up-check.json"
    game.save(check_path)
    game = Encounter.load(check_path)
    resolved = _choose(game, "keep")
    event = next(event for event in resolved.events if event.kind == "recall_knowledge")
    assert event.target_id is None
    assert event.check is not None
    assert (event.check.die, event.check.modifier, event.check.total, event.check.dc) == (
        14,
        3,
        17,
        16,
    )
    assert game.inspect().world_time_seconds - before_time == 300
    investigator = game._state.creatures["forensic_investigator"]
    assert investigator.investigator_knowledge_attempts == {
        "forensic_guard_dog_body": 1,
        "forensic_creature_type": 1,
    }

    next_setup = replace(
        FORENSIC_INVESTIGATOR_HEALING_SETUP,
        setup_id="review_forensic_creature_type_next_scene",
        name="Review Forensic creature-type next scene",
        knowledge=(FORENSIC_CREATURE_TYPE_KNOWLEDGE,),
        examinations=(),
        placements=tuple(
            replace(placement, actor_id="later_healing_dog")
            if placement.actor_id == "healing_dog"
            else placement
            for placement in FORENSIC_INVESTIGATOR_HEALING_SETUP.placements
        ),
    )
    monkeypatch.setattr(
        content,
        "_STAGED_SETUPS",
        content._STAGED_SETUPS | {next_setup.setup_id: next_setup},
    )
    assert game.next_encounter(next_setup).status in {
        ResultStatus.PAUSED,
        ResultStatus.COMPLETED,
    }
    _settle_initiative(game)
    repeated = game.execute(
        RecallKnowledge(
            "forensic_creature_type",
            FORENSIC_CREATURE_TYPE_KNOWLEDGE.question,
            "nature",
        )
    )
    assert repeated.status is ResultStatus.PAUSED
    repeated = _choose(game, "keep")
    check = next(event.check for event in repeated.events if event.kind == "recall_knowledge")
    assert check is not None and check.dc == 18
    investigator = game._state.creatures["forensic_investigator"]
    assert investigator.investigator_knowledge_attempts["forensic_creature_type"] == 2
    assert investigator.investigator_knowledge_exhausted == {"forensic_creature_type"}


def test_authored_nonactor_body_saved_decline_and_repeat_rejection_are_atomic(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    abstract_body = replace(
        FORENSIC_HEALING_DOG_EXAMINATION,
        body_key="review_unattached_body",
        body_label="Unattached Examined Body",
        body_actor_id=None,
    )
    setup = replace(
        FORENSIC_INVESTIGATOR_HEALING_SETUP,
        setup_id="review_forensic_unattached_body",
        name="Review authored non-actor body",
        examinations=(abstract_body,),
    )
    rolls = (1, 2, 20, 12, 4, 12, 3, 4, 10, 4, 10, 4, 11)
    game = _finish_healthy_fight(monkeypatch, setup, rolls)
    before_time = game.inspect().world_time_seconds
    started = game.examine_body("forensic_investigator", "review_unattached_body")
    assert started.status is ResultStatus.PAUSED
    started_event = next(
        event for event in started.events if event.kind == "forensic_examination_started"
    )
    assert started_event.target_id is None
    assert _choose(game, "keep").status is ResultStatus.PAUSED
    assert game.inspect().world_time_seconds - before_time == 300

    offer_path = tmp_path / "review-forensic-unattached-offer.json"
    game.save(offer_path)
    game = Encounter.load(offer_path)
    choice = game.inspect().choice
    assert choice is not None
    before = game.inspect()
    dice_before = game._dice.to_data()
    invalid = game.choose(choice.choice_id, "forged", choice.owner_actor_id)
    assert invalid.status is ResultStatus.REJECTED
    assert game.inspect() == before
    assert game._dice.to_data() == dice_before

    declined = _choose(game, "decline")
    assert declined.status is ResultStatus.COMPLETED
    assert any(
        event.kind == "forensic_examination_follow_up_declined"
        for event in declined.events
    )
    investigator = game._state.creatures["forensic_investigator"]
    assert investigator.investigator_knowledge_attempts == {"review_unattached_body": 1}
    assert not {
        "forensic_injury_cause",
        "forensic_creature_type",
    } & set(investigator.investigator_knowledge_attempts)

    before = game.inspect()
    dice_before = game._dice.to_data()
    repeated = game.forensic_examine("forensic_investigator", "review_unattached_body")
    assert repeated.status is ResultStatus.REJECTED
    assert game.inspect() == before
    assert game._dice.to_data() == dice_before
    assert game.inspect().world_time_seconds - before_time == 300
