"""Shared lifecycle facts for the admitted one-cast spellshape actions.

Reach Spell and Widen Spell have the same immediate-successor rule.  The
caster-specific effect remains in its own rule module; this small boundary
only prevents their transient markers from drifting apart.
"""

from __future__ import annotations


def has_pending_spellshape(actor) -> bool:
    """Whether an admitted spellshape is waiting for its direct Cast action."""
    return (
        actor.reach_spell_pending
        or actor.widen_spell_pending
        or actor.energy_ablation_pending is not None
    )


def clear_pending_spellshape(actor) -> None:
    """Discard every transient cast-shaping marker on an intervening action."""
    actor.reach_spell_pending = False
    actor.widen_spell_pending = False
    actor.energy_ablation_pending = None
