"""Runtime-admitted fixed content plus a staged S3i expansion catalog."""

from dataclasses import replace
from types import MappingProxyType
from typing import Mapping

from .model import (
    AttackDefinition,
    CreatureDefinition,
    CreaturePlacement,
    EncounterSetup,
    HealthMode,
    Position,
    PreparedSpellDefinition,
)
from .s2_interaction_content import S2_INTERACTION_SETUPS, build_s2_definitions
from .s3_interaction_content import S3_INTERACTION_SETUPS, build_s3_definitions
from .barbarian_content import (
    ANIMAL_BARBARIAN_SETUPS,
    BARBARIAN_DEFINITIONS,
    BARBARIAN_SLICE1_CHARACTER,
    BARBARIAN_TEST_ENEMY,
    BARBARIAN_TEST_SETUP,
    DRAGON_BARBARIAN_SETUPS,
)
from .typed_defense_content import (
    TYPED_DEFENSE_SETUPS,
    WAYSTONE_SENTINEL,
    WAYSTONE_SPELL_SENTINEL,
)
from .damage import DamageDefense
from .items import ItemInstance
from .rogue_content import ROGUE_THIEF_PLAYABLE
from .sorcerer_content import (
    ANGELIC_FEAR_SETUP,
    ANGELIC_FEAR_REACTION_SETUP,
    ANGELIC_FIRST_CAST_SETUP,
    ANGELIC_SORCERER_STAGED as _ANGELIC_SORCERER_STAGED,
)
from .justice_content import JUSTICE_CHAMPION, JUSTICE_CHAMPION_SETUP
from .investigator_content import (
    FORENSIC_INVESTIGATOR,
    FORENSIC_INVESTIGATOR_HEALING_SETUP,
    FORENSIC_INVESTIGATOR_VS_TWO_DOGS,
    INVESTIGATOR_DEFINITIONS,
    INVESTIGATOR_SETUPS,
)
from .swashbuckler_content import (
    BRAGGART_SWASHBUCKLER,
    BRAGGART_SWASHBUCKLER_SETUP,
)
from .bard_content import MAESTRO_BARD_STAGED, MAESTRO_BARD_ANTHEM_SETUP, MAESTRO_BARD_FEAR_SETUP
from .ranger_monk_content import (
    MONK,
    MONK_KAMA_FLURRY_SETUP,
    RANGER_PRECISION,
    RANGER_PRECISION_BOW_SETUP,
)
from .w5_stance_content import build_w5_stance_content
from .wizard_content import (
    BATTLE_MAGIC_WIZARD,
    BATTLE_MAGIC_WIZARD_DAZE,
    BATTLE_MAGIC_WIZARD_DAZE_SETUP,
    BATTLE_MAGIC_WIZARD_SUPPRESSION_SPELLS,
    BATTLE_MAGIC_WIZARD_SUPPRESSION_SPELLS_SETUP,
    BATTLE_MAGIC_WIZARD_MOVEMENT_SPELLS,
    BATTLE_MAGIC_WIZARD_MOVEMENT_SPELLS_SETUP,
    BATTLE_MAGIC_WIZARD_HERO_SAVE_SETUP,
    BATTLE_MAGIC_WIZARD_NEXT_SETUP,
    BATTLE_MAGIC_WIZARD_REACTION_SETUP,
    BATTLE_MAGIC_WIZARD_RUNIC_BODY,
    BATTLE_MAGIC_WIZARD_RUNIC_BODY_SETUP,
    BATTLE_MAGIC_WIZARD_TELEKINETIC_PROJECTILE,
    BATTLE_MAGIC_WIZARD_TELEKINETIC_PROJECTILE_SETUP,
    BATTLE_MAGIC_WIZARD_SETUP,
)
from .druid_content import STORM_DRUID, STORM_DRUID_SETUP, STORM_DRUID_NEXT_SETUP, STORM_DRUID_SAVE_SETUP, STORM_DRUID_WEATHER_SETUP, STORM_DRUID_SOCIAL_SETUP
from .oracle_content import LIFE_ORACLE, LIFE_ORACLE_NUDGE_SETUP, VOID_HEALING_ORACLE, LIFE_ORACLE_LASH_SETUP, LIFE_ORACLE_NEXT_SETUP
from .alchemist_content import (
    BOMBER_ALCHEMIST,
    BOMBER_ALCHEMIST_NEXT_SETUP,
    BOMBER_ALCHEMIST_SETUP,
    BOMBER_FORMULA_IDS,
    BOMBER_LEVEL_2_ITEM_SUPPORT_FORMULA_IDS,
    BOMBER_LEVEL_2_BOMB_ATTACKS,
    BOMBER_LEVEL_2_CONDITION_BOMB_ATTACKS,
)
from .witch_content import (
    COMMAND_TARGET,
    FAITHS_FLAMEKEEPER_DAZE_SETUP,
    FAITHS_FLAMEKEEPER_SUPPRESSION_SPELLS_SETUP,
    FAITHS_FLAMEKEEPER_SETUP,
    FAITHS_FLAMEKEEPER_NEXT_SETUP,
    FAITHS_FLAMEKEEPER_WITCH,
    FAITHS_FLAMEKEEPER_WITCH_DAZE,
    FAITHS_FLAMEKEEPER_WITCH_SUPPRESSION_SPELLS,
    FLAMEKEEPER_FOX,
    SUPPRESSION_TARGET,
)
from .l2_horizontal_content import L2_HORIZONTAL_DEFINITIONS, L2_HORIZONTAL_SETUPS
from .l2_ranger_content import (
    RANGER_PRECISION_LEVEL_2,
    RANGER_PRECISION_LEVEL_2_HUNTERS_AIM_SETUP,
)
from .l2_reach_content import L2_REACH_DEFINITIONS, L2_REACH_SETUPS
from .l2_martial_content import build_l2_martial_content
from .l2_prepared_content import L2_PREPARED_DEFINITIONS, L2_PREPARED_SETUPS
from .l2_divine_content import build_l2_divine_content
from .w3_caster_content import W3_CASTER_DEFINITIONS, W3_CASTER_SETUPS
from .w4_caster_content import build_w4_caster_content
from .w4_defensive_content import build_w4_defensive_content
from .w5_arms_content import W5_ARMS_DEFINITIONS, W5_ARMS_SETUPS
from .w5_focus_content import build_w5_focus_content


# The Witch's L2 class-local sheet is deliberately held in staging until its
# two new familiar-learned divine spells have concrete finite-engine behavior.
# The Wizard L2 and both source-legal L1 Reach alternatives are independent
# of that unresolved learning contract.
_ADMITTED_L2_PREPARED_DEFINITION_IDS = frozenset({
    "wizard_battle_magic_level_2_cantrip_expansion",
    "wizard_battle_magic_level_1_reach_spell",
    "faiths_flamekeeper_witch_level_1_reach_spell",
    "faiths_flamekeeper_witch_level_2_cantrip_expansion",
})


# The normal Maestro admission uses the Witch's existing auditory Command
# rather than inventing an additional spell family solely for a reaction test.
MAESTRO_BARD_COUNTER_SETUP = EncounterSetup(
    "maestro_bard_counter_performance_command",
    "Maestro Counter Performance against Command",
    15,
    3,
    (
        CreaturePlacement("enemy_witch", FAITHS_FLAMEKEEPER_WITCH.definition_id, "Enemy Witch", "red", Position(1, 1)),
        CreaturePlacement("beneficiary", FAITHS_FLAMEKEEPER_WITCH.definition_id, "Beneficiary", "blue", Position(2, 1)),
        CreaturePlacement("maestro_bard", MAESTRO_BARD_STAGED.definition_id, "Maestro Bard", "blue", Position(3, 1)),
    ),
)

# Dim fixtures opt into the narrow lighting model with an explicit vision
# fact in the assembled content. The selected Angelic sheet remains neutral
# here so the admitted first-cast room is bright; dim diagnostics can derive
# their own explicit vision variant.
ANGELIC_SORCERER_STAGED = replace(_ANGELIC_SORCERER_STAGED, vision="ordinary")


# These numbers are authored test fixtures, not values taken from a published
# creature. Shared rule behavior follows the source note in
# docs/implementation/s1-s3-rules.md (reviewed 2026-09-15).
SYNTHETIC_MELEE = CreatureDefinition(
    definition_id="synthetic_melee_fixture",
    name="Synthetic grounded melee combatant",
    hp=12,
    ac=15,
    perception=3,
    land_speed_ft=25,
    attacks=(
        AttackDefinition(
            attack_id="simple_melee",
            name="Simple melee Strike",
            modifier=5,
            reach_ft=5,
            traits=frozenset({"attack", "melee"}),
            damage_type="bludgeoning",
            damage_dice=(6,),
            damage_modifier=2,
        ),
    ),
)

S1_SETUP = EncounterSetup(
    setup_id="s1_duel",
    name="S1 Synthetic Duel",
    width=7,
    height=5,
    placements=(
        CreaturePlacement(
            actor_id="synthetic_a",
            definition_id=SYNTHETIC_MELEE.definition_id,
            label="Synthetic NPC A",
            team="blue",
            position=Position(1, 2),
        ),
        CreaturePlacement(
            actor_id="synthetic_b",
            definition_id=SYNTHETIC_MELEE.definition_id,
            label="Synthetic NPC B",
            team="red",
            position=Position(5, 2),
        ),
    ),
)

MELEE_FIGHTER_M = CreatureDefinition(
    definition_id="fighter_m_level_1",
    name="Level 1 Melee Fighter M",
    hp=21,
    ac=18,
    perception=6,
    land_speed_ft=25,
    attacks=(
        AttackDefinition(
            attack_id="longsword",
            name="Longsword",
            modifier=9,
            reach_ft=5,
            traits=frozenset({"attack", "melee", "versatile-p"}),
            damage_type="slashing",
            damage_dice=(8,),
            damage_modifier=4,
            item_id="longsword",
        ),
        AttackDefinition(
            attack_id="fist",
            name="Fist",
            modifier=9,
            reach_ft=5,
            traits=frozenset({"attack", "melee", "agile", "finesse", "nonlethal", "unarmed"}),
            damage_type="bludgeoning",
            damage_dice=(4,),
            damage_modifier=4,
        ),
    ),
    kind="pc",
    health_mode=HealthMode.PC,
    vision="ordinary",
    abilities=("reactive_strike", "shield_block", "vicious_swing"),
    held_items=("longsword",),
    worn_items=("breastplate",),
    hero_points=1,
    size="medium",
    ability_modifiers=(
        ("strength", 4),
        ("dexterity", 1),
        ("constitution", 3),
        ("intelligence", 0),
        ("wisdom", 1),
        ("charisma", 0),
    ),
    skills=(
        ("acrobatics", "trained", 4),
        ("athletics", "trained", 7),
        ("crafting", "trained", 3),
        ("farming_lore", "trained", 3),
        ("intimidation", "trained", 3),
        ("medicine", "trained", 4),
        ("nature", "trained", 4),
        ("society", "trained", 3),
        ("survival", "trained", 4),
    ),
    saves=(
        ("fortitude", "expert", 8),
        ("reflex", "expert", 6),
        ("will", "trained", 4),
    ),
    feats=("Natural Skill", "Assurance (Athletics)", "Vicious Swing"),
    level=1,
    ancestry="Human",
    heritage="Skilled Human",
    background="Farmhand",
    class_name="Fighter",
    languages=("Common", "Goblin"),
    proficiencies=(
        ("perception", "expert"),
        ("fortitude", "expert"),
        ("reflex", "expert"),
        ("will", "trained"),
        ("simple_weapons", "expert"),
        ("martial_weapons", "expert"),
        ("advanced_weapons", "trained"),
        ("unarmed_attacks", "expert"),
        ("unarmored_defense", "trained"),
        ("all_armor", "trained"),
        ("class_dc", "trained"),
    ),
    sheet_notes=(
        "Other skills are untrained.",
        "Assurance (Athletics) result is 13; it replaces the roll and adds no modifiers.",
        "Longsword is versatile P; choose slashing or piercing for each Strike.",
        "Shield Block is retained on the sheet but unavailable: this fixed loadout owns no shield.",
        "No level-1 weapon critical specialization is granted.",
        "Supported action menu is narrower than the full Fighter class.",
        "Starting money remaining after the listed gear: 6 gp.",
    ),
    class_dc=17,
)

# One legal Fighter M skill-choice variant supports public Feint play without
# admitting the still-incomplete Rogue. Skilled Human replaces its elective
# Nature training with Deception; Natural Skill's Crafting/Society choices and
# every other reviewed Fighter M build fact remain unchanged.
FEINT_FIGHTER_M = replace(
    MELEE_FIGHTER_M,
    definition_id="fighter_m_deception_level_1",
    name="Level 1 Melee Fighter M (Deception elective)",
    skills=tuple(
        ("deception", "trained", 3) if skill == "nature" else (skill, rank, modifier)
        for skill, rank, modifier in MELEE_FIGHTER_M.skills
    ),
    sheet_notes=(
        *MELEE_FIGHTER_M.sheet_notes,
        "Skilled Human selects trained Deception instead of Nature; Natural Skill's Crafting/Society choices and all other build choices are unchanged.",
    ),
)

# The first shield fixture is a variant of the same fixed Fighter M build.
# Its recorded 6 gp remainder buys a steel shield (2 gp), leaving 4 gp.
STEEL_SHIELD_FIGHTER_M = replace(
    MELEE_FIGHTER_M,
    definition_id="fighter_m_steel_shield_level_1",
    name="Level 1 Melee Fighter M (Steel Shield)",
    sheet_notes=tuple(
        note for note in MELEE_FIGHTER_M.sheet_notes
        if "unavailable: this fixed loadout owns no shield" not in note
        and not note.startswith("Starting money remaining after the listed gear:")
    ) + (
        "A steel shield costs 2 gp from the recorded 6 gp remainder; 4 gp remains.",
        "Steel shield: +2 circumstance AC when raised; Hardness 5; HP 20 (BT 10).",
    ),
    item_instances=(ItemInstance("steel_shield", "steel_shield", hp=20),),
)

# Explicitly granted above-level test equipment exercises the first common
# fundamental weapon runes without changing this level-1 build's level or
# ordinary starting-gear budget.
RUNE_WEAPON_FIGHTER_M = replace(
    MELEE_FIGHTER_M,
    definition_id="fighter_m_plus1_striking_test",
    name="Level 1 Melee Fighter M (+1 Striking Test Weapon)",
    item_instances=(
        ItemInstance(
            "longsword",
            "longsword",
            rune_ids=("weapon_potency_1", "striking"),
        ),
    ),
    sheet_notes=(
        *MELEE_FIGHTER_M.sheet_notes,
        "Above-level +1 striking longsword is explicitly granted for this level-1 rules test; it is not ordinary starting gear.",
    ),
)

RUNE_ARMOR_FIGHTER_M = replace(
    MELEE_FIGHTER_M,
    definition_id="fighter_m_potency_resilient_test",
    name="Level 1 Melee Fighter M (+1 Potency Resilient Armor Test)",
    item_instances=(
        ItemInstance(
            "breastplate",
            "breastplate",
            rune_ids=("armor_potency_1", "resilient"),
            invested=True,
        ),
    ),
    sheet_notes=(
        *MELEE_FIGHTER_M.sheet_notes,
        "Above-level +1 potency/resilient runes are explicitly granted for this level-1 rules test; the runed breastplate is invested and is not ordinary starting gear.",
    ),
)

RUNE_ARMOR_UNINVESTED_FIGHTER_M = replace(
    RUNE_ARMOR_FIGHTER_M,
    definition_id="fighter_m_uninvested_rune_armor_test",
    name="Level 1 Fighter M (Uninvested Rune Armor Test)",
    item_instances=(replace(RUNE_ARMOR_FIGHTER_M.item_instances[0], invested=False),),
    sheet_notes=(
        *MELEE_FIGHTER_M.sheet_notes,
        "Diagnostic-only variant: the above-level runed breastplate is worn but not invested, so it grants no rune benefits.",
    ),
)

RUNE_ARMOR_UNWORN_FIGHTER_M = replace(
    RUNE_ARMOR_FIGHTER_M,
    definition_id="fighter_m_unworn_rune_armor_test",
    name="Level 1 Fighter M (Invested Rune Armor Stowed Test)",
    item_instances=(
        ItemInstance("mundane_breastplate", "breastplate"),
        ItemInstance(
            "runed_breastplate",
            "breastplate",
            rune_ids=("armor_potency_1", "resilient"),
            invested=True,
        ),
    ),
    worn_items=("mundane_breastplate",),
    stowed_items=("runed_breastplate",),
    sheet_notes=(
        *MELEE_FIGHTER_M.sheet_notes,
        "Diagnostic-only variant: a mundane breastplate is worn while the explicitly granted invested +1 potency/resilient breastplate is stowed; the spare's runes grant no benefits.",
    ),
)

SHORTBOW_FIGHTER_R = CreatureDefinition(
    definition_id="fighter_r_level_1",
    name="Level 1 Shortbow Fighter R",
    hp=21,
    ac=18,
    perception=6,
    land_speed_ft=25,
    attacks=(
        AttackDefinition(
            attack_id="shortbow",
            name="Shortbow",
            modifier=9,
            reach_ft=0,
            traits=frozenset({"attack", "ranged", "deadly", "deadly-d10"}),
            damage_type="piercing",
            damage_dice=(6,),
            damage_modifier=0,
            item_id="shortbow",
            attack_attribute="dexterity",
            damage_attribute=None,
            range_increment_ft=60,
            max_range_ft=360,
            hands_required=1,
            free_hands_required=1,
            ammunition_id="arrow",
            deadly_die=10,
            reload=0,
        ),
        AttackDefinition(
            attack_id="longsword",
            name="Longsword",
            modifier=6,
            reach_ft=5,
            traits=frozenset({"attack", "melee", "versatile-p"}),
            damage_type="slashing",
            damage_dice=(8,),
            damage_modifier=1,
            item_id="longsword",
        ),
        AttackDefinition(
            attack_id="fist",
            name="Fist",
            modifier=9,
            reach_ft=5,
            traits=frozenset({"attack", "melee", "agile", "finesse", "nonlethal", "unarmed"}),
            damage_type="bludgeoning",
            damage_dice=(4,),
            damage_modifier=1,
            attack_attribute="dexterity",
        ),
    ),
    kind="pc",
    health_mode=HealthMode.PC,
    abilities=("reactive_strike", "shield_block", "vicious_swing"),
    held_items=("shortbow",),
    worn_items=("leather_armor", "longsword"),
    hero_points=1,
    size="medium",
    ability_modifiers=(
        ("strength", 1),
        ("dexterity", 4),
        ("constitution", 3),
        ("intelligence", 0),
        ("wisdom", 1),
        ("charisma", 0),
    ),
    skills=(
        ("acrobatics", "trained", 7),
        ("athletics", "trained", 4),
        ("crafting", "trained", 3),
        ("farming_lore", "trained", 3),
        ("intimidation", "trained", 3),
        ("medicine", "trained", 4),
        ("nature", "trained", 4),
        ("society", "trained", 3),
        ("survival", "trained", 4),
    ),
    saves=(
        ("fortitude", "expert", 8),
        ("reflex", "expert", 9),
        ("will", "trained", 4),
    ),
    feats=("Natural Skill", "Assurance (Athletics)", "Vicious Swing"),
    level=1,
    ancestry="Human",
    heritage="Skilled Human",
    background="Farmhand",
    class_name="Fighter",
    languages=("Common", "Goblin"),
    proficiencies=(
        ("perception", "expert"),
        ("fortitude", "expert"),
        ("reflex", "expert"),
        ("will", "trained"),
        ("simple_weapons", "expert"),
        ("martial_weapons", "expert"),
        ("advanced_weapons", "trained"),
        ("unarmed_attacks", "expert"),
        ("unarmored_defense", "trained"),
        ("all_armor", "trained"),
        ("class_dc", "trained"),
    ),
    sheet_notes=(
        "Other skills are untrained.",
        "Assurance (Athletics) result is 13; it replaces the roll and adds no modifiers.",
        "Shortbow is held at the start with the other hand free; each shot consumes an arrow.",
        "Shortbow has reload 0, a 60-foot range increment, 360-foot maximum, deadly d10, and 1+ hands; ",
        "it adds no Strength damage and is neither propulsive nor volley.",
        "Longsword is carried and available to draw; it is versatile P. Vicious Swing is melee only.",
        "Shield Block is retained on the sheet but unavailable: this fixed loadout owns no shield.",
        "No level-1 weapon critical specialization is granted.",
        "Supported action menu is narrower than the full Fighter class.",
        "Starting money remaining after the listed gear: 8 gp 8 sp.",
    ),
    class_dc=17,
    ammunition=(("arrow", 20),),
)

WARPRIEST_C = CreatureDefinition(
    definition_id="warpriest_c_level_1",
    name="Level 1 Iomedaean Warpriest C",
    hp=17,
    ac=18,
    perception=7,
    land_speed_ft=25,
    attacks=(
        AttackDefinition(
            attack_id="longsword",
            name="Longsword",
            modifier=6,
            reach_ft=5,
            traits=frozenset({"attack", "melee", "versatile-p"}),
            damage_type="slashing",
            damage_dice=(8,),
            damage_modifier=3,
            item_id="longsword",
        ),
        AttackDefinition(
            attack_id="fist",
            name="Fist",
            modifier=6,
            reach_ft=5,
            traits=frozenset({"attack", "melee", "agile", "finesse", "nonlethal", "unarmed"}),
            damage_type="bludgeoning",
            damage_dice=(4,),
            damage_modifier=3,
        ),
    ),
    kind="pc",
    health_mode=HealthMode.PC,
    # Human ancestry and Skilled Human heritage retain ordinary vision; the
    # explicit fact admits this otherwise unchanged sheet into dim scenes.
    vision="ordinary",
    abilities=("shield_block",),
    held_items=("longsword",),
    worn_items=("breastplate",),
    hero_points=1,
    size="medium",
    ability_modifiers=(
        ("strength", 3),
        ("dexterity", 1),
        ("constitution", 1),
        ("intelligence", 0),
        ("wisdom", 4),
        ("charisma", 0),
    ),
    skills=(
        ("athletics", "trained", 6),
        ("crafting", "trained", 3),
        ("farming_lore", "trained", 3),
        ("intimidation", "trained", 3),
        ("medicine", "trained", 7),
        ("nature", "trained", 7),
        ("religion", "trained", 7),
        ("society", "trained", 3),
        ("survival", "trained", 7),
    ),
    saves=(
        ("fortitude", "expert", 6),
        ("reflex", "trained", 4),
        ("will", "expert", 9),
    ),
    feats=("Natural Skill", "Assurance (Athletics)"),
    level=1,
    ancestry="Human",
    heritage="Skilled Human",
    background="Farmhand",
    class_name="Cleric",
    deity="Iomedae",
    languages=("Common", "Goblin"),
    proficiencies=(
        ("perception", "trained"),
        ("fortitude", "expert"),
        ("reflex", "trained"),
        ("will", "expert"),
        ("simple_weapons", "trained"),
        ("unarmed_attacks", "trained"),
        ("favored_weapon", "trained"),
        ("unarmored_defense", "trained"),
        ("light_armor", "trained"),
        ("medium_armor", "trained"),
        ("spell_attack", "trained"),
        ("spell_dc", "trained"),
        ("class_dc", "trained"),
    ),
    sheet_notes=(
        "Assurance (Athletics) result is 13; it replaces the roll and adds no modifiers.",
        "Prepared divine casting; the listed slots are a fixed day's preparation.",
        "Prepared cantrips are repeatable and do not expend prepared rank-1 Heal slots.",
        "Iomedae grants the Heal font and holy sanctification; no focus pool or deity spell is added.",
        "Shield Block is retained on the sheet but unavailable: this fixed loadout owns no shield.",
        "No Deadly Simplicity: Iomedae's favored weapon is martial.",
        "No level-1 cleric class-feat selection or whole-class action coverage is claimed.",
        "Starting money remaining after breastplate and longsword: 6 gp.",
    ),
    class_dc=17,
    prepared_spells=(
        PreparedSpellDefinition("cantrip_divine_lance", "cantrip", "divine_lance", rank=1, cantrip=True),
        PreparedSpellDefinition("cantrip_void_warp", "cantrip", "void_warp", rank=1, cantrip=True),
        PreparedSpellDefinition("cantrip_guidance", "cantrip", "guidance", rank=1, cantrip=True),
        PreparedSpellDefinition("cantrip_stabilize", "cantrip", "stabilize", rank=1, cantrip=True),
        PreparedSpellDefinition("cantrip_light", "cantrip", "light", rank=1, cantrip=True),
        PreparedSpellDefinition("ordinary_heal_1", "ordinary", "heal", rank=1),
        PreparedSpellDefinition("ordinary_heal_2", "ordinary", "heal", rank=1),
        PreparedSpellDefinition("font_heal_1", "font", "heal", rank=1),
        PreparedSpellDefinition("font_heal_2", "font", "heal", rank=1),
        PreparedSpellDefinition("font_heal_3", "font", "heal", rank=1),
        PreparedSpellDefinition("font_heal_4", "font", "heal", rank=1),
    ),
    spell_attack=7,
    spell_dc=17,
    spell_attribute="wisdom",
    spell_sanctification="holy",
)

# A fixed legal alternate preparation for the bounded Sure Strike encounter.
# It preserves the production Warpriest sheet and changes only the second
# ordinary rank-1 slot.
WARPRIEST_C_SURE_STRIKE = replace(
    WARPRIEST_C,
    definition_id="warpriest_c_sure_strike_level_1",
    name="Level 1 Iomedaean Warpriest C (Sure Strike alternate)",
    prepared_spells=tuple(
        replace(
            slot,
            slot_id="ordinary_sure_strike_1",
            spell_id="sure_strike",
        )
        if slot.slot_id == "ordinary_heal_2" else slot
        for slot in WARPRIEST_C.prepared_spells
    ),
    sheet_notes=WARPRIEST_C.sheet_notes + (
        "Fixed alternate preparation: ordinary_heal_2 is replaced by rank-1 Sure Strike; the original Warpriest preparation remains available.",
    ),
)

W4_CASTER_DEFINITIONS, W4_CASTER_SETUPS = build_w4_caster_content(WARPRIEST_C)
W4_CASTER_DEFINITION_MAP = {
    definition.definition_id: definition for definition in W4_CASTER_DEFINITIONS
}
W5_FOCUS_DEFINITIONS, W5_FOCUS_SETUPS = build_w5_focus_content(WARPRIEST_C)

# Soothe is a shared rank-1 spell for the future Bard and Life Oracle slices.
# This remains a staged occult prepared-caster fixture: it exercises the spell
# once without admitting either future class or changing the accepted
# Warpriest preparation.
SOOTHE_TEST_CASTER = replace(
    WARPRIEST_C,
    definition_id="warpriest_c_soothe_staged",
    name="Staged Occult Soothe Test Caster",
    # Soothe is an occult spell.  This authored fixture gives it an explicit
    # occult prepared-caster access record and exactly one ordinary rank-1
    # slot, without changing the accepted Warpriest or admitting Bard/Oracle.
    class_name="Staged occult Soothe caster",
    spell_tradition="occult",
    prepared_spells=(
        PreparedSpellDefinition("soothe_1", "ordinary", "soothe", rank=1),
    ),
    sheet_notes=(
        "Staged common-spell fixture: Soothe is an occult spell and this authored caster has one explicit ordinary rank-1 occult preparation.",
        "This fixture exercises Soothe only; it does not admit the future Bard or Life Oracle or alter the accepted Warpriest preparation.",
    ),
)

# This definition exists only in the typed-damage diagnostic setup. Its ward
# is an explicit authored test grant, not a Cleric or Warpriest class feature.
TYPED_DEFENSE_WARD_GRANTED_WARPRIEST = replace(
    WARPRIEST_C,
    definition_id="warpriest_c_typed_defense_test_grant",
    name="Level 1 Iomedaean Warpriest C (typed-defense test grant)",
    damage_defenses=(
        DamageDefense("weakness", "slashing", 3, source="diagnostic cracked ward"),
        DamageDefense("resistance", "all", 2, source="diagnostic waystone ward"),
    ),
    sheet_notes=WARPRIEST_C.sheet_notes + (
        "Diagnostic setup grant: weakness 3 to slashing and resistance 2 to all damage; this is not a class feature or ordinary equipment.",
    ),
)

GUARD_DOG = CreatureDefinition(
    definition_id="guard_dog_mc2924",
    name="Guard Dog",
    hp=8,
    ac=15,
    perception=6,
    land_speed_ft=30,
    attacks=(
        AttackDefinition(
            attack_id="jaws",
            name="Jaws",
            modifier=6,
            reach_ft=5,
            traits=frozenset({"attack", "melee", "unarmed"}),
            damage_type="piercing",
            damage_dice=(4,),
            damage_modifier=1,
        ),
    ),
    kind="animal",
    health_mode=HealthMode.ORDINARY,
    abilities=("pack_attack",),
    held_items=(),
    worn_items=(),
    hero_points=0,
    size="small",
    ability_modifiers=(
        ("strength", 1),
        ("dexterity", 2),
        ("constitution", 2),
        ("intelligence", -4),
        ("wisdom", 1),
        ("charisma", -1),
    ),
    skills=(
        ("acrobatics", None, 5),
        ("athletics", None, 4),
        ("stealth", None, 5),
        ("survival", None, 4),
    ),
    saves=(
        ("fortitude", None, 5),
        ("reflex", None, 7),
        ("will", None, 4),
    ),
    feats=(),
    level=-1,
    ancestry="Animal",
    senses=("Low-light vision", "Imprecise scent 30 feet"),
    vision="low_light",
    sheet_notes=(
        "Jaws have no agile, finesse, or nonlethal trait; attacks and damage use Strength.",
        "Pack Attack adds 1d4 when two other allies are within reach of the target.",
        "Senses cannot change targeting on this bright, fully observed map.",
        "Other special actions and optional creature abilities are unsupported.",
    ),
)

# The first Light prerequisite uses the already reviewed Fighter and Guard
# Dog sheets in a deliberately dim room.  The ordinary-vision Fighter is
# concealed at dim locations; the Guard Dog's actual low-light vision is an
# observer-relative exemption. Point Light orbs can be created in this scene;
# darkness behavior is not implied by this fixture.
DIM_TARGETING_SETUP = EncounterSetup(
    setup_id="dim_targeting_fixture",
    name="Dim targeting and low-light vision fixture",
    width=5,
    height=3,
    placements=(
        CreaturePlacement(
            "fighter_a", MELEE_FIGHTER_M.definition_id, "Fighter M", "blue", Position(1, 1)
        ),
        CreaturePlacement(
            "guard_dog_a", GUARD_DOG.definition_id, "Guard Dog", "red", Position(2, 1)
        ),
    ),
    ambient_light="dim",
)
# Keep a descriptive alias available to callers that use the printed scene
# name rather than the targeting-specific name.
DIM_LIGHT_SETUP = DIM_TARGETING_SETUP

DIM_REACTION_SETUP = EncounterSetup(
    setup_id="dim_reactive_strike_fixture",
    name="Dim Reactive Strike targeting fixture",
    width=4,
    height=3,
    placements=(
        CreaturePlacement(
            "fighter_a", MELEE_FIGHTER_M.definition_id, "Fighter M A", "blue", Position(1, 1)
        ),
        CreaturePlacement(
            "fighter_b", MELEE_FIGHTER_M.definition_id, "Fighter M B", "red", Position(2, 1)
        ),
    ),
    ambient_light="dim",
)

FIGHTER_M = MELEE_FIGHTER_M

FIGHTER_FLEET_SHORTSWORD, ELITE_GUARD_DOG = build_s2_definitions(MELEE_FIGHTER_M, GUARD_DOG)
(FIGHTER_RAPIER,) = build_s3_definitions(SHORTBOW_FIGHTER_R)

# The first Runic Weapon checkpoint needs physical mundane weapons that can
# cross actor ownership. Keep the historical definition ID for save
# compatibility. The curated Angelic first-cast room admits this exact
# mundane ItemInstance bridge while other transfer-only fixtures remain staged.
WEAPON_IDENTITY_FIGHTER_M = replace(
    MELEE_FIGHTER_M,
    definition_id="fighter_m_weapon_identity_staged",
    name="Level 1 Fighter M (mundane longsword identity)",
    item_instances=(ItemInstance("longsword", "longsword"),),
    sheet_notes=MELEE_FIGHTER_M.sheet_notes + (
        "Curated Angelic first-cast ally: the mundane longsword is an actual ItemInstance so its origin ID can survive transfer and save/load.",
    ),
)

WEAPON_IDENTITY_THIEF = replace(
    ROGUE_THIEF_PLAYABLE,
    definition_id="rogue_thief_weapon_identity_staged",
    name="Level 1 Thief Rogue (mundane shortsword identity staged)",
    item_instances=(ItemInstance("shortsword", "shortsword"),),
    sheet_notes=ROGUE_THIEF_PLAYABLE.sheet_notes + (
        "Staged identity fixture: the mundane shortsword is an actual ItemInstance so its origin ID can survive transfer.",
    ),
)

# The admitted Angelic first-cast room reuses the reviewed Fighter sheet while giving
# its ally an actual mundane longsword instance. This keeps existing Heal and
# Halo probes unchanged and gives Runic Weapon a real, saved item target.
ANGELIC_FIRST_CAST_SETUP = replace(
    ANGELIC_FIRST_CAST_SETUP,
    placements=tuple(
        replace(
            placement,
            definition_id=WEAPON_IDENTITY_FIGHTER_M.definition_id,
        )
        if placement.actor_id == "sorcerer_ally" else placement
        for placement in ANGELIC_FIRST_CAST_SETUP.placements
    ),
)

# The first bounded scene-carry route keeps the two Angelic party identities
# and introduces one fresh opponent identity. Its bright map is deliberately
# the same size as the first room so a carried Light attachment remains a
# scene-local object without requiring a new map or object model.
ANGELIC_NEXT_ENCOUNTER_SETUP = EncounterSetup(
    setup_id="sorcerer_angelic_next_encounter",
    name="Staged Angelic Sorcerer Next Encounter",
    width=7,
    height=5,
    placements=(
        CreaturePlacement(
            "angelic_sorcerer",
            ANGELIC_SORCERER_STAGED.definition_id,
            "Angelic Sorcerer",
            "blue",
            Position(1, 1),
        ),
        CreaturePlacement(
            "sorcerer_ally",
            WEAPON_IDENTITY_FIGHTER_M.definition_id,
            "Sorcerer's Ally",
            "blue",
            Position(2, 1),
        ),
        CreaturePlacement(
            "sorcerer_dog_b",
            GUARD_DOG.definition_id,
            "Guard Dog B",
            "red",
            Position(5, 1),
        ),
    ),
)

# A compact, source-backed occult caster room for the shared Soothe spell.
# It remains staged so the future Bard and Life Oracle are not admitted by
# this common-spell delivery.
SOOTHE_TEST_SETUP = EncounterSetup(
    setup_id="soothe_staged_occult_caster_vs_guard_dog",
    name="Staged Occult Soothe Caster vs. Guard Dog",
    width=5,
    height=3,
    placements=(
        CreaturePlacement(
            "soothe_caster",
            SOOTHE_TEST_CASTER.definition_id,
            "Soothe Caster",
            "blue",
            Position(1, 1),
        ),
        CreaturePlacement(
            "soothe_dog",
            GUARD_DOG.definition_id,
            "Guard Dog",
            "red",
            Position(2, 1),
        ),
    ),
)
L2_MARTIAL_DEFINITIONS, L2_MARTIAL_SETUPS = build_l2_martial_content(
    fighter=MELEE_FIGHTER_M,
    barbarian=BARBARIAN_SLICE1_CHARACTER.definition,
    monk=MONK,
    enemy_definition_id=GUARD_DOG.definition_id,
)
L2_DIVINE_DEFINITIONS, L2_DIVINE_SETUPS = build_l2_divine_content(
    champion=JUSTICE_CHAMPION,
    warpriest=WARPRIEST_C,
    oracle=LIFE_ORACLE,
    enemy_definition_id=GUARD_DOG.definition_id,
)
W4_DEFENSIVE_DEFINITIONS, W4_DEFENSIVE_SETUPS = build_w4_defensive_content(
    fighter=MELEE_FIGHTER_M,
    shield_fighter=STEEL_SHIELD_FIGHTER_M,
    ranged_fighter=SHORTBOW_FIGHTER_R,
    rogue=ROGUE_THIEF_PLAYABLE,
    enemy_id=GUARD_DOG.definition_id,
)
W5_STANCE_DEFINITIONS, W5_STANCE_SETUPS = build_w5_stance_content(
    monk=MONK,
    enemy_definition_id=GUARD_DOG.definition_id,
)

# The finite L2 Bomber keeps the admitted field pair and Quick Bomber from
# the level-one sheet, adds exactly the two source-selected common formulas,
# and takes Far Lobber in its new class-feat slot.  Formula-state construction
# remains in the shared encounter initializer so the alchemy module stays
# independent from the catalog.
BOMBER_ALCHEMIST_LEVEL_2_FORMULA_IDS = (
    *BOMBER_FORMULA_IDS,
    "alchemists_fire_lesser",
    "acid_flask_lesser",
)
BOMBER_ALCHEMIST_LEVEL_2_ITEM_SUPPORT_FORMULA_IDS = BOMBER_LEVEL_2_ITEM_SUPPORT_FORMULA_IDS
BOMBER_ALCHEMIST_LEVEL_2 = replace(
    BOMBER_ALCHEMIST,
    definition_id="bomber_alchemist_level_2_far_lobber",
    name="Level 2 Bomber Alchemist (Far Lobber)",
    hp=26,
    ac=18,
    perception=5,
    level=2,
    attacks=tuple(replace(attack, modifier=attack.modifier + 1) for attack in BOMBER_ALCHEMIST.attacks) + BOMBER_LEVEL_2_BOMB_ATTACKS,
    skills=tuple((name, rank, modifier + 1) for name, rank, modifier in BOMBER_ALCHEMIST.skills),
    saves=tuple((name, rank, modifier + 1) for name, rank, modifier in BOMBER_ALCHEMIST.saves),
    class_dc=18,
    abilities=(*BOMBER_ALCHEMIST.abilities, "far_lobber"),
    feats=(*BOMBER_ALCHEMIST.feats, "Far Lobber", "Quick Jump"),
    sheet_notes=(*BOMBER_ALCHEMIST.sheet_notes,
        "Level 2: HP rises by 9 (Alchemist 8 + Constitution 1), and level-based statistics rise by one.",
        "Far Lobber is the selected level-2 class feat. Its 30-foot bomb range increment is applied only through the selected Bomber alchemy state.",
        "The formula book adds lesser Alchemist's Fire and Acid Flask. Poison additions, including Black Adder Venom, remain outside this finite Bomber build.",
    ),
)
BOMBER_ALCHEMIST_LEVEL_2_ITEM_SUPPORT = replace(
    BOMBER_ALCHEMIST_LEVEL_2,
    definition_id="bomber_alchemist_level_2_item_support",
    name="Level 2 Bomber Alchemist (Item Support)",
    sheet_notes=(*BOMBER_ALCHEMIST_LEVEL_2.sheet_notes,
        "W2 item-support variant: the accepted W1 sheet remains unchanged while this finite ten-formula book adds Cheetah's Elixir, Juggernaut Mutagen, and Bravo's Brew.",
        "The item-support menu uses only common consumables at or below level 2; it does not add poison, affliction, or unsupported exploration effects.",
    ),
)
BOMBER_ALCHEMIST_LEVEL_2_CONDITION_BOMBS = replace(
    BOMBER_ALCHEMIST_LEVEL_2_ITEM_SUPPORT,
    definition_id="bomber_alchemist_level_2_condition_bombs",
    name="Level 2 Bomber Alchemist (Condition Bombs)",
    attacks=BOMBER_ALCHEMIST_LEVEL_2_ITEM_SUPPORT.attacks + BOMBER_LEVEL_2_CONDITION_BOMB_ATTACKS,
    sheet_notes=(*BOMBER_ALCHEMIST.sheet_notes,
        "Level 2: HP rises by 9 (Alchemist 8 + Constitution 1), and level-based statistics rise by one.",
        "Far Lobber is the selected level-2 class feat. Its 30-foot bomb range increment is applied only through the selected Bomber alchemy state.",
        "W3 condition-bomb variant: the finite book adds Dread Ampoule's frightened rider and Glue Bomb's speed penalty, critical immobilization, and Escape route.",
        "Thunderstone is intentionally not admitted because its auditory/deafened subsystem is outside this engine's supported condition model.",
    ),
)
BOMBER_ALCHEMIST_LEVEL_2_SETUP = EncounterSetup(
    "l2_bomber_far_lobber_vs_guard_dog",
    "Level 2 Far Lobber Bomber versus Guard Dog",
    15,
    3,
    (
        CreaturePlacement("alchemist", BOMBER_ALCHEMIST_LEVEL_2.definition_id, "Level 2 Bomber Alchemist", "blue", Position(1, 1)),
        CreaturePlacement("dog", GUARD_DOG.definition_id, "Guard Dog", "red", Position(7, 1)),
    ),
)

# The recovery route starts a fresh scene after the original guard dog has
# been defeated, so its opponent identity cannot be reused by next_encounter.
BOMBER_ALCHEMIST_LEVEL_2_NEXT_SETUP = EncounterSetup(
    "l2_bomber_far_lobber_next_vs_guard_dog",
    "Prepared Level 2 Far Lobber Bomber versus Guard Dog",
    15,
    3,
    (
        CreaturePlacement("alchemist", BOMBER_ALCHEMIST_LEVEL_2.definition_id, "Level 2 Bomber Alchemist", "blue", Position(1, 1)),
        CreaturePlacement("next_dog", GUARD_DOG.definition_id, "Guard Dog", "red", Position(7, 1)),
    ),
)

# 125 feet is beyond an ordinary bomb's 120-foot six-increment maximum but
# within Far Lobber's selected 180-foot maximum.  This makes the terminal
# target projection exercise the same typed range rule as Encounter.
BOMBER_ALCHEMIST_LEVEL_2_LONG_RANGE_SETUP = EncounterSetup(
    "l2_bomber_far_lobber_long_range_vs_guard_dog",
    "Level 2 Far Lobber Bomber Long Range versus Guard Dog",
    5,
    27,
    (
        CreaturePlacement("alchemist", BOMBER_ALCHEMIST_LEVEL_2.definition_id, "Level 2 Bomber Alchemist", "blue", Position(1, 1)),
        CreaturePlacement("long_range_dog", GUARD_DOG.definition_id, "Guard Dog", "red", Position(1, 26)),
    ),
)
BOMBER_ALCHEMIST_LEVEL_2_ITEM_SUPPORT_SETUP = EncounterSetup(
    "l2_bomber_item_support_vs_guard_dog",
    "Level 2 Item-Support Bomber versus Guard Dog",
    15,
    3,
    (
        CreaturePlacement("alchemist", BOMBER_ALCHEMIST_LEVEL_2_ITEM_SUPPORT.definition_id, "Level 2 Item-Support Bomber", "blue", Position(1, 1)),
        CreaturePlacement("dog", GUARD_DOG.definition_id, "Guard Dog", "red", Position(7, 1)),
    ),
)
BOMBER_ALCHEMIST_LEVEL_2_ITEM_SUPPORT_NEXT_SETUP = EncounterSetup(
    "l2_bomber_item_support_next_vs_guard_dog",
    "Prepared Level 2 Item-Support Bomber versus Guard Dog",
    15,
    3,
    (
        CreaturePlacement("alchemist", BOMBER_ALCHEMIST_LEVEL_2_ITEM_SUPPORT.definition_id, "Level 2 Item-Support Bomber", "blue", Position(1, 1)),
        CreaturePlacement("next_dog", GUARD_DOG.definition_id, "Guard Dog", "red", Position(7, 1)),
    ),
)
BOMBER_ALCHEMIST_LEVEL_2_CONDITION_BOMBS_SETUP = EncounterSetup(
    "l2_bomber_condition_bombs_vs_guard_dog",
    "Level 2 Condition-Bomb Bomber versus Guard Dog",
    15,
    3,
    (
        CreaturePlacement("alchemist", BOMBER_ALCHEMIST_LEVEL_2_CONDITION_BOMBS.definition_id, "Level 2 Condition-Bomb Bomber", "blue", Position(1, 1)),
        CreaturePlacement("dog", GUARD_DOG.definition_id, "Guard Dog", "red", Position(7, 1)),
    ),
)
BOMBER_ALCHEMIST_LEVEL_2_CONDITION_BOMBS_NEXT_SETUP = EncounterSetup(
    "l2_bomber_condition_bombs_next_vs_guard_dog",
    "Prepared Level 2 Condition-Bomb Bomber versus Guard Dog",
    15,
    3,
    (
        CreaturePlacement("alchemist", BOMBER_ALCHEMIST_LEVEL_2_CONDITION_BOMBS.definition_id, "Level 2 Condition-Bomb Bomber", "blue", Position(1, 1)),
        CreaturePlacement("next_dog", GUARD_DOG.definition_id, "Guard Dog", "red", Position(7, 1)),
    ),
)


CREATURES: Mapping[str, CreatureDefinition] = MappingProxyType(
    {
        **{definition.definition_id: definition for definition in BARBARIAN_DEFINITIONS},
        BARBARIAN_TEST_ENEMY.definition_id: BARBARIAN_TEST_ENEMY,
        WAYSTONE_SENTINEL.definition_id: WAYSTONE_SENTINEL,
        WAYSTONE_SPELL_SENTINEL.definition_id: WAYSTONE_SPELL_SENTINEL,
        SYNTHETIC_MELEE.definition_id: SYNTHETIC_MELEE,
        MELEE_FIGHTER_M.definition_id: MELEE_FIGHTER_M,
        FEINT_FIGHTER_M.definition_id: FEINT_FIGHTER_M,
        STEEL_SHIELD_FIGHTER_M.definition_id: STEEL_SHIELD_FIGHTER_M,
        RUNE_WEAPON_FIGHTER_M.definition_id: RUNE_WEAPON_FIGHTER_M,
        RUNE_ARMOR_FIGHTER_M.definition_id: RUNE_ARMOR_FIGHTER_M,
        RUNE_ARMOR_UNINVESTED_FIGHTER_M.definition_id: RUNE_ARMOR_UNINVESTED_FIGHTER_M,
        RUNE_ARMOR_UNWORN_FIGHTER_M.definition_id: RUNE_ARMOR_UNWORN_FIGHTER_M,
        SHORTBOW_FIGHTER_R.definition_id: SHORTBOW_FIGHTER_R,
        WARPRIEST_C.definition_id: WARPRIEST_C,
        WARPRIEST_C_SURE_STRIKE.definition_id: WARPRIEST_C_SURE_STRIKE,
        TYPED_DEFENSE_WARD_GRANTED_WARPRIEST.definition_id: TYPED_DEFENSE_WARD_GRANTED_WARPRIEST,
        GUARD_DOG.definition_id: GUARD_DOG,
        FIGHTER_FLEET_SHORTSWORD.definition_id: FIGHTER_FLEET_SHORTSWORD,
        ELITE_GUARD_DOG.definition_id: ELITE_GUARD_DOG,
        FIGHTER_RAPIER.definition_id: FIGHTER_RAPIER,
        ROGUE_THIEF_PLAYABLE.definition_id: ROGUE_THIEF_PLAYABLE,
        # Curated Angelic first-cast admission. Keep the historical IDs so
        # saves made while these sheets were staged continue to resolve.
        ANGELIC_SORCERER_STAGED.definition_id: ANGELIC_SORCERER_STAGED,
        JUSTICE_CHAMPION.definition_id: JUSTICE_CHAMPION,
        WEAPON_IDENTITY_FIGHTER_M.definition_id: WEAPON_IDENTITY_FIGHTER_M,
        BRAGGART_SWASHBUCKLER.definition_id: BRAGGART_SWASHBUCKLER,
        # The reviewed selected Forensic Investigator keeps its original
        # stable definition ID as it moves from staged to normal catalog.
        **INVESTIGATOR_DEFINITIONS,
        # Preserve the stable selected Ranger definition ID for saves made
        # before this reviewed combat setup entered the normal catalog.
        RANGER_PRECISION.definition_id: RANGER_PRECISION,
        # The selected Monk keeps its stable staged definition ID on normal
        # catalog admission. Horizontal Quick Jump is supported; vertical
        # terrain and High Jump remain outside this flat-map slice.
        MONK.definition_id: MONK,
        # The completed selected Battle Magic Wizard keeps its stable ID as
        # it moves into the normal catalog; diagnostic alternates stay staged.
        BATTLE_MAGIC_WIZARD.definition_id: BATTLE_MAGIC_WIZARD,
        BATTLE_MAGIC_WIZARD_DAZE.definition_id: BATTLE_MAGIC_WIZARD_DAZE,
        BATTLE_MAGIC_WIZARD_SUPPRESSION_SPELLS.definition_id: BATTLE_MAGIC_WIZARD_SUPPRESSION_SPELLS,
        STORM_DRUID.definition_id: STORM_DRUID,
        # Preserve the selected Oracle's stable ID while moving its completed
        # representative encounter into the ordinary catalog.
        LIFE_ORACLE.definition_id: LIFE_ORACLE,
        FAITHS_FLAMEKEEPER_WITCH.definition_id: FAITHS_FLAMEKEEPER_WITCH,
        FAITHS_FLAMEKEEPER_WITCH_DAZE.definition_id: FAITHS_FLAMEKEEPER_WITCH_DAZE,
        FAITHS_FLAMEKEEPER_WITCH_SUPPRESSION_SPELLS.definition_id: FAITHS_FLAMEKEEPER_WITCH_SUPPRESSION_SPELLS,
        FLAMEKEEPER_FOX.definition_id: FLAMEKEEPER_FOX,
        COMMAND_TARGET.definition_id: COMMAND_TARGET,
        SUPPRESSION_TARGET.definition_id: SUPPRESSION_TARGET,
        # The selected Maestro keeps its historical definition ID so existing
        # staged saves remain compatible after normal catalog admission.
        MAESTRO_BARD_STAGED.definition_id: MAESTRO_BARD_STAGED,
        # The selected Bomber retains its stable staged ID now that the full
        # level-1 recovery, preparation, venom, and terminal route is admitted.
        BOMBER_ALCHEMIST.definition_id: BOMBER_ALCHEMIST,
        BOMBER_ALCHEMIST_LEVEL_2.definition_id: BOMBER_ALCHEMIST_LEVEL_2,
        BOMBER_ALCHEMIST_LEVEL_2_ITEM_SUPPORT.definition_id: BOMBER_ALCHEMIST_LEVEL_2_ITEM_SUPPORT,
        # Selected L2 progression bundles retain explicit, finite public
        # sheets and encounters; no class/subclass discovery is implied.
        **L2_HORIZONTAL_DEFINITIONS,
        RANGER_PRECISION_LEVEL_2.definition_id: RANGER_PRECISION_LEVEL_2,
        **{definition.definition_id: definition for definition in L2_REACH_DEFINITIONS},
        **{definition.definition_id: definition for definition in W3_CASTER_DEFINITIONS},
        **W4_CASTER_DEFINITION_MAP,
        **L2_MARTIAL_DEFINITIONS,
        **L2_DIVINE_DEFINITIONS,
        **{definition.definition_id: definition for definition in W4_DEFENSIVE_DEFINITIONS},
        **{
            definition.definition_id: definition
            for definition in L2_PREPARED_DEFINITIONS
            if definition.definition_id in _ADMITTED_L2_PREPARED_DEFINITION_IDS
        },
        **W5_ARMS_DEFINITIONS,
        **W5_STANCE_DEFINITIONS,
        **W5_FOCUS_DEFINITIONS,
    }
)

# W4 offensive lane: four source-selected level-1 feats with finite weapon
# fixtures.  The builder is kept separate so the central catalog remains the
# only admission point and the lane can own its source/fixture notes.
from .w4_offensive_content import build_w4_offensive_content

W4_OFFENSIVE_DEFINITIONS, W4_OFFENSIVE_SETUPS = build_w4_offensive_content(
    fighter=MELEE_FIGHTER_M,
    ranger=RANGER_PRECISION,
    rogue=ROGUE_THIEF_PLAYABLE,
    enemy_definition_id=GUARD_DOG.definition_id,
)
CREATURES = MappingProxyType({**CREATURES, **W4_OFFENSIVE_DEFINITIONS})

ROGUE_THIEF_SETUP = EncounterSetup(
    setup_id="rogue_thief_vs_guard_dog",
    name="Thief Rogue's Observed Social Ambush",
    width=5,
    height=3,
    placements=(
        CreaturePlacement(
            "thief_rogue",
            ROGUE_THIEF_PLAYABLE.definition_id,
            "Thief Rogue",
            "blue",
            Position(1, 1),
            initiative_skill="deception",
            initiative_context="observed social confrontation",
        ),
        CreaturePlacement(
            "guard_dog",
            GUARD_DOG.definition_id,
            "Guard Dog",
            "red",
            Position(2, 1),
        ),
    ),
)

# Canonical cross-family fixtures exercise the selected Rogue's reaction
# against an ordinary weapon attack, a Reactive Strike, and a spell attack.
# They contain only already-admitted level-1 sheets; no state is injected by
# the tests that use them.
ROGUE_THIEF_FIGHTER_SETUP = EncounterSetup(
    setup_id="rogue_thief_vs_fighter_fixture",
    name="Thief Rogue and Fighter Reaction Fixture",
    width=5,
    height=3,
    placements=(
        CreaturePlacement("thief_rogue", ROGUE_THIEF_PLAYABLE.definition_id, "Thief Rogue", "blue", Position(1, 1)),
        CreaturePlacement("fighter_m", MELEE_FIGHTER_M.definition_id, "Fighter M", "red", Position(2, 1)),
    ),
)

ROGUE_THIEF_WARPRIEST_SETUP = EncounterSetup(
    setup_id="rogue_thief_vs_warpriest_fixture",
    name="Thief Rogue and Warpriest Spell Fixture",
    width=5,
    height=3,
    placements=(
        CreaturePlacement("thief_rogue", ROGUE_THIEF_PLAYABLE.definition_id, "Thief Rogue", "red", Position(2, 1)),
        CreaturePlacement("cleric_c", WARPRIEST_C.definition_id, "Warpriest C", "blue", Position(1, 1)),
    ),
)

STEEL_SHIELD_TEST_SETUP = EncounterSetup(
    setup_id="steel_shield_test",
    name="Steel Shield Fighter vs. Guard Dog",
    width=7,
    height=5,
    placements=(
        CreaturePlacement("shield_fighter", STEEL_SHIELD_FIGHTER_M.definition_id, "Shield Fighter", "blue", Position(1, 1)),
        CreaturePlacement("fighter_ally", MELEE_FIGHTER_M.definition_id, "Fighter Ally", "blue", Position(1, 3)),
        CreaturePlacement("guard_dog", GUARD_DOG.definition_id, "Guard Dog", "red", Position(2, 1)),
    ),
)

RUNE_WEAPON_TEST_SETUP = EncounterSetup(
    setup_id="fundamental_rune_weapon_test",
    name="Level 1 Fighter with Explicit +1 Striking Test Weapon vs. Guard Dog",
    width=5,
    height=3,
    placements=(
        CreaturePlacement(
            "rune_fighter",
            RUNE_WEAPON_FIGHTER_M.definition_id,
            "Rune Test Fighter",
            "blue",
            Position(1, 1),
        ),
        CreaturePlacement(
            "rune_dog",
            GUARD_DOG.definition_id,
            "Guard Dog",
            "red",
            Position(2, 1),
        ),
    ),
)

RUNE_ARMOR_AC_TEST_SETUP = EncounterSetup(
    setup_id="fundamental_rune_armor_ac_test",
    name="Guard Dog vs. Invested, Uninvested, and Stowed Rune Armor Tests",
    width=5,
    height=4,
    placements=(
        CreaturePlacement("armor_dog", GUARD_DOG.definition_id, "Guard Dog", "red", Position(2, 1)),
        CreaturePlacement("armor_active", RUNE_ARMOR_FIGHTER_M.definition_id, "Invested Rune Armor", "blue", Position(1, 1)),
        CreaturePlacement("armor_uninvested", RUNE_ARMOR_UNINVESTED_FIGHTER_M.definition_id, "Uninvested Rune Armor", "blue", Position(1, 2)),
        CreaturePlacement("armor_unworn", RUNE_ARMOR_UNWORN_FIGHTER_M.definition_id, "Stowed Rune Armor Spare", "blue", Position(2, 2)),
    ),
)

RUNE_ARMOR_DC_TEST_SETUP = EncounterSetup(
    setup_id="fundamental_rune_armor_save_dc_test",
    name="Maneuver Save DCs vs. Invested, Uninvested, and Stowed Rune Armor",
    width=5,
    height=4,
    placements=(
        CreaturePlacement("synthetic_a", SYNTHETIC_MELEE.definition_id, "Synthetic Combatant", "blue", Position(1, 1)),
        CreaturePlacement("armor_active", RUNE_ARMOR_FIGHTER_M.definition_id, "Invested Rune Armor", "red", Position(2, 1)),
        CreaturePlacement("armor_uninvested", RUNE_ARMOR_UNINVESTED_FIGHTER_M.definition_id, "Uninvested Rune Armor", "red", Position(1, 2)),
        CreaturePlacement("armor_unworn", RUNE_ARMOR_UNWORN_FIGHTER_M.definition_id, "Stowed Rune Armor Spare", "red", Position(2, 2)),
    ),
)

RUNE_ARMOR_SPELL_SAVE_TEST_SETUP = EncounterSetup(
    setup_id="fundamental_rune_armor_spell_save_test",
    name="Warpriest Void Warp vs. Invested Resilient Armor",
    width=5,
    height=3,
    placements=(
        CreaturePlacement("armor_cleric", WARPRIEST_C.definition_id, "Warpriest", "blue", Position(1, 1)),
        CreaturePlacement("armor_target", RUNE_ARMOR_FIGHTER_M.definition_id, "Invested Rune Armor", "red", Position(2, 1)),
    ),
)

RUNE_HANDWRAP_FIGHTER_M = replace(
    MELEE_FIGHTER_M,
    definition_id="fighter_m_invested_handwraps_test",
    name="Level 1 Melee Fighter M (Invested +1 Striking Handwraps Test)",
    item_instances=(
        ItemInstance(
            "handwraps",
            "handwraps_of_mighty_blows",
            rune_ids=("weapon_potency_1", "striking"),
            invested=True,
        ),
    ),
    worn_items=("breastplate", "handwraps"),
    sheet_notes=(
        *MELEE_FIGHTER_M.sheet_notes,
        "Above-level +1 striking handwraps are explicitly granted for this level-1 rules test; they are invested and affect the wearer's unarmed attacks.",
    ),
)

RUNE_HANDWRAP_UNINVESTED_FIGHTER_M = replace(
    RUNE_HANDWRAP_FIGHTER_M,
    definition_id="fighter_m_uninvested_handwraps_test",
    name="Level 1 Fighter M (Uninvested +1 Striking Handwraps Test)",
    item_instances=(replace(RUNE_HANDWRAP_FIGHTER_M.item_instances[0], invested=False),),
    sheet_notes=(
        *MELEE_FIGHTER_M.sheet_notes,
        "Diagnostic-only variant: the above-level runed handwraps are worn but not invested, so they grant no potency or striking benefits.",
    ),
)

# The handwrap fixture is defined after the base catalog block so its explicit
# item category is visible here; extend the immutable runtime map once.
CREATURES = MappingProxyType({
    **CREATURES,
    RUNE_HANDWRAP_FIGHTER_M.definition_id: RUNE_HANDWRAP_FIGHTER_M,
    RUNE_HANDWRAP_UNINVESTED_FIGHTER_M.definition_id: RUNE_HANDWRAP_UNINVESTED_FIGHTER_M,
})

RUNE_HANDWRAP_TEST_SETUP = EncounterSetup(
    setup_id="fundamental_rune_handwrap_test",
    name="Level 1 Fighter with Explicit +1 Striking Handwraps vs. Guard Dog",
    width=5,
    height=3,
    placements=(
        CreaturePlacement("wrap_fighter", RUNE_HANDWRAP_FIGHTER_M.definition_id, "Handwrap Test Fighter", "blue", Position(1, 1)),
        CreaturePlacement("wrap_dog", GUARD_DOG.definition_id, "Guard Dog", "red", Position(2, 1)),
    ),
)

RUNE_HANDWRAP_UNINVESTED_TEST_SETUP = EncounterSetup(
    setup_id="fundamental_rune_handwrap_uninvested_test",
    name="Level 1 Fighter with Uninvested +1 Striking Handwraps vs. Guard Dog",
    width=5,
    height=3,
    placements=(
        CreaturePlacement("wrap_fighter", RUNE_HANDWRAP_UNINVESTED_FIGHTER_M.definition_id, "Uninvested Handwrap Fighter", "blue", Position(1, 1)),
        CreaturePlacement("wrap_dog", GUARD_DOG.definition_id, "Guard Dog", "red", Position(2, 1)),
    ),
)

S2_SETUP = EncounterSetup(
    setup_id="s2_fighters_vs_guard_dogs",
    name="Two Level 1 Melee Fighters vs. Two Guard Dogs",
    width=7,
    height=5,
    placements=(
        CreaturePlacement("fighter_a", MELEE_FIGHTER_M.definition_id, "Fighter A", "blue", Position(1, 1)),
        CreaturePlacement("fighter_b", MELEE_FIGHTER_M.definition_id, "Fighter B", "blue", Position(1, 3)),
        CreaturePlacement("guard_dog_a", GUARD_DOG.definition_id, "Guard Dog A", "red", Position(5, 1)),
        CreaturePlacement("guard_dog_b", GUARD_DOG.definition_id, "Guard Dog B", "red", Position(5, 3)),
    ),
)

# Three allied dogs let separate S2B tests exercise the two-other-allies
# threshold. This fixture is present for testing, not a second PC roster.
S2_PACK_ATTACK_SETUP = EncounterSetup(
    setup_id="s2_pack_attack_fixture",
    name="Pack Attack Positioning Fixture",
    width=7,
    height=5,
    placements=(
        CreaturePlacement("fighter_target", MELEE_FIGHTER_M.definition_id, "Fighter Target", "blue", Position(2, 2)),
        CreaturePlacement("guard_dog_a", GUARD_DOG.definition_id, "Guard Dog A", "red", Position(1, 2)),
        CreaturePlacement("guard_dog_b", GUARD_DOG.definition_id, "Guard Dog B", "red", Position(2, 1)),
        CreaturePlacement("guard_dog_c", GUARD_DOG.definition_id, "Guard Dog C", "red", Position(2, 3)),
    ),
)

# Opposed PCs let public encounter tests exercise targeted health choices and
# Reactive Strike without fabricating a creature's state after initialization.
S2_PC_DUEL_SETUP = EncounterSetup(
    setup_id="s2_pc_duel_fixture",
    name="Opposed PC Health and Reaction Fixture",
    width=7,
    height=5,
    placements=(
        CreaturePlacement("fighter_a", MELEE_FIGHTER_M.definition_id, "Fighter A", "blue", Position(4, 1)),
        CreaturePlacement("fighter_b", MELEE_FIGHTER_M.definition_id, "Fighter B", "red", Position(5, 1)),
    ),
)

FEINT_FIGHTER_DUEL_SETUP = EncounterSetup(
    setup_id="s3_feint_fighter_duel",
    name="Deception-trained Fighter vs. Fighter",
    width=5,
    height=3,
    placements=(
        CreaturePlacement("feint_fighter", FEINT_FIGHTER_M.definition_id, "Fighter M (Deception)", "blue", Position(1, 1)),
        CreaturePlacement("duel_fighter", MELEE_FIGHTER_M.definition_id, "Fighter M", "red", Position(2, 1)),
    ),
)

# A focused Bear integration fixture places two PCs at tied initiative and a
# source-reviewed ordinary guard at lower initiative. It exercises the same
# public initialization, damage, and save paths as the single-PC test setup.
BARBARIAN_PC_PAIR_SETUP = EncounterSetup(
    setup_id="barbarian_pc_pair_test",
    name="Bear Barbarian and Fighter Initiative Pair Test",
    width=7,
    height=5,
    placements=(
        CreaturePlacement(
            "barbarian_test",
            BARBARIAN_SLICE1_CHARACTER.definition.definition_id,
            "Barbarian",
            "blue",
            Position(2, 1),
        ),
        CreaturePlacement(
            "fighter_pair",
            MELEE_FIGHTER_M.definition_id,
            "Fighter Partner",
            "blue",
            Position(2, 3),
        ),
        CreaturePlacement(
            "barbarian_guard",
            BARBARIAN_TEST_ENEMY.definition_id,
            "Test Guard",
            "red",
            Position(4, 2),
        ),
    ),
)

S2_READY = True
S3_READY = True

S3_SETUP = EncounterSetup(
    setup_id="s3_mixed_party_vs_three_guard_dogs",
    name="Fighter M, Fighter R, and Warpriest C vs. Three Guard Dogs",
    width=7,
    height=5,
    placements=(
        CreaturePlacement("fighter_m", MELEE_FIGHTER_M.definition_id, "Fighter M", "blue", Position(1, 0)),
        CreaturePlacement("fighter_r", SHORTBOW_FIGHTER_R.definition_id, "Fighter R", "blue", Position(1, 2)),
        CreaturePlacement("cleric_c", WARPRIEST_C.definition_id, "Warpriest C", "blue", Position(1, 4)),
        CreaturePlacement("guard_dog_a", GUARD_DOG.definition_id, "Guard Dog A", "red", Position(5, 0)),
        CreaturePlacement("guard_dog_b", GUARD_DOG.definition_id, "Guard Dog B", "red", Position(5, 2)),
        CreaturePlacement("guard_dog_c", GUARD_DOG.definition_id, "Guard Dog C", "red", Position(5, 4)),
    ),
)

SURE_STRIKE_WARPRIEST_SETUP = EncounterSetup(
    setup_id="sure_strike_warpriest_vs_guard_dog",
    name="Dim Sure Strike Warpriest vs. Guard Dog",
    width=5,
    height=3,
    ambient_light="dim",
    placements=(
        CreaturePlacement(
            "cleric_c",
            WARPRIEST_C_SURE_STRIKE.definition_id,
            "Warpriest C",
            "blue",
            Position(1, 1),
        ),
        CreaturePlacement(
            "guard_dog",
            GUARD_DOG.definition_id,
            "Guard Dog",
            "red",
            Position(2, 1),
        ),
    ),
)

WEAPON_IDENTITY_SETUP = EncounterSetup(
    setup_id="staged_weapon_identity_transfer",
    name="Staged mundane longsword transfer between compatible Fighters",
    width=7,
    height=3,
    placements=(
        CreaturePlacement("weapon_source", WEAPON_IDENTITY_FIGHTER_M.definition_id, "Weapon Source", "blue", Position(1, 1)),
        CreaturePlacement("weapon_recipient", WEAPON_IDENTITY_FIGHTER_M.definition_id, "Weapon Recipient", "blue", Position(2, 1)),
        CreaturePlacement("weapon_dog", GUARD_DOG.definition_id, "Guard Dog", "red", Position(1, 2)),
    ),
)

WEAPON_IDENTITY_SHORTSWORD_SETUP = EncounterSetup(
    setup_id="staged_weapon_identity_shortsword",
    name="Staged mundane shortsword identity",
    width=5,
    height=3,
    placements=(
        CreaturePlacement("shortsword_rogue", WEAPON_IDENTITY_THIEF.definition_id, "Shortsword Rogue", "blue", Position(1, 1)),
        CreaturePlacement("shortsword_dog", GUARD_DOG.definition_id, "Guard Dog", "red", Position(2, 1)),
    ),
)

SETUPS: Mapping[str, EncounterSetup] = MappingProxyType(
    {
        ROGUE_THIEF_SETUP.setup_id: ROGUE_THIEF_SETUP,
        **{setup.setup_id: setup for setup in W4_OFFENSIVE_SETUPS},
        ROGUE_THIEF_FIGHTER_SETUP.setup_id: ROGUE_THIEF_FIGHTER_SETUP,
        ROGUE_THIEF_WARPRIEST_SETUP.setup_id: ROGUE_THIEF_WARPRIEST_SETUP,
        BARBARIAN_TEST_SETUP.setup_id: BARBARIAN_TEST_SETUP,
        BARBARIAN_PC_PAIR_SETUP.setup_id: BARBARIAN_PC_PAIR_SETUP,
        S1_SETUP.setup_id: S1_SETUP,
        S2_SETUP.setup_id: S2_SETUP,
        S2_PACK_ATTACK_SETUP.setup_id: S2_PACK_ATTACK_SETUP,
        S2_PC_DUEL_SETUP.setup_id: S2_PC_DUEL_SETUP,
        FEINT_FIGHTER_DUEL_SETUP.setup_id: FEINT_FIGHTER_DUEL_SETUP,
        STEEL_SHIELD_TEST_SETUP.setup_id: STEEL_SHIELD_TEST_SETUP,
        RUNE_WEAPON_TEST_SETUP.setup_id: RUNE_WEAPON_TEST_SETUP,
        RUNE_ARMOR_AC_TEST_SETUP.setup_id: RUNE_ARMOR_AC_TEST_SETUP,
        RUNE_ARMOR_DC_TEST_SETUP.setup_id: RUNE_ARMOR_DC_TEST_SETUP,
        RUNE_ARMOR_SPELL_SAVE_TEST_SETUP.setup_id: RUNE_ARMOR_SPELL_SAVE_TEST_SETUP,
        RUNE_HANDWRAP_TEST_SETUP.setup_id: RUNE_HANDWRAP_TEST_SETUP,
        RUNE_HANDWRAP_UNINVESTED_TEST_SETUP.setup_id: RUNE_HANDWRAP_UNINVESTED_TEST_SETUP,
        S3_SETUP.setup_id: S3_SETUP,
        SURE_STRIKE_WARPRIEST_SETUP.setup_id: SURE_STRIKE_WARPRIEST_SETUP,
        ANGELIC_FIRST_CAST_SETUP.setup_id: ANGELIC_FIRST_CAST_SETUP,
        JUSTICE_CHAMPION_SETUP.setup_id: JUSTICE_CHAMPION_SETUP,
        BRAGGART_SWASHBUCKLER_SETUP.setup_id: BRAGGART_SWASHBUCKLER_SETUP,
        RANGER_PRECISION_BOW_SETUP.setup_id: RANGER_PRECISION_BOW_SETUP,
        MONK_KAMA_FLURRY_SETUP.setup_id: MONK_KAMA_FLURRY_SETUP,
        **INVESTIGATOR_SETUPS,
        **DRAGON_BARBARIAN_SETUPS,
        **ANIMAL_BARBARIAN_SETUPS,
        **TYPED_DEFENSE_SETUPS,
        **{setup.setup_id: setup for setup in S2_INTERACTION_SETUPS},
        **{setup.setup_id: setup for setup in S3_INTERACTION_SETUPS},
        BATTLE_MAGIC_WIZARD_SETUP.setup_id: BATTLE_MAGIC_WIZARD_SETUP,
        BATTLE_MAGIC_WIZARD_DAZE_SETUP.setup_id: BATTLE_MAGIC_WIZARD_DAZE_SETUP,
        BATTLE_MAGIC_WIZARD_SUPPRESSION_SPELLS_SETUP.setup_id: BATTLE_MAGIC_WIZARD_SUPPRESSION_SPELLS_SETUP,
        STORM_DRUID_SETUP.setup_id: STORM_DRUID_SETUP,
        LIFE_ORACLE_NUDGE_SETUP.setup_id: LIFE_ORACLE_NUDGE_SETUP,
        FAITHS_FLAMEKEEPER_SETUP.setup_id: FAITHS_FLAMEKEEPER_SETUP,
        FAITHS_FLAMEKEEPER_DAZE_SETUP.setup_id: FAITHS_FLAMEKEEPER_DAZE_SETUP,
        FAITHS_FLAMEKEEPER_SUPPRESSION_SPELLS_SETUP.setup_id: FAITHS_FLAMEKEEPER_SUPPRESSION_SPELLS_SETUP,
        MAESTRO_BARD_ANTHEM_SETUP.setup_id: MAESTRO_BARD_ANTHEM_SETUP,
        MAESTRO_BARD_FEAR_SETUP.setup_id: MAESTRO_BARD_FEAR_SETUP,
        MAESTRO_BARD_COUNTER_SETUP.setup_id: MAESTRO_BARD_COUNTER_SETUP,
        BOMBER_ALCHEMIST_SETUP.setup_id: BOMBER_ALCHEMIST_SETUP,
        BOMBER_ALCHEMIST_LEVEL_2_SETUP.setup_id: BOMBER_ALCHEMIST_LEVEL_2_SETUP,
        BOMBER_ALCHEMIST_LEVEL_2_NEXT_SETUP.setup_id: BOMBER_ALCHEMIST_LEVEL_2_NEXT_SETUP,
        BOMBER_ALCHEMIST_LEVEL_2_LONG_RANGE_SETUP.setup_id: BOMBER_ALCHEMIST_LEVEL_2_LONG_RANGE_SETUP,
        BOMBER_ALCHEMIST_LEVEL_2_ITEM_SUPPORT_SETUP.setup_id: BOMBER_ALCHEMIST_LEVEL_2_ITEM_SUPPORT_SETUP,
        BOMBER_ALCHEMIST_LEVEL_2_ITEM_SUPPORT_NEXT_SETUP.setup_id: BOMBER_ALCHEMIST_LEVEL_2_ITEM_SUPPORT_NEXT_SETUP,
        **L2_HORIZONTAL_SETUPS,
        RANGER_PRECISION_LEVEL_2_HUNTERS_AIM_SETUP.setup_id: RANGER_PRECISION_LEVEL_2_HUNTERS_AIM_SETUP,
        **{setup.setup_id: setup for setup in L2_REACH_SETUPS},
        **{setup.setup_id: setup for setup in W3_CASTER_SETUPS},
        **{setup.setup_id: setup for setup in W4_CASTER_SETUPS},
        **L2_MARTIAL_SETUPS,
        **L2_DIVINE_SETUPS,
        **{setup.setup_id: setup for setup in W4_DEFENSIVE_SETUPS},
        **{
            setup.setup_id: setup
            for setup in L2_PREPARED_SETUPS
            if setup.setup_id in _ADMITTED_L2_PREPARED_DEFINITION_IDS
        },
        **W5_ARMS_SETUPS,
        **W5_STANCE_SETUPS,
        **W5_FOCUS_SETUPS,
    }
)

# Closed-room diagnostics and the next-encounter continuation remain directly
# retrievable but staged.
_STAGED_CREATURES: Mapping[str, CreatureDefinition] = MappingProxyType({
    SOOTHE_TEST_CASTER.definition_id: SOOTHE_TEST_CASTER,
    WEAPON_IDENTITY_THIEF.definition_id: WEAPON_IDENTITY_THIEF,
    BATTLE_MAGIC_WIZARD_MOVEMENT_SPELLS.definition_id: BATTLE_MAGIC_WIZARD_MOVEMENT_SPELLS,
    BATTLE_MAGIC_WIZARD_RUNIC_BODY.definition_id: BATTLE_MAGIC_WIZARD_RUNIC_BODY,
    BATTLE_MAGIC_WIZARD_TELEKINETIC_PROJECTILE.definition_id: BATTLE_MAGIC_WIZARD_TELEKINETIC_PROJECTILE,
    STORM_DRUID.definition_id: STORM_DRUID,
    VOID_HEALING_ORACLE.definition_id: VOID_HEALING_ORACLE,
    FAITHS_FLAMEKEEPER_WITCH.definition_id: FAITHS_FLAMEKEEPER_WITCH,
    FLAMEKEEPER_FOX.definition_id: FLAMEKEEPER_FOX,
    COMMAND_TARGET.definition_id: COMMAND_TARGET,
    BOMBER_ALCHEMIST_LEVEL_2_CONDITION_BOMBS.definition_id: BOMBER_ALCHEMIST_LEVEL_2_CONDITION_BOMBS,
    **{
        definition.definition_id: definition
        for definition in L2_PREPARED_DEFINITIONS
        if definition.definition_id not in _ADMITTED_L2_PREPARED_DEFINITION_IDS
    },
})
_STAGED_SETUPS: Mapping[str, EncounterSetup] = MappingProxyType({
    DIM_TARGETING_SETUP.setup_id: DIM_TARGETING_SETUP,
    DIM_REACTION_SETUP.setup_id: DIM_REACTION_SETUP,
    ANGELIC_NEXT_ENCOUNTER_SETUP.setup_id: ANGELIC_NEXT_ENCOUNTER_SETUP,
    ANGELIC_FEAR_SETUP.setup_id: ANGELIC_FEAR_SETUP,
    ANGELIC_FEAR_REACTION_SETUP.setup_id: ANGELIC_FEAR_REACTION_SETUP,
    SOOTHE_TEST_SETUP.setup_id: SOOTHE_TEST_SETUP,
    WEAPON_IDENTITY_SETUP.setup_id: WEAPON_IDENTITY_SETUP,
    WEAPON_IDENTITY_SHORTSWORD_SETUP.setup_id: WEAPON_IDENTITY_SHORTSWORD_SETUP,
    BATTLE_MAGIC_WIZARD_MOVEMENT_SPELLS_SETUP.setup_id: BATTLE_MAGIC_WIZARD_MOVEMENT_SPELLS_SETUP,
    BATTLE_MAGIC_WIZARD_HERO_SAVE_SETUP.setup_id: BATTLE_MAGIC_WIZARD_HERO_SAVE_SETUP,
    BATTLE_MAGIC_WIZARD_NEXT_SETUP.setup_id: BATTLE_MAGIC_WIZARD_NEXT_SETUP,
    BATTLE_MAGIC_WIZARD_REACTION_SETUP.setup_id: BATTLE_MAGIC_WIZARD_REACTION_SETUP,
    BATTLE_MAGIC_WIZARD_RUNIC_BODY_SETUP.setup_id: BATTLE_MAGIC_WIZARD_RUNIC_BODY_SETUP,
    BATTLE_MAGIC_WIZARD_TELEKINETIC_PROJECTILE_SETUP.setup_id: BATTLE_MAGIC_WIZARD_TELEKINETIC_PROJECTILE_SETUP,
    STORM_DRUID_NEXT_SETUP.setup_id: STORM_DRUID_NEXT_SETUP,
    STORM_DRUID_SAVE_SETUP.setup_id: STORM_DRUID_SAVE_SETUP,
    STORM_DRUID_WEATHER_SETUP.setup_id: STORM_DRUID_WEATHER_SETUP,
    STORM_DRUID_SOCIAL_SETUP.setup_id: STORM_DRUID_SOCIAL_SETUP,
    LIFE_ORACLE_LASH_SETUP.setup_id: LIFE_ORACLE_LASH_SETUP,
    LIFE_ORACLE_NEXT_SETUP.setup_id: LIFE_ORACLE_NEXT_SETUP,
    BOMBER_ALCHEMIST_NEXT_SETUP.setup_id: BOMBER_ALCHEMIST_NEXT_SETUP,
    FAITHS_FLAMEKEEPER_NEXT_SETUP.setup_id: FAITHS_FLAMEKEEPER_NEXT_SETUP,
    BOMBER_ALCHEMIST_LEVEL_2_CONDITION_BOMBS_SETUP.setup_id: BOMBER_ALCHEMIST_LEVEL_2_CONDITION_BOMBS_SETUP,
    BOMBER_ALCHEMIST_LEVEL_2_CONDITION_BOMBS_NEXT_SETUP.setup_id: BOMBER_ALCHEMIST_LEVEL_2_CONDITION_BOMBS_NEXT_SETUP,
    **{
        setup.setup_id: setup
        for setup in L2_PREPARED_SETUPS
        if setup.setup_id not in _ADMITTED_L2_PREPARED_DEFINITION_IDS
    },
})


def get_definition(definition_id: str) -> CreatureDefinition:
    try:
        return CREATURES[definition_id]
    except KeyError as error:
        try:
            return _STAGED_CREATURES[definition_id]
        except KeyError:
            raise ValueError(f"unknown creature definition {definition_id!r}") from error


def get_setup(setup_id: str) -> EncounterSetup:
    try:
        return SETUPS[setup_id]
    except KeyError as error:
        try:
            return _STAGED_SETUPS[setup_id]
        except KeyError:
            raise ValueError(f"unknown encounter setup {setup_id!r}") from error


# Expansion definitions remain outside the runtime-admitted maps. The terminal
# picker reads those admitted maps; get_definition/get_setup also expose the
# explicitly staged fixtures for direct tests and review probes.
from .expansion_catalog import (  # noqa: E402  (base catalog must exist first)
    EXPANSION_CREATURES,
    EXPANSION_INITIAL_STATES,
    EXPANSION_SETUPS,
    EXPANSION_SKILL_ACTIONS,
    FIRST_FAMILIES_UNDEAD_STARTER,
)
