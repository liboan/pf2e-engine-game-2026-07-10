"""W4 caster feat alternates with finite, executable mechanics.

Sources checked 2026-09-20:

* https://2e.aonprd.com/Feats.aspx?ID=5026 (Energy Ablation)
* https://2e.aonprd.com/Feats.aspx?ID=4644 (Domain Initiate)
* https://2e.aonprd.com/Spells.aspx?ID=1852 (Weapon Surge)
* https://2e.aonprd.com/Feats.aspx?ID=4715 (Widen Spell)
* https://app.demiplane.com/nexus/pathfinder2e/spells/cackle-rm (Cackle)

Each entry is an alternate character sheet. The base W1-W3 sheets remain
unchanged, and no class-wide feat-selection system is implied.
"""

from dataclasses import replace

from .model import CreatureDefinition, CreaturePlacement, EncounterSetup, Position, SpontaneousSpellDefinition
from .sorcerer_content import ANGELIC_SORCERER_STAGED
from .witch_content import FAITHS_FLAMEKEEPER_WITCH, FLAMEKEEPER_FOX
from .wizard_content import BATTLE_MAGIC_WIZARD


def _level_two_statistics(definition: CreatureDefinition) -> dict[str, object]:
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


def build_w4_caster_content(warpriest: CreatureDefinition):
    wizard = replace(
        BATTLE_MAGIC_WIZARD,
        definition_id="wizard_battle_magic_level_2_energy_ablation",
        name="Level 2 Battle Magic Wizard (Energy Ablation)",
        hp=24,
        **_level_two_statistics(BATTLE_MAGIC_WIZARD),
        abilities=(*BATTLE_MAGIC_WIZARD.abilities, "energy_ablation"),
        feats=(*BATTLE_MAGIC_WIZARD.feats, "Energy Ablation", "Assurance (Athletics)"),
        sheet_notes=(*BATTLE_MAGIC_WIZARD.sheet_notes,
            "Energy Ablation is the level-2 Spellshape feat: choose acid, cold, electricity, fire, force, sonic, vitality, or void; the next qualifying Cast grants matching resistance equal to spell rank until the end of the next turn.",
            "Source: https://2e.aonprd.com/Feats.aspx?ID=5026.",
        ),
    )
    cleric = replace(
        warpriest,
        definition_id="warpriest_c_domain_initiate_weapon_surge",
        name="Level 1 Iomedaean Warpriest C (Domain Initiate: Zeal)",
        focus_spells=(SpontaneousSpellDefinition("weapon_surge", 1),),
        focus_source="domain",
        focus_points=1,
        focus_capacity=1,
        abilities=(*warpriest.abilities, "domain_initiate", "weapon_surge"),
        skills=tuple(entry for entry in warpriest.skills if entry[0] not in {"crafting", "society"}),
        feats=("Natural Ambition", "Assurance (Athletics)", "Domain Initiate"),
        sheet_notes=(*warpriest.sheet_notes,
            "Domain Initiate selects Iomedae's finite zeal domain and grants Weapon Surge as the initial domain focus spell; this alternate does not claim other domain choices.",
            "Natural Ambition replaces Natural Skill, so this alternate does not retain Crafting or Society from that ancestry feat.",
            "Sources: https://2e.aonprd.com/Feats.aspx?ID=4644; https://2e.aonprd.com/Spells.aspx?ID=1852; https://2e.aonprd.com/Feats.aspx?ID=4479.",
        ),
    )
    sorcerer = replace(
        ANGELIC_SORCERER_STAGED,
        definition_id="sorcerer_angelic_level_1_widen_spell",
        name="Level 1 Angelic Sorcerer (Widen Spell)",
        skills=tuple(entry for entry in ANGELIC_SORCERER_STAGED.skills if entry[0] not in {"crafting", "survival"}),
        spontaneous_spells=(*ANGELIC_SORCERER_STAGED.spontaneous_spells, SpontaneousSpellDefinition("breathe_fire", 1)),
        abilities=(*ANGELIC_SORCERER_STAGED.abilities, "widen_spell"),
        feats=("Natural Ambition", "Assurance (Athletics)", "Widen Spell"),
        sheet_notes=(*ANGELIC_SORCERER_STAGED.sheet_notes,
            "Natural Ambition replaces Natural Skill, so this alternate does not retain Crafting or Survival from that ancestry feat.",
            "Widen Spell is the legal level-1 Sorcerer feat and uses the existing finite Breathe Fire cone spellshape path.",
            "Sources: https://2e.aonprd.com/Feats.aspx?ID=4715; https://2e.aonprd.com/Spells.aspx?ID=1457; https://2e.aonprd.com/Feats.aspx?ID=4479.",
        ),
    )
    witch = replace(
        FAITHS_FLAMEKEEPER_WITCH,
        definition_id="faiths_flamekeeper_witch_level_1_cackle",
        name="Level 1 Faith's Flamekeeper Witch (Cackle)",
        skills=tuple(entry for entry in FAITHS_FLAMEKEEPER_WITCH.skills if entry[0] not in {"crafting", "society"}),
        focus_spells=(*FAITHS_FLAMEKEEPER_WITCH.focus_spells, SpontaneousSpellDefinition("cackle", 1)),
        focus_points=2,
        focus_capacity=2,
        abilities=(*FAITHS_FLAMEKEEPER_WITCH.abilities, "cackle"),
        feats=("Fleet", "Natural Ambition", "Assurance (Nature)", "Cackle"),
        sheet_notes=(*FAITHS_FLAMEKEEPER_WITCH.sheet_notes,
            "Natural Ambition replaces Natural Skill, so this alternate does not retain Crafting or Society from that ancestry feat.",
            "Cackle is a Focus 1 free-action hex that spends one Focus Point and extends the Witch's active Stoke the Heart through the next two source turns.",
            "Source: https://app.demiplane.com/nexus/pathfinder2e/spells/cackle-rm.",
        ),
    )
    definitions = (wizard, cleric, sorcerer, witch)
    setups = (
        EncounterSetup(
            "w4_energy_ablation_vs_guard_dog", "W4 Energy Ablation Wizard", 7, 5,
            (CreaturePlacement("wizard", wizard.definition_id, "Energy Ablation Wizard", "blue", Position(1, 2)),
             CreaturePlacement("dog", "guard_dog_mc2924", "Guard Dog", "red", Position(4, 2))),
        ),
        EncounterSetup(
            "w4_weapon_surge_vs_guard_dog", "W4 Weapon Surge Warpriest", 7, 5,
            (CreaturePlacement("cleric", cleric.definition_id, "Domain Warpriest", "blue", Position(1, 2)),
             CreaturePlacement("dog", "guard_dog_mc2924", "Guard Dog", "red", Position(2, 2))),
        ),
        EncounterSetup(
            "w4_widen_sorcery_vs_guard_dog", "W4 Widen Spell Sorcerer", 7, 5,
            (CreaturePlacement("sorcerer", sorcerer.definition_id, "Widen Spell Sorcerer", "blue", Position(1, 2)),
             CreaturePlacement("dog", "guard_dog_mc2924", "Guard Dog", "red", Position(4, 2))),
        ),
        EncounterSetup(
            "w4_cackle_witch", "W4 Cackle Witch", 7, 5,
            (CreaturePlacement("witch", witch.definition_id, "Cackle Witch", "blue", Position(1, 2)),
             CreaturePlacement("fox", FLAMEKEEPER_FOX.definition_id, "Flamekeeper Fox", "blue", Position(1, 2)),
             CreaturePlacement("ally", FAITHS_FLAMEKEEPER_WITCH.definition_id, "Hex Ally", "blue", Position(2, 2)),
             CreaturePlacement("dog", "guard_dog_mc2924", "Guard Dog", "red", Position(5, 2))),
        ),
    )
    return definitions, setups
