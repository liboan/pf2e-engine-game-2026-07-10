"""Finite ranged profiles shared by actual range validation and menus."""

from __future__ import annotations


def effective_ranged_profile(state, actor, attack, *, bomber_facts=None):
    """Return the committed (increment, maximum) profile for one attack.

    Only two reviewed transformations live here: Bomber's bomb profile and
    Strong Arm's thrown-weapon increment.  Callers use this same result for
    option generation, penalties, and saved-Strike validation.
    """
    increment = attack.range_increment_ft
    maximum = attack.max_range_ft
    if increment is None or maximum is None:
        return increment, maximum

    if bomber_facts is not None:
        from .alchemy import bomber_bomb_range_increment

        alchemy_state = state.alchemy_states.get(actor.actor_id)
        if alchemy_state is not None:
            increment = bomber_bomb_range_increment(alchemy_state, increment)
            maximum = increment * 6

    from .content import get_definition

    definition = get_definition(actor.definition_id)
    if (
        "Strong Arm" in definition.feats
        and {"ranged", "thrown"} <= attack.traits
    ):
        increment += 10
        maximum = increment * 6
    return increment, maximum
