"""Public finite-preparation consistency coverage."""

from __future__ import annotations

import pytest
from pf2e.model import ResultStatus
from test_daily_preparation import _finished_spent_resources_game


def _fixed_warpriest(monkeypatch: pytest.MonkeyPatch):
    game = _finished_spent_resources_game(monkeypatch)
    assert game.record_rested(("warpriest",), day_number=2, elapsed_seconds=1).status is ResultStatus.COMPLETED
    return game


def test_fixed_preparer_rejects_an_arbitrary_slot_replacement(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    game = _fixed_warpriest(monkeypatch)
    choices = {
        slot.slot_id: slot.spell_id
        for slot in game._state.creatures["warpriest"].prepared_slots
    }
    choices["ordinary_heal_1"] = "force_barrage"
    before = game.inspect()
    dice_before = game._dice.to_data()

    result = game.daily_prepare(("warpriest",), {"warpriest": choices})

    assert result.status is ResultStatus.REJECTED
    assert game.inspect() == before
    assert game._dice.to_data() == dice_before
