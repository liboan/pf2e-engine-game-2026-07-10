"""W5 Focus/font content: Initiate Warden, Harming Hands, and Hymn of Healing.

Sources checked 2026-09-20:
https://2e.aonprd.com/Feats.aspx?ID=4862,
https://2e.aonprd.com/Spells.aspx?ID=1863,
https://2e.aonprd.com/Feats.aspx?ID=4645,
https://2e.aonprd.com/Feats.aspx?ID=4574,
https://2e.aonprd.com/Spells.aspx?ID=1768.
"""

from dataclasses import replace
from types import MappingProxyType

from .bard_content import MAESTRO_BARD_STAGED
from .model import (
    CreatureDefinition,
    CreaturePlacement,
    EncounterSetup,
    PreparedSpellDefinition,
    Position,
    SpontaneousSpellDefinition,
)
from .ranger_monk_content import RANGER_PRECISION


def _harm_slots(base):
    return tuple(
        replace(slot, spell_id="harm", slot_id=slot.slot_id.replace("heal", "harm"))
        for slot in base.prepared_spells
        if not slot.cantrip
    )


def build_w5_focus_content(warpriest: CreatureDefinition):
    ranger = replace(
        RANGER_PRECISION,
        definition_id="ranger_precision_level_1_initiate_warden",
        name="Level 1 Precision Ranger (Initiate Warden)",
        abilities=tuple(ability for ability in RANGER_PRECISION.abilities if ability != "hunted_shot") + ("gravity_weapon",),
        feats=("Natural Skill", "Forager", "Fleet", "Hunter's Edge (Precision)", "Initiate Warden"),
        focus_spells=(SpontaneousSpellDefinition("gravity_weapon", 1),),
        focus_source="warden",
        focus_points=1,
        focus_capacity=1,
        spell_tradition="primal",
        spell_attack=5,
        spell_dc=15,
        spell_attribute="wisdom",
        sheet_notes=tuple(note for note in RANGER_PRECISION.sheet_notes if "Hunted Shot is the selected" not in note) + (
            "Initiate Warden replaces Hunted Shot and selects only Gravity Weapon. It grants a one-point primal Wisdom focus pool; no attack bonus or hunted-prey prerequisite is inferred.",
            "Source: https://2e.aonprd.com/Feats.aspx?ID=4862; https://2e.aonprd.com/Spells.aspx?ID=1863.",
        ),
    )
    cleric = replace(
        warpriest,
        definition_id="warpriest_nethys_harming_hands_level_1",
        name="Level 1 Nethys Warpriest (Harming Hands)",
        deity="Nethys",
        abilities=(*warpriest.abilities, "harming_hands", "harmful_font"),
        feats=("Natural Ambition", "Assurance (Athletics)", "Harming Hands", "Deadly Simplicity"),
        skills=tuple(skill for skill in warpriest.skills if skill[0] not in {"crafting", "society"}) + (("arcana", "trained", 7),),
        held_items=(),
        attacks=tuple(attack for attack in warpriest.attacks if attack.attack_id == "fist"),
        prepared_spells=tuple((*warpriest.prepared_spells[:5], *_harm_slots(warpriest))),
        spell_sanctification="unholy",
        sheet_notes=(
            "Assurance (Athletics) result is 13; it replaces the roll and adds no modifiers.",
            "Prepared divine casting; the listed slots are a fixed day's preparation.",
            "Prepared cantrips are repeatable and do not expend prepared rank-1 Harm slots.",
            "Nethys grants harmful font and unholy sanctification; Arcana is the deity skill and Religion remains the cleric class skill.",
            "Shield Block is retained on the sheet but unavailable: this fixed loadout owns no shield.",
            "Nethys permits harmful font; this fixed mundane loadout has four Harm-font slots and two ordinary rank-1 Harm slots.",
            "Natural Ambition selects Harming Hands. No longsword or staff is granted; Deadly Simplicity is an admitted feat grant.",
            "Harming Hands changes only the admitted two-action rank-1 living-target Harm die from d8 to d10.",
            "Sources: https://2e.aonprd.com/Feats.aspx?ID=4645; https://2e.aonprd.com/Deities.aspx?ID=288; https://2e.aonprd.com/Doctrines.aspx?ID=5.",
        ),
    )
    bard = replace(
        MAESTRO_BARD_STAGED,
        definition_id="bard_maestro_level_1_hymn_of_healing",
        name="Level 1 Maestro Bard (Hymn of Healing)",
        skills=tuple(skill for skill in MAESTRO_BARD_STAGED.skills if skill[0] not in {"society", "medicine"}),
        feats=("Fleet", "Natural Ambition", "Assurance (Athletics)", "Hymn of Healing"),
        focus_spells=(*MAESTRO_BARD_STAGED.focus_spells, SpontaneousSpellDefinition("hymn_of_healing", 1)),
        focus_points=3,
        focus_capacity=3,
        abilities=(*MAESTRO_BARD_STAGED.abilities, "hymn_of_healing"),
        sheet_notes=(*MAESTRO_BARD_STAGED.sheet_notes,
            "Natural Ambition selects Hymn of Healing in place of Natural Skill, so Society and Medicine are not retained. Hymn is a third focus spell and raises the focus pool to three.",
            "Hymn of Healing is a two-action composition sustained for at most four rounds; rank 1 grants fast healing 2 at recipient turn start and 2 temporary HP on cast and first Sustain each round.",
            "Sources: https://2e.aonprd.com/Feats.aspx?ID=4574; https://2e.aonprd.com/Spells.aspx?ID=1768.",
        ),
    )
    definitions = MappingProxyType({item.definition_id: item for item in (ranger, cleric, bard)})
    setups = MappingProxyType({
        "w5_gravity_weapon_vs_guard_dog": EncounterSetup(
            "w5_gravity_weapon_vs_guard_dog", "W5 Initiate Warden Ranger", 7, 5,
            (CreaturePlacement("ranger", ranger.definition_id, "Initiate Warden Ranger", "blue", Position(1, 2)),
             CreaturePlacement("dog", "guard_dog_mc2924", "Guard Dog", "red", Position(4, 2))),
        ),
        "w5_harming_hands_vs_guard_dog": EncounterSetup(
            "w5_harming_hands_vs_guard_dog", "W5 Harming Hands Warpriest", 7, 5,
            (CreaturePlacement("cleric", cleric.definition_id, "Nethys Warpriest", "blue", Position(1, 2)),
             CreaturePlacement("dog", "guard_dog_mc2924", "Guard Dog", "red", Position(3, 2))),
        ),
        "w5_hymn_of_healing_vs_guard_dog": EncounterSetup(
            "w5_hymn_of_healing_vs_guard_dog", "W5 Hymn Bard", 7, 5,
            (CreaturePlacement("bard", bard.definition_id, "Hymn Bard", "blue", Position(1, 2)),
             CreaturePlacement("ally", "fighter_m_level_1", "Bard's Ally", "blue", Position(2, 2)),
             CreaturePlacement("dog", "guard_dog_mc2924", "Guard Dog", "red", Position(5, 2))),
        ),
    })
    return definitions, setups
