"""Focused core tests for the additive class-family transaction seam."""

from dataclasses import dataclass
from types import SimpleNamespace
from pathlib import Path

from pf2e.content import get_definition, get_setup
from pf2e.encounter import Encounter
from pf2e.model import (
    ActionContinuation,
    ActiveConditionEffect,
    Cast,
    ChoiceOption,
    Choose,
    EffectExpiration,
    EndTurn,
    Event,
    FamilyCommand,
    FamilyProcedureResult,
    Interact,
    Position,
    ResultStatus,
    Step,
)
from pf2e.skill_actions import Demoralize, Escape, Grapple, Trip
from pf2e.persistence import _family_command_from_data, _family_command_to_data


def _keep_initial_choices(game: Encounter) -> None:
    while game.inspect().choice is not None:
        choice = game.inspect().choice
        assert choice is not None
        option_id = "keep" if any(option.option_id == "keep" for option in choice.options) else choice.options[0].option_id
        game.choose(choice.choice_id, option_id, choice.owner_actor_id)


def _view(game: Encounter, actor_id: str):
    return next(actor for actor in game.inspect().actors if actor.actor_id == actor_id)


def test_family_procedure_pause_saves_and_resumes_in_same_action_transaction(
    tmp_path: Path, monkeypatch,
) -> None:
    def handle_action(context):
        context.actor.actions_remaining -= 1
        saved_check = context.roll_skill_check("athletics", 15, traits=frozenset({"attack"}))
        face = context.dice.draw(6)
        context.present_choice(
            "test:resume",
            context.actor.actor_id,
            "Commit this family action?",
            (ChoiceOption("commit", "Commit"),),
            ActionContinuation(
                kind="test_family_action",
                actor_id=context.actor.actor_id,
                stage=f"rolled:{face}",
            ),
            saved_check=saved_check,
            family_command=context.command,
        )
        return FamilyProcedureResult(
            (Event("family_paused", context.actor.actor_id, None, f"Rolled {face}."),)
        )

    def handle_choice(context):
        assert context.pending is not None
        assert context.pending.procedure_id == "test:resume"
        assert context.pending.continuation is not None
        assert context.pending.continuation.stage == "rolled:6"
        assert context.pending.saved_check is not None
        assert context.pending.saved_check.result is not None
        assert context.pending.saved_check.result.die == 6
        assert context.pending.family_command == Trip("synthetic_b")
        assert context.choice is not None and context.choice.option_id == "commit"
        return FamilyProcedureResult(
            (Event("family_resumed", context.actor.actor_id, None, "Family action committed."),)
        )

    def validate_pending(context):
        pending = context.pending
        assert pending is not None
        assert pending.family_id == "martial"
        assert pending.procedure_id == "test:resume"
        assert pending.continuation is not None
        assert pending.continuation.stage == "rolled:6"
        assert pending.family_command == Trip("synthetic_b")

    handler = SimpleNamespace(
        handle_action=handle_action,
        handle_choice=handle_choice,
        validate_pending=validate_pending,
    )
    monkeypatch.setattr(Encounter, "_family_handler_module", lambda self, family_id: handler)
    game = Encounter.start(get_setup("s1_duel"), rolls=(20, 1, 6, 6))
    actor_id = game.inspect().turn_actor_id
    assert actor_id is not None
    before = next(actor for actor in game.inspect().actors if actor.actor_id == actor_id)

    paused = game.execute(Trip("synthetic_b"))
    assert paused.status is ResultStatus.PAUSED
    assert paused.inspection.choice is not None
    assert paused.inspection.choice.kind == "family_action"
    after_pause = next(actor for actor in paused.inspection.actors if actor.actor_id == actor_id)
    assert after_pause.actions_remaining == before.actions_remaining - 1
    assert after_pause.strikes_this_turn == before.strikes_this_turn + 1

    path = tmp_path / "family-action-choice.json"
    game.save(path)
    restored = Encounter.load(path)
    resumed = restored.execute(
        Choose(paused.inspection.choice.choice_id, "commit", actor_id)
    )
    assert resumed.status is ResultStatus.COMPLETED
    assert any(event.kind == "family_resumed" for event in resumed.events)
    after_resume = next(actor for actor in resumed.inspection.actors if actor.actor_id == actor_id)
    assert after_resume.actions_remaining == before.actions_remaining - 1


def test_family_rejection_discards_draft_actions_and_dice() -> None:
    attempts: list[int] = []

    class RejectFirstThenAccept:
        def handle_action(self, context):
            context.actor.actions_remaining -= 1
            face = context.dice.draw(6)
            attempts.append(face)
            if len(attempts) == 1:
                return FamilyProcedureResult(rejection="That family action is not legal.")
            return FamilyProcedureResult(
                (Event("family_roll", context.actor.actor_id, None, f"Rolled {face}."),)
            )

    game = Encounter.start(get_setup("s1_duel"), rolls=(20, 1, 6))
    actor_id = game.inspect().turn_actor_id
    assert actor_id is not None
    handler = RejectFirstThenAccept()
    game._family_handler_module = lambda family_id: handler

    from pf2e.model import FamilyCommand

    @dataclass(frozen=True)
    class RejectableFamilyAction(FamilyCommand):
        family_id: str = "martial"

    rejected = game.execute(RejectableFamilyAction())
    assert rejected.status is ResultStatus.REJECTED
    assert rejected.message == "That family action is not legal."
    after_rejection = next(actor for actor in rejected.inspection.actors if actor.actor_id == actor_id)
    assert after_rejection.actions_remaining == 3

    accepted = game.execute(RejectableFamilyAction())
    assert accepted.status is ResultStatus.COMPLETED
    assert any(event.text == "Rolled 6." for event in accepted.events)
    after_acceptance = next(actor for actor in accepted.inspection.actors if actor.actor_id == actor_id)
    assert after_acceptance.actions_remaining == 2
    assert attempts == [6, 6]


def test_pending_skill_command_encoders_are_fixed_and_typed() -> None:
    commands = (
        Trip("target", "trip_weapon"),
        Grapple("target", "grapple_weapon"),
        Escape("grapple:source:target", "unarmed_attack", "fist"),
        Demoralize("target", "Common", True),
    )
    assert tuple(_family_command_from_data(_family_command_to_data(command)) for command in commands) == commands


def test_current_save_and_skill_dc_use_explicit_statistic_triples() -> None:
    game = Encounter.start(get_setup("s2_fighters_vs_guard_dogs"), rolls=(20, 1, 20, 1))
    for actor in game._state.creatures.values():
        definition = get_definition(actor.definition_id)
        saves = {name: modifier for name, _rank, modifier in definition.saves}
        assert game._skill_dc(game._state, actor.actor_id, "fortitude") == 10 + saves["fortitude"]
        skills = {name: modifier for name, _rank, modifier in definition.skills}
        expected_athletics = skills.get("athletics", dict(definition.ability_modifiers).get("strength", 0))
        assert game._skill_dc(game._state, actor.actor_id, "athletics") == 10 + expected_athletics


def test_grabbed_interact_reaction_precedes_saved_flat_check_and_loses_effect(
    tmp_path: Path,
) -> None:
    game = Encounter.start(
        get_setup("s2_pc_duel_fixture"),
        # Initiative, successful Grapple, then failed Grabbed flat check.
        rolls=(20, 1, 11, 1, 10),
    )
    _keep_initial_choices(game)

    grapple = game.execute(Grapple("fighter_b"))
    assert grapple.status is ResultStatus.PAUSED
    grapple = game.choose(
        grapple.inspection.choice.choice_id, "keep", "fighter_a"
    )
    assert grapple.status is ResultStatus.COMPLETED
    assert game.execute(EndTurn()).status is ResultStatus.COMPLETED

    started = game.execute(Interact("stow", "longsword"))
    reaction = started.inspection.choice
    assert started.status is ResultStatus.PAUSED
    assert reaction is not None and reaction.kind == "reaction"
    assert reaction.owner_actor_id == "fighter_a"

    checked = game.choose(reaction.choice_id, "decline", "fighter_a")
    flat_choice = checked.inspection.choice
    assert checked.status is ResultStatus.PAUSED
    assert flat_choice is not None
    assert flat_choice.kind == "grabbed_manipulate_hero_reroll"
    assert any(event.kind == "grabbed_manipulate_flat_check" for event in checked.events)
    assert _view(game, "fighter_b").actions_remaining == 2
    assert "longsword" in _view(game, "fighter_b").held_items

    path = tmp_path / "grabbed-interact-flat-check.json"
    game.save(path)
    game = Encounter.load(path)
    assert game.inspect() == checked.inspection
    resolved = game.choose(flat_choice.choice_id, "keep", "fighter_b")
    assert resolved.status is ResultStatus.COMPLETED
    assert any(event.kind == "action_lost" for event in resolved.events)
    assert "longsword" in _view(game, "fighter_b").held_items

    rerolled_game = Encounter.load(path)
    rerolled = rerolled_game.choose(
        flat_choice.choice_id, "spend_hero_point", "fighter_b"
    )
    assert rerolled.status is ResultStatus.COMPLETED
    assert any(event.kind == "hero_reroll" for event in rerolled.events)
    assert _view(rerolled_game, "fighter_b").hero_points == 0
    assert "longsword" in _view(rerolled_game, "fighter_b").stowed_items


def test_grapple_ends_when_its_source_actually_moves() -> None:
    game = Encounter.start(
        get_setup("s2_pc_duel_fixture"), rolls=(20, 1, 11)
    )
    _keep_initial_choices(game)
    grapple = game.execute(Grapple("fighter_b"))
    grapple = game.choose(
        grapple.inspection.choice.choice_id, "keep", "fighter_a"
    )
    assert grapple.status is ResultStatus.COMPLETED
    assert any(
        effect.kind == "grabbed" and effect.target_actor_id == "fighter_b"
        for effect in _view(game, "fighter_b").condition_effects
    )

    moved = game.execute(Step(Position(4, 2)))
    assert moved.status is ResultStatus.COMPLETED
    assert any(event.kind == "condition_removed" for event in moved.events)
    assert not _view(game, "fighter_b").condition_effects


def test_grabbed_manipulate_cast_spends_slot_then_saved_flat_failure_stops_effect(
    tmp_path: Path,
) -> None:
    game = Encounter.start(
        get_setup("s3_interrupted_preparation"),
        # Five initiatives, then the Grabbed flat check after reaction decline.
        rolls=(1, 2, 20, 19, 3, 1),
    )
    _keep_initial_choices(game)
    assert game.inspect().turn_actor_id == "cleric_c"
    game._state.condition_effects.append(ActiveConditionEffect(
        "grapple:rapier_fighter:cleric_c",
        "grabbed",
        "rapier_fighter",
        "cleric_c",
        1,
        EffectExpiration("rapier_fighter", "end", 1),
    ))

    started = game.execute(Cast(
        "heal", "cleric_c", actions=2, slot_id="ordinary_heal_1"
    ))
    reaction = started.inspection.choice
    assert started.status is ResultStatus.PAUSED
    assert reaction is not None and reaction.kind == "reaction"
    checked = game.choose(reaction.choice_id, "decline", "rapier_fighter")
    flat_choice = checked.inspection.choice
    assert checked.status is ResultStatus.PAUSED
    assert flat_choice is not None
    assert flat_choice.kind == "grabbed_manipulate_hero_reroll"
    caster = _view(game, "cleric_c")
    assert caster.actions_remaining == 1
    assert next(
        slot for slot in caster.prepared_slots if slot.slot_id == "ordinary_heal_1"
    ).spent

    path = tmp_path / "grabbed-cast-flat-check.json"
    game.save(path)
    game = Encounter.load(path)
    resolved = game.choose(flat_choice.choice_id, "keep", "cleric_c")
    assert resolved.status is ResultStatus.COMPLETED
    assert any(event.kind == "action_lost" for event in resolved.events)
    assert not any(event.kind in {"healing", "spell_willingness"} for event in resolved.events)
