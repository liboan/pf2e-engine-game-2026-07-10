"""First public Maestro Bard Courageous Anthem play.

Rules sources: https://2e.aonprd.com/Classes.aspx?ID=32;
https://2e.aonprd.com/Spells.aspx?ID=1763; and
https://2e.aonprd.com/Traits.aspx?ID=559.
"""

from __future__ import annotations

from dataclasses import replace

import pf2e.content as content
from pf2e.content import get_definition, get_setup
from pf2e.encounter import Encounter
from pf2e.model import Cast, Choose, EndTurn, Position, ResultStatus, Step, Strike
from pf2e.skill_actions import Trip
from pf2e.spells import SPELLS
from pf2e.terminal import run_terminal
from terminal_test_helpers import BoundedInput, BoundedTranscript


ANTHEM_SETUP = "staged_maestro_bard_courageous_anthem_vs_guard_dog"
FEAR_SETUP = "staged_maestro_bard_courageous_anthem_fear"


def _keep(game: Encounter, result):
    choice = result.inspection.choice
    assert choice is not None
    return game.choose(choice.choice_id, "keep", choice.owner_actor_id)


def _finish_start_choices(game: Encounter) -> None:
    while (choice := game.inspect().choice) is not None:
        option = "keep" if any(item.option_id == "keep" for item in choice.options) else choice.options[0].option_id
        assert game.choose(choice.choice_id, option, choice.owner_actor_id).status in {
            ResultStatus.PAUSED, ResultStatus.COMPLETED,
        }


def test_staged_maestro_sheet_has_legal_level_one_spellcasting_and_declared_limits() -> None:
    bard = get_definition("bard_maestro_level_1_staged")
    assert bard.class_name == "Bard"
    assert (bard.hp, bard.perception, bard.spell_attack, bard.spell_dc) == (18, 5, 7, 17)
    assert dict(bard.ability_modifiers) == {
        "strength": 1, "dexterity": 2, "constitution": 2,
        "intelligence": 0, "wisdom": 0, "charisma": 4,
    }
    assert {spell.spell_id for spell in bard.spontaneous_spells if spell.cantrip} == {
        "light", "guidance", "void_warp", "forbidding_ward", "shield", "courageous_anthem",
    }
    assert {spell.spell_id for spell in bard.spontaneous_spells if not spell.cantrip} == {"fear", "runic_weapon", "soothe"}
    assert bard.spontaneous_slots[0].capacity == 2
    assert {name: rank for name, rank, _modifier in bard.saves}["will"] == "expert"
    assert dict((name, modifier) for name, _rank, modifier in bard.saves)["will"] == 5
    assert dict((name, modifier) for name, _rank, modifier in bard.skills) == {
        "acrobatics": 5, "athletics": 4, "deception": 7, "diplomacy": 7,
        "farming_lore": 3, "intimidation": 7, "medicine": 3, "occultism": 3,
        "performance": 7, "society": 3,
    }
    assert (bard.heritage, bard.land_speed_ft, bard.vision, bard.held_items, bard.hero_points) == (
        "Versatile Human", 30, "ordinary", ("rapier",), 1,
    )
    assert set(bard.feats) == {"Fleet", "Natural Skill", "Assurance (Athletics)"}
    assert {spell.spell_id for spell in bard.focus_spells} == {"counter_performance", "lingering_composition"}
    assert (bard.focus_points, bard.focus_capacity) == (2, 2)
    assert "shield_cantrip" in bard.abilities
    assert "Fear and Runic Weapon are the two Bard choices, while Maestro grants Soothe" in bard.sheet_notes[2]
    assert SPELLS["fear"].traits == frozenset({"concentrate", "emotion", "fear", "manipulate", "mental"})


def test_selected_maestro_assurance_and_held_rapier_round_trip(monkeypatch, tmp_path) -> None:
    # The Bard starts ten feet from the dog; a legal Step makes the actual
    # Farmhand Assurance (Athletics) Trip available without a die or Hero
    # choice. Its trained proficiency gives the fixed level-1 total of 13.
    setup = replace(
        get_setup(ANTHEM_SETUP),
        setup_id="maestro_assurance_held_rapier",
        placements=tuple(
            placement
            for placement in get_setup(ANTHEM_SETUP).placements
            if placement.actor_id != "bard_ally"
        ),
    )
    monkeypatch.setattr(content, "_STAGED_SETUPS", content._STAGED_SETUPS | {setup.setup_id: setup})
    game = Encounter.start(setup, rolls=(20, 1))
    _finish_start_choices(game)
    bard = game._state.creatures["maestro_bard"]
    assert bard.held_items == ["rapier"]
    assert game.execute(Step(Position(2, 1))).status is ResultStatus.COMPLETED
    result = game.execute(Trip("bard_dog", use_assurance=True))
    assert result.status is ResultStatus.COMPLETED
    check = next(event.check for event in result.events if event.kind == "trip_check")
    assert check is not None
    assert (check.method, check.die, check.total) == ("assurance", None, 13)

    path = tmp_path / "maestro-assurance-held-rapier.json"
    game.save(path)
    restored = Encounter.load(path)
    assert restored._state.creatures["maestro_bard"].held_items == ["rapier"]


def test_anthem_improves_ally_strike_damage_and_round_trips_active_effect(tmp_path) -> None:
    # Initiatives (bard, ally, dog); ally's attack and damage.
    game = Encounter.start(get_setup(ANTHEM_SETUP), rolls=(20, 1, 1, 10, 4))
    _finish_start_choices(game)
    assert game.inspect().turn_actor_id == "maestro_bard"
    cast = game.execute(Cast("courageous_anthem"))
    assert cast.status is ResultStatus.COMPLETED
    assert any(event.kind == "courageous_anthem_applied" for event in cast.events)
    effects = [effect for effect in game._state.active_effects if effect.kind == "courageous_anthem"]
    assert {(effect.target_actor_id, effect.value, effect.expires_at_source_start) for effect in effects} == {
        ("maestro_bard", 1, 2), ("bard_ally", 1, 2),
    }

    path = tmp_path / "bard-anthem-active.json"
    game.save(path)
    game = Encounter.load(path)
    assert {effect.target_actor_id for effect in game._state.active_effects if effect.kind == "courageous_anthem"} == {
        "maestro_bard", "bard_ally",
    }

    assert game.execute(EndTurn()).status is ResultStatus.COMPLETED
    assert game.inspect().turn_actor_id == "bard_dog"
    assert game.execute(EndTurn()).status is ResultStatus.COMPLETED
    assert game.inspect().turn_actor_id == "bard_ally"
    attack = _keep(game, game.execute(Strike("bard_dog", "longsword")))
    assert attack.status is ResultStatus.COMPLETED
    check = next(event.check for event in attack.events if event.check is not None)
    assert check is not None and check.modifier == 10
    assert ("Courageous Anthem", 1, "status") in {
        (modifier.source, modifier.amount, modifier.modifier_type)
        for modifier in check.modifier_breakdown
    }
    damage = next(event.damage for event in attack.events if event.damage is not None)
    assert damage is not None and damage.total == 9


def test_anthem_fear_save_is_typed_and_expires_at_bard_next_start() -> None:
    # Initiatives; opponent Fear Will save.
    game = Encounter.start(get_setup(FEAR_SETUP), rolls=(20, 1, 10))
    _finish_start_choices(game)
    assert game.execute(Cast("courageous_anthem")).status is ResultStatus.COMPLETED
    duplicate_before = game.inspect()
    duplicate = game.execute(Cast("courageous_anthem"))
    assert duplicate.status is ResultStatus.REJECTED
    assert game.inspect() == duplicate_before

    assert game.execute(EndTurn()).status is ResultStatus.COMPLETED
    assert game.inspect().turn_actor_id == "angelic_opponent"
    fear = game.execute(Cast("fear", "maestro_bard", slot_id="angelic_rank1"))
    resolved = _keep(game, fear) if fear.status is ResultStatus.PAUSED else fear
    save = next(event.check for event in resolved.events if event.kind == "spell_save")
    assert save is not None and save.modifier == 6
    assert ("Courageous Anthem", 1, "status") in {
        (modifier.source, modifier.amount, modifier.modifier_type)
        for modifier in save.modifier_breakdown
    }

    assert game.execute(EndTurn()).status is ResultStatus.COMPLETED
    assert game.inspect().turn_actor_id == "maestro_bard"
    assert not any(effect.kind == "courageous_anthem" for effect in game._state.active_effects)


def test_anthem_status_bonus_is_in_void_warp_raw_damage_before_basic_save() -> None:
    # Initiatives; dog Fortitude failure; Void Warp's 2d4 damage.  The raw
    # 2+3 damage roll becomes 6 with Anthem before the basic failure result.
    game = Encounter.start(get_setup(ANTHEM_SETUP), rolls=(20, 1, 1, 10, 2, 3))
    _finish_start_choices(game)
    assert game.execute(Cast("courageous_anthem")).status is ResultStatus.COMPLETED
    void_warp = game.execute(Cast("void_warp", "bard_dog"))
    resolved = _keep(game, void_warp) if void_warp.status is ResultStatus.PAUSED else void_warp
    damage = next(event.damage for event in resolved.events if event.damage is not None)
    assert damage is not None
    assert damage.rolled_total == damage.total == 6
    assert damage.components[0].source == "Void Warp"
    assert damage.components[0].modifier == 1
    assert damage.components[0].tags == frozenset()


def test_later_composition_replaces_a_saved_extended_anthem_without_reusing_turn_marker() -> None:
    # An extension source (for example, a future Lingering Composition path)
    # is deliberately outside this slice. This state exercise proves that a
    # surviving prior composition is replaced on a later Bard turn instead of
    # being mistaken for the current turn's composition.
    game = Encounter.start(get_setup(ANTHEM_SETUP), rolls=(20, 1, 1))
    _finish_start_choices(game)
    assert game.execute(Cast("courageous_anthem")).status is ResultStatus.COMPLETED
    game._state.active_effects[:] = [
        replace(effect, expires_at_source_start=3, expires_at_world_time=12)
        if effect.kind == "courageous_anthem" else effect
        for effect in game._state.active_effects
    ]
    assert game.execute(EndTurn()).status is ResultStatus.COMPLETED
    assert game.execute(EndTurn()).status is ResultStatus.COMPLETED
    assert game.execute(EndTurn()).status is ResultStatus.COMPLETED
    assert game.inspect().turn_actor_id == "maestro_bard"
    replacement = game.execute(Cast("courageous_anthem"))
    assert replacement.status is ResultStatus.COMPLETED
    effects = [effect for effect in game._state.active_effects if effect.kind == "courageous_anthem"]
    assert {effect.expires_at_source_start for effect in effects} == {3}
    assert game._state.creatures["maestro_bard"].composition_cast_at_start == 2


def test_anthem_uses_printed_emanation_without_sight_or_hearing_inference() -> None:
    setup = get_setup(ANTHEM_SETUP)
    game = Encounter.start(setup, rolls=(20, 1, 1))
    _finish_start_choices(game)
    game._state.ambient_light = "dim"
    assert game.execute(Cast("courageous_anthem")).status is ResultStatus.COMPLETED
    assert {effect.target_actor_id for effect in game._state.active_effects if effect.kind == "courageous_anthem"} == {
        "maestro_bard", "bard_ally",
    }


def test_bounded_terminal_can_select_and_cast_staged_courageous_anthem() -> None:
    transcript = BoundedTranscript(max_lines=300, max_chars=50_000)
    state = {"menu": "", "prompt": "", "choice": "", "phase": "cast"}

    def output(line: str) -> None:
        transcript.append(line)
        if line.startswith("1. "):
            state["menu"] = line
        if "choice owner:" in line:
            state["choice"] = line
        if line.endswith(":"):
            state["prompt"] = line

    def choose(label: str, *, prefix: bool = False) -> str:
        for row in state["menu"].splitlines():
            number, text = row.split(". ", 1)
            if text.startswith(label) if prefix else text == label:
                return number
        raise AssertionError(f"menu label missing: {label!r} in {state['menu']!r}")

    def scripted_input() -> str:
        prompt = state["prompt"]
        if prompt == "Choice prompt action:":
            return choose("Resolve this choice")
        if prompt == "Choice option number:":
            return choose("Keep initiative")
        if prompt == "Choice:":
            if state["phase"] == "cast":
                state["phase"] = "quit"
                return choose("Cast")
            return choose("Quit")
        if prompt == "Spell number:":
            return choose("Courageous Anthem", prefix=True)
        if prompt == "Casting mode:":
            return choose("1 action")
        raise AssertionError(f"unexpected terminal prompt: {prompt!r}")

    assert run_terminal(
        setup=get_setup(ANTHEM_SETUP), rolls=(20, 1, 1),
        input_fn=BoundedInput(scripted_input, max_calls=30), output_fn=output,
    ) == 0
    rendered = "\n".join(transcript)
    assert "Courageous Anthem" in rendered
    assert all(name in rendered for name in ("Forbidding Ward", "Guidance", "Light", "Shield", "Void Warp"))
    assert "The engine did not provide a selectable target or casting mode" not in rendered
    assert "commits Courageous Anthem" in rendered, rendered
