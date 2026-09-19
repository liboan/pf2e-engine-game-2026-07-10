"""Independent source review for the selected level-1 Bomber.

Sources checked for this combat checkpoint:

* Quick Bomber: https://2e.aonprd.com/Feats.aspx?ID=5764
* Bomb and splash rules: https://2e.aonprd.com/Rules.aspx?ID=3135
* Bomber field benefit: https://2e.aonprd.com/ResearchFields.aspx?ID=5
* Bottled Lightning: https://2e.aonprd.com/Equipment.aspx?ID=3290
* Frost Vial: https://2e.aonprd.com/Equipment.aspx?ID=3293
* Quick Alchemy: https://2e.aonprd.com/Actions.aspx?ID=2801
* Minor Elixir of Life: https://2e.aonprd.com/Equipment.aspx?ID=3308
* Antidote and Antiplague: https://2e.aonprd.com/Equipment.aspx?ID=3296
  and https://2e.aonprd.com/Equipment.aspx?ID=3297
* Bestial and Cognitive Mutagens: https://2e.aonprd.com/Equipment.aspx?ID=3315
  and https://2e.aonprd.com/Equipment.aspx?ID=3316
* Mutagen trait: https://2e.aonprd.com/Traits.aspx?ID=808
* Giant Centipede Venom: https://2e.aonprd.com/Equipment.aspx?ID=3334
* Injury trait: https://2e.aonprd.com/Traits.aspx?ID=635

The splash rules require primary splash on failure, success, and critical
success; combine a primary target's initial and same-type splash damage before
its defenses; leave splash undoubled on a critical hit; and affect nearby
creatures only on a success or critical success.  Bomber can instead restrict
that throw's splash to the primary target.

The two lesser mutagens last one minute.  Bestial grants a +1 item bonus to
Athletics and unarmed attacks, creates agile d4 claws and d6 jaws, and applies
its printed skill/save drawbacks.  Cognitive grants its knowledge bonuses and
critical-failure adjustment while applying its attack/skill and Bulk
drawbacks.  Replacing an active mutagen requires the printed counteract check.
"""

from copy import deepcopy
from dataclasses import replace
from pathlib import Path
from types import MappingProxyType

import pytest

import pf2e.content as content
from pf2e.checks import DegreeOfSuccess
from pf2e.encounter import Encounter
from pf2e.investigator import RecallKnowledge
from pf2e.investigator_content import GUARD_DOG_KNOWLEDGE
from pf2e.model import (
    ActivateAlchemy,
    Choose,
    CreaturePlacement,
    DamageDefense,
    EndTurn,
    EncounterSetup,
    Interact,
    Position,
    QuickAlchemy,
    QuickBomber,
    ResultStatus,
    Strike,
    Stride,
)
from pf2e.skill_actions import Trip
from terminal_test_helpers import BoundedInput, BoundedTranscript


def test_selected_bomber_sheet_has_source_legal_statistics_and_grants() -> None:
    definition = content.get_definition("bomber_alchemist_level_1_staged")

    assert content.CREATURES[definition.definition_id] == definition
    assert content.SETUPS["staged_bomber_alchemist_vs_guard_dog"] == content.get_setup(
        "staged_bomber_alchemist_vs_guard_dog"
    )
    assert "staged_bomber_alchemist_next_vs_guard_dog" not in content.SETUPS

    assert (
        definition.ancestry,
        definition.heritage,
        definition.background,
        definition.class_name,
    ) == ("Human", "Versatile Human", "Scholar", "Alchemist")
    assert dict(definition.ability_modifiers) == {
        "strength": 0,
        "dexterity": 3,
        "constitution": 1,
        "intelligence": 4,
        "wisdom": 1,
        "charisma": 0,
    }
    assert (definition.hp, definition.ac, definition.land_speed_ft) == (17, 17, 30)
    assert dict((save, modifier) for save, _rank, modifier in definition.saves) == {
        "fortitude": 6,
        "reflex": 8,
        "will": 4,
    }
    assert definition.class_dc == 17
    assert {"bombs", "medium_armor"} <= {
        proficiency for proficiency, _rank in definition.proficiencies
    }
    assert {
        "Quick Bomber", "Fleet", "Natural Skill", "Assurance (Nature)",
        "Alchemical Crafting",
    } <= set(definition.feats)
    attacks = {attack.attack_id: attack for attack in definition.attacks}
    assert attacks["dagger"].modifier == 6
    assert attacks["dagger"].damage_modifier == 0
    for bomb_id in ("bottled_lightning", "frost_vial"):
        bomb = attacks[bomb_id]
        assert (bomb.modifier, bomb.damage_modifier, bomb.range_increment_ft) == (6, 0, 20)
        assert bomb.striking_applies is False


def _settle_initial(game: Encounter) -> None:
    while game.inspect().choice is not None:
        choice = game.inspect().choice
        assert choice is not None
        result = game.execute(Choose(choice.choice_id, "keep", choice.owner_actor_id))
        assert result.status in {ResultStatus.COMPLETED, ResultStatus.PAUSED}


def _throw_and_keep(game: Encounter, command: QuickBomber):
    result = game.execute(command)
    if result.status is ResultStatus.PAUSED:
        choice = game.inspect().choice
        assert choice is not None and choice.kind == "attack_hero_reroll"
        result = game.execute(Choose(choice.choice_id, "keep", choice.owner_actor_id))
    assert result.status is ResultStatus.COMPLETED
    return result


def _keep_pending_check(game: Encounter, result):
    if result.status is ResultStatus.PAUSED:
        choice = game.inspect().choice
        assert choice is not None
        result = game.execute(Choose(choice.choice_id, "keep", choice.owner_actor_id))
    assert result.status is ResultStatus.COMPLETED
    return result


def _activate_prepared_formula(game: Encounter, formula_id: str):
    item_id = next(
        item.instance_id for item in game._state.infused_alchemy_items.values()
        if item.formula_id == formula_id
        and item.instance_id in game._state.creatures["alchemist"].stowed_items
    )
    assert game.execute(Interact("draw", item_id)).status is ResultStatus.COMPLETED
    result = game.execute(ActivateAlchemy(item_id, "alchemist"))
    assert result.status is ResultStatus.COMPLETED
    return item_id, result


def _install_review_setup(monkeypatch, *, setup_id: str, placements, definitions=()) -> EncounterSetup:
    for definition in definitions:
        monkeypatch.setattr(
            content,
            "_STAGED_CREATURES",
            MappingProxyType({**content._STAGED_CREATURES, definition.definition_id: definition}),
        )
    setup = EncounterSetup(setup_id, setup_id, 7, 5, tuple(placements))
    monkeypatch.setattr(
        content,
        "_STAGED_SETUPS",
        MappingProxyType({**content._STAGED_SETUPS, setup.setup_id: setup}),
    )
    return setup


def test_failed_bomb_strike_still_deals_primary_splash_and_consumes_bomb() -> None:
    game = Encounter.start(
        content.get_setup("staged_bomber_alchemist_vs_guard_dog"),
        rolls=(20, 1, 2),
    )
    _settle_initial(game)

    result = _throw_and_keep(game, QuickBomber("dog", "frost_vial_lesser"))

    strike = next(event for event in result.events if event.kind == "strike")
    assert strike.check is not None and strike.check.degree.label() == "Failure"
    assert game._state.creatures["dog"].hp == 7
    assert any(event.kind == "bomb_consumed" for event in result.events)
    assert not any(effect.kind == "speed_penalty" for effect in game._state.condition_effects)


def test_primary_initial_and_same_type_splash_share_one_defense_application(monkeypatch) -> None:
    resistant = replace(
        content.get_definition("guard_dog_mc2924"),
        definition_id="review_electricity_resistant_guard_dog",
        name="Electricity-resistant Guard Dog",
        damage_defenses=(DamageDefense(
            "resistance", "electricity", 1, source="review electricity resistance",
        ),),
    )
    setup = _install_review_setup(
        monkeypatch,
        setup_id="review_bomber_combined_primary_damage",
        definitions=(resistant,),
        placements=(
            CreaturePlacement(
                "alchemist", "bomber_alchemist_level_1_staged", "Bomber Alchemist",
                "blue", Position(1, 2),
            ),
            CreaturePlacement(
                "dog", resistant.definition_id, "Resistant Dog", "red", Position(4, 2),
            ),
        ),
    )
    game = Encounter.start(setup, rolls=(20, 1, 10, 4))
    _settle_initial(game)

    _throw_and_keep(game, QuickBomber("dog", "bottled_lightning_lesser"))

    # (1d6 result 4 + splash 1) - resistance 1 = 4 damage.
    assert game._state.creatures["dog"].hp == 4


def test_bomber_splash_restriction_is_per_throw_and_suppresses_area_splash(monkeypatch) -> None:
    setup = _install_review_setup(
        monkeypatch,
        setup_id="review_bomber_adjacent_splash",
        placements=(
            CreaturePlacement(
                "alchemist", "bomber_alchemist_level_1_staged", "Bomber Alchemist",
                "blue", Position(1, 2),
            ),
            CreaturePlacement(
                "primary", "guard_dog_mc2924", "Primary Dog", "red", Position(4, 2),
            ),
            CreaturePlacement(
                "nearby", "guard_dog_mc2924", "Nearby Dog", "red", Position(4, 3),
            ),
        ),
    )

    normal = Encounter.start(setup, rolls=(20, 1, 2, 10, 1))
    _settle_initial(normal)
    _throw_and_keep(normal, QuickBomber(
        "primary", "bottled_lightning_lesser", only_primary_splash=False,
    ))
    assert normal._state.creatures["primary"].hp == 6
    assert normal._state.creatures["nearby"].hp == 7

    restricted = Encounter.start(setup, rolls=(20, 1, 2, 10, 1))
    _settle_initial(restricted)
    _throw_and_keep(restricted, QuickBomber(
        "primary", "bottled_lightning_lesser", only_primary_splash=True,
    ))
    assert restricted._state.creatures["primary"].hp == 6
    assert restricted._state.creatures["nearby"].hp == 8


def test_critical_bomb_doubles_initial_but_not_primary_or_area_splash(monkeypatch) -> None:
    setup = _install_review_setup(
        monkeypatch,
        setup_id="review_bomber_critical_splash",
        placements=(
            CreaturePlacement(
                "alchemist", "bomber_alchemist_level_1_staged", "Bomber Alchemist",
                "blue", Position(1, 2),
            ),
            CreaturePlacement(
                "primary", "guard_dog_mc2924", "Primary Dog", "red", Position(4, 2),
            ),
            CreaturePlacement(
                "nearby", "guard_dog_mc2924", "Nearby Dog", "red", Position(4, 3),
            ),
        ),
    )
    game = Encounter.start(setup, rolls=(20, 1, 2, 20, 3))
    _settle_initial(game)

    result = _throw_and_keep(game, QuickBomber(
        "primary", "frost_vial_lesser", only_primary_splash=False,
    ))

    strike = next(event for event in result.events if event.kind == "strike")
    assert strike.check is not None and strike.check.degree.label() == "Critical Success"
    assert game._state.creatures["primary"].hp == 1  # 2*3 cold + 1 splash
    assert game._state.creatures["nearby"].hp == 7   # unchanged splash


def test_two_quick_bombs_cost_one_action_each_and_use_normal_map() -> None:
    game = Encounter.start(
        content.get_setup("staged_bomber_alchemist_vs_guard_dog"),
        rolls=(20, 1, 2, 15, 1),
    )
    _settle_initial(game)

    first = _throw_and_keep(game, QuickBomber("dog", "frost_vial_lesser"))
    second = _throw_and_keep(game, QuickBomber("dog", "bottled_lightning_lesser"))

    first_check = next(event.check for event in first.events if event.kind == "strike")
    second_check = next(event.check for event in second.events if event.kind == "strike")
    assert first_check is not None and first_check.map_penalty == 0
    assert second_check is not None and second_check.map_penalty == -5
    actor = game._state.creatures["alchemist"]
    assert (actor.actions_remaining, actor.strikes_this_turn) == (1, 2)


def test_bomb_hit_riders_use_their_distinct_source_expiration_boundaries() -> None:
    lightning = Encounter.start(
        content.get_setup("staged_bomber_alchemist_vs_guard_dog"),
        rolls=(20, 1, 10, 1),
    )
    _settle_initial(lightning)
    _throw_and_keep(lightning, QuickBomber("dog", "bottled_lightning_lesser"))
    assert any(effect.kind == "off_guard" for effect in lightning._state.condition_effects)
    assert lightning.execute(EndTurn()).status is ResultStatus.COMPLETED
    assert any(effect.kind == "off_guard" for effect in lightning._state.condition_effects)
    assert lightning.execute(EndTurn()).status is ResultStatus.COMPLETED
    assert not any(effect.kind == "off_guard" for effect in lightning._state.condition_effects)

    frost = Encounter.start(
        content.get_setup("staged_bomber_alchemist_vs_guard_dog"),
        rolls=(20, 1, 10, 1),
    )
    _settle_initial(frost)
    _throw_and_keep(frost, QuickBomber("dog", "frost_vial_lesser"))
    assert any(effect.kind == "speed_penalty" for effect in frost._state.condition_effects)
    assert frost.execute(EndTurn()).status is ResultStatus.COMPLETED
    assert any(effect.kind == "speed_penalty" for effect in frost._state.condition_effects)
    assert frost.execute(EndTurn()).status is ResultStatus.COMPLETED
    assert not any(effect.kind == "speed_penalty" for effect in frost._state.condition_effects)


def test_quick_bomber_commits_one_action_before_ranged_reaction_then_normal_map(monkeypatch) -> None:
    setup = _install_review_setup(
        monkeypatch,
        setup_id="review_bomber_ranged_reaction",
        placements=(
            CreaturePlacement(
                "alchemist", "bomber_alchemist_level_1_staged", "Bomber Alchemist",
                "blue", Position(1, 2),
            ),
            CreaturePlacement(
                "reactor", "fighter_m_level_1", "Reactive Fighter", "red", Position(2, 2),
            ),
            CreaturePlacement(
                "dog", "guard_dog_mc2924", "Guard Dog", "red", Position(4, 2),
            ),
        ),
    )
    game = Encounter.start(setup, rolls=(20, 2, 1, 10, 1))
    _settle_initial(game)

    started = game.execute(QuickBomber("dog", "bottled_lightning_lesser"))

    assert started.status is ResultStatus.PAUSED
    choice = game.inspect().choice
    assert choice is not None and choice.kind == "reaction"
    actor = game._state.creatures["alchemist"]
    assert (actor.actions_remaining, actor.strikes_this_turn) == (2, 0)
    assert "alchemist:bottled_lightning_lesser" in actor.held_items

    declined = game.execute(Choose(choice.choice_id, "decline", choice.owner_actor_id))
    assert declined.status is ResultStatus.PAUSED
    attack_choice = game.inspect().choice
    assert attack_choice is not None and attack_choice.kind == "attack_hero_reroll"
    completed = game.execute(Choose(
        attack_choice.choice_id, "keep", attack_choice.owner_actor_id,
    ))
    assert completed.status is ResultStatus.COMPLETED
    assert game._state.creatures["alchemist"].strikes_this_turn == 1
    assert game._state.creatures["reactor"].reaction_available is True
    assert (
        "alchemist:bottled_lightning_lesser"
        not in game._state.creatures["alchemist"].held_items
    )


def test_saved_attack_choice_preserves_this_throws_primary_only_scope(
    monkeypatch, tmp_path: Path,
) -> None:
    setup = _install_review_setup(
        monkeypatch,
        setup_id="review_bomber_saved_primary_only",
        placements=(
            CreaturePlacement(
                "alchemist", "bomber_alchemist_level_1_staged", "Bomber Alchemist",
                "blue", Position(1, 2),
            ),
            CreaturePlacement(
                "primary", "guard_dog_mc2924", "Primary Dog", "red", Position(4, 2),
            ),
            CreaturePlacement(
                "nearby", "guard_dog_mc2924", "Nearby Dog", "red", Position(4, 3),
            ),
        ),
    )
    game = Encounter.start(setup, rolls=(20, 1, 2, 10, 2))
    _settle_initial(game)
    paused = game.execute(QuickBomber(
        "primary", "frost_vial_lesser", only_primary_splash=True,
    ))
    assert paused.status is ResultStatus.PAUSED
    choice = game.inspect().choice
    assert choice is not None and choice.kind == "attack_hero_reroll"

    path = tmp_path / "saved-primary-only-bomb.json"
    game.save(path)
    loaded = Encounter.load(path)
    resumed = loaded.execute(Choose(choice.choice_id, "keep", choice.owner_actor_id))

    assert resumed.status is ResultStatus.COMPLETED
    assert loaded._state.creatures["primary"].hp == 5
    assert loaded._state.creatures["nearby"].hp == 8


def test_quick_created_bomb_round_trips_then_uses_the_recorded_vial_once(
    tmp_path: Path,
) -> None:
    game = Encounter.start(
        content.get_setup("staged_bomber_alchemist_vs_guard_dog"),
        rolls=(20, 1, 2, 15, 2),
    )
    _settle_initial(game)
    _throw_and_keep(game, QuickBomber("dog", "bottled_lightning_lesser"))

    created = game.execute(QuickAlchemy(
        "create_consumable", "bottled_lightning_lesser",
    ))
    assert created.status is ResultStatus.COMPLETED
    state = game._state
    assert state.alchemy_states["alchemist"].stored_vials == 5
    assert state.creatures["alchemist"].actions_remaining == 1
    quick_ids = tuple(
        item_id for item_id in state.creatures["alchemist"].held_items
        if ":quick:" in item_id
    )
    assert len(quick_ids) == 1
    quick_id = quick_ids[0]
    record = state.infused_alchemy_items[quick_id]
    assert (
        record.creator_actor_id,
        record.creation_kind,
        record.activation_deadline,
    ) == ("alchemist", "quick_alchemy", "creator_next_turn_start")

    path = tmp_path / "review-quick-created-bomb.json"
    game.save(path)
    loaded = Encounter.load(path)
    assert loaded._state.alchemy_states["alchemist"].stored_vials == 5
    assert loaded._state.infused_alchemy_items[quick_id] == record

    result = _throw_and_keep(loaded, QuickBomber(
        "dog", "bottled_lightning_lesser",
    ))
    assert any(event.kind == "bomb_consumed" for event in result.events)
    assert quick_id in loaded._state.consumed_infused_item_ids
    assert quick_id not in loaded._state.creatures["alchemist"].held_items
    assert loaded._state.alchemy_states["alchemist"].stored_vials == 5


def test_quick_alchemy_requires_known_formula_toolkit_and_free_hand_atomically() -> None:
    def fresh() -> Encounter:
        game = Encounter.start(
            content.get_setup("staged_bomber_alchemist_vs_guard_dog"),
            rolls=(20, 1),
        )
        _settle_initial(game)
        return game

    unknown = fresh()
    before = deepcopy(unknown._state)
    rejected = unknown.execute(QuickAlchemy(
        "create_consumable", "alchemists_fire_lesser",
    ))
    assert rejected.status is ResultStatus.REJECTED
    assert unknown._state == before

    no_toolkit = fresh()
    no_toolkit._state.creatures["alchemist"].worn_items.remove("alchemists_toolkit")
    before = deepcopy(no_toolkit._state)
    rejected = no_toolkit.execute(QuickAlchemy(
        "create_consumable", "frost_vial_lesser",
    ))
    assert rejected.status is ResultStatus.REJECTED
    assert no_toolkit._state == before

    hands_full = fresh()
    actor = hands_full._state.creatures["alchemist"]
    actor.stowed_items.remove("alchemist:frost_vial_lesser")
    actor.held_items.append("alchemist:frost_vial_lesser")
    before = deepcopy(hands_full._state)
    rejected = hands_full.execute(QuickAlchemy(
        "create_consumable", "frost_vial_lesser",
    ))
    assert rejected.status is ResultStatus.REJECTED
    assert hands_full._state == before


def _win_after_spending_one_vial(*, transfer_old_bottled: bool = False) -> Encounter:
    game = Encounter.start(
        content.get_setup("staged_bomber_alchemist_vs_guard_dog"),
        rolls=(20, 1, 10, 6, 10, 1),
    )
    _settle_initial(game)
    if transfer_old_bottled:
        actor = game._state.creatures["alchemist"]
        actor.stowed_items.remove("alchemist:bottled_lightning_lesser")
        game._state.creatures["dog"].stowed_items.append(
            "alchemist:bottled_lightning_lesser"
        )
    assert game.execute(QuickAlchemy(
        "create_consumable", "bottled_lightning_lesser",
    )).status is ResultStatus.COMPLETED
    _throw_and_keep(game, QuickBomber("dog", "bottled_lightning_lesser"))
    _throw_and_keep(game, QuickBomber("dog", "frost_vial_lesser"))
    assert game.inspect().winner_team == "blue"
    assert game._state.alchemy_states["alchemist"].stored_vials == 5
    return game


def test_vial_recovery_accumulates_exact_exploration_time_and_caps(
    tmp_path: Path,
) -> None:
    game = _win_after_spending_one_vial()

    partial = game.recover_versatile_vials("alchemist", elapsed_seconds=599)
    assert partial.status is ResultStatus.COMPLETED
    alchemy = game._state.alchemy_states["alchemist"]
    assert (alchemy.stored_vials, alchemy.exploration_seconds_toward_vial_recovery) == (5, 599)
    path = tmp_path / "review-partial-vial-recovery.json"
    game.save(path)
    game = Encounter.load(path)

    completed = game.recover_versatile_vials("alchemist", elapsed_seconds=1)
    assert completed.status is ResultStatus.COMPLETED
    alchemy = game._state.alchemy_states["alchemist"]
    assert (alchemy.stored_vials, alchemy.exploration_seconds_toward_vial_recovery) == (6, 0)
    capped = game.recover_versatile_vials("alchemist", elapsed_seconds=600)
    assert capped.status is ResultStatus.COMPLETED
    alchemy = game._state.alchemy_states["alchemist"]
    assert (alchemy.stored_vials, alchemy.exploration_seconds_toward_vial_recovery) == (6, 0)
    assert game._state.world_time_seconds == 1200


def test_daily_preparation_expires_transferred_creator_stock_and_prepares_eight(
    tmp_path: Path,
) -> None:
    game = _win_after_spending_one_vial(transfer_old_bottled=True)
    old_id = "alchemist:bottled_lightning_lesser"
    assert old_id in game._state.creatures["dog"].stowed_items

    rested = game.record_rested(
        ("alchemist",), day_number=2, elapsed_seconds=8 * 60 * 60,
    )
    assert rested.status is ResultStatus.COMPLETED
    prepared = game.daily_prepare(("alchemist",), {"alchemist": {}})
    assert prepared.status is ResultStatus.COMPLETED

    assert all(
        old_id not in inventory
        for actor in game._state.creatures.values()
        for inventory in (actor.held_items, actor.worn_items, actor.stowed_items)
    )
    assert old_id in game._state.consumed_infused_item_ids
    alchemy = game._state.alchemy_states["alchemist"]
    assert (alchemy.daily_preparation_id, alchemy.stored_vials) == ("day:2", 6)
    day_two = tuple(
        item for item in game._state.infused_alchemy_items.values()
        if item.creator_actor_id == "alchemist" and item.daily_preparation_id == "day:2"
    )
    assert len(day_two) == 8
    assert {item.formula_id for item in day_two} == set(alchemy.known_formula_ids)

    path = tmp_path / "review-day-two-transferred-cleanup.json"
    game.save(path)
    loaded = Encounter.load(path)
    assert loaded._state.alchemy_states["alchemist"] == alchemy
    assert old_id in loaded._state.consumed_infused_item_ids


def test_unused_quick_created_bomb_expires_at_creator_next_turn_start(
    tmp_path: Path,
) -> None:
    game = Encounter.start(
        content.get_setup("staged_bomber_alchemist_vs_guard_dog"),
        rolls=(20, 1),
    )
    _settle_initial(game)
    created = game.execute(QuickAlchemy(
        "create_consumable", "frost_vial_lesser",
    ))
    assert created.status is ResultStatus.COMPLETED
    quick_id = next(
        item_id for item_id in game._state.creatures["alchemist"].held_items
        if ":quick:" in item_id
    )

    assert game.execute(EndTurn()).status is ResultStatus.COMPLETED
    assert game.execute(EndTurn()).status is ResultStatus.COMPLETED

    assert quick_id not in game._state.creatures["alchemist"].held_items
    assert game._state.alchemy_states["alchemist"].stored_vials == 5
    rejected = game.execute(QuickBomber("dog", "frost_vial_lesser"))
    assert rejected.status is ResultStatus.REJECTED

    path = tmp_path / "review-expired-quick-bomb.json"
    game.save(path)
    loaded = Encounter.load(path)
    assert quick_id not in loaded._state.creatures["alchemist"].held_items
    assert loaded._state.alchemy_states["alchemist"].stored_vials == 5


def test_minor_elixir_heals_and_grants_its_ten_minute_recipient_save_bonus(
    tmp_path: Path,
) -> None:
    game = Encounter.start(
        content.get_setup("staged_bomber_alchemist_vs_guard_dog"),
        rolls=(20, 1, 4),
    )
    _settle_initial(game)
    actor = game._state.creatures["alchemist"]
    actor.hp = 10
    assert game.execute(QuickAlchemy(
        "create_consumable", "elixir_of_life_minor",
    )).status is ResultStatus.COMPLETED
    actor = game._state.creatures["alchemist"]
    item_id = next(item for item in actor.held_items if ":quick:" in item)

    result = game.execute(ActivateAlchemy(item_id, "alchemist"))

    assert result.status is ResultStatus.COMPLETED
    actor = game._state.creatures["alchemist"]
    assert actor.hp == 14
    assert item_id in game._state.consumed_infused_item_ids
    assert item_id not in actor.held_items
    bonus = next(
        effect for effect in game._state.active_effects
        if effect.kind == "alchemy_elixir_of_life_minor"
        and effect.target_actor_id == "alchemist"
    )
    assert (bonus.value, bonus.expires_at_world_time) == (1, 600)

    path = tmp_path / "review-minor-elixir.json"
    game.save(path)
    loaded = Encounter.load(path)
    assert any(effect == bonus for effect in loaded._state.active_effects)


def test_elixir_cannot_be_forced_on_an_active_hostile_recipient(monkeypatch) -> None:
    setup = _install_review_setup(
        monkeypatch,
        setup_id="review_bomber_hostile_elixir_recipient",
        placements=(
            CreaturePlacement(
                "alchemist", "bomber_alchemist_level_1_staged", "Bomber Alchemist",
                "blue", Position(1, 2),
            ),
            CreaturePlacement(
                "dog", "guard_dog_mc2924", "Guard Dog", "red", Position(2, 2),
            ),
        ),
    )
    game = Encounter.start(setup, rolls=(20, 1, 4))
    _settle_initial(game)
    assert game.execute(QuickAlchemy(
        "create_consumable", "elixir_of_life_minor",
    )).status is ResultStatus.COMPLETED
    item_id = next(
        item for item in game._state.creatures["alchemist"].held_items
        if ":quick:" in item
    )
    before = deepcopy(game._state)

    result = game.execute(ActivateAlchemy(item_id, "dog"))

    assert result.status is ResultStatus.REJECTED
    assert game._state == before


def test_minor_elixir_can_be_fed_to_adjacent_willing_ally(monkeypatch) -> None:
    setup = _install_review_setup(
        monkeypatch,
        setup_id="review_bomber_ally_elixir_recipient",
        placements=(
            CreaturePlacement(
                "alchemist", "bomber_alchemist_level_1_staged", "Bomber Alchemist",
                "blue", Position(1, 2),
            ),
            CreaturePlacement(
                "ally", "fighter_m_level_1", "Willing Fighter", "blue", Position(2, 2),
            ),
            CreaturePlacement(
                "dog", "guard_dog_mc2924", "Guard Dog", "red", Position(4, 2),
            ),
        ),
    )
    game = Encounter.start(setup, rolls=(20, 1, 1, 4))
    _settle_initial(game)
    game._state.creatures["ally"].hp -= 5
    assert game.execute(QuickAlchemy(
        "create_consumable", "elixir_of_life_minor",
    )).status is ResultStatus.COMPLETED
    item_id = next(
        item for item in game._state.creatures["alchemist"].held_items
        if ":quick:" in item
    )

    activated = game.execute(ActivateAlchemy(item_id, "ally"))

    assert activated.status is ResultStatus.COMPLETED
    assert game._state.creatures["ally"].hp == (
        content.get_definition("fighter_m_level_1").hp - 1
    )
    assert any(
        effect.kind == "alchemy_elixir_of_life_minor"
        and effect.target_actor_id == "ally"
        and effect.value == 1
        for effect in game._state.active_effects
    )


def _weak_dog_elixir_setup(monkeypatch, setup_id: str) -> EncounterSetup:
    weak_dog = replace(
        content.get_definition("guard_dog_mc2924"),
        definition_id=f"{setup_id}_dog",
        hp=1,
    )
    return _install_review_setup(
        monkeypatch,
        setup_id=setup_id,
        definitions=(weak_dog,),
        placements=(
            CreaturePlacement(
                "alchemist", "bomber_alchemist_level_1_staged", "Bomber Alchemist",
                "blue", Position(1, 2),
            ),
            CreaturePlacement(
                "dog", weak_dog.definition_id, "Weak Dog", "red", Position(4, 2),
            ),
        ),
    )


def test_quick_antidote_bonus_is_consumed_saved_and_capped_at_ten_minutes(
    monkeypatch, tmp_path: Path,
) -> None:
    setup = _weak_dog_elixir_setup(monkeypatch, "review_quick_antidote_expiry")
    game = Encounter.start(setup, rolls=(20, 1, 10, 1))
    _settle_initial(game)
    assert game.execute(QuickAlchemy(
        "create_consumable", "antidote_lesser",
    )).status is ResultStatus.COMPLETED
    item_id = next(
        item for item in game._state.creatures["alchemist"].held_items
        if ":quick:" in item
    )
    activated = game.execute(ActivateAlchemy(item_id, "alchemist"))
    assert activated.status is ResultStatus.COMPLETED
    bonus = next(
        effect for effect in game._state.active_effects
        if effect.kind == "alchemy_antidote_lesser"
    )
    assert (bonus.value, bonus.expires_at_world_time) == (2, 600)
    assert item_id in game._state.consumed_infused_item_ids

    _throw_and_keep(game, QuickBomber("dog", "frost_vial_lesser"))
    assert game.inspect().winner_team == "blue"
    path = tmp_path / "review-quick-antidote.json"
    game.save(path)
    game = Encounter.load(path)
    assert any(effect == bonus for effect in game._state.active_effects)
    assert game.recover_versatile_vials(
        "alchemist", elapsed_seconds=599,
    ).status is ResultStatus.COMPLETED
    assert any(effect.effect_id == bonus.effect_id for effect in game._state.active_effects)
    assert game.recover_versatile_vials(
        "alchemist", elapsed_seconds=1,
    ).status is ResultStatus.COMPLETED
    assert not any(effect.effect_id == bonus.effect_id for effect in game._state.active_effects)


def test_advanced_antiplague_keeps_its_ordinary_duration_past_ten_minutes(
    monkeypatch,
) -> None:
    setup = _weak_dog_elixir_setup(monkeypatch, "review_advanced_antiplague_expiry")
    game = Encounter.start(setup, rolls=(20, 1, 10, 1))
    _settle_initial(game)
    state = game._state
    item_id = next(
        item.instance_id for item in state.infused_alchemy_items.values()
        if item.formula_id == "antiplague_lesser"
    )
    assert game.execute(Interact("draw", item_id)).status is ResultStatus.COMPLETED
    activated = game.execute(ActivateAlchemy(item_id, "alchemist"))
    assert activated.status is ResultStatus.COMPLETED
    bonus = next(
        effect for effect in game._state.active_effects
        if effect.kind == "alchemy_antiplague_lesser"
    )
    assert (bonus.value, bonus.expires_at_world_time) == (2, 24 * 60 * 60)
    assert item_id in game._state.consumed_infused_item_ids

    _throw_and_keep(game, QuickBomber("dog", "frost_vial_lesser"))
    assert game.inspect().winner_team == "blue"
    assert game.recover_versatile_vials(
        "alchemist", elapsed_seconds=601,
    ).status is ResultStatus.COMPLETED
    assert any(effect.effect_id == bonus.effect_id for effect in game._state.active_effects)

    assert game.record_rested(
        ("alchemist",), day_number=2, elapsed_seconds=8 * 60 * 60,
    ).status is ResultStatus.COMPLETED
    assert game.daily_prepare(
        ("alchemist",), {"alchemist": {}},
    ).status is ResultStatus.COMPLETED
    assert not any(
        effect.effect_id == bonus.effect_id for effect in game._state.active_effects
    )


@pytest.mark.parametrize(
    ("counteract_die", "expected_kind", "expected_degree"),
    [
        (9, "alchemy_bestial_mutagen_lesser", DegreeOfSuccess.FAILURE),
        (10, "alchemy_cognitive_mutagen_lesser", DegreeOfSuccess.SUCCESS),
    ],
)
def test_second_mutagen_consumes_itself_and_uses_the_required_counteract_check(
    counteract_die: int, expected_kind: str, expected_degree: DegreeOfSuccess,
) -> None:
    game = Encounter.start(
        content.get_setup("staged_bomber_alchemist_vs_guard_dog"),
        rolls=(20, 1, counteract_die),
    )
    _settle_initial(game)
    _activate_prepared_formula(game, "bestial_mutagen_lesser")
    assert game.execute(EndTurn()).status is ResultStatus.COMPLETED
    assert game.execute(EndTurn()).status is ResultStatus.COMPLETED

    second_id, result = _activate_prepared_formula(
        game, "cognitive_mutagen_lesser",
    )

    check = next(event.check for event in result.events if event.kind == "alchemy_counteract")
    assert check is not None
    assert (check.die, check.modifier, check.dc, check.degree) == (
        counteract_die, 5, 15, expected_degree,
    )
    assert second_id in game._state.consumed_infused_item_ids
    mutagens = [
        effect.kind for effect in game._state.active_effects
        if effect.kind.startswith("alchemy_") and "mutagen" in effect.kind
    ]
    assert mutagens == [expected_kind]


def test_bestial_mutagen_applies_athletics_and_reflex_drawback_in_public_checks(
    monkeypatch,
) -> None:
    setup = _install_review_setup(
        monkeypatch,
        setup_id="review_bestial_mutagen_checks",
        placements=(
            CreaturePlacement(
                "alchemist", "bomber_alchemist_level_1_staged", "Bomber Alchemist",
                "blue", Position(1, 2),
            ),
            CreaturePlacement(
                "dog", "guard_dog_mc2924", "Guard Dog", "red", Position(2, 2),
            ),
        ),
    )
    game = Encounter.start(setup, rolls=(20, 1, 1, 10))
    _settle_initial(game)
    _activate_prepared_formula(game, "bestial_mutagen_lesser")

    alchemist_trip = _keep_pending_check(game, game.execute(Trip("dog")))
    alchemist_check = next(
        event.check for event in alchemist_trip.events if event.kind == "trip_check"
    )
    assert alchemist_check is not None and alchemist_check.modifier == 4
    assert any(
        modifier.source == "Bestial Mutagen" and modifier.amount == 1
        for modifier in alchemist_check.modifier_breakdown
    )
    assert game.inspect().turn_actor_id == "dog"

    dog_trip = game.execute(Trip("alchemist"))
    dog_check = next(event.check for event in dog_trip.events if event.kind == "trip_check")
    assert dog_check is not None and dog_check.dc == 16


def test_bestial_mutagen_grants_real_jaws_attack_with_printed_damage(
    monkeypatch, tmp_path: Path,
) -> None:
    setup = _install_review_setup(
        monkeypatch,
        setup_id="review_bestial_mutagen_jaws",
        placements=(
            CreaturePlacement(
                "alchemist", "bomber_alchemist_level_1_staged", "Bomber Alchemist",
                "blue", Position(1, 2),
            ),
            CreaturePlacement(
                "dog", "guard_dog_mc2924", "Guard Dog", "red", Position(2, 2),
            ),
        ),
    )
    game = Encounter.start(setup, rolls=(20, 1, 12, 4))
    _settle_initial(game)
    _activate_prepared_formula(game, "bestial_mutagen_lesser")

    paused = game.execute(Strike("dog", "bestial_jaws"))
    assert paused.status is ResultStatus.PAUSED
    choice = game.inspect().choice
    assert choice is not None and choice.kind == "attack_hero_reroll"
    path = tmp_path / "review-bestial-jaws-pending.json"
    game.save(path)
    game = Encounter.load(path)
    result = game.execute(Choose(choice.choice_id, "keep", choice.owner_actor_id))

    assert result.status is ResultStatus.COMPLETED
    strike = next(event for event in result.events if event.kind == "strike")
    assert strike.check is not None and strike.check.modifier == 4
    assert game._state.creatures["dog"].hp == 4


def test_bestial_claws_use_agile_map_and_their_printed_d4(monkeypatch) -> None:
    setup = _install_review_setup(
        monkeypatch,
        setup_id="review_bestial_mutagen_claws",
        placements=(
            CreaturePlacement(
                "alchemist", "bomber_alchemist_level_1_staged", "Bomber Alchemist",
                "blue", Position(1, 2),
            ),
            CreaturePlacement(
                "dog", "guard_dog_mc2924", "Guard Dog", "red", Position(2, 2),
            ),
        ),
    )
    game = Encounter.start(setup, rolls=(20, 1, 15, 1, 19, 2))
    _settle_initial(game)
    _activate_prepared_formula(game, "bestial_mutagen_lesser")
    assert game.execute(EndTurn()).status is ResultStatus.COMPLETED
    assert game.execute(EndTurn()).status is ResultStatus.COMPLETED

    jaws = _keep_pending_check(game, game.execute(Strike("dog", "bestial_jaws")))
    claws = _keep_pending_check(game, game.execute(Strike("dog", "bestial_claws")))

    jaws_check = next(event.check for event in jaws.events if event.kind == "strike")
    claws_check = next(event.check for event in claws.events if event.kind == "strike")
    assert jaws_check is not None and (jaws_check.modifier, jaws_check.map_penalty) == (4, 0)
    assert claws_check is not None and (claws_check.modifier, claws_check.map_penalty) == (0, -4)
    assert game._state.creatures["dog"].hp == 5


def test_cognitive_mutagen_penalizes_weapon_attack_and_upgrades_recall_critical_failure(
    monkeypatch,
) -> None:
    base = content.get_setup("staged_bomber_alchemist_vs_guard_dog")
    setup = replace(
        base,
        setup_id="review_cognitive_mutagen_knowledge",
        name="Review Cognitive Mutagen knowledge",
        knowledge=(GUARD_DOG_KNOWLEDGE,),
        placements=(
            base.placements[0],
            replace(base.placements[1], position=Position(2, 2)),
        ),
    )
    monkeypatch.setattr(
        content,
        "_STAGED_SETUPS",
        MappingProxyType({**content._STAGED_SETUPS, setup.setup_id: setup}),
    )

    knowledge_game = Encounter.start(setup, rolls=(20, 1, 1))
    _settle_initial(knowledge_game)
    _activate_prepared_formula(knowledge_game, "cognitive_mutagen_lesser")
    recalled = _keep_pending_check(
        knowledge_game,
        knowledge_game.execute(RecallKnowledge(
            "guard_dog", GUARD_DOG_KNOWLEDGE.question, "society", "dog",
        )),
    )
    knowledge_check = next(
        event.check for event in recalled.events if event.kind == "recall_knowledge"
    )
    assert knowledge_check is not None
    assert knowledge_check.modifier == 8
    assert knowledge_check.degree is DegreeOfSuccess.FAILURE
    assert any(
        modifier.source == "Cognitive Mutagen" and modifier.amount == 1
        for modifier in knowledge_check.modifier_breakdown
    )

    attack_game = Encounter.start(setup, rolls=(20, 1, 10))
    _settle_initial(attack_game)
    _activate_prepared_formula(attack_game, "cognitive_mutagen_lesser")
    attack = _keep_pending_check(
        attack_game, attack_game.execute(Strike("dog", "dagger")),
    )
    attack_check = next(event.check for event in attack.events if event.kind == "strike")
    assert attack_check is not None and attack_check.modifier == 4
    assert any(
        modifier.source == "Cognitive Mutagen drawback" and modifier.amount == -2
        for modifier in attack_check.modifier_breakdown
    )


def test_cognitive_mutagen_benefits_nature_when_it_is_used_to_recall_knowledge(
    monkeypatch,
) -> None:
    base = content.get_setup("staged_bomber_alchemist_vs_guard_dog")
    setup = replace(
        base,
        setup_id="review_cognitive_mutagen_nature_knowledge",
        name="Review Cognitive Mutagen Nature knowledge",
        knowledge=(GUARD_DOG_KNOWLEDGE,),
    )
    monkeypatch.setattr(
        content,
        "_STAGED_SETUPS",
        MappingProxyType({**content._STAGED_SETUPS, setup.setup_id: setup}),
    )
    game = Encounter.start(setup, rolls=(20, 1, 10))
    _settle_initial(game)
    _activate_prepared_formula(game, "cognitive_mutagen_lesser")

    result = _keep_pending_check(
        game,
        game.execute(RecallKnowledge(
            "guard_dog", GUARD_DOG_KNOWLEDGE.question, "nature", "dog",
        )),
    )

    check = next(event.check for event in result.events if event.kind == "recall_knowledge")
    assert check is not None and check.modifier == 5
    assert any(
        modifier.source == "Cognitive Mutagen" and modifier.amount == 1
        for modifier in check.modifier_breakdown
    )


def test_cognitive_mutagen_bulk_threshold_reduction_limits_stride(monkeypatch) -> None:
    burdened = replace(
        content.get_definition("bomber_alchemist_level_1_staged"),
        definition_id="review_burdened_bomber_alchemist",
        carried_item_bulk=(("dagger", 4),),
    )
    setup = _install_review_setup(
        monkeypatch,
        setup_id="review_cognitive_mutagen_bulk",
        definitions=(burdened,),
        placements=(
            CreaturePlacement(
                "alchemist", burdened.definition_id, "Burdened Bomber",
                "blue", Position(1, 2),
            ),
            CreaturePlacement(
                "dog", "guard_dog_mc2924", "Guard Dog", "red", Position(6, 4),
            ),
        ),
    )
    game = Encounter.start(setup, rolls=(20, 1))
    _settle_initial(game)
    _activate_prepared_formula(game, "cognitive_mutagen_lesser")
    before = deepcopy(game._state)

    result = game.execute(Stride((
        Position(1, 1), Position(2, 1), Position(3, 1), Position(4, 1), Position(5, 1),
    )))

    assert result.status is ResultStatus.REJECTED
    assert "20-foot limit" in result.message
    assert game._state == before


def test_lesser_mutagen_expires_at_one_minute_during_active_combat(
    monkeypatch,
) -> None:
    setup = _install_review_setup(
        monkeypatch,
        setup_id="review_bestial_mutagen_one_minute",
        placements=(
            CreaturePlacement(
                "alchemist", "bomber_alchemist_level_1_staged", "Bomber Alchemist",
                "blue", Position(1, 2),
            ),
            CreaturePlacement(
                "dog", "guard_dog_mc2924", "Guard Dog", "red", Position(2, 2),
            ),
        ),
    )
    game = Encounter.start(setup, rolls=(20, 1, 10))
    _settle_initial(game)
    _activate_prepared_formula(game, "bestial_mutagen_lesser")

    # A one-minute effect remains through 9 full rounds (54 seconds), then
    # ends when round 11 begins at the 60-second combat clock boundary.
    for _ in range(9):
        assert game.execute(EndTurn()).status is ResultStatus.COMPLETED
        assert game.execute(EndTurn()).status is ResultStatus.COMPLETED
    assert game._state.world_time_seconds == 54
    assert any(
        effect.kind == "alchemy_bestial_mutagen_lesser"
        for effect in game._state.active_effects
    )
    assert game.execute(EndTurn()).status is ResultStatus.COMPLETED
    assert game.execute(EndTurn()).status is ResultStatus.COMPLETED
    assert game._state.world_time_seconds == 60

    trip = _keep_pending_check(game, game.execute(Trip("dog")))
    check = next(event.check for event in trip.events if event.kind == "trip_check")
    assert check is not None and check.modifier == 3
    assert not any(
        effect.kind == "alchemy_bestial_mutagen_lesser"
        for effect in game._state.active_effects
    )


def test_coated_dagger_critical_failure_wastes_the_venom() -> None:
    game = Encounter.start(
        content.get_setup("staged_bomber_alchemist_vs_guard_dog"),
        rolls=(20, 1, 1),
    )
    _settle_initial(game)
    game._state.creatures["dog"].position = Position(2, 2)
    venom_id, _ = _activate_prepared_formula(game, "giant_centipede_venom")
    assert venom_id in game._state.consumed_infused_item_ids
    assert game.execute(EndTurn()).status is ResultStatus.COMPLETED

    strike = _keep_pending_check(game, game.execute(Strike("dog", "dagger")))

    check = next(event.check for event in strike.events if event.kind == "strike")
    assert check is not None and check.degree is DegreeOfSuccess.CRITICAL_FAILURE
    assert not any(
        effect.kind == "alchemy_giant_centipede_venom_coating"
        for effect in game._state.active_effects
    )


def test_failed_coated_dagger_strike_keeps_the_venom() -> None:
    game = Encounter.start(
        content.get_setup("staged_bomber_alchemist_vs_guard_dog"),
        rolls=(20, 1, 2),
    )
    _settle_initial(game)
    game._state.creatures["dog"].position = Position(2, 2)
    _activate_prepared_formula(game, "giant_centipede_venom")
    assert game.execute(EndTurn()).status is ResultStatus.COMPLETED

    strike = _keep_pending_check(game, game.execute(Strike("dog", "dagger")))

    check = next(event.check for event in strike.events if event.kind == "strike")
    assert check is not None and check.degree is DegreeOfSuccess.FAILURE
    assert any(
        effect.kind == "alchemy_giant_centipede_venom_coating"
        for effect in game._state.active_effects
    )


def test_unused_venom_coating_expires_after_six_rounds() -> None:
    game = Encounter.start(
        content.get_setup("staged_bomber_alchemist_vs_guard_dog"),
        rolls=(20, 1),
    )
    _settle_initial(game)
    _activate_prepared_formula(game, "giant_centipede_venom")

    while game._state.world_time_seconds < 30:
        assert game.execute(EndTurn()).status is ResultStatus.COMPLETED
    assert any(
        effect.kind == "alchemy_giant_centipede_venom_coating"
        for effect in game._state.active_effects
    )
    while game._state.world_time_seconds < 36:
        assert game.execute(EndTurn()).status is ResultStatus.COMPLETED
    assert not any(
        effect.kind == "alchemy_giant_centipede_venom_coating"
        for effect in game._state.active_effects
    )


def test_saved_coating_survives_to_the_next_turn_and_hit_exposes_target(
    tmp_path: Path,
) -> None:
    game = Encounter.start(
        content.get_setup("staged_bomber_alchemist_vs_guard_dog"),
        rolls=(20, 1, 20, 4, 1, 1),
    )
    _settle_initial(game)
    game._state.creatures["dog"].position = Position(2, 2)
    _activate_prepared_formula(game, "giant_centipede_venom")
    path = tmp_path / "review-saved-venom-coating.json"
    game.save(path)
    game = Encounter.load(path)
    assert any(
        effect.kind == "alchemy_giant_centipede_venom_coating"
        for effect in game._state.active_effects
    )
    assert game.execute(EndTurn()).status is ResultStatus.COMPLETED

    strike = _keep_pending_check(game, game.execute(Strike("dog", "dagger")))

    fortitude = next(
        event.check for event in strike.events
        if event.kind == "venom_fortitude_save"
    )
    assert fortitude is not None
    assert (fortitude.die, fortitude.dc, fortitude.degree) == (
        1, 17, DegreeOfSuccess.CRITICAL_FAILURE,
    )
    assert not any(
        effect.kind == "alchemy_giant_centipede_venom_coating"
        for effect in game._state.active_effects
    )
    assert not any(
        effect.spell_id == "giant_centipede_venom"
        for effect in game._state.persistent_effects
    )
    assert len(game._state.giant_centipede_venom_afflictions) == 1
    affliction = game._state.giant_centipede_venom_afflictions[0]
    assert (
        affliction.source_actor_id,
        affliction.target_actor_id,
        affliction.dc,
        affliction.stage,
        affliction.expires_at_world_time,
    ) == ("alchemist", "dog", 17, 2, game._state.world_time_seconds + 36)
    game.save(path)
    game = Encounter.load(path)
    assert game._state.giant_centipede_venom_afflictions == [affliction]


def test_stage_two_fatigue_applies_to_checks_then_clears_on_recovery(
    monkeypatch,
) -> None:
    durable_dog = replace(
        content.get_definition("guard_dog_mc2924"), hp=40,
    )
    monkeypatch.setattr(
        content,
        "_STAGED_CREATURES",
        MappingProxyType({
            **content._STAGED_CREATURES,
            durable_dog.definition_id: durable_dog,
        }),
    )
    game = Encounter.start(
        content.get_setup("staged_bomber_alchemist_vs_guard_dog"),
        rolls=(20, 1, 20, 1, 1, 1, 10, 20, 10),
    )
    _settle_initial(game)
    game._state.creatures["dog"].position = Position(2, 2)
    _activate_prepared_formula(game, "giant_centipede_venom")
    assert game.execute(EndTurn()).status is ResultStatus.COMPLETED

    strike = _keep_pending_check(game, game.execute(Strike("dog", "dagger")))
    initial_save = next(
        event.check for event in strike.events
        if event.kind == "venom_fortitude_save"
    )
    assert initial_save is not None
    assert initial_save.degree is DegreeOfSuccess.CRITICAL_FAILURE
    assert game._state.giant_centipede_venom_afflictions[0].stage == 2

    fatigued_trip = _keep_pending_check(game, game.execute(Trip("dog")))
    fatigued_check = next(
        event.check for event in fatigued_trip.events if event.kind == "trip_check"
    )
    assert fatigued_check is not None and fatigued_check.dc == 16
    assert game.execute(EndTurn()).status is ResultStatus.COMPLETED

    boundary = game.execute(EndTurn())
    boundary_save = next(
        event.check for event in boundary.events
        if event.kind == "venom_fortitude_save"
    )
    assert boundary_save is not None
    assert (boundary_save.modifier, boundary_save.degree) == (
        4, DegreeOfSuccess.CRITICAL_SUCCESS,
    )
    assert any(
        modifier.source.startswith("condition:fatigued:venom:")
        and modifier.amount == -1
        for modifier in boundary_save.modifier_breakdown
    )
    assert game._state.giant_centipede_venom_afflictions == []

    recovered_trip = _keep_pending_check(game, game.execute(Trip("dog")))
    recovered_check = next(
        event.check for event in recovered_trip.events if event.kind == "trip_check"
    )
    assert recovered_check is not None and recovered_check.dc == 17


def test_repeat_venom_exposure_advances_stage_without_resetting_deadline(
    monkeypatch, tmp_path: Path,
) -> None:
    durable_dog = replace(
        content.get_definition("guard_dog_mc2924"),
        definition_id="review_durable_venom_guard_dog",
        hp=100,
    )
    setup = _install_review_setup(
        monkeypatch,
        setup_id="review_repeat_venom_exposure",
        definitions=(durable_dog,),
        placements=(
            CreaturePlacement(
                "alchemist", "bomber_alchemist_level_1_staged", "Bomber Alchemist",
                "blue", Position(1, 2),
            ),
            CreaturePlacement(
                "dog", durable_dog.definition_id, "Durable Guard Dog",
                "red", Position(2, 2),
            ),
        ),
    )
    game = Encounter.start(
        setup,
        rolls=(20, 1, 10, 1, 7, 1, 7, 1, 10, 1, 7, 1),
    )
    _settle_initial(game)

    assert game.execute(QuickAlchemy(
        "create_consumable", "giant_centipede_venom",
    )).status is ResultStatus.COMPLETED
    quick_venom = next(
        item_id for item_id in game._state.creatures["alchemist"].held_items
        if item_id.startswith("alchemist:quick:")
    )
    assert game.execute(ActivateAlchemy(
        quick_venom, "alchemist",
    )).status is ResultStatus.COMPLETED
    assert game.execute(EndTurn()).status is ResultStatus.COMPLETED

    _keep_pending_check(game, game.execute(Strike("dog", "dagger")))
    first = game._state.giant_centipede_venom_afflictions[0]
    assert first.stage == 1
    prepared_venom = next(
        item.instance_id for item in game._state.infused_alchemy_items.values()
        if item.formula_id == "giant_centipede_venom"
        and item.instance_id in game._state.creatures["alchemist"].stowed_items
    )
    assert game.execute(Interact(
        "draw", prepared_venom,
    )).status is ResultStatus.COMPLETED
    assert game.execute(EndTurn()).status is ResultStatus.COMPLETED

    boundary = game.execute(EndTurn())
    assert boundary.status is ResultStatus.COMPLETED
    before_repeat = game._state.giant_centipede_venom_afflictions[0]
    assert before_repeat.stage == 2
    assert game.execute(ActivateAlchemy(
        prepared_venom, "alchemist",
    )).status is ResultStatus.COMPLETED
    repeated = _keep_pending_check(game, game.execute(Strike("dog", "dagger")))

    assert any(event.kind == "venom_stage_effect" for event in repeated.events)
    after_repeat = game._state.giant_centipede_venom_afflictions[0]
    assert after_repeat.stage == 3
    assert (
        after_repeat.effect_id,
        after_repeat.source_actor_id,
        after_repeat.expires_at_world_time,
        after_repeat.next_save_at_target_end,
    ) == (
        before_repeat.effect_id,
        before_repeat.source_actor_id,
        before_repeat.expires_at_world_time,
        before_repeat.next_save_at_target_end,
    )
    assert after_repeat.expires_at_world_time == first.expires_at_world_time
    path = tmp_path / "review-repeat-venom-exposure.json"
    game.save(path)
    assert Encounter.load(path)._state.giant_centipede_venom_afflictions == [
        after_repeat,
    ]


@pytest.mark.parametrize(
    ("formula_id", "rolls", "expected_modifier", "expected_bonus", "source"),
    [
        (
            "elixir_of_life_minor", (20, 1, 1, 12, 1, 7, 1),
            7, 1, "Minor Elixir of Life",
        ),
        (
            "antidote_lesser", (20, 1, 12, 1, 7, 1),
            8, 2, "Antidote (lesser)",
        ),
    ],
)
def test_alchemical_poison_save_bonus_applies_to_actual_venom_exposure(
    monkeypatch, formula_id: str, rolls: tuple[int, ...],
    expected_modifier: int, expected_bonus: int, source: str,
) -> None:
    setup = _install_review_setup(
        monkeypatch,
        setup_id=f"review_{formula_id}_venom_save",
        placements=(
            CreaturePlacement(
                "recipient", "bomber_alchemist_level_1_staged", "Elixir Recipient",
                "blue", Position(1, 2),
            ),
            CreaturePlacement(
                "poisoner", "bomber_alchemist_level_1_staged", "Venom Poisoner",
                "red", Position(2, 2),
            ),
        ),
    )
    game = Encounter.start(setup, rolls=rolls)
    _settle_initial(game)
    recipient_item = next(
        item.instance_id for item in game._state.infused_alchemy_items.values()
        if item.creator_actor_id == "recipient" and item.formula_id == formula_id
    )
    assert game.execute(Interact("draw", recipient_item)).status is ResultStatus.COMPLETED
    assert game.execute(ActivateAlchemy(
        recipient_item, "recipient",
    )).status is ResultStatus.COMPLETED
    assert game.execute(EndTurn()).status is ResultStatus.COMPLETED

    venom_item = next(
        item.instance_id for item in game._state.infused_alchemy_items.values()
        if item.creator_actor_id == "poisoner"
        and item.formula_id == "giant_centipede_venom"
    )
    assert game.execute(Interact("draw", venom_item)).status is ResultStatus.COMPLETED
    assert game.execute(ActivateAlchemy(
        venom_item, "poisoner",
    )).status is ResultStatus.COMPLETED
    assert game.inspect().turn_actor_id == "recipient"
    assert game.execute(EndTurn()).status is ResultStatus.COMPLETED

    strike = _keep_pending_check(game, game.execute(Strike("recipient", "dagger")))
    poison_save = next(
        event.check for event in strike.events
        if event.kind == "venom_fortitude_save"
    )
    assert poison_save is not None
    assert (poison_save.dc, poison_save.modifier) == (17, expected_modifier)
    assert any(
        modifier.amount == expected_bonus
        and modifier.modifier_type == "item" and modifier.source == source
        for modifier in poison_save.modifier_breakdown
    )


def test_saved_heroic_recovery_from_venom_stage_damage_finishes_end_turn_once(
    monkeypatch, tmp_path: Path,
) -> None:
    target_definition = replace(
        content.get_definition("fighter_m_level_1"),
        definition_id="review_venom_pc_target",
        name="Review Venom PC Target",
        abilities=(),
    )
    setup = _install_review_setup(
        monkeypatch,
        setup_id="review_venom_heroic_recovery",
        definitions=(target_definition,),
        placements=(
            CreaturePlacement(
                "alchemist", "bomber_alchemist_level_1_staged", "Bomber Alchemist",
                "blue", Position(1, 2),
            ),
            CreaturePlacement(
                "target", target_definition.definition_id, "Venom Target",
                "red", Position(2, 2),
            ),
        ),
    )
    game = Encounter.start(
        setup,
        # Initiatives; dagger success/damage; initial Fortitude failure/stage 1
        # damage; first stage-boundary Fortitude failure/stage 2 damage.
        rolls=(20, 1, 12, 1, 7, 1, 7, 4),
    )
    _settle_initial(game)
    _activate_prepared_formula(game, "giant_centipede_venom")
    assert game.inspect().turn_actor_id == "target"
    assert game.execute(EndTurn()).status is ResultStatus.COMPLETED

    _keep_pending_check(game, game.execute(Strike("target", "dagger")))
    affliction = game._state.giant_centipede_venom_afflictions[0]
    assert affliction.stage == 1
    assert game.execute(EndTurn()).status is ResultStatus.COMPLETED
    assert game.inspect().turn_actor_id == "target"
    target = game._state.creatures["target"]
    target.hp = 1
    ends_before = game._state.actor_end_counts["target"]

    paused = game.execute(EndTurn())
    assert paused.status is ResultStatus.PAUSED
    choice = paused.inspection.choice
    assert choice is not None and choice.kind == "heroic_recovery_damage"
    assert choice.owner_actor_id == "target"
    pending = game._state.pending_choice
    assert pending is not None and pending.continuation is not None
    assert pending.continuation.kind == "venom_end_turn"
    assert pending.continuation.parent_continuation is not None
    assert pending.continuation.parent_continuation.kind == "persistent_end_turn"
    assert game._state.actor_end_counts["target"] == ends_before
    advanced = game._state.giant_centipede_venom_afflictions[0]
    assert advanced.stage == 2

    path = tmp_path / "review-venom-heroic-recovery.json"
    game.save(path)
    game = Encounter.load(path)
    assert game.inspect().choice == choice
    assert game._state.giant_centipede_venom_afflictions == [advanced]

    resolved = game.execute(Choose(
        choice.choice_id, "heroic_recovery", choice.owner_actor_id,
    ))
    assert resolved.status is ResultStatus.COMPLETED
    target = game._state.creatures["target"]
    assert (
        target.hp, target.dying, target.wounded, target.unconscious,
        target.dead, target.hero_points,
    ) == (0, 0, 0, True, False, 0)
    assert game._state.actor_end_counts["target"] == ends_before + 1
    assert game.inspect().turn_actor_id == "alchemist"
    assert game._state.giant_centipede_venom_afflictions == [advanced]


def test_bounded_terminal_quick_creates_and_self_activates_venom() -> None:
    from pf2e.terminal import run_terminal

    commands = iter((
        "2", "1",  # Keep the Bomber's initiative roll.
        "4", "8",  # Quick Alchemy: Giant Centipede Venom.
        "5", "1",  # Activate the held quick-created venom on the dagger.
        "x",
    ))
    bounded_input = BoundedInput(lambda: next(commands), max_calls=12)
    transcript = BoundedTranscript(max_lines=180, max_chars=35_000)

    assert run_terminal(
        setup=content.get_setup("staged_bomber_alchemist_vs_guard_dog"),
        rolls=(20, 1), input_fn=bounded_input, output_fn=transcript.append,
    ) == 0
    assert bounded_input.calls == 8
    assert any("Quick Alchemy formula:" in line for line in transcript)
    assert any("Giant Centipede Venom" in line for line in transcript)
    assert any(
        "creates giant centipede venom from one stored versatile vial" in line
        for line in transcript
    )
    assert any(
        "applies Giant Centipede Venom to the held dagger" in line
        for line in transcript
    )


def test_two_action_venom_activation_is_not_offered_with_one_action_left() -> None:
    game = Encounter.start(
        content.get_setup("staged_bomber_alchemist_vs_guard_dog"),
        rolls=(20, 1),
    )
    _settle_initial(game)
    assert game.execute(QuickAlchemy(
        "create_consumable", "giant_centipede_venom",
    )).status is ResultStatus.COMPLETED
    assert game.execute(Stride((Position(1, 3),))).status is ResultStatus.COMPLETED
    assert game.options().actions_remaining == 1
    assert "activate_alchemy" not in game.options().available_actions


def test_day_two_cleanup_save_and_next_scene_use_new_infused_stock(
    tmp_path: Path,
) -> None:
    game = Encounter.start(
        content.get_setup("staged_bomber_alchemist_vs_guard_dog"),
        rolls=(20, 1, 10, 6, 10, 1, 20, 20, 6, 6),
    )
    _settle_initial(game)
    antidote_id = next(
        item.instance_id for item in game._state.infused_alchemy_items.values()
        if item.formula_id == "antidote_lesser"
    )
    assert game.execute(Interact("draw", antidote_id)).status is ResultStatus.COMPLETED
    assert game.execute(ActivateAlchemy(
        antidote_id, "alchemist",
    )).status is ResultStatus.COMPLETED
    assert any(
        effect.kind == "alchemy_antidote_lesser"
        for effect in game._state.active_effects
    )

    _throw_and_keep(game, QuickBomber("dog", "bottled_lightning_lesser"))
    assert game.inspect().turn_actor_id == "dog"
    assert game.execute(EndTurn()).status is ResultStatus.COMPLETED
    _throw_and_keep(game, QuickBomber("dog", "frost_vial_lesser"))
    assert game.inspect().winner_team == "blue"

    assert game.recover_versatile_vials(
        "alchemist", elapsed_seconds=600,
    ).status is ResultStatus.COMPLETED
    assert game.record_rested(
        ("alchemist",), day_number=2, elapsed_seconds=8 * 60 * 60,
    ).status is ResultStatus.COMPLETED
    assert game.daily_prepare(
        ("alchemist",), {"alchemist": {}},
    ).status is ResultStatus.COMPLETED
    assert antidote_id not in game._state.infused_alchemy_items
    assert antidote_id not in game._state.consumed_infused_item_ids
    assert not any(
        effect.kind == "alchemy_antidote_lesser"
        for effect in game._state.active_effects
    )
    day_two_frost = next(
        item.instance_id for item in game._state.infused_alchemy_items.values()
        if item.formula_id == "frost_vial_lesser"
        and item.daily_preparation_id == "day:2"
    )

    path = tmp_path / "review-bomber-day-two-next-scene.json"
    game.save(path)
    game = Encounter.load(path)
    moved = game.next_encounter(
        content.get_setup("staged_bomber_alchemist_next_vs_guard_dog")
    )
    assert moved.status in {ResultStatus.COMPLETED, ResultStatus.PAUSED}
    _settle_initial(game)
    if game.inspect().turn_actor_id != "alchemist":
        assert game.execute(EndTurn()).status is ResultStatus.COMPLETED

    thrown = _throw_and_keep(
        game, QuickBomber("next_dog", "frost_vial_lesser"),
    )
    assert any(event.kind == "bomb_consumed" for event in thrown.events)
    assert day_two_frost in game._state.consumed_infused_item_ids
