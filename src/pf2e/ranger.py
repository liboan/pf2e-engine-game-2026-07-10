"""Ranger level-1 class procedures and hunter's-edge rules.

Rules follow the reviewed Player Core Ranger entry and the detailed source
facts in ``docs/implementation/pc1-pc2-nature-rules.md``. This module keeps
the three printed edges as explicit facts; it does not infer class behavior
from actor labels.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from .checks import Modifier, multiple_attack_penalty
from .damage import DamageTerm
from .model import (
    Event,
    FamilyCommand,
    FamilyProcedureContext,
    FamilyProcedureResult,
    HuntedPreyState,
    PairedStrikeSelection,
)


class HunterEdge(StrEnum):
    FLURRY = "flurry"
    OUTWIT = "outwit"
    PRECISION = "precision"


@dataclass(frozen=True)
class HuntPrey(FamilyCommand):
    """Designate a creature as prey with the one-action Hunt Prey activity."""

    family_id = "martial"
    target_id: str


@dataclass(frozen=True)
class HuntedShot(FamilyCommand):
    """Begin Hunted Shot with its first selected reload-0 ranged Strike."""

    family_id = "martial"
    strike: PairedStrikeSelection


def hunter_edge(abilities: tuple[str, ...] | list[str]) -> HunterEdge | None:
    """Read the one fixed edge encoded in a reviewed Ranger definition."""
    selected = tuple(edge for edge in HunterEdge if f"hunter_edge_{edge.value}" in abilities)
    if len(selected) > 1:
        raise ValueError("a Ranger definition can have only one Hunter's Edge")
    return selected[0] if selected else None


def flurry_map_penalty(
    attacks_already_made: int,
    attack_traits: frozenset[str],
    *,
    attacking_hunted_prey: bool,
    edge: HunterEdge,
) -> int:
    """Return the applicable MAP, counting every earlier attack normally."""
    if edge is not HunterEdge.FLURRY or not attacking_hunted_prey:
        return multiple_attack_penalty(attacks_already_made, attack_traits)
    if attacks_already_made <= 0:
        return 0
    agile_penalty = "agile" in attack_traits
    if attacks_already_made == 1:
        return -2 if agile_penalty else -3
    return -4 if agile_penalty else -6


def hunt_prey_skill_modifier(
    *,
    target_is_hunted_prey: bool,
    action_id: str,
) -> Modifier | None:
    """Return Hunt Prey's circumstance bonus for Seek or Track about prey."""
    if target_is_hunted_prey and action_id in {"seek", "track"}:
        return Modifier(2, "circumstance", "Hunt Prey")
    return None


def hunted_prey_range_penalty(
    distance_ft: int,
    range_increment_ft: int,
    *,
    target_is_hunted_prey: bool,
) -> int:
    """Return range MAP, ignoring only the second increment penalty for prey.

    A normal ranged attack takes no penalty in its first increment, –2 in its
    second, and –4 in its third. Hunt Prey removes the second-increment –2;
    later increments retain their ordinary penalties.
    """
    if type(distance_ft) is not int or distance_ft < 0:
        raise ValueError("range distance must be a nonnegative integer")
    if type(range_increment_ft) is not int or range_increment_ft < 1:
        raise ValueError("range increment must be a positive integer")
    increments = max(1, (distance_ft + range_increment_ft - 1) // range_increment_ft)
    if target_is_hunted_prey and increments == 2:
        return 0
    return -2 * max(0, increments - 1)


def outwit_skill_modifier(
    edge: HunterEdge,
    *,
    target_is_hunted_prey: bool,
    statistic: str,
    action_id: str | None = None,
) -> Modifier | None:
    """Return Outwit's circumstance bonus for its named prey-facing checks."""
    if (
        edge is HunterEdge.OUTWIT
        and target_is_hunted_prey
        and (
            statistic in {"deception", "intimidation", "stealth"}
            or action_id == "recall_knowledge"
        )
    ):
        return Modifier(2, "circumstance", "Outwit against hunted prey")
    return None


def outwit_ac_modifier(
    edge: HunterEdge,
    *,
    attacker_is_hunted_prey: bool,
) -> Modifier | None:
    """Return Outwit's +1 circumstance AC when the current prey attacks."""
    if edge is HunterEdge.OUTWIT and attacker_is_hunted_prey:
        return Modifier(1, "circumstance", "Outwit against hunted prey")
    return None


def precision_damage_term(
    edge: HunterEdge,
    *,
    is_hunted_prey: bool,
    precision_used_round: int,
    current_round: int,
    damage_type: str,
) -> DamageTerm | None:
    """Describe Ranger Precision without consuming its once-per-round state.

    The caller appends this term only after a hit, then records the current
    round. Keeping the term separate preserves the precision tag and critical
    doubling when the shared damage pipeline applies grouped defenses.
    """
    if (
        edge is not HunterEdge.PRECISION
        or not is_hunted_prey
        or precision_used_round == current_round
    ):
        return None
    return DamageTerm(
        source="ranger_precision",
        damage_type=damage_type,
        dice=(8,),
        tags=frozenset({"precision"}),
        critical_mode="double",
    )


def handle_action(context: FamilyProcedureContext) -> FamilyProcedureResult | None:
    """Execute Ranger commands inside Encounter's existing transaction."""
    command = context.command
    if isinstance(command, HuntPrey):
        return _handle_hunt_prey(context, command)
    if isinstance(command, HuntedShot):
        from .paired_strikes import start_paired_strikes

        return start_paired_strikes(
            context,
            activity_id="ranger:hunted_shot",
            first_selection=command.strike,
            action_cost=1,
            is_flourish=True,
            same_target=True,
            ranged_only=True,
            require_hunted_prey=True,
            requires_unarmed_or_monk_weapon=False,
        )
    return None


def handle_choice(context: FamilyProcedureContext) -> FamilyProcedureResult | None:
    if context.pending is None or not (context.pending.procedure_id or "").startswith("ranger:"):
        return None
    from .paired_strikes import resume_paired_strikes

    return resume_paired_strikes(context)


def validate_pending(context: FamilyProcedureContext) -> None:
    pending = context.pending
    if pending is None or pending.procedure_id != "ranger:hunted_shot":
        raise ValueError("save has a pending choice outside the Ranger paired Strike procedure")
    from .paired_strikes import validate_pending as validate_paired_strikes

    validate_paired_strikes(context, activity_id="ranger:hunted_shot")


def _handle_hunt_prey(context: FamilyProcedureContext, command: HuntPrey) -> FamilyProcedureResult:
    actor = context.actor
    state = context.state
    definition = context.definition
    if "hunt_prey" not in definition.abilities:
        return FamilyProcedureResult(unsupported="Hunt Prey is not admitted for this creature.")
    if actor.actions_remaining < 1:
        return FamilyProcedureResult(rejection="Hunt Prey requires one action.")
    target = state.creatures.get(command.target_id)
    if target is None or target.actor_id == actor.actor_id or target.defeated:
        return FamilyProcedureResult(rejection="Hunt Prey requires another active creature.")
    # This encounter engine uses a bright, fully observed map. Hunt Prey has no
    # numeric range limit; tracking during exploration remains outside combat.
    actor.hunted_prey = HuntedPreyState(target.actor_id)
    actor.actions_remaining -= 1
    state.taking_cover.discard(actor.actor_id)
    events = [
        Event(
            "hunt_prey",
            actor.actor_id,
            target.actor_id,
            f"{actor.label} designates {target.label} as hunted prey (1 action, concentrate).",
        )
    ]
    events = context.encounter._complete_action(state, actor, events, dice=context.dice)
    return FamilyProcedureResult(events=tuple(events))
