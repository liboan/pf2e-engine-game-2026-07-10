"""Independent source-led review of the staged Wizard's Spell Substitution.

Printed expectations before engine observations:

* Spell Substitution takes 10 uninterrupted minutes (600 seconds).
* It empties one prepared slot and prepares a *different* spell from the
  Wizard's spellbook in that slot.
* If interrupted, the original spell remains prepared and another attempt
  starts the full activity again.
* Wizard preparation still constrains a replacement by the slot's rank and
  source: this selected Battle Magic curriculum can prepare Breathe Fire in
  its curriculum slot, while Sure Strike is admitted only to the ordinary
  rank-1 slot.

Sources: Player Core p. 195, Spell Substitution; Player Core pp. 194-195,
Wizard spell preparation; Player Core p. 199, School of Battle Magic.
"""

from pf2e.content import get_setup
from pf2e.encounter import Encounter
from pf2e.model import Cast, EndTurn, Position, ResultStatus
from pf2e.wizard import DrainBondedItem


def _settle_choices(game: Encounter) -> None:
    while game.inspect().choice is not None:
        choice = game.inspect().choice
        assert choice is not None
        result = game.choose(choice.choice_id, "keep", choice.owner_actor_id)
        assert result.status in {ResultStatus.COMPLETED, ResultStatus.PAUSED}


def _finished_wizard_game(*, prepare_day_two: bool) -> Encounter:
    # Wizard wins initiative, and an 8-point Breathe Fire defeats both dogs.
    game = Encounter.start(
        get_setup("staged_battle_magic_wizard_vs_two_guard_dogs"),
        rolls=(20, 1, 1, *(4 for _ in range(80))),
    )
    _settle_choices(game)
    result = game.execute(
        Cast("breathe_fire", actions=2, area_direction=Position(1, 0))
    )
    assert result.status is ResultStatus.COMPLETED
    assert not game.inspect().in_progress
    if prepare_day_two:
        assert game.record_rested(
            ("wizard",), day_number=2, elapsed_seconds=1
        ).status is ResultStatus.COMPLETED
        assert game.daily_prepare(("wizard",)).status is ResultStatus.COMPLETED
    return game


def _slot(game: Encounter, slot_id: str):
    return next(
        slot
        for slot in game._state.creatures["wizard"].prepared_slots
        if slot.slot_id == slot_id
    )


def test_substitution_requires_downtime_and_an_unspent_live_slot_atomically() -> None:
    game = Encounter.start(
        get_setup("staged_battle_magic_wizard_vs_two_guard_dogs"), rolls=(20, 1, 1)
    )
    before = game.inspect()
    dice_index = game._dice._index
    rejected = game.start_spell_substitution(
        "wizard", "wizard_breathe_fire", "sure_strike"
    )
    assert rejected.status is ResultStatus.REJECTED
    assert game.inspect() == before
    assert game._dice._index == dice_index

    game = _finished_wizard_game(prepare_day_two=False)
    assert (_slot(game, "wizard_breathe_fire").spell_id,
            _slot(game, "wizard_breathe_fire").spent) == ("breathe_fire", True)
    before = game.inspect()
    dice_index = game._dice._index
    rejected = game.start_spell_substitution(
        "wizard", "wizard_breathe_fire", "sure_strike"
    )
    assert rejected.status is ResultStatus.REJECTED
    assert game.inspect() == before
    assert game._dice._index == dice_index


def test_saved_599_seconds_blocks_other_activities_and_finishes_on_exact_second(
    tmp_path,
) -> None:
    game = _finished_wizard_game(prepare_day_two=True)
    started_at = game.inspect().world_time_seconds
    assert game.start_spell_substitution(
        "wizard", "wizard_breathe_fire", "sure_strike"
    ).status is ResultStatus.COMPLETED
    assert game.advance_spell_substitution("wizard", 599).status is ResultStatus.COMPLETED
    path = tmp_path / "substitution-599.json"
    game.save(path)
    game = Encounter.load(path)

    before = game.inspect()
    dice_index = game._dice._index
    assert game.refocus("wizard").status is ResultStatus.REJECTED
    assert game.next_encounter(
        get_setup("staged_battle_magic_wizard_next_guard_dog")
    ).status is ResultStatus.REJECTED
    assert game.record_rested(
        ("wizard",), day_number=3, elapsed_seconds=1
    ).status is ResultStatus.REJECTED
    assert game.advance_spell_substitution("wizard", True).status is ResultStatus.REJECTED
    assert game.advance_spell_substitution("wizard", 2).status is ResultStatus.REJECTED
    assert game.inspect() == before
    assert game._dice._index == dice_index

    assert game.advance_spell_substitution("wizard", 1).status is ResultStatus.COMPLETED
    assert (_slot(game, "wizard_breathe_fire").spell_id,
            _slot(game, "wizard_breathe_fire").spent) == ("sure_strike", False)
    assert game.inspect().world_time_seconds == started_at + 600


def test_interrupt_discards_progress_and_retry_starts_a_full_activity() -> None:
    game = _finished_wizard_game(prepare_day_two=True)
    assert game.start_spell_substitution(
        "wizard", "wizard_breathe_fire", "sure_strike"
    ).status is ResultStatus.COMPLETED
    assert game.advance_spell_substitution("wizard", 599).status is ResultStatus.COMPLETED
    assert game.interrupt_spell_substitution("wizard").status is ResultStatus.COMPLETED
    assert (_slot(game, "wizard_breathe_fire").spell_id,
            _slot(game, "wizard_breathe_fire").spent) == ("breathe_fire", False)

    assert game.start_spell_substitution(
        "wizard", "wizard_breathe_fire", "sure_strike"
    ).status is ResultStatus.COMPLETED
    assert game.advance_spell_substitution("wizard", 1).status is ResultStatus.COMPLETED
    progress = game._state.creatures["wizard"].spell_substitution
    assert progress is not None
    assert (progress.elapsed_seconds, progress.original_spell_id,
            _slot(game, "wizard_breathe_fire").spell_id) == (
        1, "breathe_fire", "breathe_fire"
    )


def test_owned_curriculum_spell_is_also_legal_in_an_ordinary_slot() -> None:
    # Battle Magic adds Force Barrage to the Wizard's spellbook. The extra
    # curriculum slot is restricted, but an ordinary slot may prepare any
    # same-rank spell from that owned book.
    game = _finished_wizard_game(prepare_day_two=True)
    assert game.start_spell_substitution(
        "wizard", "wizard_breathe_fire", "force_barrage"
    ).status is ResultStatus.COMPLETED
    assert game.advance_spell_substitution("wizard", 600).status is ResultStatus.COMPLETED
    assert (_slot(game, "wizard_breathe_fire").spell_id,
            _slot(game, "wizard_breathe_fire").source) == (
        "force_barrage", "ordinary_rank_1"
    )


def test_replacement_cast_and_bond_history_clear_at_daily_preparation() -> None:
    game = _finished_wizard_game(prepare_day_two=True)
    assert game.start_spell_substitution(
        "wizard", "wizard_breathe_fire", "sure_strike"
    ).status is ResultStatus.COMPLETED
    assert game.advance_spell_substitution("wizard", 600).status is ResultStatus.COMPLETED
    assert game.next_encounter(
        get_setup("staged_battle_magic_wizard_next_guard_dog")
    ).status in {ResultStatus.COMPLETED, ResultStatus.PAUSED}
    _settle_choices(game)
    while game.inspect().turn_actor_id != "wizard":
        assert game.execute(EndTurn()).status is ResultStatus.COMPLETED

    assert game.execute(Cast(
        "sure_strike", actions=1, slot_id="wizard_breathe_fire"
    )).status is ResultStatus.COMPLETED
    assert game.execute(Cast(
        "force_barrage", actions=1, target_ids=("next_guard_dog",)
    )).status is ResultStatus.COMPLETED
    assert game.execute(DrainBondedItem("wizard:bonded_staff")).status is ResultStatus.COMPLETED
    assert game.execute(Cast(
        "force_barrage", actions=1, target_ids=("next_guard_dog",),
        slot_id="wizard_force_barrage", use_arcane_bond=True,
    )).status is ResultStatus.COMPLETED
    assert not game.inspect().in_progress

    wizard = game._state.creatures["wizard"]
    assert _slot(game, "wizard_breathe_fire").spent
    assert _slot(game, "wizard_force_barrage").spent
    assert wizard.arcane_bond_used_day == 2
    assert wizard.arcane_bond_eligible_slots == {
        "wizard_breathe_fire", "wizard_force_barrage"
    }

    assert game.record_rested(
        ("wizard",), day_number=3, elapsed_seconds=1
    ).status is ResultStatus.COMPLETED
    assert game.daily_prepare(("wizard",)).status is ResultStatus.COMPLETED
    wizard = game._state.creatures["wizard"]
    assert (_slot(game, "wizard_breathe_fire").spell_id,
            _slot(game, "wizard_breathe_fire").spent) == ("sure_strike", False)
    assert not _slot(game, "wizard_force_barrage").spent
    assert wizard.arcane_bond_eligible_slots == set()
    assert wizard.arcane_bond_recast_until_start == 0
    assert wizard.arcane_bond_item_id is None
