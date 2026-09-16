"""Small typed damage records and pure PF2e damage calculations.

Critical Strike damage follows Player Core p. 407. Immunity, weakness, and
resistance application follows Player Core p. 408 as revised by Spring 2026
errata. The errata says each defense applies at most once to one effect, and
that a resistance covering multiple damage types can be assigned to one
eligible type by the defender.
"""

from dataclasses import dataclass, replace
from typing import Callable


@dataclass(frozen=True)
class DamagePacket:
    source: str
    damage_type: str
    dice_sides: int
    dice_count: int
    modifier: int


@dataclass(frozen=True)
class DamageComponent:
    source: str
    damage_type: str
    dice_sides: int
    rolls: tuple[int, ...]
    modifier: int
    amount: int
    tags: frozenset[str] = frozenset()
    critical_mode: str = "double"
    dice: tuple[int, ...] = ()


@dataclass(frozen=True)
class DamageResult:
    components: tuple[DamageComponent, ...]
    rolled_total: int
    multiplier: int
    total: int
    adjustment: str | None = None


@dataclass(frozen=True)
class DamageTerm:
    source: str
    damage_type: str
    dice: tuple[int, ...]
    modifier: int = 0
    tags: frozenset[str] = frozenset()
    critical_mode: str = "double"


@dataclass(frozen=True)
class DamageDefense:
    kind: str
    applies_to: str
    value: int = 0
    exceptions: frozenset[str] = frozenset()
    source: str = ""


@dataclass(frozen=True)
class DamageGroup:
    group_id: str
    results: tuple[DamageResult, ...]
    source_kind: str
    traits: frozenset[str] = frozenset()


@dataclass(frozen=True)
class DamagePartRef:
    result_index: int
    component_index: int


@dataclass(frozen=True)
class DefenseChoice:
    defense_source: str
    eligible_parts: tuple[DamagePartRef, ...]


@dataclass(frozen=True)
class DefenseSelection:
    defense_source: str
    part: DamagePartRef


@dataclass(frozen=True)
class DamageMitigation:
    results: tuple[DamageResult, ...]
    total: int
    applied_defenses: tuple[str, ...]
    unresolved_choices: tuple[DefenseChoice, ...] = ()


@dataclass(frozen=True)
class TemporaryHPResult:
    temporary_hp: int
    damage_to_hp: int
    absorbed: int


_CRITICAL_MODES = frozenset({"double", "unchanged", "critical_only"})
_DEFENSE_KINDS = frozenset({"immunity", "weakness", "resistance"})
_PHYSICAL_TYPES = frozenset({"bludgeoning", "piercing", "slashing"})
_DAMAGE_TYPES = frozenset(
    {
        "acid",
        "bleed",
        "bludgeoning",
        "cold",
        "electricity",
        "fire",
        "force",
        "mental",
        "piercing",
        "poison",
        "precision",
        "slashing",
        "sonic",
        "spirit",
        "vitality",
        "void",
        "untyped",
    }
)
_BROAD_RESISTANCES = frozenset({"all", "physical", "spell"})


def resolve_damage(packet: DamagePacket, roll: Callable[[int], int], *, critical: bool = False) -> DamageResult:
    """Roll dice and add the modifier, then double the complete total on a crit."""
    if packet.dice_sides < 2 or packet.dice_count < 1:
        raise ValueError("damage dice must have at least 2 sides and at least one die")
    rolls = tuple(roll(packet.dice_sides) for _ in range(packet.dice_count))
    if any(type(face) is not int or not 1 <= face <= packet.dice_sides for face in rolls):
        raise ValueError("damage die result is outside its die's range")
    rolled_total = sum(rolls) + packet.modifier
    multiplier = 2 if critical else 1
    total = rolled_total * multiplier
    component = DamageComponent(
        source=packet.source,
        damage_type=packet.damage_type,
        dice_sides=packet.dice_sides,
        rolls=rolls,
        modifier=packet.modifier,
        amount=total,
        dice=(packet.dice_sides,) * packet.dice_count,
    )
    return DamageResult((component,), rolled_total, multiplier, total)


def roll_damage_terms(
    terms: tuple[DamageTerm, ...], roll: Callable[[int], int], *, critical: bool = False
) -> DamageResult:
    """Roll typed terms while applying each term's own critical treatment.

    ``double`` terms double dice and modifier on a critical hit. ``unchanged``
    terms are present once even on a critical hit (for example, bomb splash).
    ``critical_only`` terms are rolled and added only on a critical hit (for
    example, a deadly die). This function models damage terms only; the caller
    still supplies attack-specific minimum damage and basic-save adjustments.
    """
    if not isinstance(terms, tuple):
        raise ValueError("damage terms must be a tuple")
    components: list[DamageComponent] = []
    rolled_total = 0
    for term in terms:
        _validate_term(term)
        should_roll = term.critical_mode != "critical_only" or critical
        rolls = tuple(roll(sides) for sides in term.dice) if should_roll else ()
        for sides, face in zip(term.dice, rolls):
            if type(face) is not int or not 1 <= face <= sides:
                raise ValueError("damage die result is outside its die's range")

        raw = sum(rolls) + term.modifier if should_roll else 0
        rolled_total += raw
        multiplier = 2 if critical and term.critical_mode == "double" else 1
        amount = raw * multiplier if should_roll else 0
        components.append(
            DamageComponent(
                source=term.source,
                damage_type=term.damage_type,
                dice_sides=term.dice[0] if term.dice else 0,
                rolls=rolls,
                modifier=term.modifier,
                amount=amount,
                tags=term.tags,
                critical_mode=term.critical_mode,
                dice=term.dice,
            )
        )
    return DamageResult(
        components=tuple(components),
        rolled_total=rolled_total,
        multiplier=2 if critical else 1,
        total=sum(component.amount for component in components),
    )


def damage_defense_choices(
    group: DamageGroup, defenses: tuple[DamageDefense, ...]
) -> tuple[DefenseChoice, ...]:
    """Return the unresolved multi-type resistance choices for this effect.

    A category resistance such as physical, spell, or all can cover more than
    one damage type. The rules let the defender choose which eligible type to
    resist. This function exposes the eligible parts so the caller can ask;
    it never picks the type with the largest damage on the defender's behalf.
    """
    _validate_group(group)
    normalized = _normalize_defenses(defenses)
    amounts = _initial_amounts(group)
    _apply_immunities(group, normalized, amounts)
    _apply_weaknesses(group, normalized, amounts, applied=None)
    return tuple(
        choice
        for defense_index, defense in enumerate(normalized)
        if defense.kind == "resistance"
        if (choice := _resistance_choice(group, defense_index, defense, amounts)) is not None
    )


def apply_damage_defenses(
    group: DamageGroup,
    defenses: tuple[DamageDefense, ...],
    selections: tuple[DefenseSelection, ...] = (),
) -> DamageMitigation:
    """Apply immunities, then weaknesses, then resistances to one effect group.

    A ``DamageGroup`` is the rules-defined effect boundary. Separate strikes
    and separate recipients need separate groups; a caller can combine damage
    results such as Flurry or bomb primary-plus-splash when their source rules
    say defenses see one effect. Repeated components do not multiply a single
    weakness or resistance.

    Broad resistance choices that are absent from ``selections`` remain
    unapplied and are returned in ``unresolved_choices``. A selection chooses
    a damage type through one eligible component; resistance is then applied
    once across eligible damage of that type. Same-type resistances do not
    stack: the strongest selected resistance for that type applies.
    """
    _validate_group(group)
    normalized = _normalize_defenses(defenses)
    selection_by_source = _normalize_selections(selections)
    known_sources = {_defense_source(defense, index) for index, defense in enumerate(normalized)}
    unknown = set(selection_by_source) - known_sources
    if unknown:
        raise ValueError(f"selection names unknown defense source: {sorted(unknown)[0]}")

    amounts = _initial_amounts(group)
    applied: list[str] = []
    _apply_immunities(group, normalized, amounts, applied)
    _apply_weaknesses(group, normalized, amounts, applied)

    candidates: list[tuple[int, DamageDefense, str]] = []
    unresolved: list[DefenseChoice] = []
    consumed_selections: set[str] = set()
    for defense_index, defense in enumerate(normalized):
        if defense.kind != "resistance":
            continue
        source = _defense_source(defense, defense_index)
        choice = _resistance_choice(group, defense_index, defense, amounts)
        eligible = _eligible_parts(group, defense, amounts)
        if not eligible:
            if source in selection_by_source:
                raise ValueError(f"selection supplied for ineligible defense: {source}")
            continue

        selected = selection_by_source.get(source)
        if choice is not None:
            if selected is None:
                unresolved.append(choice)
                continue
            if selected.part not in choice.eligible_parts:
                raise ValueError(f"selected part is not eligible for defense: {source}")
            consumed_selections.add(source)
            selected_type = _component_at(group, selected.part).damage_type.casefold()
        else:
            if selected is not None:
                raise ValueError(f"selection supplied for a defense with no choice: {source}")
            selected_type = group.results[eligible[0].result_index].components[
                eligible[0].component_index
            ].damage_type.casefold()

        candidates.append((defense_index, defense, selected_type))

    unused = set(selection_by_source) - consumed_selections
    if unused:
        source = sorted(unused)[0]
        raise ValueError(f"selection supplied for a defense with no unresolved choice: {source}")

    # Multiple resistances against the same damage type use only one. Select
    # the greatest value, with input order as the deterministic tie-breaker.
    damage_types: list[str] = []
    for _, _, selected_type in candidates:
        if selected_type not in damage_types:
            damage_types.append(selected_type)
    for damage_type in damage_types:
        matching = [
            item
            for item in candidates
            if item[2] == damage_type
            and any(
                group.results[part.result_index].components[part.component_index].damage_type.casefold()
                == damage_type
                for part in _eligible_parts(group, item[1], amounts)
            )
        ]
        if not matching:
            continue
        defense_index, defense, _ = max(
            matching, key=lambda item: (item[1].value, -item[0])
        )
        eligible = tuple(
            part
            for part in _eligible_parts(group, defense, amounts)
            if _component_at(group, part).damage_type.casefold() == damage_type
        )
        if _reduce_parts(group, amounts, eligible, defense.value):
            applied.append(_defense_source(defense, defense_index))

    results = _results_with_amounts(group, amounts)
    return DamageMitigation(
        results=results,
        total=sum(result.total for result in results),
        applied_defenses=tuple(applied),
        unresolved_choices=tuple(unresolved),
    )


def absorb_temporary_hp(amount: int, temporary_hp: int) -> TemporaryHPResult:
    """Apply incoming damage to temporary HP first, leaving HP damage separate."""
    if type(amount) is not int or amount < 0:
        raise ValueError("damage amount must be a non-negative integer")
    if type(temporary_hp) is not int or temporary_hp < 0:
        raise ValueError("temporary HP must be a non-negative integer")
    absorbed = min(amount, temporary_hp)
    return TemporaryHPResult(
        temporary_hp=temporary_hp - absorbed,
        damage_to_hp=amount - absorbed,
        absorbed=absorbed,
    )


def _validate_term(term: DamageTerm) -> None:
    if not isinstance(term, DamageTerm):
        raise ValueError("every damage term must be a DamageTerm")
    if not isinstance(term.source, str) or not term.source:
        raise ValueError("damage term source must be a non-empty string")
    if not isinstance(term.damage_type, str) or not term.damage_type:
        raise ValueError("damage type must be a non-empty string")
    if not isinstance(term.dice, tuple) or any(
        type(sides) is not int or sides < 2 for sides in term.dice
    ):
        raise ValueError("damage term dice must be a tuple of die sizes of at least 2")
    if type(term.modifier) is not int:
        raise ValueError("damage modifier must be an integer")
    if not isinstance(term.tags, frozenset) or any(not isinstance(tag, str) for tag in term.tags):
        raise ValueError("damage term tags must be a frozenset of strings")
    if term.critical_mode not in _CRITICAL_MODES:
        raise ValueError(f"unsupported critical mode: {term.critical_mode}")


def _validate_group(group: DamageGroup) -> None:
    if not isinstance(group, DamageGroup):
        raise ValueError("damage group must be a DamageGroup")
    if not group.group_id or not isinstance(group.group_id, str):
        raise ValueError("damage group id must be a non-empty string")
    if not group.source_kind or not isinstance(group.source_kind, str):
        raise ValueError("damage group source kind must be a non-empty string")
    if not isinstance(group.results, tuple):
        raise ValueError("damage group results must be a tuple")
    if not isinstance(group.traits, frozenset) or any(
        not isinstance(trait, str) for trait in group.traits
    ):
        raise ValueError("damage group traits must be a frozenset of strings")
    for result in group.results:
        if not isinstance(result, DamageResult) or not isinstance(result.components, tuple):
            raise ValueError("damage group must contain DamageResult values")
        for component in result.components:
            if not isinstance(component, DamageComponent):
                raise ValueError("damage results must contain DamageComponent values")
            if type(component.amount) is not int:
                raise ValueError("damage component amount must be an integer")


def _normalize_defenses(defenses: tuple[DamageDefense, ...]) -> tuple[DamageDefense, ...]:
    if not isinstance(defenses, tuple):
        raise ValueError("damage defenses must be a tuple")
    seen_sources: set[str] = set()
    for index, defense in enumerate(defenses):
        if not isinstance(defense, DamageDefense):
            raise ValueError("every damage defense must be a DamageDefense")
        if defense.kind not in _DEFENSE_KINDS:
            raise ValueError(f"unsupported damage defense kind: {defense.kind}")
        if not isinstance(defense.applies_to, str) or not defense.applies_to:
            raise ValueError("damage defense applies_to must be a non-empty string")
        if type(defense.value) is not int or defense.value < 0:
            raise ValueError("damage defense value must be a non-negative integer")
        if defense.kind != "immunity" and defense.value < 1:
            raise ValueError("weakness and resistance values must be positive")
        if not isinstance(defense.exceptions, frozenset) or any(
            not isinstance(exception, str) for exception in defense.exceptions
        ):
            raise ValueError("damage defense exceptions must be a frozenset of strings")
        if not isinstance(defense.source, str):
            raise ValueError("damage defense source must be a string")
        source = _defense_source(defense, index)
        if source in seen_sources:
            raise ValueError(f"damage defense sources must be unique: {source}")
        seen_sources.add(source)
    return defenses


def _normalize_selections(
    selections: tuple[DefenseSelection, ...],
) -> dict[str, DefenseSelection]:
    if not isinstance(selections, tuple):
        raise ValueError("defense selections must be a tuple")
    result: dict[str, DefenseSelection] = {}
    for selection in selections:
        if not isinstance(selection, DefenseSelection):
            raise ValueError("every selection must be a DefenseSelection")
        if not isinstance(selection.defense_source, str) or not selection.defense_source:
            raise ValueError("selection defense_source must be a non-empty string")
        if selection.defense_source in result:
            raise ValueError(f"duplicate selection for defense: {selection.defense_source}")
        if not isinstance(selection.part, DamagePartRef):
            raise ValueError("selection part must be a DamagePartRef")
        result[selection.defense_source] = selection
    return result


def _defense_source(defense: DamageDefense, index: int) -> str:
    return defense.source or f"{defense.kind}:{defense.applies_to}[{index}]"


def _initial_amounts(group: DamageGroup) -> list[list[int]]:
    return [[component.amount for component in result.components] for result in group.results]


def _apply_immunities(
    group: DamageGroup,
    defenses: tuple[DamageDefense, ...],
    amounts: list[list[int]],
    applied: list[str] | None = None,
) -> None:
    for defense_index, defense in enumerate(defenses):
        if defense.kind != "immunity":
            continue
        changed = False
        for part in _matching_parts(group, defense, amounts):
            result_index, component_index = part.result_index, part.component_index
            if amounts[result_index][component_index] != 0:
                amounts[result_index][component_index] = 0
                changed = True
        if changed and applied is not None:
            applied.append(_defense_source(defense, defense_index))


def _apply_weaknesses(
    group: DamageGroup,
    defenses: tuple[DamageDefense, ...],
    amounts: list[list[int]],
    applied: list[str] | None,
) -> None:
    for defense_index, defense in enumerate(defenses):
        if defense.kind != "weakness":
            continue
        eligible = _eligible_parts(group, defense, amounts)
        if not eligible:
            continue
        # The weakness belongs to the effect, so add it once. Attribute it to
        # the first qualifying component in stable source/result order.
        first = eligible[0]
        amounts[first.result_index][first.component_index] += defense.value
        if applied is not None:
            applied.append(_defense_source(defense, defense_index))


def _resistance_choice(
    group: DamageGroup,
    defense_index: int,
    defense: DamageDefense,
    amounts: list[list[int]],
) -> DefenseChoice | None:
    eligible = _eligible_parts(group, defense, amounts)
    if defense.kind != "resistance" or not eligible:
        return None
    damage_types = {_component_at(group, part).damage_type.casefold() for part in eligible}
    if len(damage_types) <= 1:
        return None
    if defense.applies_to.casefold() not in _BROAD_RESISTANCES and not _matches_many_types_by_trait(
        group, defense, eligible
    ):
        return None
    return DefenseChoice(_defense_source(defense, defense_index), eligible)


def _matches_many_types_by_trait(
    group: DamageGroup, defense: DamageDefense, eligible: tuple[DamagePartRef, ...]
) -> bool:
    """A non-damage-type characteristic can also span several damage types."""
    applies_to = defense.applies_to.casefold()
    if applies_to in _DAMAGE_TYPES or applies_to in _PHYSICAL_TYPES:
        return False
    return any(
        applies_to in {tag.casefold() for tag in _component_at(group, part).tags}
        or applies_to in {trait.casefold() for trait in group.traits}
        for part in eligible
    )


def _eligible_parts(
    group: DamageGroup, defense: DamageDefense, amounts: list[list[int]]
) -> tuple[DamagePartRef, ...]:
    return tuple(
        part
        for part in _matching_parts(group, defense, amounts)
        if amounts[part.result_index][part.component_index] > 0
    )


def _matching_parts(
    group: DamageGroup, defense: DamageDefense, amounts: list[list[int]]
) -> tuple[DamagePartRef, ...]:
    applies_to = defense.applies_to.casefold()
    exceptions = {value.casefold() for value in defense.exceptions}
    matches: list[DamagePartRef] = []
    for result_index, result in enumerate(group.results):
        for component_index, component in enumerate(result.components):
            damage_type = component.damage_type.casefold()
            tags = {tag.casefold() for tag in component.tags}
            traits = {trait.casefold() for trait in group.traits}
            if exceptions.intersection({damage_type, *tags, *traits}):
                continue
            if applies_to == "all":
                eligible = True
            elif applies_to == "physical":
                eligible = damage_type in _PHYSICAL_TYPES
            elif applies_to == "spell":
                eligible = group.source_kind.casefold() == "spell" or "spell" in traits
            elif applies_to == "precision":
                eligible = damage_type == "precision" or "precision" in tags
            elif applies_to in _PHYSICAL_TYPES:
                eligible = damage_type == applies_to
            elif applies_to in _DAMAGE_TYPES:
                eligible = damage_type == applies_to
            else:
                eligible = damage_type == applies_to or applies_to in tags or applies_to in traits
            if eligible:
                matches.append(DamagePartRef(result_index, component_index))

    # A trait on the complete effect can activate a defense even when no term
    # repeats that trait. Keep the effect-level match, while still returning a
    # concrete eligible part for attribution and a possible type selection.
    if applies_to not in _DAMAGE_TYPES and applies_to not in _BROAD_RESISTANCES and applies_to in {
        trait.casefold() for trait in group.traits
    } and not any(
        applies_to in {tag.casefold() for tag in component.tags}
        or component.damage_type.casefold() == applies_to
        for result in group.results
        for component in result.components
    ):
        for result_index, row in enumerate(amounts):
            for component_index, amount in enumerate(row):
                component = group.results[result_index].components[component_index]
                component_tags = {tag.casefold() for tag in component.tags}
                component_traits = {trait.casefold() for trait in group.traits}
                if amount > 0 and not exceptions.intersection(
                    {component.damage_type.casefold(), *component_tags, *component_traits}
                ):
                    part = DamagePartRef(result_index, component_index)
                    if part not in matches:
                        matches.append(part)
    return tuple(matches)


def _component_at(group: DamageGroup, part: DamagePartRef) -> DamageComponent:
    if (
        type(part.result_index) is not int
        or type(part.component_index) is not int
        or not 0 <= part.result_index < len(group.results)
        or not 0 <= part.component_index < len(group.results[part.result_index].components)
    ):
        raise ValueError("damage part reference is outside the group")
    return group.results[part.result_index].components[part.component_index]


def _reduce_parts(
    group: DamageGroup,
    amounts: list[list[int]],
    parts: tuple[DamagePartRef, ...],
    value: int,
) -> bool:
    remaining = value
    reduced = False
    for part in parts:
        if remaining <= 0:
            break
        current = amounts[part.result_index][part.component_index]
        reduction = min(current, remaining)
        if reduction:
            amounts[part.result_index][part.component_index] -= reduction
            remaining -= reduction
            reduced = True
    return reduced


def _results_with_amounts(
    group: DamageGroup, amounts: list[list[int]]
) -> tuple[DamageResult, ...]:
    results: list[DamageResult] = []
    for result, row in zip(group.results, amounts):
        components = tuple(
            replace(component, amount=amount)
            for component, amount in zip(result.components, row)
        )
        results.append(replace(result, components=components, total=sum(row)))
    return tuple(results)
