"""A bounded public Angelic Halo fight with saved choice continuation."""

from __future__ import annotations

from pf2e.content import ANGELIC_FIRST_CAST_SETUP
from pf2e.encounter import Encounter
from pf2e.model import Cast, EndTurn, Position, ResultStatus, Strike, Stride


def _actor(game: Encounter, actor_id: str):
    return next(actor for actor in game.inspect().actors if actor.actor_id == actor_id)


def _keep_attack_choice(game: Encounter) -> None:
    choice = game.inspect().choice
    assert choice is not None and choice.kind == "attack_hero_reroll"
    result = game.choose(choice.choice_id, "keep", choice.owner_actor_id)
    assert result.status is ResultStatus.COMPLETED


def test_angelic_halo_fight_saves_choice_heals_ally_and_wins(tmp_path) -> None:
    # Initiative (20, 1, 1), two critical jaws hits (20, 3, 20, 3),
    # two longsword hits (15, 1, 15, 1), and the slotted Heal's d8 (4).
    rolls = (20, 1, 1, 20, 3, 20, 3, 15, 1, 4, 15, 1)
    game = Encounter.start(ANGELIC_FIRST_CAST_SETUP, rolls=rolls)

    initial = game.inspect()
    assert all(actor.hp == actor.max_hp for actor in initial.actors)
    initiative = initial.choice
    assert initiative is not None and initiative.kind == "initiative_hero_reroll"
    result = game.choose(initiative.choice_id, "keep", initiative.owner_actor_id)
    assert result.status is ResultStatus.COMPLETED
    assert game.inspect().turn_actor_id == "angelic_sorcerer"

    # Cast the one-action focus spell, then save while its genuine Blood Magic
    # recipient choice is pending.  Loading must preserve the pending choice
    # and the already spent focus point.
    offered = game.execute(Cast("angelic_halo", actions=1))
    assert offered.status is ResultStatus.PAUSED
    pending = offered.inspection.choice
    assert pending is not None and pending.kind == "spell_blood_magic_recipient"
    assert {option.option_id for option in pending.options} == {
        "angelic_sorcerer",
        "sorcerer_ally",
    }
    assert _actor(game, "angelic_sorcerer").focus_points == 0
    assert _actor(game, "angelic_sorcerer").spontaneous_slots[0].remaining == 3

    save_path = tmp_path / "angelic-halo-fight.json"
    game.save(save_path)
    resumed = Encounter.load(save_path)
    assert resumed.inspect() == offered.inspection
    pending = resumed.inspect().choice
    assert pending is not None
    result = resumed.choose(pending.choice_id, "sorcerer_ally", pending.owner_actor_id)
    assert result.status is ResultStatus.COMPLETED

    sorcerer = _actor(resumed, "angelic_sorcerer")
    ally = _actor(resumed, "sorcerer_ally")
    assert sorcerer.focus_points == 0
    assert sorcerer.spontaneous_slots[0].remaining == 3
    assert any(
        effect.kind == "angelic_halo" and effect.value == 2
        for effect in sorcerer.effects
    )
    assert any(
        effect.kind == "blood_magic" and effect.value == 1
        for effect in ally.effects
    )

    # Let the ordinary enemy close to the ally and deal real damage.  The
    # second Strike ends the dog's turn and starts the ally's turn.
    assert resumed.execute(EndTurn()).status is ResultStatus.COMPLETED
    assert resumed.inspect().turn_actor_id == "sorcerer_dog"
    assert resumed.execute(
        Stride((Position(4, 2), Position(3, 2)))
    ).status is ResultStatus.COMPLETED

    first_hit = resumed.execute(Strike("sorcerer_ally", attack_id="jaws"))
    assert first_hit.status is ResultStatus.COMPLETED
    first_damage = next(event.damage for event in first_hit.events if event.damage is not None)
    assert first_damage.total == 8
    assert "critical doubles to 8" in next(
        event.text for event in first_hit.events if event.kind == "damage"
    )

    second_hit = resumed.execute(Strike("sorcerer_ally", attack_id="jaws"))
    assert second_hit.status is ResultStatus.COMPLETED
    second_damage = next(event.damage for event in second_hit.events if event.damage is not None)
    assert second_damage.total == 8
    assert _actor(resumed, "sorcerer_ally").hp == 5
    assert resumed.inspect().turn_actor_id == "sorcerer_ally"

    # The Fighter's first attack leaves a living dog for the Sorcerer's
    # slotted Heal and the final attack, keeping the fight continuous.
    ally_strike = resumed.execute(Strike("sorcerer_dog", attack_id="longsword"))
    assert ally_strike.status is ResultStatus.PAUSED
    _keep_attack_choice(resumed)
    assert _actor(resumed, "sorcerer_dog").hp == 3

    assert resumed.execute(EndTurn()).status is ResultStatus.COMPLETED
    assert resumed.inspect().turn_actor_id == "angelic_sorcerer"

    heal_offer = resumed.execute(Cast("heal", "sorcerer_ally", actions=2))
    assert heal_offer.status is ResultStatus.PAUSED
    blood = heal_offer.inspection.choice
    assert blood is not None and blood.kind == "spell_blood_magic_recipient"
    assert {option.option_id for option in blood.options} == {
        "angelic_sorcerer",
        "sorcerer_ally",
    }
    blood_result = resumed.choose(blood.choice_id, "angelic_sorcerer", blood.owner_actor_id)
    assert blood_result.status is ResultStatus.PAUSED
    willingness = blood_result.inspection.choice
    assert willingness is not None and willingness.kind == "spell_willingness"
    healed = resumed.choose(
        willingness.choice_id, "willing", willingness.owner_actor_id
    )
    assert healed.status is ResultStatus.COMPLETED
    healing = next(event for event in healed.events if event.kind == "healing")
    assert "heals 14 HP" in healing.text
    assert "+ Angelic Halo 2 status" in healing.text
    assert "+ Sorcerous Potency" not in healing.text
    assert "+ 3 status" not in healing.text

    sorcerer = _actor(resumed, "angelic_sorcerer")
    ally = _actor(resumed, "sorcerer_ally")
    assert ally.hp == 19
    assert sorcerer.focus_points == 0
    assert sorcerer.spontaneous_slots[0].remaining == 2

    # Pass the enemy's unused turn, then let the healed ally deliver the
    # bounded victory Strike.
    assert resumed.execute(EndTurn()).status is ResultStatus.COMPLETED
    assert resumed.inspect().turn_actor_id == "sorcerer_dog"
    assert resumed.execute(EndTurn()).status is ResultStatus.COMPLETED
    assert resumed.inspect().turn_actor_id == "sorcerer_ally"
    final_strike = resumed.execute(Strike("sorcerer_dog", attack_id="longsword"))
    assert final_strike.status is ResultStatus.PAUSED
    _keep_attack_choice(resumed)

    final = resumed.inspect()
    assert not final.in_progress
    assert final.winner_team == "blue"
    assert _actor(resumed, "sorcerer_dog").defeated
    assert _actor(resumed, "angelic_sorcerer").hp == 16
    assert _actor(resumed, "sorcerer_ally").hp == 19
