"""Independent source/play review of the staged Precision Ranger bow group.

Sources checked 2026-09-16:

* Ranger and Hunt Prey: https://2e.aonprd.com/Classes.aspx?ID=36
* Precision edge: https://2e.aonprd.com/HuntersEdge.aspx?ID=5
* Hunted Shot: https://2e.aonprd.com/Feats.aspx?ID=4861
* Shortbow: https://2e.aonprd.com/Weapons.aspx?ID=437
* Grabbed: https://2e.aonprd.com/Conditions.aspx?ID=77

The numerical expectations precede the observations below.  Hunt Prey is a
one-action concentrate action, ignores the penalty only inside the second
range increment, and lasts until the next daily preparations.  A shortbow is
1d6 piercing, range increment 60 feet, reload 0, and has no Strength damage.
Thus this level-1 Ranger attacks at +7 with no range penalty through 120 feet,
but at +3 in the third increment (the ordinary -4 at 125 feet).  Precision
adds 1d8 same-type precision damage to the first hit each round.  Hunted Shot
is one flourish action that makes two Strikes against the current prey,
applying MAP normally (0, then -5 here) and combining same-target damage for
weaknesses and resistances.  Grabbed requires a DC 5 flat check after an
action is spent and before a manipulate effect occurs.
"""

from pathlib import Path

import pytest

import pf2e.content as content
from pf2e.encounter import Encounter
from pf2e.model import (
    ActiveConditionEffect,
    Choose,
    CreaturePlacement,
    EffectExpiration,
    EncounterSetup,
    PairedStrikeSelection,
    Position,
    ResultStatus,
    Strike,
)
from pf2e.paired_strikes import _decode_selection
from pf2e.ranger import HuntPrey, HuntedShot
from pf2e.ranger_monk_content import RANGER_PRECISION


def _choose(game: Encounter, option_id: str):
    choice = game.inspect().choice
    assert choice is not None
    return game.execute(Choose(choice.choice_id, option_id, choice.owner_actor_id))


def _settle_initiative(game: Encounter) -> None:
    for _ in range(12):
        choice = game.inspect().choice
        if choice is None:
            return
        assert choice.kind in {"initiative_hero_reroll", "initiative_tie"}
        option_id = "keep" if any(item.option_id == "keep" for item in choice.options) else choice.options[0].option_id
        assert _choose(game, option_id).status in {ResultStatus.PAUSED, ResultStatus.COMPLETED}
    raise AssertionError("initiative did not settle")


def _second_shortbow_option(game: Encounter, target_id: str) -> str:
    choice = game.inspect().choice
    assert choice is not None and choice.kind == "family_action"
    for option in choice.options:
        selection = _decode_selection(option.option_id)
        if (
            selection is not None
            and selection.target_id == target_id
            and selection.attack_id == "shortbow"
            and selection.damage_type is None
            and selection.nonlethal is None
        ):
            return option.option_id
    raise AssertionError(f"no default second shortbow option for {target_id!r}")


def _staged_game(*, rolls: tuple[int, ...]) -> Encounter:
    game = Encounter.start(content.get_setup("staged_ranger_precision_bow"), rolls=rolls)
    _settle_initiative(game)
    assert game.inspect().turn_actor_id == "ranger"
    return game


def test_selected_shortbow_and_second_increment_match_printed_numbers() -> None:
    bow = next(attack for attack in RANGER_PRECISION.attacks if attack.attack_id == "shortbow")
    assert (
        bow.damage_dice,
        bow.damage_modifier,
        bow.damage_type,
        bow.range_increment_ft,
        bow.max_range_ft,
        bow.reload,
    ) == ((6,), 0, "piercing", 60, 360, 0)

    game = _staged_game(rolls=(20, 1, 1, 10))
    assert game.execute(HuntPrey("guard_dog_a")).status is ResultStatus.COMPLETED
    at_120 = game.execute(Strike("guard_dog_a", "shortbow"))
    check = next(event.check for event in at_120.events if event.kind == "strike")
    assert check is not None and check.modifier == 7
    assert all(item.source != "range increment penalty" for item in check.modifier_breakdown)

    game = _staged_game(rolls=(20, 1, 1, 10))
    game._state.creatures["guard_dog_a"].position = Position(25, 1)
    assert game.execute(HuntPrey("guard_dog_a")).status is ResultStatus.COMPLETED
    at_125 = game.execute(Strike("guard_dog_a", "shortbow"))
    check = next(event.check for event in at_125.events if event.kind == "strike")
    assert check is not None and check.modifier == 3
    assert any(
        item.source == "range increment penalty" and item.amount == -4
        for item in check.modifier_breakdown
    )


def test_first_hunted_shot_miss_defers_precision_to_second_hit() -> None:
    # Initiative; first natural 1; second natural 20; d6, deadly d10, precision d8.
    game = _staged_game(rolls=(20, 1, 1, 1, 20, 2, 3, 4))
    assert game.execute(HuntPrey("guard_dog_a")).status is ResultStatus.COMPLETED

    first = game.execute(HuntedShot(PairedStrikeSelection("guard_dog_a", "shortbow")))
    assert first.status is ResultStatus.PAUSED
    first = _choose(game, "keep")
    first_check = next(event.check for event in first.events if event.kind == "strike")
    assert first_check is not None and first_check.map_penalty == 0
    assert not any(event.damage is not None for event in first.events)
    assert game._state.creatures["ranger"].precision_used_round == 0

    second = _choose(game, _second_shortbow_option(game, "guard_dog_a"))
    assert second.status is ResultStatus.PAUSED
    finished = _choose(game, "keep")
    second_check = next(event.check for event in finished.events if event.kind == "strike")
    damage = next(event.damage for event in finished.events if event.damage is not None)
    assert second_check is not None and second_check.map_penalty == -5
    assert damage is not None
    assert [part.source for part in damage.components] == [
        "shortbow",
        "shortbow deadly",
        "ranger_precision",
    ]
    precision = damage.components[-1]
    assert precision.tags == frozenset({"precision"}) and precision.amount == 8
    assert game._state.creatures["ranger"].ammunition["arrow"] == 18
    assert game._state.creatures["ranger"].strikes_this_turn == 2
    assert game._state.creatures["ranger"].actions_remaining == 1


def test_two_hunted_shot_hits_apply_precision_and_same_type_resistance_once(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    ward = content.get_definition("warpriest_c_typed_defense_test_grant")
    setup = EncounterSetup(
        setup_id="review_precision_ranger_combined_defense",
        name="Review Precision Ranger combined defense",
        width=4,
        height=3,
        placements=(
            CreaturePlacement("ranger", RANGER_PRECISION.definition_id, "Precision Ranger", "blue", Position(0, 1)),
            CreaturePlacement("ward", ward.definition_id, "Ward", "red", Position(2, 1)),
        ),
    )
    monkeypatch.setattr(content, "_STAGED_SETUPS", content._STAGED_SETUPS | {setup.setup_id: setup})
    # Initiative; first hit, d6, precision d8; second hit at MAP, d6.
    game = Encounter.start(setup, rolls=(20, 1, 11, 3, 2, 16, 3))
    _settle_initiative(game)
    before_hp = game._state.creatures["ward"].hp
    assert game.execute(HuntPrey("ward")).status is ResultStatus.COMPLETED
    assert game.execute(HuntedShot(PairedStrikeSelection("ward", "shortbow"))).status is ResultStatus.PAUSED
    first = _choose(game, "keep")
    first_damage = next(event.damage for event in first.events if event.damage is not None)
    assert first_damage is not None
    assert [part.source for part in first_damage.components] == ["shortbow", "ranger_precision"]

    assert _choose(game, _second_shortbow_option(game, "ward")).status is ResultStatus.PAUSED
    second = _choose(game, "keep")
    second_damage = next(event.damage for event in second.events if event.damage is not None)
    assert second_damage is not None
    assert [part.source for part in second_damage.components] == ["shortbow"]
    # Raw damage is 3+2 then 3. Hunted Shot's resistance 2 applies once to
    # the combined same-type effect, for 6 HP lost rather than 4.
    assert before_hp - game._state.creatures["ward"].hp == 6


def test_saved_second_grabbed_failure_preserves_only_unlaunched_second_arrow_and_map(
    tmp_path: Path,
) -> None:
    # Initiative; first DC5 passes; attack hits; d6 and precision d8; second DC5 fails.
    game = _staged_game(rolls=(20, 1, 1, 5, 10, 4, 3, 4))
    assert game.execute(HuntPrey("guard_dog_a")).status is ResultStatus.COMPLETED
    game._state.condition_effects.append(ActiveConditionEffect(
        "review-grapple",
        "grabbed",
        "guard_dog_a",
        "ranger",
        1,
        EffectExpiration("guard_dog_a", "end", 1),
    ))

    first_flat = game.execute(HuntedShot(PairedStrikeSelection("guard_dog_a", "shortbow")))
    assert first_flat.status is ResultStatus.PAUSED
    assert game.inspect().choice is not None and game.inspect().choice.kind == "grabbed_manipulate_hero_reroll"
    assert _choose(game, "keep").status is ResultStatus.PAUSED
    first_attack = _choose(game, "keep")
    assert first_attack.status is ResultStatus.PAUSED
    assert game._state.creatures["ranger"].ammunition["arrow"] == 19
    assert game._state.creatures["ranger"].strikes_this_turn == 1

    second_flat = _choose(game, _second_shortbow_option(game, "guard_dog_a"))
    assert second_flat.status is ResultStatus.PAUSED
    assert game.inspect().choice is not None and game.inspect().choice.kind == "grabbed_manipulate_hero_reroll"
    path = tmp_path / "review-ranger-second-grabbed-flat.json"
    game.save(path)
    game = Encounter.load(path)
    stopped = _choose(game, "keep")
    assert stopped.status is ResultStatus.COMPLETED
    assert any(event.kind == "action_lost" for event in stopped.events)
    assert not any(event.kind == "paired_strike_complete" for event in stopped.events)
    assert not any(event.kind == "strike" for event in stopped.events)
    assert game._state.creatures["ranger"].ammunition["arrow"] == 19
    assert game._state.creatures["ranger"].strikes_this_turn == 1


def test_replacing_and_saving_prey_keeps_invalid_commands_atomic(tmp_path: Path) -> None:
    game = _staged_game(rolls=(20, 1, 1))
    assert game.execute(HuntPrey("guard_dog_a")).status is ResultStatus.COMPLETED
    assert game.execute(HuntPrey("guard_dog_b")).status is ResultStatus.COMPLETED
    ranger = game._state.creatures["ranger"]
    assert ranger.hunted_prey is not None and ranger.hunted_prey.target_actor_id == "guard_dog_b"

    path = tmp_path / "review-ranger-replaced-prey.json"
    game.save(path)
    game = Encounter.load(path)
    before = game.inspect()
    dice_before = game._dice.to_data()
    rejected = game.execute(HuntPrey("ranger"))
    assert rejected.status is ResultStatus.REJECTED
    assert game.inspect() == before and game._dice.to_data() == dice_before

    rejected = game.execute(HuntedShot(PairedStrikeSelection("guard_dog_a", "shortbow")))
    assert rejected.status is ResultStatus.REJECTED
    assert game.inspect() == before and game._dice.to_data() == dice_before
    prey = game._state.creatures["ranger"].hunted_prey
    assert prey is not None and prey.target_actor_id == "guard_dog_b"
