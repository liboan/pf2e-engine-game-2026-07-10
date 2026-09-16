"""Staged first-family definitions and fixtures, outside the picker.

The runtime's ``CREATURES`` and ``SETUPS`` maps stay limited to supported
content. The accepted Bear Barbarian and its focused fixtures live in those
runtime maps; these constants preserve the remaining staged fixtures and
source profiles without making them available to encounter startup.
"""

from __future__ import annotations

from types import MappingProxyType
from typing import Mapping

from .barbarian_content import (
    BARBARIAN_SAMPLE_CHARACTERS,
)
from .model import CreatureDefinition, CreaturePlacement, EncounterSetup, Position
from .opponent_content import PUBLISHED_OPPONENT_DEFINITIONS
from .ranger_monk_content import RANGER_MONK_DEFINITIONS, RANGER_MONK_SETUPS
from .skill_content import DEMORALIZE, ESCAPE, GRAPPLE, TRIP


_animal_barbarian_id = BARBARIAN_SAMPLE_CHARACTERS["animal"].definition.definition_id
_precision_ranger_id = next(
    definition_id
    for definition_id, definition in RANGER_MONK_DEFINITIONS.items()
    if "hunter_edge_precision" in definition.abilities
)
_monk_definition_id = next(
    definition_id
    for definition_id, definition in RANGER_MONK_DEFINITIONS.items()
    if definition.class_name == "Monk"
)


# All actors begin at the published/fixed maximum HP and without injected
# damage or conditions.  The map is a compact, mixed-party starting point,
# not a generated encounter family.
FIRST_FAMILIES_UNDEAD_STARTER = EncounterSetup(
    setup_id="s3i_first_families_undead_starter",
    name="First Families against Skeletons and a Zombie",
    width=7,
    height=5,
    placements=(
        CreaturePlacement("animal_barbarian", _animal_barbarian_id, "Wolf Instinct Barbarian", "blue", Position(1, 0)),
        CreaturePlacement("precision_ranger", _precision_ranger_id, "Precision Ranger", "blue", Position(1, 2)),
        CreaturePlacement("monk", _monk_definition_id, "Monk", "blue", Position(1, 4)),
        CreaturePlacement("skeleton_a", "skeleton_guard_mc3193", "Skeleton Guard A", "red", Position(5, 0)),
        CreaturePlacement("zombie", "zombie_shambler_mc3249", "Zombie Shambler", "red", Position(5, 2)),
        CreaturePlacement("skeleton_b", "skeleton_guard_mc3193", "Skeleton Guard B", "red", Position(5, 4)),
    ),
)


EXPANSION_CREATURES: Mapping[str, CreatureDefinition] = MappingProxyType(
    {
        **RANGER_MONK_DEFINITIONS,
        **PUBLISHED_OPPONENT_DEFINITIONS,
    }
)

EXPANSION_INITIAL_STATES = MappingProxyType({})

EXPANSION_SETUPS: Mapping[str, EncounterSetup] = MappingProxyType(
    {
        **{setup.setup_id: setup for setup in RANGER_MONK_SETUPS},
        FIRST_FAMILIES_UNDEAD_STARTER.setup_id: FIRST_FAMILIES_UNDEAD_STARTER,
    }
)

EXPANSION_SKILL_ACTIONS = MappingProxyType(
    {action.action_id: action for action in (TRIP, GRAPPLE, ESCAPE, DEMORALIZE)}
)
