"""Public encounter checks for Feint's attacker-scoped runtime behavior."""

from __future__ import annotations

from pathlib import Path

import pytest

from pf2e.checks import DegreeOfSuccess
from pf2e.content import get_setup
from pf2e.encounter import Encounter
from pf2e.model import EndTurn, ResultStatus, Strike
from pf2e.skill_actions import Escape, Feint, Grapple, Trip


def _ready(*rolls: int) -> Encounter:
    game = Encounter.start(get_setup("s3_feint_fighter_duel"), rolls=rolls)
    while game.inspect().choice is not None:
        choice = game.inspect().choice
        assert choice is not None
        option_ids = {option.option_id for option in choice.options}
        assert "keep" in option_ids
        game.choose(choice.choice_id, "keep", choice.owner_actor_id)
    return game


def _keep_check(game: Encounter, result, event_kind: str):
    assert result.status is ResultStatus.PAUSED
    choice = result.inspection.choice
    assert choice is not None
    assert "keep" in {option.option_id for option in choice.options}
    resumed = game.choose(choice.choice_id, "keep", choice.owner_actor_id)
    return next(event for event in resumed.events if event.kind == event_kind)


def _strike_check(game: Encounter, *, target_id: str = "duel_fighter", attack_id: str = "longsword"):
    result = game.execute(Strike(target_id, attack_id, "slashing" if attack_id == "longsword" else None))
    return _keep_check(game, result, "strike")


def test_success_survives_rejection_and_saved_strike_uses_original_ac_then_consumes(
    tmp_path: Path,
) -> None:
    game = _ready(20, 1, 15, 8, 8, 20, 1)

    feint = _keep_check(game, game.execute(Feint("duel_fighter")), "feint_check")
    assert feint.check is not None and feint.check.degree is DegreeOfSuccess.SUCCESS
    rejected = game.execute(Strike("missing_target", "longsword", "slashing"))
    assert rejected.status is ResultStatus.REJECTED

    prepared = game.execute(Strike("duel_fighter", "longsword", "slashing"))
    assert prepared.status is ResultStatus.PAUSED
    assert prepared.inspection.choice is not None
    save_path = tmp_path / "feint-strike-hero.json"
    game.save(save_path)
    game = Encounter.load(save_path)
    assert game.inspect() == prepared.inspection

    choice = game.inspect().choice
    assert choice is not None
    resolved = game.choose(choice.choice_id, "keep", choice.owner_actor_id)
    first = next(event for event in resolved.events if event.kind == "strike")
    assert first.check is not None
    assert (first.check.dc, first.check.degree) == (16, DegreeOfSuccess.SUCCESS)

    second = _strike_check(game)
    assert second.check is not None
    assert second.check.dc == 18

    knockout = game.inspect().choice
    assert knockout is not None and knockout.kind == "heroic_recovery_damage"
    finished = game.choose(knockout.choice_id, "normal", knockout.owner_actor_id)
    assert finished.status is ResultStatus.COMPLETED
    assert not finished.inspection.in_progress
    assert finished.inspection.winner_team == "blue"
    defeated = next(actor for actor in finished.inspection.actors if actor.actor_id == "duel_fighter")
    assert (defeated.hp, defeated.dying, defeated.unconscious) == (0, 2, True)


def test_feint_escape_from_actual_holder_preserves_opening_for_map_strike(
    tmp_path: Path,
) -> None:
    game = _ready(1, 20, 11, 15, 10, 12, 4)
    assert game.inspect().turn_actor_id == "duel_fighter"

    grapple = _keep_check(game, game.execute(Grapple("feint_fighter")), "grapple_check")
    assert grapple.check is not None and grapple.check.degree is DegreeOfSuccess.SUCCESS
    assert game.execute(EndTurn()).status is ResultStatus.COMPLETED

    feint = _keep_check(game, game.execute(Feint("duel_fighter")), "feint_check")
    assert feint.check is not None and feint.check.degree is DegreeOfSuccess.SUCCESS
    save_path = tmp_path / "feint-before-escape.json"
    game.save(save_path)
    game = Encounter.load(save_path)

    escaped = _keep_check(
        game,
        game.execute(Escape("grapple:duel_fighter:feint_fighter", "athletics")),
        "escape_check",
    )
    assert escaped.check is not None
    assert (escaped.check.dc, escaped.check.degree) == (17, DegreeOfSuccess.SUCCESS)

    strike = _strike_check(game)
    assert strike.check is not None
    assert (strike.check.dc, strike.check.map_penalty, strike.check.degree) == (
        16,
        -5,
        DegreeOfSuccess.SUCCESS,
    )


@pytest.mark.parametrize(
    ("maneuver", "event_kind", "expected_dc"),
    (
        (Trip("duel_fighter"), "trip_check", 16),
        (Grapple("duel_fighter"), "grapple_check", 18),
    ),
)
def test_committed_physical_maneuver_consumes_success_without_changing_save_dc(
    maneuver, event_kind: str, expected_dc: int,
) -> None:
    game = _ready(20, 1, 15, 5, 12)
    feint = _keep_check(game, game.execute(Feint("duel_fighter")), "feint_check")
    assert feint.check is not None and feint.check.degree is DegreeOfSuccess.SUCCESS

    attempted = _keep_check(game, game.execute(maneuver), event_kind)
    assert attempted.check is not None
    assert (attempted.check.dc, attempted.check.degree) == (
        expected_dc,
        DegreeOfSuccess.FAILURE,
    )

    strike = _strike_check(game)
    assert strike.check is not None
    assert (strike.check.dc, strike.check.map_penalty) == (18, -5)


def test_failure_creates_no_opening() -> None:
    game = _ready(20, 1, 10, 10, 1)
    result = game.execute(Feint("duel_fighter"))
    feint = _keep_check(game, result, "feint_check")
    assert feint.check is not None and feint.check.degree is DegreeOfSuccess.FAILURE

    strike = _strike_check(game)
    assert strike.check is not None and strike.check.dc == 18


def test_critical_success_applies_to_every_melee_attack_until_next_turn_end() -> None:
    game = _ready(20, 1, 20, 1, 1, 1, 1)
    feint = _keep_check(game, game.execute(Feint("duel_fighter")), "feint_check")
    assert feint.check is not None and feint.check.degree is DegreeOfSuccess.CRITICAL_SUCCESS

    assert _strike_check(game).check.dc == 16
    assert _strike_check(game).check.dc == 16
    assert game.inspect().turn_actor_id == "duel_fighter"
    assert game.execute(EndTurn()).status is ResultStatus.COMPLETED

    assert _strike_check(game).check.dc == 16
    assert game.execute(EndTurn()).status is ResultStatus.COMPLETED
    assert game.execute(EndTurn()).status is ResultStatus.COMPLETED

    assert _strike_check(game).check.dc == 18


def test_critical_failure_reverses_exposure_until_feinter_next_turn_end() -> None:
    game = _ready(20, 1, 1, 1, 1)
    feint = _keep_check(game, game.execute(Feint("duel_fighter")), "feint_check")
    assert feint.check is not None and feint.check.degree is DegreeOfSuccess.CRITICAL_FAILURE
    assert game.execute(EndTurn()).status is ResultStatus.COMPLETED

    exposed = _strike_check(game, target_id="feint_fighter")
    assert exposed.check is not None and exposed.check.dc == 16
    assert game.execute(EndTurn()).status is ResultStatus.COMPLETED
    assert game.execute(EndTurn()).status is ResultStatus.COMPLETED

    expired = _strike_check(game, target_id="feint_fighter")
    assert expired.check is not None and expired.check.dc == 18
