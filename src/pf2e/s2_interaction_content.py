"""Published S2 content variants and focused interaction encounters."""

from dataclasses import replace

from .model import AttackDefinition, CreatureDefinition, CreaturePlacement, EncounterSetup, Position


def build_s2_definitions(
    melee_fighter: CreatureDefinition, guard_dog: CreatureDefinition
) -> tuple[CreatureDefinition, CreatureDefinition]:
    """Return the Fleet/shortsword Fighter and its published elite dog variant.

    Sources: Player Core 64 (General Training), 256 (Fleet), 278 (shortsword);
    Monster Core 6 (elite adjustment), and the existing Guard Dog record.
    """
    shortsword = AttackDefinition(
        attack_id="shortsword",
        name="Shortsword",
        modifier=9,
        reach_ft=5,
        traits=frozenset({"attack", "melee", "agile", "finesse", "versatile-s"}),
        damage_type="piercing",
        damage_dice=(6,),
        damage_modifier=4,
        item_id="shortsword",
        attack_attribute="strength",
        damage_attribute="strength",
        hands_required=1,
        free_hands_required=0,
    )
    fleet_fighter = replace(
        melee_fighter,
        definition_id="fighter_fleet_shortsword_level_1",
        name="Level 1 Fleet Shortsword Fighter",
        land_speed_ft=30,
        attacks=(shortsword, melee_fighter.attacks[0], *melee_fighter.attacks[1:]),
        feats=("General Training", "Fleet", "Assurance (Athletics)", "Vicious Swing"),
        skills=tuple(
            skill for skill in melee_fighter.skills if skill[0] not in {"crafting", "society"}
        ),
        held_items=("shortsword",),
        worn_items=(*melee_fighter.worn_items, "longsword"),
        sheet_notes=(
            *melee_fighter.sheet_notes,
            "Human General Training selects the level-1 general feat Fleet; land Speed is 30 feet.",
            "Fleet replaces Natural Skill, so Crafting and Society are no longer trained.",
            "Shortsword is agile, finesse, and versatile S; this sheet uses Strength for its +9 attack and 1d6+4 damage.",
            "Starting shortsword and existing armor/longsword leave 5 gp 1 sp.",
            "Source: https://2e.aonprd.com/Feats.aspx?ID=4476; https://2e.aonprd.com/Feats.aspx?ID=5150; https://2e.aonprd.com/Weapons.aspx?ID=398",
        ),
    )

    jaws = replace(
        guard_dog.attacks[0],
        modifier=8,
        damage_modifier=3,
    )
    elite_dog = replace(
        guard_dog,
        definition_id="elite_guard_dog_mc2924",
        name="Elite Guard Dog",
        level=1,
        hp=18,
        ac=17,
        perception=8,
        attacks=(jaws,),
        skills=tuple((skill, proficiency, modifier + 2) for skill, proficiency, modifier in guard_dog.skills),
        saves=tuple((save, proficiency, modifier + 2) for save, proficiency, modifier in guard_dog.saves),
        sheet_notes=(
            "Published elite adjustment applied once to Guard Dog MC2924: +2 to Perception, AC, attacks, skills, saves, and damage; +10 HP at starting level -1.",
            "Jaws remains a non-agile, non-finesse Strength-based attack; Pack Attack remains unchanged.",
            "Elite adjustment adds +2 to the Strike damage once; Pack Attack adds its separate 1d4 when two other allies are in reach.",
            "Speed, size, attributes, senses, and abilities are unchanged by the elite adjustment.",
            "Source: https://2e.aonprd.com/Rules.aspx?ID=3262; Guard Dog: https://2e.aonprd.com/Monsters.aspx?ID=2924",
        ),
    )
    return fleet_fighter, elite_dog


FLEET_FIGHTER_ID = "fighter_fleet_shortsword_level_1"
ELITE_GUARD_DOG_ID = "elite_guard_dog_mc2924"
MELEE_FIGHTER_ID = "fighter_m_level_1"
GUARD_DOG_ID = "guard_dog_mc2924"


S2_INTERACTION_SETUPS = (
    EncounterSetup(
        "s2_fleet_diagonal_assault",
        "Fleet Diagonal Assault",
        7,
        5,
        (
            CreaturePlacement("fleet_fighter", FLEET_FIGHTER_ID, "Fleet Fighter", "blue", Position(0, 0)),
            CreaturePlacement("fighter_m", MELEE_FIGHTER_ID, "Fighter M", "blue", Position(0, 4)),
            CreaturePlacement("guard_dog", GUARD_DOG_ID, "Guard Dog", "red", Position(5, 4)),
            CreaturePlacement("elite_dog", ELITE_GUARD_DOG_ID, "Elite Guard Dog", "red", Position(6, 3)),
        ),
    ),
    EncounterSetup(
        "s2_mixed_blade_pressure",
        "Mixed Blade Pressure",
        7,
        5,
        (
            CreaturePlacement("fleet_fighter", FLEET_FIGHTER_ID, "Fleet Fighter", "blue", Position(2, 2)),
            CreaturePlacement("fighter_m", MELEE_FIGHTER_ID, "Fighter M", "blue", Position(1, 4)),
            CreaturePlacement("elite_dog", ELITE_GUARD_DOG_ID, "Elite Guard Dog", "red", Position(3, 2)),
            CreaturePlacement("guard_dog", GUARD_DOG_ID, "Guard Dog", "red", Position(5, 4)),
        ),
    ),
    EncounterSetup(
        "s2_flank_rotation",
        "Flank Rotation",
        7,
        5,
        (
            CreaturePlacement("fleet_fighter", FLEET_FIGHTER_ID, "Fleet Fighter", "blue", Position(2, 2)),
            CreaturePlacement("fighter_m", MELEE_FIGHTER_ID, "Fighter M", "blue", Position(4, 2)),
            CreaturePlacement("elite_dog", ELITE_GUARD_DOG_ID, "Elite Guard Dog", "red", Position(3, 2)),
            CreaturePlacement("guard_dog", GUARD_DOG_ID, "Guard Dog", "red", Position(5, 3)),
        ),
    ),
    EncounterSetup(
        "s2_mixed_pack_screen",
        "Mixed Pack Screen",
        7,
        5,
        (
            CreaturePlacement("fighter_m", MELEE_FIGHTER_ID, "Fighter M", "blue", Position(2, 2)),
            CreaturePlacement("fighter_support", MELEE_FIGHTER_ID, "Fighter Support", "blue", Position(0, 4)),
            CreaturePlacement("elite_dog", ELITE_GUARD_DOG_ID, "Elite Guard Dog", "red", Position(2, 1)),
            CreaturePlacement("guard_dog", GUARD_DOG_ID, "Guard Dog", "red", Position(1, 2)),
            CreaturePlacement("fleet_fighter", FLEET_FIGHTER_ID, "Fleet Fighter", "red", Position(3, 2)),
        ),
    ),
    EncounterSetup(
        "s2_reaction_relay",
        "Reaction Relay",
        7,
        5,
        (
            CreaturePlacement("fleet_fighter", FLEET_FIGHTER_ID, "Fleet Fighter", "blue", Position(2, 1)),
            CreaturePlacement("fighter_m", MELEE_FIGHTER_ID, "Fighter M", "blue", Position(2, 3)),
            CreaturePlacement("fighter_foe", MELEE_FIGHTER_ID, "Fighter Foe", "red", Position(3, 2)),
            CreaturePlacement("guard_dog", GUARD_DOG_ID, "Guard Dog", "red", Position(6, 4)),
        ),
    ),
    EncounterSetup(
        "s2_contested_weapon_swap",
        "Contested Weapon Draw",
        7,
        5,
        (
            CreaturePlacement("fleet_fighter", FLEET_FIGHTER_ID, "Fleet Fighter", "blue", Position(2, 2)),
            CreaturePlacement("fighter_m", MELEE_FIGHTER_ID, "Fighter M", "blue", Position(0, 4)),
            CreaturePlacement("fighter_foe", MELEE_FIGHTER_ID, "Fighter Foe", "red", Position(3, 2)),
            CreaturePlacement("guard_dog", GUARD_DOG_ID, "Guard Dog", "red", Position(5, 4)),
        ),
    ),
    EncounterSetup(
        "s2_nonlethal_passage",
        "Nonlethal Passage",
        7,
        5,
        (
            CreaturePlacement("fleet_fighter", FLEET_FIGHTER_ID, "Fleet Fighter", "blue", Position(1, 2)),
            CreaturePlacement("fighter_m", MELEE_FIGHTER_ID, "Fighter M", "blue", Position(0, 2)),
            CreaturePlacement("guard_dog", GUARD_DOG_ID, "Guard Dog", "red", Position(2, 2)),
            CreaturePlacement("elite_dog", ELITE_GUARD_DOG_ID, "Elite Guard Dog", "red", Position(6, 2)),
        ),
    ),
    EncounterSetup(
        "s2_heroic_last_stand",
        "Heroic Last Stand",
        7,
        5,
        (
            CreaturePlacement("fighter_target", MELEE_FIGHTER_ID, "Fighter Target", "blue", Position(2, 2)),
            CreaturePlacement("fleet_fighter", FLEET_FIGHTER_ID, "Fleet Fighter", "blue", Position(0, 3)),
            CreaturePlacement("elite_dog", ELITE_GUARD_DOG_ID, "Elite Guard Dog", "red", Position(3, 2)),
            CreaturePlacement("guard_dog", GUARD_DOG_ID, "Guard Dog", "red", Position(4, 3)),
        ),
    ),
)
