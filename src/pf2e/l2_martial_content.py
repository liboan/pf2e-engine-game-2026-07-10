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

from .model import AttackDefinition, CreatureDefinition, CreaturePlacement, EncounterSetup, Position


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
    fighter_dueling_parry_l2 = _level_two(
        fighter,
        definition_id="fighter_m_level_2_dueling_parry",
        name="Level 2 Melee Fighter M (Dueling Parry)",
        hp=34,
        class_feat="Dueling Parry",
        skill_feat="Quick Jump",
        ability_id="dueling_parry",
        note=(
            "Alternate level-2 Fighter class-feat choice: while wielding only one held one-handed "
            "melee weapon, Dueling Parry grants +2 circumstance AC until the start of the next "
            "turn, and the guard ends mechanically if that hand requirement is not retained. "
            "Source: https://2e.aonprd.com/Feats.aspx?ID=4781."
        ),
    )
    fighter_snagging_strike_l1 = replace(
        fighter,
        definition_id="fighter_m_level_1_snagging_strike",
        name="Level 1 Melee Fighter M (Snagging Strike)",
        abilities=tuple(ability for ability in fighter.abilities if ability != "vicious_swing") + ("snagging_strike",),
        feats=tuple(feat for feat in fighter.feats if feat != "Vicious Swing") + ("Snagging Strike",),
        sheet_notes=(*fighter.sheet_notes, (
            "Alternate level-1 Fighter class-feat choice: Snagging Strike is a one-action melee Strike while one hand remains free and the target is within that hand's reach. On a hit, the target is off-guard until the start of the Fighter's next turn or it leaves that reach. Source: https://2e.aonprd.com/Feats.aspx?ID=4773."
        )),
    )
    fighter_combat_grab_l2 = _level_two(
        fighter,
        definition_id="fighter_m_level_2_combat_grab",
        name="Level 2 Melee Fighter M (Combat Grab)",
        hp=34,
        class_feat="Combat Grab",
        skill_feat="Quick Jump",
        ability_id="combat_grab",
        note=(
            "Alternate level-2 Fighter class-feat choice: Combat Grab is a one-action Press melee Strike with a free hand. On a hit, the target is grabbed until the end of the Fighter's next turn or it Escapes. Source: https://2e.aonprd.com/Feats.aspx?ID=4780."
        ),
    )
    fighter_brutish_shove_l2 = _level_two(
        replace(
            fighter,
            attacks=(*(
                attack for attack in fighter.attacks if attack.attack_id != "longsword"
            ), AttackDefinition(
                "greatsword", "Greatsword", 9, 5,
                frozenset({"attack", "melee", "versatile-p"}), "slashing", (12,), 4,
                item_id="greatsword", hands_required=2,
            )),
            held_items=("greatsword",),
        ),
        definition_id="fighter_m_level_2_brutish_shove",
        name="Level 2 Melee Fighter M (Brutish Shove)",
        hp=34,
        class_feat="Brutish Shove",
        skill_feat="Quick Jump",
        ability_id="brutish_shove",
        note=(
            "Alternate level-2 Fighter class-feat choice: Brutish Shove is a one-action Press Greatsword Strike; Greatsword is a held two-handed martial weapon (1d12 slashing; versatile piercing). On a hit against a target the Fighter's size or smaller, it makes an automatic Shove; on a failure (or the selected failure effect), it leaves the target off-guard until the end of the Fighter's turn. Sources: https://2e.aonprd.com/Feats.aspx?ID=4779; https://2e.aonprd.com/Weapons.aspx?ID=379."
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
    monk_crane_stance = replace(
        monk,
        definition_id="monk_crane_stance_level_1",
        name="Level 1 Monk (Crane Stance)",
        attacks=(*(
            attack for attack in monk.attacks if attack.item_id != "kama"
        ), AttackDefinition(
            "crane_wing", "Crane Wing", 7, 5,
            frozenset({"attack", "melee", "agile", "finesse", "nonlethal", "unarmed"}),
            "bludgeoning", (6,), 2,
            attack_attribute="dexterity", damage_attribute="strength", hands_required=0,
        )),
        abilities=tuple(ability for ability in monk.abilities if ability != "monastic_weaponry") + ("crane_stance",),
        feats=tuple(feat for feat in monk.feats if feat != "Monastic Weaponry") + ("Crane Stance",),
        proficiencies=tuple(
            proficiency for proficiency in monk.proficiencies
            if proficiency[0] != "simple_and_martial_monk_weapons"
        ),
        held_items=(),
        sheet_notes=(*(
            note for note in monk.sheet_notes
            if "Monastic Weaponry" not in note and "Feats.aspx?ID=5979" not in note
        ), (
            "Alternate level-1 class-feat choice: Crane Stance is a one-action stance while "
            "unarmored. It grants +1 circumstance AC and limits Strikes to Crane Wing (1d6 "
            "bludgeoning; agile, finesse, nonlethal, unarmed). It reduces horizontal Quick "
            "Jump's Long Jump DC by 5 and increases the supported horizontal Leap distance by "
            "5 feet; vertical High Jump terrain remains unsupported. The stance ends on knockout, "
            "dismissal, encounter end, or another stance action. Source: "
            "https://2e.aonprd.com/Feats.aspx?ID=5976."
        )),
    )
    definitions = MappingProxyType({
        fighter_l2.definition_id: fighter_l2,
        fighter_intimidating_strike_l2.definition_id: fighter_intimidating_strike_l2,
        fighter_dueling_parry_l2.definition_id: fighter_dueling_parry_l2,
        fighter_snagging_strike_l1.definition_id: fighter_snagging_strike_l1,
        fighter_combat_grab_l2.definition_id: fighter_combat_grab_l2,
        fighter_brutish_shove_l2.definition_id: fighter_brutish_shove_l2,
        barbarian_l2.definition_id: barbarian_l2,
        barbarian_sudden_charge_l2.definition_id: barbarian_sudden_charge_l2,
        barbarian_intimidating_strike_l2.definition_id: barbarian_intimidating_strike_l2,
        monk_l2.definition_id: monk_l2,
        monk_crane_stance.definition_id: monk_crane_stance,
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
        "staged_fighter_level_2_dueling_parry": EncounterSetup(
            "staged_fighter_level_2_dueling_parry",
            "Staged Level 2 Fighter Dueling Parry",
            5,
            3,
            (
                CreaturePlacement("fighter", fighter_dueling_parry_l2.definition_id, "Level 2 Fighter", "blue", Position(1, 1)),
                CreaturePlacement("dog", enemy_definition_id, "Guard Dog", "red", Position(2, 1)),
            ),
        ),
        "staged_fighter_level_1_snagging_strike": EncounterSetup(
            "staged_fighter_level_1_snagging_strike", "Staged Level 1 Fighter Snagging Strike", 5, 3,
            (CreaturePlacement("fighter", fighter_snagging_strike_l1.definition_id, "Level 1 Fighter", "blue", Position(1, 1)), CreaturePlacement("dog", enemy_definition_id, "Guard Dog", "red", Position(2, 1))),
        ),
        "staged_fighter_level_2_combat_grab": EncounterSetup(
            "staged_fighter_level_2_combat_grab", "Staged Level 2 Fighter Combat Grab", 5, 3,
            (CreaturePlacement("fighter", fighter_combat_grab_l2.definition_id, "Level 2 Fighter", "blue", Position(1, 1)), CreaturePlacement("dog", enemy_definition_id, "Guard Dog", "red", Position(2, 1))),
        ),
        "staged_fighter_level_2_brutish_shove": EncounterSetup(
            "staged_fighter_level_2_brutish_shove", "Staged Level 2 Fighter Brutish Shove", 6, 3,
            (CreaturePlacement("fighter", fighter_brutish_shove_l2.definition_id, "Level 2 Fighter", "blue", Position(1, 1)), CreaturePlacement("dog", enemy_definition_id, "Guard Dog", "red", Position(2, 1))),
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
        "staged_monk_crane_stance": EncounterSetup(
            "staged_monk_crane_stance",
            "Staged Level 1 Monk Crane Stance",
            5,
            3,
            (
                CreaturePlacement("monk", monk_crane_stance.definition_id, "Crane Monk", "blue", Position(1, 1)),
                CreaturePlacement("dog", enemy_definition_id, "Guard Dog", "red", Position(2, 1)),
            ),
        ),
    })
    return definitions, setups
