"""Complete public-engine regressions for the S2 interaction encounters."""

from pathlib import Path

from interaction_helpers import EncounterHarness
from pf2e.content import get_setup
from pf2e.encounter import Encounter
from pf2e.model import (
    EndTurn,
    Interact,
    Position,
    Release,
    ResultStatus,
    Strike,
    Stride,
    ViciousSwing,
)


def _encounter(setup_id: str, rolls: tuple[int, ...]) -> EncounterHarness:
    return EncounterHarness(
        Encounter.start(get_setup(setup_id), rolls=rolls),
        setup_id,
    )


def test_s2_reaction_relay_saves_nested_choices_and_completes_fight(tmp_path: Path) -> None:
    harness = _encounter(
        "s2_reaction_relay",
        (20, 19, 18, 17, 1, 1, 20, 6, 6, 20, 1, 1),
    )
    harness.keep_initiative()
    assert harness.inspection.turn_actor_id == "fleet_fighter"
    reaction_choices_before = harness.choices

    harness.end_turn(expected_actor_id="fighter_m")
    harness.end_turn(expected_actor_id="fighter_foe")
    movement = harness.command(
        Stride((Position(4, 2), Position(5, 2))),
        expected_status=ResultStatus.PAUSED,
    )
    first_reaction = harness.pending_choice(
        kind="reaction", owner_actor_id="fleet_fighter", options=("decline",)
    )
    harness.checkpoint(tmp_path / "relay-first-reaction.json")

    declined = harness.choose(
        kind="reaction",
        owner_actor_id="fleet_fighter",
        option_id="decline",
        expected_status=ResultStatus.PAUSED,
    )
    assert sum(event.kind == "reaction_declined" for event in declined.events) == 1
    second_reaction = harness.pending_choice(
        kind="reaction", owner_actor_id="fighter_m", options=("accept",)
    )
    assert second_reaction.choice_id != first_reaction.choice_id

    accepted = harness.choose(
        kind="reaction",
        owner_actor_id="fighter_m",
        option_id="accept",
        expected_status=ResultStatus.PAUSED,
    )
    strike_check = next(event.check for event in accepted.events if event.check is not None)
    assert strike_check is not None
    assert strike_check.map_penalty == 0
    hero_choice = harness.pending_choice(
        kind="attack_hero_reroll", owner_actor_id="fighter_m", options=("keep",)
    )
    harness.checkpoint(tmp_path / "relay-nested-hero-choice.json")

    completed_move = harness.choose(
        kind="attack_hero_reroll",
        owner_actor_id="fighter_m",
        option_id="keep",
    )
    assert completed_move.status is ResultStatus.COMPLETED
    assert completed_move.inspection.choice is None
    assert harness.actor("fighter_foe").position == Position(5, 2)
    assert harness.actor("fighter_foe").actions_remaining == 2
    assert harness.actor("fleet_fighter").reaction_available
    assert not harness.actor("fighter_m").reaction_available
    # Two distinct reactors were offered once each; neither reappears for the
    # second square of the same Stride after declining or accepting.
    assert harness.choices - reaction_choices_before == 3

    harness.end_turn(expected_actor_id="guard_dog")
    harness.command(Stride((Position(5, 4), Position(4, 3), Position(3, 3))))
    dog_attack = harness.command(Strike("fighter_m", attack_id="jaws"))
    assert not any(event.damage is not None for event in dog_attack.events)
    harness.end_turn(expected_actor_id="fleet_fighter")

    harness.command(Stride((Position(3, 1), Position(4, 1))))
    swing = harness.command(
        ViciousSwing("fighter_foe", attack_id="shortsword"),
        expected_status=ResultStatus.PAUSED,
    )
    assert harness.pending_choice(
        kind="attack_hero_reroll", owner_actor_id="fleet_fighter", options=("keep",)
    )
    swing_result = harness.choose(
        kind="attack_hero_reroll",
        owner_actor_id="fleet_fighter",
        option_id="keep",
        expected_status=ResultStatus.PAUSED,
    )
    assert harness.pending_choice(
        kind="heroic_recovery_damage", owner_actor_id="fighter_foe", options=("normal",)
    )
    recovery = harness.choose(
        kind="heroic_recovery_damage", owner_actor_id="fighter_foe", option_id="normal"
    )
    assert any(event.damage is not None for event in recovery.events)
    unconscious_foe = harness.actor("fighter_foe")
    assert (unconscious_foe.hp, unconscious_foe.dying) == (0, 2)
    assert unconscious_foe.unconscious and not unconscious_foe.dead
    assert harness.inspection.turn_actor_id == "fighter_m"
    final_strike = harness.command(
        Strike("guard_dog", attack_id="longsword"),
        expected_status=ResultStatus.PAUSED,
    )
    assert harness.pending_choice(
        kind="attack_hero_reroll", owner_actor_id="fighter_m", options=("keep",)
    )
    final_result = harness.choose(
        kind="attack_hero_reroll",
        owner_actor_id="fighter_m",
        option_id="keep",
    )
    assert final_strike.inspection.in_progress
    assert any(event.damage is not None for event in final_result.events)
    assert harness.actor("guard_dog").dead
    harness.assert_ended()
    assert harness.inspection.winner_team == "blue"
    assert harness.actor("guard_dog").defeated


def test_s2_contested_weapon_swap_disrupts_then_releases_safely(tmp_path: Path) -> None:
    harness = _encounter(
        "s2_contested_weapon_swap",
        (20, 19, 18, 17, 20, 1, 20, 1, 20, 8, 8),
    )
    harness.keep_initiative()
    assert harness.inspection.turn_actor_id == "fleet_fighter"
    assert harness.actor("fleet_fighter").held_items == ("shortsword",)
    assert "longsword" in harness.actor("fleet_fighter").worn_items

    disrupted_interact = harness.command(
        Interact("stow", "shortsword"), expected_status=ResultStatus.PAUSED
    )
    assert harness.pending_choice(
        kind="reaction", owner_actor_id="fighter_foe", options=("accept",)
    )
    paid_actor = harness.actor("fleet_fighter")
    assert paid_actor.actions_remaining == 2
    assert paid_actor.held_items == ("shortsword",)
    assert "shortsword" not in paid_actor.stowed_items

    reaction = harness.choose(
        kind="reaction",
        owner_actor_id="fighter_foe",
        option_id="accept",
        expected_status=ResultStatus.PAUSED,
    )
    reaction_check = next(event.check for event in reaction.events if event.check is not None)
    assert reaction_check is not None and reaction_check.map_penalty == 0
    harness.pending_choice(
        kind="attack_hero_reroll", owner_actor_id="fighter_foe", options=("keep",)
    )
    harness.checkpoint(tmp_path / "weapon-swap-critical-reaction.json")
    interrupted = harness.choose(
        kind="attack_hero_reroll", owner_actor_id="fighter_foe", option_id="keep"
    )
    assert any(event.kind == "disrupted" for event in interrupted.events)
    assert harness.actor("fleet_fighter").actions_remaining == 2
    assert harness.actor("fleet_fighter").held_items == ("shortsword",)
    assert harness.actor("fleet_fighter").stowed_items == ()
    assert harness.inspection.ground_items == ()
    assert not harness.actor("fighter_foe").reaction_available

    retried = harness.command(Interact("stow", "shortsword"))
    assert retried.status is ResultStatus.COMPLETED
    assert retried.inspection.choice is None
    assert harness.actor("fleet_fighter").held_items == ()
    assert harness.actor("fleet_fighter").stowed_items == ("shortsword",)
    assert harness.actor("fleet_fighter").actions_remaining == 1
    harness.command(Interact("draw", "longsword"))
    assert harness.actor("fleet_fighter").held_items == ("longsword",)
    assert harness.inspection.turn_actor_id == "fighter_m"

    harness.command(Stride((Position(1, 4), Position(2, 4), Position(3, 4), Position(4, 4))))
    dog_strike = harness.command(
        Strike("guard_dog", attack_id="longsword"),
        expected_status=ResultStatus.PAUSED,
    )
    harness.pending_choice(
        kind="attack_hero_reroll", owner_actor_id="fighter_m", options=("keep",)
    )
    harness.choose(
        kind="attack_hero_reroll", owner_actor_id="fighter_m", option_id="keep"
    )
    assert dog_strike.inspection.in_progress
    assert harness.actor("guard_dog").dead
    assert harness.inspection.turn_actor_id == "fighter_m"
    harness.end_turn(expected_actor_id="fighter_foe")

    assert harness.actor("fighter_foe").reaction_available
    assert harness.actor("fleet_fighter").reaction_available
    released = harness.command(Release("longsword"))
    assert released.status is ResultStatus.COMPLETED
    assert released.inspection.choice is None
    assert harness.actor("fighter_foe").reaction_available
    assert harness.actor("fleet_fighter").reaction_available
    assert (Position(3, 2), ("longsword",)) in harness.inspection.ground_items
    assert not any(event.kind.startswith("reaction_") for event in released.events)
    harness.end_turn(expected_actor_id="fleet_fighter")

    swing = harness.command(
        ViciousSwing("fighter_foe", attack_id="longsword"),
        expected_status=ResultStatus.PAUSED,
    )
    harness.pending_choice(
        kind="attack_hero_reroll", owner_actor_id="fleet_fighter", options=("keep",)
    )
    swing_result = harness.choose(
        kind="attack_hero_reroll",
        owner_actor_id="fleet_fighter",
        option_id="keep",
        expected_status=ResultStatus.PAUSED,
    )
    assert harness.pending_choice(
        kind="heroic_recovery_damage", owner_actor_id="fighter_foe", options=("normal",)
    )
    recovered = harness.choose(
        kind="heroic_recovery_damage", owner_actor_id="fighter_foe", option_id="normal"
    )
    assert any(event.damage is not None for event in recovered.events)
    foe = harness.actor("fighter_foe")
    assert (foe.hp, foe.dying) == (0, 2)
    assert foe.unconscious and not foe.dead
    assert swing.inspection.in_progress and swing_result.inspection.choice is not None
    harness.assert_ended()
    assert harness.inspection.winner_team == "blue"
    assert harness.actor("guard_dog").dead


def test_s2_nonlethal_passage_moves_through_knocked_out_dog(tmp_path: Path) -> None:
    harness = _encounter(
        "s2_nonlethal_passage",
        (20, 19, 10, 1, 20, 1, 20, 6),
    )
    harness.keep_initiative()
    assert harness.inspection.turn_actor_id == "fleet_fighter"

    knockout = harness.command(
        Strike("guard_dog", attack_id="fist"),
        expected_status=ResultStatus.PAUSED,
    )
    harness.pending_choice(
        kind="attack_hero_reroll", owner_actor_id="fleet_fighter", options=("keep",)
    )
    knocked_out = harness.choose(
        kind="attack_hero_reroll", owner_actor_id="fleet_fighter", option_id="keep"
    )
    dog = harness.actor("guard_dog")
    assert (dog.hp, dog.dead, dog.defeated) == (0, False, True)
    assert dog.unconscious and dog.prone
    assert any(event.damage is not None for event in knocked_out.events)
    harness.checkpoint(tmp_path / "nonlethal-passage-dog-down.json")

    moved_past = harness.command(
        Stride(
            (
                Position(2, 2),
                Position(3, 2),
                Position(4, 2),
                Position(5, 2),
            )
        )
    )
    assert moved_past.status is ResultStatus.COMPLETED
    assert harness.actor("fleet_fighter").position == Position(5, 2)
    assert harness.actor("guard_dog").position == Position(2, 2)
    assert harness.actor("guard_dog").unconscious and harness.actor("guard_dog").prone

    lethal_strike = harness.command(
        Strike("elite_dog", attack_id="shortsword"),
        expected_status=ResultStatus.PAUSED,
    )
    harness.pending_choice(
        kind="attack_hero_reroll", owner_actor_id="fleet_fighter", options=("keep",)
    )
    lethal_result = harness.choose(
        kind="attack_hero_reroll", owner_actor_id="fleet_fighter", option_id="keep"
    )
    check = next(event.check for event in lethal_result.events if event.check is not None)
    damage = next(event.damage for event in lethal_result.events if event.damage is not None)
    assert check is not None and (check.attack_count, check.map_penalty) == (2, -4)
    assert damage is not None and damage.total == 20
    assert harness.actor("elite_dog").hp == 0 and harness.actor("elite_dog").dead
    assert not harness.actor("elite_dog").unconscious
    assert harness.actor("guard_dog").unconscious and not harness.actor("guard_dog").dead
    harness.assert_ended()
    assert harness.inspection.winner_team == "blue"


def test_s2_heroic_last_stand_stabilizes_fighter_and_finishes_fight(
    tmp_path: Path,
) -> None:
    harness = _encounter(
        "s2_heroic_last_stand",
        (
            5, 2, 20, 19, 20, 4, 20, 4,
            15, 1, 1, 14, 2, 12, 2, 16,
            2, 14, 2, 14, 2, 14, 2, 10, 1,
        ),
    )
    harness.keep_initiative()
    assert harness.inspection.turn_actor_id == "elite_dog"
    assert tuple(actor.actor_id for actor in harness.inspection.actors) == (
        "elite_dog",
        "guard_dog",
        "fighter_target",
        "fleet_fighter",
    )
    target = harness.actor("fighter_target")
    assert (target.hp, target.max_hp, target.hero_points) == (21, 21, 1)
    assert harness.actor("fleet_fighter").initiative < target.initiative

    elite_hit = harness.command(Strike("fighter_target", attack_id="jaws"))
    elite_check = next(event.check for event in elite_hit.events if event.check is not None)
    elite_damage = next(event.damage for event in elite_hit.events if event.damage is not None)
    assert elite_check is not None and elite_check.degree == 3
    assert elite_damage is not None and elite_damage.total == 14
    assert harness.actor("fighter_target").hp == 7
    harness.end_turn(expected_actor_id="guard_dog")

    harness.command(Stride((Position(3, 3),)))
    knockout = harness.command(
        Strike("fighter_target", attack_id="jaws"),
        expected_status=ResultStatus.PAUSED,
    )
    knockout_check = next(event.check for event in knockout.events if event.check is not None)
    assert knockout_check is not None and knockout_check.degree == 3
    harness.pending_choice(
        kind="heroic_recovery_damage",
        owner_actor_id="fighter_target",
        options=("normal", "heroic_recovery"),
    )
    assert harness.actor("fighter_target").hp == 7
    harness.checkpoint(tmp_path / "heroic-last-stand-damage-choice.json")

    recovery = harness.choose(
        kind="heroic_recovery_damage",
        owner_actor_id="fighter_target",
        option_id="heroic_recovery",
    )
    assert any(event.damage is not None for event in recovery.events)
    stabilized = harness.actor("fighter_target")
    assert (
        stabilized.hp,
        stabilized.dying,
        stabilized.wounded,
        stabilized.hero_points,
        stabilized.unconscious,
        stabilized.prone,
    ) == (0, 0, 0, 0, True, True)
    assert stabilized.held_items == ()
    assert (Position(2, 2), ("longsword",)) in harness.inspection.ground_items
    assert harness.inspection.turn_actor_id == "guard_dog"
    assert tuple(actor.actor_id for actor in harness.inspection.actors) == (
        "elite_dog",
        "fighter_target",
        "guard_dog",
        "fleet_fighter",
    )

    # Knockout moved the target before the acting dog in initiative; the dog
    # retains its turn, then the conscious ally can act without striking the
    # stabilized fighter.
    harness.end_turn(expected_actor_id="fleet_fighter")
    safe_target = harness.actor("fighter_target")
    harness.command(Stride((Position(1, 3), Position(2, 3))))
    swing = harness.command(
        ViciousSwing("elite_dog", attack_id="shortsword"),
        expected_status=ResultStatus.PAUSED,
    )
    harness.pending_choice(
        kind="attack_hero_reroll", owner_actor_id="fleet_fighter", options=("keep",)
    )
    swing_result = harness.choose(
        kind="attack_hero_reroll",
        owner_actor_id="fleet_fighter",
        option_id="keep",
    )
    swing_check = next(event.check for event in swing_result.events if event.check is not None)
    swing_damage = next(event.damage for event in swing_result.events if event.damage is not None)
    assert swing_check is not None and swing_check.map_penalty == 0
    assert swing_damage is not None and swing_damage.total == 6
    assert harness.actor("elite_dog").hp == 12 and not harness.actor("elite_dog").dead
    assert harness.actor("fighter_target") == safe_target

    assert harness.inspection.turn_actor_id == "elite_dog"
    elite_dog_attack = harness.command(Strike("fleet_fighter", attack_id="jaws"))
    elite_dog_damage = next(
        event.damage for event in elite_dog_attack.events if event.damage is not None
    )
    assert elite_dog_damage is not None and elite_dog_damage.total == 5
    assert harness.actor("fighter_target") == safe_target
    harness.end_turn(expected_actor_id="guard_dog")
    guard_dog_attack = harness.command(Strike("fleet_fighter", attack_id="jaws"))
    guard_dog_damage = next(
        event.damage for event in guard_dog_attack.events if event.damage is not None
    )
    assert guard_dog_damage is not None and guard_dog_damage.total == 3
    assert harness.actor("fighter_target") == safe_target
    harness.end_turn(expected_actor_id="fleet_fighter")

    first_elite_strike = harness.command(
        Strike("elite_dog", attack_id="shortsword"),
        expected_status=ResultStatus.PAUSED,
    )
    harness.pending_choice(
        kind="attack_hero_reroll", owner_actor_id="fleet_fighter", options=("keep",)
    )
    first_elite_result = harness.choose(
        kind="attack_hero_reroll",
        owner_actor_id="fleet_fighter",
        option_id="keep",
    )
    first_elite_check = next(
        event.check for event in first_elite_result.events if event.check is not None
    )
    first_elite_damage = next(
        event.damage for event in first_elite_result.events if event.damage is not None
    )
    assert first_elite_check is not None and first_elite_check.map_penalty == 0
    assert first_elite_damage is not None and first_elite_damage.total == 6
    assert harness.actor("elite_dog").hp == 6 and not harness.actor("elite_dog").dead

    second_elite_strike = harness.command(
        Strike("elite_dog", attack_id="shortsword"),
        expected_status=ResultStatus.PAUSED,
    )
    harness.pending_choice(
        kind="attack_hero_reroll", owner_actor_id="fleet_fighter", options=("keep",)
    )
    second_elite_result = harness.choose(
        kind="attack_hero_reroll",
        owner_actor_id="fleet_fighter",
        option_id="keep",
    )
    second_elite_check = next(
        event.check for event in second_elite_result.events if event.check is not None
    )
    second_elite_damage = next(
        event.damage for event in second_elite_result.events if event.damage is not None
    )
    assert second_elite_check is not None and second_elite_check.map_penalty == -4
    assert second_elite_damage is not None and second_elite_damage.total == 6
    assert harness.actor("elite_dog").dead

    wounded_dog = harness.command(
        Strike("guard_dog", attack_id="shortsword"),
        expected_status=ResultStatus.PAUSED,
    )
    harness.pending_choice(
        kind="attack_hero_reroll", owner_actor_id="fleet_fighter", options=("keep",)
    )
    wounded_dog_result = harness.choose(
        kind="attack_hero_reroll",
        owner_actor_id="fleet_fighter",
        option_id="keep",
    )
    wounded_dog_check = next(
        event.check for event in wounded_dog_result.events if event.check is not None
    )
    wounded_dog_damage = next(
        event.damage for event in wounded_dog_result.events if event.damage is not None
    )
    assert wounded_dog_check is not None and wounded_dog_check.map_penalty == -8
    assert wounded_dog_damage is not None and wounded_dog_damage.total == 6
    assert harness.actor("guard_dog").hp == 2 and not harness.actor("guard_dog").dead
    assert harness.actor("fighter_target") == safe_target

    dog_attack = harness.command(Strike("fleet_fighter", attack_id="jaws"))
    dog_damage = next(event.damage for event in dog_attack.events if event.damage is not None)
    assert dog_damage is not None and dog_damage.total == 3
    assert harness.actor("fighter_target") == safe_target
    harness.end_turn(expected_actor_id="fleet_fighter")
    final_strike = harness.command(
        Strike("guard_dog", attack_id="shortsword"),
        expected_status=ResultStatus.PAUSED,
    )
    harness.pending_choice(
        kind="attack_hero_reroll", owner_actor_id="fleet_fighter", options=("keep",)
    )
    final_result = harness.choose(
        kind="attack_hero_reroll",
        owner_actor_id="fleet_fighter",
        option_id="keep",
    )
    final_damage = next(event.damage for event in final_result.events if event.damage is not None)
    assert final_damage is not None and final_damage.total == 5
    assert harness.actor("guard_dog").dead
    assert harness.actor("fighter_target") == safe_target
    harness.assert_ended()
    assert harness.inspection.winner_team == "blue"
