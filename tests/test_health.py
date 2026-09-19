"""Source-backed tests for the PC HP, dying, and recovery slice.

References: Player Core pp. 410–413, Remaster AoN rules IDs 2324–2329,
2332–2333, plus the Unconscious condition (ID 95).
"""

import pytest

from pf2e.health import (
    HealthState,
    RecoveryDegree,
    UnsupportedHealthRuleError,
    can_use_heroic_recovery,
    damage,
    healing,
    heroic_recovery,
    recovery_check,
    stabilize,
)


@pytest.mark.parametrize(
    ("critical_kwargs", "expected_dying"),
    [
        ({}, 2),
        ({"attacker_critical": True}, 3),
        ({"target_critical_failure": True}, 3),
    ],
)
def test_lethal_knockout_sets_dying_once_and_requests_turn_anchor(
    critical_kwargs: dict[str, bool], expected_dying: int
) -> None:
    initial = HealthState(hp=5, max_hp=12, wounded=1)

    result = damage(initial, 5, **critical_kwargs)

    assert initial.hp == 5  # transitions do not mutate the input
    assert result.state == HealthState(
        hp=0, max_hp=12, dying=expected_dying, wounded=1, unconscious=True
    )
    assert result.knocked_out
    assert result.initiative_before_current_turn
    assert result.drop_held_items and result.fall_prone
    assert result.dying_increased


def test_nonlethal_knockout_is_unconscious_without_dying_or_wounded() -> None:
    result = damage(HealthState(hp=2, max_hp=12, wounded=2), 4, nonlethal=True)

    assert result.state == HealthState(hp=0, max_hp=12, wounded=2, unconscious=True)
    assert result.knocked_out and result.initiative_before_current_turn
    assert result.drop_held_items and result.fall_prone
    assert not result.dying_increased


def test_additional_damage_to_stable_zero_hp_requires_a_product_ruling() -> None:
    stable = HealthState(hp=0, max_hp=12, wounded=1, unconscious=True)

    assert damage(stable, 0).state == stable

    with pytest.raises(UnsupportedHealthRuleError, match="awaits a product ruling"):
        damage(stable, 3)
    assert stable.hp == 0 and stable.dying == 0 and stable.unconscious


def test_damage_while_dying_increases_without_adding_wounded_and_offers_heroic_option() -> None:
    dying = HealthState(hp=0, max_hp=12, dying=1, wounded=2, unconscious=True)

    result = damage(dying, 1, hero_points=2)

    assert result.state.dying == 2
    assert result.state.wounded == 2
    assert result.dying_increased
    assert result.heroic_recovery_available
    assert result.heroic_recovery_option is not None
    assert result.heroic_recovery_option.state == HealthState(
        hp=0, max_hp=12, wounded=2, unconscious=True
    )
    assert result.heroic_recovery_option.dying_lost
    assert result.heroic_recovery_option.hero_points_spent == 2


def test_heroic_recovery_can_prevent_an_otherwise_fatal_dying_increase() -> None:
    dying = HealthState(hp=0, max_hp=12, dying=3, wounded=1, unconscious=True)

    result = damage(dying, 1, hero_points=1)

    assert result.state.dead
    assert result.heroic_recovery_available
    assert result.heroic_recovery_option is not None
    assert not result.heroic_recovery_option.state.dead
    assert result.heroic_recovery_option.state.dying == 0
    assert result.heroic_recovery_option.state.wounded == 1


def test_heroic_recovery_can_answer_initial_lethal_knockout_increase() -> None:
    result = damage(HealthState(hp=1, max_hp=12, wounded=3), 1, hero_points=2)

    assert result.state.dead  # initial dying 1 + wounded 3 reaches dying 4
    assert result.heroic_recovery_available
    assert result.heroic_recovery_option is not None
    assert result.heroic_recovery_option.state == HealthState(
        hp=0, max_hp=12, wounded=3, unconscious=True
    )
    assert result.heroic_recovery_option.knocked_out
    assert result.heroic_recovery_option.initiative_before_current_turn
    assert result.heroic_recovery_option.drop_held_items
    assert result.heroic_recovery_option.fall_prone


@pytest.mark.parametrize("initial", [
    HealthState(hp=2, max_hp=12),
    HealthState(hp=0, max_hp=12, dying=3, wounded=1, unconscious=True),
])
def test_massive_damage_kills_without_a_heroic_recovery_option(initial: HealthState) -> None:
    result = damage(initial, 24, hero_points=3)

    assert result.state.dead and result.state.hp == 0
    assert result.massive_damage_death
    assert not result.heroic_recovery_available
    assert result.heroic_recovery_option is None


def test_healing_above_zero_ends_dying_and_adds_wounded_once() -> None:
    result = healing(
        HealthState(hp=0, max_hp=12, dying=2, wounded=1, unconscious=True), 4
    )

    assert result.state == HealthState(hp=4, max_hp=12, wounded=2)
    assert result.dying_lost
    assert not result.drop_held_items and not result.fall_prone


def test_recovery_success_stabilizes_unconscious_and_increments_wounded_once() -> None:
    result = recovery_check(
        HealthState(hp=0, max_hp=12, dying=1, unconscious=True), "success"
    )

    assert result.state == HealthState(
        hp=0, max_hp=12, wounded=1, unconscious=True
    )
    assert result.dying_lost and result.stabilized
    assert not result.drop_held_items and not result.fall_prone


@pytest.mark.parametrize(
    ("degree", "expected_dying", "expected_wounded", "dead"),
    [
        ("critical_success", 0, 3, False),
        ("success", 1, 2, False),
        ("failure", 3, 2, False),
        ("critical_failure", 0, 2, True),
    ],
)
def test_recovery_degree_maps_to_dying_delta_without_rolling(
    degree: RecoveryDegree, expected_dying: int, expected_wounded: int, dead: bool
) -> None:
    result = recovery_check(
        HealthState(hp=0, max_hp=12, dying=2, wounded=2, unconscious=True),
        degree,
    )

    assert result.state.dying == expected_dying
    assert result.state.wounded == expected_wounded
    assert result.state.dead is dead
    assert result.dying_increased is (degree in ("failure", "critical_failure"))


def test_stabilize_spell_adds_wounded_but_heroic_recovery_preserves_it() -> None:
    dying = HealthState(hp=0, max_hp=12, dying=2, wounded=1, unconscious=True)

    ordinary = stabilize(dying)
    heroic = heroic_recovery(dying, hero_points=2)

    assert ordinary.state == HealthState(
        hp=0, max_hp=12, wounded=2, unconscious=True
    )
    assert ordinary.dying_lost and ordinary.stabilized
    assert heroic.state == HealthState(
        hp=0, max_hp=12, wounded=1, unconscious=True
    )
    assert heroic.hero_points_spent == 2
    assert heroic.dying_lost and heroic.stabilized


def test_heroic_recovery_timing_requires_a_point_and_a_valid_trigger() -> None:
    dying = HealthState(hp=0, max_hp=12, dying=2, unconscious=True)
    healthy = HealthState(hp=12, max_hp=12)

    assert can_use_heroic_recovery(dying, 1, at_start_of_turn=True)
    assert can_use_heroic_recovery(healthy, 1, dying_would_increase=True)
    assert not can_use_heroic_recovery(dying, 0, at_start_of_turn=True)
    assert not can_use_heroic_recovery(healthy, 1, at_start_of_turn=True)
    assert not can_use_heroic_recovery(dying, 1)


def test_dead_pc_cannot_be_healed() -> None:
    dead = HealthState(hp=0, max_hp=12, dead=True)

    assert healing(dead, 12).state == dead
