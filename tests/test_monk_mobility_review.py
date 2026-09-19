"""Independent source/play review of selected Monk mobility and kama Trip.

Sources checked 2026-09-16:

* Quick Jump: https://2e.aonprd.com/Feats.aspx?ID=5196
* Long Jump and horizontal Leap: https://2e.aonprd.com/Actions.aspx?ID=2378
* Trip weapon trait: https://2e.aonprd.com/Traits.aspx?ID=716

The selected flat-map contract admits one-action horizontal Quick Jump at DC
15 with 30/15/5/0-foot degree bands capped by Speed. Kama's Trip trait permits
the held weapon to supply the maneuver and allows dropping it to convert a
critical failure to a failure.
"""

from pathlib import Path

import pytest

import pf2e.content as content
from pf2e.encounter import Encounter
from pf2e.model import Choose, CreaturePlacement, EncounterSetup, Position, ResultStatus
from pf2e.ranger_monk_content import MONK
from pf2e.skill_actions import QuickJump, Trip


def _choose(game: Encounter, option_id: str):
    choice = game.inspect().choice
    assert choice is not None
    return game.execute(Choose(choice.choice_id, option_id, choice.owner_actor_id))


def _settle_initiative(game: Encounter) -> None:
    for _ in range(12):
        choice = game.inspect().choice
        if choice is None:
            return
        options = {item.option_id for item in choice.options}
        option_id = "keep" if "keep" in options else choice.options[0].option_id
        assert _choose(game, option_id).status in {ResultStatus.PAUSED, ResultStatus.COMPLETED}
    raise AssertionError("initiative did not settle")


def _jump_setup(monkeypatch: pytest.MonkeyPatch, setup_id: str) -> EncounterSetup:
    setup = EncounterSetup(
        setup_id=setup_id,
        name="Review Monk Quick Jump lane",
        width=8,
        height=3,
        placements=(
            CreaturePlacement("monk", MONK.definition_id, "Monk", "blue", Position(1, 1)),
            CreaturePlacement("dog", "guard_dog_mc2924", "Dog", "red", Position(7, 0)),
        ),
    )
    monkeypatch.setattr(content, "_STAGED_SETUPS", content._STAGED_SETUPS | {setup.setup_id: setup})
    return setup


@pytest.mark.parametrize(
    ("die", "expected_x", "expected_degree", "expected_prone"),
    (
        (20, 6, "CRITICAL_SUCCESS", False),  # 30 feet is capped by Speed 25.
        (10, 4, "SUCCESS", False),
        (5, 2, "FAILURE", False),
        (1, 1, "CRITICAL_FAILURE", True),
    ),
)
def test_quick_jump_degree_distance_action_cost_and_speed_cap(
    monkeypatch: pytest.MonkeyPatch,
    die: int,
    expected_x: int,
    expected_degree: str,
    expected_prone: bool,
) -> None:
    setup = _jump_setup(monkeypatch, f"review_quick_jump_degree_{die}")
    path = tuple(Position(x, 1) for x in range(2, 7))
    game = Encounter.start(setup, rolls=(20, 1, die))
    _settle_initiative(game)
    started = game.execute(QuickJump(path))
    assert started.status is ResultStatus.PAUSED
    finished = _choose(game, "keep")
    check = next(event.check for event in finished.events if event.kind == "quick_jump_check")
    monk = game._state.creatures["monk"]
    assert check is not None and check.dc == 15 and check.degree.name == expected_degree
    assert monk.position == Position(expected_x, 1)
    assert monk.actions_remaining == 2 and monk.prone is expected_prone


def test_saved_accepted_missed_reactive_strike_resumes_quick_jump(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    setup = EncounterSetup(
        setup_id="review_quick_jump_reactive_strike",
        name="Review Quick Jump through Reactive Strike",
        width=7,
        height=6,
        placements=(
            CreaturePlacement("monk", MONK.definition_id, "Monk", "blue", Position(4, 1)),
            CreaturePlacement("fighter", "fighter_m_level_1", "Fighter", "red", Position(5, 1)),
        ),
    )
    monkeypatch.setattr(content, "_STAGED_SETUPS", content._STAGED_SETUPS | {setup.setup_id: setup})
    game = Encounter.start(setup, rolls=(20, 1, 10, 1))
    _settle_initiative(game)
    started = game.execute(QuickJump((Position(4, 2), Position(4, 3), Position(4, 4))))
    assert started.status is ResultStatus.PAUSED
    reaction = _choose(game, "keep")
    assert reaction.inspection.choice is not None and reaction.inspection.choice.kind == "reaction"
    attack = _choose(game, "accept")
    assert attack.inspection.choice is not None and attack.inspection.choice.kind == "attack_hero_reroll"
    path = tmp_path / "quick-jump-reaction-miss.json"
    game.save(path)
    game = Encounter.load(path)

    finished = _choose(game, "keep")
    monk = game._state.creatures["monk"]
    assert finished.status is ResultStatus.COMPLETED
    assert monk.position == Position(4, 4) and monk.actions_remaining == 2
    assert any(
        event.kind == "strike" and event.actor_id == "fighter" and event.check is not None
        and event.check.degree.name in {"FAILURE", "CRITICAL_FAILURE"}
        for event in finished.events
    )


def test_saved_reactive_strike_knockout_interrupts_quick_jump(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    setup = EncounterSetup(
        setup_id="review_quick_jump_reactive_strike_knockout",
        name="Review Quick Jump interrupted by Reactive Strike",
        width=7,
        height=6,
        placements=(
            CreaturePlacement("monk", MONK.definition_id, "Monk", "blue", Position(4, 1)),
            CreaturePlacement("fighter", "fighter_m_level_1", "Fighter", "red", Position(5, 1)),
        ),
    )
    monkeypatch.setattr(content, "_STAGED_SETUPS", content._STAGED_SETUPS | {setup.setup_id: setup})
    game = Encounter.start(setup, rolls=(20, 1, 10, 20, 8))
    _settle_initiative(game)
    game._state.creatures["monk"].hp = 1
    assert game.execute(
        QuickJump((Position(4, 2), Position(4, 3), Position(4, 4)))
    ).status is ResultStatus.PAUSED
    assert _choose(game, "keep").inspection.choice.kind == "reaction"
    assert _choose(game, "accept").inspection.choice.kind == "attack_hero_reroll"
    health = _choose(game, "keep")
    assert health.inspection.choice is not None
    assert health.inspection.choice.kind == "heroic_recovery_damage"
    path = tmp_path / "quick-jump-reaction-knockout.json"
    game.save(path)
    game = Encounter.load(path)

    stopped = _choose(game, "normal")
    monk = game._state.creatures["monk"]
    assert stopped.status is ResultStatus.COMPLETED
    assert monk.unconscious and monk.dying > 0
    assert monk.position != Position(4, 4)
    assert game.inspect().choice is None


def test_invalid_quick_jump_and_unheld_kama_trip_are_atomic(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    game = Encounter.start(content.get_setup("staged_monk_kama_flurry"), rolls=(20, 1, 1))
    _settle_initiative(game)
    for command in (
        QuickJump((Position(2, 2),)),
        QuickJump(tuple(Position(x, 1) for x in range(2, 8))),
        Trip("guard_dog_a", maneuver_item_id="not-the-kama"),
    ):
        before, dice_before = game.inspect(), game._dice.to_data()
        rejected = game.execute(command)
        assert rejected.status is ResultStatus.REJECTED
        assert game.inspect() == before and game._dice.to_data() == dice_before


def test_saved_kama_trip_drop_preserves_exact_item_identity(
    tmp_path: Path,
) -> None:
    game = Encounter.start(
        content.get_setup("staged_monk_kama_flurry"),
        rolls=(20, 1, 1, 1),
    )
    _settle_initiative(game)
    started = game.execute(Trip("guard_dog_a", maneuver_item_id="kama"))
    assert started.status is ResultStatus.PAUSED
    failed = _choose(game, "keep")
    assert failed.inspection.choice is not None and failed.inspection.choice.kind == "family_action"
    path = tmp_path / "kama-trip-drop.json"
    game.save(path)
    game = Encounter.load(path)

    dropped = _choose(game, "drop_weapon")
    monk = game._state.creatures["monk"]
    ground = game._state.ground_items.get(monk.position, [])
    assert dropped.status is ResultStatus.COMPLETED
    assert monk.held_items == [] and not monk.prone and monk.actions_remaining == 2
    assert ground == ["kama"]
    assert any(event.kind == "release" for event in dropped.events)

    before, dice_before = game.inspect(), game._dice.to_data()
    rejected = game.execute(Trip("guard_dog_a", maneuver_item_id="kama"))
    assert rejected.status is ResultStatus.REJECTED
    assert game.inspect() == before and game._dice.to_data() == dice_before
