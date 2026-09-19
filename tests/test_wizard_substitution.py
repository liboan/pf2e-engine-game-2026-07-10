"""Source-first Spell Substitution checks for the staged Battle Magic Wizard.

AoN Arcane Thesis 9 and Wizard preparation rules: Spell Substitution takes
ten uninterrupted minutes and changes an unspent prepared spell without
restoring any expended resource.  This selected ledger has one curriculum
rank-1 preparation and two ordinary book entries (Breathe Fire/Sure Strike).
"""

from pf2e.content import get_setup
from pf2e.encounter import Encounter
from pf2e.model import Cast, Position, ResultStatus
from pf2e.terminal import run_terminal
from pf2e.wizard import DrainBondedItem
from terminal_test_helpers import BoundedInput, BoundedTranscript


def _finished_wizard_game() -> Encounter:
    game = Encounter.start(
        get_setup("staged_battle_magic_wizard_vs_two_guard_dogs"),
        rolls=(20, 1, 1, 6, 6, 1, 1, 20, 1, 1, 3, 20, 1, 1),
    )
    while game.inspect().choice is not None:
        choice = game.inspect().choice
        assert choice is not None
        assert game.choose(choice.choice_id, "keep", choice.owner_actor_id).status in {
            ResultStatus.COMPLETED, ResultStatus.PAUSED,
        }
    assert game.execute(Cast("breathe_fire", actions=2, area_direction=Position(1, 0))).status is ResultStatus.COMPLETED
    assert not game.inspect().in_progress
    assert game.record_rested(("wizard",), day_number=2, elapsed_seconds=1).status is ResultStatus.COMPLETED
    assert game.daily_prepare(("wizard",)).status is ResultStatus.COMPLETED
    return game


def test_substitution_saves_half_complete_work_then_replaces_once_at_ten_minutes(tmp_path) -> None:
    game = _finished_wizard_game()
    starts_at = game.inspect().world_time_seconds
    assert game.start_spell_substitution("wizard", "wizard_breathe_fire", "sure_strike").status is ResultStatus.COMPLETED
    assert game.advance_spell_substitution("wizard", 300).status is ResultStatus.COMPLETED
    path = tmp_path / "substitution-half.json"
    game.save(path)
    game = Encounter.load(path)
    assert game.advance_spell_substitution("wizard", 300).status is ResultStatus.COMPLETED
    slot = next(slot for slot in game._state.creatures["wizard"].prepared_slots if slot.slot_id == "wizard_breathe_fire")
    assert (slot.spell_id, slot.spent, game.inspect().world_time_seconds) == ("sure_strike", False, starts_at + 600)
    assert game.record_rested(("wizard",), day_number=3, elapsed_seconds=1).status is ResultStatus.COMPLETED
    assert game.daily_prepare(("wizard",)).status is ResultStatus.COMPLETED
    slot = next(slot for slot in game._state.creatures["wizard"].prepared_slots if slot.slot_id == "wizard_breathe_fire")
    assert (slot.spell_id, slot.spent) == ("sure_strike", False)


def test_substitution_interrupt_preserves_original_and_source_restrictions_are_atomic() -> None:
    game = _finished_wizard_game()
    before = game.inspect()
    assert game.start_spell_substitution("wizard", "wizard_force_barrage", "sure_strike").status is ResultStatus.REJECTED
    assert game.start_spell_substitution("wizard", "wizard_shield", "sure_strike").status is ResultStatus.REJECTED
    assert game.start_spell_substitution("wizard", "wizard_breathe_fire", "breathe_fire").status is ResultStatus.REJECTED
    assert game.inspect() == before
    assert game.start_spell_substitution("wizard", "wizard_breathe_fire", "sure_strike").status is ResultStatus.COMPLETED
    assert game.advance_spell_substitution("wizard", 180).status is ResultStatus.COMPLETED
    assert game.refocus("wizard").status is ResultStatus.REJECTED
    assert game.next_encounter(get_setup("staged_battle_magic_wizard_next_guard_dog")).status is ResultStatus.REJECTED
    assert game._state.creatures["wizard"].spell_substitution is not None
    assert game.interrupt_spell_substitution("wizard").status is ResultStatus.COMPLETED
    slot = next(slot for slot in game._state.creatures["wizard"].prepared_slots if slot.slot_id == "wizard_breathe_fire")
    assert slot.spell_id == "breathe_fire"
    assert game.start_spell_substitution("wizard", "wizard_breathe_fire", "sure_strike").status is ResultStatus.COMPLETED
    assert game.advance_spell_substitution("wizard", 600).status is ResultStatus.COMPLETED


def test_substitution_rejects_an_inaccessible_book_without_mutating_time_or_dice() -> None:
    game = _finished_wizard_game()
    wizard = game._state.creatures["wizard"]
    wizard.stowed_items.remove("wizard:spellbook")
    before = game.inspect()
    dice_index = game._dice._index
    assert game.start_spell_substitution("wizard", "wizard_breathe_fire", "sure_strike").status is ResultStatus.REJECTED
    assert game.inspect() == before
    assert game._dice._index == dice_index


def test_curriculum_substitution_uses_the_curriculum_book_entry() -> None:
    game = _finished_wizard_game()
    assert game.start_spell_substitution("wizard", "wizard_force_barrage", "breathe_fire").status is ResultStatus.COMPLETED
    assert game.advance_spell_substitution("wizard", 600).status is ResultStatus.COMPLETED
    slot = next(slot for slot in game._state.creatures["wizard"].prepared_slots if slot.slot_id == "wizard_force_barrage")
    assert (slot.spell_id, slot.source, slot.spent) == ("breathe_fire", "battle_magic_curriculum", False)


def test_ordinary_substitution_can_prepare_force_barrage_from_the_owned_book() -> None:
    game = _finished_wizard_game()
    assert game.start_spell_substitution("wizard", "wizard_breathe_fire", "force_barrage").status is ResultStatus.COMPLETED
    assert game.advance_spell_substitution("wizard", 600).status is ResultStatus.COMPLETED
    slot = next(slot for slot in game._state.creatures["wizard"].prepared_slots if slot.slot_id == "wizard_breathe_fire")
    assert (slot.spell_id, slot.source, slot.spent) == ("force_barrage", "ordinary_rank_1", False)


def test_replacement_cast_round_trips_bond_in_a_healthy_next_encounter(tmp_path) -> None:
    game = _finished_wizard_game()
    assert game.start_spell_substitution("wizard", "wizard_breathe_fire", "sure_strike").status is ResultStatus.COMPLETED
    assert game.advance_spell_substitution("wizard", 600).status is ResultStatus.COMPLETED
    assert game.next_encounter(get_setup("staged_battle_magic_wizard_next_guard_dog")).status in {
        ResultStatus.COMPLETED, ResultStatus.PAUSED,
    }
    while game.inspect().choice is not None:
        choice = game.inspect().choice
        assert choice is not None
        assert game.choose(choice.choice_id, "keep", choice.owner_actor_id).status in {ResultStatus.COMPLETED, ResultStatus.PAUSED}
    assert game.execute(Cast("sure_strike", actions=1, slot_id="wizard_breathe_fire")).status is ResultStatus.COMPLETED
    slot = next(slot for slot in game._state.creatures["wizard"].prepared_slots if slot.slot_id == "wizard_breathe_fire")
    assert (slot.spell_id, slot.spent) == ("sure_strike", True)
    assert game.execute(DrainBondedItem("wizard:bonded_staff")).status is ResultStatus.COMPLETED
    path = tmp_path / "replacement-bond.json"
    game.save(path)
    game = Encounter.load(path)
    assert game.execute(Cast("sure_strike", actions=1, slot_id="wizard_breathe_fire", use_arcane_bond=True)).status is ResultStatus.COMPLETED
    assert game.execute(DrainBondedItem("wizard:bonded_staff")).status is ResultStatus.REJECTED
    assert game.execute(Cast("sure_strike", actions=1, slot_id="wizard_breathe_fire")).status is ResultStatus.REJECTED
    assert game.execute(Cast("force_bolt", "next_guard_dog")).status is ResultStatus.COMPLETED
    assert game.inspect().in_progress


def test_bounded_terminal_completes_spell_substitution_after_daily_preparation() -> None:
    transcript = BoundedTranscript(max_lines=400, max_chars=60_000)
    state = {"menu": "", "prompt": "", "phase": "cast"}

    def output(line: str) -> None:
        transcript.append(line)
        if line.startswith("1. "):
            state["menu"] = line
        if line.endswith(":"):
            state["prompt"] = line

    def choose(label: str, *, prefix: bool = False) -> str:
        for row in state["menu"].splitlines():
            number, text = row.split(". ", 1)
            if text.startswith(label) if prefix else text == label:
                return number
        raise AssertionError(f"missing terminal menu item {label!r}: {state['menu']!r}")

    def scripted_input() -> str:
        prompt = state["prompt"]
        if prompt == "Choice prompt action:":
            return choose("Resolve this choice")
        if prompt == "Choice option number:":
            return choose("Keep initiative")
        if prompt == "Choice:":
            phase = state["phase"]
            if phase == "cast":
                state["phase"] = "rest"
                return choose("Cast")
            if phase == "rest":
                state["phase"] = "prepare"
                return choose("Record Rested Eligibility")
            if phase == "prepare":
                state["phase"] = "substitute"
                return choose("Daily Preparation")
            if phase == "substitute":
                state["phase"] = "quit"
                return choose("Spell Substitution (10 minutes)")
            return choose("Quit")
        if prompt == "Spell number:":
            return choose("Breathe Fire", prefix=True)
        if prompt == "Casting mode:":
            return choose("2 actions")
        if prompt == "Prepared slot:":
            return choose("wizard_breathe_fire", prefix=True)
        if prompt == "Breathe Fire direction:":
            return choose("East")
        if prompt == "Actor numbers:":
            return "1"
        if prompt == "Declared preparation day:":
            return "2"
        if prompt == "Externally adjudicated elapsed seconds:":
            return "1"
        if prompt.startswith("Daily preparation ") and prompt.endswith(" spell:"):
            current = {
                "wizard_shield": "Telekinetic Projectile",
                "wizard_electric_arc": "Electric Arc",
                "wizard_frostbite": "Frostbite",
                "wizard_ignition": "Ignition",
                "wizard_caustic_blast": "Caustic Blast",
                "wizard_gouging_claw": "Gouging Claw",
                "wizard_force_barrage": "Force Barrage",
                "wizard_breathe_fire": "Breathe Fire",
                "wizard_enfeeble": "Enfeeble",
            }[prompt.removeprefix("Daily preparation ").removesuffix(" spell:")]
            return choose(current)
        if prompt == "Prepared rank-1 slot id:":
            return "wizard_breathe_fire"
        if prompt == "Replacement spell id:":
            return "sure_strike"
        if prompt == "Uninterrupted elapsed seconds to advance (max 600):":
            return "600"
        raise AssertionError(f"unexpected terminal prompt: {prompt!r}")

    assert run_terminal(
        setup=get_setup("staged_battle_magic_wizard_vs_two_guard_dogs"),
        rolls=(20, 1, 1, 6, 6, 1, 1),
        input_fn=BoundedInput(scripted_input, max_calls=60), output_fn=output,
    ) == 0
    rendered = "\n".join(transcript)
    assert "Daily preparation wizard_shield spell:" in rendered
    assert "Telekinetic Projectile" in rendered
    assert "Spell Substitution: breathe_fire becomes sure_strike" in rendered
    assert "Rejected:" not in rendered, rendered
