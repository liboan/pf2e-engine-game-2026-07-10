"""Public Counter Performance play through the admitted Witch Command trigger.

Sources: https://2e.aonprd.com/Spells.aspx?ID=1762 and
https://2e.aonprd.com/Spells.aspx?ID=1470 .  This bounded fixture uses the
user-approved convention: replace the save's numeric total but preserve the
beneficiary's natural die adjustment, and choose one fortune route per save.
"""

import json

import pytest

import pf2e.content as content
from pf2e.checks import combine_modifiers
from pf2e.encounter import Encounter
from pf2e.model import (
    Cast,
    Choose,
    CreaturePlacement,
    EncounterSetup,
    EndTurn,
    LingeringComposition,
    Position,
    ResultStatus,
    Strike,
)
from pf2e.persistence import save_encounter
from pf2e.spells import SPELLS
from pf2e.terminal import render_pending_choice


def _counter_game(monkeypatch, *, rolls=(20, 1, 1, 1, 15)):
    setup = content.get_setup("maestro_bard_counter_performance_command")
    assert setup.setup_id in content.SETUPS
    assert all(item.definition_id in content.CREATURES for item in setup.placements)
    game = Encounter.start(setup, rolls=rolls)
    while game.inspect().choice is not None:
        choice = game.inspect().choice
        assert choice is not None
        assert game.execute(Choose(choice.choice_id, "keep", choice.owner_actor_id)).status in {ResultStatus.PAUSED, ResultStatus.COMPLETED}
    assert game.inspect().turn_actor_id == "enemy_witch"
    return game


def test_command_counter_offer_round_trips_and_preserves_beneficiary_natural_one(monkeypatch, tmp_path):
    game = _counter_game(monkeypatch)
    game._state.creatures["maestro_bard"].hero_points = 0

    paused = game.execute(Cast("command", "beneficiary", spell_mode="stand"))
    assert paused.status is ResultStatus.PAUSED
    choice = game.inspect().choice
    assert choice is not None
    assert choice.kind == "counter_performance_save_choice"
    assert choice.owner_actor_id == "beneficiary"
    assert {item.option_id for item in choice.options} == {"counter_performance", "spend_hero_point", "keep"}
    assert not game._state.condition_effects

    path = tmp_path / "counter-pending.json"
    save_encounter(path, game._state, game._dice)
    game = Encounter.load(path)
    choice = game.inspect().choice
    assert choice is not None and choice.kind == "counter_performance_save_choice"
    resolved = game.execute(Choose(choice.choice_id, "counter_performance", "beneficiary"))
    assert resolved.status is ResultStatus.COMPLETED
    performance = next(event.check for event in resolved.events if event.kind == "counter_performance_result")
    command = next(event.check for event in resolved.events if event.kind == "command_save")
    assert performance is not None and (performance.die, performance.total) == (15, 22)
    # A 22 total would normally succeed at DC 17, but the beneficiary rolled a
    # natural 1 and keeps that degree adjustment under the approved convention.
    assert command is not None and command.die == 1 and command.total == 22 and command.degree.name == "FAILURE"
    assert combine_modifiers(command.modifier_breakdown) == command.modifier
    assert command.modifier_breakdown[0].source == "Counter Performance substituted total"
    assert len([effect for effect in game._state.condition_effects if effect.kind == "commanded"]) == 1
    bard = game._state.creatures["maestro_bard"]
    assert (bard.reaction_available, bard.focus_points) == (False, 1)


def test_beneficiary_and_bard_hero_points_are_separate_and_second_result_is_retained(monkeypatch):
    # Initiatives; beneficiary's save; Performance; Bard's reroll.
    game = _counter_game(monkeypatch, rolls=(20, 1, 1, 16, 4, 1))
    game._state.creatures["beneficiary"].hero_points = 1
    game._state.creatures["maestro_bard"].hero_points = 1
    assert game.execute(Cast("command", "beneficiary", spell_mode="stand")).status is ResultStatus.PAUSED
    choice = game.inspect().choice
    assert choice is not None
    assert game.execute(Choose(choice.choice_id, "counter_performance", "beneficiary")).status is ResultStatus.PAUSED
    bard_choice = game.inspect().choice
    assert bard_choice is not None and bard_choice.kind == "counter_performance_bard_hero_reroll"
    assert bard_choice.owner_actor_id == "maestro_bard"
    resolved = game.execute(Choose(bard_choice.choice_id, "spend_hero_point", "maestro_bard"))
    performance = next(event.check for event in resolved.events if event.kind == "counter_performance_result")
    assert performance is not None and (performance.die, performance.total) == (1, 8)
    assert game._state.creatures["beneficiary"].hero_points == 1
    assert game._state.creatures["maestro_bard"].hero_points == 0


def test_counter_uses_the_better_original_natural_twenty_save(monkeypatch):
    # Initiatives; beneficiary natural 20 save; low Performance total.
    game = _counter_game(monkeypatch, rolls=(20, 1, 1, 20, 4))
    game._state.creatures["maestro_bard"].hero_points = 0
    assert game.execute(Cast("command", "beneficiary", spell_mode="stand")).status is ResultStatus.PAUSED
    choice = game.inspect().choice
    assert choice is not None
    result = game.execute(Choose(choice.choice_id, "counter_performance", "beneficiary"))
    command = next(event.check for event in result.events if event.kind == "command_save")
    assert command is not None and (command.die, command.total, command.degree.name) == (20, 25, "CRITICAL_SUCCESS")
    assert not any(effect.kind == "commanded" for effect in game._state.condition_effects)


def test_exhausted_reaction_or_focus_or_range_does_not_offer_counter(monkeypatch):
    for mutate in (
        lambda game: setattr(game._state.creatures["maestro_bard"], "reaction_available", False),
        lambda game: setattr(game._state.creatures["maestro_bard"], "focus_points", 0),
        lambda game: (
            setattr(game._state.creatures["beneficiary"], "position", Position(0, 1)),
            setattr(game._state.creatures["maestro_bard"], "position", Position(14, 1)),
        ),
    ):
        game = _counter_game(monkeypatch)
        game._state.creatures["beneficiary"].hero_points = 0
        mutate(game)
        result = game.execute(Cast("command", "beneficiary", spell_mode="stand"))
        assert result.status is ResultStatus.COMPLETED
        assert game.inspect().choice is None


def test_counter_replaces_anthem_and_rejected_saved_choice_is_atomic(monkeypatch):
    game = _counter_game(monkeypatch)
    game._state.creatures["maestro_bard"].hero_points = 0
    # Pass the first Witch turn, then demonstrate the ordinary public Anthem
    # before the next auditory Command trigger.
    assert game.execute(EndTurn()).status is ResultStatus.COMPLETED
    assert game.inspect().turn_actor_id == "maestro_bard"
    assert game.execute(Cast("courageous_anthem")).status is ResultStatus.COMPLETED
    assert any(effect.kind == "courageous_anthem" for effect in game._state.active_effects)
    assert game.execute(EndTurn()).status is ResultStatus.COMPLETED
    assert game.execute(EndTurn()).status is ResultStatus.COMPLETED
    assert game.inspect().turn_actor_id == "enemy_witch"

    paused = game.execute(Cast("command", "beneficiary", spell_mode="stand"))
    assert paused.status is ResultStatus.PAUSED
    choice = game.inspect().choice
    assert choice is not None
    # A stale resource makes an offered response reject without consuming the
    # original save, its die, or its saved choice.
    game._state.creatures["maestro_bard"].focus_points = 0
    rejected = game.execute(Choose(choice.choice_id, "counter_performance", "beneficiary"))
    assert rejected.status is ResultStatus.REJECTED
    assert game.inspect().choice is not None and game.inspect().choice.choice_id == choice.choice_id
    assert any(effect.kind == "courageous_anthem" for effect in game._state.active_effects)

    game._state.creatures["maestro_bard"].focus_points = 1
    resolved = game.execute(Choose(choice.choice_id, "counter_performance", "beneficiary"))
    assert resolved.status is ResultStatus.COMPLETED
    assert not any(effect.kind == "courageous_anthem" for effect in game._state.active_effects)


def test_counter_terminal_choice_and_nontriggering_fear_rejection(monkeypatch):
    game = _counter_game(monkeypatch)
    assert game.execute(Cast("command", "beneficiary", spell_mode="stand")).status is ResultStatus.PAUSED
    choice = game.inspect().choice
    assert choice is not None
    rendered = render_pending_choice(choice, game.inspect())
    assert "Counter Performance" in rendered
    assert "Spend 1 Hero Point" in rendered
    # It is a saved reaction, not a freely selectable spell; Fear's lack of
    # auditory/visual traits cannot manufacture this trigger.
    assert "auditory" not in SPELLS["fear"].traits and "visual" not in SPELLS["fear"].traits
    assert game.execute(Choose(choice.choice_id, "keep", "beneficiary")).status is ResultStatus.COMPLETED
    assert game.execute(EndTurn()).status is ResultStatus.COMPLETED
    assert game.inspect().turn_actor_id == "maestro_bard"
    rejected = game.execute(Cast("counter_performance"))
    assert rejected.status is ResultStatus.REJECTED


def test_counter_can_protect_the_bard_themself(monkeypatch):
    game = _counter_game(monkeypatch)
    bard = game._state.creatures["maestro_bard"]
    bard.hero_points = 0
    assert game.execute(Cast("command", "maestro_bard", spell_mode="stand")).status is ResultStatus.PAUSED
    choice = game.inspect().choice
    assert choice is not None and choice.owner_actor_id == "maestro_bard"
    result = game.execute(Choose(choice.choice_id, "counter_performance", "maestro_bard"))
    assert result.status is ResultStatus.COMPLETED
    assert any(event.kind == "counter_performance_result" for event in result.events)
    bard = game._state.creatures["maestro_bard"]
    assert bard.reaction_available is False and bard.focus_points == 1


def test_counter_saved_choices_reject_forged_command_and_bard_provenance(monkeypatch, tmp_path):
    game = _counter_game(monkeypatch)
    game._state.creatures["maestro_bard"].hero_points = 0
    assert game.execute(Cast("command", "beneficiary", spell_mode="stand")).status is ResultStatus.PAUSED
    command_path = tmp_path / "forged-command.json"
    game.save(command_path)
    payload = json.loads(command_path.read_text())
    payload["state"]["pending_choice"]["check"]["modifier"] = 4
    payload["state"]["pending_choice"]["check"]["total"] = 5
    payload["state"]["pending_choice"]["check"]["modifier_breakdown"][0][0] = 4
    command_path.write_text(json.dumps(payload))
    with pytest.raises(ValueError, match="Command save provenance"):
        Encounter.load(command_path)

    game = _counter_game(monkeypatch)
    game._state.creatures["maestro_bard"].hero_points = 1
    assert game.execute(Cast("command", "beneficiary", spell_mode="stand")).status is ResultStatus.PAUSED
    choice = game.inspect().choice
    assert choice is not None
    assert game.execute(Choose(choice.choice_id, "counter_performance", "beneficiary")).status is ResultStatus.PAUSED
    hero_path = tmp_path / "forged-counter-hero.json"
    game.save(hero_path)
    payload = json.loads(hero_path.read_text())
    payload["state"]["creatures"]["maestro_bard"]["reaction_available"] = True
    hero_path.write_text(json.dumps(payload))
    with pytest.raises(ValueError, match="Counter Performance Hero choice"):
        Encounter.load(hero_path)

    game.save(hero_path)
    payload = json.loads(hero_path.read_text())
    payload["state"]["pending_choice"]["check"]["dc"] += 1
    hero_path.write_text(json.dumps(payload))
    with pytest.raises(ValueError, match="Counter Performance Hero choice"):
        Encounter.load(hero_path)


def test_counter_performance_declares_the_printed_mental_trait():
    assert "mental" in SPELLS["counter_performance"].traits


def test_bard_recovery_carries_identity_but_rebases_composition_turn_markers(monkeypatch, tmp_path):
    """A spent focus pool recovers across scenes without carrying turn state."""
    first = content.get_setup("staged_maestro_bard_courageous_anthem_vs_guard_dog")
    next_setup = EncounterSetup(
        setup_id="review_bard_recovery_next_scene",
        name="Bard recovery next scene",
        width=15,
        height=3,
        placements=(
            CreaturePlacement("maestro_bard", "bard_maestro_level_1_staged", "Maestro Bard", "blue", Position(1, 1)),
            CreaturePlacement("bard_ally", "fighter_m_level_1", "Bard's Ally", "blue", Position(2, 1)),
            CreaturePlacement("next_bard_dog", "guard_dog_mc2924", "Next Guard Dog", "red", Position(3, 1)),
        ),
    )
    monkeypatch.setattr(content, "_STAGED_SETUPS", content._STAGED_SETUPS | {next_setup.setup_id: next_setup})
    game = Encounter.start(first, rolls=(20, 1, 1, 20, 20, 6, 20, 20, 20))
    while game.inspect().choice is not None:
        choice = game.inspect().choice
        assert choice is not None
        assert game.execute(Choose(choice.choice_id, "keep", choice.owner_actor_id)).status in {ResultStatus.PAUSED, ResultStatus.COMPLETED}
    assert game.inspect().turn_actor_id == "maestro_bard"
    game._state.creatures["bard_dog"].hp = 1
    game._state.creatures["bard_dog"].position = Position(1, 2)
    assert game.execute(LingeringComposition()).status is ResultStatus.COMPLETED
    anthem = game.execute(Cast("courageous_anthem"))
    while anthem.status is ResultStatus.PAUSED:
        choice = game.inspect().choice
        assert choice is not None
        anthem = game.execute(Choose(choice.choice_id, "keep", choice.owner_actor_id))
    assert anthem.status is ResultStatus.COMPLETED
    assert game._state.creatures["maestro_bard"].focus_points == 1
    victory = game.execute(Strike("bard_dog", attack_id="rapier"))
    while victory.status is ResultStatus.PAUSED:
        choice = game.inspect().choice
        assert choice is not None
        victory = game.execute(Choose(choice.choice_id, "keep", choice.owner_actor_id))
    assert victory.status is ResultStatus.COMPLETED
    assert not game.inspect().in_progress and game.inspect().winner_team == "blue"

    assert game.refocus("maestro_bard").status is ResultStatus.COMPLETED
    assert game._state.creatures["maestro_bard"].focus_points == 2
    assert game.record_rested(("maestro_bard",), day_number=2, elapsed_seconds=1).status is ResultStatus.COMPLETED
    assert game.daily_prepare(("maestro_bard",)).status is ResultStatus.COMPLETED
    saved = tmp_path / "bard-recovery.json"
    game.save(saved)
    game = Encounter.load(saved)
    assert game.next_encounter(next_setup).status in {ResultStatus.PAUSED, ResultStatus.COMPLETED}
    while game.inspect().choice is not None:
        choice = game.inspect().choice
        assert choice is not None
        assert game.execute(Choose(choice.choice_id, "keep", choice.owner_actor_id)).status in {ResultStatus.PAUSED, ResultStatus.COMPLETED}
    bard = game._state.creatures["maestro_bard"]
    assert bard.definition_id == "bard_maestro_level_1_staged"
    assert (bard.composition_cast_at_start, bard.composition_cast_turn_actor_id, bard.composition_cast_turn_start) == (0, None, 0)
    while game.inspect().turn_actor_id != "maestro_bard":
        assert game.execute(EndTurn()).status is ResultStatus.COMPLETED
    assert game.execute(Cast("courageous_anthem")).status is ResultStatus.COMPLETED
