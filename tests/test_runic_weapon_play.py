"""Bounded public rank-1 Runic Weapon encounter checks.

The tests use the staged Angelic Sorcerer and physical weapon fixtures. Every
enhancement and attack below goes through the public ``Cast``, ``Choose``,
``EndTurn``, ``Release``, ``Interact``, ``Strike`` or ``ViciousSwing`` command
paths.
"""

from __future__ import annotations

from dataclasses import replace
import json
from pathlib import Path

import pf2e.encounter as encounter_module
import pf2e.persistence as persistence_module
from pf2e import (
    Cast,
    Encounter,
    EndTurn,
    Interact,
    Position,
    Release,
    ResultStatus,
    Strike,
    Stride,
    ViciousSwing,
)
from pf2e.content import (
    ANGELIC_FIRST_CAST_SETUP,
    RUNE_WEAPON_FIGHTER_M,
    WEAPON_IDENTITY_FIGHTER_M,
    WEAPON_IDENTITY_THIEF,
)
from pf2e.skill_actions import Feint


def _actor(game: Encounter, actor_id: str):
    return next(actor for actor in game.inspect().actors if actor.actor_id == actor_id)


def _keep_choice(game: Encounter):
    choice = game.inspect().choice
    assert choice is not None
    option_id = (
        "keep"
        if any(option.option_id == "keep" for option in choice.options)
        else choice.options[0].option_id
    )
    result = game.choose(choice.choice_id, option_id, choice.owner_actor_id)
    assert result.status is ResultStatus.COMPLETED
    return result


def _settle_initiative(game: Encounter) -> None:
    while game.inspect().choice is not None:
        choice = game.inspect().choice
        assert choice is not None and choice.kind == "initiative_hero_reroll"
        result = game.choose(choice.choice_id, "keep", choice.owner_actor_id)
        assert result.status in {ResultStatus.PAUSED, ResultStatus.COMPLETED}


def _cast_runic_weapon(
    game: Encounter,
    *,
    item_id: str = "sorcerer_ally:longsword",
    save_path: Path | None = None,
) -> Encounter:
    assert game.inspect().turn_actor_id == "angelic_sorcerer"
    offered = game.execute(
        Cast(
            "runic_weapon",
            item_id=item_id,
            slot_id="angelic_rank1",
        )
    )
    assert offered.status is ResultStatus.PAUSED
    pending = offered.inspection.choice
    assert pending is not None and pending.kind == "spell_willingness"
    assert item_id in pending.prompt
    assert _actor(game, "angelic_sorcerer").spontaneous_slots[0].remaining == 2

    if save_path is not None:
        game.save(save_path)
        saved = json.loads(save_path.read_text(encoding="utf-8"))
        continuation = saved["state"]["pending_choice"]["continuation"]
        assert continuation["spell_target_item_id"] == item_id
        assert continuation["spell_target_wielder_id"] == "sorcerer_ally"
        restored = Encounter.load(save_path)
        assert restored.inspect() == offered.inspection
        game = restored

    pending = game.inspect().choice
    assert pending is not None and pending.kind == "spell_willingness"
    accepted = game.choose(pending.choice_id, "willing", pending.owner_actor_id)
    assert accepted.status is ResultStatus.COMPLETED
    assert game.inspect().choice is None
    assert _actor(game, "angelic_sorcerer").spontaneous_slots[0].remaining == 2
    effect = next(
        effect
        for effect in game._state.active_item_effects
        if effect.kind == "runic_weapon"
    )
    assert effect.item_id == item_id
    assert effect.potency == 1 and effect.striking_dice == 2 and effect.magical
    return game


def _to_ally_turn(game: Encounter) -> None:
    assert game.execute(EndTurn()).status is ResultStatus.COMPLETED
    assert game.execute(EndTurn()).status is ResultStatus.COMPLETED
    assert game.inspect().turn_actor_id == "sorcerer_ally"


def _local_angelic_setup(
    monkeypatch,
    *,
    ally_definition_id: str,
    setup_id: str,
    dog_definition_id: str | None = None,
    dog_position: Position = Position(3, 2),
    ally_team: str = "blue",
):
    """Build a legal composite sheet for one cross-family public probe.

    The staged definitions already contain the reviewed actor and equipment
    facts. Encounter admission requires catalogued setup equality, so this
    test-only composite temporarily extends that lookup while leaving all
    action resolution on the normal public path.
    """
    setup = replace(
        ANGELIC_FIRST_CAST_SETUP,
        setup_id=setup_id,
        placements=tuple(
            replace(
                placement,
                definition_id=ally_definition_id,
                label="Runic Ally",
                team=ally_team,
            )
            if placement.actor_id == "sorcerer_ally"
            else replace(
                placement,
                position=dog_position,
                definition_id=dog_definition_id,
                label="Transfer Wielder",
            )
            if placement.actor_id == "sorcerer_dog" and dog_definition_id is not None
            else replace(placement, position=dog_position)
            if placement.actor_id == "sorcerer_dog"
            else placement
            for placement in ANGELIC_FIRST_CAST_SETUP.placements
        ),
    )
    original_get_setup = encounter_module.get_setup
    monkeypatch.setattr(
        encounter_module,
        "get_setup",
        lambda requested_id: (
            setup
            if requested_id == setup.setup_id
            else original_get_setup(requested_id)
        ),
    )
    original_persistence_get_setup = persistence_module.get_setup
    monkeypatch.setattr(
        persistence_module,
        "get_setup",
        lambda requested_id: setup
        if requested_id == setup.setup_id
        else original_persistence_get_setup(requested_id),
    )
    return setup


def test_runic_weapon_cast_saved_willingness_adds_item_attack_and_two_dice(
    monkeypatch, tmp_path: Path,
) -> None:
    # Initiative, then the enhanced longsword's Strike and its two d8s.
    setup = _local_angelic_setup(
        monkeypatch,
        ally_definition_id=WEAPON_IDENTITY_FIGHTER_M.definition_id,
        setup_id="runic_weapon_cast",
    )
    game = Encounter.start(setup, rolls=(20, 1, 1, 15, 4, 7))
    _settle_initiative(game)
    game = _cast_runic_weapon(game, save_path=tmp_path / "pending-runic.json")

    item = game._state.item_instances["sorcerer_ally:longsword"]
    assert item.rune_ids == ()
    _to_ally_turn(game)
    paused = game.execute(
        Strike(
            "sorcerer_dog",
            attack_id="longsword",
            item_id="sorcerer_ally:longsword",
        )
    )
    assert paused.status is ResultStatus.PAUSED
    check = next(event.check for event in paused.events if event.check is not None)
    assert check is not None and check.modifier == 10
    assert any(
        modifier.amount == 1 and modifier.modifier_type == "item"
        for modifier in check.modifier_breakdown
    )
    result = _keep_choice(game)
    damage = next(event.damage for event in result.events if event.damage is not None)
    assert damage is not None
    assert damage.components[0].dice == (8, 8)
    assert damage.components[0].rolls == (4, 7)
    assert damage.total == 30
    assert _actor(game, "sorcerer_dog").dead
    assert result.inspection.winner_team == "blue"


def test_runic_weapon_survives_release_save_retrieve_by_another_wielder(
    monkeypatch, tmp_path: Path,
) -> None:
    # The temporary spell effect belongs to the physical instance, not to the
    # actor currently holding it. Release and retrieve are public actions.
    # The second Fighter supplies another legal wielder for the transferred
    # item. Initiative, then the final Strike and its two d8s.
    setup = _local_angelic_setup(
        monkeypatch,
        ally_definition_id=WEAPON_IDENTITY_FIGHTER_M.definition_id,
        dog_definition_id=WEAPON_IDENTITY_FIGHTER_M.definition_id,
        setup_id="runic_weapon_transfer",
    )
    game = Encounter.start(setup, rolls=(20, 1, 2, 10, 4, 7))
    _settle_initiative(game)
    game = _cast_runic_weapon(game)
    _to_ally_turn(game)

    item_id = "sorcerer_ally:longsword"
    assert game.execute(Release(item_id)).status is ResultStatus.COMPLETED
    assert item_id in dict(game.inspect().ground_items)[_actor(game, "sorcerer_ally").position]
    moved = game.execute(Stride((Position(2, 3), Position(2, 4))))
    if moved.status is ResultStatus.PAUSED:
        reaction = moved.inspection.choice
        assert reaction is not None and reaction.kind == "reaction"
        moved = game.choose(reaction.choice_id, "decline", reaction.owner_actor_id)
    assert moved.status is ResultStatus.COMPLETED
    game.save(tmp_path / "released-runic.json")
    game = Encounter.load(tmp_path / "released-runic.json")

    assert game.execute(EndTurn()).status is ResultStatus.COMPLETED
    assert game.inspect().turn_actor_id == "angelic_sorcerer"
    assert game.execute(EndTurn()).status is ResultStatus.COMPLETED
    assert game.inspect().turn_actor_id == "sorcerer_dog"
    assert game.execute(Stride((Position(2, 2),))).status is ResultStatus.COMPLETED
    picked_up = game.execute(Interact("retrieve", item_id))
    assert picked_up.status is ResultStatus.COMPLETED
    assert item_id in _actor(game, "sorcerer_dog").held_items
    assert "sorcerer_dog:longsword" in _actor(game, "sorcerer_dog").held_items
    effect = next(effect for effect in game._state.active_item_effects if effect.kind == "runic_weapon")
    assert effect.item_id == item_id

    paused = game.execute(Strike("angelic_sorcerer", attack_id="longsword", item_id=item_id))
    assert paused.status is ResultStatus.PAUSED
    check = next(event.check for event in paused.events if event.check is not None)
    assert check is not None and check.modifier == 10
    result = _keep_choice(game)
    damage = next(event.damage for event in result.events if event.damage is not None)
    assert damage is not None and damage.components[0].dice == (8, 8)
    assert damage.components[0].rolls == (4, 7)
    assert _actor(game, "angelic_sorcerer").hp == 1


def test_runic_weapon_vicious_swing_has_two_weapon_dice_and_one_action_die(
    monkeypatch,
) -> None:
    # Initiative, then Vicious Swing's check and its 2d8 weapon + 1d8 action.
    setup = _local_angelic_setup(
        monkeypatch,
        ally_definition_id=WEAPON_IDENTITY_FIGHTER_M.definition_id,
        setup_id="runic_weapon_vicious_swing",
    )
    game = Encounter.start(setup, rolls=(20, 1, 1, 10, 1, 2, 3))
    _settle_initiative(game)
    game = _cast_runic_weapon(game)
    _to_ally_turn(game)

    paused = game.execute(
        ViciousSwing(
            "sorcerer_dog",
            attack_id="longsword",
            item_id="sorcerer_ally:longsword",
        )
    )
    assert paused.status is ResultStatus.PAUSED
    check = next(event.check for event in paused.events if event.check is not None)
    assert check is not None and check.modifier == 10
    assert check.attack_count == 1 and check.map_penalty == 0
    result = _keep_choice(game)
    damage = next(event.damage for event in result.events if event.damage is not None)
    assert damage is not None
    assert damage.components[0].source == "longsword"
    assert damage.components[0].dice == (8, 8, 8)
    assert damage.components[0].rolls == (1, 2, 3)
    assert damage.components[0].modifier == 4
    assert damage.total == 10
    assert all("Sorcerous Potency" not in event.text for event in result.events)
    assert _actor(game, "sorcerer_dog").dead


def test_runic_weapon_uses_maximum_permanent_potency_and_striking_without_mutation(
    monkeypatch,
) -> None:
    setup = _local_angelic_setup(
        monkeypatch,
        ally_definition_id=RUNE_WEAPON_FIGHTER_M.definition_id,
        setup_id="runic_weapon_permanent_runes",
    )
    game = Encounter.start(setup, rolls=(20, 1, 1, 10, 1, 2))
    _settle_initiative(game)
    game = _cast_runic_weapon(game)
    _to_ally_turn(game)

    item_id = "sorcerer_ally:longsword"
    item_before = game._state.item_instances[item_id]
    assert item_before.rune_ids == ("weapon_potency_1", "striking")
    paused = game.execute(Strike("sorcerer_dog", attack_id="longsword", item_id=item_id))
    assert paused.status is ResultStatus.PAUSED
    check = next(event.check for event in paused.events if event.check is not None)
    assert check is not None and check.modifier == 10
    result = _keep_choice(game)
    damage = next(event.damage for event in result.events if event.damage is not None)
    assert damage is not None
    assert damage.components[0].dice == (8, 8)
    assert damage.components[0].rolls == (1, 2)
    assert damage.total == 7
    assert game._state.item_instances[item_id] == item_before


def test_runic_weapon_expires_at_the_tenth_source_start_and_restores_strike(
    monkeypatch,
) -> None:
    # The first d20 is an active-effect failure; after expiry the Strike hits
    # with one ordinary d8. No live state is altered to advance the clock.
    setup = _local_angelic_setup(
        monkeypatch,
        ally_definition_id=WEAPON_IDENTITY_FIGHTER_M.definition_id,
        setup_id="runic_weapon_expiry",
    )
    game = Encounter.start(setup, rolls=(20, 1, 1, 1, 15, 1))
    _settle_initiative(game)
    game = _cast_runic_weapon(game)
    _to_ally_turn(game)

    active = game.execute(
        Strike("sorcerer_dog", attack_id="longsword", item_id="sorcerer_ally:longsword")
    )
    assert active.status is ResultStatus.PAUSED
    active_check = next(event.check for event in active.events if event.check is not None)
    assert active_check is not None and active_check.modifier == 10
    kept_active = _keep_choice(game)
    assert not any(event.damage is not None for event in kept_active.events)

    while game._state.actor_start_counts["angelic_sorcerer"] < 11:
        ended = game.execute(EndTurn())
        assert ended.status is ResultStatus.COMPLETED
        assert ended.inspection.choice is None
    assert game.inspect().turn_actor_id == "angelic_sorcerer"
    assert game._state.actor_start_counts["angelic_sorcerer"] == 11
    assert game._state.world_time_seconds == 60
    assert not game._state.active_item_effects

    assert game.execute(EndTurn()).status is ResultStatus.COMPLETED
    assert game.execute(EndTurn()).status is ResultStatus.COMPLETED
    expired = game.execute(
        Strike("sorcerer_dog", attack_id="longsword", item_id="sorcerer_ally:longsword")
    )
    assert expired.status is ResultStatus.PAUSED
    expired_check = next(event.check for event in expired.events if event.check is not None)
    assert expired_check is not None and expired_check.modifier == 9
    assert not any(
        modifier.modifier_type == "item" for modifier in expired_check.modifier_breakdown
    )
    result = _keep_choice(game)
    damage = next(event.damage for event in result.events if event.damage is not None)
    assert damage is not None and damage.components[0].dice == (8,)
    assert damage.components[0].rolls == (1,)
    assert damage.total == 5
    assert _actor(game, "sorcerer_dog").hp == 3


def test_runic_weapon_sneak_attack_keeps_separate_precision_die(
    monkeypatch,
) -> None:
    setup = _local_angelic_setup(
        monkeypatch,
        ally_definition_id=WEAPON_IDENTITY_THIEF.definition_id,
        setup_id="runic_weapon_sneak_attack",
    )
    game = Encounter.start(setup, rolls=(20, 1, 1, 15, 10, 1, 1, 1))
    _settle_initiative(game)
    game = _cast_runic_weapon(game, item_id="sorcerer_ally:shortsword")
    _to_ally_turn(game)

    feint = game.execute(Feint("sorcerer_dog"))
    assert feint.status is ResultStatus.PAUSED
    feint_result = _keep_choice(game)
    assert any(event.kind == "feint_exposure" for event in feint_result.events)

    paused = game.execute(
        Strike(
            "sorcerer_dog",
            attack_id="shortsword",
            item_id="sorcerer_ally:shortsword",
        )
    )
    assert paused.status is ResultStatus.PAUSED
    check = next(event.check for event in paused.events if event.check is not None)
    assert check is not None and check.modifier == 8
    result = _keep_choice(game)
    damage = next(event.damage for event in result.events if event.damage is not None)
    assert damage is not None
    assert [component.source for component in damage.components] == [
        "shortsword",
        "rogue_sneak_attack",
    ]
    assert damage.components[0].dice == (6, 6)
    assert damage.components[0].rolls == (1, 1)
    assert damage.components[1].dice == (6,)
    assert damage.components[1].rolls == (1,)
    assert damage.components[1].tags == frozenset({"precision"})
    assert damage.total == 7
    assert all("Sorcerous Potency" not in event.text for event in result.events)
    assert _actor(game, "sorcerer_dog").hp == 1


def test_critical_manipulate_reaction_keeps_runic_cost_without_effect(
    monkeypatch, tmp_path: Path,
) -> None:
    setup = _local_angelic_setup(
        monkeypatch,
        ally_definition_id=WEAPON_IDENTITY_FIGHTER_M.definition_id,
        setup_id="runic_weapon_critical_disruption",
        ally_team="red",
    )
    # Initiative, then the hostile Fighter's critical Reactive Strike and its
    # one d8. The reaction is allowed after the real willingness choice.
    game = Encounter.start(setup, rolls=(20, 1, 2, 20, 1))
    _settle_initiative(game)
    offered = game.execute(
        Cast(
            "runic_weapon",
            item_id="sorcerer_ally:longsword",
            slot_id="angelic_rank1",
        )
    )
    assert offered.status is ResultStatus.PAUSED
    assert _actor(game, "angelic_sorcerer").spontaneous_slots[0].remaining == 2
    willingness = offered.inspection.choice
    assert willingness is not None and willingness.kind == "spell_willingness"
    accepted = game.choose(willingness.choice_id, "willing", willingness.owner_actor_id)
    assert accepted.status is ResultStatus.PAUSED
    reaction = accepted.inspection.choice
    assert reaction is not None and reaction.kind == "reaction"
    selected = next(option for option in reaction.options if option.option_id == "accept")
    attack = game.choose(reaction.choice_id, selected.option_id, reaction.owner_actor_id)
    assert attack.status is ResultStatus.PAUSED
    pending = attack.inspection.choice
    assert pending is not None and pending.kind == "attack_hero_reroll"
    game.save(tmp_path / "critical-runic-reaction.json")
    restored = Encounter.load(tmp_path / "critical-runic-reaction.json")
    assert restored.inspect() == attack.inspection

    result = _keep_choice(restored)
    assert any(event.kind == "disrupted" for event in result.events)
    assert not restored._state.active_item_effects
    assert _actor(restored, "angelic_sorcerer").spontaneous_slots[0].remaining == 2
    assert _actor(restored, "sorcerer_ally").reaction_available is False
