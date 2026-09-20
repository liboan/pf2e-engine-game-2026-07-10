"""W3 caster spellshape and finite-preparation acceptance checks.

Rules checked before implementation:

* Widen Spell: https://2e.aonprd.com/Feats.aspx?ID=4715
* Cantrip Expansion: https://2e.aonprd.com/Feats.aspx?ID=4580
* Breathe Fire: https://2e.aonprd.com/Spells.aspx?ID=1457
* Daze: https://2e.aonprd.com/Spells.aspx?ID=1482
* Forbidding Ward: https://2e.aonprd.com/Spells.aspx?ID=1535
"""

from __future__ import annotations

import json

import pytest

from pf2e.druid import preparation_choices, prepared_slot_rejection
from pf2e.druid_content import STORM_DRUID
from pf2e.encounter import Encounter
from pf2e.model import Cast, EndTurn, Position, ResultStatus, WidenSpell
from pf2e.spells import SPELLS
from pf2e.terminal import run_terminal
from pf2e.w3_caster_content import (
    ANGELIC_SORCERER_L2_CANTRIP_EXPANSION,
    ANGELIC_SORCERER_L2_CANTRIP_EXPANSION_SETUP,
    BATTLE_MAGIC_WIZARD_L1_WIDEN,
    BATTLE_MAGIC_WIZARD_L1_WIDEN_REACTION_SETUP,
    BATTLE_MAGIC_WIZARD_L1_WIDEN_SETUP,
    STORM_DRUID_L1_WIDEN,
    STORM_DRUID_L1_WIDEN_SETUP,
    W3_CASTER_DEFINITIONS,
    W3_CASTER_SETUPS,
)
from pf2e.widen_spell import widened_cone_length
from terminal_test_helpers import BoundedInput, BoundedTranscript


def _settle_to_turn(game: Encounter, actor_id: str) -> None:
    while game.inspect().choice is not None:
        choice = game.inspect().choice
        assert choice is not None
        assert game.choose(
            choice.choice_id, choice.options[0].option_id, choice.owner_actor_id
        ).status in {ResultStatus.PAUSED, ResultStatus.COMPLETED}
    while game.inspect().turn_actor_id != actor_id:
        assert game.execute(EndTurn()).status is ResultStatus.COMPLETED


def test_w3_caster_content_is_public_and_preserves_legal_feat_boundaries() -> None:
    assert {definition.definition_id for definition in W3_CASTER_DEFINITIONS} == {
        "wizard_battle_magic_level_1_widen_spell",
        "storm_druid_level_1_widen_spell",
        "sorcerer_angelic_level_2_cantrip_expansion",
    }
    assert {setup.setup_id for setup in W3_CASTER_SETUPS} == {
        "wizard_battle_magic_level_1_widen_spell",
        "wizard_battle_magic_level_1_widen_spell_reaction",
        "storm_druid_level_1_widen_spell",
        "angelic_sorcerer_level_2_cantrip_expansion",
    }
    for definition in (BATTLE_MAGIC_WIZARD_L1_WIDEN, STORM_DRUID_L1_WIDEN):
        assert {"Widen Spell", "Natural Ambition"} <= set(definition.feats)
        assert "Natural Skill" not in definition.feats
        assert "widen_spell" in definition.abilities

    cantrips = {
        spell.spell_id
        for spell in ANGELIC_SORCERER_L2_CANTRIP_EXPANSION.spontaneous_spells
        if spell.cantrip
    }
    assert {"daze", "forbidding_ward"} <= cantrips
    assert ANGELIC_SORCERER_L2_CANTRIP_EXPANSION.spontaneous_slots[0].capacity == 4
    assert "Cantrip Expansion" in ANGELIC_SORCERER_L2_CANTRIP_EXPANSION.feats


def test_widen_spell_pure_contract_is_finite_and_source_shaped() -> None:
    assert widened_cone_length(SPELLS["breathe_fire"], spell_actions=2) == 20
    assert widened_cone_length(SPELLS["breathe_fire"], spell_actions=1) is None
    assert widened_cone_length(SPELLS["gale_blast"], spell_actions=2) is None
    with pytest.raises(TypeError, match="SpellDefinition"):
        widened_cone_length(object(), spell_actions=2)  # type: ignore[arg-type]


@pytest.mark.parametrize(
    ("setup", "actor_id", "target_id", "slot_id"),
    (
        (BATTLE_MAGIC_WIZARD_L1_WIDEN_SETUP, "wizard", "wizard_far_target", "wizard_breathe_fire"),
        (STORM_DRUID_L1_WIDEN_SETUP, "druid", "druid_far_target", "druid_breathe_fire_two"),
    ),
)
def test_widen_spell_extends_the_same_breathe_fire_cone_for_two_classes(
    setup, actor_id, target_id, slot_id,
) -> None:
    game = Encounter.start(setup, rolls=(20, 1, 4, 4, 1, 1))
    _settle_to_turn(game, actor_id)
    actor = game._state.creatures[actor_id]

    assert game._breathe_fire_targets(game._state, actor, Position(1, 0)) == ()
    assert "widen_spell" in game.options().available_actions
    assert game.execute(WidenSpell()).status is ResultStatus.COMPLETED
    actor = game._state.creatures[actor_id]
    assert actor.widen_spell_pending
    assert "widen_spell" not in game.options().available_actions
    assert game.execute(WidenSpell()).status is ResultStatus.REJECTED

    widened = game.execute(Cast(
        "breathe_fire", actions=2, area_direction=Position(1, 0), slot_id=slot_id,
    ))
    assert widened.status is ResultStatus.COMPLETED
    assert not game._state.creatures[actor_id].widen_spell_pending
    assert any(
        event.kind == "spell_damage" and event.target_id == target_id
        for event in widened.events
    )


def test_widen_spell_marker_round_trips_and_an_intervening_action_clears_it(tmp_path) -> None:
    game = Encounter.start(BATTLE_MAGIC_WIZARD_L1_WIDEN_SETUP, rolls=(20, 1))
    _settle_to_turn(game, "wizard")
    assert game.execute(WidenSpell()).status is ResultStatus.COMPLETED
    path = tmp_path / "widen-pending.json"
    game.save(path)
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["state"]["creatures"]["wizard"]["widen_spell_pending"] is True
    loaded = Encounter.load(path)
    assert loaded._state.creatures["wizard"].widen_spell_pending

    assert loaded.execute(EndTurn()).status is ResultStatus.COMPLETED
    assert not loaded._state.creatures["wizard"].widen_spell_pending


def test_widen_spell_reactive_strike_prompt_round_trips_then_declines(tmp_path) -> None:
    game = Encounter.start(BATTLE_MAGIC_WIZARD_L1_WIDEN_REACTION_SETUP, rolls=(20, 1, 1))
    _settle_to_turn(game, "wizard")
    paused = game.execute(WidenSpell())
    assert paused.status is ResultStatus.PAUSED
    choice = paused.inspection.choice
    assert choice is not None and choice.kind == "reaction"
    assert choice.owner_actor_id == "reactive_fighter"

    path = tmp_path / "widen-reaction.json"
    game.save(path)
    restored = Encounter.load(path)
    assert restored.inspect() == paused.inspection
    completed = restored.choose(choice.choice_id, "decline")
    assert completed.status is ResultStatus.COMPLETED
    assert any(event.kind == "reaction_declined" for event in completed.events)
    assert restored._state.creatures["wizard"].widen_spell_pending


def test_critical_reactive_strike_disrupts_widen_before_its_marker_is_ready() -> None:
    game = Encounter.start(BATTLE_MAGIC_WIZARD_L1_WIDEN_REACTION_SETUP, rolls=(20, 1, 1, 20, 1))
    _settle_to_turn(game, "wizard")
    paused = game.execute(WidenSpell())
    choice = paused.inspection.choice
    assert paused.status is ResultStatus.PAUSED and choice is not None
    reaction = game.choose(choice.choice_id, "accept")
    hero_choice = reaction.inspection.choice
    assert reaction.status is ResultStatus.PAUSED and hero_choice is not None
    result = game.choose(hero_choice.choice_id, "keep")
    assert result.status is ResultStatus.COMPLETED
    assert any(event.kind == "disrupted" for event in result.events)
    assert not game._state.creatures["wizard"].widen_spell_pending
    assert game._state.creatures["wizard"].actions_remaining == 2


def test_druid_widen_alternative_has_a_real_extra_finite_preparation_choice() -> None:
    widened_slot = next(slot for slot in STORM_DRUID_L1_WIDEN.prepared_spells if not slot.cantrip)
    ordinary_slot = next(slot for slot in STORM_DRUID.prepared_spells if not slot.cantrip)
    assert "breathe_fire" in preparation_choices(STORM_DRUID_L1_WIDEN, widened_slot)
    assert "breathe_fire" not in preparation_choices(STORM_DRUID, ordinary_slot)
    assert prepared_slot_rejection(None, STORM_DRUID_L1_WIDEN, widened_slot, "breathe_fire") is None
    assert prepared_slot_rejection(None, STORM_DRUID, ordinary_slot, "breathe_fire") is not None


def test_spontaneous_cantrip_expansion_casts_its_new_repertoire_cantrips() -> None:
    daze_game = Encounter.start(
        ANGELIC_SORCERER_L2_CANTRIP_EXPANSION_SETUP,
        rolls=(20, 1, 1, 4, 4, 4),
    )
    _settle_to_turn(daze_game, "angelic_sorcerer")
    daze = daze_game.execute(Cast("daze", target_id="sorcerer_target"))
    assert daze.status is ResultStatus.COMPLETED
    assert any(event.kind == "spell_damage" and "Daze" in event.text for event in daze.events)
    assert daze_game._state.creatures["angelic_sorcerer"].spontaneous_slots[0].remaining == 4

    ward_game = Encounter.start(
        ANGELIC_SORCERER_L2_CANTRIP_EXPANSION_SETUP, rolls=(20, 1, 1),
    )
    _settle_to_turn(ward_game, "angelic_sorcerer")
    ward = ward_game.execute(Cast(
        "forbidding_ward", target_ids=("sorcerer_ally", "sorcerer_target"),
    ))
    assert ward.status is ResultStatus.COMPLETED
    effect = next(effect for effect in ward_game._state.active_effects if effect.kind == "forbidding_ward")
    assert (effect.target_actor_id, effect.selected_enemy_actor_id) == ("sorcerer_ally", "sorcerer_target")


def test_terminal_offers_widen_spell_then_casts_the_widened_cone() -> None:
    transcript = BoundedTranscript(max_lines=300, max_chars=50_000)
    state = {"menu": "", "prompt": "", "phase": "widen"}

    def output(line: str) -> None:
        transcript.append(line)
        if line.startswith("1. "):
            state["menu"] = line
        if line.endswith(":"):
            state["prompt"] = line

    def choose(label: str, *, prefix: bool = False) -> str:
        for row in state["menu"].splitlines():
            number, text = row.split(". ", 1)
            if text.startswith(label) if prefix else text == label:
                return number
        raise AssertionError(f"missing terminal menu item {label!r}: {state['menu']!r}")

    def scripted_input() -> str:
        prompt = state["prompt"]
        if prompt == "Choice prompt action:":
            return choose("Resolve this choice")
        if prompt == "Choice option number:":
            return choose("Keep initiative")
        if prompt == "Choice:":
            if state["phase"] == "widen":
                state["phase"] = "cast"
                return choose("Widen Spell")
            if state["phase"] == "cast":
                state["phase"] = "quit"
                return choose("Cast")
            return choose("Quit")
        if prompt == "Spell number:":
            return choose("Breathe Fire", prefix=True)
        if prompt == "Casting mode:":
            return choose("2 actions")
        if prompt == "Prepared slot:":
            return "1"
        if prompt == "Breathe Fire direction:":
            return choose("East")
        raise AssertionError(f"unexpected terminal prompt: {prompt!r}")

    assert run_terminal(
        setup=BATTLE_MAGIC_WIZARD_L1_WIDEN_SETUP,
        rolls=(20, 1, 4, 4, 1, 1),
        input_fn=BoundedInput(scripted_input, max_calls=35),
        output_fn=output,
    ) == 0
    rendered = "\n".join(transcript)
    assert "Rejected:" not in rendered, rendered
    assert "shapes their next eligible area spell with Widen Spell" in rendered
    assert "commits Breathe Fire" in rendered
