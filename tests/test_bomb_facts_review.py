"""Independent review of finite BombFacts adoption for the selected Bomber.

Sources:
* Quick Bomber: https://2e.aonprd.com/Feats.aspx?ID=5764
* Bomb and splash rules: https://2e.aonprd.com/Rules.aspx?ID=3181
* Bomber field: https://2e.aonprd.com/ResearchFields.aspx?ID=5
* Bottled Lightning: https://2e.aonprd.com/Equipment.aspx?ID=3290
* Frost Vial: https://2e.aonprd.com/Equipment.aspx?ID=3293
* Quick Alchemy: https://2e.aonprd.com/Actions.aspx?ID=2801
"""

from __future__ import annotations

from copy import deepcopy
import json
from dataclasses import replace
from types import MappingProxyType

import pytest

import pf2e.content as content
from pf2e.alchemist_content import (
    BOMBER_FIELD_FORMULA_IDS,
    admitted_bomber_bomb_facts,
)
from pf2e.alchemy_content import FORMULAS_BY_ID
from pf2e.encounter import Encounter
from pf2e.model import (
    Choose,
    CreaturePlacement,
    DamageDefense,
    EndTurn,
    EncounterSetup,
    Position,
    QuickAlchemy,
    QuickBomber,
    ResultStatus,
)
from pf2e.terminal import run_terminal


def _settle(game: Encounter) -> None:
    while (choice := game.inspect().choice) is not None:
        assert game.execute(
            Choose(choice.choice_id, "keep", choice.owner_actor_id)
        ).status in {ResultStatus.COMPLETED, ResultStatus.PAUSED}


def _throw_and_keep(game: Encounter, command: QuickBomber):
    result = game.execute(command)
    if result.status is ResultStatus.PAUSED:
        choice = result.inspection.choice
        assert choice is not None and choice.kind == "attack_hero_reroll"
        result = game.execute(Choose(choice.choice_id, "keep", choice.owner_actor_id))
    assert result.status is ResultStatus.COMPLETED
    return result


def _setup(monkeypatch: pytest.MonkeyPatch, setup_id: str, placements, definitions=()):
    for definition in definitions:
        monkeypatch.setattr(
            content,
            "_STAGED_CREATURES",
            MappingProxyType({
                **content._STAGED_CREATURES, definition.definition_id: definition,
            }),
        )
    setup = EncounterSetup(setup_id, setup_id, 7, 5, tuple(placements))
    monkeypatch.setattr(
        content,
        "_STAGED_SETUPS",
        MappingProxyType({**content._STAGED_SETUPS, setup_id: setup}),
    )
    return setup


def test_only_two_admitted_formula_facts_define_the_selected_attacks_atomically() -> None:
    definition = content.get_definition("bomber_alchemist_level_1_staged")
    attacks = {attack.item_id: attack for attack in definition.attacks}
    assert BOMBER_FIELD_FORMULA_IDS == (
        "bottled_lightning_lesser", "frost_vial_lesser",
    )
    for formula_id in BOMBER_FIELD_FORMULA_IDS:
        facts = admitted_bomber_bomb_facts(formula_id)
        assert facts is FORMULAS_BY_ID[formula_id].facts
        assert facts is not None
        attack = attacks[formula_id]
        assert (
            attack.damage_type, attack.damage_dice, attack.damage_modifier,
            attack.range_increment_ft, attack.max_range_ft,
        ) == (
            facts.damage_type, facts.initial_damage_dice, facts.initial_damage_flat,
            facts.range_increment_ft, facts.range_increment_ft * 6,
        )
    assert admitted_bomber_bomb_facts("alchemists_fire_lesser") is None
    assert admitted_bomber_bomb_facts("acid_flask_lesser") is None

    game = Encounter.start(
        content.get_setup("staged_bomber_alchemist_vs_guard_dog"), rolls=(20, 1),
    )
    _settle(game)
    before, dice_before = deepcopy(game._state), game._dice.to_data()
    rejected = game.execute(QuickBomber("dog", "alchemists_fire_lesser"))
    assert rejected.status is ResultStatus.REJECTED
    assert game._state == before and game._dice.to_data() == dice_before


def test_critical_failure_consumes_bomb_without_primary_splash() -> None:
    game = Encounter.start(
        content.get_setup("staged_bomber_alchemist_vs_guard_dog"),
        rolls=(20, 1, 1),
    )
    _settle(game)

    result = _throw_and_keep(
        game, QuickBomber("dog", "bottled_lightning_lesser"),
    )

    strike = next(event for event in result.events if event.kind == "strike")
    assert strike.check is not None and strike.check.degree.name == "CRITICAL_FAILURE"
    assert game._state.creatures["dog"].hp == 8
    assert any(event.kind == "bomb_consumed" for event in result.events)
    assert not any(event.kind == "damage" for event in result.events)


def test_primary_packet_defense_and_critical_splash_use_formula_facts(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    resistant = replace(
        content.get_definition("guard_dog_mc2924"),
        definition_id="bomb_facts_electricity_resistant_dog",
        damage_defenses=(DamageDefense(
            "resistance", "electricity", 1, source="review electricity resistance",
        ),),
    )
    setup = _setup(
        monkeypatch,
        "bomb_facts_packet_review",
        (
            CreaturePlacement(
                "alchemist", "bomber_alchemist_level_1_staged", "Bomber Alchemist",
                "blue", Position(1, 2),
            ),
            CreaturePlacement(
                "primary", resistant.definition_id, "Primary Dog", "red", Position(4, 2),
            ),
            CreaturePlacement(
                "nearby", "guard_dog_mc2924", "Nearby Dog", "red", Position(4, 3),
            ),
        ),
        (resistant,),
    )
    lightning = Encounter.start(setup, rolls=(20, 1, 2, 10, 4))
    _settle(lightning)
    _throw_and_keep(
        lightning, QuickBomber("primary", "bottled_lightning_lesser"),
    )
    assert lightning._state.creatures["primary"].hp == 4
    assert lightning._state.creatures["nearby"].hp == 7

    frost = Encounter.start(setup, rolls=(20, 1, 2, 20, 3))
    _settle(frost)
    result = _throw_and_keep(frost, QuickBomber("primary", "frost_vial_lesser"))
    strike = next(event for event in result.events if event.kind == "strike")
    assert strike.check is not None and strike.check.degree.name == "CRITICAL_SUCCESS"
    assert frost._state.creatures["primary"].hp == 1
    assert frost._state.creatures["nearby"].hp == 7


def test_saved_primary_only_throw_rejects_formula_identity_tamper(
    monkeypatch: pytest.MonkeyPatch, tmp_path,
) -> None:
    setup = _setup(
        monkeypatch,
        "bomb_facts_saved_scope_review",
        (
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
    _settle(game)
    paused = game.execute(QuickBomber(
        "primary", "frost_vial_lesser", only_primary_splash=True,
    ))
    assert paused.status is ResultStatus.PAUSED
    path = tmp_path / "bomb-saved-scope.json"
    game.save(path)

    tampered = json.loads(path.read_text())
    tampered["state"]["pending_choice"]["attack_id"] = "bottled_lightning"
    path.write_text(json.dumps(tampered))
    with pytest.raises(
        ValueError,
        match="different Strike context|unavailable item identity|illegal pending Strike target or attack",
    ):
        Encounter.load(path)

    game.save(path)
    loaded = Encounter.load(path)
    choice = loaded.inspect().choice
    assert choice is not None
    completed = loaded.execute(Choose(choice.choice_id, "keep", choice.owner_actor_id))
    assert completed.status is ResultStatus.COMPLETED
    assert loaded._state.creatures["primary"].hp == 5
    assert loaded._state.creatures["nearby"].hp == 8


def test_formula_riders_round_trip_with_distinct_expiration_anchors(tmp_path) -> None:
    for formula_id, kind, boundary, anchor in (
        ("bottled_lightning_lesser", "off_guard", "start", "alchemist"),
        ("frost_vial_lesser", "speed_penalty", "end", "dog"),
    ):
        game = Encounter.start(
            content.get_setup("staged_bomber_alchemist_vs_guard_dog"),
            rolls=(20, 1, 10, 1),
        )
        _settle(game)
        _throw_and_keep(game, QuickBomber("dog", formula_id))
        effect = next(
            effect for effect in game._state.condition_effects if effect.kind == kind
        )
        assert (effect.expiration.anchor_actor_id, effect.expiration.boundary) == (
            anchor, boundary,
        )
        path = tmp_path / f"{formula_id}-rider.json"
        game.save(path)
        loaded = Encounter.load(path)
        assert effect in loaded._state.condition_effects
        assert loaded.execute(EndTurn()).status is ResultStatus.COMPLETED
        assert any(item.kind == kind for item in loaded._state.condition_effects)
        assert loaded.execute(EndTurn()).status is ResultStatus.COMPLETED
        assert not any(item.kind == kind for item in loaded._state.condition_effects)


def test_quick_created_bomb_round_trips_and_consumes_creator_item_once(tmp_path) -> None:
    game = Encounter.start(
        content.get_setup("staged_bomber_alchemist_vs_guard_dog"),
        rolls=(20, 1, 10, 2),
    )
    _settle(game)
    assert game.execute(QuickAlchemy(
        "create_consumable", "frost_vial_lesser",
    )).status is ResultStatus.COMPLETED
    quick_id = next(
        item_id for item_id in game._state.creatures["alchemist"].held_items
        if ":quick:" in item_id
    )
    infused = game._state.infused_alchemy_items[quick_id]
    assert (infused.creator_actor_id, infused.activation_deadline) == (
        "alchemist", "creator_next_turn_start",
    )
    path = tmp_path / "quick-created-frost.json"
    game.save(path)
    game = Encounter.load(path)
    result = _throw_and_keep(game, QuickBomber("dog", "frost_vial_lesser"))
    assert quick_id in game._state.consumed_infused_item_ids
    assert all(
        quick_id not in inventory
        for actor in game._state.creatures.values()
        for inventory in (actor.held_items, actor.worn_items, actor.stowed_items)
    )
    assert all(
        quick_id not in items for items in game._state.ground_items.values()
    )
    assert sum(event.kind == "bomb_consumed" for event in result.events) == 1


def test_terminal_lists_two_formulas_and_a_real_range_valid_target() -> None:
    commands = iter((
        "2", "1",  # Keep the Bomber's initiative.
        "5", "1", "1",  # Quick Bomber, Bottled Lightning, Guard Dog.
        "1", "x",  # Keep attack, then quit.
    ))
    output: list[str] = []
    assert run_terminal(
        setup=content.get_setup("staged_bomber_alchemist_vs_guard_dog"),
        rolls=(20, 1, 10, 6), input_fn=lambda: next(commands), output_fn=output.append,
    ) == 0
    transcript = "\n".join(output)
    assert "Prepared bomb:" in transcript
    assert "Bottled Lightning (lesser)" in transcript
    assert "Frost Vial (lesser)" in transcript
    assert "Guard Dog (dog)" in transcript
    assert "1. Bottled Lightning (lesser)\n2. Frost Vial (lesser)" in transcript
    assert "3. Alchemist's Fire (lesser)" not in transcript
    assert "Acid Flask (lesser)" not in transcript
    assert "uses Quick Bomber" in transcript


def test_day_two_stock_survives_save_and_throws_in_next_scene(tmp_path) -> None:
    game = Encounter.start(
        content.get_setup("staged_bomber_alchemist_vs_guard_dog"),
        rolls=(20, 1, 10, 6, 10, 1, 20, 20, 6, 6),
    )
    _settle(game)
    _throw_and_keep(game, QuickBomber("dog", "bottled_lightning_lesser"))
    assert game.execute(EndTurn()).status is ResultStatus.COMPLETED
    while game.inspect().turn_actor_id != "alchemist":
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
    day_two_frost = next(
        item.instance_id for item in game._state.infused_alchemy_items.values()
        if item.formula_id == "frost_vial_lesser"
        and item.daily_preparation_id == "day:2"
    )
    path = tmp_path / "bomb-day-two.json"
    game.save(path)
    game = Encounter.load(path)
    assert game.next_encounter(
        content.get_setup("staged_bomber_alchemist_next_vs_guard_dog")
    ).status in {ResultStatus.COMPLETED, ResultStatus.PAUSED}
    _settle(game)
    if game.inspect().turn_actor_id != "alchemist":
        assert game.execute(EndTurn()).status is ResultStatus.COMPLETED
    result = _throw_and_keep(
        game, QuickBomber("next_dog", "frost_vial_lesser"),
    )
    assert any(event.kind == "bomb_consumed" for event in result.events)
    assert day_two_frost in game._state.consumed_infused_item_ids
