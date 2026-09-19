"""Public declared-rest and daily-preparation coverage."""

from __future__ import annotations

import json
from copy import deepcopy
from dataclasses import replace
from pathlib import Path

import pytest

import pf2e.content as content
from pf2e.encounter import Encounter
from pf2e.model import Cast, CreaturePlacement, EndTurn, EncounterSetup, Position, ResultStatus, Strike, Stride
from pf2e.terminal import run_terminal
from terminal_test_helpers import BoundedTranscript


def _actor(game: Encounter, actor_id: str):
    return next(actor for actor in game.inspect().actors if actor.actor_id == actor_id)


def _choose(game: Encounter, option_id: str):
    choice = game.inspect().choice
    assert choice is not None
    return game.choose(choice.choice_id, option_id, choice.owner_actor_id)


def _settle_initiative(game: Encounter) -> None:
    while (choice := game.inspect().choice) is not None:
        assert choice.kind in {"initiative_hero_reroll", "initiative_tie"}
        option_id = "keep" if any(option.option_id == "keep" for option in choice.options) else choice.options[0].option_id
        assert _choose(game, option_id).status in {ResultStatus.PAUSED, ResultStatus.COMPLETED}


def _warpriest_setup(monkeypatch: pytest.MonkeyPatch) -> EncounterSetup:
    setup = replace(
        content.ANGELIC_FIRST_CAST_SETUP,
        setup_id="daily_preparation_first",
        name="Daily preparation first scene",
        placements=tuple(
            replace(
                placement,
                actor_id="warpriest",
                definition_id=content.WARPRIEST_C.definition_id,
                label="Iomedaean Warpriest",
            )
            if placement.actor_id == "sorcerer_ally"
            else placement
            for placement in content.ANGELIC_FIRST_CAST_SETUP.placements
        ),
    )
    monkeypatch.setattr(
        content,
        "_STAGED_SETUPS",
        content._STAGED_SETUPS | {setup.setup_id: setup},
    )
    return setup


def _warpriest_next_setup(monkeypatch: pytest.MonkeyPatch) -> EncounterSetup:
    setup = EncounterSetup(
        setup_id="daily_preparation_second",
        name="Daily preparation second scene",
        width=7,
        height=5,
        placements=(
            CreaturePlacement(
                "angelic_sorcerer",
                content.ANGELIC_SORCERER_STAGED.definition_id,
                "Angelic Sorcerer",
                "blue",
                Position(1, 1),
            ),
            CreaturePlacement(
                "warpriest",
                content.WARPRIEST_C.definition_id,
                "Iomedaean Warpriest",
                "blue",
                Position(1, 2),
            ),
            CreaturePlacement(
                "daily_dog_b",
                content.GUARD_DOG.definition_id,
                "Guard Dog B",
                "red",
                Position(5, 1),
            ),
        ),
    )
    monkeypatch.setattr(
        content,
        "_STAGED_SETUPS",
        content._STAGED_SETUPS | {setup.setup_id: setup},
    )
    return setup


def _finished_spent_resources_game(monkeypatch: pytest.MonkeyPatch) -> Encounter:
    setup = _warpriest_setup(monkeypatch)
    # Initiative; Halo's Blood Magic choice; two dog hits; Warpriest Heal;
    # saved attack choices; Sorcerer Heal; final Light and Strike choices.
    game = Encounter.start(
        setup,
        rolls=(20, 1, 10, 20, 3, 20, 3, 8, 15, 1, 4, 15, 1, 20, 1, 1, 8, 8, 20, 4, 4),
    )
    _settle_initiative(game)
    assert game.inspect().turn_actor_id == "angelic_sorcerer"

    halo = game.execute(Cast("angelic_halo", actions=1))
    assert halo.status is ResultStatus.PAUSED
    assert _choose(game, "warpriest").status is ResultStatus.COMPLETED
    light = game.execute(
        Cast(
            "light",
            point=Position(1, 2),
            color="sun-gold",
            attachment_actor_id="angelic_sorcerer",
        )
    )
    assert light.status is ResultStatus.PAUSED
    assert _choose(game, "willing").status is ResultStatus.COMPLETED
    assert game.inspect().turn_actor_id == "sorcerer_dog"
    assert game.execute(Stride((Position(4, 2), Position(3, 2)))).status is ResultStatus.COMPLETED
    assert game.execute(Strike("warpriest", attack_id="jaws")).status is ResultStatus.COMPLETED
    assert game.execute(Strike("warpriest", attack_id="jaws")).status is ResultStatus.COMPLETED
    assert game.inspect().turn_actor_id == "warpriest"

    prepared_heal = game.execute(Cast("heal", "warpriest", actions=2, slot_id="ordinary_heal_1"))
    assert prepared_heal.status is ResultStatus.PAUSED
    assert _choose(game, "willing").status is ResultStatus.COMPLETED
    assert game.execute(Strike("sorcerer_dog", attack_id="longsword")).status is ResultStatus.PAUSED
    assert _choose(game, "keep").status is ResultStatus.COMPLETED
    assert game.inspect().turn_actor_id == "angelic_sorcerer"
    spontaneous_heal = game.execute(Cast("heal", "warpriest", actions=2))
    assert spontaneous_heal.status is ResultStatus.PAUSED
    assert _choose(game, "angelic_sorcerer").status is ResultStatus.PAUSED
    assert _choose(game, "willing").status is ResultStatus.COMPLETED
    assert game.execute(EndTurn()).status is ResultStatus.COMPLETED
    assert game.inspect().turn_actor_id == "sorcerer_dog"
    assert game.execute(EndTurn()).status is ResultStatus.COMPLETED
    assert game.inspect().turn_actor_id == "warpriest"
    second_light = game.execute(
        Cast(
            "light",
            point=Position(2, 2),
            color="sun-gold",
            attachment_actor_id="warpriest",
        )
    )
    assert second_light.status is ResultStatus.PAUSED
    assert _choose(game, "willing").status is ResultStatus.COMPLETED
    final = game.execute(Strike("sorcerer_dog", attack_id="longsword"))
    if final.status is ResultStatus.PAUSED:
        assert _choose(game, "keep").status is ResultStatus.COMPLETED
        if game.inspect().choice is not None:
            assert _choose(game, "keep").status is ResultStatus.COMPLETED
    assert not game.inspect().in_progress
    assert _actor(game, "warpriest").hp > 0
    return game


def test_record_rested_save_load_prepares_and_casts_restored_resources_in_next_scene(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    game = _finished_spent_resources_game(monkeypatch)
    before = game.inspect()
    sorcerer_before = _actor(game, "angelic_sorcerer")
    warpriest_before = _actor(game, "warpriest")
    assert sorcerer_before.focus_points == 0
    assert sorcerer_before.spontaneous_slots[0].remaining == 2
    assert any(slot.spent for slot in warpriest_before.prepared_slots if slot.slot_id == "ordinary_heal_1")
    assert len(before.light_orbs) == 2

    recorded = game.record_rested(
        ("angelic_sorcerer", "warpriest"),
        day_number=2,
        elapsed_seconds=600,
    )
    assert recorded.status is ResultStatus.COMPLETED
    assert recorded.inspection.preparation_day == 2
    assert set(recorded.inspection.rested_actor_ids) == {"angelic_sorcerer", "warpriest"}
    rested_path = tmp_path / "daily-rest-eligibility.json"
    game.save(rested_path)
    restored = Encounter.load(rested_path)
    assert restored.inspect() == game.inspect()

    # A selected group shares the one-hour activity. This independent load
    # keeps the partial-caster assertions below available as well.
    grouped_game = Encounter.load(rested_path)
    group_before = grouped_game.inspect()
    group_hp = {actor_id: _actor(grouped_game, actor_id).hp for actor_id in ("angelic_sorcerer", "warpriest")}
    group_wounded = {actor_id: _actor(grouped_game, actor_id).wounded for actor_id in ("angelic_sorcerer", "warpriest")}
    group_equipment = {
        actor_id: (
            _actor(grouped_game, actor_id).held_items,
            _actor(grouped_game, actor_id).worn_items,
            _actor(grouped_game, actor_id).stowed_items,
            _actor(grouped_game, actor_id).ammunition,
        )
        for actor_id in ("angelic_sorcerer", "warpriest")
    }
    grouped = grouped_game.daily_prepare(("angelic_sorcerer", "warpriest"))
    assert grouped.status is ResultStatus.COMPLETED
    assert grouped.inspection.world_time_seconds == group_before.world_time_seconds + 3600
    assert not grouped_game.inspect().rested_actor_ids
    assert not grouped_game.inspect().light_orbs
    for actor_id in ("angelic_sorcerer", "warpriest"):
        assert _actor(grouped_game, actor_id).hp == group_hp[actor_id]
        assert _actor(grouped_game, actor_id).wounded == group_wounded[actor_id]
        assert (
            _actor(grouped_game, actor_id).held_items,
            _actor(grouped_game, actor_id).worn_items,
            _actor(grouped_game, actor_id).stowed_items,
            _actor(grouped_game, actor_id).ammunition,
        ) == group_equipment[actor_id]

    hp_before = {actor_id: _actor(restored, actor_id).hp for actor_id in ("angelic_sorcerer", "warpriest")}
    prepared = restored.daily_prepare(("warpriest",))
    assert prepared.status is ResultStatus.COMPLETED
    assert prepared.inspection.world_time_seconds == before.world_time_seconds + 600 + 3600
    assert _actor(restored, "warpriest").hp == hp_before["warpriest"]
    assert _actor(restored, "warpriest").wounded == _actor(game, "warpriest").wounded
    assert all(not slot.spent for slot in _actor(restored, "warpriest").prepared_slots)
    assert not any(orb.caster_actor_id == "warpriest" for orb in restored.inspect().light_orbs)
    assert any(orb.caster_actor_id == "angelic_sorcerer" for orb in restored.inspect().light_orbs)
    assert "warpriest" not in restored.inspect().rested_actor_ids
    assert "angelic_sorcerer" in restored.inspect().rested_actor_ids

    sorcerer_prepared = restored.daily_prepare(("angelic_sorcerer",))
    assert sorcerer_prepared.status is ResultStatus.COMPLETED
    assert _actor(restored, "angelic_sorcerer").focus_points == 1
    assert _actor(restored, "angelic_sorcerer").spontaneous_slots[0].remaining == 3
    assert not restored.inspect().light_orbs

    next_setup = _warpriest_next_setup(monkeypatch)
    transitioned = restored.next_encounter(next_setup)
    assert transitioned.status is ResultStatus.PAUSED
    _settle_initiative(restored)
    assert restored.inspect().turn_actor_id == "angelic_sorcerer"

    # Use every restored caster pool in the new scene: Focus Halo, the
    # spontaneous Heal, and the Warpriest's restored prepared Heal slot.
    halo = restored.execute(Cast("angelic_halo", actions=1))
    assert halo.status is ResultStatus.PAUSED
    assert _choose(restored, "warpriest").status is ResultStatus.COMPLETED
    assert _actor(restored, "angelic_sorcerer").focus_points == 0
    spontaneous = restored.execute(Cast("heal", "warpriest", actions=2))
    assert spontaneous.status is ResultStatus.PAUSED
    assert _choose(restored, "angelic_sorcerer").status is ResultStatus.PAUSED
    assert _choose(restored, "willing").status is ResultStatus.COMPLETED
    assert _actor(restored, "angelic_sorcerer").spontaneous_slots[0].remaining == 2

    assert restored.inspect().turn_actor_id == "warpriest"
    prepared_again = restored.execute(
        Cast("heal", "warpriest", actions=2, slot_id="ordinary_heal_1")
    )
    assert prepared_again.status is ResultStatus.PAUSED
    assert _choose(restored, "willing").status is ResultStatus.COMPLETED
    assert any(
        slot.slot_id == "ordinary_heal_1" and slot.spent
        for slot in _actor(restored, "warpriest").prepared_slots
    )

    assert restored.execute(EndTurn()).status is ResultStatus.COMPLETED
    assert restored.execute(EndTurn()).status is ResultStatus.COMPLETED
    assert restored.inspect().turn_actor_id == "angelic_sorcerer"
    assert restored.execute(Cast("divine_lance", "daily_dog_b")).status is ResultStatus.COMPLETED
    assert _actor(restored, "angelic_sorcerer").spontaneous_slots[0].remaining == 2
    assert _actor(restored, "daily_dog_b").defeated


def test_downtime_rejections_preserve_state_and_dice(monkeypatch: pytest.MonkeyPatch) -> None:
    game = Encounter.start(content.ANGELIC_FIRST_CAST_SETUP, rolls=(20, 1, 1))
    before = deepcopy(game._state)
    dice_before = game._dice.to_data()
    for result in (
        game.record_rested(("angelic_sorcerer",), day_number=2, elapsed_seconds=3600),
        game.daily_prepare(("angelic_sorcerer",)),
    ):
        assert result.status is ResultStatus.REJECTED
        assert game._state == before
        assert game._dice.to_data() == dice_before

    finished = _finished_spent_resources_game(monkeypatch)
    before = deepcopy(finished._state)
    dice_before = finished._dice.to_data()
    assert finished.daily_prepare(("angelic_sorcerer",)).status is ResultStatus.REJECTED
    assert finished._state == before
    assert finished._dice.to_data() == dice_before
    assert finished.record_rested(("angelic_sorcerer",), day_number=2, elapsed_seconds=0).status is ResultStatus.REJECTED
    assert finished._state == before
    assert finished._dice.to_data() == dice_before

    # Normalization, same-day repeat, retrogression, and an advancing day all
    # use the same transaction boundary.  A new declared day drops unused
    # eligibility from the preceding day before adding the new group.
    assert finished.record_rested(
        ("angelic_sorcerer", "warpriest"), day_number=2, elapsed_seconds=1
    ).status is ResultStatus.COMPLETED
    invalid_calls = (
        lambda: finished.record_rested(
            ("angelic_sorcerer", "angelic_sorcerer"), day_number=2, elapsed_seconds=1
        ),
        lambda: finished.record_rested(("sorcerer_dog",), day_number=2, elapsed_seconds=1),
        lambda: finished.record_rested(("angelic_sorcerer",), day_number=1, elapsed_seconds=1),
        lambda: finished.daily_prepare(("angelic_sorcerer", "angelic_sorcerer")),
    )
    for call in invalid_calls:
        before_invalid = deepcopy(finished._state)
        dice_before_invalid = finished._dice.to_data()
        invalid = call()
        assert invalid.status is ResultStatus.REJECTED
        assert finished._state == before_invalid
        assert finished._dice.to_data() == dice_before_invalid

    assert finished.daily_prepare(("angelic_sorcerer",)).status is ResultStatus.COMPLETED
    before_repeat = deepcopy(finished._state)
    dice_before_repeat = finished._dice.to_data()
    repeated = finished.daily_prepare(("angelic_sorcerer",))
    assert repeated.status is ResultStatus.REJECTED
    assert finished._state == before_repeat
    assert finished._dice.to_data() == dice_before_repeat

    assert finished.record_rested(("warpriest",), day_number=3, elapsed_seconds=1).status is ResultStatus.COMPLETED
    assert finished.inspect().preparation_day == 3
    assert finished.inspect().rested_actor_ids == ("warpriest",)

    before_stale = deepcopy(finished._state)
    dice_before_stale = finished._dice.to_data()
    stale = finished.daily_prepare(("angelic_sorcerer",))
    assert stale.status is ResultStatus.REJECTED
    assert finished._state == before_stale
    assert finished._dice.to_data() == dice_before_stale


def test_daily_preparation_save_validation_rejects_inexact_declared_facts(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    game = _finished_spent_resources_game(monkeypatch)
    assert game.record_rested(("angelic_sorcerer",), day_number=2, elapsed_seconds=1).status is ResultStatus.COMPLETED
    path = tmp_path / "strict-preparation.json"
    game.save(path)
    payload = json.loads(path.read_text(encoding="utf-8"))

    invalid_payloads = []
    invalid = deepcopy(payload)
    invalid["state"]["preparation_day"] = 0
    invalid_payloads.append(invalid)
    invalid = deepcopy(payload)
    invalid["state"]["rested_actor_ids"] = ["sorcerer_dog"]
    invalid_payloads.append(invalid)
    invalid = deepcopy(payload)
    invalid["state"]["last_prepared_day"] = {"angelic_sorcerer": 2}
    invalid_payloads.append(invalid)
    for index, candidate in enumerate(invalid_payloads):
        candidate_path = tmp_path / f"invalid-preparation-{index}.json"
        candidate_path.write_text(json.dumps(candidate), encoding="utf-8")
        with pytest.raises(ValueError):
            Encounter.load(candidate_path)


def test_terminal_distinguishes_declared_rest_from_daily_preparation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    setup = _warpriest_setup(monkeypatch)
    finished = _finished_spent_resources_game(monkeypatch)
    monkeypatch.setattr(Encounter, "start", classmethod(lambda _cls, *args, **kwargs: finished))
    transcript = BoundedTranscript()
    inputs = iter(("7", "1", "2", "1", "8", "1", "6"))
    status = run_terminal(
        setup=setup,
        input_fn=lambda: next(inputs),
        output_fn=transcript.append,
    )
    rendered = "\n".join(transcript)
    assert status == 0
    assert "Record Rested Eligibility" in rendered
    assert "Daily Preparation" in rendered
    assert "declares external rest facts; it does not simulate sleep" in rendered
    assert "advances one hour once, restores the selected casters' actual spell and Focus resources" in rendered
    assert "Daily preparation completed" in rendered
    assert finished.inspect().preparation_day == 2
    assert finished.inspect().rested_actor_ids == ()
