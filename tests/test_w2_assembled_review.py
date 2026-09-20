"""Independent save/load checks for assembled W2 content.

Fear (Player Core p. 331) makes its target flee for one round on a critical
failure: https://2e.aonprd.com/Spells.aspx?ID=1524
"""

from pathlib import Path

import pytest

import pf2e.content as content
from pf2e.content import get_setup
from pf2e.encounter import Encounter
from pf2e.martial_defense import DuelingParry
from pf2e.model import (
    ActivateAlchemy, Cast, CreaturePlacement, EncounterSetup, EndTurn,
    Position, QuickAlchemy, ResultStatus,
)


@pytest.mark.parametrize(
    "setup_id",
    (
        "faiths_flamekeeper_suppression_spells_vs_common_speaker",
        "battle_magic_wizard_suppression_spells_vs_common_speaker",
    ),
)
def test_prepared_fear_critical_failure_fleeing_survives_save_load(
    setup_id: str, tmp_path: Path,
) -> None:
    game = Encounter.start(get_setup(setup_id), rolls=(20, 1, 1))
    while (choice := game.inspect().choice) is not None:
        assert game.choose(choice.choice_id, "keep", choice.owner_actor_id).status in {
            ResultStatus.PAUSED, ResultStatus.COMPLETED,
        }

    cast = game.execute(Cast("fear", "enemy"))
    assert cast.status is ResultStatus.COMPLETED
    assert any(effect.kind == "fleeing" for effect in game._state.active_effects)
    path = tmp_path / "prepared-fear-critical.json"
    game.save(path)

    restored = Encounter.load(path)
    assert any(
        effect.kind == "fleeing" and effect.target_actor_id == "enemy"
        for effect in restored._state.active_effects
    )
    assert any(
        effect.kind == "frightened" and effect.target_actor_id == "enemy" and effect.value == 3
        for effect in restored._state.condition_effects
    )


def test_spell_guard_and_item_effects_round_trip_and_expire_independently(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    setup = EncounterSetup(
        "review_w2_joint_effects", "W2 joint effects", 9, 5,
        (
            CreaturePlacement("alchemist", "bomber_alchemist_level_2_item_support", "Alchemist", "blue", Position(1, 1)),
            CreaturePlacement("fighter", "fighter_m_level_2_dueling_parry", "Fighter", "blue", Position(1, 2)),
            CreaturePlacement("witch", "faiths_flamekeeper_witch_level_1_suppression_spells_prepared", "Witch", "blue", Position(1, 3)),
            CreaturePlacement("enemy", "flamekeeper_suppression_target", "Speaker", "red", Position(5, 2)),
        ),
    )
    monkeypatch.setattr(content, "_STAGED_SETUPS", content._STAGED_SETUPS | {setup.setup_id: setup})
    game = Encounter.start(setup, rolls=(20, 19, 18, 1, 10) * 16)
    while (choice := game.inspect().choice) is not None:
        assert game.choose(choice.choice_id, "keep", choice.owner_actor_id).status in {
            ResultStatus.PAUSED, ResultStatus.COMPLETED,
        }

    for actor_id in ("alchemist", "fighter", "witch"):
        for _ in range(8):
            if game.inspect().turn_actor_id == actor_id:
                break
            assert game.execute(EndTurn()).status is ResultStatus.COMPLETED
        else:
            raise AssertionError(f"{actor_id} did not receive a turn")
        if actor_id == "alchemist":
            assert game.execute(QuickAlchemy("create_consumable", "cheetahs_elixir_lesser")).status is ResultStatus.COMPLETED
            assert game.execute(ActivateAlchemy("alchemist:quick:1", "alchemist")).status is ResultStatus.COMPLETED
        elif actor_id == "fighter":
            assert game.execute(DuelingParry("longsword")).status is ResultStatus.COMPLETED
        else:
            assert game.execute(Cast("fear", "enemy")).status is ResultStatus.COMPLETED

    assert game.effective_speed_ft("alchemist") == 35
    assert game._effective_ac(game._state.creatures["fighter"], state=game._state) == 21
    assert any(effect.kind == "frightened" and effect.value == 2 for effect in game._state.condition_effects)
    path = tmp_path / "joint-effects.json"
    game.save(path)
    restored = Encounter.load(path)
    assert restored.effective_speed_ft("alchemist") == 35
    assert restored._effective_ac(restored._state.creatures["fighter"], state=restored._state) == 21
    assert any(effect.kind == "frightened" and effect.value == 2 for effect in restored._state.condition_effects)

    fighter_starts = restored._state.actor_start_counts["fighter"]
    for _ in range(8):
        if restored._state.actor_start_counts["fighter"] > fighter_starts:
            break
        assert restored.execute(EndTurn()).status is ResultStatus.COMPLETED
    else:
        raise AssertionError("Fighter's next turn did not start")
    assert restored._effective_ac(restored._state.creatures["fighter"], state=restored._state) == 19
    assert restored.effective_speed_ft("alchemist") == 35
