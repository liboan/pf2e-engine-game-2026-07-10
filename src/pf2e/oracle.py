"""Bounded level-1 Life Oracle rules."""


def healing_after_curse(amount: int, cursebound: int, *, level: int = 1) -> int:
    """Apply Life's level-scaled magical-healing status penalty."""
    if type(level) is not int or level < 1:
        raise ValueError("Life Oracle level must be a positive integer")
    return max(0, amount - max(1, level) * cursebound)
