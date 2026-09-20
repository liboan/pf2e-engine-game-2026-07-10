"""Finite W4 offensive class-feat sheets and public fixtures."""

from dataclasses import replace

from .model import AttackDefinition, CreatureDefinition, CreaturePlacement, EncounterSetup, Position


def _shortsword(*, modifier: int, damage_modifier: int) -> AttackDefinition:
    return AttackDefinition(
        attack_id="shortsword", name="Shortsword", modifier=modifier, reach_ft=5,
        traits=frozenset({"attack", "melee", "agile", "finesse", "weapon"}),
        damage_type="piercing", damage_dice=(6,), damage_modifier=damage_modifier,
        item_id="shortsword", attack_attribute="dexterity", damage_attribute="dexterity",
        hands_required=1,
    )


def build_w4_offensive_content(
    *, fighter: CreatureDefinition, ranger: CreatureDefinition, rogue: CreatureDefinition,
    enemy_definition_id: str,
) -> tuple[dict[str, CreatureDefinition], tuple[EncounterSetup, ...]]:
    exacting = replace(
        fighter, definition_id="w4_fighter_exacting_strike_level_1",
        name="Level 1 Fighter (Exacting Strike)",
        abilities=tuple(item for item in fighter.abilities if item != "vicious_swing") + ("exacting_strike",),
        feats=tuple("Exacting Strike" if item == "Vicious Swing" else item for item in fighter.feats),
        sheet_notes=(*fighter.sheet_notes,
                     "W4 selected class feat: Exacting Strike. On an ordinary failure its Strike does not increase MAP; critical failures still count.",
                     "Source: https://2e.aonprd.com/Feats.aspx?ID=357"),
    )
    double_slice = replace(
        fighter, definition_id="w4_fighter_double_slice_level_1",
        name="Level 1 Fighter (Double Slice)",
        attacks=fighter.attacks + (_shortsword(modifier=9, damage_modifier=4),),
        held_items=("longsword", "shortsword"),
        abilities=tuple(item for item in fighter.abilities if item != "vicious_swing") + ("double_slice",),
        feats=tuple("Double Slice" if item == "Vicious Swing" else item for item in fighter.feats),
        sheet_notes=(*fighter.sheet_notes,
                     "W4 selected class feat: Double Slice. The finite fixture holds a longsword and shortsword; each one-handed melee Strike is selected through the paired action.",
                     "Source: https://2e.aonprd.com/Feats.aspx?ID=356"),
    )
    ranger_twin = replace(
        ranger, definition_id="w4_ranger_twin_takedown_level_1",
        name="Level 1 Ranger (Twin Takedown)",
        attacks=tuple(item for item in ranger.attacks if item.attack_id != "fist") + (
            _shortsword(modifier=7, damage_modifier=1),
            replace(_shortsword(modifier=7, damage_modifier=1), attack_id="dagger", name="Dagger", damage_dice=(4,), item_id="dagger"),
        ),
        held_items=("shortsword", "dagger"),
        stowed_items=("shortbow",),
        abilities=(*ranger.abilities, "twin_takedown"),
        feats=(*ranger.feats, "Twin Takedown"),
        sheet_notes=(*ranger.sheet_notes,
                     "W4 selected class feat: Twin Takedown. The finite combat sheet holds a shortsword and dagger for two melee prey Strikes; the bow is stowed in this fixture.",
                     "Source: https://2e.aonprd.com/Feats.aspx?ID=494"),
    )
    rogue_twin = replace(
        rogue, definition_id="w4_rogue_twin_feint_level_1",
        name="Level 1 Rogue (Twin Feint)",
        attacks=rogue.attacks + (
            replace(_shortsword(modifier=7, damage_modifier=4), attack_id="dagger", name="Dagger", damage_dice=(4,), traits=frozenset({"attack", "melee", "agile", "finesse", "thrown", "weapon"}), damage_type="piercing"),
        ),
        held_items=("shortsword", "dagger"),
        abilities=(*rogue.abilities, "twin_feint"),
        feats=(*rogue.feats, "Twin Feint"),
        sheet_notes=(*rogue.sheet_notes,
                     "W4 selected class feat: Twin Feint. The finite fixture holds a shortsword and dagger and exposes two different agile/finesse melee Strikes; the second attack gets the feat's automatic off-guard benefit.",
                     "Source: https://2e.aonprd.com/Feats.aspx?ID=552"),
    )
    definitions = {item.definition_id: item for item in (exacting, double_slice, ranger_twin, rogue_twin)}
    setups = (
        EncounterSetup(
            "w4_fighter_exacting_strike_vs_guard_dog", "W4 Fighter Exacting Strike", 5, 3,
            (CreaturePlacement("fighter", exacting.definition_id, "Exacting Fighter", "blue", Position(1, 1)),
             CreaturePlacement("dog", enemy_definition_id, "Guard Dog", "red", Position(2, 1))),
        ),
        EncounterSetup(
            "w4_fighter_double_slice_vs_guard_dog", "W4 Fighter Double Slice", 5, 3,
            (CreaturePlacement("fighter", double_slice.definition_id, "Double-Slice Fighter", "blue", Position(1, 1)),
             CreaturePlacement("dog", enemy_definition_id, "Guard Dog", "red", Position(2, 1))),
        ),
        EncounterSetup(
            "w4_ranger_twin_takedown_vs_guard_dog", "W4 Ranger Twin Takedown", 5, 3,
            (CreaturePlacement("ranger", ranger_twin.definition_id, "Twin-Takedown Ranger", "blue", Position(1, 1)),
             CreaturePlacement("dog", enemy_definition_id, "Guard Dog", "red", Position(2, 1))),
        ),
        EncounterSetup(
            "w4_rogue_twin_feint_vs_guard_dog", "W4 Rogue Twin Feint", 5, 3,
            (CreaturePlacement("rogue", rogue_twin.definition_id, "Twin-Feint Rogue", "blue", Position(1, 1)),
             CreaturePlacement("dog", enemy_definition_id, "Guard Dog", "red", Position(2, 1))),
        ),
    )
    return definitions, setups
