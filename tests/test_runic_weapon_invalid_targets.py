"""Public invalid-target checks for the rank-1 Runic Weapon cast."""
from __future__ import annotations

from dataclasses import dataclass, replace
from types import MappingProxyType

import pytest

import pf2e.content as content
from pf2e import Cast, Encounter, Position, ResultStatus
from pf2e.content import (
    ANGELIC_FIRST_CAST_SETUP,
    RUNE_ARMOR_FIGHTER_M,
    STEEL_SHIELD_FIGHTER_M,
    WEAPON_IDENTITY_FIGHTER_M,
)


@dataclass(frozen=True)
class _InvalidTargetCase:
    setup: object
    item_ids: tuple[str | None, ...]
    target_id: str | None
    message: str
    definition: object | None = None


def _setup_for(
    setup_id: str,
    *,
    ally_definition_id: str = WEAPON_IDENTITY_FIGHTER_M.definition_id,
    ally_position: Position = Position(2, 2),
):
    return replace(
        ANGELIC_FIRST_CAST_SETUP,
        setup_id=setup_id,
        placements=tuple(
            replace(
                placement,
                definition_id=ally_definition_id,
                position=ally_position,
            )
            if placement.actor_id == "sorcerer_ally" else placement
            for placement in ANGELIC_FIRST_CAST_SETUP.placements
        ),
    )


_STOWED_LONGSWORD = replace(
    WEAPON_IDENTITY_FIGHTER_M,
    definition_id="runic_invalid_stowed_longsword",
    name="Runic Weapon invalid stowed longsword fixture",
    held_items=(),
    stowed_items=("longsword",),
)


_CASES = (
    pytest.param(
        _InvalidTargetCase(
            _setup_for(
                "runic_invalid_out_of_touch",
                ally_position=Position(3, 2),
            ),
            ("sorcerer_ally:longsword",),
            None,
            "outside touch range",
        ),
        id="outside-touch-range",
    ),
    pytest.param(
        _InvalidTargetCase(
            _setup_for(
                "runic_invalid_stowed",
                ally_definition_id=_STOWED_LONGSWORD.definition_id,
            ),
            ("sorcerer_ally:longsword",),
            None,
            "wielded or unattended",
            definition=_STOWED_LONGSWORD,
        ),
        id="stowed-longsword",
    ),
    pytest.param(
        _InvalidTargetCase(
            _setup_for(
                "runic_invalid_shield",
                ally_definition_id=STEEL_SHIELD_FIGHTER_M.definition_id,
            ),
            ("sorcerer_ally:steel_shield",),
            None,
            "only a longsword, shortsword, or staff",
        ),
        id="shield-is-not-a-weapon-target",
    ),
    pytest.param(
        _InvalidTargetCase(
            _setup_for(
                "runic_invalid_armor",
                ally_definition_id=RUNE_ARMOR_FIGHTER_M.definition_id,
            ),
            ("sorcerer_ally:breastplate",),
            None,
            "only a longsword, shortsword, or staff",
        ),
        id="armor-is-not-a-weapon-target",
    ),
    pytest.param(
        _InvalidTargetCase(
            _setup_for("runic_invalid_item_ids"),
            (None, "sorcerer_ally:missing-item"),
            None,
            "",
        ),
        id="missing-or-unknown-item-id",
    ),
    pytest.param(
        _InvalidTargetCase(
            _setup_for("runic_invalid_conflicting_targets"),
            ("sorcerer_ally:longsword",),
            "sorcerer_dog",
            "physical weapon through item_id",
        ),
        id="creature-and-item-target-conflict",
    ),
)


def _register_test_content(monkeypatch: pytest.MonkeyPatch, case: _InvalidTargetCase) -> None:
    creatures = dict(content._STAGED_CREATURES)
    if case.definition is not None:
        creatures[case.definition.definition_id] = case.definition
    setups = dict(content._STAGED_SETUPS)
    setups[case.setup.setup_id] = case.setup
    monkeypatch.setattr(content, "_STAGED_CREATURES", MappingProxyType(creatures))
    monkeypatch.setattr(content, "_STAGED_SETUPS", MappingProxyType(setups))


def _start_at_caster_turn(case: _InvalidTargetCase) -> Encounter:
    game = Encounter.start(case.setup, rolls=(20, 1, 1))
    while (choice := game.inspect().choice) is not None:
        option_id = (
            "keep"
            if any(option.option_id == "keep" for option in choice.options)
            else choice.options[0].option_id
        )
        result = game.choose(choice.choice_id, option_id, choice.owner_actor_id)
        assert result.status is ResultStatus.COMPLETED
    assert game.inspect().turn_actor_id == "angelic_sorcerer"
    return game


def _save_bytes(game: Encounter, path) -> bytes:
    game.save(path)
    return path.read_bytes()


@pytest.mark.parametrize("case", _CASES)
def test_invalid_runic_weapon_targets_reject_atomically(
    case: _InvalidTargetCase,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    _register_test_content(monkeypatch, case)
    game = _start_at_caster_turn(case)
    before_inspection = game.inspect()
    before_path = tmp_path / "before.json"
    before_save = _save_bytes(game, before_path)

    for index, item_id in enumerate(case.item_ids):
        result = game.execute(
            Cast(
                "runic_weapon",
                target_id=case.target_id,
                item_id=item_id,
                slot_id="angelic_rank1",
            )
        )
        assert result.status is ResultStatus.REJECTED
        if case.message:
            assert case.message in result.message
        elif item_id is None:
            assert "requires an explicit physical weapon item_id" in result.message
        else:
            assert "not a physical item instance" in result.message
        assert game.inspect() == before_inspection
        after_save = _save_bytes(game, tmp_path / f"after-{index}.json")
        assert after_save == before_save
