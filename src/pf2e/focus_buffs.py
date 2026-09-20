"""Small typed status-bonus helpers for the W5 focus spells."""

from __future__ import annotations

from .checks import Modifier


def gravity_weapon_modifier(state, actor, attack, weapon_dice: tuple[int, ...], *, applies: bool) -> Modifier | None:
    """Return Gravity Weapon's first-Strike status bonus, if committed.

    ``applies`` is copied onto the immutable Strike continuation by the common
    Strike pipeline.  This keeps a miss, a concealment failure, or a saved
    reaction from accidentally handing the bonus to a later Strike.
    """
    if not applies or not weapon_dice:
        return None
    if not any(
        effect.kind == "gravity_weapon"
        and effect.source_actor_id == actor.actor_id
        and effect.target_actor_id == actor.actor_id
        and effect.expires_at_world_time is not None
        and effect.expires_at_world_time > state.world_time_seconds
        for effect in state.active_effects
    ):
        return None
    return Modifier(2 * len(weapon_dice), "status", "Gravity Weapon")

