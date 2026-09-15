"""Fixed content and encounter setups admitted through S3i."""

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
        PreparedSpellDefinition("cantrip_read_aura", "cantrip", "read_aura", rank=1, cantrip=True),
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
    sheet_notes=(
        "Jaws have no agile, finesse, or nonlethal trait; attacks and damage use Strength.",
        "Pack Attack adds 1d4 when two other allies are within reach of the target.",
        "Senses cannot change targeting on this bright, fully observed map.",
        "Other special actions and optional creature abilities are unsupported.",
    ),
)

FIGHTER_M = MELEE_FIGHTER_M

FIGHTER_FLEET_SHORTSWORD, ELITE_GUARD_DOG = build_s2_definitions(MELEE_FIGHTER_M, GUARD_DOG)
(FIGHTER_RAPIER,) = build_s3_definitions(SHORTBOW_FIGHTER_R)

CREATURES: Mapping[str, CreatureDefinition] = MappingProxyType(
    {
        SYNTHETIC_MELEE.definition_id: SYNTHETIC_MELEE,
        MELEE_FIGHTER_M.definition_id: MELEE_FIGHTER_M,
        SHORTBOW_FIGHTER_R.definition_id: SHORTBOW_FIGHTER_R,
        WARPRIEST_C.definition_id: WARPRIEST_C,
        GUARD_DOG.definition_id: GUARD_DOG,
        FIGHTER_FLEET_SHORTSWORD.definition_id: FIGHTER_FLEET_SHORTSWORD,
        ELITE_GUARD_DOG.definition_id: ELITE_GUARD_DOG,
        FIGHTER_RAPIER.definition_id: FIGHTER_RAPIER,
    }
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

SETUPS: Mapping[str, EncounterSetup] = MappingProxyType(
    {
        S1_SETUP.setup_id: S1_SETUP,
        S2_SETUP.setup_id: S2_SETUP,
        S2_PACK_ATTACK_SETUP.setup_id: S2_PACK_ATTACK_SETUP,
        S2_PC_DUEL_SETUP.setup_id: S2_PC_DUEL_SETUP,
        S3_SETUP.setup_id: S3_SETUP,
        **{setup.setup_id: setup for setup in S2_INTERACTION_SETUPS},
        **{setup.setup_id: setup for setup in S3_INTERACTION_SETUPS},
    }
)


def get_definition(definition_id: str) -> CreatureDefinition:
    try:
        return CREATURES[definition_id]
    except KeyError as error:
        raise ValueError(f"unknown creature definition {definition_id!r}") from error


def get_setup(setup_id: str) -> EncounterSetup:
    try:
        return SETUPS[setup_id]
    except KeyError as error:
        raise ValueError(f"unknown encounter setup {setup_id!r}") from error
