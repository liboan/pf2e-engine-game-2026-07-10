"""Public Battle Medicine and Forensic Medicine healing checks."""

from dataclasses import replace
from pathlib import Path
import re

import pytest

import pf2e.content as content
from pf2e.encounter import Encounter
from pf2e.investigator import (
    BATTLE_MEDICINE_ABILITY,
    FORENSIC_ACUMEN_ABILITY,
    BattleMedicine,
)
from pf2e.model import (
    CreaturePlacement,
    EncounterSetup,
    EndTurn,
    Position,
    ResultStatus,
    Strike,
    Stride,
)
from pf2e.investigator_content import (
    FORENSIC_INVESTIGATOR,
    FORENSIC_INVESTIGATOR_HEALING_SETUP,
)
from pf2e.terminal import run_terminal
from terminal_test_helpers import BoundedInput, BoundedTranscript


def _setup() -> EncounterSetup:
    return FORENSIC_INVESTIGATOR_HEALING_SETUP


def _game(monkeypatch: pytest.MonkeyPatch, *rolls: int) -> Encounter:
    setup = _setup()
    monkeypatch.setattr(
        content,
        "_STAGED_SETUPS",
        content._STAGED_SETUPS | {setup.setup_id: setup},
    )
    game = Encounter.start(setup, rolls=rolls)
    for _ in range(8):
        choice = game.inspect().choice
        if choice is None:
            break
        option_id = (
            "keep"
            if any(option.option_id == "keep" for option in choice.options)
            else choice.options[0].option_id
        )
        result = game.choose(choice.choice_id, option_id, choice.owner_actor_id)
        assert result.status in {ResultStatus.COMPLETED, ResultStatus.PAUSED}
    assert game.inspect().turn_actor_id == "forensic_investigator"
    game._state.creatures["healing_ally"].hp = 10
    return game


def _keep_choice(game: Encounter):
    choice = game.inspect().choice
    assert choice is not None
    result = game.choose(choice.choice_id, "keep", choice.owner_actor_id)
    assert result.status is ResultStatus.COMPLETED
    return result


def test_forensic_healing_public_save_load_adds_level_and_preserves_wounded(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    game = _game(monkeypatch, 20, 1, 2, 12, 3, 4)
    target = game._state.creatures["healing_ally"]
    target.wounded = 1
    assert BATTLE_MEDICINE_ABILITY in FORENSIC_INVESTIGATOR.abilities
    assert FORENSIC_ACUMEN_ABILITY in FORENSIC_INVESTIGATOR.abilities
    assert game.options().battle_medicine_targets == ("healing_ally",)

    started = game.execute(BattleMedicine("healing_ally"))
    assert started.status is ResultStatus.PAUSED
    assert started.inspection.choice is not None
    path = tmp_path / "investigator-battle-medicine.json"
    game.save(path)
    game = Encounter.load(path)
    resolved = _keep_choice(game)
    check_event = next(event for event in resolved.events if event.kind == "battle_medicine_check")
    assert check_event.check is not None
    assert (check_event.check.die, check_event.check.modifier, check_event.check.total) == (12, 4, 16)
    healing_event = next(event for event in resolved.events if event.kind == "battle_medicine")
    assert "2d8 3, 4 + 1 Forensic Medicine" in healing_event.text

    healed_path = tmp_path / "investigator-battle-medicine-healed.json"
    game.save(healed_path)
    game = Encounter.load(healed_path)

    target = game._state.creatures["healing_ally"]
    assert target.hp == 18
    assert target.wounded == 1
    assert target.actions_remaining == 0
    immunity = game._state.condition_immunities
    assert len(immunity) == 1
    assert (immunity[0].kind, immunity[0].source_actor_id, immunity[0].target_actor_id) == (
        "battle_medicine",
        "forensic_investigator",
        "healing_ally",
    )
    assert immunity[0].expires_at_seconds == 3600


def test_forensic_immunity_survives_next_encounter_and_save_load(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    game = _game(monkeypatch, 20, 1, 2, 12, 3, 4, 20, 1, 2)
    assert game.execute(BattleMedicine("healing_ally")).status is ResultStatus.PAUSED
    _keep_choice(game)

    # The carry API requires a finished scene. The healed party state is the
    # subject under test; the defeated opponent is fixture bookkeeping.
    game._state.creatures["healing_dog"].hp = 0
    game._state.in_progress = False
    game._state.winner_team = "blue"
    base = _setup()
    next_setup = replace(
        base,
        setup_id="investigator_forensic_healing_next_scene",
        name="Forensic Investigator Battle Medicine next scene",
        placements=tuple(
            placement if placement.actor_id != "healing_dog" else replace(
                placement, actor_id="fresh_healing_dog"
            )
            for placement in base.placements
        ),
    )
    monkeypatch.setattr(
        content,
        "_STAGED_SETUPS",
        content._STAGED_SETUPS | {next_setup.setup_id: next_setup},
    )
    transitioned = game.next_encounter(next_setup)
    assert transitioned.status is ResultStatus.PAUSED
    assert transitioned.inspection.choice is not None
    immunity = game._state.condition_immunities
    assert len(immunity) == 1
    assert immunity[0].expires_at_seconds == 3600
    assert game._state.world_time_seconds == 0

    path = tmp_path / "investigator-battle-medicine-next-scene.json"
    game.save(path)
    restored = Encounter.load(path)
    restored_immunity = restored._state.condition_immunities
    assert len(restored_immunity) == 1
    assert (
        restored_immunity[0].source_actor_id,
        restored_immunity[0].target_actor_id,
        restored_immunity[0].expires_at_seconds,
    ) == ("forensic_investigator", "healing_ally", 3600)


def test_healthy_encounter_enemy_injury_battle_medicine_and_public_victory(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """A healthy staged party sustains real enemy damage, heals, and wins publicly."""
    setup = _setup()
    monkeypatch.setattr(
        content,
        "_STAGED_SETUPS",
        content._STAGED_SETUPS | {setup.setup_id: setup},
    )
    # Investigator, ally, and dog initiative; dog jaws attack and damage;
    # Battle Medicine check and healing; Investigator and ally finishing Strikes.
    game = Encounter.start(setup, rolls=(1, 2, 20, 12, 4, 12, 3, 4, 10, 4, 10, 4))
    assert all(actor.hp == actor.max_hp for actor in game.inspect().actors)
    while (choice := game.inspect().choice) is not None:
        assert choice.kind == "initiative_hero_reroll"
        kept = game.choose(choice.choice_id, "keep", choice.owner_actor_id)
        assert kept.status in {ResultStatus.PAUSED, ResultStatus.COMPLETED}
    assert game.inspect().turn_actor_id == "healing_dog"

    assert game.execute(Stride((Position(3, 2),))).status is ResultStatus.COMPLETED
    injury = game.execute(Strike("healing_ally", attack_id="jaws"))
    assert injury.status is ResultStatus.COMPLETED
    assert any(event.kind == "damage" for event in injury.events)
    injured_ally = game._state.creatures["healing_ally"]
    ally_view = next(actor for actor in game.inspect().actors if actor.actor_id == "healing_ally")
    assert injured_ally.hp == 16 and injured_ally.hp < ally_view.max_hp

    assert game.execute(EndTurn()).status is ResultStatus.COMPLETED
    assert game.inspect().turn_actor_id == "healing_ally"
    assert game.execute(EndTurn()).status is ResultStatus.COMPLETED
    assert game.inspect().turn_actor_id == "forensic_investigator"
    started = game.execute(BattleMedicine("healing_ally"))
    assert started.status is ResultStatus.PAUSED
    assert started.inspection.choice is not None
    path = tmp_path / "investigator-healthy-fight-battle-medicine.json"
    game.save(path)
    game = Encounter.load(path)
    healed = _keep_choice(game)
    assert game._state.creatures["healing_ally"].hp == 21
    assert any(event.kind == "battle_medicine" for event in healed.events)

    assert game.execute(Stride((Position(2, 2),))).status is ResultStatus.COMPLETED
    investigator_strike = game.execute(Strike("healing_dog", attack_id="shortsword"))
    if investigator_strike.status is ResultStatus.PAUSED:
        investigator_strike = game.choose(
            investigator_strike.inspection.choice.choice_id,
            "keep",
            investigator_strike.inspection.choice.owner_actor_id,
        )
    assert investigator_strike.status is ResultStatus.COMPLETED
    assert game._state.creatures["healing_dog"].hp == 4
    assert game.execute(EndTurn()).status is ResultStatus.COMPLETED
    assert game.inspect().turn_actor_id == "healing_ally"

    ally_strike = game.execute(Strike("healing_dog", attack_id="longsword"))
    if ally_strike.status is ResultStatus.PAUSED:
        ally_strike = game.choose(
            ally_strike.inspection.choice.choice_id,
            "keep",
            ally_strike.inspection.choice.owner_actor_id,
        )
    assert ally_strike.status is ResultStatus.COMPLETED
    assert not game.inspect().in_progress
    assert game.inspect().winner_team == "blue"
    assert game._state.creatures["healing_dog"].defeated


def test_battle_medicine_critical_success_uses_four_d8_without_wounded_removal(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    game = _game(monkeypatch, 20, 1, 2, 20, 1, 2, 3, 4)
    game._state.creatures["healing_ally"].wounded = 1
    assert game.execute(BattleMedicine("healing_ally")).status is ResultStatus.PAUSED
    _keep_choice(game)
    target = game._state.creatures["healing_ally"]
    assert target.hp == 20
    assert target.wounded == 1


def test_battle_medicine_failure_still_applies_forensic_immunity(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    game = _game(monkeypatch, 20, 1, 2, 5)
    before_hp = game._state.creatures["healing_ally"].hp
    result = game.execute(BattleMedicine("healing_ally"))
    assert result.status is ResultStatus.PAUSED
    _keep_choice(game)
    assert game._state.creatures["healing_ally"].hp == before_hp
    assert game._state.condition_immunities[0].expires_at_seconds == 3600

    game._state.creatures["healing_ally"].hp = 10
    actions = game._state.creatures["forensic_investigator"].actions_remaining
    repeated = game.execute(BattleMedicine("healing_ally"))
    assert repeated.status is ResultStatus.REJECTED
    assert game._state.creatures["forensic_investigator"].actions_remaining == actions


def test_forensic_immunity_is_scoped_to_medic_and_recipient(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    base = _setup()
    setup = replace(
        base,
        setup_id="investigator_forensic_healing_two_allies",
        name="Forensic Investigator Battle Medicine two allies",
        placements=base.placements + (
            CreaturePlacement(
                "second_ally",
                content.MELEE_FIGHTER_M.definition_id,
                "Second Ally",
                "blue",
                Position(1, 2),
            ),
        ),
    )
    monkeypatch.setattr(
        content,
        "_STAGED_SETUPS",
        content._STAGED_SETUPS | {setup.setup_id: setup},
    )
    # Four initiative faces, then two Medicine checks and their healing dice.
    game = Encounter.start(setup, rolls=(20, 1, 2, 3, 12, 3, 4, 12, 1, 2))
    for _ in range(4):
        choice = game.inspect().choice
        if choice is None:
            break
        assert choice.kind == "initiative_hero_reroll"
        assert game.choose(choice.choice_id, "keep", choice.owner_actor_id).status in {
            ResultStatus.PAUSED,
            ResultStatus.COMPLETED,
        }
    assert game.inspect().turn_actor_id == "forensic_investigator"
    game._state.creatures["healing_ally"].hp = 10
    game._state.creatures["second_ally"].hp = 10
    assert game.options().battle_medicine_targets == ("healing_ally", "second_ally")

    assert game.execute(BattleMedicine("healing_ally")).status is ResultStatus.PAUSED
    _keep_choice(game)
    assert game.execute(BattleMedicine("second_ally")).status is ResultStatus.PAUSED
    _keep_choice(game)

    assert game._state.creatures["healing_ally"].hp == 18
    assert game._state.creatures["second_ally"].hp == 14
    assert {
        (immunity.source_actor_id, immunity.target_actor_id)
        for immunity in game._state.condition_immunities
    } == {
        ("forensic_investigator", "healing_ally"),
        ("forensic_investigator", "second_ally"),
    }
    actions = game._state.creatures["forensic_investigator"].actions_remaining
    repeated = game.execute(BattleMedicine("healing_ally"))
    assert repeated.status is ResultStatus.REJECTED
    assert game._state.creatures["forensic_investigator"].actions_remaining == actions


def test_battle_medicine_critical_failure_deals_one_d8(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    game = _game(monkeypatch, 20, 1, 2, 1, 5)
    started = game.execute(BattleMedicine("healing_ally"))
    assert started.status is ResultStatus.PAUSED
    resolved = _keep_choice(game)
    target = game._state.creatures["healing_ally"]
    assert target.hp == 5
    # The critical-failure damage is surfaced in the resumed action result;
    # the state intentionally stores only health and the immunity record.
    assert any(event.kind == "damage" for event in resolved.events)


def test_battle_medicine_requires_two_hands_for_a_held_toolkit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    game = _game(monkeypatch, 20, 1, 2, 12, 3, 4)
    actor = game._state.creatures["forensic_investigator"]
    toolkit = actor.worn_items.pop()
    actor.held_items.append(toolkit)
    result = game.execute(BattleMedicine("healing_ally"))
    assert result.status is ResultStatus.REJECTED
    assert "toolkit" in result.message.lower()
    assert actor.actions_remaining == 3


def test_battle_medicine_higher_dc_is_explicitly_unsupported_and_atomic(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    game = _game(monkeypatch, 20, 1, 2, 12, 3, 4)
    actor = game._state.creatures["forensic_investigator"]
    result = game.execute(BattleMedicine("healing_ally", dc=20))
    assert result.status is ResultStatus.UNSUPPORTED
    assert actor.actions_remaining == 3
    assert game._state.condition_immunities == []


def test_critical_reactive_strike_disrupts_battle_medicine_before_healing(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """The Manipulate trigger can interrupt the committed action before its check."""
    reactor = replace(
        content.MELEE_FIGHTER_M,
        definition_id="investigator_healing_reactor",
        hero_points=0,
    )
    setup = EncounterSetup(
        setup_id="investigator_forensic_healing_reactive_strike",
        name="Forensic Investigator Battle Medicine reaction",
        width=4,
        height=3,
        placements=(
            CreaturePlacement(
                "forensic_investigator",
                FORENSIC_INVESTIGATOR.definition_id,
                "Forensic Investigator",
                "blue",
                Position(1, 1),
            ),
            CreaturePlacement(
                "healing_ally",
                content.GUARD_DOG.definition_id,
                "Healing Ally",
                "blue",
                Position(2, 1),
            ),
            CreaturePlacement(
                "reactive_fighter",
                reactor.definition_id,
                "Reactive Fighter",
                "red",
                Position(1, 2),
            ),
        ),
    )
    monkeypatch.setattr(
        content,
        "_STAGED_CREATURES",
        content._STAGED_CREATURES | {reactor.definition_id: reactor},
    )
    monkeypatch.setattr(
        content,
        "_STAGED_SETUPS",
        content._STAGED_SETUPS | {setup.setup_id: setup},
    )
    # Three initiative faces, then a critical Reactive Strike face and its d8.
    game = Encounter.start(setup, rolls=(20, 1, 2, 20, 1))
    for _ in range(4):
        choice = game.inspect().choice
        if choice is None:
            break
        assert choice.kind == "initiative_hero_reroll"
        assert game.choose(choice.choice_id, "keep", choice.owner_actor_id).status in {
            ResultStatus.PAUSED,
            ResultStatus.COMPLETED,
        }
    assert game.inspect().turn_actor_id == "forensic_investigator"
    ally = game._state.creatures["healing_ally"]
    ally.hp = 3
    started = game.execute(BattleMedicine("healing_ally"))
    assert started.status is ResultStatus.PAUSED
    reaction = started.inspection.choice
    assert reaction is not None and reaction.kind == "reaction"
    assert reaction.owner_actor_id == "reactive_fighter"

    path = tmp_path / "investigator-battle-medicine-reaction.json"
    game.save(path)
    game = Encounter.load(path)
    result = game.choose(reaction.choice_id, "accept", reaction.owner_actor_id)
    assert result.status is ResultStatus.COMPLETED
    assert any(event.kind == "disrupted" for event in result.events)
    assert not any(
        event.kind in {"battle_medicine_check", "battle_medicine", "immunity_applied"}
        for event in result.events
    )
    assert game._state.creatures["forensic_investigator"].actions_remaining == 2
    assert game._state.creatures["forensic_investigator"].hp == 7
    assert game._state.creatures["healing_ally"].hp == 3
    assert game._state.condition_immunities == []
    assert not game._state.creatures["reactive_fighter"].reaction_available


def test_terminal_routes_battle_medicine_and_quits_with_bounded_input(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    setup = _setup()
    monkeypatch.setattr(
        content,
        "_STAGED_SETUPS",
        content._STAGED_SETUPS | {setup.setup_id: setup},
    )
    original_start = Encounter.start

    def damaged_start(*args, **kwargs):
        game = original_start(*args, **kwargs)
        game._state.creatures["healing_ally"].hp = 10
        return game

    monkeypatch.setattr(Encounter, "start", damaged_start)
    transcript = BoundedTranscript(max_lines=1200, max_chars=200_000)

    def next_input() -> str:
        prompt = transcript[-1] if transcript else ""
        joined = "\n".join(transcript[-8:])
        if "Choice prompt action:" in prompt:
            return "2"
        if "Choice option number:" in prompt:
            return "2" if "Keep the current result" in joined else "1"
        if "Target number:" in prompt:
            return "1"
        if "Choice:" in prompt:
            match = re.search(r"(?m)^(\d+)\. Battle Medicine$", joined)
            if match:
                return match.group(1)
            match = re.search(r"(?m)^(\d+)\. Quit$", joined)
            if match:
                return match.group(1)
        raise AssertionError(f"unexpected terminal prompt: {prompt!r}")

    bounded = BoundedInput(next_input, max_calls=80, describe=lambda: transcript[-1] if transcript else "")
    exit_code = run_terminal(
        setup=setup,
        rolls=(20, 1, 2, 12, 3, 4),
        input_fn=bounded,
        output_fn=transcript.append,
    )
    assert exit_code == 0
    assert bounded.calls < 80
    assert any("Battle Medicine" in line for line in transcript)
    assert transcript[-1] == "Goodbye."
