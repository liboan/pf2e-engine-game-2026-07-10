"""Independent review of the selected Monk's fist and same-attack Flurry.

Sources checked 2026-09-16:

* Monk class, Powerful Fist, and Flurry of Blows:
  https://2e.aonprd.com/Classes.aspx?ID=60
* Shield Block: https://2e.aonprd.com/Feats.aspx?ID=5212
* Subordinate actions: https://2e.aonprd.com/Rules.aspx?ID=2335

Powerful Fist makes the fist d6 and removes the ordinary -2 circumstance
penalty for choosing lethal damage with a nonlethal unarmed attack. Flurry is
one flourish action, uses two ordinary unarmed Strikes, and applies MAP. Shield
Block applies to physical attack damage regardless of lethal intent.
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
    Strike,
)
from pf2e.monk import FlurryOfBlows
from pf2e.paired_strikes import _decode_selection, _encode_selection
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


def _second_option(game: Encounter, *, target_id: str, nonlethal: bool | None) -> str:
    choice = game.inspect().choice
    assert choice is not None and choice.kind == "family_action"
    for option in choice.options:
        selection = _decode_selection(option.option_id)
        if (
            selection is not None
            and selection.target_id == target_id
            and selection.nonlethal is nonlethal
        ):
            return option.option_id
    raise AssertionError(f"no matching fist option for {target_id}")


def test_powerful_fist_default_and_lethal_checks_share_the_printed_modifier(
    tmp_path: Path,
) -> None:
    for nonlethal in (None, False):
        game = Encounter.start(
            content.get_setup("staged_monk_kama_flurry"),
            rolls=(20, 1, 1, 14, 2),
        )
        _settle_initiative(game)
        started = game.execute(Strike("guard_dog_a", attack_id="fist", nonlethal=nonlethal))
        assert started.status is ResultStatus.PAUSED
        check = next(event.check for event in started.events if event.kind == "strike")
        assert check is not None and check.modifier == 7
        assert all(modifier.source != "nonlethal intent" for modifier in check.modifier_breakdown)
        path = tmp_path / f"powerful-fist-{nonlethal}.json"
        game.save(path)
        game = Encounter.load(path)
        resumed = _choose(game, "keep")
        damage = next(event.damage for event in resumed.events if event.kind == "damage")
        assert damage is not None
        assert damage.components[0].dice == (6,)
        assert damage.components[0].damage_type == "bludgeoning"


def test_powerful_fist_default_nonlethal_and_explicit_lethal_change_knockout(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    setup = EncounterSetup(
        setup_id="review_powerful_fist_pc_knockout",
        name="Review Powerful Fist intent against a PC",
        width=4,
        height=3,
        placements=(
            CreaturePlacement("monk", MONK.definition_id, "Monk", "blue", Position(1, 1)),
            CreaturePlacement("fighter", "fighter_m_level_1", "Fighter", "red", Position(2, 1)),
        ),
    )
    monkeypatch.setattr(content, "_STAGED_SETUPS", content._STAGED_SETUPS | {setup.setup_id: setup})
    for nonlethal, expected_dying in ((None, 0), (False, 2)):
        game = Encounter.start(setup, rolls=(20, 1, 20, 6))
        _settle_initiative(game)
        target = game._state.creatures["fighter"]
        target.hp = 7
        target.hero_points = 0
        started = game.execute(Strike("fighter", attack_id="fist", nonlethal=nonlethal))
        check = next(event.check for event in started.events if event.kind == "strike")
        assert check is not None and check.modifier == 7
        resolved = _choose(game, "keep")
        assert any(event.kind == "damage" for event in resolved.events)
        target = game._state.creatures["fighter"]
        assert target.unconscious and target.dying == expected_dying


def test_saved_nonlethal_fist_flurry_shield_and_iwr_keep_resolved_facts(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    ward_definition = replace(
        content.STEEL_SHIELD_FIGHTER_M,
        definition_id="review_fist_shielded_typed_ward",
        name="Review Fist Shielded Typed Ward",
        damage_defenses=(
            DamageDefense("weakness", "bludgeoning", 3, source="review cracked ward"),
            DamageDefense("resistance", "all", 2, source="review waystone ward"),
        ),
    )
    monkeypatch.setattr(
        content,
        "_STAGED_CREATURES",
        MappingProxyType({**content._STAGED_CREATURES, ward_definition.definition_id: ward_definition}),
    )
    setup = EncounterSetup(
        setup_id="review_monk_fist_flurry_shielded_iwr",
        name="Review Monk fist Flurry against shielded ward",
        width=4,
        height=3,
        placements=(
            CreaturePlacement("monk", MONK.definition_id, "Monk", "blue", Position(1, 1)),
            CreaturePlacement("ward", ward_definition.definition_id, "Ward", "red", Position(2, 1)),
        ),
    )
    monkeypatch.setattr(content, "_STAGED_SETUPS", content._STAGED_SETUPS | {setup.setup_id: setup})
    game = Encounter.start(setup, rolls=(1, 20, 19, 6, 19, 6))
    _settle_initiative(game)
    assert game.execute(RaiseShield()).status is ResultStatus.COMPLETED
    assert game.execute(EndTurn()).status is ResultStatus.COMPLETED

    ward_hp = game._state.creatures["ward"].hp
    started = game.execute(FlurryOfBlows(PairedStrikeSelection("ward", "fist")))
    assert started.status is ResultStatus.PAUSED
    offered = _choose(game, "keep")
    assert offered.inspection.choice is not None and offered.inspection.choice.kind == "shield_block"
    path = tmp_path / "fist-flurry-shield.json"
    game.save(path)
    game = Encounter.load(path)
    blocked = _choose(game, "block")
    assert blocked.inspection.choice is not None and blocked.inspection.choice.kind == "family_action"

    pending = game._state.pending_choice
    assert pending is not None and pending.paired_strike is not None
    first = pending.paired_strike.outcomes[0]
    assert first.attack_id == "fist"
    assert first.damage_type == "bludgeoning" and first.nonlethal
    assert first.damage is not None and first.damage.total == 9
    shield = next(iter(game._state.item_instances.values()))
    assert shield.hp == 16  # physical nonlethal damage still damages the shield
    assert game._state.creatures["ward"].hp == ward_hp - 4

    second = _choose(game, _second_option(game, target_id="ward", nonlethal=None))
    assert second.status is ResultStatus.PAUSED
    finished = _choose(game, "keep")
    assert finished.status is ResultStatus.COMPLETED
    assert game._state.creatures["ward"].hp == ward_hp - 12


def test_fist_flurry_rejects_forged_mixed_attack_atomically_and_survives_justice(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    setup = EncounterSetup(
        setup_id="review_monk_fist_flurry_justice",
        name="Review fist Flurry through Justice",
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
    game = Encounter.start(setup, rolls=(20, 1, 2, 14, 2, 1))
    _settle_initiative(game)

    assert game.execute(FlurryOfBlows(PairedStrikeSelection("protected", "fist"))).status is ResultStatus.PAUSED
    reaction = _choose(game, "keep")
    assert reaction.inspection.choice is not None and reaction.inspection.choice.kind == "reaction"
    resumed = _choose(game, "decline")
    assert resumed.inspection.choice is not None and resumed.inspection.choice.kind == "family_action"
    pending = game._state.pending_choice
    assert pending is not None and pending.paired_strike is not None
    first = pending.paired_strike.outcomes[0]
    assert first.damage_type == "bludgeoning" and first.nonlethal

    choice = game.inspect().choice
    assert choice is not None
    before, dice_before = game.inspect(), game._dice.to_data()
    forged = game.execute(Choose(
        choice.choice_id,
        _encode_selection(PairedStrikeSelection("protected", "kama")),
        choice.owner_actor_id,
    ))
    assert forged.status is ResultStatus.REJECTED
    assert game.inspect() == before and game._dice.to_data() == dice_before
