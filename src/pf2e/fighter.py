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


@dataclass(frozen=True)
class SnaggingStrike(FamilyCommand):
    """Make Snagging Strike's one-action free-hand melee Strike.

    Player Core p. 141 / AoN feat 4773.  A hit leaves the target off-guard
    only while it remains in reach of the Fighter's free hand, through the
    start of the Fighter's next turn.
    """

    family_id = "martial"
    target_id: str
    attack_id: str
    damage_type: str | None = None
    nonlethal: bool | None = None
    item_id: str | None = None


@dataclass(frozen=True)
class CombatGrab(FamilyCommand):
    """Make Combat Grab's one-action press Strike and Grab rider.

    Player Core p. 141 / AoN feat 4780.  The shared Strike still owns MAP and
    defenses; a hit supplies the printed free-hand Grab until the end of the
    Fighter's next turn or Escape.
    """

    family_id = "martial"
    target_id: str
    attack_id: str
    damage_type: str | None = None
    nonlethal: bool | None = None
    item_id: str | None = None


@dataclass(frozen=True)
class BrutishShove(FamilyCommand):
    """Make Brutish Shove's one-action press Strike.

    Player Core p. 141 / AoN feat 4779.  ``shove_destination`` is the
    player's supported horizontal Shove direction when an automatic Shove is
    selected; it can be omitted when declining that optional rider.
    ``failure_effect`` records the printed Press choice after a success.
    """

    family_id = "martial"
    target_id: str
    attack_id: str
    shove_destination: Position | None = None
    follow: bool = False
    failure_effect: bool = False
    damage_type: str | None = None
    nonlethal: bool | None = None
    item_id: str | None = None


def intimidating_strike_is_legal(*, abilities: tuple[str, ...], actions_remaining: int) -> bool:
    """Check the feat's local grant and two-action cost.

    The core hook validates the selected melee attack, target, reach, damage
    intent, MAP, and all interruption/saved-continuation details.
    """

    return "intimidating_strike" in abilities and actions_remaining >= 2


def _free_hand_strike_is_legal(context: FamilyProcedureContext, ability_id: str, *, press: bool) -> bool:
    """Check the shared local grant, hand, and Press prerequisites."""
    free_hands = context.encounter._free_hands(context.state, context.definition, context.actor)
    return (
        ability_id in context.definition.abilities
        and context.actor.actions_remaining >= 1
        and free_hands >= 1
        and (not press or context.actor.strikes_this_turn >= 1)
    )


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
    if isinstance(command, SnaggingStrike):
        if not _free_hand_strike_is_legal(context, "snagging_strike", press=False):
            return FamilyProcedureResult(rejection="Snagging Strike requires its feat, one action, and a free hand.")
        context.require_action_permitted("snagging_strike", frozenset({"attack"}))
        return _start_committed_rider(context, command, "snagging_strike")
    if isinstance(command, CombatGrab):
        if not _free_hand_strike_is_legal(context, "combat_grab", press=True):
            return FamilyProcedureResult(rejection="Combat Grab requires its feat, a free hand, and a prior Strike this turn.")
        context.require_action_permitted("combat_grab", frozenset({"attack", "press"}))
        return _start_committed_rider(context, command, "combat_grab")
    if isinstance(command, BrutishShove):
        if (
            "brutish_shove" not in context.definition.abilities
            or context.actor.actions_remaining < 1
            or context.actor.strikes_this_turn < 1
            or (command.shove_destination is not None and not isinstance(command.shove_destination, Position))
            or type(command.follow) is not bool
            or type(command.failure_effect) is not bool
        ):
            return FamilyProcedureResult(rejection="Brutish Shove requires its feat, a prior Strike this turn, and a horizontal destination.")
        context.require_action_permitted("brutish_shove", frozenset({"attack", "press"}))
        return _start_committed_rider(context, command, "brutish_shove")
    return None


def _start_committed_rider(
    context: FamilyProcedureContext,
    command: SnaggingStrike | CombatGrab | BrutishShove,
    kind: str,
) -> FamilyProcedureResult:
    """Send each admitted fixed rider through one ordinary Strike transaction."""
    hook = getattr(context.encounter, "_start_committed_strike_rider", None)
    if not callable(hook):
        return FamilyProcedureResult(unsupported="The core committed Strike rider hook is not available.")
    result = hook(context, command, kind)
    if not isinstance(result, FamilyProcedureResult):
        return FamilyProcedureResult(unsupported="The core committed Strike rider hook returned an invalid result.")
    return result


def apply_committed_strike_rider_for_kind(
    context: FamilyProcedureContext,
    *,
    kind: str,
    target_id: str,
    damage: int,
    critical: bool,
    hit: bool,
) -> tuple[Event, ...]:
    """Apply the finite committed result/rider family after defenses."""

    target = context.state.creatures.get(target_id)
    if target is None:
        raise ValueError("Fighter rider target is no longer present")
    if kind == "intimidating_strike" and damage < 1:
        return (Event(
            "intimidating_strike_no_fear", context.actor.actor_id, target.actor_id,
            f"{context.actor.label}'s Intimidating Strike dealt no damage, so it does not frighten {target.label}.",
        ),)
    if kind == "intimidating_strike" and intimidating_strike_target_is_immune(context, target_id):
        return (Event(
            "intimidating_strike_immune", context.actor.actor_id, target.actor_id,
            f"{target.label} is immune to Intimidating Strike's fear effect.",
        ),)
    from .skill_actions import add_timed_condition_effect
    source_id = context.actor.actor_id
    if kind == "intimidating_strike":
        frightened = 2 if critical else 1
        current_end = context.state.actor_end_counts.get(target.actor_id, 0)
        add_timed_condition_effect(context, effect_id=f"intimidating_strike:{source_id}:{target_id}:{context.state.round_number}:{current_end}", kind="frightened", source_id=source_id, target_id=target_id, value=frightened, expiration=EffectExpiration(target.actor_id, "end", current_end + frightened))
        return (Event("condition_applied", source_id, target_id, f"{target.label} is frightened {frightened} by Intimidating Strike."),)
    if kind == "snagging_strike" and hit:
        current_start = context.state.actor_start_counts.get(source_id, 0)
        add_timed_condition_effect(context, effect_id=f"snagging_strike:{source_id}:{target_id}:{context.state.round_number}:{current_start}", kind="off_guard", source_id=source_id, target_id=target_id, value=1, expiration=EffectExpiration(source_id, "start", current_start + 1))
        return (Event("condition_applied", source_id, target_id, f"{target.label} is off-guard to {context.actor.label}'s Snagging Strike."),)
    if kind == "combat_grab" and hit:
        current_end = context.state.actor_end_counts.get(source_id, 0)
        add_timed_condition_effect(context, effect_id=f"combat_grab:{source_id}:{target_id}:{context.state.round_number}:{current_end}", kind="grabbed", source_id=source_id, target_id=target_id, value=1, expiration=EffectExpiration(source_id, "end", current_end + 2), dc=context.skill_dc(source_id, "athletics"))
        return (Event("condition_applied", source_id, target_id, f"{target.label} is grabbed by Combat Grab until the end of {context.actor.label}'s next turn or Escape."),)
    if kind == "brutish_shove":
        current_end = context.state.actor_end_counts.get(source_id, 0)
        add_timed_condition_effect(context, effect_id=f"brutish_shove:{source_id}:{target_id}:{context.state.round_number}:{current_end}", kind="off_guard", source_id=source_id, target_id=target_id, value=1, expiration=EffectExpiration(source_id, "end", current_end + 1))
        return (Event("condition_applied", source_id, target_id, f"{target.label} is off-guard to Brutish Shove until the end of {context.actor.label}'s turn."),)
    return ()


def end_snagging_strikes_out_of_reach(state) -> None:
    """End Snagging Strike's effect once its target leaves the free-hand reach.

    AoN feat 4773 makes this a live range boundary, not merely an expiration
    timestamp.  The core calls it after every atomic public command, including
    movement and reaction resolution.
    """
    from .space import grid_distance_feet

    state.condition_effects[:] = [
        effect for effect in state.condition_effects
        if not (
            effect.effect_id.startswith("snagging_strike:")
            and (
                effect.source_actor_id not in state.creatures
                or effect.target_actor_id not in state.creatures
                or grid_distance_feet(
                    state.creatures[effect.source_actor_id].position,
                    state.creatures[effect.target_actor_id].position,
                ) > 5
            )
        )
    ]


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
