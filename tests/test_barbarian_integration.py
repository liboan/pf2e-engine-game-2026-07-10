import json
from pathlib import Path

import pytest

from pf2e import EndTurn, Rage, Stride, Strike
from pf2e.content import get_setup
from pf2e.encounter import Encounter
from pf2e.model import Position, ResultStatus
from pf2e.skill_actions import Demoralize


def _actor(game: Encounter, actor_id: str):
    return next(actor for actor in game.inspect().actors if actor.actor_id == actor_id)


def _choose(game: Encounter, option_id: str, owner: str | None = None):
    choice = game.inspect().choice
    assert choice is not None
    return game.choose(choice.choice_id, option_id, owner)


def _keep_barbarian_initiative(game: Encounter) -> None:
    choice = game.inspect().choice
    assert choice is not None
    assert choice.kind == "initiative_hero_reroll"
    assert choice.owner_actor_id == "barbarian_test"
    assert _choose(game, "keep", "barbarian_test").status is ResultStatus.PAUSED


def test_options_publish_supported_skill_action_ids() -> None:
    game = Encounter.start(get_setup("s1_duel"), rolls=(20, 20))

    options = game.options()

    assert {"trip", "grapple", "escape", "demoralize"} <= set(options.available_actions)


def test_quick_tempered_saved_offer_precedes_later_hero_choice_and_keeps_three_actions(
    tmp_path: Path,
) -> None:
    game = Encounter.start(
        get_setup("barbarian_pc_pair_test"),
        rolls=(10, 10, 1),
    )
    _keep_barbarian_initiative(game)
    quick = game.inspect().choice
    assert quick is not None
    assert quick.kind == "family_action"
    assert quick.owner_actor_id == "barbarian_test"
    assert tuple(option.option_id for option in quick.options) == ("accept", "decline")
    assert game.inspect().turn_actor_id is None
    assert all(actor.actions_remaining == 0 for actor in game.inspect().actors)

    path = tmp_path / "quick-tempered-offer.json"
    game.save(path)
    game = Encounter.load(path)
    assert game.inspect().choice == quick

    accepted = _choose(game, "accept", "barbarian_test")
    assert accepted.status is ResultStatus.PAUSED
    fighter_choice = accepted.inspection.choice
    assert fighter_choice is not None
    assert fighter_choice.kind == "initiative_hero_reroll"
    assert fighter_choice.owner_actor_id == "fighter_pair"
    barbarian = _actor(game, "barbarian_test")
    assert barbarian.temporary_hp == 4
    assert barbarian.temporary_hp_source_id == "rage:barbarian_test:1"
    assert barbarian.temporary_hp_expires_at_seconds == 60

    assert _choose(game, "keep", "fighter_pair").status is ResultStatus.PAUSED
    tie = game.inspect().choice
    assert tie is not None and tie.kind == "initiative_tie"
    finished = _choose(game, "barbarian_test")
    assert finished.status is ResultStatus.COMPLETED
    assert finished.inspection.turn_actor_id == "barbarian_test"
    assert _actor(game, "barbarian_test").actions_remaining == 3


def test_ordinary_rage_costs_one_action_persists_and_rejects_bear_weapon_atomically(
    tmp_path: Path,
) -> None:
    game = Encounter.start(get_setup("barbarian_rage_test"), rolls=(20, 1))
    _keep_barbarian_initiative(game)
    assert _choose(game, "decline", "barbarian_test").status is ResultStatus.COMPLETED
    assert {strike.attack_id for strike in game.options().strikes} == {"longsword", "fist"}

    result = game.execute(Rage())
    assert result.status is ResultStatus.COMPLETED
    barbarian = _actor(game, "barbarian_test")
    assert barbarian.actions_remaining == 2
    assert barbarian.ac == 18
    assert barbarian.temporary_hp == 4
    assert barbarian.temporary_hp_source_id == "rage:barbarian_test:1"
    assert barbarian.temporary_hp_expires_at_seconds == 60
    assert {strike.attack_id for strike in game.options().strikes} == {
        "fist", "animal_bear_jaws", "animal_bear_claw"
    }

    before = game.inspect()
    rejected = game.execute(Strike("barbarian_guard", attack_id="longsword"))
    assert rejected.status is ResultStatus.REJECTED
    assert "not currently available" in rejected.message
    assert game.inspect() == before

    path = tmp_path / "ordinary-rage.json"
    game.save(path)
    restored = Encounter.load(path)
    assert restored.inspect() == game.inspect()


def test_public_bear_fight_saves_raging_intimidation_absorbs_temp_hp_and_finishes(
    tmp_path: Path,
) -> None:
    # Initiative, Demoralize, jaws, jaws damage, guard Strike/damage,
    # first claw/damage, agile second claw/damage.
    game = Encounter.start(
        get_setup("barbarian_rage_test"),
        rolls=(20, 1, 10, 10, 5, 14, 5, 10, 6, 12, 1),
    )
    _keep_barbarian_initiative(game)
    assert _choose(game, "accept", "barbarian_test").status is ResultStatus.COMPLETED
    assert _actor(game, "barbarian_test").actions_remaining == 3

    demoralize = game.execute(
        Demoralize("barbarian_guard", use_intimidating_glare=True)
    )
    assert demoralize.status is ResultStatus.PAUSED
    assert demoralize.inspection.choice is not None
    assert demoralize.inspection.choice.owner_actor_id == "barbarian_test"
    path = tmp_path / "raging-demoralize.json"
    game.save(path)
    game = Encounter.load(path)
    demoralize = _choose(game, "keep", "barbarian_test")
    check = next(event.check for event in demoralize.events if event.check is not None)
    assert check is not None and check.total == check.dc == 13
    assert "rage" in check.traits and "visual" in check.traits
    assert "auditory" not in check.traits
    assert all(modifier.amount != -4 for modifier in check.modifier_breakdown)

    assert game.execute(Stride((Position(3, 2),))).status is ResultStatus.COMPLETED
    jaws = game.execute(Strike("barbarian_guard", attack_id="animal_bear_jaws"))
    assert jaws.status is ResultStatus.PAUSED
    jaws = _choose(game, "keep", "barbarian_test")
    jaws_damage = next(event.damage for event in jaws.events if event.damage is not None)
    assert jaws_damage.total == 11
    assert [component.modifier for component in jaws_damage.components] == [4, 2]
    assert game.inspect().turn_actor_id == "barbarian_guard"

    guard_hit = game.execute(Strike("barbarian_test", attack_id="guard_spear"))
    assert guard_hit.status is ResultStatus.COMPLETED
    damage_event = next(event for event in guard_hit.events if event.damage is not None)
    assert damage_event.temporary_hp_absorbed == 4
    assert damage_event.remaining_hp_damage == 3
    barbarian = _actor(game, "barbarian_test")
    assert barbarian.hp == 20 and barbarian.temporary_hp == 0
    assert barbarian.temporary_hp_source_id is None

    assert game.execute(EndTurn()).status is ResultStatus.COMPLETED
    first_claw = game.execute(
        Strike("barbarian_guard", attack_id="animal_bear_claw")
    )
    assert first_claw.status is ResultStatus.PAUSED
    first_claw = _choose(game, "keep", "barbarian_test")
    claw_damage = next(event.damage for event in first_claw.events if event.damage is not None)
    assert claw_damage.total == 11
    assert [component.modifier for component in claw_damage.components] == [4, 1]

    second_claw = game.execute(
        Strike("barbarian_guard", attack_id="animal_bear_claw")
    )
    assert second_claw.status is ResultStatus.PAUSED
    second_claw = _choose(game, "keep", "barbarian_test")
    second_check = next(event.check for event in second_claw.events if event.check is not None)
    second_damage = next(event.damage for event in second_claw.events if event.damage is not None)
    assert second_check.map_penalty == -4
    assert second_damage.total == 6
    assert not second_claw.inspection.in_progress
    assert second_claw.inspection.winner_team == "blue"


def test_saved_health_choice_retains_committed_temp_hp_absorption_and_ends_rage(
    tmp_path: Path,
) -> None:
    # The guard acts first, wounds the healthy Barbarian, then knocks them out
    # on the next round after ordinary Rage supplied a fresh 4-HP pool.
    game = Encounter.start(
        get_setup("barbarian_pc_pair_test"),
        rolls=(10, 9, 20, 20, 6, 20, 6),
    )
    _keep_barbarian_initiative(game)
    assert _choose(game, "decline", "barbarian_test").status is ResultStatus.PAUSED
    assert _choose(game, "keep", "fighter_pair").status is ResultStatus.COMPLETED
    assert game.inspect().turn_actor_id == "barbarian_guard"

    assert game.execute(Stride((Position(3, 1),))).status is ResultStatus.COMPLETED
    first_hit = game.execute(Strike("barbarian_test", attack_id="guard_spear"))
    assert first_hit.status is ResultStatus.COMPLETED
    assert _actor(game, "barbarian_test").hp == 7
    assert game.execute(EndTurn()).status is ResultStatus.COMPLETED

    assert game.execute(Rage()).status is ResultStatus.COMPLETED
    assert _actor(game, "barbarian_test").temporary_hp == 4
    assert game.execute(EndTurn()).status is ResultStatus.COMPLETED
    assert game.execute(EndTurn()).status is ResultStatus.COMPLETED
    assert game.inspect().turn_actor_id == "barbarian_guard"

    knockout = game.execute(Strike("barbarian_test", attack_id="guard_spear"))
    assert knockout.status is ResultStatus.PAUSED
    choice = knockout.inspection.choice
    assert choice is not None and choice.kind == "heroic_recovery_damage"
    assert choice.owner_actor_id == "barbarian_test"
    assert choice.details == ("Damage rolled: 16 piercing; 4 temporary HP absorbed.",)
    paused = _actor(game, "barbarian_test")
    assert paused.hp == 7 and paused.temporary_hp == 0
    assert paused.barbarian_state is not None and paused.barbarian_state.rage is not None

    path = tmp_path / "barbarian-health-choice.json"
    game.save(path)
    game = Encounter.load(path)
    resolved = _choose(game, "normal", "barbarian_test")
    damage = next(event for event in resolved.events if event.damage is not None)
    assert damage.temporary_hp_absorbed == 4
    assert damage.remaining_hp_damage == 12
    barbarian = _actor(game, "barbarian_test")
    assert barbarian.hp == 0 and barbarian.dying == 2 and barbarian.unconscious
    assert barbarian.temporary_hp == 0 and barbarian.temporary_hp_source_id is None
    assert barbarian.barbarian_state is not None
    assert barbarian.barbarian_state.rage is None


def test_encounter_outcome_clears_only_the_remaining_rage_pool() -> None:
    game = Encounter.start(
        get_setup("barbarian_rage_test"),
        rolls=(20, 1, 20, 10),
    )
    _keep_barbarian_initiative(game)
    assert _choose(game, "accept", "barbarian_test").status is ResultStatus.COMPLETED
    assert game.execute(Stride((Position(3, 2),))).status is ResultStatus.COMPLETED
    strike = game.execute(Strike("barbarian_guard", attack_id="animal_bear_jaws"))
    assert strike.status is ResultStatus.PAUSED
    finished = _choose(game, "keep", "barbarian_test")
    assert not finished.inspection.in_progress
    barbarian = _actor(game, "barbarian_test")
    assert barbarian.temporary_hp == 0
    assert barbarian.temporary_hp_source_id is None
    assert barbarian.temporary_hp_expires_at_seconds is None
    assert barbarian.barbarian_state is not None
    assert barbarian.barbarian_state.rage is None


def test_save_rejects_impossible_current_rage_pool_amount_and_expiry(
    tmp_path: Path,
) -> None:
    game = Encounter.start(get_setup("barbarian_rage_test"), rolls=(20, 1))
    _keep_barbarian_initiative(game)
    assert _choose(game, "accept", "barbarian_test").status is ResultStatus.COMPLETED
    path = tmp_path / "rage-pool.json"
    game.save(path)
    original = json.loads(path.read_text(encoding="utf-8"))

    too_large = json.loads(json.dumps(original))
    too_large["state"]["creatures"]["barbarian_test"]["temporary_hp"] = 5
    path.write_text(json.dumps(too_large), encoding="utf-8")
    with pytest.raises(ValueError, match="Rage temporary HP amount"):
        Encounter.load(path)

    wrong_expiry = json.loads(json.dumps(original))
    wrong_expiry["state"]["creatures"]["barbarian_test"][
        "temporary_hp_expires_at_seconds"
    ] = 59
    path.write_text(json.dumps(wrong_expiry), encoding="utf-8")
    with pytest.raises(ValueError, match="mismatched Rage temporary HP expiry"):
        Encounter.load(path)
