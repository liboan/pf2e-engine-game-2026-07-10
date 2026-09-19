"""Level-2 horizontal progression definitions and typed rule boundaries.

Rules checked 2026-09-18:

* Rogue: https://2e.aonprd.com/Classes.aspx?ID=37
* Mobility: https://2e.aonprd.com/Feats.aspx?ID=4926
* Swashbuckler: https://2e.aonprd.com/Classes.aspx?ID=63
* Long Jump: https://2e.aonprd.com/Actions.aspx?ID=2378
* Quick Jump: https://2e.aonprd.com/Feats.aspx?ID=5196
* Tumble Behind: https://2e.aonprd.com/Feats.aspx?ID=6142
"""

from types import MappingProxyType, SimpleNamespace

import pytest

import pf2e.content as content
from pf2e.l2_horizontal_content import (
    BRAGGART_SWASHBUCKLER_LEVEL_2,
    BRAGGART_SWASHBUCKLER_LEVEL_2_TUMBLE_BEHIND_SETUP,
    L2_HORIZONTAL_DEFINITIONS,
    L2_HORIZONTAL_SETUPS,
    THIEF_ROGUE_LEVEL_2,
    THIEF_ROGUE_LEVEL_2_MOBILITY_SETUP,
)
from pf2e.encounter import Encounter
from pf2e.model import (
    ActiveConditionEffect,
    CreaturePlacement,
    EndTurn,
    EffectExpiration,
    EncounterSetup,
    Position,
    ResultStatus,
    Strike,
    Stride,
)
from pf2e.movement_progression import (
    TumbleBehindExposure,
    consume_tumble_behind_on_attack,
    expire_tumble_behind_exposures,
    grant_tumble_behind_exposure,
    mobility_applies,
    tumble_behind_applies,
)
from pf2e.skill_actions import Escape, QuickJump, Trip, TumbleThrough
from pf2e.swashbuckler import ConfidentFinisher
from pf2e.terminal import run_terminal
from terminal_test_helpers import BoundedInput, BoundedTranscript


def _stage_l2_definitions(
    monkeypatch: pytest.MonkeyPatch, *setups: EncounterSetup
) -> None:
    monkeypatch.setattr(
        content,
        "_STAGED_CREATURES",
        MappingProxyType({**content._STAGED_CREATURES, **L2_HORIZONTAL_DEFINITIONS}),
    )
    if setups:
        monkeypatch.setattr(
            content,
            "_STAGED_SETUPS",
            MappingProxyType(
                {**content._STAGED_SETUPS, **{setup.setup_id: setup for setup in setups}}
            ),
        )


def _settle_initiative(game: Encounter) -> None:
    for _ in range(8):
        choice = game.inspect().choice
        if choice is None:
            return
        option_id = "keep" if any(option.option_id == "keep" for option in choice.options) else choice.options[0].option_id
        assert game.choose(choice.choice_id, option_id, choice.owner_actor_id).status in {
            ResultStatus.PAUSED, ResultStatus.COMPLETED,
        }
    raise AssertionError("initiative did not settle")


def _choose(game: Encounter, option_id: str):
    choice = game.inspect().choice
    assert choice is not None
    return game.choose(choice.choice_id, option_id, choice.owner_actor_id)


def test_l2_thief_sheet_advances_hp_statistics_mobility_and_athletics() -> None:
    sheet = THIEF_ROGUE_LEVEL_2
    assert sheet.level == 2
    assert (sheet.hp, sheet.ac, sheet.perception, sheet.class_dc) == (28, 19, 6, 18)
    assert "Mobility" in sheet.feats and "Quick Jump" in sheet.feats
    assert dict((name, (rank, modifier)) for name, rank, modifier in sheet.skills)["athletics"] == ("expert", 8)
    assert dict((name, modifier) for name, _, modifier in sheet.saves) == {
        "fortitude": 6, "reflex": 10, "will": 6,
    }
    assert [attack.modifier for attack in sheet.attacks] == [8, 8]
    # The l1 damage features remain on the selected representative sheet.
    assert {"sneak_attack", "surprise_attack", "rogue_racket_thief"} <= set(sheet.abilities)
    assert "Nimble Dodge" in sheet.feats
    assert L2_HORIZONTAL_SETUPS[THIEF_ROGUE_LEVEL_2_MOBILITY_SETUP.setup_id] is THIEF_ROGUE_LEVEL_2_MOBILITY_SETUP


def test_l2_braggart_sheet_advances_hp_statistics_tumble_behind_and_quick_jump() -> None:
    sheet = BRAGGART_SWASHBUCKLER_LEVEL_2
    assert sheet.level == 2
    assert (sheet.hp, sheet.ac, sheet.perception, sheet.class_dc) == (30, 19, 6, 18)
    assert {"Tumble Behind", "Quick Jump", "Flying Blade"} <= set(sheet.feats)
    assert dict((name, modifier) for name, _, modifier in sheet.skills)["acrobatics"] == 8
    assert dict((name, modifier) for name, _, modifier in sheet.saves) == {
        "fortitude": 5, "reflex": 10, "will": 6,
    }
    assert [attack.modifier for attack in sheet.attacks] == [8, 8]
    assert {"swashbuckler", "swashbuckler_braggart", "precise_strike", "stylish_combatant"} <= set(sheet.abilities)
    assert L2_HORIZONTAL_SETUPS[BRAGGART_SWASHBUCKLER_LEVEL_2_TUMBLE_BEHIND_SETUP.setup_id] is BRAGGART_SWASHBUCKLER_LEVEL_2_TUMBLE_BEHIND_SETUP


def test_mobility_uses_validated_actual_cost_and_preserves_odd_speed_half_boundary(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _stage_l2_definitions(monkeypatch)
    actor = SimpleNamespace(definition_id=THIEF_ROGUE_LEVEL_2.definition_id)
    assert mobility_applies(actor, actual_speed_feet=25, path_cost_feet=10, action_kind="Stride")
    assert not mobility_applies(actor, actual_speed_feet=25, path_cost_feet=15, action_kind="Stride")
    assert not mobility_applies(actor, actual_speed_feet=25, path_cost_feet=10, action_kind="Quick Jump")
    assert not mobility_applies(actor, actual_speed_feet=25, path_cost_feet=10, action_kind="Climb")


def test_tumble_behind_is_attacker_relative_one_use_and_not_feint() -> None:
    effects = grant_tumble_behind_exposure(
        (), source_actor_id="braggart", target_actor_id="dog", current_source_end_count=0
    )
    effect = effects[0]
    assert effect.expiration == EffectExpiration("braggart", "end", 1)
    assert tumble_behind_applies(effects, attacker_id="braggart", target_id="dog", actor_end_counts={"braggart": 0})
    # The selected thrown attack is deliberately eligible: no melee trait is
    # accepted by this distinct Tumble Behind API.
    consumed = consume_tumble_behind_on_attack(
        effects, attacker_id="braggart", target_id="dog", actor_end_counts={"braggart": 0}
    )
    assert consumed == ()
    assert not tumble_behind_applies(consumed, attacker_id="braggart", target_id="dog", actor_end_counts={"braggart": 0})
    assert not tumble_behind_applies(effects, attacker_id="other", target_id="dog", actor_end_counts={"braggart": 0})
    assert not tumble_behind_applies(effects, attacker_id="braggart", target_id="other", actor_end_counts={"braggart": 0})
    two_targets = grant_tumble_behind_exposure(
        effects, source_actor_id="braggart", target_actor_id="other", current_source_end_count=0
    )
    # An intervening attack on a third target ends every live source exposure;
    # it cannot preserve an opening for a later thrown Strike.
    assert consume_tumble_behind_on_attack(
        two_targets, attacker_id="braggart", target_id="third", actor_end_counts={"braggart": 0}
    ) == ()


def test_tumble_behind_expires_at_source_turn_end_and_rejects_invalid_records() -> None:
    effects = grant_tumble_behind_exposure(
        (), source_actor_id="braggart", target_actor_id="dog", current_source_end_count=4
    )
    assert expire_tumble_behind_exposures(
        effects, actor_id="dog", actor_end_counts={"braggart": 4, "dog": 1}
    ) == effects
    assert expire_tumble_behind_exposures(
        effects, actor_id="braggart", actor_end_counts={"braggart": 5, "dog": 1}
    ) == ()
    with pytest.raises(ValueError, match="source and target"):
        TumbleBehindExposure(
            "bad", "braggart", "braggart", EffectExpiration("braggart", "end", 1)
        )


def test_l2_thief_mobility_suppresses_qualifying_reaction_but_longer_stride_offers_it(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    setup = EncounterSetup(
        "test_l2_thief_mobility_reactive_reach",
        "Test level-2 Thief Mobility through reactive reach",
        5,
        3,
        (
            CreaturePlacement("thief", THIEF_ROGUE_LEVEL_2.definition_id, "Thief", "blue", Position(0, 0)),
            CreaturePlacement("fighter", content.MELEE_FIGHTER_M.definition_id, "Fighter", "red", Position(1, 1)),
        ),
    )
    _stage_l2_definitions(monkeypatch, setup)
    game = Encounter.start(setup, rolls=(20, 1, 20, 1, 1, 1))
    _settle_initiative(game)
    short = game.execute(Stride((Position(1, 0), Position(2, 0))))
    assert short.status is ResultStatus.COMPLETED
    assert game.inspect().choice is None
    assert game._state.creatures["thief"].position == Position(2, 0)

    # Build a fresh turn so the long path has full actions and the reactive
    # fighter's reaction.  It costs 15 ft at a 25-ft Speed, over half Speed.
    game = Encounter.start(setup, rolls=(20, 1, 20, 1, 1, 1))
    _settle_initiative(game)
    long = game.execute(Stride((Position(1, 0), Position(2, 0), Position(3, 0))))
    assert long.status is ResultStatus.PAUSED
    choice = game.inspect().choice
    assert choice is not None and choice.kind == "reaction" and choice.owner_actor_id == "fighter"


def test_l2_thief_mobility_uses_actual_diagonal_stride_cost_before_reactions(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    setup = EncounterSetup(
        "test_l2_thief_mobility_diagonal_cost",
        "Test level-2 Thief Mobility diagonal actual-cost threshold",
        5,
        3,
        (
            CreaturePlacement("thief", THIEF_ROGUE_LEVEL_2.definition_id, "Thief", "blue", Position(1, 1)),
            CreaturePlacement("fighter", content.MELEE_FIGHTER_M.definition_id, "Fighter", "red", Position(1, 0)),
        ),
    )
    _stage_l2_definitions(monkeypatch, setup)
    # One diagonal plus one straight square is a validated 10-foot path, so
    # Mobility suppresses Reactive Strike despite actually departing reach.
    game = Encounter.start(setup, rolls=(20, 1))
    _settle_initiative(game)
    short = game.execute(Stride((Position(2, 2), Position(3, 2))))
    assert short.status is ResultStatus.COMPLETED
    assert game.inspect().choice is None
    assert game._state.creatures["thief"].position == Position(3, 2)

    # Adding the third square makes the same path cost 15 feet at 25 Speed,
    # exceeding half Speed after the core's diagonal path-cost validation.
    game = Encounter.start(setup, rolls=(20, 1))
    _settle_initiative(game)
    long = game.execute(Stride((Position(2, 2), Position(3, 2), Position(4, 2))))
    assert long.status is ResultStatus.PAUSED
    choice = game.inspect().choice
    assert choice is not None and choice.kind == "reaction" and choice.owner_actor_id == "fighter"


def test_l2_braggart_failed_tumble_has_no_tumble_behind_exposure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    setup = EncounterSetup(
        "test_l2_braggart_failed_tumble_behind",
        "Test level-2 Braggart failed Tumble Through has no exposure",
        4,
        3,
        (
            CreaturePlacement("braggart", BRAGGART_SWASHBUCKLER_LEVEL_2.definition_id, "Braggart", "blue", Position(0, 1)),
            CreaturePlacement("dog", "guard_dog_mc2924", "Dog", "red", Position(1, 1)),
        ),
    )
    _stage_l2_definitions(monkeypatch, setup)
    game = Encounter.start(setup, rolls=(20, 1, 4))
    _settle_initiative(game)
    assert game.execute(TumbleThrough((Position(1, 1), Position(2, 1)))).status is ResultStatus.PAUSED
    resolved = _choose(game, "keep")
    assert any(event.kind == "tumble_through_failed" for event in resolved.events)
    assert game._state.tumble_behind_exposures == []
    assert game._state.feint_off_guard_effects == []


def test_l2_braggart_missed_next_strike_consumes_tumble_behind_exposure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    setup = EncounterSetup(
        "test_l2_braggart_missed_strike_consumes_exposure",
        "Test level-2 Braggart missed Strike consumes Tumble Behind",
        4,
        3,
        (
            CreaturePlacement("braggart", BRAGGART_SWASHBUCKLER_LEVEL_2.definition_id, "Braggart", "blue", Position(0, 1)),
            CreaturePlacement("dog", "guard_dog_mc2924", "Dog", "red", Position(1, 1)),
        ),
    )
    _stage_l2_definitions(monkeypatch, setup)
    game = Encounter.start(setup, rolls=(20, 1, 12, 2))
    _settle_initiative(game)
    assert game.execute(TumbleThrough((Position(1, 1), Position(2, 1)))).status is ResultStatus.PAUSED
    assert _choose(game, "keep").status is ResultStatus.COMPLETED
    assert game._state.tumble_behind_exposures
    started = game.execute(Strike("dog", "dagger"))
    assert started.status is ResultStatus.PAUSED
    assert game._state.tumble_behind_exposures == []
    resolved = _choose(game, "keep")
    attack = next(event.check for event in resolved.events if event.kind == "strike")
    assert attack is not None and attack.degree.name == "FAILURE"


def test_l2_braggart_live_tumble_behind_exposure_expires_at_end_turn(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    setup = EncounterSetup(
        "test_l2_braggart_live_tumble_behind_expiry",
        "Test level-2 Braggart live Tumble Behind turn expiry",
        4,
        3,
        (
            CreaturePlacement("braggart", BRAGGART_SWASHBUCKLER_LEVEL_2.definition_id, "Braggart", "blue", Position(0, 1)),
            CreaturePlacement("dog", "guard_dog_mc2924", "Dog", "red", Position(1, 1)),
        ),
    )
    _stage_l2_definitions(monkeypatch, setup)
    game = Encounter.start(setup, rolls=(20, 1, 12))
    _settle_initiative(game)
    assert game.execute(TumbleThrough((Position(1, 1), Position(2, 1)))).status is ResultStatus.PAUSED
    assert _choose(game, "keep").status is ResultStatus.COMPLETED
    assert game._state.tumble_behind_exposures
    assert game.execute(EndTurn()).status is ResultStatus.COMPLETED
    assert game._state.actor_end_counts["braggart"] == 1
    assert game._state.tumble_behind_exposures == []
    assert game.execute(EndTurn()).status is ResultStatus.COMPLETED
    assert game._state.actor_start_counts["braggart"] == 2
    assert game._state.tumble_behind_exposures == []


def test_l2_braggart_saved_tumble_behind_consumes_on_thrown_finisher_attempt(
    monkeypatch: pytest.MonkeyPatch, tmp_path
) -> None:
    setup = EncounterSetup(
        "test_l2_braggart_tumble_behind_throw",
        "Test level-2 Braggart saved Tumble Behind thrown finisher",
        4,
        3,
        (
            CreaturePlacement("braggart", BRAGGART_SWASHBUCKLER_LEVEL_2.definition_id, "Braggart", "blue", Position(0, 1)),
            CreaturePlacement("dog", "guard_dog_mc2924", "Guard Dog", "red", Position(1, 1)),
        ),
    )
    _stage_l2_definitions(monkeypatch, setup)
    # Initiative, Acrobatics, then a thrown finisher whose +8 total reaches
    # the off-guard DC but would fail against the ordinary AC.
    game = Encounter.start(setup, rolls=(20, 1, 12, 5, 4, 1, 1))
    _settle_initiative(game)
    started = game.execute(TumbleThrough((Position(1, 1), Position(2, 1))))
    assert started.status is ResultStatus.PAUSED
    path = tmp_path / "l2-tumble-behind.json"
    game.save(path)
    restored = Encounter.load(path)
    crossed = _choose(restored, "keep")
    assert crossed.status is ResultStatus.COMPLETED
    assert len(restored._state.tumble_behind_exposures) == 1
    exposure = restored._state.tumble_behind_exposures[0]
    assert (exposure.source_actor_id, exposure.target_actor_id) == ("braggart", "dog")

    # Flying Blade makes this selected first-increment thrown finisher legal.
    finisher = restored.execute(ConfidentFinisher("dog", "dagger_thrown", item_id="braggart:dagger_1"))
    assert finisher.status is ResultStatus.PAUSED
    assert restored._state.tumble_behind_exposures == []
    resolved = _choose(restored, "keep")
    assert resolved.status is ResultStatus.PAUSED
    # The selected thrown finisher must snapshot the target-relative opening
    # before consuming it: guard dog AC 15 becomes DC 13 for this attack.
    attack = next(event.check for event in resolved.events if event.kind == "strike")
    assert attack is not None and (attack.total, attack.dc, attack.degree.name) == (13, 13, "SUCCESS")


def test_l2_braggart_intervening_trip_consumes_tumble_behind_without_changing_save_dc(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    setup = EncounterSetup(
        "test_l2_braggart_tumble_behind_trip",
        "Test level-2 Braggart intervening Trip consumes Tumble Behind",
        4,
        3,
        (
            CreaturePlacement("braggart", BRAGGART_SWASHBUCKLER_LEVEL_2.definition_id, "Braggart", "blue", Position(0, 1)),
            CreaturePlacement("dog", "guard_dog_mc2924", "Dog", "red", Position(1, 1)),
        ),
    )
    _stage_l2_definitions(monkeypatch, setup)
    game = Encounter.start(setup, rolls=(20, 1, 12, 10))
    _settle_initiative(game)
    assert game.execute(TumbleThrough((Position(1, 1), Position(2, 1)))).status is ResultStatus.PAUSED
    assert _choose(game, "keep").status is ResultStatus.COMPLETED
    assert game._state.tumble_behind_exposures
    started = game.execute(Trip("dog"))
    assert started.status is ResultStatus.PAUSED
    assert game._state.tumble_behind_exposures == []
    resolved = _choose(game, "keep")
    check = next(event.check for event in resolved.events if event.kind == "trip_check")
    assert check is not None and check.dc == 17


def test_l2_braggart_intervening_escape_attack_consumes_tumble_behind(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    setup = EncounterSetup(
        "test_l2_braggart_tumble_behind_escape",
        "Test level-2 Braggart intervening Escape consumes Tumble Behind",
        4,
        3,
        (
            CreaturePlacement("braggart", BRAGGART_SWASHBUCKLER_LEVEL_2.definition_id, "Braggart", "blue", Position(0, 1)),
            CreaturePlacement("dog", "guard_dog_mc2924", "Dog", "red", Position(1, 1)),
        ),
    )
    _stage_l2_definitions(monkeypatch, setup)
    game = Encounter.start(setup, rolls=(20, 1, 12, 10))
    _settle_initiative(game)
    assert game.execute(TumbleThrough((Position(1, 1), Position(2, 1)))).status is ResultStatus.PAUSED
    assert _choose(game, "keep").status is ResultStatus.COMPLETED
    assert game._state.tumble_behind_exposures
    game._state.condition_effects.append(ActiveConditionEffect(
        "test:grab", "grabbed", "dog", "braggart", 1,
        EffectExpiration("braggart", "end", 1), dc=17,
    ))
    started = game.execute(Escape("test:grab", "athletics"))
    assert started.status is ResultStatus.PAUSED
    assert game._state.tumble_behind_exposures == []


def test_l2_thief_quick_jump_and_complete_fight_then_a_fresh_next_scene(
    monkeypatch: pytest.MonkeyPatch, tmp_path,
) -> None:
    fight = EncounterSetup(
        "test_l2_thief_complete_fight",
        "Test level-2 Thief complete fight",
        4,
        3,
        (
            CreaturePlacement("thief", THIEF_ROGUE_LEVEL_2.definition_id, "Thief", "blue", Position(1, 1)),
            CreaturePlacement("dog", "guard_dog_mc2924", "Dog", "red", Position(2, 1)),
        ),
    )
    next_scene = EncounterSetup(
        "test_l2_thief_next_scene",
        "Test level-2 Thief next scene Quick Jump",
        6,
        3,
        (
            CreaturePlacement("thief", THIEF_ROGUE_LEVEL_2.definition_id, "Thief", "blue", Position(1, 1)),
            CreaturePlacement("dog_next", "guard_dog_mc2924", "Dog", "red", Position(5, 0)),
        ),
    )
    _stage_l2_definitions(monkeypatch, fight, next_scene)
    # The level-2 +8 short sword's critical result decisively ends the fight.
    game = Encounter.start(fight, rolls=(20, 1, 20, 4, 20, 1, 10))
    _settle_initiative(game)
    result = game.execute(Strike("dog", "shortsword"))
    assert result.status is ResultStatus.PAUSED
    result = _choose(game, "keep")
    assert result.status is ResultStatus.COMPLETED
    assert not result.inspection.in_progress and result.inspection.winner_team == "blue"

    save_path = tmp_path / "l2-thief-complete.json"
    game.save(save_path)
    next_game = Encounter.load(save_path)
    transitioned = next_game.next_encounter(next_scene)
    assert transitioned.status in {ResultStatus.PAUSED, ResultStatus.COMPLETED}
    _settle_initiative(next_game)
    # The carried L2 Rogue has the same definition and equipment in the next
    # scene, then resolves its granted skill feat through normal procedure.
    assert next_game._state.creatures["thief"].definition_id == THIEF_ROGUE_LEVEL_2.definition_id
    assert next_game._state.creatures["thief"].held_items == ["shortsword"]
    jumped = next_game.execute(QuickJump((Position(2, 1), Position(3, 1), Position(4, 1))))
    assert jumped.status is ResultStatus.PAUSED
    assert _choose(next_game, "keep").status is ResultStatus.COMPLETED
    assert next_game._state.creatures["thief"].position == Position(4, 1)


@pytest.mark.parametrize(
    ("die", "expected_x", "expected_prone"),
    (
        (20, 6, False),  # +8 = 28, rounded to 25 ft and capped by 25-ft Speed.
        (5, 3, False),   # Failure uses the normal 10-ft horizontal Leap.
        (1, 3, True),    # Critical failure makes that Leap, then lands prone.
    ),
)
def test_l2_thief_quick_jump_uses_long_jump_result_and_failure_leap(
    monkeypatch: pytest.MonkeyPatch, die: int, expected_x: int, expected_prone: bool,
) -> None:
    setup = EncounterSetup(
        f"test_l2_thief_quick_jump_long_jump_{die}",
        "Test level-2 Thief Quick Jump Long Jump result",
        7,
        3,
        (
            CreaturePlacement("thief", THIEF_ROGUE_LEVEL_2.definition_id, "Thief", "blue", Position(1, 1)),
            CreaturePlacement("dog", "guard_dog_mc2924", "Dog", "red", Position(6, 0)),
        ),
    )
    _stage_l2_definitions(monkeypatch, setup)
    game = Encounter.start(setup, rolls=(20, 1, die))
    _settle_initiative(game)
    assert game.execute(QuickJump(tuple(Position(x, 1) for x in range(2, 7)))).status is ResultStatus.PAUSED
    resolved = _choose(game, "keep")
    thief = game._state.creatures["thief"]
    assert resolved.status is ResultStatus.COMPLETED
    assert thief.position == Position(expected_x, 1) and thief.prone is expected_prone


@pytest.mark.parametrize(("die", "expected_prone"), ((5, False), (1, True)))
def test_l2_braggart_panache_speed_uses_the_normal_fifteen_foot_leap(
    monkeypatch: pytest.MonkeyPatch, die: int, expected_prone: bool,
) -> None:
    setup = EncounterSetup(
        "test_l2_braggart_panache_quick_jump_failure",
        "Test level-2 Braggart Panache Quick Jump normal Leap",
        7,
        3,
        (
            CreaturePlacement("braggart", BRAGGART_SWASHBUCKLER_LEVEL_2.definition_id, "Braggart", "blue", Position(0, 1)),
            CreaturePlacement("dog", "guard_dog_mc2924", "Dog", "red", Position(1, 1)),
        ),
    )
    _stage_l2_definitions(monkeypatch, setup)
    game = Encounter.start(setup, rolls=(20, 1, 12, die))
    _settle_initiative(game)
    assert game.execute(TumbleThrough((Position(1, 1), Position(2, 1)))).status is ResultStatus.PAUSED
    assert _choose(game, "keep").status is ResultStatus.COMPLETED
    assert game.effective_speed_ft("braggart") == 30
    assert game.execute(QuickJump((Position(3, 1), Position(4, 1), Position(5, 1)))).status is ResultStatus.PAUSED
    assert _choose(game, "keep").status is ResultStatus.COMPLETED
    assert game._state.creatures["braggart"].position == Position(5, 1)
    assert game._state.creatures["braggart"].prone is expected_prone


def test_terminal_staged_l2_thief_offers_and_plays_quick_jump(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    setup = EncounterSetup(
        "test_terminal_l2_thief_quick_jump",
        "Test terminal level-2 Thief Quick Jump",
        4,
        3,
        (
            CreaturePlacement("thief", THIEF_ROGUE_LEVEL_2.definition_id, "Thief", "blue", Position(0, 1)),
            CreaturePlacement("dog", "guard_dog_mc2924", "Dog", "red", Position(3, 0)),
        ),
    )
    _stage_l2_definitions(monkeypatch, setup)
    transcript = BoundedTranscript()
    menu = {"text": "", "prompt": "", "jumped": False}

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

    def scripted(_prompt: str) -> str:
        if menu["prompt"] == "Choice:":
            if not menu["jumped"] and "Quick Jump" in menu["text"]:
                menu["jumped"] = True
                return menu_number("Quick Jump")
            return menu_number("Quit")
        if menu["prompt"] == "Quick Jump path, in order (for example B2 C2 D2):":
            return "B2"
        if menu["prompt"] in {"Choice option number:", "Choice prompt action:"}:
            return "2"  # Keep the Athletics check.
        raise AssertionError(f"unexpected terminal prompt: {menu['prompt']!r}")

    assert run_terminal(
        setup=setup,
        rolls=(20, 1, 10),
        input_fn=BoundedInput(lambda: scripted(menu["prompt"])),
        output_fn=output,
    ) == 0
    assert "Quick Jump" in "\n".join(transcript)


def test_l2_braggart_completes_tumble_behind_thrown_finisher_fight_and_next_scene(
    monkeypatch: pytest.MonkeyPatch, tmp_path,
) -> None:
    fight = EncounterSetup(
        "test_l2_braggart_complete_fight",
        "Test level-2 Braggart complete thrown-finisher fight",
        4,
        3,
        (
            CreaturePlacement("braggart", BRAGGART_SWASHBUCKLER_LEVEL_2.definition_id, "Braggart", "blue", Position(0, 1)),
            CreaturePlacement("dog", "guard_dog_mc2924", "Dog", "red", Position(1, 1)),
        ),
    )
    next_scene = EncounterSetup(
        "test_l2_braggart_next_scene",
        "Test level-2 Braggart next scene",
        4,
        3,
        (
            CreaturePlacement("braggart", BRAGGART_SWASHBUCKLER_LEVEL_2.definition_id, "Braggart", "blue", Position(0, 1)),
            CreaturePlacement("dog_next", "guard_dog_mc2924", "Dog", "red", Position(3, 0)),
        ),
    )
    _stage_l2_definitions(monkeypatch, fight, next_scene)
    game = Encounter.start(fight, rolls=(20, 1, 12, 20, 4, 6, 6, 20, 1, 10))
    _settle_initiative(game)
    assert game.execute(TumbleThrough((Position(1, 1), Position(2, 1)))).status is ResultStatus.PAUSED
    assert _choose(game, "keep").status is ResultStatus.COMPLETED
    assert game._state.tumble_behind_exposures
    # Use the held melee dagger here so no physical item is abandoned before
    # the carried-state transition; the separate saved test covers Flying
    # Blade's thrown finisher and its item identity.
    finisher = game.execute(ConfidentFinisher("dog", "dagger", item_id="braggart:dagger_1"))
    assert finisher.status is ResultStatus.PAUSED
    for _ in range(3):
        choice = game.inspect().choice
        if choice is None or choice.kind != "attack_hero_reroll":
            break
        finisher = _choose(game, "keep")
        assert finisher.status is not ResultStatus.REJECTED, finisher.message
    assert game.inspect().choice is not None and game.inspect().choice.kind == "family_action"
    completed = _choose(game, "full_damage")
    assert completed.status is ResultStatus.COMPLETED
    assert not completed.inspection.in_progress and completed.inspection.winner_team == "blue"

    save_path = tmp_path / "l2-braggart-complete.json"
    game.save(save_path)
    continued = Encounter.load(save_path)
    transitioned = continued.next_encounter(next_scene)
    assert transitioned.status in {ResultStatus.PAUSED, ResultStatus.COMPLETED}
    _settle_initiative(continued)
    assert continued._state.creatures["braggart"].definition_id == BRAGGART_SWASHBUCKLER_LEVEL_2.definition_id
    assert continued._state.creatures["braggart"].held_items == ["braggart:dagger_1"]
    assert continued.execute(QuickJump((Position(1, 1), Position(2, 1)))).status is ResultStatus.PAUSED
    assert _choose(continued, "keep").status is ResultStatus.COMPLETED
    assert continued._state.creatures["braggart"].position == Position(2, 1)
