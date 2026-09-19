"""Independent source-informed review of the selected Flying Blade build.

Rules checked 2026-09-16:

* Flying Blade: https://2e.aonprd.com/Feats.aspx?ID=6130
* Thrown: https://2e.aonprd.com/Traits.aspx?ID=711
* Confident Finisher: https://2e.aonprd.com/Actions.aspx?ID=2818
* Reactive Strike: https://2e.aonprd.com/Feats.aspx?ID=5832
* Swashbuckler: https://2e.aonprd.com/Classes.aspx?ID=63
"""

from pathlib import Path

import pytest

import pf2e.content as content
from pf2e.encounter import Encounter
from pf2e.model import Choose, CreaturePlacement, EncounterSetup, Interact, Position, ResultStatus, Strike
from pf2e.skill_actions import Demoralize
from pf2e.swashbuckler import ConfidentFinisher


SETUP_ID = "staged_braggart_swashbuckler_vs_guard_dog"


def _actor(game: Encounter, actor_id: str):
    return next(actor for actor in game.inspect().actors if actor.actor_id == actor_id)


def _choose(game: Encounter, option_id: str):
    choice = game.inspect().choice
    assert choice is not None
    return game.execute(Choose(choice.choice_id, option_id, choice.owner_actor_id))


def _settle_initiative(game: Encounter) -> None:
    for _ in range(8):
        choice = game.inspect().choice
        if choice is None:
            return
        option_id = "keep" if any(option.option_id == "keep" for option in choice.options) else choice.options[0].option_id
        assert _choose(game, option_id).status in {ResultStatus.PAUSED, ResultStatus.COMPLETED}
    raise AssertionError("initiative did not settle")


def _admit(monkeypatch: pytest.MonkeyPatch, setup: EncounterSetup) -> None:
    monkeypatch.setattr(content, "_STAGED_SETUPS", content._STAGED_SETUPS | {setup.setup_id: setup})


def test_selected_level_one_sheet_has_required_grants_and_proficiencies() -> None:
    definition = content.get_definition("swashbuckler_braggart_level_1")
    assert (definition.hp, definition.ac, definition.perception, definition.class_dc) == (19, 18, 5, 17)
    assert definition.ability_modifiers == (
        ("strength", 2),
        ("dexterity", 4),
        ("constitution", 1),
        ("intelligence", 0),
        ("wisdom", 0),
        ("charisma", 2),
    )
    assert set(definition.feats) == {
        "Natural Skill",
        "Assurance (Athletics)",
        "Intimidating Glare",
        "Flying Blade",
    }
    assert set(definition.proficiencies) == {
        ("perception", "expert"),
        ("fortitude", "trained"),
        ("reflex", "expert"),
        ("will", "expert"),
        ("simple_weapons", "trained"),
        ("martial_weapons", "trained"),
        ("unarmed_attacks", "trained"),
        ("unarmored_defense", "trained"),
        ("light_armor", "trained"),
        ("class_dc", "trained"),
    }
    assert dict((name, modifier) for name, _rank, modifier in definition.skills) == {
        "acrobatics": 7,
        "athletics": 5,
        "deception": 5,
        "diplomacy": 5,
        "intimidation": 5,
        "nature": 3,
        "stealth": 7,
        "survival": 3,
        "thievery": 7,
        "warfare_lore": 3,
    }
    assert definition.saves == (
        ("fortitude", "trained", 4),
        ("reflex", "expert", 9),
        ("will", "expert", 5),
    )


def test_saved_reactive_strike_then_near_throw_keeps_identity_damage_and_recovery(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    base = content.get_setup(SETUP_ID)
    setup = EncounterSetup(
        "review_flying_blade_reaction",
        "Review Flying Blade and Reactive Strike",
        4,
        3,
        (
            CreaturePlacement("braggart", base.placements[0].definition_id, "Braggart", "blue", Position(1, 1)),
            CreaturePlacement("reactor", content.MELEE_FIGHTER_M.definition_id, "Reactive Fighter", "red", Position(2, 1)),
        ),
    )
    _admit(monkeypatch, setup)
    game = Encounter.start(setup, rolls=(20, 1, 11, 2))
    _settle_initiative(game)

    started = game.execute(Strike("reactor", "dagger_thrown", item_id="braggart:dagger_1"))
    reaction = started.inspection.choice
    assert started.status is ResultStatus.PAUSED
    assert reaction is not None and reaction.kind == "reaction"
    assert reaction.owner_actor_id == "reactor"
    assert _actor(game, "braggart").held_items == ("braggart:dagger_1",)

    reaction_path = tmp_path / "flying-blade-reaction.json"
    game.save(reaction_path)
    game = Encounter.load(reaction_path)
    assert game.inspect().choice == reaction
    declined = _choose(game, "decline")
    attack_choice = declined.inspection.choice
    assert declined.status is ResultStatus.PAUSED
    assert attack_choice is not None and attack_choice.kind == "attack_hero_reroll"

    attack_path = tmp_path / "flying-blade-attack.json"
    game.save(attack_path)
    game = Encounter.load(attack_path)
    result = _choose(game, "keep")
    check = next(event.check for event in result.events if event.kind == "strike")
    damage = next(event.damage for event in result.events if event.damage is not None)
    assert check is not None and (check.die, check.modifier, check.total) == (11, 7, 18)
    assert damage is not None and damage.total == 6
    assert [(part.source, part.amount) for part in damage.components] == [
        ("dagger_thrown", 4),
        ("swashbuckler_precise_strike", 2),
    ]
    assert _actor(game, "braggart").held_items == ()
    assert game.inspect().ground_items == ((Position(2, 1), ("braggart:dagger_1",)),)

    retrieve = game.execute(Interact("retrieve", "braggart:dagger_1"))
    assert retrieve.status is ResultStatus.PAUSED
    assert retrieve.inspection.choice is not None and retrieve.inspection.choice.kind == "reaction"
    assert _choose(game, "decline").status is ResultStatus.COMPLETED
    assert _actor(game, "braggart").held_items == ("braggart:dagger_1",)
    assert game.inspect().ground_items == ()


def test_near_thrown_finisher_failure_deals_only_half_precision_and_lands_item(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    base = content.get_setup(SETUP_ID)
    setup = EncounterSetup(
        "review_flying_blade_failed_finisher",
        "Review failed Flying Blade finisher",
        5,
        3,
        (
            CreaturePlacement("braggart", base.placements[0].definition_id, "Braggart", "blue", Position(1, 1)),
            CreaturePlacement("braggart_dog", base.placements[1].definition_id, "Guard Dog", "red", Position(3, 1)),
        ),
    )
    _admit(monkeypatch, setup)
    game = Encounter.start(setup, rolls=(20, 1, 8, 2, 3, 4))
    _settle_initiative(game)

    assert game.execute(Demoralize("braggart_dog", use_intimidating_glare=True)).status is ResultStatus.PAUSED
    assert _choose(game, "keep").status is ResultStatus.COMPLETED
    assert _actor(game, "braggart").panache

    started = game.execute(
        ConfidentFinisher("braggart_dog", "dagger_thrown", item_id="braggart:dagger_1")
    )
    assert started.status is ResultStatus.PAUSED
    result = _choose(game, "keep")
    check = next(event.check for event in result.events if event.kind == "strike")
    failure = next(event.damage for event in result.events if event.kind == "confident_finisher_failure")
    assert check is not None and check.degree.name == "FAILURE"
    assert failure is not None and failure.total == 3
    assert [(part.source, part.damage_type, part.rolls, part.amount) for part in failure.components] == [
        ("confident_finisher_failure", "piercing", (3, 4), 3)
    ]
    assert _actor(game, "braggart_dog").hp == 5
    assert not _actor(game, "braggart").panache
    assert _actor(game, "braggart").held_items == ()
    assert game.inspect().ground_items == ((Position(3, 1), ("braggart:dagger_1",)),)
