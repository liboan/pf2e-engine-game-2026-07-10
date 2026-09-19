from __future__ import annotations

import json

from pf2e.barbarian import Rage
from pf2e.content import get_definition, get_setup
from pf2e.damage import DamageTerm, roll_damage_terms
from pf2e.encounter import Encounter
from pf2e.model import (
    Cast,
    EndTurn,
    FamilyProcedureContext,
    ResultStatus,
    Strike,
)


def _choose(game: Encounter, option_id: str, owner: str | None = None):
    choice = game.inspect().choice
    assert choice is not None
    return game.choose(choice.choice_id, option_id, owner)


def _start_diabolic_turn(game: Encounter) -> None:
    while game.inspect().turn_actor_id is None:
        choice = game.inspect().choice
        assert choice is not None
        if choice.kind == "initiative_hero_reroll":
            _choose(game, "keep", choice.owner_actor_id)
        elif {option.option_id for option in choice.options} == {"accept", "decline"}:
            _choose(game, "decline", choice.owner_actor_id)
        else:
            raise AssertionError(f"unexpected startup choice: {choice}")
    assert game.inspect().turn_actor_id == "dragon_barbarian"


def test_diabolic_strike_uses_saved_defender_resistance_choice_before_health(tmp_path) -> None:
    game = Encounter.start(
        get_setup("typed_defenses_diabolic_dragon_test"),
        rolls=(20, 1, 20, 8),
    )
    _start_diabolic_turn(game)
    assert all(actor.hp == actor.max_hp for actor in game.inspect().actors)

    assert game.execute(Rage()).status is ResultStatus.PAUSED
    assert _choose(game, "dragon_damage", "dragon_barbarian").status is ResultStatus.COMPLETED
    strike = game.execute(Strike("waystone_sentinel", attack_id="longsword"))
    assert strike.status is ResultStatus.PAUSED
    assert strike.inspection.choice is not None
    assert strike.inspection.choice.kind == "attack_hero_reroll"

    keep = _choose(game, "keep", "dragon_barbarian")
    assert keep.status is ResultStatus.PAUSED
    choice = keep.inspection.choice
    assert choice is not None and choice.kind == "damage_defense"
    assert choice.owner_actor_id == "waystone_sentinel"
    assert {option.option_id for option in choice.options} == {"resist:slashing", "resist:fire"}
    expected_options = choice.options
    assert _actor_hp(game, "waystone_sentinel") == 30

    before = tmp_path / "before.json"
    after = tmp_path / "after.json"
    game.save(before)
    rejected = _choose(game, "resist:fire", "dragon_barbarian")
    assert rejected.status is ResultStatus.REJECTED
    game.save(after)
    assert json.loads(before.read_text()) == json.loads(after.read_text())

    saved = tmp_path / "damage-defense.json"
    game.save(saved)
    game = Encounter.load(saved)
    choice = game.inspect().choice
    assert choice is not None and choice.kind == "damage_defense"
    assert choice.options == expected_options

    resolved = _choose(game, "resist:fire", "waystone_sentinel")
    assert resolved.status is ResultStatus.COMPLETED
    assert resolved.inspection.in_progress is False
    assert resolved.inspection.winner_team == "blue"
    event = next(event for event in resolved.events if event.kind == "damage")
    assert event.damage is not None and event.original_damage is not None
    assert event.original_damage.total == 32
    assert event.damage.total == 33  # weakness and resistance both apply once
    assert [part.amount for part in event.original_damage.components] == [24, 8]
    assert [part.amount for part in event.damage.components] == [27, 6]
    assert "damage after defenses" in event.text
    assert _actor_hp(game, "waystone_sentinel") == 0


def test_divine_lance_applies_spell_resistance_and_finishes_healthy_encounter() -> None:
    game = Encounter.start(
        get_setup("typed_defenses_warpriest_spell_test"),
        rolls=(20, 1, 20, 4, 4),
    )
    _start_turn(game, "cleric_c")
    assert all(actor.hp == actor.max_hp for actor in game.inspect().actors)

    attack = game.execute(Cast("divine_lance", "waystone_sentinel"))
    assert attack.status is ResultStatus.PAUSED
    choice = attack.inspection.choice
    assert choice is not None and choice.kind == "spell_attack_hero_reroll"

    finished = _choose(game, "keep", "cleric_c")
    assert finished.status is ResultStatus.COMPLETED
    assert finished.inspection.in_progress is False
    assert finished.inspection.winner_team == "blue"
    event = next(event for event in finished.events if event.kind == "spell_damage")
    assert event.original_damage is not None and event.damage is not None
    assert event.original_damage.total == 16
    assert event.damage.total == 14
    assert event.remaining_hp_damage == 14
    assert "14 total (was 16 before defenses)" in event.text


def test_void_warp_basic_save_arithmetic_precedes_immunity_and_keeps_aftermath() -> None:
    game = Encounter.start(
        get_setup("typed_defenses_warpriest_spell_test"),
        rolls=(20, 1, 1, 4, 4),
    )
    _start_turn(game, "cleric_c")

    result = game.execute(Cast("void_warp", "waystone_sentinel"))
    assert result.status is ResultStatus.COMPLETED
    damage = next(event for event in result.events if event.kind == "spell_damage")
    assert damage.original_damage is not None and damage.damage is not None
    assert damage.original_damage.adjustment == "basic_save:critical_failure"
    assert damage.original_damage.total == 16
    assert damage.damage.total == 0
    assert _actor_hp(game, "waystone_sentinel") == 14
    assert any(
        event.kind == "effect_applied" and "enfeebled 1" in event.text
        for event in result.events
    )


def test_family_damage_entry_uses_saved_defender_choice_in_real_context(tmp_path) -> None:
    """Direct family-procedure evidence; no admitted public family emits this mix yet."""
    game = Encounter.start(
        get_setup("typed_defenses_warpriest_spell_test"), rolls=(20, 1)
    )
    _start_turn(game, "cleric_c")
    actor = game._state.creatures["cleric_c"]
    context = FamilyProcedureContext(
        game,
        game._state,
        game._dice,
        actor,
        get_definition(actor.definition_id),
        "typed-defense-diagnostic",
    )
    damage = roll_damage_terms(
        (
            DamageTerm("diagnostic impact", "slashing", (), modifier=5),
            DamageTerm("diagnostic flare", "fire", (), modifier=7),
        ),
        game._dice.draw,
    )

    assert context.apply_family_damage(
        "waystone_sentinel",
        damage,
        source="diagnostic family effect",
        damage_type="slashing",
    ) == ()
    choice = game.inspect().choice
    assert choice is not None and choice.kind == "damage_defense"
    assert choice.owner_actor_id == "waystone_sentinel"

    path = tmp_path / "family-defense.json"
    game.save(path)
    game = Encounter.load(path)
    resolved = _choose(game, "resist:fire", "waystone_sentinel")
    event = next(event for event in resolved.events if event.damage is not None)
    assert event.original_damage is not None and event.original_damage.total == 12
    assert event.damage is not None and event.damage.total == 13
    assert [part.amount for part in event.damage.components] == [8, 5]
    assert _actor_hp(game, "waystone_sentinel") == 1


def test_defense_choice_then_saved_heroic_recovery_applies_health_once(tmp_path) -> None:
    game = Encounter.start(
        get_setup("typed_defenses_heroic_recovery_test"),
        rolls=(20, 1, 20, 8),
    )
    _start_turn(game, "dragon_barbarian")
    assert game.execute(Rage()).status is ResultStatus.PAUSED
    assert _choose(game, "dragon_damage", "dragon_barbarian").status is ResultStatus.COMPLETED
    assert game.execute(
        Strike("warded_warpriest", attack_id="longsword")
    ).status is ResultStatus.PAUSED
    assert _choose(game, "keep", "dragon_barbarian").status is ResultStatus.PAUSED

    defense = _choose(game, "resist:fire", "warded_warpriest")
    assert defense.status is ResultStatus.PAUSED
    choice = defense.inspection.choice
    assert choice is not None and choice.kind == "heroic_recovery_damage"
    assert _actor_hp(game, "warded_warpriest") == 17

    path = tmp_path / "post-defense-heroic.json"
    game.save(path)
    game = Encounter.load(path)
    finished = _choose(game, "heroic_recovery", "warded_warpriest")
    damage_events = [event for event in finished.events if event.damage is not None]
    assert len(damage_events) == 1
    assert damage_events[0].original_damage is not None
    assert damage_events[0].original_damage.total == 32
    assert damage_events[0].damage is not None
    assert damage_events[0].damage.total == 33
    target = _actor(game, "warded_warpriest")
    assert (target.hp, target.temporary_hp, target.hero_points, target.dying) == (0, 0, 0, 0)
    assert target.unconscious and not target.dead
    assert finished.inspection.in_progress is False
    assert finished.inspection.winner_team == "blue"


def test_bear_temporary_hp_absorbs_shared_runtime_damage_once() -> None:
    game = Encounter.start(
        get_setup("typed_defenses_bear_temp_hp_test"),
        rolls=(20, 1, 20, 6),
    )
    _start_turn(game, "barbarian_test")
    assert game.execute(Rage()).status is ResultStatus.COMPLETED
    assert _actor(game, "barbarian_test").temporary_hp == 4
    assert game.execute(EndTurn()).status is ResultStatus.COMPLETED

    result = game.execute(
        Strike("barbarian_test", attack_id="cinderbrand_strike")
    )
    event = next(event for event in result.events if event.damage is not None)
    assert event.damage is not None and event.damage.total == 16
    assert event.temporary_hp_absorbed == 4
    assert event.remaining_hp_damage == 12
    bear = _actor(game, "barbarian_test")
    assert (bear.hp, bear.temporary_hp) == (11, 0)


def _actor_hp(game: Encounter, actor_id: str) -> int:
    return next(actor.hp for actor in game.inspect().actors if actor.actor_id == actor_id)


def _actor(game: Encounter, actor_id: str):
    return next(actor for actor in game.inspect().actors if actor.actor_id == actor_id)


def _start_turn(game: Encounter, actor_id: str) -> None:
    while game.inspect().turn_actor_id is None:
        choice = game.inspect().choice
        assert choice is not None
        options = {option.option_id for option in choice.options}
        if "keep" in options:
            option_id = "keep"
        elif options == {"accept", "decline"}:
            option_id = "decline"
        else:
            option_id = actor_id if actor_id in options else choice.options[0].option_id
        _choose(game, option_id, choice.owner_actor_id)
    assert game.inspect().turn_actor_id == actor_id
