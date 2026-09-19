"""Bounded level-1 Life Oracle rules."""


def healing_after_curse(amount: int, cursebound: int) -> int:
    return max(0, amount - cursebound)
