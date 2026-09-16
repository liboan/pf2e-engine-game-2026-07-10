"""Public prepared-Light coverage for the fixed Warpriest sheet."""

from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path
from types import MappingProxyType

import pytest

import pf2e.content as content
from pf2e import Cast, Encounter, EndTurn, Position, ResultStatus
from pf2e.model import CreaturePlacement


def _settle_start(game: Encounter) -> None:
    while (choice := game.inspect().choice) is not None:
        option = "keep" if any(item.option_id == "keep" for item in choice.options) else choice.options[0].option_id
        result = game.choose(choice.choice_id, option, choice.owner_actor_id)
        assert result.status in {ResultStatus.PAUSED, ResultStatus.COMPLETED}


def _actor(game: Encounter, actor_id: str):
    return next(actor for actor in game.inspect().actors if actor.actor_id == actor_id)


def _advance_to(game: Encounter, actor_id: str) -> None:
    while game.inspect().turn_actor_id != actor_id:
        result = game.execute(EndTurn())
        assert result.status is ResultStatus.COMPLETED


def _warpriest_dim_setup(monkeypatch: pytest.MonkeyPatch):
    setup = replace(
        content.S3_SETUP,
        setup_id="warpriest_light_fixture",
        name="Warpriest prepared Light fixture",
        width=7,
        height=3,
        ambient_light="dim",
        placements=(
            CreaturePlacement(
                "cleric_c", content.WARPRIEST_C.definition_id, "Warpriest C", "blue", Position(1, 1)
            ),
            CreaturePlacement(
                "guard_dog", content.GUARD_DOG.definition_id, "Guard Dog", "red", Position(5, 1)
            ),
        ),
    )
    monkeypatch.setattr(
        content,
        "_STAGED_SETUPS",
        MappingProxyType({**content._STAGED_SETUPS, setup.setup_id: setup}),
    )
    return setup


def test_warpriest_fixed_preparation_uses_light_and_preserves_heal_slots() -> None:
    assert (content.WARPRIEST_C.ancestry, content.WARPRIEST_C.heritage) == (
        "Human",
        "Skilled Human",
    )
    assert content.WARPRIEST_C.vision == "ordinary"
    prepared = content.WARPRIEST_C.prepared_spells

    assert tuple(slot.spell_id for slot in prepared) == (
        "divine_lance",
        "void_warp",
        "guidance",
        "stabilize",
        "light",
        "heal",
        "heal",
        "heal",
        "heal",
        "heal",
        "heal",
    )
    assert tuple(slot.slot_id for slot in prepared[5:]) == (
        "ordinary_heal_1",
        "ordinary_heal_2",
        "font_heal_1",
        "font_heal_2",
        "font_heal_3",
        "font_heal_4",
    )
    assert tuple(slot.source for slot in prepared[5:]) == (
        "ordinary",
        "ordinary",
        "font",
        "font",
        "font",
        "font",
    )


def test_warpriest_public_light_saves_willingness_repeats_and_brightens_target(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    setup = _warpriest_dim_setup(monkeypatch)
    game = Encounter.start(setup, rolls=(20, 19))
    _settle_start(game)
    _advance_to(game, "cleric_c")

    assert game.target_illumination("cleric_c", "guard_dog") == "dim"
    assert game.target_is_concealed("cleric_c", "guard_dog")
    before_slots = _actor(game, "cleric_c").prepared_slots

    offered = game.execute(
        Cast(
            "light",
            point=Position(1, 1),
            color="amber",
            attachment_actor_id="cleric_c",
        )
    )
    assert offered.status is ResultStatus.PAUSED
    assert [event.kind for event in offered.events] == [
        "cast_started",
        "light_orb_created",
        "spell_willingness",
    ]
    choice = offered.inspection.choice
    assert choice is not None and choice.kind == "spell_willingness"
    assert choice.owner_actor_id == "cleric_c"

    save_path = tmp_path / "warpriest-light-willingness.json"
    game.save(save_path)
    payload = json.loads(save_path.read_text(encoding="utf-8"))
    assert payload["dice"]["kind"] == "sequence"
    assert payload["dice"]["index"] == game._dice._index
    restored = Encounter.load(save_path)
    assert restored.inspect() == offered.inspection

    accepted = restored.choose(choice.choice_id, "willing", choice.owner_actor_id)
    assert accepted.status is ResultStatus.COMPLETED
    orb = restored._state.light_orbs[0]
    assert (orb.point, orb.attached_actor_id) == (None, "cleric_c")
    assert restored.target_illumination("cleric_c", "guard_dog") == "bright"
    assert not restored.target_is_concealed("cleric_c", "guard_dog")
    assert _actor(restored, "cleric_c").prepared_slots == before_slots

    # Light is a repeatable prepared cantrip: on a later turn it creates a
    # second orb while every ordinary and font Heal slot remains untouched.
    assert restored.execute(EndTurn()).status is ResultStatus.COMPLETED
    _advance_to(restored, "cleric_c")
    repeated = restored.execute(
        Cast("light", point=Position(0, 1), color="white")
    )
    assert repeated.status is ResultStatus.COMPLETED
    assert len(restored._state.light_orbs) == 2
    assert _actor(restored, "cleric_c").prepared_slots == before_slots


def test_old_read_aura_preparation_save_is_rejected_without_migration(tmp_path: Path) -> None:
    game = Encounter.start(content.S3_SETUP, rolls=(20, 19, 18, 17, 16, 15))
    _settle_start(game)
    save_path = tmp_path / "old-read-aura-preparation.json"
    game.save(save_path)

    payload = json.loads(save_path.read_text(encoding="utf-8"))
    slots = payload["state"]["creatures"]["cleric_c"]["prepared_slots"]
    light_slot = next(row for row in slots if row[0] == "cantrip_light")
    light_slot[0] = "cantrip_read_aura"
    light_slot[2] = "read_aura"
    save_path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(ValueError, match="invalid prepared slot facts"):
        Encounter.load(save_path)
