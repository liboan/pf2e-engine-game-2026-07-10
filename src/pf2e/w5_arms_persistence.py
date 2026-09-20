"""Persistence contract for the W5 Arms lane.

The generic ``ActiveSpellEffect`` row already has neutral defaults and is
backward-compatible, so W5 deliberately keeps the single engine save version
at 18.  This bounded set is imported by the central validator as the lane's
only new effect kind.
"""

W5_ARMS_ACTIVE_EFFECT_KINDS = frozenset({"extravagant_parry"})
W5_SAVE_VERSION = 18
