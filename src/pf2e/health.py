"""Player-character hit point, dying, and recovery transitions.

This module does not roll checks, choose targets, update initiative, or mutate
inventory. Its immutable results include flags for the encounter layer to apply.
The focused rules here are from the Remaster Player Core: Temporary Hit Points
and Getting Knocked Out (PC 410), Dying and Recovery (PC 411), Massive Damage
(PC 412), and Hero Points (PC 413).

Rules references:
https://2e.aonprd.com/Rules.aspx?ID=2321
https://2e.aonprd.com/Rules.aspx?ID=2324
https://2e.aonprd.com/Rules.aspx?ID=2325
https://2e.aonprd.com/Rules.aspx?ID=2326
https://2e.aonprd.com/Rules.aspx?ID=2327
https://2e.aonprd.com/Rules.aspx?ID=2328
https://2e.aonprd.com/Rules.aspx?ID=2329
https://2e.aonprd.com/Rules.aspx?ID=2332
https://2e.aonprd.com/Rules.aspx?ID=2333
https://2e.aonprd.com/Conditions.aspx?ID=95
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Literal


RecoveryDegree = Literal["critical_success", "success", "failure", "critical_failure"]


class UnsupportedHealthRuleError(NotImplementedError):
    """A health event needs an explicit rule or product ruling before resolution."""


@dataclass(frozen=True, slots=True)
class HealthState:
    """The health facts used by PC dying rules; ordinary NPC mode is separate."""

    hp: int
    max_hp: int
    dying: int = 0
    wounded: int = 0
    unconscious: bool = False
    dead: bool = False

    def __post_init__(self) -> None:
        for name in ("hp", "max_hp", "dying", "wounded"):
            value = getattr(self, name)
            if type(value) is not int:
                raise TypeError(f"{name} must be an integer")
        if self.max_hp < 1:
            raise ValueError("max_hp must be positive")
        if not 0 <= self.hp <= self.max_hp:
            raise ValueError("hp must be between 0 and max_hp")
        if self.dying < 0 or self.wounded < 0:
            raise ValueError("dying and wounded values cannot be negative")


@dataclass(frozen=True, slots=True)
class HealthTransition:
    """A proposed transition plus encounter-layer effects and choice options."""

    state: HealthState
    knocked_out: bool = False
    initiative_before_current_turn: bool = False
    drop_held_items: bool = False
    fall_prone: bool = False
    dying_increased: bool = False
    dying_lost: bool = False
    stabilized: bool = False
    massive_damage_death: bool = False
    heroic_recovery_available: bool = False
    heroic_recovery_option: HealthTransition | None = None
    hero_points_spent: int = 0


def _check_hero_points(hero_points: int) -> None:
    if type(hero_points) is not int:
        raise TypeError("hero_points must be an integer")
    if hero_points < 0:
        raise ValueError("hero_points cannot be negative")


def _check_damage_or_healing(amount: int, name: str) -> None:
    if type(amount) is not int:
        raise TypeError(f"{name} must be an integer")
    if amount < 0:
        raise ValueError(f"{name} cannot be negative")


def _dead_state(state: HealthState) -> HealthState:
    # Death ends the dying/unconscious conditions and fixes HP at 0.
    return replace(state, hp=0, dying=0, unconscious=False, dead=True)


def _stable_state(state: HealthState) -> HealthState:
    return replace(state, hp=0, dying=0, unconscious=True, dead=False)


def _heroic_recovery_result(
    state: HealthState,
    hero_points: int,
    *,
    knocked_out: bool = False,
    initiative_before_current_turn: bool = False,
    drop_held_items: bool = False,
    fall_prone: bool = False,
) -> HealthTransition:
    """Build the Heroic Recovery branch without adding or increasing wounded."""
    return HealthTransition(
        state=_stable_state(state),
        knocked_out=knocked_out,
        initiative_before_current_turn=initiative_before_current_turn,
        drop_held_items=drop_held_items,
        fall_prone=fall_prone,
        dying_lost=state.dying > 0,
        stabilized=True,
        hero_points_spent=hero_points,
    )


def can_use_heroic_recovery(
    state: HealthState,
    hero_points: int,
    *,
    at_start_of_turn: bool = False,
    dying_would_increase: bool = False,
) -> bool:
    """Return whether the rules offer Heroic Recovery at this timing point.

    The caller supplies timing: it is valid at the start of the PC's turn while
    dying, or immediately before an event that would increase dying (including
    the initial increase on a lethal KO). Massive-death resolution takes
    precedence and must not be represented as a dying increase.
    """
    _check_hero_points(hero_points)
    if state.dead or hero_points < 1:
        return False
    return (at_start_of_turn and state.dying > 0) or dying_would_increase


def damage(
    state: HealthState,
    amount: int,
    *,
    damage_taken: int | None = None,
    attacker_critical: bool = False,
    target_critical_failure: bool = False,
    nonlethal: bool = False,
    hero_points: int = 0,
) -> HealthTransition:
    """Apply one resolved damage amount to a PC health state.

    ``amount`` is the damage that reaches HP after temporary HP absorption.
    ``damage_taken`` is the damage after defenses and Shield Block but before
    temporary HP; it governs only the massive-damage threshold and defaults to
    ``amount`` for callers that do not track the distinction.

    ``attacker_critical`` means this blow was an attacker's critical hit;
    ``target_critical_failure`` means the target critically failed its own
    check. On a first lethal KO either gives dying 2. While already dying,
    either makes the increase 2. Damage while already unconscious at 0 HP but
    no longer dying has an unresolved rules outcome and raises
    ``UnsupportedHealthRuleError`` unless the damage causes massive death.
    """
    _check_damage_or_healing(amount, "damage")
    if damage_taken is None:
        damage_taken = amount
    else:
        _check_damage_or_healing(damage_taken, "damage_taken")
        if damage_taken < amount:
            raise ValueError("damage_taken cannot be less than damage")
    _check_hero_points(hero_points)
    if state.dead:
        return HealthTransition(state=state)

    if damage_taken >= 2 * state.max_hp:
        return HealthTransition(
            state=_dead_state(state),
            massive_damage_death=True,
        )

    if amount == 0:
        return HealthTransition(state=state)

    critical_dying_blow = attacker_critical or target_critical_failure

    if state.dying > 0:
        dying_value = state.dying + (2 if critical_dying_blow else 1)
        dead = dying_value >= 4
        normal = HealthTransition(
            state=_dead_state(state) if dead else replace(state, dying=dying_value),
            dying_increased=True,
        )
        if hero_points > 0:
            option = _heroic_recovery_result(state, hero_points)
            normal = replace(
                normal,
                heroic_recovery_available=True,
                heroic_recovery_option=option,
            )
        return normal

    # Getting Knocked Out addresses reduction to 0 HP, while the damage-while-
    # dying rule only addresses a creature already dying. The source does not
    # resolve further damage to an unconscious living PC at 0 HP and dying 0;
    # this case awaits a product ruling, so do not infer a no-op or fresh KO.
    if state.hp == 0:
        if state.unconscious:
            raise UnsupportedHealthRuleError(
                "positive damage to an unconscious living PC at 0 HP without "
                "dying awaits a product ruling"
            )
        return HealthTransition(state=state)

    new_hp = max(0, state.hp - amount)
    if new_hp > 0:
        return HealthTransition(state=replace(state, hp=new_hp))

    newly_unconscious = not state.unconscious
    ko_effects = {
        "knocked_out": True,
        "initiative_before_current_turn": True,
        "drop_held_items": newly_unconscious,
        "fall_prone": newly_unconscious,
    }
    if nonlethal:
        return HealthTransition(
            state=replace(state, hp=0, dying=0, unconscious=True),
            **ko_effects,
        )

    initial_dying = (2 if critical_dying_blow else 1) + state.wounded
    dead = initial_dying >= 4
    normal = HealthTransition(
        state=_dead_state(replace(state, hp=0, unconscious=True))
        if dead
        else replace(state, hp=0, dying=initial_dying, unconscious=True),
        dying_increased=True,
        **ko_effects,
    )
    if hero_points > 0:
        option = _heroic_recovery_result(
            state,
            hero_points,
            **ko_effects,
        )
        normal = replace(
            normal,
            heroic_recovery_available=True,
            heroic_recovery_option=option,
        )
    return normal


def healing(state: HealthState, amount: int) -> HealthTransition:
    """Apply healing; dead creatures cannot regain HP through ordinary healing."""
    _check_damage_or_healing(amount, "healing")
    if state.dead or amount == 0:
        return HealthTransition(state=state)

    new_hp = min(state.max_hp, state.hp + amount)
    dying_lost = state.dying > 0 and new_hp > 0
    wounded = state.wounded + 1 if dying_lost else state.wounded
    return HealthTransition(
        state=replace(
            state,
            hp=new_hp,
            dying=0 if dying_lost else state.dying,
            wounded=wounded,
            unconscious=False if new_hp > 0 else state.unconscious,
        ),
        dying_lost=dying_lost,
    )


def _lose_dying(state: HealthState) -> HealthTransition:
    """Remove dying at 0 HP, keeping unconsciousness and adding wounded once."""
    return HealthTransition(
        state=replace(
            state,
            hp=0,
            dying=0,
            wounded=state.wounded + 1,
            unconscious=True,
        ),
        dying_lost=True,
        stabilized=True,
    )


def stabilize(state: HealthState) -> HealthTransition:
    """Resolve an effect such as Stabilize on a dying creature."""
    if state.dead:
        return HealthTransition(state=state)
    if state.dying == 0:
        raise ValueError("stabilize requires a dying creature")
    return _lose_dying(state)


def recovery_check(
    state: HealthState,
    degree: RecoveryDegree,
    *,
    hero_points: int = 0,
) -> HealthTransition:
    """Apply the degree of an already-rolled recovery check.

    Check rolling, DC 10 + dying, and natural 1/20 degree adjustment belong to
    the shared check flow. At the turn-start timing represented here, the
    caller can offer Heroic Recovery before rolling; the optional branch is
    also returned so an unresolved increase can be handled before commitment.
    """
    _check_hero_points(hero_points)
    if degree not in ("critical_success", "success", "failure", "critical_failure"):
        raise ValueError(f"unsupported recovery degree: {degree!r}")
    if state.dead:
        return HealthTransition(state=state)
    if state.dying == 0:
        raise ValueError("recovery_check requires a dying creature")

    delta = {
        "critical_success": -2,
        "success": -1,
        "failure": 1,
        "critical_failure": 2,
    }[degree]
    proposed_dying = max(0, state.dying + delta)
    dying_increased = proposed_dying > state.dying
    if proposed_dying >= 4:
        normal = HealthTransition(
            state=_dead_state(state),
            dying_increased=True,
        )
    elif proposed_dying == 0:
        normal = _lose_dying(state)
    else:
        normal = HealthTransition(
            state=replace(state, dying=proposed_dying),
            dying_increased=dying_increased,
        )

    if hero_points > 0:
        normal = replace(
            normal,
            heroic_recovery_available=True,
            heroic_recovery_option=_heroic_recovery_result(state, hero_points),
        )
    return normal


def heroic_recovery(state: HealthState, hero_points: int) -> HealthTransition:
    """Spend every remaining Hero Point to stabilize a currently dying PC.

    Use ``can_use_heroic_recovery`` to check turn/event timing. A lethal-damage
    transition also carries the complete Heroic Recovery alternative directly.
    """
    _check_hero_points(hero_points)
    if state.dead:
        raise ValueError("Heroic Recovery cannot prevent massive or completed death")
    if hero_points < 1:
        raise ValueError("Heroic Recovery requires at least 1 Hero Point")
    if state.dying == 0:
        raise ValueError("Heroic Recovery requires a dying creature")
    return _heroic_recovery_result(state, hero_points)
