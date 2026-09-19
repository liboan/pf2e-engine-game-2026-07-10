"""Pure condition projections for the explicitly admitted PF2e effects.

Condition records are source-relative: ``source_id`` identifies one retained
cause. The caller must pass only conditions applicable to the check/action
being queried when a rule depends on a target or circumstance (notably
off-guard and dazzled). The helpers never inspect encounter state or roll.

Supported rules were checked against the Player Core Remaster condition
entries and selected PC1/PC2 class-family notes:

* clumsy: https://2e.aonprd.com/Conditions.aspx?ID=61
* drained: https://2e.aonprd.com/Conditions.aspx?ID=68
* dazzled: https://2e.aonprd.com/Conditions.aspx?ID=65
* enfeebled: https://2e.aonprd.com/Conditions.aspx?ID=71
* fascinated: https://2e.aonprd.com/Conditions.aspx?ID=72
* fatigued: https://2e.aonprd.com/Conditions.aspx?ID=73
* frightened: https://2e.aonprd.com/Conditions.aspx?ID=76
* grabbed: https://2e.aonprd.com/Conditions.aspx?ID=77
* immobilized: https://2e.aonprd.com/Conditions.aspx?ID=81
* off-guard: https://2e.aonprd.com/Conditions.aspx?ID=58
* paralyzed: https://2e.aonprd.com/Conditions.aspx?ID=85
* prone: https://2e.aonprd.com/Conditions.aspx?ID=88
* restrained: https://2e.aonprd.com/Conditions.aspx?ID=90
* sickened: https://2e.aonprd.com/Conditions.aspx?ID=91
* stupefied: https://2e.aonprd.com/Conditions.aspx?ID=94

The official Paizo FAQ/errata is also used for the current clumsy interaction
with Dexterity-based damage rolls: https://paizo.com/pathfinder/faq
"""

from __future__ import annotations

from dataclasses import dataclass

from .checks import Modifier


@dataclass(frozen=True)
class ConditionValue:
    """One retained condition contribution from one source.

    Value-less conditions use ``1`` as their presence value. Valued conditions
    carry their current value. Multiple sources stay separate so that the
    owning state layer can expire or reduce them independently.
    """

    kind: str
    value: int
    source_id: str


@dataclass(frozen=True)
class CheckContext:
    """The statistic and explicit ability used for a check or damage roll.

    ``attribute`` is provided by the caller; helpers never infer it from the
    name of an attack or statistic. ``traits`` are the PF2e traits of the
    specific check/effect.
    """

    statistic: str
    attribute: str | None
    traits: frozenset[str] = frozenset()


@dataclass(frozen=True)
class ActionContext:
    """One concrete action query; traits are PF2e action/effect traits.

    The small normalized action IDs used here are documented by
    :func:`condition_restrictions`; they are engine context identifiers, not
    additional PF2e traits.
    """

    action_id: str
    traits: frozenset[str] = frozenset()


_VALUED_CONDITIONS = frozenset(
    {
        "clumsy",
        "drained",
        "enfeebled",
        "frightened",
        "sickened",
        "speed_penalty",
        "stupefied",
    }
)

_SUPPORTED_CONDITIONS = _VALUED_CONDITIONS | frozenset(
    {
        "dazzled",
        "fascinated",
        "fatigued",
        "grabbed",
        "immobilized",
        "off_guard",
        "paralyzed",
        "prone",
        "restrained",
        "speed_penalty",
    }
)
_PRESENCE_CONDITIONS = _SUPPORTED_CONDITIONS - _VALUED_CONDITIONS

_DAMAGE_STATISTICS = frozenset({"damage", "damage_roll"})
_SAVING_THROW_STATISTICS = frozenset({"fortitude", "reflex", "will"})
_MENTAL_ATTRIBUTES = frozenset({"intelligence", "wisdom", "charisma"})
_SKILL_STATISTICS = frozenset(
    {
        "acrobatics",
        "arcana",
        "athletics",
        "crafting",
        "deception",
        "diplomacy",
        "intimidation",
        "medicine",
        "nature",
        "occultism",
        "perception",
        "performance",
        "religion",
        "society",
        "stealth",
        "survival",
        "thievery",
    }
)


def condition_modifiers(
    conditions: tuple[ConditionValue, ...], context: CheckContext
) -> tuple[Modifier, ...]:
    """Return every applicable typed modifier; stacking remains in checks.py.

    Status penalties are emitted per source. ``combine_modifiers`` chooses
    the worst same-type penalty, while circumstance off-guard penalties from
    several causes likewise do not multiply. Conditions that change HP, speed,
    turn actions, or state transitions are outside this check helper.
    """
    _validate_conditions(conditions)
    _validate_check_context(context)

    modifiers: list[Modifier] = []
    for condition in conditions:
        if condition.value == 0:
            continue
        amount: int | None = None
        modifier_type = "status"

        if condition.kind in {"off_guard", "prone", "grabbed", "restrained", "paralyzed"}:
            if context.statistic == "armor_class":
                amount = -2
                modifier_type = "circumstance"
            elif condition.kind == "prone" and "attack" in context.traits:
                amount = -2
                modifier_type = "circumstance"
        elif condition.kind == "clumsy":
            if (
                context.attribute == "dexterity"
                or context.statistic in {"armor_class", "reflex"}
            ):
                amount = -condition.value
        elif condition.kind == "drained":
            if context.attribute == "constitution" or context.statistic == "fortitude":
                amount = -condition.value
        elif condition.kind == "enfeebled":
            if context.attribute == "strength":
                amount = -condition.value
        elif condition.kind in {"frightened", "sickened"}:
            if context.statistic not in _DAMAGE_STATISTICS:
                amount = -condition.value
        elif condition.kind == "fatigued":
            if context.statistic == "armor_class" or context.statistic in _SAVING_THROW_STATISTICS:
                amount = -1
        elif condition.kind == "stupefied":
            if context.statistic not in _DAMAGE_STATISTICS and (
                context.attribute in _MENTAL_ATTRIBUTES
                or context.statistic in {"will", "spell_attack", "spell_dc"}
            ):
                amount = -condition.value
        elif condition.kind == "fascinated":
            if _is_skill_check(context.statistic):
                amount = -2
        elif condition.kind in {"dazzled", "grabbed", "immobilized", "paralyzed", "restrained", "speed_penalty"}:
            # These conditions have action/target restrictions, handled by
            # condition_restrictions or by core-owned state procedures.
            pass
        else:  # guarded by _validate_conditions; keeps additions fail-closed.
            raise ValueError(f"unsupported condition kind: {condition.kind!r}")

        if amount is not None and amount != 0:
            modifiers.append(
                Modifier(
                    amount,
                    modifier_type,
                    f"condition:{condition.kind}:{condition.source_id}",
                )
            )

    return tuple(modifiers)


def condition_restrictions(
    conditions: tuple[ConditionValue, ...], context: ActionContext
) -> tuple[str, ...]:
    """Return stable restriction/check identifiers without rolling.

    Core action IDs used by this helper are ``ingest``,
    ``traveling_exploration_activity``, ``cast_spell``, ``crawl``, ``stand``,
    ``escape``, ``force_open``, and ``recall_knowledge``. Other action IDs are
    passed through unchanged. The returned identifiers say what core must
    reject or resolve (including any required flat check); they are not prose
    and do not trigger a hidden roll.

    For dazzled and fascinated, core must pass only explicitly applicable
    condition facts when target visibility or relation to the fascination
    subject has been established. A dazzled result asks core for its DC 5
    targeting flat check; stupefied's Cast a Spell flat-check DC is
    ``5 + effective_condition_value``.
    """
    _validate_conditions(conditions)
    _validate_action_context(context)

    reasons: set[str] = set()
    traits = context.traits

    for condition in conditions:
        if condition.value == 0:
            continue
        kind = condition.kind
        if kind == "sickened" and context.action_id == "ingest":
            reasons.add("sickened_willing_ingestion_prohibited")
        elif kind == "fatigued" and context.action_id == "traveling_exploration_activity":
            reasons.add("fatigued_traveling_exploration_prohibited")
        elif kind == "dazzled":
            reasons.add("dazzled_target_flat_check_dc5_required")
        elif kind == "stupefied" and context.action_id == "cast_spell":
            reasons.add("stupefied_cast_flat_check_dc5_plus_value_required")
        elif kind == "grabbed":
            if "move" in traits:
                reasons.add("immobilized_move_action_prohibited")
            if "manipulate" in traits:
                reasons.add("grabbed_manipulate_flat_check_dc5_required")
        elif kind == "fascinated" and "concentrate" in traits:
            reasons.add("fascinated_concentrate_subject_relation_required")
        elif kind == "prone" and "move" in traits and context.action_id not in {"crawl", "stand"}:
            reasons.add("prone_move_action_prohibited")
        elif kind == "immobilized" and "move" in traits:
            reasons.add("immobilized_move_action_prohibited")
        elif kind == "restrained":
            if "move" in traits:
                reasons.add("immobilized_move_action_prohibited")
            if (
                ("attack" in traits or "manipulate" in traits)
                and context.action_id not in {"escape", "force_open"}
            ):
                reasons.add("restrained_attack_or_manipulate_prohibited")
        elif kind == "paralyzed" and context.action_id != "recall_knowledge":
            # Core has the complete action definition and decides whether this
            # action requires only the mind; this helper never infers that fact.
            reasons.add("paralyzed_requires_mind_only_action")

    return tuple(sorted(reasons))


def effective_condition_value(conditions: tuple[ConditionValue, ...], kind: str) -> int:
    """Return the greatest retained value for a kind, or zero when absent."""
    if kind not in _SUPPORTED_CONDITIONS:
        raise ValueError(f"unsupported condition kind: {kind!r}")
    _validate_conditions(conditions)
    return max((condition.value for condition in conditions if condition.kind == kind), default=0)


def _is_skill_check(statistic: str) -> bool:
    return statistic in _SKILL_STATISTICS or statistic.endswith("_lore")


def _validate_conditions(conditions: tuple[ConditionValue, ...]) -> None:
    if not isinstance(conditions, tuple):
        raise TypeError("conditions must be a tuple")
    for condition in conditions:
        if not isinstance(condition, ConditionValue):
            raise TypeError("conditions must contain ConditionValue records")
        if condition.kind not in _SUPPORTED_CONDITIONS:
            raise ValueError(f"unsupported condition kind: {condition.kind!r}")
        if type(condition.value) is not int or condition.value < 0:
            raise ValueError("condition values must be non-negative integers")
        if condition.kind in _PRESENCE_CONDITIONS and condition.value != 1:
            raise ValueError("value-less conditions use 1 as their presence value")
        if not isinstance(condition.source_id, str) or not condition.source_id:
            raise ValueError("condition source_id must be a non-empty string")


def _validate_check_context(context: CheckContext) -> None:
    if not isinstance(context, CheckContext):
        raise TypeError("context must be a CheckContext")
    if not isinstance(context.statistic, str) or not context.statistic:
        raise ValueError("check statistic must be a non-empty string")
    if context.attribute is not None and (not isinstance(context.attribute, str) or not context.attribute):
        raise ValueError("check attribute must be None or a non-empty string")
    if not isinstance(context.traits, frozenset) or any(not isinstance(trait, str) or not trait for trait in context.traits):
        raise ValueError("check traits must be a frozenset of non-empty strings")


def _validate_action_context(context: ActionContext) -> None:
    if not isinstance(context, ActionContext):
        raise TypeError("context must be an ActionContext")
    if not isinstance(context.action_id, str) or not context.action_id:
        raise ValueError("action_id must be a non-empty string")
    if not isinstance(context.traits, frozenset) or any(not isinstance(trait, str) or not trait for trait in context.traits):
        raise ValueError("action traits must be a frozenset of non-empty strings")
