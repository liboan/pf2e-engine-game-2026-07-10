"""Curated level-1 Braggart Swashbuckler content.

This is the first public Swashbuckler slice: Braggart Demoralize, Panache,
ordinary melee Precise Strike, melee Confident Finisher, and Flying Blade
throws through a dagger's first range increment. Tumble Through is supported.

Sources checked 2026-09-16:

* https://2e.aonprd.com/Classes.aspx?ID=63
* https://2e.aonprd.com/Styles.aspx
* https://2e.aonprd.com/Traits.aspx?ID=801
* https://2e.aonprd.com/Actions.aspx?ID=2395
* https://2e.aonprd.com/Actions.aspx?ID=2818
* https://2e.aonprd.com/Traits.aspx?ID=802
* https://2e.aonprd.com/Actions.aspx?ID=2370
* https://2e.aonprd.com/Feats.aspx?ID=6130
* https://2e.aonprd.com/Weapons.aspx?ID=358 (Dagger)
"""

from .items import ItemInstance
from .model import AttackDefinition, CreatureDefinition, CreaturePlacement, EncounterSetup, HealthMode, Position


BRAGGART_SWASHBUCKLER = CreatureDefinition(
    definition_id="swashbuckler_braggart_level_1",
    name="Level 1 Braggart Swashbuckler (Flying Blade)",
    hp=19,
    ac=18,
    perception=5,
    land_speed_ft=25,
    attacks=(
        AttackDefinition(
            attack_id="dagger",
            name="Dagger",
            modifier=7,
            reach_ft=5,
            traits=frozenset({"attack", "melee", "agile", "finesse", "thrown", "weapon"}),
            damage_type="piercing",
            damage_dice=(4,),
            damage_modifier=2,
            item_id="dagger",
            attack_attribute="dexterity",
            damage_attribute="strength",
            range_increment_ft=10,
            max_range_ft=60,
        ),
        AttackDefinition(
            attack_id="dagger_thrown",
            name="Dagger (Thrown)",
            modifier=7,
            reach_ft=0,
            traits=frozenset({"attack", "ranged", "agile", "finesse", "thrown", "weapon"}),
            damage_type="piercing",
            damage_dice=(4,),
            damage_modifier=2,
            item_id="dagger",
            attack_attribute="dexterity",
            damage_attribute="strength",
            range_increment_ft=10,
            max_range_ft=60,
        ),
    ),
    kind="pc",
    health_mode=HealthMode.PC,
    abilities=("swashbuckler", "swashbuckler_braggart", "precise_strike", "stylish_combatant"),
    feats=("Natural Skill", "Assurance (Athletics)", "Intimidating Glare", "Flying Blade"),
    ability_modifiers=(
        ("strength", 2),
        ("dexterity", 4),
        ("constitution", 1),
        ("intelligence", 0),
        ("wisdom", 0),
        ("charisma", 2),
    ),
    skills=(
        ("acrobatics", "trained", 7),
        ("athletics", "trained", 5),
        ("deception", "trained", 5),
        ("diplomacy", "trained", 5),
        ("intimidation", "trained", 5),
        ("nature", "trained", 3),
        ("stealth", "trained", 7),
        ("survival", "trained", 3),
        ("thievery", "trained", 7),
        ("warfare_lore", "trained", 3),
    ),
    saves=(
        ("fortitude", "trained", 4),
        ("reflex", "expert", 9),
        ("will", "expert", 5),
    ),
    proficiencies=(
        ("perception", "expert"),
        ("fortitude", "trained"),
        ("reflex", "expert"),
        ("will", "expert"),
        ("simple_weapons", "trained"),
        ("martial_weapons", "trained"),
        ("unarmed_attacks", "trained"),
        ("unarmored_defense", "trained"),
        ("light_armor", "trained"),
        ("class_dc", "trained"),
    ),
    held_items=("dagger_1",),
    worn_items=("leather_armor",),
    stowed_items=("dagger_2", "dagger_3"),
    item_instances=(
        ItemInstance("dagger_1", "dagger"),
        ItemInstance("dagger_2", "dagger"),
        ItemInstance("dagger_3", "dagger"),
    ),
    hero_points=1,
    size="medium",
    level=1,
    ancestry="Human",
    heritage="Versatile Human",
    background="Warrior",
    class_name="Swashbuckler",
    languages=("Common",),
    class_dc=17,
    armor_category="light",
    carried_item_bulk=(
        ("dagger_1", 0),
        ("dagger_2", 0),
        ("dagger_3", 0),
        ("leather_armor", 1),
    ),
    sheet_notes=(
        "Legal fixed build: Human Versatile Human, Warrior background, Braggart style, and Flying Blade; this definition is staged.",
        "Braggart makes Demoralize a bravado action. Stylish Combatant adds +1 circumstance to the in-combat check.",
        "Panache grants a +5-foot status bonus to Speed; success or critical success is lasting, while ordinary failure lasts through the end of the next turn.",
        "Ordinary Dagger Strikes are agile and finesse melee attacks and add +2 precision from Precise Strike, with or without panache.",
        "Three individually tracked daggers are granted. Flying Blade permits agile or finesse thrown dagger Precise Strike and Confident Finisher only in the first 10-foot range increment; a thrown dagger lands in the target's cell for ordinary recovery.",
        "Starting gear is leather armor and three daggers; the selected sheet preserves the remaining starting money as an authored inventory note.",
        "Selected skills: Acrobatics, Athletics, Deception, Diplomacy, Intimidation, Nature, Stealth, Survival, Thievery, and Warfare Lore.",
        "Sources: https://2e.aonprd.com/Classes.aspx?ID=63; https://2e.aonprd.com/Styles.aspx; https://2e.aonprd.com/Traits.aspx?ID=801; https://2e.aonprd.com/Actions.aspx?ID=2370; https://2e.aonprd.com/Actions.aspx?ID=2395; https://2e.aonprd.com/Actions.aspx?ID=2818; https://2e.aonprd.com/Traits.aspx?ID=802; https://2e.aonprd.com/Feats.aspx?ID=6130; https://2e.aonprd.com/Weapons.aspx?ID=358",
    ),
)


BRAGGART_SWASHBUCKLER_SETUP = EncounterSetup(
    setup_id="staged_braggart_swashbuckler_vs_guard_dog",
    name="Curated Braggart Panache, Precise Strike, and Confident Finisher",
    width=5,
    height=3,
    placements=(
        CreaturePlacement(
            "braggart",
            BRAGGART_SWASHBUCKLER.definition_id,
            "Braggart Swashbuckler",
            "blue",
            Position(1, 1),
        ),
        CreaturePlacement(
            "braggart_dog",
            "guard_dog_mc2924",
            "Guard Dog",
            "red",
            Position(2, 1),
        ),
    ),
)


SWASHBUCKLER_DEFINITIONS = {
    BRAGGART_SWASHBUCKLER.definition_id: BRAGGART_SWASHBUCKLER,
}

SWASHBUCKLER_SETUPS = {
    BRAGGART_SWASHBUCKLER_SETUP.setup_id: BRAGGART_SWASHBUCKLER_SETUP,
}
