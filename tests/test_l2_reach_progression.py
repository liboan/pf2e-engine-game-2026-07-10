"""L2 Reach Spell sheet and rule-family acceptance tests.

Sources:

* https://2e.aonprd.com/Classes.aspx?ID=32
* https://2e.aonprd.com/Classes.aspx?ID=34
* https://2e.aonprd.com/Classes.aspx?ID=62
* https://2e.aonprd.com/Feats.aspx?ID=4577
* https://2e.aonprd.com/Spells.aspx?ID=1470
"""

from __future__ import annotations

from dataclasses import replace
from types import MappingProxyType

import pytest

import pf2e.content as content
from pf2e.encounter import Encounter
from pf2e.l2_reach_content import (
    ANGELIC_SORCERER_L2_NEXT_SETUP,
    ANGELIC_SORCERER_L2,
    ANGELIC_SORCERER_L2_REACH_SETUP,
    L2_REACH_DEFINITIONS,
    L2_REACH_SETUPS,
    MAESTRO_BARD_L2,
    MAESTRO_BARD_L2_NEXT_SETUP,
    MAESTRO_BARD_L2_REACH_SETUP,
    STORM_DRUID_L2_REACH_SETUP,
    STORM_DRUID_L2_NEXT_SETUP,
    STORM_DRUID_L2,
)
from pf2e.model import (
    Cast,
    Choose,
    CreaturePlacement,
    EncounterSetup,
    EndTurn,
    LingeringComposition,
    Position,
    ReachSpell,
    Release,
    ResultStatus,
    Stride,
)
from pf2e.reach_spell import can_shape_spell, effective_spell_range
from pf2e.spells import SPELLS


@pytest.mark.parametrize(
    ("definition", "hp", "rank_slots", "rank_spells", "new_skill_feat"),
    (
        (MAESTRO_BARD_L2, 28, 3, {"fear", "runic_weapon", "soothe", "command"}, "Intimidating Glare"),
        (STORM_DRUID_L2, 28, 3, {"heal", "runic_weapon"}, "Assurance (Athletics)"),
        (ANGELIC_SORCERER_L2, 24, 4, {"heal", "fear", "runic_weapon", "command"}, "Intimidating Glare"),
    ),
)
def test_level_two_reach_sheets_keep_the_selected_progression(
    definition, hp, rank_slots, rank_spells, new_skill_feat
) -> None:
    assert definition.level == 2
    assert definition.hp == hp
    assert definition.class_dc == 18
    assert definition.spell_attack == 8
    assert definition.spell_dc == 18
    assert "Reach Spell" in definition.feats
    assert new_skill_feat in definition.feats
    assert "reach_spell" in definition.abilities

    if definition.prepared_spells:
        ordinary = tuple(slot for slot in definition.prepared_spells if not slot.cantrip)
        assert len(ordinary) == rank_slots
        assert {slot.spell_id for slot in ordinary} == rank_spells
        assert all(slot.rank == 1 and slot.source == "primal_rank_1" for slot in ordinary)
    else:
        assert len(definition.spontaneous_slots) == 1
        slot = definition.spontaneous_slots[0]
        assert slot.rank == 1 and slot.capacity == rank_slots
        assert {
            spell.spell_id for spell in definition.spontaneous_spells
            if not spell.cantrip and spell.rank == 1
        } == rank_spells


def test_reach_spell_range_is_pure_and_mode_aware() -> None:
    command = SPELLS["command"]
    light = SPELLS["light"]
    runic_touch = replace(SPELLS["runic_weapon"], range_ft=0)
    heal_touch = replace(SPELLS["heal"], range_ft=0)
    heal_ranged = replace(SPELLS["heal"], range_ft=30)

    assert can_shape_spell(command, spell_actions=2)
    assert can_shape_spell(light, spell_actions=2)
    assert can_shape_spell(SPELLS["runic_weapon"], spell_actions=2)
    assert can_shape_spell(SPELLS["heal"], spell_actions=1)
    assert can_shape_spell(SPELLS["heal"], spell_actions=2)
    assert not can_shape_spell(SPELLS["heal"], spell_actions=3)
    assert not can_shape_spell(SPELLS["courageous_anthem"], spell_actions=1)
    assert not can_shape_spell(SPELLS["angelic_halo"], spell_actions=1)

    assert effective_spell_range(command, reach_ready=False) == 30
    assert effective_spell_range(command, reach_ready=True) == 60
    assert effective_spell_range(light, reach_ready=True) == 150
    assert effective_spell_range(runic_touch, reach_ready=True) == 30
    assert effective_spell_range(heal_touch, reach_ready=True) == 30
    assert effective_spell_range(heal_ranged, reach_ready=True) == 60
    assert effective_spell_range(SPELLS["courageous_anthem"], reach_ready=True) is None
    assert SPELLS["command"].range_ft == 30
    assert SPELLS["runic_weapon"].range_ft is None


def test_reach_spell_range_rejects_bad_contract_inputs() -> None:
    with pytest.raises(TypeError, match="SpellDefinition"):
        effective_spell_range(object(), reach_ready=False)
    with pytest.raises(TypeError, match="boolean"):
        effective_spell_range(SPELLS["command"], reach_ready=1)  # type: ignore[arg-type]
    assert not can_shape_spell(SPELLS["command"], spell_actions=1)


def test_reach_spell_is_an_one_action_casting_family_procedure(monkeypatch) -> None:
    """The typed spellshape is reachable before shared range wiring is used."""
    monkeypatch.setattr(
        content,
        "_STAGED_CREATURES",
        MappingProxyType({
            **content._STAGED_CREATURES,
            **{definition.definition_id: definition for definition in L2_REACH_DEFINITIONS},
        }),
    )
    monkeypatch.setattr(
        content,
        "_STAGED_SETUPS",
        MappingProxyType({
            **content._STAGED_SETUPS,
            ANGELIC_SORCERER_L2_REACH_SETUP.setup_id: ANGELIC_SORCERER_L2_REACH_SETUP,
        }),
    )
    game = Encounter.start(ANGELIC_SORCERER_L2_REACH_SETUP, rolls=(20, 1, 1, 20))
    while game.inspect().choice is not None:
        choice = game.inspect().choice
        assert choice is not None
        assert game.choose(choice.choice_id, "keep", choice.owner_actor_id).status in {
            ResultStatus.PAUSED, ResultStatus.COMPLETED,
        }
    while game.inspect().turn_actor_id != "angelic_sorcerer":
        assert game.end_turn().status is ResultStatus.COMPLETED

    before = game._state.creatures["angelic_sorcerer"].actions_remaining
    assert "reach_spell" in game.options().available_actions
    result = game.execute(ReachSpell())
    assert result.status is ResultStatus.COMPLETED
    actor = game._state.creatures["angelic_sorcerer"]
    assert actor.reach_spell_pending
    assert actor.actions_remaining == before - 1
    assert "reach_spell" not in game.options().available_actions
    assert game.execute(ReachSpell()).status is ResultStatus.REJECTED

    # A normal L1 Angelic Sorcerer has neither the feat nor its admitted
    # family ability, so manually submitting the typed command is invalid.
    l1 = Encounter.start(content.ANGELIC_FIRST_CAST_SETUP, rolls=(20, 1, 1))
    _settle_to_turn(l1, "angelic_sorcerer")
    assert l1.execute(ReachSpell()).status is ResultStatus.REJECTED


def _register_l2_reach_content(monkeypatch) -> None:
    monkeypatch.setattr(
        content,
        "_STAGED_CREATURES",
        MappingProxyType({
            **content._STAGED_CREATURES,
            **{definition.definition_id: definition for definition in L2_REACH_DEFINITIONS},
        }),
    )
    monkeypatch.setattr(
        content,
        "_STAGED_SETUPS",
        MappingProxyType({
            **content._STAGED_SETUPS,
            **{setup.setup_id: setup for setup in L2_REACH_SETUPS},
        }),
    )


def _settle_to_turn(game: Encounter, actor_id: str) -> None:
    while game.inspect().choice is not None:
        choice = game.inspect().choice
        assert choice is not None
        option_id = "keep" if any(option.option_id == "keep" for option in choice.options) else choice.options[0].option_id
        assert game.execute(Choose(choice.choice_id, option_id, choice.owner_actor_id)).status in {
            ResultStatus.PAUSED, ResultStatus.COMPLETED,
        }
    while game.inspect().turn_actor_id != actor_id:
        assert game.execute(EndTurn()).status is ResultStatus.COMPLETED


def _resolve_pending(game: Encounter, result):
    while result.status is ResultStatus.PAUSED:
        choice = game.inspect().choice
        assert choice is not None
        option_id = "keep" if any(option.option_id == "keep" for option in choice.options) else choice.options[0].option_id
        result = game.execute(Choose(choice.choice_id, option_id, choice.owner_actor_id))
    return result


def test_reach_spell_extends_prepared_and_spontaneous_public_casts(monkeypatch) -> None:
    _register_l2_reach_content(monkeypatch)

    ordinary_druid = Encounter.start(STORM_DRUID_L2_REACH_SETUP, rolls=(20, 1, 1, 1, 1, 1, 1))
    _settle_to_turn(ordinary_druid, "druid")
    ordinary_druid._state.creatures["druid_target"].position = Position(2, 2)
    ordinary_druid._state.creatures["druid_target"].hp -= 1
    assert _resolve_pending(
        ordinary_druid,
        ordinary_druid.execute(Cast("heal", "druid_target", actions=1, slot_id="druid_heal_one")),
    ).status is ResultStatus.COMPLETED

    druid = Encounter.start(STORM_DRUID_L2_REACH_SETUP, rolls=(20, 1, 1, 1, 1, 1, 1, 1, 1, 1))
    _settle_to_turn(druid, "druid")
    druid._state.creatures["druid_target"].hp -= 1
    rejected = druid.execute(Cast("heal", "druid_target", actions=1, slot_id="druid_heal_one"))
    assert rejected.status is ResultStatus.REJECTED
    assert druid.execute(ReachSpell()).status is ResultStatus.COMPLETED
    resolved = druid.execute(Cast("heal", "druid_target", actions=1, slot_id="druid_heal_one"))
    resolved = _resolve_pending(druid, resolved)
    assert resolved.status is ResultStatus.COMPLETED
    druid_actor = druid._state.creatures["druid"]
    assert druid_actor.reach_spell_pending is False
    assert next(slot for slot in druid_actor.prepared_slots if slot.slot_id == "druid_heal_one").spent

    sorcerer_setup = replace(
        ANGELIC_SORCERER_L2_REACH_SETUP,
        setup_id="angelic_sorcerer_level_2_reach_command",
        placements=(
            ANGELIC_SORCERER_L2_REACH_SETUP.placements[0],
            replace(
                ANGELIC_SORCERER_L2_REACH_SETUP.placements[1],
                actor_id="sorcerer_target",
                definition_id="fighter_m_level_1",
                label="Target Fighter",
            ),
        ),
    )
    monkeypatch.setattr(
        content,
        "_STAGED_SETUPS",
        MappingProxyType({**content._STAGED_SETUPS, sorcerer_setup.setup_id: sorcerer_setup}),
    )
    sorcerer = Encounter.start(sorcerer_setup, rolls=(20, 1, 1, 1, 1, 1, 1, 1, 1, 1))
    _settle_to_turn(sorcerer, "angelic_sorcerer")
    assert sorcerer.execute(Cast("command", "sorcerer_target", spell_mode="stand", slot_id="angelic_rank1")).status is ResultStatus.REJECTED
    assert sorcerer.execute(ReachSpell()).status is ResultStatus.COMPLETED
    command = sorcerer.execute(Cast("command", "sorcerer_target", spell_mode="stand", slot_id="angelic_rank1"))
    command = _resolve_pending(sorcerer, command)
    assert command.status is ResultStatus.COMPLETED
    sorcerer_actor = sorcerer._state.creatures["angelic_sorcerer"]
    assert sorcerer_actor.reach_spell_pending is False
    assert sorcerer_actor.spontaneous_slots[0].remaining == 3


def test_reach_runic_weapon_keeps_its_committed_range_through_saved_reaction(monkeypatch, tmp_path) -> None:
    _register_l2_reach_content(monkeypatch)
    setup = EncounterSetup(
        "storm_druid_level_2_reach_runic_reaction",
        "Level 2 Storm Druid Reach Runic Weapon reaction",
        12,
        5,
        (
            CreaturePlacement("druid", STORM_DRUID_L2.definition_id, "Storm Druid", "blue", Position(1, 2)),
            CreaturePlacement("reach_enemy", "fighter_m_level_1", "Reactive Fighter", "red", Position(2, 2)),
            CreaturePlacement("reach_ally", "fighter_m_weapon_identity_staged", "Reach Ally", "blue", Position(7, 2)),
        ),
    )
    monkeypatch.setattr(
        content,
        "_STAGED_SETUPS",
        MappingProxyType({**content._STAGED_SETUPS, setup.setup_id: setup}),
    )
    game = Encounter.start(setup, rolls=(20, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1))
    _settle_to_turn(game, "druid")
    assert game.execute(ReachSpell()).status is ResultStatus.COMPLETED
    started = game.execute(Cast("runic_weapon", item_id="reach_ally:longsword", slot_id="druid_runic_weapon_two"))
    assert started.status is ResultStatus.PAUSED
    pending = game.inspect().choice
    assert pending is not None and pending.kind == "spell_willingness"
    started = game.execute(Choose(pending.choice_id, "willing", pending.owner_actor_id))
    assert started.status is ResultStatus.PAUSED
    pending = game.inspect().choice
    assert pending is not None and pending.kind == "reaction"
    continuation = game._state.pending_choice.continuation
    assert continuation is not None and continuation.reach_spell_effective_range_ft == 30
    assert game._state.creatures["druid"].reach_spell_pending is False
    assert next(slot for slot in game._state.creatures["druid"].prepared_slots if slot.slot_id == "druid_runic_weapon_two").spent

    save_path = tmp_path / "reach-runic-reaction.json"
    game.save(save_path)
    restored = Encounter.load(save_path)
    pending = restored.inspect().choice
    assert pending is not None and pending.kind == "reaction"
    final = _resolve_pending(restored, restored.execute(Choose(
        pending.choice_id, "decline", pending.owner_actor_id
    )))
    assert final.status is ResultStatus.COMPLETED


def test_l2_bard_reach_does_not_disturb_lingering_or_counter_performance(monkeypatch) -> None:
    _register_l2_reach_content(monkeypatch)
    bard = Encounter.start(MAESTRO_BARD_L2_REACH_SETUP, rolls=(20, 1, 1, 1, 1, 1))
    _settle_to_turn(bard, "maestro_bard")
    assert bard.execute(ReachSpell()).status is ResultStatus.COMPLETED
    # Lingering Composition is an intervening spellshape action; it consumes
    # Reach's pending benefit but remains independently usable.
    assert bard.execute(LingeringComposition()).status is ResultStatus.COMPLETED
    assert bard._state.creatures["maestro_bard"].reach_spell_pending is False
    assert bard._state.creatures["maestro_bard"].focus_points == 1

    counter_setup = replace(
        content.get_setup("maestro_bard_counter_performance_command"),
        setup_id="maestro_bard_level_2_counter_performance",
        placements=tuple(
            replace(placement, definition_id=MAESTRO_BARD_L2.definition_id)
            if placement.actor_id == "maestro_bard" else placement
            for placement in content.get_setup("maestro_bard_counter_performance_command").placements
        ),
    )
    monkeypatch.setattr(
        content,
        "_STAGED_SETUPS",
        MappingProxyType({**content._STAGED_SETUPS, counter_setup.setup_id: counter_setup}),
    )
    counter = Encounter.start(counter_setup, rolls=(20, 1, 1, 1, 15))
    _settle_to_turn(counter, "enemy_witch")
    paused = counter.execute(Cast("command", "beneficiary", spell_mode="stand"))
    assert paused.status is ResultStatus.PAUSED
    choice = counter.inspect().choice
    assert choice is not None and choice.kind == "counter_performance_save_choice"
    assert "counter_performance" in {option.option_id for option in choice.options}


def test_reach_invalidation_and_unshapeable_modes_stay_literal(monkeypatch) -> None:
    """A pending spellshape expires on every intervening public action type.

    The committed-cast snapshot belongs to the shared Encounter continuation;
    this owner-level check demonstrates the public family procedure's visible
    contract, including free Release and end of turn.
    """
    _register_l2_reach_content(monkeypatch)

    bard = Encounter.start(MAESTRO_BARD_L2_REACH_SETUP, rolls=(20, 1, 1, 1, 1, 1))
    _settle_to_turn(bard, "maestro_bard")
    assert bard.execute(ReachSpell()).status is ResultStatus.COMPLETED
    assert bard.execute(Stride((Position(2, 2),))).status is ResultStatus.COMPLETED
    assert bard._state.creatures["maestro_bard"].reach_spell_pending is False

    # Release is a zero-action/free action in this bounded engine and still
    # ends Reach's window.  It must not spend an additional action.
    assert bard.execute(ReachSpell()).status is ResultStatus.COMPLETED
    actions_before_release = bard._state.creatures["maestro_bard"].actions_remaining
    assert bard.execute(Release("rapier")).status is ResultStatus.COMPLETED
    assert bard._state.creatures["maestro_bard"].actions_remaining == actions_before_release
    assert bard._state.creatures["maestro_bard"].reach_spell_pending is False

    druid = Encounter.start(STORM_DRUID_L2_REACH_SETUP, rolls=(20, 1, 1, 1, 1, 1))
    _settle_to_turn(druid, "druid")
    assert druid.execute(ReachSpell()).status is ResultStatus.COMPLETED
    assert druid.execute(EndTurn()).status is ResultStatus.COMPLETED
    assert druid._state.creatures["druid"].reach_spell_pending is False

    sorcerer = Encounter.start(ANGELIC_SORCERER_L2_REACH_SETUP, rolls=(20, 1, 1, 1, 1, 1))
    _settle_to_turn(sorcerer, "angelic_sorcerer")
    assert sorcerer.execute(ReachSpell()).status is ResultStatus.COMPLETED
    halo = sorcerer.execute(Cast("angelic_halo", actions=1))
    assert halo.status is ResultStatus.COMPLETED
    assert any(effect.kind == "angelic_halo" for effect in sorcerer._state.active_effects)
    assert sorcerer._state.creatures["angelic_sorcerer"].reach_spell_pending is False

    anthem = Encounter.start(MAESTRO_BARD_L2_REACH_SETUP, rolls=(20, 1, 1, 1, 1, 1))
    _settle_to_turn(anthem, "maestro_bard")
    assert anthem.execute(ReachSpell()).status is ResultStatus.COMPLETED
    assert anthem.execute(Cast("courageous_anthem", actions=1)).status is ResultStatus.COMPLETED
    assert anthem._state.creatures["maestro_bard"].reach_spell_pending is False


def test_reach_extends_light_and_forbidding_ward_but_never_bypasses_resources(monkeypatch) -> None:
    _register_l2_reach_content(monkeypatch)
    light_setup = EncounterSetup(
        "angelic_sorcerer_level_2_reach_light", "Level 2 Angelic Reach Light",
        26, 32,
        (
            CreaturePlacement("angelic_sorcerer", ANGELIC_SORCERER_L2.definition_id, "Angelic Sorcerer", "blue", Position(1, 2)),
            CreaturePlacement("light_dog", "guard_dog_mc2924", "Guard Dog", "red", Position(2, 2)),
        ),
    )
    ward_setup = EncounterSetup(
        "maestro_bard_level_2_reach_ward", "Level 2 Maestro Reach Forbidding Ward",
        14, 5,
        (
            CreaturePlacement("maestro_bard", MAESTRO_BARD_L2.definition_id, "Maestro Bard", "blue", Position(1, 2)),
            CreaturePlacement("ward_ally", "fighter_m_level_1", "Ward Ally", "blue", Position(8, 2)),
            CreaturePlacement("ward_enemy", "guard_dog_mc2924", "Ward Enemy", "red", Position(9, 2)),
        ),
    )
    monkeypatch.setattr(
        content, "_STAGED_SETUPS",
        MappingProxyType({
            **content._STAGED_SETUPS,
            light_setup.setup_id: light_setup,
            ward_setup.setup_id: ward_setup,
        }),
    )

    light = Encounter.start(light_setup, rolls=(20, 1, 1, 1, 1, 1))
    _settle_to_turn(light, "angelic_sorcerer")
    assert light.execute(Cast("light", point=Position(1, 31), color="reach")).status is ResultStatus.REJECTED
    assert light.execute(ReachSpell()).status is ResultStatus.COMPLETED
    assert light.execute(Cast("light", point=Position(1, 31), color="reach")).status is ResultStatus.COMPLETED
    assert light.inspect().light_orbs[0].point == Position(1, 31)

    ward = Encounter.start(ward_setup, rolls=(20, 1, 1, 1, 1, 1))
    _settle_to_turn(ward, "maestro_bard")
    assert ward.execute(Cast("forbidding_ward", target_ids=("ward_ally", "ward_enemy"))).status is ResultStatus.REJECTED
    assert ward.execute(ReachSpell()).status is ResultStatus.COMPLETED
    assert ward.execute(Cast("forbidding_ward", target_ids=("ward_ally", "ward_enemy"))).status is ResultStatus.COMPLETED
    effect = next(item for item in ward._state.active_effects if item.kind == "forbidding_ward")
    assert (effect.target_actor_id, effect.selected_enemy_actor_id) == ("ward_ally", "ward_enemy")

    exhausted_druid = Encounter.start(STORM_DRUID_L2_REACH_SETUP, rolls=(20, 1, 1, 1, 1, 1))
    _settle_to_turn(exhausted_druid, "druid")
    next(
        slot for slot in exhausted_druid._state.creatures["druid"].prepared_slots
        if slot.slot_id == "druid_heal_one"
    ).spent = True
    assert exhausted_druid.execute(ReachSpell()).status is ResultStatus.COMPLETED
    assert exhausted_druid.execute(Cast("heal", "druid_target", actions=1, slot_id="druid_heal_one")).status is ResultStatus.REJECTED
    assert exhausted_druid._state.creatures["druid"].reach_spell_pending is True

    exhausted_sorcerer = Encounter.start(ANGELIC_SORCERER_L2_REACH_SETUP, rolls=(20, 1, 1, 1, 1, 1))
    _settle_to_turn(exhausted_sorcerer, "angelic_sorcerer")
    exhausted_sorcerer._state.creatures["angelic_sorcerer"].spontaneous_slots[0].remaining = 0
    assert exhausted_sorcerer.execute(ReachSpell()).status is ResultStatus.COMPLETED
    assert exhausted_sorcerer.execute(Cast("heal", "angelic_sorcerer", actions=1, slot_id="angelic_rank1")).status is ResultStatus.REJECTED
    assert exhausted_sorcerer._state.creatures["angelic_sorcerer"].reach_spell_pending is True


def test_l2_prepared_and_spontaneous_recovery_keep_identity_into_next_scene(monkeypatch, tmp_path) -> None:
    _register_l2_reach_content(monkeypatch)
    druid_fight = EncounterSetup(
        "storm_druid_level_2_recovery_fight", "Storm Druid L2 recovery fight", 7, 5,
        (
            CreaturePlacement("druid", STORM_DRUID_L2.definition_id, "Storm Druid", "blue", Position(1, 2)),
            CreaturePlacement("first_druid_dog", "guard_dog_mc2924", "First Guard Dog", "red", Position(3, 2)),
        ),
    )
    sorcerer_fight = EncounterSetup(
        "angelic_sorcerer_level_2_recovery_fight", "Angelic Sorcerer L2 recovery fight", 7, 5,
        (
            CreaturePlacement("angelic_sorcerer", ANGELIC_SORCERER_L2.definition_id, "Angelic Sorcerer", "blue", Position(1, 2)),
            CreaturePlacement("first_sorcerer_dog", "guard_dog_mc2924", "First Guard Dog", "red", Position(3, 2)),
        ),
    )
    monkeypatch.setattr(
        content, "_STAGED_SETUPS",
        MappingProxyType({**content._STAGED_SETUPS, druid_fight.setup_id: druid_fight, sorcerer_fight.setup_id: sorcerer_fight}),
    )

    druid = Encounter.start(druid_fight, rolls=(20, 1, 1, 1, 1, 1, 1))
    _settle_to_turn(druid, "druid")
    druid._state.creatures["first_druid_dog"].hp = 1
    assert druid.execute(Cast("tempest_surge", "first_druid_dog", actions=2)).status is ResultStatus.COMPLETED
    assert druid.inspect().winner_team == "blue"
    assert druid.refocus("druid").status is ResultStatus.COMPLETED
    assert druid.record_rested(("druid",), day_number=2, elapsed_seconds=1).status is ResultStatus.COMPLETED
    preparations = {"druid": {
        "druid_electric_arc": "electric_arc", "druid_guidance": "guidance", "druid_stabilize": "stabilize",
        "druid_tangle_vine": "tangle_vine", "druid_light": "light", "druid_heal_one": "runic_weapon",
        "druid_runic_weapon_two": "heal", "druid_heal_three": "heal",
    }}
    assert druid.daily_prepare(("druid",), preparations).status is ResultStatus.COMPLETED
    druid_path = tmp_path / "l2-druid-recovery.json"
    druid.save(druid_path)
    druid = Encounter.load(druid_path)
    assert druid.next_encounter(STORM_DRUID_L2_NEXT_SETUP).status is ResultStatus.PAUSED
    _settle_to_turn(druid, "druid")
    assert druid.execute(Cast("runic_weapon", item_id="druid:staff", slot_id="druid_heal_one")).status is ResultStatus.COMPLETED

    sorcerer = Encounter.start(sorcerer_fight, rolls=(20, 1, 1, 20, 4, 4, 1, 1, 1))
    _settle_to_turn(sorcerer, "angelic_sorcerer")
    sorcerer._state.creatures["angelic_sorcerer"].hp -= 1
    heal = sorcerer.execute(Cast("heal", "angelic_sorcerer", actions=1, slot_id="angelic_rank1"))
    assert _resolve_pending(sorcerer, heal).status is ResultStatus.COMPLETED
    assert sorcerer._state.creatures["angelic_sorcerer"].spontaneous_slots[0].remaining == 3
    sorcerer._state.creatures["first_sorcerer_dog"].hp = 1
    assert sorcerer.execute(Cast("divine_lance", "first_sorcerer_dog", actions=2)).status is ResultStatus.COMPLETED
    assert sorcerer.inspect().winner_team == "blue"
    assert sorcerer.record_rested(("angelic_sorcerer",), day_number=2, elapsed_seconds=1).status is ResultStatus.COMPLETED
    assert sorcerer.daily_prepare(("angelic_sorcerer",)).status is ResultStatus.COMPLETED
    sorcerer_path = tmp_path / "l2-sorcerer-recovery.json"
    sorcerer.save(sorcerer_path)
    sorcerer = Encounter.load(sorcerer_path)
    assert sorcerer.next_encounter(ANGELIC_SORCERER_L2_NEXT_SETUP).status in {ResultStatus.PAUSED, ResultStatus.COMPLETED}
    next_sorcerer = sorcerer._state.creatures["angelic_sorcerer"]
    assert next_sorcerer.definition_id == ANGELIC_SORCERER_L2.definition_id
    assert next_sorcerer.spontaneous_slots[0].remaining == 4
    _settle_to_turn(sorcerer, "angelic_sorcerer")
    assert sorcerer.execute(Cast("guidance", "angelic_sorcerer")).status is ResultStatus.COMPLETED

    bard_fight = EncounterSetup(
        "maestro_bard_level_2_recovery_fight", "Maestro Bard L2 recovery fight", 7, 5,
        (
            CreaturePlacement("maestro_bard", MAESTRO_BARD_L2.definition_id, "Maestro Bard", "blue", Position(1, 2)),
            CreaturePlacement("first_bard_dog", "guard_dog_mc2924", "First Guard Dog", "red", Position(3, 2)),
        ),
    )
    monkeypatch.setattr(
        content, "_STAGED_SETUPS",
        MappingProxyType({**content._STAGED_SETUPS, bard_fight.setup_id: bard_fight}),
    )
    bard = Encounter.start(bard_fight, rolls=(20, 1, 1, 4, 4, 1, 1, 1))
    _settle_to_turn(bard, "maestro_bard")
    spent_focus = bard.execute(LingeringComposition())
    assert spent_focus.status is ResultStatus.COMPLETED
    assert bard._state.creatures["maestro_bard"].focus_points == 1
    bard._state.creatures["first_bard_dog"].hp = 1
    assert bard.execute(Cast("void_warp", "first_bard_dog", actions=2)).status is ResultStatus.COMPLETED
    assert bard.inspect().winner_team == "blue"
    assert bard.refocus("maestro_bard").status is ResultStatus.COMPLETED
    assert bard.record_rested(("maestro_bard",), day_number=2, elapsed_seconds=1).status is ResultStatus.COMPLETED
    assert bard.daily_prepare(("maestro_bard",)).status is ResultStatus.COMPLETED
    bard_path = tmp_path / "l2-bard-recovery.json"
    bard.save(bard_path)
    bard = Encounter.load(bard_path)
    assert bard.next_encounter(MAESTRO_BARD_L2_NEXT_SETUP).status in {ResultStatus.PAUSED, ResultStatus.COMPLETED}
    next_bard = bard._state.creatures["maestro_bard"]
    assert next_bard.definition_id == MAESTRO_BARD_L2.definition_id
    assert next_bard.focus_points == next_bard.focus_capacity == 2
    assert next_bard.spontaneous_slots[0].remaining == 3
    assert {
        spell.spell_id
        for spell in content.get_definition(next_bard.definition_id).spontaneous_spells
        if not spell.cantrip
    } == {
        "fear", "runic_weapon", "soothe", "command",
    }
    _settle_to_turn(bard, "maestro_bard")
    assert bard.execute(Cast("guidance", "maestro_bard")).status is ResultStatus.COMPLETED
