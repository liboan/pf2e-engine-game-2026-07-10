from pf2e.checks import DegreeOfSuccess, Modifier
from pathlib import Path

from pf2e.content import S3_SETUP, get_setup
from pf2e.encounter import Encounter
from pf2e.model import Cast, Choose, EndTurn, ResultStatus, Stand, Step, Strike, Stride, Position
from pf2e.skill_actions import (
    Demoralize,
    Escape,
    Grapple,
    Trip,
    resolve_demoralize,
    resolve_escape,
    resolve_grapple,
    resolve_trip,
)
from pf2e.skill_content import DEMORALIZE, ESCAPE, GRAPPLE, TRIP, maneuver_target_size_allowed


def _roller(*faces):
    values = iter(faces)

    def roll(sides):
        face = next(values)
        assert 1 <= face <= sides
        return face

    return roll


def _ready_pc_duel(*rolls):
    """Use the admitted public PC duel fixture and retain all start choices."""
    game = Encounter.start(get_setup("s2_pc_duel_fixture"), rolls=rolls)
    while game.inspect().choice is not None:
        choice = game.inspect().choice
        assert choice.kind == "initiative_hero_reroll"
        result = game.choose(choice.choice_id, "keep", choice.owner_actor_id)
        assert result.status in {ResultStatus.COMPLETED, ResultStatus.PAUSED}
    assert game.inspect().turn_actor_id == "fighter_a"
    return game


def _actor(game, actor_id):
    return next(actor for actor in game.inspect().actors if actor.actor_id == actor_id)


def _keep_hero_choice(game, result):
    if result.status is not ResultStatus.PAUSED:
        return result
    choice = result.inspection.choice
    assert choice is not None
    if {option.option_id for option in choice.options} in ({"keep", "reroll"}, {"keep", "spend_hero_point"}):
        return game.choose(choice.choice_id, "keep", choice.owner_actor_id)
    return result


def test_source_facts_fix_action_costs_traits_and_demoralize_range():
    assert (TRIP.action_cost, TRIP.check_skill, TRIP.target_dc, TRIP.traits) == (
        1,
        "athletics",
        "reflex",
        frozenset({"attack"}),
    )
    assert (GRAPPLE.action_cost, GRAPPLE.check_skill, GRAPPLE.target_dc) == (1, "athletics", "fortitude")
    assert (ESCAPE.action_cost, ESCAPE.target_dc, ESCAPE.traits) == (1, "selected_impediment", frozenset({"attack"}))
    assert DEMORALIZE.action_cost == 1
    assert DEMORALIZE.range_ft == 30
    assert DEMORALIZE.requires_aware_target
    assert {"auditory", "concentrate", "emotion", "fear", "mental"} == DEMORALIZE.traits
    assert maneuver_target_size_allowed("medium", "large")
    assert not maneuver_target_size_allowed("medium", "huge")


def test_trip_applies_map_and_rolls_one_bludgeoning_die_only_on_critical_success():
    result = resolve_trip(
        roll=_roller(20, 4),
        user_id="user",
        target_id="target",
        modifier=10,
        dc=21,
        attacks_already_made=1,
        modifiers=(Modifier(1, "item", "maneuver weapon"),),
    )

    assert result.check.degree is DegreeOfSuccess.CRITICAL_SUCCESS
    assert result.check.degree_before_adjustments is DegreeOfSuccess.SUCCESS
    assert result.check.map_penalty == -5
    assert result.check.modifier == 6
    assert result.target_falls_prone
    assert not result.user_falls_prone
    assert result.critical_damage is not None
    assert result.critical_damage.components[0].damage_type == "bludgeoning"
    assert result.critical_damage.components[0].dice == (6,)
    assert result.critical_damage.total == 4


def test_trip_critical_failure_makes_user_prone_without_dealing_damage():
    result = resolve_trip(
        roll=_roller(1),
        user_id="user",
        target_id="target",
        modifier=20,
        dc=20,
        attacks_already_made=2,
    )

    assert result.check.degree is DegreeOfSuccess.CRITICAL_FAILURE
    assert not result.target_falls_prone
    assert result.user_falls_prone
    assert result.critical_damage is None


def test_grapple_keeps_or_releases_existing_grapple_by_degree_and_exposes_critical_choice():
    success = resolve_grapple(
        roll=_roller(10),
        user_id="user",
        target_id="target",
        modifier=10,
        dc=20,
        attacks_already_made=0,
        already_holding_target=True,
    )
    critical_failure = resolve_grapple(
        roll=_roller(1),
        user_id="user",
        target_id="target",
        modifier=10,
        dc=20,
        attacks_already_made=0,
        already_holding_target=True,
    )

    assert success.target_condition == "grabbed"
    assert not success.release_user_grapple
    assert not success.offer_target_response
    assert critical_failure.check.degree is DegreeOfSuccess.CRITICAL_FAILURE
    assert critical_failure.target_condition is None
    assert critical_failure.release_user_grapple
    assert critical_failure.offer_target_response


def test_escape_uses_selected_impediment_and_attack_map_with_exact_degree_effects():
    critical = resolve_escape(
        roll=_roller(20),
        user_id="user",
        impediment_id="net-effect",
        modifier=15,
        dc=25,
        attacks_already_made=1,
        check_method="acrobatics",
    )
    critical_failure = resolve_escape(
        roll=_roller(1),
        user_id="user",
        impediment_id="grab-effect",
        modifier=10,
        dc=10,
        attacks_already_made=2,
        check_method="athletics",
    )

    assert critical.check.degree is DegreeOfSuccess.CRITICAL_SUCCESS
    assert critical.check.map_penalty == -5
    assert critical.free_of_selected_impediment
    assert critical.remove_grabbed_immobilized_restrained
    assert critical.followup_stride_ft == 5
    assert not critical.retry_blocked_until_next_turn
    assert critical_failure.check.degree is DegreeOfSuccess.CRITICAL_FAILURE
    assert critical_failure.check.map_penalty == -10
    assert not critical_failure.free_of_selected_impediment
    assert not critical_failure.remove_grabbed_immobilized_restrained
    assert critical_failure.followup_stride_ft == 0
    assert critical_failure.retry_blocked_until_next_turn


def test_demoralize_language_penalty_is_circumstance_and_glare_replaces_auditory():
    ordinary = resolve_demoralize(
        roll=_roller(10),
        user_id="user",
        target_id="target",
        modifier=12,
        dc=19,
        speech_understood=False,
        use_intimidating_glare=False,
    )
    glare = resolve_demoralize(
        roll=_roller(10),
        user_id="user",
        target_id="target",
        modifier=12,
        dc=19,
        speech_understood=False,
        use_intimidating_glare=True,
    )

    assert ordinary.check.modifier == 8
    assert ordinary.check.degree is DegreeOfSuccess.FAILURE
    assert ordinary.check.map_penalty == 0
    assert "auditory" in ordinary.traits
    assert "visual" not in ordinary.traits
    assert ordinary.target_immune_for_seconds == 600
    assert glare.check.modifier == 12
    assert glare.check.degree is DegreeOfSuccess.SUCCESS
    assert glare.frightened_value == 1
    assert glare.apply_frightened
    assert "visual" in glare.traits
    assert "auditory" not in glare.traits


def test_demoralize_applies_no_frightened_when_target_is_immune_but_keeps_attempt_immunity():
    result = resolve_demoralize(
        roll=_roller(20),
        user_id="user",
        target_id="target",
        modifier=10,
        dc=20,
        speech_understood=True,
        use_intimidating_glare=False,
        target_frightened_immune=True,
    )

    assert result.frightened_value == 2
    assert not result.apply_frightened
    assert result.target_immune_for_seconds == 600


def test_public_trip_saved_hero_choice_round_trips_then_applies_damage_and_prone(tmp_path: Path):
    game = _ready_pc_duel(20, 1, 20, 4)

    paused = game.execute(Trip("fighter_b"))
    assert paused.status is ResultStatus.PAUSED
    choice = paused.inspection.choice
    assert choice is not None and {option.option_id for option in choice.options} == {"keep", "reroll"}
    assert _actor(game, "fighter_a").actions_remaining == 2
    assert _actor(game, "fighter_a").strikes_this_turn == 1

    path = tmp_path / "trip-hero-choice.json"
    game.save(path)
    game = Encounter.load(path)
    assert game.inspect() == paused.inspection
    result = game.choose(choice.choice_id, "keep", choice.owner_actor_id)

    assert result.status is ResultStatus.COMPLETED
    check_event = next(event for event in result.events if event.kind == "trip_check")
    assert check_event.check is not None
    assert check_event.check.dc == 16
    assert check_event.check.degree is DegreeOfSuccess.CRITICAL_SUCCESS
    assert _actor(game, "fighter_b").prone
    assert _actor(game, "fighter_b").hp == 17
    assert _actor(game, "fighter_a").actions_remaining == 2
    assert _actor(game, "fighter_a").strikes_this_turn == 1
    assert check_event.check.attack_count == 1


def test_public_grapple_critical_failure_saves_target_choice_and_resumes():
    game = _ready_pc_duel(20, 1, 1)

    paused = game.execute(Grapple("fighter_b"))

    if paused.status is ResultStatus.PAUSED and paused.inspection.choice is not None:
        assert {option.option_id for option in paused.inspection.choice.options} == {"keep", "reroll"}
        paused = game.choose(paused.inspection.choice.choice_id, "keep", "fighter_a")

    assert paused.status is ResultStatus.PAUSED
    choice = paused.inspection.choice
    assert choice is not None
    assert choice.owner_actor_id == "fighter_b"
    assert {option.option_id for option in choice.options} == {"grab_user", "make_user_prone"}
    assert _actor(game, "fighter_a").actions_remaining == 2
    result = game.choose(choice.choice_id, "make_user_prone", "fighter_b")
    assert result.status is ResultStatus.COMPLETED
    assert _actor(game, "fighter_a").prone
    assert any(event.kind == "condition_applied" for event in result.events)


def test_public_escape_uses_unarmed_attack_and_current_grappler_dc_after_save_load(tmp_path: Path):
    game = _ready_pc_duel(20, 1, 11, 10)

    grapple = game.execute(Grapple("fighter_b"))
    grapple = _keep_hero_choice(game, grapple)
    assert grapple.status is ResultStatus.COMPLETED
    assert any(event.kind == "condition_applied" for event in grapple.events)
    game.execute(EndTurn())
    assert game.inspect().turn_actor_id == "fighter_b"
    assert any(effect.kind == "grabbed" and effect.source_actor_id == "fighter_a" for effect in _actor(game, "fighter_b").condition_effects)

    effect_id = "grapple:fighter_a:fighter_b"
    paused = game.execute(Escape(effect_id, "unarmed_attack", "fist"))
    assert paused.status is ResultStatus.PAUSED
    choice = paused.inspection.choice
    assert choice is not None and {option.option_id for option in choice.options} == {"keep", "reroll"}
    path = tmp_path / "escape-check.json"
    game.save(path)
    game = Encounter.load(path)
    escaped = game.choose(choice.choice_id, "keep", choice.owner_actor_id)

    assert escaped.status is ResultStatus.COMPLETED
    check_event = next(event for event in escaped.events if event.kind == "escape_check")
    assert check_event.check is not None
    assert check_event.check.dc == 17
    assert check_event.check.attack_id == "fist"
    assert check_event.check.degree is DegreeOfSuccess.SUCCESS
    assert any(event.kind == "condition_removed" for event in escaped.events)
    assert _actor(game, "fighter_b").actions_remaining == 2


def test_standing_escape_critical_success_stride_saves_and_resumes_movement_reaction(tmp_path: Path):
    game = _ready_pc_duel(20, 1, 11, 20)

    grappled = _keep_hero_choice(game, game.execute(Grapple("fighter_b")))
    assert grappled.status is ResultStatus.COMPLETED
    assert not _actor(game, "fighter_b").prone
    assert game.execute(EndTurn()).status is ResultStatus.COMPLETED
    assert game.inspect().turn_actor_id == "fighter_b"
    assert _actor(game, "fighter_b").actions_remaining == 3

    escaped = _keep_hero_choice(game, game.execute(Escape("grapple:fighter_a:fighter_b", "athletics")))
    assert escaped.status is ResultStatus.PAUSED
    stride_choice = escaped.inspection.choice
    assert stride_choice is not None
    stride_options = {option.option_id for option in stride_choice.options}
    assert "stay" in stride_options
    assert any(option.startswith("stride:") for option in stride_options)
    escape_check = next(event.check for event in escaped.events if event.kind == "escape_check")
    assert escape_check is not None
    assert (escape_check.die, escape_check.dc, escape_check.total) == (20, 17, 27)
    assert escape_check.degree is DegreeOfSuccess.CRITICAL_SUCCESS
    assert escape_check.attack_count == 1
    assert escape_check.map_penalty == 0
    assert not any(effect.kind in {"grabbed", "restrained", "immobilized"} for effect in _actor(game, "fighter_b").condition_effects)

    path = tmp_path / "escape-stride-choice.json"
    game.save(path)
    game = Encounter.load(path)
    assert game.inspect() == escaped.inspection
    stride_choice = game.inspect().choice
    assert stride_choice is not None
    destination_option = next(option.option_id for option in stride_choice.options if option.option_id.startswith("stride:"))
    _, x, y = destination_option.split(":")
    destination = Position(int(x), int(y))
    movement = game.choose(stride_choice.choice_id, destination_option, stride_choice.owner_actor_id)

    assert movement.status is ResultStatus.PAUSED
    reaction = movement.inspection.choice
    assert reaction is not None and reaction.kind == "reaction"
    assert reaction.owner_actor_id == "fighter_a"
    assert "decline" in {option.option_id for option in reaction.options}
    assert _actor(game, "fighter_b").position == Position(5, 1)
    assert _actor(game, "fighter_b").actions_remaining == 2
    assert _actor(game, "fighter_b").strikes_this_turn == 1

    reaction_path = tmp_path / "escape-stride-reaction.json"
    game.save(reaction_path)
    snapshot = game.inspect()
    game = Encounter.load(reaction_path)
    assert game.inspect() == snapshot
    reaction = game.inspect().choice
    assert reaction is not None
    moved = game.choose(reaction.choice_id, "decline", reaction.owner_actor_id)

    assert moved.status is ResultStatus.COMPLETED
    assert any(event.kind == "reaction_declined" for event in moved.events)
    assert any(event.kind == "move_step" and event.position == destination for event in moved.events)
    assert _actor(game, "fighter_b").position == destination
    assert _actor(game, "fighter_b").actions_remaining == 2
    assert _actor(game, "fighter_b").strikes_this_turn == 1
    assert not any(effect.kind in {"grabbed", "restrained", "immobilized"} for effect in _actor(game, "fighter_b").condition_effects)


def test_moving_grappler_releases_sourced_hold_after_actual_square_change():
    game = _ready_pc_duel(20, 1, 11)

    grapple = _keep_hero_choice(game, game.execute(Grapple("fighter_b")))
    assert grapple.status is ResultStatus.COMPLETED
    effect_id = "grapple:fighter_a:fighter_b"
    assert any(effect.effect_id == effect_id for effect in _actor(game, "fighter_b").condition_effects)

    moved = game.execute(Step(Position(4, 0)))

    assert moved.status is ResultStatus.COMPLETED
    assert _actor(game, "fighter_a").position == Position(4, 0)
    assert not any(effect.effect_id == effect_id for effect in _actor(game, "fighter_b").condition_effects)
    assert any(event.kind == "condition_removed" and event.target_id == "fighter_b" for event in moved.events)


def test_public_demoralize_applies_frightened_and_source_target_immunity():
    game = _ready_pc_duel(20, 1, 11)

    result = game.execute(Demoralize("fighter_b", spoken_language="Common"))
    result = _keep_hero_choice(game, result)

    assert result.status is ResultStatus.COMPLETED
    check_event = next(event for event in result.events if event.kind == "demoralize_check")
    assert check_event.check is not None
    assert check_event.check.dc == 14
    assert check_event.check.degree is DegreeOfSuccess.SUCCESS
    assert any(event.kind == "condition_applied" and "frightened 1" in event.text for event in result.events)
    assert any(event.kind == "immunity_applied" for event in result.events)
    assert any(condition.kind == "frightened" and condition.value == 1 for condition in _actor(game, "fighter_b").condition_effects)
    repeated = game.execute(Demoralize("fighter_b", spoken_language="Common"))
    assert repeated.status is ResultStatus.REJECTED
    assert "temporarily immune" in repeated.message
    assert _actor(game, "fighter_a").actions_remaining == 2
    assert game.execute(EndTurn()).status is ResultStatus.COMPLETED
    assert any(condition.kind == "frightened" for condition in _actor(game, "fighter_b").condition_effects)
    assert game.execute(EndTurn()).status is ResultStatus.COMPLETED
    assert not any(condition.kind == "frightened" for condition in _actor(game, "fighter_b").condition_effects)


def test_public_demoralize_failure_still_grants_attempt_immunity():
    game = _ready_pc_duel(20, 1, 6)

    result = _keep_hero_choice(game, game.execute(Demoralize("fighter_b", spoken_language="Common")))

    assert result.status is ResultStatus.COMPLETED
    check_event = next(event for event in result.events if event.kind == "demoralize_check")
    assert check_event.check is not None and check_event.check.degree is DegreeOfSuccess.FAILURE
    assert not any(event.kind == "condition_applied" and "frightened" in event.text for event in result.events)
    assert any(event.kind == "immunity_applied" for event in result.events)
    assert _actor(game, "fighter_a").actions_remaining == 2
    assert game.execute(Demoralize("fighter_b", spoken_language="Common")).status is ResultStatus.REJECTED


def test_public_escape_critical_failure_blocks_retry_without_charging_again():
    game = _ready_pc_duel(20, 1, 11, 1)
    grapple = _keep_hero_choice(game, game.execute(Grapple("fighter_b")))
    assert grapple.status is ResultStatus.COMPLETED
    game.execute(EndTurn())
    effect_id = "grapple:fighter_a:fighter_b"

    failed = _keep_hero_choice(game, game.execute(Escape(effect_id, "athletics")))

    assert failed.status is ResultStatus.COMPLETED
    check_event = next(event for event in failed.events if event.kind == "escape_check")
    assert check_event.check is not None and check_event.check.degree is DegreeOfSuccess.CRITICAL_FAILURE
    actions = _actor(game, "fighter_b").actions_remaining
    attacks = _actor(game, "fighter_b").strikes_this_turn
    retry = game.execute(Escape(effect_id, "athletics"))
    assert retry.status is ResultStatus.REJECTED
    assert "until the start of your next turn" in retry.message
    assert _actor(game, "fighter_b").actions_remaining == actions
    assert _actor(game, "fighter_b").strikes_this_turn == attacks


def test_public_trip_condition_changes_ac_and_enables_stand_then_restores_ac():
    game = _ready_pc_duel(20, 1, 10, 3)

    trip = _keep_hero_choice(game, game.execute(Trip("fighter_b")))
    assert trip.status is ResultStatus.COMPLETED
    target = _actor(game, "fighter_b")
    assert target.prone
    prone_ac = target.ac

    strike = _keep_hero_choice(game, game.execute(Strike("fighter_b", attack_id="longsword")))
    strike_check = next(event.check for event in strike.events if event.check is not None)
    assert strike_check is not None and strike_check.dc == prone_ac
    assert "stand" not in game.options().available_actions

    assert game.execute(EndTurn()).status is ResultStatus.COMPLETED
    assert game.inspect().turn_actor_id == "fighter_b"
    assert "stand" in game.options().available_actions
    stood = game.execute(Stand())
    if stood.status is ResultStatus.PAUSED:
        choice = stood.inspection.choice
        assert choice is not None and "decline" in {option.option_id for option in choice.options}
        stood = game.choose(choice.choice_id, "decline", choice.owner_actor_id)
    assert stood.status is ResultStatus.COMPLETED
    target = _actor(game, "fighter_b")
    assert not target.prone
    assert target.ac == prone_ac + 2
    assert "stand" not in game.options().available_actions


def test_rejected_trip_preserves_die_and_action_counters():
    with_rejection = _ready_pc_duel(20, 1, 12)
    direct = _ready_pc_duel(20, 1, 12)

    rejected = with_rejection.execute(Trip("no_such_target"))
    assert rejected.status is ResultStatus.REJECTED
    assert _actor(with_rejection, "fighter_a").actions_remaining == 3
    assert _actor(with_rejection, "fighter_a").strikes_this_turn == 0

    first = with_rejection.execute(Trip("fighter_b"))
    second = direct.execute(Trip("fighter_b"))
    assert first.status is ResultStatus.PAUSED and second.status is ResultStatus.PAUSED
    first_check = first.inspection.choice
    second_check = second.inspection.choice
    assert first_check is not None and second_check is not None
    assert _actor(with_rejection, "fighter_a").strikes_this_turn == 1
    assert _actor(direct, "fighter_a").strikes_this_turn == 1
    first_result = with_rejection.choose(first_check.choice_id, "keep", first_check.owner_actor_id)
    second_result = direct.choose(second_check.choice_id, "keep", second_check.owner_actor_id)
    first_event = next(event for event in first_result.events if event.kind == "trip_check")
    second_event = next(event for event in second_result.events if event.kind == "trip_check")
    assert first_event.check is not None and second_event.check is not None
    assert first_event.check.die == second_event.check.die


def test_public_skill_action_guidance_choice_round_trips_and_preserves_map(tmp_path: Path):
    game = Encounter.start(S3_SETUP, rolls=(1, 2, 20, 3, 4, 5, 10, 1, 1, 10, 3))
    while game.inspect().choice is not None:
        choice = game.inspect().choice
        assert choice is not None
        game.choose(choice.choice_id, "keep", choice.owner_actor_id)
    # The fixed mixed-party fixture starts with its warpriest. Apply Guidance
    # through the public spell command and let the fighter act later.
    if game.inspect().turn_actor_id != "cleric_c":
        while game.inspect().turn_actor_id != "cleric_c":
            assert game.execute(EndTurn()).status is ResultStatus.COMPLETED
    assert game.execute(Cast("guidance", "fighter_m")).status is ResultStatus.COMPLETED
    assert game.execute(EndTurn()).status is ResultStatus.COMPLETED
    while game.inspect().turn_actor_id != "fighter_m":
        assert game.execute(EndTurn()).status is ResultStatus.COMPLETED
    assert game.execute(Stride((Position(2, 0), Position(3, 0), Position(4, 0)))).status is ResultStatus.COMPLETED

    paused = game.execute(Trip("guard_dog_a"))
    assert paused.status is ResultStatus.PAUSED
    choice = paused.inspection.choice
    assert choice is not None and {option.option_id for option in choice.options} == {"use", "keep"}
    assert _actor(game, "fighter_m").actions_remaining == 1
    assert _actor(game, "fighter_m").strikes_this_turn == 0

    path = tmp_path / "trip-guidance-choice.json"
    game.save(path)
    game = Encounter.load(path)
    assert game.inspect() == paused.inspection
    reroll_prompt = game.choose(choice.choice_id, "use", choice.owner_actor_id)
    assert reroll_prompt.status is ResultStatus.PAUSED
    choice = reroll_prompt.inspection.choice
    assert choice is not None and {option.option_id for option in choice.options} == {"keep", "reroll"}
    # The check is rolled once after Guidance and already contributes one MAP
    # count; keeping its Hero Point choice must not count the attack again.
    assert _actor(game, "fighter_m").strikes_this_turn == 1
    kept = game.choose(choice.choice_id, "keep", choice.owner_actor_id)
    check_event = next(event for event in kept.events if event.kind == "trip_check")
    assert check_event.check is not None
    assert (check_event.check.modifier_breakdown[-1].modifier_type, check_event.check.modifier_breakdown[-1].source) == (
        "status", "Guidance",
    )
    assert _actor(game, "fighter_m").strikes_this_turn == 1


def test_s2_duel_skill_action_encounter_route_saves_then_ends_in_victory(tmp_path: Path):
    game = _ready_pc_duel(20, 1, 11, 20, 1, 20, 20, 20, 8)

    demoralize = _keep_hero_choice(game, game.execute(Demoralize("fighter_b", spoken_language="Common")))
    assert demoralize.status is ResultStatus.COMPLETED
    assert any(event.kind == "immunity_applied" for event in demoralize.events)
    trip = _keep_hero_choice(game, game.execute(Trip("fighter_b")))
    assert trip.status is ResultStatus.COMPLETED
    assert any(event.kind == "damage" and event.damage is not None and event.damage.total == 1 for event in trip.events)
    assert _actor(game, "fighter_b").prone
    grapple = _keep_hero_choice(game, game.execute(Grapple("fighter_b")))
    assert grapple.status is ResultStatus.COMPLETED
    assert game.inspect().turn_actor_id == "fighter_b"
    assert any(effect.kind == "restrained" and effect.source_actor_id == "fighter_a" for effect in _actor(game, "fighter_b").condition_effects)

    path = tmp_path / "skill-action-duel.json"
    game.save(path)
    game = Encounter.load(path)
    assert game.inspect().turn_actor_id == "fighter_b"
    assert any(effect.kind == "restrained" for effect in _actor(game, "fighter_b").condition_effects)

    escape = game.execute(Escape("grapple:fighter_a:fighter_b", "athletics"))
    assert escape.status is ResultStatus.PAUSED
    choice = escape.inspection.choice
    assert choice is not None and {option.option_id for option in choice.options} == {"keep", "reroll"}
    escape = game.choose(choice.choice_id, "keep", choice.owner_actor_id)
    assert escape.status is ResultStatus.PAUSED
    escape_check = next(event.check for event in escape.events if event.kind == "escape_check")
    assert escape_check is not None and escape_check.degree is DegreeOfSuccess.CRITICAL_SUCCESS
    choice = escape.inspection.choice
    assert choice is not None and "stay" in {option.option_id for option in choice.options}
    assert game.choose(choice.choice_id, "stay", choice.owner_actor_id).status is ResultStatus.COMPLETED
    assert not any(effect.kind in {"grabbed", "restrained"} for effect in _actor(game, "fighter_b").condition_effects)

    stand = game.execute(Stand())
    if stand.status is ResultStatus.PAUSED:
        choice = stand.inspection.choice
        assert choice is not None and "decline" in {option.option_id for option in choice.options}
        stand = game.choose(choice.choice_id, "decline", choice.owner_actor_id)
    assert stand.status is ResultStatus.COMPLETED
    assert not _actor(game, "fighter_b").prone
    assert game.execute(EndTurn()).status is ResultStatus.COMPLETED
    assert game.inspect().turn_actor_id == "fighter_a"

    strike = _keep_hero_choice(game, game.execute(Strike("fighter_b", attack_id="longsword")))
    assert strike.status is ResultStatus.PAUSED
    choice = strike.inspection.choice
    assert choice is not None and "normal" in {option.option_id for option in choice.options}
    final = game.choose(choice.choice_id, "normal", choice.owner_actor_id)
    assert final.status is ResultStatus.COMPLETED
    assert not game.inspect().in_progress
    assert game.inspect().winner_team == "blue"
    assert _actor(game, "fighter_b").hp == 0
    assert _actor(game, "fighter_b").unconscious
