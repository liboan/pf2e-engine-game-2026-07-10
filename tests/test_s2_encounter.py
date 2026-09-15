"""S2 public encounter, equipment, damage, and save semantics."""

import json
from pathlib import Path

import pytest

from pf2e.checks import Modifier, combine_modifiers
from pf2e.content import S2_PACK_ATTACK_SETUP, S2_PC_DUEL_SETUP, S2_SETUP
from pf2e.encounter import Encounter
from pf2e.model import (
    EndTurn,
    Position,
    ResultStatus,
    Strike,
    Stride,
    ViciousSwing,
)


def _keep_initiative(game: Encounter) -> None:
    while game.inspect().choice is not None:
        choice = game.inspect().choice
        assert choice is not None
        assert choice.kind == "initiative_hero_reroll"
        game.choose(choice.choice_id, "keep")


def _actor(game: Encounter, actor_id: str):
    return next(actor for actor in game.inspect().actors if actor.actor_id == actor_id)


def test_strike_can_target_a_creature_on_the_same_team() -> None:
    game = Encounter.start(S2_SETUP, rolls=(20, 19, 1, 2, 10, 1))
    _keep_initiative(game)
    assert game.inspect().turn_actor_id == "fighter_a"
    assert game.execute(Stride((Position(1, 2),))).status is ResultStatus.COMPLETED
    assert "fighter_b" in game.options().strike_targets

    paused = game.execute(Strike("fighter_b", attack_id="longsword"))
    assert paused.status is ResultStatus.PAUSED  # attacker may keep or reroll
    choice = paused.inspection.choice
    assert choice is not None and choice.kind == "attack_hero_reroll"
    result = game.choose(choice.choice_id, "keep")
    check = next(event.check for event in result.events if event.check is not None)
    damage = next(event.damage for event in result.events if event.damage is not None)
    assert check is not None and check.dc == 18
    assert damage is not None and damage.total == 5
    assert _actor(game, "fighter_b").hp == 16


def test_nonlethal_fist_knocks_out_ordinary_dog_instead_of_killing_it() -> None:
    game = Encounter.start(S2_SETUP, rolls=(20, 19, 1, 2, 20, 4))
    _keep_initiative(game)
    assert game.execute(Stride((Position(2, 1), Position(3, 1), Position(4, 1)))).status is ResultStatus.COMPLETED

    paused = game.execute(Strike("guard_dog_a", attack_id="fist"))
    choice = paused.inspection.choice
    assert paused.status is ResultStatus.PAUSED
    assert choice is not None and choice.kind == "attack_hero_reroll"
    result = game.choose(choice.choice_id, "keep")
    dog = _actor(game, "guard_dog_a")
    assert dog.hp == 0 and dog.unconscious and dog.prone
    assert not dog.dead and dog.defeated
    assert any(event.damage is not None and event.damage.total == 16 for event in result.events)


def test_lethal_intent_with_nonlethal_attack_applies_typed_penalty() -> None:
    game = Encounter.start(S2_SETUP, rolls=(20, 19, 1, 2, 20, 4))
    _keep_initiative(game)
    assert game.execute(Stride((Position(2, 1), Position(3, 1), Position(4, 1)))).status is ResultStatus.COMPLETED
    paused = game.execute(Strike("guard_dog_a", attack_id="fist", nonlethal=False))
    choice = paused.inspection.choice
    assert choice is not None and choice.kind == "attack_hero_reroll"
    strike_event = next(event for event in paused.events if event.check is not None)
    check = strike_event.check
    assert check is not None and check.modifier == 7
    assert check.modifier_breakdown == (
        Modifier(9, "untyped", "printed attack modifier"),
        Modifier(-2, "circumstance", "nonlethal intent"),
    )


def test_forged_pending_check_degree_is_rejected_on_load(tmp_path: Path) -> None:
    game = Encounter.start(S2_SETUP, rolls=(20, 19, 1, 2, 1, 8))
    _keep_initiative(game)
    assert game.execute(Stride((Position(2, 1), Position(3, 1), Position(4, 1)))).status is ResultStatus.COMPLETED
    paused = game.execute(Strike("guard_dog_a", attack_id="fist"))
    choice = paused.inspection.choice
    assert choice is not None and choice.kind == "attack_hero_reroll"

    path = tmp_path / "pending-check.json"
    game.save(path)
    saved = json.loads(path.read_text(encoding="utf-8"))
    pending = saved["state"]["pending_choice"]
    check = pending["check"]
    assert (check["die"], check["modifier"], check["dc"], check["total"]) == (1, 9, 15, 10)
    check["total"] = 29
    check["degree_before_adjustments"] = 3
    check["degree"] = 3
    check["adjustments"] = []
    path.write_text(json.dumps(saved), encoding="utf-8")

    with pytest.raises(ValueError, match="inconsistent pending check"):
        Encounter.load(path)


def test_vicious_swing_uses_pre_activity_map_and_two_damage_dice() -> None:
    game = Encounter.start(S2_PC_DUEL_SETUP, rolls=(20, 19, 1, 20, 8, 8))
    _keep_initiative(game)

    first = game.execute(Strike("fighter_b", attack_id="fist"))
    first_choice = first.inspection.choice
    assert first_choice is not None and first_choice.kind == "attack_hero_reroll"
    game.choose(first_choice.choice_id, "keep")

    swing = game.execute(ViciousSwing("fighter_b"))
    swing_choice = swing.inspection.choice
    assert swing.status is ResultStatus.PAUSED
    assert swing_choice is not None and swing_choice.kind == "attack_hero_reroll"
    paused = game.choose(swing_choice.choice_id, "keep")
    health_choice = paused.inspection.choice
    assert paused.status is ResultStatus.PAUSED
    assert health_choice is not None and health_choice.kind == "heroic_recovery_damage"
    result = game.choose(health_choice.choice_id, "normal")
    check = next(event.check for event in paused.events if event.check is not None)
    damage = next(event.damage for event in result.events if event.damage is not None)
    assert check is not None and check.map_penalty == -5 and check.attack_count == 2
    assert damage is not None and damage.components[0].rolls == (8, 8)
    assert damage.total == 40  # critical doubles both weapon dice and Strength
    assert "2d8 (8+8) + 4 = 20" in next(
        event.text for event in result.events if event.damage is not None
    )
    assert _actor(game, "fighter_b").hp == 0
    assert _actor(game, "fighter_b").dying == 2


def test_pack_attack_adds_a_die_for_two_other_allies_in_reach() -> None:
    game = Encounter.start(S2_PACK_ATTACK_SETUP, rolls=(1, 20, 19, 18, 12, 3, 4))
    _keep_initiative(game)
    assert game.inspect().turn_actor_id == "guard_dog_a"
    result = game.execute(Strike("fighter_target", attack_id="jaws"))
    damage = next(event.damage for event in result.events if event.damage is not None)
    assert damage is not None
    assert damage.components[0].rolls == (3, 4)
    assert damage.total == 8
    assert "2d4 (3+4) + 1 = 8" in next(
        event.text for event in result.events if event.damage is not None
    )
    assert _actor(game, "fighter_target").hp == 13


def test_dead_ally_does_not_satisfy_pack_attack_threshold() -> None:
    game = Encounter.start(S2_PACK_ATTACK_SETUP, rolls=(1, 20, 19, 18, 20, 4, 20, 3))
    _keep_initiative(game)
    assert game.inspect().turn_actor_id == "guard_dog_a"
    killed_ally = game.execute(Strike("guard_dog_b", attack_id="jaws"))
    assert any(actor.actor_id == "guard_dog_b" and actor.dead for actor in killed_ally.inspection.actors)

    result = game.execute(Strike("fighter_target", attack_id="jaws"))
    damage = next(event.damage for event in result.events if event.damage is not None)
    assert damage is not None
    assert damage.components[0].rolls == (3,)
    assert damage.total == 8


def test_full_public_s2_encounter_completes_without_state_patching() -> None:
    game = Encounter.start(S2_SETUP, rolls=(20, 19, 1, 2, 20, 1, 20, 1))
    _keep_initiative(game)
    assert game.inspect().turn_actor_id == "fighter_a"
    assert game.execute(Stride((Position(2, 1), Position(3, 1), Position(4, 1)))).status is ResultStatus.COMPLETED
    first = game.execute(Strike("guard_dog_a", attack_id="longsword"))
    assert first.status is ResultStatus.PAUSED
    choice = first.inspection.choice
    assert choice is not None and choice.kind == "attack_hero_reroll"
    game.choose(choice.choice_id, "keep")
    assert _actor(game, "guard_dog_a").dead
    assert game.execute(EndTurn()).status is ResultStatus.COMPLETED

    assert game.inspect().turn_actor_id == "fighter_b"
    assert game.execute(Stride((Position(2, 3), Position(3, 3), Position(4, 3)))).status is ResultStatus.COMPLETED
    second = game.execute(Strike("guard_dog_b", attack_id="longsword"))
    choice = second.inspection.choice
    assert second.status is ResultStatus.PAUSED
    assert choice is not None and choice.kind == "attack_hero_reroll"
    finished = game.choose(choice.choice_id, "keep")
    assert finished.status is ResultStatus.COMPLETED
    assert finished.inspection.in_progress is False
    assert finished.inspection.winner_team == "blue"
    assert _actor(game, "guard_dog_a").defeated
    assert _actor(game, "guard_dog_b").defeated


def test_same_type_penalties_and_bonuses_use_only_the_strongest_in_each_direction() -> None:
    attack_modifiers = (
        Modifier(9, "untyped", "printed attack modifier"),
        Modifier(-2, "circumstance", "lethal intent with a nonlethal attack"),
        Modifier(-2, "circumstance", "prone attack penalty"),
    )
    assert [modifier.modifier_type for modifier in attack_modifiers[1:]] == ["circumstance", "circumstance"]
    assert combine_modifiers(attack_modifiers) == 7

    defense_modifiers = (
        Modifier(18, "untyped", "printed AC"),
        Modifier(-2, "circumstance", "off-guard from prone"),
        Modifier(-2, "circumstance", "off-guard from flanking"),
        Modifier(1, "circumstance", "lesser creature cover"),
        Modifier(4, "circumstance", "take cover"),
    )
    assert combine_modifiers(defense_modifiers) == 20


def test_pc_stable_zero_strike_is_rejected_before_a_hero_reroll_prompt(tmp_path: Path) -> None:
    # Fighter A critically knocks Fighter B out, then spends B's only point on
    # Heroic Recovery. A remains conscious, so the team can continue and a
    # Strike into the unresolved stabilized-0-HP rule must stop atomically.
    game = Encounter.start(S2_SETUP, rolls=(20, 19, 1, 2, 20, 8))
    _keep_initiative(game)
    assert game.inspect().turn_actor_id == "fighter_a"
    assert game.execute(Stride((Position(1, 2),))).status is ResultStatus.COMPLETED
    attack = game.execute(Strike("fighter_b", attack_id="longsword"))
    check_choice = attack.inspection.choice
    assert check_choice is not None and check_choice.kind == "attack_hero_reroll"
    game.choose(check_choice.choice_id, "keep")
    recovery = game.inspect().choice
    assert recovery is not None and recovery.kind == "heroic_recovery_damage"
    result = game.choose(recovery.choice_id, "heroic_recovery")
    assert result.status is ResultStatus.COMPLETED
    assert _actor(game, "fighter_b").hp == 0
    assert _actor(game, "fighter_b").unconscious and _actor(game, "fighter_b").dying == 0

    options = game.options()
    assert "fighter_b" in options.strike_targets
    before_path = tmp_path / "stable-before.json"
    after_path = tmp_path / "stable-after.json"
    game.save(before_path)
    unsupported = game.execute(Strike("fighter_b", attack_id="longsword"))
    game.save(after_path)
    assert unsupported.status is ResultStatus.UNSUPPORTED
    assert "stabilized 0 HP PC" in unsupported.message
    assert unsupported.inspection.choice is None
    assert before_path.read_bytes() == after_path.read_bytes()
