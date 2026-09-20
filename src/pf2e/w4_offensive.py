"""W4 offensive level-1 class-feat procedures.

This lane deliberately composes the existing Strike and paired-Strike
transactions.  It does not create a second attack or damage resolver.

Sources checked 2026-09-20:
* https://2e.aonprd.com/Feats.aspx?ID=357 (Exacting Strike)
* https://2e.aonprd.com/Feats.aspx?ID=494 (Twin Takedown)
* https://2e.aonprd.com/Feats.aspx?ID=356 (Double Slice)
* https://2e.aonprd.com/Feats.aspx?ID=552 (Twin Feint)
"""

from __future__ import annotations

from dataclasses import dataclass

from .model import FamilyCommand, FamilyProcedureContext, FamilyProcedureResult, PairedStrikeSelection


@dataclass(frozen=True)
class ExactingStrike(FamilyCommand):
    """One-action Fighter Strike that does not add MAP on an ordinary miss."""

    family_id = "martial"
    target_id: str
    attack_id: str
    damage_type: str | None = None
    nonlethal: bool | None = None
    item_id: str | None = None


@dataclass(frozen=True)
class TwinTakedown(FamilyCommand):
    """One-action Ranger pair of different melee Strikes against hunted prey."""

    family_id = "martial"
    strike: PairedStrikeSelection


@dataclass(frozen=True)
class DoubleSlice(FamilyCommand):
    """Two-action Fighter pair of one-handed melee Strikes."""

    family_id = "martial"
    strike: PairedStrikeSelection


@dataclass(frozen=True)
class TwinFeint(FamilyCommand):
    """Two-action Rogue pair of different agile/finesse melee Strikes."""

    family_id = "martial"
    strike: PairedStrikeSelection


def _has(context: FamilyProcedureContext, ability_id: str, actions: int = 1) -> bool:
    return ability_id in context.definition.abilities and context.actor.actions_remaining >= actions


def handle_action(context: FamilyProcedureContext) -> FamilyProcedureResult | None:
    command = context.command
    if isinstance(command, ExactingStrike):
        if not _has(context, "exacting_strike"):
            return FamilyProcedureResult(rejection="Exacting Strike is not admitted or needs one action.")
        if context.actor.strikes_this_turn < 1:
            return FamilyProcedureResult(rejection="Exacting Strike requires an earlier attack this turn.")
        context.require_action_permitted("exacting_strike", frozenset({"attack"}))
        hook = getattr(context.encounter, "_start_w4_exacting_strike", None)
        if not callable(hook):
            return FamilyProcedureResult(unsupported="The Exacting Strike core hook is unavailable.")
        return hook(context, command)
    if isinstance(command, TwinTakedown):
        if not _has(context, "twin_takedown"):
            return FamilyProcedureResult(rejection="Twin Takedown is not admitted or needs one action.")
        from .paired_strikes import start_paired_strikes

        return start_paired_strikes(
            context, activity_id="ranger:twin_takedown", first_selection=command.strike,
            action_cost=1, is_flourish=True, same_target=True, ranged_only=False,
            require_hunted_prey=True, requires_unarmed_or_monk_weapon=False,
        )
    if isinstance(command, DoubleSlice):
        if not _has(context, "double_slice", 2):
            return FamilyProcedureResult(rejection="Double Slice requires its feat and two actions.")
        from .paired_strikes import start_paired_strikes

        return start_paired_strikes(
            context, activity_id="fighter:double_slice", first_selection=command.strike,
            action_cost=2, is_flourish=False, same_target=True, ranged_only=False,
            require_hunted_prey=False, requires_unarmed_or_monk_weapon=False,
        )
    if isinstance(command, TwinFeint):
        if not _has(context, "twin_feint", 2):
            return FamilyProcedureResult(rejection="Twin Feint requires its feat and two actions.")
        from .paired_strikes import start_paired_strikes

        return start_paired_strikes(
            context, activity_id="rogue:twin_feint", first_selection=command.strike,
            action_cost=2, is_flourish=False, same_target=True, ranged_only=False,
            require_hunted_prey=False, requires_unarmed_or_monk_weapon=False,
        )
    return None


def handle_choice(context: FamilyProcedureContext) -> FamilyProcedureResult | None:
    pending = context.pending
    if pending is None or pending.procedure_id not in {
        "ranger:twin_takedown", "fighter:double_slice", "rogue:twin_feint"
    }:
        return None
    from .paired_strikes import resume_paired_strikes

    return resume_paired_strikes(context)


def validate_pending(context: FamilyProcedureContext) -> None:
    pending = context.pending
    if pending is None or pending.procedure_id not in {
        "ranger:twin_takedown", "fighter:double_slice", "rogue:twin_feint"
    }:
        raise ValueError("save has a pending choice outside the W4 offensive paired procedures")
    from .paired_strikes import validate_pending

    validate_pending(context, activity_id=pending.procedure_id)
