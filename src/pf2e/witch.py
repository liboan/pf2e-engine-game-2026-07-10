"""Bounded familiar procedures for the selected Faith's Flamekeeper Witch.

This is intentionally not a reusable companion framework.  A commanded
familiar has only the three actions needed by the admitted fox: move, pick up,
and release a physical item.
"""

from __future__ import annotations

from dataclasses import dataclass

from .model import ActionContinuation, Event, FamilyCommand, FamilyProcedureContext, FamilyProcedureResult, Position
from .space import grid_distance_feet, in_bounds, step_cost


_CANTRIPS = frozenset({
    "divine_lance", "void_warp", "shield", "guidance", "stabilize", "light",
    "vitality_lash", "forbidding_ward", "sigil", "detect_magic",
})
_RANK_ONE = frozenset({"heal", "fear", "enfeeble", "runic_weapon", "runic_body", "command"})


def preparation_choices(definition, slot) -> tuple[str, ...]:
    if "faiths_flamekeeper" not in definition.abilities:
        return ()
    if slot.cantrip:
        return tuple(sorted(_CANTRIPS))
    if slot.rank == 1:
        return tuple(sorted(_RANK_ONE))
    return ()


def prepared_slot_rejection(actor, definition, slot, spell_id: str) -> str | None:
    if "faiths_flamekeeper" not in definition.abilities:
        return None
    allowed = _CANTRIPS if slot.cantrip else _RANK_ONE if slot.rank == 1 else frozenset()
    if spell_id not in allowed:
        return "The spell is outside this Witch's finite divine preparation choices."
    return None


@dataclass(frozen=True)
class FamiliarStride:
    path: tuple[Position, ...]


@dataclass(frozen=True)
class FamiliarPickup:
    item_id: str


@dataclass(frozen=True)
class FamiliarRelease:
    item_id: str


FamiliarAction = FamiliarStride | FamiliarPickup | FamiliarRelease


@dataclass(frozen=True)
class CommandFamiliar(FamilyCommand):
    """Spend one Witch action to give the familiar one or two literal actions."""

    family_id = "minions"
    familiar_id: str
    actions: tuple[FamiliarAction, ...]


@dataclass(frozen=True)
class PatronsPuppet(FamilyCommand):
    """Spend the focus point at turn start to issue the familiar's command free."""

    family_id = "minions"
    familiar_id: str
    actions: tuple[FamiliarAction, ...]


@dataclass(frozen=True)
class RestoreSpirit(FamilyCommand):
    """Use Faith's Flamekeeper's once-per-round restored-spirit benefit."""

    family_id = "minions"
    target_id: str


def handle_action(context: FamilyProcedureContext) -> FamilyProcedureResult:
    command = context.command
    if isinstance(command, CommandFamiliar):
        return _command(context, command.familiar_id, command.actions, puppet=False)
    if isinstance(command, PatronsPuppet):
        return _command(context, command.familiar_id, command.actions, puppet=True)
    if isinstance(command, RestoreSpirit):
        return FamilyProcedureResult(rejection="Restored Spirit is chosen only in its saved before-or-after hex trigger window.")
    return FamilyProcedureResult(unsupported="That minion action is not admitted.")


def handle_choice(context: FamilyProcedureContext) -> FamilyProcedureResult:
    return FamilyProcedureResult(unsupported="The selected Witch has no saved minion choice.")


def validate_pending(context: FamilyProcedureContext) -> None:
    raise ValueError("the selected Witch has no saved minion choice")


def _familiar(context: FamilyProcedureContext, familiar_id: str):
    if "faiths_flamekeeper" not in context.definition.abilities:
        return None, "This actor has no admitted Faith's Flamekeeper familiar."
    familiar = context.state.creatures.get(familiar_id)
    if (
        familiar is None
        or familiar.dead
        or familiar.unconscious
        or "witch_familiar" not in context.encounter._definition_abilities(familiar)
    ):
        return None, "That living familiar is unavailable."
    if not context.encounter._familiar_owned_by(context.actor, familiar):
        return None, "That familiar does not belong to this Witch."
    return familiar, None


def _command(context: FamilyProcedureContext, familiar_id: str, actions: tuple[FamiliarAction, ...], *, puppet: bool) -> FamilyProcedureResult:
    familiar, rejection = _familiar(context, familiar_id)
    if rejection:
        return FamilyProcedureResult(rejection=rejection)
    paid_actions = tuple(action for action in actions if not isinstance(action, FamiliarRelease))
    if (
        not isinstance(actions, tuple)
        or not 1 <= len(paid_actions) <= 2
        or len(actions) > 3
        or sum(isinstance(action, FamiliarRelease) for action in actions) > 1
    ):
        return FamilyProcedureResult(rejection="Command Familiar grants one or two familiar actions.")
    start = context.state.actor_start_counts.get(context.actor.actor_id, 0)
    if familiar.minion_commanded_start == start:
        return FamilyProcedureResult(rejection="The familiar has already received its two-action allotment this turn.")
    if puppet:
        if (
            context.actor.actions_remaining != 3
            or context.actor.witch_turn_activity_start == start
            or context.actor.witch_patron_used_start == start
        ):
            return FamilyProcedureResult(rejection="Patron's Puppet is available only once at the start of the Witch's turn.")
        if context.actor.focus_points < 1:
            return FamilyProcedureResult(rejection="Patron's Puppet requires 1 Focus Point.")
    else:
        if context.actor.actions_remaining < 1:
            return FamilyProcedureResult(rejection="Command Familiar requires one action.")
        try:
            context.encounter._require_action_permitted(context.state, context.actor, "command_familiar", frozenset({"auditory", "concentrate"}))
        except Exception as error:
            return FamilyProcedureResult(rejection=str(error))

    pre_recipients = ()
    if puppet:
        _owned_familiar, pre_recipients = context.encounter._restored_spirit_recipients(
            context.state, context.actor,
        )
        continuation = ActionContinuation(
            kind="witch_patrons_puppet",
            actor_id=context.actor.actor_id,
            target_id=familiar.actor_id,
            spell_id="stoke_the_heart",
            spell_actions=1,
            target_ids=tuple(candidate.actor_id for candidate in pre_recipients),
        )
        timing = context.encounter._offer_restored_spirit_timing(
            context.state,
            context.actor,
            continuation,
            pre_recipients=pre_recipients,
            action_name="using Patron's Puppet",
            family_command=PatronsPuppet(familiar_id, actions),
        )
        if timing:
            return FamilyProcedureResult(tuple(timing))
    events: list[Event] = []
    for action in actions:
        if isinstance(action, FamiliarStride):
            events.append(_stride(context, familiar, action))
        elif isinstance(action, FamiliarPickup):
            events.append(_pickup(context, familiar, action))
        elif isinstance(action, FamiliarRelease):
            events.append(_release(context, familiar, action))
        else:
            return FamilyProcedureResult(rejection="That familiar action is not admitted.")
    if puppet:
        context.actor.focus_points -= 1
        context.actor.witch_patron_used_start = context.state.actor_start_counts.get(context.actor.actor_id, 0)
        context.actor.witch_hex_cast_start = start
        prefix = "Patron's Puppet"
    else:
        context.actor.actions_remaining -= 1
        prefix = "Command Familiar"
    familiar.minion_commanded_start = start
    events.insert(0, Event(
        "familiar_command", context.actor.actor_id, familiar.actor_id,
        f"{context.actor.label} uses {prefix}; {familiar.label} receives {len(paid_actions)} action(s).",
    ))
    return FamilyProcedureResult(tuple(context.encounter._complete_action(context.state, context.actor, events, dice=context.dice)))


def _stride(context: FamilyProcedureContext, familiar, action: FamiliarStride) -> Event:
    if not isinstance(action.path, tuple) or not action.path:
        raise ValueError("Familiar Stride requires a nonempty tuple of squares.")
    current = familiar.position
    distance = 0
    diagonals = 0
    for point in action.path:
        if not isinstance(point, Position) or not in_bounds(point, context.state.map_width, context.state.map_height):
            raise ValueError("Familiar Stride leaves the supported map.")
        try:
            cost, diagonal = step_cost(current, point, diagonals)
        except ValueError as error:
            raise ValueError("Familiar Stride must visit adjacent squares.") from error
        occupant = context.encounter._occupant_at(context.state, point, except_actor=familiar.actor_id)
        if occupant is not None and not context.encounter._familiar_can_share_space(familiar, occupant):
            raise ValueError("Familiar Stride is blocked by an occupied square.")
        distance += cost
        if distance > 40:
            raise ValueError("Familiar Stride exceeds its 40-foot Speed.")
        diagonals += diagonal
        current = point
    familiar.position = current
    return Event("familiar_stride", familiar.actor_id, None, f"{familiar.label} Strides {distance} feet.", position=current)


def _pickup(context: FamilyProcedureContext, familiar, action: FamiliarPickup) -> Event:
    if not isinstance(action.item_id, str) or not action.item_id:
        raise ValueError("Familiar Pickup needs a physical item id.")
    if len(familiar.held_items) >= 2:
        raise ValueError("The familiar has no free hand for that item.")
    items = context.state.ground_items.get(familiar.position, [])
    if action.item_id not in items:
        raise ValueError("Manual Dexterity can pick up an item only in the familiar's own square.")
    items.remove(action.item_id)
    if not items:
        del context.state.ground_items[familiar.position]
    familiar.held_items.append(action.item_id)
    return Event("familiar_pickup", familiar.actor_id, None, f"{familiar.label} picks up {action.item_id}.", position=familiar.position)


def _release(context: FamilyProcedureContext, familiar, action: FamiliarRelease) -> Event:
    if action.item_id not in familiar.held_items:
        raise ValueError("The familiar is not carrying that item.")
    familiar.held_items.remove(action.item_id)
    context.state.ground_items.setdefault(familiar.position, []).append(action.item_id)
    return Event("familiar_release", familiar.actor_id, None, f"{familiar.label} releases {action.item_id}.", position=familiar.position)


def _restore_spirit(context: FamilyProcedureContext, target_id: str) -> FamilyProcedureResult:
    familiar = next((candidate for candidate in context.state.creatures.values() if context.encounter._familiar_owned_by(context.actor, candidate)), None)
    if familiar is None or familiar.dead or familiar.unconscious:
        return FamilyProcedureResult(rejection="Restored Spirit requires the living selected familiar.")
    target = context.state.creatures.get(target_id)
    if target is None or target.dead or target.team != context.actor.team:
        return FamilyProcedureResult(rejection="Restored Spirit needs a willing living ally.")
    if grid_distance_feet(familiar.position, target.position) > 15:
        return FamilyProcedureResult(rejection="Restored Spirit's recipient must be within 15 feet of the familiar.")
    start = context.state.actor_start_counts.get(context.actor.actor_id, 0)
    if context.actor.witch_restored_spirit_used_start == start:
        return FamilyProcedureResult(rejection="Restored Spirit has already been used this round.")
    target.temporary_hp = 2
    target.temporary_hp_source_id = f"restored_spirit:{context.actor.actor_id}:{start}"
    target.temporary_hp_expires_at_seconds = context.state.world_time_seconds + 6
    context.actor.witch_restored_spirit_used_start = start
    return FamilyProcedureResult((Event(
        "restored_spirit", familiar.actor_id, target.actor_id,
        f"{familiar.label}'s Restored Spirit grants {target.label} 2 temporary HP until the Witch's next turn.",
    ),))
