"""W5 focus content: Initiate Warden, Harming Hands, and Hymn of Healing."""

from __future__ import annotations

from pf2e.content import get_definition, get_setup
from pf2e.encounter import Encounter
from pf2e.model import Cast, EndTurn, ResultStatus, Strike
from pf2e.persistence import _continuation_from_data, _continuation_to_data
from pf2e.model import ActionContinuation


def _finish_start_choices(game: Encounter) -> None:
    while (choice := game.inspect().choice) is not None:
        option = next(
            (item.option_id for item in choice.options if item.option_id == "keep"),
            choice.options[0].option_id,
        )
        result = game.choose(choice.choice_id, option, choice.owner_actor_id)
        assert result.status in {ResultStatus.PAUSED, ResultStatus.COMPLETED}


def test_w5_sheets_have_the_published_alternate_rosters() -> None:
    ranger = get_definition("ranger_precision_level_1_initiate_warden")
    cleric = get_definition("warpriest_nethys_harming_hands_level_1")
    bard = get_definition("bard_maestro_level_1_hymn_of_healing")

    assert "gravity_weapon" in ranger.abilities
    assert {access.spell_id for access in ranger.focus_spells} == {"gravity_weapon"}
    assert ranger.focus_points == ranger.focus_capacity == 1
    assert "harming_hands" in cleric.abilities
    assert "Arcana" in {skill.title() for skill, _rank, _modifier in cleric.skills}
    assert {spell.spell_id for spell in cleric.prepared_spells} == {
        "divine_lance", "void_warp", "guidance", "stabilize", "light",
        "harm",
    }
    assert "hymn_of_healing" in bard.abilities
    assert {access.spell_id for access in bard.focus_spells} >= {"counter_performance", "hymn_of_healing"}
    assert bard.focus_points == bard.focus_capacity == 3


def test_gravity_weapon_applies_once_to_the_first_held_weapon_strike() -> None:
    game = Encounter.start(
        get_setup("w5_gravity_weapon_vs_guard_dog"),
        rolls=(20, 1, 8, 4, 4),
    )
    _finish_start_choices(game)
    assert game.execute(Cast("gravity_weapon")).status is ResultStatus.COMPLETED

    result = game.execute(Strike("dog", "shortbow"))
    assert result.status is ResultStatus.PAUSED
    choice = game.inspect().choice
    assert choice is not None and choice.kind == "attack_hero_reroll"
    result = game.choose(choice.choice_id, "keep", choice.owner_actor_id)
    assert result.status is ResultStatus.COMPLETED
    damage = next(event.damage for event in result.events if event.kind == "damage")
    assert damage is not None and damage.total == 6
    assert game._state.creatures["ranger"].gravity_weapon_bonus_attack_id is None


def test_harming_hands_font_harm_uses_d10() -> None:
    game = Encounter.start(
        get_setup("w5_harming_hands_vs_guard_dog"),
        rolls=(20, 1, 1, 5),
    )
    _finish_start_choices(game)
    paused = game.execute(Cast("harm", "dog", actions=2))
    assert paused.status is ResultStatus.PAUSED
    choice = game.inspect().choice
    assert choice is not None and choice.kind == "spell_slot"
    assert {option.option_id for option in choice.options} >= {"font_harm_1", "ordinary_harm_1"}
    result = game.choose(choice.choice_id, "font_harm_1", choice.owner_actor_id)
    damage = next(event.damage for event in result.events if event.kind == "spell_damage")
    assert damage is not None and damage.components[0].dice_sides == 10
    assert game._state.creatures["cleric"].prepared_slots[7].spent


def test_hymn_heals_at_recipient_start_and_preserves_active_effect(tmp_path) -> None:
    game = Encounter.start(
        get_setup("w5_hymn_of_healing_vs_guard_dog"),
        rolls=(20, 1, 1, 1),
    )
    _finish_start_choices(game)
    game._state.creatures["ally"].hp = 10
    cast = game.execute(Cast("hymn_of_healing", "ally", actions=2))
    assert cast.status is ResultStatus.COMPLETED
    assert game._state.creatures["ally"].temporary_hp == 2
    assert game._state.creatures["ally"].hp == 10
    path = tmp_path / "hymn-active.json"
    game.save(path)
    game = Encounter.load(path)
    assert any(effect.kind == "hymn_of_healing" for effect in game._state.active_effects)

    assert game.execute(EndTurn()).status is ResultStatus.COMPLETED
    assert game.execute(EndTurn()).status is ResultStatus.COMPLETED
    assert game.inspect().turn_actor_id == "ally"
    assert game._state.creatures["ally"].hp == 12
    assert any(effect.kind == "hymn_of_healing" for effect in game._state.active_effects)


def test_gravity_marker_round_trips_through_an_interrupted_continuation() -> None:
    continuation = ActionContinuation(
        kind="ranged_strike",
        actor_id="ranger",
        target_id="dog",
        attack_id="shortbow",
        gravity_weapon_bonus=True,
    )
    restored = _continuation_from_data(_continuation_to_data(continuation))
    assert restored is not None and restored.gravity_weapon_bonus is True
