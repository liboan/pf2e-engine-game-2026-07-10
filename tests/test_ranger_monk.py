"""Source-backed Ranger and Monk rules for the level-1 class slice."""

from __future__ import annotations

import pytest
from dataclasses import replace
from types import SimpleNamespace

from pf2e.damage import DamageTerm
from pf2e.monk import is_flurry_strike, powerful_fist_removes_lethal_penalty
from pf2e.model import Event, HuntedPreyState, PairedStrikeContinuation, PairedStrikeSelection, Position
from pf2e.paired_strikes import _decode_selection, _encode_selection, after_subordinate_strike, second_strike_options
from pf2e.ranger import (
    HunterEdge,
    flurry_map_penalty,
    hunt_prey_skill_modifier,
    hunted_prey_range_penalty,
    outwit_ac_modifier,
    outwit_skill_modifier,
    precision_damage_term,
)
from pf2e.ranger_monk_content import MONK, RANGER_DEFINITIONS


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
    assert MONK.level == 1
    assert {"flurry_of_blows", "powerful_fist", "monastic_weaponry"} <= set(MONK.abilities)
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
        selections=(PairedStrikeSelection("dog", "fist"),),
        outcomes=(object(),),
        next_index=1,
        stage="choose_second",
    )

    choices = tuple(_decode_selection(option.option_id) for option in second_strike_options(context, continuation))
    assert {choice.attack_id for choice in choices if choice is not None} == {"fist", "kama"}
    assert all(choice is not None and choice.damage_type is None for choice in choices)
    assert any(choice is not None and choice.attack_id == "fist" and choice.nonlethal is None for choice in choices)
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
        selections=(PairedStrikeSelection("dog", "fist"),),
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
    assert len(second_choice_ids) == 4
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
