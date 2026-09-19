"""Massive damage uses damage before temporary HP absorption.

Player Core rules reproduced by Archives of Nethys:
https://2e.aonprd.com/Rules.aspx?ID=2332 says a blow dealing at least twice
maximum HP causes instant death; https://2e.aonprd.com/Rules.aspx?ID=2321
tracks temporary HP separately and says it is reduced first. Applying both
rules means the massive-damage comparison uses damage before temporary HP.
"""

import pytest

from pf2e.health import HealthState, damage


@pytest.mark.parametrize(
    ("damage_taken", "expected_hp", "expected_massive_death"),
    [
        (39, 15, False),
        (40, 0, True),
    ],
)
def test_massive_damage_threshold_uses_damage_before_temp_hp(
    damage_taken: int,
    expected_hp: int,
    expected_massive_death: bool,
) -> None:
    state = HealthState(hp=20, max_hp=20)

    result = damage(state, 5, damage_taken=damage_taken, hero_points=2)

    assert result.state.hp == expected_hp
    assert result.state.dead is expected_massive_death
    assert result.massive_damage_death is expected_massive_death
    if expected_massive_death:
        assert not result.heroic_recovery_available
        assert result.heroic_recovery_option is None


def test_full_temp_hp_absorption_does_not_bypass_massive_damage() -> None:
    state = HealthState(hp=20, max_hp=20)

    result = damage(state, 0, damage_taken=40, hero_points=1)

    assert result.state.dead
    assert result.massive_damage_death
    assert not result.heroic_recovery_available


def test_omitted_damage_taken_keeps_existing_damage_behavior() -> None:
    state = HealthState(hp=20, max_hp=20)

    assert damage(state, 4) == damage(state, 4, damage_taken=4)


@pytest.mark.parametrize(
    ("amount", "damage_taken", "error", "message"),
    [
        (1, -1, ValueError, "damage_taken cannot be negative"),
        (1, 0, ValueError, "damage_taken cannot be less than damage"),
        (1, True, TypeError, "damage_taken must be an integer"),
        (1, 1.5, TypeError, "damage_taken must be an integer"),
    ],
)
def test_damage_taken_must_be_a_coherent_nonnegative_integer(
    amount: int,
    damage_taken: object,
    error: type[Exception],
    message: str,
) -> None:
    with pytest.raises(error, match=message):
        damage(HealthState(hp=20, max_hp=20), amount, damage_taken=damage_taken)  # type: ignore[arg-type]
