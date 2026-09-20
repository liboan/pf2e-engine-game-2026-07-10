"""Independent W3 caster checks across completed play and saved interruptions.

Widen Spell and Breathe Fire: https://2e.aonprd.com/Feats.aspx?ID=4715,
https://2e.aonprd.com/Spells.aspx?ID=1457. Cantrip Expansion:
https://2e.aonprd.com/Feats.aspx?ID=4580.
"""

from __future__ import annotations

import pytest

from pf2e.encounter import Encounter
from pf2e.model import (
    ActiveConditionEffect,
    Cast,
    EffectExpiration,
    EndTurn,
    Position,
    ResultStatus,
    WidenSpell,
)
from pf2e.w3_caster_content import (
    ANGELIC_SORCERER_L2_CANTRIP_EXPANSION_SETUP,
    BATTLE_MAGIC_WIZARD_L1_WIDEN_REACTION_SETUP,
    BATTLE_MAGIC_WIZARD_L1_WIDEN_SETUP,
)


def _ready(game: Encounter, actor_id: str) -> None:
    for _ in range(20):
        choice = game.inspect().choice
        if choice is not None:
            result = game.choose(
                choice.choice_id, choice.options[0].option_id, choice.owner_actor_id
            )
        elif game.inspect().turn_actor_id != actor_id:
            result = game.execute(EndTurn())
        else:
            return
        assert result.status in {ResultStatus.PAUSED, ResultStatus.COMPLETED}
    raise AssertionError(f"{actor_id} did not get a turn")


def test_widened_cast_after_save_wins_and_finished_scene_round_trips(tmp_path) -> None:
    game = Encounter.start(BATTLE_MAGIC_WIZARD_L1_WIDEN_SETUP, rolls=(20, 1, 4, 4, 1, 1))
    _ready(game, "wizard")
    assert game.execute(WidenSpell()).status is ResultStatus.COMPLETED

    path = tmp_path / "widen-finished.json"
    game.save(path)
    game = Encounter.load(path)
    invalid = game.execute(Cast("breathe_fire", actions=2, slot_id="wizard_breathe_fire"))
    assert invalid.status is ResultStatus.REJECTED
    assert game._state.creatures["wizard"].widen_spell_pending

    cast = game.execute(Cast(
        "breathe_fire", actions=2, area_direction=Position(1, 0),
        slot_id="wizard_breathe_fire",
    ))
    assert cast.status is ResultStatus.COMPLETED
    assert game.inspect().winner_team == "blue"
    assert any(
        event.kind == "spell_damage" and event.target_id == "wizard_far_target"
        for event in cast.events
    )
    game.save(path)
    assert Encounter.load(path).inspect().winner_team == "blue"


@pytest.mark.parametrize(("flat_die", "ready"), ((10, True), (1, False)))
def test_grabbed_widen_interruption_round_trips_before_flat_check(
    tmp_path, flat_die: int, ready: bool,
) -> None:
    game = Encounter.start(
        BATTLE_MAGIC_WIZARD_L1_WIDEN_REACTION_SETUP, rolls=(20, 1, 1, flat_die)
    )
    _ready(game, "wizard")
    # The source is an adjacent opponent, matching the established Grabbed
    # interruption fixture in test_expansion_core.py.
    game._state.condition_effects.append(ActiveConditionEffect(
        "grapple:reactive_fighter:wizard", "grabbed", "reactive_fighter", "wizard",
        1, EffectExpiration("reactive_fighter", "end", 1),
    ))
    started = game.execute(WidenSpell())
    assert started.status is ResultStatus.PAUSED
    reaction = started.inspection.choice
    assert reaction is not None and reaction.kind == "reaction"
    checked = game.choose(reaction.choice_id, "decline", "reactive_fighter")
    assert checked.status is ResultStatus.PAUSED
    assert any(event.kind == "grabbed_manipulate_flat_check" for event in checked.events)
    flat_choice = checked.inspection.choice
    assert flat_choice is not None and flat_choice.kind == "grabbed_manipulate_hero_reroll"

    path = tmp_path / "widen-grabbed.json"
    game.save(path)
    game = Encounter.load(path)
    assert game.inspect() == checked.inspection
    result = game.choose(flat_choice.choice_id, "keep", "wizard")
    assert result.status is ResultStatus.COMPLETED
    assert game._state.creatures["wizard"].widen_spell_pending is ready
    assert game._state.creatures["wizard"].actions_remaining == 2
    if not ready:
        assert any(event.kind == "action_lost" for event in result.events)


def test_expanded_sorcerer_cantrip_repertoire_survives_save(tmp_path) -> None:
    game = Encounter.start(
        ANGELIC_SORCERER_L2_CANTRIP_EXPANSION_SETUP, rolls=(20, 1, 1, 4, 4, 4)
    )
    _ready(game, "angelic_sorcerer")
    path = tmp_path / "sorcerer-cantrip-expansion.json"
    game.save(path)
    game = Encounter.load(path)
    result = game.execute(Cast("daze", target_id="sorcerer_target"))
    assert result.status is ResultStatus.COMPLETED
    assert any(event.kind == "spell_damage" for event in result.events)
    assert game._state.creatures["angelic_sorcerer"].spontaneous_slots[0].remaining == 4
