"""Public level-1 Battle Magic Wizard admission coverage."""

from __future__ import annotations

import re

from pf2e.content import get_definition, get_setup
from pf2e.encounter import Encounter
from pf2e.investigator import RecallKnowledge
from pf2e.investigator_content import GUARD_DOG_KNOWLEDGE
from pf2e.model import Cast, EndTurn, Position, ResultStatus
from pf2e.terminal import run_terminal
from pf2e.wizard import DrainBondedItem
from terminal_test_helpers import BoundedInput, BoundedTranscript


def _settle(game: Encounter) -> None:
    while game.inspect().choice is not None:
        choice = game.inspect().choice
        assert choice is not None
        assert game.choose(choice.choice_id, "keep", choice.owner_actor_id).status in {
            ResultStatus.COMPLETED, ResultStatus.PAUSED,
        }


def _wizard_turn(game: Encounter) -> None:
    _settle(game)
    while game.inspect().turn_actor_id != "wizard":
        assert game.execute(EndTurn()).status is ResultStatus.COMPLETED
        _settle(game)


def _finished_game() -> Encounter:
    game = Encounter.start(
        get_setup("staged_battle_magic_wizard_vs_two_guard_dogs"),
        rolls=(20, 1, 1, 6, 6, 1, 1, *(20 for _ in range(20))),
    )
    _wizard_turn(game)
    assert game.execute(
        Cast("breathe_fire", actions=2, area_direction=Position(1, 0))
    ).status is ResultStatus.COMPLETED
    assert not game.inspect().in_progress
    assert game.record_rested(("wizard",), day_number=2, elapsed_seconds=1).status is ResultStatus.COMPLETED
    return game


def _legal_daily_choices() -> dict[str, dict[str, str]]:
    return {"wizard": {
        "wizard_shield": "telekinetic_projectile",
        "wizard_electric_arc": "light",
        "wizard_frostbite": "void_warp",
        "wizard_ignition": "electric_arc",
        "wizard_caustic_blast": "frostbite",
        "wizard_gouging_claw": "tangle_vine",
        "wizard_force_barrage": "breathe_fire",
        "wizard_breathe_fire": "fear",
        "wizard_enfeeble": "runic_weapon",
    }}


def test_daily_preparation_selects_full_legal_book_then_saves_and_casts_next_scene(tmp_path) -> None:
    game = _finished_game()
    prepared = game.daily_prepare(("wizard",), _legal_daily_choices())
    assert prepared.status is ResultStatus.COMPLETED
    slots = {slot.slot_id: slot.spell_id for slot in game._state.creatures["wizard"].prepared_slots}
    assert slots == _legal_daily_choices()["wizard"]
    assert len(slots) == 9
    game.save(tmp_path / "wizard-daily-preparation.json")
    game = Encounter.load(tmp_path / "wizard-daily-preparation.json")

    transitioned = game.next_encounter(get_setup("staged_battle_magic_wizard_next_guard_dog"))
    assert transitioned.status in {ResultStatus.COMPLETED, ResultStatus.PAUSED}
    _wizard_turn(game)
    assert game.execute(Cast("fear", "next_guard_dog", actions=2, slot_id="wizard_breathe_fire")).status is ResultStatus.COMPLETED
    slot = next(slot for slot in game._state.creatures["wizard"].prepared_slots if slot.slot_id == "wizard_breathe_fire")
    assert slot.spent


def test_daily_preparation_rejects_invalid_book_source_and_slot_capacity_atomically() -> None:
    for slot_id, replacement in (
        ("wizard_electric_arc", "mystic_armor"),
        ("wizard_force_barrage", "fear"),
    ):
        game = _finished_game()
        choices = _legal_daily_choices()
        choices["wizard"][slot_id] = replacement
        before, dice = game.inspect(), game._dice.to_data()
        assert game.daily_prepare(("wizard",), choices).status is ResultStatus.REJECTED
        assert game.inspect() == before and game._dice.to_data() == dice

    game = _finished_game()
    choices = _legal_daily_choices()
    del choices["wizard"]["wizard_enfeeble"]
    before, dice = game.inspect(), game._dice.to_data()
    assert game.daily_prepare(("wizard",), choices).status is ResultStatus.REJECTED
    assert game.inspect() == before and game._dice.to_data() == dice


def test_admitted_sheet_exposes_the_selected_human_scholar_facts() -> None:
    wizard = get_definition("wizard_battle_magic_level_1_staged")
    assert (wizard.hp, wizard.land_speed_ft, wizard.attacks[0].modifier) == (16, 30, 5)
    assert dict((name, modifier) for name, _rank, modifier in wizard.saves)["will"] == 5
    assert dict((name, modifier) for name, _rank, modifier in wizard.skills) == {
        "arcana": 7, "crafting": 7, "medicine": 3, "society": 7,
        "stealth": 5, "thievery": 5, "athletics": 3, "acrobatics": 5,
        "nature": 3, "academia_lore": 7, "occultism": 7,
    }
    assert wizard.languages == ("Common", "Draconic", "Dwarven", "Elven", "Gnomish", "Goblin")
    assert {entry.spell_id for entry in wizard.spell_substitution_book} == {
        "light", "void_warp", "telekinetic_projectile", "electric_arc", "frostbite",
        "ignition", "caustic_blast", "gouging_claw", "tangle_vine", "gale_blast", "shield",
        "sure_strike", "fear", "runic_weapon", "enfeeble", "runic_body", "breathe_fire",
        "force_barrage",
    }
    slots = wizard.prepared_spells
    assert (sum(slot.cantrip and slot.source == "ordinary_cantrip" for slot in slots),
            sum(slot.cantrip and slot.source == "battle_magic_curriculum" for slot in slots),
            sum(not slot.cantrip and slot.source == "ordinary_rank_1" for slot in slots),
            sum(not slot.cantrip and slot.source == "battle_magic_curriculum" for slot in slots)) == (5, 1, 2, 1)


def test_wizard_assurance_nature_recall_knowledge_uses_no_die_or_hero_choice() -> None:
    game = Encounter.start(
        get_setup("staged_battle_magic_wizard_vs_two_guard_dogs"), rolls=(20, 1, 1),
    )
    _wizard_turn(game)
    dice_before = game._dice.to_data()
    result = game.execute(RecallKnowledge(
        "guard_dog", GUARD_DOG_KNOWLEDGE.question, "nature", "dog_a",
        use_assurance=True,
    ))
    assert result.status is ResultStatus.COMPLETED
    event = next(event for event in result.events if event.kind == "recall_knowledge")
    assert event.check is not None
    assert (event.check.method, event.check.die, event.check.total, event.check.modifier) == (
        "assurance", None, 13, 3,
    )
    assert game.inspect().choice is None and game._dice.to_data() == dice_before
    assert "guard_dog" in game._state.creatures["wizard"].investigator_knowledge_exhausted


def test_terminal_offers_wizard_nature_assurance_for_authored_recall_knowledge() -> None:
    transcript = BoundedTranscript(max_lines=500, max_chars=100_000)

    def next_input() -> str:
        joined = "\n".join(transcript)
        prompt = transcript[-1] if transcript else ""
        if prompt == "Choice prompt action:":
            return "2"
        if prompt == "Choice option number:":
            return "2" if "Keep the current result" in "\n".join(transcript[-15:]) else "1"
        if prompt == "Target number:":
            return "1"
        if prompt == "Recall Knowledge skill:":
            return "2"  # Nature, after Society.
        if prompt == "Recall Knowledge method:":
            return "2"
        if prompt == "Choice:":
            if "Recall Knowledge method:" in joined:
                matches = re.findall(r"(?m)^(\d+)\. Quit$", joined)
                return matches[-1]
            matches = re.findall(r"(?m)^(\d+)\. Recall Knowledge$", joined)
            if matches:
                return matches[-1]
        raise AssertionError(f"unexpected terminal prompt: {prompt!r}\n{joined}")

    bounded = BoundedInput(next_input, max_calls=30, describe=lambda: transcript[-1] if transcript else "")
    assert run_terminal(
        setup=get_setup("staged_battle_magic_wizard_vs_two_guard_dogs"),
        rolls=(20, 1, 1), input_fn=bounded, output_fn=transcript.append,
    ) == 0
    joined = "\n".join(transcript)
    assert "Use Assurance (Nature)" in joined
    assert "recalls knowledge about Guard Dog A: Failure (13 vs DC 16)." in joined
    assert bounded.calls < 30


def test_fear_completed_cast_can_be_bond_recast_on_a_later_turn_after_save(tmp_path) -> None:
    game = _finished_game()
    choices = _legal_daily_choices()
    assert game.daily_prepare(("wizard",), choices).status is ResultStatus.COMPLETED
    assert game.next_encounter(get_setup("staged_battle_magic_wizard_next_guard_dog")).status in {
        ResultStatus.COMPLETED, ResultStatus.PAUSED,
    }
    _wizard_turn(game)
    assert game.execute(Cast("fear", "next_guard_dog", actions=2, slot_id="wizard_breathe_fire")).status is ResultStatus.COMPLETED
    assert game._state.creatures["wizard"].arcane_bond_eligible_slots == {"wizard_breathe_fire"}
    assert game.execute(EndTurn()).status is ResultStatus.COMPLETED
    assert game.execute(EndTurn()).status is ResultStatus.COMPLETED
    assert game.execute(DrainBondedItem("wizard:spellbook")).status is ResultStatus.REJECTED
    assert game.execute(DrainBondedItem("wizard:bonded_staff")).status is ResultStatus.COMPLETED
    game.save(tmp_path / "fear-bond-permission.json")
    game = Encounter.load(tmp_path / "fear-bond-permission.json")
    assert game.execute(Cast(
        "fear", "next_guard_dog", actions=2, slot_id="wizard_breathe_fire", use_arcane_bond=True,
    )).status is ResultStatus.COMPLETED


def test_runic_weapon_completed_cast_can_be_bond_recast_on_a_later_turn(tmp_path) -> None:
    game = _finished_game()
    assert game.daily_prepare(("wizard",), _legal_daily_choices()).status is ResultStatus.COMPLETED
    assert game.next_encounter(get_setup("staged_battle_magic_wizard_next_guard_dog")).status in {
        ResultStatus.COMPLETED, ResultStatus.PAUSED,
    }
    _wizard_turn(game)
    assert game.execute(Cast(
        "runic_weapon", actions=2, slot_id="wizard_enfeeble", item_id="wizard:bonded_staff",
    )).status is ResultStatus.COMPLETED
    assert game._state.creatures["wizard"].arcane_bond_eligible_slots == {"wizard_enfeeble"}
    assert game.execute(EndTurn()).status is ResultStatus.COMPLETED
    assert game.execute(EndTurn()).status is ResultStatus.COMPLETED
    assert game.execute(DrainBondedItem("wizard:bonded_staff")).status is ResultStatus.COMPLETED
    game.save(tmp_path / "runic-weapon-bond-permission.json")
    game = Encounter.load(tmp_path / "runic-weapon-bond-permission.json")
    assert game.execute(Cast(
        "runic_weapon", actions=2, slot_id="wizard_enfeeble", item_id="wizard:bonded_staff", use_arcane_bond=True,
    )).status is ResultStatus.COMPLETED
