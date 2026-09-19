"""Public physical weapon identity and transfer regressions."""

import json
from pathlib import Path

from pf2e.content import get_setup
from pf2e.encounter import Encounter
from pf2e.model import EndTurn, Interact, Position, Release, ResultStatus, Strike, Stride


TRANSFER_SETUP = get_setup("staged_weapon_identity_transfer")


def _keep_initiative(game: Encounter) -> None:
    while (choice := game.inspect().choice) is not None:
        assert choice.kind in {"initiative_hero_reroll", "initiative_tie"}
        option_id = "keep" if any(option.option_id == "keep" for option in choice.options) else choice.options[0].option_id
        game.choose(choice.choice_id, option_id)


def _actor(game: Encounter, actor_id: str):
    return next(actor for actor in game.inspect().actors if actor.actor_id == actor_id)


def test_transferred_weapon_requires_identity_selection_and_round_trips_saved_strike(
    tmp_path: Path,
) -> None:
    game = Encounter.start(
        TRANSFER_SETUP,
        rolls=(20, 19, 18, 1, 20, 8),
    )
    _keep_initiative(game)
    assert game.inspect().turn_actor_id == "weapon_source"
    assert _actor(game, "weapon_source").held_items == ("weapon_source:longsword",)
    assert _actor(game, "weapon_recipient").held_items == ("weapon_recipient:longsword",)

    # The appended item_id field preserves the old positional Strike command.
    initial = game.execute(Strike("weapon_dog", "longsword"))
    assert initial.status is ResultStatus.PAUSED
    initial_choice = initial.inspection.choice
    assert initial_choice is not None and initial_choice.kind == "attack_hero_reroll"
    game.choose(initial_choice.choice_id, "keep")

    game.execute(Release("weapon_source:longsword"))
    assert game.execute(Stride((Position(1, 0),))).status is ResultStatus.COMPLETED
    game.execute(EndTurn())
    assert game.inspect().turn_actor_id == "weapon_recipient"
    assert game.execute(Stride((Position(1, 1),))).status is ResultStatus.COMPLETED
    assert game.execute(Interact("retrieve", "weapon_source:longsword")).status is ResultStatus.COMPLETED
    recipient = _actor(game, "weapon_recipient")
    assert recipient.held_items == ("weapon_recipient:longsword", "weapon_source:longsword")

    before_ambiguous = game.inspect()
    ambiguous = game.execute(Strike("weapon_dog", attack_id="longsword"))
    assert ambiguous.status is ResultStatus.REJECTED
    assert "Multiple held Longsword items" in ambiguous.message
    assert ambiguous.inspection == before_ambiguous

    before_wrong_item = game.inspect()
    wrong_item = game.execute(
        Strike("weapon_dog", attack_id="longsword", item_id="weapon_dog:longsword")
    )
    assert wrong_item.status is ResultStatus.REJECTED
    assert "not held and compatible" in wrong_item.message
    assert wrong_item.inspection == before_wrong_item

    selected = game.execute(
        Strike("weapon_dog", attack_id="longsword", item_id="weapon_source:longsword")
    )
    assert selected.status is ResultStatus.PAUSED
    selected_choice = selected.inspection.choice
    assert selected_choice is not None and selected_choice.kind == "attack_hero_reroll"
    path = tmp_path / "transferred-selected-strike.json"
    game.save(path)
    saved = json.loads(path.read_text(encoding="utf-8"))
    assert saved["state"]["pending_choice"]["item_id"] == "weapon_source:longsword"

    restored = Encounter.load(path)
    assert restored.inspect() == selected.inspection
    result = restored.choose(selected_choice.choice_id, "keep")
    check = next(event.check for event in result.events if event.check is not None)
    damage = next(event.damage for event in result.events if event.damage is not None)
    assert check is not None and check.die == 20 and check.degree.name == "CRITICAL_SUCCESS"
    assert damage is not None and damage.components[0].rolls == (8,)
    assert _actor(restored, "weapon_dog").dead
    assert _actor(restored, "weapon_recipient").held_items == (
        "weapon_recipient:longsword",
        "weapon_source:longsword",
    )


def test_saved_reactive_strike_keeps_selected_transferred_weapon_identity(
    tmp_path: Path,
) -> None:
    game = Encounter.start(TRANSFER_SETUP, rolls=(20, 19, 18, 10, 1))
    _keep_initiative(game)
    assert game.inspect().turn_actor_id == "weapon_source"
    game.execute(EndTurn())
    assert game.inspect().turn_actor_id == "weapon_recipient"
    # Move the second compatible fighter out of the dog's reach so the source
    # is the only reactor for the dog's movement.
    assert game.execute(Stride((Position(3, 1),))).status is ResultStatus.COMPLETED
    game.execute(EndTurn())
    assert game.inspect().turn_actor_id == "weapon_dog"

    movement = game.execute(Stride((Position(2, 2),)))
    assert movement.status is ResultStatus.PAUSED
    reaction_choice = movement.inspection.choice
    assert reaction_choice is not None and reaction_choice.kind == "reaction"
    selected_option = next(
        option
        for option in reaction_choice.options
        if "[weapon_source:longsword]" in option.label
        and "slashing" in option.label
        and "lethal" in option.label
    )
    reaction = game.choose(reaction_choice.choice_id, selected_option.option_id)
    pending = reaction.inspection.choice
    assert reaction.status is ResultStatus.PAUSED
    assert pending is not None and pending.kind == "attack_hero_reroll"
    assert pending.owner_actor_id == "weapon_source"

    path = tmp_path / "saved-selected-reactive-strike.json"
    game.save(path)
    saved = json.loads(path.read_text(encoding="utf-8"))
    assert saved["state"]["pending_choice"]["item_id"] == "weapon_source:longsword"

    restored = Encounter.load(path)
    assert restored.inspect() == reaction.inspection
    result = restored.choose(pending.choice_id, "keep")
    assert result.inspection.choice is None
    assert _actor(restored, "weapon_source").reaction_available is False
    assert _actor(restored, "weapon_dog").position == Position(2, 2)
    assert _actor(restored, "weapon_dog").hp == 3
