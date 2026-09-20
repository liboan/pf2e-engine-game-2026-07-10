"""Independent public review of the W1 Intimidating Strike alternatives.

Source: https://2e.aonprd.com/Feats.aspx?ID=4782. The feat's frightened
rider needs a damaging hit and has emotion, fear, and mental traits.
"""

from dataclasses import replace
from types import MappingProxyType

import pf2e.content as content
from pf2e.barbarian import Rage
from pf2e.encounter import Encounter
from pf2e.fighter import IntimidatingStrike
from pf2e.model import (
    AttackDefinition,
    Choose,
    CreaturePlacement,
    DamageDefense,
    EncounterSetup,
    Position,
    ResultStatus,
)
from pf2e.opponent_content import SKELETON_GUARD


def _settle(game: Encounter, *, decline_optional_rage: bool = False) -> None:
    for _ in range(8):
        choice = game.inspect().choice
        if choice is None:
            return
        option_id = (
            "decline"
            if decline_optional_rage and any(option.option_id == "decline" for option in choice.options)
            else "keep"
        )
        assert game.execute(Choose(choice.choice_id, option_id, choice.owner_actor_id)).status in {
            ResultStatus.COMPLETED, ResultStatus.PAUSED,
        }
    raise AssertionError("initiative did not settle")


def _registered_setup(monkeypatch, name: str, opponent) -> EncounterSetup:
    setup = EncounterSetup(
        name, name, 4, 3,
        (
            CreaturePlacement(
                "fighter", "fighter_m_level_2_intimidating_strike", "Fighter", "blue", Position(1, 1),
            ),
            CreaturePlacement("target", opponent.definition_id, "Target", "red", Position(2, 1)),
        ),
    )
    monkeypatch.setattr(
        content, "_STAGED_CREATURES",
        MappingProxyType({**content._STAGED_CREATURES, opponent.definition_id: opponent}),
    )
    monkeypatch.setattr(
        content, "_STAGED_SETUPS",
        MappingProxyType({**content._STAGED_SETUPS, setup.setup_id: setup}),
    )
    return setup


def test_mindless_target_takes_public_strike_damage_without_fear(monkeypatch) -> None:
    setup = _registered_setup(
        monkeypatch, "review_intimidating_strike_mindless", SKELETON_GUARD.definition,
    )
    game = Encounter.start(setup, rolls=(20, 1, 12, 4))
    _settle(game)
    assert game.execute(IntimidatingStrike("target", "fist")).status is ResultStatus.PAUSED
    _settle(game)

    assert game._state.creatures["target"].hp < SKELETON_GUARD.definition.hp
    assert not any(
        effect.kind == "frightened" and effect.target_actor_id == "target"
        for effect in game._state.condition_effects
    )


def test_fully_resisted_public_hit_spends_two_actions_without_fear(monkeypatch) -> None:
    warded = replace(
        content.get_definition("guard_dog_mc2924"),
        definition_id="review_intimidating_strike_warded_dog",
        damage_defenses=(DamageDefense("resistance", "all", 100, source="review ward"),),
    )
    setup = _registered_setup(monkeypatch, "review_intimidating_strike_zero_damage", warded)
    game = Encounter.start(setup, rolls=(20, 1, 12, 8))
    _settle(game)
    assert game.execute(IntimidatingStrike("target", "longsword")).status is ResultStatus.PAUSED
    _settle(game)

    assert game._state.creatures["fighter"].actions_remaining == 1
    assert game._state.creatures["fighter"].strikes_this_turn == 1
    assert game._state.creatures["target"].hp == warded.hp
    assert not any(
        effect.kind == "frightened" and effect.target_actor_id == "target"
        for effect in game._state.condition_effects
    )


def test_intimidating_strike_rejects_a_ranged_attack_without_spending_actions(monkeypatch) -> None:
    """The printed activity says melee Strike even when an actor has a bow."""
    fighter = content.get_definition("fighter_m_level_2_intimidating_strike")
    ranged = AttackDefinition(
        "review_bow", "Review Bow", 10, 0,
        frozenset({"attack", "ranged"}), "piercing", (6,), 0,
        range_increment_ft=20, max_range_ft=120,
    )
    altered = replace(
        fighter,
        definition_id="review_intimidator_with_bow",
        attacks=(*fighter.attacks, ranged),
    )
    setup = EncounterSetup(
        "review_intimidating_strike_ranged_rejection", "Ranged rejection", 4, 3,
        (
            CreaturePlacement("fighter", altered.definition_id, "Fighter", "blue", Position(1, 1)),
            CreaturePlacement("target", "guard_dog_mc2924", "Guard Dog", "red", Position(2, 1)),
        ),
    )
    monkeypatch.setattr(
        content, "_STAGED_CREATURES",
        MappingProxyType({**content._STAGED_CREATURES, altered.definition_id: altered}),
    )
    monkeypatch.setattr(
        content, "_STAGED_SETUPS",
        MappingProxyType({**content._STAGED_SETUPS, setup.setup_id: setup}),
    )
    game = Encounter.start(setup, rolls=(20, 1, 12, 6))
    _settle(game)
    before_actions = game._state.creatures["fighter"].actions_remaining
    before_attacks = game._state.creatures["fighter"].strikes_this_turn

    result = game.execute(IntimidatingStrike("target", "review_bow"))

    assert result.status is ResultStatus.REJECTED
    assert game._state.creatures["fighter"].actions_remaining == before_actions
    assert game._state.creatures["fighter"].strikes_this_turn == before_attacks


def test_bear_alternate_rages_then_saves_damaging_intimidating_strike(tmp_path) -> None:
    game = Encounter.start(
        content.get_setup("staged_barbarian_level_2_intimidating_strike"),
        rolls=(20, 1, 12, 1),
    )
    _settle(game, decline_optional_rage=True)
    assert game.execute(Rage()).status is ResultStatus.COMPLETED
    assert game.execute(IntimidatingStrike("dog", "animal_bear_jaws")).status is ResultStatus.PAUSED
    assert game._state.creatures["barbarian"].actions_remaining == 0
    assert game._state.creatures["barbarian"].strikes_this_turn == 1

    path = tmp_path / "bear-intimidating-strike-pending.json"
    game.save(path)
    loaded = Encounter.load(path)
    choice = loaded.inspect().choice
    assert choice is not None and choice.kind == "attack_hero_reroll"
    result = loaded.execute(Choose(choice.choice_id, "keep", choice.owner_actor_id))
    assert result.status is ResultStatus.COMPLETED
    assert loaded._state.creatures["dog"].hp < content.get_definition("guard_dog_mc2924").hp
    assert any(
        effect.kind == "frightened" and effect.target_actor_id == "dog"
        for effect in loaded._state.condition_effects
    )
