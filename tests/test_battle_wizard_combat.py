"""Source-first checks for the selected staged Battle Magic Wizard combat path.

Sources: Force Bolt (AoN 1896) is a one-action, 30-foot, Manipulate focus
spell that automatically deals 1d4+1 force damage; it has no attack roll or
MAP.  This first test deliberately fixes roll 3 to prove the source value 4.
"""

from pf2e.content import get_setup
from pf2e.encounter import Encounter
from pf2e.model import Cast, EndTurn, Position, ResultStatus
from pf2e.terminal import run_terminal
from pf2e.wizard import DrainBondedItem
from terminal_test_helpers import BoundedInput, BoundedTranscript


def _settle_initiative(game: Encounter) -> None:
    while game.inspect().choice is not None:
        choice = game.inspect().choice
        assert choice is not None
        assert game.choose(choice.choice_id, "keep", choice.owner_actor_id).status in {
            ResultStatus.COMPLETED,
            ResultStatus.PAUSED,
        }


def test_force_bolt_is_one_action_focus_auto_damage_without_map() -> None:
    game = Encounter.start(
        get_setup("staged_battle_magic_wizard_vs_two_guard_dogs"),
        rolls=(20, 1, 1, 3),
    )
    _settle_initiative(game)
    assert game.inspect().turn_actor_id == "wizard"

    result = game.execute(Cast("force_bolt", "dog_a"))

    assert result.status is ResultStatus.COMPLETED
    damage = next(event.damage for event in result.events if event.kind == "spell_damage")
    assert damage is not None and damage.rolled_total == damage.total == 4
    actor = game._state.creatures["wizard"]
    assert actor.actions_remaining == 2
    assert actor.focus_points == 0
    assert actor.strikes_this_turn == 0


def test_selected_prepared_ledger_has_one_curriculum_and_one_ordinary_rank_one_slot() -> None:
    # Runtime spell slots preserve the reviewed source facts from the sheet.
    game = Encounter.start(get_setup("staged_battle_magic_wizard_vs_two_guard_dogs"), rolls=(20, 1, 1))
    _settle_initiative(game)
    assert {
        slot.slot_id: (slot.source, slot.spell_id)
        for slot in game._state.creatures["wizard"].prepared_slots
    } == {
        "wizard_shield": ("battle_magic_curriculum", "shield"),
        "wizard_electric_arc": ("ordinary_cantrip", "electric_arc"),
        "wizard_frostbite": ("ordinary_cantrip", "frostbite"),
        "wizard_ignition": ("ordinary_cantrip", "ignition"),
        "wizard_caustic_blast": ("ordinary_cantrip", "caustic_blast"),
        "wizard_gouging_claw": ("ordinary_cantrip", "gouging_claw"),
        "wizard_force_barrage": ("battle_magic_curriculum", "force_barrage"),
        "wizard_breathe_fire": ("ordinary_rank_1", "breathe_fire"),
        "wizard_enfeeble": ("ordinary_rank_1", "enfeeble"),
    }


def test_force_barrage_allocates_one_auto_shard_per_action_before_costs() -> None:
    game = Encounter.start(
        get_setup("staged_battle_magic_wizard_vs_two_guard_dogs"),
        rolls=(20, 1, 1, 1, 4),
    )
    _settle_initiative(game)

    result = game.execute(Cast("force_barrage", actions=2, target_ids=("dog_a", "dog_b")))

    assert result.status is ResultStatus.COMPLETED
    damage = [event.damage for event in result.events if event.kind == "spell_damage"]
    assert [entry.total for entry in damage if entry is not None] == [2, 5]
    wizard = game._state.creatures["wizard"]
    assert wizard.actions_remaining == 1
    assert next(slot for slot in wizard.prepared_slots if slot.slot_id == "wizard_force_barrage").spent


def test_force_barrage_rejects_an_incomplete_allocation_atomically() -> None:
    game = Encounter.start(
        get_setup("staged_battle_magic_wizard_vs_two_guard_dogs"), rolls=(20, 1, 1)
    )
    _settle_initiative(game)
    before = game.inspect()
    before_dice = game._dice._index

    result = game.execute(Cast("force_barrage", actions=2, target_ids=("dog_a",)))

    assert result.status is ResultStatus.REJECTED
    assert "exactly 2 target_ids" in result.message
    assert game.inspect() == before
    assert game._dice._index == before_dice


def test_force_barrage_combines_same_targets_shards_before_one_damage_application() -> None:
    game = Encounter.start(
        get_setup("staged_battle_magic_wizard_vs_two_guard_dogs"),
        rolls=(20, 1, 1, 1, 4),
    )
    _settle_initiative(game)

    result = game.execute(Cast("force_barrage", actions=2, target_ids=("dog_a", "dog_a")))

    assert result.status is ResultStatus.COMPLETED
    damage = [event.damage for event in result.events if event.kind == "spell_damage"]
    assert len(damage) == 1 and damage[0] is not None
    assert damage[0].rolled_total == damage[0].total == 7


def test_empty_breathe_fire_still_records_an_eligible_completed_prepared_spell() -> None:
    game = Encounter.start(
        get_setup("staged_battle_magic_wizard_vs_two_guard_dogs"), rolls=(20, 1, 1, 3, 4),
    )
    _settle_initiative(game)

    result = game.execute(Cast("breathe_fire", actions=2, area_direction=Position(-1, 0)))

    assert result.status is ResultStatus.COMPLETED
    assert not any(event.kind == "spell_damage" for event in result.events)
    assert game.execute(DrainBondedItem("wizard:bonded_staff")).status is ResultStatus.COMPLETED


def test_arcane_bond_requires_completed_prepared_cast_and_is_daily() -> None:
    game = Encounter.start(
        get_setup("staged_battle_magic_wizard_vs_two_guard_dogs"),
        rolls=(20, 1, 1, 1, 4),
    )
    _settle_initiative(game)
    bonded_staff = "wizard:bonded_staff"
    assert game.execute(DrainBondedItem(bonded_staff)).status is ResultStatus.REJECTED
    assert game.execute(Cast("force_barrage", actions=2, target_ids=("dog_a", "dog_b"))).status is ResultStatus.COMPLETED

    drained = game.execute(DrainBondedItem(bonded_staff))

    assert drained.status is ResultStatus.COMPLETED
    wizard = game._state.creatures["wizard"]
    assert wizard.arcane_bond_eligible_slots == {"wizard_force_barrage"}
    assert game.execute(DrainBondedItem(bonded_staff)).status is ResultStatus.REJECTED


def test_arcane_bond_recasts_completed_prepared_spell_without_refilling_slot(tmp_path) -> None:
    game = Encounter.start(
        get_setup("staged_battle_magic_wizard_vs_two_guard_dogs"),
        rolls=(20, 1, 1, 1, 4),
    )
    _settle_initiative(game)
    first = game.execute(Cast("force_barrage", actions=1, target_ids=("dog_a",)))
    assert first.status is ResultStatus.COMPLETED
    slot = next(
        slot for slot in game._state.creatures["wizard"].prepared_slots
        if slot.slot_id == "wizard_force_barrage"
    )
    assert slot.spent
    assert game.execute(DrainBondedItem("wizard:bonded_staff")).status is ResultStatus.COMPLETED
    save_path = tmp_path / "bonded-recast.json"
    game.save(save_path)
    game = Encounter.load(save_path)

    recast = game.execute(Cast(
        "force_barrage", actions=1, target_ids=("dog_a",),
        slot_id="wizard_force_barrage", use_arcane_bond=True,
    ))

    assert recast.status is ResultStatus.COMPLETED
    assert slot.spent
    assert game.execute(Cast(
        "force_barrage", actions=1, target_ids=("dog_a",),
        slot_id="wizard_force_barrage", use_arcane_bond=True,
    )).status is ResultStatus.REJECTED


def test_breathe_fire_uses_one_shared_roll_and_reflex_basic_saves() -> None:
    """AoN 1457: 2 actions, 15-foot cone, 2d6 fire/basic Reflex."""
    game = Encounter.start(
        get_setup("staged_battle_magic_wizard_vs_two_guard_dogs"),
        rolls=(20, 1, 1, 3, 4, 10, 10),
    )
    _settle_initiative(game)
    assert game._breathe_fire_targets(game._state, game._state.creatures["wizard"], Position(1, 0)) == ("dog_a", "dog_b")

    result = game.execute(Cast("breathe_fire", actions=2, area_direction=Position(1, 0)))

    assert result.status is ResultStatus.COMPLETED
    damages = [event.damage for event in result.events if event.kind == "spell_damage"]
    # Guard Dog Reflex +7: both 10+7 saves succeed for 3 damage from the
    # one raw 3+4 roll of 7.
    assert [damage.total for damage in damages if damage is not None] == [3, 3]


def test_breathe_fire_saved_hero_choice_keeps_shared_roll_and_resumes_next_recipient(tmp_path) -> None:
    """A target-owned Hero choice saves after the shared roll, before its own basic save."""
    game = Encounter.start(
        get_setup("staged_battle_magic_wizard_breathe_hero_save"),
        rolls=(20, 1, 1, 1, 3, 4, 10, 10, 1),
    )
    _settle_initiative(game)
    # Keep this target-owned Heroic Recovery continuation probe independent
    # from the admitted Wizard's corrected maximum Hit Points.
    game._state.creatures["wizard_ally"].hp = 14

    result = game.execute(Cast("breathe_fire", actions=2, area_direction=Position(1, 0)))

    assert result.status is ResultStatus.PAUSED
    choice = game.inspect().choice
    assert choice is not None and choice.kind == "spell_save_hero_reroll"
    assert choice.owner_actor_id == "wizard_ally"
    save_path = tmp_path / "breathe-hero.json"
    game.save(save_path)
    game = Encounter.load(save_path)
    choice = game.inspect().choice
    assert choice is not None
    resumed = game.choose(choice.choice_id, "keep", choice.owner_actor_id)
    assert resumed.status is ResultStatus.PAUSED
    health_choice = game.inspect().choice
    assert health_choice is not None and health_choice.kind == "heroic_recovery_damage"
    follow_up = game.choose(health_choice.choice_id, "heroic_recovery", health_choice.owner_actor_id)
    assert follow_up.status is ResultStatus.COMPLETED
    events = [*resumed.events, *follow_up.events]
    damage = [event.damage for event in events if event.kind == "spell_damage"]
    assert len(damage) == 1 and damage[0] is not None and damage[0].total == 14


def test_arcane_bond_permission_expires_at_the_wizards_next_turn() -> None:
    game = Encounter.start(
        get_setup("staged_battle_magic_wizard_vs_two_guard_dogs"),
        rolls=(20, 1, 1, 1, 4),
    )
    _settle_initiative(game)
    assert game.execute(Cast("force_barrage", actions=1, target_ids=("dog_a",))).status is ResultStatus.COMPLETED
    assert game.execute(DrainBondedItem("wizard:bonded_staff")).status is ResultStatus.COMPLETED
    assert game.execute(EndTurn()).status is ResultStatus.COMPLETED
    while game.inspect().turn_actor_id != "wizard":
        assert game.execute(EndTurn()).status is ResultStatus.COMPLETED

    assert game._state.creatures["wizard"].arcane_bond_recast_until_start == 0
    rejected = game.execute(Cast(
        "force_barrage", actions=1, target_ids=("dog_a",),
        slot_id="wizard_force_barrage", use_arcane_bond=True,
    ))
    assert rejected.status is ResultStatus.REJECTED


def test_healthy_wizard_refocuses_after_combat_then_saves_into_the_next_scene(tmp_path) -> None:
    game = Encounter.start(
        get_setup("staged_battle_magic_wizard_vs_two_guard_dogs"),
        rolls=(20, 1, 1, 3, 6, 6, 1, 1, 20, 1),
    )
    _settle_initiative(game)
    assert game.execute(Cast("force_bolt", "dog_a")).status is ResultStatus.COMPLETED
    finished = game.execute(Cast("breathe_fire", actions=2, area_direction=Position(1, 0)))
    assert finished.status is ResultStatus.COMPLETED
    assert not game.inspect().in_progress
    assert game._state.creatures["wizard"].focus_points == 0

    assert game.refocus("wizard").status is ResultStatus.COMPLETED
    assert game._state.creatures["wizard"].focus_points == 1
    save_path = tmp_path / "wizard-refocus.json"
    game.save(save_path)
    game = Encounter.load(save_path)
    next_scene = game.next_encounter(get_setup("staged_battle_magic_wizard_next_guard_dog"))
    assert next_scene.status in {ResultStatus.COMPLETED, ResultStatus.PAUSED}
    assert {actor.actor_id for actor in game.inspect().actors} == {"wizard", "next_guard_dog"}


def test_bounded_terminal_selects_the_staged_wizards_force_bolt() -> None:
    engine = Encounter.start(
        get_setup("staged_battle_magic_wizard_vs_two_guard_dogs"), rolls=(20, 1, 1),
    )
    _settle_initiative(engine)
    assert "cast" in engine.options().available_actions
    transcript = BoundedTranscript(max_lines=300, max_chars=50_000)
    state = {"menu": "", "prompt": "", "cast": True}

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
            if state["cast"]:
                state["cast"] = False
                return choose("Cast")
            return choose("Quit")
        if prompt == "Spell number:":
            return choose("Force Bolt", prefix=True)
        if prompt == "Casting mode:":
            return choose("1 action")
        if prompt == "Target number:":
            return "1"  # Dog A; unsupported self-damage is not advertised.
        raise AssertionError(f"unexpected terminal prompt: {prompt!r}")

    assert run_terminal(
        setup=get_setup("staged_battle_magic_wizard_vs_two_guard_dogs"),
        rolls=(20, 1, 1, 3),
        input_fn=BoundedInput(scripted_input, max_calls=35), output_fn=output,
    ) == 0
    rendered = "\n".join(transcript)
    assert "Rejected:" not in rendered, rendered
    assert "commits Force Bolt" in rendered


def test_critical_reactive_strike_disrupts_force_bolt_after_its_cost_is_committed() -> None:
    game = Encounter.start(
        get_setup("staged_battle_magic_wizard_reactive_strike"),
        rolls=(20, 1, 20, 1),
    )
    _settle_initiative(game)
    started = game.execute(Cast("force_bolt", "reactive_fighter"))
    assert started.status is ResultStatus.PAUSED
    reaction = game.inspect().choice
    assert reaction is not None and reaction.kind == "reaction"
    asserted = game.choose(reaction.choice_id, "accept", reaction.owner_actor_id)
    assert asserted.status is ResultStatus.PAUSED
    hero = game.inspect().choice
    assert hero is not None and hero.kind == "attack_hero_reroll"
    result = game.choose(hero.choice_id, "keep", hero.owner_actor_id)
    assert result.status is ResultStatus.COMPLETED
    assert any(event.kind == "disrupted" for event in result.events)
    wizard = game._state.creatures["wizard"]
    assert (wizard.actions_remaining, wizard.focus_points) == (2, 0)
    assert not any(event.kind == "spell_damage" for event in result.events)


def test_bounded_terminal_casts_then_drains_the_bonded_item() -> None:
    transcript = BoundedTranscript(max_lines=300, max_chars=50_000)
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
            if state["phase"] == "cast":
                state["phase"] = "drain"
                return choose("Cast")
            if state["phase"] == "drain":
                state["phase"] = "recast"
                return choose("Drain Bonded Item")
            if state["phase"] == "recast":
                state["phase"] = "quit"
                return choose("Cast")
            return choose("Quit")
        if prompt == "Spell number:":
            return choose("Force Barrage", prefix=True)
        if prompt == "Casting mode:":
            return choose("1 action")
        if prompt == "Prepared slot:":
            return "1"
        if prompt == "Target number:":
            return "1"
        if prompt == "Held item:":
            return "1"
        raise AssertionError(f"unexpected terminal prompt: {prompt!r}")

    assert run_terminal(
        setup=get_setup("staged_battle_magic_wizard_vs_two_guard_dogs"),
        rolls=(20, 1, 1, 1, 1),
        input_fn=BoundedInput(scripted_input, max_calls=40), output_fn=output,
    ) == 0
    rendered = "\n".join(transcript)
    assert rendered.count("commits Force Barrage") == 2
    assert "drains wizard:bonded_staff" in rendered
