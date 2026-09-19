"""Reviewed content facts for the explicitly admitted common skill actions.

This module contains only fixed action metadata. It does not decide whether a
creature is in reach, roll a check, spend actions, or apply effects; the named
procedures in :mod:`pf2e.skill_actions` do that from current encounter facts.

The initial action text was checked against the current Remaster entries on
Archives of Nethys and the current Paizo FAQ (including 2026 errata):

* Trip: https://2e.aonprd.com/Actions.aspx?ID=2382
* Grapple: https://2e.aonprd.com/Actions.aspx?ID=2376
* Escape: https://2e.aonprd.com/Rules.aspx?ID=2343
* Demoralize: https://2e.aonprd.com/Actions.aspx?ID=2395
* Maneuver weapon traits: https://2e.aonprd.com/Traits.aspx?ID=619
* Intimidating Glare: https://2e.aonprd.com/Feats.aspx?ID=5162
* Feint: https://2e.aonprd.com/Actions.aspx?ID=2390
* Tumble Through: https://2e.aonprd.com/Actions.aspx?ID=2370
* Current official errata: https://paizo.com/pathfinder/faq
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SkillActionContent:
    """Printed action facts used by a named handler, not a generic script."""

    action_id: str
    name: str
    action_cost: int
    check_skill: str
    target_dc: str
    traits: frozenset[str]
    source_url: str
    range_ft: int | None = None
    requires_aware_target: bool = False
    max_target_size_steps_larger: int | None = None
    free_hand_required: bool = False
    effect_kinds: tuple[str, ...] = ()
    immunity_duration_seconds: int = 0


TRIP = SkillActionContent(
    "trip",
    "Trip",
    1,
    "athletics",
    "reflex",
    frozenset({"attack"}),
    "https://2e.aonprd.com/Actions.aspx?ID=2382",
    max_target_size_steps_larger=1,
    free_hand_required=True,
    effect_kinds=("prone",),
)

GRAPPLE = SkillActionContent(
    "grapple",
    "Grapple",
    1,
    "athletics",
    "fortitude",
    frozenset({"attack"}),
    "https://2e.aonprd.com/Actions.aspx?ID=2376",
    max_target_size_steps_larger=1,
    free_hand_required=True,
    effect_kinds=("grabbed", "restrained"),
)

ESCAPE = SkillActionContent(
    "escape",
    "Escape",
    1,
    "unarmed_attack_or_acrobatics_or_athletics",
    "selected_impediment",
    frozenset({"attack"}),
    "https://2e.aonprd.com/Rules.aspx?ID=2343",
    effect_kinds=("grabbed", "immobilized", "restrained"),
)

DEMORALIZE = SkillActionContent(
    "demoralize",
    "Demoralize",
    1,
    "intimidation",
    "will",
    frozenset({"auditory", "concentrate", "emotion", "fear", "mental"}),
    "https://2e.aonprd.com/Actions.aspx?ID=2395",
    range_ft=30,
    requires_aware_target=True,
    effect_kinds=("frightened",),
    immunity_duration_seconds=600,
)

FEINT = SkillActionContent(
    "feint",
    "Feint",
    1,
    "deception",
    "perception",
    frozenset({"mental"}),
    "https://2e.aonprd.com/Actions.aspx?ID=2390",
    effect_kinds=("off_guard",),
)

TUMBLE_THROUGH = SkillActionContent(
    "tumble_through",
    "Tumble Through",
    1,
    "acrobatics",
    "reflex",
    frozenset({"bravado", "move"}),
    "https://2e.aonprd.com/Actions.aspx?ID=2370",
)

# Quick Jump modifies the ordinary two-action Long Jump.  The bounded engine
# represents its horizontal result only; elevated surfaces and High Jump are
# deliberately outside its flat encounter maps.
QUICK_JUMP = SkillActionContent(
    "quick_jump",
    "Quick Jump",
    1,
    "athletics",
    "long_jump_dc_15",
    frozenset({"move"}),
    "https://2e.aonprd.com/Feats.aspx?ID=5196",
)


# These are the size categories in ascending order. A maneuver target may be
# at most one category larger than its user under the base action.
SIZE_ORDER = ("tiny", "small", "medium", "large", "huge", "gargantuan")


def maneuver_target_size_allowed(user_size: str, target_size: str) -> bool:
    """Return whether the base Trip/Grapple size requirement is met."""

    if user_size not in SIZE_ORDER or target_size not in SIZE_ORDER:
        raise ValueError("maneuver size must be a supported PF2e size category")
    return SIZE_ORDER.index(target_size) - SIZE_ORDER.index(user_size) <= 1
