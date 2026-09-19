"""Independent public-play review of carrying a party into a second scene.

The staged rooms below use existing reviewed character definitions.  They are
diagnostic encounter fixtures, not additional class builds.
"""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from types import MappingProxyType

import pytest

import pf2e.content as content
from pf2e.encounter import Encounter
from pf2e.model import (
    Cast,
    CreaturePlacement,
    EncounterSetup,
    EndTurn,
    Interact,
    Position,
    RaiseShield,
    ResultStatus,
    Stand,
    Strike,
)


SHIELD_ID = "carry_shield:steel_shield"


def _actor(game: Encounter, actor_id: str):
    return next(actor for actor in game.inspect().actors if actor.actor_id == actor_id)


def _choose(game: Encounter, option_id: str):
    choice = game.inspect().choice
    assert choice is not None
    return game.choose(choice.choice_id, option_id, choice.owner_actor_id)


def _keep_initiative(game: Encounter) -> None:
    while (choice := game.inspect().choice) is not None:
        assert choice.kind == "initiative_hero_reroll"
        result = _choose(game, "keep")
        assert result.status in {ResultStatus.PAUSED, ResultStatus.COMPLETED}


def _scene_pair(monkeypatch: pytest.MonkeyPatch) -> tuple[EncounterSetup, EncounterSetup]:
    first = EncounterSetup(
        setup_id="scene_carry_review_first",
        name="Scene Carry Review: Recovery and Equipment",
        width=5,
        height=4,
        placements=(
            CreaturePlacement("carry_shield", content.STEEL_SHIELD_FIGHTER_M.definition_id, "Shield Fighter", "blue", Position(1, 1)),
            CreaturePlacement("carry_dog_a", content.ELITE_GUARD_DOG.definition_id, "Elite Guard Dog A", "red", Position(2, 1)),
            CreaturePlacement("carry_warpriest", content.WARPRIEST_C.definition_id, "Warpriest", "blue", Position(1, 2)),
            CreaturePlacement("carry_archer", content.SHORTBOW_FIGHTER_R.definition_id, "Archer", "blue", Position(2, 2)),
        ),
    )
    second = EncounterSetup(
        setup_id="scene_carry_review_second",
        name="Scene Carry Review: Fresh Opposition",
        width=5,
        height=4,
        placements=(
            CreaturePlacement("carry_archer", content.SHORTBOW_FIGHTER_R.definition_id, "Archer", "blue", Position(1, 1)),
            CreaturePlacement("carry_dog_b", content.GUARD_DOG.definition_id, "Guard Dog B", "red", Position(2, 1)),
            CreaturePlacement("carry_shield", content.STEEL_SHIELD_FIGHTER_M.definition_id, "Shield Fighter", "blue", Position(1, 2)),
            CreaturePlacement("carry_warpriest", content.WARPRIEST_C.definition_id, "Warpriest", "blue", Position(1, 3)),
        ),
    )
    monkeypatch.setattr(
        content,
        "_STAGED_SETUPS",
        MappingProxyType(
            {
                **content._STAGED_SETUPS,
                first.setup_id: first,
                second.setup_id: second,
            }
        ),
    )
    return first, second


def test_changed_shield_ammo_hero_and_wounded_carry_through_saved_two_fight_play(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    first, second = _scene_pair(monkeypatch)
    # Four initiative dice; three dog Strikes; Warpriest Heal; saved archer
    # Strike and reroll; then scene-B initiative and the final shot.
    rolls = (
        20, 15, 10, 1,
        15, 4, 20, 4, 20, 4,
        8,
        1, 20, 6, 6,
        20, 1, 10, 5,
        20, 4, 4,
    )
    game = Encounter.start(first, rolls=rolls)
    _keep_initiative(game)
    assert game.inspect().turn_actor_id == "carry_shield"

    assert game.execute(RaiseShield()).status is ResultStatus.COMPLETED
    assert game.execute(EndTurn()).status is ResultStatus.COMPLETED
    assert game.inspect().turn_actor_id == "carry_dog_a"

    blocked = game.execute(Strike("carry_shield", attack_id="jaws"))
    assert blocked.status is ResultStatus.PAUSED
    assert blocked.inspection.choice is not None
    assert blocked.inspection.choice.kind == "shield_block"
    assert _choose(game, "block").status is ResultStatus.COMPLETED
    assert _actor(game, "carry_shield").shields[0].hp == 18

    assert game.execute(Strike("carry_archer", attack_id="jaws")).status is ResultStatus.COMPLETED
    knocked_out = game.execute(Strike("carry_archer", attack_id="jaws"))
    assert knocked_out.status is ResultStatus.PAUSED
    assert knocked_out.inspection.choice is not None
    assert knocked_out.inspection.choice.kind == "heroic_recovery_damage"
    assert _choose(game, "normal").status is ResultStatus.COMPLETED
    assert _actor(game, "carry_archer").dying == 2

    healed = game.execute(
        Cast("heal", "carry_archer", actions=2, slot_id="ordinary_heal_1")
    )
    assert healed.status is ResultStatus.PAUSED
    assert healed.inspection.choice is not None
    assert healed.inspection.choice.kind == "spell_willingness"
    assert _choose(game, "willing").status is ResultStatus.COMPLETED
    recovered = _actor(game, "carry_archer")
    assert (recovered.hp, recovered.dying, recovered.wounded) == (16, 0, 1)
    assert game.execute(EndTurn()).status is ResultStatus.COMPLETED

    # Knockout moves the archer in initiative. Let the intervening actors pass;
    # this also reaches the shield owner's next start and expires its defense.
    while game.inspect().turn_actor_id != "carry_archer":
        assert game.execute(EndTurn()).status is ResultStatus.COMPLETED
    assert game.execute(Stand()).status is ResultStatus.COMPLETED
    assert game.execute(Interact("retrieve", "shortbow")).status is ResultStatus.COMPLETED
    assert not _actor(game, "carry_shield").shields[0].raised

    offered = game.execute(Strike("carry_dog_a", attack_id="shortbow"))
    assert offered.status is ResultStatus.PAUSED
    assert offered.inspection.choice is not None
    assert offered.inspection.choice.kind == "attack_hero_reroll"
    assert _actor(game, "carry_archer").ammunition == (("arrow", 19),)
    decision_path = tmp_path / "scene-carry-saved-hero-choice.json"
    game.save(decision_path)
    game = Encounter.load(decision_path)
    finished = _choose(game, "spend_hero_point")
    assert finished.status is ResultStatus.COMPLETED
    assert not game.inspect().in_progress

    carried_before = {
        "shield_hp": _actor(game, "carry_shield").shields[0].hp,
        "ammo": _actor(game, "carry_archer").ammunition,
        "hero": _actor(game, "carry_archer").hero_points,
        "hp": _actor(game, "carry_archer").hp,
        "wounded": _actor(game, "carry_archer").wounded,
        "heal_spent": next(
            slot.spent
            for slot in _actor(game, "carry_warpriest").prepared_slots
            if slot.slot_id == "ordinary_heal_1"
        ),
    }
    assert carried_before == {
        "shield_hp": 18,
        "ammo": (("arrow", 19),),
        "hero": 0,
        "hp": 16,
        "wounded": 1,
        "heal_spent": True,
    }
    shield_item = deepcopy(game._state.item_instances[SHIELD_ID])

    transitioned = game.next_encounter(second)
    assert transitioned.status is ResultStatus.PAUSED
    _keep_initiative(game)
    assert game.inspect().turn_actor_id == "carry_archer"
    assert game.inspect().round_number == 1
    archer = _actor(game, "carry_archer")
    assert (archer.actions_remaining, archer.strikes_this_turn, archer.diagonals_this_turn) == (3, 0, 0)
    assert archer.reaction_available
    assert game._state.actor_start_counts == {
        "carry_archer": 1,
        "carry_dog_b": 0,
        "carry_shield": 0,
        "carry_warpriest": 0,
    }
    assert game._state.actor_end_counts == {actor_id: 0 for actor_id in game._state.creatures}
    assert game._state.item_instances[SHIELD_ID] == shield_item
    assert _actor(game, "carry_shield").shields[0].hp == carried_before["shield_hp"]
    assert archer.ammunition == carried_before["ammo"]
    assert (archer.hero_points, archer.hp, archer.wounded) == (0, 16, 1)
    assert next(
        slot.spent
        for slot in _actor(game, "carry_warpriest").prepared_slots
        if slot.slot_id == "ordinary_heal_1"
    )

    second_finish = game.execute(Strike("carry_dog_b", attack_id="shortbow"))
    assert second_finish.status is ResultStatus.COMPLETED
    assert not second_finish.inspection.in_progress
    assert _actor(game, "carry_dog_b").defeated
    assert _actor(game, "carry_archer").ammunition == (("arrow", 18),)


def test_exhausted_next_initiative_and_invalid_party_transfer_preserve_state_and_dice(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _scene_pair(monkeypatch)
    # A finished state is needed for the public transition boundary.  This
    # narrow setup makes that state directly without altering the carry rules.
    quick_first = EncounterSetup(
        setup_id="scene_carry_review_atomic_first",
        name="Scene Carry Review: Atomic First Fight",
        width=3,
        height=2,
        placements=(
            CreaturePlacement("carry_shield", content.STEEL_SHIELD_FIGHTER_M.definition_id, "Shield Fighter", "blue", Position(1, 0)),
            CreaturePlacement("atomic_dog", content.GUARD_DOG.definition_id, "Guard Dog", "red", Position(2, 0)),
        ),
    )
    quick_second = EncounterSetup(
        setup_id="scene_carry_review_atomic_second",
        name="Scene Carry Review: Atomic Second Fight",
        width=3,
        height=2,
        placements=(
            CreaturePlacement("carry_shield", content.STEEL_SHIELD_FIGHTER_M.definition_id, "Shield Fighter", "blue", Position(1, 0)),
            CreaturePlacement("atomic_dog_b", content.GUARD_DOG.definition_id, "Guard Dog B", "red", Position(2, 0)),
        ),
    )
    invalid = EncounterSetup(
        setup_id="scene_carry_review_invalid_party",
        name="Scene Carry Review: Invalid Party Transfer",
        width=3,
        height=2,
        placements=(
            CreaturePlacement("different_pc", content.STEEL_SHIELD_FIGHTER_M.definition_id, "Different Fighter", "blue", Position(1, 0)),
            CreaturePlacement("atomic_dog_c", content.GUARD_DOG.definition_id, "Guard Dog C", "red", Position(2, 0)),
        ),
    )
    monkeypatch.setattr(
        content,
        "_STAGED_SETUPS",
        MappingProxyType(
            {
                **content._STAGED_SETUPS,
                quick_first.setup_id: quick_first,
                quick_second.setup_id: quick_second,
                invalid.setup_id: invalid,
            }
        ),
    )

    game = Encounter.start(quick_first, rolls=(20, 1, 20, 4, 1))
    _keep_initiative(game)
    offered = game.execute(Strike("atomic_dog", attack_id="longsword"))
    assert offered.status is ResultStatus.PAUSED
    assert _choose(game, "keep").status is ResultStatus.COMPLETED
    assert not game.inspect().in_progress

    before_state = deepcopy(game._state)
    before_dice = game._dice.to_data()
    exhausted = game.next_encounter(quick_second)
    assert exhausted.status is ResultStatus.REJECTED
    assert "sequence exhausted" in exhausted.message
    assert game._state == before_state
    assert game._dice.to_data() == before_dice

    invalid_result = game.next_encounter(invalid)
    assert invalid_result.status is ResultStatus.REJECTED
    assert "same PC actor IDs" in invalid_result.message
    assert game._state == before_state
    assert game._dice.to_data() == before_dice


def test_nonzero_clock_halo_runic_and_flee_deadlines_round_trip(tmp_path: Path) -> None:
    game = Encounter.start(
        content.ANGELIC_FIRST_CAST_SETUP,
        rolls=(
            20, 1, 10, 20, 4, 4,
            20, 1, 1,
            1,
        ),
    )
    _keep_initiative(game)
    halo = game.execute(Cast("angelic_halo", actions=1))
    assert halo.status is ResultStatus.PAUSED
    assert halo.inspection.choice is not None
    assert halo.inspection.choice.kind == "spell_blood_magic_recipient"
    assert _choose(game, "sorcerer_ally").status is ResultStatus.COMPLETED
    assert game.execute(Cast("divine_lance", "sorcerer_dog")).status is ResultStatus.COMPLETED
    assert not game.inspect().in_progress

    assert game.refocus("angelic_sorcerer").status is ResultStatus.COMPLETED
    assert game.inspect().world_time_seconds == 600
    transitioned = game.next_encounter(content.ANGELIC_NEXT_ENCOUNTER_SETUP)
    assert transitioned.status is ResultStatus.PAUSED
    _keep_initiative(game)
    assert game.inspect().turn_actor_id == "angelic_sorcerer"

    halo = game.execute(Cast("angelic_halo", actions=1))
    assert halo.status is ResultStatus.PAUSED
    assert _choose(game, "sorcerer_ally").status is ResultStatus.COMPLETED
    runic = game.execute(
        Cast(
            "runic_weapon",
            item_id="sorcerer_ally:longsword",
            slot_id="angelic_rank1",
        )
    )
    assert runic.status is ResultStatus.PAUSED
    assert runic.inspection.choice is not None
    assert runic.inspection.choice.kind == "spell_willingness"
    assert _choose(game, "willing").status is ResultStatus.COMPLETED
    while game.inspect().turn_actor_id != "angelic_sorcerer":
        assert game.execute(EndTurn()).status is ResultStatus.COMPLETED
    assert game.inspect().world_time_seconds == 606

    fear = game.execute(Cast("fear", "sorcerer_dog_b", slot_id="angelic_rank1"))
    assert fear.status is ResultStatus.COMPLETED
    halo_effect = next(
        effect for effect in game._state.active_effects
        if effect.kind == "angelic_halo"
    )
    fleeing_effect = next(
        effect for effect in game._state.active_effects
        if effect.kind == "fleeing"
    )
    runic_effect = next(
        effect for effect in game._state.active_item_effects
        if effect.kind == "runic_weapon"
    )
    assert (
        halo_effect.expires_at_source_start,
        halo_effect.expires_at_world_time,
    ) == (11, 660)
    assert (
        runic_effect.expires_at_source_start,
        runic_effect.expires_at_world_time,
    ) == (11, 660)
    assert (
        fleeing_effect.expires_at_source_start,
        fleeing_effect.expires_at_world_time,
    ) == (3, 612)

    path = tmp_path / "scene-b-nonzero-duration-effects.json"
    game.save(path)
    restored = Encounter.load(path)
    assert restored.inspect() == game.inspect()
    assert restored._state.active_effects == game._state.active_effects
    assert restored._state.active_item_effects == game._state.active_item_effects
