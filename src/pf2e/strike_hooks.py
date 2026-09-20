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
    """Commit Gravity Weapon to the first held-weapon attempt this round."""
    if attack.item_id is None:
        return None
    if actor.gravity_weapon_used_round == state.round_number:
        actor.gravity_weapon_bonus_attack_id = None
        return None
    actor.gravity_weapon_bonus_attack_id = None
    actor.gravity_weapon_used_round = state.round_number
    if not any(
        effect.kind == "gravity_weapon"
        and effect.source_actor_id == actor.actor_id
        and effect.target_actor_id == actor.actor_id
        and (effect.expires_at_world_time is None or effect.expires_at_world_time > state.world_time_seconds)
        for effect in state.active_effects
    ):
        return None
    actor.gravity_weapon_bonus_attack_id = attack.attack_id
    return None


def post_mitigation_damaging_critical(
    state, *, attacker, target, attack, damage, check, continuation=None,
    damage_resolution=None,
):
    """Notify the narrow critical-rider adopters after final mitigation."""
    from .monk_stances import post_mitigation_tiger_bleed

    return post_mitigation_tiger_bleed(
        state, attacker=attacker, target=target, attack=attack,
        damage=damage, check=check, continuation=continuation,
        damage_resolution=damage_resolution,
    )
