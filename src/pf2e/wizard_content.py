"""Selected level-1 Battle Magic Wizard build and its focused diagnostics.

This deliberately narrow prepared-casting build has a finite source-checked
spellbook, daily preparation, Spell Substitution, and Arcane Bond procedure.
Focused alternate setups remain available for individual spell boundaries.

Sources checked 2026-09-17:
* https://2e.aonprd.com/Classes.aspx?ID=39
* https://2e.aonprd.com/ArcaneSchools.aspx?ID=22
* https://2e.aonprd.com/Spells.aspx?ID=1896
* https://2e.aonprd.com/Spells.aspx?ID=1536
* https://2e.aonprd.com/Spells.aspx?ID=1457
* https://2e.aonprd.com/Spells.aspx?ID=1671
* https://2e.aonprd.com/Spells.aspx?ID=1565
* https://2e.aonprd.com/Spells.aspx?ID=1461
* https://2e.aonprd.com/Spells.aspx?ID=1546
"""

from dataclasses import replace

from .items import ItemInstance
from .investigator_content import GUARD_DOG_KNOWLEDGE
from .witch_content import COMMAND_TARGET
from .model import (
    AttackDefinition,
    CreatureDefinition,
    CreaturePlacement,
    EncounterSetup,
    HealthMode,
    Position,
    PreparedSpellDefinition,
    SpellbookSpellDefinition,
    SpontaneousSpellDefinition,
)


BATTLE_MAGIC_WIZARD = CreatureDefinition(
    definition_id="wizard_battle_magic_level_1_staged",
    name="Level 1 Battle Magic Wizard",
    hp=16,
    ac=15,
    perception=3,
    land_speed_ft=30,
    attacks=(
        AttackDefinition(
            attack_id="fist", name="Fist", modifier=5, reach_ft=5,
            traits=frozenset({"attack", "melee", "agile", "finesse", "nonlethal", "unarmed"}),
            damage_type="bludgeoning", damage_dice=(4,), damage_modifier=0,
            attack_attribute="dexterity", damage_attribute="strength",
        ),
    ),
    kind="pc",
    health_mode=HealthMode.PC,
    vision="ordinary",
    hero_points=1,
    ability_modifiers=(
        ("strength", 0), ("dexterity", 2), ("constitution", 2),
        ("intelligence", 4), ("wisdom", 0), ("charisma", 1),
    ),
    skills=(
        ("arcana", "trained", 7), ("crafting", "trained", 7),
        ("medicine", "trained", 3), ("society", "trained", 7),
        ("stealth", "trained", 5), ("thievery", "trained", 5),
        ("athletics", "trained", 3), ("acrobatics", "trained", 5),
        ("nature", "trained", 3), ("academia_lore", "trained", 7),
        ("occultism", "trained", 7),
    ),
    saves=(("fortitude", "trained", 5), ("reflex", "trained", 5), ("will", "expert", 5)),
    proficiencies=(
        ("perception", "trained"), ("fortitude", "trained"), ("reflex", "trained"),
        ("will", "expert"), ("simple_weapons", "trained"), ("unarmed_attacks", "trained"),
        ("unarmored_defense", "trained"), ("spell_attack", "trained"),
        ("spell_dc", "trained"), ("class_dc", "trained"),
    ),
    level=1,
    ancestry="Human",
    heritage="Versatile Human",
    background="Scholar",
    class_name="Wizard",
    languages=("Common", "Draconic", "Dwarven", "Elven", "Gnomish", "Goblin"),
    class_dc=17,
    spell_attack=7,
    spell_dc=17,
    spell_attribute="intelligence",
    spell_tradition="arcane",
    prepared_spells=(
        PreparedSpellDefinition("wizard_shield", "battle_magic_curriculum", "shield", cantrip=True),
        PreparedSpellDefinition("wizard_electric_arc", "ordinary_cantrip", "electric_arc", cantrip=True),
        PreparedSpellDefinition("wizard_frostbite", "ordinary_cantrip", "frostbite", cantrip=True),
        PreparedSpellDefinition("wizard_ignition", "ordinary_cantrip", "ignition", cantrip=True),
        PreparedSpellDefinition("wizard_caustic_blast", "ordinary_cantrip", "caustic_blast", cantrip=True),
        PreparedSpellDefinition("wizard_gouging_claw", "ordinary_cantrip", "gouging_claw", cantrip=True),
        PreparedSpellDefinition("wizard_force_barrage", "battle_magic_curriculum", "force_barrage"),
        PreparedSpellDefinition("wizard_breathe_fire", "ordinary_rank_1", "breathe_fire"),
        PreparedSpellDefinition("wizard_enfeeble", "ordinary_rank_1", "enfeeble"),
    ),
    focus_spells=(SpontaneousSpellDefinition("force_bolt", 1),),
    focus_source="battle_magic_focus",
    focus_points=1,
    focus_capacity=1,
    abilities=("battle_magic", "force_bolt", "arcane_bond", "shield_cantrip", "spell_substitution", "assurance_nature"),
    feats=("Fleet", "Natural Skill", "Assurance (Nature)"),
    held_items=("bonded_staff",),
    stowed_items=("spellbook",),
    item_instances=(ItemInstance("bonded_staff", "staff"), ItemInstance("spellbook", "spellbook")),
    spell_substitution_book_id="spellbook",
    spell_substitution_book=(
        # The book records each known spell once; permission rows distinguish
        # ordinary preparation from the two Battle Magic curriculum slots.
        SpellbookSpellDefinition("light", 1, "ordinary_cantrip"),
        SpellbookSpellDefinition("void_warp", 1, "ordinary_cantrip"),
        SpellbookSpellDefinition("telekinetic_projectile", 1, "ordinary_cantrip", ("ordinary_cantrip", "battle_magic_curriculum")),
        SpellbookSpellDefinition("electric_arc", 1, "ordinary_cantrip"),
        SpellbookSpellDefinition("frostbite", 1, "ordinary_cantrip"),
        SpellbookSpellDefinition("ignition", 1, "ordinary_cantrip"),
        SpellbookSpellDefinition("caustic_blast", 1, "ordinary_cantrip"),
        SpellbookSpellDefinition("gouging_claw", 1, "ordinary_cantrip"),
        SpellbookSpellDefinition("tangle_vine", 1, "ordinary_cantrip"),
        SpellbookSpellDefinition("gale_blast", 1, "ordinary_cantrip"),
        SpellbookSpellDefinition("shield", 1, "ordinary_cantrip", ("ordinary_cantrip", "battle_magic_curriculum")),
        SpellbookSpellDefinition("sure_strike", 1, "ordinary_rank_1"),
        SpellbookSpellDefinition("fear", 1, "ordinary_rank_1"),
        SpellbookSpellDefinition("runic_weapon", 1, "ordinary_rank_1"),
        SpellbookSpellDefinition("enfeeble", 1, "ordinary_rank_1"),
        SpellbookSpellDefinition("runic_body", 1, "ordinary_rank_1"),
        SpellbookSpellDefinition("breathe_fire", 1, "ordinary_rank_1", ("ordinary_rank_1", "battle_magic_curriculum")),
        SpellbookSpellDefinition("force_barrage", 1, "ordinary_rank_1", ("ordinary_rank_1", "battle_magic_curriculum")),
    ),
    sheet_notes=(
        "Human boosts Intelligence/Constitution; Scholar boosts Intelligence/Dexterity; Wizard boosts Intelligence; free boosts Intelligence/Dexterity/Constitution/Charisma.",
        "Versatile Human grants Fleet; Natural Skill grants Athletics and Acrobatics; Scholar grants Nature, Academia Lore, and Assurance (Nature).",
        "The finite book has eleven cantrips and seven rank-1 spells. Daily preparation has five ordinary cantrip slots, one Battle Magic curriculum cantrip slot, two ordinary rank-1 slots, and one curriculum rank-1 slot; Force Bolt is separate.",
        "Arcane Bond names the held bonded_staff; once per day it permits one previously prepared-and-cast spell to be recast during the current turn without a slot.",
        "Spell Substitution uses the owned finite book and never restores a spent slot.",
        "Sources: https://2e.aonprd.com/Classes.aspx?ID=39; https://2e.aonprd.com/ArcaneSchools.aspx?ID=22; https://2e.aonprd.com/Spells.aspx?ID=1671; https://2e.aonprd.com/Spells.aspx?ID=1896; https://2e.aonprd.com/Spells.aspx?ID=1536; https://2e.aonprd.com/Spells.aspx?ID=1457; https://2e.aonprd.com/Spells.aspx?ID=1509; https://2e.aonprd.com/Spells.aspx?ID=1718; https://2e.aonprd.com/Spells.aspx?ID=1539; https://2e.aonprd.com/Spells.aspx?ID=1513; https://2e.aonprd.com/Spells.aspx?ID=1657; https://2e.aonprd.com/Spells.aspx?ID=1565; https://2e.aonprd.com/Spells.aspx?ID=1461; https://2e.aonprd.com/Spells.aspx?ID=1546",
    ),
)


# This is the same selected Wizard after a completed, source-constrained
# Spell Substitution replaces the legal ordinary Breathe Fire preparation.
# It keeps the level-1 capacity at its two ordinary rank-1 slots while giving
# the direct Runic Body encounter a durable legal prepared snapshot.
BATTLE_MAGIC_WIZARD_RUNIC_BODY = replace(
    BATTLE_MAGIC_WIZARD,
    definition_id="wizard_battle_magic_level_1_runic_body_prepared",
    name="Level 1 Battle Magic Wizard (Runic Body prepared)",
    prepared_spells=tuple(
        replace(slot, spell_id="runic_body")
        if slot.slot_id == "wizard_breathe_fire" else slot
        for slot in BATTLE_MAGIC_WIZARD.prepared_spells
    ),
)


# A legal alternate daily curriculum choice exchanges Shield for Telekinetic
# Projectile.  It preserves the five ordinary cantrips while keeping the
# selected build at exactly one curriculum cantrip.
BATTLE_MAGIC_WIZARD_TELEKINETIC_PROJECTILE = replace(
    BATTLE_MAGIC_WIZARD,
    definition_id="wizard_battle_magic_level_1_telekinetic_projectile_prepared",
    name="Level 1 Battle Magic Wizard (Telekinetic Projectile prepared)",
    prepared_spells=tuple(
        replace(slot, slot_id="wizard_telekinetic_projectile", spell_id="telekinetic_projectile")
        if slot.slot_id == "wizard_shield" else slot
        for slot in BATTLE_MAGIC_WIZARD.prepared_spells
    ),
)


# This legal alternate keeps the same one-curriculum plus five-ordinary
# cantrip capacity while exercising the selected movement-control pair.
BATTLE_MAGIC_WIZARD_MOVEMENT_SPELLS = replace(
    BATTLE_MAGIC_WIZARD,
    definition_id="wizard_battle_magic_level_1_movement_spells_prepared",
    name="Level 1 Battle Magic Wizard (movement spells prepared)",
    prepared_spells=tuple(
        replace(slot, slot_id="wizard_tangle_vine", spell_id="tangle_vine")
        if slot.slot_id == "wizard_caustic_blast" else
        replace(slot, slot_id="wizard_gale_blast", spell_id="gale_blast")
        if slot.slot_id == "wizard_gouging_claw" else slot
        for slot in BATTLE_MAGIC_WIZARD.prepared_spells
    ),
)


# Daze is recorded as one source-legal spell learned after the selected
# Wizard's starting book was fixed.  It preserves the original starting book
# and all daily slot counts while making the additional W1 option literal.
BATTLE_MAGIC_WIZARD_DAZE = replace(
    BATTLE_MAGIC_WIZARD,
    definition_id="wizard_battle_magic_level_1_daze_prepared",
    name="Level 1 Battle Magic Wizard (Daze prepared)",
    prepared_spells=tuple(
        replace(slot, slot_id="wizard_daze", spell_id="daze")
        if slot.slot_id == "wizard_caustic_blast" else slot
        for slot in BATTLE_MAGIC_WIZARD.prepared_spells
    ),
    spell_substitution_book=(
        *BATTLE_MAGIC_WIZARD.spell_substitution_book,
        SpellbookSpellDefinition("daze", 1, "ordinary_cantrip"),
    ),
    sheet_notes=(
        *BATTLE_MAGIC_WIZARD.sheet_notes,
        "Daze is one additional arcane cantrip legally learned after the fixed starting spellbook; it replaces Caustic Blast in this ordinary daily cantrip slot. The starting-book grant and all existing prepared-slot counts remain unchanged.",
        "Daze is a two-action, 60-foot, basic Will-save 1d6 mental cantrip; a critical failure also causes stunned 1. Source: https://2e.aonprd.com/Spells.aspx?ID=1482.",
    ),
)


# This daily alternate is a bounded hostile/control package.  Void Warp,
# Fear, and Enfeeble were already in the fixed selected book; Command is one
# source-legal arcane spell learned afterward, like the prior Daze option.
# It leaves both the original starting-book grant and every daily slot count
# intact, while choosing distinct Fortitude and Will suppression outcomes.
BATTLE_MAGIC_WIZARD_SUPPRESSION_SPELLS = replace(
    BATTLE_MAGIC_WIZARD,
    definition_id="wizard_battle_magic_level_1_suppression_spells_prepared",
    name="Level 1 Battle Magic Wizard (suppression spells prepared)",
    prepared_spells=tuple(
        replace(slot, slot_id="wizard_void_warp", spell_id="void_warp")
        if slot.slot_id == "wizard_caustic_blast" else
        replace(slot, slot_id="wizard_fear", spell_id="fear")
        if slot.slot_id == "wizard_breathe_fire" else
        replace(slot, slot_id="wizard_command", spell_id="command")
        if slot.slot_id == "wizard_enfeeble" else slot
        for slot in BATTLE_MAGIC_WIZARD.prepared_spells
    ),
    spell_substitution_book=(
        *BATTLE_MAGIC_WIZARD.spell_substitution_book,
        SpellbookSpellDefinition("command", 1, "ordinary_rank_1"),
    ),
    sheet_notes=(
        *BATTLE_MAGIC_WIZARD.sheet_notes,
        "This daily hostile/control alternate prepares Void Warp, Fear, and Command in existing ordinary slots. Command is one additional arcane rank-1 spell legally learned after the fixed starting spellbook; it does not change starting-book or slot counts.",
        "Sources: Void Warp https://2e.aonprd.com/Spells.aspx?ID=1745; Fear https://2e.aonprd.com/Spells.aspx?ID=1524; Enfeeble https://2e.aonprd.com/Spells.aspx?ID=1513; Command https://2e.aonprd.com/Spells.aspx?ID=1470.",
    ),
)


BATTLE_MAGIC_WIZARD_SETUP = EncounterSetup(
    setup_id="staged_battle_magic_wizard_vs_two_guard_dogs",
    name="Battle Magic Wizard vs. Two Guard Dogs",
    width=7,
    height=5,
    placements=(
        CreaturePlacement("wizard", BATTLE_MAGIC_WIZARD.definition_id, "Battle Magic Wizard", "blue", Position(1, 2)),
        CreaturePlacement("dog_a", "guard_dog_mc2924", "Guard Dog A", "red", Position(3, 1)),
        CreaturePlacement("dog_b", "guard_dog_mc2924", "Guard Dog B", "red", Position(3, 2)),
    ),
    knowledge=(GUARD_DOG_KNOWLEDGE,),
)


# A finite ally-in-cone fixture exposes the target-owned Hero/save pause of
# Breathe Fire without changing the selected one-Wizard public combat setup.
BATTLE_MAGIC_WIZARD_HERO_SAVE_SETUP = EncounterSetup(
    setup_id="staged_battle_magic_wizard_breathe_hero_save",
    name="Staged Battle Magic Wizard Breathe Fire Hero Save",
    width=7,
    height=5,
    placements=BATTLE_MAGIC_WIZARD_SETUP.placements + (
        CreaturePlacement("wizard_ally", BATTLE_MAGIC_WIZARD.definition_id, "Wizard Ally", "blue", Position(3, 3)),
    ),
)


BATTLE_MAGIC_WIZARD_RUNIC_BODY_SETUP = EncounterSetup(
    setup_id="staged_battle_magic_wizard_runic_body_prepared",
    name="Staged Battle Magic Wizard with Runic Body prepared",
    width=7,
    height=5,
    placements=(
        CreaturePlacement(
            "wizard", BATTLE_MAGIC_WIZARD_RUNIC_BODY.definition_id,
            "Battle Magic Wizard", "blue", Position(1, 2),
        ),
        CreaturePlacement("dog_a", "guard_dog_mc2924", "Guard Dog A", "red", Position(3, 1)),
        CreaturePlacement("dog_b", "guard_dog_mc2924", "Guard Dog B", "red", Position(3, 2)),
    ),
)


BATTLE_MAGIC_WIZARD_TELEKINETIC_PROJECTILE_SETUP = EncounterSetup(
    setup_id="staged_battle_magic_wizard_telekinetic_projectile_prepared",
    name="Staged Battle Magic Wizard with Telekinetic Projectile prepared",
    width=7,
    height=5,
    placements=(
        CreaturePlacement(
            "wizard", BATTLE_MAGIC_WIZARD_TELEKINETIC_PROJECTILE.definition_id,
            "Battle Magic Wizard", "blue", Position(1, 2),
        ),
        CreaturePlacement("dog_a", "guard_dog_mc2924", "Guard Dog A", "red", Position(3, 1)),
        CreaturePlacement("dog_b", "guard_dog_mc2924", "Guard Dog B", "red", Position(3, 2)),
    ),
)


BATTLE_MAGIC_WIZARD_MOVEMENT_SPELLS_SETUP = EncounterSetup(
    setup_id="staged_battle_magic_wizard_movement_spells_prepared",
    name="Staged Battle Magic Wizard with movement spells prepared",
    width=7,
    height=5,
    placements=(
        CreaturePlacement("wizard", BATTLE_MAGIC_WIZARD_MOVEMENT_SPELLS.definition_id, "Battle Magic Wizard", "blue", Position(1, 2)),
        CreaturePlacement("dog_a", "guard_dog_mc2924", "Guard Dog A", "red", Position(3, 1)),
        CreaturePlacement("dog_b", "guard_dog_mc2924", "Guard Dog B", "red", Position(3, 2)),
    ),
)

BATTLE_MAGIC_WIZARD_DAZE_SETUP = EncounterSetup(
    setup_id="battle_magic_wizard_daze_vs_guard_dog",
    name="Battle Magic Wizard Daze versus Guard Dog",
    width=15,
    height=5,
    placements=(
        CreaturePlacement("wizard", BATTLE_MAGIC_WIZARD_DAZE.definition_id, "Battle Magic Wizard", "blue", Position(1, 2)),
        CreaturePlacement("dog", "guard_dog_mc2924", "Guard Dog", "red", Position(5, 2)),
    ),
)


BATTLE_MAGIC_WIZARD_SUPPRESSION_SPELLS_SETUP = EncounterSetup(
    setup_id="battle_magic_wizard_suppression_spells_vs_guard_dog",
    name="Battle Magic Wizard suppression spells versus Common Speaker",
    width=15,
    height=5,
    placements=(
        CreaturePlacement("wizard", BATTLE_MAGIC_WIZARD_SUPPRESSION_SPELLS.definition_id, "Battle Magic Wizard", "blue", Position(1, 2)),
        CreaturePlacement("enemy", COMMAND_TARGET.definition_id, "Common Speaker", "red", Position(5, 2)),
    ),
)


BATTLE_MAGIC_WIZARD_NEXT_SETUP = EncounterSetup(
    setup_id="staged_battle_magic_wizard_next_guard_dog",
    name="Staged Battle Magic Wizard Next Guard Dog",
    width=7,
    height=5,
    placements=(
        CreaturePlacement("wizard", BATTLE_MAGIC_WIZARD.definition_id, "Battle Magic Wizard", "blue", Position(1, 2)),
        CreaturePlacement("next_guard_dog", "guard_dog_mc2924", "Next Guard Dog", "red", Position(3, 2)),
    ),
)


BATTLE_MAGIC_WIZARD_REACTION_SETUP = EncounterSetup(
    setup_id="staged_battle_magic_wizard_reactive_strike",
    name="Staged Battle Magic Wizard vs. Reactive Strike",
    width=5,
    height=3,
    placements=(
        CreaturePlacement("wizard", BATTLE_MAGIC_WIZARD.definition_id, "Battle Magic Wizard", "blue", Position(1, 1)),
        CreaturePlacement("reactive_fighter", "fighter_m_level_1", "Reactive Fighter", "red", Position(2, 1)),
    ),
)
