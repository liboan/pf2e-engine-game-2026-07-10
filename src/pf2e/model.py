"""Typed definitions, commands, state, and public results for the prototype."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from .checks import CheckResult
from .damage import DamageResult
from .health import HealthTransition


@dataclass(frozen=True, order=True)
class Position:
    x: int
    y: int


class HealthMode(str, Enum):
    """Health behavior explicitly admitted for a creature definition."""

    PROTOTYPE = "prototype"
    ORDINARY = "ordinary"
    PC = "pc"


@dataclass(frozen=True)
class AttackDefinition:
    attack_id: str
    name: str
    modifier: int
    reach_ft: int
    traits: frozenset[str]
    damage_type: str
    damage_dice: tuple[int, ...]
    damage_modifier: int
    item_id: str | None = None
    attack_attribute: str = "strength"
    damage_attribute: str | None = "strength"
    range_increment_ft: int | None = None
    max_range_ft: int | None = None
    hands_required: int = 1
    free_hands_required: int = 0
    ammunition_id: str | None = None
    deadly_die: int | None = None


@dataclass(frozen=True)
class PreparedSpellDefinition:
    slot_id: str
    source: str
    spell_id: str
    rank: int = 1
    cantrip: bool = False


@dataclass(frozen=True)
class CreatureDefinition:
    definition_id: str
    name: str
    hp: int
    ac: int
    perception: int
    land_speed_ft: int
    attacks: tuple[AttackDefinition, ...]
    kind: str = "synthetic_npc"
    grounded: bool = True
    footprint_cells: int = 1
    health_mode: HealthMode = HealthMode.PROTOTYPE
    abilities: tuple[str, ...] = ()
    feats: tuple[str, ...] = ()
    ability_modifiers: tuple[tuple[str, int], ...] = ()
    skills: tuple[tuple[str, str | None, int], ...] = ()
    saves: tuple[tuple[str, str | None, int], ...] = ()
    proficiencies: tuple[tuple[str, str], ...] = ()
    senses: tuple[str, ...] = ()
    sheet_notes: tuple[str, ...] = ()
    held_items: tuple[str, ...] = ()
    worn_items: tuple[str, ...] = ()
    stowed_items: tuple[str, ...] = ()
    hero_points: int = 0
    size: str = "medium"
    level: int = 1
    ancestry: str | None = None
    heritage: str | None = None
    background: str | None = None
    class_name: str | None = None
    deity: str | None = None
    languages: tuple[str, ...] = ()
    class_dc: int | None = None
    prepared_spells: tuple[PreparedSpellDefinition, ...] = ()
    spell_attack: int | None = None
    spell_dc: int | None = None
    spell_attribute: str | None = None
    spell_sanctification: str | None = None
    ammunition: tuple[tuple[str, int], ...] = ()


@dataclass(frozen=True)
class CreaturePlacement:
    actor_id: str
    definition_id: str
    label: str
    team: str
    position: Position


@dataclass(frozen=True)
class EncounterSetup:
    setup_id: str
    name: str
    width: int
    height: int
    placements: tuple[CreaturePlacement, ...]
    # Ties between these two GM-controlled synthetic actors follow setup order.
    tie_policy: str = "stable_setup_order"


@dataclass(frozen=True)
class Stride:
    path: tuple[Position, ...]


@dataclass(frozen=True)
class Step:
    destination: Position


@dataclass(frozen=True)
class Strike:
    target_id: str
    attack_id: str | None = None
    damage_type: str | None = None
    nonlethal: bool | None = None


@dataclass(frozen=True)
class ViciousSwing:
    target_id: str
    attack_id: str | None = None
    damage_type: str | None = None
    nonlethal: bool | None = None


@dataclass(frozen=True)
class Cast:
    spell_id: str
    target_id: str | None = None
    actions: int | None = None
    slot_id: str | None = None
    include_self: bool | None = None


@dataclass(frozen=True)
class TakeCover:
    pass


@dataclass(frozen=True)
class DismissCover:
    pass


@dataclass(frozen=True)
class Interact:
    mode: str
    item_id: str


@dataclass(frozen=True)
class Release:
    item_id: str


@dataclass(frozen=True)
class Stand:
    pass


@dataclass(frozen=True)
class Crawl:
    path: tuple[Position, ...]


@dataclass(frozen=True)
class EndTurn:
    pass


@dataclass(frozen=True)
class Choose:
    choice_id: int
    option_id: str
    actor_id: str | None = None


Command = Stride | Step | Strike | ViciousSwing | Cast | TakeCover | DismissCover | Interact | Release | Stand | Crawl | EndTurn | Choose


class ResultStatus(str, Enum):
    COMPLETED = "completed"
    PAUSED = "paused"
    REJECTED = "rejected"
    UNSUPPORTED = "unsupported"


@dataclass(frozen=True)
class Event:
    kind: str
    actor_id: str | None
    target_id: str | None
    text: str
    check: CheckResult | None = None
    damage: DamageResult | None = None
    position: Position | None = None
    details: tuple[str, ...] = ()


@dataclass(frozen=True)
class ChoiceOption:
    option_id: str
    label: str


@dataclass(frozen=True)
class ChoiceView:
    choice_id: int
    kind: str
    owner_actor_id: str | None
    prompt: str
    options: tuple[ChoiceOption, ...]
    details: tuple[str, ...] = ()


@dataclass(frozen=True)
class ActorView:
    actor_id: str
    label: str
    team: str
    position: Position
    hp: int
    max_hp: int
    defeated: bool
    initiative: int
    actions_remaining: int
    strikes_this_turn: int
    diagonals_this_turn: int
    health_mode: HealthMode = HealthMode.PROTOTYPE
    dying: int = 0
    wounded: int = 0
    unconscious: bool = False
    dead: bool = False
    prone: bool = False
    hero_points: int = 0
    reaction_available: bool = False
    held_items: tuple[str, ...] = ()
    worn_items: tuple[str, ...] = ()
    stowed_items: tuple[str, ...] = ()
    prepared_slots: tuple["PreparedSlotView", ...] = ()
    ammunition: tuple[tuple[str, int], ...] = ()
    effects: tuple["EffectView", ...] = ()
    guidance_immune_until_round: int | None = None
    taking_cover: bool = False
    ability_modifiers: tuple[tuple[str, int], ...] = ()
    skills: tuple[tuple[str, str | None, int], ...] = ()
    saves: tuple[tuple[str, str | None, int], ...] = ()
    proficiencies: tuple[tuple[str, str], ...] = ()
    senses: tuple[str, ...] = ()
    sheet_notes: tuple[str, ...] = ()
    abilities: tuple[str, ...] = ()
    feats: tuple[str, ...] = ()
    size: str = "medium"
    level: int = 1
    ancestry: str | None = None
    heritage: str | None = None
    background: str | None = None
    class_name: str | None = None
    deity: str | None = None
    languages: tuple[str, ...] = ()
    class_dc: int | None = None
    ac: int = 0
    perception: int = 0


@dataclass(frozen=True)
class Inspection:
    in_progress: bool
    round_number: int
    turn_actor_id: str | None
    actors: tuple[ActorView, ...]
    map_width: int
    map_height: int
    winner_team: str | None
    choice: ChoiceView | None = None
    ground_items: tuple[tuple[Position, tuple[str, ...]], ...] = ()


@dataclass(frozen=True)
class ActionOptions:
    actor_id: str | None
    actions_remaining: int
    can_stride: bool
    can_step: bool
    can_strike: bool
    can_end_turn: bool
    strike_targets: tuple[str, ...]
    step_destinations: tuple[Position, ...]
    available_actions: tuple[str, ...] = ()
    capabilities: tuple[str, ...] = ()
    strikes: tuple[StrikeOption, ...] = ()
    interact_options: tuple[tuple[str, str], ...] = ()
    spells: tuple["SpellOption", ...] = ()


@dataclass(frozen=True)
class StrikeOption:
    attack_id: str
    name: str
    targets: tuple[str, ...]
    damage_types: tuple[str, ...]
    default_damage_type: str
    default_nonlethal: bool


@dataclass(frozen=True)
class SpellTargetOption:
    actions: int
    targets: tuple[str, ...]
    include_self_available: bool = False
    traits: tuple[str, ...] = ()


@dataclass(frozen=True)
class SpellOption:
    spell_id: str
    name: str
    traits: tuple[str, ...]
    action_costs: tuple[int, ...]
    slots: tuple[tuple[str, str], ...] = ()
    target_options: tuple[SpellTargetOption, ...] = ()
    unavailable_reason: str | None = None
    cantrip: bool = False


@dataclass(frozen=True)
class PreparedSlotView:
    slot_id: str
    source: str
    spell_id: str
    rank: int
    cantrip: bool
    spent: bool


@dataclass(frozen=True)
class EffectView:
    kind: str
    source_actor_id: str
    target_actor_id: str
    value: int
    expires_at_source_start: int


@dataclass(frozen=True)
class ActionResult:
    status: ResultStatus
    events: tuple[Event, ...]
    message: str
    inspection: Inspection


@dataclass
class CreatureState:
    actor_id: str
    definition_id: str
    label: str
    team: str
    position: Position
    hp: int
    initiative: int = 0
    actions_remaining: int = 0
    strikes_this_turn: int = 0
    diagonals_this_turn: int = 0
    health_mode: HealthMode = HealthMode.PROTOTYPE
    dying: int = 0
    wounded: int = 0
    unconscious: bool = False
    dead: bool = False
    prone: bool = False
    hero_points: int = 0
    reaction_available: bool = False
    held_items: list[str] = field(default_factory=list)
    worn_items: list[str] = field(default_factory=list)
    stowed_items: list[str] = field(default_factory=list)
    ammunition: dict[str, int] = field(default_factory=dict)
    prepared_slots: list["PreparedSlotState"] = field(default_factory=list)
    flourish_used_round: int = 0
    must_leave_occupied: bool = False

    @property
    def defeated(self) -> bool:
        if self.health_mode is HealthMode.PC:
            return self.dead
        if self.health_mode is HealthMode.ORDINARY:
            return self.dead or self.hp <= 0
        return self.hp <= 0


def is_combat_capable(creature: CreatureState) -> bool:
    """Whether a creature can keep its team in an active encounter.

    An unconscious PC remains present and healable, but cannot keep a team
    fighting on their own. Keep this outcome rule separate from ``defeated``,
    which has other gameplay uses such as occupancy and Pack Attack.
    """
    return not creature.defeated and not creature.unconscious and not creature.dead


@dataclass
class PendingChoice:
    """A small persisted continuation for a real player/GM decision."""

    choice_id: int
    kind: str
    owner_actor_id: str | None
    prompt: str
    options: tuple[ChoiceOption, ...]
    details: tuple[str, ...] = ()
    actor_id: str | None = None
    target_id: str | None = None
    attack_id: str | None = None
    attack_penalty: int = 0
    attack_count: int = 0
    check: CheckResult | None = None
    damage_result: DamageResult | None = None
    damage_text: str | None = None
    attack_critical: bool = False
    initiative_roll: int | None = None
    initiative_modifier: int | None = None
    tie_candidates: tuple[str, ...] = ()
    tie_selected: tuple[str, ...] = ()
    health_normal: HealthTransition | None = None
    health_heroic: HealthTransition | None = None
    transition_kind: str | None = None
    damage_type: str | None = None
    nonlethal: bool = False
    damage_bonus_dice: int = 0
    attack_actions_cost: int = 1
    attack_count_cost: int = 1
    ranged_penalty: int = 0
    guidance_bonus: int = 0
    is_reaction: bool = False
    continuation: ActionContinuation | None = None
    check_kind: str | None = None
    check_owner_actor_id: str | None = None
    spell_id: str | None = None
    slot_id: str | None = None
    actions_cost: int = 0
    spell_actions: int = 0
    include_self: bool | None = None
    effect_id: str | None = None
    damage_adjustment: str | None = None
    damage_context: str | None = None
    target_ids: tuple[str, ...] = ()


@dataclass
class ActionContinuation:
    """Saved remaining work for an action interrupted by a reaction."""

    kind: str
    actor_id: str
    path: tuple[Position, ...] = ()
    next_step: int = 0
    mode: str | None = None
    item_id: str | None = None
    target_id: str | None = None
    attack_id: str | None = None
    damage_type: str | None = None
    nonlethal: bool = False
    damage_bonus_dice: int = 0
    attack_actions_cost: int = 1
    attack_count_cost: int = 1
    attack_penalty: int = 0
    attack_count: int = 1
    seen_reactors: list[str] = field(default_factory=list)
    must_disrupt_on_critical: bool = False
    vicious_swing: bool = False
    movement_kind: str | None = None
    reaction_trigger: str | None = None
    spell_id: str | None = None
    spell_target_id: str | None = None
    slot_id: str | None = None
    spell_actions: int = 0
    include_self: bool | None = None
    spell_damage: DamageResult | None = None
    spell_check: CheckResult | None = None
    spell_save_degree: int | None = None
    target_ids: tuple[str, ...] = ()
    ranged_penalty: int = 0
    guidance_bonus: int = 0
    guidance_checked: bool = False
    stage: str | None = None
    parent_continuation: ActionContinuation | None = None
    attack_count_committed: bool = False


@dataclass
class PreparedSlotState:
    slot_id: str
    source: str
    spell_id: str
    rank: int
    cantrip: bool
    spent: bool = False


@dataclass(frozen=True)
class ActiveSpellEffect:
    effect_id: str
    kind: str
    source_actor_id: str
    target_actor_id: str
    value: int
    expires_at_source_start: int


@dataclass(frozen=True)
class GuidanceImmunity:
    target_actor_id: str
    expires_at_round: int


@dataclass
class EncounterState:
    setup_id: str
    map_width: int
    map_height: int
    creatures: dict[str, CreatureState]
    initiative_order: list[str]
    active_index: int
    round_number: int = 1
    in_progress: bool = True
    winner_team: str | None = None
    initiative_finalized: bool = True
    pending_choice: PendingChoice | None = None
    next_choice_id: int = 1
    initiative_hero_decided: set[str] = field(default_factory=set)
    ground_items: dict[Position, list[str]] = field(default_factory=dict)
    initiative_tie_groups: list[tuple[str, ...]] = field(default_factory=list)
    initiative_tie_orders: dict[int, list[str]] = field(default_factory=dict)
    initiative_tie_group_index: int = 0
    initiative_reordered: set[str] = field(default_factory=set)
    actor_start_counts: dict[str, int] = field(default_factory=dict)
    active_effects: list[ActiveSpellEffect] = field(default_factory=list)
    guidance_immunities: dict[str, int] = field(default_factory=dict)
    taking_cover: set[str] = field(default_factory=set)
