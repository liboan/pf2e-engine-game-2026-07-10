"""Source-backed tests for typed damage terms and one-effect defenses.

Rules checked here: Player Core pp. 407–408, including Spring 2026 errata
(https://paizo.com/pathfinder/faq); GM Core p. 242 alchemical bomb splash as
revised by Spring 2026 errata at the same FAQ. The official Paizo summary is
https://paizo.com/blog/spring-errata-2026.
"""

from __future__ import annotations

import pytest

from pf2e.damage import (
    DamageComponent,
    DamageDefense,
    DamageGroup,
    DamagePartRef,
    DamageResult,
    DamageTerm,
    DefenseSelection,
    absorb_temporary_hp,
    apply_damage_defenses,
    damage_defense_choices,
    roll_damage_terms,
)


def _result(*components: DamageComponent) -> DamageResult:
    total = sum(component.amount for component in components)
    return DamageResult(tuple(components), total, 1, total)


def _part(result: int, component: int) -> DamagePartRef:
    return DamagePartRef(result, component)


def test_critical_modes_keep_splash_and_deadly_outside_base_strike_doubling() -> None:
    terms = (
        DamageTerm("bomb", "piercing", (6,), modifier=2),
        DamageTerm("precision", "piercing", (4,), tags=frozenset({"precision"})),
        DamageTerm("splash", "fire", (), modifier=2, tags=frozenset({"splash"}), critical_mode="unchanged"),
        DamageTerm("deadly", "piercing", (10,), tags=frozenset({"deadly"}), critical_mode="critical_only"),
    )

    normal_calls: list[int] = []
    normal = roll_damage_terms(terms, lambda sides: normal_calls.append(sides) or 4)
    assert normal_calls == [6, 4]
    assert [component.amount for component in normal.components] == [6, 4, 2, 0]
    assert normal.total == 12
    assert normal.components[1].tags == frozenset({"precision"})
    assert normal.components[2].tags == frozenset({"splash"})
    assert normal.components[2].critical_mode == "unchanged"
    assert normal.components[3].rolls == ()

    critical_calls: list[int] = []

    def critical_roll(sides: int) -> int:
        critical_calls.append(sides)
        return {6: 4, 4: 3, 10: 7}[sides]

    critical = roll_damage_terms(terms, critical_roll, critical=True)
    assert critical_calls == [6, 4, 10]
    assert [component.amount for component in critical.components] == [12, 6, 2, 7]
    assert critical.total == 27
    assert critical.components[0].dice == (6,)
    assert critical.components[3].critical_mode == "critical_only"


def test_flurry_group_applies_precision_immunity_weaknesses_and_each_resistance_once() -> None:
    first = _result(
        DamageComponent("flurry strike one", "slashing", 0, (), 0, 10),
        DamageComponent("precision", "slashing", 0, (), 0, 4, frozenset({"precision"})),
        DamageComponent("energy", "fire", 0, (), 0, 3),
    )
    second = _result(
        DamageComponent("flurry strike two", "slashing", 0, (), 0, 5),
        DamageComponent("precision", "slashing", 0, (), 0, 2, frozenset({"precision"})),
        DamageComponent("energy", "fire", 0, (), 0, 1),
    )
    group = DamageGroup("flurry", (first, second), "strike", frozenset({"agile"}))
    defenses = (
        DamageDefense("immunity", "precision", source="precision ward"),
        DamageDefense("weakness", "slashing", 3, source="slashing weakness"),
        DamageDefense("weakness", "fire", 2, source="fire weakness"),
        DamageDefense("resistance", "physical", 4, source="physical resistance"),
        DamageDefense("resistance", "all", 5, source="all resistance"),
    )

    choices = damage_defense_choices(group, defenses)
    assert len(choices) == 1
    assert choices[0].defense_source == "all resistance"
    assert choices[0].eligible_parts == (_part(0, 0), _part(0, 2), _part(1, 0), _part(1, 2))

    pending = apply_damage_defenses(group, defenses)
    assert pending.total == 20  # precision removed, both weaknesses once, physical resistance once
    assert pending.unresolved_choices == choices
    assert [component.amount for component in pending.results[0].components] == [9, 0, 5]
    assert [component.amount for component in pending.results[1].components] == [5, 0, 1]

    selected = apply_damage_defenses(
        group,
        defenses,
        (DefenseSelection("all resistance", _part(0, 2)),),
    )
    assert selected.unresolved_choices == ()
    assert selected.total == 15
    assert [component.amount for component in selected.results[0].components] == [9, 0, 0]
    assert [component.amount for component in selected.results[1].components] == [5, 0, 1]
    assert selected.applied_defenses == (
        "precision ward",
        "slashing weakness",
        "fire weakness",
        "physical resistance",
        "all resistance",
    )


def test_damage_type_and_material_weaknesses_both_apply_once_before_resistance() -> None:
    group = DamageGroup(
        "silver strike",
        (_result(DamageComponent("weapon", "slashing", 0, (), 0, 8, frozenset({"silver"}))),),
        "strike",
    )
    defenses = (
        DamageDefense("weakness", "slashing", 3, source="slashing weakness"),
        DamageDefense("weakness", "silver", 5, source="silver weakness"),
        DamageDefense("resistance", "slashing", 10, source="slashing resistance"),
    )

    result = apply_damage_defenses(group, defenses)
    assert result.total == 6
    assert result.results[0].components[0].amount == 6
    assert result.applied_defenses == (
        "slashing weakness",
        "silver weakness",
        "slashing resistance",
    )


def test_damage_type_immunity_does_not_wipe_other_types_in_a_mixed_effect() -> None:
    group = DamageGroup(
        "mixed spell",
        (
            _result(
                DamageComponent("flame", "fire", 0, (), 0, 2),
                DamageComponent("frost", "cold", 0, (), 0, 4),
            ),
        ),
        "spell",
        frozenset({"fire"}),
    )
    result = apply_damage_defenses(
        group, (DamageDefense("immunity", "fire", source="fire immunity"),)
    )
    assert result.total == 4
    assert [component.amount for component in result.results[0].components] == [0, 4]


def test_broad_resistance_choice_is_limited_by_exceptions_and_is_not_guessed() -> None:
    group = DamageGroup(
        "mixed weapon",
        (
            _result(
                DamageComponent("ordinary", "slashing", 0, (), 0, 4),
                DamageComponent("silver", "slashing", 0, (), 0, 7, frozenset({"silver"})),
                DamageComponent("fire", "fire", 0, (), 0, 5),
            ),
        ),
        "strike",
    )
    defense = DamageDefense(
        "resistance", "physical", 3, exceptions=frozenset({"silver"}), source="physical except silver"
    )

    assert damage_defense_choices(group, (defense,)) == ()
    result = apply_damage_defenses(group, (defense,))
    assert result.total == 13
    assert [component.amount for component in result.results[0].components] == [1, 7, 5]

    broad = DamageDefense("resistance", "all", 4, source="all resistance")
    pending = apply_damage_defenses(group, (broad,))
    assert pending.total == 16
    assert pending.unresolved_choices[0].eligible_parts == (_part(0, 0), _part(0, 1), _part(0, 2))
    with pytest.raises(ValueError, match="not eligible"):
        apply_damage_defenses(group, (broad,), (DefenseSelection("all resistance", _part(4, 0)),))


@pytest.mark.parametrize(
    ("amount", "temporary_hp", "remaining_temp", "hp_damage", "absorbed"),
    [(7, 3, 0, 4, 3), (2, 5, 3, 0, 2), (0, 0, 0, 0, 0)],
)
def test_temporary_hp_absorbs_damage_before_hp(amount, temporary_hp, remaining_temp, hp_damage, absorbed) -> None:
    result = absorb_temporary_hp(amount, temporary_hp)
    assert (result.temporary_hp, result.damage_to_hp, result.absorbed) == (
        remaining_temp,
        hp_damage,
        absorbed,
    )


@pytest.mark.parametrize(("amount", "temporary_hp"), [(-1, 0), (1, -1), (True, 2), (1, False)])
def test_temporary_hp_rejects_negative_or_non_integer_inputs(amount, temporary_hp) -> None:
    with pytest.raises(ValueError):
        absorb_temporary_hp(amount, temporary_hp)
