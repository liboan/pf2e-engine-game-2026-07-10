"""Public, saveable behavior for the first fundamental weapon rune grade."""

from pathlib import Path

from pf2e import Cast, Encounter, ResultStatus, Strike, ViciousSwing
from pf2e.content import get_setup
from pf2e.skill_actions import Demoralize, Feint, Grapple, Trip


def _settle_initiative(game: Encounter) -> None:
    while (choice := game.inspect().choice) is not None:
        assert choice.kind == "initiative_hero_reroll"
        game.choose(choice.choice_id, "keep")


def _runed_attack() -> Encounter:
    game = Encounter.start(
        get_setup("fundamental_rune_weapon_test"),
        # Fighter initiative, dog initiative, Strike d20, then the two longsword d8s.
        rolls=(20, 1, 15, 4, 7),
    )
    _settle_initiative(game)
    assert game.inspect().turn_actor_id == "rune_fighter"
    return game


def _strike_and_check(game: Encounter):
    result = game.execute(Strike("rune_dog", attack_id="longsword"))
    choice = result.inspection.choice
    assert result.status is ResultStatus.PAUSED
    assert choice is not None and choice.kind == "attack_hero_reroll"
    check = next(event.check for event in result.events if event.check is not None)
    assert check is not None
    assert check.modifier == 10  # printed +9 plus the +1 item bonus
    assert any(
        modifier.amount == 1 and modifier.modifier_type == "item"
        for modifier in check.modifier_breakdown
    )
    return result, choice.choice_id


def test_plus_one_striking_longsword_strike_round_trips_pending_choice(tmp_path: Path) -> None:
    uninterrupted = _runed_attack()
    uninterrupted_pending, uninterrupted_choice_id = _strike_and_check(uninterrupted)

    game = _runed_attack()
    pending, choice_id = _strike_and_check(game)
    assert pending.inspection == uninterrupted_pending.inspection
    assert choice_id == uninterrupted_choice_id

    stable_id = "rune_fighter:longsword"
    item = game._state.item_instances[stable_id]
    assert item.rune_ids == ("weapon_potency_1", "striking")
    assert item.invested is False
    assert stable_id in next(actor for actor in game._state.creatures.values() if actor.actor_id == "rune_fighter").held_items

    path = tmp_path / "pending-rune-strike.json"
    game.save(path)
    restored = Encounter.load(path)
    assert restored.inspect() == game.inspect()
    assert restored._state.item_instances[stable_id] == item

    resumed = restored.choose(choice_id, "keep")
    direct = uninterrupted.choose(uninterrupted_choice_id, "keep")
    assert resumed.status is ResultStatus.COMPLETED
    assert resumed.events == direct.events
    damage = next(event.damage for event in resumed.events if event.damage is not None)
    assert damage is not None and damage.total == 30  # 2d8 + 4, doubled on the critical hit
    assert damage.components[0].dice == (8, 8)
    assert damage.components[0].rolls == (4, 7)
    assert not restored.inspect().in_progress
    assert restored.inspect() == uninterrupted.inspect()


def _settle_initial_choices(game: Encounter) -> None:
    while (choice := game.inspect().choice) is not None:
        assert choice.kind == "initiative_hero_reroll"
        game.choose(choice.choice_id, "keep")


def test_armor_potency_changes_real_ac_only_when_worn_and_invested() -> None:
    rolls = (20, 1, 2, 3, 12, 4)
    setup = get_setup("fundamental_rune_armor_ac_test")
    cases = (
        ("armor_active", 19, "FAILURE"),
        ("armor_uninvested", 18, "SUCCESS"),
        ("armor_unworn", 18, "SUCCESS"),
    )
    for target_id, expected_ac, expected_degree in cases:
        game = Encounter.start(setup, rolls=rolls)
        _settle_initial_choices(game)
        assert game.inspect().turn_actor_id == "armor_dog"
        target = next(actor for actor in game.inspect().actors if actor.actor_id == target_id)
        assert target.ac == expected_ac
        if target_id == "armor_unworn":
            state = game._state.creatures[target_id]
            assert tuple(state.worn_items) == ("armor_unworn:mundane_breastplate",)
            assert tuple(state.stowed_items) == ("armor_unworn:runed_breastplate",)
            stowed_runes = game._state.item_instances["armor_unworn:runed_breastplate"]
            assert stowed_runes.rune_ids == ("armor_potency_1", "resilient")
            assert stowed_runes.invested

        result = game.execute(Strike(target_id, attack_id="jaws"))
        check = next(event.check for event in result.events if event.check is not None)
        assert check is not None and check.dc == expected_ac
        assert check.degree.name == expected_degree


def test_invested_armor_public_fight_finishes_and_saved_strike_matches(tmp_path: Path) -> None:
    # The active runed fighter wins a complete healthy encounter against the
    # dog; the other two blue actors are present only as fixed comparison
    # targets for the investment boundary above.
    setup = get_setup("fundamental_rune_armor_ac_test")
    rolls = (1, 20, 2, 3, 20, 1)

    uninterrupted = Encounter.start(setup, rolls=rolls)
    _settle_initial_choices(uninterrupted)
    assert uninterrupted.inspect().turn_actor_id == "armor_active"
    direct = uninterrupted.execute(Strike("armor_dog", attack_id="longsword"))
    direct_choice = direct.inspection.choice
    assert direct.status is ResultStatus.PAUSED and direct_choice is not None

    game = Encounter.start(setup, rolls=rolls)
    _settle_initial_choices(game)
    paused = game.execute(Strike("armor_dog", attack_id="longsword"))
    choice = paused.inspection.choice
    assert choice is not None and choice.kind == "attack_hero_reroll"
    path = tmp_path / "pending-armor-fight.json"
    game.save(path)
    restored = Encounter.load(path)
    assert restored.inspect() == paused.inspection
    resumed = restored.choose(choice.choice_id, "keep")
    finished = uninterrupted.choose(direct_choice.choice_id, "keep")
    assert resumed.events == finished.events
    assert resumed.status is ResultStatus.COMPLETED
    assert not resumed.inspection.in_progress and resumed.inspection.winner_team == "blue"
    assert restored.inspect() == uninterrupted.inspect()


def test_resilient_changes_trip_grapple_and_demoralize_defense_dcs() -> None:
    setup = get_setup("fundamental_rune_armor_save_dc_test")
    target_variants = (
        ("armor_active", 1),
        ("armor_uninvested", 0),
        ("armor_unworn", 0),
    )
    actions = (
        (lambda target: Trip(target), "trip_check", 16),
        (lambda target: Grapple(target), "grapple_check", 18),
        (lambda target: Demoralize(target), "demoralize_check", 14),
    )
    for target_id, rune_bonus in target_variants:
        for command_for, event_kind, printed_dc in actions:
            game = Encounter.start(setup, rolls=(20, 1, 2, 3, 10))
            _settle_initial_choices(game)
            assert game.inspect().turn_actor_id == "synthetic_a"
            result = game.execute(command_for(target_id))
            event = next(event for event in result.events if event.kind == event_kind)
            assert event.check is not None
            assert event.check.dc == printed_dc + rune_bonus


def test_resilient_rune_modifies_saved_void_warp_fortitude_check(tmp_path: Path) -> None:
    setup = get_setup("fundamental_rune_armor_spell_save_test")
    rolls = (20, 1, 8, 1, 1)
    uninterrupted = Encounter.start(setup, rolls=rolls)
    _settle_initial_choices(uninterrupted)
    assert uninterrupted.inspect().turn_actor_id == "armor_cleric"
    direct_attack = uninterrupted.execute(Cast("void_warp", "armor_target"))
    if direct_attack.inspection.choice is not None and direct_attack.inspection.choice.kind == "reaction":
        reaction = direct_attack.inspection.choice
        direct_attack = uninterrupted.choose(reaction.choice_id, "decline", reaction.owner_actor_id)
    direct_choice = direct_attack.inspection.choice
    assert direct_attack.status is ResultStatus.PAUSED
    assert direct_choice is not None and direct_choice.kind == "spell_save_hero_reroll"
    direct_check = next(event.check for event in direct_attack.events if event.kind == "spell_save")
    assert direct_check is not None and direct_check.modifier == 9
    assert any(
        modifier.amount == 1 and modifier.modifier_type == "item"
        for modifier in direct_check.modifier_breakdown
    )

    game = Encounter.start(setup, rolls=rolls)
    _settle_initial_choices(game)
    paused = game.execute(Cast("void_warp", "armor_target"))
    if paused.inspection.choice is not None and paused.inspection.choice.kind == "reaction":
        reaction = paused.inspection.choice
        paused = game.choose(reaction.choice_id, "decline", reaction.owner_actor_id)
    path = tmp_path / "pending-resilient-save.json"
    game.save(path)
    restored = Encounter.load(path)
    assert restored.inspect() == paused.inspection
    item = restored._state.item_instances["armor_target:breastplate"]
    assert item.rune_ids == ("armor_potency_1", "resilient") and item.invested

    resumed = restored.choose(direct_choice.choice_id, "keep")
    direct = uninterrupted.choose(direct_choice.choice_id, "keep")
    assert resumed.events == direct.events
    assert resumed.status is ResultStatus.COMPLETED
    assert restored.inspect() == uninterrupted.inspect()


def test_feint_fighter_uses_skilled_human_deception_modifier() -> None:
    game = Encounter.start(
        get_setup("s3_feint_fighter_duel"),
        rolls=(20, 1, 10),
    )
    _settle_initial_choices(game)
    result = game.execute(Feint("duel_fighter"))
    choice = result.inspection.choice
    assert result.status is ResultStatus.PAUSED and choice is not None
    resolved = game.choose(choice.choice_id, "keep", choice.owner_actor_id)
    check_event = next(event for event in resolved.events if event.kind == "feint_check")
    assert check_event.check is not None
    assert check_event.check.modifier == 3
    assert any(
        modifier.source == "printed deception modifier" and modifier.amount == 3
        for modifier in check_event.check.modifier_breakdown
    )


def test_invested_handwraps_modify_actual_fist_attack_and_round_trip(tmp_path: Path) -> None:
    setup = get_setup("fundamental_rune_handwrap_test")
    rolls = (20, 1, 15, 2, 3)
    uninterrupted = Encounter.start(setup, rolls=rolls)
    _settle_initial_choices(uninterrupted)
    assert uninterrupted.inspect().turn_actor_id == "wrap_fighter"
    result = uninterrupted.execute(Strike("wrap_dog", attack_id="fist"))
    choice = result.inspection.choice
    assert result.status is ResultStatus.PAUSED
    assert choice is not None and choice.kind == "attack_hero_reroll"
    check = next(event.check for event in result.events if event.check is not None)
    assert check is not None and check.modifier == 10
    assert any(modifier.source == "handwraps" for modifier in check.modifier_breakdown)

    game = Encounter.start(setup, rolls=rolls)
    _settle_initial_choices(game)
    paused = game.execute(Strike("wrap_dog", attack_id="fist"))
    path = tmp_path / "pending-handwrap-strike.json"
    game.save(path)
    restored = Encounter.load(path)
    item = restored._state.item_instances["wrap_fighter:handwraps"]
    assert item.definition_id == "handwraps_of_mighty_blows"
    assert item.rune_ids == ("weapon_potency_1", "striking") and item.invested
    assert "wrap_fighter:handwraps" in restored._state.creatures["wrap_fighter"].worn_items
    resumed = restored.choose(paused.inspection.choice.choice_id, "keep")
    direct = uninterrupted.choose(choice.choice_id, "keep")
    assert resumed.events == direct.events
    damage = next(event.damage for event in resumed.events if event.damage is not None)
    assert damage is not None and damage.total == 18  # 2d4 + 4 on a critical hit
    assert damage.components[0].dice == (4, 4)
    assert damage.components[0].rolls == (2, 3)


def test_uninvested_handwraps_are_worn_but_grant_no_rune_attack_benefits() -> None:
    game = Encounter.start(
        get_setup("fundamental_rune_handwrap_uninvested_test"),
        rolls=(20, 1, 15, 2),
    )
    _settle_initial_choices(game)
    result = game.execute(Strike("wrap_dog", attack_id="fist"))
    choice = result.inspection.choice
    assert result.status is ResultStatus.PAUSED
    assert choice is not None and choice.kind == "attack_hero_reroll"
    check = next(event.check for event in result.events if event.check is not None)
    assert check is not None and check.modifier == 9
    assert not any(modifier.source == "handwraps" for modifier in check.modifier_breakdown)
    resumed = game.choose(choice.choice_id, "keep")
    damage = next(event.damage for event in resumed.events if event.damage is not None)
    assert damage is not None and damage.components[0].dice == (4,)
    assert damage.components[0].rolls == (2,)
    assert damage.total == 6


def test_striking_weapon_keeps_vicious_swing_extra_die_and_map() -> None:
    game = Encounter.start(
        get_setup("fundamental_rune_weapon_test"),
        # Initiative, first Strike d20/two striking d8s, Vicious Swing d20/three d8s.
        rolls=(20, 1, 5, 1, 2, 20, 2, 3, 4),
    )
    _settle_initial_choices(game)
    first = game.execute(Strike("rune_dog", attack_id="longsword"))
    first_choice = first.inspection.choice
    assert first_choice is not None and first_choice.kind == "attack_hero_reroll"
    game.choose(first_choice.choice_id, "keep")

    swing = game.execute(ViciousSwing("rune_dog", attack_id="longsword"))
    swing_choice = swing.inspection.choice
    assert swing.status is ResultStatus.PAUSED
    assert swing_choice is not None and swing_choice.kind == "attack_hero_reroll"
    resolved = game.choose(swing_choice.choice_id, "keep")
    check = next(event.check for event in resolved.events if event.check is not None)
    damage = next(event.damage for event in resolved.events if event.damage is not None)
    assert check is not None and check.map_penalty == -5 and check.attack_count == 2
    assert damage is not None and damage.components[0].dice == (8, 8, 8)
    assert damage.components[0].rolls == (2, 3, 4)
    assert damage.total == 26  # (2d8 striking + 1d8 Vicious Swing + 4) x2
