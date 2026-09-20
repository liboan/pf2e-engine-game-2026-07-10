"""Small, explicit Fighter feat contracts for the level-2 martial slice.

The core owns movement transactions and Strike continuations.  This module
therefore describes the source-checked Fighter intent without creating a
second movement or attack resolver.
"""

from __future__ import annotations

from dataclasses import dataclass

from .model import FamilyCommand, FamilyProcedureContext, FamilyProcedureResult, Position


@dataclass(frozen=True)
class SuddenCharge(FamilyCommand):
    """Two Strides followed by an optional melee Strike.

    Player Core, p. 141 / AoN feat 4774: this is a two-action flourish.  The
    two paths are kept separate so the shared encounter hook can validate the
    first Stride before it begins the second, preserving reaction timing.
    """

    family_id = "martial"
    first_path: tuple[Position, ...]
    second_path: tuple[Position, ...]
    target_id: str | None = None
    attack_id: str | None = None
    item_id: str | None = None


def sudden_charge_is_legal(
    *,
    abilities: tuple[str, ...],
    actions_remaining: int,
    first_path: tuple[Position, ...],
    second_path: tuple[Position, ...],
    target_id: str | None,
    attack_id: str | None,
) -> bool:
    """Check only class-local facts; core validates movement and the Strike.

    A Strike is optional, but its target and attack must be supplied together.
    Empty paths are deliberately rejected here: the printed activity requires
    the character to make two Strides, even if one is only the minimum legal
    movement allowed by the shared grid contract.
    """

    return (
        "sudden_charge" in abilities
        and actions_remaining >= 2
        and bool(first_path)
        and bool(second_path)
        and ((target_id is None and attack_id is None) or (target_id is not None and attack_id is not None))
    )


def handle_action(context: FamilyProcedureContext) -> FamilyProcedureResult | None:
    """Delegate the ordered common movement/Strike work to its one core hook."""

    command = context.command
    if not isinstance(command, SuddenCharge):
        return None
    if not sudden_charge_is_legal(
        abilities=context.definition.abilities,
        actions_remaining=context.actor.actions_remaining,
        first_path=command.first_path,
        second_path=command.second_path,
        target_id=command.target_id,
        attack_id=command.attack_id,
    ):
        return FamilyProcedureResult(
            rejection=(
                "Sudden Charge requires its admitted feat, two actions, two Strides, and either "
                "no Strike or both a target and melee attack."
            )
        )
    hook = getattr(context.encounter, "_start_sudden_charge", None)
    if not callable(hook):
        return FamilyProcedureResult(
            unsupported="The core Sudden Charge subordinate-movement hook is not available."
        )
    result = hook(context, command)
    if not isinstance(result, FamilyProcedureResult):
        return FamilyProcedureResult(
            unsupported="The core Sudden Charge subordinate-movement hook returned an invalid result."
        )
    return result


def handle_choice(context: FamilyProcedureContext) -> FamilyProcedureResult | None:
    """Sudden Charge continuations belong to the shared movement transaction."""

    if context.pending is None or context.pending.procedure_id != "fighter:sudden_charge":
        return None
    hook = getattr(context.encounter, "_resume_sudden_charge", None)
    if not callable(hook):
        return FamilyProcedureResult(
            unsupported="The core Sudden Charge continuation hook is not available."
        )
    result = hook(context)
    if not isinstance(result, FamilyProcedureResult):
        return FamilyProcedureResult(
            unsupported="The core Sudden Charge continuation hook returned an invalid result."
        )
    return result


def validate_pending(context: FamilyProcedureContext) -> None:
    """Make missing core validation fail closed instead of accepting a save."""

    if context.pending is None or context.pending.procedure_id != "fighter:sudden_charge":
        raise ValueError("save has a pending choice outside Fighter Sudden Charge")
    hook = getattr(context.encounter, "_validate_sudden_charge_pending", None)
    if not callable(hook):
        raise ValueError("save has a Sudden Charge continuation without its core validator")
    hook(context)
