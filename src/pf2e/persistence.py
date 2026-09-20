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
    GiantCentipedeVenomAffliction,
    PersistentDamageEffect,
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
    MartialStanceState,
    RaisedShieldState,
    ShieldBlockRecord,
    Position,
    PreparedSlotState,
    SpellSubstitutionState,
    SpontaneousSlotState,
    SavedCheckContext,
    is_combat_capable,
)
from .conditions import CheckContext, ConditionValue, effective_condition_value
from .health import HealthState, HealthTransition
from .items import ItemInstance, STEEL_SHIELD, runtime_item_instance_id
from .martial_defense import dueling_parry_requirements_met
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
    PERSON_OF_INTEREST_ABILITY,
    PERSON_OF_INTEREST_COOLDOWN_SECONDS,
    PERSON_OF_INTEREST_DURATION_SECONDS,
    SKILL_STRATAGEM,
    InvestigatorWeaknessBonus,
    PersonOfInterestState,
    stratagem_from_data,
    stratagem_to_data,
    validate_person_of_interest_state,
    validate_stratagem_state,
)
from .swashbuckler import effective_speed_ft
from .alchemy import AlchemyState, InfusedAlchemyItem
from .alchemy_content import FORMULAS_BY_ID
from .spells import CONCEALMENT_TARGETED_SPELL_IDS, SPELLS
from .preparation import has_variable_preparations, prepared_slot_rejection


SAVE_VERSION = 18
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
    initiative_count = sum(
        not get_definition(creature.definition_id).initiative_exempt
        for creature in state.creatures.values()
    )
    if dice.kind == "sequence" and dice._index < initiative_count:
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



def _alchemy_state_to_data(value: object) -> dict[str, Any]:
    state = value
    assert isinstance(state, AlchemyState)
    return {key: getattr(state, key) if key not in {"field_formula_ids", "known_formula_ids"} else list(getattr(state, key)) for key in (
        "character_level", "intelligence_modifier", "research_field", "field_formula_ids", "known_formula_ids", "selected_level_1_feat", "daily_preparation_id", "stored_vials", "vial_capacity", "exploration_seconds_toward_vial_recovery", "next_creation_sequence", "mutagen_temp_hp_available_at_seconds", "selected_level_2_feat")}


def _infused_item_to_data(value: object) -> dict[str, Any]:
    item = value
    assert isinstance(item, InfusedAlchemyItem)
    return {key: getattr(item, key) for key in ("formula_id", "creator_actor_id", "creation_kind", "created_at_seconds", "daily_preparation_id", "expires_at_seconds", "activation_deadline", "creator_turn_occurrence", "creator_turn_id", "temporary_vial")}


def _load_alchemy_records(data: Any, setup) -> tuple[dict[str, AlchemyState], dict[str, InfusedAlchemyItem], set[str]]:
    from .alchemist_content import BOMBER_FIELD_FORMULA_IDS, BOMBER_FORMULA_IDS, BOMBER_LEVEL_2_CONDITION_BOMB_FORMULA_IDS, BOMBER_LEVEL_2_ITEM_SUPPORT_FORMULA_IDS
    from .alchemy import FAR_LOBBER
    from .content import BOMBER_ALCHEMIST_LEVEL_2, BOMBER_ALCHEMIST_LEVEL_2_CONDITION_BOMBS, BOMBER_ALCHEMIST_LEVEL_2_FORMULA_IDS, BOMBER_ALCHEMIST_LEVEL_2_ITEM_SUPPORT

    raw_states = data.get("alchemy_states", {})
    raw_items = data.get("infused_alchemy_items", {})
    consumed = data.get("consumed_infused_item_ids", [])
    expected = {p.actor_id for p in setup.placements if "bomber_alchemist" in get_definition(p.definition_id).abilities}
    if not isinstance(raw_states, dict) or not isinstance(raw_items, dict) or not isinstance(consumed, list) or set(raw_states) != expected:
        raise ValueError("save has invalid Bomber Alchemy records")
    states = {}
    for actor_id, raw in raw_states.items():
        if not isinstance(raw, dict): raise ValueError("save has invalid Bomber Alchemy state")
        try:
            state = AlchemyState(_required_int(raw,"character_level"), _required_int(raw,"intelligence_modifier"), _required_str(raw,"research_field"), tuple(_required_str_list(raw,"field_formula_ids")), tuple(_required_str_list(raw,"known_formula_ids")), raw.get("selected_level_1_feat"), _required_str(raw,"daily_preparation_id"), _required_int(raw,"stored_vials"), _required_int(raw,"vial_capacity"), _required_int(raw,"exploration_seconds_toward_vial_recovery"), _required_int(raw,"next_creation_sequence"), _required_int(raw,"mutagen_temp_hp_available_at_seconds"), raw.get("selected_level_2_feat"))
        except (TypeError, ValueError) as e: raise ValueError("save has invalid Bomber Alchemy state") from e
        definition_id = next(
            placement.definition_id
            for placement in setup.placements
            if placement.actor_id == actor_id
        )
        level_two = definition_id in {
            BOMBER_ALCHEMIST_LEVEL_2.definition_id,
            BOMBER_ALCHEMIST_LEVEL_2_ITEM_SUPPORT.definition_id,
            BOMBER_ALCHEMIST_LEVEL_2_CONDITION_BOMBS.definition_id,
        }
        expected_level = 2 if level_two else 1
        expected_formulas = (
            BOMBER_LEVEL_2_CONDITION_BOMB_FORMULA_IDS
            if definition_id == BOMBER_ALCHEMIST_LEVEL_2_CONDITION_BOMBS.definition_id
            else BOMBER_LEVEL_2_ITEM_SUPPORT_FORMULA_IDS
            if definition_id == BOMBER_ALCHEMIST_LEVEL_2_ITEM_SUPPORT.definition_id
            else BOMBER_ALCHEMIST_LEVEL_2_FORMULA_IDS
            if level_two
            else BOMBER_FORMULA_IDS
        )
        expected_level_two_feat = FAR_LOBBER if level_two else None
        if (
            state.research_field != "bomber"
            or state.intelligence_modifier != 4
            or state.field_formula_ids != BOMBER_FIELD_FORMULA_IDS
            or state.known_formula_ids != expected_formulas
            or state.selected_level_1_feat != "quick_bomber"
            or state.character_level != expected_level
            or state.selected_level_2_feat != expected_level_two_feat
            or state.vial_capacity != 6
        ):
            raise ValueError("save changed selected Bomber build")
        states[actor_id]=state
    items={}
    for item_id, raw in raw_items.items():
        if not isinstance(item_id,str) or not item_id or not isinstance(raw,dict): raise ValueError("save has invalid infused Alchemy item")
        try:
            item=InfusedAlchemyItem(item_id,raw.get("formula_id"),_required_str(raw,"creator_actor_id"),_required_str(raw,"creation_kind"),_required_int(raw,"created_at_seconds"),_required_str(raw,"daily_preparation_id"),_required_int(raw,"expires_at_seconds"),raw.get("activation_deadline"),raw.get("creator_turn_occurrence"),raw.get("creator_turn_id"),_required_bool(raw,"temporary_vial"))
        except (TypeError,ValueError) as e: raise ValueError("save has invalid infused Alchemy item") from e
        owner=states.get(item.creator_actor_id)
        if owner is None or item.formula_id not in owner.known_formula_ids or item.formula_id not in FORMULAS_BY_ID: raise ValueError("save has infused item outside selected Bomber book")
        items[item_id]=item
    if any(not isinstance(i,str) or i not in items for i in consumed) or len(set(consumed))!=len(consumed): raise ValueError("save has invalid consumed infused items")
    if any(item.daily_preparation_id != states[item.creator_actor_id].daily_preparation_id and item_id not in consumed for item_id, item in items.items()): raise ValueError("save has an unexpired prior-preparation infused item")
    return states,items,set(consumed)

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
                "composition_cast_at_start": creature.composition_cast_at_start,
                "composition_cast_turn_actor_id": creature.composition_cast_turn_actor_id,
                "composition_cast_turn_start": creature.composition_cast_turn_start,
                "lingering_composition_pending": creature.lingering_composition_pending,
                "reach_spell_pending": creature.reach_spell_pending,
                "widen_spell_pending": creature.widen_spell_pending,
                "energy_ablation_pending": creature.energy_ablation_pending,
                "must_leave_occupied": creature.must_leave_occupied,
                "temporary_hp": creature.temporary_hp,
                "temporary_hp_source_id": creature.temporary_hp_source_id,
                "temporary_hp_expires_at_seconds": creature.temporary_hp_expires_at_seconds,
                "temporary_hp_expires_at_source_start": creature.temporary_hp_expires_at_source_start,
                "hunted_prey": creature.hunted_prey.target_actor_id if creature.hunted_prey else None,
                "precision_used_round": creature.precision_used_round,
                "arcane_bond_used_day": creature.arcane_bond_used_day,
                "arcane_bond_recast_until_start": creature.arcane_bond_recast_until_start,
                "arcane_bond_item_id": creature.arcane_bond_item_id,
                "arcane_bond_eligible_slots": sorted(creature.arcane_bond_eligible_slots),
                "spell_substitution": None if creature.spell_substitution is None else [
                    creature.spell_substitution.slot_id,
                    creature.spell_substitution.original_spell_id,
                    creature.spell_substitution.replacement_spell_id,
                    creature.spell_substitution.elapsed_seconds,
                ],
                "magic_shield_expires_at_start": creature.magic_shield_expires_at_start,
                "shield_recast_available_at_seconds": creature.shield_recast_available_at_seconds,
                "panache": creature.panache,
                "panache_expires_at_end": creature.panache_expires_at_end,
                "finisher_used_this_turn": creature.finisher_used_this_turn,
                "barbarian_state": _barbarian_state_to_data(creature.barbarian_state),
                "escape_lockout_until_start": creature.escape_lockout_until_start,
                "stunned": creature.stunned,
                "stunned_until_start": creature.stunned_until_start,
                "stunned_source_actor_id": creature.stunned_source_actor_id,
                "investigator_stratagem": stratagem_to_data(creature.investigator_stratagem),
                "investigator_knowledge_attempts": dict(sorted(creature.investigator_knowledge_attempts.items())),
                "investigator_knowledge_exhausted": sorted(creature.investigator_knowledge_exhausted),
                "investigator_examinations_completed": sorted(creature.investigator_examinations_completed),
                "investigator_active_cases": sorted(creature.investigator_active_cases),
                "investigator_solved_cases": sorted(creature.investigator_solved_cases),
                "investigator_abandoned_cases": sorted(creature.investigator_abandoned_cases),
                "investigator_awareness": sorted(creature.investigator_awareness),
                "investigator_lead_cooldown_until": creature.investigator_lead_cooldown_until,
                "investigator_clue_in_cooldown_until": creature.investigator_clue_in_cooldown_until,
                "investigator_person_of_interest": (
                    None if creature.investigator_person_of_interest is None else {
                        "target_id": creature.investigator_person_of_interest.target_id,
                        "expires_at_seconds": creature.investigator_person_of_interest.expires_at_seconds,
                    }
                ),
                "investigator_person_of_interest_cooldown_until": creature.investigator_person_of_interest_cooldown_until,
                "investigator_streetwise_recall_attempts": dict(sorted(creature.investigator_streetwise_recall_attempts.items())),
                "investigator_streetwise_gather_attempts": dict(sorted(creature.investigator_streetwise_gather_attempts.items())),
                "investigator_streetwise_results": dict(sorted(creature.investigator_streetwise_results.items())),
                "druid_animal_empathy_attempts": dict(sorted(creature.druid_animal_empathy_attempts.items())),
                "druid_animal_empathy_results": dict(sorted(creature.druid_animal_empathy_results.items())),
                "druid_animal_empathy_attitudes": dict(sorted(creature.druid_animal_empathy_attitudes.items())),
                "oracle_cursebound": creature.oracle_cursebound,
                "oracle_life_mode": creature.oracle_life_mode,
                "oracle_life_mode_selected_day": creature.oracle_life_mode_selected_day,
                "witch_patron_used_start": creature.witch_patron_used_start,
                "witch_restored_spirit_used_start": creature.witch_restored_spirit_used_start,
                "witch_hex_cast_start": creature.witch_hex_cast_start,
                "minion_commanded_start": creature.minion_commanded_start,
                "witch_turn_activity_start": creature.witch_turn_activity_start,
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
        "alchemy_states": {actor_id: _alchemy_state_to_data(value) for actor_id, value in sorted(state.alchemy_states.items())},
        "infused_alchemy_items": {item_id: _infused_item_to_data(value) for item_id, value in sorted(state.infused_alchemy_items.items())},
        "consumed_infused_item_ids": sorted(state.consumed_infused_item_ids),
        "raised_shields": {
            actor_id: [raised.instance_id, raised.expires_at_owner_start]
            for actor_id, raised in sorted((state.raised_shields or {}).items())
        },
        "martial_stances": {
            actor_id: [stance.stance_id, stance.entered_round]
            for actor_id, stance in sorted((state.martial_stances or {}).items())
        },
        "martial_stance_used_rounds": dict(sorted(state.martial_stance_used_rounds.items())),
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
        "overextending_feint_effects": [
            [
                effect.effect_id,
                effect.source_actor_id,
                effect.target_actor_id,
                [effect.expiration.anchor_actor_id, effect.expiration.boundary, effect.expiration.occurrence],
                effect.all_attacks,
            ]
            for effect in state.overextending_feint_effects
        ],
        "tumble_behind_exposures": [
            [
                effect.effect_id,
                effect.source_actor_id,
                effect.target_actor_id,
                [
                    effect.expiration.anchor_actor_id,
                    effect.expiration.boundary,
                    effect.expiration.occurrence,
                ],
            ]
            for effect in state.tumble_behind_exposures
        ],
        "world_time_seconds": state.world_time_seconds,
        "encounter_start_seconds": state.encounter_start_seconds,
        "active_effects": [
            [effect.effect_id, effect.kind, effect.source_actor_id,
             effect.target_actor_id, effect.value, effect.expires_at_source_start,
             effect.expires_at_world_time, effect.sustain_limit_source_start,
             effect.sustain_limit_world_time, effect.sustain_expires_at_source_end,
             effect.selected_enemy_actor_id, effect.life_link_used_round,
             effect.glue_removal_actions]
            for effect in state.active_effects
        ],
        "persistent_effects": [
            [effect.effect_id, effect.source_actor_id, effect.target_actor_id,
             effect.spell_id, effect.damage_type, list(effect.dice), effect.flat,
             effect.expires_at_world_time]
            for effect in state.persistent_effects
        ],
        "giant_centipede_venom_afflictions": [
            [effect.effect_id, effect.source_actor_id, effect.target_actor_id,
             effect.dc, effect.stage, effect.expires_at_world_time,
             effect.next_save_at_target_end]
            for effect in state.giant_centipede_venom_afflictions
        ],
        "active_item_effects": [
            [effect.effect_id, effect.kind, effect.source_actor_id, effect.item_id,
             effect.expires_at_source_start, effect.expires_at_world_time, effect.visible]
            for effect in state.active_item_effects
        ],
        "condition_effects": [
            [effect.effect_id, effect.kind, effect.source_actor_id,
             effect.target_actor_id, effect.value,
             [effect.expiration.anchor_actor_id, effect.expiration.boundary,
              effect.expiration.occurrence], effect.dc, effect.command_mode]
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


def _valid_alchemy_elixir_effect(
    row: list[Any], creatures: dict[str, CreatureState], starts: dict[str, int],
    world_time_seconds: int, infused_items: dict[str, Any], consumed_item_ids: set[str],
) -> bool:
    """Validate the finite Bomber elixir effects and their consumed origin."""
    from .alchemy_content import ElixirFacts, FORMULAS_BY_ID

    kind_to_formula = {
        "alchemy_elixir_of_life_minor": "elixir_of_life_minor",
        "alchemy_antidote_lesser": "antidote_lesser",
        "alchemy_antiplague_lesser": "antiplague_lesser",
        "alchemy_cheetahs_elixir_lesser": "cheetahs_elixir_lesser",
        "alchemy_bravos_brew_lesser": "bravos_brew_lesser",
    }
    formula_id = kind_to_formula[row[1]]
    formula = FORMULAS_BY_ID[formula_id]
    facts = formula.facts
    if not isinstance(facts, ElixirFacts) or facts.duration_seconds is None:
        return False
    expected_value = (
        facts.speed_bonus_ft
        if facts.effect == "speed_bonus"
        else facts.save_bonuses[0].bonus
        if facts.save_bonuses
        else None
    )
    if expected_value is None or expected_value <= 0:
        return False
    source = creatures[row[2]]
    target = creatures[row[3]]
    if (
        row[4] != expected_value
        or row[5] != starts[row[2]] + 1
        or type(row[6]) is not int
        or not world_time_seconds < row[6] <= world_time_seconds + facts.duration_seconds
        or row[0] not in {f"alchemy:{item_id}" for item_id in consumed_item_ids}
        or "bomber_alchemist" not in get_definition(source.definition_id).abilities
        or target.dead
    ):
        return False
    item_id = row[0].removeprefix("alchemy:")
    item = infused_items.get(item_id)
    if item is None or item.formula_id != formula_id or item.creator_actor_id != row[2]:
        return False
    maximum = 600 if item.creation_kind == "quick_alchemy" else facts.duration_seconds
    return row[6] <= world_time_seconds + maximum


def _valid_alchemy_bomb_rider_effect(
    row: list[Any], creatures: dict[str, CreatureState], starts: dict[str, int],
    world_time_seconds: int, infused_items: dict[str, Any], consumed_item_ids: set[str],
) -> bool:
    """Validate Glue Bomb's sourced minute-long rider and consumed origin."""
    from .alchemy_content import BombFacts, FORMULAS_BY_ID

    facts = FORMULAS_BY_ID["glue_bomb_lesser"].facts
    if not isinstance(facts, BombFacts):
        return False
    item_id = row[0].removeprefix("glue_bomb:")
    item = infused_items.get(item_id)
    source = creatures[row[2]]
    return (
        row[0].startswith("glue_bomb:")
        and row[1] == "alchemy_glue_bomb_lesser"
        and row[4] == facts.on_hit_effect_value == 10
        and row[12] in {0, 1, 2}
        and row[5] == starts[row[2]] + 1
        and type(row[6]) is int
        and world_time_seconds < row[6] <= world_time_seconds + (facts.on_hit_effect_duration_seconds or 0)
        and item_id in consumed_item_ids
        and item is not None
        and item.formula_id == "glue_bomb_lesser"
        and item.creator_actor_id == row[2]
        and "bomber_alchemist" in get_definition(source.definition_id).abilities
        and not creatures[row[3]].dead
    )


def _valid_bomber_bomb_condition_effect(
    effect: ActiveConditionEffect,
    creatures: dict[str, CreatureState],
    starts: dict[str, int],
    ends: dict[str, int],
    active_effects: list[ActiveSpellEffect],
) -> bool:
    """Validate the condition half of Dread/Glue's sourced rider state."""
    source = creatures.get(effect.source_actor_id)
    target = creatures.get(effect.target_actor_id)
    if source is None or target is None or "bomber_alchemist" not in get_definition(source.definition_id).abilities:
        return False
    if effect.kind == "frightened" and effect.effect_id.startswith("dread_ampoule:"):
        return (
            effect.value in {1, 2}
            and effect.expiration.anchor_actor_id == effect.target_actor_id
            and effect.expiration.boundary == "end"
            and effect.expiration.occurrence == ends[effect.target_actor_id] + effect.value
        )
    if effect.kind == "immobilized" and effect.effect_id.startswith("glue_bomb:"):
        glue_id = effect.effect_id.removesuffix(":immobilized")
        return (
            effect.value == 1
            and effect.dc == 17
            and effect.expiration.anchor_actor_id == effect.source_actor_id
            and effect.expiration.boundary == "start"
            and effect.expiration.occurrence == starts[effect.source_actor_id] + 1
            and any(
                current.effect_id == glue_id
                and current.kind == "alchemy_glue_bomb_lesser"
                and current.source_actor_id == effect.source_actor_id
                and current.target_actor_id == effect.target_actor_id
                for current in active_effects
            )
        )
    return True


def _valid_alchemy_mutagen_effect(
    row: list[Any], creatures: dict[str, CreatureState], starts: dict[str, int],
    world_time_seconds: int, infused_items: dict[str, Any], consumed_item_ids: set[str],
) -> bool:
    from .alchemy_content import FORMULAS_BY_ID, MutagenFacts
    formula_id = row[1].removeprefix("alchemy_")
    formula = FORMULAS_BY_ID.get(formula_id)
    if formula is None or not isinstance(formula.facts, MutagenFacts):
        return False
    item_id = row[0].removeprefix("alchemy:")
    item = infused_items.get(item_id)
    source = creatures[row[2]]
    valid = (
        row[0] == f"alchemy:{item_id}" and row[3] == row[2] and row[4] == 1
        and row[5] == starts[row[2]] + 1 and type(row[6]) is int
        and world_time_seconds < row[6] <= world_time_seconds + formula.facts.duration_seconds
        and item_id in consumed_item_ids and item is not None
        and item.formula_id == formula_id and item.creator_actor_id == row[2]
        and "bomber_alchemist" in get_definition(source.definition_id).abilities
    )
    if not valid:
        return False
    if formula_id == "juggernaut_mutagen_lesser" and source.temporary_hp_source_id == row[0]:
        return (
            0 < source.temporary_hp <= formula.facts.temporary_hp
            and source.temporary_hp_expires_at_seconds == row[6]
            and source.temporary_hp_expires_at_source_start == 0
        )
    return True


def _valid_alchemy_venom_coating(
    row: list[Any], creatures: dict[str, CreatureState], starts: dict[str, int],
    world_time_seconds: int, infused_items: dict[str, Any], consumed_item_ids: set[str],
) -> bool:
    item_id = row[0].removeprefix("alchemy:")
    item = infused_items.get(item_id)
    source = creatures[row[2]]
    return (
        row[0] == f"alchemy:{item_id}" and row[2] == row[3] and row[4] == 17
        and row[5] == starts[row[2]] + 1 and type(row[6]) is int
        and world_time_seconds < row[6] <= world_time_seconds + 36
        and item_id in consumed_item_ids and item is not None
        and item.formula_id == "giant_centipede_venom" and item.creator_actor_id == row[2]
        and "bomber_alchemist" in get_definition(source.definition_id).abilities
    )


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

    alchemy_states, infused_alchemy_items, consumed_infused_item_ids = _load_alchemy_records(data, setup)
    initial_item_instances: dict[str, ItemInstance] = {}
    for placement in setup.placements:
        for item in get_definition(placement.definition_id).item_instances:
            instance_id = runtime_item_instance_id(placement.actor_id, item.instance_id)
            if instance_id in initial_item_instances:
                raise ValueError("setup has duplicate stable item identities")
            initial_item_instances[instance_id] = replace(item, instance_id=instance_id)
    item_instances_raw = data.get("item_instances", {})
    expected_item_ids = set(initial_item_instances) | (set(infused_alchemy_items) - set(initial_item_instances))
    if not isinstance(item_instances_raw, dict) or set(item_instances_raw) != expected_item_ids:
        raise ValueError("save has invalid stable or infused item instances")
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
    for instance_id, infused in infused_alchemy_items.items():
        if instance_id in initial_item_instances:
            continue
        raw_item = item_instances_raw[instance_id]
        if not isinstance(raw_item, dict):
            raise ValueError("save has invalid infused item instance")
        try:
            instance = ItemInstance(instance_id, _required_str(raw_item, "definition_id"), _required_int(raw_item, "quantity"), raw_item.get("charges"), raw_item.get("hp"), tuple(_required_str_list(raw_item, "rune_ids")), _required_bool(raw_item, "invested"))
        except (TypeError, ValueError) as error:
            raise ValueError("save has invalid infused item instance") from error
        if instance.definition_id != infused.formula_id or instance.quantity != 1 or instance.charges is not None or instance.hp is not None or instance.rune_ids or instance.invested:
            raise ValueError("save changed infused item identity or quantity")
        item_instances[instance_id] = instance

    saved_starts_for_initiative = data.get("actor_start_counts", {})
    saved_effects_for_initiative = data.get("active_effects", [])

    def saved_juggernaut_penalty(actor_id: str) -> int:
        if not isinstance(saved_starts_for_initiative, dict) or not isinstance(saved_effects_for_initiative, list):
            return 0
        for row in saved_effects_for_initiative:
            if (
                isinstance(row, list)
                and len(row) >= 7
                and row[1] == "alchemy_juggernaut_mutagen_lesser"
                and row[3] == actor_id
                and isinstance(row[2], str)
                and type(row[5]) is int
                and row[5] > saved_starts_for_initiative.get(row[2], 0)
                and type(row[6]) is int
                and row[6] > world_time_seconds
            ):
                return 2
        return 0

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
        if definition.initiative_exempt:
            if initiative != 0:
                raise ValueError(f"saved familiar {actor_id!r} has an initiative")
        elif not initiative_modifier - saved_juggernaut_penalty(actor_id) + 1 <= initiative <= initiative_modifier + 20:
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
        composition_cast_at_start = _required_int(raw, "composition_cast_at_start")
        composition_cast_turn_actor_id = raw.get("composition_cast_turn_actor_id")
        composition_cast_turn_start = raw.get("composition_cast_turn_start", 0)
        if (
            composition_cast_turn_actor_id is not None
            and (not isinstance(composition_cast_turn_actor_id, str) or not composition_cast_turn_actor_id)
        ) or type(composition_cast_turn_start) is not int or composition_cast_turn_start < 0:
            raise ValueError(f"saved actor {actor_id!r} has invalid composition turn marker")
        lingering_composition_pending = _required_bool(raw, "lingering_composition_pending")
        reach_spell_pending = raw.get("reach_spell_pending", False)
        if type(reach_spell_pending) is not bool:
            raise ValueError(f"saved actor {actor_id!r} has invalid Reach Spell state")
        widen_spell_pending = raw.get("widen_spell_pending", False)
        if type(widen_spell_pending) is not bool:
            raise ValueError(f"saved actor {actor_id!r} has invalid Widen Spell state")
        energy_ablation_pending = raw.get("energy_ablation_pending")
        if energy_ablation_pending is not None and energy_ablation_pending not in {"acid", "cold", "electricity", "fire", "force", "sonic", "vitality", "void"}:
            raise ValueError(f"saved actor {actor_id!r} has invalid Energy Ablation state")
        must_leave_occupied = _required_bool(raw, "must_leave_occupied")
        temporary_hp = _required_int(raw, "temporary_hp")
        temporary_hp_source_id = raw.get("temporary_hp_source_id")
        temporary_hp_expires_at_seconds = raw.get("temporary_hp_expires_at_seconds")
        temporary_hp_expires_at_source_start = raw.get("temporary_hp_expires_at_source_start", 0)
        hunted_target_id = raw.get("hunted_prey")
        precision_used_round = _required_int(raw, "precision_used_round")
        # These Wizard-only fields were added without a save-version bump.
        # Older v17 saves therefore decode to the inert state.
        arcane_bond_used_day = raw.get("arcane_bond_used_day", 0)
        arcane_bond_recast_until_start = raw.get("arcane_bond_recast_until_start", 0)
        arcane_bond_item_id = raw.get("arcane_bond_item_id")
        arcane_bond_eligible_slots = raw.get("arcane_bond_eligible_slots", [])
        substitution_raw = raw.get("spell_substitution")
        if substitution_raw is None:
            spell_substitution = None
        elif (
            isinstance(substitution_raw, list)
            and len(substitution_raw) == 4
            and all(isinstance(value, str) and value for value in substitution_raw[:3])
            and type(substitution_raw[3]) is int
            and 0 <= substitution_raw[3] < 600
        ):
            spell_substitution = SpellSubstitutionState(*substitution_raw)
        else:
            raise ValueError(f"saved actor {actor_id!r} has invalid Spell Substitution progress")
        magic_shield_expires_at_start = raw.get("magic_shield_expires_at_start", 0)
        shield_recast_available_at_seconds = raw.get("shield_recast_available_at_seconds", 0)
        if (
            type(arcane_bond_used_day) is not int
            or type(arcane_bond_recast_until_start) is not int
            or arcane_bond_used_day < 0
            or arcane_bond_recast_until_start < 0
            or (arcane_bond_item_id is not None and not isinstance(arcane_bond_item_id, str))
            or not isinstance(arcane_bond_eligible_slots, list)
            or any(not isinstance(item, str) or not item for item in arcane_bond_eligible_slots)
            or type(magic_shield_expires_at_start) is not int or magic_shield_expires_at_start < 0
            or type(shield_recast_available_at_seconds) is not int or shield_recast_available_at_seconds < 0
            or len(set(arcane_bond_eligible_slots)) != len(arcane_bond_eligible_slots)
        ):
            raise ValueError(f"saved actor {actor_id!r} has invalid Arcane Bond state")
        panache = raw.get("panache", False)
        panache_expires_at_end = raw.get("panache_expires_at_end")
        finisher_used_this_turn = raw.get("finisher_used_this_turn", False)
        escape_lockout_until_start = _required_int(raw, "escape_lockout_until_start")
        stunned = raw.get("stunned", 0)
        stunned_until_start = raw.get("stunned_until_start", 0)
        stunned_source_actor_id = raw.get("stunned_source_actor_id")
        if (
            type(stunned) is not int or stunned < 0
            or type(stunned_until_start) is not int or stunned_until_start < 0
            or (stunned_source_actor_id is not None and (
                not isinstance(stunned_source_actor_id, str) or not stunned_source_actor_id
            ))
        ):
            raise ValueError(f"saved actor {actor_id!r} has invalid Stunning Blows state")
        barbarian_state = _barbarian_state_from_data(raw.get("barbarian_state"))
        investigator_stratagem = stratagem_from_data(raw.get("investigator_stratagem"))
        knowledge_attempts_raw = raw.get("investigator_knowledge_attempts", {})
        knowledge_exhausted_raw = raw.get("investigator_knowledge_exhausted", [])
        examinations_completed_raw = raw.get("investigator_examinations_completed", [])
        active_cases_raw = raw.get("investigator_active_cases", [])
        solved_cases_raw = raw.get("investigator_solved_cases", [])
        abandoned_cases_raw = raw.get("investigator_abandoned_cases", [])
        awareness_raw = raw.get("investigator_awareness", [])
        lead_cooldown_until = raw.get("investigator_lead_cooldown_until", 0)
        clue_in_cooldown_until = raw.get("investigator_clue_in_cooldown_until", 0)
        person_of_interest_raw = raw.get("investigator_person_of_interest")
        person_of_interest_cooldown_until = raw.get(
            "investigator_person_of_interest_cooldown_until", 0
        )
        if person_of_interest_raw is None:
            person_of_interest = None
        elif (
            isinstance(person_of_interest_raw, dict)
            and set(person_of_interest_raw) == {"target_id", "expires_at_seconds"}
        ):
            person_of_interest = PersonOfInterestState(
                person_of_interest_raw["target_id"],
                person_of_interest_raw["expires_at_seconds"],
            )
            try:
                validate_person_of_interest_state(person_of_interest)
            except ValueError as error:
                raise ValueError(
                    f"saved actor {actor_id!r} has invalid Person of Interest state"
                ) from error
            if (
                definition.class_name != "Investigator"
                or (
                    PERSON_OF_INTEREST_ABILITY not in definition.abilities
                    and "Person of Interest" not in definition.feats
                )
            ):
                raise ValueError(
                    f"saved actor {actor_id!r} has Person of Interest state outside its admitted build"
                )
            if (
                type(person_of_interest_cooldown_until) is not int
                or person_of_interest_cooldown_until < 0
                or person_of_interest_cooldown_until
                != person_of_interest.expires_at_seconds
                + (PERSON_OF_INTEREST_COOLDOWN_SECONDS - PERSON_OF_INTEREST_DURATION_SECONDS)
            ):
                raise ValueError(
                    f"saved actor {actor_id!r} has inconsistent Person of Interest cooldown"
                )
            if (
                person_of_interest.expires_at_seconds > world_time_seconds
                and person_of_interest.expires_at_seconds
                > world_time_seconds + PERSON_OF_INTEREST_DURATION_SECONDS
            ):
                raise ValueError(
                    f"saved actor {actor_id!r} has an overlong Person of Interest grant"
                )
            # Absolute duration ends at this exact boundary; restoring a save
            # after it has elapsed clears only the grant, never its separate
            # ten-minute frequency.
            if person_of_interest.expires_at_seconds <= world_time_seconds:
                person_of_interest = None
        else:
            raise ValueError(f"saved actor {actor_id!r} has invalid Person of Interest state")
        streetwise_recall_raw = raw.get("investigator_streetwise_recall_attempts", {})
        streetwise_gather_raw = raw.get("investigator_streetwise_gather_attempts", {})
        streetwise_results_raw = raw.get("investigator_streetwise_results", {})
        animal_empathy_attempts_raw = raw.get("druid_animal_empathy_attempts", {})
        animal_empathy_results_raw = raw.get("druid_animal_empathy_results", {})
        animal_empathy_attitudes_raw = raw.get("druid_animal_empathy_attitudes", {})
        oracle_cursebound = raw.get("oracle_cursebound", 0)
        oracle_life_mode = raw.get("oracle_life_mode", "life")
        oracle_life_mode_selected_day = raw.get("oracle_life_mode_selected_day", 0)
        witch_patron_used_start = raw.get("witch_patron_used_start", 0)
        witch_restored_spirit_used_start = raw.get("witch_restored_spirit_used_start", 0)
        witch_hex_cast_start = raw.get("witch_hex_cast_start", 0)
        minion_commanded_start = raw.get("minion_commanded_start", 0)
        witch_turn_activity_start = raw.get("witch_turn_activity_start", 0)
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
                or not isinstance(active_cases_raw, list)
                or any(not isinstance(case_id, str) or not case_id for case_id in active_cases_raw)
                or len(set(active_cases_raw)) != len(active_cases_raw)
                or not isinstance(solved_cases_raw, list)
                or any(not isinstance(case_id, str) or not case_id for case_id in solved_cases_raw)
                or len(set(solved_cases_raw)) != len(solved_cases_raw)
                or not set(solved_cases_raw).issubset(set(active_cases_raw))
                or not isinstance(abandoned_cases_raw, list)
                or any(not isinstance(case_id, str) or not case_id for case_id in abandoned_cases_raw)
                or len(set(abandoned_cases_raw)) != len(abandoned_cases_raw)
                or set(active_cases_raw) & set(abandoned_cases_raw)
                or not isinstance(awareness_raw, list)
                or any(not isinstance(actor_ref, str) or not actor_ref for actor_ref in awareness_raw)
                or len(set(awareness_raw)) != len(awareness_raw)
                or type(lead_cooldown_until) is not int or lead_cooldown_until < 0
            or type(clue_in_cooldown_until) is not int or clue_in_cooldown_until < 0
            or type(person_of_interest_cooldown_until) is not int
            or person_of_interest_cooldown_until < 0
            or any(
                not isinstance(values, dict)
                or any(not isinstance(key, str) or not key or type(count) is not int or count < 0
                       for key, count in values.items())
                for values in (streetwise_recall_raw, streetwise_gather_raw)
            )
            or not isinstance(streetwise_results_raw, dict)
            or any(not isinstance(key, str) or not key or not isinstance(value, str) or not value
                   for key, value in streetwise_results_raw.items())
            or not isinstance(animal_empathy_attempts_raw, dict)
            or any(not isinstance(key, str) or not key or type(value) is not int or value < 0
                   for key, value in animal_empathy_attempts_raw.items())
            or not isinstance(animal_empathy_results_raw, dict)
            or any(not isinstance(key, str) or not key or not isinstance(value, str) or not value
                   for key, value in animal_empathy_results_raw.items())
            or not isinstance(animal_empathy_attitudes_raw, dict)
            or any(not isinstance(key, str) or not key or value not in {"hostile", "unfriendly", "indifferent", "friendly", "helpful"}
                   for key, value in animal_empathy_attitudes_raw.items())
            ):
            raise ValueError(f"saved actor {actor_id!r} has invalid Investigator knowledge state")
        if temporary_hp_source_id is not None and (
            not isinstance(temporary_hp_source_id, str) or not temporary_hp_source_id
        ):
            raise ValueError(f"saved actor {actor_id!r} has invalid temporary HP source")
        if type(oracle_cursebound) is not int or not 0 <= oracle_cursebound <= 2 or oracle_life_mode not in {"life", "death"} or type(oracle_life_mode_selected_day) is not int or oracle_life_mode_selected_day < 0:
            raise ValueError(f"saved actor {actor_id!r} has invalid Oracle state")
        if (
            type(witch_patron_used_start) is not int or witch_patron_used_start < 0
            or type(witch_restored_spirit_used_start) is not int
            or witch_restored_spirit_used_start < 0
            or type(witch_hex_cast_start) is not int or witch_hex_cast_start < 0
            or type(minion_commanded_start) is not int or minion_commanded_start < 0
            or type(witch_turn_activity_start) is not int or witch_turn_activity_start < 0
        ):
            raise ValueError(f"saved actor {actor_id!r} has invalid Witch patron gate")
        if temporary_hp_expires_at_seconds is not None and (
            type(temporary_hp_expires_at_seconds) is not int or temporary_hp_expires_at_seconds < 0
        ):
            raise ValueError(f"saved actor {actor_id!r} has invalid temporary HP expiry")
        if type(temporary_hp_expires_at_source_start) is not int or temporary_hp_expires_at_source_start < 0:
            raise ValueError(f"saved actor {actor_id!r} has invalid temporary HP source expiry")
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
        variable_preparations = has_variable_preparations(definition)
        for saved_slot, definition_slot in zip(prepared_slots, expected_slots):
            if variable_preparations:
                valid_facts = (
                    (saved_slot.slot_id, saved_slot.source, saved_slot.rank, saved_slot.cantrip)
                    == (definition_slot.slot_id, definition_slot.source, definition_slot.rank, definition_slot.cantrip)
                )
            else:
                valid_facts = (
                    (saved_slot.slot_id, saved_slot.source, saved_slot.spell_id,
                     saved_slot.rank, saved_slot.cantrip)
                    == (definition_slot.slot_id, definition_slot.source, definition_slot.spell_id,
                        definition_slot.rank, definition_slot.cantrip)
                )
            if not valid_facts or saved_slot.cantrip and saved_slot.spent:
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
        if variable_preparations and any(
            prepared_slot_rejection(None, definition, slot, slot.spell_id) is not None
            for slot in prepared_slots
        ):
            raise ValueError(f"saved actor {actor_id!r} has prepared spells outside finite choices")
        if health_mode is HealthMode.PC:
            if (dead and (hp != 0 or dying != 0 or unconscious)) or (hp == 0 and not unconscious and not dead):
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
                {"reactive_strike", "shield_block", "shield_cantrip", "no_escape"} & set(definition.abilities)
                or "Nimble Dodge" in definition.feats
                or "investigator_on_the_case" in definition.abilities
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
            composition_cast_at_start=composition_cast_at_start,
            composition_cast_turn_actor_id=composition_cast_turn_actor_id,
            composition_cast_turn_start=composition_cast_turn_start,
            lingering_composition_pending=lingering_composition_pending,
            reach_spell_pending=reach_spell_pending,
            widen_spell_pending=widen_spell_pending,
            energy_ablation_pending=energy_ablation_pending,
            must_leave_occupied=must_leave_occupied,
            temporary_hp=temporary_hp,
            temporary_hp_source_id=temporary_hp_source_id,
            temporary_hp_expires_at_seconds=temporary_hp_expires_at_seconds,
            temporary_hp_expires_at_source_start=temporary_hp_expires_at_source_start,
            hunted_prey=HuntedPreyState(hunted_target_id) if hunted_target_id is not None else None,
            precision_used_round=precision_used_round,
            arcane_bond_used_day=arcane_bond_used_day,
            arcane_bond_recast_until_start=arcane_bond_recast_until_start,
            arcane_bond_item_id=arcane_bond_item_id,
            arcane_bond_eligible_slots=set(arcane_bond_eligible_slots),
            spell_substitution=spell_substitution,
            magic_shield_expires_at_start=magic_shield_expires_at_start,
            shield_recast_available_at_seconds=shield_recast_available_at_seconds,
            panache=panache,
            panache_expires_at_end=panache_expires_at_end,
            finisher_used_this_turn=finisher_used_this_turn,
            barbarian_state=barbarian_state,
            escape_lockout_until_start=escape_lockout_until_start,
            stunned=stunned,
            stunned_until_start=stunned_until_start,
            stunned_source_actor_id=stunned_source_actor_id,
            investigator_stratagem=investigator_stratagem,
            investigator_knowledge_attempts=dict(knowledge_attempts_raw),
            investigator_knowledge_exhausted=set(knowledge_exhausted_raw),
            investigator_examinations_completed=set(examinations_completed_raw),
            investigator_active_cases=set(active_cases_raw),
            investigator_solved_cases=set(solved_cases_raw),
            investigator_abandoned_cases=set(abandoned_cases_raw),
            investigator_awareness=set(awareness_raw),
            investigator_lead_cooldown_until=lead_cooldown_until,
            investigator_clue_in_cooldown_until=clue_in_cooldown_until,
            investigator_person_of_interest=person_of_interest,
            investigator_person_of_interest_cooldown_until=person_of_interest_cooldown_until,
            investigator_streetwise_recall_attempts=dict(streetwise_recall_raw),
            investigator_streetwise_gather_attempts=dict(streetwise_gather_raw),
            investigator_streetwise_results=dict(streetwise_results_raw),
            druid_animal_empathy_attempts=dict(animal_empathy_attempts_raw),
            druid_animal_empathy_results=dict(animal_empathy_results_raw),
            druid_animal_empathy_attitudes=dict(animal_empathy_attitudes_raw),
            oracle_cursebound=oracle_cursebound,
            oracle_life_mode=oracle_life_mode,
            oracle_life_mode_selected_day=oracle_life_mode_selected_day,
            witch_patron_used_start=witch_patron_used_start,
            witch_restored_spirit_used_start=witch_restored_spirit_used_start,
            witch_hex_cast_start=witch_hex_cast_start,
            minion_commanded_start=minion_commanded_start,
            witch_turn_activity_start=witch_turn_activity_start,
        )
        if barbarian_state is not None and definition.class_name != "Barbarian":
            raise ValueError(f"saved actor {actor_id!r} has Barbarian state on another class")
        if (definition.class_name == "Barbarian") != (barbarian_state is not None):
            raise ValueError(f"saved actor {actor_id!r} has missing or unexpected Barbarian state")
        if barbarian_state is not None:
            from .barbarian_content import BARBARIAN_INITIAL_STATES

            # The admitted level-two Bear sheets add a feat to the accepted
            # level-one build; they deliberately retain its literal instinct
            # state rather than introducing another selectable Barbarian
            # state.
            canonical = BARBARIAN_INITIAL_STATES.get(
                definition_id,
                BARBARIAN_INITIAL_STATES.get("barbarian_animal_bear")
                if definition_id in {
                    "barbarian_animal_bear_level_2_no_escape",
                    "barbarian_animal_bear_level_2_sudden_charge",
                    "barbarian_animal_bear_level_2_intimidating_strike",
                }
                else None,
            )
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
        if person_of_interest is not None and (
            definition.class_name != "Investigator"
            or (
                PERSON_OF_INTEREST_ABILITY not in definition.abilities
                and "Person of Interest" not in definition.feats
            )
        ):
            raise ValueError(
                f"saved actor {actor_id!r} has Person of Interest state outside its admitted build"
            )
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
                familiar_share = (
                    get_definition(first.definition_id).initiative_exempt
                    and get_definition(first.definition_id).size == "tiny"
                    and first.team == second.team
                ) or (
                    get_definition(second.definition_id).initiative_exempt
                    and get_definition(second.definition_id).size == "tiny"
                    and first.team == second.team
                )
                if not downed_share and not living_ally_share and not familiar_share:
                    raise ValueError("saved actors occupy an unsupported shared space")

    initiative_order = data.get("initiative_order")
    initiative_ids = {
        actor_id for actor_id, creature in creatures.items()
        if not get_definition(creature.definition_id).initiative_exempt
    }
    if (
        not isinstance(initiative_order, list)
        or any(not isinstance(actor_id, str) for actor_id in initiative_order)
        or (initiative_order and (set(initiative_order) != initiative_ids or len(initiative_order) != len(initiative_ids)))
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
                creature.hunted_prey.target_actor_id == creature.actor_id
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
        "investigator:streetwise:recall:hero_point",
        "investigator:streetwise:gather:hero_point",
    }:
        raise ValueError("finished encounters cannot retain choices")
    if initiative_finalized and len(initiative_order) != len(initiative_ids):
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
        if pending_choice.kind == "initiative_tie" and len(initiative_order) != len(initiative_ids):
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
        if pending_choice is None and not (active_creature.unconscious or active_creature.dead) and not 0 <= active_creature.actions_remaining <= 3:
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
        flurry_extra_strike = (
            "flurry_of_blows" in get_definition(active_creature.definition_id).abilities
            and active_creature.strikes_this_turn == used_actions + 1
        )
        if active_creature.strikes_this_turn > used_actions and not flurry_extra_strike:
            raise ValueError("saved attack count exceeds actions spent this turn")
        movement_actions = max(0, used_actions - active_creature.strikes_this_turn)
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
    if any(count != 1 and not (count == 0 and instance_id in consumed_infused_item_ids) for instance_id, count in instance_locations.items()):
        raise ValueError("save loses or duplicates a stable item instance")

    starts_raw = data.get("actor_start_counts")
    if (
        not isinstance(starts_raw, dict)
        or set(starts_raw) != expected_ids
        or any(type(value) is not int or value < 0 for value in starts_raw.values())
    ):
        raise ValueError("save has invalid actor start counters")
    for actor_id, creature in creatures.items():
        if creature.stunned:
            source = creatures.get(creature.stunned_source_actor_id or "")
            source_definition = get_definition(source.definition_id) if source is not None else None
            stunning_blows = (
                source_definition is not None
                and "stunning_blows" in source_definition.abilities
                and creature.stunned in {1, 3}
            )
            daze = (
                source is not None
                and creature.stunned == 1
                and any(slot.spell_id == "daze" and slot.cantrip for slot in source.prepared_slots)
            )
            if (
                not (stunning_blows or daze)
                or creature.stunned_until_start != starts_raw[actor_id] + 1
            ):
                raise ValueError(f"saved actor {actor_id!r} has invalid admitted stunned state")
        elif creature.stunned_until_start or creature.stunned_source_actor_id is not None:
            raise ValueError(f"saved actor {actor_id!r} has stale admitted stunned state")
    ends_raw = data.get("actor_end_counts")
    if (
        not isinstance(ends_raw, dict)
        or set(ends_raw) != expected_ids
        or any(type(value) is not int or value < 0 for value in ends_raw.values())
    ):
        raise ValueError("save has invalid actor end counters")
    if any(
        creature.composition_cast_at_start < 0
        or creature.composition_cast_at_start > starts_raw[actor_id]
        or (
            creature.composition_cast_at_start
            and (
                get_definition(creature.definition_id).class_name != "Bard"
                or "courageous_anthem" not in get_definition(creature.definition_id).abilities
            )
        )
        for actor_id, creature in creatures.items()
    ):
        raise ValueError("save has invalid composition turn marker")
    if any(
        (creature.composition_cast_turn_actor_id is None) != (creature.composition_cast_turn_start == 0)
        or (
            creature.composition_cast_turn_actor_id is not None
            and (
                creature.composition_cast_turn_actor_id not in expected_ids
                or creature.composition_cast_turn_start > starts_raw[creature.composition_cast_turn_actor_id]
            )
        )
        for creature in creatures.values()
    ):
        raise ValueError("save has invalid composition actual-turn marker")
    if any(
        creature.lingering_composition_pending
        and (
            get_definition(creature.definition_id).class_name != "Bard"
            or "lingering_composition" not in get_definition(creature.definition_id).abilities
            # A later turn can legitimately start Lingering with fewer than a
            # full pool.  Its pending spellshape proves only that one point
            # was spent, so zero through capacity-minus-one are valid.
            or not 0 <= creature.focus_points < creature.focus_capacity
        )
        for creature in creatures.values()
    ):
        raise ValueError("save has invalid Lingering Composition spellshape state")
    for creature in creatures.values():
        if sum(bool(marker) for marker in (creature.reach_spell_pending, creature.widen_spell_pending, creature.energy_ablation_pending is not None)) > 1:
            raise ValueError("save has overlapping spellshape markers")
        if creature.reach_spell_pending:
            definition = get_definition(creature.definition_id)
            if (
                "reach_spell" not in definition.abilities
                or "Reach Spell" not in definition.feats
                or not in_progress
                or not initiative_finalized
                or active_actor_id != creature.actor_id
                # Reach Spell is a one-action activity. Its saved marker must
                # prove that action has already been committed, but can remain
                # at zero actions until the current turn ends.
                or not 0 <= creature.actions_remaining <= 2
            ):
                raise ValueError("save has invalid Reach Spell spellshape state")
        if creature.widen_spell_pending:
            definition = get_definition(creature.definition_id)
            if (
                "widen_spell" not in definition.abilities
                or "Widen Spell" not in definition.feats
                or not in_progress
                or not initiative_finalized
                or active_actor_id != creature.actor_id
                # Widen Spell is a one-action activity. Its saved marker must
                # prove that action has already been committed, but can remain
                # at zero actions until the current turn ends.
                or not 0 <= creature.actions_remaining <= 2
            ):
                raise ValueError("save has invalid Widen Spell spellshape state")
        if creature.energy_ablation_pending is not None:
            definition = get_definition(creature.definition_id)
            if (
                "energy_ablation" not in definition.abilities
                or "Energy Ablation" not in definition.feats
                or not in_progress
                or not initiative_finalized
                or active_actor_id != creature.actor_id
                or creature.actions_remaining < 0
            ):
                raise ValueError("save has invalid Energy Ablation spellshape state")
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
        if stratagem.mode not in {None, ATTACK_STRATAGEM, SKILL_STRATAGEM}:
            raise ValueError(f"saved actor {actor_id!r} has an unsupported Investigator stratagem mode")
        if stratagem.mode is None and (
            pending_choice is None
            or pending_choice.procedure_id != "investigator:devise_stratagem:mode"
            or pending_choice.actor_id != actor_id
        ):
            raise ValueError(f"saved actor {actor_id!r} has an unfinished Investigator stratagem without its choice")
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
    overextending_effects_raw = data.get("overextending_feint_effects", [])
    if not isinstance(overextending_effects_raw, list):
        raise ValueError("save has invalid Overextending Feint effects")
    from .skill_actions import OverextendingFeintEffect

    overextending_effects: list[OverextendingFeintEffect] = []
    overextending_ids: set[str] = set()
    for row in overextending_effects_raw:
        if (
            not isinstance(row, list) or len(row) != 5
            or any(not isinstance(value, str) or not value for value in row[:3])
            or not isinstance(row[3], list) or len(row[3]) != 3
            or row[3][0] not in expected_ids or row[3][1] != "end"
            or type(row[3][2]) is not int or row[3][2] < 1
            or type(row[4]) is not bool or row[0] in overextending_ids
            or row[1] not in expected_ids or row[2] not in expected_ids
            or row[1] == row[2]
        ):
            raise ValueError("save has invalid Overextending Feint effect")
        try:
            expiration = EffectExpiration(row[3][0], row[3][1], row[3][2])
            effect = OverextendingFeintEffect(row[0], row[1], row[2], expiration, row[4])
        except (TypeError, ValueError) as error:
            raise ValueError("save has invalid Overextending Feint effect") from error
        if expiration.occurrence <= ends_raw[expiration.anchor_actor_id]:
            raise ValueError("save retains an expired Overextending Feint effect")
        overextending_ids.add(effect.effect_id)
        overextending_effects.append(effect)
    tumble_effects_raw = data.get("tumble_behind_exposures", [])
    if not isinstance(tumble_effects_raw, list):
        raise ValueError("save has invalid Tumble Behind exposures")
    from .movement_progression import TumbleBehindExposure

    tumble_effects: list[TumbleBehindExposure] = []
    tumble_effect_ids: set[str] = set()
    for row in tumble_effects_raw:
        if (
            not isinstance(row, list) or len(row) != 4
            or any(not isinstance(value, str) or not value for value in row[:3])
            or not isinstance(row[3], list) or len(row[3]) != 3
            or not isinstance(row[3][0], str) or not row[3][0]
            or row[3][1] != "end"
            or type(row[3][2]) is not int or row[3][2] < 1
            or row[0] in tumble_effect_ids
            or row[1] not in expected_ids or row[2] not in expected_ids
            or row[3][0] not in expected_ids
        ):
            raise ValueError("save has invalid Tumble Behind exposure")
        try:
            expiration = EffectExpiration(row[3][0], row[3][1], row[3][2])
            effect = TumbleBehindExposure(row[0], row[1], row[2], expiration)
        except (TypeError, ValueError) as error:
            raise ValueError("save has invalid Tumble Behind exposure") from error
        if expiration.occurrence <= ends_raw[expiration.anchor_actor_id]:
            raise ValueError("save retains an expired Tumble Behind exposure")
        source_definition = get_definition(creatures[row[1]].definition_id)
        if (
            "Tumble Behind" not in source_definition.feats
            or expiration.anchor_actor_id != row[1]
            or expiration.occurrence != ends_raw[row[1]] + 1
            or not in_progress
            or not initiative_order
            or initiative_order[active_index] != row[1]
            or creatures[row[1]].team == creatures[row[2]].team
        ):
            raise ValueError("save has forged or off-schedule Tumble Behind exposure")
        tumble_effect_ids.add(effect.effect_id)
        tumble_effects.append(effect)
    effects_raw = data.get("active_effects")
    if not isinstance(effects_raw, list):
        raise ValueError("save has invalid active spell effects")
    effects: list[ActiveSpellEffect] = []
    active_effect_ids: set[str] = set()
    blood_magic_sources: set[str] = set()
    halo_sources: set[str] = set()
    anthem_pairs: set[tuple[str, str]] = set()
    sure_strike_sources: set[str] = set()
    soothe_pairs: set[tuple[str, str]] = set()
    protection_pairs: set[tuple[str, str]] = set()
    fleeing_pairs: set[tuple[str, str]] = set()
    life_link_sources: set[str] = set()
    dueling_parry_sources: set[str] = set()
    for raw_row in effects_raw:
        # v17 saves before sustained-spell clocks stored the original seven
        # fields.  The appended Link round marker preserves all prior rows.
        if not isinstance(raw_row, list):
            raise ValueError("save has invalid active spell effect")
        if len(raw_row) == 7:
            row = [*raw_row, 0, None, 0, None, 0, 0]
        elif len(raw_row) == 9:
            row = [*raw_row, 0, None, 0, 0]
        elif len(raw_row) == 10:
            row = [*raw_row, None, 0, 0]
        elif len(raw_row) == 11:
            row = [*raw_row, 0, 0]
        elif len(raw_row) == 12:
            row = [*raw_row, 0]
        elif len(raw_row) == 13:
            row = raw_row
        else:
            raise ValueError("save has invalid active spell effect")
        if (
            any(not isinstance(value, str) or not value for value in row[:4])
            or type(row[4]) is not int or type(row[5]) is not int
            or row[4] < 1 or row[5] < 1
            or type(row[7]) is not int or row[7] < 0
            or (row[8] is not None and type(row[8]) is not int)
            or type(row[9]) is not int or row[9] < 0
            or (row[10] is not None and (not isinstance(row[10], str) or not row[10]))
            or type(row[11]) is not int or row[11] < 0
            or type(row[12]) is not int or row[12] < 0
            or row[1] not in {"guidance", "enfeebled", "frostbite_weakness", "runic_body", "blood_magic", "angelic_halo", "courageous_anthem", "fleeing", "sure_strike", "soothe", "protection", "lay_on_hands_ac", "stoke_the_heart", "forbidding_ward", "life_link", "sigil", "dueling_parry", "energy_ablation", "weapon_surge", "alchemy_elixir_of_life_minor", "alchemy_antidote_lesser", "alchemy_antiplague_lesser", "alchemy_cheetahs_elixir_lesser", "alchemy_bravos_brew_lesser", "alchemy_bestial_mutagen_lesser", "alchemy_cognitive_mutagen_lesser", "alchemy_juggernaut_mutagen_lesser", "alchemy_giant_centipede_venom_coating", "alchemy_glue_bomb_lesser"}
            or row[2] not in expected_ids or row[3] not in expected_ids
            or (row[10] is not None and row[10] not in expected_ids)
            or row[0] in active_effect_ids
            or row[5] <= starts_raw[row[2]]
            or (row[6] is not None and type(row[6]) is not int)
            or (
                row[1] not in {"guidance", "enfeebled", "frostbite_weakness", "runic_body", "blood_magic", "angelic_halo", "courageous_anthem", "fleeing", "sure_strike", "soothe", "protection", "lay_on_hands_ac", "stoke_the_heart", "forbidding_ward", "life_link", "sigil", "dueling_parry", "energy_ablation", "weapon_surge", "alchemy_elixir_of_life_minor", "alchemy_antidote_lesser", "alchemy_antiplague_lesser", "alchemy_cheetahs_elixir_lesser", "alchemy_bravos_brew_lesser", "alchemy_bestial_mutagen_lesser", "alchemy_cognitive_mutagen_lesser", "alchemy_juggernaut_mutagen_lesser", "alchemy_giant_centipede_venom_coating", "alchemy_glue_bomb_lesser"}
                and row[6] is not None
            )
            or (
                row[1] in {"guidance", "enfeebled", "frostbite_weakness", "runic_body", "blood_magic", "stoke_the_heart", "forbidding_ward", "life_link", "protection"}
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
                row[1] in {"alchemy_elixir_of_life_minor", "alchemy_antidote_lesser", "alchemy_antiplague_lesser", "alchemy_cheetahs_elixir_lesser", "alchemy_bravos_brew_lesser"}
                and not _valid_alchemy_elixir_effect(
                    row, creatures, starts_raw, world_time_seconds,
                    infused_alchemy_items, consumed_infused_item_ids,
                )
            )
            or (
                row[1] in {"alchemy_bestial_mutagen_lesser", "alchemy_cognitive_mutagen_lesser", "alchemy_juggernaut_mutagen_lesser"}
                and not _valid_alchemy_mutagen_effect(
                    row, creatures, starts_raw, world_time_seconds,
                    infused_alchemy_items, consumed_infused_item_ids,
                )
            )
            or (
                row[1] == "alchemy_giant_centipede_venom_coating"
                and not _valid_alchemy_venom_coating(
                    row, creatures, starts_raw, world_time_seconds,
                    infused_alchemy_items, consumed_infused_item_ids,
                )
            )
            or (
                row[1] == "alchemy_glue_bomb_lesser"
                and not _valid_alchemy_bomb_rider_effect(
                    row, creatures, starts_raw, world_time_seconds,
                    infused_alchemy_items, consumed_infused_item_ids,
                )
            )
            or (
                row[1] != "alchemy_glue_bomb_lesser"
                and row[12] != 0
            )
            or (
                row[1] == "alchemy_glue_bomb_lesser"
                and row[12] > 2
            )
            or (
                row[1] == "dueling_parry"
                and (
                    row[4] != 2
                    or row[2] != row[3]
                    or row[5] != starts_raw[row[2]] + 1
                    or row[6] is not None
                    or "dueling_parry" not in get_definition(
                        creatures[row[2]].definition_id
                    ).abilities
                    or not dueling_parry_requirements_met(
                        item_instances, creatures[row[2]],
                        get_definition(creatures[row[2]].definition_id),
                    )
                    or row[2] in dueling_parry_sources
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
                row[1] == "courageous_anthem"
                and (
                    row[4] != 1
                    or row[5] - starts_raw[row[2]] not in {1, 3, 4}
                    or not _valid_active_duration_deadline(
                        "courageous_anthem", row[5], starts_raw[row[2]],
                        round_number, world_time_seconds, row[6],
                        encounter_start_seconds=encounter_start_seconds,
                        in_progress=in_progress,
                    )
                    or "courageous_anthem" not in get_definition(
                        creatures[row[2]].definition_id
                    ).abilities
                    or not any(
                        spell.spell_id == "courageous_anthem"
                        and spell.rank == 1 and spell.cantrip
                        for spell in get_definition(creatures[row[2]].definition_id).spontaneous_spells
                    )
                    or creatures[row[3]].team != creatures[row[2]].team
                    or (row[2], row[3]) in anthem_pairs
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
                        for spell in (
                            *get_definition(creatures[row[2]].definition_id).prepared_spells,
                            *get_definition(creatures[row[2]].definition_id).spontaneous_spells,
                        )
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
                            or not (
                                any(
                                    spell.spell_id == "sure_strike"
                                    and spell.rank == 1
                                    and not spell.cantrip
                                    for spell in get_definition(
                                        creatures[row[2]].definition_id
                                    ).prepared_spells
                                )
                                or (
                                    "spell_substitution" in get_definition(
                                        creatures[row[2]].definition_id
                                    ).abilities
                                    and any(
                                        entry.spell_id == "sure_strike" and entry.rank == 1
                                        for entry in get_definition(
                                            creatures[row[2]].definition_id
                                        ).spell_substitution_book
                                    )
                                )
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
                row[1] == "protection"
                and (
                    row[4] != 1
                    or row[5] != starts_raw[row[2]] + 10
                    or not _valid_active_duration_deadline(
                        "protection", row[5], starts_raw[row[2]],
                        round_number, world_time_seconds, row[6],
                        encounter_start_seconds=encounter_start_seconds,
                        in_progress=in_progress,
                    )
                    or not any(
                        spell.spell_id == "protection" and spell.rank == 1 and not spell.cantrip
                        for spell in get_definition(creatures[row[2]].definition_id).prepared_spells
                    )
                    or not any(
                        slot.spell_id == "protection" and slot.rank == 1
                        and not slot.cantrip and slot.spent
                        for slot in creatures[row[2]].prepared_slots
                    )
                    or creatures[row[3]].dead
                    or (row[2], row[3]) in protection_pairs
                )
            )
                or (
                row[1] == "forbidding_ward"
                and (
                    row[4] != 1
                    or row[7] <= starts_raw[row[2]]
                    or row[7] > starts_raw[row[2]] + 10
                    or row[8] != encounter_start_seconds + (row[7] - 1) * 6
                    or row[5] > row[7]
                    or row[6] is None or row[8] is None or row[6] > row[8]
                    or row[9] < 1
                    or row[10] is None
                    or row[2] == row[3] or row[2] == row[10] or row[3] == row[10]
                    or creatures[row[3]].team != creatures[row[2]].team
                    or creatures[row[10]].team == creatures[row[2]].team
                    or not _valid_active_duration_deadline(
                        "forbidding_ward", row[5], starts_raw[row[2]],
                        round_number, world_time_seconds, row[6],
                        encounter_start_seconds=encounter_start_seconds,
                        in_progress=in_progress,
                    )
                    or not any(
                        spell.spell_id == "forbidding_ward"
                        and spell.rank == 1 and spell.cantrip
                        for spell in (
                            *get_definition(creatures[row[2]].definition_id).prepared_spells,
                            *get_definition(creatures[row[2]].definition_id).spontaneous_spells,
                        )
                    )
                )
            )
                or (
                row[1] == "stoke_the_heart"
                and (
                    row[4] != 2
                    or row[7] <= starts_raw[row[2]]
                    or row[7] > starts_raw[row[2]] + 10
                    or row[8] != encounter_start_seconds + (row[7] - 1) * 6
                    or row[5] > row[7]
                    or row[6] is None or row[8] is None or row[6] > row[8]
                    or row[9] < 1
                    or not _valid_active_duration_deadline(
                        "stoke_the_heart", row[5], starts_raw[row[2]],
                            round_number, world_time_seconds, row[6],
                            encounter_start_seconds=encounter_start_seconds,
                            in_progress=in_progress,
                        )
                        or "stoke_the_heart" not in get_definition(creatures[row[2]].definition_id).abilities
                        or creatures[row[3]].dead
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
        if row[1] == "life_link" and (
            row[4] != 3
            or row[2] == row[3]
            or row[5] > starts_raw[row[2]] + 10
            or not _valid_active_duration_deadline(
                "life_link", row[5], starts_raw[row[2]],
                round_number, world_time_seconds, row[6],
                encounter_start_seconds=encounter_start_seconds,
                in_progress=in_progress,
            )
            or "life_oracle" not in get_definition(creatures[row[2]].definition_id).abilities
            or not any(
                spell.spell_id == "life_link" and spell.rank == 1 and not spell.cantrip
                for spell in get_definition(creatures[row[2]].definition_id).focus_spells
            )
            or creatures[row[2]].unconscious or creatures[row[2]].dead
            or row[2] in life_link_sources
            or row[11] > round_number
        ):
            raise ValueError("save has invalid Life Link effect")
        if row[1] == "sigil" and (
            row[4] not in {1, 2}
            or row[5] <= starts_raw[row[2]]
            or type(row[6]) is not int
            or row[6] <= world_time_seconds
            or row[6] > world_time_seconds + 604800
            or not any(
                slot.spell_id == "sigil" and slot.cantrip
                for slot in creatures[row[2]].prepared_slots
            )
        ):
            raise ValueError("save has invalid Sigil effect")
        active_effect_ids.add(row[0])
        if row[1] == "dueling_parry":
            dueling_parry_sources.add(row[2])
        if row[1] == "blood_magic":
            blood_magic_sources.add(row[2])
        if row[1] == "angelic_halo":
            halo_sources.add(row[2])
        if row[1] == "courageous_anthem":
            anthem_pairs.add((row[2], row[3]))
        if row[1] == "sure_strike":
            sure_strike_sources.add(row[2])
        if row[1] == "energy_ablation":
            energy = row[0].split(":", 3)[2] if row[0].count(":") >= 2 else ""
            definition = get_definition(creatures[row[2]].definition_id)
            if (
                row[2] != row[3] or row[4] != 1 or row[5] != starts_raw[row[2]] + 2
                or type(row[6]) is not int or not world_time_seconds < row[6] <= world_time_seconds + 12
                or energy not in {"acid", "cold", "electricity", "fire", "force", "sonic", "vitality", "void"}
                or "energy_ablation" not in definition.abilities
            ):
                raise ValueError("save has invalid Energy Ablation effect")
        if row[1] == "weapon_surge":
            definition = get_definition(creatures[row[2]].definition_id)
            if (
                row[2] != row[3] or row[4] != 1 or row[5] != starts_raw[row[2]] + 1
                or type(row[6]) is not int or not world_time_seconds < row[6] <= world_time_seconds + 6
                or "weapon_surge" not in definition.abilities
                or row[0].count(":") < 3
                or row[0].split(":", 3)[2] not in creatures[row[2]].held_items
            ):
                raise ValueError("save has invalid Weapon Surge effect")
        if row[1] == "soothe":
            soothe_pairs.add((row[2], row[3]))
        if row[1] == "protection":
            protection_pairs.add((row[2], row[3]))
        if row[1] == "fleeing":
            fleeing_pairs.add((row[2], row[3]))
        if row[1] == "life_link":
            life_link_sources.add(row[2])
        effects.append(ActiveSpellEffect(*row))
    persistent_raw = data.get("persistent_effects", [])
    if not isinstance(persistent_raw, list):
        raise ValueError("save has invalid persistent damage effects")
    persistent_effects: list[PersistentDamageEffect] = []
    persistent_keys: set[tuple[str, str]] = set()
    persistent_ids: set[str] = set()
    for row in persistent_raw:
        if (
            not isinstance(row, list) or len(row) != 8
            or any(not isinstance(value, str) or not value for value in row[:5])
            or not isinstance(row[5], list) or any(type(value) is not int or value < 2 for value in row[5])
            or type(row[6]) is not int or row[6] < 0
            # The admitted spell and Bomber bomb sources author a one-minute
            # expiration. A save may retain only its remaining portion, never
            # extend it or replace it with an unbounded GM condition.
            or type(row[7]) is not int or not world_time_seconds < row[7] <= world_time_seconds + 60
            or row[1] not in expected_ids or row[2] not in expected_ids
            or row[4] not in {"acid", "bleed", "fire"}
            or (row[3], row[4], tuple(row[5]), row[6]) not in {
                ("ignition", "fire", (4,), 0),
                ("caustic_blast", "acid", (), 1),
                ("gouging_claw", "bleed", (), 2),
                ("gouging_claw", "bleed", (), 4),
                # Ignition's adjacent melee profile persists with d6s.
                ("ignition", "fire", (6,), 0),
                ("alchemists_fire_lesser", "fire", (), 1),
                ("alchemists_fire_lesser", "fire", (), 2),
                ("acid_flask_lesser", "acid", (6,), 0),
                ("acid_flask_lesser", "acid", (6, 6), 0),
            }
            or (not row[5] and row[6] < 1)
            or row[0] in persistent_ids or (row[2], row[4]) in persistent_keys
        ):
            raise ValueError("save has invalid persistent damage effect")
        source = creatures[row[1]]
        source_definition = get_definition(source.definition_id)
        if row[3] in {"alchemists_fire_lesser", "acid_flask_lesser"}:
            alchemy_state = alchemy_states.get(row[1])
            if (
                alchemy_state is None
                or alchemy_state.character_level != 2
                or not any(
                    item.formula_id == row[3]
                    and item.creator_actor_id == row[1]
                    and item_id in consumed_infused_item_ids
                    for item_id, item in infused_alchemy_items.items()
                )
            ):
                raise ValueError("save has a persistent damage source without consumed Bomber formula provenance")
        elif not (
            any(slot.spell_id == row[3] for slot in source.prepared_slots)
            or any(access.spell_id == row[3] for access in source_definition.spontaneous_spells)
        ):
            raise ValueError("save has a persistent damage source without that spell access")
        persistent_ids.add(row[0]); persistent_keys.add((row[2], row[4]))
        persistent_effects.append(PersistentDamageEffect(
            row[0], row[1], row[2], row[3], row[4], tuple(row[5]), row[6], row[7]
        ))
    venom_raw = data.get("giant_centipede_venom_afflictions", [])
    if not isinstance(venom_raw, list):
        raise ValueError("save has invalid Giant Centipede Venom afflictions")
    venom_afflictions: list[GiantCentipedeVenomAffliction] = []
    venom_ids: set[str] = set()
    venom_targets: set[str] = set()
    paused_venom_effect_id: str | None = None
    paused_venom_target_id: str | None = None
    if pending_choice is not None:
        continuation = pending_choice.continuation
        resolution = pending_choice.damage_resolution
        parent = continuation.parent_continuation if continuation is not None else None
        if (
            pending_choice.kind == "heroic_recovery_damage"
            and continuation is not None and continuation.kind == "venom_end_turn"
            and parent is not None and parent.kind == "persistent_end_turn"
            and resolution is not None
            and resolution.source_kind == "family"
            and resolution.source == "Giant Centipede Venom"
            and continuation.actor_id == pending_choice.target_id
            and parent.actor_id == pending_choice.target_id
        ):
            paused_venom_effect_id = resolution.group.group_id
            paused_venom_target_id = pending_choice.target_id
    for row in venom_raw:
        if (
            not isinstance(row, list) or len(row) != 7
            or any(not isinstance(value, str) or not value for value in row[:3])
            or row[3] != 17 or row[4] not in {1, 2, 3}
            or type(row[5]) is not int or not world_time_seconds < row[5] <= world_time_seconds + 36
            or type(row[6]) is not int
            or row[6] not in {
                ends_raw.get(row[2], 0) + 1,
                *(
                    (ends_raw.get(row[2], 0) + 2,)
                    if (row[0], row[2]) == (paused_venom_effect_id, paused_venom_target_id)
                    else ()
                ),
            }
            or row[1] not in expected_ids or row[2] not in expected_ids
            or row[0] in venom_ids or row[2] in venom_targets
            or "bomber_alchemist" not in get_definition(creatures[row[1]].definition_id).abilities
        ):
            raise ValueError("save has invalid Giant Centipede Venom affliction")
        venom_ids.add(row[0]); venom_targets.add(row[2])
        venom_afflictions.append(GiantCentipedeVenomAffliction(*row))
    item_effects_raw = data.get("active_item_effects", [])
    if not isinstance(item_effects_raw, list):
        raise ValueError("save has invalid active item spell effects")
    item_effects: list[ActiveItemSpellEffect] = []
    # Item effects share the encounter-wide effect identity namespace with
    # creature effects.  A forged cross-family duplicate must not silently
    # shadow an existing active effect on load.
    item_effect_ids: set[str] = set(active_effect_ids)
    item_effect_targets: set[tuple[str, str, str]] = set()
    for raw_row in item_effects_raw:
        if not isinstance(raw_row, list):
            raise ValueError("save has invalid active item spell effects")
        # The visible marker bit was appended for Sigil; legacy Runic Weapon
        # rows remain visible by definition.
        row = [*raw_row, True] if len(raw_row) == 6 else raw_row
        if (
            len(row) != 7
            or any(not isinstance(value, str) or not value for value in row[:4])
            or type(row[4]) is not int or row[4] < 1
            or (row[1] == "runic_weapon" and (type(row[5]) is not int or row[5] < 1))
            or (row[1] == "sigil" and row[5] is not None)
            or type(row[6]) is not bool
            or row[1] not in {"runic_weapon", "sigil"}
            or row[2] not in expected_ids
            or row[3] not in item_instances
            or row[0] in item_effect_ids
            or (row[1], row[2], row[3]) in item_effect_targets
            or row[4] <= starts_raw[row[2]]
            or (row[1] == "runic_weapon" and (
                row[4] > starts_raw[row[2]] + 10
                or not _valid_active_duration_deadline(
                    "runic_weapon", row[4], starts_raw[row[2]],
                    round_number, world_time_seconds, row[5],
                    encounter_start_seconds=encounter_start_seconds,
                    in_progress=in_progress,
                )
            ))
            or (row[1] == "sigil" and not any(
                slot.spell_id == "sigil" and slot.cantrip
                for slot in creatures[row[2]].prepared_slots
            ))
            or (row[1] == "runic_weapon" and (
                ITEM_CATEGORIES.get(item_instances[row[3]].definition_id) != "weapon"
                and item_instances[row[3]].definition_id != "staff"
            ))
            or (row[1] == "runic_weapon" and item_instances[row[3]].definition_id not in {"longsword", "shortsword", "staff"})
            or (row[1] == "runic_weapon" and not (
                any(
                    spell.spell_id == "runic_weapon"
                    and spell.rank == 1
                    and not spell.cantrip
                    for spell in get_definition(creatures[row[2]].definition_id).spontaneous_spells
                )
                or any(
                    slot.spell_id == "runic_weapon"
                    and slot.rank == 1
                    and not slot.cantrip
                    for slot in creatures[row[2]].prepared_slots
                )
            ))
        ):
            raise ValueError("save has invalid active item spell effects")
        try:
            if row[1] == "runic_weapon":
                weapon_rune_profile_for_item(item_instances[row[3]])
                effect = ActiveItemSpellEffect(*row[:6], visible=row[6])
            else:
                effect = ActiveItemSpellEffect(
                    row[0], row[1], row[2], row[3], row[4], row[5], visible=row[6]
                )
        except (TypeError, ValueError) as error:
            raise ValueError("save has invalid active item spell effects") from error
        item_effect_ids.add(row[0])
        item_effect_targets.add((row[1], row[2], row[3]))
        item_effects.append(effect)
    condition_effects_raw = data.get("condition_effects")
    if not isinstance(condition_effects_raw, list):
        raise ValueError("save has invalid condition effects")
    condition_effects: list[ActiveConditionEffect] = []
    effect_ids: set[str] = set()
    for row in condition_effects_raw:
        if not isinstance(row, list):
            raise ValueError("save has invalid condition effect")
        if len(row) == 7:
            row = [*row, None]
        if (
            len(row) != 8
            or any(not isinstance(value, str) or not value for value in row[:4])
            or type(row[4]) is not int or row[4] < 1
            or not isinstance(row[5], list) or len(row[5]) != 3
            or not isinstance(row[5][0], str) or not row[5][0]
            or row[5][1] not in {"start", "end"}
            or type(row[5][2]) is not int or row[5][2] < 1
            or row[2] not in expected_ids or row[3] not in expected_ids
            or row[5][0] not in expected_ids
            or (row[6] is not None and (type(row[6]) is not int or row[6] < 0))
            or (row[7] is not None and row[7] not in {"approach", "flee", "release", "prone", "stand"})
            or row[0] in effect_ids
        ):
            raise ValueError("save has invalid condition effect")
        expiration = EffectExpiration(row[5][0], row[5][1], row[5][2])
        effect = ActiveConditionEffect(row[0], row[1], row[2], row[3], row[4], expiration, row[6], row[7])
        if effect.kind != "commanded":
            try:
                effective_condition_value((ConditionValue(effect.kind, effect.value, effect.effect_id),), effect.kind)
            except (TypeError, ValueError) as error:
                raise ValueError("save has unsupported condition effect") from error
        elif (effect.value not in {1, 3} or effect.command_mode not in {"approach", "flee", "release", "prone", "stand"}
              or effect.expiration.anchor_actor_id != effect.target_actor_id or effect.expiration.boundary != "end"):
            raise ValueError("save has invalid Command effect")
        if effect.effect_id.startswith(("dread_ampoule:", "glue_bomb:")) and not _valid_bomber_bomb_condition_effect(
            effect, creatures, starts_raw, ends_raw, effects,
        ):
            raise ValueError("save has invalid Bomber bomb condition provenance")
        completed_count = starts_raw[expiration.anchor_actor_id] if expiration.boundary == "start" else ends_raw[expiration.anchor_actor_id]
        if expiration.occurrence <= completed_count:
            raise ValueError("save retains an expired condition effect")
        effect_ids.add(effect.effect_id)
        condition_effects.append(effect)

    # A saved Guidance decision or spell-save reroll occurs after the cast has
    # already committed its source and target facts.  Validate that provenance
    # before Encounter validates the live effect, DC, and modifiers.
    if pending_choice is not None and (
        pending_choice.kind == "spell_save_hero_reroll"
        or (
            pending_choice.kind == "guidance_use"
            and pending_choice.check_kind == "spell_save"
        )
    ):
        _validate_committed_spell_save_provenance(creatures, pending_choice)

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

    martial_stances_raw = data.get("martial_stances", {})
    if not isinstance(martial_stances_raw, dict) or not set(martial_stances_raw).issubset(expected_ids):
        raise ValueError("save has invalid martial stances")
    martial_stances: dict[str, MartialStanceState] = {}
    for actor_id, row in martial_stances_raw.items():
        actor = creatures[actor_id]
        definition = get_definition(actor.definition_id)
        if (
            not isinstance(row, list) or len(row) != 2
            or row[0] not in {"crane_stance", "point_blank_stance"} or type(row[1]) is not int
            or not 1 <= row[1] <= round_number
            or not in_progress or actor.unconscious or actor.dead
            or (
                row[0] == "crane_stance"
                and (
                    "crane_stance" not in definition.abilities
                    or definition.armor_category not in {None, "unarmored"}
                    or bool(actor.worn_items)
                )
            )
            or (
                row[0] == "point_blank_stance"
                and (
                    "point_blank_stance" not in definition.abilities
                    or not any("ranged" in attack.traits and attack.item_id in actor.held_items for attack in definition.attacks)
                )
            )
        ):
            raise ValueError("save has invalid Crane Stance state")
        martial_stances[actor_id] = MartialStanceState(row[0], row[1])
    stance_rounds_raw = data.get("martial_stance_used_rounds", {})
    if (
        not isinstance(stance_rounds_raw, dict)
        or not set(stance_rounds_raw).issubset(expected_ids)
        or any(type(value) is not int or not 1 <= value <= round_number for value in stance_rounds_raw.values())
        or any(
            not (
                "crane_stance" in get_definition(creatures[actor_id].definition_id).abilities
                or "point_blank_stance" in get_definition(creatures[actor_id].definition_id).abilities
            )
            for actor_id in stance_rounds_raw
        )
        or any(stance_rounds_raw.get(actor_id) != stance.entered_round for actor_id, stance in martial_stances.items())
    ):
        raise ValueError("save has invalid martial stance action history")

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
        martial_stances=martial_stances,
        martial_stance_used_rounds=dict(stance_rounds_raw),
        initiative_tie_groups=tie_groups,
        initiative_tie_orders=tie_orders,
        initiative_tie_group_index=tie_group_index,
        initiative_reordered=set(initiative_reordered),
        actor_start_counts=dict(starts_raw),
        actor_end_counts=dict(ends_raw),
        feint_off_guard_effects=feint_effects,
        overextending_feint_effects=overextending_effects,
        tumble_behind_exposures=tumble_effects,
        active_effects=effects,
        persistent_effects=persistent_effects,
        giant_centipede_venom_afflictions=venom_afflictions,
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
        alchemy_states=alchemy_states,
        infused_alchemy_items=infused_alchemy_items,
        consumed_infused_item_ids=consumed_infused_item_ids,
    )
    for actor in state.creatures.values():
        definition = get_definition(actor.definition_id)
        if any(
            prepared_slot_rejection(actor, definition, slot, slot.spell_id) is not None
            for slot in actor.prepared_slots
        ):
            raise ValueError("save has a prepared spell outside its finite preparation policy")
        knows_shield = (
            any(slot.spell_id == "shield" and slot.cantrip for slot in actor.prepared_slots)
            or any(
                spell.spell_id == "shield" and spell.cantrip
                for spell in definition.spontaneous_spells
            )
        )
        if (
            (actor.magic_shield_expires_at_start and not knows_shield)
            or actor.magic_shield_expires_at_start > state.actor_start_counts.get(actor.actor_id, 0) + 1
            or (
                actor.shield_recast_available_at_seconds
                and actor.shield_recast_available_at_seconds < state.world_time_seconds
            )
            or (actor.shield_recast_available_at_seconds and not knows_shield)
        ):
            raise ValueError("save has invalid Shield cantrip state")
        has_bond = "arcane_bond" in definition.abilities
        bond_facts = (
            actor.arcane_bond_used_day,
            actor.arcane_bond_recast_until_start,
            actor.arcane_bond_item_id,
            actor.arcane_bond_eligible_slots,
        )
        if not has_bond and any((bond_facts[0], bond_facts[1], bond_facts[2] is not None, bond_facts[3])):
            raise ValueError("save has Arcane Bond facts for an ineligible actor")
        if actor.arcane_bond_used_day > state.preparation_day:
            raise ValueError("save has Arcane Bond use after its preparation day")
        slot_by_id = {slot.slot_id: slot for slot in actor.prepared_slots}
        if any(
            slot_id not in slot_by_id or not slot_by_id[slot_id].spent
            for slot_id in actor.arcane_bond_eligible_slots
        ):
            raise ValueError("save has invalid Arcane Bond prepared-slot history")
        if actor.arcane_bond_item_id is not None and actor.arcane_bond_item_id not in {
            *actor.held_items, *actor.worn_items, *actor.stowed_items,
        }:
            raise ValueError("save has a Bonded Item that is not on the caster")
        if has_bond and actor.arcane_bond_item_id not in {
            None, f"{actor.actor_id}:bonded_staff",
        }:
            raise ValueError("save has a Bonded Item other than the selected bonded_staff")
        if actor.arcane_bond_recast_until_start:
            if (
                actor.arcane_bond_used_day != state.preparation_day
                or actor.arcane_bond_recast_until_start != state.actor_start_counts.get(actor.actor_id, 0)
                or actor.arcane_bond_item_id is None
                or not actor.arcane_bond_eligible_slots
            ):
                raise ValueError("save has invalid current-turn Arcane Bond permission")
        substitution = actor.spell_substitution
        has_substitution = (
            "spell_substitution" in definition.abilities
            and definition.spell_substitution_book_id is not None
        )
        if substitution is not None:
            if not has_substitution:
                raise ValueError("save has Spell Substitution progress for an ineligible actor")
            if f"{actor.actor_id}:{definition.spell_substitution_book_id}" not in {
                *actor.held_items, *actor.worn_items, *actor.stowed_items,
            }:
                raise ValueError("save has Spell Substitution without its owned spellbook")
            slot = slot_by_id.get(substitution.slot_id)
            if (
                slot is None or slot.spent or slot.cantrip or slot.rank != 1
                or slot.spell_id != substitution.original_spell_id
                or substitution.replacement_spell_id == slot.spell_id
                or prepared_slot_rejection(actor, definition, slot, substitution.replacement_spell_id) is not None
            ):
                raise ValueError("save has invalid Spell Substitution progress")
    # ``load_encounter`` is also a public persistence API. Re-run live
    # validation for every target-owned spell-save Hero pause, so direct state
    # loads cannot bypass current DC/save modifiers or the resource ledger.
    if (
        state.pending_choice is not None
        and (
            (
                state.pending_choice.kind in {"spell_save_hero_reroll", "guidance_use"}
                and (
                    state.pending_choice.kind == "spell_save_hero_reroll"
                    or state.pending_choice.check_kind == "spell_save"
                )
                and state.pending_choice.spell_id in {
                    "daze", "void_warp", "fear", "breathe_fire", "electric_arc",
                    "tempest_surge", "vitality_lash", "frostbite", "enfeeble", "harm",
                    "caustic_blast", "gale_blast",
                }
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
            or state.pending_choice.kind in {"witch_restored_spirit", "witch_restored_spirit_timing"}
            or state.pending_choice.kind == "concealment_hero_reroll"
            or state.pending_choice.kind in {"counter_performance_save_choice", "counter_performance_bard_hero_reroll"}
        )
    ):
        from .encounter import Encounter

        Encounter(state, DiceSource())._validate_pending_context()
    return state


def _validate_committed_spell_save_provenance(
    creatures: dict[str, CreatureState], pending: PendingChoice,
) -> None:
    """Validate the one cast already committed before a target's Hero choice."""
    continuation = pending.continuation
    caster = creatures.get(continuation.actor_id if continuation is not None else "")
    target = creatures.get(pending.target_id or "")
    spell_id = pending.spell_id
    spell_label = SPELLS[spell_id].name if spell_id in SPELLS else "spell"
    hero_options = (
        ChoiceOption("keep", "Keep result"),
        ChoiceOption("spend_hero_point", "Spend 1 Hero Point and reroll"),
    )
    guidance_options = (
        ChoiceOption("use", "Use Guidance (+1 status)"),
        ChoiceOption("keep", "Keep Guidance for later"),
    )
    is_hero_choice = pending.kind == "spell_save_hero_reroll"
    is_guidance_choice = pending.kind == "guidance_use" and pending.check_kind == "spell_save"
    if (
        continuation is None
        or caster is None
        or target is None
        or spell_id not in {
            "daze", "void_warp", "fear", "breathe_fire", "electric_arc",
            "tempest_surge", "vitality_lash", "frostbite", "enfeeble", "harm",
            "caustic_blast", "gale_blast",
        }
        or continuation.kind != "cast"
        or continuation.actor_id != caster.actor_id
        or continuation.spell_id != spell_id
        or continuation.spell_actions != 2
        or pending.slot_id != continuation.slot_id
        or continuation.sorcerous_potency != 0
        or continuation.blood_magic_recipient_id is not None
        or (
            continuation.target_id != target.actor_id
            and target.actor_id not in continuation.target_ids
        )
        or target.health_mode is not HealthMode.PC
        or pending.owner_actor_id != target.actor_id
        or pending.actor_id != (caster.actor_id if is_hero_choice else target.actor_id)
        or pending.target_id != target.actor_id
        or pending.check_owner_actor_id != target.actor_id
        or pending.check_kind != "spell_save"
        or not (is_hero_choice or is_guidance_choice)
        or pending.options != (hero_options if is_hero_choice else guidance_options)
    ):
        raise ValueError(f"save has invalid {spell_label} spell save Hero choice provenance")

    spell = SPELLS[spell_id]
    definition = get_definition(caster.definition_id)
    if continuation.spell_source_kind == "prepared":
        if (
            (continuation.slot_id is None and not spell.cantrip)
            or (spell.cantrip and continuation.slot_id is not None)
            or not any(
                (spell.cantrip or slot.slot_id == continuation.slot_id)
                and slot.spell_id == spell_id
                and slot.cantrip == spell.cantrip
                and (slot.cantrip or slot.spent)
                for slot in caster.prepared_slots
            )
        ):
            raise ValueError(f"save has an uncommitted {spell_label} prepared spell save source")
        return
    if continuation.spell_source_kind == "spontaneous":
        access = next(
            (
                item for item in definition.spontaneous_spells
                if item.spell_id == spell_id and item.cantrip == spell.cantrip
            ),
            None,
        )
        if access is None:
            raise ValueError(f"save has an unavailable {spell_label} spontaneous spell save source")
        if spell.cantrip and continuation.slot_id is not None:
            raise ValueError(f"save has an invalid {spell_label} spontaneous spell save source")
        if not spell.cantrip and not any(
            slot.slot_id == continuation.slot_id
            and slot.rank == access.rank
            and slot.remaining < slot.capacity
            for slot in caster.spontaneous_slots
        ):
            raise ValueError(f"save has an uncommitted {spell_label} spontaneous spell save source")
        return
    if continuation.spell_source_kind == "focus" and (
        any(item.spell_id == spell_id for item in definition.focus_spells)
        and caster.focus_points < caster.focus_capacity
    ):
        return
    raise ValueError(f"save has an unavailable {spell_label} spell save source")


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
        "angelic_halo", "courageous_anthem", "fleeing", "runic_weapon", "runic_body", "guidance", "enfeebled", "frostbite_weakness", "blood_magic", "sure_strike", "soothe", "protection", "stoke_the_heart", "forbidding_ward", "life_link",
    } or type(world_deadline) is not int:
        return False
    duration_rounds = 4 if kind == "courageous_anthem" else 1 if kind in {"fleeing", "guidance", "frostbite_weakness", "blood_magic", "sure_strike"} else 10
    starts_remaining = source_start_deadline - source_starts
    expected_deadline = encounter_start_seconds + (source_start_deadline - 1) * 6
    return bool(
        (starts_remaining in {1, 3, 4} if kind == "courageous_anthem" else 1 <= starts_remaining <= duration_rounds)
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
        "defense_target_id": value.defense_target_id,
        "defense_damage_type": value.defense_damage_type,
        "spent_weaknesses": list(value.spent_weaknesses),
        "resistance_remaining": [list(item) for item in value.resistance_remaining],
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
    defense_target_id, defense_damage_type = data.get("defense_target_id"), data.get("defense_damage_type")
    spent_weaknesses, resistance_remaining = data.get("spent_weaknesses", []), data.get("resistance_remaining", [])
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
    if (
        defense_target_id is not None and (not isinstance(defense_target_id, str) or not defense_target_id)
        or defense_damage_type is not None and (not isinstance(defense_damage_type, str) or not defense_damage_type)
        or not isinstance(spent_weaknesses, list)
        or any(not isinstance(item, str) or not item for item in spent_weaknesses)
        or len(set(spent_weaknesses)) != len(spent_weaknesses)
        or not isinstance(resistance_remaining, list)
        or any(not isinstance(row, list) or len(row) != 2 or not isinstance(row[0], str) or not row[0] or type(row[1]) is not int or row[1] < 0 for row in resistance_remaining)
    ):
        raise ValueError("save has invalid paired Strike defense facts")
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
        # Paired outcomes retain the actual post-defense event damage so the
        # second Strike can follow a saved Justice/Shield/Hero interruption.
        check, damage = _check_from_data(row[2]), _damage_from_data(row[3], allow_mitigated=True)
        if check is None or (row[6] and damage is None) or (not row[6] and damage is not None):
            raise ValueError("save has inconsistent paired Strike outcome")
        outcomes.append(PairedStrikeOutcome(row[0], row[1], check, damage, row[4], row[5], row[6]))
    return PairedStrikeContinuation(
        activity_id, owner, paid, initial, tuple(selections), next_index, tuple(outcomes), stage,
        defense_target_id, defense_damage_type, tuple(spent_weaknesses), tuple((row[0], row[1]) for row in resistance_remaining),
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
    from .witch import FamiliarPickup, FamiliarRelease, FamiliarStride, PatronsPuppet

    if type(command) is PatronsPuppet:
        actions = []
        for action in command.actions:
            if type(action) is FamiliarStride:
                actions.append(["stride", [[point.x, point.y] for point in action.path]])
            elif type(action) is FamiliarPickup:
                actions.append(["pickup", action.item_id])
            elif type(action) is FamiliarRelease:
                actions.append(["release", action.item_id])
            else:
                raise ValueError("save cannot encode this familiar action")
        return {"type": "PatronsPuppet", "familiar_id": command.familiar_id, "actions": actions}
    from .barbarian import QuickTempered, Rage

    if type(command) in {Rage, QuickTempered}:
        return {
            "type": type(command).__name__,
            "mode_id": command.mode_id,
            "temporary_hp_choice": command.temporary_hp_choice,
        }
    from .skill_actions import Trip, Grapple, Escape, Demoralize, Feint, TumbleThrough, QuickJump

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
            "youre_next_reaction": command.youre_next_reaction,
        }
    if type(command) is Feint:
        return {"type": "Feint", "target_id": command.target_id, "use_overextending": command.use_overextending}
    if type(command) is TumbleThrough:
        return {
            "type": "TumbleThrough",
            "path": [[point.x, point.y] for point in command.path],
        }
    if type(command) is QuickJump:
        return {
            "type": "QuickJump",
            "path": [[point.x, point.y] for point in command.path],
        }
    from .investigator import BattleMedicine, DeviseStratagem, ForensicExamination, RecallKnowledge, InvestigationCheck, PursueLead, Streetwise

    if type(command) is DeviseStratagem:
        return {
            "type": "DeviseStratagem",
            "target_id": command.target_id,
            "mode": command.mode,
            "free_action": command.free_action,
            "known_weaknesses": command.known_weaknesses,
        }

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
    if type(command) is Streetwise:
        return {
            "type": "Streetwise", "question_key": command.question_key,
            "mode": command.mode, "settlement_key": command.settlement_key,
        }
    if type(command) is InvestigationCheck:
        return {
            "type": "InvestigationCheck",
            "check_key": command.check_key,
            "statistic": command.statistic,
            "target_id": command.target_id,
        }
    if type(command) is PursueLead:
        return {
            "type": "PursueLead",
            "case_id": command.case_id,
            "clue_key": command.clue_key,
            "open_investigation": command.open_investigation,
            "replace_case_id": command.replace_case_id,
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
    from .skill_actions import Trip, Grapple, Escape, Demoralize, Feint, TumbleThrough, QuickJump
    from .investigator import DeviseStratagem, ForensicExamination, RecallKnowledge, InvestigationCheck, PursueLead, Streetwise
    from .swashbuckler import ConfidentFinisher

    kind = data["type"]
    if kind == "PatronsPuppet":
        from .witch import FamiliarPickup, FamiliarRelease, FamiliarStride, PatronsPuppet
        if set(data) != {"type", "familiar_id", "actions"} or not isinstance(data["familiar_id"], str) or not data["familiar_id"] or not isinstance(data["actions"], list):
            raise ValueError("save has invalid pending Patron's Puppet command")
        actions = []
        for row in data["actions"]:
            if not isinstance(row, list) or len(row) != 2 or not isinstance(row[0], str):
                raise ValueError("save has invalid pending familiar action")
            if row[0] == "stride" and isinstance(row[1], list) and row[1]:
                if any(not isinstance(point, list) or len(point) != 2 or any(type(value) is not int for value in point) for point in row[1]):
                    raise ValueError("save has invalid pending familiar stride")
                actions.append(FamiliarStride(tuple(Position(*point) for point in row[1])))
            elif row[0] == "pickup" and isinstance(row[1], str) and row[1]:
                actions.append(FamiliarPickup(row[1]))
            elif row[0] == "release" and isinstance(row[1], str) and row[1]:
                actions.append(FamiliarRelease(row[1]))
            else:
                raise ValueError("save has invalid pending familiar action")
        return PatronsPuppet(data["familiar_id"], tuple(actions))
    if kind == "DeviseStratagem":
        if set(data) != {"type", "target_id", "mode", "free_action", "known_weaknesses"}:
            raise ValueError("save has invalid pending Devise a Stratagem command")
        target_id, mode = data["target_id"], data["mode"]
        if (
            not isinstance(target_id, str) or not target_id
            or mode not in {None, ATTACK_STRATAGEM, SKILL_STRATAGEM}
            or type(data["free_action"]) is not bool
            or type(data["known_weaknesses"]) is not bool
        ):
            raise ValueError("save has invalid pending Devise a Stratagem command")
        return DeviseStratagem(target_id, mode, data["free_action"], data["known_weaknesses"])
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
        if set(data) not in (
            {"type", "target_id", "spoken_language", "use_intimidating_glare"},
            {"type", "target_id", "spoken_language", "use_intimidating_glare", "youre_next_reaction"},
        ):
            raise ValueError("save has invalid pending Demoralize command")
        target_id, language, glare = data["target_id"], data["spoken_language"], data["use_intimidating_glare"]
        youre_next = data.get("youre_next_reaction", False)
        if (
            not isinstance(target_id, str) or not target_id
            or (language is not None and (not isinstance(language, str) or not language))
            or type(glare) is not bool
            or type(youre_next) is not bool
        ):
            raise ValueError("save has invalid pending Demoralize command")
        return Demoralize(target_id, language, glare, youre_next)
    if kind == "Feint":
        if set(data) not in ({"type", "target_id"}, {"type", "target_id", "use_overextending"}):
            raise ValueError("save has invalid pending Feint command")
        target_id = data["target_id"]
        use_overextending = data.get("use_overextending", False)
        if not isinstance(target_id, str) or not target_id or type(use_overextending) is not bool:
            raise ValueError("save has invalid pending Feint command")
        return Feint(target_id, use_overextending)
    if kind == "TumbleThrough":
        if set(data) != {"type", "path"} or not isinstance(data["path"], list) or not data["path"]:
            raise ValueError("save has invalid pending Tumble Through command")
        points = []
        for row in data["path"]:
            if (
                not isinstance(row, list)
                or len(row) != 2
                or any(type(value) is not int for value in row)
            ):
                raise ValueError("save has invalid pending Tumble Through path")
            points.append(Position(row[0], row[1]))
        return TumbleThrough(tuple(points))
    if kind == "QuickJump":
        if set(data) != {"type", "path"} or not isinstance(data["path"], list) or not data["path"]:
            raise ValueError("save has invalid pending Quick Jump path")
        points = []
        for row in data["path"]:
            if (
                not isinstance(row, list) or len(row) != 2
                or type(row[0]) is not int or type(row[1]) is not int
            ):
                raise ValueError("save has invalid pending Quick Jump path")
            points.append(Position(row[0], row[1]))
        return QuickJump(tuple(points))
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
    if kind == "Streetwise":
        if set(data) != {"type", "question_key", "mode", "settlement_key"}:
            raise ValueError("save has invalid pending Streetwise command")
        question_key, mode, settlement_key = data["question_key"], data["mode"], data["settlement_key"]
        if (not isinstance(question_key, str) or not question_key or mode not in {"recall", "gather"}
            or (settlement_key is not None and (not isinstance(settlement_key, str) or not settlement_key))):
            raise ValueError("save has invalid pending Streetwise command")
        return Streetwise(question_key, mode, settlement_key)
    if kind == "InvestigationCheck":
        if set(data) != {"type", "check_key", "statistic", "target_id"}:
            raise ValueError("save has invalid pending investigation check command")
        check_key, statistic, target_id = data["check_key"], data["statistic"], data["target_id"]
        if (
            not isinstance(check_key, str) or not check_key
            or (statistic is not None and (not isinstance(statistic, str) or not statistic))
            or (target_id is not None and (not isinstance(target_id, str) or not target_id))
        ):
            raise ValueError("save has invalid pending investigation check command")
        return InvestigationCheck(check_key, statistic, target_id)
    if kind == "PursueLead":
        if set(data) != {"type", "case_id", "clue_key", "open_investigation", "replace_case_id"}:
            raise ValueError("save has invalid pending Pursue a Lead command")
        case_id, clue_key, open_investigation, replace_case_id = (
            data["case_id"], data["clue_key"], data["open_investigation"], data["replace_case_id"]
        )
        if (
            not isinstance(case_id, str) or not case_id
            or (clue_key is not None and (not isinstance(clue_key, str) or not clue_key))
            or type(open_investigation) is not bool
            or (replace_case_id is not None and (not isinstance(replace_case_id, str) or not replace_case_id))
        ):
            raise ValueError("save has invalid pending Pursue a Lead command")
        return PursueLead(case_id, clue_key, open_investigation, replace_case_id)
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
        "heroic_recovery_damage", "damage_defense", "shield_block", "reaction", "no_escape", "stunning_blows", "stunning_blows_hero_reroll", "spell_target", "spell_self_inclusion", "persistent_recovery",
            "spell_willingness", "spell_blood_magic_recipient", "guidance_use", "divine_grace", "spell_attack_hero_reroll", "detect_magic_known",
            "spell_save_hero_reroll", "spell_slot",
            "lingering_composition_hero_reroll", "counter_performance_save_choice", "counter_performance_bard_hero_reroll",
        "grabbed_manipulate_hero_reroll",
        "family_action", "nimble_dodge", "reactive_shield", "youre_next", "concealment_hero_reroll",
            "desperate_prayer", "witch_restored_spirit", "witch_restored_spirit_timing",
            "witch_restored_spirit_temp_hp", "witch_restored_spirit_willingness",
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
    elif kind not in {"concealment_hero_reroll", "reaction"} and (
        family_id is not None or procedure_id is not None
    ):
        raise ValueError("save has family identifiers on a non-family choice")
    if family_command is not None and not (
        (kind in {"family_action", "reaction", "concealment_hero_reroll"} and family_id == "martial")
        or (kind == "witch_restored_spirit_timing" and type(family_command).__name__ == "PatronsPuppet")
        or (kind == "witch_restored_spirit_temp_hp" and type(family_command).__name__ == "PatronsPuppet")
        or (kind == "witch_restored_spirit_willingness" and type(family_command).__name__ == "PatronsPuppet")
    ):
        raise ValueError("save has a skill command on a non-martial family choice")
    if kind == "reaction" and (
        family_command is not None
        and (family_id != "martial" or procedure_id != "investigator:clue_in")
    ):
        raise ValueError("save has an unsupported family reaction choice")
    if kind == "concealment_hero_reroll":
        spell_concealment = (
            family_id is None
            and procedure_id is None
            and optional_strings["spell_id"] in CONCEALMENT_TARGETED_SPELL_IDS
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
        # The live spell-save validator recomputes a deferred Hero check after
        # it has established its committed caster and target.  This keeps the
        # specific provenance/DC error ordering while still rejecting forged
        # arithmetic there.
        check=_check_from_data(
            data.get("check"),
            validate_arithmetic=kind != "spell_save_hero_reroll",
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
        "spell_area_direction": None if continuation.spell_area_direction is None else [
            continuation.spell_area_direction.x, continuation.spell_area_direction.y
        ],
        "widen_spell_area_length_ft": continuation.widen_spell_area_length_ft,
        "spell_mode": continuation.spell_mode,
        "hunter_aim_intent": (
            None if continuation.hunter_aim_intent is None else [
                continuation.hunter_aim_intent.target_actor_id,
                continuation.hunter_aim_intent.attack_id,
                continuation.hunter_aim_intent.item_id,
            ]
        ),
        "reach_spell_effective_range_ft": continuation.reach_spell_effective_range_ft,
        "ranged_penalty": continuation.ranged_penalty,
        "guidance_bonus": continuation.guidance_bonus,
        "feint_off_guard_applied": continuation.feint_off_guard_applied,
        "guidance_checked": continuation.guidance_checked,
        "divine_grace_checked": continuation.divine_grace_checked,
        "divine_grace_used": continuation.divine_grace_used,
        "stage": continuation.stage,
        "parent_continuation": _continuation_to_data(continuation.parent_continuation),
        "attack_count_committed": continuation.attack_count_committed,
        "attack_target_off_guard": continuation.attack_target_off_guard,
        "nimble_dodge_decided": continuation.nimble_dodge_decided,
        "nimble_dodge_used": continuation.nimble_dodge_used,
        "reactive_shield_decided": continuation.reactive_shield_decided,
        "overextending_feint_penalty": continuation.overextending_feint_penalty,
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
        "tumble_command": _family_command_to_data(continuation.tumble_command),
        "tumble_saved_check": _saved_check_to_data(continuation.tumble_saved_check),
        "tumble_distance": continuation.tumble_distance,
        "tumble_origin": None if continuation.tumble_origin is None else [
            continuation.tumble_origin.x, continuation.tumble_origin.y
        ],
        "quick_jump_saved_check": _saved_check_to_data(continuation.quick_jump_saved_check),
        "paired_strike": _paired_strike_to_data(continuation.paired_strike),
        "sudden_charge_second_path": [
            [point.x, point.y] for point in continuation.sudden_charge_second_path
        ],
        "sudden_charge_first_path": [
            [point.x, point.y] for point in continuation.sudden_charge_first_path
        ],
        "sudden_charge_origin": (
            None if continuation.sudden_charge_origin is None
            else [continuation.sudden_charge_origin.x, continuation.sudden_charge_origin.y]
        ),
        "sudden_charge_origin_diagonals": continuation.sudden_charge_origin_diagonals,
        "movement_origin": (
            None if continuation.movement_origin is None
            else [continuation.movement_origin.x, continuation.movement_origin.y]
        ),
        "no_escape_reactor_id": continuation.no_escape_reactor_id,
        "no_escape_remaining_speed_ft": continuation.no_escape_remaining_speed_ft,
        "stunning_blows_target_id": continuation.stunning_blows_target_id,
        "bomber_only_primary_splash": continuation.bomber_only_primary_splash,
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
    for key in ("mode", "item_id", "target_id", "attack_id", "damage_type", "movement_kind", "reaction_trigger", "spell_id", "spell_target_id", "spell_target_item_id", "spell_target_wielder_id", "slot_id", "stage", "spell_source_kind", "blood_magic_recipient_id", "light_control", "light_color", "light_attachment_actor_id", "light_replacement_orb_id", "light_orb_id", "spell_mode"):
        value = data.get(key)
        if value is not None and not isinstance(value, str):
            raise ValueError(f"save has invalid interrupted action {key}")
        optional_strings[key] = value
    integers = {
        key: _required_int(data, key)
        for key in ("next_step", "damage_bonus_dice", "attack_actions_cost", "attack_count_cost", "attack_penalty", "attack_count", "spell_actions", "ranged_penalty", "guidance_bonus")
    }
    overextending_feint_penalty = data.get("overextending_feint_penalty", 0)
    if type(overextending_feint_penalty) is not int or overextending_feint_penalty not in {0, -2}:
        raise ValueError("save has invalid Overextending Feint penalty")
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
        or optional_strings["spell_source_kind"] not in {"prepared", "spontaneous"}
        or optional_strings["slot_id"] is None
        or integers["spell_actions"] != 2
        or sorcerous_potency != 0
        or optional_strings["blood_magic_recipient_id"] is not None
    ):
        raise ValueError("save has invalid Runic Weapon item-target provenance")
    seen_reactors = _required_str_list(data, "seen_reactors")
    target_ids = _required_str_list(data, "target_ids")
    area_direction_raw = data.get("spell_area_direction")
    if area_direction_raw is None:
        spell_area_direction = None
    elif (
        not isinstance(area_direction_raw, list)
        or len(area_direction_raw) != 2
        or any(type(value) is not int for value in area_direction_raw)
        or tuple(area_direction_raw) == (0, 0)
        or any(value not in {-1, 0, 1} for value in area_direction_raw)
    ):
        raise ValueError("save has invalid Breathe Fire area direction")
    else:
        spell_area_direction = Position(*area_direction_raw)
    if spell_area_direction is not None and optional_strings["spell_id"] != "breathe_fire":
        raise ValueError("save has Breathe Fire area direction on a different spell")
    if optional_strings["spell_id"] == "breathe_fire" and spell_area_direction is None:
        raise ValueError("save has Breathe Fire without its area direction")
    include_self = data.get("include_self")
    spell_save_degree = data.get("spell_save_degree")
    reach_spell_effective_range_ft = data.get("reach_spell_effective_range_ft")
    widen_spell_area_length_ft = data.get("widen_spell_area_length_ft")
    if include_self is not None and type(include_self) is not bool:
        raise ValueError("save has invalid interrupted spell self-inclusion")
    if spell_save_degree is not None and (type(spell_save_degree) is not int or not 0 <= spell_save_degree <= 3):
        raise ValueError("save has invalid interrupted save degree")
    if reach_spell_effective_range_ft is not None and (
        type(reach_spell_effective_range_ft) is not int or reach_spell_effective_range_ft <= 0
    ):
        raise ValueError("save has invalid committed Reach Spell range")
    if reach_spell_effective_range_ft is not None and kind != "cast":
        raise ValueError("save has Reach Spell range on a non-cast continuation")
    if widen_spell_area_length_ft is not None and (
        type(widen_spell_area_length_ft) is not int or widen_spell_area_length_ft <= 0
    ):
        raise ValueError("save has invalid committed Widen Spell area")
    if widen_spell_area_length_ft is not None and (
        kind != "cast" or optional_strings["spell_id"] != "breathe_fire"
    ):
        raise ValueError("save has Widen Spell area on an invalid continuation")
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
    hunter_aim_raw = data.get("hunter_aim_intent")
    if hunter_aim_raw is None:
        hunter_aim_intent = None
    elif (
        not isinstance(hunter_aim_raw, list) or len(hunter_aim_raw) != 3
        or not isinstance(hunter_aim_raw[0], str) or not hunter_aim_raw[0]
        or not isinstance(hunter_aim_raw[1], str) or not hunter_aim_raw[1]
        or (hunter_aim_raw[2] is not None and (not isinstance(hunter_aim_raw[2], str) or not hunter_aim_raw[2]))
    ):
        raise ValueError("save has invalid Hunter's Aim intent")
    else:
        from .ranger import HunterAimIntent

        hunter_aim_intent = HunterAimIntent(*hunter_aim_raw)
    tumble_command = _family_command_from_data(data.get("tumble_command"))
    tumble_saved_check = _saved_check_from_data(data.get("tumble_saved_check"))
    tumble_distance = data.get("tumble_distance")
    tumble_origin_raw = data.get("tumble_origin")
    if tumble_origin_raw is None:
        tumble_origin = None
    elif (
        not isinstance(tumble_origin_raw, list) or len(tumble_origin_raw) != 2
        or any(type(value) is not int for value in tumble_origin_raw)
    ):
        raise ValueError("save has invalid Tumble Through origin")
    else:
        tumble_origin = Position(*tumble_origin_raw)
    quick_jump_saved_check = _saved_check_from_data(data.get("quick_jump_saved_check"))
    paired_strike = _paired_strike_from_data(data.get("paired_strike"))
    sudden_charge_path_raw = data.get("sudden_charge_second_path", [])
    if (
        not isinstance(sudden_charge_path_raw, list)
        or any(
            not isinstance(point, list) or len(point) != 2
            or any(type(value) is not int for value in point)
            for point in sudden_charge_path_raw
        )
    ):
        raise ValueError("save has invalid Sudden Charge second path")
    sudden_charge_first_path_raw = data.get("sudden_charge_first_path", [])
    if (
        not isinstance(sudden_charge_first_path_raw, list)
        or any(
            not isinstance(point, list) or len(point) != 2
            or any(type(value) is not int for value in point)
            for point in sudden_charge_first_path_raw
        )
    ):
        raise ValueError("save has invalid Sudden Charge first path")
    sudden_charge_origin_raw = data.get("sudden_charge_origin")
    if sudden_charge_origin_raw is None:
        sudden_charge_origin = None
    elif (
        not isinstance(sudden_charge_origin_raw, list)
        or len(sudden_charge_origin_raw) != 2
        or any(type(value) is not int for value in sudden_charge_origin_raw)
    ):
        raise ValueError("save has invalid Sudden Charge origin")
    else:
        sudden_charge_origin = Position(*sudden_charge_origin_raw)
    sudden_charge_origin_diagonals = data.get("sudden_charge_origin_diagonals")
    if sudden_charge_origin_diagonals is not None and (
        type(sudden_charge_origin_diagonals) is not int
        or sudden_charge_origin_diagonals < 0
    ):
        raise ValueError("save has invalid Sudden Charge diagonal state")
    movement_origin_raw = data.get("movement_origin")
    if movement_origin_raw is None:
        movement_origin = None
    elif (
        not isinstance(movement_origin_raw, list)
        or len(movement_origin_raw) != 2
        or any(type(value) is not int for value in movement_origin_raw)
    ):
        raise ValueError("save has invalid movement reaction origin")
    else:
        movement_origin = Position(*movement_origin_raw)
    no_escape_reactor_id = data.get("no_escape_reactor_id")
    no_escape_remaining_speed_ft = data.get("no_escape_remaining_speed_ft")
    if no_escape_reactor_id is not None and (
        not isinstance(no_escape_reactor_id, str) or not no_escape_reactor_id
    ):
        raise ValueError("save has invalid No Escape reactor")
    if no_escape_remaining_speed_ft is not None and (
        type(no_escape_remaining_speed_ft) is not int
        or no_escape_remaining_speed_ft < 0
    ):
        raise ValueError("save has invalid No Escape remaining Speed")
    if (no_escape_reactor_id is None) != (no_escape_remaining_speed_ft is None):
        raise ValueError("save has incomplete No Escape continuation")
    stunning_blows_target_id = data.get("stunning_blows_target_id")
    if stunning_blows_target_id is not None and (
        not isinstance(stunning_blows_target_id, str) or not stunning_blows_target_id
    ):
        raise ValueError("save has invalid Stunning Blows target")
    bomber_only_primary_splash = data.get("bomber_only_primary_splash", False)
    if type(bomber_only_primary_splash) is not bool:
        raise ValueError("save has invalid Bomber splash scope")
    if tumble_distance is not None and (type(tumble_distance) is not int or tumble_distance < 0):
        raise ValueError("save has invalid Tumble Through movement distance")
    if tumble_command is not None and type(tumble_command).__name__ != "TumbleThrough":
        raise ValueError("save has an unsupported Tumble Through continuation command")
    if tumble_saved_check is not None and tumble_saved_check.context.statistic != "acrobatics":
        raise ValueError("save has an invalid Tumble Through continuation check")
    if tumble_origin is not None and (
        kind != "movement" or optional_strings["stage"] != "tumble_through_lead_in"
    ):
        raise ValueError("save has Tumble Through origin on an invalid continuation")
    if quick_jump_saved_check is not None and quick_jump_saved_check.context.statistic != "athletics":
        raise ValueError("save has an invalid Quick Jump continuation check")
    quick_jump_kind = optional_strings["movement_kind"] in {
        "quick_jump", "quick_jump_critical_failure",
    }
    if quick_jump_kind != (quick_jump_saved_check is not None):
        raise ValueError("save has inconsistent Quick Jump continuation provenance")
    if quick_jump_saved_check is not None and kind != "movement":
        raise ValueError("save has Quick Jump facts on a non-movement continuation")
    sudden_charge_present = bool(sudden_charge_path_raw) or sudden_charge_origin is not None
    if sudden_charge_present and (
        kind != "movement"
        or optional_strings["movement_kind"] != "sudden_charge"
        or sudden_charge_origin is None
        or not path_data
        or not sudden_charge_path_raw
        or optional_strings["stage"] not in {"first_stride", "second_stride"}
    ):
        raise ValueError("save has invalid Sudden Charge continuation facts")
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
        spell_area_direction=spell_area_direction,
        widen_spell_area_length_ft=widen_spell_area_length_ft,
        spell_mode=optional_strings["spell_mode"],
        hunter_aim_intent=hunter_aim_intent,
        reach_spell_effective_range_ft=reach_spell_effective_range_ft,
        ranged_penalty=integers["ranged_penalty"],
        guidance_bonus=integers["guidance_bonus"],
        feint_off_guard_applied=_required_bool(data, "feint_off_guard_applied"),
        guidance_checked=_required_bool(data, "guidance_checked"),
        divine_grace_checked=(
            _required_bool(data, "divine_grace_checked")
            if "divine_grace_checked" in data else False
        ),
        divine_grace_used=(
            _required_bool(data, "divine_grace_used")
            if "divine_grace_used" in data else False
        ),
        stage=optional_strings["stage"],
        parent_continuation=_continuation_from_data(data.get("parent_continuation")),
        attack_count_committed=_required_bool(data, "attack_count_committed"),
        attack_target_off_guard=_required_bool(data, "attack_target_off_guard"),
        nimble_dodge_decided=_required_bool(data, "nimble_dodge_decided"),
        nimble_dodge_used=_required_bool(data, "nimble_dodge_used"),
        reactive_shield_decided=(
            _required_bool(data, "reactive_shield_decided")
            if "reactive_shield_decided" in data else False
        ),
        overextending_feint_penalty=overextending_feint_penalty,
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
        tumble_command=tumble_command,
        tumble_saved_check=tumble_saved_check,
        tumble_distance=tumble_distance,
        tumble_origin=tumble_origin,
        quick_jump_saved_check=quick_jump_saved_check,
        light_control=optional_strings["light_control"],
        light_point=light_point,
        light_color=optional_strings["light_color"],
        light_attachment_actor_id=optional_strings["light_attachment_actor_id"],
        light_replacement_orb_id=optional_strings["light_replacement_orb_id"],
        light_orb_id=optional_strings["light_orb_id"],
        paired_strike=paired_strike,
        sudden_charge_second_path=tuple(Position(*point) for point in sudden_charge_path_raw),
        sudden_charge_first_path=tuple(Position(*point) for point in sudden_charge_first_path_raw),
        sudden_charge_origin=sudden_charge_origin,
        sudden_charge_origin_diagonals=sudden_charge_origin_diagonals,
        movement_origin=movement_origin,
        no_escape_reactor_id=no_escape_reactor_id,
        no_escape_remaining_speed_ft=no_escape_remaining_speed_ft,
        stunning_blows_target_id=stunning_blows_target_id,
        bomber_only_primary_splash=bomber_only_primary_splash,
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
        "item_id": resolution.item_id,
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
        "shield_block_magic": resolution.shield_block_magic,
        "justice_checked": resolution.justice_checked,
        "justice_actor_id": resolution.justice_actor_id,
        "justice_protected": resolution.justice_protected,
        "life_link_effect_id": resolution.life_link_effect_id,
        "life_link_source_actor_id": resolution.life_link_source_actor_id,
        "life_link_transfer": resolution.life_link_transfer,
        "bomber_only_primary_splash": resolution.bomber_only_primary_splash,
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
            "magic": resolution.shield_block_record.magic,
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
    item_id = data.get("item_id")
    spell_id = data.get("spell_id")
    for name, value in (("attack_id", attack_id), ("item_id", item_id), ("spell_id", spell_id)):
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
    shield_block_magic = data.get("shield_block_magic", False)
    if shield_block_status is not None and (
        not isinstance(shield_block_status, str)
        or shield_block_status not in {"pending", "applied", "declined"}
    ):
        raise ValueError("save has invalid Shield Block status")
    if shield_block_instance_id is not None and (
        not isinstance(shield_block_instance_id, str) or not shield_block_instance_id
    ):
        raise ValueError("save has invalid Shield Block item identity")
    if type(shield_block_magic) is not bool:
        raise ValueError("save has invalid Shield Block source")
    shield_block_raw = data.get("shield_block_record")
    shield_block_record = None
    if shield_block_raw is not None:
        if not isinstance(shield_block_raw, dict):
            raise ValueError("save has invalid Shield Block record")
        shield_block_instance = _required_str(shield_block_raw, "shield_instance_id")
        shield_block_magic_record = shield_block_raw.get("magic", False)
        if type(shield_block_magic_record) is not bool:
            raise ValueError("save has invalid Shield Block source")
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
            shield_block_instance, **shield_block_values, magic=shield_block_magic_record
        )
    if (
        (shield_block_status == "applied") != (shield_block_record is not None)
        or (shield_block_status == "pending") != ((shield_block_magic or shield_block_instance_id is not None) and shield_block_record is None)
        or (shield_block_status == "declined" and not (shield_block_magic or shield_block_instance_id is not None))
        or (shield_block_record is not None and not shield_block_magic and shield_block_instance_id != shield_block_record.shield_instance_id)
        or (shield_block_record is not None and shield_block_magic != shield_block_record.magic)
        or (shield_block_status is None and shield_block_instance_id is not None)
        or (shield_block_status is None and shield_block_magic)
    ):
        raise ValueError("save has inconsistent Shield Block continuation data")
    if shield_block_record is not None:
        record = shield_block_record
        if (
            record.hardness <= 0
            or record.shield_vulnerable_damage > record.incoming_damage
            or record.prevented_from_actor != min(record.incoming_damage, record.hardness)
            or record.damage_to_actor != record.incoming_damage - record.prevented_from_actor
            or (not record.magic and record.damage_to_shield != max(0, record.shield_vulnerable_damage - record.hardness))
            or (not record.magic and record.shield_hp_after != max(0, record.shield_hp_before - record.damage_to_shield))
            or (record.magic and (record.shield_instance_id != "magic_shield" or record.shield_vulnerable_damage != 0 or record.damage_to_shield != 0 or record.shield_hp_before != 0 or record.shield_hp_after != 0))
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
    life_link_effect_id = data.get("life_link_effect_id")
    life_link_source_actor_id = data.get("life_link_source_actor_id")
    life_link_transfer = data.get("life_link_transfer", 0)
    bomber_only_primary_splash = data.get("bomber_only_primary_splash", False)
    if type(bomber_only_primary_splash) is not bool:
        raise ValueError("save has invalid Bomber splash scope")
    if (
        (life_link_effect_id is not None and (not isinstance(life_link_effect_id, str) or not life_link_effect_id))
        or (life_link_source_actor_id is not None and (not isinstance(life_link_source_actor_id, str) or not life_link_source_actor_id))
        or type(life_link_transfer) is not int
        or not 0 <= life_link_transfer <= 3
        or (life_link_transfer == 0 and (life_link_effect_id is not None or life_link_source_actor_id is not None))
        or (life_link_transfer > 0 and (life_link_effect_id is None or life_link_source_actor_id is None))
    ):
        raise ValueError("save has invalid Life Link damage evidence")
    return DamageResolution(
        source_kind=source_kind,
        group=group,
        actor_id=actor_id,
        target_id=target_id,
        source=source,
        damage_type=damage_type,
        check=_check_from_data(data.get("check")),
        attack_id=attack_id,
        item_id=item_id,
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
        shield_block_magic=shield_block_magic,
        shield_block_record=shield_block_record,
        justice_checked=justice_checked,
        justice_actor_id=justice_actor_id,
        justice_protected=justice_protected,
        life_link_effect_id=life_link_effect_id,
        life_link_source_actor_id=life_link_source_actor_id,
        life_link_transfer=life_link_transfer,
        bomber_only_primary_splash=bomber_only_primary_splash,
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
        elif adjustment == "persistent_iwr":
            if not allow_mitigated or multiplier != 1:
                raise ValueError("save has inconsistent persistent mitigated damage")
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
