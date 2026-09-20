"""Public W3 Fighter Strike-rider checks.

Sources checked 2026-09-20: Snagging Strike (Player Core p. 141,
https://2e.aonprd.com/Feats.aspx?ID=4773), Combat Grab (Player Core p. 141,
https://2e.aonprd.com/Feats.aspx?ID=4780), and Brutish Shove (Player Core
p. 141, https://2e.aonprd.com/Feats.aspx?ID=4779).  The Brutish Shove sheet
uses the Player Core p. 278 Greatsword (https://2e.aonprd.com/Weapons.aspx?ID=379);
its automatic Shove uses Player Core p. 235 (https://2e.aonprd.com/Actions.aspx?ID=2380).
"""

from __future__ import annotations

from pathlib import Path
from dataclasses import replace
from types import MappingProxyType

from pf2e import EndTurn, Stride, Strike
from pf2e.content import get_definition, get_setup
from pf2e.encounter import Encounter
from pf2e.fighter import BrutishShove, CombatGrab, SnaggingStrike
from pf2e.model import CreaturePlacement, EncounterSetup, Position, ResultStatus


def _settle(game: Encounter) -> None:
    for _ in range(10):
        choice = game.inspect().choice
        if choice is None:
            return
        option = "keep" if any(item.option_id == "keep" for item in choice.options) else choice.options[0].option_id
        assert game.choose(choice.choice_id, option, choice.owner_actor_id).status in {ResultStatus.PAUSED, ResultStatus.COMPLETED}
    raise AssertionError("choice did not settle")


def test_snagging_strike_uses_free_hand_hit_and_live_reach_expiry(tmp_path: Path) -> None:
    game = Encounter.start(get_setup("staged_fighter_level_1_snagging_strike"), rolls=(20, 1, 12, 1))
    _settle(game)
    assert "snagging_strike" in game.options().available_actions
    paused = game.execute(SnaggingStrike("dog", "longsword"))
    assert paused.status is ResultStatus.PAUSED
    save_path = tmp_path / "snagging-strike.json"
    game.save(save_path)
    game = Encounter.load(save_path)
    _settle(game)
    assert any(effect.effect_id.startswith("snagging_strike:") and effect.kind == "off_guard" for effect in game._state.condition_effects)
    # Moving the target is a live reach boundary, not an eventually-expiring
    # cosmetic marker. The dog can move once its own turn arrives.
    assert game.execute(EndTurn()).status is ResultStatus.COMPLETED
    assert game.execute(Stride((Position(3, 1),))).status is ResultStatus.PAUSED
    choice = game.inspect().choice
    assert choice is not None and choice.kind == "reaction"
    assert game.choose(choice.choice_id, "decline", choice.owner_actor_id).status is ResultStatus.COMPLETED
    assert not any(effect.effect_id.startswith("snagging_strike:") for effect in game._state.condition_effects)


def test_combat_grab_is_press_and_persists_its_escape_condition(tmp_path: Path) -> None:
    game = Encounter.start(get_setup("staged_fighter_level_2_combat_grab"), rolls=(20, 1, 12, 1, 12, 1))
    _settle(game)
    rejected = game.execute(CombatGrab("dog", "longsword"))
    assert rejected.status is ResultStatus.REJECTED
    assert game.execute(Strike("dog", "longsword")).status is ResultStatus.PAUSED
    _settle(game)
    assert game.execute(CombatGrab("dog", "longsword")).status is ResultStatus.PAUSED
    _settle(game)
    effect = next(effect for effect in game._state.condition_effects if effect.effect_id.startswith("combat_grab:"))
    assert effect.kind == "grabbed" and effect.dc == 18
    save_path = tmp_path / "combat-grab.json"
    game.save(save_path)
    loaded = Encounter.load(save_path)
    assert any(effect.effect_id.startswith("combat_grab:") for effect in loaded._state.condition_effects)


def test_brutish_shove_keeps_press_failure_and_critical_shove_results_distinct() -> None:
    game = Encounter.start(get_setup("staged_fighter_level_2_brutish_shove"), rolls=(20, 1, 12, 1, 2))
    _settle(game)
    assert game.execute(Strike("dog", "greatsword")).status is ResultStatus.PAUSED
    _settle(game)
    # A failure applies Brutish Shove's limited failure effect, without moving
    # the target. The chosen destination survives only for a successful Shove.
    result = game.execute(BrutishShove("dog", "greatsword", Position(3, 1)))
    assert result.status is ResultStatus.PAUSED
    _settle(game)
    dog = game._state.creatures["dog"]
    assert dog.position == Position(2, 1)
    assert any(effect.effect_id.startswith("brutish_shove:") for effect in game._state.condition_effects)

    critical = Encounter.start(
        get_setup("staged_fighter_level_2_brutish_shove"), rolls=(20, 1, 12, 1, 20, 1),
    )
    _settle(critical)
    assert critical.execute(Strike("dog", "greatsword")).status is ResultStatus.PAUSED
    _settle(critical)
    assert critical.execute(BrutishShove("dog", "greatsword", Position(3, 1), follow=True)).status is ResultStatus.PAUSED
    _settle(critical)
    assert critical._state.creatures["dog"].position == Position(4, 1)
    assert critical._state.creatures["fighter"].position == Position(3, 1)


def test_brutish_shove_rejects_sideways_and_critical_failure_has_no_failure_effect() -> None:
    sideways = Encounter.start(
        get_setup("staged_fighter_level_2_brutish_shove"), rolls=(20, 1, 12, 1),
    )
    _settle(sideways)
    assert sideways.execute(Strike("dog", "greatsword")).status is ResultStatus.PAUSED
    _settle(sideways)
    rejected = sideways.execute(BrutishShove("dog", "greatsword", Position(2, 2)))
    assert rejected.status is ResultStatus.REJECTED

    critical_failure = Encounter.start(
        get_setup("staged_fighter_level_2_brutish_shove"), rolls=(20, 1, 12, 1, 1),
    )
    _settle(critical_failure)
    assert critical_failure.execute(Strike("dog", "greatsword")).status is ResultStatus.PAUSED
    _settle(critical_failure)
    assert critical_failure.execute(BrutishShove("dog", "greatsword", Position(3, 1))).status is ResultStatus.PAUSED
    _settle(critical_failure)
    assert not any(effect.effect_id.startswith("brutish_shove:") for effect in critical_failure._state.condition_effects)


def test_brutish_shove_records_the_actual_greatsword_sheet_and_selected_failure_effect_on_larger_hit(
    monkeypatch,
) -> None:
    import pf2e.content as content

    definition = get_definition("fighter_m_level_2_brutish_shove")
    assert definition.held_items == ("greatsword",)
    assert {(attack.attack_id, attack.hands_required) for attack in definition.attacks} >= {("greatsword", 2)}
    assert ("greatsword", 2) in definition.carried_item_bulk
    assert not any("Longsword is versatile" in note for note in definition.sheet_notes)
    assert "Starting money remaining after the listed gear: 5 gp." in definition.sheet_notes

    large_dog = replace(content.GUARD_DOG, definition_id="w3_large_guard_dog", size="large")
    monkeypatch.setattr(content, "CREATURES", MappingProxyType({**content.CREATURES, large_dog.definition_id: large_dog}))
    setup = EncounterSetup(
        "w3_brutish_large_failure_effect", "Brutish Shove larger target failure effect", 5, 3,
        (
            CreaturePlacement("fighter", definition.definition_id, "Fighter", "blue", Position(1, 1)),
            CreaturePlacement("dog", large_dog.definition_id, "Large Guard Dog", "red", Position(2, 1)),
        ),
    )
    monkeypatch.setattr(content, "_STAGED_SETUPS", content._STAGED_SETUPS | {setup.setup_id: setup})
    game = Encounter.start(setup, rolls=(20, 1, 12, 1, 12, 1))
    _settle(game)
    assert game.execute(Strike("dog", "greatsword")).status is ResultStatus.PAUSED
    _settle(game)
    assert game.execute(BrutishShove("dog", "greatsword", Position(3, 1), failure_effect=True)).status is ResultStatus.PAUSED
    _settle(game)
    assert any(effect.effect_id.startswith("brutish_shove:") for effect in game._state.condition_effects)
    assert game._state.creatures["dog"].position == Position(2, 1)
