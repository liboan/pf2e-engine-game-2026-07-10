"""Independent public-play review of concealment versus Angelic Blood Magic.

Rules sources:
* Player Core 2 p. 149-150: https://2e.aonprd.com/Bloodlines.aspx
* Player Core p. 442: https://2e.aonprd.com/Conditions.aspx?ID=62
* Player Core p. 335: https://2e.aonprd.com/Spells.aspx?ID=1554
"""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from types import MappingProxyType

import pytest

import pf2e.content as content
from pf2e import Cast, Encounter, ResultStatus
from pf2e.content import ANGELIC_FIRST_CAST_SETUP
from pf2e.model import EndTurn, Position, Strike


def _injured_ally_in_ordinary_dim_light(
    monkeypatch: pytest.MonkeyPatch,
    setup_id: str,
) -> Encounter:
    """Start with the low-light dog adjacent, then injure the ally by Strike."""
    setup = replace(
        ANGELIC_FIRST_CAST_SETUP,
        setup_id=setup_id,
        ambient_light="dim",
        placements=tuple(
            replace(placement, position=Position(3, 2))
            if placement.actor_id == "sorcerer_dog"
            else placement
            for placement in ANGELIC_FIRST_CAST_SETUP.placements
        ),
    )
    monkeypatch.setattr(
        content,
        "_STAGED_SETUPS",
        MappingProxyType({**content._STAGED_SETUPS, setup.setup_id: setup}),
    )
    # Three initiative dice; dog Strike attack/damage; failed DC 5 flat check.
    game = Encounter.start(setup, rolls=(1, 2, 20, 15, 4, 4))
    while (choice := game.inspect().choice) is not None:
        assert choice.kind == "initiative_hero_reroll"
        kept = game.choose(choice.choice_id, "keep", choice.owner_actor_id)
        assert kept.status is ResultStatus.COMPLETED

    assert game.inspect().turn_actor_id == "sorcerer_dog"
    ally_before = next(
        actor.hp for actor in game.inspect().actors
        if actor.actor_id == "sorcerer_ally"
    )
    struck = game.execute(Strike("sorcerer_ally"))
    assert struck.status is ResultStatus.COMPLETED
    assert any(event.kind == "damage" for event in struck.events)
    ally_after = next(
        actor.hp for actor in game.inspect().actors
        if actor.actor_id == "sorcerer_ally"
    )
    assert ally_after < ally_before

    while game.inspect().turn_actor_id != "angelic_sorcerer":
        assert game.execute(EndTurn()).status is ResultStatus.COMPLETED
    # The staged Sorcerer fixture has no campaign-issued Hero Point. Grant one
    # explicitly so the public targeting choice can be saved and resumed.
    game._state.creatures["angelic_sorcerer"].hero_points = 1
    return game


def _start_failed_targeted_heal(game: Encounter, blood_recipient: str):
    started = game.execute(
        Cast("heal", "sorcerer_ally", actions=2, slot_id="angelic_rank1")
    )
    assert started.status is ResultStatus.PAUSED
    blood = started.inspection.choice
    assert blood is not None and blood.kind == "spell_blood_magic_recipient"
    flat = game.choose(blood.choice_id, blood_recipient, blood.owner_actor_id)
    assert flat.status is ResultStatus.PAUSED
    assert flat.inspection.choice is not None
    assert flat.inspection.choice.kind == "concealment_hero_reroll"
    assert flat.events[-1].check is not None and flat.events[-1].check.die == 4
    return flat


def test_saved_failed_heal_targeting_still_applies_caster_blood_magic(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    game = _injured_ally_in_ordinary_dim_light(
        monkeypatch, "review_failed_heal_caster_blood_magic"
    )
    ally_hp = next(
        actor.hp for actor in game.inspect().actors
        if actor.actor_id == "sorcerer_ally"
    )
    flat = _start_failed_targeted_heal(game, "angelic_sorcerer")

    path = tmp_path / "failed-heal-caster-blood-magic.json"
    game.save(path)
    restored = Encounter.load(path)
    assert restored.inspect() == flat.inspection
    result = restored.choose(
        restored.inspect().choice.choice_id,
        "keep",
        restored.inspect().choice.owner_actor_id,
    )

    assert result.status is ResultStatus.COMPLETED
    assert any(event.kind == "concealment_failed" for event in result.events)
    assert any(event.kind == "blood_magic_applied" for event in result.events)
    assert not any(event.kind in {"heal_roll", "healing"} for event in result.events)
    assert next(
        actor.hp for actor in restored.inspect().actors
        if actor.actor_id == "sorcerer_ally"
    ) == ally_hp
    caster = next(
        actor for actor in restored.inspect().actors
        if actor.actor_id == "angelic_sorcerer"
    )
    assert caster.spontaneous_slots[0].remaining == 2
    assert any(
        effect.kind == "blood_magic"
        and effect.source_actor_id == "angelic_sorcerer"
        and effect.target_actor_id == "angelic_sorcerer"
        for effect in restored._state.active_effects
    )


def test_failed_heal_targeting_does_not_apply_blood_magic_to_concealed_target(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    game = _injured_ally_in_ordinary_dim_light(
        monkeypatch, "review_failed_heal_target_blood_magic"
    )
    ally_hp = next(
        actor.hp for actor in game.inspect().actors
        if actor.actor_id == "sorcerer_ally"
    )
    _start_failed_targeted_heal(game, "sorcerer_ally")
    choice = game.inspect().choice
    assert choice is not None
    result = game.choose(choice.choice_id, "keep", choice.owner_actor_id)

    assert result.status is ResultStatus.COMPLETED
    assert any(event.kind == "concealment_failed" for event in result.events)
    assert not any(
        event.kind in {"blood_magic_applied", "heal_roll", "healing"}
        for event in result.events
    )
    assert next(
        actor.hp for actor in game.inspect().actors
        if actor.actor_id == "sorcerer_ally"
    ) == ally_hp
    caster = next(
        actor for actor in game.inspect().actors
        if actor.actor_id == "angelic_sorcerer"
    )
    assert caster.spontaneous_slots[0].remaining == 2
    assert not any(effect.kind == "blood_magic" for effect in game._state.active_effects)


def test_critical_cast_disruption_suppresses_caster_blood_magic(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A disrupted cast loses all effects, unlike an ordinary target miss."""
    setup = replace(
        ANGELIC_FIRST_CAST_SETUP,
        setup_id="review_disrupted_heal_blood_magic",
        ambient_light="dim",
        placements=tuple(
            replace(placement, team="red")
            if placement.actor_id == "sorcerer_ally"
            else placement
            for placement in ANGELIC_FIRST_CAST_SETUP.placements
        ),
    )
    monkeypatch.setattr(
        content,
        "_STAGED_SETUPS",
        MappingProxyType({**content._STAGED_SETUPS, setup.setup_id: setup}),
    )
    # Initiative, then the hostile Fighter's concealment check, critical
    # Reactive Strike attack, and damage against the manipulate cast.
    game = Encounter.start(setup, rolls=(1, 20, 2, 20, 20, 3))
    while (choice := game.inspect().choice) is not None:
        assert choice.kind == "initiative_hero_reroll"
        game.choose(choice.choice_id, "keep", choice.owner_actor_id)

    assert game.inspect().turn_actor_id == "sorcerer_ally"
    # Keep this check about disruption rather than fortune choices; all flat,
    # attack, and damage results still come from the supplied roll stream.
    game._state.creatures["sorcerer_ally"].hero_points = 0
    caster_before = next(
        actor.hp for actor in game.inspect().actors
        if actor.actor_id == "angelic_sorcerer"
    )
    while game.inspect().turn_actor_id != "angelic_sorcerer":
        assert game.execute(EndTurn()).status is ResultStatus.COMPLETED
    offered = game.execute(
        Cast("heal", "angelic_sorcerer", actions=2, slot_id="angelic_rank1")
    )
    assert offered.status is ResultStatus.PAUSED
    blood = offered.inspection.choice
    assert blood is not None and blood.kind == "spell_blood_magic_recipient"
    reaction = game.choose(blood.choice_id, "angelic_sorcerer", blood.owner_actor_id)
    assert reaction.status is ResultStatus.PAUSED
    assert reaction.inspection.choice is not None
    assert reaction.inspection.choice.kind == "reaction"
    attacked = game.choose(
        reaction.inspection.choice.choice_id,
        "accept",
        reaction.inspection.choice.owner_actor_id,
    )
    result = attacked

    assert result.status is ResultStatus.COMPLETED
    assert any(event.kind == "disrupted" for event in result.events), [
        (event.kind, event.text, event.check.die if event.check is not None else None)
        for event in result.events
    ]
    caster_after = next(
        actor.hp for actor in game.inspect().actors
        if actor.actor_id == "angelic_sorcerer"
    )
    assert caster_after < caster_before
    assert not any(
        event.kind in {"blood_magic_applied", "heal_roll", "healing"}
        for event in result.events
    )
    caster = next(
        actor for actor in game.inspect().actors
        if actor.actor_id == "angelic_sorcerer"
    )
    assert caster.spontaneous_slots[0].remaining == 2
    assert not any(effect.kind == "blood_magic" for effect in game._state.active_effects)
