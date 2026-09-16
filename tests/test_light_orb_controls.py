"""Focused Sustain, Dismiss, and replacement checks for Light."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from types import MappingProxyType

import pytest
import pf2e.content as content

from pf2e import (
    Cast,
    Dismiss,
    EndTurn,
    Encounter,
    Position,
    ResultStatus,
    Stride,
    Sustain,
)
from pf2e.content import ANGELIC_FIRST_CAST_SETUP, ANGELIC_FEAR_REACTION_SETUP
from pf2e.model import LightOrb


def _settle_start(game: Encounter) -> None:
    while (choice := game.inspect().choice) is not None:
        option = "keep" if any(item.option_id == "keep" for item in choice.options) else choice.options[0].option_id
        result = game.choose(choice.choice_id, option, choice.owner_actor_id)
        assert result.status in {ResultStatus.PAUSED, ResultStatus.COMPLETED}


def _light_game(monkeypatch: pytest.MonkeyPatch, *, width: int = 7) -> Encounter:
    setup = replace(
        ANGELIC_FIRST_CAST_SETUP,
        setup_id=f"light_orb_controls_{width}",
        ambient_light="dim",
        width=width,
    )
    monkeypatch.setattr(
        content,
        "_STAGED_SETUPS",
        MappingProxyType({**content._STAGED_SETUPS, setup.setup_id: setup}),
    )
    game = Encounter.start(setup, rolls=(20, 1, 1, 20, 1, 1, 1) * 40)
    _settle_start(game)
    assert game.inspect().turn_actor_id == "angelic_sorcerer"
    return game


def _advance_to(game: Encounter, actor_id: str) -> None:
    game.execute(EndTurn())
    while game.inspect().turn_actor_id != actor_id:
        game.execute(EndTurn())


def _orb_id(game: Encounter) -> str:
    return game._state.light_orbs[0].stable_id


def test_sustain_moves_one_action_repeatedly_and_survives_skipped_turns(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    game = _light_game(monkeypatch, width=15)
    game.execute(Cast("light", point=Position(1, 2), color="amber"))
    orb_id = _orb_id(game)

    # The first Sustain spends the final action left by the two-action cast.
    _advance_to(game, "angelic_sorcerer")
    moved = game.execute(Sustain(orb_id, point=Position(3, 2)))
    assert moved.status is ResultStatus.COMPLETED
    assert game._state.light_orbs[0].point == Position(3, 2)
    assert any(event.kind == "light_orb_sustained" for event in moved.events)

    # Sustain can be repeated on a later turn and still costs one action.
    _advance_to(game, "angelic_sorcerer")
    before = game._state.creatures["angelic_sorcerer"].actions_remaining
    repeated = game.execute(Sustain(orb_id, point=Position(4, 2)))
    assert repeated.status is ResultStatus.COMPLETED
    assert game._state.creatures["angelic_sorcerer"].actions_remaining == before - 1

    # Round rollover and skipped Sustains do not expire Light.
    _advance_to(game, "angelic_sorcerer")
    assert game._state.light_orbs[0].stable_id == orb_id
    assert game._state.round_number >= 2


def test_sustain_allows_60_feet_and_rejects_65_atomically(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    game = _light_game(monkeypatch, width=15)
    game.execute(Cast("light", point=Position(1, 2), color="white"))
    orb_id = _orb_id(game)
    _advance_to(game, "angelic_sorcerer")

    success = game.execute(Sustain(orb_id, point=Position(13, 2)))
    assert success.status is ResultStatus.COMPLETED
    assert game._state.light_orbs[0].point == Position(13, 2)
    _advance_to(game, "angelic_sorcerer")
    before = game.inspect()
    rejected = game.execute(Sustain(orb_id, point=Position(0, 2)))
    assert rejected.status is ResultStatus.REJECTED
    assert "60 feet" in rejected.message
    assert game.inspect() == before


def test_sustain_attached_carrier_derives_location_and_saved_detach(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    game = _light_game(monkeypatch)
    offered = game.execute(
        Cast("light", point=Position(2, 2), attachment_actor_id="sorcerer_ally")
    )
    assert offered.status is ResultStatus.PAUSED
    choice = offered.inspection.choice
    assert choice is not None and choice.kind == "spell_willingness"
    game.choose(choice.choice_id, "willing", choice.owner_actor_id)
    orb_id = _orb_id(game)

    # Move the actual carrier; illumination follows it before Sustain runs.
    _advance_to(game, "sorcerer_ally")
    game.execute(Stride((Position(3, 2),)))
    _advance_to(game, "angelic_sorcerer")
    assert game.illumination_at(Position(3, 2)) == "bright"
    detached = game.execute(Sustain(orb_id))
    assert detached.status is ResultStatus.COMPLETED
    assert game._state.light_orbs[0] == replace(
        game._state.light_orbs[0], point=Position(3, 2), attached_actor_id=None
    )

    save_path = tmp_path / "light-detached.json"
    game.save(save_path)
    restored = Encounter.load(save_path)
    assert restored._state.light_orbs == game._state.light_orbs


def test_sustain_attachment_saves_willingness_and_decline_leaves_destination(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    game = _light_game(monkeypatch)
    game.execute(Cast("light", point=Position(1, 2), color="white"))
    orb_id = _orb_id(game)
    _advance_to(game, "angelic_sorcerer")
    offered = game.execute(Sustain(orb_id, attachment_actor_id="sorcerer_ally"))
    assert offered.status is ResultStatus.PAUSED
    assert offered.inspection.choice is not None

    save_path = tmp_path / "light-sustain-willingness.json"
    game.save(save_path)
    restored = Encounter.load(save_path)
    choice = restored.inspect().choice
    assert choice is not None and choice.kind == "spell_willingness"
    declined = restored.choose(choice.choice_id, "unwilling", choice.owner_actor_id)
    assert declined.status is ResultStatus.COMPLETED
    orb = restored._state.light_orbs[0]
    assert (orb.point, orb.attached_actor_id) == (Position(2, 2), None)


def test_sustain_and_dismiss_reject_foreign_or_stale_ids(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    game = _light_game(monkeypatch)
    game.execute(Cast("light", point=Position(1, 2), color="white"))
    orb_id = _orb_id(game)
    # This is a real active orb record whose caster is another actor; control
    # must remain owned by the Light caster.
    game._state.light_orbs.append(
        LightOrb("light:foreign:1", "sorcerer_dog", 1, "blue", point=Position(5, 2))
    )
    _advance_to(game, "angelic_sorcerer")
    before = game.inspect()
    for command in (Sustain("light:foreign:1", point=Position(2, 2)), Dismiss("light:foreign:1"), Sustain("light:stale", point=Position(2, 2))):
        result = game.execute(command)
        assert result.status is ResultStatus.REJECTED
        assert game.inspect() == before
    dismissed = game.execute(Dismiss(orb_id))
    assert dismissed.status is ResultStatus.COMPLETED
    assert all(orb.stable_id != orb_id for orb in game._state.light_orbs)


def test_fifth_light_replacement_requires_id_and_replaces_only_after_cast(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    game = _light_game(monkeypatch)
    points = (Position(0, 2), Position(1, 2), Position(2, 2), Position(3, 2))
    for index, point in enumerate(points):
        result = game.execute(Cast("light", point=point, color=f"color-{index}"))
        assert result.status is ResultStatus.COMPLETED
        if index < 3:
            _advance_to(game, "angelic_sorcerer")
    _advance_to(game, "angelic_sorcerer")
    before = game.inspect()
    missing = game.execute(Cast("light", point=Position(4, 2), color="fifth"))
    assert missing.status is ResultStatus.REJECTED
    assert game.inspect() == before
    stale = game.execute(
        Cast("light", point=Position(4, 2), color="fifth", replacement_orb_id="light:angelic_sorcerer:99")
    )
    assert stale.status is ResultStatus.REJECTED
    assert game.inspect() == before

    replaced = game.execute(
        Cast(
            "light",
            point=Position(4, 2),
            color="fifth",
            replacement_orb_id="light:angelic_sorcerer:1",
        )
    )
    assert replaced.status is ResultStatus.COMPLETED
    assert len(game._state.light_orbs) == 4
    assert "light:angelic_sorcerer:1" not in {orb.stable_id for orb in game._state.light_orbs}
    assert "light:angelic_sorcerer:5" in {orb.stable_id for orb in game._state.light_orbs}


def test_fifth_replacement_selection_survives_disrupted_reaction(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    setup = replace(
        ANGELIC_FEAR_REACTION_SETUP,
        setup_id="light_orb_replacement_reaction_fixture",
        ambient_light="dim",
        placements=tuple(
            replace(
                placement,
                definition_id=(
                    "light_low_light_fighter"
                    if placement.actor_id == "sorcerer_dog"
                    else placement.definition_id
                ),
                position=(
                    Position(2, 1)
                    if placement.actor_id == "angelic_sorcerer"
                    else placement.position
                ),
            )
            for placement in ANGELIC_FEAR_REACTION_SETUP.placements
        ),
    )
    low_light_fighter = replace(
        content.MELEE_FIGHTER_M,
        definition_id="light_low_light_fighter",
        vision="low_light",
        hero_points=0,
    )
    monkeypatch.setattr(
        content,
        "_STAGED_CREATURES",
        MappingProxyType({**content._STAGED_CREATURES, low_light_fighter.definition_id: low_light_fighter}),
    )
    monkeypatch.setattr(
        content,
        "_STAGED_SETUPS",
        MappingProxyType({**content._STAGED_SETUPS, setup.setup_id: setup}),
    )
    game = Encounter.start(setup, rolls=(20, 1, 1, 20, 1, 1, 1) * 60)
    _settle_start(game)

    for index in range(4):
        result = game.execute(
            Cast("light", point=Position(index + 2, 1), color=f"color-{index}")
        )
        assert result.status is ResultStatus.PAUSED
        choice = game.inspect().choice
        assert choice is not None and choice.kind == "reaction"
        game.choose(choice.choice_id, "decline", choice.owner_actor_id)
        if index < 3:
            _advance_to(game, "angelic_sorcerer")
    _advance_to(game, "angelic_sorcerer")

    offered = game.execute(
        Cast(
            "light",
            point=Position(6, 1),
            color="fifth",
            replacement_orb_id="light:angelic_sorcerer:1",
        )
    )
    assert offered.status is ResultStatus.PAUSED
    assert offered.inspection.choice is not None and offered.inspection.choice.kind == "reaction"
    assert {orb.stable_id for orb in game._state.light_orbs} == {
        "light:angelic_sorcerer:1",
        "light:angelic_sorcerer:2",
        "light:angelic_sorcerer:3",
        "light:angelic_sorcerer:4",
    }
    path = tmp_path / "light-replacement-reaction.json"
    game.save(path)
    restored = Encounter.load(path)
    choice = restored.inspect().choice
    assert choice is not None and choice.kind == "reaction"
    completed = restored.choose(choice.choice_id, "accept", choice.owner_actor_id)
    assert any(event.kind == "disrupted" for event in completed.events)
    assert {orb.stable_id for orb in restored._state.light_orbs} == {
        "light:angelic_sorcerer:1",
        "light:angelic_sorcerer:2",
        "light:angelic_sorcerer:3",
        "light:angelic_sorcerer:4",
    }
