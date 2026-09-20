"""Typed definitions, commands, state, and public results for the prototype."""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from enum import Enum

from .checks import CheckResult, Modifier
from .conditions import ActionContext, CheckContext, ConditionValue
from .damage import DamageDefense, DamageGroup, DamageResult, DefenseChoice, DefenseSelection
from .health import HealthTransition
from .items import ItemInstance


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
    reload: int | None = None
    striking_applies: bool = True

    def __post_init__(self) -> None:
        if self.reload is not None and (type(self.reload) is not int or self.reload < 0):
            raise ValueError("reload must be a non-negative integer or None")
        if type(self.striking_applies) is not bool:
            raise ValueError("striking_applies must be a boolean")


@dataclass(frozen=True)
class PreparedSpellDefinition:
    slot_id: str
    source: str
    spell_id: str
    rank: int = 1
    cantrip: bool = False


@dataclass(frozen=True)
class SpontaneousSpellDefinition:
    """One explicitly known spell in a spontaneous repertoire."""

    spell_id: str
    rank: int = 1
    cantrip: bool = False
    signature: bool = False


@dataclass(frozen=True)
class SpontaneousSlotDefinition:
    """One rank pool owned by a spontaneous casting source."""

    slot_id: str
    source: str
    rank: int = 1
    capacity: int = 1


@dataclass(frozen=True)
class SpontaneousSlotView:
    slot_id: str
    source: str
    rank: int
    capacity: int
    remaining: int


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
    # The first lighting slice admits only explicitly declared ordinary or
    # low-light vision. Leave this unset by default instead of inferring it
    # from descriptive sense strings.
    vision: str | None = None
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
    spontaneous_spells: tuple[SpontaneousSpellDefinition, ...] = ()
    spontaneous_slots: tuple[SpontaneousSlotDefinition, ...] = ()
    spontaneous_source: str = "repertoire"
    focus_spells: tuple[SpontaneousSpellDefinition, ...] = ()
    focus_source: str = "focus"
    focus_points: int = 0
    focus_capacity: int = 0
    spell_tradition: str | None = None
    spell_attack: int | None = None
    spell_dc: int | None = None
    spell_attribute: str | None = None
    spell_sanctification: str | None = None
    ammunition: tuple[tuple[str, int], ...] = ()
    armor_category: str | None = None
    carried_item_bulk: tuple[tuple[str, int], ...] = ()
    damage_defenses: tuple[DamageDefense, ...] = ()
    item_instances: tuple[ItemInstance, ...] = ()
    # Spell Substitution is kept as a finite owned-book ledger for the one
    # staged Wizard. It is not a general spellbook/catalogue model.
    spell_substitution_book_id: str | None = None
    spell_substitution_book: tuple["SpellbookSpellDefinition", ...] = ()
    # Familiars are present, targetable creatures but do not receive an
    # independent initiative turn.  Their owner supplies their finite actions.
    initiative_exempt: bool = False
    familiar_owner_actor_id: str | None = None


@dataclass(frozen=True)
class CreaturePlacement:
    actor_id: str
    definition_id: str
    label: str
    team: str
    position: Position
    # Perception is the normal encounter initiative statistic.  A placement
    # may author another trained statistic when the encounter establishes the
    # required context (for example Deception in an observed social scene).
    initiative_skill: str = "perception"
    initiative_context: str | None = None


@dataclass(frozen=True)
class EncounterSetup:
    setup_id: str
    name: str
    width: int
    height: int
    placements: tuple[CreaturePlacement, ...]
    # Ties between these two GM-controlled synthetic actors follow setup order.
    tie_policy: str = "stable_setup_order"
    # The first Flee slice only admits a finite room with a physical boundary.
    # Open edges and exits remain unsupported until a setup supplies a richer
    # environment fact.
    closed_boundary: bool = False
    # Ambient illumination for this local scene.  Existing setups retain the
    # bright default; the Light prerequisite adds a dim diagnostic fixture.
    ambient_light: str = "bright"
    # Finite environmental provenance for Storm Born. These never stand in
    # for darkness, cover, or ordinary weapon targeting.
    weather_ranged_spell_attack_circumstance_penalty: int = 0
    weather_perception_circumstance_penalty: int = 0
    weather_concealment: bool = False
    # Authored Recall Knowledge subjects/questions for a scene.  The tuple is
    # intentionally opaque to the core model; Investigator owns the concrete
    # record and its rule interpretation.
    knowledge: tuple[object, ...] = ()
    # Authored outside-combat Forensic Acumen examination records. The tuple
    # remains opaque to the core model; Investigator owns their interpretation.
    examinations: tuple[object, ...] = ()
    # Authored On the Case records. The tuple remains opaque to the core
    # model; Investigator owns the literal case and clue interpretation.
    investigations: tuple[object, ...] = ()
    # Finite authored Streetwise questions for this settlement. Investigator
    # owns the record interpretation and persistence of its separate paths.
    streetwise: tuple[object, ...] = ()
    # Finite Animal Empathy dialogue records. Druid owns their meaning.
    animal_empathy: tuple[object, ...] = ()


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
    # Optional stable physical item identity. Appended to preserve legacy
    # positional command construction.
    item_id: str | None = None
    # Investigator Devise a Stratagem attack mode may explicitly choose
    # Intelligence for the eligible Strike. ``None`` keeps ordinary Strikes
    # on their printed attribute and preserves legacy construction.
    use_intelligence: bool | None = None


@dataclass(frozen=True)
class QuickBomber:
    """Draw one authored bomb and make its Strike as one action."""

    target_id: str
    formula_id: str
    only_primary_splash: bool = False


@dataclass(frozen=True)
class QuickAlchemy:
    """Create one finite infused consumable or temporary Quick Vial."""

    mode: str
    formula_id: str | None = None


@dataclass(frozen=True)
class ActivateAlchemy:
    """Use one held selected infused formula item on a literal recipient."""

    item_id: str
    target_id: str | None = None


@dataclass(frozen=True)
class ViciousSwing:
    target_id: str
    attack_id: str | None = None
    damage_type: str | None = None
    nonlethal: bool | None = None
    # Optional stable physical item identity. Appended to preserve legacy
    # positional command construction.
    item_id: str | None = None


@dataclass(frozen=True)
class Cast:
    spell_id: str
    target_id: str | None = None
    actions: int | None = None
    slot_id: str | None = None
    include_self: bool | None = None
    # Stable physical item identity for item-targeted spells such as Runic
    # Weapon. Appended to preserve all legacy positional Cast construction.
    item_id: str | None = None
    # Point and attachment intent for the rank-1 Light cantrip. These fields
    # are appended so all legacy positional Cast construction remains valid.
    point: Position | None = None
    color: str | None = None
    attachment_actor_id: str | None = None
    replacement_orb_id: str | None = None
    # Force Barrage allocates one shard per action. This literal list keeps
    # each target selection atomic without changing existing single-target
    # Cast construction.
    target_ids: tuple[str, ...] | None = None
    # Direction vector for the finite Breathe Fire cone template. Kept
    # independent of Light's point-targeted intent.
    area_direction: Position | None = None
    # Consume the current-turn Arcane Bond permission for this prepared cast.
    use_arcane_bond: bool = False
    # Finite printed attack-profile choice for cantrips such as Ignition and
    # Gouging Claw. ``None`` is only valid for spells without such a choice.
    spell_mode: str | None = None


@dataclass(frozen=True)
class LingeringComposition:
    """Prepare the Maestro's next one-round composition cantrip."""

    pass


@dataclass(frozen=True)
class Sustain:
    """Sustain one of the caster's Light orbs for one concentrate action.

    ``point`` moves or detaches the orb at a chosen grid point.  Supplying
    ``attachment_actor_id`` instead moves the orb to that actor's current
    space and presents the existing willingness choice before attaching it.
    For an attached orb, omitting both fields detaches it in the carrier's
    current space.
    """

    orb_id: str
    point: Position | None = None
    attachment_actor_id: str | None = None


@dataclass(frozen=True)
class Dismiss:
    """Dismiss one bounded owned spell effect or Light orb."""

    orb_id: str | None = None
    effect_id: str | None = None


# Descriptive aliases keep callers free to distinguish these from any future
# generic Sustain/Dismiss actions while retaining one command implementation.
SustainLight = Sustain
DismissLight = Dismiss


@dataclass(frozen=True)
class TakeCover:
    pass


@dataclass(frozen=True)
class DismissCover:
    pass


@dataclass(frozen=True)
class RaiseShield:
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
class Flee:
    """Use one action to pursue escape from a current fleeing source."""

    pass


@dataclass(frozen=True)
class EndTurn:
    pass


@dataclass(frozen=True)
class Choose:
    choice_id: int
    option_id: str
    actor_id: str | None = None


class FamilyCommand:
    """Marker base for an explicit class-family action command.

    Family modules define their own frozen command records and set a fixed
    ``family_id`` (martial, casting, items, or minions). Encounter handles
    these through a small explicit procedure dispatch while retaining its
    usual atomic draft and dice transaction.
    """

    family_id: str


@dataclass(frozen=True)
class ReachSpell(FamilyCommand):
    """Ready the selected caster's next eligible ranged or touch spell."""

    family_id = "casting"


@dataclass(frozen=True)
class LayOnHands(FamilyCommand):
    """One-action living-target devotion healing."""

    family_id = "martial"
    target_id: str


@dataclass(frozen=True)
class SuppressAura(FamilyCommand):
    """Suppress the acting Champion's divine aura."""

    family_id = "martial"


@dataclass(frozen=True)
class ResumeAura(FamilyCommand):
    """Resume the acting Champion's divine aura."""

    family_id = "martial"


@dataclass(frozen=True)
class ToggleAura(FamilyCommand):
    """Set the acting Champion's divine aura state explicitly."""

    family_id = "martial"
    active: bool


Command = Stride | Step | Strike | QuickBomber | QuickAlchemy | ActivateAlchemy | ViciousSwing | Cast | LingeringComposition | Sustain | Dismiss | TakeCover | DismissCover | RaiseShield | Interact | Release | Stand | Crawl | Flee | EndTurn | Choose | FamilyCommand


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
    temporary_hp_absorbed: int = 0
    remaining_hp_damage: int = 0
    original_damage: DamageResult | None = None
    shield_block: "ShieldBlockRecord | None" = None


@dataclass(frozen=True)
class FamilyProcedureResult:
    """Result returned by one explicit family action procedure."""

    events: tuple[Event, ...] = ()
    rejection: str | None = None
    unsupported: str | None = None


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
    initiative_skill: str = "perception"
    initiative_context: str | None = None
    health_mode: HealthMode = HealthMode.PROTOTYPE
    temporary_hp_source_id: str | None = None
    temporary_hp_expires_at_seconds: int | None = None
    temporary_hp_expires_at_source_start: int = 0
    barbarian_state: "BarbarianState | None" = None
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
    spontaneous_slots: tuple["SpontaneousSlotView", ...] = ()
    focus_points: int = 0
    focus_capacity: int = 0
    ammunition: tuple[tuple[str, int], ...] = ()
    effects: tuple["EffectView", ...] = ()
    guidance_immune_until_round: int | None = None
    # Absolute wall-clock deadline for the one-hour Guidance immunity.
    # ``guidance_immune_until_round`` remains as a compatibility projection
    # for callers written against the original combat-only interface.
    guidance_immune_until_seconds: int | None = None
    sure_strike_immune_until_seconds: int | None = None
    taking_cover: bool = False
    ability_modifiers: tuple[tuple[str, int], ...] = ()
    skills: tuple[tuple[str, str | None, int], ...] = ()
    saves: tuple[tuple[str, str | None, int], ...] = ()
    proficiencies: tuple[tuple[str, str], ...] = ()
    senses: tuple[str, ...] = ()
    vision: str | None = None
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
    speed_ft: int = 0
    panache: bool = False
    panache_expires_at_end: int | None = None
    finisher_used_this_turn: bool = False
    temporary_hp: int = 0
    condition_effects: tuple["ActiveConditionEffect", ...] = ()
    hunted_prey: "HuntedPreyState | None" = None
    shields: tuple["ShieldView", ...] = ()

    @property
    def speed(self) -> int:
        """Compatibility alias for callers that call Speed simply ``speed``."""

        return self.speed_ft


@dataclass(frozen=True)
class ShieldView:
    instance_id: str
    definition_id: str
    hp: int
    max_hp: int
    broken_threshold: int
    hardness: int
    ac_bonus: int
    broken: bool
    raised: bool
    ac_bonus_active: bool


@dataclass(frozen=True)
class Inspection:
    in_progress: bool
    round_number: int
    turn_actor_id: str | None
    actors: tuple[ActorView, ...]
    map_width: int
    map_height: int
    winner_team: str | None
    ambient_light: str = "bright"
    choice: ChoiceView | None = None
    ground_items: tuple[tuple[Position, tuple[str, ...]], ...] = ()
    light_orbs: tuple["LightOrb", ...] = ()
    world_time_seconds: int = 0
    encounter_start_seconds: int = 0
    preparation_day: int = 1
    rested_actor_ids: tuple[str, ...] = ()
    last_prepared_day: tuple[tuple[str, int], ...] = ()


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
    # Target of the acting Investigator's still-valid attack stratagem, when
    # one is available for the current owner turn.
    investigator_stratagem_target_id: str | None = None
    # Engine-computed living ally targets for the selected Investigator's
    # Battle Medicine action.
    battle_medicine_targets: tuple[str, ...] = ()
    # Engine-computed target ids for authored Recall Knowledge subjects.
    recall_knowledge_targets: tuple[str, ...] = ()
    # Source-legal targets for the selected Investigator's Person of Interest
    # action after the shared action/cooldown gates are applied.
    person_of_interest_targets: tuple[str, ...] = ()


@dataclass(frozen=True)
class StrikeOption:
    attack_id: str
    name: str
    targets: tuple[str, ...]
    damage_types: tuple[str, ...]
    default_damage_type: str
    default_nonlethal: bool
    intelligence_substitution_available: bool = False


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
    expires_at_world_time: int | None = None


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
    spontaneous_slots: list["SpontaneousSlotState"] = field(default_factory=list)
    focus_points: int = 0
    focus_capacity: int = 0
    flourish_used_round: int = 0
    # Composition's once-per-turn limit belongs to the source turn, not to an
    # active effect. The marker is persisted because an extended composition
    # may be saved before a later turn replaces it.
    composition_cast_at_start: int = 0
    # A composition can also be cast as an off-turn reaction. The source
    # start count above remains the expiry marker; these identify the actual
    # current turn that consumed the composition allowance.
    composition_cast_turn_actor_id: str | None = None
    composition_cast_turn_start: int = 0
    # Lingering Composition is a spellshape free action. It has exactly one
    # legal successor: the next action must cast the qualifying composition.
    lingering_composition_pending: bool = False
    # Reach Spell is a distinct one-spell spellshape marker.  The cast keeps
    # its committed range separately on ActionContinuation.
    reach_spell_pending: bool = False
    must_leave_occupied: bool = False
    temporary_hp: int = 0
    temporary_hp_source_id: str | None = None
    temporary_hp_expires_at_seconds: int | None = None
    temporary_hp_expires_at_source_start: int = 0
    hunted_prey: "HuntedPreyState | None" = None
    precision_used_round: int = 0
    # Arcane Bond is a literal once-daily, current-turn permission. The
    # completed prepared-slot history stays separate from ordinary slot spend.
    arcane_bond_used_day: int = 0
    arcane_bond_recast_until_start: int = 0
    arcane_bond_item_id: str | None = None
    arcane_bond_eligible_slots: set[str] = field(default_factory=set)
    spell_substitution: "SpellSubstitutionState | None" = None
    # Shield is a literal magical defense rather than an inventory item. Its
    # one-turn raised state and post-Block absolute cooldown must both survive
    # saved combat and scene changes.
    magic_shield_expires_at_start: int = 0
    shield_recast_available_at_seconds: int = 0
    # Swashbuckler Panache is encounter-scoped. A ``None`` expiry means the
    # actor has lasting panache; otherwise the value is the actor-end counter
    # at which temporary panache expires.
    panache: bool = False
    panache_expires_at_end: int | None = None
    # A Finisher bars further attack-trait actions until this actor's turn
    # ends. It is encounter-turn state and therefore must survive saves.
    finisher_used_this_turn: bool = False
    barbarian_state: "BarbarianState | None" = None
    escape_lockout_until_start: int = 0
    # Stunning Blows has a literal next-turn action loss rather than a broad
    # condition framework.  The source remains persisted so restoration can
    # reject a condition attributed to a non-admitted Monk feature.
    stunned: int = 0
    stunned_until_start: int = 0
    stunned_source_actor_id: str | None = None
    # The stored preliminary d20 is an input for the Investigator's first
    # eligible Strike, rather than a CheckResult. Kept on the actor so it is
    # saved even while a reaction or other choice interrupts the action.
    investigator_stratagem: "InvestigatorStratagemState | None" = None
    # Recall Knowledge attempts belong to the investigator and subject, so
    # they survive scene transitions with the carried PC.
    investigator_knowledge_attempts: dict[str, int] = field(default_factory=dict)
    investigator_knowledge_exhausted: set[str] = field(default_factory=set)
    # A body can only be examined once for a given authored examination key;
    # this is separate from subject-keyed Recall Knowledge history so an
    # immediate follow-up may intentionally reuse that subject.
    investigator_examinations_completed: set[str] = field(default_factory=set)
    # On the Case state is keyed by authored case IDs. Questions, clues and
    # useful-creature bindings remain in investigator_content.
    investigator_active_cases: set[str] = field(default_factory=set)
    investigator_solved_cases: set[str] = field(default_factory=set)
    investigator_abandoned_cases: set[str] = field(default_factory=set)
    investigator_awareness: set[str] = field(default_factory=set)
    investigator_lead_cooldown_until: int = 0
    investigator_clue_in_cooldown_until: int = 0
    # Person of Interest is a small, target-specific free-Devise grant.  The
    # class-local record is imported lazily by persistence and procedures to
    # avoid making this shared model own Investigator rules.
    investigator_person_of_interest: "PersonOfInterestState | None" = None
    investigator_person_of_interest_cooldown_until: int = 0
    # Streetwise Recall Knowledge and Gather Information have deliberately
    # separate authored attempt limits. Results carry through scene changes.
    investigator_streetwise_recall_attempts: dict[str, int] = field(default_factory=dict)
    investigator_streetwise_gather_attempts: dict[str, int] = field(default_factory=dict)
    investigator_streetwise_results: dict[str, str] = field(default_factory=dict)
    druid_animal_empathy_attempts: dict[str, int] = field(default_factory=dict)
    druid_animal_empathy_results: dict[str, str] = field(default_factory=dict)
    druid_animal_empathy_attitudes: dict[str, str] = field(default_factory=dict)
    oracle_cursebound: int = 0
    oracle_life_mode: str = "life"
    oracle_life_mode_selected_day: int = 0
    # The selected Faith's Flamekeeper's per-turn patron benefit is deliberately
    # a narrow saved gate.  Familiar recovery timing is intentionally absent.
    witch_patron_used_start: int = 0
    # Patron's Puppet and Restored Spirit have distinct per-turn gates.  Keep
    # their saved counters separate so using the former never suppresses the
    # latter's optional recipient benefit.
    witch_restored_spirit_used_start: int = 0
    # The hex trait permits at most one Cast-a-hex action in a Witch turn.
    witch_hex_cast_start: int = 0
    # A minion receives one two-action allotment per owner turn.
    minion_commanded_start: int = 0
    # Literal turn-begins trigger gate for the selected Patron's Puppet.
    witch_turn_activity_start: int = 0

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
    # Stable physical weapon identity for a saved Strike or Reactive Strike.
    # This is intentionally separate from ``attack_id``: a transferred
    # longsword still backs the same attack profile while retaining its origin
    # instance ID.
    item_id: str | None = None
    attack_penalty: int = 0
    attack_count: int = 0
    check: CheckResult | None = None
    damage_result: DamageResult | None = None
    damage_text: str | None = None
    temporary_hp_absorbed: int = 0
    remaining_hp_damage: int = 0
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
    feint_off_guard_applied: bool = False
    attack_target_off_guard: bool = False
    nimble_dodge_used: bool = False
    is_reaction: bool = False
    continuation: ActionContinuation | None = None
    check_kind: str | None = None
    check_owner_actor_id: str | None = None
    spell_id: str | None = None
    slot_id: str | None = None
    # Exact physical item selected by an item-targeted spell. Keep this
    # separate from ``item_id``, which belongs to Strike/reaction choices.
    spell_target_item_id: str | None = None
    actions_cost: int = 0
    spell_actions: int = 0
    include_self: bool | None = None
    effect_id: str | None = None
    damage_adjustment: str | None = None
    damage_context: str | None = None
    target_ids: tuple[str, ...] = ()
    family_id: str | None = None
    procedure_id: str | None = None
    saved_check: "SavedCheckContext | None" = None
    paired_strike: "PairedStrikeContinuation | None" = None
    barbarian_choice: "RageModeChoice | None" = None
    family_command: "FamilyCommand | None" = None
    damage_resolution: "DamageResolution | None" = None
    damage_result_is_mitigated: bool = False
    # True once the observer-relative DC 5 concealment gate has been resolved
    # or is waiting on its Hero Point decision.  It is distinct from the later
    # attack check and prevents a saved attack reroll from rechecking light.
    concealment_checked: bool = False


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
    # Confident Finisher uses the normal Strike continuation machinery while
    # replacing its damage and applying the Finisher attack lockout.
    finisher: bool = False
    movement_kind: str | None = None
    reaction_trigger: str | None = None
    spell_id: str | None = None
    spell_target_id: str | None = None
    slot_id: str | None = None
    spell_actions: int = 0
    include_self: bool | None = None
    spell_source_kind: str | None = None
    sorcerous_potency: int = 0
    blood_magic_recipient_id: str | None = None
    spell_damage: DamageResult | None = None
    spell_check: CheckResult | None = None
    spell_save_degree: int | None = None
    target_ids: tuple[str, ...] = ()
    spell_area_direction: Position | None = None
    spell_mode: str | None = None
    # Hunter's Aim is a Ranger-procedure-only attack intent.  It remains
    # typed through reaction and saved-decision continuations.
    hunter_aim_intent: "HunterAimIntent | None" = None
    # A positive range is the immutable range committed by Reach Spell; it is
    # never recomputed from the caster's transient pending marker.
    reach_spell_effective_range_ft: int | None = None
    ranged_penalty: int = 0
    guidance_bonus: int = 0
    feint_off_guard_applied: bool = False
    attack_target_off_guard: bool = False
    nimble_dodge_decided: bool = False
    nimble_dodge_used: bool = False
    guidance_checked: bool = False
    # Divine Grace is an optional Champion reaction before a spell save.  Its
    # two markers distinguish declining the reaction from consuming it, so a
    # resumed cast cannot offer or apply it twice.
    divine_grace_checked: bool = False
    divine_grace_used: bool = False
    stage: str | None = None
    parent_continuation: ActionContinuation | None = None
    attack_count_committed: bool = False
    # Item-targeted spell facts remain independent of creature-target fields.
    spell_target_item_id: str | None = None
    spell_target_wielder_id: str | None = None
    concealment_checked: bool = False
    # Light's point/color/attachment intent survives manipulate reactions and
    # a saved choice. The orb is created only once this continuation resolves.
    light_control: str | None = None
    light_point: Position | None = None
    light_color: str | None = None
    light_attachment_actor_id: str | None = None
    light_replacement_orb_id: str | None = None
    light_orb_id: str | None = None
    # A failed observer-relative target gate can still preserve a character
    # benefit (Scoundrel's Step) without fabricating the underlying skill die.
    targeting_failed: bool = False
    # Sure Strike is consumed by the first actual attack roll, after any
    # reaction window. These markers make a saved continuation unambiguous.
    sure_strike_checked: bool = False
    sure_strike_used: bool = False
    # Investigator attack stratagem intent survives every reaction/choice
    # continuation until the actual Strike roll consumes the stored die.
    use_intelligence: bool | None = None
    # Tumble Through reaches its check only after any clear lead-in squares
    # and their movement reactions have resolved. Keep the prepared action
    # facts on that movement continuation so a reaction/save can resume it.
    tumble_command: "FamilyCommand | None" = None
    tumble_saved_check: "SavedCheckContext | None" = None
    tumble_distance: int | None = None
    tumble_origin: Position | None = None
    # Quick Jump carries the resolved Long Jump check through reaction
    # continuations so its failure/critical-failure landing is not a mutable
    # movement-kind string after save/load.
    quick_jump_saved_check: "SavedCheckContext | None" = None
    # A paid paired activity retains this parent while each subordinate Strike
    # passes through the ordinary reaction/check/damage continuation.
    paired_strike: "PairedStrikeContinuation | None" = None
    # Sudden Charge is one paid flourish containing two ordinary Strides and
    # an optional ordinary melee Strike.  Keep both literal paths and the
    # starting square through reactions/save-load; the core revalidates them
    # rather than trusting a later UI submission.
    sudden_charge_second_path: tuple[Position, ...] = ()
    sudden_charge_first_path: tuple[Position, ...] = ()
    sudden_charge_origin: Position | None = None
    sudden_charge_origin_diagonals: int | None = None
    # A reaction that triggers after a movement step retains that departure
    # square so save/load can authenticate its trigger rather than guessing.
    movement_origin: Position | None = None
    # No Escape is one reaction-driven Stride which may continue alongside the
    # triggering creature's remaining movement.  Its literal reactor and
    # unspent Speed keep that forced follow-up local, finite, and saveable.
    no_escape_reactor_id: str | None = None
    no_escape_remaining_speed_ft: int | None = None
    # Stunning Blows pauses after a qualifying Flurry for the Monk's optional
    # rider decision and, for a PC target, that target's ordinary Hero reroll.
    stunning_blows_target_id: str | None = None
    # Bomber may deliberately restrict a bomb splash to its primary target.
    # The chosen scope must survive a Hero/reaction continuation.
    bomber_only_primary_splash: bool = False


@dataclass(frozen=True)
class DamageResolution:
    """Original damage and caller context needed to resume defense choices."""

    source_kind: str
    group: DamageGroup
    actor_id: str
    target_id: str
    source: str
    damage_type: str
    check: CheckResult | None = None
    attack_id: str | None = None
    spell_id: str | None = None
    nonlethal: bool = False
    attacker_critical: bool = False
    attack_target_off_guard: bool = False
    target_critical_failure: bool = False
    damage_bonus_dice: int = 0
    is_reaction: bool = False
    continuation: ActionContinuation | None = None
    enfeebled_on_failure: int = 0
    complete_family_action_on_resume: bool = False
    selections: tuple[DefenseSelection, ...] = ()
    pending_defense_choice: DefenseChoice | None = None
    shield_block_status: str | None = None
    shield_block_instance_id: str | None = None
    shield_block_magic: bool = False
    shield_block_record: "ShieldBlockRecord | None" = None
    # Justice Champion's protection is attached to this damage event, not to
    # the target's ordinary defenses. These facts survive each saved choice.
    justice_checked: bool = False
    justice_actor_id: str | None = None
    justice_protected: bool = False
    # A Life Link reduction is part of this exact damage event.  Keeping the
    # literal effect/source evidence on a saved health choice prevents load
    # validation from either reapplying it or treating its pre-temp-HP result
    # as an accounting mismatch.
    life_link_effect_id: str | None = None
    life_link_source_actor_id: str | None = None
    life_link_transfer: int = 0
    bomber_only_primary_splash: bool = False


@dataclass(frozen=True)
class ShieldBlockRecord:
    shield_instance_id: str
    hardness: int
    incoming_damage: int
    shield_vulnerable_damage: int
    prevented_from_actor: int
    damage_to_actor: int
    damage_to_shield: int
    shield_hp_before: int
    shield_hp_after: int
    magic: bool = False


@dataclass(frozen=True)
class RaisedShieldState:
    instance_id: str
    expires_at_owner_start: int


@dataclass(frozen=True)
class SavedCheckContext:
    """Authoritative facts for a check that may pause and later resume."""

    check_owner_actor_id: str
    context: CheckContext
    dc: int
    modifiers: tuple[Modifier, ...]
    pre_roll_choices: tuple[str, ...] = ()
    result: CheckResult | None = None
    fortune_used: bool = False
    reroll_used: bool = False
    parent_continuation: ActionContinuation | None = None
    attack_id: str | None = None
    # Skill maneuvers commit their attack count before the observer-relative
    # targeting flat check.  This marker keeps resumption from incrementing
    # the same count a second time.
    attack_count_committed: bool = False
    # Unarmed-attack Escape is represented as a saved skill check, so retain
    # the consumed fortune fact alongside the ordinary choice flags.
    sure_strike_used: bool = False


@dataclass(frozen=True)
class HuntedPreyState:
    """One Ranger's current explicitly hunted target."""

    target_actor_id: str


@dataclass(frozen=True)
class PairedStrikeSelection:
    """One selected subordinate Strike in a compound Strike activity."""

    target_id: str
    attack_id: str
    damage_type: str | None = None
    nonlethal: bool | None = None


@dataclass(frozen=True)
class PairedStrikeOutcome:
    """One retained subordinate Strike result, before any grouped defense."""

    target_id: str
    attack_id: str
    check: CheckResult
    damage: DamageResult | None
    damage_type: str
    nonlethal: bool
    hit: bool


@dataclass(frozen=True)
class PairedStrikeContinuation:
    """Typed continuation for an action that makes two separate Strikes."""

    activity_id: str
    owner_actor_id: str
    paid_actions: int
    initial_attack_count: int
    selections: tuple[PairedStrikeSelection, ...] = ()
    next_index: int = 0
    outcomes: tuple[PairedStrikeOutcome, ...] = ()
    stage: str = "selecting"
    # Flurry's same-recipient same-type defenses are allocated chronologically.
    # Weakness is spent once; resistance carries its unused value forward.
    defense_target_id: str | None = None
    defense_damage_type: str | None = None
    spent_weaknesses: tuple[str, ...] = ()
    resistance_remaining: tuple[tuple[str, int], ...] = ()


@dataclass(frozen=True)
class EffectExpiration:
    """Concrete owner-relative duration boundary for one sourced effect."""

    anchor_actor_id: str
    boundary: str
    occurrence: int


@dataclass(frozen=True)
class ActiveConditionEffect:
    """One separately sourced, expiring condition contribution."""

    effect_id: str
    kind: str
    source_actor_id: str
    target_actor_id: str
    value: int
    expiration: EffectExpiration
    dc: int | None = None
    command_mode: str | None = None


@dataclass(frozen=True)
class ConditionImmunity:
    """An action/condition lockout keyed to a source and target."""

    kind: str
    source_actor_id: str
    target_actor_id: str
    expires_at_seconds: int


@dataclass
class PreparedSlotState:
    slot_id: str
    source: str
    spell_id: str
    rank: int
    cantrip: bool
    spent: bool = False


@dataclass(frozen=True)
class SpellbookSpellDefinition:
    """One finite legal entry in the staged Wizard's owned spellbook."""

    spell_id: str
    rank: int
    source: str
    permitted_sources: tuple[str, ...] = ()


@dataclass
class SpellSubstitutionState:
    """Saved ten-minute replacement work before it changes a prepared slot."""

    slot_id: str
    original_spell_id: str
    replacement_spell_id: str
    elapsed_seconds: int = 0


@dataclass
class SpontaneousSlotState:
    """Mutable remaining uses for one spontaneous rank pool."""

    slot_id: str
    source: str
    rank: int
    capacity: int
    remaining: int


@dataclass(frozen=True)
class ActiveSpellEffect:
    effect_id: str
    kind: str
    source_actor_id: str
    target_actor_id: str
    value: int
    expires_at_source_start: int
    expires_at_world_time: int | None = None
    # Sustained spells have an ordinary "through the next turn" deadline and
    # a separate printed total cap.  Stoke uses both; legacy effects leave
    # these at zero.
    sustain_limit_source_start: int = 0
    sustain_limit_world_time: int | None = None
    sustain_expires_at_source_end: int = 0
    # For Forbidding Ward, the enemy whose effects the ward counters.
    selected_enemy_actor_id: str | None = None
    # Life Link reduces only the first qualifying damage event to its target
    # each encounter round.  A round marker belongs to the literal link, not
    # the target, so save/load cannot accidentally replay its reduction.
    life_link_used_round: int = 0


@dataclass(frozen=True)
class PersistentDamageEffect:
    """One literal persistent-damage condition, keyed by target and type."""

    effect_id: str
    source_actor_id: str
    target_actor_id: str
    spell_id: str
    damage_type: str
    dice: tuple[int, ...] = ()
    flat: int = 0
    expires_at_world_time: int | None = None


@dataclass(frozen=True)
class GiantCentipedeVenomAffliction:
    """The selected injury poison's literal ongoing state.

    This stays separate from persistent damage: its DC 17 Fortitude lifecycle
    and stage facts are poison rules, not the generic DC 15 flat recovery rule.
    """

    effect_id: str
    source_actor_id: str
    target_actor_id: str
    dc: int
    stage: int
    expires_at_world_time: int
    next_save_at_target_end: int


@dataclass(frozen=True)
class ActiveItemSpellEffect:
    """One concrete temporary spell effect attached to a physical item.

    Rank-1 Runic Weapon has fixed values, so the record stores only the
    source, exact item identity, and both duration boundaries. The constants
    are exposed as fields with defaults to make the effective profile
    explicit while retaining a compact save representation.
    """

    effect_id: str
    kind: str
    source_actor_id: str
    item_id: str
    expires_at_source_start: int
    expires_at_world_time: int | None
    potency: int = 1
    striking_dice: int = 2
    magical: bool = True
    visible: bool = True


@dataclass(frozen=True)
class GuidanceImmunity:
    target_actor_id: str
    expires_at_round: int


@dataclass(frozen=True)
class LightOrb:
    """One concrete rank-1 Light orb in the local scene.

    An orb has no creature or equipment identity. Its location is either a
    point on the grid or a carrier actor; attached locations are derived from
    the carrier at query time so movement pauses cannot leave stale light.
    ``owner_preparation`` records the caster's preparation epoch for the
    future daily-preparation cleanup command; no turn-based expiry is used.
    """

    stable_id: str
    caster_actor_id: str
    rank: int
    color: str
    point: Position | None = None
    attached_actor_id: str | None = None
    owner_preparation: int = 0

    @property
    def orb_id(self) -> str:
        """Convenient public alias for the stable orb identity."""
        return self.stable_id

    @property
    def position(self) -> Position | None:
        """Return the stored point; attached positions are scene-relative."""
        return self.point


@dataclass
class EncounterState:
    setup_id: str
    map_width: int
    map_height: int
    creatures: dict[str, CreatureState]
    initiative_order: list[str]
    active_index: int
    initiative_skills: dict[str, str] = field(default_factory=dict)
    initiative_contexts: dict[str, str | None] = field(default_factory=dict)
    round_number: int = 1
    in_progress: bool = True
    winner_team: str | None = None
    initiative_finalized: bool = True
    pending_choice: PendingChoice | None = None
    next_choice_id: int = 1
    initiative_hero_decided: set[str] = field(default_factory=set)
    quick_tempered_decided: set[str] = field(default_factory=set)
    ground_items: dict[Position, list[str]] = field(default_factory=dict)
    item_instances: dict[str, ItemInstance] = field(default_factory=dict)
    raised_shields: dict[str, RaisedShieldState] = field(default_factory=dict)
    initiative_tie_groups: list[tuple[str, ...]] = field(default_factory=list)
    initiative_tie_orders: dict[int, list[str]] = field(default_factory=dict)
    initiative_tie_group_index: int = 0
    initiative_reordered: set[str] = field(default_factory=set)
    actor_start_counts: dict[str, int] = field(default_factory=dict)
    actor_end_counts: dict[str, int] = field(default_factory=dict)
    feint_off_guard_effects: list["FeintOffGuardEffect"] = field(default_factory=list)
    # Tumble Behind is deliberately a distinct typed, attacker-relative
    # one-attack exposure; it does not reuse Feint's melee-only contract.
    tumble_behind_exposures: list["TumbleBehindExposure"] = field(default_factory=list)
    active_effects: list[ActiveSpellEffect] = field(default_factory=list)
    persistent_effects: list[PersistentDamageEffect] = field(default_factory=list)
    giant_centipede_venom_afflictions: list[GiantCentipedeVenomAffliction] = field(default_factory=list)
    active_item_effects: list[ActiveItemSpellEffect] = field(default_factory=list)
    guidance_immunities: dict[str, int] = field(default_factory=dict)
    taking_cover: set[str] = field(default_factory=set)
    condition_effects: list[ActiveConditionEffect] = field(default_factory=list)
    condition_immunities: list[ConditionImmunity] = field(default_factory=list)
    world_time_seconds: int = 0
    # The absolute clock at which this encounter's round-one clock began.
    # Combat advances remain anchored to this value; recovery activities may
    # advance ``world_time_seconds`` after combat ends.
    encounter_start_seconds: int = 0
    ambient_light: str = "bright"
    light_orbs: list[LightOrb] = field(default_factory=list)
    next_light_orb_id: int = 1
    # Compatibility projection retains the original round-shaped Guidance
    # field.  Rules use the absolute map below.
    guidance_immunity_deadlines: dict[str, int] = field(default_factory=dict)
    # Sure Strike's local ten-minute post-use cooldown is absolute time based.
    sure_strike_immunity_deadlines: dict[str, int] = field(default_factory=dict)
    # Downtime facts are declared explicitly by the caller.  They never derive
    # from elapsed seconds or simulate sleep/rest procedures.
    preparation_day: int = 1
    rested_actor_ids: set[str] = field(default_factory=set)
    last_prepared_day: dict[str, int] = field(default_factory=dict)
    # Justice state is literal per encounter: an active aura is removed by
    # suppression or unconsciousness, and Prayer's temporary point is tracked
    # separately so it cannot fund arbitrary spells or survive turn end.
    justice_aura_active: set[str] = field(default_factory=set)
    desperate_prayer_used: set[str] = field(default_factory=set)
    desperate_prayer_points: set[str] = field(default_factory=set)
    # Known Weaknesses grants are target- and recipient-specific and expire at
    # the investigator's next turn start.  The concrete record is defined in
    # ``investigator.py``; keeping this list on encounter state lets allies
    # consume their own grant independently.
    investigator_weakness_bonuses: list[object] = field(default_factory=list)
    # Alchemy keeps creator and daily-preparation provenance separate from
    # ordinary equipment. Dynamic items are present only while unopened.
    alchemy_states: dict[str, object] = field(default_factory=dict)
    infused_alchemy_items: dict[str, object] = field(default_factory=dict)
    consumed_infused_item_ids: set[str] = field(default_factory=set)


@dataclass
class FamilyProcedureContext:
    """Shared transactional context for explicit family procedures.

    ``state`` and ``dice`` are the private draft and cloned dice provider
    owned by ``Encounter.execute``. A handler must not call public
    ``Encounter.execute``: it should use the draft directly and return one
    ``FamilyProcedureResult``. A pause is recorded as a normal typed
    ``PendingChoice`` and resumes through ``handle_choice`` after save/load.
    """

    encounter: "Encounter"
    state: EncounterState
    dice: "DiceSource"
    actor: CreatureState
    definition: CreatureDefinition
    family_id: str
    command: FamilyCommand | None = None
    pending: PendingChoice | None = None
    choice: Choose | None = None
    quick_tempered_trigger: bool = False

    @property
    def rage_source_id(self) -> str | None:
        """Return the next unique Rage source identity from core-owned state."""
        barbarian_state = self.actor.barbarian_state
        if barbarian_state is None:
            return None
        return f"rage:{self.actor.actor_id}:{barbarian_state.next_rage_instance}"

    def present_choice(
        self,
        procedure_id: str,
        owner_actor_id: str | None,
        prompt: str,
        options: tuple[ChoiceOption, ...],
        continuation: ActionContinuation,
        *,
        details: tuple[str, ...] = (),
        target_id: str | None = None,
        saved_check: SavedCheckContext | None = None,
        paired_strike: PairedStrikeContinuation | None = None,
        family_command: FamilyCommand | None = None,
    ) -> PendingChoice:
        """Persist a family pause using the core's ordinary choice sequence."""
        if self.state.pending_choice is not None:
            raise ValueError("a family procedure cannot replace an existing pending choice")
        if not procedure_id or not prompt or not options:
            raise ValueError("family choices need a procedure id, prompt, and options")
        if continuation.actor_id != self.actor.actor_id:
            raise ValueError("family continuation must retain its acting actor")
        self.encounter._set_pending(
            self.state,
            kind="family_action",
            owner_actor_id=owner_actor_id,
            prompt=prompt,
            options=options,
            details=details,
            actor_id=self.actor.actor_id,
            target_id=target_id,
            continuation=continuation,
            family_id=self.family_id,
            procedure_id=procedure_id,
            saved_check=saved_check,
            paired_strike=paired_strike,
            family_command=family_command,
        )
        assert self.state.pending_choice is not None
        return self.state.pending_choice

    def present_spell_slot_choice(
        self,
        command: Cast,
        options: tuple[ChoiceOption, ...],
        *,
        spell_name: str,
        actions: int,
    ) -> PendingChoice:
        """Create the existing persisted prepared-slot choice for a cast."""
        if self.state.pending_choice is not None:
            raise ValueError("a spell-slot choice cannot replace an existing pending choice")
        if not isinstance(command, Cast) or command.slot_id is not None:
            raise ValueError("a spell-slot choice requires a Cast without a selected slot")
        if not isinstance(spell_name, str) or not spell_name:
            raise ValueError("a spell-slot choice needs the printed spell name")
        if type(actions) is not int or actions < 1:
            raise ValueError("a spell-slot choice needs a positive action count")
        if not isinstance(options, tuple) or not options or any(
            not isinstance(option, ChoiceOption) for option in options
        ):
            raise ValueError("a spell-slot choice needs typed prepared-slot options")
        self.encounter._set_pending(
            self.state,
            kind="spell_slot",
            owner_actor_id=self.actor.actor_id,
            prompt=f"Choose which prepared {spell_name} slot to expend.",
            options=options,
            actor_id=self.actor.actor_id,
            spell_id=command.spell_id,
            spell_actions=actions,
            target_id=command.target_id,
            spell_target_item_id=command.item_id,
            include_self=command.include_self,
        )
        assert self.state.pending_choice is not None
        return self.state.pending_choice

    def roll_skill_check(
        self,
        statistic: str,
        dc: int,
        *,
        traits: frozenset[str] = frozenset(),
        extra_modifiers: tuple[Modifier, ...] = (),
        pre_roll_choices: tuple[str, ...] = (),
        parent_continuation: ActionContinuation | None = None,
    ) -> SavedCheckContext:
        """Roll a printed skill with sourced conditions and retain its facts."""
        return self.encounter._roll_skill_check(
            self.state,
            self.dice,
            self.actor,
            statistic,
            dc,
            traits=traits,
            extra_modifiers=extra_modifiers,
            pre_roll_choices=pre_roll_choices,
            parent_continuation=parent_continuation,
        )

    def prepare_skill_check(
        self,
        statistic: str,
        dc: int,
        *,
        traits: frozenset[str] = frozenset(),
        extra_modifiers: tuple[Modifier, ...] = (),
        pre_roll_choices: tuple[str, ...] = (),
        parent_continuation: ActionContinuation | None = None,
    ) -> SavedCheckContext:
        return self.encounter._prepare_skill_check(
            self.state, self.actor, statistic, dc, traits=traits,
            extra_modifiers=extra_modifiers, pre_roll_choices=pre_roll_choices,
            parent_continuation=parent_continuation,
        )

    def prepare_unarmed_attack_check(
        self,
        dc: int,
        attack_id: str | None = None,
        *,
        parent_continuation: ActionContinuation | None = None,
    ) -> SavedCheckContext:
        """Prepare an unarmed attack check, retaining its selected profile and MAP."""
        return self.encounter._prepare_unarmed_attack_check(
            self.state, self.actor, dc, attack_id, parent_continuation=parent_continuation,
        )

    def resolve_saved_check(self, saved: SavedCheckContext) -> SavedCheckContext:
        return self.encounter._resolve_saved_check(self.state, self.actor, self.dice, saved)

    def reroll_saved_check(self, saved: SavedCheckContext, *, spend_hero_point: bool) -> SavedCheckContext:
        return self.encounter._reroll_saved_check(self.state, self.dice, self.actor, saved, spend_hero_point=spend_hero_point)

    def reroll_skill_check(self, saved: SavedCheckContext) -> SavedCheckContext:
        return self.encounter._reroll_saved_check(self.state, self.dice, self.actor, saved, spend_hero_point=True)

    def add_check_modifier(self, saved: SavedCheckContext, modifier: Modifier) -> SavedCheckContext:
        if saved.result is not None:
            raise ValueError("check modifiers must be chosen before rolling")
        return replace(saved, modifiers=(*saved.modifiers, modifier))

    def guidance_for(self, actor_id: str | None = None):
        return self.encounter._guidance_for(self.state, actor_id or self.actor.actor_id)

    def guidance_effect(self):
        return self.guidance_for()

    def consume_guidance(self, effect_id: str) -> Modifier | None:
        return self.encounter._consume_guidance(self.state, self.actor.actor_id, effect_id)

    def skill_modifier(self, statistic: str) -> int:
        """Return the actor's printed or untrained skill modifier."""
        return self.encounter._skill_modifier(self.definition, statistic)

    @property
    def free_hands(self) -> int:
        """Number of hands not occupied by held items in this draft."""
        return self.encounter._free_hands(self.state, self.definition, self.actor)

    def commit_family_action(self, *, actions: int, attacks: int = 0) -> None:
        """Commit ordinary action and MAP counters at the procedure boundary."""
        self.encounter._commit_family_action(self, actions=actions, attacks=attacks)

    def require_action_permitted(self, action_id: str, traits: frozenset[str]) -> None:
        """Apply the shared condition gate before a family action commits costs."""
        self.encounter._require_action_permitted(
            self.state, self.actor, action_id, traits
        )

    def has_condition(self, target_actor_id: str, kind: str) -> bool:
        return any(
            effect.target_actor_id == target_actor_id and effect.kind == kind
            for effect in self.state.condition_effects
        )

    def skill_dc(self, actor_id: str, statistic: str) -> int:
        """Return the creature's ordinary DC for one saved skill statistic."""
        return self.encounter._skill_dc(self.state, actor_id, statistic)

    def condition_effects_for(self, target_actor_id: str, kind: str | None = None) -> tuple[ActiveConditionEffect, ...]:
        return tuple(
            effect for effect in self.state.condition_effects
            if effect.target_actor_id == target_actor_id and (kind is None or effect.kind == kind)
        )

    def add_condition_effect(
        self,
        effect_id: str,
        kind: str,
        source_actor_id: str,
        target_actor_id: str,
        value: int,
        *,
        expiration: EffectExpiration,
        dc: int | None = None,
    ) -> None:
        if not effect_id or any(item.effect_id == effect_id for item in self.state.condition_effects):
            raise ValueError("condition effect IDs must be unique and non-empty")
        if target_actor_id not in self.state.creatures or source_actor_id not in self.state.creatures:
            raise ValueError("condition effect source and target must exist")
        if dc is not None and (type(dc) is not int or dc < 0):
            raise ValueError("condition effect DC must be a non-negative integer")
        self.state.condition_effects.append(
            ActiveConditionEffect(effect_id, kind, source_actor_id, target_actor_id, value, expiration, dc)
        )

    def remove_condition_effect(self, effect_id: str) -> None:
        self.state.condition_effects = [
            effect for effect in self.state.condition_effects if effect.effect_id != effect_id
        ]

    def condition_immunity_active(self, kind: str, source_actor_id: str, target_actor_id: str) -> bool:
        now = self.state.world_time_seconds
        return any(
            item.kind == kind
            and item.source_actor_id == source_actor_id
            and item.target_actor_id == target_actor_id
            and item.expires_at_seconds > now
            for item in self.state.condition_immunities
        )

    @property
    def escape_locked(self) -> bool:
        return self.actor.escape_lockout_until_start > self.state.actor_start_counts.get(self.actor.actor_id, 0)

    def grant_condition_immunity(
        self, kind: str, source_actor_id: str, target_actor_id: str, *, duration_seconds: int
    ) -> None:
        if not kind or type(duration_seconds) is not int or duration_seconds < 0:
            raise ValueError("condition immunity requires a kind and non-negative duration")
        if source_actor_id not in self.state.creatures or target_actor_id not in self.state.creatures:
            raise ValueError("condition immunity source and target must exist")
        self.state.condition_immunities = [
            item for item in self.state.condition_immunities
            if (item.kind, item.source_actor_id, item.target_actor_id)
            != (kind, source_actor_id, target_actor_id)
        ]
        self.state.condition_immunities.append(
            ConditionImmunity(kind, source_actor_id, target_actor_id, self.state.world_time_seconds + duration_seconds)
        )

    def apply_family_damage(
        self,
        target_actor_id: str,
        damage: DamageResult,
        *,
        source: str,
        damage_type: str,
        check: CheckResult | None = None,
        nonlethal: bool = False,
        attacker_critical: bool = False,
        target_critical_failure: bool = False,
        continuation: ActionContinuation | None = None,
    ) -> tuple[Event, ...]:
        """Apply one named family damage result through shared core health rules."""
        return tuple(self.encounter.apply_family_damage(
            self.state,
            self.actor,
            target_actor_id,
            damage,
            dice=self.dice,
            source=source,
            damage_type=damage_type,
            check=check,
            nonlethal=nonlethal,
            attacker_critical=attacker_critical,
            target_critical_failure=target_critical_failure,
            continuation=continuation,
        ))
