from __future__ import annotations

from pathlib import Path

import pytest

from pf2e import Encounter, Rage, ResultStatus, Strike
from pf2e.barbarian import DRAGON_CHOICES, DRAGONS_BY_ID
from pf2e.barbarian_content import (
    DRAGON_BARBARIAN_CHARACTERS,
    DRAGON_BARBARIAN_INITIAL_STATES,
    DRAGON_BARBARIAN_SETUPS,
)
from pf2e.content import get_setup
from pf2e.skill_actions import Demoralize


DRAGON_IDS = tuple(dragon.dragon_id for dragon in DRAGON_CHOICES)


def _actor(game: Encounter, actor_id: str):
    return next(actor for actor in game.inspect().actors if actor.actor_id == actor_id)


def _choose(game: Encounter, option_id: str, owner: str | None = None):
    choice = game.inspect().choice
    assert choice is not None
    return game.choose(choice.choice_id, option_id, owner)


def _start_dragon_turn(game: Encounter, *, quick_tempered: str = "decline") -> None:
    """Resolve only the ordinary initiative/Quick-Tempered startup decisions."""
    while game.inspect().turn_actor_id is None:
        choice = game.inspect().choice
        assert choice is not None, "initiative is waiting without a public choice"
        options = {option.option_id for option in choice.options}
        if choice.kind == "initiative_hero_reroll":
            _choose(game, "keep", choice.owner_actor_id)
        elif options == {"accept", "decline"}:
            _choose(game, quick_tempered, choice.owner_actor_id)
        elif choice.kind == "initiative_tie":
            option_id = "dragon_barbarian" if "dragon_barbarian" in options else choice.options[0].option_id
            _choose(game, option_id)
        else:
            raise AssertionError(f"unexpected startup choice: {choice}")
    assert game.inspect().turn_actor_id == "dragon_barbarian"


def _save_reload(game: Encounter, tmp_path: Path, filename: str) -> Encounter:
    path = tmp_path / filename
    game.save(path)
    return Encounter.load(path)


@pytest.mark.parametrize("dragon_id", DRAGON_IDS)
def test_each_canonical_dragon_build_uses_its_typed_rage_and_finishes_a_public_encounter(
    dragon_id: str,
    tmp_path: Path,
) -> None:
    character = DRAGON_BARBARIAN_CHARACTERS[dragon_id]
    dragon = DRAGONS_BY_ID[dragon_id]
    setup_id = f"barbarian_dragon_{dragon_id}_rage_test"
    assert DRAGON_BARBARIAN_SETUPS[setup_id] == get_setup(setup_id)
    assert DRAGON_BARBARIAN_INITIAL_STATES[character.definition.definition_id] == character.barbarian_state

    game = Encounter.start(get_setup(setup_id), rolls=(10, 1, 20, 8, 8))
    _start_dragon_turn(game)
    actor = _actor(game, "dragon_barbarian")
    assert actor.hp == actor.max_hp == 23
    assert actor.barbarian_state == character.barbarian_state

    # The ordinary action presents both legal modes. Saving the uncommitted
    # choice proves the selected dragon and mode survive a real continuation.
    result = game.execute(Rage())
    assert result.status is ResultStatus.PAUSED
    choice = result.inspection.choice
    assert choice is not None and choice.kind == "family_action"
    assert {option.option_id for option in choice.options} == {"base", "dragon_damage"}
    game = _save_reload(game, tmp_path, f"{dragon_id}-ordinary-mode.json")
    result = _choose(game, "dragon_damage", "dragon_barbarian")
    assert result.status is ResultStatus.COMPLETED

    raging = _actor(game, "dragon_barbarian")
    active = raging.barbarian_state.rage
    assert active is not None
    assert (active.mode_id, active.damage_type) == ("dragon_damage", dragon.damage_type)
    assert active.action_traits == frozenset({dragon.tradition, dragon.damage_type})
    rage_started = next(event for event in result.events if event.kind == "rage_started")
    assert rage_started.details == tuple(sorted(
        {"barbarian", "concentrate", "emotion", "mental", dragon.tradition, dragon.damage_type}
    ))
    assert raging.actions_remaining == 2
    assert raging.temporary_hp == 4

    strike = game.execute(Strike("dragon_guard", attack_id="longsword"))
    assert strike.status is ResultStatus.PAUSED
    assert strike.inspection.choice is not None
    assert strike.inspection.choice.kind == "attack_hero_reroll"
    game = _save_reload(game, tmp_path, f"{dragon_id}-attack-reroll.json")
    finished = _choose(game, "keep", "dragon_barbarian")
    assert finished.status is ResultStatus.COMPLETED

    check = next(event.check for event in finished.events if event.check is not None)
    damage = next(event.damage for event in finished.events if event.damage is not None)
    assert check is not None and check.degree.label() == "Critical Success"
    assert damage is not None and damage.multiplier == 2
    assert damage.total == 32
    assert tuple(component.damage_type for component in damage.components) == (
        "slashing", dragon.damage_type
    )
    weapon, rage = damage.components
    assert (weapon.dice, weapon.rolls, weapon.modifier, weapon.amount) == ((8,), (8,), 4, 24)
    assert (rage.dice, rage.rolls, rage.modifier, rage.amount) == ((), (), 4, 8)
    assert "rage" in rage.tags and "instinct" in rage.tags
    assert finished.inspection.in_progress is False
    assert finished.inspection.winner_team == "blue"
    ended = _actor(game, "dragon_barbarian")
    assert ended.barbarian_state.rage is None
    assert ended.temporary_hp == 0
    assert ended.temporary_hp_source_id is None


def test_base_rage_damage_and_agile_halving_stay_separate_typed_components() -> None:
    game = Encounter.start(
        get_setup("barbarian_dragon_diabolic_rage_test"),
        rolls=(10, 1, 10, 2, 20, 4, 4),
    )
    _start_dragon_turn(game)

    assert game.execute(Rage()).status is ResultStatus.PAUSED
    base = _choose(game, "base", "dragon_barbarian")
    assert base.status is ResultStatus.COMPLETED
    active = _actor(game, "dragon_barbarian").barbarian_state.rage
    assert active is not None and active.mode_id == "base" and active.damage_type is None

    ordinary = game.execute(Strike("dragon_guard", attack_id="longsword"))
    assert ordinary.status is ResultStatus.PAUSED
    normal = _choose(game, "keep", "dragon_barbarian")
    first_damage = next(event.damage for event in normal.events if event.damage is not None)
    assert first_damage is not None and first_damage.multiplier == 1
    assert tuple(component.damage_type for component in first_damage.components) == ("slashing", "slashing")
    assert tuple(component.modifier for component in first_damage.components) == (4, 2)

    agile = game.execute(Strike("dragon_guard", attack_id="fist"))
    assert agile.status is ResultStatus.PAUSED
    last = _choose(game, "keep", "dragon_barbarian")
    check = next(event.check for event in last.events if event.check is not None)
    agile_damage = next(event.damage for event in last.events if event.damage is not None)
    assert check is not None and check.map_penalty == -4
    assert agile_damage is not None and agile_damage.multiplier == 2
    assert tuple(component.damage_type for component in agile_damage.components) == (
        "bludgeoning", "bludgeoning"
    )
    weapon, rage = agile_damage.components
    assert (weapon.dice, weapon.rolls, weapon.modifier) == ((4,), (4,), 4)
    assert (rage.modifier, rage.amount) == (1, 2)
    assert not last.inspection.in_progress
    assert last.inspection.winner_team == "blue"


def test_selected_dragon_damage_is_halved_for_agile_and_keeps_its_type() -> None:
    game = Encounter.start(
        get_setup("barbarian_dragon_diabolic_rage_test"),
        rolls=(10, 1, 20, 4, 20, 8),
    )
    _start_dragon_turn(game)

    assert game.execute(Rage()).status is ResultStatus.PAUSED
    assert _choose(game, "dragon_damage", "dragon_barbarian").status is ResultStatus.COMPLETED

    first = game.execute(Strike("dragon_guard", attack_id="fist"))
    assert first.status is ResultStatus.PAUSED
    first = _choose(game, "keep", "dragon_barbarian")
    first_damage = next(event.damage for event in first.events if event.damage is not None)
    assert first_damage is not None and first_damage.multiplier == 2
    weapon, rage = first_damage.components
    assert (weapon.damage_type, weapon.modifier, weapon.amount) == ("bludgeoning", 4, 16)
    assert (rage.damage_type, rage.modifier, rage.amount) == ("fire", 2, 4)

    last = game.execute(Strike("dragon_guard", attack_id="longsword"))
    assert last.status is ResultStatus.PAUSED
    last = _choose(game, "keep", "dragon_barbarian")
    check = next(event.check for event in last.events if event.check is not None)
    damage = next(event.damage for event in last.events if event.damage is not None)
    assert check is not None and check.map_penalty == -5
    assert damage is not None and damage.multiplier == 2
    assert tuple(component.damage_type for component in damage.components) == ("slashing", "fire")
    assert damage.total == 32
    assert not last.inspection.in_progress
    assert last.inspection.winner_team == "blue"


def test_saved_quick_tempered_dragon_mode_supports_glare_and_survives_attack_reroll(
    tmp_path: Path,
) -> None:
    game = Encounter.start(
        get_setup("barbarian_dragon_diabolic_rage_test"),
        rolls=(20, 1, 20, 1, 20, 8, 8),
    )
    # Keep the initiative roll, then accept the free trigger. Dragon mode is a
    # second saved decision owned by the same initiative initialization.
    choice = game.inspect().choice
    assert choice is not None and choice.kind == "initiative_hero_reroll"
    _choose(game, "keep", "dragon_barbarian")
    quick = game.inspect().choice
    assert quick is not None and {item.option_id for item in quick.options} == {"accept", "decline"}
    _choose(game, "accept", "dragon_barbarian")
    mode = game.inspect().choice
    assert mode is not None and {item.option_id for item in mode.options} == {"base", "dragon_damage"}
    game = _save_reload(game, tmp_path, "quick-tempered-dragon-mode.json")
    accepted = _choose(game, "dragon_damage", "dragon_barbarian")
    assert accepted.status is ResultStatus.COMPLETED
    active = _actor(game, "dragon_barbarian")
    assert active.actions_remaining == 3
    assert active.barbarian_state.rage is not None
    assert active.barbarian_state.rage.mode_id == "dragon_damage"
    assert active.temporary_hp == 4

    glare = game.execute(Demoralize("dragon_guard", use_intimidating_glare=True))
    assert glare.status is ResultStatus.PAUSED
    assert glare.inspection.choice is not None
    glare = _choose(game, "keep", "dragon_barbarian")
    check = next(event.check for event in glare.events if event.check is not None)
    assert check is not None
    assert {"rage", "visual"} <= set(check.traits)
    assert "auditory" not in check.traits
    assert all(modifier.amount != -4 for modifier in check.modifier_breakdown)
    attack = game.execute(Strike("dragon_guard", attack_id="longsword"))
    assert attack.status is ResultStatus.PAUSED
    assert attack.inspection.choice is not None
    assert attack.inspection.choice.kind == "attack_hero_reroll"
    game = _save_reload(game, tmp_path, "quick-dragon-attack-reroll.json")
    result = _choose(game, "spend_hero_point", "dragon_barbarian")
    reroll = next(event.check for event in result.events if event.check is not None)
    damage = next(event.damage for event in result.events if event.damage is not None)
    assert reroll is not None and reroll.die == 20 and reroll.degree.label() == "Critical Success"
    assert damage is not None and damage.multiplier == 2
    assert tuple(component.damage_type for component in damage.components) == ("slashing", "fire")
    assert tuple(component.modifier for component in damage.components) == (4, 4)
    assert not result.inspection.in_progress
    assert result.inspection.winner_team == "blue"
    ended = _actor(game, "dragon_barbarian")
    assert ended.barbarian_state.rage is None
    assert ended.temporary_hp == 0
