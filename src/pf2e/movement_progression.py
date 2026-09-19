"""Narrow level-2 horizontal-movement rules.

The records here deliberately model only the two admitted effects rather than
adding a movement or off-guard framework.  Callers own path validation,
reaction presentation, state persistence, and Strike resolution.

Rules checked 2026-09-18:

* Mobility: https://2e.aonprd.com/Feats.aspx?ID=4926
* Tumble Behind: https://2e.aonprd.com/Feats.aspx?ID=6142
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from .model import EffectExpiration


@runtime_checkable
class _DefinitionActor(Protocol):
    """The small state surface Mobility needs after the core validates a path."""

    definition_id: str


@dataclass(frozen=True)
class TumbleBehindExposure:
    """One attacker-relative, one-attack off-guard exposure.

    Tumble Behind is intentionally distinct from Feint: it is granted only by
    a successful Tumble Through, applies to ranged/thrown attacks too, and is
    consumed by the source's next attack attempt before the source actor's
    current turn ends.  Only an attempt against ``target_actor_id`` receives
    the off-guard benefit.
    """

    effect_id: str
    source_actor_id: str
    target_actor_id: str
    expiration: EffectExpiration

    def __post_init__(self) -> None:
        if not all(
            isinstance(value, str) and value
            for value in (self.effect_id, self.source_actor_id, self.target_actor_id)
        ):
            raise ValueError("Tumble Behind needs stable non-empty effect/source/target IDs")
        if self.source_actor_id == self.target_actor_id:
            raise ValueError("Tumble Behind source and target must differ")
        if (
            not isinstance(self.expiration, EffectExpiration)
            or self.expiration.anchor_actor_id != self.source_actor_id
            or self.expiration.boundary != "end"
            or type(self.expiration.occurrence) is not int
            or self.expiration.occurrence < 1
        ):
            raise ValueError("Tumble Behind expires at its source actor's end boundary")


def mobility_applies(
    actor: _DefinitionActor,
    *,
    actual_speed_feet: int,
    path_cost_feet: int,
    action_kind: str,
) -> bool:
    """Whether a validated ordinary Stride suppresses its reactions.

    The caller supplies *actual* path cost and current Speed only after all
    movement/path checks have passed.  Comparing doubled cost preserves the
    printed ``half your Speed or less`` threshold for odd Speeds without
    rounding an 12.5-foot allowance down prematurely.
    """

    if not isinstance(actor, _DefinitionActor):
        raise TypeError("Mobility needs an actor with a definition ID")
    if type(actual_speed_feet) is not int or actual_speed_feet < 0:
        raise ValueError("Mobility needs a non-negative actual Speed")
    if type(path_cost_feet) is not int or path_cost_feet < 0:
        raise ValueError("Mobility needs a non-negative validated path cost")
    if not isinstance(action_kind, str) or not action_kind:
        raise ValueError("Mobility needs a named movement action")
    if action_kind.casefold() != "stride":
        return False
    # Content is resolved lazily so this pure rules module remains usable by
    # test-local staged definitions and does not create a content import loop.
    from .content import get_definition

    return (
        "Mobility" in get_definition(actor.definition_id).feats
        and path_cost_feet * 2 <= actual_speed_feet
    )


def grant_tumble_behind_exposure(
    effects: tuple[TumbleBehindExposure, ...],
    *,
    source_actor_id: str,
    target_actor_id: str,
    current_source_end_count: int,
) -> tuple[TumbleBehindExposure, ...]:
    """Return ``effects`` with one newly granted Tumble Behind exposure."""

    _validate_effects(effects)
    if not all(isinstance(value, str) and value for value in (source_actor_id, target_actor_id)):
        raise ValueError("Tumble Behind grant needs source and target IDs")
    if source_actor_id == target_actor_id:
        raise ValueError("Tumble Behind must name a different target")
    if type(current_source_end_count) is not int or current_source_end_count < 0:
        raise ValueError("Tumble Behind needs a non-negative source end count")
    prefix = f"tumble_behind:{source_actor_id}:{target_actor_id}:{current_source_end_count + 1}"
    used = {effect.effect_id for effect in effects}
    suffix = 1
    while f"{prefix}:{suffix}" in used:
        suffix += 1
    return effects + (
        TumbleBehindExposure(
            f"{prefix}:{suffix}",
            source_actor_id,
            target_actor_id,
            EffectExpiration(source_actor_id, "end", current_source_end_count + 1),
        ),
    )


def tumble_behind_applies(
    effects: tuple[TumbleBehindExposure, ...],
    *,
    attacker_id: str,
    target_id: str,
    actor_end_counts: dict[str, int],
) -> bool:
    """Whether this particular Strike sees the target as off-guard."""

    _validate_query(effects, attacker_id, target_id, actor_end_counts)
    return any(
        effect.source_actor_id == attacker_id
        and effect.target_actor_id == target_id
        and _active(effect, actor_end_counts)
        for effect in effects
    )


def consume_tumble_behind_on_attack(
    effects: tuple[TumbleBehindExposure, ...],
    *,
    attacker_id: str,
    target_id: str,
    actor_end_counts: dict[str, int],
) -> tuple[TumbleBehindExposure, ...]:
    """Consume all of an attacker's active exposures on any attack attempt.

    ``target_id`` remains part of the narrow shared hook so the caller can use
    the same attack context for the preceding applicability query.  It does
    not constrain consumption: the printed feat says the *next attack you
    make*, so an intervening attack against another creature ends every live
    Tumble Behind exposure granted to this attacker.
    """

    _validate_query(effects, attacker_id, target_id, actor_end_counts)
    consumed = {
        effect.effect_id
        for effect in effects
        if effect.source_actor_id == attacker_id and _active(effect, actor_end_counts)
    }
    return tuple(item for item in effects if item.effect_id not in consumed)


def expire_tumble_behind_exposures(
    effects: tuple[TumbleBehindExposure, ...],
    *,
    actor_id: str,
    actor_end_counts: dict[str, int],
) -> tuple[TumbleBehindExposure, ...]:
    """Expire source-anchored exposures after an actor's end boundary."""

    _validate_effects(effects)
    if not isinstance(actor_id, str) or not actor_id:
        raise ValueError("Tumble Behind expiry needs an actor ID")
    _validate_end_counts(actor_end_counts)
    return tuple(
        effect
        for effect in effects
        if not (
            effect.expiration.anchor_actor_id == actor_id
            and not _active(effect, actor_end_counts)
        )
    )


def _validate_effects(effects: tuple[TumbleBehindExposure, ...]) -> None:
    if not isinstance(effects, tuple) or any(not isinstance(item, TumbleBehindExposure) for item in effects):
        raise TypeError("Tumble Behind effects must be a tuple of typed exposures")
    effect_ids = tuple(item.effect_id for item in effects)
    if len(set(effect_ids)) != len(effect_ids):
        raise ValueError("Tumble Behind effect IDs must be unique")


def _validate_query(
    effects: tuple[TumbleBehindExposure, ...], attacker_id: str, target_id: str, actor_end_counts: dict[str, int]
) -> None:
    _validate_effects(effects)
    if not all(isinstance(value, str) and value for value in (attacker_id, target_id)):
        raise ValueError("Tumble Behind attack queries need attacker and target IDs")
    _validate_end_counts(actor_end_counts)


def _validate_end_counts(actor_end_counts: dict[str, int]) -> None:
    if (
        not isinstance(actor_end_counts, dict)
        or any(not isinstance(key, str) or not key or type(value) is not int or value < 0 for key, value in actor_end_counts.items())
    ):
        raise TypeError("Tumble Behind end counts must map actor IDs to non-negative integers")


def _active(effect: TumbleBehindExposure, actor_end_counts: dict[str, int]) -> bool:
    return actor_end_counts.get(effect.expiration.anchor_actor_id, 0) < effect.expiration.occurrence
