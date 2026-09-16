"""Ordered two-Strike class activities for Monk and Ranger.

The first Strike resolves completely before a second Strike is offered. This
module owns the activity-specific selection sequence; Encounter supplies the
ordinary single-Strike/check/reaction/health continuation.

Sources: Monk Flurry of Blows (https://2e.aonprd.com/Classes.aspx?ID=60),
Hunted Shot (https://2e.aonprd.com/Feats.aspx?ID=4861), subordinate actions
(https://2e.aonprd.com/Rules.aspx?ID=2335), and the paired-resolution notes in
``docs/implementation/paired-strike-resolution.md``. Shared resistance and
weakness allocation remains a separately adjudicated damage concern.
"""

from __future__ import annotations

import base64
import json
from dataclasses import replace

from .model import (
    ActionContinuation,
    ChoiceOption,
    Event,
    FamilyProcedureContext,
    FamilyProcedureResult,
    PairedStrikeContinuation,
    PairedStrikeSelection,
)
from .space import grid_distance_feet


def start_paired_strikes(
    context: FamilyProcedureContext,
    *,
    activity_id: str,
    first_selection: PairedStrikeSelection,
    action_cost: int,
    is_flourish: bool,
    same_target: bool,
    ranged_only: bool,
    require_hunted_prey: bool,
    requires_unarmed_or_monk_weapon: bool,
) -> FamilyProcedureResult:
    """Validate an activity's first Strike and begin its ordered continuation."""
    if activity_id == "ranger:hunted_shot":
        if not (is_flourish and same_target and ranged_only and require_hunted_prey and not requires_unarmed_or_monk_weapon):
            return FamilyProcedureResult(unsupported="Hunted Shot was called with inconsistent activity rules.")
        if "hunted_shot" not in context.definition.abilities:
            return FamilyProcedureResult(unsupported="Hunted Shot is not admitted for this creature.")
    elif activity_id == "monk:flurry_of_blows":
        if not (is_flourish and not same_target and not ranged_only and not require_hunted_prey and requires_unarmed_or_monk_weapon):
            return FamilyProcedureResult(unsupported="Flurry of Blows was called with inconsistent activity rules.")
        if "flurry_of_blows" not in context.definition.abilities:
            return FamilyProcedureResult(unsupported="Flurry of Blows is not admitted for this creature.")
    else:
        return FamilyProcedureResult(unsupported=f"Paired activity {activity_id!r} is not admitted.")

    reason = validate_first_selection(
        context,
        first_selection,
        activity_id=activity_id,
        action_cost=action_cost,
        is_flourish=is_flourish,
        ranged_only=ranged_only,
        require_hunted_prey=require_hunted_prey,
        requires_unarmed_or_monk_weapon=requires_unarmed_or_monk_weapon,
    )
    if reason is not None:
        return FamilyProcedureResult(rejection=reason)

    hook = getattr(context.encounter, "_resolve_subordinate_strike", None)
    if not callable(hook):
        return FamilyProcedureResult(
            unsupported="The core single-subordinate-Strike continuation hook is not available."
        )

    actor = context.actor
    # The paired activity pays once; each subordinate Strike increments MAP
    # and pays its ordinary incidental costs in the core single-Strike hook.
    actor.actions_remaining -= action_cost
    if is_flourish:
        actor.flourish_used_round = context.state.round_number
    context.state.taking_cover.discard(actor.actor_id)
    continuation = PairedStrikeContinuation(
        activity_id=activity_id,
        owner_actor_id=actor.actor_id,
        paid_actions=action_cost,
        initial_attack_count=actor.strikes_this_turn,
        selections=(first_selection,),
        next_index=0,
        outcomes=(),
        stage="first_strike",
    )
    events = [
        Event(
            "paired_strike_started",
            actor.actor_id,
            first_selection.target_id,
            f"{actor.label} begins {activity_id.rsplit(':', 1)[-1].replace('_', ' ')} ({action_cost} action).",
        )
    ]
    result = hook(context, continuation)
    if not isinstance(result, FamilyProcedureResult):
        return FamilyProcedureResult(
            unsupported="The core subordinate-Strike hook returned an invalid result."
        )
    return replace(result, events=tuple(events) + result.events)


def resume_paired_strikes(context: FamilyProcedureContext) -> FamilyProcedureResult:
    """Resume a saved family-level second-Strike selection."""
    pending = context.pending
    choice = context.choice
    if pending is None or choice is None or pending.paired_strike is None:
        return FamilyProcedureResult(rejection="The saved paired-Strike selection is incomplete.")
    continuation = pending.paired_strike
    if continuation.stage != "choose_second" or len(continuation.selections) != 1:
        return FamilyProcedureResult(rejection="The saved paired-Strike stage is inconsistent.")
    current_options = second_strike_options(context, continuation)
    if current_options != pending.options:
        return FamilyProcedureResult(rejection="The available second Strikes changed; choose from the refreshed options.")
    selection = _selection_for_option(current_options, choice.option_id)
    if selection is None:
        return FamilyProcedureResult(rejection="That second-Strike selection is stale.")

    hook = getattr(context.encounter, "_resolve_subordinate_strike", None)
    if not callable(hook):
        return FamilyProcedureResult(
            unsupported="The core single-subordinate-Strike continuation hook is not available."
        )
    resumed = replace(
        continuation,
        selections=(*continuation.selections, selection),
        next_index=1,
        stage="second_strike",
    )
    result = hook(context, resumed)
    if not isinstance(result, FamilyProcedureResult):
        return FamilyProcedureResult(
            unsupported="The core subordinate-Strike hook returned an invalid result."
        )
    return result


def after_subordinate_strike(
    context: FamilyProcedureContext,
    continuation: PairedStrikeContinuation,
    *,
    events: tuple[Event, ...] = (),
) -> FamilyProcedureResult:
    """Choose the next legal step after one subordinate Strike is fully settled.

    The core calls this only after ordinary reactions, check/Hero choices,
    damage, health, and first-hit effects for the current Strike are complete.
    """
    if continuation.owner_actor_id != context.actor.actor_id:
        return FamilyProcedureResult(rejection="The paired Strike belongs to a different actor.")
    resolved_count = len(continuation.outcomes)
    if resolved_count == 1 and continuation.stage == "first_resolved":
        options = second_strike_options(context, continuation)
        if not options:
            stopped = Event(
                "paired_strike_stopped",
                context.actor.actor_id,
                continuation.selections[0].target_id,
                "The activity ends because no legal second Strike can be made.",
            )
            final_events = list(events) + [stopped]
            final_events.extend(
                context.encounter._complete_action(
                    context.state, context.actor, [], dice=context.dice
                )
            )
            return FamilyProcedureResult(events=tuple(final_events))
        selecting = replace(continuation, next_index=1, stage="choose_second")
        action_name = continuation.activity_id.rsplit(":", 1)[-1].replace("_", " ")
        context.present_choice(
            continuation.activity_id,
            context.actor.actor_id,
            f"Choose the second Strike for {action_name}.",
            options,
            ActionContinuation(kind="paired_strike", actor_id=context.actor.actor_id),
            details=(
                "The first Strike, its reactions, damage, and health effects have resolved.",
                "Choose from the currently legal second Strikes; the choice is revalidated before it begins.",
            ),
            paired_strike=selecting,
        )
        return FamilyProcedureResult(events=events)
    if resolved_count == 2 and continuation.stage == "second_resolved":
        completed = replace(continuation, stage="done")
        final_events = list(events)
        final_events.append(
            Event(
                "paired_strike_complete",
                context.actor.actor_id,
                None,
                f"{completed.activity_id.rsplit(':', 1)[-1].replace('_', ' ').title()} is complete.",
            )
        )
        final_events.extend(
            context.encounter._complete_action(context.state, context.actor, [], dice=context.dice)
        )
        return FamilyProcedureResult(events=tuple(final_events))
    return FamilyProcedureResult(rejection="The paired Strike continuation has no completed subordinate Strike.")


def validate_pending(context: FamilyProcedureContext, *, activity_id: str) -> None:
    """Validate persisted state for a pending player choice between Strikes."""
    pending = context.pending
    if pending is None or pending.paired_strike is None:
        raise ValueError("save has no paired-Strike continuation")
    continuation = pending.paired_strike
    if (
        pending.procedure_id != activity_id
        or pending.family_id != "martial"
        or pending.actor_id != context.actor.actor_id
        or pending.continuation is None
        or pending.continuation.actor_id != context.actor.actor_id
        or pending.continuation.kind != "paired_strike"
        or continuation.activity_id != activity_id
        or continuation.owner_actor_id != context.actor.actor_id
        or continuation.paid_actions != 1
        or continuation.stage != "choose_second"
        or continuation.next_index != 1
        or len(continuation.selections) != 1
        or len(continuation.outcomes) != 1
        or not pending.options
    ):
        raise ValueError("save has an inconsistent pending paired-Strike selection")
    if len({option.option_id for option in pending.options}) != len(pending.options):
        raise ValueError("save has duplicate paired-Strike options")
    if second_strike_options(context, continuation) != pending.options:
        raise ValueError("save has stale paired-Strike options")
    for option in pending.options:
        if _decode_selection(option.option_id) is None:
            raise ValueError("save has a malformed paired-Strike option")


def validate_first_selection(
    context: FamilyProcedureContext,
    selection: PairedStrikeSelection,
    *,
    activity_id: str,
    action_cost: int,
    is_flourish: bool,
    ranged_only: bool,
    require_hunted_prey: bool,
    requires_unarmed_or_monk_weapon: bool,
) -> str | None:
    """Check shared and class-specific gates before any action is committed."""
    actor = context.actor
    state = context.state
    definition = context.definition
    if not isinstance(selection, PairedStrikeSelection):
        return "Choose the first Strike before starting this activity."
    if type(action_cost) is not int or action_cost < 1:
        return "A paired Strike activity needs a positive action cost."
    if actor.unconscious or actor.dead:
        return "An incapacitated creature cannot begin this activity."
    if actor.actions_remaining < action_cost:
        return f"This activity requires {action_cost} action(s)."
    if actor.must_leave_occupied:
        return "Move out of the occupied ally's space before taking another action."
    if is_flourish and actor.flourish_used_round == state.round_number:
        return "Only one flourish action can be used per round."
    if type(selection.nonlethal) not in (bool, type(None)):
        return "Nonlethal intent must be true, false, or the attack's default."

    target = state.creatures.get(selection.target_id)
    if target is None or target.actor_id == actor.actor_id or target.defeated:
        return "The first Strike needs another active creature as its target."
    attack_definition = next(
        (attack for attack in definition.attacks if attack.attack_id == selection.attack_id),
        None,
    )
    if attack_definition is None:
        return f"Attack {selection.attack_id!r} is not supported for this creature."
    attack = context.encounter._select_attack(actor, selection.attack_id)
    if attack is None:
        return f"Attack {selection.attack_id!r} is not currently equipped or usable."

    if ranged_only and (attack.item_id is None or "ranged" not in attack.traits):
        return "Hunted Shot requires a ranged weapon."
    if ranged_only:
        reload_value = getattr(attack, "reload", None)
        if reload_value != 0:
            return "Hunted Shot requires a ranged weapon with reload 0."
    if require_hunted_prey:
        hunted_prey = actor.hunted_prey
        if hunted_prey is None or target.actor_id != hunted_prey.target_actor_id:
            return "Hunted Shot must target your current hunted prey."
    if requires_unarmed_or_monk_weapon:
        from .monk import is_flurry_strike

        if not is_flurry_strike(definition.abilities, attack):
            return "Flurry of Blows requires an unarmed Strike or a melee monk weapon permitted by Monastic Weaponry."
    if selection.damage_type is not None and selection.damage_type not in context.encounter._attack_damage_types(attack):
        return f"{selection.damage_type!r} is not an available damage type for {attack.name}."
    return None


def second_strike_options(
    context: FamilyProcedureContext,
    continuation: PairedStrikeContinuation,
) -> tuple[ChoiceOption, ...]:
    """Return every currently legal second Strike choice, without choosing."""
    activity_id = continuation.activity_id
    first = continuation.selections[0]
    if activity_id == "ranger:hunted_shot":
        targets = (first.target_id,)
        first_attack_id = first.attack_id
        ranged_only = True
        monk_weapons_only = False
    elif activity_id == "monk:flurry_of_blows":
        targets = tuple(context.state.creatures)
        first_attack_id = None
        ranged_only = False
        monk_weapons_only = True
    else:
        return ()

    actor = context.actor
    if actor.unconscious or actor.dead or actor.must_leave_occupied:
        return ()
    if activity_id == "ranger:hunted_shot":
        prey = actor.hunted_prey
        if prey is None or prey.target_actor_id != first.target_id:
            return ()
    options: list[ChoiceOption] = []
    for target_id in targets:
        target = context.state.creatures.get(target_id)
        if target is None or target.actor_id == actor.actor_id or target.defeated:
            continue
        distance = grid_distance_feet(actor.position, target.position)
        for attack in context.definition.attacks:
            if first_attack_id is not None and attack.attack_id != first_attack_id:
                continue
            if not context.encounter._attack_usable(context.state, actor, attack):
                continue
            if ranged_only:
                if "ranged" not in attack.traits or getattr(attack, "reload", None) != 0:
                    continue
                if attack.max_range_ft is None or distance > attack.max_range_ft:
                    continue
            elif distance > attack.reach_ft:
                continue
            if attack.free_hands_required and max(0, 2 - len(actor.held_items)) < attack.free_hands_required:
                continue
            if monk_weapons_only:
                from .monk import is_flurry_strike

                if not is_flurry_strike(context.definition.abilities, attack):
                    continue
            damage_types = (None, *(
                value
                for value in context.encounter._attack_damage_types(attack)
                if value != attack.damage_type
            ))
            for damage_type in damage_types:
                default_nonlethal = "nonlethal" in attack.traits
                for nonlethal in (None, not default_nonlethal):
                    selection = PairedStrikeSelection(
                        target_id=target.actor_id,
                        attack_id=attack.attack_id,
                        damage_type=damage_type,
                        nonlethal=nonlethal,
                    )
                    intent = "nonlethal" if (default_nonlethal if nonlethal is None else nonlethal) else "lethal"
                    displayed_damage_type = damage_type or attack.damage_type
                    options.append(
                        ChoiceOption(
                            _encode_selection(selection),
                            f"{attack.name} → {target.label} ({displayed_damage_type}, {intent})",
                        )
                    )
    return tuple(options)


def _encode_selection(selection: PairedStrikeSelection) -> str:
    payload = json.dumps(
        {
            "target": selection.target_id,
            "attack": selection.attack_id,
            "damage": selection.damage_type,
            "nonlethal": selection.nonlethal,
        },
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return "paired:" + base64.urlsafe_b64encode(payload).decode("ascii").rstrip("=")


def _decode_selection(option_id: str) -> PairedStrikeSelection | None:
    if not isinstance(option_id, str) or not option_id.startswith("paired:"):
        return None
    encoded = option_id.removeprefix("paired:")
    try:
        raw = base64.urlsafe_b64decode(encoded + "=" * (-len(encoded) % 4))
        value = json.loads(raw)
        if set(value) != {"target", "attack", "damage", "nonlethal"}:
            return None
        if any(not isinstance(value[key], str) or not value[key] for key in ("target", "attack")):
            return None
        if value["damage"] is not None and (not isinstance(value["damage"], str) or not value["damage"]):
            return None
        if value["nonlethal"] is not None and type(value["nonlethal"]) is not bool:
            return None
        return PairedStrikeSelection(
            target_id=value["target"],
            attack_id=value["attack"],
            damage_type=value["damage"],
            nonlethal=value["nonlethal"],
        )
    except (ValueError, TypeError, KeyError):
        return None


def _selection_for_option(options: tuple[ChoiceOption, ...], option_id: str) -> PairedStrikeSelection | None:
    if option_id not in {option.option_id for option in options}:
        return None
    return _decode_selection(option_id)
