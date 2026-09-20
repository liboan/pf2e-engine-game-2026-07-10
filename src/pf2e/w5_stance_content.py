"""Runtime-admitted W5 Monk Tiger and Wolf stance sheets."""

from __future__ import annotations

from dataclasses import replace
from types import MappingProxyType

from .model import AttackDefinition, CreatureDefinition, CreaturePlacement, EncounterSetup, Position


def _stance_definition(monk: CreatureDefinition, *, stance: str) -> CreatureDefinition:
    label = "Tiger" if stance == "tiger" else "Wolf"
    attack_id = f"{stance}_claws" if stance == "tiger" else f"{stance}_jaws"
    attack_name = "Tiger Claws" if stance == "tiger" else "Wolf Jaws"
    traits = {"attack", "melee", "agile", "finesse", "nonlethal", "unarmed"}
    if stance == "wolf":
        traits.add("trip")
    special = AttackDefinition(
        attack_id=attack_id,
        name=attack_name,
        modifier=7,
        reach_ft=5,
        traits=frozenset(traits),
        damage_type="slashing" if stance == "tiger" else "piercing",
        damage_dice=(8,),
        damage_modifier=2,
        attack_attribute="dexterity",
        damage_attribute="strength",
        hands_required=0,
    )
    abilities = tuple(item for item in monk.abilities if item != "monastic_weaponry") + (f"{stance}_stance",)
    feats = tuple(item for item in monk.feats if item != "Monastic Weaponry") + (f"{label} Stance",)
    proficiencies = tuple(
        item for item in monk.proficiencies
        if item[0] != "simple_and_martial_monk_weapons"
    )
    notes = tuple(
        item for item in monk.sheet_notes
        if "Monastic Weaponry" not in item and "Feats.aspx?ID=5979" not in item
    )
    notes += (
        f"Alternate level-1 class-feat choice: {label} Stance is a one-action stance while unarmored. "
        f"It grants {attack_name} (1d8 {'slashing' if stance == 'tiger' else 'piercing'}; agile, finesse, nonlethal, unarmed). "
        "Ordinary fists remain legal while the stance is active. "
        + ("Tiger Stance permits a horizontal 10-foot Step with Speed 20 or higher; a damaging critical adds exactly 1d4 persistent bleed. "
           if stance == "tiger" else
           "Wolf Stance grants +1 precision damage against off-guard targets; Wolf Jaws can Trip only while actually flanking. ")
        + f"Sources: https://2e.aonprd.com/Feats.aspx?ID={'5983' if stance == 'tiger' else '5984'}; "
        "https://2e.aonprd.com/Traits.aspx?ID=544.",
    )
    return replace(
        monk,
        definition_id=f"monk_{stance}_stance_level_1",
        name=f"Level 1 Monk ({label} Stance)",
        attacks=tuple(item for item in monk.attacks if item.item_id != "kama") + (special,),
        abilities=abilities,
        feats=feats,
        proficiencies=proficiencies,
        held_items=(),
        sheet_notes=notes,
    )


def build_w5_stance_content(*, monk: CreatureDefinition, enemy_definition_id: str):
    tiger = _stance_definition(monk, stance="tiger")
    wolf = _stance_definition(monk, stance="wolf")
    definitions = MappingProxyType({tiger.definition_id: tiger, wolf.definition_id: wolf})
    setups = MappingProxyType({
        "w5_tiger_stance_vs_guard_dog": EncounterSetup(
            "w5_tiger_stance_vs_guard_dog", "W5 Tiger Stance Monk versus Guard Dog", 7, 3,
            (
                CreaturePlacement("monk", tiger.definition_id, "Tiger Monk", "blue", Position(1, 1)),
                CreaturePlacement("dog", enemy_definition_id, "Guard Dog", "red", Position(3, 1)),
            ),
        ),
        "w5_wolf_stance_vs_guard_dog": EncounterSetup(
            "w5_wolf_stance_vs_guard_dog", "W5 Wolf Stance Monk versus Guard Dog", 7, 5,
            (
                CreaturePlacement("monk", wolf.definition_id, "Wolf Monk", "blue", Position(2, 2)),
                CreaturePlacement("flanker", enemy_definition_id, "Flanking Ally", "blue", Position(2, 1)),
                CreaturePlacement("dog", enemy_definition_id, "Guard Dog", "red", Position(4, 2)),
            ),
        ),
    })
    return definitions, setups
