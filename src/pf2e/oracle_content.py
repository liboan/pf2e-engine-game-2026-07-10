"""Selected level-1 Life Oracle and narrowly staged fixtures."""

from dataclasses import replace

from .items import ItemInstance
from .investigator_content import GUARD_DOG_KNOWLEDGE
from .model import AttackDefinition, CreatureDefinition, CreaturePlacement, EncounterSetup, HealthMode, Position, SpontaneousSlotDefinition, SpontaneousSpellDefinition

LIFE_ORACLE = CreatureDefinition(
    definition_id="life_oracle_level_1_staged", name="Level 1 Life Oracle", hp=18, ac=15, perception=5, land_speed_ft=30,
    attacks=(AttackDefinition("staff", "Staff", 3, 5, frozenset({"attack", "melee", "two_hand_d8"}), "bludgeoning", (4,), 0, item_id="staff"),), kind="pc", health_mode=HealthMode.PC, vision="ordinary", hero_points=1,
    ability_modifiers=(("strength", 0), ("dexterity", 1), ("constitution", 2), ("intelligence", 0), ("wisdom", 2), ("charisma", 4)),
    skills=(("acrobatics", "trained", 4), ("athletics", "trained", 3), ("diplomacy", "trained", 7), ("intimidation", "trained", 7), ("medicine", "trained", 5), ("nature", "trained", 5), ("religion", "trained", 5), ("society", "trained", 3), ("academia_lore", "trained", 3)), saves=(("fortitude", "trained", 5), ("reflex", "trained", 4), ("will", "expert", 7)),
    proficiencies=(("perception", "trained"), ("fortitude", "trained"), ("reflex", "trained"), ("will", "expert"), ("simple_weapons", "trained"), ("unarmed_attacks", "trained"), ("light_armor", "trained"), ("unarmored_defense", "trained"), ("spell_attack", "trained"), ("spell_dc", "trained"), ("class_dc", "trained")), level=1, ancestry="Human", heritage="Versatile Human", background="Scholar", class_name="Oracle", languages=("Common", "Elven"), class_dc=17, spell_attack=7, spell_dc=17, spell_attribute="charisma", spell_tradition="divine", spontaneous_source="oracle_repertoire",
    spontaneous_spells=(SpontaneousSpellDefinition("divine_lance", 1, cantrip=True), SpontaneousSpellDefinition("guidance", 1, cantrip=True), SpontaneousSpellDefinition("stabilize", 1, cantrip=True), SpontaneousSpellDefinition("light", 1, cantrip=True), SpontaneousSpellDefinition("void_warp", 1, cantrip=True), SpontaneousSpellDefinition("vitality_lash", 1, cantrip=True), SpontaneousSpellDefinition("heal", 1), SpontaneousSpellDefinition("fear", 1), SpontaneousSpellDefinition("runic_weapon", 1), SpontaneousSpellDefinition("soothe", 1)), spontaneous_slots=(SpontaneousSlotDefinition("oracle_rank1", "rank1", rank=1, capacity=3),), focus_spells=(SpontaneousSpellDefinition("life_link", 1),), focus_points=1, focus_capacity=1,
    abilities=("life_oracle", "nudge_the_scales", "life_link", "assurance_nature"), feats=("Fleet", "Natural Skill", "Assurance (Nature)", "Nudge the Scales"), held_items=("staff",), worn_items=("leather_armor",), item_instances=(ItemInstance("staff", "staff"),), sheet_notes=("Human Versatile Human Scholar Life Oracle: 18 HP, AC 15, Speed 30, and the source-checked finite divine repertoire.", "The plain staff and leather armor fit the selected mundane starting-equipment budget.", "Nudge the Scales and Life Link are bounded executable Life mystery grants; cursebound and daily life/death mode are persisted.", "Anathema and unsupported health/persistent boundaries remain explicitly GM-adjudicated."),
)

# Preserve the historical setup ID for saved games while presenting this as
# the admitted ordinary level-1 Oracle encounter.
LIFE_ORACLE_NUDGE_SETUP = EncounterSetup("staged_life_oracle_nudge", "Life Oracle Nudge", 7, 5, (CreaturePlacement("oracle", LIFE_ORACLE.definition_id, "Life Oracle", "blue", Position(1, 2)), CreaturePlacement("dog", "guard_dog_mc2924", "Guard Dog", "red", Position(4, 2))), knowledge=(GUARD_DOG_KNOWLEDGE,))

VOID_HEALING_ORACLE = replace(LIFE_ORACLE, definition_id="life_oracle_death_mode_target_staged", name="Life Oracle (death mode target)", abilities=(*LIFE_ORACLE.abilities, "void_healing"))
LIFE_ORACLE_LASH_SETUP = EncounterSetup("staged_life_oracle_vitality_lash", "Staged Life Oracle Vitality Lash", 7, 5, (CreaturePlacement("oracle", LIFE_ORACLE.definition_id, "Life Oracle", "blue", Position(1, 2)), CreaturePlacement("death_oracle", VOID_HEALING_ORACLE.definition_id, "Death-mode Oracle", "red", Position(4, 2))))
LIFE_ORACLE_NEXT_SETUP = EncounterSetup("staged_life_oracle_next", "Staged Life Oracle Next Scene", 7, 5, (CreaturePlacement("oracle", LIFE_ORACLE.definition_id, "Life Oracle", "blue", Position(1, 2)), CreaturePlacement("next_dog", "guard_dog_mc2924", "Next Guard Dog", "red", Position(4, 2))))
