from pathlib import Path

from pf2e import EndTurn, Strike
from pf2e.content import get_setup
from pf2e.encounter import Encounter
from pf2e.martial_defense import PointBlankStance
from pf2e.model import ResultStatus
from pf2e.skill_actions import Feint


def _settle(game: Encounter) -> None:
    while game.inspect().choice is not None:
        choice = game.inspect().choice
        option = next((item.option_id for item in choice.options if item.option_id == "keep"), choice.options[0].option_id)
        game.choose(choice.choice_id, option, choice.owner_actor_id)


def test_w4_roster_is_admitted_and_point_blank_persists(tmp_path: Path) -> None:
    game = Encounter.start(get_setup("w4_point_blank_stance_vs_guard_dog"), rolls=(20, 1))
    _settle(game)
    assert game.execute(PointBlankStance()).status is ResultStatus.COMPLETED
    assert game._state.martial_stances["w4_actor"].stance_id == "point_blank_stance"
    path = tmp_path / "w4-point-blank.json"
    game.save(path)
    loaded = Encounter.load(path)
    assert loaded._state.martial_stances["w4_actor"].stance_id == "point_blank_stance"


def test_reactive_shield_is_a_saved_pre_roll_choice(tmp_path: Path) -> None:
    game = Encounter.start(get_setup("w4_reactive_shield_vs_guard_dog"), rolls=(20, 1, 20, 1))
    _settle(game)
    assert game.execute(EndTurn()).status is ResultStatus.COMPLETED
    assert game.execute(Strike(target_id="w4_actor", attack_id="jaws")).status is ResultStatus.PAUSED
    assert game.inspect().choice.kind == "reactive_shield"
    path = tmp_path / "w4-reactive-shield.json"
    game.save(path)
    loaded = Encounter.load(path)
    assert loaded.inspect().choice.kind == "reactive_shield"
    assert loaded.choose(loaded.inspect().choice.choice_id, "use", "w4_actor").status is ResultStatus.COMPLETED


def test_overextending_feint_and_youre_next_runtime_paths() -> None:
    game = Encounter.start(get_setup("w4_overextending_feint_vs_guard_dog"), rolls=(20, 1, 20, 20))
    _settle(game)
    assert game.execute(Feint("w4_enemy", use_overextending=True)).status is ResultStatus.PAUSED
    choice = game.inspect().choice
    assert game.choose(choice.choice_id, "keep", choice.owner_actor_id).status is ResultStatus.COMPLETED
    assert game._state.overextending_feint_effects

    game = Encounter.start(get_setup("w4_youre_next_vs_two_guard_dogs"), rolls=(20, 1, 1, 20, 1, 20, 1, 20, 1, 20))
    _settle(game)
    game._state.creatures["w4_enemy_a"].hp = 1
    assert game.execute(Strike(target_id="w4_enemy_a", attack_id="shortsword")).status is ResultStatus.PAUSED
    choice = game.inspect().choice
    assert game.choose(choice.choice_id, "keep", choice.owner_actor_id).status is ResultStatus.PAUSED
    assert game.inspect().choice.kind == "youre_next"
    assert game.choose(game.inspect().choice.choice_id, "target:w4_enemy_b", "w4_actor").status is ResultStatus.COMPLETED
