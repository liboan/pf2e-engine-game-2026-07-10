"""Public engine checks for spell and health continuations in S3."""

from pathlib import Path

import pytest

from pf2e.content import S3_SETUP
from pf2e.encounter import Encounter
from pf2e.model import (
    Cast,
    EndTurn,
    Interact,
    Position,
    ResultStatus,
    Stand,
    Strike,
    Stride,
    ViciousSwing,
)


def _keep_start_choices(game: Encounter) -> None:
    while game.inspect().choice is not None:
        choice = game.inspect().choice
        assert choice is not None
        assert choice.kind in ("initiative_hero_reroll", "initiative_tie")
        option_id = "keep" if any(option.option_id == "keep" for option in choice.options) else choice.options[0].option_id
        game.choose(choice.choice_id, option_id)


def _actor(game: Encounter, actor_id: str):
    return next(actor for actor in game.inspect().actors if actor.actor_id == actor_id)


def _knock_down_fighter_r(*, extra_rolls: tuple[int, ...] = ()) -> Encounter:
    """Reach an unconscious PC using only admitted public encounter actions."""
    game = Encounter.start(
        S3_SETUP,
        rolls=(20, 19, 10, 1, 2, 3, 20, 8, *extra_rolls),
    )
    _keep_start_choices(game)
    assert game.inspect().turn_actor_id == "fighter_m"
    assert game.execute(Stride((Position(1, 1),))).status is ResultStatus.COMPLETED
    attack = game.execute(Strike("fighter_r", attack_id="longsword"))
    choice = attack.inspection.choice
    assert attack.status is ResultStatus.PAUSED
    assert choice is not None and choice.kind == "attack_hero_reroll"
    health = game.choose(choice.choice_id, "keep")
    choice = health.inspection.choice
    assert choice is not None and choice.kind == "heroic_recovery_damage"
    game.choose(choice.choice_id, "normal")
    fighter = _actor(game, "fighter_r")
    assert fighter.hp == 0 and fighter.dying == 2 and fighter.unconscious
    assert game.execute(EndTurn()).status is ResultStatus.COMPLETED
    assert game.inspect().turn_actor_id == "cleric_c"
    return game


def test_divine_lance_hero_choice_round_trips_and_keeps_individual_damage_dice(tmp_path: Path) -> None:
    game = Encounter.start(S3_SETUP, rolls=(1, 2, 20, 3, 4, 5, 20, 4, 3))
    _keep_start_choices(game)
    assert game.inspect().turn_actor_id == "cleric_c"

    paused = game.execute(Cast("divine_lance", "guard_dog_c"))
    choice = paused.inspection.choice
    assert paused.status is ResultStatus.PAUSED
    assert choice is not None and choice.kind == "spell_attack_hero_reroll"
    assert choice.owner_actor_id == "cleric_c"
    path = tmp_path / "divine-lance.json"
    game.save(path)
    restored = Encounter.load(path)
    assert restored.inspect() == paused.inspection

    kept = restored.choose(choice.choice_id, "keep")
    damage = next(event.damage for event in kept.events if event.damage is not None)
    assert damage is not None and damage.components[0].rolls == (4, 3)
    assert damage.total == 14
    assert _actor(restored, "guard_dog_c").hp == 0


def test_void_warp_save_hero_choice_belongs_to_target_and_round_trips(tmp_path: Path) -> None:
    game = Encounter.start(S3_SETUP, rolls=(1, 2, 20, 3, 4, 5, 8, 20, 4, 3))
    _keep_start_choices(game)
    paused = game.execute(Cast("void_warp", "fighter_m"))
    choice = paused.inspection.choice
    assert paused.status is ResultStatus.PAUSED
    assert choice is not None and choice.kind == "spell_save_hero_reroll"
    assert choice.owner_actor_id == "fighter_m"

    path = tmp_path / "void-warp-save.json"
    game.save(path)
    restored = Encounter.load(path)
    assert restored.inspect() == paused.inspection
    rerolled = restored.choose(choice.choice_id, "spend_hero_point")
    check = next(event.check for event in rerolled.events if event.check is not None)
    assert check is not None and check.die == 20 and check.dc == 17
    assert _actor(restored, "fighter_m").hero_points == 0
    damage = next(event.damage for event in rerolled.events if event.damage is not None)
    assert damage is not None and damage.total == 0
    assert _actor(restored, "fighter_m").hp == 21


def test_guidance_use_and_hero_reroll_preserve_bonus_and_saved_dice(tmp_path: Path) -> None:
    game = Encounter.start(S3_SETUP, rolls=(1, 2, 20, 3, 4, 5, 1, 20, 4, 3))
    _keep_start_choices(game)
    assert game.execute(Cast("guidance", "cleric_c")).status is ResultStatus.COMPLETED

    guidance_path = tmp_path / "guidance-effect.json"
    game.save(guidance_path)
    restored = Encounter.load(guidance_path)
    assert restored.inspect() == game.inspect()
    attack = restored.execute(Cast("divine_lance", "guard_dog_c"))
    choice = attack.inspection.choice
    assert attack.status is ResultStatus.PAUSED
    assert choice is not None and choice.kind == "guidance_use"
    assert choice.owner_actor_id == "cleric_c"

    choice_path = tmp_path / "guidance-choice.json"
    restored.save(choice_path)
    restored = Encounter.load(choice_path)
    assert restored.inspect() == attack.inspection
    reroll_prompt = restored.choose(choice.choice_id, "use")
    choice = reroll_prompt.inspection.choice
    assert reroll_prompt.status is ResultStatus.PAUSED
    assert choice is not None and choice.kind == "spell_attack_hero_reroll"
    reroll_path = tmp_path / "guidance-hero-reroll.json"
    restored.save(reroll_path)
    restored = Encounter.load(reroll_path)
    result = restored.choose(choice.choice_id, "spend_hero_point")
    check = next(event.check for event in result.events if event.check is not None)
    assert check is not None and check.die == 20 and check.modifier == 8
    assert (check.modifier_breakdown[-1].modifier_type, check.modifier_breakdown[-1].source) == (
        "status", "Guidance",
    )
    assert _actor(restored, "cleric_c").hero_points == 0
    assert _actor(restored, "cleric_c").effects == ()
    assert _actor(restored, "cleric_c").guidance_immune_until_round == restored.inspect().round_number + 600
    damage = next(event.damage for event in result.events if event.damage is not None)
    assert damage is not None and damage.components[0].rolls == (4, 3) and damage.total == 14


def test_void_warp_enfeebled_modifies_strength_damage_but_not_dexterity_attack() -> None:
    game = Encounter.start(S3_SETUP, rolls=(1, 19, 20, 2, 3, 4, 1, 1, 1, 12, 4))
    _keep_start_choices(game)
    assert game.inspect().turn_actor_id == "cleric_c"
    save = game.execute(Cast("void_warp", "fighter_r"))
    choice = save.inspection.choice
    assert choice is not None and choice.kind == "spell_save_hero_reroll"
    assert choice.owner_actor_id == "fighter_r"
    game.choose(choice.choice_id, "keep")
    effect = _actor(game, "fighter_r").effects[0]
    assert (effect.kind, effect.source_actor_id, effect.value) == ("enfeebled", "cleric_c", 1)

    game.execute(EndTurn())
    assert game.inspect().turn_actor_id == "fighter_r"
    assert game.execute(Stride((Position(2, 2), Position(3, 2), Position(4, 1)))).status is ResultStatus.COMPLETED
    attack = game.execute(Strike("guard_dog_a", attack_id="fist"))
    choice = attack.inspection.choice
    assert choice is not None and choice.kind == "attack_hero_reroll"
    assert next(event.check for event in attack.events if event.check is not None).modifier == 9
    result = game.choose(choice.choice_id, "keep")
    damage = next(event.damage for event in result.events if event.damage is not None)
    assert damage is not None and damage.components[0].modifier == 0 and damage.total == 4
    assert _actor(game, "fighter_r").effects[0] == effect


@pytest.mark.parametrize(
    ("actions", "heal_roll", "expected_hp", "slot_id"),
    ((1, 8, 8, "ordinary_heal_1"), (2, 4, 12, "ordinary_heal_2")),
)
def test_heal_single_target_modes_require_willingness_and_save(
    tmp_path: Path,
    actions: int,
    heal_roll: int,
    expected_hp: int,
    slot_id: str,
) -> None:
    game = _knock_down_fighter_r(extra_rolls=(heal_roll,))
    if actions == 1:
        assert game.execute(Stride((Position(1, 3),))).status is ResultStatus.COMPLETED
    paused = game.execute(Cast("heal", "fighter_r", actions=actions, slot_id=slot_id))
    choice = paused.inspection.choice
    assert paused.status is ResultStatus.PAUSED
    assert choice is not None and choice.kind == "spell_willingness"
    assert choice.owner_actor_id == "fighter_r"

    path = tmp_path / f"heal-{actions}-action.json"
    game.save(path)
    restored = Encounter.load(path)
    assert restored.inspect() == paused.inspection
    restored.choose(choice.choice_id, "willing")
    fighter = _actor(restored, "fighter_r")
    assert (fighter.hp, fighter.dying, fighter.wounded, fighter.unconscious) == (
        expected_hp, 0, 1, False,
    )
    slot = next(slot for slot in _actor(restored, "cleric_c").prepared_slots if slot.slot_id == slot_id)
    assert slot.spent


def test_three_action_heal_uses_one_shared_roll_on_enemies_and_optional_self(tmp_path: Path) -> None:
    game = _knock_down_fighter_r(extra_rolls=(4,))
    paused = game.execute(Cast("heal", actions=3, slot_id="font_heal_1"))
    choice = paused.inspection.choice
    assert paused.status is ResultStatus.PAUSED
    assert choice is not None and choice.kind == "spell_self_inclusion"
    assert choice.owner_actor_id == "cleric_c"

    path = tmp_path / "heal-emanation.json"
    game.save(path)
    restored = Encounter.load(path)
    assert restored.inspect() == paused.inspection
    result = restored.choose(choice.choice_id, "include")
    assert sum(event.kind == "heal_roll" for event in result.events) == 1
    assert {event.target_id for event in result.events if event.kind == "healing"} == {
        "fighter_m", "fighter_r", "cleric_c", "guard_dog_a", "guard_dog_b", "guard_dog_c",
    }
    assert _actor(restored, "fighter_r").hp == 4
    assert _actor(restored, "cleric_c").hp == 17
    assert next(
        slot for slot in _actor(restored, "cleric_c").prepared_slots
        if slot.slot_id == "font_heal_1"
    ).spent


def test_stabilize_uses_health_helper_on_dying_pc() -> None:
    game = _knock_down_fighter_r()
    result = game.execute(Cast("stabilize", "fighter_r"))
    assert result.status is ResultStatus.COMPLETED
    fighter = _actor(game, "fighter_r")
    assert (fighter.hp, fighter.dying, fighter.wounded, fighter.unconscious, fighter.dead) == (
        0, 0, 1, True, False,
    )


def test_public_knockout_heal_stand_and_retrieve_after_save_load(tmp_path: Path) -> None:
    game = Encounter.start(S3_SETUP, rolls=(20, 19, 10, 1, 2, 3, 20, 8, 8, 8))
    _keep_start_choices(game)
    assert game.inspect().turn_actor_id == "fighter_m"
    assert game.execute(Stride((Position(1, 1),))).status is ResultStatus.COMPLETED

    swing = game.execute(ViciousSwing("fighter_r", attack_id="longsword"))
    choice = swing.inspection.choice
    assert choice is not None and choice.kind == "attack_hero_reroll"
    damage = game.choose(choice.choice_id, "keep")
    choice = damage.inspection.choice
    assert choice is not None and choice.kind == "heroic_recovery_damage"
    knocked_out = game.choose(choice.choice_id, "normal")
    fighter = _actor(game, "fighter_r")
    assert fighter.hp == 0 and fighter.dying == 2 and fighter.unconscious and fighter.prone
    assert fighter.held_items == ()
    assert knocked_out.inspection.ground_items == ((Position(1, 2), ("shortbow",)),)
    assert knocked_out.inspection.turn_actor_id == "cleric_c"

    heal = game.execute(Cast("heal", "fighter_r", actions=2, slot_id="ordinary_heal_1"))
    choice = heal.inspection.choice
    assert choice is not None and choice.kind == "spell_willingness"
    path = tmp_path / "knockout-heal.json"
    game.save(path)
    restored = Encounter.load(path)
    assert restored.inspect() == heal.inspection
    restored.choose(choice.choice_id, "willing")
    fighter = _actor(restored, "fighter_r")
    assert (fighter.hp, fighter.dying, fighter.wounded, fighter.unconscious, fighter.prone) == (
        16, 0, 1, False, True,
    )
    assert fighter.held_items == ()
    assert restored.inspect().ground_items == ((Position(1, 2), ("shortbow",)),)

    restored.execute(EndTurn())
    while restored.inspect().turn_actor_id != "fighter_r":
        restored.execute(EndTurn())
    assert "stand" in restored.options().available_actions
    assert restored.execute(Stand()).status is ResultStatus.COMPLETED
    assert not _actor(restored, "fighter_r").prone
    assert ("retrieve", "shortbow") in restored.options().interact_options
    assert restored.execute(Interact("retrieve", "shortbow")).status is ResultStatus.COMPLETED
    assert _actor(restored, "fighter_r").held_items == ("shortbow",)
    assert restored.inspect().ground_items == ()
