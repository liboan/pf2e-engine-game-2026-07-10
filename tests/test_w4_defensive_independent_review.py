"""Independent public checks for W4 defensive class feats."""

from pathlib import Path

from pf2e import EndTurn, Strike
from pf2e.content import get_setup
from pf2e.encounter import Encounter
from pf2e.martial_defense import PointBlankStance, point_blank_stance_is_active
from pf2e.model import Release, ResultStatus
from pf2e.skill_actions import Demoralize


def _ready(setup_id: str, rolls: tuple[int, ...]) -> Encounter:
    game = Encounter.start(get_setup(setup_id), rolls=rolls)
    for _ in range(6):
        choice = game.inspect().choice
        if choice is None:
            return game
        option_id = "keep" if any(option.option_id == "keep" for option in choice.options) else choice.options[0].option_id
        assert game.choose(choice.choice_id, option_id, choice.owner_actor_id).status in {
            ResultStatus.PAUSED, ResultStatus.COMPLETED,
        }
    raise AssertionError("initiative choices did not settle")


def test_reactive_shield_is_not_offered_for_a_melee_miss() -> None:
    game = _ready("w4_reactive_shield_vs_guard_dog", (20, 1, 1))
    assert game.execute(EndTurn()).status is ResultStatus.COMPLETED
    result = game.execute(Strike("w4_actor", "jaws"))
    assert result.status is ResultStatus.COMPLETED
    assert game.inspect().choice is None
    assert game._state.creatures["w4_actor"].reaction_available
    assert "w4_actor" not in game._state.raised_shields


def test_point_blank_stance_ends_when_the_ranged_weapon_is_released(tmp_path: Path) -> None:
    game = _ready("w4_point_blank_stance_vs_guard_dog", (20, 1))
    assert game.execute(PointBlankStance()).status is ResultStatus.COMPLETED
    assert point_blank_stance_is_active(game._state, "w4_actor")
    assert game.execute(Release("shortbow")).status is ResultStatus.COMPLETED
    assert not point_blank_stance_is_active(game._state, "w4_actor")
    path = tmp_path / "point-blank-after-release.json"
    game.save(path)
    assert not point_blank_stance_is_active(Encounter.load(path)._state, "w4_actor")


def test_youre_next_reaction_demoralize_cannot_be_called_without_its_trigger() -> None:
    for setup_id in ("w4_youre_next_vs_guard_dog", "w4_overextending_feint_vs_guard_dog"):
        game = _ready(setup_id, (20, 1, 15))
        actor = game._state.creatures["w4_actor"]
        actions_before = actor.actions_remaining
        reaction_before = actor.reaction_available
        result = game.execute(Demoralize("w4_enemy", youre_next_reaction=True))
        assert result.status is ResultStatus.REJECTED
        assert actor.actions_remaining == actions_before
        assert actor.reaction_available == reaction_before
