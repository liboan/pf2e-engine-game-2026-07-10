"""Selected level-1 Faith's Flamekeeper Witch and its compact fixtures.

Sources: https://2e.aonprd.com/Classes.aspx?ID=38,
https://2e.aonprd.com/Patrons.aspx?ID=12, and
https://2e.aonprd.com/Spells.aspx?ID=1882.
"""

from .items import ItemInstance
from dataclasses import replace
from .investigator_content import GUARD_DOG_KNOWLEDGE
from .model import AttackDefinition, CreatureDefinition, CreaturePlacement, EncounterSetup, HealthMode, Position, PreparedSpellDefinition, SpontaneousSpellDefinition


FAITHS_FLAMEKEEPER_WITCH = CreatureDefinition(
    definition_id="faiths_flamekeeper_witch_level_1",
    name="Level 1 Faith's Flamekeeper Witch", hp=16, ac=15, perception=3, land_speed_ft=30,
    attacks=(AttackDefinition("fist", "Fist", 5, 5, frozenset({"attack", "melee", "agile", "finesse", "nonlethal", "unarmed"}), "bludgeoning", (4,), 0, attack_attribute="dexterity", damage_attribute="strength"),),
    kind="pc", health_mode=HealthMode.PC, vision="ordinary", hero_points=1,
    ability_modifiers=(("strength", 0), ("dexterity", 2), ("constitution", 2), ("intelligence", 4), ("wisdom", 0), ("charisma", 1)),
    skills=(("arcana", "trained", 7), ("crafting", "trained", 7), ("medicine", "trained", 3), ("occultism", "trained", 7), ("society", "trained", 7), ("stealth", "trained", 5), ("thievery", "trained", 5), ("nature", "trained", 3), ("academia_lore", "trained", 3), ("athletics", "trained", 3), ("acrobatics", "trained", 5), ("religion", "trained", 3)),
    saves=(("fortitude", "trained", 5), ("reflex", "trained", 5), ("will", "expert", 5)),
    proficiencies=(("perception", "trained"), ("fortitude", "trained"), ("reflex", "trained"), ("will", "expert"), ("simple_weapons", "trained"), ("unarmed_attacks", "trained"), ("unarmored_defense", "trained"), ("spell_attack", "trained"), ("spell_dc", "trained"), ("class_dc", "trained")),
    level=1, ancestry="Human", heritage="Versatile Human", background="Scholar", class_name="Witch", languages=("Common", "Draconic", "Dwarven", "Elven", "Gnomish", "Goblin"), class_dc=17, spell_attack=7, spell_dc=17, spell_attribute="intelligence", spell_tradition="divine",
    prepared_spells=(
        PreparedSpellDefinition("witch_divine_lance", "witch_cantrip", "divine_lance", cantrip=True),
        PreparedSpellDefinition("witch_shield", "witch_cantrip", "shield", cantrip=True),
        PreparedSpellDefinition("witch_guidance", "witch_cantrip", "guidance", cantrip=True),
        PreparedSpellDefinition("witch_light", "witch_cantrip", "light", cantrip=True),
        PreparedSpellDefinition("witch_forbidding_ward", "witch_cantrip", "forbidding_ward", cantrip=True),
        PreparedSpellDefinition("witch_command", "witch_rank_1", "command"),
        PreparedSpellDefinition("witch_heal", "witch_rank_1", "heal"),
    ),
    spontaneous_source="witch_hexes", spontaneous_spells=(SpontaneousSpellDefinition("stoke_the_heart", 1, cantrip=True),), focus_spells=(SpontaneousSpellDefinition("patrons_puppet", 1),), focus_source="witch_focus", focus_points=1, focus_capacity=1,
    abilities=("faiths_flamekeeper", "witch_preparation", "witch_familiar", "stoke_the_heart", "patrons_puppet", "restored_spirit", "assurance_nature"), feats=("Fleet", "Natural Skill", "Assurance (Nature)"), held_items=("flame_token",), item_instances=(ItemInstance("flame_token", "staff"),),
    sheet_notes=(
        "Human/Versatile Human/Scholar Witch: ancestry boosts Intelligence and Dexterity, background boosts Intelligence and Constitution, class boost Intelligence, and final boosts Intelligence/Dexterity/Constitution/Charisma.",
        "The familiar knows ten divine cantrips (Divine Lance, Void Warp, Shield, Guidance, Stabilize, Light, Vitality Lash, Forbidding Ward, Sigil, Detect Magic) and six rank-1 spells (Heal, Fear, Enfeeble, Runic Weapon, Runic Body, Command).",
        "Daily defaults are Divine Lance, Shield, Guidance, Light, Forbidding Ward; Command and Heal. Patron's Puppet is a one-point focus command and Stoke the Heart is the selected hex cantrip.",
        "Starting equipment is the mundane flame-token staff within the selected 15 gp budget; the unspent remainder is 15 gp because no armor or consumable purchase is admitted to this fixed sheet.",
    ),
)

FLAMEKEEPER_FOX = CreatureDefinition(
    definition_id="faiths_flamekeeper_fox", name="Flamekeeper Fox Familiar", hp=7, ac=15, perception=5, land_speed_ft=40,
    attacks=(), kind="familiar", health_mode=HealthMode.PC, vision="low_light", size="tiny", initiative_exempt=True, familiar_owner_actor_id="witch",
    # Familiars do not use independent ability modifiers. Their named
    # familiar skills use the master's trained value; the remaining exposed
    # checks use master level + key ability in this level-one sheet.
    ability_modifiers=(), skills=(
        ("acrobatics", "trained", 5), ("stealth", "trained", 5),
        ("arcana", None, 1), ("athletics", None, 1), ("crafting", None, 1),
        ("deception", None, 1), ("diplomacy", None, 1), ("intimidation", None, 1),
        ("medicine", None, 1), ("nature", None, 1), ("occultism", None, 1),
        ("performance", None, 1), ("religion", None, 1), ("society", None, 1), ("survival", None, 1),
        ("thievery", None, 1),
    ), saves=(("fortitude", "trained", 5), ("reflex", "trained", 5), ("will", "trained", 5)),
    abilities=("witch_familiar", "manual_dexterity", "tough", "fast_movement", "restored_spirit"), sheet_notes=("Tiny fox familiar: no speech, no Strike, no flanking, and no independent initiative or actions.",),
)

COMMAND_TARGET = CreatureDefinition(
    definition_id="flamekeeper_common_speaker", name="Common-speaking Command Target", hp=14, ac=15, perception=3, land_speed_ft=25,
    attacks=(AttackDefinition("club", "Club", 5, 5, frozenset({"attack", "melee"}), "bludgeoning", (6,), 2),),
    health_mode=HealthMode.ORDINARY, abilities=("common_speaker",), languages=("Common",),
    saves=(("fortitude", "trained", 4), ("reflex", "trained", 4), ("will", "trained", 3)),
)

FLAMEKEEPER_COMMAND_KNOWLEDGE = replace(
    GUARD_DOG_KNOWLEDGE,
    subject_key="common_speaker",
    question="What does this Common-speaking opponent's stance reveal?",
    answer="The opponent understands a direct Common command and has no special resistance in this fixture.",
    subject_definition_id=COMMAND_TARGET.definition_id,
)

FAITHS_FLAMEKEEPER_SETUP = EncounterSetup(
    "faiths_flamekeeper_first_play", "Faith's Flamekeeper Witch and Fox", 7, 5,
    (
        CreaturePlacement("witch", FAITHS_FLAMEKEEPER_WITCH.definition_id, "Flamekeeper Witch", "blue", Position(1, 2)),
        CreaturePlacement("fox", FLAMEKEEPER_FOX.definition_id, "Flamekeeper Fox", "blue", Position(1, 2)),
        CreaturePlacement("ally", FAITHS_FLAMEKEEPER_WITCH.definition_id, "Witch Ally", "blue", Position(2, 2)),
        CreaturePlacement("enemy", COMMAND_TARGET.definition_id, "Command Target", "red", Position(5, 2)),
    ), knowledge=(FLAMEKEEPER_COMMAND_KNOWLEDGE,),
)

FAITHS_FLAMEKEEPER_NEXT_SETUP = EncounterSetup(
    "faiths_flamekeeper_next", "Faith's Flamekeeper Next Scene", 7, 5,
    (
        CreaturePlacement("witch", FAITHS_FLAMEKEEPER_WITCH.definition_id, "Flamekeeper Witch", "blue", Position(1, 2)),
        CreaturePlacement("fox", FLAMEKEEPER_FOX.definition_id, "Flamekeeper Fox", "blue", Position(1, 2)),
        CreaturePlacement("ally", FAITHS_FLAMEKEEPER_WITCH.definition_id, "Witch Ally", "blue", Position(2, 2)),
        CreaturePlacement("next_enemy", COMMAND_TARGET.definition_id, "Next Command Target", "red", Position(5, 2)),
    ),
)
