"""Small Swashbuckler rules used by the staged first-play slice.

Sources checked 2026-09-16:

* https://2e.aonprd.com/Classes.aspx?ID=63 (Panache, Precise Strike,
  Stylish Combatant)
* https://2e.aonprd.com/Styles.aspx (Braggart style)
* https://2e.aonprd.com/Traits.aspx?ID=801 (Bravado)
* https://2e.aonprd.com/Actions.aspx?ID=2818 (Confident Finisher)
* https://2e.aonprd.com/Traits.aspx?ID=802 (Finisher)
"""

from __future__ import annotations

from dataclasses import dataclass

from .checks import DegreeOfSuccess, Modifier
from .damage import DamageComponent, DamageResult, DamageTerm
from .model import (
    AttackDefinition,
    CreatureDefinition,
    CreatureState,
    FamilyCommand,
    FamilyProcedureContext,
    FamilyProcedureResult,
)


@dataclass(frozen=True)
class ConfidentFinisher(FamilyCommand):
    """One-action Finisher that replaces Precise Strike damage."""

    family_id = "martial"
    target_id: str
    attack_id: str | None = None
    damage_type: str | None = None
    nonlethal: bool | None = None
    item_id: str | None = None


def handle_action(context: FamilyProcedureContext) -> FamilyProcedureResult | None:
    """Route the selected Swashbuckler finisher into normal Strike resolution."""

    if not isinstance(context.command, ConfidentFinisher):
        return None
    command = context.command
    events = context.encounter._start_strike(
        context.state,
        context.dice,
        context.actor,
        command.target_id,
        command.attack_id,
        command.item_id,
        command.damage_type,
        command.nonlethal,
        actions_cost=1,
        attack_count_cost=1,
        vicious_swing=False,
        use_intelligence=None,
        finisher=True,
    )
    return FamilyProcedureResult(events=tuple(events))


def handle_choice(context: FamilyProcedureContext) -> FamilyProcedureResult | None:
    """Resolve the success choice between full and failure-effect damage."""

    pending = context.pending
    command = context.choice
    if pending is None or command is None or pending.procedure_id != "swashbuckler:confident_finisher:damage":
        return None
    events = context.encounter._resolve_confident_finisher_choice(
        context.state, context.dice, pending, command
    )
    return FamilyProcedureResult(events=tuple(events))


def validate_pending(context: FamilyProcedureContext) -> None:
    pending = context.pending
    if pending is None or pending.procedure_id != "swashbuckler:confident_finisher:damage":
        raise ValueError("save has an unsupported Swashbuckler family choice")
    context.encounter._validate_confident_finisher_pending(context.state, pending)


def is_swashbuckler(definition: CreatureDefinition) -> bool:
    """Return whether a definition has the admitted Swashbuckler class."""

    return definition.class_name == "Swashbuckler"


def is_braggart(definition: CreatureDefinition) -> bool:
    """Return whether this Swashbuckler selected the Braggart style."""

    if not is_swashbuckler(definition):
        return False
    normalized = {
        value.strip().casefold().replace("_", " ")
        for value in definition.abilities + definition.feats
    }
    return "swashbuckler braggart" in normalized or "braggart" in normalized


def stylish_combatant_modifiers(definition: CreatureDefinition) -> tuple[Modifier, ...]:
    """The in-combat +1 circumstance bonus to a Swashbuckler bravado check."""

    if not is_swashbuckler(definition):
        return ()
    return (Modifier(1, "circumstance", "Stylish Combatant"),)


def apply_bravado_result(
    actor: CreatureState,
    definition: CreatureDefinition,
    degree: DegreeOfSuccess,
    *,
    current_end_count: int,
) -> str | None:
    """Apply Bravado's panache result and return a concise event label.

    A success or critical success lasts until encounter end. An ordinary
    failure lasts through the end of the actor's next turn. A critical
    failure does not remove panache already held.
    """

    if not is_braggart(definition):
        return None
    if degree in (DegreeOfSuccess.SUCCESS, DegreeOfSuccess.CRITICAL_SUCCESS):
        was_panache = actor.panache
        actor.panache = True
        actor.panache_expires_at_end = None
        return "panache_refreshed" if was_panache else "panache_gained"
    if degree is DegreeOfSuccess.FAILURE:
        if not actor.panache or actor.panache_expires_at_end is not None:
            return apply_temporary_panache(
                actor, current_end_count=current_end_count
            )
    return None


def apply_temporary_panache(
    actor: CreatureState, *, current_end_count: int
) -> str:
    """Grant the finite through-next-turn panache used by defensive feats."""
    if not actor.panache:
        actor.panache = True
        actor.panache_expires_at_end = current_end_count + 2
        return "panache_gained_temporarily"
    if actor.panache_expires_at_end is not None:
        actor.panache_expires_at_end = max(
            actor.panache_expires_at_end, current_end_count + 2
        )
        return "panache_extended"
    return "panache_preserved"


def precise_strike_damage_term(
    definition: CreatureDefinition,
    attack: AttackDefinition,
    *,
    finisher: bool = False,
    distance_ft: int | None = None,
) -> DamageTerm | None:
    """Return Precise Strike's precision term for an eligible attack.

    Confident Finisher replaces this ordinary +2 term with 2d6 precision.
    Flying Blade extends this only to a qualifying thrown Strike in its first
    range increment, so callers resolving a ranged attack provide distance.
    """

    if not is_swashbuckler(definition):
        return None
    if not ({"agile", "finesse"} & attack.traits):
        return None
    melee = "melee" in attack.traits
    flying_blade = "Flying Blade" in definition.feats
    thrown_first_increment = (
        flying_blade
        and "ranged" in attack.traits
        and "thrown" in attack.traits
        and attack.range_increment_ft is not None
        and distance_ft is not None
        and 0 < distance_ft <= attack.range_increment_ft
    )
    if not melee and not thrown_first_increment:
        return None
    return DamageTerm(
        source="swashbuckler_precise_strike",
        damage_type="precision",
        dice=(6, 6) if finisher else (),
        modifier=0 if finisher else 2,
        tags=frozenset({"precision"}),
        critical_mode="double",
    )


def confident_finisher_failure_damage(
    precision_damage: DamageResult, damage_type: str
) -> DamageResult:
    """Convert one rolled 2d6 Precise Strike term to the Finisher failure effect."""

    if (
        not isinstance(precision_damage, DamageResult)
        or len(precision_damage.components) != 1
        or not isinstance(damage_type, str)
    ):
        raise ValueError("Confident Finisher failure damage needs one precision result and a weapon type")
    component = precision_damage.components[0]
    if component.dice != (6, 6) or not component.rolls:
        raise ValueError("Confident Finisher failure damage needs a rolled 2d6 term")
    amount = sum(component.rolls) // 2
    failure = DamageComponent(
        source="confident_finisher_failure",
        damage_type=damage_type,
        dice_sides=6,
        rolls=component.rolls,
        modifier=0,
        amount=amount,
        tags=frozenset({"precision"}),
        critical_mode="unchanged",
        dice=component.dice,
    )
    return DamageResult((failure,), amount, 1, amount)


def effective_speed_ft(actor: CreatureState, definition: CreatureDefinition, conditions=()) -> int:
    """Return land Speed after same-type status bonuses and penalties."""

    status_bonuses = [effect.value for effect in conditions if effect.kind == "speed_bonus"]
    if is_swashbuckler(definition) and actor.panache:
        status_bonuses.append(5)
    base = definition.land_speed_ft + max(status_bonuses, default=0)
    penalties = [effect.value for effect in conditions if effect.kind == "speed_penalty"]
    return max(0, base - (max(penalties) if penalties else 0))


def clear_panache(actor: CreatureState) -> None:
    """Remove the encounter-scoped panache state."""

    actor.panache = False
    actor.panache_expires_at_end = None
