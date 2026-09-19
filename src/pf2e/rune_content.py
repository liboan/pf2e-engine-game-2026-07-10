"""Curated definitions for the first common fundamental rune grades.

Rune effects are attached to stable ``ItemInstance.rune_ids``. Item category
comes from this explicit catalog, never from an instance's display or stable
identity string. Selectable property runes are outside this first slice.
"""

from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Mapping

from .items import ArmorRuneProfile, ItemInstance, WeaponRuneProfile


_HANDWRAPS_SOURCE = "https://2e.aonprd.com/Equipment.aspx?ID=3086"


@dataclass(frozen=True)
class FundamentalRuneDefinition:
    rune_id: str
    category: str
    value: int
    source_url: str


WEAPON_POTENCY_1 = FundamentalRuneDefinition(
    "weapon_potency_1",
    "weapon_potency",
    1,
    "https://2e.aonprd.com/Equipment.aspx?ID=2830",
)
STRIKING = FundamentalRuneDefinition(
    "striking",
    "striking",
    2,
    "https://2e.aonprd.com/Equipment.aspx?ID=2829",
)
ARMOR_POTENCY_1 = FundamentalRuneDefinition(
    "armor_potency_1",
    "armor_potency",
    1,
    "https://2e.aonprd.com/Equipment.aspx?ID=2785",
)
RESILIENT = FundamentalRuneDefinition(
    "resilient",
    "resilient",
    1,
    "https://2e.aonprd.com/Equipment.aspx?ID=2786",
)

FUNDAMENTAL_RUNES: Mapping[str, FundamentalRuneDefinition] = MappingProxyType(
    {
        rune.rune_id: rune
        for rune in (WEAPON_POTENCY_1, STRIKING, ARMOR_POTENCY_1, RESILIENT)
    }
)

# These are the only ordinary equipment definitions currently admitted to
# receive fundamental rune attachments. Explicit IDs prevent the rules layer
# from guessing an item's category from its name.
ITEM_CATEGORIES: Mapping[str, str] = MappingProxyType(
    {
        "longsword": "weapon",
        "shortsword": "weapon",
        "leather_armor": "armor",
        "breastplate": "armor",
        "handwraps_of_mighty_blows": "handwraps",
        "steel_shield": "shield",
    }
)


def _runes_for_item(instance: ItemInstance, expected_category: str) -> tuple[FundamentalRuneDefinition, ...]:
    category = ITEM_CATEGORIES.get(instance.definition_id)
    if category is None:
        if instance.rune_ids:
            raise ValueError(f"item definition {instance.definition_id!r} cannot receive supported rune attachments")
        return ()
    if category not in {expected_category, "handwraps" if expected_category == "weapon" else expected_category}:
        if instance.rune_ids:
            raise ValueError(f"{category} item {instance.definition_id!r} cannot receive {expected_category} runes")
        return ()
    runes: list[FundamentalRuneDefinition] = []
    for rune_id in instance.rune_ids:
        rune = FUNDAMENTAL_RUNES.get(rune_id)
        if rune is None:
            raise ValueError(f"unsupported rune attachment {rune_id!r}")
        if rune.category not in ({"weapon_potency", "striking"} if expected_category == "weapon" else {"armor_potency", "resilient"}):
            raise ValueError(f"rune {rune_id!r} is incompatible with {category} item {instance.definition_id!r}")
        runes.append(rune)
    if len({rune.category for rune in runes}) != len(runes):
        raise ValueError("an item cannot have more than one supported rune of the same fundamental category")
    return tuple(runes)


def weapon_rune_profile_for_item(instance: ItemInstance) -> WeaponRuneProfile | None:
    """Resolve supported weapon runes from an item's explicit definition."""
    category = ITEM_CATEGORIES.get(instance.definition_id)
    if category not in {"weapon", "handwraps"}:
        if instance.rune_ids and category is None:
            _runes_for_item(instance, "weapon")
        return None
    runes = _runes_for_item(instance, "weapon")
    potency = next((rune.value for rune in runes if rune.category == "weapon_potency"), 0)
    striking_dice = next((rune.value for rune in runes if rune.category == "striking"), None)
    source_url_rows = ((_HANDWRAPS_SOURCE,) if category == "handwraps" else ()) + tuple(
        rune.source_url for rune in runes
    )
    source_urls = tuple(dict.fromkeys(source_url_rows))
    return WeaponRuneProfile(
        potency=potency,
        striking_dice=striking_dice,
        handwraps=category == "handwraps",
        source_urls=source_urls or WeaponRuneProfile(handwraps=category == "handwraps").source_urls,
    )


def armor_rune_profile_for_item(instance: ItemInstance) -> ArmorRuneProfile | None:
    """Resolve armor rune values without deciding whether the armor is active."""
    if ITEM_CATEGORIES.get(instance.definition_id) != "armor":
        if instance.rune_ids and ITEM_CATEGORIES.get(instance.definition_id) is None:
            _runes_for_item(instance, "armor")
        return None
    runes = _runes_for_item(instance, "armor")
    potency = next((rune.value for rune in runes if rune.category == "armor_potency"), 0)
    resilient = next((rune.value for rune in runes if rune.category == "resilient"), 0)
    source_urls = tuple(dict.fromkeys(rune.source_url for rune in runes))
    return ArmorRuneProfile(source_urls=source_urls or ArmorRuneProfile().source_urls, potency=potency, resilient_bonus=resilient)


def is_drawable_equipment_definition(definition_id: str) -> bool:
    """Whether an instance of this curated equipment category is held to use."""
    return ITEM_CATEGORIES.get(definition_id) in {"weapon", "shield"}
