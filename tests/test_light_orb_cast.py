"""Focused first-stage Light point-cast and orb persistence checks."""

from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

import pytest
import pf2e.content as content

from pf2e import Cast, Encounter, EndTurn, Position, ResultStatus, Strike
from pf2e.content import ANGELIC_FIRST_CAST_SETUP, ANGELIC_FEAR_REACTION_SETUP
from pf2e.model import AttackDefinition


def _settle_start(game: Encounter) -> None:
    while (choice := game.inspect().choice) is not None:
        option = "keep" if any(item.option_id == "keep" for item in choice.options) else choice.options[0].option_id
        result = game.choose(choice.choice_id, option, choice.owner_actor_id)
        assert result.status in {ResultStatus.PAUSED, ResultStatus.COMPLETED}


def _light_game(monkeypatch: pytest.MonkeyPatch, *, rolls: tuple[int, ...] = (20, 1, 1, 20, 1, 1, 1)) -> Encounter:
    setup = replace(
        ANGELIC_FIRST_CAST_SETUP,
        setup_id="light_orb_cast_fixture",
        ambient_light="dim",
    )
    monkeypatch.setattr(
        content,
        "_STAGED_SETUPS",
        content.MappingProxyType({**content._STAGED_SETUPS, setup.setup_id: setup}),
    )
    game = Encounter.start(setup, rolls=rolls)
    _settle_start(game)
    assert game.inspect().turn_actor_id == "angelic_sorcerer"
    return game


def _actor(game: Encounter, actor_id: str):
    return next(actor for actor in game.inspect().actors if actor.actor_id == actor_id)


def test_light_point_cast_creates_bright_orb_and_dim_falloff(monkeypatch: pytest.MonkeyPatch) -> None:
    game = _light_game(monkeypatch)

    before = _actor(game, "angelic_sorcerer")
    before_slots = before.spontaneous_slots
    before_focus = before.focus_points
    result = game.execute(Cast("light", point=Position(0, 2), color="red"))
    after = _actor(game, "angelic_sorcerer")

    assert result.status is ResultStatus.COMPLETED
    assert [event.kind for event in result.events] == ["cast_started", "light_orb_created"]
    assert (after.actions_remaining, len(game._state.light_orbs)) == (1, 1)
    assert after.spontaneous_slots == before_slots
    assert after.focus_points == before_focus
    assert all(event.kind != "blood_magic_choice" for event in result.events)
    orb = game._state.light_orbs[0]
    assert (orb.stable_id, orb.caster_actor_id, orb.rank, orb.color, orb.point) == (
        "light:angelic_sorcerer:1", "angelic_sorcerer", 1, "red", Position(0, 2)
    )
    assert game.illumination_at(Position(0, 2)) == "bright"
    assert game.illumination_at(Position(4, 2)) == "bright"
    assert game.illumination_at(Position(5, 2)) == "dim"
    assert game.target_illumination("angelic_sorcerer", "sorcerer_dog") == "dim"


def test_light_point_cast_save_load_preserves_orb_record(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    game = _light_game(monkeypatch)
    result = game.execute(Cast("light", point=Position(0, 2), color="amber"))
    assert result.status is ResultStatus.COMPLETED

    path = tmp_path / "light.json"
    game.save(path)
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["save_version"] == 18
    assert payload["state"]["light_orbs"] == [
        ["light:angelic_sorcerer:1", "angelic_sorcerer", 1, "amber", [0, 2], None, 0]
    ]
    restored = Encounter.load(path)
    assert restored.inspect() == game.inspect()
    assert restored._state.light_orbs == game._state.light_orbs


def test_light_point_range_rejection_is_atomic(monkeypatch: pytest.MonkeyPatch) -> None:
    setup = replace(
        ANGELIC_FIRST_CAST_SETUP,
        setup_id="light_orb_long_range_fixture",
        width=26,
        height=5,
        ambient_light="dim",
    )
    monkeypatch.setattr(
        content,
        "_STAGED_SETUPS",
        content.MappingProxyType({**content._STAGED_SETUPS, setup.setup_id: setup}),
    )
    game = Encounter.start(setup, rolls=(20, 1, 1, 20, 1, 1, 1))
    _settle_start(game)
    before = game.inspect()
    before_dice = game._dice._index
    result = game.execute(Cast("light", point=Position(25, 4), color="white"))
    assert result.status is ResultStatus.REJECTED
    assert "120-foot range" in result.message
    assert game.inspect() == before
    assert game._dice._index == before_dice
    assert game._state.light_orbs == []


def test_light_attachment_saved_and_accepted_or_declined(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    game = _light_game(monkeypatch)
    offered = game.execute(
        Cast(
            "light",
            point=Position(2, 2),
            color="blue",
            attachment_actor_id="sorcerer_ally",
        )
    )
    assert offered.status is ResultStatus.PAUSED
    choice = offered.inspection.choice
    assert choice is not None and choice.kind == "spell_willingness"
    save_path = tmp_path / "light-willingness.json"
    game.save(save_path)
    restored = Encounter.load(save_path)
    assert restored.inspect() == offered.inspection
    pending = restored.inspect().choice
    assert pending is not None
    accepted = restored.choose(pending.choice_id, "willing", pending.owner_actor_id)
    assert accepted.status is ResultStatus.COMPLETED
    orb = restored._state.light_orbs[0]
    assert (orb.point, orb.attached_actor_id) == (None, "sorcerer_ally")
    assert restored.illumination_at(Position(2, 2)) == "bright"

    refused_game = _light_game(monkeypatch)
    refused = refused_game.execute(
        Cast(
            "light",
            point=Position(2, 2),
            color="green",
            attachment_actor_id="sorcerer_ally",
        )
    )
    refused_path = tmp_path / "light-unwilling.json"
    refused_game.save(refused_path)
    refused_game = Encounter.load(refused_path)
    pending = refused_game.inspect().choice
    assert pending is not None and pending.kind == "spell_willingness"
    declined = refused_game.choose(pending.choice_id, "unwilling", pending.owner_actor_id)
    assert declined.status is ResultStatus.COMPLETED
    orb = refused_game._state.light_orbs[0]
    assert (orb.point, orb.attached_actor_id) == (Position(2, 2), None)


def test_light_critical_reaction_disruption_spends_actions_without_orb(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    setup = replace(
        ANGELIC_FEAR_REACTION_SETUP,
        setup_id="light_orb_reaction_fixture",
        ambient_light="dim",
        placements=tuple(
            replace(
                placement,
                definition_id=("light_low_light_fighter" if placement.actor_id == "sorcerer_dog" else placement.definition_id),
                position=(Position(2, 1) if placement.actor_id == "angelic_sorcerer" else placement.position),
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
        content.MappingProxyType({**content._STAGED_CREATURES, low_light_fighter.definition_id: low_light_fighter}),
    )
    monkeypatch.setattr(
        content,
        "_STAGED_SETUPS",
        content.MappingProxyType({**content._STAGED_SETUPS, setup.setup_id: setup}),
    )
    # Sorcerer wins initiative; the dog is adjacent and can critically
    # disrupt the concentrate/manipulate cast through the ordinary reaction.
    game = Encounter.start(setup, rolls=(20, 1, 1, 20, 1, 1, 1))
    _settle_start(game)
    offered = game.execute(Cast("light", point=Position(2, 1), color="white"))
    assert offered.status is ResultStatus.PAUSED
    reaction = offered.inspection.choice
    assert reaction is not None and reaction.kind == "reaction"
    accepted = game.choose(reaction.choice_id, "accept", reaction.owner_actor_id)
    assert accepted.status is ResultStatus.COMPLETED
    assert any(event.kind == "disrupted" for event in accepted.events)
    assert game._state.light_orbs == []
    assert _actor(game, "angelic_sorcerer").actions_remaining == 1


def test_light_fifth_cast_rejects_before_cost(monkeypatch: pytest.MonkeyPatch) -> None:
    game = _light_game(monkeypatch)
    points = (Position(0, 2), Position(1, 2), Position(2, 2), Position(3, 2))
    for index, point in enumerate(points):
        result = game.execute(Cast("light", point=point, color=f"color-{index}"))
        assert result.status is ResultStatus.COMPLETED
        if index < len(points) - 1:
            # A point cast costs two of the caster's three actions. End the
            # remaining action before advancing through the other actors.
            ended = game.execute(EndTurn())
            assert ended.status is ResultStatus.COMPLETED
            while game.inspect().turn_actor_id != "angelic_sorcerer":
                ended = game.execute(EndTurn())
                assert ended.status is ResultStatus.COMPLETED
    assert len(game._state.light_orbs) == 4
    ended = game.execute(EndTurn())
    assert ended.status is ResultStatus.COMPLETED
    while game.inspect().turn_actor_id != "angelic_sorcerer":
        ended = game.execute(EndTurn())
        assert ended.status is ResultStatus.COMPLETED
    before = game.inspect()
    fifth = game.execute(Cast("light", point=Position(4, 2), color="white"))
    assert fifth.status is ResultStatus.REJECTED
    assert "four active Light orbs" in fifth.message
    assert game.inspect() == before


def test_light_brightens_actual_strike_target_and_dim_target_hits_dc5(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The shared Strike concealment gate reads the active orb query."""
    ranged_caster = replace(
        content.ANGELIC_SORCERER_STAGED,
        definition_id="light_ranged_sorcerer",
        hero_points=0,
        attacks=(
            AttackDefinition(
                attack_id="light_ray",
                name="Light ray",
                modifier=5,
                reach_ft=0,
                traits=frozenset({"attack", "ranged"}),
                damage_type="bludgeoning",
                damage_dice=(4,),
                damage_modifier=1,
                range_increment_ft=30,
                max_range_ft=120,
            ),
        ),
    )
    monkeypatch.setattr(
        content,
        "_STAGED_CREATURES",
        content.MappingProxyType({**content._STAGED_CREATURES, ranged_caster.definition_id: ranged_caster}),
    )
    setup = replace(
        ANGELIC_FIRST_CAST_SETUP,
        setup_id="light_orb_strike_fixture",
        ambient_light="dim",
        placements=tuple(
            replace(
                placement,
                definition_id=ranged_caster.definition_id
                if placement.actor_id == "angelic_sorcerer"
                else placement.definition_id,
            )
            for placement in ANGELIC_FIRST_CAST_SETUP.placements
        ),
    )
    monkeypatch.setattr(
        content,
        "_STAGED_SETUPS",
        content.MappingProxyType({**content._STAGED_SETUPS, setup.setup_id: setup}),
    )

    bright_game = Encounter.start(setup, rolls=(20, 1, 1, 20, 1, 1, 10, 1))
    _settle_start(bright_game)
    cast = bright_game.execute(Cast("light", point=Position(1, 2), color="white"))
    assert cast.status is ResultStatus.COMPLETED
    assert bright_game.target_illumination("angelic_sorcerer", "sorcerer_dog") == "bright"
    bright_strike = bright_game.execute(Strike("sorcerer_dog", attack_id="light_ray"))
    assert bright_strike.status is ResultStatus.COMPLETED
    assert not any(event.kind == "concealment_flat_check" for event in bright_strike.events)
    assert any(event.kind == "strike" for event in bright_strike.events)

    dim_game = Encounter.start(setup, rolls=(20, 1, 1, 4, 1))
    _settle_start(dim_game)
    # With only ambient dim, the same public Strike path must use its DC 5
    # gate. This is the outside-the-orb comparison for the cast above.
    dim_strike = dim_game.execute(Strike("sorcerer_dog", attack_id="light_ray"))
    assert dim_strike.status is ResultStatus.COMPLETED
    assert any(event.kind == "concealment_flat_check" for event in dim_strike.events)
    assert any(event.kind == "concealment_failed" for event in dim_strike.events)
