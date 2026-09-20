"""Finite Player Core 2 common Alchemist level-1/2 formula and feat content.

The records below are selected catalog facts, not a crafting language.  The
level-two Bomber progression chooses two previously unknown common formulas
from this finite level-one catalog, as the class permits formulas of any item
level the Alchemist can create. Definitions and prices follow the current
individual entries, with the Spring 2026 errata applied where noted in the
Alchemist rules source note. Every row links to its source entry.
"""

from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Literal

from .alchemy import ALCHEMIST_LEVEL_1_FEATS, ALCHEMIST_LEVEL_2_BOMBER_FEATS, FAR_LOBBER, QUICK_BOMBER


@dataclass(frozen=True, slots=True)
class AlchemySaveBonus:
    statistic: str
    against: str
    bonus: int
    duration_seconds: int


@dataclass(frozen=True, slots=True)
class BombFacts:
    damage_type: str
    initial_damage_dice: tuple[int, ...] = ()
    initial_damage_flat: int = 0
    persistent_damage_type: str | None = None
    persistent_damage_dice: tuple[int, ...] = ()
    persistent_damage_flat: int = 0
    splash_damage: int = 0
    on_hit_effect: str | None = None
    on_hit_effect_deadline: Literal["thrower_next_turn_start", "target_next_turn_end"] | None = None
    range_increment_ft: int = 20
    strength_damage: bool = False
    critical_splash_mode: Literal["unchanged"] = "unchanged"


@dataclass(frozen=True, slots=True)
class ElixirFacts:
    effect: Literal["heal", "save_bonus"]
    healing_dice: tuple[int, ...] = ()
    save_bonuses: tuple[AlchemySaveBonus, ...] = ()
    duration_seconds: int | None = None
    living_target_only: bool = False
    coagulant: bool = False


@dataclass(frozen=True, slots=True)
class MutagenBonus:
    statistic: str
    value: int
    modifier_type: Literal["item"] = "item"


@dataclass(frozen=True, slots=True)
class GrantedMutagenAttack:
    attack_id: str
    name: str
    damage_type: str
    damage_dice: tuple[int, ...]
    agile: bool = False
    magical: bool = True
    striking_applies: bool = False


@dataclass(frozen=True, slots=True)
class MutagenFacts:
    duration_seconds: int
    benefits: tuple[MutagenBonus, ...]
    drawbacks: tuple[str, ...]
    granted_attacks: tuple[GrantedMutagenAttack, ...] = ()
    recall_knowledge_critical_failure_becomes_failure: bool = False
    encumbrance_threshold_penalty_bulk: int = 0
    maximum_carry_penalty_bulk: int = 0


@dataclass(frozen=True, slots=True)
class PoisonStage:
    stage: int
    damage_dice: tuple[int, ...]
    conditions: tuple[tuple[str, int], ...] = ()


@dataclass(frozen=True, slots=True)
class PoisonFacts:
    delivery: Literal["injury", "ingested"]
    save_dc: int
    onset_seconds: int
    maximum_duration_seconds: int
    stage_interval_seconds: int
    stages: tuple[PoisonStage, ...]
    prevents_sickened_reduction_while_active: bool = False
    ordinary_hands_required: int = 2
    ordinary_application_actions: int = 2
    toxicologist_application_actions: int = 1


AlchemyItemFacts = BombFacts | ElixirFacts | MutagenFacts | PoisonFacts


@dataclass(frozen=True, slots=True)
class AlchemyFormula:
    formula_id: str
    name: str
    level: int
    price_gp: int
    category: Literal["bomb", "healing_elixir", "mutagen", "poison"]
    facts: AlchemyItemFacts
    traits: frozenset[str]
    bulk: str
    hands_required: int
    activation_actions: int
    activation_kind: str
    source_url: str


@dataclass(frozen=True, slots=True)
class AlchemistFeatProfile:
    feat_id: str
    name: str
    level: int
    source_url: str
    action_cost: int | None = None
    action_modes: tuple[str, ...] = ()
    includes_strike: bool = False
    only_strike_advances_map: bool = False
    quick_vial_eligible: bool = False
    bomb_range_increment_ft: int | None = None


ALCHEMIST_FORMULAS: tuple[AlchemyFormula, ...] = (
    AlchemyFormula(
        formula_id="alchemists_fire_lesser",
        name="Alchemist's Fire (lesser)", level=1, price_gp=3, category="bomb",
        facts=BombFacts("fire", initial_damage_dice=(8,), persistent_damage_type="fire", persistent_damage_flat=1, splash_damage=1),
        traits=frozenset({"alchemical", "consumable", "bomb", "splash", "thrown"}), bulk="L", hands_required=1,
        activation_actions=1, activation_kind="strike", source_url="https://2e.aonprd.com/Equipment.aspx?ID=3287",
    ),
    AlchemyFormula(
        formula_id="acid_flask_lesser",
        name="Acid Flask (lesser)", level=1, price_gp=3, category="bomb",
        facts=BombFacts("acid", initial_damage_flat=1, persistent_damage_type="acid", persistent_damage_dice=(6,), splash_damage=1),
        traits=frozenset({"alchemical", "consumable", "bomb", "splash", "thrown"}), bulk="L", hands_required=1,
        activation_actions=1, activation_kind="strike", source_url="https://2e.aonprd.com/Equipment.aspx?ID=3286",
    ),
    AlchemyFormula(
        formula_id="bottled_lightning_lesser",
        name="Bottled Lightning (lesser)", level=1, price_gp=3, category="bomb",
        facts=BombFacts("electricity", initial_damage_dice=(6,), splash_damage=1, on_hit_effect="off_guard", on_hit_effect_deadline="thrower_next_turn_start"),
        traits=frozenset({"alchemical", "consumable", "bomb", "splash", "thrown", "electricity"}), bulk="L", hands_required=1,
        activation_actions=1, activation_kind="strike", source_url="https://2e.aonprd.com/Equipment.aspx?ID=3290",
    ),
    AlchemyFormula(
        formula_id="frost_vial_lesser",
        name="Frost Vial (lesser)", level=1, price_gp=3, category="bomb",
        facts=BombFacts("cold", initial_damage_dice=(6,), splash_damage=1, on_hit_effect="speed_minus_5", on_hit_effect_deadline="target_next_turn_end"),
        traits=frozenset({"alchemical", "consumable", "bomb", "splash", "thrown", "cold"}), bulk="L", hands_required=1,
        activation_actions=1, activation_kind="strike", source_url="https://2e.aonprd.com/Equipment.aspx?ID=3293",
    ),
    AlchemyFormula(
        formula_id="elixir_of_life_minor",
        name="Elixir of Life (minor)", level=1, price_gp=3, category="healing_elixir",
        facts=ElixirFacts(
            "heal", healing_dice=(6,),
            save_bonuses=(AlchemySaveBonus("fortitude", "poison_or_disease", 1, 600),),
            duration_seconds=600, living_target_only=True, coagulant=False,
        ),
        traits=frozenset({"alchemical", "consumable", "elixir", "healing"}), bulk="L", hands_required=1,
        activation_actions=1, activation_kind="interact_drink_or_feed", source_url="https://2e.aonprd.com/Equipment.aspx?ID=3308",
    ),
    AlchemyFormula(
        formula_id="antidote_lesser",
        name="Antidote (lesser)", level=1, price_gp=3, category="healing_elixir",
        facts=ElixirFacts("save_bonus", save_bonuses=(AlchemySaveBonus("fortitude", "poison", 2, 6 * 60 * 60),), duration_seconds=6 * 60 * 60),
        traits=frozenset({"alchemical", "consumable", "elixir", "healing"}), bulk="L", hands_required=1,
        activation_actions=1, activation_kind="interact_drink_or_feed", source_url="https://2e.aonprd.com/Equipment.aspx?ID=3296",
    ),
    AlchemyFormula(
        formula_id="antiplague_lesser",
        name="Antiplague (lesser)", level=1, price_gp=3, category="healing_elixir",
        facts=ElixirFacts("save_bonus", save_bonuses=(AlchemySaveBonus("fortitude", "disease", 2, 24 * 60 * 60),), duration_seconds=24 * 60 * 60),
        traits=frozenset({"alchemical", "consumable", "elixir", "healing"}), bulk="L", hands_required=1,
        activation_actions=1, activation_kind="interact_drink_or_feed", source_url="https://2e.aonprd.com/Equipment.aspx?ID=3297",
    ),
    AlchemyFormula(
        formula_id="bestial_mutagen_lesser",
        name="Bestial Mutagen (lesser)", level=1, price_gp=4, category="mutagen",
        facts=MutagenFacts(
            60,
            (MutagenBonus("athletics", 1), MutagenBonus("unarmed_attack", 1)),
            ("reflex:-2:untyped", "acrobatics:-2:untyped", "stealth:-2:untyped"),
            (
                GrantedMutagenAttack("bestial_claws", "Bestial Claws", "slashing", (4,), agile=True),
                GrantedMutagenAttack("bestial_jaws", "Bestial Jaws", "piercing", (6,)),
            ),
        ),
        traits=frozenset({"alchemical", "consumable", "elixir", "mutagen", "polymorph"}), bulk="L", hands_required=1,
        activation_actions=1, activation_kind="interact_drink", source_url="https://2e.aonprd.com/Equipment.aspx?ID=3315",
    ),
    AlchemyFormula(
        formula_id="cognitive_mutagen_lesser",
        name="Cognitive Mutagen (lesser)", level=1, price_gp=4, category="mutagen",
        facts=MutagenFacts(
            60,
            tuple(MutagenBonus(stat, 1) for stat in ("arcana", "crafting", "lore", "occultism", "society", "recall_knowledge")),
            ("weapon_attack:-2:untyped", "unarmed_attack:-2:untyped", "athletics:-2:untyped", "acrobatics:-2:untyped"),
            recall_knowledge_critical_failure_becomes_failure=True,
            encumbrance_threshold_penalty_bulk=2,
            maximum_carry_penalty_bulk=4,
        ),
        traits=frozenset({"alchemical", "consumable", "elixir", "mutagen", "polymorph"}), bulk="L", hands_required=1,
        activation_actions=1, activation_kind="interact_drink", source_url="https://2e.aonprd.com/Equipment.aspx?ID=3316",
    ),
    AlchemyFormula(
        formula_id="giant_centipede_venom",
        name="Giant Centipede Venom", level=1, price_gp=4, category="poison",
        facts=PoisonFacts(
            "injury", 17, 0, 6 * 6, 6,
            (
                PoisonStage(1, (4,)),
                PoisonStage(2, (4,), (("fatigued", 1),)),
                PoisonStage(3, (4,), (("fatigued", 1), ("clumsy", 1))),
            ),
        ),
        traits=frozenset({"alchemical", "consumable", "poison", "injury"}), bulk="L", hands_required=2,
        activation_actions=2, activation_kind="interact_apply_to_weapon_or_ammunition", source_url="https://2e.aonprd.com/Equipment.aspx?ID=3334",
    ),
    AlchemyFormula(
        formula_id="arsenic",
        name="Arsenic", level=1, price_gp=3, category="poison",
        facts=PoisonFacts(
            "ingested", 18, 10 * 60, 5 * 60, 60,
            (
                PoisonStage(1, (4,), (("sickened", 1),)),
                PoisonStage(2, (6,), (("sickened", 2),)),
                PoisonStage(3, (8,), (("sickened", 3),)),
            ),
            prevents_sickened_reduction_while_active=True,
            ordinary_hands_required=1,
            ordinary_application_actions=1,
            toxicologist_application_actions=1,
        ),
        traits=frozenset({"alchemical", "consumable", "poison", "ingested"}), bulk="L", hands_required=1,
        activation_actions=1, activation_kind="interact_apply_to_food_or_mouth", source_url="https://2e.aonprd.com/Equipment.aspx?ID=3322",
    ),
)

ALCHEMIST_FORMULAS_BY_ID = MappingProxyType({formula.formula_id: formula for formula in ALCHEMIST_FORMULAS})
FORMULAS_BY_ID = ALCHEMIST_FORMULAS_BY_ID

ALCHEMIST_LEVEL_1_FEAT_MENU: tuple[str, ...] = tuple(sorted(ALCHEMIST_LEVEL_1_FEATS))
ALCHEMIST_LEVEL_1_FEATS_BY_ID = MappingProxyType(
    {
        QUICK_BOMBER: AlchemistFeatProfile(
            feat_id=QUICK_BOMBER,
            name="Quick Bomber",
            level=1,
            source_url="https://2e.aonprd.com/Feats.aspx?ID=5764",
            action_cost=1,
            action_modes=("draw_bomb", "draw_versatile_vial", "quick_alchemy_bomb"),
            includes_strike=True,
            only_strike_advances_map=True,
            quick_vial_eligible=True,
        ),
        FAR_LOBBER: AlchemistFeatProfile(
            feat_id=FAR_LOBBER,
            name="Far Lobber",
            level=1,
            source_url="https://2e.aonprd.com/Feats.aspx?ID=5763",
            bomb_range_increment_ft=30,
        ),
    }
)

# A level-two Alchemist can select an eligible level-one class feat in its
# new class-feat slot.  This finite Bomber menu therefore supports keeping
# Quick Bomber while gaining Far Lobber, or the inverse, without pretending to
# implement unrelated mutagen, poison-additive, or Crafting-check feats.
ALCHEMIST_LEVEL_2_BOMBER_FEAT_MENU: tuple[str, ...] = tuple(sorted(ALCHEMIST_LEVEL_2_BOMBER_FEATS))
ALCHEMIST_LEVEL_2_BOMBER_FEATS_BY_ID = MappingProxyType(
    {feat_id: ALCHEMIST_LEVEL_1_FEATS_BY_ID[feat_id] for feat_id in ALCHEMIST_LEVEL_2_BOMBER_FEAT_MENU}
)
