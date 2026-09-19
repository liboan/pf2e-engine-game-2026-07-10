"""Independent source/play review of the selected Courageous Anthem slice.

Sources checked 2026-09-16:

* Bard and Composition: https://2e.aonprd.com/Classes.aspx?ID=32
* Courageous Anthem: https://2e.aonprd.com/Spells.aspx?ID=1763
* Composition trait: https://2e.aonprd.com/Traits.aspx?ID=559

The printed cantrip is one action, lasts one round, and affects the caster and
living allies in a 60-foot emanation. Its +1 status bonus applies to attack
rolls, damage rolls, and saves against fear. A Bard can cast one composition
per turn; casting a new composition ends the previous active composition.
"""

from dataclasses import replace
from pathlib import Path

import pytest

import pf2e.content as content
from pf2e.bard_content import MAESTRO_BARD_ANTHEM_SETUP
from pf2e.encounter import Encounter
from pf2e.model import Cast, EndTurn, Position, ResultStatus, Strike


def _settle_choices(game: Encounter) -> None:
    for _ in range(10):
        choice = game.inspect().choice
        if choice is None:
            return
        option_ids = {option.option_id for option in choice.options}
        option_id = "keep" if "keep" in option_ids else choice.options[0].option_id
        assert game.choose(choice.choice_id, option_id, choice.owner_actor_id).status in {
            ResultStatus.PAUSED, ResultStatus.COMPLETED,
        }
    raise AssertionError("initiative choices did not settle")


def _finish_action_choices(game: Encounter, result):
    for _ in range(10):
        if result.status is not ResultStatus.PAUSED:
            return result
        choice = result.inspection.choice
        assert choice is not None
        option_ids = {option.option_id for option in choice.options}
        option_id = "use" if "use" in option_ids else "keep"
        assert option_id in option_ids
        result = game.choose(choice.choice_id, option_id, choice.owner_actor_id)
    raise AssertionError("action choices did not settle")


def test_emanation_includes_sixty_feet_but_excludes_dead_distant_and_enemy_creatures(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    base = MAESTRO_BARD_ANTHEM_SETUP
    bard, ally, dog = base.placements
    setup = replace(
        base,
        setup_id="review_bard_anthem_eligibility",
        name="Review Bard Anthem eligibility",
        width=17,
        placements=(
            replace(bard, position=Position(1, 1)),
            replace(ally, actor_id="ally_at_60", label="Ally at 60 feet", position=Position(13, 1)),
            replace(ally, actor_id="ally_at_65", label="Ally at 65 feet", position=Position(14, 1)),
            replace(ally, actor_id="dead_ally", label="Dead ally", position=Position(2, 2)),
            replace(dog, position=Position(3, 1)),
        ),
    )
    monkeypatch.setattr(content, "_STAGED_SETUPS", content._STAGED_SETUPS | {setup.setup_id: setup})
    game = Encounter.start(setup, rolls=(20, 1, 2, 3, 4))
    _settle_choices(game)
    dead = game._state.creatures["dead_ally"]
    dead.hp = 0
    dead.dead = True
    before_actions = game._state.creatures["maestro_bard"].actions_remaining

    cast = game.execute(Cast("courageous_anthem"))

    assert cast.status is ResultStatus.COMPLETED
    assert game._state.creatures["maestro_bard"].actions_remaining == before_actions - 1
    assert {
        effect.target_actor_id
        for effect in game._state.active_effects
        if effect.kind == "courageous_anthem"
    } == {"maestro_bard", "ally_at_60"}


def test_saved_anthem_and_guidance_status_bonuses_do_not_stack_on_attack(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    # Initiatives; ally attack and damage.
    base = MAESTRO_BARD_ANTHEM_SETUP
    setup = replace(
        base,
        setup_id="review_bard_anthem_stacking",
        name="Review Bard Anthem stacking",
        placements=base.placements + (
            replace(base.placements[2], actor_id="bard_dog_b", label="Second Guard Dog", position=Position(4, 1)),
        ),
    )
    monkeypatch.setattr(content, "_STAGED_SETUPS", content._STAGED_SETUPS | {setup.setup_id: setup})
    game = Encounter.start(setup, rolls=(20, 1, 2, 3, 10, 4))
    _settle_choices(game)
    assert game.execute(Cast("courageous_anthem")).status is ResultStatus.COMPLETED
    assert game.execute(Cast("guidance", "bard_ally")).status is ResultStatus.COMPLETED
    path = tmp_path / "review-bard-anthem-guidance.json"
    game.save(path)
    game = Encounter.load(path)

    before, dice_before = game.inspect(), game._dice.to_data()
    duplicate = game.execute(Cast("courageous_anthem"))
    assert duplicate.status is ResultStatus.REJECTED
    assert game.inspect() == before and game._dice.to_data() == dice_before

    assert game.execute(EndTurn()).status is ResultStatus.COMPLETED
    while game.inspect().turn_actor_id != "bard_ally":
        assert game.execute(EndTurn()).status is ResultStatus.COMPLETED
    assert game.inspect().turn_actor_id == "bard_ally"
    result = _finish_action_choices(game, game.execute(Strike("bard_dog", "longsword")))

    check = next(event.check for event in result.events if event.kind == "strike")
    assert check is not None and check.modifier == 10
    status_sources = {
        item.source for item in check.modifier_breakdown
        if item.modifier_type == "status" and item.amount == 1
    }
    assert status_sources == {"Courageous Anthem", "Guidance"}
    damage = next(event.damage for event in result.events if event.damage is not None)
    assert damage is not None and damage.total == 9

    assert game.execute(EndTurn()).status is ResultStatus.COMPLETED
    assert game.inspect().turn_actor_id == "maestro_bard"
    assert not any(effect.kind == "courageous_anthem" for effect in game._state.active_effects)


@pytest.mark.parametrize(
    ("save_die", "degree", "expected_total"),
    (
        (20, "CRITICAL_SUCCESS", 0),
        (12, "SUCCESS", 3),
        (5, "FAILURE", 6),
        (1, "CRITICAL_FAILURE", 12),
    ),
)
def test_saved_bard_anthem_adds_status_damage_before_void_warp_basic_save(
    tmp_path: Path,
    save_die: int,
    degree: str,
    expected_total: int,
) -> None:
    # Initiatives; dog Fortitude save; two Void Warp d4s.
    game = Encounter.start(MAESTRO_BARD_ANTHEM_SETUP, rolls=(20, 1, 2, save_die, 2, 3))
    _settle_choices(game)
    assert game.execute(Cast("courageous_anthem")).status is ResultStatus.COMPLETED
    path = tmp_path / f"review-bard-anthem-void-{degree.lower()}.json"
    game.save(path)
    game = Encounter.load(path)

    cast = game.execute(Cast("void_warp", "bard_dog"))

    assert cast.status is ResultStatus.COMPLETED
    save = next(event.check for event in cast.events if event.kind == "spell_save")
    assert save is not None and save.degree.name == degree
    damage = next(event.damage for event in cast.events if event.damage is not None)
    assert damage is not None
    assert damage.components[0].rolls == (2, 3)
    assert damage.components[0].modifier == 1
    assert damage.rolled_total == 6
    assert damage.total == expected_total
