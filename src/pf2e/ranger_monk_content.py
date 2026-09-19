"""Reviewed level-1 Ranger edges and Monk build for the S3i roster.

This module supplies definitions and one healthy mixed-class encounter to
the central content owner. It intentionally does not edit or register
``content.py`` itself.
"""

from types import MappingProxyType

from .model import (
    AttackDefinition,
    CreatureDefinition,
    CreaturePlacement,
    EncounterSetup,
    HealthMode,
    Position,
)


_RANGER_ABILITIES = (
    "hunt_prey",
    "hunted_shot",
)
_RANGER_ABILITY_MODIFIERS = (
    ("strength", 1),
    ("dexterity", 4),
    ("constitution", 2),
    ("intelligence", 0),
    ("wisdom", 2),
    ("charisma", 0),
)
_RANGER_SKILLS = (
    ("acrobatics", "trained", 7),
    ("athletics", "trained", 4),
    ("crafting", "trained", 3),
    ("deception", "trained", 3),
    ("forest_lore", "trained", 3),
    ("medicine", "trained", 5),
    ("nature", "trained", 5),
    ("society", "trained", 3),
    ("stealth", "trained", 7),
    ("survival", "trained", 5),
)
_RANGER_SAVES = (
    ("fortitude", "expert", 7),
    ("reflex", "expert", 9),
    ("will", "trained", 5),
)
_RANGER_PROFICIENCIES = (
    ("perception", "expert"),
    ("fortitude", "expert"),
    ("reflex", "expert"),
    ("will", "trained"),
    ("simple_weapons", "trained"),
    ("martial_weapons", "trained"),
    ("unarmed_attacks", "trained"),
    ("unarmored_defense", "trained"),
    ("light_armor", "trained"),
    ("medium_armor", "trained"),
    ("class_dc", "trained"),
)


def _ranger_definition(edge: str) -> CreatureDefinition:
    label = edge.title()
    return CreatureDefinition(
        definition_id=f"ranger_{edge}_level_1",
        name=f"Level 1 Ranger ({label} Edge)",
        hp=20,
        ac=18,
        perception=7,
        land_speed_ft=30,
        attacks=(
            AttackDefinition(
                attack_id="shortbow",
                name="Shortbow",
                modifier=7,
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
                attack_id="fist",
                name="Fist",
                modifier=7,
                reach_ft=5,
                traits=frozenset({"attack", "melee", "agile", "finesse", "nonlethal", "unarmed"}),
                damage_type="bludgeoning",
                damage_dice=(4,),
                damage_modifier=1,
                attack_attribute="dexterity",
                damage_attribute="strength",
                hands_required=0,
            ),
        ),
        kind="pc",
        health_mode=HealthMode.PC,
        abilities=(*_RANGER_ABILITIES, f"hunter_edge_{edge}"),
        feats=("Natural Skill", "Forager", "Fleet", f"Hunter's Edge ({label})", "Hunted Shot"),
        ability_modifiers=_RANGER_ABILITY_MODIFIERS,
        skills=_RANGER_SKILLS,
        saves=_RANGER_SAVES,
        proficiencies=_RANGER_PROFICIENCIES,
        sheet_notes=(
            "Level-1 Versatile Human Ranger; the heritage selects the general feat Fleet, increasing land Speed from 25 to 30 feet. Key attribute Dexterity +4; ancestry/background/free boosts recorded in the selected ability modifiers.",
            "Class skills: Nature and Survival, plus Acrobatics, Athletics, Medicine, and Stealth. Scout's duplicate Survival training grants Deception as the replacement skill, and adds Forest Lore and Forager; Natural Skill trains Crafting and Society.",
            "Hunt Prey is a one-action concentrate action with no numeric range limit. Select one printed Hunter's Edge; this build uses the displayed edge.",
            "Hunted Shot is the selected level-1 class feat. Both subordinate Strikes use this held reload-0 shortbow and target current hunted prey; each consumes an arrow.",
            "Shortbow: 1d6 piercing, range increment 60 feet, maximum 360 feet, deadly d10; no Strength damage. Fist: +7 using Dexterity through finesse, 1d4+1 bludgeoning using Strength for damage.",
            "Human ancestry HP 8 + Ranger class HP 10 + Constitution 2 = 20 HP. Leather armor, trained light armor, Dexterity +4 gives AC 18.",
            "Sources: https://2e.aonprd.com/Classes.aspx?ID=36; https://2e.aonprd.com/Heritages.aspx?ID=262; https://2e.aonprd.com/Feats.aspx?ID=5150; https://2e.aonprd.com/Traits.aspx?ID=602; https://2e.aonprd.com/Actions.aspx?ID=2257; https://2e.aonprd.com/HuntersEdge.aspx?ID=4; https://2e.aonprd.com/HuntersEdge.aspx?ID=5; https://2e.aonprd.com/HuntersEdge.aspx?ID=6; https://2e.aonprd.com/Feats.aspx?ID=4861; https://2e.aonprd.com/Feats.aspx?ID=4479; https://2e.aonprd.com/Weapons.aspx?ID=437",
            "Forager remains a granted exploration skill feat recorded on this sheet; it does not gate the combat-only Ranger acceptance.",
        ),
        held_items=("shortbow",),
        worn_items=("leather_armor",),
        hero_points=1,
        size="medium",
        level=1,
        ancestry="Human",
        heritage="Versatile Human",
        background="Scout",
        class_name="Ranger",
        languages=("Common",),
        class_dc=17,
        ammunition=(("arrow", 20),),
    )


RANGER_FLURRY = _ranger_definition("flurry")
RANGER_OUTWIT = _ranger_definition("outwit")
RANGER_PRECISION = _ranger_definition("precision")
RANGER_DEFINITIONS = MappingProxyType(
    {
        item.definition_id: item
        for item in (RANGER_FLURRY, RANGER_OUTWIT, RANGER_PRECISION)
    }
)


MONK = CreatureDefinition(
    definition_id="monk_monastic_weaponry_level_1",
    name="Level 1 Monk (Monastic Weaponry)",
    hp=20,
    ac=19,
    perception=4,
    # Versatile Human grants a qualifying general feat at character creation.
    # This selected sheet takes Fleet, so its ordinary 25-foot Human Speed is
    # increased by 5 feet.
    land_speed_ft=30,
    attacks=(
        AttackDefinition(
            attack_id="fist",
            name="Fist",
            modifier=7,
            reach_ft=5,
            traits=frozenset({"attack", "melee", "agile", "finesse", "nonlethal", "unarmed"}),
            damage_type="bludgeoning",
            damage_dice=(6,),
            damage_modifier=2,
            attack_attribute="dexterity",
            damage_attribute="strength",
            hands_required=0,
        ),
        AttackDefinition(
            attack_id="kama",
            name="Kama",
            modifier=5,
            reach_ft=5,
            traits=frozenset({"attack", "melee", "agile", "trip", "monk", "weapon"}),
            damage_type="slashing",
            damage_dice=(6,),
            damage_modifier=2,
            item_id="kama",
            attack_attribute="strength",
            damage_attribute="strength",
            hands_required=1,
        ),
    ),
    kind="pc",
    health_mode=HealthMode.PC,
    abilities=("flurry_of_blows", "powerful_fist", "monastic_weaponry"),
    feats=("Natural Skill", "Fleet", "Quick Jump", "Flurry of Blows", "Powerful Fist", "Monastic Weaponry"),
    ability_modifiers=(
        ("strength", 2),
        ("dexterity", 4),
        ("constitution", 2),
        ("intelligence", 0),
        ("wisdom", 1),
        ("charisma", 0),
    ),
    skills=(
        ("acrobatics", "trained", 7),
        ("athletics", "trained", 5),
        ("crafting", "trained", 3),
        ("medicine", "trained", 4),
        ("society", "trained", 3),
        ("stealth", "trained", 7),
        ("survival", "trained", 4),
        ("warfare_lore", "trained", 3),
    ),
    saves=(
        ("fortitude", "expert", 7),
        ("reflex", "expert", 9),
        ("will", "expert", 6),
    ),
    proficiencies=(
        ("perception", "trained"),
        ("fortitude", "expert"),
        ("reflex", "expert"),
        ("will", "expert"),
        ("simple_weapons", "trained"),
        ("unarmed_attacks", "trained"),
        ("simple_and_martial_monk_weapons", "trained"),
        ("unarmored_defense", "expert"),
        ("light_armor", "untrained"),
        ("medium_armor", "untrained"),
        ("class_dc", "trained"),
    ),
    sheet_notes=(
        "Level-1 Versatile Human Monk; the heritage selects the general feat Fleet, increasing land Speed from 25 to 30 feet. Martial Disciple background. Key attribute Dexterity +4; Strength +2, Constitution +2, Wisdom +1.",
        "Four class skills: Acrobatics, Medicine, Stealth, and Survival. Martial Disciple trains Athletics and Warfare Lore and grants Quick Jump; Natural Skill trains Crafting and Society.",
        "Monk is expert in unarmored defense and all three saves; no armor is worn. Human ancestry HP 8 + Monk class HP 10 + Constitution 2 = 20 HP.",
        "Powerful Fist changes fist damage to 1d6 and removes the –2 circumstance penalty for a lethal fist Strike.",
        "Monastic Weaponry is the selected level-1 class feat. The held kama is a one-handed martial monk weapon: 1d6 slashing, agile, trip; it may replace an unarmed Strike in Flurry.",
        "Sources: https://2e.aonprd.com/Classes.aspx?ID=60; https://2e.aonprd.com/Heritages.aspx?ID=262; https://2e.aonprd.com/Feats.aspx?ID=5150; https://2e.aonprd.com/Backgrounds.aspx?ID=432; https://2e.aonprd.com/Feats.aspx?ID=5979; https://2e.aonprd.com/Feats.aspx?ID=4479; https://2e.aonprd.com/Weapons.aspx",
        "Quick Jump is the background's granted skill feat; the selected slice supports its one-action horizontal Long Jump result on these flat maps.",
    ),
    held_items=("kama",),
    hero_points=1,
    size="medium",
    level=1,
    ancestry="Human",
    heritage="Versatile Human",
    background="Martial Disciple",
    class_name="Monk",
    languages=("Common",),
    class_dc=17,
)

RANGER_MONK_DEFINITIONS = MappingProxyType({
    **RANGER_DEFINITIONS,
    MONK.definition_id: MONK,
})


RANGER_MONK_SETUP = EncounterSetup(
    setup_id="s3i_ranger_monk_hunter_edges",
    name="Hunter's Edges and Monk Flurry",
    width=7,
    height=5,
    placements=(
        CreaturePlacement("ranger_flurry", RANGER_FLURRY.definition_id, "Flurry Ranger", "blue", Position(1, 0)),
        CreaturePlacement("ranger_outwit", RANGER_OUTWIT.definition_id, "Outwit Ranger", "blue", Position(1, 1)),
        CreaturePlacement("ranger_precision", RANGER_PRECISION.definition_id, "Precision Ranger", "blue", Position(1, 3)),
        CreaturePlacement("monk", MONK.definition_id, "Monk", "blue", Position(1, 4)),
        CreaturePlacement("guard_dog_a", "guard_dog_mc2924", "Guard Dog A", "red", Position(5, 0)),
        CreaturePlacement("guard_dog_b", "guard_dog_mc2924", "Guard Dog B", "red", Position(5, 1)),
        CreaturePlacement("guard_dog_c", "guard_dog_mc2924", "Guard Dog C", "red", Position(5, 3)),
        CreaturePlacement("guard_dog_d", "guard_dog_mc2924", "Guard Dog D", "red", Position(5, 4)),
    ),
)

RANGER_MONK_SETUPS = (RANGER_MONK_SETUP,)


MONK_KAMA_FLURRY_SETUP = EncounterSetup(
    setup_id="staged_monk_kama_flurry",
    name="Staged Monk Kama Flurry",
    width=5,
    height=3,
    placements=(
        CreaturePlacement("monk", MONK.definition_id, "Monk", "blue", Position(1, 1)),
        CreaturePlacement("guard_dog_a", "guard_dog_mc2924", "Guard Dog A", "red", Position(2, 1)),
        CreaturePlacement("guard_dog_b", "guard_dog_mc2924", "Guard Dog B", "red", Position(2, 2)),
    ),
)


RANGER_PRECISION_BOW_SETUP = EncounterSetup(
    setup_id="staged_ranger_precision_bow",
    name="Staged Precision Ranger Bow",
    width=26,
    height=3,
    placements=(
        CreaturePlacement("ranger", RANGER_PRECISION.definition_id, "Precision Ranger", "blue", Position(0, 1)),
        CreaturePlacement("guard_dog_a", "guard_dog_mc2924", "Guard Dog A", "red", Position(24, 1)),
        CreaturePlacement("guard_dog_b", "guard_dog_mc2924", "Guard Dog B", "red", Position(20, 2)),
    ),
)
