"""Focused procedure checks, including public Cast/save-load routing."""

from __future__ import annotations

from copy import deepcopy

from pf2e.content import get_definition, get_setup, S3_SETUP
from pf2e.encounter import Encounter
from pf2e.family_casting import _prepared_casting_snapshots, begin_cast
from pf2e.model import Cast, FamilyProcedureContext, Position, ResultStatus, Stride
from pf2e.space import grid_distance_feet


def _finish_start_choices(game: Encounter) -> None:
    while game.inspect().choice is not None:
        choice = game.inspect().choice
        assert choice is not None
        option = "keep" if any(item.option_id == "keep" for item in choice.options) else choice.options[0].option_id
        game.choose(choice.choice_id, option, choice.owner_actor_id)


class _SlotPromptContext(FamilyProcedureContext):
    """Capture the required legacy prompt adapter contract without core edits."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.slot_prompt = None

    def present_spell_slot_choice(self, command, options, *, spell_name, actions):
        self.slot_prompt = (command, options, spell_name, actions)


def _context(
    *, setup_id: str = S3_SETUP.setup_id, rolls: tuple[int, ...] | None = None,
) -> _SlotPromptContext:
    game = Encounter.start(
        get_setup(setup_id),
        seed=281,
        rolls=rolls,
    )
    _finish_start_choices(game)
    state = deepcopy(game._state)
    actor = state.creatures["cleric_c"]
    actor.actions_remaining = 3
    return _SlotPromptContext(
        game,
        state,
        game._dice.clone(),
        actor,
        get_definition(actor.definition_id),
        "casting",
    )


def _slot(context: FamilyProcedureContext, slot_id: str):
    return next(slot for slot in context.actor.prepared_slots if slot.slot_id == slot_id)


def _public_cast_range_game(rolls: tuple[int, ...] = (1, 1, 20, 1, 1)) -> Encounter:
    game = Encounter.start(
        get_setup("s3_long_lane_crossfire"),
        rolls=rolls,
    )
    _finish_start_choices(game)
    assert game.inspect().turn_actor_id == "cleric_c"
    return game


def test_casting_snapshots_keep_cantrip_access_and_font_slot_provenance() -> None:
    context = _context()
    snapshot = _prepared_casting_snapshots(context)
    assert isinstance(snapshot, tuple)
    sources, resources = snapshot

    cantrip = next(source for source in sources if source.source_id == "prepared:cantrip:cantrip")
    ordinary = next(source for source in sources if source.source_id == "prepared:ordinary:slots")
    font = next(source for source in sources if source.source_id == "prepared:font:slots")
    assert {access.spell_id for access in cantrip.spells} >= {
        "divine_lance", "void_warp", "guidance", "stabilize", "light",
    }
    assert next(access for access in ordinary.spells if access.spell_id == "heal").rank == 1
    assert next(access for access in font.spells if access.spell_id == "heal").rank == 1

    resources_by_id = {resource.resource_id: resource for resource in resources}
    assert resources_by_id["ordinary_heal_1"].source_id == ordinary.source_id
    assert resources_by_id["font_heal_1"].source_id == font.source_id
    assert resources_by_id["font_heal_1"].remaining == 1


def test_repeatable_guidance_cantrip_spends_no_prepared_slot() -> None:
    context = _context()
    before_slots = tuple(slot.spent for slot in context.actor.prepared_slots)

    first = begin_cast(context, Cast("guidance", "cleric_c"))
    second = begin_cast(context, Cast("guidance", "fighter_m"))

    assert first.rejection is None and first.unsupported is None
    assert second.rejection is None and second.unsupported is None
    assert sum(not slot.spent for slot in context.actor.prepared_slots if not slot.cantrip) == 6
    assert tuple(slot.spent for slot in context.actor.prepared_slots) == before_slots
    assert context.actor.actions_remaining == 1
    assert {effect.target_actor_id for effect in context.state.active_effects if effect.kind == "guidance"} == {
        "cleric_c", "fighter_m",
    }


def test_one_remaining_prepared_slot_is_selected_automatically() -> None:
    context = _context()
    for slot in context.actor.prepared_slots:
        if slot.spell_id == "heal" and slot.slot_id != "ordinary_heal_1":
            slot.spent = True

    result = begin_cast(context, Cast("heal", "cleric_c", actions=2))

    assert result.rejection is None and result.unsupported is None
    assert _slot(context, "ordinary_heal_1").spent
    assert context.state.pending_choice is not None
    assert context.state.pending_choice.kind == "spell_willingness"
    continuation = context.state.pending_choice.continuation
    assert continuation is not None
    assert continuation.kind == "cast"
    assert continuation.slot_id == "ordinary_heal_1"
    assert continuation.spell_actions == 2


def test_multiple_prepared_resources_use_the_legacy_spell_slot_prompt() -> None:
    context = _context()
    command = Cast("heal", "cleric_c", actions=2)

    result = begin_cast(context, command)

    assert result.rejection is None and result.unsupported is None
    assert result.events[0].kind == "spell_slot_choice"
    assert context.slot_prompt is not None
    prompted_command, options, spell_name, actions = context.slot_prompt
    assert prompted_command == command
    assert spell_name == "Heal" and actions == 2
    assert tuple(option.option_id for option in options) == (
        "ordinary_heal_1", "ordinary_heal_2",
        "font_heal_1", "font_heal_2", "font_heal_3", "font_heal_4",
    )
    assert tuple(option.label for option in options) == (
        "ordinary: ordinary_heal_1", "ordinary: ordinary_heal_2",
        "font: font_heal_1", "font: font_heal_2", "font: font_heal_3", "font: font_heal_4",
    )
    assert context.actor.actions_remaining == 3
    assert all(not slot.spent for slot in context.actor.prepared_slots if slot.spell_id == "heal")


def test_selected_font_slot_is_the_only_resource_committed() -> None:
    context = _context()

    result = begin_cast(context, Cast("heal", "cleric_c", actions=2, slot_id="font_heal_2"))

    assert result.rejection is None and result.unsupported is None
    assert _slot(context, "font_heal_2").spent
    assert not _slot(context, "font_heal_1").spent
    assert not _slot(context, "ordinary_heal_1").spent
    assert context.actor.actions_remaining == 1
    continuation = context.state.pending_choice.continuation
    assert continuation is not None and continuation.kind == "cast"
    assert continuation.slot_id == "font_heal_2"


def test_invalid_target_rejects_without_spending_actions_or_the_selected_slot() -> None:
    context = _context(setup_id="s3_long_lane_crossfire")
    before_dice_index = context.dice._index

    result = begin_cast(context, Cast("heal", "guard_dog_65", actions=2, slot_id="font_heal_2"))

    assert result.rejection == "That creature is not a legal target for Heal in this mode."
    assert context.actor.actions_remaining == 3
    assert not _slot(context, "font_heal_2").spent
    assert context.state.pending_choice is None
    assert context.dice._index == before_dice_index


def test_cast_resource_is_committed_before_reactive_strike_and_keeps_cast_parent() -> None:
    context = _context(
        setup_id="s3_interrupted_preparation",
        rolls=(1, 2, 20, 19, 3, 20, 3, 1),
    )

    result = begin_cast(context, Cast("heal", "cleric_c", actions=2, slot_id="ordinary_heal_1"))

    pending = context.state.pending_choice
    assert result.rejection is None and result.unsupported is None
    assert pending is not None and pending.kind == "reaction"
    assert pending.owner_actor_id == "rapier_fighter"
    assert pending.continuation is not None
    assert pending.continuation.kind == "cast"
    assert pending.continuation.slot_id == "ordinary_heal_1"
    assert pending.continuation.must_disrupt_on_critical
    assert _slot(context, "ordinary_heal_1").spent
    assert context.actor.actions_remaining == 1


def test_public_cast_heal_two_action_range_is_30_feet_and_rejection_is_atomic() -> None:
    at_thirty_feet = _public_cast_range_game()
    assert at_thirty_feet.execute(Stride((Position(1, 4), Position(2, 4)))).status is ResultStatus.COMPLETED
    assert grid_distance_feet(Position(2, 4), Position(6, 0)) == 30
    legal = at_thirty_feet.execute(
        Cast("heal", "fighter_m", actions=2, slot_id="ordinary_heal_1")
    )
    assert legal.status is ResultStatus.PAUSED
    assert legal.inspection.choice is not None
    assert legal.inspection.choice.kind == "spell_willingness"

    at_thirty_five_feet = _public_cast_range_game()
    assert at_thirty_five_feet.execute(Stride((Position(1, 4),))).status is ResultStatus.COMPLETED
    assert grid_distance_feet(Position(1, 4), Position(6, 0)) == 35
    before = at_thirty_five_feet.inspect()
    dice_index = at_thirty_five_feet._dice._index
    rejected = at_thirty_five_feet.execute(
        Cast("heal", "fighter_m", actions=2, slot_id="font_heal_1")
    )
    assert rejected.status is ResultStatus.REJECTED
    assert rejected.message == "That creature is not a legal target for Heal in this mode."
    assert rejected.inspection == before
    assert at_thirty_five_feet._dice._index == dice_index


def test_public_spell_slot_choice_saves_resumes_and_spends_only_the_selected_slot(tmp_path) -> None:
    game = _public_cast_range_game((1, 1, 20, 1, 1, 4))

    offered = game.execute(Cast("heal", "fighter_r", actions=2))
    assert offered.status is ResultStatus.PAUSED
    choice = offered.inspection.choice
    assert choice is not None and choice.kind == "spell_slot"
    assert tuple(option.option_id for option in choice.options) == (
        "ordinary_heal_1", "ordinary_heal_2",
        "font_heal_1", "font_heal_2", "font_heal_3", "font_heal_4",
    )
    before_save = offered.inspection
    save_path = tmp_path / "spell-slot-choice.json"
    game.save(save_path)
    resumed = Encounter.load(save_path)
    assert resumed.inspect() == before_save

    selected = resumed.choose(choice.choice_id, "font_heal_1", choice.owner_actor_id)
    assert selected.status is ResultStatus.PAUSED
    willingness = selected.inspection.choice
    assert willingness is not None and willingness.kind == "spell_willingness"
    cleric = next(actor for actor in selected.inspection.actors if actor.actor_id == "cleric_c")
    spent = next(slot for slot in cleric.prepared_slots if slot.slot_id == "font_heal_1")
    assert spent.spent
    assert not next(slot for slot in cleric.prepared_slots if slot.slot_id == "ordinary_heal_1").spent
    assert cleric.actions_remaining == 1

    resumed.save(save_path)
    loaded_willingness = Encounter.load(save_path)
    choice = loaded_willingness.inspect().choice
    assert choice is not None and choice.kind == "spell_willingness"
    healed = loaded_willingness.choose(choice.choice_id, "willing", choice.owner_actor_id)
    assert healed.status is ResultStatus.COMPLETED
    assert any(event.kind == "healing" for event in healed.events)
