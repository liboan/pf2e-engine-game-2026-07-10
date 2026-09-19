"""Public selected Streetwise coverage.

Rules references checked 2026-09-16:

* https://2e.aonprd.com/Feats.aspx?ID=5218
* https://2e.aonprd.com/Actions.aspx?ID=2391

Streetwise substitutes Society for Gather Information.  Its instant Recall
Knowledge option is limited to a settlement the character frequents, uses a
separately authored higher DC, and a failed Recall does not prevent Gather.
"""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest

import pf2e.content as content
from pf2e.checks import Modifier
from pf2e.encounter import Encounter
from pf2e.investigator_content import FORENSIC_INVESTIGATOR_VS_TWO_DOGS
from pf2e.model import ResultStatus
from pf2e.terminal import run_terminal
from terminal_test_helpers import BoundedInput, BoundedTranscript


def _settle_initiative(game: Encounter) -> None:
    for _ in range(8):
        choice = game.inspect().choice
        if choice is None:
            return
        game.choose(choice.choice_id, choice.options[0].option_id, choice.owner_actor_id)
    raise AssertionError("initiative did not settle")


def _finished_game(monkeypatch: pytest.MonkeyPatch, rolls: tuple[int, ...]) -> Encounter:
    setup = FORENSIC_INVESTIGATOR_VS_TWO_DOGS
    monkeypatch.setattr(content, "_STAGED_SETUPS", content._STAGED_SETUPS | {setup.setup_id: setup})
    game = Encounter.start(setup, rolls=rolls)
    _settle_initiative(game)
    for actor_id in ("investigator_guard_dog_a", "investigator_guard_dog_b"):
        actor = game._state.creatures[actor_id]
        actor.hp = 0
        actor.dead = True
    game._state.in_progress = False
    game._state.winner_team = "blue"
    for actor in game._state.creatures.values():
        actor.actions_remaining = 0
    return game


def _choose(game: Encounter, option_id: str):
    choice = game.inspect().choice
    assert choice is not None
    result = game.choose(choice.choice_id, option_id, choice.owner_actor_id)
    assert result.status in {ResultStatus.COMPLETED, ResultStatus.PAUSED}
    return result


def test_familiar_recall_uses_society_higher_dc_and_unfamiliar_is_atomic(monkeypatch: pytest.MonkeyPatch) -> None:
    game = _finished_game(monkeypatch, (20, 1, 2, 12))
    before = game.inspect()
    rejected = game.streetwise("forensic_investigator", "outpost_handler", mode="recall", settlement_key="unknown")
    assert rejected.status is ResultStatus.REJECTED
    assert game.inspect() == before

    result = game.streetwise("forensic_investigator", "outpost_handler", mode="recall")
    assert result.status is ResultStatus.PAUSED
    kept = _choose(game, "keep")
    event = next(item for item in kept.events if item.kind == "streetwise_recall")
    assert event.check is not None
    assert (event.check.die, event.check.total, event.check.dc) == (12, 19, 20)
    assert game.inspect().world_time_seconds == before.world_time_seconds


def test_failed_recall_allows_separate_two_hour_gather_and_saved_hero_charges_once(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    game = _finished_game(monkeypatch, (20, 1, 2, 2, 11))
    before = game.inspect().world_time_seconds
    actor = game._state.creatures["forensic_investigator"]
    failed = game.streetwise(actor.actor_id, "outpost_handler", mode="recall")
    assert failed.status is ResultStatus.PAUSED
    kept_recall = _choose(game, "keep")
    assert next(item for item in kept_recall.events if item.kind == "streetwise_recall").check.degree.name in {"FAILURE", "CRITICAL_FAILURE"}

    started = game.streetwise(actor.actor_id, "outpost_handler", mode="gather")
    assert started.status is ResultStatus.PAUSED
    assert game.inspect().world_time_seconds - before == 7200
    assert game._state.pending_choice is not None
    assert game._state.pending_choice.saved_check is not None
    path = tmp_path / "streetwise-pending.json"
    game.save(path)
    game = Encounter.load(path)
    kept_gather = _choose(game, "keep")
    event = next(item for item in kept_gather.events if item.kind == "streetwise_gather")
    assert event.check is not None
    assert (event.check.die, event.check.total, event.check.dc) == (11, 18, 15)
    assert game.inspect().world_time_seconds - before == 7200
    actor = game._state.creatures["forensic_investigator"]
    assert actor.investigator_streetwise_recall_attempts == {"outpost_handler": 1}
    assert actor.investigator_streetwise_gather_attempts == {"outpost_handler": 1}
    assert actor.investigator_streetwise_results["outpost_handler"].startswith("The outpost quartermaster")


def test_repeat_limits_are_separate_and_result_carries_to_saved_next_scene(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    game = _finished_game(monkeypatch, (20, 1, 2, 20, 20, 1, 2))
    actor_id = "forensic_investigator"
    game._state.creatures[actor_id].hero_points = 0
    assert game.streetwise(actor_id, "outpost_handler", mode="gather").status is ResultStatus.COMPLETED
    snapshot = game.inspect()
    assert game.streetwise(actor_id, "outpost_handler", mode="gather").status is ResultStatus.REJECTED
    assert game.inspect() == snapshot
    path = tmp_path / "streetwise-complete.json"
    game.save(path)
    game = Encounter.load(path)
    next_setup = replace(
        FORENSIC_INVESTIGATOR_VS_TWO_DOGS,
        setup_id="investigator_streetwise_next_scene",
        streetwise=(),
        placements=tuple(
            replace(placement, actor_id={
                "investigator_guard_dog_a": "next_dog_a",
                "investigator_guard_dog_b": "next_dog_b",
            }.get(placement.actor_id, placement.actor_id))
            for placement in FORENSIC_INVESTIGATOR_VS_TWO_DOGS.placements
        ),
    )
    monkeypatch.setattr(content, "_STAGED_SETUPS", content._STAGED_SETUPS | {next_setup.setup_id: next_setup})
    assert game.next_encounter(next_setup).status in {ResultStatus.COMPLETED, ResultStatus.PAUSED}
    assert game._state.creatures[actor_id].investigator_streetwise_results["outpost_handler"].startswith("The outpost quartermaster")
    carried = game.streetwise_result(actor_id, "outpost_handler")
    assert carried.status is ResultStatus.COMPLETED
    assert "outpost quartermaster" in carried.events[0].text


def test_gather_critical_failure_is_authored_incorrect_information(monkeypatch: pytest.MonkeyPatch) -> None:
    game = _finished_game(monkeypatch, (20, 1, 2, 1))
    game._state.creatures["forensic_investigator"].hero_points = 0
    result = game.streetwise("forensic_investigator", "outpost_handler", mode="gather")
    assert result.status is ResultStatus.COMPLETED
    event = next(item for item in result.events if item.kind == "streetwise_gather")
    assert event.check is not None and event.check.degree.name == "CRITICAL_FAILURE"
    assert "false rumor" in event.text
    assert "stablehand" in game._state.creatures["forensic_investigator"].investigator_streetwise_results["outpost_handler"]


def test_explicit_active_lead_adds_typed_circumstance_bonus(monkeypatch: pytest.MonkeyPatch) -> None:
    game = _finished_game(monkeypatch, (20, 1, 2, 11))
    actor = game._state.creatures["forensic_investigator"]
    actor.hero_points = 0
    assert game.pursue_lead(actor.actor_id, "guard_dog_case", "bloodied_collar").status is ResultStatus.COMPLETED
    result = game.streetwise(actor.actor_id, "outpost_handler", mode="gather")
    event = next(item for item in result.events if item.kind == "streetwise_gather")
    assert event.check is not None and (event.check.total, event.check.dc) == (19, 15)
    assert Modifier(1, "circumstance", "Pursue a Lead") in event.check.modifier_breakdown


def test_terminal_exposes_selected_streetwise_and_finishes_bounded(monkeypatch: pytest.MonkeyPatch) -> None:
    finished = _finished_game(monkeypatch, (20, 1, 2, 20))
    finished._state.creatures["forensic_investigator"].hero_points = 0
    monkeypatch.setattr(Encounter, "start", classmethod(lambda _cls, *args, **kwargs: finished))
    inputs = iter(("11", "1", "2", "6"))
    transcript = BoundedTranscript(max_lines=300, max_chars=50_000)
    bounded_input = BoundedInput(lambda: next(inputs), max_calls=20)
    assert run_terminal(
        setup=FORENSIC_INVESTIGATOR_VS_TWO_DOGS,
        rolls=(20, 1, 2, 20),
        input_fn=bounded_input,
        output_fn=transcript.append,
    ) == 0
    rendered = "\n".join(transcript)
    assert "Streetwise" in rendered
    assert "Gather Information (Society, 2 hours)" in rendered
    assert "outpost quartermaster" in rendered
