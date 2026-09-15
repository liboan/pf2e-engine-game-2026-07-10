"""Four source-backed S3 interaction encounters played to a real outcome.

Content/source review: docs/plan/05-interaction-encounters.md and
docs/implementation/s1-s3-rules.md (2026-09-15).
"""

from collections import deque
from pathlib import Path

from interaction_helpers import EncounterHarness
from pf2e.content import SHORTBOW_FIGHTER_R, get_definition, get_setup
from pf2e.encounter import Encounter
from pf2e.model import (
    Cast,
    Interact,
    Position,
    ResultStatus,
    Stand,
    Strike,
    Stride,
    Step,
)
from pf2e.s3_interaction_content import S3_INTERACTION_SETUPS, build_s3_definitions


_SAFE_TAIL = (15, 1) * 280


def _initiative_faces(setup_id: str, order: tuple[str, ...]) -> tuple[int, ...]:
    """Supply unique initiative totals in the requested order."""
    setup = get_setup(setup_id)
    target_totals = {actor_id: 25 - rank for rank, actor_id in enumerate(order)}
    assert set(target_totals) == {placement.actor_id for placement in setup.placements}
    faces = tuple(
        target_totals[placement.actor_id] - get_definition(placement.definition_id).perception
        for placement in setup.placements
    )
    assert all(1 <= face <= 20 for face in faces)
    return faces


def _start(
    scenario: str,
    order: tuple[str, ...],
    *,
    draws: tuple[int, ...] = (),
    max_commands: int = 160,
) -> EncounterHarness:
    setup = get_setup(scenario)
    rolls = (*_initiative_faces(scenario, order), *draws, *_SAFE_TAIL)
    harness = EncounterHarness(
        Encounter.start(setup, rolls=rolls),
        scenario,
        max_commands=max_commands,
        max_choices=40,
        max_rounds=12,
        max_events=2000,
    )
    harness.keep_initiative()
    assert harness.inspection.turn_actor_id == order[0]
    return harness


def _slot(harness: EncounterHarness, actor_id: str, slot_id: str):
    return next(slot for slot in harness.actor(actor_id).prepared_slots if slot.slot_id == slot_id)


def _is_attackable(actor) -> bool:
    if actor.dead or actor.defeated:
        return False
    # Positive damage into a stable 0-HP PC is intentionally unsupported.
    return not (
        actor.health_mode.value == "pc"
        and actor.hp == 0
        and actor.dying == 0
        and not actor.dead
    )


def _choose_filler_choice(harness: EncounterHarness) -> None:
    choice = harness.inspection.choice
    assert choice is not None
    if choice.kind in {
        "initiative_hero_reroll",
        "attack_hero_reroll",
        "spell_attack_hero_reroll",
        "spell_save_hero_reroll",
        "recovery_hero_reroll",
    }:
        option = "keep"
    elif choice.kind == "initiative_tie":
        option = choice.options[0].option_id
    elif choice.kind == "reaction":
        option = "decline"
    elif choice.kind in {"heroic_recovery_damage", "recovery_heroic_increase"}:
        option = "normal"
    elif choice.kind == "recovery_start_heroic":
        option = "recovery_check"
    elif choice.kind == "guidance_use":
        option = "keep"
    elif choice.kind == "spell_self_inclusion":
        option = "exclude"
    elif choice.kind == "spell_willingness":
        option = "willing"
    elif choice.kind == "spell_slot":
        option = choice.options[0].option_id
    elif choice.kind == "spell_target":
        option = choice.options[0].option_id
    else:
        raise AssertionError(f"unexpected choice during complete fight: {choice.kind}")
    harness.choose(
        kind=choice.kind,
        owner_actor_id=choice.owner_actor_id,
        option_id=option,
        expected_status=None,
    )


def _movement_path(harness: EncounterHarness, actor_id: str) -> tuple[Position, ...]:
    inspection = harness.inspection
    actor = harness.actor(actor_id)
    setup = get_setup(inspection_setup_id := next(
        setup.setup_id for setup in S3_INTERACTION_SETUPS
        if {placement.actor_id for placement in setup.placements}
        == {view.actor_id for view in inspection.actors}
    ))
    definition_id = next(
        placement.definition_id for placement in setup.placements
        if placement.actor_id == actor_id
    )
    max_squares = max(1, get_definition(definition_id).land_speed_ft // 5)
    foes = [
        other for other in inspection.actors
        if other.team != actor.team and _is_attackable(other)
    ]
    # The engine keeps defeated actors on their squares, so treat every other
    # token as path-blocking even if it is no longer a valid target.
    occupied = {
        other.position for other in inspection.actors
        if other.actor_id != actor_id
    }
    width, height = inspection.map_width, inspection.map_height
    queue = deque([actor.position])
    parents: dict[Position, Position | None] = {actor.position: None}
    goal: Position | None = None
    while queue:
        position = queue.popleft()
        if any(
            max(abs(position.x - foe.position.x), abs(position.y - foe.position.y)) <= 1
            for foe in foes
        ):
            goal = position
            break
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            neighbor = Position(position.x + dx, position.y + dy)
            if not (0 <= neighbor.x < width and 0 <= neighbor.y < height):
                continue
            if neighbor in occupied or neighbor in parents:
                continue
            parents[neighbor] = position
            queue.append(neighbor)
    if goal is None or goal == actor.position:
        return ()
    reversed_path: list[Position] = []
    cursor = goal
    while cursor != actor.position:
        reversed_path.append(cursor)
        parent = parents[cursor]
        assert parent is not None
        cursor = parent
    return tuple(reversed(reversed_path))[:max_squares]


def _finish_fight(harness: EncounterHarness) -> None:
    """Continue a modest public-command policy until the engine declares a winner."""
    while harness.inspection.in_progress:
        if harness.inspection.choice is not None:
            _choose_filler_choice(harness)
            continue

        actor_id = harness.inspection.turn_actor_id
        assert actor_id is not None
        actor = harness.actor(actor_id)
        options = harness.game.options()
        if actor.actions_remaining <= 0:
            harness.end_turn()
            continue

        attack_rows = [
            strike for strike in options.strikes
            if any(
                _is_attackable(harness.actor(target_id))
                and harness.actor(target_id).team != actor.team
                for target_id in strike.targets
            )
        ]
        if attack_rows:
            preferred = {
                "fighter_r_level_1": ("shortbow", "longsword", "fist"),
                "fighter_fleet_shortsword_level_1": ("shortsword", "longsword", "fist"),
                "fighter_rapier_level_1": ("rapier", "longsword", "fist"),
            }.get(
                next(
                    placement.definition_id
                    for setup in S3_INTERACTION_SETUPS
                    for placement in setup.placements
                    if placement.actor_id == actor_id
                    and {p.actor_id for p in setup.placements}
                    == {view.actor_id for view in harness.inspection.actors}
                ),
                ("jaws", "longsword", "fist"),
            )
            chosen = next(
                (row for attack_id in preferred for row in attack_rows if row.attack_id == attack_id),
                attack_rows[0],
            )
            target_id = next(
                target_id for target_id in chosen.targets
                if _is_attackable(harness.actor(target_id))
                and harness.actor(target_id).team != actor.team
            )
            harness.command(
                Strike(target_id, attack_id=chosen.attack_id),
                expected_status=None,
            )
            continue

        path = _movement_path(harness, actor_id)
        if path:
            harness.command(Stride(path), expected_status=None)
        else:
            harness.end_turn()

    harness.assert_ended()
    assert harness.inspection.winner_team in {"blue", "red"}


def test_s3_interaction_content_has_eight_catalogued_setups_and_legal_rapier_build() -> None:
    assert len(S3_INTERACTION_SETUPS) == 8
    assert len({setup.setup_id for setup in S3_INTERACTION_SETUPS}) == 8
    (rapier_fighter,) = build_s3_definitions(SHORTBOW_FIGHTER_R)
    assert rapier_fighter.definition_id == "fighter_rapier_level_1"
    assert rapier_fighter.level == 1
    assert (rapier_fighter.hp, rapier_fighter.ac, rapier_fighter.land_speed_ft) == (21, 18, 25)
    assert rapier_fighter.held_items == ("rapier",)
    assert rapier_fighter.ammunition == ()
    rapier = next(attack for attack in rapier_fighter.attacks if attack.attack_id == "rapier")
    assert (rapier.modifier, rapier.damage_dice, rapier.damage_modifier, rapier.damage_type) == (
        9, (6,), 1, "piercing",
    )
    assert (rapier.attack_attribute, rapier.damage_attribute, rapier.deadly_die) == (
        "dexterity", "strength", 8,
    )
    assert {"finesse", "deadly", "deadly-d8", "disarm"} <= rapier.traits
    assert any("Disarm action is unavailable" in note for note in rapier_fighter.sheet_notes)
    assert any("10 gp" in note for note in rapier_fighter.sheet_notes)


def test_s3_long_lane_crossfire_tracks_range_cover_ammo_and_saved_shot(
    tmp_path: Path,
) -> None:
    """Shortbow: 60/65 ft increments; creature cover and range are separate."""
    # Remaster shortbow/range: https://2e.aonprd.com/Weapons.aspx?ID=437 and
    # https://2e.aonprd.com/Rules.aspx?ID=2290; cover: Rule 2372.
    harness = _start(
        "s3_long_lane_crossfire",
        ("fighter_r", "fighter_m", "cleric_c", "guard_dog_60", "guard_dog_65"),
        draws=(6, 1, 9),
    )
    fighter = harness.actor("fighter_r")
    assert fighter.position == Position(0, 2)
    assert harness.actor("guard_dog_60").position == Position(12, 2)
    assert harness.actor("guard_dog_65").position == Position(13, 2)

    shot_60 = harness.command(
        Strike("guard_dog_60", attack_id="shortbow"), expected_status=ResultStatus.PAUSED
    )
    check_60 = next(event.check for event in shot_60.events if event.check is not None)
    assert check_60 is not None
    assert (check_60.dc, check_60.modifier, check_60.map_penalty) == (15, 9, 0)
    assert not any(term.source == "range increment penalty" for term in check_60.modifier_breakdown)
    kept_60 = harness.choose(
        kind="attack_hero_reroll", owner_actor_id="fighter_r", option_id="keep"
    )
    damage_60 = next(event.damage for event in kept_60.events if event.damage is not None)
    assert damage_60.total == 1
    assert harness.actor("guard_dog_60").hp < harness.actor("guard_dog_60").max_hp
    assert dict(harness.actor("fighter_r").ammunition)["arrow"] == 19

    pending_65 = harness.command(
        Strike("guard_dog_65", attack_id="shortbow"), expected_status=ResultStatus.PAUSED
    )
    check_65 = next(event.check for event in pending_65.events if event.check is not None)
    assert check_65 is not None
    assert (check_65.dc, check_65.modifier, check_65.map_penalty) == (16, 2, -5)
    range_terms = [term.amount for term in check_65.modifier_breakdown if term.source == "range increment penalty"]
    assert range_terms == [-2]
    before = pending_65.inspection
    harness.checkpoint(tmp_path / "long-lane-pending-shot.json")
    assert harness.inspection == before
    assert harness.pending_choice(kind="attack_hero_reroll", owner_actor_id="fighter_r")
    assert harness.actor("fighter_r").position == Position(0, 2)
    assert harness.actor("fighter_r").actions_remaining == 1
    assert dict(harness.actor("fighter_r").ammunition)["arrow"] == 18
    harness.choose(kind="attack_hero_reroll", owner_actor_id="fighter_r", option_id="keep")
    assert dict(harness.actor("fighter_r").ammunition)["arrow"] == 18

    _finish_fight(harness)


def test_s3_cover_lane_rotation_changes_ac_after_ally_moves(tmp_path: Path) -> None:
    """Creature cover raises AC but does not block an attack's line of effect."""
    # Lesser cover and line of effect: https://2e.aonprd.com/Rules.aspx?ID=2372
    # and https://2e.aonprd.com/Rules.aspx?ID=2382.
    harness = _start(
        "s3_cover_lane_rotation",
        ("fighter_r", "cleric_c", "fighter_m", "elite_guard_dog", "guard_dog"),
        draws=(10, 1, 10, 12, 2, 3, 8, 2),
    )
    covered = harness.command(
        Strike("elite_guard_dog", attack_id="shortbow"), expected_status=ResultStatus.PAUSED
    )
    covered_check = next(event.check for event in covered.events if event.check is not None)
    assert covered_check is not None and covered_check.dc == 18
    first_hit = harness.choose(
        kind="attack_hero_reroll", owner_actor_id="fighter_r", option_id="keep"
    )
    assert any(event.damage is not None for event in first_hit.events)
    assert harness.actor("elite_guard_dog").hp < harness.actor("elite_guard_dog").max_hp

    mapped = harness.command(
        Strike("elite_guard_dog", attack_id="shortbow"), expected_status=ResultStatus.PAUSED
    )
    mapped_check = next(event.check for event in mapped.events if event.check is not None)
    assert mapped_check is not None and mapped_check.dc == 18
    assert mapped_check.map_penalty == -5
    harness.choose(kind="attack_hero_reroll", owner_actor_id="fighter_r", option_id="keep")

    harness.end_turn()  # Fighter R has one remaining shot, which is not needed here.
    assert harness.inspection.turn_actor_id == "cleric_c"
    caster = harness.actor("cleric_c")
    slots_before_lance = tuple((slot.slot_id, slot.spent) for slot in caster.prepared_slots)
    lance = harness.command(
        Cast("divine_lance", "elite_guard_dog"), expected_status=ResultStatus.PAUSED
    )
    lance_check = next(event.check for event in lance.events if event.check is not None)
    assert lance_check is not None and lance_check.dc == 18
    assert lance_check.modifier == 7 and lance_check.map_penalty == 0
    lance_result = harness.choose(
        kind="spell_attack_hero_reroll", owner_actor_id="cleric_c", option_id="keep"
    )
    assert any(event.damage is not None for event in lance_result.events)
    assert tuple((slot.slot_id, slot.spent) for slot in harness.actor("cleric_c").prepared_slots) == slots_before_lance

    harness.end_turn()
    assert harness.inspection.turn_actor_id == "fighter_m"
    step = harness.command(Step(Position(4, 3)))
    assert all(event.kind != "reaction" for event in step.events)
    assert harness.actor("fighter_m").position == Position(4, 3)

    # The dogs and cleric pass without altering the lane, so Fighter R can
    # compare the same target after the interposing ally leaves.
    while harness.inspection.turn_actor_id != "fighter_r" or harness.inspection.round_number == 1:
        actor_id = harness.inspection.turn_actor_id
        assert actor_id is not None
        harness.end_turn()
    clear = harness.command(
        Strike("elite_guard_dog", attack_id="shortbow"), expected_status=ResultStatus.PAUSED
    )
    clear_check = next(event.check for event in clear.events if event.check is not None)
    assert clear_check is not None and clear_check.dc == 17
    assert clear_check.map_penalty == 0
    harness.choose(kind="attack_hero_reroll", owner_actor_id="fighter_r", option_id="keep")

    _finish_fight(harness)


def _knock_out_melee_fighter(
    scenario: str,
    tmp_path: Path,
) -> EncounterHarness:
    order = (
        ("guard_dog_a", "guard_dog_b", "cleric_c", "fighter_r", "fighter_m")
        if scenario == "s3_rescue_under_pressure"
        else ("guard_dog_a", "cleric_c", "fighter_r", "fighter_m")
    )
    harness = _start(
        scenario,
        order,
        # Dog A critically hits twice for 10 each, then hits once for 5.
        # Fighter M starts at 21 HP, so this produces a real PC knockout.
        draws=(20, 4, 20, 4, 20, 4, 8),
    )
    assert harness.inspection.turn_actor_id == "guard_dog_a"
    for _ in range(3):
        attack = harness.command(
            Strike("fighter_m", attack_id="jaws"), expected_status=None
        )
        if harness.inspection.choice is not None:
            break
    choice = harness.pending_choice(
        kind="heroic_recovery_damage", owner_actor_id="fighter_m", options=("normal", "heroic_recovery")
    )
    assert choice is not None
    harness.checkpoint(tmp_path / f"{scenario}-knockout-choice.json")
    harness.choose(
        kind="heroic_recovery_damage",
        owner_actor_id="fighter_m",
        option_id="normal",
    )
    downed = harness.actor("fighter_m")
    assert (downed.hp, downed.dying, downed.unconscious, downed.prone) == (0, 1, True, True)
    assert downed.wounded == 0
    assert downed.held_items == ()
    expected_next = "guard_dog_b" if scenario == "s3_rescue_under_pressure" else "cleric_c"
    assert harness.inspection.turn_actor_id == expected_next
    return harness


def _advance_to(harness: EncounterHarness, actor_id: str, *, limit: int = 10) -> None:
    for _ in range(limit):
        if harness.inspection.turn_actor_id == actor_id:
            return
        assert harness.inspection.turn_actor_id is not None
        harness.end_turn()
    assert harness.inspection.turn_actor_id == actor_id


def _recover_and_rejoin(harness: EncounterHarness) -> None:
    _advance_to(harness, "fighter_m")
    assert "stand" in harness.game.options().available_actions
    harness.command(Stand())
    assert not harness.actor("fighter_m").prone
    assert ("retrieve", "longsword") in harness.game.options().interact_options
    harness.command(Interact("retrieve", "longsword"))
    assert harness.actor("fighter_m").held_items == ("longsword",)
    attack = harness.command(
        Strike("guard_dog_a", attack_id="longsword"), expected_status=ResultStatus.PAUSED
    )
    resolved = harness.choose(
        kind="attack_hero_reroll", owner_actor_id="fighter_m", option_id="keep"
    )
    assert any(event.damage is not None for event in (*attack.events, *resolved.events))


def test_s3_rescue_under_pressure_heal_restores_pc_and_equipment_then_fight_ends(
    tmp_path: Path,
) -> None:
    """Rank-1 two-action Heal ends dying, adds wounded once, and preserves prone/drop."""
    # Knockout: https://2e.aonprd.com/Rules.aspx?ID=2324; Heal:
    # https://2e.aonprd.com/Spells.aspx?ID=1554.
    harness = _knock_out_melee_fighter("s3_rescue_under_pressure", tmp_path)
    harness.end_turn()  # The second dog deliberately leaves the dying PC unharmed.
    assert harness.inspection.turn_actor_id == "cleric_c"

    pending = harness.command(
        Cast("heal", "fighter_m", actions=2, slot_id="ordinary_heal_1"),
        expected_status=ResultStatus.PAUSED,
    )
    assert pending.inspection.choice is not None
    assert pending.inspection.choice.kind == "spell_willingness"
    assert _slot(harness, "cleric_c", "ordinary_heal_1").spent
    assert not _slot(harness, "cleric_c", "font_heal_1").spent
    harness.checkpoint(tmp_path / "rescue-heal-willingness.json")
    healed = harness.choose(
        kind="spell_willingness", owner_actor_id="fighter_m", option_id="willing"
    )
    healing = next(event for event in healed.events if event.kind == "healing")
    assert "heals 16 HP (1d8 8 + 8)" in healing.text
    fighter = harness.actor("fighter_m")
    assert (fighter.hp, fighter.dying, fighter.wounded, fighter.unconscious, fighter.prone) == (
        16, 0, 1, False, True,
    )
    assert fighter.held_items == ()
    assert harness.inspection.ground_items == ((Position(2, 2), ("longsword",)),)

    _recover_and_rejoin(harness)
    _finish_fight(harness)


def test_s3_stabilize_then_touch_heal_preserves_the_stable_zero_boundary(
    tmp_path: Path,
) -> None:
    """Stabilize leaves stable zero; a later touch Heal restores without +8."""
    # Stabilize: https://2e.aonprd.com/Spells.aspx?ID=1689; Heal:
    # https://2e.aonprd.com/Spells.aspx?ID=1554.
    # This two-dog route has more actual attacks than the rescue case. The
    # first bounded run reached its 40-choice cap in round 8 while both teams
    # were still advancing, so allow the documented 12-round route to finish.
    harness = _knock_out_melee_fighter("s3_stabilize_then_touch", tmp_path)
    assert harness.inspection.turn_actor_id == "cleric_c"

    stabilized = harness.command(Cast("stabilize", "fighter_m"))
    fighter = harness.actor("fighter_m")
    assert (fighter.hp, fighter.dying, fighter.wounded, fighter.unconscious, fighter.prone) == (
        0, 0, 1, True, True,
    )
    assert not any(slot.spent for slot in harness.actor("cleric_c").prepared_slots)
    assert any(event.kind == "stabilize" for event in stabilized.events)
    stable_inspection = harness.inspection
    harness.checkpoint(tmp_path / "stable-zero-before-touch-heal.json")
    assert harness.inspection == stable_inspection

    # Let the round continue without damaging the stable 0-HP PC.
    safe_interval_results = []
    harness.end_turn()  # C has one action left after Stabilize.
    for _ in range(8):
        if harness.inspection.turn_actor_id == "cleric_c":
            break
        result = harness.end_turn()
        safe_interval_results.extend(result.events)
    assert harness.inspection.turn_actor_id == "cleric_c"
    assert not any(event.damage is not None and event.target_id == "fighter_m" for event in safe_interval_results)
    assert harness.actor("fighter_m").hp == 0 and harness.actor("fighter_m").dying == 0

    pending = harness.command(
        Cast("heal", "fighter_m", actions=1, slot_id="ordinary_heal_2"),
        expected_status=ResultStatus.PAUSED,
    )
    assert pending.inspection.choice is not None and pending.inspection.choice.kind == "spell_willingness"
    assert _slot(harness, "cleric_c", "ordinary_heal_2").spent
    assert not _slot(harness, "cleric_c", "font_heal_1").spent
    harness.checkpoint(tmp_path / "touch-heal-willingness.json")
    healed = harness.choose(
        kind="spell_willingness", owner_actor_id="fighter_m", option_id="willing"
    )
    healing = next(event for event in healed.events if event.kind == "healing")
    assert "heals 8 HP (1d8 8)" in healing.text
    assert " + 8" not in healing.text
    fighter = harness.actor("fighter_m")
    assert (fighter.hp, fighter.dying, fighter.wounded, fighter.unconscious, fighter.prone) == (
        8, 0, 1, False, True,
    )
    assert fighter.held_items == ()
    assert harness.inspection.ground_items == ((Position(2, 2), ("longsword",)),)

    _recover_and_rejoin(harness)
    _finish_fight(harness)
