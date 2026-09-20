"""Public local encounter interface for the S1 rules boundary.

Initiative and turns follow Remaster Player Core pp. 435–436:
https://2e.aonprd.com/Rules.aspx?ID=2423
https://2e.aonprd.com/Rules.aspx?ID=2428
https://2e.aonprd.com/Rules.aspx?ID=2429
"""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Iterable, Mapping

from .checks import DegreeOfSuccess, Modifier, combine_modifiers, multiple_attack_penalty, resolve_check
from .conditions import ActionContext, CheckContext, ConditionValue, condition_modifiers, condition_restrictions
from .content import S1_SETUP, get_definition, get_setup
from .rogue import (
    RogueRacket,
    WeaponCategory,
    nimble_dodge_modifier,
    sneak_attack_damage_term,
    surprise_attack_applies,
)
from .investigator import (
    ATTACK_STRATAGEM,
    FORENSIC_ACUMEN_ABILITY,
    intelligence_substitution_eligible,
    person_of_interest_grant_allows_free_devise,
    resolve_stratagem_check,
    strategic_strike_damage_term,
    stratagem_for_attack,
    consume_stratagem,
    skill_stratagem_blocks_strike,
)
from .damage import (
    DamageComponent,
    DamageDefense,
    DamageGroup,
    DamagePacket,
    DamagePartRef,
    DamageResult,
    DamageTerm,
    DefenseChoice,
    DefenseSelection,
    apply_damage_defenses,
    damage_defense_choices,
    resolve_damage,
    roll_damage_terms,
    absorb_temporary_hp,
)
from .model import (
    ActionContinuation,
    ActionOptions,
    ActionResult,
    ActorView,
    ChoiceOption,
    ChoiceView,
    Choose,
    Crawl,
    Cast,
    LingeringComposition,
    ReachSpell,
    WidenSpell,
    EnergyAblation,
    Sustain,
    Dismiss,
    Command,
    CreatureState,
    EncounterSetup,
    EncounterState,
    EndTurn,
    EffectView,
    EffectExpiration,
    ActiveConditionEffect,
    Event,
    Flee,
    FamilyCommand,
    FamilyProcedureContext,
    FamilyProcedureResult,
    PairedStrikeOutcome,
    HealthMode,
    Interact,
    Inspection,
    PendingChoice,
    Position,
    PreparedSlotState,
    SpellSubstitutionState,
    PreparedSlotView,
    SpontaneousSlotState,
    SpontaneousSlotView,
    RaiseShield,
    RaisedShieldState,
    ShieldBlockRecord,
    ShieldView,
    SpellOption,
    SpellTargetOption,
    ActiveSpellEffect,
    GiantCentipedeVenomAffliction,
    PersistentDamageEffect,
    ActiveItemSpellEffect,
    GuidanceImmunity,
    LightOrb,
    ResultStatus,
    Release,
    Stand,
    Step,
    StrikeOption,
    Strike,
    QuickBomber,
    QuickAlchemy,
    ActivateAlchemy,
    AttackDefinition,
    Stride,
    ViciousSwing,
    TakeCover,
    DismissCover,
    DamageResolution,
    is_combat_capable,
)
from .persistence import DiceSource, DiceSourceError, load_encounter, save_encounter
from .spellshape import clear_pending_spellshape, has_pending_spellshape
from .space import (
    flanking_geometry,
    grid_distance_feet,
    in_bounds,
    is_adjacent,
    segment_crosses_cell_interior,
    step_cost,
)


_CARRYABLE_W2_ALCHEMY_EFFECT_KINDS = frozenset({
    "alchemy_cheetahs_elixir_lesser",
    "alchemy_bravos_brew_lesser",
    "alchemy_juggernaut_mutagen_lesser",
})
_ALCHEMY_TEMP_HP_CHOICES = frozenset({"keep_existing", "gain_new"})
from .health import (
    HealthState,
    HealthTransition,
    UnsupportedHealthRuleError,
    can_use_heroic_recovery,
    damage as pc_damage,
    healing as pc_healing,
    heroic_recovery,
    recovery_check,
    stabilize as pc_stabilize,
)
from .items import (
    SHIELD_IMMUNE_DAMAGE_TYPES,
    STEEL_SHIELD,
    ItemInstance,
    armor_item_ac_bonus,
    armor_resilient_modifier,
    shield_ac_modifier,
    shield_block_result,
    shield_block_trigger_eligible,
    shield_integrity,
    weapon_potency_modifier,
    weapon_rune_dice,
    runtime_item_instance_id,
)
from .rune_content import (
    ITEM_CATEGORIES,
    armor_rune_profile_for_item,
    is_drawable_equipment_definition,
    weapon_rune_profile_for_item,
)
from .spells import (
    CONCEALMENT_TARGETED_SPELL_IDS,
    SPELLS,
    basic_save_damage,
    basic_save_damage_result,
    divine_lance_damage,
    heal_range_ft,
    heal_roll,
    in_heal_emanation,
    soothe_roll,
    spell_traits,
    telekinetic_projectile_object_profile,
    void_warp_effect,
)
from .fleeing import choose_flee_route
from .swashbuckler import effective_speed_ft, precise_strike_damage_term
from .areas import Footprint, cone_cells


@dataclass(frozen=True)
class _DamageHealthResult:
    damage: DamageResult
    temporary_hp_absorbed: int
    remaining_hp_damage: int
    defeated: bool
    shield_block: ShieldBlockRecord | None = None


_MAGIC_SHIELD_BLOCK = "magic_shield"


class Encounter:
    """An in-memory encounter. Each command commits atomically on completion."""

    def __init__(self, state: EncounterState, dice: DiceSource) -> None:
        self._state = state
        self._dice = dice

    @classmethod
    def start(
        cls,
        setup: EncounterSetup = S1_SETUP,
        *,
        seed: int = 0,
        rolls: Iterable[int] | None = None,
    ) -> "Encounter":
        """Start a fixture with seeded automatic dice or supplied die faces.

        ``rolls`` contains individual d20 and damage-die faces in exact draw
        order. When supplied it is the active provider; ``seed`` is ignored.
        NPC–NPC initiative ties use the setup's stable order policy.
        """
        _validate_setup(setup)
        dice = DiceSource(seed=seed, rolls=rolls)
        creatures, item_instances = cls._fresh_creatures_for_setup(setup)
        state = EncounterState(
            setup_id=setup.setup_id,
            map_width=setup.width,
            map_height=setup.height,
            creatures=creatures,
            initiative_order=[],
            active_index=0,
            initiative_finalized=False,
            initiative_skills={
                placement.actor_id: placement.initiative_skill
                for placement in setup.placements
            },
            initiative_contexts={
                placement.actor_id: placement.initiative_context
                for placement in setup.placements
            },
            item_instances=item_instances,
            actor_start_counts={placement.actor_id: 0 for placement in setup.placements},
            actor_end_counts={placement.actor_id: 0 for placement in setup.placements},
            ambient_light=setup.ambient_light,
            preparation_day=1,
            rested_actor_ids=set(),
            last_prepared_day={
                placement.actor_id: 1
                for placement in setup.placements
                if HealthMode(get_definition(placement.definition_id).health_mode) is HealthMode.PC
            },
        )
        cls._initialize_bomber_alchemy(state)
        # The selected Champion's divine aura begins active and is removed
        # explicitly by suppression or unconsciousness.
        state.justice_aura_active = {
            placement.actor_id
            for placement in setup.placements
            if "justice_champion" in get_definition(placement.definition_id).abilities
        }
        # All initial initiative checks are ranked by d20 + their authored
        # statistic modifier only; no degree-of-success or natural-die
        # adjustment applies to initiative.
        for placement in setup.placements:
            definition = get_definition(placement.definition_id)
            if definition.initiative_exempt:
                continue
            initiative_skill = placement.initiative_skill
            modifier = cls._initiative_modifier_for_definition(
                definition, initiative_skill,
                weather_perception_penalty=(0 if "storm_born" in definition.abilities else setup.weather_perception_circumstance_penalty),
            )
            creatures[placement.actor_id].initiative = dice.draw(20) + modifier
        encounter = cls(state, dice)
        encounter._continue_initiative_initialization(state)
        return encounter

    @staticmethod
    def _fresh_creatures_for_setup(
        setup: EncounterSetup,
    ) -> tuple[dict[str, CreatureState], dict[str, ItemInstance]]:
        """Build new actors and stable item instances for an authored setup."""
        try:
            from .barbarian_content import BARBARIAN_INITIAL_STATES
        except ModuleNotFoundError as error:
            if error.name != f"{__package__}.barbarian_content":
                raise
            BARBARIAN_INITIAL_STATES = {}
        creatures: dict[str, CreatureState] = {}
        item_instances: dict[str, ItemInstance] = {}
        for placement in setup.placements:
            definition = get_definition(placement.definition_id)
            initial_item_instances: dict[str, ItemInstance] = {}
            for item in definition.item_instances:
                instance_id = runtime_item_instance_id(placement.actor_id, item.instance_id)
                if instance_id in item_instances:
                    raise ValueError(f"duplicate item instance {instance_id!r}")
                instance = replace(item, instance_id=instance_id)
                item_instances[instance_id] = instance
                initial_item_instances[item.instance_id] = instance

            def locate(local_item_id: str) -> str:
                instance = initial_item_instances.get(local_item_id)
                return instance.instance_id if instance is not None else local_item_id

            held_items = [locate(item_id) for item_id in definition.held_items]
            worn_items = [locate(item_id) for item_id in definition.worn_items]
            stowed_items = [locate(item_id) for item_id in definition.stowed_items]
            explicitly_located = set(held_items + worn_items + stowed_items)
            # Existing shield definitions rely on an authored instance defaulting
            # to held. Keep that convention for every unplaced fixed grant.
            held_items.extend(
                item.instance_id
                for item in initial_item_instances.values()
                if item.instance_id not in explicitly_located
            )
            creatures[placement.actor_id] = CreatureState(
                actor_id=placement.actor_id,
                definition_id=placement.definition_id,
                label=placement.label,
                team=placement.team,
                position=placement.position,
                hp=definition.hp,
                health_mode=HealthMode(definition.health_mode),
                hero_points=definition.hero_points,
                held_items=held_items,
                worn_items=worn_items,
                stowed_items=stowed_items,
                ammunition=dict(definition.ammunition),
                prepared_slots=[
                    PreparedSlotState(
                        slot.slot_id, slot.source, slot.spell_id,
                        slot.rank, slot.cantrip, False,
                    )
                    for slot in definition.prepared_spells
                ],
                spontaneous_slots=[
                    SpontaneousSlotState(
                        slot.slot_id, slot.source, slot.rank, slot.capacity, slot.capacity,
                    )
                    for slot in definition.spontaneous_slots
                ],
            focus_points=definition.focus_points,
            focus_capacity=definition.focus_capacity,
            barbarian_state=BARBARIAN_INITIAL_STATES.get(
                definition.definition_id,
                # The two level-two Bear sheets retain exactly the accepted
                # level-one Bear instinct state; their new feat is a literal
                # definition ability, not a new Barbarian build selector.
                BARBARIAN_INITIAL_STATES.get("barbarian_animal_bear")
                if definition.definition_id in {
                    "barbarian_animal_bear_level_2_no_escape",
                    "barbarian_animal_bear_level_2_sudden_charge",
                    "barbarian_animal_bear_level_2_intimidating_strike",
                }
                else None,
            ),
            )
        return creatures, item_instances

    @classmethod
    def load(cls, path: str | Path) -> "Encounter":
        state, dice = load_encounter(path)
        encounter = cls(state, dice)
        encounter._validate_pending_context()
        return encounter

    def _validate_quick_jump_continuation(
        self, state: EncounterState, continuation: ActionContinuation
    ) -> None:
        """Authenticate a saved Quick Jump landing before a reaction resumes it."""
        saved = continuation.quick_jump_saved_check
        quick_kind = continuation.movement_kind in {
            "quick_jump", "quick_jump_critical_failure",
        }
        if saved is None:
            if quick_kind:
                raise ValueError("save has Quick Jump movement without its committed check")
            return
        actor = state.creatures.get(continuation.actor_id)
        if actor is None or continuation.kind != "movement" or not quick_kind:
            raise ValueError("save has Quick Jump facts on an invalid continuation")
        definition = get_definition(actor.definition_id)
        if "Quick Jump" not in definition.feats or actor.prone:
            raise ValueError("save has an unavailable Quick Jump continuation")
        from .skill_content import QUICK_JUMP
        from .martial_defense import crane_stance_leap_bonus

        expected = self._prepare_skill_check(
            state, actor, "athletics",
            15 - crane_stance_leap_bonus(state, actor.actor_id),
            traits=QUICK_JUMP.traits,
        )
        result = saved.result
        if (
            saved.check_owner_actor_id != actor.actor_id
            or saved.context != expected.context
            or saved.dc != expected.dc
            or saved.modifiers != expected.modifiers
            or saved.pre_roll_choices != expected.pre_roll_choices
            or result is None
            or continuation.next_step < 0
            or continuation.next_step > len(continuation.path)
            or not continuation.path
            or not 0 <= actor.actions_remaining <= 2
        ):
            raise ValueError("save has inconsistent Quick Jump check provenance")
        speed = effective_speed_ft(actor, definition, self._conditions_for_actor(state, actor))
        if speed < 15:
            raise ValueError("save has Quick Jump below its required Speed")
        leap_bonus = crane_stance_leap_bonus(state, actor.actor_id)
        normal_leap = (15 if speed >= 30 else 10) + leap_bonus
        maximum = (
            min((result.total // 5) * 5 + leap_bonus, speed)
            if result.degree >= DegreeOfSuccess.SUCCESS
            else normal_leap
        )
        expected_kind = (
            "quick_jump_critical_failure"
            if result.degree is DegreeOfSuccess.CRITICAL_FAILURE
            else "quick_jump"
        )
        if continuation.movement_kind != expected_kind or len(continuation.path) * 5 > maximum:
            raise ValueError("save has inconsistent Quick Jump landing result")
        for index, point in enumerate(continuation.path):
            if not in_bounds(point, state.map_width, state.map_height):
                raise ValueError("save has an out-of-bounds Quick Jump path")
            if index:
                previous = continuation.path[index - 1]
                if abs(point.x - previous.x) + abs(point.y - previous.y) != 1:
                    raise ValueError("save has a noncontiguous Quick Jump path")
        if continuation.next_step == 0:
            prior = actor.position
        else:
            prior = continuation.path[continuation.next_step - 1]
            if actor.position != prior:
                raise ValueError("save has an inconsistent Quick Jump progress position")
        for point in continuation.path[continuation.next_step:]:
            if abs(point.x - prior.x) + abs(point.y - prior.y) != 1:
                raise ValueError("save has an invalid remaining Quick Jump path")
            prior = point

    def _validate_committed_reach_spell_range(
        self, state: EncounterState, continuation: ActionContinuation
    ) -> None:
        """Reject a saved cast whose shaped range was not actually committed."""
        committed = continuation.reach_spell_effective_range_ft
        if committed is None:
            return
        caster = state.creatures.get(continuation.actor_id)
        if (
            caster is None
            or continuation.kind != "cast"
            or continuation.spell_id not in SPELLS
            or has_pending_spellshape(caster)
        ):
            raise ValueError("save has invalid committed Reach Spell range")
        definition = get_definition(caster.definition_id)
        from .reach_spell import can_shape_spell

        spell = SPELLS[continuation.spell_id]
        expected = self._effective_reach_spell_range(
            continuation.spell_id, continuation.spell_actions, reach_ready=True,
        )
        if (
            "reach_spell" not in definition.abilities
            or "Reach Spell" not in definition.feats
            or not can_shape_spell(spell, spell_actions=continuation.spell_actions)
            or expected is None
            or committed != expected
        ):
            raise ValueError("save has forged or unsupported committed Reach Spell range")

    def _validate_committed_widen_spell_area(
        self, state: EncounterState, continuation: ActionContinuation
    ) -> None:
        """Reject a saved cast whose widened cone was not actually committed."""
        committed = continuation.widen_spell_area_length_ft
        if committed is None:
            return
        caster = state.creatures.get(continuation.actor_id)
        if (
            caster is None
            or continuation.kind != "cast"
            or continuation.spell_id not in SPELLS
            or has_pending_spellshape(caster)
        ):
            raise ValueError("save has invalid committed Widen Spell area")
        definition = get_definition(caster.definition_id)
        from .widen_spell import widened_cone_length

        expected = widened_cone_length(
            SPELLS[continuation.spell_id], spell_actions=continuation.spell_actions,
        )
        if (
            "widen_spell" not in definition.abilities
            or "Widen Spell" not in definition.feats
            or expected is None
            or committed != expected
        ):
            raise ValueError("save has forged or unsupported committed Widen Spell area")

    def _validate_tumble_through_continuation(
        self, state: EncounterState, continuation: ActionContinuation
    ) -> None:
        """Authenticate the pre-check Tumble Through movement continuation."""
        lead_in = continuation.stage == "tumble_through_lead_in"
        retained = (
            continuation.tumble_command,
            continuation.tumble_saved_check,
            continuation.tumble_distance,
            continuation.tumble_origin,
        )
        if not lead_in:
            if any(item is not None for item in retained):
                raise ValueError("save has Tumble Through facts outside its lead-in")
            return
        from .skill_actions import (
            TumbleThrough,
            _tumble_path_cost,
            _tumble_target,
            is_swashbuckler,
            stylish_combatant_modifiers,
        )
        from .skill_content import TUMBLE_THROUGH
        command = continuation.tumble_command
        saved = continuation.tumble_saved_check
        origin = continuation.tumble_origin
        actor = state.creatures.get(continuation.actor_id)
        if (
            continuation.kind != "movement"
            or continuation.movement_kind != "tumble_through"
            or continuation.mode != "tumble_through"
            or not isinstance(command, TumbleThrough)
            or saved is None
            or origin is None
            or actor is None
            or continuation.target_id is None
            or continuation.tumble_distance is None
            or not in_bounds(origin, state.map_width, state.map_height)
            or continuation.next_step < 0
            or continuation.next_step > len(continuation.path)
        ):
            raise ValueError("save has incomplete Tumble Through lead-in facts")
        definition = get_definition(actor.definition_id)
        source = replace(actor, position=origin)
        context = FamilyProcedureContext(
            self, state, self._dice.clone(), source, definition, "martial", command=command,
        )
        try:
            target = _tumble_target(context, command.path)
            target_index = command.path.index(target.position)
            distance = _tumble_path_cost(context, command.path, target)
        except (NotImplementedError, ValueError) as error:
            raise ValueError("save has invalid Tumble Through lead-in path") from error
        traits = TUMBLE_THROUGH.traits if is_swashbuckler(definition) else frozenset({"move"})
        expected = self._prepare_skill_check(
            state, source, "acrobatics", context.skill_dc(target.actor_id, "reflex"),
            traits=traits,
            extra_modifiers=(stylish_combatant_modifiers(definition) if is_swashbuckler(definition) else ()),
        )
        if (
            continuation.target_id != target.actor_id
            or continuation.path != command.path[:target_index]
            or continuation.tumble_distance != distance
            or saved.check_owner_actor_id != source.actor_id
            or saved.context != expected.context
            or saved.dc != expected.dc
            or saved.modifiers != expected.modifiers
            or saved.result is not None
            or (continuation.next_step == 0 and actor.position != origin)
            or (
                continuation.next_step > 0
                and actor.position != continuation.path[continuation.next_step - 1]
            )
        ):
            raise ValueError("save has forged Tumble Through lead-in provenance")

    def _validate_sudden_charge_continuation(
        self, state: EncounterState, continuation: ActionContinuation,
    ) -> None:
        """Authenticate the paid Fighter/Barbarian two-Stride activity."""
        present = (
            bool(continuation.sudden_charge_first_path)
            or bool(continuation.sudden_charge_second_path)
            or continuation.sudden_charge_origin is not None
            or continuation.sudden_charge_origin_diagonals is not None
        )
        if not present:
            return
        actor = state.creatures.get(continuation.actor_id)
        if (
            actor is None
            or continuation.kind != "movement"
            or continuation.movement_kind != "sudden_charge"
            or continuation.stage not in {"first_stride", "second_stride"}
            or continuation.sudden_charge_origin is None
            or continuation.sudden_charge_origin_diagonals is None
            or not continuation.path
            or not continuation.sudden_charge_first_path
            or not continuation.sudden_charge_second_path
            or "sudden_charge" not in get_definition(actor.definition_id).abilities
            or actor.flourish_used_round != state.round_number
            or continuation.next_step < 0
            or continuation.next_step > len(continuation.path)
        ):
            raise ValueError("save has invalid Sudden Charge continuation")
        origin = continuation.sudden_charge_origin
        first_path = continuation.sudden_charge_first_path
        second_path = continuation.sudden_charge_second_path
        if continuation.path != (first_path if continuation.stage == "first_stride" else second_path):
            raise ValueError("save has inconsistent Sudden Charge active path")
        current = origin
        diagonals = continuation.sudden_charge_origin_diagonals
        limit = effective_speed_ft(
            actor, get_definition(actor.definition_id), self._conditions_for_actor(state, actor),
        )
        completed_diagonals = diagonals
        for path_index, path in enumerate((first_path, second_path)):
            spent = 0
            for point in path:
                if not in_bounds(point, state.map_width, state.map_height):
                    raise ValueError("save has an out-of-bounds Sudden Charge path")
                try:
                    cost, diagonal_count = step_cost(current, point, diagonals)
                except ValueError as error:
                    raise ValueError("save has a noncontiguous Sudden Charge path") from error
                spent += cost
                if spent > limit:
                    raise ValueError("save has an over-speed Sudden Charge stride")
                diagonals += diagonal_count
                current = point
            if path_index == 0:
                completed_diagonals = diagonals
        if continuation.stage == "first_stride":
            expected = origin if continuation.next_step == 0 else first_path[continuation.next_step - 1]
            expected_diagonals = continuation.sudden_charge_origin_diagonals
            prior = origin
            for point in first_path[:continuation.next_step]:
                _cost, diagonal_count = step_cost(prior, point, expected_diagonals)
                expected_diagonals += diagonal_count
                prior = point
        else:
            expected = first_path[-1] if continuation.next_step == 0 else second_path[continuation.next_step - 1]
            expected_diagonals = completed_diagonals
            prior = first_path[-1]
            for point in second_path[:continuation.next_step]:
                _cost, diagonal_count = step_cost(prior, point, expected_diagonals)
                expected_diagonals += diagonal_count
                prior = point
        if actor.position != expected or actor.diagonals_this_turn != expected_diagonals:
            raise ValueError("save has inconsistent Sudden Charge movement progress")

    def _validate_continuation_chain(
        self, state: EncounterState, continuation: ActionContinuation
    ) -> None:
        """Validate every retained parent action, not only the top reaction."""
        seen: set[int] = set()
        current: ActionContinuation | None = continuation
        while current is not None:
            if id(current) in seen:
                raise ValueError("save has a cyclic action continuation")
            seen.add(id(current))
            self._validate_quick_jump_continuation(state, current)
            self._validate_committed_reach_spell_range(state, current)
            self._validate_committed_widen_spell_area(state, current)
            self._validate_tumble_through_continuation(state, current)
            self._validate_sudden_charge_continuation(state, current)
            self._validate_no_escape_follow(state, current)
            current = current.parent_continuation

    def _validate_committed_strike_rider_effects(self, state: EncounterState) -> None:
        """Fail closed for saved effects created by the finite W3 rider seam."""
        for effect in state.condition_effects:
            if not effect.effect_id.startswith(("snagging_strike:", "combat_grab:", "brutish_shove:")):
                continue
            source = state.creatures.get(effect.source_actor_id)
            target = state.creatures.get(effect.target_actor_id)
            if source is None or target is None:
                raise ValueError("save has a Fighter rider with a missing creature")
            abilities = get_definition(source.definition_id).abilities
            if effect.effect_id.startswith("snagging_strike:"):
                if (
                    "snagging_strike" not in abilities or effect.kind != "off_guard" or effect.value != 1
                    or effect.expiration != EffectExpiration(source.actor_id, "start", state.actor_start_counts.get(source.actor_id, 0) + 1)
                    or grid_distance_feet(source.position, target.position) > 5
                ):
                    raise ValueError("save has invalid Snagging Strike effect")
            elif effect.effect_id.startswith("combat_grab:"):
                if (
                    "combat_grab" not in abilities or effect.kind != "grabbed" or effect.value != 1
                    or effect.expiration.boundary != "end" or effect.expiration.anchor_actor_id != source.actor_id
                    or effect.dc != self._skill_dc(state, source.actor_id, "athletics")
                    or effect.expiration.occurrence > state.actor_end_counts.get(source.actor_id, 0) + 2
                ):
                    raise ValueError("save has invalid Combat Grab effect")
            elif (
                "brutish_shove" not in abilities or effect.kind != "off_guard" or effect.value != 1
                or effect.expiration != EffectExpiration(source.actor_id, "end", state.actor_end_counts.get(source.actor_id, 0) + 1)
            ):
                raise ValueError("save has invalid Brutish Shove effect")

    def _validate_pending_context(self) -> None:
        """Reject saved choices whose continuation no longer matches engine state."""
        state = self._state
        self._validate_committed_strike_rider_effects(state)
        pending = state.pending_choice
        if pending is None:
            return
        if pending.continuation is not None:
            self._validate_continuation_chain(state, pending.continuation)
        if pending.kind in {"stunning_blows", "stunning_blows_hero_reroll"}:
            continuation = pending.continuation
            monk = state.creatures.get(pending.actor_id or "")
            target = state.creatures.get(pending.target_id or "")
            if (
                continuation is None or monk is None or target is None
                or continuation.kind != "paired_strike"
                or continuation.stunning_blows_target_id != target.actor_id
                or self._stunning_blows_target(state, monk, continuation.paired_strike) != target
            ):
                raise ValueError("save has an unavailable Stunning Blows choice")
            if pending.kind == "stunning_blows":
                if (
                    pending.owner_actor_id != monk.actor_id
                    or pending.options != (
                        ChoiceOption("attempt", "Attempt Fortitude save"),
                        ChoiceOption("decline", "Decline"),
                    )
                ):
                    raise ValueError("save has an inconsistent Stunning Blows choice")
                return
            check = pending.check
            if (
                pending.owner_actor_id != target.actor_id
                or target.health_mode is not HealthMode.PC or target.hero_points < 1
                or pending.check_kind != "stunning_blows_save"
                or pending.check_owner_actor_id != target.actor_id
                or pending.options != (
                    ChoiceOption("keep", "Keep"), ChoiceOption("spend_hero_point", "Spend Hero Point"),
                )
                or check is None
            ):
                raise ValueError("save has an inconsistent Stunning Blows Hero choice")
            expected = self._stunning_blows_save(
                state, None, monk, target, continuation, die=check.die,
            )
            if check != expected:
                raise ValueError("save has an inconsistent Stunning Blows Fortitude save")
            return
        if pending.kind == "no_escape":
            continuation = pending.continuation
            mover = state.creatures.get(pending.actor_id or "")
            reactor = state.creatures.get(pending.owner_actor_id or "")
            eligible = (
                continuation is not None and mover is not None and reactor is not None
                and continuation.kind == "movement"
                and continuation.actor_id == mover.actor_id
                and continuation.no_escape_reactor_id is None
                and continuation.no_escape_remaining_speed_ft is None
                and pending.target_id == reactor.actor_id
                and pending.options == (
                    ChoiceOption("pursue", "Use No Escape"),
                    ChoiceOption("decline", "Decline"),
                )
                and continuation.movement_origin is not None
                and self._no_escape_reactor(
                    state, mover, continuation, include_seen=True,
                ) == reactor
            )
            if not eligible:
                raise ValueError("save has an unavailable or inconsistent No Escape reaction")
            return
        if pending.kind in {"counter_performance_save_choice", "counter_performance_bard_hero_reroll"}:
            caster = state.creatures.get(pending.actor_id or "")
            target = state.creatures.get(pending.target_id or "")
            continuation = pending.continuation
            check = pending.check
            if (
                caster is None or target is None or continuation is None or check is None
                or continuation.kind != "cast" or continuation.actor_id != caster.actor_id
                or continuation.spell_id != "command" or pending.spell_id != "command"
                or pending.slot_id != continuation.slot_id or pending.spell_actions != continuation.spell_actions
                or target.dead or target.defeated or "Common" not in get_definition(target.definition_id).languages
            ):
                raise ValueError("save has an incomplete Counter Performance Command choice")
            command_check = (
                continuation.spell_check
                if pending.kind == "counter_performance_bard_hero_reroll"
                else pending.check
            )
            if command_check is None:
                raise ValueError("save has no committed Command save for Counter Performance")
            self._validate_committed_command_save(state, caster, target, continuation, command_check)
            if pending.kind == "counter_performance_save_choice":
                reactor = self._counter_performance_reactor(state, target)
                expected = []
                if reactor is not None:
                    expected.append(ChoiceOption("counter_performance", f"Use {reactor.label}'s Counter Performance"))
                if target.health_mode is HealthMode.PC and target.hero_points > 0:
                    expected.append(ChoiceOption("spend_hero_point", "Spend 1 Hero Point and reroll"))
                expected.append(ChoiceOption("keep", "Keep result"))
                if (
                    pending.owner_actor_id != target.actor_id
                    or pending.check_owner_actor_id != target.actor_id
                    or pending.check_kind != "counter_performance_save"
                    or pending.options != tuple(expected)
                    or "auditory" not in spell_traits("command")
                ):
                    raise ValueError("save has an unavailable Counter Performance save choice")
                return
            bard = state.creatures.get(pending.owner_actor_id or "")
            original = continuation.spell_check
            active_actor_id = state.initiative_order[state.active_index] if state.initiative_order else None
            active_start = state.actor_start_counts.get(active_actor_id or "", 0)
            performance_modifier = next(
                (modifier for skill, _rank, modifier in get_definition(bard.definition_id).skills if skill == "performance"),
                None,
            ) if bard is not None else None
            expected_performance = (
                replace(
                    resolve_check(check.die, performance_modifier, original.dc),
                    modifier_breakdown=(Modifier(performance_modifier, "untyped", "printed Performance modifier"),),
                )
                if check is not None and original is not None and performance_modifier is not None else None
            )
            if (
                bard is None or original is None or pending.check_owner_actor_id != bard.actor_id
                or pending.check_kind != "counter_performance_check"
                or pending.options != (
                    ChoiceOption("keep", "Keep Performance result"),
                    ChoiceOption("spend_hero_point", "Spend 1 Hero Point and reroll Performance"),
                )
                or bard.hero_points < 1 or not any(item.spell_id == "counter_performance" for item in get_definition(bard.definition_id).focus_spells)
                or "counter_performance_singing" not in get_definition(bard.definition_id).abilities
                or bard.team != target.team or bard.dead or bard.unconscious or bard.defeated
                or bard.reaction_available or not 0 <= bard.focus_points < bard.focus_capacity
                or active_actor_id != caster.actor_id
                or (bard.composition_cast_turn_actor_id, bard.composition_cast_turn_start) != (active_actor_id, active_start)
                or grid_distance_feet(bard.position, target.position) > 60
                or continuation.stage != "counter_performance"
                or check != expected_performance
            ):
                raise ValueError("save has an unavailable Counter Performance Hero choice")
            return
        if pending.kind == "witch_restored_spirit":
            actor = state.creatures.get(pending.actor_id or "")
            if (
                actor is None
                or pending.owner_actor_id != actor.actor_id
                or tuple(option.option_id for option in pending.options) != pending.target_ids
                or not state.initiative_finalized
                or not state.initiative_order
                or state.initiative_order[state.active_index] != actor.actor_id
                or actor.dead or actor.unconscious
                or "restored_spirit" not in self._definition_abilities(actor)
            ):
                raise ValueError("save has an unavailable Restored Spirit choice")
            familiar = next(
                (candidate for candidate in state.creatures.values()
                 if self._familiar_owned_by(actor, candidate)
                 and not candidate.dead and not candidate.unconscious),
                None,
            )
            expected = tuple(
                candidate.actor_id for candidate in state.creatures.values()
                if not candidate.dead
                and not candidate.unconscious
                and familiar is not None
                and grid_distance_feet(familiar.position, candidate.position) <= 15
            )
            if familiar is None or pending.target_ids != expected:
                raise ValueError("save has stale Restored Spirit recipients")
            return
        if pending.kind == "witch_restored_spirit_timing":
            actor = state.creatures.get(pending.actor_id or "")
            continuation = pending.continuation
            familiar, recipients = self._restored_spirit_recipients(state, actor) if actor is not None else (None, ())
            before_recipients = (
                tuple(state.creatures[actor_id] for actor_id in continuation.target_ids)
                if continuation is not None and continuation.kind == "witch_patrons_puppet"
                and all(actor_id in state.creatures for actor_id in continuation.target_ids)
                else recipients
            )
            expected_options = (
                ChoiceOption("after", "After the hex"),
                *tuple(ChoiceOption(f"before:{candidate.actor_id}", f"Before the hex: {candidate.label}") for candidate in before_recipients),
            )
            if (
                actor is None or pending.owner_actor_id != actor.actor_id
                or continuation is None
                or continuation.kind not in {"cast", "witch_sustain_stoke", "witch_patrons_puppet"}
                or continuation.actor_id != actor.actor_id or continuation.spell_id != "stoke_the_heart"
                or pending.spell_id != "stoke_the_heart" or pending.spell_actions != 1
                or familiar is None or pending.target_ids != tuple(candidate.actor_id for candidate in before_recipients)
                or pending.options != expected_options
                or (
                    continuation.kind == "witch_patrons_puppet"
                    and type(pending.family_command).__name__ != "PatronsPuppet"
                )
                or (
                    continuation.kind == "witch_sustain_stoke"
                    and not any(
                        effect.effect_id == pending.effect_id
                        and effect.kind == "stoke_the_heart"
                        and effect.source_actor_id == actor.actor_id
                        for effect in state.active_effects
                    )
                )
            ):
                raise ValueError("save has an unavailable Restored Spirit timing choice")
            return
        if pending.kind == "witch_restored_spirit_temp_hp":
            actor = state.creatures.get(pending.actor_id or "")
            target = state.creatures.get(pending.target_id or "")
            familiar = state.creatures.get(pending.effect_id or "")
            continuation = pending.continuation
            if (
                actor is None or target is None or familiar is None
                or pending.owner_actor_id != target.actor_id
                or target.temporary_hp <= 0
                or pending.options != (
                    ChoiceOption("keep_existing", "Keep existing temporary HP"),
                    ChoiceOption("gain_new", "Gain 2 temporary HP"),
                )
                or pending.transition_kind not in {"before", "after"}
                or not self._familiar_owned_by(actor, familiar)
                or familiar.dead or familiar.unconscious
                or (pending.transition_kind == "before" and continuation is None)
            ):
                raise ValueError("save has an unavailable Restored Spirit temporary-HP choice")
            return
        if pending.kind == "witch_restored_spirit_willingness":
            actor = state.creatures.get(pending.actor_id or "")
            target = state.creatures.get(pending.target_id or "")
            familiar = state.creatures.get(pending.effect_id or "")
            continuation = pending.continuation
            if (
                actor is None or target is None or familiar is None
                or pending.owner_actor_id != target.actor_id
                or pending.options != (
                    ChoiceOption("willing", "Willing"),
                    ChoiceOption("unwilling", "Unwilling"),
                )
                or pending.transition_kind not in {"before", "after"}
                or not self._familiar_owned_by(actor, familiar)
                or familiar.dead or familiar.unconscious
                or target.dead or target.unconscious
                or (pending.transition_kind == "before" and continuation is None)
            ):
                raise ValueError("save has an unavailable Restored Spirit willingness choice")
            return
        if pending.kind == "detect_magic_known":
            caster = state.creatures.get(pending.actor_id or "")
            continuation = pending.continuation
            if (
                caster is None
                or pending.owner_actor_id != caster.actor_id
                or pending.spell_id != "detect_magic"
                or pending.spell_actions != 2
                or pending.options != (
                    ChoiceOption("detect_all", "Detect all magic"),
                    ChoiceOption("ignore_known", "Ignore magic already known to the caster"),
                )
                or continuation is None
                or continuation.kind != "cast"
                or continuation.actor_id != caster.actor_id
                or continuation.spell_id != "detect_magic"
                or continuation.spell_actions != 2
                or continuation.target_id is not None
                or continuation.spell_target_id is not None
                or continuation.spell_target_item_id is not None
                or continuation.include_self is not None
            ):
                raise ValueError("save has an unavailable Detect Magic choice")
            return
        if pending.kind == "persistent_recovery":
            actor = state.creatures.get(pending.actor_id or "")
            hero_owner = (self._familiar_hero_owner(state, actor) or actor) if actor is not None else None
            effect = next((item for item in state.persistent_effects if item.effect_id == pending.effect_id), None)
            continuation = pending.continuation
            check = pending.check
            familiar_lifecycle = (
                actor is not None
                and hero_owner is not None
                and hero_owner is not actor
                and state.initiative_finalized
                and bool(state.initiative_order)
                and state.initiative_order[state.active_index] == hero_owner.actor_id
            )
            try:
                recovery_index = int(continuation.stage or "0")
            except ValueError:
                recovery_index = -1
            if (
                actor is None or effect is None or continuation is None or check is None
                or hero_owner is None or pending.owner_actor_id != hero_owner.actor_id or pending.target_id != actor.actor_id
                or effect.target_actor_id != actor.actor_id or continuation.kind != "persistent_tick"
                or not 0 <= recovery_index < len(continuation.target_ids)
                or continuation.target_ids[recovery_index] != pending.effect_id
                or len(set(continuation.target_ids)) != len(continuation.target_ids)
                or (
                    continuation.parent_continuation is None
                    and not familiar_lifecycle
                )
                or (
                    continuation.parent_continuation is not None
                    and continuation.parent_continuation.kind not in {"persistent_end_turn", "persistent_incapacitated_turn"}
                )
                or check.modifier != 0 or check.dc != 15 or len(check.dice) != 1
                or pending.options != (ChoiceOption("keep", "Keep result"), ChoiceOption("spend_hero_point", "Spend 1 Hero Point and reroll"))
                or actor.health_mode is not HealthMode.PC or hero_owner.hero_points < 1
            ):
                raise ValueError("save has an unavailable persistent recovery choice")
            return
        if pending.kind == "damage_defense":
            self._validate_damage_resolution_pending(state, pending, expect_health_choice=False)
            return
        if pending.kind == "shield_block":
            self._validate_shield_block_pending(state, pending)
            return
        if pending.kind == "heroic_recovery_damage":
            if pending.transition_kind == "familiar_persistent_damage":
                owner = state.creatures.get(pending.owner_actor_id or "")
                target = state.creatures.get(pending.target_id or "")
                if (
                    owner is None or target is None
                    or pending.actor_id != owner.actor_id
                    or self._familiar_hero_owner(state, target) is not owner
                    or target.health_mode is not HealthMode.PC
                    or owner.hero_points < 1
                    or pending.options != (
                        ChoiceOption("normal", "Apply normal health outcome"),
                        ChoiceOption("heroic_recovery", "Heroic Recovery (spend all Hero Points)"),
                    )
                    or pending.damage_result is None
                    or not pending.damage_result_is_mitigated
                    or pending.health_normal is None
                    or pending.health_heroic is None
                    or not any(effect.target_actor_id == target.actor_id for effect in state.persistent_effects)
                    or not state.initiative_finalized
                    or not state.initiative_order
                    or state.initiative_order[state.active_index] != owner.actor_id
                ):
                    raise ValueError("save has an unavailable familiar persistent damage recovery choice")
                return
            if pending.damage_resolution is not None:
                self._validate_damage_resolution_pending(state, pending, expect_health_choice=True)
                return
        if pending.kind == "desperate_prayer":
            actor = state.creatures.get(pending.actor_id or "")
            if (
                actor is None
                or pending.owner_actor_id != actor.actor_id
                or pending.options != (
                    ChoiceOption("accept", "Use Desperate Prayer (+1 devotion Focus Point)"),
                    ChoiceOption("decline", "Decline"),
                )
                or not state.initiative_finalized
                # ``_active_actor_id`` intentionally returns ``None`` while a
                # choice is pending.  Validate the persisted turn slot
                # directly so a saved Desperate Prayer prompt can round-trip.
                or (
                    not state.initiative_order
                    or state.active_index < 0
                    or state.active_index >= len(state.initiative_order)
                    or state.initiative_order[state.active_index] != actor.actor_id
                )
                or actor.unconscious
                or actor.dead
                or actor.focus_points != 0
                or actor.actor_id in state.desperate_prayer_used
                or "desperate_prayer" not in get_definition(actor.definition_id).abilities
            ):
                raise ValueError("save has an unavailable or inconsistent Desperate Prayer choice")
            return
        if pending.kind == "reaction" and pending.procedure_id == "investigator:clue_in":
            actor = state.creatures.get(pending.actor_id or "")
            if actor is None or pending.family_id != "martial":
                raise ValueError("save has an incomplete Clue In reaction choice")
            from . import investigator

            context = FamilyProcedureContext(
                self, state, self._dice.clone(), actor, get_definition(actor.definition_id),
                "martial", pending=pending,
            )
            investigator.validate_pending(context)
            return
        if pending.kind == "family_action":
            if pending.procedure_id == "barbarian:quick_tempered":
                self._validate_quick_tempered_offer(state, pending)
                return
            if pending.procedure_id == "w4_offensive:exacting_strike":
                self._validate_w4_exacting_press_pending(state, pending)
                return
            self._validate_family_pending(state, pending)
            return
        if pending.kind == "nimble_dodge":
            continuation = pending.continuation
            attacker = state.creatures.get(pending.actor_id or "")
            target = state.creatures.get(pending.target_id or "")
            if (
                continuation is None
                or attacker is None
                or target is None
                or pending.owner_actor_id != target.actor_id
                or continuation.actor_id != attacker.actor_id
                or continuation.target_id != target.actor_id
                or continuation.kind not in {"strike", "ranged_strike", "reaction_strike", "cast"}
                or not self._nimble_dodge_available(state, attacker, target)
                or pending.options != (
                    ChoiceOption("use", "Use Nimble Dodge (+2 AC)"),
                    ChoiceOption("decline", "Decline"),
                )
            ):
                raise ValueError("save has an unavailable or inconsistent Nimble Dodge choice")
            return
        if pending.kind == "youre_next":
            actor = state.creatures.get(pending.actor_id or "")
            definition = get_definition(actor.definition_id) if actor is not None else None
            expected = tuple(
                candidate.actor_id
                for candidate in sorted(state.creatures.values(), key=lambda item: item.actor_id)
                if actor is not None
                and candidate.team != actor.team
                and not candidate.defeated and not candidate.unconscious and not candidate.dead
                and grid_distance_feet(actor.position, candidate.position) <= 60
            )
            expected_options = tuple(
                [ChoiceOption(f"target:{target_id}", f"Demoralize {state.creatures[target_id].label} (+2)") for target_id in expected]
                + [ChoiceOption("decline", "Decline")]
            )
            if (
                actor is None or definition is None
                or pending.owner_actor_id != actor.actor_id
                or "You're Next" not in definition.feats
                or not actor.reaction_available
                or not expected
                or pending.target_ids != expected
                or pending.options != expected_options
            ):
                raise ValueError("save has an unavailable or inconsistent You're Next choice")
            return
        if pending.kind == "reactive_shield":
            continuation = pending.continuation
            attacker = state.creatures.get(pending.actor_id or "")
            target = state.creatures.get(pending.target_id or "")
            attack = self._find_attack(state, attacker, pending.attack_id) if attacker is not None else None
            if (
                continuation is None or attacker is None or target is None or attack is None
                or pending.owner_actor_id != target.actor_id
                or continuation.actor_id != attacker.actor_id
                or continuation.target_id != target.actor_id
                or continuation.kind != "reactive_shield"
                or "melee" not in attack.traits or "ranged" in attack.traits
                or not self._reactive_shield_available(state, attacker, target)
                or pending.options != (
                    ChoiceOption("use", "Use Reactive Shield (+2 AC)"),
                    ChoiceOption("decline", "Decline"),
                )
            ):
                raise ValueError("save has an unavailable or inconsistent Reactive Shield choice")
            check = pending.check
            if check is None:
                raise ValueError("save has a Reactive Shield choice without its committed hit check")
            if (
                check.attack_id != attack.attack_id
                or check.attack_count != pending.attack_count
                or check.map_penalty != pending.attack_penalty
                or check.traits != tuple(sorted(attack.traits))
                or pending.attack_penalty != continuation.attack_penalty
                or pending.attack_count != continuation.attack_count
            ):
                raise ValueError("save has an inconsistent Reactive Shield attack context")
            expected_modifiers = _strike_modifier_breakdown_full(
                attack,
                pending.attack_penalty,
                pending.nonlethal,
                attacker.prone and not attacker.unconscious,
                ranged_penalty=pending.ranged_penalty,
                guidance_bonus=pending.guidance_bonus,
                enfeebled=self._enfeebled_value(state, attacker.actor_id),
                lethal_penalty_exempt=self._powerful_fist_lethal_penalty_exempt(
                    attacker, attack, pending.nonlethal
                ),
            )
            item_modifier = self._attack_item_potency_modifier(
                state, attacker, attack, item_id=pending.item_id
            )
            if item_modifier is not None:
                expected_modifiers = (*expected_modifiers, item_modifier)
            expected_modifiers = (
                *expected_modifiers,
                *self._strike_condition_modifiers(state, attacker, attack),
                *self._mutagen_modifiers(state, attacker, "attack", attack_traits=attack.traits),
            )
            if check.modifier_breakdown != expected_modifiers or check.modifier != combine_modifiers(expected_modifiers):
                raise ValueError("save has forged Reactive Shield attack modifiers")
            actual_continuation = continuation.parent_continuation
            if check.dc != self._attack_dc(
                state, attacker, target, attack,
                target_off_guard=pending.attack_target_off_guard,
                nimble_dodge=(actual_continuation.nimble_dodge_used if actual_continuation is not None else False),
            ):
                raise ValueError("save has forged Reactive Shield target AC")
            return
        if pending.kind == "concealment_hero_reroll":
            self._validate_concealment_pending(state, pending)
            return
        if pending.kind == "reaction":
            continuation = pending.continuation
            actor = state.creatures.get(pending.actor_id or "")
            owner = state.creatures.get(pending.owner_actor_id or "")
            if continuation is None or actor is None or owner is None:
                raise ValueError("save has an incomplete pending reaction")
            if continuation.actor_id != actor.actor_id or (
                continuation.reaction_trigger != "justice_damage"
                and pending.target_id != actor.actor_id
            ):
                raise ValueError("save has a pending reaction for a different action actor")
            if continuation.reaction_trigger == "justice_damage":
                resolution = pending.damage_resolution
                if (
                    resolution is None
                    or continuation.kind != "justice_damage"
                    or resolution.actor_id != actor.actor_id
                    or resolution.target_id != pending.target_id
                    or continuation.target_id != pending.target_id
                    or not resolution.justice_checked
                    or resolution.justice_actor_id != owner.actor_id
                    or "justice_retributive_strike" not in get_definition(owner.definition_id).abilities
                    or not owner.reaction_available
                    or owner.unconscious
                    or owner.dead
                    or not self._in_justice_aura(state, owner, state.creatures[resolution.target_id])
                    or pending.options != (
                        ChoiceOption("accept", "Accept protection and retaliate if reachable"),
                        ChoiceOption("decline", "Decline"),
                    )
                ):
                    raise ValueError("save has an unavailable or inconsistent Retributive Strike choice")
                return
            if continuation.reaction_trigger not in {"movement", "manipulate", "ranged", "stand"}:
                raise ValueError("save has an invalid pending reaction trigger")
            if continuation.must_disrupt_on_critical != (
                continuation.reaction_trigger == "manipulate"
                or continuation.kind == "ranged_strike"
            ):
                raise ValueError("save has inconsistent pending reaction disruption")
            if self._next_reactor(state, actor, continuation, continuation.reaction_trigger) is not owner:
                raise ValueError("save has a pending reaction for an ineligible reactor")
            expected_kind = {
                "movement": "movement",
                "manipulate": "interact",
                "ranged": "ranged_strike",
                "stand": "stand",
            }[continuation.reaction_trigger]
            if continuation.kind != expected_kind and not (
                continuation.kind == "cast" and continuation.reaction_trigger == "manipulate"
            ) and not (
                continuation.kind == "family_action"
                and continuation.reaction_trigger == "manipulate"
                and continuation.stage in {"battle_medicine_check", "widen_spell"}
            ):
                raise ValueError("save has a pending reaction for an inconsistent continuation")
            if continuation.kind == "cast" and continuation.spell_id == "runic_weapon":
                if not self._valid_committed_runic_weapon(actor, continuation):
                    raise ValueError("save has an invalid committed Runic Weapon reaction continuation")
                try:
                    _item, wielder_id, _position = self._runic_weapon_target(
                        state, actor, continuation.spell_target_item_id,
                        reach_spell_effective_range_ft=continuation.reach_spell_effective_range_ft,
                    )
                except ValueError as error:
                    raise ValueError("save has an unavailable Runic Weapon item target") from error
                if wielder_id != continuation.spell_target_wielder_id:
                    raise ValueError("save has an inconsistent Runic Weapon item wielder")
            if continuation.kind == "cast" and continuation.spell_id in {"ignition", "gouging_claw"}:
                valid_modes = {"ranged", "melee"} if continuation.spell_id == "ignition" else {"piercing", "slashing"}
                if pending.damage_context != continuation.spell_mode or continuation.spell_mode not in valid_modes:
                    raise ValueError("save has an inconsistent persistent spell reaction mode")
                spell_target = state.creatures.get(continuation.target_id or "")
                if spell_target is None or spell_target.defeated:
                    raise ValueError("save has an unavailable persistent spell reaction target")
                if continuation.spell_id == "ignition" and continuation.spell_mode == "melee" and grid_distance_feet(actor.position, spell_target.position) > 5:
                    raise ValueError("save has an out-of-reach melee Ignition reaction continuation")
            if continuation.kind == "cast" and continuation.spell_id == "light":
                caster = actor
                attachment = state.creatures.get(continuation.light_attachment_actor_id or "")
                if (
                    not self._valid_committed_light_cast(caster, continuation)
                    or continuation.spell_actions != 2
                    or continuation.target_id is not None
                    or continuation.spell_target_id is not None
                    or continuation.slot_id is not None
                    or continuation.sorcerous_potency != 0
                    or continuation.blood_magic_recipient_id is not None
                    or continuation.light_point is None
                    or not in_bounds(continuation.light_point, state.map_width, state.map_height)
                    or continuation.light_color is None
                    or not continuation.light_color.strip()
                    or continuation.light_control not in {None, "cast"}
                    or (
                        continuation.light_replacement_orb_id is None
                        and sum(
                            orb.caster_actor_id == caster.actor_id
                            for orb in state.light_orbs
                        ) >= 4
                    )
                    or (
                        continuation.light_replacement_orb_id is not None
                        and sum(
                            orb.caster_actor_id == caster.actor_id
                            for orb in state.light_orbs
                        ) != 4
                    )
                    or (
                        continuation.light_replacement_orb_id is not None
                        and not any(
                            orb.caster_actor_id == caster.actor_id
                            and orb.stable_id == continuation.light_replacement_orb_id
                            for orb in state.light_orbs
                        )
                    )
                    or continuation.light_orb_id is not None
                    or (
                        attachment is not None
                        and attachment.position != continuation.light_point
                    )
                ):
                    raise ValueError("save has an invalid Light reaction continuation")
            expected_options = tuple(
                ChoiceOption(option_id, label)
                for option_id, _attack, _damage_type, _nonlethal, label, _item_id
                in self._reaction_strike_choices(state, owner, actor)
            ) + (ChoiceOption("decline", "Decline"),)
            if pending.options != expected_options:
                raise ValueError("save has inconsistent pending Reactive Strike options")
            return

        if pending.kind == "spell_blood_magic_recipient":
            continuation = pending.continuation
            caster = state.creatures.get(pending.actor_id or "")
            target = state.creatures.get(pending.target_id or "")
            if continuation is not None and continuation.spell_id == "angelic_halo":
                if (
                    continuation.kind != "cast"
                    or continuation.spell_source_kind != "focus"
                    or continuation.blood_magic_recipient_id is not None
                    or caster is None
                    or not self._valid_committed_blood_magic_halo(caster, continuation)
                    or pending.owner_actor_id != caster.actor_id
                    or pending.actor_id != caster.actor_id
                    or pending.target_id is not None
                    or pending.spell_id != continuation.spell_id
                    or pending.slot_id != continuation.slot_id
                    or pending.spell_actions != continuation.spell_actions
                    or pending.options != self._blood_magic_halo_recipient_options(state, caster)
                ):
                    raise ValueError("save has an unavailable or inconsistent Halo Blood Magic choice")
                return
            if continuation is not None and continuation.spell_actions == 3:
                if (
                    continuation.kind != "cast"
                    or continuation.spell_id != "heal"
                    or continuation.spell_source_kind != "spontaneous"
                    or continuation.blood_magic_recipient_id is not None
                    or caster is None
                    or not self._valid_committed_blood_magic_heal(caster, continuation)
                    or pending.owner_actor_id != caster.actor_id
                    or pending.spell_id != continuation.spell_id
                    or pending.slot_id != continuation.slot_id
                    or pending.spell_actions != continuation.spell_actions
                    or continuation.include_self is None
                    or pending.target_id is not None
                    or pending.options != self._blood_magic_area_recipient_options(state, caster, continuation)
                ):
                    raise ValueError("save has an unavailable or inconsistent Blood Magic area choice")
                return
            if (
                continuation is None
                or continuation.kind != "cast"
                or continuation.spell_id != "heal"
                or continuation.spell_source_kind != "spontaneous"
                or continuation.blood_magic_recipient_id is not None
                or caster is None
                or target is None
                or not self._valid_committed_blood_magic_heal(caster, continuation)
                or pending.owner_actor_id != caster.actor_id
                or pending.spell_id != continuation.spell_id
                or pending.slot_id != continuation.slot_id
                or pending.spell_actions != continuation.spell_actions
                or continuation.actor_id != caster.actor_id
                or continuation.target_id != target.actor_id
                or continuation.spell_target_id != target.actor_id
                or target.actor_id not in self._spell_targets_for_cast(
                    state, caster, "heal", continuation.spell_actions,
                    reach_spell_effective_range_ft=continuation.reach_spell_effective_range_ft,
                )
                or pending.options != self._blood_magic_recipient_options(caster, target)
            ):
                raise ValueError("save has an unavailable or inconsistent Blood Magic recipient choice")
            return

        if pending.kind == "spell_willingness":
            continuation = pending.continuation
            caster = state.creatures.get(pending.actor_id or "")
            target = state.creatures.get(pending.target_id or "")
            if pending.spell_id == "light":
                if continuation is not None and continuation.light_control == "sustain":
                    orb = next(
                        (
                            item for item in state.light_orbs
                            if item.stable_id == continuation.light_orb_id
                        ),
                        None,
                    )
                    if (
                        caster is None
                        or target is None
                        or continuation.kind != "cast"
                        or continuation.actor_id != caster.actor_id
                        or continuation.spell_id != "light"
                        or continuation.target_id != target.actor_id
                        or continuation.spell_target_id != target.actor_id
                        or continuation.spell_actions != 1
                        or continuation.slot_id is not None
                        or continuation.spell_source_kind is not None
                        or continuation.light_point is None
                        or continuation.light_color is not None
                        or continuation.light_attachment_actor_id != target.actor_id
                        or continuation.light_orb_id is None
                        or orb is None
                        or orb.caster_actor_id != caster.actor_id
                        or orb.rank != 1
                        or orb.point != continuation.light_point
                        or orb.attached_actor_id is not None
                        or target.position != orb.point
                        or pending.actor_id != caster.actor_id
                        or pending.target_id != target.actor_id
                        or pending.owner_actor_id != (
                            target.actor_id if target.health_mode is HealthMode.PC else None
                        )
                        or pending.slot_id is not None
                        or pending.spell_actions != 1
                        or pending.options != (
                            ChoiceOption("willing", "Willing"),
                            ChoiceOption("unwilling", "Unwilling"),
                        )
                    ):
                        raise ValueError(
                            "save has an unavailable or inconsistent Light Sustain willingness choice"
                        )
                    return
                orb = next(
                    (
                        item for item in state.light_orbs
                        if continuation is not None
                        and item.stable_id == continuation.light_orb_id
                    ),
                    None,
                )
                if (
                    continuation is None
                    or caster is None
                    or target is None
                    or continuation.kind != "cast"
                    or continuation.actor_id != caster.actor_id
                    or continuation.spell_id != "light"
                    or continuation.target_id is not None
                    or continuation.spell_target_id is not None
                    or continuation.spell_actions != 2
                    or continuation.slot_id is not None
                    or continuation.sorcerous_potency != 0
                    or continuation.blood_magic_recipient_id is not None
                    or continuation.light_point is None
                    or continuation.light_color is None
                    or continuation.light_attachment_actor_id != target.actor_id
                    or continuation.light_orb_id is None
                    or orb is None
                    or orb.caster_actor_id != caster.actor_id
                    or orb.rank != 1
                    or orb.point != continuation.light_point
                    or orb.attached_actor_id is not None
                    or target.position != orb.point
                    or pending.actor_id != caster.actor_id
                    or pending.target_id != target.actor_id
                    or pending.owner_actor_id != (
                        target.actor_id if target.health_mode is HealthMode.PC else None
                    )
                    or pending.slot_id is not None
                    or pending.spell_actions != 2
                    or pending.options != (
                        ChoiceOption("willing", "Willing"),
                        ChoiceOption("unwilling", "Unwilling"),
                    )
                ):
                    raise ValueError("save has an unavailable or inconsistent Light willingness choice")
                return
            if continuation is not None and continuation.spell_id == "runic_weapon":
                if (
                    caster is None
                    or target is None
                    or not self._valid_committed_runic_weapon(caster, continuation)
                    or continuation.actor_id != caster.actor_id
                    or continuation.target_id is not None
                    or continuation.spell_target_item_id != pending.spell_target_item_id
                    or continuation.spell_target_item_id is None
                    or continuation.spell_target_wielder_id != target.actor_id
                    or pending.spell_id != "runic_weapon"
                    or pending.slot_id != continuation.slot_id
                    or pending.spell_actions != 2
                    or pending.actor_id != caster.actor_id
                    or pending.target_id != target.actor_id
                    or pending.owner_actor_id != (
                        target.actor_id if target.health_mode is HealthMode.PC else None
                    )
                    or pending.options != (
                        ChoiceOption("willing", "Willing"),
                        ChoiceOption("unwilling", "Unwilling"),
                    )
                ):
                    raise ValueError("save has an unavailable or inconsistent Runic Weapon willingness choice")
                try:
                    _item, wielder_id, _position = self._runic_weapon_target(
                        state, caster, continuation.spell_target_item_id,
                        reach_spell_effective_range_ft=continuation.reach_spell_effective_range_ft,
                    )
                except ValueError as error:
                    raise ValueError("save has an unavailable Runic Weapon item target") from error
                if wielder_id != target.actor_id:
                    raise ValueError("save has an unavailable Runic Weapon item wielder")
                return
            if continuation is not None and continuation.spell_id == "runic_body":
                slot = (
                    next(
                        (item for item in caster.prepared_slots if item.slot_id == continuation.slot_id),
                        None,
                    )
                    if caster is not None else None
                )
                if (
                    caster is None
                    or target is None
                    or continuation.kind != "cast"
                    or continuation.actor_id != caster.actor_id
                    or continuation.target_id != target.actor_id
                    or continuation.spell_target_id != target.actor_id
                    or continuation.spell_source_kind != "prepared"
                    or continuation.spell_actions != 2
                    or continuation.stage is not None
                    or slot is None
                    or slot.spell_id != "runic_body"
                    or slot.rank != 1
                    or slot.cantrip
                    or not slot.spent
                    or pending.spell_id != "runic_body"
                    or pending.slot_id != continuation.slot_id
                    or pending.spell_actions != 2
                    or pending.actor_id != caster.actor_id
                    or pending.target_id != target.actor_id
                    or pending.owner_actor_id != (
                        target.actor_id if target.health_mode is HealthMode.PC else None
                    )
                    or pending.options != (
                        ChoiceOption("willing", "Willing"),
                        ChoiceOption("unwilling", "Unwilling"),
                    )
                    or not self._is_living_target(target)
                    or target.actor_id not in self._spell_targets_for_cast(
                        state, caster, "runic_body", 2,
                        reach_spell_effective_range_ft=continuation.reach_spell_effective_range_ft,
                    )
                ):
                    raise ValueError("save has an unavailable or inconsistent Runic Body willingness choice")
                return
            if (
                continuation is None
                or caster is None
                or target is None
                or continuation.kind != "cast"
                or continuation.actor_id != caster.actor_id
                or continuation.spell_id not in {"heal", "soothe", "protection"}
                or continuation.target_id != target.actor_id
                or continuation.spell_target_id != target.actor_id
                or continuation.spell_actions not in ((2,) if continuation.spell_id == "protection" else (1, 2))
                or pending.spell_id != continuation.spell_id
                or pending.slot_id != continuation.slot_id
                or pending.spell_actions != continuation.spell_actions
                or pending.owner_actor_id != (
                    target.actor_id if target.health_mode is HealthMode.PC else None
                )
                or pending.options != (
                    ChoiceOption("willing", "Willing"),
                    ChoiceOption("unwilling", "Unwilling"),
                )
                or target.actor_id not in self._spell_targets_for_cast(
                    state, caster, continuation.spell_id, continuation.spell_actions,
                    reach_spell_effective_range_ft=continuation.reach_spell_effective_range_ft,
                )
            ):
                raise ValueError("save has an unavailable or inconsistent willing-spell choice")
            if continuation.spell_id == "heal" and continuation.spell_source_kind == "spontaneous":
                if (
                    not self._valid_committed_blood_magic_heal(caster, continuation)
                    or continuation.blood_magic_recipient_id
                    not in {
                        option.option_id
                        for option in self._blood_magic_recipient_options(caster, target)
                    }
                ):
                    raise ValueError("save has an inconsistent spontaneous Heal willingness choice")
            elif continuation.spell_id == "heal" and continuation.spell_source_kind == "prepared":
                slot = next((
                    item for item in caster.prepared_slots
                    if item.slot_id == continuation.slot_id
                ), None)
                if (
                    slot is None or slot.spell_id != "heal" or slot.rank != 1
                    or slot.cantrip or not slot.spent
                    or continuation.sorcerous_potency != 0
                    or continuation.blood_magic_recipient_id is not None
                ):
                    raise ValueError("save has an inconsistent prepared Heal willingness choice")
            elif continuation.spell_id == "soothe" and continuation.spell_source_kind == "spontaneous":
                definition = get_definition(caster.definition_id)
                slot = next((
                    item for item in caster.spontaneous_slots
                    if item.slot_id == continuation.slot_id
                ), None)
                if (
                    continuation.slot_id is None
                    or slot is None
                    or slot.rank != 1
                    or slot.remaining >= slot.capacity
                    or not any(
                        spell.spell_id == "soothe"
                        and spell.rank == 1
                        and not spell.cantrip
                        for spell in definition.spontaneous_spells
                    )
                    or continuation.sorcerous_potency != 0
                    or continuation.blood_magic_recipient_id is not None
                ):
                    raise ValueError("save has an inconsistent spontaneous Soothe willingness choice")
            elif continuation.spell_id == "soothe" and continuation.spell_source_kind == "prepared":
                slot = next((
                    item for item in caster.prepared_slots
                    if item.slot_id == continuation.slot_id
                ), None)
                if (
                    slot is None or slot.spell_id != "soothe" or slot.rank != 1
                    or slot.cantrip or not slot.spent
                    or continuation.sorcerous_potency != 0
                    or continuation.blood_magic_recipient_id is not None
                ):
                    raise ValueError("save has an inconsistent prepared Soothe willingness choice")
            elif continuation.spell_id == "protection" and continuation.spell_source_kind == "prepared":
                slot = next((
                    item for item in caster.prepared_slots
                    if item.slot_id == continuation.slot_id
                ), None)
                if (
                    slot is None or slot.spell_id != "protection" or slot.rank != 1
                    or slot.cantrip or not slot.spent
                    or continuation.sorcerous_potency != 0
                    or continuation.blood_magic_recipient_id is not None
                ):
                    raise ValueError("save has an inconsistent prepared Protection willingness choice")
            else:
                raise ValueError("save has an unsupported healing casting source")
            return

        if pending.kind == "divine_grace":
            continuation = pending.continuation
            caster = state.creatures.get(pending.actor_id or "")
            target = state.creatures.get(pending.target_id or "")
            if (
                continuation is None
                or caster is None
                or target is None
                or continuation.kind != "cast"
                or continuation.actor_id != caster.actor_id
                or continuation.spell_id != pending.spell_id
                or continuation.target_id != target.actor_id
                or pending.owner_actor_id != target.actor_id
                or pending.target_id != target.actor_id
                or pending.slot_id != continuation.slot_id
                or pending.spell_actions != continuation.spell_actions
                or continuation.divine_grace_checked
                or continuation.divine_grace_used
                or not target.reaction_available
                or target.unconscious
                or target.dead
                or "divine_grace" not in get_definition(target.definition_id).abilities
                or "Divine Grace" not in get_definition(target.definition_id).feats
                or pending.options != (
                    ChoiceOption("use", "Use Divine Grace (+2 circumstance)"),
                    ChoiceOption("decline", "Decline"),
                )
            ):
                raise ValueError("save has an unavailable or inconsistent Divine Grace choice")
            return

        if pending.kind in {"spell_attack_hero_reroll", "spell_save_hero_reroll"}:
            continuation = pending.continuation
            caster = state.creatures.get(pending.actor_id or "")
            target = state.creatures.get(pending.target_id or "")
            check = pending.check
            if continuation is None or continuation.kind != "cast" or caster is None or target is None or check is None:
                raise ValueError("save has an incomplete pending spell check")
            target_matches = continuation.target_id == target.actor_id
            if pending.spell_id in {"breathe_fire", "electric_arc", "caustic_blast", "gale_blast"}:
                target_matches = target.actor_id in continuation.target_ids
            if continuation.spell_id != pending.spell_id or not target_matches:
                raise ValueError("save has a pending spell check for a different cast")
            if pending.kind == "spell_attack_hero_reroll":
                if (
                    continuation.sure_strike_used
                    or pending.owner_actor_id != caster.actor_id
                    or caster.health_mode is not HealthMode.PC
                    or caster.hero_points < 1
                ):
                    raise ValueError("save has an unavailable spell attack Hero Point choice")
                if len(check.dice) != 1:
                    raise ValueError("save has an unavailable Sure Strike Hero Point choice")
                if (
                    pending.spell_id not in {"divine_lance", "telekinetic_projectile", "ignition", "gouging_claw", "tangle_vine"}
                    or (
                        pending.spell_id == "divine_lance"
                        and check.attack_id != "divine_lance"
                    )
                    or (
                        pending.spell_id in {"telekinetic_projectile", "ignition", "gouging_claw", "tangle_vine"}
                        and check.attack_id is not None
                    )
                ):
                    raise ValueError("save has an unsupported pending spell attack")
                if pending.spell_id in {"telekinetic_projectile", "ignition", "gouging_claw", "tangle_vine"}:
                    if (
                        not continuation.attack_count_committed
                        or caster.strikes_this_turn != continuation.attack_count
                        or continuation.attack_penalty != multiple_attack_penalty(
                            caster.strikes_this_turn - 1,
                            spell_traits(pending.spell_id),
                        )
                    ):
                        raise ValueError("save has inconsistent spell attack MAP state")
                    modifiers = self._spell_attack_modifier_breakdown(state, caster, continuation, pending.spell_id)
                    expected_dc = self._effective_ac(target, state=state, attacker_id=caster.actor_id, lesser_cover=self._has_lesser_cover(state, caster, target))
                    if (
                        check.dc != expected_dc
                        or check.modifier_breakdown != tuple(modifiers)
                        or check.modifier != combine_modifiers(modifiers)
                        or check.attack_count != continuation.attack_count
                        or check.map_penalty != continuation.attack_penalty
                        or check.traits != tuple(sorted(spell_traits(pending.spell_id)))
                    ):
                        raise ValueError("save has an inconsistent spell attack check")
                    if pending.spell_id == "ignition":
                        if pending.damage_context != continuation.spell_mode or continuation.spell_mode not in {"ranged", "melee"}:
                            raise ValueError("save has an inconsistent Ignition attack mode")
                        if continuation.spell_mode == "melee" and grid_distance_feet(caster.position, target.position) > 5:
                            raise ValueError("save has an out-of-reach melee Ignition attack")
                    if pending.spell_id == "gouging_claw" and (
                        pending.damage_context != continuation.spell_mode
                        or continuation.spell_mode not in {"piercing", "slashing"}
                    ):
                        raise ValueError("save has an inconsistent Gouging Claw damage type")
                else:
                    if (
                        not continuation.attack_count_committed
                        or caster.strikes_this_turn != continuation.attack_count
                        or continuation.attack_penalty != multiple_attack_penalty(caster.strikes_this_turn - 1, spell_traits("divine_lance"))
                    ):
                        raise ValueError("save has inconsistent Divine Lance MAP state")
                    modifiers = self._spell_attack_modifier_breakdown(
                        state, caster, continuation, "divine_lance"
                    )
                    expected_dc = self._effective_ac(
                        target,
                        state=state,
                        attacker_id=caster.actor_id,
                        lesser_cover=self._has_lesser_cover(state, caster, target),
                        taking_cover=target.actor_id in state.taking_cover,
                        nimble_dodge=continuation.nimble_dodge_used,
                    )
                    if (
                        check.dc != expected_dc or check.modifier_breakdown != tuple(modifiers)
                        or check.modifier != combine_modifiers(modifiers)
                        or check.attack_count != continuation.attack_count
                        or check.map_penalty != continuation.attack_penalty
                        or check.traits != tuple(sorted(spell_traits("divine_lance")))
                    ):
                        raise ValueError("save has an inconsistent Divine Lance check")
            else:
                if pending.owner_actor_id != target.actor_id or target.health_mode is not HealthMode.PC or target.hero_points < 1:
                    raise ValueError("save has an unavailable spell save Hero Point choice")
                if pending.spell_id not in {"daze", "void_warp", "fear", "breathe_fire", "electric_arc", "tempest_surge", "vitality_lash", "frostbite", "enfeeble", "caustic_blast", "gale_blast"} or check.attack_id is not None:
                    raise ValueError("save has an unsupported pending spell save")
                save_statistic = (
                    "will" if pending.spell_id in {"daze", "fear"}
                    else "reflex" if pending.spell_id in {"breathe_fire", "electric_arc", "tempest_surge", "caustic_blast"}
                    else "fortitude"
                )
                expected_dc = self._spell_dc(state, caster, pending.spell_id)
                modifiers = self._spell_save_modifier_breakdown(
                    state, target, continuation, pending.spell_id, save_statistic
                )
                if check.dc != expected_dc:
                    raise ValueError(f"save has an inconsistent {pending.spell_id} DC")
                if check.modifier_breakdown != tuple(modifiers) or check.modifier != combine_modifiers(modifiers):
                    raise ValueError(f"save has inconsistent {pending.spell_id} save modifiers")
                expected_check = resolve_check(check.die, check.modifier, check.dc)
                if replace(check, modifier_breakdown=(), dice=()) != replace(
                    expected_check, modifier_breakdown=(), dice=(),
                ):
                    raise ValueError(f"save has inconsistent pending check arithmetic for {pending.spell_id}")
            expected_options = (ChoiceOption("keep", "Keep result"), ChoiceOption("spend_hero_point", "Spend 1 Hero Point and reroll"))
            if pending.options != expected_options:
                raise ValueError("save has inconsistent spell Hero Point options")
            return
        if pending.kind == "guidance_use":
            continuation = pending.continuation
            effect = next((item for item in state.active_effects if item.effect_id == pending.effect_id), None)
            if continuation is None or effect is None or effect.kind != "guidance" or effect.target_actor_id != pending.owner_actor_id:
                raise ValueError("save has an incomplete Guidance choice")
            if pending.check_kind == "weapon_attack":
                attacker = state.creatures.get(pending.actor_id or "")
                target = state.creatures.get(pending.target_id or "")
                attack = self._find_attack(state, attacker, pending.attack_id) if attacker is not None else None
                if (
                    attacker is None or target is None or attack is None
                    or continuation.actor_id != attacker.actor_id
                    or continuation.target_id != target.actor_id
                    or continuation.attack_id != attack.attack_id
                    or continuation.kind not in {"strike", "ranged_strike", "reaction_strike"}
                    or pending.owner_actor_id != attacker.actor_id
                    or pending.attack_penalty != continuation.attack_penalty
                    or pending.attack_count != continuation.attack_count
                    or pending.damage_type != continuation.damage_type
                    or pending.item_id != continuation.item_id
                    or pending.nonlethal != continuation.nonlethal
                    or pending.attack_actions_cost != continuation.attack_actions_cost
                    or pending.attack_count_cost != continuation.attack_count_cost
                    or pending.feint_off_guard_applied != continuation.feint_off_guard_applied
                    or (
                        continuation.feint_off_guard_applied
                        and ("melee" not in attack.traits or "ranged" in attack.traits)
                    )
                ):
                    raise ValueError("save has an inconsistent pending Feint/GUIDANCE Strike context")
            elif pending.check_kind == "spell_save":
                caster = state.creatures.get(continuation.actor_id)
                target = state.creatures.get(pending.target_id or "")
                target_matches = target is not None and continuation.target_id == target.actor_id
                if pending.spell_id in {"breathe_fire", "electric_arc", "caustic_blast", "gale_blast"}:
                    target_matches = target is not None and target.actor_id in continuation.target_ids
                if (
                    caster is None
                    or target is None
                    or continuation.kind != "cast"
                    or continuation.actor_id != caster.actor_id
                    or continuation.spell_id != pending.spell_id
                    or continuation.spell_actions != 2
                    or continuation.slot_id != pending.slot_id
                    or pending.actor_id != target.actor_id
                    or pending.owner_actor_id != target.actor_id
                    or pending.check_owner_actor_id != target.actor_id
                    or not target_matches
                ):
                    raise ValueError("save has inconsistent spell-save Guidance cast context")
            elif pending.check_kind != "spell_attack":
                raise ValueError("save has unsupported Guidance check kind")
            if pending.options != (ChoiceOption("use", "Use Guidance (+1 status)"), ChoiceOption("keep", "Keep Guidance for later")):
                raise ValueError("save has inconsistent Guidance options")
            return
        if pending.kind == "grabbed_manipulate_hero_reroll":
            continuation = pending.continuation
            actor = state.creatures.get(pending.actor_id or "")
            check = pending.check
            expected_options = (
                ChoiceOption("keep", "Keep result"),
                ChoiceOption("spend_hero_point", "Spend 1 Hero Point and reroll"),
            )
            if (
                actor is None or continuation is None or check is None
                or pending.owner_actor_id != actor.actor_id
                or actor.health_mode is not HealthMode.PC or actor.hero_points < 1
                or continuation.actor_id != actor.actor_id
                or continuation.kind not in {"cast", "interact", "ranged_strike", "family_action"}
                or continuation.movement_kind not in {"manipulate", "ranged"}
                or (
                    continuation.kind != "family_action"
                    and continuation.stage != "grabbed_manipulate_flat_check"
                )
                or (
                    continuation.kind == "family_action"
                    and continuation.stage != "widen_spell_grabbed_flat_check"
                )
                or check.modifier != 0 or check.dc != 5
                or check.attack_id is not None or check.map_penalty != 0
                or check.modifier_breakdown
                or pending.options != expected_options
                or not self._grabbed_manipulate_check_required(state, actor, continuation)
                or self._next_reactor(
                    state,
                    actor,
                    continuation,
                    "ranged" if continuation.kind == "ranged_strike" else "manipulate",
                ) is not None
            ):
                raise ValueError("save has an invalid Grabbed manipulate flat-check choice")
            return
        if pending.kind != "attack_hero_reroll":
            return
        actor = state.creatures.get(pending.actor_id or "")
        target = state.creatures.get(pending.target_id or "")
        check = pending.check
        attack = self._find_attack(state, actor, pending.attack_id) if actor is not None else None
        if actor is None or target is None or check is None or attack is None:
            raise ValueError("save has an incomplete pending Strike check")
        if pending.continuation is not None and pending.continuation.sure_strike_used:
            raise ValueError("save has an unavailable Sure Strike Hero Point choice")
        if len(check.dice) != 1:
            raise ValueError("save has an unavailable Sure Strike Hero Point choice")
        if pending.owner_actor_id != actor.actor_id or actor.health_mode is not HealthMode.PC or actor.hero_points < 1:
            raise ValueError("save has an unavailable Hero Point Strike choice")
        if self.target_is_concealed(actor.actor_id, target.actor_id) and not pending.concealment_checked:
            raise ValueError("save has a Strike Hero choice before its concealment flat check")
        if target.actor_id == actor.actor_id or target.defeated or not self._attack_equipped(state, actor, attack):
            raise ValueError("save has an illegal pending Strike target or attack")
        if attack.item_id is None:
            if pending.item_id is not None:
                raise ValueError("save has an item identity on an unarmed Strike")
        elif pending.item_id not in self._held_attack_item_ids(state, actor, attack):
            raise ValueError("save has a pending Strike for an unavailable item identity")
        if pending.damage_type not in self._attack_damage_types(attack):
            raise ValueError("save has an illegal pending Strike damage type")
        if pending.nonlethal not in (True, False):
            raise ValueError("save has an invalid pending Strike intent")
        if pending.attack_actions_cost not in (0, 1, 2) or pending.attack_count_cost not in (0, 1, 2):
            raise ValueError("save has invalid pending Strike costs")
        if pending.is_reaction != (pending.attack_actions_cost == 0 and pending.attack_count_cost == 0):
            raise ValueError("save has inconsistent pending reaction costs")
        if pending.is_reaction:
            continuation = pending.continuation
            expected_reaction_parent = {
                "movement": "movement",
                "interact": "manipulate",
                "stand": "stand",
                "ranged_strike": "ranged",
                "cast": "manipulate",
                "family_action": "manipulate",
            }
            justice_retaliation = (
                continuation is not None
                and continuation.kind == "justice_damage"
                and continuation.reaction_trigger == "justice_damage"
            )
            if continuation is None or (
                not justice_retaliation
                and expected_reaction_parent.get(continuation.kind) != continuation.reaction_trigger
            ) or (
                continuation is not None
                and continuation.kind == "family_action"
                and continuation.stage != "widen_spell"
            ):
                raise ValueError("save has a pending reaction Strike without its parent action")
            if continuation.must_disrupt_on_critical != (continuation.reaction_trigger == "manipulate"):
                raise ValueError("save has inconsistent pending reaction disruption")
            if not justice_retaliation and actor.actor_id not in continuation.seen_reactors:
                raise ValueError("save has a pending reaction Strike without its parent action")
            if continuation.actor_id != target.actor_id:
                raise ValueError("save has a pending reaction Strike for another target")
            if justice_retaliation:
                protected = state.creatures.get(continuation.target_id or "")
                if (
                    protected is None
                    or protected.team != actor.team
                    or protected.actor_id in {actor.actor_id, target.actor_id}
                    or actor.reaction_available
                    or "justice_retributive_strike" not in get_definition(actor.definition_id).abilities
                ):
                    raise ValueError("save has an inconsistent Justice retaliation continuation")
            if "melee" not in attack.traits or grid_distance_feet(actor.position, target.position) > attack.reach_ft:
                raise ValueError("save has an illegal pending Reactive Strike")
            expected_penalty, expected_count = 0, 1
        else:
            continuation = pending.continuation
            hunter_aim_intent = (
                continuation.hunter_aim_intent
                if continuation is not None
                else None
            )
            hunter_aim = hunter_aim_intent is not None
            sudden_charge_strike = (
                continuation is not None
                and continuation.kind == "sudden_charge"
                and continuation.actor_id == actor.actor_id
                and "sudden_charge" in get_definition(actor.definition_id).abilities
                and actor.flourish_used_round == state.round_number
                and pending.attack_actions_cost == 0
                and pending.attack_count_cost == 1
            )
            intimidating_strike = (
                continuation is not None
                and continuation.kind == "intimidating_strike"
                and continuation.actor_id == actor.actor_id
                and continuation.target_id == target.actor_id
                and continuation.attack_id == attack.attack_id
                and "intimidating_strike" in get_definition(actor.definition_id).abilities
                and pending.attack_actions_cost == 2
                and pending.attack_count_cost == 1
                and "melee" in attack.traits
            )
            paired_strike_subordinate = (
                continuation is not None
                and continuation.kind == "paired_strike"
                and continuation.paired_strike is not None
                and pending.attack_actions_cost == 0
                and pending.attack_count_cost == 1
            )
            paired_double_slice_non_agile = (
                paired_strike_subordinate
                and continuation.paired_strike.activity_id == "fighter:double_slice"
                and continuation.paired_strike.next_index == 1
                and "agile" not in attack.traits
            )
            if (
                pending.attack_actions_cost not in ((0, 1, 2) if (sudden_charge_strike or paired_strike_subordinate) else (1, 2))
                or pending.attack_count_cost not in (1, 2)
                or (not hunter_aim and not sudden_charge_strike and not intimidating_strike and not paired_strike_subordinate and pending.attack_count_cost != pending.attack_actions_cost)
                or (hunter_aim and pending.attack_actions_cost != 2)
            ):
                raise ValueError("save has inconsistent pending Strike costs")
            if hunter_aim:
                from .ranger import validate_hunter_aim_intent

                if (
                    continuation is None
                    or continuation.kind != "ranged_strike"
                    or continuation.actor_id != actor.actor_id
                    or continuation.target_id != target.actor_id
                    or continuation.attack_id != attack.attack_id
                    or continuation.item_id != pending.item_id
                    or hunter_aim_intent.item_id != continuation.item_id
                    or not validate_hunter_aim_intent(
                        hunter_aim_intent,
                        actor=actor,
                        target=target,
                        attack=attack,
                        actions_cost=pending.attack_actions_cost,
                        attack_count_cost=pending.attack_count_cost,
                    )
                ):
                    raise ValueError("save has invalid Hunter's Aim intent")
            if actor.strikes_this_turn < pending.attack_count_cost:
                raise ValueError("save has impossible pending Strike count")
            attacks_before = actor.strikes_this_turn - pending.attack_count_cost
            expected_penalty = multiple_attack_penalty(attacks_before, attack.traits)
            if paired_double_slice_non_agile:
                expected_penalty -= 2
            expected_count = attacks_before + 1
            if (
                pending.attack_actions_cost == 2
                and not hunter_aim
                and not intimidating_strike
                and "vicious_swing" not in get_definition(actor.definition_id).abilities
            ):
                raise ValueError("save has an unsupported pending two-action Strike")
        if pending.attack_penalty != expected_penalty or pending.attack_count != expected_count:
            raise ValueError("save has inconsistent pending Strike MAP or attack count")
        if check.attack_id != attack.attack_id or check.attack_count != expected_count or check.map_penalty != expected_penalty:
            raise ValueError("save has a pending check for a different Strike context")
        if check.traits != tuple(sorted(attack.traits)):
            raise ValueError("save has a pending check with different attack traits")
        distance = grid_distance_feet(actor.position, target.position)
        expected_ranged_penalty = 0
        if "ranged" in attack.traits:
            range_increment_ft, max_range_ft = self._effective_ranged_profile(
                state, actor, attack,
            )
            if max_range_ft is None or range_increment_ft is None or distance > max_range_ft:
                raise ValueError("save has an out-of-range pending Strike")
            expected_ranged_penalty = -2 * max(0, (distance - 1) // range_increment_ft)
            if actor.hunted_prey is not None and actor.hunted_prey.target_actor_id == target.actor_id:
                from .ranger import hunted_prey_range_penalty

                expected_ranged_penalty = hunted_prey_range_penalty(
                    distance, range_increment_ft, target_is_hunted_prey=True
                )
        elif distance > attack.reach_ft:
            raise ValueError("save has an out-of-reach pending Strike")
        if pending.ranged_penalty != expected_ranged_penalty:
            raise ValueError("save has an inconsistent pending range penalty")
        expected_modifiers = _strike_modifier_breakdown_full(
            attack,
            expected_penalty,
            pending.nonlethal,
            actor.prone and not actor.unconscious,
            ranged_penalty=pending.ranged_penalty,
            guidance_bonus=pending.guidance_bonus,
            enfeebled=self._enfeebled_value(state, actor.actor_id),
            lethal_penalty_exempt=self._powerful_fist_lethal_penalty_exempt(
                actor, attack, pending.nonlethal
            ),
        )
        item_modifier = self._attack_item_potency_modifier(
            state, actor, attack, item_id=pending.item_id
        )
        if item_modifier is not None:
            expected_modifiers = (*expected_modifiers, item_modifier)
        if pending.continuation is not None and pending.continuation.hunter_aim_intent is not None:
            from .ranger import hunter_aim_attack_bonus

            expected_modifiers = (*expected_modifiers, Modifier(
                hunter_aim_attack_bonus(pending.continuation.hunter_aim_intent),
                "circumstance",
                "Hunter's Aim",
            ))
        expected_modifiers = (*expected_modifiers, *self._strike_condition_modifiers(state, actor, attack), *self._mutagen_modifiers(state, actor, "attack", attack_traits=attack.traits))
        from .skill_actions import overextending_feint_penalty

        saved_overextending_penalty = overextending_feint_penalty(
            tuple(state.overextending_feint_effects),
            attacker_id=actor.actor_id,
            target_id=target.actor_id,
            actor_end_counts=state.actor_end_counts,
        )
        if saved_overextending_penalty:
            expected_modifiers = (*expected_modifiers, Modifier(
                saved_overextending_penalty, "circumstance", "Overextending Feint"
            ))
        if check.modifier_breakdown != expected_modifiers or check.modifier != combine_modifiers(expected_modifiers):
            raise ValueError("save has a pending check with inconsistent Strike modifiers")
        if (
            pending.feint_off_guard_applied
            and ("melee" not in attack.traits or "ranged" in attack.traits)
        ):
            raise ValueError("save has a Feint AC adjustment on an ineligible attack")
        if check.dc != self._attack_dc(
            state, actor, target, attack,
            feint_off_guard=pending.feint_off_guard_applied,
            target_off_guard=pending.attack_target_off_guard,
            nimble_dodge=pending.nimble_dodge_used,
            hunter_aim_intent=(
                pending.continuation.hunter_aim_intent
                if pending.continuation is not None
                else None
            ),
        ):
            raise ValueError("save has a pending check with inconsistent target AC")
        if pending.options != (ChoiceOption("keep", "Keep result"), ChoiceOption("spend_hero_point", "Spend 1 Hero Point and reroll")):
            raise ValueError("save has inconsistent pending Hero Point Strike options")

    def _validate_concealment_pending(self, state: EncounterState, pending: PendingChoice) -> None:
        """Validate the saved, observer-relative DC 5 targeting decision."""
        attacker = state.creatures.get(pending.actor_id or "")
        target = state.creatures.get(pending.target_id or "")
        continuation = pending.continuation
        check = pending.check
        if attacker is None or continuation is None or check is None:
            raise ValueError("save has an unavailable or inconsistent concealment flat-check choice")
        if continuation.kind == "cast" and pending.spell_id == "runic_weapon":
            try:
                item_facts = self._runic_weapon_target(
                    state, attacker, continuation.spell_target_item_id,
                    reach_spell_effective_range_ft=continuation.reach_spell_effective_range_ft,
                )
            except ValueError as error:
                raise ValueError("save has an unavailable Runic Weapon item concealment target") from error
            _item, wielder_id, _position = item_facts
            if (
                pending.owner_actor_id != attacker.actor_id
                or attacker.health_mode is not HealthMode.PC
                or attacker.hero_points < 1
                or continuation.actor_id != attacker.actor_id
                or continuation.target_id is not None
                or continuation.spell_target_id is not None
                or continuation.spell_target_item_id is None
                or pending.target_id is not None
                or pending.spell_target_item_id != continuation.spell_target_item_id
                or wielder_id != continuation.spell_target_wielder_id
                or wielder_id == attacker.actor_id
                or (wielder_id is not None and continuation.stage != "willing")
                or not continuation.concealment_checked
                or pending.concealment_checked is not True
                or not self._runic_weapon_item_concealed(state, attacker, item_facts)
                or check.die is None
                or check.modifier != 0
                or check.dc != 5
                or check.attack_id is not None
                or check.attack_count is not None
                or check.map_penalty != 0
                or check.traits
                or check.modifier_breakdown
                or continuation.sure_strike_used
                or pending.check_kind != "concealment"
                or pending.attack_id is not None
                or pending.damage_type is not None
                or pending.nonlethal
                or pending.is_reaction
                or pending.spell_id != "runic_weapon"
                or pending.slot_id != continuation.slot_id
                or pending.spell_actions != continuation.spell_actions
                or pending.actions_cost != continuation.spell_actions
                or continuation.spell_actions != 2
                or continuation.include_self is not None
                or not self._valid_committed_runic_weapon(attacker, continuation)
                or pending.attack_penalty != continuation.attack_penalty
                or pending.attack_count != continuation.attack_count
            ):
                raise ValueError("save has an unavailable or inconsistent Runic Weapon concealment choice")
            return
        if target is None:
            raise ValueError("save has an unavailable or inconsistent concealment flat-check choice")
        if (
            pending.owner_actor_id != attacker.actor_id
            or attacker.health_mode is not HealthMode.PC
            or attacker.hero_points < 1
            or continuation.actor_id != attacker.actor_id
            or continuation.target_id != target.actor_id
            or not continuation.concealment_checked
            or pending.concealment_checked is not True
            or not self.target_is_concealed(attacker.actor_id, target.actor_id)
            or check.die is None
            or check.modifier != 0
            or check.dc != 5
            or check.attack_id is not None
            or check.attack_count is not None
            or check.map_penalty != 0
            or check.traits
            or check.modifier_breakdown
            or continuation.sure_strike_used
            or pending.check_kind != "concealment"
            or pending.options != (
                ChoiceOption("keep", "Keep result"),
                ChoiceOption("spend_hero_point", "Spend 1 Hero Point and reroll"),
            )
            or pending.attack_penalty != continuation.attack_penalty
            or pending.attack_count != continuation.attack_count
        ):
            raise ValueError("save has an unavailable or inconsistent concealment flat-check choice")
        if continuation.kind == "family_action":
            if (
                pending.family_id != "martial"
                or pending.procedure_id is None
                or not pending.procedure_id.startswith("skill_actions:")
                or pending.attack_id is not None
                or pending.spell_id is not None
                or pending.actions_cost != 1
                or pending.family_command is None
            ):
                raise ValueError("save has an unavailable or inconsistent skill concealment choice")
            from . import skill_actions
            context = FamilyProcedureContext(
                self, state, self._dice.clone(), attacker,
                get_definition(attacker.definition_id), "martial", pending=pending,
            )
            skill_actions.validate_targeting_pending(context)
            return
        if continuation.kind == "cast":
            if (
                pending.spell_id not in CONCEALMENT_TARGETED_SPELL_IDS
                or continuation.spell_id != pending.spell_id
                or pending.slot_id != continuation.slot_id
                or pending.spell_actions != continuation.spell_actions
                or pending.actions_cost != continuation.spell_actions
                or pending.target_id != continuation.target_id
                or continuation.spell_target_id != target.actor_id
                or target.actor_id not in self._spell_targets_for_cast(
                    state, attacker, pending.spell_id, continuation.spell_actions,
                    reach_spell_effective_range_ft=continuation.reach_spell_effective_range_ft,
                )
                or pending.attack_id != (
                    "divine_lance" if pending.spell_id == "divine_lance" else None
                )
                or pending.damage_type is not None
                or pending.nonlethal
                or pending.is_reaction
                or continuation.spell_target_item_id is not None
                or continuation.include_self is not None
                or (
                    continuation.spell_source_kind not in {"prepared", "spontaneous"}
                    and not (
                        continuation.spell_source_kind == "focus"
                        and pending.spell_id == "force_bolt"
                    )
                )
                or not self._valid_committed_spell_concealment_cast(attacker, continuation)
            ):
                raise ValueError("save has an unavailable or inconsistent spell concealment choice")
            if pending.spell_id == "heal":
                if continuation.spell_actions not in (1, 2) or target.actor_id == attacker.actor_id:
                    raise ValueError("save has an unavailable Heal concealment choice")
            elif pending.spell_id == "divine_lance" and (
                not continuation.attack_count_committed
                or attacker.strikes_this_turn != continuation.attack_count
                or continuation.attack_penalty != multiple_attack_penalty(
                    attacker.strikes_this_turn - 1, spell_traits("divine_lance")
                )
            ):
                raise ValueError("save has inconsistent Divine Lance concealment MAP state")
            elif pending.spell_id in {"daze", "soothe", "protection", "fear", "void_warp", "guidance", "stabilize"}:
                expected_actions = {
                    "daze": 2,
                    "soothe": 2,
                    "protection": 2,
                    "fear": 2,
                    "void_warp": 2,
                    "guidance": 1,
                    "stabilize": 2,
                }[pending.spell_id]
                if continuation.spell_actions != expected_actions:
                    raise ValueError(f"save has an unavailable {pending.spell_id} concealment choice")
                if pending.spell_id in {"guidance", "stabilize"} and target.actor_id == attacker.actor_id:
                    raise ValueError(f"save has an unavailable self-target {pending.spell_id} concealment choice")
            elif pending.spell_id in {
                "runic_body", "force_bolt", "frostbite", "enfeeble",
                "telekinetic_projectile", "ignition", "gouging_claw", "tangle_vine",
            }:
                expected_actions = 1 if pending.spell_id == "force_bolt" else 2
                if continuation.spell_actions != expected_actions:
                    raise ValueError(f"save has an unavailable {pending.spell_id} concealment choice")
            return
        attack = self._find_attack(state, attacker, pending.attack_id)
        if (
            attack is None
            or continuation.target_id != target.actor_id
            or continuation.attack_id != attack.attack_id
            or continuation.kind not in {"strike", "ranged_strike", "reaction_strike"}
            or pending.attack_id != attack.attack_id
            or pending.damage_type != continuation.damage_type
            or pending.nonlethal != continuation.nonlethal
        ):
            raise ValueError("save has an unavailable or inconsistent concealment Strike choice")
        if pending.is_reaction != (continuation.kind == "reaction_strike"):
            raise ValueError("save has inconsistent concealment reaction context")

    @staticmethod
    def _valid_committed_spell_concealment_cast(caster, continuation) -> bool:
        """Confirm a saved dim-targeted cast still names its spent source."""
        spell_id = continuation.spell_id
        if spell_id not in CONCEALMENT_TARGETED_SPELL_IDS:
            return False
        definition = get_definition(caster.definition_id)
        if continuation.spell_source_kind == "spontaneous":
            access = tuple(
                item for item in definition.spontaneous_spells
                if item.spell_id == spell_id and item.rank == 1
            )
            if continuation.slot_id is None:
                return any(item.cantrip for item in access)
            slot = next(
                (item for item in caster.spontaneous_slots if item.slot_id == continuation.slot_id),
                None,
            )
            return bool(
                any(not item.cantrip for item in access)
                and slot is not None
                and slot.rank == 1
                and slot.remaining < slot.capacity
            )
        if continuation.spell_source_kind == "prepared":
            if continuation.slot_id is None:
                return any(
                    item.spell_id == spell_id and item.cantrip and not item.spent
                    for item in caster.prepared_slots
                )
            slot = next(
                (item for item in caster.prepared_slots if item.slot_id == continuation.slot_id),
                None,
            )
            from .preparation import prepared_slot_rejection

            finite_preparation_valid = (
                slot is not None
                and prepared_slot_rejection(caster, definition, slot, spell_id) is None
            )
            return bool(
                slot is not None
                and slot.spell_id == spell_id
                and slot.rank == 1
                and not slot.cantrip
                and slot.spent
                and finite_preparation_valid
            )
        if continuation.spell_source_kind == "focus":
            return bool(
                spell_id == "force_bolt"
                and continuation.slot_id == "actor_focus_pool"
                and any(
                    item.spell_id == "force_bolt" and item.rank == 1
                    for item in definition.focus_spells
                )
                and caster.focus_points < caster.focus_capacity
            )
        return False

    @staticmethod
    def _valid_committed_light_cast(caster, continuation) -> bool:
        """Confirm a saved Light cast still names its free cantrip access."""
        if (
            continuation.kind != "cast"
            or continuation.spell_id != "light"
            or continuation.spell_actions != 2
            or continuation.slot_id is not None
        ):
            return False
        definition = get_definition(caster.definition_id)
        if continuation.spell_source_kind == "spontaneous":
            return any(
                spell.spell_id == "light" and spell.rank == 1 and spell.cantrip
                for spell in definition.spontaneous_spells
            )
        if continuation.spell_source_kind == "prepared":
            return any(
                slot.spell_id == "light" and slot.rank == 1 and slot.cantrip and not slot.spent
                for slot in caster.prepared_slots
            )
        return False

    def _validate_damage_resolution_pending(
        self, state: EncounterState, pending: PendingChoice, *, expect_health_choice: bool
    ) -> None:
        resolution = pending.damage_resolution
        if resolution is None:
            raise ValueError("save has an incomplete damage resolution choice")
        attacker = state.creatures.get(resolution.actor_id)
        target = state.creatures.get(resolution.target_id)
        hero_owner = (
            self._familiar_hero_owner(state, target) or target
            if target is not None else None
        )
        if (
            attacker is None or target is None or attacker.actor_id == target.actor_id
            or pending.actor_id != attacker.actor_id or pending.target_id != target.actor_id
            or pending.owner_actor_id != hero_owner.actor_id
            or pending.check != resolution.check
            or pending.attack_id != resolution.attack_id
            or pending.spell_id != resolution.spell_id
            or pending.damage_type != resolution.damage_type
            or pending.nonlethal != resolution.nonlethal
            or pending.attack_critical != resolution.attacker_critical
            or pending.is_reaction != resolution.is_reaction
        ):
            raise ValueError("save has an inconsistent damage resolution owner or source")
        if resolution.source_kind == "strike":
            if self._find_attack(state, attacker, resolution.attack_id or "") is None:
                raise ValueError("save has a damage resolution for an unknown Strike")
        elif resolution.source_kind == "spell":
            if resolution.spell_id not in SPELLS:
                raise ValueError("save has a damage resolution for an unknown spell")
        elif resolution.source_kind != "family":
            raise ValueError("save has an unsupported damage resolution source")
        if len(resolution.group.results) != 1 or resolution.group.source_kind != resolution.source_kind:
            raise ValueError("save has an inconsistent damage resolution group")
        try:
            mitigation = apply_damage_defenses(
                resolution.group,
                self._justice_damage_defenses(
                    state,
                    resolution,
                    get_definition(target.definition_id).damage_defenses,
                ),
                resolution.selections,
            )
        except ValueError as error:
            raise ValueError("save has an invalid damage defense selection") from error
        if expect_health_choice:
            if (
                pending.damage_result is None
                or not pending.damage_result_is_mitigated
                or resolution.pending_defense_choice is not None
                or mitigation.unresolved_choices
                or len(mitigation.results) != 1
                or pending.damage_result != mitigation.results[0]
                or pending.transition_kind != "damage"
                or pending.health_normal is None
            ):
                raise ValueError("save has an inconsistent pending damage health choice")
            damage = mitigation.results[0]
            post_shield_damage = self._validate_completed_shield_block(
                state, resolution, target, damage
            )
            actor_damage = post_shield_damage - resolution.life_link_transfer
            if actor_damage < 0:
                raise ValueError("save has Life Link transfer beyond remaining damage")
            if resolution.life_link_transfer:
                source = state.creatures.get(resolution.life_link_source_actor_id or "")
                effect = next(
                    (item for item in state.active_effects
                     if item.effect_id == resolution.life_link_effect_id),
                    None,
                )
                if (
                    source is None
                    or "life_oracle" not in get_definition(source.definition_id).abilities
                    or resolution.life_link_transfer > post_shield_damage
                    or (
                        effect is not None
                        and (
                            effect.kind != "life_link"
                            or effect.source_actor_id != source.actor_id
                            or effect.target_actor_id != target.actor_id
                            or effect.value < resolution.life_link_transfer
                            or effect.life_link_used_round != state.round_number
                        )
                    )
                    or (effect is None and not (source.unconscious or source.dead))
                ):
                    raise ValueError("save has inconsistent Life Link damage evidence")
            temp_before = target.temporary_hp + pending.temporary_hp_absorbed
            if (
                pending.temporary_hp_absorbed != min(actor_damage, temp_before)
                or pending.remaining_hp_damage != actor_damage - pending.temporary_hp_absorbed
                or target.temporary_hp != max(0, temp_before - actor_damage)
            ):
                raise ValueError("save has inconsistent temporary HP damage accounting")
            expected_transition = self._propose_pc_damage(
                target,
                pending.remaining_hp_damage,
                damage_taken=actor_damage,
                attacker_critical=resolution.attacker_critical,
                target_critical_failure=resolution.target_critical_failure,
                nonlethal=resolution.nonlethal,
                hero_points=hero_owner.hero_points,
            )
            if (
                not expected_transition.heroic_recovery_available
                or expected_transition.heroic_recovery_option is None
                or pending.health_normal != expected_transition
                or pending.health_heroic != expected_transition.heroic_recovery_option
            ):
                raise ValueError("save has inconsistent pending damage health transitions")
            return

        if (
            pending.damage_result is not None
            or pending.damage_result_is_mitigated
            or resolution.pending_defense_choice is None
            or not mitigation.unresolved_choices
            or resolution.pending_defense_choice != mitigation.unresolved_choices[0]
        ):
            raise ValueError("save has an inconsistent pending damage defense choice")
        options, _by_type = self._damage_defense_options(
            resolution.group, mitigation.unresolved_choices[0]
        )
        if pending.options != options:
            raise ValueError("save has inconsistent pending damage defense options")

    def _validate_completed_shield_block(
        self,
        state: EncounterState,
        resolution: DamageResolution,
        target: CreatureState,
        damage: DamageResult,
    ) -> int:
        """Validate the saved Block decision and return damage reaching the actor."""
        status = resolution.shield_block_status
        record = resolution.shield_block_record
        if status is None:
            if resolution.shield_block_instance_id is not None or resolution.shield_block_magic or record is not None:
                raise ValueError("save has Shield Block data without a resolved decision")
            return damage.total
        if status == "pending":
            raise ValueError("save has unresolved Shield Block before the health choice")
        if resolution.shield_block_magic:
            magic_source = (
                resolution.source_kind == "spell"
                or "magical" in resolution.group.traits
                or (
                    resolution.source_kind == "strike"
                    and any(
                        component.amount > 0
                        and shield_block_trigger_eligible(component.damage_type, from_attack=True)
                        for component in damage.components
                    )
                )
            )
            if not magic_source:
                raise ValueError("save has magic Shield Block from an unsupported source")
            if resolution.shield_block_instance_id is not None:
                raise ValueError("save has magic Shield Block tied to an inventory item")
            if status == "declined":
                if record is not None or not target.reaction_available or target.magic_shield_expires_at_start <= state.actor_start_counts.get(target.actor_id, 0):
                    raise ValueError("save has inconsistent declined magic Shield Block data")
                return damage.total
            if (
                damage.total <= 0
                or status != "applied" or record is None or not record.magic
                or record.shield_instance_id != _MAGIC_SHIELD_BLOCK
                or record.hardness != 5 or record.incoming_damage != damage.total
                or record.shield_vulnerable_damage != 0 or record.damage_to_shield != 0
                or record.shield_hp_before != 0 or record.shield_hp_after != 0
                or record.prevented_from_actor != min(damage.total, 5)
                or record.damage_to_actor != damage.total - record.prevented_from_actor
                or target.reaction_available or target.magic_shield_expires_at_start != 0
                or target.shield_recast_available_at_seconds <= state.world_time_seconds
            ):
                raise ValueError("save has an inconsistent applied magic Shield Block record")
            return record.damage_to_actor
        shield_id = resolution.shield_block_instance_id
        if shield_id is None or resolution.source_kind != "strike":
            raise ValueError("save has a Shield Block decision without an attack shield")
        shield = state.item_instances.get(shield_id)
        profile = self._shield_profile(shield) if shield is not None else None
        if (
            shield is None or profile is None or shield.hp is None
            or shield_id not in target.held_items
        ):
            raise ValueError("save has a Shield Block decision for an unavailable shield")
        if status == "declined":
            if record is not None or not target.reaction_available:
                raise ValueError("save has inconsistent declined Shield Block data")
            current_shield = self._raised_shield_instance(state, target)
            if current_shield is None or current_shield.instance_id != shield_id:
                raise ValueError("save has a declined Shield Block without its raised shield")
            return damage.total
        if status != "applied" or record is None:
            raise ValueError("save has an unknown Shield Block outcome")
        shield_vulnerable = sum(
            component.amount
            for component in damage.components
            if component.damage_type.casefold() not in SHIELD_IMMUNE_DAMAGE_TYPES
        )
        integrity_before = shield_integrity(profile, record.shield_hp_before)
        if (
            record.shield_instance_id != shield_id
            or record.hardness != profile.hardness
            or record.incoming_damage != damage.total
            or record.shield_vulnerable_damage != shield_vulnerable
            or integrity_before.broken or integrity_before.destroyed
            or record.shield_hp_after != shield.hp
            or shield.hp != max(0, record.shield_hp_before - record.damage_to_shield)
            or record.prevented_from_actor != min(damage.total, profile.hardness)
            or record.damage_to_actor != damage.total - record.prevented_from_actor
            or record.damage_to_shield != max(0, shield_vulnerable - profile.hardness)
            or target.reaction_available
        ):
            raise ValueError("save has an inconsistent applied Shield Block record")
        raised = state.raised_shields.get(target.actor_id)
        if (shield.hp > profile.broken_threshold) != (
            raised is not None and raised.instance_id == shield_id
        ):
            raise ValueError("save has an inconsistent raised shield after Shield Block")
        return record.damage_to_actor

    def _validate_shield_block_pending(self, state: EncounterState, pending: PendingChoice) -> None:
        resolution = pending.damage_resolution
        if resolution is None:
            raise ValueError("save has an incomplete Shield Block choice")
        attacker = state.creatures.get(resolution.actor_id)
        target = state.creatures.get(resolution.target_id)
        if (
            attacker is None or target is None or attacker.actor_id == target.actor_id
            or pending.actor_id != attacker.actor_id or pending.target_id != target.actor_id
            or pending.owner_actor_id != target.actor_id
            or pending.check != resolution.check or pending.attack_id != resolution.attack_id
            or pending.damage_type != resolution.damage_type
            or pending.nonlethal != resolution.nonlethal
            or pending.attack_critical != resolution.attacker_critical
            or pending.is_reaction != resolution.is_reaction
            or resolution.source_kind not in {"strike", "spell"}
            or resolution.shield_block_status != "pending"
            or (not resolution.shield_block_magic and resolution.shield_block_instance_id is None)
            or (resolution.shield_block_magic and resolution.shield_block_instance_id is not None)
            or resolution.shield_block_record is not None
            or resolution.pending_defense_choice is not None
            or pending.damage_result is not None
            or pending.damage_result_is_mitigated
        ):
            raise ValueError("save has an inconsistent Shield Block owner or source")
        try:
            mitigation = apply_damage_defenses(
                resolution.group,
                self._justice_damage_defenses(
                    state,
                    resolution,
                    get_definition(target.definition_id).damage_defenses,
                ),
                resolution.selections,
            )
        except ValueError as error:
            raise ValueError("save has an invalid Shield Block damage defense selection") from error
        if mitigation.unresolved_choices or len(mitigation.results) != 1:
            raise ValueError("save has an unresolved defense before Shield Block")
        shield = self._shield_block_trigger(state, target, resolution, mitigation.results[0])
        if (
            shield is None
            or (shield == _MAGIC_SHIELD_BLOCK) != resolution.shield_block_magic
            or (
                shield != _MAGIC_SHIELD_BLOCK
                and shield.instance_id != resolution.shield_block_instance_id
            )
            or pending.options != (
                ChoiceOption("block", "Use Shield Block"),
                ChoiceOption("decline", "Decline"),
            )
        ):
            raise ValueError("save has an unavailable or inconsistent Shield Block choice")

    def save(self, path: str | Path) -> None:
        save_encounter(path, self._state, self._dice)

    def forensic_examine(
        self,
        actor_id: str,
        examination_key: str | None = None,
        *,
        body_key: str | None = None,
        subject_key: str | None = None,
    ) -> ActionResult:
        """Perform one authored Forensic Acumen examination outside combat.

        The examination is a public elapsed-time activity. Investigator owns
        its finite authored body and follow-up records; Encounter owns the
        transaction, saved dice cursor, pending choices and clock transition.
        """
        if not isinstance(actor_id, str) or not actor_id:
            return self._result(ResultStatus.REJECTED, "Forensic examination requires a non-empty actor id.")
        requested_keys = tuple(
            key for key in (examination_key, body_key, subject_key) if key is not None
        )
        if any(not isinstance(key, str) or not key for key in requested_keys):
            return self._result(ResultStatus.REJECTED, "Forensic examination requires a non-empty authored body key.")
        if len(set(requested_keys)) > 1:
            return self._result(ResultStatus.REJECTED, "Forensic examination keys must identify one authored body.")
        if self._state.in_progress:
            return self._result(ResultStatus.REJECTED, "Forensic examination is only available outside combat.")
        if self._state.pending_choice is not None:
            return self._result(ResultStatus.REJECTED, "A pending choice must be resolved before examination.")
        actor = self._state.creatures.get(actor_id)
        if actor is None:
            return self._result(ResultStatus.REJECTED, f"Unknown examination actor {actor_id!r}.")
        group_error = self._downtime_group_error((actor_id,))
        if group_error is not None:
            return self._result(ResultStatus.REJECTED, group_error)
        if FORENSIC_ACUMEN_ABILITY not in get_definition(actor.definition_id).abilities:
            return self._result(ResultStatus.UNSUPPORTED, "Forensic examination requires Forensic Acumen.")
        from .investigator import (
            ForensicExamination,
            _examination_records,
            _resolve_forensic_examination,
        )

        key = requested_keys[0] if requested_keys else None
        if key is None:
            records = tuple(
                item for item in _examination_records(
                    FamilyProcedureContext(
                        self,
                        self._state,
                        self._dice.clone(),
                        actor,
                        get_definition(actor.definition_id),
                        "martial",
                    )
                )
            )
            if len(records) != 1:
                return self._result(ResultStatus.REJECTED, "Choose one authored Forensic examination body.")
            key = records[0].key
        draft = deepcopy(self._state)
        dice = self._dice.clone()
        draft_actor = draft.creatures[actor_id]
        context = FamilyProcedureContext(
            self,
            draft,
            dice,
            draft_actor,
            get_definition(draft_actor.definition_id),
            "martial",
            command=ForensicExamination(key),
        )
        try:
            result = _resolve_forensic_examination(context, context.command)
            events = self._family_result_events(result, "martial")
        except _Rejected as error:
            return self._result(ResultStatus.REJECTED, str(error))
        except _Unsupported as error:
            return self._result(ResultStatus.UNSUPPORTED, str(error))
        except (DiceSourceError, ValueError, NotImplementedError) as error:
            return self._result(ResultStatus.REJECTED, str(error))
        self._state = draft
        self._dice = dice
        status = ResultStatus.PAUSED if draft.pending_choice is not None else ResultStatus.COMPLETED
        message = draft.pending_choice.prompt if draft.pending_choice is not None else (
            events[0].text if events else "Forensic examination completed."
        )
        return ActionResult(status, tuple(events), message, self.inspect())

    def streetwise(
        self,
        actor_id: str,
        question_key: str,
        *,
        mode: str,
        settlement_key: str | None = None,
    ) -> ActionResult:
        """Use the selected Streetwise feat on one authored local question."""
        if (not isinstance(actor_id, str) or not actor_id or not isinstance(question_key, str)
            or not question_key or mode not in {"recall", "gather"}
            or (settlement_key is not None and (not isinstance(settlement_key, str) or not settlement_key))):
            return self._result(ResultStatus.REJECTED, "Streetwise requires an actor, authored question, and recall or gather mode.")
        if self._state.in_progress:
            return self._result(ResultStatus.REJECTED, "Streetwise is only available outside combat.")
        if self._state.pending_choice is not None:
            return self._result(ResultStatus.REJECTED, "A pending choice must be resolved before Streetwise.")
        actor = self._state.creatures.get(actor_id)
        if actor is None:
            return self._result(ResultStatus.REJECTED, f"Unknown Streetwise actor {actor_id!r}.")
        group_error = self._downtime_group_error((actor_id,))
        if group_error is not None:
            return self._result(ResultStatus.REJECTED, group_error)
        from .investigator import Streetwise, _resolve_streetwise

        draft = deepcopy(self._state)
        dice = self._dice.clone()
        draft_actor = draft.creatures[actor_id]
        command = Streetwise(question_key, mode, settlement_key)
        context = FamilyProcedureContext(
            self, draft, dice, draft_actor, get_definition(draft_actor.definition_id),
            "martial", command=command,
        )
        try:
            result = _resolve_streetwise(context, command)
            events = self._family_result_events(result, "martial")
        except _Rejected as error:
            return self._result(ResultStatus.REJECTED, str(error))
        except _Unsupported as error:
            return self._result(ResultStatus.UNSUPPORTED, str(error))
        except (DiceSourceError, ValueError, NotImplementedError) as error:
            return self._result(ResultStatus.REJECTED, str(error))
        self._state = draft
        self._dice = dice
        status = ResultStatus.PAUSED if draft.pending_choice is not None else ResultStatus.COMPLETED
        message = draft.pending_choice.prompt if draft.pending_choice is not None else (
            events[0].text if events else "Streetwise completed."
        )
        return ActionResult(status, tuple(events), message, self.inspect())

    def streetwise_result(self, actor_id: str, question_key: str) -> ActionResult:
        """Read one saved authored Streetwise result in a later scene.

        This small public projection is intentionally keyed to an already
        completed finite question; it neither creates a new investigation nor
        infers a settlement fact for a scene that has not authored one.
        """
        if not isinstance(actor_id, str) or not actor_id or not isinstance(question_key, str) or not question_key:
            return self._result(ResultStatus.REJECTED, "Streetwise result requires an actor and authored question key.")
        actor = self._state.creatures.get(actor_id)
        if actor is None:
            return self._result(ResultStatus.REJECTED, f"Unknown Streetwise actor {actor_id!r}.")
        answer = actor.investigator_streetwise_results.get(question_key)
        if answer is None:
            return self._result(ResultStatus.REJECTED, "No saved Streetwise result matches that question.")
        event = Event(
            "streetwise_result", actor_id, None,
            f"{actor.label} recalls Streetwise information: {answer}",
            details=(f"Question: {question_key}",),
        )
        return ActionResult(ResultStatus.COMPLETED, (event,), event.text, self.inspect())

    def animal_empathy(self, actor_id: str, question_key: str, *, action: str) -> ActionResult:
        """Make an authored Animal Empathy Impression or Request with Diplomacy.

        The content supplies the animal's willingness, attitude, DCs, and four
        degree-specific answers. This records a bounded conversation; it does
        not turn an animal into a commanded combatant.
        """
        if not isinstance(actor_id, str) or not actor_id or not isinstance(question_key, str) or not question_key or action not in {"make_impression", "request"}:
            return self._result(ResultStatus.REJECTED, "Animal Empathy requires an actor, authored question, and Make an Impression or Request.")
        if self._state.in_progress:
            return self._result(ResultStatus.REJECTED, "Animal Empathy is only available outside combat.")
        if self._state.pending_choice is not None:
            return self._result(ResultStatus.REJECTED, "A pending choice must be resolved before Animal Empathy.")
        actor = self._state.creatures.get(actor_id)
        if actor is None or actor.health_mode is not HealthMode.PC or actor.unconscious or actor.dead:
            return self._result(ResultStatus.REJECTED, "Animal Empathy requires a conscious living PC.")
        definition = get_definition(actor.definition_id)
        if "animal_empathy" not in definition.abilities:
            return self._result(ResultStatus.UNSUPPORTED, "Animal Empathy requires the selected Voice of Nature feature.")
        record = next((item for item in get_setup(self._state.setup_id).animal_empathy if getattr(item, "question_key", None) == question_key), None)
        if record is None or record.animal_actor_id not in self._state.creatures:
            return self._result(ResultStatus.REJECTED, "No authored Animal Empathy question matches that selection.")
        attempt_key = f"{question_key}:{action}"
        if actor.druid_animal_empathy_attempts.get(attempt_key, 0) >= 1:
            return self._result(ResultStatus.REJECTED, f"That authored Animal Empathy {action.replace('_', ' ')} attempt is exhausted.")
        target = self._state.creatures[record.animal_actor_id]
        if target.dead or target.defeated:
            return self._result(ResultStatus.REJECTED, "The authored animal is no longer available for this conversation.")
        attitude = actor.druid_animal_empathy_attitudes.get(question_key, record.attitude)
        if action == "request" and attitude not in {"friendly", "helpful"}:
            return self._result(ResultStatus.REJECTED, "Request requires the authored animal to be friendly or helpful after Make an Impression.")
        draft = deepcopy(self._state)
        dice = self._dice.clone()
        check = resolve_check(dice.draw(20), self._skill_modifier(definition, "diplomacy"), record.will_dc if action == "make_impression" else record.request_dc)
        answers = record.impression_answers if action == "make_impression" else record.request_answers
        index = {DegreeOfSuccess.CRITICAL_FAILURE: 0, DegreeOfSuccess.FAILURE: 1, DegreeOfSuccess.SUCCESS: 2, DegreeOfSuccess.CRITICAL_SUCCESS: 3}[check.degree]
        answer = answers[index]
        draft_actor = draft.creatures[actor_id]
        draft_actor.druid_animal_empathy_attempts[attempt_key] = 1
        draft_actor.druid_animal_empathy_results[attempt_key] = answer
        if action == "make_impression":
            steps = {DegreeOfSuccess.CRITICAL_SUCCESS: 2, DegreeOfSuccess.SUCCESS: 1, DegreeOfSuccess.FAILURE: 0, DegreeOfSuccess.CRITICAL_FAILURE: -1}[check.degree]
            attitudes = ("hostile", "unfriendly", "indifferent", "friendly", "helpful")
            next_attitude = attitudes[max(0, min(len(attitudes) - 1, attitudes.index(attitude) + steps))]
            draft_actor.druid_animal_empathy_attitudes[question_key] = next_attitude
            self._advance_elapsed_time(draft, 60)
            details = (f"Animal willingness: {record.willingness}", f"Attitude: {attitude} → {next_attitude}", f"Question: {record.question}", "Make an Impression elapsed time: 60 seconds", "Animal Empathy grants no obedience or extra combat commands.")
        else:
            draft_actor.druid_animal_empathy_results[question_key] = answer
            if check.degree is DegreeOfSuccess.CRITICAL_FAILURE:
                attitudes = ("hostile", "unfriendly", "indifferent", "friendly", "helpful")
                next_attitude = attitudes[max(0, attitudes.index(attitude) - 1)]
                draft_actor.druid_animal_empathy_attitudes[question_key] = next_attitude
                attitude_detail = f"Attitude: {attitude} → {next_attitude} (Request critical failure)"
            else:
                attitude_detail = f"Attitude: {attitude}"
            details = (f"Animal willingness: {record.willingness}", attitude_detail, f"Question: {record.question}", "Animal Empathy grants no obedience or extra combat commands.")
        event = Event("animal_empathy", actor_id, record.animal_actor_id, f"{actor.label} uses Diplomacy to {('Make an Impression on' if action == 'make_impression' else 'Request help from')} {target.label}: {check.degree.label()} ({check.total} vs DC {check.dc}). {answer}", check=check, details=details)
        self._state = draft
        self._dice = dice
        return ActionResult(ResultStatus.COMPLETED, (event,), event.text, self.inspect())

    def animal_empathy_result(self, actor_id: str, question_key: str) -> ActionResult:
        actor = self._state.creatures.get(actor_id)
        if actor is None or not isinstance(question_key, str) or not question_key:
            return self._result(ResultStatus.REJECTED, "Animal Empathy result requires an actor and authored question key.")
        answer = actor.druid_animal_empathy_results.get(question_key)
        if answer is None:
            return self._result(ResultStatus.REJECTED, "No saved Animal Empathy result matches that question.")
        event = Event("animal_empathy_result", actor_id, None, f"{actor.label} recalls Animal Empathy information: {answer}", details=(f"Question: {question_key}",))
        return ActionResult(ResultStatus.COMPLETED, (event,), event.text, self.inspect())

    def pursue_lead(
        self,
        actor_id: str,
        case_id: str,
        clue_key: str | None = None,
        *,
        open_investigation: bool = True,
        replace_case_id: str | None = None,
    ) -> ActionResult:
        """Pursue one authored On the Case clue outside combat.

        This is an elapsed-time activity, so it remains available after a
        finished encounter and commits through the same cloned state/dice
        transaction as the other public downtime procedures.
        """
        if not isinstance(actor_id, str) or not actor_id:
            return self._result(ResultStatus.REJECTED, "Pursue a Lead requires a non-empty actor id.")
        if not isinstance(case_id, str) or not case_id:
            return self._result(ResultStatus.REJECTED, "Pursue a Lead requires a non-empty authored case id.")
        if clue_key is not None and (not isinstance(clue_key, str) or not clue_key):
            return self._result(ResultStatus.REJECTED, "Pursue a Lead requires a non-empty authored clue key.")
        if replace_case_id is not None and (not isinstance(replace_case_id, str) or not replace_case_id):
            return self._result(ResultStatus.REJECTED, "A replacement investigation requires a non-empty case id.")
        if type(open_investigation) is not bool:
            return self._result(ResultStatus.REJECTED, "open_investigation must be a boolean.")
        if self._state.pending_choice is not None:
            return self._result(ResultStatus.REJECTED, "A pending choice must be resolved before pursuing a lead.")
        actor = self._state.creatures.get(actor_id)
        if actor is None:
            return self._result(ResultStatus.REJECTED, f"Unknown Pursue a Lead actor {actor_id!r}.")
        if actor.health_mode is not HealthMode.PC or actor.unconscious or actor.dead:
            return self._result(ResultStatus.REJECTED, "Pursue a Lead requires a conscious living PC.")
        from .investigator import PursueLead, _investigation_records, _resolve_pursue_lead

        context = FamilyProcedureContext(
            self, self._state, self._dice.clone(), actor, get_definition(actor.definition_id), "martial"
        )
        if not _investigation_records(context):
            return self._result(ResultStatus.REJECTED, "No authored investigations are available in this scene.")
        draft = deepcopy(self._state)
        dice = self._dice.clone()
        draft_actor = draft.creatures[actor_id]
        context = FamilyProcedureContext(
            self,
            draft,
            dice,
            draft_actor,
            get_definition(draft_actor.definition_id),
            "martial",
            command=PursueLead(case_id, clue_key, open_investigation, replace_case_id),
        )
        try:
            result = _resolve_pursue_lead(context, context.command)
            events = self._family_result_events(result, "martial")
        except _Rejected as error:
            return self._result(ResultStatus.REJECTED, str(error))
        except _Unsupported as error:
            return self._result(ResultStatus.UNSUPPORTED, str(error))
        except (DiceSourceError, ValueError, NotImplementedError) as error:
            return self._result(ResultStatus.REJECTED, str(error))
        self._state = draft
        self._dice = dice
        event_tuple = tuple(events)
        return ActionResult(
            ResultStatus.COMPLETED,
            event_tuple,
            event_tuple[0].text if event_tuple else "Pursue a Lead completed.",
            self.inspect(),
        )

    pursue = pursue_lead
    pursue_a_lead = pursue_lead

    def close_investigation(self, actor_id: str, case_id: str) -> ActionResult:
        """Close one solved or abandoned authored investigation."""
        if not isinstance(actor_id, str) or not actor_id or not isinstance(case_id, str) or not case_id:
            return self._result(ResultStatus.REJECTED, "Closing an investigation requires actor and case ids.")
        if self._state.in_progress:
            return self._result(ResultStatus.REJECTED, "Investigations can be closed only outside combat.")
        if self._state.pending_choice is not None:
            return self._result(ResultStatus.REJECTED, "A pending choice must be resolved before closing an investigation.")
        actor = self._state.creatures.get(actor_id)
        if actor is None:
            return self._result(ResultStatus.REJECTED, f"Unknown investigation actor {actor_id!r}.")
        if actor.health_mode is not HealthMode.PC or actor.unconscious or actor.dead:
            return self._result(ResultStatus.REJECTED, "Closing an investigation requires a conscious living PC.")
        if case_id not in actor.investigator_active_cases:
            return self._result(ResultStatus.REJECTED, "That investigation is not active.")
        draft = deepcopy(self._state)
        draft_actor = draft.creatures[actor_id]
        draft_actor.investigator_active_cases.discard(case_id)
        draft_actor.investigator_solved_cases.discard(case_id)
        draft_actor.investigator_abandoned_cases.discard(case_id)
        draft_actor.investigator_awareness.clear()
        from .investigator import _sync_investigation_awareness
        context = FamilyProcedureContext(
            self, draft, self._dice.clone(), draft_actor, get_definition(draft_actor.definition_id), "martial"
        )
        _sync_investigation_awareness(context)
        event = Event("investigation_closed", actor_id, None, f"{draft_actor.label} closes investigation {case_id}.")
        self._state = draft
        return ActionResult(ResultStatus.COMPLETED, (event,), event.text, self.inspect())

    def mark_investigation_solved(self, actor_id: str, case_id: str) -> ActionResult:
        """Record the authored larger-mystery solution while retaining benefits."""
        if not isinstance(actor_id, str) or not actor_id or not isinstance(case_id, str) or not case_id:
            return self._result(ResultStatus.REJECTED, "Solving an investigation requires actor and case ids.")
        if self._state.in_progress or self._state.pending_choice is not None:
            return self._result(ResultStatus.REJECTED, "Investigations can be marked solved only outside combat without a pending choice.")
        actor = self._state.creatures.get(actor_id)
        if actor is None or actor.health_mode is not HealthMode.PC or actor.unconscious or actor.dead:
            return self._result(ResultStatus.REJECTED, "Solving an investigation requires a conscious living PC.")
        if case_id not in actor.investigator_active_cases:
            return self._result(ResultStatus.REJECTED, "That investigation is not active.")
        draft = deepcopy(self._state)
        draft.creatures[actor_id].investigator_solved_cases.add(case_id)
        event = Event("investigation_solved", actor_id, None, f"{draft.creatures[actor_id].label} marks investigation {case_id} solved; its benefits remain active.")
        self._state = draft
        return ActionResult(ResultStatus.COMPLETED, (event,), event.text, self.inspect())

    solve_investigation = mark_investigation_solved

    # These aliases keep the outside-combat API discoverable for callers that
    # use the action's printed name or the body's shorter name.
    def examine(self, actor_id: str, examination_key: str | None = None, **kwargs) -> ActionResult:
        return self.forensic_examine(actor_id, examination_key, **kwargs)

    def examine_body(self, actor_id: str, body_key: str | None = None, **kwargs) -> ActionResult:
        return self.forensic_examine(actor_id, body_key, **kwargs)

    def refocus(self, actor_id: str) -> ActionResult:
        """Spend ten minutes outside combat to restore one Focus Point.

        Refocus is deliberately a public activity instead of a normal combat
        command: finished encounters have no active turn.  The whole elapsed
        time transition and resource change happen on one cloned state/dice
        draft, so every rejected eligibility or health boundary is atomic.
        """
        if not isinstance(actor_id, str) or not actor_id:
            return self._result(ResultStatus.REJECTED, "Refocus requires a non-empty actor id.")
        state = self._state
        if state.in_progress:
            return self._result(ResultStatus.REJECTED, "Refocus is only available outside combat.")
        if state.pending_choice is not None:
            return self._result(ResultStatus.REJECTED, "A pending choice must be resolved before Refocus.")
        if any(creature.spell_substitution is not None for creature in state.creatures.values()):
            return self._result(ResultStatus.REJECTED, "Spell Substitution must be explicitly interrupted or completed before Refocus.")
        actor = state.creatures.get(actor_id)
        if actor is None:
            return self._result(ResultStatus.REJECTED, f"Unknown Refocus actor {actor_id!r}.")
        if actor.health_mode is not HealthMode.PC or actor.unconscious or actor.dead:
            return self._result(ResultStatus.REJECTED, "Refocus requires a conscious living PC.")
        if actor.focus_capacity < 1:
            return self._result(ResultStatus.REJECTED, "This actor has no Focus Point pool to Refocus.")
        if (
            "witch_familiar" in get_definition(actor.definition_id).abilities
            and not any(
                self._familiar_owned_by(actor, familiar) and not familiar.dead
                for familiar in state.creatures.values()
            )
        ):
            return self._result(ResultStatus.REJECTED, "Refocus requires the Witch's living familiar.")
        if any(creature.dying > 0 for creature in state.creatures.values()):
            return self._result(ResultStatus.REJECTED, "Refocus cannot advance time while a dying check is unresolved.")
        if any(creature.unconscious and not creature.dead for creature in state.creatures.values()):
            return self._result(ResultStatus.REJECTED, "Refocus cannot advance time while an unconscious actor needs unsupported recovery.")

        draft = deepcopy(state)
        dice = self._dice.clone()
        self._advance_elapsed_time(draft, 600)
        draft.creatures[actor_id].focus_points = min(
            draft.creatures[actor_id].focus_capacity,
            draft.creatures[actor_id].focus_points + 1,
        )
        if "life_oracle" in get_definition(actor.definition_id).abilities:
            draft.creatures[actor_id].oracle_cursebound = max(
                0, draft.creatures[actor_id].oracle_cursebound - 1
            )
        event = Event(
            "refocus",
            actor_id,
            actor_id,
            f"{draft.creatures[actor_id].label} Refocuses for 10 minutes and regains 1 Focus Point.",
            details=(f"world time advanced to {draft.world_time_seconds} seconds",),
        )
        self._state = draft
        self._dice = dice
        return ActionResult(ResultStatus.COMPLETED, (event,), event.text, self.inspect())

    def scrub_sigil(self, actor_id: str, effect_id: str) -> ActionResult:
        """Spend Sigil's printed five minutes washing or scraping one mark.

        This is deliberately a finite outside-combat activity: it changes no
        item identity and advances the same elapsed clock that naturally
        fades a creature mark after one week.
        """
        if not isinstance(effect_id, str) or not effect_id:
            return self._result(ResultStatus.REJECTED, "Scrub Sigil requires one active effect id.")
        error = self._downtime_group_error((actor_id,))
        if error is not None:
            return self._result(ResultStatus.REJECTED, error)
        state = self._state
        creature_effect = next((item for item in state.active_effects if item.effect_id == effect_id and item.kind == "sigil"), None)
        item_effect = next((item for item in state.active_item_effects if item.effect_id == effect_id and item.kind == "sigil"), None)
        if creature_effect is None and item_effect is None:
            return self._result(ResultStatus.REJECTED, "That Sigil is no longer active.")
        target_position = (
            state.creatures[creature_effect.target_actor_id].position
            if creature_effect is not None and creature_effect.target_actor_id in state.creatures
            else self._item_position(state, item_effect.item_id) if item_effect is not None else None
        )
        actor = state.creatures[actor_id]
        if target_position is None or grid_distance_feet(actor.position, target_position) > 5:
            return self._result(ResultStatus.REJECTED, "Scrub Sigil requires touching the marked creature or item.")
        draft = deepcopy(state)
        self._advance_elapsed_time(draft, 300)
        draft.active_effects[:] = [effect for effect in draft.active_effects if effect.effect_id != effect_id]
        draft.active_item_effects[:] = [effect for effect in draft.active_item_effects if effect.effect_id != effect_id]
        event = Event(
            "sigil_scrubbed", actor_id, None,
            f"{draft.creatures[actor_id].label} spends 5 minutes washing or scraping away a Sigil.",
        )
        self._state = draft
        return ActionResult(ResultStatus.COMPLETED, (event,), event.text, self.inspect())

    def nudge_the_scales(self, actor_id: str, target_id: str) -> ActionResult:
        """Use the Life Oracle's one-action, cursebound healing grant."""
        state = self._state
        actor = state.creatures.get(actor_id)
        target = state.creatures.get(target_id)
        if actor is None or target is None or self._active_actor_id(state) != actor_id:
            return self._result(ResultStatus.REJECTED, "Nudge the Scales requires the active Oracle and an existing target.")
        if state.pending_choice is not None or actor.actions_remaining < 1 or actor.unconscious or actor.dead:
            return self._result(ResultStatus.REJECTED, "Nudge the Scales requires one available action without a pending choice.")
        if "nudge_the_scales" not in get_definition(actor.definition_id).abilities or target.dead:
            return self._result(ResultStatus.REJECTED, "Nudge the Scales requires the selected Life Oracle and a living target.")
        if grid_distance_feet(actor.position, target.position) > 30:
            return self._result(ResultStatus.REJECTED, "Nudge the Scales has a range of 30 feet.")
        if actor.oracle_cursebound >= 2:
            return self._result(ResultStatus.REJECTED, "Nudge the Scales cannot increase cursebound beyond 2.")
        from .oracle import healing_after_curse
        draft = deepcopy(state)
        draft_actor = draft.creatures[actor_id]
        draft_target = draft.creatures[target_id]
        oracle_level = get_definition(draft_actor.definition_id).level
        base_healing = 2 + 2 * oracle_level
        amount = (
            healing_after_curse(
                base_healing, draft_target.oracle_cursebound,
                level=get_definition(draft_target.definition_id).level,
            )
            if "life_oracle" in get_definition(draft_target.definition_id).abilities
            else base_healing
        )
        if draft_target.health_mode is HealthMode.PC:
            self._apply_health_transition(draft, draft_target, pc_healing(self._health_state(draft_target), amount))
        else:
            draft_target.hp = min(get_definition(draft_target.definition_id).hp, draft_target.hp + amount)
        draft_actor.actions_remaining -= 1
        draft_actor.oracle_cursebound += 1
        event = Event("nudge_the_scales", actor_id, target_id, f"{draft_actor.label} nudges {draft_target.label}'s life force for {amount} healing; cursebound is now {draft_actor.oracle_cursebound}.")
        self._state = draft
        return ActionResult(ResultStatus.COMPLETED, (event,), event.text, self.inspect())

    def set_oracle_life_mode(self, actor_id: str, mode: str) -> ActionResult:
        """Select the Life Oracle's finite mode for an already-rested daily prep."""
        actor = self._state.creatures.get(actor_id)
        if self._state.in_progress or self._state.pending_choice is not None or actor is None:
            return self._result(ResultStatus.REJECTED, "Oracle life mode can be selected only outside combat without a pending choice.")
        if mode not in {"life", "death"} or "life_oracle" not in get_definition(actor.definition_id).abilities:
            return self._result(ResultStatus.REJECTED, "Select life or death for the selected Life Oracle.")
        if actor_id not in self._state.rested_actor_ids or self._state.last_prepared_day.get(actor_id, 0) == self._state.preparation_day:
            return self._result(ResultStatus.REJECTED, "Oracle life mode requires recorded rest before that day's daily preparation.")
        if actor.oracle_life_mode_selected_day == self._state.preparation_day:
            return self._result(ResultStatus.REJECTED, "Oracle life mode is already selected for this daily preparation.")
        draft = deepcopy(self._state)
        draft.creatures[actor_id].oracle_life_mode = mode
        draft.creatures[actor_id].oracle_life_mode_selected_day = draft.preparation_day
        event = Event("oracle_life_mode", actor_id, actor_id, f"{actor.label} selects {mode} mode for today's daily preparation.")
        self._state = draft
        return ActionResult(ResultStatus.COMPLETED, (event,), event.text, self.inspect())

    def start_spell_substitution(
        self, actor_id: str, slot_id: str, replacement_spell_id: str,
    ) -> ActionResult:
        """Begin the staged Wizard's ten-minute, explicitly interruptible work."""
        error = self._downtime_group_error((actor_id,))
        if error is not None:
            return self._result(ResultStatus.REJECTED, error)
        actor = self._state.creatures.get(actor_id)
        if actor is None:
            return self._result(ResultStatus.REJECTED, f"Unknown downtime actor {actor_id!r}.")
        if any(item.spell_substitution is not None for item in self._state.creatures.values()):
            return self._result(ResultStatus.REJECTED, "A Spell Substitution activity is already in progress.")
        from .wizard import substitution_rejection

        rejection = substitution_rejection(
            actor, get_definition(actor.definition_id),
            slot_id=slot_id, replacement_spell_id=replacement_spell_id,
        )
        if rejection is not None:
            return self._result(ResultStatus.REJECTED, rejection)
        draft = deepcopy(self._state)
        draft.creatures[actor_id].spell_substitution = SpellSubstitutionState(
            slot_id, next(slot.spell_id for slot in actor.prepared_slots if slot.slot_id == slot_id),
            replacement_spell_id,
        )
        event = Event("spell_substitution_started", actor_id, None, f"{actor.label} begins Spell Substitution; 600 uninterrupted seconds are required.")
        self._state = draft
        return ActionResult(ResultStatus.COMPLETED, (event,), event.text, self.inspect())

    def advance_spell_substitution(self, actor_id: str, elapsed_seconds: int) -> ActionResult:
        """Charge real uninterrupted elapsed time; only the final second changes the slot."""
        if type(elapsed_seconds) is not int or elapsed_seconds <= 0:
            return self._result(ResultStatus.REJECTED, "Spell Substitution advancement requires positive elapsed seconds.")
        actor = self._state.creatures.get(actor_id)
        progress = actor.spell_substitution if actor is not None else None
        if actor is None or progress is None:
            return self._result(ResultStatus.REJECTED, "This actor has no Spell Substitution activity in progress.")
        if progress.elapsed_seconds + elapsed_seconds > 600:
            return self._result(ResultStatus.REJECTED, "Spell Substitution cannot advance beyond its required 600 seconds.")
        draft = deepcopy(self._state)
        self._advance_elapsed_time(draft, elapsed_seconds)
        draft_actor = draft.creatures[actor_id]
        draft_progress = draft_actor.spell_substitution
        assert draft_progress is not None
        draft_progress.elapsed_seconds += elapsed_seconds
        if draft_progress.elapsed_seconds == 600:
            slot = next(slot for slot in draft_actor.prepared_slots if slot.slot_id == draft_progress.slot_id)
            slot.spell_id = draft_progress.replacement_spell_id
            draft_actor.spell_substitution = None
            event = Event("spell_substitution_completed", actor_id, None, f"{draft_actor.label} completes Spell Substitution: {draft_progress.original_spell_id} becomes {slot.spell_id}.")
        else:
            event = Event("spell_substitution_advanced", actor_id, None, f"{draft_actor.label} advances Spell Substitution to {draft_progress.elapsed_seconds}/600 seconds.")
        self._state = draft
        return ActionResult(ResultStatus.COMPLETED, (event,), event.text, self.inspect())

    def interrupt_spell_substitution(self, actor_id: str) -> ActionResult:
        actor = self._state.creatures.get(actor_id)
        if actor is None or actor.spell_substitution is None:
            return self._result(ResultStatus.REJECTED, "This actor has no Spell Substitution activity to interrupt.")
        draft = deepcopy(self._state)
        progress = draft.creatures[actor_id].spell_substitution
        assert progress is not None
        draft.creatures[actor_id].spell_substitution = None
        event = Event("spell_substitution_interrupted", actor_id, None, f"{draft.creatures[actor_id].label} interrupts Spell Substitution after {progress.elapsed_seconds}/600 seconds; {progress.original_spell_id} remains prepared.")
        self._state = draft
        return ActionResult(ResultStatus.COMPLETED, (event,), event.text, self.inspect())

    @staticmethod
    def _normalize_downtime_actor_ids(actor_ids: Iterable[str]) -> tuple[str, ...] | None:
        """Validate the explicit actor group used by downtime activities."""
        if isinstance(actor_ids, (str, bytes)):
            return None
        try:
            normalized = tuple(actor_ids)
        except TypeError:
            return None
        if (
            not normalized
            or any(type(actor_id) is not str or not actor_id for actor_id in normalized)
            or len(set(normalized)) != len(normalized)
        ):
            return None
        return normalized

    def _downtime_group_error(self, actor_ids: tuple[str, ...]) -> str | None:
        """Return a shared rejection for outside-combat downtime boundaries."""
        state = self._state
        if state.in_progress:
            return "Downtime activities are only available outside combat."
        if state.pending_choice is not None:
            return "A pending choice must be resolved before a downtime activity."
        if any(creature.spell_substitution is not None for creature in state.creatures.values()):
            return "Spell Substitution must be explicitly interrupted or completed before another downtime activity."
        if any(creature.dying > 0 for creature in state.creatures.values()):
            return "Downtime cannot advance time while a dying check is unresolved."
        if any(creature.unconscious and not creature.dead for creature in state.creatures.values()):
            return "Downtime cannot advance time while an unconscious actor needs unsupported recovery."
        for actor_id in actor_ids:
            actor = state.creatures.get(actor_id)
            if actor is None:
                return f"Unknown downtime actor {actor_id!r}."
            if actor.health_mode is not HealthMode.PC or actor.unconscious or actor.dead:
                return "Downtime requires a conscious living PC group."
        return None

    def recover_versatile_vials(self, actor_id: str, *, elapsed_seconds: int) -> ActionResult:
        """Record declared exploration time and recover the selected Bomber's vials."""
        if self._state.in_progress:
            return self._result(ResultStatus.REJECTED, "Versatile vial recovery requires a completed encounter.")
        if type(elapsed_seconds) is not int or elapsed_seconds <= 0:
            return self._result(ResultStatus.REJECTED, "Versatile vial recovery requires positive elapsed seconds.")
        if actor_id not in self._state.alchemy_states:
            return self._result(ResultStatus.REJECTED, "This actor has no admitted versatile vial resource.")
        from .alchemy import recover_versatile_vials
        draft = deepcopy(self._state)
        self._advance_elapsed_time(draft, elapsed_seconds)
        before = draft.alchemy_states[actor_id]
        after = recover_versatile_vials(before, elapsed_seconds)
        draft.alchemy_states[actor_id] = after
        self._state = draft
        text = f"Recovered versatile vials for {draft.creatures[actor_id].label}: {before.stored_vials} to {after.stored_vials}."
        return ActionResult(ResultStatus.COMPLETED, (Event("versatile_vials_recovered", actor_id, actor_id, text),), text, self.inspect())

    def record_rested(
        self,
        actor_ids: Iterable[str],
        *,
        day_number: int,
        elapsed_seconds: int,
    ) -> ActionResult:
        """Declare externally adjudicated rest eligibility for selected PCs.

        This boundary records a fact supplied by the caller and advances the
        supported elapsed clock.  It does not simulate sleep, natural healing,
        fatigue recovery, or any other unadmitted rest procedure.
        """
        normalized = self._normalize_downtime_actor_ids(actor_ids)
        if normalized is None:
            return self._result(ResultStatus.REJECTED, "Rest eligibility requires a non-empty unique actor group.")
        if type(day_number) is not int or day_number < 1:
            return self._result(ResultStatus.REJECTED, "Rest eligibility requires a positive declared day number.")
        if type(elapsed_seconds) is not int or elapsed_seconds <= 0:
            return self._result(ResultStatus.REJECTED, "Rest eligibility requires positive elapsed seconds.")
        error = self._downtime_group_error(normalized)
        if error is not None:
            return self._result(ResultStatus.REJECTED, error)
        state = self._state
        if day_number < state.preparation_day:
            return self._result(ResultStatus.REJECTED, "Declared preparation day cannot move backward.")

        draft = deepcopy(state)
        dice = self._dice.clone()
        self._advance_elapsed_time(draft, elapsed_seconds)
        if day_number > draft.preparation_day:
            # A new declared day invalidates any unused eligibility from an
            # earlier day before the newly rested actors are recorded.
            draft.preparation_day = day_number
            draft.rested_actor_ids.clear()
        draft.rested_actor_ids.update(normalized)
        labels = ", ".join(draft.creatures[actor_id].label for actor_id in normalized)
        event = Event(
            "rest_recorded",
            None,
            None,
            f"Recorded externally adjudicated rest eligibility for {labels} on preparation day {draft.preparation_day}.",
            details=(
                "This declaration does not simulate sleep, natural healing, fatigue recovery, or conditions.",
                f"world time advanced to {draft.world_time_seconds} seconds",
            ),
        )
        self._state = draft
        self._dice = dice
        return ActionResult(ResultStatus.COMPLETED, (event,), event.text, self.inspect())

    def daily_prepare(
        self,
        actor_ids: Iterable[str],
        preparations: Mapping[str, Mapping[str, str]] | None = None,
    ) -> ActionResult:
        """Perform one explicit daily preparation for rested selected PCs."""
        normalized = self._normalize_downtime_actor_ids(actor_ids)
        if normalized is None:
            return self._result(ResultStatus.REJECTED, "Daily preparation requires a non-empty unique actor group.")
        error = self._downtime_group_error(normalized)
        if error is not None:
            return self._result(ResultStatus.REJECTED, error)
        state = self._state
        missing = tuple(actor_id for actor_id in normalized if actor_id not in state.rested_actor_ids)
        if missing:
            return self._result(
                ResultStatus.REJECTED,
                "Daily preparation requires recorded rest eligibility for every selected actor.",
            )
        repeated = tuple(
            actor_id
            for actor_id in normalized
            if state.last_prepared_day.get(actor_id, 0) == state.preparation_day
        )
        if repeated:
            return self._result(
                ResultStatus.REJECTED,
                "Each selected actor may prepare only once on the current declared day.",
            )

        if preparations is not None:
            if not isinstance(preparations, Mapping) or set(preparations) != set(normalized):
                return self._result(
                    ResultStatus.REJECTED,
                    "Daily preparation choices must name exactly the selected actors.",
                )

        # Validate every proposed slot before cloning time, resources, or any
        # actor state.  A Wizard's finite spellbook is intentionally shared by
        # daily preparation, substitution, casting, and save validation.
        from .preparation import prepared_slot_rejection

        selected_preparations: dict[str, Mapping[str, str]] = {}
        for actor_id in normalized:
            actor = state.creatures[actor_id]
            definition = get_definition(actor.definition_id)
            if "life_oracle" in definition.abilities and actor.oracle_life_mode_selected_day != state.preparation_day:
                return self._result(ResultStatus.REJECTED, "Life Oracle daily preparation requires choosing life or death mode after rest.")
            proposed = preparations[actor_id] if preparations is not None else {
                slot.slot_id: slot.spell_id for slot in actor.prepared_slots
            }
            if not isinstance(proposed, Mapping) or set(proposed) != {
                slot.slot_id for slot in actor.prepared_slots
            }:
                return self._result(
                    ResultStatus.REJECTED,
                    "Daily preparation choices must select every existing prepared slot exactly once.",
                )
            for slot in actor.prepared_slots:
                spell_id = proposed[slot.slot_id]
                rejection = prepared_slot_rejection(actor, definition, slot, spell_id)
                if rejection is not None:
                    return self._result(ResultStatus.REJECTED, rejection)
            selected_preparations[actor_id] = proposed

        draft = deepcopy(state)
        dice = self._dice.clone()
        self._advance_elapsed_time(draft, 60 * 60)
        familiar_replacements: list[Event] = []
        for actor_id in normalized:
            actor = draft.creatures[actor_id]
            choices = selected_preparations[actor_id]
            actor.prepared_slots = [
                replace(slot, spell_id=choices[slot.slot_id], spent=False)
                for slot in actor.prepared_slots
            ]
            actor.spontaneous_slots = [
                replace(slot, remaining=slot.capacity)
                for slot in actor.spontaneous_slots
            ]
            actor.focus_points = actor.focus_capacity
            actor.arcane_bond_recast_until_start = 0
            actor.arcane_bond_item_id = None
            actor.arcane_bond_eligible_slots.clear()
            actor.spell_substitution = None
            # Hunt Prey lasts until the Ranger's next daily preparations. A
            # carried target identity may outlive a scene even when that
            # creature is not present in the next encounter.
            actor.hunted_prey = None
            actor.precision_used_round = 0
            draft.desperate_prayer_used.discard(actor_id)
            draft.desperate_prayer_points.discard(actor_id)
            if actor_id in draft.alchemy_states:
                from .alchemy import advanced_alchemy_capacity, daily_prepare_alchemy
                old_ids = [item_id for item_id, item in draft.infused_alchemy_items.items()
                           if item.creator_actor_id == actor_id]
                stable_item_ids = {
                    runtime_item_instance_id(actor_id, item.instance_id)
                    for item in get_definition(actor.definition_id).item_instances
                }
                # An infused elixir's benefit is creator-owned as well as its
                # physical stock.  Daily preparation ends that finite effect
                # even when the recipient is another creature.
                old_effect_ids = {f"alchemy:{item_id}" for item_id in old_ids}
                draft.active_effects[:] = [
                    effect for effect in draft.active_effects
                    if effect.effect_id not in old_effect_ids
                ]
                for item_id in old_ids:
                    if item_id in stable_item_ids:
                        # The old physical identity remains serialized as consumed history;
                        # it cannot reappear as current stock after its preparation ends.
                        draft.consumed_infused_item_ids.add(item_id)
                    else:
                        draft.infused_alchemy_items.pop(item_id, None)
                        draft.consumed_infused_item_ids.discard(item_id)
                        draft.item_instances.pop(item_id, None)
                    for holder in draft.creatures.values():
                        for inventory in (holder.held_items, holder.worn_items, holder.stowed_items):
                            if item_id in inventory:
                                inventory.remove(item_id)
                    for position, items in tuple(draft.ground_items.items()):
                        if item_id in items:
                            items.remove(item_id)
                            if not items:
                                del draft.ground_items[position]
                prepared_alchemy = daily_prepare_alchemy(
                    draft.alchemy_states[actor_id],
                    # A level-two Bomber knows ten formulas but Advanced
                    # Alchemy still creates only 4 + Intelligence items.
                    # The ordered finite book preserves the authored L1
                    # default choices while the additional L2 formulas remain
                    # legal Quick Alchemy selections.
                    draft.alchemy_states[actor_id].known_formula_ids[
                        :advanced_alchemy_capacity(draft.alchemy_states[actor_id])
                    ],
                    creator_actor_id=actor_id, preparation_id=f"day:{draft.preparation_day}",
                    now_seconds=draft.world_time_seconds,
                )
                draft.alchemy_states[actor_id] = prepared_alchemy.state
                for infused in prepared_alchemy.items:
                    draft.infused_alchemy_items[infused.instance_id] = infused
                    draft.item_instances[infused.instance_id] = ItemInstance(infused.instance_id, infused.formula_id or "", 1)
                    actor.stowed_items.append(infused.instance_id)
            draft.last_prepared_day[actor_id] = draft.preparation_day
            draft.rested_actor_ids.discard(actor_id)
            # On the Case permits an abandoned lead to be reopened after the
            # actor's actual daily preparation, and only then.
            actor.investigator_abandoned_cases.clear()
            familiar_replacements.extend(
                self._replace_dead_witch_familiars(draft, actor)
            )
        # Preparation ends only Light cast by the selected casters.  Other
        # casters' orbs remain concrete scene objects until their own prep.
        draft.light_orbs = [
            orb for orb in draft.light_orbs
            if orb.caster_actor_id not in normalized
        ]
        labels = ", ".join(draft.creatures[actor_id].label for actor_id in normalized)
        event = Event(
            "daily_preparation",
            None,
            None,
            f"Daily preparation completed for {labels} on preparation day {draft.preparation_day}.",
            details=(
                "Prepared choices remain fixed; available prepared, spontaneous, and Focus resources were restored.",
                "Selected casters' Light orbs ended; HP, wounds, equipment, and ammunition were preserved.",
                f"world time advanced to {draft.world_time_seconds} seconds",
            ),
        )
        self._state = draft
        self._dice = dice
        return ActionResult(
            ResultStatus.COMPLETED,
            (event, *familiar_replacements),
            event.text,
            self.inspect(),
        )

    def next_encounter(self, next_setup: EncounterSetup) -> ActionResult:
        """Begin a validated authored scene while carrying the same party.

        The transition is intentionally narrow: every PC in the next setup
        must be an existing PC with the same definition, while all opponents
        must have fresh actor IDs.  A Refocus-first route leaves no short-lived
        turn-bound effects to rebase; attached Light and absolute immunities
        are the only scene-owned records carried here.
        """
        state = self._state
        if state.in_progress:
            return self._result(ResultStatus.REJECTED, "The current encounter must finish before starting another.")
        if state.pending_choice is not None:
            return self._result(ResultStatus.REJECTED, "A pending choice must be resolved before starting another encounter.")
        if any(actor.spell_substitution is not None for actor in state.creatures.values()):
            return self._result(ResultStatus.REJECTED, "Spell Substitution must be explicitly interrupted or completed before starting another encounter.")
        try:
            _validate_setup(next_setup)
            next_state, dice = self._candidate_next_encounter(next_setup)
            # Round-trip the candidate through the strict save validator before
            # committing either the new scene or its cloned dice cursor.
            from .persistence import _state_from_data, _state_to_data

            next_state = _state_from_data(_state_to_data(next_state))
        except (DiceSourceError, TypeError, ValueError) as error:
            return self._result(ResultStatus.REJECTED, str(error))

        event = Event(
            "encounter_started",
            None,
            None,
            f"{next_setup.name} begins at world time {next_state.world_time_seconds} seconds.",
        )
        self._state = next_state
        self._dice = dice
        if next_state.pending_choice is not None:
            return ActionResult(
                ResultStatus.PAUSED,
                (event,),
                next_state.pending_choice.prompt,
                self.inspect(),
            )
        return ActionResult(ResultStatus.COMPLETED, (event,), event.text, self.inspect())

    def _candidate_next_encounter(
        self, next_setup: EncounterSetup
    ) -> tuple[EncounterState, DiceSource]:
        """Build and initialize the next scene without mutating this handle."""
        state = self._state
        old_ids = set(state.creatures)
        old_pc_ids = {
            actor_id
            for actor_id, actor in state.creatures.items()
            if actor.health_mode is HealthMode.PC
        }
        placements_by_id = {placement.actor_id: placement for placement in next_setup.placements}
        next_pc_ids = {
            placement.actor_id
            for placement in next_setup.placements
            if HealthMode(get_definition(placement.definition_id).health_mode) is HealthMode.PC
        }
        if next_pc_ids != old_pc_ids:
            raise ValueError("next encounter must keep exactly the same PC actor IDs")
        for placement in next_setup.placements:
            if placement.actor_id in old_pc_ids and (
                placement.definition_id != state.creatures[placement.actor_id].definition_id
            ):
                raise ValueError(
                    f"next encounter must keep the same PC definition for {placement.actor_id!r}"
                )
        next_opponent_ids = set(placements_by_id) - next_pc_ids
        if old_ids & next_opponent_ids:
            raise ValueError("next encounter opponents must use fresh actor IDs")
        if not any(is_combat_capable(state.creatures[actor_id]) for actor_id in old_pc_ids):
            raise ValueError("next encounter needs at least one conscious living carried PC")

        retained_ids = old_pc_ids
        for actor_id in old_pc_ids:
            actor = state.creatures[actor_id]
            if actor.dying > 0:
                raise ValueError("next encounter cannot skip an unresolved dying check")
            if actor.unconscious and not actor.dead:
                raise ValueError("next encounter cannot skip unsupported unconscious recovery")
            if actor.prone or actor.must_leave_occupied or actor.escape_lockout_until_start or actor.magic_shield_expires_at_start:
                raise ValueError("next encounter cannot carry turn-bound movement or Shield state")
            if actor.barbarian_state is not None and actor.barbarian_state.rage is not None:
                raise ValueError("next encounter cannot carry active Rage")

        if state.ground_items:
            raise ValueError("all party gear must be carried before leaving the encounter")
        carried_active_effects: list[ActiveSpellEffect] = []
        for effect in state.active_effects:
            if effect.kind not in _CARRYABLE_W2_ALCHEMY_EFFECT_KINDS:
                raise ValueError("next encounter cannot carry surviving turn-bound spell effects")
            if effect.source_actor_id not in retained_ids or effect.target_actor_id not in retained_ids:
                raise ValueError("next encounter cannot carry an item effect from a departed actor")
            if effect.expires_at_world_time is None:
                raise ValueError("next encounter cannot carry an item effect without an absolute expiry")
            if effect.expires_at_world_time > state.world_time_seconds:
                # Scene-local source-start occurrences reset to zero in the
                # new scene; preserve only the absolute remaining duration.
                carried_active_effects.append(replace(effect, expires_at_source_start=1))
        if state.active_item_effects or state.persistent_effects or state.giant_centipede_venom_afflictions:
            raise ValueError("next encounter cannot carry surviving turn-bound spell effects")
        if state.condition_effects or state.feint_off_guard_effects:
            raise ValueError("next encounter cannot carry surviving turn-bound conditions")
        if state.raised_shields or state.taking_cover:
            raise ValueError("next encounter cannot carry raised shields or Take Cover")

        fresh, fresh_items = self._fresh_creatures_for_setup(next_setup)
        # A carried PC's physical item identities must match the authored
        # definition in the next setup exactly. New opponents may have their
        # own freshly-instantiated equipment, while any old opponent item is
        # rejected as imported loot because it cannot be carried by a PC.
        fresh_pc_item_ids: set[str] = set()
        for actor_id in retained_ids:
            fresh_pc_item_ids.update(
                instance_id
                for instance_id in (
                    fresh[actor_id].held_items
                    + fresh[actor_id].worn_items
                    + fresh[actor_id].stowed_items
                )
                if instance_id in fresh_items
            )
        carried_infused_ids = {
            item_id for item_id in state.infused_alchemy_items
            if item_id not in state.consumed_infused_item_ids
        }
        expected_carried_ids = fresh_pc_item_ids | carried_infused_ids | state.consumed_infused_item_ids
        if set(state.item_instances) != expected_carried_ids:
            raise ValueError("next encounter cannot leave behind or import party equipment")
        locations = {instance_id: 0 for instance_id in state.item_instances}
        for actor_id in retained_ids:
            actor = state.creatures[actor_id]
            for instance_id in actor.held_items + actor.worn_items + actor.stowed_items:
                if instance_id in locations:
                    locations[instance_id] += 1
        if any(count != 1 and not (count == 0 and instance_id in state.consumed_infused_item_ids) for instance_id, count in locations.items()):
            raise ValueError("every party item must be carried exactly once")

        condition_immunities: list = []
        for immunity in state.condition_immunities:
            if immunity.target_actor_id not in retained_ids:
                # A record concerning only a departed target has no meaning
                # in the new scene and is safely discarded.
                continue
            if immunity.source_actor_id not in retained_ids:
                raise ValueError("next encounter cannot carry an immunity from a departed source")
            condition_immunities.append(deepcopy(immunity))

        guidance_deadlines = {}
        for actor_id, deadline in state.guidance_immunity_deadlines.items():
            if actor_id in retained_ids:
                guidance_deadlines[actor_id] = deadline
            elif actor_id not in old_ids:
                raise ValueError("next encounter has Guidance immunity for an unknown actor")

        sure_strike_deadlines = {}
        for actor_id, deadline in state.sure_strike_immunity_deadlines.items():
            if actor_id in retained_ids:
                sure_strike_deadlines[actor_id] = deadline
            elif actor_id not in old_ids:
                raise ValueError("next encounter has Sure Strike immunity for an unknown actor")

        light_orbs = deepcopy(state.light_orbs)
        light_ids: set[str] = set()
        for orb in light_orbs:
            if (
                orb.stable_id in light_ids
                or orb.caster_actor_id not in retained_ids
                or orb.point is not None
                or orb.attached_actor_id is None
                or orb.attached_actor_id not in retained_ids
            ):
                raise ValueError(
                    "next encounter carries only attached Light orbs on retained actors"
                )
            light_ids.add(orb.stable_id)

        fresh_creatures = fresh
        next_item_instances = deepcopy(state.item_instances)
        next_item_instances.update(
            {
                instance_id: deepcopy(instance)
                for instance_id, instance in fresh_items.items()
                if instance_id not in next_item_instances
            }
        )
        creatures: dict[str, CreatureState] = {}
        for placement in next_setup.placements:
            if placement.actor_id in retained_ids:
                actor = deepcopy(state.creatures[placement.actor_id])
                actor.label = placement.label
                actor.team = placement.team
                actor.position = placement.position
                actor.initiative = 0
                actor.actions_remaining = 0
                actor.strikes_this_turn = 0
                actor.diagonals_this_turn = 0
                actor.reaction_available = False
                actor.flourish_used_round = 0
                # Composition's once-per-turn bookkeeping belongs to the
                # departing encounter's turn counters.  It is neither an
                # effect nor a resource that survives into a fresh scene.
                actor.composition_cast_at_start = 0
                actor.composition_cast_turn_actor_id = None
                actor.composition_cast_turn_start = 0
                actor.must_leave_occupied = False
                actor.precision_used_round = 0
                actor.panache = False
                actor.panache_expires_at_end = None
                actor.escape_lockout_until_start = 0
                actor.investigator_stratagem = None
            else:
                actor = deepcopy(fresh_creatures[placement.actor_id])
            creatures[placement.actor_id] = actor

        next_state = EncounterState(
            setup_id=next_setup.setup_id,
            map_width=next_setup.width,
            map_height=next_setup.height,
            creatures=creatures,
            initiative_order=[],
            active_index=0,
            initiative_skills={
                placement.actor_id: placement.initiative_skill
                for placement in next_setup.placements
            },
            initiative_contexts={
                placement.actor_id: placement.initiative_context
                for placement in next_setup.placements
            },
            round_number=1,
            in_progress=True,
            winner_team=None,
            initiative_finalized=False,
            pending_choice=None,
            next_choice_id=state.next_choice_id,
            initiative_hero_decided=set(),
            quick_tempered_decided=set(),
            ground_items={},
            item_instances=next_item_instances,
            raised_shields={},
            initiative_tie_groups=[],
            initiative_tie_orders={},
            initiative_tie_group_index=0,
            initiative_reordered=set(),
            actor_start_counts={actor_id: 0 for actor_id in creatures},
            actor_end_counts={actor_id: 0 for actor_id in creatures},
            feint_off_guard_effects=[],
            active_effects=carried_active_effects,
            active_item_effects=[],
            guidance_immunities={
                actor_id: 601 for actor_id in guidance_deadlines
            },
            taking_cover=set(),
            condition_effects=[],
            condition_immunities=condition_immunities,
            world_time_seconds=state.world_time_seconds,
            encounter_start_seconds=state.world_time_seconds,
            ambient_light=next_setup.ambient_light,
            light_orbs=light_orbs,
            next_light_orb_id=state.next_light_orb_id,
            guidance_immunity_deadlines=guidance_deadlines,
            sure_strike_immunity_deadlines=sure_strike_deadlines,
            preparation_day=state.preparation_day,
            rested_actor_ids=set(state.rested_actor_ids),
            last_prepared_day=dict(state.last_prepared_day),
            alchemy_states=deepcopy(state.alchemy_states),
            infused_alchemy_items=deepcopy(state.infused_alchemy_items),
            consumed_infused_item_ids=set(state.consumed_infused_item_ids),
        )
        dice = self._dice.clone()
        for placement in next_setup.placements:
            definition = get_definition(placement.definition_id)
            if definition.initiative_exempt:
                continue
            modifier = self._initiative_modifier_for_state(
                next_state, next_state.creatures[placement.actor_id], definition,
                placement.initiative_skill,
                weather_perception_penalty=(0 if "storm_born" in definition.abilities else next_setup.weather_perception_circumstance_penalty),
            )
            next_state.creatures[placement.actor_id].initiative = dice.draw(20) + modifier
        self._continue_initiative_initialization(next_state)
        return next_state, dice

    def effective_speed_ft(self, actor_id: str) -> int:
        """Return the engine-computed land Speed for one current actor."""

        actor = self._state.creatures.get(actor_id)
        if actor is None:
            raise ValueError(f"unknown actor {actor_id!r}")
        return effective_speed_ft(actor, get_definition(actor.definition_id), self._conditions_for_actor(self._state, actor))

    def inspect(self) -> Inspection:
        state = self._state
        active_id = self._active_actor_id(state)
        actors: list[ActorView] = []
        display_order = state.initiative_order
        if not display_order:
            display_order = [placement.actor_id for placement in get_setup(state.setup_id).placements]
        else:
            # Familiars stay visible to terminal and inspection consumers even
            # though they have no initiative slot or independent actions.
            display_order = [
                *display_order,
                *(placement.actor_id for placement in get_setup(state.setup_id).placements
                  if placement.actor_id not in display_order),
            ]
        for actor_id in display_order:
            creature = state.creatures[actor_id]
            definition = get_definition(creature.definition_id)
            actors.append(
                ActorView(
                    actor_id=creature.actor_id,
                    label=creature.label,
                    team=creature.team,
                    position=creature.position,
                    hp=creature.hp,
                    max_hp=definition.hp,
                    defeated=creature.defeated,
                    initiative=creature.initiative,
                    actions_remaining=creature.actions_remaining,
                    strikes_this_turn=creature.strikes_this_turn,
                    diagonals_this_turn=creature.diagonals_this_turn,
                    initiative_skill=state.initiative_skills.get(creature.actor_id, "perception"),
                    initiative_context=state.initiative_contexts.get(creature.actor_id),
                    health_mode=creature.health_mode,
                    dying=creature.dying,
                    wounded=creature.wounded,
                    unconscious=creature.unconscious,
                    dead=creature.dead,
                    prone=creature.prone,
                    hero_points=creature.hero_points,
                    reaction_available=creature.reaction_available,
                    held_items=tuple(creature.held_items),
                    worn_items=tuple(creature.worn_items),
                    stowed_items=tuple(creature.stowed_items),
                    prepared_slots=tuple(
                        PreparedSlotView(slot.slot_id, slot.source, slot.spell_id,
                                         slot.rank, slot.cantrip, slot.spent)
                        for slot in creature.prepared_slots
                    ),
                    spontaneous_slots=tuple(
                        SpontaneousSlotView(
                            slot.slot_id, slot.source, slot.rank,
                            slot.capacity, slot.remaining,
                        )
                        for slot in creature.spontaneous_slots
                    ),
                    focus_points=creature.focus_points,
                    focus_capacity=creature.focus_capacity,
                    ammunition=tuple(sorted(creature.ammunition.items())),
                    effects=tuple(
                        EffectView(effect.kind, effect.source_actor_id,
                                   effect.target_actor_id, effect.value,
                                   effect.expires_at_source_start,
                                   effect.expires_at_world_time)
                        for effect in state.active_effects
                        if effect.target_actor_id == creature.actor_id
                    ),
                    # The absolute deadline is authoritative.  Keep the
                    # round-shaped field as a derived view for older callers.
                    guidance_immune_until_round=(
                        state.round_number + 600
                        if state.guidance_immunity_deadlines.get(creature.actor_id, 0)
                        > state.world_time_seconds
                        else None
                    ),
                    guidance_immune_until_seconds=state.guidance_immunity_deadlines.get(creature.actor_id),
                    sure_strike_immune_until_seconds=state.sure_strike_immunity_deadlines.get(creature.actor_id),
                    taking_cover=creature.actor_id in state.taking_cover,
                    ability_modifiers=definition.ability_modifiers,
                    skills=definition.skills,
                    saves=definition.saves,
                    proficiencies=definition.proficiencies,
                    senses=definition.senses,
                    vision=definition.vision,
                    sheet_notes=definition.sheet_notes,
                    abilities=definition.abilities,
                    feats=definition.feats,
                    size=definition.size,
                    level=definition.level,
                    ancestry=definition.ancestry,
                    heritage=definition.heritage,
                    background=definition.background,
                    class_name=definition.class_name,
                    deity=definition.deity,
                    languages=definition.languages,
                    class_dc=definition.class_dc,
                    ac=self._effective_ac(creature, state=state),
                    perception=definition.perception - (4 if creature.unconscious else 0),
                    speed_ft=effective_speed_ft(creature, definition, self._conditions_for_actor(state, creature)),
                    panache=creature.panache,
                    panache_expires_at_end=creature.panache_expires_at_end,
                    finisher_used_this_turn=creature.finisher_used_this_turn,
                    temporary_hp=creature.temporary_hp,
                    temporary_hp_source_id=creature.temporary_hp_source_id,
                    temporary_hp_expires_at_seconds=creature.temporary_hp_expires_at_seconds,
                    barbarian_state=creature.barbarian_state,
                    condition_effects=tuple(
                        effect for effect in state.condition_effects
                        if effect.target_actor_id == creature.actor_id
                    ),
                    hunted_prey=creature.hunted_prey,
                    shields=self._shield_views(state, creature),
                )
            )
        return Inspection(
            in_progress=state.in_progress,
            round_number=state.round_number,
            turn_actor_id=active_id,
            actors=tuple(actors),
            map_width=state.map_width,
            map_height=state.map_height,
            winner_team=state.winner_team,
            ambient_light=state.ambient_light,
            choice=self._choice_view(state.pending_choice),
                    ground_items=tuple(
                (position, tuple(items))
                for position, items in sorted((state.ground_items or {}).items())
                if items
            ),
            light_orbs=tuple(state.light_orbs),
            world_time_seconds=state.world_time_seconds,
            encounter_start_seconds=state.encounter_start_seconds,
            preparation_day=state.preparation_day,
            rested_actor_ids=tuple(sorted(state.rested_actor_ids)),
            last_prepared_day=tuple(sorted(state.last_prepared_day.items())),
        )

    def illumination_at(self, position: Position) -> str:
        """Return the supported illumination at one cell in this scene.

        Ambient light supplies the default; a point or attached Light orb can
        raise a cell to bright within its 20-foot radius. Keeping this query
        on ``Encounter`` gives targeting and callers one shared geometry seam
        without making them infer light from descriptive sense text.
        """
        if not isinstance(position, Position) or not in_bounds(
            position, self._state.map_width, self._state.map_height
        ):
            raise ValueError("illumination queries require a position inside the supported map")
        illumination = self._state.ambient_light
        if illumination == "bright":
            return illumination
        for orb in self._state.light_orbs:
            orb_position = self._light_orb_position(self._state, orb)
            if orb_position is not None and grid_distance_feet(orb_position, position) <= 20:
                return "bright"
        return illumination

    @staticmethod
    def _light_orb_position(state: EncounterState, orb: LightOrb) -> Position | None:
        """Resolve an orb's current point, deriving attached light from its carrier."""
        if orb.attached_actor_id is not None:
            carrier = state.creatures.get(orb.attached_actor_id)
            return carrier.position if carrier is not None else None
        return orb.point

    def target_illumination(self, observer_id: str, target_id: str) -> str:
        """Return the current illumination of ``target_id`` for an observer.

        Illumination itself is location-relative; this method intentionally
        accepts both actors so the concealment decision has one public,
        observer-relative query point when vision and orb effects expand.
        """
        observer = self._state.creatures.get(observer_id)
        target = self._state.creatures.get(target_id)
        if observer is None or target is None:
            raise ValueError("illumination queries require existing observer and target actors")
        return self.illumination_at(target.position)

    def target_is_concealed(self, observer_id: str, target_id: str) -> bool:
        """Return whether dim light or authored weather conceals a target."""
        observer = self._state.creatures.get(observer_id)
        if observer is None or target_id not in self._state.creatures:
            raise ValueError("concealment queries require existing observer and target actors")
        return get_setup(self._state.setup_id).weather_concealment or (
            self.target_illumination(observer_id, target_id) == "dim"
            and get_definition(observer.definition_id).vision == "ordinary"
        )

    def _target_weather_concealed(self, observer_id: str, target_id: str) -> bool:
        if observer_id not in self._state.creatures or target_id not in self._state.creatures:
            raise ValueError("concealment queries require existing observer and target actors")
        return get_setup(self._state.setup_id).weather_concealment

    # A descriptive alias keeps callers from coupling to the condition's
    # wording while retaining the same shared observer-relative result.
    is_target_concealed = target_is_concealed

    def options(self) -> ActionOptions:
        from .alchemy_content import FORMULAS_BY_ID

        state = self._state
        active_id = self._active_actor_id(state)
        if active_id is None:
            return ActionOptions(
                actor_id=None, actions_remaining=0, can_stride=False, can_step=False,
                can_strike=False, can_end_turn=False, strike_targets=(),
                step_destinations=(),
            )
        actor = state.creatures[active_id]
        definition = get_definition(actor.definition_id)
        self._expire_person_of_interest_grants(state)
        actions = actor.actions_remaining
        can_act = actions > 0 and not actor.unconscious and not actor.dead
        can_move = can_act and not actor.prone
        step_destinations = self._step_destinations(actor, state) if can_move else ()
        usable = tuple(attack for attack in definition.attacks if self._attack_usable(state, actor, attack)) if can_act else ()
        stored_stratagem = actor.investigator_stratagem
        active_stratagem = (
            stored_stratagem
            if stored_stratagem is not None
            and stored_stratagem.mode == ATTACK_STRATAGEM
            and not stored_stratagem.consumed
            and stored_stratagem.round_number == state.round_number
            and stored_stratagem.turn_start == state.actor_start_counts.get(actor.actor_id, 0)
            else None
        )
        skill_stratagem_target_id = (
            stored_stratagem.target_id
            if stored_stratagem is not None
            and stored_stratagem.mode == "skill"
            and stored_stratagem.round_number == state.round_number
            and stored_stratagem.turn_start == state.actor_start_counts.get(actor.actor_id, 0)
            else None
        )

        def strike_targets_for_menu(attack):
            return tuple(
                target_id for target_id in self._strike_targets(actor, state, attack)
                if target_id != skill_stratagem_target_id
            )

        strikes = tuple(
            StrikeOption(
                attack_id=attack.attack_id,
                name=attack.name,
                targets=strike_targets_for_menu(attack),
                damage_types=self._attack_damage_types(attack),
                default_damage_type=attack.damage_type,
                default_nonlethal="nonlethal" in attack.traits,
                intelligence_substitution_available=bool(
                    active_stratagem is not None
                    and intelligence_substitution_eligible(attack)
                ),
            )
            for attack in usable
        )
        targets = tuple(dict.fromkeys(target for strike in strikes for target in strike.targets))
        if actor.must_leave_occupied:
            strikes = ()
            targets = ()
        can_stride = can_move and self._has_open_neighbor(actor, state)
        can_step = bool(step_destinations)
        can_strike = (
            bool(targets)
            and can_act
            and not actor.must_leave_occupied
            and any(
                self._action_permitted(state, actor, "strike", attack.traits)
                for attack in usable
                if strike_targets_for_menu(attack)
            )
        )
        existing_stratagem = actor.investigator_stratagem
        free_devise_target_ids = self._free_devise_target_ids(state, actor)
        devise_available = (
            (can_act or bool(free_devise_target_ids))
            and not actor.must_leave_occupied
            and "investigator_devise_stratagem" in definition.abilities
            and any(
                target.actor_id != actor.actor_id
                and not target.defeated
                for target in state.creatures.values()
            )
            and not (
                existing_stratagem is not None
                and existing_stratagem.round_number == state.round_number
            )
            and self._action_permitted(
                state,
                actor,
                "devise_stratagem",
                frozenset({"concentrate", "investigator"}),
            )
        )
        can_vicious = (
            can_act and not actor.must_leave_occupied
            and "vicious_swing" in definition.abilities
            and actor.flourish_used_round != state.round_number
            and actions >= 2
            and any("melee" in attack.traits and self._strike_targets(actor, state, attack) for attack in usable)
            and any(
                self._action_permitted(state, actor, "vicious_swing", attack.traits)
                for attack in usable
                if "melee" in attack.traits and self._strike_targets(actor, state, attack)
            )
        )
        can_intimidating_strike = (
            can_act and actions >= 2 and not actor.must_leave_occupied
            and "intimidating_strike" in definition.abilities
            and any(
                "melee" in attack.traits and self._strike_targets(actor, state, attack)
                and self._action_permitted(
                    state, actor, "intimidating_strike",
                    frozenset({"attack", "emotion", "fear", "mental"}),
                )
                for attack in usable
            )
        )
        free_hand_targets = any(
            grid_distance_feet(actor.position, state.creatures[target_id].position) <= 5
            for attack in usable if "melee" in attack.traits
            for target_id in self._strike_targets(actor, state, attack)
        )
        can_snagging_strike = (
            can_act and actions >= 1 and not actor.must_leave_occupied
            and "snagging_strike" in definition.abilities
            and self._free_hands(state, definition, actor) >= 1
            and free_hand_targets
            and self._action_permitted(state, actor, "snagging_strike", frozenset({"attack"}))
        )
        can_combat_grab = (
            can_act and actions >= 1 and not actor.must_leave_occupied
            and "combat_grab" in definition.abilities and actor.strikes_this_turn >= 1
            and self._free_hands(state, definition, actor) >= 1
            and free_hand_targets
            and self._action_permitted(state, actor, "combat_grab", frozenset({"attack", "press"}))
        )
        can_brutish_shove = (
            can_act and actions >= 1 and not actor.must_leave_occupied
            and "brutish_shove" in definition.abilities and actor.strikes_this_turn >= 1
            and any(
                "melee" in attack.traits and attack.hands_required >= 2
                and self._strike_targets(actor, state, attack)
                for attack in usable
            )
            and self._action_permitted(state, actor, "brutish_shove", frozenset({"attack", "press"}))
        )
        can_sudden_charge = (
            can_act and actions >= 2 and not actor.must_leave_occupied
            and "sudden_charge" in definition.abilities
            and actor.flourish_used_round != state.round_number
            and self._action_permitted(state, actor, "sudden_charge", frozenset({"flourish", "move"}))
        )
        melee_pair_attacks = tuple(
            attack for attack in usable
            if "melee" in attack.traits and self._strike_targets(actor, state, attack)
        )
        can_exacting_strike = (
            can_act and actor.strikes_this_turn >= 1 and not actor.must_leave_occupied and "exacting_strike" in definition.abilities
            and bool(melee_pair_attacks)
            and self._action_permitted(state, actor, "exacting_strike", frozenset({"attack"}))
        )
        can_double_slice = (
            can_act and actions >= 2 and not actor.must_leave_occupied
            and "double_slice" in definition.abilities
            and sum(attack.hands_required == 1 for attack in melee_pair_attacks) >= 2
            and self._action_permitted(state, actor, "double_slice", frozenset({"attack"}))
        )
        hunted_prey = actor.hunted_prey
        can_twin_takedown = (
            can_act and not actor.must_leave_occupied and "twin_takedown" in definition.abilities
            and hunted_prey is not None and hunted_prey.target_actor_id in state.creatures
            and sum(attack.attack_id != "shortbow" for attack in melee_pair_attacks) >= 2
            and hunted_prey.target_actor_id in {
                target_id for attack in melee_pair_attacks
                for target_id in self._strike_targets(actor, state, attack)
            }
            and self._action_permitted(state, actor, "twin_takedown", frozenset({"flourish"}))
        )
        can_twin_feint = (
            can_act and actions >= 2 and not actor.must_leave_occupied and "twin_feint" in definition.abilities
            and sum(bool({"agile", "finesse"} & attack.traits) for attack in melee_pair_attacks) >= 2
            and self._action_permitted(state, actor, "twin_feint", frozenset({"attack"}))
        )
        from .monk import is_flurry_strike

        can_flurry = (
            can_act and not actor.must_leave_occupied
            and "flurry_of_blows" in definition.abilities
            and actor.flourish_used_round != state.round_number
            and any(
                is_flurry_strike(definition.abilities, attack)
                and self._strike_targets(actor, state, attack)
                and self._action_permitted(state, actor, "flurry_of_blows", frozenset({"flourish"}))
                for attack in usable
            )
        )
        can_hunt_prey = (
            can_act and actions >= 1 and not actor.must_leave_occupied
            and "hunt_prey" in definition.abilities
            and any(
                target.actor_id != actor.actor_id and not target.defeated
                for target in state.creatures.values()
            )
            and self._action_permitted(
                state, actor, "hunt_prey", frozenset({"concentrate"})
            )
        )
        hunted_prey = actor.hunted_prey
        can_hunted_shot = (
            can_act and actions >= 1 and not actor.must_leave_occupied
            and "hunted_shot" in definition.abilities
            and actor.flourish_used_round != state.round_number
            and hunted_prey is not None
            and hunted_prey.target_actor_id in state.creatures
            and not state.creatures[hunted_prey.target_actor_id].defeated
            and any(
                "ranged" in attack.traits and attack.reload == 0
                and hunted_prey.target_actor_id in strike_targets_for_menu(attack)
                for attack in usable
            )
            and self._action_permitted(
                state, actor, "hunted_shot", frozenset({"flourish"})
            )
        )
        can_hunters_aim = (
            can_act
            and actions >= 2
            and not actor.must_leave_occupied
            and "hunters_aim" in definition.abilities
            and hunted_prey is not None
            and hunted_prey.target_actor_id in state.creatures
            and not state.creatures[hunted_prey.target_actor_id].defeated
            and any(
                "ranged" in attack.traits
                and hunted_prey.target_actor_id in strike_targets_for_menu(attack)
                for attack in usable
            )
            and self._action_permitted(
                state, actor, "hunter_aim", frozenset({"concentrate"})
            )
        )
        can_reach_spell = (
            can_act
            and actions >= 1
            and not actor.must_leave_occupied
            and not has_pending_spellshape(actor)
            and "reach_spell" in definition.abilities
            and "Reach Spell" in definition.feats
            and self._action_permitted(
                state, actor, "reach_spell", frozenset({"concentrate", "spellshape"})
            )
        )
        can_widen_spell = (
            can_act
            and actions >= 1
            and not actor.must_leave_occupied
            and not has_pending_spellshape(actor)
            and "widen_spell" in definition.abilities
            and "Widen Spell" in definition.feats
            and self._action_permitted(
                state, actor, "widen_spell", frozenset({"manipulate", "spellshape"})
            )
        )
        can_energy_ablation = (
            can_act
            and actions >= 1
            and not actor.must_leave_occupied
            and not has_pending_spellshape(actor)
            and "energy_ablation" in definition.abilities
            and "Energy Ablation" in definition.feats
            and self._action_permitted(state, actor, "energy_ablation", frozenset({"spellshape"}))
        )
        can_cackle = (
            "cackle" in definition.abilities
            and "Cackle" in definition.feats
            and actor.focus_points > 0
            and actor.witch_cackle_used_start != state.actor_start_counts.get(actor.actor_id, 0)
            and any(
                effect.kind == "stoke_the_heart" and effect.source_actor_id == actor.actor_id
                for effect in state.active_effects
            )
            and self._action_permitted(state, actor, "cackle", frozenset({"auditory", "concentrate"}))
        )
        from .martial_defense import crane_stance_is_active, dueling_parry_requirements_met
        from .martial_defense import point_blank_stance_is_active

        can_dueling_parry = (
            can_act and actions >= 1 and not actor.must_leave_occupied
            and "dueling_parry" in definition.abilities
            and dueling_parry_requirements_met(state.item_instances, actor, definition)
            and self._action_permitted(state, actor, "dueling_parry", frozenset())
        )
        can_crane_stance = (
            can_act and actions >= 1 and not actor.must_leave_occupied
            and "crane_stance" in definition.abilities
            and definition.armor_category in {None, "unarmored"}
            and not actor.worn_items
            and not crane_stance_is_active(state, actor.actor_id)
            and state.martial_stance_used_rounds.get(actor.actor_id) != state.round_number
            and self._action_permitted(state, actor, "crane_stance", frozenset({"stance"}))
        )
        can_dismiss_crane_stance = crane_stance_is_active(state, actor.actor_id)
        can_point_blank_stance = (
            can_act and actions >= 1 and not actor.must_leave_occupied
            and "point_blank_stance" in definition.abilities
            and not point_blank_stance_is_active(state, actor.actor_id)
            and state.martial_stances.get(actor.actor_id) is None
            and state.martial_stance_used_rounds.get(actor.actor_id) != state.round_number
            and any("ranged" in attack.traits and attack.item_id in actor.held_items for attack in definition.attacks)
            and self._action_permitted(state, actor, "point_blank_stance", frozenset({"stance"}))
        )
        can_arcane_bond = (
            can_act
            and "arcane_bond" in definition.abilities
            and actor.arcane_bond_used_day != state.preparation_day
            and bool(actor.arcane_bond_eligible_slots)
        )
        from .swashbuckler import is_swashbuckler, precise_strike_damage_term

        can_finisher = (
            can_act
            and not actor.must_leave_occupied
            and actor.panache
            and is_swashbuckler(definition)
            and any(
                precise_strike_damage_term(
                    definition,
                    attack,
                    finisher=True,
                    distance_ft=grid_distance_feet(actor.position, state.creatures[target_id].position),
                ) is not None
                for attack in usable
                for target_id in self._strike_targets(actor, state, attack)
            )
            and self._action_permitted(state, actor, "confident_finisher", frozenset({"attack", "finisher"}))
        )
        interact_options = self._interact_options(actor, state) if can_act and not actor.must_leave_occupied else ()
        spells = self._spell_options(actor, state) if can_act and not actor.must_leave_occupied else ()
        activate_alchemy_available = any(
            item_id in state.infused_alchemy_items
            and state.infused_alchemy_items[item_id].formula_id in FORMULAS_BY_ID
            and FORMULAS_BY_ID[state.infused_alchemy_items[item_id].formula_id].category != "bomb"
            and FORMULAS_BY_ID[state.infused_alchemy_items[item_id].formula_id].activation_actions <= actions
            for item_id in actor.held_items
        )
        can_stand = can_act and actor.prone and not self._shares_space_with_living_actor(actor, state)
        can_crawl = can_act and actor.prone and self._has_open_neighbor(actor, state)
        can_flee = can_act and self._active_fleeing_effect(state, actor) is not None
        can_release = bool(actor.held_items) and not actor.must_leave_occupied
        justice_lay_targets = tuple(
            target.actor_id
            for target in state.creatures.values()
            if target.team == actor.team
            and not target.dead
            and self._is_living_target(target)
            and grid_distance_feet(actor.position, target.position) <= 5
        )
        justice_lay_available = (
            can_act
            and not actor.must_leave_occupied
            and "lay_on_hands" in definition.abilities
            and actor.focus_points > 0
            and bool(justice_lay_targets)
            and self._action_permitted(state, actor, "lay_on_hands", frozenset({"manipulate", "concentrate"}))
        )
        from .investigator import (
            battle_medicine_target_ids,
            person_of_interest_target_ids,
            recall_knowledge_target_ids,
        )

        battle_medicine_targets = (
            battle_medicine_target_ids(self, state, actor, definition)
            if can_act and not actor.must_leave_occupied
            else ()
        )
        battle_medicine_available = (
            bool(battle_medicine_targets)
            and self._action_permitted(state, actor, "battle_medicine", frozenset({"healing", "manipulate", "skill"}))
        )
        person_of_interest_targets = (
            person_of_interest_target_ids(self, state, actor, definition)
            if (
                can_act
                and not actor.must_leave_occupied
                and actor.investigator_person_of_interest_cooldown_until
                <= state.world_time_seconds
            )
            else ()
        )
        person_of_interest_available = (
            bool(person_of_interest_targets)
            and self._action_permitted(state, actor, "person_of_interest", frozenset())
        )
        recall_knowledge_targets = (
            recall_knowledge_target_ids(self, state, actor, definition)
            if can_act and not actor.must_leave_occupied
            else ()
        )
        recall_knowledge_available = (
            bool(recall_knowledge_targets)
            and self._action_permitted(
                state,
                actor,
                "recall_knowledge",
                frozenset({"concentrate", "secret", "skill"}),
            )
        )
        known_weaknesses_available = (
            devise_available
            and bool(recall_knowledge_targets)
            and self._action_permitted(
                state,
                actor,
                "known_weaknesses",
                frozenset({"concentrate", "investigator", "secret", "skill"}),
            )
        )
        justice_aura_suppressed = (
            "justice_champion" in definition.abilities
            and actor.actor_id not in state.justice_aura_active
        )
        rage_available = (
            can_act and actions >= 1 and not actor.must_leave_occupied
            and actor.barbarian_state is not None
            and actor.barbarian_state.rage is None
            and not any(
                effect.target_actor_id == actor.actor_id and effect.kind == "fatigued"
                for effect in state.condition_effects
            )
            and self._action_permitted(state, actor, "rage", frozenset({"concentrate"}))
        )
        skill_action_ids = ()
        assurance_action_ids = ()
        if can_act and actions >= 1 and not actor.must_leave_occupied:
            from .skill_actions import assurance_athletics_available
            from .skill_content import DEMORALIZE, ESCAPE, FEINT, GRAPPLE, QUICK_JUMP, TRIP, TUMBLE_THROUGH

            skill_actions = (TRIP, GRAPPLE, ESCAPE, DEMORALIZE, FEINT, TUMBLE_THROUGH)
            if "Quick Jump" in definition.feats and any(
                skill == "athletics" and rank in {"trained", "expert", "master", "legendary"}
                for skill, rank, _modifier in definition.skills
            ):
                skill_actions = (*skill_actions, QUICK_JUMP)
            skill_action_ids = tuple(
                action.action_id
                for action in skill_actions
                if self._action_permitted(state, actor, action.action_id, action.traits)
                and (
                    action.action_id != FEINT.action_id
                    or any(
                        skill == "deception" and rank is not None
                        for skill, rank, _modifier in definition.skills
                    )
                )
            )
            if assurance_athletics_available(definition):
                assurance_action_ids = tuple(
                    f"{action_id}_assurance"
                    for action_id in ("trip", "grapple", "escape")
                    if action_id in skill_action_ids
                )
        if can_flee:
            # The condition gate is reflected in the public action projection
            # as well as enforced by _resolve, while reactions remain exposed
            # through their persisted Choose records.
            can_stride = False
            can_step = False
            can_strike = False
            can_vicious = False
            can_intimidating_strike = False
            can_snagging_strike = False
            can_combat_grab = False
            can_brutish_shove = False
            can_sudden_charge = False
            can_exacting_strike = False
            can_double_slice = False
            can_twin_takedown = False
            can_twin_feint = False
            can_flurry = False
            can_hunt_prey = False
            can_hunted_shot = False
            can_hunters_aim = False
            can_reach_spell = False
            can_widen_spell = False
            can_energy_ablation = False
            can_cackle = False
            can_dueling_parry = False
            can_crane_stance = False
            can_dismiss_crane_stance = False
            can_point_blank_stance = False
            can_stand = False
            can_crawl = False
            can_release = False
            interact_options = ()
            spells = ()
            rage_available = False
            skill_action_ids = ()
            assurance_action_ids = ()
            battle_medicine_targets = ()
            battle_medicine_available = False
            person_of_interest_targets = ()
            person_of_interest_available = False
        available = tuple(
            action
            for action, enabled in (
                ("stride", can_stride),
                ("step", can_step),
                ("strike", can_strike),
                ("quick_alchemy", can_act and actor.actor_id in state.alchemy_states and state.alchemy_states[actor.actor_id].stored_vials > 0),
                ("activate_alchemy", can_act and activate_alchemy_available),
                ("quick_bomber", can_act and "quick_bomber" in definition.abilities and any(
                    state.item_instances.get(item) is not None
                    and self._admitted_bomber_bomb_facts(
                        state.item_instances[item].definition_id,
                        character_level=state.alchemy_states[actor.actor_id].character_level,
                    ) is not None
                    for item in actor.held_items + actor.stowed_items
                )),
                ("confident_finisher", can_finisher),
                ("devise_stratagem", devise_available),
                ("known_weaknesses", known_weaknesses_available),
                ("vicious_swing", can_vicious),
                ("intimidating_strike", can_intimidating_strike),
                ("snagging_strike", can_snagging_strike),
                ("combat_grab", can_combat_grab),
                ("brutish_shove", can_brutish_shove),
                ("sudden_charge", can_sudden_charge),
                ("exacting_strike", can_exacting_strike),
                ("double_slice", can_double_slice),
                ("twin_takedown", can_twin_takedown),
                ("twin_feint", can_twin_feint),
                ("dueling_parry", can_dueling_parry),
                ("crane_stance", can_crane_stance),
                ("dismiss_crane_stance", can_dismiss_crane_stance),
                ("point_blank_stance", can_point_blank_stance),
                ("flurry_of_blows", can_flurry),
                ("hunt_prey", can_hunt_prey),
                ("hunted_shot", can_hunted_shot),
                ("hunter_aim", can_hunters_aim),
                ("reach_spell", can_reach_spell),
                ("widen_spell", can_widen_spell),
                ("energy_ablation", can_energy_ablation),
                ("cackle", can_cackle),
                ("interact", bool(interact_options)),
                ("release", can_release),
                ("stand", can_stand),
                ("crawl", can_crawl),
                ("flee", can_flee),
                ("take_cover", can_act and not can_flee and actor.prone and actor.actor_id not in state.taking_cover),
                ("raise_shield", can_act and not can_flee and self._held_shield_instance(state, actor) is not None),
                ("dismiss_cover", actor.actor_id in state.taking_cover and not can_flee),
                ("lingering_composition", can_act and actor.focus_points > 0 and "lingering_composition" in definition.abilities),
                ("drain_bonded_item", can_arcane_bond),
                ("cast", any(not spell.unavailable_reason and (spell.cantrip or spell.slots) for spell in spells)),
                ("sustain_light", can_act and self._light_control_available(state, actor, "sustain")),
                ("dismiss_light", can_act and self._light_control_available(state, actor, "dismiss")),
                ("dismiss_life_link", self._active_life_link(state, actor) is not None),
                ("rage", rage_available),
                ("lay_on_hands", justice_lay_available),
                ("nudge_the_scales", can_act and "nudge_the_scales" in definition.abilities and actor.oracle_cursebound < 2),
                ("battle_medicine", battle_medicine_available),
                ("person_of_interest", person_of_interest_available),
                ("recall_knowledge", recall_knowledge_available),
                ("suppress_aura", can_act and "justice_champion" in definition.abilities and not justice_aura_suppressed),
                ("resume_aura", can_act and "justice_champion" in definition.abilities and justice_aura_suppressed),
                ("end_turn", not actor.must_leave_occupied and not can_flee),
            )
            if enabled
        ) + skill_action_ids + assurance_action_ids
        return ActionOptions(
            actor_id=active_id,
            actions_remaining=actions,
            can_stride=can_stride,
            can_step=can_step,
            can_strike=can_strike,
            can_end_turn=not actor.must_leave_occupied and not can_flee,
            strike_targets=targets,
            step_destinations=step_destinations,
            available_actions=available,
            capabilities=tuple(sorted(definition.abilities)),
            strikes=strikes,
            interact_options=interact_options,
            spells=spells,
            investigator_stratagem_target_id=(
                active_stratagem.target_id if active_stratagem is not None else None
            ),
            battle_medicine_targets=battle_medicine_targets,
            person_of_interest_targets=person_of_interest_targets,
            recall_knowledge_targets=recall_knowledge_targets,
        )

    def _spell_options(self, actor, state) -> tuple[SpellOption, ...]:
        """Report only engine-computed targets and currently available slots."""
        definition = get_definition(actor.definition_id)
        prepared_ids = tuple(dict.fromkeys(slot.spell_id for slot in actor.prepared_slots))
        spontaneous_ids = tuple(
            spell.spell_id for spell in definition.spontaneous_spells
        )
        focus_ids = tuple(spell.spell_id for spell in definition.focus_spells)
        spell_ids = tuple(dict.fromkeys((*prepared_ids, *spontaneous_ids, *focus_ids)))
        result: list[SpellOption] = []
        for spell_id in spell_ids:
            spell = SPELLS.get(spell_id)
            if spell is None:
                continue
            if spell_id in {"lingering_composition", "counter_performance", "cackle"}:
                # This focus spellshape is a dedicated free action, not a
                # creature-targeted Cast entry. Counter Performance is a
                # saved reaction offered only by its eligible trigger.
                continue
            slots = tuple(
                (slot.slot_id, slot.source)
                for slot in actor.prepared_slots
                if slot.spell_id == spell_id and not slot.cantrip and not slot.spent
            )
            if actor.arcane_bond_recast_until_start == state.actor_start_counts.get(actor.actor_id, 0):
                slots += tuple(
                    (slot.slot_id, f"{slot.source}; Arcane Bond")
                    for slot in actor.prepared_slots
                    if (
                        slot.spell_id == spell_id
                        and slot.spent
                        and slot.slot_id in actor.arcane_bond_eligible_slots
                    )
                )
            slots += tuple(
                (slot.slot_id, slot.source)
                for slot in actor.spontaneous_slots
                if slot.remaining > 0
                and any(
                    access.spell_id == spell_id
                    and not access.cantrip
                    and access.rank == slot.rank
                    for access in definition.spontaneous_spells
                )
            )
            if spell_id in focus_ids and actor.focus_points > 0:
                slots += (("actor_focus_pool", definition.focus_source),)
            cantrip = (
                any(slot.spell_id == spell_id and slot.cantrip for slot in actor.prepared_slots)
                or any(
                    access.spell_id == spell_id and access.cantrip
                    for access in definition.spontaneous_spells
                )
            )
            target_options: list[SpellTargetOption] = []
            for actions in spell.action_costs:
                if actions > actor.actions_remaining:
                    continue
                if spell_id == "light":
                    # Light's point and optional attachment are supplied by
                    # the direct Cast command. The terminal has no point
                    # selector yet, so keep this metadata intentionally
                    # unselectable rather than advertising a fake creature
                    # target list.
                    continue
                if spell_id == "runic_weapon":
                    # Runic Weapon targets a physical item selected by the
                    # terminal, so the public creature target list is empty.
                    target_options.append(SpellTargetOption(
                        actions, (),
                        traits=tuple(sorted(spell_traits(spell_id, actions))),
                    ))
                    continue
                if spell_id == "sigil":
                    # The terminal presents both creature and physical-item
                    # targets.  The latter has no actor id to advertise here.
                    candidates = tuple(
                        candidate.actor_id for candidate in state.creatures.values()
                        if self._spell_target_valid(spell_id, actor, candidate, state)
                        and grid_distance_feet(actor.position, candidate.position)
                        <= self._effective_reach_spell_range(
                            spell_id, actions, reach_ready=actor.reach_spell_pending,
                        )
                    )
                    target_options.append(SpellTargetOption(
                        actions, candidates,
                        traits=tuple(sorted(spell_traits(spell_id, actions))),
                    ))
                    continue
                if spell_id in {"angelic_halo", "courageous_anthem", "shield", "detect_magic", "weapon_surge"}:
                    target_options.append(SpellTargetOption(
                        actions, (),
                        traits=tuple(sorted(spell_traits(spell_id, actions))),
                    ))
                    continue
                if spell_id == "gale_blast":
                    target_options.append(SpellTargetOption(
                        actions, (), include_self_available=self._is_living_target(actor),
                        traits=tuple(sorted(spell_traits(spell_id, actions))),
                    ))
                    continue
                if spell_id == "breathe_fire":
                    target_options.append(SpellTargetOption(
                        actions, (), traits=tuple(sorted(spell_traits(spell_id, actions))),
                    ))
                    continue
                if spell_id == "sure_strike":
                    target_options.append(SpellTargetOption(
                        actions, (),
                        traits=tuple(sorted(spell_traits(spell_id, actions))),
                    ))
                    continue
                if spell_id == "heal" and actions == 3:
                    recipients = tuple(
                        candidate.actor_id
                        for candidate in state.creatures.values()
                        if candidate.actor_id != actor.actor_id
                        and self._is_living_target(candidate)
                        and in_heal_emanation(actor.position, candidate.position)
                    )
                    target_options.append(SpellTargetOption(
                        actions, recipients,
                        include_self_available=self._is_living_target(actor),
                        traits=tuple(sorted(spell_traits(spell_id, actions))),
                    ))
                    continue
                # The terminal projection shares the same normalized range
                # calculation as cast initiation: Reach's transient marker
                # changes the next eligible touch/ranged mode, never an
                # emanation or global spell definition.
                range_ft = self._effective_reach_spell_range(
                    spell_id, actions, reach_ready=actor.reach_spell_pending,
                )
                candidates = []
                for candidate in state.creatures.values():
                    if not self._spell_target_valid(spell_id, actor, candidate, state):
                        continue
                    distance = grid_distance_feet(actor.position, candidate.position)
                    if range_ft is not None and distance > range_ft:
                        continue
                    candidates.append(candidate.actor_id)
                target_options.append(SpellTargetOption(
                    actions, tuple(candidates),
                    traits=tuple(sorted(spell_traits(spell_id, actions))),
                ))
            result.append(SpellOption(
                spell_id=spell_id,
                name=spell.name,
                traits=tuple(sorted(spell.traits)),
                action_costs=spell.action_costs,
                slots=slots,
                target_options=tuple(target_options),
                unavailable_reason=spell.unavailable_reason,
                cantrip=cantrip,
            ))
        return tuple(result)

    @staticmethod
    def _is_living_target(creature) -> bool:
        return not creature.dead and (
            creature.health_mode is HealthMode.PC
            or creature.hp > 0
            or creature.unconscious
        )

    @staticmethod
    def _in_justice_aura(state: EncounterState, champion: CreatureState, target: CreatureState) -> bool:
        """Whether a living ally is inside an active 15-foot Champion aura."""
        return (
            champion.actor_id in state.justice_aura_active
            and not champion.unconscious
            and not champion.dead
            and target.team == champion.team
            and not target.dead
            and grid_distance_feet(champion.position, target.position) <= 15
        )

    def _spell_target_valid(self, spell_id, caster, target, state) -> bool:
        # This combat slice has no self-damage health resolution. Keep its
        # destructive targeted spells out of the public target list rather
        # than advertising a selection the ordinary damage path cannot apply.
        if spell_id == "harm":
            return (
                target.actor_id != caster.actor_id
                and self._is_living_target(target)
                and "void_healing" not in get_definition(target.definition_id).abilities
            )
        if spell_id in {"daze", "force_bolt", "force_barrage", "electric_arc", "tempest_surge", "telekinetic_projectile", "frostbite", "enfeeble", "ignition", "gouging_claw", "caustic_blast", "tangle_vine"}:
            return target.actor_id != caster.actor_id and not target.dead and not target.defeated
        if spell_id == "vitality_lash":
            return target.actor_id != caster.actor_id and not target.dead and (
                target.oracle_life_mode == "death" or "void_healing" in get_definition(target.definition_id).abilities
            )
        if spell_id == "life_link":
            return target.actor_id != caster.actor_id and self._is_living_target(target)
        if spell_id == "forbidding_ward":
            return False  # Ward validates its ally/enemy pair in the casting procedure.
        if spell_id == "stoke_the_heart":
            return not target.dead and not target.defeated
        if spell_id == "runic_body":
            return self._is_living_target(target)
        if spell_id == "stabilize":
            return target.health_mode is HealthMode.PC and target.dying > 0 and not target.dead
        if spell_id == "guidance":
            return (
                self._is_living_target(target)
                and state.guidance_immunity_deadlines.get(target.actor_id, 0)
                <= state.world_time_seconds
                and not any(effect.kind == "guidance" and effect.target_actor_id == target.actor_id for effect in state.active_effects)
            )
        if spell_id in {"heal", "soothe", "void_warp", "protection"}:
            return self._is_living_target(target)
        return not target.dead and not target.defeated

    def _breathe_fire_targets(
        self, state, caster, direction: Position, *, length_ft: int = 15
    ) -> tuple[str, ...]:
        if type(length_ft) is not int or length_ft not in {15, 20}:
            raise ValueError("Breathe Fire has an unsupported cone length")
        cells = cone_cells(Footprint(caster.position), direction, length_ft)
        return tuple(
            target.actor_id
            for target in state.creatures.values()
            if not target.dead and target.position in cells
        )

    def execute(self, command: Command) -> ActionResult:
        if not isinstance(command, (Stride, Step, Strike, QuickBomber, QuickAlchemy, ActivateAlchemy, ViciousSwing, Cast, LingeringComposition, Sustain, Dismiss, TakeCover, DismissCover, RaiseShield, Interact, Release, Stand, Crawl, Flee, EndTurn, Choose, FamilyCommand)):
            return self._result(ResultStatus.UNSUPPORTED, f"Unsupported command type: {type(command).__name__}.")
        if self._state.pending_choice is not None and not isinstance(command, Choose):
            return self._result(ResultStatus.REJECTED, "A pending choice must be resolved before another action.")
        if self._state.pending_choice is None and isinstance(command, Choose):
            return self._result(ResultStatus.REJECTED, "There is no pending choice to resolve.")
        finished_choice = (
            isinstance(command, Choose)
            and self._state.pending_choice is not None
            and (self._state.pending_choice.procedure_id or "").startswith(
                ("investigator:forensic_examination:", "investigator:streetwise:")
            )
        )
        if not self._state.in_progress and not finished_choice:
            return self._result(ResultStatus.REJECTED, "The encounter has already finished.")

        draft = deepcopy(self._state)
        dice = self._dice.clone()
        try:
            events = self._resolve(draft, dice, command)
        except _Rejected as error:
            return self._result(ResultStatus.REJECTED, str(error))
        except _Unsupported as error:
            return self._result(ResultStatus.UNSUPPORTED, str(error))
        except DiceSourceError as error:
            # Both the private state copy and private dice cursor are discarded.
            return self._result(ResultStatus.REJECTED, str(error))
        except UnsupportedHealthRuleError as error:
            return self._result(ResultStatus.UNSUPPORTED, str(error))

        # Dueling Parry has a continuous one-weapon/empty-other-hands
        # requirement. Resolve every completed command first, then discard a
        # guard whose equipment facts no longer qualify; a later retrieve or
        # draw cannot reactivate that same use of the feat.
        from .martial_defense import end_dueling_parries_with_broken_requirements
        from .fighter import end_snagging_strikes_out_of_reach

        end_dueling_parries_with_broken_requirements(draft)
        end_snagging_strikes_out_of_reach(draft)

        self._state = draft
        self._dice = dice
        pending = draft.pending_choice is not None
        message = events[0].text if events else "Action completed."
        if pending:
            message = draft.pending_choice.prompt
            status = ResultStatus.PAUSED
        elif draft.in_progress is False:
            message = "Encounter finished."
            status = ResultStatus.COMPLETED
        elif any(event.kind == "turn_ended" for event in events):
            message = "Turn ended."
            status = ResultStatus.COMPLETED
        else:
            status = ResultStatus.COMPLETED
        return ActionResult(
            status=status,
            events=tuple(events),
            message=message,
            inspection=self.inspect(),
        )

    def _resolve(self, state: EncounterState, dice: DiceSource, command: Command) -> list[Event]:
        if isinstance(command, Choose):
            return self._choose(state, dice, command)
        actor_id = self._active_actor_id(state)
        if actor_id is None:
            raise _Rejected("There is no active actor.")
        actor = state.creatures[actor_id]
        self._refresh_barbarian_state(state, actor)
        # A spellshape is spent by the next Cast; every other action (including
        # a free action or End Turn) invalidates its pending marker.
        # Rejected commands remain atomic because this is the draft state.
        if has_pending_spellshape(actor) and not isinstance(command, (Cast, ReachSpell, WidenSpell, EnergyAblation)):
            clear_pending_spellshape(actor)
        lingering = actor.lingering_composition_pending
        fleeing = self._active_fleeing_effect(state, actor)
        if fleeing is not None and not isinstance(command, Flee):
            raise _Rejected("Fleeing requires the Flee action until the effect expires.")
        if isinstance(command, Flee):
            if actor.unconscious or actor.dead:
                raise _Rejected("An unconscious or dead actor cannot take actions.")
            events = self._flee(state, dice, actor, fleeing)
            if lingering:
                actor.lingering_composition_pending = False
            return events
        if isinstance(command, FamilyCommand):
            if actor.unconscious or actor.dead:
                raise _Rejected("An unconscious or dead actor cannot take actions.")
            if actor.must_leave_occupied:
                raise _Rejected("Move immediately to leave the occupied ally's space before another action.")
            events = self._run_family_action(state, dice, actor, command)
            if lingering:
                actor.lingering_composition_pending = False
            return events
        if isinstance(command, EndTurn):
            if actor.must_leave_occupied:
                raise _Rejected("Move immediately to leave the occupied ally's space before ending the turn.")
            events = self._end_turn(state, actor, early=True, dice=dice)
            if lingering:
                actor.lingering_composition_pending = False
            return events
        if actor.unconscious or actor.dead:
            raise _Rejected("An unconscious or dead actor cannot take actions.")
        if isinstance(command, LingeringComposition):
            return self._lingering_composition(state, actor)
        if isinstance(command, DismissCover):
            if actor.actor_id not in state.taking_cover:
                raise _Rejected("The actor is not taking cover.")
            state.taking_cover.remove(actor.actor_id)
            if lingering:
                actor.lingering_composition_pending = False
            return [Event("cover_dismissed", actor.actor_id, None, f"{actor.label} dismisses Take Cover.")]
        if isinstance(command, RaiseShield):
            events = self._raise_shield(state, dice, actor)
            if lingering:
                actor.lingering_composition_pending = False
            return events
        if isinstance(command, Release):
            events = self._release(state, actor, command)
            if lingering:
                actor.lingering_composition_pending = False
            return events
        if actor.must_leave_occupied and not isinstance(command, (Stride, Step, Crawl)):
            raise _Rejected("Move immediately to leave the occupied ally's space before another action.")
        if isinstance(command, Dismiss) and command.effect_id is not None:
            return self._dismiss_life_link(state, dice, actor, command)
        if actor.actions_remaining < 1:
            raise _Rejected("The active actor has no actions remaining.")
        # A spellshape benefit lasts only until the next action.  This runs in
        # the transaction after ordinary validity gates, so rejected input is
        # atomic while any completed non-cast action consumes the window.
        if lingering and not isinstance(command, Cast):
            actor.lingering_composition_pending = False
        if isinstance(command, Stride):
            return self._stride(state, dice, actor, command)
        if isinstance(command, Step):
            return self._step(state, dice, actor, command)
        if isinstance(command, Strike):
            return self._strike(state, dice, actor, command)
        if isinstance(command, QuickBomber):
            return self._quick_bomber(state, dice, actor, command)
        if isinstance(command, QuickAlchemy):
            return self._quick_alchemy(state, dice, actor, command)
        if isinstance(command, ActivateAlchemy):
            return self._activate_alchemy(state, dice, actor, command)
        if isinstance(command, ViciousSwing):
            return self._vicious_swing(state, dice, actor, command)
        if isinstance(command, Cast):
            events = self._cast(state, dice, actor, command)
            if lingering:
                if command.spell_id == "courageous_anthem":
                    return self._resolve_lingering_composition(state, dice, actor, events)
                actor.lingering_composition_pending = False
            return events
        if isinstance(command, Sustain):
            return self._sustain_light(state, dice, actor, command)
        if isinstance(command, Dismiss):
            return self._dismiss_light(state, dice, actor, command)
        if isinstance(command, TakeCover):
            return self._take_cover(state, dice, actor)
        if isinstance(command, DismissCover):
            raise _Rejected("The actor is not taking cover.")
        if isinstance(command, Interact):
            return self._interact(state, dice, actor, command)
        if isinstance(command, Release):
            return self._release(state, actor, command)
        if isinstance(command, Stand):
            return self._stand(state, dice, actor)
        if isinstance(command, Crawl):
            return self._crawl(state, dice, actor, command)
        raise _Rejected("This action is not supported in the admitted encounter.")

    def _stride(self, state: EncounterState, dice: DiceSource, actor: CreatureState, command: Stride) -> list[Event]:
        return self._begin_move(state, dice, actor, command.path, "stride", reactions=True)

    @staticmethod
    def _active_fleeing_effect(
        state: EncounterState, actor: CreatureState
    ) -> ActiveSpellEffect | None:
        """Return a live Fleeing source for ``actor``.

        Fleeing is represented by the existing sourced spell-effect record.
        During active combat its printed source-turn boundary is authoritative:
        the encounter's six-second round clock can cross the absolute deadline
        before a later-in-initiative source starts its next turn.  Absolute
        time remains available for an explicit elapsed-time transition outside
        active combat.  The live checks make stale effects harmless between
        those maintenance boundaries and keep an invalid source fail-closed.
        """

        starts = state.actor_start_counts
        now = state.world_time_seconds
        for effect in state.active_effects:
            if (
                effect.kind != "fleeing"
                or effect.target_actor_id != actor.actor_id
                or effect.source_actor_id not in state.creatures
                or effect.expires_at_source_start <= starts.get(effect.source_actor_id, 0)
                or (
                    not state.in_progress
                    and effect.expires_at_world_time is not None
                    and effect.expires_at_world_time <= now
                )
            ):
                continue
            return effect
        return None

    def _flee(
        self,
        state: EncounterState,
        dice: DiceSource,
        actor: CreatureState,
        effect: ActiveSpellEffect | None,
    ) -> list[Event]:
        """Use the one admitted Flee action for a currently fleeing actor."""

        if effect is None:
            raise _Rejected("Flee is only available while the actor is fleeing.")
        setup = get_setup(state.setup_id)
        if not setup.closed_boundary:
            raise _Unsupported(
                "Flee requires an explicitly closed supported scene; open edges and exits are not admitted."
            )
        source = state.creatures.get(effect.source_actor_id)
        if source is None:
            raise _Unsupported("Flee requires a living creature source for its fleeing effect.")

        # Fleeing first performs a necessary Escape or Stand when one is
        # required.  These call the existing family/stand procedures, so their
        # checks, Hero choices, and saved continuations remain authoritative.
        impediments = tuple(
            sorted(
                (
                    current
                    for current in state.condition_effects
                    if current.target_actor_id == actor.actor_id
                    and current.kind in {"grabbed", "immobilized", "restrained"}
                ),
                key=lambda current: (
                    {"restrained": 0, "grabbed": 1, "immobilized": 2}[current.kind],
                    current.effect_id,
                ),
            )
        )
        if impediments:
            from .skill_actions import Escape

            # Athletics is an admitted Escape statistic for every creature;
            # the existing procedure supplies the source-backed DC and rolls
            # one action, including any normal Hero Point choice.
            return self._run_family_action(
                state,
                dice,
                actor,
                Escape(impediments[0].effect_id, "athletics"),
            )
        if actor.prone:
            return self._stand(state, dice, actor)

        other_creatures = tuple(
            current for current in state.creatures.values()
            if current.actor_id != actor.actor_id
        )
        body_positions = tuple(
            current.position
            for current in other_creatures
            if (current.unconscious or current.dead)
            and current.prone
            and self._can_share_with_body(actor, current)
        )
        ally_positions = tuple(
            current.position
            for current in other_creatures
            if current.team == actor.team
            and not current.unconscious
            and not current.dead
            and not current.defeated
        )
        occupied_positions = tuple(current.position for current in other_creatures)
        illegal_final_positions = (
            ally_positions
            if actor.actions_remaining < 2 or actor.must_leave_occupied
            else ()
        )
        route = choose_flee_route(
            actor.position,
            source.position,
            state.map_width,
            state.map_height,
            effective_speed_ft(actor, get_definition(actor.definition_id), self._conditions_for_actor(state, actor)),
            diagonals_already_made=actor.diagonals_this_turn,
            occupied_positions=occupied_positions,
            body_positions=body_positions,
            ally_positions=ally_positions,
            illegal_final_positions=illegal_final_positions,
        )
        if route.stop_reason == "occupied_blocker" and not route.path:
            raise _Unsupported(
                "Flee reaches an unwilling creature; Tumble Through is not admitted in this closed scene."
            )
        if route.path:
            return self._begin_move(
                state,
                dice,
                actor,
                route.path,
                "flee",
                reactions=True,
            )

        # At a physical boundary the attempted Flee still consumes its action.
        # Keep the actor on the board and preserve the explicit reason for the
        # blocked attempt; no defeat or map exit is invented.
        actor.actions_remaining -= 1
        state.taking_cover.discard(actor.actor_id)
        return self._complete_action(
            state,
            actor,
            [Event(
                "flee_blocked",
                actor.actor_id,
                source.actor_id,
                f"{actor.label} cannot move farther from {source.label}; the closed-room boundary blocks Flee.",
                position=actor.position,
            )],
            dice=dice,
        )

    def _step(self, state: EncounterState, dice: DiceSource, actor: CreatureState, command: Step) -> list[Event]:
        definition = get_definition(actor.definition_id)
        if effective_speed_ft(actor, definition, self._conditions_for_actor(state, actor)) < 10:
            raise _Rejected("Step requires a land Speed of at least 10 feet.")
        return self._begin_move(state, dice, actor, (command.destination,), "step", reactions=False, max_distance=5)

    def _crawl(self, state: EncounterState, dice: DiceSource, actor: CreatureState, command: Crawl) -> list[Event]:
        if not actor.prone:
            raise _Rejected("Crawl is only available while prone.")
        return self._begin_move(state, dice, actor, command.path, "crawl", reactions=True, max_distance=5)

    def _sudden_charge_path_is_legal(self, state, actor, path, *, origin, diagonals) -> str | None:
        """Validate one subordinate Stride without charging an extra action."""
        if not isinstance(path, tuple) or not path:
            return "Sudden Charge requires two nonempty Stride paths."
        definition = get_definition(actor.definition_id)
        limit = effective_speed_ft(actor, definition, self._conditions_for_actor(state, actor))
        distance = 0
        current = origin
        prior_diagonals = diagonals
        for point in path:
            if not isinstance(point, Position) or not in_bounds(point, state.map_width, state.map_height):
                return "Sudden Charge path leaves the supported map."
            try:
                cost, diagonal_count = step_cost(current, point, prior_diagonals)
            except ValueError:
                return "Sudden Charge path must visit adjacent grid squares."
            occupant = self._occupant_at(state, point, except_actor=actor.actor_id)
            if occupant is not None:
                if occupant.team != actor.team and not occupant.defeated:
                    return "Sudden Charge cannot move through an unwilling living creature."
                if not self._can_share_with_body(actor, occupant) and not (
                    occupant.team == actor.team and not occupant.unconscious and not occupant.dead
                ):
                    return "Sudden Charge path is blocked by an occupied square."
            distance += cost
            if distance > limit:
                return f"Sudden Charge path costs {distance} feet, above its {limit}-foot limit."
            prior_diagonals += diagonal_count
            current = point
        return None

    def _start_sudden_charge(self, context: FamilyProcedureContext, command) -> FamilyProcedureResult:
        """Pay once, then run Sudden Charge's two normal move segments."""
        from .fighter import SuddenCharge

        if not isinstance(command, SuddenCharge):
            return FamilyProcedureResult(rejection="Sudden Charge needs its typed command.")
        actor, state = context.actor, context.state
        if actor.flourish_used_round == state.round_number:
            return FamilyProcedureResult(rejection="Only one flourish action can be used per round.")
        try:
            self._require_action_permitted(state, actor, "sudden_charge", frozenset({"flourish", "move"}))
        except _Rejected as error:
            return FamilyProcedureResult(rejection=str(error))
        first_error = self._sudden_charge_path_is_legal(
            state, actor, command.first_path, origin=actor.position,
            diagonals=actor.diagonals_this_turn,
        )
        if first_error is not None:
            return FamilyProcedureResult(rejection=first_error)
        first_end = command.first_path[-1]
        first_diagonals = actor.diagonals_this_turn
        first_point = actor.position
        for point in command.first_path:
            _cost, diagonal_count = step_cost(first_point, point, first_diagonals)
            first_diagonals += diagonal_count
            first_point = point
        second_error = self._sudden_charge_path_is_legal(
            state, actor, command.second_path, origin=first_end,
            diagonals=first_diagonals,
        )
        if second_error is not None:
            return FamilyProcedureResult(rejection=second_error)
        actor.actions_remaining -= 2
        actor.flourish_used_round = state.round_number
        state.taking_cover.discard(actor.actor_id)
        continuation = ActionContinuation(
            kind="movement", actor_id=actor.actor_id, path=command.first_path,
            movement_kind="sudden_charge", stage="first_stride", seen_reactors=[],
            sudden_charge_second_path=command.second_path,
            sudden_charge_first_path=command.first_path,
            sudden_charge_origin=actor.position,
            sudden_charge_origin_diagonals=actor.diagonals_this_turn,
            target_id=command.target_id, attack_id=command.attack_id, item_id=command.item_id,
        )
        events = [Event(
            "sudden_charge_started", actor.actor_id, command.target_id,
            f"{actor.label} begins Sudden Charge: two Strides for two actions.",
        )]
        events.extend(self._advance_continuation(state, context.dice, continuation))
        return FamilyProcedureResult(events=tuple(events))

    def _resume_sudden_charge(self, context: FamilyProcedureContext) -> FamilyProcedureResult:
        """Resume a saved family-form Sudden Charge frame, fail closed otherwise."""
        pending = context.pending
        if pending is None or pending.continuation is None:
            return FamilyProcedureResult(rejection="Sudden Charge has no saved continuation.")
        try:
            self._validate_sudden_charge_continuation(context.state, pending.continuation)
        except ValueError as error:
            return FamilyProcedureResult(rejection=str(error))
        return FamilyProcedureResult(events=tuple(
            self._advance_continuation(context.state, context.dice, pending.continuation)
        ))

    def _validate_sudden_charge_pending(self, context: FamilyProcedureContext) -> None:
        pending = context.pending
        if pending is None or pending.continuation is None:
            raise ValueError("save has no Sudden Charge continuation")
        self._validate_sudden_charge_continuation(context.state, pending.continuation)

    def _finish_sudden_charge(self, state, dice, actor, continuation: ActionContinuation) -> list[Event]:
        """Resolve Sudden Charge's optional last subordinate Strike."""
        if continuation.target_id is None:
            return self._complete_action(state, actor, [Event(
                "sudden_charge_complete", actor.actor_id, None,
                f"{actor.label} completes Sudden Charge without a Strike.",
            )], dice=dice)
        attack = self._select_attack(
            state, actor, continuation.attack_id or "", item_id=continuation.item_id,
        )
        if attack is None or "melee" not in attack.traits:
            return self._complete_action(state, actor, [Event(
                "sudden_charge_strike_stopped", actor.actor_id, continuation.target_id,
                "Sudden Charge's selected final melee Strike is no longer legal.",
            )], dice=dice)
        parent = ActionContinuation(kind="sudden_charge", actor_id=actor.actor_id)
        try:
            return self._start_strike(
                state, dice, actor, continuation.target_id, attack.attack_id,
                continuation.item_id, None, None, actions_cost=0,
                attack_count_cost=1, vicious_swing=False, parent=parent,
            )
        except _Rejected as error:
            return self._complete_action(state, actor, [Event(
                "sudden_charge_strike_stopped", actor.actor_id, continuation.target_id,
                f"Sudden Charge's final Strike stops: {error}",
            )], dice=dice)

    def _begin_move(self, state, dice, actor, path, kind, *, reactions, max_distance=None) -> list[Event]:
        self._require_action_permitted(state, actor, kind, frozenset({"move"}))
        if actor.prone and kind not in ("crawl",):
            raise _Rejected("While prone, only Crawl or Stand can be used as a move action.")
        if not isinstance(path, tuple) or not path:
            raise _Rejected(f"{kind.title()} requires a nonempty tuple of path squares.")
        definition = get_definition(actor.definition_id)
        limit = effective_speed_ft(actor, definition, self._conditions_for_actor(state, actor)) if max_distance is None else max_distance
        distance = 0
        diagonals = actor.diagonals_this_turn
        current = actor.position
        final_living_ally = False
        for index, point in enumerate(path):
            if not isinstance(point, Position) or not in_bounds(point, state.map_width, state.map_height):
                raise _Rejected(f"{kind.title()} path leaves the supported map.")
            try:
                cost, diagonal_count = step_cost(current, point, diagonals)
            except ValueError as error:
                raise _Rejected(f"{kind.title()} path must visit adjacent grid squares.") from error
            occupant = self._occupant_at(state, point, except_actor=actor.actor_id)
            if occupant is not None:
                if occupant.team == actor.team and not occupant.defeated and not occupant.unconscious and not occupant.dead:
                    final_living_ally = index == len(path) - 1
                elif self._can_share_with_body(actor, occupant):
                    final_living_ally = False
                elif occupant.team != actor.team and not occupant.defeated:
                    raise _Unsupported("Moving through an unwilling living creature requires unsupported Tumble Through.")
                else:
                    raise _Rejected("The movement path is blocked by an occupied square.")
            else:
                final_living_ally = False
            distance += cost
            if distance > limit:
                if kind == "step":
                    raise _Rejected(f"The Step would cost {distance} feet, above Step's 5-foot movement.")
                raise _Rejected(f"{kind.title()} path costs {distance} feet, above its {limit}-foot limit.")
            diagonals += diagonal_count
            current = point
        if actor.must_leave_occupied and final_living_ally:
            raise _Rejected("Move to an unoccupied square immediately after entering an ally's space.")
        if final_living_ally and actor.actions_remaining < 2:
            raise _Rejected("Entering an ally's space requires another immediate move action to leave it.")

        mobility_suppresses_reactions = False
        if kind == "stride" and reactions:
            from .movement_progression import mobility_applies

            mobility_suppresses_reactions = mobility_applies(
                actor,
                actual_speed_feet=limit,
                path_cost_feet=distance,
                action_kind=kind,
            )

        actor.actions_remaining -= 1
        state.taking_cover.discard(actor.actor_id)
        actor.must_leave_occupied = False
        continuation = ActionContinuation(
            kind="movement",
            actor_id=actor.actor_id,
            path=path,
            movement_kind=kind,
            seen_reactors=[],
        )
        events = [Event(f"{kind}_started", actor.actor_id, None, f"{kind.title()} committed; {distance} feet of movement.")]
        if kind == "step" or not reactions or mobility_suppresses_reactions:
            released_holds = False
            for point in path:
                cost, diagonal_count = step_cost(actor.position, point, actor.diagonals_this_turn)
                actor.position = point
                actor.diagonals_this_turn += diagonal_count
                if not released_holds:
                    events.extend(self._release_sourced_holds(state, actor))
                    released_holds = True
            actor.must_leave_occupied = self._ends_in_living_ally_space(actor, state)
            events.append(Event(kind, actor.actor_id, None, f"{kind.title()}: moved to {_coord(actor.position)}.", position=actor.position))
            return self._complete_action(state, actor, events, dice=dice)
        return events + self._advance_continuation(state, dice, continuation)

    def _strike(self, state: EncounterState, dice: DiceSource, actor: CreatureState, command: Strike) -> list[Event]:
        return self._start_strike(
            state, dice, actor, command.target_id, command.attack_id,
            command.item_id, command.damage_type, command.nonlethal,
            actions_cost=1, attack_count_cost=1,
            vicious_swing=False, use_intelligence=command.use_intelligence,
        )

    @staticmethod
    def _initialize_bomber_alchemy(state) -> None:
        from .alchemy import (
            FAR_LOBBER,
            AlchemyBuildChoices,
            InfusedAlchemyItem,
            advanced_alchemy_capacity,
            build_alchemy_state,
        )
        from .alchemist_content import (
            BOMBER_FIELD_FORMULA_IDS,
            BOMBER_FORMULA_IDS,
            BOMBER_LEVEL_2_CONDITION_BOMB_FORMULA_IDS,
            BOMBER_LEVEL_2_ITEM_SUPPORT_FORMULA_IDS,
        )
        from .content import (
            BOMBER_ALCHEMIST_LEVEL_2,
            BOMBER_ALCHEMIST_LEVEL_2_FORMULA_IDS,
            BOMBER_ALCHEMIST_LEVEL_2_CONDITION_BOMBS,
            BOMBER_ALCHEMIST_LEVEL_2_ITEM_SUPPORT,
        )
        for actor in state.creatures.values():
            definition = get_definition(actor.definition_id)
            if "bomber_alchemist" not in definition.abilities:
                continue
            level_two = definition.definition_id in {
                BOMBER_ALCHEMIST_LEVEL_2.definition_id,
                BOMBER_ALCHEMIST_LEVEL_2_ITEM_SUPPORT.definition_id,
                BOMBER_ALCHEMIST_LEVEL_2_CONDITION_BOMBS.definition_id,
            }
            formula_ids = (
                BOMBER_LEVEL_2_CONDITION_BOMB_FORMULA_IDS
                if definition.definition_id == BOMBER_ALCHEMIST_LEVEL_2_CONDITION_BOMBS.definition_id
                else BOMBER_LEVEL_2_ITEM_SUPPORT_FORMULA_IDS
                if definition.definition_id == BOMBER_ALCHEMIST_LEVEL_2_ITEM_SUPPORT.definition_id
                else BOMBER_ALCHEMIST_LEVEL_2_FORMULA_IDS
                if definition.definition_id == BOMBER_ALCHEMIST_LEVEL_2.definition_id
                else BOMBER_FORMULA_IDS
            )
            state.alchemy_states[actor.actor_id] = build_alchemy_state(
                AlchemyBuildChoices(
                    "bomber",
                    BOMBER_FIELD_FORMULA_IDS,
                    formula_ids,
                    4,
                    "quick_bomber",
                    2 if level_two else 1,
                    FAR_LOBBER if level_two else None,
                ),
                daily_preparation_id="day:1",
            )
            for item_id in actor.stowed_items:
                instance = state.item_instances.get(item_id)
                if instance is not None and instance.definition_id in BOMBER_FIELD_FORMULA_IDS:
                    state.infused_alchemy_items[item_id] = InfusedAlchemyItem(item_id, instance.definition_id, actor.actor_id, "advanced_alchemy", 0, "day:1", 86400)
            prepared_formula_ids = state.alchemy_states[actor.actor_id].known_formula_ids[
                :advanced_alchemy_capacity(state.alchemy_states[actor.actor_id])
            ]
            for index, formula_id in enumerate(prepared_formula_ids, start=1):
                if formula_id in BOMBER_FIELD_FORMULA_IDS:
                    continue
                item_id = f"{actor.actor_id}:advanced:day:1:{index}"
                state.item_instances[item_id] = ItemInstance(item_id, formula_id, 1)
                state.infused_alchemy_items[item_id] = InfusedAlchemyItem(item_id, formula_id, actor.actor_id, "advanced_alchemy", 0, "day:1", 86400)
                actor.stowed_items.append(item_id)

    def _quick_alchemy(self, state, dice, actor, command: QuickAlchemy) -> list[Event]:
        from .alchemy import AlchemyRuleError, QuickAlchemyRequest, perform_quick_alchemy
        alchemy_state = state.alchemy_states.get(actor.actor_id)
        if alchemy_state is None:
            raise _Unsupported("Quick Alchemy is not admitted for this creature.")
        if command.mode != "create_consumable":
            raise _Rejected("This selected Bomber exposes Create Consumable, not a general Quick Vial menu.")
        toolkit = "alchemists_toolkit" in actor.worn_items or any(state.item_instances.get(item_id) is not None and state.item_instances[item_id].definition_id == "alchemists_toolkit" for item_id in actor.worn_items + actor.held_items)
        try:
            created = perform_quick_alchemy(alchemy_state, QuickAlchemyRequest("create_consumable", actor.actor_id, state.world_time_seconds, toolkit, self._free_hands(state, get_definition(actor.definition_id), actor) >= 1, formula_id=command.formula_id, creator_turn_occurrence=state.actor_start_counts.get(actor.actor_id, 0)))
        except AlchemyRuleError as error:
            raise _Rejected(str(error)) from error
        actor.actions_remaining -= 1
        state.alchemy_states[actor.actor_id] = created.state
        state.infused_alchemy_items[created.item.instance_id] = created.item
        state.item_instances[created.item.instance_id] = ItemInstance(created.item.instance_id, created.item.formula_id or "", 1)
        actor.held_items.append(created.item.instance_id)
        return self._complete_action(state, actor, [Event("quick_alchemy", actor.actor_id, None, f"{actor.label} creates {created.item.formula_id.replace('_', ' ')} from one stored versatile vial.")], dice=dice)

    def _activate_alchemy(self, state, dice, actor, command: ActivateAlchemy) -> list[Event]:
        """Use the selected first three held formula effects without a generic item system."""
        from .alchemy import AlchemyRuleError, validate_alchemy_activation_window
        from .alchemy_content import ElixirFacts, MutagenFacts, PoisonFacts, FORMULAS_BY_ID
        if command.item_id not in actor.held_items:
            raise _Rejected("An activated alchemical item must be held.")
        infused = state.infused_alchemy_items.get(command.item_id)
        instance = state.item_instances.get(command.item_id)
        if infused is None or instance is None or infused.formula_id not in FORMULAS_BY_ID:
            raise _Rejected("This is not a tracked selected infused formula item.")
        formula = FORMULAS_BY_ID[infused.formula_id]
        if not isinstance(formula.facts, (ElixirFacts, MutagenFacts, PoisonFacts)):
            raise _Rejected("That selected formula activation is not available.")
        is_juggernaut = formula.formula_id == "juggernaut_mutagen_lesser"
        if is_juggernaut:
            if actor.temporary_hp > 0 and command.temporary_hp_choice not in _ALCHEMY_TEMP_HP_CHOICES:
                raise _Rejected("Choose keep_existing or gain_new for the temporary-HP pool before drinking Juggernaut Mutagen.")
            if actor.temporary_hp == 0 and command.temporary_hp_choice is not None:
                raise _Rejected("A temporary-HP choice is only available when an existing pool remains.")
        elif command.temporary_hp_choice is not None:
            raise _Rejected("A temporary-HP choice is only available for Juggernaut Mutagen.")
        if isinstance(formula.facts, PoisonFacts):
            return self._coat_giant_centipede_venom(state, dice, actor, command, infused, formula)
        target = state.creatures.get(command.target_id or actor.actor_id)
        if target is None or target.dead or not self._is_living_target(target):
            raise _Rejected("Elixir effects require a living active recipient.")
        if target.actor_id != actor.actor_id and grid_distance_feet(actor.position, target.position) > 5:
            raise _Rejected("Feeding an elixir requires an adjacent recipient.")
        if target.actor_id != actor.actor_id and target.team != actor.team and not target.unconscious:
            raise _Rejected("An active hostile recipient can prevent being fed an elixir.")
        try:
            validate_alchemy_activation_window(infused, active_preparation_id=state.alchemy_states[actor.actor_id].daily_preparation_id, now_seconds=state.world_time_seconds, creator_turn_occurrence=state.actor_start_counts.get(actor.actor_id, 0))
        except AlchemyRuleError as error:
            raise _Rejected(str(error)) from error
        if actor.actions_remaining < formula.activation_actions:
            raise _Rejected(f"This formula activation requires {formula.activation_actions} action(s).")
        actor.actions_remaining -= formula.activation_actions
        actor.held_items.remove(command.item_id)
        state.consumed_infused_item_ids.add(command.item_id)
        events=[]
        if isinstance(formula.facts, ElixirFacts):
            facts = formula.facts
            duration = facts.duration_seconds
            if duration is None:
                raise _Rejected(f"{formula.name} has no admitted duration.")
            if facts.effect == "heal":
                amount = dice.draw(6)
                if target.health_mode is HealthMode.PC:
                    self._apply_health_transition(state, target, pc_healing(self._health_state(target), amount))
                else:
                    target.hp = min(get_definition(target.definition_id).hp, target.hp + amount)
                bonus = facts.save_bonuses[0]
                state.active_effects.append(ActiveSpellEffect(f"alchemy:{command.item_id}", f"alchemy_{formula.formula_id}", actor.actor_id, target.actor_id, bonus.bonus, state.actor_start_counts.get(actor.actor_id, 0) + 1, state.world_time_seconds + duration))
                events.append(Event("alchemy_healing", actor.actor_id, target.actor_id, f"{target.label} drinks Minor Elixir of Life and heals {amount} HP (1d6 {amount}); +1 item to Fortitude saves against poison or disease for 10 minutes."))
            elif facts.effect == "save_bonus":
                bonus = facts.save_bonuses[0]
                from .alchemy import quick_alchemy_effect_duration
                duration = quick_alchemy_effect_duration(duration) if infused.creation_kind == "quick_alchemy" else duration
                state.active_effects.append(ActiveSpellEffect(f"alchemy:{command.item_id}", f"alchemy_{formula.formula_id}", actor.actor_id, target.actor_id, bonus.bonus, state.actor_start_counts.get(actor.actor_id, 0) + 1, state.world_time_seconds + duration))
                detail = " and +2 against fear" if formula.formula_id == "bravos_brew_lesser" else ""
                events.append(Event("alchemy_save_bonus", actor.actor_id, target.actor_id, f"{target.label} gains +{bonus.bonus} to {bonus.statistic.title()} saves for {duration} seconds{detail}."))
            elif facts.effect == "speed_bonus":
                if facts.speed_bonus_ft <= 0:
                    raise _Rejected(f"{formula.name} has no admitted Speed bonus.")
                from .alchemy import quick_alchemy_effect_duration
                duration = quick_alchemy_effect_duration(duration) if infused.creation_kind == "quick_alchemy" else duration
                state.active_effects.append(ActiveSpellEffect(f"alchemy:{command.item_id}", f"alchemy_{formula.formula_id}", actor.actor_id, target.actor_id, facts.speed_bonus_ft, state.actor_start_counts.get(actor.actor_id, 0) + 1, state.world_time_seconds + duration))
                events.append(Event("alchemy_speed_bonus", actor.actor_id, target.actor_id, f"{target.label} gains a +{facts.speed_bonus_ft}-foot status bonus to Speed for {duration} seconds."))
            else:
                raise _Rejected(f"{formula.name} has an unsupported elixir effect.")
        elif isinstance(formula.facts, MutagenFacts):
            if target.actor_id != actor.actor_id:
                raise _Rejected("The selected mutagens are drunk only by their user.")
            from .alchemy import quick_alchemy_effect_duration
            duration = quick_alchemy_effect_duration(formula.facts.duration_seconds) if infused.creation_kind == "quick_alchemy" else formula.facts.duration_seconds
            mutagen_kinds = {
                "alchemy_bestial_mutagen_lesser",
                "alchemy_cognitive_mutagen_lesser",
                "alchemy_juggernaut_mutagen_lesser",
            }
            prior = next((effect for effect in state.active_effects if effect.target_actor_id == actor.actor_id and effect.kind in mutagen_kinds), None)
            cleared_counteracted_juggernaut_temp_hp = False
            if prior is not None:
                check = resolve_check(dice.draw(20), 5, 15)
                events.append(Event("alchemy_counteract", actor.actor_id, actor.actor_id, f"{actor.label} attempts to counteract the prior mutagen: d20 {check.die} + 5 = {check.total} vs DC 15.", check=check))
                if check.degree not in {DegreeOfSuccess.SUCCESS, DegreeOfSuccess.CRITICAL_SUCCESS}:
                    events.append(Event("alchemy_mutagen_failed", actor.actor_id, actor.actor_id, f"{formula.name} fails to counteract the existing mutagen; the consumed item has no effect."))
                    return self._complete_action(state, actor, events, dice=dice)
                state.active_effects.remove(prior)
                if prior.kind == "alchemy_juggernaut_mutagen_lesser" and actor.temporary_hp_source_id == prior.effect_id:
                    # Counteracting the source ends its printed benefit.  A
                    # keep-existing choice can preserve another pool, but it
                    # cannot preserve temporary HP granted by the removed
                    # Juggernaut effect.
                    actor.temporary_hp = 0
                    actor.temporary_hp_source_id = None
                    actor.temporary_hp_expires_at_seconds = None
                    actor.temporary_hp_expires_at_source_start = 0
                    cleared_counteracted_juggernaut_temp_hp = True
            effect_id = f"alchemy:{command.item_id}"
            effect_value = formula.facts.save_bonuses[0].bonus if formula.facts.save_bonuses else 1
            state.active_effects.append(ActiveSpellEffect(effect_id, f"alchemy_{formula.formula_id}", actor.actor_id, actor.actor_id, effect_value, state.actor_start_counts.get(actor.actor_id, 0) + 1, state.world_time_seconds + duration))
            gaining_temporary_hp = (
                formula.facts.temporary_hp > 0
                and (
                    command.temporary_hp_choice == "gain_new"
                    or (
                        actor.temporary_hp == 0
                        and (
                            command.temporary_hp_choice is None
                            or cleared_counteracted_juggernaut_temp_hp
                        )
                    )
                )
            )
            if gaining_temporary_hp:
                actor.temporary_hp = formula.facts.temporary_hp
                actor.temporary_hp_source_id = effect_id
                actor.temporary_hp_expires_at_seconds = state.world_time_seconds + duration
                actor.temporary_hp_expires_at_source_start = 0
            replacement = " It counteracts the previous mutagen." if prior else ""
            temp_text = (
                f" It grants {formula.facts.temporary_hp} temporary HP."
                if gaining_temporary_hp
                else " It keeps the existing temporary-HP pool."
                if formula.facts.temporary_hp > 0
                else ""
            )
            events.append(Event("alchemy_mutagen", actor.actor_id, actor.actor_id, f"{actor.label} drinks {formula.name}; its printed benefits and drawbacks last {duration} seconds.{temp_text}{replacement}"))
        else:
            raise _Rejected("Giant Centipede Venom coating is the next selected activation path.")
        return self._complete_action(state, actor, events, dice=dice)

    def _coat_giant_centipede_venom(self, state, dice, actor, command, infused, formula) -> list[Event]:
        """Apply the selected injury poison to the held mundane dagger."""
        from .alchemy import AlchemyRuleError, validate_alchemy_activation_window
        dagger_id = next((item_id for item_id in actor.held_items if state.item_instances.get(item_id) is not None and state.item_instances[item_id].definition_id == "dagger"), None)
        if dagger_id is None:
            raise _Rejected("Giant Centipede Venom needs the held dagger; the held vial supplies the second required hand.")
        if actor.actions_remaining < formula.activation_actions:
            raise _Rejected("Giant Centipede Venom requires two actions to apply.")
        try:
            validate_alchemy_activation_window(infused, active_preparation_id=state.alchemy_states[actor.actor_id].daily_preparation_id, now_seconds=state.world_time_seconds, creator_turn_occurrence=state.actor_start_counts.get(actor.actor_id, 0))
        except AlchemyRuleError as error:
            raise _Rejected(str(error)) from error
        actor.actions_remaining -= formula.activation_actions
        actor.held_items.remove(command.item_id)
        state.consumed_infused_item_ids.add(command.item_id)
        state.active_effects[:] = [effect for effect in state.active_effects if effect.kind != "alchemy_giant_centipede_venom_coating" or effect.target_actor_id != actor.actor_id]
        state.active_effects.append(ActiveSpellEffect(f"alchemy:{command.item_id}", "alchemy_giant_centipede_venom_coating", actor.actor_id, actor.actor_id, 17, state.actor_start_counts.get(actor.actor_id, 0) + 1, state.world_time_seconds + formula.facts.maximum_duration_seconds))
        return self._complete_action(state, actor, [Event("alchemy_venom_coating", actor.actor_id, actor.actor_id, f"{actor.label} applies Giant Centipede Venom to the held dagger (DC 17 injury poison).")], dice=dice)

    def _quick_bomber(self, state, dice, actor, command: QuickBomber) -> list[Event]:
        """Run the selected Bomber's finite draw-and-throw route.

        The ordinary ranged Strike pipeline owns MAP, ranged reactions, saved
        Hero choices, and final damage.  This wrapper only supplies Quick
        Bomber's one-action draw and selects an authored prepared bomb.
        """
        definition = get_definition(actor.definition_id)
        if "quick_bomber" not in definition.abilities:
            raise _Unsupported("Quick Bomber is not admitted for this creature.")
        if self._admitted_bomber_bomb_facts(
            command.formula_id,
            character_level=state.alchemy_states[actor.actor_id].character_level,
        ) is None:
            raise _Rejected("Quick Bomber requires one selected prepared Bomber formula.")
        if type(command.only_primary_splash) is not bool:
            raise _Rejected("Quick Bomber splash restriction must be true or false.")
        item_id = next(
            (item for item in actor.held_items + actor.stowed_items
             if (instance := state.item_instances.get(item)) is not None
             and instance.definition_id == command.formula_id),
            None,
        )
        if item_id is None:
            raise _Rejected("No selected prepared bomb is available to draw.")
        from .alchemy import AlchemyRuleError, validate_alchemy_activation_window
        infused = state.infused_alchemy_items.get(item_id)
        if infused is None:
            raise _Rejected("Quick Bomber requires a tracked infused bomb.")
        try:
            validate_alchemy_activation_window(infused,
                active_preparation_id=state.alchemy_states[actor.actor_id].daily_preparation_id,
                now_seconds=state.world_time_seconds,
                creator_turn_occurrence=state.actor_start_counts.get(actor.actor_id, 0))
        except AlchemyRuleError as error:
            raise _Rejected(str(error)) from error
        if item_id in actor.stowed_items:
            actor.stowed_items.remove(item_id)
            actor.held_items.append(item_id)
        attack = next(
            (candidate for candidate in definition.attacks if candidate.item_id == command.formula_id),
            None,
        )
        if attack is None:
            raise _Unsupported("Quick Bomber has no admitted attack for the selected formula.")
        events = self._start_strike(
            state, dice, actor, command.target_id, attack.attack_id, item_id, None, False,
            actions_cost=1, attack_count_cost=1, vicious_swing=False,
            bomber_only_primary_splash=command.only_primary_splash,
        )
        return [Event(
            "quick_bomber", actor.actor_id, command.target_id,
            f"{actor.label} uses Quick Bomber to draw {command.formula_id.replace('_', ' ')} and Strike.",
            details=("only_primary_splash" if command.only_primary_splash else "normal_splash",),
        ), *events]

    def _vicious_swing(self, state, dice, actor, command: ViciousSwing) -> list[Event]:
        if "vicious_swing" not in get_definition(actor.definition_id).abilities:
            raise _Unsupported("Vicious Swing is not admitted for this creature.")
        if actor.flourish_used_round == state.round_number:
            raise _Rejected("Vicious Swing is limited to once per round.")
        return self._start_strike(
            state, dice, actor, command.target_id, command.attack_id,
            command.item_id, command.damage_type, command.nonlethal,
            actions_cost=2, attack_count_cost=2,
            vicious_swing=True,
        )

    def _start_intimidating_strike(self, context, command):
        """Commit Intimidating Strike to the ordinary melee Strike pipeline."""
        from .fighter import IntimidatingStrike

        if not isinstance(command, IntimidatingStrike):
            return FamilyProcedureResult(rejection="Intimidating Strike needs its fighter command.")
        return self._start_committed_strike_rider(context, command, "intimidating_strike")

    def _start_w4_exacting_strike(self, context, command):
        """Commit Exacting Strike to the ordinary melee Strike pipeline."""
        from .w4_offensive import ExactingStrike

        if not isinstance(command, ExactingStrike):
            return FamilyProcedureResult(rejection="Exacting Strike needs its typed command.")
        attack = self._select_attack(context.state, context.actor, command.attack_id, item_id=command.item_id)
        target = context.state.creatures.get(command.target_id)
        if attack is None or target is None or "melee" not in attack.traits:
            return FamilyProcedureResult(rejection="Exacting Strike requires an available melee Strike and active target.")
        parent = ActionContinuation(
            kind="exacting_strike", actor_id=context.actor.actor_id,
            target_id=command.target_id, attack_id=command.attack_id,
        )
        events = self._start_strike(
            context.state, context.dice, context.actor,
            command.target_id, command.attack_id, command.item_id,
            command.damage_type, command.nonlethal,
            actions_cost=1, attack_count_cost=1, vicious_swing=False,
            melee_required=True, parent=parent,
        )
        return FamilyProcedureResult(events=tuple(events))

    def _validate_w4_exacting_press_pending(self, state, pending):
        """Validate the success/failure-effect choice for Exacting Strike."""
        actor = state.creatures.get(pending.actor_id or "")
        target = state.creatures.get(pending.target_id or "")
        continuation = pending.continuation
        resolution = pending.damage_resolution
        attack = self._find_attack(state, actor, pending.attack_id) if actor is not None else None
        if (
            actor is None
            or target is None
            or attack is None
            or continuation is None
            or resolution is None
            or pending.owner_actor_id != actor.actor_id
            or pending.family_id != "martial"
            or pending.procedure_id != "w4_offensive:exacting_strike"
            or pending.options != (
                ChoiceOption("full_hit", "Apply the successful Strike"),
                ChoiceOption("failure_effect", "Use the Press failure effect (no damage; no MAP)"),
            )
            or continuation.kind != "exacting_strike"
            or continuation.actor_id != actor.actor_id
            or continuation.target_id != target.actor_id
            or continuation.attack_id != attack.attack_id
            or resolution.source_kind != "strike"
            or resolution.actor_id != actor.actor_id
            or resolution.target_id != target.actor_id
            or resolution.attack_id != attack.attack_id
            or resolution.continuation != continuation
            or resolution.pending_defense_choice is not None
            or pending.damage_result is None
            or pending.damage_result != resolution.group.results[0]
            or pending.damage_result_is_mitigated
            or pending.check is None
            or pending.check != resolution.check
            or pending.attack_count != actor.strikes_this_turn
            or pending.attack_count_cost != 1
            or pending.attack_actions_cost != 1
            or pending.attack_penalty != multiple_attack_penalty(actor.strikes_this_turn - 1, attack.traits)
            or (
                (attack.item_id is None and pending.item_id is not None)
                or (attack.item_id is not None and pending.item_id not in self._held_attack_item_ids(state, actor, attack))
            )
            or not self._attack_equipped(state, actor, attack)
            or target.defeated
            or actor.unconscious
            or actor.dead
        ):
            raise ValueError("save has an unavailable or inconsistent Exacting Strike Press choice")

    def _resolve_w4_exacting_press_choice(self, state, dice, pending, command):
        """Apply Exacting Strike's success result or its Press failure effect."""
        self._validate_w4_exacting_press_pending(state, pending)
        actor = state.creatures[pending.actor_id]
        target = state.creatures[pending.target_id]
        continuation = pending.continuation
        resolution = pending.damage_resolution
        assert continuation is not None and resolution is not None and pending.check is not None
        if command.option_id == "full_hit":
            return [Event(
                "exacting_strike_full_hit", actor.actor_id, target.actor_id,
                f"{actor.label} keeps Exacting Strike's successful hit.", check=pending.check,
            )] + self._resolve_damage_to_health(state, dice, resolution, resumed=True)
        if command.option_id != "failure_effect":
            raise _Rejected("Choose the successful Strike or Exacting Strike's Press failure effect.")
        if actor.strikes_this_turn < 1:
            raise _Rejected("Exacting Strike's Press failure effect can no longer remove its MAP.")
        actor.strikes_this_turn -= 1
        events = [Event(
            "exacting_strike_failure_effect", actor.actor_id, target.actor_id,
            f"{actor.label} uses Exacting Strike's Press failure effect; the hit deals no damage and does not increase MAP.",
            check=pending.check,
        )]
        events.extend(self._resume_continuation(
            state, dice, continuation, critical=False,
        ))
        return events

    def _start_committed_strike_rider(self, context, command, kind):
        """Commit the finite Fighter result-rider family to one Strike path."""
        from .fighter import BrutishShove, CombatGrab, IntimidatingStrike, SnaggingStrike

        if kind not in {"intimidating_strike", "snagging_strike", "combat_grab", "brutish_shove"}:
            return FamilyProcedureResult(rejection="Unsupported committed Strike rider.")
        if not isinstance(command, (IntimidatingStrike, SnaggingStrike, CombatGrab, BrutishShove)):
            return FamilyProcedureResult(rejection="Fighter rider needs its matching command.")
        target = context.state.creatures.get(command.target_id)
        attack = self._select_attack(context.state, context.actor, command.attack_id, item_id=command.item_id)
        if target is None or attack is None:
            return FamilyProcedureResult(rejection="Fighter rider requires an active target and held attack.")
        if "melee" not in attack.traits:
            return FamilyProcedureResult(rejection="Fighter Strike riders require a melee Strike.")
        if kind in {"snagging_strike", "combat_grab"}:
            if grid_distance_feet(context.actor.position, target.position) > 5:
                return FamilyProcedureResult(rejection="This feat requires the target within reach of the Fighter's free hand.")
        if kind == "brutish_shove":
            if attack.hands_required < 2:
                return FamilyProcedureResult(rejection="Brutish Shove requires a two-handed melee weapon.")
            sizes = {"tiny": 0, "small": 1, "medium": 2, "large": 3, "huge": 4, "gargantuan": 5}
            if (
                command.shove_destination is not None
                and sizes.get(get_definition(target.definition_id).size, 99) <= sizes.get(context.definition.size, -1)
            ):
                destination = command.shove_destination
                away_x = (target.position.x > context.actor.position.x) - (target.position.x < context.actor.position.x)
                away_y = (target.position.y > context.actor.position.y) - (target.position.y < context.actor.position.y)
                if (
                    not in_bounds(destination, context.state.map_width, context.state.map_height)
                    or grid_distance_feet(target.position, destination) != 5
                    or destination != Position(target.position.x + away_x, target.position.y + away_y)
                    or self._occupant_at(context.state, destination, except_actor=target.actor_id) is not None
                ):
                    return FamilyProcedureResult(rejection="Brutish Shove needs an open adjacent destination directly away from the Fighter.")
        parent = ActionContinuation(
            kind=kind,
            actor_id=context.actor.actor_id,
            target_id=command.target_id,
            attack_id=command.attack_id,
            path=(
                (command.shove_destination,)
                if isinstance(command, BrutishShove) and command.shove_destination is not None
                else ()
            ),
            mode=("failure_effect" if isinstance(command, BrutishShove) and command.failure_effect else ("follow" if isinstance(command, BrutishShove) and command.follow else None)),
        )
        events = self._start_strike(
            context.state, context.dice, context.actor,
            command.target_id, command.attack_id, command.item_id,
            command.damage_type, command.nonlethal,
            actions_cost=2 if kind == "intimidating_strike" else 1, attack_count_cost=1, vicious_swing=False,
            melee_required=True,
            parent=parent,
        )
        return FamilyProcedureResult(events=tuple(events))

    @staticmethod
    def _committed_rider_parent(continuation):
        """Find a Fighter rider through a temporary Justice reaction wrapper."""
        current = continuation
        while current is not None:
            if current.kind in {"intimidating_strike", "snagging_strike", "combat_grab", "brutish_shove"}:
                return current
            current = current.parent_continuation
        return None

    def _apply_committed_strike_rider(
        self, state, dice, actor, target, continuation, *, damage: int, critical: bool, hit: bool,
    ) -> list[Event]:
        """Resolve the admitted Fighter result rider after the Strike is final."""
        from .fighter import apply_committed_strike_rider_for_kind

        parent = self._committed_rider_parent(continuation)
        if parent is None:
            return []
        if parent.kind != "brutish_shove" and not hit:
            return []
        if parent.kind == "brutish_shove" and not hit and critical:
            return []
        if parent.kind == "brutish_shove" and hit and parent.mode != "failure_effect":
            sizes = {"tiny": 0, "small": 1, "medium": 2, "large": 3, "huge": 4, "gargantuan": 5}
            if sizes.get(get_definition(target.definition_id).size, 99) > sizes.get(get_definition(actor.definition_id).size, -1):
                return [Event(
                    "brutish_shove_size", actor.actor_id, target.actor_id,
                    f"{target.label} is larger than {actor.label}, so Brutish Shove has no hit rider.",
                )]
        context = FamilyProcedureContext(
            self, state, dice, actor, get_definition(actor.definition_id), "martial"
        )
        events = list(apply_committed_strike_rider_for_kind(
            context, kind=parent.kind, target_id=target.actor_id, damage=damage,
            critical=critical, hit=hit,
        ))
        if parent.kind != "brutish_shove" or not hit or parent.mode == "failure_effect":
            return events
        if not parent.path:
            events.append(Event(
                "brutish_shove_not_used", actor.actor_id, target.actor_id,
                f"{actor.label} does not use Brutish Shove's optional automatic Shove.",
            ))
            return events
        origin, destination = target.position, parent.path[0]
        away_x = (origin.x > actor.position.x) - (origin.x < actor.position.x)
        away_y = (origin.y > actor.position.y) - (origin.y < actor.position.y)
        if (
            grid_distance_feet(origin, destination) != 5
            or destination != Position(origin.x + away_x, origin.y + away_y)
            or self._occupant_at(
            state, destination, except_actor=target.actor_id
            ) is not None
        ):
            events.append(Event("brutish_shove_blocked", actor.actor_id, target.actor_id, "Brutish Shove's chosen destination is no longer open."))
            return events
        dx, dy = destination.x - origin.x, destination.y - origin.y
        target.position = destination
        if critical:
            second = Position(destination.x + dx, destination.y + dy)
            if in_bounds(second, state.map_width, state.map_height) and self._occupant_at(
                state, second, except_actor=target.actor_id
            ) is None:
                target.position = second
        events.append(Event(
            "brutish_shove", actor.actor_id, target.actor_id,
            f"{actor.label}'s Brutish Shove moves {target.label} from {_coord(origin)} to {_coord(target.position)} without triggering reactions.",
            position=target.position,
        ))
        if parent.mode == "follow":
            follow_steps = 2 if target.position != destination else 1
            follow = Position(actor.position.x + dx * follow_steps, actor.position.y + dy * follow_steps)
            if self._occupant_at(state, follow, except_actor=actor.actor_id) is None:
                actor.position = follow
                events.append(Event("brutish_shove_follow", actor.actor_id, target.actor_id, f"{actor.label} follows the Shoved target without triggering reactions.", position=follow))
        return events

    def _start_strike(self, state, dice, actor, target_id, attack_id, item_id, damage_type, nonlethal, *, actions_cost, attack_count_cost, vicious_swing, melee_required=False, use_intelligence=None, finisher=False, parent=None, bomber_only_primary_splash=False, hunter_aim_intent=None, attack_penalty_adjustment=0, target_off_guard_override=None):
        if not isinstance(target_id, str):
            raise _Rejected("Strike target id must be text.")
        if actions_cost > actor.actions_remaining:
            raise _Rejected(f"This activity requires {actions_cost} actions.")
        target = state.creatures.get(target_id)
        if target is None or target.actor_id == actor.actor_id or target.defeated:
            raise _Rejected("Strike target must be an active creature.")
        attack = self._select_attack(state, actor, attack_id, item_id=item_id)
        if attack is None:
            defined_attack = next(
                (
                    item for item in get_definition(actor.definition_id).attacks
                    if item.attack_id == attack_id
                ),
                None,
            )
            if defined_attack is not None:
                if item_id is not None:
                    raise _Rejected(
                        f"Item {item_id!r} is not held and compatible with attack {attack_id!r}."
                    )
                if not self._attack_equipped(state, actor, defined_attack):
                    raise _Rejected(f"Attack {attack_id!r} requires its listed item to be held.")
                raise _Rejected(f"Attack {attack_id!r} is not currently available.")
            raise _Unsupported(f"Attack {attack_id!r} is not supported in S1 or for this creature.")
        if melee_required and "melee" not in attack.traits:
            raise _Rejected("Intimidating Strike requires a melee Strike.")
        if hunter_aim_intent is not None:
            from .ranger import validate_hunter_aim_intent

            if not validate_hunter_aim_intent(
                hunter_aim_intent,
                actor=actor,
                target=target,
                attack=attack,
                actions_cost=actions_cost,
                attack_count_cost=attack_count_cost,
            ):
                raise _Rejected("Hunter's Aim intent is not valid for this Strike.")
        if use_intelligence is not None and type(use_intelligence) is not bool:
            raise _Rejected("Intelligence substitution intent must be true or false.")
        turn_start = state.actor_start_counts.get(actor.actor_id, 0)
        if skill_stratagem_blocks_strike(
            actor,
            target_id=target.actor_id,
            round_number=state.round_number,
            turn_start=turn_start,
        ):
            raise _Rejected("Skill Stratagem prevents Strikes against that target until the start of your next turn.")
        stratagem = stratagem_for_attack(
            actor,
            target_id=target.actor_id,
            round_number=state.round_number,
            turn_start=turn_start,
        )
        if use_intelligence is True and stratagem is None:
            raise _Rejected("Intelligence substitution requires an eligible attack stratagem for this target.")
        if stratagem is not None:
            eligible_intelligence = intelligence_substitution_eligible(attack)
            # Intelligence substitution is an explicit optional choice. A
            # normal Strike command keeps its printed Strength/Dexterity
            # attribute unless the caller supplies ``True``.
            selected_intelligence = bool(use_intelligence)
            if selected_intelligence and not eligible_intelligence:
                raise _Rejected(
                    f"Intelligence substitution is not eligible for {attack.name}; the weapon needs Agile or Finesse."
                )
            if any(
                effect.kind == "sure_strike"
                and effect.source_actor_id == actor.actor_id
                and effect.target_actor_id == actor.actor_id
                and effect.expires_at_world_time is not None
                and effect.expires_at_world_time > state.world_time_seconds
                for effect in state.active_effects
            ):
                raise _Rejected("Devise a Stratagem's fortune attack cannot combine with Sure Strike's fortune effect.")
        else:
            selected_intelligence = False
        self._require_action_permitted(state, actor, "strike", attack.traits)
        distance = grid_distance_feet(actor.position, target.position)
        if finisher:
            from .swashbuckler import is_swashbuckler, precise_strike_damage_term

            if not is_swashbuckler(get_definition(actor.definition_id)):
                raise _Unsupported("Confident Finisher is only admitted for the staged Swashbuckler.")
            if not actor.panache:
                raise _Rejected("Confident Finisher requires Panache.")
            if precise_strike_damage_term(
                get_definition(actor.definition_id), attack, finisher=True, distance_ft=distance
            ) is None:
                raise _Rejected(
                    "Confident Finisher requires an agile or finesse melee Strike, or a Flying Blade thrown Strike in its first range increment."
                )
        if vicious_swing and "melee" not in attack.traits:
            raise _Rejected("Vicious Swing requires a melee Strike.")
        if "melee" not in attack.traits:
            # Ranged attacks provoke Reactive Strike before their roll.
            is_ranged = "ranged" in attack.traits
        else:
            is_ranged = False
        ranged_penalty = 0
        if "ranged" in attack.traits:
            range_increment_ft, max_range_ft = self._effective_ranged_profile(
                state, actor, attack,
            )
            if max_range_ft is None or range_increment_ft is None or range_increment_ft < 1:
                raise _Unsupported("This ranged weapon has no admitted range profile.")
            if distance > max_range_ft:
                raise _Rejected(f"Target is {distance} feet away; maximum range is {max_range_ft} feet.")
            ranged_penalty = -2 * max(0, (distance - 1) // range_increment_ft)
            if actor.hunted_prey is not None and actor.hunted_prey.target_actor_id == target.actor_id:
                from .ranger import hunted_prey_range_penalty

                ranged_penalty = hunted_prey_range_penalty(
                    distance, range_increment_ft, target_is_hunted_prey=True
                )
            if attack.item_id is not None and not self._attack_equipped(state, actor, attack, item_id=item_id):
                raise _Rejected(f"The {attack.name} must be held to use it.")
            free_hands = self._free_hands(state, get_definition(actor.definition_id), actor)
            if free_hands < attack.free_hands_required:
                raise _Rejected(f"The {attack.name} requires {attack.free_hands_required} free hand(s).")
            if attack.ammunition_id is not None and actor.ammunition.get(attack.ammunition_id, 0) < 1:
                raise _Rejected(f"No {attack.ammunition_id} ammunition remains.")
        elif distance > attack.reach_ft:
            raise _Rejected(f"Target is {distance} feet away; this Strike has reach {attack.reach_ft} feet.")
        legal_types = self._attack_damage_types(attack)
        if damage_type is not None and damage_type not in legal_types:
            raise _Rejected(f"{damage_type!r} is not an available damage type for {attack.name}.")
        chosen_type = damage_type or attack.damage_type
        default_nonlethal = "nonlethal" in attack.traits
        chosen_nonlethal = default_nonlethal if nonlethal is None else nonlethal
        if type(chosen_nonlethal) is not bool:
            raise _Rejected("nonlethal intent must be true or false.")
        if actor.must_leave_occupied:
            raise _Rejected("Move out of the occupied ally's space before taking another action.")
        damage_modifier = self._damage_modifier(state, actor, attack)
        minimum_damage = len(attack.damage_dice) + damage_modifier + (1 if vicious_swing else 0)
        if (
            target.health_mode is HealthMode.PC
            and target.hp == 0
            and target.unconscious
            and target.dying == 0
            and minimum_damage > 0
        ):
            raise _Unsupported(
                "A Strike that can deal positive damage to a stabilized 0 HP PC awaits a product ruling and is unsupported."
            )

        if finisher:
            # Panache is lost immediately after performing the Finisher, and
            # the attack-trait lockout lasts through the actor's turn.
            actor.panache = False
            actor.panache_expires_at_end = None
            actor.finisher_used_this_turn = True

        feint_off_guard_applied = self._commit_feint_strike(state, actor, target, attack)
        tumble_behind_off_guard = self._commit_tumble_behind_strike(state, actor, target)
        target_off_guard = (
            target_off_guard_override
            if target_off_guard_override is not None
            else self._attacker_off_guard(
                state,
                actor,
                target,
                attack,
                feint_off_guard=feint_off_guard_applied,
                tumble_behind_off_guard=tumble_behind_off_guard,
            )
        )
        penalty = multiple_attack_penalty(actor.strikes_this_turn, attack.traits)
        penalty += attack_penalty_adjustment
        actor.actions_remaining -= actions_cost
        state.taking_cover.discard(actor.actor_id)
        if not is_ranged:
            actor.strikes_this_turn += attack_count_cost
        if vicious_swing:
            actor.flourish_used_round = state.round_number
        selected_item_id = self._held_attack_item_id(state, actor, attack, item_id=item_id)
        if hunter_aim_intent is not None:
            hunter_aim_intent = replace(hunter_aim_intent, item_id=selected_item_id)
        context = ActionContinuation(
            kind="ranged_strike" if is_ranged else "strike",
            actor_id=actor.actor_id,
            target_id=target.actor_id,
            attack_id=attack.attack_id,
            item_id=selected_item_id,
            damage_type=chosen_type,
            nonlethal=chosen_nonlethal,
            attack_penalty=penalty,
            attack_count=actor.strikes_this_turn + 1 if is_ranged else actor.strikes_this_turn - attack_count_cost + 1,
            attack_actions_cost=actions_cost,
            attack_count_cost=attack_count_cost,
            damage_bonus_dice=1 if vicious_swing else 0,
            vicious_swing=vicious_swing,
            finisher=finisher,
            hunter_aim_intent=hunter_aim_intent,
            movement_kind="ranged" if is_ranged else None,
            ranged_penalty=ranged_penalty,
            feint_off_guard_applied=feint_off_guard_applied,
            attack_target_off_guard=target_off_guard,
            use_intelligence=selected_intelligence,
            parent_continuation=parent,
            bomber_only_primary_splash=bomber_only_primary_splash,
        )
        if is_ranged:
            return [Event("strike_started", actor.actor_id, target.actor_id, f"{actor.label} commits to a ranged Strike.")] + self._advance_continuation(state, dice, context)
        events = self._roll_strike(state, dice, actor, target, attack, context, parent=parent)
        if finisher:
            return [Event(
                "confident_finisher_started",
                actor.actor_id,
                target.actor_id,
                f"{actor.label} spends Panache on Confident Finisher; no further attack actions are available this turn.",
            ), *events]
        return events

    def _resolve_subordinate_strike(self, context, paired):
        """Run one already-paid Flurry/Hunted Shot subordinate Strike.

        The ordinary Strike pipeline owns MAP, reactions, Hero choices, Shield
        Block, Justice, and health.  The small parent continuation returns here
        only after that pipeline has completely settled this one Strike.
        """
        from .model import ActionContinuation, FamilyProcedureResult

        if paired.owner_actor_id != context.actor.actor_id or paired.next_index not in (0, 1):
            return FamilyProcedureResult(rejection="The paired Strike continuation is inconsistent.")
        if len(paired.selections) != paired.next_index + 1 or len(paired.outcomes) != paired.next_index:
            return FamilyProcedureResult(rejection="The paired Strike stage is inconsistent.")
        selection = paired.selections[paired.next_index]
        if paired.activity_id == "fighter:double_slice" and paired.next_index == 1:
            # Double Slice makes both one-handed Strikes at the same current
            # MAP, then counts as two attacks for later actions.
            context.actor.strikes_this_turn = paired.initial_attack_count
        selected_attack = next(
            attack for attack in get_definition(context.actor.definition_id).attacks
            if attack.attack_id == selection.attack_id
        )
        parent = ActionContinuation(
            kind="paired_strike",
            actor_id=context.actor.actor_id,
            paired_strike=paired,
        )
        events = self._start_strike(
            context.state, context.dice, context.actor,
            selection.target_id, selection.attack_id, None,
            selection.damage_type, selection.nonlethal,
            actions_cost=0, attack_count_cost=1, vicious_swing=False,
            attack_penalty_adjustment=(
                -2
                if paired.activity_id == "fighter:double_slice"
                and paired.next_index == 1
                and "agile" not in selected_attack.traits
                else 0
            ),
            target_off_guard_override=(
                True
                if paired.activity_id == "rogue:twin_feint" and paired.next_index == 1
                else None
            ),
            parent=parent,
        )
        return FamilyProcedureResult(events=tuple(events))

    @staticmethod
    def _paired_parent(continuation):
        """Find the paired parent through a triggering Justice wrapper."""
        current = continuation
        while current is not None:
            if current.kind == "paired_strike":
                return current
            current = current.parent_continuation
        return None

    def _record_paired_outcome(self, continuation, *, check, damage, damage_type, nonlethal, hit):
        parent = self._paired_parent(continuation)
        if parent is None or parent.paired_strike is None:
            return
        paired = parent.paired_strike
        if len(paired.outcomes) != paired.next_index or paired.next_index >= len(paired.selections):
            raise _Rejected("The paired Strike outcome is inconsistent.")
        selection = paired.selections[paired.next_index]
        parent.paired_strike = replace(
            paired,
            outcomes=(*paired.outcomes, PairedStrikeOutcome(
                selection.target_id, selection.attack_id, check, damage,
                damage_type,
                nonlethal, hit,
            )),
            stage="first_resolved" if paired.next_index == 0 else "second_resolved",
        )

    def _roll_strike(self, state, dice, actor, target, attack, context, *, parent):
        # Concealment is an independent targeting gate.  Resolve it before
        # Guidance or any later attack roll/fortune choice so a failed flat
        # check spends the already committed action/MAP but consumes no
        # attack-only modifier or die.  Ranged Reactive Strike windows have
        # already completed before this continuation reaches here.
        if not context.sure_strike_checked:
            self._consume_sure_strike_for_attack(state, actor, context)
        if context.sure_strike_used:
            context.concealment_checked = True
        if context.hunter_aim_intent is not None:
            context.concealment_checked = True
        if not context.concealment_checked:
            context.parent_continuation = parent
            context.concealment_checked = True
            if self.target_is_concealed(actor.actor_id, target.actor_id):
                check = resolve_check(dice.draw(20), 0, 5)
                events = [Event(
                    "concealment_flat_check",
                    actor.actor_id,
                    target.actor_id,
                    f"{actor.label} attempts the DC 5 concealment flat check against {target.label}: "
                    f"d20 {check.die}; {check.degree.label().lower()}.",
                    check=check,
                )]
                if actor.health_mode is HealthMode.PC and actor.hero_points > 0:
                    self._set_pending(
                        state,
                        kind="concealment_hero_reroll",
                        owner_actor_id=actor.actor_id,
                        prompt=(
                            f"{actor.label} may keep the concealment flat check or spend 1 Hero Point "
                            "to reroll it."
                        ),
                        options=(
                            ChoiceOption("keep", "Keep result"),
                            ChoiceOption("spend_hero_point", "Spend 1 Hero Point and reroll"),
                        ),
                        details=(f"Original flat check: d20 {check.die} vs DC 5.",),
                        actor_id=actor.actor_id,
                        target_id=target.actor_id,
                        attack_id=attack.attack_id,
                        item_id=context.item_id,
                        attack_penalty=context.attack_penalty,
                        attack_count=context.attack_count,
                        check=check,
                        check_kind="concealment",
                        damage_type=context.damage_type,
                        nonlethal=context.nonlethal,
                        damage_bonus_dice=context.damage_bonus_dice,
                        attack_actions_cost=context.attack_actions_cost,
                        attack_count_cost=context.attack_count_cost,
                        ranged_penalty=context.ranged_penalty,
                        guidance_bonus=context.guidance_bonus,
                        feint_off_guard_applied=context.feint_off_guard_applied,
                        attack_target_off_guard=context.attack_target_off_guard,
                        nimble_dodge_used=context.nimble_dodge_used,
                        is_reaction=context.kind == "reaction_strike",
                        concealment_checked=True,
                        continuation=context,
                    )
                    return events
                return events + self._finish_concealment_check(
                    state, dice, actor, target, attack, context, check
                )
        if not context.guidance_checked:
            effect = self._guidance_for(state, actor.actor_id)
            if effect is not None:
                context.guidance_checked = True
                self._offer_guidance(state, actor, context, effect, check_kind="weapon_attack", parent=parent)
                return [Event("guidance_choice", effect.source_actor_id, actor.actor_id, f"{actor.label} may use Guidance before this attack roll.")]
        if not context.nimble_dodge_decided and self._nimble_dodge_available(state, actor, target):
            context.parent_continuation = parent
            self._present_nimble_dodge(state, actor, target, context)
            return [Event(
                "nimble_dodge_choice",
                target.actor_id,
                actor.actor_id,
                f"{target.label} may use Nimble Dodge before {actor.label}'s attack roll.",
            )]
        if context.overextending_feint_penalty == 0:
            from .skill_actions import overextending_feint_penalty

            context.overextending_feint_penalty = overextending_feint_penalty(
                tuple(state.overextending_feint_effects),
                attacker_id=actor.actor_id,
                target_id=target.actor_id,
                actor_end_counts=state.actor_end_counts,
            )
        stratagem_roll = consume_stratagem(
            actor,
            target_id=target.actor_id,
            round_number=state.round_number,
            turn_start=state.actor_start_counts.get(actor.actor_id, 0),
        )
        if context.use_intelligence and stratagem_roll is None:
            raise _Rejected("The Investigator's stored attack stratagem is no longer available for this Strike.")
        weakness_bonus = self._consume_investigator_weakness_bonus(
            state,
            actor,
            target,
            stratagem_used=stratagem_roll is not None,
        )
        intelligence_adjustment = 0
        if stratagem_roll is not None and context.use_intelligence:
            ability_modifiers = dict(get_definition(actor.definition_id).ability_modifiers)
            intelligence_adjustment = ability_modifiers.get("intelligence", 0) - ability_modifiers.get(
                attack.attack_attribute, 0
            )
        modifiers = _strike_modifier_breakdown_full(
            attack,
            context.attack_penalty,
            context.nonlethal,
            actor.prone and not actor.unconscious,
            ranged_penalty=context.ranged_penalty,
            guidance_bonus=context.guidance_bonus,
            enfeebled=(
                self._enfeebled_value(state, actor.actor_id)
                if attack.attack_attribute == "strength" and not context.use_intelligence
                else 0
            ),
            attack_modifier_adjustment=intelligence_adjustment,
            lethal_penalty_exempt=self._powerful_fist_lethal_penalty_exempt(
                actor, attack, context.nonlethal
            ),
        )
        item_modifier = self._attack_item_potency_modifier(
            state, actor, attack, item_id=context.item_id
        )
        if item_modifier is not None:
            modifiers = (*modifiers, item_modifier)
        if self._weapon_surge_applies(state, actor, attack, context.item_id):
            modifiers = (*modifiers, Modifier(1, "status", "Weapon Surge"))
        if context.hunter_aim_intent is not None:
            from .ranger import hunter_aim_attack_bonus

            modifiers = (*modifiers, Modifier(
                hunter_aim_attack_bonus(context.hunter_aim_intent),
                "circumstance",
                "Hunter's Aim",
            ))
        modifiers = (*modifiers, *self._strike_condition_modifiers(state, actor, attack), *self._mutagen_modifiers(state, actor, "attack", attack_traits=attack.traits))
        if weakness_bonus is not None:
            modifiers = (*modifiers, weakness_bonus)
        if context.sure_strike_used:
            modifiers = self._sure_strike_attack_modifiers(modifiers)
        if context.overextending_feint_penalty:
            modifiers = (*modifiers, Modifier(
                context.overextending_feint_penalty,
                "circumstance",
                "Overextending Feint",
            ))
        modifier = combine_modifiers(modifiers)
        dc = self._attack_dc(
            state, actor, target, attack,
            feint_off_guard=context.feint_off_guard_applied,
            target_off_guard=context.attack_target_off_guard,
            nimble_dodge=context.nimble_dodge_used,
            hunter_aim_intent=context.hunter_aim_intent,
        )
        if stratagem_roll is not None:
            stored_die, consumed_state = stratagem_roll
            check = replace(resolve_stratagem_check(
                consumed_state,
                modifier=modifier,
                dc=dc,
                attack_id=attack.attack_id,
                attack_count=max(1, context.attack_count),
                map_penalty=context.attack_penalty,
                traits=frozenset(attack.traits),
            ), modifier_breakdown=tuple(modifiers), dice=(stored_die,))
        else:
            rolled_dice = (
                (dice.draw(20), dice.draw(20))
                if context.sure_strike_used else (dice.draw(20),)
            )
            die = max(rolled_dice)
            check = replace(resolve_check(
                die,
                modifier,
                dc,
                attack_id=attack.attack_id,
                attack_count=max(1, context.attack_count),
                map_penalty=context.attack_penalty,
                traits=attack.traits,
            ), modifier_breakdown=tuple(modifiers), dice=rolled_dice)
        if actor.health_mode is HealthMode.PC and actor.hero_points > 0 and not context.sure_strike_used and stratagem_roll is None:
            self._set_pending(
                state,
                kind="attack_hero_reroll",
                owner_actor_id=actor.actor_id,
                prompt=f"{actor.label} may keep this Strike check or spend 1 Hero Point to reroll it.",
                options=(ChoiceOption("keep", "Keep result"), ChoiceOption("spend_hero_point", "Spend 1 Hero Point and reroll")),
                details=(
                    f"Original: d20 {check.die} + {check.modifier} = {check.total} vs AC {check.dc}.",
                    f"Degree: {check.degree.label()}.",
                ),
                actor_id=actor.actor_id,
                target_id=target.actor_id,
                attack_id=attack.attack_id,
                item_id=context.item_id,
                attack_penalty=context.attack_penalty,
                attack_count=context.attack_count,
                check=check,
                damage_type=context.damage_type,
                nonlethal=context.nonlethal,
                damage_bonus_dice=context.damage_bonus_dice,
                attack_actions_cost=context.attack_actions_cost,
                attack_count_cost=context.attack_count_cost,
                ranged_penalty=context.ranged_penalty,
                guidance_bonus=context.guidance_bonus,
                feint_off_guard_applied=context.feint_off_guard_applied,
                attack_target_off_guard=context.attack_target_off_guard,
                nimble_dodge_used=context.nimble_dodge_used,
                is_reaction=context.kind == "reaction_strike",
                concealment_checked=context.concealment_checked,
                damage_context=("bomber_only_primary" if context.bomber_only_primary_splash else None),
                continuation=(
                    context
                    if context.finisher or context.hunter_aim_intent is not None
                    else parent
                ),
            )
            return [self._attack_event(actor, target, check)]
        if context.overextending_feint_penalty:
            from .skill_actions import consume_overextending_feint_on_attack

            state.overextending_feint_effects = list(consume_overextending_feint_on_attack(
                tuple(state.overextending_feint_effects),
                attacker_id=actor.actor_id,
                target_id=target.actor_id,
                actor_end_counts=state.actor_end_counts,
            ))
        return self._resolve_attack_result(
            state, dice, actor, target, attack, check,
            damage_type=context.damage_type or attack.damage_type,
            nonlethal=context.nonlethal,
            damage_bonus_dice=context.damage_bonus_dice,
            attack_target_off_guard=context.attack_target_off_guard,
            is_reaction=context.kind == "reaction_strike",
            continuation=context if context.finisher else parent,
            item_id=context.item_id,
            investigator_strategic_strike=bool(stratagem_roll is not None and context.use_intelligence),
            investigator_use_intelligence=bool(stratagem_roll is not None and context.use_intelligence),
            bomber_only_primary_splash=context.bomber_only_primary_splash,
        )

    @staticmethod
    def _powerful_fist_lethal_penalty_exempt(actor, attack, nonlethal: bool) -> bool:
        """Apply Powerful Fist only to a lethal unarmed Strike's normal penalty."""
        from .monk import powerful_fist_removes_lethal_penalty

        return powerful_fist_removes_lethal_penalty(
            get_definition(actor.definition_id).abilities, attack, nonlethal=nonlethal
        )

    def _finish_concealment_check(
        self, state, dice, actor, target, attack, context, check
    ) -> list[Event]:
        """Finish one saved DC 5 gate without entering attack resolution."""
        if check.degree < DegreeOfSuccess.SUCCESS:
            events = [Event(
                "concealment_failed",
                actor.actor_id,
                target.actor_id,
                f"{actor.label} fails the concealment flat check; no attack roll is attempted.",
                check=check,
            )]
            if context.kind == "reaction_strike":
                parent = context.parent_continuation
                if parent is not None:
                    events.extend(self._resume_continuation(state, dice, parent, critical=False))
                return events
            return self._complete_action(state, actor, events, dice=dice)
        events = [Event(
            "concealment_passed",
            actor.actor_id,
            target.actor_id,
            f"{actor.label} passes the concealment flat check; the attack may proceed.",
            check=check,
        )]
        events.extend(self._roll_strike(state, dice, actor, target, attack, context, parent=context.parent_continuation))
        return events

    def _attack_event(self, actor: CreatureState, target: CreatureState, check) -> Event:
        degree_text = check.degree.label().lower()
        dice_text = ", ".join(str(face) for face in check.dice) if check.dice else str(check.die)
        attack_text = f"Attack: d20 {dice_text} + {check.modifier} = {check.total} vs AC {check.dc}; {degree_text}."
        if check.map_penalty:
            attack_text = attack_text[:-1] + f" (MAP {check.map_penalty})."
        return Event("strike", actor.actor_id, target.actor_id, attack_text, check=check)

    def _resolve_attack_result(
        self, state, dice, actor, target, attack, check, *, damage_type=None,
        nonlethal=False, damage_bonus_dice=0, is_reaction=False, continuation=None,
        attack_target_off_guard=False, item_id=None,
        investigator_strategic_strike=False, investigator_use_intelligence=False,
        bomber_only_primary_splash=False,
    ) -> list[Event]:
        events = [self._attack_event(actor, target, check)]
        weapon_surge = self._weapon_surge_applies(state, actor, attack, item_id)
        finisher = bool(continuation is not None and continuation.finisher)
        if check.degree not in (DegreeOfSuccess.SUCCESS, DegreeOfSuccess.CRITICAL_SUCCESS):
            if weapon_surge:
                self._consume_weapon_surge(state, actor)
            if (
                check.degree is DegreeOfSuccess.CRITICAL_FAILURE
                and attack.attack_id == "dagger"
                and (damage_type or attack.damage_type) in {"piercing", "slashing"}
            ):
                state.active_effects[:] = [
                    effect for effect in state.active_effects
                    if not (effect.kind == "alchemy_giant_centipede_venom_coating" and effect.target_actor_id == actor.actor_id)
                ]
                events.append(Event("venom_wasted", actor.actor_id, target.actor_id, "The critically failed injury Strike wastes Giant Centipede Venom."))
            if finisher and check.degree is not DegreeOfSuccess.CRITICAL_FAILURE:
                from .swashbuckler import confident_finisher_failure_damage

                precision = roll_damage_terms(
                    (
                        DamageTerm(
                            source="swashbuckler_precise_strike",
                            damage_type="precision",
                            dice=(6, 6),
                            tags=frozenset({"precision"}),
                        ),
                    ),
                    dice.draw,
                )
                damage = confident_finisher_failure_damage(
                    precision, damage_type or attack.damage_type
                )
                resolution = DamageResolution(
                    source_kind="strike",
                    group=DamageGroup(
                        f"finisher:{actor.actor_id}:{target.actor_id}:{state.next_choice_id}",
                        (damage,),
                        "strike",
                        attack.traits,
                    ),
                    actor_id=actor.actor_id,
                    target_id=target.actor_id,
                    source="confident_finisher_failure",
                    damage_type=damage_type or attack.damage_type,
                    check=check,
                    attack_id=attack.attack_id,
                    nonlethal=nonlethal,
                    attacker_critical=False,
                    attack_target_off_guard=attack_target_off_guard,
                    is_reaction=is_reaction,
                    continuation=continuation,
                )
                events.append(Event(
                    "confident_finisher_failure",
                    actor.actor_id,
                    target.actor_id,
                    f"{actor.label}'s Confident Finisher fails; it deals half the rolled 2d6 precise-strike damage.",
                    check=check,
                    damage=damage,
                ))
                landing = self._land_thrown_item(state, actor, target, attack, item_id)
                if landing is not None:
                    events.append(landing)
                events.extend(self._resolve_damage_to_health(state, dice, resolution, resumed=False))
                return events
            landing = self._land_thrown_item(state, actor, target, attack, item_id)
            if landing is not None:
                events.append(landing)
            bomb_facts = self._admitted_bomber_bomb_facts(
                attack.item_id,
                character_level=get_definition(actor.definition_id).level,
            )
            if (
                check.degree is DegreeOfSuccess.FAILURE
                and bomb_facts is not None
                and bomb_facts.splash_damage
            ):
                events.extend(self._apply_bomber_miss_primary_splash(
                    state, dice, actor, target, attack, bomb_facts, item_id=item_id
                ))
                if state.pending_choice is not None:
                    raise _Unsupported("A bomb splash that pauses for a defense choice after a miss is not yet admitted.")
            if continuation is not None:
                events.extend(self._apply_committed_strike_rider(
                    state, dice, actor, target, continuation, damage=0,
                    critical=check.degree is DegreeOfSuccess.CRITICAL_FAILURE, hit=False,
                ))
                if not is_reaction:
                    self._record_paired_outcome(
                        continuation,
                        check=check,
                        damage=None,
                        damage_type=damage_type or attack.damage_type,
                        nonlethal=nonlethal,
                        hit=False,
                    )
                if check.degree is DegreeOfSuccess.FAILURE:
                    current = continuation
                    while current is not None and current.kind != "exacting_strike":
                        current = current.parent_continuation
                    if current is not None and actor.strikes_this_turn > 0:
                        actor.strikes_this_turn -= 1
                        events.append(Event(
                            "exacting_strike_exact", actor.actor_id, target.actor_id,
                            f"{actor.label}'s Exacting Strike misses without increasing its multiple attack penalty.",
                        ))
                events.extend(self._resume_continuation(
                    state, dice, continuation,
                    critical=check.degree is DegreeOfSuccess.CRITICAL_FAILURE,
                ))
            elif (
                not is_reaction
                and state.in_progress
                and actor.actions_remaining == 0
                and not self._free_devise_target_ids(state, actor)
            ):
                events.extend(self._end_turn(state, actor, early=False, dice=dice))
            return events

        if (
            check.degree in {DegreeOfSuccess.SUCCESS, DegreeOfSuccess.CRITICAL_SUCCESS}
            and not is_reaction
            and not (continuation is not None and continuation.reactive_shield_decided)
            and "melee" in attack.traits
            and "ranged" not in attack.traits
            and self._reactive_shield_available(state, actor, target)
        ):
            self._present_reactive_shield_after_hit(
                state, actor, target, attack, check,
                damage_type=damage_type or attack.damage_type,
                nonlethal=nonlethal,
                damage_bonus_dice=damage_bonus_dice,
                attack_target_off_guard=attack_target_off_guard,
                item_id=item_id,
                investigator_strategic_strike=investigator_strategic_strike,
                investigator_use_intelligence=investigator_use_intelligence,
                bomber_only_primary_splash=bomber_only_primary_splash,
                parent_continuation=continuation,
            )
            events.append(Event(
                "reactive_shield_choice",
                target.actor_id,
                actor.actor_id,
                f"{target.label} was hit by {actor.label}'s melee Strike and may use Reactive Shield.",
                check=check,
            ))
            return events

        pack_bonus = 1 if "pack_attack" in get_definition(actor.definition_id).abilities and self._pack_attack_applies(state, actor, target) else 0
        bonus_dice = damage_bonus_dice + pack_bonus
        damage = self._roll_attack_damage(
            state, dice, actor, target.actor_id, attack, damage_type or attack.damage_type,
            critical=check.degree is DegreeOfSuccess.CRITICAL_SUCCESS,
            bonus_dice=bonus_dice,
            target_is_off_guard=attack_target_off_guard,
            item_id=item_id,
            strategic_strike=investigator_strategic_strike,
            use_intelligence=investigator_use_intelligence,
            finisher=finisher,
            weapon_surge=weapon_surge,
        )
        if weapon_surge:
            self._consume_weapon_surge(state, actor)
        bomb_facts = self._admitted_bomber_bomb_facts(
            attack.item_id,
            character_level=get_definition(actor.definition_id).level,
        )
        if bomb_facts is not None and bomb_facts.splash_damage:
            damage = self._bomb_damage_with_primary_splash(damage, attack.attack_id, bomb_facts)
        resolution = DamageResolution(
            source_kind="strike",
            group=DamageGroup(
                f"strike:{actor.actor_id}:{target.actor_id}:{state.next_choice_id}",
                (damage,),
                "strike",
                attack.traits,
            ),
            actor_id=actor.actor_id,
            target_id=target.actor_id,
            source=attack.attack_id,
            damage_type=damage_type or attack.damage_type,
            check=check,
            attack_id=attack.attack_id,
            nonlethal=nonlethal,
            attacker_critical=check.degree is DegreeOfSuccess.CRITICAL_SUCCESS,
            attack_target_off_guard=attack_target_off_guard,
            damage_bonus_dice=bonus_dice,
            is_reaction=is_reaction,
            continuation=continuation,
            bomber_only_primary_splash=bomber_only_primary_splash,
            item_id=item_id,
        )
        if continuation is not None and continuation.kind == "exacting_strike" and not is_reaction:
            self._set_pending(
                state,
                kind="family_action",
                owner_actor_id=actor.actor_id,
                prompt=(
                    f"{actor.label} succeeded with Exacting Strike; choose the hit or its Press failure effect."
                ),
                options=(
                    ChoiceOption("full_hit", "Apply the successful Strike"),
                    ChoiceOption("failure_effect", "Use the Press failure effect (no damage; no MAP)"),
                ),
                details=(
                    f"Successful result: d20 {check.die} + {check.modifier} = {check.total} vs AC {check.dc}.",
                    "The Press trait allows a successful action to use its failure effect instead.",
                ),
                actor_id=actor.actor_id,
                target_id=target.actor_id,
                attack_id=attack.attack_id,
                item_id=item_id,
                attack_penalty=check.map_penalty,
                attack_count=check.attack_count,
                check=check,
                damage_result=damage,
                damage_type=damage_type or attack.damage_type,
                nonlethal=nonlethal,
                attack_critical=check.degree is DegreeOfSuccess.CRITICAL_SUCCESS,
                attack_actions_cost=1,
                attack_count_cost=1,
                continuation=continuation,
                family_id="martial",
                procedure_id="w4_offensive:exacting_strike",
                damage_resolution=resolution,
            )
            events.append(Event(
                "exacting_strike_press_choice", actor.actor_id, target.actor_id,
                f"{actor.label}'s Exacting Strike succeeds; choose the hit or Press failure effect.",
                check=check, damage=damage,
            ))
            return events
        if finisher:
            from .swashbuckler import ConfidentFinisher

            self._set_pending(
                state,
                kind="family_action",
                owner_actor_id=actor.actor_id,
                prompt=(
                    f"{actor.label}'s Confident Finisher succeeded; choose full damage "
                    "or its failure effect."
                ),
                options=(
                    ChoiceOption("full_damage", "Apply full Strike damage"),
                    ChoiceOption("failure_effect", "Use the failure effect (half precise-strike damage)"),
                ),
                details=(
                    f"Full result: {damage.total} damage before defenses.",
                    "The failure effect deals half the rolled 2d6 precision damage as the weapon's damage type.",
                ),
                actor_id=actor.actor_id,
                target_id=target.actor_id,
                attack_id=attack.attack_id,
                item_id=item_id,
                attack_penalty=continuation.attack_penalty if continuation is not None else 0,
                attack_count=continuation.attack_count if continuation is not None else 0,
                check=check,
                damage_result=damage,
                damage_type=damage_type or attack.damage_type,
                nonlethal=nonlethal,
                attack_critical=check.degree is DegreeOfSuccess.CRITICAL_SUCCESS,
                attack_actions_cost=continuation.attack_actions_cost if continuation is not None else 1,
                attack_count_cost=continuation.attack_count_cost if continuation is not None else 1,
                continuation=continuation,
                family_id="martial",
                procedure_id="swashbuckler:confident_finisher:damage",
                damage_resolution=resolution,
                family_command=ConfidentFinisher(
                    target.actor_id,
                    attack.attack_id,
                    damage_type or attack.damage_type,
                    nonlethal,
                    item_id,
                ),
            )
            events.append(Event(
                "confident_finisher_success",
                actor.actor_id,
                target.actor_id,
                f"{actor.label}'s Confident Finisher succeeds; choose full or failure-effect damage.",
                check=check,
                damage=damage,
            ))
            landing = self._land_thrown_item(state, actor, target, attack, item_id)
            if landing is not None:
                events.append(landing)
            return events
        landing = self._land_thrown_item(state, actor, target, attack, item_id)
        if landing is not None:
            events.append(landing)
        events.extend(self._resolve_damage_to_health(state, dice, resolution, resumed=False))
        if (
            check.degree in {DegreeOfSuccess.SUCCESS, DegreeOfSuccess.CRITICAL_SUCCESS}
            and attack.attack_id == "dagger"
            and (damage_type or attack.damage_type) in {"piercing", "slashing"}
        ):
            events.extend(self._resolve_giant_centipede_venom_exposure(state, dice, actor, target))
        return events

    def _resolve_giant_centipede_venom_exposure(self, state, dice, actor, target):
        coating = next((effect for effect in state.active_effects if effect.kind == "alchemy_giant_centipede_venom_coating" and effect.target_actor_id == actor.actor_id and effect.expires_at_world_time is not None and effect.expires_at_world_time > state.world_time_seconds), None)
        if coating is None or "poison" in getattr(get_definition(target.definition_id), "condition_immunities", ()):
            return []
        state.active_effects.remove(coating)
        base = dict((name, modifier) for name, _rank, modifier in get_definition(target.definition_id).saves).get("fortitude")
        if base is None:
            raise _Unsupported("Giant Centipede Venom needs an admitted Fortitude save.")
        modifiers = (Modifier(base, "untyped", "printed Fortitude save"), *self._resilient_save_modifiers(state, target), *self._alchemy_save_modifiers(state, target, "fortitude", against="poison"), *self._mutagen_modifiers(state, target, "fortitude"), *condition_modifiers(self._conditions_for_actor(state, target), CheckContext("fortitude", "constitution", frozenset({"poison"}))))
        check = replace(resolve_check(dice.draw(20), combine_modifiers(modifiers), 17), modifier_breakdown=tuple(modifiers))
        events = [Event("venom_fortitude_save", actor.actor_id, target.actor_id, _spell_save_text(target, check, statistic="Fortitude"), check=check)]
        if check.degree in {DegreeOfSuccess.FAILURE, DegreeOfSuccess.CRITICAL_FAILURE}:
            increase = 2 if check.degree is DegreeOfSuccess.CRITICAL_FAILURE else 1
            existing = next((effect for effect in state.giant_centipede_venom_afflictions if effect.target_actor_id == target.actor_id), None)
            if existing is None:
                affliction = GiantCentipedeVenomAffliction(
                    f"venom:{actor.actor_id}:{target.actor_id}:{state.next_choice_id}",
                    actor.actor_id, target.actor_id, 17, increase,
                    state.world_time_seconds + 36,
                    state.actor_end_counts.get(target.actor_id, 0) + 1,
                )
                state.giant_centipede_venom_afflictions.append(affliction)
            else:
                # A later failed poison exposure advances the existing
                # affliction without replacing its original maximum duration.
                affliction = replace(existing, stage=min(3, existing.stage + increase))
                state.giant_centipede_venom_afflictions[
                    state.giant_centipede_venom_afflictions.index(existing)
                ] = affliction
            events.extend(self._apply_giant_centipede_venom_stage(
                state, dice, affliction,
            ))
            events.append(Event("venom_stage", actor.actor_id, target.actor_id, f"{target.label} enters Giant Centipede Venom stage {affliction.stage}.", check=check))
        return events

    def _apply_giant_centipede_venom_stage(self, state, dice, affliction, *, end_turn=False):
        """Apply the selected poison's current stage immediately on reaching it."""
        from .alchemy_content import FORMULAS_BY_ID

        target = state.creatures[affliction.target_actor_id]
        stage = FORMULAS_BY_ID["giant_centipede_venom"].facts.stages[affliction.stage - 1]
        raw = roll_damage_terms((DamageTerm(
            f"venom:{affliction.effect_id}:stage:{affliction.stage}", "poison",
            stage.damage_dice,
        ),), dice.draw)
        resolution = DamageResolution(
            "family", DamageGroup(affliction.effect_id, (raw,), "family", frozenset({"poison"})),
            affliction.source_actor_id, target.actor_id, "Giant Centipede Venom", "poison",
            continuation=(ActionContinuation(kind="venom_end_turn", actor_id=target.actor_id) if end_turn else None),
        )
        events = [Event(
            "venom_stage_effect", affliction.source_actor_id, target.actor_id,
            f"{target.label} suffers Giant Centipede Venom stage {affliction.stage}.", damage=raw,
        )]
        return events + self._resolve_damage_to_health(state, dice, resolution, resumed=False)

    def _resolve_giant_centipede_venom_end_turn(self, state, dice, actor):
        """Advance only the selected poison at the end of its target's stage."""
        state.giant_centipede_venom_afflictions[:] = [
            effect for effect in state.giant_centipede_venom_afflictions
            if effect.expires_at_world_time > state.world_time_seconds
            and not state.creatures[effect.target_actor_id].dead
        ]
        effects = tuple(
            effect for effect in state.giant_centipede_venom_afflictions
            if effect.target_actor_id == actor.actor_id
            and effect.next_save_at_target_end <= state.actor_end_counts.get(actor.actor_id, 0) + 1
        )
        events = []
        for effect in effects:
            base = dict((name, modifier) for name, _rank, modifier in get_definition(actor.definition_id).saves).get("fortitude")
            if base is None:
                raise _Unsupported("Giant Centipede Venom needs an admitted Fortitude save.")
            modifiers = (Modifier(base, "untyped", "printed Fortitude save"), *self._resilient_save_modifiers(state, actor), *self._alchemy_save_modifiers(state, actor, "fortitude", against="poison"), *self._mutagen_modifiers(state, actor, "fortitude"), *condition_modifiers(self._conditions_for_actor(state, actor), CheckContext("fortitude", "constitution", frozenset({"poison"}))))
            check = replace(resolve_check(dice.draw(20), combine_modifiers(modifiers), effect.dc), modifier_breakdown=tuple(modifiers))
            events.append(Event("venom_fortitude_save", effect.source_actor_id, actor.actor_id, _spell_save_text(actor, check, statistic="Fortitude"), check=check))
            delta = {DegreeOfSuccess.CRITICAL_SUCCESS: -2, DegreeOfSuccess.SUCCESS: -1, DegreeOfSuccess.FAILURE: 1, DegreeOfSuccess.CRITICAL_FAILURE: 2}[check.degree]
            stage = max(0, min(3, effect.stage + delta))
            state.giant_centipede_venom_afflictions.remove(effect)
            if stage == 0:
                events.append(Event("venom_recovered", effect.source_actor_id, actor.actor_id, f"{actor.label} recovers from Giant Centipede Venom.", check=check))
                continue
            advanced = replace(effect, stage=stage, next_save_at_target_end=state.actor_end_counts.get(actor.actor_id, 0) + 2)
            state.giant_centipede_venom_afflictions.append(advanced)
            events.extend(self._apply_giant_centipede_venom_stage(state, dice, advanced, end_turn=True))
            events.append(Event("venom_stage", effect.source_actor_id, actor.actor_id, f"{actor.label} enters Giant Centipede Venom stage {stage}.", check=check))
        return events

    def _land_thrown_item(self, state, actor, target, attack, item_id):
        """Move a resolved thrown weapon into the target cell for recovery.

        This local GM convention applies after the attack roll has resolved,
        whether the attack hit or missed.  It deliberately does not model
        scatter, projectile paths, or returning weapons.
        """

        if not (
            "ranged" in attack.traits
            and "thrown" in attack.traits
            and attack.item_id is not None
        ):
            return None
        if item_id is None or item_id not in self._held_attack_item_ids(state, actor, attack):
            raise ValueError("resolved thrown Strike lacks its held selected item")
        actor.held_items.remove(item_id)
        if "bomb" in attack.traits:
            state.consumed_infused_item_ids.add(item_id)
            # Bombs are consumables, unlike the ordinary thrown weapons this
            # recovery convention preserves.
            return Event(
                "bomb_consumed", actor.actor_id, target.actor_id,
                f"{actor.label}'s {attack.name} is consumed on impact.",
            )
        state.ground_items.setdefault(target.position, []).append(item_id)
        return Event(
            "thrown_item_landed",
            actor.actor_id,
            target.actor_id,
            f"{actor.label}'s {attack.name} lands at {_coord(target.position)} for recovery.",
            position=target.position,
        )

    @staticmethod
    def _weapon_surge_applies(state, actor, attack, item_id) -> bool:
        selected_item = item_id or attack.item_id
        if selected_item is None:
            return False
        return any(
            effect.kind == "weapon_surge"
            and effect.source_actor_id == actor.actor_id
            and effect.effect_id.split(":")[2:3] == [selected_item]
            for effect in state.active_effects
        )

    @staticmethod
    def _consume_weapon_surge(state, actor) -> None:
        state.active_effects[:] = [
            effect for effect in state.active_effects
            if not (effect.kind == "weapon_surge" and effect.source_actor_id == actor.actor_id)
        ]

    def _roll_attack_damage(
        self,
        state,
        dice,
        actor,
        target_id,
        attack,
        damage_type,
        *,
        critical,
        bonus_dice=0,
        target_is_off_guard=False,
        item_id=None,
        strategic_strike=False,
        use_intelligence=False,
        finisher=False,
        weapon_surge=False,
    ):
        modifier = self._damage_modifier(state, actor, attack)
        from .martial_defense import point_blank_stance_damage_bonus

        modifier += point_blank_stance_damage_bonus(
            state, actor, state.creatures[target_id], attack
        )
        weapon_dice = attack.damage_dice
        rune_profile = self._weapon_rune_profile_for_attack(
            state, actor, attack, item_id=item_id
        )
        if rune_profile is not None:
            weapon_dice = weapon_rune_dice(
                attack.damage_dice,
                rune_profile,
                striking_applies=attack.striking_applies,
                unarmed="unarmed" in attack.traits,
            )
        terms = [DamageTerm(
            source=attack.attack_id,
            damage_type=damage_type,
            dice=weapon_dice + ((attack.damage_dice[0],) * bonus_dice if attack.damage_dice else ()),
            modifier=modifier,
            tags=(
                frozenset({"holy"})
                if get_definition(actor.definition_id).spell_sanctification == "holy"
                else frozenset()
            ),
        )]
        if weapon_surge:
            terms.append(DamageTerm(
                source="weapon_surge",
                damage_type="spirit",
                dice=(6,),
                tags=frozenset({"sanctified"}),
            ))
        if strategic_strike:
            term = strategic_strike_damage_term(
                attack,
                used_intelligence=use_intelligence,
                investigator_level=get_definition(actor.definition_id).level,
            )
            if term is not None:
                terms.append(term)
        target = state.creatures[target_id]
        swashbuckler_term = precise_strike_damage_term(
            get_definition(actor.definition_id),
            attack,
            finisher=finisher,
            distance_ft=grid_distance_feet(actor.position, target.position),
        )
        if swashbuckler_term is not None:
            terms.append(swashbuckler_term)
        if "sneak_attack" in get_definition(actor.definition_id).abilities:
            racket = next(
                (
                    value
                    for value in RogueRacket
                    if f"rogue_racket_{value.value}" in get_definition(actor.definition_id).abilities
                ),
                None,
            )
            if racket is not None:
                from .rogue_content import ROGUE_WEAPON_FACTS

                facts = ROGUE_WEAPON_FACTS.get(attack.item_id or "")
                thrown_melee = bool(
                    facts is not None
                    and "ranged" in attack.traits
                    and "thrown" in attack.traits
                    and facts.is_melee_weapon
                )
                sneak = sneak_attack_damage_term(
                    attack,
                    damage_type=damage_type,
                    target_is_off_guard=target_is_off_guard,
                    racket=racket,
                    weapon_category=facts.category if facts is not None else None,
                    adjusted_weapon_die_sides=attack.damage_dice[0] if attack.damage_dice else None,
                    thrown_melee_weapon=thrown_melee,
                )
                if sneak is not None:
                    terms.append(sneak)
        barbarian_state = actor.barbarian_state
        if barbarian_state is not None:
            from .barbarian import rage_strike_adjustment

            adjustment = rage_strike_adjustment(
                barbarian_state,
                attack_id=attack.attack_id,
                attack_damage_type=damage_type,
                attack_traits=attack.traits,
                attack_is_weapon=attack.item_id is not None,
                is_melee="melee" in attack.traits,
                wielded_item_id=attack.item_id,
                target_actor_id=target_id,
                now_seconds=state.world_time_seconds,
            )
            if not adjustment.allowed:
                raise _Rejected(adjustment.rejection or "This attack is prohibited during Rage.")
            if adjustment.damage_term is not None:
                terms.append(adjustment.damage_term)
        if critical and attack.deadly_die is not None:
            terms.append(DamageTerm(
                source=f"{attack.attack_id} deadly",
                damage_type=damage_type,
                dice=(attack.deadly_die,),
                critical_mode="critical_only",
            ))
        if actor.hunted_prey is not None and actor.hunted_prey.target_actor_id == target_id:
            from .ranger import hunter_edge, precision_damage_term

            precision = precision_damage_term(
                hunter_edge(get_definition(actor.definition_id).abilities),
                is_hunted_prey=True,
                precision_used_round=actor.precision_used_round,
                current_round=state.round_number,
                damage_type=damage_type,
            )
            if precision is not None:
                terms.append(precision)
                # A finalized hit consumes Precision even when its precision
                # component is later prevented by an immunity or resistance.
                actor.precision_used_round = state.round_number
        result = roll_damage_terms(
            tuple(terms), dice.draw, critical=critical
        )
        if critical and attack.deadly_die is not None:
            return replace(result, adjustment="deadly_after_critical")
        return result

    def _resolve_confident_finisher_choice(
        self, state, dice, pending: PendingChoice, command: Choose
    ) -> list[Event]:
        """Apply the saved full or failure-effect result through normal defenses."""

        resolution = pending.damage_resolution
        full_damage = pending.damage_result
        if resolution is None or full_damage is None:
            raise _Rejected("The Confident Finisher damage choice is incomplete.")
        if command.option_id == "full_damage":
            selected = resolution
            event = Event(
                "confident_finisher_full_damage",
                resolution.actor_id,
                resolution.target_id,
                "Confident Finisher applies its full Strike damage.",
            )
        elif command.option_id == "failure_effect":
            from .swashbuckler import confident_finisher_failure_damage

            precision_components = tuple(
                component
                for component in full_damage.components
                if component.source == "swashbuckler_precise_strike"
                and component.dice == (6, 6)
            )
            if len(precision_components) != 1:
                raise _Rejected("The saved Confident Finisher has no unique rolled 2d6 precision term.")
            precision = DamageResult(
                (precision_components[0],),
                sum(precision_components[0].rolls),
                1,
                sum(precision_components[0].rolls),
            )
            failure = confident_finisher_failure_damage(
                precision, resolution.damage_type
            )
            selected = replace(
                resolution,
                source="confident_finisher_failure",
                damage_type=resolution.damage_type,
                attacker_critical=False,
                group=DamageGroup(
                    resolution.group.group_id + ":failure",
                    (failure,),
                    "strike",
                    resolution.group.traits,
                ),
            )
            event = Event(
                "confident_finisher_failure_effect",
                resolution.actor_id,
                resolution.target_id,
                "Confident Finisher uses its failure effect: half the rolled 2d6 precision damage.",
                damage=failure,
            )
        else:
            raise _Rejected("Choose full damage or the Confident Finisher failure effect.")
        return [event, *self._resolve_damage_to_health(state, dice, selected, resumed=False)]

    def _validate_confident_finisher_pending(
        self, state: EncounterState, pending: PendingChoice
    ) -> None:
        """Validate the saved success choice against the committed Finisher."""

        continuation = pending.continuation
        resolution = pending.damage_resolution
        actor = state.creatures.get(pending.actor_id or "")
        target = state.creatures.get(pending.target_id or "")
        attack = self._find_attack(state, actor, pending.attack_id or "") if actor is not None else None
        if (
            actor is None
            or target is None
            or attack is None
            or continuation is None
            or not continuation.finisher
            or continuation.actor_id != actor.actor_id
            or continuation.target_id != target.actor_id
            or continuation.attack_id != attack.attack_id
            or pending.owner_actor_id != actor.actor_id
            or pending.family_id != "martial"
            or pending.procedure_id != "swashbuckler:confident_finisher:damage"
            or pending.options != (
                ChoiceOption("full_damage", "Apply full Strike damage"),
                ChoiceOption("failure_effect", "Use the failure effect (half precise-strike damage)"),
            )
            or resolution is None
            or resolution.source_kind != "strike"
            or resolution.actor_id != actor.actor_id
            or resolution.target_id != target.actor_id
            or resolution.attack_id != attack.attack_id
            or resolution.continuation != continuation
            or pending.damage_result is None
            or pending.damage_result != resolution.group.results[0]
            or pending.damage_result_is_mitigated
            or resolution.pending_defense_choice is not None
            or not actor.finisher_used_this_turn
            or actor.panache
            or not state.initiative_order
            or not 0 <= state.active_index < len(state.initiative_order)
            or state.initiative_order[state.active_index] != actor.actor_id
            or pending.attack_count != continuation.attack_count
            or pending.attack_penalty != continuation.attack_penalty
            or pending.item_id != continuation.item_id
            or not self._confident_finisher_item_available(
                state, actor, target, attack, pending.item_id
            )
            or not any(
                component.source == "swashbuckler_precise_strike"
                and component.dice == (6, 6)
                and component.rolls
                for component in pending.damage_result.components
            )
        ):
            raise ValueError("save has an unavailable or inconsistent Confident Finisher choice")

    def _confident_finisher_item_available(self, state, actor, target, attack, item_id):
        if attack.item_id is None:
            return item_id is None
        if "ranged" in attack.traits and "thrown" in attack.traits:
            return item_id in (state.ground_items or {}).get(target.position, ())
        return item_id in self._held_attack_item_ids(state, actor, attack)

    @staticmethod
    def _damage_application_text(text: str, absorbed: int) -> str:
        if absorbed <= 0:
            return text
        return text[:-1] + f"; {absorbed} temporary HP absorbed."

    def _absorb_damage_temporary_hp(self, state, target, amount):
        self._refresh_barbarian_state(state, target)
        result = absorb_temporary_hp(amount, target.temporary_hp)
        target.temporary_hp = result.temporary_hp
        if result.temporary_hp == 0:
            target.temporary_hp_source_id = None
            target.temporary_hp_expires_at_seconds = None
            target.temporary_hp_expires_at_source_start = 0
        return result

    def _damage_defense_options(
        self, group: DamageGroup, choice: DefenseChoice
    ) -> tuple[tuple[ChoiceOption, ...], dict[str, DamagePartRef]]:
        by_type: dict[str, DamagePartRef] = {}
        labels: dict[str, str] = {}
        for part in choice.eligible_parts:
            component = group.results[part.result_index].components[part.component_index]
            damage_type = component.damage_type.casefold()
            by_type.setdefault(damage_type, part)
            labels.setdefault(damage_type, component.damage_type)
        options = tuple(
            ChoiceOption(f"resist:{damage_type}", f"Resist {labels[damage_type]}")
            for damage_type in by_type
        )
        return options, by_type

    def _justice_protector(self, state: EncounterState, attacker: CreatureState, target: CreatureState):
        """Find the first eligible Champion reaction for one ally damage event."""
        if attacker.team == target.team:
            return None
        for actor_id in state.initiative_order or tuple(state.creatures):
            champion = state.creatures[actor_id]
            if (
                champion.actor_id != target.actor_id
                and champion.team == target.team
                and champion.reaction_available
                and "justice_retributive_strike" in get_definition(champion.definition_id).abilities
                and self._in_justice_aura(state, champion, target)
            ):
                return champion
        return None

    def _justice_damage_defenses(self, state, resolution: DamageResolution, defenses):
        if not resolution.justice_protected:
            return defenses
        champion = state.creatures.get(resolution.justice_actor_id or "")
        if champion is None:
            raise _Rejected("Justice protection no longer has its Champion source.")
        resistance = 2 + get_definition(champion.definition_id).level
        source = f"Justice Champion resistance ({resolution.justice_actor_id})"
        return (*defenses, DamageDefense("resistance", "all", resistance, source=source))

    def _paired_base_defenses(self, resolution: DamageResolution, defenses):
        """Return ordinary defenses with a prior same-type Flurry use carried.

        This is the documented chronological allocation convention.  Triggered
        Justice resistance is deliberately added later and stays scoped to its
        own damage event; Shield Block is likewise downstream from this list.
        """
        parent = self._paired_parent(resolution.continuation)
        paired = parent.paired_strike if parent is not None else None
        if (
            paired is None
            or paired.defense_target_id != resolution.target_id
            or paired.defense_damage_type != resolution.damage_type
        ):
            return defenses, parent
        remaining = dict(paired.resistance_remaining)
        adjusted = []
        for index, defense in enumerate(defenses):
            source = defense.source or f"{defense.kind}:{defense.applies_to}[{index}]"
            if defense.kind == "weakness" and source in paired.spent_weaknesses:
                continue
            if defense.kind == "resistance" and source in remaining:
                if remaining[source] == 0:
                    continue
                defense = replace(defense, value=remaining[source])
            adjusted.append(defense)
        return tuple(adjusted), parent

    def _remember_paired_defenses(self, resolution, base_defenses, mitigation, parent):
        if parent is None or parent.paired_strike is None:
            return
        paired = parent.paired_strike
        if paired.defense_target_id not in {None, resolution.target_id} or paired.defense_damage_type not in {None, resolution.damage_type}:
            return
        spent = set(paired.spent_weaknesses)
        remaining = dict(paired.resistance_remaining)
        applied = set(mitigation.applied_defenses)
        non_resistance = tuple(item for item in base_defenses if item.kind != "resistance")
        baseline = apply_damage_defenses(resolution.group, non_resistance).total
        for index, defense in enumerate(base_defenses):
            source = defense.source or f"{defense.kind}:{defense.applies_to}[{index}]"
            if defense.kind == "weakness" and source in applied:
                spent.add(source)
            elif defense.kind == "resistance" and source in applied:
                # Only the chosen strongest resistance applies. Its unused
                # value carries to the next same-type hit; lower alternatives
                # remain excluded by the normal non-stacking rule.
                remaining[source] = max(0, defense.value - baseline)
        parent.paired_strike = replace(
            paired,
            defense_target_id=resolution.target_id,
            defense_damage_type=resolution.damage_type,
            spent_weaknesses=tuple(sorted(spent)),
            resistance_remaining=tuple(sorted(remaining.items())),
        )

    def _justice_retaliation(self, state, dice, resolution: DamageResolution) -> tuple[list[Event], bool]:
        """Strike the triggering enemy after accepted protection, if reachable."""
        if not resolution.justice_protected or resolution.justice_actor_id is None:
            return [], False
        champion = state.creatures.get(resolution.justice_actor_id)
        attacker = state.creatures.get(resolution.actor_id)
        if champion is None or attacker is None or champion.unconscious or champion.dead or attacker.defeated:
            return [], False
        attacks = tuple(
            attack for attack in get_definition(champion.definition_id).attacks
            if "melee" in attack.traits
            and self._attack_usable(state, champion, attack)
            and grid_distance_feet(champion.position, attacker.position) <= attack.reach_ft
        )
        if not attacks:
            return [Event(
                "retributive_strike_out_of_reach",
                champion.actor_id,
                attacker.actor_id,
                f"{champion.label} protects the ally, but the triggering enemy is out of melee reach.",
            )], False
        attack = attacks[0]
        if champion.actor_id == self._active_actor_id(state):
            penalty = multiple_attack_penalty(champion.strikes_this_turn, attack.traits)
            champion.strikes_this_turn += 1
            attack_count = champion.strikes_this_turn
        else:
            penalty = 0
            attack_count = 1
        context = ActionContinuation(
            kind="reaction_strike",
            actor_id=champion.actor_id,
            target_id=attacker.actor_id,
            attack_id=attack.attack_id,
            item_id=self._held_attack_item_id(state, champion, attack),
            damage_type=attack.damage_type,
            nonlethal="nonlethal" in attack.traits,
            attack_penalty=penalty,
            attack_count=attack_count,
            attack_actions_cost=0,
            attack_count_cost=0,
            reaction_trigger="justice_damage",
        )
        events = [Event(
            "retributive_strike",
            champion.actor_id,
            attacker.actor_id,
            f"{champion.label} uses Retributive Strike against {attacker.label} (MAP {penalty}).",
        )]
        events.extend(self._roll_strike(state, dice, champion, attacker, attack, context, parent=resolution.continuation))
        return events, True

    def _resolve_damage_to_health(
        self,
        state: EncounterState,
        dice: DiceSource,
        resolution: DamageResolution,
        *,
        resumed: bool,
    ) -> list[Event]:
        """Resolve one already-rolled effect through defenses, temp HP, then health."""
        target = state.creatures.get(resolution.target_id)
        attacker = state.creatures.get(resolution.actor_id)
        if (
            target is None or attacker is None
            or (target.actor_id == attacker.actor_id and resolution.spell_id not in {"caustic_blast", "gale_blast"})
        ):
            raise _Rejected("Damage requires two different existing creatures.")
        if not resolution.justice_checked:
            protector = self._justice_protector(state, attacker, target)
            if protector is not None:
                resolution = replace(
                    resolution,
                    justice_checked=True,
                    justice_actor_id=protector.actor_id,
                )
                continuation = ActionContinuation(
                    kind="justice_damage",
                    actor_id=attacker.actor_id,
                    target_id=target.actor_id,
                    reaction_trigger="justice_damage",
                    parent_continuation=resolution.continuation,
                )
                # Keep the Justice reaction as the saved continuation of the
                # damage event. Its parent is the interrupted action (when
                # there is one); after retaliation resolves, that action can
                # resume through the ordinary continuation path.
                resolution = replace(resolution, continuation=continuation)
                self._set_pending(
                    state,
                    kind="reaction",
                    owner_actor_id=protector.actor_id,
                    prompt=(
                        f"{protector.label} may use Retributive Strike to protect {target.label}."
                    ),
                    options=(
                        ChoiceOption("accept", "Accept protection and retaliate if reachable"),
                        ChoiceOption("decline", "Decline"),
                    ),
                    details=(
                        f"Accepted protection grants resistance {2 + get_definition(protector.definition_id).level} to this damage and spends the Champion's reaction.",
                        "The ally remains protected even when the Champion cannot reach the attacker.",
                    ),
                    actor_id=attacker.actor_id,
                    target_id=target.actor_id,
                    continuation=continuation,
                    damage_resolution=resolution,
                )
                return []
        frostbite_weakness = tuple(
            DamageDefense("weakness", "bludgeoning", effect.value, source=effect.effect_id)
            for effect in state.active_effects
            if effect.kind == "frostbite_weakness" and effect.target_actor_id == target.actor_id
        )
        bomber_immunities = self._bomber_bomb_damage_immunities(state, target, resolution)
        energy_ablation = tuple(
            DamageDefense(
                "resistance",
                effect.effect_id.split(":", 2)[2],
                effect.value,
                source=effect.effect_id,
            )
            for effect in state.active_effects
            if effect.kind == "energy_ablation"
            and effect.target_actor_id == target.actor_id
            and len(effect.effect_id.split(":", 2)) == 3
        )
        base_defenses, paired_parent = self._paired_base_defenses(
            resolution,
            (*get_definition(target.definition_id).damage_defenses, *frostbite_weakness, *bomber_immunities, *energy_ablation),
        )
        defenses = self._justice_damage_defenses(state, resolution, base_defenses)
        try:
            mitigation = apply_damage_defenses(
                resolution.group, defenses, resolution.selections
            )
        except ValueError as error:
            raise _Rejected(f"Damage defense selection is no longer legal: {error}") from error
        if mitigation.unresolved_choices:
            choice = mitigation.unresolved_choices[0]
            resolution = replace(resolution, pending_defense_choice=choice)
            options, _by_type = self._damage_defense_options(resolution.group, choice)
            defense_name = choice.defense_source
            details = tuple(
                f"{resolution.group.results[part.result_index].components[part.component_index].source}: "
                f"{resolution.group.results[part.result_index].components[part.component_index].amount} "
                f"{resolution.group.results[part.result_index].components[part.component_index].damage_type}"
                for part in choice.eligible_parts
            )
            self._set_pending(
                state,
                kind="damage_defense",
                owner_actor_id=target.actor_id,
                prompt=f"{target.label} chooses which damage type {defense_name} resists.",
                options=options,
                details=details,
                actor_id=attacker.actor_id,
                target_id=target.actor_id,
                check=resolution.check,
                attack_id=resolution.attack_id,
                spell_id=resolution.spell_id,
                damage_type=resolution.damage_type,
                nonlethal=resolution.nonlethal,
                attack_critical=resolution.attacker_critical,
                damage_bonus_dice=resolution.damage_bonus_dice,
                is_reaction=resolution.is_reaction,
                continuation=resolution.continuation,
                damage_resolution=resolution,
            )
            return []

        if len(mitigation.results) != 1:
            raise _Unsupported("This damage entry expects one rolled result per effect group.")
        damage = mitigation.results[0]
        if resolution.shield_block_status == "pending":
            raise _Rejected("The saved Shield Block decision must be resolved before damage continues.")
        if resolution.shield_block_status is None:
            shield = self._shield_block_trigger(state, target, resolution, damage)
            if shield is not None:
                magic = shield == _MAGIC_SHIELD_BLOCK
                resolution = replace(
                    resolution,
                    shield_block_status="pending",
                    shield_block_instance_id=None if magic else shield.instance_id,
                    shield_block_magic=magic,
                )
                physical = sum(
                    component.amount for component in damage.components
                    if shield_block_trigger_eligible(component.damage_type, from_attack=True)
                )
                self._set_pending(
                    state,
                    kind="shield_block",
                    owner_actor_id=target.actor_id,
                    prompt=(
                        f"{target.label} would take {damage.total} damage. Use magical Shield Block?"
                        if magic else
                        f"{target.label} would take {damage.total} damage, including {physical} physical from an attack. Use Shield Block?"
                    ),
                    options=(
                        ChoiceOption("block", "Use Shield Block"),
                        ChoiceOption("decline", "Decline"),
                    ),
                    details=(
                        f"Damage after IWR: {damage.total} ({', '.join(f'{component.amount} {component.damage_type}' for component in damage.components)}).",
                        "Magic Shield: Hardness 5; blocking ends the spell and starts its ten-minute cooldown."
                        if magic else
                        f"Shield: {shield.definition_id}; Hardness {STEEL_SHIELD.hardness}; HP {shield.hp}/{STEEL_SHIELD.max_hp}.",
                    ),
                    actor_id=attacker.actor_id,
                    target_id=target.actor_id,
                    check=resolution.check,
                    attack_id=resolution.attack_id,
                    damage_type=resolution.damage_type,
                    nonlethal=resolution.nonlethal,
                    attack_critical=resolution.attacker_critical,
                    is_reaction=resolution.is_reaction,
                    continuation=resolution.continuation,
                    damage_resolution=resolution,
                )
                return []
        block_record = resolution.shield_block_record
        actor_damage = block_record.damage_to_actor if block_record is not None else damage.total
        life_link_events, actor_damage, life_link_effect_id, life_link_source_actor_id = self._apply_life_link_damage(
            state, target, actor_damage,
        )
        if life_link_effect_id is not None:
            resolution = replace(
                resolution,
                life_link_effect_id=life_link_effect_id,
                life_link_source_actor_id=life_link_source_actor_id,
                life_link_transfer=(block_record.damage_to_actor if block_record is not None else damage.total) - actor_damage,
            )
        hp_damage = self._absorb_damage_temporary_hp(state, target, actor_damage)
        if self._stable_zero_pc(target) and hp_damage.damage_to_hp > 0:
            raise _Unsupported("Positive damage to a stabilized 0 HP PC awaits a product ruling and is unsupported.")

        if target.health_mode is HealthMode.PC:
            hero_owner = self._familiar_hero_owner(state, target) or target
            transition = self._propose_pc_damage(
                target,
                hp_damage.damage_to_hp,
                attacker_critical=resolution.attacker_critical,
                target_critical_failure=resolution.target_critical_failure,
                nonlethal=resolution.nonlethal,
                hero_points=hero_owner.hero_points,
                damage_taken=actor_damage,
            )
            if transition.heroic_recovery_available and transition.heroic_recovery_option is not None:
                if (
                    resolution.source_kind == "spell"
                    and resolution.continuation is not None
                    and resolution.continuation.spell_id not in {"force_barrage", "breathe_fire", "gale_blast"}
                ):
                    resolution.continuation.stage = "done"
                damage_text = self._damage_text_for_resolution(
                    resolution, damage, transition.state.dead, hp_damage.absorbed
                )
                if resolution.source_kind == "spell":
                    damage_text = self._damage_application_text(
                        f"{SPELLS[resolution.spell_id].name} deals {damage.total} {resolution.damage_type}.",
                        hp_damage.absorbed,
                    )
                self._set_pending(
                    state,
                    kind="heroic_recovery_damage",
                    owner_actor_id=hero_owner.actor_id,
                    prompt=(
                        f"{target.label} would gain dying from {resolution.source} damage; choose normal outcome or Heroic Recovery."
                        if hero_owner is target else
                        f"{hero_owner.label} may spend Hero Points on behalf of {target.label}; choose normal outcome or Heroic Recovery."
                    ),
                    options=(
                        ChoiceOption("normal", "Apply normal health outcome"),
                        ChoiceOption("heroic_recovery", "Heroic Recovery (spend all Hero Points)"),
                    ),
                    details=(
                        self._damage_application_text(
                            f"{'Damage rolled' if resolution.source_kind == 'strike' else 'Damage'}: "
                            f"{damage.total} {resolution.damage_type}.",
                            hp_damage.absorbed,
                        ),
                        *((self._shield_block_detail(block_record),) if block_record is not None else ()),
                    ),
                    actor_id=attacker.actor_id,
                    target_id=target.actor_id,
                    attack_id=resolution.attack_id,
                    check=resolution.check,
                    damage_result=damage,
                    damage_result_is_mitigated=True,
                    damage_resolution=replace(resolution, pending_defense_choice=None),
                    damage_text=damage_text,
                    temporary_hp_absorbed=hp_damage.absorbed,
                    remaining_hp_damage=hp_damage.damage_to_hp,
                    attack_critical=resolution.attacker_critical,
                    health_normal=transition,
                    health_heroic=transition.heroic_recovery_option,
                    transition_kind="damage",
                    damage_type=resolution.damage_type,
                    nonlethal=resolution.nonlethal,
                    damage_bonus_dice=resolution.damage_bonus_dice,
                    is_reaction=resolution.is_reaction,
                    continuation=resolution.continuation,
                    spell_id=resolution.spell_id,
                    damage_context=(
                        f"enfeebled:{resolution.enfeebled_on_failure}"
                        if resolution.enfeebled_on_failure else None
                    ),
                )
                return []
            self._apply_health_transition(state, target, transition)
        else:
            before_hp = target.hp
            target.hp = max(0, target.hp - hp_damage.damage_to_hp)
            if target.hp == 0 and before_hp > 0 and target.health_mode is HealthMode.ORDINARY:
                if resolution.nonlethal:
                    target.dead = False
                    target.unconscious = True
                    target.prone = True
                    target.reaction_available = False
                    target.must_leave_occupied = False
                    if target.held_items:
                        state.raised_shields.pop(target.actor_id, None)
                        state.ground_items.setdefault(target.position, []).extend(target.held_items)
                        target.held_items.clear()
                else:
                    target.dead = True
                    target.unconscious = False
                    if resolution.source_kind == "spell":
                        target.prone = False
                        target.reaction_available = False
        outcome = _DamageHealthResult(
            damage=damage,
            temporary_hp_absorbed=hp_damage.absorbed,
            remaining_hp_damage=hp_damage.damage_to_hp,
            defeated=target.defeated,
            shield_block=block_record,
        )
        return life_link_events + self._finish_damage_application(state, dice, resolution, outcome, resumed=resumed)

    @staticmethod
    def _active_life_link(state: EncounterState, oracle: CreatureState) -> ActiveSpellEffect | None:
        """Return the Oracle's live one-minute Life Link, if any."""
        start = state.actor_start_counts.get(oracle.actor_id, 0)
        for effect in state.active_effects:
            if (
                effect.kind == "life_link"
                and effect.source_actor_id == oracle.actor_id
                and effect.expires_at_source_start > start
                and (
                    state.in_progress
                    or effect.expires_at_world_time is None
                    or effect.expires_at_world_time > state.world_time_seconds
                )
            ):
                return effect
        return None

    def _apply_life_link_damage(
        self, state: EncounterState, target: CreatureState, actor_damage: int,
    ) -> tuple[list[Event], int, str | None, str | None]:
        """Apply the approved post-Shield, pre-temporary-HP Life Link transfer."""
        if actor_damage <= 0:
            return [], actor_damage, None, None
        effect = next(
            (item for item in state.active_effects
             if item.kind == "life_link"
             and item.target_actor_id == target.actor_id
             and item.life_link_used_round != state.round_number),
            None,
        )
        if effect is None:
            return [], actor_damage, None, None
        oracle = state.creatures.get(effect.source_actor_id)
        if oracle is None or oracle.unconscious or oracle.dead:
            return [], actor_damage, None, None
        transfer = min(effect.value, actor_damage)
        state.active_effects[state.active_effects.index(effect)] = replace(
            effect, life_link_used_round=state.round_number,
        )
        if oracle.health_mode is HealthMode.PC:
            transition = self._propose_pc_damage(
                oracle, transfer, attacker_critical=False,
                target_critical_failure=False, nonlethal=False,
                hero_points=0, damage_taken=transfer,
            )
            self._apply_health_transition(state, oracle, transition)
        else:
            oracle.hp = max(0, oracle.hp - transfer)
            if oracle.hp == 0:
                oracle.dead = True
        if oracle.unconscious or oracle.dead:
            state.active_effects[:] = [
                item for item in state.active_effects
                if not (item.kind == "life_link" and item.source_actor_id == oracle.actor_id)
            ]
        return [Event(
            "life_link_transfer", oracle.actor_id, target.actor_id,
            f"Life Link transfers {transfer} damage from {target.label} to {oracle.label}; the Oracle loses {transfer} HP without mitigation.",
            details=(effect.effect_id, f"round:{state.round_number}"),
        )], actor_damage - transfer, effect.effect_id, oracle.actor_id

    def _damage_text_for_resolution(
        self,
        resolution: DamageResolution,
        damage: DamageResult,
        defeated: bool,
        absorbed: int,
    ) -> str:
        if resolution.source_kind == "strike":
            attack = next(
                (item for item in get_definition(
                    self._state.creatures[resolution.actor_id].definition_id
                ).attacks if item.attack_id == resolution.attack_id),
                None,
            )
            dice = attack.damage_dice if attack is not None else ()
            text = _damage_text(damage, dice, defeated, bonus_dice=resolution.damage_bonus_dice)
        elif resolution.source_kind == "spell":
            name = SPELLS[resolution.spell_id].name
            text = f"{name} deals {damage.total} {resolution.damage_type}."
        else:
            text = f"{resolution.source} deals {damage.total} {resolution.damage_type} damage."
        original = resolution.group.results[0]
        if original.components != damage.components or original.total != damage.total:
            text = self._defense_adjusted_damage_text(
                resolution, original, damage, defeated=defeated
            )
        return self._damage_application_text(text, absorbed)

    @staticmethod
    def _defense_adjusted_damage_text(
        resolution: DamageResolution,
        original: DamageResult,
        damage: DamageResult,
        *,
        defeated: bool,
    ) -> str:
        component_text = ", ".join(
            f"{component.damage_type} {component.amount}"
            for component in damage.components
        )
        if resolution.source_kind == "spell":
            prefix = f"{SPELLS[resolution.spell_id].name}: "
        elif resolution.source_kind == "family":
            prefix = f"{resolution.source}: "
        else:
            prefix = ""
        text = (
            f"{prefix}damage after defenses: {component_text}; "
            f"{damage.total} total (was {original.total} before defenses)"
        )
        if defeated:
            text += "; target defeated"
        return text + "."

    def _finish_damage_application(
        self,
        state: EncounterState,
        dice: DiceSource,
        resolution: DamageResolution,
        outcome: _DamageHealthResult,
        *,
        resumed: bool,
        health_choice: str | None = None,
    ) -> list[Event]:
        attacker = state.creatures[resolution.actor_id]
        target = state.creatures[resolution.target_id]
        damage = outcome.damage
        if resolution.source_kind == "spell":
            kind = "spell_damage"
            text = self._damage_application_text(
                f"{SPELLS[resolution.spell_id].name} deals {damage.total} {resolution.damage_type} to {target.label}.",
                outcome.temporary_hp_absorbed,
            )
        elif resolution.source_kind == "family":
            kind = "damage"
            text = self._damage_application_text(
                f"{resolution.source} deals {damage.total} {resolution.damage_type} damage to {target.label}.",
                outcome.temporary_hp_absorbed,
            )
        else:
            kind = "damage"
            text = self._damage_text_for_resolution(
                resolution, damage, outcome.defeated, outcome.temporary_hp_absorbed
            )
        original_damage = resolution.group.results[0]
        if original_damage.components != damage.components or original_damage.total != damage.total:
            text = self._defense_adjusted_damage_text(
                resolution, original_damage, damage, defeated=outcome.defeated
            )
            text = self._damage_application_text(text, outcome.temporary_hp_absorbed)
        details = ()
        if outcome.shield_block is not None:
            details = (self._shield_block_detail(outcome.shield_block),)
            text = f"{text} {details[0]}"
        events = [Event(
            kind,
            attacker.actor_id,
            target.actor_id,
            text,
            check=resolution.check,
            damage=damage,
            temporary_hp_absorbed=outcome.temporary_hp_absorbed,
            remaining_hp_damage=outcome.remaining_hp_damage,
            original_damage=original_damage,
            details=details,
            shield_block=outcome.shield_block,
        )]
        if health_choice is not None:
            event_kind = "heroic_recovery" if health_choice == "heroic_recovery" else "health_changed"
            events.append(Event(
                event_kind,
                attacker.actor_id,
                target.actor_id,
                f"{target.label}: HP {target.hp}, dying {target.dying}, wounded {target.wounded}.",
            ))

        if resolution.source_kind == "spell":
            if resolution.continuation is None or resolution.continuation.spell_id != "gale_blast":
                self._finish_if_team_defeated(state)
            if resolution.enfeebled_on_failure and not target.dead:
                self._apply_enfeebled(state, attacker, target, resolution.enfeebled_on_failure)
                events.append(Event(
                    "effect_applied", attacker.actor_id, target.actor_id,
                    f"{target.label} is enfeebled {resolution.enfeebled_on_failure} until {attacker.label}'s next turn.",
                ))
            if target.defeated:
                events.append(Event("defeated", attacker.actor_id, target.actor_id, f"{target.label} is defeated."))
            if resolution.continuation is not None and resolution.continuation.spell_id == "gale_blast":
                continuation = resolution.continuation
                try:
                    _tag, index_text, push_text = (continuation.stage or "").split(":")
                    index, push_ft = int(index_text), int(push_text)
                except (ValueError, IndexError) as error:
                    raise _Rejected("Gale Blast's saved recipient progress is invalid.") from error
                if push_ft and target.actor_id != attacker.actor_id:
                    events.extend(self._apply_gale_blast_push(state, dice, attacker, target, push_ft))
                continuation.stage = f"gale:{index + 1}:0"
                return events + self._continue_gale_blast(state, dice, attacker, continuation)
            if resolution.continuation is not None and resolution.continuation.spell_id == "force_barrage":
                continuation = resolution.continuation
                try:
                    index = int((continuation.stage or "force_barrage:0").split(":", 1)[1])
                except (IndexError, ValueError):
                    raise _Rejected("Force Barrage's saved recipient progress is invalid.")
                continuation.stage = f"force_barrage:{index + 1}"
                return events + self._continue_force_barrage(state, dice, attacker, continuation)
            if resolution.continuation is not None and resolution.continuation.spell_id == "breathe_fire":
                continuation = resolution.continuation
                try:
                    index = int((continuation.stage or "breathe_fire:0").split(":", 1)[1])
                except (IndexError, ValueError):
                    raise _Rejected("Breathe Fire's saved recipient progress is invalid.")
                continuation.stage = f"breathe_fire:{index + 1}"
                return events + self._continue_breathe_fire(state, dice, attacker, continuation)
            if resolution.continuation is not None and resolution.continuation.spell_id == "electric_arc":
                continuation = resolution.continuation
                try:
                    index = int((continuation.stage or "electric_arc:0").split(":", 1)[1])
                except (IndexError, ValueError):
                    raise _Rejected("Electric Arc's saved recipient progress is invalid.")
                continuation.stage = f"electric_arc:{index + 1}"
                return events + self._continue_electric_arc(state, dice, attacker, continuation)
            if resolution.continuation is not None and resolution.continuation.spell_id == "caustic_blast":
                continuation = resolution.continuation
                try:
                    _tag, index_text, persistent_text = (continuation.stage or "").split(":")
                    index = int(index_text)
                    persistent = bool(int(persistent_text))
                except (ValueError, IndexError) as error:
                    raise _Rejected("Caustic Blast's saved recipient progress is invalid.") from error
                if persistent and damage.total > 0 and not target.defeated:
                    self._apply_persistent_effect(state, attacker, target, "caustic_blast", "acid", flat=1)
                    events.append(Event("persistent_applied", attacker.actor_id, target.actor_id, f"{target.label} takes 1 persistent acid damage."))
                continuation.stage = f"caustic:{index + 1}:0"
                return events + self._continue_caustic_blast(state, dice, attacker, continuation)
            if resolution.continuation is not None:
                continuation = resolution.continuation
                if (
                    continuation.stage is not None
                    and continuation.stage.startswith("persistent:")
                    and damage.total > 0
                    and not target.defeated
                ):
                    try:
                        _tag, damage_type, dice_side, flat = continuation.stage.split(":")
                        persistent_dice = (int(dice_side),) if int(dice_side) else ()
                        self._apply_persistent_effect(
                            state, attacker, target, continuation.spell_id or "",
                            damage_type, dice=persistent_dice, flat=int(flat),
                        )
                        events.append(Event(
                            "persistent_applied", attacker.actor_id, target.actor_id,
                            f"{target.label} takes persistent {damage_type} damage.",
                        ))
                    except ValueError as error:
                        raise _Rejected("The pending persistent-damage spell result is invalid.") from error
                resolution.continuation.stage = "done"
            return self._complete_action(state, attacker, events, dice=dice)

        if outcome.defeated:
            events.append(Event("defeated", attacker.actor_id, target.actor_id, f"{target.label} is defeated."))
        if resolution.source_kind == "strike" and resolution.continuation is not None:
            events.extend(self._apply_committed_strike_rider(
                state, dice, attacker, target, resolution.continuation,
                damage=damage.total, critical=resolution.attacker_critical, hit=True,
            ))
        if resolution.source_kind == "strike":
            bomb_facts = self._admitted_bomber_bomb_facts_for_attack(attacker, resolution.attack_id)
            if bomb_facts is not None:
                events.extend(self._apply_bomber_bomb_effects(
                    state, dice, resolution, attacker, target, bomb_facts,
                    only_primary_splash=resolution.bomber_only_primary_splash,
                ))
        if (
            outcome.defeated
            and resolution.continuation is None
            and not resolution.is_reaction
            and self._present_youre_next(state, attacker, target)
        ):
            return events
        self._finish_if_team_defeated(state)
        # Commit the shared Flurry defense ledger only after this damage event
        # has cleared its own Shield Block/Hero/Justice continuations.  A
        # saved Shield choice re-enters damage resolution, so committing it
        # earlier would make the same Strike consume IWR twice on resume.
        base_defenses, paired_parent = self._paired_base_defenses(
            resolution,
            (*get_definition(target.definition_id).damage_defenses,
             *self._bomber_bomb_damage_immunities(state, target, resolution)),
        )
        effective_defenses = self._justice_damage_defenses(state, resolution, base_defenses)
        mitigation = apply_damage_defenses(
            resolution.group, effective_defenses, resolution.selections
        )
        if mitigation.unresolved_choices:
            raise _Rejected("The completed paired Strike has an unresolved damage defense.")
        self._remember_paired_defenses(resolution, base_defenses, mitigation, paired_parent)
        # Record the triggering subordinate before Justice can start its own
        # retaliatory Strike.  The reaction inherits this parent solely to
        # resume it; it must never become this activity's outcome.
        if resolution.source_kind == "strike" and not resolution.is_reaction:
            self._record_paired_outcome(
                resolution.continuation,
                check=resolution.check,
                damage=damage,
                damage_type=resolution.damage_type,
                nonlethal=resolution.nonlethal,
                hit=True,
            )
        retaliation_events, retaliation_started = self._justice_retaliation(
            state, dice, resolution
        )
        events.extend(retaliation_events)
        if retaliation_started:
            # The retaliation owns the triggering action's continuation. Its
            # Strike result will resume that action after any saved check or
            # defense choice completes.
            return events
        if resolution.source_kind == "strike":
            continuation = resolution.continuation
            has_interrupted_action = continuation is not None and (
                continuation.kind != "justice_damage"
                or continuation.parent_continuation is not None
            )
            if has_interrupted_action and (
                state.in_progress or continuation.kind == "paired_strike"
            ):
                events.extend(self._resume_continuation(
                    state, dice, continuation, critical=resolution.attacker_critical
                ))
            elif (
                not resolution.is_reaction and state.in_progress
                and attacker.actions_remaining == 0 and state.pending_choice is None
                and not self._free_devise_target_ids(state, attacker)
            ):
                events.extend(self._end_turn(state, attacker, early=False, dice=dice))
        elif resumed and resolution.complete_family_action_on_resume:
            events = self._complete_action(state, attacker, events, dice=dice)
        return events

    def _present_youre_next(self, state, attacker, defeated_target) -> bool:
        """Offer the finite post-defeat reaction before the attack completes."""

        definition = get_definition(attacker.definition_id)
        if (
            "You're Next" not in definition.feats
            or not attacker.reaction_available
            or attacker.unconscious
            or attacker.dead
        ):
            return False
        target_ids = tuple(
            candidate.actor_id
            for candidate in sorted(state.creatures.values(), key=lambda item: item.actor_id)
            if candidate.team != attacker.team
            and candidate.actor_id != defeated_target.actor_id
            and not candidate.defeated
            and not candidate.unconscious
            and not candidate.dead
            and grid_distance_feet(attacker.position, candidate.position) <= 60
        )
        if not target_ids:
            return False
        self._set_pending(
            state,
            kind="youre_next",
            owner_actor_id=attacker.actor_id,
            prompt=f"{attacker.label} may use You're Next after defeating {defeated_target.label}.",
            options=tuple(
                [ChoiceOption(f"target:{target_id}", f"Demoralize {state.creatures[target_id].label} (+2)") for target_id in target_ids]
                + [ChoiceOption("decline", "Decline")]
            ),
            details=("Reaction; choose an enemy within 60 feet for a Demoralize attempt with a +2 circumstance bonus.",),
            actor_id=attacker.actor_id,
            target_ids=target_ids,
        )
        return True

    def _finish_after_youre_next(self, state, dice, attacker, events):
        self._finish_if_team_defeated(state)
        if (
            state.in_progress
            and attacker.actions_remaining == 0
            and state.pending_choice is None
            and not self._free_devise_target_ids(state, attacker)
        ):
            events.extend(self._end_turn(state, attacker, early=False, dice=dice))
        return events

    @staticmethod
    def _bomb_damage_with_primary_splash(damage, attack_id, facts):
        """Fold primary splash into the Strike effect before defenses.

        Splash uses the bomb's type but is never doubled.  Keeping it in the
        same DamageResult makes a matching resistance apply once to the
        combined primary damage, as the bomb rules require.
        """
        splash = DamageComponent(
            f"{attack_id}_primary_splash", facts.damage_type, 0, (), facts.splash_damage,
            facts.splash_damage, critical_mode=facts.critical_splash_mode,
        )
        return replace(
            damage,
            components=(*damage.components, splash),
            rolled_total=damage.rolled_total + facts.splash_damage,
            total=damage.total + facts.splash_damage,
        )

    def _apply_bomber_miss_primary_splash(self, state, dice, attacker, target, attack, facts, *, item_id):
        """A missed bomb still applies its splash to the primary target."""
        splash = DamageResult(
            (DamageComponent(
                f"{attack.attack_id}_primary_splash", facts.damage_type, 0, (),
                facts.splash_damage, facts.splash_damage,
                critical_mode=facts.critical_splash_mode,
            ),),
            facts.splash_damage, 1, facts.splash_damage,
        )
        resolution = DamageResolution(
            source_kind="family",
            group=DamageGroup(
                f"{attack.attack_id}:miss_splash:{attacker.actor_id}:{target.actor_id}:{state.next_choice_id}",
                (splash,), "family", frozenset({"bomb", "splash"}),
            ),
            actor_id=attacker.actor_id,
            target_id=target.actor_id,
            source=f"{attack.attack_id}_splash",
            damage_type=facts.damage_type,
            item_id=item_id,
        )
        return self._resolve_damage_to_health(state, dice, resolution, resumed=False)

    def _apply_bomber_bomb_effects(self, state, dice, resolution, attacker, target, facts, *, only_primary_splash):
        """Apply nearby splash on a hit and the selected bomb's hit rider."""
        attack_id = resolution.attack_id
        events: list[Event] = []
        if facts.splash_damage and not only_primary_splash:
            for recipient in tuple(state.creatures.values()):
                if recipient.actor_id in {attacker.actor_id, target.actor_id} or recipient.defeated:
                    continue
                if grid_distance_feet(recipient.position, target.position) > 5:
                    continue
                splash = DamageResult(
                    (DamageComponent(
                        f"{attack_id}_splash", facts.damage_type, 0, (),
                        facts.splash_damage, facts.splash_damage,
                        critical_mode=facts.critical_splash_mode,
                    ),),
                    facts.splash_damage, 1, facts.splash_damage,
                )
                splash_resolution = DamageResolution(
                    source_kind="family", group=DamageGroup(
                        f"{attack_id}:splash:{attacker.actor_id}:{recipient.actor_id}:{state.next_choice_id}",
                        (splash,), "family", frozenset({"bomb", "splash"}),
                    ), actor_id=attacker.actor_id, target_id=recipient.actor_id,
                    source=f"{attack_id}_splash", damage_type=facts.damage_type,
                    item_id=resolution.item_id,
                )
                events.extend(self._resolve_damage_to_health(state, dice, splash_resolution, resumed=False))
        if resolution.check is not None and resolution.check.degree in {
            DegreeOfSuccess.SUCCESS, DegreeOfSuccess.CRITICAL_SUCCESS,
        } and not target.defeated:
            if facts.persistent_damage_type is not None:
                bomb_formula_id = next(
                    (attack.item_id for attack in get_definition(attacker.definition_id).attacks
                     if attack.attack_id == attack_id),
                    None,
                )
                persistent_multiplier = 2 if resolution.attacker_critical else 1
                self._apply_persistent_effect(
                    state,
                    attacker,
                    target,
                    bomb_formula_id or "bomber_bomb",
                    facts.persistent_damage_type,
                    dice=facts.persistent_damage_dice * persistent_multiplier,
                    flat=facts.persistent_damage_flat * persistent_multiplier,
                )
                events.append(Event(
                    "persistent_applied", attacker.actor_id, target.actor_id,
                    f"{target.label} takes persistent {facts.persistent_damage_type} damage.",
                ))
            events.extend(self._apply_bomber_bomb_rider(
                state, resolution, attacker, target, facts,
            ))
        return events

    @staticmethod
    def _apply_bomber_bomb_rider(state, resolution, attacker, target, facts):
        """Apply the finite bomb riders through their shared sourced lifecycles."""
        if (
            resolution.check is None
            or resolution.check.degree not in {DegreeOfSuccess.SUCCESS, DegreeOfSuccess.CRITICAL_SUCCESS}
            or target.defeated
            or facts.on_hit_effect is None
        ):
            return []
        critical = resolution.attacker_critical
        effect_id = f"{resolution.attack_id}:{attacker.actor_id}:{target.actor_id}:{state.next_choice_id}"
        if facts.on_hit_effect == "off_guard":
            kind, value = "off_guard", facts.on_hit_effect_value or 1
            text = f"{target.label} is off-guard until {attacker.label}'s next turn."
            anchor, boundary = attacker.actor_id, "start"
            occurrence = state.actor_start_counts.get(anchor, 0) + 1
            state.condition_effects[:] = [
                effect for effect in state.condition_effects
                if not (effect.kind == kind and effect.source_actor_id == attacker.actor_id and effect.target_actor_id == target.actor_id)
            ]
            state.condition_effects.append(ActiveConditionEffect(
                effect_id, kind, attacker.actor_id, target.actor_id, value,
                EffectExpiration(anchor, boundary, occurrence),
            ))
            return [Event("bomb_rider", attacker.actor_id, target.actor_id, text)]
        if facts.on_hit_effect == "speed_minus_5":
            kind, value = "speed_penalty", facts.on_hit_effect_value or 5
            text = f"{target.label} takes a -{value}-foot status penalty to all Speeds until its next turn ends."
            anchor, boundary = target.actor_id, "end"
            occurrence = state.actor_end_counts.get(anchor, 0) + 1
            state.condition_effects[:] = [
                effect for effect in state.condition_effects
                if not (effect.kind == kind and effect.source_actor_id == attacker.actor_id and effect.target_actor_id == target.actor_id)
            ]
            state.condition_effects.append(ActiveConditionEffect(
                effect_id, kind, attacker.actor_id, target.actor_id, value,
                EffectExpiration(anchor, boundary, occurrence),
            ))
            return [Event("bomb_rider", attacker.actor_id, target.actor_id, text)]
        if facts.on_hit_effect == "frightened":
            from .opponent_content import PUBLISHED_OPPONENT_PROFILES

            dynamic_immunity = any(
                immunity.target_actor_id == target.actor_id
                and immunity.expires_at_seconds > state.world_time_seconds
                and immunity.kind in {"mental", "poison", "fear", "emotion", "frightened"}
                for immunity in state.condition_immunities
            )
            published = PUBLISHED_OPPONENT_PROFILES.get(target.definition_id)
            printed_immunity = published is not None and bool(
                {"mental", "poison", "fear", "emotion", "frightened"}
                & set(published.condition_immunities)
            )
            if dynamic_immunity or printed_immunity:
                return []
            value = facts.on_critical_hit_value if critical and facts.on_critical_hit_value is not None else facts.on_hit_effect_value or 1
            state.condition_effects[:] = [
                effect for effect in state.condition_effects
                if not (effect.kind == "frightened" and effect.source_actor_id == attacker.actor_id and effect.target_actor_id == target.actor_id)
            ]
            state.condition_effects.append(ActiveConditionEffect(
                f"dread_ampoule:{attacker.actor_id}:{target.actor_id}:{state.next_choice_id}",
                "frightened", attacker.actor_id, target.actor_id, value,
                EffectExpiration(target.actor_id, "end", state.actor_end_counts.get(target.actor_id, 0) + value),
            ))
            return [Event("bomb_rider", attacker.actor_id, target.actor_id, f"{target.label} is frightened {value}.")]
        if facts.on_hit_effect == "glue_speed_penalty":
            duration = facts.on_hit_effect_duration_seconds
            value = facts.on_hit_effect_value
            if duration is None or value is None or facts.on_hit_effect_dc is None:
                return []
            state.active_effects[:] = [
                effect for effect in state.active_effects
                if not (effect.kind == "alchemy_glue_bomb_lesser" and effect.source_actor_id == attacker.actor_id and effect.target_actor_id == target.actor_id)
            ]
            if resolution.item_id is None:
                return []
            glue_id = f"glue_bomb:{resolution.item_id}"
            state.active_effects.append(ActiveSpellEffect(
                glue_id, "alchemy_glue_bomb_lesser", attacker.actor_id, target.actor_id,
                value, state.actor_start_counts.get(attacker.actor_id, 0) + 1,
                state.world_time_seconds + duration,
            ))
            if critical and facts.on_critical_hit_effect == "glue_immobilized":
                state.condition_effects[:] = [
                    effect for effect in state.condition_effects
                    if not (effect.effect_id.startswith("glue_bomb:") and effect.source_actor_id == attacker.actor_id and effect.target_actor_id == target.actor_id)
                ]
                state.condition_effects.append(ActiveConditionEffect(
                    f"{glue_id}:immobilized", "immobilized", attacker.actor_id, target.actor_id,
                    facts.on_critical_hit_value or 1,
                    EffectExpiration(attacker.actor_id, "start", state.actor_start_counts.get(attacker.actor_id, 0) + 1),
                    facts.on_hit_effect_dc,
                ))
                text = f"{target.label} takes a -{value}-foot status penalty and is stuck to the solid ground for 1 round, until {attacker.label}'s next turn starts."
            else:
                text = f"{target.label} takes a -{value}-foot status penalty to all Speeds for {duration} seconds."
            return [Event("bomb_rider", attacker.actor_id, target.actor_id, text)]
        return []

    @staticmethod
    def _bomber_bomb_damage_immunities(state, target, resolution):
        """Return the finite Dread damage immunity for one bomb recipient."""
        item_id = resolution.item_id
        if not isinstance(item_id, str):
            return ()
        from .alchemy_content import FORMULAS_BY_ID
        from .opponent_content import PUBLISHED_OPPONENT_PROFILES

        infused = state.infused_alchemy_items.get(item_id)
        formula_id = getattr(infused, "formula_id", None) or item_id
        formula = FORMULAS_BY_ID.get(formula_id)
        if formula is None or formula.formula_id != "dread_ampoule_lesser":
            return ()
        dynamic_immunity = any(
            immunity.target_actor_id == target.actor_id
            and immunity.expires_at_seconds > state.world_time_seconds
            and immunity.kind in {"mental", "poison"}
            for immunity in state.condition_immunities
        )
        published = PUBLISHED_OPPONENT_PROFILES.get(target.definition_id)
        printed_immunity = published is not None and bool(
            {"mental", "poison"} & set(published.condition_immunities)
        )
        if not (dynamic_immunity or printed_immunity):
            return ()
        return (DamageDefense(
            "immunity", "mental", 0,
            source=f"{resolution.source}:dread_ampoule_immunity",
        ),)

    @staticmethod
    def _admitted_bomber_bomb_facts(formula_id, *, character_level=1):
        from .alchemist_content import admitted_bomber_bomb_facts

        return admitted_bomber_bomb_facts(formula_id, character_level=character_level)

    def _admitted_bomber_bomb_facts_for_attack(self, actor, attack_id):
        if not isinstance(attack_id, str):
            return None
        attack = next(
            (candidate for candidate in get_definition(actor.definition_id).attacks if candidate.attack_id == attack_id),
            None,
        )
        return None if attack is None else self._admitted_bomber_bomb_facts(
            attack.item_id, character_level=get_definition(actor.definition_id).level,
        )

    def _damage_modifier(self, state, actor, attack):
        if attack.damage_attribute is None:
            return attack.damage_modifier
        modifiers = condition_modifiers(
            self._conditions_for_actor(state, actor),
            CheckContext("damage", attack.damage_attribute, attack.traits),
        )
        # Enfeebled applies once to Strength damage; Clumsy applies to
        # Dexterity damage.  Keeping both in the shared condition projection
        # avoids the old Strength-only subtraction and prevents double
        # application when an active spell effect is present.
        anthem = self._courageous_anthem_damage_modifiers(state, actor)
        return attack.damage_modifier + combine_modifiers((*modifiers, *anthem))

    @staticmethod
    def _courageous_anthem_damage_modifiers(state, actor):
        """Return the typed Anthem modifiers for one creature's damage rolls."""
        return tuple(
            Modifier(effect.value, "status", "Courageous Anthem")
            for effect in state.active_effects
            if effect.kind == "courageous_anthem" and effect.target_actor_id == actor.actor_id
        ) + tuple(
            Modifier(effect.value, "status", "Stoke the Heart")
            for effect in state.active_effects
            if effect.kind == "stoke_the_heart" and effect.target_actor_id == actor.actor_id
        )

    def _effective_ranged_profile(self, state, actor, attack):
        """Return the finite selected-Bomber range profile for an attack."""
        if attack.max_range_ft is None or attack.range_increment_ft is None:
            return attack.range_increment_ft, attack.max_range_ft
        alchemy_state = state.alchemy_states.get(actor.actor_id)
        if (
            self._admitted_bomber_bomb_facts(
                attack.item_id, character_level=get_definition(actor.definition_id).level,
            ) is None
            or alchemy_state is None
        ):
            return attack.range_increment_ft, attack.max_range_ft
        from .alchemy import bomber_bomb_range_increment

        increment = bomber_bomb_range_increment(alchemy_state, attack.range_increment_ft)
        return increment, increment * 6

    def _strike_targets(self, actor: CreatureState, state: EncounterState, attack=None) -> tuple[str, ...]:
        definition = get_definition(actor.definition_id)
        attacks = (attack,) if attack is not None else tuple(item for item in definition.attacks if self._attack_usable(state, actor, item))
        reachable: list[str] = []
        # Initiative-exempt familiars are still creatures on the map and may
        # be attacked; they simply never receive their own turn.
        for target_id, target in state.creatures.items():
            if target.actor_id == actor.actor_id or target.defeated:
                continue
            if any(
                self._attack_usable(state, actor, item)
                and grid_distance_feet(actor.position, target.position) <= (
                    self._effective_ranged_profile(state, actor, item)[1]
                    if "ranged" in item.traits and item.max_range_ft is not None
                    else item.reach_ft
                )
                for item in attacks
            ):
                reachable.append(target_id)
        return tuple(reachable)

    def _attack_usable(self, state, actor, attack) -> bool:
        from .martial_defense import crane_stance_attack_permitted

        if not crane_stance_attack_permitted(state, actor.actor_id, attack.attack_id):
            return False
        barbarian_state = actor.barbarian_state
        if barbarian_state is not None:
            from .barbarian import animal_attack_ids, attack_allowed_during_rage

            if attack.attack_id in animal_attack_ids(barbarian_state) and barbarian_state.rage is None:
                return False
            if not attack_allowed_during_rage(
                barbarian_state,
                attack_is_weapon=attack.item_id is not None,
                attack_id=attack.attack_id,
            ):
                return False
        return self._attack_equipped(state, actor, attack) and (
            attack.ammunition_id is None or actor.ammunition.get(attack.ammunition_id, 0) > 0
        )

    def _attack_equipped(self, state, actor, attack, *, item_id=None) -> bool:
        if attack.item_id is not None:
            if item_id is None:
                if not self._held_attack_item_ids(state, actor, attack):
                    return False
            elif not self._held_attack_item_id(state, actor, attack, item_id=item_id):
                return False
        if attack.free_hands_required:
            if self._free_hands(state, get_definition(actor.definition_id), actor) < attack.free_hands_required:
                return False
        return True

    def _held_attack_item_ids(self, state, actor, attack):
        """Return held physical or legacy-literal items compatible with attack."""
        if attack.item_id is None:
            return ()
        compatible: list[str] = []
        for held_id in actor.held_items:
            instance = state.item_instances.get(held_id)
            if instance is not None:
                if instance.definition_id == attack.item_id:
                    compatible.append(held_id)
            elif held_id == attack.item_id:
                # Preserve the pre-instance literal equipment contract.
                compatible.append(held_id)
        return tuple(compatible)

    def _held_attack_item_id(self, state, actor, attack, *, item_id=None):
        """Resolve one held item for an attack, retaining its origin identity."""
        if attack.item_id is None:
            if item_id is not None:
                return None
            return None
        compatible = self._held_attack_item_ids(state, actor, attack)
        if item_id is not None:
            return item_id if item_id in compatible else None
        if len(compatible) == 1:
            return compatible[0]
        return None

    def _attack_item_instance(self, state, actor, attack, *, item_id=None):
        if attack.item_id is None:
            return None
        selected = self._held_attack_item_id(state, actor, attack, item_id=item_id)
        if selected is None:
            return None
        instance = state.item_instances.get(selected)
        if instance is not None and instance.definition_id == attack.item_id:
            return instance
        return None

    def _handwrap_instance(self, state, actor):
        for item_id in actor.worn_items:
            instance = state.item_instances.get(item_id)
            if (
                instance is not None
                and instance.invested
                and ITEM_CATEGORIES.get(instance.definition_id) == "handwraps"
            ):
                return instance
        return None

    def _weapon_rune_profile_for_attack(self, state, actor, attack, *, item_id=None):
        if "unarmed" in attack.traits:
            instance = self._handwrap_instance(state, actor)
            profile = weapon_rune_profile_for_item(instance) if instance is not None else None
            runic_body = next((
                effect for effect in state.active_effects
                if effect.kind == "runic_body" and effect.target_actor_id == actor.actor_id
                and effect.source_actor_id in state.creatures
                and effect.expires_at_source_start > state.actor_start_counts.get(effect.source_actor_id, 0)
            ), None)
            if runic_body is None:
                return profile
            from .items import WeaponRuneProfile
            permanent_dice = profile.striking_dice if profile is not None else None
            return WeaponRuneProfile(
                potency=max(profile.potency if profile is not None else 0, 1),
                striking_dice=max(permanent_dice or 1, 2),
                property_runes=profile.property_runes if profile is not None else (),
                handwraps=True,
                source_urls=profile.source_urls if profile is not None else WeaponRuneProfile().source_urls,
            )
        instance = self._attack_item_instance(state, actor, attack, item_id=item_id)
        profile = weapon_rune_profile_for_item(instance) if instance is not None else None
        if instance is None:
            return profile
        temporary = self._active_runic_weapon_effect(state, instance.instance_id)
        if temporary is None:
            return profile
        from .items import WeaponRuneProfile

        permanent_potency = profile.potency if profile is not None else 0
        permanent_dice = profile.striking_dice if profile is not None else None
        return WeaponRuneProfile(
            potency=max(permanent_potency, temporary.potency),
            striking_dice=max(permanent_dice or 1, temporary.striking_dice),
            property_runes=profile.property_runes if profile is not None else (),
            source_urls=(profile.source_urls if profile is not None else WeaponRuneProfile().source_urls),
        )

    def _active_runic_weapon_effect(self, state, item_id):
        """Return a live Runic Weapon effect for an exact item identity."""
        starts = state.actor_start_counts
        for effect in state.active_item_effects:
            if (
                effect.kind == "runic_weapon"
                and effect.item_id == item_id
                and effect.source_actor_id in state.creatures
                and effect.expires_at_source_start > starts.get(effect.source_actor_id, 0)
                and (
                    state.in_progress
                    or effect.expires_at_world_time > state.world_time_seconds
                )
            ):
                return effect
        return None

    def _item_is_magical(self, state, item_id):
        """Report the current magical status of one physical item."""
        item = state.item_instances.get(item_id)
        if item is None:
            return False
        return bool(
            item.rune_ids
            or self._active_runic_weapon_effect(state, item_id)
            or any(
                effect.item_id == item_id
                and (effect.expires_at_world_time is None or effect.expires_at_world_time > state.world_time_seconds)
                for effect in state.active_item_effects
            )
        )

    def _attack_item_potency_modifier(self, state, actor, attack, *, item_id=None):
        profile = self._weapon_rune_profile_for_attack(state, actor, attack, item_id=item_id)
        if profile is None:
            return None
        return weapon_potency_modifier(
            profile,
            unarmed="unarmed" in attack.traits,
            source=("handwraps" if profile.handwraps else "weapon potency"),
        )

    def _select_attack(self, state, actor, attack_id, *, item_id=None):
        attacks = get_definition(actor.definition_id).attacks
        if any(effect.kind == "alchemy_bestial_mutagen_lesser" and effect.target_actor_id == actor.actor_id for effect in state.active_effects):
            attacks = (*attacks, AttackDefinition("bestial_claws", "Bestial Claws", 3, 5, frozenset({"melee", "unarmed", "agile"}), "slashing", (4,), 0, attack_attribute="strength", striking_applies=False), AttackDefinition("bestial_jaws", "Bestial Jaws", 3, 5, frozenset({"melee", "unarmed"}), "piercing", (6,), 0, attack_attribute="strength", striking_applies=False))
        candidates = attacks if attack_id is None else tuple(a for a in attacks if a.attack_id == attack_id)
        if item_id is not None and (
            not isinstance(item_id, str) or not item_id
        ):
            raise _Rejected("Strike item_id must be a non-empty held item identity.")
        if item_id is not None:
            return next(
                (
                    attack for attack in candidates
                    if attack.item_id is not None
                    and item_id in self._held_attack_item_ids(state, actor, attack)
                    and self._attack_usable(state, actor, attack)
                ),
                None,
            )
        for attack in candidates:
            if not self._attack_usable(state, actor, attack):
                continue
            if attack.item_id is not None:
                compatible = self._held_attack_item_ids(state, actor, attack)
                if len(compatible) > 1:
                    raise _Rejected(
                        f"Multiple held {attack.name} items are compatible; select item_id explicitly."
                    )
            return attack
        return None

    @staticmethod
    def _attack_damage_types(attack) -> tuple[str, ...]:
        types = [attack.damage_type]
        for trait, damage_type in (("versatile-p", "piercing"), ("versatile-s", "slashing"), ("versatile-b", "bludgeoning")):
            if trait in attack.traits and damage_type not in types:
                types.append(damage_type)
        return tuple(types)

    def _attack_dc(
        self,
        state,
        actor,
        target,
        attack,
        *,
        feint_off_guard: bool | None = None,
        target_off_guard: bool | None = None,
        nimble_dodge: bool = False,
        hunter_aim_intent=None,
    ) -> int:
        if feint_off_guard is None:
            feint_off_guard = self._feint_off_guard_applies(state, actor, target, attack)
        if target_off_guard is None:
            target_off_guard = self._attacker_off_guard(
                state, actor, target, attack, feint_off_guard=feint_off_guard
            )
        return self._effective_ac(
            target,
            state=state,
            off_guard=target_off_guard,
            lesser_cover=(
                False if hunter_aim_intent is not None
                else self._has_lesser_cover(state, actor, target)
            ),
            attacker_id=actor.actor_id,
            taking_cover=("ranged" in attack.traits and target.actor_id in state.taking_cover),
            feint_off_guard=feint_off_guard,
            nimble_dodge=nimble_dodge,
        )

    def _attacker_off_guard(
        self,
        state,
        attacker,
        target,
        attack,
        *,
        feint_off_guard: bool | None = None,
        tumble_behind_off_guard: bool | None = None,
    ) -> bool:
        """Snapshot one attacker's relation to its target before the roll.

        The snapshot is deliberately source-relative: prone/unconscious and
        retained conditions apply generally, while flanking, Feint, and
        Surprise Attack are evaluated for this attacker and this target.
        """
        if feint_off_guard is None:
            feint_off_guard = self._feint_off_guard_applies(state, attacker, target, attack)
        if tumble_behind_off_guard is None:
            tumble_behind_off_guard = self._tumble_behind_off_guard_applies(
                state, attacker, target
            )
        condition_off_guard = any(
            condition.kind == "off_guard"
            for condition in self._conditions_for_actor(state, target)
        )
        flanked = (
            "melee" in attack.traits
            and "ranged" not in attack.traits
            and not target.unconscious
            and not target.prone
            and self._is_flanked(state, attacker, target)
        )
        definition = get_definition(attacker.definition_id)
        initiative_skill = state.initiative_skills.get(attacker.actor_id, "perception")
        surprise = surprise_attack_applies(
            round_number=state.round_number,
            initiative_skill=initiative_skill,
            target_has_acted=state.actor_start_counts.get(target.actor_id, 0) > 0,
            has_surprise_attack="surprise_attack" in definition.abilities,
        )
        return bool(
            target.unconscious
            or target.prone
            or condition_off_guard
            or flanked
            or feint_off_guard
            or tumble_behind_off_guard
            or surprise
        )

    def _feint_off_guard_applies(self, state, attacker, target, attack) -> bool:
        if "melee" not in attack.traits or "ranged" in attack.traits:
            return False
        from .skill_actions import feint_off_guard_applies

        return feint_off_guard_applies(
            tuple(state.feint_off_guard_effects),
            attacker_id=attacker.actor_id,
            target_id=target.actor_id,
            attack_traits=frozenset({"melee"}),
            actor_end_counts=state.actor_end_counts,
        )

    def _commit_feint_strike(self, state, attacker, target, attack) -> bool:
        applies = self._feint_off_guard_applies(state, attacker, target, attack)
        if applies:
            from .skill_actions import consume_feint_off_guard_on_attack

            state.feint_off_guard_effects = list(consume_feint_off_guard_on_attack(
                tuple(state.feint_off_guard_effects),
                attacker_id=attacker.actor_id,
                target_id=target.actor_id,
                attack_traits=frozenset({"melee"}),
                actor_end_counts=state.actor_end_counts,
            ))
        return applies

    @staticmethod
    def _tumble_behind_off_guard_applies(state, attacker, target) -> bool:
        from .movement_progression import tumble_behind_applies

        return tumble_behind_applies(
            tuple(state.tumble_behind_exposures),
            attacker_id=attacker.actor_id,
            target_id=target.actor_id,
            actor_end_counts=state.actor_end_counts,
        )

    def _commit_tumble_behind_strike(self, state, attacker, target) -> bool:
        applies = self._tumble_behind_off_guard_applies(state, attacker, target)
        # The effect expires on the source's next attack, irrespective of the
        # eventual target.  Its target still determines off-guard here.
        from .movement_progression import consume_tumble_behind_on_attack

        state.tumble_behind_exposures = list(consume_tumble_behind_on_attack(
            tuple(state.tumble_behind_exposures),
            attacker_id=attacker.actor_id,
            target_id=target.actor_id,
            actor_end_counts=state.actor_end_counts,
        ))
        return applies

    def _encumbered(self, state, actor: CreatureState) -> bool:
        """Apply Bulk carried in the authored definition to the current load."""
        definition = get_definition(actor.definition_id)
        bulk_by_item = dict(definition.carried_item_bulk)
        carried = (*actor.held_items, *actor.worn_items, *actor.stowed_items)
        bulk = sum(bulk_by_item.get(item_id, 0) for item_id in carried)
        strength = dict(definition.ability_modifiers).get("strength", 0)
        return bulk > max(0, 5 + strength)

    def _nimble_dodge_available(self, state, attacker, target) -> bool:
        """Check Nimble Dodge's pre-attack trigger from current state facts."""
        definition = get_definition(target.definition_id)
        modifier = nimble_dodge_modifier(
            has_feat="Nimble Dodge" in definition.feats,
            reaction_available=target.reaction_available,
            attacker_visible=True,
            encumbered=self._encumbered(state, target),
            attacker_targets_rogue_with_attack=True,
        )
        return modifier is not None and not target.unconscious and not target.dead

    def _reactive_shield_available(self, state, attacker, target) -> bool:
        definition = get_definition(target.definition_id)
        return (
            ("Reactive Shield" in definition.feats or "reactive_shield" in definition.abilities)
            and target.reaction_available
            and not target.unconscious
            and not target.dead
            and self._held_shield_instance(state, target) is not None
            and not attacker.unconscious
            and not attacker.dead
        )

    def _present_nimble_dodge(self, state, attacker, target, continuation) -> None:
        continuation.nimble_dodge_decided = False
        self._set_pending(
            state,
            kind="nimble_dodge",
            owner_actor_id=target.actor_id,
            prompt=f"{target.label} may use Nimble Dodge before {attacker.label}'s attack roll.",
            options=(
                ChoiceOption("use", "Use Nimble Dodge (+2 AC)"),
                ChoiceOption("decline", "Decline"),
            ),
            details=(
                f"{attacker.label} is visible and targets {target.label}; +2 circumstance AC against this attack only.",
                "Using Nimble Dodge spends the Rogue's shared reaction.",
            ),
            actor_id=attacker.actor_id,
            target_id=target.actor_id,
            attack_id=continuation.attack_id,
            attack_penalty=continuation.attack_penalty,
            attack_count=continuation.attack_count,
            damage_type=continuation.damage_type,
            nonlethal=continuation.nonlethal,
            attack_actions_cost=continuation.attack_actions_cost,
            attack_count_cost=continuation.attack_count_cost,
            ranged_penalty=continuation.ranged_penalty,
            feint_off_guard_applied=continuation.feint_off_guard_applied,
            attack_target_off_guard=continuation.attack_target_off_guard,
            nimble_dodge_used=continuation.nimble_dodge_used,
            is_reaction=continuation.kind == "reaction_strike",
            continuation=continuation,
        )

    def _present_reactive_shield_after_hit(
        self, state, attacker, target, attack, check, *, damage_type,
        nonlethal, damage_bonus_dice, attack_target_off_guard, item_id,
        investigator_strategic_strike, investigator_use_intelligence,
        bomber_only_primary_splash, parent_continuation,
    ) -> None:
        if parent_continuation is not None:
            parent_continuation.reactive_shield_decided = True
        continuation = ActionContinuation(
            kind="reactive_shield",
            actor_id=attacker.actor_id,
            target_id=target.actor_id,
            attack_id=attack.attack_id,
            attack_penalty=check.map_penalty,
            attack_count=check.attack_count or 1,
            reactive_shield_decided=True,
            parent_continuation=parent_continuation,
        )
        self._set_pending(
            state,
            kind="reactive_shield",
            owner_actor_id=target.actor_id,
            prompt=f"{target.label} was hit by {attacker.label}'s melee Strike and may use Reactive Shield.",
            options=(
                ChoiceOption("use", "Use Reactive Shield (+2 AC)"),
                ChoiceOption("decline", "Decline"),
            ),
            details=(
                f"Raise the held shield immediately; its +2 circumstance AC applies to the triggering attack.",
                "Using Reactive Shield spends the target's shared reaction.",
            ),
            actor_id=attacker.actor_id,
            target_id=target.actor_id,
            attack_id=attack.attack_id,
            attack_penalty=check.map_penalty,
            attack_count=check.attack_count or 1,
            check=check,
            item_id=item_id,
            damage_type=damage_type,
            nonlethal=nonlethal,
            damage_bonus_dice=damage_bonus_dice,
            attack_target_off_guard=attack_target_off_guard,
            damage_context=("bomber_only_primary" if bomber_only_primary_splash else None),
            continuation=continuation,
        )

    def _is_flanked(self, state, attacker, target) -> bool:
        own_definition = get_definition(attacker.definition_id)
        if attacker.unconscious or attacker.dead or not any("melee" in a.traits and self._attack_usable(state, attacker, a) for a in own_definition.attacks):
            return False
        for ally in state.creatures.values():
            if ally.actor_id in (attacker.actor_id, target.actor_id) or ally.team != attacker.team or ally.unconscious or ally.dead or ally.defeated:
                continue
            definition = get_definition(ally.definition_id)
            if not any(
                "melee" in attack.traits
                and self._attack_usable(state, ally, attack)
                and grid_distance_feet(ally.position, target.position) <= attack.reach_ft
                for attack in definition.attacks
            ):
                continue
            if flanking_geometry(attacker.position, ally.position, target.position):
                return True
        return False

    def _has_lesser_cover(self, state, attacker, target) -> bool:
        return any(
            other.actor_id not in (attacker.actor_id, target.actor_id)
            and segment_crosses_cell_interior(attacker.position, target.position, other.position)
            for other in state.creatures.values()
        )

    def _pack_attack_applies(self, state, attacker, target) -> bool:
        allies_in_reach = 0
        for ally in state.creatures.values():
            if ally.actor_id in (attacker.actor_id, target.actor_id) or ally.team != attacker.team:
                continue
            if ally.dead:
                # A dead creature is an object and is no longer a creature ally.
                continue
            definition = get_definition(ally.definition_id)
            if any(
                "melee" in attack.traits
                and grid_distance_feet(ally.position, target.position) <= attack.reach_ft
                for attack in definition.attacks
            ):
                allies_in_reach += 1
        return allies_in_reach >= 2

    def _interact_options(self, actor, state) -> tuple[tuple[str, str], ...]:
        choices: list[tuple[str, str]] = []
        if len(actor.held_items) < 2:
            drawable_items = {
                attack.item_id
                for attack in get_definition(actor.definition_id).attacks
                if attack.item_id is not None
            }
            shield_instances = {
                instance_id for instance_id in actor.worn_items + actor.stowed_items
                if self._shield_profile(state.item_instances.get(instance_id)) is not None
            }
            drawable_instances = {
                instance_id for instance_id in actor.worn_items + actor.stowed_items
                if (instance := state.item_instances.get(instance_id)) is not None
                and (
                    instance.definition_id in drawable_items
                    or instance_id in state.infused_alchemy_items
                    or is_drawable_equipment_definition(instance.definition_id)
                )
            }
            choices.extend(
                ("draw", item)
                for item in actor.worn_items
                if (item in drawable_items or item in shield_instances or item in drawable_instances)
                and item not in actor.held_items
            )
            choices.extend(
                ("draw", item)
                for item in actor.stowed_items
                if (item in drawable_items or item in shield_instances or item in drawable_instances)
                and item not in actor.held_items
            )
            choices.extend(
                ("retrieve", item_id)
                for position, item_ids in (state.ground_items or {}).items()
                if grid_distance_feet(actor.position, position) <= 5
                for item_id in item_ids
            )
        choices.extend(("stow", item) for item in actor.held_items)
        choices.extend(
            ("toggle_sigil", effect.effect_id)
            for effect in state.active_effects
            if effect.kind == "sigil"
            and effect.source_actor_id == actor.actor_id
            and effect.expires_at_world_time is not None
            and effect.expires_at_world_time > state.world_time_seconds
            and effect.target_actor_id in state.creatures
            and grid_distance_feet(actor.position, state.creatures[effect.target_actor_id].position) <= 5
        )
        choices.extend(
            ("remove_glue", effect.effect_id)
            for effect in state.active_effects
            if effect.kind == "alchemy_glue_bomb_lesser"
            and effect.target_actor_id in state.creatures
            and not state.creatures[effect.target_actor_id].dead
            and grid_distance_feet(actor.position, state.creatures[effect.target_actor_id].position) <= 5
            and effect.glue_removal_actions < 3
        )
        choices.extend(
            ("toggle_sigil", effect.effect_id)
            for effect in state.active_item_effects
            if effect.kind == "sigil"
            and effect.source_actor_id == actor.actor_id
            and (effect.expires_at_world_time is None or effect.expires_at_world_time > state.world_time_seconds)
            and (position := self._item_position(state, effect.item_id)) is not None
            and grid_distance_feet(actor.position, position) <= 5
        )
        return tuple(choices)

    def _interact(self, state, dice, actor, command: Interact) -> list[Event]:
        if actor.must_leave_occupied:
            raise _Rejected("Move out of the occupied ally's space before Interacting.")
        self._require_action_permitted(state, actor, "interact", frozenset({"manipulate"}))
        if (command.mode, command.item_id) not in self._interact_options(actor, state):
            raise _Rejected("That Interact mode and item are not currently available.")
        actor.actions_remaining -= 1
        if command.mode == "toggle_sigil":
            effect = next((item for item in state.active_effects if item.effect_id == command.item_id), None)
            if effect is not None:
                state.active_effects[state.active_effects.index(effect)] = replace(effect, value=2 if effect.value == 1 else 1)
                visible = effect.value != 1
            else:
                item_effect = next((item for item in state.active_item_effects if item.effect_id == command.item_id), None)
                if item_effect is None:
                    raise _Rejected("That Sigil is no longer active.")
                state.active_item_effects[state.active_item_effects.index(item_effect)] = replace(item_effect, visible=not item_effect.visible)
                visible = not item_effect.visible
            return self._complete_action(state, actor, [Event(
                "sigil_toggled", actor.actor_id, None,
                f"{actor.label} makes the touched Sigil {'visible' if visible else 'invisible'}.",
            )], dice=dice)
        continuation = ActionContinuation(
            kind="interact",
            actor_id=actor.actor_id,
            mode=command.mode,
            item_id=command.item_id,
            movement_kind="manipulate",
            must_disrupt_on_critical=True,
            seen_reactors=[],
        )
        events = [Event("interact_started", actor.actor_id, None, f"{command.mode.title()} {command.item_id} committed.")]
        return events + self._advance_continuation(state, dice, continuation)

    def _take_cover(self, state, dice, actor):
        if not actor.prone:
            raise _Rejected("Take Cover is only available while prone in this prototype.")
        if actor.actor_id in state.taking_cover:
            raise _Rejected("The actor is already taking cover.")
        if actor.actions_remaining < 1:
            raise _Rejected("Take Cover requires one action.")
        actor.actions_remaining -= 1
        state.taking_cover.add(actor.actor_id)
        events = [Event("take_cover", actor.actor_id, None, f"{actor.label} takes cover while prone; +4 circumstance AC against ranged attacks.")]
        return self._complete_action(state, actor, events, dice=dice)

    def _raise_shield(self, state, dice, actor):
        self._require_action_permitted(state, actor, "raise_shield", frozenset())
        shield = self._held_shield_instance(state, actor)
        if shield is None:
            raise _Rejected("Raise a Shield requires an intact shield held in one hand.")
        actor.actions_remaining -= 1
        state.raised_shields[actor.actor_id] = RaisedShieldState(
            shield.instance_id,
            state.actor_start_counts.get(actor.actor_id, 0) + 1,
        )
        events = [Event(
            "shield_raised", actor.actor_id, None,
            f"{actor.label} raises the steel shield; +2 circumstance AC until their next turn starts.",
        )]
        return self._complete_action(state, actor, events, dice=dice)

    def _lingering_composition(self, state, actor) -> list[Event]:
        definition = get_definition(actor.definition_id)
        if (
            "lingering_composition" not in definition.abilities
            or not any(spell.spell_id == "lingering_composition" for spell in definition.focus_spells)
        ):
            raise _Rejected("This actor has not learned Lingering Composition.")
        if actor.lingering_composition_pending:
            raise _Rejected("Lingering Composition is already waiting for its next composition cantrip.")
        if actor.focus_points < 1:
            raise _Rejected("Lingering Composition requires 1 Focus Point.")
        self._require_action_permitted(
            state, actor, "lingering_composition", frozenset({"concentrate"})
        )
        actor.focus_points -= 1
        actor.lingering_composition_pending = True
        return [Event(
            "lingering_composition_started", actor.actor_id, actor.actor_id,
            f"{actor.label} spends 1 Focus Point on Lingering Composition; their next action must cast a one-round composition cantrip.",
        )]

    def _resolve_lingering_composition(self, state, dice, actor, events: list[Event]) -> list[Event]:
        """Resolve Lingering only after its immediately following Anthem cast."""
        actor.lingering_composition_pending = False
        effects = [
            effect for effect in state.active_effects
            if effect.kind == "courageous_anthem" and effect.source_actor_id == actor.actor_id
        ]
        if not effects:
            raise _Rejected("Lingering Composition requires the next action to create a one-round composition effect.")
        highest_level = max(
            get_definition(state.creatures[effect.target_actor_id].definition_id).level
            for effect in effects
        )
        # Bounded standard-difficulty level DCs for the levels represented by
        # supported Bard recipients.  A GM-specific override remains outside
        # this literal fixture contract.
        standard_dc = {-1: 13, 0: 14, 1: 15, 2: 16}.get(highest_level)
        if standard_dc is None:
            raise _Unsupported("Lingering Composition needs an authored standard level DC for this target level.")
        performance = self._skill_modifier(get_definition(actor.definition_id), "performance")
        check = replace(
            resolve_check(dice.draw(20), performance, standard_dc),
            modifier_breakdown=(Modifier(performance, "untyped", "printed Performance"),),
        )
        if actor.health_mode is HealthMode.PC and actor.hero_points > 0:
            self._set_pending(
                state, kind="lingering_composition_hero_reroll", owner_actor_id=actor.actor_id,
                prompt=f"{actor.label} may keep this Lingering Composition Performance check or spend 1 Hero Point to reroll.",
                options=(ChoiceOption("keep", "Keep result"), ChoiceOption("spend_hero_point", "Spend 1 Hero Point and reroll")),
                actor_id=actor.actor_id, check=check, check_kind="skill_check",
                target_ids=tuple(sorted(effect.target_actor_id for effect in effects)),
            )
            return events + [Event("lingering_composition_check", actor.actor_id, None, "Lingering Composition Performance check awaits a Hero Point choice.", check=check)]
        return events + self._finalize_lingering_composition(state, actor, check)

    def _finalize_lingering_composition(self, state, actor, check) -> list[Event]:
        rounds = 4 if check.degree is DegreeOfSuccess.CRITICAL_SUCCESS else 3 if check.degree is DegreeOfSuccess.SUCCESS else 1
        if rounds == 1:
            actor.focus_points = min(actor.focus_capacity, actor.focus_points + 1)
        expires = state.actor_start_counts.get(actor.actor_id, 0) + rounds
        state.active_effects[:] = [
            replace(
                effect,
                expires_at_source_start=expires,
                expires_at_world_time=state.world_time_seconds + rounds * 6,
            )
            if effect.kind == "courageous_anthem" and effect.source_actor_id == actor.actor_id
            else effect
            for effect in state.active_effects
        ]
        refund = " Focus Point refunded." if rounds == 1 else ""
        return [Event(
            "lingering_composition_resolved", actor.actor_id, None,
            f"Lingering Composition {check.degree.label().lower()}: Courageous Anthem lasts {rounds} round(s).{refund}",
            check=check,
        )]

    def _cast(self, state, dice, actor, command: Cast):
        unsupported = self._dim_targeted_spell_unsupported(state, actor, command)
        if unsupported is not None:
            raise _Unsupported(unsupported)
        from . import family_casting

        context = FamilyProcedureContext(
            self, state, dice, actor, get_definition(actor.definition_id), "casting"
        )
        result = family_casting.begin_cast(context, command)
        return self._family_result_events(result, "casting")

    def _light_control_available(
        self, state: EncounterState, actor: CreatureState, control: str
    ) -> bool:
        """Whether the active actor can currently control one owned Light orb."""
        return (
            control in {"sustain", "dismiss"}
            and any(orb.caster_actor_id == actor.actor_id for orb in state.light_orbs)
            and self._action_permitted(
                state, actor, f"{control}_light", frozenset({"concentrate"})
            )
        )

    def _light_orb_index_for_control(
        self, state: EncounterState, actor: CreatureState, orb_id: str
    ) -> int:
        """Resolve an owned, active Light orb for Sustain or Dismiss."""
        if not isinstance(orb_id, str) or not orb_id:
            raise _Rejected("Light control requires a non-empty orb_id.")
        index = next(
            (index for index, orb in enumerate(state.light_orbs) if orb.stable_id == orb_id),
            None,
        )
        if index is None:
            raise _Rejected("That Light orb is no longer active.")
        if state.light_orbs[index].caster_actor_id != actor.actor_id:
            raise _Rejected("Only the Light's caster can control that orb.")
        return index

    def _sustain_light(
        self, state: EncounterState, dice: DiceSource, actor: CreatureState, command: Sustain
    ) -> list[Event]:
        """Spend one action to move, detach, or offer attachment of a Light orb."""
        hex_effect = next(
            (effect for effect in state.active_effects
             if effect.effect_id == command.orb_id
             and effect.source_actor_id == actor.actor_id
             and effect.kind == "stoke_the_heart"),
            None,
        )
        if hex_effect is not None:
            if command.point is not None or command.attachment_actor_id is not None:
                raise _Rejected("Sustain Stoke the Heart takes no movement or attachment selection.")
            self._require_action_permitted(state, actor, "sustain_stoke_the_heart", frozenset({"concentrate"}))
            continuation = ActionContinuation(
                kind="witch_sustain_stoke",
                actor_id=actor.actor_id,
                target_id=hex_effect.target_actor_id,
                spell_id="stoke_the_heart",
                spell_actions=1,
                item_id=hex_effect.effect_id,
            )
            timing = self._offer_restored_spirit_timing(
                state, actor, continuation, effect_id=hex_effect.effect_id,
                action_name="sustaining Stoke the Heart",
            )
            if timing:
                return timing
            return self._commit_sustain_stoke(state, dice, actor, continuation)
        ward_effect = next(
            (effect for effect in state.active_effects
             if effect.effect_id == command.orb_id
             and effect.source_actor_id == actor.actor_id
             and effect.kind == "forbidding_ward"),
            None,
        )
        if ward_effect is not None:
            if command.point is not None or command.attachment_actor_id is not None:
                raise _Rejected("Sustain Forbidding Ward takes no movement or attachment selection.")
            self._require_action_permitted(
                state, actor, "sustain_forbidding_ward", frozenset({"concentrate"})
            )
            actor.actions_remaining -= 1
            refreshed = replace(
                ward_effect,
                sustain_expires_at_source_end=state.actor_end_counts.get(actor.actor_id, 0) + 2,
            )
            state.active_effects[state.active_effects.index(ward_effect)] = refreshed
            return self._complete_action(state, actor, [Event(
                "forbidding_ward_sustained", actor.actor_id, ward_effect.target_actor_id,
                f"{actor.label} sustains Forbidding Ward protecting "
                f"{state.creatures[ward_effect.target_actor_id].label} from "
                f"{state.creatures[ward_effect.selected_enemy_actor_id or ''].label}'s effects.",
            )], dice=dice)
        self._require_action_permitted(
            state, actor, "sustain_light", frozenset({"concentrate"})
        )
        orb_index = self._light_orb_index_for_control(state, actor, command.orb_id)
        orb = state.light_orbs[orb_index]
        current = self._light_orb_position(state, orb)
        if current is None:
            raise _Rejected("The Light orb's carrier is no longer available.")
        if command.point is not None and not isinstance(command.point, Position):
            raise _Rejected("Sustain's point must be a grid position.")
        if command.attachment_actor_id is not None:
            attached = state.creatures.get(command.attachment_actor_id)
            if attached is None:
                raise _Rejected("Light's attachment actor does not exist.")
            destination = attached.position
            if command.point is not None and command.point != destination:
                raise _Rejected(
                    "Light's attachment point must match the carrier's current space."
                )
        elif command.point is not None:
            attached = None
            destination = command.point
        elif orb.attached_actor_id is not None:
            # A bare Sustain on an attached orb is the explicit detach form.
            attached = None
            destination = current
        else:
            # A bare Sustain on an unattached orb keeps it in place while
            # paying the concentrate action; this is useful for repeating
            # Sustain without imposing a turn-based lifetime rule.
            attached = None
            destination = current
        if not in_bounds(destination, state.map_width, state.map_height):
            raise _Rejected("Light's sustained point must be inside the encounter map.")
        distance = grid_distance_feet(current, destination)
        if distance > 60:
            raise _Rejected(
                f"Sustain can move a Light orb only 60 feet; requested movement is {distance} feet."
            )

        # The action is committed only after every ownership, map, range, and
        # carrier fact is valid. A declined attachment still leaves the orb at
        # this successfully sustained destination.
        actor.actions_remaining -= 1
        state.light_orbs[orb_index] = replace(
            orb, point=destination, attached_actor_id=None
        )
        events = [Event(
            "light_orb_sustained",
            actor.actor_id,
            attached.actor_id if attached is not None else None,
            f"{actor.label} sustains Light orb {orb.stable_id} to {_coord(destination)}.",
            position=destination,
            details=(orb.stable_id, str(distance)),
        )]
        if attached is None:
            return self._complete_action(state, actor, events, dice=dice)

        continuation = ActionContinuation(
            kind="cast",
            actor_id=actor.actor_id,
            target_id=attached.actor_id,
            spell_id="light",
            spell_target_id=attached.actor_id,
            spell_actions=1,
            stage="sustain",
            light_control="sustain",
            light_point=destination,
            light_attachment_actor_id=attached.actor_id,
            light_orb_id=orb.stable_id,
        )
        self._set_pending(
            state,
            kind="spell_willingness",
            owner_actor_id=(
                attached.actor_id if attached.health_mode is HealthMode.PC else None
            ),
            prompt=f"Is {attached.label} willing to carry the Light orb?",
            options=(ChoiceOption("willing", "Willing"), ChoiceOption("unwilling", "Unwilling")),
            actor_id=actor.actor_id,
            target_id=attached.actor_id,
            spell_id="light",
            spell_actions=1,
            continuation=continuation,
        )
        events.append(Event(
            "spell_willingness",
            actor.actor_id,
            attached.actor_id,
            f"Ask {attached.label} whether to carry Light orb {orb.stable_id}.",
        ))
        return events

    def _dismiss_light(
        self, state: EncounterState, dice: DiceSource, actor: CreatureState, command: Dismiss
    ) -> list[Event]:
        """Spend one action to remove an owned Light orb."""
        self._require_action_permitted(
            state, actor, "dismiss_light", frozenset({"concentrate"})
        )
        orb_index = self._light_orb_index_for_control(state, actor, command.orb_id)
        orb = state.light_orbs.pop(orb_index)
        actor.actions_remaining -= 1
        position = self._light_orb_position(state, orb)
        events = [Event(
            "light_orb_dismissed",
            actor.actor_id,
            None,
            f"{actor.label} dismisses Light orb {orb.stable_id}.",
            position=position,
            details=(orb.stable_id,),
        )]
        return self._complete_action(state, actor, events, dice=dice)

    def _dismiss_life_link(
        self, state: EncounterState, dice: DiceSource, actor: CreatureState, command: Dismiss,
    ) -> list[Event]:
        """Dismiss the Oracle's one bounded Life Link without spending an action."""
        if command.orb_id is not None or not isinstance(command.effect_id, str) or not command.effect_id:
            raise _Rejected("Dismiss Life Link requires exactly its active effect id.")
        self._require_action_permitted(state, actor, "dismiss_life_link", frozenset({"concentrate"}))
        effect = next(
            (item for item in state.active_effects
             if item.effect_id == command.effect_id
             and item.kind == "life_link"
             and item.source_actor_id == actor.actor_id),
            None,
        )
        if effect is None:
            raise _Rejected("Life Link is no longer active for this Oracle.")
        state.active_effects.remove(effect)
        return self._complete_action(state, actor, [Event(
            "life_link_dismissed", actor.actor_id, effect.target_actor_id,
            f"{actor.label} dismisses Life Link to {state.creatures[effect.target_actor_id].label}.",
            details=(effect.effect_id,),
        )], dice=dice)

    def _commit_sustain_stoke(self, state, dice, actor, continuation):
        effect = next(
            (item for item in state.active_effects
             if item.effect_id == continuation.item_id
             and item.kind == "stoke_the_heart"
             and item.source_actor_id == actor.actor_id),
            None,
        )
        if effect is None:
            raise _Rejected("The saved Stoke the Heart effect is no longer available.")
        self._require_action_permitted(state, actor, "sustain_stoke_the_heart", frozenset({"concentrate"}))
        actor.actions_remaining -= 1
        refreshed = replace(
            effect,
            sustain_expires_at_source_end=state.actor_end_counts.get(actor.actor_id, 0) + 2,
        )
        state.active_effects[state.active_effects.index(effect)] = refreshed
        return [Event(
            "stoke_the_heart_sustained", actor.actor_id, effect.target_actor_id,
            f"{actor.label} sustains Stoke the Heart on {state.creatures[effect.target_actor_id].label}.",
        )]

    def _offer_restored_spirit_choice(self, state, caster, events, *, dice):
        """Pause immediately after a Flamekeeper hex action for its recipient.

        This is deliberately a small saved continuation, not a generic
        reaction framework: the patron permits the optional benefit only
        directly before or after casting or sustaining a hex.
        """
        familiar = next(
            (candidate for candidate in state.creatures.values()
             if self._familiar_owned_by(caster, candidate)
             and not candidate.dead and not candidate.unconscious),
            None,
        )
        start = state.actor_start_counts.get(caster.actor_id, 0)
        if (
            familiar is None
            or caster.witch_restored_spirit_used_start == start
            or "restored_spirit" not in self._definition_abilities(caster)
        ):
            return self._complete_action(state, caster, events, dice=dice)
        recipients = tuple(
            candidate for candidate in state.creatures.values()
            if not candidate.dead
            and not candidate.unconscious
            and grid_distance_feet(familiar.position, candidate.position) <= 15
        )
        if not recipients:
            return self._complete_action(state, caster, events, dice=dice)
        self._set_pending(
            state, kind="witch_restored_spirit", owner_actor_id=caster.actor_id,
            prompt="Choose a willing creature within 15 feet of the familiar for Restored Spirit.",
            options=tuple(ChoiceOption(candidate.actor_id, candidate.label) for candidate in recipients),
            actor_id=caster.actor_id,
            target_ids=tuple(candidate.actor_id for candidate in recipients),
        )
        return events

    def _restored_spirit_recipients(self, state, caster):
        familiar = next(
            (candidate for candidate in state.creatures.values()
             if self._familiar_owned_by(caster, candidate)
             and not candidate.dead and not candidate.unconscious),
            None,
        )
        if familiar is None:
            return familiar, ()
        return familiar, tuple(
            candidate for candidate in state.creatures.values()
            if not candidate.dead
            and not candidate.unconscious
            and grid_distance_feet(familiar.position, candidate.position) <= 15
        )

    def _offer_restored_spirit_timing(
        self, state, caster, continuation, *, effect_id=None, pre_recipients=None,
        action_name="casting Stoke the Heart", family_command=None,
    ):
        """Save the patron's explicit before/after hex trigger window."""
        familiar, recipients = self._restored_spirit_recipients(state, caster)
        start = state.actor_start_counts.get(caster.actor_id, 0)
        if (
            familiar is None or caster.witch_restored_spirit_used_start == start
            or "restored_spirit" not in self._definition_abilities(caster)
            or not recipients
        ):
            return []
        before_recipients = recipients if pre_recipients is None else pre_recipients
        self._set_pending(
            state, kind="witch_restored_spirit_timing", owner_actor_id=caster.actor_id,
            prompt=f"Use Restored Spirit before or after {action_name}?",
            options=(
                ChoiceOption("after", "After the hex"),
                *tuple(ChoiceOption(f"before:{candidate.actor_id}", f"Before the hex: {candidate.label}") for candidate in before_recipients),
            ),
            actor_id=caster.actor_id,
            target_ids=tuple(candidate.actor_id for candidate in before_recipients),
            continuation=continuation, spell_id="stoke_the_heart", spell_actions=1,
            effect_id=effect_id, family_command=family_command,
        )
        return [Event("restored_spirit_timing", familiar.actor_id, None,
                      f"Choose whether Restored Spirit occurs before or after {action_name}.")]

    def _grant_restored_spirit(self, state, caster, target) -> None:
        start = state.actor_start_counts.get(caster.actor_id, 0)
        target.temporary_hp = 2
        target.temporary_hp_source_id = f"restored_spirit:{caster.actor_id}:{start}"
        target.temporary_hp_expires_at_seconds = None
        target.temporary_hp_expires_at_source_start = start + 1
        caster.witch_restored_spirit_used_start = start

    def _offer_restored_spirit_temp_hp_choice(
        self, state, caster, familiar, target, continuation, *, timing, family_command=None,
    ) -> None:
        self._set_pending(
            state,
            kind="witch_restored_spirit_temp_hp",
            owner_actor_id=target.actor_id,
            prompt=f"{target.label} already has temporary HP. Keep it or gain Restored Spirit's 2 temporary HP?",
            options=(
                ChoiceOption("keep_existing", "Keep existing temporary HP"),
                ChoiceOption("gain_new", "Gain 2 temporary HP"),
            ),
            actor_id=caster.actor_id,
            target_id=target.actor_id,
            effect_id=familiar.actor_id,
            continuation=continuation,
            transition_kind=timing,
            family_command=family_command,
        )

    def _offer_restored_spirit_willingness(
        self, state, caster, familiar, target, continuation, *, timing, family_command=None,
    ) -> None:
        self._set_pending(
            state,
            kind="witch_restored_spirit_willingness",
            owner_actor_id=target.actor_id,
            prompt=f"Is {target.label} willing to receive Restored Spirit?",
            options=(ChoiceOption("willing", "Willing"), ChoiceOption("unwilling", "Unwilling")),
            actor_id=caster.actor_id,
            target_id=target.actor_id,
            effect_id=familiar.actor_id,
            continuation=continuation,
            transition_kind=timing,
            family_command=family_command,
        )

    def _resume_restored_spirit_trigger(self, state, dice, caster, continuation, family_command=None):
        if continuation.kind == "cast":
            return self._resolve_cast(state, dice, continuation)
        if continuation.kind in {"witch_sustain_stoke", "witch_patrons_puppet"}:
            if continuation.kind == "witch_sustain_stoke":
                return self._complete_action(
                    state, caster, self._commit_sustain_stoke(state, dice, caster, continuation), dice=dice,
                )
            from .witch import PatronsPuppet
            if not isinstance(family_command, PatronsPuppet):
                raise _Rejected("Restored Spirit has no saved Patron's Puppet command.")
            return self._run_family_action(state, dice, caster, family_command)
        raise _Rejected("Restored Spirit has no valid saved hex action.")

    def _dim_targeted_spell_unsupported(
        self, state: EncounterState, actor: CreatureState, command: Cast
    ) -> str | None:
        """Reject dim-light spell routes that still lack a targeting gate."""
        if state.ambient_light != "dim" or get_definition(actor.definition_id).vision != "ordinary":
            return None
        # Creature-targeted spells admitted by the shared continuation reach
        # their own legal-target, reaction, and concealment flow below. Keep
        # this hook available for future dim routes without treating unknown
        # or globally unavailable spells as a concealment-specific failure.
        return None

    def _runic_weapon_target(
        self, state, caster, item_id, *, reach_spell_effective_range_ft: int | None = None
    ):
        """Resolve one actual, touchable longsword/shortsword target.

        Item location is derived from the encounter's physical inventories.
        A held item is wielded by that actor; a ground item is unattended.
        Worn/stowed weapons and legacy literal IDs are intentionally outside
        this first Runic Weapon target menu.
        """
        if not isinstance(item_id, str) or not item_id:
            raise ValueError("Runic Weapon requires a non-empty physical item_id.")
        item = state.item_instances.get(item_id)
        if item is None:
            raise ValueError(f"Runic Weapon target {item_id!r} is not a physical item instance.")
        if item.definition_id not in {"longsword", "shortsword", "staff"}:
            raise ValueError("Runic Weapon can target only a longsword, shortsword, or staff in this slice.")

        locations: list[tuple[str, str | None, Position]] = []
        for actor in state.creatures.values():
            if item_id in actor.held_items:
                locations.append(("held", actor.actor_id, actor.position))
            if item_id in actor.worn_items:
                locations.append(("worn", actor.actor_id, actor.position))
            if item_id in actor.stowed_items:
                locations.append(("stowed", actor.actor_id, actor.position))
        for position, item_ids in (state.ground_items or {}).items():
            if item_id in item_ids:
                locations.append(("ground", None, position))
        if len(locations) != 1:
            raise ValueError("Runic Weapon target item has missing or duplicated physical location.")
        location, wielder_id, position = locations[0]
        if location in {"worn", "stowed"}:
            raise ValueError("Runic Weapon requires a wielded or unattended weapon; worn/stowed items are invalid.")
        target_range = 5 if reach_spell_effective_range_ft is None else reach_spell_effective_range_ft
        if type(target_range) is not int or target_range < 0:
            raise ValueError("Runic Weapon has an invalid committed spell range.")
        if grid_distance_feet(caster.position, position) > target_range:
            raise ValueError("Runic Weapon target is outside touch range.")
        if wielder_id is not None:
            wielder = state.creatures.get(wielder_id)
            if wielder is None or wielder.dead or wielder.unconscious:
                raise ValueError("Runic Weapon cannot target a weapon held by an incapacitated creature.")
        return item, wielder_id, position

    @staticmethod
    def _forbidding_ward_targets_valid(caster, ally, enemy, *, range_ft: int) -> bool:
        """Validate Ward's two selected targets against one effective range."""
        return bool(
            type(range_ft) is int
            and range_ft >= 0
            and ally is not None
            and enemy is not None
            and ally.actor_id != caster.actor_id
            and not ally.dead
            and not enemy.dead
            and ally.team == caster.team
            and enemy.team != caster.team
            and grid_distance_feet(caster.position, ally.position) <= range_ft
            and grid_distance_feet(caster.position, enemy.position) <= range_ft
        )

    def _runic_weapon_item_concealed(self, state, caster, item_facts) -> bool:
        """Return whether the caster cannot see a Runic Weapon target."""
        _item, wielder_id, position = item_facts
        return (
            wielder_id != caster.actor_id
            and get_definition(caster.definition_id).vision == "ordinary"
            and self.illumination_at(position) == "dim"
        )

    def _offer_runic_weapon_willingness(self, state, caster, continuation):
        """Persist the post-commit willingness choice for another wielder."""
        item_id = continuation.spell_target_item_id
        wielder_id = continuation.spell_target_wielder_id
        wielder = state.creatures.get(wielder_id or "")
        if item_id is None or wielder is None:
            raise _Rejected("Runic Weapon's saved item wielder is no longer available.")
        self._set_pending(
            state,
            kind="spell_willingness",
            owner_actor_id=wielder.actor_id if wielder.health_mode is HealthMode.PC else None,
            prompt=f"Is {wielder.label} willing to receive Runic Weapon on {item_id}?",
            options=(ChoiceOption("willing", "Willing"), ChoiceOption("unwilling", "Unwilling")),
            actor_id=caster.actor_id,
            target_id=wielder.actor_id,
            spell_id="runic_weapon",
            slot_id=continuation.slot_id,
            spell_actions=continuation.spell_actions,
            spell_target_item_id=item_id,
            continuation=continuation,
        )
        return [Event(
            "spell_willingness",
            caster.actor_id,
            wielder.actor_id,
            f"Ask {wielder.label} whether to accept Runic Weapon on {item_id}.",
        )]

    def _effective_reach_spell_range(
        self, spell_id: str, actions: int, *, reach_ready: bool
    ) -> int | None:
        """Return the single source of truth for this cast mode's range."""
        spell = SPELLS[spell_id]
        if spell_id == "heal":
            if actions == 3:
                return None
            if actions == 1:
                spell = replace(spell, range_ft=0)
            elif actions == 2:
                spell = replace(spell, range_ft=30)
        elif spell_id in {"runic_weapon", "runic_body", "gouging_claw", "protection", "sigil"}:
            spell = replace(spell, range_ft=0)
        from .reach_spell import effective_spell_range

        effective = effective_spell_range(spell, reach_ready=reach_ready)
        # Rules content represents touch as range 0 for spell-shaping, while
        # this grid represents an ordinary touch target in an adjacent square.
        # Reach turns that 0 into 30 before this boundary, so only the
        # unshaped grid projection/validator receives the 5-foot conversion.
        return 5 if effective == 0 else effective

    def _spell_targets_for_cast(
        self,
        state,
        caster,
        spell_id,
        actions,
        *,
        reach_spell_effective_range_ft: int | None = None,
    ):
        spell = SPELLS[spell_id]
        if spell_id == "heal" and actions == 3:
            return tuple(
                creature.actor_id for creature in state.creatures.values()
                if creature.actor_id != caster.actor_id and self._is_living_target(creature)
                and in_heal_emanation(caster.position, creature.position)
            )
        range_ft = (
            reach_spell_effective_range_ft
            if reach_spell_effective_range_ft is not None
            else self._effective_reach_spell_range(spell_id, actions, reach_ready=False)
        )
        result = []
        for target in state.creatures.values():
            if not self._spell_target_valid(spell_id, caster, target, state):
                continue
            if range_ft is not None and grid_distance_feet(caster.position, target.position) > range_ft:
                continue
            result.append(target.actor_id)
        return tuple(result)

    @staticmethod
    def _blood_magic_recipient_options(caster, target) -> tuple[ChoiceOption, ...]:
        """Return the legal Angelic Blood Magic recipient choices for Heal."""
        options = [ChoiceOption(caster.actor_id, f"{caster.label} (caster)")]
        if target.actor_id != caster.actor_id and target.team == caster.team:
            options.append(ChoiceOption(target.actor_id, f"{target.label} (Heal target)"))
        return tuple(options)

    @staticmethod
    def _in_angelic_halo_emanation(origin: Position, target: Position) -> bool:
        """Return whether a one-cell target lies within Halo's 15-foot aura."""
        return grid_distance_feet(origin, target) <= 15

    def _blood_magic_halo_recipient_options(self, state, caster) -> tuple[ChoiceOption, ...]:
        """Return caster plus living allies inside Halo at cast time."""
        options = [ChoiceOption(caster.actor_id, f"{caster.label} (caster)")]
        options.extend(
            ChoiceOption(target.actor_id, f"{target.label} (ally inside Halo)")
            for target in state.creatures.values()
            if target.actor_id != caster.actor_id
            and target.team == caster.team
            and self._is_living_target(target)
            and self._in_angelic_halo_emanation(caster.position, target.position)
        )
        return tuple(options)

    @staticmethod
    def _valid_committed_blood_magic_halo(caster, continuation) -> bool:
        """Confirm a saved Halo continuation names exactly one spent focus point."""
        definition = get_definition(caster.definition_id)
        knows_halo = any(
            spell.spell_id == "angelic_halo" and spell.rank == 1 and not spell.cantrip
            for spell in definition.focus_spells
        )
        return bool(
            continuation.kind == "cast"
            and continuation.actor_id == caster.actor_id
            and continuation.spell_id == "angelic_halo"
            and continuation.spell_source_kind == "focus"
            and continuation.slot_id == "actor_focus_pool"
            and continuation.spell_actions == 1
            and continuation.include_self is None
            and continuation.sorcerous_potency == 0
            and continuation.movement_kind is None
            and not continuation.must_disrupt_on_critical
            and "blood_magic" in definition.abilities
            and "angelic_halo" in definition.abilities
            and knows_halo
            and caster.focus_capacity == definition.focus_capacity == 1
            and caster.focus_points == 0
        )

    def _offer_blood_magic_halo_recipient(self, state, caster, continuation, dice) -> list[Event]:
        """Select Halo's Blood Magic recipient before the aura is applied."""
        options = self._blood_magic_halo_recipient_options(state, caster)
        if len(options) == 1:
            continuation.blood_magic_recipient_id = caster.actor_id
            return self._resolve_cast(state, dice, continuation)
        self._set_pending(
            state,
            kind="spell_blood_magic_recipient",
            owner_actor_id=caster.actor_id,
            prompt="Choose the recipient of Angelic Blood Magic for Halo.",
            options=options,
            actor_id=caster.actor_id,
            spell_id="angelic_halo",
            slot_id=continuation.slot_id,
            spell_actions=continuation.spell_actions,
            continuation=continuation,
        )
        return [Event(
            "spell_blood_magic_choice",
            caster.actor_id,
            None,
            "Choose whether Angelic Blood Magic protects the caster or an ally inside Halo.",
        )]

    @staticmethod
    def _valid_committed_blood_magic_heal(caster, continuation) -> bool:
        """Confirm a saved Angelic Heal still names its spent rank pool."""
        definition = get_definition(caster.definition_id)
        slot = next((
            item for item in caster.spontaneous_slots
            if item.slot_id == continuation.slot_id
        ), None)
        knows_gift = any(
            spell.spell_id == "heal" and spell.rank == 1 and not spell.cantrip
            for spell in definition.spontaneous_spells
        )
        return bool(
            continuation.kind == "cast"
            and continuation.actor_id == caster.actor_id
            and continuation.spell_id == "heal"
            and continuation.spell_source_kind == "spontaneous"
            and continuation.spell_actions in (1, 2, 3)
            and continuation.sorcerous_potency == 1
            and continuation.movement_kind == "manipulate"
            and continuation.must_disrupt_on_critical
            and "blood_magic" in definition.abilities
            and "sorcerous_potency" in definition.abilities
            and knows_gift
            and slot is not None
            and slot.rank == 1
            and slot.remaining < slot.capacity
        )

    @staticmethod
    def _valid_committed_runic_weapon(caster, continuation) -> bool:
        """Confirm a saved Runic Weapon names one committed rank-1 cast."""
        definition = get_definition(caster.definition_id)
        spontaneous_slot = next(
            (item for item in caster.spontaneous_slots if item.slot_id == continuation.slot_id),
            None,
        )
        prepared_slot = next(
            (item for item in caster.prepared_slots if item.slot_id == continuation.slot_id),
            None,
        )
        knows_runic_weapon = any(
            spell.spell_id == "runic_weapon" and spell.rank == 1 and not spell.cantrip
            for spell in definition.spontaneous_spells
        )
        prepared_source_valid = False
        if continuation.spell_source_kind == "prepared":
            from .preparation import prepared_slot_rejection

            prepared_source_valid = bool(
                prepared_slot is not None
                and prepared_slot.spell_id == "runic_weapon"
                and prepared_slot.rank == 1
                and not prepared_slot.cantrip
                and prepared_slot.spent
                and prepared_slot_rejection(
                    caster, definition, prepared_slot, prepared_slot.spell_id,
                ) is None
            )
        spontaneous_source_valid = bool(
            continuation.spell_source_kind == "spontaneous"
            and spontaneous_slot is not None
            and spontaneous_slot.rank == 1
            and spontaneous_slot.remaining < spontaneous_slot.capacity
            and knows_runic_weapon
        )
        return bool(
            continuation.kind == "cast"
            and continuation.actor_id == caster.actor_id
            and continuation.spell_id == "runic_weapon"
            and continuation.spell_source_kind in {"prepared", "spontaneous"}
            and continuation.spell_actions == 2
            and continuation.slot_id is not None
            and continuation.target_id is None
            and continuation.spell_target_id is None
            and continuation.spell_target_item_id
            and (
                continuation.spell_target_wielder_id is None
                or continuation.spell_target_wielder_id
            )
            and continuation.include_self is None
            and continuation.sorcerous_potency == 0
            and continuation.blood_magic_recipient_id is None
            and continuation.movement_kind == "manipulate"
            and continuation.must_disrupt_on_critical
            and (prepared_source_valid or spontaneous_source_valid)
        )

    def _offer_blood_magic_recipient(self, state, caster, continuation) -> list[Event]:
        """Save the Angelic recipient before a spontaneous Heal resolves."""
        target = state.creatures.get(continuation.target_id or "")
        if target is None:
            raise _Rejected("The Heal target is no longer eligible.")
        self._set_pending(
            state,
            kind="spell_blood_magic_recipient",
            owner_actor_id=caster.actor_id,
            prompt="Choose the recipient of Angelic Blood Magic for Heal.",
            options=self._blood_magic_recipient_options(caster, target),
            actor_id=caster.actor_id,
            target_id=target.actor_id,
            spell_id="heal",
            slot_id=continuation.slot_id,
            spell_actions=continuation.spell_actions,
            continuation=continuation,
        )
        return [Event(
            "spell_blood_magic_choice",
            caster.actor_id,
            target.actor_id,
            "Choose whether Angelic Blood Magic protects the caster or the Heal target.",
        )]

    def _blood_magic_area_recipient_options(self, state, caster, continuation) -> tuple[ChoiceOption, ...]:
        """Return caster plus living creatures affected by three-action Heal."""
        options = [ChoiceOption(caster.actor_id, f"{caster.label} (caster)")]
        recipients = (
            target for target in state.creatures.values()
            if target.actor_id != caster.actor_id
            and target.team == caster.team
            and self._is_living_target(target)
            and in_heal_emanation(caster.position, target.position)
        )
        options.extend(
            ChoiceOption(target.actor_id, f"{target.label} (Heal target)")
            for target in recipients
        )
        return tuple(options)

    def _offer_blood_magic_area_recipient(self, state, caster, continuation) -> list[Event]:
        """Save an area Heal's Blood Magic recipient before rolling healing."""
        options = self._blood_magic_area_recipient_options(state, caster, continuation)
        self._set_pending(
            state,
            kind="spell_blood_magic_recipient",
            owner_actor_id=caster.actor_id,
            prompt="Choose the recipient of Angelic Blood Magic for Heal.",
            options=options,
            actor_id=caster.actor_id,
            spell_id="heal",
            slot_id=continuation.slot_id,
            spell_actions=continuation.spell_actions,
            continuation=continuation,
        )
        return [Event(
            "spell_blood_magic_choice",
            caster.actor_id,
            None,
            "Choose whether Angelic Blood Magic protects the caster or a Heal target.",
        )]

    @staticmethod
    def _stable_zero_pc(creature):
        return creature is not None and (
            creature.health_mode is HealthMode.PC and creature.hp == 0
            and creature.unconscious and creature.dying == 0 and not creature.dead
        )

    def _resolve_cast(self, state, dice, continuation):
        caster = state.creatures[continuation.actor_id]
        if caster.unconscious or caster.dead:
            return [Event("action_stopped", caster.actor_id, continuation.target_id, f"{caster.label} cannot complete the spell while incapacitated.")]
        spell_id = continuation.spell_id
        if spell_id is None:
            raise _Rejected("Saved spell continuation is missing its spell id.")
        if spell_id == "shield":
            if (
                continuation.target_id is not None
                or continuation.spell_target_id is not None
                or continuation.spell_actions != 1
                or continuation.slot_id is not None
                or continuation.spell_source_kind not in {"prepared", "spontaneous"}
            ):
                raise _Rejected("Shield requires its one-action cantrip form.")
            if caster.shield_recast_available_at_seconds > state.world_time_seconds:
                raise _Rejected("Shield cannot be cast again until its ten-minute post-Block cooldown expires.")
            caster.magic_shield_expires_at_start = state.actor_start_counts.get(caster.actor_id, 0) + 1
            continuation.stage = "done"
            return self._complete_action(state, caster, [Event(
                "magic_shield_raised",
                caster.actor_id,
                caster.actor_id,
                f"{caster.label} raises a magical shield; +1 circumstance AC until their next turn starts.",
            )], dice=dice)
        if spell_id == "weapon_surge":
            item_id = continuation.spell_target_item_id
            if item_id is None or item_id not in caster.held_items:
                return [Event("action_stopped", caster.actor_id, None, "Weapon Surge's target weapon is no longer held.")]
            start = state.actor_start_counts.get(caster.actor_id, 0)
            state.active_effects[:] = [
                effect for effect in state.active_effects
                if not (effect.kind == "weapon_surge" and effect.source_actor_id == caster.actor_id)
            ]
            state.active_effects.append(ActiveSpellEffect(
                effect_id=f"weapon_surge:{caster.actor_id}:{item_id}:{state.next_choice_id}",
                kind="weapon_surge", source_actor_id=caster.actor_id,
                target_actor_id=caster.actor_id, value=1,
                expires_at_source_start=start + 1,
                expires_at_world_time=state.world_time_seconds + 6,
            ))
            continuation.stage = "done"
            return self._complete_action(state, caster, [Event(
                "weapon_surge", caster.actor_id, None,
                f"{caster.label} imbues {item_id}; its next Strike gains +1 status and 1d6 spirit damage.",
            )], dice=dice)
        if spell_id == "light":
            return self._resolve_light(state, dice, caster, continuation)
        if spell_id == "sigil":
            expires_source = state.actor_start_counts.get(caster.actor_id, 0) + 1_000_000
            expires_world = state.world_time_seconds + 604800
            if continuation.target_id is not None:
                target = state.creatures.get(continuation.target_id)
                if (
                    target is None
                    or target.dead
                    or grid_distance_feet(caster.position, target.position)
                    > self._effective_reach_spell_range(
                        spell_id,
                        continuation.spell_actions,
                        reach_ready=continuation.reach_spell_effective_range_ft is not None,
                    )
                ):
                    return [Event("action_stopped", caster.actor_id, continuation.target_id, "Sigil's touched creature is no longer eligible.")]
                state.active_effects[:] = [
                    effect for effect in state.active_effects
                    if not (
                        effect.kind == "sigil"
                        and effect.target_actor_id == target.actor_id
                        and effect.source_actor_id == caster.actor_id
                    )
                ]
                state.active_effects.append(ActiveSpellEffect(
                    f"sigil:{caster.actor_id}:{target.actor_id}:{state.next_choice_id}", "sigil", caster.actor_id, target.actor_id,
                    2 if continuation.spell_mode == "invisible" else 1,
                    expires_source, expires_world,
                ))
                target_id = target.actor_id
                target_label = target.label
            else:
                item_id = continuation.spell_target_item_id
                position = self._item_position(state, item_id or "")
                if (
                    item_id not in state.item_instances
                    or position is None
                    or grid_distance_feet(caster.position, position)
                    > self._effective_reach_spell_range(
                        spell_id,
                        continuation.spell_actions,
                        reach_ready=continuation.reach_spell_effective_range_ft is not None,
                    )
                ):
                    return [Event("action_stopped", caster.actor_id, None, "Sigil's touched item is no longer eligible.")]
                state.active_item_effects[:] = [
                    effect for effect in state.active_item_effects
                    if not (
                        effect.kind == "sigil"
                        and effect.item_id == item_id
                        and effect.source_actor_id == caster.actor_id
                    )
                ]
                state.active_item_effects.append(ActiveItemSpellEffect(
                    f"sigil:{caster.actor_id}:{item_id}:{state.next_choice_id}", "sigil", caster.actor_id, item_id,
                    expires_source, None, visible=continuation.spell_mode != "invisible",
                ))
                target_id = None
                target_label = item_id
            continuation.stage = "done"
            return self._complete_action(state, caster, [Event("sigil_marked", caster.actor_id, target_id, f"{caster.label} places a visible magical sigil on {target_label}.")], dice=dice)
        if spell_id == "detect_magic":
            # Rank-1 Detect Magic reports only presence or absence.  The
            # caster may first discard magic already known to their side; no
            # source, location, school, or identity is surfaced.
            if continuation.include_self is None:
                self._set_pending(
                    state, kind="detect_magic_known", owner_actor_id=caster.actor_id,
                    prompt="Detect Magic: include magic already known to the caster?",
                    options=(
                        ChoiceOption("detect_all", "Detect all magic"),
                        ChoiceOption("ignore_known", "Ignore magic already known to the caster"),
                    ),
                    actor_id=caster.actor_id, spell_id="detect_magic",
                    slot_id=continuation.slot_id, spell_actions=2, continuation=continuation,
                )
                return [Event("detect_magic_choice", caster.actor_id, None,
                    "Choose whether Detect Magic includes already-known magic.")]
            ignore_known = continuation.include_self is False
            caster_team = caster.team
            # A fact is just a known owner (when one exists) and a concrete
            # grid location.  Rank 1 deliberately exposes neither field.
            magical_facts: list[tuple[str | None, Position]] = []
            for effect in state.active_effects:
                target = state.creatures.get(effect.target_actor_id)
                source = state.creatures.get(effect.source_actor_id)
                position = target.position if target is not None else source.position if source is not None else None
                if position is not None:
                    magical_facts.append((effect.source_actor_id, position))
            for effect in state.active_item_effects:
                position = self._item_position(state, effect.item_id)
                if position is not None:
                    magical_facts.append((effect.source_actor_id, position))
            for actor_id, creature in state.creatures.items():
                if any(
                    self._item_is_magical(state, item_id)
                    for item_id in (*creature.held_items, *creature.stowed_items, *creature.worn_items)
                ):
                    magical_facts.append((actor_id, creature.position))
                if creature.magic_shield_expires_at_start > state.actor_start_counts.get(actor_id, 0):
                    magical_facts.append((actor_id, creature.position))
            for orb in state.light_orbs:
                position = (
                    state.creatures[orb.attached_actor_id].position
                    if orb.attached_actor_id in state.creatures else orb.point
                )
                if position is not None:
                    magical_facts.append((orb.caster_actor_id, position))
            for effect in state.condition_effects:
                if effect.kind != "commanded":
                    continue
                target = state.creatures.get(effect.target_actor_id)
                if target is not None:
                    magical_facts.append((effect.source_actor_id, target.position))
            magical_facts = [
                (owner_id, position) for owner_id, position in magical_facts
                if grid_distance_feet(caster.position, position) <= 30
            ]
            if ignore_known:
                magical_facts = [
                    (owner_id, position) for owner_id, position in magical_facts
                    if owner_id is None
                    or state.creatures.get(owner_id) is None
                    or state.creatures[owner_id].team != caster_team
                ]
            continuation.stage = "done"
            present = bool(magical_facts)
            return self._complete_action(state, caster, [Event(
                "detect_magic_present" if present else "detect_magic_absent", caster.actor_id, None,
                "Detect Magic registers the presence of magic." if present else "Detect Magic registers no magic.",
            )], dice=dice)
        if spell_id == "forbidding_ward":
            ally = state.creatures.get(continuation.target_id or "")
            enemy_id = continuation.target_ids[0] if len(continuation.target_ids) == 1 else ""
            enemy = state.creatures.get(enemy_id)
            if (
                continuation.spell_target_id != continuation.target_id
                or continuation.spell_actions != 2
                or ally is None or enemy is None
                or not self._forbidding_ward_targets_valid(
                    caster,
                    ally,
                    enemy,
                    range_ft=(
                        continuation.reach_spell_effective_range_ft
                        if continuation.reach_spell_effective_range_ft is not None
                        else 30
                    ),
                )
            ):
                return [Event(
                    "action_stopped", caster.actor_id, continuation.target_id,
                    "Forbidding Ward's saved ally and enemy are no longer legal targets.",
                )]
            start = state.actor_start_counts.get(caster.actor_id, 0)
            state.active_effects.append(ActiveSpellEffect(
                effect_id=f"forbidding_ward:{caster.actor_id}:{ally.actor_id}:{enemy.actor_id}:{state.next_choice_id}",
                kind="forbidding_ward", source_actor_id=caster.actor_id,
                target_actor_id=ally.actor_id, value=1,
                expires_at_source_start=start + 10,
                expires_at_world_time=state.world_time_seconds + 60,
                sustain_limit_source_start=start + 10,
                sustain_limit_world_time=state.world_time_seconds + 60,
                sustain_expires_at_source_end=state.actor_end_counts.get(caster.actor_id, 0) + 2,
                selected_enemy_actor_id=enemy.actor_id,
            ))
            continuation.stage = "done"
            return self._complete_action(state, caster, [Event(
                "forbidding_ward", caster.actor_id, ally.actor_id,
                f"{ally.label} gains +1 status AC and saves against {enemy.label}'s effects.",
            )], dice=dice)
        if spell_id == "stoke_the_heart":
            target = state.creatures.get(continuation.target_id or "")
            if target is None or target.dead or target.defeated:
                return [Event("action_stopped", caster.actor_id, continuation.target_id, "Stoke the Heart's target is no longer eligible.")]
            start = state.actor_start_counts.get(caster.actor_id, 0)
            if caster.witch_hex_cast_start == start:
                continuation.stage = "done"
                return self._complete_action(state, caster, [Event(
                    "hex_cast_lost", caster.actor_id, target.actor_id,
                    "A Witch can Cast only one hex each turn; the attempted Stoke the Heart loses its action.",
                )], dice=dice)
            state.active_effects.append(ActiveSpellEffect(
                effect_id=f"stoke_the_heart:{caster.actor_id}:{target.actor_id}:{state.next_choice_id}",
                kind="stoke_the_heart", source_actor_id=caster.actor_id, target_actor_id=target.actor_id,
                value=2, expires_at_source_start=start + 10,
                expires_at_world_time=state.world_time_seconds + 60,
                sustain_limit_source_start=start + 10,
                sustain_limit_world_time=state.world_time_seconds + 60,
                sustain_expires_at_source_end=state.actor_end_counts.get(caster.actor_id, 0) + 2,
            ))
            restored_choice = continuation.stage
            caster.witch_hex_cast_start = start
            continuation.stage = "done"
            events = [Event(
                "stoke_the_heart", caster.actor_id, target.actor_id,
                f"{target.label} gains +2 status to damage rolls while Stoke the Heart is sustained.",
            )]
            if restored_choice == "restored_spirit_declined":
                return self._complete_action(state, caster, events, dice=dice)
            # A before recipient has already consumed the patron gate.
            if caster.witch_restored_spirit_used_start == start:
                return self._complete_action(state, caster, events, dice=dice)
            return self._offer_restored_spirit_choice(state, caster, events, dice=dice)
        if spell_id == "command":
            target = state.creatures.get(continuation.target_id or "")
            if target is None or target.dead or target.defeated:
                return [Event("action_stopped", caster.actor_id, continuation.target_id, "Command's target is no longer eligible.")]
            if "Common" not in get_definition(target.definition_id).languages:
                raise _Rejected("Command requires a target that understands the caster's spoken language.")
            breakdown = self._spell_save_modifier_breakdown(state, target, continuation, "command", statistic="will")
            check = replace(resolve_check(dice.draw(20), combine_modifiers(breakdown), self._spell_dc(state, caster, "command")), modifier_breakdown=tuple(breakdown))
            if self._offer_counter_performance_choice(state, caster, target, continuation, check):
                return [Event(
                    "command_save", caster.actor_id, target.actor_id,
                    f"{target.label} rolls Will against Command: {check.degree.label().lower()} ({continuation.spell_mode}); choose a response before consequences.",
                    check=check,
                )]
            return self._resolve_command_result(state, dice, caster, target, continuation, check)

        if spell_id == "runic_weapon":
            return self._resolve_runic_weapon(state, dice, caster, continuation)
        if spell_id == "angelic_halo":
            if continuation.spell_source_kind != "focus":
                raise _Rejected("Angelic Halo requires the caster's focus source.")
            if continuation.blood_magic_recipient_id is None:
                return self._offer_blood_magic_halo_recipient(state, caster, continuation, dice)
            if continuation.blood_magic_recipient_id not in {
                option.option_id
                for option in self._blood_magic_halo_recipient_options(state, caster)
            }:
                return [Event(
                    "action_stopped",
                    caster.actor_id,
                    None,
                    "Angelic Blood Magic's saved Halo recipient is no longer eligible.",
                )]
            events = self._apply_blood_magic(state, caster, continuation)
            events.extend(self._apply_angelic_halo(state, caster, continuation, dice=dice))
            return events
        if spell_id == "courageous_anthem":
            if (
                continuation.spell_source_kind != "spontaneous"
                or continuation.target_id is not None
                or continuation.include_self is not None
                or continuation.spell_actions != 1
            ):
                raise _Rejected("Courageous Anthem requires its one-action spontaneous cantrip form.")
            source_start = state.actor_start_counts.get(caster.actor_id, 0)
            active_actor_id = state.initiative_order[state.active_index] if state.initiative_order else None
            active_start = state.actor_start_counts.get(active_actor_id or "", 0)
            if (
                caster.composition_cast_at_start == source_start
                or active_actor_id is None
                or (caster.composition_cast_turn_actor_id, caster.composition_cast_turn_start) == (active_actor_id, active_start)
            ):
                raise _Rejected("Only one composition spell can be cast each turn.")
            # This literal procedure owns the only admitted composition today.
            # Removing a source's prior effect retains the Composition trait's
            # replacement rule without introducing a general aura subsystem.
            state.active_effects[:] = [
                effect for effect in state.active_effects
                if not (
                    effect.kind == "courageous_anthem"
                    and effect.source_actor_id == caster.actor_id
                )
            ]
            caster.composition_cast_at_start = source_start
            caster.composition_cast_turn_actor_id = active_actor_id
            caster.composition_cast_turn_start = active_start
            expires_at_start = source_start + 1
            for recipient in state.creatures.values():
                if (
                    recipient.team == caster.team
                    and self._is_living_target(recipient)
                    and grid_distance_feet(caster.position, recipient.position) <= 60
                ):
                    state.active_effects.append(ActiveSpellEffect(
                        effect_id=f"courageous_anthem:{caster.actor_id}:{recipient.actor_id}:{state.next_choice_id}",
                        kind="courageous_anthem",
                        source_actor_id=caster.actor_id,
                        target_actor_id=recipient.actor_id,
                        value=1,
                        expires_at_source_start=expires_at_start,
                        expires_at_world_time=state.world_time_seconds + 6,
                    ))
            continuation.stage = "done"
            events = [Event(
                "courageous_anthem_applied",
                caster.actor_id,
                None,
                f"{caster.label} inspires themself and allies within 60 feet: +1 status to attacks, damage, and saves against fear for 1 round.",
            )]
            return events + self._complete_action(state, caster, [], dice=dice)
        if spell_id == "sure_strike":
            if continuation.spell_source_kind != "prepared":
                raise _Rejected("Sure Strike requires the prepared ordinary slot.")
            if continuation.target_id is not None or continuation.include_self is not None:
                raise _Rejected("Sure Strike targets only its caster.")
            if state.sure_strike_immunity_deadlines.get(caster.actor_id, 0) > state.world_time_seconds:
                raise _Rejected("Sure Strike is unavailable while its ten-minute immunity is active.")
            state.active_effects[:] = [
                effect for effect in state.active_effects
                if not (
                    effect.kind == "sure_strike"
                    and effect.source_actor_id == caster.actor_id
                )
            ]
            state.active_effects.append(ActiveSpellEffect(
                effect_id=f"sure_strike:{caster.actor_id}:{state.next_choice_id}",
                kind="sure_strike",
                source_actor_id=caster.actor_id,
                target_actor_id=caster.actor_id,
                value=1,
                expires_at_source_start=state.actor_start_counts.get(caster.actor_id, 0) + 1,
                expires_at_world_time=state.world_time_seconds + 6,
            ))
            continuation.stage = "done"
            events = [Event(
                "sure_strike_ready",
                caster.actor_id,
                caster.actor_id,
                f"{caster.label} casts Sure Strike; the next attack this turn rolls twice and takes the better result.",
            )]
            self._record_arcane_bond_completed(caster, continuation)
            return events + self._complete_action(state, caster, [], dice=dice)
        if spell_id in {"heal", "gale_blast"} and (spell_id == "gale_blast" or continuation.spell_actions == 3):
            if continuation.include_self is None:
                self._set_pending(
                    state, kind="spell_self_inclusion", owner_actor_id=caster.actor_id,
                    prompt=("Include the caster in the three-action Heal emanation?" if spell_id == "heal" else "Include the caster in the Gale Blast emanation?"),
                    options=(ChoiceOption("include", "Include self"), ChoiceOption("exclude", "Exclude self")),
                    actor_id=caster.actor_id, spell_id=spell_id,
                    slot_id=continuation.slot_id, spell_actions=continuation.spell_actions,
                    continuation=continuation,
                )
                return [Event("spell_self_choice", caster.actor_id, None, f"Choose whether {SPELLS[spell_id].name} includes the caster.")]
            if spell_id == "heal":
                return self._apply_heal_emanation(state, dice, continuation)
            return self._resolve_gale_blast(state, dice, caster, continuation)
        if spell_id == "force_barrage":
            return self._resolve_force_barrage(state, dice, caster, continuation)
        if spell_id == "breathe_fire":
            return self._resolve_breathe_fire(state, dice, caster, continuation)
        if spell_id == "electric_arc":
            return self._resolve_electric_arc(state, dice, caster, continuation)
        if spell_id == "gale_blast":
            return self._resolve_gale_blast(state, dice, caster, continuation)
        if continuation.target_id is None:
            candidates = self._spell_targets_for_cast(
                state,
                caster,
                spell_id,
                continuation.spell_actions,
                reach_spell_effective_range_ft=continuation.reach_spell_effective_range_ft,
            )
            if not candidates:
                return [Event("action_stopped", caster.actor_id, None, f"{SPELLS[spell_id].name} has no remaining legal target after the reaction.")]
            self._set_pending(
                state, kind="spell_target", owner_actor_id=caster.actor_id,
                prompt=f"Choose a target for {SPELLS[spell_id].name}.",
                options=tuple(ChoiceOption(actor_id, state.creatures[actor_id].label) for actor_id in candidates),
                actor_id=caster.actor_id, spell_id=spell_id,
                slot_id=continuation.slot_id, spell_actions=continuation.spell_actions,
                continuation=continuation, target_ids=candidates,
            )
            return [Event("spell_target_choice", caster.actor_id, None, f"Choose a target for {SPELLS[spell_id].name}.")]
        target = state.creatures.get(continuation.target_id)
        if target is None or target.actor_id not in self._spell_targets_for_cast(
            state,
            caster,
            spell_id,
            continuation.spell_actions,
            reach_spell_effective_range_ft=continuation.reach_spell_effective_range_ft,
        ):
            return [Event("action_stopped", caster.actor_id, continuation.target_id, f"{SPELLS[spell_id].name}'s target is no longer eligible.")]
        if spell_id == "caustic_blast":
            return self._resolve_caustic_blast(state, dice, caster, target, continuation)
        # A spell with the attack trait commits its attack count with the cast, before the
        # observer-relative targeting gate.  A failed flat check still spends
        # the action and contributes MAP, while the actual spell attack keeps
        # the pre-cast penalty captured on the continuation.
        if "attack" in spell_traits(spell_id) and not continuation.attack_count_committed:
            caster.strikes_this_turn += 1
            continuation.attack_count_committed = True
        if "attack" in spell_traits(spell_id):
            self._consume_sure_strike_for_attack(state, caster, continuation)
        concealment_events = self._resolve_spell_concealment(
            state, dice, caster, target, continuation
        )
        if concealment_events is not None:
            return concealment_events
        if (
            spell_id == "heal"
            and continuation.spell_source_kind == "spontaneous"
            and continuation.blood_magic_recipient_id is None
        ):
            return self._offer_blood_magic_recipient(state, caster, continuation)
        if spell_id == "guidance":
            effect = ActiveSpellEffect(
                effect_id=f"guidance:{caster.actor_id}:{target.actor_id}:{state.next_choice_id}",
                kind="guidance", source_actor_id=caster.actor_id,
                target_actor_id=target.actor_id, value=1,
                expires_at_source_start=state.actor_start_counts.get(caster.actor_id, 0) + 1,
                expires_at_world_time=state.world_time_seconds + 6,
            )
            state.active_effects.append(effect)
            continuation.stage = "done"
            events = [Event("effect_applied", caster.actor_id, target.actor_id, f"Guidance grants {target.label} +1 status to one eligible check before the caster's next turn.")]
            return events + self._complete_action(state, caster, [], dice=dice)
        if spell_id == "fear":
            return self._roll_fear_save(state, dice, caster, target, continuation)
        if spell_id == "daze":
            return self._roll_daze_save(state, dice, caster, target, continuation)
        if spell_id == "harm":
            if continuation.spell_actions != 2:
                raise _Rejected("Harm is admitted only in its two-action living-target form.")
            return self._roll_spell_save(
                state, dice, caster, target, continuation, "harm", "fortitude",
            )
        if spell_id == "stabilize":
            transition = pc_stabilize(self._health_state(target))
            self._apply_health_transition(state, target, transition)
            self._finish_if_team_defeated(state)
            continuation.stage = "done"
            events = [Event("stabilize", caster.actor_id, target.actor_id, f"{target.label} is stabilized at 0 HP and gains wounded {target.wounded}.")]
            return events + self._complete_action(state, caster, [], dice=dice)
        if spell_id == "force_bolt":
            if continuation.spell_source_kind != "focus" or continuation.spell_actions != 1:
                raise _Rejected("Force Bolt requires its one-action focus-spell form.")
            damage = resolve_damage(
                DamagePacket("Force Bolt", "force", 4, 1, 1), dice.draw
            )
            return self._apply_spell_damage(
                state, dice, caster, target, damage,
                check=None, source="force_bolt", damage_type="force",
                continuation=continuation,
            )
        if spell_id == "life_link":
            if (
                continuation.spell_source_kind != "focus"
                or continuation.spell_actions != 1
                or continuation.slot_id != "actor_focus_pool"
                or target.actor_id == caster.actor_id
            ):
                raise _Rejected("Life Link requires its one-action focus form on another creature.")
            effect = ActiveSpellEffect(
                effect_id=f"life_link:{caster.actor_id}:{target.actor_id}:{state.next_choice_id}",
                kind="life_link", source_actor_id=caster.actor_id,
                target_actor_id=target.actor_id, value=3,
                expires_at_source_start=state.actor_start_counts.get(caster.actor_id, 0) + 10,
                expires_at_world_time=state.world_time_seconds + 60,
            )
            state.active_effects.append(effect)
            continuation.stage = "done"
            initial_healing = dice.draw(4)
            events = [Event(
                "life_link_applied", caster.actor_id, target.actor_id,
                f"{caster.label} links life to {target.label} for 1 minute; the first damage each round transfers up to 3.",
                details=(effect.effect_id,),
            )]
            events.extend(self._apply_healing(
                state, caster, target, initial_healing, (initial_healing,), continuation,
            ))
            return events + self._complete_action(state, caster, [], dice=dice)
        if (
            (spell_id in {"heal", "soothe"} and continuation.spell_actions in (1, 2))
            or (
                spell_id == "protection"
                and continuation.spell_actions == 2
                and target.actor_id != caster.actor_id
            )
        ):
            self._set_pending(
                state, kind="spell_willingness",
                owner_actor_id=target.actor_id if target.health_mode is HealthMode.PC else None,
                prompt=f"Is {target.label} willing to receive {SPELLS[spell_id].name}?",
                options=(ChoiceOption("willing", "Willing"), ChoiceOption("unwilling", "Unwilling")),
                actor_id=caster.actor_id, target_id=target.actor_id,
                spell_id=spell_id, slot_id=continuation.slot_id,
                spell_actions=continuation.spell_actions,
                continuation=continuation,
            )
            return [Event("spell_willingness", caster.actor_id, target.actor_id, f"Ask {target.label} whether to accept {SPELLS[spell_id].name}.")]
        if spell_id == "protection":
            if continuation.spell_actions != 2:
                raise _Rejected("Protection is admitted only in its two-action form.")
            state.active_effects[:] = [
                effect for effect in state.active_effects
                if not (
                    effect.kind == "protection"
                    and effect.source_actor_id == caster.actor_id
                    and effect.target_actor_id == target.actor_id
                )
            ]
            state.active_effects.append(ActiveSpellEffect(
                effect_id=f"protection:{caster.actor_id}:{target.actor_id}:{state.next_choice_id}",
                kind="protection", source_actor_id=caster.actor_id,
                target_actor_id=target.actor_id, value=1,
                expires_at_source_start=state.actor_start_counts.get(caster.actor_id, 0) + 10,
                expires_at_world_time=state.world_time_seconds + 60,
            ))
            continuation.stage = "done"
            events = [Event(
                "protection_applied", caster.actor_id, target.actor_id,
                f"{target.label} gains +1 status to AC and all saves for 1 minute.",
            )]
            return events + self._complete_action(state, caster, [], dice=dice)
        if spell_id in {"heal", "soothe"}:
            healing = (
                soothe_roll(dice.draw)
                if spell_id == "soothe"
                else heal_roll(
                    continuation.spell_actions, dice.draw,
                    die_sides=self._heal_die_sides(caster),
                )
            )
            events = self._apply_blood_magic(state, caster, continuation) if spell_id == "heal" else []
            events.extend(self._apply_healing(state, caster, target, healing.total, healing.rolls, continuation))
            if spell_id == "soothe":
                state.active_effects[:] = [
                    effect for effect in state.active_effects
                    if not (
                        effect.kind == "soothe"
                        and effect.source_actor_id == caster.actor_id
                        and effect.target_actor_id == target.actor_id
                    )
                ]
                state.active_effects.append(ActiveSpellEffect(
                    effect_id=f"soothe:{caster.actor_id}:{target.actor_id}:{state.next_choice_id}",
                    kind="soothe",
                    source_actor_id=caster.actor_id,
                    target_actor_id=target.actor_id,
                    value=2,
                    expires_at_source_start=state.actor_start_counts.get(caster.actor_id, 0) + 10,
                    expires_at_world_time=state.world_time_seconds + 60,
                ))
                events.append(Event(
                    "soothe_protection_applied",
                    caster.actor_id,
                    target.actor_id,
                    f"{target.label} gains +2 status to saves against mental effects for 1 minute.",
                ))
            continuation.stage = "done"
            return events + self._complete_action(state, caster, [], dice=dice)
        if spell_id == "divine_lance":
            return self._roll_divine_lance(state, dice, caster, target, continuation)
        if spell_id == "void_warp":
            return self._roll_void_warp_save(state, dice, caster, target, continuation)
        if spell_id == "frostbite":
            return self._roll_frostbite_save(state, dice, caster, target, continuation)
        if spell_id == "tempest_surge":
            return self._roll_tempest_surge_save(state, dice, caster, target, continuation)
        if spell_id == "vitality_lash":
            return self._roll_vitality_lash_save(state, dice, caster, target, continuation)
        if spell_id == "enfeeble":
            return self._roll_enfeeble_save(state, dice, caster, target, continuation)
        if spell_id == "runic_body":
            if target.actor_id != caster.actor_id and continuation.stage != "willing":
                self._set_pending(
                    state, kind="spell_willingness",
                    owner_actor_id=target.actor_id if target.health_mode is HealthMode.PC else None,
                    prompt=f"Is {target.label} willing to receive Runic Body?",
                    options=(ChoiceOption("willing", "Willing"), ChoiceOption("unwilling", "Unwilling")),
                    actor_id=caster.actor_id, target_id=target.actor_id, spell_id=spell_id,
                    slot_id=continuation.slot_id, spell_actions=continuation.spell_actions,
                    continuation=continuation,
                )
                return [Event("spell_willingness", caster.actor_id, target.actor_id, f"Ask {target.label} whether to accept Runic Body.")]
            return self._resolve_runic_body(state, dice, caster, target, continuation)
        if spell_id == "telekinetic_projectile":
            return self._roll_telekinetic_projectile(state, dice, caster, target, continuation)
        if spell_id in {"ignition", "gouging_claw"}:
            return self._roll_persistent_attack_spell(state, dice, caster, target, continuation)
        if spell_id == "tangle_vine":
            return self._roll_tangle_vine(state, dice, caster, target, continuation)
        raise _Unsupported(f"No encounter procedure is admitted for {spell_id!r}.")

    def _resolve_force_barrage(self, state, dice, caster, continuation):
        """Resolve one grouped Force Barrage recipient at a time.

        Target allocation was atomically validated before costs were committed.
        Shards aimed at one recipient are one damage effect, so their dice are
        combined before ordinary resistance, weakness, reactions, or health
        continuations. Each completed recipient resumes this same literal
        continuation rather than completing the spell after the first one.
        """
        if continuation.spell_source_kind != "prepared":
            raise _Rejected("Force Barrage requires a prepared rank-1 slot.")
        allocated = continuation.target_ids
        if len(allocated) != continuation.spell_actions or not allocated:
            raise _Rejected("Force Barrage's saved shard allocation is invalid.")
        groups = tuple(dict.fromkeys(allocated))
        try:
            index = int((continuation.stage or "force_barrage:0").split(":", 1)[1])
        except (IndexError, ValueError):
            raise _Rejected("Force Barrage's saved recipient progress is invalid.")
        if not 0 <= index < len(groups):
            raise _Rejected("Force Barrage has no saved recipient to resolve.")
        target_id = groups[index]
        target = state.creatures.get(target_id)
        if target is None or target.actor_id not in self._spell_targets_for_cast(
            state,
            caster,
            "force_barrage",
            continuation.spell_actions,
            reach_spell_effective_range_ft=continuation.reach_spell_effective_range_ft,
        ):
            continuation.stage = f"force_barrage:{index + 1}"
            events = [Event(
                "action_stopped", caster.actor_id, target_id,
                "Force Barrage's saved target is no longer eligible; its allocated shards dissipate.",
            )]
            return events + self._continue_force_barrage(state, dice, caster, continuation)
        shard_count = allocated.count(target_id)
        damage = roll_damage_terms(
            tuple(DamageTerm("Force Barrage", "force", (4,), 1) for _ in range(shard_count)),
            dice.draw,
        )
        return self._apply_spell_damage(
            state, dice, caster, target, damage,
            check=None, source="force_barrage", damage_type="force",
            continuation=continuation,
        )

    def _continue_force_barrage(self, state, dice, caster, continuation):
        allocated = continuation.target_ids
        groups = tuple(dict.fromkeys(allocated))
        try:
            index = int((continuation.stage or "force_barrage:0").split(":", 1)[1])
        except (IndexError, ValueError):
            raise _Rejected("Force Barrage's saved recipient progress is invalid.")
        if index < len(groups):
            return self._resolve_force_barrage(state, dice, caster, continuation)
        continuation.stage = "done"
        self._record_arcane_bond_completed(caster, continuation)
        return self._complete_action(state, caster, [], dice=dice)

    def _resolve_breathe_fire(self, state, dice, caster, continuation):
        """Apply one shared Breathe Fire roll through each listed Reflex save."""
        if continuation.spell_source_kind not in {"prepared", "spontaneous"} or continuation.spell_actions != 2:
            raise _Rejected("Breathe Fire requires a two-action rank-1 prepared or spontaneous cast.")
        if continuation.spell_damage is None:
            continuation.spell_damage = resolve_damage(
                DamagePacket("Breathe Fire", "fire", 6, 2, 0), dice.draw
            )
        raw_damage = continuation.spell_damage
        if not continuation.target_ids:
            continuation.stage = "done"
            self._record_arcane_bond_completed(caster, continuation)
            return self._complete_action(state, caster, [], dice=dice)
        try:
            index = int((continuation.stage or "breathe_fire:0").split(":", 1)[1])
        except (IndexError, ValueError):
            raise _Rejected("Breathe Fire's saved recipient progress is invalid.")
        if index >= len(continuation.target_ids):
            continuation.stage = "done"
            self._finish_if_team_defeated(state)
            return self._complete_action(state, caster, [], dice=dice)
        target = state.creatures.get(continuation.target_ids[index])
        if target is None or target.dead:
            continuation.stage = f"breathe_fire:{index + 1}"
            return self._continue_breathe_fire(state, dice, caster, continuation)
        return self._roll_spell_save(
            state, dice, caster, target, continuation, "breathe_fire", "reflex",
        )

    def _resolve_breathe_fire_result(self, state, dice, caster, target, check, continuation):
        """Apply one saved recipient's basic Reflex result from Breathe Fire's shared roll."""
        raw_damage = continuation.spell_damage
        if raw_damage is None:
            raise _Rejected("Breathe Fire's shared damage roll is missing.")
        total = basic_save_damage(raw_damage.total, check.degree)
        damage = DamageResult(
            components=tuple(replace(component, amount=total) for component in raw_damage.components),
            rolled_total=raw_damage.rolled_total,
            multiplier=raw_damage.multiplier,
            total=total,
            adjustment=f"basic_save:{check.degree.name.lower()}",
        )
        events = [Event(
            "spell_save", caster.actor_id, target.actor_id,
            _spell_save_text(target, check, statistic="Reflex"), check=check,
        )]
        return events + self._apply_spell_damage(
            state, dice, caster, target, damage,
            check=check, source="breathe_fire", damage_type="fire",
            target_critical_failure=check.degree is DegreeOfSuccess.CRITICAL_FAILURE,
            continuation=continuation,
        )

    def _continue_breathe_fire(self, state, dice, caster, continuation):
        continuation.guidance_checked = False
        continuation.guidance_bonus = 0
        try:
            index = int((continuation.stage or "breathe_fire:0").split(":", 1)[1])
        except (IndexError, ValueError):
            raise _Rejected("Breathe Fire's saved recipient progress is invalid.")
        if index < len(continuation.target_ids):
            return self._resolve_breathe_fire(state, dice, caster, continuation)
        continuation.stage = "done"
        self._record_arcane_bond_completed(caster, continuation)
        return self._complete_action(state, caster, [], dice=dice)

    def _resolve_caustic_blast(self, state, dice, caster, center, continuation):
        """Resolve the literal five-foot burst, including the caster if hit."""
        if continuation.spell_source_kind != "prepared" or continuation.spell_actions != 2:
            raise _Rejected("Caustic Blast requires a prepared two-action cantrip cast.")
        if not continuation.target_ids:
            continuation.target_ids = tuple(
                creature.actor_id for creature in state.creatures.values()
                if not creature.dead and grid_distance_feet(center.position, creature.position) <= 5
            )
        if continuation.spell_damage is None:
            continuation.spell_damage = resolve_damage(
                DamagePacket("Caustic Blast", "acid", 8, 1, 0), dice.draw
            )
        return self._continue_caustic_blast(state, dice, caster, continuation)

    def _continue_caustic_blast(self, state, dice, caster, continuation):
        continuation.guidance_checked = False
        continuation.guidance_bonus = 0
        try:
            index = int((continuation.stage or "caustic:0:0").split(":")[1])
        except (IndexError, ValueError) as error:
            raise _Rejected("Caustic Blast's saved recipient progress is invalid.") from error
        if index >= len(continuation.target_ids):
            continuation.stage = "done"
            return self._complete_action(state, caster, [], dice=dice)
        target = state.creatures.get(continuation.target_ids[index])
        if target is None or target.dead:
            continuation.stage = f"caustic:{index + 1}:0"
            return self._continue_caustic_blast(state, dice, caster, continuation)
        return self._roll_spell_save(
            state, dice, caster, target, continuation, "caustic_blast", "reflex",
        )

    def _resolve_gale_blast(self, state, dice, caster, continuation):
        if continuation.spell_source_kind != "prepared" or continuation.spell_actions != 2:
            raise _Rejected("Gale Blast requires a prepared two-action cantrip cast.")
        if not continuation.target_ids:
            continuation.target_ids = tuple(
                creature.actor_id for creature in state.creatures.values()
                if not creature.dead and grid_distance_feet(caster.position, creature.position) <= 5
                and (creature.actor_id != caster.actor_id or continuation.include_self)
            )
        if continuation.spell_damage is None:
            continuation.spell_damage = resolve_damage(DamagePacket("Gale Blast", "bludgeoning", 6, 1, 0), dice.draw)
        return self._continue_gale_blast(state, dice, caster, continuation)

    def _continue_gale_blast(self, state, dice, caster, continuation):
        continuation.guidance_checked = False
        continuation.guidance_bonus = 0
        try:
            index = int((continuation.stage or "gale:0:0").split(":")[1])
        except (IndexError, ValueError) as error:
            raise _Rejected("Gale Blast's saved recipient progress is invalid.") from error
        if index >= len(continuation.target_ids):
            continuation.stage = "done"
            # Gale Blast snapshots and resolves every recipient before an
            # otherwise defeated team can end the encounter.
            self._finish_if_team_defeated(state)
            return self._complete_action(state, caster, [], dice=dice)
        target = state.creatures.get(continuation.target_ids[index])
        if target is None or target.dead:
            continuation.stage = f"gale:{index + 1}:0"
            return self._continue_gale_blast(state, dice, caster, continuation)
        return self._roll_spell_save(
            state, dice, caster, target, continuation, "gale_blast", "fortitude",
        )

    def _resolve_gale_blast_result(self, state, dice, caster, target, check, continuation):
        raw_damage = continuation.spell_damage
        if raw_damage is None:
            raise _Rejected("Gale Blast's shared damage roll is missing.")
        damage = basic_save_damage_result(raw_damage, check.degree)
        index = int((continuation.stage or "gale:0:0").split(":")[1])
        push_ft = 10 if check.degree is DegreeOfSuccess.CRITICAL_FAILURE else 5 if check.degree is DegreeOfSuccess.FAILURE else 0
        continuation.stage = f"gale:{index}:{push_ft}"
        events = [Event("spell_save", caster.actor_id, target.actor_id, _spell_save_text(target, check, statistic="Fortitude"), check=check)]
        return events + self._apply_spell_damage(state, dice, caster, target, damage, check=check, source="gale_blast", damage_type="bludgeoning", continuation=continuation)

    def _resolve_caustic_blast_result(self, state, dice, caster, target, check, continuation):
        raw_damage = continuation.spell_damage
        if raw_damage is None:
            raise _Rejected("Caustic Blast's shared damage roll is missing.")
        total = basic_save_damage(raw_damage.total, check.degree)
        damage = DamageResult(
            components=tuple(replace(component, amount=total) for component in raw_damage.components),
            rolled_total=raw_damage.rolled_total, multiplier=raw_damage.multiplier, total=total,
            adjustment=f"basic_save:{check.degree.name.lower()}",
        )
        try:
            index = int((continuation.stage or "caustic:0:0").split(":")[1])
        except (IndexError, ValueError) as error:
            raise _Rejected("Caustic Blast's saved recipient progress is invalid.") from error
        continuation.stage = f"caustic:{index}:{int(check.degree is DegreeOfSuccess.CRITICAL_FAILURE)}"
        events = [Event("spell_save", caster.actor_id, target.actor_id, _spell_save_text(target, check, statistic="Reflex"), check=check)]
        return events + self._apply_spell_damage(
            state, dice, caster, target, damage, check=check, source="caustic_blast", damage_type="acid",
            target_critical_failure=check.degree is DegreeOfSuccess.CRITICAL_FAILURE,
            continuation=continuation,
        )

    def _resolve_electric_arc(self, state, dice, caster, continuation):
        """Apply one shared Electric Arc roll through its selected Reflex saves."""
        if (
            continuation.spell_source_kind != "prepared"
            or continuation.spell_actions != 2
            or not 1 <= len(continuation.target_ids) <= 2
            or len(set(continuation.target_ids)) != len(continuation.target_ids)
            or continuation.target_id is not None
        ):
            raise _Rejected("Electric Arc requires one or two distinct prepared two-action targets.")
        if continuation.spell_damage is None:
            continuation.spell_damage = resolve_damage(
                DamagePacket("Electric Arc", "electricity", 4, 2, 0), dice.draw
            )
        try:
            index = int((continuation.stage or "electric_arc:0").split(":", 1)[1])
        except (IndexError, ValueError):
            raise _Rejected("Electric Arc's saved recipient progress is invalid.")
        if index >= len(continuation.target_ids):
            continuation.stage = "done"
            return self._complete_action(state, caster, [], dice=dice)
        target = state.creatures.get(continuation.target_ids[index])
        if (
            target is None
            or target.actor_id not in self._spell_targets_for_cast(
                state,
                caster,
                "electric_arc",
                continuation.spell_actions,
                reach_spell_effective_range_ft=continuation.reach_spell_effective_range_ft,
            )
        ):
            continuation.stage = f"electric_arc:{index + 1}"
            return [Event(
                "action_stopped", caster.actor_id, continuation.target_ids[index],
                "Electric Arc's saved target is no longer eligible; that arc dissipates.",
            )] + self._continue_electric_arc(state, dice, caster, continuation)
        return self._roll_spell_save(
            state, dice, caster, target, continuation, "electric_arc", "reflex",
        )

    def _resolve_electric_arc_result(self, state, dice, caster, target, check, continuation):
        raw_damage = continuation.spell_damage
        if raw_damage is None:
            raise _Rejected("Electric Arc's shared damage roll is missing.")
        damage = basic_save_damage_result(raw_damage, check.degree)
        return [Event(
            "spell_save", caster.actor_id, target.actor_id,
            _spell_save_text(target, check, statistic="Reflex"), check=check,
        )] + self._apply_spell_damage(
            state, dice, caster, target, damage, check=check, source="electric_arc",
            damage_type="electricity", continuation=continuation,
        )

    def _roll_frostbite_save(self, state, dice, caster, target, continuation):
        return self._roll_direct_fortitude_save(
            state, dice, caster, target, continuation, "frostbite"
        )

    def _roll_spell_save(
        self, state, dice, caster, target, continuation, spell_id, statistic,
    ):
        """Offer Guidance, roll one save, then offer that target's Hero reroll.

        Spell procedures retain target selection and their result riders.  This
        common seam owns only the ordinary save check and its saved decision
        facts, so a committed cast always resumes through the same modifier
        breakdown that produced the original check.
        """
        if not continuation.guidance_checked:
            effect = self._guidance_for(state, target.actor_id)
            if effect is not None:
                continuation.guidance_checked = True
                self._offer_guidance(
                    state, target, continuation, effect, check_kind="spell_save",
                )
                return [Event(
                    "guidance_choice", effect.source_actor_id, target.actor_id,
                    f"{target.label} may use Guidance before the {statistic.title()} save.",
                )]
        if not continuation.divine_grace_checked:
            definition = get_definition(target.definition_id)
            if (
                target.reaction_available
                and not target.unconscious
                and not target.dead
                and "divine_grace" in definition.abilities
                and "Divine Grace" in definition.feats
            ):
                self._set_pending(
                    state,
                    kind="divine_grace",
                    owner_actor_id=target.actor_id,
                    prompt=(
                        f"{target.label} may use Divine Grace before this "
                        f"{statistic.title()} save."
                    ),
                    options=(
                        ChoiceOption("use", "Use Divine Grace (+2 circumstance)"),
                        ChoiceOption("decline", "Decline"),
                    ),
                    actor_id=caster.actor_id,
                    target_id=target.actor_id,
                    spell_id=spell_id,
                    slot_id=continuation.slot_id,
                    spell_actions=continuation.spell_actions,
                    continuation=continuation,
                )
                return [Event(
                    "divine_grace_choice", target.actor_id, caster.actor_id,
                    f"{target.label} may spend their reaction for Divine Grace before the save.",
                )]
            continuation.divine_grace_checked = True
        breakdown = self._spell_save_modifier_breakdown(
            state, target, continuation, spell_id, statistic,
        )
        die = dice.draw(20)
        check = replace(
            resolve_check(
                die, combine_modifiers(breakdown), self._spell_dc(state, caster, spell_id),
            ),
            modifier_breakdown=tuple(breakdown),
        )
        if target.health_mode is HealthMode.PC and target.hero_points > 0:
            self._set_pending(
                state,
                kind="spell_save_hero_reroll",
                owner_actor_id=target.actor_id,
                prompt=(
                    f"{target.label} may keep this {SPELLS[spell_id].name} "
                    f"{statistic.title()} save or spend 1 Hero Point to reroll."
                ),
                options=(
                    ChoiceOption("keep", "Keep result"),
                    ChoiceOption("spend_hero_point", "Spend 1 Hero Point and reroll"),
                ),
                details=(
                    f"Original: d20 {die} + {check.modifier} = {check.total} vs DC {check.dc}.",
                    f"Degree: {check.degree.label()}.",
                ),
                actor_id=caster.actor_id,
                target_id=target.actor_id,
                check=check,
                check_kind="spell_save",
                check_owner_actor_id=target.actor_id,
                spell_id=spell_id,
                slot_id=continuation.slot_id,
                spell_actions=continuation.spell_actions,
                continuation=continuation,
            )
            return [Event(
                "spell_save", caster.actor_id, target.actor_id,
                _spell_save_text(target, check, statistic=statistic.title()), check=check,
            )]
        return self._resolve_spell_save_result(
            state, dice, caster, target, check, continuation,
        )

    def _roll_tempest_surge_save(self, state, dice, caster, target, continuation):
        """Resolve Storm order's single-target basic Reflex save."""
        if continuation.spell_source_kind != "focus" or continuation.spell_actions != 2:
            raise _Rejected("Tempest Surge requires its two-action focus-spell form.")
        return self._roll_spell_save(
            state, dice, caster, target, continuation, "tempest_surge", "reflex",
        )

    def _resolve_tempest_surge_result(self, state, dice, caster, target, check, continuation):
        raw_damage = resolve_damage(DamagePacket("Tempest Surge", "electricity", 12, 1, 0), dice.draw)
        damage = basic_save_damage_result(raw_damage, check.degree)
        events = [Event("spell_save", caster.actor_id, target.actor_id, _spell_save_text(target, check, statistic="Reflex"), check=check)]
        if check.degree in {DegreeOfSuccess.FAILURE, DegreeOfSuccess.CRITICAL_FAILURE}:
            occurrence = state.actor_start_counts.get(caster.actor_id, 0) + 1
            state.condition_effects[:] = [effect for effect in state.condition_effects if not (effect.kind == "clumsy" and effect.source_actor_id == caster.actor_id and effect.target_actor_id == target.actor_id)]
            state.condition_effects.append(ActiveConditionEffect(
                f"tempest_surge:clumsy:{caster.actor_id}:{target.actor_id}:{state.next_choice_id}", "clumsy", caster.actor_id, target.actor_id, 2,
                EffectExpiration(caster.actor_id, "start", occurrence), self._spell_dc(state, caster, "tempest_surge")))
            events.append(Event("condition_applied", caster.actor_id, target.actor_id, f"{target.label} is clumsy 2 until {caster.label}'s next turn starts.", check=check))
        return events + self._apply_spell_damage(state, dice, caster, target, damage, check=check, source="tempest_surge", damage_type="electricity", continuation=continuation)

    def _roll_vitality_lash_save(self, state, dice, caster, target, continuation):
        if continuation.spell_source_kind not in {"spontaneous", "prepared"} or continuation.spell_actions != 2:
            raise _Rejected("Vitality Lash requires its two-action cantrip form.")
        return self._roll_spell_save(
            state, dice, caster, target, continuation, "vitality_lash", "fortitude",
        )

    def _resolve_vitality_lash_result(self, state, dice, caster, target, check, continuation):
        status_bonus = combine_modifiers(self._courageous_anthem_damage_modifiers(state, caster))
        raw = resolve_damage(DamagePacket("Vitality Lash", "vitality", 6, 2, status_bonus), dice.draw)
        damage = basic_save_damage_result(raw, check.degree)
        events = [Event("spell_save", caster.actor_id, target.actor_id, _spell_save_text(target, check, statistic="Fortitude"), check=check)]
        if check.degree is DegreeOfSuccess.CRITICAL_FAILURE:
            occurrence = state.actor_start_counts.get(caster.actor_id, 0) + 1
            state.condition_effects.append(ActiveConditionEffect(f"vitality_lash:enfeebled:{caster.actor_id}:{target.actor_id}:{state.next_choice_id}", "enfeebled", caster.actor_id, target.actor_id, 1, EffectExpiration(caster.actor_id, "start", occurrence), self._spell_dc(state, caster, "vitality_lash")))
            events.append(Event("condition_applied", caster.actor_id, target.actor_id, f"{target.label} is enfeebled 1 until {caster.label}'s next turn starts.", check=check))
        return events + self._apply_spell_damage(state, dice, caster, target, damage, check=check, source="vitality_lash", damage_type="vitality", continuation=continuation)

    def _roll_telekinetic_projectile(self, state, dice, caster, target, continuation):
        item_id = continuation.spell_target_item_id
        item_positions = [
            position for position, item_ids in (state.ground_items or {}).items()
            if item_id is not None and item_id in item_ids
        ]
        item = state.item_instances.get(item_id or "")
        profile = (
            telekinetic_projectile_object_profile(item.definition_id)
            if item is not None else None
        )
        if (
            item_id is None or len(item_positions) != 1 or profile is None
            or profile[0] > 1 or grid_distance_feet(caster.position, item_positions[0]) > 30
        ):
            return [Event("action_stopped", caster.actor_id, target.actor_id, "Telekinetic Projectile's selected loose object is no longer on the ground.")]
        if not continuation.attack_count_committed:
            caster.strikes_this_turn += 1
            continuation.attack_count_committed = True
        breakdown = list(self._spell_attack_modifier_breakdown(
            state, caster, continuation, "telekinetic_projectile"
        ))
        if continuation.sure_strike_used:
            breakdown = list(self._sure_strike_attack_modifiers(breakdown))
        rolled_dice = (
            (dice.draw(20), dice.draw(20))
            if continuation.sure_strike_used else (dice.draw(20),)
        )
        check = replace(
            resolve_check(
                max(rolled_dice), combine_modifiers(breakdown),
                self._effective_ac(
                    target, state=state, attacker_id=caster.actor_id,
                    lesser_cover=self._has_lesser_cover(state, caster, target),
                ),
                attack_count=max(1, continuation.attack_count),
                map_penalty=continuation.attack_penalty,
                traits=spell_traits("telekinetic_projectile"),
            ),
            modifier_breakdown=tuple(breakdown), dice=rolled_dice,
        )
        if (
            caster.health_mode is HealthMode.PC
            and caster.hero_points > 0
            and not continuation.sure_strike_used
        ):
            self._set_pending(
                state, kind="spell_attack_hero_reroll", owner_actor_id=caster.actor_id,
                prompt=f"{caster.label} may keep this Telekinetic Projectile attack or spend 1 Hero Point to reroll.",
                options=(ChoiceOption("keep", "Keep result"), ChoiceOption("spend_hero_point", "Spend 1 Hero Point and reroll")),
                actor_id=caster.actor_id, target_id=target.actor_id, check=check, check_kind="spell_attack",
                check_owner_actor_id=caster.actor_id, spell_id="telekinetic_projectile", slot_id=continuation.slot_id,
                spell_actions=continuation.spell_actions, continuation=continuation,
            )
            return [Event("spell_attack", caster.actor_id, target.actor_id, _spell_attack_text(check, "Telekinetic Projectile"), check=check)]
        return self._resolve_telekinetic_projectile_result(state, dice, caster, target, check, continuation)

    def _resolve_telekinetic_projectile_result(self, state, dice, caster, target, check, continuation):
        events = [Event("spell_attack", caster.actor_id, target.actor_id, _spell_attack_text(check, "Telekinetic Projectile"), check=check)]
        if check.degree in {DegreeOfSuccess.SUCCESS, DegreeOfSuccess.CRITICAL_SUCCESS}:
            item = state.item_instances.get(continuation.spell_target_item_id or "")
            profile = telekinetic_projectile_object_profile(item.definition_id) if item is not None else None
            if profile is None:
                raise _Rejected("Telekinetic Projectile's saved object no longer has a supported physical profile.")
            _bulk, damage_type = profile
            damage = resolve_damage(DamagePacket("Telekinetic Projectile", damage_type, 6, 2, 0), dice.draw, critical=check.degree is DegreeOfSuccess.CRITICAL_SUCCESS)
            events.extend(self._apply_spell_damage(state, dice, caster, target, damage, check=check, source="telekinetic_projectile", damage_type=damage_type, attacker_critical=check.degree is DegreeOfSuccess.CRITICAL_SUCCESS, continuation=continuation))
            return events
        continuation.stage = "done"
        return events + self._complete_action(state, caster, [], dice=dice)

    def _apply_persistent_effect(self, state, caster, target, spell_id, damage_type, *, dice=(), flat=0) -> None:
        """Install one comparable persistent type, replacing only a weaker one."""
        # These are the only admitted non-blood-bearing profiles.  Keep this
        # finite fact here until creature physiology becomes a first-class
        # sheet field; Gouging Claw's initial damage still resolves normally.
        if damage_type == "bleed" and target.definition_id in {
            "skeleton_guard_mc3193", "zombie_shambler_mc3249",
        }:
            return
        previous = next(
            (effect for effect in state.persistent_effects
             if effect.target_actor_id == target.actor_id and effect.damage_type == damage_type),
            None,
        )
        if previous is not None:
            # The selected spells only compare flat bleed amounts.  Do not
            # invent a cross-die strength ordering: that needs a GM ruling.
            if bool(previous.dice) != bool(dice) or previous.dice != tuple(dice):
                raise _Unsupported("Replacing incomparable persistent damage needs an explicit GM ruling.")
            if flat <= previous.flat:
                return
            state.persistent_effects.remove(previous)
        state.persistent_effects.append(PersistentDamageEffect(
            f"persistent:{spell_id}:{caster.actor_id}:{target.actor_id}:{state.next_choice_id}",
            caster.actor_id, target.actor_id, spell_id, damage_type, tuple(dice), flat,
            state.world_time_seconds + 60,
        ))

    def _roll_persistent_attack_spell(self, state, dice, caster, target, continuation):
        spell_id = continuation.spell_id
        assert spell_id in {"ignition", "gouging_claw"}
        if (
            (spell_id == "ignition" and continuation.spell_mode not in {"ranged", "melee"})
            or (spell_id == "gouging_claw" and continuation.spell_mode not in {"piercing", "slashing"})
        ):
            raise _Rejected(f"{SPELLS[spell_id].name}'s saved attack profile is invalid.")
        if spell_id == "ignition" and continuation.spell_mode == "melee" and grid_distance_feet(caster.position, target.position) > 5:
            raise _Rejected("Ignition's melee target is no longer within reach.")
        if spell_id == "gouging_claw" and target.actor_id not in self._spell_targets_for_cast(
            state, caster, spell_id, continuation.spell_actions,
            reach_spell_effective_range_ft=continuation.reach_spell_effective_range_ft,
        ):
            raise _Rejected("Gouging Claw's target is no longer within range.")
        if not continuation.attack_count_committed:
            caster.strikes_this_turn += 1
            continuation.attack_count_committed = True
        breakdown = list(self._spell_attack_modifier_breakdown(state, caster, continuation, spell_id))
        if continuation.sure_strike_used:
            breakdown = list(self._sure_strike_attack_modifiers(breakdown))
        rolled = (dice.draw(20), dice.draw(20)) if continuation.sure_strike_used else (dice.draw(20),)
        check = replace(resolve_check(
            max(rolled), combine_modifiers(breakdown),
            self._effective_ac(target, state=state, attacker_id=caster.actor_id, lesser_cover=self._has_lesser_cover(state, caster, target)),
            attack_count=max(1, continuation.attack_count), map_penalty=continuation.attack_penalty,
            traits=spell_traits(spell_id),
        ), modifier_breakdown=tuple(breakdown), dice=rolled)
        if caster.health_mode is HealthMode.PC and caster.hero_points and not continuation.sure_strike_used:
            self._set_pending(
                state, kind="spell_attack_hero_reroll", owner_actor_id=caster.actor_id,
                prompt=f"{caster.label} may keep this {SPELLS[spell_id].name} attack or spend 1 Hero Point to reroll.",
                options=(ChoiceOption("keep", "Keep result"), ChoiceOption("spend_hero_point", "Spend 1 Hero Point and reroll")),
                actor_id=caster.actor_id, target_id=target.actor_id, check=check,
                check_kind="spell_attack", check_owner_actor_id=caster.actor_id,
                spell_id=spell_id, slot_id=continuation.slot_id, spell_actions=continuation.spell_actions,
                damage_context=continuation.spell_mode,
                continuation=continuation,
            )
            return [Event("spell_attack", caster.actor_id, target.actor_id, _spell_attack_text(check, SPELLS[spell_id].name), check=check)]
        return self._resolve_persistent_attack_spell_result(state, dice, caster, target, check, continuation)

    def _roll_tangle_vine(self, state, dice, caster, target, continuation):
        """Make Tangle Vine's ordinary spell attack and retain its source identity."""
        if not continuation.attack_count_committed:
            caster.strikes_this_turn += 1
            continuation.attack_count_committed = True
        breakdown = list(self._spell_attack_modifier_breakdown(state, caster, continuation, "tangle_vine"))
        if continuation.sure_strike_used:
            breakdown = list(self._sure_strike_attack_modifiers(breakdown))
        rolled = (dice.draw(20), dice.draw(20)) if continuation.sure_strike_used else (dice.draw(20),)
        check = replace(resolve_check(
            max(rolled), combine_modifiers(breakdown),
            self._effective_ac(target, state=state, attacker_id=caster.actor_id, lesser_cover=self._has_lesser_cover(state, caster, target)),
            attack_count=max(1, continuation.attack_count), map_penalty=continuation.attack_penalty,
            traits=spell_traits("tangle_vine"),
        ), modifier_breakdown=tuple(breakdown), dice=rolled)
        if caster.health_mode is HealthMode.PC and caster.hero_points and not continuation.sure_strike_used:
            self._set_pending(
                state, kind="spell_attack_hero_reroll", owner_actor_id=caster.actor_id,
                prompt=f"{caster.label} may keep this Tangle Vine attack or spend 1 Hero Point to reroll.",
                options=(ChoiceOption("keep", "Keep result"), ChoiceOption("spend_hero_point", "Spend 1 Hero Point and reroll")),
                actor_id=caster.actor_id, target_id=target.actor_id, check=check, check_kind="spell_attack",
                check_owner_actor_id=caster.actor_id, spell_id="tangle_vine", slot_id=continuation.slot_id,
                spell_actions=continuation.spell_actions, continuation=continuation,
            )
            return [Event("spell_attack", caster.actor_id, target.actor_id, _spell_attack_text(check, "Tangle Vine"), check=check)]
        return self._resolve_tangle_vine_result(state, dice, caster, target, check, continuation)

    def _resolve_tangle_vine_result(self, state, dice, caster, target, check, continuation):
        events = [Event("spell_attack", caster.actor_id, target.actor_id, _spell_attack_text(check, "Tangle Vine"), check=check)]
        if check.degree in {DegreeOfSuccess.SUCCESS, DegreeOfSuccess.CRITICAL_SUCCESS}:
            occurrence = state.actor_start_counts.get(caster.actor_id, 0) + 1
            base_id = f"tangle_vine:{caster.actor_id}:{target.actor_id}:{state.next_choice_id}"
            state.condition_effects = [
                effect for effect in state.condition_effects
                if not (effect.source_actor_id == caster.actor_id and effect.target_actor_id == target.actor_id and effect.effect_id.startswith("tangle_vine:"))
            ]
            expiration = EffectExpiration(caster.actor_id, "start", occurrence)
            state.condition_effects.append(ActiveConditionEffect(
                f"{base_id}:speed", "speed_penalty", caster.actor_id, target.actor_id, 10, expiration, self._spell_dc(state, caster, "tangle_vine"),
            ))
            if check.degree is DegreeOfSuccess.CRITICAL_SUCCESS:
                state.condition_effects.append(ActiveConditionEffect(
                    f"{base_id}:immobilized", "immobilized", caster.actor_id, target.actor_id, 1, expiration, self._spell_dc(state, caster, "tangle_vine"),
                ))
            events.append(Event(
                "tangle_vine_applied", caster.actor_id, target.actor_id,
                f"{target.label} is tangled by Tangle Vine until {caster.label}'s next turn starts.", check=check,
            ))
        continuation.stage = "done"
        return events + self._complete_action(state, caster, [], dice=dice)

    def _resolve_persistent_attack_spell_result(self, state, dice, caster, target, check, continuation):
        spell_id = continuation.spell_id
        events = [Event("spell_attack", caster.actor_id, target.actor_id, _spell_attack_text(check, SPELLS[spell_id].name), check=check)]
        if check.degree in {DegreeOfSuccess.SUCCESS, DegreeOfSuccess.CRITICAL_SUCCESS}:
            sides = 6 if spell_id == "ignition" and continuation.spell_mode == "melee" else 4 if spell_id == "ignition" else 6
            damage_type = "fire" if spell_id == "ignition" else continuation.spell_mode
            damage = resolve_damage(DamagePacket(SPELLS[spell_id].name, damage_type, sides, 2, 0), dice.draw, critical=check.degree is DegreeOfSuccess.CRITICAL_SUCCESS)
            # Install persistence only after initial damage clears the public
            # damage resolver.  That prevents it when initial damage is fully
            # negated and keeps saved defenses/Shield choices atomic.
            if spell_id == "ignition" and check.degree is DegreeOfSuccess.CRITICAL_SUCCESS:
                continuation.stage = f"persistent:fire:{6 if continuation.spell_mode == 'melee' else 4}:0"
            elif spell_id == "gouging_claw":
                continuation.stage = f"persistent:bleed:0:{4 if check.degree is DegreeOfSuccess.CRITICAL_SUCCESS else 2}"
            else:
                continuation.stage = "done"
            return events + self._apply_spell_damage(state, dice, caster, target, damage, check=check, source=spell_id, damage_type=damage_type, attacker_critical=check.degree is DegreeOfSuccess.CRITICAL_SUCCESS, continuation=continuation)
        continuation.stage = "done"
        return events + self._complete_action(state, caster, [], dice=dice)

    def _roll_enfeeble_save(self, state, dice, caster, target, continuation):
        return self._roll_direct_fortitude_save(
            state, dice, caster, target, continuation, "enfeeble"
        )

    def _roll_direct_fortitude_save(self, state, dice, caster, target, continuation, spell_id):
        return self._roll_spell_save(
            state, dice, caster, target, continuation, spell_id, "fortitude",
        )

    def _resolve_command_result(self, state, dice, caster, target, continuation, check):
        """Apply Command exactly once after its saved response window."""
        if continuation.stage == "done":
            raise _Rejected("Command's saved result was already applied.")
        if check.degree.value < 2:
            actions = 3 if check.degree.value == 0 else 1
            state.condition_effects.append(ActiveConditionEffect(
                effect_id=f"commanded:{caster.actor_id}:{target.actor_id}:{continuation.spell_mode}:{state.next_choice_id}",
                kind="commanded", source_actor_id=caster.actor_id, target_actor_id=target.actor_id,
                value=actions,
                expiration=EffectExpiration(target.actor_id, "end", state.actor_end_counts.get(target.actor_id, 0) + 1),
                command_mode=continuation.spell_mode,
            ))
            target.reaction_available = False
        continuation.stage = "done"
        return self._complete_action(state, caster, [Event(
            "command_save", caster.actor_id, target.actor_id,
            f"{target.label} rolls Will against Command: {check.degree.label().lower()} ({continuation.spell_mode}).", check=check,
        )], dice=dice)

    def _validate_committed_command_save(self, state, caster, target, continuation, check) -> None:
        """Recompute the already-committed Command save for a saved response."""
        definition = get_definition(caster.definition_id)
        source_valid = False
        if continuation.spell_source_kind == "prepared":
            source_valid = any(
                slot.slot_id == continuation.slot_id and slot.spell_id == "command"
                and slot.spent and not slot.cantrip and slot.rank == 1
                for slot in caster.prepared_slots
            ) and any(slot.spell_id == "command" for slot in definition.prepared_spells)
        elif continuation.spell_source_kind == "spontaneous":
            source_valid = any(
                slot.slot_id == continuation.slot_id and slot.rank == 1 and slot.remaining < slot.capacity
                for slot in caster.spontaneous_slots
            ) and any(
                spell.spell_id == "command" and spell.rank == 1 and not spell.cantrip
                for spell in definition.spontaneous_spells
            )
        if (
            not source_valid or continuation.slot_id is None or continuation.spell_actions != 2
            or continuation.target_id != target.actor_id or continuation.spell_target_id != target.actor_id
            or continuation.spell_mode not in {"approach", "flee", "release", "prone", "stand"}
            or continuation.spell_source_kind not in {"prepared", "spontaneous"}
            or continuation.include_self is not None or continuation.target_ids
        ):
            raise ValueError("save has invalid committed Command source provenance")
        breakdown = self._spell_save_modifier_breakdown(state, target, continuation, "command", statistic="will")
        expected = replace(
            resolve_check(check.die, combine_modifiers(breakdown), self._spell_dc(state, caster, "command")),
            modifier_breakdown=tuple(breakdown),
        )
        if check != expected:
            raise ValueError("save has invalid committed Command save provenance")

    def _counter_performance_reactor(self, state, target):
        for candidate in state.creatures.values():
            definition = get_definition(candidate.definition_id)
            if (
                candidate.team == target.team
                and not candidate.dead and not candidate.unconscious and not candidate.defeated
                and candidate.reaction_available and candidate.focus_points > 0
                and "counter_performance" in definition.abilities
                and "counter_performance_singing" in definition.abilities
                and any(item.spell_id == "counter_performance" for item in definition.focus_spells)
                and grid_distance_feet(candidate.position, target.position) <= 60
            ):
                return candidate
        return None

    def _offer_counter_performance_choice(self, state, caster, target, continuation, check) -> bool:
        """Pause one auditory Command save before its rider, if a choice exists."""
        if "auditory" not in spell_traits("command"):
            return False
        reactor = self._counter_performance_reactor(state, target)
        options = []
        if reactor is not None:
            options.append(ChoiceOption("counter_performance", f"Use {reactor.label}'s Counter Performance"))
        if target.health_mode is HealthMode.PC and target.hero_points > 0:
            options.append(ChoiceOption("spend_hero_point", "Spend 1 Hero Point and reroll"))
        if not options:
            return False
        options.append(ChoiceOption("keep", "Keep result"))
        self._set_pending(state, kind="counter_performance_save_choice", owner_actor_id=target.actor_id,
            prompt=f"{target.label} chooses Counter Performance, a Hero Point reroll, or the Command Will save result.",
            options=tuple(options), details=(
                f"Original save: d20 {check.die} + {check.modifier} = {check.total} vs DC {check.dc}.",
                f"Degree: {check.degree.label()}.",
                "Counter Performance and a Hero Point reroll are both fortune effects; choose at most one for this save.",
            ), actor_id=caster.actor_id, target_id=target.actor_id, check=check,
            check_kind="counter_performance_save", check_owner_actor_id=target.actor_id,
            spell_id="command", slot_id=continuation.slot_id, spell_actions=continuation.spell_actions,
            continuation=continuation)
        return True

    def _start_counter_performance(self, state, dice, pending):
        caster, target, continuation, original = (
            state.creatures.get(pending.actor_id or ""), state.creatures.get(pending.target_id or ""),
            pending.continuation, pending.check,
        )
        if caster is None or target is None or continuation is None or original is None:
            raise _Rejected("The saved Counter Performance trigger is incomplete.")
        bard = self._counter_performance_reactor(state, target)
        if bard is None:
            raise _Rejected("No eligible Bard can Counter Performance for this save.")
        active_actor_id = state.initiative_order[state.active_index] if state.initiative_order else None
        active_start = state.actor_start_counts.get(active_actor_id or "", 0)
        if active_actor_id is None or (bard.composition_cast_turn_actor_id, bard.composition_cast_turn_start) == (active_actor_id, active_start):
            raise _Rejected("Only one composition spell can be cast each turn.")
        performance_modifier = next(
            (modifier for skill, _rank, modifier in get_definition(bard.definition_id).skills if skill == "performance"),
            None,
        )
        if performance_modifier is None:
            raise _Rejected("Counter Performance requires an admitted Performance modifier.")
        bard.reaction_available = False
        clear_pending_spellshape(bard)
        bard.focus_points -= 1
        bard.composition_cast_turn_actor_id, bard.composition_cast_turn_start = active_actor_id, active_start
        state.active_effects[:] = [effect for effect in state.active_effects if not (
            effect.kind == "courageous_anthem" and effect.source_actor_id == bard.actor_id
        )]
        performance = replace(resolve_check(dice.draw(20), performance_modifier, original.dc),
            modifier_breakdown=(Modifier(performance_modifier, "untyped", "printed Performance modifier"),))
        events = [Event("counter_performance_cast", bard.actor_id, target.actor_id,
            f"{bard.label} sings Counter Performance, spends their reaction and 1 Focus Point, and ends their prior composition.", check=performance)]
        if bard.hero_points > 0:
            self._set_pending(state, kind="counter_performance_bard_hero_reroll", owner_actor_id=bard.actor_id,
                prompt=f"{bard.label} may keep the Counter Performance check or spend 1 Hero Point to reroll it.",
                options=(ChoiceOption("keep", "Keep Performance result"), ChoiceOption("spend_hero_point", "Spend 1 Hero Point and reroll Performance")),
                details=(f"Performance: d20 {performance.die} + {performance.modifier} = {performance.total} vs DC {performance.dc}.",
                    "This is the Bard's separate check; the beneficiary cannot spend their Hero Point on it."),
                actor_id=caster.actor_id, target_id=target.actor_id, check=performance,
                check_kind="counter_performance_check", check_owner_actor_id=bard.actor_id,
                spell_id="command", slot_id=continuation.slot_id, spell_actions=continuation.spell_actions,
                continuation=replace(continuation, spell_check=original, stage="counter_performance"))
            return events
        return events + self._resolve_counter_performance_result(state, dice, caster, target, continuation, original, performance, bard)

    def _resolve_counter_performance_result(self, state, dice, caster, target, continuation, original, performance, bard):
        """Use the better numeric total while retaining the beneficiary die."""
        substituted = (
            original
            if original.total >= performance.total
            else replace(resolve_check(original.die, performance.total - original.die, original.dc),
                modifier_breakdown=(Modifier(
                    performance.total - original.die,
                    "untyped",
                    "Counter Performance substituted total",
                ),))
        )
        chosen = "original save" if substituted is original else "Performance total"
        events = [Event("counter_performance_result", bard.actor_id, target.actor_id,
            f"{bard.label} compares Counter Performance with {target.label}'s Command save and uses the better numeric result; the beneficiary's original natural die still adjusts the degree.",
            check=performance, details=(f"Chosen result: {chosen}; beneficiary die: {original.die}; save degree: {substituted.degree.label()}.",))]
        return events + self._resolve_command_result(state, dice, caster, target, continuation, substituted)

    def _resolve_spell_save_result(
        self, state, dice, caster, target, check, continuation,
    ):
        """Resume a committed spell save through its admitted result rider."""
        resolvers = {
            "fear": self._resolve_fear_result,
            "breathe_fire": self._resolve_breathe_fire_result,
            "caustic_blast": self._resolve_caustic_blast_result,
            "gale_blast": self._resolve_gale_blast_result,
            "electric_arc": self._resolve_electric_arc_result,
            "tempest_surge": self._resolve_tempest_surge_result,
            "vitality_lash": self._resolve_vitality_lash_result,
            "harm": self._resolve_harm_result,
            "frostbite": self._resolve_direct_fortitude_result,
            "enfeeble": self._resolve_direct_fortitude_result,
            "void_warp": self._resolve_void_warp_result,
            "daze": self._resolve_daze_result,
        }
        try:
            resolver = resolvers[continuation.spell_id]
        except KeyError as error:
            raise _Rejected("The pending spell save has no admitted result rider.") from error
        return resolver(state, dice, caster, target, check, continuation)

    def _resolve_harm_result(self, state, dice, caster, target, check, continuation):
        """Resolve the finite rank-one two-action Harm basic Fortitude form."""
        raw = resolve_damage(DamagePacket("Harm", "void", 8, 1, 0), dice.draw)
        damage = basic_save_damage_result(raw, check.degree)
        events = [Event(
            "spell_save", caster.actor_id, target.actor_id,
            _spell_save_text(target, check, statistic="Fortitude"), check=check,
        )]
        return events + self._apply_spell_damage(
            state, dice, caster, target, damage, check=check, source="harm",
            damage_type="void", continuation=continuation,
        )

    def _resolve_direct_fortitude_result(self, state, dice, caster, target, check, continuation):
        spell_id = continuation.spell_id
        events = [Event("spell_save", caster.actor_id, target.actor_id, _spell_save_text(target, check), check=check)]
        if spell_id == "enfeeble":
            values = {DegreeOfSuccess.SUCCESS: (1, 1), DegreeOfSuccess.FAILURE: (2, 10), DegreeOfSuccess.CRITICAL_FAILURE: (3, 10)}
            if check.degree in values:
                value, duration = values[check.degree]
                self._apply_enfeebled(state, caster, target, value, duration_rounds=duration)
                events.append(Event("effect_applied", caster.actor_id, target.actor_id, f"{target.label} is enfeebled {value} for {'1 minute' if duration == 10 else '1 round'}."))
            continuation.stage = "done"
            self._record_arcane_bond_completed(caster, continuation)
            return events + self._complete_action(state, caster, [], dice=dice)
        damage = resolve_damage(DamagePacket("Frostbite", "cold", 4, 2, 0), dice.draw)
        damage = basic_save_damage_result(damage, check.degree)
        if check.degree is DegreeOfSuccess.CRITICAL_FAILURE:
            state.active_effects.append(ActiveSpellEffect(
                effect_id=f"frostbite_weakness:{caster.actor_id}:{target.actor_id}:{state.next_choice_id}",
                kind="frostbite_weakness", source_actor_id=caster.actor_id, target_actor_id=target.actor_id,
                value=1, expires_at_source_start=state.actor_start_counts.get(caster.actor_id, 0) + 1,
                expires_at_world_time=state.world_time_seconds + 6,
            ))
            events.append(Event("effect_applied", caster.actor_id, target.actor_id, f"{target.label} gains weakness 1 to bludgeoning until {caster.label}'s next turn."))
        return events + self._apply_spell_damage(state, dice, caster, target, damage, check=check, source="frostbite", damage_type="cold", continuation=continuation)

    def _continue_electric_arc(self, state, dice, caster, continuation):
        continuation.guidance_checked = False
        continuation.guidance_bonus = 0
        try:
            index = int((continuation.stage or "electric_arc:0").split(":", 1)[1])
        except (IndexError, ValueError):
            raise _Rejected("Electric Arc's saved recipient progress is invalid.")
        if index < len(continuation.target_ids):
            return self._resolve_electric_arc(state, dice, caster, continuation)
        continuation.stage = "done"
        return self._complete_action(state, caster, [], dice=dice)

    def _resolve_runic_body(self, state, dice, caster, target, continuation):
        if continuation.spell_source_kind != "prepared" or continuation.spell_actions != 2:
            raise _Rejected("Runic Body requires a prepared two-action rank-1 slot.")
        if target.actor_id not in self._spell_targets_for_cast(
            state, caster, "runic_body", 2,
            reach_spell_effective_range_ft=continuation.reach_spell_effective_range_ft,
        ):
            return [Event("action_stopped", caster.actor_id, target.actor_id, "Runic Body's willing target is no longer within touch range.")]
        state.active_effects[:] = [
            effect for effect in state.active_effects
            if not (effect.kind == "runic_body" and effect.target_actor_id == target.actor_id)
        ]
        state.active_effects.append(ActiveSpellEffect(
            effect_id=f"runic_body:{caster.actor_id}:{target.actor_id}:{state.next_choice_id}",
            kind="runic_body", source_actor_id=caster.actor_id, target_actor_id=target.actor_id,
            value=1, expires_at_source_start=state.actor_start_counts.get(caster.actor_id, 0) + 10,
            expires_at_world_time=state.world_time_seconds + 60,
        ))
        continuation.stage = "done"
        self._record_arcane_bond_completed(caster, continuation)
        return [Event("effect_applied", caster.actor_id, target.actor_id, f"Runic Body grants {target.label}'s unarmed attacks +1 item to attack and two weapon damage dice for 1 minute.")] + self._complete_action(state, caster, [], dice=dice)

    @staticmethod
    def _record_arcane_bond_completed(caster, continuation) -> None:
        if (
            continuation.spell_source_kind == "prepared"
            and continuation.slot_id is not None
            and "arcane_bond" in get_definition(caster.definition_id).abilities
        ):
            caster.arcane_bond_eligible_slots.add(continuation.slot_id)

    def _resolve_light(self, state, dice, caster, continuation):
        """Create one rank-1 Light orb after its manipulate action resolves."""
        point = continuation.light_point
        color = continuation.light_color
        if not isinstance(point, Position) or not in_bounds(
            point, state.map_width, state.map_height
        ):
            raise _Rejected("Light's saved point is no longer inside the encounter map.")
        if not isinstance(color, str) or not color:
            raise _Rejected("Light's saved color is invalid.")
        if continuation.light_orb_id is not None:
            # A saved continuation can be resumed exactly once. If it already
            # names an orb, validate it rather than silently creating a copy.
            if any(orb.stable_id == continuation.light_orb_id for orb in state.light_orbs):
                return self._complete_action(state, caster, [], dice=dice)
            raise _Rejected("Light's saved orb identity is unavailable.")
        owned_orbs = [
            orb for orb in state.light_orbs if orb.caster_actor_id == caster.actor_id
        ]
        replacement_id = continuation.light_replacement_orb_id
        if len(owned_orbs) >= 4:
            if len(owned_orbs) != 4 or replacement_id is None:
                raise _Rejected(
                    "The caster already has four active Light orbs; a saved fifth cast "
                    "must name one replacement_orb_id."
                )
            if not any(orb.stable_id == replacement_id for orb in owned_orbs):
                if any(orb.stable_id == replacement_id for orb in state.light_orbs):
                    raise _Rejected("Light replacement_orb_id belongs to another caster.")
                raise _Rejected("Light replacement_orb_id is no longer active.")
        elif replacement_id is not None:
            raise _Rejected(
                "Light replacement_orb_id is only valid when four active orbs exist."
            )
        stable_id = f"light:{caster.actor_id}:{state.next_light_orb_id}"
        state.next_light_orb_id += 1
        orb = LightOrb(
            stable_id=stable_id,
            caster_actor_id=caster.actor_id,
            rank=1,
            color=color,
            point=point,
            owner_preparation=0,
        )
        state.light_orbs.append(orb)
        if replacement_id is not None:
            # The new orb now exists, so replacement is committed. This point
            # is reached only after any cast manipulate/reaction interruption;
            # a disrupted cast therefore preserves all four prior orbs.
            state.light_orbs[:] = [
                existing for existing in state.light_orbs
                if existing.stable_id != replacement_id
            ]
        continuation.light_orb_id = stable_id
        events = [Event(
            "light_orb_created",
            caster.actor_id,
            None,
            f"{caster.label} creates a {color} Light orb at {_coord(point)}; bright within 20 feet and dim for the next 20 feet.",
            position=point,
            details=(stable_id, color, "bright_within_20ft", "dim_next_20ft"),
        )]
        attachment_id = continuation.light_attachment_actor_id
        if attachment_id is None:
            continuation.stage = "done"
            return events + self._complete_action(state, caster, [], dice=dice)
        attached = state.creatures.get(attachment_id)
        if attached is None or attached.position != point:
            # The orb was successfully created at the chosen point. Consent
            # was optional and the creature must still occupy that space when
            # the post-cast willingness decision is presented.
            continuation.light_attachment_actor_id = None
            continuation.stage = "done"
            events.append(Event(
                "light_attachment_unavailable",
                caster.actor_id,
                attachment_id,
                "The intended Light carrier is no longer in the orb's point; the orb remains there.",
                position=point,
            ))
            return events + self._complete_action(state, caster, [], dice=dice)
        self._set_pending(
            state,
            kind="spell_willingness",
            owner_actor_id=attached.actor_id if attached.health_mode is HealthMode.PC else None,
            prompt=f"Is {attached.label} willing to carry the Light orb?",
            options=(ChoiceOption("willing", "Willing"), ChoiceOption("unwilling", "Unwilling")),
            actor_id=caster.actor_id,
            target_id=attached.actor_id,
            spell_id="light",
            spell_actions=2,
            continuation=continuation,
        )
        events.append(Event(
            "spell_willingness",
            caster.actor_id,
            attached.actor_id,
            f"Ask {attached.label} whether to carry Light orb {stable_id}.",
        ))
        return events

    def _resolve_spell_concealment(
        self, state, dice, caster, target, continuation, *, item_facts=None
    ) -> list[Event] | None:
        """Resolve the shared DC 5 gate for admitted targeted spells.

        Costs, casting reactions, and Grabbed's manipulate check have already
        been handled before this point.  The continuation records the gate so
        a saved Hero choice resumes the same spell exactly once.
        """
        spell_id = continuation.spell_id
        if continuation.sure_strike_used:
            continuation.concealment_checked = True
            return None
        if continuation.concealment_checked:
            return None
        continuation.concealment_checked = True
        if spell_id not in CONCEALMENT_TARGETED_SPELL_IDS:
            return None
        item_target = spell_id == "runic_weapon"
        if item_target:
            if item_facts is None or continuation.spell_target_item_id is None:
                return None
            _item, wielder_id, position = item_facts
            if wielder_id == caster.actor_id:
                return None
            concealed = self._runic_weapon_item_concealed(state, caster, item_facts)
            target_id = continuation.spell_target_item_id
            target_label = target_id
        else:
            if target is None:
                return None
            # Self-target Guidance and Stabilize are likewise visible to the
            # caster; area Heal has already bypassed this gate above.
            if spell_id == "heal" and continuation.spell_actions == 3:
                return None
            if spell_id in {"heal", "soothe", "guidance", "stabilize"} and target.actor_id == caster.actor_id:
                return None
            concealed = self.target_is_concealed(caster.actor_id, target.actor_id)
            if (
                "storm_born" in get_definition(caster.definition_id).abilities
                and self._target_weather_concealed(caster.actor_id, target.actor_id)
            ):
                concealed = (
                    self.target_illumination(caster.actor_id, target.actor_id) == "dim"
                    and get_definition(caster.definition_id).vision == "ordinary"
                )
            target_id = target.actor_id
            target_label = target.label
        if not concealed:
            return None
        check = resolve_check(dice.draw(20), 0, 5)
        events = [Event(
            "concealment_flat_check",
            caster.actor_id, target_id,
            f"{caster.label} attempts the DC 5 concealment flat check against {target_label}: "
            f"d20 {check.die}; {check.degree.label().lower()}.",
            check=check,
        )]
        if caster.health_mode is HealthMode.PC and caster.hero_points > 0:
            self._set_pending(
                state,
                kind="concealment_hero_reroll",
                owner_actor_id=caster.actor_id,
                prompt=(
                    f"{caster.label} may keep the concealment flat check or spend 1 Hero Point "
                    "to reroll it."
                ),
                options=(
                    ChoiceOption("keep", "Keep result"),
                    ChoiceOption("spend_hero_point", "Spend 1 Hero Point and reroll"),
                ),
                details=(f"Original flat check: d20 {check.die} vs DC 5.",),
                actor_id=caster.actor_id,
                target_id=None if item_target else target.actor_id,
                attack_id="divine_lance" if spell_id == "divine_lance" else None,
                attack_penalty=continuation.attack_penalty,
                attack_count=continuation.attack_count,
                check=check,
                check_kind="concealment",
                spell_id=spell_id,
                slot_id=continuation.slot_id,
                spell_actions=continuation.spell_actions,
                actions_cost=continuation.spell_actions,
                spell_target_item_id=(
                    continuation.spell_target_item_id if item_target else None
                ),
                continuation=continuation,
                concealment_checked=True,
            )
            return events
        return events + self._finish_spell_concealment(
            state, dice, caster, target, continuation, check,
            item_id=target_id if item_target else None,
        )

    def _finish_spell_concealment(
        self, state, dice, caster, target, continuation, check, *, item_id=None
    ) -> list[Event]:
        """Finish a saved spell targeting gate and resume its cast on success."""
        target_id = target.actor_id if target is not None else item_id
        if target_id is None:
            raise _Rejected("The concealment continuation has no target identity.")
        target_label = target.label if target is not None else item_id
        if check.degree < DegreeOfSuccess.SUCCESS:
            continuation.stage = "done"
            events = [Event(
                "concealment_failed",
                caster.actor_id,
                target_id,
                f"{caster.label} fails the concealment flat check against {target_label}; no spell check, healing die, or item effect is attempted.",
                check=check,
            )]
            # Angelic Blood Magic is selected independently before this gate.
            # A failed targeted Heal still grants its caster-side save bonus,
            # while selecting the concealed target grants nothing. The
            # manipulate disruption path never reaches this helper.
            if (
                continuation.spell_id == "heal"
                and continuation.spell_source_kind == "spontaneous"
                and continuation.blood_magic_recipient_id == caster.actor_id
            ):
                events.extend(self._apply_blood_magic(state, caster, continuation))
            # A failed concealment check suppresses the target effect, but an
            # undisrupted prepared spell was still cast and its slot spent.
            self._record_arcane_bond_completed(caster, continuation)
            return events + self._complete_action(state, caster, [], dice=dice)
        events = [Event(
            "concealment_passed",
            caster.actor_id,
            target_id,
            f"{caster.label} passes the concealment flat check against {target_label}; the spell may proceed.",
            check=check,
        )]
        events.extend(self._resolve_cast(state, dice, continuation))
        return events

    def _resolve_runic_weapon(self, state, dice, caster, continuation):
        """Apply or replace rank-1 Runic Weapon on the exact physical item."""
        # A wielder can refuse after the cast has committed its actions and
        # slot. The refusal suppresses the spell's effect, while the already
        # committed manipulate action still passes through the ordinary
        # reaction continuation. Once reactions are exhausted, finish the
        # cast without creating an item effect.
        if continuation.stage == "refused":
            continuation.stage = "done"
            self._record_arcane_bond_completed(caster, continuation)
            return self._complete_action(state, caster, [], dice=dice)
        item_id = continuation.spell_target_item_id
        if item_id is None:
            raise _Rejected("Runic Weapon's saved continuation is missing its item target.")
        try:
            item, wielder_id, _position = self._runic_weapon_target(
                state, caster, item_id,
                reach_spell_effective_range_ft=continuation.reach_spell_effective_range_ft,
            )
        except ValueError:
            return [Event(
                "action_stopped",
                caster.actor_id,
                None,
                "Runic Weapon's original physical item is no longer an eligible target.",
            )]
        if wielder_id != continuation.spell_target_wielder_id:
            return [Event(
                "action_stopped",
                caster.actor_id,
                None,
                "Runic Weapon's original item wielder changed before resolution.",
            )]
        if wielder_id not in (None, caster.actor_id) and continuation.stage != "willing":
            return [Event(
                "action_stopped",
                caster.actor_id,
                None,
                "Runic Weapon's original wielder did not complete willingness.",
            )]
        if not continuation.concealment_checked:
            concealment_events = self._resolve_spell_concealment(
                state, dice, caster, None, continuation, item_facts=(item, wielder_id, _position)
            )
            if concealment_events is not None:
                return concealment_events
        # Recasting the same rank-1 spell on this item renews its duration;
        # temporary potency/striking never mutate the permanent item snapshot.
        state.active_item_effects[:] = [
            effect for effect in state.active_item_effects
            if effect.item_id != item.instance_id
        ]
        effect = ActiveItemSpellEffect(
            effect_id=f"runic_weapon:{caster.actor_id}:{item.instance_id}:{state.next_choice_id}",
            kind="runic_weapon",
            source_actor_id=caster.actor_id,
            item_id=item.instance_id,
            expires_at_source_start=state.actor_start_counts.get(caster.actor_id, 0) + 10,
            expires_at_world_time=state.world_time_seconds + 60,
        )
        state.active_item_effects.append(effect)
        continuation.stage = "done"
        self._record_arcane_bond_completed(caster, continuation)
        return [Event(
            "item_effect_applied",
            caster.actor_id,
            None,
            f"Runic Weapon enchants {item.instance_id}: +1 item attack and two weapon damage dice for 1 minute.",
            details=(item.instance_id,),
        )] + self._complete_action(state, caster, [], dice=dice)

    def _guidance_for(self, state, actor_id):
        return next((
            effect for effect in state.active_effects
            if effect.kind == "guidance" and effect.target_actor_id == actor_id
        ), None)

    def _enfeebled_value(self, state, actor_id):
        return max((
            effect.value for effect in state.active_effects
            if effect.kind == "enfeebled" and effect.target_actor_id == actor_id
        ), default=0)

    def _offer_guidance(self, state, check_actor, continuation, effect, *, check_kind, parent=None):
        if check_kind == "weapon_attack":
            continuation.parent_continuation = parent
            self._set_pending(
                state, kind="guidance_use", owner_actor_id=check_actor.actor_id,
                prompt=f"{check_actor.label} may use Guidance for this attack check.",
                options=(ChoiceOption("use", "Use Guidance (+1 status)"), ChoiceOption("keep", "Keep Guidance for later")),
                details=(f"The effect was cast by {state.creatures[effect.source_actor_id].label}.",),
                actor_id=check_actor.actor_id, target_id=continuation.target_id,
                attack_id=continuation.attack_id, attack_penalty=continuation.attack_penalty,
                item_id=continuation.item_id,
                attack_count=continuation.attack_count, damage_type=continuation.damage_type,
                nonlethal=continuation.nonlethal, damage_bonus_dice=continuation.damage_bonus_dice,
                attack_actions_cost=continuation.attack_actions_cost,
                attack_count_cost=continuation.attack_count_cost,
                feint_off_guard_applied=continuation.feint_off_guard_applied,
                attack_target_off_guard=continuation.attack_target_off_guard,
                nimble_dodge_used=continuation.nimble_dodge_used,
                is_reaction=continuation.kind == "reaction_strike",
                continuation=continuation, check_kind=check_kind, effect_id=effect.effect_id,
            )
            return
        self._set_pending(
            state, kind="guidance_use", owner_actor_id=check_actor.actor_id,
            prompt=f"{check_actor.label} may use Guidance for this {check_kind.replace('_', ' ')}.",
            options=(ChoiceOption("use", "Use Guidance (+1 status)"), ChoiceOption("keep", "Keep Guidance for later")),
            details=(f"The effect was cast by {state.creatures[effect.source_actor_id].label}.",),
            actor_id=check_actor.actor_id,
            target_id=continuation.target_id,
            spell_id=continuation.spell_id,
            slot_id=continuation.slot_id,
            spell_actions=continuation.spell_actions,
            continuation=continuation,
            check_kind=check_kind,
            check_owner_actor_id=check_actor.actor_id,
            effect_id=effect.effect_id,
        )

    def _apply_heal_emanation(self, state, dice, continuation):
        caster = state.creatures[continuation.actor_id]
        die_sides = self._heal_die_sides(caster)
        healing = heal_roll(3, dice.draw, die_sides=die_sides)
        recipients = [
            target for target in state.creatures.values()
            if self._is_living_target(target)
            and in_heal_emanation(caster.position, target.position)
            and (target.actor_id != caster.actor_id or continuation.include_self)
        ]
        events = [Event("heal_roll", caster.actor_id, None, f"Three-action Heal rolls 1d{die_sides} ({healing.rolls[0]}) = {healing.total}; the same result applies to {len(recipients)} creature(s).")]
        events.extend(self._apply_blood_magic(state, caster, continuation))
        for target in recipients:
            events.extend(self._apply_healing(state, caster, target, healing.total, healing.rolls, continuation, roll_shared=True))
        continuation.stage = "done"
        events.extend(self._complete_action(state, caster, [], dice=dice))
        return events

    def _apply_healing(self, state, caster, target, amount, rolls, continuation, *, roll_shared=False):
        if target.dead:
            return [Event("healing_ignored", caster.actor_id, target.actor_id, f"{target.label} is dead and cannot be healed.")]
        if (
            continuation.spell_id in {"heal", "life_link"}
            and (
                target.oracle_life_mode == "death"
                or "void_healing" in get_definition(target.definition_id).abilities
            )
        ):
            return [Event("healing_ignored", caster.actor_id, target.actor_id, f"{target.label}'s death mode receives no vitality healing from {SPELLS[continuation.spell_id].name}.")]
        potency_bonus = continuation.sorcerous_potency
        halo_bonus = self._angelic_halo_healing_bonus(state, caster, target)
        status_bonus = max(potency_bonus, halo_bonus)
        if status_bonus:
            amount += status_bonus
        if "life_oracle" in get_definition(target.definition_id).abilities:
            from .oracle import healing_after_curse
            amount = healing_after_curse(
                amount, target.oracle_cursebound,
                level=get_definition(target.definition_id).level,
            )
        if target.health_mode is HealthMode.PC:
            transition = pc_healing(self._health_state(target), amount)
            self._apply_health_transition(state, target, transition)
        else:
            target.hp = min(get_definition(target.definition_id).hp, target.hp + amount)
            if target.hp > 0:
                target.unconscious = False
        if target.hp >= get_definition(target.definition_id).hp:
            state.persistent_effects[:] = [
                effect for effect in state.persistent_effects
                if not (effect.target_actor_id == target.actor_id and effect.damage_type == "bleed")
            ]
        if halo_bonus > potency_bonus:
            status_detail = " + Angelic Halo 2 status"
        elif potency_bonus:
            status_detail = " + Sorcerous Potency 1 status"
        else:
            status_detail = ""
        if continuation.spell_id == "life_link":
            text = f"{target.label} heals {amount} HP (1d4 {rolls[0]}{status_detail}); now at {target.hp} HP."
        else:
            die_sides = self._heal_die_sides(caster)
            text = f"{target.label} heals {amount} HP ({'shared ' if roll_shared else ''}1d{die_sides} {rolls[0]}{' + 8' if continuation.spell_actions == 2 else ''}{status_detail}); now at {target.hp} HP."
        events = [Event("healing", caster.actor_id, target.actor_id, text)]
        return events

    @staticmethod
    def _heal_die_sides(caster: CreatureState) -> int:
        """Return the literal Heal die for the selected casting sheet."""
        return 10 if "healing_hands" in get_definition(caster.definition_id).abilities else 8

    def _angelic_halo_healing_bonus(self, state, healer, target) -> int:
        """Return the strongest active Angelic Halo bonus at resolution."""
        bonuses = []
        for effect in state.active_effects:
            if effect.kind != "angelic_halo" or effect.target_actor_id not in state.creatures:
                continue
            source = state.creatures[effect.source_actor_id]
            if (
                target.team == source.team
                and target.actor_id != source.actor_id
                and self._is_living_target(target)
                and self._in_angelic_halo_emanation(source.position, target.position)
            ):
                bonuses.append(effect.value)
        return max(bonuses, default=0)

    def _apply_angelic_halo(self, state, caster, continuation, *, dice=None) -> list[Event]:
        """Create or replace the caster's one-minute 15-foot Heal aura."""
        state.active_effects[:] = [
            effect for effect in state.active_effects
            if not (
                effect.kind == "angelic_halo"
                and effect.source_actor_id == caster.actor_id
            )
        ]
        state.active_effects.append(ActiveSpellEffect(
            effect_id=f"angelic_halo:{caster.actor_id}:{state.next_choice_id}",
            kind="angelic_halo",
            source_actor_id=caster.actor_id,
            target_actor_id=caster.actor_id,
            value=2,
            expires_at_source_start=state.actor_start_counts.get(caster.actor_id, 0) + 10,
            expires_at_world_time=state.world_time_seconds + 60,
        ))
        continuation.stage = "done"
        return [Event(
            "angelic_halo_applied",
            caster.actor_id,
            caster.actor_id,
            f"Angelic Halo surrounds {caster.label} for 1 minute; allies within 15 feet gain +2 status HP from rank-1 Heal.",
        )] + self._complete_action(state, caster, [], dice=dice)

    def _apply_blood_magic(self, state, caster, continuation) -> list[Event]:
        """Apply Angelic Divine Aura after a successful Heal willingness check."""
        recipient_id = continuation.blood_magic_recipient_id
        if recipient_id is None:
            return []
        recipient = state.creatures.get(recipient_id)
        if recipient is None:
            raise _Rejected("The selected Blood Magic recipient no longer exists.")
        state.active_effects[:] = [
            effect for effect in state.active_effects
            if not (
                effect.kind == "blood_magic"
                and effect.source_actor_id == caster.actor_id
            )
        ]
        effect_id = f"blood_magic:{caster.actor_id}:{recipient.actor_id}:{state.next_choice_id}"
        state.active_effects.append(ActiveSpellEffect(
            effect_id=effect_id,
            kind="blood_magic",
            source_actor_id=caster.actor_id,
            target_actor_id=recipient.actor_id,
            value=1,
            expires_at_source_start=state.actor_start_counts.get(caster.actor_id, 0) + 1,
            expires_at_world_time=state.world_time_seconds + 6,
        ))
        return [Event(
            "blood_magic_applied",
            caster.actor_id,
            recipient.actor_id,
            f"Angelic Blood Magic grants {recipient.label} +1 status to saves for one round.",
        )]

    def _roll_divine_lance(self, state, dice, caster, target, continuation):
        if not continuation.guidance_checked:
            effect = self._guidance_for(state, caster.actor_id)
            if effect is not None:
                continuation.guidance_checked = True
                self._offer_guidance(state, caster, continuation, effect, check_kind="spell_attack")
                return [Event("guidance_choice", effect.source_actor_id, caster.actor_id, f"{caster.label} may use Guidance before Divine Lance.")]
        if not continuation.nimble_dodge_decided and self._nimble_dodge_available(state, caster, target):
            self._present_nimble_dodge(state, caster, target, continuation)
            return [Event(
                "nimble_dodge_choice", target.actor_id, caster.actor_id,
                f"{target.label} may use Nimble Dodge before {caster.label}'s spell attack.",
            )]
        if not continuation.attack_count_committed:
            caster.strikes_this_turn += 1
            continuation.attack_count_committed = True
        breakdown = list(self._spell_attack_modifier_breakdown(
            state, caster, continuation, "divine_lance"
        ))
        if continuation.sure_strike_used:
            breakdown = list(self._sure_strike_attack_modifiers(breakdown))
        rolled_dice = (
            (dice.draw(20), dice.draw(20))
            if continuation.sure_strike_used else (dice.draw(20),)
        )
        die = max(rolled_dice)
        traits = spell_traits("divine_lance")
        dc = self._effective_ac(
            target,
            state=state,
            lesser_cover=self._has_lesser_cover(state, caster, target),
            taking_cover=target.actor_id in state.taking_cover,
            nimble_dodge=continuation.nimble_dodge_used,
        )
        check = replace(resolve_check(
            die, combine_modifiers(breakdown), dc,
            attack_id="divine_lance", attack_count=max(1, continuation.attack_count),
            map_penalty=continuation.attack_penalty, traits=traits,
        ), modifier_breakdown=tuple(breakdown), dice=rolled_dice)
        if caster.health_mode is HealthMode.PC and caster.hero_points > 0 and not continuation.sure_strike_used:
            self._set_pending(
                state, kind="spell_attack_hero_reroll", owner_actor_id=caster.actor_id,
                prompt=f"{caster.label} may keep this Divine Lance check or spend 1 Hero Point to reroll.",
                options=(ChoiceOption("keep", "Keep result"), ChoiceOption("spend_hero_point", "Spend 1 Hero Point and reroll"),),
                details=(f"Original: d20 {die} + {check.modifier} = {check.total} vs AC {check.dc}.", f"Degree: {check.degree.label()}.",),
                actor_id=caster.actor_id, target_id=target.actor_id,
                check=check, check_kind="spell_attack", check_owner_actor_id=caster.actor_id,
                spell_id="divine_lance", slot_id=continuation.slot_id,
                spell_actions=continuation.spell_actions, continuation=continuation,
            )
            return [Event("spell_attack", caster.actor_id, target.actor_id, _spell_attack_text(check), check=check)]
        return self._resolve_divine_lance_result(state, dice, caster, target, check, continuation)

    def _resolve_divine_lance_result(self, state, dice, caster, target, check, continuation):
        events = [Event("spell_attack", caster.actor_id, target.actor_id, _spell_attack_text(check), check=check)]
        if check.degree in (DegreeOfSuccess.SUCCESS, DegreeOfSuccess.CRITICAL_SUCCESS):
            status_bonus = combine_modifiers(self._courageous_anthem_damage_modifiers(state, caster))
            damage = divine_lance_damage(check.degree, dice.draw, status_bonus)
            if damage is not None:
                events.extend(self._apply_spell_damage(
                    state, dice, caster, target, damage, check=check, source="divine_lance",
                    damage_type="spirit", attacker_critical=check.degree is DegreeOfSuccess.CRITICAL_SUCCESS,
                    continuation=continuation,
                ))
                return events
        continuation.stage = "done"
        events.extend(self._complete_action(state, caster, [], dice=dice))
        return events

    def _roll_void_warp_save(self, state, dice, caster, target, continuation):
        return self._roll_spell_save(
            state, dice, caster, target, continuation, "void_warp", "fortitude",
        )

    def _resolve_void_warp_result(self, state, dice, caster, target, check, continuation):
        result = void_warp_effect(
            check.degree,
            dice.draw,
            status_damage_bonus=combine_modifiers(
                self._courageous_anthem_damage_modifiers(state, caster)
            ),
        )
        if target.oracle_life_mode == "death":
            result = replace(result, damage=replace(result.damage, components=(replace(result.damage.components[0], amount=0),), total=0))
        damage = replace(result.damage, adjustment=f"basic_save:{check.degree.name.lower()}")
        events = [Event("spell_save", caster.actor_id, target.actor_id, _spell_save_text(target, check), check=check)]
        events.extend(self._apply_spell_damage(
            state, dice, caster, target, damage, check=check, source="void_warp",
            damage_type="void", target_critical_failure=check.degree is DegreeOfSuccess.CRITICAL_FAILURE,
            continuation=continuation, enfeebled_on_failure=result.enfeebled,
        ))
        return events

    def _roll_daze_save(self, state, dice, caster, target, continuation):
        """Resolve Daze's single-target basic Will save."""
        if continuation.spell_actions != 2:
            raise _Rejected("Daze requires its two-action cantrip form.")
        return self._roll_spell_save(
            state, dice, caster, target, continuation, "daze", "will",
        )

    def _resolve_daze_result(self, state, dice, caster, target, check, continuation):
        """Apply Daze's basic mental damage and critical-failure stun."""
        raw = resolve_damage(DamagePacket("Daze", "mental", 6, 1, 0), dice.draw)
        damage = basic_save_damage_result(raw, check.degree)
        events = [Event(
            "spell_save", caster.actor_id, target.actor_id,
            _spell_save_text(target, check, statistic="Will"), check=check,
        )]
        if check.degree is DegreeOfSuccess.CRITICAL_FAILURE and self._apply_stunned(
            state, caster, target, 1,
        ):
            events.append(Event(
                "condition_applied", caster.actor_id, target.actor_id,
                f"{target.label} is stunned 1 until the start of its next turn.", check=check,
            ))
        return events + self._apply_spell_damage(
            state, dice, caster, target, damage, check=check, source="daze",
            damage_type="mental", nonlethal=True, continuation=continuation,
        )

    def _roll_fear_save(self, state, dice, caster, target, continuation):
        """Roll Fear's Will save, honoring Guidance before Hero Point choice."""
        return self._roll_spell_save(
            state, dice, caster, target, continuation, "fear", "will",
        )

    def _resolve_fear_result(self, state, dice, caster, target, check, continuation):
        """Apply only Fear's final save conditions, after any reroll choice."""
        events = [Event(
            "spell_save", caster.actor_id, target.actor_id,
            _spell_save_text(target, check, statistic="Will"), check=check,
        )]
        frightened = {
            DegreeOfSuccess.CRITICAL_SUCCESS: 0,
            DegreeOfSuccess.SUCCESS: 1,
            DegreeOfSuccess.FAILURE: 2,
            DegreeOfSuccess.CRITICAL_FAILURE: 3,
        }[check.degree]
        if frightened:
            current_end = state.actor_end_counts.get(target.actor_id, 0)
            state.condition_effects = [
                effect for effect in state.condition_effects
                if not (
                    effect.kind == "frightened"
                    and effect.source_actor_id == caster.actor_id
                    and effect.target_actor_id == target.actor_id
                )
            ]
            state.condition_effects.append(ActiveConditionEffect(
                effect_id=f"fear:{caster.actor_id}:{target.actor_id}:{state.next_choice_id}",
                kind="frightened",
                source_actor_id=caster.actor_id,
                target_actor_id=target.actor_id,
                value=frightened,
                expiration=EffectExpiration(
                    target.actor_id, "end", current_end + frightened
                ),
            ))
            events.append(Event(
                "condition_applied", caster.actor_id, target.actor_id,
                f"{target.label} is frightened {frightened}.", check=check,
            ))
        if check.degree is DegreeOfSuccess.CRITICAL_FAILURE:
            state.active_effects = [
                effect for effect in state.active_effects
                if not (
                    effect.kind == "fleeing"
                    and effect.source_actor_id == caster.actor_id
                    and effect.target_actor_id == target.actor_id
                )
            ]
            state.active_effects.append(ActiveSpellEffect(
                effect_id=f"fleeing:{caster.actor_id}:{target.actor_id}:{state.next_choice_id}",
                kind="fleeing",
                source_actor_id=caster.actor_id,
                target_actor_id=target.actor_id,
                value=1,
                expires_at_source_start=state.actor_start_counts.get(caster.actor_id, 0) + 1,
                expires_at_world_time=state.world_time_seconds + 6,
            ))
            events.append(Event(
                "condition_applied", caster.actor_id, target.actor_id,
                f"{target.label} is fleeing from {caster.label} for 1 round.",
                check=check,
            ))
        continuation.stage = "done"
        self._record_arcane_bond_completed(caster, continuation)
        return events + self._complete_action(state, caster, [], dice=dice)

    def _apply_enfeebled(self, state, caster, target, value, *, duration_rounds=1):
        if type(duration_rounds) is not int or duration_rounds < 1:
            raise ValueError("enfeebled duration must be a positive whole number of rounds")
        current = next((effect for effect in state.active_effects if effect.kind == "enfeebled" and effect.target_actor_id == target.actor_id), None)
        if current is not None and current.value >= value:
            return
        if current is not None:
            state.active_effects.remove(current)
        state.active_effects.append(ActiveSpellEffect(
            effect_id=f"enfeebled:{caster.actor_id}:{target.actor_id}:{state.next_choice_id}",
            kind="enfeebled", source_actor_id=caster.actor_id,
            target_actor_id=target.actor_id, value=value,
            expires_at_source_start=state.actor_start_counts.get(caster.actor_id, 0) + duration_rounds,
            expires_at_world_time=state.world_time_seconds + 6 * duration_rounds,
        ))

    def _apply_stunned(self, state, source, target, value: int) -> bool:
        """Apply an admitted stunned value through the literal saved fields.

        Stunned values use the strongest current value; both currently admitted
        sources expire at the start of the target's next turn and remove the
        target's reaction immediately.
        """
        if type(value) is not int or value < 1:
            raise ValueError("stunned requires a positive whole value")
        until_start = state.actor_start_counts.get(target.actor_id, 0) + 1
        if target.stunned >= value and target.stunned_until_start >= until_start:
            return False
        target.stunned = value
        target.stunned_source_actor_id = source.actor_id
        target.stunned_until_start = until_start
        target.reaction_available = False
        return True

    def apply_family_damage(
        self,
        state,
        attacker: CreatureState,
        target_actor_id: str,
        damage: DamageResult,
        *,
        dice: DiceSource | None = None,
        source: str,
        damage_type: str,
        check=None,
        nonlethal: bool = False,
        attacker_critical: bool = False,
        target_critical_failure: bool = False,
        continuation: ActionContinuation | None = None,
    ) -> list[Event]:
        """Apply one explicit family damage result with normal health choices."""
        target = state.creatures.get(target_actor_id)
        if target is None or target.actor_id == attacker.actor_id:
            raise _Rejected("Family damage requires a different existing target.")
        if not isinstance(damage, DamageResult) or damage.total < 0:
            raise _Rejected("Family damage must be a valid rolled damage result.")
        if not isinstance(source, str) or not source or not isinstance(damage_type, str) or not damage_type:
            raise _Rejected("Family damage needs a named source and damage type.")
        if type(nonlethal) is not bool or type(attacker_critical) is not bool or type(target_critical_failure) is not bool:
            raise _Rejected("Family damage intent flags must be booleans.")
        definition = get_definition(attacker.definition_id)
        traits = frozenset(check.traits) if check is not None else frozenset()
        resolution = DamageResolution(
            source_kind="family",
            group=DamageGroup(
                f"family:{source}:{attacker.actor_id}:{target.actor_id}:{state.next_choice_id}",
                (damage,),
                "family",
                traits,
            ),
            actor_id=attacker.actor_id,
            target_id=target.actor_id,
            source=source,
            damage_type=damage_type,
            check=check,
            nonlethal=nonlethal,
            attacker_critical=attacker_critical,
            target_critical_failure=target_critical_failure,
            continuation=continuation,
            complete_family_action_on_resume=True,
        )
        return self._resolve_damage_to_health(
            state, dice or self._dice.clone(), resolution, resumed=False
        )

    def _apply_spell_damage(self, state, dice, caster, target, damage, *, check, source, damage_type,
                            attacker_critical=False, target_critical_failure=False, nonlethal=False, continuation,
                            enfeebled_on_failure=0):
        if not isinstance(damage, DamageResult) or damage.total < 0:
            raise _Rejected("Spell damage must be a valid rolled damage result.")
        resolution = DamageResolution(
            source_kind="spell",
            group=DamageGroup(
                f"spell:{source}:{caster.actor_id}:{target.actor_id}:{state.next_choice_id}",
                (damage,),
                "spell",
                spell_traits(source),
            ),
            actor_id=caster.actor_id,
            target_id=target.actor_id,
            source=source,
            damage_type=damage_type,
            check=check,
            spell_id=source,
            nonlethal=nonlethal,
            attacker_critical=attacker_critical,
            target_critical_failure=target_critical_failure,
            continuation=continuation,
            enfeebled_on_failure=enfeebled_on_failure,
        )
        return self._resolve_damage_to_health(state, dice, resolution, resumed=False)

    def _release(self, state, actor, command: Release) -> list[Event]:
        if actor.must_leave_occupied:
            raise _Rejected("Move out of the occupied ally's space before taking another action.")
        if command.item_id not in actor.held_items:
            raise _Rejected(f"{command.item_id!r} is not held and cannot be released.")
        actor.held_items.remove(command.item_id)
        state.active_effects[:] = [
            effect for effect in state.active_effects
            if not (
                effect.kind == "weapon_surge"
                and effect.source_actor_id == actor.actor_id
                and effect.effect_id.split(":")[2:3] == [command.item_id]
            )
        ]
        raised = state.raised_shields.get(actor.actor_id)
        if raised is not None and raised.instance_id == command.item_id:
            state.raised_shields.pop(actor.actor_id, None)
        from .martial_defense import point_blank_stance_is_active

        if point_blank_stance_is_active(state, actor.actor_id):
            definition = get_definition(actor.definition_id)
            if not any(
                "ranged" in attack.traits and attack.item_id in actor.held_items
                for attack in definition.attacks
            ):
                state.martial_stances.pop(actor.actor_id, None)
        state.ground_items.setdefault(actor.position, []).append(command.item_id)
        actor.witch_turn_activity_start = state.actor_start_counts.get(actor.actor_id, 0)
        return [Event("release", actor.actor_id, None, f"{actor.label} releases {command.item_id} onto {_coord(actor.position)}.", position=actor.position)]

    def _stand(self, state, dice, actor) -> list[Event]:
        self._require_action_permitted(state, actor, "stand", frozenset({"move"}))
        if not actor.prone:
            raise _Rejected("Stand is only available while prone.")
        if self._occupant_at(state, actor.position, except_actor=actor.actor_id) is not None:
            raise _Rejected("A creature shares this space; it must be clear before standing.")
        actor.actions_remaining -= 1
        actor.prone = False
        continuation = ActionContinuation(
            kind="stand",
            actor_id=actor.actor_id,
            movement_kind="stand",
            seen_reactors=[],
        )
        events = [Event("stand_started", actor.actor_id, None, f"{actor.label} stands up before movement reactions.")]
        return events + self._advance_continuation(state, dice, continuation)

    def _advance_continuation(self, state, dice, continuation: ActionContinuation) -> list[Event]:
        """Offer eligible reactions, then perform the next saved action segment."""
        events: list[Event] = []
        actor = state.creatures[continuation.actor_id]
        if continuation.kind == "movement":
            if actor.unconscious or actor.dead:
                actor.must_leave_occupied = False
                events.append(Event("movement_stopped", actor.actor_id, None, f"{actor.label} cannot continue moving while incapacitated."))
                return self._complete_action(state, actor, events, dice=dice)
            if continuation.stage == "tumble_through_failure":
                # A failed Tumble Through leaves the actor in its starting
                # square, but the action still triggers movement reactions as
                # if the actor had departed that square.
                reactor = self._next_reactor(state, actor, continuation, "movement")
                if reactor is not None:
                    self._present_reaction(state, actor, reactor, continuation, "movement")
                    return events
                events.append(Event(
                    "tumble_through_stopped",
                    actor.actor_id,
                    continuation.target_id,
                    f"{actor.label}'s failed Tumble Through ends without movement.",
                    position=actor.position,
                ))
                return self._complete_action(state, actor, events, dice=dice)
            if continuation.stage == "tumble_through_lead_in" and continuation.next_step >= len(continuation.path):
                # The next step is the attempted entry into the enemy's
                # space. Offer the ordinary departure reaction from the last
                # clear square before resolving the Acrobatics check.
                reactor = self._next_reactor(state, actor, continuation, "movement")
                if reactor is not None:
                    self._present_reaction(state, actor, reactor, continuation, "movement")
                    return events
                command = continuation.tumble_command
                saved = continuation.tumble_saved_check
                if command is None or saved is None:
                    events.append(Event(
                        "action_stopped",
                        actor.actor_id,
                        continuation.target_id,
                        f"{actor.label}'s Tumble Through continuation is incomplete.",
                    ))
                    return self._complete_action(state, actor, events, dice=dice)
                from . import skill_actions

                # The prepared check is resolved only once the clear lead-in
                # has finished, so any departure reactions happen first.
                saved = replace(saved, parent_continuation=continuation)
                context = FamilyProcedureContext(
                    self, state, dice, actor, get_definition(actor.definition_id),
                    "martial", command=command,
                )
                result = skill_actions._continue_skill_after_target(context, command, saved)
                events.extend(self._family_result_events(result, "martial"))
                return events
            if continuation.next_step >= len(continuation.path):
                actor.must_leave_occupied = self._ends_in_living_ally_space(actor, state)
                events.append(Event(continuation.movement_kind or "move", actor.actor_id, None, f"{actor.label} finishes moving at {_coord(actor.position)}.", position=actor.position))
                if continuation.movement_kind == "no_escape":
                    if continuation.parent_continuation is None:
                        raise _Rejected("No Escape has no triggering movement to resume.")
                    return events + self._advance_continuation(
                        state, dice, continuation.parent_continuation,
                    )
                if continuation.movement_kind == "sudden_charge":
                    if continuation.stage == "first_stride":
                        continuation.path = continuation.sudden_charge_second_path
                        continuation.next_step = 0
                        continuation.stage = "second_stride"
                        # Each subordinate Stride owns its own normal
                        # departure triggers; a reactor that declined the
                        # first can still react to the second.
                        continuation.seen_reactors = []
                        events.append(Event(
                            "sudden_charge_second_stride", actor.actor_id, None,
                            f"{actor.label} begins Sudden Charge's second Stride.",
                        ))
                        return events + self._advance_continuation(state, dice, continuation)
                    if continuation.stage == "second_stride":
                        return events + self._finish_sudden_charge(state, dice, actor, continuation)
                    raise _Rejected("Sudden Charge has an invalid movement stage.")
                if continuation.movement_kind == "quick_jump_critical_failure":
                    actor.prone = True
                    events.append(Event(
                        "condition_applied", actor.actor_id, actor.actor_id,
                        f"{actor.label} falls prone after the failed Quick Jump.",
                    ))
                return self._complete_action(state, actor, events, dice=dice)
            reactor = self._next_reactor(state, actor, continuation, "movement")
            if reactor is not None:
                self._present_reaction(state, actor, reactor, continuation, "movement")
                return events
            origin = actor.position
            destination = continuation.path[continuation.next_step]
            cost, diagonal_count = step_cost(actor.position, destination, actor.diagonals_this_turn)
            if continuation.movement_kind == "tumble_through":
                occupant = self._occupant_at(state, destination, except_actor=actor.actor_id)
                if occupant is not None and occupant.team != actor.team and not occupant.defeated and not occupant.dead:
                    cost *= 2
            actor.position = destination
            continuation.movement_origin = origin
            actor.diagonals_this_turn += diagonal_count
            events.extend(self._release_sourced_holds(state, actor))
            continuation.next_step += 1
            if actor.must_leave_occupied and not self._ends_in_living_ally_space(actor, state):
                actor.must_leave_occupied = False
            events.append(Event("move_step", actor.actor_id, None, f"{actor.label} moves to {_coord(destination)} ({cost} feet).", position=destination))
            follow_events = self._continue_no_escape_pursuit(state, dice, continuation, actor)
            if follow_events:
                return events + follow_events
            no_escape = self._no_escape_reactor(state, actor, continuation)
            if no_escape is not None:
                continuation.seen_reactors.append(no_escape.actor_id)
                self._set_pending(
                    state, kind="no_escape", owner_actor_id=no_escape.actor_id,
                    prompt=f"{no_escape.label} may use No Escape to pursue {actor.label}.",
                    options=(
                        ChoiceOption("pursue", "Use No Escape"),
                        ChoiceOption("decline", "Decline"),
                    ),
                    actor_id=actor.actor_id, target_id=no_escape.actor_id,
                    continuation=continuation,
                )
                events.append(Event(
                    "no_escape_triggered", no_escape.actor_id, actor.actor_id,
                    f"{actor.label} moved away from {no_escape.label}'s reach while the latter is raging.",
                ))
                return events
            events.extend(self._advance_continuation(state, dice, continuation))
            return events

        trigger = continuation.movement_kind
        if trigger in ("manipulate", "ranged", "stand"):
            reactor = self._next_reactor(state, actor, continuation, trigger)
            if reactor is not None:
                self._present_reaction(state, actor, reactor, continuation, trigger)
                return events

        if self._grabbed_manipulate_check_required(state, actor, continuation):
            events.extend(self._start_grabbed_manipulate_check(state, dice, actor, continuation))
            return events

        if continuation.kind == "interact":
            events.append(self._apply_interact(state, actor, continuation.mode or "", continuation.item_id or ""))
            return self._complete_action(state, actor, events, dice=dice)
        if (
            continuation.kind == "family_action"
            and continuation.stage == "battle_medicine_check"
        ):
            from .investigator import resolve_battle_medicine_continuation

            try:
                events.extend(resolve_battle_medicine_continuation(
                    self, state, dice, continuation
                ))
            except ValueError as error:
                raise _Rejected(str(error)) from error
            return events
        if (
            continuation.kind == "family_action"
            and continuation.stage in {"widen_spell", "widen_spell_grabbed_checked"}
        ):
            definition = get_definition(actor.definition_id)
            if (
                "widen_spell" not in definition.abilities
                or "Widen Spell" not in definition.feats
                or has_pending_spellshape(actor)
            ):
                raise _Rejected("Widen Spell is no longer available.")
            actor.widen_spell_pending = True
            events.append(Event(
                "widen_spell_ready", actor.actor_id, None,
                f"{actor.label} shapes their next eligible area spell with Widen Spell.",
            ))
            return self._complete_action(state, actor, events, dice=dice)
        if continuation.kind == "stand":
            events.append(Event("stand", actor.actor_id, None, f"{actor.label} is no longer prone."))
            return self._complete_action(state, actor, events, dice=dice)
        if continuation.kind == "ranged_strike":
            if actor.unconscious or actor.dead:
                events.append(Event("action_stopped", actor.actor_id, continuation.target_id, f"{actor.label} cannot finish the ranged Strike while incapacitated."))
                return events
            target = state.creatures.get(continuation.target_id or "")
            attack = self._find_attack(state, actor, continuation.attack_id)
            if target is None or target.defeated or attack is None or not self._attack_equipped(state, actor, attack):
                events.append(Event("action_stopped", actor.actor_id, continuation.target_id, "The ranged Strike is no longer legal after the reaction."))
                return self._complete_action(state, actor, events, dice=dice)
            if continuation.stage != "ranged_launched":
                if attack.ammunition_id is not None:
                    if actor.ammunition.get(attack.ammunition_id, 0) < 1:
                        return self._complete_action(state, actor, events, dice=dice)
                    actor.ammunition[attack.ammunition_id] -= 1
                actor.strikes_this_turn += continuation.attack_count_cost
                continuation.stage = "ranged_launched"
            events.extend(self._roll_strike(
                state, dice, actor, target, attack, continuation,
                parent=continuation.parent_continuation,
            ))
            return events
        if continuation.kind == "justice_lay_on_hands":
            from .justice import resolve_lay_continuation

            try:
                return resolve_lay_continuation(self, state, dice, continuation)
            except ValueError as error:
                raise _Rejected(str(error)) from error
        if continuation.kind == "cast":
            events.extend(self._resolve_cast(state, dice, continuation))
            return events
        raise _Rejected(f"Unsupported interrupted action {continuation.kind!r}.")

    @staticmethod
    def _release_sourced_holds(state: EncounterState, actor: CreatureState) -> list[Event]:
        """End Grapple conditions when their source actually changes squares."""
        released = tuple(
            effect for effect in state.condition_effects
            if effect.source_actor_id == actor.actor_id
            and effect.kind in {"grabbed", "restrained"}
        )
        if not released:
            return []
        released_ids = {effect.effect_id for effect in released}
        state.condition_effects = [
            effect for effect in state.condition_effects
            if effect.effect_id not in released_ids
        ]
        return [
            Event(
                "condition_removed",
                actor.actor_id,
                effect.target_actor_id,
                f"{state.creatures[effect.target_actor_id].label} is no longer {effect.kind}; "
                f"{actor.label} moved.",
            )
            for effect in released
        ]

    @staticmethod
    def _grabbed_manipulate_check_required(
        state: EncounterState, actor: CreatureState, continuation: ActionContinuation
    ) -> bool:
        return (
            (
                continuation.kind in {"cast", "interact", "ranged_strike"}
                or (
                    continuation.kind == "family_action"
                    and continuation.stage in {"widen_spell", "widen_spell_grabbed_flat_check"}
                )
            )
            and continuation.movement_kind in {"manipulate", "ranged"}
            and continuation.stage != "grabbed_manipulate_checked"
            and any(
                effect.target_actor_id == actor.actor_id and effect.kind == "grabbed"
                for effect in state.condition_effects
            )
        )

    def _start_grabbed_manipulate_check(
        self, state, dice, actor: CreatureState, continuation: ActionContinuation
    ) -> list[Event]:
        """Resolve Grabbed after reactions and before the manipulate effect."""
        check = resolve_check(dice.draw(20), 0, 5)
        continuation.stage = (
            "widen_spell_grabbed_flat_check"
            if continuation.kind == "family_action" and continuation.stage == "widen_spell"
            else "grabbed_manipulate_flat_check"
        )
        events = [Event(
            "grabbed_manipulate_flat_check",
            actor.actor_id,
            None,
            f"{actor.label} attempts the Grabbed DC 5 flat check: d20 {check.die}; "
            f"{check.degree.label().lower()}.",
            check=check,
        )]
        if actor.health_mode is HealthMode.PC and actor.hero_points > 0:
            self._set_pending(
                state,
                kind="grabbed_manipulate_hero_reroll",
                owner_actor_id=actor.actor_id,
                prompt=(
                    f"{actor.label} may keep the Grabbed flat check or spend 1 Hero Point "
                    "to reroll it."
                ),
                options=(
                    ChoiceOption("keep", "Keep result"),
                    ChoiceOption("spend_hero_point", "Spend 1 Hero Point and reroll"),
                ),
                details=(f"Original flat check: d20 {check.die} vs DC 5.",),
                actor_id=actor.actor_id,
                check=check,
                continuation=continuation,
            )
            return events
        return events + self._finish_grabbed_manipulate_check(
            state, dice, actor, continuation, check
        )

    def _finish_grabbed_manipulate_check(
        self, state, dice, actor, continuation: ActionContinuation, check
    ) -> list[Event]:
        continuation.stage = (
            "widen_spell_grabbed_checked"
            if (
                continuation.kind == "family_action"
                and continuation.stage == "widen_spell_grabbed_flat_check"
            )
            else "grabbed_manipulate_checked"
        )
        if check.degree < DegreeOfSuccess.SUCCESS:
            return [Event(
                "action_lost",
                actor.actor_id,
                None,
                f"{actor.label}'s manipulate action is lost to Grabbed before it has any effect.",
                check=check,
            )] + self._complete_action(state, actor, [], dice=dice)
        return self._advance_continuation(state, dice, continuation)

    def _resume_continuation(self, state, dice, continuation, *, critical) -> list[Event]:
        events: list[Event] = []
        if continuation.kind == "justice_damage":
            # A Justice reaction wraps the action that caused the damage. A
            # direct Strike has no remaining action to resume; an interrupted
            # action continues through the ordinary continuation machinery.
            if continuation.parent_continuation is None:
                return events
            return self._resume_continuation(
                state, dice, continuation.parent_continuation, critical=critical
            )
        actor = state.creatures[continuation.actor_id]
        if continuation.kind == "paired_strike":
            from .paired_strikes import after_subordinate_strike

            if continuation.paired_strike is None:
                raise _Rejected("The paired Strike continuation is incomplete.")
            family_context = FamilyProcedureContext(
                self, state, dice, actor, get_definition(actor.definition_id), "martial"
            )
            stunning_events = self._resolve_stunning_blows(
                state, dice, actor, continuation,
            )
            if state.pending_choice is not None:
                return stunning_events
            result = after_subordinate_strike(family_context, continuation.paired_strike)
            return stunning_events + self._family_result_events(result, "martial")
        if continuation.kind == "sudden_charge":
            return self._complete_action(state, actor, [Event(
                "sudden_charge_complete", actor.actor_id, continuation.target_id,
                f"{actor.label} completes Sudden Charge.",
            )], dice=dice)
        if continuation.kind in {"intimidating_strike", "snagging_strike", "combat_grab", "brutish_shove", "exacting_strike"}:
            return self._complete_action(state, actor, [Event(
                f"{continuation.kind}_complete", actor.actor_id, continuation.target_id,
                f"{actor.label} completes {continuation.kind.replace('_', ' ')}.",
            )], dice=dice)
        if continuation.finisher:
            if critical:
                events.append(Event(
                    "confident_finisher_critical_failure",
                    actor.actor_id,
                    continuation.target_id,
                    f"{actor.label}'s Confident Finisher critically fails; it deals no damage.",
                ))
            return self._complete_action(state, actor, events, dice=dice)
        if continuation.kind == "cast" and continuation.stage == "done":
            return self._complete_action(state, actor, [], dice=dice)
        if continuation.must_disrupt_on_critical and critical:
            events.append(Event("disrupted", actor.actor_id, None, f"{actor.label}'s manipulate action was disrupted by a critical Reactive Strike."))
            if actor.unconscious or actor.dead:
                if actor.actor_id == self._active_actor_id(state):
                    events.extend(self._advance_after_incapacitated_turn(state, dice))
                return events
            return self._complete_action(state, actor, events, dice=dice)
        if actor.unconscious or actor.dead:
            events.append(Event("action_stopped", actor.actor_id, None, f"{actor.label} cannot continue the committed action while incapacitated."))
            if actor.actor_id == self._active_actor_id(state):
                events.extend(self._advance_after_incapacitated_turn(state, dice))
            return events
        if not state.in_progress:
            return events
        return self._advance_continuation(state, dice, continuation)

    def _stunning_blows_target(self, state, monk, paired):
        """Return the one source-eligible target for this completed Flurry."""
        if paired is None:
            return None
        if paired.activity_id != "monk:flurry_of_blows" or paired.stage != "second_resolved" or len(paired.outcomes) != 2:
            return None
        first, second = paired.outcomes
        from .monk import stunning_blows_is_eligible

        if not stunning_blows_is_eligible(
            abilities=get_definition(monk.definition_id).abilities,
            first_target_id=first.target_id, second_target_id=second.target_id,
            first_hit=first.hit, second_hit=second.hit,
            first_damage=first.damage.total if first.damage is not None else None,
            second_damage=second.damage.total if second.damage is not None else None,
        ):
            return None
        target = state.creatures.get(first.target_id)
        if target is None or target.dead or target.defeated:
            return None
        return target

    def _resolve_stunning_blows(self, state, dice, monk, continuation) -> list[Event]:
        """Offer the finite post-Flurry Fortitude rider after both Strikes settle."""
        paired = continuation.paired_strike
        target = self._stunning_blows_target(state, monk, paired)
        if target is None:
            return []
        continuation.stunning_blows_target_id = target.actor_id
        self._set_pending(
            state, kind="stunning_blows", owner_actor_id=monk.actor_id,
            prompt=f"Use Stunning Blows against {target.label}?",
            options=(ChoiceOption("attempt", "Attempt Fortitude save"), ChoiceOption("decline", "Decline")),
            actor_id=monk.actor_id, target_id=target.actor_id, continuation=continuation,
        )
        return [Event(
            "stunning_blows_choice", monk.actor_id, target.actor_id,
            f"{monk.label} may attempt Stunning Blows after the Flurry.",
        )]

    def _stunning_blows_save(self, state, dice, monk, target, continuation, *, die=None):
        modifiers = self._spell_save_modifier_breakdown(state, target, continuation, "harm", "fortitude")
        check = replace(
            resolve_check(dice.draw(20) if die is None else die, combine_modifiers(modifiers), get_definition(monk.definition_id).class_dc),
            modifier_breakdown=tuple(modifiers),
        )
        if get_definition(target.definition_id).level > get_definition(monk.definition_id).level:
            adjusted = DegreeOfSuccess(min(DegreeOfSuccess.CRITICAL_SUCCESS, check.degree + 1))
            if adjusted != check.degree:
                check = replace(check, degree=adjusted)
        return check

    def _apply_stunning_blows_result(self, state, dice, monk, target, continuation, check):
        events = [Event(
            "stunning_blows_save", monk.actor_id, target.actor_id,
            f"{target.label} attempts a Fortitude save against {monk.label}'s class DC {get_definition(monk.definition_id).class_dc}: {check.degree.label()}.",
            check=check,
        )]
        value = 3 if check.degree is DegreeOfSuccess.CRITICAL_FAILURE else 1 if check.degree is DegreeOfSuccess.FAILURE else 0
        if value and self._apply_stunned(state, monk, target, value):
            events.append(Event(
                "condition_applied", monk.actor_id, target.actor_id,
                f"{target.label} is stunned {value} until the start of its next turn.", check=check,
            ))
        continuation.stunning_blows_target_id = None
        from .paired_strikes import after_subordinate_strike
        family_context = FamilyProcedureContext(
            self, state, dice, monk, get_definition(monk.definition_id), "martial",
        )
        result = after_subordinate_strike(family_context, continuation.paired_strike)
        return events + self._family_result_events(result, "martial")

    def _next_reactor(self, state, actor, continuation, trigger):
        for reactor_id in state.initiative_order:
            if reactor_id == actor.actor_id or reactor_id in continuation.seen_reactors:
                continue
            reactor = state.creatures[reactor_id]
            if reactor.team == actor.team:
                continue
            if not reactor.reaction_available or reactor.unconscious or reactor.dead or reactor.stunned:
                continue
            if "reactive_strike" not in get_definition(reactor.definition_id).abilities:
                continue
            if not any(
                "melee" in attack.traits
                and self._attack_usable(state, reactor, attack)
                and grid_distance_feet(reactor.position, actor.position) <= attack.reach_ft
                for attack in get_definition(reactor.definition_id).attacks
            ):
                continue
            return reactor
        return None

    def _no_escape_reactor(self, state, mover, continuation, *, include_seen: bool = False):
        """Return the one admitted raging pursuit reactor for this movement step."""
        if continuation.next_step < 1 or continuation.next_step > len(continuation.path):
            return None
        started = continuation.movement_origin
        if started is None:
            return None
        from .barbarian import no_escape_is_eligible

        for reactor_id in state.initiative_order:
            if reactor_id == mover.actor_id or (not include_seen and reactor_id in continuation.seen_reactors):
                continue
            reactor = state.creatures[reactor_id]
            barbarian_state = reactor.barbarian_state
            if reactor.team == mover.team or reactor.dead or reactor.unconscious or reactor.stunned or barbarian_state is None:
                continue
            reach = max((
                attack.reach_ft for attack in get_definition(reactor.definition_id).attacks
                if "melee" in attack.traits and self._attack_usable(state, reactor, attack)
            ), default=0)
            if not reach:
                continue
            if no_escape_is_eligible(
                abilities=get_definition(reactor.definition_id).abilities,
                rage_active=barbarian_state.rage is not None,
                reaction_available=reactor.reaction_available,
                enemy_started_in_reach=grid_distance_feet(reactor.position, started) <= reach,
                enemy_is_moving_away=(
                    grid_distance_feet(reactor.position, mover.position)
                    > grid_distance_feet(reactor.position, started)
                ),
            ):
                return reactor
        return None

    def _no_escape_pursuit_path(
        self, state, reactor, mover, *, maximum_distance: int | None = None,
    ) -> tuple[tuple[Position, ...], int, int] | None:
        """Find one legal finite No Escape follow-up within its remaining Speed."""
        reach = max((
            attack.reach_ft for attack in get_definition(reactor.definition_id).attacks
            if "melee" in attack.traits and self._attack_usable(state, reactor, attack)
        ), default=0)
        speed = effective_speed_ft(
            reactor, get_definition(reactor.definition_id), self._conditions_for_actor(state, reactor),
        )
        if maximum_distance is not None:
            speed = maximum_distance
        candidates: list[Position] = []
        cells = max(1, reach // 5)
        for x in range(max(0, mover.position.x - cells), min(state.map_width, mover.position.x + cells + 1)):
            for y in range(max(0, mover.position.y - cells), min(state.map_height, mover.position.y + cells + 1)):
                point = Position(x, y)
                if grid_distance_feet(point, mover.position) > reach:
                    continue
                occupant = self._occupant_at(state, point, except_actor=reactor.actor_id)
                if occupant is None:
                    candidates.append(point)
        def path_to(destination: Position) -> tuple[tuple[Position, ...], int, int] | None:
            point, diagonals, spent, path = reactor.position, reactor.diagonals_this_turn, 0, []
            while point != destination:
                next_point = Position(
                    point.x + ((destination.x > point.x) - (destination.x < point.x)),
                    point.y + ((destination.y > point.y) - (destination.y < point.y)),
                )
                cost, diagonal = step_cost(point, next_point, diagonals)
                spent += cost
                if spent > speed:
                    return None
                occupant = self._occupant_at(state, next_point, except_actor=reactor.actor_id)
                if occupant is not None and not self._can_share_with_body(reactor, occupant):
                    return None
                path.append(next_point)
                point, diagonals = next_point, diagonals + diagonal
            return tuple(path), spent, diagonals - reactor.diagonals_this_turn
        paths = [path for point in candidates if (path := path_to(point)) is not None]
        return min(paths, key=lambda candidate: (candidate[1], len(candidate[0]))) if paths else None

    def _continue_no_escape_pursuit(self, state, dice, continuation, mover) -> list[Event]:
        """Keep the reacting Barbarian adjacent as the same move continues."""
        reactor_id = continuation.no_escape_reactor_id
        remaining = continuation.no_escape_remaining_speed_ft
        if reactor_id is None or remaining is None:
            return []
        reactor = state.creatures.get(reactor_id)
        if reactor is None or reactor.dead or reactor.unconscious or reactor.stunned or remaining <= 0:
            continuation.no_escape_reactor_id = None
            continuation.no_escape_remaining_speed_ft = None
            return []
        pursuit = self._no_escape_pursuit_path(
            state, reactor, mover, maximum_distance=remaining,
        )
        if pursuit is None:
            continuation.no_escape_reactor_id = None
            continuation.no_escape_remaining_speed_ft = None
            return [Event(
                "no_escape_stopped", reactor.actor_id, mover.actor_id,
                f"{reactor.label} cannot continue No Escape through the remaining movement.",
            )]
        path, spent, diagonals = pursuit
        if not path:
            return []
        continuation.no_escape_remaining_speed_ft -= spent
        follow = ActionContinuation(
            kind="movement", actor_id=reactor.actor_id, path=path,
            movement_kind="no_escape", seen_reactors=[], parent_continuation=continuation,
        )
        return [Event(
            "no_escape_follow", reactor.actor_id, mover.actor_id,
            f"{reactor.label} follows {mover.label} with No Escape.",
            details=tuple(_coord(point) for point in path),
        )] + self._advance_continuation(state, dice, follow)

    def _validate_no_escape_follow(self, state, continuation: ActionContinuation) -> None:
        """Fail closed for a saved movement that is mid-No Escape follow-up."""
        reactor_id = continuation.no_escape_reactor_id
        remaining = continuation.no_escape_remaining_speed_ft
        if reactor_id is None and remaining is None:
            return
        reactor = state.creatures.get(reactor_id or "")
        mover = state.creatures.get(continuation.actor_id)
        if (
            reactor is None or mover is None or continuation.kind != "movement"
            or reactor.actor_id == mover.actor_id or reactor.reaction_available
            or reactor.dead or reactor.unconscious or reactor.stunned
            or reactor.barbarian_state is None or reactor.barbarian_state.rage is None
            or "no_escape" not in get_definition(reactor.definition_id).abilities
            or remaining is None or remaining < 0
            or remaining > effective_speed_ft(
                reactor, get_definition(reactor.definition_id), self._conditions_for_actor(state, reactor),
            )
        ):
            raise ValueError("save has an invalid No Escape follow-up")

    def _present_reaction(self, state, actor, reactor, continuation, trigger):
        continuation.reaction_trigger = trigger
        continuation.must_disrupt_on_critical = (
            trigger == "manipulate" or continuation.kind == "ranged_strike"
        )
        strike_choices = self._reaction_strike_choices(state, reactor, actor)
        self._set_pending(
            state,
            kind="reaction",
            owner_actor_id=reactor.actor_id,
            prompt=f"{reactor.label} may use Reactive Strike against {actor.label} ({trigger} trigger).",
            options=tuple(
                ChoiceOption(option_id, label)
                for option_id, _attack, _damage_type, _nonlethal, label, _item_id in strike_choices
            ) + (ChoiceOption("decline", "Decline"),),
            details=(f"Reaction remains available if declined; this reactor is prompted at most once for this action.",),
            actor_id=actor.actor_id,
            target_id=actor.actor_id,
            damage_context=(
                continuation.spell_mode
                if continuation.kind == "cast" and continuation.spell_id in {"ignition", "gouging_claw"}
                else None
            ),
            continuation=continuation,
        )

    def _reaction_strike_choices(self, state, reactor, target):
        """Selectable melee Strike options for the current Reactive Strike."""
        attacks = tuple(
            attack for attack in get_definition(reactor.definition_id).attacks
            if "melee" in attack.traits and self._attack_usable(state, reactor, attack)
            and grid_distance_feet(reactor.position, target.position) <= attack.reach_ft
        )
        choices = []
        for attack_index, attack in enumerate(attacks):
            item_ids = self._held_attack_item_ids(state, reactor, attack) if attack.item_id is not None else (None,)
            for item_id in item_ids:
                default_type = attack.damage_type
                default_nonlethal = "nonlethal" in attack.traits
                for damage_type in self._attack_damage_types(attack):
                    for nonlethal in (default_nonlethal, not default_nonlethal):
                        is_default = (
                            attack_index == 0
                            and len(item_ids) == 1
                            and damage_type == default_type
                            and nonlethal == default_nonlethal
                        )
                        option_id = "accept" if is_default else (
                            f"strike:{item_id or 'unarmed'}:{attack.attack_id}:{damage_type}:"
                            f"{'nonlethal' if nonlethal else 'lethal'}"
                        )
                        intent = "nonlethal" if nonlethal else "lethal"
                        label = f"Use {attack.name} ({damage_type}, {intent})"
                        if item_id is not None:
                            label += f" [{item_id}]"
                        choices.append((option_id, attack, damage_type, nonlethal, label, item_id))
        return tuple(choices)

    def _perform_reaction(self, state, dice, reactor, target, continuation, attack, damage_type, nonlethal, item_id=None):
        reactor.reaction_available = False
        clear_pending_spellshape(reactor)
        feint_off_guard_applied = self._commit_feint_strike(state, reactor, target, attack)
        target_off_guard = self._attacker_off_guard(
            state, reactor, target, attack, feint_off_guard=feint_off_guard_applied
        )
        context = ActionContinuation(
            kind="reaction_strike",
            actor_id=reactor.actor_id,
            target_id=target.actor_id,
            attack_id=attack.attack_id,
            item_id=item_id,
            damage_type=damage_type,
            nonlethal=nonlethal,
            attack_penalty=0,
            attack_count=1,
            attack_actions_cost=0,
            attack_count_cost=0,
            feint_off_guard_applied=feint_off_guard_applied,
            attack_target_off_guard=target_off_guard,
        )
        events = [Event("reaction", reactor.actor_id, target.actor_id, f"{reactor.label} uses Reactive Strike; it ignores MAP.")]
        events.extend(self._roll_strike(state, dice, reactor, target, attack, context, parent=continuation))
        return events

    def _apply_interact(self, state, actor, mode, item_id):
        drawable_items = {
            attack.item_id
            for attack in get_definition(actor.definition_id).attacks
            if attack.item_id is not None
        }
        instance = state.item_instances.get(item_id)
        is_drawable_instance = instance is not None and (
            instance.definition_id in drawable_items
            or item_id in state.infused_alchemy_items
            or self._shield_profile(instance) is not None
            or is_drawable_equipment_definition(instance.definition_id)
        )
        if mode == "draw" and (item_id in drawable_items or is_drawable_instance) and len(actor.held_items) < 2 and (item_id in actor.worn_items or item_id in actor.stowed_items):
            if item_id in actor.stowed_items:
                actor.stowed_items.remove(item_id)
            else:
                actor.worn_items.remove(item_id)
            actor.held_items.append(item_id)
            text = f"{actor.label} draws {item_id}."
        elif mode == "remove_glue":
            effect = next(
                (current for current in state.active_effects
                 if current.effect_id == item_id
                 and current.kind == "alchemy_glue_bomb_lesser"
                 and current.target_actor_id in state.creatures
                 and not state.creatures[current.target_actor_id].dead
                 and grid_distance_feet(actor.position, state.creatures[current.target_actor_id].position) <= 5),
                None,
            )
            if effect is None:
                raise _Rejected("The selected Glue Bomb effect is no longer in reach.")
            count = effect.glue_removal_actions + 1
            if count >= 3:
                state.active_effects.remove(effect)
                base_id = effect.effect_id
                state.condition_effects[:] = [
                    current for current in state.condition_effects
                    if current.effect_id != f"{base_id}:immobilized"
                ]
                return Event(
                    "glue_removed", actor.actor_id, effect.target_actor_id,
                    f"{actor.label} completes the third careful action and removes the Glue Bomb effects.",
                    position=actor.position,
                )
            state.active_effects[state.active_effects.index(effect)] = replace(
                effect, glue_removal_actions=count,
            )
            return Event(
                "glue_removal_progress", actor.actor_id, effect.target_actor_id,
                f"{actor.label} carefully removes part of the Glue Bomb residue ({count}/3 actions).",
                position=actor.position,
            )
        elif mode == "stow" and item_id in actor.held_items:
            actor.held_items.remove(item_id)
            actor.stowed_items.append(item_id)
            raised = state.raised_shields.get(actor.actor_id)
            if raised is not None and raised.instance_id == item_id:
                state.raised_shields.pop(actor.actor_id, None)
            text = f"{actor.label} stows {item_id}."
        elif mode == "retrieve" and len(actor.held_items) < 2 and (
            ground_position := self._ground_item_position_in_reach(state, actor, item_id)
        ) is not None:
            items = state.ground_items[ground_position]
            items.remove(item_id)
            if not items:
                del state.ground_items[ground_position]
            actor.held_items.append(item_id)
            text = f"{actor.label} picks up {item_id} from {_coord(ground_position)}."
        else:
            raise _Rejected("The selected item transfer is no longer legal.")
        return Event("interact", actor.actor_id, None, text, position=actor.position)

    @staticmethod
    def _ground_item_position_in_reach(state, actor, item_id):
        for position, item_ids in (state.ground_items or {}).items():
            if item_id in item_ids and grid_distance_feet(actor.position, position) <= 5:
                return position
        return None

    @staticmethod
    def _item_position(state, item_id):
        """Locate one supported physical item on the grid or on its bearer."""
        for creature in state.creatures.values():
            if item_id in (*creature.held_items, *creature.worn_items, *creature.stowed_items):
                return creature.position
        for position, item_ids in (state.ground_items or {}).items():
            if item_id in item_ids:
                return position
        return None

    def _free_devise_target_ids(self, state: EncounterState, actor: CreatureState) -> tuple[str, ...]:
        """Return the finite free-Devise targets that can keep this turn open.

        A Person of Interest grant (and the existing lead-aware free Devise)
        is a free action usable on the investigator's turn.  At zero actions,
        retain that narrow opportunity instead of auto-ending the turn.
        """
        definition = get_definition(actor.definition_id)
        existing = actor.investigator_stratagem
        if (
            actor.unconscious
            or actor.dead
            or actor.must_leave_occupied
            or "investigator_devise_stratagem" not in definition.abilities
            or (
                existing is not None
                and existing.round_number == state.round_number
            )
            or not self._action_permitted(
                state,
                actor,
                "devise_stratagem",
                frozenset({"concentrate", "investigator"}),
            )
        ):
            return ()
        return tuple(
            target.actor_id
            for target in state.creatures.values()
            if (
                target.actor_id != actor.actor_id
                and not target.defeated
                and (
                    (
                        bool(actor.investigator_active_cases)
                        and target.actor_id in actor.investigator_awareness
                    )
                    or person_of_interest_grant_allows_free_devise(
                        actor.investigator_person_of_interest,
                        target_id=target.actor_id,
                        now_seconds=state.world_time_seconds,
                    )
                )
            )
        )

    def _complete_action(self, state, actor, events, *, dice=None):
        if (
            state.in_progress
            and actor.actions_remaining == 0
            and actor.actor_id == self._active_actor_id(state)
            and not self._free_devise_target_ids(state, actor)
        ):
            events.extend(self._end_turn(state, actor, early=False, dice=dice or self._dice.clone()))
        return events

    def _find_attack(self, state, actor, attack_id):
        attacks = get_definition(actor.definition_id).attacks
        if any(effect.kind == "alchemy_bestial_mutagen_lesser" and effect.target_actor_id == actor.actor_id for effect in state.active_effects):
            attacks = (*attacks, AttackDefinition("bestial_claws", "Bestial Claws", 3, 5, frozenset({"melee", "unarmed", "agile"}), "slashing", (4,), 0, attack_attribute="strength", striking_applies=False), AttackDefinition("bestial_jaws", "Bestial Jaws", 3, 5, frozenset({"melee", "unarmed"}), "piercing", (6,), 0, attack_attribute="strength", striking_applies=False))
        return next((attack for attack in attacks if attack.attack_id == attack_id), None)

    def _occupant_at(self, state, position, *, except_actor=None):
        return next((item for item in state.creatures.values() if item.actor_id != except_actor and item.position == position), None)

    def _apply_gale_blast_push(self, state, dice, caster, target, distance_ft):
        """Apply Gale Blast's forced, reactionless outward displacement.

        The printed immobilized rule requires an external-force check but does
        not prescribe a modifier. This local slice uses the caster's printed
        spell-attack modifier with no MAP and does not free the holding effect.
        """
        holds = [effect for effect in state.condition_effects if effect.target_actor_id == target.actor_id and effect.kind == "immobilized"]
        force_checks = []
        for hold in holds:
            if hold.dc is None:
                return [Event("forced_movement_blocked", caster.actor_id, target.actor_id, f"Gale Blast cannot test {target.label}'s holding effect without its DC.")]
            definition = get_definition(caster.definition_id)
            if definition.spell_attack is None:
                raise _Unsupported("Gale Blast's local immobilized-force convention needs a printed spell attack modifier.")
            check = resolve_check(dice.draw(20), definition.spell_attack, hold.dc)
            force_checks.append(check)
            if check.degree < DegreeOfSuccess.SUCCESS:
                return [Event("forced_movement_blocked", caster.actor_id, target.actor_id, f"Gale Blast fails the local spell-attack check against {target.label}'s immobilizing effect.", check=check)]
        dx = (target.position.x > caster.position.x) - (target.position.x < caster.position.x)
        dy = (target.position.y > caster.position.y) - (target.position.y < caster.position.y)
        if not dx and not dy:
            return []
        origin, current = target.position, target.position
        spent, diagonals = 0, target.diagonals_this_turn
        while spent < distance_ft:
            point = Position(current.x + dx, current.y + dy)
            if not in_bounds(point, state.map_width, state.map_height):
                break
            cost, diagonal_count = step_cost(current, point, diagonals)
            if spent + cost > distance_ft:
                break
            occupant = self._occupant_at(state, point, except_actor=target.actor_id)
            if occupant is not None and not self._can_share_with_body(target, occupant):
                break
            spent += cost
            diagonals += diagonal_count
            current = point
        target.position = current
        return [Event("forced_movement", caster.actor_id, target.actor_id, f"Gale Blast pushes {target.label} from {_coord(origin)} to {_coord(current)} without triggering movement reactions.", position=current, check=force_checks[-1] if force_checks else None)]

    def _can_share_with_body(self, actor, occupant) -> bool:
        if not (occupant.unconscious or occupant.dead) or not occupant.prone:
            return False
        sizes = {"tiny": 0, "small": 1, "medium": 2}
        return sizes.get(get_definition(occupant.definition_id).size, 99) <= sizes.get(get_definition(actor.definition_id).size, -1)

    def _ends_in_living_ally_space(self, actor, state):
        occupant = self._occupant_at(state, actor.position, except_actor=actor.actor_id)
        return occupant is not None and occupant.team == actor.team and not occupant.defeated and not occupant.unconscious and not occupant.dead

    def _shares_space_with_living_actor(self, actor, state):
        return self._occupant_at(state, actor.position, except_actor=actor.actor_id) is not None

    def _has_open_neighbor(self, actor, state):
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                if not dx and not dy:
                    continue
                point = Position(actor.position.x + dx, actor.position.y + dy)
                if in_bounds(point, state.map_width, state.map_height):
                    occupant = self._occupant_at(state, point, except_actor=actor.actor_id)
                    if occupant is None or (
                        occupant.team == actor.team and not occupant.defeated
                    ) or self._can_share_with_body(actor, occupant):
                        return True
        return False

    def _step_destinations(self, actor: CreatureState, state: EncounterState) -> tuple[Position, ...]:
        definition = get_definition(actor.definition_id)
        if effective_speed_ft(actor, definition, self._conditions_for_actor(state, actor)) < 10 or actor.prone:
            return ()
        candidates: list[Position] = []
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                if dx == 0 and dy == 0:
                    continue
                point = Position(actor.position.x + dx, actor.position.y + dy)
                if not in_bounds(point, state.map_width, state.map_height):
                    continue
                cost, _ = step_cost(actor.position, point, actor.diagonals_this_turn)
                if cost > 5:
                    continue
                occupant = self._occupant_at(state, point, except_actor=actor.actor_id)
                if occupant is not None:
                    if occupant.team == actor.team and not occupant.defeated and not occupant.unconscious and not occupant.dead:
                        if actor.actions_remaining < 2 or actor.must_leave_occupied:
                            continue
                    elif not self._can_share_with_body(actor, occupant):
                        continue
                candidates.append(point)
        return tuple(sorted(candidates))

    def _resolve_persistent_damage_end_turn(self, state, dice, actor) -> list[Event]:
        """Roll the actor's simultaneous persistent conditions, then recover each.

        This intentionally remains a small literal record list.  It creates one
        damage application for all types on this actor rather than reusing the
        ordinary attack/spell resolver once per condition.
        """
        # Remove authored expirations before snapshotting this turn.  Spells
        # supply the usual one-minute fact; the condition has no global clock.
        state.persistent_effects[:] = [
            effect for effect in state.persistent_effects
            if effect.expires_at_world_time is None or effect.expires_at_world_time > state.world_time_seconds
        ]
        effects = tuple(
            effect for effect in state.persistent_effects
            if effect.target_actor_id == actor.actor_id
            and (effect.expires_at_world_time is None or effect.expires_at_world_time > state.world_time_seconds)
        )
        if not effects:
            return []
        # Each persistent type is its own damage effect for IWR.  They share
        # one later health trigger, but a broad resistance or weakness applies
        # once to each condition rather than once to this combined tick.
        raw_results: list[DamageResult] = []
        mitigated_results: list[DamageResult] = []
        defenses = get_definition(actor.definition_id).damage_defenses
        for effect in effects:
            raw = roll_damage_terms((DamageTerm(
                f"persistent:{effect.effect_id}", effect.damage_type,
                effect.dice, effect.flat,
            ),), dice.draw)
            mitigation = apply_damage_defenses(
                DamageGroup(effect.effect_id, (raw,), "persistent", frozenset({"persistent"})),
                defenses, (),
            )
            if mitigation.unresolved_choices:
                raise _Unsupported("Persistent damage with a selectable resistance needs a supported defender choice.")
            raw_results.append(raw)
            mitigated_results.append(mitigation.results[0])
        damage = DamageResult(
            components=tuple(component for result in raw_results for component in result.components),
            rolled_total=sum(result.rolled_total for result in raw_results),
            multiplier=1,
            total=sum(result.total for result in raw_results),
        )
        mitigated = DamageResult(
            components=tuple(component for result in mitigated_results for component in result.components),
            rolled_total=damage.rolled_total,
            multiplier=1,
            total=sum(result.total for result in mitigated_results),
            adjustment="persistent_iwr",
        )
        temporary = absorb_temporary_hp(mitigated.total, actor.temporary_hp)
        remaining, absorbed = temporary.damage_to_hp, temporary.absorbed
        if actor.health_mode is HealthMode.PC:
            hero_owner = self._familiar_hero_owner(state, actor) or actor
            transition = self._propose_pc_damage(
                actor, remaining, damage_taken=remaining,
                hero_points=hero_owner.hero_points,
            )
            if transition.heroic_recovery_available:
                if hero_owner is actor:
                    raise _Unsupported("Persistent damage that needs Heroic Recovery remains outside the stable-unconscious boundary.")
                actor.temporary_hp -= absorbed
                self._set_pending(
                    state,
                    kind="heroic_recovery_damage",
                    owner_actor_id=hero_owner.actor_id,
                    prompt=f"{hero_owner.label} may spend Hero Points on behalf of {actor.label} after persistent damage.",
                    options=(
                        ChoiceOption("normal", "Apply normal health outcome"),
                        ChoiceOption("heroic_recovery", "Heroic Recovery (spend all Hero Points)"),
                    ),
                    actor_id=hero_owner.actor_id,
                    target_id=actor.actor_id,
                    damage_result=mitigated,
                    damage_result_is_mitigated=True,
                    temporary_hp_absorbed=absorbed,
                    remaining_hp_damage=remaining,
                    health_normal=transition,
                    health_heroic=transition.heroic_recovery_option,
                    transition_kind="familiar_persistent_damage",
                )
                return [Event(
                    "persistent_damage", None, actor.actor_id,
                    f"Persistent damage deals {mitigated.total} total to {actor.label}.",
                    damage=mitigated, temporary_hp_absorbed=absorbed,
                    remaining_hp_damage=remaining,
                )]
            actor.temporary_hp -= absorbed
            self._apply_health_transition(state, actor, transition)
        else:
            before_hp = actor.hp
            actor.temporary_hp -= absorbed
            actor.hp = max(0, actor.hp - remaining)
            if actor.hp == 0 and before_hp > 0:
                actor.dead = True
                actor.unconscious = False
                actor.prone = False
                actor.reaction_available = False
                # Persistent damage ends with the creature; there is no
                # recovery check for a condition on a dead ordinary target.
                state.persistent_effects[:] = [
                    effect for effect in state.persistent_effects
                    if effect.target_actor_id != actor.actor_id
                ]
        events = [Event(
            "persistent_damage", None, actor.actor_id,
            f"Persistent damage deals {mitigated.total} total to {actor.label}.",
            damage=mitigated, temporary_hp_absorbed=absorbed,
            remaining_hp_damage=remaining,
        )]
        # Damage is now committed exactly once.  Recovery checks follow one
        # effect at a time so their Hero Point rerolls can save/load without
        # drawing damage dice again.
        continuation = ActionContinuation(
            kind="persistent_tick", actor_id=actor.actor_id,
            target_ids=tuple(effect.effect_id for effect in effects),
        )
        return events + self._continue_persistent_recovery(state, dice, actor, continuation)

    def _continue_persistent_recovery(self, state, dice, actor, continuation) -> list[Event]:
        """Resolve the saved sequence of DC 15 persistent recovery checks."""
        try:
            index = int(continuation.stage or "0")
        except ValueError as error:
            raise _Rejected("Persistent recovery progress is invalid.") from error
        if index >= len(continuation.target_ids):
            return []
        effect_id = continuation.target_ids[index]
        effect = next((item for item in state.persistent_effects if item.effect_id == effect_id), None)
        if effect is None or effect.target_actor_id != actor.actor_id:
            continuation.stage = str(index + 1)
            return self._continue_persistent_recovery(state, dice, actor, continuation)
        check = resolve_check(dice.draw(20), 0, 15)
        event = Event(
            "persistent_recovery", None, actor.actor_id,
            f"{actor.label} rolls {check.die} against DC 15 to recover from persistent {effect.damage_type} damage.",
            check=check,
        )
        hero_owner = self._familiar_hero_owner(state, actor) or actor
        if actor.health_mode is HealthMode.PC and hero_owner.hero_points > 0:
            self._set_pending(
                state, kind="persistent_recovery", owner_actor_id=hero_owner.actor_id,
                prompt=(
                    f"{actor.label} may keep this persistent recovery check or spend 1 Hero Point to reroll."
                    if hero_owner is actor else
                    f"{hero_owner.label} may spend a Hero Point on behalf of {actor.label}'s persistent recovery check."
                ),
                options=(ChoiceOption("keep", "Keep result"), ChoiceOption("spend_hero_point", "Spend 1 Hero Point and reroll")),
                details=(f"Persistent {effect.damage_type}; d20 {check.die} vs DC 15.",),
                actor_id=actor.actor_id, target_id=actor.actor_id, effect_id=effect_id,
                check=check, continuation=continuation,
            )
            return [event]
        return [event, *self._finish_persistent_recovery_check(state, dice, actor, continuation, effect, check)]

    def _finish_persistent_recovery_check(self, state, dice, actor, continuation, effect, check) -> list[Event]:
        events: list[Event] = []
        if check.degree in {DegreeOfSuccess.SUCCESS, DegreeOfSuccess.CRITICAL_SUCCESS}:
            state.persistent_effects.remove(effect)
            events.append(Event("persistent_recovered", None, actor.actor_id, f"{actor.label} recovers from persistent {effect.damage_type} damage."))
        continuation.stage = str(int(continuation.stage or "0") + 1)
        events.extend(self._continue_persistent_recovery(state, dice, actor, continuation))
        return events

    def _end_turn(self, state, actor, *, early: bool, dice: DiceSource) -> list[Event]:
        discarded = actor.actions_remaining
        actor.actions_remaining = 0
        actor.strikes_this_turn = 0
        actor.diagonals_this_turn = 0
        if actor.arcane_bond_recast_until_start == state.actor_start_counts.get(actor.actor_id, 0):
            actor.arcane_bond_recast_until_start = 0
            actor.arcane_bond_item_id = None
        if actor.actor_id in state.desperate_prayer_points:
            if actor.focus_points > 0:
                actor.focus_points -= 1
            state.desperate_prayer_points.discard(actor.actor_id)
        venom_events = self._resolve_giant_centipede_venom_end_turn(state, dice, actor)
        if state.pending_choice is not None:
            continuation = state.pending_choice.continuation
            if continuation is None or continuation.kind != "venom_end_turn":
                raise _Unsupported("Giant Centipede Venom end-turn damage lost its saved continuation.")
            continuation.parent_continuation = ActionContinuation(
                kind="persistent_end_turn", actor_id=actor.actor_id,
                stage=f"{int(early)}:{discarded}",
            )
            return venom_events
        persistent_events = self._resolve_persistent_damage_end_turn(state, dice, actor)
        if state.pending_choice is not None:
            # Recovery pauses the end turn before condition cleanup, frightened
            # reduction, and initiative advance.  Resume never rolls damage.
            state.pending_choice.continuation.parent_continuation = ActionContinuation(
                kind="persistent_end_turn", actor_id=actor.actor_id,
                stage=f"{int(early)}:{discarded}",
            )
            return persistent_events
        return venom_events + persistent_events + self._finish_end_turn(state, dice, actor, early=early, discarded=discarded)

    def _finish_end_turn(self, state, dice, actor, *, early: bool, discarded: int) -> list[Event]:
        self._source_turn_end(state, actor)
        # A still-available reaction remains available after an actor's own
        # turn; it refreshes at that actor's next turn, not at round end.
        if early:
            text = f"{actor.label} ended the turn early and lost {discarded} remaining action(s)."
        else:
            text = f"{actor.label} spent the third action; the turn ends."
        events = [Event("turn_ended", actor.actor_id, None, text)]
        self._finish_if_team_defeated(state)
        if not state.in_progress:
            return events

        for _ in range(len(state.initiative_order)):
            next_index = (state.active_index + 1) % len(state.initiative_order)
            if next_index == 0:
                state.round_number += 1
                state.world_time_seconds = (
                    state.encounter_start_seconds + (state.round_number - 1) * 6
                )
                self._refresh_all_barbarians(state)
            state.active_index = next_index
            next_actor = state.creatures[state.initiative_order[next_index]]
            self._source_turn_start(state, next_actor)
            if next_actor.defeated:
                self._finish_if_team_defeated(state)
                if not state.in_progress:
                    return events
                continue
            next_actor.strikes_this_turn = 0
            next_actor.diagonals_this_turn = 0
            if self._begin_turn(state, dice, next_actor, events):
                return events
        # No living creature can currently take a turn (for example, a party
        # of stabilized unconscious PCs). Keep the encounter visible without
        # inventing a wake-up or time-advance rule.
        state.active_index = 0
        events.append(Event("turn_paused", None, None, "No conscious combatant can take a supported turn."))
        return events

    def _source_turn_start(self, state, actor: CreatureState) -> None:
        # Persistent effects in this deliberately small slice use a declared
        # local GM one-minute absolute expiration. Round-wrap advances the
        # clock immediately before this maintenance boundary, so purge here
        # before a save can retain an already-expired record.
        state.persistent_effects = [
            effect for effect in state.persistent_effects
            if effect.expires_at_world_time > state.world_time_seconds
        ]
        state.giant_centipede_venom_afflictions = [
            effect for effect in state.giant_centipede_venom_afflictions
            if effect.expires_at_world_time > state.world_time_seconds
            and not state.creatures[effect.target_actor_id].dead
        ]
        self._expire_person_of_interest_grants(state)
        starts = state.actor_start_counts
        assert starts is not None
        starts[actor.actor_id] = starts.get(actor.actor_id, 0) + 1
        for item_id, infused in tuple(state.infused_alchemy_items.items()):
            if (infused.creator_actor_id == actor.actor_id
                and infused.activation_deadline == "creator_next_turn_start"
                and starts[actor.actor_id] > (infused.creator_turn_occurrence or 0)):
                for holder in state.creatures.values():
                    for inventory in (holder.held_items, holder.worn_items, holder.stowed_items):
                        if item_id in inventory:
                            inventory.remove(item_id)
                state.consumed_infused_item_ids.add(item_id)
        for recipient in state.creatures.values():
            if (
                recipient.temporary_hp_source_id is not None
                and recipient.temporary_hp_source_id.startswith(f"restored_spirit:{actor.actor_id}:")
                and recipient.temporary_hp_expires_at_source_start
                and recipient.temporary_hp_expires_at_source_start <= starts[actor.actor_id]
            ):
                recipient.temporary_hp = 0
                recipient.temporary_hp_source_id = None
                recipient.temporary_hp_expires_at_seconds = None
                recipient.temporary_hp_expires_at_source_start = 0
        stratagem = getattr(actor, "investigator_stratagem", None)
        if stratagem is not None and stratagem.turn_start < starts[actor.actor_id]:
            actor.investigator_stratagem = None
        if state.investigator_weakness_bonuses:
            state.investigator_weakness_bonuses = [
                bonus for bonus in state.investigator_weakness_bonuses
                if not (
                    bonus.source_actor_id == actor.actor_id
                    and bonus.expires_at_actor_start <= starts[actor.actor_id]
                )
            ]
        raised_shield = state.raised_shields.get(actor.actor_id)
        if raised_shield is not None and raised_shield.expires_at_owner_start <= starts[actor.actor_id]:
            state.raised_shields.pop(actor.actor_id, None)
        if actor.magic_shield_expires_at_start <= starts[actor.actor_id]:
            actor.magic_shield_expires_at_start = 0
        if actor.escape_lockout_until_start <= starts[actor.actor_id]:
            actor.escape_lockout_until_start = 0
        state.condition_effects = [
            effect for effect in state.condition_effects
            if not (
                effect.expiration.anchor_actor_id == actor.actor_id
                and effect.expiration.boundary == "start"
                and effect.expiration.occurrence <= starts[actor.actor_id]
            )
        ]
        retained: list[ActiveSpellEffect] = []
        expired: list[ActiveSpellEffect] = []
        for effect in state.active_effects:
            if (
                (effect.kind.startswith("alchemy_") and effect.expires_at_world_time is not None and effect.expires_at_world_time <= state.world_time_seconds)
                or (
                    effect.source_actor_id == actor.actor_id
                    and not effect.kind.startswith("alchemy_")
                    and effect.expires_at_source_start <= starts[actor.actor_id]
                )
            ):
                expired.append(effect)
            else:
                if effect.kind.startswith("alchemy_") and effect.source_actor_id == actor.actor_id:
                    # Alchemical effects use an absolute clock for their
                    # duration, while persistence retains a source-relative
                    # anchor for strict save validation.  Rebase that anchor
                    # as the source starts another turn.
                    effect = replace(effect, expires_at_source_start=starts[actor.actor_id] + 1)
                retained.append(effect)
        state.active_effects = retained
        state.active_item_effects = [
            effect for effect in state.active_item_effects
            if not (
                effect.source_actor_id == actor.actor_id
                and effect.expires_at_source_start <= starts[actor.actor_id]
            )
        ]
        for effect in expired:
            if effect.kind == "guidance":
                deadline = state.world_time_seconds + 600
                state.guidance_immunity_deadlines[effect.target_actor_id] = max(
                    deadline,
                    state.guidance_immunity_deadlines.get(effect.target_actor_id, 0),
                )
                state.guidance_immunities[effect.target_actor_id] = state.round_number + 600
        for target_id, deadline in tuple(state.guidance_immunity_deadlines.items()):
            if deadline <= state.world_time_seconds:
                del state.guidance_immunity_deadlines[target_id]
                state.guidance_immunities.pop(target_id, None)

    @staticmethod
    def _expire_elapsed_spell_effects(state: EncounterState) -> None:
        """Expire effects during an explicit elapsed-time transition.

        Ordinary combat round wraps must not call this helper.  Printed
        source-turn durations remain live until that source's next start even
        when a later-in-initiative cast crosses its absolute clock deadline at
        the round boundary.
        """
        now = state.world_time_seconds
        retained: list[ActiveSpellEffect] = []
        for effect in state.active_effects:
            deadline = effect.expires_at_world_time
            if deadline is None:
                # Older saves predate absolute deadlines for one-turn effects.
                # Their source-start occurrence maps to the encounter clock;
                # use that concrete boundary while migrating the live record.
                deadline = state.encounter_start_seconds + (
                    effect.expires_at_source_start - 1
                ) * 6
            if deadline > now:
                retained.append(replace(effect, expires_at_world_time=deadline))
                continue
            if effect.kind == "guidance":
                immunity_deadline = deadline + 600
                state.guidance_immunity_deadlines[effect.target_actor_id] = max(
                    immunity_deadline,
                    state.guidance_immunity_deadlines.get(effect.target_actor_id, 0),
                )
                # Keep the old display projection stable for callers that
                # still render the combat-round field.
                state.guidance_immunities[effect.target_actor_id] = state.round_number + 600
        state.active_effects = retained
        state.active_item_effects = [
            effect for effect in state.active_item_effects
            if effect.expires_at_world_time is None or effect.expires_at_world_time > now
        ]

    @staticmethod
    def _expire_person_of_interest_grants(state: EncounterState) -> None:
        """Clear only the elapsed free-Devise grant, never its cooldown."""
        for actor in state.creatures.values():
            grant = actor.investigator_person_of_interest
            if grant is not None and state.world_time_seconds >= grant.expires_at_seconds:
                actor.investigator_person_of_interest = None

    def _advance_elapsed_time(self, state: EncounterState, elapsed_seconds: int) -> None:
        """Advance an explicit outside-combat clock and its concrete expiries."""
        if type(elapsed_seconds) is not int or elapsed_seconds <= 0:
            raise ValueError("elapsed time must be a positive integer")
        state.world_time_seconds += elapsed_seconds
        Encounter._expire_elapsed_spell_effects(state)
        state.persistent_effects[:] = [
            effect for effect in state.persistent_effects
            if effect.expires_at_world_time is None
            or effect.expires_at_world_time > state.world_time_seconds
        ]
        Encounter._expire_person_of_interest_grants(state)

        # Turn-bound defenses have no useful meaning between fights. Their
        # printed source-turn anchors remain authoritative during combat, and
        # this path clears them only after an explicit elapsed transition.
        state.raised_shields.clear()
        state.taking_cover.clear()
        state.feint_off_guard_effects.clear()
        state.tumble_behind_exposures.clear()
        for actor in state.creatures.values():
            actor.escape_lockout_until_start = 0
            actor.magic_shield_expires_at_start = 0
            if actor.shield_recast_available_at_seconds <= state.world_time_seconds:
                actor.shield_recast_available_at_seconds = 0

        # Frightened decreases at the end of a creature's turns. Ten minutes
        # is far beyond every admitted frightened duration; model shorter
        # future elapsed calls with six-second ticks while preserving the
        # condition's source record until its value reaches zero.
        frightened_steps = elapsed_seconds // 6
        retained_conditions: list[ActiveConditionEffect] = []
        for effect in state.condition_effects:
            if effect.kind == "frightened":
                value = effect.value - frightened_steps
                if value <= 0:
                    continue
                retained_conditions.append(replace(effect, value=value))
                continue
            deadline = state.encounter_start_seconds + (
                effect.expiration.occurrence - 1
            ) * 6
            if deadline > state.world_time_seconds:
                retained_conditions.append(effect)
        state.condition_effects = retained_conditions

        state.condition_immunities = [
            immunity for immunity in state.condition_immunities
            if immunity.expires_at_seconds > state.world_time_seconds
        ]
        for actor_id, deadline in tuple(state.guidance_immunity_deadlines.items()):
            if deadline <= state.world_time_seconds:
                del state.guidance_immunity_deadlines[actor_id]
                state.guidance_immunities.pop(actor_id, None)
        for actor_id, deadline in tuple(state.sure_strike_immunity_deadlines.items()):
            if deadline <= state.world_time_seconds:
                del state.sure_strike_immunity_deadlines[actor_id]
        # Rage and temporary HP carry absolute deadlines of their own.
        self._refresh_all_barbarians(state)

    def _refresh_barbarian_state(
        self, state: EncounterState, actor: CreatureState, *, encounter_ended: bool = False
    ) -> None:
        """Expire Rage and its own temporary HP without disturbing other pools."""
        from .barbarian import expire_rage

        now = state.world_time_seconds
        barbarian_state = actor.barbarian_state
        if barbarian_state is not None:
            ending = expire_rage(
                barbarian_state,
                now_seconds=now,
                unconscious=actor.unconscious or actor.dead,
                encounter_ended=encounter_ended,
            )
            if ending is not None:
                actor.barbarian_state = ending.state
                if (
                    ending.temporary_hp_source_to_clear is not None
                    and actor.temporary_hp_source_id == ending.temporary_hp_source_to_clear
                ):
                    actor.temporary_hp = 0
                    actor.temporary_hp_source_id = None
                    actor.temporary_hp_expires_at_seconds = None
                    actor.temporary_hp_expires_at_source_start = 0
        if (
            actor.temporary_hp_expires_at_seconds is not None
            and actor.temporary_hp_expires_at_seconds <= now
        ):
            actor.temporary_hp = 0
            actor.temporary_hp_source_id = None
            actor.temporary_hp_expires_at_seconds = None
            actor.temporary_hp_expires_at_source_start = 0

    def _refresh_all_barbarians(self, state: EncounterState) -> None:
        for actor in state.creatures.values():
            self._refresh_barbarian_state(state, actor)

    @staticmethod
    def _source_turn_end(state, actor: CreatureState) -> None:
        """Advance owner-relative end boundaries and expire sourced effects."""
        ends = state.actor_end_counts
        ends[actor.actor_id] = ends.get(actor.actor_id, 0) + 1
        # A sustained effect remains through the source's next turn and ends
        # at that turn's end unless Sustain moved this owner-end boundary.
        state.active_effects = [
            effect for effect in state.active_effects
            if not (
                effect.source_actor_id == actor.actor_id
                and effect.sustain_expires_at_source_end
                and effect.sustain_expires_at_source_end <= ends[actor.actor_id]
            )
        ]
        actor.finisher_used_this_turn = False
        clear_pending_spellshape(actor)
        if (
            actor.panache
            and actor.panache_expires_at_end is not None
            and actor.panache_expires_at_end <= ends[actor.actor_id]
        ):
            actor.panache = False
            actor.panache_expires_at_end = None
        state.feint_off_guard_effects = [
            effect for effect in state.feint_off_guard_effects
            if not (
                effect.expiration.anchor_actor_id == actor.actor_id
                and effect.expiration.boundary == "end"
                and effect.expiration.occurrence <= ends[actor.actor_id]
            )
        ]
        from .movement_progression import expire_tumble_behind_exposures

        state.tumble_behind_exposures = list(expire_tumble_behind_exposures(
            tuple(state.tumble_behind_exposures),
            actor_id=actor.actor_id,
            actor_end_counts=ends,
        ))
        retained = []
        for effect in state.condition_effects:
            if (
                effect.expiration.anchor_actor_id == actor.actor_id
                and effect.expiration.boundary == "end"
                and effect.expiration.occurrence <= ends[actor.actor_id]
            ):
                continue
            if effect.target_actor_id == actor.actor_id and effect.kind == "frightened":
                if effect.value <= 1:
                    continue
                effect = replace(effect, value=effect.value - 1)
            retained.append(effect)
        state.condition_effects = retained
        # Sure Strike's unused next-attack benefit ends at the source's turn
        # boundary and does not start its ten-minute post-use immunity.
        state.active_effects = [
            effect for effect in state.active_effects
            if not (
                effect.kind == "sure_strike"
                and effect.source_actor_id == actor.actor_id
            )
        ]

    @staticmethod
    def _skill_attribute(statistic: str) -> str | None:
        fixed = {
            "acrobatics": "dexterity",
            "arcana": "intelligence",
            "athletics": "strength",
            "crafting": "intelligence",
            "deception": "charisma",
            "diplomacy": "charisma",
            "intimidation": "charisma",
            "medicine": "wisdom",
            "nature": "wisdom",
            "occultism": "intelligence",
            "perception": "wisdom",
            "performance": "charisma",
            "religion": "wisdom",
            "society": "intelligence",
            "stealth": "dexterity",
            "survival": "wisdom",
            "thievery": "dexterity",
            "fortitude": "constitution",
            "reflex": "dexterity",
            "will": "wisdom",
        }
        if statistic.endswith("_lore"):
            return "intelligence"
        return fixed.get(statistic)

    @classmethod
    def _skill_modifier(cls, definition, statistic: str) -> int:
        if not isinstance(statistic, str) or not statistic:
            raise ValueError("skill statistic must be a non-empty string")
        if statistic == "perception":
            return definition.perception
        for name, _rank, modifier in definition.skills:
            if name == statistic:
                return modifier
        attribute = cls._skill_attribute(statistic)
        if attribute is None:
            raise ValueError(f"{statistic!r} is not an admitted skill statistic")
        ability_modifiers = dict(definition.ability_modifiers)
        return ability_modifiers.get(attribute, 0)

    def _free_hands(self, state, definition, actor: CreatureState) -> int:
        occupied = 0
        for item_id in actor.held_items:
            hands = [
                attack.hands_required
                for attack in definition.attacks
                if self._held_attack_item_id(state, actor, attack) == item_id
            ]
            occupied += max(hands, default=1)
        return max(0, 2 - occupied)

    @staticmethod
    def _mutagen_modifiers(state: EncounterState, actor: CreatureState, statistic: str, *, attack_traits: frozenset[str] = frozenset()) -> tuple[Modifier, ...]:
        """Project the finite selected mutagens' literal benefits and drawbacks."""
        from .alchemy_content import FORMULAS_BY_ID, MutagenFacts

        effects = tuple(effect for effect in state.active_effects if effect.target_actor_id == actor.actor_id and effect.kind.startswith("alchemy_") and effect.kind.endswith("_mutagen_lesser"))
        modifiers: list[Modifier] = []
        for effect in effects:
            formula = FORMULAS_BY_ID.get(effect.kind.removeprefix("alchemy_"))
            if formula is None or not isinstance(formula.facts, MutagenFacts):
                continue
            name = formula.name.removesuffix(" (lesser)")
            if effect.kind == "alchemy_bestial_mutagen_lesser":
                if statistic == "athletics" or (statistic == "attack" and "unarmed" in attack_traits):
                    modifiers.append(Modifier(1, "item", name))
                if statistic in {"reflex", "acrobatics", "stealth"}:
                    modifiers.append(Modifier(-2, "untyped", f"{name} drawback"))
            elif effect.kind == "alchemy_cognitive_mutagen_lesser":
                if statistic in {"arcana", "crafting", "lore", "occultism", "society", "recall_knowledge"} or statistic.endswith("_lore"):
                    modifiers.append(Modifier(1, "item", name))
                if statistic in {"athletics", "acrobatics"} or (statistic == "attack" and "unarmed" not in attack_traits):
                    modifiers.append(Modifier(-2, "untyped", f"{name} drawback"))
            elif effect.kind == "alchemy_juggernaut_mutagen_lesser":
                for bonus in formula.facts.save_bonuses:
                    if bonus.statistic == statistic:
                        modifiers.append(Modifier(bonus.bonus, "item", name))
                if statistic in {"will", "perception", "initiative"}:
                    modifiers.append(Modifier(-2, "untyped", f"{name} drawback"))
        return tuple(modifiers)

    def _skill_dc(self, state: EncounterState, actor_id: str, statistic: str) -> int:
        actor = state.creatures.get(actor_id)
        if actor is None:
            raise ValueError(f"unknown actor {actor_id!r}")
        definition = get_definition(actor.definition_id)
        saves = {name: modifier for name, _rank, modifier in definition.saves}
        if statistic == "perception":
            base = definition.perception
        elif statistic in {"fortitude", "reflex", "will"}:
            if statistic not in saves:
                raise ValueError(f"{actor.label} has no printed {statistic.title()} modifier for a current save DC")
            base = saves[statistic]
        else:
            base = self._skill_modifier(definition, statistic)
        conditions = self._conditions_for_actor(state, actor)
        modifiers = (*condition_modifiers(
            conditions, CheckContext(statistic, self._skill_attribute(statistic))
        ), *self._mutagen_modifiers(state, actor, statistic))
        if statistic in {"fortitude", "reflex", "will"}:
            modifiers = (
                *modifiers,
                *self._resilient_save_modifiers(state, actor),
                *self._blood_magic_save_modifiers(state, actor),
            )
        return 10 + base + combine_modifiers(modifiers)

    @classmethod
    def _initiative_modifier_for_state(
        cls, state: EncounterState, actor: CreatureState, definition, statistic: str,
        *, weather_perception_penalty: int = 0,
    ) -> int:
        modifier = cls._initiative_modifier_for_definition(
            definition, statistic, weather_perception_penalty=weather_perception_penalty
        )
        if any(
            effect.kind == "alchemy_juggernaut_mutagen_lesser"
            and effect.target_actor_id == actor.actor_id
            and effect.source_actor_id in state.creatures
            and effect.expires_at_source_start > state.actor_start_counts.get(effect.source_actor_id, 0)
            and (effect.expires_at_world_time is None or effect.expires_at_world_time > state.world_time_seconds)
            for effect in state.active_effects
        ):
            modifier -= 2
        return modifier

    @staticmethod
    def _initiative_modifier_for_definition(definition, statistic: str, *, weather_perception_penalty: int = 0) -> int:
        """Return the printed modifier for one authored initiative statistic."""
        if statistic == "perception":
            return definition.perception - weather_perception_penalty
        for name, _rank, modifier in definition.skills:
            if name == statistic:
                return modifier
        raise ValueError(
            f"{definition.name} has no admitted initiative statistic {statistic!r}"
        )

    @staticmethod
    def add_escape_lockout(state: EncounterState, actor_id: str) -> None:
        actor = state.creatures.get(actor_id)
        if actor is None:
            raise ValueError(f"unknown actor {actor_id!r}")
        actor.escape_lockout_until_start = state.actor_start_counts.get(actor_id, 0) + 1

    @staticmethod
    def _conditions_for_actor(state: EncounterState, actor: CreatureState) -> tuple[ConditionValue, ...]:
        conditions = [
            ConditionValue(effect.kind, effect.value, effect.effect_id)
            for effect in state.condition_effects
            if effect.target_actor_id == actor.actor_id and effect.kind != "commanded"
        ]
        conditions.extend(
            ConditionValue(effect.kind, effect.value, effect.effect_id)
            for effect in state.active_effects
            if effect.target_actor_id == actor.actor_id
            and effect.kind == "enfeebled"
        )
        conditions.extend(
            ConditionValue("speed_bonus", effect.value, effect.effect_id)
            for effect in state.active_effects
            if effect.target_actor_id == actor.actor_id
            and effect.kind == "alchemy_cheetahs_elixir_lesser"
        )
        conditions.extend(
            ConditionValue("speed_penalty", effect.value, effect.effect_id)
            for effect in state.active_effects
            if effect.target_actor_id == actor.actor_id
            and effect.kind == "alchemy_glue_bomb_lesser"
        )
        from .alchemy_content import FORMULAS_BY_ID
        for effect in state.giant_centipede_venom_afflictions:
            if effect.target_actor_id == actor.actor_id:
                stage = FORMULAS_BY_ID["giant_centipede_venom"].facts.stages[effect.stage - 1]
                conditions.extend(
                    ConditionValue(kind, value, effect.effect_id)
                    for kind, value in stage.conditions
                )
        if actor.prone:
            conditions.append(ConditionValue("prone", 1, f"condition:prone:{actor.actor_id}"))
        if any(effect.kind == "alchemy_cognitive_mutagen_lesser" and effect.target_actor_id == actor.actor_id for effect in state.active_effects):
            definition = get_definition(actor.definition_id)
            bulk_by_item = dict(definition.carried_item_bulk)
            bulk = sum(bulk_by_item.get(item_id, bulk_by_item.get((state.item_instances.get(item_id).definition_id if state.item_instances.get(item_id) is not None else item_id), 0)) for item_id in (*actor.held_items, *actor.worn_items, *actor.stowed_items))
            strength = dict(definition.ability_modifiers).get("strength", 0)
            if bulk > max(0, 5 + strength - 2):
                conditions.extend((ConditionValue("clumsy", 1, "cognitive_mutagen_bulk"), ConditionValue("speed_penalty", 10, "cognitive_mutagen_bulk")))
            if bulk > max(0, 10 + strength - 4):
                conditions.append(ConditionValue("speed_penalty", definition.land_speed_ft, "cognitive_mutagen_max_bulk"))
        return tuple(conditions)

    def _require_action_permitted(
        self, state: EncounterState, actor: CreatureState, action_id: str, traits: frozenset[str]
    ) -> None:
        blocking = self._action_blocking_reasons(state, actor, action_id, traits)
        if blocking:
            raise _Rejected("; ".join(blocking))

    def _action_permitted(
        self, state: EncounterState, actor: CreatureState, action_id: str, traits: frozenset[str]
    ) -> bool:
        return not self._action_blocking_reasons(state, actor, action_id, traits)

    def _action_blocking_reasons(
        self, state: EncounterState, actor: CreatureState, action_id: str, traits: frozenset[str]
    ) -> tuple[str, ...]:
        if actor.stunned:
            return ("stunned",)
        if actor.finisher_used_this_turn and "attack" in traits:
            return ("finisher_attack_lockout",)
        if actor.barbarian_state is not None:
            from .barbarian import action_allowed_while_raging, action_traits_with_instinct_features

            definition = get_definition(actor.definition_id)
            intimidation_trained = any(
                skill == "intimidation" and rank is not None
                for skill, rank, _modifier in definition.skills
            )
            traits = action_traits_with_instinct_features(
                actor.barbarian_state,
                action_id,
                traits,
                intimidation_trained=intimidation_trained,
            )
            if not action_allowed_while_raging(actor.barbarian_state, action_id, traits):
                return ("rage_concentrate_prohibited",)
        # Cause- and target-sensitive checks are admitted only by the action
        # procedure that can establish those facts. A dazzled creature does
        # not make every action a single-target action.
        conditions = tuple(
            condition for condition in self._conditions_for_actor(state, actor)
            if condition.kind not in {"dazzled", "fascinated"}
        )
        reasons = condition_restrictions(
            conditions, ActionContext(action_id, traits)
        )
        required_checks = {
            "grabbed_manipulate_flat_check_dc5_required",
            "stupefied_cast_flat_check_dc5_plus_value_required",
        }
        blocking = tuple(reason for reason in reasons if reason not in required_checks)
        return blocking

    def _strike_condition_modifiers(self, state: EncounterState, actor: CreatureState, attack) -> tuple[Modifier, ...]:
        """Add check penalties not already represented by the ordinary Strike terms."""
        modifiers = condition_modifiers(
            self._conditions_for_actor(state, actor),
            CheckContext("attack", attack.attack_attribute, attack.traits),
        )
        # Existing Strike construction already expresses these two effects in
        # the printed-attack and prone terms; retain their source detail there.
        modifiers = tuple(
            modifier for modifier in modifiers
            if not modifier.source.startswith(("condition:enfeebled:", "condition:prone:"))
        )
        anthem = tuple(
            Modifier(effect.value, "status", "Courageous Anthem")
            for effect in state.active_effects
            if effect.kind == "courageous_anthem" and effect.target_actor_id == actor.actor_id
        )
        return (*modifiers, *anthem)

    def _roll_skill_check(
        self,
        state: EncounterState,
        dice: DiceSource,
        actor: CreatureState,
        statistic: str,
        dc: int,
        *,
        traits: frozenset[str] = frozenset(),
        extra_modifiers: tuple[Modifier, ...] = (),
        pre_roll_choices: tuple[str, ...] = (),
        parent_continuation: ActionContinuation | None = None,
    ):
        saved = self._prepare_skill_check(
            state, actor, statistic, dc, traits=traits,
            extra_modifiers=extra_modifiers, pre_roll_choices=pre_roll_choices,
            parent_continuation=parent_continuation,
        )
        return self._resolve_saved_check(state, actor, dice, saved)

    def _prepare_skill_check(
        self,
        state: EncounterState,
        actor: CreatureState,
        statistic: str,
        dc: int,
        *,
        traits: frozenset[str] = frozenset(),
        extra_modifiers: tuple[Modifier, ...] = (),
        pre_roll_choices: tuple[str, ...] = (),
        parent_continuation: ActionContinuation | None = None,
    ):
        if type(dc) is not int or dc < 0:
            raise ValueError("skill DC must be a non-negative integer")
        if not isinstance(traits, frozenset) or any(not isinstance(item, str) or not item for item in traits):
            raise TypeError("skill traits must be a frozenset of non-empty strings")
        if not isinstance(extra_modifiers, tuple) or any(not isinstance(item, Modifier) for item in extra_modifiers):
            raise TypeError("extra_modifiers must be a tuple of Modifier records")
        if not isinstance(pre_roll_choices, tuple) or any(not isinstance(item, str) or not item for item in pre_roll_choices):
            raise TypeError("pre_roll_choices must be a tuple of non-empty strings")
        definition = get_definition(actor.definition_id)
        if not any(name == statistic for name, _rank, _modifier in definition.skills) and self._skill_attribute(statistic) is None:
            raise ValueError(f"{statistic!r} is not an admitted check statistic")
        attribute = self._skill_attribute(statistic)
        base = self._skill_modifier(definition, statistic)
        context = CheckContext(statistic, attribute, traits)
        modifiers = (
            Modifier(base, "untyped", f"printed {statistic} modifier"),
            *extra_modifiers,
            *( (Modifier(1, "item", "Cognitive Mutagen"),) if {"secret", "skill"} <= traits and any(effect.kind == "alchemy_cognitive_mutagen_lesser" and effect.target_actor_id == actor.actor_id for effect in state.active_effects) else () ),
            *self._mutagen_modifiers(state, actor, statistic),
            *condition_modifiers(self._conditions_for_actor(state, actor), context),
        )
        penalty = multiple_attack_penalty(actor.strikes_this_turn, traits) if "attack" in traits else 0
        if penalty:
            modifiers = (*modifiers, Modifier(penalty, "untyped", "multiple attack penalty"))
        from .model import SavedCheckContext
        return SavedCheckContext(
            check_owner_actor_id=actor.actor_id,
            context=context,
            dc=dc,
            modifiers=tuple(modifiers),
            pre_roll_choices=pre_roll_choices,
            parent_continuation=parent_continuation,
        )

    def _prepare_unarmed_attack_check(
        self,
        state: EncounterState,
        actor: CreatureState,
        dc: int,
        attack_id: str | None = None,
        *,
        parent_continuation: ActionContinuation | None = None,
    ):
        if type(dc) is not int or dc < 0:
            raise ValueError("unarmed attack check DC must be a non-negative integer")
        if attack_id is not None and (not isinstance(attack_id, str) or not attack_id):
            raise ValueError("unarmed attack check attack_id must be non-empty text")
        definition = get_definition(actor.definition_id)
        profiles = tuple(
            attack for attack in definition.attacks
            if "unarmed" in attack.traits
            and (attack_id is None or attack.attack_id == attack_id)
            and self._attack_usable(state, actor, attack)
        )
        if len(profiles) != 1:
            if not profiles:
                raise ValueError("Escape needs a usable unarmed attack profile")
            raise ValueError("Escape needs the selected unarmed attack profile")
        attack = profiles[0]
        penalty = multiple_attack_penalty(actor.strikes_this_turn, attack.traits)
        modifiers = _strike_modifier_breakdown_full(
            attack,
            penalty,
            nonlethal="nonlethal" in attack.traits,
            prone=actor.prone and not actor.unconscious,
            enfeebled=self._enfeebled_value(state, actor.actor_id)
            if attack.attack_attribute == "strength" else 0,
        )
        item_modifier = self._attack_item_potency_modifier(state, actor, attack)
        if item_modifier is not None:
            modifiers = (*modifiers, item_modifier)
        modifiers = (*modifiers, *self._strike_condition_modifiers(state, actor, attack), *self._mutagen_modifiers(state, actor, "attack", attack_traits=attack.traits))
        from .model import SavedCheckContext
        return SavedCheckContext(
            check_owner_actor_id=actor.actor_id,
            context=CheckContext("unarmed_attack", attack.attack_attribute, attack.traits),
            dc=dc,
            modifiers=modifiers,
            parent_continuation=parent_continuation,
            attack_id=attack.attack_id,
        )

    def _resolve_saved_check(self, state: EncounterState, actor: CreatureState, dice: DiceSource, saved):
        if saved.result is not None:
            raise ValueError("saved check has already been rolled")
        if saved.check_owner_actor_id != actor.actor_id:
            raise ValueError("saved check belongs to a different actor")
        penalty = sum(item.amount for item in saved.modifiers if item.source == "multiple attack penalty")
        sure_strike_used = saved.sure_strike_used
        if (
            not sure_strike_used
            and saved.context.statistic == "unarmed_attack"
            and "attack" in saved.context.traits
        ):
            sure_strike_used = self._consume_sure_strike_for_attack(
                state,
                actor,
                ActionContinuation(
                    kind="family_action",
                    actor_id=actor.actor_id,
                    sure_strike_checked=False,
                ),
            )
        modifiers = (
            self._sure_strike_attack_modifiers(saved.modifiers)
            if sure_strike_used else saved.modifiers
        )
        total_modifier = combine_modifiers(modifiers)
        if "attack" in saved.context.traits:
            # Maneuvers commit MAP/attack count before their concealment gate;
            # ordinary skill checks continue to increment at resolution.
            attack_count = (
                actor.strikes_this_turn
                if saved.attack_count_committed
                else actor.strikes_this_turn + 1
            )
        else:
            attack_count = None
        rolled_dice = (
            (dice.draw(20), dice.draw(20))
            if sure_strike_used else (dice.draw(20),)
        )
        check = resolve_check(
            max(rolled_dice), total_modifier, saved.dc,
            attack_id=saved.attack_id,
            attack_count=attack_count,
            map_penalty=penalty, traits=saved.context.traits,
        )
        check = replace(check, modifier_breakdown=tuple(modifiers), dice=rolled_dice)
        if "attack" in saved.context.traits and not saved.attack_count_committed:
            actor.strikes_this_turn += 1
        return replace(saved, result=check, modifiers=tuple(modifiers), sure_strike_used=sure_strike_used)

    def _reroll_saved_check(self, state, dice, actor, saved, *, spend_hero_point: bool):
        if not isinstance(spend_hero_point, bool) or not spend_hero_point:
            raise ValueError("a skill-check reroll must explicitly spend a Hero Point")
        if saved.check_owner_actor_id != actor.actor_id or saved.result is None or saved.reroll_used:
            raise ValueError("saved skill check is not eligible for a Hero Point reroll")
        if saved.fortune_used:
            raise ValueError("A check already affected by fortune cannot be rerolled with a Hero Point")
        if saved.sure_strike_used or len(saved.result.dice) > 1:
            raise ValueError("Sure Strike attack checks cannot be rerolled with a Hero Point")
        if actor.health_mode is not HealthMode.PC or actor.hero_points < 1:
            raise _Rejected("This actor cannot spend a Hero Point to reroll the check.")
        actor.hero_points -= 1
        check = self._hero_reroll_check(dice, saved.result)
        return replace(saved, result=check, reroll_used=True)

    @staticmethod
    def _sure_strike_attack_modifiers(modifiers):
        """Remove only negative circumstance attack penalties for Sure Strike."""
        return tuple(
            modifier for modifier in modifiers
            if not (
                modifier.modifier_type == "circumstance"
                and modifier.amount < 0
            )
        )

    @staticmethod
    def _consume_sure_strike_for_attack(
        state: EncounterState,
        actor: CreatureState,
        continuation: ActionContinuation,
    ) -> bool:
        """Consume the caster's pending Sure Strike at the actual attack roll."""
        if continuation.sure_strike_checked:
            return continuation.sure_strike_used
        continuation.sure_strike_checked = True
        effect = next(
            (
                item for item in state.active_effects
                if item.kind == "sure_strike"
                and item.source_actor_id == actor.actor_id
                and item.target_actor_id == actor.actor_id
                and item.expires_at_world_time is not None
                and item.expires_at_world_time > state.world_time_seconds
            ),
            None,
        )
        if effect is None:
            return False
        state.active_effects.remove(effect)
        state.sure_strike_immunity_deadlines[actor.actor_id] = state.world_time_seconds + 600
        continuation.sure_strike_used = True
        return True

    @staticmethod
    def _consume_investigator_weakness_bonus(
        state: EncounterState,
        actor: CreatureState,
        target: CreatureState,
        *,
        stratagem_used: bool,
    ) -> Modifier | None:
        """Consume one Known Weakness grant at the actual attack roll.

        The Investigator's own grant is gated on consuming the selected
        attack stratagem; an informed ally may consume its grant on any next
        attack against the authored subject. Wrong-target attacks leave the
        grant available, while a miss still consumes it once an attack roll is
        made.
        """
        candidates = [
            bonus for bonus in state.investigator_weakness_bonuses
            if bonus.recipient_actor_id == actor.actor_id
            and bonus.target_actor_id == target.actor_id
            and bonus.expires_at_actor_start > state.actor_start_counts.get(bonus.source_actor_id, 0)
            and (bonus.recipient_actor_id != bonus.source_actor_id or stratagem_used)
        ]
        if not candidates:
            return None
        state.investigator_weakness_bonuses.remove(candidates[0])
        return Modifier(1, "circumstance", "Known Weaknesses")

    def _consume_guidance(self, state, actor_id: str, effect_id: str) -> Modifier | None:
        effect = next((item for item in state.active_effects if item.effect_id == effect_id), None)
        if effect is None or effect.kind != "guidance" or effect.target_actor_id != actor_id:
            return None
        if state.guidance_immunity_deadlines.get(actor_id, 0) > state.world_time_seconds:
            return None
        state.active_effects.remove(effect)
        state.guidance_immunity_deadlines[actor_id] = state.world_time_seconds + 600
        state.guidance_immunities[actor_id] = state.round_number + 600
        return Modifier(1, "status", "Guidance")

    @staticmethod
    def _commit_family_action(context: FamilyProcedureContext, *, actions: int, attacks: int = 0) -> None:
        if type(actions) is not int or actions < 0 or type(attacks) is not int or attacks < 0:
            raise ValueError("family action and attack costs must be non-negative integers")
        if context.actor.actions_remaining < actions:
            raise _Rejected(f"This activity requires {actions} action(s).")
        context.actor.actions_remaining -= actions
        context.actor.strikes_this_turn += attacks
        context.state.taking_cover.discard(context.actor.actor_id)

    def _advance_witch_familiar_lifecycle(self, state, dice, owner: CreatureState, events: list[Event]) -> bool:
        """Give the selected familiar passive owner-turn health boundaries.

        The fox remains initiative-exempt: this never grants actions or a
        reaction.  The approved local timing merely supplies its start/end
        recovery and ongoing-effect boundaries at the Witch's turn.
        """
        familiar = next(
            (candidate for candidate in state.creatures.values()
             if self._familiar_owned_by(owner, candidate)),
            None,
        )
        if familiar is None:
            return False
        owner_start = state.actor_start_counts.get(owner.actor_id, 0)
        if state.actor_start_counts.get(familiar.actor_id, 0) >= owner_start:
            return False

        self._source_turn_start(state, familiar)
        if familiar.dead:
            return False
        if familiar.dying > 0:
            if owner.hero_points > 0:
                self._set_pending(
                    state,
                    kind="recovery_start_heroic",
                    owner_actor_id=owner.actor_id,
                    prompt=(
                        f"{familiar.label} is dying at {owner.label}'s turn start; "
                        "choose recovery check or Heroic Recovery."
                    ),
                    options=(
                        ChoiceOption("recovery_check", "Attempt recovery check"),
                        ChoiceOption("heroic_recovery", "Heroic Recovery (spend all Hero Points)"),
                    ),
                    details=(f"Dying {familiar.dying}; Hero Points {owner.hero_points}.",),
                    actor_id=familiar.actor_id,
                    target_id=familiar.actor_id,
                )
                return True
            die = dice.draw(20)
            check = resolve_check(die, 0, 10 + familiar.dying)
            transition = recovery_check(self._health_state(familiar), check.degree.name.lower())
            self._finish_familiar_recovery(state, dice, owner, familiar, transition, events)
            return False

        self._finish_witch_familiar_lifecycle(state, dice, familiar, events)
        return state.pending_choice is not None

    def _finish_familiar_recovery(
        self, state, dice, owner: CreatureState, familiar: CreatureState,
        transition: HealthTransition, events: list[Event],
    ) -> None:
        self._apply_health_transition(state, familiar, transition)
        events.append(Event(
            "familiar_recovery", owner.actor_id, familiar.actor_id,
            (
                f"{familiar.label} dies from the recovery check."
                if familiar.dead
                else f"{familiar.label}'s recovery check resolves; dying {familiar.dying}, wounded {familiar.wounded}."
            ),
        ))
        self._finish_if_team_defeated(state)
        self._finish_witch_familiar_lifecycle(state, dice, familiar, events)

    def _finish_witch_familiar_lifecycle(self, state, dice, familiar: CreatureState, events: list[Event]) -> None:
        """Resolve the approved passive familiar end boundary without a turn."""
        if not familiar.dead:
            events.extend(self._resolve_persistent_damage_end_turn(state, dice, familiar))
        if state.pending_choice is None:
            self._source_turn_end(state, familiar)
            self._finish_if_team_defeated(state)

    def _familiar_recovery_owner(self, state, pending: PendingChoice) -> CreatureState | None:
        """Return the Witch funding this saved familiar recovery, if any."""
        owner = state.creatures.get(pending.owner_actor_id or "")
        familiar = state.creatures.get(pending.actor_id or "")
        if (
            owner is None or familiar is None
            or pending.target_id != familiar.actor_id
            or self._familiar_hero_owner(state, familiar) is not owner
        ):
            return None
        return owner

    def _familiar_hero_owner(self, state, familiar: CreatureState) -> CreatureState | None:
        """Find the Witch who may spend Hero Points for this fixed familiar."""
        return next(
            (candidate for candidate in state.creatures.values()
             if self._familiar_owned_by(candidate, familiar)),
            None,
        )

    def _replace_dead_witch_familiars(self, state, owner: CreatureState) -> list[Event]:
        """Replace this fixed Witch's dead familiar during daily preparation."""
        if "witch_familiar" not in get_definition(owner.definition_id).abilities:
            return []
        events: list[Event] = []
        for familiar in tuple(state.creatures.values()):
            if not self._familiar_owned_by(owner, familiar) or not familiar.dead:
                continue
            definition = get_definition(familiar.definition_id)
            state.creatures[familiar.actor_id] = replace(
                familiar,
                position=owner.position,
                hp=definition.hp,
                dying=0,
                wounded=0,
                unconscious=False,
                dead=False,
                prone=False,
                actions_remaining=0,
                strikes_this_turn=0,
                diagonals_this_turn=0,
                reaction_available=False,
                temporary_hp=0,
                temporary_hp_source_id=None,
                temporary_hp_expires_at_seconds=None,
                temporary_hp_expires_at_source_start=0,
                minion_commanded_start=0,
                must_leave_occupied=False,
            )
            state.active_effects[:] = [
                effect for effect in state.active_effects
                if effect.source_actor_id != familiar.actor_id
                and effect.target_actor_id != familiar.actor_id
            ]
            state.persistent_effects[:] = [
                effect for effect in state.persistent_effects
                if effect.source_actor_id != familiar.actor_id
                and effect.target_actor_id != familiar.actor_id
            ]
            state.condition_effects[:] = [
                effect for effect in state.condition_effects
                if effect.source_actor_id != familiar.actor_id
                and effect.target_actor_id != familiar.actor_id
            ]
            events.append(Event(
                "familiar_replaced", owner.actor_id, familiar.actor_id,
                f"{owner.label} replaces the dead familiar during daily preparation; the new familiar knows the same spells.",
            ))
        return events

    def _begin_turn(self, state, dice, actor: CreatureState, events: list[Event]) -> bool:
        """Resolve start-turn recovery before granting actions/reaction.

        Return true when a choice is pending or the actor successfully begins
        a turn. An incapacitated actor is skipped by the caller.
        """
        if actor.health_mode is HealthMode.PC and actor.dying > 0:
            if actor.hero_points > 0:
                self._set_pending(
                    state,
                    kind="recovery_start_heroic",
                    owner_actor_id=actor.actor_id,
                    prompt=f"{actor.label} is dying at the start of their turn; choose recovery check or Heroic Recovery.",
                    options=(ChoiceOption("recovery_check", "Attempt recovery check"), ChoiceOption("heroic_recovery", "Heroic Recovery (spend all Hero Points)")),
                    details=(f"Dying {actor.dying}; Hero Points {actor.hero_points}.",),
                    actor_id=actor.actor_id,
                )
                return True
            return self._roll_recovery(state, dice, actor, events)
        if actor.unconscious or actor.dead:
            return False
        if self._advance_witch_familiar_lifecycle(state, dice, actor, events):
            return True
        if (
            "desperate_prayer" in get_definition(actor.definition_id).abilities
            and actor.focus_points == 0
            and actor.actor_id not in state.desperate_prayer_used
        ):
            self._set_pending(
                state,
                kind="desperate_prayer",
                owner_actor_id=actor.actor_id,
                prompt=(
                    f"{actor.label} begins a turn with 0 Focus Points; use Desperate Prayer?"
                ),
                options=(
                    ChoiceOption("accept", "Use Desperate Prayer (+1 devotion Focus Point)"),
                    ChoiceOption("decline", "Decline"),
                ),
                details=(
                    "Once per day; the temporary point is devotion-only and expires at turn end.",
                ),
                actor_id=actor.actor_id,
            )
            return True
        actor.actions_remaining = 3
        if actor.stunned and actor.stunned_until_start == state.actor_start_counts.get(actor.actor_id, 0):
            lost = min(actor.actions_remaining, actor.stunned)
            actor.actions_remaining -= lost
            events.append(Event(
                "stunned_actions_lost", actor.stunned_source_actor_id, actor.actor_id,
                f"{actor.label} loses {lost} action(s) to stunned {actor.stunned}.",
            ))
            actor.stunned = 0
            actor.stunned_until_start = 0
            actor.stunned_source_actor_id = None
        abilities = set(get_definition(actor.definition_id).abilities)
        actor.reaction_available = bool({"reactive_strike", "shield_block", "shield_cantrip", "counter_performance", "no_escape", "reactive_shield"} & abilities) or bool({"Nimble Dodge", "Reactive Shield", "You're Next"} & set(get_definition(actor.definition_id).feats)) or "investigator_on_the_case" in abilities
        commanded = next((effect for effect in state.condition_effects if effect.kind == "commanded" and effect.target_actor_id == actor.actor_id), None)
        if commanded is not None:
            actor.actions_remaining = max(0, actor.actions_remaining - commanded.value)
            normal_reaction_available = actor.reaction_available
            actor.reaction_available = False
            state.condition_effects.remove(commanded)
            source = state.creatures.get(commanded.source_actor_id)
            mode = commanded.command_mode
            if mode == "release" and actor.held_items:
                item_id = actor.held_items.pop()
                state.ground_items.setdefault(actor.position, []).append(item_id)
                events.append(Event("command_release", commanded.source_actor_id, actor.actor_id, f"{actor.label} releases {item_id} under Command.", position=actor.position))
            elif mode == "prone":
                actor.prone = True
                state.taking_cover.discard(actor.actor_id)
                events.append(Event("command_prone", commanded.source_actor_id, actor.actor_id, f"{actor.label} drops prone under Command."))
            elif mode == "stand":
                events.append(Event("command_stand_in_place", commanded.source_actor_id, actor.actor_id, f"{actor.label} stands in place under Command."))
            elif mode == "flee" and source is not None:
                # The admitted clear-grid Flee path keeps heading directly away
                # from the source, up to Speed for each compelled action.
                dx = (actor.position.x > source.position.x) - (actor.position.x < source.position.x)
                dy = (actor.position.y > source.position.y) - (actor.position.y < source.position.y)
                for _ in range(commanded.value):
                    moved = False
                    for _step in range(effective_speed_ft(actor, get_definition(actor.definition_id), self._conditions_for_actor(state, actor)) // 5):
                        destination = Position(actor.position.x + dx, actor.position.y + dy)
                        if not (dx or dy) or not in_bounds(destination, state.map_width, state.map_height):
                            break
                        if self._occupant_at(state, destination, except_actor=actor.actor_id) is not None:
                            route = choose_flee_route(actor.position, source.position, state.map_width, state.map_height, effective_speed_ft(actor, get_definition(actor.definition_id), self._conditions_for_actor(state, actor)), occupied_positions=tuple(current.position for current in state.creatures.values() if current.actor_id != actor.actor_id))
                            if route.path:
                                actor.position = route.destination
                                moved = True
                            break
                        actor.position = destination
                        moved = True
                    if not moved:
                        break
                    actor.must_leave_occupied = False
                    events.append(Event("command_flee", commanded.source_actor_id, actor.actor_id, f"{actor.label} flees to {_coord(actor.position)} under Command.", position=actor.position))
            elif mode == "approach" and source is not None:
                for _ in range(commanded.value):
                    dx = (source.position.x > actor.position.x) - (source.position.x < actor.position.x)
                    dy = (source.position.y > actor.position.y) - (source.position.y < actor.position.y)
                    destination = Position(actor.position.x + dx, actor.position.y + dy)
                    # A creature has approached once it reaches an adjacent
                    # square; the caster's occupied square is never entered.
                    if not (dx or dy) or grid_distance_feet(actor.position, source.position) <= 5 or not in_bounds(destination, state.map_width, state.map_height) or self._occupant_at(state, destination, except_actor=actor.actor_id) is not None:
                        break
                    actor.position = destination
                    actor.must_leave_occupied = False
                    events.append(Event("command_approach", commanded.source_actor_id, actor.actor_id, f"{actor.label} moves to {_coord(destination)} under Command.", position=destination))
            actor.reaction_available = normal_reaction_available
            events.append(Event("command_obeyed", commanded.source_actor_id, actor.actor_id, f"{actor.label} obeys Command and spends {commanded.value} action(s); reactions are available again."))
        events.append(Event("turn_started", actor.actor_id, None, f"{actor.label} regains 3 actions and 1 reaction."))
        return True

    def _roll_recovery(self, state, dice, actor, events: list[Event], *, allow_reroll: bool = True) -> bool:
        die = dice.draw(20)
        dc = 10 + actor.dying
        check = resolve_check(die, 0, dc)
        transition = recovery_check(self._health_state(actor), check.degree.name.lower(), hero_points=actor.hero_points)
        if allow_reroll and actor.hero_points > 0:
            self._set_pending(
                state,
                kind="recovery_hero_reroll",
                owner_actor_id=actor.actor_id,
                prompt=f"{actor.label} may keep this recovery check or spend 1 Hero Point to reroll it.",
                options=(ChoiceOption("keep", "Keep result"), ChoiceOption("spend_hero_point", "Spend 1 Hero Point and reroll")),
                details=(f"Original: d20 {die} vs DC {dc}.", f"Degree: {check.degree.label()}.",),
                actor_id=actor.actor_id,
                check=check,
                health_normal=transition,
                transition_kind="recovery",
            )
            return True
        return self._finish_recovery_roll(state, actor, transition, events)

    def _finish_recovery_roll(self, state, actor, transition: HealthTransition, events: list[Event]) -> bool:
        if transition.dying_increased and transition.heroic_recovery_available and transition.heroic_recovery_option:
            self._set_pending(
                state,
                kind="recovery_heroic_increase",
                owner_actor_id=actor.actor_id,
                prompt=f"{actor.label}'s recovery check would increase dying; choose normal result or Heroic Recovery.",
                options=(ChoiceOption("normal", "Apply recovery result"), ChoiceOption("heroic_recovery", "Heroic Recovery (spend all Hero Points)")),
                details=(f"Dying {actor.dying}; recovery result: {transition.state.dying}.",),
                actor_id=actor.actor_id,
                health_normal=transition,
                health_heroic=transition.heroic_recovery_option,
                transition_kind="recovery",
            )
            return True
        self._apply_health_transition(state, actor, transition)
        self._finish_if_team_defeated(state)
        recovery_text = (
            f"{actor.label} dies from the recovery check."
            if actor.dead else f"Recovery check resolves; dying {actor.dying}, wounded {actor.wounded}."
        )
        events.append(Event("recovery", actor.actor_id, actor.actor_id, recovery_text))
        return state.in_progress and not actor.unconscious and not actor.dead

    def _apply_health_transition(self, state, creature: CreatureState, transition: HealthTransition) -> None:
        before_unconscious = creature.unconscious
        creature.hp = transition.state.hp
        creature.dying = transition.state.dying
        creature.wounded = transition.state.wounded
        creature.unconscious = transition.state.unconscious
        creature.dead = transition.state.dead
        if creature.unconscious or creature.dead:
            creature.reaction_available = False
            state.justice_aura_active.discard(creature.actor_id)
            creature.must_leave_occupied = False
            state.taking_cover.discard(creature.actor_id)
            state.raised_shields.pop(creature.actor_id, None)
            state.martial_stances.pop(creature.actor_id, None)
            state.active_effects[:] = [
                effect for effect in state.active_effects
                if not (effect.kind == "life_link" and effect.source_actor_id == creature.actor_id)
            ]
        if transition.fall_prone:
            creature.prone = True
        if transition.drop_held_items and creature.held_items:
            ground_items = state.ground_items
            assert ground_items is not None
            ground_items.setdefault(creature.position, []).extend(creature.held_items)
            creature.held_items.clear()
        if before_unconscious and not creature.unconscious:
            # Becoming conscious removes unconsciousness's AC penalties, but
            # the separately acquired prone condition remains.
            pass
        if transition.initiative_before_current_turn and creature.actor_id in state.initiative_order:
            active_id = self._active_actor_id(state)
            if active_id is not None and active_id != creature.actor_id:
                order = state.initiative_order
                order.remove(creature.actor_id)
                anchor_index = order.index(active_id)
                order.insert(anchor_index, creature.actor_id)
                state.active_index = order.index(active_id)
                state.initiative_reordered.add(creature.actor_id)
        self._refresh_barbarian_state(state, creature)

    def _finish_if_team_defeated(self, state: EncounterState) -> None:
        active_teams = {creature.team for creature in state.creatures.values() if is_combat_capable(creature)}
        # A healthy combatant still burning/bleeding keeps ordinary initiative
        # alive long enough for end-turn ticks and recovery checks.
        affected_living = {
            state.creatures[effect.target_actor_id].team
            for effect in state.persistent_effects
            if effect.target_actor_id in state.creatures
            and not state.creatures[effect.target_actor_id].dead
        }
        affected_living.update(
            state.creatures[effect.target_actor_id].team
            for effect in state.giant_centipede_venom_afflictions
            if effect.target_actor_id in state.creatures
            and not state.creatures[effect.target_actor_id].dead
        )
        active_teams.update(affected_living)
        if len(active_teams) <= 1 and not affected_living:
            state.in_progress = False
            state.winner_team = next(iter(active_teams), None)
            for creature in state.creatures.values():
                creature.panache = False
                creature.panache_expires_at_end = None
                creature.actions_remaining = 0
                creature.reaction_available = False
                self._refresh_barbarian_state(state, creature, encounter_ended=True)
            state.martial_stances.clear()
            state.martial_stance_used_rounds.clear()

    def _effective_ac(
        self,
        creature: CreatureState,
        *,
        state: EncounterState | None = None,
        attacker_id: str | None = None,
        off_guard: bool = False,
        flanked: bool = False,
        lesser_cover: bool = False,
        taking_cover: bool = False,
        feint_off_guard: bool = False,
        nimble_dodge: bool = False,
    ) -> int:
        definition = get_definition(creature.definition_id)
        modifiers = [Modifier(definition.ac, "untyped", "printed AC")]
        if creature.unconscious:
            modifiers.append(Modifier(-4, "status", "unconscious condition"))
        if creature.unconscious or creature.prone or flanked or off_guard:
            modifiers.append(Modifier(-2, "circumstance", "off-guard"))
        if lesser_cover:
            modifiers.append(Modifier(1, "circumstance", "lesser creature cover"))
        if taking_cover:
            modifiers.append(Modifier(4, "circumstance", "Take Cover"))
        if nimble_dodge:
            modifiers.append(Modifier(2, "circumstance", "Nimble Dodge"))
        if state is not None:
            from .martial_defense import ac_modifiers as martial_defense_ac_modifiers

            modifiers.extend(martial_defense_ac_modifiers(state, creature, definition))
            shield = self._raised_shield_instance(state, creature)
            if shield is not None:
                profile = self._shield_profile(shield)
                modifier = shield_ac_modifier(profile, raised=True, shield_hp=shield.hp or 0)
                if modifier is not None:
                    modifiers.append(modifier)
            if creature.magic_shield_expires_at_start > state.actor_start_counts.get(creature.actor_id, 0):
                modifiers.append(Modifier(1, "circumstance", "Shield"))
            modifiers.extend(self._armor_potency_modifiers(state, creature))
            modifiers.extend(
                Modifier(effect.value, "status", "Lay on Hands")
                for effect in state.active_effects
                if effect.kind == "lay_on_hands_ac"
                and effect.target_actor_id == creature.actor_id
            )
            modifiers.extend(
                Modifier(effect.value, "status", "Protection")
                for effect in state.active_effects
                if effect.kind == "protection"
                and effect.target_actor_id == creature.actor_id
            )
            if attacker_id is not None:
                modifiers.extend(
                    Modifier(effect.value, "status", "Forbidding Ward")
                    for effect in state.active_effects
                    if effect.kind == "forbidding_ward"
                    and effect.target_actor_id == creature.actor_id
                    and effect.selected_enemy_actor_id == attacker_id
                )
        if state is not None:
            modifiers.extend(condition_modifiers(
                self._conditions_for_actor(state, creature),
                CheckContext("armor_class", "dexterity"),
            ))
            if feint_off_guard:
                modifiers.extend(condition_modifiers(
                    (ConditionValue("off_guard", 1, "feint"),),
                    CheckContext("armor_class", "dexterity"),
                ))
        return combine_modifiers(modifiers)

    @staticmethod
    def _shield_profile(instance: ItemInstance):
        if instance is None:
            return None
        if instance.definition_id == STEEL_SHIELD.definition_id:
            return STEEL_SHIELD
        return None

    @staticmethod
    def _invested_worn_armors(state: EncounterState, creature: CreatureState):
        for item_id in creature.worn_items:
            instance = state.item_instances.get(item_id)
            if instance is None or not instance.invested:
                continue
            profile = armor_rune_profile_for_item(instance)
            if profile is not None:
                yield profile

    def _armor_potency_modifiers(self, state: EncounterState, creature: CreatureState) -> tuple[Modifier, ...]:
        modifiers: list[Modifier] = []
        for profile in self._invested_worn_armors(state, creature):
            bonus = armor_item_ac_bonus(0, profile)
            if bonus:
                modifiers.append(Modifier(bonus, "item", "armor potency"))
        return tuple(modifiers)

    def _resilient_save_modifiers(self, state: EncounterState, creature: CreatureState) -> tuple[Modifier, ...]:
        modifiers: list[Modifier] = []
        for profile in self._invested_worn_armors(state, creature):
            modifier = armor_resilient_modifier(profile)
            if modifier is not None:
                modifiers.append(modifier)
        return tuple(modifiers)

    def _spell_attack_modifier_breakdown(
        self, state: EncounterState, caster: CreatureState,
        continuation: ActionContinuation, spell_id: str,
    ) -> tuple[Modifier, ...]:
        """Build one spell attack from printed values and live conditions."""
        definition = get_definition(caster.definition_id)
        if definition.spell_attack is None or definition.spell_attribute is None:
            raise _Unsupported("This caster has no admitted spell attack statistic.")
        modifiers: list[Modifier] = [
            Modifier(definition.spell_attack, "untyped", "printed spell attack modifier")
        ]
        if continuation.attack_penalty:
            modifiers.append(Modifier(continuation.attack_penalty, "untyped", "multiple attack penalty"))
        if continuation.guidance_bonus:
            modifiers.append(Modifier(continuation.guidance_bonus, "status", "Guidance"))
        weather_penalty = get_setup(state.setup_id).weather_ranged_spell_attack_circumstance_penalty
        if weather_penalty and "storm_born" not in definition.abilities:
            modifiers.append(Modifier(-weather_penalty, "circumstance", "weather"))
        modifiers.extend(condition_modifiers(
            self._conditions_for_actor(state, caster),
            CheckContext("spell_attack", definition.spell_attribute, spell_traits(spell_id)),
        ))
        return tuple(modifiers)

    def _spell_save_modifier_breakdown(
        self, state: EncounterState, target: CreatureState,
        continuation: ActionContinuation, spell_id: str,
        statistic: str = "fortitude",
    ) -> tuple[Modifier, ...]:
        """Build one spell save from its target's live defenses and conditions."""
        if statistic not in {"fortitude", "reflex", "will"}:
            raise _Unsupported(f"{statistic!r} is not an admitted saving throw statistic.")
        save_modifiers = dict(
            (name, modifier)
            for name, _rank, modifier in get_definition(target.definition_id).saves
        )
        base = save_modifiers.get(statistic)
        if base is None:
            raise _Unsupported(f"This target has no admitted {statistic.title()} save modifier.")
        modifiers: list[Modifier] = [Modifier(base, "untyped", f"printed {statistic.title()} save")]
        modifiers.extend(self._resilient_save_modifiers(state, target))
        alchemy_context = "poison" if spell_id == "giant_centipede_venom" else "fear" if spell_id == "fear" else None
        modifiers.extend(self._alchemy_save_modifiers(state, target, statistic, against=alchemy_context))
        if continuation.guidance_bonus:
            modifiers.append(Modifier(continuation.guidance_bonus, "status", "Guidance"))
        if continuation.divine_grace_used:
            modifiers.append(Modifier(2, "circumstance", "Divine Grace"))
        modifiers.extend(self._blood_magic_save_modifiers(state, target))
        modifiers.extend(
            Modifier(effect.value, "status", "Protection")
            for effect in state.active_effects
            if effect.kind == "protection"
            and effect.target_actor_id == target.actor_id
        )
        if spell_id == "fear":
            modifiers.extend(
                Modifier(effect.value, "status", "Courageous Anthem")
                for effect in state.active_effects
                if effect.kind == "courageous_anthem"
                and effect.target_actor_id == target.actor_id
            )
        if "mental" in spell_traits(spell_id):
            modifiers.extend(
                Modifier(effect.value, "status", "Soothe")
                for effect in state.active_effects
                if effect.kind == "soothe"
                and effect.target_actor_id == target.actor_id
            )
        modifiers.extend(
            Modifier(effect.value, "status", "Forbidding Ward")
            for effect in state.active_effects
            if effect.kind == "forbidding_ward"
            and effect.target_actor_id == target.actor_id
            and effect.selected_enemy_actor_id == continuation.actor_id
        )
        attribute = {
            "fortitude": "constitution",
            "reflex": "dexterity",
            "will": "wisdom",
        }[statistic]
        modifiers.extend(self._mutagen_modifiers(state, target, statistic))
        modifiers.extend(condition_modifiers(
            self._conditions_for_actor(state, target),
            CheckContext(statistic, attribute, spell_traits(spell_id)),
        ))
        return tuple(modifiers)

    @staticmethod
    def _alchemy_save_modifiers(
        state: EncounterState, target: CreatureState, statistic: str, *, against: str | None,
    ) -> tuple[Modifier, ...]:
        """Project the finite alchemical elixir save bonuses onto one save."""
        from .alchemy_content import ElixirFacts, FORMULAS_BY_ID

        modifiers: list[Modifier] = []
        labels = {
            "elixir_of_life_minor": "Minor Elixir of Life",
            "antidote_lesser": "Antidote (lesser)",
            "antiplague_lesser": "Antiplague (lesser)",
        }
        for effect in state.active_effects:
            if effect.target_actor_id != target.actor_id or not effect.kind.startswith("alchemy_"):
                continue
            formula = FORMULAS_BY_ID.get(effect.kind.removeprefix("alchemy_"))
            if formula is None or not isinstance(formula.facts, ElixirFacts):
                continue
            label = labels.get(formula.formula_id, formula.name)
            for bonus in formula.facts.save_bonuses:
                if bonus.statistic != statistic:
                    continue
                if bonus.against == "all":
                    modifiers.append(Modifier(bonus.bonus, "item", label))
                elif against == bonus.against or (
                    bonus.against == "poison_or_disease" and against in {"poison", "disease"}
                ):
                    modifiers.append(Modifier(bonus.bonus, "item", label))
        return tuple(modifiers)

    @staticmethod
    def _blood_magic_save_modifiers(
        state: EncounterState, target: CreatureState,
    ) -> tuple[Modifier, ...]:
        return tuple(
            Modifier(effect.value, "status", "Angelic Blood Magic (Divine Aura)")
            for effect in state.active_effects
            if effect.kind == "blood_magic"
            and effect.target_actor_id == target.actor_id
        )

    def _spell_dc(self, state: EncounterState, caster: CreatureState, spell_id: str) -> int:
        """Return the caster's current spell DC, including its conditions."""
        definition = get_definition(caster.definition_id)
        if definition.spell_dc is None or definition.spell_attribute is None:
            raise _Unsupported("This caster has no admitted spell DC statistic.")
        modifiers = condition_modifiers(
            self._conditions_for_actor(state, caster),
            CheckContext("spell_dc", definition.spell_attribute, spell_traits(spell_id)),
        )
        return definition.spell_dc + combine_modifiers(modifiers)

    def _held_shield_instance(self, state: EncounterState, actor: CreatureState) -> ItemInstance | None:
        for instance_id in actor.held_items:
            instance = state.item_instances.get(instance_id)
            if instance is None:
                continue
            profile = self._shield_profile(instance)
            if profile is None or instance.hp is None:
                continue
            integrity = shield_integrity(profile, instance.hp)
            if not integrity.broken and not integrity.destroyed:
                return instance
        return None

    def _raised_shield_instance(self, state: EncounterState, actor: CreatureState) -> ItemInstance | None:
        raised = state.raised_shields.get(actor.actor_id)
        if raised is None or raised.instance_id not in actor.held_items:
            return None
        instance = state.item_instances.get(raised.instance_id)
        if instance is None or instance.hp is None:
            return None
        profile = self._shield_profile(instance)
        if profile is None:
            return None
        integrity = shield_integrity(profile, instance.hp)
        return None if integrity.broken or integrity.destroyed else instance

    def _shield_views(self, state: EncounterState, actor: CreatureState) -> tuple[ShieldView, ...]:
        inventory = (*actor.held_items, *actor.worn_items, *actor.stowed_items)
        views = []
        for instance_id in inventory:
            instance = state.item_instances.get(instance_id)
            if instance is None or instance.hp is None:
                continue
            profile = self._shield_profile(instance)
            if profile is None:
                continue
            integrity = shield_integrity(profile, instance.hp)
            raised = state.raised_shields.get(actor.actor_id)
            is_raised = raised is not None and raised.instance_id == instance.instance_id
            views.append(ShieldView(
                instance_id=instance.instance_id,
                definition_id=instance.definition_id,
                hp=instance.hp,
                max_hp=profile.max_hp,
                broken_threshold=profile.broken_threshold,
                hardness=profile.hardness,
                ac_bonus=profile.ac_bonus,
                broken=integrity.broken,
                raised=is_raised,
                ac_bonus_active=is_raised and not integrity.broken and not integrity.destroyed,
            ))
        return tuple(views)

    def _shield_block_trigger(
        self,
        state: EncounterState,
        target: CreatureState,
        resolution: DamageResolution,
        damage: DamageResult,
    ) -> ItemInstance | str | None:
        definition = get_definition(target.definition_id)
        if (not target.reaction_available
            or target.unconscious or target.dead
        ):
            return None
        magic_active = target.magic_shield_expires_at_start > state.actor_start_counts.get(target.actor_id, 0)
        if magic_active and damage.total > 0 and (
            resolution.source_kind == "spell"
            or "magical" in resolution.group.traits
            or (
                resolution.source_kind == "strike"
                and any(
                    component.amount > 0
                    and shield_block_trigger_eligible(component.damage_type, from_attack=True)
                    for component in damage.components
                )
            )
        ):
            return _MAGIC_SHIELD_BLOCK
        if resolution.source_kind != "strike" or "shield_block" not in definition.abilities:
            return None
        shield = self._raised_shield_instance(state, target)
        if shield is None:
            return None
        if not any(
            component.amount > 0
            and shield_block_trigger_eligible(component.damage_type, from_attack=True)
            for component in damage.components
        ):
            return None
        return shield

    @staticmethod
    def _shield_block_detail(record: ShieldBlockRecord) -> str:
        if record.magic:
            return (
                f"Magic Shield Block: Hardness {record.hardness} prevents "
                f"{record.prevented_from_actor} from reaching the caster; the spell ends."
            )
        return (
            f"Shield Block: Hardness {record.hardness} prevents "
            f"{record.prevented_from_actor} from reaching the wielder; "
            f"wielder takes {record.damage_to_actor} and shield takes "
            f"{record.damage_to_shield} ({record.shield_hp_before}→{record.shield_hp_after} HP)."
        )

    def _apply_shield_block(
        self,
        state: EncounterState,
        target: CreatureState,
        resolution: DamageResolution,
        damage: DamageResult,
        shield: ItemInstance,
    ) -> ShieldBlockRecord:
        profile = self._shield_profile(shield)
        if profile is None or shield.hp is None:
            raise _Rejected("Shield Block no longer has a valid shield instance.")
        shield_vulnerable_damage = sum(
            component.amount
            for component in damage.components
            if component.damage_type.casefold() not in SHIELD_IMMUNE_DAMAGE_TYPES
        )
        result = shield_block_result(
            damage.total,
            profile,
            shield.hp,
            shield_vulnerable_damage=shield_vulnerable_damage,
        )
        state.item_instances[shield.instance_id] = replace(shield, hp=result.shield_hp)
        target.reaction_available = False
        if shield_integrity(profile, result.shield_hp).broken:
            state.raised_shields.pop(target.actor_id, None)
        return ShieldBlockRecord(
            shield_instance_id=shield.instance_id,
            hardness=profile.hardness,
            incoming_damage=damage.total,
            shield_vulnerable_damage=shield_vulnerable_damage,
            prevented_from_actor=result.prevented,
            damage_to_actor=result.damage_to_actor,
            damage_to_shield=result.damage_to_shield,
            shield_hp_before=shield.hp,
            shield_hp_after=result.shield_hp,
        )

    @staticmethod
    def _apply_magic_shield_block(
        state: EncounterState, target: CreatureState, damage: DamageResult,
    ) -> ShieldBlockRecord:
        if target.magic_shield_expires_at_start <= state.actor_start_counts.get(target.actor_id, 0):
            raise _Rejected("Magic Shield is no longer raised.")
        prevented = min(damage.total, 5)
        target.reaction_available = False
        target.magic_shield_expires_at_start = 0
        target.shield_recast_available_at_seconds = state.world_time_seconds + 600
        return ShieldBlockRecord(
            shield_instance_id=_MAGIC_SHIELD_BLOCK,
            hardness=5,
            incoming_damage=damage.total,
            shield_vulnerable_damage=0,
            prevented_from_actor=prevented,
            damage_to_actor=damage.total - prevented,
            damage_to_shield=0,
            shield_hp_before=0,
            shield_hp_after=0,
            magic=True,
        )

    def choose(self, choice_id: int, option_id: str, actor_id: str | None = None) -> ActionResult:
        """Resolve the currently displayed persisted choice."""
        return self.execute(Choose(choice_id, option_id, actor_id))

    def _choose(self, state: EncounterState, dice: DiceSource, command: Choose) -> list[Event]:
        pending = state.pending_choice
        if pending is None or command.choice_id != pending.choice_id:
            raise _Rejected("This choice is stale or no longer pending.")
        if command.actor_id is not None and command.actor_id != pending.owner_actor_id:
            raise _Rejected("This choice belongs to another actor or the GM.")
        if command.option_id not in {option.option_id for option in pending.options}:
            raise _Rejected("That option is not available for the pending choice.")
        state.pending_choice = None

        if pending.kind == "no_escape":
            state.pending_choice = pending
            try:
                self._validate_pending_context()
            except ValueError as error:
                raise _Rejected("No Escape is no longer available.") from error
            finally:
                state.pending_choice = None
            continuation = pending.continuation
            mover = state.creatures[pending.actor_id or ""]
            reactor = state.creatures[pending.owner_actor_id or ""]
            assert continuation is not None
            if command.option_id == "decline":
                return [Event(
                    "no_escape_declined", reactor.actor_id, mover.actor_id,
                    f"{reactor.label} declines to use No Escape.",
                )] + self._advance_continuation(state, dice, continuation)
            pursuit = self._no_escape_pursuit_path(state, reactor, mover)
            if pursuit is None:
                return [Event(
                    "no_escape_stopped", reactor.actor_id, mover.actor_id,
                    f"{reactor.label} cannot legally Stride to maintain reach.",
                )] + self._advance_continuation(state, dice, continuation)
            path, spent, diagonals = pursuit
            reactor.reaction_available = False
            continuation.no_escape_reactor_id = reactor.actor_id
            continuation.no_escape_remaining_speed_ft = (
                effective_speed_ft(
                    reactor, get_definition(reactor.definition_id),
                    self._conditions_for_actor(state, reactor),
                ) - spent
            )
            event = Event(
                "no_escape_pursuit", reactor.actor_id, mover.actor_id,
                f"{reactor.label} spends their reaction to Stride and maintain reach of {mover.label}.",
                details=tuple(_coord(point) for point in path),
            )
            if not path:
                return [event] + self._advance_continuation(state, dice, continuation)
            follow = ActionContinuation(
                kind="movement", actor_id=reactor.actor_id, path=path,
                movement_kind="no_escape", seen_reactors=[], parent_continuation=continuation,
            )
            return [event] + self._advance_continuation(state, dice, follow)

        if pending.kind in {"stunning_blows", "stunning_blows_hero_reroll"}:
            state.pending_choice = pending
            try:
                self._validate_pending_context()
            except ValueError as error:
                raise _Rejected("Stunning Blows is no longer available.") from error
            finally:
                state.pending_choice = None
            continuation = pending.continuation
            monk = state.creatures[pending.actor_id or ""]
            target = state.creatures[pending.target_id or ""]
            assert continuation is not None
            if pending.kind == "stunning_blows":
                if command.option_id == "decline":
                    continuation.stunning_blows_target_id = None
                    from .paired_strikes import after_subordinate_strike
                    context = FamilyProcedureContext(
                        self, state, dice, monk, get_definition(monk.definition_id), "martial",
                    )
                    result = after_subordinate_strike(context, continuation.paired_strike)
                    return [Event(
                        "stunning_blows_declined", monk.actor_id, target.actor_id,
                        f"{monk.label} declines Stunning Blows.",
                    )] + self._family_result_events(result, "martial")
                check = self._stunning_blows_save(state, dice, monk, target, continuation)
                if target.health_mode is HealthMode.PC and target.hero_points > 0:
                    self._set_pending(
                        state, kind="stunning_blows_hero_reroll", owner_actor_id=target.actor_id,
                        prompt=f"{target.label} may keep this Stunning Blows Fortitude save or spend a Hero Point to reroll.",
                        options=(ChoiceOption("keep", "Keep"), ChoiceOption("spend_hero_point", "Spend Hero Point")),
                        actor_id=monk.actor_id, target_id=target.actor_id, check=check,
                        check_kind="stunning_blows_save", check_owner_actor_id=target.actor_id,
                        continuation=continuation,
                    )
                    return [Event(
                        "stunning_blows_save", monk.actor_id, target.actor_id,
                        f"{target.label} attempts a Fortitude save against {monk.label}'s class DC {get_definition(monk.definition_id).class_dc}: {check.degree.label()}.",
                        check=check,
                    )]
                return self._apply_stunning_blows_result(state, dice, monk, target, continuation, check)
            check = pending.check
            assert check is not None
            events: list[Event] = []
            if command.option_id == "spend_hero_point":
                target.hero_points -= 1
                check = self._stunning_blows_save(state, dice, monk, target, continuation)
                events.append(Event(
                    "hero_reroll", target.actor_id, target.actor_id,
                    f"Stunning Blows Fortitude Hero reroll: d20 {check.die}.", check=check,
                ))
            else:
                events.append(Event(
                    "check_kept", target.actor_id, target.actor_id,
                    "Kept the Stunning Blows Fortitude save.", check=check,
                ))
            return events + self._apply_stunning_blows_result(
                state, dice, monk, target, continuation, check,
            )

        if pending.kind == "witch_restored_spirit_timing":
            state.pending_choice = pending
            try:
                self._validate_pending_context()
            finally:
                state.pending_choice = None
            actor = state.creatures[pending.actor_id or ""]
            continuation = pending.continuation
            assert continuation is not None
            familiar, _recipients = self._restored_spirit_recipients(state, actor)
            assert familiar is not None
            events: list[Event] = []
            if command.option_id.startswith("before:"):
                target = state.creatures[command.option_id.partition(":")[2]]
                if target.temporary_hp:
                    self._offer_restored_spirit_temp_hp_choice(
                        state, actor, familiar, target, continuation, timing="before",
                        family_command=pending.family_command,
                    )
                    return events
                if target.actor_id != actor.actor_id:
                    self._offer_restored_spirit_willingness(
                        state, actor, familiar, target, continuation, timing="before",
                        family_command=pending.family_command,
                    )
                    return events
                self._grant_restored_spirit(state, actor, target)
                events.append(Event("restored_spirit", familiar.actor_id, target.actor_id,
                    f"{familiar.label}'s Restored Spirit grants {target.label} 2 temporary HP before the hex."))
            elif command.option_id == "decline":
                continuation.stage = "restored_spirit_declined"
            elif continuation.kind in {"witch_sustain_stoke", "witch_patrons_puppet"}:
                if continuation.kind == "witch_sustain_stoke":
                    events.extend(self._commit_sustain_stoke(state, dice, actor, continuation))
                else:
                    from .witch import PatronsPuppet
                    if not isinstance(pending.family_command, PatronsPuppet):
                        raise _Rejected("Restored Spirit has no saved Patron's Puppet command.")
                    start = state.actor_start_counts.get(actor.actor_id, 0)
                    actor.witch_restored_spirit_used_start = start
                    events.extend(self._run_family_action(state, dice, actor, pending.family_command))
                    actor.witch_restored_spirit_used_start = 0
                return self._offer_restored_spirit_choice(state, actor, events, dice=dice)
            return events + self._resume_restored_spirit_trigger(
                state, dice, actor, continuation, pending.family_command,
            )

        if pending.kind == "witch_restored_spirit":
            # Re-use the load-time validation after clearing the UI frame.
            state.pending_choice = pending
            try:
                self._validate_pending_context()
            finally:
                state.pending_choice = None
            actor = state.creatures[pending.actor_id or ""]
            familiar = next(candidate for candidate in state.creatures.values()
                            if self._familiar_owned_by(actor, candidate)
                            and not candidate.dead and not candidate.unconscious)
            if command.option_id == "decline":
                return self._complete_action(state, actor, [Event(
                    "restored_spirit_declined", familiar.actor_id, None,
                    f"{actor.label} declines Restored Spirit.",
                )], dice=dice)
            target = state.creatures[command.option_id]
            if target.temporary_hp:
                self._offer_restored_spirit_temp_hp_choice(
                    state, actor, familiar, target, None, timing="after",
                )
                return []
            if target.actor_id != actor.actor_id:
                self._offer_restored_spirit_willingness(
                    state, actor, familiar, target, None, timing="after",
                )
                return []
            self._grant_restored_spirit(state, actor, target)
            return self._complete_action(state, actor, [Event(
                "restored_spirit", familiar.actor_id, target.actor_id,
                f"{familiar.label}'s Restored Spirit grants {target.label} 2 temporary HP until the Witch's next turn.",
            )], dice=dice)

        if pending.kind == "witch_restored_spirit_temp_hp":
            actor = state.creatures[pending.actor_id or ""]
            target = state.creatures[pending.target_id or ""]
            familiar = state.creatures[pending.effect_id or ""]
            continuation = pending.continuation
            if command.option_id == "gain_new":
                self._grant_restored_spirit(state, actor, target)
            else:
                actor.witch_restored_spirit_used_start = state.actor_start_counts.get(actor.actor_id, 0)
            events = [Event(
                "restored_spirit",
                familiar.actor_id,
                target.actor_id,
                f"{target.label} {'gains 2 temporary HP from' if command.option_id == 'gain_new' else 'keeps existing temporary HP instead of'} {familiar.label}'s Restored Spirit.",
            )]
            if pending.transition_kind == "before":
                if continuation is None:
                    raise _Rejected("Restored Spirit has no saved hex action.")
                return events + self._resume_restored_spirit_trigger(
                    state, dice, actor, continuation, pending.family_command,
                )
            return events + self._complete_action(state, actor, [], dice=dice)

        if pending.kind == "witch_restored_spirit_willingness":
            actor = state.creatures[pending.actor_id or ""]
            target = state.creatures[pending.target_id or ""]
            familiar = state.creatures[pending.effect_id or ""]
            continuation = pending.continuation
            events: list[Event] = []
            if command.option_id == "willing":
                self._grant_restored_spirit(state, actor, target)
                events.append(Event(
                    "restored_spirit", familiar.actor_id, target.actor_id,
                    f"{target.label} accepts {familiar.label}'s Restored Spirit and gains 2 temporary HP.",
                ))
            else:
                events.append(Event(
                    "restored_spirit_refused", familiar.actor_id, target.actor_id,
                    f"{target.label} declines {familiar.label}'s Restored Spirit.",
                ))
            if pending.transition_kind == "before":
                if continuation is None:
                    raise _Rejected("Restored Spirit has no saved hex action.")
                return events + self._resume_restored_spirit_trigger(
                    state, dice, actor, continuation, pending.family_command,
                )
            return events + self._complete_action(state, actor, [], dice=dice)

        if pending.kind == "counter_performance_save_choice":
            state.pending_choice = pending
            try:
                self._validate_pending_context()
            except ValueError as error:
                raise _Rejected("Counter Performance is no longer available for this save.") from error
            finally:
                state.pending_choice = None
            caster = state.creatures[pending.actor_id or ""]
            target = state.creatures[pending.target_id or ""]
            continuation = pending.continuation
            check = pending.check
            assert continuation is not None and check is not None
            if command.option_id == "counter_performance":
                return self._start_counter_performance(state, dice, pending)
            if command.option_id == "spend_hero_point":
                if target.hero_points < 1:
                    raise _Rejected("No Hero Point remains for this Command save.")
                target.hero_points -= 1
                check = self._hero_reroll_check(dice, check)
                events = [Event("hero_reroll", target.actor_id, target.actor_id,
                    f"{target.label} spends 1 Hero Point and retains the second Command save result.", check=check)]
            else:
                events = [Event("command_save_kept", target.actor_id, target.actor_id,
                    f"{target.label} keeps the Command save result.", check=check)]
            return events + self._resolve_command_result(state, dice, caster, target, continuation, check)

        if pending.kind == "counter_performance_bard_hero_reroll":
            state.pending_choice = pending
            try:
                self._validate_pending_context()
            except ValueError as error:
                raise _Rejected("The saved Counter Performance check is no longer available.") from error
            finally:
                state.pending_choice = None
            bard = state.creatures[pending.owner_actor_id or ""]
            caster = state.creatures[pending.actor_id or ""]
            target = state.creatures[pending.target_id or ""]
            continuation = pending.continuation
            performance = pending.check
            if continuation is None or continuation.spell_check is None or performance is None:
                raise _Rejected("The saved Counter Performance check is incomplete.")
            if command.option_id == "spend_hero_point":
                if bard.hero_points < 1:
                    raise _Rejected("No Hero Point remains for Counter Performance.")
                bard.hero_points -= 1
                performance = self._hero_reroll_check(dice, performance)
                events = [Event("hero_reroll", bard.actor_id, target.actor_id,
                    f"{bard.label} spends 1 Hero Point and retains the second Counter Performance result.", check=performance)]
            else:
                events = [Event("counter_performance_kept", bard.actor_id, target.actor_id,
                    f"{bard.label} keeps the Counter Performance result.", check=performance)]
            return events + self._resolve_counter_performance_result(
                state, dice, caster, target, continuation, continuation.spell_check, performance, bard
            )

        if pending.kind == "lingering_composition_hero_reroll":
            actor = state.creatures.get(pending.actor_id or "")
            check = pending.check
            if (
                actor is None or check is None or pending.owner_actor_id != actor.actor_id
                or pending.options != (ChoiceOption("keep", "Keep result"), ChoiceOption("spend_hero_point", "Spend 1 Hero Point and reroll"))
                or not pending.target_ids
            ):
                raise _Rejected("The saved Lingering Composition check is incomplete.")
            if command.option_id == "spend_hero_point":
                if actor.health_mode is not HealthMode.PC or actor.hero_points < 1:
                    raise _Rejected("No Hero Point remains for this Lingering Composition check.")
                actor.hero_points -= 1
                check = self._hero_reroll_check(dice, check)
            return self._finalize_lingering_composition(state, actor, check)

        # Clue In is represented as a reaction choice, but its saved
        # underlying skill check belongs to the triggering creature and must
        # resume through the Investigator family handler.
        if pending.kind == "reaction" and pending.procedure_id == "investigator:clue_in":
            return self._run_family_choice(state, dice, pending, command)

        if pending.kind == "desperate_prayer":
            actor = state.creatures.get(pending.actor_id or "")
            if (
                actor is None
                or actor.actor_id != pending.owner_actor_id
                or actor.unconscious
                or actor.dead
                or "desperate_prayer" not in get_definition(actor.definition_id).abilities
                or actor.focus_points != 0
                or actor.actor_id in state.desperate_prayer_used
            ):
                raise _Rejected("Desperate Prayer is no longer available.")
            if command.option_id == "accept":
                actor.focus_points = 1
                state.desperate_prayer_used.add(actor.actor_id)
                state.desperate_prayer_points.add(actor.actor_id)
                events = [Event(
                    "desperate_prayer",
                    actor.actor_id,
                    actor.actor_id,
                    f"{actor.label} uses Desperate Prayer and gains 1 temporary devotion Focus Point.",
                )]
            else:
                events = [Event(
                    "desperate_prayer_declined",
                    actor.actor_id,
                    actor.actor_id,
                    f"{actor.label} declines Desperate Prayer; the daily use remains available.",
                )]
            actor.actions_remaining = 3
            abilities = set(get_definition(actor.definition_id).abilities)
            actor.reaction_available = bool({"reactive_strike", "shield_block", "shield_cantrip", "counter_performance", "no_escape", "reactive_shield"} & abilities) or bool({"Nimble Dodge", "Reactive Shield", "You're Next"} & set(get_definition(actor.definition_id).feats)) or "investigator_on_the_case" in abilities
            events.append(Event("turn_started", actor.actor_id, None, f"{actor.label} regains 3 actions and 1 reaction."))
            return events

        if pending.kind == "damage_defense":
            resolution = pending.damage_resolution
            if resolution is None or resolution.pending_defense_choice is None:
                raise _Rejected("The pending damage defense choice is incomplete.")
            options, by_type = self._damage_defense_options(
                resolution.group, resolution.pending_defense_choice
            )
            selected_type = command.option_id.removeprefix("resist:")
            part = by_type.get(selected_type)
            if command.option_id not in {option.option_id for option in options} or part is None:
                raise _Rejected("That damage type is no longer eligible for this defense.")
            selection = DefenseSelection(
                resolution.pending_defense_choice.defense_source, part
            )
            resolution = replace(
                resolution,
                selections=(*resolution.selections, selection),
                pending_defense_choice=None,
            )
            target = state.creatures[resolution.target_id]
            events = [Event(
                "damage_defense_choice",
                target.actor_id,
                target.actor_id,
                f"{target.label} chooses {selected_type} for {selection.defense_source}.",
            )]
            events.extend(self._resolve_damage_to_health(
                state, dice, resolution, resumed=True
            ))
            return events

        if pending.kind == "shield_block":
            resolution = pending.damage_resolution
            if resolution is None or resolution.shield_block_status != "pending":
                raise _Rejected("The pending Shield Block choice is incomplete.")
            try:
                mitigation = apply_damage_defenses(
                    resolution.group,
                    self._justice_damage_defenses(
                        state,
                        resolution,
                        get_definition(state.creatures[resolution.target_id].definition_id).damage_defenses,
                    ),
                    resolution.selections,
                )
            except ValueError as error:
                raise _Rejected("The pending Shield Block damage defenses are no longer valid.") from error
            if mitigation.unresolved_choices or len(mitigation.results) != 1:
                raise _Rejected("Damage defenses must be resolved before Shield Block.")
            target = state.creatures[resolution.target_id]
            damage = mitigation.results[0]
            shield = self._shield_block_trigger(state, target, resolution, damage)
            magic = shield == _MAGIC_SHIELD_BLOCK
            if (
                shield is None
                or magic != resolution.shield_block_magic
                or (not magic and shield.instance_id != resolution.shield_block_instance_id)
                or (magic and resolution.shield_block_instance_id is not None)
            ):
                raise _Rejected("The raised shield or reaction is no longer available.")
            if command.option_id == "block":
                clear_pending_spellshape(target)
                record = (
                    self._apply_magic_shield_block(state, target, damage)
                    if magic else self._apply_shield_block(state, target, resolution, damage, shield)
                )
                resolution = replace(
                    resolution,
                    shield_block_status="applied",
                    shield_block_record=record,
                )
                choice_event = Event(
                    "shield_block", target.actor_id, target.actor_id,
                    self._shield_block_detail(record),
                )
            else:
                resolution = replace(resolution, shield_block_status="declined")
                choice_event = Event(
                    "shield_block_declined", target.actor_id, target.actor_id,
                    f"{target.label} declines Shield Block; the reaction remains available.",
                )
            return [choice_event, *self._resolve_damage_to_health(
                state, dice, resolution, resumed=True
            )]

        if pending.kind == "family_action":
            if pending.procedure_id == "w4_offensive:exacting_strike":
                return self._resolve_w4_exacting_press_choice(state, dice, pending, command)
            return self._run_family_choice(state, dice, pending, command)

        if pending.kind == "nimble_dodge":
            target = state.creatures.get(pending.target_id or "")
            attacker = state.creatures.get(pending.actor_id or "")
            continuation = pending.continuation
            if target is None or attacker is None or continuation is None:
                raise _Rejected("The pending Nimble Dodge choice is incomplete.")
            if target.actor_id != pending.owner_actor_id or not self._nimble_dodge_available(state, attacker, target):
                raise _Rejected("Nimble Dodge is no longer available.")
            continuation.nimble_dodge_decided = True
            if command.option_id == "use":
                target.reaction_available = False
                clear_pending_spellshape(target)
                continuation.nimble_dodge_used = True
                event = Event(
                    "nimble_dodge_used",
                    target.actor_id,
                    attacker.actor_id,
                    f"{target.label} uses Nimble Dodge; +2 circumstance AC against this attack.",
                )
            else:
                event = Event(
                    "nimble_dodge_declined",
                    target.actor_id,
                    attacker.actor_id,
                    f"{target.label} declines Nimble Dodge; the reaction remains available.",
                )
            if continuation.kind == "cast":
                events = [event, *self._resolve_cast(state, dice, continuation)]
            elif continuation.kind == "ranged_strike":
                events = [event, *self._roll_strike(
                    state, dice, attacker, target,
                    self._find_attack(state, attacker, continuation.attack_id), continuation,
                    parent=continuation.parent_continuation,
                )]
            else:
                attack = self._find_attack(state, attacker, continuation.attack_id)
                if attack is None:
                    raise _Rejected("The Nimble Dodge Strike is no longer available.")
                events = [event, *self._roll_strike(
                    state, dice, attacker, target, attack, continuation,
                    parent=continuation.parent_continuation,
                )]
            return events

        if pending.kind == "youre_next":
            attacker = state.creatures.get(pending.actor_id or "")
            if attacker is None or pending.owner_actor_id != attacker.actor_id:
                raise _Rejected("The pending You're Next choice is incomplete.")
            state.pending_choice = pending
            try:
                self._validate_pending_context()
            except ValueError as error:
                raise _Rejected("You're Next is no longer available.") from error
            finally:
                state.pending_choice = None
            if command.option_id == "decline":
                return self._finish_after_youre_next(
                    state, dice, attacker,
                    [Event("youre_next_declined", attacker.actor_id, None, f"{attacker.label} declines You're Next.")],
                )
            if not command.option_id.startswith("target:"):
                raise _Rejected("Choose an eligible You're Next target or decline.")
            target_id = command.option_id.removeprefix("target:")
            if target_id not in pending.target_ids:
                raise _Rejected("That You're Next target is no longer eligible.")
            attacker.reaction_available = False
            from .skill_actions import Demoralize

            events = [Event(
                "youre_next_used", attacker.actor_id, target_id,
                f"{attacker.label} uses You're Next against {state.creatures[target_id].label}; the Demoralize gains +2 circumstance.",
            )]
            events.extend(self._run_family_action(
                state, dice, attacker,
                Demoralize(target_id=target_id, youre_next_reaction=True),
                youre_next_trigger=True,
            ))
            if state.pending_choice is not None:
                raise _Rejected("You're Next must resolve its bounded Demoralize check without another choice.")
            return self._finish_after_youre_next(state, dice, attacker, events)

        if pending.kind == "reactive_shield":
            target = state.creatures.get(pending.target_id or "")
            attacker = state.creatures.get(pending.actor_id or "")
            continuation = pending.continuation
            if target is None or attacker is None or continuation is None:
                raise _Rejected("The pending Reactive Shield choice is incomplete.")
            attack = self._find_attack(state, attacker, continuation.attack_id)
            if (
                target.actor_id != pending.owner_actor_id
                or attack is None
                or "melee" not in attack.traits
                or "ranged" in attack.traits
                or not self._reactive_shield_available(state, attacker, target)
            ):
                raise _Rejected("Reactive Shield is no longer available.")
            if command.option_id == "use":
                target.reaction_available = False
                clear_pending_spellshape(target)
                shield = self._held_shield_instance(state, target)
                if shield is None:
                    raise _Rejected("Reactive Shield requires the same intact held shield.")
                state.raised_shields[target.actor_id] = RaisedShieldState(
                    shield.instance_id,
                    state.actor_start_counts.get(target.actor_id, 0) + 1,
                )
                event = Event(
                    "reactive_shield_used",
                    target.actor_id,
                    attacker.actor_id,
                    f"{target.label} uses Reactive Shield; the shield's +2 circumstance AC applies to this attack.",
                )
            elif command.option_id == "decline":
                event = Event(
                    "reactive_shield_declined",
                    target.actor_id,
                    attacker.actor_id,
                    f"{target.label} declines Reactive Shield; the reaction remains available.",
                )
            else:
                raise _Rejected("Choose whether to use Reactive Shield.")
            check = pending.check
            if check is None:
                raise _Rejected("The pending Reactive Shield attack check is incomplete.")
            if command.option_id == "use":
                check = replace(
                    resolve_check(
                        check.die,
                        check.modifier,
                        self._attack_dc(state, attacker, target, attack),
                        attack_id=check.attack_id,
                        attack_count=check.attack_count,
                        map_penalty=check.map_penalty,
                        traits=check.traits,
                    ),
                    modifier_breakdown=check.modifier_breakdown,
                    dice=check.dice,
                )
            events = [event]
            events.extend(self._resolve_attack_result(
                state, dice, attacker, target, attack, check,
                damage_type=pending.damage_type or attack.damage_type,
                nonlethal=pending.nonlethal,
                damage_bonus_dice=pending.damage_bonus_dice,
                attack_target_off_guard=pending.attack_target_off_guard,
                is_reaction=pending.is_reaction,
                continuation=continuation.parent_continuation,
                item_id=pending.item_id,
                bomber_only_primary_splash=pending.damage_context == "bomber_only_primary",
            ))
            return events

        if pending.kind == "concealment_hero_reroll":
            continuation = pending.continuation
            actor = state.creatures.get(pending.actor_id or "")
            target = state.creatures.get(pending.target_id or "")
            check = pending.check
            attack = self._find_attack(state, actor, pending.attack_id) if actor is not None and pending.attack_id else None
            if actor is None or continuation is None or check is None:
                raise _Rejected("The pending concealment flat check is incomplete.")
            item_target = continuation.kind == "cast" and pending.spell_id == "runic_weapon"
            if item_target:
                try:
                    item_facts = self._runic_weapon_target(
                        state, actor, continuation.spell_target_item_id,
                        reach_spell_effective_range_ft=continuation.reach_spell_effective_range_ft,
                    )
                except ValueError as error:
                    raise _Rejected("Runic Weapon's original physical item is no longer eligible.") from error
                if item_facts[1] != continuation.spell_target_wielder_id:
                    raise _Rejected("Runic Weapon's original item wielder changed before the flat check.")
                if not self._runic_weapon_item_concealed(state, actor, item_facts):
                    raise _Rejected("The concealment flat check is no longer required.")
                concealment_target_id = continuation.spell_target_item_id
                concealment_target_label = concealment_target_id
            else:
                if target is None:
                    raise _Rejected("The pending concealment flat check is incomplete.")
                if not self.target_is_concealed(actor.actor_id, target.actor_id):
                    raise _Rejected("The concealment flat check is no longer required.")
                concealment_target_id = target.actor_id
                concealment_target_label = target.label
            if continuation.kind == "family_action":
                from . import skill_actions
                family_context = FamilyProcedureContext(
                    self, state, dice, actor, get_definition(actor.definition_id),
                    "martial", pending=pending, choice=command,
                )
                result = skill_actions.handle_choice(family_context)
                return self._family_result_events(result, "martial")
            if command.option_id == "spend_hero_point":
                if actor.hero_points < 1:
                    raise _Rejected("The concealment check owner no longer has a Hero Point.")
                actor.hero_points -= 1
                check = resolve_check(dice.draw(20), 0, 5)
                events = [Event(
                    "hero_reroll",
                    actor.actor_id,
                    concealment_target_id,
                    f"Hero Point reroll of the concealment flat check against {concealment_target_label}: d20 {check.die} vs DC 5; "
                    f"{check.degree.label().lower()}.",
                    check=check,
                )]
            else:
                events = [Event(
                    "concealment_kept",
                    actor.actor_id,
                    concealment_target_id,
                    f"{actor.label} keeps the concealment flat check result against {concealment_target_label}.",
                    check=check,
                )]
            if continuation.kind == "cast":
                if pending.spell_id not in CONCEALMENT_TARGETED_SPELL_IDS:
                    raise _Rejected("The saved spell concealment check is unsupported.")
                events.extend(self._finish_spell_concealment(
                    state, dice, actor, target if not item_target else None,
                    continuation, check,
                    item_id=concealment_target_id if item_target else None,
                ))
            else:
                if attack is None:
                    raise _Rejected("The pending concealment Strike is incomplete.")
                events.extend(self._finish_concealment_check(
                    state, dice, actor, target, attack, continuation, check
                ))
            return events

        if pending.kind == "initiative_hero_reroll":
            actor = state.creatures[pending.actor_id or ""]
            events: list[Event] = []
            if command.option_id == "spend_hero_point":
                actor.hero_points -= 1
                die = dice.draw(20)
                modifier = pending.initiative_modifier or 0
                actor.initiative = die + modifier
                events.append(Event("hero_reroll", actor.actor_id, None, f"{actor.label} spent 1 Hero Point; initiative reroll is d20 {die} + {modifier} = {actor.initiative}."))
            else:
                events.append(Event("initiative_kept", actor.actor_id, None, f"{actor.label} kept initiative {actor.initiative}."))
            decided = state.initiative_hero_decided
            assert decided is not None
            decided.add(actor.actor_id)
            self._continue_initiative_initialization(state)
            return events

        if pending.kind == "initiative_tie":
            group_index = state.initiative_tie_group_index
            orders = state.initiative_tie_orders
            assert orders is not None
            selected = orders.setdefault(group_index, [])
            selected.append(command.option_id)
            remaining = [actor_id for actor_id in pending.tie_candidates if actor_id != command.option_id]
            if len(remaining) > 1:
                self._present_initiative_tie(state, group_index, tuple(remaining), tuple(selected))
            else:
                selected.extend(remaining)
                self._apply_initiative_tie_order(state, group_index)
                state.initiative_tie_group_index += 1
                self._continue_tie_choices(state)
            return [Event("initiative_tie_choice", command.option_id, None, f"Selected {command.option_id} as the next tied PC in initiative order.")]

        if pending.kind == "reaction":
            if pending.continuation is not None and pending.continuation.reaction_trigger == "justice_damage":
                resolution = pending.damage_resolution
                reactor = state.creatures.get(pending.owner_actor_id or "")
                attacker = state.creatures.get(pending.actor_id or "")
                target = state.creatures.get(pending.target_id or "")
                if resolution is None or reactor is None or attacker is None or target is None:
                    raise _Rejected("The pending Retributive Strike choice is incomplete.")
                if (
                    resolution.target_id != target.actor_id
                    or resolution.actor_id != attacker.actor_id
                    or reactor.actor_id != resolution.justice_actor_id
                    or not resolution.justice_checked
                ):
                    raise _Rejected("The pending Retributive Strike choice is stale.")
                if command.option_id == "accept":
                    if not reactor.reaction_available or reactor.unconscious or reactor.dead:
                        raise _Rejected("Retributive Strike is no longer available.")
                    reactor.reaction_available = False
                    clear_pending_spellshape(reactor)
                    resolution = replace(resolution, justice_protected=True)
                    choice_event = Event(
                        "retributive_strike_protection",
                        reactor.actor_id,
                        target.actor_id,
                        f"{reactor.label} protects {target.label} with resistance 3; the Champion's reaction is spent.",
                    )
                else:
                    resolution = replace(resolution, justice_actor_id=None)
                    choice_event = Event(
                        "retributive_strike_declined",
                        reactor.actor_id,
                        target.actor_id,
                        f"{reactor.label} declines Retributive Strike; the reaction remains available.",
                    )
                return [choice_event, *self._resolve_damage_to_health(
                    state, dice, resolution, resumed=False
                )]
            reactor = state.creatures[pending.owner_actor_id or ""]
            target = state.creatures[pending.target_id or ""]
            continuation = pending.continuation
            assert continuation is not None
            if reactor.actor_id not in continuation.seen_reactors:
                continuation.seen_reactors.append(reactor.actor_id)
            if command.option_id == "decline":
                return [Event("reaction_declined", reactor.actor_id, target.actor_id, f"{reactor.label} declines; the reaction remains available.")] + self._advance_continuation(state, dice, continuation)
            if not reactor.reaction_available or reactor.unconscious or reactor.dead:
                raise _Rejected("This Reactive Strike is no longer available.")
            selection = next(
                (entry for entry in self._reaction_strike_choices(state, reactor, target) if entry[0] == command.option_id),
                None,
            )
            if selection is None:
                raise _Rejected("That Reactive Strike option is no longer available.")
            _option_id, attack, damage_type, nonlethal, _label, item_id = selection
            return self._perform_reaction(
                state, dice, reactor, target, continuation, attack, damage_type, nonlethal,
                item_id,
            )

        if pending.kind == "grabbed_manipulate_hero_reroll":
            actor = state.creatures[pending.actor_id or ""]
            continuation = pending.continuation
            check = pending.check
            assert continuation is not None and check is not None
            events: list[Event] = []
            if command.option_id == "spend_hero_point":
                actor.hero_points -= 1
                check = self._hero_reroll_check(dice, check)
                events.append(Event(
                    "hero_reroll",
                    actor.actor_id,
                    None,
                    f"Hero Point reroll of the Grabbed flat check: d20 {check.die} vs DC 5; "
                    f"{check.degree.label().lower()}.",
                    check=check,
                ))
            else:
                events.append(Event(
                    "flat_check_kept",
                    actor.actor_id,
                    None,
                    f"{actor.label} keeps the Grabbed flat check result.",
                    check=check,
                ))
            events.extend(self._finish_grabbed_manipulate_check(
                state, dice, actor, continuation, check
            ))
            return events

        if pending.kind == "spell_slot":
            actor = state.creatures[pending.actor_id or ""]
            return self._cast(state, dice, actor, Cast(
                spell_id=pending.spell_id or "",
                target_id=pending.target_id,
                actions=pending.spell_actions,
                slot_id=command.option_id,
                include_self=pending.include_self,
                item_id=pending.spell_target_item_id,
            ))

        if pending.kind == "spell_blood_magic_recipient":
            continuation = pending.continuation
            caster = state.creatures.get(pending.actor_id or "")
            target = state.creatures.get(pending.target_id or "")
            if continuation is not None and continuation.spell_id == "angelic_halo":
                if (
                    continuation.spell_source_kind != "focus"
                    or continuation.blood_magic_recipient_id is not None
                    or caster is None
                    or not self._valid_committed_blood_magic_halo(caster, continuation)
                    or pending.owner_actor_id != caster.actor_id
                    or pending.actor_id != caster.actor_id
                    or pending.target_id is not None
                    or pending.spell_id != continuation.spell_id
                    or pending.slot_id != continuation.slot_id
                    or pending.spell_actions != continuation.spell_actions
                    or pending.options != self._blood_magic_halo_recipient_options(state, caster)
                    or command.option_id not in {option.option_id for option in pending.options}
                ):
                    raise _Rejected("The Halo Blood Magic recipient choice is stale.")
                continuation.blood_magic_recipient_id = command.option_id
                return self._resolve_cast(state, dice, continuation)
            if continuation is not None and continuation.spell_actions == 3:
                if (
                    continuation.spell_id != "heal"
                    or continuation.spell_source_kind != "spontaneous"
                    or caster is None
                    or pending.owner_actor_id != caster.actor_id
                    or pending.options != self._blood_magic_area_recipient_options(state, caster, continuation)
                    or command.option_id not in {option.option_id for option in pending.options}
                ):
                    raise _Rejected("The Blood Magic recipient choice is stale.")
                continuation.blood_magic_recipient_id = command.option_id
                return self._apply_heal_emanation(state, dice, continuation)
            if (
                continuation is None
                or caster is None
                or target is None
                or pending.owner_actor_id != caster.actor_id
                or pending.options != self._blood_magic_recipient_options(caster, target)
                or command.option_id not in {
                    option.option_id for option in pending.options
                }
            ):
                raise _Rejected("The Blood Magic recipient choice is stale.")
            continuation.blood_magic_recipient_id = command.option_id
            if continuation.movement_kind == "manipulate":
                return self._advance_continuation(state, dice, continuation)
            return self._resolve_cast(state, dice, continuation)

        if pending.kind == "spell_target":
            continuation = pending.continuation
            if continuation is None or command.option_id not in pending.target_ids:
                raise _Rejected("That spell target choice is stale.")
            continuation.target_id = command.option_id
            continuation.spell_target_id = command.option_id
            return self._resolve_cast(state, dice, continuation)

        if pending.kind == "detect_magic_known":
            continuation = pending.continuation
            if continuation is None:
                raise _Rejected("The Detect Magic choice is stale.")
            state.pending_choice = pending
            try:
                self._validate_pending_context()
            finally:
                state.pending_choice = None
            continuation.include_self = command.option_id == "detect_all"
            return self._resolve_cast(state, dice, continuation)

        if pending.kind == "spell_self_inclusion":
            continuation = pending.continuation
            if continuation is None or (
                continuation.spell_id != "gale_blast"
                and (continuation.spell_id != "heal" or continuation.spell_actions != 3)
            ):
                raise _Rejected("That spell self-inclusion choice is stale.")
            continuation.include_self = command.option_id == "include"
            if continuation.spell_id == "gale_blast":
                caster = state.creatures.get(continuation.actor_id)
                if caster is None:
                    raise _Rejected("The Gale Blast caster is no longer available.")
                return self._resolve_gale_blast(state, dice, caster, continuation)
            if continuation.spell_source_kind == "spontaneous" and continuation.blood_magic_recipient_id is None:
                caster = state.creatures.get(continuation.actor_id)
                if caster is None:
                    raise _Rejected("The Heal caster is no longer available.")
                return self._offer_blood_magic_area_recipient(state, caster, continuation)
            return self._apply_heal_emanation(state, dice, continuation)

        if pending.kind == "spell_willingness":
            continuation = pending.continuation
            caster = state.creatures[pending.actor_id or ""]
            target = state.creatures[pending.target_id or ""]
            if pending.spell_id == "light":
                if continuation is not None and continuation.light_control == "sustain":
                    if (
                        continuation.kind != "cast"
                        or continuation.actor_id != caster.actor_id
                        or continuation.spell_id != "light"
                        or continuation.target_id != target.actor_id
                        or continuation.spell_target_id != target.actor_id
                        or continuation.light_orb_id is None
                        or continuation.light_attachment_actor_id != target.actor_id
                        or pending.spell_actions != 1
                        or pending.options != (
                            ChoiceOption("willing", "Willing"),
                            ChoiceOption("unwilling", "Unwilling"),
                        )
                    ):
                        raise _Rejected("The Light Sustain willingness choice is stale.")
                    orb_index = next(
                        (
                            index for index, orb in enumerate(state.light_orbs)
                            if orb.stable_id == continuation.light_orb_id
                        ),
                        None,
                    )
                    if orb_index is None:
                        raise _Rejected("The sustained Light orb is no longer available.")
                    orb = state.light_orbs[orb_index]
                    if (
                        orb.caster_actor_id != caster.actor_id
                        or orb.rank != 1
                        or orb.point != continuation.light_point
                        or orb.attached_actor_id is not None
                        or continuation.light_point is None
                        or target.position != orb.point
                    ):
                        raise _Rejected("The sustained Light orb or carrier is no longer eligible.")
                    if command.option_id == "willing":
                        state.light_orbs[orb_index] = replace(
                            orb,
                            point=None,
                            attached_actor_id=target.actor_id,
                        )
                        continuation.stage = "done"
                        return [Event(
                            "light_orb_attached",
                            caster.actor_id,
                            target.actor_id,
                            f"{target.label} willingly carries Light orb {orb.stable_id}.",
                            position=target.position,
                            details=(orb.stable_id, target.actor_id),
                        )] + self._complete_action(state, caster, [], dice=dice)
                    continuation.stage = "done"
                    return [Event(
                        "light_attachment_declined",
                        caster.actor_id,
                        target.actor_id,
                        f"{target.label} declines to carry Light orb {orb.stable_id}; it remains at {_coord(orb.point)}.",
                        position=orb.point,
                        details=(orb.stable_id,),
                    )] + self._complete_action(state, caster, [], dice=dice)
                if (
                    continuation is None
                    or continuation.kind != "cast"
                    or continuation.spell_id != "light"
                    or continuation.actor_id != caster.actor_id
                    or continuation.light_orb_id is None
                    or continuation.light_attachment_actor_id != target.actor_id
                    or pending.spell_actions != 2
                    or pending.options != (
                        ChoiceOption("willing", "Willing"),
                        ChoiceOption("unwilling", "Unwilling"),
                    )
                ):
                    raise _Rejected("The Light willingness choice is stale.")
                orb_index = next(
                    (
                        index for index, orb in enumerate(state.light_orbs)
                        if orb.stable_id == continuation.light_orb_id
                    ),
                    None,
                )
                if orb_index is None:
                    raise _Rejected("The Light orb is no longer available.")
                orb = state.light_orbs[orb_index]
                if (
                    orb.caster_actor_id != caster.actor_id
                    or orb.rank != 1
                    or orb.point is None
                    or orb.attached_actor_id is not None
                    or target.position != orb.point
                ):
                    raise _Rejected("The Light orb or carrier is no longer eligible.")
                if command.option_id == "willing":
                    state.light_orbs[orb_index] = replace(
                        orb,
                        point=None,
                        attached_actor_id=target.actor_id,
                    )
                    continuation.stage = "done"
                    return [Event(
                        "light_orb_attached",
                        caster.actor_id,
                        target.actor_id,
                        f"{target.label} willingly carries Light orb {orb.stable_id}.",
                        position=target.position,
                        details=(orb.stable_id, target.actor_id),
                    )] + self._complete_action(state, caster, [], dice=dice)
                continuation.stage = "done"
                return [Event(
                    "light_attachment_declined",
                    caster.actor_id,
                    target.actor_id,
                    f"{target.label} declines to carry Light orb {orb.stable_id}; it remains at {_coord(orb.point)}.",
                    position=orb.point,
                    details=(orb.stable_id,),
                )] + self._complete_action(state, caster, [], dice=dice)
            if pending.spell_id == "runic_weapon":
                if (
                    continuation is None
                    or continuation.spell_id != "runic_weapon"
                    or continuation.spell_target_item_id is None
                    or continuation.spell_target_wielder_id != target.actor_id
                    or pending.spell_target_item_id != continuation.spell_target_item_id
                    or command.option_id not in {"willing", "unwilling"}
                ):
                    raise _Rejected("The Runic Weapon willingness choice is stale.")
                if command.option_id == "unwilling":
                    continuation.stage = "refused"
                    return [Event(
                        "enchantment_refused",
                        caster.actor_id,
                        target.actor_id,
                        f"{target.label} declines Runic Weapon on {continuation.spell_target_item_id}.",
                    )] + self._advance_continuation(state, dice, continuation)
                try:
                    _item, wielder_id, _position = self._runic_weapon_target(
                        state, caster, continuation.spell_target_item_id,
                        reach_spell_effective_range_ft=continuation.reach_spell_effective_range_ft,
                    )
                except ValueError:
                    return [Event(
                        "action_stopped",
                        caster.actor_id,
                        None,
                        "Runic Weapon's original physical item is no longer an eligible target.",
                    )]
                if wielder_id != target.actor_id:
                    return [Event(
                        "action_stopped",
                        caster.actor_id,
                        None,
                        "Runic Weapon's original item wielder changed before resolution.",
                    )]
                continuation.stage = "willing"
                return [Event(
                    "spell_willingness_accepted",
                    target.actor_id,
                    caster.actor_id,
                    f"{target.label} accepts Runic Weapon on {continuation.spell_target_item_id}.",
                )] + self._advance_continuation(state, dice, continuation)
            if pending.spell_id == "runic_body":
                if (
                    continuation is None or continuation.spell_id != "runic_body"
                    or continuation.target_id != target.actor_id
                    or command.option_id not in {"willing", "unwilling"}
                ):
                    raise _Rejected("The Runic Body willingness choice is stale.")
                if command.option_id == "unwilling":
                    continuation.stage = "done"
                    return [Event("enchantment_refused", caster.actor_id, target.actor_id, f"{target.label} declines Runic Body.")] + self._complete_action(state, caster, [], dice=dice)
                continuation.stage = "willing"
                return self._resolve_runic_body(state, dice, caster, target, continuation)
            if pending.spell_id == "protection":
                if (
                    continuation is None or continuation.kind != "cast"
                    or continuation.spell_id != "protection"
                    or continuation.spell_actions != 2
                    or continuation.target_id != target.actor_id
                    or command.option_id not in {"willing", "unwilling"}
                ):
                    raise _Rejected("The Protection willingness choice is stale.")
                if command.option_id == "unwilling":
                    continuation.stage = "done"
                    return [Event(
                        "protection_refused", caster.actor_id, target.actor_id,
                        f"{target.label} declines Protection.",
                    )] + self._complete_action(state, caster, [], dice=dice)
                state.active_effects[:] = [
                    effect for effect in state.active_effects
                    if not (
                        effect.kind == "protection"
                        and effect.source_actor_id == caster.actor_id
                        and effect.target_actor_id == target.actor_id
                    )
                ]
                state.active_effects.append(ActiveSpellEffect(
                    effect_id=f"protection:{caster.actor_id}:{target.actor_id}:{state.next_choice_id}",
                    kind="protection", source_actor_id=caster.actor_id,
                    target_actor_id=target.actor_id, value=1,
                    expires_at_source_start=state.actor_start_counts.get(caster.actor_id, 0) + 10,
                    expires_at_world_time=state.world_time_seconds + 60,
                ))
                continuation.stage = "done"
                return [Event(
                    "protection_applied", caster.actor_id, target.actor_id,
                    f"{target.label} accepts +1 status to AC and all saves for 1 minute.",
                )] + self._complete_action(state, caster, [], dice=dice)
            if continuation is None or target.dead or not self._is_living_target(target):
                raise _Rejected("The healing target is no longer eligible.")
            if command.option_id == "unwilling":
                continuation.stage = "done"
                return [Event("healing_refused", caster.actor_id, target.actor_id, f"{target.label} declines {SPELLS[pending.spell_id].name}.")] + self._complete_action(state, caster, [], dice=dice)
            healing = (
                soothe_roll(dice.draw) if pending.spell_id == "soothe"
                else heal_roll(
                    continuation.spell_actions, dice.draw,
                    die_sides=self._heal_die_sides(caster),
                )
            )
            events = self._apply_blood_magic(state, caster, continuation) if pending.spell_id == "heal" else []
            events.extend(self._apply_healing(state, caster, target, healing.total, healing.rolls, continuation))
            if pending.spell_id == "soothe":
                state.active_effects[:] = [
                    effect for effect in state.active_effects
                    if not (
                        effect.kind == "soothe"
                        and effect.source_actor_id == caster.actor_id
                        and effect.target_actor_id == target.actor_id
                    )
                ]
                state.active_effects.append(ActiveSpellEffect(
                    effect_id=f"soothe:{caster.actor_id}:{target.actor_id}:{state.next_choice_id}",
                    kind="soothe",
                    source_actor_id=caster.actor_id,
                    target_actor_id=target.actor_id,
                    value=2,
                    expires_at_source_start=state.actor_start_counts.get(caster.actor_id, 0) + 10,
                    expires_at_world_time=state.world_time_seconds + 60,
                ))
                events.append(Event(
                    "soothe_protection_applied",
                    caster.actor_id,
                    target.actor_id,
                    f"{target.label} gains +2 status to saves against mental effects for 1 minute.",
                ))
            continuation.stage = "done"
            return events + self._complete_action(state, caster, [], dice=dice)

        if pending.kind == "divine_grace":
            continuation = pending.continuation
            caster = state.creatures.get(pending.actor_id or "")
            target = state.creatures.get(pending.target_id or "")
            if continuation is None or caster is None or target is None:
                raise _Rejected("The Divine Grace save is no longer available.")
            if command.option_id == "use":
                if (
                    not target.reaction_available
                    or target.unconscious
                    or target.dead
                    or "divine_grace" not in get_definition(target.definition_id).abilities
                ):
                    raise _Rejected("Divine Grace is no longer available.")
                target.reaction_available = False
                continuation.divine_grace_used = True
                events = [Event(
                    "divine_grace_used", target.actor_id, caster.actor_id,
                    f"{target.label} uses Divine Grace for +2 circumstance to this spell save.",
                )]
            else:
                events = [Event(
                    "divine_grace_declined", target.actor_id, caster.actor_id,
                    f"{target.label} declines Divine Grace; the reaction remains available.",
                )]
            continuation.divine_grace_checked = True
            return events + self._resolve_cast(state, dice, continuation)

        if pending.kind == "guidance_use":
            continuation = pending.continuation
            effect = next((item for item in state.active_effects if item.effect_id == pending.effect_id), None)
            if continuation is None or effect is None:
                raise _Rejected("The Guidance effect is no longer available.")
            events: list[Event] = []
            if command.option_id == "use":
                state.active_effects.remove(effect)
                state.guidance_immunity_deadlines[effect.target_actor_id] = (
                    state.world_time_seconds + 600
                )
                state.guidance_immunities[effect.target_actor_id] = state.round_number + 600
                continuation.guidance_bonus = 1
                events.append(Event("guidance_used", effect.source_actor_id, effect.target_actor_id, "Guidance is consumed for +1 status to this check; the target becomes immune for one hour."))
            else:
                events.append(Event("guidance_kept", effect.source_actor_id, effect.target_actor_id, "Guidance is retained for a later eligible check."))
            continuation.guidance_checked = True
            if pending.check_kind == "weapon_attack":
                attacker = state.creatures[continuation.actor_id]
                target = state.creatures[continuation.target_id or ""]
                attack = self._find_attack(state, attacker, continuation.attack_id)
                if attack is None:
                    raise _Rejected("The guided Strike is no longer available.")
                context = ActionContinuation(
                    kind="reaction_strike" if pending.is_reaction else ("ranged_strike" if "ranged" in attack.traits else "strike"),
                    actor_id=attacker.actor_id, target_id=target.actor_id,
                    attack_id=attack.attack_id, damage_type=continuation.damage_type,
                    item_id=continuation.item_id,
                    nonlethal=continuation.nonlethal, attack_penalty=continuation.attack_penalty,
                    attack_count=continuation.attack_count,
                    attack_actions_cost=continuation.attack_actions_cost,
                    attack_count_cost=continuation.attack_count_cost,
                    damage_bonus_dice=continuation.damage_bonus_dice,
                    ranged_penalty=continuation.ranged_penalty,
                    guidance_bonus=continuation.guidance_bonus,
                    feint_off_guard_applied=continuation.feint_off_guard_applied,
                    attack_target_off_guard=continuation.attack_target_off_guard,
                    nimble_dodge_decided=continuation.nimble_dodge_decided,
                    nimble_dodge_used=continuation.nimble_dodge_used,
                    guidance_checked=True,
                    concealment_checked=continuation.concealment_checked,
                    sure_strike_checked=continuation.sure_strike_checked,
                    sure_strike_used=continuation.sure_strike_used,
                    use_intelligence=continuation.use_intelligence,
                )
                events.extend(self._roll_strike(state, dice, attacker, target, attack, context, parent=continuation.parent_continuation))
            else:
                events.extend(self._resolve_cast(state, dice, continuation))
            return events

        if pending.kind == "persistent_recovery":
            actor = state.creatures.get(pending.actor_id or "")
            hero_owner = state.creatures.get(pending.owner_actor_id or "")
            continuation = pending.continuation
            check = pending.check
            effect = next((item for item in state.persistent_effects if item.effect_id == pending.effect_id), None)
            if actor is None or hero_owner is None or continuation is None or check is None or effect is None:
                raise _Rejected("The pending persistent recovery is no longer available.")
            if command.option_id == "spend_hero_point":
                if hero_owner.hero_points < 1:
                    raise _Rejected("The recovery check owner no longer has a Hero Point.")
                hero_owner.hero_points -= 1
                die = dice.draw(20)
                check = resolve_check(die, 0, 15)
                events = [Event("hero_reroll", hero_owner.actor_id, actor.actor_id, f"Persistent recovery reroll: d20 {die} vs DC 15; {check.degree.label().lower()}.", check=check)]
            else:
                events = [Event("check_kept", hero_owner.actor_id, actor.actor_id, "Kept the persistent recovery check.", check=check)]
            events.extend(self._finish_persistent_recovery_check(state, dice, actor, continuation, effect, check))
            if state.pending_choice is None:
                parent = continuation.parent_continuation
                familiar_owner = self._familiar_hero_owner(state, actor)
                if familiar_owner is not None and hero_owner is familiar_owner and parent is None:
                    self._source_turn_end(state, actor)
                    self._finish_if_team_defeated(state)
                    if state.in_progress and not familiar_owner.unconscious and not familiar_owner.dead:
                        self._begin_turn(state, dice, familiar_owner, events)
                    return events
                if parent is None or parent.kind not in {"persistent_end_turn", "persistent_incapacitated_turn"}:
                    raise _Rejected("Persistent recovery has no saved end-turn continuation.")
                if parent.kind == "persistent_incapacitated_turn":
                    events.extend(self._advance_after_incapacitated_turn(state, dice, skip_persistent=True))
                    return events
                try:
                    early_text, discarded_text = (parent.stage or "").split(":")
                    early, discarded = bool(int(early_text)), int(discarded_text)
                except (TypeError, ValueError) as error:
                    raise _Rejected("Persistent recovery has invalid end-turn progress.") from error
                events.extend(self._finish_end_turn(state, dice, actor, early=early, discarded=discarded))
            return events

        if pending.kind in {"spell_attack_hero_reroll", "spell_save_hero_reroll"}:
            check = pending.check
            continuation = pending.continuation
            owner = state.creatures[pending.owner_actor_id or ""]
            caster = state.creatures[pending.actor_id or ""]
            target = state.creatures[pending.target_id or ""]
            if check is None or continuation is None:
                raise _Rejected("The pending spell check is incomplete.")
            if command.option_id == "spend_hero_point":
                if owner.hero_points < 1:
                    raise _Rejected("The check owner no longer has a Hero Point.")
                owner.hero_points -= 1
                die = dice.draw(20)
                check = replace(resolve_check(
                    die, check.modifier, check.dc,
                    attack_id=check.attack_id, attack_count=check.attack_count,
                    map_penalty=check.map_penalty, traits=check.traits,
                ), modifier_breakdown=check.modifier_breakdown)
                events = [Event("hero_reroll", owner.actor_id, target.actor_id, f"Hero Point reroll: d20 {die} + {check.modifier} = {check.total} vs DC {check.dc}; {check.degree.label().lower()}.", check=check)]
            else:
                events = [Event("check_kept", owner.actor_id, target.actor_id, "Kept the original spell check.", check=check)]
            if pending.kind == "spell_attack_hero_reroll":
                if pending.spell_id == "telekinetic_projectile":
                    events.extend(self._resolve_telekinetic_projectile_result(state, dice, caster, target, check, continuation))
                elif pending.spell_id in {"ignition", "gouging_claw"}:
                    events.extend(self._resolve_persistent_attack_spell_result(state, dice, caster, target, check, continuation))
                elif pending.spell_id == "tangle_vine":
                    events.extend(self._resolve_tangle_vine_result(state, dice, caster, target, check, continuation))
                else:
                    events.extend(self._resolve_divine_lance_result(state, dice, caster, target, check, continuation))
            else:
                events.extend(self._resolve_spell_save_result(
                    state, dice, caster, target, check, continuation,
                ))
            return events

        if pending.kind == "attack_hero_reroll":
            actor = state.creatures[pending.actor_id or ""]
            target = state.creatures[pending.target_id or ""]
            attack = self._find_attack(state, actor, pending.attack_id)
            assert attack is not None
            if command.option_id == "spend_hero_point":
                actor.hero_points -= 1
                die = dice.draw(20)
                original = pending.check
                assert original is not None
                check = replace(resolve_check(
                    die,
                    original.modifier,
                    original.dc,
                    attack_id=attack.attack_id,
                    attack_count=pending.attack_count,
                    map_penalty=pending.attack_penalty,
                    traits=attack.traits,
                ), modifier_breakdown=original.modifier_breakdown)
                events = [Event("hero_reroll", actor.actor_id, target.actor_id, f"Hero Point reroll: d20 {die} + {check.modifier} = {check.total} vs AC {check.dc}; {check.degree.label().lower()}.", check=check)]
            else:
                assert pending.check is not None
                check = pending.check
                events = [Event("check_kept", actor.actor_id, target.actor_id, "Kept the original Strike check.", check=check)]
            events.extend(self._resolve_attack_result(
                state, dice, actor, target, attack, check,
                damage_type=pending.damage_type or attack.damage_type,
                nonlethal=pending.nonlethal,
                damage_bonus_dice=pending.damage_bonus_dice,
                attack_target_off_guard=pending.attack_target_off_guard,
                is_reaction=pending.is_reaction,
                continuation=(
                    None
                    if (
                        pending.continuation is not None
                        and pending.continuation.hunter_aim_intent is not None
                    )
            else pending.continuation
                ),
                item_id=pending.item_id,
                bomber_only_primary_splash=pending.damage_context == "bomber_only_primary",
            ))
            from .skill_actions import consume_overextending_feint_on_attack

            state.overextending_feint_effects = list(consume_overextending_feint_on_attack(
                tuple(state.overextending_feint_effects),
                attacker_id=actor.actor_id,
                target_id=target.actor_id,
                actor_end_counts=state.actor_end_counts,
            ))
            return events

        if pending.kind == "recovery_start_heroic":
            actor = state.creatures[pending.actor_id or ""]
            familiar_owner = self._familiar_recovery_owner(state, pending)
            if familiar_owner is not None:
                if command.option_id == "heroic_recovery":
                    transition = heroic_recovery(self._health_state(actor), familiar_owner.hero_points)
                    familiar_owner.hero_points -= transition.hero_points_spent
                    events = [Event("heroic_recovery", familiar_owner.actor_id, actor.actor_id, f"{familiar_owner.label} spends all Hero Points to stabilize {actor.label} at 0 HP.")]
                    self._finish_familiar_recovery(state, dice, familiar_owner, actor, transition, events)
                    if state.in_progress and not familiar_owner.unconscious and not familiar_owner.dead:
                        self._begin_turn(state, dice, familiar_owner, events)
                    return events
                die = dice.draw(20)
                check = resolve_check(die, 0, 10 + actor.dying)
                transition = recovery_check(
                    self._health_state(actor), check.degree.name.lower(),
                    hero_points=familiar_owner.hero_points,
                )
                self._set_pending(
                    state,
                    kind="recovery_hero_reroll",
                    owner_actor_id=familiar_owner.actor_id,
                    prompt=f"{familiar_owner.label} may keep {actor.label}'s recovery check or spend 1 Hero Point to reroll.",
                    options=(ChoiceOption("keep", "Keep result"), ChoiceOption("spend_hero_point", "Spend 1 Hero Point and reroll")),
                    details=(f"Original: d20 {die} vs DC {check.dc}.",),
                    actor_id=actor.actor_id,
                    target_id=actor.actor_id,
                    check=check,
                    health_normal=transition,
                    transition_kind="recovery",
                )
                return []
            if command.option_id == "heroic_recovery":
                transition = heroic_recovery(self._health_state(actor), actor.hero_points)
                actor.hero_points -= transition.hero_points_spent
                self._apply_health_transition(state, actor, transition)
                events = [Event("heroic_recovery", actor.actor_id, actor.actor_id, f"{actor.label} spends all Hero Points and stabilizes at 0 HP.")]
                events.extend(self._advance_after_incapacitated_turn(state, dice))
                return events
            events: list[Event] = []
            self._roll_recovery(state, dice, actor, events)
            if state.pending_choice is None:
                events.extend(self._advance_after_incapacitated_turn(state, dice))
            return events

        if pending.kind == "recovery_hero_reroll":
            actor = state.creatures[pending.actor_id or ""]
            familiar_owner = self._familiar_recovery_owner(state, pending)
            if familiar_owner is not None:
                if command.option_id == "spend_hero_point":
                    familiar_owner.hero_points -= 1
                    die = dice.draw(20)
                    dc = pending.check.dc if pending.check is not None else 10 + actor.dying
                    check = resolve_check(die, 0, dc)
                    transition = recovery_check(
                        self._health_state(actor), check.degree.name.lower(),
                        hero_points=familiar_owner.hero_points,
                    )
                    events = [Event("hero_reroll", familiar_owner.actor_id, actor.actor_id, f"{familiar_owner.label} rerolls {actor.label}'s recovery: d20 {die} vs DC {dc}; {check.degree.label().lower()}.", check=check)]
                else:
                    check = pending.check
                    transition = pending.health_normal
                    assert check is not None and isinstance(transition, HealthTransition)
                    events = [Event("check_kept", familiar_owner.actor_id, actor.actor_id, "Kept the familiar's recovery result.", check=check)]
                if (
                    transition.dying_increased
                    and not transition.state.dead
                    and transition.heroic_recovery_available
                    and transition.heroic_recovery_option
                ):
                    self._set_pending(
                        state,
                        kind="recovery_heroic_increase",
                        owner_actor_id=familiar_owner.actor_id,
                        prompt=f"{actor.label}'s recovery check would increase dying; choose normal result or Heroic Recovery.",
                        options=(ChoiceOption("normal", "Apply recovery result"), ChoiceOption("heroic_recovery", "Heroic Recovery (spend all Hero Points)")),
                        details=(f"Dying {actor.dying}; recovery result: {transition.state.dying}.",),
                        actor_id=actor.actor_id,
                        target_id=actor.actor_id,
                        health_normal=transition,
                        health_heroic=transition.heroic_recovery_option,
                        transition_kind="recovery",
                    )
                    return events
                self._finish_familiar_recovery(state, dice, familiar_owner, actor, transition, events)
                if state.in_progress and not familiar_owner.unconscious and not familiar_owner.dead:
                    self._begin_turn(state, dice, familiar_owner, events)
                return events
            if command.option_id == "spend_hero_point":
                actor.hero_points -= 1
                die = dice.draw(20)
                dc = pending.check.dc if pending.check is not None else 10 + actor.dying
                check = resolve_check(die, 0, dc)
                transition = recovery_check(self._health_state(actor), check.degree.name.lower(), hero_points=actor.hero_points)
                events = [Event("hero_reroll", actor.actor_id, actor.actor_id, f"Recovery reroll: d20 {die} vs DC {dc}; {check.degree.label().lower()}.", check=check)]
            else:
                check = pending.check
                transition = pending.health_normal
                assert check is not None and isinstance(transition, HealthTransition)
                events = [Event("check_kept", actor.actor_id, actor.actor_id, "Kept the original recovery check.", check=check)]
            if transition.dying_increased and transition.heroic_recovery_available and transition.heroic_recovery_option:
                self._set_pending(
                    state,
                    kind="recovery_heroic_increase",
                    owner_actor_id=actor.actor_id,
                    prompt=f"{actor.label}'s recovery check would increase dying; choose normal result or Heroic Recovery.",
                    options=(ChoiceOption("normal", "Apply recovery result"), ChoiceOption("heroic_recovery", "Heroic Recovery (spend all Hero Points)")),
                    details=(f"Dying {actor.dying}; recovery result: {transition.state.dying}.",),
                    actor_id=actor.actor_id,
                    health_normal=transition,
                    health_heroic=transition.heroic_recovery_option,
                    transition_kind="recovery",
                )
                return events
            self._apply_health_transition(state, actor, transition)
            recovery_text = (
                f"{actor.label} dies from the recovery check."
                if actor.dead else f"Recovery check resolves; dying {actor.dying}, wounded {actor.wounded}."
            )
            events.append(Event("recovery", actor.actor_id, actor.actor_id, recovery_text))
            if actor.unconscious or actor.dead:
                events.extend(self._advance_after_incapacitated_turn(state, dice))
            else:
                actor.actions_remaining = 3
                definition = get_definition(actor.definition_id)
                actor.reaction_available = bool({"reactive_strike", "shield_block", "shield_cantrip", "counter_performance", "no_escape", "reactive_shield"} & set(definition.abilities)) or bool({"Nimble Dodge", "Reactive Shield", "You're Next"} & set(definition.feats)) or "investigator_on_the_case" in definition.abilities
                events.append(Event("turn_started", actor.actor_id, None, f"{actor.label} regains 3 actions and 1 reaction."))
            return events

        if pending.kind == "recovery_heroic_increase":
            actor = state.creatures[pending.actor_id or ""]
            familiar_owner = self._familiar_recovery_owner(state, pending)
            if familiar_owner is not None:
                transition = pending.health_heroic if command.option_id == "heroic_recovery" else pending.health_normal
                assert isinstance(transition, HealthTransition)
                if command.option_id == "heroic_recovery":
                    familiar_owner.hero_points -= transition.hero_points_spent
                events = [Event("heroic_recovery" if command.option_id == "heroic_recovery" else "familiar_recovery", familiar_owner.actor_id, actor.actor_id, f"Familiar recovery choice applied; dying {transition.state.dying}.")]
                self._finish_familiar_recovery(state, dice, familiar_owner, actor, transition, events)
                if state.in_progress and not familiar_owner.unconscious and not familiar_owner.dead:
                    self._begin_turn(state, dice, familiar_owner, events)
                return events
            transition = pending.health_heroic if command.option_id == "heroic_recovery" else pending.health_normal
            assert isinstance(transition, HealthTransition)
            if command.option_id == "heroic_recovery":
                actor.hero_points -= transition.hero_points_spent
            self._apply_health_transition(state, actor, transition)
            events = [Event("heroic_recovery" if command.option_id == "heroic_recovery" else "recovery", actor.actor_id, actor.actor_id, f"Health choice applied; dying {actor.dying}, wounded {actor.wounded}.")]
            if actor.unconscious or actor.dead:
                events.extend(self._advance_after_incapacitated_turn(state, dice))
            else:
                actor.actions_remaining = 3
                definition = get_definition(actor.definition_id)
                actor.reaction_available = bool({"reactive_strike", "shield_block", "shield_cantrip", "counter_performance", "no_escape", "reactive_shield"} & set(definition.abilities)) or bool({"Nimble Dodge", "Reactive Shield", "You're Next"} & set(definition.feats)) or "investigator_on_the_case" in definition.abilities
                events.append(Event("turn_started", actor.actor_id, None, f"{actor.label} regains 3 actions and 1 reaction."))
            return events

        if pending.kind == "heroic_recovery_damage":
            target = state.creatures[pending.target_id or ""]
            hero_owner = self._familiar_hero_owner(state, target) or target
            transition = pending.health_heroic if command.option_id == "heroic_recovery" else pending.health_normal
            assert isinstance(transition, HealthTransition)
            if command.option_id == "heroic_recovery":
                hero_owner.hero_points -= transition.hero_points_spent
            self._apply_health_transition(state, target, transition)
            if pending.transition_kind == "familiar_persistent_damage":
                events = [Event(
                    "heroic_recovery" if command.option_id == "heroic_recovery" else "health_changed",
                    hero_owner.actor_id,
                    target.actor_id,
                    f"{target.label}: HP {target.hp}, dying {target.dying}, wounded {target.wounded}.",
                )]
                self._source_turn_end(state, target)
                self._finish_if_team_defeated(state)
                if state.in_progress and not hero_owner.unconscious and not hero_owner.dead:
                    self._begin_turn(state, dice, hero_owner, events)
                return events
            if pending.damage_resolution is not None:
                if pending.damage_result is None:
                    raise _Rejected("The pending damage result is incomplete.")
                outcome = _DamageHealthResult(
                    damage=pending.damage_result,
                    temporary_hp_absorbed=pending.temporary_hp_absorbed,
                    remaining_hp_damage=pending.remaining_hp_damage,
                    defeated=target.defeated,
                    shield_block=pending.damage_resolution.shield_block_record,
                )
                events = self._finish_damage_application(
                    state,
                    dice,
                    pending.damage_resolution,
                    outcome,
                    resumed=True,
                    health_choice=command.option_id,
                )
                continuation = pending.continuation
                if continuation is not None and continuation.kind == "venom_end_turn":
                    parent = continuation.parent_continuation
                    if parent is None or parent.kind != "persistent_end_turn":
                        raise _Rejected("Giant Centipede Venom damage has no saved end-turn continuation.")
                    try:
                        early_text, discarded_text = (parent.stage or "").split(":", 1)
                        early, discarded = bool(int(early_text)), int(discarded_text)
                    except (TypeError, ValueError) as error:
                        raise _Rejected("Giant Centipede Venom end-turn progress is invalid.") from error
                    events.extend(self._finish_end_turn(state, dice, target, early=early, discarded=discarded))
                return events
            events = []
            if pending.damage_result is not None and pending.damage_text:
                events.append(Event(
                    "damage", pending.actor_id, target.actor_id, pending.damage_text,
                    damage=pending.damage_result,
                    temporary_hp_absorbed=pending.temporary_hp_absorbed,
                    remaining_hp_damage=pending.remaining_hp_damage,
                ))
            events.append(Event("heroic_recovery" if command.option_id == "heroic_recovery" else "health_changed", pending.actor_id, target.actor_id, f"{target.label}: HP {target.hp}, dying {target.dying}, wounded {target.wounded}."))
            if pending.spell_id == "void_warp" and pending.damage_context and pending.damage_context.startswith("enfeebled:") and not target.dead:
                value = int(pending.damage_context.split(":", 1)[1])
                caster = state.creatures[pending.actor_id or ""]
                self._apply_enfeebled(state, caster, target, value)
                events.append(Event("effect_applied", caster.actor_id, target.actor_id, f"{target.label} is enfeebled {value} until {caster.label}'s next turn."))
            self._finish_if_team_defeated(state)
            if target.defeated:
                events.append(Event("defeated", pending.actor_id, target.actor_id, f"{target.label} is defeated."))
            if pending.continuation is not None and state.in_progress:
                events.extend(self._resume_continuation(state, dice, pending.continuation, critical=pending.attack_critical))
            elif not pending.is_reaction:
                actor = state.creatures[pending.actor_id or ""]
                if (
                    state.in_progress
                    and actor.actions_remaining == 0
                    and state.pending_choice is None
                    and not self._free_devise_target_ids(state, actor)
                ):
                    events.extend(self._end_turn(state, actor, early=False, dice=dice))
            return events

        raise _Rejected(f"Unsupported pending choice kind {pending.kind!r}.")

    def _advance_after_incapacitated_turn(self, state, dice, *, skip_persistent: bool = False):
        actor = state.creatures[state.initiative_order[state.active_index]]
        actor.actions_remaining = 0
        actor.reaction_available = False
        events: list[Event] = []
        if not skip_persistent:
            events.extend(self._resolve_persistent_damage_end_turn(state, dice, actor))
            if state.pending_choice is not None:
                state.pending_choice.continuation.parent_continuation = ActionContinuation(
                    kind="persistent_incapacitated_turn", actor_id=actor.actor_id,
                )
                return events
        self._source_turn_end(state, actor)
        self._finish_if_team_defeated(state)
        if not state.in_progress:
            return events
        for _ in range(len(state.initiative_order)):
            next_index = (state.active_index + 1) % len(state.initiative_order)
            if next_index == 0:
                state.round_number += 1
                state.world_time_seconds = (
                    state.encounter_start_seconds + (state.round_number - 1) * 6
                )
                self._refresh_all_barbarians(state)
            state.active_index = next_index
            next_actor = state.creatures[state.initiative_order[next_index]]
            self._source_turn_start(state, next_actor)
            if next_actor.defeated:
                self._finish_if_team_defeated(state)
                if not state.in_progress:
                    break
                continue
            next_actor.strikes_this_turn = 0
            next_actor.diagonals_this_turn = 0
            if self._begin_turn(state, dice, next_actor, events):
                break
        else:
            events.append(Event("turn_paused", None, None, "No conscious combatant can take a supported turn."))
        return events

    def _continue_initiative_initialization(self, state: EncounterState) -> None:
        if state.initiative_finalized:
            return
        setup = get_setup(state.setup_id)
        decided = state.initiative_hero_decided
        assert decided is not None
        for placement in setup.placements:
            actor = state.creatures[placement.actor_id]
            definition = get_definition(actor.definition_id)
            if actor.health_mode is HealthMode.PC and actor.hero_points > 0 and actor.actor_id not in decided:
                initiative_skill = state.initiative_skills.get(actor.actor_id, "perception")
                initiative_modifier = self._initiative_modifier_for_state(
                    state, actor, definition, initiative_skill,
                    weather_perception_penalty=(
                        0 if "storm_born" in definition.abilities
                        else get_setup(state.setup_id).weather_perception_circumstance_penalty
                    ),
                )
                context = state.initiative_contexts.get(actor.actor_id)
                context_detail = f" ({context})" if context else ""
                initiative_details = (
                    f"Original: d20 {actor.initiative - initiative_modifier} + {initiative_modifier} = {actor.initiative}.",
                )
                if initiative_skill != "perception" or context:
                    initiative_details = (
                        f"Initiative: {initiative_skill.title()}{context_detail}.",
                        *initiative_details,
                    )
                self._set_pending(
                    state,
                    kind="initiative_hero_reroll",
                    owner_actor_id=actor.actor_id,
                    prompt=f"{actor.label} may keep initiative or spend 1 Hero Point to reroll.",
                    options=(ChoiceOption("keep", "Keep initiative"), ChoiceOption("spend_hero_point", "Spend 1 Hero Point and reroll")),
                    details=initiative_details,
                    actor_id=actor.actor_id,
                    initiative_roll=actor.initiative - initiative_modifier,
                    initiative_modifier=initiative_modifier,
                )
                return
            if self._quick_tempered_eligible(state, actor) and actor.actor_id not in state.quick_tempered_decided:
                from .barbarian import RageModeChoice

                self._set_pending(
                    state,
                    kind="family_action",
                    owner_actor_id=actor.actor_id,
                    prompt=f"{actor.label} may use Quick-Tempered to Rage before initiative is finalized.",
                    options=(ChoiceOption("accept", "Use Quick-Tempered"), ChoiceOption("decline", "Decline")),
                    details=("Quick-Tempered is a free Rage action at initiative.",),
                    actor_id=actor.actor_id,
                    continuation=ActionContinuation(
                        kind="family_action", actor_id=actor.actor_id, mode="quick_tempered"
                    ),
                    family_id="martial",
                    procedure_id="barbarian:quick_tempered",
                    barbarian_choice=RageModeChoice(
                        "barbarian:quick_tempered", actor.actor_id, "QuickTempered"
                    ),
                )
                return
        self._prepare_initiative_order(state)
        self._continue_tie_choices(state)

    def _quick_tempered_eligible(self, state: EncounterState, actor: CreatureState) -> bool:
        from .barbarian import quick_tempered_eligible

        if (
            state.initiative_finalized
            or actor.health_mode is not HealthMode.PC
            or actor.unconscious or actor.dead or actor.defeated
            or actor.barbarian_state is None or actor.barbarian_state.rage is not None
        ):
            return False
        definition = get_definition(actor.definition_id)
        if definition.class_name != "Barbarian" or definition.armor_category is None:
            return False
        fatigued = any(
            effect.target_actor_id == actor.actor_id and effect.kind == "fatigued"
            for effect in state.condition_effects
        )
        carried = set(actor.held_items) | set(actor.worn_items) | set(actor.stowed_items)
        bulk_by_item = dict(definition.carried_item_bulk)
        carried_bulk = sum(bulk_by_item[item_id] for item_id in carried if item_id in bulk_by_item)
        strength = dict(definition.ability_modifiers).get("strength")
        if type(strength) is not int:
            return False
        encumbered = carried_bulk > max(0, 5 + strength)
        return quick_tempered_eligible(
            initiative_trigger=True,
            fatigued=fatigued,
            encumbered=encumbered,
            wearing_heavy_armor=definition.armor_category == "heavy",
            is_raging=actor.barbarian_state.rage is not None,
        )

    def _validate_quick_tempered_offer(self, state: EncounterState, pending: PendingChoice) -> None:
        from .barbarian import RageModeChoice

        actor = state.creatures.get(pending.actor_id or "")
        continuation = pending.continuation
        choice = pending.barbarian_choice
        if (
            state.initiative_finalized
            or pending.family_id != "martial"
            or pending.owner_actor_id != pending.actor_id
            or actor is None
            or continuation is None
            or continuation.kind != "family_action"
            or continuation.actor_id != actor.actor_id
            or not isinstance(choice, RageModeChoice)
            or choice.procedure_id != "barbarian:quick_tempered"
            or choice.actor_id != actor.actor_id
            or choice.command_kind != "QuickTempered"
            or choice.mode_id is not None
            or choice.temporary_hp_choice is not None
            or actor.actor_id in state.quick_tempered_decided
            or not self._quick_tempered_eligible(state, actor)
            or (
                actor.hero_points > 0
                and actor.actor_id not in state.initiative_hero_decided
            )
            or pending.options != (
                ChoiceOption("accept", "Use Quick-Tempered"),
                ChoiceOption("decline", "Decline"),
            )
            or state.initiative_order
            or any(
                creature.actions_remaining or creature.strikes_this_turn or creature.diagonals_this_turn
                for creature in state.creatures.values()
            )
        ):
            raise ValueError("save has an invalid Quick-Tempered initiative offer")

    def _prepare_initiative_order(self, state: EncounterState) -> None:
        setup = get_setup(state.setup_id)
        setup_index = {placement.actor_id: index for index, placement in enumerate(setup.placements)}
        grouped: dict[int, list[str]] = {}
        for actor_id, creature in state.creatures.items():
            if get_definition(creature.definition_id).initiative_exempt:
                continue
            grouped.setdefault(creature.initiative, []).append(actor_id)
        order: list[str] = []
        tie_groups: list[tuple[str, ...]] = []
        for rank in sorted(grouped, reverse=True):
            ids = grouped[rank]
            pc_ids = [actor_id for actor_id in ids if state.creatures[actor_id].health_mode is HealthMode.PC]
            if len(pc_ids) > 1:
                tie_groups.append(tuple(sorted(pc_ids, key=lambda actor_id: setup_index[actor_id])))
            has_pc = bool(pc_ids)
            ids.sort(
                key=lambda actor_id: (
                    0 if has_pc and state.creatures[actor_id].health_mode is not HealthMode.PC
                    and any(state.creatures[pc].team != state.creatures[actor_id].team for pc in pc_ids)
                    else 1,
                    setup_index[actor_id],
                )
            )
            order.extend(ids)
        state.initiative_order = order
        state.initiative_tie_groups = tie_groups
        state.initiative_tie_group_index = 0
        state.initiative_tie_orders = {}

    def _continue_tie_choices(self, state: EncounterState) -> None:
        groups = state.initiative_tie_groups or []
        index = state.initiative_tie_group_index
        if index < len(groups):
            group = groups[index]
            selected = (state.initiative_tie_orders or {}).get(index, [])
            remaining = tuple(actor_id for actor_id in group if actor_id not in selected)
            if len(remaining) > 1:
                self._present_initiative_tie(state, index, remaining, tuple(selected))
                return
            if remaining:
                (state.initiative_tie_orders or {}).setdefault(index, []).extend(remaining)
            self._apply_initiative_tie_order(state, index)
            state.initiative_tie_group_index += 1
            self._continue_tie_choices(state)
            return
        state.initiative_finalized = True
        state.active_index = 0
        if state.initiative_order:
            active = state.creatures[state.initiative_order[0]]
            state.actor_start_counts[active.actor_id] = max(1, state.actor_start_counts.get(active.actor_id, 0))
            state.active_effects = [
                replace(
                    effect,
                    expires_at_source_start=state.actor_start_counts.get(effect.source_actor_id, 0) + 1,
                )
                if effect.kind.startswith("alchemy_") and effect.source_actor_id in state.creatures
                else effect
                for effect in state.active_effects
            ]
            for creature in state.creatures.values():
                if not creature.defeated:
                    definition = get_definition(creature.definition_id)
                    creature.reaction_available = bool({"reactive_strike", "shield_block", "shield_cantrip", "counter_performance", "no_escape", "reactive_shield"} & set(definition.abilities)) or bool({"Nimble Dodge", "Reactive Shield", "You're Next"} & set(definition.feats)) or "investigator_on_the_case" in definition.abilities
            active.actions_remaining = 3

    def _apply_initiative_tie_order(self, state, index: int) -> None:
        group = (state.initiative_tie_groups or [])[index]
        slots = [i for i, actor_id in enumerate(state.initiative_order) if actor_id in group]
        current_group = [state.initiative_order[i] for i in slots]
        pc_order = (state.initiative_tie_orders or {}).get(index, list(group))
        iterator = iter(pc_order)
        replaced = [next(iterator) if actor_id in group else actor_id for actor_id in current_group]
        for slot, actor_id in zip(slots, replaced):
            state.initiative_order[slot] = actor_id

    def _present_initiative_tie(self, state, group_index, candidates, selected) -> None:
        self._set_pending(
            state,
            kind="initiative_tie",
            owner_actor_id=None,
            prompt="Choose the next tied PC in initiative order.",
            options=tuple(ChoiceOption(actor_id, state.creatures[actor_id].label) for actor_id in candidates),
            details=("Tied PCs choose their order.",),
            tie_candidates=candidates,
            tie_selected=selected,
        )
        # Group index is persisted as part of the state; the choice frame also
        # includes candidates so stale UI submissions cannot reorder a group.
        state.initiative_tie_group_index = group_index

    @staticmethod
    def _set_pending(state, *, kind, owner_actor_id, prompt, options, details=(), **values) -> None:
        state.pending_choice = PendingChoice(
            choice_id=state.next_choice_id,
            kind=kind,
            owner_actor_id=owner_actor_id,
            prompt=prompt,
            options=options,
            details=details,
            **values,
        )
        state.next_choice_id += 1

    def _family_handler_module(self, family_id: str):
        """Return one of the fixed family modules; this is not extensible registration."""
        if family_id == "martial":
            try:
                from . import family_martial
            except ModuleNotFoundError as error:
                if error.name != f"{__package__}.family_martial":
                    raise
                return None
            return family_martial
        if family_id == "casting":
            try:
                from . import family_casting
            except ModuleNotFoundError as error:
                if error.name != f"{__package__}.family_casting":
                    raise
                return None
            return family_casting
        if family_id == "items":
            try:
                from . import family_items
            except ModuleNotFoundError as error:
                if error.name != f"{__package__}.family_items":
                    raise
                return None
            return family_items
        if family_id == "minions":
            try:
                from . import family_minions
            except ModuleNotFoundError as error:
                if error.name != f"{__package__}.family_minions":
                    raise
                return None
            return family_minions
        return None

    def _run_family_action(
        self, state, dice, actor, command: FamilyCommand, *, quick_tempered_trigger: bool = False,
        youre_next_trigger: bool = False,
    ) -> list[Event]:
        if type(command).__module__.endswith(".skill_actions"):
            from . import skill_actions
            from .skill_content import DEMORALIZE, ESCAPE, GRAPPLE, QUICK_JUMP, TRIP, TUMBLE_THROUGH

            if type(command) is skill_actions.Trip:
                content = TRIP
            elif type(command) is skill_actions.Grapple:
                content = GRAPPLE
            elif type(command) is skill_actions.Escape:
                content = ESCAPE
            elif type(command) is skill_actions.Demoralize:
                content = DEMORALIZE
            elif type(command) is skill_actions.TumbleThrough:
                content = TUMBLE_THROUGH
            elif type(command) is skill_actions.QuickJump:
                content = QUICK_JUMP
            else:
                content = None
            if content is not None:
                self._require_action_permitted(state, actor, content.action_id, content.traits)
        handler = self._family_handler_module(command.family_id)
        if handler is None or not callable(getattr(handler, "handle_action", None)):
            raise _Unsupported(f"No {command.family_id!r} family action procedure is admitted.")
        context = FamilyProcedureContext(
            self, state, dice, actor, get_definition(actor.definition_id),
            command.family_id, command=command,
            quick_tempered_trigger=quick_tempered_trigger,
            youre_next_trigger=youre_next_trigger,
        )
        result = handler.handle_action(context)
        events = self._family_result_events(result, command.family_id)
        from .barbarian import Rage

        if (
            isinstance(command, Rage)
            and state.pending_choice is None
            and any(event.kind == "rage_started" for event in events)
        ):
            events = self._complete_action(state, actor, events, dice=dice)
        return events

    def _run_family_choice(self, state, dice, pending, command: Choose) -> list[Event]:
        if pending.procedure_id == "barbarian:quick_tempered":
            actor = state.creatures[pending.actor_id or ""]
            state.quick_tempered_decided.add(actor.actor_id)
            if command.option_id == "decline":
                events = [Event("quick_tempered_declined", actor.actor_id, None, f"{actor.label} declines Quick-Tempered.")]
            else:
                from .barbarian import QuickTempered

                state.quick_tempered_decided.discard(actor.actor_id)
                events = self._run_family_action(
                    state, dice, actor, QuickTempered(), quick_tempered_trigger=True
                )
                if state.pending_choice is not None:
                    return events
                if not any(event.kind == "rage_started" for event in events):
                    # A valid acceptance either starts Rage or pauses for one
                    # of its persisted mode/pool decisions.
                    raise _Rejected("Quick-Tempered did not begin Rage or offer a required choice.")
                state.quick_tempered_decided.add(actor.actor_id)
            self._continue_initiative_initialization(state)
            return events

        family_id = pending.family_id
        if family_id is None:
            raise _Rejected("The saved family choice has no family id.")
        handler = self._family_handler_module(family_id)
        if handler is None or not callable(getattr(handler, "handle_choice", None)):
            raise _Unsupported(f"No {family_id!r} family choice procedure is admitted.")
        actor = state.creatures.get(pending.actor_id or "")
        if actor is None:
            raise _Rejected("The saved family choice has no acting creature.")
        context = FamilyProcedureContext(
            self, state, dice, actor, get_definition(actor.definition_id), family_id,
            pending=pending, choice=command,
            quick_tempered_trigger=(
                getattr(pending.barbarian_choice, "command_kind", None) == "QuickTempered"
            ),
        )
        result = handler.handle_choice(context)
        events = self._family_result_events(result, family_id)
        origin = getattr(pending.barbarian_choice, "command_kind", None)
        if origin == "QuickTempered" and state.pending_choice is None:
            if not any(event.kind == "rage_started" for event in events):
                raise _Rejected("Quick-Tempered did not begin Rage or offer a required choice.")
            state.quick_tempered_decided.add(actor.actor_id)
            self._continue_initiative_initialization(state)
        elif origin == "Rage" and state.pending_choice is None and any(
            event.kind == "rage_started" for event in events
        ):
            events = self._complete_action(state, actor, events, dice=dice)
        return events

    def _validate_family_pending(self, state, pending) -> None:
        if (
            pending.family_id not in {"martial", "casting", "items", "minions"}
            or not pending.procedure_id
            or pending.actor_id not in state.creatures
            or pending.continuation is None
            or pending.continuation.actor_id != pending.actor_id
        ):
            raise ValueError("save has an incomplete family action choice")
        handler = self._family_handler_module(pending.family_id)
        if handler is None or not callable(getattr(handler, "validate_pending", None)):
            raise ValueError(f"save has a pending choice for unsupported {pending.family_id!r} family action")
        actor = state.creatures[pending.actor_id]
        quick_tempered_trigger = self._validate_rage_pending_origin(state, pending, actor)
        context = FamilyProcedureContext(
            self, state, self._dice.clone(), actor, get_definition(actor.definition_id),
            pending.family_id, pending=pending,
            quick_tempered_trigger=quick_tempered_trigger,
        )
        handler.validate_pending(context)

    def _validate_rage_pending_origin(self, state, pending, actor) -> bool:
        if pending.procedure_id not in {"barbarian:rage_mode", "barbarian:temporary_hp"}:
            return False
        from .barbarian import RageModeChoice

        choice = pending.barbarian_choice
        if not isinstance(choice, RageModeChoice) or choice.actor_id != actor.actor_id:
            raise ValueError("save has an invalid Rage choice origin")
        if choice.command_kind == "QuickTempered":
            if (
                state.initiative_finalized
                or actor.actor_id in state.quick_tempered_decided
                or not self._quick_tempered_eligible(state, actor)
                or pending.owner_actor_id != actor.actor_id
                or pending.continuation is None
                or pending.continuation.kind != "family_action"
                or pending.continuation.actor_id != actor.actor_id
            ):
                raise ValueError("save has a Quick-Tempered Rage choice outside its initiative trigger")
            return True
        if choice.command_kind == "Rage":
            if (
                not state.initiative_finalized
                or not state.initiative_order
                or not 0 <= state.active_index < len(state.initiative_order)
                or actor.actor_id != state.initiative_order[state.active_index]
                or actor.actions_remaining < 1
                or actor.unconscious or actor.dead
                or pending.owner_actor_id != actor.actor_id
            ):
                raise ValueError("save has an ordinary Rage choice outside the acting turn")
            return False
        raise ValueError("save has an unknown Rage choice origin")

    @staticmethod
    def _family_result_events(result, family_id: str) -> list[Event]:
        if result is None:
            raise _Unsupported(f"The {family_id!r} family procedure did not handle this action.")
        if not isinstance(result, FamilyProcedureResult):
            raise _Unsupported(f"The {family_id!r} family procedure returned an invalid result.")
        if result.rejection and result.unsupported:
            raise _Unsupported(f"The {family_id!r} family procedure returned conflicting failure reasons.")
        if result.rejection:
            raise _Rejected(result.rejection)
        if result.unsupported:
            raise _Unsupported(result.unsupported)
        if any(not isinstance(event, Event) for event in result.events):
            raise _Unsupported(f"The {family_id!r} family procedure returned an invalid event.")
        return list(result.events)

    @staticmethod
    def _choice_view(pending: PendingChoice | None) -> ChoiceView | None:
        if pending is None:
            return None
        return ChoiceView(
            pending.choice_id,
            pending.kind,
            pending.owner_actor_id,
            pending.prompt,
            pending.options,
            pending.details,
        )

    @staticmethod
    def _health_state(creature: CreatureState) -> HealthState:
        return HealthState(
            hp=creature.hp,
            max_hp=get_definition(creature.definition_id).hp,
            dying=creature.dying,
            wounded=creature.wounded,
            unconscious=creature.unconscious,
            dead=creature.dead,
        )

    def _propose_pc_damage(
        self,
        target: CreatureState,
        amount: int,
        *,
        damage_taken: int | None = None,
        attacker_critical: bool = False,
        target_critical_failure: bool = False,
        nonlethal: bool = False,
        hero_points: int | None = None,
    ) -> HealthTransition:
        """Use one PC-health path for weapon and spell damage outcomes."""
        return pc_damage(
            self._health_state(target),
            amount,
            damage_taken=damage_taken,
            attacker_critical=attacker_critical,
            target_critical_failure=target_critical_failure,
            nonlethal=nonlethal,
            hero_points=target.hero_points if hero_points is None else hero_points,
        )

    @staticmethod
    def _hero_reroll_check(dice: DiceSource, original):
        """Reroll the die while preserving the check's saved modifier context."""
        die = dice.draw(20)
        check = resolve_check(
            die,
            original.modifier,
            original.dc,
            attack_id=original.attack_id,
            attack_count=original.attack_count,
            map_penalty=original.map_penalty,
            traits=original.traits,
        )
        return replace(check, modifier_breakdown=original.modifier_breakdown)

    @staticmethod
    def _active_actor_id(state: EncounterState) -> str | None:
        if not state.in_progress or not state.initiative_finalized or state.pending_choice is not None or not state.initiative_order:
            return None
        return state.initiative_order[state.active_index]

    @staticmethod
    def _definition_abilities(actor: CreatureState) -> tuple[str, ...]:
        return get_definition(actor.definition_id).abilities

    @staticmethod
    def _familiar_owned_by(owner: CreatureState, familiar: CreatureState) -> bool:
        definition = get_definition(familiar.definition_id)
        return (
            definition.initiative_exempt
            and "witch_familiar" in definition.abilities
            and definition.familiar_owner_actor_id == owner.actor_id
        )

    @staticmethod
    def _familiar_can_share_space(familiar: CreatureState, other: CreatureState) -> bool:
        """Tiny familiar sharing is limited to a living ally's square."""
        return (
            get_definition(familiar.definition_id).size == "tiny"
            and familiar.team == other.team
            and not other.defeated and not other.unconscious and not other.dead
        )

    def _result(self, status: ResultStatus, message: str) -> ActionResult:
        return ActionResult(status, (), message, self.inspect())


class _Rejected(Exception):
    pass


class _Unsupported(Exception):
    pass


def _strike_modifier_breakdown(attack, map_penalty: int, nonlethal: bool, prone: bool) -> tuple[Modifier, ...]:
    return _strike_modifier_breakdown_full(attack, map_penalty, nonlethal, prone)


def _strike_modifier_breakdown_full(
    attack,
    map_penalty: int,
    nonlethal: bool,
    prone: bool,
    *,
    ranged_penalty: int = 0,
    guidance_bonus: int = 0,
    enfeebled: int = 0,
    attack_modifier_adjustment: int = 0,
    lethal_penalty_exempt: bool = False,
) -> tuple[Modifier, ...]:
    modifiers = [Modifier(
        attack.modifier + attack_modifier_adjustment
        - (enfeebled if attack.attack_attribute == "strength" else 0),
        "untyped",
        "printed attack modifier",
    )]
    if map_penalty:
        modifiers.append(Modifier(map_penalty, "untyped", "multiple attack penalty"))
    if ranged_penalty:
        modifiers.append(Modifier(ranged_penalty, "untyped", "range increment penalty"))
    if guidance_bonus:
        modifiers.append(Modifier(guidance_bonus, "status", "Guidance"))
    trait_default = "nonlethal" in attack.traits
    if nonlethal != trait_default and not lethal_penalty_exempt:
        modifiers.append(Modifier(-2, "circumstance", "nonlethal intent"))
    if prone:
        modifiers.append(Modifier(-2, "circumstance", "prone attack penalty"))
    return tuple(modifiers)


def _spell_attack_text(check, spell_name: str = "Divine Lance") -> str:
    dice_text = ", ".join(str(face) for face in check.dice) if check.dice else str(check.die)
    return (
        f"{spell_name} attack: d20 {dice_text} + {check.modifier} = {check.total} "
        f"vs AC {check.dc}; {check.degree.label().lower()}."
    )


def _spell_save_text(target, check, *, statistic: str = "Fortitude") -> str:
    return (
        f"{target.label} {statistic} save: d20 {check.die} + {check.modifier} = "
        f"{check.total} vs DC {check.dc}; {check.degree.label().lower()}."
    )


def _validate_setup(setup: EncounterSetup) -> None:
    if not isinstance(setup, EncounterSetup):
        raise ValueError("setup must be an EncounterSetup")
    if not setup.setup_id or not setup.name:
        raise ValueError("setup needs an id and name")
    try:
        catalogued_setup = get_setup(setup.setup_id)
    except ValueError as error:
        raise ValueError(f"unknown encounter setup {setup.setup_id!r}") from error
    if setup != catalogued_setup:
        raise ValueError("encounter setup must match its catalogued definition")
    if setup.ambient_light not in {"bright", "dim"}:
        raise ValueError("scene ambient light must be bright or dim")
    if (
        type(setup.weather_ranged_spell_attack_circumstance_penalty) is not int
        or type(setup.weather_perception_circumstance_penalty) is not int
        or setup.weather_ranged_spell_attack_circumstance_penalty < 0
        or setup.weather_perception_circumstance_penalty < 0
        or type(setup.weather_concealment) is not bool
    ):
        raise ValueError("weather provenance must use non-negative penalties and a boolean concealment fact")
    # Catalogue equality above closes admission; grid coordinates support up to 26 columns.
    if (
        type(setup.width) is not int
        or type(setup.height) is not int
        or not 1 <= setup.width <= 26
        or setup.height < 1
    ):
        raise ValueError("map width must be 1–26 columns and height must be a positive integer")
    if len(setup.placements) < 2:
        raise ValueError("an encounter requires at least two actors")
    if setup.tie_policy != "stable_setup_order":
        raise ValueError("NPC initiative ties use stable setup order")
    if len({placement.actor_id for placement in setup.placements}) != len(setup.placements):
        raise ValueError("actor ids must be unique")
    if len({placement.team for placement in setup.placements}) < 2:
        raise ValueError("an encounter requires at least two teams")
    positions: dict[Position, list[CreaturePlacement]] = {}
    for placement in setup.placements:
        positions.setdefault(placement.position, []).append(placement)
    for occupants in positions.values():
        if len(occupants) < 2:
            continue
        if len(occupants) != 2:
            raise ValueError("starting actor positions cannot overlap")
        first, second = occupants
        first_definition = get_definition(first.definition_id)
        second_definition = get_definition(second.definition_id)
        familiar, other = (
            (first, second) if first_definition.initiative_exempt else (second, first)
        )
        familiar_definition = get_definition(familiar.definition_id)
        if not (
            familiar_definition.initiative_exempt
            and familiar_definition.size == "tiny"
            and familiar.team == other.team
            and familiar_definition.familiar_owner_actor_id == other.actor_id
        ):
            raise ValueError("starting actor positions cannot overlap")
    for placement in setup.placements:
        if not placement.actor_id or not placement.label or not placement.team:
            raise ValueError("each actor needs an id, label, and team")
        if not isinstance(placement.position, Position):
            raise ValueError(f"starting position for {placement.actor_id!r} is invalid")
        if not in_bounds(placement.position, setup.width, setup.height):
            raise ValueError(f"starting position for {placement.actor_id!r} is outside the map")
        definition = get_definition(placement.definition_id)
        if setup.ambient_light == "dim" and definition.vision not in {"ordinary", "low_light"}:
            raise ValueError(
                f"actor {placement.actor_id!r} has unsupported vision {definition.vision!r}"
            )
        initiative_skill = placement.initiative_skill
        if not isinstance(initiative_skill, str) or not initiative_skill.strip():
            raise ValueError(f"initiative statistic for {placement.actor_id!r} is invalid")
        if initiative_skill != "perception" and not any(
            name == initiative_skill and rank is not None
            for name, rank, _modifier in definition.skills
        ):
            raise ValueError(
                f"initiative statistic {initiative_skill!r} is not trained for {placement.actor_id!r}"
            )
        if placement.initiative_context is not None and (
            not isinstance(placement.initiative_context, str)
            or not placement.initiative_context.strip()
        ):
            raise ValueError(f"initiative context for {placement.actor_id!r} is invalid")
        if initiative_skill != "perception" and placement.initiative_context is None:
            raise ValueError(
                f"initiative statistic {initiative_skill!r} needs an authored context"
            )
        for item in definition.item_instances:
            # Resolve every authored rune attachment while admitting the
            # setup, so unsupported/invalid content fails before initiative.
            weapon_rune_profile_for_item(item)
            armor_rune_profile_for_item(item)
        if not definition.grounded or definition.footprint_cells != 1:
            raise ValueError("supported actors are grounded and occupy one grid square")
        try:
            mode = HealthMode(definition.health_mode)
        except ValueError as error:
            raise ValueError(f"actor {placement.actor_id!r} has an unsupported health mode") from error
        if mode is HealthMode.PC and not 0 <= definition.hero_points <= 3:
            raise ValueError("PC Hero Points must be from zero through three")
        if definition.class_name == "Barbarian":
            if definition.armor_category not in {"unarmored", "light", "medium", "heavy"}:
                raise ValueError("admitted Barbarian loadouts need a reviewed armor category")
            bulk_rows = definition.carried_item_bulk
            if (
                not isinstance(bulk_rows, tuple)
                or any(
                    not isinstance(row, tuple) or len(row) != 2
                    or not isinstance(row[0], str) or not row[0]
                    or type(row[1]) is not int or row[1] < 0
                    for row in bulk_rows
                )
                or len({item_id for item_id, _bulk in bulk_rows}) != len(bulk_rows)
            ):
                raise ValueError("admitted Barbarian loadouts need explicit carried item Bulk facts")
            inventory_ids = set(definition.held_items + definition.worn_items + definition.stowed_items)
            if {item_id for item_id, _bulk in bulk_rows} != inventory_ids:
                raise ValueError("Barbarian carried item Bulk facts must match the fixed loadout")


def _coord(position: Position) -> str:
    return f"{chr(ord('A') + position.x)}{position.y + 1}"


def _damage_text(
    damage: DamageResult,
    dice_sides: tuple[int, ...],
    defeated: bool,
    *,
    bonus_dice: int = 0,
) -> str:
    if len(damage.components) > 1 and not (
        damage.adjustment == "deadly_after_critical" and len(damage.components) == 2
    ):
        component_text: list[str] = []
        for component in damage.components:
            source = component.source
            if component.dice:
                counts: dict[int, int] = {}
                for sides in component.dice:
                    counts[sides] = counts.get(sides, 0) + 1
                dice_label = "+".join(
                    f"{count}d{sides}" for sides, count in sorted(counts.items())
                )
                rolls = "+".join(str(face) for face in component.rolls) or "not rolled"
                raw = sum(component.rolls) + component.modifier
                detail = f"{source}: {dice_label} ({rolls}) + {component.modifier} = {raw}"
                if damage.multiplier == 2 and component.critical_mode == "double":
                    detail += f"; critical doubles to {component.amount}"
                elif component.critical_mode == "critical_only":
                    detail += f"; critical-only {component.amount}"
            else:
                detail = f"{source}: {component.modifier:+d} {component.damage_type}"
                if damage.multiplier == 2 and component.critical_mode == "double":
                    detail += f"; critical doubles to {component.amount}"
            component_text.append(detail)
        total_text = "; ".join(component_text) + f"; total {damage.total} damage"
        if defeated:
            total_text += "; target defeated"
        return f"Damage: {total_text}."
    component = damage.components[0]
    dice_counts: dict[int, int] = {}
    for sides in component.dice:
        dice_counts[sides] = dice_counts.get(sides, 0) + 1
    dice_label = "+".join(
        f"{count}d{sides}" for sides, count in sorted(dice_counts.items())
    )
    rolls_text = "+".join(str(face) for face in component.rolls)
    if damage.adjustment == "deadly_after_critical" and len(damage.components) > 1:
        base_raw = sum(component.rolls) + component.modifier
        deadly = damage.components[1]
        roll_detail = f"{dice_label} ({rolls_text}) + {component.modifier} = {base_raw}"
        result = (
            f"Damage: {roll_detail}; critical doubles to {component.amount}, "
            f"plus deadly 1d{deadly.dice_sides} ({deadly.rolls[0]}) = {damage.total} {component.damage_type}"
        )
        if defeated:
            result += "; target defeated"
        return result + "."
    roll_detail = f"{dice_label} ({rolls_text}) + {component.modifier} = {damage.rolled_total}"
    if damage.multiplier == 2:
        result = f"Damage: {roll_detail}; critical doubles to {damage.total} {component.damage_type}"
    else:
        result = f"Damage: {roll_detail} {component.damage_type}"
    if defeated:
        result += "; target defeated"
    return result + "."
