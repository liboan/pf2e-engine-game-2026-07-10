"""Terminal-facing literals for the one-action Widen Spell activity."""

from __future__ import annotations

from .model import WidenSpell


ACTION_ID = "widen_spell"
ACTION_LABEL = "Widen Spell"


def command() -> WidenSpell:
    """Return the public fieldless command advertised by the terminal."""
    return WidenSpell()
