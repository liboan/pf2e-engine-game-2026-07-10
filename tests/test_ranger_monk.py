"""Source-backed Ranger and Monk rules for the level-1 class slice."""

from __future__ import annotations

import pytest

import pf2e.content as content
from pf2e.encounter import Encounter
from pf2e.monk import FlurryOfBlows
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

from pf2e.damage import DamageTerm
from pf2e.monk import is_flurry_strike, powerful_fist_removes_lethal_penalty
from pf2e.model import ActiveConditionEffect, Choose, CreaturePlacement, EffectExpiration, EncounterSetup, Event, HuntedPreyState, PairedStrikeContinuation, PairedStrikeSelection, Position, ResultStatus, Strike, Stride
from pf2e.paired_strikes import _decode_selection, _encode_selection, after_subordinate_strike, second_strike_options
from pf2e.ranger import (
    HunterEdge,
    HuntPrey,
    HuntedShot,
    flurry_map_penalty,
    hunt_prey_skill_modifier,
    hunted_prey_range_penalty,
    outwit_ac_modifier,
    outwit_skill_modifier,
    precision_damage_term,
)
from pf2e.ranger_monk_content import MONK, RANGER_DEFINITIONS, RANGER_PRECISION
from pf2e.skill_actions import QuickJump, Trip
from pf2e.terminal import run_terminal
from terminal_test_helpers import BoundedInput, BoundedTranscript


def _choose(game: Encounter, option_id: str):
    choice = game.inspect().choice
    assert choice is not None
    return game.execute(Choose(choice.choice_id, option_id, choice.owner_actor_id))


def _settle_initiative(game: Encounter) -> None:
    for _ in range(8):
        choice = game.inspect().choice
        if choice is None:
            return
        assert choice.kind in {"initiative_hero_reroll", "initiative_tie"}
        option = "keep" if any(item.option_id == "keep" for item in choice.options) else choice.options[0].option_id
        _choose(game, option)
    raise AssertionError("initiative did not settle")


def test_flurry_edge_reduces_map_only_against_prey_and_counts_all_prior_attacks() -> None:
    edge = HunterEdge.FLURRY

    assert flurry_map_penalty(0, frozenset(), attacking_hunted_prey=True, edge=edge) == 0
    assert flurry_map_penalty(1, frozenset(), attacking_hunted_prey=True, edge=edge) == -3
    assert flurry_map_penalty(2, frozenset(), attacking_hunted_prey=True, edge=edge) == -6
    assert flurry_map_penalty(1, frozenset({"agile"}), attacking_hunted_prey=True, edge=edge) == -2
    assert flurry_map_penalty(2, frozenset({"agile"}), attacking_hunted_prey=True, edge=edge) == -4

    # The first prior attack can be against a different target; MAP still counts it.
    assert flurry_map_penalty(1, frozenset(), attacking_hunted_prey=False, edge=edge) == -5
    assert flurry_map_penalty(1, frozenset(), attacking_hunted_prey=True, edge=HunterEdge.OUTWIT) == -5


def test_hunt_prey_bonuses_are_target_and_action_scoped() -> None:
    assert hunt_prey_skill_modifier(target_is_hunted_prey=True, action_id="seek").amount == 2
    assert hunt_prey_skill_modifier(target_is_hunted_prey=True, action_id="track").modifier_type == "circumstance"
    assert hunt_prey_skill_modifier(target_is_hunted_prey=False, action_id="seek") is None
    assert hunt_prey_skill_modifier(target_is_hunted_prey=True, action_id="recall_knowledge") is None

    assert outwit_skill_modifier(
        HunterEdge.OUTWIT,
        target_is_hunted_prey=True,
        statistic="nature",
        action_id="recall_knowledge",
    ).amount == 2
    assert outwit_skill_modifier(
        HunterEdge.OUTWIT, target_is_hunted_prey=True, statistic="athletics"
    ) is None
    assert outwit_ac_modifier(HunterEdge.OUTWIT, attacker_is_hunted_prey=True).amount == 1
    assert outwit_ac_modifier(HunterEdge.OUTWIT, attacker_is_hunted_prey=False) is None


def test_hunt_prey_ignores_only_second_range_increment_penalty() -> None:
    # Shortbow increment 60 ft. Hunt Prey removes the ordinary -2 in the
    # second increment; the third increment still takes its full -4 penalty.
    assert hunted_prey_range_penalty(60, 60, target_is_hunted_prey=True) == 0
    assert hunted_prey_range_penalty(65, 60, target_is_hunted_prey=True) == 0
    assert hunted_prey_range_penalty(120, 60, target_is_hunted_prey=True) == 0
    assert hunted_prey_range_penalty(125, 60, target_is_hunted_prey=True) == -4
    assert hunted_prey_range_penalty(125, 60, target_is_hunted_prey=False) == -4
    with pytest.raises(ValueError):
        hunted_prey_range_penalty(10, 0, target_is_hunted_prey=True)


def test_precision_is_a_once_per_round_precision_term_with_critical_doubling() -> None:
    term = precision_damage_term(
        HunterEdge.PRECISION,
        is_hunted_prey=True,
        precision_used_round=0,
        current_round=2,
        damage_type="piercing",
    )
    assert term == DamageTerm(
        source="ranger_precision",
        damage_type="piercing",
        dice=(8,),
        tags=frozenset({"precision"}),
        critical_mode="double",
    )
    assert precision_damage_term(
        HunterEdge.PRECISION,
        is_hunted_prey=True,
        precision_used_round=2,
        current_round=2,
        damage_type="piercing",
    ) is None
    assert precision_damage_term(
        HunterEdge.PRECISION,
        is_hunted_prey=False,
        precision_used_round=0,
        current_round=2,
        damage_type="piercing",
    ) is None


def test_flurry_weapon_permission_and_powerful_fist_exception_are_exact() -> None:
    fist = next(attack for attack in MONK.attacks if attack.attack_id == "fist")
    kama = next(attack for attack in MONK.attacks if attack.attack_id == "kama")
    assert fist.damage_dice == (6,) and fist.modifier == 7
    assert ("unarmed_attacks", "trained") in MONK.proficiencies
    assert is_flurry_strike(MONK.abilities, fist)
    assert is_flurry_strike(MONK.abilities, kama)
    assert not is_flurry_strike((), kama)
    assert not is_flurry_strike(
        MONK.abilities, replace(kama, traits=kama.traits - {"weapon"})
    )
    assert powerful_fist_removes_lethal_penalty(MONK.abilities, fist, nonlethal=False)
    other_unarmed = replace(fist, attack_id="claw")
    assert powerful_fist_removes_lethal_penalty(MONK.abilities, other_unarmed, nonlethal=False)
    assert not powerful_fist_removes_lethal_penalty(MONK.abilities, fist, nonlethal=None)
    assert not powerful_fist_removes_lethal_penalty(MONK.abilities, fist, nonlethal=True)
    assert not powerful_fist_removes_lethal_penalty(MONK.abilities, kama, nonlethal=False)


def test_level_one_definitions_cover_all_edges_and_selected_class_feats() -> None:
    assert set(RANGER_DEFINITIONS) == {
        "ranger_flurry_level_1",
        "ranger_outwit_level_1",
        "ranger_precision_level_1",
    }
    for edge, definition in zip(("flurry", "outwit", "precision"), RANGER_DEFINITIONS.values()):
        assert f"hunter_edge_{edge}" in definition.abilities
        assert "hunt_prey" in definition.abilities
        assert "hunted_shot" in definition.abilities
        assert definition.level == 1
        shortbow = next(attack for attack in definition.attacks if attack.attack_id == "shortbow")
        assert "ranged" in shortbow.traits
        assert shortbow.ammunition_id == "arrow"
        assert definition.ammunition == (("arrow", 20),)
        assert definition.land_speed_ft == 30
        assert "Fleet" in definition.feats
        fist = next(attack for attack in definition.attacks if attack.attack_id == "fist")
        assert (fist.modifier, fist.damage_modifier, fist.attack_attribute, fist.damage_attribute) == (7, 1, "dexterity", "strength")
    assert MONK.level == 1
    assert {"flurry_of_blows", "powerful_fist", "monastic_weaponry"} <= set(MONK.abilities)
    assert MONK.land_speed_ft == 30
    assert "Fleet" in MONK.feats
    assert {"Natural Skill", "Hunted Shot"} <= set(RANGER_DEFINITIONS["ranger_flurry_level_1"].feats)


def test_saved_second_strike_option_retains_default_damage_and_nonlethal_choices() -> None:
    selection = PairedStrikeSelection(
        target_id="guard_dog_b",
        attack_id="fist",
        damage_type=None,
        nonlethal=None,
    )
    option_id = _encode_selection(selection)
    assert option_id.startswith("paired:")
    assert _decode_selection(option_id) == selection
    assert _decode_selection("paired:not-valid-json") is None
    import base64
    import json

    malformed = base64.urlsafe_b64encode(
        json.dumps({"target": "guard_dog_b", "attack": "fist", "damage": None, "nonlethal": 1}).encode()
    ).decode().rstrip("=")
    assert _decode_selection("paired:" + malformed) is None


def test_flurry_second_strike_menu_keeps_default_choices_and_both_attacks() -> None:
    actor = SimpleNamespace(
        actor_id="monk",
        label="Monk",
        position=Position(0, 0),
        held_items=("kama",),
        unconscious=False,
        dead=False,
        must_leave_occupied=False,
        hunted_prey=None,
    )
    target = SimpleNamespace(
        actor_id="dog",
        label="Guard Dog",
        position=Position(1, 0),
        defeated=False,
    )
    state = SimpleNamespace(creatures={actor.actor_id: actor, target.actor_id: target})
    encounter = SimpleNamespace(
        _attack_usable=lambda _state, owner, attack: attack.item_id is None or attack.item_id in owner.held_items,
        _attack_damage_types=lambda attack: (attack.damage_type,),
    )
    context = SimpleNamespace(
        actor=actor,
        state=state,
        definition=SimpleNamespace(attacks=MONK.attacks, abilities=MONK.abilities),
        encounter=encounter,
    )
    continuation = PairedStrikeContinuation(
        activity_id="monk:flurry_of_blows",
        owner_actor_id=actor.actor_id,
        paid_actions=1,
        initial_attack_count=0,
        selections=(PairedStrikeSelection("dog", "kama"),),
        outcomes=(object(),),
        next_index=1,
        stage="choose_second",
    )

    choices = tuple(_decode_selection(option.option_id) for option in second_strike_options(context, continuation))
    assert {choice.attack_id for choice in choices if choice is not None} == {"kama"}
    assert all(choice is not None and choice.damage_type is None for choice in choices)
    assert any(choice is not None and choice.attack_id == "kama" and choice.nonlethal is None for choice in choices)


def test_first_strike_callback_offers_second_choice_only_after_resolved_stage() -> None:
    actor = SimpleNamespace(
        actor_id="monk",
        label="Monk",
        position=Position(0, 0),
        held_items=("kama",),
        unconscious=False,
        dead=False,
        must_leave_occupied=False,
        hunted_prey=None,
    )
    target = SimpleNamespace(
        actor_id="dog",
        label="Guard Dog",
        position=Position(1, 0),
        defeated=False,
    )
    presented = {}
    encounter = SimpleNamespace(
        _attack_usable=lambda _state, owner, attack: attack.item_id is None or attack.item_id in owner.held_items,
        _attack_damage_types=lambda attack: (attack.damage_type,),
        _complete_action=lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("parent action ended early")),
    )
    context = SimpleNamespace(
        actor=actor,
        state=SimpleNamespace(creatures={actor.actor_id: actor, target.actor_id: target}),
        definition=SimpleNamespace(attacks=MONK.attacks, abilities=MONK.abilities),
        encounter=encounter,
        present_choice=lambda *args, **kwargs: presented.update(args=args, kwargs=kwargs),
    )
    first_result = Event("strike_result", "monk", "dog", "First Strike fully resolved.")
    continuation = PairedStrikeContinuation(
        activity_id="monk:flurry_of_blows",
        owner_actor_id=actor.actor_id,
        paid_actions=1,
        initial_attack_count=0,
        selections=(PairedStrikeSelection("dog", "kama"),),
        outcomes=(object(),),
        next_index=1,
        stage="first_resolved",
    )

    result = after_subordinate_strike(context, continuation, events=(first_result,))

    assert result.events == (first_result,)
    assert presented["args"][0] == "monk:flurry_of_blows"
    saved_pair = presented["kwargs"]["paired_strike"]
    assert saved_pair.stage == "choose_second"
    assert saved_pair.selections == continuation.selections
    assert len(saved_pair.outcomes) == 1
    second_choice_ids = {option.option_id for option in presented["args"][3]}
    assert len(second_choice_ids) == 2
    assert presented["args"][4].kind == "paired_strike"


def test_hunted_shot_second_strike_stays_on_current_prey_with_reload_zero_bow() -> None:
    bow_definition = next(
        attack for attack in RANGER_DEFINITIONS["ranger_flurry_level_1"].attacks
        if attack.attack_id == "shortbow"
    )
    bow = SimpleNamespace(**{
        **{name: getattr(bow_definition, name) for name in bow_definition.__dataclass_fields__},
        "reload": 0,
    })
    actor = SimpleNamespace(
        actor_id="ranger",
        label="Ranger",
        position=Position(0, 0),
        held_items=("shortbow",),
        unconscious=False,
        dead=False,
        must_leave_occupied=False,
        hunted_prey=HuntedPreyState("prey"),
    )
    prey = SimpleNamespace(actor_id="prey", label="Hunted Prey", position=Position(8, 0), defeated=False)
    other = SimpleNamespace(actor_id="other", label="Other", position=Position(2, 0), defeated=False)
    state = SimpleNamespace(creatures={actor.actor_id: actor, prey.actor_id: prey, other.actor_id: other})
    encounter = SimpleNamespace(
        _attack_usable=lambda _state, owner, attack: attack.item_id in owner.held_items,
        _attack_damage_types=lambda attack: (attack.damage_type,),
    )
    context = SimpleNamespace(
        actor=actor,
        state=state,
        definition=SimpleNamespace(attacks=(bow,), abilities=RANGER_DEFINITIONS["ranger_flurry_level_1"].abilities),
        encounter=encounter,
    )
    continuation = PairedStrikeContinuation(
        activity_id="ranger:hunted_shot",
        owner_actor_id=actor.actor_id,
        paid_actions=1,
        initial_attack_count=0,
        selections=(PairedStrikeSelection("prey", "shortbow"),),
        outcomes=(object(),),
        next_index=1,
        stage="choose_second",
    )

    choices = tuple(_decode_selection(option.option_id) for option in second_strike_options(context, continuation))
    assert choices
    assert {choice.target_id for choice in choices if choice is not None} == {"prey"}
    assert all(choice is not None and choice.attack_id == "shortbow" for choice in choices)
    actor.hunted_prey = HuntedPreyState("other")
    assert second_strike_options(context, continuation) == ()


def test_class_pending_validators_route_through_paired_procedure() -> None:
    from pf2e import monk, ranger

    with pytest.raises(ValueError, match="no paired-Strike continuation"):
        ranger.validate_pending(SimpleNamespace(pending=SimpleNamespace(
            procedure_id="ranger:hunted_shot", paired_strike=None
        )))
    with pytest.raises(ValueError, match="no paired-Strike continuation"):
        monk.validate_pending(SimpleNamespace(pending=SimpleNamespace(
            procedure_id="monk:flurry_of_blows", paired_strike=None
        )))


def test_precision_ranger_hunt_prey_then_shortbow_uses_second_increment_and_precision() -> None:
    # Hunt Prey removes only the shortbow's second-increment penalty.  The
    # first finalized hit that round adds a separately tagged 1d8 Precision
    # component, so ordinary damage defenses can still distinguish it.
    game = Encounter.start(content.get_setup("staged_ranger_precision_bow"), rolls=(20, 1, 1, 10, 4, 3))
    _settle_initiative(game)
    assert game.inspect().turn_actor_id == "ranger"
    hunted = game.execute(HuntPrey("guard_dog_a"))
    assert hunted.status is ResultStatus.COMPLETED

    started = game.execute(Strike("guard_dog_a", attack_id="shortbow"))
    assert started.status is ResultStatus.PAUSED
    check = next(event.check for event in started.events if event.kind == "strike")
    assert check is not None and check.map_penalty == 0 and check.modifier == 7
    assert not any(item.source == "range increment penalty" for item in check.modifier_breakdown)
    finished = _choose(game, "keep")
    damage = next(event.damage for event in finished.events if event.damage is not None)
    assert damage is not None
    assert [component.source for component in damage.components] == ["shortbow", "ranger_precision"]
    assert game._state.creatures["ranger"].ammunition["arrow"] == 19
    assert game._state.creatures["ranger"].precision_used_round == game._state.round_number


def test_fleet_stride_then_hunt_prey_and_hunted_shot_continue_the_selected_combat() -> None:
    # Versatile Human supplies a legal general feat; Fleet raises the printed
    # 25-foot land Speed to 30. The route then uses only selected combat rules.
    game = Encounter.start(
        content.get_setup("staged_ranger_precision_bow"),
        rolls=(20, 1, 1, 10, 4, 3, 10, 5),
    )
    _settle_initiative(game)
    assert game.effective_speed_ft("ranger") == 30
    stride = game.execute(Stride(tuple(Position(column, 1) for column in range(1, 7))))
    assert stride.status is ResultStatus.COMPLETED
    assert game._state.creatures["ranger"].position == Position(6, 1)
    assert game._state.creatures["ranger"].actions_remaining == 2
    assert game.execute(HuntPrey("guard_dog_a")).status is ResultStatus.COMPLETED
    started = game.execute(HuntedShot(PairedStrikeSelection("guard_dog_a", "shortbow")))
    assert started.status is ResultStatus.PAUSED
    assert _choose(game, "keep").inspection.choice is not None


def test_ranger_finesse_fist_uses_dexterity_for_attack_and_strength_for_damage() -> None:
    # Finesse replaces Strength only for the attack roll. The selected
    # Ranger's Dexterity +4 yields +7 trained attack; Strength stays +1.
    game = Encounter.start(
        content.get_setup("staged_ranger_precision_bow"), rolls=(20, 1, 1, 10, 4),
    )
    _settle_initiative(game)
    game._state.creatures["guard_dog_b"].position = Position(1, 1)
    started = game.execute(Strike("guard_dog_b", attack_id="fist"))
    check = next(event.check for event in started.events if event.kind == "strike")
    assert check is not None and check.modifier == 7
    resolved = _choose(game, "keep")
    damage = next(event.damage for event in resolved.events if event.damage is not None)
    assert damage is not None and damage.components[0].modifier == 1


def test_hunt_prey_keeps_the_third_increment_penalty() -> None:
    game = Encounter.start(
        content.get_setup("staged_ranger_precision_bow"), rolls=(20, 1, 1, 10, 4, 3),
    )
    _settle_initiative(game)
    game._state.creatures["guard_dog_a"].position = Position(25, 1)
    assert game.execute(HuntPrey("guard_dog_a")).status is ResultStatus.COMPLETED
    started = game.execute(Strike("guard_dog_a", attack_id="shortbow"))
    check = next(event.check for event in started.events if event.kind == "strike")
    assert check is not None and check.modifier == 3
    assert any(
        item.source == "range increment penalty" and item.amount == -4
        for item in check.modifier_breakdown
    )


def test_hunted_shot_rejects_without_current_prey_atomically() -> None:
    game = Encounter.start(content.get_setup("staged_ranger_precision_bow"), rolls=(20, 1, 1))
    _settle_initiative(game)
    before = (game._state.creatures["ranger"].actions_remaining, game._state.creatures["ranger"].ammunition["arrow"], game._state.creatures["ranger"].strikes_this_turn)
    rejected = game.execute(HuntedShot(PairedStrikeSelection("guard_dog_a", "shortbow")))
    assert rejected.status is ResultStatus.REJECTED
    assert "hunted prey" in rejected.message.lower()
    assert (
        game._state.creatures["ranger"].actions_remaining,
        game._state.creatures["ranger"].ammunition["arrow"],
        game._state.creatures["ranger"].strikes_this_turn,
    ) == before


def test_hunted_shot_runs_two_ranged_strikes_with_sequential_map_and_ammunition(tmp_path: Path) -> None:
    game = Encounter.start(
        content.get_setup("staged_ranger_precision_bow"),
        rolls=(20, 1, 1, 10, 4, 3, 10, 5),
    )
    _settle_initiative(game)
    assert game.execute(HuntPrey("guard_dog_a")).status is ResultStatus.COMPLETED

    started = game.execute(HuntedShot(PairedStrikeSelection("guard_dog_a", "shortbow")))
    assert started.status is ResultStatus.PAUSED
    first = _choose(game, "keep")
    first_check = next(event.check for event in first.events if event.kind == "strike")
    assert first_check is not None and first_check.map_penalty == 0
    choice = game.inspect().choice
    assert choice is not None and choice.kind == "family_action"

    saved = tmp_path / "hunted-shot-second-choice.json"
    game.save(saved)
    game = Encounter.load(saved)
    choice = game.inspect().choice
    assert choice is not None and choice.kind == "family_action"

    encoded = next(option.option_id for option in choice.options if _decode_selection(option.option_id) == PairedStrikeSelection("guard_dog_a", "shortbow"))
    second = _choose(game, encoded)
    assert second.status is ResultStatus.PAUSED
    finished = _choose(game, "keep")
    second_check = next(event.check for event in finished.events if event.kind == "strike")
    assert second_check is not None and second_check.map_penalty == -5
    assert any(event.kind == "paired_strike_complete" for event in finished.events)
    assert game._state.creatures["ranger"].ammunition["arrow"] == 18


def test_grabbed_hunted_shot_flat_check_failure_keeps_arrow_and_stops_second_shot(
    tmp_path: Path,
) -> None:
    game = Encounter.start(
        content.get_setup("staged_ranger_precision_bow"),
        rolls=(20, 1, 1, 4),
    )
    _settle_initiative(game)
    assert game.execute(HuntPrey("guard_dog_a")).status is ResultStatus.COMPLETED
    game._state.condition_effects.append(ActiveConditionEffect(
        "test-grapple", "grabbed", "guard_dog_a", "ranger", 1,
        EffectExpiration("guard_dog_a", "end", 1),
    ))

    paused = game.execute(HuntedShot(PairedStrikeSelection("guard_dog_a", "shortbow")))
    assert paused.status is ResultStatus.PAUSED
    choice = game.inspect().choice
    assert choice is not None and choice.kind == "grabbed_manipulate_hero_reroll"
    assert game._state.creatures["ranger"].ammunition["arrow"] == 20
    assert game._state.creatures["ranger"].strikes_this_turn == 0

    saved = tmp_path / "grabbed-hunted-shot.json"
    game.save(saved)
    game = Encounter.load(saved)

    stopped = _choose(game, "keep")
    assert stopped.status is ResultStatus.COMPLETED
    assert any(event.kind == "action_lost" for event in stopped.events)
    assert not any(event.kind == "strike" for event in stopped.events)
    assert game._state.creatures["ranger"].ammunition["arrow"] == 20
    assert game._state.creatures["ranger"].strikes_this_turn == 0


def test_hunted_prey_carries_across_scenes_then_daily_preparation_clears_it(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    first = EncounterSetup(
        setup_id="test_ranger_prey_first_scene",
        name="Ranger prey first scene",
        width=4,
        height=3,
        placements=(
            CreaturePlacement("ranger", RANGER_PRECISION.definition_id, "Precision Ranger", "blue", Position(0, 1)),
            CreaturePlacement("old_dog", "guard_dog_mc2924", "Old Guard Dog", "red", Position(1, 1)),
        ),
    )
    second = EncounterSetup(
        setup_id="test_ranger_prey_second_scene",
        name="Ranger prey second scene",
        width=4,
        height=3,
        placements=(
            CreaturePlacement("ranger", RANGER_PRECISION.definition_id, "Precision Ranger", "blue", Position(0, 1)),
            CreaturePlacement("new_dog", "guard_dog_mc2924", "New Guard Dog", "red", Position(1, 1)),
        ),
    )
    monkeypatch.setattr(
        content, "_STAGED_SETUPS",
        content._STAGED_SETUPS | {first.setup_id: first, second.setup_id: second},
    )
    game = Encounter.start(first, rolls=(20, 1, 20, 6, 10, 8, 20, 1))
    _settle_initiative(game)
    assert game.execute(HuntPrey("old_dog")).status is ResultStatus.COMPLETED
    started = game.execute(HuntedShot(PairedStrikeSelection("old_dog", "shortbow")))
    assert started.status is ResultStatus.PAUSED
    assert _choose(game, "keep").inspection.winner_team == "blue"

    before_prep = tmp_path / "preparation-prey.json"
    game.save(before_prep)
    prepared = Encounter.load(before_prep)
    assert prepared.record_rested(("ranger",), day_number=2, elapsed_seconds=28_800).status is ResultStatus.COMPLETED
    assert prepared.daily_prepare(("ranger",)).status is ResultStatus.COMPLETED
    assert prepared._state.creatures["ranger"].hunted_prey is None

    advanced = game.next_encounter(second)
    assert advanced.status in {ResultStatus.COMPLETED, ResultStatus.PAUSED}
    _settle_initiative(game)
    assert game._state.creatures["ranger"].hunted_prey == HuntedPreyState("old_dog")
    carried = tmp_path / "carried-prey.json"
    game.save(carried)
    assert Encounter.load(carried)._state.creatures["ranger"].hunted_prey == HuntedPreyState("old_dog")


def test_healthy_monk_recovers_prepares_saves_and_acts_in_next_scene(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    """The selected Monk retains its Fleet Speed through ordinary staged continuity.

    The build retains its historical setup ID after horizontal-only catalog
    admission. This covers the source-settled sheet grant and the existing
    common recovery/next-scene lifecycle without expanding into vertical play.
    """
    first = content.get_setup("staged_monk_kama_flurry")
    second = EncounterSetup(
        setup_id="test_monk_next_scene",
        name="Monk next scene",
        width=6,
        height=3,
        placements=(
            CreaturePlacement("monk", MONK.definition_id, "Monk", "blue", Position(1, 1)),
            CreaturePlacement("next_dog", "guard_dog_mc2924", "Next Guard Dog", "red", Position(4, 1)),
        ),
    )
    monkeypatch.setattr(content, "_STAGED_SETUPS", content._STAGED_SETUPS | {second.setup_id: second})

    # Initiative, two critical kama Strikes/d6 damage, next-scene initiative,
    # then a live fist Strike/d6 damage.
    game = Encounter.start(first, rolls=(20, 1, 1, 20, 6, 20, 6, 20, 1, 20, 6))
    _settle_initiative(game)
    assert game.inspect().turn_actor_id == "monk"
    assert game.execute(FlurryOfBlows(PairedStrikeSelection("guard_dog_a", "kama"))).status is ResultStatus.PAUSED
    assert _choose(game, "keep").status is ResultStatus.PAUSED
    second_choice = game.inspect().choice
    assert second_choice is not None
    second_kama = next(
        option.option_id
        for option in second_choice.options
        if (selection := _decode_selection(option.option_id)) is not None
        and selection.target_id == "guard_dog_b"
    )
    assert _choose(game, second_kama).status is ResultStatus.PAUSED
    assert _choose(game, "keep").inspection.winner_team == "blue"
    assert game._state.creatures["monk"].hp == MONK.hp

    assert game.record_rested(("monk",), day_number=2, elapsed_seconds=28_800).status is ResultStatus.COMPLETED
    save_path = tmp_path / "healthy-monk-rested.json"
    game.save(save_path)
    game = Encounter.load(save_path)
    assert game.daily_prepare(("monk",)).status is ResultStatus.COMPLETED

    transitioned = game.next_encounter(second)
    assert transitioned.status is ResultStatus.PAUSED
    _settle_initiative(game)
    monk = next(actor for actor in game.inspect().actors if actor.actor_id == "monk")
    assert monk.speed_ft == 30 and monk.hp == MONK.hp
    assert game.execute(Stride((Position(2, 1), Position(3, 1)))).status is ResultStatus.COMPLETED
    strike = game.execute(Strike("next_dog", attack_id="fist"))
    assert strike.status is ResultStatus.PAUSED
    resolved = _choose(game, "keep")
    assert any(event.kind == "strike" and event.actor_id == "monk" for event in resolved.events)

def test_kama_flurry_is_one_action_with_sequential_map_and_second_target(tmp_path: Path) -> None:
    # Initiative, first kama attack/d6, second kama attack/d6.  The first
    # hit defeats its dog, so the saved second menu must select the other dog.
    game = Encounter.start(content.get_setup("staged_monk_kama_flurry"), rolls=(20, 1, 1, 20, 6, 20, 6))
    _settle_initiative(game)
    assert game.inspect().turn_actor_id == "monk"
    started = game.execute(FlurryOfBlows(PairedStrikeSelection("guard_dog_a", "kama")))
    assert started.status is ResultStatus.PAUSED
    first = _choose(game, "keep")
    first_check = next(event.check for event in first.events if event.kind == "strike")
    assert first_check is not None and first_check.map_penalty == 0
    choice = game.inspect().choice
    assert choice is not None and choice.kind == "family_action"
    path = tmp_path / "saved-kama-second-choice.json"
    game.save(path)
    game = Encounter.load(path)
    choice = game.inspect().choice
    assert choice is not None and choice.kind == "family_action"
    selections = tuple(_decode_selection(option.option_id) for option in choice.options)
    second = next(item for item in selections if item is not None and item.target_id == "guard_dog_b")
    finished = _choose(game, next(option.option_id for option in choice.options if _decode_selection(option.option_id) == second))
    assert finished.status is ResultStatus.PAUSED
    finished = _choose(game, "keep")
    checks = [event.check for event in finished.events if event.kind == "strike"]
    assert checks and checks[0] is not None and checks[0].map_penalty == -4
    assert any(event.kind == "paired_strike_complete" for event in finished.events)
    assert finished.inspection.winner_team == "blue"


def test_powerful_fist_keeps_normal_nonlethal_and_removes_only_lethal_penalty(tmp_path: Path) -> None:
    # Player Core 2 says Powerful Fist makes a fist d6 and removes the normal
    # -2 circumstance penalty only for a lethal fist or other unarmed Strike.
    # The selected Monk's printed fist is already d6; this probes the runtime
    # check modifier and persisted Hero choice for both attack intents.
    for nonlethal in (None, False):
        game = Encounter.start(
            content.get_setup("staged_monk_kama_flurry"), rolls=(20, 1, 1, 20, 6)
        )
        _settle_initiative(game)
        paused = game.execute(Strike("guard_dog_a", attack_id="fist", nonlethal=nonlethal))
        assert paused.status is ResultStatus.PAUSED
        check = next(event.check for event in paused.events if event.kind == "strike")
        choice = game.inspect().choice
        assert choice is not None and choice.kind == "attack_hero_reroll" and check is not None
        assert check.modifier == 7
        assert all(item.source != "nonlethal intent" for item in check.modifier_breakdown)
        saved = tmp_path / f"saved-powerful-fist-{nonlethal}.json"
        game.save(saved)
        loaded = Encounter.load(saved)
        resumed = _choose(loaded, "keep")
        assert any(event.kind == "strike" for event in resumed.events)


def test_fist_lethal_intent_changes_the_pc_knockout_outcome(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    setup = EncounterSetup(
        setup_id="test_monk_fist_lethal_outcome",
        name="Monk fist intent outcome",
        width=4,
        height=3,
        placements=(
            CreaturePlacement("monk", MONK.definition_id, "Monk", "blue", Position(1, 1)),
            CreaturePlacement("fighter", "fighter_m_level_1", "Fighter", "red", Position(2, 1)),
        ),
    )
    monkeypatch.setattr(content, "_STAGED_SETUPS", content._STAGED_SETUPS | {setup.setup_id: setup})
    for nonlethal, expected_dying in ((True, 0), (False, 2)):
        game = Encounter.start(setup, rolls=(20, 1, 20, 6))
        _settle_initiative(game)
        # A critical fist hit exceeds this PC's remaining HP.  Its printed
        # nonlethal trait knocks out at dying 0; Powerful Fist permits an
        # explicit lethal choice without changing the attack's check modifier.
        game._state.creatures["fighter"].hp = 7
        game._state.creatures["fighter"].hero_points = 0
        paused = game.execute(Strike("fighter", attack_id="fist", nonlethal=nonlethal))
        assert paused.status is ResultStatus.PAUSED
        resolved = _choose(game, "keep")
        assert any(event.kind == "damage" for event in resolved.events)
        fighter = next(actor for actor in game.inspect().actors if actor.actor_id == "fighter")
        assert fighter.unconscious and fighter.dying == expected_dying


def test_fist_flurry_saves_same_type_second_choice_and_rejects_mixed_attack(tmp_path: Path) -> None:
    # Flurry applies normal agile MAP (0, then -4) and each pair stays fist/fist
    # so the supported shared-defense record has one physical damage type.
    game = Encounter.start(content.get_setup("staged_monk_kama_flurry"), rolls=(20, 1, 1, 20, 6, 20, 6))
    _settle_initiative(game)
    started = game.execute(FlurryOfBlows(PairedStrikeSelection("guard_dog_a", "fist", nonlethal=False)))
    assert started.status is ResultStatus.PAUSED
    first = _choose(game, "keep")
    first_check = next(event.check for event in first.events if event.kind == "strike")
    assert first_check is not None and first_check.map_penalty == 0 and first_check.modifier == 7
    choice = game.inspect().choice
    assert choice is not None and choice.kind == "family_action"
    assert all(
        item is not None and item.attack_id == "fist"
        for item in (_decode_selection(option.option_id) for option in choice.options)
    )
    rejected = game.execute(Choose(
        choice.choice_id,
        _encode_selection(PairedStrikeSelection("guard_dog_b", "kama", nonlethal=False)),
        choice.owner_actor_id,
    ))
    assert rejected.status is ResultStatus.REJECTED
    assert game.inspect().choice == choice
    saved = tmp_path / "saved-fist-second-choice.json"
    game.save(saved)
    game = Encounter.load(saved)
    choice = game.inspect().choice
    assert choice is not None
    decoded_options = tuple(
        (option.option_id, _decode_selection(option.option_id)) for option in choice.options
    )
    second = next(
        option_id for option_id, selection in decoded_options
        if selection is not None
        and selection.target_id == "guard_dog_b"
        and selection.nonlethal is False
    )
    paused = _choose(game, second)
    assert paused.status is ResultStatus.PAUSED
    resolved = _choose(game, "keep")
    second_check = next(event.check for event in resolved.events if event.kind == "strike")
    assert second_check is not None and second_check.map_penalty == -4 and second_check.modifier == 3
    assert all(item.source != "nonlethal intent" for item in second_check.modifier_breakdown)


def test_same_type_kama_flurry_carries_unused_resistance_and_spends_weakness_once(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    setup = EncounterSetup(
        setup_id="test_kama_flurry_same_type_defense",
        name="Kama Flurry same-type defense",
        width=4,
        height=3,
        placements=(
            CreaturePlacement("monk", MONK.definition_id, "Monk", "blue", Position(1, 1)),
            CreaturePlacement("ward", "warpriest_c_typed_defense_test_grant", "Ward", "red", Position(2, 1)),
        ),
    )
    monkeypatch.setattr(content, "_STAGED_SETUPS", content._STAGED_SETUPS | {setup.setup_id: setup})
    # Both critical kama hits roll 1 on d6: 6 raw after doubling. The ward's
    # +3 weakness and resistance 2 apply once to the combined Flurry: 7 then
    # 6, rather than repeating the ward against each individual Strike.
    game = Encounter.start(setup, rolls=(20, 1, 20, 1, 20, 1))
    _settle_initiative(game)
    first = game.execute(FlurryOfBlows(PairedStrikeSelection("ward", "kama")))
    assert first.status is ResultStatus.PAUSED
    first = _choose(game, "keep")
    assert next(actor for actor in game.inspect().actors if actor.actor_id == "ward").hp == 10
    second_choice = game.inspect().choice
    assert second_choice is not None
    second = _choose(game, second_choice.options[0].option_id)
    assert second.status is ResultStatus.PAUSED
    second = _choose(game, "keep")
    assert next(actor for actor in game.inspect().actors if actor.actor_id == "ward").hp == 4


def test_terminal_plays_staged_kama_flurry_to_completion() -> None:
    transcript = BoundedTranscript()
    menu = {"text": "", "prompt": ""}

    def output(line: str) -> None:
        transcript.append(line)
        if line.startswith("1. "):
            menu["text"] = line
        if line.endswith(":"):
            menu["prompt"] = line

    def menu_number(label: str) -> str:
        for row in menu["text"].splitlines():
            if ". " in row and row.split(". ", 1)[1] == label:
                return row.split(". ", 1)[0]
        raise AssertionError(f"missing terminal menu item {label!r}: {menu['text']!r}")

    def script(prompt: str) -> str:
        if prompt == "Choice:":
            return menu_number("Flurry of Blows") if "Flurry of Blows" in menu["text"] else menu_number("Quit")
        if prompt == "Choice prompt action:":
            return "2"
        if prompt == "Choice option number:":
            return "2"  # Keep each Hero Point result.
        if prompt == "Weapon / attack number:":
            return "2"  # Fist is first; retain the accepted kama terminal path.
        if prompt in {"Kama target:", "Target number:"}:
            return "1"
        if prompt == "Damage intent:":
            return "1"
        raise AssertionError(f"unexpected terminal prompt: {prompt!r}")

    result = run_terminal(
        setup=content.get_setup("staged_monk_kama_flurry"),
        rolls=(20, 1, 1, 20, 6, 20, 6),
        input_fn=BoundedInput(lambda: script(menu["prompt"])),
        output_fn=output,
    )
    assert result == 0
    assert "Flurry of Blows" in "\n".join(transcript)


def test_terminal_plays_staged_fist_flurry_to_completion() -> None:
    transcript = BoundedTranscript()
    menu = {"text": "", "prompt": ""}

    def output(line: str) -> None:
        transcript.append(line)
        if line.startswith("1. "):
            menu["text"] = line
        if line.endswith(":"):
            menu["prompt"] = line

    def menu_number(label: str) -> str:
        for row in menu["text"].splitlines():
            if ". " in row and row.split(". ", 1)[1] == label:
                return row.split(". ", 1)[0]
        raise AssertionError(f"missing terminal menu item {label!r}: {menu['text']!r}")

    def script(prompt: str) -> str:
        if prompt == "Choice:":
            return menu_number("Flurry of Blows") if "Flurry of Blows" in menu["text"] else menu_number("Quit")
        if prompt == "Choice prompt action:":
            return "2"
        if prompt == "Choice option number:":
            return "1"
        if prompt == "Weapon / attack number:":
            return "1"
        if prompt in {"Fist target:", "Target number:"}:
            return "1"
        if prompt == "Damage intent:":
            return "2"  # Explicit lethal intent, exempted by Powerful Fist.
        raise AssertionError(f"unexpected terminal prompt: {prompt!r}")

    result = run_terminal(
        setup=content.get_setup("staged_monk_kama_flurry"),
        rolls=(20, 1, 1, 20, 6, 20, 6),
        input_fn=BoundedInput(lambda: script(menu["prompt"])),
        output_fn=output,
    )
    assert result == 0
    assert "Flurry of Blows" in "\n".join(transcript)


def test_terminal_plays_staged_precision_ranger_hunt_then_hunted_shot() -> None:
    transcript = BoundedTranscript(max_lines=300, max_chars=50_000)
    menu = {"text": "", "prompt": "", "hunted": False}

    def output(line: str) -> None:
        transcript.append(line)
        if line.startswith("1. "):
            menu["text"] = line
        if line.endswith(":"):
            menu["prompt"] = line

    def menu_number(label: str) -> str:
        for row in menu["text"].splitlines():
            if ". " in row and row.split(". ", 1)[1] == label:
                return row.split(". ", 1)[0]
        raise AssertionError(f"missing terminal menu item {label!r}: {menu['text']!r}")

    def script(prompt: str) -> str:
        if prompt == "Choice:":
            if "Hunt Prey" in menu["text"] and not menu["hunted"]:
                menu["hunted"] = True
                return menu_number("Hunt Prey")
            if "Hunted Shot" in menu["text"]:
                return menu_number("Hunted Shot")
            return menu_number("Quit")
        if prompt == "Choice prompt action:":
            return "2"
        if prompt == "Choice option number:":
            return "1"
        if prompt in {"Hunt Prey target:", "Shortbow target:", "Target number:"}:
            return "1"
        if prompt == "Weapon / attack number:":
            return "1"
        if prompt == "Damage intent:":
            return "1"
        raise AssertionError(f"unexpected terminal prompt: {prompt!r}")

    assert run_terminal(
        setup=content.get_setup("staged_ranger_precision_bow"),
        rolls=(20, 1, 1, 10, 4, 3, 10, 5),
        input_fn=BoundedInput(lambda: script(menu["prompt"])),
        output_fn=output,
    ) == 0
    rendered = "\n".join(transcript)
    assert "Hunt Prey" in rendered and "Hunted Shot" in rendered


def test_kama_trip_critical_failure_saves_drop_or_prone_choice(tmp_path: Path) -> None:
    # The kama's Trip trait permits Athletics without a free hand. On a
    # critical failure, its wielder can drop it to take a failure instead.
    game = Encounter.start(content.get_setup("staged_monk_kama_flurry"), rolls=(20, 1, 1, 1))
    _settle_initiative(game)
    paused = game.execute(Trip("guard_dog_a", maneuver_item_id="kama"))
    assert paused.status is ResultStatus.PAUSED
    saved = tmp_path / "saved-kama-trip-hero.json"
    game.save(saved)
    game = Encounter.load(saved)
    resolved = _choose(game, "keep")
    assert any(event.kind == "trip_check" and event.check is not None for event in resolved.events)
    choice = game.inspect().choice
    assert choice is not None and choice.kind == "family_action"
    dropped = _choose(game, "drop_weapon")
    monk = next(actor for actor in game.inspect().actors if actor.actor_id == "monk")
    assert monk.held_items == () and not monk.prone
    assert any(event.kind == "release" for event in dropped.events)


def test_kama_trip_critical_failure_can_accept_prone_after_save(tmp_path: Path) -> None:
    game = Encounter.start(content.get_setup("staged_monk_kama_flurry"), rolls=(20, 1, 1, 1))
    _settle_initiative(game)
    assert game.execute(Trip("guard_dog_a", maneuver_item_id="kama")).status is ResultStatus.PAUSED
    _choose(game, "keep")
    choice = game.inspect().choice
    assert choice is not None and choice.kind == "family_action"
    save_path = tmp_path / "saved-kama-trip-critical-failure.json"
    game.save(save_path)
    restored = Encounter.load(save_path)
    accepted = _choose(restored, "accept_critical_failure")
    monk = next(actor for actor in restored.inspect().actors if actor.actor_id == "monk")
    assert accepted.status is ResultStatus.COMPLETED
    assert monk.held_items == ("kama",) and monk.prone


def test_quick_jump_rejects_nonstraight_path_without_spending_action() -> None:
    game = Encounter.start(content.get_setup("staged_monk_kama_flurry"), rolls=(20, 1, 1))
    _settle_initiative(game)
    before = game.inspect()
    rejected = game.execute(QuickJump((Position(2, 2),)))
    assert rejected.status is ResultStatus.REJECTED
    assert game.inspect() == before


def test_quick_jump_is_one_action_saved_long_jump_with_normal_movement(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Quick Jump removes Long Jump's initial Stride and 10-foot-runup failure.
    # A success permits 15 feet, consuming one action and using normal movement.
    setup = EncounterSetup(
        setup_id="test_monk_quick_jump",
        name="Monk Quick Jump",
        width=7,
        height=3,
        placements=(
            CreaturePlacement("monk", MONK.definition_id, "Monk", "blue", Position(1, 1)),
            CreaturePlacement("dog", "guard_dog_mc2924", "Dog", "red", Position(6, 0)),
        ),
    )
    monkeypatch.setattr(content, "_STAGED_SETUPS", content._STAGED_SETUPS | {setup.setup_id: setup})
    game = Encounter.start(setup, rolls=(20, 1, 10))
    _settle_initiative(game)
    paused = game.execute(QuickJump((Position(2, 1), Position(3, 1), Position(4, 1))))
    assert paused.status is ResultStatus.PAUSED
    saved = tmp_path / "saved-quick-jump-hero.json"
    game.save(saved)
    game = Encounter.load(saved)
    resolved = _choose(game, "keep")
    monk = next(actor for actor in game.inspect().actors if actor.actor_id == "monk")
    assert monk.position == Position(4, 1) and monk.actions_remaining == 2
    check = next(event.check for event in resolved.events if event.kind == "quick_jump_check")
    assert check is not None and check.dc == 15 and check.degree.name == "SUCCESS"


def test_quick_jump_saved_reaction_decline_resumes_remaining_path(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    setup = EncounterSetup(
        setup_id="test_monk_quick_jump_reaction",
        name="Monk Quick Jump reaction",
        width=7,
        height=5,
        placements=(
            CreaturePlacement("monk", MONK.definition_id, "Monk", "blue", Position(4, 1)),
            CreaturePlacement("fighter", "fighter_m_level_1", "Fighter", "red", Position(5, 1)),
        ),
    )
    monkeypatch.setattr(content, "_STAGED_SETUPS", content._STAGED_SETUPS | {setup.setup_id: setup})
    game = Encounter.start(setup, rolls=(20, 1, 10))
    _settle_initiative(game)
    paused = game.execute(QuickJump((Position(4, 2), Position(4, 3))))
    assert paused.status is ResultStatus.PAUSED
    reaction = _choose(game, "keep")
    choice = game.inspect().choice
    assert reaction.status is ResultStatus.PAUSED
    assert choice is not None and choice.kind == "reaction" and choice.owner_actor_id == "fighter"
    save_path = tmp_path / "saved-quick-jump-reaction.json"
    game.save(save_path)
    restored = Encounter.load(save_path)
    finished = _choose(restored, "decline")
    monk = next(actor for actor in restored.inspect().actors if actor.actor_id == "monk")
    assert finished.status is ResultStatus.COMPLETED
    assert monk.position == Position(4, 3)
    assert sum(event.kind == "reaction_declined" for event in finished.events) == 1


def test_quick_jump_critical_failure_leaps_then_falls_prone(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    setup = EncounterSetup(
        setup_id="test_monk_quick_jump_failure",
        name="Monk Quick Jump failure",
        width=4,
        height=3,
        placements=(
            CreaturePlacement("monk", MONK.definition_id, "Monk", "blue", Position(1, 1)),
            CreaturePlacement("dog", "guard_dog_mc2924", "Dog", "red", Position(3, 0)),
        ),
    )
    monkeypatch.setattr(content, "_STAGED_SETUPS", content._STAGED_SETUPS | {setup.setup_id: setup})
    game = Encounter.start(setup, rolls=(20, 1, 1))
    _settle_initiative(game)
    paused = game.execute(QuickJump((Position(2, 1),)))
    assert paused.status is ResultStatus.PAUSED
    _choose(game, "keep")
    monk = next(actor for actor in game.inspect().actors if actor.actor_id == "monk")
    # Critical failure retains Long Jump's ordinary horizontal Leap before
    # applying prone. The chosen path is one square, so it ends after 5 feet.
    assert monk.position == Position(2, 1) and monk.prone


def test_terminal_plays_monk_quick_jump() -> None:
    transcript = BoundedTranscript()
    menu = {"text": "", "prompt": "", "jumped": False}

    def output(line: str) -> None:
        transcript.append(line)
        if line.startswith("1. "):
            menu["text"] = line
        if line.endswith(":"):
            menu["prompt"] = line

    def menu_number(label: str) -> str:
        for row in menu["text"].splitlines():
            if ". " in row and row.split(". ", 1)[1] == label:
                return row.split(". ", 1)[0]
        raise AssertionError(f"missing terminal menu item {label!r}: {menu['text']!r}")

    def script(prompt: str) -> str:
        if prompt == "Choice:":
            if "Quick Jump" in menu["text"] and not menu["jumped"]:
                menu["jumped"] = True
                return menu_number("Quick Jump")
            return menu_number("Quit")
        if prompt == "Quick Jump path, in order (for example B2 C2 D2):":
            return "A2"
        if prompt == "Choice option number:":
            return "2"  # Keep the Athletics check rather than rerolling it.
        if prompt == "Choice prompt action:":
            return "2"  # Keep the Athletics check.
        raise AssertionError(f"unexpected terminal prompt: {prompt!r}")

    assert run_terminal(
        setup=content.get_setup("staged_monk_kama_flurry"),
        rolls=(20, 1, 1, 10),
        input_fn=BoundedInput(lambda: script(menu["prompt"])),
        output_fn=output,
    ) == 0
    assert "Quick Jump" in "\n".join(transcript)


def test_terminal_plays_monk_kama_trip() -> None:
    transcript = BoundedTranscript()
    menu = {"text": "", "prompt": "", "tripped": False}

    def output(line: str) -> None:
        transcript.append(line)
        if line.startswith("1. "):
            menu["text"] = line
        if line.endswith(":"):
            menu["prompt"] = line

    def menu_number(label: str) -> str:
        for row in menu["text"].splitlines():
            if ". " in row and row.split(". ", 1)[1] == label:
                return row.split(". ", 1)[0]
        raise AssertionError(f"missing terminal menu item {label!r}: {menu['text']!r}")

    def script(prompt: str) -> str:
        if prompt == "Choice:":
            if "Trip" in menu["text"] and not menu["tripped"]:
                menu["tripped"] = True
                return menu_number("Trip")
            return menu_number("Quit")
        if prompt in {"Trip target:", "Target number:"}:
            return "1"
        if prompt == "Maneuver option:":
            return "2"  # Use the held kama rather than a free hand.
        if prompt == "Choice prompt action:":
            return "2"
        if prompt == "Choice option number:":
            return "2"  # Keep the Athletics check.
        raise AssertionError(f"unexpected terminal prompt: {prompt!r}")

    assert run_terminal(
        setup=content.get_setup("staged_monk_kama_flurry"),
        rolls=(20, 1, 1, 20),
        input_fn=BoundedInput(lambda: script(menu["prompt"])),
        output_fn=output,
    ) == 0
    rendered = "\n".join(transcript)
    assert "Trip" in rendered and "Held item: kama" in rendered
