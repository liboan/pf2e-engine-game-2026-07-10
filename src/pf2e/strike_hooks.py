"""Small, non-owning notifications emitted by the common Strike pipeline."""

from __future__ import annotations

from .checks import DegreeOfSuccess


def final_check_outcome(state, *, attacker, target, attack, check):
    """Notify feature consumers after the final attack check is chosen.

    This deliberately does not reroll, recommit, or alter the Strike result.
    It is called only after targeting flat checks and Hero Point/result choices.
    """
    from .model import Event

    events = []
    if check.degree < DegreeOfSuccess.SUCCESS:
        from .martial_defense import apply_extravagant_parry_miss

        label = apply_extravagant_parry_miss(
            state, attacker=attacker, target=target, attack=attack, check=check
        )
        if label is not None:
            events.append(Event(
                "extravagant_parry_panache",
                target.actor_id,
                attacker.actor_id,
                f"{target.label}'s Extravagant Parry turns the resolved miss into temporary Panache.",
                check=check,
            ))
    return events


def committed_first_weapon_attempt(state, *, actor, attack):
    """Reserved adopter hook for Gravity Weapon's first weapon attempt."""
    return None


def post_mitigation_damaging_critical(state, *, attacker, target, attack, damage, check):
    """Notify the narrow critical-rider adopters after final mitigation."""
    from .monk_stances import post_mitigation_tiger_bleed

    return post_mitigation_tiger_bleed(
        state, attacker=attacker, target=target, attack=attack,
        damage=damage, check=check,
    )
