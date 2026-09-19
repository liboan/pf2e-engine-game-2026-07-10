"""Independent source/play review of the selected Wizard Shield cantrip.

Sources checked 2026-09-16:

* Shield: https://2e.aonprd.com/Spells.aspx?ID=1671
* School of Battle Magic: https://2e.aonprd.com/ArcaneSchools.aspx?ID=22

Shield is a one-action, hand-free cantrip granting +1 circumstance AC until
the caster's next turn. Its Hardness 5 reaction can reduce physical attack
damage or damage from a spell/magical effect. Blocking ends the spell and
prevents another casting for ten minutes.
"""

from pathlib import Path

import pytest

import pf2e.content as content
from pf2e.encounter import Encounter
from pf2e.model import Cast, Choose, CreaturePlacement, EncounterSetup, EndTurn, Position, ResultStatus, Strike
from pf2e.wizard_content import BATTLE_MAGIC_WIZARD


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


def _wizard_and_dog_setup(monkeypatch: pytest.MonkeyPatch, setup_id: str) -> EncounterSetup:
    setup = EncounterSetup(
        setup_id=setup_id,
        name="Review Shield cantrip against dog",
        width=4,
        height=3,
        placements=(
            CreaturePlacement(
                "wizard", BATTLE_MAGIC_WIZARD.definition_id, "Wizard", "blue", Position(1, 1)
            ),
            CreaturePlacement("dog", "guard_dog_mc2924", "Dog", "red", Position(2, 1)),
        ),
    )
    monkeypatch.setattr(content, "_STAGED_SETUPS", content._STAGED_SETUPS | {setup.setup_id: setup})
    return setup


def test_shield_ac_changes_attack_threshold_then_expires_at_next_start(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    setup = _wizard_and_dog_setup(monkeypatch, "review_shield_ac_threshold")
    game = Encounter.start(setup, rolls=(20, 1, 9, 9, 1))
    _settle_initiative(game)
    wizard_hp = game._state.creatures["wizard"].hp
    cast = game.execute(Cast("shield"))
    assert cast.status is ResultStatus.COMPLETED
    assert game._state.creatures["wizard"].actions_remaining == 2
    assert game.execute(EndTurn()).status is ResultStatus.COMPLETED

    protected = game.execute(Strike("wizard"))
    check = next(event.check for event in protected.events if event.kind == "strike")
    assert protected.status is ResultStatus.COMPLETED
    assert check is not None and check.total == 15 and check.dc == 16
    assert game._state.creatures["wizard"].hp == wizard_hp

    assert game.execute(EndTurn()).status is ResultStatus.COMPLETED
    assert game._state.creatures["wizard"].magic_shield_expires_at_start == 0
    assert game.execute(EndTurn()).status is ResultStatus.COMPLETED
    unprotected = game.execute(Strike("wizard"))
    check = next(event.check for event in unprotected.events if event.kind == "strike")
    assert check is not None and check.total == 15 and check.dc == 15
    assert game._state.creatures["wizard"].hp < wizard_hp


def test_zero_damage_spell_does_not_offer_magic_shield_block(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    setup = EncounterSetup(
        setup_id="review_shield_zero_damage_spell",
        name="Review Shield against zero spell damage",
        width=6,
        height=3,
        placements=(
            CreaturePlacement(
                "blue", BATTLE_MAGIC_WIZARD.definition_id, "Blue Wizard", "blue", Position(1, 1)
            ),
            CreaturePlacement(
                "red", BATTLE_MAGIC_WIZARD.definition_id, "Red Wizard", "red", Position(4, 1)
            ),
        ),
    )
    monkeypatch.setattr(content, "_STAGED_SETUPS", content._STAGED_SETUPS | {setup.setup_id: setup})
    game = Encounter.start(setup, rolls=(20, 1, 3, 4, 20))
    _settle_initiative(game)
    assert game.execute(Cast("shield")).status is ResultStatus.COMPLETED
    assert game.execute(EndTurn()).status is ResultStatus.COMPLETED

    saved_roll = game.execute(Cast("breathe_fire", actions=2, area_direction=Position(-1, 0)))
    assert saved_roll.status is ResultStatus.PAUSED
    assert saved_roll.inspection.choice is not None
    assert saved_roll.inspection.choice.kind == "spell_save_hero_reroll"
    path = tmp_path / "shield-zero-damage-save.json"
    game.save(path)
    game = Encounter.load(path)
    finished = _choose(game, "keep")

    blue = game._state.creatures["blue"]
    assert finished.status is ResultStatus.COMPLETED
    assert game.inspect().choice is None
    assert blue.magic_shield_expires_at_start > game._state.actor_start_counts["blue"]
    assert blue.reaction_available and blue.shield_recast_available_at_seconds == 0
    damage = next(event.damage for event in finished.events if event.kind == "spell_damage")
    assert damage is not None and damage.total == 0


def test_saved_magic_block_ends_ac_and_cooldown_rejection_is_atomic(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    setup = _wizard_and_dog_setup(monkeypatch, "review_shield_saved_physical_block")
    game = Encounter.start(setup, rolls=(20, 1, 20, 4))
    _settle_initiative(game)
    assert game.execute(Cast("shield")).status is ResultStatus.COMPLETED
    assert game.execute(EndTurn()).status is ResultStatus.COMPLETED
    offered = game.execute(Strike("wizard"))
    assert offered.inspection.choice is not None and offered.inspection.choice.kind == "shield_block"
    path = tmp_path / "shield-physical-block.json"
    game.save(path)
    game = Encounter.load(path)

    blocked = _choose(game, "block")
    record = next(event.shield_block for event in blocked.events if event.shield_block is not None)
    wizard = game._state.creatures["wizard"]
    assert record is not None and record.magic and record.hardness == 5
    assert record.damage_to_actor == max(0, record.incoming_damage - 5)
    assert wizard.magic_shield_expires_at_start == 0 and not wizard.reaction_available
    assert wizard.shield_recast_available_at_seconds == game._state.world_time_seconds + 600

    before, dice_before = game.inspect(), game._dice.to_data()
    rejected = game.execute(Cast("shield"))
    assert rejected.status is ResultStatus.REJECTED
    assert game.inspect() == before and game._dice.to_data() == dice_before


def test_declined_block_and_knockout_do_not_end_the_timed_spell(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    setup = _wizard_and_dog_setup(monkeypatch, "review_shield_knockout_duration")
    game = Encounter.start(setup, rolls=(20, 1, 20, 4))
    _settle_initiative(game)
    assert game.execute(Cast("shield")).status is ResultStatus.COMPLETED
    game._state.creatures["wizard"].hp = 1
    assert game.execute(EndTurn()).status is ResultStatus.COMPLETED

    offered = game.execute(Strike("wizard"))
    assert offered.inspection.choice is not None and offered.inspection.choice.kind == "shield_block"
    health = _choose(game, "decline")
    assert health.inspection.choice is not None
    assert health.inspection.choice.kind == "heroic_recovery_damage"
    assert _choose(game, "normal").status is ResultStatus.COMPLETED

    wizard = game._state.creatures["wizard"]
    assert wizard.unconscious and wizard.dying > 0
    assert wizard.magic_shield_expires_at_start == 2
    assert wizard.shield_recast_available_at_seconds == 0
