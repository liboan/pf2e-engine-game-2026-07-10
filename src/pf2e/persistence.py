"""Versioned JSON saves and transactional random-dice providers."""

import json
import os
import random
import tempfile
from dataclasses import replace
from pathlib import Path
from typing import Any, Iterable

from .content import get_definition, get_setup
from .model import (
    ActionContinuation,
    ActiveSpellEffect,
    ChoiceOption,
    CreatureState,
    EncounterState,
    HealthMode,
    GuidanceImmunity,
    PendingChoice,
    Position,
    PreparedSlotState,
    is_combat_capable,
)
from .health import HealthState, HealthTransition
from .checks import CheckResult, DegreeOfSuccess, DegreeChange, Modifier, combine_modifiers, resolve_check
from .damage import DamageComponent, DamageResult
from .space import in_bounds


SAVE_VERSION = 5
ENGINE_COMPATIBILITY = "pf2e-s3-casting-engine-v5"
CONTENT_COMPATIBILITY = "pf2e-s3-roster-v3"


class DiceSourceError(ValueError):
    """A supplied dice stream cannot satisfy a requested roll."""


class DiceSource:
    """Seeded random dice or a sequence of individual die faces."""

    def __init__(self, *, seed: int = 0, rolls: Iterable[int] | None = None) -> None:
        if type(seed) is not int:
            raise ValueError("seed must be an integer")
        self.kind = "sequence" if rolls is not None else "random"
        self._random = random.Random(seed)
        self._rolls: tuple[int, ...] = ()
        self._index = 0
        if rolls is not None:
            faces = tuple(rolls)
            if any(type(face) is not int for face in faces):
                raise ValueError("supplied die faces must be integers")
            self._rolls = faces

    def draw(self, sides: int) -> int:
        if type(sides) is not int or sides < 2:
            raise ValueError("a die must have at least 2 sides")
        if self.kind == "random":
            return self._random.randint(1, sides)
        if self._index >= len(self._rolls):
            raise DiceSourceError(f"supplied roll sequence exhausted; the next roll needs d{sides}")
        face = self._rolls[self._index]
        if not 1 <= face <= sides:
            raise DiceSourceError(
                f"supplied roll {self._index + 1} is {face}; d{sides} requires a face from 1 through {sides}"
            )
        self._index += 1
        return face

    def clone(self) -> "DiceSource":
        clone = object.__new__(DiceSource)
        clone.kind = self.kind
        clone._random = random.Random()
        clone._random.setstate(self._random.getstate())
        clone._rolls = self._rolls
        clone._index = self._index
        return clone

    def to_data(self) -> dict[str, Any]:
        if self.kind == "sequence":
            return {"kind": "sequence", "rolls": list(self._rolls), "index": self._index}
        return {"kind": "random", "random_state": _json_list(self._random.getstate())}

    @classmethod
    def from_data(cls, data: Any) -> "DiceSource":
        if not isinstance(data, dict):
            raise ValueError("save has no dice state")
        kind = data.get("kind")
        source = object.__new__(cls)
        source._random = random.Random()
        if kind == "random":
            try:
                source._random.setstate(_json_tuple(data["random_state"]))
            except (KeyError, TypeError, ValueError) as error:
                raise ValueError("save has invalid random-generator state") from error
            source.kind = "random"
            source._rolls = ()
            source._index = 0
            return source
        if kind == "sequence":
            rolls = data.get("rolls")
            index = data.get("index")
            if not isinstance(rolls, list) or any(type(face) is not int for face in rolls):
                raise ValueError("save has invalid supplied dice")
            if type(index) is not int or not 0 <= index <= len(rolls):
                raise ValueError("save has invalid supplied-dice position")
            source.kind = "sequence"
            source._rolls = tuple(rolls)
            source._index = index
            return source
        raise ValueError(f"unsupported dice provider kind {kind!r}")


def save_encounter(path: str | os.PathLike[str], state: EncounterState, dice: DiceSource) -> None:
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "save_version": SAVE_VERSION,
        "engine_compatibility": ENGINE_COMPATIBILITY,
        "content_compatibility": CONTENT_COMPATIBILITY,
        "state": _state_to_data(state),
        "dice": dice.to_data(),
    }
    temporary_path: str | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=destination.parent,
            prefix=f".{destination.name}.",
            suffix=".tmp",
            delete=False,
        ) as stream:
            temporary_path = stream.name
            json.dump(payload, stream, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary_path, destination)
    except Exception:
        if temporary_path is not None:
            try:
                os.unlink(temporary_path)
            except FileNotFoundError:
                pass
        raise


def load_encounter(path: str | os.PathLike[str]) -> tuple[EncounterState, DiceSource]:
    with Path(path).open("r", encoding="utf-8") as stream:
        payload = json.load(stream)
    if not isinstance(payload, dict):
        raise ValueError("save must contain a JSON object")
    if payload.get("save_version") != SAVE_VERSION:
        raise ValueError(f"unsupported save version {payload.get('save_version')!r}")
    if payload.get("engine_compatibility") != ENGINE_COMPATIBILITY:
        raise ValueError("save was made by an incompatible engine build")
    if payload.get("content_compatibility") != CONTENT_COMPATIBILITY:
        raise ValueError("save was made with incompatible encounter content")
    state = _state_from_data(payload.get("state"))
    dice = DiceSource.from_data(payload.get("dice"))
    if dice.kind == "sequence" and dice._index < len(state.creatures):
        raise ValueError("saved supplied-dice position predates initial initiative")
    return state, dice


def _state_to_data(state: EncounterState) -> dict[str, Any]:
    return {
        "setup_id": state.setup_id,
        "map_width": state.map_width,
        "map_height": state.map_height,
        "creatures": {
            actor_id: {
                "definition_id": creature.definition_id,
                "label": creature.label,
                "team": creature.team,
                "position": [creature.position.x, creature.position.y],
                "hp": creature.hp,
                "initiative": creature.initiative,
                "actions_remaining": creature.actions_remaining,
                "strikes_this_turn": creature.strikes_this_turn,
                "diagonals_this_turn": creature.diagonals_this_turn,
                "health_mode": creature.health_mode.value,
                "dying": creature.dying,
                "wounded": creature.wounded,
                "unconscious": creature.unconscious,
                "dead": creature.dead,
                "prone": creature.prone,
                "hero_points": creature.hero_points,
                "reaction_available": creature.reaction_available,
                "held_items": list(creature.held_items),
                "worn_items": list(creature.worn_items),
                "stowed_items": list(creature.stowed_items),
                "ammunition": dict(sorted(creature.ammunition.items())),
                "prepared_slots": [
                    [slot.slot_id, slot.source, slot.spell_id, slot.rank, slot.cantrip, slot.spent]
                    for slot in creature.prepared_slots
                ],
                "flourish_used_round": creature.flourish_used_round,
                "must_leave_occupied": creature.must_leave_occupied,
            }
            for actor_id, creature in state.creatures.items()
        },
        "initiative_order": list(state.initiative_order),
        "active_index": state.active_index,
        "round_number": state.round_number,
        "in_progress": state.in_progress,
        "winner_team": state.winner_team,
        "initiative_finalized": state.initiative_finalized,
        "pending_choice": _pending_to_data(state.pending_choice),
        "next_choice_id": state.next_choice_id,
        "initiative_hero_decided": sorted(state.initiative_hero_decided or ()),
        "initiative_tie_groups": [list(group) for group in (state.initiative_tie_groups or ())],
        "initiative_tie_orders": {
            str(index): list(actors) for index, actors in (state.initiative_tie_orders or {}).items()
        },
        "initiative_tie_group_index": state.initiative_tie_group_index,
        "initiative_reordered": sorted(state.initiative_reordered),
        "actor_start_counts": dict(sorted(state.actor_start_counts.items())),
        "active_effects": [
            [effect.effect_id, effect.kind, effect.source_actor_id,
             effect.target_actor_id, effect.value, effect.expires_at_source_start]
            for effect in state.active_effects
        ],
        "guidance_immunities": dict(sorted(state.guidance_immunities.items())),
        "taking_cover": sorted(state.taking_cover),
        "ground_items": [
            {"position": [position.x, position.y], "items": list(items)}
            for position, items in sorted((state.ground_items or {}).items())
            if items
        ],
    }


def _state_from_data(data: Any) -> EncounterState:
    if not isinstance(data, dict):
        raise ValueError("save has no encounter state")
    setup = get_setup(_required_str(data, "setup_id"))
    width = _required_int(data, "map_width")
    height = _required_int(data, "map_height")
    if width != setup.width or height != setup.height:
        raise ValueError("saved map dimensions do not match the encounter setup")
    raw_creatures = data.get("creatures")
    if not isinstance(raw_creatures, dict):
        raise ValueError("save has invalid creatures")
    expected_ids = {placement.actor_id for placement in setup.placements}
    if set(raw_creatures) != expected_ids:
        raise ValueError("saved actors do not match the encounter setup")

    creatures: dict[str, CreatureState] = {}
    for placement in setup.placements:
        actor_id = placement.actor_id
        raw = raw_creatures[actor_id]
        if not isinstance(raw, dict):
            raise ValueError(f"saved actor {actor_id!r} is invalid")
        definition_id = _required_str(raw, "definition_id")
        definition = get_definition(definition_id)
        if definition_id != placement.definition_id:
            raise ValueError(f"saved actor {actor_id!r} has an unsupported definition")
        label = _required_str(raw, "label")
        team = _required_str(raw, "team")
        if label != placement.label or team != placement.team:
            raise ValueError(f"saved actor {actor_id!r} does not match the encounter setup")
        position_data = raw.get("position")
        if (
            not isinstance(position_data, list)
            or len(position_data) != 2
            or any(type(value) is not int for value in position_data)
        ):
            raise ValueError(f"saved actor {actor_id!r} has invalid position")
        position = Position(position_data[0], position_data[1])
        if not in_bounds(position, width, height):
            raise ValueError(f"saved actor {actor_id!r} is outside the map")
        hp = _required_int(raw, "hp")
        actions_remaining = _required_int(raw, "actions_remaining")
        strikes_this_turn = _required_int(raw, "strikes_this_turn")
        diagonals_this_turn = _required_int(raw, "diagonals_this_turn")
        initiative = _required_int(raw, "initiative")
        if not 0 <= hp <= definition.hp:
            raise ValueError(f"saved actor {actor_id!r} has invalid Hit Points")
        if not definition.perception + 1 <= initiative <= definition.perception + 20:
            raise ValueError(f"saved actor {actor_id!r} has invalid initiative")
        if not 0 <= actions_remaining <= 3 or strikes_this_turn < 0 or diagonals_this_turn < 0:
            raise ValueError(f"saved actor {actor_id!r} has invalid turn counters")
        health_mode = HealthMode(_required_str(raw, "health_mode"))
        dying = _required_int(raw, "dying")
        wounded = _required_int(raw, "wounded")
        hero_points = _required_int(raw, "hero_points")
        unconscious = _required_bool(raw, "unconscious")
        dead = _required_bool(raw, "dead")
        prone = _required_bool(raw, "prone")
        reaction_available = _required_bool(raw, "reaction_available")
        held_items = _required_str_list(raw, "held_items")
        worn_items = _required_str_list(raw, "worn_items")
        stowed_items = _required_str_list(raw, "stowed_items")
        ammunition_raw = raw.get("ammunition")
        if not isinstance(ammunition_raw, dict) or any(
            not isinstance(item, str) or type(count) is not int or count < 0
            for item, count in ammunition_raw.items()
        ):
            raise ValueError(f"saved actor {actor_id!r} has invalid ammunition")
        prepared_raw = raw.get("prepared_slots")
        if not isinstance(prepared_raw, list):
            raise ValueError(f"saved actor {actor_id!r} has invalid prepared spells")
        prepared_slots: list[PreparedSlotState] = []
        for row in prepared_raw:
            if (
                not isinstance(row, list) or len(row) != 6
                or not isinstance(row[0], str) or not isinstance(row[1], str)
                or not isinstance(row[2], str) or type(row[3]) is not int
                or type(row[4]) is not bool or type(row[5]) is not bool
            ):
                raise ValueError(f"saved actor {actor_id!r} has invalid prepared slot")
            prepared_slots.append(PreparedSlotState(*row))
        flourish_used_round = _required_int(raw, "flourish_used_round")
        must_leave_occupied = _required_bool(raw, "must_leave_occupied")
        if health_mode is not HealthMode(definition.health_mode):
            raise ValueError(f"saved actor {actor_id!r} has an incompatible health mode")
        if not 0 <= hero_points <= 3 or not 0 <= dying <= 3 or wounded < 0:
            raise ValueError(f"saved actor {actor_id!r} has invalid health resources")
        attack_items = {attack.item_id for attack in definition.attacks if attack.item_id is not None}
        allowed_items = set(definition.held_items) | set(definition.worn_items) | set(definition.stowed_items)
        all_inventory = held_items + worn_items + stowed_items
        required_worn = set(definition.worn_items) - attack_items
        if (
            any(item not in allowed_items for item in all_inventory)
            or len(all_inventory) != len(set(all_inventory))
            or any(item not in attack_items for item in held_items + stowed_items)
            or not required_worn.issubset(worn_items)
        ):
            raise ValueError(f"saved actor {actor_id!r} has invalid equipment")
        expected_ammunition = dict(definition.ammunition)
        if (
            set(ammunition_raw) != set(expected_ammunition)
            or any(ammunition_raw[item] > expected_ammunition[item] for item in expected_ammunition)
        ):
            raise ValueError(f"saved actor {actor_id!r} has invalid ammunition")
        expected_slots = definition.prepared_spells
        if len(prepared_slots) != len(expected_slots):
            raise ValueError(f"saved actor {actor_id!r} has invalid prepared slots")
        for saved_slot, definition_slot in zip(prepared_slots, expected_slots):
            if (
                (saved_slot.slot_id, saved_slot.source, saved_slot.spell_id,
                 saved_slot.rank, saved_slot.cantrip)
                != (definition_slot.slot_id, definition_slot.source, definition_slot.spell_id,
                    definition_slot.rank, definition_slot.cantrip)
                or saved_slot.cantrip and saved_slot.spent
            ):
                raise ValueError(f"saved actor {actor_id!r} has invalid prepared slot facts")
        if health_mode is HealthMode.PC:
            if (dead and (hp != 0 or dying != 0 or unconscious)) or (hp == 0 and not unconscious):
                raise ValueError(f"saved PC {actor_id!r} has inconsistent unconscious/death state")
            if hp > 0 and (dying != 0 or unconscious or dead):
                raise ValueError(f"saved PC {actor_id!r} has impossible positive-HP conditions")
            if dying > 0 and (hp != 0 or not unconscious or dead):
                raise ValueError(f"saved PC {actor_id!r} has inconsistent dying state")
        elif dying != 0 or wounded != 0 or hero_points != 0:
            raise ValueError(f"non-PC actor {actor_id!r} has PC-only health conditions")
        elif health_mode is HealthMode.ORDINARY:
            if dead and (hp != 0 or unconscious):
                raise ValueError(f"dead ordinary actor {actor_id!r} has inconsistent health")
            if unconscious and (hp != 0 or not prone or dead):
                raise ValueError(f"unconscious ordinary actor {actor_id!r} has inconsistent conditions")
            if hp == 0 and not (dead or unconscious):
                raise ValueError(f"ordinary actor {actor_id!r} at 0 HP must be dead or unconscious")
            if hp > 0 and (dead or unconscious):
                raise ValueError(f"ordinary actor {actor_id!r} has impossible positive-HP conditions")
        elif dead or unconscious or prone:
            raise ValueError(f"prototype actor {actor_id!r} has unsupported conditions")
        if reaction_available and (
            "reactive_strike" not in definition.abilities or unconscious or dead
        ):
            raise ValueError(f"saved actor {actor_id!r} has an unavailable reaction")
        if health_mode is HealthMode.PROTOTYPE and (dead or reaction_available or held_items or worn_items):
            # The original S1 fixture has no inventory and no special PC/NPC
            # condition bookkeeping; reaction availability is harmless but is
            # still serialized from the S2 turn model, so allow that field.
            if dead or held_items or worn_items:
                raise ValueError(f"prototype actor {actor_id!r} has unsupported health or equipment state")
        creatures[actor_id] = CreatureState(
            actor_id=actor_id,
            definition_id=definition_id,
            label=label,
            team=team,
            position=position,
            hp=hp,
            initiative=initiative,
            actions_remaining=actions_remaining,
            strikes_this_turn=strikes_this_turn,
            diagonals_this_turn=diagonals_this_turn,
            health_mode=health_mode,
            dying=dying,
            wounded=wounded,
            unconscious=unconscious,
            dead=dead,
            prone=prone,
            hero_points=hero_points,
            reaction_available=reaction_available,
            held_items=held_items,
            worn_items=worn_items,
            stowed_items=stowed_items,
            ammunition=dict(ammunition_raw),
            prepared_slots=prepared_slots,
            flourish_used_round=flourish_used_round,
            must_leave_occupied=must_leave_occupied,
        )
    by_position: dict[Position, list[CreatureState]] = {}
    for creature in creatures.values():
        by_position.setdefault(creature.position, []).append(creature)
    for occupants in by_position.values():
        if len(occupants) < 2:
            continue
        for index, first in enumerate(occupants):
            for second in occupants[index + 1 :]:
                sizes = {"tiny": 0, "small": 1, "medium": 2}
                first_size = sizes.get(get_definition(first.definition_id).size, 99)
                second_size = sizes.get(get_definition(second.definition_id).size, 99)
                downed_share = (
                    (first.unconscious or first.dead) and first.prone and first_size <= second_size
                ) or (
                    (second.unconscious or second.dead) and second.prone and second_size <= first_size
                )
                living_ally_share = (
                    first.team == second.team
                    and not first.defeated and not second.defeated
                    and not first.unconscious and not second.unconscious
                    and (first.must_leave_occupied or second.must_leave_occupied)
                )
                if not downed_share and not living_ally_share:
                    raise ValueError("saved actors occupy an unsupported shared space")

    initiative_order = data.get("initiative_order")
    if (
        not isinstance(initiative_order, list)
        or any(not isinstance(actor_id, str) for actor_id in initiative_order)
        or (initiative_order and (set(initiative_order) != expected_ids or len(initiative_order) != len(expected_ids)))
    ):
        raise ValueError("save has invalid initiative order")
    initiative_finalized = _required_bool(data, "initiative_finalized")
    initiative_reordered = _required_str_list(data, "initiative_reordered")
    if not set(initiative_reordered).issubset(expected_ids) or len(set(initiative_reordered)) != len(initiative_reordered):
        raise ValueError("save has invalid initiative anchor moves")
    if any(
        creatures[actor_id].health_mode is not HealthMode.PC
        or creatures[actor_id].hp != 0
        or not (creatures[actor_id].unconscious or creatures[actor_id].dead)
        for actor_id in initiative_reordered
    ):
        raise ValueError("only a knocked-out PC can have a saved initiative anchor move")
    active_index = _required_int(data, "active_index")
    if active_index < 0 or (initiative_order and active_index >= len(initiative_order)):
        raise ValueError("save has invalid active turn")
    round_number = _required_int(data, "round_number")
    if round_number < 1:
        raise ValueError("save has invalid round number")
    if any(creature.flourish_used_round < 0 or creature.flourish_used_round > round_number for creature in creatures.values()):
        raise ValueError("save has invalid per-round flourish use")
    in_progress = data.get("in_progress")
    winner_team = data.get("winner_team")
    if type(in_progress) is not bool or (winner_team is not None and not isinstance(winner_team, str)):
        raise ValueError("save has invalid encounter outcome")
    if in_progress and winner_team is not None:
        raise ValueError("an unfinished encounter cannot have a winner")
    active_teams = {creature.team for creature in creatures.values() if is_combat_capable(creature)}
    pending_choice = _pending_from_data(data.get("pending_choice"))
    next_choice_id = _required_int(data, "next_choice_id")
    if next_choice_id < 1 or (pending_choice is not None and pending_choice.choice_id >= next_choice_id):
        raise ValueError("save has invalid choice sequence")
    if pending_choice is not None and not in_progress:
        raise ValueError("finished encounters cannot retain choices")
    if initiative_finalized and len(initiative_order) != len(expected_ids):
        raise ValueError("finalized initiative must include every actor")
    if not initiative_finalized:
        if pending_choice is None or pending_choice.kind not in ("initiative_hero_reroll", "initiative_tie") or active_index != 0:
            raise ValueError("unfinalized initiative requires a pending initiative choice")
        if pending_choice.kind == "initiative_hero_reroll" and initiative_order:
            raise ValueError("initiative order is not available before initiative choices finish")
        if pending_choice.kind == "initiative_tie" and len(initiative_order) != len(expected_ids):
            raise ValueError("initiative tie choice requires a complete ranked order")
    if initiative_finalized and not initiative_order:
        raise ValueError("finalized initiative must have an order")
    if initiative_finalized and not initiative_reordered:
        _validate_ranked_initiative(initiative_order, creatures, setup.placements)
    if initiative_finalized and initiative_order:
        active_actor_id = initiative_order[active_index]
    else:
        active_actor_id = None
    if in_progress and initiative_finalized:
        if len(active_teams) < 2:
            raise ValueError("an unfinished encounter must have active creatures on multiple teams")
        if active_actor_id is None:
            raise ValueError("unfinished encounter has no active actor")
        if any(
            creature.actions_remaining != 0
            or creature.strikes_this_turn != 0
            or creature.diagonals_this_turn != 0
            for actor_id, creature in creatures.items()
            if actor_id != active_actor_id
        ):
            raise ValueError("inactive actors cannot retain turn resources")
        active_creature = creatures[active_actor_id]
        if active_creature.defeated:
            raise ValueError("a defeated actor cannot own the active turn")
        if pending_choice is None and not (active_creature.unconscious or active_creature.dead) and not 1 <= active_creature.actions_remaining <= 3:
            raise ValueError("the saved active actor has impossible actions or health")
        if active_creature.unconscious and active_creature.actions_remaining != 0:
            raise ValueError("an unconscious active actor cannot retain actions")
        for creature in creatures.values():
            if not creature.must_leave_occupied:
                continue
            occupant = next(
                (other for other in creatures.values() if other.actor_id != creature.actor_id and other.position == creature.position),
                None,
            )
            if (
                creature.actor_id != active_actor_id
                or creature.actions_remaining < 1
                or creature.unconscious
                or occupant is None
                or occupant.team != creature.team
                or occupant.defeated
                or occupant.unconscious
            ):
                raise ValueError("saved move obligation does not match a living ally sharing the active actor's space")
        used_actions = 3 - active_creature.actions_remaining
        if active_creature.strikes_this_turn > used_actions:
            raise ValueError("saved attack count exceeds actions spent this turn")
        movement_actions = used_actions - active_creature.strikes_this_turn
        max_diagonals_per_move = max(1, (get_definition(active_creature.definition_id).land_speed_ft + 4) // 5)
        if active_creature.diagonals_this_turn > movement_actions * max_diagonals_per_move:
            raise ValueError("saved diagonal count exceeds possible movement this turn")
    elif in_progress and not initiative_finalized:
        if pending_choice is None or pending_choice.kind not in ("initiative_hero_reroll", "initiative_tie"):
            raise ValueError("unfinalized initiative requires an initiative choice")
        if any(creature.actions_remaining or creature.strikes_this_turn or creature.diagonals_this_turn for creature in creatures.values()):
            raise ValueError("actors cannot have turn resources before initiative is finalized")
    else:
        if len(active_teams) > 1 or winner_team != next(iter(active_teams), None):
            raise ValueError("finished encounter outcome does not match remaining actors")
        if any(creature.actions_remaining != 0 for creature in creatures.values()):
            raise ValueError("finished encounters cannot retain actions")

    initiative_hero_decided = _required_str_list(data, "initiative_hero_decided")
    if not set(initiative_hero_decided).issubset(expected_ids) or len(set(initiative_hero_decided)) != len(initiative_hero_decided):
        raise ValueError("save has invalid initiative Hero Point decisions")
    tie_groups_raw = data.get("initiative_tie_groups")
    if not isinstance(tie_groups_raw, list) or any(not isinstance(group, list) or any(not isinstance(x, str) for x in group) for group in tie_groups_raw):
        raise ValueError("save has invalid initiative tie groups")
    tie_groups = [tuple(group) for group in tie_groups_raw]
    if any(not set(group).issubset(expected_ids) or len(set(group)) != len(group) for group in tie_groups):
        raise ValueError("save has invalid actors in initiative tie groups")
    tie_orders_raw = data.get("initiative_tie_orders")
    if not isinstance(tie_orders_raw, dict):
        raise ValueError("save has invalid initiative tie progress")
    tie_orders: dict[int, list[str]] = {}
    for index_text, actors in tie_orders_raw.items():
        if not isinstance(index_text, str) or not index_text.isdigit() or not isinstance(actors, list) or any(not isinstance(actor, str) for actor in actors):
            raise ValueError("save has invalid initiative tie progress")
        index = int(index_text)
        if index >= len(tie_groups) or len(set(actors)) != len(actors) or not set(actors).issubset(tie_groups[index]):
            raise ValueError("save has invalid actors in initiative tie progress")
        tie_orders[index] = list(actors)
    tie_group_index = _required_int(data, "initiative_tie_group_index")
    if not 0 <= tie_group_index <= len(tie_groups):
        raise ValueError("save has invalid initiative tie cursor")
    if pending_choice is not None:
        for actor_id in (pending_choice.owner_actor_id, pending_choice.actor_id, pending_choice.target_id):
            if actor_id is not None and actor_id not in expected_ids:
                raise ValueError("pending choice refers to an unknown actor")
        if not set(pending_choice.tie_candidates).issubset(expected_ids) or not set(pending_choice.tie_selected).issubset(expected_ids):
            raise ValueError("pending choice has invalid tie actors")
        if pending_choice.kind == "initiative_tie" and any(option.option_id not in expected_ids for option in pending_choice.options):
            raise ValueError("initiative choice has invalid actor options")
    ground_items_raw = data.get("ground_items")
    if not isinstance(ground_items_raw, list):
        raise ValueError("save has invalid ground items")
    ground_items: dict[Position, list[str]] = {}
    for row in ground_items_raw:
        if not isinstance(row, dict):
            raise ValueError("save has invalid ground item entry")
        position_data = row.get("position")
        if not isinstance(position_data, list) or len(position_data) != 2 or any(type(x) is not int for x in position_data):
            raise ValueError("save has invalid ground item position")
        position = Position(*position_data)
        items = _required_str_list(row, "items")
        if not in_bounds(position, width, height) or not items or position in ground_items:
            raise ValueError("save has invalid ground item entry")
        ground_items[position] = items

    starts_raw = data.get("actor_start_counts")
    if (
        not isinstance(starts_raw, dict)
        or set(starts_raw) != expected_ids
        or any(type(value) is not int or value < 0 for value in starts_raw.values())
    ):
        raise ValueError("save has invalid actor start counters")
    effects_raw = data.get("active_effects")
    if not isinstance(effects_raw, list):
        raise ValueError("save has invalid active spell effects")
    effects: list[ActiveSpellEffect] = []
    for row in effects_raw:
        if (
            not isinstance(row, list) or len(row) != 6
            or any(not isinstance(value, str) or not value for value in row[:4])
            or type(row[4]) is not int or type(row[5]) is not int
            or row[4] < 1 or row[5] < 1
            or row[1] not in {"guidance", "enfeebled"}
            or row[2] not in expected_ids or row[3] not in expected_ids
            or row[5] <= starts_raw[row[2]]
        ):
            raise ValueError("save has invalid active spell effect")
        effects.append(ActiveSpellEffect(*row))
    immunity_raw = data.get("guidance_immunities")
    if (
        not isinstance(immunity_raw, dict)
        or any(actor_id not in expected_ids or type(until) is not int or until < round_number for actor_id, until in immunity_raw.items())
    ):
        raise ValueError("save has invalid Guidance immunity")
    taking_cover_raw = _required_str_list(data, "taking_cover")
    if not set(taking_cover_raw).issubset(expected_ids) or len(set(taking_cover_raw)) != len(taking_cover_raw):
        raise ValueError("save has invalid Take Cover state")

    return EncounterState(
        setup_id=setup.setup_id,
        map_width=width,
        map_height=height,
        creatures=creatures,
        initiative_order=initiative_order,
        active_index=active_index,
        round_number=round_number,
        in_progress=in_progress,
        winner_team=winner_team,
        initiative_finalized=initiative_finalized,
        pending_choice=pending_choice,
        next_choice_id=next_choice_id,
        initiative_hero_decided=set(initiative_hero_decided),
        ground_items=ground_items,
        initiative_tie_groups=tie_groups,
        initiative_tie_orders=tie_orders,
        initiative_tie_group_index=tie_group_index,
        initiative_reordered=set(initiative_reordered),
        actor_start_counts=dict(starts_raw),
        active_effects=effects,
        guidance_immunities=dict(immunity_raw),
        taking_cover=set(taking_cover_raw),
    )


def _required_str(data: dict[str, Any], key: str) -> str:
    value = data.get(key)
    if not isinstance(value, str) or not value:
        raise ValueError(f"save has invalid {key}")
    return value


def _validate_ranked_initiative(initiative_order, creatures, placements) -> None:
    """Check rank and GM ties unless a recorded PC knockout changed order."""
    setup_index = {placement.actor_id: index for index, placement in enumerate(placements)}
    ranks = [creatures[actor_id].initiative for actor_id in initiative_order]
    if any(left < right for left, right in zip(ranks, ranks[1:])):
        raise ValueError("saved initiative order conflicts with initiative results")
    by_rank: dict[int, list[str]] = {}
    for actor_id in initiative_order:
        by_rank.setdefault(creatures[actor_id].initiative, []).append(actor_id)
    for actors in by_rank.values():
        npcs = [actor_id for actor_id in actors if creatures[actor_id].health_mode is not HealthMode.PC]
        if npcs != sorted(npcs, key=lambda actor_id: setup_index[actor_id]):
            raise ValueError("saved NPC initiative ties conflict with stable setup order")
        for pc_id in (actor_id for actor_id in actors if creatures[actor_id].health_mode is HealthMode.PC):
            enemy_npcs = [
                actor_id
                for actor_id in npcs
                if creatures[actor_id].team != creatures[pc_id].team
            ]
            if any(actors.index(actor_id) > actors.index(pc_id) for actor_id in enemy_npcs):
                raise ValueError("an enemy NPC must precede a tied PC in initiative")


def _required_int(data: dict[str, Any], key: str) -> int:
    value = data.get(key)
    if type(value) is not int:
        raise ValueError(f"save has invalid {key}")
    return value


def _required_bool(data: dict[str, Any], key: str) -> bool:
    value = data.get(key)
    if type(value) is not bool:
        raise ValueError(f"save has invalid {key}")
    return value


def _required_str_list(data: dict[str, Any], key: str) -> list[str]:
    value = data.get(key)
    if not isinstance(value, list) or any(not isinstance(item, str) or not item for item in value):
        raise ValueError(f"save has invalid {key}")
    return list(value)


def _pending_to_data(pending) -> dict[str, Any] | None:
    if pending is None:
        return None
    return {
        "choice_id": pending.choice_id,
        "kind": pending.kind,
        "owner_actor_id": pending.owner_actor_id,
        "prompt": pending.prompt,
        "options": [[option.option_id, option.label] for option in pending.options],
        "details": list(pending.details),
        "actor_id": pending.actor_id,
        "target_id": pending.target_id,
        "attack_id": pending.attack_id,
        "attack_penalty": pending.attack_penalty,
        "attack_count": pending.attack_count,
        "check": _check_to_data(pending.check),
        "damage_result": _damage_to_data(pending.damage_result),
        "damage_text": pending.damage_text,
        "attack_critical": pending.attack_critical,
        "damage_type": pending.damage_type,
        "nonlethal": pending.nonlethal,
        "damage_bonus_dice": pending.damage_bonus_dice,
        "attack_actions_cost": pending.attack_actions_cost,
        "attack_count_cost": pending.attack_count_cost,
        "ranged_penalty": pending.ranged_penalty,
        "guidance_bonus": pending.guidance_bonus,
        "is_reaction": pending.is_reaction,
        "continuation": _continuation_to_data(pending.continuation),
        "initiative_roll": pending.initiative_roll,
        "initiative_modifier": pending.initiative_modifier,
        "tie_candidates": list(pending.tie_candidates),
        "tie_selected": list(pending.tie_selected),
        "health_normal": _transition_to_data(pending.health_normal),
        "health_heroic": _transition_to_data(pending.health_heroic),
        "transition_kind": pending.transition_kind,
        "check_kind": pending.check_kind,
        "check_owner_actor_id": pending.check_owner_actor_id,
        "spell_id": pending.spell_id,
        "slot_id": pending.slot_id,
        "actions_cost": pending.actions_cost,
        "spell_actions": pending.spell_actions,
        "include_self": pending.include_self,
        "effect_id": pending.effect_id,
        "damage_adjustment": pending.damage_adjustment,
        "damage_context": pending.damage_context,
        "target_ids": list(pending.target_ids),
    }


def _pending_from_data(data: Any) -> PendingChoice | None:
    if data is None:
        return None
    if not isinstance(data, dict):
        raise ValueError("save has invalid pending choice")
    choice_id = _required_int(data, "choice_id")
    kind = _required_str(data, "kind")
    if choice_id < 1 or kind not in {
        "initiative_hero_reroll", "initiative_tie", "attack_hero_reroll",
        "recovery_start_heroic", "recovery_hero_reroll", "recovery_heroic_increase",
        "heroic_recovery_damage", "reaction", "spell_target", "spell_self_inclusion",
        "spell_willingness", "guidance_use", "spell_attack_hero_reroll",
        "spell_save_hero_reroll", "spell_slot",
    }:
        raise ValueError("save has unsupported pending choice")
    owner = data.get("owner_actor_id")
    if owner is not None and (not isinstance(owner, str) or not owner):
        raise ValueError("save has invalid choice owner")
    prompt = _required_str(data, "prompt")
    raw_options = data.get("options")
    if not isinstance(raw_options, list) or not raw_options:
        raise ValueError("save has invalid choice options")
    options: list[ChoiceOption] = []
    for option in raw_options:
        if not isinstance(option, list) or len(option) != 2 or any(not isinstance(part, str) or not part for part in option):
            raise ValueError("save has invalid choice option")
        options.append(ChoiceOption(option[0], option[1]))
    if len({option.option_id for option in options}) != len(options):
        raise ValueError("save has duplicate choice options")
    details = _required_str_list(data, "details")
    optional_strings: dict[str, str | None] = {}
    for key in ("actor_id", "target_id", "attack_id", "damage_text", "transition_kind", "check_kind", "check_owner_actor_id", "spell_id", "slot_id", "effect_id", "damage_adjustment", "damage_context"):
        value = data.get(key)
        if value is not None and not isinstance(value, str):
            raise ValueError(f"save has invalid pending choice {key}")
        optional_strings[key] = value
    ints: dict[str, int] = {}
    for key in ("attack_penalty", "attack_count", "actions_cost", "spell_actions", "ranged_penalty", "guidance_bonus"):
        ints[key] = _required_int(data, key)
    if ints["attack_count"] < 0:
        raise ValueError("save has invalid pending attack count")
    attack_critical = _required_bool(data, "attack_critical")
    nonlethal = _required_bool(data, "nonlethal")
    is_reaction = _required_bool(data, "is_reaction")
    damage_bonus_dice = _required_int(data, "damage_bonus_dice")
    attack_actions_cost = _required_int(data, "attack_actions_cost")
    attack_count_cost = _required_int(data, "attack_count_cost")
    damage_type = data.get("damage_type")
    if damage_type is not None and not isinstance(damage_type, str):
        raise ValueError("save has invalid pending damage type")
    if damage_bonus_dice < 0 or attack_actions_cost < 0 or attack_count_cost < 0:
        raise ValueError("save has invalid pending attack costs")
    initiative_roll = data.get("initiative_roll")
    initiative_modifier = data.get("initiative_modifier")
    for value in (initiative_roll, initiative_modifier):
        if value is not None and type(value) is not int:
            raise ValueError("save has invalid pending initiative check")
    tie_candidates = _required_str_list(data, "tie_candidates")
    tie_selected = _required_str_list(data, "tie_selected")
    target_ids = _required_str_list(data, "target_ids")
    include_self = data.get("include_self")
    if include_self is not None and type(include_self) is not bool:
        raise ValueError("save has invalid pending self-inclusion choice")
    if set(tie_candidates) & set(tie_selected):
        raise ValueError("save has duplicate initiative tie actors")
    return PendingChoice(
        choice_id=choice_id,
        kind=kind,
        owner_actor_id=owner,
        prompt=prompt,
        options=tuple(options),
        details=tuple(details),
        actor_id=optional_strings["actor_id"],
        target_id=optional_strings["target_id"],
        attack_id=optional_strings["attack_id"],
        attack_penalty=ints["attack_penalty"],
        attack_count=ints["attack_count"],
        check=_check_from_data(data.get("check")),
        damage_result=_damage_from_data(data.get("damage_result")),
        damage_text=optional_strings["damage_text"],
        attack_critical=attack_critical,
        damage_type=damage_type,
        nonlethal=nonlethal,
        damage_bonus_dice=damage_bonus_dice,
        attack_actions_cost=attack_actions_cost,
        attack_count_cost=attack_count_cost,
        ranged_penalty=ints["ranged_penalty"],
        guidance_bonus=ints["guidance_bonus"],
        is_reaction=is_reaction,
        continuation=_continuation_from_data(data.get("continuation")),
        initiative_roll=initiative_roll,
        initiative_modifier=initiative_modifier,
        tie_candidates=tuple(tie_candidates),
        tie_selected=tuple(tie_selected),
        health_normal=_transition_from_data(data.get("health_normal")),
        health_heroic=_transition_from_data(data.get("health_heroic")),
        transition_kind=optional_strings["transition_kind"],
        check_kind=optional_strings["check_kind"],
        check_owner_actor_id=optional_strings["check_owner_actor_id"],
        spell_id=optional_strings["spell_id"],
        slot_id=optional_strings["slot_id"],
        actions_cost=ints["actions_cost"],
        spell_actions=ints["spell_actions"],
        include_self=include_self,
        effect_id=optional_strings["effect_id"],
        damage_adjustment=optional_strings["damage_adjustment"],
        damage_context=optional_strings["damage_context"],
        target_ids=tuple(target_ids),
    )


def _continuation_to_data(continuation: ActionContinuation | None) -> dict[str, Any] | None:
    if continuation is None:
        return None
    return {
        "kind": continuation.kind,
        "actor_id": continuation.actor_id,
        "path": [[point.x, point.y] for point in continuation.path],
        "next_step": continuation.next_step,
        "mode": continuation.mode,
        "item_id": continuation.item_id,
        "target_id": continuation.target_id,
        "attack_id": continuation.attack_id,
        "damage_type": continuation.damage_type,
        "nonlethal": continuation.nonlethal,
        "damage_bonus_dice": continuation.damage_bonus_dice,
        "attack_actions_cost": continuation.attack_actions_cost,
        "attack_count_cost": continuation.attack_count_cost,
        "attack_penalty": continuation.attack_penalty,
        "attack_count": continuation.attack_count,
        "seen_reactors": list(continuation.seen_reactors),
        "must_disrupt_on_critical": continuation.must_disrupt_on_critical,
        "vicious_swing": continuation.vicious_swing,
        "movement_kind": continuation.movement_kind,
        "reaction_trigger": continuation.reaction_trigger,
        "spell_id": continuation.spell_id,
        "spell_target_id": continuation.spell_target_id,
        "slot_id": continuation.slot_id,
        "spell_actions": continuation.spell_actions,
        "include_self": continuation.include_self,
        "spell_damage": _damage_to_data(continuation.spell_damage),
        "spell_check": _check_to_data(continuation.spell_check),
        "spell_save_degree": continuation.spell_save_degree,
        "target_ids": list(continuation.target_ids),
        "ranged_penalty": continuation.ranged_penalty,
        "guidance_bonus": continuation.guidance_bonus,
        "guidance_checked": continuation.guidance_checked,
        "stage": continuation.stage,
        "parent_continuation": _continuation_to_data(continuation.parent_continuation),
        "attack_count_committed": continuation.attack_count_committed,
    }


def _continuation_from_data(data: Any) -> ActionContinuation | None:
    if data is None:
        return None
    if not isinstance(data, dict):
        raise ValueError("save has invalid interrupted action")
    path_data = data.get("path")
    if not isinstance(path_data, list) or any(
        not isinstance(point, list)
        or len(point) != 2
        or any(type(value) is not int for value in point)
        for point in path_data
    ):
        raise ValueError("save has invalid interrupted movement path")
    optional_strings = {}
    for key in ("mode", "item_id", "target_id", "attack_id", "damage_type", "movement_kind", "reaction_trigger", "spell_id", "spell_target_id", "slot_id", "stage"):
        value = data.get(key)
        if value is not None and not isinstance(value, str):
            raise ValueError(f"save has invalid interrupted action {key}")
        optional_strings[key] = value
    integers = {
        key: _required_int(data, key)
        for key in ("next_step", "damage_bonus_dice", "attack_actions_cost", "attack_count_cost", "attack_penalty", "attack_count", "spell_actions", "ranged_penalty", "guidance_bonus")
    }
    seen_reactors = _required_str_list(data, "seen_reactors")
    target_ids = _required_str_list(data, "target_ids")
    include_self = data.get("include_self")
    spell_save_degree = data.get("spell_save_degree")
    if include_self is not None and type(include_self) is not bool:
        raise ValueError("save has invalid interrupted spell self-inclusion")
    if spell_save_degree is not None and (type(spell_save_degree) is not int or not 0 <= spell_save_degree <= 3):
        raise ValueError("save has invalid interrupted save degree")
    if (
        integers["next_step"] < 0
        or integers["damage_bonus_dice"] < 0
        or integers["attack_actions_cost"] < 0
        or integers["attack_count_cost"] < 0
        or len(set(seen_reactors)) != len(seen_reactors)
    ):
        raise ValueError("save has invalid interrupted action counters")
    return ActionContinuation(
        kind=_required_str(data, "kind"),
        actor_id=_required_str(data, "actor_id"),
        path=tuple(Position(*point) for point in path_data),
        next_step=integers["next_step"],
        mode=optional_strings["mode"],
        item_id=optional_strings["item_id"],
        target_id=optional_strings["target_id"],
        attack_id=optional_strings["attack_id"],
        damage_type=optional_strings["damage_type"],
        nonlethal=_required_bool(data, "nonlethal"),
        damage_bonus_dice=integers["damage_bonus_dice"],
        attack_actions_cost=integers["attack_actions_cost"],
        attack_count_cost=integers["attack_count_cost"],
        attack_penalty=integers["attack_penalty"],
        attack_count=integers["attack_count"],
        seen_reactors=seen_reactors,
        must_disrupt_on_critical=_required_bool(data, "must_disrupt_on_critical"),
        vicious_swing=_required_bool(data, "vicious_swing"),
        movement_kind=optional_strings["movement_kind"],
        reaction_trigger=optional_strings["reaction_trigger"],
        spell_id=optional_strings["spell_id"],
        spell_target_id=optional_strings["spell_target_id"],
        slot_id=optional_strings["slot_id"],
        spell_actions=integers["spell_actions"],
        include_self=include_self,
        spell_damage=_damage_from_data(data.get("spell_damage")),
        spell_check=_check_from_data(data.get("spell_check")),
        spell_save_degree=spell_save_degree,
        target_ids=tuple(target_ids),
        ranged_penalty=integers["ranged_penalty"],
        guidance_bonus=integers["guidance_bonus"],
        guidance_checked=_required_bool(data, "guidance_checked"),
        stage=optional_strings["stage"],
        parent_continuation=_continuation_from_data(data.get("parent_continuation")),
        attack_count_committed=_required_bool(data, "attack_count_committed"),
    )


def _check_to_data(check: CheckResult | None) -> dict[str, Any] | None:
    if check is None:
        return None
    return {
        "die": check.die,
        "modifier": check.modifier,
        "dc": check.dc,
        "total": check.total,
        "degree_before_adjustments": int(check.degree_before_adjustments),
        "degree": int(check.degree),
        "adjustments": [[item.stage, item.amount, item.reason] for item in check.adjustments],
        "attack_id": check.attack_id,
        "attack_count": check.attack_count,
        "map_penalty": check.map_penalty,
        "traits": list(check.traits),
        "modifier_breakdown": [
            [modifier.amount, modifier.modifier_type, modifier.source]
            for modifier in check.modifier_breakdown
        ],
    }


def _check_from_data(data: Any) -> CheckResult | None:
    if data is None:
        return None
    if not isinstance(data, dict):
        raise ValueError("save has invalid pending check")
    adjustments_raw = data.get("adjustments")
    if not isinstance(adjustments_raw, list):
        raise ValueError("save has invalid pending check adjustments")
    adjustments: list[DegreeChange] = []
    for entry in adjustments_raw:
        if not isinstance(entry, list) or len(entry) != 3 or not isinstance(entry[0], str) or type(entry[1]) is not int or not isinstance(entry[2], str):
            raise ValueError("save has invalid pending check adjustment")
        adjustments.append(DegreeChange(entry[0], entry[1], entry[2]))
    traits = _required_str_list(data, "traits")
    modifiers_raw = data.get("modifier_breakdown")
    if not isinstance(modifiers_raw, list):
        raise ValueError("save has invalid pending check modifier breakdown")
    modifiers: list[Modifier] = []
    for entry in modifiers_raw:
        if (
            not isinstance(entry, list)
            or len(entry) != 3
            or type(entry[0]) is not int
            or not isinstance(entry[1], str)
            or not entry[1]
            or not isinstance(entry[2], str)
            or not entry[2]
        ):
            raise ValueError("save has invalid pending check modifier")
        modifiers.append(Modifier(entry[0], entry[1], entry[2]))
    attack_id = data.get("attack_id")
    attack_count = data.get("attack_count")
    if attack_id is not None and not isinstance(attack_id, str):
        raise ValueError("save has invalid pending attack id")
    if attack_count is not None and (type(attack_count) is not int or attack_count < 1):
        raise ValueError("save has invalid pending attack count")
    die = _required_int(data, "die")
    if not 1 <= die <= 20:
        raise ValueError("save has invalid pending check die")
    try:
        before = DegreeOfSuccess(_required_int(data, "degree_before_adjustments"))
        degree = DegreeOfSuccess(_required_int(data, "degree"))
    except ValueError as error:
        raise ValueError("save has invalid pending check degree") from error
    check = CheckResult(
        die=die,
        modifier=_required_int(data, "modifier"),
        dc=_required_int(data, "dc"),
        total=_required_int(data, "total"),
        degree_before_adjustments=before,
        degree=degree,
        adjustments=tuple(adjustments),
        attack_id=attack_id,
        attack_count=attack_count,
        map_penalty=_required_int(data, "map_penalty"),
        traits=tuple(traits),
        modifier_breakdown=tuple(modifiers),
    )
    if replace(check, modifier_breakdown=()) != resolve_check(
        check.die,
        check.modifier,
        check.dc,
        attack_id=check.attack_id,
        attack_count=check.attack_count,
        map_penalty=check.map_penalty,
        traits=check.traits,
    ):
        raise ValueError("save has internally inconsistent pending check arithmetic or degree")
    if combine_modifiers(check.modifier_breakdown) != check.modifier:
        raise ValueError("save has internally inconsistent pending check modifiers")
    return check


def _damage_to_data(result: DamageResult | None) -> dict[str, Any] | None:
    if result is None:
        return None
    return {
        "rolled_total": result.rolled_total,
        "multiplier": result.multiplier,
        "total": result.total,
        "adjustment": result.adjustment,
        "components": [
            [component.source, component.damage_type, component.dice_sides,
             list(component.rolls), component.modifier, component.amount]
            for component in result.components
        ],
    }


def _damage_from_data(data: Any) -> DamageResult | None:
    if data is None:
        return None
    if not isinstance(data, dict) or not isinstance(data.get("components"), list):
        raise ValueError("save has invalid pending damage")
    components: list[DamageComponent] = []
    for row in data["components"]:
        if not isinstance(row, list) or len(row) != 6:
            raise ValueError("save has invalid pending damage component")
        source, damage_type, sides, rolls, modifier, amount = row
        if not isinstance(source, str) or not isinstance(damage_type, str) or type(sides) is not int or sides < 2 or not isinstance(rolls, list) or any(type(face) is not int or not 1 <= face <= sides for face in rolls) or type(modifier) is not int or type(amount) is not int:
            raise ValueError("save has invalid pending damage component")
        components.append(DamageComponent(source, damage_type, sides, tuple(rolls), modifier, amount))
    rolled_total = _required_int(data, "rolled_total")
    multiplier = _required_int(data, "multiplier")
    total = _required_int(data, "total")
    adjustment = data.get("adjustment")
    if adjustment is not None and not isinstance(adjustment, str):
        raise ValueError("save has invalid pending damage adjustment")
    component_total = sum(component.amount for component in components)
    if multiplier not in (1, 2) or total != component_total:
        raise ValueError("save has inconsistent pending damage")
    raw_total = sum(sum(component.rolls) + component.modifier for component in components)
    if adjustment is None and (total != rolled_total * multiplier or raw_total != rolled_total):
        raise ValueError("save has inconsistent pending damage")
    if adjustment is not None:
        if adjustment.startswith("basic_save:"):
            if len(components) != 1 or multiplier != 1:
                raise ValueError("save has inconsistent basic-save damage")
            try:
                degree = DegreeOfSuccess[adjustment.removeprefix("basic_save:").upper()]
            except KeyError as error:
                raise ValueError("save has an invalid basic-save degree") from error
            raw = raw_total
            if degree is DegreeOfSuccess.CRITICAL_SUCCESS:
                expected = 0
            elif degree is DegreeOfSuccess.SUCCESS:
                expected = 1 if raw == 1 else raw // 2
            elif degree is DegreeOfSuccess.FAILURE:
                expected = raw
            else:
                expected = raw * 2
            if total != expected or rolled_total != raw:
                raise ValueError("save has inconsistent basic-save damage")
        elif adjustment == "deadly_after_critical":
            if (
                multiplier != 2 or len(components) < 2
                or components[0].amount != (sum(components[0].rolls) + components[0].modifier) * 2
                or any(component.amount != sum(component.rolls) + component.modifier for component in components[1:])
                or raw_total != rolled_total
                or total != components[0].amount + sum(component.amount for component in components[1:])
            ):
                raise ValueError("save has inconsistent deadly damage")
        else:
            raise ValueError("save has unsupported pending damage adjustment")
    return DamageResult(tuple(components), rolled_total, multiplier, total, adjustment)


def _transition_to_data(transition: HealthTransition | None) -> dict[str, Any] | None:
    if transition is None:
        return None
    state = transition.state
    return {
        "state": [state.hp, state.max_hp, state.dying, state.wounded, state.unconscious, state.dead],
        "flags": [transition.knocked_out, transition.initiative_before_current_turn,
                  transition.drop_held_items, transition.fall_prone, transition.dying_increased,
                  transition.dying_lost, transition.stabilized, transition.massive_damage_death],
        "heroic_recovery_available": transition.heroic_recovery_available,
        "heroic_recovery_option": _transition_to_data(transition.heroic_recovery_option),
        "hero_points_spent": transition.hero_points_spent,
    }


def _transition_from_data(data: Any) -> HealthTransition | None:
    if data is None:
        return None
    if not isinstance(data, dict):
        raise ValueError("save has invalid pending health transition")
    raw_state = data.get("state")
    raw_flags = data.get("flags")
    if not isinstance(raw_state, list) or len(raw_state) != 6 or any(type(x) not in (int, bool) for x in raw_state):
        raise ValueError("save has invalid pending health state")
    if type(raw_state[4]) is not bool or type(raw_state[5]) is not bool:
        raise ValueError("save has invalid pending health conditions")
    if not isinstance(raw_flags, list) or len(raw_flags) != 8 or any(type(x) is not bool for x in raw_flags):
        raise ValueError("save has invalid pending health flags")
    state = HealthState(raw_state[0], raw_state[1], raw_state[2], raw_state[3], raw_state[4], raw_state[5])
    heroic_available = data.get("heroic_recovery_available")
    if type(heroic_available) is not bool:
        raise ValueError("save has invalid pending Heroic Recovery flag")
    spent = _required_int(data, "hero_points_spent")
    if spent < 0:
        raise ValueError("save has invalid pending Hero Point cost")
    return HealthTransition(
        state=state,
        knocked_out=raw_flags[0],
        initiative_before_current_turn=raw_flags[1],
        drop_held_items=raw_flags[2],
        fall_prone=raw_flags[3],
        dying_increased=raw_flags[4],
        dying_lost=raw_flags[5],
        stabilized=raw_flags[6],
        massive_damage_death=raw_flags[7],
        heroic_recovery_available=heroic_available,
        heroic_recovery_option=_transition_from_data(data.get("heroic_recovery_option")),
        hero_points_spent=spent,
    )


def _json_list(value: Any) -> Any:
    if isinstance(value, tuple):
        return [_json_list(item) for item in value]
    return value


def _json_tuple(value: Any) -> Any:
    if isinstance(value, list):
        return tuple(_json_tuple(item) for item in value)
    return value
