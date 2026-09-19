"""Fixed level-2 sheets for the selected horizontal-movement bundle.

The integration owner imports these fixed definitions and setups into the
normal local catalog. Tests also use their literal records for focused
source-to-play probes.

Rules checked 2026-09-18:

* Rogue progression and Mobility: https://2e.aonprd.com/Classes.aspx?ID=37;
  https://2e.aonprd.com/Feats.aspx?ID=4926
* Swashbuckler progression: https://2e.aonprd.com/Classes.aspx?ID=63
* Quick Jump: https://2e.aonprd.com/Feats.aspx?ID=5196
* Tumble Behind: https://2e.aonprd.com/Feats.aspx?ID=6142
"""

from __future__ import annotations

from dataclasses import replace
from types import MappingProxyType

from .model import AttackDefinition, CreatureDefinition, CreaturePlacement, EncounterSetup, Position
from .rogue_content import ROGUE_THIEF_PLAYABLE
from .swashbuckler_content import BRAGGART_SWASHBUCKLER


def _level_attack(attack: AttackDefinition) -> AttackDefinition:
    """Apply the ordinary level increase while preserving sheet weapon facts."""

    return replace(attack, modifier=attack.modifier + 1)


def _level_skills(
    definition: CreatureDefinition, *, expert_skill: str | None = None
) -> tuple[tuple[str, str, int], ...]:
    upgraded: list[tuple[str, str, int]] = []
    for name, rank, modifier in definition.skills:
        if name == expert_skill:
            if rank != "trained":
                raise ValueError(f"{definition.definition_id} must be trained in {name} before the level-2 increase")
            upgraded.append((name, "expert", modifier + 3))
        else:
            upgraded.append((name, rank, modifier + 1))
    return tuple(upgraded)


def _level_saves(definition: CreatureDefinition) -> tuple[tuple[str, str, int], ...]:
    return tuple((name, rank, modifier + 1) for name, rank, modifier in definition.saves)


def _level_two(
    definition: CreatureDefinition,
    *,
    definition_id: str,
    name: str,
    hp: int,
    class_feat: str,
    skill_feat: str,
    expert_skill: str | None = None,
    note: str,
) -> CreatureDefinition:
    return replace(
        definition,
        definition_id=definition_id,
        name=name,
        hp=hp,
        ac=definition.ac + 1,
        perception=definition.perception + 1,
        attacks=tuple(_level_attack(attack) for attack in definition.attacks),
        feats=definition.feats + (class_feat, skill_feat),
        skills=_level_skills(definition, expert_skill=expert_skill),
        saves=_level_saves(definition),
        level=2,
        class_dc=definition.class_dc + 1,
        sheet_notes=definition.sheet_notes + (note,),
    )


THIEF_ROGUE_LEVEL_2 = _level_two(
    ROGUE_THIEF_PLAYABLE,
    definition_id="rogue_thief_warrior_level_2_mobility",
    name="Level 2 Thief Rogue (Warrior, Mobility)",
    hp=28,
    class_feat="Mobility",
    skill_feat="Quick Jump",
    expert_skill="athletics",
    note=(
        "Level 2: Mobility is the Rogue feat; Quick Jump is the level-2 skill feat; "
        "Athletics advances trained +5 to expert +8. HP advances 18 to 28; all other "
        "level-based modifiers increase by one. Mobility applies only to a validated "
        "Stride of half actual Speed or less, and this flat-map slice excludes its Climb, "
        "Fly, and Swim alternatives. Sources: https://2e.aonprd.com/Classes.aspx?ID=37; "
        "https://2e.aonprd.com/Feats.aspx?ID=4926; https://2e.aonprd.com/Feats.aspx?ID=5196"
    ),
)


BRAGGART_SWASHBUCKLER_LEVEL_2 = _level_two(
    BRAGGART_SWASHBUCKLER,
    definition_id="swashbuckler_braggart_level_2_tumble_behind",
    name="Level 2 Braggart Swashbuckler (Flying Blade, Tumble Behind)",
    hp=30,
    class_feat="Tumble Behind",
    skill_feat="Quick Jump",
    note=(
        "Level 2: Tumble Behind is the Swashbuckler feat and Quick Jump is the level-2 "
        "skill feat. HP advances 19 to 30; all existing level-based modifiers increase "
        "by one. A successful Tumble Through makes only that target off-guard to this "
        "Swashbuckler's next attack before this turn ends, including the selected Flying "
        "Blade thrown finisher; it is a separate one-use exposure, not a Feint effect. "
        "Sources: https://2e.aonprd.com/Classes.aspx?ID=63; "
        "https://2e.aonprd.com/Feats.aspx?ID=5196; "
        "https://2e.aonprd.com/Feats.aspx?ID=6142"
    ),
)


L2_HORIZONTAL_DEFINITIONS = MappingProxyType(
    {
        THIEF_ROGUE_LEVEL_2.definition_id: THIEF_ROGUE_LEVEL_2,
        BRAGGART_SWASHBUCKLER_LEVEL_2.definition_id: BRAGGART_SWASHBUCKLER_LEVEL_2,
    }
)


# These compact public-play setups remain beside their definition records so
# the catalog import and focused tests share one literal layout.
THIEF_ROGUE_LEVEL_2_MOBILITY_SETUP = EncounterSetup(
    "l2_thief_rogue_mobility_vs_reactive_fighter",
    "Level 2 Thief Rogue Mobility through Reactive Reach",
    5,
    3,
    (
        CreaturePlacement("thief", THIEF_ROGUE_LEVEL_2.definition_id, "Thief Rogue", "blue", Position(0, 0)),
        CreaturePlacement("fighter", "fighter_m_level_1", "Reactive Fighter", "red", Position(1, 1)),
    ),
)


BRAGGART_SWASHBUCKLER_LEVEL_2_TUMBLE_BEHIND_SETUP = EncounterSetup(
    "l2_braggart_tumble_behind_vs_guard_dog",
    "Level 2 Braggart Tumble Behind and Flying Blade",
    4,
    3,
    (
        CreaturePlacement("braggart", BRAGGART_SWASHBUCKLER_LEVEL_2.definition_id, "Braggart Swashbuckler", "blue", Position(0, 1)),
        CreaturePlacement("braggart_dog", "guard_dog_mc2924", "Guard Dog", "red", Position(1, 1)),
    ),
)


L2_HORIZONTAL_SETUPS = MappingProxyType(
    {
        THIEF_ROGUE_LEVEL_2_MOBILITY_SETUP.setup_id: THIEF_ROGUE_LEVEL_2_MOBILITY_SETUP,
        BRAGGART_SWASHBUCKLER_LEVEL_2_TUMBLE_BEHIND_SETUP.setup_id: BRAGGART_SWASHBUCKLER_LEVEL_2_TUMBLE_BEHIND_SETUP,
    }
)
