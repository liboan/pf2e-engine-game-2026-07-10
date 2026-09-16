"""Independent public-play review of authored Recall Knowledge.

Rules references:
- Recall Knowledge: https://2e.aonprd.com/Actions.aspx?ID=2367
- Additional Knowledge: https://2e.aonprd.com/Rules.aspx?ID=2638
- Known Weaknesses: https://2e.aonprd.com/Feats.aspx?ID=5936
- Devise a Stratagem: https://2e.aonprd.com/Actions.aspx?ID=2813
- Secret checks and fortune: https://2e.aonprd.com/Rules.aspx?ID=2263
"""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest

import pf2e.content as content
from pf2e import Rage
from pf2e.encounter import Encounter
from pf2e.investigator import DeviseStratagem, RecallKnowledge
from pf2e.investigator_content import (
    FORENSIC_INVESTIGATOR_HEALING_SETUP,
    GUARD_DOG_KNOWLEDGE,
    RecallKnowledgeContent,
)
from pf2e.model import (
    CreaturePlacement,
    EncounterSetup,
    EndTurn,
    Position,
    ResultStatus,
    Strike,
    Stride,
)
from pf2e.skill_actions import Demoralize, Trip


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


def _register(monkeypatch: pytest.MonkeyPatch, *setups: EncounterSetup) -> None:
    monkeypatch.setattr(
        content,
        "_STAGED_SETUPS",
        content._STAGED_SETUPS | {setup.setup_id: setup for setup in setups},
    )


def test_healthy_known_weaknesses_fight_saves_ordered_check_wins_and_carries_subject_history(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    first_knowledge = replace(
        GUARD_DOG_KNOWLEDGE,
        communication_recipients=("healing_ally",),
    )
    first_setup = replace(
        FORENSIC_INVESTIGATOR_HEALING_SETUP,
        setup_id="review_known_weaknesses_healthy_fight",
        name="Review Known Weaknesses healthy fight",
        knowledge=(first_knowledge,),
    )
    changed_knowledge = replace(
        first_knowledge,
        question="What new physical clue identifies this later guard dog?",
        allowed_skills=(("crafting", 18),),
        dc_progression=(18, 20, 22),
        answer="Its reinforced tracking collar uses the same kennel pattern.",
    )
    next_setup = replace(
        first_setup,
        setup_id="review_known_weaknesses_later_scene",
        name="Review later knowledge scene",
        placements=tuple(
            replace(placement, actor_id="later_healing_dog")
            if placement.actor_id == "healing_dog"
            else placement
            for placement in first_setup.placements
        ),
        knowledge=(changed_knowledge,),
    )
    _register(monkeypatch, first_setup, next_setup)

    # First scene initiatives; critical knowledge; Devise die; Investigator
    # weapon/precision dice; dog attack/damage; ally attack/damage. Then the
    # later scene initiatives and its changed-question Crafting check.
    rolls = (20, 1, 5, 20, 14, 1, 1, 12, 4, 10, 4, 20, 1, 5, 13)
    game = Encounter.start(first_setup, rolls=rolls)
    assert all(actor.hp == actor.max_hp for actor in game.inspect().actors)
    _settle_initiative(game)
    assert game.inspect().turn_actor_id == "forensic_investigator"

    started = game.execute(DeviseStratagem("healing_dog", known_weaknesses=True))
    assert started.status is ResultStatus.PAUSED
    assert started.inspection.choice is not None
    assert started.inspection.choice.kind == "family_action"
    assert game._state.creatures["forensic_investigator"].actions_remaining == 2
    assert game._state.creatures["forensic_investigator"].investigator_stratagem is None
    assert game._state.creatures["forensic_investigator"].investigator_knowledge_attempts == {}

    pending_path = tmp_path / "known-weaknesses-knowledge-pending.json"
    game.save(pending_path)
    game = Encounter.load(pending_path)
    assert game.inspect().choice == started.inspection.choice
    finalized = _choose(game, "keep")
    assert finalized.status is ResultStatus.COMPLETED
    kinds = [event.kind for event in finalized.events]
    assert kinds.index("recall_knowledge") < kinds.index("known_weaknesses") < kinds.index("devise_stratagem")
    knowledge_check = next(event.check for event in finalized.events if event.kind == "recall_knowledge")
    assert knowledge_check is not None
    assert (knowledge_check.die, knowledge_check.dc, knowledge_check.degree.name) == (
        20,
        16,
        "CRITICAL_SUCCESS",
    )
    investigator = game._state.creatures["forensic_investigator"]
    assert investigator.investigator_knowledge_attempts == {"guard_dog": 1}
    assert investigator.actions_remaining == 2
    assert investigator.investigator_stratagem is not None
    assert investigator.investigator_stratagem.die == 14
    assert {
        bonus.recipient_actor_id for bonus in game._state.investigator_weakness_bonuses
    } == {"forensic_investigator", "healing_ally"}

    assert game.execute(Stride((Position(2, 1), Position(3, 1)))).status is ResultStatus.COMPLETED
    investigator_attack = game.execute(
        Strike("healing_dog", attack_id="shortsword", use_intelligence=True)
    )
    assert investigator_attack.status is ResultStatus.COMPLETED
    attack_check = next(event.check for event in investigator_attack.events if event.kind == "strike")
    assert attack_check is not None and attack_check.die == 14
    assert any(
        modifier.source == "Known Weaknesses" and modifier.amount == 1
        for modifier in attack_check.modifier_breakdown
    )
    assert not any(
        bonus.recipient_actor_id == "forensic_investigator"
        for bonus in game._state.investigator_weakness_bonuses
    )
    assert _actor(game, "healing_dog").hp == 6

    # The third action completes the Investigator's turn automatically.
    assert game.inspect().turn_actor_id == "healing_dog"
    assert game.execute(Stride((Position(3, 2),))).status is ResultStatus.COMPLETED
    assert game.execute(Strike("healing_ally", attack_id="jaws")).status is ResultStatus.COMPLETED
    assert _actor(game, "healing_ally").hp == 16
    assert game.execute(EndTurn()).status is ResultStatus.COMPLETED
    assert game.inspect().turn_actor_id == "healing_ally"
    ally_attack = game.execute(Strike("healing_dog", attack_id="longsword"))
    assert ally_attack.status is ResultStatus.PAUSED
    ally_check = next(event.check for event in ally_attack.events if event.kind == "strike")
    assert ally_check is not None
    assert any(
        modifier.source == "Known Weaknesses" and modifier.amount == 1
        for modifier in ally_check.modifier_breakdown
    )
    victory = _choose(game, "keep")
    assert victory.status is ResultStatus.COMPLETED
    assert not game.inspect().in_progress and game.inspect().winner_team == "blue"
    assert game._state.investigator_weakness_bonuses == []

    transitioned = game.next_encounter(next_setup)
    assert transitioned.status in {ResultStatus.PAUSED, ResultStatus.COMPLETED}
    _settle_initiative(game)
    assert game.inspect().turn_actor_id == "forensic_investigator"
    assert game._state.creatures["forensic_investigator"].investigator_knowledge_attempts == {
        "guard_dog": 1
    }
    later = game.execute(
        RecallKnowledge(
            "guard_dog",
            changed_knowledge.question,
            "crafting",
            "later_healing_dog",
        )
    )
    assert later.status is ResultStatus.PAUSED
    later_path = tmp_path / "changed-question-history.json"
    game.save(later_path)
    game = Encounter.load(later_path)
    later = _choose(game, "keep")
    later_check = next(event.check for event in later.events if event.kind == "recall_knowledge")
    assert later_check is not None
    assert (later_check.die, later_check.modifier, later_check.total, later_check.dc) == (
        13,
        7,
        20,
        20,
    )
    assert changed_knowledge.answer in next(
        event.text for event in later.events if event.kind == "recall_knowledge"
    )
    assert game._state.creatures["forensic_investigator"].investigator_knowledge_attempts == {
        "guard_dog": 2
    }


def test_known_weaknesses_bonus_ignores_skill_attack_and_wrong_target_then_miss_consumes_and_source_turn_expires(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    knowledge = replace(
        GUARD_DOG_KNOWLEDGE,
        communication_recipients=("healing_ally",),
    )
    setup = EncounterSetup(
        setup_id="review_known_weaknesses_attack_consumption",
        name="Review Known Weaknesses attack consumption",
        width=5,
        height=3,
        placements=(
            CreaturePlacement(
                "forensic_investigator",
                content.get_definition("investigator_forensic_level_1").definition_id,
                "Forensic Investigator",
                "blue",
                Position(1, 1),
            ),
            CreaturePlacement(
                "healing_ally",
                content.MELEE_FIGHTER_M.definition_id,
                "Informed Ally",
                "blue",
                Position(2, 1),
            ),
            CreaturePlacement(
                "knowledge_dog",
                content.GUARD_DOG.definition_id,
                "Knowledge Dog",
                "red",
                Position(3, 1),
            ),
            CreaturePlacement(
                "other_dog",
                content.GUARD_DOG.definition_id,
                "Other Dog",
                "red",
                Position(3, 2),
            ),
        ),
        knowledge=(knowledge,),
    )
    _register(monkeypatch, setup)
    game = Encounter.start(setup, rolls=(20, 10, 2, 1, 20, 14, 10, 1, 1))
    _settle_initiative(game)
    started = game.execute(DeviseStratagem("knowledge_dog", known_weaknesses=True))
    assert started.status is ResultStatus.PAUSED
    assert _choose(game, "keep").status is ResultStatus.COMPLETED
    assert {
        bonus.recipient_actor_id for bonus in game._state.investigator_weakness_bonuses
    } == {"forensic_investigator", "healing_ally"}

    assert game.execute(EndTurn()).status is ResultStatus.COMPLETED
    assert game.inspect().turn_actor_id == "healing_ally"
    tripped = game.execute(Trip("knowledge_dog"))
    assert tripped.status is ResultStatus.PAUSED
    tripped = _choose(game, "keep")
    trip_check = next(event.check for event in tripped.events if event.kind == "trip_check")
    assert trip_check is not None
    assert not any(modifier.source == "Known Weaknesses" for modifier in trip_check.modifier_breakdown)
    assert any(
        bonus.recipient_actor_id == "healing_ally"
        for bonus in game._state.investigator_weakness_bonuses
    )

    wrong = game.execute(Strike("other_dog", attack_id="longsword"))
    assert wrong.status is ResultStatus.PAUSED
    wrong_check = next(event.check for event in wrong.events if event.kind == "strike")
    assert wrong_check is not None and wrong_check.die == 1
    assert not any(modifier.source == "Known Weaknesses" for modifier in wrong_check.modifier_breakdown)
    assert _choose(game, "keep").status is ResultStatus.COMPLETED
    assert any(
        bonus.recipient_actor_id == "healing_ally"
        for bonus in game._state.investigator_weakness_bonuses
    )

    target_miss = game.execute(Strike("knowledge_dog", attack_id="longsword"))
    assert target_miss.status is ResultStatus.PAUSED
    target_check = next(event.check for event in target_miss.events if event.kind == "strike")
    assert target_check is not None and target_check.die == 1
    assert any(
        modifier.source == "Known Weaknesses" and modifier.amount == 1
        for modifier in target_check.modifier_breakdown
    )
    assert not any(
        bonus.recipient_actor_id == "healing_ally"
        for bonus in game._state.investigator_weakness_bonuses
    )
    assert _choose(game, "keep").status is ResultStatus.COMPLETED

    for _ in range(4):
        if game.inspect().turn_actor_id == "forensic_investigator":
            break
        assert game.execute(EndTurn()).status is ResultStatus.COMPLETED
    assert game.inspect().turn_actor_id == "forensic_investigator"
    assert game._state.investigator_weakness_bonuses == []


def test_generic_fighter_uses_conditions_then_hero_finalization_exhausts_subject(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    setup = EncounterSetup(
        setup_id="review_generic_recall_knowledge_conditions",
        name="Review generic Recall Knowledge conditions",
        width=5,
        height=3,
        placements=(
            CreaturePlacement(
                "braggart",
                content.get_definition("swashbuckler_braggart_level_1").definition_id,
                "Hostile Braggart",
                "red",
                Position(1, 1),
            ),
            CreaturePlacement(
                "ordinary_fighter",
                content.MELEE_FIGHTER_M.definition_id,
                "Ordinary Fighter",
                "blue",
                Position(2, 1),
            ),
            CreaturePlacement(
                "generic_dog",
                content.GUARD_DOG.definition_id,
                "Knowledge Dog",
                "red",
                Position(3, 1),
            ),
        ),
        knowledge=(replace(GUARD_DOG_KNOWLEDGE, dc_progression=(16, 18)),),
    )
    _register(monkeypatch, setup)
    # Initiatives; Braggart Demoralize; first knowledge; second knowledge and reroll.
    game = Encounter.start(setup, rolls=(20, 10, 1, 8, 14, 1, 5))
    _settle_initiative(game)
    assert game.inspect().turn_actor_id == "braggart"
    frightened = game.execute(Demoralize("ordinary_fighter", use_intimidating_glare=True))
    assert frightened.status is ResultStatus.PAUSED
    assert _choose(game, "keep").status is ResultStatus.COMPLETED
    assert game.execute(EndTurn()).status is ResultStatus.COMPLETED
    assert game.inspect().turn_actor_id == "ordinary_fighter"

    recalled = game.execute(
        RecallKnowledge("guard_dog", GUARD_DOG_KNOWLEDGE.question, "society", "generic_dog")
    )
    assert recalled.status is ResultStatus.PAUSED
    recalled = _choose(game, "keep")
    check = next(event.check for event in recalled.events if event.kind == "recall_knowledge")
    assert check is not None
    assert (check.die, check.modifier, check.total, check.dc) == (14, 2, 16, 16)
    assert any(
        "frightened" in modifier.source.casefold() and modifier.amount == -1
        for modifier in check.modifier_breakdown
    )
    fighter = game._state.creatures["ordinary_fighter"]
    assert fighter.investigator_knowledge_attempts == {"guard_dog": 1}

    pending = game.execute(
        RecallKnowledge("guard_dog", GUARD_DOG_KNOWLEDGE.question, "society", "generic_dog")
    )
    assert pending.status is ResultStatus.PAUSED
    assert fighter.investigator_knowledge_attempts == {"guard_dog": 1}
    finalized = _choose(game, "reroll")
    assert finalized.status is ResultStatus.COMPLETED
    final_check = next(event.check for event in finalized.events if event.kind == "recall_knowledge")
    assert final_check is not None and final_check.die == 5
    fighter = game._state.creatures["ordinary_fighter"]
    assert fighter.hero_points == 0
    assert fighter.investigator_knowledge_attempts == {"guard_dog": 2}
    assert fighter.investigator_knowledge_exhausted == {"guard_dog"}


def test_raging_barbarian_rejects_concentrate_recall_knowledge_atomically(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    base = content.get_setup("barbarian_rage_test")
    record = RecallKnowledgeContent(
        subject_key="barbarian_guard",
        question="What stance is the guard using?",
        allowed_skills=(("society", 15),),
        dc_progression=(15, 17),
        answer="The guard is braced for a frontal attack.",
        critical_context="Its weight is committed to that stance.",
        subject_actor_id="barbarian_guard",
    )
    setup = replace(
        base,
        setup_id="review_raging_recall_knowledge",
        name="Review raging Recall Knowledge",
        knowledge=(record,),
    )
    _register(monkeypatch, setup)
    game = Encounter.start(setup, rolls=(20, 1, 14))
    # Quick-Tempered is offered after the initiative choices and before the
    # Barbarian's first turn begins.
    for _ in range(8):
        choice = game.inspect().choice
        assert choice is not None
        if choice.kind == "family_action":
            break
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
    else:
        raise AssertionError("Quick-Tempered choice did not appear within eight choices")
    quick_tempered = game.inspect().choice
    assert quick_tempered is not None and quick_tempered.kind == "family_action"
    assert _choose(game, "decline").status is ResultStatus.COMPLETED
    assert game.execute(Rage()).status is ResultStatus.COMPLETED

    before = game.inspect()
    dice_before = game._dice.to_data()
    rejected = game.execute(
        RecallKnowledge("barbarian_guard", record.question, "society", "barbarian_guard")
    )
    assert rejected.status is ResultStatus.REJECTED
    assert "concentrate" in rejected.message.lower()
    assert game.inspect() == before
    assert game._dice.to_data() == dice_before
