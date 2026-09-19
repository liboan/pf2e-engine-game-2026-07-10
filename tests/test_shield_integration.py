"""Public Steel Shield encounter behavior and persisted Shield Block choices."""

from pathlib import Path

import pytest

from pf2e import (
    EndTurn,
    Encounter,
    Interact,
    Position,
    RaiseShield,
    Release,
    ResultStatus,
    Stride,
    Strike,
)
from pf2e.content import get_setup


SETUP = get_setup("steel_shield_test")
SHIELD_ID = "shield_fighter:steel_shield"


def _started(*, rolls: tuple[int, ...]) -> Encounter:
    game = Encounter.start(SETUP, rolls=rolls)
    while (choice := game.inspect().choice) is not None:
        assert choice.kind == "initiative_hero_reroll"
        game.choose(choice.choice_id, "keep")
    assert game.inspect().turn_actor_id == "shield_fighter"
    return game


def _to_guard_dog(game: Encounter, *, raise_shield: bool = True) -> None:
    if raise_shield:
        result = game.execute(RaiseShield())
        assert result.status is ResultStatus.COMPLETED
    game.execute(EndTurn())
    assert game.inspect().turn_actor_id == "guard_dog"


def _actor(game: Encounter, actor_id: str):
    return next(actor for actor in game.inspect().actors if actor.actor_id == actor_id)


def _dog_attack(game: Encounter):
    return game.execute(Strike("shield_fighter", attack_id="jaws"))


def test_raising_changes_real_attack_outcome_and_expires_at_next_turn_start() -> None:
    rolls = (20, 1, 5, 12, 4)
    raised = _started(rolls=rolls)
    _to_guard_dog(raised)
    raised_attack = _dog_attack(raised)
    assert raised_attack.status is ResultStatus.COMPLETED
    raised_check = next(event.check for event in raised_attack.events if event.check is not None)
    assert raised_check is not None and raised_check.dc == 20
    assert raised_check.degree.name == "FAILURE"
    assert not any(event.damage is not None for event in raised_attack.events)

    unraised = _started(rolls=rolls)
    _to_guard_dog(unraised, raise_shield=False)
    unraised_attack = _dog_attack(unraised)
    unraised_check = next(event.check for event in unraised_attack.events if event.check is not None)
    assert unraised_check is not None and unraised_check.dc == 18
    assert unraised_check.degree.name == "SUCCESS"
    assert any(event.damage is not None for event in unraised_attack.events)

    # Finish the dog and ally turns. The owner's next turn start ends Raise a Shield.
    raised.execute(EndTurn())
    raised.execute(EndTurn())
    assert raised.inspect().turn_actor_id == "shield_fighter"
    shield = _actor(raised, "shield_fighter").shields[0]
    assert not shield.raised and not shield.ac_bonus_active
    assert _actor(raised, "shield_fighter").ac == 18


@pytest.mark.parametrize("option", ["block", "decline"])
def test_shield_block_choice_saves_and_resumes_without_reroll_or_double_spend(
    tmp_path: Path, option: str
) -> None:
    rolls = (20, 1, 5, 20, 4)
    uninterrupted = _started(rolls=rolls)
    _to_guard_dog(uninterrupted)
    uninterrupted_choice = _dog_attack(uninterrupted).inspection.choice
    assert uninterrupted_choice is not None and uninterrupted_choice.kind == "shield_block"

    game = _started(rolls=rolls)
    _to_guard_dog(game)
    paused = _dog_attack(game)
    choice = paused.inspection.choice
    assert paused.status is ResultStatus.PAUSED
    assert choice is not None and choice.kind == "shield_block"
    assert [item.option_id for item in choice.options] == ["block", "decline"]
    assert _actor(game, "shield_fighter").hp == 21
    assert _actor(game, "shield_fighter").hero_points == 1

    path = tmp_path / f"shield-{option}.json"
    game.save(path)
    restored = Encounter.load(path)
    saved_choice = restored.inspect().choice
    assert saved_choice is not None and saved_choice.kind == "shield_block"
    result = restored.choose(saved_choice.choice_id, option)
    uninterrupted_result = uninterrupted.choose(uninterrupted_choice.choice_id, option)
    assert result.status is ResultStatus.COMPLETED
    assert result.events == uninterrupted_result.events
    assert _actor(restored, "shield_fighter") == _actor(uninterrupted, "shield_fighter")

    fighter = _actor(restored, "shield_fighter")
    if option == "block":
        assert fighter.hp == 16
        assert fighter.hero_points == 1
        assert not fighter.reaction_available
        assert fighter.shields[0].hp == 15
        damage_event = next(event for event in result.events if event.damage is not None)
        assert damage_event.shield_block is not None
        assert damage_event.shield_block.damage_to_actor == 5
        assert damage_event.shield_block.damage_to_shield == 5
        assert damage_event.original_damage is not None
        assert damage_event.original_damage.total == 10
    else:
        assert fighter.hp == 11
        assert fighter.hero_points == 1
        assert fighter.reaction_available
        assert fighter.shields[0].hp == 20
        assert not any(event.shield_block is not None for event in result.events)


def test_block_spends_reactive_strike_reaction_and_shield_breaks_at_threshold() -> None:
    game = _started(rolls=(20, 1, 5, 20, 4, 20, 4, 1))
    _to_guard_dog(game)
    pending = _dog_attack(game)
    choice = pending.inspection.choice
    assert choice is not None and choice.kind == "shield_block"
    game.choose(choice.choice_id, "block")
    assert not _actor(game, "shield_fighter").reaction_available

    # The dog leaves the fighter's reach; the spent shared reaction cannot trigger Reactive Strike.
    movement = game.execute(Stride((Position(3, 1),)))
    assert movement.status is ResultStatus.COMPLETED
    assert movement.inspection.choice is None

    game.execute(EndTurn())
    game.execute(EndTurn())
    assert game.inspect().turn_actor_id == "shield_fighter"
    game.execute(RaiseShield())
    game.execute(EndTurn())
    assert game.inspect().turn_actor_id == "guard_dog"
    game.execute(Stride((Position(2, 1),)))
    next_pending = _dog_attack(game)
    next_choice = next_pending.inspection.choice
    assert next_choice is not None and next_choice.kind == "shield_block"
    game.choose(next_choice.choice_id, "block")
    shield = _actor(game, "shield_fighter").shields[0]
    assert shield.hp == 10
    assert shield.broken
    assert not shield.raised and not shield.ac_bonus_active
    assert _actor(game, "shield_fighter").ac == 18

    # Broken shields no longer offer the physical-attack reaction.
    miss = _dog_attack(game)
    assert miss.inspection.choice is None
    assert not any(event.kind == "shield_block" for event in miss.events)


def test_dropped_and_retrieved_shield_keeps_instance_and_damage(tmp_path: Path) -> None:
    game = _started(rolls=(20, 1, 5, 20, 4))
    _to_guard_dog(game)
    choice = _dog_attack(game).inspection.choice
    assert choice is not None and choice.kind == "shield_block"
    game.choose(choice.choice_id, "block")
    assert _actor(game, "shield_fighter").shields[0].hp == 15

    game.execute(EndTurn())
    game.execute(EndTurn())
    assert game.inspect().turn_actor_id == "shield_fighter"
    released = game.execute(Release(SHIELD_ID))
    assert released.status is ResultStatus.COMPLETED
    assert not _actor(game, "shield_fighter").shields
    retrieved = game.execute(Interact("retrieve", SHIELD_ID))
    assert retrieved.status is ResultStatus.COMPLETED
    shield = _actor(game, "shield_fighter").shields[0]
    assert shield.instance_id == SHIELD_ID
    assert shield.hp == 15
    assert not shield.raised and not shield.ac_bonus_active
    path = tmp_path / "retrieved-shield.json"
    game.save(path)
    restored = Encounter.load(path)
    shield = _actor(restored, "shield_fighter").shields[0]
    assert shield.instance_id == SHIELD_ID
    assert shield.hp == 15


def test_saved_real_shield_block_can_finish_the_healthy_encounter(tmp_path: Path) -> None:
    game = _started(rolls=(20, 1, 5, 20, 4, 20, 8, 8))
    _to_guard_dog(game)
    pending = _dog_attack(game)
    choice = pending.inspection.choice
    assert choice is not None and choice.kind == "shield_block"

    path = tmp_path / "shield-block-fight.json"
    game.save(path)
    game = Encounter.load(path)
    restored_choice = game.inspect().choice
    assert restored_choice is not None and restored_choice.kind == "shield_block"
    game.choose(restored_choice.choice_id, "block")

    game.execute(EndTurn())
    assert game.inspect().turn_actor_id == "fighter_ally"
    game.execute(Stride((Position(1, 2),)))
    attack = game.execute(Strike("guard_dog", attack_id="longsword"))
    hero_choice = attack.inspection.choice
    assert hero_choice is not None and hero_choice.kind == "attack_hero_reroll"
    finished = game.choose(hero_choice.choice_id, "keep")
    assert finished.status is ResultStatus.COMPLETED
    assert not finished.inspection.in_progress
    assert finished.inspection.winner_team == "blue"
    assert _actor(game, "guard_dog").dead
    assert _actor(game, "shield_fighter").shields[0].hp == 15


def test_applied_block_record_survives_save_at_heroic_health_choice(tmp_path: Path) -> None:
    rolls = (20, 1, 5, 20, 4, 1, 20, 4, 19, 4, 20, 4)
    game = _started(rolls=rolls)

    # First turn: take one critical hit without raising, then let a miss consume
    # the dog's second Strike so the fighter survives to raise their shield.
    game.execute(EndTurn())
    assert game.inspect().turn_actor_id == "guard_dog"
    assert _dog_attack(game).status is ResultStatus.COMPLETED
    assert _actor(game, "shield_fighter").hp == 11
    assert _dog_attack(game).status is ResultStatus.COMPLETED
    game.execute(EndTurn())
    game.execute(EndTurn())

    # The next critical is Blocked; a normal second hit leaves the PC at 1 HP.
    game.execute(RaiseShield())
    game.execute(EndTurn())
    first_block = _dog_attack(game).inspection.choice
    assert first_block is not None and first_block.kind == "shield_block"
    game.choose(first_block.choice_id, "block")
    second_hit = _dog_attack(game)
    assert second_hit.inspection.choice is None
    assert _actor(game, "shield_fighter").hp == 1
    game.execute(EndTurn())
    game.execute(EndTurn())

    # The final Block breaks the shield and creates the ordinary Heroic
    # Recovery decision. Save/load validates its retained damage and Block data.
    game.execute(RaiseShield())
    game.execute(EndTurn())
    last_block = _dog_attack(game).inspection.choice
    assert last_block is not None and last_block.kind == "shield_block"
    paused = game.choose(last_block.choice_id, "block")
    health_choice = paused.inspection.choice
    assert health_choice is not None and health_choice.kind == "heroic_recovery_damage"

    path = tmp_path / "blocked-health-choice.json"
    game.save(path)
    restored = Encounter.load(path)
    restored_choice = restored.inspect().choice
    assert restored_choice is not None and restored_choice.kind == "heroic_recovery_damage"
    finished = restored.choose(restored_choice.choice_id, "normal")
    damage_event = next(event for event in finished.events if event.damage is not None)
    assert damage_event.shield_block is not None
    assert damage_event.shield_block.shield_hp_after == 10
    assert _actor(restored, "shield_fighter").dying == 2
