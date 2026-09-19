"""Complete public-engine regressions for S3 effect interactions."""

from pathlib import Path

from pf2e.checks import DegreeOfSuccess
from pf2e.content import get_setup
from pf2e.encounter import Encounter
from pf2e.model import (
    Cast,
    Interact,
    Position,
    ResultStatus,
    Strike,
    Stride,
    ViciousSwing,
)
from interaction_helpers import EncounterHarness


def _keep_attack(harness: EncounterHarness, paused, owner_actor_id: str):
    choice = harness.pending_choice(
        kind="attack_hero_reroll",
        owner_actor_id=owner_actor_id,
        options=("keep",),
    )
    check = next(event.check for event in paused.events if event.check is not None)
    assert check is not None
    return harness.choose(
        kind="attack_hero_reroll",
        owner_actor_id=owner_actor_id,
        option_id="keep",
        expected_status=None,
    ), check


def test_s3_void_against_finesse_crosses_dex_str_damage_expiry_and_deadly(
    tmp_path: Path,
) -> None:
    # Initiative is C, Rapier, M, R, then the elite dog. The rapier fighter
    # survives Void Warp's critical failure and gets a turn under enfeebled 1.
    rolls = (
        12, 10, 20, 18, 1,  # initiative
        1, 1, 1,  # failed Fortitude save, then critical-failure Void Warp damage
        10, 1, 10,  # Rapier Strike and the enfeebled longsword Strike
        20, 1, 14, 1,  # M's two Strikes against the dog
        12, 1,  # R's Strike against the dog
        1,  # dog's failed Strike
        20, 1, 1, 1,  # Vicious Swing check, two weapon dice, then deadly d8
        20, 1, 14, 1,  # M weakens the rapier fighter
        12, 1, 12, 1,  # R knocks out both remaining enemies
    )
    harness = EncounterHarness(
        Encounter.start(get_setup("s3_void_against_finesse"), rolls=rolls),
        "s3_void_against_finesse",
        max_commands=100,
        max_rounds=6,
    )
    harness.keep_initiative()
    assert harness.inspection.turn_actor_id == "cleric_c"

    paused = harness.command(
        Cast("void_warp", "rapier_fighter"), expected_status=ResultStatus.PAUSED
    )
    harness.pending_choice(
        kind="spell_save_hero_reroll",
        owner_actor_id="rapier_fighter",
        options=("keep",),
    )
    original_save = next(event.check for event in paused.events if event.check is not None)
    assert original_save is not None
    assert original_save.die == 1 and original_save.degree is DegreeOfSuccess.CRITICAL_FAILURE
    harness.checkpoint(tmp_path / "void-save-choice.json")
    voided = harness.choose(
        kind="spell_save_hero_reroll",
        owner_actor_id="rapier_fighter",
        option_id="keep",
    )
    void_damage = next(event.damage for event in voided.events if event.damage is not None)
    assert void_damage is not None and void_damage.total == 4
    rapier = harness.actor("rapier_fighter")
    assert rapier.hp == 17
    effect = next(effect for effect in rapier.effects if effect.kind == "enfeebled")
    assert effect.value == 1 and effect.source_actor_id == "cleric_c"

    # C closes to melee so both attacks can happen inside the effect's duration.
    harness.command(Stride((Position(2, 2), Position(3, 2), Position(4, 2))))
    rapier_attack = harness.command(
        Strike("cleric_c", attack_id="rapier"), expected_status=ResultStatus.PAUSED
    )
    rapier_result, rapier_check = _keep_attack(harness, rapier_attack, "rapier_fighter")
    assert rapier_check.modifier == 9  # Finesse uses Dex despite enfeebled.
    rapier_damage = next(event.damage for event in rapier_result.events if event.damage is not None)
    assert rapier_damage is not None
    assert rapier_damage.components[0].modifier == 0
    assert harness.actor("cleric_c").hp == 16

    harness.command(Interact("draw", "longsword"))
    longsword_attack = harness.command(
        Strike("cleric_c", attack_id="longsword"), expected_status=ResultStatus.PAUSED
    )
    _longsword_result, longsword_check = _keep_attack(
        harness, longsword_attack, "rapier_fighter"
    )
    assert longsword_check.map_penalty == -5
    assert longsword_check.modifier_breakdown[0].amount == 5
    assert longsword_check.modifier == 0

    # The blue fighters attack the elite dog while the effect remains in force.
    assert harness.inspection.turn_actor_id == "fighter_m"
    harness.command(
        Stride((Position(2, 1), Position(3, 1), Position(4, 1), Position(5, 1))),
        expected_status=ResultStatus.PAUSED,
    )
    harness.pending_choice(
        kind="reaction", owner_actor_id="rapier_fighter", options=("decline",)
    )
    harness.choose(
        kind="reaction", owner_actor_id="rapier_fighter", option_id="decline"
    )
    m_first = harness.command(
        Strike("elite_guard_dog", attack_id="longsword"),
        expected_status=ResultStatus.PAUSED,
    )
    _keep_attack(harness, m_first, "fighter_m")
    m_second = harness.command(
        Strike("elite_guard_dog", attack_id="longsword"),
        expected_status=ResultStatus.PAUSED,
    )
    _keep_attack(harness, m_second, "fighter_m")

    assert harness.inspection.turn_actor_id == "fighter_r"
    harness.command(Stride((Position(2, 2), Position(3, 1), Position(4, 0))))
    r_dog_attack = harness.command(
        Strike("elite_guard_dog", attack_id="fist"),
        expected_status=ResultStatus.PAUSED,
    )
    _keep_attack(harness, r_dog_attack, "fighter_r")
    harness.end_turn(expected_actor_id="elite_guard_dog")
    assert harness.inspection.turn_actor_id == "elite_guard_dog"
    harness.command(Strike("fighter_m", attack_id="jaws"))
    assert harness.actor("fighter_m").hp == 21

    harness.end_turn(expected_actor_id="cleric_c")
    assert harness.inspection.round_number == 2
    assert not any(effect.kind == "enfeebled" for effect in harness.actor("rapier_fighter").effects)
    harness.command(
        Stride((Position(4, 3),)), expected_status=ResultStatus.PAUSED
    )
    harness.pending_choice(
        kind="reaction", owner_actor_id="rapier_fighter", options=("decline",)
    )
    harness.choose(
        kind="reaction", owner_actor_id="rapier_fighter", option_id="decline"
    )
    harness.end_turn(expected_actor_id="rapier_fighter")

    # Vicious Swing uses rapier's deadly d8 as a separate die after ordinary
    # critical doubling; this is the live weapon, not a fabricated damage path.
    swing = harness.command(
        ViciousSwing("fighter_m", attack_id="rapier"),
        expected_status=ResultStatus.PAUSED,
    )
    swing_result, swing_check = _keep_attack(harness, swing, "rapier_fighter")
    assert swing_check.degree is DegreeOfSuccess.CRITICAL_SUCCESS
    deadly = next(event.damage for event in swing_result.events if event.damage is not None)
    assert deadly is not None and deadly.adjustment == "deadly_after_critical"
    assert deadly.components[0].rolls == (1, 1)
    assert deadly.multiplier == 2
    assert deadly.components[1].source == "rapier deadly"
    assert (deadly.components[1].dice_sides, deadly.components[1].rolls, deadly.components[1].amount) == (
        8, (1,), 1
    )
    assert deadly.total == 7

    harness.end_turn(expected_actor_id="fighter_m")
    assert harness.inspection.turn_actor_id == "fighter_m"
    first_finish = harness.command(
        Strike("rapier_fighter", attack_id="longsword"),
        expected_status=ResultStatus.PAUSED,
    )
    _keep_attack(harness, first_finish, "fighter_m")
    second_finish = harness.command(
        Strike("rapier_fighter", attack_id="longsword"),
        expected_status=ResultStatus.PAUSED,
    )
    _keep_attack(harness, second_finish, "fighter_m")
    assert harness.actor("rapier_fighter").hp == 2
    harness.end_turn(expected_actor_id="fighter_r")
    assert harness.inspection.turn_actor_id == "fighter_r"

    harness.command(Stride((Position(4, 1),)))
    rapier_knockout = harness.command(
        Strike("rapier_fighter", attack_id="fist"),
        expected_status=ResultStatus.PAUSED,
    )
    _keep_attack(harness, rapier_knockout, "fighter_r")
    rapier = harness.actor("rapier_fighter")
    assert (rapier.hp, rapier.dying, rapier.unconscious) == (0, 0, True)
    assert harness.inspection.in_progress  # Its conscious dog ally is still fighting.

    dog_knockout = harness.command(
        Strike("elite_guard_dog", attack_id="fist"),
        expected_status=ResultStatus.PAUSED,
    )
    _keep_attack(harness, dog_knockout, "fighter_r")
    assert harness.actor("elite_guard_dog").defeated
    assert harness.actor("rapier_fighter").unconscious
    harness.assert_ended()
    assert harness.inspection.winner_team == "blue"


def test_s3_emanation_edge_shares_one_roll_and_excludes_the_35_foot_dog(
    tmp_path: Path,
) -> None:
    rolls = (
        12, 10, 8, 20, 1,  # initiative: elite dog, M, R, C, then distant dog
        15, 4, 17, 1,  # elite dog injures the caster and R
        10, 1, 1,  # M hits the elite dog, then misses
        10, 1, 20, 1, 1,  # R wounds the outside dog, then crits the elite dog
        4,  # one shared three-action Heal die
        1,  # the outside dog misses M after approaching
        20, 1, 1, 20, 1,  # M's critical Vicious Swing and follow-up
        20, 1, 20, 1,  # R's two critical attacks against the approaching dog
    )
    harness = EncounterHarness(
        Encounter.start(get_setup("s3_emanation_edge"), rolls=rolls),
        "s3_emanation_edge",
        max_commands=100,
        max_rounds=6,
    )
    harness.keep_initiative()
    assert harness.inspection.turn_actor_id == "elite_guard_dog"

    harness.command(
        Stride(
            (
                Position(4, 1),
                Position(3, 1),
                Position(3, 2),
                Position(3, 3),
                Position(2, 3),
            )
        )
    )
    first_jaw = harness.command(
        Strike("cleric_c", attack_id="jaws"), expected_status=ResultStatus.COMPLETED
    )
    assert next(event.damage for event in first_jaw.events if event.damage is not None).total == 7
    second_jaw = harness.command(
        Strike("fighter_r", attack_id="jaws"), expected_status=ResultStatus.COMPLETED
    )
    assert next(event.damage for event in second_jaw.events if event.damage is not None).total == 4
    assert harness.actor("cleric_c").hp == 10
    assert harness.actor("fighter_r").hp == 17

    harness.command(Stride((Position(2, 1), Position(2, 2))))
    m_first = harness.command(
        Strike("elite_guard_dog", attack_id="longsword"),
        expected_status=ResultStatus.PAUSED,
    )
    _keep_attack(harness, m_first, "fighter_m")
    m_second = harness.command(
        Strike("elite_guard_dog", attack_id="longsword"),
        expected_status=ResultStatus.PAUSED,
    )
    _keep_attack(harness, m_second, "fighter_m")
    r_strike = harness.command(
        Strike("guard_dog_35", attack_id="shortbow"),
        expected_status=ResultStatus.PAUSED,
    )
    _keep_attack(harness, r_strike, "fighter_r")
    r_second = harness.command(
        Strike("elite_guard_dog", attack_id="shortbow"),
        expected_status=ResultStatus.PAUSED,
    )
    _keep_attack(harness, r_second, "fighter_r")
    harness.end_turn(expected_actor_id="cleric_c")

    assert harness.actor("elite_guard_dog").hp < harness.actor("elite_guard_dog").max_hp
    outside_hp_before_heal = harness.actor("guard_dog_35").hp
    assert outside_hp_before_heal == 7
    cleric = harness.actor("cleric_c")
    heal_slot = next(
        slot for slot in cleric.prepared_slots if slot.slot_id == "ordinary_heal_1"
    )
    assert not heal_slot.spent
    harness.command(
        Cast("heal", actions=3, slot_id="ordinary_heal_1"),
        expected_status=ResultStatus.PAUSED,
    )
    harness.pending_choice(
        kind="spell_self_inclusion",
        owner_actor_id="cleric_c",
        options=("include",),
    )
    assert next(
        slot for slot in harness.actor("cleric_c").prepared_slots
        if slot.slot_id == "ordinary_heal_1"
    ).spent
    harness.checkpoint(tmp_path / "emanation-self-inclusion.json")
    healed = harness.choose(
        kind="spell_self_inclusion",
        owner_actor_id="cleric_c",
        option_id="include",
    )
    heal_rolls = [event for event in healed.events if event.kind == "heal_roll"]
    assert len(heal_rolls) == 1 and "1d8 (4) = 4" in heal_rolls[0].text
    healed_targets = {
        event.target_id for event in healed.events if event.kind == "healing"
    }
    assert healed_targets == {"fighter_m", "fighter_r", "cleric_c", "elite_guard_dog"}
    assert not any(event.damage is not None for event in healed.events)
    assert harness.actor("cleric_c").hp == 14
    assert harness.actor("fighter_r").hp == 21
    assert harness.actor("elite_guard_dog").hp == 14
    assert harness.actor("fighter_m").hp == 21
    outside = harness.actor("guard_dog_35")
    assert outside.hp == outside_hp_before_heal and outside.position == Position(8, 2)
    spent_slots = {
        slot.slot_id for slot in harness.actor("cleric_c").prepared_slots if slot.spent
    }
    assert spent_slots == {"ordinary_heal_1"}

    harness.command(
        Stride(
            (
                Position(7, 2),
                Position(6, 2),
                Position(5, 2),
                Position(4, 2),
                Position(3, 2),
                Position(3, 3),
            )
        ),
        expected_status=ResultStatus.PAUSED,
    )
    harness.pending_choice(
        kind="reaction", owner_actor_id="fighter_m", options=("decline",)
    )
    harness.choose(kind="reaction", owner_actor_id="fighter_m", option_id="decline")
    harness.command(Strike("fighter_m", attack_id="jaws"))
    assert harness.actor("fighter_m").hp == 21
    harness.end_turn(expected_actor_id="elite_guard_dog")
    harness.end_turn(expected_actor_id="fighter_m")  # Elite dog declines to act this round.

    swing = harness.command(
        ViciousSwing("elite_guard_dog", attack_id="longsword"),
        expected_status=ResultStatus.PAUSED,
    )
    _keep_attack(harness, swing, "fighter_m")
    follow_up = harness.command(
        Strike("elite_guard_dog", attack_id="longsword"),
        expected_status=ResultStatus.PAUSED,
    )
    _keep_attack(harness, follow_up, "fighter_m")
    assert harness.actor("elite_guard_dog").defeated

    harness.command(
        Stride((Position(1, 1), Position(2, 1), Position(3, 1), Position(3, 2)))
    )
    dog_first = harness.command(
        Strike("guard_dog_35", attack_id="fist"),
        expected_status=ResultStatus.PAUSED,
    )
    _keep_attack(harness, dog_first, "fighter_r")
    dog_second = harness.command(
        Strike("guard_dog_35", attack_id="fist"),
        expected_status=ResultStatus.PAUSED,
    )
    _keep_attack(harness, dog_second, "fighter_r")
    dog = harness.actor("guard_dog_35")
    assert dog.hp == 0 and dog.unconscious
    harness.assert_ended()
    assert harness.inspection.winner_team == "blue"
