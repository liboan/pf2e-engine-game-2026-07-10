"""Finite shared Composition-trait lifecycle used by Anthem and Hymn."""

COMPOSITION_KINDS = frozenset({"courageous_anthem", "hymn_of_healing"})


def clear_prior_compositions(state, *, source_actor_id: str) -> None:
    retained = []
    for effect in state.active_effects:
        if effect.source_actor_id != source_actor_id or effect.kind not in COMPOSITION_KINDS:
            retained.append(effect)
            continue
        _clear_hymn_temporary_hp(state, effect)
    state.active_effects[:] = retained


def _clear_hymn_temporary_hp(state, effect) -> None:
    if effect.kind != "hymn_of_healing":
        return
    target = state.creatures.get(effect.target_actor_id)
    if target is not None and target.temporary_hp_source_id == effect.effect_id:
        target.temporary_hp = 0
        target.temporary_hp_source_id = None
        target.temporary_hp_expires_at_seconds = None
        target.temporary_hp_expires_at_source_start = 0


def composition_cast_allowed(actor, state, *, active_actor_id: str | None, active_start: int) -> bool:
    source_start = state.actor_start_counts.get(actor.actor_id, 0)
    return bool(
        actor.composition_cast_at_start != source_start
        and active_actor_id is not None
        and (actor.composition_cast_turn_actor_id, actor.composition_cast_turn_start)
        != (active_actor_id, active_start)
    )
