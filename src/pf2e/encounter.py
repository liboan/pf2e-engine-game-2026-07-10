"""Public local encounter interface for the S1 rules boundary.

Initiative and turns follow Remaster Player Core pp. 435–436:
https://2e.aonprd.com/Rules.aspx?ID=2423
https://2e.aonprd.com/Rules.aspx?ID=2428
https://2e.aonprd.com/Rules.aspx?ID=2429
"""

from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
from pathlib import Path
from typing import Iterable

from .checks import DegreeOfSuccess, Modifier, combine_modifiers, multiple_attack_penalty, resolve_check
from .content import S1_SETUP, get_definition, get_setup
from .damage import DamageComponent, DamagePacket, DamageResult, resolve_damage
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
    Command,
    CreatureState,
    EncounterSetup,
    EncounterState,
    EndTurn,
    EffectView,
    Event,
    HealthMode,
    Interact,
    Inspection,
    PendingChoice,
    Position,
    PreparedSlotState,
    PreparedSlotView,
    SpellOption,
    SpellTargetOption,
    ActiveSpellEffect,
    GuidanceImmunity,
    ResultStatus,
    Release,
    Stand,
    Step,
    StrikeOption,
    Strike,
    Stride,
    ViciousSwing,
    TakeCover,
    DismissCover,
    is_combat_capable,
)
from .persistence import DiceSource, DiceSourceError, load_encounter, save_encounter
from .space import (
    flanking_geometry,
    grid_distance_feet,
    in_bounds,
    is_adjacent,
    segment_crosses_cell_interior,
    step_cost,
)
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
from .spells import (
    SPELLS,
    basic_save_damage,
    divine_lance_damage,
    heal_range_ft,
    heal_roll,
    in_heal_emanation,
    spell_traits,
    void_warp_effect,
)


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
        creatures: dict[str, CreatureState] = {}
        for placement in setup.placements:
            definition = get_definition(placement.definition_id)
            creatures[placement.actor_id] = CreatureState(
                actor_id=placement.actor_id,
                definition_id=placement.definition_id,
                label=placement.label,
                team=placement.team,
                position=placement.position,
                hp=definition.hp,
                health_mode=HealthMode(definition.health_mode),
                hero_points=definition.hero_points,
                held_items=list(definition.held_items),
                worn_items=list(definition.worn_items),
                stowed_items=list(definition.stowed_items),
                ammunition=dict(definition.ammunition),
                prepared_slots=[
                    PreparedSlotState(
                        slot.slot_id, slot.source, slot.spell_id,
                        slot.rank, slot.cantrip, False,
                    )
                    for slot in definition.prepared_spells
                ],
            )
        state = EncounterState(
            setup_id=setup.setup_id,
            map_width=setup.width,
            map_height=setup.height,
            creatures=creatures,
            initiative_order=[],
            active_index=0,
            initiative_finalized=False,
            actor_start_counts={placement.actor_id: 0 for placement in setup.placements},
        )
        # All initial Perception checks are ranked by d20 + modifier only; no
        # degree-of-success or natural-die adjustment applies to initiative.
        for placement in setup.placements:
            definition = get_definition(placement.definition_id)
            creatures[placement.actor_id].initiative = dice.draw(20) + definition.perception
        encounter = cls(state, dice)
        encounter._continue_initiative_initialization(state)
        return encounter

    @classmethod
    def load(cls, path: str | Path) -> "Encounter":
        state, dice = load_encounter(path)
        encounter = cls(state, dice)
        encounter._validate_pending_context()
        return encounter

    def _validate_pending_context(self) -> None:
        """Reject saved choices whose continuation no longer matches engine state."""
        state = self._state
        pending = state.pending_choice
        if pending is None:
            return
        if pending.kind == "reaction":
            continuation = pending.continuation
            actor = state.creatures.get(pending.actor_id or "")
            owner = state.creatures.get(pending.owner_actor_id or "")
            if continuation is None or actor is None or owner is None:
                raise ValueError("save has an incomplete pending reaction")
            if continuation.actor_id != actor.actor_id or pending.target_id != actor.actor_id:
                raise ValueError("save has a pending reaction for a different action actor")
            if continuation.reaction_trigger not in {"movement", "manipulate", "ranged", "stand"}:
                raise ValueError("save has an invalid pending reaction trigger")
            if continuation.must_disrupt_on_critical != (continuation.reaction_trigger == "manipulate"):
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
            ):
                raise ValueError("save has a pending reaction for an inconsistent continuation")
            expected_options = tuple(
                ChoiceOption(option_id, label)
                for option_id, _attack, _damage_type, _nonlethal, label
                in self._reaction_strike_choices(owner, actor)
            ) + (ChoiceOption("decline", "Decline"),)
            if pending.options != expected_options:
                raise ValueError("save has inconsistent pending Reactive Strike options")
            return

        if pending.kind in {"spell_attack_hero_reroll", "spell_save_hero_reroll"}:
            continuation = pending.continuation
            caster = state.creatures.get(pending.actor_id or "")
            target = state.creatures.get(pending.target_id or "")
            check = pending.check
            if continuation is None or continuation.kind != "cast" or caster is None or target is None or check is None:
                raise ValueError("save has an incomplete pending spell check")
            if continuation.spell_id != pending.spell_id or continuation.target_id != target.actor_id:
                raise ValueError("save has a pending spell check for a different cast")
            if pending.kind == "spell_attack_hero_reroll":
                if pending.owner_actor_id != caster.actor_id or caster.health_mode is not HealthMode.PC or caster.hero_points < 1:
                    raise ValueError("save has an unavailable spell attack Hero Point choice")
                if pending.spell_id != "divine_lance" or check.attack_id != "divine_lance":
                    raise ValueError("save has an unsupported pending spell attack")
                if (
                    not continuation.attack_count_committed
                    or caster.strikes_this_turn != continuation.attack_count
                    or continuation.attack_penalty != multiple_attack_penalty(caster.strikes_this_turn - 1, spell_traits("divine_lance"))
                ):
                    raise ValueError("save has inconsistent Divine Lance MAP state")
                definition = get_definition(caster.definition_id)
                modifiers = [Modifier(definition.spell_attack or 0, "untyped", "printed spell attack modifier")]
                if continuation.attack_penalty:
                    modifiers.append(Modifier(continuation.attack_penalty, "untyped", "multiple attack penalty"))
                if continuation.guidance_bonus:
                    modifiers.append(Modifier(continuation.guidance_bonus, "status", "Guidance"))
                expected_dc = self._effective_ac(
                    target,
                    lesser_cover=self._has_lesser_cover(state, caster, target),
                    taking_cover=target.actor_id in state.taking_cover,
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
                if pending.spell_id != "void_warp" or check.dc != 17 or check.attack_id is not None:
                    raise ValueError("save has an unsupported pending spell save")
                fortitude = dict((name, modifier) for name, _rank, modifier in get_definition(target.definition_id).saves).get("fortitude")
                modifiers = [Modifier(fortitude or 0, "untyped", "printed Fortitude save")]
                if continuation.guidance_bonus:
                    modifiers.append(Modifier(continuation.guidance_bonus, "status", "Guidance"))
                if check.modifier_breakdown != tuple(modifiers) or check.modifier != combine_modifiers(modifiers):
                    raise ValueError("save has inconsistent Void Warp save modifiers")
            expected_options = (ChoiceOption("keep", "Keep result"), ChoiceOption("spend_hero_point", "Spend 1 Hero Point and reroll"))
            if pending.options != expected_options:
                raise ValueError("save has inconsistent spell Hero Point options")
            return
        if pending.kind == "guidance_use":
            continuation = pending.continuation
            effect = next((item for item in state.active_effects if item.effect_id == pending.effect_id), None)
            if continuation is None or effect is None or effect.kind != "guidance" or effect.target_actor_id != pending.owner_actor_id:
                raise ValueError("save has an incomplete Guidance choice")
            if pending.options != (ChoiceOption("use", "Use Guidance (+1 status)"), ChoiceOption("keep", "Keep Guidance for later")):
                raise ValueError("save has inconsistent Guidance options")
            return
        if pending.kind != "attack_hero_reroll":
            return
        actor = state.creatures.get(pending.actor_id or "")
        target = state.creatures.get(pending.target_id or "")
        check = pending.check
        attack = self._find_attack(actor, pending.attack_id) if actor is not None else None
        if actor is None or target is None or check is None or attack is None:
            raise ValueError("save has an incomplete pending Strike check")
        if pending.owner_actor_id != actor.actor_id or actor.health_mode is not HealthMode.PC or actor.hero_points < 1:
            raise ValueError("save has an unavailable Hero Point Strike choice")
        if target.actor_id == actor.actor_id or target.defeated or not self._attack_equipped(actor, attack):
            raise ValueError("save has an illegal pending Strike target or attack")
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
            }
            if continuation is None or expected_reaction_parent.get(continuation.kind) != continuation.reaction_trigger:
                raise ValueError("save has a pending reaction Strike without its parent action")
            if continuation.must_disrupt_on_critical != (continuation.reaction_trigger == "manipulate"):
                raise ValueError("save has inconsistent pending reaction disruption")
            if actor.actor_id not in continuation.seen_reactors:
                raise ValueError("save has a pending reaction Strike without its parent action")
            if continuation.actor_id != target.actor_id:
                raise ValueError("save has a pending reaction Strike for another target")
            if "melee" not in attack.traits or grid_distance_feet(actor.position, target.position) > attack.reach_ft:
                raise ValueError("save has an illegal pending Reactive Strike")
            expected_penalty, expected_count = 0, 1
        else:
            if pending.attack_actions_cost not in (1, 2) or pending.attack_count_cost != pending.attack_actions_cost:
                raise ValueError("save has inconsistent pending Strike costs")
            if actor.strikes_this_turn < pending.attack_count_cost:
                raise ValueError("save has impossible pending Strike count")
            attacks_before = actor.strikes_this_turn - pending.attack_count_cost
            expected_penalty = multiple_attack_penalty(attacks_before, attack.traits)
            expected_count = attacks_before + 1
            if pending.attack_actions_cost == 2 and "vicious_swing" not in get_definition(actor.definition_id).abilities:
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
            if attack.max_range_ft is None or attack.range_increment_ft is None or distance > attack.max_range_ft:
                raise ValueError("save has an out-of-range pending Strike")
            expected_ranged_penalty = -2 * max(0, (distance - 1) // attack.range_increment_ft)
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
        )
        if check.modifier_breakdown != expected_modifiers or check.modifier != combine_modifiers(expected_modifiers):
            raise ValueError("save has a pending check with inconsistent Strike modifiers")
        if check.dc != self._attack_dc(state, actor, target, attack):
            raise ValueError("save has a pending check with inconsistent target AC")
        if pending.options != (ChoiceOption("keep", "Keep result"), ChoiceOption("spend_hero_point", "Spend 1 Hero Point and reroll")):
            raise ValueError("save has inconsistent pending Hero Point Strike options")

    def save(self, path: str | Path) -> None:
        save_encounter(path, self._state, self._dice)

    def inspect(self) -> Inspection:
        state = self._state
        active_id = self._active_actor_id(state)
        actors: list[ActorView] = []
        display_order = state.initiative_order
        if not display_order:
            display_order = [placement.actor_id for placement in get_setup(state.setup_id).placements]
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
                    ammunition=tuple(sorted(creature.ammunition.items())),
                    effects=tuple(
                        EffectView(effect.kind, effect.source_actor_id,
                                   effect.target_actor_id, effect.value,
                                   effect.expires_at_source_start)
                        for effect in state.active_effects
                        if effect.target_actor_id == creature.actor_id
                    ),
                    guidance_immune_until_round=state.guidance_immunities.get(creature.actor_id),
                    taking_cover=creature.actor_id in state.taking_cover,
                    ability_modifiers=definition.ability_modifiers,
                    skills=definition.skills,
                    saves=definition.saves,
                    proficiencies=definition.proficiencies,
                    senses=definition.senses,
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
                    ac=self._effective_ac(creature),
                    perception=definition.perception - (4 if creature.unconscious else 0),
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
            choice=self._choice_view(state.pending_choice),
            ground_items=tuple(
                (position, tuple(items))
                for position, items in sorted((state.ground_items or {}).items())
                if items
            ),
        )

    def options(self) -> ActionOptions:
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
        actions = actor.actions_remaining
        can_act = actions > 0 and not actor.unconscious and not actor.dead
        can_move = can_act and not actor.prone
        step_destinations = self._step_destinations(actor, state) if can_move else ()
        usable = tuple(attack for attack in definition.attacks if self._attack_usable(actor, attack)) if can_act else ()
        strikes = tuple(
            StrikeOption(
                attack_id=attack.attack_id,
                name=attack.name,
                targets=self._strike_targets(actor, state, attack),
                damage_types=self._attack_damage_types(attack),
                default_damage_type=attack.damage_type,
                default_nonlethal="nonlethal" in attack.traits,
            )
            for attack in usable
        )
        targets = tuple(dict.fromkeys(target for strike in strikes for target in strike.targets))
        if actor.must_leave_occupied:
            strikes = ()
            targets = ()
        can_stride = can_move and self._has_open_neighbor(actor, state)
        can_step = bool(step_destinations)
        can_strike = bool(targets) and can_act and not actor.must_leave_occupied
        can_vicious = (
            can_act and not actor.must_leave_occupied
            and "vicious_swing" in definition.abilities
            and actor.flourish_used_round != state.round_number
            and actions >= 2
            and any("melee" in attack.traits and self._strike_targets(actor, state, attack) for attack in usable)
        )
        interact_options = self._interact_options(actor, state) if can_act and not actor.must_leave_occupied else ()
        spells = self._spell_options(actor, state) if can_act and not actor.must_leave_occupied else ()
        can_stand = can_act and actor.prone and not self._shares_space_with_living_actor(actor, state)
        can_crawl = can_act and actor.prone and self._has_open_neighbor(actor, state)
        can_release = bool(actor.held_items) and not actor.must_leave_occupied
        available = tuple(
            action
            for action, enabled in (
                ("stride", can_stride),
                ("step", can_step),
                ("strike", can_strike),
                ("vicious_swing", can_vicious),
                ("interact", bool(interact_options)),
                ("release", can_release),
                ("stand", can_stand),
                ("crawl", can_crawl),
                ("take_cover", can_act and actor.prone and actor.actor_id not in state.taking_cover),
                ("dismiss_cover", actor.actor_id in state.taking_cover),
                ("cast", any(not spell.unavailable_reason and (spell.cantrip or spell.slots) for spell in spells)),
                ("end_turn", not actor.must_leave_occupied),
            )
            if enabled
        )
        return ActionOptions(
            actor_id=active_id,
            actions_remaining=actions,
            can_stride=can_stride,
            can_step=can_step,
            can_strike=can_strike,
            can_end_turn=not actor.must_leave_occupied,
            strike_targets=targets,
            step_destinations=step_destinations,
            available_actions=available,
            capabilities=tuple(sorted(definition.abilities)),
            strikes=strikes,
            interact_options=interact_options,
            spells=spells,
        )

    def _spell_options(self, actor, state) -> tuple[SpellOption, ...]:
        """Report only engine-computed targets and currently available slots."""
        prepared_ids = tuple(dict.fromkeys(slot.spell_id for slot in actor.prepared_slots))
        result: list[SpellOption] = []
        for spell_id in prepared_ids:
            spell = SPELLS.get(spell_id)
            if spell is None:
                continue
            slots = tuple(
                (slot.slot_id, slot.source)
                for slot in actor.prepared_slots
                if slot.spell_id == spell_id and not slot.cantrip and not slot.spent
            )
            cantrip = any(slot.spell_id == spell_id and slot.cantrip for slot in actor.prepared_slots)
            target_options: list[SpellTargetOption] = []
            for actions in spell.action_costs:
                if actions > actor.actions_remaining:
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
                range_ft = spell.range_ft
                if spell_id == "heal" and actions == 1:
                    range_ft = 5
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

    def _spell_target_valid(self, spell_id, caster, target, state) -> bool:
        if spell_id == "stabilize":
            return target.health_mode is HealthMode.PC and target.dying > 0 and not target.dead
        if spell_id == "guidance":
            return (
                self._is_living_target(target)
                and state.guidance_immunities.get(target.actor_id, 0) < state.round_number
                and not any(effect.kind == "guidance" and effect.target_actor_id == target.actor_id for effect in state.active_effects)
            )
        if spell_id in {"heal", "void_warp"}:
            return self._is_living_target(target)
        return not target.dead and not target.defeated

    def execute(self, command: Command) -> ActionResult:
        if not isinstance(command, (Stride, Step, Strike, ViciousSwing, Cast, TakeCover, DismissCover, Interact, Release, Stand, Crawl, EndTurn, Choose)):
            return self._result(ResultStatus.UNSUPPORTED, f"Unsupported command type: {type(command).__name__}.")
        if self._state.pending_choice is not None and not isinstance(command, Choose):
            return self._result(ResultStatus.REJECTED, "A pending choice must be resolved before another action.")
        if self._state.pending_choice is None and isinstance(command, Choose):
            return self._result(ResultStatus.REJECTED, "There is no pending choice to resolve.")
        if not self._state.in_progress:
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
        if isinstance(command, EndTurn):
            if actor.must_leave_occupied:
                raise _Rejected("Move immediately to leave the occupied ally's space before ending the turn.")
            return self._end_turn(state, actor, early=True, dice=dice)
        if actor.unconscious or actor.dead:
            raise _Rejected("An unconscious or dead actor cannot take actions.")
        if isinstance(command, DismissCover):
            if actor.actor_id not in state.taking_cover:
                raise _Rejected("The actor is not taking cover.")
            state.taking_cover.remove(actor.actor_id)
            return [Event("cover_dismissed", actor.actor_id, None, f"{actor.label} dismisses Take Cover.")]
        if isinstance(command, Release):
            return self._release(state, actor, command)
        if actor.must_leave_occupied and not isinstance(command, (Stride, Step, Crawl)):
            raise _Rejected("Move immediately to leave the occupied ally's space before another action.")
        if actor.actions_remaining < 1:
            raise _Rejected("The active actor has no actions remaining.")
        if isinstance(command, Stride):
            return self._stride(state, dice, actor, command)
        if isinstance(command, Step):
            return self._step(state, dice, actor, command)
        if isinstance(command, Strike):
            return self._strike(state, dice, actor, command)
        if isinstance(command, ViciousSwing):
            return self._vicious_swing(state, dice, actor, command)
        if isinstance(command, Cast):
            return self._cast(state, dice, actor, command)
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

    def _step(self, state: EncounterState, dice: DiceSource, actor: CreatureState, command: Step) -> list[Event]:
        definition = get_definition(actor.definition_id)
        if definition.land_speed_ft < 10:
            raise _Rejected("Step requires a land Speed of at least 10 feet.")
        return self._begin_move(state, dice, actor, (command.destination,), "step", reactions=False, max_distance=5)

    def _crawl(self, state: EncounterState, dice: DiceSource, actor: CreatureState, command: Crawl) -> list[Event]:
        if not actor.prone:
            raise _Rejected("Crawl is only available while prone.")
        return self._begin_move(state, dice, actor, command.path, "crawl", reactions=True, max_distance=5)

    def _begin_move(self, state, dice, actor, path, kind, *, reactions, max_distance=None) -> list[Event]:
        if actor.prone and kind not in ("crawl",):
            raise _Rejected("While prone, only Crawl or Stand can be used as a move action.")
        if not isinstance(path, tuple) or not path:
            raise _Rejected(f"{kind.title()} requires a nonempty tuple of path squares.")
        definition = get_definition(actor.definition_id)
        limit = definition.land_speed_ft if max_distance is None else max_distance
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
        if kind == "step" or not reactions:
            for point in path:
                cost, diagonal_count = step_cost(actor.position, point, actor.diagonals_this_turn)
                actor.position = point
                actor.diagonals_this_turn += diagonal_count
            actor.must_leave_occupied = self._ends_in_living_ally_space(actor, state)
            events.append(Event(kind, actor.actor_id, None, f"{kind.title()}: moved to {_coord(actor.position)}.", position=actor.position))
            return self._complete_action(state, actor, events, dice=dice)
        return events + self._advance_continuation(state, dice, continuation)

    def _strike(self, state: EncounterState, dice: DiceSource, actor: CreatureState, command: Strike) -> list[Event]:
        return self._start_strike(
            state, dice, actor, command.target_id, command.attack_id,
            command.damage_type, command.nonlethal, actions_cost=1, attack_count_cost=1,
            vicious_swing=False,
        )

    def _vicious_swing(self, state, dice, actor, command: ViciousSwing) -> list[Event]:
        if "vicious_swing" not in get_definition(actor.definition_id).abilities:
            raise _Unsupported("Vicious Swing is not admitted for this creature.")
        if actor.flourish_used_round == state.round_number:
            raise _Rejected("Vicious Swing is limited to once per round.")
        return self._start_strike(
            state, dice, actor, command.target_id, command.attack_id,
            command.damage_type, command.nonlethal, actions_cost=2, attack_count_cost=2,
            vicious_swing=True,
        )

    def _start_strike(self, state, dice, actor, target_id, attack_id, damage_type, nonlethal, *, actions_cost, attack_count_cost, vicious_swing):
        if not isinstance(target_id, str):
            raise _Rejected("Strike target id must be text.")
        if actions_cost > actor.actions_remaining:
            raise _Rejected(f"This activity requires {actions_cost} actions.")
        target = state.creatures.get(target_id)
        if target is None or target.actor_id == actor.actor_id or target.defeated:
            raise _Rejected("Strike target must be an active creature.")
        attack = self._select_attack(actor, attack_id)
        if attack is None:
            if any(item.attack_id == attack_id for item in get_definition(actor.definition_id).attacks):
                raise _Rejected(f"Attack {attack_id!r} requires its listed item to be held.")
            raise _Unsupported(f"Attack {attack_id!r} is not supported in S1 or for this creature.")
        if vicious_swing and "melee" not in attack.traits:
            raise _Rejected("Vicious Swing requires a melee Strike.")
        if "melee" not in attack.traits:
            # Ranged attacks provoke Reactive Strike before their roll.
            is_ranged = "ranged" in attack.traits
        else:
            is_ranged = False
        distance = grid_distance_feet(actor.position, target.position)
        ranged_penalty = 0
        if "ranged" in attack.traits:
            if attack.max_range_ft is None or attack.range_increment_ft is None or attack.range_increment_ft < 1:
                raise _Unsupported("This ranged weapon has no admitted range profile.")
            if distance > attack.max_range_ft:
                raise _Rejected(f"Target is {distance} feet away; maximum range is {attack.max_range_ft} feet.")
            ranged_penalty = -2 * max(0, (distance - 1) // attack.range_increment_ft)
            if attack.item_id is not None and attack.item_id not in actor.held_items:
                raise _Rejected(f"The {attack.name} must be held to use it.")
            hands_used = len(actor.held_items)
            free_hands = max(0, 2 - hands_used)
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

        penalty = multiple_attack_penalty(actor.strikes_this_turn, attack.traits)
        if attack.ammunition_id is not None:
            actor.ammunition[attack.ammunition_id] -= 1
        actor.actions_remaining -= actions_cost
        state.taking_cover.discard(actor.actor_id)
        actor.strikes_this_turn += attack_count_cost
        if vicious_swing:
            actor.flourish_used_round = state.round_number
        context = ActionContinuation(
            kind="ranged_strike" if is_ranged else "strike",
            actor_id=actor.actor_id,
            target_id=target.actor_id,
            attack_id=attack.attack_id,
            damage_type=chosen_type,
            nonlethal=chosen_nonlethal,
            attack_penalty=penalty,
            attack_count=actor.strikes_this_turn - attack_count_cost + 1,
            attack_actions_cost=actions_cost,
            attack_count_cost=attack_count_cost,
            damage_bonus_dice=1 if vicious_swing else 0,
            vicious_swing=vicious_swing,
            movement_kind="ranged" if is_ranged else None,
            ranged_penalty=ranged_penalty,
        )
        if is_ranged:
            return [Event("strike_started", actor.actor_id, target.actor_id, f"{actor.label} commits to a ranged Strike.")] + self._advance_continuation(state, dice, context)
        return self._roll_strike(state, dice, actor, target, attack, context, parent=None)

    def _roll_strike(self, state, dice, actor, target, attack, context, *, parent):
        if not context.guidance_checked:
            effect = self._guidance_for(state, actor.actor_id)
            if effect is not None:
                context.guidance_checked = True
                self._offer_guidance(state, actor, context, effect, check_kind="weapon_attack", parent=parent)
                return [Event("guidance_choice", effect.source_actor_id, actor.actor_id, f"{actor.label} may use Guidance before this attack roll.")]
        modifiers = _strike_modifier_breakdown_full(
            attack,
            context.attack_penalty,
            context.nonlethal,
            actor.prone and not actor.unconscious,
            ranged_penalty=context.ranged_penalty,
            guidance_bonus=context.guidance_bonus,
            enfeebled=self._enfeebled_value(state, actor.actor_id) if attack.attack_attribute == "strength" else 0,
        )
        modifier = combine_modifiers(modifiers)
        dc = self._attack_dc(state, actor, target, attack)
        die = dice.draw(20)
        check = replace(resolve_check(
            die,
            modifier,
            dc,
            attack_id=attack.attack_id,
            attack_count=max(1, context.attack_count),
            map_penalty=context.attack_penalty,
            traits=attack.traits,
        ), modifier_breakdown=tuple(modifiers))
        if actor.health_mode is HealthMode.PC and actor.hero_points > 0:
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
                is_reaction=context.kind == "reaction_strike",
                continuation=parent,
            )
            return [self._attack_event(actor, target, check)]
        return self._resolve_attack_result(
            state, dice, actor, target, attack, check,
            damage_type=context.damage_type or attack.damage_type,
            nonlethal=context.nonlethal,
            damage_bonus_dice=context.damage_bonus_dice,
            is_reaction=context.kind == "reaction_strike",
            continuation=parent,
        )

    def _attack_event(self, actor: CreatureState, target: CreatureState, check) -> Event:
        degree_text = check.degree.label().lower()
        attack_text = f"Attack: d20 {check.die} + {check.modifier} = {check.total} vs AC {check.dc}; {degree_text}."
        if check.map_penalty:
            attack_text = attack_text[:-1] + f" (MAP {check.map_penalty})."
        return Event("strike", actor.actor_id, target.actor_id, attack_text, check=check)

    def _resolve_attack_result(
        self, state, dice, actor, target, attack, check, *, damage_type=None,
        nonlethal=False, damage_bonus_dice=0, is_reaction=False, continuation=None,
    ) -> list[Event]:
        events = [self._attack_event(actor, target, check)]
        if check.degree not in (DegreeOfSuccess.SUCCESS, DegreeOfSuccess.CRITICAL_SUCCESS):
            if continuation is not None:
                events.extend(self._resume_continuation(state, dice, continuation, critical=False))
            elif not is_reaction and state.in_progress and actor.actions_remaining == 0:
                events.extend(self._end_turn(state, actor, early=False, dice=dice))
            return events

        pack_bonus = 1 if "pack_attack" in get_definition(actor.definition_id).abilities and self._pack_attack_applies(state, actor, target) else 0
        bonus_dice = damage_bonus_dice + pack_bonus
        damage = self._roll_attack_damage(
            state, dice, actor, attack, damage_type or attack.damage_type,
            critical=check.degree is DegreeOfSuccess.CRITICAL_SUCCESS,
            bonus_dice=bonus_dice,
        )
        defeated = False
        if target.health_mode is HealthMode.PC:
            transition = self._propose_pc_damage(
                target,
                damage.total,
                attacker_critical=check.degree is DegreeOfSuccess.CRITICAL_SUCCESS,
                target_critical_failure=False,
                nonlethal=nonlethal,
                hero_points=target.hero_points,
            )
            if transition.heroic_recovery_available and transition.heroic_recovery_option is not None:
                self._set_pending(
                    state,
                    kind="heroic_recovery_damage",
                    owner_actor_id=target.actor_id,
                    prompt=f"{target.label} would gain dying from damage; choose normal outcome or Heroic Recovery.",
                    options=(ChoiceOption("normal", "Apply normal health outcome"), ChoiceOption("heroic_recovery", "Heroic Recovery (spend all Hero Points)")),
                    details=(f"Damage rolled: {damage.total} {damage_type or attack.damage_type}.",),
                    actor_id=actor.actor_id,
                    target_id=target.actor_id,
                    attack_id=attack.attack_id,
                    check=check,
                    damage_result=damage,
                    damage_text=_damage_text(damage, attack.damage_dice, transition.state.dead, bonus_dice=bonus_dice),
                    attack_critical=check.degree is DegreeOfSuccess.CRITICAL_SUCCESS,
                    health_normal=transition,
                    health_heroic=transition.heroic_recovery_option,
                    transition_kind="damage",
                    damage_type=damage_type or attack.damage_type,
                    nonlethal=nonlethal,
                    damage_bonus_dice=damage_bonus_dice,
                    is_reaction=is_reaction,
                    continuation=continuation,
                )
                return events
            self._apply_health_transition(state, target, transition)
            defeated = target.defeated
        else:
            before_hp = target.hp
            target.hp = max(0, target.hp - damage.total)
            if target.hp == 0 and before_hp > 0:
                if target.health_mode is HealthMode.ORDINARY:
                    if nonlethal:
                        target.dead = False
                        target.unconscious = True
                        target.prone = True
                        target.reaction_available = False
                        target.must_leave_occupied = False
                        if target.held_items:
                            state.ground_items.setdefault(target.position, []).extend(target.held_items)
                            target.held_items.clear()
                    else:
                        target.dead = True
                        target.unconscious = False
                defeated = target.defeated

        text = _damage_text(damage, attack.damage_dice, defeated, bonus_dice=bonus_dice)
        events.append(Event("damage", actor.actor_id, target.actor_id, text, damage=damage))
        if defeated:
            events.append(Event("defeated", actor.actor_id, target.actor_id, f"{target.label} is defeated."))
        self._finish_if_team_defeated(state)
        if continuation is not None and state.in_progress:
            events.extend(self._resume_continuation(state, dice, continuation, critical=check.degree is DegreeOfSuccess.CRITICAL_SUCCESS))
        elif not is_reaction and state.in_progress and actor.actions_remaining == 0 and state.pending_choice is None:
            events.extend(self._end_turn(state, actor, early=False, dice=dice))
        return events

    def _roll_attack_damage(self, state, dice, actor, attack, damage_type, *, critical, bonus_dice=0):
        modifier = self._damage_modifier(state, actor, attack)
        base = resolve_damage(
            DamagePacket(
                source=attack.attack_id,
                damage_type=damage_type,
                dice_sides=attack.damage_dice[0],
                dice_count=len(attack.damage_dice) + bonus_dice,
                modifier=modifier,
            ),
            dice.draw,
            critical=critical,
        )
        if not critical or attack.deadly_die is None:
            return base
        deadly_roll = dice.draw(attack.deadly_die)
        deadly = DamageComponent(
            source=f"{attack.attack_id} deadly",
            damage_type=damage_type,
            dice_sides=attack.deadly_die,
            rolls=(deadly_roll,),
            modifier=0,
            amount=deadly_roll,
        )
        return DamageResult(
            components=base.components + (deadly,),
            rolled_total=base.rolled_total + deadly_roll,
            multiplier=2,
            total=base.total + deadly_roll,
            adjustment="deadly_after_critical",
        )

    def _damage_modifier(self, state, actor, attack):
        penalty = self._enfeebled_value(state, actor.actor_id) if attack.damage_attribute == "strength" else 0
        return attack.damage_modifier - penalty

    def _strike_targets(self, actor: CreatureState, state: EncounterState, attack=None) -> tuple[str, ...]:
        definition = get_definition(actor.definition_id)
        attacks = (attack,) if attack is not None else tuple(item for item in definition.attacks if self._attack_usable(actor, item))
        reachable: list[str] = []
        for target_id in state.initiative_order or state.creatures:
            target = state.creatures[target_id]
            if target.actor_id == actor.actor_id or target.defeated:
                continue
            if any(
                self._attack_usable(actor, item)
                and grid_distance_feet(actor.position, target.position) <= (
                    item.max_range_ft if "ranged" in item.traits and item.max_range_ft is not None
                    else item.reach_ft
                )
                for item in attacks
            ):
                reachable.append(target_id)
        return tuple(reachable)

    def _attack_usable(self, actor, attack) -> bool:
        return self._attack_equipped(actor, attack) and (
            attack.ammunition_id is None or actor.ammunition.get(attack.ammunition_id, 0) > 0
        )

    def _attack_equipped(self, actor, attack) -> bool:
        if attack.item_id is not None and attack.item_id not in actor.held_items:
            return False
        if attack.free_hands_required:
            if max(0, 2 - len(actor.held_items)) < attack.free_hands_required:
                return False
        return True

    def _select_attack(self, actor, attack_id):
        attacks = get_definition(actor.definition_id).attacks
        candidates = attacks if attack_id is None else tuple(a for a in attacks if a.attack_id == attack_id)
        return next((attack for attack in candidates if self._attack_usable(actor, attack)), None)

    @staticmethod
    def _attack_damage_types(attack) -> tuple[str, ...]:
        types = [attack.damage_type]
        for trait, damage_type in (("versatile-p", "piercing"), ("versatile-s", "slashing"), ("versatile-b", "bludgeoning")):
            if trait in attack.traits and damage_type not in types:
                types.append(damage_type)
        return tuple(types)

    def _attack_dc(self, state, actor, target, attack) -> int:
        flanked = (
            "melee" in attack.traits
            and not target.unconscious
            and not target.prone
            and self._is_flanked(state, actor, target)
        )
        return self._effective_ac(
            target,
            flanked=flanked,
            lesser_cover=self._has_lesser_cover(state, actor, target),
            taking_cover=("ranged" in attack.traits and target.actor_id in state.taking_cover),
        )

    def _is_flanked(self, state, attacker, target) -> bool:
        own_definition = get_definition(attacker.definition_id)
        if attacker.unconscious or attacker.dead or not any("melee" in a.traits and self._attack_usable(attacker, a) for a in own_definition.attacks):
            return False
        for ally in state.creatures.values():
            if ally.actor_id in (attacker.actor_id, target.actor_id) or ally.team != attacker.team or ally.unconscious or ally.dead or ally.defeated:
                continue
            definition = get_definition(ally.definition_id)
            if not any(
                "melee" in attack.traits
                and self._attack_usable(ally, attack)
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
            choices.extend(
                ("draw", item)
                for item in actor.worn_items
                if item in drawable_items and item not in actor.held_items
            )
            choices.extend(
                ("draw", item)
                for item in actor.stowed_items
                if item in drawable_items and item not in actor.held_items
            )
            choices.extend(("retrieve", item) for item in (state.ground_items or {}).get(actor.position, ()))
        choices.extend(("stow", item) for item in actor.held_items)
        return tuple(choices)

    def _interact(self, state, dice, actor, command: Interact) -> list[Event]:
        if actor.must_leave_occupied:
            raise _Rejected("Move out of the occupied ally's space before Interacting.")
        if (command.mode, command.item_id) not in self._interact_options(actor, state):
            raise _Rejected("That Interact mode and item are not currently available.")
        actor.actions_remaining -= 1
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

    def _cast(self, state, dice, actor, command: Cast):
        spell = SPELLS.get(command.spell_id)
        if spell is None:
            raise _Unsupported(f"Spell {command.spell_id!r} is outside the admitted spell list.")
        if spell.unavailable_reason:
            raise _Rejected(spell.unavailable_reason)
        definition = get_definition(actor.definition_id)
        prepared = [slot for slot in actor.prepared_slots if slot.spell_id == spell.spell_id]
        if not prepared:
            raise _Rejected(f"{actor.label} has not prepared {spell.name}.")
        cantrip = any(slot.cantrip for slot in prepared)
        if command.actions is None:
            if len(spell.action_costs) != 1:
                raise _Rejected(f"Choose an action mode for {spell.name}: {', '.join(map(str, spell.action_costs))} actions.")
            actions = spell.action_costs[0]
        else:
            actions = command.actions
        if type(actions) is not int or actions not in spell.action_costs:
            raise _Rejected(f"{actions!r} is not a supported action mode for {spell.name}.")
        if actions > actor.actions_remaining:
            raise _Rejected(f"{spell.name} requires {actions} actions.")
        if spell.spell_id == "heal" and actions == 3:
            if command.target_id is not None:
                raise _Rejected("Three-action Heal affects the eligible emanation; it does not take a single target.")
            if command.include_self is not None and type(command.include_self) is not bool:
                raise _Rejected("include_self must be true or false for three-action Heal.")
        elif command.include_self is not None:
            raise _Rejected("include_self is only supported for three-action Heal.")
        if not cantrip:
            available_slots = [slot for slot in prepared if not slot.cantrip and not slot.spent]
            if command.slot_id is None:
                if not available_slots:
                    raise _Rejected(f"No unspent prepared slot remains for {spell.name}.")
                if len(available_slots) > 1:
                    self._set_pending(
                        state, kind="spell_slot", owner_actor_id=actor.actor_id,
                        prompt=f"Choose which prepared {spell.name} slot to expend.",
                        options=tuple(ChoiceOption(slot.slot_id, f"{slot.source}: {slot.slot_id}") for slot in available_slots),
                        actor_id=actor.actor_id, spell_id=spell.spell_id,
                        spell_actions=actions, target_id=command.target_id,
                        include_self=command.include_self,
                    )
                    return [Event("spell_slot_choice", actor.actor_id, None, f"Choose a prepared {spell.name} slot.")]
                selected_slot = available_slots[0]
            else:
                selected_slot = next((slot for slot in available_slots if slot.slot_id == command.slot_id), None)
                if selected_slot is None:
                    raise _Rejected("That prepared spell slot is unavailable.")
        else:
            if command.slot_id is not None:
                raise _Rejected("Cantrips do not expend a prepared spell slot.")
            selected_slot = None

        candidates = self._spell_targets_for_cast(state, actor, spell.spell_id, actions)
        if spell.spell_id != "heal" or actions != 3:
            if command.target_id is not None and spell.spell_id in {"divine_lance", "void_warp"} and self._stable_zero_pc(state.creatures.get(command.target_id)):
                raise _Unsupported("Positive damage to a stabilized 0 HP PC awaits a product ruling and is unsupported.")
            if command.target_id is not None and command.target_id not in candidates:
                raise _Rejected(f"That creature is not a legal target for {spell.name} in this mode.")
            if command.target_id is None and not candidates:
                raise _Rejected(f"There are no eligible targets for {spell.name}.")

        actor.actions_remaining -= actions
        if selected_slot is not None:
            selected_slot.spent = True
        if "attack" in spell.traits:
            state.taking_cover.discard(actor.actor_id)
        attack_count = 0
        attack_penalty = 0
        if "attack" in spell.traits:
            attack_penalty = multiple_attack_penalty(actor.strikes_this_turn, spell.traits)
            attack_count = actor.strikes_this_turn + 1
        continuation = ActionContinuation(
            kind="cast",
            actor_id=actor.actor_id,
            target_id=command.target_id,
            attack_penalty=attack_penalty,
            attack_count=attack_count,
            spell_id=spell.spell_id,
            spell_target_id=command.target_id,
            slot_id=selected_slot.slot_id if selected_slot else None,
            spell_actions=actions,
            include_self=command.include_self,
            movement_kind="manipulate" if "manipulate" in spell_traits(spell.spell_id, actions) else None,
            must_disrupt_on_critical="manipulate" in spell_traits(spell.spell_id, actions),
        )
        events = [Event("cast_started", actor.actor_id, command.target_id, f"{actor.label} commits {spell.name} ({actions} action(s)).")]
        if continuation.movement_kind == "manipulate":
            events.extend(self._advance_continuation(state, dice, continuation))
        else:
            events.extend(self._resolve_cast(state, dice, continuation))
        return events

    def _spell_targets_for_cast(self, state, caster, spell_id, actions):
        spell = SPELLS[spell_id]
        if spell_id == "heal" and actions == 3:
            return tuple(
                creature.actor_id for creature in state.creatures.values()
                if creature.actor_id != caster.actor_id and self._is_living_target(creature)
                and in_heal_emanation(caster.position, creature.position)
            )
        range_ft = 5 if spell_id == "heal" and actions == 1 else spell.range_ft
        result = []
        for target in state.creatures.values():
            if not self._spell_target_valid(spell_id, caster, target, state):
                continue
            if spell_id in {"divine_lance", "void_warp"} and self._stable_zero_pc(target):
                continue
            if range_ft is not None and grid_distance_feet(caster.position, target.position) > range_ft:
                continue
            result.append(target.actor_id)
        return tuple(result)

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
        if spell_id == "heal" and continuation.spell_actions == 3:
            if continuation.include_self is None:
                self._set_pending(
                    state, kind="spell_self_inclusion", owner_actor_id=caster.actor_id,
                    prompt="Include the caster in the three-action Heal emanation?",
                    options=(ChoiceOption("include", "Include self"), ChoiceOption("exclude", "Exclude self")),
                    actor_id=caster.actor_id, spell_id=spell_id,
                    slot_id=continuation.slot_id, spell_actions=3,
                    continuation=continuation,
                )
                return [Event("spell_self_choice", caster.actor_id, None, "Choose whether the Heal emanation includes the caster.")]
            return self._apply_heal_emanation(state, dice, continuation)
        if continuation.target_id is None:
            candidates = self._spell_targets_for_cast(state, caster, spell_id, continuation.spell_actions)
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
        if target is None or target.actor_id not in self._spell_targets_for_cast(state, caster, spell_id, continuation.spell_actions):
            return [Event("action_stopped", caster.actor_id, continuation.target_id, f"{SPELLS[spell_id].name}'s target is no longer eligible.")]
        if spell_id == "guidance":
            effect = ActiveSpellEffect(
                effect_id=f"guidance:{caster.actor_id}:{target.actor_id}:{state.next_choice_id}",
                kind="guidance", source_actor_id=caster.actor_id,
                target_actor_id=target.actor_id, value=1,
                expires_at_source_start=state.actor_start_counts.get(caster.actor_id, 0) + 1,
            )
            state.active_effects.append(effect)
            continuation.stage = "done"
            events = [Event("effect_applied", caster.actor_id, target.actor_id, f"Guidance grants {target.label} +1 status to one eligible check before the caster's next turn.")]
            return events + self._complete_action(state, caster, [], dice=dice)
        if spell_id == "stabilize":
            transition = pc_stabilize(self._health_state(target))
            self._apply_health_transition(state, target, transition)
            self._finish_if_team_defeated(state)
            continuation.stage = "done"
            events = [Event("stabilize", caster.actor_id, target.actor_id, f"{target.label} is stabilized at 0 HP and gains wounded {target.wounded}.")]
            return events + self._complete_action(state, caster, [], dice=dice)
        if spell_id == "heal" and continuation.spell_actions in (1, 2):
            self._set_pending(
                state, kind="spell_willingness",
                owner_actor_id=target.actor_id if target.health_mode is HealthMode.PC else None,
                prompt=f"Is {target.label} willing to receive Heal?",
                options=(ChoiceOption("willing", "Willing"), ChoiceOption("unwilling", "Unwilling")),
                actor_id=caster.actor_id, target_id=target.actor_id,
                spell_id="heal", slot_id=continuation.slot_id,
                spell_actions=continuation.spell_actions,
                continuation=continuation,
            )
            return [Event("spell_willingness", caster.actor_id, target.actor_id, f"Ask {target.label} whether to accept Heal.")]
        if spell_id == "heal":
            healing = heal_roll(continuation.spell_actions, dice.draw)
            events = self._apply_healing(state, caster, target, healing.total, healing.rolls, continuation)
            continuation.stage = "done"
            return events + self._complete_action(state, caster, [], dice=dice)
        if spell_id == "divine_lance":
            return self._roll_divine_lance(state, dice, caster, target, continuation)
        if spell_id == "void_warp":
            return self._roll_void_warp_save(state, dice, caster, target, continuation)
        raise _Unsupported(f"No encounter procedure is admitted for {spell_id!r}.")

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
                attack_count=continuation.attack_count, damage_type=continuation.damage_type,
                nonlethal=continuation.nonlethal, damage_bonus_dice=continuation.damage_bonus_dice,
                attack_actions_cost=continuation.attack_actions_cost,
                attack_count_cost=continuation.attack_count_cost,
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
        healing = heal_roll(3, dice.draw)
        recipients = [
            target for target in state.creatures.values()
            if self._is_living_target(target)
            and in_heal_emanation(caster.position, target.position)
            and (target.actor_id != caster.actor_id or continuation.include_self)
        ]
        events = [Event("heal_roll", caster.actor_id, None, f"Three-action Heal rolls 1d8 ({healing.rolls[0]}) = {healing.total}; the same result applies to {len(recipients)} creature(s).")]
        for target in recipients:
            events.extend(self._apply_healing(state, caster, target, healing.total, healing.rolls, continuation, roll_shared=True))
        continuation.stage = "done"
        events.extend(self._complete_action(state, caster, [], dice=dice))
        return events

    def _apply_healing(self, state, caster, target, amount, rolls, continuation, *, roll_shared=False):
        if target.dead:
            return [Event("healing_ignored", caster.actor_id, target.actor_id, f"{target.label} is dead and cannot be healed.")]
        if target.health_mode is HealthMode.PC:
            transition = pc_healing(self._health_state(target), amount)
            self._apply_health_transition(state, target, transition)
        else:
            target.hp = min(get_definition(target.definition_id).hp, target.hp + amount)
            if target.hp > 0:
                target.unconscious = False
        text = f"{target.label} heals {amount} HP ({'shared ' if roll_shared else ''}1d8 {rolls[0]}{' + 8' if continuation.spell_actions == 2 else ''}); now at {target.hp} HP."
        events = [Event("healing", caster.actor_id, target.actor_id, text)]
        return events

    def _roll_divine_lance(self, state, dice, caster, target, continuation):
        if not continuation.guidance_checked:
            effect = self._guidance_for(state, caster.actor_id)
            if effect is not None:
                continuation.guidance_checked = True
                self._offer_guidance(state, caster, continuation, effect, check_kind="spell_attack")
                return [Event("guidance_choice", effect.source_actor_id, caster.actor_id, f"{caster.label} may use Guidance before Divine Lance.")]
        if not continuation.attack_count_committed:
            caster.strikes_this_turn += 1
            continuation.attack_count_committed = True
        definition = get_definition(caster.definition_id)
        modifier = definition.spell_attack or 0
        breakdown = [Modifier(modifier, "untyped", "printed spell attack modifier")]
        if continuation.attack_penalty:
            breakdown.append(Modifier(continuation.attack_penalty, "untyped", "multiple attack penalty"))
        if continuation.guidance_bonus:
            breakdown.append(Modifier(continuation.guidance_bonus, "status", "Guidance"))
        die = dice.draw(20)
        traits = spell_traits("divine_lance")
        dc = self._effective_ac(
            target,
            lesser_cover=self._has_lesser_cover(state, caster, target),
            taking_cover=target.actor_id in state.taking_cover,
        )
        check = replace(resolve_check(
            die, combine_modifiers(breakdown), dc,
            attack_id="divine_lance", attack_count=max(1, continuation.attack_count),
            map_penalty=continuation.attack_penalty, traits=traits,
        ), modifier_breakdown=tuple(breakdown))
        if caster.health_mode is HealthMode.PC and caster.hero_points > 0:
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
            damage = divine_lance_damage(check.degree, dice.draw)
            if damage is not None:
                events.extend(self._apply_spell_damage(
                    state, caster, target, damage, check=check, source="divine_lance",
                    damage_type="spirit", attacker_critical=check.degree is DegreeOfSuccess.CRITICAL_SUCCESS,
                    continuation=continuation,
                ))
                if state.pending_choice is None:
                    continuation.stage = "done"
                    events.extend(self._complete_action(state, caster, [], dice=dice))
                return events
        continuation.stage = "done"
        events.extend(self._complete_action(state, caster, [], dice=dice))
        return events

    def _roll_void_warp_save(self, state, dice, caster, target, continuation):
        if not continuation.guidance_checked:
            effect = self._guidance_for(state, target.actor_id)
            if effect is not None:
                continuation.guidance_checked = True
                self._offer_guidance(state, target, continuation, effect, check_kind="spell_save")
                return [Event("guidance_choice", effect.source_actor_id, target.actor_id, f"{target.label} may use Guidance before the Fortitude save.")]
        fortitude = dict((name, modifier) for name, _rank, modifier in get_definition(target.definition_id).saves).get("fortitude")
        if fortitude is None:
            raise _Unsupported("Void Warp requires a supported Fortitude save modifier.")
        breakdown = [Modifier(fortitude, "untyped", "printed Fortitude save")]
        if continuation.guidance_bonus:
            breakdown.append(Modifier(continuation.guidance_bonus, "status", "Guidance"))
        die = dice.draw(20)
        check = replace(resolve_check(die, combine_modifiers(breakdown), 17), modifier_breakdown=tuple(breakdown))
        if target.health_mode is HealthMode.PC and target.hero_points > 0:
            self._set_pending(
                state, kind="spell_save_hero_reroll", owner_actor_id=target.actor_id,
                prompt=f"{target.label} may keep this Fortitude save or spend 1 Hero Point to reroll.",
                options=(ChoiceOption("keep", "Keep result"), ChoiceOption("spend_hero_point", "Spend 1 Hero Point and reroll"),),
                details=(f"Original: d20 {die} + {check.modifier} = {check.total} vs DC 17.", f"Degree: {check.degree.label()}.",),
                actor_id=caster.actor_id, target_id=target.actor_id,
                check=check, check_kind="spell_save", check_owner_actor_id=target.actor_id,
                spell_id="void_warp", slot_id=continuation.slot_id,
                spell_actions=continuation.spell_actions, continuation=continuation,
            )
            return [Event("spell_save", caster.actor_id, target.actor_id, _spell_save_text(target, check), check=check)]
        return self._resolve_void_warp_result(state, dice, caster, target, check, continuation)

    def _resolve_void_warp_result(self, state, dice, caster, target, check, continuation):
        result = void_warp_effect(check.degree, dice.draw)
        damage = replace(result.damage, adjustment=f"basic_save:{check.degree.name.lower()}")
        events = [Event("spell_save", caster.actor_id, target.actor_id, _spell_save_text(target, check), check=check)]
        events.extend(self._apply_spell_damage(
            state, caster, target, damage, check=check, source="void_warp",
            damage_type="void", target_critical_failure=check.degree is DegreeOfSuccess.CRITICAL_FAILURE,
            continuation=continuation, enfeebled_on_failure=result.enfeebled,
        ))
        if result.enfeebled and not target.dead and state.pending_choice is None:
            self._apply_enfeebled(state, caster, target, result.enfeebled)
            events.append(Event("effect_applied", caster.actor_id, target.actor_id, f"{target.label} is enfeebled {result.enfeebled} until {caster.label}'s next turn."))
        if state.pending_choice is None:
            continuation.stage = "done"
            events.extend(self._complete_action(state, caster, [], dice=dice))
        return events

    def _apply_enfeebled(self, state, caster, target, value):
        current = next((effect for effect in state.active_effects if effect.kind == "enfeebled" and effect.target_actor_id == target.actor_id), None)
        if current is not None and current.value >= value:
            return
        if current is not None:
            state.active_effects.remove(current)
        state.active_effects.append(ActiveSpellEffect(
            effect_id=f"enfeebled:{caster.actor_id}:{target.actor_id}:{state.next_choice_id}",
            kind="enfeebled", source_actor_id=caster.actor_id,
            target_actor_id=target.actor_id, value=value,
            expires_at_source_start=state.actor_start_counts.get(caster.actor_id, 0) + 1,
        ))

    def _apply_spell_damage(self, state, caster, target, damage, *, check, source, damage_type,
                            attacker_critical=False, target_critical_failure=False, continuation,
                            enfeebled_on_failure=0):
        if target.health_mode is HealthMode.PC:
            transition = self._propose_pc_damage(
                target, damage.total,
                attacker_critical=attacker_critical,
                target_critical_failure=target_critical_failure,
                hero_points=target.hero_points,
            )
            if transition.heroic_recovery_available and transition.heroic_recovery_option is not None:
                continuation.stage = "done"
                self._set_pending(
                    state, kind="heroic_recovery_damage", owner_actor_id=target.actor_id,
                    prompt=f"{target.label} would gain dying from {SPELLS[source].name}; choose normal outcome or Heroic Recovery.",
                    options=(ChoiceOption("normal", "Apply normal health outcome"), ChoiceOption("heroic_recovery", "Heroic Recovery (spend all Hero Points)")),
                    details=(f"Damage: {damage.total} {damage_type}.",),
                    actor_id=caster.actor_id, target_id=target.actor_id,
                    check=check, check_kind=source, damage_result=damage,
                    damage_text=f"{SPELLS[source].name} deals {damage.total} {damage_type}.",
                    spell_id=source,
                    damage_context=f"enfeebled:{enfeebled_on_failure}" if enfeebled_on_failure else None,
                    attack_critical=attacker_critical,
                    health_normal=transition, health_heroic=transition.heroic_recovery_option,
                    transition_kind="damage", damage_type=damage_type,
                    continuation=continuation,
                )
                return []
            self._apply_health_transition(state, target, transition)
        else:
            target.hp = max(0, target.hp - damage.total)
            if target.hp == 0 and target.health_mode is HealthMode.ORDINARY:
                target.dead = True
                target.unconscious = False
                target.prone = False
                target.reaction_available = False
        text = f"{SPELLS[source].name} deals {damage.total} {damage_type} to {target.label}."
        events = [Event("spell_damage", caster.actor_id, target.actor_id, text, check=check, damage=damage)]
        if target.defeated:
            events.append(Event("defeated", caster.actor_id, target.actor_id, f"{target.label} is defeated."))
        self._finish_if_team_defeated(state)
        continuation.stage = "done"
        return events

    def _release(self, state, actor, command: Release) -> list[Event]:
        if actor.must_leave_occupied:
            raise _Rejected("Move out of the occupied ally's space before taking another action.")
        if command.item_id not in actor.held_items:
            raise _Rejected(f"{command.item_id!r} is not held and cannot be released.")
        actor.held_items.remove(command.item_id)
        state.ground_items.setdefault(actor.position, []).append(command.item_id)
        return [Event("release", actor.actor_id, None, f"{actor.label} releases {command.item_id} onto {_coord(actor.position)}.", position=actor.position)]

    def _stand(self, state, dice, actor) -> list[Event]:
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
            if continuation.next_step >= len(continuation.path):
                actor.must_leave_occupied = self._ends_in_living_ally_space(actor, state)
                events.append(Event(continuation.movement_kind or "move", actor.actor_id, None, f"{actor.label} finishes moving at {_coord(actor.position)}.", position=actor.position))
                return self._complete_action(state, actor, events, dice=dice)
            reactor = self._next_reactor(state, actor, continuation, "movement")
            if reactor is not None:
                self._present_reaction(state, actor, reactor, continuation, "movement")
                return events
            destination = continuation.path[continuation.next_step]
            cost, diagonal_count = step_cost(actor.position, destination, actor.diagonals_this_turn)
            actor.position = destination
            actor.diagonals_this_turn += diagonal_count
            continuation.next_step += 1
            if actor.must_leave_occupied and not self._ends_in_living_ally_space(actor, state):
                actor.must_leave_occupied = False
            events.append(Event("move_step", actor.actor_id, None, f"{actor.label} moves to {_coord(destination)} ({cost} feet).", position=destination))
            events.extend(self._advance_continuation(state, dice, continuation))
            return events

        trigger = continuation.movement_kind
        if trigger in ("manipulate", "ranged", "stand"):
            reactor = self._next_reactor(state, actor, continuation, trigger)
            if reactor is not None:
                self._present_reaction(state, actor, reactor, continuation, trigger)
                return events

        if continuation.kind == "interact":
            events.append(self._apply_interact(state, actor, continuation.mode or "", continuation.item_id or ""))
            return self._complete_action(state, actor, events, dice=dice)
        if continuation.kind == "stand":
            events.append(Event("stand", actor.actor_id, None, f"{actor.label} is no longer prone."))
            return self._complete_action(state, actor, events, dice=dice)
        if continuation.kind == "ranged_strike":
            if actor.unconscious or actor.dead:
                events.append(Event("action_stopped", actor.actor_id, continuation.target_id, f"{actor.label} cannot finish the ranged Strike while incapacitated."))
                return events
            target = state.creatures.get(continuation.target_id or "")
            attack = self._find_attack(actor, continuation.attack_id)
            if target is None or target.defeated or attack is None or not self._attack_equipped(actor, attack):
                events.append(Event("action_stopped", actor.actor_id, continuation.target_id, "The ranged Strike is no longer legal after the reaction."))
                return self._complete_action(state, actor, events, dice=dice)
            events.extend(self._roll_strike(state, dice, actor, target, attack, continuation, parent=None))
            return events
        if continuation.kind == "cast":
            events.extend(self._resolve_cast(state, dice, continuation))
            return events
        raise _Rejected(f"Unsupported interrupted action {continuation.kind!r}.")

    def _resume_continuation(self, state, dice, continuation, *, critical) -> list[Event]:
        events: list[Event] = []
        actor = state.creatures[continuation.actor_id]
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

    def _next_reactor(self, state, actor, continuation, trigger):
        for reactor_id in state.initiative_order:
            if reactor_id == actor.actor_id or reactor_id in continuation.seen_reactors:
                continue
            reactor = state.creatures[reactor_id]
            if reactor.team == actor.team:
                continue
            if not reactor.reaction_available or reactor.unconscious or reactor.dead:
                continue
            if "reactive_strike" not in get_definition(reactor.definition_id).abilities:
                continue
            if not any(
                "melee" in attack.traits
                and self._attack_usable(reactor, attack)
                and grid_distance_feet(reactor.position, actor.position) <= attack.reach_ft
                for attack in get_definition(reactor.definition_id).attacks
            ):
                continue
            return reactor
        return None

    def _present_reaction(self, state, actor, reactor, continuation, trigger):
        continuation.reaction_trigger = trigger
        continuation.must_disrupt_on_critical = trigger == "manipulate"
        strike_choices = self._reaction_strike_choices(reactor, actor)
        self._set_pending(
            state,
            kind="reaction",
            owner_actor_id=reactor.actor_id,
            prompt=f"{reactor.label} may use Reactive Strike against {actor.label} ({trigger} trigger).",
            options=tuple(
                ChoiceOption(option_id, label)
                for option_id, _attack, _damage_type, _nonlethal, label in strike_choices
            ) + (ChoiceOption("decline", "Decline"),),
            details=(f"Reaction remains available if declined; this reactor is prompted at most once for this action.",),
            actor_id=actor.actor_id,
            target_id=actor.actor_id,
            continuation=continuation,
        )

    def _reaction_strike_choices(self, reactor, target):
        """Selectable melee Strike options for the current Reactive Strike."""
        attacks = tuple(
            attack for attack in get_definition(reactor.definition_id).attacks
            if "melee" in attack.traits and self._attack_usable(reactor, attack)
            and grid_distance_feet(reactor.position, target.position) <= attack.reach_ft
        )
        choices = []
        for attack_index, attack in enumerate(attacks):
            default_type = attack.damage_type
            default_nonlethal = "nonlethal" in attack.traits
            for damage_type in self._attack_damage_types(attack):
                for nonlethal in (default_nonlethal, not default_nonlethal):
                    is_default = (
                        attack_index == 0
                        and damage_type == default_type
                        and nonlethal == default_nonlethal
                    )
                    option_id = "accept" if is_default else (
                        f"strike:{attack.attack_id}:{damage_type}:"
                        f"{'nonlethal' if nonlethal else 'lethal'}"
                    )
                    intent = "nonlethal" if nonlethal else "lethal"
                    label = f"Use {attack.name} ({damage_type}, {intent})"
                    choices.append((option_id, attack, damage_type, nonlethal, label))
        return tuple(choices)

    def _perform_reaction(self, state, dice, reactor, target, continuation, attack, damage_type, nonlethal):
        reactor.reaction_available = False
        context = ActionContinuation(
            kind="reaction_strike",
            actor_id=reactor.actor_id,
            target_id=target.actor_id,
            attack_id=attack.attack_id,
            damage_type=damage_type,
            nonlethal=nonlethal,
            attack_penalty=0,
            attack_count=1,
            attack_actions_cost=0,
            attack_count_cost=0,
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
        if mode == "draw" and item_id in drawable_items and len(actor.held_items) < 2 and (item_id in actor.worn_items or item_id in actor.stowed_items):
            if item_id in actor.stowed_items:
                actor.stowed_items.remove(item_id)
            else:
                actor.worn_items.remove(item_id)
            actor.held_items.append(item_id)
            text = f"{actor.label} draws {item_id}."
        elif mode == "stow" and item_id in actor.held_items:
            actor.held_items.remove(item_id)
            actor.stowed_items.append(item_id)
            text = f"{actor.label} stows {item_id}."
        elif mode == "retrieve" and item_id in (state.ground_items or {}).get(actor.position, ()) and len(actor.held_items) < 2:
            items = state.ground_items[actor.position]
            items.remove(item_id)
            if not items:
                del state.ground_items[actor.position]
            actor.held_items.append(item_id)
            text = f"{actor.label} picks up {item_id}."
        else:
            raise _Rejected("The selected item transfer is no longer legal.")
        return Event("interact", actor.actor_id, None, text, position=actor.position)

    def _complete_action(self, state, actor, events, *, dice=None):
        if state.in_progress and actor.actions_remaining == 0 and actor.actor_id == self._active_actor_id(state):
            events.extend(self._end_turn(state, actor, early=False, dice=dice or self._dice.clone()))
        return events

    @staticmethod
    def _find_attack(actor, attack_id):
        return next((item for item in get_definition(actor.definition_id).attacks if item.attack_id == attack_id), None)

    def _occupant_at(self, state, position, *, except_actor=None):
        return next((item for item in state.creatures.values() if item.actor_id != except_actor and item.position == position), None)

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
        if definition.land_speed_ft < 10 or actor.prone:
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

    def _end_turn(self, state, actor, *, early: bool, dice: DiceSource) -> list[Event]:
        discarded = actor.actions_remaining
        actor.actions_remaining = 0
        actor.strikes_this_turn = 0
        actor.diagonals_this_turn = 0
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
        starts = state.actor_start_counts
        assert starts is not None
        starts[actor.actor_id] = starts.get(actor.actor_id, 0) + 1
        retained: list[ActiveSpellEffect] = []
        expired: list[ActiveSpellEffect] = []
        for effect in state.active_effects:
            if effect.source_actor_id == actor.actor_id and effect.expires_at_source_start <= starts[actor.actor_id]:
                expired.append(effect)
            else:
                retained.append(effect)
        state.active_effects = retained
        for effect in expired:
            if effect.kind == "guidance":
                state.guidance_immunities[effect.target_actor_id] = state.round_number + 600
        for target_id, until in tuple(state.guidance_immunities.items()):
            if state.round_number > until:
                del state.guidance_immunities[target_id]

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
        actor.actions_remaining = 3
        actor.reaction_available = "reactive_strike" in get_definition(actor.definition_id).abilities
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
            creature.must_leave_occupied = False
            state.taking_cover.discard(creature.actor_id)
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

    def _finish_if_team_defeated(self, state: EncounterState) -> None:
        active_teams = {creature.team for creature in state.creatures.values() if is_combat_capable(creature)}
        if len(active_teams) <= 1:
            state.in_progress = False
            state.winner_team = next(iter(active_teams), None)
            for creature in state.creatures.values():
                creature.actions_remaining = 0
                creature.reaction_available = False

    def _effective_ac(self, creature: CreatureState, *, flanked: bool = False, lesser_cover: bool = False, taking_cover: bool = False) -> int:
        definition = get_definition(creature.definition_id)
        modifiers = [Modifier(definition.ac, "untyped", "printed AC")]
        if creature.unconscious:
            modifiers.append(Modifier(-4, "status", "unconscious condition"))
        if creature.unconscious or creature.prone or flanked:
            modifiers.append(Modifier(-2, "circumstance", "off-guard"))
        if lesser_cover:
            modifiers.append(Modifier(1, "circumstance", "lesser creature cover"))
        if taking_cover:
            modifiers.append(Modifier(4, "circumstance", "Take Cover"))
        return combine_modifiers(modifiers)

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
                (entry for entry in self._reaction_strike_choices(reactor, target) if entry[0] == command.option_id),
                None,
            )
            if selection is None:
                raise _Rejected("That Reactive Strike option is no longer available.")
            _option_id, attack, damage_type, nonlethal, _label = selection
            return self._perform_reaction(
                state, dice, reactor, target, continuation, attack, damage_type, nonlethal
            )

        if pending.kind == "spell_slot":
            actor = state.creatures[pending.actor_id or ""]
            return self._cast(state, dice, actor, Cast(
                spell_id=pending.spell_id or "",
                target_id=pending.target_id,
                actions=pending.spell_actions,
                slot_id=command.option_id,
                include_self=pending.include_self,
            ))

        if pending.kind == "spell_target":
            continuation = pending.continuation
            if continuation is None or command.option_id not in pending.target_ids:
                raise _Rejected("That spell target choice is stale.")
            continuation.target_id = command.option_id
            continuation.spell_target_id = command.option_id
            return self._resolve_cast(state, dice, continuation)

        if pending.kind == "spell_self_inclusion":
            continuation = pending.continuation
            if continuation is None or continuation.spell_id != "heal" or continuation.spell_actions != 3:
                raise _Rejected("That Heal self-inclusion choice is stale.")
            continuation.include_self = command.option_id == "include"
            return self._apply_heal_emanation(state, dice, continuation)

        if pending.kind == "spell_willingness":
            continuation = pending.continuation
            caster = state.creatures[pending.actor_id or ""]
            target = state.creatures[pending.target_id or ""]
            if continuation is None or target.dead or not self._is_living_target(target):
                raise _Rejected("The Heal target is no longer eligible.")
            if command.option_id == "unwilling":
                continuation.stage = "done"
                return [Event("healing_refused", caster.actor_id, target.actor_id, f"{target.label} declines Heal.")] + self._complete_action(state, caster, [], dice=dice)
            healing = heal_roll(continuation.spell_actions, dice.draw)
            events = self._apply_healing(state, caster, target, healing.total, healing.rolls, continuation)
            continuation.stage = "done"
            return events + self._complete_action(state, caster, [], dice=dice)

        if pending.kind == "guidance_use":
            continuation = pending.continuation
            effect = next((item for item in state.active_effects if item.effect_id == pending.effect_id), None)
            if continuation is None or effect is None:
                raise _Rejected("The Guidance effect is no longer available.")
            events: list[Event] = []
            if command.option_id == "use":
                state.active_effects.remove(effect)
                state.guidance_immunities[effect.target_actor_id] = state.round_number + 600
                continuation.guidance_bonus = 1
                events.append(Event("guidance_used", effect.source_actor_id, effect.target_actor_id, "Guidance is consumed for +1 status to this check; the target becomes immune for one hour."))
            else:
                events.append(Event("guidance_kept", effect.source_actor_id, effect.target_actor_id, "Guidance is retained for a later eligible check."))
            continuation.guidance_checked = True
            if pending.check_kind == "weapon_attack":
                attacker = state.creatures[continuation.actor_id]
                target = state.creatures[continuation.target_id or ""]
                attack = self._find_attack(attacker, continuation.attack_id)
                if attack is None:
                    raise _Rejected("The guided Strike is no longer available.")
                context = ActionContinuation(
                    kind="reaction_strike" if pending.is_reaction else ("ranged_strike" if "ranged" in attack.traits else "strike"),
                    actor_id=attacker.actor_id, target_id=target.actor_id,
                    attack_id=attack.attack_id, damage_type=continuation.damage_type,
                    nonlethal=continuation.nonlethal, attack_penalty=continuation.attack_penalty,
                    attack_count=continuation.attack_count,
                    attack_actions_cost=continuation.attack_actions_cost,
                    attack_count_cost=continuation.attack_count_cost,
                    damage_bonus_dice=continuation.damage_bonus_dice,
                    ranged_penalty=continuation.ranged_penalty,
                    guidance_bonus=continuation.guidance_bonus,
                    guidance_checked=True,
                )
                events.extend(self._roll_strike(state, dice, attacker, target, attack, context, parent=continuation.parent_continuation))
            else:
                events.extend(self._resolve_cast(state, dice, continuation))
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
                events.extend(self._resolve_divine_lance_result(state, dice, caster, target, check, continuation))
            else:
                events.extend(self._resolve_void_warp_result(state, dice, caster, target, check, continuation))
            return events

        if pending.kind == "attack_hero_reroll":
            actor = state.creatures[pending.actor_id or ""]
            target = state.creatures[pending.target_id or ""]
            attack = self._find_attack(actor, pending.attack_id)
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
                is_reaction=pending.is_reaction,
                continuation=pending.continuation,
            ))
            return events

        if pending.kind == "recovery_start_heroic":
            actor = state.creatures[pending.actor_id or ""]
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
                actor.reaction_available = "reactive_strike" in get_definition(actor.definition_id).abilities
                events.append(Event("turn_started", actor.actor_id, None, f"{actor.label} regains 3 actions and 1 reaction."))
            return events

        if pending.kind == "recovery_heroic_increase":
            actor = state.creatures[pending.actor_id or ""]
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
                actor.reaction_available = "reactive_strike" in get_definition(actor.definition_id).abilities
                events.append(Event("turn_started", actor.actor_id, None, f"{actor.label} regains 3 actions and 1 reaction."))
            return events

        if pending.kind == "heroic_recovery_damage":
            target = state.creatures[pending.target_id or ""]
            transition = pending.health_heroic if command.option_id == "heroic_recovery" else pending.health_normal
            assert isinstance(transition, HealthTransition)
            if command.option_id == "heroic_recovery":
                target.hero_points -= transition.hero_points_spent
            self._apply_health_transition(state, target, transition)
            events = []
            if pending.damage_result is not None and pending.damage_text:
                events.append(Event("damage", pending.actor_id, target.actor_id, pending.damage_text, damage=pending.damage_result))
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
                if state.in_progress and actor.actions_remaining == 0 and state.pending_choice is None:
                    events.extend(self._end_turn(state, actor, early=False, dice=dice))
            return events

        raise _Rejected(f"Unsupported pending choice kind {pending.kind!r}.")

    def _advance_after_incapacitated_turn(self, state, dice):
        actor = state.creatures[state.initiative_order[state.active_index]]
        actor.actions_remaining = 0
        actor.reaction_available = False
        events: list[Event] = []
        self._finish_if_team_defeated(state)
        if not state.in_progress:
            return events
        for _ in range(len(state.initiative_order)):
            next_index = (state.active_index + 1) % len(state.initiative_order)
            if next_index == 0:
                state.round_number += 1
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
                self._set_pending(
                    state,
                    kind="initiative_hero_reroll",
                    owner_actor_id=actor.actor_id,
                    prompt=f"{actor.label} may keep initiative or spend 1 Hero Point to reroll.",
                    options=(ChoiceOption("keep", "Keep initiative"), ChoiceOption("spend_hero_point", "Spend 1 Hero Point and reroll")),
                    details=(f"Original: d20 {actor.initiative - definition.perception} + {definition.perception} = {actor.initiative}.",),
                    actor_id=actor.actor_id,
                    initiative_roll=actor.initiative - definition.perception,
                    initiative_modifier=definition.perception,
                )
                return
        self._prepare_initiative_order(state)
        self._continue_tie_choices(state)

    def _prepare_initiative_order(self, state: EncounterState) -> None:
        setup = get_setup(state.setup_id)
        setup_index = {placement.actor_id: index for index, placement in enumerate(setup.placements)}
        grouped: dict[int, list[str]] = {}
        for actor_id, creature in state.creatures.items():
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
            for creature in state.creatures.values():
                if not creature.defeated:
                    creature.reaction_available = "reactive_strike" in get_definition(creature.definition_id).abilities
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
        attacker_critical: bool = False,
        target_critical_failure: bool = False,
        nonlethal: bool = False,
        hero_points: int | None = None,
    ) -> HealthTransition:
        """Use one PC-health path for weapon and spell damage outcomes."""
        return pc_damage(
            self._health_state(target),
            amount,
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
) -> tuple[Modifier, ...]:
    modifiers = [Modifier(attack.modifier - (enfeebled if attack.attack_attribute == "strength" else 0), "untyped", "printed attack modifier")]
    if map_penalty:
        modifiers.append(Modifier(map_penalty, "untyped", "multiple attack penalty"))
    if ranged_penalty:
        modifiers.append(Modifier(ranged_penalty, "untyped", "range increment penalty"))
    if guidance_bonus:
        modifiers.append(Modifier(guidance_bonus, "status", "Guidance"))
    trait_default = "nonlethal" in attack.traits
    if nonlethal != trait_default:
        modifiers.append(Modifier(-2, "circumstance", "nonlethal intent"))
    if prone:
        modifiers.append(Modifier(-2, "circumstance", "prone attack penalty"))
    return tuple(modifiers)


def _spell_attack_text(check) -> str:
    return (
        f"Divine Lance attack: d20 {check.die} + {check.modifier} = {check.total} "
        f"vs AC {check.dc}; {check.degree.label().lower()}."
    )


def _spell_save_text(target, check) -> str:
    return (
        f"{target.label} Fortitude save: d20 {check.die} + {check.modifier} = "
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
    if len({placement.position for placement in setup.placements}) != len(setup.placements):
        raise ValueError("starting actor positions cannot overlap")
    for placement in setup.placements:
        if not placement.actor_id or not placement.label or not placement.team:
            raise ValueError("each actor needs an id, label, and team")
        if not isinstance(placement.position, Position):
            raise ValueError(f"starting position for {placement.actor_id!r} is invalid")
        if not in_bounds(placement.position, setup.width, setup.height):
            raise ValueError(f"starting position for {placement.actor_id!r} is outside the map")
        definition = get_definition(placement.definition_id)
        if not definition.grounded or definition.footprint_cells != 1:
            raise ValueError("supported actors are grounded and occupy one grid square")
        try:
            mode = HealthMode(definition.health_mode)
        except ValueError as error:
            raise ValueError(f"actor {placement.actor_id!r} has an unsupported health mode") from error
        if mode is HealthMode.PC and not 0 <= definition.hero_points <= 3:
            raise ValueError("PC Hero Points must be from zero through three")


def _coord(position: Position) -> str:
    return f"{chr(ord('A') + position.x)}{position.y + 1}"


def _damage_text(
    damage: DamageResult,
    dice_sides: tuple[int, ...],
    defeated: bool,
    *,
    bonus_dice: int = 0,
) -> str:
    component = damage.components[0]
    dice_counts: dict[int, int] = {}
    for sides in dice_sides + ((dice_sides[0],) * bonus_dice if dice_sides else ()):
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
