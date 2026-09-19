from types import SimpleNamespace

from pf2e.checks import DegreeOfSuccess, resolve_check
from pf2e.model import EffectExpiration
from pf2e.skill_actions import (
    FeintAttackScope,
    FeintOffGuardEffect,
    consume_feint_off_guard_on_attack,
    feint_off_guard_applies,
    feint_outcome_from_check,
    _trained_skill_from_definition,
)
from pf2e.skill_content import FEINT


def _result(die, modifier, dc):
    return resolve_check(die, modifier, dc, traits=FEINT.traits)


def _outcome(die, modifier, dc, *, scoundrel=False, weapon=False):
    return feint_outcome_from_check(
        _result(die, modifier, dc),
        feinter_id="rogue",
        target_id="guard",
        effect_id="feint:rogue:guard:1",
        current_feinter_end_count=3,
        scoundrel=scoundrel,
        wielding_agile_or_finesse_melee_weapon=weapon,
    )


def _active(outcome):
    return outcome.off_guard_effects


def _query(effects, *, attacker="rogue", target="guard", traits=frozenset({"melee"}), ends=None):
    return feint_off_guard_applies(
        effects,
        attacker_id=attacker,
        target_id=target,
        attack_traits=traits,
        actor_end_counts=ends or {"rogue": 3},
    )


def test_feint_content_is_trained_deception_mental_action_against_perception_dc():
    assert (FEINT.action_id, FEINT.name, FEINT.action_cost) == ("feint", "Feint", 1)
    assert (FEINT.check_skill, FEINT.target_dc) == ("deception", "perception")
    assert FEINT.traits == frozenset({"mental"})
    assert FEINT.source_url == "https://2e.aonprd.com/Actions.aspx?ID=2390"


def test_standard_success_scopes_one_next_melee_attempt_and_consumes_it_once():
    outcome = _outcome(10, 0, 10)
    effect, = _active(outcome)

    assert outcome.check.degree is DegreeOfSuccess.SUCCESS
    assert effect.scope is FeintAttackScope.NEXT_MELEE_ATTACK
    assert effect.consume_on_next_attack
    assert effect.expiration == EffectExpiration("rogue", "end", 4)
    assert _query((effect,))
    assert not _query((effect,), attacker="ally")
    assert not _query((effect,), traits=frozenset({"ranged"}))
    assert not _query((effect,), ends={"rogue": 4})

    assert consume_feint_off_guard_on_attack(
        (effect,), attacker_id="ally", target_id="guard",
        attack_traits=frozenset({"melee"}), actor_end_counts={"rogue": 3},
    ) == (effect,)
    assert consume_feint_off_guard_on_attack(
        (effect,), attacker_id="rogue", target_id="other",
        attack_traits=frozenset({"melee"}), actor_end_counts={"rogue": 3},
    ) == (effect,)
    assert consume_feint_off_guard_on_attack(
        (effect,), attacker_id="rogue", target_id="guard",
        attack_traits=frozenset({"ranged"}), actor_end_counts={"rogue": 3},
    ) == (effect,)
    assert consume_feint_off_guard_on_attack(
        (effect,), attacker_id="rogue", target_id="guard",
        attack_traits=frozenset({"melee"}), actor_end_counts={"rogue": 3},
    ) == ()


def test_critical_success_allows_users_melee_attacks_until_the_next_turn_ends():
    outcome = _outcome(15, 0, 5)
    effect, = _active(outcome)

    assert outcome.check.degree is DegreeOfSuccess.CRITICAL_SUCCESS
    assert effect.scope is FeintAttackScope.NAMED_ATTACKER_MELEE
    assert not effect.consume_on_next_attack
    assert effect.expiration == EffectExpiration("rogue", "end", 5)
    assert _query((effect,))
    assert _query((effect,), ends={"rogue": 4})
    assert not _query((effect,), ends={"rogue": 5})
    assert consume_feint_off_guard_on_attack(
        (effect,), attacker_id="rogue", target_id="guard",
        attack_traits=frozenset({"melee"}), actor_end_counts={"rogue": 3},
    ) == (effect,)


def test_critical_failure_reverses_who_is_off_guard():
    outcome = _outcome(1, 0, 10)
    effect, = _active(outcome)

    assert outcome.check.degree is DegreeOfSuccess.CRITICAL_FAILURE
    assert effect.source_actor_id == "rogue"
    assert effect.target_actor_id == "rogue"
    assert effect.eligible_attacker_id == "guard"
    assert effect.scope is FeintAttackScope.NAMED_ATTACKER_MELEE
    assert effect.expiration == EffectExpiration("rogue", "end", 5)
    assert _query((effect,), attacker="guard", target="rogue")
    assert not _query((effect,), attacker="rogue", target="guard")
    assert not _query((effect,), attacker="guard", target="rogue", traits=frozenset({"ranged"}))


def test_scoundrel_success_replaces_one_attack_with_multiple_attacks_and_step():
    outcome = _outcome(10, 0, 10, scoundrel=True, weapon=True)
    effect, = _active(outcome)

    assert outcome.can_free_step
    assert effect.scope is FeintAttackScope.NAMED_ATTACKER_MELEE
    assert not effect.consume_on_next_attack
    assert effect.expiration == EffectExpiration("rogue", "end", 5)
    assert _query((effect,))
    assert _query((effect,), ends={"rogue": 4})
    assert not _query((effect,), attacker="ally")
    assert not _query((effect,), ends={"rogue": 5})


def test_scoundrel_critical_success_exposes_target_to_every_melee_attacker():
    outcome = _outcome(15, 0, 5, scoundrel=True)
    effect, = _active(outcome)

    assert not outcome.can_free_step
    assert effect.scope is FeintAttackScope.ANY_MELEE_ATTACKER
    assert effect.eligible_attacker_id is None
    assert _query((effect,), attacker="rogue")
    assert _query((effect,), attacker="ally")
    assert not _query((effect,), attacker="ally", traits=frozenset({"ranged"}))


def test_failure_has_no_exposure_but_scoundrel_weapon_still_allows_step():
    ordinary_failure = _outcome(10, 0, 11)
    scoundrel_failure = _outcome(10, 0, 11, scoundrel=True, weapon=True)

    assert ordinary_failure.check.degree is DegreeOfSuccess.FAILURE
    assert ordinary_failure.off_guard_effects == ()
    assert not ordinary_failure.can_free_step
    assert scoundrel_failure.off_guard_effects == ()
    assert scoundrel_failure.can_free_step


def test_skill_sheet_rank_is_the_authoritative_intimidation_training_fact():
    untrained = SimpleNamespace(definition=SimpleNamespace(skills=(("intimidation", None, 4),)))
    trained = SimpleNamespace(definition=SimpleNamespace(skills=(("intimidation", "trained", 4),)))
    expert = SimpleNamespace(definition=SimpleNamespace(skills=(("intimidation", "expert", 9),)))

    assert not _trained_skill_from_definition(untrained, "intimidation")
    assert _trained_skill_from_definition(trained, "intimidation")
    assert _trained_skill_from_definition(expert, "intimidation")
