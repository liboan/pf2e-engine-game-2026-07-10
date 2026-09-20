"""Content W1: the finite level-2 Bomber bomb-variant family.

Sources checked 2026-09-20:
* Alchemist's Fire (lesser): https://2e.aonprd.com/Equipment.aspx?ID=3287
* Acid Flask (lesser): https://2e.aonprd.com/Equipment.aspx?ID=3286
* Bomb splash and persistent damage: https://2e.aonprd.com/Rules.aspx?ID=3181
"""

import json
from pathlib import Path

import pytest

from pf2e.alchemist_content import (
    BOMBER_FIELD_FORMULA_IDS,
    BOMBER_LEVEL_2_BOMB_FORMULA_IDS,
    admitted_bomber_bomb_facts,
)
from pf2e.alchemy_content import FORMULAS_BY_ID
from pf2e.content import get_setup
from pf2e.encounter import Encounter
from pf2e.model import Choose, EndTurn, QuickAlchemy, QuickBomber, ResultStatus
from pf2e.terminal import run_terminal


def _settle(game: Encounter) -> None:
    while (choice := game.inspect().choice) is not None:
        assert game.execute(Choose(choice.choice_id, "keep", choice.owner_actor_id)).status in {
            ResultStatus.COMPLETED,
            ResultStatus.PAUSED,
        }


def _fire_game(*, rolls=(20, 1, 15, 1)) -> Encounter:
    game = Encounter.start(
        get_setup("l2_bomber_far_lobber_vs_guard_dog"),
        rolls=rolls,
    )
    _settle(game)
    assert game.execute(QuickAlchemy("create_consumable", "alchemists_fire_lesser")).status is ResultStatus.COMPLETED
    result = game.execute(QuickBomber("dog", "alchemists_fire_lesser"))
    assert result.status is ResultStatus.PAUSED
    choice = result.inspection.choice
    assert choice is not None and choice.kind == "attack_hero_reroll"
    assert game.execute(Choose(choice.choice_id, "keep", choice.owner_actor_id)).status is ResultStatus.COMPLETED
    return game


def test_l2_bomber_item_menu_adds_only_source_checked_fire_and_acid_variants() -> None:
    assert BOMBER_LEVEL_2_BOMB_FORMULA_IDS == (
        "alchemists_fire_lesser",
        "acid_flask_lesser",
    )
    assert admitted_bomber_bomb_facts("alchemists_fire_lesser") is None
    assert admitted_bomber_bomb_facts("acid_flask_lesser") is None
    assert admitted_bomber_bomb_facts("alchemists_fire_lesser", character_level=2) is FORMULAS_BY_ID["alchemists_fire_lesser"].facts
    assert admitted_bomber_bomb_facts("acid_flask_lesser", character_level=2) is FORMULAS_BY_ID["acid_flask_lesser"].facts
    fire = FORMULAS_BY_ID["alchemists_fire_lesser"]
    acid = FORMULAS_BY_ID["acid_flask_lesser"]
    assert (fire.facts.initial_damage_dice, fire.facts.persistent_damage_type, fire.facts.persistent_damage_flat, fire.facts.splash_damage) == ((8,), "fire", 1, 1)
    assert (acid.facts.initial_damage_flat, acid.facts.persistent_damage_type, acid.facts.persistent_damage_dice, acid.facts.splash_damage) == (1, "acid", (6,), 1)
    assert BOMBER_FIELD_FORMULA_IDS == ("bottled_lightning_lesser", "frost_vial_lesser")


def test_alchemists_fire_quick_bomber_consumes_and_saves_persistent_damage(tmp_path: Path) -> None:
    game = _fire_game()
    dog = game._state.creatures["dog"]
    assert dog.hp == 6  # 1d8 initial fire (1) plus 1 fire splash.
    assert "alchemist:quick:1" in game._state.consumed_infused_item_ids
    persistent = game._state.persistent_effects
    assert len(persistent) == 1
    assert (persistent[0].spell_id, persistent[0].damage_type, persistent[0].dice, persistent[0].flat) == (
        "alchemists_fire_lesser", "fire", (), 1,
    )

    save_path = tmp_path / "w1-fire-persistent.json"
    game.save(save_path)
    restored = Encounter.load(save_path)
    assert restored._state.persistent_effects == persistent
    assert restored._state.consumed_infused_item_ids == {"alchemist:quick:1"}

    tampered = json.loads(save_path.read_text())
    tampered["state"]["persistent_effects"][0][3:] = [
        "acid_flask_lesser", "acid", [6], 0, tampered["state"]["persistent_effects"][0][7],
    ]
    save_path.write_text(json.dumps(tampered))
    with pytest.raises(ValueError, match="consumed Bomber formula provenance"):
        Encounter.load(save_path)


def test_acid_flask_variant_uses_existing_persistent_d6_and_recovery_lifecycle() -> None:
    game = Encounter.start(
        get_setup("l2_bomber_far_lobber_vs_guard_dog"),
        rolls=(20, 1, 15, 1, 20),
    )
    _settle(game)
    assert game.execute(QuickAlchemy("create_consumable", "acid_flask_lesser")).status is ResultStatus.COMPLETED
    result = game.execute(QuickBomber("dog", "acid_flask_lesser"))
    assert result.status is ResultStatus.PAUSED
    choice = result.inspection.choice
    assert choice is not None
    assert game.execute(Choose(choice.choice_id, "keep", choice.owner_actor_id)).status is ResultStatus.COMPLETED
    effect = game._state.persistent_effects[0]
    assert (effect.spell_id, effect.damage_type, effect.dice, effect.flat) == (
        "acid_flask_lesser", "acid", (6,), 0,
    )
    assert game.execute(EndTurn()).status is ResultStatus.COMPLETED
    tick = game.execute(EndTurn())
    assert tick.status is ResultStatus.COMPLETED
    assert any(event.kind == "persistent_damage" for event in tick.events)
    assert any(event.kind == "persistent_recovered" for event in tick.events)
    assert not game._state.persistent_effects


@pytest.mark.parametrize(
    ("formula_id", "persistent_dice", "persistent_flat"),
    (
        ("alchemists_fire_lesser", (), 2),
        ("acid_flask_lesser", (6, 6), 0),
    ),
)
def test_critical_bomb_doubles_persistent_damage_but_not_splash_after_saved_choice(
    formula_id: str,
    persistent_dice: tuple[int, ...],
    persistent_flat: int,
    tmp_path: Path,
) -> None:
    game = Encounter.start(
        get_setup("l2_bomber_far_lobber_vs_guard_dog"),
        rolls=(20, 1, 20, 1, 1, 1),
    )
    _settle(game)
    assert game.execute(QuickAlchemy("create_consumable", formula_id)).status is ResultStatus.COMPLETED
    result = game.execute(QuickBomber("dog", formula_id))
    assert result.status is ResultStatus.PAUSED
    choice = result.inspection.choice
    assert choice is not None and choice.kind == "attack_hero_reroll"
    pending_path = tmp_path / f"critical-pending-{formula_id}.json"
    game.save(pending_path)
    game = Encounter.load(pending_path)
    choice = game.inspect().choice
    assert choice is not None and choice.kind == "attack_hero_reroll"
    assert game.execute(Choose(choice.choice_id, "keep", choice.owner_actor_id)).status is ResultStatus.COMPLETED
    assert game._state.creatures["dog"].hp == 5  # doubled initial packet plus one undoubled splash.
    effect = game._state.persistent_effects[0]
    assert (effect.dice, effect.flat) == (persistent_dice, persistent_flat)

    save_path = tmp_path / f"critical-{formula_id}.json"
    game.save(save_path)
    restored = Encounter.load(save_path)
    assert [(item.dice, item.flat) for item in restored._state.persistent_effects] == [
        (persistent_dice, persistent_flat),
    ]


def test_terminal_creates_and_throws_the_new_fire_formula() -> None:
    commands = iter((
        "2", "1",  # Keep initiative.
        "4", "9",  # Quick Alchemy -> Alchemist's Fire (lesser).
        "6", "1", "1",  # Quick Bomber -> fire -> Guard Dog.
        "2", "1",  # Resolve the saved Strike choice, then keep it.
        "x",
    ))
    output: list[str] = []
    assert run_terminal(
        setup=get_setup("l2_bomber_far_lobber_vs_guard_dog"),
        rolls=(20, 1, 15, 1),
        input_fn=lambda: next(commands),
        output_fn=output.append,
    ) == 0
    transcript = "\n".join(output)
    assert "Alchemist's Fire (lesser)" in transcript
    assert "creates alchemists fire lesser" in transcript
    assert "uses Quick Bomber to draw alchemists fire lesser" in transcript


def test_bomb_persistent_damage_expires_during_rest_before_save_and_next_scene(tmp_path: Path) -> None:
    game = Encounter.start(
        get_setup("l2_bomber_far_lobber_vs_guard_dog"),
        rolls=(20, 1, 15, 1, 20, 3, 20, 1),
    )
    _settle(game)
    assert game.execute(QuickAlchemy("create_consumable", "alchemists_fire_lesser")).status is ResultStatus.COMPLETED
    fire = game.execute(QuickBomber("dog", "alchemists_fire_lesser"))
    assert fire.status is ResultStatus.PAUSED
    choice = fire.inspection.choice
    assert choice is not None
    assert game.execute(Choose(choice.choice_id, "keep", choice.owner_actor_id)).status is ResultStatus.COMPLETED
    frost = game.execute(QuickBomber("dog", "frost_vial_lesser"))
    assert frost.status is ResultStatus.PAUSED
    choice = frost.inspection.choice
    assert choice is not None
    assert game.execute(Choose(choice.choice_id, "keep", choice.owner_actor_id)).status is ResultStatus.COMPLETED
    assert game.inspect().winner_team == "blue"
    assert game._state.persistent_effects

    recovered = game.recover_versatile_vials("alchemist", elapsed_seconds=600)
    assert recovered.status is ResultStatus.COMPLETED
    assert game._state.world_time_seconds == 600
    assert not game._state.persistent_effects

    save_path = tmp_path / "w1-rested-fire.json"
    game.save(save_path)
    restored = Encounter.load(save_path)
    assert not restored._state.persistent_effects
    next_scene = restored.next_encounter(get_setup("l2_bomber_far_lobber_next_vs_guard_dog"))
    assert next_scene.status in {ResultStatus.COMPLETED, ResultStatus.PAUSED}
    assert not restored._state.persistent_effects
