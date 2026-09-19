"""Public-engine S2 interaction encounters using published content variants."""

from collections import deque
from pathlib import Path

from interaction_helpers import EncounterHarness
from pf2e.content import FIGHTER_FLEET_SHORTSWORD, ELITE_GUARD_DOG, get_definition, get_setup
from pf2e.checks import DegreeOfSuccess
from pf2e.encounter import Encounter
from pf2e.model import (
    EndTurn,
    HealthMode,
    Interact,
    Position,
    ResultStatus,
    Step,
    Strike,
    Stride,
    ViciousSwing,
)
from pf2e.s2_interaction_content import S2_INTERACTION_SETUPS


def _rolls(initiative: tuple[int, ...], scripted: tuple[int, ...] = ()) -> tuple[int, ...]:
    """Append finite, low-damage rolls for the bounded melee finish."""
    return (*initiative, *scripted, *((12, 1) * 400))


def _start(
    setup_id: str,
    initiative: tuple[int, ...],
    scripted: tuple[int, ...] = (),
    *,
    max_choices: int = 40,
) -> EncounterHarness:
    game = Encounter.start(get_setup(setup_id), rolls=_rolls(initiative, scripted))
    harness = EncounterHarness(game, setup_id, max_choices=max_choices)
    harness.keep_initiative()
    return harness


def _finish_pc_attack(harness: EncounterHarness, result=None):
    """Keep a real Hero Point prompt if this PC attack offers one."""
    while harness.inspection.choice is not None:
        choice = harness.inspection.choice
        assert choice is not None
        if choice.kind == "attack_hero_reroll":
            result = harness.choose(
                kind="attack_hero_reroll",
                owner_actor_id=choice.owner_actor_id,
                option_id="keep",
                expected_status=None,
            )
            continue
        if choice.kind == "reaction":
            result = harness.choose(
                kind="reaction",
                owner_actor_id=choice.owner_actor_id,
                option_id="decline",
                expected_status=None,
            )
            continue
        if choice.kind == "heroic_recovery_damage":
            result = harness.choose(
                kind="heroic_recovery_damage",
                owner_actor_id=choice.owner_actor_id,
                option_id="normal",
                expected_status=None,
            )
            continue
        if choice.kind == "recovery_start_heroic":
            result = harness.choose(
                kind="recovery_start_heroic",
                owner_actor_id=choice.owner_actor_id,
                option_id="recovery_check",
                expected_status=None,
            )
            continue
        if choice.kind == "recovery_hero_reroll":
            result = harness.choose(
                kind="recovery_hero_reroll",
                owner_actor_id=choice.owner_actor_id,
                option_id="keep",
                expected_status=None,
            )
            continue
        if choice.kind == "recovery_heroic_increase":
            result = harness.choose(
                kind="recovery_heroic_increase",
                owner_actor_id=choice.owner_actor_id,
                option_id="normal",
                expected_status=None,
            )
            continue
        raise AssertionError(f"unexpected choice while finishing attack: {choice.kind}")
    if result is not None:
        assert result.status is ResultStatus.COMPLETED
    return result


def _path_to_enemy(harness: EncounterHarness, actor_id: str) -> tuple[Position, ...]:
    """Find a bounded, cardinal Stride path to an open square next to an enemy."""
    inspection = harness.inspection
    actor = next(item for item in inspection.actors if item.actor_id == actor_id)
    enemies = [item for item in inspection.actors if item.team != actor.team and not item.defeated]
    occupied = {item.position for item in inspection.actors if item.actor_id != actor_id}
    start = actor.position
    frontier = deque([(start, ())])
    visited = {start}
    definition_id = next(
        item.definition_id
        for item in get_setup(harness.scenario).placements
        if item.actor_id == actor_id
    )
    max_steps = get_definition(definition_id).land_speed_ft // 5
    best_path: tuple[Position, ...] = ()
    while frontier:
        point, path = frontier.popleft()
        if path and any(
            max(abs(point.x - enemy.position.x), abs(point.y - enemy.position.y)) == 1
            for enemy in enemies
        ):
            return path
        if len(path) >= max_steps:
            if len(path) > len(best_path):
                best_path = path
            continue
        for dx, dy in ((1, 0), (0, 1), (-1, 0), (0, -1)):
            nxt = Position(point.x + dx, point.y + dy)
            if not (0 <= nxt.x < inspection.map_width and 0 <= nxt.y < inspection.map_height):
                continue
            if nxt in occupied or nxt in visited:
                continue
            visited.add(nxt)
            frontier.append((nxt, (*path, nxt)))
    return best_path


def _finish_blue_win(harness: EncounterHarness) -> None:
    """Use legal public commands to continue ordinary combat to a blue victory."""
    for _ in range(160):
        inspection = harness.inspection
        if not inspection.in_progress:
            break
        if inspection.choice is not None:
            _finish_pc_attack(harness)
            continue
        actor_id = inspection.turn_actor_id
        assert actor_id is not None
        actor = next(item for item in inspection.actors if item.actor_id == actor_id)
        if actor.team != "blue" or actor.actions_remaining <= 0:
            result = harness.command(EndTurn(), expected_status=None)
            _finish_pc_attack(harness, result)
            continue
        if actor.prone and not actor.unconscious:
            from pf2e.model import Stand

            _finish_pc_attack(harness, harness.command(Stand(), expected_status=None))
            continue

        options = harness.game.options()
        strike = next(
            (
                (attack, target_id)
                for attack in options.strikes
                for target_id in attack.targets
                if next(item for item in inspection.actors if item.actor_id == target_id).team == "red"
            ),
            None,
        )
        if strike is not None:
            attack, target_id = strike
            target = next(item for item in inspection.actors if item.actor_id == target_id)
            attack_id = "fist" if target.health_mode is HealthMode.PC else attack.attack_id
            result = harness.command(
                Strike(
                    target_id,
                    attack_id=attack_id,
                    nonlethal=False if target.health_mode is HealthMode.PC else None,
                ),
                expected_status=None,
            )
            _finish_pc_attack(harness, result)
            continue

        if options.can_stride:
            path = _path_to_enemy(harness, actor_id)
            if path:
                result = harness.command(Stride(path), expected_status=None)
                _finish_pc_attack(harness, result)
                continue
        harness.end_turn()

    harness.assert_ended()
    assert harness.inspection.winner_team == "blue"


def test_s2_interaction_content_is_exactly_catalogued() -> None:
    fighter = get_definition("fighter_fleet_shortsword_level_1")
    dog = get_definition("elite_guard_dog_mc2924")

    assert fighter is FIGHTER_FLEET_SHORTSWORD
    assert dog is ELITE_GUARD_DOG
    assert (fighter.level, fighter.hp, fighter.ac, fighter.land_speed_ft) == (1, 21, 18, 30)
    assert fighter.feats == ("General Training", "Fleet", "Assurance (Athletics)", "Vicious Swing")
    assert {skill[0] for skill in fighter.skills}.isdisjoint({"crafting", "society"})
    assert fighter.held_items == ("shortsword",)
    assert fighter.worn_items == ("breastplate", "longsword")
    shortsword = fighter.attacks[0]
    assert (shortsword.modifier, shortsword.damage_type, shortsword.damage_dice, shortsword.damage_modifier) == (
        9,
        "piercing",
        (6,),
        4,
    )
    assert {"agile", "finesse", "versatile-s"} <= shortsword.traits
    assert fighter.attacks[1].attack_id == "longsword"
    assert (dog.level, dog.hp, dog.ac, dog.perception, dog.land_speed_ft) == (1, 18, 17, 8, 30)
    assert dog.saves == (("fortitude", None, 7), ("reflex", None, 9), ("will", None, 6))
    assert dog.skills == (("acrobatics", None, 7), ("athletics", None, 6), ("stealth", None, 7), ("survival", None, 6))
    assert (dog.attacks[0].modifier, dog.attacks[0].damage_dice, dog.attacks[0].damage_modifier) == (8, (4,), 3)
    assert len(S2_INTERACTION_SETUPS) == 8
    assert len({setup.setup_id for setup in S2_INTERACTION_SETUPS}) == 8
    assert all(get_setup(setup.setup_id) == setup for setup in S2_INTERACTION_SETUPS)


def test_fleet_four_diagonals_and_vicious_swing_refresh_through_full_fight(tmp_path: Path) -> None:
    harness = _start(
        "s2_fleet_diagonal_assault",
        (20, 19, 18, 15),
        scripted=(12, 1, 1, 12, 1),
    )
    assert harness.inspection.turn_actor_id == "fleet_fighter"

    moved = harness.command(
        Stride((Position(1, 1), Position(2, 2), Position(3, 3), Position(4, 4)))
    )
    assert moved.status is ResultStatus.COMPLETED
    assert harness.actor("fleet_fighter").position == Position(4, 4)
    assert harness.actor("fleet_fighter").diagonals_this_turn == 4
    assert harness.actor("fleet_fighter").actions_remaining == 2
    harness.checkpoint(tmp_path / "fleet-diagonals.json")

    paused = harness.command(ViciousSwing("guard_dog", attack_id="shortsword"), expected_status=None)
    choice = harness.pending_choice(kind="attack_hero_reroll", owner_actor_id="fleet_fighter", options=("keep",))
    result = harness.choose(
        kind="attack_hero_reroll",
        owner_actor_id="fleet_fighter",
        option_id="keep",
    )
    check = next(event.check for event in result.events if event.check is not None)
    assert paused.status is ResultStatus.PAUSED and choice.choice_id > 0
    assert check is not None and check.map_penalty == 0
    before_reset = next(
        actor for actor in paused.inspection.actors if actor.actor_id == "fleet_fighter"
    )
    assert before_reset.strikes_this_turn == 2
    # The two-action Vicious Swing consumes the last two actions after the
    # Stride; the public engine ends Fleet's turn and resets turn-wide counts.
    assert harness.inspection.turn_actor_id == "fighter_m"
    assert harness.actor("fleet_fighter").strikes_this_turn == 0
    assert harness.actor("guard_dog").hp == 2

    moved_m = harness.command(
        Stride((Position(1, 4), Position(2, 4), Position(3, 4), Position(4, 3)))
    )
    assert moved_m.status is ResultStatus.COMPLETED
    strike = _finish_pc_attack(
        harness,
        harness.command(Strike("guard_dog", attack_id="longsword"), expected_status=None),
    )
    assert any(event.damage is not None for event in strike.events)
    assert harness.actor("guard_dog").hp == 0 and harness.actor("guard_dog").dead
    harness.end_turn(expected_actor_id="elite_dog")
    harness.end_turn(expected_actor_id="fleet_fighter")
    assert harness.inspection.round_number == 2
    assert harness.actor("fleet_fighter").diagonals_this_turn == 0
    assert harness.actor("fleet_fighter").strikes_this_turn == 0

    _finish_blue_win(harness)


def test_shortsword_and_longsword_apply_their_own_map_and_versatile_choice(tmp_path: Path) -> None:
    harness = _start(
        "s2_mixed_blade_pressure",
        (20, 19, 15, 14),
        scripted=(12, 1, 7, 1, 7, 12, 1, 1, 16, 1),
    )
    assert harness.inspection.turn_actor_id == "fleet_fighter"
    assert ("draw", "longsword") in harness.game.options().interact_options
    harness.command(Interact("draw", "longsword"))
    assert harness.actor("fleet_fighter").held_items == ("shortsword", "longsword")

    long_result = _finish_pc_attack(
        harness,
        harness.command(
            Strike("elite_dog", attack_id="longsword", damage_type="piercing"),
            expected_status=None,
        ),
    )
    long_check = next(event.check for event in long_result.events if event.check is not None)
    assert long_check is not None and long_check.attack_id == "longsword" and long_check.map_penalty == 0

    short_result = _finish_pc_attack(
        harness,
        harness.command(
            Strike("elite_dog", attack_id="shortsword", damage_type="slashing"),
            expected_status=None,
        ),
    )
    short_check = next(event.check for event in short_result.events if event.check is not None)
    assert short_check is not None and short_check.attack_id == "shortsword" and short_check.map_penalty == -4
    assert short_check.degree is DegreeOfSuccess.FAILURE
    assert not any(event.damage is not None for event in short_result.events)
    assert harness.actor("elite_dog").hp == 13
    harness.checkpoint(tmp_path / "mixed-blades.json")

    harness.end_turn(expected_actor_id="elite_dog")
    harness.end_turn(expected_actor_id="guard_dog")
    harness.end_turn(expected_actor_id="fleet_fighter")
    assert harness.inspection.turn_actor_id == "fleet_fighter"
    assert harness.actor("fleet_fighter").strikes_this_turn == 0

    short_first = _finish_pc_attack(
        harness,
        harness.command(
            Strike("elite_dog", attack_id="shortsword", damage_type="slashing"),
            expected_status=None,
        ),
    )
    short_first_check = next(event.check for event in short_first.events if event.check is not None)
    assert short_first_check is not None and short_first_check.attack_id == "shortsword"
    assert short_first_check.attack_count == 1 and short_first_check.map_penalty == 0

    long_second = _finish_pc_attack(
        harness,
        harness.command(
            Strike("elite_dog", attack_id="longsword", damage_type="piercing"),
            expected_status=None,
        ),
    )
    long_second_check = next(event.check for event in long_second.events if event.check is not None)
    assert long_second_check is not None and long_second_check.attack_id == "longsword"
    assert long_second_check.attack_count == 2 and long_second_check.map_penalty == -5
    assert long_second_check.degree is DegreeOfSuccess.FAILURE
    assert harness.actor("elite_dog").hp == 13

    harness.end_turn(expected_actor_id="fighter_m")
    harness.end_turn(expected_actor_id="elite_dog")
    harness.end_turn(expected_actor_id="guard_dog")
    harness.end_turn(expected_actor_id="fleet_fighter")
    assert harness.inspection.round_number == 3
    assert harness.actor("fleet_fighter").strikes_this_turn == 0

    swing = harness.command(
        ViciousSwing("elite_dog", attack_id="shortsword", damage_type="slashing"),
        expected_status=None,
    )
    assert swing.status is ResultStatus.PAUSED
    swing_result = harness.choose(
        kind="attack_hero_reroll",
        owner_actor_id="fleet_fighter",
        option_id="keep",
    )
    swing_check = next(event.check for event in swing_result.events if event.check is not None)
    assert swing_check is not None and swing_check.map_penalty == 0
    assert any(
        event.damage is not None
        and event.damage.components[0].damage_type == "slashing"
        for event in swing_result.events
    )
    followup = _finish_pc_attack(
        harness,
        harness.command(
            Strike("elite_dog", attack_id="shortsword", damage_type="slashing"),
            expected_status=None,
        ),
    )
    followup_check = next(event.check for event in followup.events if event.check is not None)
    assert followup_check is not None and followup_check.map_penalty == -8
    assert any(
        event.damage is not None
        and event.damage.components[0].damage_type == "slashing"
        for event in followup.events
    )
    assert harness.actor("elite_dog").hp == 2 and not harness.actor("elite_dog").dead

    _finish_blue_win(harness)


def test_flanking_changes_with_step_and_is_reestablished(tmp_path: Path) -> None:
    harness = _start(
        "s2_flank_rotation",
        (20, 19, 15, 14),
        scripted=(6, 1, 6, 6, 1),
    )
    assert harness.inspection.turn_actor_id == "fleet_fighter"
    initial = _finish_pc_attack(
        harness,
        harness.command(Strike("elite_dog", attack_id="shortsword"), expected_status=None),
    )
    initial_check = next(event.check for event in initial.events if event.check is not None)
    initial_damage = next(event.damage for event in initial.events if event.damage is not None)
    assert initial_check is not None and initial_check.dc == 15
    assert initial_check.degree is DegreeOfSuccess.SUCCESS
    assert initial_damage.total == 5 and harness.actor("elite_dog").hp == 13

    stepped = harness.command(Step(Position(2, 1)))
    assert stepped.status is ResultStatus.COMPLETED
    assert stepped.inspection.choice is None
    assert harness.actor("fleet_fighter").position == Position(2, 1)
    harness.checkpoint(tmp_path / "flank-broken.json")
    harness.end_turn(expected_actor_id="fighter_m")

    unflanked = _finish_pc_attack(
        harness,
        harness.command(Strike("elite_dog", attack_id="longsword"), expected_status=None),
    )
    unflanked_check = next(event.check for event in unflanked.events if event.check is not None)
    assert unflanked_check is not None and unflanked_check.dc == 17
    assert unflanked_check.degree is DegreeOfSuccess.FAILURE
    assert not any(event.damage is not None for event in unflanked.events)
    assert harness.actor("elite_dog").hp == 13
    harness.end_turn(expected_actor_id="elite_dog")
    harness.end_turn(expected_actor_id="guard_dog")
    harness.end_turn(expected_actor_id="fleet_fighter")

    returned = harness.command(Step(Position(2, 2)))
    assert returned.status is ResultStatus.COMPLETED and returned.inspection.choice is None
    assert harness.actor("fleet_fighter").position == Position(2, 2)
    harness.end_turn(expected_actor_id="fighter_m")
    reflanked = _finish_pc_attack(
        harness,
        harness.command(Strike("elite_dog", attack_id="longsword"), expected_status=None),
    )
    reflanked_check = next(event.check for event in reflanked.events if event.check is not None)
    reflanked_damage = next(event.damage for event in reflanked.events if event.damage is not None)
    assert reflanked_check is not None and reflanked_check.dc == 15
    assert reflanked_check.degree is DegreeOfSuccess.SUCCESS
    assert reflanked_damage.total == 5 and harness.actor("elite_dog").hp == 8

    _finish_blue_win(harness)


def test_elite_pack_attack_requires_two_other_allies_and_is_not_flanking(tmp_path: Path) -> None:
    harness = _start(
        "s2_mixed_pack_screen",
        (10, 9, 20, 19, 18),
        scripted=(12, 2, 3, 12, 2),
        max_choices=50,
    )
    assert harness.inspection.turn_actor_id == "elite_dog"

    with_pack = harness.command(Strike("fighter_m", attack_id="jaws"))
    pack_check = next(event.check for event in with_pack.events if event.check is not None)
    pack_damage = next(event.damage for event in with_pack.events if event.damage is not None)
    assert pack_check is not None and pack_check.dc == 18
    assert pack_damage is not None and pack_damage.components[0].rolls == (2, 3)
    assert pack_damage.total == 8
    assert harness.actor("fighter_m").hp == 13
    harness.end_turn(expected_actor_id="guard_dog")
    harness.end_turn(expected_actor_id="fleet_fighter")

    escaped = harness.command(Step(Position(4, 2)))
    assert escaped.status is ResultStatus.COMPLETED and escaped.inspection.choice is None
    assert harness.actor("fleet_fighter").position == Position(4, 2)
    harness.checkpoint(tmp_path / "mixed-pack-screen.json")
    harness.end_turn(expected_actor_id="fighter_m")
    harness.end_turn(expected_actor_id="fighter_support")
    harness.end_turn(expected_actor_id="elite_dog")
    assert harness.inspection.round_number == 2
    assert harness.inspection.turn_actor_id == "elite_dog"

    without_pack = harness.command(Strike("fighter_m", attack_id="jaws"))
    plain_check = next(event.check for event in without_pack.events if event.check is not None)
    plain_damage = next(event.damage for event in without_pack.events if event.damage is not None)
    assert plain_check is not None and plain_check.dc == 18
    assert plain_damage is not None and plain_damage.components[0].rolls == (2,)
    assert plain_damage.total == 5
    assert harness.actor("fighter_m").hp == 8

    _finish_blue_win(harness)
