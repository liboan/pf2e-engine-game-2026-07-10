"""Selected level-1 Maestro Bard sheet and Courageous Anthem play fixture.

Sources checked 2026-09-16:

* https://2e.aonprd.com/Classes.aspx?ID=32
* https://2e.aonprd.com/Spells.aspx?ID=1763
* https://2e.aonprd.com/Spells.aspx?ID=1769
* https://2e.aonprd.com/Traits.aspx?ID=559
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


MAESTRO_BARD_STAGED = CreatureDefinition(
    definition_id="bard_maestro_level_1_staged",
    name="Level 1 Maestro Bard (Courageous Anthem sheet)",
    hp=18,
    ac=15,
    perception=5,
    land_speed_ft=30,
    attacks=(
        AttackDefinition(
            attack_id="rapier",
            name="Rapier",
            modifier=5,
            reach_ft=5,
            traits=frozenset({"attack", "deadly-d8", "disarm", "finesse", "melee"}),
            damage_type="piercing",
            damage_dice=(6,),
            damage_modifier=1,
            attack_attribute="dexterity",
            damage_attribute="strength",
            item_id="rapier",
        ),
    ),
    kind="pc",
    health_mode=HealthMode.PC,
    ability_modifiers=(
        ("strength", 1), ("dexterity", 2), ("constitution", 2),
        ("intelligence", 0), ("wisdom", 0), ("charisma", 4),
    ),
    skills=(
        ("acrobatics", "trained", 5), ("athletics", "trained", 4),
        ("deception", "trained", 7), ("diplomacy", "trained", 7),
        ("farming_lore", "trained", 3), ("intimidation", "trained", 7),
        ("medicine", "trained", 3), ("occultism", "trained", 3),
        ("performance", "trained", 7), ("society", "trained", 3),
    ),
    saves=(
        ("fortitude", "trained", 5), ("reflex", "trained", 5),
        ("will", "expert", 5),
    ),
    proficiencies=(
        ("perception", "expert"), ("fortitude", "trained"),
        ("reflex", "trained"), ("will", "expert"),
        ("simple_weapons", "trained"), ("martial_weapons", "trained"),
        ("light_armor", "trained"), ("unarmored_defense", "trained"),
        ("spell_attack", "trained"), ("spell_dc", "trained"),
        ("class_dc", "trained"),
    ),
    feats=("Fleet", "Natural Skill", "Assurance (Athletics)"),
    vision="ordinary",
    held_items=("rapier",),
    hero_points=1,
    level=1,
    ancestry="Human",
    heritage="Versatile Human",
    background="Farmhand",
    class_name="Bard",
    languages=("Common",),
    class_dc=17,
    spell_attack=7,
    spell_dc=17,
    spell_attribute="charisma",
    spell_tradition="occult",
    spontaneous_source="bard_repertoire",
    spontaneous_spells=(
        SpontaneousSpellDefinition("light", 1, cantrip=True),
        SpontaneousSpellDefinition("guidance", 1, cantrip=True),
        SpontaneousSpellDefinition("void_warp", 1, cantrip=True),
        SpontaneousSpellDefinition("forbidding_ward", 1, cantrip=True),
        SpontaneousSpellDefinition("shield", 1, cantrip=True),
        SpontaneousSpellDefinition("courageous_anthem", 1, cantrip=True),
        SpontaneousSpellDefinition("fear", 1),
        SpontaneousSpellDefinition("runic_weapon", 1),
        SpontaneousSpellDefinition("soothe", 1),
    ),
    spontaneous_slots=(
        SpontaneousSlotDefinition("bard_rank1", "rank1", rank=1, capacity=2),
    ),
    focus_spells=(
        SpontaneousSpellDefinition("counter_performance", 1),
        SpontaneousSpellDefinition("lingering_composition", 1),
    ),
    # Counter Performance's trigger/substitution behavior remains deferred,
    # but it is a granted focus spell and therefore contributes to this
    # Maestro's reviewed two-point Focus Pool.
    focus_points=2,
    focus_capacity=2,
    abilities=(
        "courageous_anthem", "counter_performance", "lingering_composition", "shield_cantrip",
    ),
    sheet_notes=(
        "Human Versatile Human Farmhand Maestro Bard: Str +1, Dex +2, Con +2, Int +0, Wis +0, Cha +4; 18 HP, Perception +5, Will +5, Speed 30, ordinary vision, Hero Point 1, and a held rapier.",
        "Farmhand grants Athletics, Farming Lore, and Assurance (Athletics); Natural Skill grants Society and Medicine. The Bard's four additional trained skills are Acrobatics, Deception, Diplomacy, and Intimidation.",
        "Five ordinary occult cantrips and three rank-1 repertoire spells are legal here: Light, Guidance, Void Warp, Forbidding Ward, and Shield; Fear and Runic Weapon are the two Bard choices, while Maestro grants Soothe; the two rank-1 slots are shared. Courageous Anthem and the Maestro's Lingering Composition are executable; Counter Performance remains granted but unimplemented.",
        "Courageous Anthem is a one-action 60-foot emanation for 1 round. Its printed entry has no auditory or visual trait or recipient gate, so this literal slice does not infer hearing from sight or lighting.",
        "Sources: https://2e.aonprd.com/Classes.aspx?ID=32; https://2e.aonprd.com/Spells.aspx?ID=1763; https://2e.aonprd.com/Spells.aspx?ID=1769; https://2e.aonprd.com/Traits.aspx?ID=559",
    ),
)


MAESTRO_BARD_ANTHEM_SETUP = EncounterSetup(
    setup_id="staged_maestro_bard_courageous_anthem_vs_guard_dog",
    name="Staged Maestro Bard Courageous Anthem vs. Guard Dog",
    width=15,
    height=3,
    placements=(
        CreaturePlacement("maestro_bard", MAESTRO_BARD_STAGED.definition_id, "Maestro Bard", "blue", Position(1, 1)),
        CreaturePlacement("bard_ally", "fighter_m_level_1", "Bard's Ally", "blue", Position(2, 1)),
        CreaturePlacement("bard_dog", "guard_dog_mc2924", "Guard Dog", "red", Position(3, 1)),
    ),
)


MAESTRO_BARD_FEAR_SETUP = EncounterSetup(
    setup_id="staged_maestro_bard_courageous_anthem_fear",
    name="Staged Maestro Bard Courageous Anthem against Fear",
    width=7,
    height=3,
    placements=(
        CreaturePlacement("maestro_bard", MAESTRO_BARD_STAGED.definition_id, "Maestro Bard", "blue", Position(1, 1)),
        CreaturePlacement("angelic_opponent", "sorcerer_angelic_level_1_staged", "Angelic Opponent", "red", Position(2, 1)),
    ),
)
