"""Combined public play for the accepted Angelic and Justice builds.

Rules references:
- Angelic bloodline: https://2e.aonprd.com/Bloodlines.aspx?ID=20
- Angelic Halo: https://2e.aonprd.com/Spells.aspx?ID=2093
- Sorcerous Potency: https://2e.aonprd.com/Classes.aspx?ID=62
- Justice: https://2e.aonprd.com/Causes.aspx?ID=11
- Lay on Hands: https://2e.aonprd.com/Spells.aspx?ID=2047
"""

from __future__ import annotations

from pathlib import Path

import pytest

import pf2e.content as content
from pf2e.encounter import Encounter
from pf2e.model import (
    Cast,
    CreaturePlacement,
    EncounterSetup,
    EndTurn,
    LayOnHands,
    Position,
    ResultStatus,
    Strike,
)


def _actor(game: Encounter, actor_id: str):
    return next(actor for actor in game.inspect().actors if actor.actor_id == actor_id)


def _choose(game: Encounter, option_id: str):
    choice = game.inspect().choice
    assert choice is not None
    return game.choose(choice.choice_id, option_id, choice.owner_actor_id)


def _settle_initiative(game: Encounter) -> None:
    for _ in range(8):
        choice = game.inspect().choice
        if choice is None:
            return
        assert choice.kind in {"initiative_hero_reroll", "initiative_tie"}
        option_id = (
            "keep"
            if any(option.option_id == "keep" for option in choice.options)
            else choice.options[0].option_id
        )
        result = game.choose(choice.choice_id, option_id, choice.owner_actor_id)
        assert result.status in {ResultStatus.PAUSED, ResultStatus.COMPLETED}
    raise AssertionError("initiative did not settle within eight choices")


def _party_setup(monkeypatch: pytest.MonkeyPatch) -> EncounterSetup:
    """Accepted production builds in one finite interaction fixture."""
    setup = EncounterSetup(
        setup_id="review_angelic_justice_party",
        name="Review Angelic and Justice party",
        width=5,
        height=4,
        placements=(
            CreaturePlacement(
                "angelic_sorcerer",
                content.ANGELIC_SORCERER_STAGED.definition_id,
                "Angelic Sorcerer",
                "blue",
                Position(1, 1),
            ),
            CreaturePlacement(
                "justice_champion",
                content.JUSTICE_CHAMPION.definition_id,
                "Justice Champion",
                "blue",
                Position(2, 1),
            ),
            CreaturePlacement(
                "divine_ally",
                content.STEEL_SHIELD_FIGHTER_M.definition_id,
                "Divine Party Ally",
                "blue",
                Position(2, 2),
            ),
            CreaturePlacement(
                "divine_dog",
                content.GUARD_DOG.definition_id,
                "Guard Dog",
                "red",
                Position(3, 2),
            ),
        ),
    )
    monkeypatch.setattr(
        content,
        "_STAGED_SETUPS",
        content._STAGED_SETUPS | {setup.setup_id: setup},
    )
    return setup


def test_angelic_and_justice_party_protects_heals_saves_effects_and_wins(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    # Four initiatives; first dog Strike; Justice retaliation; Heal d8; second
    # dog Strike; third dog Strike; final Champion Strike.
    rolls = (20, 10, 5, 15, 15, 4, 10, 1, 1, 15, 4, 12, 1, 10, 1)
    game = Encounter.start(_party_setup(monkeypatch), rolls=rolls)
    assert all(actor.hp == actor.max_hp for actor in game.inspect().actors)
    _settle_initiative(game)
    assert game.inspect().turn_actor_id == "angelic_sorcerer"

    halo_offer = game.execute(Cast("angelic_halo", actions=1))
    assert halo_offer.status is ResultStatus.PAUSED
    assert halo_offer.inspection.choice is not None
    assert halo_offer.inspection.choice.kind == "spell_blood_magic_recipient"
    assert _choose(game, "divine_ally").status is ResultStatus.COMPLETED
    assert _actor(game, "angelic_sorcerer").focus_points == 0
    assert any(effect.kind == "angelic_halo" for effect in _actor(game, "angelic_sorcerer").effects)
    assert any(effect.kind == "blood_magic" for effect in _actor(game, "divine_ally").effects)

    assert game.execute(EndTurn()).status is ResultStatus.COMPLETED
    assert game.inspect().turn_actor_id == "divine_dog"
    reaction_offer = game.execute(Strike("divine_ally", attack_id="jaws"))
    assert reaction_offer.status is ResultStatus.PAUSED
    reaction = reaction_offer.inspection.choice
    assert reaction is not None and reaction.kind == "reaction"

    protection_path = tmp_path / "divine-party-protection.json"
    game.save(protection_path)
    game = Encounter.load(protection_path)
    assert game.inspect().choice == reaction

    protected = _choose(game, "accept")
    assert protected.status is ResultStatus.PAUSED
    assert protected.inspection.choice is not None
    assert protected.inspection.choice.kind == "attack_hero_reroll"
    retaliation = _choose(game, "keep")
    assert retaliation.status is ResultStatus.COMPLETED
    events = (*protected.events, *retaliation.events)
    injury = next(
        event for event in events
        if event.kind == "damage" and event.target_id == "divine_ally"
    )
    assert injury.original_damage is not None and injury.original_damage.total == 5
    assert injury.damage is not None and injury.damage.total == 2
    counter = next(
        event for event in events
        if event.kind == "strike" and event.actor_id == "justice_champion"
    )
    assert counter.check is not None
    assert (counter.check.attack_count, counter.check.map_penalty) == (1, 0)
    assert _actor(game, "divine_ally").hp == 19
    assert _actor(game, "divine_dog").hp == 3

    assert game.execute(EndTurn()).status is ResultStatus.COMPLETED
    assert game.inspect().turn_actor_id == "justice_champion"
    assert game.execute(EndTurn()).status is ResultStatus.COMPLETED
    assert game.inspect().turn_actor_id == "divine_ally"
    assert game.execute(EndTurn()).status is ResultStatus.COMPLETED
    assert game.inspect().turn_actor_id == "angelic_sorcerer"
    assert not any(effect.kind == "blood_magic" for effect in _actor(game, "divine_ally").effects)

    heal_offer = game.execute(Cast("heal", "divine_ally", actions=2))
    assert heal_offer.status is ResultStatus.PAUSED
    assert heal_offer.inspection.choice is not None
    assert heal_offer.inspection.choice.kind == "spell_blood_magic_recipient"
    willingness_offer = _choose(game, "divine_ally")
    assert willingness_offer.status is ResultStatus.PAUSED
    assert willingness_offer.inspection.choice is not None
    assert willingness_offer.inspection.choice.kind == "spell_willingness"
    healed = _choose(game, "willing")
    assert healed.status is ResultStatus.COMPLETED
    healing = next(event for event in healed.events if event.kind == "healing")
    assert "heals 11 HP" in healing.text
    assert "+ Angelic Halo 2 status" in healing.text
    assert "+ Sorcerous Potency" not in healing.text
    assert _actor(game, "divine_ally").hp == 21
    assert _actor(game, "angelic_sorcerer").spontaneous_slots[0].remaining == 2

    assert game.execute(EndTurn()).status is ResultStatus.COMPLETED
    second_hit = game.execute(Strike("divine_ally", attack_id="jaws"))
    assert second_hit.status is ResultStatus.PAUSED
    assert second_hit.inspection.choice is not None
    assert second_hit.inspection.choice.kind == "reaction"
    unprotected = _choose(game, "decline")
    assert unprotected.status is ResultStatus.COMPLETED
    assert next(event.damage.total for event in unprotected.events if event.damage is not None) == 5
    assert _actor(game, "divine_ally").hp == 16

    assert game.execute(EndTurn()).status is ResultStatus.COMPLETED
    assert game.inspect().turn_actor_id == "justice_champion"
    laid = game.execute(LayOnHands("divine_ally"))
    assert laid.status is ResultStatus.COMPLETED
    ally = _actor(game, "divine_ally")
    assert ally.hp == 21
    assert ally.ac == 20
    assert {effect.kind for effect in ally.effects} >= {"blood_magic", "lay_on_hands_ac"}
    # The effects overlap without being added to the wrong statistic: Divine
    # Aura is +1 status to saves, while Lay on Hands is +2 status to AC.
    assert game._skill_dc(game._state, "divine_ally", "fortitude") == 19

    effects_path = tmp_path / "divine-party-timed-effects.json"
    before_save = game.inspect()
    game.save(effects_path)
    game = Encounter.load(effects_path)
    assert game.inspect() == before_save
    assert _actor(game, "divine_ally").ac == 20
    assert game._skill_dc(game._state, "divine_ally", "fortitude") == 19

    assert game.execute(EndTurn()).status is ResultStatus.COMPLETED
    assert game.inspect().turn_actor_id == "divine_ally"
    assert game.execute(EndTurn()).status is ResultStatus.COMPLETED
    assert game.inspect().turn_actor_id == "angelic_sorcerer"
    ally = _actor(game, "divine_ally")
    assert not any(effect.kind == "blood_magic" for effect in ally.effects)
    assert any(effect.kind == "lay_on_hands_ac" for effect in ally.effects)
    assert ally.ac == 20
    assert game._skill_dc(game._state, "divine_ally", "fortitude") == 18

    assert game.execute(EndTurn()).status is ResultStatus.COMPLETED
    assert game.inspect().turn_actor_id == "divine_dog"
    third_hit = game.execute(Strike("justice_champion", attack_id="jaws"))
    assert third_hit.status is ResultStatus.COMPLETED
    assert _actor(game, "justice_champion").hp == 18
    prayer_offer = game.execute(EndTurn())
    assert prayer_offer.status is ResultStatus.PAUSED
    assert prayer_offer.inspection.choice is not None
    assert prayer_offer.inspection.choice.kind == "desperate_prayer"
    assert _choose(game, "decline").status is ResultStatus.COMPLETED
    assert game.inspect().turn_actor_id == "justice_champion"
    ally = _actor(game, "divine_ally")
    assert not any(effect.kind == "lay_on_hands_ac" for effect in ally.effects)
    assert ally.ac == 18

    final = game.execute(Strike("divine_dog", attack_id="longsword"))
    assert final.status is ResultStatus.PAUSED
    victory = _choose(game, "keep")
    assert victory.status is ResultStatus.COMPLETED
    state = game.inspect()
    assert not state.in_progress and state.winner_team == "blue"
    assert _actor(game, "divine_dog").defeated
    assert _actor(game, "divine_ally").hp == 21
    assert _actor(game, "angelic_sorcerer").hp == 16
