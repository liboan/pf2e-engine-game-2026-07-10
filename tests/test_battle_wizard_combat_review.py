"""Independent source/play review of the staged Battle Magic Wizard group.

Sources checked 2026-09-17:

* Wizard and Arcane Bond: https://2e.aonprd.com/Classes.aspx?ID=39
* School of Battle Magic: https://2e.aonprd.com/ArcaneSchools.aspx?ID=22
* Force Bolt: https://2e.aonprd.com/Spells.aspx?ID=1896
* Force Barrage: https://2e.aonprd.com/Spells.aspx?ID=1536
* Breathe Fire: https://2e.aonprd.com/Spells.aspx?ID=1457

The numerical expectations precede observations. Force Bolt is Focus 1, one
action, manipulate, range 30 feet, and automatically deals 1d4+1 force with
no attack roll or MAP. Force Barrage takes 1--3 actions, has range 120 feet,
and fires one automatic 1d4+1 force shard per action; same-target shards are
combined before damage adjustments. Breathe Fire takes two actions and deals
one shared 2d6 fire result in a 15-foot cone, with a basic Reflex save per
creature. Drain Bonded Item is a once-daily free action requiring the bonded
item on the wizard's person; during that turn, it permits one spell prepared
today and already cast to be cast again without spending another slot.
At level 1, a wizard has two ordinary rank-1 slots and one extra curriculum
slot; this staged two-slot combat subset therefore exposes one of each, while
Battle Magic makes both represented spells legal curriculum choices.
"""

from pathlib import Path

import pytest

import pf2e.content as content
from pf2e.content import get_setup
from pf2e.encounter import Encounter
from pf2e.model import (
    Cast,
    Choose,
    CreaturePlacement,
    EncounterSetup,
    Position,
    Release,
    ResultStatus,
)
from pf2e.wizard import DrainBondedItem
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
        assert choice.kind in {"initiative_hero_reroll", "initiative_tie"}
        option_id = "keep" if any(item.option_id == "keep" for item in choice.options) else choice.options[0].option_id
        assert _choose(game, option_id).status in {ResultStatus.PAUSED, ResultStatus.COMPLETED}
    raise AssertionError("initiative did not settle")


def _game(*, rolls: tuple[int, ...]) -> Encounter:
    game = Encounter.start(
        get_setup("staged_battle_magic_wizard_vs_two_guard_dogs"), rolls=rolls
    )
    _settle_initiative(game)
    assert game.inspect().turn_actor_id == "wizard"
    return game


def test_empty_breathe_fire_is_completed_cast_eligible_for_arcane_bond() -> None:
    game = _game(rolls=(20, 1, 1, 3, 4))
    result = game.execute(
        Cast("breathe_fire", actions=2, area_direction=Position(-1, 0))
    )
    assert result.status is ResultStatus.COMPLETED
    assert not any(event.kind == "spell_damage" for event in result.events)
    wizard = game._state.creatures["wizard"]
    assert next(
        slot for slot in wizard.prepared_slots if slot.slot_id == "wizard_breathe_fire"
    ).spent
    assert game.execute(DrainBondedItem("wizard:bonded_staff")).status is ResultStatus.COMPLETED


def test_staged_preparations_have_one_curriculum_and_one_ordinary_slot() -> None:
    slots = BATTLE_MAGIC_WIZARD.prepared_spells
    assert {slot.spell_id for slot in slots} == {"shield", "electric_arc", "frostbite", "ignition", "caustic_blast", "gouging_claw", "force_barrage", "breathe_fire", "enfeeble"}
    assert [slot.source for slot in slots].count("battle_magic_curriculum") == 2
    assert [slot.source for slot in slots].count("ordinary_rank_1") == 2


def test_three_action_force_barrage_groups_same_recipient_before_damage() -> None:
    # Initiative; two shards on Dog A roll 1 and 4, one on Dog B rolls 3.
    game = _game(rolls=(20, 1, 1, 1, 4, 3))
    result = game.execute(Cast(
        "force_barrage",
        actions=3,
        target_ids=("dog_a", "dog_a", "dog_b"),
    ))

    assert result.status is ResultStatus.COMPLETED
    damage = [event for event in result.events if event.kind == "spell_damage"]
    assert [(event.target_id, event.damage.total) for event in damage if event.damage] == [
        ("dog_a", 7),
        ("dog_b", 4),
    ]
    wizard = game._state.creatures["wizard"]
    assert wizard.actions_remaining == 0
    assert wizard.arcane_bond_eligible_slots == {"wizard_force_barrage"}


def test_breathe_fire_shared_roll_applies_all_four_basic_save_degrees(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    setup = EncounterSetup(
        setup_id="review_battle_wizard_four_basic_saves",
        name="Review Battle Wizard four basic saves",
        width=6,
        height=5,
        placements=(
            CreaturePlacement("wizard", BATTLE_MAGIC_WIZARD.definition_id, "Wizard", "blue", Position(1, 2)),
            CreaturePlacement("critical_success", "guard_dog_mc2924", "Critical Success", "red", Position(2, 2)),
            CreaturePlacement("success", "guard_dog_mc2924", "Success", "red", Position(3, 1)),
            CreaturePlacement("failure", "guard_dog_mc2924", "Failure", "red", Position(3, 2)),
            CreaturePlacement("critical_failure", "guard_dog_mc2924", "Critical Failure", "red", Position(3, 3)),
        ),
    )
    monkeypatch.setattr(content, "_STAGED_SETUPS", content._STAGED_SETUPS | {setup.setup_id: setup})
    # Initiative; shared 3+4 damage; Reflex rolls 20, 10, 9, 1 at +7 vs DC 17.
    game = Encounter.start(setup, rolls=(20, 1, 2, 3, 4, 3, 4, 20, 10, 9, 1))
    _settle_initiative(game)
    assert game._breathe_fire_targets(
        game._state, game._state.creatures["wizard"], Position(1, 0)
    ) == ("critical_success", "success", "failure", "critical_failure")

    result = game.execute(Cast("breathe_fire", actions=2, area_direction=Position(1, 0)))
    assert result.status is ResultStatus.COMPLETED
    damage = {
        event.target_id: event.damage.total
        for event in result.events
        if event.kind == "spell_damage" and event.damage is not None
    }
    assert damage == {
        "critical_success": 0,
        "success": 3,
        "failure": 7,
        "critical_failure": 14,
    }


def test_disrupted_prepared_barrage_spends_cost_but_is_not_bond_eligible() -> None:
    game = Encounter.start(
        get_setup("staged_battle_magic_wizard_reactive_strike"),
        rolls=(20, 1, 20, 1),
    )
    _settle_initiative(game)
    started = game.execute(Cast(
        "force_barrage", actions=1, target_ids=("reactive_fighter",)
    ))
    assert started.status is ResultStatus.PAUSED
    reaction = game.inspect().choice
    assert reaction is not None and reaction.kind == "reaction"
    assert _choose(game, "accept").status is ResultStatus.PAUSED
    disrupted = _choose(game, "keep")

    assert disrupted.status is ResultStatus.COMPLETED
    assert any(event.kind == "disrupted" for event in disrupted.events)
    assert not any(event.kind == "spell_damage" for event in disrupted.events)
    wizard = game._state.creatures["wizard"]
    slot = next(slot for slot in wizard.prepared_slots if slot.slot_id == "wizard_force_barrage")
    assert slot.spent and wizard.actions_remaining == 2
    assert wizard.arcane_bond_eligible_slots == set()
    assert game.execute(DrainBondedItem("wizard:bonded_staff")).status is ResultStatus.REJECTED


def test_saved_bond_permission_survives_atomic_mismatch_then_recasts_variable_spell(
    tmp_path: Path,
) -> None:
    game = _game(rolls=(20, 1, 1, 1, 2, 3))
    assert game.execute(Cast(
        "force_barrage", actions=1, target_ids=("dog_a",)
    )).status is ResultStatus.COMPLETED
    drained = game.execute(DrainBondedItem("wizard:bonded_staff"))
    assert drained.status is ResultStatus.COMPLETED
    assert game._state.creatures["wizard"].actions_remaining == 2

    path = tmp_path / "review-wizard-bond-permission.json"
    game.save(path)
    game = Encounter.load(path)
    before = game.inspect()
    dice_before = game._dice.to_data()
    rejected = game.execute(Cast(
        "breathe_fire",
        actions=2,
        slot_id="wizard_force_barrage",
        area_direction=Position(1, 0),
        use_arcane_bond=True,
    ))
    assert rejected.status is ResultStatus.REJECTED
    assert game.inspect() == before and game._dice.to_data() == dice_before

    recast = game.execute(Cast(
        "force_barrage",
        actions=2,
        slot_id="wizard_force_barrage",
        target_ids=("dog_a", "dog_b"),
        use_arcane_bond=True,
    ))
    assert recast.status is ResultStatus.COMPLETED
    wizard = game._state.creatures["wizard"]
    slot = next(slot for slot in wizard.prepared_slots if slot.slot_id == "wizard_force_barrage")
    assert slot.spent and wizard.actions_remaining == 0
    assert wizard.arcane_bond_recast_until_start == 0
    # The completed-cast history can still name this slot; the daily-use and
    # current-turn permission gates prevent another drain or bonded recast.
    assert wizard.arcane_bond_used_day == game._state.preparation_day
    assert game.execute(DrainBondedItem("wizard:bonded_staff")).status is ResultStatus.REJECTED
    assert game.execute(Cast(
        "force_barrage",
        actions=1,
        slot_id="wizard_force_barrage",
        target_ids=("dog_b",),
        use_arcane_bond=True,
    )).status is ResultStatus.REJECTED


def test_released_bonded_staff_blocks_drain_without_spending_daily_use() -> None:
    game = _game(rolls=(20, 1, 1, 1))
    assert game.execute(Cast(
        "force_barrage", actions=1, target_ids=("dog_a",)
    )).status is ResultStatus.COMPLETED
    assert game.execute(Release("wizard:bonded_staff")).status is ResultStatus.COMPLETED
    wizard = game._state.creatures["wizard"]
    rejected = game.execute(DrainBondedItem("wizard:bonded_staff"))
    assert rejected.status is ResultStatus.REJECTED
    assert wizard.arcane_bond_used_day != game._state.preparation_day
    assert wizard.arcane_bond_eligible_slots == {"wizard_force_barrage"}
