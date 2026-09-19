"""Pure spell-access and expenditure checks for explicit casting snapshots.

Rules checked 2026-09-15 against Player Core, pp. 297–298 (spell slots,
cantrips, focus pools, innate spells, and Refocus), and GM Core, p. 278
(staves):

* https://2e.aonprd.com/Rules.aspx?ID=2221
* https://2e.aonprd.com/Rules.aspx?ID=3211
* https://2e.aonprd.com/Actions.aspx?ID=2621

The caller supplies admitted spell ranks and the casting statistics belonging
to each source. This module does not learn spells, infer heightened access from
spell slots, perform daily preparation, check casting actions, or apply spell
effects. In particular, class spellbook/repertoire/curriculum budgets are an
input-content responsibility, not a helper rule.
"""

from __future__ import annotations

from dataclasses import dataclass, replace


@dataclass(frozen=True, slots=True)
class SpellAccess:
    """A spell and rank explicitly admitted by one casting source."""

    spell_id: str
    rank: int
    cantrip: bool = False
    signature: bool = False


@dataclass(frozen=True, slots=True)
class CastingSource:
    """One source's spell access and actual spell attack/DC statistics.

    ``kind`` is one of ``prepared``, ``spontaneous``, ``focus``, ``innate``,
    or ``staff``. Staff spell access is an explicit snapshot of the spells the
    caster can currently cast from that staff; the caller establishes the
    staff's association, tradition, and casting statistics.
    """

    source_id: str
    kind: str
    tradition: str | None
    attribute: str | None
    attack_modifier: int
    dc: int
    spells: tuple[SpellAccess, ...]


@dataclass(frozen=True, slots=True)
class CastingResource:
    """Current immutable view of one owned casting resource.

    ``source_id`` is ``None`` only for the actor's single shared focus pool.
    Staff charges are an additive resource kind, ``staff_charges``.
    """

    resource_id: str
    source_id: str | None
    kind: str
    rank: int
    capacity: int
    remaining: int
    spell_id: str | None = None


@dataclass(frozen=True, slots=True)
class CastSelection:
    """The exact source, known rank, and resource choices for a cast.

    `resource_id` identifies the ordinary expenditure. When a spontaneous
    caster supplements a staff cast, `supplemental_resource_id` identifies the
    spell slot spent alongside one staff charge.
    """

    source_id: str
    spell_id: str
    rank: int
    resource_id: str | None
    supplemental_resource_id: str | None = None


@dataclass(frozen=True, slots=True)
class ResourceSpend:
    """A precise amount to commit from one selected resource."""

    resource_id: str
    amount: int


@dataclass(frozen=True, slots=True)
class CastPermission:
    """Validated cast selection and exact resources to spend."""

    selection: CastSelection
    spends: tuple[ResourceSpend, ...]


class CastSelectionError(ValueError):
    """Invalid cast request with a stable machine-readable ``reason``."""

    def __init__(self, reason: str, message: str | None = None) -> None:
        self.reason = reason
        super().__init__(message or reason.replace("_", " "))


_SOURCE_KINDS = frozenset({"prepared", "spontaneous", "focus", "innate", "staff"})
_RESOURCE_SOURCE_KIND = {
    "prepared_slot": "prepared",
    "rank_slots": "spontaneous",
    "innate_uses": "innate",
    "staff_charges": "staff",
}
_RESOURCE_KINDS = frozenset((*_RESOURCE_SOURCE_KIND, "focus_points"))


def available_casts(
    sources: tuple[CastingSource, ...],
    resources: tuple[CastingResource, ...],
) -> tuple[CastSelection, ...]:
    """List currently legal source/spell/rank/resource combinations.

    Repeatable cantrips have ``resource_id=None`` and no expenditure. Limited
    casts include each eligible resource ID, so prepared slots with different
    origins (for example, ordinary slots and font slots) remain distinguishable.
    """
    source_by_id, resources_by_id = _index_snapshots(sources, resources)
    del source_by_id  # validation above also checks each resource's owner kind
    choices: list[CastSelection] = []

    for source in sources:
        for access in source.spells:
            if access.cantrip:
                choices.append(CastSelection(source.source_id, access.spell_id, access.rank, None))
                continue

            if source.kind == "prepared":
                choices.extend(
                    CastSelection(source.source_id, access.spell_id, access.rank, resource.resource_id)
                    for resource in resources
                    if _prepared_slot_matches(resource, source, access) and resource.remaining > 0
                )
            elif source.kind == "spontaneous":
                choices.extend(
                    CastSelection(source.source_id, access.spell_id, access.rank, resource.resource_id)
                    for resource in resources
                    if _rank_slot_matches(resource, source, access.rank) and resource.remaining > 0
                )
            elif source.kind == "focus":
                choices.extend(
                    CastSelection(source.source_id, access.spell_id, access.rank, resource.resource_id)
                    for resource in resources
                    if resource.kind == "focus_points" and resource.remaining > 0
                )
            elif source.kind == "innate":
                choices.extend(
                    CastSelection(source.source_id, access.spell_id, access.rank, resource.resource_id)
                    for resource in resources
                    if _innate_use_matches(resource, source, access) and resource.remaining > 0
                )
            elif source.kind == "staff":
                choices.extend(
                    CastSelection(source.source_id, access.spell_id, access.rank, resource.resource_id)
                    for resource in resources
                    if _staff_charge_matches(resource, source) and resource.remaining >= access.rank
                )
                # A spontaneous caster can spend one staff charge plus one
                # spell slot to cast a staff spell of the slot's rank or lower.
                # Each resource ID remains an explicit player choice.
                for charges in resources:
                    if not _staff_charge_matches(charges, source) or charges.remaining < 1:
                        continue
                    for slot in resources:
                        if (
                            _RESOURCE_SOURCE_KIND.get(slot.kind) == "spontaneous"
                            and slot.remaining > 0
                            and slot.rank >= access.rank
                        ):
                            choices.append(
                                CastSelection(
                                    source.source_id,
                                    access.spell_id,
                                    access.rank,
                                    charges.resource_id,
                                    supplemental_resource_id=slot.resource_id,
                                )
                            )

    return tuple(choices)


def validate_cast(
    selection: CastSelection,
    sources: tuple[CastingSource, ...],
    resources: tuple[CastingResource, ...],
) -> CastPermission:
    """Validate one explicit cast and return the exact resource spend.

    A limited cast must name its resource even when only one is currently
    available. This preserves provenance and leaves all choice to the caller.
    ``SpellAccess.signature`` is descriptive: it does not admit an unlisted rank.
    """
    if not isinstance(selection, CastSelection):
        raise CastSelectionError("invalid_selection", "cast selection must be a CastSelection record")
    if (
        not isinstance(selection.source_id, str)
        or not isinstance(selection.spell_id, str)
        or (selection.resource_id is not None and not isinstance(selection.resource_id, str))
        or (
            selection.supplemental_resource_id is not None
            and not isinstance(selection.supplemental_resource_id, str)
        )
    ):
        raise CastSelectionError("invalid_selection", "selection IDs must be strings")
    source_by_id, resource_by_id = _index_snapshots(sources, resources)
    source = source_by_id.get(selection.source_id)
    if source is None:
        raise CastSelectionError("unknown_source", f"unknown casting source {selection.source_id!r}")
    if type(selection.rank) is not int or selection.rank < 1 or not selection.spell_id:
        raise CastSelectionError("invalid_spell_selection", "spell selection needs an ID and positive rank")

    access = next(
        (
            item
            for item in source.spells
            if item.spell_id == selection.spell_id and item.rank == selection.rank
        ),
        None,
    )
    if access is None:
        if any(item.spell_id == selection.spell_id for item in source.spells):
            raise CastSelectionError("rank_unavailable", "that source has no access to the selected spell rank")
        raise CastSelectionError("spell_unavailable", "that spell is not admitted by the selected source")

    if access.cantrip:
        if selection.resource_id is not None or selection.supplemental_resource_id is not None:
            raise CastSelectionError("cantrip_has_no_cost", "cantrips do not spend a casting resource")
        return CastPermission(selection, ())

    if selection.resource_id is None:
        matching_count = _eligible_resource_count(source, access, sources, resources)
        reason = "resource_choice_required" if matching_count > 1 else "resource_required"
        raise CastSelectionError(reason, "select the exact resource to spend")
    resource = resource_by_id.get(selection.resource_id)
    if resource is None:
        raise CastSelectionError("unknown_resource", f"unknown resource {selection.resource_id!r}")

    if source.kind == "prepared":
        if selection.supplemental_resource_id is not None:
            raise CastSelectionError("unexpected_supplemental_resource", "prepared casts use one prepared slot")
        _require(_prepared_slot_matches(resource, source, access), "resource_not_owned", "slot does not prepare this spell")
        _require(resource.remaining > 0, "resource_depleted", "prepared slot is expended")
        return CastPermission(selection, (ResourceSpend(resource.resource_id, 1),))

    if source.kind == "spontaneous":
        if selection.supplemental_resource_id is not None:
            raise CastSelectionError("unexpected_supplemental_resource", "ordinary repertoire casts use one slot")
        _require(_rank_slot_matches(resource, source, selection.rank), "resource_not_owned", "slot is not owned by this casting source at this rank")
        _require(resource.remaining > 0, "resource_depleted", "spell rank slots are expended")
        return CastPermission(selection, (ResourceSpend(resource.resource_id, 1),))

    if source.kind == "focus":
        if selection.supplemental_resource_id is not None:
            raise CastSelectionError("unexpected_supplemental_resource", "focus casts use the shared focus pool")
        _require(resource.kind == "focus_points", "resource_kind_mismatch", "focus spells spend focus points")
        _require(resource.source_id is None, "resource_not_owned", "focus points belong to the actor's shared pool")
        _require(resource.remaining > 0, "resource_depleted", "the shared focus pool is empty")
        return CastPermission(selection, (ResourceSpend(resource.resource_id, 1),))

    if source.kind == "innate":
        if selection.supplemental_resource_id is not None:
            raise CastSelectionError("unexpected_supplemental_resource", "innate casts use their innate-use resource")
        _require(_innate_use_matches(resource, source, access), "resource_not_owned", "innate use does not belong to this spell/source")
        _require(resource.remaining > 0, "resource_depleted", "innate uses are expended")
        return CastPermission(selection, (ResourceSpend(resource.resource_id, 1),))

    if source.kind == "staff":
        _require(_staff_charge_matches(resource, source), "resource_not_owned", "staff charges belong to another source")
        if selection.supplemental_resource_id is None:
            _require(resource.remaining >= selection.rank, "resource_depleted", "the staff lacks charges for this rank")
            return CastPermission(selection, (ResourceSpend(resource.resource_id, selection.rank),))
        _require(resource.remaining >= 1, "resource_depleted", "the staff has no charge to supplement")
        supplemental = resource_by_id.get(selection.supplemental_resource_id)
        if supplemental is None:
            raise CastSelectionError("unknown_resource", f"unknown supplemental resource {selection.supplemental_resource_id!r}")
        _require(
            _RESOURCE_SOURCE_KIND.get(supplemental.kind) == "spontaneous"
            and supplemental.remaining > 0
            and supplemental.rank >= selection.rank,
            "resource_not_owned",
            "the supplemental resource must be an available spontaneous slot of sufficient rank",
        )
        return CastPermission(
            selection,
            (ResourceSpend(resource.resource_id, 1), ResourceSpend(supplemental.resource_id, 1)),
        )

    raise CastSelectionError("unsupported_source_kind", f"unsupported source kind {source.kind!r}")


def focus_pool_capacity(sources: tuple[CastingSource, ...]) -> int:
    """Return the remaster focus-pool capacity: known focus spells, capped at 3.

    A focus cantrip does not cost a Focus Point and is not counted as a focus
    spell. Repeated rank entries for one focus spell count once, and focus
    spells from different sources contribute to the same actor pool.
    """
    if type(sources) is not tuple:
        raise CastSelectionError("invalid_source", "focus-capacity sources must be an immutable tuple")
    source_by_id: dict[str, CastingSource] = {}
    for source in sources:
        if (
            not isinstance(source, CastingSource)
            or not isinstance(source.source_id, str)
            or not source.source_id
            or type(source.spells) is not tuple
        ):
            raise CastSelectionError("invalid_source", "focus-capacity sources need IDs and immutable spell tuples")
        if source.source_id in source_by_id:
            raise CastSelectionError("duplicate_source_id", f"duplicate source ID {source.source_id!r}")
        if source.kind not in _SOURCE_KINDS:
            raise CastSelectionError("unsupported_source_kind", f"unsupported source kind {source.kind!r}")
        if any(
            not isinstance(access, SpellAccess)
            or not isinstance(access.spell_id, str)
            or not access.spell_id
            or type(access.rank) is not int
            or access.rank < 1
            or type(access.cantrip) is not bool
            or type(access.signature) is not bool
            for access in source.spells
        ):
            raise CastSelectionError("invalid_spell_access", "spell access needs a spell ID and positive rank")
        source_by_id[source.source_id] = source
    spell_ids = {
        access.spell_id
        for source in sources
        if source.kind == "focus"
        for access in source.spells
        if not access.cantrip
    }
    return min(3, len(spell_ids))


def refocus_focus_points(resource: CastingResource) -> CastingResource:
    """Restore one point to the shared pool, capped at its current capacity.

    The core caller owns the Refocus activity's ten-minute timing and its
    source-specific requirements. Oracle cursebound reduction is independent.
    """
    _validate_resource_snapshot(resource)
    if resource.kind != "focus_points" or resource.source_id is not None:
        raise CastSelectionError("not_focus_pool", "Refocus applies to the actor's shared focus pool")
    if resource.capacity > 3:
        raise CastSelectionError("focus_pool_over_capacity", "the shared focus pool is capped at 3")
    return replace(resource, remaining=min(resource.capacity, resource.remaining + 1))


def _index_snapshots(
    sources: tuple[CastingSource, ...],
    resources: tuple[CastingResource, ...],
) -> tuple[dict[str, CastingSource], dict[str, CastingResource]]:
    if type(sources) is not tuple or type(resources) is not tuple:
        raise CastSelectionError("invalid_snapshots", "sources and resources must be immutable tuples")
    source_by_id: dict[str, CastingSource] = {}
    for source in sources:
        if (
            not isinstance(source, CastingSource)
            or not isinstance(source.source_id, str)
            or not source.source_id
        ):
            raise CastSelectionError("invalid_source", "casting sources need a nonempty source ID")
        if type(source.spells) is not tuple:
            raise CastSelectionError("invalid_source", "source spell access must be an immutable tuple")
        if source.source_id in source_by_id:
            raise CastSelectionError("duplicate_source_id", f"duplicate source ID {source.source_id!r}")
        if not isinstance(source.kind, str) or source.kind not in _SOURCE_KINDS:
            raise CastSelectionError("unsupported_source_kind", f"unsupported source kind {source.kind!r}")
        if type(source.attack_modifier) is not int or type(source.dc) is not int:
            raise CastSelectionError("invalid_source_statistics", "source attack and DC must be integers")
        seen_access: set[tuple[str, int]] = set()
        for access in source.spells:
            if (
                not isinstance(access, SpellAccess)
                or not isinstance(access.spell_id, str)
                or not access.spell_id
                or type(access.rank) is not int
                or access.rank < 1
                or type(access.cantrip) is not bool
                or type(access.signature) is not bool
            ):
                raise CastSelectionError("invalid_spell_access", "spell access needs a spell ID and positive rank")
            key = (access.spell_id, access.rank)
            if key in seen_access:
                raise CastSelectionError("duplicate_spell_access", f"duplicate spell access {key!r}")
            seen_access.add(key)
        source_by_id[source.source_id] = source

    resource_by_id: dict[str, CastingResource] = {}
    focus_pools = 0
    for resource in resources:
        _validate_resource_snapshot(resource)
        if resource.resource_id in resource_by_id:
            raise CastSelectionError("duplicate_resource_id", f"duplicate resource ID {resource.resource_id!r}")
        if not isinstance(resource.kind, str) or resource.kind not in _RESOURCE_KINDS:
            raise CastSelectionError("unsupported_resource_kind", f"unsupported resource kind {resource.kind!r}")
        if resource.kind in {"prepared_slot", "rank_slots", "innate_uses"} and resource.rank < 1:
            raise CastSelectionError("invalid_resource_rank", f"{resource.kind} needs a positive spell rank")
        if resource.kind in {"focus_points", "staff_charges"} and resource.rank != 0:
            raise CastSelectionError("invalid_resource_rank", f"{resource.kind} is not rank-specific")
        if resource.kind == "focus_points":
            focus_pools += 1
            if resource.source_id is not None:
                raise CastSelectionError("invalid_focus_pool_owner", "focus points are one actor-level shared pool")
            if resource.capacity > 3:
                raise CastSelectionError("focus_pool_over_capacity", "the shared focus pool is capped at 3")
        else:
            if resource.source_id is None:
                raise CastSelectionError("resource_missing_owner", "non-focus resources need an owning source")
            source = source_by_id.get(resource.source_id)
            if source is None:
                raise CastSelectionError("unknown_resource_source", f"unknown owner source {resource.source_id!r}")
            expected_kind = _RESOURCE_SOURCE_KIND[resource.kind]
            if source.kind != expected_kind:
                raise CastSelectionError(
                    "resource_kind_mismatch",
                    f"{resource.kind} cannot belong to a {source.kind} source",
                )
        if resource.kind == "prepared_slot" and (resource.spell_id is None or resource.capacity != 1):
            raise CastSelectionError("invalid_prepared_slot", "a prepared slot names one spell and has capacity 1")
        if resource.kind == "innate_uses" and not resource.spell_id:
            raise CastSelectionError("invalid_innate_use", "an innate-use resource must name its spell")
        if resource.kind in {"rank_slots", "focus_points", "staff_charges"} and resource.spell_id is not None:
            raise CastSelectionError("invalid_resource_spell", f"{resource.kind} is not spell-specific")
        resource_by_id[resource.resource_id] = resource
    if focus_pools > 1:
        raise CastSelectionError("duplicate_focus_pool", "all focus grants use one shared actor pool")
    focus_capacity = focus_pool_capacity(sources)
    if focus_capacity and focus_pools == 0:
        raise CastSelectionError("missing_focus_pool", "focus spells require the actor's shared focus pool")
    if focus_pools == 1:
        pool = next(resource for resource in resources if resource.kind == "focus_points")
        if pool.capacity != focus_capacity:
            raise CastSelectionError(
                "focus_pool_capacity_mismatch",
                f"focus pool capacity must match its admitted focus spells ({focus_capacity})",
            )
    return source_by_id, resource_by_id


def _validate_resource_snapshot(resource: CastingResource) -> None:
    if (
        not isinstance(resource, CastingResource)
        or not isinstance(resource.resource_id, str)
        or not resource.resource_id
        or (resource.source_id is not None and not isinstance(resource.source_id, str))
        or (resource.spell_id is not None and not isinstance(resource.spell_id, str))
        or not isinstance(resource.kind, str)
    ):
        raise CastSelectionError("invalid_resource", "casting resources need a nonempty resource ID")
    if (
        type(resource.rank) is not int
        or resource.rank < 0
        or type(resource.capacity) is not int
        or type(resource.remaining) is not int
        or resource.capacity < 0
        or not 0 <= resource.remaining <= resource.capacity
    ):
        raise CastSelectionError("invalid_resource", "resource rank/capacity/remaining values are invalid")


def _prepared_slot_matches(
    resource: CastingResource,
    source: CastingSource,
    access: SpellAccess,
) -> bool:
    return (
        resource.kind == "prepared_slot"
        and resource.source_id == source.source_id
        and resource.rank == access.rank
        and resource.spell_id == access.spell_id
    )


def _rank_slot_matches(resource: CastingResource, source: CastingSource, rank: int) -> bool:
    return resource.kind == "rank_slots" and resource.source_id == source.source_id and resource.rank == rank


def _innate_use_matches(
    resource: CastingResource,
    source: CastingSource,
    access: SpellAccess,
) -> bool:
    return (
        resource.kind == "innate_uses"
        and resource.source_id == source.source_id
        and resource.rank == access.rank
        and resource.spell_id == access.spell_id
    )


def _staff_charge_matches(resource: CastingResource, source: CastingSource) -> bool:
    return resource.kind == "staff_charges" and resource.source_id == source.source_id


def _eligible_resource_count(
    source: CastingSource,
    access: SpellAccess,
    sources: tuple[CastingSource, ...],
    resources: tuple[CastingResource, ...],
) -> int:
    if source.kind == "prepared":
        return sum(_prepared_slot_matches(item, source, access) and item.remaining > 0 for item in resources)
    if source.kind == "spontaneous":
        return sum(_rank_slot_matches(item, source, access.rank) and item.remaining > 0 for item in resources)
    if source.kind == "focus":
        return sum(item.kind == "focus_points" and item.remaining > 0 for item in resources)
    if source.kind == "innate":
        return sum(_innate_use_matches(item, source, access) and item.remaining > 0 for item in resources)
    if source.kind == "staff":
        charge_choices = sum(_staff_charge_matches(item, source) and item.remaining >= access.rank for item in resources)
        charge_choices += sum(_staff_charge_matches(item, source) and item.remaining > 0 for item in resources) * sum(
            _RESOURCE_SOURCE_KIND.get(item.kind) == "spontaneous"
            and item.remaining > 0
            and item.rank >= access.rank
            for item in resources
        )
        return charge_choices
    return 0


def _require(condition: bool, reason: str, message: str) -> None:
    if not condition:
        raise CastSelectionError(reason, message)
