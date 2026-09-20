"""Level-2 prepared-caster sheets for the first feat-breadth wave.

The two selected representatives take Cantrip Expansion at level 2.  The
separate level-1 Reach Spell variants use the already-admitted spellshape
procedure; this module contains only their literal class-local sheet and
fixture facts so the shared catalogue owner can admit them without changing a
casting contract.

Sources checked 2026-09-19:

* https://2e.aonprd.com/Classes.aspx?ID=39
* https://2e.aonprd.com/Classes.aspx?ID=38
* https://2e.aonprd.com/ArcaneSchools.aspx?ID=22
* https://2e.aonprd.com/Feats.aspx?ID=4577
* https://2e.aonprd.com/Feats.aspx?ID=4580
* https://2e.aonprd.com/Feats.aspx?ID=5121
"""

from __future__ import annotations

from dataclasses import replace

from .model import CreatureDefinition, CreaturePlacement, EncounterSetup, Position, PreparedSpellDefinition
from .witch_content import FLAMEKEEPER_FOX, FAITHS_FLAMEKEEPER_WITCH
from .wizard_content import BATTLE_MAGIC_WIZARD


def _level_two_statistics(definition: CreatureDefinition) -> dict[str, object]:
    """Advance only level-derived level-one statistics to level two."""
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


# Cantrip Expansion is the selected level-two class feat for both prepared
# casters.  The additional two cantrip preparations are real literal slots;
# they do not alter the accepted rank-one casting or curriculum contracts.
BATTLE_MAGIC_WIZARD_L2_CANTRIP_EXPANSION = replace(
    BATTLE_MAGIC_WIZARD,
    definition_id="wizard_battle_magic_level_2_cantrip_expansion",
    name="Level 2 Battle Magic Wizard (Cantrip Expansion)",
    hp=24,
    **_level_two_statistics(BATTLE_MAGIC_WIZARD),
    prepared_spells=(
        *BATTLE_MAGIC_WIZARD.prepared_spells,
        PreparedSpellDefinition("wizard_l2_detect_magic", "ordinary_cantrip", "detect_magic", cantrip=True),
        PreparedSpellDefinition("wizard_l2_sigil", "ordinary_cantrip", "sigil", cantrip=True),
        PreparedSpellDefinition("wizard_l2_sure_strike", "ordinary_rank_1", "sure_strike"),
    ),
    spell_substitution_book=(
        *BATTLE_MAGIC_WIZARD.spell_substitution_book,
        # Level advancement adds two actual supported arcane cantrips to the
        # finite book.  Cantrip Expansion prepares those two new choices.
        type(BATTLE_MAGIC_WIZARD.spell_substitution_book[0])("detect_magic", 1, "ordinary_cantrip"),
        type(BATTLE_MAGIC_WIZARD.spell_substitution_book[0])("sigil", 1, "ordinary_cantrip"),
    ),
    feats=(*BATTLE_MAGIC_WIZARD.feats, "Cantrip Expansion", "Assurance (Athletics)"),
    sheet_notes=(*(
        note for note in BATTLE_MAGIC_WIZARD.sheet_notes
        if "The finite book has eleven cantrips and seven rank-1 spells" not in note
    ),
        "The finite book has thirteen cantrips and seven rank-1 spells after the level-up additions. Daily preparation has seven ordinary cantrip slots, one Battle Magic curriculum cantrip slot, three ordinary rank-1 slots, and one curriculum rank-1 slot; Force Bolt is separate.",
        "Level 2 adds Cantrip Expansion and Assurance (Athletics). The Wizard has seven ordinary prepared cantrips plus one Battle Magic curriculum cantrip, three ordinary rank-1 slots, and one curriculum rank-1 slot.",
        "The level-up spellbook additions are Detect Magic and Sigil; the selected daily preparation puts both new, supported arcane cantrips in Cantrip Expansion's two additional slots.",
        "Sources: https://2e.aonprd.com/Classes.aspx?ID=39; https://2e.aonprd.com/ArcaneSchools.aspx?ID=22; https://2e.aonprd.com/Spells.aspx?ID=1485; https://2e.aonprd.com/Feats.aspx?ID=4580; https://2e.aonprd.com/Feats.aspx?ID=5121.",
    ),
)


# A Human can take Natural Ambition at level one to select this level-one
# Wizard feat. It replaces the accepted build's Natural Skill ancestry feat,
# so its two granted trained skills are not retained on the alternative sheet.
# The spellshape itself is already admitted and leaves preparation unchanged.
BATTLE_MAGIC_WIZARD_L1_REACH = replace(
    BATTLE_MAGIC_WIZARD,
    definition_id="wizard_battle_magic_level_1_reach_spell",
    name="Level 1 Battle Magic Wizard (Reach Spell)",
    skills=tuple(
        entry for entry in BATTLE_MAGIC_WIZARD.skills
        if entry[0] not in {"athletics", "acrobatics"}
    ),
    abilities=(*BATTLE_MAGIC_WIZARD.abilities, "reach_spell"),
    feats=("Fleet", "Natural Ambition", "Assurance (Nature)", "Reach Spell"),
    sheet_notes=(*(
        note for note in BATTLE_MAGIC_WIZARD.sheet_notes
        if "Natural Skill grants Athletics and Acrobatics" not in note
    ),
        "Versatile Human grants Fleet. Natural Ambition selects Reach Spell in place of Natural Skill, so this alternative does not receive Athletics or Acrobatics from that ancestry feat.",
        "Level-1 alternative: Reach Spell is a one-action spellshape and increases the next ranged or touch spell's range by 30 feet. It replaces no spell preparation and uses the existing reviewed spellshape lifecycle.",
        "Source: https://2e.aonprd.com/Feats.aspx?ID=4577.",
    ),
)


# The Witch has the same 5->7 Cantrip Expansion increase and the printed
# 2->3 first-rank prepared-slot progression at level 2. Its familiar learns
# two new, source-legal divine rank-one spells at this level: Harm and
# Protection. The shared spell runtime admits only Harm's two-action living
# target mode, while the public sheet prepares both learned spells literally.
FAITHS_FLAMEKEEPER_WITCH_L2_CANTRIP_EXPANSION = replace(
    FAITHS_FLAMEKEEPER_WITCH,
    definition_id="faiths_flamekeeper_witch_level_2_cantrip_expansion",
    name="Level 2 Faith's Flamekeeper Witch (Cantrip Expansion)",
    hp=24,
    **_level_two_statistics(FAITHS_FLAMEKEEPER_WITCH),
    prepared_spells=(
        # Daily preparation can change the two level-one rank-one selections;
        # retain Command and prepare both new familiar spells instead of Heal.
        *(spell for spell in FAITHS_FLAMEKEEPER_WITCH.prepared_spells if spell.slot_id != "witch_heal"),
        PreparedSpellDefinition("witch_l2_void_warp", "witch_cantrip", "void_warp", cantrip=True),
        PreparedSpellDefinition("witch_l2_vitality_lash", "witch_cantrip", "vitality_lash", cantrip=True),
        PreparedSpellDefinition("witch_l2_harm", "witch_rank_1", "harm"),
        PreparedSpellDefinition("witch_l2_protection", "witch_rank_1", "protection"),
    ),
    feats=(*FAITHS_FLAMEKEEPER_WITCH.feats, "Cantrip Expansion", "Assurance (Athletics)"),
    sheet_notes=(*(
        note for note in FAITHS_FLAMEKEEPER_WITCH.sheet_notes
        if "The familiar knows ten divine cantrips" not in note
    ),
        "The familiar knows ten divine cantrips and eight rank-1 spells (the level-two additions are Harm and Protection).",
        "Level 2 adds Cantrip Expansion and Assurance (Athletics). It prepares seven cantrips and three rank-1 spells: the two added cantrip slots use Void Warp and Vitality Lash, and the rank-1 slots prepare Command, Harm, and Protection.",
        "The familiar's two new learned spells are Harm and Protection. The finite public slice admits Harm's two-action living-target mode and Protection's one willing-creature, one-minute ward; Harm's one- and three-action modes and willing-undead healing are not advertised.",
        "Sources: https://2e.aonprd.com/Classes.aspx?ID=38; https://2e.aonprd.com/Spells.aspx?ID=1552; https://2e.aonprd.com/Spells.aspx?ID=1641; https://2e.aonprd.com/Feats.aspx?ID=4580; https://2e.aonprd.com/Feats.aspx?ID=5121.",
    ),
)


# The familiar is a Pet: it takes its master's level, AC, saves, and the
# selected master-derived modifiers. Tough raises its HP from 5 per level to
# 7 per level. This literal L2 definition prevents the level-two setup from
# silently retaining the level-one fox's numbers.
FAITHS_FLAMEKEEPER_FOX_L2 = replace(
    FLAMEKEEPER_FOX,
    definition_id="faiths_flamekeeper_fox_level_2",
    name="Level 2 Flamekeeper Fox Familiar",
    hp=14,
    ac=16,
    perception=6,
    skills=tuple(
        (name, rank, 6 if name in {"acrobatics", "stealth"} else 2)
        for name, rank, _modifier in FLAMEKEEPER_FOX.skills
    ),
    saves=tuple((name, rank, 6) for name, rank, _modifier in FLAMEKEEPER_FOX.saves),
    level=2,
    sheet_notes=(
        "Level 2 Tiny fox familiar: Pet rules give its level, AC, and saves from its level-2 master; Tough grants 14 HP. It has no Strike, flanking, independent initiative, or actions outside a command.",
    ),
)


FAITHS_FLAMEKEEPER_WITCH_L1_REACH = replace(
    FAITHS_FLAMEKEEPER_WITCH,
    definition_id="faiths_flamekeeper_witch_level_1_reach_spell",
    name="Level 1 Faith's Flamekeeper Witch (Reach Spell)",
    skills=tuple(
        entry for entry in FAITHS_FLAMEKEEPER_WITCH.skills
        if entry[0] not in {"athletics", "acrobatics"}
    ),
    abilities=(*FAITHS_FLAMEKEEPER_WITCH.abilities, "reach_spell"),
    feats=("Fleet", "Natural Ambition", "Assurance (Nature)", "Reach Spell"),
    sheet_notes=(*FAITHS_FLAMEKEEPER_WITCH.sheet_notes,
        "Natural Ambition selects Reach Spell in place of Natural Skill, so this alternative does not receive Athletics or Acrobatics from that ancestry feat.",
        "Level-1 alternative: Reach Spell is a one-action spellshape that increases the next ranged or touch spell's range by 30 feet, using the already accepted lifecycle without changing familiar or preparation rules.",
        "Source: https://2e.aonprd.com/Feats.aspx?ID=4577.",
    ),
)


BATTLE_MAGIC_WIZARD_L2_CANTRIP_EXPANSION_SETUP = EncounterSetup(
    "wizard_battle_magic_level_2_cantrip_expansion",
    "Level 2 Battle Magic Wizard Cantrip Expansion",
    15,
    5,
    (
        CreaturePlacement("wizard", BATTLE_MAGIC_WIZARD_L2_CANTRIP_EXPANSION.definition_id, "Level 2 Battle Magic Wizard", "blue", Position(1, 2)),
        CreaturePlacement("wizard_target", "guard_dog_mc2924", "Guard Dog", "red", Position(7, 2)),
    ),
)

FAITHS_FLAMEKEEPER_WITCH_L2_CANTRIP_EXPANSION_SETUP = EncounterSetup(
    "faiths_flamekeeper_witch_level_2_cantrip_expansion",
    "Level 2 Faith's Flamekeeper Witch Cantrip Expansion",
    15,
    5,
    (
        CreaturePlacement("witch", FAITHS_FLAMEKEEPER_WITCH_L2_CANTRIP_EXPANSION.definition_id, "Level 2 Flamekeeper Witch", "blue", Position(1, 2)),
        CreaturePlacement("fox", FAITHS_FLAMEKEEPER_FOX_L2.definition_id, "Level 2 Flamekeeper Fox", "blue", Position(1, 2)),
        CreaturePlacement("witch_target", "flamekeeper_common_speaker", "Command Target", "red", Position(7, 2)),
    ),
)

BATTLE_MAGIC_WIZARD_L1_REACH_SETUP = EncounterSetup(
    "wizard_battle_magic_level_1_reach_spell",
    "Level 1 Battle Magic Wizard Reach Spell",
    15,
    5,
    (
        CreaturePlacement("wizard", BATTLE_MAGIC_WIZARD_L1_REACH.definition_id, "Battle Magic Wizard", "blue", Position(1, 2)),
        CreaturePlacement("wizard_target", "guard_dog_mc2924", "Guard Dog", "red", Position(8, 2)),
    ),
)

FAITHS_FLAMEKEEPER_WITCH_L1_REACH_SETUP = EncounterSetup(
    "faiths_flamekeeper_witch_level_1_reach_spell",
    "Level 1 Faith's Flamekeeper Witch Reach Spell",
    15,
    5,
    (
        CreaturePlacement("witch", FAITHS_FLAMEKEEPER_WITCH_L1_REACH.definition_id, "Flamekeeper Witch", "blue", Position(1, 2)),
        CreaturePlacement("fox", "faiths_flamekeeper_fox", "Flamekeeper Fox", "blue", Position(1, 2)),
        CreaturePlacement("witch_target", "flamekeeper_common_speaker", "Command Target", "red", Position(8, 2)),
    ),
)


L2_PREPARED_DEFINITIONS = (
    BATTLE_MAGIC_WIZARD_L2_CANTRIP_EXPANSION,
    FAITHS_FLAMEKEEPER_WITCH_L2_CANTRIP_EXPANSION,
    FAITHS_FLAMEKEEPER_FOX_L2,
    BATTLE_MAGIC_WIZARD_L1_REACH,
    FAITHS_FLAMEKEEPER_WITCH_L1_REACH,
)
L2_PREPARED_SETUPS = (
    BATTLE_MAGIC_WIZARD_L2_CANTRIP_EXPANSION_SETUP,
    FAITHS_FLAMEKEEPER_WITCH_L2_CANTRIP_EXPANSION_SETUP,
    BATTLE_MAGIC_WIZARD_L1_REACH_SETUP,
    FAITHS_FLAMEKEEPER_WITCH_L1_REACH_SETUP,
)
