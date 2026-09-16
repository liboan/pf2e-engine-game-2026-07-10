"""Independent source-informed play review for Light and its controls.

Primary rules text checked 2026-09-16:

* Light: https://2e.aonprd.com/Spells.aspx?ID=1585
* Sustain: https://2e.aonprd.com/Actions.aspx?ID=2317
* Dismiss: https://2e.aonprd.com/Actions.aspx?ID=2311
* Targets: https://2e.aonprd.com/Rules.aspx?ID=2240
* Dim light: https://2e.aonprd.com/Rules.aspx?ID=2403
* Concealed: https://2e.aonprd.com/Conditions.aspx?ID=62

The review keeps the accepted flat, open, ambient-dim scene boundary. It does
not claim darkness, occlusion, hidden creatures, or object targeting support.
"""

from __future__ import annotations

from dataclasses import replace
import json
from pathlib import Path
from types import MappingProxyType

import pytest

import pf2e.content as content
from pf2e import Cast, Dismiss, Encounter, EndTurn, Position, ResultStatus, Strike, Stride, Sustain
from pf2e.content import ANGELIC_FIRST_CAST_SETUP, ANGELIC_FEAR_REACTION_SETUP


def _actor(game: Encounter, actor_id: str):
    return next(actor for actor in game.inspect().actors if actor.actor_id == actor_id)


def _settle_initiative(game: Encounter) -> None:
    while (choice := game.inspect().choice) is not None:
        assert choice.kind == "initiative_hero_reroll"
        result = game.choose(choice.choice_id, "keep", choice.owner_actor_id)
        assert result.status in {ResultStatus.PAUSED, ResultStatus.COMPLETED}


def _register_setup(monkeypatch: pytest.MonkeyPatch, setup) -> None:
    monkeypatch.setattr(
        content,
        "_STAGED_SETUPS",
        MappingProxyType({**content._STAGED_SETUPS, setup.setup_id: setup}),
    )


def _advance_to(game: Encounter, actor_id: str) -> None:
    while game.inspect().turn_actor_id != actor_id:
        assert game.execute(EndTurn()).status is ResultStatus.COMPLETED


def _next_turn_for(game: Encounter, actor_id: str) -> None:
    if game.inspect().turn_actor_id == actor_id:
        assert game.execute(EndTurn()).status is ResultStatus.COMPLETED
    _advance_to(game, actor_id)


def test_healthy_dim_fight_saves_light_choice_sustains_targeting_and_wins(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """A continuous healthy-start encounter proves Light changes real play."""
    positions = {
        "angelic_sorcerer": Position(0, 2),
        "sorcerer_ally": Position(6, 2),
        "sorcerer_dog": Position(9, 2),
    }
    setup = replace(
        ANGELIC_FIRST_CAST_SETUP,
        setup_id="light_complete_play_review",
        width=12,
        ambient_light="dim",
        placements=tuple(
            replace(placement, position=positions[placement.actor_id])
            for placement in ANGELIC_FIRST_CAST_SETUP.placements
        ),
    )
    _register_setup(monkeypatch, setup)

    # Initiative; dog critical jaws and damage; failed DC 5 targeting check;
    # then Divine Lance critical attack and its two damage dice.
    game = Encounter.start(setup, rolls=(20, 1, 1, 20, 3, 4, 20, 2, 2))
    assert all(actor.hp == actor.max_hp for actor in game.inspect().actors)
    _settle_initiative(game)
    assert game.inspect().turn_actor_id == "angelic_sorcerer"

    offered = game.execute(
        Cast(
            "light",
            point=Position(0, 2),
            color="warm gold",
            attachment_actor_id="angelic_sorcerer",
        )
    )
    assert offered.status is ResultStatus.PAUSED
    assert offered.inspection.choice is not None
    assert offered.inspection.choice.kind == "spell_willingness"

    save_path = tmp_path / "light-complete-play.json"
    game.save(save_path)
    payload = json.loads(save_path.read_text(encoding="utf-8"))
    assert payload["save_version"] == 17
    resumed = Encounter.load(save_path)
    assert resumed.inspect() == offered.inspection
    choice = resumed.inspect().choice
    assert choice is not None
    attached = resumed.choose(choice.choice_id, "willing", choice.owner_actor_id)
    assert attached.status is ResultStatus.COMPLETED
    orb = resumed._state.light_orbs[0]
    assert (orb.point, orb.attached_actor_id) == (None, "angelic_sorcerer")

    assert resumed.execute(EndTurn()).status is ResultStatus.COMPLETED
    assert resumed.inspect().turn_actor_id == "sorcerer_dog"
    assert resumed.execute(
        Stride((Position(8, 2), Position(7, 2)))
    ).status is ResultStatus.COMPLETED
    injury = resumed.execute(Strike("sorcerer_ally", attack_id="jaws"))
    assert injury.status is ResultStatus.COMPLETED
    assert any(event.kind == "damage" for event in injury.events)
    assert _actor(resumed, "sorcerer_ally").hp < _actor(resumed, "sorcerer_ally").max_hp

    assert resumed.execute(EndTurn()).status is ResultStatus.COMPLETED
    assert resumed.inspect().turn_actor_id == "sorcerer_ally"
    assert resumed.target_is_concealed("sorcerer_ally", "sorcerer_dog")
    dog_hp = _actor(resumed, "sorcerer_dog").hp
    attempted = resumed.execute(Strike("sorcerer_dog", attack_id="longsword"))
    assert attempted.status is ResultStatus.PAUSED
    flat_choice = attempted.inspection.choice
    assert flat_choice is not None and flat_choice.kind == "concealment_hero_reroll"
    missed = resumed.choose(flat_choice.choice_id, "keep", flat_choice.owner_actor_id)
    assert missed.status is ResultStatus.COMPLETED
    assert any(event.kind == "concealment_failed" for event in missed.events)
    assert _actor(resumed, "sorcerer_dog").hp == dog_hp

    assert resumed.execute(EndTurn()).status is ResultStatus.COMPLETED
    assert resumed.inspect().turn_actor_id == "angelic_sorcerer"
    moved_light = resumed.execute(Sustain(orb.stable_id, point=Position(4, 2)))
    assert moved_light.status is ResultStatus.COMPLETED
    assert not resumed.target_is_concealed("angelic_sorcerer", "sorcerer_dog")
    assert resumed._state.light_orbs[0].point == Position(4, 2)

    finishing_cast = resumed.execute(Cast("divine_lance", "sorcerer_dog"))
    if finishing_cast.status is ResultStatus.PAUSED:
        attack_choice = finishing_cast.inspection.choice
        assert attack_choice is not None and attack_choice.kind == "spell_attack_hero_reroll"
        victory = resumed.choose(attack_choice.choice_id, "keep", attack_choice.owner_actor_id)
    else:
        assert finishing_cast.status is ResultStatus.COMPLETED
        victory = finishing_cast
    assert victory.status is ResultStatus.COMPLETED
    assert any(event.kind == "spell_damage" for event in victory.events)
    assert not resumed.inspect().in_progress
    assert resumed.inspect().winner_team == "blue"
    assert _actor(resumed, "sorcerer_dog").defeated


def test_attached_light_follows_carrier_through_saved_movement_reaction(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """The orb derives its point from the carrier before and after a pause."""
    positions = {
        "angelic_sorcerer": Position(1, 1),
        "sorcerer_ally": Position(5, 2),
        "sorcerer_dog": Position(5, 1),
    }
    setup = replace(
        ANGELIC_FEAR_REACTION_SETUP,
        setup_id="light_attached_saved_movement_review",
        width=12,
        ambient_light="dim",
        placements=tuple(
            replace(placement, position=positions[placement.actor_id])
            for placement in ANGELIC_FEAR_REACTION_SETUP.placements
        ),
    )
    _register_setup(monkeypatch, setup)
    game = Encounter.start(setup, rolls=(20, 10, 1))
    _settle_initiative(game)

    offered = game.execute(
        Cast(
            "light",
            point=Position(5, 1),
            color="blue",
            attachment_actor_id="sorcerer_dog",
        )
    )
    assert offered.status is ResultStatus.PAUSED
    willingness = offered.inspection.choice
    assert willingness is not None and willingness.kind == "spell_willingness"
    accepted = game.choose(willingness.choice_id, "willing", willingness.owner_actor_id)
    assert accepted.status is ResultStatus.COMPLETED
    orb = game._state.light_orbs[0]
    assert (orb.point, orb.attached_actor_id) == (None, "sorcerer_dog")

    assert game.execute(EndTurn()).status is ResultStatus.COMPLETED
    assert game.execute(EndTurn()).status is ResultStatus.COMPLETED
    assert game.inspect().turn_actor_id == "sorcerer_dog"
    assert game.illumination_at(Position(1, 1)) == "bright"

    movement = game.execute(Stride((Position(6, 1),)))
    assert movement.status is ResultStatus.PAUSED
    reaction = movement.inspection.choice
    assert reaction is not None and reaction.kind == "reaction"
    assert reaction.owner_actor_id == "sorcerer_ally"

    save_path = tmp_path / "attached-light-movement-reaction.json"
    game.save(save_path)
    restored = Encounter.load(save_path)
    assert restored.inspect() == movement.inspection
    assert restored.illumination_at(Position(1, 1)) == "bright"
    reaction = restored.inspect().choice
    assert reaction is not None
    moved = restored.choose(reaction.choice_id, "decline", reaction.owner_actor_id)
    assert moved.status is ResultStatus.COMPLETED
    assert _actor(restored, "sorcerer_dog").position == Position(6, 1)
    assert restored._state.light_orbs[0].attached_actor_id == "sorcerer_dog"
    assert restored.illumination_at(Position(1, 1)) == "dim"


def test_replacement_is_not_a_free_dismiss_and_cannot_take_foreign_orb(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    placements = tuple(
        replace(
            placement,
            actor_id="other_sorcerer",
            definition_id=content.ANGELIC_SORCERER_STAGED.definition_id,
            label="Other Sorcerer",
        )
        if placement.actor_id == "sorcerer_ally"
        else placement
        for placement in ANGELIC_FIRST_CAST_SETUP.placements
    )
    setup = replace(
        ANGELIC_FIRST_CAST_SETUP,
        setup_id="light_replacement_ownership_review",
        ambient_light="dim",
        placements=placements,
    )
    _register_setup(monkeypatch, setup)
    game = Encounter.start(setup, rolls=(20, 19, 1))
    _settle_initiative(game)
    assert game.inspect().turn_actor_id == "angelic_sorcerer"

    assert game.execute(Cast("light", point=Position(0, 0), color="first")).status is ResultStatus.COMPLETED
    first_id = next(
        orb.stable_id for orb in game._state.light_orbs
        if orb.caster_actor_id == "angelic_sorcerer"
    )
    assert game.execute(EndTurn()).status is ResultStatus.COMPLETED
    assert game.inspect().turn_actor_id == "other_sorcerer"
    assert game.execute(Cast("light", point=Position(6, 0), color="foreign")).status is ResultStatus.COMPLETED
    foreign_id = next(
        orb.stable_id for orb in game._state.light_orbs
        if orb.caster_actor_id == "other_sorcerer"
    )
    _next_turn_for(game, "angelic_sorcerer")

    before = game.inspect()
    before_dice = game._dice._index
    under_cap = game.execute(
        Cast(
            "light",
            point=Position(1, 0),
            color="invalid replacement",
            replacement_orb_id=first_id,
        )
    )
    assert under_cap.status is ResultStatus.REJECTED
    assert "already has four active Light orbs" in under_cap.message
    assert game.inspect() == before
    assert game._dice._index == before_dice
    assert {orb.stable_id for orb in game._state.light_orbs} == {first_id, foreign_id}

    actions = _actor(game, "angelic_sorcerer").actions_remaining
    dismissed = game.execute(Dismiss(first_id))
    assert dismissed.status is ResultStatus.COMPLETED
    assert _actor(game, "angelic_sorcerer").actions_remaining == actions - 1
    assert first_id not in {orb.stable_id for orb in game._state.light_orbs}
    assert game.execute(Cast("light", point=Position(1, 0), color="one")).status is ResultStatus.COMPLETED

    for index, point in enumerate((Position(2, 0), Position(3, 0), Position(4, 0)), start=2):
        _advance_to(game, "angelic_sorcerer")
        if _actor(game, "angelic_sorcerer").actions_remaining < 2:
            _next_turn_for(game, "angelic_sorcerer")
        result = game.execute(Cast("light", point=point, color=f"owned-{index}"))
        assert result.status is ResultStatus.COMPLETED

    owned = {
        orb.stable_id for orb in game._state.light_orbs
        if orb.caster_actor_id == "angelic_sorcerer"
    }
    assert len(owned) == 4
    _next_turn_for(game, "angelic_sorcerer")
    before = game.inspect()
    before_dice = game._dice._index
    wrong_owner = game.execute(
        Cast(
            "light",
            point=Position(5, 0),
            color="fifth",
            replacement_orb_id=foreign_id,
        )
    )
    assert wrong_owner.status is ResultStatus.REJECTED
    assert "caster's active orbs" in wrong_owner.message
    assert game.inspect() == before
    assert game._dice._index == before_dice
    assert owned.issubset({orb.stable_id for orb in game._state.light_orbs})
    assert foreign_id in {orb.stable_id for orb in game._state.light_orbs}

    control_before = game.inspect()
    rejected_dismiss = game.execute(Dismiss(foreign_id))
    assert rejected_dismiss.status is ResultStatus.REJECTED
    assert game.inspect() == control_before
