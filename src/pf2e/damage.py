"""Small typed damage records for the S1 Strike boundary.

Critical doubling follows Player Core p. 407, checked 2026-09-15:
https://2e.aonprd.com/Rules.aspx?ID=2307
"""

from dataclasses import dataclass
from typing import Callable


@dataclass(frozen=True)
class DamagePacket:
    source: str
    damage_type: str
    dice_sides: int
    dice_count: int
    modifier: int


@dataclass(frozen=True)
class DamageComponent:
    source: str
    damage_type: str
    dice_sides: int
    rolls: tuple[int, ...]
    modifier: int
    amount: int


@dataclass(frozen=True)
class DamageResult:
    components: tuple[DamageComponent, ...]
    rolled_total: int
    multiplier: int
    total: int
    adjustment: str | None = None


def resolve_damage(packet: DamagePacket, roll: Callable[[int], int], *, critical: bool = False) -> DamageResult:
    """Roll dice and add the modifier, then double the complete total on a crit."""
    if packet.dice_sides < 2 or packet.dice_count < 1:
        raise ValueError("damage dice must have at least 2 sides and at least one die")
    rolls = tuple(roll(packet.dice_sides) for _ in range(packet.dice_count))
    if any(type(face) is not int or not 1 <= face <= packet.dice_sides for face in rolls):
        raise ValueError("damage die result is outside its die's range")
    rolled_total = sum(rolls) + packet.modifier
    multiplier = 2 if critical else 1
    total = rolled_total * multiplier
    component = DamageComponent(
        source=packet.source,
        damage_type=packet.damage_type,
        dice_sides=packet.dice_sides,
        rolls=rolls,
        modifier=packet.modifier,
        amount=total,
    )
    return DamageResult((component,), rolled_total, multiplier, total)
