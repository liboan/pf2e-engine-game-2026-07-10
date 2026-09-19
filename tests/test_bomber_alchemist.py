from dataclasses import replace
from pathlib import Path
from types import MappingProxyType

import pf2e.content as content
from pf2e.alchemist_content import BOMBER_FIELD_FORMULA_IDS, admitted_bomber_bomb_facts
from pf2e.alchemy_content import FORMULAS_BY_ID
from pf2e.content import get_setup
from pf2e.encounter import Encounter
from pf2e.model import Choose, CreaturePlacement, EncounterSetup, EndTurn, Position, QuickBomber, ResultStatus


def _settle_initial(game: Encounter) -> None:
    while game.inspect().choice is not None:
        choice = game.inspect().choice
        assert choice is not None
        assert game.execute(Choose(choice.choice_id, "keep", choice.owner_actor_id)).status in {
            ResultStatus.COMPLETED, ResultStatus.PAUSED,
        }


def test_admitted_bomber_attacks_take_their_facts_from_the_selected_formula_pair() -> None:
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
            attack.damage_type,
            attack.damage_dice,
            attack.damage_modifier,
            attack.range_increment_ft,
            attack.max_range_ft,
        ) == (
            facts.damage_type,
            facts.initial_damage_dice,
            facts.initial_damage_flat,
            facts.range_increment_ft,
            facts.range_increment_ft * 6,
        )
    assert admitted_bomber_bomb_facts("alchemists_fire_lesser") is None
    assert admitted_bomber_bomb_facts([]) is None


def test_quick_bomber_draws_selected_bomb_saves_attack_choice_and_consumes_it(tmp_path: Path) -> None:
    game = Encounter.start(get_setup("staged_bomber_alchemist_vs_guard_dog"), rolls=(20, 1, 10, 6))
    _settle_initial(game)

    paused = game.execute(QuickBomber("dog", "bottled_lightning_lesser"))
    assert paused.status is ResultStatus.PAUSED
    assert paused.inspection.choice is not None
    assert paused.inspection.choice.kind == "attack_hero_reroll"
    assert "alchemist:bottled_lightning_lesser" in game._state.creatures["alchemist"].held_items
    game.save(tmp_path / "bomber-attack.json")

    restored = Encounter.load(tmp_path / "bomber-attack.json")
    choice = restored.inspect().choice
    assert choice is not None
    result = restored.execute(Choose(choice.choice_id, "keep", choice.owner_actor_id))
    assert result.status is ResultStatus.COMPLETED
    assert any(event.kind == "bomb_consumed" for event in result.events)
    assert restored._state.creatures["dog"].hp == 1
    assert any(
        effect.kind == "off_guard" and effect.target_actor_id == "dog"
        for effect in restored._state.condition_effects
    )
    assert "alchemist:bottled_lightning_lesser" not in restored._state.creatures["alchemist"].held_items
    assert "alchemist:bottled_lightning_lesser" not in restored._state.ground_items.get(restored._state.creatures["dog"].position, [])


def test_quick_alchemy_created_bomb_round_trips_with_creator_provenance(tmp_path: Path) -> None:
    from pf2e.model import QuickAlchemy

    game = Encounter.start(get_setup("staged_bomber_alchemist_vs_guard_dog"), rolls=(20, 1))
    _settle_initial(game)
    created = game.execute(QuickAlchemy("create_consumable", "bottled_lightning_lesser"))
    assert created.status is ResultStatus.COMPLETED
    state = game._state
    created_ids = [item_id for item_id in state.creatures["alchemist"].held_items if ":quick:" in item_id]
    assert len(created_ids) == 1
    item_id = created_ids[0]
    assert state.alchemy_states["alchemist"].stored_vials == 5
    assert state.infused_alchemy_items[item_id].creator_actor_id == "alchemist"
    game.save(tmp_path / "quick-created.json")

    restored = Encounter.load(tmp_path / "quick-created.json")
    assert item_id in restored._state.item_instances
    assert restored._state.infused_alchemy_items[item_id].activation_deadline == "creator_next_turn_start"
    assert restored._state.alchemy_states["alchemist"].stored_vials == 5


def test_consumed_infused_bomb_save_load_keeps_the_consumption_record(tmp_path: Path) -> None:
    game = Encounter.start(get_setup("staged_bomber_alchemist_vs_guard_dog"), rolls=(20, 1, 10, 1))
    _settle_initial(game)
    paused = game.execute(QuickBomber("dog", "bottled_lightning_lesser"))
    choice = paused.inspection.choice
    assert choice is not None
    game.execute(Choose(choice.choice_id, "keep", choice.owner_actor_id))
    game.save(tmp_path / "consumed-bomb.json")
    restored = Encounter.load(tmp_path / "consumed-bomb.json")
    item_id = "alchemist:bottled_lightning_lesser"
    assert item_id in restored._state.consumed_infused_item_ids
    assert item_id not in restored._state.creatures["alchemist"].held_items


def test_bomber_recovers_vials_and_daily_preparation_replaces_old_stock(tmp_path: Path) -> None:
    from pf2e.model import QuickAlchemy

    game = Encounter.start(
        get_setup("staged_bomber_alchemist_vs_guard_dog"),
        rolls=(20, 1, 10, 6, 10, 1, 20, 20, 6, 6),
    )
    _settle_initial(game)
    assert game.execute(QuickAlchemy("create_consumable", "bottled_lightning_lesser")).status is ResultStatus.COMPLETED
    for formula_id in ("bottled_lightning_lesser", "frost_vial_lesser"):
        pending = game.execute(QuickBomber("dog", formula_id))
        choice = pending.inspection.choice
        assert choice is not None
        game.execute(Choose(choice.choice_id, "keep", choice.owner_actor_id))
    assert game.inspect().winner_team == "blue"
    recovered = game.recover_versatile_vials("alchemist", elapsed_seconds=600)
    assert recovered.status is ResultStatus.COMPLETED
    assert game._state.alchemy_states["alchemist"].stored_vials == 6
    assert game.record_rested(("alchemist",), day_number=2, elapsed_seconds=8 * 60 * 60).status is ResultStatus.COMPLETED
    prepared = game.daily_prepare(("alchemist",), {"alchemist": {}})
    assert prepared.status is ResultStatus.COMPLETED
    assert game._state.alchemy_states["alchemist"].daily_preparation_id == "day:2"
    assert {item.formula_id for item in game._state.infused_alchemy_items.values() if item.daily_preparation_id == "day:2"} == {"bottled_lightning_lesser", "frost_vial_lesser", "elixir_of_life_minor", "antidote_lesser", "antiplague_lesser", "bestial_mutagen_lesser", "cognitive_mutagen_lesser", "giant_centipede_venom"}
    game.save(tmp_path / "bomber-day-two.json")
    restored = Encounter.load(tmp_path / "bomber-day-two.json")
    assert restored._state.alchemy_states["alchemist"].daily_preparation_id == "day:2"
    next_scene = restored.next_encounter(
        get_setup("staged_bomber_alchemist_next_vs_guard_dog")
    )
    assert next_scene.status in {ResultStatus.COMPLETED, ResultStatus.PAUSED}
    _settle_initial(restored)
    if restored.inspect().turn_actor_id != "alchemist":
        assert restored.execute(EndTurn()).status is ResultStatus.COMPLETED
    assert restored.inspect().turn_actor_id == "alchemist"
    post_prep_bomb = restored.execute(
        QuickBomber("next_dog", "bottled_lightning_lesser")
    )
    choice = post_prep_bomb.inspection.choice
    completed = (
        restored.execute(Choose(choice.choice_id, "keep", choice.owner_actor_id))
        if choice is not None else post_prep_bomb
    )
    assert completed.status is ResultStatus.COMPLETED
    assert any(event.kind == "bomb_consumed" for event in completed.events)


def test_created_minor_elixir_heals_living_recipient_and_is_consumed() -> None:
    from pf2e.model import ActivateAlchemy, QuickAlchemy

    game = Encounter.start(get_setup("staged_bomber_alchemist_vs_guard_dog"), rolls=(20, 1, 5))
    _settle_initial(game)
    game._state.creatures["alchemist"].hp = 10
    assert game.execute(QuickAlchemy("create_consumable", "elixir_of_life_minor")).status is ResultStatus.COMPLETED
    item_id = next(item for item in game._state.creatures["alchemist"].held_items if item.endswith(":quick:1"))
    result = game.execute(ActivateAlchemy(item_id))
    assert result.status is ResultStatus.COMPLETED
    assert game._state.creatures["alchemist"].hp == 15
    assert item_id in game._state.consumed_infused_item_ids


def test_selected_mutagen_replaces_prior_effect_and_round_trips(tmp_path: Path) -> None:
    from pf2e.model import ActivateAlchemy, Interact

    game = Encounter.start(get_setup("staged_bomber_alchemist_vs_guard_dog"), rolls=(20, 1))
    _settle_initial(game)
    bestial = next(item for item, record in game._state.infused_alchemy_items.items() if record.formula_id == "bestial_mutagen_lesser")
    assert game.execute(Interact("draw", bestial)).status is ResultStatus.COMPLETED
    assert game.execute(ActivateAlchemy(bestial)).status is ResultStatus.COMPLETED
    assert any(effect.kind == "alchemy_bestial_mutagen_lesser" for effect in game._state.active_effects)
    game.save(tmp_path / "bomber-mutagen.json")
    restored = Encounter.load(tmp_path / "bomber-mutagen.json")
    assert any(effect.kind == "alchemy_bestial_mutagen_lesser" for effect in restored._state.active_effects)


def test_giant_centipede_venom_requires_held_dagger_and_two_actions() -> None:
    from pf2e.model import ActivateAlchemy, Interact

    game = Encounter.start(get_setup("staged_bomber_alchemist_vs_guard_dog"), rolls=(20, 1))
    _settle_initial(game)
    venom = next(item for item, record in game._state.infused_alchemy_items.items() if record.formula_id == "giant_centipede_venom")
    assert game.execute(ActivateAlchemy(venom)).status is ResultStatus.REJECTED
    assert game.execute(Interact("draw", venom)).status is ResultStatus.COMPLETED
    result = game.execute(ActivateAlchemy(venom))
    assert result.status is ResultStatus.COMPLETED
    assert any(effect.kind == "alchemy_giant_centipede_venom_coating" and effect.value == 17 for effect in game._state.active_effects)
    assert venom in game._state.consumed_infused_item_ids


def test_coated_dagger_hit_saves_literal_dc17_venom_affliction(tmp_path: Path) -> None:
    from pf2e.model import ActivateAlchemy, EndTurn, Interact, Position, Strike

    game = Encounter.start(get_setup("staged_bomber_alchemist_vs_guard_dog"), rolls=(20, 1, 20, 4, 7, 3))
    _settle_initial(game)
    game._state.creatures["dog"].position = Position(2, 2)
    venom = next(item for item, record in game._state.infused_alchemy_items.items() if record.formula_id == "giant_centipede_venom")
    assert game.execute(Interact("draw", venom)).status is ResultStatus.COMPLETED
    assert game.execute(ActivateAlchemy(venom)).status is ResultStatus.COMPLETED
    assert game.execute(EndTurn()).status is ResultStatus.COMPLETED
    result = game.execute(Strike("dog", "dagger"))
    if result.status is ResultStatus.PAUSED:
        choice = game.inspect().choice
        assert choice is not None
        result = game.execute(Choose(choice.choice_id, "keep", choice.owner_actor_id))
    assert any(event.kind == "venom_fortitude_save" and event.check is not None and event.check.dc == 17 for event in result.events)
    affliction = game._state.giant_centipede_venom_afflictions[0]
    assert (
        affliction.source_actor_id, affliction.target_actor_id, affliction.dc,
        affliction.stage, affliction.expires_at_world_time,
    ) == ("alchemist", "dog", 17, 1, game._state.world_time_seconds + 36)
    path = tmp_path / "bomber-venom-affliction.json"
    game.save(path)
    restored = Encounter.load(path)
    assert restored._state.giant_centipede_venom_afflictions == [affliction]


def test_venom_stage_boundary_advances_and_saves_stage_three(tmp_path: Path, monkeypatch) -> None:
    from pf2e.model import ActivateAlchemy, EndTurn, Interact, Position, QuickAlchemy, Strike

    durable_dog = replace(content.get_definition("guard_dog_mc2924"), hp=1000)
    monkeypatch.setattr(
        content,
        "_STAGED_CREATURES",
        MappingProxyType({**content._STAGED_CREATURES, durable_dog.definition_id: durable_dog}),
    )
    game = Encounter.start(
        get_setup("staged_bomber_alchemist_vs_guard_dog"),
        rolls=(20, 1, 20, 1, 7, 2, 7, 3, 7, 4),
    )
    _settle_initial(game)
    game._state.creatures["dog"].position = Position(2, 2)
    venom = next(item for item, record in game._state.infused_alchemy_items.items() if record.formula_id == "giant_centipede_venom")
    assert game.execute(Interact("draw", venom)).status is ResultStatus.COMPLETED
    assert game.execute(ActivateAlchemy(venom)).status is ResultStatus.COMPLETED
    assert game.execute(EndTurn()).status is ResultStatus.COMPLETED
    result = game.execute(Strike("dog", "dagger"))
    if result.status is ResultStatus.PAUSED:
        choice = game.inspect().choice
        assert choice is not None
        result = game.execute(Choose(choice.choice_id, "keep", choice.owner_actor_id))
    assert result.status is ResultStatus.COMPLETED

    assert game.execute(EndTurn()).status is ResultStatus.COMPLETED
    boundary = game.execute(EndTurn())
    assert boundary.status is ResultStatus.COMPLETED
    assert any(event.kind == "venom_fortitude_save" and event.check is not None and event.check.degree.label() == "Failure" for event in boundary.events)
    assert any(event.kind == "venom_stage_effect" for event in boundary.events)
    affliction = game._state.giant_centipede_venom_afflictions[0]
    assert (affliction.stage, affliction.next_save_at_target_end) == (2, game._state.actor_end_counts["dog"] + 1)
    assert game.execute(EndTurn()).status is ResultStatus.COMPLETED
    boundary = game.execute(EndTurn())
    assert boundary.status is ResultStatus.COMPLETED
    affliction = game._state.giant_centipede_venom_afflictions[0]
    assert affliction.stage == 3
    path = tmp_path / "bomber-venom-stage-three.json"
    game.save(path)
    assert Encounter.load(path)._state.giant_centipede_venom_afflictions == [affliction]


def test_giant_centipede_venom_expires_after_its_six_round_maximum(monkeypatch) -> None:
    from pf2e.model import ActivateAlchemy, Interact, Strike

    durable_dog = replace(
        content.get_definition("guard_dog_mc2924"),
        definition_id="owner_durable_venom_expiry_dog", hp=100,
    )
    setup = EncounterSetup(
        "owner_giant_centipede_venom_expiry", "Venom duration fixture", 7, 5,
        (
            CreaturePlacement("alchemist", "bomber_alchemist_level_1_staged", "Bomber Alchemist", "blue", Position(1, 2)),
            CreaturePlacement("dog", durable_dog.definition_id, "Durable Guard Dog", "red", Position(2, 2)),
        ),
    )
    monkeypatch.setattr(
        content, "_STAGED_CREATURES",
        MappingProxyType({**content._STAGED_CREATURES, durable_dog.definition_id: durable_dog}),
    )
    monkeypatch.setattr(
        content, "_STAGED_SETUPS",
        MappingProxyType({**content._STAGED_SETUPS, setup.setup_id: setup}),
    )
    game = Encounter.start(
        setup,
        rolls=(20, 1, 20, 1, 7, 1, 7, 1, 7, 1, 7, 1, 7, 1, 7, 1, 7, 1, 7, 1),
    )
    _settle_initial(game)
    venom = next(item for item, record in game._state.infused_alchemy_items.items() if record.formula_id == "giant_centipede_venom")
    assert game.execute(Interact("draw", venom)).status is ResultStatus.COMPLETED
    assert game.execute(ActivateAlchemy(venom)).status is ResultStatus.COMPLETED
    assert game.execute(EndTurn()).status is ResultStatus.COMPLETED
    hit = game.execute(Strike("dog", "dagger"))
    if hit.status is ResultStatus.PAUSED:
        choice = game.inspect().choice
        assert choice is not None
        assert game.execute(Choose(choice.choice_id, "keep", choice.owner_actor_id)).status is ResultStatus.COMPLETED
    assert game._state.giant_centipede_venom_afflictions
    for _ in range(16):
        if not game._state.giant_centipede_venom_afflictions:
            break
        assert game.execute(EndTurn()).status is ResultStatus.COMPLETED
    assert game._state.world_time_seconds >= 36
    assert game._state.giant_centipede_venom_afflictions == []


def test_terminal_draws_and_activates_prepared_minor_elixir() -> None:
    from pf2e.terminal import run_terminal

    commands = iter((
        "2", "1",  # Resolve the Bomber's initiative choice by keeping it.
        "6", "3",  # Interact: draw prepared Minor Elixir of Life.
        "5", "1", "1",  # Activate it; choose held elixir and self recipient.
        "x",  # End the bounded terminal transcript.
    ))
    output: list[str] = []
    assert run_terminal(
        setup=get_setup("staged_bomber_alchemist_vs_guard_dog"), rolls=(20, 1, 4),
        input_fn=lambda: next(commands), output_fn=output.append,
    ) == 0
    assert any("drinks Minor Elixir of Life and heals 4 HP" in line for line in output)


def test_terminal_quick_bomber_lists_and_throws_the_admitted_formula_pair() -> None:
    from pf2e.terminal import run_terminal

    commands = iter((
        "2", "1",  # Resolve the Bomber's initiative choice by keeping it.
        "5", "1", "1",  # Quick Bomber: Bottled Lightning, then the Guard Dog.
        "1",  # Keep the saved attack result.
        "x",  # End the bounded terminal transcript.
    ))
    output: list[str] = []
    assert run_terminal(
        setup=get_setup("staged_bomber_alchemist_vs_guard_dog"), rolls=(20, 1, 10, 6),
        input_fn=lambda: next(commands), output_fn=output.append,
    ) == 0
    transcript = "\n".join(output)
    assert "Prepared bomb:" in transcript
    assert "Bottled Lightning (lesser)" in transcript
    assert "Frost Vial (lesser)" in transcript
    assert any("uses Quick Bomber" in line for line in output)
