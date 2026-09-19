"""Independent public-path review regressions for rank-1 Runic Weapon."""

from __future__ import annotations

from dataclasses import replace
import json
from pathlib import Path
from types import MappingProxyType

import pytest

import pf2e.content as content
from pf2e import Cast, Encounter, EndTurn, Position, ResultStatus, Strike, Stride
from pf2e.content import ANGELIC_FIRST_CAST_SETUP, GUARD_DOG


def _settle_initiative(game: Encounter) -> None:
    while (choice := game.inspect().choice) is not None:
        assert choice.kind == "initiative_hero_reroll"
        game.choose(choice.choice_id, "keep", choice.owner_actor_id)


def _actor(game: Encounter, actor_id: str):
    return next(actor for actor in game.inspect().actors if actor.actor_id == actor_id)


def test_refused_committed_runic_weapon_still_traverses_saved_manipulate_reaction(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Refusal stops the effect, not the trigger from the spent manipulate cast."""
    reactive_dog = replace(
        GUARD_DOG,
        definition_id="runic_review_reactive_dog",
        abilities=("reactive_strike",),
        hp=30,
    )
    setup = replace(
        ANGELIC_FIRST_CAST_SETUP,
        setup_id="runic_review_refusal_reaction",
        name="Runic Weapon refusal reaction review",
        placements=tuple(
            replace(
                placement,
                definition_id=reactive_dog.definition_id,
                position=Position(1, 1),
            )
            if placement.actor_id == "sorcerer_dog"
            else placement
            for placement in ANGELIC_FIRST_CAST_SETUP.placements
        ),
    )
    monkeypatch.setattr(
        content,
        "_STAGED_CREATURES",
        MappingProxyType(
            {**content._STAGED_CREATURES, reactive_dog.definition_id: reactive_dog}
        ),
    )
    monkeypatch.setattr(
        content,
        "_STAGED_SETUPS",
        MappingProxyType({**content._STAGED_SETUPS, setup.setup_id: setup}),
    )

    game = Encounter.start(setup, rolls=(20, 1, 1))
    _settle_initiative(game)
    offered = game.execute(
        Cast(
            "runic_weapon",
            item_id="sorcerer_ally:longsword",
            slot_id="angelic_rank1",
        )
    )
    willingness = offered.inspection.choice
    assert offered.status is ResultStatus.PAUSED
    assert willingness is not None and willingness.kind == "spell_willingness"

    refused = game.choose(
        willingness.choice_id,
        "unwilling",
        willingness.owner_actor_id,
    )
    reaction = refused.inspection.choice
    assert refused.status is ResultStatus.PAUSED
    assert reaction is not None and reaction.kind == "reaction"
    assert reaction.owner_actor_id == "sorcerer_dog"
    caster = _actor(game, "angelic_sorcerer")
    assert caster.actions_remaining == 1
    assert caster.spontaneous_slots[0].remaining == 2

    pending_path = tmp_path / "refused-runic-reaction.json"
    game.save(pending_path)
    saved = json.loads(pending_path.read_text(encoding="utf-8"))
    continuation = saved["state"]["pending_choice"]["continuation"]
    assert continuation["spell_target_item_id"] == "sorcerer_ally:longsword"
    assert continuation["reaction_trigger"] == "manipulate"
    restored = Encounter.load(pending_path)
    assert restored.inspect() == game.inspect()

    completed = restored.choose(
        reaction.choice_id,
        "decline",
        reaction.owner_actor_id,
    )
    assert completed.status is ResultStatus.COMPLETED
    assert completed.inspection.choice is None
    assert not any(event.kind == "item_effect_applied" for event in completed.events)
    caster = _actor(restored, "angelic_sorcerer")
    assert caster.actions_remaining == 1
    assert caster.spontaneous_slots[0].remaining == 2

    resolved_path = tmp_path / "refused-runic-resolved.json"
    restored.save(resolved_path)
    resolved = json.loads(resolved_path.read_text(encoding="utf-8"))
    assert resolved["state"]["active_item_effects"] == []


def test_runic_weapon_remains_live_at_round_wrap_until_the_casters_tenth_start(
    tmp_path: Path,
) -> None:
    """A one-minute combat duration expires on its source-start boundary."""
    # The ally acts before the caster. At the round-11 wrap the world clock
    # reaches 60 seconds, but the caster's tenth post-cast start has not yet
    # happened, so the ally gets one last enhanced Strike.
    game = Encounter.start(ANGELIC_FIRST_CAST_SETUP, rolls=(10, 20, 1, 1))
    _settle_initiative(game)
    assert game.inspect().turn_actor_id == "sorcerer_ally"
    assert game.execute(
        Stride((Position(3, 2), Position(4, 2)))
    ).status is ResultStatus.COMPLETED
    assert game.execute(EndTurn()).status is ResultStatus.COMPLETED
    assert game.inspect().turn_actor_id == "angelic_sorcerer"
    assert game.execute(
        Stride((Position(2, 2), Position(3, 2)))
    ).status is ResultStatus.COMPLETED

    offered = game.execute(
        Cast(
            "runic_weapon",
            item_id="sorcerer_ally:longsword",
            slot_id="angelic_rank1",
        )
    )
    willingness = offered.inspection.choice
    assert offered.status is ResultStatus.PAUSED
    assert willingness is not None and willingness.kind == "spell_willingness"
    assert game.choose(
        willingness.choice_id,
        "willing",
        willingness.owner_actor_id,
    ).status is ResultStatus.COMPLETED
    assert game.execute(EndTurn()).status is ResultStatus.COMPLETED

    while not (
        game.inspect().round_number == 11
        and game.inspect().turn_actor_id == "sorcerer_ally"
    ):
        assert game.execute(EndTurn()).status is ResultStatus.COMPLETED

    wrapped_path = tmp_path / "runic-round-wrap.json"
    game.save(wrapped_path)
    wrapped = json.loads(wrapped_path.read_text(encoding="utf-8"))
    assert wrapped["state"]["world_time_seconds"] == 60
    assert len(wrapped["state"]["active_item_effects"]) == 1

    strike = game.execute(
        Strike(
            "sorcerer_dog",
            attack_id="longsword",
            item_id="sorcerer_ally:longsword",
        )
    )
    assert strike.status is ResultStatus.PAUSED
    check = next(event.check for event in strike.events if event.check is not None)
    assert check is not None and check.modifier == 10
    reroll = strike.inspection.choice
    assert reroll is not None and reroll.kind == "attack_hero_reroll"
    assert game.choose(
        reroll.choice_id,
        "keep",
        reroll.owner_actor_id,
    ).status is ResultStatus.COMPLETED

    assert game.execute(EndTurn()).status is ResultStatus.COMPLETED
    assert game.inspect().turn_actor_id == "angelic_sorcerer"
    expired_path = tmp_path / "runic-source-start-expired.json"
    game.save(expired_path)
    expired = json.loads(expired_path.read_text(encoding="utf-8"))
    assert expired["state"]["world_time_seconds"] == 60
    assert expired["state"]["active_item_effects"] == []
