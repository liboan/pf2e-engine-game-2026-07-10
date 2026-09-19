"""Focused public scene carry and second encounter play."""

from __future__ import annotations

import json
from pathlib import Path

from pf2e.content import ANGELIC_FIRST_CAST_SETUP, ANGELIC_NEXT_ENCOUNTER_SETUP
from pf2e.encounter import Encounter
from pf2e.model import Cast, EndTurn, Position, ResultStatus, Strike, Stride


def _actor(game: Encounter, actor_id: str):
    return next(actor for actor in game.inspect().actors if actor.actor_id == actor_id)


def _choose(game: Encounter, option_id: str):
    choice = game.inspect().choice
    assert choice is not None
    result = game.choose(choice.choice_id, option_id, choice.owner_actor_id)
    assert result.status in {ResultStatus.PAUSED, ResultStatus.COMPLETED}
    return result


def _keep_start_choices(game: Encounter) -> None:
    while (choice := game.inspect().choice) is not None:
        option_id = (
            "keep"
            if any(option.option_id == "keep" for option in choice.options)
            else choice.options[0].option_id
        )
        _choose(game, option_id)


def _complete_first_scene(game: Encounter) -> None:
    _keep_start_choices(game)
    halo = game.execute(Cast("angelic_halo", actions=1))
    assert halo.status is ResultStatus.PAUSED
    assert halo.inspection.choice is not None
    assert halo.inspection.choice.kind == "spell_blood_magic_recipient"
    _choose(game, "sorcerer_ally")

    # Use the remaining two actions to create Light and attach it to the
    # Fighter. This is the object that the scene transition must carry.
    light = game.execute(
        Cast(
            "light",
            point=Position(2, 2),
            color="sun-gold",
            attachment_actor_id="sorcerer_ally",
        )
    )
    assert light.status is ResultStatus.PAUSED
    assert light.inspection.choice is not None
    assert light.inspection.choice.kind == "spell_willingness"
    _choose(game, "willing")

    assert game.inspect().turn_actor_id == "sorcerer_dog"
    assert game.execute(Stride((Position(4, 2), Position(3, 2)))).status is ResultStatus.COMPLETED
    assert game.execute(Strike("sorcerer_ally", attack_id="jaws")).status is ResultStatus.COMPLETED
    assert game.execute(Strike("sorcerer_ally", attack_id="jaws")).status is ResultStatus.COMPLETED
    assert _actor(game, "sorcerer_ally").hp == 5

    first_hit = game.execute(Strike("sorcerer_dog", attack_id="longsword"))
    assert first_hit.status is ResultStatus.PAUSED
    _choose(game, "keep")
    assert _actor(game, "sorcerer_dog").hp == 3

    assert game.execute(EndTurn()).status is ResultStatus.COMPLETED
    assert game.inspect().turn_actor_id == "angelic_sorcerer"
    heal = game.execute(Cast("heal", "sorcerer_ally", actions=2))
    assert heal.status is ResultStatus.PAUSED
    assert heal.inspection.choice is not None
    assert heal.inspection.choice.kind == "spell_blood_magic_recipient"
    _choose(game, "angelic_sorcerer")
    assert game.inspect().choice is not None
    assert game.inspect().choice.kind == "spell_willingness"
    _choose(game, "willing")
    assert _actor(game, "sorcerer_ally").hp == 19

    assert game.execute(Cast("guidance", "sorcerer_ally")).status is ResultStatus.COMPLETED
    assert game.execute(EndTurn()).status is ResultStatus.COMPLETED
    final = game.execute(Strike("sorcerer_dog", attack_id="longsword"))
    assert final.status is ResultStatus.PAUSED
    # Guidance is offered before the attack roll; keeping it leaves the
    # ordinary Hero Point reroll choice to resolve as well.
    _choose(game, "keep")
    if game.inspect().choice is not None:
        _choose(game, "keep")
    assert not game.inspect().in_progress


def test_finished_fight_refocus_save_load_next_encounter_and_finish(tmp_path: Path) -> None:
    first_rolls = (20, 1, 10, 20, 3, 20, 3, 15, 1, 4, 15, 1)
    second_rolls = (20, 1, 1, 20, 4, 4)
    game = Encounter.start(ANGELIC_FIRST_CAST_SETUP, rolls=first_rolls + second_rolls)
    _complete_first_scene(game)

    before = game.inspect()
    assert before.world_time_seconds == 6
    assert _actor(game, "angelic_sorcerer").spontaneous_slots[0].remaining == 2
    assert _actor(game, "sorcerer_ally").hp == 19
    assert len(before.light_orbs) == 1
    assert before.light_orbs[0].attached_actor_id == "sorcerer_ally"

    assert game.refocus("angelic_sorcerer").status is ResultStatus.COMPLETED
    assert game.inspect().world_time_seconds == 606
    assert _actor(game, "sorcerer_ally").guidance_immune_until_seconds == 612
    save_path = tmp_path / "before-next-encounter.json"
    game.save(save_path)
    payload = json.loads(save_path.read_text(encoding="utf-8"))
    assert payload["state"]["world_time_seconds"] == 606
    assert payload["state"]["light_orbs"][0][5] == "sorcerer_ally"
    loaded = Encounter.load(save_path)
    assert loaded.inspect() == game.inspect()

    transitioned = loaded.next_encounter(ANGELIC_NEXT_ENCOUNTER_SETUP)
    assert transitioned.status is ResultStatus.PAUSED
    assert transitioned.inspection.world_time_seconds == 606
    assert transitioned.inspection.encounter_start_seconds == 606
    assert transitioned.inspection.choice is not None
    assert transitioned.inspection.choice.kind == "initiative_hero_reroll"
    _choose(loaded, "keep")
    assert loaded.inspect().in_progress
    assert loaded.inspect().turn_actor_id == "angelic_sorcerer"
    assert _actor(loaded, "angelic_sorcerer").spontaneous_slots[0].remaining == 2
    assert _actor(loaded, "angelic_sorcerer").focus_points == 1
    assert _actor(loaded, "sorcerer_ally").hp == 19
    assert _actor(loaded, "sorcerer_ally").guidance_immune_until_seconds == 612
    assert loaded.inspect().light_orbs[0].attached_actor_id == "sorcerer_ally"
    assert "sorcerer_dog_b" in {actor.actor_id for actor in loaded.inspect().actors}

    halo = loaded.execute(Cast("angelic_halo", actions=1))
    assert halo.status is ResultStatus.PAUSED
    assert halo.inspection.choice is not None
    assert halo.inspection.choice.kind == "spell_blood_magic_recipient"
    _choose(loaded, "sorcerer_ally")
    final = loaded.execute(Cast("divine_lance", "sorcerer_dog_b"))
    assert final.status is ResultStatus.COMPLETED
    assert not loaded.inspect().in_progress
    assert _actor(loaded, "sorcerer_dog_b").defeated
    assert loaded.inspect().world_time_seconds == 606

    second_save = tmp_path / "after-next-encounter.json"
    loaded.save(second_save)
    restored = Encounter.load(second_save)
    assert restored.inspect() == loaded.inspect()
    assert any(effect.kind == "angelic_halo" for effect in _actor(restored, "angelic_sorcerer").effects)


def test_next_encounter_rejects_invalid_carry_atomically() -> None:
    game = Encounter.start(ANGELIC_FIRST_CAST_SETUP, rolls=(20, 1, 1))
    before = game.inspect()
    result = game.next_encounter(ANGELIC_NEXT_ENCOUNTER_SETUP)
    assert result.status is ResultStatus.REJECTED
    assert game.inspect() == before
