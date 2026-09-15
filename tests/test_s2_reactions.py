"""Public-command coverage for S2 Reactive Strike continuations."""

from pathlib import Path

from pf2e.content import S2_PACK_ATTACK_SETUP, S2_PC_DUEL_SETUP
from pf2e.encounter import Encounter
from pf2e.model import EndTurn, Interact, Position, ResultStatus, Release, Step, Strike, Stride


def _keep_initiative(game: Encounter) -> None:
    while game.inspect().choice is not None:
        choice = game.inspect().choice
        assert choice is not None
        assert choice.kind == "initiative_hero_reroll"
        result = game.choose(choice.choice_id, "keep")
        assert result.status in (ResultStatus.PAUSED, ResultStatus.COMPLETED)


def _actor(game: Encounter, actor_id: str):
    return next(actor for actor in game.inspect().actors if actor.actor_id == actor_id)


def test_saved_declined_movement_reaction_is_once_per_action_and_later_fires(tmp_path: Path) -> None:
    game = Encounter.start(S2_PC_DUEL_SETUP, rolls=(20, 19, 1, 10, 1))
    _keep_initiative(game)

    # Leave two reachable squares during one Stride. The first prompt is
    # saved; declining retains the reaction but not a second prompt during
    # this same move action.
    movement = game.execute(Stride((Position(4, 2), Position(4, 1))))
    assert movement.status is ResultStatus.PAUSED
    reaction = movement.inspection.choice
    assert reaction is not None and reaction.kind == "reaction"
    assert reaction.owner_actor_id == "fighter_b"

    save_path = tmp_path / "movement-reaction.json"
    game.save(save_path)
    restored = Encounter.load(save_path)
    assert restored.inspect() == movement.inspection
    declined = restored.choose(reaction.choice_id, "decline")
    assert declined.status is ResultStatus.COMPLETED
    assert sum(event.kind == "reaction_declined" for event in declined.events) == 1
    assert _actor(restored, "fighter_b").reaction_available
    assert _actor(restored, "fighter_a").position == Position(4, 1)

    # The declined reaction survives its owner's turn and triggers on a later
    # enemy move. The original mover's own reaction likewise remains available
    # after its turn, so it can act as the later reactor.
    assert restored.inspect().turn_actor_id == "fighter_a"
    assert restored.execute(EndTurn()).status is ResultStatus.COMPLETED
    assert restored.inspect().turn_actor_id == "fighter_b"
    later_move = restored.execute(Stride((Position(6, 1),)))
    assert later_move.status is ResultStatus.PAUSED
    later_choice = later_move.inspection.choice
    assert later_choice is not None and later_choice.kind == "reaction"
    assert later_choice.owner_actor_id == "fighter_a"

    # The reaction uses MAP 0 and does not count as one of Fighter A's attacks.
    reaction_check = restored.choose(later_choice.choice_id, "accept")
    assert reaction_check.status is ResultStatus.PAUSED
    hero_choice = reaction_check.inspection.choice
    assert hero_choice is not None and hero_choice.kind == "attack_hero_reroll"
    kept = restored.choose(hero_choice.choice_id, "keep")
    reaction_event = next(event for event in kept.events if event.check is not None)
    assert reaction_event.check is not None
    assert reaction_event.check.map_penalty == 0
    assert _actor(restored, "fighter_b").position == Position(6, 1)
    assert restored.inspect().turn_actor_id == "fighter_b"
    assert restored.execute(EndTurn()).status is ResultStatus.COMPLETED
    assert restored.inspect().turn_actor_id == "fighter_a"
    assert restored.execute(Stride((Position(5, 1),))).status is ResultStatus.COMPLETED

    own_turn_attack = restored.execute(
        Strike("fighter_b")
    )
    assert own_turn_attack.status is ResultStatus.PAUSED
    own_choice = own_turn_attack.inspection.choice
    assert own_choice is not None and own_choice.kind == "attack_hero_reroll"
    result = restored.choose(own_choice.choice_id, "keep")
    own_check = next(event.check for event in result.events if event.check is not None)
    assert own_check is not None and own_check.map_penalty == 0


def test_critical_reactive_strike_disrupts_manipulate_but_keeps_paid_cost() -> None:
    game = Encounter.start(S2_PC_DUEL_SETUP, rolls=(20, 19, 20, 1))
    _keep_initiative(game)
    paused = game.execute(Interact("stow", "longsword"))
    assert paused.status is ResultStatus.PAUSED
    choice = paused.inspection.choice
    assert choice is not None and choice.kind == "reaction"
    assert choice.owner_actor_id == "fighter_b"
    reaction = game.choose(choice.choice_id, "accept")
    assert reaction.status is ResultStatus.PAUSED
    hero_choice = reaction.inspection.choice
    assert hero_choice is not None and hero_choice.kind == "attack_hero_reroll"
    result = game.choose(hero_choice.choice_id, "keep")
    assert result.status is ResultStatus.COMPLETED
    assert any(event.kind == "disrupted" for event in result.events)
    assert _actor(game, "fighter_a").held_items == ("longsword",)
    assert _actor(game, "fighter_a").actions_remaining == 2
    assert not _actor(game, "fighter_b").reaction_available
    assert _actor(game, "fighter_a").hp == 11


def test_reaction_choice_preserves_attack_and_intent_alternatives_after_load(tmp_path: Path) -> None:
    game = Encounter.start(S2_PC_DUEL_SETUP, rolls=(20, 19, 10, 2))
    _keep_initiative(game)
    movement = game.execute(Stride((Position(4, 2),)))
    choice = movement.inspection.choice
    assert choice is not None and choice.kind == "reaction"
    option_ids = {option.option_id for option in choice.options}
    assert "accept" in option_ids
    assert "strike:fist:bludgeoning:nonlethal" in option_ids
    assert "strike:longsword:slashing:nonlethal" in option_ids
    assert "decline" in option_ids

    path = tmp_path / "reaction-alternatives.json"
    game.save(path)
    restored = Encounter.load(path)
    assert restored.inspect() == movement.inspection
    selected = restored.choose(choice.choice_id, "strike:fist:bludgeoning:nonlethal")
    hero = selected.inspection.choice
    assert hero is not None and hero.kind == "attack_hero_reroll"
    strike_event = next(event for event in selected.events if event.check is not None)
    assert strike_event.check is not None
    assert strike_event.check.attack_id == "fist"
    assert strike_event.check.modifier == 9
    completed = restored.choose(hero.choice_id, "keep")
    assert completed.status is ResultStatus.COMPLETED
    assert any(event.damage is not None and event.damage.components[0].damage_type == "bludgeoning" for event in completed.events)
    assert _actor(restored, "fighter_b").reaction_available is False


def test_step_and_release_do_not_trigger_reactive_strike() -> None:
    game = Encounter.start(S2_PC_DUEL_SETUP, rolls=(20, 19))
    _keep_initiative(game)
    released = game.execute(Release("longsword"))
    assert released.status is ResultStatus.COMPLETED
    assert released.inspection.choice is None
    assert _actor(game, "fighter_b").reaction_available
    assert released.inspection.ground_items == ((Position(4, 1), ("longsword",)),)

    step = game.execute(Step(Position(3, 1)))
    assert step.status is ResultStatus.COMPLETED
    assert step.inspection.choice is None
    assert _actor(game, "fighter_b").reaction_available


def test_stowed_weapon_round_trips_and_can_be_drawn_after_load(tmp_path: Path) -> None:
    game = Encounter.start(S2_PC_DUEL_SETUP, rolls=(20, 19))
    _keep_initiative(game)
    stow = game.execute(Interact("stow", "longsword"))
    choice = stow.inspection.choice
    assert choice is not None and choice.kind == "reaction"
    declined = game.choose(choice.choice_id, "decline")
    actor = _actor(game, "fighter_a")
    assert actor.held_items == () and actor.stowed_items == ("longsword",)
    assert actor.worn_items == ("breastplate",)

    path = tmp_path / "stowed-sword.json"
    game.save(path)
    restored = Encounter.load(path)
    assert restored.inspect() == declined.inspection
    assert ("draw", "longsword") in restored.options().interact_options
    draw = restored.execute(Interact("draw", "longsword"))
    choice = draw.inspection.choice
    assert choice is not None and choice.kind == "reaction"
    restored.choose(choice.choice_id, "decline")
    actor = _actor(restored, "fighter_a")
    assert actor.held_items == ("longsword",) and actor.stowed_items == ()
    assert actor.worn_items == ("breastplate",)


def test_speed_30_stride_with_four_diagonals_round_trips(tmp_path: Path) -> None:
    # With the fixed initiative faces Dog B acts first. Its four diagonal
    # transitions cost 5 + 10 + 5 + 10 feet, the Guard Dog's full 30-foot
    # Speed. The adjacent fighter may react before the first step.
    game = Encounter.start(S2_PACK_ATTACK_SETUP, rolls=(1, 2, 20, 3))
    _keep_initiative(game)
    assert game.inspect().turn_actor_id == "guard_dog_b"

    movement = game.execute(
        Stride((Position(3, 0), Position(4, 1), Position(5, 0), Position(6, 1)))
    )
    assert movement.status is ResultStatus.PAUSED
    reaction = movement.inspection.choice
    assert reaction is not None and reaction.kind == "reaction"
    assert game.choose(reaction.choice_id, "decline").status is ResultStatus.COMPLETED
    assert _actor(game, "guard_dog_b").position == Position(6, 1)
    assert _actor(game, "guard_dog_b").diagonals_this_turn == 4

    save_path = tmp_path / "speed-30-four-diagonals.json"
    game.save(save_path)
    restored = Encounter.load(save_path)
    assert restored.inspect() == game.inspect()
    assert _actor(restored, "guard_dog_b").diagonals_this_turn == 4
