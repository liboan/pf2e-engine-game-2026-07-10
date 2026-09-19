"""Pure rule facts for the admitted Reach Spell spellshape.

Rules sources:

* Reach Spell, Player Core p. 101 and Player Core 2 p. 138:
  https://2e.aonprd.com/Feats.aspx?ID=4577
* Spellshape timing, Player Core p. 298:
  https://2e.aonprd.com/Rules.aspx?ID=2232

The procedure that owns actions and persistent state lives in
``family_casting``.  This module deliberately receives spell facts and returns
only a range: it never edits the global spell catalogue or a creature.
"""

from __future__ import annotations

from .spells import SpellDefinition


# These are the only target modes whose fixed spell entry represents touch as
# ``None`` rather than a numeric range.  Heal is mode-sensitive: its one- and
# two-action forms are target spells, while the three-action form is an
# emanation.  The encounter integration supplies a mode-normalized spell to
# ``effective_spell_range`` (touch=0, two-action Heal=30).
_TOUCH_RANGE_SPELL_IDS = frozenset({"heal", "runic_weapon"})


def can_shape_spell(spell: SpellDefinition, *, spell_actions: int) -> bool:
    """Whether the selected mode has a range that Reach Spell can extend.

    The check is deliberately mode-aware for Heal.  It excludes a three-action
    Heal emanation and all other no-range effects, while preserving target
    spells with a finite printed range and the reviewed touch modes.
    """
    if not isinstance(spell, SpellDefinition):
        return False
    if type(spell_actions) is not int or spell_actions not in spell.action_costs:
        return False
    if spell.spell_id == "heal":
        return spell_actions in {1, 2}
    if spell.spell_id in _TOUCH_RANGE_SPELL_IDS:
        return True
    return type(spell.range_ft) is int and spell.range_ft >= 0


def effective_spell_range(spell: SpellDefinition, *, reach_ready: bool) -> int | None:
    """Return a mode-normalized finite range, with Reach Spell when ready.

    Callers must pass a view of the spell's chosen targeting mode.  In
    particular, use range ``0`` for touch and use ``30`` for two-action Heal;
    a mode that cannot be shaped must not call this helper with ``reach_ready``
    true.  ``None`` remains a no-range/area effect, so emanations are never
    accidentally converted into ranged spells.
    """
    if not isinstance(spell, SpellDefinition):
        raise TypeError("Reach Spell requires a SpellDefinition")
    if type(reach_ready) is not bool:
        raise TypeError("reach_ready must be a boolean")
    range_ft = spell.range_ft
    if range_ft is None:
        return None
    if type(range_ft) is not int or range_ft < 0:
        raise ValueError("spell range must be a non-negative integer or None")
    return range_ft + 30 if reach_ready else range_ft
