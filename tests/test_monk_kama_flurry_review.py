"""Independent source/play review of the staged kama/kama Flurry slice.

Sources checked 2026-09-16:

* Monk and Flurry of Blows: https://2e.aonprd.com/Classes.aspx?ID=60
* Subordinate actions: https://2e.aonprd.com/Rules.aspx?ID=2335

Flurry is one action with flourish, makes two ordinary subordinate Strikes,
and applies MAP normally. If both hit one creature, their damage is combined
for weaknesses and resistances. Monastic Weaponry permits the selected melee
monk weapon to replace the otherwise-required unarmed Strikes.
"""

from dataclasses import replace
from pathlib import Path
from types import MappingProxyType

import pytest

import pf2e.content as content
from pf2e import EndTurn, RaiseShield
from pf2e.damage import DamageDefense
from pf2e.encounter import Encounter
from pf2e.justice_content import JUSTICE_CHAMPION
from pf2e.model import (
    Choose,
    CreaturePlacement,
    EncounterSetup,
    PairedStrikeSelection,
    Position,
    ResultStatus,
)
from pf2e.monk import FlurryOfBlows
from pf2e.paired_strikes import _decode_selection
from pf2e.ranger_monk_content import MONK


def _choose(game: Encounter, option_id: str):
    choice = game.inspect().choice
    assert choice is not None
    return game.execute(Choose(choice.choice_id, option_id, choice.owner_actor_id))


def _settle_initiative(game: Encounter) -> None:
    for _ in range(12):
        choice = game.inspect().choice
        if choice is None:
            return
        options = {item.option_id for item in choice.options}
        option_id = "keep" if "keep" in options else choice.options[0].option_id
        assert _choose(game, option_id).status in {ResultStatus.PAUSED, ResultStatus.COMPLETED}
    raise AssertionError("initiative did not settle")


def _default_second_option(game: Encounter, *, target_id: str) -> str:
    choice = game.inspect().choice
    assert choice is not None and choice.kind == "family_action"
    for option in choice.options:
        selection = _decode_selection(option.option_id)
        if selection is not None and selection.target_id == target_id and selection.nonlethal is None:
            return option.option_id
    raise AssertionError(f"no default kama option for {target_id}")


def test_one_action_normal_map_and_saved_flourish_rejection_are_atomic(tmp_path: Path) -> None:
    game = Encounter.start(
        content.get_setup("staged_monk_kama_flurry"),
        rolls=(20, 1, 1, 1, 1),
    )
    _settle_initiative(game)
    monk = game._state.creatures["monk"]
    assert monk.actions_remaining == 3 and monk.strikes_this_turn == 0

    first = game.execute(FlurryOfBlows(PairedStrikeSelection("guard_dog_a", "kama")))
    assert first.status is ResultStatus.PAUSED
    first = _choose(game, "keep")
    first_check = next(event.check for event in first.events if event.kind == "strike")
    assert first_check is not None and (first_check.map_penalty, first_check.attack_count) == (0, 1)
    path = tmp_path / "review-monk-flourish-choice.json"
    game.save(path)
    game = Encounter.load(path)

    second = _choose(game, _default_second_option(game, target_id="guard_dog_b"))
    assert second.status is ResultStatus.PAUSED
    second = _choose(game, "keep")
    second_check = next(event.check for event in second.events if event.kind == "strike")
    assert second_check is not None and (second_check.map_penalty, second_check.attack_count) == (-4, 2)
    monk = game._state.creatures["monk"]
    assert monk.actions_remaining == 2 and monk.strikes_this_turn == 2

    before, dice_before = game.inspect(), game._dice.to_data()
    blocked = game.execute(FlurryOfBlows(PairedStrikeSelection("guard_dog_a", "kama")))
    assert blocked.status is ResultStatus.REJECTED
    assert game.inspect() == before and game._dice.to_data() == dice_before


def test_saved_shield_choice_keeps_current_hit_iwr_then_carries_it_to_second_hit(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    ward_definition = replace(
        content.STEEL_SHIELD_FIGHTER_M,
        definition_id="review_shielded_typed_ward",
        name="Review Shielded Typed Ward",
        damage_defenses=(
            DamageDefense("weakness", "slashing", 3, source="review cracked ward"),
            DamageDefense("resistance", "all", 2, source="review waystone ward"),
        ),
    )
    monkeypatch.setattr(
        content,
        "_STAGED_CREATURES",
        MappingProxyType({**content._STAGED_CREATURES, ward_definition.definition_id: ward_definition}),
    )
    setup = EncounterSetup(
        setup_id="review_monk_flurry_shielded_iwr",
        name="Review Monk Flurry against shielded ward",
        width=4,
        height=3,
        placements=(
            CreaturePlacement("monk", MONK.definition_id, "Monk", "blue", Position(1, 1)),
            CreaturePlacement(
                "ward", ward_definition.definition_id, "Shielded Ward", "red", Position(2, 1)
            ),
        ),
    )
    monkeypatch.setattr(content, "_STAGED_SETUPS", content._STAGED_SETUPS | {setup.setup_id: setup})
    game = Encounter.start(setup, rolls=(1, 20, 19, 1, 19, 1))
    _settle_initiative(game)
    assert game.inspect().turn_actor_id == "ward"
    assert game.execute(RaiseShield()).status is ResultStatus.COMPLETED
    assert game.execute(EndTurn()).status is ResultStatus.COMPLETED

    ward_before = game._state.creatures["ward"].hp
    started = game.execute(FlurryOfBlows(PairedStrikeSelection("ward", "kama")))
    assert started.status is ResultStatus.PAUSED
    offered = _choose(game, "keep")
    assert offered.inspection.choice is not None and offered.inspection.choice.kind == "shield_block"
    path = tmp_path / "review-flurry-shield.json"
    game.save(path)
    game = Encounter.load(path)
    first = _choose(game, "decline")
    first_damage = next(event.damage for event in first.events if event.kind == "damage")
    assert first_damage is not None and first_damage.total == 4
    assert game._state.creatures["ward"].hp == ward_before - 4

    second = _choose(game, _default_second_option(game, target_id="ward"))
    assert second.status is ResultStatus.PAUSED
    second = _choose(game, "keep")
    assert second.inspection.choice is not None and second.inspection.choice.kind == "shield_block"
    second = _choose(game, "decline")
    second_damage = next(event.damage for event in second.events if event.kind == "damage")
    assert second_damage is not None and second_damage.total == 3
    assert game._state.creatures["ward"].hp == ward_before - 7


def test_justice_retaliation_does_not_replace_the_first_flurry_outcome(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    setup = EncounterSetup(
        setup_id="review_monk_flurry_justice",
        name="Review Monk Flurry through Justice",
        width=4,
        height=4,
        placements=(
            CreaturePlacement("monk", MONK.definition_id, "Monk", "blue", Position(1, 1)),
            CreaturePlacement(
                "protected", "fighter_m_steel_shield_level_1", "Protected Ally", "red", Position(2, 1)
            ),
            CreaturePlacement(
                "champion", JUSTICE_CHAMPION.definition_id, "Justice Champion", "red", Position(2, 2)
            ),
        ),
    )
    monkeypatch.setattr(content, "_STAGED_SETUPS", content._STAGED_SETUPS | {setup.setup_id: setup})
    game = Encounter.start(setup, rolls=(20, 1, 2, 14, 1, 20, 1))
    _settle_initiative(game)

    started = game.execute(FlurryOfBlows(PairedStrikeSelection("protected", "kama")))
    assert started.status is ResultStatus.PAUSED
    justice = _choose(game, "keep")
    assert justice.inspection.choice is not None and justice.inspection.choice.kind == "reaction"
    retaliation = _choose(game, "accept")
    assert retaliation.status is ResultStatus.PAUSED
    assert retaliation.inspection.choice is not None and retaliation.inspection.choice.kind == "attack_hero_reroll"
    resumed = _choose(game, "keep")

    assert resumed.status is ResultStatus.PAUSED
    assert resumed.inspection.choice is not None and resumed.inspection.choice.kind == "family_action"
    pending = game._state.pending_choice
    assert pending is not None and pending.paired_strike is not None
    first_outcome = pending.paired_strike.outcomes[0]
    assert first_outcome.target_id == "protected" and first_outcome.attack_id == "kama"
    assert first_outcome.check.die == 14 and first_outcome.check.map_penalty == 0
    assert first_outcome.damage is not None
    assert first_outcome.damage.components[0].source == "kama"
    assert first_outcome.damage.total == 0  # raw 3, Justice resistance 3 for this event


def test_same_type_defenses_are_tracked_per_recipient(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    setup = EncounterSetup(
        setup_id="review_monk_flurry_two_wards",
        name="Review Monk Flurry against separate wards",
        width=4,
        height=4,
        placements=(
            CreaturePlacement("monk", MONK.definition_id, "Monk", "blue", Position(1, 1)),
            CreaturePlacement(
                "ward_a", "warpriest_c_typed_defense_test_grant", "Ward A", "red", Position(2, 1)
            ),
            CreaturePlacement(
                "ward_b", "warpriest_c_typed_defense_test_grant", "Ward B", "red", Position(1, 2)
            ),
        ),
    )
    monkeypatch.setattr(content, "_STAGED_SETUPS", content._STAGED_SETUPS | {setup.setup_id: setup})
    game = Encounter.start(setup, rolls=(20, 1, 2, 19, 1, 19, 1))
    _settle_initiative(game)
    hp_a = game._state.creatures["ward_a"].hp
    hp_b = game._state.creatures["ward_b"].hp

    first = game.execute(FlurryOfBlows(PairedStrikeSelection("ward_a", "kama")))
    assert first.status is ResultStatus.PAUSED
    first = _choose(game, "keep")
    assert game._state.creatures["ward_a"].hp == hp_a - 4

    second = _choose(game, _default_second_option(game, target_id="ward_b"))
    assert second.status is ResultStatus.PAUSED
    second = _choose(game, "keep")
    assert second.status is ResultStatus.COMPLETED
    assert game._state.creatures["ward_b"].hp == hp_b - 4


def test_justice_knockout_interrupts_flurry_before_second_strike(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    setup = EncounterSetup(
        setup_id="review_monk_flurry_justice_knockout",
        name="Review Justice interruption of Monk Flurry",
        width=4,
        height=4,
        placements=(
            CreaturePlacement("monk", MONK.definition_id, "Monk", "blue", Position(1, 1)),
            CreaturePlacement(
                "protected", "fighter_m_steel_shield_level_1", "Protected Ally", "red", Position(2, 1)
            ),
            CreaturePlacement(
                "champion", JUSTICE_CHAMPION.definition_id, "Justice Champion", "red", Position(2, 2)
            ),
        ),
    )
    monkeypatch.setattr(content, "_STAGED_SETUPS", content._STAGED_SETUPS | {setup.setup_id: setup})
    game = Encounter.start(setup, rolls=(20, 1, 2, 14, 1, 20, 1))
    _settle_initiative(game)
    game._state.creatures["monk"].hp = 1

    assert game.execute(FlurryOfBlows(PairedStrikeSelection("protected", "kama"))).status is ResultStatus.PAUSED
    justice = _choose(game, "keep")
    assert justice.inspection.choice is not None and justice.inspection.choice.kind == "reaction"
    retaliation = _choose(game, "accept")
    assert retaliation.inspection.choice is not None and retaliation.inspection.choice.kind == "attack_hero_reroll"
    health = _choose(game, "keep")
    assert health.inspection.choice is not None and health.inspection.choice.kind == "heroic_recovery_damage"
    path = tmp_path / "review-flurry-justice-knockout.json"
    game.save(path)
    game = Encounter.load(path)

    stopped = _choose(game, "normal")
    monk = game._state.creatures["monk"]
    assert monk.unconscious and monk.dying > 0
    assert not any(event.kind == "paired_strike_complete" for event in stopped.events)
    assert game.inspect().choice is None or game.inspect().choice.kind != "family_action"
