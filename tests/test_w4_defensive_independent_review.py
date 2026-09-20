"""Independent public checks for W4 defensive class feats."""

import json
from pathlib import Path

import pytest

from pf2e import EndTurn, Strike
import pf2e.content as content
from pf2e.content import get_setup
from pf2e.encounter import Encounter
from pf2e.fighter import SnaggingStrike
from pf2e.martial_defense import PointBlankStance, point_blank_stance_is_active
from pf2e.model import CreaturePlacement, EncounterSetup, Position, Release, ResultStatus
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


def test_reactive_shield_turns_an_ordinary_hit_into_a_miss_after_load(tmp_path: Path) -> None:
    game = _ready("w4_reactive_shield_vs_guard_dog", (20, 1, 12))
    assert game.execute(EndTurn()).status is ResultStatus.COMPLETED
    assert game.execute(Strike("w4_actor", "jaws")).status is ResultStatus.PAUSED
    choice = game.inspect().choice
    assert choice is not None and choice.kind == "reactive_shield"
    path = tmp_path / "reactive-shield-hit.json"
    game.save(path)
    loaded = Encounter.load(path)
    choice = loaded.inspect().choice
    assert choice is not None and choice.kind == "reactive_shield"
    before_hp = loaded._state.creatures["w4_actor"].hp
    assert loaded.choose(choice.choice_id, "use", choice.owner_actor_id).status is ResultStatus.COMPLETED
    assert loaded._state.creatures["w4_actor"].hp == before_hp
    assert not loaded._state.creatures["w4_actor"].reaction_available
    assert "w4_actor" in loaded._state.raised_shields


def test_reactive_shield_triggers_on_a_special_melee_strike(monkeypatch: pytest.MonkeyPatch) -> None:
    snagging = get_setup("staged_fighter_level_1_snagging_strike").placements[0]
    shield = get_setup("w4_reactive_shield_vs_guard_dog").placements[0]
    setup = EncounterSetup(
        "review_reactive_shield_special_strike", "Reactive Shield versus Snagging Strike", 5, 3,
        (
            CreaturePlacement("attacker", snagging.definition_id, "Attacker", "red", Position(1, 1)),
            CreaturePlacement("defender", shield.definition_id, "Defender", "blue", Position(2, 1)),
        ),
    )
    monkeypatch.setattr(content, "_STAGED_SETUPS", content._STAGED_SETUPS | {setup.setup_id: setup})
    game = Encounter.start(setup, rolls=(20, 1, 12, 1))
    for _ in range(6):
        choice = game.inspect().choice
        if choice is None:
            break
        game.choose(choice.choice_id, "keep" if any(option.option_id == "keep" for option in choice.options) else choice.options[0].option_id, choice.owner_actor_id)
    assert game.execute(SnaggingStrike("defender", "longsword")).status is ResultStatus.PAUSED
    choice = game.inspect().choice
    assert choice is not None and choice.kind == "attack_hero_reroll"
    assert game.choose(choice.choice_id, "keep", choice.owner_actor_id).status is ResultStatus.PAUSED
    assert game.inspect().choice is not None and game.inspect().choice.kind == "reactive_shield"


def test_reactive_shield_save_rejects_a_forged_attack_modifier(tmp_path: Path) -> None:
    game = _ready("w4_reactive_shield_vs_guard_dog", (20, 1, 12))
    assert game.execute(EndTurn()).status is ResultStatus.COMPLETED
    assert game.execute(Strike("w4_actor", "jaws")).status is ResultStatus.PAUSED
    path = tmp_path / "forged-reactive-shield.json"
    game.save(path)
    payload = json.loads(path.read_text(encoding="utf-8"))
    check = payload["state"]["pending_choice"]["check"]
    check["modifier"] = 100
    check["total"] = check["die"] + 100
    check["degree"] = 3
    check["degree_before_adjustments"] = 3
    check["modifier_breakdown"] = [[100, "untyped", "printed attack modifier"]]
    check["adjustments"] = []
    path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ValueError):
        Encounter.load(path)
