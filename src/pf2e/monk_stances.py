"""W5 Monk stance policies and lifecycle helpers.

The two new stances deliberately share the existing finite stance state.  The
policy is narrow: it governs attack availability and the Tiger Step extension;
ordinary fists remain legal in both stances.
"""

from __future__ import annotations

from dataclasses import dataclass

from .model import (
    ActionContinuation,
    ChoiceOption,
    Event,
    FamilyCommand,
    FamilyProcedureContext,
    FamilyProcedureResult,
    MartialStanceState,
    PendingChoice,
)


@dataclass(frozen=True)
class TigerStance(FamilyCommand):
    family_id = "martial"


@dataclass(frozen=True)
class WolfStance(FamilyCommand):
    family_id = "martial"


@dataclass(frozen=True)
class DismissTigerStance(FamilyCommand):
    family_id = "martial"


@dataclass(frozen=True)
class DismissWolfStance(FamilyCommand):
    family_id = "martial"


STANCE_ATTACKS = {
    "tiger_stance": "tiger_claws",
    "wolf_stance": "wolf_jaws",
}


def active_stance(state, actor_id: str) -> str | None:
    stance = state.martial_stances.get(actor_id)
    return None if stance is None else stance.stance_id


def stance_attack_permitted(state, actor_id: str, attack_id: str) -> bool:
    """Apply the finite policy used by Crane, Tiger, and Wolf."""

    stance = active_stance(state, actor_id)
    if stance == "crane_stance":
        return attack_id == "crane_wing"
    if stance in STANCE_ATTACKS:
        # Tiger/Wolf don't prohibit normal fists, but their replacement attack
        # exists only while the matching stance is held.
        return attack_id in {"fist", STANCE_ATTACKS[stance]}
    return attack_id not in set(STANCE_ATTACKS.values()) | {"crane_wing"}


def tiger_stance_is_active(state, actor_id: str) -> bool:
    return active_stance(state, actor_id) == "tiger_stance"


def wolf_stance_is_active(state, actor_id: str) -> bool:
    return active_stance(state, actor_id) == "wolf_stance"


def tiger_step_enabled(state, actor_id: str, speed_ft: int) -> bool:
    return tiger_stance_is_active(state, actor_id) and speed_ft >= 20


def handle_action(context: FamilyProcedureContext) -> FamilyProcedureResult | None:
    command = context.command
    entries = {
        TigerStance: ("tiger_stance", "Tiger Stance"),
        WolfStance: ("wolf_stance", "Wolf Stance"),
    }
    if isinstance(command, (DismissTigerStance, DismissWolfStance)):
        expected = "tiger_stance" if isinstance(command, DismissTigerStance) else "wolf_stance"
        if active_stance(context.state, context.actor.actor_id) != expected:
            return FamilyProcedureResult(rejection=f"The Monk is not in {expected.replace('_', ' ').title()}.")
        context.state.martial_stances.pop(context.actor.actor_id, None)
        return FamilyProcedureResult(events=(Event(
            f"{expected}_dismissed", context.actor.actor_id, context.actor.actor_id,
            f"{context.actor.label} dismisses {expected.replace('_', ' ').title()}.",
        ),))
    entry = next((value for cls, value in entries.items() if isinstance(command, cls)), None)
    if entry is None:
        return None
    stance_id, label = entry
    if stance_id not in context.definition.abilities:
        return FamilyProcedureResult(rejection=f"{label} is not admitted for this creature.")
    context.require_action_permitted(stance_id, frozenset({"stance"}))
    if context.definition.armor_category not in {None, "unarmored"} or context.actor.worn_items:
        return FamilyProcedureResult(rejection=f"{label} requires the Monk to be unarmored.")
    if context.state.martial_stances.get(context.actor.actor_id) is not None:
        return FamilyProcedureResult(rejection="Dismiss the current stance before entering another stance.")
    if context.state.martial_stance_used_rounds.get(context.actor.actor_id) == context.state.round_number:
        return FamilyProcedureResult(rejection="Only one stance action can be used each round.")
    context.encounter._commit_family_action(context, actions=1)
    context.state.martial_stances[context.actor.actor_id] = MartialStanceState(
        stance_id, context.state.round_number,
    )
    context.state.martial_stance_used_rounds[context.actor.actor_id] = context.state.round_number
    attack_name = "Tiger Claws" if stance_id == "tiger_stance" else "Wolf Jaws"
    return FamilyProcedureResult(events=(Event(
        stance_id, context.actor.actor_id, context.actor.actor_id,
        f"{context.actor.label} enters {label}; {attack_name} is available and ordinary fists remain legal.",
    ),))


def validate_pending(context: FamilyProcedureContext) -> None:
    pending = context.pending
    if pending is None or pending.procedure_id != "monk_stances:tiger_bleed":
        raise ValueError("Monk stances have an invalid saved choice")
    continuation = pending.continuation
    target = context.state.creatures.get(pending.target_id or "")
    tiger_attack = next(
        (attack for attack in context.definition.attacks if attack.attack_id == "tiger_claws"),
        None,
    )
    existing = next(
        (
            effect for effect in context.state.persistent_effects
            if effect.target_actor_id == (target.actor_id if target is not None else "")
            and effect.damage_type == "bleed"
        ),
        None,
    )
    resolution = pending.damage_resolution
    if (
        pending.kind != "family_action"
        or pending.family_id != "martial"
        or pending.owner_actor_id != context.actor.actor_id
        or pending.actor_id != context.actor.actor_id
        or pending.target_id == context.actor.actor_id
        or pending.attack_id != "tiger_claws"
        or pending.options != (
            ChoiceOption("existing", "Keep existing bleed"),
            ChoiceOption("incoming", "Use Tiger's 1d4 bleed"),
        )
        or continuation is None or continuation.stage != "tiger_bleed_choice"
        or continuation.actor_id != context.actor.actor_id
        or continuation.target_id != pending.target_id
        or continuation.attack_id != "tiger_claws"
        or tiger_attack is None
        or target is None or target.dead
        or not tiger_stance_is_active(context.state, context.actor.actor_id)
        or "Tiger Stance" not in context.definition.feats
        or existing is None
        or (bool(existing.dice) and existing.dice == (4,))
        or resolution is None
        or resolution.source_kind != "strike"
        or resolution.actor_id != context.actor.actor_id
        or resolution.target_id != pending.target_id
        or resolution.attack_id != "tiger_claws"
        or not resolution.attacker_critical
        or resolution.continuation != continuation.parent_continuation
    ):
        raise ValueError("save has an invalid Tiger bleed choice")


def post_mitigation_tiger_bleed(
    state, *, attacker, target, attack, damage, check, continuation=None,
    damage_resolution=None,
):
    """Install Tiger's exactly-one-d4 critical bleed after defenses."""
    if (
        attack is None
        or "Tiger Stance" not in _definition(attacker).feats
        or not tiger_stance_is_active(state, attacker.actor_id)
        or attack.attack_id != "tiger_claws"
        or target.defeated
        or target.definition_id in {"skeleton_guard_mc3193", "zombie_shambler_mc3249"}
    ):
        return None
    from .persistent_effects import install_persistent_effect

    installed, existing = install_persistent_effect(
        state,
        source_actor_id=attacker.actor_id,
        target_actor_id=target.actor_id,
        source_id="tiger_stance",
        damage_type="bleed",
        dice=(4,),
    )
    if existing is not None and installed is None and (
        bool(existing.dice) != True or existing.dice != (4,)
    ):
        continuation = ActionContinuation(
            kind="family_action", actor_id=attacker.actor_id,
            target_id=target.actor_id, attack_id=attack.attack_id,
            stage="tiger_bleed_choice",
            parent_continuation=continuation,
        )
        state.pending_choice = PendingChoice(
            choice_id=state.next_choice_id,
            kind="family_action",
            owner_actor_id=attacker.actor_id,
            prompt=f"{target.label} already has persistent bleed; choose which 1d4 bleed source remains.",
            options=(
                ChoiceOption("existing", "Keep existing bleed"),
                ChoiceOption("incoming", "Use Tiger's 1d4 bleed"),
            ),
            details=("Persistent bleed uses one finite condition record per target and damage type.",),
            actor_id=attacker.actor_id,
            target_id=target.actor_id,
            attack_id=attack.attack_id,
            continuation=continuation,
            damage_resolution=damage_resolution,
            family_id="martial",
            procedure_id="monk_stances:tiger_bleed",
        )
        state.next_choice_id += 1
        return Event("choice_offered", attacker.actor_id, target.actor_id, "Choose which persistent bleed source remains.", check=check)
    if installed is None:
        return None
    return Event(
        "persistent_applied", attacker.actor_id, target.actor_id,
        f"{target.label} takes 1d4 persistent bleed from Tiger Stance.", check=check,
    )


def handle_choice(context: FamilyProcedureContext) -> FamilyProcedureResult | None:
    pending = context.pending
    if pending is None or pending.procedure_id != "monk_stances:tiger_bleed":
        return None
    choice = context.choice
    if choice is None or choice.option_id not in {"existing", "incoming"}:
        return FamilyProcedureResult(rejection="Choose the existing bleed or Tiger's 1d4 bleed.")
    target = context.state.creatures.get(pending.target_id or "")
    if target is None:
        return FamilyProcedureResult(rejection="The Tiger bleed target is no longer present.")
    if choice.option_id == "incoming":
        existing = next(
            (item for item in context.state.persistent_effects
             if item.target_actor_id == target.actor_id and item.damage_type == "bleed"),
            None,
        )
        if existing is not None:
            context.state.persistent_effects.remove(existing)
        from .persistent_effects import install_persistent_effect

        install_persistent_effect(
            context.state,
            source_actor_id=context.actor.actor_id,
            target_actor_id=target.actor_id,
            source_id="tiger_stance",
            damage_type="bleed",
            dice=(4,),
        )
        text = f"{context.actor.label} keeps Tiger's 1d4 persistent bleed on {target.label}."
    else:
        text = f"{context.actor.label} keeps the existing persistent bleed on {target.label}."
    events = [Event("persistent_choice", context.actor.actor_id, target.actor_id, text)]
    continuation = pending.continuation
    if continuation is None:
        raise ValueError("Tiger bleed choice has no continuation")
    parent = continuation.parent_continuation
    resolution = pending.damage_resolution
    if resolution is not None:
        retaliation_events, retaliation_started = context.encounter._justice_retaliation(
            context.state, context.dice, resolution
        )
        events.extend(retaliation_events)
        if retaliation_started:
            return FamilyProcedureResult(events=tuple(events))
        parent = resolution.continuation
    if parent is None:
        events.extend(
            context.encounter._complete_action(
                context.state, context.actor, [], dice=context.dice
            )
        )
    else:
        events.extend(
            context.encounter._resume_continuation(
                context.state, context.dice, parent, critical=False
            )
        )
    return FamilyProcedureResult(events=tuple(events))


def _definition(actor):
    from .content import get_definition

    return get_definition(actor.definition_id)
