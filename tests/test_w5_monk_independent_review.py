"""Independent public review of the W5 Monk stance family.

Rules: https://2e.aonprd.com/Feats.aspx?ID=5983 and
https://2e.aonprd.com/Feats.aspx?ID=5984.
"""

from __future__ import annotations

from pathlib import Path
from dataclasses import replace
from types import MappingProxyType
import json
import re
from time import perf_counter

import pf2e.content as content
import pytest
from pf2e import EndTurn
from pf2e.damage import DamageDefense
from pf2e.encounter import Encounter
from pf2e.justice_content import JUSTICE_CHAMPION
from pf2e.model import (
    ActiveConditionEffect, CreaturePlacement, EffectExpiration, EncounterSetup,
    PairedStrikeSelection, PersistentDamageEffect, Position, ResultStatus, Step, Strike,
)
from pf2e.monk import FlurryOfBlows
from pf2e.monk_stances import TigerStance, WolfStance
from pf2e.opponent_content import SKELETON_GUARD
from pf2e.paired_strikes import _decode_selection
from pf2e.skill_actions import Trip
from pf2e.terminal import run_terminal
from terminal_test_helpers import BoundedInput, BoundedTranscript


def _settle(game: Encounter, *, save_path: Path | None = None) -> tuple[Encounter, list]:
    events = []
    for _ in range(30):
        choice = game.inspect().choice
        if choice is None:
            return game, events
        if save_path is not None and choice.kind == "family_action":
            before = game.inspect()
            game.save(save_path)
            game = Encounter.load(save_path)
            assert game.inspect() == before
            choice = game.inspect().choice
            assert choice is not None
        selected = next((o.option_id for o in choice.options if o.option_id == "keep"), None)
        if selected is None and choice.kind == "family_action":
            selected = next(
                (o.option_id for o in choice.options
                 if (s := _decode_selection(o.option_id)) is not None
                 and s.attack_id == "tiger_claws"),
                None,
            )
        selected = selected or choice.options[0].option_id
        result = game.choose(choice.choice_id, selected, choice.owner_actor_id)
        assert result.status in {ResultStatus.PAUSED, ResultStatus.COMPLETED}, result.message
        events.extend(result.events)
    raise AssertionError("choice chain did not settle")


def _start_monk(setup_id: str, rolls) -> Encounter:
    game = Encounter.start(content.get_setup(setup_id), rolls=rolls)
    game, _ = _settle(game)
    assert game.inspect().turn_actor_id == "monk"
    return game


def test_tiger_legal_grant_flurry_saved_second_strike_and_victory(tmp_path: Path) -> None:
    sheet = content.get_definition("monk_tiger_stance_level_1")
    assert "Tiger Stance" in sheet.feats and "Monastic Weaponry" not in sheet.feats
    assert "Powerful Fist" in sheet.feats and "Flurry of Blows" in sheet.feats
    assert not any(attack.item_id == "kama" for attack in sheet.attacks)
    assert "simple_and_martial_monk_weapons" not in dict(sheet.proficiencies)

    game = _start_monk(
        "w5_tiger_stance_vs_guard_dog",
        (20, 1, 14, 1, 14, 1, 20, 1) + (15,) * 50,
    )
    assert game.execute(Strike("dog", "tiger_claws")).status is ResultStatus.REJECTED
    assert game.execute(TigerStance()).status is ResultStatus.COMPLETED
    assert {option.attack_id for option in game.options().strikes} == {"fist", "tiger_claws"}
    assert game.execute(Step(Position(2, 1))).status is ResultStatus.COMPLETED
    started = game.execute(FlurryOfBlows(PairedStrikeSelection("dog", "tiger_claws")))
    assert started.status is ResultStatus.PAUSED
    game, events = _settle(game, save_path=tmp_path / "flurry-second.json")
    strikes = [event.check for event in (started.events + tuple(events)) if event.kind == "strike"]
    assert any(check is not None and check.map_penalty == -4 for check in strikes)
    assert game._state.creatures["dog"].hp == 2

    assert game.inspect().turn_actor_id == "dog"
    assert game.execute(EndTurn()).status is ResultStatus.COMPLETED
    assert game.inspect().turn_actor_id == "monk"
    assert game.execute(Strike("dog", "tiger_claws")).status is ResultStatus.PAUSED
    game, _ = _settle(game)
    assert game.inspect().winner_team == "blue"
    assert not game._state.martial_stances
    final = tmp_path / "tiger-victory.json"
    game.save(final)
    assert Encounter.load(final).inspect().winner_team == "blue"


def test_tiger_step_uses_traversed_squares_and_effective_speed() -> None:
    game = _start_monk("w5_tiger_stance_vs_guard_dog", (20, 1) + (15,) * 30)
    assert game.execute(TigerStance()).status is ResultStatus.COMPLETED
    path = (Position(2, 2), Position(3, 2))
    assert game.execute(Step(path[-1], path)).status is ResultStatus.COMPLETED
    assert game._state.creatures["monk"].position == Position(3, 2)

    slowed = _start_monk("w5_tiger_stance_vs_guard_dog", (20, 1) + (15,) * 30)
    assert slowed.execute(TigerStance()).status is ResultStatus.COMPLETED
    slowed._state.condition_effects.append(ActiveConditionEffect(
        "review-speed-penalty", "speed_penalty", "dog", "monk", 15,
        EffectExpiration("dog", "end", 2),
    ))
    assert slowed.effective_speed_ft("monk") == 15
    before = slowed.inspect()
    assert slowed.execute(Step(path[-1], path)).status is ResultStatus.REJECTED
    assert slowed.inspect() == before
    assert slowed.execute(Step(Position(2, 1))).status is ResultStatus.COMPLETED


def test_wolf_unarmed_trip_critical_failure_has_no_weapon_drop_choice(tmp_path: Path) -> None:
    sheet = content.get_definition("monk_wolf_stance_level_1")
    assert "Wolf Stance" in sheet.feats and "Monastic Weaponry" not in sheet.feats
    assert not any(attack.item_id == "kama" for attack in sheet.attacks)
    game = _start_monk("w5_wolf_stance_vs_guard_dog", (20, 1, 1, 1, 1) + (15,) * 20)
    game._state.creatures["monk"].hero_points = 0
    assert game.execute(WolfStance()).status is ResultStatus.COMPLETED
    # The original fixture does not flank. Move only the allied participant
    # to the opposite side, leaving the printed Wolf grant untouched.
    game._state.creatures["monk"].position = Position(3, 2)
    game._state.creatures["flanker"].position = Position(5, 2)
    result = game.execute(Trip("dog", maneuver_attack_id="wolf_jaws"))
    assert result.status is ResultStatus.COMPLETED
    assert game._state.creatures["monk"].prone
    assert game.inspect().choice is None
    path = tmp_path / "wolf-trip-critical-failure.json"
    game.save(path)
    assert Encounter.load(path).inspect() == game.inspect()


def test_wolf_off_guard_precision_does_not_enable_unflanked_jaws_trip() -> None:
    game = _start_monk("w5_wolf_stance_vs_guard_dog", (20, 1, 1, 20, 3, 20, 1) + (15,) * 30)
    game._state.creatures["monk"].hero_points = 0
    game._state.creatures["monk"].position = Position(3, 2)
    assert game.execute(WolfStance()).status is ResultStatus.COMPLETED
    assert game.execute(Trip("dog")).status is ResultStatus.COMPLETED
    assert game._state.creatures["dog"].prone
    before = game.inspect()
    assert game.execute(Trip("dog", maneuver_attack_id="wolf_jaws")).status is ResultStatus.REJECTED
    assert game.inspect() == before
    result = game.execute(Strike("dog", "wolf_jaws"))
    game, events = _settle(game)
    damage_events = [e for e in result.events + tuple(events) if e.kind == "damage"]
    assert damage_events
    assert any(
        component.source == "wolf_stance_precision" and "precision" in component.tags
        for component in damage_events[-1].damage.components
    )


def test_tiger_bleed_choice_keeps_saved_flurry_continuation(monkeypatch, tmp_path: Path) -> None:
    dog = replace(content.GUARD_DOG, definition_id="w5_review_tough_dog", hp=30)
    monkeypatch.setattr(content, "_STAGED_CREATURES", MappingProxyType({
        **content._STAGED_CREATURES, dog.definition_id: dog,
    }))
    setup = EncounterSetup(
        "w5_review_tiger_existing_bleed", "Tiger versus existing bleed", 5, 3,
        (
            CreaturePlacement("monk", "monk_tiger_stance_level_1", "Tiger Monk", "blue", Position(1, 1)),
            CreaturePlacement("wizard", "wizard_battle_magic_level_1_staged", "Wizard", "blue", Position(0, 0)),
            CreaturePlacement("dog", dog.definition_id, "Dog", "red", Position(2, 1)),
        ),
    )
    monkeypatch.setattr(content, "_STAGED_SETUPS", MappingProxyType({
        **content._STAGED_SETUPS, setup.setup_id: setup,
    }))
    game = Encounter.start(setup, rolls=(20, 1, 1, 20, 4, 14, 1, 2, 15) + (15,) * 30)
    game, _ = _settle(game)
    assert game.inspect().turn_actor_id == "monk"
    game._state.creatures["monk"].hero_points = 0
    assert game.execute(TigerStance()).status is ResultStatus.COMPLETED
    game._state.persistent_effects.append(PersistentDamageEffect(
        "existing-bleed", "wizard", "dog", "gouging_claw", "bleed", (), 2, 60,
    ))
    result = game.execute(FlurryOfBlows(PairedStrikeSelection("dog", "tiger_claws")))
    assert result.status is ResultStatus.PAUSED
    choice = game.inspect().choice
    assert choice is not None and {o.option_id for o in choice.options} == {"existing", "incoming"}
    path = tmp_path / "tiger-bleed-flurry.json"
    game.save(path)
    forged = json.loads(path.read_text())
    forged["state"]["persistent_effects"] = []
    forged_path = tmp_path / "forged-bleed-choice.json"
    forged_path.write_text(json.dumps(forged))
    with pytest.raises(ValueError):
        Encounter.load(forged_path)
    dropped_parent = json.loads(path.read_text())
    dropped_parent["state"]["pending_choice"]["continuation"]["parent_continuation"] = None
    forged_path.write_text(json.dumps(dropped_parent))
    with pytest.raises(ValueError):
        Encounter.load(forged_path)
    game = Encounter.load(path)
    choice = game.inspect().choice
    assert choice is not None
    resolved = game.choose(choice.choice_id, "incoming", choice.owner_actor_id)
    assert resolved.status is ResultStatus.PAUSED
    assert len(game._state.persistent_effects) == 1
    assert game._state.persistent_effects[0].dice == (4,)
    choice = game.inspect().choice
    assert choice is not None and any(
        (s := _decode_selection(o.option_id)) is not None and s.attack_id == "tiger_claws"
        for o in choice.options
    )
    game, events = _settle(game, save_path=path)
    assert any(e.kind == "paired_strike_complete" for e in events)
    for _ in range(3):
        if game.inspect().turn_actor_id == "dog":
            break
        assert game.execute(EndTurn()).status is ResultStatus.COMPLETED
    else:
        raise AssertionError("bleeding target's turn did not arrive")
    before_hp = game._state.creatures["dog"].hp
    assert game.execute(EndTurn()).status is ResultStatus.COMPLETED
    assert game._state.creatures["dog"].hp == before_hp - 2
    assert not game._state.persistent_effects
    game.save(path)
    loaded = Encounter.load(path)
    assert loaded._state.creatures["dog"].hp == before_hp - 2


def test_tiger_saved_bleed_choice_preserves_justice_retaliation(monkeypatch, tmp_path: Path) -> None:
    dog = replace(content.GUARD_DOG, definition_id="w5_review_justice_dog", hp=30)
    monkeypatch.setattr(content, "_STAGED_CREATURES", MappingProxyType({
        **content._STAGED_CREATURES,
        dog.definition_id: dog,
        JUSTICE_CHAMPION.definition_id: JUSTICE_CHAMPION,
    }))
    setup = EncounterSetup(
        "w5_review_tiger_justice_bleed", "Tiger bleed through Justice", 5, 4,
        (
            CreaturePlacement("monk", "monk_tiger_stance_level_1", "Monk", "red", Position(1, 1)),
            CreaturePlacement("wizard", "wizard_battle_magic_level_1_staged", "Wizard", "red", Position(0, 0)),
            CreaturePlacement("dog", dog.definition_id, "Dog", "blue", Position(2, 1)),
            CreaturePlacement("champion", JUSTICE_CHAMPION.definition_id, "Champion", "blue", Position(2, 2)),
        ),
    )
    monkeypatch.setattr(content, "_STAGED_SETUPS", MappingProxyType({
        **content._STAGED_SETUPS, setup.setup_id: setup,
    }))
    game = Encounter.start(setup, rolls=(20, 1, 1, 1, 20, 4, 15, 1) + (15,) * 30)
    game, _ = _settle(game)
    assert game.inspect().turn_actor_id == "monk"
    game._state.creatures["monk"].hero_points = 0
    game._state.creatures["champion"].hero_points = 0
    assert game.execute(TigerStance()).status is ResultStatus.COMPLETED
    game._state.persistent_effects.append(PersistentDamageEffect(
        "existing-bleed", "wizard", "dog", "gouging_claw", "bleed", (), 2, 60,
    ))
    assert game.execute(Strike("dog", "tiger_claws")).status is ResultStatus.PAUSED
    choice = game.inspect().choice
    assert choice is not None and choice.kind == "reaction"
    protected = game.choose(choice.choice_id, "accept", choice.owner_actor_id)
    assert protected.status is ResultStatus.PAUSED
    assert any(e.kind == "retributive_strike_protection" for e in protected.events)
    choice = game.inspect().choice
    assert choice is not None and {o.option_id for o in choice.options} == {"existing", "incoming"}
    saved = tmp_path / "tiger-justice-bleed.json"
    game.save(saved)
    game = Encounter.load(saved)
    choice = game.inspect().choice
    assert choice is not None
    resolved = game.choose(choice.choice_id, "incoming", choice.owner_actor_id)
    game, extra = _settle(game)
    assert any(e.kind == "retributive_strike" for e in resolved.events + tuple(extra))
    assert any(e.kind == "strike" and e.actor_id == "champion" for e in resolved.events + tuple(extra))


def test_tiger_critical_needs_post_mitigation_damage_and_bleedable_target(monkeypatch) -> None:
    immune = replace(
        content.GUARD_DOG, definition_id="w5_review_slashing_immune", hp=30,
        damage_defenses=(DamageDefense("immunity", "slashing", source="review immunity"),),
    )
    monkeypatch.setattr(content, "_STAGED_CREATURES", MappingProxyType({
        **content._STAGED_CREATURES, immune.definition_id: immune,
        SKELETON_GUARD.definition.definition_id: SKELETON_GUARD.definition,
    }))
    for name, enemy_id in (
        ("immune", immune.definition_id),
        ("undead", "skeleton_guard_mc3193"),
    ):
        setup = EncounterSetup(
            f"w5_review_tiger_{name}", f"Tiger versus {name}", 4, 3,
            (
                CreaturePlacement("monk", "monk_tiger_stance_level_1", "Tiger Monk", "blue", Position(1, 1)),
                CreaturePlacement("enemy", enemy_id, "Enemy", "red", Position(2, 1)),
            ),
        )
        monkeypatch.setattr(content, "_STAGED_SETUPS", MappingProxyType({
            **content._STAGED_SETUPS, setup.setup_id: setup,
        }))
        game = Encounter.start(setup, rolls=(20, 1, 20, 5) + (15,) * 20)
        game, _ = _settle(game)
        assert game.inspect().turn_actor_id == "monk"
        game._state.creatures["monk"].hero_points = 0
        assert game.execute(TigerStance()).status is ResultStatus.COMPLETED
        result = game.execute(Strike("enemy", "tiger_claws"))
        assert result.status is ResultStatus.COMPLETED
        assert not game._state.persistent_effects
        assert not any(e.kind == "persistent_applied" for e in result.events)


def test_tiger_terminal_uses_numbered_stance_and_step_choices() -> None:
    transcript = BoundedTranscript(max_lines=90, max_chars=14_000)
    menu = {"text": "", "prompt": ""}
    actions = iter(("Tiger Stance", "Step", "Quit"))

    def output(line: str) -> None:
        transcript.append(line)
        if line.startswith("1. "):
            menu["text"] = line
        if line.endswith(":"):
            menu["prompt"] = line

    def number_containing(label: str) -> str:
        for row in menu["text"].splitlines():
            match = re.match(r"(\d+)\.\s+(.*)", row)
            if match and label in match.group(2):
                return match.group(1)
        raise AssertionError(f"missing {label!r} from {menu['text']!r}")

    def answer() -> str:
        prompt = menu["prompt"]
        if prompt == "Choice:":
            return number_containing(next(actions))
        if prompt == "Choice prompt action:":
            return "2"
        if prompt == "Choice option number:":
            return number_containing("Keep")
        if prompt.startswith("Tiger Step path"):
            return "C3 D3"
        raise AssertionError(f"unexpected prompt {prompt!r}")

    assert run_terminal(
        setup=content.get_setup("w5_tiger_stance_vs_guard_dog"),
        rolls=(20, 1) + (15,) * 30,
        input_fn=BoundedInput(answer, max_calls=18), output_fn=output,
    ) == 0
    rendered = "\n".join(transcript)
    assert "enters Tiger Stance" in rendered and "moved to D3" in rendered


def test_wolf_terminal_uses_numbered_stance_choice() -> None:
    transcript = BoundedTranscript(max_lines=70, max_chars=12_000)
    menu = {"text": "", "prompt": ""}
    actions = iter(("Wolf Stance", "Quit"))

    def output(line: str) -> None:
        transcript.append(line)
        if line.startswith("1. "):
            menu["text"] = line
        if line.endswith(":"):
            menu["prompt"] = line

    def answer() -> str:
        if menu["prompt"] == "Choice:":
            label = next(actions)
            for row in menu["text"].splitlines():
                match = re.match(r"(\d+)\.\s+(.*)", row)
                if match and label in match.group(2):
                    return match.group(1)
            raise AssertionError(f"missing {label!r} from terminal menu")
        if menu["prompt"] == "Choice prompt action:":
            return "2"
        if menu["prompt"] == "Choice option number:":
            return "1"
        raise AssertionError(f"unexpected prompt {menu['prompt']!r}")

    assert run_terminal(
        setup=content.get_setup("w5_wolf_stance_vs_guard_dog"),
        rolls=(20, 1, 1) + (15,) * 20,
        input_fn=BoundedInput(answer, max_calls=15), output_fn=output,
    ) == 0
    assert "enters Wolf Stance" in "\n".join(transcript)


def test_tiger_option_generation_is_bounded() -> None:
    game = _start_monk("w5_tiger_stance_vs_guard_dog", (20, 1) + (15,) * 20)
    assert game.execute(TigerStance()).status is ResultStatus.COMPLETED
    start = perf_counter()
    for _ in range(100):
        assert game.options().step_destinations
    assert perf_counter() - start < 2
