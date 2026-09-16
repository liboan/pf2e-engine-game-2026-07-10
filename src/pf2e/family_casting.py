"""Resource-backed procedure for the currently admitted prepared casts.

This is the first migration slice for the existing Warpriest encounter casts.
It adapts the actor's literal prepared-slot state to the independent casting
permission helper, then commits the returned spend into those same slots. Spell
targeting, effects, dice, and saved cast continuations remain owned by
``Encounter``.
"""

from __future__ import annotations

from .checks import multiple_attack_penalty
from .casting import (
    CastSelection,
    CastSelectionError,
    CastingResource,
    CastingSource,
    SpellAccess,
    available_casts,
    focus_pool_capacity,
    validate_cast,
)
from .model import (
    ActionContinuation,
    Cast,
    ChoiceOption,
    Event,
    FamilyProcedureContext,
    FamilyProcedureResult,
    PreparedSpellDefinition,
    PreparedSlotState,
    Position,
)
from .spells import SPELLS, spell_traits
from .space import grid_distance_feet, in_bounds


def begin_cast(context: FamilyProcedureContext, command: Cast) -> FamilyProcedureResult:
    """Validate, select, and commit one cast in the active encounter draft.

    The cast resource snapshots are made afresh from ``PreparedSlotState`` for
    every request. A limited cast spends only the precise slot returned by
    ``validate_cast``; the existing spell-resolution procedure receives that
    same slot ID in its saved ``ActionContinuation``.
    """
    if not isinstance(command, Cast):
        return FamilyProcedureResult(unsupported="The casting procedure requires a Cast command.")
    if context.state.pending_choice is not None:
        return FamilyProcedureResult(rejection="A pending choice must be resolved before another action.")

    spell = SPELLS.get(command.spell_id)
    if spell is None:
        return FamilyProcedureResult(unsupported=f"Spell {command.spell_id!r} is outside the admitted spell list.")
    runic_weapon = spell.spell_id == "runic_weapon"
    light = spell.spell_id == "light"
    sure_strike = spell.spell_id == "sure_strike"
    if spell.unavailable_reason:
        return FamilyProcedureResult(rejection=spell.unavailable_reason)
    if sure_strike and context.state.sure_strike_immunity_deadlines.get(
        context.actor.actor_id, 0
    ) > context.state.world_time_seconds:
        return FamilyProcedureResult(
            rejection="Sure Strike is unavailable while its ten-minute immunity is active."
        )

    spontaneous = bool(context.definition.spontaneous_spells or context.definition.spontaneous_slots)
    known_focus = tuple(
        access for access in context.definition.focus_spells
        if access.spell_id == spell.spell_id
    )
    prepared = tuple(
        slot for slot in context.actor.prepared_slots
        if slot.spell_id == spell.spell_id
    )
    known_spontaneous = tuple(
        access for access in context.definition.spontaneous_spells
        if access.spell_id == spell.spell_id
    )
    if not prepared and not known_spontaneous and not known_focus:
        return FamilyProcedureResult(
            rejection=(
                f"{context.actor.label} does not know {spell.name}."
                if spontaneous else f"{context.actor.label} has not prepared {spell.name}."
            )
        )

    supported_action_costs = spell.action_costs
    if command.actions is None:
        if len(supported_action_costs) != 1:
            return FamilyProcedureResult(
                rejection=f"Choose an action mode for {spell.name}: {', '.join(map(str, spell.action_costs))} actions."
            )
        actions = supported_action_costs[0]
    else:
        actions = command.actions
    if type(actions) is not int or actions not in supported_action_costs:
        return FamilyProcedureResult(rejection=f"{actions!r} is not a supported action mode for {spell.name}.")
    if actions > context.actor.actions_remaining:
        return FamilyProcedureResult(rejection=f"{spell.name} requires {actions} actions.")

    traits = spell_traits(spell.spell_id, actions)
    context.encounter._require_action_permitted(
        context.state, context.actor, "cast_spell", traits
    )
    if light:
        if command.target_id is not None:
            return FamilyProcedureResult(
                rejection="Light creates an orb at point; it does not take a creature target."
            )
        if command.include_self is not None:
            return FamilyProcedureResult(rejection="include_self is not supported for Light.")
        if command.item_id is not None:
            return FamilyProcedureResult(rejection="Light does not target a physical item.")
        if not isinstance(command.point, Position):
            return FamilyProcedureResult(rejection="Light requires a point inside the encounter map.")
        if not in_bounds(command.point, context.state.map_width, context.state.map_height):
            return FamilyProcedureResult(rejection="Light's point must be inside the encounter map.")
        if grid_distance_feet(context.actor.position, command.point) > 120:
            return FamilyProcedureResult(rejection="Light's point is outside its 120-foot range.")
        if command.color is not None and (
            not isinstance(command.color, str) or not command.color.strip()
        ):
            return FamilyProcedureResult(rejection="Light's color must be a non-empty string.")
        if command.attachment_actor_id is not None:
            attached = context.state.creatures.get(command.attachment_actor_id)
            if attached is None:
                return FamilyProcedureResult(rejection="Light's attachment actor does not exist.")
            if attached.position != command.point:
                return FamilyProcedureResult(
                    rejection="Light can attach only to a creature in the chosen point's space."
                )
        owned_orbs = tuple(
            orb for orb in context.state.light_orbs
            if orb.caster_actor_id == context.actor.actor_id
        )
        if len(owned_orbs) >= 4:
            if command.replacement_orb_id is None:
                return FamilyProcedureResult(
                    rejection=(
                        "The caster already has four active Light orbs; choose one with "
                        "replacement_orb_id before casting a fifth."
                    )
                )
            if not any(orb.stable_id == command.replacement_orb_id for orb in owned_orbs):
                # Keep foreign, stale, and malformed IDs atomic and distinct
                # from the ordinary missing-selection boundary.
                if any(orb.stable_id == command.replacement_orb_id for orb in context.state.light_orbs):
                    return FamilyProcedureResult(
                        rejection="Light replacement_orb_id must name one of the caster's active orbs."
                    )
                return FamilyProcedureResult(
                    rejection="Light replacement_orb_id does not name an active orb."
                )
        elif command.replacement_orb_id is not None:
            return FamilyProcedureResult(
                rejection=(
                    "Light replacement_orb_id is only valid when the caster already has "
                    "four active Light orbs."
                )
            )
    elif spell.spell_id == "heal" and actions == 3:
        if command.target_id is not None:
            return FamilyProcedureResult(
                rejection="Three-action Heal affects the eligible emanation; it does not take a single target."
            )
        if command.include_self is not None and type(command.include_self) is not bool:
            return FamilyProcedureResult(rejection="include_self must be true or false for three-action Heal.")
    elif command.include_self is not None:
        return FamilyProcedureResult(rejection="include_self is only supported for three-action Heal.")
    if sure_strike and (
        command.target_id is not None
        or command.include_self is not None
        or command.item_id is not None
        or command.point is not None
    ):
        return FamilyProcedureResult(
            rejection="Sure Strike targets the caster and takes no target or point selection."
        )
    if spell.spell_id == "angelic_halo" and command.target_id is not None:
        return FamilyProcedureResult(rejection="Angelic Halo creates an emanation and does not take a target.")
    if spell.spell_id == "angelic_halo" and command.include_self is not None:
        return FamilyProcedureResult(rejection="include_self is not supported for Angelic Halo.")
    if runic_weapon:
        if command.target_id is not None:
            return FamilyProcedureResult(
                rejection="Runic Weapon targets a physical weapon through item_id, not a creature target."
            )
        if command.include_self is not None:
            return FamilyProcedureResult(rejection="include_self is not supported for Runic Weapon.")
        if command.item_id is None:
            return FamilyProcedureResult(rejection="Runic Weapon requires an explicit physical weapon item_id.")
        try:
            target_facts = context.encounter._runic_weapon_target(
                context.state, context.actor, command.item_id
            )
        except ValueError as error:
            return FamilyProcedureResult(rejection=str(error))
    else:
        target_facts = None

    if known_focus and not prepared and not known_spontaneous:
        source_kind = "focus"
        snapshot = _focus_casting_snapshots(context)
    elif known_spontaneous and not prepared:
        source_kind = "spontaneous"
        snapshot = _spontaneous_casting_snapshots(context)
    else:
        source_kind = "prepared"
        snapshot = _prepared_casting_snapshots(context)
    if isinstance(snapshot, FamilyProcedureResult):
        return snapshot
    sources, resources = snapshot

    # The legacy Cast API has no source/rank fields. It historically prefers a
    # prepared cantrip of the same spell ID and rejects a supplied slot ID for
    # that cast, so preserve that public behavior while still validating its
    # source access through the casting helper. A spontaneous source uses its
    # one actor-level rank pool and keeps its repertoire provenance in the
    # continuation.
    cantrip_access = tuple(
        selection for selection in available_casts(sources, resources)
        if selection.spell_id == spell.spell_id and selection.resource_id is None
    )
    if cantrip_access:
        if command.slot_id is not None:
            return FamilyProcedureResult(rejection="Cantrips do not expend a casting slot.")
        if len(cantrip_access) != 1:
            return FamilyProcedureResult(
                rejection="This spell is available as a cantrip from more than one source; select a source explicitly."
            )
        permission_selection = cantrip_access[0]
        permission = validate_cast(permission_selection, sources, resources)
        selected_rank = permission.selection.rank
    else:
        candidates = tuple(
            selection for selection in available_casts(sources, resources)
            if selection.spell_id == spell.spell_id
        )
        if command.slot_id is None:
            if not candidates:
                if source_kind == "focus":
                    return FamilyProcedureResult(rejection=f"No focus point remains for {spell.name}.")
                return FamilyProcedureResult(
                    rejection=(
                        f"No unspent {'spontaneous rank slot' if source_kind == 'spontaneous' else 'prepared slot'} remains for {spell.name}."
                    )
                )
            if len(candidates) > 1:
                if source_kind == "spontaneous":
                    slot_by_id = {
                        slot.slot_id: slot
                        for slot in context.actor.spontaneous_slots
                        if slot.remaining > 0
                    }
                    options = tuple(
                        ChoiceOption(
                            candidate.resource_id or "",
                            _spontaneous_slot_label(slot_by_id[candidate.resource_id or ""]),
                        )
                        for candidate in candidates
                    )
                else:
                    slot_by_id = {slot.slot_id: slot for slot in prepared if not slot.cantrip and not slot.spent}
                    options = tuple(
                        ChoiceOption(candidate.resource_id or "", _slot_label(slot_by_id[candidate.resource_id or ""]))
                        for candidate in candidates
                    )
                context.present_spell_slot_choice(
                    command,
                    options,
                    spell_name=spell.name,
                    actions=actions,
                )
                return FamilyProcedureResult((Event(
                    "spell_slot_choice",
                    context.actor.actor_id,
                    None,
                    f"Choose a {'spontaneous rank' if source_kind == 'spontaneous' else 'prepared'} {spell.name} slot.",
                ),))
            permission_selection = candidates[0]
        else:
            selected_resource = next(
                (resource for resource in resources if resource.resource_id == command.slot_id),
                None,
            )
            if selected_resource is None:
                return FamilyProcedureResult(
                    rejection=(
                        "That focus point is unavailable."
                        if source_kind == "focus" else
                        "That spontaneous rank slot is unavailable."
                        if source_kind == "spontaneous" else
                        "That prepared spell slot is unavailable."
                    )
                )
            permission_selection = CastSelection(
                source_id=(
                    selected_resource.source_id
                    or (sources[0].source_id if source_kind == "focus" else "")
                ),
                spell_id=spell.spell_id,
                rank=selected_resource.rank,
                resource_id=command.slot_id,
            )
        try:
            permission = validate_cast(permission_selection, sources, resources)
        except CastSelectionError:
            return FamilyProcedureResult(
                rejection=(
                    "That focus point is unavailable."
                    if source_kind == "focus" else
                    "That spontaneous rank slot is unavailable."
                    if source_kind == "spontaneous" else
                    "That prepared spell slot is unavailable."
                )
            )
        selected_rank = permission.selection.rank

    if selected_rank != 1:
        return FamilyProcedureResult(
            unsupported=f"Rank {selected_rank} resolution for {spell.name} is not admitted by the current spell procedure."
        )

    if not runic_weapon and not light and spell.spell_id != "angelic_halo" and (spell.spell_id != "heal" or actions != 3):
        if (
            command.target_id is not None
            and spell.spell_id in {"divine_lance", "void_warp"}
            and context.encounter._stable_zero_pc(context.state.creatures.get(command.target_id))
        ):
            return FamilyProcedureResult(
                unsupported="Positive damage to a stabilized 0 HP PC awaits a product ruling and is unsupported."
            )
        candidates = context.encounter._spell_targets_for_cast(
            context.state, context.actor, spell.spell_id, actions
        )
        if command.target_id is not None and command.target_id not in candidates:
            return FamilyProcedureResult(
                rejection=f"That creature is not a legal target for {spell.name} in this mode."
            )
        if command.target_id is None and not candidates:
            return FamilyProcedureResult(rejection=f"There are no eligible targets for {spell.name}.")

    # Only now commit the action and the exact helper-reported resource spend.
    # The encounter transaction discards both together on rejection.
    if permission.spends:
        if source_kind == "spontaneous":
            slots_by_id = {slot.slot_id: slot for slot in context.actor.spontaneous_slots}
            for spend in permission.spends:
                slot = slots_by_id.get(spend.resource_id)
                if (
                    spend.amount != 1
                    or slot is None
                    or slot.remaining < spend.amount
                    or slot.rank != permission.selection.rank
                ):
                    return FamilyProcedureResult(rejection="That spontaneous rank slot is unavailable.")
            for spend in permission.spends:
                slots_by_id[spend.resource_id].remaining -= spend.amount
        elif source_kind == "focus":
            for spend in permission.spends:
                if (
                    spend.resource_id != "actor_focus_pool"
                    or spend.amount != 1
                    or context.actor.focus_points < spend.amount
                ):
                    return FamilyProcedureResult(rejection="The shared focus pool is empty.")
            context.actor.focus_points -= 1
        else:
            slots_by_id = {slot.slot_id: slot for slot in context.actor.prepared_slots}
            for spend in permission.spends:
                slot = slots_by_id.get(spend.resource_id)
                if (
                    spend.amount != 1
                    or slot is None
                    or slot.cantrip
                    or slot.spent
                    or slot.spell_id != permission.selection.spell_id
                    or slot.rank != permission.selection.rank
                ):
                    return FamilyProcedureResult(rejection="That prepared spell slot is unavailable.")
            for spend in permission.spends:
                slots_by_id[spend.resource_id].spent = True

    context.actor.actions_remaining -= actions
    if "attack" in spell.traits:
        context.state.taking_cover.discard(context.actor.actor_id)
    attack_count = 0
    attack_penalty = 0
    if "attack" in spell.traits:
        attack_penalty = multiple_attack_penalty(context.actor.strikes_this_turn, spell.traits)
        attack_count = context.actor.strikes_this_turn + 1
    slot_id = permission.selection.resource_id
    continuation = ActionContinuation(
        kind="cast",
        actor_id=context.actor.actor_id,
        target_id=command.target_id,
        attack_penalty=attack_penalty,
        attack_count=attack_count,
        spell_id=spell.spell_id,
        spell_target_id=command.target_id,
        slot_id=slot_id,
        spell_actions=actions,
        include_self=command.include_self,
        spell_source_kind=source_kind,
        sorcerous_potency=1 if source_kind == "spontaneous" and spell.spell_id == "heal" else 0,
        movement_kind="manipulate" if "manipulate" in traits else None,
        must_disrupt_on_critical="manipulate" in traits,
        spell_target_item_id=command.item_id if runic_weapon else None,
        spell_target_wielder_id=(target_facts[1] if target_facts is not None else None),
        light_point=command.point if light else None,
        light_color=(command.color.strip() if isinstance(command.color, str) else "white") if light else None,
        light_attachment_actor_id=command.attachment_actor_id if light else None,
        light_replacement_orb_id=command.replacement_orb_id if light else None,
    )
    events = [Event(
        "cast_started",
        context.actor.actor_id,
        command.target_id,
        f"{context.actor.label} commits {spell.name} ({actions} action(s))"
        + (f" on {command.item_id}." if runic_weapon else "."),
    )]
    if runic_weapon and continuation.spell_target_wielder_id not in (None, context.actor.actor_id):
        events.extend(context.encounter._offer_runic_weapon_willingness(
            context.state, context.actor, continuation,
        ))
        return FamilyProcedureResult(tuple(events))
    # Angelic Blood Magic is selected before a Heal's initial resolution.  For
    # an explicit one- or two-action target this is before the shared
    # manipulate/reaction window as well; the continuation resumes that window
    # after the saved recipient choice.
    if (
        spell.spell_id == "heal"
        and source_kind == "spontaneous"
        and actions in (1, 2)
        and continuation.target_id is not None
    ):
        events.extend(context.encounter._offer_blood_magic_recipient(
            context.state, context.actor, continuation,
        ))
        return FamilyProcedureResult(tuple(events))
    if continuation.movement_kind == "manipulate":
        events.extend(context.encounter._advance_continuation(context.state, context.dice, continuation))
    else:
        events.extend(context.encounter._resolve_cast(context.state, context.dice, continuation))
    return FamilyProcedureResult(tuple(events))


def handle_choice(context: FamilyProcedureContext) -> FamilyProcedureResult:
    """Casting choices remain on the legacy core route in this migration."""
    return FamilyProcedureResult(unsupported="The casting procedure does not own this family choice.")


def validate_pending(context: FamilyProcedureContext) -> None:
    """No family-action save format is introduced for the legacy slot prompt."""
    raise ValueError("casting choices use the existing typed spell choice records")


def _prepared_casting_snapshots(
    context: FamilyProcedureContext,
) -> tuple[tuple[CastingSource, ...], tuple[CastingResource, ...]] | FamilyProcedureResult:
    """Adapt immutable spell access and live expenditure from prepared slots."""
    definition = context.definition
    if type(definition.spell_attack) is not int or type(definition.spell_dc) is not int:
        return FamilyProcedureResult(
            unsupported=f"{definition.name} has no admitted spell attack and DC statistics."
        )

    expected = tuple(
        (slot.slot_id, slot.source, slot.spell_id, slot.rank, slot.cantrip)
        for slot in definition.prepared_spells
    )
    actual = tuple(
        (slot.slot_id, slot.source, slot.spell_id, slot.rank, slot.cantrip)
        for slot in context.actor.prepared_slots
    )
    if actual != expected:
        return FamilyProcedureResult(
            rejection="The prepared spell slots no longer match this creature's reviewed definition."
        )

    grouped: dict[tuple[str, bool], list[PreparedSpellDefinition]] = {}
    for slot in definition.prepared_spells:
        grouped.setdefault((slot.source, slot.cantrip), []).append(slot)

    sources: list[CastingSource] = []
    resources: list[CastingResource] = []
    for (source_name, is_cantrip), slots in grouped.items():
        source_id = _source_id(source_name, is_cantrip)
        accesses: list[SpellAccess] = []
        seen_access: set[tuple[str, int]] = set()
        for slot in slots:
            key = (slot.spell_id, slot.rank)
            if key not in seen_access:
                accesses.append(SpellAccess(slot.spell_id, slot.rank, cantrip=is_cantrip))
                seen_access.add(key)
        sources.append(CastingSource(
            source_id=source_id,
            kind="prepared",
            tradition=definition.spell_tradition or "divine",
            attribute=definition.spell_attribute,
            attack_modifier=definition.spell_attack,
            dc=definition.spell_dc,
            spells=tuple(accesses),
        ))
    for slot in context.actor.prepared_slots:
        if slot.cantrip:
            continue
        resources.append(CastingResource(
            resource_id=slot.slot_id,
            source_id=_source_id(slot.source, False),
            kind="prepared_slot",
            rank=slot.rank,
            capacity=1,
            remaining=0 if slot.spent else 1,
            spell_id=slot.spell_id,
        ))
    return tuple(sources), tuple(resources)


def _spontaneous_casting_snapshots(
    context: FamilyProcedureContext,
) -> tuple[tuple[CastingSource, ...], tuple[CastingResource, ...]] | FamilyProcedureResult:
    """Adapt one literal repertoire and rank pool to the shared cast helper."""
    definition = context.definition
    if type(definition.spell_attack) is not int or type(definition.spell_dc) is not int:
        return FamilyProcedureResult(
            unsupported=f"{definition.name} has no admitted spell attack and DC statistics."
        )
    seen: set[tuple[str, int]] = set()
    for spell in definition.spontaneous_spells:
        if (
            not spell.spell_id
            or type(spell.rank) is not int
            or spell.rank < 1
            or type(spell.cantrip) is not bool
            or type(spell.signature) is not bool
            or (spell.spell_id, spell.rank) in seen
        ):
            return FamilyProcedureResult(rejection="The spontaneous repertoire is invalid.")
        seen.add((spell.spell_id, spell.rank))
    actual_slots = tuple(
        (slot.slot_id, slot.source, slot.rank, slot.capacity)
        for slot in context.actor.spontaneous_slots
    )
    expected_slots = tuple(
        (slot.slot_id, slot.source, slot.rank, slot.capacity)
        for slot in definition.spontaneous_slots
    )
    if actual_slots != expected_slots:
        return FamilyProcedureResult(
            rejection="The spontaneous rank slots no longer match this creature's reviewed definition."
        )
    if any(
        not slot.slot_id
        or not slot.source
        or type(slot.rank) is not int
        or slot.rank < 1
        or type(slot.capacity) is not int
        or slot.capacity < 1
        or type(slot.remaining) is not int
        or not 0 <= slot.remaining <= slot.capacity
        for slot in context.actor.spontaneous_slots
    ):
        return FamilyProcedureResult(rejection="The spontaneous rank slots are invalid.")
    source_id = _spontaneous_source_id(definition.spontaneous_source)
    source = CastingSource(
        source_id=source_id,
        kind="spontaneous",
        tradition=definition.spell_tradition or "divine",
        attribute=definition.spell_attribute,
        attack_modifier=definition.spell_attack,
        dc=definition.spell_dc,
        spells=tuple(
            SpellAccess(spell.spell_id, spell.rank, spell.cantrip, spell.signature)
            for spell in definition.spontaneous_spells
        ),
    )
    resources = tuple(
        CastingResource(
            resource_id=slot.slot_id,
            source_id=source_id,
            kind="rank_slots",
            rank=slot.rank,
            capacity=slot.capacity,
            remaining=slot.remaining,
        )
        for slot in context.actor.spontaneous_slots
    )
    return (source,), resources


def _focus_casting_snapshots(
    context: FamilyProcedureContext,
) -> tuple[tuple[CastingSource, ...], tuple[CastingResource, ...]] | FamilyProcedureResult:
    """Adapt one actor's admitted focus repertoire and shared focus pool."""
    definition = context.definition
    if type(definition.spell_attack) is not int or type(definition.spell_dc) is not int:
        return FamilyProcedureResult(
            unsupported=f"{definition.name} has no admitted spell attack and DC statistics."
        )
    if not definition.focus_spells:
        return FamilyProcedureResult(rejection="This caster has no admitted focus spell.")
    seen: set[tuple[str, int]] = set()
    for spell in definition.focus_spells:
        if (
            not spell.spell_id
            or type(spell.rank) is not int
            or spell.rank < 1
            or type(spell.cantrip) is not bool
            or type(spell.signature) is not bool
            or (spell.spell_id, spell.rank) in seen
        ):
            return FamilyProcedureResult(rejection="The focus repertoire is invalid.")
        seen.add((spell.spell_id, spell.rank))
    expected_capacity = focus_pool_capacity((CastingSource(
        source_id=f"focus:{definition.focus_source}",
        kind="focus",
        tradition=definition.spell_tradition or "divine",
        attribute=definition.spell_attribute,
        attack_modifier=definition.spell_attack,
        dc=definition.spell_dc,
        spells=tuple(SpellAccess(item.spell_id, item.rank, item.cantrip, item.signature) for item in definition.focus_spells),
    ),))
    if (
        type(definition.focus_capacity) is not int
        or definition.focus_capacity != expected_capacity
        or type(context.actor.focus_capacity) is not int
        or context.actor.focus_capacity != definition.focus_capacity
        or type(context.actor.focus_points) is not int
        or not 0 <= context.actor.focus_points <= context.actor.focus_capacity
    ):
        return FamilyProcedureResult(rejection="The focus pool no longer matches this creature's reviewed definition.")
    source_id = f"focus:{definition.focus_source}"
    source = CastingSource(
        source_id=source_id,
        kind="focus",
        tradition=definition.spell_tradition or "divine",
        attribute=definition.spell_attribute,
        attack_modifier=definition.spell_attack,
        dc=definition.spell_dc,
        spells=tuple(
            SpellAccess(item.spell_id, item.rank, item.cantrip, item.signature)
            for item in definition.focus_spells
        ),
    )
    return (
        (source,),
        (CastingResource(
            resource_id="actor_focus_pool",
            source_id=None,
            kind="focus_points",
            rank=0,
            capacity=context.actor.focus_capacity,
            remaining=context.actor.focus_points,
        ),),
    )


def _source_id(source: str, cantrip: bool) -> str:
    """Keep slot-origin labels distinct, including cantrip and slot access."""
    return f"prepared:{source}:{'cantrip' if cantrip else 'slots'}"


def _spontaneous_source_id(source: str) -> str:
    return f"spontaneous:{source}"


def _slot_label(slot: PreparedSlotState) -> str:
    return f"{slot.source}: {slot.slot_id}"


def _spontaneous_slot_label(slot) -> str:
    return f"{slot.source}: {slot.slot_id} (rank {slot.rank})"
