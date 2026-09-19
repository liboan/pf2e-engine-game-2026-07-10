"""Source-backed boundary tests for pure casting access and expenditure."""

from __future__ import annotations

import pytest

from pf2e.casting import (
    CastSelection,
    CastSelectionError,
    CastingResource,
    CastingSource,
    ResourceSpend,
    SpellAccess,
    available_casts,
    focus_pool_capacity,
    refocus_focus_points,
    validate_cast,
)


def test_prepared_spells_spend_the_selected_owned_slot_and_keep_grant_provenance() -> None:
    heal = SpellAccess("heal", 1)
    sources = (
        CastingSource("cleric_divine", "prepared", "divine", "wisdom", 7, 17, (heal,)),
        CastingSource("other_caster", "prepared", "arcane", "intelligence", 7, 17, (heal,)),
    )
    resources = (
        CastingResource("ordinary_heal_1", "cleric_divine", "prepared_slot", 1, 1, 1, "heal"),
        CastingResource("ordinary_heal_2", "cleric_divine", "prepared_slot", 1, 1, 1, "heal"),
        CastingResource("font_heal_1", "cleric_divine", "prepared_slot", 1, 1, 1, "heal"),
        CastingResource("other_heal_slot", "other_caster", "prepared_slot", 1, 1, 1, "heal"),
    )

    choices = available_casts(sources, resources)
    assert choices == (
        CastSelection("cleric_divine", "heal", 1, "ordinary_heal_1"),
        CastSelection("cleric_divine", "heal", 1, "ordinary_heal_2"),
        CastSelection("cleric_divine", "heal", 1, "font_heal_1"),
        CastSelection("other_caster", "heal", 1, "other_heal_slot"),
    )
    selected = choices[2]
    permission = validate_cast(selected, sources, resources)
    assert permission.spends == (ResourceSpend("font_heal_1", 1),)
    assert permission.spends[0].resource_id == "font_heal_1"
    assert permission.spends[0].amount == 1
    assert tuple(resource.remaining for resource in resources) == (1, 1, 1, 1)  # validation does not mutate snapshots
    selected_source = next(source for source in sources if source.source_id == permission.selection.source_id)
    assert (selected_source.tradition, selected_source.attribute, selected_source.attack_modifier, selected_source.dc) == (
        "divine",
        "wisdom",
        7,
        17,
    )

    with pytest.raises(CastSelectionError) as no_choice:
        validate_cast(CastSelection("cleric_divine", "heal", 1, None), sources, resources)
    assert no_choice.value.reason == "resource_choice_required"
    wrong_slot = CastSelection("cleric_divine", "heal", 1, "other_heal_slot")
    with pytest.raises(CastSelectionError) as wrong_owner:
        validate_cast(wrong_slot, sources, resources)
    assert wrong_owner.value.reason == "resource_not_owned"


def test_prepared_and_repertoire_rank_one_casts_use_different_resources_at_levels_one_and_two() -> None:
    repertoire = CastingSource(
        "bard_repertoire",
        "spontaneous",
        "occult",
        "charisma",
        7,
        17,
        (SpellAccess("heal", 1),),
    )
    prepared = CastingSource(
        "witch_prepared",
        "prepared",
        "primal",
        "intelligence",
        7,
        17,
        (SpellAccess("heal", 1), SpellAccess("fear", 1)),
    )

    # Both sources keep rank 1 at character levels 1 and 2. Bard advances from
    # two to three rank-1 slots and adds one repertoire spell; Witch advances
    # from two to three individually prepared rank-1 slots.
    for level, slot_count, repertoire_spells, attack, dc in (
        (
            1,
            2,
            (SpellAccess("fear", 1), SpellAccess("soothe", 1), SpellAccess("sure_strike", 1)),
            7,
            17,
        ),
        (
            2,
            3,
            (
                SpellAccess("fear", 1),
                SpellAccess("soothe", 1),
                SpellAccess("sure_strike", 1),
                SpellAccess("bless", 1),
            ),
            8,
            18,
        ),
    ):
        repertoire_at_level = CastingSource(
            repertoire.source_id,
            repertoire.kind,
            repertoire.tradition,
            repertoire.attribute,
            attack,
            dc,
            repertoire_spells,
        )
        rank_pool = CastingResource(
            f"bard_rank1_level{level}",
            repertoire_at_level.source_id,
            "rank_slots",
            1,
            slot_count,
            slot_count,
        )
        repertoire_choices = available_casts((repertoire_at_level,), (rank_pool,))
        assert len(repertoire_choices) == len(repertoire_spells)
        assert {choice.rank for choice in repertoire_choices} == {1}
        assert {choice.resource_id for choice in repertoire_choices} == {rank_pool.resource_id}
        assert all(
            validate_cast(choice, (repertoire_at_level,), (rank_pool,)).spends
            == (ResourceSpend(rank_pool.resource_id, 1),)
            for choice in repertoire_choices
        )
        assert (repertoire_at_level.attack_modifier, repertoire_at_level.dc) == (attack, dc)

        prepared_source = CastingSource(
            prepared.source_id,
            prepared.kind,
            prepared.tradition,
            prepared.attribute,
            attack,
            dc,
            prepared.spells,
        )
        prepared_slots = tuple(
            CastingResource(
                f"witch_heal_{level}_{number}",
                prepared_source.source_id,
                "prepared_slot",
                1,
                1,
                1,
                "heal",
            )
            for number in range(1, slot_count + 1)
        )
        prepared_choices = available_casts((prepared_source,), prepared_slots)
        assert len(prepared_choices) == slot_count
        assert {choice.spell_id for choice in prepared_choices} == {"heal"}
        assert {choice.resource_id for choice in prepared_choices} == {slot.resource_id for slot in prepared_slots}
        assert all(
            validate_cast(choice, (prepared_source,), prepared_slots).spends
            == (ResourceSpend(choice.resource_id, 1),)
            for choice in prepared_choices
        )

    # Having a higher-rank slot does not grant an unlisted heightened rank.
    rank_two_slot = CastingResource("rank2", repertoire.source_id, "rank_slots", 2, 1, 1)
    with pytest.raises(CastSelectionError) as unlisted_rank:
        validate_cast(
            CastSelection(repertoire.source_id, "heal", 2, "rank2"),
            (repertoire,),
            (rank_two_slot,),
        )
    assert unlisted_rank.value.reason == "rank_unavailable"


def test_cantrips_are_repeatable_and_require_no_resource() -> None:
    source = CastingSource(
        "wizard_arcane",
        "prepared",
        "arcane",
        "intelligence",
        7,
        17,
        (SpellAccess("electric_arc", 1, cantrip=True),),
    )
    selection = CastSelection("wizard_arcane", "electric_arc", 1, None)
    assert available_casts((source,), ()) == (selection,)
    assert validate_cast(selection, (source,), ()).spends == ()
    with pytest.raises(CastSelectionError) as unnecessary_spend:
        validate_cast(
            CastSelection("wizard_arcane", "electric_arc", 1, "slot"),
            (source,),
            (CastingResource("slot", "wizard_arcane", "prepared_slot", 1, 1, 1, "electric_arc"),),
        )
    assert unnecessary_spend.value.reason == "cantrip_has_no_cost"


def test_focus_sources_share_one_actor_pool_and_refocus_restores_one_point() -> None:
    sources = (
        CastingSource("cleric_domain", "focus", "divine", "wisdom", 8, 18, (SpellAccess("fire_ray", 1),)),
        CastingSource("druid_order", "focus", "primal", "wisdom", 7, 17, (SpellAccess("storm_burst", 1),)),
        CastingSource("witch_hex", "focus", "primal", "intelligence", 7, 17, (SpellAccess("phase_familiar", 1),)),
        CastingSource("witch_hex_cantrip", "focus", "primal", "intelligence", 7, 17, (SpellAccess("patron_hex", 1, cantrip=True),)),
    )
    pool = CastingResource("actor_focus_pool", None, "focus_points", 0, 3, 2)

    assert focus_pool_capacity(sources) == 3
    choices = available_casts(sources, (pool,))
    focus_choices = tuple(choice for choice in choices if choice.resource_id is not None)
    assert {choice.resource_id for choice in focus_choices} == {"actor_focus_pool"}
    assert {choice.source_id for choice in focus_choices} == {"cleric_domain", "druid_order", "witch_hex"}
    assert CastSelection("witch_hex_cantrip", "patron_hex", 1, None) in choices
    domain_cast = next(choice for choice in choices if choice.source_id == "cleric_domain")
    assert validate_cast(domain_cast, sources, (pool,)).spends[0].amount == 1
    assert validate_cast(domain_cast, sources, (pool,)).spends[0].resource_id == pool.resource_id

    restored = refocus_focus_points(pool)
    assert restored.remaining == 3
    assert restored.capacity == 3
    assert pool.remaining == 2
    assert refocus_focus_points(restored).remaining == 3

    duplicated_pool = (pool, CastingResource("second_pool", None, "focus_points", 0, 1, 1))
    with pytest.raises(CastSelectionError) as duplicate:
        available_casts(sources, duplicated_pool)
    assert duplicate.value.reason == "duplicate_focus_pool"


def test_innate_spells_use_their_own_spell_specific_daily_resource() -> None:
    source = CastingSource(
        "ancestry_innate",
        "innate",
        "divine",
        "charisma",
        5,
        15,
        (SpellAccess("heal", 1), SpellAccess("fear", 1)),
    )
    use = CastingResource("ancestry_heal_daily", source.source_id, "innate_uses", 1, 1, 1, "heal")
    selection = CastSelection(source.source_id, "heal", 1, use.resource_id)

    assert available_casts((source,), (use,)) == (selection,)
    assert validate_cast(selection, (source,), (use,)).spends[0].amount == 1
    spent = CastingResource(use.resource_id, use.source_id, use.kind, use.rank, use.capacity, 0, use.spell_id)
    assert available_casts((source,), (spent,)) == ()
    with pytest.raises(CastSelectionError) as exhausted:
        validate_cast(selection, (source,), (spent,))
    assert exhausted.value.reason == "resource_depleted"

    unbound = CastingResource("ancestry_unbound_daily", source.source_id, "innate_uses", 1, 1, 1)
    with pytest.raises(CastSelectionError) as missing_spell:
        available_casts((source,), (unbound,))
    assert missing_spell.value.reason == "invalid_innate_use"

    fear_use = CastingResource("ancestry_fear_daily", source.source_id, "innate_uses", 1, 1, 1, "fear")
    heal_with_fear_use = CastSelection(source.source_id, "heal", 1, fear_use.resource_id)
    assert available_casts((source,), (fear_use,)) == (
        CastSelection(source.source_id, "fear", 1, fear_use.resource_id),
    )
    with pytest.raises(CastSelectionError) as wrong_spell:
        validate_cast(heal_with_fear_use, (source,), (fear_use,))
    assert wrong_spell.value.reason == "resource_not_owned"


def test_staff_spend_uses_rank_charges_or_one_charge_plus_a_spontaneous_slot() -> None:
    staff = CastingSource(
        "staff_nexus",
        "staff",
        "arcane",
        "intelligence",
        7,
        17,
        (SpellAccess("force_barrage", 1), SpellAccess("staff_cantrip", 1, cantrip=True)),
    )
    spontaneous = CastingSource(
        "bard_repertoire",
        "spontaneous",
        "occult",
        "charisma",
        8,
        18,
        (SpellAccess("soothe", 1),),
    )
    charges = CastingResource("staff_charges", staff.source_id, "staff_charges", 0, 1, 1)
    slot = CastingResource("bard_slot", spontaneous.source_id, "rank_slots", 1, 2, 2)
    sources = (staff, spontaneous)
    resources = (charges, slot)

    staff_cast = CastSelection(staff.source_id, "force_barrage", 1, charges.resource_id)
    assert available_casts(sources, resources).count(staff_cast) == 1
    assert validate_cast(staff_cast, sources, resources).spends == (ResourceSpend(charges.resource_id, 1),)
    with pytest.raises(CastSelectionError) as staff_choice:
        validate_cast(CastSelection(staff.source_id, "force_barrage", 1, None), sources, resources)
    assert staff_choice.value.reason == "resource_choice_required"
    supplemented = CastSelection(
        staff.source_id,
        "force_barrage",
        1,
        charges.resource_id,
        supplemental_resource_id=slot.resource_id,
    )
    assert supplemented in available_casts(sources, resources)
    assert [(spend.resource_id, spend.amount) for spend in validate_cast(supplemented, sources, resources).spends] == [
        (charges.resource_id, 1),
        (slot.resource_id, 1),
    ]

    cantrip = CastSelection(staff.source_id, "staff_cantrip", 1, None)
    assert validate_cast(cantrip, sources, resources).spends == ()
    no_charges = CastingResource(charges.resource_id, charges.source_id, charges.kind, 0, 1, 0)
    with pytest.raises(CastSelectionError) as depleted:
        validate_cast(staff_cast, sources, (no_charges, slot))
    assert depleted.value.reason == "resource_depleted"


def test_invalid_resource_kind_and_focus_refocus_do_not_alias_class_resources() -> None:
    source = CastingSource("wizard", "prepared", "arcane", "intelligence", 7, 17, ())
    wrong_pool = CastingResource("fake_focus", "wizard", "focus_points", 0, 1, 1)
    with pytest.raises(CastSelectionError) as invalid_owner:
        available_casts((source,), (wrong_pool,))
    assert invalid_owner.value.reason == "invalid_focus_pool_owner"

    class_slot = CastingResource("slot", "wizard", "prepared_slot", 1, 1, 0, "magic_missile")
    with pytest.raises(CastSelectionError) as wrong_refocus:
        refocus_focus_points(class_slot)
    assert wrong_refocus.value.reason == "not_focus_pool"
