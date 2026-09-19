"""Source-informed Level-2 Precision Ranger Hunter's Aim bundle.

Sources checked 2026-09-18:

* Ranger advancement and feats: https://2e.aonprd.com/Classes.aspx?ID=36
* Hunter's Aim: https://2e.aonprd.com/Feats.aspx?ID=4867
* Assurance: https://2e.aonprd.com/Feats.aspx?ID=5121

The selected definition and staged encounter are normally catalogued; these
tests additionally use narrow local fixtures for adversarial rule probes.
"""

from __future__ import annotations

from dataclasses import replace
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

import pf2e.content as content
from pf2e.content import GUARD_DOG
from pf2e.l2_ranger_content import (
    RANGER_PRECISION_LEVEL_2,
    RANGER_PRECISION_LEVEL_2_HUNTERS_AIM_SETUP,
)
from pf2e.encounter import Encounter
from pf2e.model import Choose, CreaturePlacement, EndTurn, HuntedPreyState, Position, ResultStatus
from pf2e.ranger import (
    HunterAim,
    HunterAimIntent,
    HuntPrey,
    hunter_aim_attack_bonus,
    validate_hunter_aim_intent,
)
from pf2e.skill_actions import Trip
from pf2e.terminal import run_terminal
from terminal_test_helpers import BoundedInput, BoundedTranscript


def _register_level_two_ranger(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        content,
        "_STAGED_CREATURES",
        content._STAGED_CREATURES | {
            RANGER_PRECISION_LEVEL_2.definition_id: RANGER_PRECISION_LEVEL_2,
        },
    )
    monkeypatch.setattr(
        content,
        "_STAGED_SETUPS",
        content._STAGED_SETUPS | {
            RANGER_PRECISION_LEVEL_2_HUNTERS_AIM_SETUP.setup_id:
                RANGER_PRECISION_LEVEL_2_HUNTERS_AIM_SETUP,
        },
    )


def _settle_start_choices(game: Encounter) -> None:
    while (choice := game.inspect().choice) is not None:
        option_id = "keep" if any(item.option_id == "keep" for item in choice.options) else choice.options[0].option_id
        assert game.execute(Choose(choice.choice_id, option_id, choice.owner_actor_id)).status in {
            ResultStatus.PAUSED,
            ResultStatus.COMPLETED,
        }


def _keep_pending_choice(game: Encounter):
    choice = game.inspect().choice
    assert choice is not None
    return game.execute(Choose(choice.choice_id, "keep", choice.owner_actor_id))


def test_level_two_precision_ranger_sheet_advances_only_level_based_facts() -> None:
    ranger = RANGER_PRECISION_LEVEL_2
    assert (ranger.level, ranger.hp, ranger.ac, ranger.perception, ranger.class_dc) == (2, 32, 19, 8, 18)
    assert tuple((attack.attack_id, attack.modifier) for attack in ranger.attacks) == (
        ("shortbow", 8), ("fist", 8),
    )
    assert dict((name, modifier) for name, _rank, modifier in ranger.saves) == {
        "fortitude": 8, "reflex": 10, "will": 6,
    }
    assert dict((name, modifier) for name, _rank, modifier in ranger.skills)["athletics"] == 5
    assert {"Hunter's Aim", "Assurance (Athletics)", "Hunted Shot"} <= set(ranger.feats)
    assert {"hunt_prey", "hunted_shot", "hunters_aim", "assurance_athletics", "hunter_edge_precision"} <= set(ranger.abilities)
    assert "combat-only" in " ".join(ranger.sheet_notes).lower()


def test_hunter_aim_intent_requires_precision_prey_ranged_attack_and_exact_costs(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _register_level_two_ranger(monkeypatch)
    attack = next(attack for attack in RANGER_PRECISION_LEVEL_2.attacks if attack.attack_id == "shortbow")
    actor = SimpleNamespace(
        actor_id="ranger",
        definition_id=RANGER_PRECISION_LEVEL_2.definition_id,
        hunted_prey=HuntedPreyState("prey"),
    )
    prey = SimpleNamespace(actor_id="prey")
    intent = HunterAimIntent("prey", "shortbow", None)

    assert validate_hunter_aim_intent(
        intent, actor=actor, target=prey, attack=attack, actions_cost=2, attack_count_cost=1,
    )
    assert hunter_aim_attack_bonus(intent) == 2
    assert not validate_hunter_aim_intent(
        intent, actor=actor, target=prey, attack=attack, actions_cost=1, attack_count_cost=1,
    )
    assert not validate_hunter_aim_intent(
        intent, actor=actor, target=SimpleNamespace(actor_id="other"), attack=attack,
        actions_cost=2, attack_count_cost=1,
    )
    fist = next(attack for attack in RANGER_PRECISION_LEVEL_2.attacks if attack.attack_id == "fist")
    assert not validate_hunter_aim_intent(
        intent, actor=actor, target=prey, attack=fist, actions_cost=2, attack_count_cost=1,
    )


def test_hunters_aim_concealed_lesser_cover_save_reloads_one_arrow_and_one_map(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    """The first public hook checkpoint keeps normal strike bookkeeping.

    Dim light makes the prey concealed and the intervening creature supplies
    lesser cover.  Hunter's Aim alone suppresses those targeting gates; its
    attack still reaches the normal saved Hero Point decision after committing
    its one arrow and one ranged MAP count.
    """
    _register_level_two_ranger(monkeypatch)
    setup = replace(
        RANGER_PRECISION_LEVEL_2_HUNTERS_AIM_SETUP,
        setup_id="test_local_l2_hunters_aim_dim_lesser_cover",
        ambient_light="dim",
    )
    monkeypatch.setattr(content, "_STAGED_SETUPS", content._STAGED_SETUPS | {setup.setup_id: setup})
    # Initiative for Ranger/cover/prey, then attack, shortbow damage, and
    # Precision damage.  The attack is deliberately not a natural 20 so the
    # live Precision target survives the committed saved-decision checkpoint.
    game = Encounter.start(setup, rolls=(20, 1, 1, 10, 1, 1))
    _settle_start_choices(game)
    assert game.inspect().turn_actor_id == "ranger"
    assert game.execute(HuntPrey("prey")).status is ResultStatus.COMPLETED

    started = game.execute(HunterAim("prey", "shortbow"))
    assert started.status is ResultStatus.PAUSED
    assert game.inspect().choice is not None
    ranger = game._state.creatures["ranger"]
    assert (ranger.ammunition["arrow"], ranger.strikes_this_turn, ranger.actions_remaining) == (19, 1, 0)

    save_path = tmp_path / "l2-hunters-aim-saved-attack.json"
    game.save(save_path)
    restored = Encounter.load(save_path)
    restored_ranger = restored._state.creatures["ranger"]
    assert (restored_ranger.ammunition["arrow"], restored_ranger.strikes_this_turn) == (19, 1)
    resolved = _keep_pending_choice(restored)
    check = next(event.check for event in resolved.events if event.kind == "strike")
    assert check is not None
    assert (check.modifier, check.dc, check.map_penalty) == (10, 15, 0)
    assert any(modifier.source == "Hunter's Aim" and modifier.amount == 2 for modifier in check.modifier_breakdown)
    assert not any(event.kind.startswith("concealment_") for event in (*started.events, *resolved.events))


def test_hunters_aim_rejects_nonprey_and_insufficient_actions_atomically(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _register_level_two_ranger(monkeypatch)
    game = Encounter.start(RANGER_PRECISION_LEVEL_2_HUNTERS_AIM_SETUP, rolls=(20, 1, 1))
    _settle_start_choices(game)
    before = game.inspect()
    assert game.execute(HunterAim("prey", "shortbow")).status is ResultStatus.REJECTED
    assert game.inspect() == before

    assert game.execute(HuntPrey("cover")).status is ResultStatus.COMPLETED
    before = game.inspect()
    assert game.execute(HunterAim("prey", "shortbow")).status is ResultStatus.REJECTED
    assert game.inspect() == before

    assert game.execute(HuntPrey("prey")).status is ResultStatus.COMPLETED
    before = game.inspect()
    assert game.execute(HunterAim("prey", "shortbow")).status is ResultStatus.REJECTED
    assert game.inspect() == before


def test_level_two_assurance_athletics_uses_the_existing_fixed_public_trip(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _register_level_two_ranger(monkeypatch)
    setup = replace(
        RANGER_PRECISION_LEVEL_2_HUNTERS_AIM_SETUP,
        setup_id="test_local_l2_ranger_assurance_athletics",
        width=3,
        placements=(
            CreaturePlacement(
                "ranger", RANGER_PRECISION_LEVEL_2.definition_id,
                "Level 2 Precision Ranger", "blue", Position(0, 1),
            ),
            CreaturePlacement("prey", "guard_dog_mc2924", "Prey Dog", "red", Position(1, 1)),
        ),
    )
    monkeypatch.setattr(content, "_STAGED_SETUPS", content._STAGED_SETUPS | {setup.setup_id: setup})
    game = Encounter.start(setup, rolls=(20, 1))
    _settle_start_choices(game)
    result = game.execute(Trip("prey", use_assurance=True))
    assert result.status is ResultStatus.COMPLETED
    check = next(event.check for event in result.events if event.kind == "trip_check")
    assert check is not None
    assert (check.method, check.die, check.modifier, check.total) == ("assurance", None, 4, 14)


def test_forged_saved_hunters_aim_intent_is_rejected_before_resuming_attack(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    _register_level_two_ranger(monkeypatch)
    setup = replace(
        RANGER_PRECISION_LEVEL_2_HUNTERS_AIM_SETUP,
        setup_id="test_local_l2_hunters_aim_forged_saved_intent",
        ambient_light="dim",
    )
    monkeypatch.setattr(content, "_STAGED_SETUPS", content._STAGED_SETUPS | {setup.setup_id: setup})
    game = Encounter.start(setup, rolls=(20, 1, 1, 10, 1, 1))
    _settle_start_choices(game)
    assert game.execute(HuntPrey("prey")).status is ResultStatus.COMPLETED
    assert game.execute(HunterAim("prey", "shortbow")).status is ResultStatus.PAUSED

    path = tmp_path / "forged-hunters-aim.json"
    game.save(path)
    payload = json.loads(path.read_text())
    intent = payload["state"]["pending_choice"]["continuation"]["hunter_aim_intent"]
    assert intent == ["prey", "shortbow", "shortbow"]
    intent[0] = "cover"
    path.write_text(json.dumps(payload))
    with pytest.raises(ValueError, match="Hunter's Aim"):
        Encounter.load(path)


def test_hunters_aim_reaction_interruption_round_trips_and_still_uses_one_arrow(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    """Reactive Strike remains a normal interruption, rather than a bypass."""
    _register_level_two_ranger(monkeypatch)
    reactive_prey = replace(
        GUARD_DOG,
        definition_id="test_local_reactive_prey_for_hunters_aim",
        hp=40,
        abilities=("reactive_strike",),
        attacks=(replace(GUARD_DOG.attacks[0], reach_ft=30),),
    )
    setup = replace(
        RANGER_PRECISION_LEVEL_2_HUNTERS_AIM_SETUP,
        setup_id="test_local_l2_hunters_aim_reactive_prey",
        placements=(
            CreaturePlacement(
                "ranger", RANGER_PRECISION_LEVEL_2.definition_id,
                "Level 2 Precision Ranger", "blue", Position(0, 1),
            ),
            CreaturePlacement("cover", "guard_dog_mc2924", "Cover Dog", "red", Position(2, 1)),
            CreaturePlacement("prey", reactive_prey.definition_id, "Reactive Prey", "red", Position(4, 1)),
        ),
    )
    monkeypatch.setattr(
        content, "_STAGED_CREATURES",
        content._STAGED_CREATURES | {reactive_prey.definition_id: reactive_prey},
    )
    monkeypatch.setattr(content, "_STAGED_SETUPS", content._STAGED_SETUPS | {setup.setup_id: setup})
    game = Encounter.start(setup, rolls=(20, 1, 1, 10, 1, 1))
    _settle_start_choices(game)
    assert game.execute(HuntPrey("prey")).status is ResultStatus.COMPLETED
    paused = game.execute(HunterAim("prey", "shortbow"))
    choice = paused.inspection.choice
    assert paused.status is ResultStatus.PAUSED and choice is not None and choice.kind == "reaction"
    # The standard reaction window precedes committing the ammunition/MAP
    # Strike; declining it must commit each exactly once.
    assert (game._state.creatures["ranger"].ammunition["arrow"], game._state.creatures["ranger"].strikes_this_turn) == (20, 0)

    path = tmp_path / "hunters-aim-reactive-choice.json"
    game.save(path)
    restored = Encounter.load(path)
    choice = restored.inspect().choice
    assert choice is not None and choice.kind == "reaction"
    assert restored.execute(Choose(choice.choice_id, "decline", choice.owner_actor_id)).status is ResultStatus.PAUSED
    assert (restored._state.creatures["ranger"].ammunition["arrow"], restored._state.creatures["ranger"].strikes_this_turn) == (19, 1)
    resolved = _keep_pending_choice(restored)
    assert resolved.status is ResultStatus.COMPLETED
    check = next(event.check for event in resolved.events if event.kind == "strike")
    assert check is not None and check.attack_count == 1
    assert restored._state.creatures["ranger"].ammunition["arrow"] == 19


def test_level_two_ranger_wins_prepares_saves_and_hunts_in_a_next_scene(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    """Healthy victory uses the ordinary rest/preparation/scene lifecycle."""
    _register_level_two_ranger(monkeypatch)
    first = replace(
        RANGER_PRECISION_LEVEL_2_HUNTERS_AIM_SETUP,
        setup_id="test_local_l2_ranger_hunters_aim_win",
        width=3,
        placements=(
            CreaturePlacement(
                "ranger", RANGER_PRECISION_LEVEL_2.definition_id,
                "Level 2 Precision Ranger", "blue", Position(0, 1),
            ),
            CreaturePlacement("prey", "guard_dog_mc2924", "Prey Dog", "red", Position(1, 1)),
        ),
    )
    second = replace(
        first,
        setup_id="test_local_l2_ranger_next_scene",
        placements=(
            first.placements[0],
            CreaturePlacement("new_prey", "guard_dog_mc2924", "New Prey Dog", "red", Position(1, 1)),
        ),
    )
    monkeypatch.setattr(
        content, "_STAGED_SETUPS", content._STAGED_SETUPS | {
            first.setup_id: first, second.setup_id: second,
        },
    )
    # Initiatives, natural-20 Hunter's Aim, 2d6 base damage and 2d8 Precision.
    game = Encounter.start(first, rolls=(20, 1, 20, 6, 6, 8, 8, 20, 1))
    _settle_start_choices(game)
    assert game.execute(HuntPrey("prey")).status is ResultStatus.COMPLETED
    assert game.execute(HunterAim("prey", "shortbow")).status is ResultStatus.PAUSED
    assert _keep_pending_choice(game).inspection.winner_team == "blue"

    assert game.record_rested(("ranger",), day_number=2, elapsed_seconds=28_800).status is ResultStatus.COMPLETED
    assert game.daily_prepare(("ranger",)).status is ResultStatus.COMPLETED
    path = tmp_path / "l2-ranger-prepared.json"
    game.save(path)
    restored = Encounter.load(path)
    assert restored.next_encounter(second).status in {ResultStatus.PAUSED, ResultStatus.COMPLETED}
    _settle_start_choices(restored)
    for _ in range(2):
        if restored.inspect().turn_actor_id == "ranger":
            break
        assert restored.execute(EndTurn()).status is ResultStatus.COMPLETED
    assert restored.inspect().turn_actor_id == "ranger"
    assert restored.execute(HuntPrey("new_prey")).status is ResultStatus.COMPLETED


def test_terminal_plays_level_two_hunt_prey_then_hunters_aim(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _register_level_two_ranger(monkeypatch)
    setup = replace(
        RANGER_PRECISION_LEVEL_2_HUNTERS_AIM_SETUP,
        setup_id="test_local_l2_ranger_terminal_hunters_aim",
        width=3,
        placements=(
            CreaturePlacement(
                "ranger", RANGER_PRECISION_LEVEL_2.definition_id,
                "Level 2 Precision Ranger", "blue", Position(0, 1),
            ),
            CreaturePlacement("prey", "guard_dog_mc2924", "Prey Dog", "red", Position(1, 1)),
        ),
    )
    monkeypatch.setattr(content, "_STAGED_SETUPS", content._STAGED_SETUPS | {setup.setup_id: setup})
    transcript = BoundedTranscript(max_lines=300, max_chars=50_000)
    menu = {"text": "", "prompt": "", "hunted": False}

    def output(line: str) -> None:
        transcript.append(line)
        if line.startswith("1. "):
            menu["text"] = line
        if line.endswith(":"):
            menu["prompt"] = line

    def menu_number(label: str) -> str:
        for row in menu["text"].splitlines():
            if ". " in row and row.split(". ", 1)[1] == label:
                return row.split(". ", 1)[0]
        raise AssertionError(f"missing terminal menu item {label!r}: {menu['text']!r}")

    def script(prompt: str) -> str:
        if prompt == "Choice:":
            if "Hunt Prey" in menu["text"] and not menu["hunted"]:
                menu["hunted"] = True
                return menu_number("Hunt Prey")
            if "Hunter's Aim" in menu["text"]:
                return menu_number("Hunter's Aim")
            return menu_number("Quit")
        if prompt == "Choice prompt action:":
            return "2"  # Keep a Hero Point check result.
        if prompt == "Choice option number:":
            return "1"
        if prompt in {"Hunt Prey target:", "Shortbow target:", "Target number:"}:
            return "1"
        if prompt in {"Weapon / attack number:", "Damage intent:"}:
            return "1"
        raise AssertionError(f"unexpected terminal prompt: {prompt!r}")

    assert run_terminal(
        setup=setup,
        rolls=(20, 1, 20, 6, 6, 8, 8),
        input_fn=BoundedInput(lambda: script(menu["prompt"])),
        output_fn=output,
    ) == 0
    rendered = "\n".join(transcript)
    assert "Hunt Prey" in rendered and "Hunter's Aim" in rendered
