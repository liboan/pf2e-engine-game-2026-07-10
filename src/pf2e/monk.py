"""Monk level-1 class procedures and the selected Monastic Weaponry feat."""

from __future__ import annotations

from dataclasses import dataclass

from .model import (
    FamilyCommand,
    FamilyProcedureContext,
    FamilyProcedureResult,
    PairedStrikeSelection,
)


@dataclass(frozen=True)
class FlurryOfBlows(FamilyCommand):
    """Begin Flurry of Blows with its first selected Strike."""

    family_id = "martial"
    strike: PairedStrikeSelection


def is_flurry_strike(abilities: tuple[str, ...], attack) -> bool:
    """Whether this attack is a legal member of this Monk's Flurry."""
    if "unarmed" in attack.traits:
        return True
    return (
        "monastic_weaponry" in abilities
        and "melee" in attack.traits
        and "monk" in attack.traits
        and "weapon" in attack.traits
        and attack.item_id is not None
    )


def powerful_fist_removes_lethal_penalty(
    abilities: tuple[str, ...], attack, *, nonlethal: bool | None,
) -> bool:
    """Powerful Fist exempts fists from the ordinary lethal-use penalty."""
    chosen_nonlethal = "nonlethal" in attack.traits if nonlethal is None else nonlethal
    return (
        "powerful_fist" in abilities
        and "unarmed" in attack.traits
        and not chosen_nonlethal
    )


def handle_action(context: FamilyProcedureContext) -> FamilyProcedureResult | None:
    command = context.command
    if not isinstance(command, FlurryOfBlows):
        return None
    if "flurry_of_blows" not in context.definition.abilities:
        return FamilyProcedureResult(unsupported="Flurry of Blows is not admitted for this creature.")
    from .paired_strikes import start_paired_strikes

    return start_paired_strikes(
        context,
        activity_id="monk:flurry_of_blows",
        first_selection=command.strike,
        action_cost=1,
        is_flourish=True,
        same_target=False,
        ranged_only=False,
        require_hunted_prey=False,
        requires_unarmed_or_monk_weapon=True,
    )


def handle_choice(context: FamilyProcedureContext) -> FamilyProcedureResult | None:
    if context.pending is None or context.pending.procedure_id != "monk:flurry_of_blows":
        return None
    from .paired_strikes import resume_paired_strikes

    return resume_paired_strikes(context)


def validate_pending(context: FamilyProcedureContext) -> None:
    pending = context.pending
    if pending is None or pending.procedure_id != "monk:flurry_of_blows":
        raise ValueError("save has a pending choice outside the Monk Flurry procedure")
    from .paired_strikes import validate_pending as validate_paired_strikes

    validate_paired_strikes(context, activity_id="monk:flurry_of_blows")
