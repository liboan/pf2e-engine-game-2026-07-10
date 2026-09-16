"""Focused public runtime checks for the admitted level-1 Thief Rogue."""

from __future__ import annotations

from pf2e.content import get_setup
from pf2e.encounter import Encounter
from pf2e.model import Cast, EndTurn, Position, ResultStatus, Strike, Stride
from pf2e.skill_actions import Demoralize, Trip


def _keep_start_choices(game: Encounter) -> None:
    while game.inspect().choice is not None:
        choice = game.inspect().choice
        assert choice is not None
        option = (
            "keep" if any(item.option_id == "keep" for item in choice.options)
            else "fighter_m" if any(item.option_id == "fighter_m" for item in choice.options)
            else choice.options[0].option_id
        )
        game.choose(choice.choice_id, option, choice.owner_actor_id)


def test_public_thief_uses_observed_deception_and_resolves_sneak_attack() -> None:
    game = Encounter.start(
        get_setup("rogue_thief_vs_guard_dog"),
        rolls=(20, 1, 15, 4, 3),
    )
    choice = game.inspect().choice
    assert choice is not None and choice.kind == "initiative_hero_reroll"
    assert "Deception (observed social confrontation)" in choice.details[0]
    game.choose(choice.choice_id, "keep")

    result = game.execute(Strike("guard_dog", attack_id="shortsword"))
    assert result.status is ResultStatus.PAUSED
    choice = result.inspection.choice
    assert choice is not None and choice.kind == "attack_hero_reroll"
    kept = game.choose(choice.choice_id, "keep")
    damage = next(event.damage for event in kept.events if event.damage is not None)
    assert damage is not None
    assert [component.source for component in damage.components] == [
        "shortsword", "rogue_sneak_attack",
    ]
    assert damage.components[1].tags == frozenset({"precision"})


def test_nimble_dodge_saved_choice_adds_ac_and_spends_shared_reaction(tmp_path) -> None:
    # The dog wins initiative, so the Rogue is the visible target of an
    # ordinary melee attack before the Rogue has taken its first turn.
    game = Encounter.start(
        get_setup("rogue_thief_vs_guard_dog"),
        rolls=(1, 20, 15, 4, 5),
    )
    choice = game.inspect().choice
    assert choice is not None
    game.choose(choice.choice_id, "keep")
    paused = game.execute(Strike("thief_rogue", attack_id="jaws"))
    assert paused.status is ResultStatus.PAUSED
    choice = paused.inspection.choice
    assert choice is not None and choice.kind == "nimble_dodge"

    path = tmp_path / "thief-nimble.json"
    game.save(path)
    restored = Encounter.load(path)
    assert restored.inspect() == paused.inspection
    result = restored.choose(choice.choice_id, "use")
    attack = next(event.check for event in result.events if event.kind == "strike")
    assert attack is not None
    assert attack.modifier == 6  # Guard Dog Jaws +6; Nimble is AC-only.
    assert attack.dc == 20  # Rogue AC 18 plus the +2 circumstance bonus.
    rogue = next(actor for actor in restored.inspect().actors if actor.actor_id == "thief_rogue")
    assert rogue.reaction_available is False


def test_nimble_use_then_attacker_hero_reroll_keeps_ac_and_does_not_redraw(tmp_path) -> None:
    game = Encounter.start(
        get_setup("rogue_thief_vs_fighter_fixture"),
        # Rogue initiative, Fighter initiative, Fighter attack, Hero reroll,
        # and longsword damage. Choices themselves never consume a d20.
        rolls=(1, 20, 10, 15, 4),
    )
    _keep_start_choices(game)
    paused = game.execute(Strike("thief_rogue", attack_id="longsword"))
    nimble = paused.inspection.choice
    assert nimble is not None and nimble.kind == "nimble_dodge"

    path = tmp_path / "thief-nimble-hero.json"
    game.save(path)
    restored = Encounter.load(path)
    before = restored._dice._index
    use = restored.choose(nimble.choice_id, "use")
    assert restored._dice._index == before + 1
    hero = use.inspection.choice
    assert hero is not None and hero.kind == "attack_hero_reroll"
    assert next(event for event in use.events if event.kind == "strike").check.dc == 20
    assert not any(event.kind == "nimble_dodge_choice" for event in use.events)

    rerolled = restored.choose(hero.choice_id, "spend_hero_point")
    checks = [event.check for event in rerolled.events if event.check is not None]
    assert checks and all((check.die, check.modifier, check.dc) == (15, 9, 20) for check in checks)
    assert next(actor for actor in restored.inspect().actors if actor.actor_id == "thief_rogue").reaction_available is False


def test_nimble_decline_preserves_reaction_and_attacker_hero_choice() -> None:
    game = Encounter.start(
        get_setup("rogue_thief_vs_fighter_fixture"),
        rolls=(1, 20, 10, 15, 4),
    )
    _keep_start_choices(game)
    paused = game.execute(Strike("thief_rogue", attack_id="longsword"))
    nimble = paused.inspection.choice
    assert nimble is not None and nimble.kind == "nimble_dodge"
    result = game.choose(nimble.choice_id, "decline")
    hero = result.inspection.choice
    assert hero is not None and hero.kind == "attack_hero_reroll"
    attack = next(event.check for event in result.events if event.kind == "strike")
    assert attack is not None and attack.dc == 18
    rogue = next(actor for actor in result.inspection.actors if actor.actor_id == "thief_rogue")
    assert rogue.reaction_available is True
    assert not any(event.kind == "nimble_dodge_choice" for event in result.events)


def test_divine_lance_nimble_choice_round_trips_before_saved_spell_attack(tmp_path) -> None:
    game = Encounter.start(
        get_setup("rogue_thief_vs_warpriest_fixture"),
        # Rogue initiative, Warpriest initiative, Divine Lance attack, damage.
        rolls=(1, 20, 10, 4),
    )
    _keep_start_choices(game)
    assert game.inspect().turn_actor_id == "cleric_c"
    paused = game.execute(Cast("divine_lance", "thief_rogue"))
    nimble = paused.inspection.choice
    assert paused.status is ResultStatus.PAUSED
    assert nimble is not None and nimble.kind == "nimble_dodge"

    path = tmp_path / "thief-nimble-lance.json"
    game.save(path)
    restored = Encounter.load(path)
    assert restored.inspect() == paused.inspection
    before = restored._dice._index
    attack = restored.choose(nimble.choice_id, "use")
    assert restored._dice._index == before + 1
    hero = attack.inspection.choice
    assert hero is not None and hero.kind == "spell_attack_hero_reroll"
    check = next(event.check for event in attack.events if event.kind == "spell_attack")
    assert check is not None and (check.die, check.modifier, check.dc) == (10, 7, 20)
    assert not any(event.kind == "nimble_dodge_choice" for event in attack.events)

    path = tmp_path / "thief-nimble-lance-hero.json"
    restored.save(path)
    restored = Encounter.load(path)
    rerolled = restored.choose(hero.choice_id, "keep")
    check = next(event.check for event in rerolled.events if event.kind == "spell_attack")
    assert check is not None and (check.die, check.modifier, check.dc) == (10, 7, 20)
    rogue = next(actor for actor in restored.inspect().actors if actor.actor_id == "thief_rogue")
    assert rogue.reaction_available is False


def test_round_two_reactive_strike_nimble_resumes_parent_stride_after_save(tmp_path) -> None:
    game = Encounter.start(
        get_setup("rogue_thief_vs_fighter_fixture"),
        # Fighter acts first in round one; later rolls are Reactive Strike and
        # its Hero reroll. The Rogue's second-round start avoids the unresolved
        # before-first-turn reaction edge.
        rolls=(1, 20, 10, 15, 4),
    )
    _keep_start_choices(game)
    assert game.inspect().turn_actor_id == "fighter_m"
    game.execute(EndTurn())
    game.execute(EndTurn())
    game.execute(EndTurn())
    assert game.inspect().turn_actor_id == "thief_rogue"
    assert game.inspect().round_number == 2

    paused = game.execute(Stride((Position(0, 1),)))
    reaction = paused.inspection.choice
    assert paused.status is ResultStatus.PAUSED
    assert reaction is not None and reaction.kind == "reaction"
    reaction_result = game.choose(reaction.choice_id, "accept")
    nimble = reaction_result.inspection.choice
    assert nimble is not None and nimble.kind == "nimble_dodge"
    assert "has acted" not in nimble.prompt
    nimble_path = tmp_path / "nested-reaction-nimble.json"
    game.save(nimble_path)
    game = Encounter.load(nimble_path)
    assert game.inspect().choice == nimble
    nimble = game.inspect().choice
    assert nimble is not None
    game.choose(nimble.choice_id, "use")
    hero = game.inspect().choice
    assert hero is not None and hero.kind == "attack_hero_reroll"

    path = tmp_path / "nested-reaction.json"
    game.save(path)
    restored = Encounter.load(path)
    assert restored.inspect() == game.inspect()
    result = restored.choose(hero.choice_id, "spend_hero_point")
    assert result.status is ResultStatus.COMPLETED
    assert any(event.kind == "move_step" for event in result.events)
    rogue = next(actor for actor in result.inspection.actors if actor.actor_id == "thief_rogue")
    assert rogue.position == Position(0, 1)


def test_caster_frightened_and_prone_apply_to_divine_lance_and_saved_void_warp_dc(tmp_path) -> None:
    game = Encounter.start(
        get_setup("rogue_thief_vs_warpriest_fixture"),
        # Rogue initiative, Warpriest initiative, Demoralize, Trip, Divine
        # Lance, Void Warp save, and the final Void Warp damage die.
        rolls=(20, 1, 20, 15, 10, 10, 4, 4),
    )
    _keep_start_choices(game)
    demoralize = game.execute(Demoralize("cleric_c", spoken_language="Common"))
    choice = demoralize.inspection.choice
    assert choice is not None and choice.kind == "family_action"
    game.choose(choice.choice_id, "keep")
    trip = game.execute(Trip("cleric_c"))
    choice = trip.inspection.choice
    assert choice is not None and choice.kind == "family_action"
    game.choose(choice.choice_id, "keep")
    caster = next(actor for actor in game.inspect().actors if actor.actor_id == "cleric_c")
    assert caster.prone is True
    assert any(effect.kind == "frightened" and effect.value == 2 for effect in caster.condition_effects)

    game.execute(EndTurn())
    lance = game.execute(Cast("divine_lance", "thief_rogue"))
    choice = lance.inspection.choice
    assert choice is not None and choice.kind == "nimble_dodge"
    lance = game.choose(choice.choice_id, "decline")
    choice = lance.inspection.choice
    assert choice is not None and choice.kind == "spell_attack_hero_reroll"
    check = next(event.check for event in lance.events if event.kind == "spell_attack")
    assert check is not None and (check.modifier, check.dc) == (3, 18)

    path = tmp_path / "caster-conditions-lance.json"
    game.save(path)
    restored = Encounter.load(path)
    assert restored.inspect() == lance.inspection
    restored.choose(choice.choice_id, "keep")
    restored.execute(EndTurn())
    restored.execute(EndTurn())
    warp = restored.execute(Cast("void_warp", "thief_rogue"))
    choice = warp.inspection.choice
    assert choice is not None and choice.kind == "spell_save_hero_reroll"
    check = next(event.check for event in warp.events if event.kind == "spell_save")
    assert check is not None and (check.modifier, check.dc) == (5, 16)

    path = tmp_path / "caster-conditions-warp.json"
    restored.save(path)
    restored = Encounter.load(path)
    assert restored.inspect() == warp.inspection
    result = restored.choose(choice.choice_id, "keep")
    damage = next(event.damage for event in result.events if event.damage is not None)
    assert damage is not None and damage.total == 8


def test_void_warp_uses_frightened_fortitude_modifier() -> None:
    game = Encounter.start(
        get_setup("s3_rescue_under_pressure"),
        rolls=(1, 1, 20, 1, 1, 20, 12, 2, 2),
    )
    _keep_start_choices(game)
    assert game.inspect().turn_actor_id == "cleric_c"
    demoralize = game.execute(Demoralize("guard_dog_a", spoken_language="Common"))
    assert demoralize.status is ResultStatus.PAUSED
    choice = demoralize.inspection.choice
    assert choice is not None and choice.kind == "family_action"
    game.choose(choice.choice_id, "keep")

    result = game.execute(Cast("void_warp", "guard_dog_a"))
    check = next(event.check for event in result.events if event.kind == "spell_save")
    assert check is not None
    assert (check.die, check.modifier, check.dc, check.total) == (12, 3, 17, 15)
    damage = next(event.damage for event in result.events if event.damage is not None)
    assert damage is not None and damage.total == 4
