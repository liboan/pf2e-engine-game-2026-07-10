"""Independent public interaction checks for the assembled W5 families.

Rules: https://2e.aonprd.com/Feats.aspx?ID=5983,
https://2e.aonprd.com/Feats.aspx?ID=6128,
https://2e.aonprd.com/Spells.aspx?ID=1863,
https://2e.aonprd.com/Spells.aspx?ID=1768.
"""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from time import perf_counter
import json

import pf2e.content as content
import pytest
from pf2e import ExtravagantParry
from pf2e.encounter import Encounter
from pf2e.model import (
    Cast, CreaturePlacement, EncounterSetup, EndTurn, PairedStrikeSelection,
    HealthMode, Position, ResultStatus, Strike, Sustain,
)
from pf2e.monk import FlurryOfBlows
from pf2e.monk_stances import TigerStance
from pf2e.paired_strikes import _decode_selection
from pf2e.terminal import run_terminal
from terminal_test_helpers import BoundedInput, BoundedTranscript


def _setup(monkeypatch, setup_id: str, placements) -> EncounterSetup:
    setup = EncounterSetup(setup_id, setup_id, 8, 5, tuple(placements))
    monkeypatch.setattr(content, "_STAGED_SETUPS", content._STAGED_SETUPS | {setup_id: setup})
    return setup


def _durable_swashbuckler(
    monkeypatch, definition_id: str, *, hp: int = 50,
    health_mode: HealthMode = HealthMode.PC,
):
    definition = replace(
        content.get_definition("swashbuckler_braggart_extravagant_parry_level_1"),
        definition_id=definition_id, hp=hp, health_mode=health_mode,
        hero_points=0 if health_mode is HealthMode.ORDINARY else 1,
    )
    monkeypatch.setattr(content, "CREATURES", content.CREATURES | {definition_id: definition})
    return definition


def _settle(game: Encounter) -> list:
    events = []
    for _ in range(24):
        choice = game.inspect().choice
        if choice is None:
            return events
        option = next((item.option_id for item in choice.options if item.option_id == "keep"), None)
        if option is None and choice.kind == "family_action":
            option = next((
                item.option_id for item in choice.options
                if (selection := _decode_selection(item.option_id)) is not None
                and selection.attack_id == "tiger_claws"
            ), None)
        option = option or choice.options[0].option_id
        result = game.choose(choice.choice_id, option, choice.owner_actor_id)
        assert result.status in {ResultStatus.PAUSED, ResultStatus.COMPLETED}, result.message
        events.extend(result.events)
    raise AssertionError("assembled choice chain did not settle")


def _round_trip(game: Encounter, path: Path) -> Encounter:
    before = game.inspect()
    game.save(path)
    restored = Encounter.load(path)
    assert restored.inspect() == before
    return restored


def test_saved_tiger_flurry_miss_grants_parry_panache_then_critical_bleed_and_victory(
    monkeypatch, tmp_path: Path,
) -> None:
    swash = _durable_swashbuckler(
        monkeypatch, "review_w5_parry_18", hp=18, health_mode=HealthMode.ORDINARY,
    )
    setup = _setup(monkeypatch, "review_w5_tiger_into_parry", (
        CreaturePlacement("monk", "monk_tiger_stance_level_1", "Tiger Monk", "blue", Position(1, 1)),
        CreaturePlacement("swash", swash.definition_id, "Parry Swashbuckler", "red", Position(2, 1)),
    ))
    game = Encounter.start(setup, rolls=(1, 20, 1, 20, 4, 20, 4) + (4,) * 120)
    _settle(game)
    assert game.inspect().turn_actor_id == "swash"
    assert game.execute(ExtravagantParry()).status is ResultStatus.COMPLETED
    assert game.execute(EndTurn()).status is ResultStatus.COMPLETED
    assert game.execute(TigerStance()).status is ResultStatus.COMPLETED

    started = game.execute(FlurryOfBlows(PairedStrikeSelection("swash", "tiger_claws")))
    assert started.status is ResultStatus.PAUSED
    assert game.inspect().choice.kind == "attack_hero_reroll"
    game = _round_trip(game, tmp_path / "tiger-parry-first-check.json")
    choice = game.inspect().choice
    missed = game.choose(choice.choice_id, "keep", choice.owner_actor_id)
    assert missed.status is ResultStatus.PAUSED
    assert any(event.kind == "extravagant_parry_panache" for event in missed.events)
    assert game._state.creatures["swash"].panache
    assert game.inspect().choice.kind == "family_action"
    game = _round_trip(game, tmp_path / "tiger-parry-second-choice.json")
    second_events = _settle(game)
    assert any(event.kind == "persistent_applied" for event in second_events)
    assert len(game._state.persistent_effects) == 1
    assert game._state.persistent_effects[0].dice == (4,)

    for _ in range(24):
        if game.inspect().winner_team is not None:
            break
        actor = game.inspect().turn_actor_id
        if actor == "monk" and "swash" in next(
            option for option in game.options().strikes if option.attack_id == "tiger_claws"
        ).targets:
            result = game.execute(Strike("swash", "tiger_claws"))
            assert result.status in {ResultStatus.PAUSED, ResultStatus.COMPLETED}
            _settle(game)
        if game.inspect().winner_team is None:
            assert game.execute(EndTurn()).status in {ResultStatus.PAUSED, ResultStatus.COMPLETED}
            _settle(game)
    assert game.inspect().winner_team == "blue"
    assert not game._state.martial_stances
    game = _round_trip(game, tmp_path / "tiger-parry-victory.json")
    assert game.inspect().winner_team == "blue"


def test_all_three_w5_families_play_together_to_saved_victory(
    monkeypatch, tmp_path: Path,
) -> None:
    dog = replace(
        content.get_definition("guard_dog_mc2924"),
        definition_id="review_w5_assembled_dog", hp=50,
    )
    monkeypatch.setattr(content, "CREATURES", content.CREATURES | {dog.definition_id: dog})
    setup = _setup(monkeypatch, "review_w5_all_families", (
        CreaturePlacement("bard", "bard_maestro_level_1_hymn_of_healing", "Hymn Bard", "blue", Position(1, 1)),
        CreaturePlacement("ranger", "ranger_precision_level_1_initiate_warden", "Warden Ranger", "blue", Position(1, 2)),
        CreaturePlacement("monk", "monk_tiger_stance_level_1", "Tiger Monk", "blue", Position(3, 1)),
        CreaturePlacement("swash", "swashbuckler_braggart_extravagant_parry_level_1", "Parry Swashbuckler", "blue", Position(3, 2)),
        CreaturePlacement("dog", dog.definition_id, "Guard Dog", "red", Position(4, 2)),
    ))
    game = Encounter.start(setup, rolls=(20, 19, 18, 17, 1, 12, 4, 20, 4, 1) + (4,) * 120)
    _settle(game)
    assert game._state.initiative_order == ["ranger", "bard", "monk", "swash", "dog"]

    assert game.execute(Cast("gravity_weapon")).status is ResultStatus.COMPLETED
    assert game.execute(Strike("dog", "shortbow")).status is ResultStatus.PAUSED
    ranger_events = _settle(game)
    ranger_damage = next(event.damage for event in ranger_events if event.kind == "damage")
    assert ranger_damage is not None and ranger_damage.components[0].modifier == 2
    assert game.execute(EndTurn()).status is ResultStatus.COMPLETED

    assert game.execute(Cast("hymn_of_healing", "monk", actions=2)).status is ResultStatus.COMPLETED
    assert game._state.creatures["monk"].temporary_hp == 2
    assert game.execute(EndTurn()).status is ResultStatus.COMPLETED

    assert game.execute(TigerStance()).status is ResultStatus.COMPLETED
    assert game.execute(Strike("dog", "tiger_claws")).status is ResultStatus.PAUSED
    monk_events = _settle(game)
    assert any(event.kind == "persistent_applied" for event in monk_events)
    assert game.execute(EndTurn()).status is ResultStatus.COMPLETED

    assert game.execute(ExtravagantParry()).status is ResultStatus.COMPLETED
    game = _round_trip(game, tmp_path / "w5-all-families-active.json")
    assert {effect.kind for effect in game._state.active_effects} >= {
        "gravity_weapon", "hymn_of_healing", "extravagant_parry",
    }
    assert game.execute(EndTurn()).status is ResultStatus.COMPLETED

    missed = game.execute(Strike("swash", "jaws"))
    assert missed.status is ResultStatus.COMPLETED
    assert any(event.kind == "extravagant_parry_panache" for event in missed.events)
    assert game._state.creatures["swash"].panache
    assert game.execute(EndTurn()).status in {ResultStatus.PAUSED, ResultStatus.COMPLETED}
    _settle(game)

    for _ in range(50):
        if game.inspect().winner_team is not None:
            break
        assert game.execute(EndTurn()).status in {ResultStatus.PAUSED, ResultStatus.COMPLETED}
        _settle(game)
    assert game.inspect().winner_team == "blue"
    assert not game._state.martial_stances
    assert not any(effect.kind in {"hymn_of_healing", "extravagant_parry"} for effect in game._state.active_effects)
    game = _round_trip(game, tmp_path / "w5-all-families-victory.json")
    assert game.inspect().winner_team == "blue"


def test_tiger_critical_bleed_after_hymn_temporary_hp_then_saved_recipient_healing(
    monkeypatch, tmp_path: Path,
) -> None:
    swash = _durable_swashbuckler(monkeypatch, "review_w5_hymn_recipient_50")
    setup = _setup(monkeypatch, "review_w5_tiger_hymn", (
        CreaturePlacement("bard", "bard_maestro_level_1_hymn_of_healing", "Hymn Bard", "red", Position(4, 1)),
        CreaturePlacement("swash", swash.definition_id, "Hymn Recipient", "red", Position(3, 1)),
        CreaturePlacement("monk", "monk_tiger_stance_level_1", "Tiger Monk", "blue", Position(2, 1)),
    ))
    game = Encounter.start(setup, rolls=(20, 10, 1, 20, 1, 8) + (15,) * 60)
    _settle(game)
    assert game.inspect().turn_actor_id == "bard"
    assert game.execute(Cast("hymn_of_healing", "swash", actions=2)).status is ResultStatus.COMPLETED
    assert game._state.creatures["swash"].temporary_hp == 2
    assert game.execute(EndTurn()).status is ResultStatus.COMPLETED
    assert game.execute(EndTurn()).status is ResultStatus.COMPLETED
    assert game.inspect().turn_actor_id == "monk"
    assert game.execute(TigerStance()).status is ResultStatus.COMPLETED
    started = game.execute(Strike("swash", "tiger_claws"))
    assert started.status is ResultStatus.PAUSED
    game = _round_trip(game, tmp_path / "tiger-hymn-check.json")
    choice = game.inspect().choice
    resolved = game.choose(choice.choice_id, "keep", choice.owner_actor_id)
    assert resolved.status is ResultStatus.COMPLETED
    damage = next(event for event in resolved.events if event.kind == "damage")
    assert damage.temporary_hp_absorbed == 2
    assert damage.remaining_hp_damage > 0
    assert any(event.kind == "persistent_applied" for event in resolved.events)
    assert game._state.creatures["swash"].temporary_hp == 0
    hp_after_hit = game._state.creatures["swash"].hp

    assert game.execute(EndTurn()).status is ResultStatus.COMPLETED
    hymn = next(effect for effect in game._state.active_effects if effect.kind == "hymn_of_healing")
    assert game.execute(Sustain(hymn.effect_id)).status is ResultStatus.COMPLETED
    game = _round_trip(game, tmp_path / "tiger-hymn-before-recipient-start.json")
    assert game.execute(EndTurn()).status is ResultStatus.COMPLETED
    assert game.inspect().turn_actor_id == "swash"
    assert game._state.creatures["swash"].hp == hp_after_hit + 2
    game = _round_trip(game, tmp_path / "tiger-hymn-after-recipient-start.json")
    assert game._state.creatures["swash"].hp == hp_after_hit + 2


def test_gravity_weapon_overrides_anthem_status_bonus_on_saved_first_strike(
    monkeypatch, tmp_path: Path,
) -> None:
    setup = _setup(monkeypatch, "review_w5_gravity_anthem", (
        CreaturePlacement("bard", "bard_maestro_level_1_hymn_of_healing", "Maestro Bard", "blue", Position(1, 1)),
        CreaturePlacement("ranger", "ranger_precision_level_1_initiate_warden", "Warden Ranger", "blue", Position(1, 2)),
        CreaturePlacement("dog", "guard_dog_mc2924", "Guard Dog", "red", Position(4, 2)),
    ))
    game = Encounter.start(setup, rolls=(20, 10, 1, 12, 1, 4) + (15,) * 24)
    _settle(game)
    assert game.inspect().turn_actor_id == "bard"
    assert game.execute(Cast("courageous_anthem")).status is ResultStatus.COMPLETED
    assert game.execute(EndTurn()).status is ResultStatus.COMPLETED
    assert game.inspect().turn_actor_id == "ranger"
    assert game.execute(Cast("gravity_weapon")).status is ResultStatus.COMPLETED
    start = perf_counter()
    for _ in range(40):
        assert game.options().strikes
    assert perf_counter() - start < 2.0
    started = game.execute(Strike("dog", "shortbow"))
    assert started.status is ResultStatus.PAUSED
    saved = tmp_path / "gravity-anthem-check.json"
    game = _round_trip(game, saved)
    forged = json.loads(saved.read_text())
    forged["state"]["pending_choice"]["gravity_weapon_bonus"] = False
    forged_path = tmp_path / "forged-gravity-anthem-check.json"
    forged_path.write_text(json.dumps(forged))
    with pytest.raises(ValueError):
        Encounter.load(forged_path)
    choice = game.inspect().choice
    resolved = game.choose(choice.choice_id, "keep", choice.owner_actor_id)
    damage = next(event.damage for event in resolved.events if event.kind == "damage")
    assert damage is not None
    assert damage.components[0].rolls == (1,)
    assert damage.components[0].modifier == 2  # Gravity 2, Anthem 1: same type, use the higher.
    assert damage.total == 3
    assert game._state.creatures["ranger"].gravity_weapon_bonus_attack_id is None


@pytest.mark.parametrize(
    ("setup_id", "spell_label", "mode_label", "event_text", "rolls"),
    (
        ("w5_gravity_weapon_vs_guard_dog", "Gravity Weapon", "1 action", "commits Gravity Weapon", (20, 1)),
        ("w5_hymn_of_healing_vs_guard_dog", "Hymn of Healing", "2 actions", "starts Hymn of Healing", (20, 1, 1)),
    ),
)
def test_numbered_terminal_casts_w5_focus_spells(
    setup_id: str, spell_label: str, mode_label: str, event_text: str,
    rolls: tuple[int, ...],
) -> None:
    transcript = BoundedTranscript(max_lines=210, max_chars=32_000)
    state = {"menu": "", "prompt": "", "phase": "cast"}

    def output(line: str) -> None:
        transcript.append(line)
        if line.startswith("1. "):
            state["menu"] = line
        if line.endswith((":", "?")):
            state["prompt"] = line

    def number(label: str) -> str:
        for row in state["menu"].splitlines():
            index, text = row.split(". ", 1)
            if label in text:
                return index
        raise AssertionError(f"missing {label!r} from terminal menu")

    def answer() -> str:
        prompt = state["prompt"]
        if prompt == "Choice prompt action:":
            return number("Resolve this choice")
        if prompt == "Choice option number:":
            return number("Keep")
        if prompt == "Choice:":
            if state["phase"] == "cast":
                state["phase"] = "quit"
                return number("Cast")
            return number("Quit")
        if prompt == "Spell number:":
            return number(spell_label)
        if prompt == "Casting mode:":
            return number(mode_label)
        if prompt == "Target number:":
            return number("Ally")
        raise AssertionError(f"unexpected terminal prompt {prompt!r}")

    assert run_terminal(
        setup=content.get_setup(setup_id), rolls=rolls,
        input_fn=BoundedInput(answer, max_calls=25), output_fn=output,
    ) == 0
    rendered = "\n".join(transcript)
    assert event_text in rendered
    assert "Rejected:" not in rendered
