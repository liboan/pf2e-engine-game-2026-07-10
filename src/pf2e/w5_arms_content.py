"""W5 Arms/parry sheets and finite public setups.

This module owns the selected new names while the common Strike and catalog
integration remain in their existing family owners.
"""

from dataclasses import replace

from .barbarian_content import BARBARIAN_SAMPLE_CHARACTERS, BARBARIAN_TEST_ENEMY
from .l2_horizontal_content import THIEF_ROGUE_LEVEL_2
from .model import AttackDefinition, CreatureDefinition, CreaturePlacement, EncounterSetup, Position
from .swashbuckler_content import BRAGGART_SWASHBUCKLER


RAGING_THROWER = BARBARIAN_SAMPLE_CHARACTERS["raging_thrower"].definition


EXTRAVAGANT_PARRY_SWASHBUCKLER = replace(
    BRAGGART_SWASHBUCKLER,
    definition_id="swashbuckler_braggart_extravagant_parry_level_1",
    name="Level 1 Braggart Swashbuckler (Extravagant Parry)",
    feats=tuple(
        "Extravagant Parry" if feat == "Flying Blade" else feat
        for feat in BRAGGART_SWASHBUCKLER.feats
    ),
    sheet_notes=BRAGGART_SWASHBUCKLER.sheet_notes + (
        "Extravagant Parry replaces Flying Blade: one action grants +1 circumstance AC, or +2 with a free hand/parry weapon, until the next turn starts; a resolved enemy Strike miss grants temporary panache through the end of the next turn.",
        "Thrown dagger attacks remain ordinary weapon Strikes and do not inherit Flying Blade's Precise Strike extension.",
    ),
)


def _strong_arm_attacks() -> tuple[AttackDefinition, ...]:
    dagger = AttackDefinition(
        "dagger", "Dagger", 8, 5,
        frozenset({"attack", "melee", "agile", "finesse", "thrown", "weapon"}),
        "piercing", (4,), 4, item_id="dagger", attack_attribute="dexterity",
        damage_attribute="dexterity", range_increment_ft=10, max_range_ft=60,
    )
    thrown = replace(
        dagger, attack_id="dagger_thrown", name="Dagger (Thrown)", reach_ft=0,
        damage_modifier=0, damage_attribute="strength",
        traits=frozenset({"attack", "ranged", "agile", "finesse", "thrown", "weapon"}),
    )
    return dagger, thrown, THIEF_ROGUE_LEVEL_2.attacks[1]


STRONG_ARM_ROGUE = replace(
    THIEF_ROGUE_LEVEL_2,
    definition_id="rogue_thief_warrior_level_2_strong_arm",
    name="Level 2 Thief Rogue (Warrior, Strong Arm)",
    attacks=_strong_arm_attacks(),
    feats=tuple("Strong Arm" if feat == "Mobility" else feat for feat in THIEF_ROGUE_LEVEL_2.feats),
    held_items=("dagger",),
    carried_item_bulk=(("dagger", 0), ("leather_armor", 1)),
    sheet_notes=THIEF_ROGUE_LEVEL_2.sheet_notes + (
        "Strong Arm replaces Mobility and increases the thrown dagger's range increment from 10 to 20 feet; its maximum range is 120 feet.",
    ),
)


RAGING_THROWER_SETUP = EncounterSetup(
    "w5_raging_thrower_vs_guard",
    "W5 Raging Thrower versus Guard",
    15, 3,
    (
        CreaturePlacement("raging_thrower", RAGING_THROWER.definition_id, "Raging Thrower", "blue", Position(1, 1)),
        CreaturePlacement("raging_thrower_guard", BARBARIAN_TEST_ENEMY.definition_id, "Guard", "red", Position(7, 1)),
    ),
)

EXTRAVAGANT_PARRY_SETUP = EncounterSetup(
    "w5_extravagant_parry_vs_guard",
    "W5 Extravagant Parry versus Guard",
    5, 3,
    (
        CreaturePlacement("parry_swashbuckler", EXTRAVAGANT_PARRY_SWASHBUCKLER.definition_id, "Parry Swashbuckler", "blue", Position(1, 1)),
        CreaturePlacement("parry_guard", BARBARIAN_TEST_ENEMY.definition_id, "Guard", "red", Position(2, 1)),
    ),
)

STRONG_ARM_SETUP = EncounterSetup(
    "w5_strong_arm_vs_guard",
    "W5 Strong Arm versus Guard",
    25, 3,
    (
        CreaturePlacement("strong_arm", STRONG_ARM_ROGUE.definition_id, "Strong Arm Rogue", "blue", Position(1, 1)),
        CreaturePlacement("strong_arm_guard", BARBARIAN_TEST_ENEMY.definition_id, "Guard", "red", Position(13, 1)),
    ),
)


W5_ARMS_DEFINITIONS = {
    EXTRAVAGANT_PARRY_SWASHBUCKLER.definition_id: EXTRAVAGANT_PARRY_SWASHBUCKLER,
    STRONG_ARM_ROGUE.definition_id: STRONG_ARM_ROGUE,
}
W5_ARMS_SETUPS = {
    setup.setup_id: setup
    for setup in (RAGING_THROWER_SETUP, EXTRAVAGANT_PARRY_SETUP, STRONG_ARM_SETUP)
}
