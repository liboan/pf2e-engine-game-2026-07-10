"""Narrow Battle Magic Wizard family commands."""

from dataclasses import dataclass

from .model import Event, FamilyCommand, FamilyProcedureContext, FamilyProcedureResult
from .spells import SPELLS


@dataclass(frozen=True)
class DrainBondedItem(FamilyCommand):
    """Use Arcane Bond's once-daily free action with one owned item."""

    family_id = "casting"
    item_id: str


def preparation_choices(actor, definition, slot) -> tuple[str, ...]:
    """Return this Wizard slot's source-ordered accessible book entries."""
    if not definition.spell_substitution_book_id:
        return ()
    return tuple(
        entry.spell_id
        for entry in definition.spell_substitution_book
        if entry.rank == slot.rank
        and SPELLS[entry.spell_id].cantrip == slot.cantrip
        and slot.source in (entry.permitted_sources or (entry.source,))
    )


def prepared_slot_rejection(actor, definition, slot, spell_id: str) -> str | None:
    """Validate one Wizard slot against its accessible finite spellbook.

    The book records spell identity once and keeps each permitted preparation
    source alongside it.  Daily preparation, substitution, live casting, and
    save validation all call this same helper so a slot cannot become legal in
    one path but unusable in another.
    """
    book_id = definition.spell_substitution_book_id
    if not book_id:
        return None
    expected_book_id = f"{actor.actor_id}:{book_id}"
    if expected_book_id not in {*actor.held_items, *actor.worn_items, *actor.stowed_items}:
        return "Wizard prepared casting requires the accessible owned spellbook."
    if not isinstance(spell_id, str) or not spell_id:
        return "Prepared spell selection requires a spell id."
    for entry in definition.spell_substitution_book:
        sources = entry.permitted_sources or (entry.source,)
        if (
            entry.spell_id == spell_id
            and entry.rank == slot.rank
            and SPELLS[entry.spell_id].cantrip == slot.cantrip
            and slot.source in sources
        ):
            return None
    return "The spell is not in the Wizard's finite book for this preparation slot."


def substitution_rejection(actor, definition, *, slot_id: str, replacement_spell_id: str) -> str | None:
    """Validate the finite owned-book replacement without mutating a slot."""
    if "spell_substitution" not in definition.abilities or not definition.spell_substitution_book_id:
        return "This actor has no admitted Spell Substitution thesis."
    if not isinstance(slot_id, str) or not slot_id or not isinstance(replacement_spell_id, str) or not replacement_spell_id:
        return "Spell Substitution requires a prepared slot and replacement spell id."
    slot = next((entry for entry in actor.prepared_slots if entry.slot_id == slot_id), None)
    if slot is None or slot.cantrip or slot.rank != 1:
        return "Spell Substitution supports only an existing rank-1 prepared spell slot."
    if slot.spent:
        return "Spell Substitution cannot change an expended prepared spell."
    if replacement_spell_id == slot.spell_id:
        return "Spell Substitution requires a different replacement spell."
    return prepared_slot_rejection(actor, definition, slot, replacement_spell_id)


def handle_action(context: FamilyProcedureContext) -> FamilyProcedureResult:
    command = context.command
    if not isinstance(command, DrainBondedItem):
        return FamilyProcedureResult(unsupported="That casting family action is not admitted.")
    actor = context.actor
    if "arcane_bond" not in context.definition.abilities:
        return FamilyProcedureResult(rejection="This actor has no Arcane Bond.")
    if command.item_id != f"{actor.actor_id}:bonded_staff":
        return FamilyProcedureResult(rejection="Arcane Bond requires this Wizard's selected bonded_staff.")
    if command.item_id not in {*actor.held_items, *actor.worn_items, *actor.stowed_items}:
        return FamilyProcedureResult(rejection="Arcane Bond requires the bonded item to be on the caster's person.")
    if actor.arcane_bond_used_day == context.state.preparation_day:
        return FamilyProcedureResult(rejection="Arcane Bond has already been used today.")
    if not actor.arcane_bond_eligible_slots:
        return FamilyProcedureResult(rejection="Arcane Bond requires a completed prepared spell cast today.")
    actor.arcane_bond_used_day = context.state.preparation_day
    actor.arcane_bond_item_id = command.item_id
    actor.arcane_bond_recast_until_start = context.state.actor_start_counts.get(actor.actor_id, 0)
    return FamilyProcedureResult((Event(
        "arcane_bond_drained", actor.actor_id, None,
        f"{actor.label} drains {command.item_id}; one eligible completed prepared spell may be recast this turn without expending its slot.",
    ),))
