"""Selected level-1 Justice Champion procedures.

This module owns only the admitted Human/Iomedae Champion slice.  It routes
through the shared martial family transaction so action costs, reactions,
health, effects, and save/load remain core-owned.

Sources checked 2026-09-16:
* https://2e.aonprd.com/Classes.aspx?ID=58
* https://2e.aonprd.com/Causes.aspx?ID=11
* https://2e.aonprd.com/Spells.aspx?ID=2047
* https://2e.aonprd.com/Feats.aspx?ID=5884
"""

from __future__ import annotations

from dataclasses import dataclass

from .health import healing as pc_healing
from .model import (
    ActionContinuation,
    ActiveSpellEffect,
    Event,
    FamilyCommand,
    FamilyProcedureContext,
    FamilyProcedureResult,
    LayOnHands,
    ResumeAura,
    SuppressAura,
    ToggleAura,
)
from .space import grid_distance_feet


JUSTICE_ABILITY = "justice_champion"
RETRIBUTIVE_STRIKE_ABILITY = "justice_retributive_strike"
LAY_ON_HANDS_ABILITY = "lay_on_hands"
DESPERATE_PRAYER_ABILITY = "desperate_prayer"
JUSTICE_AC_EFFECT = "lay_on_hands_ac"


def is_justice_champion(definition) -> bool:
    return JUSTICE_ABILITY in definition.abilities


def _reject_unless_champion(context: FamilyProcedureContext) -> str | None:
    if not is_justice_champion(context.definition):
        return "This procedure is only admitted for the selected Justice Champion."
    return None


def _lay_target(context: FamilyProcedureContext, target_id: str):
    target = context.state.creatures.get(target_id)
    if target is None or target.actor_id == context.actor.actor_id:
        if target is None:
            return None, "Lay on Hands requires an existing living target."
        # Self-healing is legal; this branch only distinguishes the error text.
    if target is None or target.dead or not context.encounter._is_living_target(target):
        return None, "Lay on Hands requires a living target."
    if target.team != context.actor.team:
        return None, "Lay on Hands can target only an ally."
    if grid_distance_feet(context.actor.position, target.position) > 5:
        return None, "Lay on Hands requires a target within 5 feet."
    return target, None


def _resolve_lay(context: FamilyProcedureContext, continuation: ActionContinuation) -> list[Event]:
    encounter = context.encounter
    state = context.state
    target = state.creatures.get(continuation.target_id or "")
    if target is None or target.dead or not encounter._is_living_target(target):
        raise ValueError("Lay on Hands' living target is no longer eligible.")
    if target.team != context.actor.team or grid_distance_feet(context.actor.position, target.position) > 5:
        raise ValueError("Lay on Hands' target is no longer within touch range.")

    amount = 6
    if target.health_mode.value == "pc":
        transition = pc_healing(encounter._health_state(target), amount)
        encounter._apply_health_transition(state, target, transition)
    else:
        from .content import get_definition

        target.hp = min(get_definition(target.definition_id).hp, target.hp + amount)
        if target.hp > 0:
            target.unconscious = False

    events = [Event(
        "lay_on_hands",
        context.actor.actor_id,
        target.actor_id,
        f"{context.actor.label} uses Lay on Hands; {target.label} heals 6 HP and is now at {target.hp} HP.",
    )]
    if target.actor_id != context.actor.actor_id:
        effect_id = f"lay_on_hands:{context.actor.actor_id}:{target.actor_id}:{state.next_choice_id}"
        state.active_effects.append(ActiveSpellEffect(
            effect_id,
            JUSTICE_AC_EFFECT,
            context.actor.actor_id,
            target.actor_id,
            2,
            state.actor_start_counts.get(context.actor.actor_id, 0) + 1,
            None,
        ))
        events.append(Event(
            "lay_on_hands_ac",
            context.actor.actor_id,
            target.actor_id,
            f"{target.label} gains +2 status AC until the start of {context.actor.label}'s next turn.",
        ))
    return events + encounter._complete_action(state, context.actor, [], dice=context.dice)


def _handle_lay(context: FamilyProcedureContext, command: LayOnHands) -> FamilyProcedureResult:
    if LAY_ON_HANDS_ABILITY not in context.definition.abilities:
        return FamilyProcedureResult(unsupported="Lay on Hands is not admitted for this creature.")
    if context.actor.actions_remaining < 1:
        return FamilyProcedureResult(rejection="Lay on Hands requires one action.")
    if context.actor.focus_points < 1:
        return FamilyProcedureResult(rejection="Lay on Hands requires 1 Focus Point.")
    target, error = _lay_target(context, command.target_id)
    if error:
        return FamilyProcedureResult(rejection=error)

    context.require_action_permitted("lay_on_hands", frozenset({"manipulate", "concentrate"}))
    context.actor.focus_points -= 1
    context.state.desperate_prayer_points.discard(context.actor.actor_id)
    context.commit_family_action(actions=1)
    continuation = ActionContinuation(
        kind="justice_lay_on_hands",
        actor_id=context.actor.actor_id,
        target_id=target.actor_id,
        movement_kind="manipulate",
        reaction_trigger="manipulate",
        must_disrupt_on_critical=True,
        stage="committed",
    )
    events = [Event(
        "lay_on_hands_started",
        context.actor.actor_id,
        target.actor_id,
        f"{context.actor.label} commits Lay on Hands on {target.label}.",
    )]
    events.extend(context.encounter._advance_continuation(context.state, context.dice, continuation))
    return FamilyProcedureResult(events=tuple(events))


def _handle_aura(context: FamilyProcedureContext, active: bool) -> FamilyProcedureResult:
    error = _reject_unless_champion(context)
    if error:
        return FamilyProcedureResult(rejection=error)
    if context.actor.actions_remaining < 1:
        return FamilyProcedureResult(rejection="Suppressing or resuming the aura requires one action.")
    if active == (context.actor.actor_id in context.state.justice_aura_active):
        return FamilyProcedureResult(rejection=("The divine aura is already active." if active else "The divine aura is already suppressed."))
    context.require_action_permitted("champion_aura", frozenset({"concentrate"}))
    context.commit_family_action(actions=1)
    if active:
        context.state.justice_aura_active.add(context.actor.actor_id)
        text = f"{context.actor.label} resumes the 15-foot divine aura."
        kind = "aura_resumed"
    else:
        context.state.justice_aura_active.discard(context.actor.actor_id)
        text = f"{context.actor.label} suppresses the 15-foot divine aura."
        kind = "aura_suppressed"
    return FamilyProcedureResult(events=tuple(
        context.encounter._complete_action(
            context.state,
            context.actor,
            [Event(kind, context.actor.actor_id, None, text)],
            dice=context.dice,
        )
    ))


def handle_action(context: FamilyProcedureContext) -> FamilyProcedureResult | None:
    command = context.command
    if isinstance(command, LayOnHands):
        return _handle_lay(context, command)
    if isinstance(command, SuppressAura):
        return _handle_aura(context, False)
    if isinstance(command, ResumeAura):
        return _handle_aura(context, True)
    if isinstance(command, ToggleAura):
        if type(command.active) is not bool:
            return FamilyProcedureResult(rejection="Aura state must be boolean.")
        return _handle_aura(context, command.active)
    return None


def handle_choice(context: FamilyProcedureContext) -> FamilyProcedureResult | None:
    return None


def validate_pending(context: FamilyProcedureContext) -> None:
    pending = context.pending
    if pending is None:
        raise ValueError("save has no Justice pending choice")
    raise ValueError("save has an unsupported Justice pending choice")


def resolve_lay_continuation(encounter, state, dice, continuation: ActionContinuation) -> list[Event]:
    """Finish a committed Lay action after its manipulation reaction window."""
    actor = state.creatures.get(continuation.actor_id or "")
    if actor is None:
        raise ValueError("Lay on Hands actor no longer exists.")
    from .content import get_definition

    context = FamilyProcedureContext(
        encounter, state, dice, actor,
        get_definition(actor.definition_id), "martial",
    )
    return _resolve_lay(context, continuation)
