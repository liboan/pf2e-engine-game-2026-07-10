"""Independent W4 caster checks for source-specific choices and resources.

Energy Ablation: https://2e.aonprd.com/Feats.aspx?ID=5026
Cackle: https://app.demiplane.com/nexus/pathfinder2e/spells/cackle-rm
"""

from __future__ import annotations

from pf2e.content import get_setup
from pf2e.encounter import Encounter
from pf2e.model import Cackle, Cast, EndTurn, EnergyAblation, ResultStatus


def _ready(game: Encounter, actor_id: str) -> None:
    for _ in range(16):
        choice = game.inspect().choice
        if choice is not None:
            option = next(
                (row.option_id for row in choice.options if row.option_id == "keep"),
                choice.options[0].option_id,
            )
            result = game.choose(choice.choice_id, option, choice.owner_actor_id)
        elif game.inspect().turn_actor_id != actor_id:
            result = game.execute(EndTurn())
        else:
            return
        assert result.status in {ResultStatus.PAUSED, ResultStatus.COMPLETED}
    raise AssertionError(f"{actor_id} did not get a turn")


def test_energy_ablation_resistance_choice_is_independent_of_spell_damage(tmp_path) -> None:
    game = Encounter.start(
        get_setup("w4_energy_ablation_vs_guard_dog"), rolls=(20, 1, 2, 2, 2, 2)
    )
    _ready(game, "wizard")
    assert game.execute(EnergyAblation("fire")).status is ResultStatus.COMPLETED
    result = game.execute(Cast("electric_arc", target_ids=("dog",)))
    assert result.status is ResultStatus.COMPLETED
    assert any(
        effect.kind == "energy_ablation" and ":fire:" in effect.effect_id
        for effect in game._state.active_effects
    )
    path = tmp_path / "fire-ablation-after-electric-cast.json"
    game.save(path)
    assert Encounter.load(path).inspect() == game.inspect()


def test_cackle_spends_a_focus_point_to_sustain_stoke(tmp_path) -> None:
    game = Encounter.start(get_setup("w4_cackle_witch"), rolls=(20, 1, 1, 1, 1, 1, 1))
    _ready(game, "witch")
    assert game.execute(Cast("stoke_the_heart", "ally")).status is ResultStatus.PAUSED
    _ready(game, "witch")
    assert game.execute(EndTurn()).status is ResultStatus.COMPLETED
    _ready(game, "witch")
    before = game._state.creatures["witch"].focus_points
    assert before >= 1
    assert game.execute(Cackle()).status in {ResultStatus.PAUSED, ResultStatus.COMPLETED}
    _ready(game, "witch")
    assert game._state.creatures["witch"].focus_points == before - 1
    path = tmp_path / "cackle-spent-focus.json"
    game.save(path)
    assert Encounter.load(path)._state.creatures["witch"].focus_points == before - 1


def test_cackle_cannot_follow_another_hex_cast_in_the_same_turn() -> None:
    """Witch's one-hex limit also applies to the Cackle focus hex."""
    game = Encounter.start(get_setup("w4_cackle_witch"), rolls=(20, 1, 1, 1, 1, 1, 1))
    _ready(game, "witch")
    assert game.execute(Cast("stoke_the_heart", "ally")).status is ResultStatus.PAUSED
    _ready(game, "witch")
    before = game._state.creatures["witch"].focus_points
    result = game.execute(Cackle())
    assert result.status is ResultStatus.REJECTED
    assert game._state.creatures["witch"].focus_points == before
