"""W4 lane 2: defensive, mobility, and skill-linked level-one feats.

Sources checked 2026-09-20:

* Reactive Shield: https://2e.aonprd.com/Feats.aspx?ID=4772
* Point Blank Stance: https://2e.aonprd.com/Feats.aspx?ID=4771
* Overextending Feint: https://2e.aonprd.com/Feats.aspx?ID=4917
* You're Next: https://2e.aonprd.com/Feats.aspx?ID=4922
"""

from dataclasses import replace

from .model import CreatureDefinition, CreaturePlacement, EncounterSetup, Position


def _setup(setup_id: str, name: str, definition: CreatureDefinition, enemy_id: str) -> EncounterSetup:
    return EncounterSetup(
        setup_id=setup_id,
        name=name,
        width=5,
        height=3,
        placements=(
            CreaturePlacement("w4_actor", definition.definition_id, definition.name, "blue", Position(1, 1)),
            CreaturePlacement("w4_enemy", enemy_id, "Guard Dog", "red", Position(2, 1)),
        ),
    )


def build_w4_defensive_content(
    *, fighter: CreatureDefinition, shield_fighter: CreatureDefinition,
    ranged_fighter: CreatureDefinition, rogue: CreatureDefinition, enemy_id: str,
) -> tuple[tuple[CreatureDefinition, ...], tuple[EncounterSetup, ...]]:
    reactive_shield = replace(
        shield_fighter,
        definition_id="w4_fighter_reactive_shield_level_1",
        name="W4 Level 1 Fighter (Reactive Shield)",
        abilities=tuple(ability for ability in shield_fighter.abilities if ability != "vicious_swing") + ("reactive_shield",),
        feats=tuple("Reactive Shield" if feat == "Vicious Swing" else feat for feat in shield_fighter.feats),
        sheet_notes=(*shield_fighter.sheet_notes, "W4 lane 2: Reactive Shield is the selected level-1 class feat."),
    )
    point_blank = replace(
        ranged_fighter,
        definition_id="w4_fighter_point_blank_stance_level_1",
        name="W4 Level 1 Fighter (Point Blank Stance)",
        abilities=tuple(ability for ability in ranged_fighter.abilities if ability != "vicious_swing") + ("point_blank_stance",),
        feats=tuple("Point Blank Stance" if feat == "Vicious Swing" else feat for feat in ranged_fighter.feats),
        sheet_notes=(*ranged_fighter.sheet_notes, "W4 lane 2: Point Blank Stance is the selected level-1 class feat."),
    )
    overextending = replace(
        rogue,
        definition_id="w4_rogue_overextending_feint_level_1",
        name="W4 Level 1 Rogue (Overextending Feint)",
        abilities=(*rogue.abilities, "overextending_feint"),
        feats=tuple("Overextending Feint" if feat == "Nimble Dodge" else feat for feat in rogue.feats),
        sheet_notes=(*rogue.sheet_notes, "W4 lane 2: Overextending Feint is the selected level-1 class feat."),
    )
    youre_next = replace(
        rogue,
        definition_id="w4_rogue_youre_next_level_1",
        name="W4 Level 1 Rogue (You're Next)",
        abilities=(*rogue.abilities, "youre_next"),
        feats=tuple("You're Next" if feat == "Nimble Dodge" else feat for feat in rogue.feats),
        sheet_notes=(*rogue.sheet_notes, "W4 lane 2: You're Next is the selected level-1 class feat."),
    )
    definitions = (reactive_shield, point_blank, overextending, youre_next)
    setups = (
        _setup("w4_reactive_shield_vs_guard_dog", "W4 Reactive Shield Fighter versus Guard Dog", reactive_shield, enemy_id),
        _setup("w4_point_blank_stance_vs_guard_dog", "W4 Point Blank Stance Fighter versus Guard Dog", point_blank, enemy_id),
        _setup("w4_overextending_feint_vs_guard_dog", "W4 Overextending Feint Rogue versus Guard Dog", overextending, enemy_id),
        _setup("w4_youre_next_vs_guard_dog", "W4 You're Next Rogue versus Guard Dog", youre_next, enemy_id),
        EncounterSetup(
            setup_id="w4_youre_next_vs_two_guard_dogs",
            name="W4 You're Next Rogue versus Two Guard Dogs",
            width=7,
            height=3,
            placements=(
                CreaturePlacement("w4_actor", youre_next.definition_id, youre_next.name, "blue", Position(1, 1)),
                CreaturePlacement("w4_enemy_a", enemy_id, "Guard Dog A", "red", Position(2, 1)),
                CreaturePlacement("w4_enemy_b", enemy_id, "Guard Dog B", "red", Position(3, 1)),
            ),
        ),
    )
    return definitions, setups
