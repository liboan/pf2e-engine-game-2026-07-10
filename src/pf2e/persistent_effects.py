"""Finite persistent-damage installation and provenance checks."""

from __future__ import annotations

from .model import PersistentDamageEffect


def install_persistent_effect(
    state,
    *,
    source_actor_id: str,
    target_actor_id: str,
    source_id: str,
    damage_type: str,
    dice: tuple[int, ...] = (),
    flat: int = 0,
) -> tuple[PersistentDamageEffect | None, PersistentDamageEffect | None]:
    """Install a source with the printed same-type comparison.

    Returns ``(installed, existing)``.  Comparable same-shape effects replace
    only when stronger; incomparable shapes are returned to the caller so a
    bounded GM choice can be persisted instead of silently averaging/rejecting.
    """
    if damage_type == "bleed" and state.creatures[target_actor_id].definition_id in {
        "skeleton_guard_mc3193", "zombie_shambler_mc3249",
    }:
        return None, None
    previous = next(
        (effect for effect in state.persistent_effects
         if effect.target_actor_id == target_actor_id and effect.damage_type == damage_type),
        None,
    )
    candidate = PersistentDamageEffect(
        f"persistent:{source_id}:{source_actor_id}:{target_actor_id}:{state.next_choice_id}",
        source_actor_id, target_actor_id, source_id, damage_type,
        tuple(dice), flat, state.world_time_seconds + 60,
    )
    if previous is None:
        state.persistent_effects.append(candidate)
        return candidate, None
    if bool(previous.dice) != bool(candidate.dice) or previous.dice != candidate.dice:
        return None, previous
    if candidate.flat <= previous.flat:
        return None, previous
    state.persistent_effects.remove(previous)
    state.persistent_effects.append(candidate)
    return candidate, previous
