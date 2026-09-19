"""Public Angelic Halo play with a second caster and a moving recipient."""

from __future__ import annotations

from pathlib import Path

import pytest

import pf2e.encounter as encounter_module
import pf2e.persistence as persistence_module
from pf2e.content import ANGELIC_SORCERER_STAGED, GUARD_DOG, MELEE_FIGHTER_M
from pf2e.encounter import Encounter
from pf2e.model import (
    Cast,
    CreaturePlacement,
    EncounterSetup,
    EndTurn,
    Position,
    ResultStatus,
    Strike,
    Stride,
)


def _actor(game: Encounter, actor_id: str):
    return next(actor for actor in game.inspect().actors if actor.actor_id == actor_id)


def _finish_initial_choices(game: Encounter) -> None:
    while (choice := game.inspect().choice) is not None:
        assert choice.kind == "initiative_hero_reroll"
        result = game.choose(choice.choice_id, "keep", choice.owner_actor_id)
        assert result.status is ResultStatus.COMPLETED


def _choose(game: Encounter, option_id: str, *, status: ResultStatus) -> None:
    choice = game.inspect().choice
    assert choice is not None
    result = game.choose(choice.choice_id, option_id, choice.owner_actor_id)
    assert result.status is status


def _decline_reaction(game: Encounter) -> None:
    choice = game.inspect().choice
    assert choice is not None and choice.kind == "reaction"
    _choose(game, "decline", status=ResultStatus.COMPLETED)


@pytest.fixture
def cross_caster_setup(monkeypatch: pytest.MonkeyPatch) -> EncounterSetup:
    """Temporarily admit a local authored room using normal catalog definitions."""

    setup = EncounterSetup(
        setup_id="test_halo_cross_caster_play",
        name="Halo cross-caster public play fixture",
        width=7,
        height=5,
        placements=(
            CreaturePlacement(
                "halo_sorcerer",
                ANGELIC_SORCERER_STAGED.definition_id,
                "Halo Sorcerer",
                "blue",
                Position(1, 2),
            ),
            CreaturePlacement(
                "healer_sorcerer",
                ANGELIC_SORCERER_STAGED.definition_id,
                "Healer Sorcerer",
                "blue",
                Position(2, 2),
            ),
            CreaturePlacement(
                "injured_fighter",
                MELEE_FIGHTER_M.definition_id,
                "Injured Fighter",
                "blue",
                Position(3, 2),
            ),
            CreaturePlacement(
                "guard_dog",
                GUARD_DOG.definition_id,
                "Guard Dog",
                "red",
                Position(5, 2),
            ),
        ),
    )

    encounter_lookup = encounter_module.get_setup
    persistence_lookup = persistence_module.get_setup

    def lookup_for_encounter(setup_id: str) -> EncounterSetup:
        return setup if setup_id == setup.setup_id else encounter_lookup(setup_id)

    def lookup_for_persistence(setup_id: str) -> EncounterSetup:
        return setup if setup_id == setup.setup_id else persistence_lookup(setup_id)

    # The definitions remain ordinary staged/catalog definitions. Only this
    # test-local setup ID is added to the two runtime lookup tables needed for
    # start and save/load; it never becomes a picker/catalog entry.
    monkeypatch.setattr(encounter_module, "get_setup", lookup_for_encounter)
    monkeypatch.setattr(persistence_module, "get_setup", lookup_for_persistence)
    return setup


def test_halo_heals_from_another_caster_and_tracks_moved_recipient(
    cross_caster_setup: EncounterSetup, tmp_path: Path
) -> None:
    # Setup-order initiative draws are Halo caster, healer, Fighter, dog. The
    # dog acts after Halo and before the healer, and both dog attacks are real
    # critical jaws hits (d20 20, d4 2), dealing 6 damage each.
    rolls = (20, 10, 1, 10, 20, 2, 4, 20, 2, 4, 20, 1)
    game = Encounter.start(cross_caster_setup, rolls=rolls)
    assert all(actor.hp == actor.max_hp for actor in game.inspect().actors)
    _finish_initial_choices(game)
    assert game.inspect().turn_actor_id == "halo_sorcerer"

    halo_offer = game.execute(Cast("angelic_halo", actions=1))
    assert halo_offer.status is ResultStatus.PAUSED
    assert _actor(game, "halo_sorcerer").focus_points == 0
    assert _actor(game, "halo_sorcerer").spontaneous_slots[0].remaining == 3
    halo_recipient = halo_offer.inspection.choice
    assert halo_recipient is not None
    assert {option.option_id for option in halo_recipient.options} == {
        "halo_sorcerer",
        "healer_sorcerer",
        "injured_fighter",
    }
    _choose(game, "halo_sorcerer", status=ResultStatus.COMPLETED)
    assert any(
        effect.kind == "angelic_halo" and effect.value == 2
        for effect in _actor(game, "halo_sorcerer").effects
    )
    assert game.inspect().turn_actor_id == "halo_sorcerer"
    assert game.execute(EndTurn()).status is ResultStatus.COMPLETED

    # The dog closes and injures the Fighter through the ordinary Strike path.
    assert game.inspect().turn_actor_id == "guard_dog"
    assert game.execute(Stride((Position(4, 2),))).status is ResultStatus.COMPLETED
    dog_hit = game.execute(Strike("injured_fighter", attack_id="jaws"))
    assert dog_hit.status is ResultStatus.COMPLETED
    dog_damage = next(event.damage for event in dog_hit.events if event.damage is not None)
    assert dog_damage is not None and dog_damage.total == 6
    assert _actor(game, "injured_fighter").hp == 15

    # Moving away provokes the Fighter's real reaction prompt; declining it
    # lets the dog finish its turn and keeps the sequence public and legal.
    assert game.execute(Stride((Position(5, 2),))).status is ResultStatus.PAUSED
    _decline_reaction(game)
    assert game.inspect().turn_actor_id == "healer_sorcerer"

    # This is a second Sorcerer's actual spontaneous Heal. The injured
    # recipient is inside the Halo (10 feet from its source), so Halo's +2
    # status benefit wins over that caster's +1 Sorcerous Potency. Save while
    # the genuine target willingness choice is pending.
    first_offer = game.execute(
        Cast("heal", "injured_fighter", actions=2, slot_id="angelic_rank1")
    )
    assert first_offer.status is ResultStatus.PAUSED
    first_blood = first_offer.inspection.choice
    assert first_blood is not None and first_blood.kind == "spell_blood_magic_recipient"
    _choose(game, "healer_sorcerer", status=ResultStatus.PAUSED)
    first_willingness = game.inspect().choice
    assert first_willingness is not None and first_willingness.kind == "spell_willingness"
    assert _actor(game, "healer_sorcerer").spontaneous_slots[0].remaining == 2

    save_path = tmp_path / "halo-cross-caster-willingness.json"
    game.save(save_path)
    resumed = Encounter.load(save_path)
    assert resumed.inspect() == game.inspect()
    assert resumed.inspect().choice is not None
    assert resumed.inspect().choice.kind == "spell_willingness"
    healed_inside = resumed.choose(
        resumed.inspect().choice.choice_id,
        "willing",
        resumed.inspect().choice.owner_actor_id,
    )
    assert healed_inside.status is ResultStatus.COMPLETED
    healing_inside = next(event for event in healed_inside.events if event.kind == "healing")
    assert healing_inside.actor_id == "healer_sorcerer"
    assert healing_inside.target_id == "injured_fighter"
    assert healing_inside.text == (
        "Injured Fighter heals 14 HP (1d8 4 + 8 + Angelic Halo 2 status); now at 21 HP."
    )
    assert "+ Sorcerous Potency" not in healing_inside.text
    assert "+ 3 status" not in healing_inside.text
    assert _actor(resumed, "injured_fighter").hp == 21

    # The living recipient then moves from 10 feet from the Halo source to
    # 25 feet away. This is a real Stride from a living, injured participant.
    assert resumed.execute(EndTurn()).status is ResultStatus.COMPLETED
    assert resumed.inspect().turn_actor_id == "injured_fighter"
    moved = resumed.execute(
        Stride((Position(4, 1), Position(5, 1), Position(6, 1)))
    )
    assert moved.status is ResultStatus.COMPLETED
    assert _actor(resumed, "injured_fighter").position == Position(6, 1)
    assert _actor(resumed, "halo_sorcerer").position == Position(1, 2)
    assert resumed.execute(EndTurn()).status is ResultStatus.COMPLETED
    assert resumed.inspect().turn_actor_id == "halo_sorcerer"
    assert resumed.execute(EndTurn()).status is ResultStatus.COMPLETED
    assert resumed.inspect().turn_actor_id == "guard_dog"

    # A second actual dog hit occurs while the recipient is outside the 15-foot
    # aura, then the same second caster heals again. Halo must follow the
    # recipient's current position at resolution and therefore no longer add
    # its +2; the applicable +1 Potency remains.
    second_dog_hit = resumed.execute(Strike("injured_fighter", attack_id="jaws"))
    assert second_dog_hit.status is ResultStatus.COMPLETED
    second_damage = next(event.damage for event in second_dog_hit.events if event.damage is not None)
    assert second_damage is not None and second_damage.total == 6
    assert _actor(resumed, "injured_fighter").hp == 15
    assert resumed.execute(EndTurn()).status is ResultStatus.COMPLETED
    assert resumed.inspect().turn_actor_id == "healer_sorcerer"

    second_offer = resumed.execute(
        Cast("heal", "injured_fighter", actions=2, slot_id="angelic_rank1")
    )
    assert second_offer.status is ResultStatus.PAUSED
    second_blood = second_offer.inspection.choice
    assert second_blood is not None and second_blood.kind == "spell_blood_magic_recipient"
    _choose(resumed, "healer_sorcerer", status=ResultStatus.PAUSED)
    second_willingness = resumed.inspect().choice
    assert second_willingness is not None and second_willingness.kind == "spell_willingness"
    healed_outside = resumed.choose(
        second_willingness.choice_id,
        "willing",
        second_willingness.owner_actor_id,
    )
    assert healed_outside.status is ResultStatus.COMPLETED
    healing_outside = next(event for event in healed_outside.events if event.kind == "healing")
    assert healing_outside.actor_id == "healer_sorcerer"
    assert healing_outside.target_id == "injured_fighter"
    assert healing_outside.text == (
        "Injured Fighter heals 13 HP (1d8 4 + 8 + Sorcerous Potency 1 status); now at 21 HP."
    )
    assert "Angelic Halo" not in healing_outside.text
    assert "+ 3 status" not in healing_outside.text
    assert _actor(resumed, "healer_sorcerer").spontaneous_slots[0].remaining == 1
    assert _actor(resumed, "halo_sorcerer").focus_points == 0

    # Finish through the ordinary public Strike and Hero choice path.
    assert resumed.execute(EndTurn()).status is ResultStatus.COMPLETED
    finishing_strike = resumed.execute(Strike("guard_dog", attack_id="longsword"))
    assert finishing_strike.status is ResultStatus.PAUSED
    finish_choice = finishing_strike.inspection.choice
    assert finish_choice is not None and finish_choice.kind == "attack_hero_reroll"
    finished = resumed.choose(finish_choice.choice_id, "keep", finish_choice.owner_actor_id)
    assert finished.status is ResultStatus.COMPLETED
    final = resumed.inspect()
    assert not final.in_progress
    assert final.winner_team == "blue"
    assert _actor(resumed, "guard_dog").defeated
