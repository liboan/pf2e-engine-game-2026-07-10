"""Finite shared Composition-trait lifecycle used by Anthem and Hymn."""

COMPOSITION_KINDS = frozenset({"courageous_anthem", "hymn_of_healing"})


def clear_prior_compositions(state, *, source_actor_id: str) -> None:
    state.active_effects[:] = [
        effect for effect in state.active_effects
        if not (
            effect.source_actor_id == source_actor_id
            and effect.kind in COMPOSITION_KINDS
        )
    ]


def composition_cast_allowed(actor, state, *, active_actor_id: str | None, active_start: int) -> bool:
    source_start = state.actor_start_counts.get(actor.actor_id, 0)
    return bool(
        actor.composition_cast_at_start != source_start
        and active_actor_id is not None
        and (actor.composition_cast_turn_actor_id, actor.composition_cast_turn_start)
        != (active_actor_id, active_start)
    )

