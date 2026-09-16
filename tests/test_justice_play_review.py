"""Independent source and public-play review of the selected Justice Champion.

Rules references:
- Champion: https://2e.aonprd.com/Classes.aspx?ID=58
- Justice: https://2e.aonprd.com/Causes.aspx?ID=11
- Lay on Hands: https://2e.aonprd.com/Spells.aspx?ID=2047
- Desperate Prayer: https://2e.aonprd.com/Feats.aspx?ID=5884
"""

from __future__ import annotations

from pathlib import Path

import pytest

import pf2e.content as content
from pf2e.damage import DamageTerm, roll_damage_terms
from pf2e.encounter import Encounter
from pf2e.model import (
    CreaturePlacement,
    EncounterSetup,
    EndTurn,
    FamilyProcedureContext,
    LayOnHands,
    Position,
    RaiseShield,
    ResultStatus,
    Strike,
    SuppressAura,
    ToggleAura,
)


def _actor(game: Encounter, actor_id: str):
    return next(actor for actor in game.inspect().actors if actor.actor_id == actor_id)


def _choose(game: Encounter, option_id: str):
    choice = game.inspect().choice
    assert choice is not None
    return game.choose(choice.choice_id, option_id, choice.owner_actor_id)


def _settle_initiative(game: Encounter) -> None:
    while (choice := game.inspect().choice) is not None:
        assert choice.kind in {"initiative_hero_reroll", "initiative_tie"}
        option_id = (
            "keep"
            if any(option.option_id == "keep" for option in choice.options)
            else choice.options[0].option_id
        )
        assert game.choose(choice.choice_id, option_id, choice.owner_actor_id).status in {
            ResultStatus.PAUSED,
            ResultStatus.COMPLETED,
        }


def _end_to(game: Encounter, actor_id: str) -> None:
    for _ in range(len(game.inspect().actors) + 2):
        if game.inspect().turn_actor_id == actor_id:
            return
        result = game.execute(EndTurn())
        assert result.status in {ResultStatus.PAUSED, ResultStatus.COMPLETED}
        if game.inspect().choice is not None:
            return
    raise AssertionError(f"did not reach {actor_id}")


def _reach_setup(monkeypatch: pytest.MonkeyPatch) -> EncounterSetup:
    """Production definitions in a diagnostic reach fixture, not a new class."""
    setup = EncounterSetup(
        setup_id="review_justice_reach_corridor",
        name="Review Justice reach corridor",
        width=6,
        height=3,
        placements=(
            CreaturePlacement(
                "justice_champion",
                content.JUSTICE_CHAMPION.definition_id,
                "Justice Champion",
                "blue",
                Position(0, 1),
            ),
            CreaturePlacement(
                "justice_ally",
                content.STEEL_SHIELD_FIGHTER_M.definition_id,
                "Champion's Shield Ally",
                "blue",
                Position(2, 1),
            ),
            CreaturePlacement(
                "justice_guard_dog",
                content.GUARD_DOG.definition_id,
                "Justice Guard Dog",
                "red",
                Position(3, 1),
            ),
        ),
    )
    monkeypatch.setattr(
        content,
        "_STAGED_SETUPS",
        content._STAGED_SETUPS | {setup.setup_id: setup},
    )
    return setup


def _knockout_setup(monkeypatch: pytest.MonkeyPatch) -> EncounterSetup:
    """Production builds positioned to make actual unconsciousness observable."""
    setup = EncounterSetup(
        setup_id="review_justice_knockout",
        name="Review Justice unconscious aura end",
        width=4,
        height=3,
        placements=(
            CreaturePlacement(
                "justice_champion",
                content.JUSTICE_CHAMPION.definition_id,
                "Justice Champion",
                "blue",
                Position(1, 1),
            ),
            CreaturePlacement(
                "justice_ally",
                content.STEEL_SHIELD_FIGHTER_M.definition_id,
                "Champion's Shield Ally",
                "blue",
                Position(1, 2),
            ),
            CreaturePlacement(
                "justice_attacker",
                content.MELEE_FIGHTER_M.definition_id,
                "Hostile Fighter",
                "red",
                Position(2, 1),
            ),
        ),
    )
    monkeypatch.setattr(
        content,
        "_STAGED_SETUPS",
        content._STAGED_SETUPS | {setup.setup_id: setup},
    )
    return setup


def test_selected_justice_sheet_matches_source_grants() -> None:
    champion = content.JUSTICE_CHAMPION
    assert (champion.hp, champion.ac, champion.perception) == (20, 18, 3)
    assert champion.deity == "Iomedae"
    assert champion.spell_sanctification == "holy"
    assert champion.focus_points == champion.focus_capacity == 1
    assert {"shield_block", "justice_retributive_strike", "lay_on_hands", "desperate_prayer"} <= set(
        champion.abilities
    )
    assert dict(champion.ability_modifiers) == {
        "strength": 4,
        "dexterity": 1,
        "constitution": 2,
        "intelligence": 0,
        "wisdom": 0,
        "charisma": 2,
    }
    assert dict((name, (rank, value)) for name, rank, value in champion.saves) == {
        "fortitude": ("expert", 7),
        "reflex": ("trained", 4),
        "will": ("expert", 5),
    }
    proficiencies = dict(champion.proficiencies)
    assert proficiencies["spell_attack"] == "trained"
    assert proficiencies["spell_dc"] == "trained"


def test_healthy_fight_saves_protection_block_retaliation_and_lay_expiry(
    tmp_path: Path,
) -> None:
    # Champion, ally, dog initiatives; dog attack/damage; retaliation
    # attack/damage; Champion miss; Champion final attack/damage.
    game = Encounter.start(
        content.get_setup("justice_champion_iomedae_vs_guard_dog"),
        rolls=(1, 20, 10, 20, 4, 10, 1, 1, 10, 3),
    )
    assert all(actor.hp == actor.max_hp for actor in game.inspect().actors)
    _settle_initiative(game)
    assert game.inspect().turn_actor_id == "justice_ally"
    assert game.execute(RaiseShield()).status is ResultStatus.COMPLETED
    assert game.execute(EndTurn()).status is ResultStatus.COMPLETED

    offered = game.execute(Strike("justice_ally", attack_id="jaws"))
    assert offered.status is ResultStatus.PAUSED
    reaction = offered.inspection.choice
    assert reaction is not None and reaction.kind == "reaction"
    reaction_path = tmp_path / "justice-protection.json"
    game.save(reaction_path)
    game = Encounter.load(reaction_path)
    assert game.inspect().choice == reaction

    protected = _choose(game, "accept")
    assert protected.status is ResultStatus.PAUSED
    block = protected.inspection.choice
    assert block is not None and block.kind == "shield_block"
    blocked = _choose(game, "block")
    assert blocked.status is ResultStatus.PAUSED
    hero = blocked.inspection.choice
    assert hero is not None and hero.kind == "attack_hero_reroll"
    hero_path = tmp_path / "justice-retaliation-hero.json"
    game.save(hero_path)
    game = Encounter.load(hero_path)
    assert game.inspect().choice == hero

    retaliation = _choose(game, "keep")
    assert retaliation.status is ResultStatus.COMPLETED
    events = (*protected.events, *blocked.events, *retaliation.events)
    damage = next(event for event in events if event.kind == "damage" and event.target_id == "justice_ally")
    assert damage.original_damage is not None and damage.original_damage.total == 10
    assert damage.damage is not None and damage.damage.total == 7
    assert damage.shield_block is not None
    assert damage.shield_block.damage_to_actor == 2
    retaliation_check = next(
        event.check for event in events
        if event.kind == "strike" and event.actor_id == "justice_champion"
    )
    assert retaliation_check is not None
    assert (retaliation_check.attack_count, retaliation_check.map_penalty) == (1, 0)
    retaliation_damage = next(
        event.damage for event in events
        if event.kind == "damage" and event.target_id == "justice_guard_dog"
    )
    assert retaliation_damage is not None
    assert retaliation_damage.components[0].tags == frozenset({"holy"})
    assert _actor(game, "justice_ally").hp == _actor(game, "justice_ally").max_hp - 2
    assert not _actor(game, "justice_champion").reaction_available

    assert game.execute(EndTurn()).status is ResultStatus.COMPLETED
    assert game.inspect().turn_actor_id == "justice_champion"
    healed = game.execute(LayOnHands("justice_ally"))
    assert healed.status is ResultStatus.COMPLETED
    assert _actor(game, "justice_ally").hp == _actor(game, "justice_ally").max_hp
    # Raise a Shield's circumstance bonus and Lay on Hands' status bonus stack.
    assert _actor(game, "justice_ally").ac == 22
    assert _actor(game, "justice_champion").focus_points == 0
    lay_path = tmp_path / "justice-lay-effect.json"
    game.save(lay_path)
    game = Encounter.load(lay_path)

    missed = game.execute(Strike("justice_guard_dog", attack_id="longsword"))
    assert missed.status is ResultStatus.PAUSED
    assert _choose(game, "keep").status is ResultStatus.COMPLETED
    assert game.execute(EndTurn()).status is ResultStatus.COMPLETED
    assert game.inspect().turn_actor_id == "justice_ally"
    # Raise a Shield has expired; the one-round Lay on Hands status bonus remains.
    assert _actor(game, "justice_ally").ac == 20
    assert game.execute(EndTurn()).status is ResultStatus.COMPLETED
    assert game.inspect().turn_actor_id == "justice_guard_dog"
    prayer_offer = game.execute(EndTurn())
    assert prayer_offer.status is ResultStatus.PAUSED
    assert prayer_offer.inspection.choice is not None
    assert prayer_offer.inspection.choice.kind == "desperate_prayer"
    assert _choose(game, "decline").status is ResultStatus.COMPLETED
    assert game.inspect().turn_actor_id == "justice_champion"
    assert _actor(game, "justice_ally").ac == 18

    final = game.execute(Strike("justice_guard_dog", attack_id="longsword"))
    assert final.status is ResultStatus.PAUSED
    victory = _choose(game, "keep")
    assert victory.status is ResultStatus.COMPLETED
    assert not game.inspect().in_progress and game.inspect().winner_team == "blue"


def test_aura_protects_out_of_reach_suppression_blocks_it_and_unconscious_ends_it(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    setup = _reach_setup(monkeypatch)
    protected_game = Encounter.start(setup, rolls=(1, 10, 20, 15, 4))
    _settle_initiative(protected_game)
    assert protected_game.inspect().turn_actor_id == "justice_guard_dog"
    offered = protected_game.execute(Strike("justice_ally", attack_id="jaws"))
    assert offered.status is ResultStatus.PAUSED
    accepted = _choose(protected_game, "accept")
    assert accepted.status is ResultStatus.COMPLETED
    assert any(event.kind == "retributive_strike_out_of_reach" for event in accepted.events)
    assert not any(
        event.kind == "strike" and event.actor_id == "justice_champion"
        for event in accepted.events
    )
    assert _actor(protected_game, "justice_ally").hp == _actor(protected_game, "justice_ally").max_hp - 2

    suppressed_game = Encounter.start(setup, rolls=(20, 10, 1, 15, 4))
    _settle_initiative(suppressed_game)
    assert suppressed_game.execute(SuppressAura()).status is ResultStatus.COMPLETED
    assert suppressed_game.execute(EndTurn()).status is ResultStatus.COMPLETED
    assert suppressed_game.execute(EndTurn()).status is ResultStatus.COMPLETED
    unprotected = suppressed_game.execute(Strike("justice_ally", attack_id="jaws"))
    assert unprotected.status is ResultStatus.COMPLETED
    assert unprotected.inspection.choice is None
    assert _actor(suppressed_game, "justice_ally").hp == _actor(suppressed_game, "justice_ally").max_hp - 5

    knockout = Encounter.start(
        _knockout_setup(monkeypatch),
        rolls=(1, 10, 20, 20, 8),
    )
    _settle_initiative(knockout)
    down = knockout.execute(Strike("justice_champion", attack_id="longsword"))
    assert down.status is ResultStatus.PAUSED
    assert down.inspection.choice is not None
    assert down.inspection.choice.kind == "attack_hero_reroll"
    down = _choose(knockout, "keep")
    assert down.status is ResultStatus.PAUSED
    assert down.inspection.choice is not None
    assert down.inspection.choice.kind == "heroic_recovery_damage"
    assert _choose(knockout, "normal").status is ResultStatus.COMPLETED
    champion = _actor(knockout, "justice_champion")
    assert champion.unconscious and champion.dying == 2
    assert "justice_champion" not in knockout._state.justice_aura_active
    before = knockout.inspect()
    dice_before = knockout._dice.to_data()
    rejected = knockout.execute(ToggleAura(active=True))
    assert rejected.status is ResultStatus.REJECTED
    assert knockout.inspect() == before and knockout._dice.to_data() == dice_before


def test_declining_retribution_preserves_champion_reaction_for_own_shield() -> None:
    game = Encounter.start(
        content.JUSTICE_CHAMPION_SETUP,
        # Initiatives; first dog attack/damage; second MAP attack/damage.
        rolls=(20, 10, 1, 15, 4, 19, 4),
    )
    _settle_initiative(game)
    assert game.execute(RaiseShield()).status is ResultStatus.COMPLETED
    assert game.execute(EndTurn()).status is ResultStatus.COMPLETED
    assert game.execute(EndTurn()).status is ResultStatus.COMPLETED

    ally_hit = game.execute(Strike("justice_ally", attack_id="jaws"))
    assert ally_hit.status is ResultStatus.PAUSED
    assert ally_hit.inspection.choice is not None
    assert ally_hit.inspection.choice.kind == "reaction"
    declined = _choose(game, "decline")
    assert declined.status is ResultStatus.COMPLETED
    assert _actor(game, "justice_champion").reaction_available

    champion_hit = game.execute(Strike("justice_champion", attack_id="jaws"))
    assert champion_hit.status is ResultStatus.PAUSED
    assert champion_hit.inspection.choice is not None
    assert champion_hit.inspection.choice.kind == "shield_block"
    blocked = _choose(game, "block")
    assert blocked.status is ResultStatus.COMPLETED
    damage = next(event for event in blocked.events if event.kind == "damage")
    assert damage.shield_block is not None
    assert damage.shield_block.prevented_from_actor == 5
    assert damage.shield_block.damage_to_actor == 0
    assert not _actor(game, "justice_champion").reaction_available


def test_own_turn_retaliation_keeps_map_and_prayer_spend_survives_recovery(
    tmp_path: Path,
) -> None:
    # First game is a diagnostic trigger during the Champion's real turn.
    map_game = Encounter.start(
        content.JUSTICE_CHAMPION_SETUP,
        rolls=(20, 10, 1, 2, 20, 4),
    )
    _settle_initiative(map_game)
    first = map_game.execute(Strike("justice_guard_dog", attack_id="longsword"))
    assert first.status is ResultStatus.PAUSED
    assert _choose(map_game, "keep").status is ResultStatus.COMPLETED
    assert _actor(map_game, "justice_champion").strikes_this_turn == 1
    dog = map_game._state.creatures["justice_guard_dog"]
    context = FamilyProcedureContext(
        map_game,
        map_game._state,
        map_game._dice,
        dog,
        content.get_definition(dog.definition_id),
        "review diagnostic",
    )
    damage = roll_damage_terms(
        (DamageTerm("review", "slashing", (), modifier=6),),
        lambda _sides: 1,
    )
    assert context.apply_family_damage(
        "justice_ally", damage, source="review own-turn trigger", damage_type="slashing"
    ) == ()
    accepted = _choose(map_game, "accept")
    assert accepted.status is ResultStatus.PAUSED
    retaliation_check = next(event.check for event in accepted.events if event.kind == "strike")
    assert retaliation_check is not None
    assert (retaliation_check.attack_count, retaliation_check.map_penalty) == (2, -5)

    # Second game spends the normal point, saves the next-start prayer offer,
    # spends its restricted point, wins, then checks Refocus and preparation.
    game = Encounter.start(
        content.JUSTICE_CHAMPION_SETUP,
        rolls=(20, 10, 1, 20, 8),
    )
    _settle_initiative(game)
    assert game.execute(LayOnHands("justice_ally")).status is ResultStatus.COMPLETED
    assert _actor(game, "justice_champion").focus_points == 0
    assert game.execute(EndTurn()).status is ResultStatus.COMPLETED
    assert game.execute(EndTurn()).status is ResultStatus.COMPLETED
    prayer_offer = game.execute(EndTurn())
    assert prayer_offer.status is ResultStatus.PAUSED
    prayer = prayer_offer.inspection.choice
    assert prayer is not None and prayer.kind == "desperate_prayer"
    prayer_path = tmp_path / "justice-prayer-review.json"
    game.save(prayer_path)
    game = Encounter.load(prayer_path)
    assert game.inspect().choice == prayer
    assert _choose(game, "accept").status is ResultStatus.COMPLETED
    assert "justice_champion" in game._state.desperate_prayer_points
    assert game.execute(LayOnHands("justice_ally")).status is ResultStatus.COMPLETED
    assert _actor(game, "justice_champion").focus_points == 0
    assert "justice_champion" not in game._state.desperate_prayer_points

    attack = game.execute(Strike("justice_guard_dog", attack_id="longsword"))
    assert attack.status is ResultStatus.PAUSED
    victory = _choose(game, "keep")
    assert victory.status is ResultStatus.COMPLETED
    dealt = next(event.damage for event in victory.events if event.kind == "damage")
    assert dealt is not None and dealt.components[0].tags == frozenset({"holy"})
    assert not game.inspect().in_progress

    assert game.refocus("justice_champion").status is ResultStatus.COMPLETED
    assert _actor(game, "justice_champion").focus_points == 1
    assert "justice_champion" in game._state.desperate_prayer_used
    assert game.record_rested(
        ("justice_champion", "justice_ally"), day_number=2, elapsed_seconds=1
    ).status is ResultStatus.COMPLETED
    assert game.daily_prepare(("justice_champion", "justice_ally")).status is ResultStatus.COMPLETED
    assert "justice_champion" not in game._state.desperate_prayer_used
    assert _actor(game, "justice_champion").focus_points == 1
