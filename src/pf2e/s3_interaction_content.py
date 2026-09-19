"""Eight fixed S3 interaction encounters and their small added weapon build.

The existing S1--S3 sheets are retained and adjusted with ``replace`` so the
encounters share the engine's admitted character facts.  Source records:
``docs/implementation/s1-s3-rules.md`` and
``docs/plan/05-interaction-encounters.md`` (reviewed 2026-09-15).
The added rapier uses the Remaster weapon entry:
https://2e.aonprd.com/Weapons.aspx?ID=391
"""

from dataclasses import replace

from .model import CreatureDefinition, CreaturePlacement, EncounterSetup, Position


def build_s3_definitions(shortbow_fighter: CreatureDefinition) -> tuple[CreatureDefinition, ...]:
    """Build the level-1 rapier loadout from the already-reviewed Fighter R."""
    bow = next(attack for attack in shortbow_fighter.attacks if attack.attack_id == "shortbow")
    rapier = replace(
        bow,
        attack_id="rapier",
        name="Rapier",
        modifier=9,
        reach_ft=5,
        traits=frozenset({"attack", "melee", "finesse", "deadly", "deadly-d8", "disarm"}),
        damage_type="piercing",
        damage_dice=(6,),
        damage_modifier=1,
        item_id="rapier",
        attack_attribute="dexterity",
        damage_attribute="strength",
        range_increment_ft=None,
        max_range_ft=None,
        hands_required=1,
        free_hands_required=0,
        ammunition_id=None,
        deadly_die=8,
    )
    fighter = replace(
        shortbow_fighter,
        definition_id="fighter_rapier_level_1",
        name="Level 1 Rapier Fighter R",
        attacks=(rapier, *tuple(attack for attack in shortbow_fighter.attacks if attack.attack_id != "shortbow")),
        held_items=("rapier",),
        ammunition=(),
        sheet_notes=(
            "Other skills are untrained.",
            "Assurance (Athletics) result is 13; it replaces the roll and adds no modifiers.",
            "Rapier is held; carried longsword is available to draw.",
            "Rapier is finesse and deadly d8; its damage still uses Strength.",
            "Disarm is shown as a rapier trait, but the Disarm action is unavailable.",
            "Rapier source: https://2e.aonprd.com/Weapons.aspx?ID=391.",
            "Starting money remaining after leather armor, rapier, and longsword: 10 gp.",
            "Shield Block is retained on the sheet but unavailable: this fixed loadout owns no shield.",
            "No level-1 weapon critical specialization is granted.",
            "Supported action menu is narrower than the full Fighter class.",
        ),
    )
    return (fighter,)


_FLEET_FIGHTER = "fighter_fleet_shortsword_level_1"
_ELITE_DOG = "elite_guard_dog_mc2924"
_RAPIER_FIGHTER = "fighter_rapier_level_1"

S3_INTERACTION_SETUPS: tuple[EncounterSetup, ...] = (
    EncounterSetup(
        "s3_long_lane_crossfire",
        "S3i Long Lane Crossfire",
        15,
        5,
        (
            CreaturePlacement("fighter_m", "fighter_m_level_1", "Fighter M", "blue", Position(6, 0)),
            CreaturePlacement("fighter_r", "fighter_r_level_1", "Fighter R", "blue", Position(0, 2)),
            CreaturePlacement("cleric_c", "warpriest_c_level_1", "Warpriest C", "blue", Position(0, 4)),
            CreaturePlacement("guard_dog_60", "guard_dog_mc2924", "Guard Dog at 60 feet", "red", Position(12, 2)),
            CreaturePlacement("guard_dog_65", "guard_dog_mc2924", "Guard Dog at 65 feet behind dog60", "red", Position(13, 2)),
        ),
    ),
    EncounterSetup(
        "s3_cover_lane_rotation",
        "S3i Cover Lane Rotation",
        7,
        5,
        (
            CreaturePlacement("fighter_m", "fighter_m_level_1", "Fighter M", "blue", Position(4, 2)),
            CreaturePlacement("fighter_r", "fighter_r_level_1", "Fighter R", "blue", Position(1, 2)),
            CreaturePlacement("cleric_c", "warpriest_c_level_1", "Warpriest C", "blue", Position(1, 3)),
            CreaturePlacement("elite_guard_dog", _ELITE_DOG, "Elite Guard Dog", "red", Position(6, 2)),
            CreaturePlacement("guard_dog", "guard_dog_mc2924", "Guard Dog", "red", Position(6, 0)),
        ),
    ),
    EncounterSetup(
        "s3_rescue_under_pressure",
        "S3i Rescue Under Pressure",
        7,
        5,
        (
            CreaturePlacement("fighter_m", "fighter_m_level_1", "Fighter M", "blue", Position(2, 2)),
            CreaturePlacement("fighter_r", "fighter_r_level_1", "Fighter R", "blue", Position(1, 4)),
            CreaturePlacement("cleric_c", "warpriest_c_level_1", "Warpriest C", "blue", Position(1, 1)),
            CreaturePlacement("guard_dog_a", "guard_dog_mc2924", "Guard Dog A", "red", Position(3, 2)),
            CreaturePlacement("guard_dog_b", "guard_dog_mc2924", "Guard Dog B", "red", Position(4, 2)),
        ),
    ),
    EncounterSetup(
        "s3_stabilize_then_touch",
        "S3i Stabilize Then Touch",
        7,
        5,
        (
            CreaturePlacement("fighter_m", "fighter_m_level_1", "Fighter M", "blue", Position(2, 2)),
            CreaturePlacement("fighter_r", "fighter_r_level_1", "Fighter R", "blue", Position(1, 4)),
            CreaturePlacement("cleric_c", "warpriest_c_level_1", "Warpriest C", "blue", Position(1, 1)),
            CreaturePlacement("guard_dog_a", "guard_dog_mc2924", "Guard Dog A", "red", Position(3, 2)),
        ),
    ),
    EncounterSetup(
        "s3_emanation_edge",
        "S3i Emanation Edge",
        15,
        5,
        (
            CreaturePlacement("fighter_m", "fighter_m_level_1", "Fighter M", "blue", Position(1, 1)),
            CreaturePlacement("fighter_r", "fighter_r_level_1", "Fighter R", "blue", Position(1, 2)),
            CreaturePlacement("cleric_c", "warpriest_c_level_1", "Warpriest C", "blue", Position(1, 3)),
            CreaturePlacement("elite_guard_dog", _ELITE_DOG, "Elite Guard Dog", "red", Position(5, 1)),
            CreaturePlacement("guard_dog_35", "guard_dog_mc2924", "Guard Dog at 35 feet", "red", Position(8, 2)),
        ),
    ),
    EncounterSetup(
        "s3_void_against_finesse",
        "S3i Void Against Finesse",
        7,
        5,
        (
            CreaturePlacement("fighter_m", "fighter_m_level_1", "Fighter M", "blue", Position(1, 1)),
            CreaturePlacement("fighter_r", "fighter_r_level_1", "Fighter R", "blue", Position(1, 3)),
            CreaturePlacement("cleric_c", "warpriest_c_level_1", "Warpriest C", "blue", Position(1, 2)),
            CreaturePlacement("rapier_fighter", _RAPIER_FIGHTER, "Rapier Fighter", "red", Position(5, 2)),
            CreaturePlacement("elite_guard_dog", _ELITE_DOG, "Elite Guard Dog", "red", Position(5, 0)),
        ),
    ),
    EncounterSetup(
        "s3_guided_reaction",
        "S3i Guided Reaction",
        7,
        5,
        (
            CreaturePlacement("fleet_fighter", _FLEET_FIGHTER, "Fleet Fighter", "blue", Position(2, 2)),
            CreaturePlacement("fighter_m", "fighter_m_level_1", "Fighter M", "blue", Position(1, 1)),
            CreaturePlacement("cleric_c", "warpriest_c_level_1", "Warpriest C", "blue", Position(1, 4)),
            CreaturePlacement("rapier_fighter", _RAPIER_FIGHTER, "Rapier Fighter", "red", Position(4, 2)),
            CreaturePlacement("guard_dog", "guard_dog_mc2924", "Guard Dog", "red", Position(5, 4)),
        ),
    ),
    EncounterSetup(
        "s3_interrupted_preparation",
        "S3i Interrupted Preparation",
        7,
        5,
        (
            CreaturePlacement("fighter_m", "fighter_m_level_1", "Fighter M", "blue", Position(1, 1)),
            CreaturePlacement("fighter_r", "fighter_r_level_1", "Fighter R", "blue", Position(1, 3)),
            CreaturePlacement("cleric_c", "warpriest_c_level_1", "Warpriest C", "blue", Position(3, 2)),
            CreaturePlacement("rapier_fighter", _RAPIER_FIGHTER, "Rapier Fighter", "red", Position(4, 2)),
            CreaturePlacement("elite_guard_dog", _ELITE_DOG, "Elite Guard Dog", "red", Position(5, 4)),
        ),
    ),
)
