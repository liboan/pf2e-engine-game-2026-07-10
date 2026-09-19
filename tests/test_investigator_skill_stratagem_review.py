"""Independent public review of Investigator Skill Stratagem.

Source expectations checked 2026-09-16:

* https://2e.aonprd.com/Classes.aspx?ID=59
* https://2e.aonprd.com/Actions.aspx?ID=2813

The stored d20 is revealed before the mode decision. Skill Stratagem forbids
Strikes against that creature until the start of the Investigator's next turn.
Before that same deadline, the next target-related Perception or Intelligence-,
Wisdom-, or Charisma-based skill check gets +1 circumstance; an applicable
Pursue a Lead bonus becomes +2 instead.
"""

from dataclasses import replace
from pathlib import Path

import pytest

import pf2e.content as content
from pf2e.encounter import Encounter
from pf2e.investigator import ATTACK_STRATAGEM, DeviseStratagem, InvestigationCheck, RecallKnowledge
from pf2e.investigator_content import INVESTIGATOR_CLUE_ROOM, InvestigationCheckContent
from pf2e.model import Choose, EndTurn, ResultStatus, Strike


INVESTIGATOR = "forensic_investigator"
TARGET = "investigator_guard_dog_a"


def _actor(game: Encounter, actor_id: str):
    return next(actor for actor in game.inspect().actors if actor.actor_id == actor_id)


def _choose(game: Encounter, option_id: str):
    choice = game.inspect().choice
    assert choice is not None
    return game.execute(Choose(choice.choice_id, option_id, choice.owner_actor_id))


def _settle_initiative(game: Encounter) -> None:
    for _ in range(8):
        choice = game.inspect().choice
        if choice is None:
            return
        option_id = "keep" if any(option.option_id == "keep" for option in choice.options) else choice.options[0].option_id
        assert _choose(game, option_id).status in {ResultStatus.PAUSED, ResultStatus.COMPLETED}
    raise AssertionError("initiative did not settle")


def _admit(monkeypatch: pytest.MonkeyPatch, setup) -> None:
    monkeypatch.setattr(content, "_STAGED_SETUPS", content._STAGED_SETUPS | {setup.setup_id: setup})


def test_saved_skill_mode_and_check_complete_healthy_fight_after_exact_start_expiry(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    base = content.get_setup("investigator_forensic_vs_two_guard_dogs")
    setup = replace(
        base,
        setup_id="review_skill_stratagem_healthy_fight",
        name="Review healthy Skill Stratagem fight",
        placements=base.placements[:2],
    )
    _admit(monkeypatch, setup)
    # Initiatives; Skill Devise; Society Recall Knowledge; dog miss; next-round
    # Attack Devise; critical shortsword d6 and Strategic Strike d6.
    game = Encounter.start(setup, rolls=(20, 1, 5, 8, 1, 20, 1, 3))
    _settle_initiative(game)
    assert all(actor.hp == actor.max_hp for actor in game.inspect().actors)

    opened = game.execute(DeviseStratagem(TARGET))
    assert opened.status is ResultStatus.PAUSED
    assert any("preliminary d20 is 5" in event.text for event in opened.events)
    mode_path = tmp_path / "review-skill-mode.json"
    game.save(mode_path)
    game = Encounter.load(mode_path)
    assert _choose(game, "skill").status is ResultStatus.COMPLETED

    knowledge = game.execute(RecallKnowledge("guard_dog", skill="society", target_id=TARGET))
    assert knowledge.status is ResultStatus.PAUSED
    check_path = tmp_path / "review-skill-check.json"
    game.save(check_path)
    game = Encounter.load(check_path)
    knowledge = _choose(game, "keep")
    check = next(event.check for event in knowledge.events if event.kind == "recall_knowledge")
    assert check is not None and (check.die, check.modifier, check.total, check.dc) == (8, 8, 16, 16)
    assert any(
        item.modifier_type == "circumstance" and item.source == "Skill Stratagem" and item.amount == 1
        for item in check.modifier_breakdown
    )
    stored = game._state.creatures[INVESTIGATOR].investigator_stratagem
    assert stored is not None and stored.mode == "skill" and stored.consumed

    before, dice_before = game.inspect(), game._dice.to_data()
    blocked = game.execute(Strike(TARGET, attack_id="shortsword"))
    assert blocked.status is ResultStatus.REJECTED
    assert blocked.inspection == before and game._dice.to_data() == dice_before

    assert game.execute(EndTurn()).status is ResultStatus.COMPLETED
    assert game.inspect().turn_actor_id == TARGET
    assert game.execute(Strike(INVESTIGATOR, attack_id="jaws")).status is ResultStatus.COMPLETED
    assert _actor(game, INVESTIGATOR).hp == _actor(game, INVESTIGATOR).max_hp
    assert game.execute(EndTurn()).status is ResultStatus.COMPLETED
    assert game.inspect().turn_actor_id == INVESTIGATOR
    assert game._state.creatures[INVESTIGATOR].investigator_stratagem is None

    assert game.execute(DeviseStratagem(TARGET, mode=ATTACK_STRATAGEM)).status is ResultStatus.COMPLETED
    victory = game.execute(Strike(TARGET, attack_id="shortsword", use_intelligence=True))
    attack = next(event.check for event in victory.events if event.kind == "strike")
    damage = next(event.damage for event in victory.events if event.kind == "damage")
    assert attack is not None and (attack.die, attack.modifier, attack.total) == (20, 7, 27)
    assert damage is not None and damage.total == 8
    assert [(part.source, part.rolls) for part in damage.components] == [
        ("shortsword", (1,)),
        ("investigator_strategic_strike", (3,)),
    ]
    assert victory.status is ResultStatus.COMPLETED
    assert not victory.inspection.in_progress and victory.inspection.winner_team == "blue"


def test_same_target_physical_check_preserves_skill_bonus_for_later_mental_check(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    physical = InvestigationCheckContent(
        check_key="guard_dog_handler_force",
        question="Can the collar be forced open?",
        statistic="athletics",
        dc=14,
        result="The collar opens.",
        target_actor_id=TARGET,
        traits=("skill",),
    )
    mental = INVESTIGATOR_CLUE_ROOM.relevant_checks[1]
    case = replace(INVESTIGATOR_CLUE_ROOM, relevant_checks=(physical, mental))
    base = content.get_setup("investigator_forensic_vs_two_guard_dogs")
    setup = replace(
        base,
        setup_id="review_skill_stratagem_qualification",
        name="Review Skill Stratagem qualification",
        investigations=(case,),
    )
    _admit(monkeypatch, setup)
    game = Encounter.start(setup, rolls=(20, 1, 2, 7, 10, 11))
    _settle_initiative(game)
    game._state.creatures[INVESTIGATOR].investigator_active_cases = {case.case_id}

    assert game.execute(DeviseStratagem(TARGET)).status is ResultStatus.PAUSED
    assert _choose(game, "skill").status is ResultStatus.COMPLETED
    first = game.execute(InvestigationCheck(physical.check_key, target_id=TARGET))
    physical_check = next(event.check for event in first.events if event.kind == "investigation_check")
    assert physical_check is not None and physical_check.modifier == 4
    assert any(item.source == "Pursue a Lead" and item.amount == 1 for item in physical_check.modifier_breakdown)
    assert not any("Skill Stratagem" in item.source for item in physical_check.modifier_breakdown)
    stored = game._state.creatures[INVESTIGATOR].investigator_stratagem
    assert stored is not None and not stored.consumed

    second = game.execute(InvestigationCheck(mental.check_key, target_id=TARGET))
    mental_check = next(event.check for event in second.events if event.kind == "investigation_check")
    assert mental_check is not None and mental_check.modifier == 9
    assert any(
        item.modifier_type == "circumstance"
        and item.source == "Pursue a Lead (Skill Stratagem)"
        and item.amount == 2
        for item in mental_check.modifier_breakdown
    )
    stored = game._state.creatures[INVESTIGATOR].investigator_stratagem
    assert stored is not None and stored.consumed


def test_saved_free_known_weaknesses_precedes_mode_and_preserves_atomic_choice(
    tmp_path: Path,
) -> None:
    game = Encounter.start(
        content.get_setup("investigator_forensic_vs_two_guard_dogs"),
        rolls=(20, 1, 2, 11, 4, 12),
    )
    _settle_initiative(game)
    investigator = game._state.creatures[INVESTIGATOR]
    investigator.investigator_active_cases = {"guard_dog_case"}
    investigator.investigator_awareness = {TARGET}
    actions_before = investigator.actions_remaining

    opened = game.execute(DeviseStratagem(TARGET, free_action=True, known_weaknesses=True))
    assert opened.status is ResultStatus.PAUSED
    assert game.inspect().choice is not None
    assert game.inspect().choice.kind == "family_action"
    assert "Recall Knowledge" in game.inspect().choice.prompt
    knowledge_path = tmp_path / "review-free-known-knowledge.json"
    game.save(knowledge_path)
    game = Encounter.load(knowledge_path)
    resolved = _choose(game, "keep")
    assert resolved.status is ResultStatus.PAUSED
    mode = resolved.inspection.choice
    assert mode is not None and mode.kind == "family_action"
    assert "attack or skill stratagem" in mode.prompt
    assert tuple(option.option_id for option in mode.options) == ("attack", "skill")
    knowledge = next(event.check for event in resolved.events if event.kind == "recall_knowledge")
    assert knowledge is not None
    assert not any("Skill Stratagem" in item.source for item in knowledge.modifier_breakdown)
    investigator = game._state.creatures[INVESTIGATOR]
    assert investigator.actions_remaining == actions_before
    assert investigator.investigator_stratagem is not None
    assert investigator.investigator_stratagem.die == 4
    assert investigator.investigator_stratagem.mode is None

    mode_path = tmp_path / "review-free-known-mode.json"
    game.save(mode_path)
    game = Encounter.load(mode_path)
    before, dice_before = game.inspect(), game._dice.to_data()
    forged = game.execute(Choose(mode.choice_id, "forged", mode.owner_actor_id))
    assert forged.status is ResultStatus.REJECTED
    assert forged.inspection == before and game._dice.to_data() == dice_before
    assert _choose(game, "skill").status is ResultStatus.COMPLETED
    assert game._state.creatures[INVESTIGATOR].actions_remaining == actions_before

    check_result = game.execute(InvestigationCheck("guard_dog_handler_marks", target_id=TARGET))
    check = next(event.check for event in check_result.events if event.kind == "investigation_check")
    assert check is not None and check.modifier == 9
    assert any(
        item.source == "Pursue a Lead (Skill Stratagem)" and item.amount == 2
        for item in check.modifier_breakdown
    )
    stored = game._state.creatures[INVESTIGATOR].investigator_stratagem
    assert stored is not None and stored.consumed
