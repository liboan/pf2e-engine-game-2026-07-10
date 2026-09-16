"""Selected Angelic Sorcerer level-1 sheet and first-cast fixture.

This is deliberately a small, source-backed ledger.  The repertoire and rank
pool are executable for the first Divine Lance, Heal, Fear and Runic Weapon
checkpoints, and the focus-sourced Angelic Halo path is executable for its
bounded aura checkpoint; Light point creation and willing attachment are now
executable. The admitted first-cast setup uses this selected sheet; the
additional closed-room diagnostics below remain staged.

Sources checked 2026-09-15:

* https://2e.aonprd.com/Classes.aspx?ID=62
* https://2e.aonprd.com/Bloodlines.aspx?ID=20
* https://2e.aonprd.com/Spells.aspx?ID=1554
* https://2e.aonprd.com/Spells.aspx?ID=1524
* https://2e.aonprd.com/Conditions.aspx?ID=74
* https://2e.aonprd.com/Actions.aspx?ID=2256
* https://2e.aonprd.com/Spells.aspx?ID=2093
* https://2e.aonprd.com/Bloodlines.aspx
"""

from .model import (
    AttackDefinition,
    CreatureDefinition,
    CreaturePlacement,
    EncounterSetup,
    HealthMode,
    Position,
    SpontaneousSlotDefinition,
    SpontaneousSpellDefinition,
)

ANGELIC_SORCERER_STAGED = CreatureDefinition(
    definition_id="sorcerer_angelic_level_1_staged",
    # Keep the historical definition ID for save compatibility with the
    # earlier staged fixture while admitting this exact selected sheet.
    name="Level 1 Angelic Sorcerer (admitted first-cast sheet)",
    hp=16,
    ac=15,
    perception=3,
    land_speed_ft=25,
    attacks=(
        AttackDefinition(
            attack_id="fist",
            name="Fist",
            modifier=5,
            reach_ft=5,
            traits=frozenset({"attack", "melee", "agile", "finesse", "nonlethal", "unarmed"}),
            damage_type="bludgeoning",
            damage_dice=(4,),
            damage_modifier=1,
            attack_attribute="dexterity",
            damage_attribute="strength",
        ),
    ),
    kind="pc",
    health_mode=HealthMode.PC,
    ability_modifiers=(
        ("strength", 1),
        ("dexterity", 2),
        ("constitution", 2),
        ("intelligence", 0),
        ("wisdom", 0),
        ("charisma", 4),
    ),
    skills=(
        ("athletics", "trained", 4),
        ("crafting", "trained", 3),
        ("deception", "trained", 7),
        ("diplomacy", "trained", 7),
        ("farming_lore", "trained", 3),
        ("intimidation", "trained", 7),
        ("performance", "trained", 7),
        ("religion", "trained", 3),
        ("survival", "trained", 3),
    ),
    saves=(
        ("fortitude", "trained", 5),
        ("reflex", "trained", 5),
        ("will", "expert", 5),
    ),
    proficiencies=(
        ("perception", "trained"),
        ("fortitude", "trained"),
        ("reflex", "trained"),
        ("will", "expert"),
        ("simple_weapons", "trained"),
        ("unarmed_attacks", "trained"),
        ("unarmored_defense", "trained"),
        ("spell_attack", "trained"),
        ("spell_dc", "trained"),
        ("class_dc", "trained"),
    ),
    feats=("Natural Skill", "Assurance (Athletics)"),
    level=1,
    ancestry="Human",
    heritage="Skilled Human",
    background="Farmhand",
    class_name="Sorcerer",
    languages=("Common",),
    class_dc=17,
    spell_attack=7,
    spell_dc=17,
    spell_attribute="charisma",
    spell_tradition="divine",
    spontaneous_source="angelic_repertoire",
    spontaneous_spells=(
        SpontaneousSpellDefinition("light", 1, cantrip=True),
        SpontaneousSpellDefinition("divine_lance", 1, cantrip=True),
        SpontaneousSpellDefinition("void_warp", 1, cantrip=True),
        SpontaneousSpellDefinition("guidance", 1, cantrip=True),
        SpontaneousSpellDefinition("stabilize", 1, cantrip=True),
        SpontaneousSpellDefinition("heal", 1),
        SpontaneousSpellDefinition("fear", 1),
        SpontaneousSpellDefinition("runic_weapon", 1),
    ),
    spontaneous_slots=(
        SpontaneousSlotDefinition("angelic_rank1", "rank1", rank=1, capacity=3),
    ),
    focus_spells=(SpontaneousSpellDefinition("angelic_halo", 1),),
    focus_source="angelic_focus",
    focus_points=1,
    focus_capacity=1,
    abilities=("sorcerous_potency", "blood_magic", "angelic_halo"),
    sheet_notes=(
        "Legal level-1 Human with Skilled Human, Natural Skill and Farmhand; Assurance (Athletics) is the background skill feat.",
        "Legal attribute boosts: ancestry boosts Dexterity and Charisma; Farmhand boosts Constitution and Charisma; the class boosts Charisma; four free boosts raise Strength, Dexterity, Constitution and Charisma, resulting in Str +1, Dex +2, Con +2, Int +0, Wis +0, Cha +4.",
        "Natural Skill grants Crafting and Survival; Skilled Human grants Performance; Farmhand grants Athletics and Farming Lore; the angelic bloodline grants Diplomacy and Religion; the Sorcerer choices are Deception and Intimidation.",
        "Angelic bloodline gifts Light and Heal; Divine Lance, Void Warp, Guidance and Stabilize fill the four chosen cantrips; Fear and Runic Weapon fill the two chosen rank-1 repertoire entries.",
        "Angelic Halo grants one Focus Point and Blood Magic; its one-action focus cast, 15-foot aura and bounded Blood Magic choice are executable in the admitted first-cast route. Refocus, Light point creation/attachment/Sustain/Dismiss and declared daily preparation have bounded public support; Runic Weapon's rank-1 physical item cast and Fear's Will save path remain available only in their staged closed-room fixtures.",
        "The first executed spontaneous casts are Divine Lance (repeatable cantrip) and rank-1 Heal (one shared pool of three slots). Sorcerous Potency applies only to the initial slot Heal.",
        "Sources: https://2e.aonprd.com/Classes.aspx?ID=62; https://2e.aonprd.com/Bloodlines.aspx?ID=20; https://2e.aonprd.com/Spells.aspx?ID=1554; https://2e.aonprd.com/Bloodlines.aspx",
    ),
)


ANGELIC_FIRST_CAST_SETUP = EncounterSetup(
    setup_id="sorcerer_angelic_first_cast",
    name="Angelic Sorcerer First Cast",
    width=7,
    height=5,
    placements=(
        CreaturePlacement(
            "angelic_sorcerer",
            ANGELIC_SORCERER_STAGED.definition_id,
            "Angelic Sorcerer",
            "blue",
            Position(1, 2),
        ),
        CreaturePlacement(
            "sorcerer_ally",
            "fighter_m_level_1",
            "Sorcerer's Ally",
            "blue",
            Position(2, 2),
        ),
        CreaturePlacement(
            "sorcerer_dog",
            "guard_dog_mc2924",
            "Guard Dog",
            "red",
            Position(5, 2),
        ),
    ),
)


# Fear/Flee's first public fixture is deliberately staged alongside the
# first-cast sheet. The finite rectangle is an authored closed room; no exits,
# doors, or terrain are implied by the map itself.
ANGELIC_FEAR_SETUP = EncounterSetup(
    setup_id="sorcerer_angelic_fear_closed",
    name="Staged Angelic Sorcerer Fear in a Closed Room",
    width=5,
    height=3,
    placements=(
        CreaturePlacement(
            "angelic_sorcerer",
            ANGELIC_SORCERER_STAGED.definition_id,
            "Angelic Sorcerer",
            "blue",
            Position(1, 1),
        ),
        CreaturePlacement(
            "sorcerer_dog",
            "guard_dog_mc2924",
            "Guard Dog",
            "red",
            Position(3, 1),
        ),
    ),
    closed_boundary=True,
)


# This closed review room makes two public timing boundaries observable in one
# healthy-start encounter.  The dog acts before the caster, so a critical Fear
# cast crosses the encounter's round clock before the caster's next start.  A
# hostile Fighter adjacent to the dog supplies the ordinary Reactive Strike
# window when the dog then Flees.
ANGELIC_FEAR_REACTION_SETUP = EncounterSetup(
    setup_id="sorcerer_angelic_fear_reaction_closed",
    name="Staged Angelic Sorcerer Fear and Reactive Strike Review",
    width=7,
    height=3,
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
            "fighter_m_level_1",
            "Sorcerer's Ally",
            "blue",
            Position(3, 2),
        ),
        CreaturePlacement(
            "sorcerer_dog",
            "guard_dog_mc2924",
            "Guard Dog",
            "red",
            Position(3, 1),
        ),
    ),
    closed_boundary=True,
)
