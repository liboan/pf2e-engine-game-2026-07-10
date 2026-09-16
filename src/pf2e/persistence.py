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
    ActiveConditionEffect,
    ActiveSpellEffect,
    ActiveItemSpellEffect,
    ChoiceOption,
    ConditionImmunity,
    CreatureState,
    EffectExpiration,
    EncounterState,
    HealthMode,
    GuidanceImmunity,
    HuntedPreyState,
    LightOrb,
    PairedStrikeContinuation,
    PairedStrikeOutcome,
    PairedStrikeSelection,
    PendingChoice,
    DamageResolution,
    RaisedShieldState,
    ShieldBlockRecord,
    Position,
    PreparedSlotState,
    SpontaneousSlotState,
    SavedCheckContext,
    is_combat_capable,
)
from .conditions import CheckContext, ConditionValue, effective_condition_value
from .health import HealthState, HealthTransition
from .items import ItemInstance, STEEL_SHIELD, runtime_item_instance_id
from .rune_content import ITEM_CATEGORIES, weapon_rune_profile_for_item
from .checks import (
    CheckResult,
    DegreeOfSuccess,
    DegreeChange,
    Modifier,
    combine_modifiers,
    resolve_assurance_check,
    resolve_check,
)
from .damage import (
    DamageComponent,
    DamageGroup,
    DamagePartRef,
    DamageResult,
    DefenseChoice,
    DefenseSelection,
)
from .space import in_bounds
from .barbarian import (
    AcceptedMagicEffect,
    ActiveRage,
    BarbarianState,
    RageModeChoice,
    SpellcastWitness,
    validate_barbarian_state,
)
from .investigator import (
    ATTACK_STRATAGEM,
    InvestigatorWeaknessBonus,
    stratagem_from_data,
    stratagem_to_data,
    validate_stratagem_state,
)
from .swashbuckler import effective_speed_ft


SAVE_VERSION = 17
ENGINE_COMPATIBILITY = "pf2e-s3i-thief-rogue-v1"
CONTENT_COMPATIBILITY = "pf2e-s3i-thief-rogue-content-v1"


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


def _barbarian_state_to_data(state: BarbarianState | None) -> dict[str, Any] | None:
    if state is None:
        return None
    rage = state.rage
    return {
        "instinct_id": state.instinct_id,
        "animal_choice": state.animal_choice,
        "dragon_choice": state.dragon_choice,
        "giant_weapon_id": state.giant_weapon_id,
        "class_feat_id": state.class_feat_id,
        "bonus_feat_id": state.bonus_feat_id,
        "next_rage_instance": state.next_rage_instance,
        "rage": None if rage is None else {
            "mode_id": rage.mode_id,
            "started_at_seconds": rage.started_at_seconds,
            "expires_at_seconds": rage.expires_at_seconds,
            "temporary_hp_source_id": rage.temporary_hp_source_id,
            "temporary_hp_gained": rage.temporary_hp_gained,
            "damage_type": rage.damage_type,
            "action_traits": sorted(rage.action_traits),
            "ghost_touch": rage.ghost_touch,
        },
        "rage_temp_hp_available_at_seconds": state.rage_temp_hp_available_at_seconds,
        "superstition_heal_available_at_seconds": state.superstition_heal_available_at_seconds,
        "spellcast_witnesses": [
            [witness.caster_actor_id, witness.witnessed_at_seconds]
            for witness in state.spellcast_witnesses
        ],
        "accepted_magic_effects": [
            [effect.effect_id, effect.expires_at_seconds]
            for effect in state.accepted_magic_effects
        ],
        "anathema_violated_at_downtime_day": state.anathema_violated_at_downtime_day,
        "superstition_recentered_at_downtime_day": state.superstition_recentered_at_downtime_day,
    }


def _barbarian_state_from_data(data: Any) -> BarbarianState | None:
    if data is None:
        return None
    if not isinstance(data, dict):
        raise ValueError("save has invalid Barbarian state")
    strings = ("instinct_id",)
    if any(not isinstance(data.get(key), str) or not data[key] for key in strings):
        raise ValueError("save has invalid Barbarian instinct")
    optional_strings = ("animal_choice", "dragon_choice", "giant_weapon_id", "class_feat_id", "bonus_feat_id")
    if any(data.get(key) is not None and (not isinstance(data[key], str) or not data[key]) for key in optional_strings):
        raise ValueError("save has invalid Barbarian build choice")
    next_rage_instance = data.get("next_rage_instance")
    if type(next_rage_instance) is not int or next_rage_instance < 1:
        raise ValueError("save has invalid next Rage instance")
    rage_raw = data.get("rage")
    rage = None
    if rage_raw is not None:
        if not isinstance(rage_raw, dict):
            raise ValueError("save has invalid active Rage")
        mode_id = rage_raw.get("mode_id")
        started = rage_raw.get("started_at_seconds")
        expires = rage_raw.get("expires_at_seconds")
        source = rage_raw.get("temporary_hp_source_id")
        gained = rage_raw.get("temporary_hp_gained")
        damage_type = rage_raw.get("damage_type")
        traits = rage_raw.get("action_traits")
        ghost_touch = rage_raw.get("ghost_touch")
        if (
            not isinstance(mode_id, str) or not mode_id
            or type(started) is not int or type(expires) is not int
            or (source is not None and (not isinstance(source, str) or not source))
            or type(gained) is not int
            or (damage_type is not None and (not isinstance(damage_type, str) or not damage_type))
            or not isinstance(traits, list) or any(not isinstance(item, str) or not item for item in traits)
            or type(ghost_touch) is not bool
        ):
            raise ValueError("save has invalid active Rage")
        rage = ActiveRage(mode_id, started, expires, source, gained, damage_type, frozenset(traits), ghost_touch)
    for key in ("rage_temp_hp_available_at_seconds", "superstition_heal_available_at_seconds"):
        if type(data.get(key)) is not int or data[key] < 0:
            raise ValueError("save has invalid Barbarian cooldown")
    witnesses_raw = data.get("spellcast_witnesses")
    if not isinstance(witnesses_raw, list):
        raise ValueError("save has invalid spellcast witnesses")
    witnesses: list[SpellcastWitness] = []
    for row in witnesses_raw:
        if not isinstance(row, list) or len(row) != 2 or not isinstance(row[0], str) or not row[0] or type(row[1]) is not int:
            raise ValueError("save has invalid spellcast witness")
        witnesses.append(SpellcastWitness(row[0], row[1]))
    accepted_raw = data.get("accepted_magic_effects")
    if not isinstance(accepted_raw, list):
        raise ValueError("save has invalid accepted magic effects")
    accepted: list[AcceptedMagicEffect] = []
    for row in accepted_raw:
        if (
            not isinstance(row, list) or len(row) != 2
            or not isinstance(row[0], str) or not row[0]
            or (row[1] is not None and type(row[1]) is not int)
        ):
            raise ValueError("save has invalid accepted magic effect")
        accepted.append(AcceptedMagicEffect(row[0], row[1]))
    violation = data.get("anathema_violated_at_downtime_day")
    recentered = data.get("superstition_recentered_at_downtime_day")
    if (violation is not None and type(violation) is not int) or (recentered is not None and type(recentered) is not int):
        raise ValueError("save has invalid Barbarian downtime context")
    state = BarbarianState(
        instinct_id=data["instinct_id"],
        animal_choice=data.get("animal_choice"),
        dragon_choice=data.get("dragon_choice"),
        giant_weapon_id=data.get("giant_weapon_id"),
        class_feat_id=data.get("class_feat_id"),
        bonus_feat_id=data.get("bonus_feat_id"),
        next_rage_instance=next_rage_instance,
        rage=rage,
        rage_temp_hp_available_at_seconds=data["rage_temp_hp_available_at_seconds"],
        superstition_heal_available_at_seconds=data["superstition_heal_available_at_seconds"],
        spellcast_witnesses=tuple(witnesses),
        accepted_magic_effects=tuple(accepted),
        anathema_violated_at_downtime_day=violation,
        superstition_recentered_at_downtime_day=recentered,
    )
    try:
        validate_barbarian_state(state)
    except ValueError as error:
        raise ValueError("save has invalid Barbarian state") from error
    return state


def _state_to_data(state: EncounterState) -> dict[str, Any]:
    return {
        "setup_id": state.setup_id,
        "map_width": state.map_width,
        "map_height": state.map_height,
        "ambient_light": state.ambient_light,
        "light_orbs": [
            [
                orb.stable_id,
                orb.caster_actor_id,
                orb.rank,
                orb.color,
                None if orb.point is None else [orb.point.x, orb.point.y],
                orb.attached_actor_id,
                orb.owner_preparation,
            ]
            for orb in state.light_orbs
        ],
        "next_light_orb_id": state.next_light_orb_id,
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
                "spontaneous_slots": [
                    [slot.slot_id, slot.source, slot.rank, slot.capacity, slot.remaining]
                    for slot in creature.spontaneous_slots
                ],
                "focus_points": creature.focus_points,
                "focus_capacity": creature.focus_capacity,
                "flourish_used_round": creature.flourish_used_round,
                "must_leave_occupied": creature.must_leave_occupied,
                "temporary_hp": creature.temporary_hp,
                "temporary_hp_source_id": creature.temporary_hp_source_id,
                "temporary_hp_expires_at_seconds": creature.temporary_hp_expires_at_seconds,
                "hunted_prey": creature.hunted_prey.target_actor_id if creature.hunted_prey else None,
                "precision_used_round": creature.precision_used_round,
                "panache": creature.panache,
                "panache_expires_at_end": creature.panache_expires_at_end,
                "finisher_used_this_turn": creature.finisher_used_this_turn,
                "barbarian_state": _barbarian_state_to_data(creature.barbarian_state),
                "escape_lockout_until_start": creature.escape_lockout_until_start,
                "investigator_stratagem": stratagem_to_data(creature.investigator_stratagem),
                "investigator_knowledge_attempts": dict(sorted(creature.investigator_knowledge_attempts.items())),
                "investigator_knowledge_exhausted": sorted(creature.investigator_knowledge_exhausted),
                "investigator_examinations_completed": sorted(creature.investigator_examinations_completed),
            }
            for actor_id, creature in state.creatures.items()
        },
        "initiative_order": list(state.initiative_order),
        "initiative_skills": dict(sorted(state.initiative_skills.items())),
        "initiative_contexts": dict(sorted(state.initiative_contexts.items())),
        "active_index": state.active_index,
        "round_number": state.round_number,
        "in_progress": state.in_progress,
        "winner_team": state.winner_team,
        "initiative_finalized": state.initiative_finalized,
        "pending_choice": _pending_to_data(state.pending_choice),
        "next_choice_id": state.next_choice_id,
        "initiative_hero_decided": sorted(state.initiative_hero_decided or ()),
        "quick_tempered_decided": sorted(state.quick_tempered_decided or ()),
        "item_instances": {
            instance_id: {
                "definition_id": instance.definition_id,
                "quantity": instance.quantity,
                "charges": instance.charges,
                "hp": instance.hp,
                "rune_ids": list(instance.rune_ids),
                "invested": instance.invested,
            }
            for instance_id, instance in sorted((state.item_instances or {}).items())
        },
        "raised_shields": {
            actor_id: [raised.instance_id, raised.expires_at_owner_start]
            for actor_id, raised in sorted((state.raised_shields or {}).items())
        },
        "initiative_tie_groups": [list(group) for group in (state.initiative_tie_groups or ())],
        "initiative_tie_orders": {
            str(index): list(actors) for index, actors in (state.initiative_tie_orders or {}).items()
        },
        "initiative_tie_group_index": state.initiative_tie_group_index,
        "initiative_reordered": sorted(state.initiative_reordered),
        "actor_start_counts": dict(sorted(state.actor_start_counts.items())),
        "actor_end_counts": dict(sorted(state.actor_end_counts.items())),
        "feint_off_guard_effects": [
            [
                effect.effect_id,
                effect.source_actor_id,
                effect.target_actor_id,
                effect.eligible_attacker_id,
                effect.scope.value,
                [effect.expiration.anchor_actor_id, effect.expiration.boundary,
                 effect.expiration.occurrence],
                effect.consume_on_next_attack,
            ]
            for effect in state.feint_off_guard_effects
        ],
        "world_time_seconds": state.world_time_seconds,
        "encounter_start_seconds": state.encounter_start_seconds,
        "active_effects": [
            [effect.effect_id, effect.kind, effect.source_actor_id,
             effect.target_actor_id, effect.value, effect.expires_at_source_start,
             effect.expires_at_world_time]
            for effect in state.active_effects
        ],
        "active_item_effects": [
            [effect.effect_id, effect.kind, effect.source_actor_id, effect.item_id,
             effect.expires_at_source_start, effect.expires_at_world_time]
            for effect in state.active_item_effects
        ],
        "condition_effects": [
            [effect.effect_id, effect.kind, effect.source_actor_id,
             effect.target_actor_id, effect.value,
             [effect.expiration.anchor_actor_id, effect.expiration.boundary,
              effect.expiration.occurrence], effect.dc]
            for effect in state.condition_effects
        ],
        "condition_immunities": [
            [immunity.kind, immunity.source_actor_id, immunity.target_actor_id,
             immunity.expires_at_seconds]
            for immunity in state.condition_immunities
        ],
        "guidance_immunity_deadlines": dict(sorted(state.guidance_immunity_deadlines.items())),
        "sure_strike_immunity_deadlines": dict(sorted(state.sure_strike_immunity_deadlines.items())),
        "taking_cover": sorted(state.taking_cover),
        "preparation_day": state.preparation_day,
        "rested_actor_ids": sorted(state.rested_actor_ids),
        "last_prepared_day": dict(sorted(state.last_prepared_day.items())),
        "justice_aura_active": sorted(state.justice_aura_active),
        "desperate_prayer_used": sorted(state.desperate_prayer_used),
        "desperate_prayer_points": sorted(state.desperate_prayer_points),
        "investigator_weakness_bonuses": [
            [
                bonus.source_actor_id,
                bonus.target_actor_id,
                bonus.recipient_actor_id,
                bonus.expires_at_actor_start,
            ]
            for bonus in state.investigator_weakness_bonuses
        ],
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
    ambient_light = _required_str(data, "ambient_light")
    if ambient_light not in {"bright", "dim"}:
        raise ValueError("save has unsupported scene ambient light")
    if ambient_light != setup.ambient_light:
        raise ValueError("saved scene ambient light does not match the encounter setup")
    world_time_seconds = _required_int(data, "world_time_seconds")
    if world_time_seconds < 0:
        raise ValueError("save has invalid encounter world clock")
    encounter_start_seconds = _required_int(data, "encounter_start_seconds")
    if encounter_start_seconds < 0 or world_time_seconds < encounter_start_seconds:
        raise ValueError("save has invalid encounter start clock")
    in_progress = data.get("in_progress")
    winner_team = data.get("winner_team")
    if type(in_progress) is not bool or (winner_team is not None and not isinstance(winner_team, str)):
        raise ValueError("save has invalid encounter outcome")
    if width != setup.width or height != setup.height:
        raise ValueError("saved map dimensions do not match the encounter setup")
    raw_creatures = data.get("creatures")
    if not isinstance(raw_creatures, dict):
        raise ValueError("save has invalid creatures")
    expected_ids = {placement.actor_id for placement in setup.placements}
    if set(raw_creatures) != expected_ids:
        raise ValueError("saved actors do not match the encounter setup")
    initiative_skills_raw = data.get("initiative_skills")
    initiative_contexts_raw = data.get("initiative_contexts")
    if (
        not isinstance(initiative_skills_raw, dict)
        or set(initiative_skills_raw) != expected_ids
        or any(not isinstance(value, str) or not value for value in initiative_skills_raw.values())
        or not isinstance(initiative_contexts_raw, dict)
        or set(initiative_contexts_raw) != expected_ids
        or any(value is not None and (not isinstance(value, str) or not value) for value in initiative_contexts_raw.values())
    ):
        raise ValueError("save has invalid initiative statistic metadata")
    expected_initiative_skills = {placement.actor_id: placement.initiative_skill for placement in setup.placements}
    expected_initiative_contexts = {placement.actor_id: placement.initiative_context for placement in setup.placements}
    if initiative_skills_raw != expected_initiative_skills or initiative_contexts_raw != expected_initiative_contexts:
        raise ValueError("saved initiative statistic metadata does not match the encounter setup")

    initial_item_instances: dict[str, ItemInstance] = {}
    for placement in setup.placements:
        for item in get_definition(placement.definition_id).item_instances:
            instance_id = runtime_item_instance_id(placement.actor_id, item.instance_id)
            if instance_id in initial_item_instances:
                raise ValueError("setup has duplicate stable item identities")
            initial_item_instances[instance_id] = replace(item, instance_id=instance_id)
    item_instances_raw = data.get("item_instances", {})
    if not isinstance(item_instances_raw, dict) or set(item_instances_raw) != set(initial_item_instances):
        raise ValueError("save has invalid stable item instances")
    item_instances: dict[str, ItemInstance] = {}
    for instance_id, initial in initial_item_instances.items():
        raw_item = item_instances_raw[instance_id]
        if not isinstance(raw_item, dict):
            raise ValueError("save has invalid stable item instance")
        definition_id = _required_str(raw_item, "definition_id")
        quantity = _required_int(raw_item, "quantity")
        charges = raw_item.get("charges")
        if charges is not None and type(charges) is not int:
            raise ValueError("save has invalid item charges")
        hp = raw_item.get("hp")
        if hp is not None and type(hp) is not int:
            raise ValueError("save has invalid item HP")
        rune_ids = _required_str_list(raw_item, "rune_ids")
        invested = _required_bool(raw_item, "invested")
        try:
            instance = ItemInstance(
                instance_id, definition_id, quantity, charges, hp, tuple(rune_ids), invested
            )
        except ValueError as error:
            raise ValueError("save has invalid stable item instance") from error
        if (
            instance.definition_id != initial.definition_id
            or instance.quantity != initial.quantity
            or instance.charges != initial.charges
            or instance.rune_ids != initial.rune_ids
            or instance.invested != initial.invested
        ):
            raise ValueError("save changed stable item definition or attachments")
        if instance.definition_id == STEEL_SHIELD.definition_id and (
            instance.hp is None or instance.hp > STEEL_SHIELD.max_hp
        ):
            raise ValueError("save has invalid steel shield HP")
        item_instances[instance_id] = instance

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
        initiative_skill = initiative_skills_raw[actor_id]
        if initiative_skill == "perception":
            initiative_modifier = definition.perception
        else:
            initiative_modifier = next(
                (
                    modifier for name, _rank, modifier in definition.skills
                    if name == initiative_skill
                ),
                None,
            )
            if initiative_modifier is None:
                raise ValueError(f"saved actor {actor_id!r} has an unsupported initiative statistic")
        if not initiative_modifier + 1 <= initiative <= initiative_modifier + 20:
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
        spontaneous_raw = raw.get("spontaneous_slots", [])
        if not isinstance(spontaneous_raw, list):
            raise ValueError(f"saved actor {actor_id!r} has invalid spontaneous slots")
        spontaneous_slots: list[SpontaneousSlotState] = []
        for row in spontaneous_raw:
            if (
                not isinstance(row, list) or len(row) != 5
                or not isinstance(row[0], str) or not isinstance(row[1], str)
                or type(row[2]) is not int or type(row[3]) is not int
                or type(row[4]) is not int
                or row[2] < 1 or row[3] < 1 or not 0 <= row[4] <= row[3]
            ):
                raise ValueError(f"saved actor {actor_id!r} has invalid spontaneous slot")
            spontaneous_slots.append(SpontaneousSlotState(*row))
        focus_points = _required_int(raw, "focus_points")
        focus_capacity = _required_int(raw, "focus_capacity")
        if focus_capacity < 0 or not 0 <= focus_points <= focus_capacity:
            raise ValueError(f"saved actor {actor_id!r} has invalid focus pool")
        if (
            focus_capacity != definition.focus_capacity
            or (focus_capacity == 0 and definition.focus_spells)
            or (focus_capacity > 0 and not definition.focus_spells)
        ):
            raise ValueError(f"saved actor {actor_id!r} has focus capacity outside its reviewed definition")
        flourish_used_round = _required_int(raw, "flourish_used_round")
        must_leave_occupied = _required_bool(raw, "must_leave_occupied")
        temporary_hp = _required_int(raw, "temporary_hp")
        temporary_hp_source_id = raw.get("temporary_hp_source_id")
        temporary_hp_expires_at_seconds = raw.get("temporary_hp_expires_at_seconds")
        hunted_target_id = raw.get("hunted_prey")
        precision_used_round = _required_int(raw, "precision_used_round")
        panache = raw.get("panache", False)
        panache_expires_at_end = raw.get("panache_expires_at_end")
        finisher_used_this_turn = raw.get("finisher_used_this_turn", False)
        escape_lockout_until_start = _required_int(raw, "escape_lockout_until_start")
        barbarian_state = _barbarian_state_from_data(raw.get("barbarian_state"))
        investigator_stratagem = stratagem_from_data(raw.get("investigator_stratagem"))
        knowledge_attempts_raw = raw.get("investigator_knowledge_attempts", {})
        knowledge_exhausted_raw = raw.get("investigator_knowledge_exhausted", [])
        examinations_completed_raw = raw.get("investigator_examinations_completed", [])
        if (
            not isinstance(knowledge_attempts_raw, dict)
            or any(
                not isinstance(subject, str)
                or not subject
                or type(attempts) is not int
                or attempts < 0
                for subject, attempts in knowledge_attempts_raw.items()
            )
            or not isinstance(knowledge_exhausted_raw, list)
            or any(not isinstance(subject, str) or not subject for subject in knowledge_exhausted_raw)
            or len(set(knowledge_exhausted_raw)) != len(knowledge_exhausted_raw)
            or not set(knowledge_exhausted_raw).issubset(set(knowledge_attempts_raw))
            or any(knowledge_attempts_raw[subject] < 1 for subject in knowledge_exhausted_raw)
                or not isinstance(examinations_completed_raw, list)
                or any(not isinstance(key, str) or not key for key in examinations_completed_raw)
                or len(set(examinations_completed_raw)) != len(examinations_completed_raw)
                or not set(examinations_completed_raw).issubset(set(knowledge_attempts_raw))
                or any(knowledge_attempts_raw[key] < 1 for key in examinations_completed_raw)
            ):
            raise ValueError(f"saved actor {actor_id!r} has invalid Investigator knowledge state")
        if temporary_hp_source_id is not None and (
            not isinstance(temporary_hp_source_id, str) or not temporary_hp_source_id
        ):
            raise ValueError(f"saved actor {actor_id!r} has invalid temporary HP source")
        if temporary_hp_expires_at_seconds is not None and (
            type(temporary_hp_expires_at_seconds) is not int or temporary_hp_expires_at_seconds < 0
        ):
            raise ValueError(f"saved actor {actor_id!r} has invalid temporary HP expiry")
        if (
            temporary_hp < 0
            or (temporary_hp == 0 and temporary_hp_source_id is not None)
            or (temporary_hp == 0 and temporary_hp_expires_at_seconds is not None)
            or (temporary_hp > 0 and temporary_hp_source_id is None)
        ):
            raise ValueError(f"saved actor {actor_id!r} has invalid temporary HP state")
        if hunted_target_id is not None and (
            not isinstance(hunted_target_id, str) or not hunted_target_id
        ):
            raise ValueError(f"saved actor {actor_id!r} has invalid hunted prey")
        if precision_used_round < 0:
            raise ValueError(f"saved actor {actor_id!r} has invalid precision round")
        if type(panache) is not bool:
            raise ValueError(f"saved actor {actor_id!r} has invalid Panache state")
        if type(finisher_used_this_turn) is not bool:
            raise ValueError(f"saved actor {actor_id!r} has invalid Finisher state")
        if panache_expires_at_end is not None and (
            type(panache_expires_at_end) is not int or panache_expires_at_end < 0
        ):
            raise ValueError(f"saved actor {actor_id!r} has invalid Panache expiry")
        if not panache and panache_expires_at_end is not None:
            raise ValueError(f"saved actor {actor_id!r} has an expiry without Panache")
        if health_mode is not HealthMode(definition.health_mode):
            raise ValueError(f"saved actor {actor_id!r} has an incompatible health mode")
        if not 0 <= hero_points <= 3 or not 0 <= dying <= 3 or wounded < 0:
            raise ValueError(f"saved actor {actor_id!r} has invalid health resources")
        attack_items = {attack.item_id for attack in definition.attacks if attack.item_id is not None}
        allowed_items = (
            set(definition.held_items) | set(definition.worn_items) | set(definition.stowed_items)
            | set(item_instances)
        )
        all_inventory = held_items + worn_items + stowed_items
        def runtime_slot(local_item_id: str) -> str:
            stable_id = runtime_item_instance_id(actor_id, local_item_id)
            return stable_id if stable_id in item_instances else local_item_id

        required_worn = {
            runtime_slot(item_id)
            for item_id in definition.worn_items
            if item_id not in attack_items
        }
        if (
            any(item not in allowed_items for item in all_inventory)
            or len(all_inventory) != len(set(all_inventory))
            or any(item not in attack_items and item not in item_instances for item in held_items + stowed_items)
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
        expected_spontaneous = definition.spontaneous_slots
        if len(spontaneous_slots) != len(expected_spontaneous):
            raise ValueError(f"saved actor {actor_id!r} has invalid spontaneous slots")
        for saved_slot, definition_slot in zip(spontaneous_slots, expected_spontaneous):
            if (
                (saved_slot.slot_id, saved_slot.source, saved_slot.rank, saved_slot.capacity)
                != (definition_slot.slot_id, definition_slot.source, definition_slot.rank, definition_slot.capacity)
            ):
                raise ValueError(f"saved actor {actor_id!r} has invalid spontaneous slot facts")
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
            not (
                {"reactive_strike", "shield_block"} & set(definition.abilities)
                or "Nimble Dodge" in definition.feats
            )
            or unconscious or dead
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
            spontaneous_slots=spontaneous_slots,
            focus_points=focus_points,
            focus_capacity=focus_capacity,
            flourish_used_round=flourish_used_round,
            must_leave_occupied=must_leave_occupied,
            temporary_hp=temporary_hp,
            temporary_hp_source_id=temporary_hp_source_id,
            temporary_hp_expires_at_seconds=temporary_hp_expires_at_seconds,
            hunted_prey=HuntedPreyState(hunted_target_id) if hunted_target_id is not None else None,
            precision_used_round=precision_used_round,
            panache=panache,
            panache_expires_at_end=panache_expires_at_end,
            finisher_used_this_turn=finisher_used_this_turn,
            barbarian_state=barbarian_state,
            escape_lockout_until_start=escape_lockout_until_start,
            investigator_stratagem=investigator_stratagem,
            investigator_knowledge_attempts=dict(knowledge_attempts_raw),
            investigator_knowledge_exhausted=set(knowledge_exhausted_raw),
            investigator_examinations_completed=set(examinations_completed_raw),
        )
        if barbarian_state is not None and definition.class_name != "Barbarian":
            raise ValueError(f"saved actor {actor_id!r} has Barbarian state on another class")
        if (definition.class_name == "Barbarian") != (barbarian_state is not None):
            raise ValueError(f"saved actor {actor_id!r} has missing or unexpected Barbarian state")
        if barbarian_state is not None:
            from .barbarian_content import BARBARIAN_INITIAL_STATES

            canonical = BARBARIAN_INITIAL_STATES.get(definition_id)
            if canonical is None or (
                barbarian_state.instinct_id,
                barbarian_state.animal_choice,
                barbarian_state.dragon_choice,
                barbarian_state.giant_weapon_id,
                barbarian_state.class_feat_id,
                barbarian_state.bonus_feat_id,
            ) != (
                canonical.instinct_id,
                canonical.animal_choice,
                canonical.dragon_choice,
                canonical.giant_weapon_id,
                canonical.class_feat_id,
                canonical.bonus_feat_id,
            ):
                raise ValueError(f"saved actor {actor_id!r} has Barbarian choices outside its admitted build")
            try:
                validate_barbarian_state(barbarian_state, now_seconds=world_time_seconds)
            except ValueError as error:
                raise ValueError(f"saved actor {actor_id!r} has invalid Barbarian state") from error
            if barbarian_state.rage is not None and barbarian_state.rage.expires_at_seconds <= world_time_seconds:
                raise ValueError(f"saved actor {actor_id!r} retains expired Rage")
        if investigator_stratagem is not None and definition.class_name != "Investigator":
            raise ValueError(f"saved actor {actor_id!r} has Investigator state on another class")
        if definition.class_name == "Investigator" and investigator_stratagem is not None:
            try:
                validate_stratagem_state(investigator_stratagem)
            except ValueError as error:
                raise ValueError(f"saved actor {actor_id!r} has invalid Investigator state") from error
        if temporary_hp_expires_at_seconds is not None and temporary_hp_expires_at_seconds <= world_time_seconds:
            raise ValueError(f"saved actor {actor_id!r} retains expired temporary HP")
        if (
            barbarian_state is not None
            and barbarian_state.rage is not None
            and barbarian_state.rage.temporary_hp_source_id is not None
            and temporary_hp_source_id == barbarian_state.rage.temporary_hp_source_id
        ):
            if temporary_hp > barbarian_state.rage.temporary_hp_gained:
                raise ValueError(
                    f"saved actor {actor_id!r} has an impossible Rage temporary HP amount"
                )
            if temporary_hp_expires_at_seconds != barbarian_state.rage.expires_at_seconds:
                raise ValueError(f"saved actor {actor_id!r} has mismatched Rage temporary HP expiry")
        if panache and definition.class_name != "Swashbuckler":
            raise ValueError(f"saved actor {actor_id!r} has Panache on another class")
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
        for actor_id in initiative_reordered
    ):
        # A recovered PC keeps the initiative position established when the
        # knockout moved it ahead of the current turn.  The marker therefore
        # remains valid after healing; it is cleared with the next encounter
        # state rather than rewriting the active turn order on save/load.
        raise ValueError("only a PC can have a saved initiative anchor move")
    preparation_day = _required_int(data, "preparation_day")
    if preparation_day < 1:
        raise ValueError("save has invalid preparation day")
    rested_actor_ids = _required_str_list(data, "rested_actor_ids")
    if (
        not set(rested_actor_ids).issubset(expected_ids)
        or len(set(rested_actor_ids)) != len(rested_actor_ids)
        or any(creatures[actor_id].health_mode is not HealthMode.PC for actor_id in rested_actor_ids)
    ):
        raise ValueError("save has invalid rest eligibility")
    last_prepared_raw = data.get("last_prepared_day")
    pc_ids = {
        actor_id for actor_id, creature in creatures.items()
        if creature.health_mode is HealthMode.PC
    }
    if (
        not isinstance(last_prepared_raw, dict)
        or set(last_prepared_raw) != pc_ids
        or any(type(day) is not int or day < 1 or day > preparation_day for day in last_prepared_raw.values())
    ):
        raise ValueError("save has invalid last prepared day facts")
    justice_aura_active = _required_str_list(data, "justice_aura_active") if "justice_aura_active" in data else []
    desperate_prayer_used = _required_str_list(data, "desperate_prayer_used") if "desperate_prayer_used" in data else []
    desperate_prayer_points = _required_str_list(data, "desperate_prayer_points") if "desperate_prayer_points" in data else []
    for field_name, values in (
        ("Justice aura", justice_aura_active),
        ("Desperate Prayer use", desperate_prayer_used),
        ("Desperate Prayer points", desperate_prayer_points),
    ):
        if not set(values).issubset(expected_ids) or len(set(values)) != len(values):
            raise ValueError(f"save has invalid {field_name} state")
    if any(
        "justice_champion" not in get_definition(creatures[actor_id].definition_id).abilities
        or creatures[actor_id].unconscious
        or creatures[actor_id].dead
        for actor_id in justice_aura_active
    ):
        raise ValueError("save has an active Justice aura for an ineligible actor")
    if not set(desperate_prayer_points).issubset(set(desperate_prayer_used)):
        raise ValueError("save has a Desperate Prayer point without its daily use")
    active_index = _required_int(data, "active_index")
    if active_index < 0 or (initiative_order and active_index >= len(initiative_order)):
        raise ValueError("save has invalid active turn")
    round_number = _required_int(data, "round_number")
    if round_number < 1:
        raise ValueError("save has invalid round number")
    expected_combat_time = encounter_start_seconds + (round_number - 1) * 6
    if world_time_seconds < expected_combat_time:
        raise ValueError("save has an encounter clock before its current round")
    if any(creature.flourish_used_round < 0 or creature.flourish_used_round > round_number for creature in creatures.values()):
        raise ValueError("save has invalid per-round flourish use")
    for creature in creatures.values():
        if creature.precision_used_round > round_number:
            raise ValueError(f"saved actor {creature.actor_id!r} has invalid precision round")
        if creature.hunted_prey is not None:
            if (
                creature.hunted_prey.target_actor_id not in expected_ids
                or creature.hunted_prey.target_actor_id == creature.actor_id
                or get_definition(creature.definition_id).class_name != "Ranger"
            ):
                raise ValueError(f"saved actor {creature.actor_id!r} has invalid Hunted Prey state")
        elif creature.precision_used_round:
            raise ValueError(f"saved actor {creature.actor_id!r} used prey precision without Hunted Prey")
        if creature.precision_used_round and get_definition(creature.definition_id).class_name != "Ranger":
            raise ValueError(f"saved actor {creature.actor_id!r} has unsupported prey precision state")
    if in_progress and world_time_seconds != expected_combat_time:
        raise ValueError("save has invalid encounter world clock")
    if in_progress and winner_team is not None:
        raise ValueError("an unfinished encounter cannot have a winner")
    active_teams = {creature.team for creature in creatures.values() if is_combat_capable(creature)}
    pending_choice = _pending_from_data(data.get("pending_choice"))
    next_choice_id = _required_int(data, "next_choice_id")
    quick_tempered_decided = _required_str_list(data, "quick_tempered_decided")
    if not set(quick_tempered_decided).issubset(expected_ids) or len(set(quick_tempered_decided)) != len(quick_tempered_decided):
        raise ValueError("save has invalid Quick-Tempered decisions")
    if next_choice_id < 1 or (pending_choice is not None and pending_choice.choice_id >= next_choice_id):
        raise ValueError("save has invalid choice sequence")
    if pending_choice is not None and not in_progress and pending_choice.procedure_id not in {
        "investigator:forensic_examination:medicine_hero_point",
        "investigator:forensic_examination:follow_up",
        "investigator:forensic_examination:follow_up:hero_point",
    }:
        raise ValueError("finished encounters cannot retain choices")
    if initiative_finalized and len(initiative_order) != len(expected_ids):
        raise ValueError("finalized initiative must include every actor")
    if not initiative_finalized:
        initialization_family_choice = pending_choice is not None and (
            pending_choice.kind == "family_action"
            and pending_choice.family_id == "martial"
            and pending_choice.procedure_id in {
                "barbarian:quick_tempered", "barbarian:rage_mode", "barbarian:temporary_hp",
            }
        )
        if pending_choice is None or not (
            pending_choice.kind in ("initiative_hero_reroll", "initiative_tie")
            or initialization_family_choice
        ) or active_index != 0:
            raise ValueError("unfinalized initiative requires a pending initiative choice")
        if pending_choice.kind in {"initiative_hero_reroll", "family_action"} and initiative_order:
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
        max_diagonals_per_move = max(
            1,
            (effective_speed_ft(active_creature, get_definition(active_creature.definition_id)) + 4) // 5,
        )
        if active_creature.diagonals_this_turn > movement_actions * max_diagonals_per_move:
            raise ValueError("saved diagonal count exceeds possible movement this turn")
    elif in_progress and not initiative_finalized:
        initialization_family_choice = pending_choice is not None and (
            pending_choice.kind == "family_action"
            and pending_choice.family_id == "martial"
            and pending_choice.procedure_id in {
                "barbarian:quick_tempered", "barbarian:rage_mode", "barbarian:temporary_hp",
            }
        )
        if pending_choice is None or not (
            pending_choice.kind in ("initiative_hero_reroll", "initiative_tie")
            or initialization_family_choice
        ):
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
        if pending_choice.saved_check is not None:
            if (
                pending_choice.saved_check.check_owner_actor_id not in expected_ids
                or pending_choice.actor_id != pending_choice.saved_check.check_owner_actor_id
                or (
                    pending_choice.saved_check.parent_continuation is not None
                    and pending_choice.saved_check.parent_continuation.actor_id not in expected_ids
                )
            ):
                raise ValueError("pending choice has a saved check for another actor")
        if pending_choice.paired_strike is not None:
            paired = pending_choice.paired_strike
            referenced = {paired.owner_actor_id, *(item.target_id for item in paired.selections), *(item.target_id for item in paired.outcomes)}
            if not referenced.issubset(expected_ids):
                raise ValueError("pending choice has invalid paired Strike actors")
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
    instance_locations: dict[str, int] = {instance_id: 0 for instance_id in item_instances}
    for creature in creatures.values():
        for instance_id in creature.held_items + creature.worn_items + creature.stowed_items:
            if instance_id in instance_locations:
                instance_locations[instance_id] += 1
    for items in ground_items.values():
        for instance_id in items:
            if instance_id in instance_locations:
                instance_locations[instance_id] += 1
    if any(count != 1 for count in instance_locations.values()):
        raise ValueError("save loses or duplicates a stable item instance")

    starts_raw = data.get("actor_start_counts")
    if (
        not isinstance(starts_raw, dict)
        or set(starts_raw) != expected_ids
        or any(type(value) is not int or value < 0 for value in starts_raw.values())
    ):
        raise ValueError("save has invalid actor start counters")
    ends_raw = data.get("actor_end_counts")
    if (
        not isinstance(ends_raw, dict)
        or set(ends_raw) != expected_ids
        or any(type(value) is not int or value < 0 for value in ends_raw.values())
    ):
        raise ValueError("save has invalid actor end counters")
    weakness_raw = data.get("investigator_weakness_bonuses", [])
    if not isinstance(weakness_raw, list):
        raise ValueError("save has invalid Investigator Known Weaknesses bonuses")
    weakness_bonuses: list[InvestigatorWeaknessBonus] = []
    weakness_keys: set[tuple[str, str, str]] = set()
    for row in weakness_raw:
        if (
            not isinstance(row, list)
            or len(row) != 4
            or any(not isinstance(value, str) or not value for value in row[:3])
            or type(row[3]) is not int
            or row[3] < 1
            or row[0] not in expected_ids
            or row[1] not in expected_ids
            or row[2] not in expected_ids
            or row[3] <= starts_raw[row[0]]
            or (row[0], row[1], row[2]) in weakness_keys
        ):
            raise ValueError("save has invalid Investigator Known Weaknesses bonus")
        source = creatures[row[0]]
        recipient = creatures[row[2]]
        target = creatures[row[1]]
        if (
            source.health_mode is not HealthMode.PC
            or get_definition(source.definition_id).class_name != "Investigator"
            or recipient.team != source.team
            or (recipient.actor_id != source.actor_id and (
                recipient.defeated or recipient.unconscious
            ))
            or target.actor_id == source.actor_id
            or target.team == source.team
            or row[3] != starts_raw[row[0]] + 1
        ):
            raise ValueError("save has an unavailable Investigator Known Weaknesses bonus")
        weakness_keys.add((row[0], row[1], row[2]))
        weakness_bonuses.append(InvestigatorWeaknessBonus(*row))
    for actor_id, creature in creatures.items():
        if (
            creature.panache_expires_at_end is not None
            and (
                creature.panache_expires_at_end <= ends_raw[actor_id]
                or creature.panache_expires_at_end > ends_raw[actor_id] + 2
            )
        ):
            raise ValueError(f"saved actor {actor_id!r} has an invalid temporary Panache expiry")
    if any(
        creature.escape_lockout_until_start < 0
        or creature.escape_lockout_until_start > starts_raw[actor_id] + 1
        or (creature.escape_lockout_until_start not in {0, starts_raw[actor_id] + 1})
        for actor_id, creature in creatures.items()
    ):
        raise ValueError("save has invalid Escape retry lockout")
    for actor_id, creature in creatures.items():
        stratagem = creature.investigator_stratagem
        if stratagem is None:
            continue
        if stratagem.mode != ATTACK_STRATAGEM:
            raise ValueError(f"saved actor {actor_id!r} has an unsupported Investigator stratagem mode")
        if (
            stratagem.target_id not in expected_ids
            or stratagem.target_id == actor_id
        ):
            raise ValueError(f"saved actor {actor_id!r} has an invalid Investigator stratagem target")
    feint_effects_raw = data.get("feint_off_guard_effects")
    if not isinstance(feint_effects_raw, list):
        raise ValueError("save has invalid Feint off-guard effects")
    from .skill_actions import FeintAttackScope, FeintOffGuardEffect

    feint_effects: list[FeintOffGuardEffect] = []
    feint_effect_ids: set[str] = set()
    for row in feint_effects_raw:
        if (
            not isinstance(row, list) or len(row) != 7
            or any(not isinstance(value, str) or not value for value in row[:3])
            or (row[3] is not None and (not isinstance(row[3], str) or not row[3]))
            or not isinstance(row[4], str)
            or not isinstance(row[5], list) or len(row[5]) != 3
            or not isinstance(row[5][0], str) or not row[5][0]
            or row[5][1] not in {"start", "end"}
            or type(row[5][2]) is not int or row[5][2] < 1
            or type(row[6]) is not bool
            or row[0] in feint_effect_ids
            or row[1] not in expected_ids or row[2] not in expected_ids
            or row[5][0] not in expected_ids
            or (row[3] is not None and row[3] not in expected_ids)
        ):
            raise ValueError("save has invalid Feint off-guard effect")
        try:
            scope = FeintAttackScope(row[4])
            expiration = EffectExpiration(row[5][0], row[5][1], row[5][2])
            effect = FeintOffGuardEffect(
                row[0], row[1], row[2], row[3], scope, expiration, row[6]
            )
        except (TypeError, ValueError) as error:
            raise ValueError("save has invalid Feint off-guard effect") from error
        if expiration.occurrence <= ends_raw[expiration.anchor_actor_id]:
            raise ValueError("save retains an expired Feint off-guard effect")
        feint_effect_ids.add(effect.effect_id)
        feint_effects.append(effect)
    effects_raw = data.get("active_effects")
    if not isinstance(effects_raw, list):
        raise ValueError("save has invalid active spell effects")
    effects: list[ActiveSpellEffect] = []
    active_effect_ids: set[str] = set()
    blood_magic_sources: set[str] = set()
    halo_sources: set[str] = set()
    sure_strike_sources: set[str] = set()
    soothe_pairs: set[tuple[str, str]] = set()
    fleeing_pairs: set[tuple[str, str]] = set()
    for row in effects_raw:
        if (
            not isinstance(row, list) or len(row) != 7
            or any(not isinstance(value, str) or not value for value in row[:4])
            or type(row[4]) is not int or type(row[5]) is not int
            or row[4] < 1 or row[5] < 1
            or row[1] not in {"guidance", "enfeebled", "blood_magic", "angelic_halo", "fleeing", "sure_strike", "soothe", "lay_on_hands_ac"}
            or row[2] not in expected_ids or row[3] not in expected_ids
            or row[0] in active_effect_ids
            or row[5] <= starts_raw[row[2]]
            or (row[6] is not None and type(row[6]) is not int)
            or (
                row[1] not in {"guidance", "enfeebled", "blood_magic", "angelic_halo", "fleeing", "sure_strike", "soothe", "lay_on_hands_ac"}
                and row[6] is not None
            )
            or (
                row[1] in {"guidance", "enfeebled", "blood_magic"}
                and (
                    type(row[6]) is not int
                    or not _valid_active_duration_deadline(
                        row[1], row[5], starts_raw[row[2]],
                        round_number, world_time_seconds, row[6],
                        encounter_start_seconds=encounter_start_seconds,
                        in_progress=in_progress,
                    )
                )
            )
            or (
                row[1] == "guidance"
                and (
                    row[4] != 1
                    or row[5] != starts_raw[row[2]] + 1
                    or not any(
                        spell.spell_id == "guidance"
                        and spell.rank == 1
                        and spell.cantrip
                        for spell in (
                            *get_definition(creatures[row[2]].definition_id).prepared_spells,
                            *get_definition(creatures[row[2]].definition_id).spontaneous_spells,
                        )
                    )
                )
            )
            or (
                row[1] == "blood_magic"
                and (
                    row[4] != 1
                    or row[5] != starts_raw[row[2]] + 1
                    or "blood_magic" not in get_definition(
                        creatures[row[2]].definition_id
                    ).abilities
                    or row[2] in blood_magic_sources
                )
            )
            or (
                row[1] == "angelic_halo"
                and (
                    row[4] != 2
                    or row[3] != row[2]
                    or row[5] > starts_raw[row[2]] + 10
                    or not _valid_active_duration_deadline(
                        "angelic_halo", row[5], starts_raw[row[2]],
                        round_number, world_time_seconds, row[6],
                        encounter_start_seconds=encounter_start_seconds,
                        in_progress=in_progress,
                    )
                    or "angelic_halo" not in get_definition(
                        creatures[row[2]].definition_id
                    ).abilities
                    or not any(
                        spell.spell_id == "angelic_halo"
                        and spell.rank == 1
                        and not spell.cantrip
                        for spell in get_definition(
                            creatures[row[2]].definition_id
                        ).focus_spells
                    )
                    or get_definition(
                        creatures[row[2]].definition_id
                    ).focus_capacity < 1
                    or row[2] in halo_sources
                )
            )
            or (
                row[1] == "fleeing"
                and (
                    row[4] != 1
                    or row[5] != starts_raw[row[2]] + 1
                    or not _valid_active_duration_deadline(
                        "fleeing", row[5], starts_raw[row[2]],
                        round_number, world_time_seconds, row[6],
                        encounter_start_seconds=encounter_start_seconds,
                        in_progress=in_progress,
                    )
                    or row[2] == row[3]
                    or not any(
                        spell.spell_id == "fear"
                        and spell.rank == 1
                        and not spell.cantrip
                        for spell in get_definition(
                            creatures[row[2]].definition_id
                        ).spontaneous_spells
                    )
                    or (row[2], row[3]) in fleeing_pairs
                )
            )
            or (
                row[1] == "sure_strike"
                and (
                    row[4] != 1
                    or row[3] != row[2]
                    or row[5] != starts_raw[row[2]] + 1
                    or not _valid_active_duration_deadline(
                        "sure_strike", row[5], starts_raw[row[2]],
                        round_number, world_time_seconds, row[6],
                        encounter_start_seconds=encounter_start_seconds,
                        in_progress=in_progress,
                    )
                    or not any(
                        spell.spell_id == "sure_strike"
                        and spell.rank == 1
                        and not spell.cantrip
                        for spell in get_definition(
                            creatures[row[2]].definition_id
                        ).prepared_spells
                    )
                    or not any(
                        slot.spell_id == "sure_strike"
                        and slot.rank == 1
                        and not slot.cantrip
                        and slot.spent
                        for slot in creatures[row[2]].prepared_slots
                    )
                    or row[2] in sure_strike_sources
                )
            )
            or (
                row[1] == "soothe"
                and (
                    row[4] != 2
                    or row[5] != starts_raw[row[2]] + 10
                    or not _valid_active_duration_deadline(
                        "soothe", row[5], starts_raw[row[2]],
                        round_number, world_time_seconds, row[6],
                        encounter_start_seconds=encounter_start_seconds,
                        in_progress=in_progress,
                    )
                    or not any(
                        spell.spell_id == "soothe"
                        and spell.rank == 1
                        and not spell.cantrip
                        for spell in (
                            *get_definition(creatures[row[2]].definition_id).prepared_spells,
                            *get_definition(creatures[row[2]].definition_id).spontaneous_spells,
                        )
                    )
                    or not (
                        any(
                            slot.spell_id == "soothe"
                            and slot.rank == 1
                            and not slot.cantrip
                            and slot.spent
                            for slot in creatures[row[2]].prepared_slots
                        )
                        or any(
                            spell.spell_id == "soothe"
                            and spell.rank == 1
                            and not spell.cantrip
                            for spell in get_definition(creatures[row[2]].definition_id).spontaneous_spells
                        )
                        and any(
                            slot.rank == 1
                            and slot.remaining < slot.capacity
                            for slot in creatures[row[2]].spontaneous_slots
                        )
                    )
                    or creatures[row[3]].dead
                    or (
                        creatures[row[3]].health_mode is HealthMode.ORDINARY
                        and creatures[row[3]].hp <= 0
                        and not creatures[row[3]].unconscious
                    )
                    or (row[2], row[3]) in soothe_pairs
                )
            )
                or (
                    row[1] == "lay_on_hands_ac"
                    and (
                        row[4] != 2
                        or row[2] == row[3]
                        or row[5] != starts_raw[row[2]] + 1
                        or "lay_on_hands" not in get_definition(
                            creatures[row[2]].definition_id
                        ).abilities
                    )
                )
        ):
            raise ValueError("save has invalid active spell effect")
        active_effect_ids.add(row[0])
        if row[1] == "blood_magic":
            blood_magic_sources.add(row[2])
        if row[1] == "angelic_halo":
            halo_sources.add(row[2])
        if row[1] == "sure_strike":
            sure_strike_sources.add(row[2])
        if row[1] == "soothe":
            soothe_pairs.add((row[2], row[3]))
        if row[1] == "fleeing":
            fleeing_pairs.add((row[2], row[3]))
        effects.append(ActiveSpellEffect(*row))
    item_effects_raw = data.get("active_item_effects", [])
    if not isinstance(item_effects_raw, list):
        raise ValueError("save has invalid active item spell effects")
    item_effects: list[ActiveItemSpellEffect] = []
    # Item effects share the encounter-wide effect identity namespace with
    # creature effects.  A forged cross-family duplicate must not silently
    # shadow an existing active effect on load.
    item_effect_ids: set[str] = set(active_effect_ids)
    item_effect_targets: set[str] = set()
    for row in item_effects_raw:
        if (
            not isinstance(row, list) or len(row) != 6
            or any(not isinstance(value, str) or not value for value in row[:4])
            or type(row[4]) is not int or row[4] < 1
            or type(row[5]) is not int or row[5] < 1
            or row[1] != "runic_weapon"
            or row[2] not in expected_ids
            or row[3] not in item_instances
            or row[0] in item_effect_ids
            or row[3] in item_effect_targets
            or row[4] <= starts_raw[row[2]]
            or row[4] > starts_raw[row[2]] + 10
            or not _valid_active_duration_deadline(
                "runic_weapon", row[4], starts_raw[row[2]],
                round_number, world_time_seconds, row[5],
                encounter_start_seconds=encounter_start_seconds,
                in_progress=in_progress,
            )
            or ITEM_CATEGORIES.get(item_instances[row[3]].definition_id) != "weapon"
            or item_instances[row[3]].definition_id not in {"longsword", "shortsword"}
            or not any(
                spell.spell_id == "runic_weapon"
                and spell.rank == 1
                and not spell.cantrip
                for spell in get_definition(creatures[row[2]].definition_id).spontaneous_spells
            )
        ):
            raise ValueError("save has invalid active Runic Weapon item effect")
        try:
            weapon_rune_profile_for_item(item_instances[row[3]])
            effect = ActiveItemSpellEffect(*row)
        except (TypeError, ValueError) as error:
            raise ValueError("save has invalid active Runic Weapon item effect") from error
        item_effect_ids.add(row[0])
        item_effect_targets.add(row[3])
        item_effects.append(effect)
    condition_effects_raw = data.get("condition_effects")
    if not isinstance(condition_effects_raw, list):
        raise ValueError("save has invalid condition effects")
    condition_effects: list[ActiveConditionEffect] = []
    effect_ids: set[str] = set()
    for row in condition_effects_raw:
        if (
            not isinstance(row, list) or len(row) != 7
            or any(not isinstance(value, str) or not value for value in row[:4])
            or type(row[4]) is not int or row[4] < 1
            or not isinstance(row[5], list) or len(row[5]) != 3
            or not isinstance(row[5][0], str) or not row[5][0]
            or row[5][1] not in {"start", "end"}
            or type(row[5][2]) is not int or row[5][2] < 1
            or row[2] not in expected_ids or row[3] not in expected_ids
            or row[5][0] not in expected_ids
            or (row[6] is not None and (type(row[6]) is not int or row[6] < 0))
            or row[0] in effect_ids
        ):
            raise ValueError("save has invalid condition effect")
        expiration = EffectExpiration(row[5][0], row[5][1], row[5][2])
        effect = ActiveConditionEffect(row[0], row[1], row[2], row[3], row[4], expiration, row[6])
        try:
            effective_condition_value((ConditionValue(effect.kind, effect.value, effect.effect_id),), effect.kind)
        except (TypeError, ValueError) as error:
            raise ValueError("save has unsupported condition effect") from error
        completed_count = starts_raw[expiration.anchor_actor_id] if expiration.boundary == "start" else ends_raw[expiration.anchor_actor_id]
        if expiration.occurrence <= completed_count:
            raise ValueError("save retains an expired condition effect")
        effect_ids.add(effect.effect_id)
        condition_effects.append(effect)

    # Fear's Will Hero choice is the only saved spell-save reroll currently
    # admitted besides Void Warp.  Keep the source/rank ledger and target-owned
    # choice facts explicit here so a forged continuation cannot turn Fear into
    # a cantrip, another-rank cast, or Angelic Blood Magic path before the
    # encounter-level modifier validation runs.
    if pending_choice is not None and pending_choice.kind == "spell_save_hero_reroll":
        continuation = pending_choice.continuation
        if pending_choice.spell_id == "fear":
            caster = creatures.get(pending_choice.actor_id or "")
            target = creatures.get(pending_choice.target_id or "")
            if (
                continuation is None
                or caster is None
                or target is None
                or continuation.kind != "cast"
                or continuation.actor_id != caster.actor_id
                or continuation.target_id != target.actor_id
                or continuation.spell_target_id != target.actor_id
                or continuation.spell_id != "fear"
                or continuation.spell_actions != 2
                or continuation.spell_source_kind != "spontaneous"
                or continuation.slot_id is None
                or continuation.sorcerous_potency != 0
                or continuation.blood_magic_recipient_id is not None
                or target.health_mode is not HealthMode.PC
                or pending_choice.owner_actor_id != target.actor_id
                or pending_choice.actor_id != caster.actor_id
                or pending_choice.target_id != target.actor_id
                or pending_choice.check_owner_actor_id != target.actor_id
                or pending_choice.check_kind != "spell_save"
                or pending_choice.options != (
                    ChoiceOption("keep", "Keep result"),
                    ChoiceOption("spend_hero_point", "Spend 1 Hero Point and reroll"),
                )
                or not any(
                    slot.slot_id == continuation.slot_id
                    and slot.rank == 1
                    and slot.remaining < slot.capacity
                    for slot in caster.spontaneous_slots
                )
                or not any(
                    spell.spell_id == "fear"
                    and spell.rank == 1
                    and not spell.cantrip
                    for spell in get_definition(caster.definition_id).spontaneous_spells
                )
            ):
                raise ValueError("save has invalid Fear Will Hero choice provenance")

    # A Flee movement reaction can be paused only in the explicitly authored
    # closed room.  The continuation uses the ordinary movement shape; the
    # fleeing effect above remains its source/deadline authority.
    if pending_choice is not None and pending_choice.kind == "reaction":
        continuation = pending_choice.continuation
        fleeing_actor = (
            continuation is not None
            and continuation.kind == "movement"
            and next(
                (
                    item for item in effects
                    if item.kind == "fleeing"
                    and item.target_actor_id == continuation.actor_id
                ),
                None,
            )
            is not None
        )
        if continuation is not None and (continuation.movement_kind == "flee" or fleeing_actor):
            actor = creatures.get(continuation.actor_id)
            effect = next(
                (
                    item for item in effects
                    if item.kind == "fleeing"
                    and item.target_actor_id == continuation.actor_id
                ),
                None,
            )
            if (
                not setup.closed_boundary
                or actor is None
                or continuation.kind != "movement"
                or continuation.movement_kind != "flee"
                or continuation.reaction_trigger != "movement"
                or not continuation.path
                or not 0 <= continuation.next_step <= len(continuation.path)
                or any(not in_bounds(point, width, height) for point in continuation.path)
                or (
                    continuation.next_step == 0
                    and actor.position == continuation.path[-1]
                )
                or (
                    continuation.next_step > 0
                    and actor.position != continuation.path[continuation.next_step - 1]
                )
                or effect is None
            ):
                raise ValueError("save has invalid Flee movement reaction continuation")
    immunities_raw = data.get("condition_immunities")
    if not isinstance(immunities_raw, list):
        raise ValueError("save has invalid condition immunities")
    condition_immunities: list[ConditionImmunity] = []
    immunity_keys: set[tuple[str, str, str]] = set()
    for row in immunities_raw:
        if (
            not isinstance(row, list) or len(row) != 4
            or any(not isinstance(value, str) or not value for value in row[:3])
            or type(row[3]) is not int or row[3] < world_time_seconds
            or row[1] not in expected_ids or row[2] not in expected_ids
        ):
            raise ValueError("save has invalid condition immunity")
        key = (row[0], row[1], row[2])
        if key in immunity_keys:
            raise ValueError("save has duplicate condition immunity")
        immunity_keys.add(key)
        condition_immunities.append(ConditionImmunity(row[0], row[1], row[2], row[3]))
    immunity_raw = data.get("guidance_immunity_deadlines")
    if (
        not isinstance(immunity_raw, dict)
        or any(
            actor_id not in expected_ids
            or type(until) is not int
            or until < world_time_seconds
            for actor_id, until in immunity_raw.items()
        )
    ):
        raise ValueError("save has invalid Guidance immunity deadline")
    sure_strike_immunity_raw = data.get("sure_strike_immunity_deadlines", {})
    if (
        not isinstance(sure_strike_immunity_raw, dict)
        or any(
            not isinstance(actor_id, str)
            or actor_id not in expected_ids
            or type(until) is not int
            or until <= world_time_seconds
            for actor_id, until in sure_strike_immunity_raw.items()
        )
    ):
        raise ValueError("save has invalid Sure Strike immunity deadline")
    taking_cover_raw = _required_str_list(data, "taking_cover")
    if not set(taking_cover_raw).issubset(expected_ids) or len(set(taking_cover_raw)) != len(taking_cover_raw):
        raise ValueError("save has invalid Take Cover state")
    raised_shields_raw = data.get("raised_shields", {})
    if not isinstance(raised_shields_raw, dict) or not set(raised_shields_raw).issubset(expected_ids):
        raise ValueError("save has invalid raised shields")
    raised_shields: dict[str, RaisedShieldState] = {}
    for actor_id, row in raised_shields_raw.items():
        if (
            not isinstance(row, list) or len(row) != 2
            or not isinstance(row[0], str) or type(row[1]) is not int
        ):
            raise ValueError("save has invalid raised shield state")
        instance = item_instances.get(row[0])
        actor = creatures[actor_id]
        if (
            instance is None or instance.hp is None
            or instance.definition_id != STEEL_SHIELD.definition_id
            or row[0] not in actor.held_items
            or instance.hp <= STEEL_SHIELD.broken_threshold
            or row[1] != starts_raw[actor_id] + 1
        ):
            raise ValueError("save has a raised shield that is absent, broken, or expired")
        raised_shields[actor_id] = RaisedShieldState(row[0], row[1])

    light_orbs_raw = data.get("light_orbs")
    if not isinstance(light_orbs_raw, list):
        raise ValueError("save has invalid Light orbs")
    next_light_orb_id = _required_int(data, "next_light_orb_id")
    if next_light_orb_id < 1:
        raise ValueError("save has invalid Light orb sequence")
    light_orbs: list[LightOrb] = []
    light_orb_ids: set[str] = set()
    caster_orb_counts: dict[str, int] = {}
    for row in light_orbs_raw:
        if not isinstance(row, list) or len(row) != 7:
            raise ValueError("save has invalid Light orb")
        stable_id, caster_id, rank, color, point_raw, attached_id, owner_preparation = row
        if (
            not isinstance(stable_id, str) or not stable_id
            or not isinstance(caster_id, str) or caster_id not in expected_ids
            or type(rank) is not int or rank != 1
            or not isinstance(color, str) or not color.strip()
            or (point_raw is not None and (
                not isinstance(point_raw, list)
                or len(point_raw) != 2
                or any(type(value) is not int for value in point_raw)
            ))
            or (attached_id is not None and (
                not isinstance(attached_id, str) or attached_id not in expected_ids
            ))
            or type(owner_preparation) is not int or owner_preparation < 0
            or stable_id in light_orb_ids
            or (point_raw is None) == (attached_id is None)
        ):
            raise ValueError("save has invalid Light orb")
        point = Position(*point_raw) if point_raw is not None else None
        if point is not None and not in_bounds(point, width, height):
            raise ValueError("save has an out-of-bounds Light orb point")
        known_light = (
            any(
                spell.spell_id == "light" and spell.rank == 1 and spell.cantrip
                for spell in get_definition(creatures[caster_id].definition_id).spontaneous_spells
            )
            or any(
                spell.spell_id == "light" and spell.rank == 1 and spell.cantrip
                for spell in get_definition(creatures[caster_id].definition_id).prepared_spells
            )
        )
        if not known_light:
            raise ValueError("save has a Light orb for a caster without the admitted cantrip")
        caster_orb_counts[caster_id] = caster_orb_counts.get(caster_id, 0) + 1
        if caster_orb_counts[caster_id] > 4:
            raise ValueError("save has more than four active Light orbs for one caster")
        light_orb_ids.add(stable_id)
        light_orbs.append(
            LightOrb(
                stable_id,
                caster_id,
                rank,
                color,
                point,
                attached_id,
                owner_preparation,
            )
        )

    state = EncounterState(
        setup_id=setup.setup_id,
        map_width=width,
        map_height=height,
        creatures=creatures,
        initiative_order=initiative_order,
        active_index=active_index,
        initiative_skills=dict(initiative_skills_raw),
        initiative_contexts=dict(initiative_contexts_raw),
        round_number=round_number,
        in_progress=in_progress,
        winner_team=winner_team,
        initiative_finalized=initiative_finalized,
        pending_choice=pending_choice,
        next_choice_id=next_choice_id,
        initiative_hero_decided=set(initiative_hero_decided),
        quick_tempered_decided=set(quick_tempered_decided),
        ground_items=ground_items,
        item_instances=item_instances,
        raised_shields=raised_shields,
        initiative_tie_groups=tie_groups,
        initiative_tie_orders=tie_orders,
        initiative_tie_group_index=tie_group_index,
        initiative_reordered=set(initiative_reordered),
        actor_start_counts=dict(starts_raw),
        actor_end_counts=dict(ends_raw),
        feint_off_guard_effects=feint_effects,
        active_effects=effects,
        active_item_effects=item_effects,
        condition_effects=condition_effects,
        condition_immunities=condition_immunities,
        world_time_seconds=world_time_seconds,
        encounter_start_seconds=encounter_start_seconds,
        ambient_light=ambient_light,
        guidance_immunities={
            actor_id: round_number + 600 for actor_id in immunity_raw
        },
        guidance_immunity_deadlines=dict(immunity_raw),
        sure_strike_immunity_deadlines=dict(sure_strike_immunity_raw),
        taking_cover=set(taking_cover_raw),
        light_orbs=light_orbs,
        next_light_orb_id=next_light_orb_id,
        preparation_day=preparation_day,
        rested_actor_ids=set(rested_actor_ids),
        last_prepared_day=dict(last_prepared_raw),
        justice_aura_active=set(justice_aura_active),
        desperate_prayer_used=set(desperate_prayer_used),
        desperate_prayer_points=set(desperate_prayer_points),
        investigator_weakness_bonuses=weakness_bonuses,
    )
    # ``load_encounter`` is also a public persistence API.  Re-run the same
    # live-state validation used by ``Encounter.load`` for Fear's target-owned
    # Will/Hero pause, so direct state loads cannot bypass current DC/save
    # modifiers or the Hero Point/resource ledger.
    if (
        state.pending_choice is not None
        and (
            (
                state.pending_choice.kind == "spell_save_hero_reroll"
                and state.pending_choice.spell_id == "fear"
            )
            or (
                state.pending_choice.kind == "spell_willingness"
                and state.pending_choice.spell_id == "runic_weapon"
            )
            or (
                state.pending_choice.kind == "reaction"
                and state.pending_choice.continuation is not None
                and state.pending_choice.continuation.kind == "cast"
                and state.pending_choice.continuation.spell_id == "runic_weapon"
            )
            or state.pending_choice.kind == "concealment_hero_reroll"
        )
    ):
        from .encounter import Encounter

        Encounter(state, DiceSource())._validate_pending_context()
    return state


def _required_str(data: dict[str, Any], key: str) -> str:
    value = data.get(key)
    if not isinstance(value, str) or not value:
        raise ValueError(f"save has invalid {key}")
    return value


def _valid_active_duration_deadline(
    kind: str,
    source_start_deadline: int,
    source_starts: int,
    round_number: int,
    world_time_seconds: int,
    world_deadline: int | None,
    *,
    encounter_start_seconds: int = 0,
    in_progress: bool = True,
) -> bool:
    """Validate Halo/Flee duration across an initiative wrap.

    During combat the source-start boundary is authoritative.  A save may be
    taken after the six-second round transition but before the source's next
    turn starts, so its absolute deadline can equal the current world clock.
    Under the saved encounter-clock invariant, a source-start occurrence N
    has the matching absolute deadline ``(N - 1) * 6``.  The remaining
    source-start count must also fit the spell's printed duration.
    """
    if kind not in {
        "angelic_halo", "fleeing", "runic_weapon", "guidance", "enfeebled", "blood_magic", "sure_strike", "soothe",
    } or type(world_deadline) is not int:
        return False
    duration_rounds = 1 if kind in {"fleeing", "guidance", "enfeebled", "blood_magic", "sure_strike"} else 10
    starts_remaining = source_start_deadline - source_starts
    expected_deadline = encounter_start_seconds + (source_start_deadline - 1) * 6
    return bool(
        1 <= starts_remaining <= duration_rounds
        and world_deadline == expected_deadline
        and world_time_seconds >= encounter_start_seconds + (round_number - 1) * 6
        and (not in_progress or world_time_seconds == encounter_start_seconds + (round_number - 1) * 6)
    )


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


def _paired_strike_to_data(value: PairedStrikeContinuation | None) -> dict[str, Any] | None:
    if value is None:
        return None
    return {
        "activity_id": value.activity_id,
        "owner_actor_id": value.owner_actor_id,
        "paid_actions": value.paid_actions,
        "initial_attack_count": value.initial_attack_count,
        "selections": [
            [item.target_id, item.attack_id, item.damage_type, item.nonlethal]
            for item in value.selections
        ],
        "next_index": value.next_index,
        "outcomes": [
            [item.target_id, item.attack_id, _check_to_data(item.check), _damage_to_data(item.damage),
             item.damage_type, item.nonlethal, item.hit]
            for item in value.outcomes
        ],
        "stage": value.stage,
    }


def _paired_strike_from_data(data: Any) -> PairedStrikeContinuation | None:
    if data is None:
        return None
    if not isinstance(data, dict):
        raise ValueError("save has invalid paired Strike continuation")
    activity_id, owner = data.get("activity_id"), data.get("owner_actor_id")
    paid, initial, next_index, stage = (
        data.get("paid_actions"), data.get("initial_attack_count"), data.get("next_index"), data.get("stage")
    )
    selections_raw, outcomes_raw = data.get("selections"), data.get("outcomes")
    if (
        not isinstance(activity_id, str) or not activity_id
        or not isinstance(owner, str) or not owner
        or type(paid) is not int or paid < 0
        or type(initial) is not int or initial < 0
        or type(next_index) is not int or not 0 <= next_index <= 2
        or not isinstance(stage, str) or not stage
        or not isinstance(selections_raw, list) or len(selections_raw) > 2
        or not isinstance(outcomes_raw, list) or len(outcomes_raw) > 2
    ):
        raise ValueError("save has invalid paired Strike facts")
    selections: list[PairedStrikeSelection] = []
    for row in selections_raw:
        if (
            not isinstance(row, list) or len(row) != 4
            or not isinstance(row[0], str) or not row[0]
            or not isinstance(row[1], str) or not row[1]
            or (row[2] is not None and (not isinstance(row[2], str) or not row[2]))
            or (row[3] is not None and type(row[3]) is not bool)
        ):
            raise ValueError("save has invalid paired Strike selection")
        selections.append(PairedStrikeSelection(*row))
    outcomes: list[PairedStrikeOutcome] = []
    for row in outcomes_raw:
        if (
            not isinstance(row, list) or len(row) != 7
            or not isinstance(row[0], str) or not row[0]
            or not isinstance(row[1], str) or not row[1]
            or not isinstance(row[4], str) or not row[4]
            or type(row[5]) is not bool or type(row[6]) is not bool
        ):
            raise ValueError("save has invalid paired Strike outcome")
        check, damage = _check_from_data(row[2]), _damage_from_data(row[3])
        if check is None or (row[6] and damage is None) or (not row[6] and damage is not None):
            raise ValueError("save has inconsistent paired Strike outcome")
        outcomes.append(PairedStrikeOutcome(row[0], row[1], check, damage, row[4], row[5], row[6]))
    return PairedStrikeContinuation(
        activity_id, owner, paid, initial, tuple(selections), next_index, tuple(outcomes), stage
    )


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
        "item_id": pending.item_id,
        "attack_penalty": pending.attack_penalty,
        "attack_count": pending.attack_count,
        "check": _check_to_data(pending.check),
        "damage_result": _damage_to_data(pending.damage_result),
        "damage_result_is_mitigated": pending.damage_result_is_mitigated,
        "damage_resolution": _damage_resolution_to_data(pending.damage_resolution),
        "damage_text": pending.damage_text,
        "temporary_hp_absorbed": pending.temporary_hp_absorbed,
        "remaining_hp_damage": pending.remaining_hp_damage,
        "attack_critical": pending.attack_critical,
        "damage_type": pending.damage_type,
        "nonlethal": pending.nonlethal,
        "damage_bonus_dice": pending.damage_bonus_dice,
        "attack_actions_cost": pending.attack_actions_cost,
        "attack_count_cost": pending.attack_count_cost,
        "ranged_penalty": pending.ranged_penalty,
        "guidance_bonus": pending.guidance_bonus,
        "feint_off_guard_applied": pending.feint_off_guard_applied,
        "attack_target_off_guard": pending.attack_target_off_guard,
        "nimble_dodge_used": pending.nimble_dodge_used,
        "concealment_checked": pending.concealment_checked,
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
        "spell_target_item_id": pending.spell_target_item_id,
        "actions_cost": pending.actions_cost,
        "spell_actions": pending.spell_actions,
        "include_self": pending.include_self,
        "effect_id": pending.effect_id,
        "damage_adjustment": pending.damage_adjustment,
        "damage_context": pending.damage_context,
        "target_ids": list(pending.target_ids),
        "family_id": pending.family_id,
        "procedure_id": pending.procedure_id,
        "barbarian_choice": None if pending.barbarian_choice is None else {
            "procedure_id": pending.barbarian_choice.procedure_id,
            "actor_id": pending.barbarian_choice.actor_id,
            "command_kind": pending.barbarian_choice.command_kind,
            "mode_id": getattr(pending.barbarian_choice, "mode_id", None),
            "temporary_hp_choice": getattr(pending.barbarian_choice, "temporary_hp_choice", None),
        },
        "saved_check": _saved_check_to_data(pending.saved_check),
        "paired_strike": _paired_strike_to_data(pending.paired_strike),
        "family_command": _family_command_to_data(pending.family_command),
    }


def _family_command_to_data(command) -> dict[str, Any] | None:
    """Encode only the typed skill and Rage commands used by saved choices."""
    if command is None:
        return None
    from .barbarian import QuickTempered, Rage

    if type(command) in {Rage, QuickTempered}:
        return {
            "type": type(command).__name__,
            "mode_id": command.mode_id,
            "temporary_hp_choice": command.temporary_hp_choice,
        }
    from .skill_actions import Trip, Grapple, Escape, Demoralize, Feint

    if type(command) is Trip:
        return {
            "type": "Trip", "target_id": command.target_id,
            "maneuver_item_id": command.maneuver_item_id,
            "use_assurance": command.use_assurance,
        }
    if type(command) is Grapple:
        return {
            "type": "Grapple", "target_id": command.target_id,
            "maneuver_item_id": command.maneuver_item_id,
            "use_assurance": command.use_assurance,
        }
    if type(command) is Escape:
        return {
            "type": "Escape", "impediment_id": command.impediment_id,
            "check_method": command.check_method, "attack_id": command.attack_id,
            "use_assurance": command.use_assurance,
        }
    if type(command) is Demoralize:
        return {
            "type": "Demoralize", "target_id": command.target_id,
            "spoken_language": command.spoken_language,
            "use_intimidating_glare": command.use_intimidating_glare,
        }
    if type(command) is Feint:
        return {"type": "Feint", "target_id": command.target_id}
    from .investigator import BattleMedicine, ForensicExamination, RecallKnowledge

    if type(command) is BattleMedicine:
        return {
            "type": "BattleMedicine",
            "target_id": command.target_id,
            "dc": command.dc,
        }
    if type(command) is RecallKnowledge:
        return {
            "type": "RecallKnowledge",
            "subject_key": command.subject_key,
            "question": command.question,
            "skill": command.skill,
            "target_id": command.target_id,
            "circumstance_bonus": command.circumstance_bonus,
            "forensic_follow_up": command.forensic_follow_up,
        }
    if type(command) is ForensicExamination:
        return {
            "type": "ForensicExamination",
            "examination_key": command.examination_key,
        }
    from .swashbuckler import ConfidentFinisher

    if type(command) is ConfidentFinisher:
        return {
            "type": "ConfidentFinisher",
            "target_id": command.target_id,
            "attack_id": command.attack_id,
            "damage_type": command.damage_type,
            "nonlethal": command.nonlethal,
            "item_id": command.item_id,
        }
    raise ValueError("save cannot encode this family command in a pending skill choice")


def _family_command_from_data(data: Any):
    if data is None:
        return None
    if not isinstance(data, dict) or not isinstance(data.get("type"), str):
        raise ValueError("save has invalid pending family command")
    from .barbarian import QuickTempered, Rage
    from .skill_actions import Trip, Grapple, Escape, Demoralize, Feint
    from .investigator import ForensicExamination, RecallKnowledge
    from .swashbuckler import ConfidentFinisher

    kind = data["type"]
    if kind in {"Rage", "QuickTempered"}:
        if set(data) != {"type", "mode_id", "temporary_hp_choice"}:
            raise ValueError("save has invalid pending Rage command")
        mode_id = data["mode_id"]
        temporary_hp_choice = data["temporary_hp_choice"]
        if (
            (mode_id is not None and (not isinstance(mode_id, str) or not mode_id))
            or (
                temporary_hp_choice is not None
                and (not isinstance(temporary_hp_choice, str) or not temporary_hp_choice)
            )
        ):
            raise ValueError("save has invalid pending Rage command")
        cls = Rage if kind == "Rage" else QuickTempered
        return cls(mode_id=mode_id, temporary_hp_choice=temporary_hp_choice)
    if kind in {"Trip", "Grapple"}:
        if set(data) != {"type", "target_id", "maneuver_item_id", "use_assurance"}:
            raise ValueError("save has invalid pending maneuver command")
        target_id, item_id = data["target_id"], data["maneuver_item_id"]
        use_assurance = data["use_assurance"]
        if (
            not isinstance(target_id, str) or not target_id
            or (item_id is not None and (not isinstance(item_id, str) or not item_id))
            or type(use_assurance) is not bool
        ):
            raise ValueError("save has invalid pending maneuver command")
        cls = Trip if kind == "Trip" else Grapple
        return cls(target_id, item_id, use_assurance)
    if kind == "Escape":
        if set(data) != {"type", "impediment_id", "check_method", "attack_id", "use_assurance"}:
            raise ValueError("save has invalid pending Escape command")
        use_assurance = data["use_assurance"]
        if (
            any(not isinstance(data[key], str) or not data[key] for key in ("impediment_id", "check_method"))
            or (data["attack_id"] is not None and (not isinstance(data["attack_id"], str) or not data["attack_id"]))
            or type(use_assurance) is not bool
        ):
            raise ValueError("save has invalid pending Escape command")
        return Escape(data["impediment_id"], data["check_method"], data["attack_id"], use_assurance)
    if kind == "Demoralize":
        if set(data) != {"type", "target_id", "spoken_language", "use_intimidating_glare"}:
            raise ValueError("save has invalid pending Demoralize command")
        target_id, language, glare = data["target_id"], data["spoken_language"], data["use_intimidating_glare"]
        if (
            not isinstance(target_id, str) or not target_id
            or (language is not None and (not isinstance(language, str) or not language))
            or type(glare) is not bool
        ):
            raise ValueError("save has invalid pending Demoralize command")
        return Demoralize(target_id, language, glare)
    if kind == "Feint":
        if set(data) != {"type", "target_id"}:
            raise ValueError("save has invalid pending Feint command")
        target_id = data["target_id"]
        if not isinstance(target_id, str) or not target_id:
            raise ValueError("save has invalid pending Feint command")
        return Feint(target_id)
    if kind == "BattleMedicine":
        if set(data) != {"type", "target_id", "dc"}:
            raise ValueError("save has invalid pending Battle Medicine command")
        target_id, dc = data["target_id"], data["dc"]
        if not isinstance(target_id, str) or not target_id or type(dc) is not int:
            raise ValueError("save has invalid pending Battle Medicine command")
        from .investigator import BattleMedicine

        return BattleMedicine(target_id, dc)
    if kind == "RecallKnowledge":
        if set(data) != {
            "type", "subject_key", "question", "skill", "target_id",
            "circumstance_bonus", "forensic_follow_up",
        }:
            raise ValueError("save has invalid pending Recall Knowledge command")
        subject_key, question, skill, target_id = (
            data["subject_key"], data["question"], data["skill"], data["target_id"]
        )
        circumstance_bonus = data["circumstance_bonus"]
        forensic_follow_up = data["forensic_follow_up"]
        if (
            not isinstance(subject_key, str) or not subject_key
            or (question is not None and (not isinstance(question, str) or not question))
            or (skill is not None and (not isinstance(skill, str) or not skill))
            or (target_id is not None and (not isinstance(target_id, str) or not target_id))
            or type(circumstance_bonus) is not int or circumstance_bonus < 0
            or type(forensic_follow_up) is not bool
            or (forensic_follow_up and circumstance_bonus != 2)
            or (not forensic_follow_up and circumstance_bonus != 0)
        ):
            raise ValueError("save has invalid pending Recall Knowledge command")
        return RecallKnowledge(
            subject_key,
            question,
            skill,
            target_id,
            circumstance_bonus,
            forensic_follow_up,
        )
    if kind == "ForensicExamination":
        if set(data) != {"type", "examination_key"}:
            raise ValueError("save has invalid pending Forensic examination command")
        examination_key = data["examination_key"]
        if not isinstance(examination_key, str) or not examination_key:
            raise ValueError("save has invalid pending Forensic examination command")
        return ForensicExamination(examination_key)
    if kind == "ConfidentFinisher":
        expected = {"type", "target_id", "attack_id", "damage_type", "nonlethal", "item_id"}
        if set(data) != expected:
            raise ValueError("save has invalid pending Confident Finisher command")
        target_id = data["target_id"]
        if (
            not isinstance(target_id, str) or not target_id
            or (data["attack_id"] is not None and (not isinstance(data["attack_id"], str) or not data["attack_id"]))
            or (data["damage_type"] is not None and (not isinstance(data["damage_type"], str) or not data["damage_type"]))
            or (data["item_id"] is not None and (not isinstance(data["item_id"], str) or not data["item_id"]))
            or (data["nonlethal"] is not None and type(data["nonlethal"]) is not bool)
        ):
            raise ValueError("save has invalid pending Confident Finisher command")
        return ConfidentFinisher(
            target_id,
            data["attack_id"],
            data["damage_type"],
            data["nonlethal"],
            data["item_id"],
        )
    raise ValueError("save has unsupported pending family command")


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
        "heroic_recovery_damage", "damage_defense", "shield_block", "reaction", "spell_target", "spell_self_inclusion",
        "spell_willingness", "spell_blood_magic_recipient", "guidance_use", "spell_attack_hero_reroll",
        "spell_save_hero_reroll", "spell_slot",
        "grabbed_manipulate_hero_reroll",
        "family_action", "nimble_dodge", "concealment_hero_reroll",
        "desperate_prayer",
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
    for key in ("actor_id", "target_id", "attack_id", "item_id", "damage_text", "transition_kind", "check_kind", "check_owner_actor_id", "spell_id", "slot_id", "spell_target_item_id", "effect_id", "damage_adjustment", "damage_context", "family_id", "procedure_id"):
        value = data.get(key)
        if value is not None and not isinstance(value, str):
            raise ValueError(f"save has invalid pending choice {key}")
        optional_strings[key] = value
    ints: dict[str, int] = {}
    for key in (
        "attack_penalty", "attack_count", "actions_cost", "spell_actions", "ranged_penalty",
        "guidance_bonus", "temporary_hp_absorbed", "remaining_hp_damage",
    ):
        ints[key] = _required_int(data, key)
    if ints["temporary_hp_absorbed"] < 0 or ints["remaining_hp_damage"] < 0:
        raise ValueError("save has invalid pending temporary-HP damage accounting")
    if ints["attack_count"] < 0:
        raise ValueError("save has invalid pending attack count")
    attack_critical = _required_bool(data, "attack_critical")
    nonlethal = _required_bool(data, "nonlethal")
    feint_off_guard_applied = _required_bool(data, "feint_off_guard_applied")
    attack_target_off_guard = _required_bool(data, "attack_target_off_guard")
    nimble_dodge_used = _required_bool(data, "nimble_dodge_used")
    concealment_checked = _required_bool(data, "concealment_checked")
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
    family_id = optional_strings["family_id"]
    procedure_id = optional_strings["procedure_id"]
    barbarian_choice_raw = data.get("barbarian_choice")
    barbarian_choice = None
    if barbarian_choice_raw is not None:
        if (
            not isinstance(barbarian_choice_raw, dict)
            or any(
                not isinstance(barbarian_choice_raw.get(key), str) or not barbarian_choice_raw[key]
                for key in ("procedure_id", "actor_id", "command_kind")
            )
            or (
                barbarian_choice_raw.get("mode_id") is not None
                and not isinstance(barbarian_choice_raw["mode_id"], str)
            )
            or (
                barbarian_choice_raw.get("temporary_hp_choice") is not None
                and not isinstance(barbarian_choice_raw["temporary_hp_choice"], str)
            )
        ):
            raise ValueError("save has invalid Barbarian choice payload")
        barbarian_choice = RageModeChoice(
            barbarian_choice_raw["procedure_id"],
            barbarian_choice_raw["actor_id"],
            barbarian_choice_raw["command_kind"],
            barbarian_choice_raw.get("mode_id"),
            barbarian_choice_raw.get("temporary_hp_choice"),
        )
    saved_check = _saved_check_from_data(data.get("saved_check"))
    paired_strike = _paired_strike_from_data(data.get("paired_strike"))
    family_command = _family_command_from_data(data.get("family_command"))
    damage_resolution = _damage_resolution_from_data(data.get("damage_resolution"))
    damage_result_is_mitigated = _required_bool(data, "damage_result_is_mitigated")
    if kind == "family_action":
        if (
            family_id not in {"martial", "casting", "items", "minions"}
            or not procedure_id
            or optional_strings["actor_id"] is None
            or _continuation_from_data(data.get("continuation")) is None
        ):
            raise ValueError("save has an incomplete family action choice")
    elif kind != "concealment_hero_reroll" and (
        family_id is not None or procedure_id is not None
    ):
        raise ValueError("save has family identifiers on a non-family choice")
    if family_command is not None and (
        kind not in {"family_action", "concealment_hero_reroll"}
        or family_id != "martial"
    ):
        raise ValueError("save has a skill command on a non-martial family choice")
    if kind == "concealment_hero_reroll":
        spell_concealment = (
            family_id is None
            and procedure_id is None
            and optional_strings["spell_id"] in {
                "divine_lance", "heal", "soothe", "fear", "void_warp", "guidance", "stabilize",
                "runic_weapon",
            }
        )
        strike_concealment = (
            family_id is None
            and procedure_id is None
            and optional_strings["spell_id"] is None
            and optional_strings["attack_id"] is not None
        )
        skill_concealment = (
            family_id == "martial"
            and procedure_id is not None
            and procedure_id.startswith("skill_actions:")
        )
        if not (spell_concealment or strike_concealment or skill_concealment):
            raise ValueError("save has an invalid concealment choice")
    if barbarian_choice is not None and (
        kind != "family_action" or family_id != "martial"
        or procedure_id not in {
            "barbarian:quick_tempered", "barbarian:rage_mode", "barbarian:temporary_hp",
        }
        or barbarian_choice.procedure_id != procedure_id
    ):
        raise ValueError("save has a Barbarian payload on another choice")
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
        item_id=optional_strings["item_id"],
        attack_penalty=ints["attack_penalty"],
        attack_count=ints["attack_count"],
        # Fear's saved Will check is validated against the live target/caster
        # state below (after deserialization).  Keep structural check parsing
        # here, but defer arithmetic so a changed DC or current modifier gets
        # the specific Fear admission error from Encounter's validator.
        check=_check_from_data(
            data.get("check"),
            validate_arithmetic=not (
                kind == "spell_save_hero_reroll" and optional_strings["spell_id"] == "fear"
            ),
        ),
        damage_result=_damage_from_data(
            data.get("damage_result"), allow_mitigated=damage_result_is_mitigated
        ),
        damage_result_is_mitigated=damage_result_is_mitigated,
        damage_resolution=damage_resolution,
        damage_text=optional_strings["damage_text"],
        temporary_hp_absorbed=ints["temporary_hp_absorbed"],
        remaining_hp_damage=ints["remaining_hp_damage"],
        attack_critical=attack_critical,
        damage_type=damage_type,
        nonlethal=nonlethal,
        damage_bonus_dice=damage_bonus_dice,
        attack_actions_cost=attack_actions_cost,
        attack_count_cost=attack_count_cost,
        ranged_penalty=ints["ranged_penalty"],
        guidance_bonus=ints["guidance_bonus"],
        feint_off_guard_applied=feint_off_guard_applied,
        attack_target_off_guard=attack_target_off_guard,
        nimble_dodge_used=nimble_dodge_used,
        concealment_checked=concealment_checked,
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
        spell_target_item_id=optional_strings["spell_target_item_id"],
        actions_cost=ints["actions_cost"],
        spell_actions=ints["spell_actions"],
        include_self=include_self,
        effect_id=optional_strings["effect_id"],
        damage_adjustment=optional_strings["damage_adjustment"],
        damage_context=optional_strings["damage_context"],
        target_ids=tuple(target_ids),
        family_id=family_id,
        procedure_id=procedure_id,
        barbarian_choice=barbarian_choice,
        saved_check=saved_check,
        paired_strike=paired_strike,
        family_command=family_command,
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
        "finisher": continuation.finisher,
        "movement_kind": continuation.movement_kind,
        "reaction_trigger": continuation.reaction_trigger,
        "spell_id": continuation.spell_id,
        "spell_target_id": continuation.spell_target_id,
        "spell_target_item_id": continuation.spell_target_item_id,
        "spell_target_wielder_id": continuation.spell_target_wielder_id,
        "slot_id": continuation.slot_id,
        "spell_actions": continuation.spell_actions,
        "include_self": continuation.include_self,
        "spell_source_kind": continuation.spell_source_kind,
        "sorcerous_potency": continuation.sorcerous_potency,
        "blood_magic_recipient_id": continuation.blood_magic_recipient_id,
        "spell_damage": _damage_to_data(continuation.spell_damage),
        "spell_check": _check_to_data(continuation.spell_check),
        "spell_save_degree": continuation.spell_save_degree,
        "target_ids": list(continuation.target_ids),
        "ranged_penalty": continuation.ranged_penalty,
        "guidance_bonus": continuation.guidance_bonus,
        "feint_off_guard_applied": continuation.feint_off_guard_applied,
        "guidance_checked": continuation.guidance_checked,
        "stage": continuation.stage,
        "parent_continuation": _continuation_to_data(continuation.parent_continuation),
        "attack_count_committed": continuation.attack_count_committed,
        "attack_target_off_guard": continuation.attack_target_off_guard,
        "nimble_dodge_decided": continuation.nimble_dodge_decided,
        "nimble_dodge_used": continuation.nimble_dodge_used,
        "concealment_checked": continuation.concealment_checked,
        "light_control": continuation.light_control,
        "light_point": None if continuation.light_point is None else [
            continuation.light_point.x, continuation.light_point.y
        ],
        "light_color": continuation.light_color,
        "light_attachment_actor_id": continuation.light_attachment_actor_id,
        "light_replacement_orb_id": continuation.light_replacement_orb_id,
        "light_orb_id": continuation.light_orb_id,
        "targeting_failed": continuation.targeting_failed,
        "sure_strike_checked": continuation.sure_strike_checked,
        "sure_strike_used": continuation.sure_strike_used,
        "use_intelligence": continuation.use_intelligence,
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
    kind = _required_str(data, "kind")
    optional_strings = {}
    for key in ("mode", "item_id", "target_id", "attack_id", "damage_type", "movement_kind", "reaction_trigger", "spell_id", "spell_target_id", "spell_target_item_id", "spell_target_wielder_id", "slot_id", "stage", "spell_source_kind", "blood_magic_recipient_id", "light_control", "light_color", "light_attachment_actor_id", "light_replacement_orb_id", "light_orb_id"):
        value = data.get(key)
        if value is not None and not isinstance(value, str):
            raise ValueError(f"save has invalid interrupted action {key}")
        optional_strings[key] = value
    integers = {
        key: _required_int(data, key)
        for key in ("next_step", "damage_bonus_dice", "attack_actions_cost", "attack_count_cost", "attack_penalty", "attack_count", "spell_actions", "ranged_penalty", "guidance_bonus")
    }
    sorcerous_potency = data.get("sorcerous_potency", 0)
    if type(sorcerous_potency) is not int or sorcerous_potency < 0:
        raise ValueError("save has invalid Sorcerous Potency")
    spell_source_kind = optional_strings["spell_source_kind"]
    if spell_source_kind not in {None, "prepared", "spontaneous", "focus"}:
        raise ValueError("save has an unsupported spell resource source")
    if spell_source_kind == "focus":
        if optional_strings["slot_id"] != "actor_focus_pool" or sorcerous_potency != 0:
            raise ValueError("save has invalid focus cast resource provenance")
    elif spell_source_kind == "prepared":
        if sorcerous_potency != 0 or optional_strings["blood_magic_recipient_id"] is not None:
            raise ValueError("save has invalid prepared cast resource provenance")
    elif spell_source_kind is None:
        if sorcerous_potency != 0 or optional_strings["blood_magic_recipient_id"] is not None:
            raise ValueError("save has invalid untyped cast resource provenance")
    elif optional_strings["spell_id"] == "heal":
        if optional_strings["slot_id"] is None or sorcerous_potency != 1:
            raise ValueError(
                "save has invalid spontaneous Heal resource provenance for Blood Magic recipient choice"
            )
    if (
        optional_strings["blood_magic_recipient_id"] is not None
        and optional_strings["spell_id"] not in {"heal", "angelic_halo"}
    ):
        raise ValueError("save has Blood Magic provenance on a non-Blood-Magic spell")
    if optional_strings["spell_id"] == "runic_weapon" and (
        optional_strings["spell_target_item_id"] is None
        or optional_strings["spell_target_id"] is not None
        or optional_strings["target_id"] is not None
        or optional_strings["spell_source_kind"] != "spontaneous"
        or optional_strings["slot_id"] is None
        or integers["spell_actions"] != 2
        or sorcerous_potency != 0
        or optional_strings["blood_magic_recipient_id"] is not None
    ):
        raise ValueError("save has invalid Runic Weapon item-target provenance")
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
    light_point_raw = data.get("light_point")
    if light_point_raw is not None:
        if (
            not isinstance(light_point_raw, list)
            or len(light_point_raw) != 2
            or any(type(value) is not int for value in light_point_raw)
        ):
            raise ValueError("save has invalid interrupted Light point")
        light_point = Position(*light_point_raw)
    else:
        light_point = None
    use_intelligence = data.get("use_intelligence")
    if use_intelligence is not None and type(use_intelligence) is not bool:
        raise ValueError("save has invalid Investigator Intelligence intent")
    finisher = data.get("finisher", False)
    if type(finisher) is not bool:
        raise ValueError("save has invalid Confident Finisher continuation")
    light_fields = (
        optional_strings["light_control"],
        light_point,
        optional_strings["light_color"],
        optional_strings["light_attachment_actor_id"],
        optional_strings["light_replacement_orb_id"],
        optional_strings["light_orb_id"],
    )
    if any(value is not None for value in light_fields) and optional_strings["spell_id"] != "light":
        raise ValueError("save has Light continuation data on a non-Light action")
    if optional_strings["spell_id"] == "light":
        light_control = optional_strings["light_control"]
        if kind != "cast":
            raise ValueError("save has invalid Light continuation facts")
        if light_control == "sustain":
            if (
                light_point is None
                or optional_strings["light_color"] is not None
                or optional_strings["light_replacement_orb_id"] is not None
                or optional_strings["light_orb_id"] is None
            ):
                raise ValueError("save has invalid Light Sustain continuation facts")
        elif light_control is not None:
            raise ValueError("save has unsupported Light continuation control")
        elif (
            light_point is None
            or optional_strings["light_color"] is None
            or not optional_strings["light_color"].strip()
        ):
            raise ValueError("save has invalid Light continuation facts")
    return ActionContinuation(
        kind=kind,
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
        finisher=finisher,
        movement_kind=optional_strings["movement_kind"],
        reaction_trigger=optional_strings["reaction_trigger"],
        spell_id=optional_strings["spell_id"],
        spell_target_id=optional_strings["spell_target_id"],
        spell_target_item_id=optional_strings["spell_target_item_id"],
        spell_target_wielder_id=optional_strings["spell_target_wielder_id"],
        slot_id=optional_strings["slot_id"],
        spell_actions=integers["spell_actions"],
        include_self=include_self,
        spell_source_kind=optional_strings["spell_source_kind"],
        sorcerous_potency=sorcerous_potency,
        blood_magic_recipient_id=optional_strings["blood_magic_recipient_id"],
        spell_damage=_damage_from_data(data.get("spell_damage")),
        spell_check=_check_from_data(data.get("spell_check")),
        spell_save_degree=spell_save_degree,
        target_ids=tuple(target_ids),
        ranged_penalty=integers["ranged_penalty"],
        guidance_bonus=integers["guidance_bonus"],
        feint_off_guard_applied=_required_bool(data, "feint_off_guard_applied"),
        guidance_checked=_required_bool(data, "guidance_checked"),
        stage=optional_strings["stage"],
        parent_continuation=_continuation_from_data(data.get("parent_continuation")),
        attack_count_committed=_required_bool(data, "attack_count_committed"),
        attack_target_off_guard=_required_bool(data, "attack_target_off_guard"),
        nimble_dodge_decided=_required_bool(data, "nimble_dodge_decided"),
        nimble_dodge_used=_required_bool(data, "nimble_dodge_used"),
        concealment_checked=_required_bool(data, "concealment_checked"),
        targeting_failed=(
            _required_bool(data, "targeting_failed")
            if "targeting_failed" in data
            else False
        ),
        sure_strike_checked=(
            _required_bool(data, "sure_strike_checked")
            if "sure_strike_checked" in data
            else False
        ),
        sure_strike_used=(
            _required_bool(data, "sure_strike_used")
            if "sure_strike_used" in data
            else False
        ),
        use_intelligence=use_intelligence,
        light_control=optional_strings["light_control"],
        light_point=light_point,
        light_color=optional_strings["light_color"],
        light_attachment_actor_id=optional_strings["light_attachment_actor_id"],
        light_replacement_orb_id=optional_strings["light_replacement_orb_id"],
        light_orb_id=optional_strings["light_orb_id"],
    )


def _check_to_data(check: CheckResult | None) -> dict[str, Any] | None:
    if check is None:
        return None
    return {
        "die": check.die,
        "method": check.method,
        "dice": list(check.dice),
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


def _check_from_data(data: Any, *, validate_arithmetic: bool = True) -> CheckResult | None:
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
    method = _required_str(data, "method")
    die = data.get("die")
    dice_raw = data.get("dice", [die] if method == "d20" else [])
    if not isinstance(dice_raw, list) or any(type(face) is not int or not 1 <= face <= 20 for face in dice_raw):
        raise ValueError("save has invalid pending check dice")
    if method == "d20":
        if type(die) is not int or not 1 <= die <= 20 or len(dice_raw) not in {1, 2}:
            raise ValueError("save has invalid pending check die")
        if len(dice_raw) == 1 and dice_raw[0] != die:
            raise ValueError("save has inconsistent pending check dice")
        if len(dice_raw) == 2 and max(dice_raw) != die:
            raise ValueError("save has inconsistent Sure Strike dice")
    elif method == "assurance":
        if die is not None or dice_raw:
            raise ValueError("save has an Assurance check with a fabricated die")
    else:
        raise ValueError("save has unsupported pending check method")
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
        method=method,
        dice=tuple(dice_raw),
    )
    if validate_arithmetic:
        expected = (
            resolve_check(
                check.die,
                check.modifier,
                check.dc,
                attack_id=check.attack_id,
                attack_count=check.attack_count,
                map_penalty=check.map_penalty,
                traits=check.traits,
            )
            if method == "d20"
            else resolve_assurance_check(
                check.modifier,
                check.dc,
                attack_id=check.attack_id,
                attack_count=check.attack_count,
                traits=check.traits,
            )
        )
        # D20 resolution has no intrinsic modifier breakdown, while the
        # Assurance resolver records its fixed proficiency bonus as one.
        # Compare the persisted breakdown against the matching resolver shape
        # so an Assurance result can survive a pending target save/load.
        if replace(check, modifier_breakdown=(), dice=()) != replace(expected, modifier_breakdown=(), dice=()):
            raise ValueError("save has internally inconsistent pending check arithmetic or degree")
        if combine_modifiers(check.modifier_breakdown) != check.modifier:
            raise ValueError("save has internally inconsistent pending check modifiers")
    return check


def _saved_check_to_data(saved: SavedCheckContext | None) -> dict[str, Any] | None:
    if saved is None:
        return None
    return {
        "check_owner_actor_id": saved.check_owner_actor_id,
        "context": [saved.context.statistic, saved.context.attribute, sorted(saved.context.traits)],
        "dc": saved.dc,
        "modifiers": [[item.amount, item.modifier_type, item.source] for item in saved.modifiers],
        "pre_roll_choices": list(saved.pre_roll_choices),
        "result": _check_to_data(saved.result),
        "fortune_used": saved.fortune_used,
        "reroll_used": saved.reroll_used,
        "parent_continuation": _continuation_to_data(saved.parent_continuation),
        "attack_id": saved.attack_id,
        "attack_count_committed": saved.attack_count_committed,
        "sure_strike_used": saved.sure_strike_used,
    }


def _saved_check_from_data(data: Any) -> SavedCheckContext | None:
    if data is None:
        return None
    if not isinstance(data, dict):
        raise ValueError("save has invalid saved check context")
    owner = data.get("check_owner_actor_id")
    attack_id = data.get("attack_id")
    context_raw = data.get("context")
    dc = data.get("dc")
    modifiers_raw = data.get("modifiers")
    pre_roll = data.get("pre_roll_choices")
    if (
        not isinstance(owner, str) or not owner
        or not isinstance(context_raw, list) or len(context_raw) != 3
        or not isinstance(context_raw[0], str) or not context_raw[0]
        or (context_raw[1] is not None and (not isinstance(context_raw[1], str) or not context_raw[1]))
        or not isinstance(context_raw[2], list)
        or any(not isinstance(item, str) or not item for item in context_raw[2])
        or type(dc) is not int or dc < 0
        or not isinstance(modifiers_raw, list)
        or not isinstance(pre_roll, list)
        or any(not isinstance(item, str) or not item for item in pre_roll)
        or (attack_id is not None and (not isinstance(attack_id, str) or not attack_id))
    ):
        raise ValueError("save has invalid saved check facts")
    modifiers: list[Modifier] = []
    for row in modifiers_raw:
        if (
            not isinstance(row, list) or len(row) != 3
            or type(row[0]) is not int
            or not isinstance(row[1], str) or not row[1]
            or not isinstance(row[2], str) or not row[2]
        ):
            raise ValueError("save has invalid saved check modifier")
        modifiers.append(Modifier(*row))
    context = CheckContext(context_raw[0], context_raw[1], frozenset(context_raw[2]))
    result = _check_from_data(data.get("result"))
    fortune_used = data.get("fortune_used")
    reroll_used = data.get("reroll_used")
    attack_count_committed = data.get("attack_count_committed", False)
    sure_strike_used = data.get("sure_strike_used", False)
    if (
        type(fortune_used) is not bool
        or type(reroll_used) is not bool
        or type(attack_count_committed) is not bool
        or type(sure_strike_used) is not bool
    ):
        raise ValueError("save has invalid saved check choice flags")
    if result is not None:
        if len(result.dice) > 1 and (
            not sure_strike_used
            or context.statistic != "unarmed_attack"
            or "attack" not in context.traits
        ):
            raise ValueError("save has Sure Strike dice on an unsupported saved check")
        map_penalty = sum(item.amount for item in modifiers if item.source == "multiple attack penalty")
        if result.method == "d20":
            expected = resolve_check(
                result.die,
                combine_modifiers(modifiers),
                dc,
                attack_id=result.attack_id,
                attack_count=result.attack_count,
                map_penalty=map_penalty,
                traits=context.traits,
            )
        elif result.method == "assurance":
            if map_penalty != 0 or result.die is not None:
                raise ValueError("save has Assurance with a multiple attack penalty")
            expected_modifiers = (
                Modifier(result.modifier, "untyped", "Assurance proficiency bonus"),
            )
            if tuple(modifiers) != expected_modifiers:
                raise ValueError("save has an Assurance result with extra modifiers")
            expected = resolve_assurance_check(
                combine_modifiers(modifiers),
                dc,
                attack_id=result.attack_id,
                attack_count=result.attack_count,
                traits=context.traits,
            )
        else:
            raise ValueError("save has unsupported saved check method")
        if (
            replace(result, modifier_breakdown=(), dice=())
            != replace(expected, modifier_breakdown=(), dice=())
            or result.modifier_breakdown != tuple(modifiers)
        ):
            raise ValueError("save has inconsistent saved check result")
        if result.attack_id != attack_id:
            raise ValueError("save has a saved check result for a different attack profile")
    if attack_id is not None and (
        context.statistic != "unarmed_attack" or "attack" not in context.traits
    ):
        raise ValueError("save has an attack profile on a non-attack check")
    if sure_strike_used and (
        result is None
        or context.statistic != "unarmed_attack"
        or "attack" not in context.traits
        or len(result.dice) != 2
    ):
        raise ValueError("save has invalid Sure Strike saved-check facts")
    return SavedCheckContext(
        check_owner_actor_id=owner,
        context=context,
        dc=dc,
        modifiers=tuple(modifiers),
        pre_roll_choices=tuple(pre_roll),
        result=result,
        fortune_used=fortune_used,
        reroll_used=reroll_used,
        parent_continuation=_continuation_from_data(data.get("parent_continuation")),
        attack_id=attack_id,
        attack_count_committed=attack_count_committed,
        sure_strike_used=sure_strike_used,
    )


def _damage_group_to_data(group: DamageGroup | None) -> dict[str, Any] | None:
    if group is None:
        return None
    return {
        "group_id": group.group_id,
        "results": [_damage_to_data(result) for result in group.results],
        "source_kind": group.source_kind,
        "traits": sorted(group.traits),
    }


def _damage_group_from_data(data: Any) -> DamageGroup | None:
    if data is None:
        return None
    if not isinstance(data, dict):
        raise ValueError("save has invalid pending damage group")
    group_id = _required_str(data, "group_id")
    source_kind = _required_str(data, "source_kind")
    traits = _required_str_list(data, "traits")
    if len(set(traits)) != len(traits):
        raise ValueError("save has duplicate pending damage group traits")
    raw_results = data.get("results")
    if not isinstance(raw_results, list):
        raise ValueError("save has invalid pending damage group results")
    results = tuple(_damage_from_data(result) for result in raw_results)
    if any(result is None for result in results):
        raise ValueError("save has a missing pending damage group result")
    return DamageGroup(group_id, results, source_kind, frozenset(traits))


def _damage_resolution_to_data(resolution: DamageResolution | None) -> dict[str, Any] | None:
    if resolution is None:
        return None
    choice = resolution.pending_defense_choice
    return {
        "source_kind": resolution.source_kind,
        "group": _damage_group_to_data(resolution.group),
        "actor_id": resolution.actor_id,
        "target_id": resolution.target_id,
        "source": resolution.source,
        "damage_type": resolution.damage_type,
        "check": _check_to_data(resolution.check),
        "attack_id": resolution.attack_id,
        "spell_id": resolution.spell_id,
        "nonlethal": resolution.nonlethal,
        "attacker_critical": resolution.attacker_critical,
        "target_critical_failure": resolution.target_critical_failure,
        "attack_target_off_guard": resolution.attack_target_off_guard,
        "damage_bonus_dice": resolution.damage_bonus_dice,
        "is_reaction": resolution.is_reaction,
        "continuation": _continuation_to_data(resolution.continuation),
        "enfeebled_on_failure": resolution.enfeebled_on_failure,
        "complete_family_action_on_resume": resolution.complete_family_action_on_resume,
        "selections": [
            [item.defense_source, item.part.result_index, item.part.component_index]
            for item in resolution.selections
        ],
        "pending_defense_choice": None if choice is None else {
            "defense_source": choice.defense_source,
            "eligible_parts": [[part.result_index, part.component_index] for part in choice.eligible_parts],
        },
        "shield_block_status": resolution.shield_block_status,
        "shield_block_instance_id": resolution.shield_block_instance_id,
        "justice_checked": resolution.justice_checked,
        "justice_actor_id": resolution.justice_actor_id,
        "justice_protected": resolution.justice_protected,
        "shield_block_record": None if resolution.shield_block_record is None else {
            "shield_instance_id": resolution.shield_block_record.shield_instance_id,
            "hardness": resolution.shield_block_record.hardness,
            "incoming_damage": resolution.shield_block_record.incoming_damage,
            "shield_vulnerable_damage": resolution.shield_block_record.shield_vulnerable_damage,
            "prevented_from_actor": resolution.shield_block_record.prevented_from_actor,
            "damage_to_actor": resolution.shield_block_record.damage_to_actor,
            "damage_to_shield": resolution.shield_block_record.damage_to_shield,
            "shield_hp_before": resolution.shield_block_record.shield_hp_before,
            "shield_hp_after": resolution.shield_block_record.shield_hp_after,
        },
    }


def _damage_resolution_from_data(data: Any) -> DamageResolution | None:
    if data is None:
        return None
    if not isinstance(data, dict):
        raise ValueError("save has invalid damage resolution")
    source_kind = _required_str(data, "source_kind")
    if source_kind not in {"strike", "spell", "family"}:
        raise ValueError("save has unsupported damage source kind")
    group = _damage_group_from_data(data.get("group"))
    if group is None or len(group.results) != 1:
        raise ValueError("save has invalid damage resolution group")
    actor_id = _required_str(data, "actor_id")
    target_id = _required_str(data, "target_id")
    source = _required_str(data, "source")
    damage_type = _required_str(data, "damage_type")
    attack_id = data.get("attack_id")
    spell_id = data.get("spell_id")
    for name, value in (("attack_id", attack_id), ("spell_id", spell_id)):
        if value is not None and (not isinstance(value, str) or not value):
            raise ValueError(f"save has invalid damage resolution {name}")
    if source_kind == "strike" and not attack_id:
        raise ValueError("save has a Strike damage resolution without an attack")
    if source_kind == "spell" and not spell_id:
        raise ValueError("save has a spell damage resolution without a spell")
    bonus_dice = _required_int(data, "damage_bonus_dice")
    enfeebled = _required_int(data, "enfeebled_on_failure")
    if bonus_dice < 0 or enfeebled < 0:
        raise ValueError("save has invalid damage resolution counters")
    selection_rows = data.get("selections")
    if not isinstance(selection_rows, list):
        raise ValueError("save has invalid damage defense selections")
    selections: list[DefenseSelection] = []
    for row in selection_rows:
        if (
            not isinstance(row, list) or len(row) != 3
            or not isinstance(row[0], str) or not row[0]
            or type(row[1]) is not int or type(row[2]) is not int
        ):
            raise ValueError("save has invalid damage defense selection")
        selections.append(DefenseSelection(row[0], DamagePartRef(row[1], row[2])))
    if len({selection.defense_source for selection in selections}) != len(selections):
        raise ValueError("save has duplicate damage defense selection")
    choice_raw = data.get("pending_defense_choice")
    choice = None
    if choice_raw is not None:
        if not isinstance(choice_raw, dict):
            raise ValueError("save has invalid pending damage defense choice")
        defense_source = _required_str(choice_raw, "defense_source")
        raw_parts = choice_raw.get("eligible_parts")
        if not isinstance(raw_parts, list):
            raise ValueError("save has invalid eligible damage parts")
        parts: list[DamagePartRef] = []
        for row in raw_parts:
            if (
                not isinstance(row, list) or len(row) != 2
                or type(row[0]) is not int or type(row[1]) is not int
            ):
                raise ValueError("save has invalid eligible damage part")
            parts.append(DamagePartRef(row[0], row[1]))
        if not parts or len(set(parts)) != len(parts):
            raise ValueError("save has invalid eligible damage parts")
        choice = DefenseChoice(defense_source, tuple(parts))
    shield_block_status = data.get("shield_block_status")
    shield_block_instance_id = data.get("shield_block_instance_id")
    if shield_block_status is not None and (
        not isinstance(shield_block_status, str)
        or shield_block_status not in {"pending", "applied", "declined"}
    ):
        raise ValueError("save has invalid Shield Block status")
    if shield_block_instance_id is not None and (
        not isinstance(shield_block_instance_id, str) or not shield_block_instance_id
    ):
        raise ValueError("save has invalid Shield Block item identity")
    shield_block_raw = data.get("shield_block_record")
    shield_block_record = None
    if shield_block_raw is not None:
        if not isinstance(shield_block_raw, dict):
            raise ValueError("save has invalid Shield Block record")
        shield_block_instance = _required_str(shield_block_raw, "shield_instance_id")
        shield_block_values = {
            key: _required_int(shield_block_raw, key)
            for key in (
                "hardness", "incoming_damage", "shield_vulnerable_damage",
                "prevented_from_actor", "damage_to_actor", "damage_to_shield",
                "shield_hp_before", "shield_hp_after",
            )
        }
        if any(value < 0 for value in shield_block_values.values()):
            raise ValueError("save has invalid Shield Block amounts")
        shield_block_record = ShieldBlockRecord(
            shield_block_instance, **shield_block_values
        )
    if (
        (shield_block_status == "applied") != (shield_block_record is not None)
        or (shield_block_status == "pending") != (shield_block_instance_id is not None and shield_block_record is None)
        or (shield_block_status == "declined" and shield_block_instance_id is None)
        or (shield_block_record is not None and shield_block_instance_id != shield_block_record.shield_instance_id)
        or (shield_block_status is None and shield_block_instance_id is not None)
    ):
        raise ValueError("save has inconsistent Shield Block continuation data")
    if shield_block_record is not None:
        record = shield_block_record
        if (
            record.hardness <= 0
            or record.shield_vulnerable_damage > record.incoming_damage
            or record.prevented_from_actor != min(record.incoming_damage, record.hardness)
            or record.damage_to_actor != record.incoming_damage - record.prevented_from_actor
            or record.damage_to_shield != max(0, record.shield_vulnerable_damage - record.hardness)
            or record.shield_hp_after != max(0, record.shield_hp_before - record.damage_to_shield)
            ):
            raise ValueError("save has an inconsistent Shield Block arithmetic record")
    justice_checked = data.get("justice_checked", False)
    justice_protected = data.get("justice_protected", False)
    justice_actor_id = data.get("justice_actor_id")
    if type(justice_checked) is not bool or type(justice_protected) is not bool:
        raise ValueError("save has invalid Justice protection flags")
    if justice_actor_id is not None and (not isinstance(justice_actor_id, str) or not justice_actor_id):
        raise ValueError("save has invalid Justice protector")
    if not justice_checked and (justice_actor_id is not None or justice_protected):
        raise ValueError("save has Justice protection facts before its trigger check")
    if justice_protected and justice_actor_id is None:
        raise ValueError("save has protected Justice damage without a Champion")
    return DamageResolution(
        source_kind=source_kind,
        group=group,
        actor_id=actor_id,
        target_id=target_id,
        source=source,
        damage_type=damage_type,
        check=_check_from_data(data.get("check")),
        attack_id=attack_id,
        spell_id=spell_id,
        nonlethal=_required_bool(data, "nonlethal"),
        attacker_critical=_required_bool(data, "attacker_critical"),
        target_critical_failure=_required_bool(data, "target_critical_failure"),
        attack_target_off_guard=_required_bool(data, "attack_target_off_guard"),
        damage_bonus_dice=bonus_dice,
        is_reaction=_required_bool(data, "is_reaction"),
        continuation=_continuation_from_data(data.get("continuation")),
        enfeebled_on_failure=enfeebled,
        complete_family_action_on_resume=_required_bool(data, "complete_family_action_on_resume"),
        selections=tuple(selections),
        pending_defense_choice=choice,
        shield_block_status=shield_block_status,
        shield_block_instance_id=shield_block_instance_id,
        shield_block_record=shield_block_record,
        justice_checked=justice_checked,
        justice_actor_id=justice_actor_id,
        justice_protected=justice_protected,
    )


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
             list(component.rolls), component.modifier, component.amount,
             sorted(component.tags), component.critical_mode, list(component.dice)]
            for component in result.components
        ],
    }


def _damage_from_data(data: Any, *, allow_mitigated: bool = False) -> DamageResult | None:
    if data is None:
        return None
    if not isinstance(data, dict) or not isinstance(data.get("components"), list):
        raise ValueError("save has invalid pending damage")
    components: list[DamageComponent] = []
    for row in data["components"]:
        if not isinstance(row, list) or len(row) != 9:
            raise ValueError("save has invalid pending damage component")
        source, damage_type, sides, rolls, modifier, amount, tags, critical_mode, dice = row
        if (
            not isinstance(source, str) or not source
            or not isinstance(damage_type, str) or not damage_type
            or type(sides) is not int or sides < 0
            or not isinstance(rolls, list)
            or type(modifier) is not int or type(amount) is not int or amount < 0
            or not isinstance(tags, list)
            or any(not isinstance(tag, str) or not tag for tag in tags)
            or len(set(tags)) != len(tags)
            or critical_mode not in {"double", "unchanged", "critical_only"}
            or not isinstance(dice, list)
            or any(type(size) is not int or size < 2 for size in dice)
            or sides != (dice[0] if dice else 0)
        ):
            raise ValueError("save has invalid pending damage component")
        if len(rolls) not in (0, len(dice)) or (rolls and len(rolls) != len(dice)):
            raise ValueError("save has invalid pending damage dice")
        if len(rolls) == len(dice) and any(
            type(face) is not int or not 1 <= face <= size
            for face, size in zip(rolls, dice)
        ):
            raise ValueError("save has a pending damage die outside its range")
        components.append(DamageComponent(
            source, damage_type, sides, tuple(rolls), modifier, amount,
            frozenset(tags), critical_mode, tuple(dice),
        ))
    rolled_total = _required_int(data, "rolled_total")
    multiplier = _required_int(data, "multiplier")
    total = _required_int(data, "total")
    adjustment = data.get("adjustment")
    if adjustment is not None and not isinstance(adjustment, str):
        raise ValueError("save has invalid pending damage adjustment")
    component_total = sum(component.amount for component in components)
    if multiplier not in (1, 2) or total != component_total:
        raise ValueError("save has inconsistent pending damage")
    raw_components = tuple(
        0 if component.critical_mode == "critical_only" and multiplier == 1
        else sum(component.rolls) + component.modifier
        for component in components
    )
    raw_total = sum(raw_components)
    if raw_total != rolled_total:
        raise ValueError("save has inconsistent pending damage roll total")
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
            if (not allow_mitigated and total != expected) or rolled_total != raw:
                raise ValueError("save has inconsistent basic-save damage")
        elif adjustment == "deadly_after_critical":
            if (
                multiplier != 2 or len(components) < 2
                or raw_total != rolled_total
            ):
                raise ValueError("save has inconsistent deadly damage")
        else:
            raise ValueError("save has unsupported pending damage adjustment")
    elif not allow_mitigated:
        expected_amounts = tuple(
            raw * (multiplier if component.critical_mode == "double" else 1)
            for raw, component in zip(raw_components, components)
        )
        if tuple(component.amount for component in components) != expected_amounts:
            raise ValueError("save has inconsistent pending damage components")
    if not allow_mitigated:
        if total != sum(component.amount for component in components):
            raise ValueError("save has inconsistent pending damage total")
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
