from __future__ import annotations

import pytest

from pf2e.checks import DegreeOfSuccess
from pf2e.damage import roll_damage_terms
from pf2e.model import AttackDefinition
from pf2e.rogue import (
    OffGuardExpiry,
    OffGuardScope,
    RogueRacket,
    WeaponCategory,
    is_thrown_melee_weapon,
    mastermind_recall_knowledge_grant,
    nimble_dodge_modifier,
    rogue_racket,
    ruffian_critical_specialization,
    ruffian_weapon_is_eligible,
    scoundrel_feint_benefits,
    sneak_attack_damage_term,
    sneak_attack_is_eligible,
    surprise_attack_applies,
    thief_damage_attribute,
    thief_damage_modifier,
)
from pf2e.rogue_content import (
    ROGUE_DEFINITIONS,
    ROGUE_MASTERMIND,
    ROGUE_RUFFIAN,
    ROGUE_SCOUNDREL,
    ROGUE_THIEF,
    ROGUE_WEAPON_FACTS,
)


def _attack(
    attack_id: str,
    traits: set[str],
    *,
    die: int = 6,
    item_id: str | None = "weapon",
    deadly_die: int | None = None,
) -> AttackDefinition:
    return AttackDefinition(
        attack_id=attack_id,
        name=attack_id,
        modifier=5,
        reach_ft=5 if "melee" in traits else 0,
        traits=frozenset(traits),
        damage_type="piercing",
        damage_dice=(die,),
        damage_modifier=1,
        item_id=item_id,
        deadly_die=deadly_die,
    )


def test_core_sneak_attack_weapon_eligibility_and_precision_term() -> None:
    finesse_melee = _attack("finesse", {"attack", "melee", "finesse", "weapon"}, die=6)
    plain_melee = _attack("plain", {"attack", "melee", "weapon"}, die=6)
    ranged_weapon = _attack("bow", {"attack", "ranged", "weapon"}, die=6)
    ranged_unarmed = _attack("seed", {"attack", "ranged", "unarmed"}, die=4, item_id=None)
    thrown_dagger = _attack(
        "dagger_thrown", {"attack", "ranged", "thrown", "agile", "finesse", "weapon"}, die=4
    )

    assert sneak_attack_is_eligible(
        finesse_melee,
        target_is_off_guard=True,
        racket=RogueRacket.THIEF,
        thrown_melee_weapon=False,
    )
    assert not sneak_attack_is_eligible(
        plain_melee,
        target_is_off_guard=True,
        racket=RogueRacket.THIEF,
        thrown_melee_weapon=False,
    )
    assert sneak_attack_is_eligible(
        ranged_weapon,
        target_is_off_guard=True,
        racket=RogueRacket.THIEF,
        thrown_melee_weapon=False,
    )
    assert sneak_attack_is_eligible(
        ranged_unarmed,
        target_is_off_guard=True,
        racket=RogueRacket.THIEF,
        thrown_melee_weapon=False,
    )
    assert sneak_attack_is_eligible(
        thrown_dagger,
        target_is_off_guard=True,
        racket=RogueRacket.THIEF,
        thrown_melee_weapon=True,
    )
    assert not sneak_attack_is_eligible(
        _attack("thrown_club", {"attack", "ranged", "thrown", "weapon"}, die=6),
        target_is_off_guard=True,
        racket=RogueRacket.THIEF,
        thrown_melee_weapon=True,
    )
    assert not sneak_attack_is_eligible(
        finesse_melee,
        target_is_off_guard=False,
        racket=RogueRacket.THIEF,
        thrown_melee_weapon=False,
    )

    term = sneak_attack_damage_term(
        finesse_melee,
        damage_type="slashing",
        target_is_off_guard=True,
        racket=RogueRacket.THIEF,
        thrown_melee_weapon=False,
    )
    assert term is not None
    assert term.source == "rogue_sneak_attack"
    assert term.damage_type == "slashing"
    assert term.dice == (6,)
    assert term.tags == frozenset({"precision"})
    assert term.critical_mode == "double"
    critical = roll_damage_terms((term,), lambda sides: 4, critical=True)
    assert critical.total == 8


def test_thrown_melee_fact_uses_matching_melee_profile() -> None:
    dagger = _attack("dagger", {"attack", "melee", "agile", "finesse", "thrown", "weapon"}, die=4, item_id="dagger")
    thrown = _attack("dagger_thrown", {"attack", "ranged", "agile", "finesse", "thrown", "weapon"}, die=4, item_id="dagger")
    dart = _attack("dart", {"attack", "ranged", "thrown", "weapon"}, die=4, item_id="dart")
    assert is_thrown_melee_weapon(thrown, (dagger, thrown))
    assert not is_thrown_melee_weapon(dart, (dart,))
    assert not is_thrown_melee_weapon(dagger, (dagger, thrown))


def test_ruffian_limits_use_adjusted_base_die_and_not_fatal_die() -> None:
    simple_d8 = _attack("simple_d8", {"attack", "melee", "weapon"}, die=8)
    simple_d10 = _attack("simple_d10", {"attack", "melee", "weapon"}, die=10)
    fatal_pick = _attack("fatal_pick", {"attack", "melee", "weapon", "fatal"}, die=6, deadly_die=10)
    martial_d6 = _attack("martial_d6", {"attack", "melee", "weapon"}, die=6)

    assert ruffian_weapon_is_eligible(simple_d8, weapon_category=WeaponCategory.SIMPLE)
    assert not ruffian_weapon_is_eligible(simple_d10, weapon_category=WeaponCategory.SIMPLE)
    assert ruffian_weapon_is_eligible(
        fatal_pick,
        weapon_category=WeaponCategory.MARTIAL,
        adjusted_weapon_die_sides=6,
    )
    assert not ruffian_weapon_is_eligible(
        martial_d6,
        weapon_category=WeaponCategory.MARTIAL,
        adjusted_weapon_die_sides=8,
    )
    assert sneak_attack_is_eligible(
        simple_d8,
        target_is_off_guard=True,
        racket=RogueRacket.RUFFIAN,
        weapon_category=WeaponCategory.SIMPLE,
        thrown_melee_weapon=False,
    )
    assert sneak_attack_is_eligible(
        _attack("fist", {"attack", "melee", "agile", "finesse", "unarmed"}, item_id=None),
        target_is_off_guard=True,
        racket=RogueRacket.RUFFIAN,
        weapon_category=WeaponCategory.SIMPLE,
        thrown_melee_weapon=False,
    )  # Ruffian does not remove the ordinary eligible-unarmed rule.


def test_surprise_attack_requires_rogue_round_one_initiative_and_unacted_target() -> None:
    facts = {
        "round_number": 1,
        "initiative_skill": "Stealth",
        "target_has_acted": False,
        "has_surprise_attack": True,
    }
    assert surprise_attack_applies(**facts)
    assert surprise_attack_applies(**(facts | {"initiative_skill": "deception"}))
    assert not surprise_attack_applies(**(facts | {"initiative_skill": "perception"}))
    assert not surprise_attack_applies(**(facts | {"round_number": 2}))
    assert not surprise_attack_applies(**(facts | {"target_has_acted": True}))
    assert not surprise_attack_applies(**(facts | {"has_surprise_attack": False}))


def test_mastermind_identification_is_explicit_and_has_two_expiries() -> None:
    assert mastermind_recall_knowledge_grant(
        DegreeOfSuccess.SUCCESS,
        identified_creature=False,
    ) is None
    assert mastermind_recall_knowledge_grant(
        DegreeOfSuccess.FAILURE,
        identified_creature=True,
    ) is None
    success = mastermind_recall_knowledge_grant(
        DegreeOfSuccess.SUCCESS,
        identified_creature=True,
    )
    critical = mastermind_recall_knowledge_grant(
        DegreeOfSuccess.CRITICAL_SUCCESS,
        identified_creature=True,
    )
    assert success is not None
    assert (success.scope, success.expiry) == (
        OffGuardScope.ROGUE_ATTACKS,
        OffGuardExpiry.ROGUE_NEXT_TURN_START,
    )
    assert critical is not None
    assert critical.expiry is OffGuardExpiry.SIXTY_SECONDS


def test_scoundrel_feint_scope_depends_on_degree_but_free_step_on_weapon() -> None:
    failed = scoundrel_feint_benefits(
        DegreeOfSuccess.FAILURE,
        wielding_agile_or_finesse_melee_weapon=True,
    )
    success = scoundrel_feint_benefits(
        DegreeOfSuccess.SUCCESS,
        wielding_agile_or_finesse_melee_weapon=True,
    )
    critical = scoundrel_feint_benefits(
        DegreeOfSuccess.CRITICAL_SUCCESS,
        wielding_agile_or_finesse_melee_weapon=False,
    )
    assert failed.off_guard is None and failed.can_free_step
    assert success.off_guard is not None
    assert success.off_guard.scope is OffGuardScope.ROGUE_MELEE_ATTACKS
    assert success.off_guard.expiry is OffGuardExpiry.ROGUE_NEXT_TURN_END
    assert success.can_free_step
    assert critical.off_guard is not None
    assert critical.off_guard.scope is OffGuardScope.ALL_MELEE_ATTACKS
    assert not critical.can_free_step


def test_thief_damage_only_changes_finesse_melee_strikes() -> None:
    melee_dagger = _attack("dagger", {"attack", "melee", "finesse", "weapon"}, die=4)
    thrown_dagger = _attack("dagger_thrown", {"attack", "ranged", "thrown", "finesse", "weapon"}, die=4)
    plain_melee = _attack("club", {"attack", "melee", "weapon"}, die=6)
    assert thief_damage_attribute(melee_dagger, racket=RogueRacket.THIEF) == "dexterity"
    assert thief_damage_modifier(
        melee_dagger,
        racket=RogueRacket.THIEF,
        strength_modifier=1,
        dexterity_modifier=4,
    ) == 4
    assert thief_damage_attribute(thrown_dagger, racket=RogueRacket.THIEF) is None
    assert thief_damage_modifier(
        thrown_dagger,
        racket=RogueRacket.THIEF,
        strength_modifier=1,
        dexterity_modifier=4,
    ) == 1
    assert thief_damage_attribute(melee_dagger, racket=RogueRacket.RUFFIAN) is None
    assert thief_damage_attribute(plain_melee, racket=RogueRacket.THIEF) is None


def test_nimble_dodge_requires_all_trigger_and_requirement_facts() -> None:
    eligible = nimble_dodge_modifier(
        has_feat=True,
        reaction_available=True,
        attacker_visible=True,
        encumbered=False,
        attacker_targets_rogue_with_attack=True,
    )
    assert eligible is not None
    assert (eligible.amount, eligible.modifier_type, eligible.source) == (2, "circumstance", "Nimble Dodge")
    assert nimble_dodge_modifier(
        has_feat=True,
        reaction_available=False,
        attacker_visible=True,
        encumbered=False,
        attacker_targets_rogue_with_attack=True,
    ) is None
    assert nimble_dodge_modifier(
        has_feat=True,
        reaction_available=True,
        attacker_visible=True,
        encumbered=True,
        attacker_targets_rogue_with_attack=True,
    ) is None


def test_ruffian_critical_specialization_applies_actual_club_effect() -> None:
    club = _attack("club", {"attack", "melee", "weapon"}, die=6, item_id="club")
    effect = ruffian_critical_specialization(
        club,
        racket=RogueRacket.RUFFIAN,
        weapon_category=WeaponCategory.SIMPLE,
        weapon_group="club",
        target_is_off_guard=True,
        critical_hit=True,
    )
    assert effect is not None
    assert effect.weapon_group == "club"
    assert effect.maximum_distance_ft == 10
    assert effect.direction == "away_from_striker"
    assert effect.forced_movement
    assert ruffian_critical_specialization(
        club,
        racket=RogueRacket.RUFFIAN,
        weapon_category=WeaponCategory.SIMPLE,
        weapon_group="club",
        target_is_off_guard=False,
        critical_hit=True,
    ) is None
    with pytest.raises(NotImplementedError, match="critical specialization"):
        ruffian_critical_specialization(
            _attack("knife", {"attack", "melee", "weapon"}, die=4, item_id="knife"),
            racket=RogueRacket.RUFFIAN,
            weapon_category=WeaponCategory.SIMPLE,
            weapon_group="knife",
            target_is_off_guard=True,
            critical_hit=True,
        )


def test_all_four_level_one_racket_definitions_have_legal_class_trained_skills() -> None:
    definitions = (ROGUE_MASTERMIND, ROGUE_RUFFIAN, ROGUE_SCOUNDREL, ROGUE_THIEF)
    assert set(ROGUE_DEFINITIONS) == {definition.definition_id for definition in definitions}
    racket_skills = {
        RogueRacket.MASTERMIND: {"society", "arcana"},
        RogueRacket.RUFFIAN: {"intimidation"},
        RogueRacket.SCOUNDREL: {"deception", "diplomacy"},
        RogueRacket.THIEF: {"thievery"},
    }
    for definition in definitions:
        racket = rogue_racket(definition.abilities)
        assert racket is not None
        skills = {name: (rank, modifier) for name, rank, modifier in definition.skills}
        assert len(skills) == len(definition.skills)
        assert {"stealth", *racket_skills[racket]}.issubset(skills)
        assert all(rank == "trained" for rank, _modifier in skills.values())
        assert "sneak_attack" in definition.abilities
        assert "surprise_attack" in definition.abilities
        assert "deny_advantage" not in definition.abilities
        assert definition.class_name == "Rogue"
        assert definition.level == 1
        assert definition.ac == 14 + dict(definition.ability_modifiers)["dexterity"]
        assert definition.hp == 16 + dict(definition.ability_modifiers)["constitution"]
        proficiencies = dict(definition.proficiencies)
        assert proficiencies["perception"] == "expert"
        assert proficiencies["fortitude"] == "trained"
        assert proficiencies["reflex"] == proficiencies["will"] == "expert"
        assert proficiencies["simple_weapons"] == proficiencies["martial_weapons"] == "trained"
        assert proficiencies["unarmed_attacks"] == proficiencies["class_dc"] == "trained"
        assert "Nimble Dodge" in definition.feats
        assert "Intimidating Glare" in definition.feats

        int_modifier = dict(definition.ability_modifiers)["intelligence"]
        base_skill_count = 1 + len(racket_skills[racket]) + 7 + int_modifier
        assert len(skills) == base_skill_count + 4  # Human and custom background training.

    assert ROGUE_RUFFIAN.class_dc == 17
    assert "medium_armor" not in dict(ROGUE_MASTERMIND.proficiencies)
    assert dict(ROGUE_RUFFIAN.proficiencies)["medium_armor"] == "trained"
    assert ROGUE_WEAPON_FACTS["club"].category is WeaponCategory.SIMPLE
    assert ROGUE_WEAPON_FACTS["club"].group == "club"
    ruffian_club = next(attack for attack in ROGUE_RUFFIAN.attacks if attack.attack_id == "club")
    assert ruffian_club.damage_dice == (6,)


def test_thief_content_uses_dexterity_melee_and_strength_for_thrown_dagger() -> None:
    melee = next(attack for attack in ROGUE_THIEF.attacks if attack.attack_id == "dagger")
    thrown = next(attack for attack in ROGUE_THIEF.attacks if attack.attack_id == "dagger_thrown")
    assert melee.damage_attribute == "dexterity"
    assert melee.damage_modifier == 4
    assert thrown.damage_attribute == "strength"
    assert thrown.damage_modifier == 2
