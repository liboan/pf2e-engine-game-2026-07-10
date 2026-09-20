"""Focused public evidence for the W5 Arms/parry lane."""

from pathlib import Path

from pf2e import EndTurn, Encounter, ExtravagantParry, Release, Strike
from pf2e.content import get_definition, get_setup
from pf2e.model import ResultStatus


def _settle(game: Encounter, *, accept_quick_tempered: bool = False) -> None:
    for _ in range(12):
        choice = game.inspect().choice
        if choice is None:
            return
        ids = {option.option_id for option in choice.options}
        if accept_quick_tempered and choice.kind == "family_action" and "accept" in ids:
            option_id = "accept"
        elif "keep" in ids:
            option_id = "keep"
        elif "decline" in ids:
            option_id = "decline"
        else:
            option_id = choice.options[0].option_id
        game.choose(choice.choice_id, option_id, choice.owner_actor_id)
    raise AssertionError("initiative did not settle")


def _choose(game: Encounter, option_id: str):
    choice = game.inspect().choice
    assert choice is not None
    return game.choose(choice.choice_id, option_id, choice.owner_actor_id)


def test_raging_thrower_applies_agile_rage_damage_and_lands_selected_dagger(tmp_path: Path) -> None:
    game = Encounter.start(
        get_setup("w5_raging_thrower_vs_guard"),
        rolls=(20, 1, 20, 1, 10, 10),
    )
    _settle(game, accept_quick_tempered=True)
    actor = game._state.creatures["raging_thrower"]
    assert actor.barbarian_state is not None and actor.barbarian_state.rage is not None
    definition = get_definition(actor.definition_id)
    dagger = next(attack for attack in definition.attacks if attack.attack_id == "dagger")
    thrown = next(attack for attack in definition.attacks if attack.attack_id == "dagger_thrown")
    assert (dagger.modifier, dagger.damage_modifier, dagger.attack_attribute) == (7, 4, "strength")
    assert (thrown.modifier, thrown.damage_modifier, thrown.attack_attribute) == (4, 4, "dexterity")
    assert "dagger_thrown" in {strike.attack_id for strike in game.options().strikes}

    pending = game.execute(
        Strike("raging_thrower_guard", "dagger_thrown", item_id="raging_thrower:dagger_1")
    )
    assert pending.status is ResultStatus.PAUSED
    path = tmp_path / "raging-thrower.json"
    game.save(path)
    game = Encounter.load(path)
    result = _choose(game, "keep")
    damage_event = next(event for event in result.events if event.damage is not None)
    rage_parts = [part for part in damage_event.damage.components if "Rage" in part.source]
    assert len(rage_parts) == 1 and rage_parts[0].modifier == 1
    weapon_parts = [part for part in damage_event.damage.components if part.source == "dagger_thrown"]
    assert len(weapon_parts) == 1 and weapon_parts[0].modifier == 4
    assert "raging_thrower:dagger_1" in game._state.ground_items[game._state.creatures["raging_thrower_guard"].position]


def test_strong_arm_profile_is_shared_by_menu_and_maximum_range() -> None:
    game = Encounter.start(get_setup("w5_strong_arm_vs_guard"), rolls=(20, 1))
    _settle(game)
    actor = game._state.creatures["strong_arm"]
    attack = next(item for item in get_definition(actor.definition_id).attacks if item.attack_id == "dagger_thrown")
    assert game._effective_ranged_profile(game._state, actor, attack) == (20, 120)
    assert "strong_arm_guard" in game.options().strikes[1].targets


def test_extravagant_parry_has_saved_guard_resolved_miss_panache_and_expiry(tmp_path: Path) -> None:
    game = Encounter.start(
        get_setup("w5_extravagant_parry_vs_guard"),
        rolls=(20, 1, 1, 1, 1),
    )
    _settle(game)
    assert game.execute(ExtravagantParry()).status is ResultStatus.COMPLETED
    assert game._effective_ac(game._state.creatures["parry_swashbuckler"], state=game._state) == 20
    path = tmp_path / "parry.json"
    game.save(path)
    game = Encounter.load(path)

    assert game.execute(EndTurn()).status is ResultStatus.COMPLETED
    miss = game.execute(Strike("parry_swashbuckler", "guard_spear"))
    assert any(event.kind == "extravagant_parry_panache" for event in miss.events)
    parry = game._state.creatures["parry_swashbuckler"]
    assert parry.panache and parry.panache_expires_at_end == 3

    # The guard's one-use requirement ends on release and cannot be revived by
    # retrieving the same dagger; the saved active effect is gone.
    game = Encounter.start(get_setup("w5_extravagant_parry_vs_guard"), rolls=(20, 1, 1, 1))
    _settle(game)
    assert game.execute(ExtravagantParry()).status is ResultStatus.COMPLETED
    assert game.execute(Release("parry_swashbuckler:dagger_1")).status is ResultStatus.COMPLETED
    assert not any(effect.kind == "extravagant_parry" for effect in game._state.active_effects)
