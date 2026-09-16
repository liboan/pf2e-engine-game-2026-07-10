"""Independent public-play review of the first staged Swashbuckler slice.

Rules references:
- Swashbuckler: https://2e.aonprd.com/Classes.aspx?ID=63
- Bravado: https://2e.aonprd.com/Traits.aspx?ID=801
- Demoralize: https://2e.aonprd.com/Actions.aspx?ID=2395
- Warrior background: https://2e.aonprd.com/Backgrounds.aspx?ID=445
"""

from __future__ import annotations

from pathlib import Path

import pytest

import pf2e.content as content
from pf2e.encounter import Encounter
from pf2e.model import (
    CreaturePlacement,
    EncounterSetup,
    EndTurn,
    Position,
    ResultStatus,
    Strike,
    Stride,
)
from pf2e.skill_actions import Demoralize


SETUP_ID = "staged_braggart_swashbuckler_vs_guard_dog"


def _actor(game: Encounter, actor_id: str):
    return next(actor for actor in game.inspect().actors if actor.actor_id == actor_id)


def _choose(game: Encounter, option_id: str):
    choice = game.inspect().choice
    assert choice is not None
    return game.choose(choice.choice_id, option_id, choice.owner_actor_id)


def _settle_initiative(game: Encounter) -> None:
    for _ in range(8):
        choice = game.inspect().choice
        if choice is None:
            return
        assert choice.kind in {"initiative_hero_reroll", "initiative_tie"}
        option_id = (
            "keep"
            if any(option.option_id == "keep" for option in choice.options)
            else choice.options[0].option_id
        )
        assert game.choose(choice.choice_id, option_id, choice.owner_actor_id).status in {
            ResultStatus.PAUSED,
            ResultStatus.COMPLETED,
        }
    raise AssertionError("initiative did not settle within eight choices")


def test_healthy_fight_saves_strike_and_bravado_check_then_wins(tmp_path: Path) -> None:
    definition = content.get_definition("swashbuckler_braggart_level_1")
    setup = content.get_setup(SETUP_ID)
    assert definition not in content.CREATURES.values()
    assert setup.setup_id not in content.SETUPS
    assert definition.background == "Warrior"
    assert "Intimidating Glare" in definition.feats
    assert (definition.class_name, definition.land_speed_ft) == ("Swashbuckler", 25)
    assert {"swashbuckler_braggart", "precise_strike", "stylish_combatant"} <= set(
        definition.abilities
    )
    proficiencies = dict(definition.proficiencies)
    assert {
        "simple_weapons": "trained",
        "martial_weapons": "trained",
        "unarmed_attacks": "trained",
    }.items() <= proficiencies.items()

    # Initiatives; ordinary dagger attack/damage; Demoralize; MAP dagger
    # attack/damage. Both PCs begin healthy and the dog is defeated publicly.
    game = Encounter.start(setup, rolls=(20, 1, 8, 2, 8, 11, 1))
    assert all(actor.hp == actor.max_hp for actor in game.inspect().actors)
    _settle_initiative(game)

    first = game.execute(Strike("braggart_dog", attack_id="dagger"))
    assert first.status is ResultStatus.PAUSED
    assert first.inspection.choice is not None
    assert first.inspection.choice.kind == "attack_hero_reroll"
    strike_path = tmp_path / "swashbuckler-no-panache-strike.json"
    game.save(strike_path)
    game = Encounter.load(strike_path)
    assert game.inspect().choice == first.inspection.choice
    first = _choose(game, "keep")
    assert first.status is ResultStatus.COMPLETED
    first_damage = next(event.damage for event in first.events if event.damage is not None)
    assert first_damage is not None and first_damage.total == 6
    assert first_damage.components[-1].source == "swashbuckler_precise_strike"
    assert first_damage.components[-1].amount == 2
    assert not _actor(game, "braggart").panache

    check_offer = game.execute(
        Demoralize("braggart_dog", use_intimidating_glare=True)
    )
    assert check_offer.status is ResultStatus.PAUSED
    assert check_offer.inspection.choice is not None
    assert check_offer.inspection.choice.kind == "family_action"
    assert "Hero Point" in check_offer.inspection.choice.prompt
    check_path = tmp_path / "swashbuckler-bravado-check.json"
    game.save(check_path)
    game = Encounter.load(check_path)
    assert game.inspect().choice == check_offer.inspection.choice
    checked = _choose(game, "keep")
    check = next(event.check for event in checked.events if event.kind == "demoralize_check")
    assert check is not None
    assert (check.die, check.modifier, check.total, check.dc) == (8, 6, 14, 14)
    assert _actor(game, "braggart").panache
    assert _actor(game, "braggart").panache_expires_at_end is None
    assert game.effective_speed_ft("braggart") == 30

    final = game.execute(Strike("braggart_dog", attack_id="dagger"))
    assert final.status is ResultStatus.PAUSED
    final = _choose(game, "keep")
    assert final.status is ResultStatus.COMPLETED
    final_check = next(event.check for event in final.events if event.kind == "strike")
    assert final_check is not None
    assert (final_check.attack_count, final_check.map_penalty) == (2, -4)
    assert not final.inspection.in_progress and final.inspection.winner_team == "blue"
    assert _actor(game, "braggart_dog").defeated
    assert not _actor(game, "braggart").panache


def test_no_panache_natural_extremes_and_critical_precision() -> None:
    # Initiatives; natural-1 first attack; natural-20 MAP attack; two critical
    # dagger dice. A miss rolls no damage, while the critical doubles +2 precision.
    game = Encounter.start(content.get_setup(SETUP_ID), rolls=(20, 1, 1, 20, 2, 3))
    _settle_initiative(game)
    missed = game.execute(Strike("braggart_dog", attack_id="dagger"))
    assert missed.status is ResultStatus.PAUSED
    missed = _choose(game, "keep")
    assert missed.status is ResultStatus.COMPLETED
    miss_check = next(event.check for event in missed.events if event.kind == "strike")
    assert miss_check is not None and miss_check.die == 1
    assert not any(event.damage is not None for event in missed.events)
    assert not _actor(game, "braggart").panache

    critical = game.execute(Strike("braggart_dog", attack_id="dagger"))
    assert critical.status is ResultStatus.PAUSED
    critical = _choose(game, "keep")
    damage = next(event.damage for event in critical.events if event.damage is not None)
    assert damage is not None
    assert damage.components[-1].source == "swashbuckler_precise_strike"
    assert damage.components[-1].amount == 4
    assert _actor(game, "braggart_dog").defeated


def test_failure_panache_enables_actual_thirty_foot_stride_then_expires_and_immunity_still_allows_bravado(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    base = content.get_setup(SETUP_ID)
    setup = EncounterSetup(
        setup_id="review_braggart_speed_and_immunity",
        name="Review Braggart speed and immunity",
        width=7,
        height=3,
        placements=(
            CreaturePlacement(
                "braggart",
                base.placements[0].definition_id,
                "Braggart Swashbuckler",
                "blue",
                Position(0, 1),
            ),
            CreaturePlacement(
                "braggart_dog",
                base.placements[1].definition_id,
                "Guard Dog",
                "red",
                Position(6, 2),
            ),
        ),
    )
    monkeypatch.setattr(
        content,
        "_STAGED_SETUPS",
        content._STAGED_SETUPS | {setup.setup_id: setup},
    )
    game = Encounter.start(setup, rolls=(20, 1, 4, 8))
    _settle_initiative(game)

    failed = game.execute(Demoralize("braggart_dog", use_intimidating_glare=True))
    assert failed.status is ResultStatus.PAUSED
    failed = _choose(game, "keep")
    failed_check = next(event.check for event in failed.events if event.kind == "demoralize_check")
    assert failed_check is not None and failed_check.degree.name == "FAILURE"
    assert _actor(game, "braggart").panache_expires_at_end == 2
    assert game.effective_speed_ft("braggart") == 30

    path = tuple(Position(x, 1) for x in range(1, 7))
    assert game.execute(Stride(path)).status is ResultStatus.COMPLETED
    assert _actor(game, "braggart").position == Position(6, 1)
    assert game.execute(EndTurn()).status is ResultStatus.COMPLETED
    assert game.execute(EndTurn()).status is ResultStatus.COMPLETED
    assert game.inspect().turn_actor_id == "braggart"
    assert _actor(game, "braggart").panache
    assert game.execute(EndTurn()).status is ResultStatus.COMPLETED
    assert not _actor(game, "braggart").panache
    assert game.effective_speed_ft("braggart") == 25

    assert game.execute(EndTurn()).status is ResultStatus.COMPLETED
    repeated = game.execute(Demoralize("braggart_dog", use_intimidating_glare=True))
    assert repeated.status is ResultStatus.PAUSED
    repeated = _choose(game, "keep")
    assert _actor(game, "braggart").panache
    assert _actor(game, "braggart").panache_expires_at_end is None
    assert not any(
        effect.kind == "frightened"
        for effect in _actor(game, "braggart_dog").condition_effects
    )


def test_non_swashbuckler_remains_blocked_by_demoralize_immunity(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    setup = EncounterSetup(
        setup_id="review_non_swashbuckler_demoralize_immunity",
        name="Review ordinary Demoralize immunity",
        width=4,
        height=3,
        placements=(
            CreaturePlacement(
                "ordinary_fighter",
                content.MELEE_FIGHTER_M.definition_id,
                "Ordinary Fighter",
                "blue",
                Position(1, 1),
            ),
            CreaturePlacement(
                "ordinary_dog",
                content.GUARD_DOG.definition_id,
                "Guard Dog",
                "red",
                Position(2, 1),
            ),
        ),
    )
    monkeypatch.setattr(
        content,
        "_STAGED_SETUPS",
        content._STAGED_SETUPS | {setup.setup_id: setup},
    )
    game = Encounter.start(setup, rolls=(20, 1, 11))
    _settle_initiative(game)
    first = game.execute(Demoralize("ordinary_dog", spoken_language="Common"))
    assert first.status is ResultStatus.PAUSED
    assert _choose(game, "keep").status is ResultStatus.COMPLETED

    before = game.inspect()
    dice_before = game._dice.to_data()
    repeated = game.execute(Demoralize("ordinary_dog", spoken_language="Common"))
    assert repeated.status is ResultStatus.REJECTED
    assert "temporarily immune" in repeated.message
    assert game.inspect() == before
    assert game._dice.to_data() == dice_before
