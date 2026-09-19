"""Level-2 Reach Spell sheets and test-local encounter fixtures.

The normal :mod:`pf2e.content` catalogue imports these definitions and named
setups once the shared persistence, terminal, and range-validation hooks are
available.  Keeping the literals together here makes the selected L2 sheets
and their retained-identity next-scene routes directly auditable.

Sources checked 2026-09-18:

* Bard class: https://2e.aonprd.com/Classes.aspx?ID=32
* Druid class: https://2e.aonprd.com/Classes.aspx?ID=34
* Sorcerer class: https://2e.aonprd.com/Classes.aspx?ID=62
* Reach Spell: https://2e.aonprd.com/Feats.aspx?ID=4577
* Command: https://2e.aonprd.com/Spells.aspx?ID=1470
"""

from __future__ import annotations

from dataclasses import replace

from .bard_content import MAESTRO_BARD_STAGED
from .druid_content import STORM_DRUID
from .model import (
    CreatureDefinition,
    CreaturePlacement,
    EncounterSetup,
    Position,
    PreparedSpellDefinition,
    SpontaneousSlotDefinition,
    SpontaneousSpellDefinition,
)
from .sorcerer_content import ANGELIC_SORCERER_STAGED


def _plus_one_stats(definition: CreatureDefinition) -> dict[str, object]:
    """Return the level-based statistics that advance from L1 to L2."""
    return {
        "ac": definition.ac + 1,
        "perception": definition.perception + 1,
        "attacks": tuple(replace(attack, modifier=attack.modifier + 1) for attack in definition.attacks),
        "skills": tuple((name, rank, modifier + 1) for name, rank, modifier in definition.skills),
        "saves": tuple((name, rank, modifier + 1) for name, rank, modifier in definition.saves),
        "class_dc": definition.class_dc + 1,
        "spell_attack": definition.spell_attack + 1,
        "spell_dc": definition.spell_dc + 1,
        "level": 2,
    }


MAESTRO_BARD_L2 = replace(
    MAESTRO_BARD_STAGED,
    definition_id="bard_maestro_level_2_reach",
    name="Level 2 Maestro Bard (Reach Spell)",
    hp=28,
    **_plus_one_stats(MAESTRO_BARD_STAGED),
    feats=("Fleet", "Natural Skill", "Assurance (Athletics)", "Reach Spell", "Intimidating Glare"),
    spontaneous_spells=(*MAESTRO_BARD_STAGED.spontaneous_spells, SpontaneousSpellDefinition("command", 1)),
    spontaneous_slots=(SpontaneousSlotDefinition("bard_rank1", "rank1", rank=1, capacity=3),),
    abilities=(*MAESTRO_BARD_STAGED.abilities, "reach_spell"),
    sheet_notes=(*MAESTRO_BARD_STAGED.sheet_notes,
        "Level 2 adds the Reach Spell Bard feat and Intimidating Glare skill feat. Command is the fourth finite rank-1 repertoire spell and the rank-1 pool increases to three slots.",
        "Reach Spell increases the next ranged or touch spell's range by 30 feet; it does not alter an emanation. Command remains a two-action, 30-foot Will-save spell with its selected command mode.",
        "Sources: https://2e.aonprd.com/Classes.aspx?ID=32; https://2e.aonprd.com/Feats.aspx?ID=4577; https://2e.aonprd.com/Spells.aspx?ID=1470",
    ),
)


STORM_DRUID_L2 = replace(
    STORM_DRUID,
    definition_id="storm_druid_level_2_reach",
    name="Level 2 Storm Druid (Reach Spell)",
    hp=28,
    **_plus_one_stats(STORM_DRUID),
    prepared_spells=(*STORM_DRUID.prepared_spells,
                     PreparedSpellDefinition("druid_heal_three", "primal_rank_1", "heal")),
    feats=("Fleet", "Natural Skill", "Assurance (Nature)", "Storm Born", "Animal Empathy", "Reach Spell", "Assurance (Athletics)"),
    abilities=(*STORM_DRUID.abilities, "reach_spell"),
    sheet_notes=(*STORM_DRUID.sheet_notes,
        "Level 2 adds Reach Spell and Assurance (Athletics). Its three ordinary rank-1 prepared slots are Heal, Runic Weapon, and Heal; repeated legal choices remain allowed by the existing finite preparation policy.",
        "Reach Spell can extend a one-action touch Heal to 30 feet or a two-action 30-foot Heal to 60 feet, but never changes Heal's three-action emanation.",
        "Sources: https://2e.aonprd.com/Classes.aspx?ID=34; https://2e.aonprd.com/Feats.aspx?ID=4577; https://2e.aonprd.com/Spells.aspx?ID=1554",
    ),
)


ANGELIC_SORCERER_L2 = replace(
    ANGELIC_SORCERER_STAGED,
    definition_id="sorcerer_angelic_level_2_reach",
    name="Level 2 Angelic Sorcerer (Reach Spell)",
    hp=24,
    **_plus_one_stats(ANGELIC_SORCERER_STAGED),
    feats=("Natural Skill", "Assurance (Athletics)", "Reach Spell", "Intimidating Glare"),
    spontaneous_spells=(*ANGELIC_SORCERER_STAGED.spontaneous_spells, SpontaneousSpellDefinition("command", 1)),
    spontaneous_slots=(SpontaneousSlotDefinition("angelic_rank1", "rank1", rank=1, capacity=4),),
    abilities=(*ANGELIC_SORCERER_STAGED.abilities, "reach_spell"),
    sheet_notes=(*ANGELIC_SORCERER_STAGED.sheet_notes,
        "Level 2 adds Reach Spell and Intimidating Glare. Command is the fourth finite rank-1 repertoire spell and the shared rank-1 spontaneous pool has four slots.",
        "Reach Spell increases the next ranged or touch spell's range by 30 feet, without changing Angelic Halo's emanation.",
        "Sources: https://2e.aonprd.com/Classes.aspx?ID=62; https://2e.aonprd.com/Feats.aspx?ID=4577; https://2e.aonprd.com/Spells.aspx?ID=1470",
    ),
)


MAESTRO_BARD_L2_REACH_SETUP = EncounterSetup(
    "maestro_bard_level_2_reach", "Level 2 Maestro Bard Reach Spell",
    15, 5,
    (
        CreaturePlacement("maestro_bard", MAESTRO_BARD_L2.definition_id, "Maestro Bard", "blue", Position(1, 2)),
        CreaturePlacement("bard_target", "guard_dog_mc2924", "Guard Dog", "red", Position(8, 2)),
    ),
)

STORM_DRUID_L2_REACH_SETUP = EncounterSetup(
    "storm_druid_level_2_reach", "Level 2 Storm Druid Reach Spell",
    15, 5,
    (
        CreaturePlacement("druid", STORM_DRUID_L2.definition_id, "Storm Druid", "blue", Position(1, 2)),
        CreaturePlacement("druid_target", "fighter_m_level_1", "Druid Ally", "blue", Position(7, 2)),
        CreaturePlacement("druid_enemy", "guard_dog_mc2924", "Guard Dog", "red", Position(12, 2)),
    ),
)

ANGELIC_SORCERER_L2_REACH_SETUP = EncounterSetup(
    "angelic_sorcerer_level_2_reach", "Level 2 Angelic Sorcerer Reach Spell",
    15, 5,
    (
        CreaturePlacement("angelic_sorcerer", ANGELIC_SORCERER_L2.definition_id, "Angelic Sorcerer", "blue", Position(1, 2)),
        CreaturePlacement("sorcerer_target", "guard_dog_mc2924", "Guard Dog", "red", Position(8, 2)),
    ),
)


# These named routes retain the exact L2 definition and actor identity.  They
# are deliberately compact next-scene fixtures, not alternate character
# builds; recovery and daily preparation remain the engine's normal public
# procedures before a transition.
MAESTRO_BARD_L2_NEXT_SETUP = EncounterSetup(
    "maestro_bard_level_2_reach_next", "Level 2 Maestro Bard Reach Spell Next Scene",
    7, 5,
    (
        CreaturePlacement("maestro_bard", MAESTRO_BARD_L2.definition_id, "Maestro Bard", "blue", Position(1, 2)),
        CreaturePlacement("next_bard_dog", "guard_dog_mc2924", "Next Guard Dog", "red", Position(4, 2)),
    ),
)

STORM_DRUID_L2_NEXT_SETUP = EncounterSetup(
    "storm_druid_level_2_reach_next", "Level 2 Storm Druid Reach Spell Next Scene",
    7, 5,
    (
        CreaturePlacement("druid", STORM_DRUID_L2.definition_id, "Storm Druid", "blue", Position(1, 2)),
        CreaturePlacement("next_druid_dog", "guard_dog_mc2924", "Next Guard Dog", "red", Position(4, 2)),
    ),
)

ANGELIC_SORCERER_L2_NEXT_SETUP = EncounterSetup(
    "angelic_sorcerer_level_2_reach_next", "Level 2 Angelic Sorcerer Reach Spell Next Scene",
    7, 5,
    (
        CreaturePlacement("angelic_sorcerer", ANGELIC_SORCERER_L2.definition_id, "Angelic Sorcerer", "blue", Position(1, 2)),
        CreaturePlacement("next_sorcerer_dog", "guard_dog_mc2924", "Next Guard Dog", "red", Position(4, 2)),
    ),
)


L2_REACH_DEFINITIONS = (MAESTRO_BARD_L2, STORM_DRUID_L2, ANGELIC_SORCERER_L2)
L2_REACH_SETUPS = (
    MAESTRO_BARD_L2_REACH_SETUP,
    STORM_DRUID_L2_REACH_SETUP,
    ANGELIC_SORCERER_L2_REACH_SETUP,
    MAESTRO_BARD_L2_NEXT_SETUP,
    STORM_DRUID_L2_NEXT_SETUP,
    ANGELIC_SORCERER_L2_NEXT_SETUP,
)
