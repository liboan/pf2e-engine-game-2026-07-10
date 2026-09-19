"""Independent source-led review of movement spells and Wizard admission.

Expectations were fixed from Player Core pp. 362, 416, 422, and 444 and
Player Core 2 p. 246 before observing these outcomes.  Tangle Vine's hit
reduces Speed for 1 round, its critical hit also immobilizes, and Escape
against the caster's spell DC removes the linked effects.  Gale Blast is a
5-foot emanation with one shared d6, basic Fortitude damage, and a 5- or
10-foot outward push on failure or critical failure.  Forced movement does
not trigger movement reactions and stops before a space the creature cannot
occupy.  The local external-force modifier is the user-approved spell attack
bonus without MAP.

The later admission checks use Player Core's Wizard, Battle Magic, Spell
Substitution, Drain Bonded Item, Assurance, Human, Scholar, and Concealed
rules.  They keep the selected finite book literal, require the authored
staff across save/load, and count a prepared spell for Arcane Bond only once
its cast has reached a completed outcome (including refusal or failed
concealment, but excluding manipulate disruption).
"""

from dataclasses import replace
import json
from types import MappingProxyType

import pf2e.content as content
import pytest
from pf2e.content import get_definition, get_setup
from pf2e.damage import DamageDefense
from pf2e.encounter import Encounter
from pf2e.model import (
    ActiveConditionEffect,
    Cast,
    CreaturePlacement,
    EndTurn,
    EffectExpiration,
    EncounterSetup,
    PersistentDamageEffect,
    Position,
    ResultStatus,
)
from pf2e.skill_actions import Escape


def _settle(game: Encounter) -> None:
    while game.inspect().choice is not None:
        choice = game.inspect().choice
        assert choice is not None
        assert game.choose(
            choice.choice_id, "keep", choice.owner_actor_id
        ).status in {ResultStatus.COMPLETED, ResultStatus.PAUSED}


def _register(monkeypatch, setup: EncounterSetup, *definitions) -> None:
    monkeypatch.setattr(
        content,
        "_STAGED_CREATURES",
        MappingProxyType({
            **content._STAGED_CREATURES,
            **{definition.definition_id: definition for definition in definitions},
        }),
    )
    monkeypatch.setattr(
        content,
        "_STAGED_SETUPS",
        MappingProxyType({**content._STAGED_SETUPS, setup.setup_id: setup}),
    )


def _reaction_setup(monkeypatch, setup_id: str) -> EncounterSetup:
    reactor = replace(
        get_definition("fighter_m_level_1"),
        definition_id=f"{setup_id}_reactor",
        hero_points=0,
    )
    setup = EncounterSetup(
        setup_id=setup_id,
        name="Movement Spell Reaction Review",
        width=6,
        height=4,
        placements=(
            CreaturePlacement(
                "wizard", "wizard_battle_magic_level_1_movement_spells_prepared",
                "Wizard", "blue", Position(1, 1),
            ),
            CreaturePlacement(
                "ally", "guard_dog_mc2924", "Ally", "blue", Position(2, 1),
            ),
            CreaturePlacement(
                "reactor", reactor.definition_id, "Reactive Fighter", "red",
                Position(1, 2),
            ),
        ),
    )
    _register(monkeypatch, setup, reactor)
    return setup


def test_gale_critical_push_uses_ordinary_diagonal_distance() -> None:
    game = Encounter.start(
        get_setup("staged_battle_magic_wizard_movement_spells_prepared"),
        rolls=(20, 1, 1, 3, 1),
    )
    _settle(game)
    game._state.creatures["wizard"].position = Position(1, 1)
    game._state.creatures["dog_a"].position = Position(2, 2)
    game._state.creatures["dog_b"].position = Position(6, 4)

    result = game.execute(Cast("gale_blast", include_self=False))

    assert result.status is ResultStatus.COMPLETED
    # The first diagonal costs 5 feet and the next costs 10 feet, so a
    # 10-foot push can traverse only the first square.
    assert game._state.creatures["dog_a"].position == Position(3, 3)
    pushes = [event for event in result.events if event.kind == "forced_movement"]
    assert len(pushes) == 1 and pushes[0].target_id == "dog_a"


def test_saved_gale_health_choice_commits_once_then_drops_before_push(
    tmp_path,
    monkeypatch,
) -> None:
    fragile_ally = replace(
        get_definition("wizard_battle_magic_level_1_movement_spells_prepared"),
        definition_id="movement_review_fragile_ally",
        hp=5,
    )
    setup = EncounterSetup(
        setup_id="movement_review_saved_gale_health",
        name="Saved Gale Health Review",
        width=6,
        height=3,
        placements=(
            CreaturePlacement(
                "wizard", "wizard_battle_magic_level_1_movement_spells_prepared",
                "Wizard", "blue", Position(1, 1),
            ),
            CreaturePlacement(
                "ally", fragile_ally.definition_id, "Fragile Ally", "blue",
                Position(2, 1),
            ),
            CreaturePlacement(
                "dog", "guard_dog_mc2924", "Dog", "red", Position(5, 1),
            ),
        ),
    )
    _register(monkeypatch, setup, fragile_ally)
    # Initiative, shared d6=4, then the ally's critical Fortitude failure.
    game = Encounter.start(setup, rolls=(20, 10, 1, 4, 1))
    _settle(game)

    saved_fortitude = game.execute(Cast("gale_blast", include_self=False))
    assert saved_fortitude.status is ResultStatus.PAUSED
    choice = game.inspect().choice
    assert choice is not None and choice.kind == "spell_save_hero_reroll"
    health_choice = game.choose(choice.choice_id, "keep", choice.owner_actor_id)
    assert health_choice.status is ResultStatus.PAUSED
    choice = game.inspect().choice
    assert choice is not None and choice.kind == "heroic_recovery_damage"
    path = tmp_path / "saved-gale-health.json"
    game.save(path)
    game = Encounter.load(path)

    choice = game.inspect().choice
    assert choice is not None
    completed = game.choose(choice.choice_id, "normal", choice.owner_actor_id)

    assert completed.status is ResultStatus.COMPLETED
    ally = game._state.creatures["ally"]
    assert ally.unconscious and ally.position == Position(4, 1)
    assert game._state.ground_items[Position(2, 1)] == ["ally:bonded_staff"]
    assert len([
        event for event in completed.events
        if event.kind == "spell_damage" and event.target_id == "ally"
    ]) == 1
    assert len([
        event for event in completed.events
        if event.kind == "forced_movement" and event.target_id == "ally"
    ]) == 1


def test_gale_finishes_only_after_every_snapshotted_recipient(
    monkeypatch,
) -> None:
    fragile_enemy = replace(
        get_definition("guard_dog_mc2924"),
        definition_id="movement_review_fragile_enemy",
        hp=1,
    )
    setup = EncounterSetup(
        setup_id="movement_review_finish_after_recipients",
        name="Gale Finish After Recipients Review",
        width=5,
        height=4,
        placements=(
            CreaturePlacement(
                "wizard", "wizard_battle_magic_level_1_movement_spells_prepared",
                "Wizard", "blue", Position(1, 1),
            ),
            CreaturePlacement(
                "enemy", fragile_enemy.definition_id, "Enemy", "red",
                Position(2, 1),
            ),
            CreaturePlacement(
                "ally", "wizard_battle_magic_level_1_movement_spells_prepared",
                "Ally", "blue", Position(1, 2),
            ),
        ),
    )
    _register(monkeypatch, setup, fragile_enemy)
    # Initiative; shared d6=3; enemy critical failure; ally ordinary success.
    game = Encounter.start(setup, rolls=(20, 1, 10, 3, 1, 12))
    _settle(game)

    paused = game.execute(Cast("gale_blast", include_self=False))

    assert paused.status is ResultStatus.PAUSED
    assert game._state.creatures["enemy"].defeated
    assert game.inspect().in_progress
    choice = game.inspect().choice
    assert choice is not None and choice.owner_actor_id == "ally"
    completed = game.choose(choice.choice_id, "keep", choice.owner_actor_id)
    assert completed.status is ResultStatus.COMPLETED
    assert not game.inspect().in_progress
    assert game._state.creatures["ally"].hp == 15


def test_failed_external_force_check_blocks_push_without_spending_an_attack() -> None:
    game = Encounter.start(
        get_setup("staged_battle_magic_wizard_movement_spells_prepared"),
        rolls=(20, 1, 1, 3, 1, 1),
    )
    _settle(game)
    wizard = game._state.creatures["wizard"]
    dog = game._state.creatures["dog_a"]
    dog.position = Position(2, 2)
    game._state.creatures["dog_b"].position = Position(6, 4)
    wizard.strikes_this_turn = 2
    game._state.condition_effects.append(ActiveConditionEffect(
        "movement-review-hold", "immobilized", "wizard", "dog_a", 1,
        EffectExpiration("wizard", "start", 9), 30,
    ))

    result = game.execute(Cast("gale_blast", include_self=False))

    assert result.status is ResultStatus.COMPLETED
    assert dog.position == Position(2, 2)
    blocked = next(
        event for event in result.events if event.kind == "forced_movement_blocked"
    )
    assert blocked.check is not None
    assert (blocked.check.modifier, blocked.check.map_penalty) == (7, 0)
    assert wizard.strikes_this_turn == 2
    assert any(
        effect.effect_id == "movement-review-hold"
        for effect in game._state.condition_effects
    )


def test_gale_push_stops_before_occupied_space_and_map_boundary() -> None:
    occupied = Encounter.start(
        get_setup("staged_battle_magic_wizard_movement_spells_prepared"),
        rolls=(20, 1, 1, 3, 1),
    )
    _settle(occupied)
    occupied._state.creatures["wizard"].position = Position(1, 1)
    occupied._state.creatures["dog_a"].position = Position(2, 1)
    occupied._state.creatures["dog_b"].position = Position(3, 1)
    result = occupied.execute(Cast("gale_blast", include_self=False))
    assert result.status is ResultStatus.COMPLETED
    assert occupied._state.creatures["dog_a"].position == Position(2, 1)
    assert occupied._state.creatures["dog_b"].position == Position(3, 1)

    bounded = Encounter.start(
        get_setup("staged_battle_magic_wizard_movement_spells_prepared"),
        rolls=(20, 1, 1, 3, 1),
    )
    _settle(bounded)
    bounded._state.creatures["wizard"].position = Position(1, 1)
    bounded._state.creatures["dog_a"].position = Position(0, 1)
    bounded._state.creatures["dog_b"].position = Position(6, 4)
    result = bounded.execute(Cast("gale_blast", include_self=False))
    assert result.status is ResultStatus.COMPLETED
    assert bounded._state.creatures["dog_a"].position == Position(0, 1)


def test_zero_damage_after_resistance_does_not_cancel_earned_push(
    monkeypatch,
) -> None:
    ward = replace(
        get_definition("guard_dog_mc2924"),
        definition_id="movement_review_bludgeoning_ward",
        damage_defenses=(DamageDefense(
            "resistance", "bludgeoning", 10, source="review ward"
        ),),
    )
    setup = EncounterSetup(
        setup_id="movement_review_zero_damage_push",
        name="Zero Damage Gale Push Review",
        width=6,
        height=3,
        placements=(
            CreaturePlacement(
                "wizard", "wizard_battle_magic_level_1_movement_spells_prepared",
                "Wizard", "blue", Position(1, 1),
            ),
            CreaturePlacement(
                "ward", ward.definition_id, "Ward", "red", Position(2, 1),
            ),
            CreaturePlacement(
                "dog", "guard_dog_mc2924", "Dog", "red", Position(5, 1),
            ),
        ),
    )
    _register(monkeypatch, setup, ward)
    # Initiative, shared d6=3, ordinary failed Fortitude save.
    game = Encounter.start(setup, rolls=(20, 1, 2, 3, 10))
    _settle(game)

    result = game.execute(Cast("gale_blast", include_self=False))

    assert result.status is ResultStatus.COMPLETED
    damage = next(
        event.damage for event in result.events
        if event.kind == "spell_damage" and event.target_id == "ward"
    )
    assert damage is not None and damage.total == 0
    assert game._state.creatures["ward"].position == Position(3, 1)


def test_included_gale_caster_takes_damage_without_displacement() -> None:
    game = Encounter.start(
        get_setup("staged_battle_magic_wizard_movement_spells_prepared"),
        rolls=(20, 1, 1, 3, 1),
    )
    _settle(game)
    game._state.creatures["dog_a"].position = Position(6, 4)
    game._state.creatures["dog_b"].position = Position(6, 3)
    origin = game._state.creatures["wizard"].position
    result = game.execute(Cast("gale_blast", include_self=True))
    assert result.status is ResultStatus.PAUSED
    choice = game.inspect().choice
    assert choice is not None and choice.owner_actor_id == "wizard"
    completed = game.choose(choice.choice_id, "keep", choice.owner_actor_id)

    assert completed.status is ResultStatus.COMPLETED
    assert game._state.creatures["wizard"].hp == 10
    assert game._state.creatures["wizard"].position == origin
    assert not any(
        event.kind == "forced_movement" and event.target_id == "wizard"
        for event in completed.events
    )


def test_gale_forced_movement_does_not_offer_a_movement_reaction(
    monkeypatch,
) -> None:
    setup = _reaction_setup(monkeypatch, "movement_review_forced_reaction")
    # Initiative; after the manipulate reaction is declined: shared d6,
    # ally critical Fortitude failure, reactor critical Fortitude success.
    game = Encounter.start(setup, rolls=(20, 10, 1, 3, 1, 20))
    _settle(game)

    cast = game.execute(Cast("gale_blast", include_self=False))
    assert cast.status is ResultStatus.PAUSED
    choice = game.inspect().choice
    assert choice is not None and choice.kind == "reaction"
    completed = game.choose(choice.choice_id, "decline", choice.owner_actor_id)

    assert completed.status is ResultStatus.COMPLETED
    assert game.inspect().choice is None
    assert game._state.creatures["ally"].position == Position(4, 1)
    assert game._state.creatures["reactor"].reaction_available
    assert len([
        event for event in completed.events
        if event.kind == "forced_movement" and event.target_id == "ally"
    ]) == 1


def test_tangle_escape_critical_stride_still_offers_a_movement_reaction(
    monkeypatch,
) -> None:
    setup = _reaction_setup(monkeypatch, "movement_review_escape_reaction")
    # Initiative; Tangle Vine critical spell attack; critical Escape.
    game = Encounter.start(setup, rolls=(20, 10, 1, 20, 20))
    _settle(game)
    cast = game.execute(Cast("tangle_vine", target_id="ally"))
    assert cast.status is ResultStatus.PAUSED
    reaction = game.inspect().choice
    assert reaction is not None and reaction.kind == "reaction"
    spell_attack = game.choose(
        reaction.choice_id, "decline", reaction.owner_actor_id
    )
    assert spell_attack.status is ResultStatus.PAUSED
    choice = game.inspect().choice
    assert choice is not None and choice.kind == "spell_attack_hero_reroll"
    assert game.choose(
        choice.choice_id, "keep", choice.owner_actor_id
    ).status is ResultStatus.COMPLETED
    assert game.execute(EndTurn()).status is ResultStatus.COMPLETED

    impediment = next(
        effect.effect_id for effect in game._state.condition_effects
        if effect.target_actor_id == "ally" and effect.kind == "immobilized"
    )
    escaped = game.execute(Escape(impediment, "athletics"))
    assert escaped.status is ResultStatus.PAUSED
    stride = game.inspect().choice
    assert stride is not None
    offered = game.choose(stride.choice_id, "stride:3:1", stride.owner_actor_id)

    assert offered.status is ResultStatus.PAUSED
    reaction = game._state.pending_choice
    assert reaction is not None and reaction.kind == "reaction"
    assert reaction.continuation is not None
    assert reaction.continuation.reaction_trigger == "movement"


def test_tangle_expires_at_incapacitated_caster_start(monkeypatch) -> None:
    setup = EncounterSetup(
        setup_id="movement_review_incapacitated_expiry",
        name="Incapacitated Tangle Expiry Review",
        width=6,
        height=3,
        placements=(
            CreaturePlacement(
                "wizard", "wizard_battle_magic_level_1_movement_spells_prepared",
                "Wizard", "blue", Position(1, 1),
            ),
            CreaturePlacement(
                "fighter", "fighter_m_level_1", "Fighter", "blue",
                Position(5, 2),
            ),
            CreaturePlacement(
                "dog_a", "guard_dog_mc2924", "Dog", "red", Position(2, 1),
            ),
        ),
    )
    _register(monkeypatch, setup)
    game = Encounter.start(
        setup,
        rolls=(20, 10, 1, 20, 10),
    )
    _settle(game)
    cast = game.execute(Cast("tangle_vine", target_id="dog_a"))
    assert cast.status is ResultStatus.PAUSED
    choice = game.inspect().choice
    assert choice is not None
    assert game.choose(
        choice.choice_id, "keep", choice.owner_actor_id
    ).status is ResultStatus.COMPLETED
    assert game.effective_speed_ft("dog_a") == 20
    assert game.execute(EndTurn()).status is ResultStatus.COMPLETED

    wizard = game._state.creatures["wizard"]
    wizard.hp = 0
    wizard.dying = 1
    wizard.unconscious = True
    wizard.prone = True
    assert game.execute(EndTurn()).status is ResultStatus.COMPLETED
    wrapped = game.execute(EndTurn())

    assert wrapped.status is ResultStatus.PAUSED
    choice = game.inspect().choice
    assert choice is not None and choice.owner_actor_id == "wizard"
    assert not any(
        effect.effect_id.startswith("tangle_vine:")
        for effect in game._state.condition_effects
    )
    assert game.effective_speed_ft("dog_a") == 30


def test_gale_rejects_non_emanation_targeting_atomically() -> None:
    game = Encounter.start(
        get_setup("staged_battle_magic_wizard_movement_spells_prepared"),
        rolls=(20, 1, 1),
    )
    _settle(game)
    before = game.inspect()
    dice_index = game._dice._index

    targeted = game.execute(Cast(
        "gale_blast", target_id="dog_a", include_self=False
    ))
    invalid_self = game.execute(Cast("gale_blast", include_self="yes"))

    assert targeted.status is ResultStatus.REJECTED
    assert invalid_self.status is ResultStatus.REJECTED
    assert game.inspect() == before
    assert game._dice._index == dice_index


def test_round_wrap_purge_preserves_committed_persistent_tick_after_load(
    tmp_path,
    monkeypatch,
) -> None:
    setup = EncounterSetup(
        setup_id="movement_review_persistent_wrap_commit",
        name="Persistent Wrap Commit Review",
        width=6,
        height=3,
        placements=(
            CreaturePlacement(
                "wizard", "wizard_battle_magic_level_1_movement_spells_prepared",
                "Wizard", "blue", Position(1, 1),
            ),
            CreaturePlacement(
                "dog", "guard_dog_mc2924", "Dog", "red", Position(4, 1),
            ),
            CreaturePlacement(
                "ally", "wizard_battle_magic_level_1_movement_spells_prepared",
                "Ally", "blue", Position(2, 1),
            ),
        ),
    )
    _register(monkeypatch, setup)
    # Initiative; one d4 tick=3; failed DC 15 recovery=14.
    game = Encounter.start(setup, rolls=(20, 10, 1, 3, 14))
    _settle(game)
    game._state.persistent_effects.append(PersistentDamageEffect(
        "movement-review-wrap-fire", "wizard", "ally", "ignition", "fire",
        (4,), 0, 6,
    ))
    assert game.execute(EndTurn()).status is ResultStatus.COMPLETED
    assert game.execute(EndTurn()).status is ResultStatus.COMPLETED
    tick = game.execute(EndTurn())
    assert tick.status is ResultStatus.PAUSED
    assert game._state.creatures["ally"].hp == 13
    choice = game.inspect().choice
    assert choice is not None and choice.kind == "persistent_recovery"
    path = tmp_path / "persistent-wrap-committed.json"
    game.save(path)
    game = Encounter.load(path)

    choice = game.inspect().choice
    assert choice is not None
    wrapped = game.choose(choice.choice_id, "keep", choice.owner_actor_id)

    assert wrapped.status is ResultStatus.COMPLETED
    assert game.inspect().world_time_seconds == 6
    assert game._state.creatures["ally"].hp == 13
    assert not [event for event in wrapped.events if event.kind == "persistent_damage"]
    assert not game._state.persistent_effects
    post_wrap = tmp_path / "persistent-wrap-purged.json"
    game.save(post_wrap)
    assert not Encounter.load(post_wrap)._state.persistent_effects


def test_prepared_runic_weapon_reaction_continuation_round_trips(
    tmp_path,
    monkeypatch,
) -> None:
    """A prepared Wizard cast must use the same saved-reaction path as Runic Weapon."""
    wizard = replace(
        get_definition("wizard_battle_magic_level_1_staged"),
        definition_id="wizard_admission_review_runic_prepared",
        hp=50,
        prepared_spells=tuple(
            replace(slot, spell_id="runic_weapon")
            if slot.slot_id == "wizard_enfeeble" else slot
            for slot in get_definition(
                "wizard_battle_magic_level_1_staged"
            ).prepared_spells
        ),
    )
    reactor = replace(
        get_definition("fighter_m_level_1"),
        definition_id="wizard_admission_review_reactor",
        hero_points=0,
    )
    setup = EncounterSetup(
        setup_id="wizard_admission_review_runic_reaction",
        name="Prepared Runic Weapon Reaction Review",
        width=5,
        height=3,
        placements=(
            CreaturePlacement(
                "wizard", wizard.definition_id, "Wizard", "blue", Position(1, 1)
            ),
            CreaturePlacement(
                "reactor", reactor.definition_id, "Reactor", "red", Position(1, 2)
            ),
        ),
    )
    _register(monkeypatch, setup, wizard, reactor)
    game = Encounter.start(setup, rolls=(20, 1, 20, 8))
    _settle(game)

    cast = game.execute(Cast(
        "runic_weapon",
        actions=2,
        slot_id="wizard_enfeeble",
        item_id="wizard:bonded_staff",
    ))

    assert cast.status is ResultStatus.PAUSED
    choice = game.inspect().choice
    assert choice is not None and choice.kind == "reaction"
    path = tmp_path / "prepared-runic-reaction.json"
    game.save(path)
    restored = Encounter.load(path)
    assert restored.inspect().choice == choice
    disrupted = restored.choose(choice.choice_id, "accept", choice.owner_actor_id)
    assert disrupted.status is ResultStatus.COMPLETED
    assert any(event.kind == "disrupted" for event in disrupted.events)
    restored_wizard = restored._state.creatures["wizard"]
    assert not restored._state.active_item_effects
    assert restored_wizard.arcane_bond_eligible_slots == set()
    assert next(
        slot for slot in restored_wizard.prepared_slots
        if slot.slot_id == "wizard_enfeeble"
    ).spent


def test_saved_arcane_bond_permission_rejects_a_different_carried_item(
    tmp_path,
) -> None:
    """The selected staff remains the bond across the persistence boundary."""
    game = Encounter.start(
        get_setup("staged_battle_magic_wizard_vs_two_guard_dogs"),
        rolls=(20, 1, 1, 1),
    )
    _settle(game)
    assert game.execute(Cast(
        "force_barrage", actions=1, target_ids=("dog_a",)
    )).status is ResultStatus.COMPLETED
    from pf2e.wizard import DrainBondedItem

    assert game.execute(
        DrainBondedItem("wizard:bonded_staff")
    ).status is ResultStatus.COMPLETED
    path = tmp_path / "forged-bond-item.json"
    game.save(path)
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["state"]["creatures"]["wizard"][
        "arcane_bond_item_id"
    ] = "wizard:spellbook"
    path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(ValueError, match="Bonded Item|Arcane Bond"):
        Encounter.load(path)


def test_admitted_wizard_catalog_uses_completed_public_labels() -> None:
    definition_id = "wizard_battle_magic_level_1_staged"
    setup_id = "staged_battle_magic_wizard_vs_two_guard_dogs"
    assert definition_id in content.CREATURES
    assert setup_id in content.SETUPS
    assert "staged" not in content.CREATURES[definition_id].name.lower()
    assert "staged" not in content.SETUPS[setup_id].name.lower()
    assert content.CREATURES[definition_id].vision == "ordinary"


def test_unwilling_runic_weapon_target_still_records_the_completed_cast(
    monkeypatch,
) -> None:
    wizard = replace(
        get_definition("wizard_battle_magic_level_1_staged"),
        definition_id="wizard_admission_review_runic_refused",
        prepared_spells=tuple(
            replace(slot, spell_id="runic_weapon")
            if slot.slot_id == "wizard_enfeeble" else slot
            for slot in get_definition(
                "wizard_battle_magic_level_1_staged"
            ).prepared_spells
        ),
    )
    setup = EncounterSetup(
        setup_id="wizard_admission_review_runic_refused",
        name="Runic Weapon Refusal Review",
        width=6,
        height=3,
        placements=(
            CreaturePlacement(
                "wizard", wizard.definition_id, "Wizard", "blue", Position(1, 1)
            ),
            CreaturePlacement(
                "ally", "fighter_m_weapon_identity_staged", "Ally", "blue", Position(2, 1)
            ),
            CreaturePlacement(
                "dog", "guard_dog_mc2924", "Dog", "red", Position(5, 1)
            ),
        ),
    )
    _register(monkeypatch, setup, wizard)
    game = Encounter.start(setup, rolls=(20, 10, 1))
    _settle(game)

    offered = game.execute(Cast(
        "runic_weapon",
        actions=2,
        slot_id="wizard_enfeeble",
        item_id="ally:longsword",
    ))
    assert offered.status is ResultStatus.PAUSED
    choice = game.inspect().choice
    assert choice is not None and choice.kind == "spell_willingness"
    refused = game.choose(choice.choice_id, "unwilling", choice.owner_actor_id)

    assert refused.status is ResultStatus.COMPLETED
    wizard_state = game._state.creatures["wizard"]
    assert next(
        slot for slot in wizard_state.prepared_slots
        if slot.slot_id == "wizard_enfeeble"
    ).spent
    assert wizard_state.arcane_bond_eligible_slots == {"wizard_enfeeble"}
    assert not game._state.active_item_effects


def test_failed_concealment_still_records_a_completed_prepared_cast(
    tmp_path,
    monkeypatch,
) -> None:
    setup = EncounterSetup(
        setup_id="wizard_admission_review_concealment_bond",
        name="Concealment Bond Review",
        width=6,
        height=3,
        placements=(
            CreaturePlacement(
                "wizard", "wizard_battle_magic_level_1_staged",
                "Wizard", "blue", Position(1, 1),
            ),
            CreaturePlacement(
                "dog", "guard_dog_mc2924", "Dog", "red", Position(4, 1),
            ),
        ),
        ambient_light="dim",
    )
    _register(monkeypatch, setup)
    game = Encounter.start(setup, rolls=(20, 1, 1))
    _settle(game)

    offered = game.execute(Cast(
        "enfeeble", "dog", actions=2, slot_id="wizard_enfeeble"
    ))
    assert offered.status is ResultStatus.PAUSED
    choice = game.inspect().choice
    assert choice is not None and choice.kind == "concealment_hero_reroll"
    path = tmp_path / "enfeeble-concealment.json"
    game.save(path)
    game = Encounter.load(path)
    choice = game.inspect().choice
    assert choice is not None
    result = game.choose(choice.choice_id, "keep", choice.owner_actor_id)
    assert result.status is ResultStatus.COMPLETED
    assert any(event.kind == "concealment_failed" for event in result.events)
    wizard = game._state.creatures["wizard"]
    assert next(
        slot for slot in wizard.prepared_slots
        if slot.slot_id == "wizard_enfeeble"
    ).spent
    assert wizard.arcane_bond_eligible_slots == {"wizard_enfeeble"}


def test_daily_preparation_requires_the_owned_book_atomically() -> None:
    game = Encounter.start(
        get_setup("staged_battle_magic_wizard_vs_two_guard_dogs"),
        rolls=(20, 1, 1, 6, 6, 1, 1),
    )
    _settle(game)
    assert game.execute(Cast(
        "breathe_fire", actions=2, area_direction=Position(1, 0)
    )).status is ResultStatus.COMPLETED
    assert not game.inspect().in_progress
    assert game.record_rested(
        ("wizard",), day_number=2, elapsed_seconds=1
    ).status is ResultStatus.COMPLETED
    wizard = game._state.creatures["wizard"]
    wizard.stowed_items.remove("wizard:spellbook")
    choices = {"wizard": {
        slot.slot_id: slot.spell_id for slot in wizard.prepared_slots
    }}
    before = game.inspect()
    dice_before = game._dice.to_data()

    rejected = game.daily_prepare(("wizard",), choices)

    assert rejected.status is ResultStatus.REJECTED
    assert "spellbook" in rejected.message.lower()
    assert game.inspect() == before
    assert game._dice.to_data() == dice_before


def test_saved_force_bolt_concealment_uses_its_committed_focus_point(
    tmp_path,
    monkeypatch,
) -> None:
    setup = EncounterSetup(
        setup_id="wizard_admission_review_force_bolt_concealment",
        name="Force Bolt Concealment Review",
        width=6,
        height=3,
        placements=(
            CreaturePlacement(
                "wizard", "wizard_battle_magic_level_1_staged",
                "Wizard", "blue", Position(1, 1),
            ),
            CreaturePlacement(
                "dog", "guard_dog_mc2924", "Dog", "red", Position(4, 1),
            ),
        ),
        ambient_light="dim",
    )
    _register(monkeypatch, setup)
    game = Encounter.start(setup, rolls=(20, 1, 1))
    _settle(game)
    offered = game.execute(Cast("force_bolt", "dog"))
    assert offered.status is ResultStatus.PAUSED
    choice = game.inspect().choice
    assert choice is not None and choice.kind == "concealment_hero_reroll"
    assert game._state.creatures["wizard"].focus_points == 0
    path = tmp_path / "force-bolt-concealment.json"
    game.save(path)

    restored = Encounter.load(path)
    choice = restored.inspect().choice
    assert choice is not None
    result = restored.choose(choice.choice_id, "keep", choice.owner_actor_id)
    assert result.status is ResultStatus.COMPLETED
    assert any(event.kind == "concealment_failed" for event in result.events)
    assert restored._state.creatures["wizard"].focus_points == 0
