"""Released shared integration checks for the final finite level-two wave."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from pf2e.alchemy import advanced_alchemy_capacity
from pf2e.content import get_setup
from pf2e.encounter import Encounter
from pf2e.investigator import DeviseStratagem, PersonOfInterest
from pf2e.model import EndTurn, Position, QuickBomber, ResultStatus, Strike, Stride
from pf2e.terminal import run_terminal
from terminal_test_helpers import BoundedInput, BoundedTranscript


def _settle(game: Encounter) -> None:
    for _ in range(12):
        choice = game.inspect().choice
        if choice is None:
            return
        option = next(
            (item.option_id for item in choice.options if item.option_id == "keep"),
            choice.options[0].option_id,
        )
        assert game.choose(choice.choice_id, option, choice.owner_actor_id).status in {
            ResultStatus.COMPLETED,
            ResultStatus.PAUSED,
        }
    raise AssertionError("initiative did not settle")


def _to_turn(game: Encounter, actor_id: str) -> None:
    for _ in range(len(game._state.initiative_order) + 1):
        if game.inspect().turn_actor_id == actor_id:
            return
        assert game.execute(EndTurn()).status is ResultStatus.COMPLETED
        _settle(game)
    raise AssertionError(f"did not reach {actor_id}")


def test_person_of_interest_round_trips_free_devise_and_expires_without_resetting_cooldown(
    tmp_path: Path,
) -> None:
    game = Encounter.start(
        get_setup("staged_investigator_forensic_level_2_assurance_medicine"),
        rolls=(20, 1, 1, 12),
    )
    _settle(game)
    _to_turn(game, "forensic_investigator")
    assert game.options().person_of_interest_targets == ("healing_ally", "healing_dog")

    chosen = game.execute(PersonOfInterest("healing_dog"))
    assert chosen.status is ResultStatus.COMPLETED
    actor = game._state.creatures["forensic_investigator"]
    assert actor.investigator_person_of_interest is not None
    assert actor.investigator_person_of_interest.target_id == "healing_dog"
    assert actor.investigator_person_of_interest_cooldown_until == 600

    path = tmp_path / "person-of-interest.json"
    game.save(path)
    restored = Encounter.load(path)
    wrong_target = restored.execute(DeviseStratagem("healing_ally", free_action=True))
    assert wrong_target.status is ResultStatus.REJECTED
    free_devise = restored.execute(DeviseStratagem("healing_dog", free_action=True))
    assert free_devise.status is ResultStatus.PAUSED
    assert restored._state.creatures["forensic_investigator"].actions_remaining == 2
    mode = restored.inspect().choice
    assert mode is not None
    assert restored.choose(mode.choice_id, "attack", mode.owner_actor_id).status is ResultStatus.COMPLETED

    # A real elapsed-time transition clears the one-minute target grant at
    # the exact boundary, while retaining the independent ten-minute lockout.
    restored._advance_elapsed_time(restored._state, 60)
    assert restored._state.creatures["forensic_investigator"].investigator_person_of_interest is None
    assert "person_of_interest" not in restored.options().available_actions
    restored._advance_elapsed_time(restored._state, 540)
    assert "person_of_interest" in restored.options().available_actions


def test_load_rejects_person_of_interest_grant_on_l1_investigator(tmp_path: Path) -> None:
    game = Encounter.start(get_setup("investigator_forensic_vs_two_guard_dogs"))
    path = tmp_path / "forged-person-of-interest.json"
    game.save(path)
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["state"]["creatures"]["forensic_investigator"]["investigator_person_of_interest"] = {
        "target_id": "dog_a",
        "expires_at_seconds": 60,
    }
    path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(ValueError, match="Person of Interest state outside its admitted build"):
        Encounter.load(path)


@pytest.mark.parametrize(
    ("field", "value", "message"),
    (
        ("expires_at_seconds", 61, "overlong Person of Interest grant"),
        ("cooldown", 0, "inconsistent Person of Interest cooldown"),
    ),
)
def test_load_rejects_extended_live_person_of_interest_grant(
    tmp_path: Path, field: str, value: int, message: str,
) -> None:
    game = Encounter.start(
        get_setup("staged_investigator_forensic_level_2_assurance_medicine"),
        rolls=(20, 1, 1),
    )
    _settle(game)
    _to_turn(game, "forensic_investigator")
    assert game.execute(PersonOfInterest("healing_dog")).status is ResultStatus.COMPLETED
    path = tmp_path / f"forged-person-of-interest-{field}.json"
    game.save(path)
    payload = json.loads(path.read_text(encoding="utf-8"))
    actor_data = payload["state"]["creatures"]["forensic_investigator"]
    if field == "expires_at_seconds":
        actor_data["investigator_person_of_interest"][field] = value
        actor_data["investigator_person_of_interest_cooldown_until"] = value + 540
    else:
        actor_data["investigator_person_of_interest_cooldown_until"] = value
    path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(ValueError, match=message):
        Encounter.load(path)


def test_person_of_interest_free_devise_remains_available_at_zero_actions() -> None:
    game = Encounter.start(
        get_setup("staged_investigator_forensic_level_2_assurance_medicine"),
        rolls=(20, 1, 1, 12),
    )
    _settle(game)
    _to_turn(game, "forensic_investigator")
    assert game.execute(PersonOfInterest("healing_dog")).status is ResultStatus.COMPLETED
    actor = game._state.creatures["forensic_investigator"]
    assert game.execute(Stride((Position(0, 1),))).status is ResultStatus.COMPLETED
    assert game.execute(Stride((Position(1, 1),))).status is ResultStatus.COMPLETED
    assert game.inspect().turn_actor_id == "forensic_investigator"
    actor = game._state.creatures["forensic_investigator"]
    assert actor.actions_remaining == 0
    assert "devise_stratagem" in game.options().available_actions

    free_devise = game.execute(DeviseStratagem("healing_dog", free_action=True))
    assert free_devise.status is ResultStatus.PAUSED
    assert actor.actions_remaining == 0


def test_l2_bomber_catalog_state_far_lobber_range_and_pending_save_round_trip(
    tmp_path: Path,
) -> None:
    game = Encounter.start(
        get_setup("l2_bomber_far_lobber_vs_guard_dog"), rolls=(20, 1, 10, 6),
    )
    _settle(game)
    _to_turn(game, "alchemist")
    state = game._state.alchemy_states["alchemist"]
    assert (
        state.character_level,
        state.selected_level_1_feat,
        state.selected_level_2_feat,
        state.known_formula_ids[-2:],
    ) == (2, "quick_bomber", "far_lobber", ("alchemists_fire_lesser", "acid_flask_lesser"))
    initial_prepared = tuple(
        item
        for item in game._state.infused_alchemy_items.values()
        if item.creator_actor_id == "alchemist" and item.daily_preparation_id == "day:1"
    )
    assert len(initial_prepared) == advanced_alchemy_capacity(state) == 8
    assert len(state.known_formula_ids) == 10

    attack = game.execute(QuickBomber("dog", "bottled_lightning_lesser"))
    assert attack.status is ResultStatus.PAUSED
    pending = game._state.pending_choice
    assert pending is not None and pending.ranged_penalty == 0
    path = tmp_path / "l2-bomber-pending.json"
    game.save(path)
    restored = Encounter.load(path)
    assert restored._state.alchemy_states["alchemist"].selected_level_2_feat == "far_lobber"
    choice = restored.inspect().choice
    assert choice is not None
    finished = restored.choose(choice.choice_id, "keep", choice.owner_actor_id)
    assert finished.status is ResultStatus.COMPLETED
    assert any(event.kind == "bomb_consumed" for event in finished.events)


def test_load_rejects_level_two_bomber_state_forged_into_level_one_setup(tmp_path: Path) -> None:
    game = Encounter.start(
        get_setup("staged_bomber_alchemist_vs_guard_dog"), rolls=(20, 1),
    )
    path = tmp_path / "forged-l2-bomber.json"
    game.save(path)
    payload = json.loads(path.read_text(encoding="utf-8"))
    state = payload["state"]["alchemy_states"]["alchemist"]
    state["character_level"] = 2
    state["selected_level_2_feat"] = "far_lobber"
    state["known_formula_ids"].extend(("alchemists_fire_lesser", "acid_flask_lesser"))
    path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(ValueError, match="changed selected Bomber build"):
        Encounter.load(path)


def test_load_rejects_forged_bomber_vial_capacity(tmp_path: Path) -> None:
    game = Encounter.start(
        get_setup("l2_bomber_far_lobber_vs_guard_dog"), rolls=(20, 1),
    )
    path = tmp_path / "forged-bomber-vial-capacity.json"
    game.save(path)
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["state"]["alchemy_states"]["alchemist"]["vial_capacity"] = 7
    path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(ValueError, match="changed selected Bomber build"):
        Encounter.load(path)


def test_terminal_selects_far_lobber_target_beyond_ordinary_bomb_maximum() -> None:
    commands = iter((
        "2", "1",  # Resolve the Bomber's initiative choice by keeping it.
        "5", "1", "1",  # Quick Bomber, Bottled Lightning, Guard Dog at 125 feet.
        "1",  # Keep the saved attack result.
        "x",
    ))
    output: list[str] = []

    assert run_terminal(
        setup=get_setup("l2_bomber_far_lobber_long_range_vs_guard_dog"),
        rolls=(20, 1, 10, 6),
        input_fn=lambda: next(commands),
        output_fn=output.append,
    ) == 0
    assert any("uses Quick Bomber" in line for line in output)


def test_terminal_offers_and_dispatches_l2_assurance_battle_medicine(monkeypatch) -> None:
    transcript = BoundedTranscript()
    menu = {"text": "", "prompt": ""}

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

    def script() -> str:
        if menu["prompt"] == "Choice prompt action:":
            return menu_number("Resolve this choice")
        if menu["prompt"] == "Choice option number:":
            return menu_number("Keep initiative")
        if menu["prompt"] == "Choice:":
            if "Battle Medicine" in menu["text"]:
                return menu_number("Battle Medicine")
            return menu_number("Quit")
        if menu["prompt"] == "Target number:":
            return "1"
        if menu["prompt"] == "Battle Medicine method:":
            return "2"
        raise AssertionError(f"unexpected terminal prompt: {menu['prompt']!r}")

    original_start = Encounter.start

    def start_with_injured_ally(_cls, *args, **kwargs):
        game = original_start(*args, **kwargs)
        game._state.creatures["healing_ally"].hp = 1
        return game

    monkeypatch.setattr(Encounter, "start", classmethod(start_with_injured_ally))

    assert run_terminal(
        setup=get_setup("staged_investigator_forensic_level_2_assurance_medicine"),
        rolls=(20, 1, 1, 3, 4),
        input_fn=BoundedInput(script, max_calls=20),
        output_fn=output,
    ) == 0
    rendered = "\n".join(transcript)
    assert "Battle Medicine method:" in rendered
    assert "attempts Battle Medicine on Healing Ally: Success (16 vs DC 15)." in rendered


def test_terminal_routes_person_of_interest_to_free_devise_and_strike(monkeypatch) -> None:
    transcript = BoundedTranscript()
    menu = {"text": "", "prompt": ""}
    started: dict[str, Encounter] = {}
    target_choices = 0

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

    def script() -> str:
        nonlocal target_choices
        if menu["prompt"] == "Choice prompt action:":
            return menu_number("Resolve this choice")
        if menu["prompt"] == "Choice option number:":
            return menu_number(
                "Keep initiative" if "Keep initiative" in menu["text"] else "Attack Stratagem"
            )
        if menu["prompt"] == "Choice:":
            for label in ("Person of Interest", "Devise a Stratagem", "Quit"):
                if label in menu["text"]:
                    return menu_number(label)
        if menu["prompt"] == "Target number:":
            target_choices += 1
            return "2" if target_choices == 1 else "1"
        raise AssertionError(f"unexpected terminal prompt: {menu['prompt']!r}")

    original_start = Encounter.start

    def capture_start(_cls, *args, **kwargs):
        game = original_start(*args, **kwargs)
        started["game"] = game
        return game

    monkeypatch.setattr(Encounter, "start", classmethod(capture_start))
    assert run_terminal(
        setup=get_setup("staged_investigator_forensic_level_2_assurance_medicine"),
        rolls=(20, 1, 1, 20, 6),
        input_fn=BoundedInput(script, max_calls=40),
        output_fn=output,
    ) == 0
    game = started["game"]
    actor = game._state.creatures["forensic_investigator"]
    assert target_choices == 2
    assert actor.actions_remaining == 2
    assert actor.investigator_stratagem is not None
    assert actor.investigator_stratagem.target_id == "healing_dog"
    assert game.execute(Stride((Position(2, 2), Position(3, 2)))).status is ResultStatus.COMPLETED
    strike = game.execute(Strike("healing_dog"))
    assert strike.status is ResultStatus.COMPLETED
    assert any(event.kind == "strike" for event in strike.events)
