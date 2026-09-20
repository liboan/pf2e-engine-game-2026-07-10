"""Typed Player Core 2 Alchemist levels 1–2 rules facts and procedures.

This module is deliberately independent of Encounter and CreatureState. Core
supplies declared hand/tool/turn/time facts, then commits returned immutable
state and creation records. The helpers never roll or advance time.

Rules checked 2026-09-15 against Player Core 2, pp. 56–62, Spring 2026
errata, and the individual item entries linked by ``alchemy_content``:
https://2e.aonprd.com/Classes.aspx?ID=56
https://2e.aonprd.com/Actions.aspx?ID=2801
https://2e.aonprd.com/Traits.aspx?ID=797
https://paizo.com/pathfinder/faq
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


ALCHEMIST_LEVEL = 1
ALCHEMIST_LEVEL_2 = 2
SUPPORTED_ALCHEMIST_LEVELS = frozenset({ALCHEMIST_LEVEL, ALCHEMIST_LEVEL_2})
STARTING_FORMULA_COUNT = 8
FORMULAS_PER_LEVEL = 2
ADVANCED_ALCHEMY_BASE_CAPACITY = 4
VERSATILE_VIAL_BASE_CAPACITY = 2
VIAL_RECOVERY_INTERVAL_SECONDS = 10 * 60
VIAL_RECOVERY_AMOUNT = 2
INFUSED_LIFETIME_SECONDS = 24 * 60 * 60
QUICK_ALCHEMY_EFFECT_CAP_SECONDS = 10 * 60
QUICK_ALCHEMY_ACTION_COST = 1
QUICK_ALCHEMY_ACTION_TRAITS = frozenset({"alchemist", "manipulate"})

FIELD_BOMBER = "bomber"
FIELD_CHIRURGEON = "chirurgeon"
FIELD_MUTAGENIST = "mutagenist"
FIELD_TOXICOLOGIST = "toxicologist"
RESEARCH_FIELDS = frozenset({FIELD_BOMBER, FIELD_CHIRURGEON, FIELD_MUTAGENIST, FIELD_TOXICOLOGIST})

QUICK_BOMBER = "quick_bomber"
FAR_LOBBER = "far_lobber"
ALCHEMIST_LEVEL_1_FEATS = frozenset({QUICK_BOMBER, FAR_LOBBER})
# The level-two class-feat slot may legally select either already-supported
# level-one bomb feat.  The other level-two Alchemist feats require mutagen,
# additive-poison, or Crafting-check procedures outside this Bomber slice.
ALCHEMIST_LEVEL_2_BOMBER_FEATS = frozenset({QUICK_BOMBER, FAR_LOBBER})


class AlchemyRuleError(ValueError):
    """Invalid alchemist selection or transition with a stable ``reason``."""

    def __init__(self, reason: str, message: str | None = None) -> None:
        self.reason = reason
        super().__init__(message or reason.replace("_", " "))


@dataclass(frozen=True, slots=True)
class AlchemyBuildChoices:
    research_field: str
    field_formula_ids: tuple[str, str]
    known_formula_ids: tuple[str, ...]
    intelligence_modifier: int
    selected_level_1_feat: str | None = None
    character_level: int = ALCHEMIST_LEVEL
    selected_level_2_feat: str | None = None


@dataclass(frozen=True, slots=True)
class AlchemyState:
    """Current levels 1–2 field, formula book, and infused-vial resources."""

    character_level: int
    intelligence_modifier: int
    research_field: str
    field_formula_ids: tuple[str, str]
    known_formula_ids: tuple[str, ...]
    selected_level_1_feat: str | None
    daily_preparation_id: str
    stored_vials: int
    vial_capacity: int
    exploration_seconds_toward_vial_recovery: int = 0
    next_creation_sequence: int = 1
    mutagen_temp_hp_available_at_seconds: int = 0
    selected_level_2_feat: str | None = None

    def __post_init__(self) -> None:
        if type(self.character_level) is not int or self.character_level not in SUPPORTED_ALCHEMIST_LEVELS:
            raise ValueError("this alchemy slice supports character levels 1 and 2 only")
        if type(self.intelligence_modifier) is not int:
            raise TypeError("intelligence_modifier must be an integer")
        if self.research_field not in RESEARCH_FIELDS:
            raise ValueError("research_field is not a supported Player Core 2 field")
        if self.character_level == ALCHEMIST_LEVEL_2 and self.research_field != FIELD_BOMBER:
            raise ValueError("the level-2 alchemy slice is limited to Bomber")
        if not isinstance(self.field_formula_ids, tuple) or not isinstance(self.known_formula_ids, tuple):
            raise ValueError("formula selections must be tuples")
        if len(self.field_formula_ids) != 2 or len(set(self.field_formula_ids)) != 2:
            raise ValueError("exactly two distinct field formulas are required")
        if any(not isinstance(item, str) or not item.strip() for item in (*self.field_formula_ids, *self.known_formula_ids)):
            raise ValueError("formula IDs must be non-empty strings")
        expected_formula_count = STARTING_FORMULA_COUNT + (self.character_level - ALCHEMIST_LEVEL) * FORMULAS_PER_LEVEL
        if len(self.known_formula_ids) != expected_formula_count or len(set(self.known_formula_ids)) != expected_formula_count:
            raise ValueError(f"the level-{self.character_level} formula book must contain {expected_formula_count} distinct formulas")
        if not set(self.field_formula_ids) <= set(self.known_formula_ids):
            raise ValueError("field formulas must also be in the formula book")
        if not isinstance(self.daily_preparation_id, str) or not self.daily_preparation_id.strip():
            raise ValueError("daily_preparation_id must be a non-empty string")
        if type(self.stored_vials) is not int or type(self.vial_capacity) is not int:
            raise TypeError("vial resources must be integers")
        if not 0 <= self.stored_vials <= self.vial_capacity:
            raise ValueError("stored_vials must be within the vial capacity")
        if type(self.exploration_seconds_toward_vial_recovery) is not int:
            raise TypeError("exploration recovery progress must be an integer")
        if not 0 <= self.exploration_seconds_toward_vial_recovery < VIAL_RECOVERY_INTERVAL_SECONDS:
            raise ValueError("exploration recovery progress must be below ten minutes")
        if type(self.next_creation_sequence) is not int or self.next_creation_sequence < 1:
            raise ValueError("next_creation_sequence must be a positive integer")
        if type(self.mutagen_temp_hp_available_at_seconds) is not int or self.mutagen_temp_hp_available_at_seconds < 0:
            raise ValueError("mutagen temp HP cooldown must be a non-negative timestamp")
        if self.character_level == ALCHEMIST_LEVEL and self.selected_level_2_feat is not None:
            raise ValueError("a level-1 Alchemist has no level-2 class feat")
        if self.character_level == ALCHEMIST_LEVEL_2 and self.selected_level_2_feat is None:
            raise ValueError("a level-2 Alchemist must select its level-2 class feat")
        if self.selected_level_2_feat is not None and self.selected_level_2_feat not in ALCHEMIST_LEVEL_2_BOMBER_FEATS:
            raise ValueError("selected level-2 feat is outside the admitted Bomber menu")
        if self.selected_level_2_feat is not None and self.selected_level_2_feat == self.selected_level_1_feat:
            raise ValueError("the same Alchemist feat cannot occupy both level-1 and level-2 slots")


@dataclass(frozen=True, slots=True)
class InfusedAlchemyItem:
    """An item produced by Advanced Alchemy or Quick Alchemy.

    ``activation_deadline`` is None for a prepared Advanced Alchemy item,
    ``creator_next_turn_start`` for a Quick Alchemy consumable, and
    ``creator_current_turn_end`` for a temporary Quick Vial.
    """

    instance_id: str
    formula_id: str | None
    creator_actor_id: str
    creation_kind: Literal["advanced_alchemy", "quick_alchemy", "quick_vial"]
    created_at_seconds: int
    daily_preparation_id: str
    expires_at_seconds: int
    activation_deadline: Literal["creator_next_turn_start", "creator_current_turn_end"] | None = None
    creator_turn_occurrence: int | None = None
    creator_turn_id: str | None = None
    temporary_vial: bool = False

    def __post_init__(self) -> None:
        for field_name in ("instance_id", "creator_actor_id", "daily_preparation_id"):
            value = getattr(self, field_name)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{field_name} must be a non-empty string")
        if self.formula_id is not None and (not isinstance(self.formula_id, str) or not self.formula_id.strip()):
            raise ValueError("formula_id must be None or a non-empty string")
        for field_name in ("created_at_seconds", "expires_at_seconds"):
            if type(getattr(self, field_name)) is not int or getattr(self, field_name) < 0:
                raise ValueError(f"{field_name} must be a non-negative integer")
        if self.expires_at_seconds <= self.created_at_seconds:
            raise ValueError("infused item expiry must follow its creation time")
        if self.creation_kind == "advanced_alchemy":
            if self.formula_id is None or self.activation_deadline is not None or self.temporary_vial:
                raise ValueError("Advanced Alchemy creates a formula item without a turn deadline")
        elif self.creation_kind == "quick_alchemy":
            if self.formula_id is None or self.activation_deadline != "creator_next_turn_start":
                raise ValueError("Quick Alchemy consumables expire for activation at the creator's next turn")
        elif self.creation_kind == "quick_vial":
            if self.formula_id is not None or self.activation_deadline != "creator_current_turn_end" or not self.temporary_vial:
                raise ValueError("Quick Vial is a temporary vial available only through the current turn")
        if self.activation_deadline is None:
            if self.creator_turn_occurrence is not None or self.creator_turn_id is not None:
                raise ValueError("items without a turn deadline cannot carry turn identity")
        elif self.activation_deadline == "creator_next_turn_start":
            if type(self.creator_turn_occurrence) is not int or self.creator_turn_occurrence < 1:
                raise ValueError("Quick Alchemy needs the creator's positive turn occurrence")
            if self.creator_turn_id is not None:
                raise ValueError("Quick Alchemy's next-start limit uses the creator's turn occurrence")
        elif self.activation_deadline == "creator_current_turn_end":
            if not isinstance(self.creator_turn_id, str) or not self.creator_turn_id.strip():
                raise ValueError("Quick Vial needs the creator's current turn ID")
            if self.creator_turn_occurrence is not None:
                raise ValueError("Quick Vial's end-turn limit uses its current turn ID")


@dataclass(frozen=True, slots=True)
class AdvancedAlchemyPreparation:
    state: AlchemyState
    items: tuple[InfusedAlchemyItem, ...]
    expired_preparation_id: str


@dataclass(frozen=True, slots=True)
class QuickAlchemyRequest:
    mode: Literal["create_consumable", "quick_vial"]
    creator_actor_id: str
    now_seconds: int
    worn_or_held_toolkit: bool
    free_hand: bool
    formula_id: str | None = None
    creator_turn_occurrence: int | None = None
    creator_turn_id: str | None = None


@dataclass(frozen=True, slots=True)
class QuickAlchemyResult:
    state: AlchemyState
    item: InfusedAlchemyItem
    action_cost: int = QUICK_ALCHEMY_ACTION_COST
    action_traits: frozenset[str] = QUICK_ALCHEMY_ACTION_TRAITS


@dataclass(frozen=True, slots=True)
class FieldVialProfile:
    research_field: str
    use_mode: Literal["bomb_strike", "healing_drink", "healing_throw", "mutagen_suppression", "injury_coating"]
    damage_type: str | None = None
    initial_damage_dice: tuple[int, ...] = ()
    initial_damage_flat: int = 0
    splash_damage: int = 0
    healing_dice: tuple[int, ...] = ()
    thrown_healing_range_ft: int | None = None
    living_target_only: bool = False
    attack_roll_required: bool = False
    coagulant: bool = False
    suppression_seconds: int | None = None
    injury_strike_damage_dice: tuple[int, ...] = ()
    injury_expires_at: Literal["creator_current_turn_end"] | None = None
    injury_requires_piercing_or_slashing_damage: bool = False
    traits: frozenset[str] = frozenset({"alchemical", "consumable"})


@dataclass(frozen=True, slots=True)
class MutagenTemporaryHPGrant:
    state: AlchemyState
    amount: int
    expires_at_seconds: int


def _catalog():
    # Lazy import keeps the content facts independent of this state module.
    from .alchemy_content import FORMULAS_BY_ID

    return FORMULAS_BY_ID


def _known_formula(state: AlchemyState, formula_id: str, *, action: str) -> None:
    if formula_id not in state.known_formula_ids:
        raise AlchemyRuleError("unknown_formula", f"{formula_id!r} is not in this alchemist's formula book")
    formula = _catalog().get(formula_id)
    if formula is None:
        raise AlchemyRuleError("unsupported_formula", f"formula {formula_id!r} is outside the admitted catalog")
    if formula.level > state.character_level:
        raise AlchemyRuleError("formula_level_too_high", f"{action} cannot create a level {formula.level} item at level {state.character_level}")


def build_alchemy_state(choices: AlchemyBuildChoices, *, daily_preparation_id: str = "initial") -> AlchemyState:
    """Validate a legal selected level-1 or level-2 Alchemist state."""
    if choices.character_level not in SUPPORTED_ALCHEMIST_LEVELS:
        raise AlchemyRuleError("unsupported_character_level", "this slice supports Alchemist levels 1 and 2")
    if choices.research_field not in RESEARCH_FIELDS:
        raise AlchemyRuleError("unknown_research_field", f"unknown research field {choices.research_field!r}")
    if choices.character_level == ALCHEMIST_LEVEL_2 and choices.research_field != FIELD_BOMBER:
        raise AlchemyRuleError("unsupported_l2_research_field", "this level-2 alchemy slice is limited to Bomber")
    if type(choices.intelligence_modifier) is not int:
        raise AlchemyRuleError("invalid_intelligence", "intelligence modifier must be an integer")
    if not isinstance(choices.field_formula_ids, tuple) or not isinstance(choices.known_formula_ids, tuple):
        raise AlchemyRuleError("invalid_formula_book", "field and known formula selections must be tuples")
    if len(choices.field_formula_ids) != 2 or len(set(choices.field_formula_ids)) != 2:
        raise AlchemyRuleError("invalid_field_formulas", "choose exactly two different field formulas")
    expected_formula_count = STARTING_FORMULA_COUNT + (choices.character_level - ALCHEMIST_LEVEL) * FORMULAS_PER_LEVEL
    if len(choices.known_formula_ids) != expected_formula_count or len(set(choices.known_formula_ids)) != expected_formula_count:
        raise AlchemyRuleError("invalid_formula_book_size", f"the level-{choices.character_level} formula book contains {expected_formula_count} different formulas")
    if not set(choices.field_formula_ids) <= set(choices.known_formula_ids):
        raise AlchemyRuleError("field_formula_not_known", "both research-field formulas must be in the formula book")
    if choices.selected_level_1_feat is not None and choices.selected_level_1_feat not in ALCHEMIST_LEVEL_1_FEATS:
        raise AlchemyRuleError("unsupported_class_feat", f"level-1 Alchemist feat {choices.selected_level_1_feat!r} is not in this catalog")
    if choices.character_level == ALCHEMIST_LEVEL and choices.selected_level_2_feat is not None:
        raise AlchemyRuleError("level_2_feat_too_early", "level-2 feat selection requires character level 2")
    if choices.character_level == ALCHEMIST_LEVEL_2 and choices.selected_level_2_feat is None:
        raise AlchemyRuleError("level_2_feat_required", "a level-2 Alchemist must select its class feat")
    if choices.selected_level_2_feat is not None and choices.selected_level_2_feat not in ALCHEMIST_LEVEL_2_BOMBER_FEATS:
        raise AlchemyRuleError("unsupported_class_feat", f"level-2 Alchemist feat {choices.selected_level_2_feat!r} is not in this Bomber catalog")
    if choices.selected_level_2_feat is not None and choices.selected_level_2_feat == choices.selected_level_1_feat:
        raise AlchemyRuleError("duplicate_class_feat", "the same Alchemist feat cannot occupy both class-feat slots")

    formulas = _catalog()
    for formula_id in choices.known_formula_ids:
        formula = formulas.get(formula_id)
        if formula is None or formula.level > choices.character_level:
            raise AlchemyRuleError("unsupported_formula", f"{formula_id!r} is not an admitted common formula creatable at level {choices.character_level}")
    required_category = {
        FIELD_BOMBER: "bomb",
        FIELD_CHIRURGEON: "healing_elixir",
        FIELD_MUTAGENIST: "mutagen",
        FIELD_TOXICOLOGIST: "poison",
    }[choices.research_field]
    for formula_id in choices.field_formula_ids:
        formula = formulas[formula_id]
        if formula.category != required_category:
            raise AlchemyRuleError("wrong_field_formula", f"{formula.name} is not a {required_category} formula for {choices.research_field}")

    capacity = max(0, VERSATILE_VIAL_BASE_CAPACITY + choices.intelligence_modifier)
    return AlchemyState(
        character_level=choices.character_level,
        intelligence_modifier=choices.intelligence_modifier,
        research_field=choices.research_field,
        field_formula_ids=choices.field_formula_ids,
        known_formula_ids=choices.known_formula_ids,
        selected_level_1_feat=choices.selected_level_1_feat,
        daily_preparation_id=daily_preparation_id,
        stored_vials=capacity,
        vial_capacity=capacity,
        selected_level_2_feat=choices.selected_level_2_feat,
    )


def advanced_alchemy_capacity(state: AlchemyState) -> int:
    """Return the daily number of consumables producible by Advanced Alchemy."""
    return max(0, ADVANCED_ALCHEMY_BASE_CAPACITY + state.intelligence_modifier)


def bomber_bomb_range_increment(state: AlchemyState, ordinary_range_increment_ft: int) -> int:
    """Return a selected Bomber bomb's range increment.

    Far Lobber is a class-feat choice, not a new item profile.  The encounter
    layer supplies the individual bomb's ordinary increment and applies this
    helper only when resolving a Bomber bomb Strike.
    """
    if state.research_field != FIELD_BOMBER:
        raise AlchemyRuleError("wrong_research_field", "only a Bomber can apply a Bomber bomb range feat")
    if type(ordinary_range_increment_ft) is not int or ordinary_range_increment_ft <= 0:
        raise AlchemyRuleError("invalid_range_increment", "ordinary bomb range increment must be a positive integer")
    if FAR_LOBBER in {state.selected_level_1_feat, state.selected_level_2_feat}:
        return 30
    return ordinary_range_increment_ft


def daily_prepare_alchemy(
    state: AlchemyState,
    formula_ids: tuple[str, ...],
    *,
    creator_actor_id: str,
    preparation_id: str,
    now_seconds: int,
) -> AdvancedAlchemyPreparation:
    """Prepare up to 4 + Intelligence known consumables and refresh stored vials.

    Core should remove all still-existing infused items bearing the returned
    ``expired_preparation_id`` for this creator. The returned items carry both
    the 24-hour limit and their preparation provenance, so transferred stock
    follows the same cleanup.
    """
    _validate_identifier(creator_actor_id, "creator_actor_id")
    _validate_identifier(preparation_id, "preparation_id")
    _validate_time(now_seconds, "now_seconds")
    if preparation_id == state.daily_preparation_id:
        raise AlchemyRuleError("preparation_id_not_advanced", "a new daily preparation needs a new identity")
    if not isinstance(formula_ids, tuple):
        raise AlchemyRuleError("invalid_preparation", "formula selections must be a tuple")
    capacity = advanced_alchemy_capacity(state)
    if len(formula_ids) > capacity:
        raise AlchemyRuleError("advanced_alchemy_capacity_exceeded", f"daily Advanced Alchemy capacity is {capacity}")
    for formula_id in formula_ids:
        _known_formula(state, formula_id, action="Advanced Alchemy")

    new_state = AlchemyState(
        character_level=state.character_level,
        intelligence_modifier=state.intelligence_modifier,
        research_field=state.research_field,
        field_formula_ids=state.field_formula_ids,
        known_formula_ids=state.known_formula_ids,
        selected_level_1_feat=state.selected_level_1_feat,
        daily_preparation_id=preparation_id,
        stored_vials=state.vial_capacity,
        vial_capacity=state.vial_capacity,
        exploration_seconds_toward_vial_recovery=0,
        next_creation_sequence=state.next_creation_sequence,
        mutagen_temp_hp_available_at_seconds=state.mutagen_temp_hp_available_at_seconds,
        selected_level_2_feat=state.selected_level_2_feat,
    )
    items = tuple(
        InfusedAlchemyItem(
            instance_id=f"{creator_actor_id}:advanced:{preparation_id}:{index}",
            formula_id=formula_id,
            creator_actor_id=creator_actor_id,
            creation_kind="advanced_alchemy",
            created_at_seconds=now_seconds,
            daily_preparation_id=preparation_id,
            expires_at_seconds=now_seconds + INFUSED_LIFETIME_SECONDS,
        )
        for index, formula_id in enumerate(formula_ids, start=1)
    )
    return AdvancedAlchemyPreparation(new_state, items, state.daily_preparation_id)


def recover_versatile_vials(state: AlchemyState, exploration_seconds: int) -> AlchemyState:
    """Advance declared exploration time and recover two vials per ten minutes.

    Exploration can include another legal exploration activity; the caller
    supplies only the elapsed exploration time. Progress is not banked while
    stock is at maximum.
    """
    _validate_time(exploration_seconds, "exploration_seconds")
    if state.stored_vials == state.vial_capacity:
        return AlchemyState(
            **{
                **_state_values(state),
                "exploration_seconds_toward_vial_recovery": 0,
            }
        )
    progress = state.exploration_seconds_toward_vial_recovery + exploration_seconds
    intervals, remainder = divmod(progress, VIAL_RECOVERY_INTERVAL_SECONDS)
    recovered = intervals * VIAL_RECOVERY_AMOUNT
    new_stock = min(state.vial_capacity, state.stored_vials + recovered)
    if new_stock == state.vial_capacity:
        remainder = 0
    return AlchemyState(
        **{
            **_state_values(state),
            "stored_vials": new_stock,
            "exploration_seconds_toward_vial_recovery": remainder,
        }
    )


def perform_quick_alchemy(state: AlchemyState, request: QuickAlchemyRequest) -> QuickAlchemyResult:
    """Validate and produce one consumable or one free temporary Quick Vial."""
    _validate_identifier(request.creator_actor_id, "creator_actor_id")
    _validate_time(request.now_seconds, "now_seconds")
    if not request.worn_or_held_toolkit:
        raise AlchemyRuleError("toolkit_required", "Quick Alchemy requires a worn or held alchemist's toolkit")
    if not request.free_hand:
        raise AlchemyRuleError("free_hand_required", "Quick Alchemy requires a free hand")
    if request.mode == "create_consumable":
        if request.formula_id is None:
            raise AlchemyRuleError("formula_required", "Create Consumable requires a known formula")
        if request.creator_turn_occurrence is None or type(request.creator_turn_occurrence) is not int or request.creator_turn_occurrence < 1:
            raise AlchemyRuleError("turn_occurrence_required", "Quick Alchemy needs the creator's current turn occurrence")
        if request.creator_turn_id is not None:
            raise AlchemyRuleError("unexpected_turn_id", "Create Consumable uses the creator's turn occurrence")
        _known_formula(state, request.formula_id, action="Quick Alchemy")
        if state.stored_vials < 1:
            raise AlchemyRuleError("no_stored_vial", "Create Consumable expends one stored versatile vial")
        item = InfusedAlchemyItem(
            instance_id=f"{request.creator_actor_id}:quick:{state.next_creation_sequence}",
            formula_id=request.formula_id,
            creator_actor_id=request.creator_actor_id,
            creation_kind="quick_alchemy",
            created_at_seconds=request.now_seconds,
            daily_preparation_id=state.daily_preparation_id,
            expires_at_seconds=request.now_seconds + INFUSED_LIFETIME_SECONDS,
            activation_deadline="creator_next_turn_start",
            creator_turn_occurrence=request.creator_turn_occurrence,
        )
        new_state = AlchemyState(
            **{
                **_state_values(state),
                "stored_vials": state.stored_vials - 1,
                "next_creation_sequence": state.next_creation_sequence + 1,
            }
        )
        return QuickAlchemyResult(new_state, item)
    if request.mode == "quick_vial":
        if request.formula_id is not None:
            raise AlchemyRuleError("quick_vial_has_no_formula", "Quick Vial is not a formula consumable")
        if not isinstance(request.creator_turn_id, str) or not request.creator_turn_id.strip():
            raise AlchemyRuleError("turn_id_required", "Quick Vial is available only through the current turn's end")
        if request.creator_turn_occurrence is not None:
            raise AlchemyRuleError("unexpected_turn_occurrence", "Quick Vial's deadline is its current turn ID")
        item = InfusedAlchemyItem(
            instance_id=f"{request.creator_actor_id}:quick-vial:{state.next_creation_sequence}",
            formula_id=None,
            creator_actor_id=request.creator_actor_id,
            creation_kind="quick_vial",
            created_at_seconds=request.now_seconds,
            daily_preparation_id=state.daily_preparation_id,
            expires_at_seconds=request.now_seconds + INFUSED_LIFETIME_SECONDS,
            activation_deadline="creator_current_turn_end",
            creator_turn_id=request.creator_turn_id,
            temporary_vial=True,
        )
        new_state = AlchemyState(
            **{
                **_state_values(state),
                "next_creation_sequence": state.next_creation_sequence + 1,
            }
        )
        return QuickAlchemyResult(new_state, item)
    raise AlchemyRuleError("unknown_quick_alchemy_mode", f"unsupported Quick Alchemy mode {request.mode!r}")


def validate_alchemy_activation_window(
    item: InfusedAlchemyItem,
    *,
    active_preparation_id: str,
    now_seconds: int,
    creator_turn_occurrence: int | None = None,
    current_turn_id: str | None = None,
    creator_current_turn_active: bool = False,
) -> None:
    """Raise unless an unopened infused item is still valid to activate."""
    _validate_identifier(active_preparation_id, "active_preparation_id")
    _validate_time(now_seconds, "now_seconds")
    if item.daily_preparation_id != active_preparation_id or now_seconds >= item.expires_at_seconds:
        raise AlchemyRuleError("infused_item_expired", "the infused item expired at daily preparation or after 24 hours")
    if item.activation_deadline == "creator_next_turn_start":
        if creator_turn_occurrence is None or type(creator_turn_occurrence) is not int:
            raise AlchemyRuleError("turn_occurrence_required", "checking a Quick Alchemy item needs the creator's turn occurrence")
        if creator_turn_occurrence > (item.creator_turn_occurrence or 0):
            raise AlchemyRuleError("quick_alchemy_activation_expired", "activate a Quick Alchemy consumable before the creator's next turn starts")
    elif item.activation_deadline == "creator_current_turn_end":
        if not creator_current_turn_active or current_turn_id != item.creator_turn_id:
            raise AlchemyRuleError("quick_vial_activation_expired", "use a Quick Vial before its creator's current turn ends")


def quick_alchemy_effect_duration(ordinary_duration_seconds: int) -> int:
    """Apply Quick Alchemy's ten-minute maximum to a nonpermanent duration."""
    _validate_time(ordinary_duration_seconds, "ordinary_duration_seconds")
    return min(ordinary_duration_seconds, QUICK_ALCHEMY_EFFECT_CAP_SECONDS)


def bomber_splash_targets(
    state: AlchemyState,
    primary_target_id: str,
    other_targets_within_5_feet: tuple[str, ...],
    *,
    only_primary_target: bool,
) -> tuple[str, ...]:
    """Choose the recipients of one Bomber's splash; geometry comes from core."""
    if state.research_field != FIELD_BOMBER:
        raise AlchemyRuleError("wrong_research_field", "only Bomber can restrict splash to the primary target")
    _validate_identifier(primary_target_id, "primary_target_id")
    if not isinstance(other_targets_within_5_feet, tuple):
        raise AlchemyRuleError("invalid_splash_targets", "nearby target IDs must be a tuple")
    for target_id in other_targets_within_5_feet:
        _validate_identifier(target_id, "target_id")
    if primary_target_id in other_targets_within_5_feet or len(set(other_targets_within_5_feet)) != len(other_targets_within_5_feet):
        raise AlchemyRuleError("invalid_splash_targets", "nearby target IDs must be unique and exclude the primary target")
    if type(only_primary_target) is not bool:
        raise AlchemyRuleError("invalid_splash_choice", "only_primary_target must be a boolean")
    if only_primary_target:
        return (primary_target_id,)
    return (primary_target_id, *other_targets_within_5_feet)


def gain_mutagenist_temporary_hp(
    state: AlchemyState,
    *,
    now_seconds: int,
    active_mutagen_expires_at_seconds: int,
) -> MutagenTemporaryHPGrant:
    """Return the field's requested temporary HP and its per-character lock.

    Core owns replacement/absorption of temporary HP pools. This result caps
    the new pool at both one minute and the active mutagen's remaining time.
    """
    _validate_time(now_seconds, "now_seconds")
    _validate_time(active_mutagen_expires_at_seconds, "active_mutagen_expires_at_seconds")
    if state.research_field != FIELD_MUTAGENIST:
        raise AlchemyRuleError("wrong_research_field", "only a Mutagenist receives this mutagen benefit")
    if active_mutagen_expires_at_seconds <= now_seconds:
        raise AlchemyRuleError("mutagen_not_active", "Mutagenist temporary HP requires an active mutagen")
    if now_seconds < state.mutagen_temp_hp_available_at_seconds:
        raise AlchemyRuleError("mutagen_temp_hp_cooldown", "Mutagenist temporary HP cannot be gained again for one minute")
    grant = max(state.intelligence_modifier, 0) + state.character_level // 2
    expires = min(now_seconds + 60, active_mutagen_expires_at_seconds)
    new_state = AlchemyState(
        **{
            **_state_values(state),
            "mutagen_temp_hp_available_at_seconds": now_seconds + 60,
        }
    )
    return MutagenTemporaryHPGrant(new_state, grant, expires)


def field_vial_profile(research_field: str, *, damage_type: str = "acid", use_mode: str | None = None) -> FieldVialProfile:
    """Return one field's explicit level-1 versatile-vial conversion facts."""
    if research_field not in RESEARCH_FIELDS:
        raise AlchemyRuleError("unknown_research_field", f"unknown research field {research_field!r}")
    if research_field == FIELD_BOMBER:
        if use_mode not in {None, "bomb_strike"}:
            raise AlchemyRuleError("invalid_field_vial_use", "a Bomber field vial is used as a bomb Strike")
        if damage_type not in {"acid", "cold", "electricity", "fire"}:
            raise AlchemyRuleError("invalid_vial_damage_type", "Bomber versatile-vial damage can be acid, cold, electricity, or fire")
        return FieldVialProfile(
            research_field=FIELD_BOMBER,
            use_mode="bomb_strike",
            damage_type=damage_type,
            initial_damage_dice=(6,),
            splash_damage=1,
            attack_roll_required=True,
            traits=frozenset({"alchemical", "consumable", "bomb", "thrown", "splash"}),
        )
    if research_field == FIELD_CHIRURGEON:
        requested_mode = "healing_drink" if use_mode is None else use_mode
        if requested_mode not in {"healing_drink", "healing_throw"}:
            raise AlchemyRuleError("invalid_field_vial_use", "a Chirurgeon field vial restores HP by drinking or a 20-foot Interact throw")
        return FieldVialProfile(
            research_field=FIELD_CHIRURGEON,
            use_mode=requested_mode,
            traits=frozenset({"alchemical", "consumable", "healing", "coagulant", *( {"elixir"} if requested_mode == "healing_drink" else set() )}),
            healing_dice=(6,),
            thrown_healing_range_ft=20 if requested_mode == "healing_throw" else None,
            living_target_only=True,
            coagulant=True,
        )
    if research_field == FIELD_MUTAGENIST:
        if use_mode not in {None, "mutagen_suppression"}:
            raise AlchemyRuleError("invalid_field_vial_use", "a Mutagenist field vial suppresses one active mutagen's drawback")
        return FieldVialProfile(
            research_field=FIELD_MUTAGENIST,
            use_mode="mutagen_suppression",
            traits=frozenset({"alchemical", "consumable", "elixir"}),
            suppression_seconds=60,
        )
    if use_mode not in {None, "bomb_strike", "injury_coating"}:
        raise AlchemyRuleError("invalid_field_vial_use", "a Toxicologist field vial is a poison bomb or an injury coating")
    if use_mode == "injury_coating":
        return FieldVialProfile(
            research_field=FIELD_TOXICOLOGIST,
            use_mode="injury_coating",
            damage_type="poison",
            injury_strike_damage_dice=(6,),
            injury_expires_at="creator_current_turn_end",
            injury_requires_piercing_or_slashing_damage=True,
            traits=frozenset({"alchemical", "consumable", "poison", "injury"}),
        )
    return FieldVialProfile(
        research_field=FIELD_TOXICOLOGIST,
        use_mode="bomb_strike",
        damage_type="poison",
        initial_damage_dice=(6,),
        attack_roll_required=True,
        traits=frozenset({"alchemical", "consumable", "bomb", "thrown", "poison"}),
    )


def _validate_identifier(value: str, name: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise AlchemyRuleError("invalid_identifier", f"{name} must be a non-empty string")


def _validate_time(value: int, name: str) -> None:
    if type(value) is not int or value < 0:
        raise AlchemyRuleError("invalid_time", f"{name} must be a non-negative integer number of seconds")


def _state_values(state: AlchemyState) -> dict[str, object]:
    return {
        "character_level": state.character_level,
        "intelligence_modifier": state.intelligence_modifier,
        "research_field": state.research_field,
        "field_formula_ids": state.field_formula_ids,
        "known_formula_ids": state.known_formula_ids,
        "selected_level_1_feat": state.selected_level_1_feat,
        "daily_preparation_id": state.daily_preparation_id,
        "stored_vials": state.stored_vials,
        "vial_capacity": state.vial_capacity,
        "exploration_seconds_toward_vial_recovery": state.exploration_seconds_toward_vial_recovery,
        "next_creation_sequence": state.next_creation_sequence,
        "mutagen_temp_hp_available_at_seconds": state.mutagen_temp_hp_available_at_seconds,
        "selected_level_2_feat": state.selected_level_2_feat,
    }
