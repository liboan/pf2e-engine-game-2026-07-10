"""Independent Daze checks against Player Core p. 322.

https://2e.aonprd.com/Spells.aspx?ID=1482
https://2e.aonprd.com/Rules.aspx?ID=2297
"""

import json
from types import MappingProxyType

import pytest

import pf2e.content as content
from pf2e.content import get_definition, get_setup
from pf2e.encounter import Encounter
from pf2e.model import Cast, CreaturePlacement, EncounterSetup, Position, ResultStatus
from pf2e.witch import preparation_choices


def _settle_initiative(game: Encounter) -> None:
    while (choice := game.inspect().choice) is not None:
        assert game.choose(choice.choice_id, "keep", choice.owner_actor_id).status in {
            ResultStatus.PAUSED,
            ResultStatus.COMPLETED,
        }


@pytest.mark.parametrize(
    ("save_die", "expected_hp", "expected_stun"),
    ((1, 2, 1), (10, 8, 0), (14, 11, 0), (20, 14, 0)),
)
def test_daze_respects_every_basic_will_degree(
    save_die: int, expected_hp: int, expected_stun: int,
) -> None:
    game = Encounter.start(
        get_setup("faiths_flamekeeper_daze_vs_common_speaker"),
        rolls=(20, 1, save_die, 6),
    )
    _settle_initiative(game)

    result = game.execute(Cast("daze", "enemy"))

    assert result.status is ResultStatus.COMPLETED
    assert game._state.creatures["enemy"].hp == expected_hp
    assert game._state.creatures["enemy"].stunned == expected_stun
    assert sum(event.kind == "condition_applied" for event in result.events) == expected_stun


def test_saved_daze_pc_hero_save_keeps_critical_failure_and_stun(
    monkeypatch: pytest.MonkeyPatch, tmp_path,
) -> None:
    setup = EncounterSetup(
        "review_daze_pc_hero",
        "Daze against PC Will save",
        15,
        5,
        (
            CreaturePlacement(
                "witch", "faiths_flamekeeper_witch_level_1_daze_prepared",
                "Witch", "blue", Position(1, 2),
            ),
            CreaturePlacement(
                "wizard", "wizard_battle_magic_level_1_staged",
                "Wizard", "red", Position(9, 2),
            ),
        ),
    )
    monkeypatch.setattr(
        content, "_STAGED_SETUPS",
        MappingProxyType({**content._STAGED_SETUPS, setup.setup_id: setup}),
    )
    game = Encounter.start(setup, rolls=(20, 1, 1, 6))
    _settle_initiative(game)

    paused = game.execute(Cast("daze", "wizard"))
    choice = paused.inspection.choice
    assert choice is not None and choice.kind == "spell_save_hero_reroll"
    assert choice.owner_actor_id == "wizard"
    path = tmp_path / "daze-pc-hero.json"
    game.save(path)
    restored = Encounter.load(path)
    choice = restored.inspect().choice
    assert choice is not None and choice.kind == "spell_save_hero_reroll"

    resolved = restored.choose(choice.choice_id, "keep", choice.owner_actor_id)

    assert resolved.status is ResultStatus.COMPLETED
    wizard = restored._state.creatures["wizard"]
    assert (wizard.hp, wizard.stunned, wizard.stunned_source_actor_id) == (4, 1, "witch")


def test_daze_out_of_range_rejects_without_spending_actions() -> None:
    game = Encounter.start(
        get_setup("battle_magic_wizard_daze_vs_guard_dog"), rolls=(20, 1),
    )
    _settle_initiative(game)
    game._state.creatures["dog"].position = Position(14, 2)
    before_actions = game._state.creatures["wizard"].actions_remaining

    rejected = game.execute(Cast("daze", "dog"))

    assert rejected.status is ResultStatus.REJECTED
    assert game._state.creatures["wizard"].actions_remaining == before_actions


def test_daze_witch_familiar_keeps_exactly_ten_known_cantrips() -> None:
    base = get_definition("faiths_flamekeeper_witch_level_1")
    alternate = get_definition("faiths_flamekeeper_witch_level_1_daze_prepared")
    base_slot = next(slot for slot in base.prepared_spells if slot.cantrip)
    alternate_slot = next(slot for slot in alternate.prepared_spells if slot.cantrip)

    base_choices = set(preparation_choices(base, base_slot))
    alternate_choices = set(preparation_choices(alternate, alternate_slot))

    assert len(base_choices) == len(alternate_choices) == 10
    assert alternate_choices == (base_choices - {"sigil"}) | {"daze"}


def test_saved_daze_stun_rejects_source_without_prepared_daze(tmp_path) -> None:
    game = Encounter.start(
        get_setup("faiths_flamekeeper_daze_vs_common_speaker"),
        rolls=(20, 1, 1, 6),
    )
    _settle_initiative(game)
    assert game.execute(Cast("daze", "enemy")).status is ResultStatus.COMPLETED
    path = tmp_path / "forged-daze-stun.json"
    game.save(path)
    saved = json.loads(path.read_text())
    slots = saved["state"]["creatures"]["witch"]["prepared_slots"]
    daze = next(slot for slot in slots if slot[2] == "daze")
    daze[2] = "light"
    path.write_text(json.dumps(saved))

    with pytest.raises(ValueError, match="invalid admitted stunned state"):
        Encounter.load(path)
