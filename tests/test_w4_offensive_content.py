"""Focused public play checks for the W4 offensive level-1 feat lane.

Sources checked 2026-09-20:
Exacting Strike https://2e.aonprd.com/Feats.aspx?ID=357
Double Slice https://2e.aonprd.com/Feats.aspx?ID=356
Twin Takedown https://2e.aonprd.com/Feats.aspx?ID=494
Twin Feint https://2e.aonprd.com/Feats.aspx?ID=552
"""

from pathlib import Path

from pf2e.content import get_setup
from pf2e.encounter import Encounter
from pf2e.model import PairedStrikeSelection, ResultStatus, Strike
from pf2e.ranger import HuntPrey
from pf2e.w4_offensive import DoubleSlice, ExactingStrike, TwinFeint, TwinTakedown


def _settle(game: Encounter) -> None:
    for _ in range(12):
        choice = game.inspect().choice
        if choice is None:
            return
        option = next((item.option_id for item in choice.options if item.option_id == "keep"), choice.options[0].option_id)
        result = game.choose(choice.choice_id, option, choice.owner_actor_id)
        assert result.status in {ResultStatus.PAUSED, ResultStatus.COMPLETED}
    raise AssertionError("choice chain did not settle")


def test_exacting_strike_ordinary_failure_does_not_add_map() -> None:
    game = Encounter.start(
        get_setup("w4_fighter_exacting_strike_vs_guard_dog"),
        rolls=(20, 1, 6, 1, 6, 1, 6, 1, 6, 1),
    )
    _settle(game)
    rejected = game.execute(ExactingStrike("dog", "longsword"))
    assert rejected.status is ResultStatus.REJECTED
    assert game.execute(Strike("dog", "longsword")).status is ResultStatus.PAUSED
    _settle(game)
    result = game.execute(ExactingStrike("dog", "longsword"))
    assert result.status is ResultStatus.PAUSED
    _settle(game)
    fighter = game._state.creatures["fighter"]
    assert fighter.strikes_this_turn == 1


def test_double_slice_uses_same_map_and_persists_between_strikes(tmp_path: Path) -> None:
    game = Encounter.start(
        get_setup("w4_fighter_double_slice_vs_guard_dog"),
        rolls=(20, 1, 6, 1, 6, 1, 6, 1, 6, 1, 6, 1),
    )
    _settle(game)
    result = game.execute(DoubleSlice(PairedStrikeSelection("dog", "longsword")))
    assert result.status is ResultStatus.PAUSED
    choice = game.inspect().choice
    assert choice is not None and choice.kind == "attack_hero_reroll"
    save_path = tmp_path / "double-slice.json"
    game.save(save_path)
    loaded = Encounter.load(save_path)
    choice = loaded.inspect().choice
    assert choice is not None and choice.kind == "attack_hero_reroll"
    loaded.choose(choice.choice_id, choice.options[0].option_id, choice.owner_actor_id)
    _settle(loaded)
    fighter = loaded._state.creatures["fighter"]
    assert fighter.strikes_this_turn == 2


def test_twin_takedown_requires_hunt_prey_and_runs_two_melee_attacks() -> None:
    game = Encounter.start(
        get_setup("w4_ranger_twin_takedown_vs_guard_dog"),
        rolls=(20, 1, 10, 1, 1, 10, 1, 1),
    )
    _settle(game)
    rejected = game.execute(TwinTakedown(PairedStrikeSelection("dog", "shortsword")))
    assert rejected.status is ResultStatus.REJECTED
    assert game.execute(HuntPrey("dog")).status is ResultStatus.COMPLETED
    result = game.execute(TwinTakedown(PairedStrikeSelection("dog", "shortsword")))
    assert result.status is ResultStatus.PAUSED
    _settle(game)
    assert game._state.creatures["ranger"].strikes_this_turn == 2


def test_twin_feint_is_public_and_requires_different_agile_or_finesse_melee_weapon() -> None:
    game = Encounter.start(
        get_setup("w4_rogue_twin_feint_vs_guard_dog"),
        rolls=(20, 1, 6, 1, 6, 1, 6, 1, 6, 1, 6, 1),
    )
    _settle(game)
    result = game.execute(TwinFeint(PairedStrikeSelection("dog", "shortsword")))
    assert result.status is ResultStatus.PAUSED
    assert game._state.creatures["rogue"].actions_remaining == 1
    choice = game.inspect().choice
    assert choice is not None and choice.kind == "attack_hero_reroll"
    kept = game.choose(choice.choice_id, "keep", choice.owner_actor_id)
    assert kept.status is ResultStatus.PAUSED
    choice = game.inspect().choice
    assert choice is not None and choice.kind == "family_action"
    second = game.choose(choice.choice_id, choice.options[0].option_id, choice.owner_actor_id)
    assert second.status is ResultStatus.PAUSED
    pending = game._state.pending_choice
    assert pending is not None and pending.kind == "attack_hero_reroll"
    assert pending.attack_target_off_guard is True
    _settle(game)
    assert game._state.creatures["rogue"].strikes_this_turn == 2
