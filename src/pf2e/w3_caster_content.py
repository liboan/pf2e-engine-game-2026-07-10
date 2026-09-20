"""Content W3 caster alternatives for Widen Spell and spontaneous breadth.

Candidate assessment, checked 2026-09-20:

* Widen Spell is a level-1 Druid, Oracle, Sorcerer, Witch, or Wizard
  spellshape feat.
  Its no-duration burst/cone/line boundary is executable for the admitted
  Breathe Fire 15-foot cone, which becomes 20 feet.
* Cantrip Expansion is a level-2 Bard, Cleric, Magus, Oracle, Psychic,
  Sorcerer, Witch, or Wizard feat.  W2 exercised its prepared-caster branch;
  this Angelic Sorcerer alternative exercises its distinct two-cantrip
  repertoire branch.
* Existing Reach Spell has no area modification, and no admitted spell makes
  another Widen shape executable without inventing duration/area metadata.

Sources: https://2e.aonprd.com/Feats.aspx?ID=4715,
https://2e.aonprd.com/Feats.aspx?ID=4580,
https://2e.aonprd.com/Spells.aspx?ID=1457, and the cited class pages.
"""

from __future__ import annotations

from dataclasses import replace

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
from .wizard_content import BATTLE_MAGIC_WIZARD


def _level_two_statistics(definition: CreatureDefinition) -> dict[str, object]:
    """Advance only the literal level-derived values used by these sheets."""
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


# Natural Ambition takes the level-1 Wizard feat in place of Natural Skill.
# Its existing Breathe Fire preparation supplies a real arcane Widen cast.
BATTLE_MAGIC_WIZARD_L1_WIDEN = replace(
    BATTLE_MAGIC_WIZARD,
    definition_id="wizard_battle_magic_level_1_widen_spell",
    name="Level 1 Battle Magic Wizard (Widen Spell)",
    skills=tuple(
        entry for entry in BATTLE_MAGIC_WIZARD.skills
        if entry[0] not in {"athletics", "acrobatics"}
    ),
    abilities=(*BATTLE_MAGIC_WIZARD.abilities, "widen_spell"),
    feats=("Fleet", "Natural Ambition", "Assurance (Nature)", "Widen Spell"),
    sheet_notes=(*(
        note for note in BATTLE_MAGIC_WIZARD.sheet_notes
        if "Natural Skill grants Athletics and Acrobatics" not in note
    ),
        "Natural Ambition selects Widen Spell in place of Natural Skill, so this alternative does not receive Athletics or Acrobatics from that ancestry feat.",
        "Widen Spell is a one-action manipulate spellshape. Its next qualifying no-duration burst, cone, or line spell widens; Breathe Fire's 15-foot cone becomes a 20-foot cone.",
        "Sources: https://2e.aonprd.com/Feats.aspx?ID=4715; https://2e.aonprd.com/Spells.aspx?ID=1457.",
    ),
)


# The same Human ancestry choice grants the Druid's level-1 Widen Spell.  The
# alternative alone expands its finite primal menu with Breathe Fire; ordinary
# Storm Druid sheets keep their accepted Heal/Runic Weapon menu unchanged.
STORM_DRUID_L1_WIDEN = replace(
    STORM_DRUID,
    definition_id="storm_druid_level_1_widen_spell",
    name="Level 1 Storm Druid (Widen Spell)",
    skills=tuple(
        entry for entry in STORM_DRUID.skills
        if entry[0] not in {"athletics", "society"}
    ),
    prepared_spells=tuple(
        PreparedSpellDefinition("druid_breathe_fire_two", "primal_rank_1", "breathe_fire")
        if slot.slot_id == "druid_runic_weapon_two" else slot
        for slot in STORM_DRUID.prepared_spells
    ),
    abilities=(*STORM_DRUID.abilities, "widen_spell", "storm_druid_widen_preparation"),
    feats=("Fleet", "Natural Ambition", "Assurance (Nature)", "Storm Born", "Animal Empathy", "Widen Spell"),
    sheet_notes=(*(
        note for note in STORM_DRUID.sheet_notes
        if "Natural Skill is the level-1 Human ancestry feat" not in note
    ),
        "Natural Ambition selects Widen Spell in place of Natural Skill, so this alternative does not receive Athletics or Society from that ancestry feat.",
        "This Widen-only finite preparation alternative adds Breathe Fire to its primal rank-1 choices and prepares it in place of Runic Weapon. Its five accepted cantrip choices are unchanged.",
        "Widen Spell is a one-action manipulate spellshape. It changes this Breathe Fire's printed 15-foot cone to 20 feet; it does not make a duration spell or an emanation eligible.",
        "Sources: https://2e.aonprd.com/Feats.aspx?ID=4715; https://2e.aonprd.com/Spells.aspx?ID=1457; https://2e.aonprd.com/Classes.aspx?ID=34.",
    ),
)


# Cantrip Expansion adds repertoire choices, not slots, to a spontaneous
# caster. Daze and Forbidding Ward are both admitted divine cantrips with
# existing public resolution paths, so the extra repertoire is playable.
ANGELIC_SORCERER_L2_CANTRIP_EXPANSION = replace(
    ANGELIC_SORCERER_STAGED,
    definition_id="sorcerer_angelic_level_2_cantrip_expansion",
    name="Level 2 Angelic Sorcerer (Cantrip Expansion)",
    hp=24,
    **_level_two_statistics(ANGELIC_SORCERER_STAGED),
    spontaneous_spells=(
        *ANGELIC_SORCERER_STAGED.spontaneous_spells,
        SpontaneousSpellDefinition("daze", 1, cantrip=True),
        SpontaneousSpellDefinition("forbidding_ward", 1, cantrip=True),
    ),
    spontaneous_slots=(SpontaneousSlotDefinition("angelic_rank1", "rank1", rank=1, capacity=4),),
    feats=(*ANGELIC_SORCERER_STAGED.feats, "Cantrip Expansion", "Intimidating Glare"),
    sheet_notes=(*ANGELIC_SORCERER_STAGED.sheet_notes,
        "Level 2 adds Cantrip Expansion and Intimidating Glare. As a spontaneous caster, Cantrip Expansion adds Daze and Forbidding Ward to the divine repertoire; it does not create prepared cantrip slots.",
        "The rank-1 spontaneous pool advances to four slots. Daze is a 60-foot basic Will cantrip; Forbidding Ward remains the admitted two-action ally/enemy sustained cantrip route.",
        "Sources: https://2e.aonprd.com/Feats.aspx?ID=4580; https://2e.aonprd.com/Spells.aspx?ID=1482; https://2e.aonprd.com/Spells.aspx?ID=1535; https://2e.aonprd.com/Classes.aspx?ID=62.",
    ),
)


BATTLE_MAGIC_WIZARD_L1_WIDEN_SETUP = EncounterSetup(
    "wizard_battle_magic_level_1_widen_spell",
    "Level 1 Battle Magic Wizard Widen Spell",
    8, 5,
    (
        CreaturePlacement("wizard", BATTLE_MAGIC_WIZARD_L1_WIDEN.definition_id, "Battle Magic Wizard", "blue", Position(1, 2)),
        CreaturePlacement("wizard_far_target", "guard_dog_mc2924", "Guard Dog", "red", Position(5, 2)),
    ),
)

# This adjacent hostile room keeps the Widen Spell manipulate interruption
# executable in the public setup catalog.
BATTLE_MAGIC_WIZARD_L1_WIDEN_REACTION_SETUP = EncounterSetup(
    "wizard_battle_magic_level_1_widen_spell_reaction",
    "Level 1 Battle Magic Wizard Widen Spell Reactive Strike",
    8, 5,
    (
        CreaturePlacement("wizard", BATTLE_MAGIC_WIZARD_L1_WIDEN.definition_id, "Battle Magic Wizard", "blue", Position(1, 2)),
        CreaturePlacement("reactive_fighter", "fighter_m_level_1", "Reactive Fighter", "red", Position(2, 1)),
        CreaturePlacement("wizard_far_target", "guard_dog_mc2924", "Guard Dog", "red", Position(5, 2)),
    ),
)

STORM_DRUID_L1_WIDEN_SETUP = EncounterSetup(
    "storm_druid_level_1_widen_spell",
    "Level 1 Storm Druid Widen Spell",
    8, 5,
    (
        CreaturePlacement("druid", STORM_DRUID_L1_WIDEN.definition_id, "Storm Druid", "blue", Position(1, 2)),
        CreaturePlacement("druid_far_target", "guard_dog_mc2924", "Guard Dog", "red", Position(5, 2)),
    ),
)

ANGELIC_SORCERER_L2_CANTRIP_EXPANSION_SETUP = EncounterSetup(
    "angelic_sorcerer_level_2_cantrip_expansion",
    "Level 2 Angelic Sorcerer Cantrip Expansion",
    8, 5,
    (
        CreaturePlacement("angelic_sorcerer", ANGELIC_SORCERER_L2_CANTRIP_EXPANSION.definition_id, "Level 2 Angelic Sorcerer", "blue", Position(1, 2)),
        CreaturePlacement("sorcerer_ally", "fighter_m_level_1", "Sorcerer Ally", "blue", Position(2, 2)),
        CreaturePlacement("sorcerer_target", "guard_dog_mc2924", "Guard Dog", "red", Position(5, 2)),
    ),
)


W3_CASTER_DEFINITIONS = (
    BATTLE_MAGIC_WIZARD_L1_WIDEN,
    STORM_DRUID_L1_WIDEN,
    ANGELIC_SORCERER_L2_CANTRIP_EXPANSION,
)
W3_CASTER_SETUPS = (
    BATTLE_MAGIC_WIZARD_L1_WIDEN_SETUP,
    BATTLE_MAGIC_WIZARD_L1_WIDEN_REACTION_SETUP,
    STORM_DRUID_L1_WIDEN_SETUP,
    ANGELIC_SORCERER_L2_CANTRIP_EXPANSION_SETUP,
)
