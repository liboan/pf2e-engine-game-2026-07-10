"""Pure rule facts for the admitted Widen Spell spellshape.

Rules source: Widen Spell, Player Core p. 128 and Player Core 2 p. 138:
https://2e.aonprd.com/Feats.aspx?ID=4715

The admitted catalogue currently has one qualifying no-duration area spell:
Breathe Fire's 15-foot cone.  This finite helper keeps its 20-foot widened
length separate from creature state and from the global spell catalogue.
"""

from __future__ import annotations

from .spells import SpellDefinition


def widened_cone_length(spell: SpellDefinition, *, spell_actions: int) -> int | None:
    """Return the widened length for an admitted eligible cone, else ``None``.

    Widen Spell adds 5 feet to a cone or line of 15 feet or less.  Breathe
    Fire is the sole supported cone at present, so other area shapes remain
    deliberately outside this bounded implementation rather than being
    approximated from incomplete spell metadata.
    """
    if not isinstance(spell, SpellDefinition):
        raise TypeError("Widen Spell requires a SpellDefinition")
    if type(spell_actions) is not int or spell_actions not in spell.action_costs:
        return None
    if spell.spell_id == "breathe_fire" and spell_actions == 2:
        return 20
    return None
