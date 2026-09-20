"""Source-checked level-2 sheets for the first-wave martial group.

This module intentionally builds records from supplied level-1 definitions.
The shared catalog owner can import the resulting maps without a reverse
``content`` import or a catalog cycle.

Sources checked 2026-09-19:

* Fighter and Sudden Charge: https://2e.aonprd.com/Classes.aspx?ID=35;
  https://2e.aonprd.com/Feats.aspx?ID=4774
* Barbarian and No Escape: https://2e.aonprd.com/Classes.aspx?ID=57;
  https://2e.aonprd.com/Feats.aspx?ID=5815
* Monk and Stunning Blows: https://2e.aonprd.com/Classes.aspx?ID=60;
  https://2e.aonprd.com/Feats.aspx?ID=5989
* Intimidating Strike: https://2e.aonprd.com/Feats.aspx?ID=4782
"""

from __future__ import annotations

from dataclasses import replace
from types import MappingProxyType

from .model import CreatureDefinition, CreaturePlacement, EncounterSetup, Position


def _level_skills(definition: CreatureDefinition) -> tuple[tuple[str, str | None, int], ...]:
    return tuple((name, rank, modifier + 1) for name, rank, modifier in definition.skills)


def _level_saves(definition: CreatureDefinition) -> tuple[tuple[str, str | None, int], ...]:
    return tuple((name, rank, modifier + 1) for name, rank, modifier in definition.saves)


def _level_two(
    definition: CreatureDefinition,
    *,
    definition_id: str,
    name: str,
    hp: int,
    class_feat: str,
    skill_feat: str,
    ability_id: str,
    note: str,
) -> CreatureDefinition:
    if definition.level != 1:
        raise ValueError("first-wave martial progression requires a level-1 base definition")
    if definition.class_dc is None:
        raise ValueError("first-wave martial progression requires a class DC")
    return replace(
        definition,
        definition_id=definition_id,
        name=name,
        hp=hp,
        ac=definition.ac + 1,
        perception=definition.perception + 1,
        attacks=tuple(replace(attack, modifier=attack.modifier + 1) for attack in definition.attacks),
        abilities=(*definition.abilities, ability_id),
        feats=(*definition.feats, class_feat, skill_feat),
        skills=_level_skills(definition),
        saves=_level_saves(definition),
        level=2,
        class_dc=definition.class_dc + 1,
        sheet_notes=(*definition.sheet_notes, note),
    )


def build_l2_martial_content(
    *,
    fighter: CreatureDefinition,
    barbarian: CreatureDefinition,
    monk: CreatureDefinition,
    enemy_definition_id: str,
) -> tuple[MappingProxyType, MappingProxyType]:
    """Return the narrow L2 records and their staged public setups.

    The build deliberately advances one accepted Bear Barbarian.  It neither
    alters nor relabels the other ten accepted level-1 Barbarian builds.
    """

    fighter_l2 = _level_two(
        fighter,
        definition_id="fighter_m_level_2_sudden_charge",
        name="Level 2 Melee Fighter M (Sudden Charge)",
        hp=34,
        class_feat="Sudden Charge",
        skill_feat="Quick Jump",
        ability_id="sudden_charge",
        note=(
            "Level 2: HP rises from 21 to 34 (Fighter 10 + Constitution 3); all level-based "
            "statistics rise by one. Sudden Charge is the selected Fighter class-feat option: "
            "two actions, flourish, two Strides, then an optional melee Strike. Quick Jump is "
            "a separately tracked skill-feat choice. Sources: https://2e.aonprd.com/Classes.aspx?ID=35; "
            "https://2e.aonprd.com/Feats.aspx?ID=4774; https://2e.aonprd.com/Feats.aspx?ID=5196."
        ),
    )
    barbarian_l2 = _level_two(
        barbarian,
        definition_id="barbarian_animal_bear_level_2_no_escape",
        name="Level 2 Animal Instinct Barbarian (Bear, No Escape)",
        hp=38,
        class_feat="No Escape",
        skill_feat="Quick Jump",
        ability_id="no_escape",
        note=(
            "Level 2: HP rises from 23 to 38 (Barbarian 12 + Constitution 3); all level-based "
            "statistics rise by one. No Escape is the selected reaction class feat while raging; "
            "it follows a moving enemy while maintaining reach. Quick Jump is a separate skill-feat "
            "choice. Sources: https://2e.aonprd.com/Classes.aspx?ID=57; "
            "https://2e.aonprd.com/Feats.aspx?ID=5815; https://2e.aonprd.com/Feats.aspx?ID=5196."
        ),
    )
    # This is an alternate legal Barbarian class-feat selection, not a second
    # required representative.  It deliberately reuses Fighter's source-legal
    # Sudden Charge contract, giving the first-wave movement hook two real
    # class adopters without manufacturing a generic martial activity system.
    barbarian_sudden_charge_l2 = _level_two(
        barbarian,
        definition_id="barbarian_animal_bear_level_2_sudden_charge",
        name="Level 2 Animal Instinct Barbarian (Bear, Sudden Charge)",
        hp=38,
        class_feat="Sudden Charge",
        skill_feat="Quick Jump",
        ability_id="sudden_charge",
        note=(
            "Alternate level-2 class-feat choice: Sudden Charge is a two-action flourish that "
            "uses two Strides and may make one melee Strike at the end. It is a legal level-1 "
            "Barbarian feat selected in the level-2 class-feat slot and shares the admitted Fighter "
            "movement contract. This alternate does not replace the selected No Escape representative. "
            "Sources: https://2e.aonprd.com/Feats.aspx?ID=4774; "
            "https://2e.aonprd.com/Classes.aspx?ID=57."
        ),
    )
    # Intimidating Strike is a level-2 Fighter and Barbarian feat.  These are
    # legal alternate class-feat choices, not replacements for the accepted
    # Sudden Charge and No Escape representatives.
    fighter_intimidating_strike_l2 = _level_two(
        fighter,
        definition_id="fighter_m_level_2_intimidating_strike",
        name="Level 2 Melee Fighter M (Intimidating Strike)",
        hp=34,
        class_feat="Intimidating Strike",
        skill_feat="Quick Jump",
        ability_id="intimidating_strike",
        note=(
            "Alternate level-2 Fighter class-feat choice: Intimidating Strike is a two-action "
            "melee Strike. If it hits and deals damage, its target is frightened 1, or frightened "
            "2 on a critical hit. It has the emotion, fear, and mental traits; an effect immune to "
            "fear, emotion, mental, or frightened is not silently bypassed. Source: https://2e.aonprd.com/Feats.aspx?ID=4782."
        ),
    )
    barbarian_intimidating_strike_l2 = _level_two(
        barbarian,
        definition_id="barbarian_animal_bear_level_2_intimidating_strike",
        name="Level 2 Animal Instinct Barbarian (Bear, Intimidating Strike)",
        hp=38,
        class_feat="Intimidating Strike",
        skill_feat="Quick Jump",
        ability_id="intimidating_strike",
        note=(
            "Alternate level-2 Barbarian class-feat choice: Intimidating Strike is a two-action "
            "melee Strike. If it hits and deals damage, its target is frightened 1, or frightened "
            "2 on a critical hit. This shares the admitted Fighter procedure while remaining a "
            "separate legal Barbarian choice. Source: https://2e.aonprd.com/Feats.aspx?ID=4782."
        ),
    )
    monk_l2 = _level_two(
        monk,
        definition_id="monk_monastic_weaponry_level_2_stunning_blows",
        name="Level 2 Monk (Monastic Weaponry, Stunning Blows)",
        hp=32,
        class_feat="Stunning Blows",
        skill_feat="Assurance (Athletics)",
        ability_id="stunning_blows",
        note=(
            "Level 2: HP rises from 20 to 32 (Monk 10 + Constitution 2); all level-based "
            "statistics rise by one. Stunning Blows applies only after a same-target Flurry meets "
            "its hit/damage condition; the target then makes the printed Fortitude save against the "
            "Monk class DC. Assurance (Athletics) is a separate skill-feat choice. Horizontal "
            "movement remains the only admitted Monk movement scope. Sources: "
            "https://2e.aonprd.com/Classes.aspx?ID=60; https://2e.aonprd.com/Feats.aspx?ID=5989; "
            "https://2e.aonprd.com/Feats.aspx?ID=5121."
        ),
    )
    definitions = MappingProxyType({
        fighter_l2.definition_id: fighter_l2,
        fighter_intimidating_strike_l2.definition_id: fighter_intimidating_strike_l2,
        barbarian_l2.definition_id: barbarian_l2,
        barbarian_sudden_charge_l2.definition_id: barbarian_sudden_charge_l2,
        barbarian_intimidating_strike_l2.definition_id: barbarian_intimidating_strike_l2,
        monk_l2.definition_id: monk_l2,
    })
    setups = MappingProxyType({
        "staged_fighter_level_2_sudden_charge": EncounterSetup(
            "staged_fighter_level_2_sudden_charge",
            "Staged Level 2 Fighter Sudden Charge",
            7,
            3,
            (
                CreaturePlacement("fighter", fighter_l2.definition_id, "Level 2 Fighter", "blue", Position(0, 1)),
                CreaturePlacement("dog", enemy_definition_id, "Guard Dog", "red", Position(5, 1)),
            ),
        ),
        "staged_fighter_level_2_intimidating_strike": EncounterSetup(
            "staged_fighter_level_2_intimidating_strike",
            "Staged Level 2 Fighter Intimidating Strike",
            5,
            3,
            (
                CreaturePlacement("fighter", fighter_intimidating_strike_l2.definition_id, "Level 2 Fighter", "blue", Position(1, 1)),
                CreaturePlacement("dog", enemy_definition_id, "Guard Dog", "red", Position(2, 1)),
            ),
        ),
        "staged_barbarian_level_2_no_escape": EncounterSetup(
            "staged_barbarian_level_2_no_escape",
            "Staged Level 2 Barbarian No Escape",
            7,
            3,
            (
                CreaturePlacement("barbarian", barbarian_l2.definition_id, "Level 2 Barbarian", "blue", Position(2, 1)),
                CreaturePlacement("dog", enemy_definition_id, "Guard Dog", "red", Position(3, 1)),
            ),
        ),
        "staged_barbarian_level_2_sudden_charge": EncounterSetup(
            "staged_barbarian_level_2_sudden_charge",
            "Staged Level 2 Barbarian Sudden Charge",
            7,
            3,
            (
                CreaturePlacement(
                    "barbarian", barbarian_sudden_charge_l2.definition_id,
                    "Level 2 Barbarian", "blue", Position(0, 1),
                ),
                CreaturePlacement("dog", enemy_definition_id, "Guard Dog", "red", Position(5, 1)),
            ),
        ),
        "staged_barbarian_level_2_intimidating_strike": EncounterSetup(
            "staged_barbarian_level_2_intimidating_strike",
            "Staged Level 2 Barbarian Intimidating Strike",
            5,
            3,
            (
                CreaturePlacement("barbarian", barbarian_intimidating_strike_l2.definition_id, "Level 2 Barbarian", "blue", Position(1, 1)),
                CreaturePlacement("dog", enemy_definition_id, "Guard Dog", "red", Position(2, 1)),
            ),
        ),
        "staged_monk_level_2_stunning_blows": EncounterSetup(
            "staged_monk_level_2_stunning_blows",
            "Staged Level 2 Monk Stunning Blows",
            5,
            3,
            (
                CreaturePlacement("monk", monk_l2.definition_id, "Level 2 Monk", "blue", Position(1, 1)),
                CreaturePlacement("dog", enemy_definition_id, "Guard Dog", "red", Position(2, 1)),
            ),
        ),
    })
    return definitions, setups
