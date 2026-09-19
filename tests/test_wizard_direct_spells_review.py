"""Independent source-led checks for the staged Wizard's direct spells.

Numerical expectations recorded before engine observation:

* Electric Arc is two actions, targets one or two creatures within 30 feet,
  rolls one shared 2d4 electricity result, and gives each a basic Reflex save.
* Frostbite is two actions at 60 feet for 2d4 cold with a basic Fortitude
  save; critical failure also gives weakness 1 to bludgeoning until the
  caster's next turn.
* Enfeeble is two actions at 30 feet: critical success has no effect, success
  is enfeebled 1 until the caster's next turn, failure is enfeebled 2 for one
  minute, and critical failure is enfeebled 3 for one minute.
* Runic Body is touch, willing, and one minute; every unarmed attack becomes
  +1 striking, so existing item bonuses and striking dice do not add again.
* Telekinetic Projectile is two actions at 30 feet and requires a loose,
  unattended object of at most 1 Bulk within range; it makes a spell attack
  for 2d6 physical damage appropriate to that object.

Sources: Player Core pp. 328, 332, 329, 354, and 363; AoN spell IDs 1509,
1539, 1513, 1657, and 1718.
"""

from dataclasses import replace
from types import MappingProxyType

import pf2e.content as content
import pf2e.spells as spells
from pf2e.content import get_definition, get_setup
from pf2e.encounter import Encounter
from pf2e.model import (
    Cast,
    CreaturePlacement,
    EncounterSetup,
    EndTurn,
    ItemInstance,
    Position,
    Release,
    ResultStatus,
    Strike,
)


def _settle(game: Encounter) -> None:
    while game.inspect().choice is not None:
        choice = game.inspect().choice
        assert choice is not None
        assert game.choose(
            choice.choice_id, "keep", choice.owner_actor_id
        ).status in {ResultStatus.COMPLETED, ResultStatus.PAUSED}


def _register_staged(monkeypatch, setup: EncounterSetup, *definitions) -> None:
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


def test_electric_arc_saves_on_its_second_recipient_without_rerolling_damage(
    tmp_path,
) -> None:
    game = Encounter.start(
        get_setup("staged_battle_magic_wizard_breathe_hero_save"),
        rolls=(20, 1, 1, 1, 3, 4, 10, 10),
    )
    _settle(game)
    result = game.execute(Cast(
        "electric_arc", target_ids=("dog_a", "wizard_ally")
    ))
    assert result.status is ResultStatus.PAUSED
    assert game._state.creatures["wizard"].actions_remaining == 1
    first = [
        event.damage.total
        for event in result.events
        if event.kind == "spell_damage" and event.target_id == "dog_a"
        and event.damage is not None
    ]
    assert first == [3]
    pending = game.inspect().choice
    assert pending is not None and pending.owner_actor_id == "wizard_ally"
    continuation = game._state.pending_choice.continuation
    assert continuation is not None
    assert continuation.spell_damage is not None
    assert continuation.spell_damage.total == 7

    path = tmp_path / "electric-arc-second-recipient.json"
    game.save(path)
    restored = Encounter.load(path)
    pending = restored.inspect().choice
    assert pending is not None
    completed = restored.choose(pending.choice_id, "keep", pending.owner_actor_id)
    assert completed.status is ResultStatus.COMPLETED
    second = [
        event.damage.total
        for event in completed.events
        if event.kind == "spell_damage" and event.target_id == "wizard_ally"
        and event.damage is not None
    ]
    assert second == [7]


def test_enfeeble_success_expires_next_turn_and_failure_saves_one_minute(
    tmp_path,
) -> None:
    success = Encounter.start(
        get_setup("staged_battle_magic_wizard_vs_two_guard_dogs"),
        rolls=(20, 1, 1, 15),
    )
    _settle(success)
    assert success.execute(Cast("enfeeble", "dog_a")).status is ResultStatus.COMPLETED
    effect = next(
        effect for effect in success._state.active_effects
        if effect.kind == "enfeebled" and effect.target_actor_id == "dog_a"
    )
    assert (effect.value, effect.expires_at_source_start) == (
        1, success._state.actor_start_counts["wizard"] + 1
    )
    assert success.execute(EndTurn()).status is ResultStatus.COMPLETED
    while success.inspect().turn_actor_id != "wizard":
        assert success.execute(EndTurn()).status is ResultStatus.COMPLETED
    assert not any(effect.kind == "enfeebled" for effect in success._state.active_effects)

    failure = Encounter.start(
        get_setup("staged_battle_magic_wizard_vs_two_guard_dogs"),
        rolls=(20, 1, 1, 10),
    )
    _settle(failure)
    assert failure.execute(Cast("enfeeble", "dog_a")).status is ResultStatus.COMPLETED
    effect = next(effect for effect in failure._state.active_effects if effect.kind == "enfeebled")
    assert (effect.value, effect.expires_at_source_start,
            effect.expires_at_world_time) == (
        2, failure._state.actor_start_counts["wizard"] + 10,
        failure.inspect().world_time_seconds + 60,
    )
    path = tmp_path / "enfeeble-failure.json"
    failure.save(path)
    restored = Encounter.load(path)
    assert restored.inspect() == failure.inspect()


def test_frostbite_critical_failure_weakness_applies_then_expires(
    monkeypatch,
) -> None:
    durable_dog = replace(
        get_definition("guard_dog_mc2924"),
        definition_id="wizard_direct_review_durable_dog",
        hp=40,
    )
    setup = EncounterSetup(
        setup_id="wizard_direct_review_frostbite",
        name="Frostbite Weakness Review",
        width=5,
        height=3,
        placements=(
            CreaturePlacement(
                "wizard", "wizard_battle_magic_level_1_staged", "Wizard",
                "blue", Position(1, 1),
            ),
            CreaturePlacement(
                "fighter", "fighter_m_level_1", "Fighter",
                "blue", Position(2, 1),
            ),
            CreaturePlacement(
                "dog", durable_dog.definition_id, "Durable Dog",
                "red", Position(3, 1),
            ),
        ),
    )
    _register_staged(monkeypatch, setup, durable_dog)
    game = Encounter.start(setup, rolls=(20, 10, 1, 1, 1, 1, 15, 2))
    _settle(game)
    assert game.execute(Cast("frostbite", "dog")).status is ResultStatus.COMPLETED
    weakness = next(effect for effect in game._state.active_effects if effect.kind == "frostbite_weakness")
    assert (weakness.value, weakness.expires_at_source_start) == (
        1, game._state.actor_start_counts["wizard"] + 1
    )
    assert game.execute(EndTurn()).status is ResultStatus.COMPLETED
    strike = game.execute(Strike("dog", attack_id="fist"))
    assert strike.status is ResultStatus.PAUSED
    choice = strike.inspection.choice
    assert choice is not None
    resolved = game.choose(choice.choice_id, "keep", choice.owner_actor_id)
    damage = next(event.damage for event in resolved.events if event.damage is not None)
    assert damage.total == 7  # 1d4 (2) + Strength 4 + weakness 1.
    assert game.execute(EndTurn()).status is ResultStatus.COMPLETED
    assert game.execute(EndTurn()).status is ResultStatus.COMPLETED
    assert game.inspect().turn_actor_id == "wizard"
    assert not any(
        effect.kind == "frostbite_weakness" for effect in game._state.active_effects
    )


def test_telekinetic_projectile_rejects_a_loose_object_beyond_30_feet_atomically(
    monkeypatch,
) -> None:
    setup = EncounterSetup(
        setup_id="wizard_direct_review_far_object",
        name="Telekinetic Projectile Far Object Review",
        width=12,
        height=3,
        placements=(
            CreaturePlacement(
                "wizard", "wizard_battle_magic_level_1_telekinetic_projectile_prepared", "Wizard",
                "blue", Position(8, 1),
            ),
            CreaturePlacement(
                "item_ally", "wizard_battle_magic_level_1_staged", "Item Ally",
                "blue", Position(1, 1),
            ),
            CreaturePlacement(
                "dog", "guard_dog_mc2924", "Dog", "red", Position(10, 1),
            ),
        ),
    )
    _register_staged(monkeypatch, setup)
    game = Encounter.start(setup, rolls=(10, 20, 1, 20, 3, 4))
    _settle(game)
    assert game.inspect().turn_actor_id == "item_ally"
    assert game.execute(Release("item_ally:bonded_staff")).status is ResultStatus.COMPLETED
    assert game.execute(EndTurn()).status is ResultStatus.COMPLETED
    assert game.inspect().turn_actor_id == "wizard"
    before = game.inspect()
    dice_index = game._dice._index
    rejected = game.execute(Cast(
        "telekinetic_projectile", "dog", item_id="item_ally:bonded_staff"
    ))
    assert rejected.status is ResultStatus.REJECTED
    assert game.inspect() == before
    assert game._dice._index == dice_index


def test_telekinetic_projectile_rejects_a_profiled_two_bulk_object_atomically(
    monkeypatch,
) -> None:
    heavy_holder = replace(
        get_definition("wizard_battle_magic_level_1_staged"),
        definition_id="wizard_direct_review_heavy_holder",
        held_items=("heavy_object",),
        stowed_items=(),
        item_instances=(ItemInstance("heavy_object", "review_heavy_object"),),
        carried_item_bulk=(("heavy_object", 2),),
    )
    setup = EncounterSetup(
        setup_id="wizard_direct_review_heavy_object",
        name="Telekinetic Projectile Heavy Object Review",
        width=5,
        height=3,
        placements=(
            CreaturePlacement(
                "wizard", "wizard_battle_magic_level_1_telekinetic_projectile_prepared", "Wizard",
                "blue", Position(1, 1),
            ),
            CreaturePlacement(
                "holder", heavy_holder.definition_id, "Heavy Holder",
                "blue", Position(2, 1),
            ),
            CreaturePlacement(
                "dog", "guard_dog_mc2924", "Dog", "red", Position(3, 1),
            ),
        ),
    )
    _register_staged(monkeypatch, setup, heavy_holder)
    monkeypatch.setattr(
        spells,
        "TELEKINETIC_PROJECTILE_OBJECTS",
        MappingProxyType({
            **spells.TELEKINETIC_PROJECTILE_OBJECTS,
            "review_heavy_object": (2, "bludgeoning"),
        }),
    )
    game = Encounter.start(setup, rolls=(10, 20, 1, 20, 3, 4))
    _settle(game)
    assert game.inspect().turn_actor_id == "holder"
    assert game.execute(Release("holder:heavy_object")).status is ResultStatus.COMPLETED
    assert game.execute(EndTurn()).status is ResultStatus.COMPLETED
    assert game.inspect().turn_actor_id == "wizard"
    before = game.inspect()
    dice_index = game._dice._index
    rejected = game.execute(Cast(
        "telekinetic_projectile", "dog", item_id="holder:heavy_object"
    ))
    assert rejected.status is ResultStatus.REJECTED
    assert game.inspect() == before
    assert game._dice._index == dice_index


def test_telekinetic_projectile_is_a_saved_second_attack_with_map(
    tmp_path,
    monkeypatch,
) -> None:
    setup = EncounterSetup(
        setup_id="wizard_direct_review_tkp_map",
        name="Telekinetic Projectile MAP Review",
        width=5,
        height=3,
        placements=(
            CreaturePlacement(
                "wizard", "wizard_battle_magic_level_1_telekinetic_projectile_prepared", "Wizard",
                "blue", Position(1, 1),
            ),
            CreaturePlacement(
                "dog", "guard_dog_mc2924", "Dog", "red", Position(2, 1),
            ),
        ),
    )
    _register_staged(monkeypatch, setup)
    game = Encounter.start(setup, rolls=(20, 1, 5, 20, 3, 4))
    _settle(game)
    assert game.execute(Release("wizard:bonded_staff")).status is ResultStatus.COMPLETED
    first = game.execute(Strike("dog", attack_id="fist"))
    assert first.status is ResultStatus.PAUSED
    choice = first.inspection.choice
    assert choice is not None
    assert game.choose(
        choice.choice_id, "keep", choice.owner_actor_id
    ).status is ResultStatus.COMPLETED

    projectile = game.execute(Cast(
        "telekinetic_projectile", "dog", item_id="wizard:bonded_staff"
    ))
    assert projectile.status is ResultStatus.PAUSED
    pending = game._state.pending_choice
    assert pending is not None and pending.check is not None
    assert (
        pending.check.attack_count,
        pending.check.map_penalty,
        game._state.creatures["wizard"].strikes_this_turn,
    ) == (2, -5, 2)
    assert "attack" in pending.check.traits
    path = tmp_path / "telekinetic-projectile-second-attack.json"
    game.save(path)
    game = Encounter.load(path)
    pending_view = game.inspect().choice
    assert pending_view is not None
    completed = game.choose(
        pending_view.choice_id, "keep", pending_view.owner_actor_id
    )
    assert completed.status is ResultStatus.COMPLETED
    damage = next(event.damage for event in completed.events if event.damage is not None)
    assert damage.total == 14


def test_runic_body_does_not_stack_with_invested_plus_one_striking_handwraps(
    tmp_path,
    monkeypatch,
) -> None:
    durable_dog = replace(
        get_definition("guard_dog_mc2924"),
        definition_id="wizard_direct_review_runic_durable_dog",
        hp=40,
    )
    setup = EncounterSetup(
        setup_id="wizard_direct_review_runic_handwraps",
        name="Runic Body Handwrap Nonstacking Review",
        width=5,
        height=3,
        placements=(
            CreaturePlacement(
                "wizard", "wizard_battle_magic_level_1_runic_body_prepared",
                "Wizard", "blue", Position(1, 1),
            ),
            CreaturePlacement(
                "fighter", "fighter_m_invested_handwraps_test", "Fighter",
                "blue", Position(2, 1),
            ),
            CreaturePlacement(
                "dog", durable_dog.definition_id, "Dog", "red", Position(3, 1),
            ),
        ),
    )
    _register_staged(monkeypatch, setup, durable_dog)
    game = Encounter.start(setup, rolls=(20, 10, 1, 15, 2, 3))
    _settle(game)
    offered = game.execute(Cast("runic_body", "fighter"))
    assert offered.status is ResultStatus.PAUSED
    choice = offered.inspection.choice
    assert choice is not None and choice.kind == "spell_willingness"
    path = tmp_path / "runic-body-handwrap-willingness.json"
    game.save(path)
    game = Encounter.load(path)
    choice = game.inspect().choice
    assert choice is not None
    assert game.choose(
        choice.choice_id, "willing", choice.owner_actor_id
    ).status is ResultStatus.COMPLETED
    runic_effect = next(
        effect for effect in game._state.active_effects
        if effect.kind == "runic_body" and effect.target_actor_id == "fighter"
    )
    assert (
        runic_effect.expires_at_source_start,
        runic_effect.expires_at_world_time,
    ) == (
        game._state.actor_start_counts["wizard"] + 10,
        game.inspect().world_time_seconds + 60,
    )

    fighter = game._state.creatures["fighter"]
    fist = next(
        attack for attack in get_definition(fighter.definition_id).attacks
        if attack.attack_id == "fist"
    )
    profile = game._weapon_rune_profile_for_attack(game._state, fighter, fist)
    assert profile is not None
    assert (profile.potency, profile.striking_dice) == (1, 2)
    assert game.execute(EndTurn()).status is ResultStatus.COMPLETED
    strike = game.execute(Strike("dog", attack_id="fist"))
    assert strike.status is ResultStatus.PAUSED
    check = next(event.check for event in strike.events if event.check is not None)
    assert check is not None and check.modifier == 10
    choice = strike.inspection.choice
    assert choice is not None
    resolved = game.choose(choice.choice_id, "keep", choice.owner_actor_id)
    damage = next(event.damage for event in resolved.events if event.damage is not None)
    assert damage.components[0].dice == (4, 4)
    assert damage.components[0].rolls == (2, 3)
    while (
        game._state.actor_start_counts["wizard"]
        < runic_effect.expires_at_source_start
    ):
        assert game.execute(EndTurn()).status is ResultStatus.COMPLETED
    assert not any(
        effect.kind == "runic_body" for effect in game._state.active_effects
    )
