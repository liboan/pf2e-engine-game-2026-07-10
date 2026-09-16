from __future__ import annotations

from dataclasses import replace

from pf2e.content import CREATURES, SETUPS, get_definition, get_setup
from pf2e.encounter import Encounter
from pf2e.model import Choose, EndTurn, ResultStatus, Strike
from pf2e.skill_actions import Demoralize
from pf2e.swashbuckler import ConfidentFinisher, precise_strike_damage_term
from pf2e.terminal import render_inspection, render_support_summary, run_terminal
from terminal_test_helpers import BoundedInput, BoundedTranscript


SETUP_ID = "staged_braggart_swashbuckler_vs_guard_dog"


def _keep(game: Encounter, result):
    choice = result.inspection.choice
    assert choice is not None
    return game.execute(Choose(choice.choice_id, "keep", choice.owner_actor_id))


def _started_game(*rolls: int) -> Encounter:
    game = Encounter.start(get_setup(SETUP_ID), rolls=rolls)
    choice = game.inspect().choice
    if choice is not None:
        game.execute(Choose(choice.choice_id, "keep", choice.owner_actor_id))
    return game


def test_braggart_sheet_and_setup_remain_staged_with_legal_fixed_grants() -> None:
    definition = get_definition("swashbuckler_braggart_level_1")
    setup = get_setup(SETUP_ID)

    assert definition not in CREATURES.values()
    assert setup.setup_id not in SETUPS
    assert definition.class_name == "Swashbuckler"
    assert definition.abilities[:2] == ("swashbuckler", "swashbuckler_braggart")
    assert "Intimidating Glare" in definition.feats
    assert definition.skills[4] == ("intimidation", "trained", 5)
    assert definition.held_items == ("dagger_1",)
    assert definition.stowed_items == ("dagger_2", "dagger_3")
    assert {item.definition_id for item in definition.item_instances} == {"dagger"}
    assert setup.placements[0].definition_id == definition.definition_id


def test_braggart_demoralize_panache_and_ordinary_precise_strike() -> None:
    # Initiative d20s, Demoralize d20, Strike d20, dagger damage d4.
    game = _started_game(20, 1, 8, 8, 2)
    result = game.execute(
        Demoralize("braggart_dog", use_intimidating_glare=True)
    )
    assert result.status is ResultStatus.PAUSED
    result = _keep(game, result)
    braggart = next(actor for actor in result.inspection.actors if actor.actor_id == "braggart")
    dog = next(actor for actor in result.inspection.actors if actor.actor_id == "braggart_dog")
    assert braggart.panache
    assert braggart.panache_expires_at_end is None
    assert braggart.speed_ft == 30
    assert any(event.kind == "condition_applied" for event in result.events)

    result = game.execute(Strike("braggart_dog", "dagger"))
    result = _keep(game, result)
    damage_event = next(event for event in result.events if event.damage is not None)
    assert damage_event.damage is not None
    assert damage_event.damage.total == 6
    assert [component.source for component in damage_event.damage.components] == [
        "dagger",
        "swashbuckler_precise_strike",
    ]
    assert damage_event.damage.components[1].amount == 2
    assert next(actor for actor in result.inspection.actors if actor.actor_id == "braggart_dog").hp == 2
    assert next(actor for actor in result.inspection.actors if actor.actor_id == "braggart").panache


def test_braggart_path_reaches_public_victory_and_clears_encounter_panache() -> None:
    # Initiative d20s, Demoralize d20, critical Strike d20, two critical
    # dagger damage dice. The critical Strike deals 9 and defeats the dog.
    game = _started_game(20, 1, 8, 20, 2, 3)
    result = _keep(
        game,
        game.execute(Demoralize("braggart_dog", use_intimidating_glare=True)),
    )
    assert next(actor for actor in result.inspection.actors if actor.actor_id == "braggart").panache
    result = _keep(game, game.execute(Strike("braggart_dog", "dagger")))
    assert result.status is ResultStatus.COMPLETED
    assert not result.inspection.in_progress
    assert result.inspection.winner_team == "blue"
    assert not next(actor for actor in result.inspection.actors if actor.actor_id == "braggart").panache


def test_confident_finisher_success_pauses_with_replacement_precision_damage() -> None:
    # Initiative d20s, Demoralize d20, finisher d20, dagger d4, finisher 2d6.
    game = _started_game(20, 1, 8, 11, 2, 3, 4)
    _keep(game, game.execute(Demoralize("braggart_dog", use_intimidating_glare=True)))

    result = game.execute(ConfidentFinisher("braggart_dog", attack_id="dagger"))
    assert result.status is ResultStatus.PAUSED
    if result.inspection.choice is not None and result.inspection.choice.kind == "attack_hero_reroll":
        result = _keep(game, result)
    assert any(event.kind == "confident_finisher_success" for event in result.events)
    choice = result.inspection.choice
    assert choice is not None
    assert [option.option_id for option in choice.options] == ["full_damage", "failure_effect"]
    braggart = next(actor for actor in result.inspection.actors if actor.actor_id == "braggart")
    assert not braggart.panache
    assert braggart.actions_remaining == 1
    assert braggart.strikes_this_turn == 1


def test_confident_finisher_success_choice_saves_and_applies_failure_effect(tmp_path) -> None:
    game = _started_game(20, 1, 8, 11, 2, 3, 4)
    _keep(game, game.execute(Demoralize("braggart_dog", use_intimidating_glare=True)))
    result = game.execute(ConfidentFinisher("braggart_dog", attack_id="dagger"))
    if result.inspection.choice is not None and result.inspection.choice.kind == "attack_hero_reroll":
        result = _keep(game, result)
    choice = result.inspection.choice
    assert choice is not None

    path = tmp_path / "confident-finisher-choice.json"
    game.save(path)
    loaded = Encounter.load(path)
    saved_choice = loaded.inspect().choice
    assert saved_choice is not None
    assert saved_choice.options[1].option_id == "failure_effect"
    result = loaded.execute(Choose(saved_choice.choice_id, "failure_effect", "braggart"))
    damage_event = next(event for event in result.events if event.damage is not None)
    assert damage_event.damage is not None
    assert damage_event.damage.total == 3
    assert damage_event.damage.components[0].source == "confident_finisher_failure"
    assert damage_event.damage.components[0].damage_type == "piercing"
    assert next(actor for actor in result.inspection.actors if actor.actor_id == "braggart_dog").hp == 5


def test_confident_finisher_failure_halves_rolled_precision_and_critical_failure_is_zero() -> None:
    failed = _started_game(20, 1, 8, 2, 4, 5)
    _keep(failed, failed.execute(Demoralize("braggart_dog", use_intimidating_glare=True)))
    result = failed.execute(ConfidentFinisher("braggart_dog", attack_id="dagger"))
    if result.inspection.choice is not None and result.inspection.choice.kind == "attack_hero_reroll":
        result = _keep(failed, result)
    damage_event = next(event for event in result.events if event.kind == "confident_finisher_failure")
    assert damage_event.damage is not None
    assert damage_event.damage.total == 4  # floor((4 + 5) / 2)
    assert damage_event.damage.components[0].damage_type == "piercing"

    critical = _started_game(20, 1, 8, 1)
    _keep(critical, critical.execute(Demoralize("braggart_dog", use_intimidating_glare=True)))
    result = critical.execute(ConfidentFinisher("braggart_dog", attack_id="dagger"))
    if result.inspection.choice is not None and result.inspection.choice.kind == "attack_hero_reroll":
        result = _keep(critical, result)
    assert any(event.kind == "confident_finisher_critical_failure" for event in result.events)
    assert not any(event.damage is not None for event in result.events)
    assert next(actor for actor in result.inspection.actors if actor.actor_id == "braggart_dog").hp == 8


def test_confident_finisher_blocks_attack_actions_until_the_next_turn() -> None:
    game = _started_game(20, 1, 8, 2, 4, 5, 20, 1)
    _keep(game, game.execute(Demoralize("braggart_dog", use_intimidating_glare=True)))
    result = game.execute(ConfidentFinisher("braggart_dog", attack_id="dagger"))
    if result.inspection.choice is not None and result.inspection.choice.kind == "attack_hero_reroll":
        result = _keep(game, result)
    assert result.inspection.choice is None
    blocked = game.execute(Strike("braggart_dog", "dagger"))
    assert blocked.status is ResultStatus.REJECTED
    assert "finisher_attack_lockout" in blocked.message
    assert game.inspect().actors[0].actions_remaining == 1

    game.execute(EndTurn())
    game.execute(EndTurn())
    result = _keep(game, game.execute(Strike("braggart_dog", "dagger")))
    assert result.status in {ResultStatus.COMPLETED, ResultStatus.PAUSED}
    assert any(event.kind == "strike" for event in result.events)


def test_confident_finisher_critical_success_doubles_the_2d6_precision_term() -> None:
    game = _started_game(20, 1, 8, 20, 2, 3, 4)
    _keep(game, game.execute(Demoralize("braggart_dog", use_intimidating_glare=True)))
    result = game.execute(ConfidentFinisher("braggart_dog", attack_id="dagger"))
    if result.inspection.choice is not None and result.inspection.choice.kind == "attack_hero_reroll":
        result = _keep(game, result)
    choice = result.inspection.choice
    assert choice is not None
    result = game.execute(Choose(choice.choice_id, "full_damage", "braggart"))
    damage_event = next(event for event in result.events if event.kind == "damage")
    assert damage_event.damage is not None
    assert damage_event.damage.total == 22
    assert damage_event.damage.components[1].amount == 14
    assert result.inspection.winner_team == "blue"


def test_confident_finisher_without_panache_rejects_before_spending_action() -> None:
    game = _started_game(20, 1, 8)
    before = next(actor for actor in game.inspect().actors if actor.actor_id == "braggart")
    result = game.execute(ConfidentFinisher("braggart_dog", attack_id="dagger"))
    after = next(actor for actor in game.inspect().actors if actor.actor_id == "braggart")
    assert result.status is ResultStatus.REJECTED
    assert "Panache" in result.message
    assert after.actions_remaining == before.actions_remaining
    assert after.strikes_this_turn == before.strikes_this_turn
    assert not after.finisher_used_this_turn
    wrong_target = game.execute(ConfidentFinisher("missing_target", attack_id="dagger"))
    assert wrong_target.status is ResultStatus.REJECTED
    assert "active creature" in wrong_target.message
    after_wrong_target = next(actor for actor in game.inspect().actors if actor.actor_id == "braggart")
    assert after_wrong_target.actions_remaining == before.actions_remaining


def test_precise_strike_applies_without_panache() -> None:
    game = _started_game(20, 1, 8, 2)
    result = _keep(game, game.execute(Strike("braggart_dog", "dagger")))
    braggart = next(actor for actor in result.inspection.actors if actor.actor_id == "braggart")
    damage_event = next(event for event in result.events if event.damage is not None)
    assert not braggart.panache
    assert damage_event.damage is not None
    assert damage_event.damage.components[-1].source == "swashbuckler_precise_strike"
    assert damage_event.damage.components[-1].amount == 2


def test_braggart_can_gain_panache_through_language_mismatch_and_bypass_attempt_immunity() -> None:
    game = _started_game(20, 1, 14, 1)
    result = game.execute(Demoralize("braggart_dog", spoken_language="Common"))
    result = _keep(game, result)
    check = next(event.check for event in result.events if event.kind == "demoralize_check")
    assert check is not None
    assert check.modifier == 2  # +5 Intimidation, +1 Stylish, -4 language barrier
    braggart = next(actor for actor in result.inspection.actors if actor.actor_id == "braggart")
    assert braggart.panache and braggart.panache_expires_at_end is None

    # The target is now immune to this actor's ordinary Demoralize attempt.
    # Braggart Bravado still resolves the critical failure and leaves lasting
    # Panache intact.
    result = game.execute(Demoralize("braggart_dog", use_intimidating_glare=True))
    result = _keep(game, result)
    assert result.status is ResultStatus.COMPLETED
    check = next(event.check for event in result.events if event.kind == "demoralize_check")
    assert check.degree.name == "CRITICAL_FAILURE"
    braggart = next(actor for actor in result.inspection.actors if actor.actor_id == "braggart")
    assert braggart.panache and braggart.panache_expires_at_end is None


def test_braggart_immunity_bypass_grants_panache_without_reapplying_frightened() -> None:
    game = _started_game(20, 1, 14, 14)
    first = _keep(
        game,
        game.execute(Demoralize("braggart_dog", use_intimidating_glare=True)),
    )
    assert any(event.kind == "condition_applied" for event in first.events)
    repeated = _keep(
        game,
        game.execute(Demoralize("braggart_dog", use_intimidating_glare=True)),
    )
    assert any(event.kind == "demoralize_check" for event in repeated.events)
    assert not any(event.kind == "condition_applied" for event in repeated.events)
    assert next(actor for actor in repeated.inspection.actors if actor.actor_id == "braggart").panache


def test_braggart_critical_failure_does_not_create_panache() -> None:
    game = _started_game(20, 1, 1)
    result = _keep(
        game,
        game.execute(Demoralize("braggart_dog", use_intimidating_glare=True)),
    )
    check = next(event.check for event in result.events if event.kind == "demoralize_check")
    assert check is not None and check.degree.name == "CRITICAL_FAILURE"
    braggart = next(actor for actor in result.inspection.actors if actor.actor_id == "braggart")
    assert not braggart.panache


def test_braggart_failure_panache_expires_at_end_of_next_turn_and_save_round_trips(
    tmp_path,
) -> None:
    game = _started_game(20, 1, 4)
    result = game.execute(Demoralize("braggart_dog", use_intimidating_glare=True))
    result = _keep(game, result)
    braggart = next(actor for actor in result.inspection.actors if actor.actor_id == "braggart")
    assert braggart.panache and braggart.panache_expires_at_end == 2

    path = tmp_path / "braggart-panache.json"
    game.save(path)
    loaded = Encounter.load(path)
    loaded_braggart = next(actor for actor in loaded.inspect().actors if actor.actor_id == "braggart")
    assert loaded_braggart.panache
    assert loaded_braggart.panache_expires_at_end == 2
    assert loaded_braggart.speed_ft == 30

    # Braggart end count 1, dog end count 1, Braggart end count 2.
    loaded.execute(EndTurn())
    loaded.execute(EndTurn())
    result = loaded.execute(EndTurn())
    loaded_braggart = next(actor for actor in result.inspection.actors if actor.actor_id == "braggart")
    assert not loaded_braggart.panache
    assert loaded_braggart.speed_ft == 25


def test_precise_strike_rejects_non_agile_non_finesse_attack() -> None:
    definition = get_definition("swashbuckler_braggart_level_1")
    dagger = definition.attacks[0]
    nonqualifying = replace(dagger, traits=frozenset({"attack", "melee", "weapon"}))
    assert precise_strike_damage_term(definition, nonqualifying) is None


def test_terminal_inspection_surfaces_panache_and_effective_speed() -> None:
    game = _started_game(20, 1, 8)
    result = _keep(game, game.execute(Demoralize("braggart_dog", use_intimidating_glare=True)))
    rendered = render_inspection(result.inspection, include_sheets=True)
    assert "Panache active" in rendered
    assert "Speed 30 ft" in rendered
    assert "remain unsupported" in render_support_summary(SETUP_ID)


def test_terminal_braggart_completes_demoralize_and_precise_strike_victory() -> None:
    transcript = BoundedTranscript()
    state = {"menu": "", "prompt": "", "choice_block": "", "target": "", "phase": "demoralize"}

    def output(line: str) -> None:
        transcript.append(line)
        if line.startswith("1. "):
            state["menu"] = line
        if "choice owner:" in line:
            state["choice_block"] = line
        if line in {"Target number:", "Dagger target:"}:
            state["target"] = line
        if line.endswith(":"):
            state["prompt"] = line

    def choose(label: str, *, prefix: bool = False) -> str:
        for row in state["menu"].splitlines():
            parts = row.split(". ", 1)
            if len(parts) == 2 and (parts[1].startswith(label) if prefix else parts[1] == label):
                return parts[0]
        raise AssertionError(f"menu label missing: {label!r} in {state['menu']!r}")

    def scripted_input() -> str:
        prompt = state["prompt"]
        if prompt == "Choice prompt action:":
            return choose("Resolve this choice")
        if prompt == "Choice option number:":
            if "initiative" in state["choice_block"]:
                return choose("Keep initiative")
            if "Strike check" in state["choice_block"]:
                return choose("Keep result")
            return choose("Keep the current result")
        if prompt == "Choice:":
            if state["phase"] == "demoralize":
                state["phase"] = "strike"
                return choose("Demoralize")
            if state["phase"] == "strike":
                state["phase"] = "finished"
                return choose("Strike")
            return choose("Quit")
        if prompt == "Target number:":
            return choose("Guard Dog", prefix=True)
        if prompt == "Dagger target:":
            return choose("Guard Dog", prefix=True)
        if prompt == "Weapon / attack number:":
            return choose("Dagger", prefix=True)
        if prompt == "Damage intent:":
            return choose("Use attack default", prefix=True)
        if prompt.startswith("Use Intimidating Glare"):
            return "y"
        raise AssertionError(f"unexpected terminal prompt: {prompt!r}")

    result = run_terminal(
        setup=get_setup(SETUP_ID),
        rolls=(20, 1, 8, 20, 2, 3),
        input_fn=BoundedInput(scripted_input, max_calls=40),
        output_fn=output,
    )
    rendered = "\n".join(transcript)
    assert result == 0
    assert "Guard Dog (red) — HP 0/8" in rendered
    assert "Panache active" in rendered


def test_terminal_braggart_completes_melee_confident_finisher_victory() -> None:
    transcript = BoundedTranscript()
    state = {"menu": "", "prompt": "", "choice_block": "", "phase": "demoralize"}

    def output(line: str) -> None:
        transcript.append(line)
        if line.startswith("1. "):
            state["menu"] = line
        if "choice owner:" in line:
            state["choice_block"] = line
        if line.endswith(":"):
            state["prompt"] = line

    def choose(label: str, *, prefix: bool = False) -> str:
        for row in state["menu"].splitlines():
            parts = row.split(". ", 1)
            if len(parts) == 2 and (parts[1].startswith(label) if prefix else parts[1] == label):
                return parts[0]
        raise AssertionError(f"menu label missing: {label!r} in {state['menu']!r}")

    def scripted_input() -> str:
        prompt = state["prompt"]
        if prompt == "Choice prompt action:":
            return choose("Resolve this choice")
        if prompt == "Choice option number:":
            if "initiative" in state["choice_block"]:
                return choose("Keep initiative")
            if "Apply full Strike damage" in state["menu"]:
                return choose("Apply full Strike damage")
            if "Keep result" in state["menu"]:
                return choose("Keep result")
            return choose("Keep the current result")
        if prompt == "Choice:":
            if state["phase"] == "demoralize":
                state["phase"] = "finisher"
                return choose("Demoralize")
            if state["phase"] == "finisher":
                state["phase"] = "finished"
                return choose("Confident Finisher")
            return choose("Quit")
        if prompt in {"Target number:", "Demoralize target:"} or prompt.endswith("target:"):
            return choose("Guard Dog", prefix=True)
        if prompt == "Weapon / attack number:":
            return choose("Dagger", prefix=True)
        if prompt == "Damage intent:":
            return choose("Use attack default", prefix=True)
        if prompt.startswith("Use Intimidating Glare"):
            return "y"
        raise AssertionError(f"unexpected terminal prompt: {prompt!r}")

    result = run_terminal(
        setup=get_setup(SETUP_ID),
        rolls=(20, 1, 8, 20, 2, 3, 4),
        input_fn=BoundedInput(scripted_input, max_calls=60),
        output_fn=output,
    )
    rendered = "\n".join(transcript)
    assert result == 0
    assert "Guard Dog (red) — HP 0/8" in rendered
    assert "Confident Finisher" in rendered
