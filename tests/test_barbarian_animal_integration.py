from __future__ import annotations

from pathlib import Path

import pytest

from pf2e import EndTurn, Encounter, Rage, ResultStatus, Strike
from pf2e.barbarian_content import (
    ANIMAL_BARBARIAN_CHARACTERS,
    ANIMAL_BARBARIAN_INITIAL_STATES,
    ANIMAL_BARBARIAN_SETUPS,
)
from pf2e.content import get_setup
from pf2e.skill_actions import Demoralize


ANIMAL_IDS = tuple(ANIMAL_BARBARIAN_CHARACTERS)


def _actor(game: Encounter, actor_id: str):
    return next(actor for actor in game.inspect().actors if actor.actor_id == actor_id)


def _choose(game: Encounter, option_id: str, owner: str | None = None):
    choice = game.inspect().choice
    assert choice is not None
    return game.choose(choice.choice_id, option_id, owner)


def _start_animal_turn(game: Encounter, *, quick_tempered: str) -> None:
    while game.inspect().turn_actor_id is None:
        choice = game.inspect().choice
        assert choice is not None, "initiative is waiting without a public choice"
        option_ids = {option.option_id for option in choice.options}
        if choice.kind == "initiative_hero_reroll":
            _choose(game, "keep", choice.owner_actor_id)
        elif option_ids == {"accept", "decline"}:
            _choose(game, quick_tempered, choice.owner_actor_id)
        elif choice.kind == "initiative_tie":
            option_id = "animal_barbarian" if "animal_barbarian" in option_ids else choice.options[0].option_id
            _choose(game, option_id)
        else:
            raise AssertionError(f"unexpected startup choice: {choice}")
    assert game.inspect().turn_actor_id == "animal_barbarian"


def _save_reload(game: Encounter, tmp_path: Path, filename: str) -> Encounter:
    path = tmp_path / filename
    game.save(path)
    return Encounter.load(path)


@pytest.mark.parametrize(
    ("animal_id", "quick_tempered", "rolls"),
    (
        # Cat uses ordinary Rage: initiative, jaws, jaw damage, claw miss,
        # claw Hero reroll, claw die.
        ("cat", "decline", (10, 1, 9, 1, 1, 20, 6)),
        # Frog accepts Quick-Tempered and uses Raging Intimidation before
        # making the same two-attack sequence.
        ("frog", "accept", (10, 1, 10, 9, 1, 1, 20, 6)),
    ),
)
def test_cat_and_frog_finish_public_rage_fights_with_saved_attacks_and_agile_map(
    animal_id: str,
    quick_tempered: str,
    rolls: tuple[int, ...],
    tmp_path: Path,
) -> None:
    character = ANIMAL_BARBARIAN_CHARACTERS[animal_id]
    setup_id = f"barbarian_animal_{animal_id}_rage_test"
    assert ANIMAL_BARBARIAN_SETUPS[setup_id] == get_setup(setup_id)
    assert ANIMAL_BARBARIAN_INITIAL_STATES[character.definition.definition_id] == character.barbarian_state

    game = Encounter.start(get_setup(setup_id), rolls=rolls)
    _start_animal_turn(game, quick_tempered=quick_tempered)
    actor = _actor(game, "animal_barbarian")
    assert actor.hp == actor.max_hp == 23
    assert actor.barbarian_state is not None
    assert actor.barbarian_state.instinct_id == "animal"
    assert actor.barbarian_state.animal_choice == animal_id
    assert actor.barbarian_state.class_feat_id == character.barbarian_state.class_feat_id

    primary_id = f"animal_{animal_id}_jaws"
    agile_id = f"animal_{animal_id}_{'claw' if animal_id == 'cat' else 'tongue'}"
    primary_type = "piercing" if animal_id == "cat" else "bludgeoning"
    agile_type = "slashing" if animal_id == "cat" else "bludgeoning"
    if quick_tempered == "decline":
        strike_ids_before_rage = {strike.attack_id for strike in game.options().strikes}
        assert {"longsword", "fist"} <= strike_ids_before_rage
        assert primary_id not in strike_ids_before_rage and agile_id not in strike_ids_before_rage
        before = game.inspect()
        rejected_unraged_animal_attack = game.execute(
            Strike("animal_guard", attack_id=primary_id)
        )
        assert rejected_unraged_animal_attack.status is ResultStatus.REJECTED
        assert "not currently available" in rejected_unraged_animal_attack.message
        assert game.inspect() == before
        started = game.execute(Rage())
        assert started.status is ResultStatus.COMPLETED
    actor = _actor(game, "animal_barbarian")
    assert actor.barbarian_state.rage is not None
    assert actor.temporary_hp == 4
    active_ids = {strike.attack_id for strike in game.options().strikes}
    assert {"fist", primary_id, agile_id} <= active_ids
    assert "longsword" not in active_ids

    before = game.inspect()
    rejected_raging_weapon = game.execute(
        Strike("animal_guard", attack_id="longsword")
    )
    assert rejected_raging_weapon.status is ResultStatus.REJECTED
    assert "not currently available" in rejected_raging_weapon.message
    assert game.inspect() == before

    # The Rage is committed and serialized before the encounter's attacks.
    game = _save_reload(game, tmp_path, f"{animal_id}-active-rage.json")
    assert _actor(game, "animal_barbarian").barbarian_state.rage is not None

    if animal_id == "frog":
        glare = game.execute(
            Demoralize("animal_guard", use_intimidating_glare=True)
        )
        assert glare.status is ResultStatus.PAUSED
        glare = _choose(game, "keep", "animal_barbarian")
        check = next(event.check for event in glare.events if event.check is not None)
        assert check is not None
        assert {"rage", "visual"} <= set(check.traits)
        assert "auditory" not in check.traits
        assert all(modifier.amount != -4 for modifier in check.modifier_breakdown)

    primary = game.execute(Strike("animal_guard", attack_id=primary_id))
    assert primary.status is ResultStatus.PAUSED
    assert primary.inspection.choice is not None
    assert primary.inspection.choice.kind == "attack_hero_reroll"
    primary = _choose(game, "keep", "animal_barbarian")
    primary_check = next(event.check for event in primary.events if event.check is not None)
    primary_damage = next(event.damage for event in primary.events if event.damage is not None)
    assert primary_check is not None
    assert primary_check.attack_id == primary_id
    assert primary_check.modifier == 7 and primary_check.map_penalty == 0
    assert primary_damage is not None and primary_damage.multiplier == 1
    assert primary_damage.total == 7
    assert tuple(component.damage_type for component in primary_damage.components) == (
        primary_type, primary_type
    )
    assert tuple(component.modifier for component in primary_damage.components) == (4, 2)

    agile = game.execute(Strike("animal_guard", attack_id=agile_id))
    assert agile.status is ResultStatus.PAUSED
    assert agile.inspection.choice is not None
    assert agile.inspection.choice.kind == "attack_hero_reroll"
    game = _save_reload(game, tmp_path, f"{animal_id}-attack-hero-choice.json")
    resolved = _choose(game, "spend_hero_point", "animal_barbarian")
    rerolled_check = next(event.check for event in resolved.events if event.check is not None)
    agile_damage = next(event.damage for event in resolved.events if event.damage is not None)
    assert rerolled_check is not None
    assert rerolled_check.die == 20
    assert rerolled_check.degree.label() == "Critical Success"
    assert rerolled_check.attack_id == agile_id
    assert rerolled_check.modifier == 3 and rerolled_check.map_penalty == -4
    assert agile_damage is not None and agile_damage.multiplier == 2
    assert agile_damage.total == 22
    assert tuple(component.damage_type for component in agile_damage.components) == (
        agile_type, agile_type
    )
    assert tuple(component.modifier for component in agile_damage.components) == (4, 1)
    assert tuple(component.amount for component in agile_damage.components) == (20, 2)
    assert resolved.inspection.in_progress is False
    assert resolved.inspection.winner_team == "blue"

    ended = _actor(game, "animal_barbarian")
    assert ended.barbarian_state is not None and ended.barbarian_state.rage is None
    assert ended.temporary_hp == 0 and ended.temporary_hp_source_id is None


def test_frog_attacks_are_hidden_and_rejected_before_quick_tempered_rage() -> None:
    game = Encounter.start(
        get_setup("barbarian_animal_frog_rage_test"),
        rolls=(10, 1),
    )
    _start_animal_turn(game, quick_tempered="decline")
    actor = _actor(game, "animal_barbarian")
    assert actor.barbarian_state is not None and actor.barbarian_state.rage is None
    available = {strike.attack_id for strike in game.options().strikes}
    assert {"longsword", "fist"} <= available
    assert "animal_frog_jaws" not in available
    assert "animal_frog_tongue" not in available
    before = game.inspect()
    rejected = game.execute(Strike("animal_guard", attack_id="animal_frog_jaws"))
    assert rejected.status is ResultStatus.REJECTED
    assert "not currently available" in rejected.message
    assert game.inspect() == before


@pytest.mark.parametrize("animal_id", ANIMAL_IDS)
def test_animal_attacks_return_to_unraged_availability_after_rage_expires(
    animal_id: str,
) -> None:
    game = Encounter.start(
        get_setup(f"barbarian_animal_{animal_id}_rage_test"),
        rolls=(10, 1),
    )
    _start_animal_turn(game, quick_tempered="accept")
    actor = _actor(game, "animal_barbarian")
    assert actor.barbarian_state is not None and actor.barbarian_state.rage is not None

    # Every full round advances the documented six-second encounter clock.
    # Spending no actions leaves both participants healthy through expiration.
    for _ in range(10):
        game.execute(EndTurn())
        assert game.inspect().turn_actor_id == "animal_guard"
        game.execute(EndTurn())
        assert game.inspect().turn_actor_id == "animal_barbarian"

    actor = _actor(game, "animal_barbarian")
    assert game.inspect().round_number == 11
    assert actor.barbarian_state is not None and actor.barbarian_state.rage is None
    assert actor.temporary_hp == 0 and actor.temporary_hp_source_id is None
    available = {strike.attack_id for strike in game.options().strikes}
    assert {"longsword", "fist"} <= available
    primary_id = f"animal_{animal_id}_jaws"
    assert primary_id not in available
    before = game.inspect()
    rejected = game.execute(Strike("animal_guard", attack_id=primary_id))
    assert rejected.status is ResultStatus.REJECTED
    assert "not currently available" in rejected.message
    assert game.inspect() == before
