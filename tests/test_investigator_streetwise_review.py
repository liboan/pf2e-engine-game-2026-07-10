"""Independent source/play review of selected Investigator Streetwise.

Rules checked 2026-09-16:

* Streetwise: https://2e.aonprd.com/Feats.aspx?ID=5218
* Gather Information: https://2e.aonprd.com/Actions.aspx?ID=2391
* Recall Knowledge: https://2e.aonprd.com/Actions.aspx?ID=2367
* Pursue a Lead: https://2e.aonprd.com/Classes.aspx?ID=59

Streetwise substitutes Society for Diplomacy when Gathering Information and
adds an instant, higher-DC Society Recall option only in familiar settlements.
A failed Recall still permits Gather Information. Gather's time and DC are GM
authored; its critical failure gives incorrect information. Attempt limits in
this slice are likewise authored content, not a universal Streetwise rule.
"""

from dataclasses import replace
from pathlib import Path

import pytest

import pf2e.content as content
from pf2e.encounter import Encounter
from pf2e.investigator import ATTACK_STRATAGEM, DeviseStratagem
from pf2e.investigator_content import (
    FORENSIC_INVESTIGATOR_VS_TWO_DOGS,
    OUTPOST_HANDLER_STREETWISE,
)
from pf2e.model import Choose, Modifier, ResultStatus, Strike


INVESTIGATOR = "forensic_investigator"
TARGET = "investigator_guard_dog_a"


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


def _healthy_victory(monkeypatch: pytest.MonkeyPatch, setup, rolls: tuple[int, ...]) -> Encounter:
    monkeypatch.setattr(content, "_STAGED_SETUPS", content._STAGED_SETUPS | {setup.setup_id: setup})
    game = Encounter.start(setup, rolls=rolls)
    _settle_initiative(game)
    assert all(actor.hp == actor.max_hp for actor in game.inspect().actors)
    assert game.inspect().turn_actor_id == INVESTIGATOR
    assert game.execute(DeviseStratagem(TARGET, mode=ATTACK_STRATAGEM)).status is ResultStatus.COMPLETED
    victory = game.execute(Strike(TARGET, attack_id="shortsword", use_intelligence=True))
    assert victory.status is ResultStatus.COMPLETED
    damage = next(event.damage for event in victory.events if event.kind == "damage")
    assert damage is not None and damage.total == 8
    assert not victory.inspection.in_progress and victory.inspection.winner_team == "blue"
    return game


def _one_dog_setup(setup_id: str, *, streetwise=(OUTPOST_HANDLER_STREETWISE,)):
    return replace(
        FORENSIC_INVESTIGATOR_VS_TWO_DOGS,
        setup_id=setup_id,
        name=setup_id,
        placements=FORENSIC_INVESTIGATOR_VS_TWO_DOGS.placements[:2],
        streetwise=streetwise,
    )


def test_healthy_victory_saved_gather_reroll_charges_once_and_critical_failure_misinforms(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    # Initiatives; attack Devise; two critical damage dice; initial Gather;
    # saved Hero Point reroll to a natural 1 critical failure.
    setup = _one_dog_setup("review_streetwise_critical_failure")
    game = _healthy_victory(monkeypatch, setup, (20, 1, 20, 1, 3, 12, 1))
    before = game.inspect().world_time_seconds

    started = game.streetwise(INVESTIGATOR, "outpost_handler", mode="gather", settlement_key="outpost")
    assert started.status is ResultStatus.PAUSED
    assert game.inspect().world_time_seconds == before + 7200
    path = tmp_path / "review-streetwise-gather.json"
    game.save(path)
    game = Encounter.load(path)
    result = _choose(game, "reroll")

    event = next(item for item in result.events if item.kind == "streetwise_gather")
    assert event.check is not None and event.check.degree.name == "CRITICAL_FAILURE"
    assert event.check.modifier == 7
    assert "Society" in event.text
    assert OUTPOST_HANDLER_STREETWISE.gather_critical_failure_answer in event.text
    assert game.inspect().world_time_seconds == before + 7200
    actor = game._state.creatures[INVESTIGATOR]
    assert actor.hero_points == 0
    assert actor.investigator_streetwise_gather_attempts == {"outpost_handler": 1}
    assert actor.investigator_streetwise_results["outpost_handler"] == (
        OUTPOST_HANDLER_STREETWISE.gather_critical_failure_answer
    )


def test_familiarity_only_gates_recall_and_authored_two_attempt_limit_is_honored(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    record = replace(
        OUTPOST_HANDLER_STREETWISE,
        familiar_actor_ids=("another_investigator",),
        gather_attempt_limit=2,
    )
    setup = _one_dog_setup("review_streetwise_authored_limits", streetwise=(record,))
    game = _healthy_victory(monkeypatch, setup, (20, 1, 20, 1, 3, 20, 20))
    game._state.creatures[INVESTIGATOR].hero_points = 0

    before, dice_before = game.inspect(), game._dice.to_data()
    recall = game.streetwise(INVESTIGATOR, record.question_key, mode="recall", settlement_key="outpost")
    assert recall.status is ResultStatus.REJECTED
    assert recall.inspection == before and game._dice.to_data() == dice_before

    assert game.streetwise(INVESTIGATOR, record.question_key, mode="gather").status is ResultStatus.COMPLETED
    assert game.streetwise(INVESTIGATOR, record.question_key, mode="gather").status is ResultStatus.COMPLETED
    exhausted = game.inspect()
    rejected = game.streetwise(INVESTIGATOR, record.question_key, mode="gather")
    assert rejected.status is ResultStatus.REJECTED and rejected.inspection == exhausted
    actor = game._state.creatures[INVESTIGATOR]
    assert actor.investigator_streetwise_gather_attempts == {record.question_key: 2}
    assert game.inspect().world_time_seconds == 14400


def test_active_lead_bonus_and_saved_result_are_usable_in_the_next_real_scene(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    setup = _one_dog_setup("review_streetwise_lead_carry")
    game = _healthy_victory(monkeypatch, setup, (20, 1, 20, 1, 3, 11, 20, 1))
    actor = game._state.creatures[INVESTIGATOR]
    actor.hero_points = 0

    assert game.pursue_lead(INVESTIGATOR, "guard_dog_case", "bloodied_collar").status is ResultStatus.COMPLETED
    gathered = game.streetwise(INVESTIGATOR, "outpost_handler", mode="gather")
    event = next(item for item in gathered.events if item.kind == "streetwise_gather")
    assert event.check is not None
    assert (event.check.die, event.check.total, event.check.dc) == (11, 19, 15)
    assert Modifier(1, "circumstance", "Pursue a Lead") in event.check.modifier_breakdown
    assert game.inspect().world_time_seconds == 7260

    path = tmp_path / "review-streetwise-lead-carry.json"
    game.save(path)
    game = Encounter.load(path)
    next_setup = replace(
        setup,
        setup_id="review_streetwise_later_scene",
        name="review_streetwise_later_scene",
        streetwise=(),
        placements=(setup.placements[0], replace(setup.placements[1], actor_id="review_next_dog")),
    )
    monkeypatch.setattr(content, "_STAGED_SETUPS", content._STAGED_SETUPS | {next_setup.setup_id: next_setup})
    assert game.next_encounter(next_setup).status in {ResultStatus.COMPLETED, ResultStatus.PAUSED}
    carried = game.streetwise_result(INVESTIGATOR, "outpost_handler")
    assert carried.status is ResultStatus.COMPLETED
    assert carried.events[0].kind == "streetwise_result"
    assert OUTPOST_HANDLER_STREETWISE.gather_success_answer in carried.events[0].text
