"""Small routing boundary for admitted finite prepared-spell policies."""

from __future__ import annotations


def has_variable_preparations(definition) -> bool:
    """Whether this definition selects its prepared spells during daily prep."""
    return bool(
        definition.spell_substitution_book_id
        or "storm_druid_preparation" in definition.abilities
        or "faiths_flamekeeper" in definition.abilities
    )


def preparation_choices(actor, definition, slot) -> tuple[str, ...]:
    """Return one slot's ordered finite menu, including a fixed-slot fallback."""
    if definition.spell_substitution_book_id:
        from . import wizard

        return wizard.preparation_choices(actor, definition, slot)
    if "storm_druid_preparation" in definition.abilities:
        from . import druid

        return druid.preparation_choices(definition, slot)
    if "faiths_flamekeeper" in definition.abilities:
        from . import witch

        return witch.preparation_choices(definition, slot)
    return (slot.spell_id,)


def prepared_slot_rejection(actor, definition, slot, spell_id: str) -> str | None:
    """Apply the authored class policy for one live prepared slot.

    The initial save parser has no reconstructed actor inventory. Wizard
    ownership is therefore checked only once that actor exists, while the
    Druid, Witch, and fixed-slot policies remain safe in either stage.
    """
    if not isinstance(spell_id, str) or not spell_id:
        return "Prepared spell selection requires a spell id."
    if definition.spell_substitution_book_id:
        if actor is None:
            return None
        from . import wizard

        return wizard.prepared_slot_rejection(actor, definition, slot, spell_id)
    if "storm_druid_preparation" in definition.abilities:
        from . import druid

        return druid.prepared_slot_rejection(actor, definition, slot, spell_id)
    if "faiths_flamekeeper" in definition.abilities:
        from . import witch

        return witch.prepared_slot_rejection(actor, definition, slot, spell_id)
    if spell_id != slot.spell_id:
        return "This fixed prepared slot cannot be replaced during daily preparation."
    return None
