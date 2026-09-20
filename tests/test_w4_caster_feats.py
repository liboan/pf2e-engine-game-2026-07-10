"""Focused W4 caster/support feature checks."""

from pathlib import Path
from pf2e.content import get_setup
from pf2e.encounter import Encounter
from pf2e.model import Cackle, Cast, EndTurn, EnergyAblation, Position, ResultStatus, Strike, WidenSpell


def _settle(game: Encounter) -> None:
    for _ in range(12):
        choice = game.inspect().choice
        if choice is not None:
            if choice.kind == "initiative_hero_reroll":
                option = "keep"
            elif choice.kind == "witch_restored_spirit_timing":
                option = "after"
            elif choice.kind == "witch_restored_spirit":
                option = choice.options[0].option_id
            else:
                option = choice.options[0].option_id
            game.choose(choice.choice_id, option, choice.owner_actor_id)
            continue
        return
    raise AssertionError("fixture did not settle bounded choices")


def _take_turn(game: Encounter, actor_id: str) -> None:
    _settle(game)
    for _ in range(8):
        if game.inspect().turn_actor_id == actor_id:
            return
        game.execute(EndTurn())
        _settle(game)
    raise AssertionError(f"fixture did not reach {actor_id}")


def test_energy_ablation_is_an_immediate_successor_and_persists(tmp_path: Path) -> None:
    game = Encounter.start(get_setup("w4_energy_ablation_vs_guard_dog"), rolls=(20, 1, 2, 2, 2, 2))
    _take_turn(game, "wizard")

    assert game.execute(EnergyAblation("fire")).status is ResultStatus.COMPLETED
    save_path = tmp_path / "energy-ablation.json"
    game.save(save_path)
    restored = Encounter.load(save_path)
    assert restored._state.creatures["wizard"].energy_ablation_pending == "fire"

    result = restored.execute(Cast("electric_arc", target_ids=("dog",)))
    assert result.status is ResultStatus.COMPLETED
    assert any(
        effect.kind == "energy_ablation" and ":fire:" in effect.effect_id
        for effect in restored._state.active_effects
    )


def test_energy_ablation_is_wasted_by_an_ineligible_cast() -> None:
    game = Encounter.start(get_setup("w4_energy_ablation_vs_guard_dog"), rolls=(20, 1, 2, 2, 2, 2))
    _take_turn(game, "wizard")
    assert game.execute(EnergyAblation("fire")).status is ResultStatus.COMPLETED
    result = game.execute(Cast("shield"))
    assert result.status is ResultStatus.COMPLETED
    assert game._state.creatures["wizard"].energy_ablation_pending is None
    assert not any(effect.kind == "energy_ablation" for effect in game._state.active_effects)


def test_weapon_surge_targets_the_held_weapon_and_is_consumed_by_strike() -> None:
    game = Encounter.start(get_setup("w4_weapon_surge_vs_guard_dog"), rolls=(20, 1, 20, 1, 1, 1, 1))
    _take_turn(game, "cleric")

    assert game.execute(Cast("weapon_surge")).status is ResultStatus.COMPLETED
    result = game.execute(Strike("dog", item_id="longsword"))
    while game.inspect().choice is not None:
        choice = game.inspect().choice
        assert choice is not None
        result = game.choose(choice.choice_id, "keep", choice.owner_actor_id)
    assert result.status in {ResultStatus.PAUSED, ResultStatus.COMPLETED}
    assert any(
        modifier.source == "Weapon Surge"
        for event in result.events
        if event.check is not None
        for modifier in event.check.modifier_breakdown
    )
    assert any(
        component.source == "weapon_surge"
        for event in result.events
        if event.damage is not None
        for component in event.damage.components
    )
    assert not any(effect.kind == "weapon_surge" for effect in game._state.active_effects)


def test_sorcerer_widen_spell_uses_the_existing_area_spellshape_contract() -> None:
    game = Encounter.start(get_setup("w4_widen_sorcery_vs_guard_dog"), rolls=(20, 1, 1, 1, 1, 1, 1))
    _take_turn(game, "sorcerer")
    assert game.execute(WidenSpell()).status is ResultStatus.COMPLETED
    result = game.execute(Cast("breathe_fire", actions=2, area_direction=Position(1, 0)))
    assert result.status is ResultStatus.COMPLETED
    assert not game._state.creatures["sorcerer"].widen_spell_pending


def test_cackle_extends_stoke_without_spending_an_action() -> None:
    game = Encounter.start(get_setup("w4_cackle_witch"), rolls=(20, 1, 1, 1, 1, 1, 1))
    _take_turn(game, "witch")
    assert game.execute(Cast("stoke_the_heart", "ally")).status is ResultStatus.PAUSED
    _settle(game)
    actions_before = game._state.creatures["witch"].actions_remaining
    focus_before = game._state.creatures["witch"].focus_points
    assert game._state.creatures["witch"].focus_capacity == 2
    result = game.execute(Cackle())
    assert result.status is ResultStatus.COMPLETED
    witch = game._state.creatures["witch"]
    assert witch.actions_remaining == actions_before
    assert witch.focus_points == focus_before - 1
    assert any(effect.kind == "stoke_the_heart" for effect in game._state.active_effects)
    assert game.execute(Cackle()).status is ResultStatus.REJECTED
