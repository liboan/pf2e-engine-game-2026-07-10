"""Small, explicit Fighter feat contracts for the level-2 martial slice.

The core owns movement transactions and Strike continuations.  This module
therefore describes the source-checked Fighter intent without creating a
second movement or attack resolver.
"""

from __future__ import annotations

from dataclasses import dataclass

from .model import (
    EffectExpiration,
    Event,
    FamilyCommand,
    FamilyProcedureContext,
    FamilyProcedureResult,
    Position,
)


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


@dataclass(frozen=True)
class IntimidatingStrike(FamilyCommand):
    """Make Intimidating Strike's two-action, melee-Strike activity.

    Player Core p. 141 / AoN feat 4782: on a hit that deals damage, frighten
    the target 1, or 2 on a critical hit.  Normal Strike resolution owns the
    attack, MAP, damage, reactions, and all saved choices.
    """

    family_id = "martial"
    target_id: str
    attack_id: str
    damage_type: str | None = None
    nonlethal: bool | None = None
    item_id: str | None = None


def intimidating_strike_is_legal(*, abilities: tuple[str, ...], actions_remaining: int) -> bool:
    """Check the feat's local grant and two-action cost.

    The core hook validates the selected melee attack, target, reach, damage
    intent, MAP, and all interruption/saved-continuation details.
    """

    return "intimidating_strike" in abilities and actions_remaining >= 2


def intimidating_strike_target_is_immune(
    context: FamilyProcedureContext, target_id: str,
) -> bool:
    """Check the feat's emotion/fear/mental immunity boundary.

    Dynamic encounter immunities cover active effects.  The finite published
    opponent records retain printed mindless/mental immunity separately from
    the general creature definition, so consult that small source-backed
    packet when the target is one of those admitted profiles.
    """

    target = context.state.creatures.get(target_id)
    if target is None:
        raise ValueError("Intimidating Strike's target is no longer present")
    if any(
        context.condition_immunity_active(kind, target.actor_id, target.actor_id)
        for kind in ("frightened", "fear", "emotion", "mental")
    ):
        return True
    from .opponent_content import PUBLISHED_OPPONENT_PROFILES

    profile = PUBLISHED_OPPONENT_PROFILES.get(target.definition_id)
    return profile is not None and bool(
        {"frightened", "fear", "emotion", "mental"} & set(profile.condition_immunities)
    )


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
    if isinstance(command, SuddenCharge):
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
    if isinstance(command, IntimidatingStrike):
        if not intimidating_strike_is_legal(
            abilities=context.definition.abilities,
            actions_remaining=context.actor.actions_remaining,
        ):
            return FamilyProcedureResult(
                rejection="Intimidating Strike requires its admitted feat and two actions."
            )
        context.require_action_permitted(
            "intimidating_strike", frozenset({"attack", "emotion", "fear", "mental"})
        )
        hook = getattr(context.encounter, "_start_intimidating_strike", None)
        if not callable(hook):
            return FamilyProcedureResult(
                unsupported="The core Intimidating Strike hook is not available."
            )
        result = hook(context, command)
        if not isinstance(result, FamilyProcedureResult):
            return FamilyProcedureResult(
                unsupported="The core Intimidating Strike hook returned an invalid result."
            )
        return result
    return None


def apply_intimidating_strike_frightened(
    context: FamilyProcedureContext,
    *,
    target_id: str,
    damage: int,
    critical: bool,
) -> Event:
    """Apply this feat's fear effect after the shared Strike has dealt damage."""

    target = context.state.creatures.get(target_id)
    if target is None:
        raise ValueError("Intimidating Strike's target is no longer present")
    if damage < 1:
        return Event(
            "intimidating_strike_no_fear", context.actor.actor_id, target.actor_id,
            f"{context.actor.label}'s Intimidating Strike dealt no damage, so it does not frighten {target.label}.",
        )
    if intimidating_strike_target_is_immune(context, target_id):
        return Event(
            "intimidating_strike_immune", context.actor.actor_id, target.actor_id,
            f"{target.label} is immune to Intimidating Strike's fear effect.",
        )
    frightened = 2 if critical else 1
    current_end = context.state.actor_end_counts.get(target.actor_id, 0)
    from .skill_actions import add_timed_condition_effect

    add_timed_condition_effect(
        context,
        effect_id=(
            f"intimidating_strike:{context.actor.actor_id}:{target.actor_id}:"
            f"{context.state.round_number}:{current_end}"
        ),
        kind="frightened",
        source_id=context.actor.actor_id,
        target_id=target.actor_id,
        value=frightened,
        expiration=EffectExpiration(target.actor_id, "end", current_end + frightened),
    )
    return Event(
        "condition_applied", context.actor.actor_id, target.actor_id,
        f"{target.label} is frightened {frightened} by Intimidating Strike.",
    )


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
