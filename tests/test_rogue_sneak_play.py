"""Source-informed public Thief play and damage-boundary checks.

The selected Rogue slice follows the Remaster rules for Sneak Attack and
Surprise Attack ([Rogue](https://2e.aonprd.com/Classes.aspx?ID=37),
[precision damage](https://2e.aonprd.com/Rules.aspx?ID=2308)), Thief's
Dexterity damage ([Thief](https://2e.aonprd.com/Rackets.aspx?ID=9)),
Nimble Dodge ([Nimble Dodge](https://2e.aonprd.com/Feats.aspx?ID=4916)),
and conditions ([Clumsy](https://2e.aonprd.com/Conditions.aspx?ID=61),
[Enfeebled](https://2e.aonprd.com/Conditions.aspx?ID=71),
[Frightened](https://2e.aonprd.com/Conditions.aspx?ID=76)).
"""

from __future__ import annotations

from pathlib import Path

from pf2e.checks import Modifier, combine_modifiers
from pf2e.conditions import CheckContext, ConditionValue, condition_modifiers
from pf2e.content import get_definition, get_setup
from pf2e.damage import (
    DamageDefense,
    DamageGroup,
    DamageTerm,
    apply_damage_defenses,
    roll_damage_terms,
)
from pf2e.encounter import Encounter
from pf2e.model import EndTurn, ResultStatus, Strike
from pf2e.rogue import RogueRacket, thief_damage_attribute, thief_damage_modifier
from pf2e.skill_actions import Demoralize, Feint


def _choose(game: Encounter, option_id: str):
    choice = game.inspect().choice
    assert choice is not None
    assert option_id in {option.option_id for option in choice.options}
    return game.choose(choice.choice_id, option_id, choice.owner_actor_id)


def _keep_pending(game: Encounter):
    """Resolve one visible Hero or family choice without hiding its existence."""
    choice = game.inspect().choice
    assert choice is not None
    assert any(option.option_id == "keep" for option in choice.options)
    return _choose(game, "keep")


def _damage(result):
    damage = next((event.damage for event in result.events if event.damage is not None), None)
    assert damage is not None
    return damage


def _keep_initiative(game: Encounter) -> None:
    while game.inspect().choice is not None:
        choice = game.inspect().choice
        assert choice is not None and choice.kind == "initiative_hero_reroll"
        _choose(game, "keep")


def test_thief_repeated_sneak_attack_and_critical_doubling_on_qualifying_hits() -> None:
    """A Thief can add precision on each qualifying hit in one turn."""
    game = Encounter.start(
        get_setup("rogue_thief_vs_fighter_fixture"),
        # Initiative, Feint, first Strike, and critical second Strike.
        rolls=(20, 1, 20, 12, 1, 1, 20, 1, 1),
    )
    _keep_initiative(game)

    feint = game.execute(Feint("fighter_m"))
    assert feint.status is ResultStatus.PAUSED
    assert game.inspect().choice is not None and game.inspect().choice.kind == "family_action"
    feint = _keep_pending(game)
    assert any(event.kind == "feint_exposure" for event in feint.events)

    first = game.execute(Strike("fighter_m", attack_id="shortsword"))
    assert first.status is ResultStatus.PAUSED
    assert first.inspection.choice is not None
    first = _keep_pending(game)
    first_damage = _damage(first)

    second = game.execute(Strike("fighter_m", attack_id="shortsword"))
    assert second.status is ResultStatus.PAUSED
    assert second.inspection.choice is not None
    second = _keep_pending(game)
    second_damage = _damage(second)

    assert [component.source for component in first_damage.components] == [
        "shortsword",
        "rogue_sneak_attack",
    ]
    assert [component.source for component in second_damage.components] == [
        "shortsword",
        "rogue_sneak_attack",
    ]
    assert second_damage.components[1].tags == frozenset({"precision"})
    assert second_damage.components[1].amount == 2  # 1d6 precision doubled on a critical.
    assert second_damage.multiplier == 2
    assert second.inspection.turn_actor_id == "fighter_m"
    assert next(actor for actor in second.inspection.actors if actor.actor_id == "fighter_m").hp == 3


def test_thief_feint_opening_is_consumed_and_ordinary_hit_has_no_sneak_attack(
    tmp_path: Path,
) -> None:
    game = Encounter.start(
        get_setup("rogue_thief_vs_fighter_fixture"),
        # Initiative, successful Feint, first Strike, ordinary second Strike.
        rolls=(20, 1, 15, 12, 1, 1, 15, 1),
    )
    _keep_initiative(game)

    feint = game.execute(Feint("fighter_m"))
    assert feint.status is ResultStatus.PAUSED
    _keep_pending(game)

    first = game.execute(Strike("fighter_m", attack_id="shortsword"))
    assert first.status is ResultStatus.PAUSED
    first = _keep_pending(game)
    first_check = next(event.check for event in first.events if event.kind == "strike")
    assert first_check is not None and first_check.dc == 16
    assert [component.source for component in _damage(first).components] == [
        "shortsword",
        "rogue_sneak_attack",
    ]

    # Saving while the Rogue's Hero choice is visible proves the Feint and
    # one-attack exposure survive persistence as a single continuation.
    second = game.execute(Strike("fighter_m", attack_id="shortsword"))
    assert second.status is ResultStatus.PAUSED
    pending = second.inspection.choice
    assert pending is not None and pending.kind == "attack_hero_reroll"
    path = tmp_path / "rogue-feint-hero.json"
    game.save(path)
    restored = Encounter.load(path)
    assert restored.inspect() == second.inspection
    second = _keep_pending(restored)
    second_check = next(event.check for event in second.events if event.kind == "strike")
    assert second_check is not None and second_check.dc == 18
    assert [component.source for component in _damage(second).components] == ["shortsword"]


def test_canonical_deception_fight_expires_surprise_and_saves_nimble_dodge(
    tmp_path: Path,
) -> None:
    """Complete the healthy public fight through the enemy turn and round two."""
    game = Encounter.start(
        get_setup("rogue_thief_vs_guard_dog"),
        # Initiative, first Strike, dog attack, round-two expiry probe,
        # Feint and Strike.
        rolls=(20, 1, 12, 1, 1, 1, 1, 15, 12, 1, 1),
    )
    initial = game.inspect().choice
    assert initial is not None and initial.kind == "initiative_hero_reroll"
    assert initial.details[0] == "Initiative: Deception (observed social confrontation)."
    _choose(game, "keep")

    opening = game.execute(Strike("guard_dog", attack_id="shortsword"))
    assert opening.status is ResultStatus.PAUSED
    opening_check = next(event.check for event in opening.events if event.kind == "strike")
    assert opening_check is not None and opening_check.dc == 13  # Surprise Attack off-guard.
    opening = _keep_pending(game)
    assert [component.source for component in _damage(opening).components] == [
        "shortsword",
        "rogue_sneak_attack",
    ]

    assert game.execute(EndTurn()).status is ResultStatus.COMPLETED
    dog_attack = game.execute(Strike("thief_rogue", attack_id="jaws"))
    assert dog_attack.status is ResultStatus.PAUSED
    nimble = dog_attack.inspection.choice
    assert nimble is not None and nimble.kind == "nimble_dodge"
    path = tmp_path / "rogue-nimble.json"
    game.save(path)
    restored = Encounter.load(path)
    assert restored.inspect() == dog_attack.inspection
    dog_attack = _choose(restored, "use")
    dog_check = next(event.check for event in dog_attack.events if event.kind == "strike")
    assert dog_check is not None and dog_check.dc == 20
    rogue = next(actor for actor in restored.inspect().actors if actor.actor_id == "thief_rogue")
    assert rogue.reaction_available is False
    assert restored.execute(EndTurn()).status is ResultStatus.COMPLETED

    expired_probe = restored.execute(Strike("guard_dog", attack_id="shortsword"))
    assert expired_probe.status is ResultStatus.PAUSED
    expired_check = next(event.check for event in expired_probe.events if event.kind == "strike")
    assert expired_check is not None and expired_check.dc == 15
    expired_probe = _keep_pending(restored)
    assert not any(event.damage is not None for event in expired_probe.events)

    feint = restored.execute(Feint("guard_dog"))
    assert feint.status is ResultStatus.PAUSED
    feint = _keep_pending(restored)
    assert any(event.kind == "feint_exposure" for event in feint.events)

    later = restored.execute(Strike("guard_dog", attack_id="shortsword"))
    assert later.status is ResultStatus.PAUSED
    later_check = next(event.check for event in later.events if event.kind == "strike")
    assert later_check is not None and later_check.dc == 13  # Feint restores off-guard after Surprise expires.
    later = _keep_pending(restored)
    assert [component.source for component in _damage(later).components] == [
        "shortsword",
        "rogue_sneak_attack",
    ]
    assert later.status is ResultStatus.COMPLETED
    assert later.inspection.winner_team == "blue"
    assert not later.inspection.in_progress


def test_thief_frightened_penalizes_attack_but_not_dexterity_damage() -> None:
    """The condition belongs to the Rogue and leaves the damage modifier intact."""
    game = Encounter.start(
        get_setup("rogue_thief_vs_fighter_fixture"),
        # Fighter wins, critically Demoralizes, then Rogue makes one Strike.
        rolls=(1, 20, 20, 15, 1),
    )
    _keep_initiative(game)
    demoralize = game.execute(Demoralize("thief_rogue", spoken_language="Common"))
    assert demoralize.status is ResultStatus.PAUSED
    demoralize = _keep_pending(game)
    assert any(event.kind == "condition_applied" for event in demoralize.events)
    assert game.execute(EndTurn()).status is ResultStatus.COMPLETED

    strike = game.execute(Strike("fighter_m", attack_id="shortsword"))
    assert strike.status is ResultStatus.PAUSED
    check = next(event.check for event in strike.events if event.kind == "strike")
    assert check is not None and check.modifier == 5  # +7 attack, frightened 2 penalty.
    strike = _keep_pending(game)
    damage = _damage(strike)
    assert [component.source for component in damage.components] == ["shortsword"]
    assert damage.components[0].modifier == 4  # Frightened never penalizes damage rolls.


def test_thief_damage_conditions_apply_clumsy_to_dexterity_and_not_enfeebled() -> None:
    """No admitted fixture inflicts Clumsy, so this stays a pure tagged projection check."""
    definition = get_definition("rogue_thief_warrior_level_1")
    shortsword = next(attack for attack in definition.attacks if attack.attack_id == "shortsword")
    assert thief_damage_attribute(shortsword, racket=RogueRacket.THIEF) == "dexterity"
    base_damage = thief_damage_modifier(
        shortsword,
        racket=RogueRacket.THIEF,
        strength_modifier=2,
        dexterity_modifier=4,
    )
    assert base_damage == 4

    clumsy = condition_modifiers(
        (ConditionValue("clumsy", 2, "test:clumsy"),),
        CheckContext("damage", "dexterity", shortsword.traits),
    )
    enfeebled = condition_modifiers(
        (ConditionValue("enfeebled", 2, "test:enfeebled"),),
        CheckContext("damage", "dexterity", shortsword.traits),
    )
    frightened = condition_modifiers(
        (ConditionValue("frightened", 2, "test:frightened"),),
        CheckContext("damage", "dexterity", shortsword.traits),
    )
    assert clumsy == (Modifier(-2, "status", "condition:clumsy:test:clumsy"),)
    assert enfeebled == ()
    assert frightened == ()

    clumsy_damage = roll_damage_terms(
        (DamageTerm("shortsword", "piercing", (6,), modifier=base_damage + combine_modifiers(clumsy)),),
        lambda _sides: 1,
    )
    enfeebled_damage = roll_damage_terms(
        (DamageTerm("shortsword", "piercing", (6,), modifier=base_damage + combine_modifiers(enfeebled)),),
        lambda _sides: 1,
    )
    assert clumsy_damage.total == 3  # 1d6 + 4 - Clumsy 2.
    assert enfeebled_damage.total == 5  # Thief's Dexterity damage ignores Enfeebled.


def test_sneak_attack_precision_immunity_and_one_effect_physical_resistance() -> None:
    """The separate precision term is removable while resistance sees the whole attack."""
    result = roll_damage_terms(
        (
            DamageTerm("shortsword", "piercing", (6,), modifier=4),
            DamageTerm(
                "rogue_sneak_attack",
                "piercing",
                (6,),
                tags=frozenset({"precision"}),
            ),
        ),
        lambda _sides: 1,
    )
    group = DamageGroup("thief-strike", (result,), "strike", frozenset({"attack", "melee"}))
    immunity = apply_damage_defenses(
        group,
        (DamageDefense("immunity", "precision", source="precision immunity"),),
    )
    assert immunity.total == 5
    assert immunity.results[0].components[1].amount == 0

    resistance = apply_damage_defenses(
        group,
        (DamageDefense("resistance", "physical", 2, source="physical resistance"),),
    )
    assert resistance.total == 4
    assert [component.amount for component in resistance.results[0].components] == [3, 1]

    combined = apply_damage_defenses(
        group,
        (
            DamageDefense("immunity", "precision", source="precision immunity"),
            DamageDefense("resistance", "physical", 2, source="physical resistance"),
        ),
    )
    assert combined.total == 3
    assert [component.amount for component in combined.results[0].components] == [3, 0]
