"""Adverse public-play review for accepted Forensic Battle Medicine.

Rules references:
- Battle Medicine: https://2e.aonprd.com/Feats.aspx?ID=5125
- Forensic Medicine: https://2e.aonprd.com/Methodologies.aspx?ID=7
- Treat Wounds outcomes: https://2e.aonprd.com/Actions.aspx?ID=2399
"""

from __future__ import annotations

from pathlib import Path

import pytest

import pf2e.content as content
from pf2e.encounter import Encounter
from pf2e.investigator import BattleMedicine
from pf2e.investigator_content import FORENSIC_INVESTIGATOR
from pf2e.model import (
    CreaturePlacement,
    EncounterSetup,
    EndTurn,
    Position,
    ResultStatus,
    Strike,
)


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


def test_actual_knockout_then_saved_battle_medicine_critical_failure_advances_dying_and_applies_immunity(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    setup = EncounterSetup(
        setup_id="review_forensic_dying_critical_failure",
        name="Review Forensic Medicine while dying",
        width=4,
        height=3,
        placements=(
            CreaturePlacement(
                "forensic_investigator",
                FORENSIC_INVESTIGATOR.definition_id,
                "Forensic Investigator",
                "blue",
                Position(1, 1),
            ),
            CreaturePlacement(
                "forensic_ally",
                content.MELEE_FIGHTER_M.definition_id,
                "Forensic Ally",
                "blue",
                Position(2, 1),
            ),
            CreaturePlacement(
                "hostile_fighter",
                content.MELEE_FIGHTER_M.definition_id,
                "Hostile Fighter",
                "red",
                Position(3, 1),
            ),
        ),
    )
    monkeypatch.setattr(
        content,
        "_STAGED_SETUPS",
        content._STAGED_SETUPS | {setup.setup_id: setup},
    )
    # Initiatives; hostile critical Strike and d8; Medicine natural 1;
    # critical-failure d8. Every actor begins at its authored maximum HP.
    game = Encounter.start(setup, rolls=(10, 1, 20, 20, 7, 1, 1))
    assert all(actor.hp == actor.max_hp for actor in game.inspect().actors)
    _settle_initiative(game)
    assert game.inspect().turn_actor_id == "hostile_fighter"

    knockout = game.execute(Strike("forensic_ally", attack_id="longsword"))
    assert knockout.status is ResultStatus.PAUSED
    assert knockout.inspection.choice is not None
    assert knockout.inspection.choice.kind == "attack_hero_reroll"
    knockout = _choose(game, "keep")
    assert knockout.status is ResultStatus.PAUSED
    assert knockout.inspection.choice is not None
    assert knockout.inspection.choice.kind == "heroic_recovery_damage"
    knockout = _choose(game, "normal")
    assert knockout.status is ResultStatus.COMPLETED
    ally = _actor(game, "forensic_ally")
    assert (ally.hp, ally.dying, ally.wounded, ally.unconscious) == (0, 2, 0, True)

    assert game.execute(EndTurn()).status is ResultStatus.COMPLETED
    assert game.inspect().turn_actor_id == "forensic_investigator"
    medicine = game.execute(BattleMedicine("forensic_ally"))
    assert medicine.status is ResultStatus.PAUSED
    assert medicine.inspection.choice is not None
    assert medicine.inspection.choice.kind == "family_action"
    assert "Hero Point" in medicine.inspection.choice.prompt
    save_path = tmp_path / "forensic-dying-medicine.json"
    game.save(save_path)
    game = Encounter.load(save_path)
    assert game.inspect().choice == medicine.inspection.choice

    checked = _choose(game, "keep")
    assert checked.status is ResultStatus.PAUSED
    assert checked.inspection.choice is not None
    assert checked.inspection.choice.kind == "heroic_recovery_damage"
    failed = _choose(game, "normal")
    assert failed.status is ResultStatus.COMPLETED
    events = (*checked.events, *failed.events)
    check = next(event.check for event in events if event.kind == "battle_medicine_check")
    assert check is not None
    assert (check.die, check.modifier, check.total, check.dc) == (1, 4, 5, 15)
    damage = next(event.damage for event in events if event.damage is not None)
    assert damage is not None and damage.total == 1
    ally = _actor(game, "forensic_ally")
    assert (ally.hp, ally.dying, ally.wounded, ally.unconscious) == (0, 3, 0, True)
    immunity = game._state.condition_immunities
    assert len(immunity) == 1
    assert (
        immunity[0].kind,
        immunity[0].source_actor_id,
        immunity[0].target_actor_id,
        immunity[0].expires_at_seconds,
    ) == ("battle_medicine", "forensic_investigator", "forensic_ally", 3600)

    before = game.inspect()
    dice_before = game._dice.to_data()
    repeated = game.execute(BattleMedicine("forensic_ally"))
    assert repeated.status is ResultStatus.REJECTED
    assert "temporarily immune" in repeated.message
    assert game.inspect() == before
    assert game._dice.to_data() == dice_before
