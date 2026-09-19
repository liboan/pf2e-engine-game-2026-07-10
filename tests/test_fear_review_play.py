"""Source-informed public Fear/Flee timing and reaction play.

Rules checked 2026-09-15:

* Fear: https://2e.aonprd.com/Spells.aspx?ID=1524
* Fleeing: https://2e.aonprd.com/Conditions.aspx?ID=74
* Frightened: https://2e.aonprd.com/Conditions.aspx?ID=76
* Reactive Strike: https://2e.aonprd.com/Actions.aspx?ID=2256
"""

from __future__ import annotations

from pf2e.content import ANGELIC_FEAR_REACTION_SETUP
from pf2e.encounter import Encounter
from pf2e.model import Cast, EndTurn, Flee, ResultStatus


def _keep_start_choices(game: Encounter) -> None:
    while (choice := game.inspect().choice) is not None:
        option = (
            "keep"
            if any(item.option_id == "keep" for item in choice.options)
            else choice.options[0].option_id
        )
        result = game.choose(choice.choice_id, option, choice.owner_actor_id)
        assert result.status is ResultStatus.COMPLETED


def test_later_initiative_fear_saves_flee_reaction_then_completes_fight(tmp_path) -> None:
    # Initiative: dog 26, Sorcerer 18, Fighter 16.  Fear's natural 1 is a
    # critical failure.  The Fighter then hits (3 + 9 vs frightened AC 12)
    # for 5, and Divine Lance finishes the 3-HP dog after Flee ends.
    game = Encounter.start(
        ANGELIC_FEAR_REACTION_SETUP,
        rolls=(15, 10, 20, 1, 3, 1, 6, 1, 2),
    )
    assert all(actor.hp == actor.max_hp for actor in game.inspect().actors)
    _keep_start_choices(game)
    assert game.inspect().turn_actor_id == "sorcerer_dog"

    # The target has already acted when the later-in-initiative caster applies
    # Fear.  Fleeing must survive the immediate round wrap until the caster's
    # next start, while frightened belongs to the victim's end-turn boundary.
    assert game.execute(EndTurn()).status is ResultStatus.COMPLETED
    assert game.inspect().turn_actor_id == "angelic_sorcerer"
    feared = game.execute(Cast("fear", "sorcerer_dog"))
    assert feared.status is ResultStatus.COMPLETED
    assert game.execute(EndTurn()).status is ResultStatus.COMPLETED
    assert game.inspect().turn_actor_id == "sorcerer_ally"
    assert game.execute(EndTurn()).status is ResultStatus.COMPLETED
    assert game._state.world_time_seconds == 6
    assert game.inspect().turn_actor_id == "sorcerer_dog"
    assert any(
        effect.kind == "fleeing" and effect.target_actor_id == "sorcerer_dog"
        for effect in game._state.active_effects
    )
    assert next(
        effect.value
        for effect in game._state.condition_effects
        if effect.kind == "frightened" and effect.target_actor_id == "sorcerer_dog"
    ) == 3

    offered = game.execute(Flee())
    assert offered.status is ResultStatus.PAUSED
    reaction = offered.inspection.choice
    assert reaction is not None and reaction.kind == "reaction"
    assert reaction.owner_actor_id == "sorcerer_ally"
    pending = game._state.pending_choice
    assert pending is not None and pending.continuation is not None
    assert pending.continuation.movement_kind == "flee"
    assert pending.continuation.next_step == 0
    saved_path = pending.continuation.path

    save_path = tmp_path / "public-flee-reaction.json"
    game.save(save_path)
    resumed = Encounter.load(save_path)
    restored = resumed.inspect().choice
    assert restored is not None and restored.kind == "reaction"
    restored_pending = resumed._state.pending_choice
    assert restored_pending is not None and restored_pending.continuation is not None
    assert restored_pending.continuation.path == saved_path
    assert restored_pending.continuation.next_step == 0

    struck = resumed.choose(restored.choice_id, "accept", restored.owner_actor_id)
    assert struck.status is ResultStatus.PAUSED
    hero = struck.inspection.choice
    assert hero is not None and hero.kind == "attack_hero_reroll"
    assert any(event.kind == "reaction" for event in struck.events)
    moved = resumed.choose(hero.choice_id, "keep", hero.owner_actor_id)
    assert moved.status is ResultStatus.COMPLETED
    assert resumed._state.creatures["sorcerer_dog"].hp == 3
    assert resumed._state.creatures["sorcerer_dog"].position == saved_path[-1]
    assert any(event.kind == "flee" for event in moved.events)

    # The remaining escape attempts consume the turn at the closed boundary.
    # Frightened drops at the dog's end; Fleeing remains until the Sorcerer's
    # immediately following start, where it expires independently.
    assert resumed.execute(Flee()).status is ResultStatus.COMPLETED
    final_flee = resumed.execute(Flee())
    assert final_flee.status is ResultStatus.COMPLETED
    assert resumed.inspect().turn_actor_id == "angelic_sorcerer"
    assert not any(effect.kind == "fleeing" for effect in resumed._state.active_effects)
    assert next(
        effect.value
        for effect in resumed._state.condition_effects
        if effect.kind == "frightened" and effect.target_actor_id == "sorcerer_dog"
    ) == 2

    finished = resumed.execute(Cast("divine_lance", "sorcerer_dog"))
    assert finished.status is ResultStatus.COMPLETED
    assert not resumed.inspect().in_progress
    assert resumed.inspect().winner_team == "blue"
    assert resumed._state.creatures["sorcerer_dog"].defeated


def test_later_initiative_halo_uses_caster_start_after_world_deadline(tmp_path) -> None:
    game = Encounter.start(
        ANGELIC_FEAR_REACTION_SETUP,
        rolls=(15, 10, 20),
    )
    _keep_start_choices(game)
    assert game.inspect().turn_actor_id == "sorcerer_dog"
    assert game.execute(EndTurn()).status is ResultStatus.COMPLETED
    assert game.inspect().turn_actor_id == "angelic_sorcerer"

    offered = game.execute(Cast("angelic_halo", actions=1))
    assert offered.status is ResultStatus.PAUSED
    blood = offered.inspection.choice
    assert blood is not None and blood.kind == "spell_blood_magic_recipient"
    cast = game.choose(blood.choice_id, "angelic_sorcerer", blood.owner_actor_id)
    assert cast.status is ResultStatus.COMPLETED
    halo = next(
        effect for effect in game._state.active_effects
        if effect.kind == "angelic_halo"
    )
    assert halo.expires_at_source_start == 11
    assert halo.expires_at_world_time == 60

    # The tenth round wrap reaches the one-minute clock before this
    # later-in-initiative caster starts turn 11.  The aura remains active
    # through the intervening dog's turn, including after save/load.
    assert game.execute(EndTurn()).status is ResultStatus.COMPLETED
    while game._state.world_time_seconds < 60:
        assert game.execute(EndTurn()).status is ResultStatus.COMPLETED
    assert game._state.world_time_seconds == 60
    assert game.inspect().turn_actor_id == "sorcerer_dog"
    assert any(effect.kind == "angelic_halo" for effect in game._state.active_effects)

    save_path = tmp_path / "later-initiative-halo-deadline.json"
    game.save(save_path)
    resumed = Encounter.load(save_path)
    assert any(effect.kind == "angelic_halo" for effect in resumed._state.active_effects)

    assert resumed.execute(EndTurn()).status is ResultStatus.COMPLETED
    assert resumed.inspect().turn_actor_id == "angelic_sorcerer"
    assert not any(
        effect.kind == "angelic_halo" for effect in resumed._state.active_effects
    )
