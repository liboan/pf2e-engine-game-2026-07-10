"""Complete public-engine play for S3 spell and reaction interactions.

Rules references (reviewed 2026-09-15):
https://2e.aonprd.com/Spells.aspx?ID=1549 (Guidance),
https://2e.aonprd.com/Actions.aspx?ID=2256 (Reactive Strike), and
https://2e.aonprd.com/Rules.aspx?ID=2289 (multiple attack penalty),
https://2e.aonprd.com/Spells.aspx?ID=1554 (Heal), and
https://2e.aonprd.com/Rules.aspx?ID=2233 (casting and disrupted spells).
"""

from pathlib import Path

from interaction_helpers import EncounterHarness
from pf2e.checks import DegreeOfSuccess
from pf2e.content import get_definition, get_setup
from pf2e.encounter import Encounter
from pf2e.model import (
    Cast,
    Position,
    ResultStatus,
    Strike,
    Stride,
    ViciousSwing,
)


def _initiative_faces(setup_id: str, order: tuple[str, ...]) -> tuple[int, ...]:
    setup = get_setup(setup_id)
    target_totals = {actor_id: 25 - rank for rank, actor_id in enumerate(order)}
    assert set(target_totals) == {placement.actor_id for placement in setup.placements}
    faces = tuple(
        target_totals[placement.actor_id]
        - get_definition(placement.definition_id).perception
        for placement in setup.placements
    )
    assert all(1 <= face <= 20 for face in faces)
    return faces


def _start(
    setup_id: str,
    order: tuple[str, ...],
    draws: tuple[int, ...],
) -> EncounterHarness:
    harness = EncounterHarness(
        Encounter.start(
            get_setup(setup_id),
            rolls=(*_initiative_faces(setup_id, order), *draws),
        ),
        setup_id,
        max_commands=80,
        max_choices=30,
        max_rounds=6,
        max_events=800,
    )
    harness.keep_initiative()
    assert harness.inspection.turn_actor_id == order[0]
    return harness


def _check(result):
    check = next(event.check for event in result.events if event.check is not None)
    assert check is not None
    return check


def _slot(harness: EncounterHarness, slot_id: str):
    return next(
        slot
        for slot in harness.actor("cleric_c").prepared_slots
        if slot.slot_id == slot_id
    )


def test_s3_guided_reaction_keeps_bonus_through_saved_reroll_and_ignores_map(
    tmp_path: Path,
) -> None:
    harness = _start(
        "s3_guided_reaction",
        ("cleric_c", "fleet_fighter", "rapier_fighter", "fighter_m", "guard_dog"),
        (
            8,  # Fleet's first Strike misses.
            10,  # Fleet's agile second Strike misses at MAP -4.
            8, 20, 6,  # Guided reaction, Hero reroll, and critical damage.
            20, 6, 6,  # M's critical Vicious Swing and its two dice.
            1,  # C's unguided Divine Lance misses in round 2.
            20, 6,  # Fleet's next check and critical damage finish the dog.
        ),
    )

    applied = harness.command(Cast("guidance", "fleet_fighter"))
    assert any(event.kind == "effect_applied" for event in applied.events)
    assert harness.actor("fleet_fighter").effects[0].kind == "guidance"
    harness.end_turn(expected_actor_id="fleet_fighter")

    # Two attacks make the MAP comparison real. Fleet keeps Guidance unused
    # for both checks, then spends it on the reaction on the enemy's turn.
    harness.command(Stride((Position(3, 2),)))
    first = harness.command(
        Strike("rapier_fighter", attack_id="shortsword"),
        expected_status=ResultStatus.PAUSED,
    )
    assert harness.pending_choice(
        kind="guidance_use", owner_actor_id="fleet_fighter", options=("keep",)
    )
    first_roll = harness.choose(
        kind="guidance_use",
        owner_actor_id="fleet_fighter",
        option_id="keep",
        expected_status=ResultStatus.PAUSED,
    )
    assert _check(first_roll).map_penalty == 0
    harness.choose(
        kind="attack_hero_reroll", owner_actor_id="fleet_fighter", option_id="keep"
    )
    assert first.inspection.choice is not None

    second = harness.command(
        Strike("rapier_fighter", attack_id="shortsword"),
        expected_status=ResultStatus.PAUSED,
    )
    assert second.inspection.choice is not None
    second_roll = harness.choose(
        kind="guidance_use",
        owner_actor_id="fleet_fighter",
        option_id="keep",
        expected_status=ResultStatus.PAUSED,
    )
    assert _check(second_roll).map_penalty == -4
    harness.choose(
        kind="attack_hero_reroll", owner_actor_id="fleet_fighter", option_id="keep"
    )
    assert harness.inspection.turn_actor_id == "rapier_fighter"

    movement = harness.command(
        Stride((Position(5, 2),)), expected_status=ResultStatus.PAUSED
    )
    assert movement.inspection.choice is not None
    harness.choose(
        kind="reaction",
        owner_actor_id="fleet_fighter",
        option_id="accept",
        expected_status=ResultStatus.PAUSED,
    )
    guided = harness.choose(
        kind="guidance_use",
        owner_actor_id="fleet_fighter",
        option_id="use",
        expected_status=ResultStatus.PAUSED,
    )
    original = _check(guided)
    assert original.die == 8
    assert original.map_penalty == 0
    assert original.attack_count == 1
    assert original.modifier == 10
    assert original.modifier_breakdown[-1].source == "Guidance"
    assert harness.actor("fleet_fighter").effects == ()
    assert harness.actor("fleet_fighter").guidance_immune_until_round == 601

    # Save the actual nested Hero choice after the reaction has consumed
    # Guidance. The restored reroll must retain its already-committed +1.
    assert harness.pending_choice(
        kind="attack_hero_reroll",
        owner_actor_id="fleet_fighter",
        options=("spend_hero_point",),
    )
    harness.checkpoint(tmp_path / "guided-reaction-hero-choice.json")
    rerolled = harness.choose(
        kind="attack_hero_reroll",
        owner_actor_id="fleet_fighter",
        option_id="spend_hero_point",
    )
    reroll_check = _check(rerolled)
    assert reroll_check.die == 20
    assert reroll_check.degree is DegreeOfSuccess.CRITICAL_SUCCESS
    assert reroll_check.map_penalty == 0 and reroll_check.modifier == 10
    assert reroll_check.modifier_breakdown[-1].source == "Guidance"
    assert harness.actor("fleet_fighter").hero_points == 0
    assert harness.actor("rapier_fighter").hp == 1
    assert harness.actor("rapier_fighter").position == Position(5, 2)
    assert harness.actor("rapier_fighter").actions_remaining == 2

    harness.end_turn(expected_actor_id="fighter_m")
    harness.command(Stride((Position(2, 1), Position(3, 1), Position(4, 1))))
    knockout = harness.command(
        ViciousSwing("rapier_fighter", attack_id="longsword"),
        expected_status=ResultStatus.PAUSED,
    )
    assert _check(knockout).degree is DegreeOfSuccess.CRITICAL_SUCCESS
    harness.choose(
        kind="attack_hero_reroll",
        owner_actor_id="fighter_m",
        option_id="keep",
        expected_status=ResultStatus.PAUSED,
    )
    harness.choose(
        kind="heroic_recovery_damage",
        owner_actor_id="rapier_fighter",
        option_id="normal",
    )
    assert harness.actor("rapier_fighter").unconscious
    assert harness.inspection.turn_actor_id == "guard_dog"
    harness.end_turn(expected_actor_id="cleric_c")
    assert harness.inspection.round_number == 2

    # The consumed bonus cannot help another check, and the one-hour immunity
    # rejects an immediate attempt to apply a fresh Guidance.
    before_rejected_cast = harness.inspection
    rejected = harness.game.execute(Cast("guidance", "fleet_fighter"))
    assert rejected.status is ResultStatus.REJECTED
    assert "legal target" in rejected.message
    assert harness.inspection == before_rejected_cast

    lance = harness.command(
        Cast("divine_lance", "guard_dog"), expected_status=ResultStatus.PAUSED
    )
    lance_check = _check(lance)
    assert lance_check.modifier == 7
    assert all(term.source != "Guidance" for term in lance_check.modifier_breakdown)
    harness.choose(
        kind="spell_attack_hero_reroll",
        owner_actor_id="cleric_c",
        option_id="keep",
    )
    assert harness.actor("guard_dog").hp == harness.actor("guard_dog").max_hp
    harness.end_turn(expected_actor_id="fleet_fighter")

    harness.command(Stride((Position(4, 3),)))
    fleet_check = harness.command(Strike("guard_dog", attack_id="shortsword"))
    spent_guidance_check = _check(fleet_check)
    assert spent_guidance_check.die == 20
    assert spent_guidance_check.modifier == 9
    assert all(
        term.source != "Guidance"
        for term in spent_guidance_check.modifier_breakdown
    )
    assert harness.actor("guard_dog").dead
    harness.assert_ended()
    assert harness.inspection.winner_team == "blue"
    assert harness.inspection.choice is None


def test_s3_interrupted_preparation_spends_heal_then_uses_cantrip_and_finishes(
    tmp_path: Path,
) -> None:
    harness = _start(
        "s3_interrupted_preparation",
        ("rapier_fighter", "cleric_c", "fighter_m", "fighter_r", "elite_guard_dog"),
        (
            10, 4,  # Rapier Strike injures C for 5.
            20, 1, 1,  # Critical reaction: rapier die and deadly d8.
            20, 6, 6,  # Guided Vicious Swing knocks out the rapier fighter.
            20, 6, 10,  # Shortbow critical and deadly d10 finish the dog.
        ),
    )

    # The encounter itself creates the Heal target's injury; no state is
    # patched before the spell and reaction interaction.
    injury = harness.command(
        Strike("cleric_c", attack_id="rapier"),
        expected_status=ResultStatus.PAUSED,
    )
    assert _check(injury).degree is DegreeOfSuccess.SUCCESS
    harness.choose(
        kind="attack_hero_reroll",
        owner_actor_id="rapier_fighter",
        option_id="keep",
    )
    assert harness.actor("cleric_c").hp == 12
    harness.end_turn(expected_actor_id="cleric_c")

    before_cast_hp = harness.actor("cleric_c").hp
    assert not _slot(harness, "ordinary_heal_1").spent
    started = harness.command(
        Cast(
            "heal",
            "cleric_c",
            actions=2,
            slot_id="ordinary_heal_1",
        ),
        expected_status=ResultStatus.PAUSED,
    )
    assert any(event.kind == "cast_started" for event in started.events)
    assert harness.pending_choice(
        kind="reaction", owner_actor_id="rapier_fighter", options=("accept",)
    )
    assert harness.actor("cleric_c").actions_remaining == 1
    assert _slot(harness, "ordinary_heal_1").spent

    reaction = harness.choose(
        kind="reaction",
        owner_actor_id="rapier_fighter",
        option_id="accept",
        expected_status=ResultStatus.PAUSED,
    )
    reaction_check = _check(reaction)
    assert reaction_check.degree is DegreeOfSuccess.CRITICAL_SUCCESS
    assert reaction_check.map_penalty == 0
    assert harness.pending_choice(
        kind="attack_hero_reroll",
        owner_actor_id="rapier_fighter",
        options=("keep",),
    )
    harness.checkpoint(tmp_path / "interrupted-heal-reaction-hero-choice.json")

    disrupted = harness.choose(
        kind="attack_hero_reroll",
        owner_actor_id="rapier_fighter",
        option_id="keep",
    )
    assert any(event.kind == "disrupted" for event in disrupted.events)
    assert not any(
        event.kind in {"healing", "heal_roll", "spell_willingness"}
        for event in disrupted.events
    )
    assert harness.inspection.choice is None
    assert harness.actor("cleric_c").hp == before_cast_hp - 5 == 7
    assert harness.actor("cleric_c").actions_remaining == 1
    assert _slot(harness, "ordinary_heal_1").spent
    assert not harness.actor("rapier_fighter").reaction_available

    # A later cantrip uses C's remaining action without spending any additional
    # prepared slot, proving the disrupted slot's provenance remains isolated.
    slot_state_after_disruption = tuple(
        (slot.slot_id, slot.spent) for slot in harness.actor("cleric_c").prepared_slots
    )
    guidance = harness.command(Cast("guidance", "fighter_m"))
    assert any(event.kind == "effect_applied" for event in guidance.events)
    assert tuple(
        (slot.slot_id, slot.spent) for slot in harness.actor("cleric_c").prepared_slots
    ) == slot_state_after_disruption
    assert harness.inspection.turn_actor_id == "fighter_m"

    harness.command(Stride((Position(2, 1), Position(3, 1))))
    swing = harness.command(
        ViciousSwing("rapier_fighter", attack_id="longsword"),
        expected_status=ResultStatus.PAUSED,
    )
    assert swing.inspection.choice is not None
    harness.choose(
        kind="guidance_use",
        owner_actor_id="fighter_m",
        option_id="use",
        expected_status=ResultStatus.PAUSED,
    )
    harness.choose(
        kind="attack_hero_reroll",
        owner_actor_id="fighter_m",
        option_id="keep",
        expected_status=ResultStatus.PAUSED,
    )
    swing_result = harness.choose(
        kind="heroic_recovery_damage",
        owner_actor_id="rapier_fighter",
        option_id="normal",
    )
    assert any(event.damage is not None for event in swing_result.events)
    assert harness.actor("rapier_fighter").unconscious
    assert harness.inspection.in_progress
    assert harness.inspection.turn_actor_id == "fighter_r"

    shot = harness.command(
        Strike("elite_guard_dog", attack_id="shortbow"),
        expected_status=ResultStatus.PAUSED,
    )
    assert _check(shot).degree is DegreeOfSuccess.CRITICAL_SUCCESS
    finished = harness.choose(
        kind="attack_hero_reroll",
        owner_actor_id="fighter_r",
        option_id="keep",
    )
    damage = next(event.damage for event in finished.events if event.damage is not None)
    assert damage is not None and damage.total == 22
    assert harness.actor("elite_guard_dog").dead
    harness.assert_ended()
    assert harness.inspection.winner_team == "blue"
    assert harness.inspection.choice is None
