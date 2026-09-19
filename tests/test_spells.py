from __future__ import annotations

from dataclasses import FrozenInstanceError

import pytest

from pf2e.checks import DegreeOfSuccess
from pf2e.model import Position
from pf2e.persistence import DiceSource
from pf2e.spells import (
    SPELLS,
    basic_save_damage,
    divine_lance_damage,
    heal_range_ft,
    heal_roll,
    in_heal_emanation,
    soothe_roll,
    spell_traits,
    void_warp_effect,
)


def test_fixed_spell_metadata_is_frozen_and_marks_only_deferred_spells_unavailable() -> None:
    assert set(SPELLS) == {
        "divine_lance",
        "void_warp",
        "guidance",
        "stabilize",
        "read_aura",
        "heal",
        "soothe",
        "angelic_halo",
        "courageous_anthem",
        "lingering_composition",
        "force_bolt",
            "tempest_surge",
            "life_link",
            "vitality_lash",
        "shield",
        "force_barrage",
        "breathe_fire",
        "light",
        "fear",
        "runic_weapon",
        "sure_strike",
        "electric_arc",
        "telekinetic_projectile",
        "frostbite",
        "enfeeble",
        "runic_body",
        "ignition",
        "caustic_blast",
        "gouging_claw",
        "tangle_vine",
        "gale_blast",
        "stoke_the_heart",
        "patrons_puppet",
        "command",
        "forbidding_ward",
        "sigil",
        "detect_magic",
    }
    with pytest.raises(TypeError):
        SPELLS["new"] = SPELLS["heal"]  # type: ignore[index]
    with pytest.raises(FrozenInstanceError):
        SPELLS["heal"].name = "Other"  # type: ignore[misc]

    assert SPELLS["read_aura"].action_costs == ()
    assert "one-minute" in SPELLS["read_aura"].unavailable_reason
    assert SPELLS["light"].action_costs == (2,)
    assert SPELLS["light"].range_ft == 120
    assert SPELLS["light"].cantrip is True
    assert SPELLS["light"].unavailable_reason is None
    assert "light" in SPELLS["light"].traits
    assert SPELLS["runic_weapon"].action_costs == (2,)
    assert SPELLS["runic_weapon"].unavailable_reason is None
    assert SPELLS["courageous_anthem"].action_costs == (1,)
    assert SPELLS["courageous_anthem"].range_ft is None
    assert SPELLS["courageous_anthem"].traits == frozenset(
        {"bard", "cantrip", "composition", "concentrate", "emotion", "mental"}
    )
    assert SPELLS["lingering_composition"].action_costs == (0,)
    assert SPELLS["lingering_composition"].traits == frozenset(
        {"bard", "concentrate", "focus", "spellshape"}
    )
    assert SPELLS["shield"].action_costs == (1,)
    assert SPELLS["shield"].range_ft is None
    assert SPELLS["shield"].cantrip is True
    assert SPELLS["shield"].traits == frozenset({"cantrip", "concentrate", "force"})
    assert SPELLS["force_bolt"].action_costs == (1,)
    assert SPELLS["force_bolt"].range_ft == 30
    assert SPELLS["force_barrage"].action_costs == (1, 2, 3)
    assert SPELLS["electric_arc"].action_costs == (2,)
    assert SPELLS["electric_arc"].range_ft == 30
    assert SPELLS["electric_arc"].traits == frozenset(
        {"cantrip", "concentrate", "electricity", "manipulate"}
    )
    assert SPELLS["force_barrage"].range_ft == 120
    assert SPELLS["breathe_fire"].action_costs == (2,)
    assert SPELLS["breathe_fire"].range_ft is None
    assert SPELLS["fear"].unavailable_reason is None
    assert SPELLS["sure_strike"].action_costs == (1,)
    assert SPELLS["sure_strike"].traits == frozenset({"concentrate", "fortune"})
    assert SPELLS["soothe"].action_costs == (2,)
    assert SPELLS["soothe"].range_ft == 30
    assert SPELLS["soothe"].traits == frozenset({"concentrate", "emotion", "healing", "mental"})
    assert SPELLS["soothe"].cantrip is False
    assert SPELLS["divine_lance"].traits == frozenset(
        {"attack", "cantrip", "concentrate", "manipulate", "sanctified", "spirit"}
    )
    assert "manipulate" not in SPELLS["guidance"].traits


def test_soothe_roll_is_rank_one_d10_plus_four() -> None:
    calls: list[int] = []

    def roll(sides: int) -> int:
        calls.append(sides)
        return 6

    healing = soothe_roll(roll)
    assert calls == [10]
    assert healing.rolls == (6,)
    assert healing.modifier == 4
    assert healing.total == 10


def test_divine_lance_rolls_only_on_hit_and_doubles_complete_damage_on_critical() -> None:
    calls: list[int] = []

    def roll(sides: int) -> int:
        calls.append(sides)
        return 4

    assert divine_lance_damage(DegreeOfSuccess.FAILURE, roll) is None
    assert calls == []

    success = divine_lance_damage(DegreeOfSuccess.SUCCESS, roll)
    assert success is not None
    assert success.total == 8
    assert success.multiplier == 1
    assert success.components[0].damage_type == "spirit"

    critical = divine_lance_damage(DegreeOfSuccess.CRITICAL_SUCCESS, roll)
    assert critical is not None
    assert critical.rolled_total == 8
    assert critical.total == 16
    assert critical.multiplier == 2
    assert calls == [4] * 4


@pytest.mark.parametrize(
    ("degree", "expected"),
    [
        (DegreeOfSuccess.CRITICAL_SUCCESS, 0),
        (DegreeOfSuccess.SUCCESS, 3),
        (DegreeOfSuccess.FAILURE, 7),
        (DegreeOfSuccess.CRITICAL_FAILURE, 14),
    ],
)
def test_void_warp_applies_basic_save_and_critical_failure_condition(
    degree: DegreeOfSuccess,
    expected: int,
) -> None:
    calls: list[int] = []

    def roll(sides: int) -> int:
        calls.append(sides)
        return 3 if len(calls) == 1 else 4

    result = void_warp_effect(degree, roll)

    assert result.damage.rolled_total == 7
    assert result.damage.total == expected
    assert result.damage.components[0].amount == expected
    assert result.enfeebled == (1 if degree is DegreeOfSuccess.CRITICAL_FAILURE else 0)
    assert calls == [4, 4]


def test_basic_save_damage_keeps_positive_one_when_halved() -> None:
    assert basic_save_damage(1, DegreeOfSuccess.SUCCESS) == 1


def test_spell_helpers_accept_the_existing_dice_source_draw_method() -> None:
    dice = DiceSource(rolls=(4, 3, 5))

    lance = divine_lance_damage(DegreeOfSuccess.SUCCESS, dice.draw)
    heal = heal_roll(2, dice.draw)

    assert lance is not None and lance.total == 7
    assert heal.total == 13
    assert dice.to_data()["index"] == 3


@pytest.mark.parametrize(
    ("actions", "expected_modifier", "expected_total", "expected_range"),
    [(1, 0, 5, None), (2, 8, 13, 30), (3, 0, 5, None)],
)
def test_heal_modes_roll_one_shared_d8_and_only_two_actions_adds_eight(
    actions: int,
    expected_modifier: int,
    expected_total: int,
    expected_range: int | None,
) -> None:
    calls: list[int] = []

    def roll(sides: int) -> int:
        calls.append(sides)
        return 5

    result = heal_roll(actions, roll)

    assert result.rolls == (5,)
    assert result.modifier == expected_modifier
    assert result.total == expected_total
    assert heal_range_ft(actions) == expected_range
    assert ("concentrate" in spell_traits("heal", actions)) is (actions in (2, 3))
    assert calls == [8]


@pytest.mark.parametrize(
    ("offset", "included"),
    [((4, 4), True), ((5, 3), True), ((6, 1), True), ((6, 2), False)],
)
def test_heal_emanation_uses_ordinary_grid_distance(offset, included: bool) -> None:
    origin = Position(0, 0)
    target = Position(*offset)

    assert in_heal_emanation(origin, target) is included


@pytest.mark.parametrize("face", [0, 9, True, 1.5])
def test_healing_roll_rejects_invalid_die_results(face) -> None:
    with pytest.raises(ValueError):
        heal_roll(1, lambda _sides: face)


@pytest.mark.parametrize("face", [0, 5, True])
def test_damage_helpers_reject_invalid_d4_results(face) -> None:
    with pytest.raises(ValueError):
        divine_lance_damage(DegreeOfSuccess.SUCCESS, lambda _sides: face)


def test_helpers_reject_invalid_actions_and_check_degrees() -> None:
    with pytest.raises(ValueError):
        heal_roll(0, lambda _sides: 1)
    with pytest.raises(ValueError):
        spell_traits("heal", 4)
    with pytest.raises(TypeError):
        spell_traits("heal", True)
    with pytest.raises(TypeError):
        divine_lance_damage(2, lambda _sides: 1)  # type: ignore[arg-type]
