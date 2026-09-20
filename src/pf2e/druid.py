"""Finite preparation rules for the selected Storm Druid."""

from __future__ import annotations

from dataclasses import dataclass

_CANTRIPS = frozenset({"electric_arc", "guidance", "stabilize", "tangle_vine", "light"})
_RANK_ONE = frozenset({"heal", "runic_weapon"})
_CANTRIP_CHOICES = ("electric_arc", "guidance", "stabilize", "tangle_vine", "light")
_RANK_ONE_CHOICES = ("heal", "runic_weapon")
_WIDEN_RANK_ONE = frozenset({*_RANK_ONE, "breathe_fire"})
_WIDEN_RANK_ONE_CHOICES = (*_RANK_ONE_CHOICES, "breathe_fire")


@dataclass(frozen=True)
class AnimalEmpathyRecord:
    """One authored animal conversation, without a social-world simulator."""

    question_key: str
    animal_actor_id: str
    question: str
    willingness: str
    attitude: str
    will_dc: int
    request_dc: int
    impression_answers: tuple[str, str, str, str]
    request_answers: tuple[str, str, str, str]


def preparation_choices(definition, slot) -> tuple[str, ...]:
    """Return the selected Storm Druid's finite daily menu for one slot."""
    if "storm_druid_preparation" not in definition.abilities:
        return ()
    if slot.cantrip:
        return _CANTRIP_CHOICES
    if slot.rank == 1:
        return (
            _WIDEN_RANK_ONE_CHOICES
            if "storm_druid_widen_preparation" in definition.abilities
            else _RANK_ONE_CHOICES
        )
    return ()


def prepared_slot_rejection(actor, definition, slot, spell_id: str) -> str | None:
    """Validate one selected Druid slot's finite daily choice."""
    if "storm_druid_preparation" not in definition.abilities:
        return None
    if not isinstance(spell_id, str) or not spell_id:
        return "Prepared spell selection requires a spell id."
    allowed = (
        _CANTRIPS if slot.cantrip else
        _WIDEN_RANK_ONE if slot.rank == 1 and "storm_druid_widen_preparation" in definition.abilities else
        _RANK_ONE if slot.rank == 1 else frozenset()
    )
    if spell_id in allowed:
        return None
    return "The spell is outside this Storm Druid's finite primal preparation choices."
