"""Finite guard and stance procedures for the selected W2 martial choices.

Sources checked 2026-09-19:

* Dueling Parry (Fighter), Player Core p. 141:
  https://2e.aonprd.com/Feats.aspx?ID=4781
* Crane Stance, Player Core 2 p. 118:
  https://2e.aonprd.com/Feats.aspx?ID=5976
* Reactive Shield, Player Core p. 142:
  https://2e.aonprd.com/Feats.aspx?ID=4772
* Point Blank Stance, Player Core p. 141:
  https://2e.aonprd.com/Feats.aspx?ID=4771

They deliberately share only their AC-modifier projection.  Dueling Parry is
a one-turn circumstance guard whose weapon/hand requirement remains live;
Crane Stance is an encounter stance with a replacement unarmed Strike.
"""

from __future__ import annotations

from dataclasses import dataclass

from .checks import Modifier
from .model import (
    ActiveSpellEffect,
    Event,
    FamilyCommand,
    FamilyProcedureContext,
    FamilyProcedureResult,
    MartialStanceState,
)


@dataclass(frozen=True)
class DuelingParry(FamilyCommand):
    """Use a held one-handed melee weapon to gain the feat's guard."""

    family_id = "martial"
    attack_id: str
    item_id: str | None = None


@dataclass(frozen=True)
class CraneStance(FamilyCommand):
    """Enter the selected Monk's Crane Stance."""

    family_id = "martial"


@dataclass(frozen=True)
class DismissCraneStance(FamilyCommand):
    """Dismiss Crane Stance as its explicit free action."""

    family_id = "martial"


@dataclass(frozen=True)
class PointBlankStance(FamilyCommand):
    """Enter the Fighter's shortbow stance."""

    family_id = "martial"


def _held_attack_matches(item_instances, actor, attack) -> bool:
    """Return whether the single held object is this attack's weapon."""

    if attack.item_id is None or len(actor.held_items) != 1:
        return False
    held_id = actor.held_items[0]
    instance = item_instances.get(held_id)
    return held_id == attack.item_id or (
        instance is not None and instance.definition_id == attack.item_id
    )


def dueling_parry_requirements_met(item_instances, actor, definition, attack=None) -> bool:
    """Check the printed one-weapon, otherwise-empty hands requirement."""

    attacks = (attack,) if attack is not None else definition.attacks
    return any(
        candidate is not None
        and candidate.item_id is not None
        and candidate.hands_required == 1
        and "melee" in candidate.traits
        and _held_attack_matches(item_instances, actor, candidate)
        for candidate in attacks
    )


def dueling_parry_is_active(state, actor, definition) -> bool:
    """Return the live guarded state only while its requirements continue."""

    return (
        "dueling_parry" in definition.abilities
        and dueling_parry_requirements_met(state.item_instances, actor, definition)
        and any(
            effect.kind == "dueling_parry"
            and effect.source_actor_id == actor.actor_id
            and effect.target_actor_id == actor.actor_id
            and effect.expires_at_source_start
            > state.actor_start_counts.get(actor.actor_id, 0)
            for effect in state.active_effects
        )
    )


def crane_stance_is_active(state, actor_id: str) -> bool:
    stance = state.martial_stances.get(actor_id)
    return stance is not None and stance.stance_id == "crane_stance"


def crane_stance_attack_permitted(state, actor_id: str, attack_id: str) -> bool:
    """Keep Crane Wing unavailable outside the stance and exclusive inside it."""

    active = crane_stance_is_active(state, actor_id)
    if attack_id == "crane_wing":
        return active
    return not active


def crane_stance_leap_bonus(state, actor_id: str) -> int:
    """Return Crane Stance's printed horizontal Leap increase, if active."""

    return 5 if crane_stance_is_active(state, actor_id) else 0


def point_blank_stance_is_active(state, actor_id: str) -> bool:
    stance = state.martial_stances.get(actor_id)
    return stance is not None and stance.stance_id == "point_blank_stance"


def point_blank_stance_damage_bonus(state, actor, target, attack) -> int:
    """Return the fixed first-range-increment bonus for a legal attack."""

    from .content import get_definition

    definition = get_definition(actor.definition_id)
    if (
        not point_blank_stance_is_active(state, actor.actor_id)
        or "Point Blank Stance" not in definition.feats
        or "ranged" not in attack.traits
        or "volley" in attack.traits
        or attack.range_increment_ft is None
    ):
        return 0
    distance = max(
        abs(actor.position.x - target.position.x),
        abs(actor.position.y - target.position.y),
    ) * 5
    return 2 if distance <= attack.range_increment_ft else 0


def end_dueling_parries_with_broken_requirements(state) -> None:
    """End a guard at the instant its continuous hand requirement is broken."""

    from .content import get_definition

    state.active_effects[:] = [
        effect
        for effect in state.active_effects
        if effect.kind != "dueling_parry"
        or (
            (actor := state.creatures.get(effect.source_actor_id)) is not None
            and dueling_parry_requirements_met(
                state.item_instances, actor, get_definition(actor.definition_id)
            )
        )
    ]


def _unarmored(definition, actor) -> bool:
    """The finite Monk sheet has no worn armor or armor category."""

    return definition.armor_category in {None, "unarmored"} and not actor.worn_items


def ac_modifiers(state, actor, definition) -> tuple[Modifier, ...]:
    """Project the two selected defenses without equating their lifecycles."""

    modifiers: list[Modifier] = []
    if dueling_parry_is_active(state, actor, definition):
        modifiers.append(Modifier(2, "circumstance", "Dueling Parry"))
    if crane_stance_is_active(state, actor.actor_id):
        modifiers.append(Modifier(1, "circumstance", "Crane Stance"))
    return tuple(modifiers)


def handle_action(context: FamilyProcedureContext) -> FamilyProcedureResult | None:
    command = context.command
    if isinstance(command, DuelingParry):
        if "dueling_parry" not in context.definition.abilities:
            return FamilyProcedureResult(rejection="Dueling Parry is not admitted for this creature.")
        context.require_action_permitted("dueling_parry", frozenset())
        attack = context.encounter._select_attack(
            context.state, context.actor, command.attack_id, item_id=command.item_id,
        )
        if attack is None or not dueling_parry_requirements_met(
            context.state.item_instances, context.actor, context.definition, attack,
        ):
            return FamilyProcedureResult(
                rejection="Dueling Parry requires one held one-handed melee weapon and empty other hands."
            )
        context.encounter._commit_family_action(context, actions=1)
        context.state.active_effects[:] = [
            effect for effect in context.state.active_effects
            if not (
                effect.kind == "dueling_parry"
                and effect.source_actor_id == context.actor.actor_id
            )
        ]
        context.state.active_effects.append(ActiveSpellEffect(
            f"dueling_parry:{context.actor.actor_id}:{context.state.actor_start_counts.get(context.actor.actor_id, 0)}",
            "dueling_parry", context.actor.actor_id, context.actor.actor_id, 2,
            context.state.actor_start_counts.get(context.actor.actor_id, 0) + 1,
        ))
        return FamilyProcedureResult(events=(Event(
            "dueling_parry", context.actor.actor_id, context.actor.actor_id,
            f"{context.actor.label} uses Dueling Parry; +2 circumstance AC until their next turn starts while holding only that weapon.",
        ),))
    if isinstance(command, CraneStance):
        if "crane_stance" not in context.definition.abilities:
            return FamilyProcedureResult(rejection="Crane Stance is not admitted for this creature.")
        context.require_action_permitted("crane_stance", frozenset({"stance"}))
        if not _unarmored(context.definition, context.actor):
            return FamilyProcedureResult(rejection="Crane Stance requires the Monk to be unarmored.")
        if crane_stance_is_active(context.state, context.actor.actor_id):
            return FamilyProcedureResult(rejection="The Monk is already in Crane Stance.")
        if context.state.martial_stance_used_rounds.get(context.actor.actor_id) == context.state.round_number:
            return FamilyProcedureResult(rejection="Only one stance action can be used each round.")
        context.encounter._commit_family_action(context, actions=1)
        context.state.martial_stances[context.actor.actor_id] = MartialStanceState(
            "crane_stance", context.state.round_number,
        )
        context.state.martial_stance_used_rounds[context.actor.actor_id] = context.state.round_number
        return FamilyProcedureResult(events=(Event(
            "crane_stance", context.actor.actor_id, context.actor.actor_id,
            f"{context.actor.label} enters Crane Stance; +1 circumstance AC and only Crane Wing Strikes are available.",
        ),))
    if isinstance(command, DismissCraneStance):
        if not crane_stance_is_active(context.state, context.actor.actor_id):
            return FamilyProcedureResult(rejection="The Monk is not in Crane Stance.")
        context.state.martial_stances.pop(context.actor.actor_id, None)
        return FamilyProcedureResult(events=(Event(
            "crane_stance_dismissed", context.actor.actor_id, context.actor.actor_id,
            f"{context.actor.label} dismisses Crane Stance.",
        ),))
    if isinstance(command, PointBlankStance):
        if "point_blank_stance" not in context.definition.abilities:
            return FamilyProcedureResult(rejection="Point Blank Stance is not admitted for this creature.")
        context.require_action_permitted("point_blank_stance", frozenset({"stance"}))
        if context.state.martial_stances.get(context.actor.actor_id) is not None:
            return FamilyProcedureResult(rejection="Dismiss the current stance before entering Point Blank Stance.")
        if context.state.martial_stance_used_rounds.get(context.actor.actor_id) == context.state.round_number:
            return FamilyProcedureResult(rejection="Only one stance action can be used each round.")
        if not any(
            "ranged" in attack.traits and attack.item_id in context.actor.held_items
            for attack in context.definition.attacks
        ):
            return FamilyProcedureResult(rejection="Point Blank Stance requires a held ranged weapon.")
        context.encounter._commit_family_action(context, actions=1)
        context.state.martial_stances[context.actor.actor_id] = MartialStanceState(
            "point_blank_stance", context.state.round_number,
        )
        context.state.martial_stance_used_rounds[context.actor.actor_id] = context.state.round_number
        return FamilyProcedureResult(events=(Event(
            "point_blank_stance", context.actor.actor_id, context.actor.actor_id,
            f"{context.actor.label} enters Point Blank Stance; ranged attacks within the first range increment deal +2 circumstance damage.",
        ),))
    return None


def handle_choice(context: FamilyProcedureContext) -> FamilyProcedureResult | None:
    return None


def validate_pending(context: FamilyProcedureContext) -> None:
    raise ValueError("martial defenses do not create pending choices")
