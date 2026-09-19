"""Terminal-facing literals for the one-action Reach Spell activity.

Presentation code imports these small values instead of duplicating an action
identifier or constructing a look-alike command record.  Validation and all
range behavior remain in the casting family and encounter layers.
"""

from __future__ import annotations

from .model import ReachSpell


ACTION_ID = "reach_spell"
ACTION_LABEL = "Reach Spell"


def command() -> ReachSpell:
    """Return the one fieldless public command advertised by the terminal."""
    return ReachSpell()
