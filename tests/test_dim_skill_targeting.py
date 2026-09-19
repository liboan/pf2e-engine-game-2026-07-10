"""Focused shared concealment targeting checks for connected skill actions."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from types import MappingProxyType

import pytest

import pf2e.content as content
from pf2e import Encounter, ResultStatus
from pf2e.content import DIM_TARGETING_SETUP
from pf2e.model import ActiveSpellEffect
from pf2e.rogue_content import ROGUE_SCOUNDREL
from pf2e.skill_actions import Demoralize, Feint, Grapple, Trip


def _ready(game: Encounter) -> None:
    while (choice := game.inspect().choice) is not None:
        assert choice.kind == "initiative_hero_reroll"
        game.choose(choice.choice_id, "keep", choice.owner_actor_id)


def _actor(game: Encounter, actor_id: str):
    return next(actor for actor in game.inspect().actors if actor.actor_id == actor_id)


def test_dim_trip_target_failure_and_success_round_trip_saved_target_choice(
    tmp_path: Path,
) -> None:
    failed = Encounter.start(DIM_TARGETING_SETUP, rolls=(20, 1, 4))
    _ready(failed)
    started = failed.execute(Trip("guard_dog_a"))
    assert started.status is ResultStatus.PAUSED
    choice = started.inspection.choice
    assert choice is not None and choice.kind == "concealment_hero_reroll"
    assert _actor(failed, "fighter_a").strikes_this_turn == 1

    path = tmp_path / "dim-trip-target-failure.json"
    failed.save(path)
    restored = Encounter.load(path)
    assert restored.inspect() == started.inspection
    result = restored.choose(choice.choice_id, "keep", choice.owner_actor_id)
    assert result.status is ResultStatus.COMPLETED
    assert [event.kind for event in result.events] == [
        "concealment_kept",
        "concealment_failed",
    ]
    assert not any(event.kind == "trip_check" for event in result.events)
    assert not _actor(restored, "guard_dog_a").prone
    assert (_actor(restored, "fighter_a").actions_remaining,
            _actor(restored, "fighter_a").strikes_this_turn) == (2, 1)

    passed = Encounter.start(DIM_TARGETING_SETUP, rolls=(20, 1, 5, 20, 6))
    _ready(passed)
    targeting = passed.execute(Trip("guard_dog_a"))
    target_choice = targeting.inspection.choice
    assert target_choice is not None and target_choice.kind == "concealment_hero_reroll"
    after_target = passed.choose(target_choice.choice_id, "keep", target_choice.owner_actor_id)
    assert after_target.inspection.choice is not None
    assert after_target.inspection.choice.kind == "family_action"
    skill_choice = after_target.inspection.choice
    result = passed.choose(skill_choice.choice_id, "keep", skill_choice.owner_actor_id)
    assert result.status is ResultStatus.COMPLETED
    check_event = next(event for event in result.events if event.kind == "trip_check")
    assert check_event.check is not None
    assert check_event.check.attack_count == 1
    assert _actor(passed, "guard_dog_a").prone


def test_dim_trip_commits_map_once_after_a_prior_attack() -> None:
    game = Encounter.start(DIM_TARGETING_SETUP, rolls=(20, 1, 5, 20, 6))
    _ready(game)
    game._state.creatures["fighter_a"].strikes_this_turn = 1

    targeting = game.execute(Trip("guard_dog_a"))
    target_choice = targeting.inspection.choice
    assert target_choice is not None and target_choice.kind == "concealment_hero_reroll"
    after_target = game.choose(target_choice.choice_id, "keep", target_choice.owner_actor_id)
    skill_choice = after_target.inspection.choice
    assert skill_choice is not None and skill_choice.kind == "family_action"
    result = game.choose(skill_choice.choice_id, "keep", skill_choice.owner_actor_id)
    check_event = next(event for event in result.events if event.kind == "trip_check")
    assert check_event.check is not None
    assert (check_event.check.attack_count, check_event.check.map_penalty) == (2, -5)
    assert _actor(game, "fighter_a").strikes_this_turn == 2


def test_dim_trip_target_hero_reroll_is_saved_separately_from_skill_check(
    tmp_path: Path,
) -> None:
    game = Encounter.start(DIM_TARGETING_SETUP, rolls=(20, 1, 4, 5, 10))
    _ready(game)
    started = game.execute(Trip("guard_dog_a"))
    choice = started.inspection.choice
    assert choice is not None and choice.kind == "concealment_hero_reroll"
    path = tmp_path / "dim-trip-target-reroll.json"
    game.save(path)
    restored = Encounter.load(path)

    after_target = restored.choose(choice.choice_id, "spend_hero_point", choice.owner_actor_id)
    assert after_target.status is ResultStatus.COMPLETED
    assert [event.kind for event in after_target.events[:3]] == [
        "hero_reroll",
        "concealment_passed",
        "trip_check",
    ]
    assert _actor(restored, "fighter_a").hero_points == 0


def test_dim_assurance_trip_still_rolls_target_flat_check_only() -> None:
    game = Encounter.start(DIM_TARGETING_SETUP, rolls=(20, 1, 4))
    _ready(game)
    started = game.execute(Trip("guard_dog_a", use_assurance=True))
    choice = started.inspection.choice
    assert choice is not None and choice.kind == "concealment_hero_reroll"
    pending = game._state.pending_choice
    assert pending is not None and pending.saved_check is not None
    assert pending.saved_check.result is not None
    assert pending.saved_check.result.method == "assurance"
    result = game.choose(choice.choice_id, "keep", choice.owner_actor_id)
    assert result.status is ResultStatus.COMPLETED
    assert not any(event.kind == "trip_check" for event in result.events)
    assert not _actor(game, "guard_dog_a").prone
    assert (_actor(game, "fighter_a").actions_remaining,
            _actor(game, "fighter_a").strikes_this_turn) == (2, 1)


def test_dim_target_failure_leaves_guidance_unspent() -> None:
    game = Encounter.start(DIM_TARGETING_SETUP, rolls=(20, 1, 4))
    _ready(game)
    guidance = ActiveSpellEffect(
        effect_id="guidance:fixture:fighter_a",
        kind="guidance",
        source_actor_id="fighter_a",
        target_actor_id="fighter_a",
        value=1,
        expires_at_source_start=1,
        expires_at_world_time=600,
    )
    game._state.active_effects.append(guidance)

    started = game.execute(Trip("guard_dog_a"))
    choice = started.inspection.choice
    assert choice is not None and choice.kind == "concealment_hero_reroll"
    result = game.choose(choice.choice_id, "keep", choice.owner_actor_id)
    assert result.status is ResultStatus.COMPLETED
    assert guidance in game._state.active_effects
    assert "fighter_a" not in game._state.guidance_immunity_deadlines
    assert not any(event.kind == "guidance_used" for event in result.events)


def test_dim_failed_grapple_preserves_existing_hold_and_makes_no_athletics_check() -> None:
    game = Encounter.start(DIM_TARGETING_SETUP, rolls=(20, 1, 5, 20, 4))
    _ready(game)
    first = game.execute(Grapple("guard_dog_a"))
    first_choice = first.inspection.choice
    assert first_choice is not None and first_choice.kind == "concealment_hero_reroll"
    first = game.choose(first_choice.choice_id, "keep", first_choice.owner_actor_id)
    skill_choice = first.inspection.choice
    assert skill_choice is not None and skill_choice.kind == "family_action"
    first = game.choose(skill_choice.choice_id, "keep", skill_choice.owner_actor_id)
    assert any(event.kind == "grapple_check" for event in first.events)
    assert any(effect.kind in {"grabbed", "restrained"} for effect in game._state.condition_effects)

    second = game.execute(Grapple("guard_dog_a"))
    second_choice = second.inspection.choice
    assert second_choice is not None and second_choice.kind == "concealment_hero_reroll"
    assert second_choice.details == ("Original flat check: d20 4 vs DC 5.",)
    result = game.choose(second_choice.choice_id, "keep", second_choice.owner_actor_id)
    assert result.status is ResultStatus.COMPLETED
    assert not any(event.kind == "grapple_check" for event in result.events)
    assert not any(event.kind == "condition_removed" for event in result.events)
    assert any(effect.kind in {"grabbed", "restrained"} for effect in game._state.condition_effects)


def test_dim_failed_demoralize_applies_attempt_immunity_without_frightened() -> None:
    game = Encounter.start(DIM_TARGETING_SETUP, rolls=(20, 1, 4))
    _ready(game)
    started = game.execute(Demoralize("guard_dog_a", spoken_language="Common"))
    choice = started.inspection.choice
    assert choice is not None and choice.kind == "concealment_hero_reroll"
    result = game.choose(choice.choice_id, "keep", choice.owner_actor_id)
    assert result.status is ResultStatus.COMPLETED
    assert any(event.kind == "immunity_applied" for event in result.events)
    assert not any(event.kind == "demoralize_check" for event in result.events)
    assert not any(effect.kind == "frightened" for effect in game._state.condition_effects)
    repeated = game.execute(Demoralize("guard_dog_a", spoken_language="Common"))
    assert repeated.status is ResultStatus.REJECTED
    assert "temporarily immune" in repeated.message


def test_dim_failed_scoundrel_feint_preserves_free_step_without_deception_die(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    rogue = replace(
        ROGUE_SCOUNDREL,
        definition_id="dim_scoundrel_targeting",
        name="Dim Scoundrel Targeting",
        vision="ordinary",
    )
    setup = replace(
        DIM_TARGETING_SETUP,
        setup_id="dim_scoundrel_targeting_setup",
        placements=(
            replace(DIM_TARGETING_SETUP.placements[0], definition_id=rogue.definition_id),
            DIM_TARGETING_SETUP.placements[1],
        ),
    )
    monkeypatch.setattr(
        content,
        "_STAGED_CREATURES",
        MappingProxyType({**content._STAGED_CREATURES, rogue.definition_id: rogue}),
    )
    monkeypatch.setattr(
        content,
        "_STAGED_SETUPS",
        MappingProxyType({**content._STAGED_SETUPS, setup.setup_id: setup}),
    )
    game = Encounter.start(setup, rolls=(20, 1, 4))
    _ready(game)
    started = game.execute(Feint("guard_dog_a"))
    target_choice = started.inspection.choice
    assert target_choice is not None and target_choice.kind == "concealment_hero_reroll"
    stepped = game.choose(target_choice.choice_id, "keep", target_choice.owner_actor_id)
    step_choice = stepped.inspection.choice
    assert step_choice is not None and step_choice.kind == "family_action"
    assert "free step" in step_choice.prompt.casefold()

    path = tmp_path / "dim-scoundrel-step.json"
    game.save(path)
    restored = Encounter.load(path)
    result = restored.choose(step_choice.choice_id, "stay", step_choice.owner_actor_id)
    assert result.status is ResultStatus.COMPLETED
    step_event = next(event for event in result.events if event.kind == "scoundrel_step")
    assert step_event.check is None
    assert "failed concealment targeting" in step_event.text
    assert not any(
        event.kind == "feint_check" or event.check is not None and event.check.method == "d20"
        for event in result.events
    )
