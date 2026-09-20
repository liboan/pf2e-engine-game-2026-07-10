"""Validation helpers for bounded W5 Monk stance records."""

from __future__ import annotations


def tiger_bleed_save_allowed(source_definition, *, source_id: str, damage_type: str, dice, flat: int) -> bool:
    return (
        source_id == "tiger_stance"
        and "Tiger Stance" in source_definition.feats
        and damage_type == "bleed"
        and tuple(dice) == (4,)
        and flat == 0
    )
