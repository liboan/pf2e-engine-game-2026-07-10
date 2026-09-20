"""Named common skill-action checks and their local encounter handlers.

The pure resolution functions below accept a caller-owned die roller and
explicit modifiers. The family handlers apply the returned, named outcomes to
the encounter draft; they never call ``Encounter.execute`` recursively.

Initial sources (checked 2026-09-15):

* https://2e.aonprd.com/Actions.aspx?ID=2382 (Trip)
* https://2e.aonprd.com/Actions.aspx?ID=2376 (Grapple)
* https://2e.aonprd.com/Rules.aspx?ID=2343 (Escape)
* https://2e.aonprd.com/Actions.aspx?ID=2395 (Demoralize)
* https://2e.aonprd.com/Traits.aspx?ID=619 (Grapple weapon trait)
* https://2e.aonprd.com/Feats.aspx?ID=5162 (Intimidating Glare)
* https://2e.aonprd.com/Actions.aspx?ID=2390 (Feint)
* https://2e.aonprd.com/Rackets.aspx (Rogue Scoundrel)
* https://2e.aonprd.com/Feats.aspx?ID=5121 (Assurance)
* https://paizo.com/pathfinder/faq (current official errata)
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from enum import StrEnum
from typing import Callable, ClassVar

from .checks import CheckResult, DegreeOfSuccess, Modifier, combine_modifiers, multiple_attack_penalty, resolve_assurance_check, resolve_check
from .damage import DamageResult, DamageTerm, roll_damage_terms
from .content import get_definition
from .model import (
    ActionContinuation,
    ActiveConditionEffect,
    ActiveSpellEffect,
    ChoiceOption,
    Choose,
    EffectExpiration,
    Event,
    FamilyCommand,
    FamilyProcedureContext,
    FamilyProcedureResult,
    Position,
    SavedCheckContext,
)
from .conditions import CheckContext, ConditionValue
from .skill_content import (
    DEMORALIZE,
    ESCAPE,
    FEINT,
    GRAPPLE,
    TRIP,
    TUMBLE_THROUGH,
    maneuver_target_size_allowed,
)
from .space import grid_distance_feet, in_bounds, is_adjacent, step_cost
from .swashbuckler import (
    apply_bravado_result,
    effective_speed_ft,
    is_braggart,
    is_swashbuckler,
    stylish_combatant_modifiers,
)


Roll = Callable[[int], int]


@dataclass(frozen=True)
class TripResolution:
    check: CheckResult
    target_falls_prone: bool
    user_falls_prone: bool
    critical_damage: DamageResult | None


@dataclass(frozen=True)
class GrappleResolution:
    check: CheckResult
    target_condition: str | None
    release_user_grapple: bool
    offer_target_response: bool


@dataclass(frozen=True)
class EscapeResolution:
    check: CheckResult
    free_of_selected_impediment: bool
    remove_grabbed_immobilized_restrained: bool
    followup_stride_ft: int
    retry_blocked_until_next_turn: bool


@dataclass(frozen=True)
class DemoralizeResolution:
    check: CheckResult
    frightened_value: int
    apply_frightened: bool
    target_immune_for_seconds: int
    traits: frozenset[str]


class FeintAttackScope(StrEnum):
    """Attacker-relative attack scope for one Feint exposure."""

    NEXT_MELEE_ATTACK = "next_melee_attack"
    NAMED_ATTACKER_MELEE = "named_attacker_melee"
    ANY_MELEE_ATTACKER = "any_melee_attacker"


@dataclass(frozen=True)
class FeintOffGuardEffect:
    """A typed, source-relative Feint exposure, never a global condition.

    ``target_actor_id`` is the creature whose AC is affected. A named
    ``eligible_attacker_id`` limits the exposure to that attacker's melee
    attacks; ``None`` is used only for Scoundrel's critical-success benefit to
    every melee attacker. A normal successful Feint consumes its exposure on
    that attacker's next eligible melee attack attempt, hit or miss.
    """

    effect_id: str
    source_actor_id: str
    target_actor_id: str
    eligible_attacker_id: str | None
    scope: FeintAttackScope
    expiration: EffectExpiration
    consume_on_next_attack: bool

    def __post_init__(self) -> None:
        if not self.effect_id or not self.source_actor_id or not self.target_actor_id:
            raise ValueError("Feint exposure needs an effect ID and source/target actors")
        if self.eligible_attacker_id is not None and not self.eligible_attacker_id:
            raise ValueError("eligible_attacker_id must be non-empty text or None")
        if not isinstance(self.scope, FeintAttackScope):
            raise ValueError("Feint exposure needs a supported attack scope")
        if not isinstance(self.expiration, EffectExpiration) or self.expiration.boundary != "end":
            raise ValueError("Feint exposure needs an actor-relative end boundary")
        if self.expiration.anchor_actor_id != self.source_actor_id or self.expiration.occurrence < 1:
            raise ValueError("Feint exposure expiry must be anchored to its source's turn end")
        if type(self.consume_on_next_attack) is not bool:
            raise ValueError("consume_on_next_attack must be a boolean")
        if (self.scope is FeintAttackScope.ANY_MELEE_ATTACKER) != (self.eligible_attacker_id is None):
            raise ValueError("only an any-attacker Feint exposure may omit its attacker ID")
        if self.consume_on_next_attack != (self.scope is FeintAttackScope.NEXT_MELEE_ATTACK):
            raise ValueError("only a next-melee-attack exposure is consumed on attack")


@dataclass(frozen=True)
class OverextendingFeintEffect:
    """Rogue's typed attack penalty from Overextending Feint."""

    effect_id: str
    source_actor_id: str
    target_actor_id: str
    expiration: EffectExpiration
    all_attacks: bool

    def __post_init__(self) -> None:
        if not self.effect_id or not self.source_actor_id or not self.target_actor_id:
            raise ValueError("Overextending Feint needs stable source and target actors")
        if self.source_actor_id == self.target_actor_id:
            raise ValueError("Overextending Feint needs distinct actors")
        if self.expiration.anchor_actor_id != self.target_actor_id or self.expiration.boundary != "end":
            raise ValueError("Overextending Feint expires at the feinted target's turn end")
        if self.expiration.occurrence < 1 or type(self.all_attacks) is not bool:
            raise ValueError("Overextending Feint has invalid expiry or scope")


def overextending_feint_penalty(
    effects: tuple[OverextendingFeintEffect, ...],
    *, attacker_id: str,
    target_id: str,
    actor_end_counts: dict[str, int],
) -> int:
    """Return the -2 penalty when the attacker is the feinted creature."""

    for effect in effects:
        if (
            effect.source_actor_id == target_id
            and effect.target_actor_id == attacker_id
            and actor_end_counts.get(attacker_id, 0) < effect.expiration.occurrence
        ):
            return -2
    return 0


def consume_overextending_feint_on_attack(
    effects: tuple[OverextendingFeintEffect, ...],
    *, attacker_id: str, target_id: str, actor_end_counts: dict[str, int],
) -> tuple[OverextendingFeintEffect, ...]:
    """Consume a successful (non-critical) Overextending Feint on one attack."""

    consumed = {
        effect.effect_id
        for effect in effects
        if (
            not effect.all_attacks
            and effect.source_actor_id == target_id
            and effect.target_actor_id == attacker_id
            and actor_end_counts.get(attacker_id, 0) < effect.expiration.occurrence
        )
    }
    return tuple(effect for effect in effects if effect.effect_id not in consumed)


@dataclass(frozen=True)
class FeintResolution:
    check: CheckResult
    off_guard_effects: tuple[FeintOffGuardEffect, ...]
    can_free_step: bool


def feint_outcome_from_check(
    check: CheckResult,
    *,
    feinter_id: str,
    target_id: str,
    effect_id: str,
    current_feinter_end_count: int,
    scoundrel: bool,
    wielding_agile_or_finesse_melee_weapon: bool,
) -> FeintResolution:
    """Build the four-degree Feint result and exact actor-relative exposure."""

    if not isinstance(check, CheckResult):
        raise ValueError("Feint needs its authoritative saved check result")
    if not feinter_id or not target_id or feinter_id == target_id or not effect_id:
        raise ValueError("Feint needs distinct actors and a stable effect ID")
    if type(current_feinter_end_count) is not int or current_feinter_end_count < 0:
        raise ValueError("current_feinter_end_count must be non-negative")
    if type(scoundrel) is not bool or type(wielding_agile_or_finesse_melee_weapon) is not bool:
        raise ValueError("Scoundrel and weapon facts must be booleans")

    from .rogue import OffGuardExpiry, OffGuardScope, scoundrel_feint_benefits

    benefits = scoundrel_feint_benefits(
        check.degree,
        wielding_agile_or_finesse_melee_weapon=wielding_agile_or_finesse_melee_weapon,
    )
    can_free_step = scoundrel and benefits.can_free_step
    if check.degree is DegreeOfSuccess.CRITICAL_FAILURE:
        effects = (
            FeintOffGuardEffect(
                effect_id,
                feinter_id,
                feinter_id,
                target_id,
                FeintAttackScope.NAMED_ATTACKER_MELEE,
                EffectExpiration(feinter_id, "end", current_feinter_end_count + 2),
                False,
            ),
        )
    elif check.degree is DegreeOfSuccess.FAILURE:
        effects = ()
    elif scoundrel:
        grant = benefits.off_guard
        if grant is None:
            raise ValueError("successful Scoundrel Feint did not produce its racket benefit")
        if grant.scope is OffGuardScope.ALL_MELEE_ATTACKS:
            scope = FeintAttackScope.ANY_MELEE_ATTACKER
            eligible_attacker_id = None
        elif grant.scope is OffGuardScope.ROGUE_MELEE_ATTACKS:
            scope = FeintAttackScope.NAMED_ATTACKER_MELEE
            eligible_attacker_id = feinter_id
        else:
            raise ValueError("Scoundrel Feint returned an unsupported off-guard scope")
        if grant.expiry is not OffGuardExpiry.ROGUE_NEXT_TURN_END:
            raise ValueError("Scoundrel Feint must expire at the end of the Rogue's next turn")
        expiry_count = current_feinter_end_count + 2
        effects = (
            FeintOffGuardEffect(
                effect_id,
                feinter_id,
                target_id,
                eligible_attacker_id,
                scope,
                EffectExpiration(feinter_id, "end", expiry_count),
                False,
            ),
        )
    elif check.degree is DegreeOfSuccess.SUCCESS:
        effects = (
            FeintOffGuardEffect(
                effect_id,
                feinter_id,
                target_id,
                feinter_id,
                FeintAttackScope.NEXT_MELEE_ATTACK,
                EffectExpiration(feinter_id, "end", current_feinter_end_count + 1),
                True,
            ),
        )
    else:
        effects = (
            FeintOffGuardEffect(
                effect_id,
                feinter_id,
                target_id,
                feinter_id,
                FeintAttackScope.NAMED_ATTACKER_MELEE,
                EffectExpiration(feinter_id, "end", current_feinter_end_count + 2),
                False,
            ),
        )
    return FeintResolution(check, effects, can_free_step)


def feint_off_guard_applies(
    effects: tuple[FeintOffGuardEffect, ...],
    *,
    attacker_id: str,
    target_id: str,
    attack_traits: frozenset[str],
    actor_end_counts: dict[str, int],
) -> bool:
    """Whether one saved melee attack sees this defender as off-guard."""

    if not isinstance(effects, tuple) or any(not isinstance(item, FeintOffGuardEffect) for item in effects):
        raise TypeError("effects must be a tuple of typed Feint exposures")
    if not attacker_id or not target_id or not isinstance(attack_traits, frozenset):
        raise ValueError("Feint AC queries need attacker, target, and attack traits")
    if "melee" not in attack_traits or "ranged" in attack_traits:
        return False
    return any(
        effect.target_actor_id == target_id
        and _feint_effect_active(effect, actor_end_counts)
        and (
            effect.scope is FeintAttackScope.ANY_MELEE_ATTACKER
            or effect.eligible_attacker_id == attacker_id
        )
        for effect in effects
    )


def consume_feint_off_guard_on_attack(
    effects: tuple[FeintOffGuardEffect, ...],
    *,
    attacker_id: str,
    target_id: str,
    attack_traits: frozenset[str],
    actor_end_counts: dict[str, int],
) -> tuple[FeintOffGuardEffect, ...]:
    """Consume matching one-attack exposures when a melee Strike is prepared."""

    if not isinstance(effects, tuple) or any(not isinstance(item, FeintOffGuardEffect) for item in effects):
        raise TypeError("effects must be a tuple of typed Feint exposures")
    if not attacker_id or not target_id or not isinstance(attack_traits, frozenset):
        raise ValueError("Feint attack consumption needs attacker, target, and attack traits")
    consumed = {
        effect.effect_id
        for effect in effects
        if effect.scope is FeintAttackScope.NEXT_MELEE_ATTACK
        and effect.target_actor_id == target_id
        and effect.eligible_attacker_id == attacker_id
        and _feint_effect_active(effect, actor_end_counts)
        and "melee" in attack_traits
        and "ranged" not in attack_traits
    }
    return tuple(effect for effect in effects if effect.effect_id not in consumed)


def _feint_effect_active(effect: FeintOffGuardEffect, actor_end_counts: dict[str, int]) -> bool:
    if not isinstance(actor_end_counts, dict):
        raise TypeError("actor_end_counts must be an actor-to-count mapping")
    return actor_end_counts.get(effect.expiration.anchor_actor_id, 0) < effect.expiration.occurrence


@dataclass(frozen=True)
class Trip(FamilyCommand):
    family_id: ClassVar[str] = "martial"
    target_id: str
    maneuver_item_id: str | None = None
    use_assurance: bool = False

    def __post_init__(self) -> None:
        if type(self.use_assurance) is not bool:
            raise TypeError("use_assurance must be a boolean")


@dataclass(frozen=True)
class Grapple(FamilyCommand):
    family_id: ClassVar[str] = "martial"
    target_id: str
    maneuver_item_id: str | None = None
    use_assurance: bool = False

    def __post_init__(self) -> None:
        if type(self.use_assurance) is not bool:
            raise TypeError("use_assurance must be a boolean")


@dataclass(frozen=True)
class QuickJump(FamilyCommand):
    """Use the selected Quick Jump feat for a one-action horizontal Long Jump."""

    family_id: ClassVar[str] = "martial"
    path: tuple[Position, ...]


@dataclass(frozen=True)
class Escape(FamilyCommand):
    family_id: ClassVar[str] = "martial"
    impediment_id: str
    check_method: str
    attack_id: str | None = None
    use_assurance: bool = False

    def __post_init__(self) -> None:
        if type(self.use_assurance) is not bool:
            raise TypeError("use_assurance must be a boolean")


def assurance_athletics_available(definition: object) -> bool:
    """Whether a creature can select the fixed Assurance (Athletics) intent.

    This reports only the actor-side prerequisites. Action target, DC, and
    impediment legality remain checks performed by the corresponding family
    procedure after the terminal has collected the engine-listed inputs.
    """

    if "Assurance (Athletics)" not in getattr(definition, "feats", ()):
        return False
    return any(
        statistic == "athletics" and rank in {"trained", "expert", "master", "legendary"}
        for statistic, rank, _modifier in getattr(definition, "skills", ())
    )


@dataclass(frozen=True)
class Demoralize(FamilyCommand):
    family_id: ClassVar[str] = "martial"
    target_id: str
    spoken_language: str | None = None
    use_intimidating_glare: bool = False
    youre_next_reaction: bool = False


@dataclass(frozen=True)
class Feint(FamilyCommand):
    family_id: ClassVar[str] = "martial"
    target_id: str
    use_overextending: bool = False


@dataclass(frozen=True)
class TumbleThrough(FamilyCommand):
    """One-action Acrobatics movement through a supported enemy square."""

    family_id: ClassVar[str] = "martial"
    path: tuple[Position, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.path, tuple) or not self.path:
            raise TypeError("Tumble Through needs a nonempty tuple of path squares")
        if any(not isinstance(point, Position) for point in self.path):
            raise TypeError("Tumble Through path squares must be Position records")


def _resolve_skill_check(
    die: int,
    base_modifier: int,
    dc: int,
    *,
    statistic: str,
    attacks_already_made: int,
    attack_trait: bool,
    modifiers: tuple[Modifier, ...] = (),
    traits: frozenset[str] = frozenset(),
) -> CheckResult:
    """Resolve a named skill check from a saved modifier and typed context."""

    if type(base_modifier) is not int or type(dc) is not int or dc < 0:
        raise ValueError("skill checks need integer modifiers and a non-negative DC")
    if not isinstance(statistic, str) or not statistic:
        raise ValueError("a skill check needs a statistic name")
    if not isinstance(modifiers, tuple) or any(not isinstance(item, Modifier) for item in modifiers):
        raise TypeError("modifiers must be a tuple of Modifier records")
    if not isinstance(traits, frozenset) or any(not isinstance(item, str) or not item for item in traits):
        raise TypeError("traits must be a frozenset of non-empty strings")

    map_penalty = multiple_attack_penalty(attacks_already_made) if attack_trait else 0
    breakdown = (
        Modifier(base_modifier, "untyped", f"{statistic} skill modifier"),
        *modifiers,
        *((Modifier(map_penalty, "untyped", "multiple attack penalty"),) if map_penalty else ()),
    )
    modifier = base_modifier + combine_modifiers(modifiers) + map_penalty
    check = resolve_check(
        die,
        modifier,
        dc,
        map_penalty=map_penalty,
        traits=traits | ({"attack"} if attack_trait else set()),
    )
    return replace(check, modifier_breakdown=breakdown)


def resolve_trip(
    *,
    roll: Roll,
    user_id: str,
    target_id: str,
    modifier: int,
    dc: int,
    attacks_already_made: int,
    modifiers: tuple[Modifier, ...] = (),
) -> TripResolution:
    """Resolve Trip's degree effects; legality and state mutation stay in core."""

    if not callable(roll) or not user_id or not target_id or user_id == target_id:
        raise ValueError("Trip needs a roller and distinct user and target IDs")
    check = _resolve_skill_check(
        roll(20),
        modifier,
        dc,
        statistic="athletics",
        attacks_already_made=attacks_already_made,
        attack_trait=True,
        modifiers=modifiers,
        traits=frozenset(),
    )
    return trip_outcome_from_check(check, roll)


def trip_outcome_from_check(check: CheckResult, roll: Roll) -> TripResolution:
    """Project Trip's degree without making another check."""

    critical = check.degree is DegreeOfSuccess.CRITICAL_SUCCESS
    damage = roll_damage_terms((DamageTerm("trip_critical", "bludgeoning", (6,)),), roll) if critical else None
    return TripResolution(
        check=check,
        target_falls_prone=check.degree >= DegreeOfSuccess.SUCCESS,
        user_falls_prone=check.degree is DegreeOfSuccess.CRITICAL_FAILURE,
        critical_damage=damage,
    )


def resolve_grapple(
    *,
    roll: Roll,
    user_id: str,
    target_id: str,
    modifier: int,
    dc: int,
    attacks_already_made: int,
    already_holding_target: bool,
    modifiers: tuple[Modifier, ...] = (),
) -> GrappleResolution:
    """Resolve Grapple's degree effects without mutating retained conditions."""

    if not callable(roll) or not user_id or not target_id or user_id == target_id:
        raise ValueError("Grapple needs a roller and distinct user and target IDs")
    if type(already_holding_target) is not bool:
        raise TypeError("already_holding_target must be a bool")
    check = _resolve_skill_check(
        roll(20),
        modifier,
        dc,
        statistic="athletics",
        attacks_already_made=attacks_already_made,
        attack_trait=True,
        modifiers=modifiers,
        traits=frozenset(),
    )
    return grapple_outcome_from_check(check, already_holding_target=already_holding_target)


def grapple_outcome_from_check(check: CheckResult, *, already_holding_target: bool) -> GrappleResolution:
    """Project Grapple's degree without changing condition state."""

    if check.degree is DegreeOfSuccess.CRITICAL_SUCCESS:
        condition = "restrained"
    elif check.degree is DegreeOfSuccess.SUCCESS:
        condition = "grabbed"
    else:
        condition = None
    failed = check.degree <= DegreeOfSuccess.FAILURE
    return GrappleResolution(
        check=check,
        target_condition=condition,
        release_user_grapple=already_holding_target and failed,
        offer_target_response=check.degree is DegreeOfSuccess.CRITICAL_FAILURE,
    )


def resolve_escape(
    *,
    roll: Roll,
    user_id: str,
    impediment_id: str,
    modifier: int,
    dc: int,
    attacks_already_made: int,
    modifiers: tuple[Modifier, ...] = (),
    check_method: str,
) -> EscapeResolution:
    """Resolve Escape against exactly one selected effect or impediment."""

    if not callable(roll) or not user_id or not impediment_id:
        raise ValueError("Escape needs a roller, a user ID, and a selected impediment ID")
    if check_method not in {"unarmed_attack", "acrobatics", "athletics"}:
        raise ValueError("Escape check_method must be unarmed_attack, acrobatics, or athletics")
    check = _resolve_skill_check(
        roll(20),
        modifier,
        dc,
        statistic=check_method,
        attacks_already_made=attacks_already_made,
        attack_trait=True,
        modifiers=modifiers,
        traits=frozenset() if check_method != "unarmed_attack" else frozenset({"unarmed"}),
    )
    return escape_outcome_from_check(check)


def escape_outcome_from_check(check: CheckResult) -> EscapeResolution:
    """Project Escape's degree without removing any retained condition."""

    critical = check.degree is DegreeOfSuccess.CRITICAL_SUCCESS
    freed = check.degree >= DegreeOfSuccess.SUCCESS
    return EscapeResolution(
        check=check,
        free_of_selected_impediment=freed,
        remove_grabbed_immobilized_restrained=freed,
        followup_stride_ft=5 if critical else 0,
        retry_blocked_until_next_turn=check.degree is DegreeOfSuccess.CRITICAL_FAILURE,
    )


def resolve_demoralize(
    *,
    roll: Roll,
    user_id: str,
    target_id: str,
    modifier: int,
    dc: int,
    speech_understood: bool,
    use_intimidating_glare: bool,
    target_frightened_immune: bool = False,
    modifiers: tuple[Modifier, ...] = (),
) -> DemoralizeResolution:
    """Resolve Demoralize, preserving its language penalty and immunity clock."""

    if not callable(roll) or not user_id or not target_id or user_id == target_id:
        raise ValueError("Demoralize needs a roller and distinct user and target IDs")
    if type(speech_understood) is not bool or type(use_intimidating_glare) is not bool:
        raise TypeError("Demoralize language and glare facts must be booleans")
    if type(target_frightened_immune) is not bool:
        raise TypeError("target_frightened_immune must be a bool")

    action_modifiers = modifiers
    if not speech_understood and not use_intimidating_glare:
        action_modifiers += (Modifier(-4, "circumstance", "Demoralize language barrier"),)
    traits = frozenset({"concentrate", "emotion", "fear", "mental"})
    if use_intimidating_glare:
        traits |= {"visual"}
    else:
        traits |= {"auditory"}
    check = _resolve_skill_check(
        roll(20),
        modifier,
        dc,
        statistic="intimidation",
        attacks_already_made=0,
        attack_trait=False,
        modifiers=action_modifiers,
        traits=traits,
    )
    return demoralize_outcome_from_check(check, use_intimidating_glare=use_intimidating_glare,
                                         target_frightened_immune=target_frightened_immune)


def demoralize_outcome_from_check(
    check: CheckResult,
    *,
    use_intimidating_glare: bool,
    target_frightened_immune: bool = False,
) -> DemoralizeResolution:
    """Project Demoralize's effects after its authoritative check is rolled."""

    frightened = (
        2
        if check.degree is DegreeOfSuccess.CRITICAL_SUCCESS
        else 1
        if check.degree is DegreeOfSuccess.SUCCESS
        else 0
    )
    return DemoralizeResolution(
        check=check,
        frightened_value=frightened,
        apply_frightened=frightened > 0 and not target_frightened_immune,
        target_immune_for_seconds=600,
        traits=(check.traits and frozenset(check.traits)) or frozenset(),
    )


def _definition(actor):
    return get_definition(actor.definition_id)


def _save_dc(context: FamilyProcedureContext, actor, statistic: str) -> int:
    """Return one creature's current defense DC, including condition penalties."""

    return context.skill_dc(actor.actor_id, statistic)


def _skill_dc(context: FamilyProcedureContext, actor, statistic: str, attribute: str) -> int:
    """Return a creature's current skill DC, including DC-affecting conditions."""

    # Core owns the printed statistic and currently applicable condition
    # modifiers. Keep the attribute explicit at the rule call site so the
    # selected source statistic remains visible here.
    if attribute != "strength" or statistic != "athletics":
        raise ValueError("this skill DC helper only admits Athletics (Strength)")
    return context.skill_dc(actor.actor_id, statistic)


def _active_effect(context: FamilyProcedureContext, effect_id: str) -> ActiveConditionEffect | ActiveSpellEffect | None:
    return next(
        (
            effect for effect in (*context.state.condition_effects, *context.state.active_effects)
            if effect.effect_id == effect_id
        ),
        None,
    )


def _source_held_effects(context: FamilyProcedureContext, source_id: str, target_id: str) -> tuple[ActiveConditionEffect, ...]:
    return tuple(
        effect for effect in context.state.condition_effects
        if effect.source_actor_id == source_id and effect.target_actor_id == target_id
        and effect.kind in {"grabbed", "restrained"}
    )


def _expiry_after_actor_end(context: FamilyProcedureContext, actor_id: str, *, turns: int = 1) -> EffectExpiration:
    return EffectExpiration(
        anchor_actor_id=actor_id,
        boundary="end",
        occurrence=context.state.actor_end_counts.get(actor_id, 0) + turns,
    )


def add_timed_condition_effect(
    context: FamilyProcedureContext,
    *,
    effect_id: str,
    kind: str,
    source_id: str,
    target_id: str,
    value: int,
    expiration: EffectExpiration,
    dc: int | None = None,
) -> None:
    """Replace one source-owned, actor-relative condition effect.

    Demoralize and the martial Intimidating Strike family both create a
    frightened condition with an explicit source and end-of-turn boundary.
    Keeping the small state mutation here avoids duplicating the replacement
    and persistence-safe ID rules while leaving each action's trigger and
    immunity contract in its owning module.
    """
    context.state.condition_effects = [effect for effect in context.state.condition_effects if effect.effect_id != effect_id]
    context.add_condition_effect(
        effect_id, kind, source_id, target_id, value, expiration=expiration, dc=dc,
    )


def _maneuver_weapon(context: FamilyProcedureContext, item_id: str | None, action_trait: str):
    """Resolve a held weapon profile by exact item id and printed action trait."""

    if item_id is None:
        return None
    if item_id not in context.actor.held_items:
        raise ValueError(f"{item_id!r} is not currently held")
    profiles = tuple(
        attack for attack in context.definition.attacks
        if attack.item_id == item_id and "melee" in attack.traits
    )
    if not profiles:
        raise NotImplementedError(f"No admitted melee profile identifies held item {item_id!r}")
    profile = next((attack for attack in profiles if action_trait in attack.traits), None)
    if profile is None:
        raise ValueError(f"{item_id!r} does not have the {action_trait} trait")
    return profile


def _target(context: FamilyProcedureContext, target_id: str):
    actor = context.state.creatures.get(target_id)
    if actor is None or actor.defeated or actor.dead:
        raise ValueError("target must be a present creature")
    if actor.actor_id == context.actor.actor_id:
        raise ValueError("this action requires another creature")
    return actor


def _tumble_target(context: FamilyProcedureContext, path: tuple[Position, ...]):
    """Find the single supported enemy square crossed by a Tumble path."""

    if not isinstance(path, tuple) or not path:
        raise ValueError("Tumble Through requires a nonempty path")
    current = context.actor.position
    target = None
    for point in path:
        if not isinstance(point, Position) or not in_bounds(
            point, context.state.map_width, context.state.map_height
        ):
            raise ValueError("Tumble Through path leaves the supported map")
        try:
            step_cost(current, point, context.actor.diagonals_this_turn)
        except ValueError as error:
            raise ValueError("Tumble Through path must visit adjacent grid squares") from error
        occupant = context.encounter._occupant_at(
            context.state, point, except_actor=context.actor.actor_id
        )
        if occupant is not None:
            if occupant.team == context.actor.team and not occupant.defeated and not occupant.unconscious and not occupant.dead:
                raise ValueError("Tumble Through cannot enter an allied creature's space")
            if occupant.team != context.actor.team and not occupant.defeated and not occupant.dead:
                if target is not None and target.actor_id != occupant.actor_id:
                    raise NotImplementedError("Tumble Through across multiple enemy spaces is not admitted")
                target = occupant
            elif not context.encounter._can_share_with_body(context.actor, occupant):
                raise ValueError("Tumble Through path is blocked by an occupied square")
        current = point
    if target is None:
        raise ValueError("Tumble Through requires a path through an active enemy space")
    target_index = next(
        index for index, point in enumerate(path)
        if point == target.position
    )
    if target_index >= len(path) - 1:
        # The source gives the failure result when Speed cannot carry the
        # creature all the way through the enemy's space. Ending on the
        # enemy square is the supported one-square form of that boundary.
        raise ValueError("Tumble Through path must continue beyond the enemy's space")
    if _definition(target).size not in {"tiny", "small", "medium"} or _definition(context.actor).size not in {"tiny", "small", "medium"}:
        raise NotImplementedError("Tumble Through currently admits supported one-square Tiny, Small, or Medium creatures only")
    return target


def _tumble_path_cost(context: FamilyProcedureContext, path: tuple[Position, ...], target) -> int:
    distance = 0
    diagonals = context.actor.diagonals_this_turn
    current = context.actor.position
    for point in path:
        cost, diagonal_count = step_cost(current, point, diagonals)
        if point == target.position:
            cost *= 2
        distance += cost
        diagonals += diagonal_count
        current = point
    return distance


def _tumble_remaining_path(context: FamilyProcedureContext, path: tuple[Position, ...]) -> tuple[Position, ...]:
    """Return the unperformed suffix after a clear lead-in has moved."""

    try:
        current_index = path.index(context.actor.position)
    except ValueError:
        return path
    return path[current_index + 1:]


def _check_maneuver(
    context: FamilyProcedureContext,
    target,
    action_trait: str,
    item_id: str | None,
    *,
    already_holding_target: bool = False,
):
    profile = _maneuver_weapon(context, item_id, action_trait)
    source = _definition(context.actor)
    target_definition = _definition(target)
    if not maneuver_target_size_allowed(source.size, target_definition.size):
        raise ValueError("target is too large for this maneuver")
    hands = 2 - context.free_hands
    if profile is None and context.free_hands < 1 and not already_holding_target:
        raise ValueError(f"{action_trait.title()} requires a free hand or a weapon with the {action_trait} trait")
    if profile is not None and profile.hands_required > hands:
        raise ValueError("The selected weapon is not wielded in its required number of hands.")
    if profile is not None and profile.hands_required > 1 and context.actor.held_items != [item_id]:
        raise ValueError("The selected two-handed weapon must occupy both hands for this maneuver.")
    reach_ft = profile.reach_ft if profile is not None else 5
    if grid_distance_feet(context.actor.position, target.position) > reach_ft:
        raise ValueError(f"target is outside {reach_ft}-foot reach")
    if context.actor.must_leave_occupied:
        raise ValueError("Move out of the occupied ally's space before taking another action.")
    return profile


def _conditions_for_target(context: FamilyProcedureContext, target) -> tuple[ConditionValue, ...]:
    return context.encounter._conditions_for_actor(context.state, target)


def _event_check(action: str, actor, target, check: CheckResult) -> Event:
    if check.method == "assurance":
        text = (
            f"{actor.label} uses Assurance (Athletics) for {action.replace('_', ' ').title()} "
            f"against {target.label}: {check.degree.label()} ({check.total} vs DC {check.dc})."
        )
    else:
        text = (
            f"{actor.label} attempts {action.replace('_', ' ').title()} against {target.label}: "
            f"{check.degree.label()} ({check.total} vs DC {check.dc})."
        )
    return Event(
        f"{action}_check",
        actor.actor_id,
        target.actor_id,
        text,
        check=check,
    )


def _action_id(command: FamilyCommand) -> str:
    if isinstance(command, Trip):
        return "trip"
    if isinstance(command, Grapple):
        return "grapple"
    if isinstance(command, Escape):
        return "escape"
    if isinstance(command, Demoralize):
        return "demoralize"
    if isinstance(command, Feint):
        return "feint"
    if isinstance(command, TumbleThrough):
        return "tumble_through"
    if isinstance(command, QuickJump):
        return "quick_jump"
    raise TypeError("unknown skill-action command")


def _check_statistic(command: FamilyCommand) -> str:
    if isinstance(command, (Trip, Grapple)):
        return "athletics"
    if isinstance(command, Escape):
        return command.check_method
    if isinstance(command, Demoralize):
        return "intimidation"
    if isinstance(command, Feint):
        return "deception"
    if isinstance(command, TumbleThrough):
        return "acrobatics"
    if isinstance(command, QuickJump):
        return "athletics"
    raise TypeError("unknown skill-action command")


def _command_target_id(command: FamilyCommand) -> str | None:
    if isinstance(command, (Trip, Grapple, Demoralize, Feint)):
        return command.target_id
    return None


def _assurance_proficiency_bonus(context: FamilyProcedureContext, statistic: str) -> int:
    """Return the trained Athletics proficiency bonus for Assurance.

    The feat's fixed result is 10 plus proficiency only; the saved skill
    modifier, ability score, item, condition, and MAP values are not inputs.
    """

    if statistic != "athletics":
        raise ValueError("Assurance (Athletics) can only be used with an Athletics check.")
    if "Assurance (Athletics)" not in context.definition.feats:
        raise ValueError("This actor does not have Assurance (Athletics).")
    ranks = {
        "trained": 2,
        "expert": 4,
        "master": 6,
        "legendary": 8,
    }
    rank = next(
        (rank for name, rank, _modifier in context.definition.skills if name == "athletics"),
        None,
    )
    if rank not in ranks:
        raise ValueError("Assurance (Athletics) requires trained Athletics.")
    level = context.definition.level
    if type(level) is not int or level < 0:
        raise ValueError("Assurance requires a valid character level.")
    return level + ranks[rank]


def _unarmed_escape_profile(context: FamilyProcedureContext, command: Escape):
    profiles = tuple(
        attack for attack in context.definition.attacks
        if "unarmed" in attack.traits and context.encounter._attack_usable(context.state, context.actor, attack)
    )
    if not profiles:
        raise ValueError("Escape with an unarmed attack requires an admitted unarmed attack profile.")
    if command.attack_id is None:
        if len(profiles) != 1:
            raise ValueError("Choose an unarmed attack profile for Escape.")
        return profiles[0]
    selected = tuple(attack for attack in profiles if attack.attack_id == command.attack_id)
    if len(selected) != 1:
        raise ValueError(f"{command.attack_id!r} is not an admitted unarmed attack profile.")
    return selected[0]


def _skill_continuation(
    context: FamilyProcedureContext,
    command: FamilyCommand,
    saved: SavedCheckContext,
    stage: str,
    *,
    targeting_failed: bool = False,
) -> ActionContinuation:
    """Build the saved family continuation shared by targeting and skill choices."""

    action_id = _action_id(command)
    attack_count = 0
    attack_penalty = 0
    if "attack" in saved.context.traits:
        attack_count = (
            context.actor.strikes_this_turn
            if saved.attack_count_committed
            else context.actor.strikes_this_turn + 1
        )
        attack_penalty = sum(
            modifier.amount
            for modifier in saved.modifiers
            if modifier.source == "multiple attack penalty"
        )
    return ActionContinuation(
        kind="family_action",
        actor_id=context.actor.actor_id,
        target_id=_command_target_id(command),
        attack_penalty=attack_penalty,
        attack_count=attack_count,
        attack_count_committed=saved.attack_count_committed,
        concealment_checked=True,
        stage=stage,
        targeting_failed=targeting_failed,
    )


def _targeting_choice_options() -> tuple[ChoiceOption, ...]:
    return (
        ChoiceOption("keep", "Keep result"),
        ChoiceOption("spend_hero_point", "Spend 1 Hero Point and reroll"),
    )


def _start_skill_targeting(
    context: FamilyProcedureContext,
    command: FamilyCommand,
    saved: SavedCheckContext,
) -> FamilyProcedureResult:
    """Resolve the shared DC 5 target gate before any skill check or Guidance."""

    target_id = _command_target_id(command)
    if target_id is None:
        return _continue_skill_after_target(context, command, saved)
    target = context.state.creatures.get(target_id)
    if target is None:
        return FamilyProcedureResult(rejection="The saved skill-action target is no longer available.")
    if not context.encounter.target_is_concealed(context.actor.actor_id, target.actor_id):
        return _continue_skill_after_target(context, command, saved)

    check = resolve_check(context.dice.draw(20), 0, 5)
    event = Event(
        "concealment_flat_check",
        context.actor.actor_id,
        target.actor_id,
        f"{context.actor.label} attempts the DC 5 concealment flat check against {target.label}: "
        f"d20 {check.die}; {check.degree.label().lower()}.",
        check=check,
    )
    continuation = _skill_continuation(
        context, command, saved, f"{_action_id(command)}_skill_targeting"
    )
    if context.actor.health_mode.value == "pc" and context.actor.hero_points > 0:
        context.encounter._set_pending(
            context.state,
            kind="concealment_hero_reroll",
            owner_actor_id=context.actor.actor_id,
            prompt=(
                f"{context.actor.label} may keep the concealment flat check or spend 1 Hero Point "
                "to reroll it."
            ),
            options=_targeting_choice_options(),
            details=(f"Original flat check: d20 {check.die} vs DC 5.",),
            actor_id=context.actor.actor_id,
            target_id=target.actor_id,
            attack_penalty=continuation.attack_penalty,
            attack_count=continuation.attack_count,
            check=check,
            check_kind="concealment",
            actions_cost=1,
            family_id="martial",
            procedure_id=f"skill_actions:{_action_id(command)}:concealment",
            saved_check=saved,
            family_command=command,
            concealment_checked=True,
            continuation=continuation,
        )
        return FamilyProcedureResult(events=(event,))
    return FamilyProcedureResult(
        events=tuple((event,))
        + _finish_skill_targeting(context, command, saved, continuation, check)
    )


def _continue_skill_after_target(
    context: FamilyProcedureContext,
    command: FamilyCommand,
    saved: SavedCheckContext,
) -> FamilyProcedureResult:
    """Resume Guidance and the skill check after targeting succeeds/bypasses."""

    # Assurance is the complete fixed skill result. It cannot take Guidance
    # or a separate skill Hero reroll, though its target gate still applies.
    if saved.result is not None:
        return _finish_checked_action(context, command, saved)
    action_id = _action_id(command)
    guidance = context.guidance_for()
    if guidance is not None:
        continuation = _skill_continuation(
            context, command, saved, f"{action_id}_skill_guidance"
        )
        continuation.item_id = guidance.effect_id
        context.present_choice(
            f"skill_actions:{action_id}:guidance",
            context.actor.actor_id,
            f"{context.actor.label} may use Guidance for this check.",
            (ChoiceOption("use", "Use Guidance (+1 status)"), ChoiceOption("keep", "Keep Guidance for later")),
            continuation,
            target_id=_command_target_id(command),
            saved_check=saved,
            family_command=command,
        )
        return FamilyProcedureResult(
            events=(Event("choice_offered", context.actor.actor_id, _command_target_id(command), "Choose whether to use Guidance."),)
        )
    if saved.result is None:
        try:
            saved = context.resolve_saved_check(saved)
        except (NotImplementedError, ValueError) as error:
            return FamilyProcedureResult(unsupported=str(error))
    return _offer_hero_point_or_finish(context, command, saved)


def _finish_skill_targeting(
    context: FamilyProcedureContext,
    command: FamilyCommand,
    saved: SavedCheckContext,
    continuation: ActionContinuation,
    check: CheckResult,
) -> tuple[Event, ...]:
    """Apply the target-gate result, without inventing a skill check on failure."""

    target = context.state.creatures.get(_command_target_id(command) or "")
    if target is None:
        return (Event("action_stopped", context.actor.actor_id, None, "The skill-action target is no longer available."),)
    if check.degree < DegreeOfSuccess.SUCCESS:
        events: list[Event] = [Event(
            "concealment_failed",
            context.actor.actor_id,
            target.actor_id,
            f"{context.actor.label} fails the concealment flat check; no skill check is attempted.",
            check=check,
        )]
        if isinstance(command, Feint):
            events.extend(_finish_failed_feint_targeting(context, command, saved, continuation))
        elif isinstance(command, Demoralize):
            context.grant_condition_immunity(
                "demoralize", context.actor.actor_id, target.actor_id,
                duration_seconds=DEMORALIZE.immunity_duration_seconds,
            )
            events.append(Event(
                "immunity_applied", context.actor.actor_id, target.actor_id,
                f"{target.label} is immune to this actor's Demoralize for 10 minutes.",
            ))
            events.extend(context.encounter._complete_action(context.state, context.actor, [], dice=context.dice))
        else:
            # A failed targeting gate never invokes Trip/Grapple degree effects.
            # In particular, an existing Grapple is retained until its normal
            # expiration because the Athletics check was never attempted.
            events.extend(context.encounter._complete_action(context.state, context.actor, [], dice=context.dice))
        return tuple(events)
    events = [Event(
        "concealment_passed",
        context.actor.actor_id,
        target.actor_id,
        f"{context.actor.label} passes the concealment flat check; the skill action may proceed.",
        check=check,
    )]
    events.extend(_continue_skill_after_target(context, command, saved).events)
    return tuple(events)


def _finish_failed_feint_targeting(
    context: FamilyProcedureContext,
    command: Feint,
    saved: SavedCheckContext,
    continuation: ActionContinuation,
) -> tuple[Event, ...]:
    """Preserve Scoundrel's Step while retaining the real failed gate provenance."""

    if not (_is_scoundrel(context) and _wielding_agile_or_finesse_melee_weapon(context)):
        return tuple(context.encounter._complete_action(context.state, context.actor, [], dice=context.dice))
    destinations = _feint_step_destinations(context)
    if not destinations:
        return tuple(context.encounter._complete_action(context.state, context.actor, [], dice=context.dice))
    step_continuation = replace(
        continuation,
        stage="feint_scoundrel_step_targeting_failure",
        targeting_failed=True,
    )
    context.present_choice(
        "skill_actions:feint:scoundrel_step",
        context.actor.actor_id,
        f"{context.actor.label} may take Scoundrel's free Step after Feint.",
        _feint_step_options(destinations),
        step_continuation,
        details=("The Feint's target concealment check failed; no Deception check was rolled.",),
        target_id=command.target_id,
        saved_check=saved,
        family_command=command,
    )
    return (Event(
        "choice_offered", context.actor.actor_id, command.target_id,
        "Choose whether and where to take Scoundrel's free Step after the failed targeting check.",
    ),)


def _start_skill_action_check(
    context: FamilyProcedureContext,
    command: FamilyCommand,
    statistic: str,
    dc: int,
    traits: frozenset[str],
    *,
    extra_modifiers: tuple[Modifier, ...] = (),
) -> FamilyProcedureResult:
    """Commit a named action once, then preserve the check through choices."""

    reaction_action = isinstance(command, Demoralize) and command.youre_next_reaction
    if not reaction_action and context.actor.actions_remaining < 1:
        return FamilyProcedureResult(rejection=f"{_action_id(command).title()} requires one action.")
    use_assurance = getattr(command, "use_assurance", False)
    if type(use_assurance) is not bool:
        return FamilyProcedureResult(rejection="use_assurance must be a boolean.")
    proficiency_bonus: int | None = None
    if use_assurance:
        try:
            proficiency_bonus = _assurance_proficiency_bonus(context, statistic)
        except ValueError as error:
            return FamilyProcedureResult(rejection=str(error))
    try:
        context.require_action_permitted(_action_id(command), traits)
        if use_assurance:
            assert proficiency_bonus is not None
            next_attack_count = context.actor.strikes_this_turn + 1 if "attack" in traits else None
            check = resolve_assurance_check(
                proficiency_bonus,
                dc,
                attack_id=command.attack_id if isinstance(command, Escape) else None,
                attack_count=next_attack_count,
                traits=traits,
            )
            saved = SavedCheckContext(
                check_owner_actor_id=context.actor.actor_id,
                context=CheckContext(statistic, "strength", traits),
                dc=dc,
                modifiers=check.modifier_breakdown,
                result=check,
                attack_id=check.attack_id,
            )
        elif isinstance(command, Escape) and command.check_method == "unarmed_attack":
            profile = _unarmed_escape_profile(context, command)
            saved = context.prepare_unarmed_attack_check(dc, profile.attack_id)
        else:
            saved = context.prepare_skill_check(
                statistic, dc, traits=traits, extra_modifiers=extra_modifiers,
            )
    except (NotImplementedError, ValueError) as error:
        return FamilyProcedureResult(unsupported=str(error))
    # Trip/Grapple are attack-trait maneuvers. Their MAP and attack count are
    # committed before the target gate so a failed concealment check still
    # spends the action and advances MAP exactly once. Escape retains its
    # established deferred attack-count behavior.
    target_for_gate = context.state.creatures.get(_command_target_id(command) or "")
    target_is_concealed = (
        target_for_gate is not None
        and context.encounter.target_is_concealed(
            context.actor.actor_id, target_for_gate.actor_id
        )
    )
    commit_attack_count = 1 if (
        isinstance(command, (Trip, Grapple))
        and "attack" in traits
        and (use_assurance or target_is_concealed)
    ) else 0
    if commit_attack_count:
        saved = replace(saved, attack_count_committed=True)
    context.commit_family_action(actions=0 if reaction_action else 1, attacks=(
        commit_attack_count or (1 if use_assurance and "attack" in traits else 0)
    ))
    if isinstance(command, (Trip, Grapple)):
        target_id = command.target_id
        context.state.feint_off_guard_effects = list(consume_feint_off_guard_on_attack(
            tuple(context.state.feint_off_guard_effects),
            attacker_id=context.actor.actor_id,
            target_id=target_id,
            # A physical maneuver against the feinted target consumes the
            # ordinary opening, but the off-guard penalty never changes its
            # Fortitude or Reflex DC.
            attack_traits=frozenset({"melee"}),
            actor_end_counts=context.state.actor_end_counts,
        ))
    if isinstance(command, (Trip, Grapple, Escape)):
        # Tumble Behind is separate from Feint and never alters a skill
        # action's save DC.  Trip, Grapple, and Escape carry the attack trait,
        # so each is the source's next attack and ends any live exposure
        # before a later Strike can claim it. Escape has no target creature;
        # its stable impediment ID is only a non-empty hook token because the
        # Tumble Behind helper deliberately consumes attacker-wide.
        tumble_store = getattr(context.state, "tumble_behind_exposures", None)
        if tumble_store is not None:
            from .movement_progression import consume_tumble_behind_on_attack

            context.state.tumble_behind_exposures = list(
                consume_tumble_behind_on_attack(
                    tuple(tumble_store),
                    attacker_id=context.actor.actor_id,
                    target_id=(command.target_id if not isinstance(command, Escape) else command.impediment_id),
                    actor_end_counts=context.state.actor_end_counts,
                )
            )
    if isinstance(command, TumbleThrough):
        # Tumble's check occurs on entering the enemy square.  Move through
        # any clear lead-in squares first, including their ordinary departure
        # reaction windows, then resolve the saved check at the enemy space.
        target = _tumble_target(context, command.path)
        target_index = next(index for index, point in enumerate(command.path) if point == target.position)
        continuation = ActionContinuation(
            kind="movement",
            actor_id=context.actor.actor_id,
            target_id=target.actor_id,
            path=command.path[:target_index],
            tumble_origin=context.actor.position,
            movement_kind="tumble_through",
            mode="tumble_through",
            stage="tumble_through_lead_in",
            seen_reactors=[],
            tumble_command=command,
            tumble_saved_check=saved,
            tumble_distance=_tumble_path_cost(context, command.path, target),
        )
        return FamilyProcedureResult(
            events=tuple(context.encounter._advance_continuation(
                context.state, context.dice, continuation
            ))
        )
    # The shared target gate must precede Guidance and the underlying skill
    # result. Assurance already has a saved fixed result, so it follows the
    # same gate and simply skips the later Hero Point skill reroll.
    return _start_skill_targeting(context, command, saved)


def _offer_hero_point_or_finish(
    context: FamilyProcedureContext,
    command: FamilyCommand,
    saved_check,
) -> FamilyProcedureResult:
    if isinstance(command, Demoralize) and command.youre_next_reaction:
        return _finish_checked_action(context, command, saved_check)
    if context.actor.health_mode.value == "pc" and context.actor.hero_points > 0:
        action_id = _action_id(command)
        # Keep the already resolved check's committed MAP and targeting
        # provenance on the separate skill Hero Point choice. This matters
        # when a dim target gate preceded a maneuver and the choice is saved.
        continuation = _skill_continuation(
            context, command, saved_check, f"{action_id}_skill_hero_point"
        )
        context.present_choice(
            f"skill_actions:{action_id}:hero_point",
            context.actor.actor_id,
            f"{context.actor.label} may spend a Hero Point to reroll this check.",
            (ChoiceOption("reroll", "Spend a Hero Point to reroll"), ChoiceOption("keep", "Keep the current result")),
            continuation,
            target_id=_command_target_id(command),
            saved_check=saved_check,
            family_command=command,
        )
        return FamilyProcedureResult(events=(Event("choice_offered", context.actor.actor_id, _command_target_id(command), "Choose whether to spend a Hero Point to reroll."),))
    return _finish_checked_action(context, command, saved_check)


def _finish_checked_action(
    context: FamilyProcedureContext,
    command: FamilyCommand,
    saved_check,
) -> FamilyProcedureResult:
    if saved_check.result is None:
        return FamilyProcedureResult(rejection="The saved skill-action check has not been resolved.")
    if isinstance(command, Trip):
        return _finish_trip(context, command, saved_check)
    if isinstance(command, Grapple):
        return _finish_grapple(context, command, saved_check)
    if isinstance(command, Escape):
        return _finish_escape(context, command, saved_check)
    if isinstance(command, Demoralize):
        return _finish_demoralize(context, command, saved_check)
    if isinstance(command, Feint):
        return _finish_feint(context, command, saved_check)
    if isinstance(command, TumbleThrough):
        return _finish_tumble_through(context, command, saved_check)
    if isinstance(command, QuickJump):
        return _finish_quick_jump(context, command, saved_check)
    return FamilyProcedureResult(unsupported="The saved skill-action command is not admitted.")


def _quick_jump_path(context: FamilyProcedureContext, command: QuickJump) -> tuple[Position, ...]:
    """Validate the flat-map horizontal path chosen before the Long Jump check."""
    actor = context.actor
    if actor.prone:
        raise ValueError("Stand before using Quick Jump.")
    if effective_speed_ft(actor, context.definition, _conditions_for_target(context, actor)) < 15:
        raise ValueError("Quick Jump requires at least 15-foot Speed.")
    if not isinstance(command.path, tuple) or not command.path:
        raise ValueError("Quick Jump requires a nonempty straight horizontal path.")
    current = actor.position
    direction: tuple[int, int] | None = None
    distance = 0
    for point in command.path:
        if not isinstance(point, Position) or not in_bounds(
            point, context.state.map_width, context.state.map_height
        ):
            raise ValueError("Quick Jump path leaves the supported map.")
        delta = (point.x - current.x, point.y - current.y)
        if delta not in {(1, 0), (-1, 0), (0, 1), (0, -1)}:
            raise ValueError("Quick Jump supports a straight cardinal horizontal path.")
        if direction is None:
            direction = delta
        elif delta != direction:
            raise ValueError("Quick Jump path must remain straight.")
        occupant = context.encounter._occupant_at(
            context.state, point, except_actor=actor.actor_id
        )
        if occupant is not None and not occupant.defeated:
            raise ValueError("Quick Jump path is blocked by an occupied square.")
        distance += 5
        current = point
    if distance > effective_speed_ft(actor, context.definition, _conditions_for_target(context, actor)):
        raise ValueError("Quick Jump cannot exceed your Speed.")
    if actor.must_leave_occupied:
        raise ValueError("Move out of the occupied ally's space before using Quick Jump.")
    return command.path


def _finish_quick_jump(
    context: FamilyProcedureContext,
    command: QuickJump,
    check_context: SavedCheckContext,
) -> FamilyProcedureResult:
    """Apply a Quick Jump Long Jump result through ordinary movement reactions."""
    check = check_context.result
    if check is None:
        return FamilyProcedureResult(rejection="Quick Jump requires a resolved Athletics check.")
    path = _quick_jump_path(context, command)
    speed = effective_speed_ft(
        context.actor, context.definition, _conditions_for_target(context, context.actor)
    )
    from .martial_defense import crane_stance_leap_bonus

    leap_bonus = crane_stance_leap_bonus(context.state, context.actor.actor_id)
    # Quick Jump changes only Long Jump's action cost and run-up requirement.
    # It retains Long Jump's check-result distance and failed-check horizontal
    # Leap, rather than using an invented degree-to-distance table. Crane
    # Stance's printed horizontal Leap increase applies to either result.
    # A normal horizontal Leap is 10 feet at Speed 15--25 and 15 feet at
    # Speed 30 or greater.  Vertical Long/High Jump terrain remains outside
    # this deliberately horizontal movement slice.
    normal_leap = (15 if speed >= 30 else 10) + leap_bonus
    if check.degree >= DegreeOfSuccess.SUCCESS:
        maximum = min((check.total // 5) * 5 + leap_bonus, speed)
    else:
        maximum = normal_leap
    events = [Event(
        "quick_jump_check",
        context.actor.actor_id,
        None,
        f"{context.actor.label} attempts Quick Jump: {check.degree.label()} "
        f"({check.total} vs DC {check.dc}); up to {maximum} feet.",
        check=check,
    )]
    jumped_path = path[: maximum // 5]
    if not jumped_path:
        if check.degree is DegreeOfSuccess.CRITICAL_FAILURE:
            context.actor.prone = True
            events.append(Event(
                "condition_applied", context.actor.actor_id, context.actor.actor_id,
                f"{context.actor.label} falls prone after the failed Quick Jump.", check=check,
            ))
        return _complete_action_unless_paused(context, events)
    continuation = ActionContinuation(
        kind="movement",
        actor_id=context.actor.actor_id,
        path=jumped_path,
        quick_jump_saved_check=check_context,
        movement_kind=(
            "quick_jump_critical_failure"
            if check.degree is DegreeOfSuccess.CRITICAL_FAILURE
            else "quick_jump"
        ),
        seen_reactors=[],
    )
    events.append(Event(
        "quick_jump_started", context.actor.actor_id, None,
        f"{context.actor.label} begins a {len(jumped_path) * 5}-foot Quick Jump.",
    ))
    events.extend(context.encounter._advance_continuation(
        context.state, context.dice, continuation
    ))
    return FamilyProcedureResult(events=tuple(events))


def _bravado_event(context: FamilyProcedureContext, result: str | None, check: CheckResult) -> Event | None:
    if result is None:
        return None
    if result == "panache_gained":
        text = f"{context.actor.label} gains Panache from Bravado."
    elif result == "panache_gained_temporarily":
        text = f"{context.actor.label} gains temporary Panache from Bravado through the end of the next turn."
    elif result == "panache_refreshed":
        text = f"{context.actor.label}'s Panache becomes lasting."
    else:
        text = f"{context.actor.label}'s temporary Panache is extended."
    return Event(result, context.actor.actor_id, None, text, check=check)


def _finish_tumble_through(
    context: FamilyProcedureContext,
    command: TumbleThrough,
    check_context: SavedCheckContext,
) -> FamilyProcedureResult:
    """Apply the Acrobatics result, then enter normal movement reactions."""

    lead_in = check_context.parent_continuation
    movement_path = command.path
    try:
        if lead_in is not None and lead_in.stage == "tumble_through_lead_in":
            movement_path = _tumble_remaining_path(context, command.path)
            target = _tumble_target(context, movement_path)
            if target.actor_id != lead_in.target_id:
                raise ValueError("The Tumble Through enemy space changed before the check resolved.")
            distance = lead_in.tumble_distance
            if distance is None:
                raise ValueError("The saved Tumble Through movement distance is missing.")
        else:
            target = _tumble_target(context, movement_path)
            distance = _tumble_path_cost(context, movement_path, target)
    except NotImplementedError as error:
        return FamilyProcedureResult(unsupported=str(error))
    except ValueError as error:
        return FamilyProcedureResult(rejection=str(error))
    check = check_context.result
    if check is None:
        return FamilyProcedureResult(rejection="The saved Tumble Through check has not been resolved.")
    events: list[Event] = [_event_check("tumble_through", context.actor, target, check)]
    # The movement limit is fixed when the action begins. Bravado grants its
    # Panache result after the check; it cannot retroactively add five feet to
    # the movement that was already attempted.
    enough_speed = distance <= effective_speed_ft(context.actor, context.definition, _conditions_for_target(context, context.actor))
    success = check.degree >= DegreeOfSuccess.SUCCESS and enough_speed
    bravado_degree = (
        check.degree
        if success or check.degree is DegreeOfSuccess.CRITICAL_FAILURE
        else DegreeOfSuccess.FAILURE
    )
    panache = apply_bravado_result(
        context.actor,
        context.definition,
        bravado_degree,
        current_end_count=context.state.actor_end_counts.get(context.actor.actor_id, 0),
    )
    panache_event = _bravado_event(context, panache, check)
    if panache_event is not None:
        events.append(panache_event)
    if success:
        # This is deliberately not a Feint exposure.  The selected level-2
        # Braggart feat keys its target-relative, next-attack benefit to a
        # successful Tumble Through and permits the admitted thrown attack.
        if "Tumble Behind" in context.definition.feats:
            from .movement_progression import grant_tumble_behind_exposure

            store = getattr(context.state, "tumble_behind_exposures", None)
            if store is None:
                return FamilyProcedureResult(
                    unsupported="Encounter state does not yet persist typed Tumble Behind exposures."
                )
            updated = grant_tumble_behind_exposure(
                tuple(store),
                source_actor_id=context.actor.actor_id,
                target_actor_id=target.actor_id,
                current_source_end_count=context.state.actor_end_counts.get(context.actor.actor_id, 0),
            )
            store[:] = updated
            events.append(Event(
                "tumble_behind_exposure",
                context.actor.actor_id,
                target.actor_id,
                f"{target.label} is off-guard to {context.actor.label}'s next attack before the end of this turn.",
                check=check,
            ))
        continuation = ActionContinuation(
            kind="movement",
            actor_id=context.actor.actor_id,
            target_id=target.actor_id,
            path=movement_path,
            movement_kind="tumble_through",
            mode="tumble_through",
            stage="tumble_through_success",
            seen_reactors=list(lead_in.seen_reactors) if lead_in is not None else [],
        )
        events.extend(context.encounter._advance_continuation(context.state, context.dice, continuation))
        return FamilyProcedureResult(events=tuple(events))

    reason = "fails the Acrobatics check" if check.degree < DegreeOfSuccess.SUCCESS else (
        f"does not have enough Speed to cross the enemy's space ({distance} feet required)"
    )
    events.append(Event(
        "tumble_through_failed",
        context.actor.actor_id,
        target.actor_id,
        f"{context.actor.label}'s Tumble Through {reason}; movement ends in {context.actor.position.x},{context.actor.position.y}.",
        check=check,
        position=context.actor.position,
    ))
    # Failure triggers reactions as if the actor moved out of its starting
    # square, even though the actor remains there. The movement continuation
    # gives the ordinary reaction/save machinery a persisted parent.
    continuation = ActionContinuation(
        kind="movement",
        actor_id=context.actor.actor_id,
        target_id=target.actor_id,
        path=(),
        movement_kind="tumble_through",
        mode="tumble_through",
        stage="tumble_through_failure",
        seen_reactors=[],
    )
    events.extend(context.encounter._advance_continuation(context.state, context.dice, continuation))
    return FamilyProcedureResult(events=tuple(events))


def _complete_action_unless_paused(context: FamilyProcedureContext, events: list[Event]) -> FamilyProcedureResult:
    if context.state.pending_choice is None:
        events.extend(context.encounter._complete_action(context.state, context.actor, [], dice=context.dice))
    return FamilyProcedureResult(events=tuple(events))


def _finish_trip(context: FamilyProcedureContext, command: Trip, check_context) -> FamilyProcedureResult:
    try:
        target = _target(context, command.target_id)
        profile = _check_maneuver(context, target, "trip", command.maneuver_item_id)
    except NotImplementedError as error:
        return FamilyProcedureResult(unsupported=str(error))
    except ValueError as error:
        return FamilyProcedureResult(rejection=str(error))
    outcome = trip_outcome_from_check(check_context.result, context.dice.draw)
    events = [_event_check("trip", context.actor, target, outcome.check)]
    if outcome.target_falls_prone:
        target.prone = True
        events.append(Event("condition_applied", context.actor.actor_id, target.actor_id, f"{target.label} falls prone.", check=outcome.check))
    if outcome.user_falls_prone and profile is not None:
        continuation = ActionContinuation(
            kind="family_action",
            actor_id=context.actor.actor_id,
            target_id=target.actor_id,
            item_id=profile.item_id,
            stage="trip_weapon_critical_failure",
        )
        context.present_choice(
            "skill_actions:trip_weapon_critical_failure",
            context.actor.actor_id,
            f"{context.actor.label} critically fails the weapon Trip; drop it to treat the result as a failure?",
            (ChoiceOption("drop_weapon", "Drop the weapon; treat this as a failure"), ChoiceOption("accept_critical_failure", "Keep the weapon; fall prone")),
            continuation,
            target_id=target.actor_id,
            saved_check=check_context,
            family_command=command,
        )
        events.append(Event("choice_offered", context.actor.actor_id, target.actor_id, "Choose whether to drop the weapon or fall prone."))
    elif outcome.user_falls_prone:
        context.actor.prone = True
        events.append(Event("condition_applied", context.actor.actor_id, context.actor.actor_id, f"{context.actor.label} falls prone after the failed Trip.", check=outcome.check))
    if outcome.critical_damage is not None:
        events.extend(_apply_trip_damage(context, target, outcome.critical_damage, outcome.check))
    return _complete_action_unless_paused(context, events)


def _apply_trip_damage(
    context: FamilyProcedureContext,
    target,
    damage: DamageResult,
    check: CheckResult,
) -> tuple[Event, ...]:
    """Apply Trip's one d6 through core's common damage and Hero Point path."""

    return context.apply_family_damage(
        target.actor_id,
        damage,
        source="Trip",
        damage_type="bludgeoning",
        check=check,
    )


def _finish_grapple(context: FamilyProcedureContext, command: Grapple, check_context) -> FamilyProcedureResult:
    try:
        target = _target(context, command.target_id)
    except ValueError as error:
        return FamilyProcedureResult(rejection=str(error))
    existing = _source_held_effects(context, context.actor.actor_id, target.actor_id)
    try:
        profile = _check_maneuver(
            context, target, "grapple", command.maneuver_item_id,
            already_holding_target=bool(existing),
        )
    except NotImplementedError as error:
        return FamilyProcedureResult(unsupported=str(error))
    except ValueError as error:
        return FamilyProcedureResult(rejection=str(error))
    outcome = grapple_outcome_from_check(check_context.result, already_holding_target=bool(existing))
    events = [_event_check("grapple", context.actor, target, outcome.check)]
    if outcome.release_user_grapple:
        removed_ids = {effect.effect_id for effect in existing}
        context.state.condition_effects = [effect for effect in context.state.condition_effects if effect.effect_id not in removed_ids]
        events.append(Event("condition_removed", context.actor.actor_id, target.actor_id, f"{context.actor.label} releases their Grapple on {target.label} after failing to maintain it."))
    if outcome.target_condition is not None:
        effect_id = f"grapple:{context.actor.actor_id}:{target.actor_id}"
        add_timed_condition_effect(
            context,
            effect_id=effect_id,
            kind=outcome.target_condition,
            source_id=context.actor.actor_id,
            target_id=target.actor_id,
            value=1,
            # Grapple is performed during this turn, and the source text says
            # the effect lasts until the end of the user's *next* turn.
            expiration=_expiry_after_actor_end(context, context.actor.actor_id, turns=2),
        )
        events.append(Event("condition_applied", context.actor.actor_id, target.actor_id, f"{target.label} is {outcome.target_condition} by {context.actor.label}'s Grapple through the end of {context.actor.label}'s next turn.", check=outcome.check))
    if outcome.offer_target_response and profile is not None:
        continuation = ActionContinuation(
            kind="family_action",
            actor_id=context.actor.actor_id,
            target_id=target.actor_id,
            item_id=profile.item_id,
            stage="grapple_weapon_critical_failure",
        )
        context.present_choice(
            "skill_actions:grapple_weapon_critical_failure",
            context.actor.actor_id,
            f"{context.actor.label} critically fails the weapon Grapple; drop it to treat the result as a failure?",
            (ChoiceOption("drop_weapon", "Drop the weapon; treat this as a failure"), ChoiceOption("keep_weapon", "Keep the weapon; allow the target's response")),
            continuation,
            target_id=target.actor_id,
            saved_check=check_context,
            family_command=command,
        )
        events.append(Event("choice_offered", context.actor.actor_id, target.actor_id, "Choose whether to drop the weapon or allow the target's response."))
    elif outcome.offer_target_response:
        _offer_grapple_target_choice(context, target, check_context, events, command)
    return _complete_action_unless_paused(context, events)


def _offer_grapple_target_choice(context, target, check_context, events, command):
    continuation = ActionContinuation(
        kind="family_action",
        actor_id=context.actor.actor_id,
        target_id=target.actor_id,
        stage="grapple_critical_failure",
    )
    context.present_choice(
        "skill_actions:grapple_critical_failure",
        target.actor_id,
        f"Choose {target.label}'s critical failure response to Grapple.",
        (ChoiceOption("grab_user", "Grab the acting creature"), ChoiceOption("make_user_prone", "Knock the acting creature prone")),
        continuation,
        target_id=target.actor_id,
        saved_check=check_context,
        family_command=command,
    )
    events.append(Event("choice_offered", context.actor.actor_id, target.actor_id, f"{target.label} chooses Grapple's critical failure effect."))


def _escape(context: FamilyProcedureContext, command: Escape) -> FamilyProcedureResult:
    if context.actor.actions_remaining < ESCAPE.action_cost:
        return FamilyProcedureResult(rejection="Escape requires one action.")
    if context.actor.must_leave_occupied:
        return FamilyProcedureResult(rejection="Move out of the occupied ally's space before taking another action.")
    if context.escape_locked:
        return FamilyProcedureResult(rejection="A critical failure bars Escape until the start of your next turn.")
    effect = _active_effect(context, command.impediment_id)
    if effect is None or effect.target_actor_id != context.actor.actor_id or (
        effect.kind not in {"grabbed", "immobilized", "restrained", "alchemy_glue_bomb_lesser"}
        and not (effect.kind == "speed_penalty" and effect.effect_id.startswith("tangle_vine:"))
    ):
        return FamilyProcedureResult(rejection="Escape must select a current grabbed, immobilized, restrained, or Tangle Vine effect on the acting creature.")
    if effect.source_actor_id not in context.state.creatures:
        return FamilyProcedureResult(unsupported="Escape against a non-creature effect needs a source-specific difficulty rule.")
    source = context.state.creatures[effect.source_actor_id]
    if command.check_method not in {"athletics", "acrobatics", "unarmed_attack"}:
        return FamilyProcedureResult(rejection="Escape check_method must be athletics, acrobatics, or unarmed_attack.")
    effect_dc = getattr(effect, "dc", None)
    if effect_dc is not None:
        dc = effect_dc
    elif effect.kind == "alchemy_glue_bomb_lesser" and effect.effect_id.startswith("glue_bomb:"):
        dc = 17
    elif effect.kind in {"grabbed", "restrained"} and effect.effect_id.startswith("grapple:"):
        try:
            dc = _skill_dc(context, source, "athletics", "strength")
        except ValueError:
            return FamilyProcedureResult(unsupported="Escape needs the selected creature source's authoritative Athletics DC.")
    else:
        return FamilyProcedureResult(unsupported="Escape needs the selected effect's source-backed DC.")
    if command.check_method == "unarmed_attack" and command.attack_id is not None:
        try:
            _unarmed_escape_profile(context, command)
        except ValueError as error:
            return FamilyProcedureResult(rejection=str(error))
    elif command.check_method != "unarmed_attack" and command.attack_id is not None:
        return FamilyProcedureResult(rejection="attack_id is only used when Escape uses an unarmed attack.")
    return _start_skill_action_check(
        context,
        command,
        command.check_method,
        dc,
        ESCAPE.traits,
    )


def _finish_escape(context: FamilyProcedureContext, command: Escape, check_context) -> FamilyProcedureResult:
    effect = _active_effect(context, command.impediment_id)
    if effect is None or effect.target_actor_id != context.actor.actor_id:
        return FamilyProcedureResult(rejection="The selected Escape impediment no longer affects the acting creature.")
    source = context.state.creatures.get(effect.source_actor_id)
    if source is None:
        return FamilyProcedureResult(unsupported="Escape against a non-creature effect needs a source-specific difficulty rule.")
    outcome = escape_outcome_from_check(check_context.result)
    events = [_event_check("escape", context.actor, source, outcome.check)]
    if outcome.free_of_selected_impediment:
        linked_vine = effect.effect_id.startswith("tangle_vine:")
        linked_glue = effect.effect_id.startswith("glue_bomb:")
        glue_base_id = (
            effect.effect_id.removesuffix(":immobilized")
            if linked_glue else None
        )
        removed_effects = tuple(
            current for current in context.state.condition_effects
            if (
                current.effect_id == effect.effect_id
                or (
                    linked_vine
                    and current.effect_id.rsplit(":", 1)[0] == effect.effect_id.rsplit(":", 1)[0]
                )
                or (
                    linked_glue
                    and current.effect_id == f"{glue_base_id}:immobilized"
                )
            )
        )
        removed_ids = {current.effect_id for current in removed_effects}
        context.state.condition_effects = [current for current in context.state.condition_effects if current.effect_id not in removed_ids]
        if linked_glue:
            context.state.active_effects = [
                current for current in context.state.active_effects
                if current.effect_id != glue_base_id
            ]
        events.append(Event("condition_removed", context.actor.actor_id, source.actor_id, f"{context.actor.label} escapes the selected effect imposed by {source.label}.", check=outcome.check))
    if outcome.retry_blocked_until_next_turn:
        # Core persists this action-only lockout separately from conditions so
        # it cannot leak into skill/DC modifier calculation.
        context.encounter.add_escape_lockout(context.state, context.actor.actor_id)
        events.append(Event("condition_applied", context.actor.actor_id, source.actor_id, f"{context.actor.label} cannot attempt Escape again until their next turn."))
    if outcome.followup_stride_ft:
        continuation = ActionContinuation(
            kind="family_action",
            actor_id=context.actor.actor_id,
            target_id=source.actor_id,
            item_id=effect.effect_id,
            stage="escape_critical_success_stride",
        )
        destinations = _escape_stride_destinations(context)
        options = (ChoiceOption("stay", "Stay here"),) + tuple(
            ChoiceOption(f"stride:{destination.x}:{destination.y}", f"Stride to ({destination.x}, {destination.y})")
            for destination in destinations
        )
        context.present_choice(
            "skill_actions:escape_critical_success_stride",
            context.actor.actor_id,
            f"{context.actor.label} may Stride up to 5 feet after the critical success.",
            options,
            continuation,
            target_id=source.actor_id,
            saved_check=check_context,
            family_command=command,
        )
        events.append(Event("choice_offered", context.actor.actor_id, source.actor_id, "Choose whether to use the 5-foot Stride."))
    return _complete_action_unless_paused(context, events)


def _escape_stride_destinations(context: FamilyProcedureContext):
    if context.actor.prone or effective_speed_ft(context.actor, _definition(context.actor), _conditions_for_target(context, context.actor)) < 10:
        return ()
    destinations = []
    for dx in (-1, 0, 1):
        for dy in (-1, 0, 1):
            if (dx, dy) == (0, 0):
                continue
            destination = Position(context.actor.position.x + dx, context.actor.position.y + dy)
            if not in_bounds(destination, context.state.map_width, context.state.map_height):
                continue
            cost, _ = step_cost(context.actor.position, destination, context.actor.diagonals_this_turn)
            if cost > 5:
                continue
            occupant = context.encounter._occupant_at(context.state, destination, except_actor=context.actor.actor_id)
            if occupant is not None and not context.encounter._can_share_with_body(context.actor, occupant):
                continue
            destinations.append(destination)
    return tuple(sorted(destinations))


def _demoralize(context: FamilyProcedureContext, command: Demoralize) -> FamilyProcedureResult:
    if not command.youre_next_reaction and context.actor.actions_remaining < DEMORALIZE.action_cost:
        return FamilyProcedureResult(rejection="Demoralize requires one action.")
    if not command.youre_next_reaction and context.actor.must_leave_occupied:
        return FamilyProcedureResult(rejection="Move out of the occupied ally's space before taking another action.")
    try:
        target = _target(context, command.target_id)
    except ValueError as error:
        return FamilyProcedureResult(rejection=str(error))
    max_range = 60 if command.youre_next_reaction else DEMORALIZE.range_ft
    if grid_distance_feet(context.actor.position, target.position) > max_range:
        return FamilyProcedureResult(rejection=f"Demoralize requires a target within {max_range} feet.")
    if target.unconscious:
        return FamilyProcedureResult(rejection="Demoralize requires an aware target.")
    if command.use_intimidating_glare:
        known_feats = {feat.strip().casefold().replace("_", " ") for feat in context.definition.feats}
        known_abilities = {ability.strip().casefold().replace("_", " ") for ability in context.definition.abilities}
        barbarian_state = context.actor.barbarian_state
        if barbarian_state is not None:
            from .barbarian import has_intimidating_glare

            if has_intimidating_glare(
                barbarian_state,
                intimidation_trained=_trained_skill_from_definition(context, "intimidation"),
            ):
                known_abilities.add("intimidating glare")
        if "intimidating glare" not in known_feats | known_abilities:
            return FamilyProcedureResult(rejection="Intimidating Glare requires the Intimidating Glare feat.")
    understood = False
    if not command.use_intimidating_glare:
        spoken_language = command.spoken_language
        if spoken_language is None:
            spoken_language = next(iter(context.definition.languages), None)
        if spoken_language is not None and spoken_language not in context.definition.languages:
            return FamilyProcedureResult(rejection="Choose a language the acting creature can speak for Demoralize.")
        understood = spoken_language is not None and spoken_language in _definition(target).languages
    braggart = is_braggart(context.definition)
    # Braggart's Bravado still grants panache when Demoralize has no effect
    # because of the target's temporary Demoralize immunity. Let the check
    # resolve in that case; the normal frightened application below remains
    # suppressed by the target's effect immunity.
    if (
        context.condition_immunity_active("demoralize", context.actor.actor_id, target.actor_id)
        and not braggart
    ):
        return FamilyProcedureResult(rejection="This target is temporarily immune to this actor's Demoralize.")
    try:
        dc = _save_dc(context, target, "will")
    except ValueError as error:
        return FamilyProcedureResult(unsupported=str(error))
    trait_values = {"concentrate", "emotion", "fear", "mental"}
    if braggart:
        trait_values.add("bravado")
    trait_values.add("visual" if command.use_intimidating_glare else "auditory")
    traits = frozenset(trait_values)
    barbarian_state = context.actor.barbarian_state
    if barbarian_state is not None:
        from .barbarian import action_traits_with_instinct_features

        traits = action_traits_with_instinct_features(
            barbarian_state,
            "demoralize",
            traits,
            intimidation_trained=_trained_skill_from_definition(context, "intimidation"),
        )
    return _start_skill_action_check(
        context,
        command,
        "intimidation",
        dc,
        traits,
        extra_modifiers=(
            *((Modifier(2, "circumstance", "You're Next"),) if command.youre_next_reaction else ()),
            *stylish_combatant_modifiers(context.definition),
            *(() if understood or command.use_intimidating_glare else (
                Modifier(-4, "circumstance", "Demoralize language barrier"),
            )),
        ),
    )


def _finish_demoralize(context: FamilyProcedureContext, command: Demoralize, check_context) -> FamilyProcedureResult:
    try:
        target = _target(context, command.target_id)
    except ValueError as error:
        return FamilyProcedureResult(rejection=str(error))
    # A target's temporary Demoralize immunity suppresses the action's
    # frightened effect. Braggart still reaches this finish path so Bravado
    # can grant Panache from the check, as required by the Bravado trait.
    frightened_immune = (
        context.condition_immunity_active("demoralize", context.actor.actor_id, target.actor_id)
        or any(
            context.condition_immunity_active(kind, target.actor_id, target.actor_id)
            for kind in ("frightened", "fear")
        )
    )
    outcome = demoralize_outcome_from_check(
        check_context.result,
        use_intimidating_glare=command.use_intimidating_glare,
        target_frightened_immune=frightened_immune,
    )
    context.grant_condition_immunity("demoralize", context.actor.actor_id, target.actor_id, duration_seconds=DEMORALIZE.immunity_duration_seconds)
    events = [_event_check("demoralize", context.actor, target, outcome.check)]
    if outcome.apply_frightened:
        current_round_end = context.state.actor_end_counts.get(target.actor_id, 0)
        add_timed_condition_effect(
            context,
            effect_id=f"demoralize:{context.actor.actor_id}:{target.actor_id}:{context.state.round_number}:{current_round_end}",
            kind="frightened",
            source_id=context.actor.actor_id,
            target_id=target.actor_id,
            value=outcome.frightened_value,
            expiration=EffectExpiration(target.actor_id, "end", current_round_end + outcome.frightened_value),
        )
        events.append(Event("condition_applied", context.actor.actor_id, target.actor_id, f"{target.label} is frightened {outcome.frightened_value}.", check=outcome.check))
    events.append(Event("immunity_applied", context.actor.actor_id, target.actor_id, f"{target.label} is immune to this actor's Demoralize for 10 minutes."))
    panache_event = apply_bravado_result(
        context.actor,
        context.definition,
        check_context.result.degree,
        current_end_count=context.state.actor_end_counts.get(context.actor.actor_id, 0),
    )
    if panache_event is not None:
        if panache_event == "panache_gained":
            text = f"{context.actor.label} gains Panache from Bravado."
        elif panache_event == "panache_gained_temporarily":
            text = f"{context.actor.label} gains temporary Panache from Bravado through the end of the next turn."
        elif panache_event == "panache_refreshed":
            text = f"{context.actor.label}'s Panache becomes lasting."
        else:
            text = f"{context.actor.label}'s temporary Panache is extended."
        events.append(Event(panache_event, context.actor.actor_id, None, text, check=check_context.result))
    if command.youre_next_reaction:
        return FamilyProcedureResult(events=tuple(events))
    return _complete_action_unless_paused(context, events)


def _trained_deception(context: FamilyProcedureContext) -> bool:
    ranks = {
        rank.strip().casefold()
        for name, rank, _modifier in context.definition.skills
        if name == "deception" and isinstance(rank, str)
    }
    return bool(ranks & {"trained", "expert", "master", "legendary"})


def _trained_skill_from_definition(context: FamilyProcedureContext, statistic: str) -> bool:
    """Skill sheets use ``None`` only for an untrained skill entry."""

    return any(
        name == statistic and rank is not None
        for name, rank, _modifier in context.definition.skills
    )


def _is_scoundrel(context: FamilyProcedureContext) -> bool:
    from .rogue import RogueRacket, rogue_racket

    return rogue_racket(context.definition.abilities) is RogueRacket.SCOUNDREL


def _wielding_agile_or_finesse_melee_weapon(context: FamilyProcedureContext) -> bool:
    return any(
        attack.item_id is not None
        and attack.item_id in context.actor.held_items
        and "melee" in attack.traits
        and "ranged" not in attack.traits
        and bool({"agile", "finesse"} & attack.traits)
        for attack in context.definition.attacks
    )


def _new_feint_effect_id(context: FamilyProcedureContext, target_id: str) -> str:
    effects = getattr(context.state, "feint_off_guard_effects", ())
    used = {item.effect_id for item in effects if isinstance(item, FeintOffGuardEffect)}
    prefix = f"feint:{context.actor.actor_id}:{target_id}:{context.state.round_number}"
    suffix = 1
    while f"{prefix}:{suffix}" in used:
        suffix += 1
    return f"{prefix}:{suffix}"


def _feint_step_destinations(context: FamilyProcedureContext) -> tuple[Position, ...]:
    if not context.encounter._action_permitted(
        context.state, context.actor, "step", frozenset({"move"})
    ):
        return ()
    return context.encounter._step_destinations(context.actor, context.state)


def _feint_step_options(destinations: tuple[Position, ...]) -> tuple[ChoiceOption, ...]:
    return (
        ChoiceOption("stay", "Don't Step"),
        *(ChoiceOption(f"step:{point.x}:{point.y}", f"Step to {point.x},{point.y}") for point in destinations),
    )


def _finish_feint(context: FamilyProcedureContext, command: Feint, check_context) -> FamilyProcedureResult:
    if check_context.result is None:
        return FamilyProcedureResult(rejection="The saved Feint check has not been resolved.")
    try:
        target = _target(context, command.target_id)
    except ValueError as error:
        return FamilyProcedureResult(rejection=str(error))

    if command.use_overextending and "Overextending Feint" not in context.definition.feats:
        return FamilyProcedureResult(rejection="Overextending Feint is not admitted for this creature.")
    store = getattr(context.state, "feint_off_guard_effects", None)
    if check_context.result.degree is not DegreeOfSuccess.FAILURE and store is None:
        return FamilyProcedureResult(
            unsupported="Encounter state does not yet persist typed, attacker-scoped Feint exposures."
        )
    outcome = feint_outcome_from_check(
        check_context.result,
        feinter_id=context.actor.actor_id,
        target_id=target.actor_id,
        effect_id=_new_feint_effect_id(context, target.actor_id),
        current_feinter_end_count=context.state.actor_end_counts.get(context.actor.actor_id, 0),
        scoundrel=_is_scoundrel(context),
        wielding_agile_or_finesse_melee_weapon=_wielding_agile_or_finesse_melee_weapon(context),
    )
    events = [_event_check("feint", context.actor, target, outcome.check)]
    if command.use_overextending and outcome.check.degree >= DegreeOfSuccess.SUCCESS:
        effect_id = f"overextending_feint:{context.actor.actor_id}:{target.actor_id}:{context.state.round_number}:{len(context.state.overextending_feint_effects) + 1}"
        context.state.overextending_feint_effects.append(OverextendingFeintEffect(
            effect_id,
            context.actor.actor_id,
            target.actor_id,
            EffectExpiration(target.actor_id, "end", context.state.actor_end_counts.get(target.actor_id, 0) + 1),
            outcome.check.degree is DegreeOfSuccess.CRITICAL_SUCCESS,
        ))
        events.append(Event(
            "overextending_feint",
            context.actor.actor_id,
            target.actor_id,
            f"{target.label} takes a -2 circumstance penalty to {'all attacks' if outcome.check.degree is DegreeOfSuccess.CRITICAL_SUCCESS else 'their next attack'} against {context.actor.label}.",
            check=outcome.check,
        ))
        return _complete_action_unless_paused(context, events)
    for effect in outcome.off_guard_effects:
        store.append(effect)
        if effect.target_actor_id == context.actor.actor_id:
            message = f"{context.actor.label} is off-guard to {target.label}'s melee attacks through the end of {context.actor.label}'s next turn."
        elif effect.scope is FeintAttackScope.NEXT_MELEE_ATTACK:
            message = f"{target.label} is off-guard to {context.actor.label}'s next melee attack this turn."
        elif effect.scope is FeintAttackScope.ANY_MELEE_ATTACKER:
            message = f"{target.label} is off-guard to all melee attackers through the end of {context.actor.label}'s next turn."
        elif _is_scoundrel(context):
            message = f"{target.label} is off-guard to {context.actor.label}'s melee attacks through the end of {context.actor.label}'s next turn."
        else:
            message = f"{target.label} is off-guard to {context.actor.label}'s melee attacks through the end of {context.actor.label}'s next turn."
        events.append(Event("feint_exposure", context.actor.actor_id, effect.target_actor_id, message, check=outcome.check))

    destinations = _feint_step_destinations(context) if outcome.can_free_step else ()
    if destinations:
        continuation = ActionContinuation(
            kind="family_action",
            actor_id=context.actor.actor_id,
            target_id=target.actor_id,
            stage="feint_scoundrel_step",
        )
        context.present_choice(
            "skill_actions:feint:scoundrel_step",
            context.actor.actor_id,
            f"{context.actor.label} may take Scoundrel's free Step after Feint.",
            _feint_step_options(destinations),
            continuation,
            target_id=target.actor_id,
            saved_check=check_context,
            family_command=command,
        )
        events.append(Event("choice_offered", context.actor.actor_id, target.actor_id, "Choose whether and where to take Scoundrel's free Step."))
        return FamilyProcedureResult(events=tuple(events))
    return _complete_action_unless_paused(context, events)


def handle_action(context: FamilyProcedureContext) -> FamilyProcedureResult:
    """Run one of the currently admitted common skill-action procedures."""

    command = context.command
    if isinstance(command, QuickJump):
        if context.actor.actions_remaining < 1:
            return FamilyProcedureResult(rejection="Quick Jump requires one action.")
        if "Quick Jump" not in context.definition.feats:
            return FamilyProcedureResult(unsupported="Quick Jump is not admitted for this creature.")
        try:
            _quick_jump_path(context, command)
        except ValueError as error:
            return FamilyProcedureResult(rejection=str(error))
        from .skill_content import QUICK_JUMP
        from .martial_defense import crane_stance_leap_bonus

        return _start_skill_action_check(
            context, command, "athletics",
            15 - crane_stance_leap_bonus(context.state, context.actor.actor_id),
            QUICK_JUMP.traits,
        )
    if isinstance(command, TumbleThrough):
        if context.actor.actions_remaining < TUMBLE_THROUGH.action_cost:
            return FamilyProcedureResult(rejection="Tumble Through requires one action.")
        try:
            target = _tumble_target(context, command.path)
            dc = _save_dc(context, target, "reflex")
            traits = TUMBLE_THROUGH.traits if is_swashbuckler(context.definition) else frozenset({"move"})
            context.require_action_permitted(TUMBLE_THROUGH.action_id, traits)
        except NotImplementedError as error:
            return FamilyProcedureResult(unsupported=str(error))
        except ValueError as error:
            return FamilyProcedureResult(rejection=str(error))
        return _start_skill_action_check(
            context,
            command,
            "acrobatics",
            dc,
            traits,
            extra_modifiers=(
                stylish_combatant_modifiers(context.definition)
                if is_swashbuckler(context.definition) else ()
            ),
        )
    if isinstance(command, Feint):
        if context.actor.actions_remaining < FEINT.action_cost:
            return FamilyProcedureResult(rejection="Feint requires one action.")
        if context.actor.must_leave_occupied:
            return FamilyProcedureResult(rejection="Move out of the occupied ally's space before taking another action.")
        if not _trained_deception(context):
            return FamilyProcedureResult(rejection="Feint requires trained Deception.")
        try:
            target = _target(context, command.target_id)
        except ValueError as error:
            return FamilyProcedureResult(rejection=str(error))
        reachable_melee = tuple(
            attack
            for attack in context.definition.attacks
            if "melee" in attack.traits
            and "ranged" not in attack.traits
            and context.encounter._attack_usable(context.state, context.actor, attack)
            and grid_distance_feet(context.actor.position, target.position) <= attack.reach_ft
        )
        if not reachable_melee:
            return FamilyProcedureResult(rejection="Feint requires a target within your melee reach.")
        try:
            dc = _save_dc(context, target, "perception")
        except ValueError as error:
            return FamilyProcedureResult(unsupported=str(error))
        return _start_skill_action_check(context, command, "deception", dc, FEINT.traits)
    if isinstance(command, Trip):
        if context.actor.actions_remaining < TRIP.action_cost:
            return FamilyProcedureResult(rejection="Trip requires one action.")
        try:
            target = _target(context, command.target_id)
            _check_maneuver(context, target, "trip", command.maneuver_item_id)
            dc = _save_dc(context, target, "reflex")
        except NotImplementedError as error:
            return FamilyProcedureResult(unsupported=str(error))
        except ValueError as error:
            return FamilyProcedureResult(rejection=str(error))
        return _start_skill_action_check(context, command, "athletics", dc, TRIP.traits)
    if isinstance(command, Grapple):
        if context.actor.actions_remaining < GRAPPLE.action_cost:
            return FamilyProcedureResult(rejection="Grapple requires one action.")
        try:
            target = _target(context, command.target_id)
            existing = _source_held_effects(context, context.actor.actor_id, target.actor_id)
            _check_maneuver(context, target, "grapple", command.maneuver_item_id, already_holding_target=bool(existing))
            dc = _save_dc(context, target, "fortitude")
        except NotImplementedError as error:
            return FamilyProcedureResult(unsupported=str(error))
        except ValueError as error:
            return FamilyProcedureResult(rejection=str(error))
        return _start_skill_action_check(context, command, "athletics", dc, GRAPPLE.traits)
    if isinstance(command, Escape):
        return _escape(context, command)
    if isinstance(command, Demoralize):
        return _demoralize(context, command)
    return FamilyProcedureResult(unsupported="This skill-action command is not admitted.")


def handle_choice(context: FamilyProcedureContext) -> FamilyProcedureResult:
    """Resume only saved choices owned by this module."""

    pending, choice = context.pending, context.choice
    if pending is None or choice is None or pending.procedure_id is None:
        return FamilyProcedureResult(rejection="The saved skill-action choice is incomplete.")
    continuation = pending.continuation
    if continuation is None:
        return FamilyProcedureResult(rejection="The saved skill-action continuation is missing.")
    if pending.procedure_id.endswith(":concealment"):
        command = pending.family_command
        saved = pending.saved_check
        if (
            not isinstance(command, (Trip, Grapple, Demoralize, Feint, TumbleThrough))
            or saved is None
            or (saved.result is not None and not getattr(command, "use_assurance", False))
            or continuation.stage != f"{_action_id(command)}_skill_targeting"
            or not continuation.concealment_checked
            or pending.target_id != _command_target_id(command)
        ):
            return FamilyProcedureResult(rejection="The saved skill-action concealment step is incomplete.")
        check = pending.check
        if check is None or check.dc != 5 or check.modifier != 0:
            return FamilyProcedureResult(rejection="The saved skill-action concealment check is incomplete.")
        if choice.option_id == "spend_hero_point":
            try:
                if context.actor.hero_points < 1:
                    return FamilyProcedureResult(rejection="The concealment check owner no longer has a Hero Point.")
                context.actor.hero_points -= 1
                check = resolve_check(context.dice.draw(20), 0, 5)
            except ValueError as error:
                return FamilyProcedureResult(rejection=str(error))
            events = [Event(
                "hero_reroll", context.actor.actor_id, pending.target_id,
                f"Hero Point reroll of the concealment flat check: d20 {check.die} vs DC 5; "
                f"{check.degree.label().lower()}.",
                check=check,
            )]
        elif choice.option_id == "keep":
            events = [Event(
                "concealment_kept", context.actor.actor_id, pending.target_id,
                f"{context.actor.label} keeps the concealment flat check result.",
                check=check,
            )]
        else:
            return FamilyProcedureResult(rejection="Choose whether to keep or reroll the concealment check.")
        events.extend(_finish_skill_targeting(context, command, saved, continuation, check))
        return FamilyProcedureResult(events=tuple(events))
    if pending.procedure_id == "skill_actions:feint:scoundrel_step":
        command = pending.family_command
        saved = pending.saved_check
        if (
            not isinstance(command, Feint)
            or saved is None
            or (saved.result is not None and not continuation.targeting_failed)
            or continuation.stage not in {"feint_scoundrel_step", "feint_scoundrel_step_targeting_failure"}
            or continuation.actor_id != context.actor.actor_id
            or pending.target_id != command.target_id
        ):
            return FamilyProcedureResult(rejection="The saved Scoundrel Step continuation is incomplete.")
        destinations = _feint_step_destinations(context)
        expected_options = _feint_step_options(destinations)
        if pending.options != expected_options:
            return FamilyProcedureResult(rejection="The saved Scoundrel Step destinations are no longer legal.")
        if choice.option_id == "stay":
            events = [Event(
                "scoundrel_step", context.actor.actor_id, command.target_id,
                (
                    f"{context.actor.label} keeps position after Feint."
                    if not continuation.targeting_failed
                    else f"{context.actor.label} keeps position after Feint's failed concealment targeting."
                ),
                check=None if continuation.targeting_failed else saved.result,
            )]
            events.extend(context.encounter._complete_action(context.state, context.actor, [], dice=context.dice))
            return FamilyProcedureResult(events=tuple(events))
        try:
            _, raw_x, raw_y = choice.option_id.split(":")
            destination = Position(int(raw_x), int(raw_y))
        except (ValueError, TypeError):
            return FamilyProcedureResult(rejection="Choose one of the saved Scoundrel Step destinations or stay.")
        if destination not in destinations:
            return FamilyProcedureResult(rejection="That destination is no longer legal for Scoundrel's free Step.")
        try:
            _cost, diagonal_count = step_cost(context.actor.position, destination, context.actor.diagonals_this_turn)
        except ValueError as error:
            return FamilyProcedureResult(rejection=str(error))
        context.state.taking_cover.discard(context.actor.actor_id)
        context.actor.position = destination
        context.actor.diagonals_this_turn += diagonal_count
        events = context.encounter._release_sourced_holds(context.state, context.actor)
        context.actor.must_leave_occupied = context.encounter._ends_in_living_ally_space(context.actor, context.state)
        events.append(Event(
            "scoundrel_step", context.actor.actor_id, command.target_id,
            (
                f"{context.actor.label} takes a free Step to {destination.x},{destination.y} after Feint."
                if not continuation.targeting_failed
                else f"{context.actor.label} takes a free Step to {destination.x},{destination.y} after Feint's failed concealment targeting."
            ),
            check=None if continuation.targeting_failed else saved.result,
            position=destination,
        ))
        events.extend(context.encounter._complete_action(context.state, context.actor, [], dice=context.dice))
        return FamilyProcedureResult(events=tuple(events))
    if pending.procedure_id.endswith(":guidance"):
        command = pending.family_command
        saved = pending.saved_check
        action_id = pending.procedure_id.split(":")[1]
        if (
            not isinstance(command, (Trip, Grapple, Escape, Demoralize, Feint, TumbleThrough, QuickJump))
            or _action_id(command) != action_id
            or saved is None or saved.result is not None
            or continuation.stage != f"{action_id}_skill_guidance"
        ):
            return FamilyProcedureResult(rejection="The saved skill-action Guidance step is incomplete.")
        if choice.option_id == "use":
            try:
                bonus = context.consume_guidance(continuation.item_id or "")
                saved = context.add_check_modifier(saved, bonus)
            except ValueError as error:
                return FamilyProcedureResult(rejection=str(error))
        elif choice.option_id != "keep":
            return FamilyProcedureResult(rejection="Choose whether to use Guidance for the saved check.")
        try:
            rolled = context.resolve_saved_check(saved)
        except ValueError as error:
            return FamilyProcedureResult(rejection=str(error))
        return _offer_hero_point_or_finish(context, command, rolled)
    if pending.procedure_id.endswith(":hero_point"):
        command = pending.family_command
        saved = pending.saved_check
        action_id = pending.procedure_id.split(":")[1]
        if (
            not isinstance(command, (Trip, Grapple, Escape, Demoralize, Feint, TumbleThrough, QuickJump))
            or _action_id(command) != action_id
            or saved is None or saved.result is None or saved.reroll_used
            or continuation.stage != f"{action_id}_skill_hero_point"
        ):
            return FamilyProcedureResult(rejection="The saved skill-action Hero Point step is incomplete.")
        if choice.option_id == "reroll":
            try:
                saved = context.reroll_skill_check(saved)
            except ValueError as error:
                return FamilyProcedureResult(rejection=str(error))
        elif choice.option_id != "keep":
            return FamilyProcedureResult(rejection="Choose whether to reroll the saved check.")
        return _finish_checked_action(context, command, saved)
    if pending.procedure_id == "skill_actions:grapple_critical_failure":
        target = context.state.creatures.get(continuation.target_id or "")
        if target is None or pending.saved_check is None or not isinstance(pending.family_command, Grapple):
            return FamilyProcedureResult(rejection="The Grapple choice no longer has its target or check.")
        if choice.option_id == "make_user_prone":
            context.actor.prone = True
            message = f"{context.actor.label} falls prone from {target.label}'s Grapple response."
            events = [Event("condition_applied", target.actor_id, context.actor.actor_id, message, check=pending.saved_check.result)]
        elif choice.option_id == "grab_user":
            add_timed_condition_effect(
                context,
                effect_id=f"grapple:{target.actor_id}:{context.actor.actor_id}",
                kind="grabbed",
                source_id=target.actor_id,
                target_id=context.actor.actor_id,
                value=1,
                expiration=_expiry_after_actor_end(context, target.actor_id),
            )
            events = [Event("condition_applied", target.actor_id, context.actor.actor_id, f"{context.actor.label} is grabbed by {target.label} through the end of {target.label}'s next turn.", check=pending.saved_check.result)]
        else:
            return FamilyProcedureResult(rejection="Choose one of the saved Grapple responses.")
        events.extend(context.encounter._complete_action(context.state, context.actor, [], dice=context.dice))
        return FamilyProcedureResult(events=tuple(events))
    if pending.procedure_id == "skill_actions:trip_weapon_critical_failure":
        target = context.state.creatures.get(continuation.target_id or "")
        if target is None or pending.saved_check is None or pending.saved_check.result is None:
            return FamilyProcedureResult(rejection="The saved Trip choice no longer has its target or check.")
        try:
            _maneuver_weapon(context, continuation.item_id, "trip")
        except (NotImplementedError, ValueError) as error:
            return FamilyProcedureResult(rejection=str(error))
        if continuation.item_id not in context.actor.held_items:
            return FamilyProcedureResult(rejection="The selected Trip weapon is no longer held.")
        events: list[Event] = []
        if choice.option_id == "drop_weapon":
            context.actor.held_items.remove(continuation.item_id)
            context.state.ground_items.setdefault(context.actor.position, []).append(continuation.item_id)
            events.append(Event("release", context.actor.actor_id, target.actor_id, f"{context.actor.label} drops {continuation.item_id}; the Trip is treated as a failure."))
        elif choice.option_id == "accept_critical_failure":
            context.actor.prone = True
            events.append(Event("condition_applied", context.actor.actor_id, context.actor.actor_id, f"{context.actor.label} falls prone after the failed Trip.", check=pending.saved_check.result))
        else:
            return FamilyProcedureResult(rejection="Choose whether to drop the weapon or accept the Trip critical failure.")
        events.extend(context.encounter._complete_action(context.state, context.actor, [], dice=context.dice))
        return FamilyProcedureResult(events=tuple(events))
    if pending.procedure_id == "skill_actions:grapple_weapon_critical_failure":
        target = context.state.creatures.get(continuation.target_id or "")
        if target is None or pending.saved_check is None or pending.saved_check.result is None:
            return FamilyProcedureResult(rejection="The saved Grapple choice no longer has its target or check.")
        try:
            _maneuver_weapon(context, continuation.item_id, "grapple")
        except (NotImplementedError, ValueError) as error:
            return FamilyProcedureResult(rejection=str(error))
        if continuation.item_id not in context.actor.held_items:
            return FamilyProcedureResult(rejection="The selected Grapple weapon is no longer held.")
        if choice.option_id == "drop_weapon":
            context.actor.held_items.remove(continuation.item_id)
            context.state.ground_items.setdefault(context.actor.position, []).append(continuation.item_id)
            events = [Event("release", context.actor.actor_id, target.actor_id, f"{context.actor.label} drops {continuation.item_id}; the Grapple is treated as a failure.")]
            events.extend(context.encounter._complete_action(context.state, context.actor, [], dice=context.dice))
            return FamilyProcedureResult(events=tuple(events))
        if choice.option_id == "keep_weapon":
            events: list[Event] = []
            _offer_grapple_target_choice(context, target, pending.saved_check, events, pending.family_command)
            return FamilyProcedureResult(events=tuple(events))
        return FamilyProcedureResult(rejection="Choose whether to drop the weapon or allow the target's Grapple response.")
    if pending.procedure_id == "skill_actions:escape_critical_success_stride":
        if pending.saved_check is None or not isinstance(pending.family_command, Escape):
            return FamilyProcedureResult(rejection="The saved Escape check is missing.")
        if choice.option_id == "stay":
            events = [Event("escape_stride", context.actor.actor_id, pending.target_id, f"{context.actor.label} stays in place after the critical Escape.")]
            events.extend(context.encounter._complete_action(context.state, context.actor, [], dice=context.dice))
            return FamilyProcedureResult(events=tuple(events))
        if not choice.option_id.startswith("stride:"):
            return FamilyProcedureResult(rejection="Choose a saved Escape follow-up destination.")
        try:
            _, raw_x, raw_y = choice.option_id.split(":")
            destination = Position(int(raw_x), int(raw_y))
        except (ValueError, TypeError):
            return FamilyProcedureResult(rejection="The saved Escape destination is invalid.")
        if destination not in _escape_stride_destinations(context):
            return FamilyProcedureResult(rejection="That destination is no longer legal for the 5-foot Stride.")
        continuation = ActionContinuation(
            kind="movement",
            actor_id=context.actor.actor_id,
            path=(destination,),
            movement_kind="stride",
        )
        events = [Event("escape_stride", context.actor.actor_id, pending.target_id, f"{context.actor.label} takes the 5-foot Stride from the critical Escape.", check=pending.saved_check.result)]
        events.extend(context.encounter._advance_continuation(context.state, context.dice, continuation))
        return FamilyProcedureResult(events=tuple(events))
    return FamilyProcedureResult(unsupported="The saved choice is not an admitted skill-action continuation.")


def validate_pending(context: FamilyProcedureContext) -> None:
    pending = context.pending
    if pending is None or pending.procedure_id is None:
        raise ValueError("save has no skill-action procedure id")
    if pending.procedure_id == "skill_actions:feint:scoundrel_step":
        command = pending.family_command
        continuation = pending.continuation
        saved = pending.saved_check
        destinations = _feint_step_destinations(context)
        targeting_failure_step = continuation is not None and continuation.targeting_failed
        if (
            not isinstance(command, Feint)
            or not _is_scoundrel(context)
            or not _wielding_agile_or_finesse_melee_weapon(context)
            or not destinations
            or saved is None
            or (saved.result is None and not targeting_failure_step)
            or (targeting_failure_step and saved.result is not None)
            or saved.check_owner_actor_id != context.actor.actor_id
            or saved.context.statistic != "deception"
            or continuation is None
            or continuation.stage not in {"feint_scoundrel_step", "feint_scoundrel_step_targeting_failure"}
            or continuation.actor_id != context.actor.actor_id
            or pending.family_id != "martial"
            or pending.actor_id != context.actor.actor_id
            or pending.owner_actor_id != context.actor.actor_id
            or pending.target_id != command.target_id
            or pending.options != _feint_step_options(destinations)
        ):
            raise ValueError("save has an invalid Scoundrel Step continuation")
        return
    if pending.procedure_id.endswith(":guidance") or pending.procedure_id.endswith(":hero_point"):
        command = pending.family_command
        continuation = pending.continuation
        saved = pending.saved_check
        if not isinstance(command, (Trip, Grapple, Escape, Demoralize, Feint, TumbleThrough, QuickJump)) or saved is None or continuation is None:
            raise ValueError("save has an incomplete skill-action check choice")
        action_id = _action_id(command)
        is_guidance = pending.procedure_id == f"skill_actions:{action_id}:guidance"
        is_hero = pending.procedure_id == f"skill_actions:{action_id}:hero_point"
        expected_stage = f"{action_id}_skill_guidance" if is_guidance else f"{action_id}_skill_hero_point"
        if (
            not (is_guidance or is_hero)
            or pending.family_id != "martial"
            or pending.actor_id != context.actor.actor_id
            or pending.owner_actor_id != context.actor.actor_id
            or continuation.stage != expected_stage
            or continuation.actor_id != context.actor.actor_id
            or saved.check_owner_actor_id != context.actor.actor_id
            or saved.context.statistic != ("unarmed_attack" if isinstance(command, Escape) and command.check_method == "unarmed_attack" else _check_statistic(command))
            or (is_guidance and (saved.result is not None or not continuation.item_id))
            or (is_hero and (saved.result is None or saved.reroll_used or context.actor.health_mode.value != "pc" or context.actor.hero_points < 1))
            or (is_hero and saved.result is not None and (saved.sure_strike_used or len(saved.result.dice) > 1))
        ):
            raise ValueError("save has an invalid skill-action check choice")
        if is_guidance:
            effect = context.guidance_for()
            if effect is None or effect.effect_id != continuation.item_id:
                raise ValueError("save has a Guidance choice without its active effect")
            if {option.option_id for option in pending.options} != {"use", "keep"}:
                raise ValueError("save has invalid Guidance options")
        else:
            if {option.option_id for option in pending.options} != {"reroll", "keep"}:
                raise ValueError("save has invalid Hero Point options")
        return
    if pending.procedure_id == "skill_actions:grapple_critical_failure":
        continuation = pending.continuation
        if (
            continuation is None or continuation.stage != "grapple_critical_failure"
            or continuation.target_id not in context.state.creatures
            or pending.owner_actor_id != continuation.target_id
            or pending.saved_check is None
            or pending.saved_check.result is None
            or pending.saved_check.check_owner_actor_id != context.actor.actor_id
            or pending.saved_check.result.degree is not DegreeOfSuccess.CRITICAL_FAILURE
            or not isinstance(pending.family_command, Grapple)
            or {option.option_id for option in pending.options} != {"grab_user", "make_user_prone"}
        ):
            raise ValueError("save has an invalid Grapple critical failure choice")
        return
    if pending.procedure_id in {
        "skill_actions:trip_weapon_critical_failure",
        "skill_actions:grapple_weapon_critical_failure",
    }:
        action_trait = "trip" if pending.procedure_id.endswith("trip_weapon_critical_failure") else "grapple"
        continuation = pending.continuation
        expected_options = (
            {"drop_weapon", "accept_critical_failure"}
            if action_trait == "trip"
            else {"drop_weapon", "keep_weapon"}
        )
        if (
            continuation is None
            or continuation.stage != f"{action_trait}_weapon_critical_failure"
            or continuation.target_id not in context.state.creatures
            or continuation.item_id not in context.actor.held_items
            or pending.owner_actor_id != context.actor.actor_id
            or pending.saved_check is None
            or pending.saved_check.result is None
            or pending.saved_check.check_owner_actor_id != context.actor.actor_id
            or pending.saved_check.result.degree is not DegreeOfSuccess.CRITICAL_FAILURE
            or ((action_trait == "trip") != isinstance(pending.family_command, Trip))
            or ((action_trait == "grapple") != isinstance(pending.family_command, Grapple))
            or {option.option_id for option in pending.options} != expected_options
        ):
            raise ValueError("save has an invalid maneuver weapon critical failure choice")
        _maneuver_weapon(context, continuation.item_id, action_trait)
        return
    if pending.procedure_id == "skill_actions:escape_critical_success_stride":
        continuation = pending.continuation
        if (
            continuation is None or continuation.stage != "escape_critical_success_stride"
            or continuation.item_id is None
            or pending.saved_check is None or pending.saved_check.result is None
            or pending.saved_check.check_owner_actor_id != context.actor.actor_id
            or pending.saved_check.result.degree is not DegreeOfSuccess.CRITICAL_SUCCESS
            or not isinstance(pending.family_command, Escape)
            or not any(option.option_id == "stay" for option in pending.options)
        ):
            raise ValueError("save has an invalid Escape critical success choice")
        return
    raise ValueError("save has an unsupported skill-action choice")


def validate_targeting_pending(context: FamilyProcedureContext) -> None:
    """Validate a saved shared concealment choice for a skill action."""

    pending = context.pending
    continuation = None if pending is None else pending.continuation
    command = None if pending is None else pending.family_command
    saved = None if pending is None else pending.saved_check
    if (
        pending is None
        or continuation is None
        or not isinstance(command, (Trip, Grapple, Demoralize, Feint, TumbleThrough))
        or saved is None
        or pending.kind != "concealment_hero_reroll"
        or pending.family_id != "martial"
        or pending.procedure_id != f"skill_actions:{_action_id(command)}:concealment"
        or continuation.kind != "family_action"
        or continuation.actor_id != context.actor.actor_id
        or continuation.target_id != _command_target_id(command)
        or continuation.stage != f"{_action_id(command)}_skill_targeting"
        or not continuation.concealment_checked
        or continuation.targeting_failed
        or pending.target_id != _command_target_id(command)
        or pending.check is None
        or pending.check.dc != 5
        or pending.check.modifier != 0
        or pending.check.die is None
        or saved.check_owner_actor_id != context.actor.actor_id
        or saved.context.statistic != _check_statistic(command)
    ):
        raise ValueError("save has an invalid skill-action concealment choice")
    if pending.options != _targeting_choice_options():
        raise ValueError("save has invalid skill-action concealment options")
    use_assurance = getattr(command, "use_assurance", False)
    if type(use_assurance) is not bool:
        raise ValueError("save has an invalid Assurance flag on the targeting choice")
    if use_assurance and (
        saved.result is None or saved.result.method != "assurance"
    ):
        raise ValueError("save has an Assurance targeting choice without its fixed result")
    if "attack" in saved.context.traits:
        if not isinstance(command, (Trip, Grapple)):
            raise ValueError("save has an invalid skill-action attack targeting choice")
        if not saved.attack_count_committed or not continuation.attack_count_committed:
            raise ValueError("save has an uncommitted maneuver attack count")
        if context.actor.strikes_this_turn != continuation.attack_count:
            raise ValueError("save has an inconsistent maneuver attack count")
        expected_map = multiple_attack_penalty(continuation.attack_count - 1)
        if continuation.attack_penalty != expected_map:
            raise ValueError("save has an inconsistent maneuver MAP")
    elif continuation.attack_count or continuation.attack_penalty or saved.attack_count_committed:
        raise ValueError("save has an attack count on a non-attack skill action")
    if saved.result is not None and not use_assurance:
        raise ValueError("save has a resolved non-Assurance skill check before targeting")
