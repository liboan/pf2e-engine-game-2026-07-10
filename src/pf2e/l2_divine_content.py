"""Finite level-two sheets for the selected divine representatives.

The builder takes level-one records from ``content`` so this module owns no
reverse catalog import.  The admitted feat choices are intentionally small:
Divine Grace, Healing Hands, and Reach Spell.  Domain alternatives remain
limited to Iomedae's zeal / Weapon Surge and healing / Healer's Blessing until
their particular focus-spell handlers are separately exercised.

Sources checked 2026-09-19:
* Champion and Divine Grace: https://2e.aonprd.com/Classes.aspx?ID=58;
  https://2e.aonprd.com/Feats.aspx?ID=5892
* Cleric, Healing Hands, and Domain Initiate: https://2e.aonprd.com/Classes.aspx?ID=33;
  https://2e.aonprd.com/Feats.aspx?ID=4646;
  https://2e.aonprd.com/Feats.aspx?ID=4644
* Oracle and Reach Spell: https://2e.aonprd.com/Classes.aspx?ID=61;
  https://2e.aonprd.com/Feats.aspx?ID=4577
* Protection: https://2e.aonprd.com/Spells.aspx?ID=1641
* Quick Jump: https://2e.aonprd.com/Feats.aspx?ID=5196
"""

from __future__ import annotations

from dataclasses import replace
from types import MappingProxyType

from .model import (
    CreatureDefinition,
    CreaturePlacement,
    EncounterSetup,
    Position,
    PreparedSpellDefinition,
    SpontaneousSlotDefinition,
    SpontaneousSpellDefinition,
)


def _level_two_statistics(definition: CreatureDefinition) -> dict[str, object]:
    if definition.level != 1:
        raise ValueError("level-two divine sheets require level-one base definitions")
    return {
        "ac": definition.ac + 1,
        "perception": definition.perception + 1,
        "attacks": tuple(replace(attack, modifier=attack.modifier + 1) for attack in definition.attacks),
        "skills": tuple((name, rank, modifier + 1) for name, rank, modifier in definition.skills),
        "saves": tuple((name, rank, modifier + 1) for name, rank, modifier in definition.saves),
        "class_dc": None if definition.class_dc is None else definition.class_dc + 1,
        "spell_attack": None if definition.spell_attack is None else definition.spell_attack + 1,
        "spell_dc": None if definition.spell_dc is None else definition.spell_dc + 1,
        "level": 2,
    }


def build_l2_divine_content(
    *,
    champion: CreatureDefinition,
    warpriest: CreatureDefinition,
    oracle: CreatureDefinition,
    enemy_definition_id: str,
) -> tuple[MappingProxyType, MappingProxyType]:
    """Build literal L2 sheets plus compact public encounters."""
    justice_l2 = replace(
        champion,
        definition_id="justice_champion_iomedae_level_2_divine_grace",
        name="Level 2 Justice Champion of Iomedae (Divine Grace)",
        hp=32,
        abilities=(*champion.abilities, "divine_grace"),
        feats=(*champion.feats, "Divine Grace", "Quick Jump"),
        **_level_two_statistics(champion),
        sheet_notes=(*champion.sheet_notes,
            "Level 2: HP rises by 12 (Champion 10 + Constitution 2), and level-based statistics rise by one.",
            "Divine Grace is the selected level-2 Champion feat: before the Champion rolls a save against a spell, spend their reaction for a +2 circumstance bonus. Quick Jump is the selected trained-Athletics skill feat.",
            "No Deity's Domain build is advertised here: its separate focus-spell path remains limited to an independently exercised legal domain handler.",
        ),
    )
    warpriest_l2 = replace(
        warpriest,
        definition_id="warpriest_c_iomedae_level_2_healing_hands",
        name="Level 2 Iomedaean Warpriest C (Healing Hands)",
        hp=26,
        abilities=(*warpriest.abilities, "healing_hands"),
        feats=(*warpriest.feats, "Healing Hands", "Quick Jump"),
        prepared_spells=(*warpriest.prepared_spells,
            PreparedSpellDefinition("ordinary_heal_3", "ordinary", "heal", rank=1),
        ),
        **_level_two_statistics(warpriest),
        sheet_notes=(*warpriest.sheet_notes,
            "Level 2: HP rises by 9 (Cleric 8 + Constitution 1), level-based statistics rise by one, and the ordinary rank-1 preparation count becomes three while the four Heal-font slots remain separate.",
            "Healing Hands is the selected legal level-1 Cleric feat in the level-2 class-feat slot; every Heal cast by this sheet rolls d10s instead of d8s, retaining the two-action +8 only while healing. Quick Jump is the selected trained-Athletics skill feat.",
            "Domain Initiate alternatives stay finite: Iomedae's only future supported choice is zeal / Weapon Surge; healing / Healer's Blessing is reserved for a legal healing-domain sheet rather than inferred for Iomedae.",
        ),
    )
    oracle_l2 = replace(
        oracle,
        definition_id="life_oracle_level_2_reach_spell",
        name="Level 2 Life Oracle (Reach Spell)",
        hp=28,
        abilities=(*oracle.abilities, "reach_spell"),
        feats=(*oracle.feats, "Reach Spell", "Quick Jump"),
        spontaneous_slots=tuple(
            SpontaneousSlotDefinition(slot.slot_id, slot.source, slot.rank, 4)
            if slot.slot_id == "oracle_rank1" else slot
            for slot in oracle.spontaneous_slots
        ),
        spontaneous_spells=(*oracle.spontaneous_spells, SpontaneousSpellDefinition("protection", 1)),
        **_level_two_statistics(oracle),
        sheet_notes=(*oracle.sheet_notes,
            "Level 2: HP rises by 10 (Oracle 8 + Constitution 2), level-based statistics rise by one, the rank-1 spontaneous pool rises from three to four slots, and Protection is the one new chosen rank-1 repertoire spell.",
            "Reach Spell is the selected one-action spellshape class feat and uses the existing saved range lifecycle. Quick Jump is the selected trained-Athletics skill feat. Nudge the Scales heals 6 before the recipient's Life curse penalty; that penalty is 2 per cursebound value at this level.",
        ),
    )
    definitions = MappingProxyType({
        justice_l2.definition_id: justice_l2,
        warpriest_l2.definition_id: warpriest_l2,
        oracle_l2.definition_id: oracle_l2,
    })
    setups = MappingProxyType({
        "l2_divine_party_protection_healing": EncounterSetup(
            "l2_divine_party_protection_healing",
            "Level 2 Justice, Warpriest, and Life Oracle",
            7,
            4,
            (
                CreaturePlacement("champion", justice_l2.definition_id, "Level 2 Justice Champion", "blue", Position(2, 2)),
                CreaturePlacement("cleric", warpriest_l2.definition_id, "Level 2 Iomedaean Warpriest", "blue", Position(2, 1)),
                CreaturePlacement("oracle", oracle_l2.definition_id, "Level 2 Life Oracle", "blue", Position(1, 2)),
                CreaturePlacement("dog", enemy_definition_id, "Guard Dog", "red", Position(3, 1)),
            ),
        ),
        "l2_life_oracle_reach_spell": EncounterSetup(
            "l2_life_oracle_reach_spell",
            "Level 2 Life Oracle Reach Spell",
            15,
            3,
            (
                CreaturePlacement("oracle", oracle_l2.definition_id, "Level 2 Life Oracle", "blue", Position(1, 1)),
                CreaturePlacement("dog", enemy_definition_id, "Guard Dog", "red", Position(8, 1)),
            ),
        ),
        "l2_divine_grace_review": EncounterSetup(
            "l2_divine_grace_review",
            "Level 2 Divine Grace against Reach Spell",
            15,
            3,
            (
                CreaturePlacement("oracle", oracle_l2.definition_id, "Level 2 Life Oracle", "red", Position(1, 1)),
                CreaturePlacement("champion", justice_l2.definition_id, "Level 2 Justice Champion", "blue", Position(8, 1)),
            ),
        ),
    })
    return definitions, setups
