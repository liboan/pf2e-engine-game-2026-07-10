"""Independent source review of the W1 Bomber bomb variants.

Source: https://2e.aonprd.com/Rules.aspx?ID=3181 says a critical hit
doubles an acid flask's initial and persistent damage, but not its splash.
Alchemist's Fire: https://2e.aonprd.com/Equipment.aspx?ID=3287.
Acid Flask: https://2e.aonprd.com/Equipment.aspx?ID=3286.
"""

import pytest

from pf2e.content import get_setup
from pf2e.encounter import Encounter
from pf2e.model import Choose, QuickAlchemy, QuickBomber, ResultStatus


def _settle_initial(game: Encounter) -> None:
    for _ in range(8):
        choice = game.inspect().choice
        if choice is None:
            return
        assert game.execute(Choose(choice.choice_id, "keep", choice.owner_actor_id)).status in {
            ResultStatus.COMPLETED, ResultStatus.PAUSED,
        }
    raise AssertionError("Bomber initiative did not settle")


@pytest.mark.parametrize(
    ("formula_id", "expected_type", "expected_dice", "expected_flat"),
    (
        ("alchemists_fire_lesser", "fire", (), 2),
        ("acid_flask_lesser", "acid", (6, 6), 0),
    ),
)
def test_critical_bomb_doubles_persistent_damage_but_not_splash_after_saved_choice(
    tmp_path, formula_id, expected_type, expected_dice, expected_flat,
) -> None:
    game = Encounter.start(
        get_setup("l2_bomber_far_lobber_vs_guard_dog"),
        rolls=(20, 1, 20, 1),
    )
    _settle_initial(game)
    assert game.execute(QuickAlchemy("create_consumable", formula_id)).status is ResultStatus.COMPLETED
    started = game.execute(QuickBomber("dog", formula_id))
    assert started.status is ResultStatus.PAUSED
    assert game._state.persistent_effects == []

    path = tmp_path / f"critical-{formula_id}.json"
    game.save(path)
    loaded = Encounter.load(path)
    choice = loaded.inspect().choice
    assert choice is not None and choice.kind == "attack_hero_reroll"
    result = loaded.execute(Choose(choice.choice_id, "keep", choice.owner_actor_id))
    assert result.status is ResultStatus.COMPLETED
    strike = next(event for event in result.events if event.kind == "strike")
    assert strike.check is not None and strike.check.degree.name == "CRITICAL_SUCCESS"
    assert loaded._state.creatures["dog"].hp == 5  # 2 initial + 1 unchanged splash.
    assert len(loaded._state.persistent_effects) == 1
    effect = loaded._state.persistent_effects[0]
    assert (effect.damage_type, effect.dice, effect.flat) == (
        expected_type, expected_dice, expected_flat,
    )

    loaded.save(path)
    assert Encounter.load(path)._state.persistent_effects == [effect]


def test_level_one_bomber_cannot_create_the_new_bombs_or_spend_a_vial() -> None:
    game = Encounter.start(
        get_setup("staged_bomber_alchemist_vs_guard_dog"), rolls=(20, 1),
    )
    _settle_initial(game)
    original_vials = game._state.alchemy_states["alchemist"].stored_vials
    original_actions = game._state.creatures["alchemist"].actions_remaining

    for formula_id in ("alchemists_fire_lesser", "acid_flask_lesser"):
        result = game.execute(QuickAlchemy("create_consumable", formula_id))
        assert result.status is ResultStatus.REJECTED
        assert game._state.alchemy_states["alchemist"].stored_vials == original_vials
        assert game._state.creatures["alchemist"].actions_remaining == original_actions


def test_new_bomb_can_be_created_and_thrown_after_completed_fight_and_rest(tmp_path) -> None:
    game = Encounter.start(
        get_setup("l2_bomber_far_lobber_vs_guard_dog"),
        rolls=(20, 1, 15, 1, 20, 6, 20, 1, 12, 1),
    )
    _settle_initial(game)
    assert game.execute(QuickAlchemy("create_consumable", "alchemists_fire_lesser")).status is ResultStatus.COMPLETED
    assert game.execute(QuickBomber("dog", "alchemists_fire_lesser")).status is ResultStatus.PAUSED
    _settle_initial(game)
    assert game._state.creatures["dog"].hp == 6
    assert game.execute(QuickBomber("dog", "frost_vial_lesser")).status is ResultStatus.PAUSED
    _settle_initial(game)
    assert game.inspect().winner_team == "blue"

    assert game.recover_versatile_vials("alchemist", elapsed_seconds=600).status is ResultStatus.COMPLETED
    # The authored persistent condition has a one-minute absolute deadline;
    # ten minutes of declared exploration must remove it before a save.
    assert not game._state.persistent_effects
    assert game.record_rested(
        ("alchemist",), day_number=2, elapsed_seconds=8 * 60 * 60,
    ).status is ResultStatus.COMPLETED
    assert game.daily_prepare(("alchemist",), {"alchemist": {}}).status is ResultStatus.COMPLETED
    path = tmp_path / "after-fire-rest.json"
    game.save(path)
    game = Encounter.load(path)

    advanced = game.next_encounter(get_setup("l2_bomber_far_lobber_next_vs_guard_dog"))
    assert advanced.status in {ResultStatus.COMPLETED, ResultStatus.PAUSED}
    _settle_initial(game)
    assert game.inspect().turn_actor_id == "alchemist"
    assert game.execute(QuickAlchemy("create_consumable", "acid_flask_lesser")).status is ResultStatus.COMPLETED
    assert game.execute(QuickBomber("next_dog", "acid_flask_lesser")).status is ResultStatus.PAUSED
    _settle_initial(game)
    assert any(
        effect.spell_id == "acid_flask_lesser" and effect.target_actor_id == "next_dog"
        for effect in game._state.persistent_effects
    )
