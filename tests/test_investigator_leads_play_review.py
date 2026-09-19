"""Independent public-play review of Investigator leads and Clue In.

Rules checked 2026-09-16:

* Investigator, On the Case, and Clue In: https://2e.aonprd.com/Classes.aspx?ID=59
* Devise a Stratagem: https://2e.aonprd.com/Actions.aspx?ID=2813
"""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest

import pf2e.content as content
from pf2e.encounter import Encounter
from pf2e.investigator import ATTACK_STRATAGEM, BattleMedicine, DeviseStratagem, InvestigationCheck
from pf2e.investigator_content import (
    FORENSIC_INVESTIGATOR_HEALING_SETUP,
    INVESTIGATOR_CLUE_ROOM,
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


def _register(monkeypatch: pytest.MonkeyPatch, *setups) -> None:
    monkeypatch.setattr(
        content,
        "_STAGED_SETUPS",
        content._STAGED_SETUPS | {setup.setup_id: setup for setup in setups},
    )


def _finish_healthy_healing_fight(
    monkeypatch: pytest.MonkeyPatch,
    setup,
    rolls: tuple[int, ...],
) -> Encounter:
    _register(monkeypatch, setup)
    game = Encounter.start(setup, rolls=rolls)
    assert all(actor.hp == actor.max_hp for actor in game.inspect().actors)
    _settle_initiative(game)
    assert game.inspect().turn_actor_id == "healing_dog"

    assert game.execute(Stride((Position(3, 2),))).status is ResultStatus.COMPLETED
    injury = game.execute(Strike("healing_ally", attack_id="jaws"))
    assert injury.status is ResultStatus.COMPLETED
    assert _actor(game, "healing_ally").hp == 16
    assert game.execute(EndTurn()).status is ResultStatus.COMPLETED
    assert game.execute(EndTurn()).status is ResultStatus.COMPLETED
    assert game.inspect().turn_actor_id == "forensic_investigator"

    medicine = game.execute(BattleMedicine("healing_ally"))
    assert medicine.status is ResultStatus.PAUSED
    assert _choose(game, "keep").status is ResultStatus.COMPLETED
    assert _actor(game, "healing_ally").hp == 21
    assert game.execute(Stride((Position(2, 2),))).status is ResultStatus.COMPLETED
    strike = game.execute(Strike("healing_dog", attack_id="shortsword"))
    if strike.status is ResultStatus.PAUSED:
        strike = _choose(game, "keep")
    assert strike.status is ResultStatus.COMPLETED
    assert _actor(game, "healing_dog").hp == 4
    assert game.execute(EndTurn()).status is ResultStatus.COMPLETED
    victory = game.execute(Strike("healing_dog", attack_id="longsword"))
    if victory.status is ResultStatus.PAUSED:
        victory = _choose(game, "keep")
    assert victory.status is ResultStatus.COMPLETED
    assert not game.inspect().in_progress and game.inspect().winner_team == "blue"
    return game


def test_healthy_victory_pursuit_scene_carry_free_devise_and_saved_ally_clue_in(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    # First fight; next-scene initiatives; Known Weaknesses, stored Devise,
    # ally investigation check, then its finishing Strike.
    rolls = (
        1, 2, 20, 12, 4, 12, 3, 4, 10, 4, 10, 4,
        20, 2, 1, 20, 14, 1, 1, 14, 20, 1,
    )
    game = _finish_healthy_healing_fight(
        monkeypatch,
        FORENSIC_INVESTIGATOR_HEALING_SETUP,
        rolls,
    )

    before_pursuit = game.inspect().world_time_seconds
    pursued = game.pursue_lead(
        "forensic_investigator", "guard_dog_case", "bloodied_collar"
    )
    assert pursued.status is ResultStatus.COMPLETED
    assert game.inspect().world_time_seconds == before_pursuit + 60
    investigator = game._state.creatures["forensic_investigator"]
    assert investigator.investigator_active_cases == {"guard_dog_case"}
    assert investigator.investigator_lead_cooldown_until == before_pursuit + 660

    pursued_path = tmp_path / "review-investigator-pursued-lead.json"
    game.save(pursued_path)
    game = Encounter.load(pursued_path)

    tracks = INVESTIGATOR_CLUE_ROOM.relevant_checks[0]
    ally_tracks = replace(
        tracks,
        target_actor_id="investigator_guard_dog_a",
        helper_actor_ids=("healing_ally",),
    )
    ally_case = replace(
        INVESTIGATOR_CLUE_ROOM,
        relevant_checks=(ally_tracks,),
    )
    next_setup = replace(
        FORENSIC_INVESTIGATOR_HEALING_SETUP,
        setup_id="review_investigator_lead_ally_scene",
        name="Review Investigator lead with allied Clue In",
        placements=tuple(
            replace(placement, actor_id="investigator_guard_dog_a")
            if placement.actor_id == "healing_dog"
            else placement
            for placement in FORENSIC_INVESTIGATOR_HEALING_SETUP.placements
        ),
        examinations=(),
        investigations=(ally_case,),
    )
    _register(monkeypatch, next_setup)
    transitioned = game.next_encounter(next_setup)
    assert transitioned.status in {ResultStatus.PAUSED, ResultStatus.COMPLETED}
    _settle_initiative(game)
    assert game.inspect().turn_actor_id == "forensic_investigator"
    investigator = game._state.creatures["forensic_investigator"]
    assert investigator.investigator_active_cases == {"guard_dog_case"}
    assert investigator.investigator_awareness == {"investigator_guard_dog_a"}

    actions_before = investigator.actions_remaining
    known = game.execute(
        DeviseStratagem(
            "investigator_guard_dog_a",
            mode=ATTACK_STRATAGEM,
            free_action=True,
            known_weaknesses=True,
        )
    )
    assert known.status is ResultStatus.PAUSED
    known_path = tmp_path / "review-free-devise-known-weaknesses.json"
    game.save(known_path)
    game = Encounter.load(known_path)
    known = _choose(game, "keep")
    assert known.status is ResultStatus.COMPLETED
    kinds = [event.kind for event in known.events]
    assert kinds.index("recall_knowledge") < kinds.index("devise_stratagem")
    investigator = game._state.creatures["forensic_investigator"]
    assert investigator.actions_remaining == actions_before
    assert investigator.investigator_stratagem is not None
    assert investigator.investigator_stratagem.die == 14

    assert game.execute(
        Stride((Position(1, 2), Position(2, 2), Position(3, 2)))
    ).status is ResultStatus.COMPLETED
    devised_strike = game.execute(
        Strike(
            "investigator_guard_dog_a",
            attack_id="shortsword",
            use_intelligence=True,
        )
    )
    assert devised_strike.status is ResultStatus.COMPLETED
    attack = next(event.check for event in devised_strike.events if event.kind == "strike")
    damage = next(event.damage for event in devised_strike.events if event.kind == "damage")
    assert attack is not None and (attack.die, attack.modifier, attack.total) == (14, 8, 22)
    assert any(
        modifier.source == "Known Weaknesses"
        and modifier.amount == 1
        and modifier.modifier_type == "circumstance"
        for modifier in attack.modifier_breakdown
    )
    assert damage is not None and damage.total == 2
    assert [(part.source, part.modifier) for part in damage.components] == [
        ("shortsword", 0),
        ("investigator_strategic_strike", 0),
    ]
    assert game.execute(EndTurn()).status is ResultStatus.COMPLETED
    assert game.inspect().turn_actor_id == "healing_ally"

    dice_before = game._dice.to_data()
    started = game.execute(
        InvestigationCheck("guard_dog_handler_tracks", target_id="investigator_guard_dog_a")
    )
    assert started.status is ResultStatus.PAUSED
    choice = started.inspection.choice
    assert choice is not None and choice.kind == "reaction"
    assert choice.owner_actor_id == "forensic_investigator"
    pending = game._state.pending_choice
    assert pending is not None and pending.saved_check is not None
    assert pending.saved_check.result is None
    assert game._dice.to_data() == dice_before

    clue_path = tmp_path / "review-saved-ally-clue-in.json"
    game.save(clue_path)
    game = Encounter.load(clue_path)
    used = _choose(game, "use")
    clue_event = next(event for event in used.events if event.kind == "clue_in_used")
    check_event = next(event for event in used.events if event.kind == "investigation_check")
    assert (clue_event.actor_id, clue_event.target_id) == (
        "forensic_investigator",
        "healing_ally",
    )
    assert "Communication traits: auditory, linguistic" in clue_event.details
    assert check_event.actor_id == "healing_ally"
    assert check_event.check is not None
    assert check_event.check.modifier == 7
    investigator = game._state.creatures["forensic_investigator"]
    assert not investigator.reaction_available
    assert investigator.investigator_clue_in_cooldown_until == game.inspect().world_time_seconds + 600

    assert game.execute(Stride((Position(3, 1),))).status is ResultStatus.COMPLETED
    final = game.execute(Strike("investigator_guard_dog_a", attack_id="longsword"))
    assert final.status is ResultStatus.PAUSED
    final = _choose(game, "keep")
    assert final.status is ResultStatus.COMPLETED
    assert not final.inspection.in_progress and final.inspection.winner_team == "blue"


def test_public_daily_preparation_reopens_abandoned_case_without_clock_shortcuts(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    cases = tuple(
        replace(INVESTIGATOR_CLUE_ROOM, case_id=case_id, name=case_id)
        for case_id in ("first_case", "second_case", "third_case")
    )
    setup = replace(
        FORENSIC_INVESTIGATOR_HEALING_SETUP,
        setup_id="review_investigator_lead_daily_preparation",
        investigations=cases,
    )
    game = _finish_healthy_healing_fight(
        monkeypatch,
        setup,
        (1, 2, 20, 12, 4, 12, 3, 4, 10, 4, 10, 4),
    )

    assert game.pursue_lead(
        "forensic_investigator", "first_case", "bloodied_collar"
    ).status is ResultStatus.COMPLETED
    assert game.record_rested(
        ("forensic_investigator",), day_number=2, elapsed_seconds=3600
    ).status is ResultStatus.COMPLETED
    assert game.daily_prepare(("forensic_investigator",)).status is ResultStatus.COMPLETED
    assert game.pursue_lead(
        "forensic_investigator", "second_case", "bloodied_collar"
    ).status is ResultStatus.COMPLETED
    assert game.record_rested(
        ("forensic_investigator",), day_number=3, elapsed_seconds=3600
    ).status is ResultStatus.COMPLETED
    assert game.daily_prepare(("forensic_investigator",)).status is ResultStatus.COMPLETED
    assert game.pursue_lead(
        "forensic_investigator",
        "third_case",
        "bloodied_collar",
        replace_case_id="first_case",
    ).status is ResultStatus.COMPLETED
    actor = game._state.creatures["forensic_investigator"]
    assert actor.investigator_active_cases == {"second_case", "third_case"}
    assert actor.investigator_abandoned_cases == {"first_case"}

    before = game.inspect()
    dice_before = game._dice.to_data()
    blocked = game.pursue_lead(
        "forensic_investigator",
        "first_case",
        "bloodied_collar",
        replace_case_id="second_case",
    )
    assert blocked.status is ResultStatus.REJECTED
    assert game.inspect() == before
    assert game._dice.to_data() == dice_before

    assert game.record_rested(
        ("forensic_investigator",), day_number=4, elapsed_seconds=3600
    ).status is ResultStatus.COMPLETED
    assert game.daily_prepare(("forensic_investigator",)).status is ResultStatus.COMPLETED
    assert not game._state.creatures["forensic_investigator"].investigator_abandoned_cases
    reopened = game.pursue_lead(
        "forensic_investigator",
        "first_case",
        "bloodied_collar",
        replace_case_id="second_case",
    )
    assert reopened.status is ResultStatus.COMPLETED
    assert game._state.creatures["forensic_investigator"].investigator_active_cases == {
        "first_case",
        "third_case",
    }
