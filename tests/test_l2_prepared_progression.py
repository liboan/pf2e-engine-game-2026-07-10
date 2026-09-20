"""Public-sheet and casting probes for the prepared-caster first-wave slice."""

from __future__ import annotations

from dataclasses import replace
from types import MappingProxyType

import pytest

import pf2e.content as content
from pf2e.encounter import Encounter
from pf2e.l2_prepared_content import (
    BATTLE_MAGIC_WIZARD_L1_REACH,
    BATTLE_MAGIC_WIZARD_L1_REACH_SETUP,
    BATTLE_MAGIC_WIZARD_L2_CANTRIP_EXPANSION,
    BATTLE_MAGIC_WIZARD_L2_CANTRIP_EXPANSION_SETUP,
    FAITHS_FLAMEKEEPER_WITCH_L1_REACH,
    FAITHS_FLAMEKEEPER_WITCH_L1_REACH_SETUP,
    FAITHS_FLAMEKEEPER_FOX_L2,
    FAITHS_FLAMEKEEPER_WITCH_L2_CANTRIP_EXPANSION,
    FAITHS_FLAMEKEEPER_WITCH_L2_CANTRIP_EXPANSION_SETUP,
    L2_PREPARED_DEFINITIONS,
    L2_PREPARED_SETUPS,
)
from pf2e.model import Cast, Choose, EndTurn, Position, ReachSpell, ResultStatus
from pf2e.terminal import run_terminal
from pf2e.witch import CommandFamiliar, FamiliarStride
from terminal_test_helpers import BoundedInput, BoundedTranscript


def _register(monkeypatch: pytest.MonkeyPatch) -> None:
    """Expose the class-local literals without changing the public catalogue."""
    monkeypatch.setattr(
        content,
        "_STAGED_CREATURES",
        MappingProxyType({
            **content._STAGED_CREATURES,
            **{definition.definition_id: definition for definition in L2_PREPARED_DEFINITIONS},
        }),
    )
    monkeypatch.setattr(
        content,
        "_STAGED_SETUPS",
        MappingProxyType({
            **content._STAGED_SETUPS,
            **{setup.setup_id: setup for setup in L2_PREPARED_SETUPS},
        }),
    )


def _settle_start_choices(game: Encounter) -> None:
    while (choice := game.inspect().choice) is not None:
        assert game.execute(
            Choose(choice.choice_id, choice.options[0].option_id, choice.owner_actor_id)
        ).status in {ResultStatus.PAUSED, ResultStatus.COMPLETED}


@pytest.mark.parametrize(
    ("definition", "hp", "cantrips", "rank_one", "level_up_spells"),
    (
        (BATTLE_MAGIC_WIZARD_L2_CANTRIP_EXPANSION, 24, 8, 4, {"detect_magic", "sigil"}),
        (FAITHS_FLAMEKEEPER_WITCH_L2_CANTRIP_EXPANSION, 24, 7, 3, {"harm", "protection"}),
    ),
)
def test_selected_l2_prepared_sheets_apply_actual_slot_and_stat_deltas(
    definition, hp, cantrips, rank_one, level_up_spells
) -> None:
    assert (definition.level, definition.hp, definition.ac, definition.perception) == (2, hp, 16, 4)
    assert (definition.class_dc, definition.spell_attack, definition.spell_dc) == (18, 8, 18)
    assert "Cantrip Expansion" in definition.feats
    # Skill feat coverage is deliberately distinct from the class-feat menu.
    assert "Assurance (Athletics)" in definition.feats
    assert sum(slot.cantrip for slot in definition.prepared_spells) == cantrips
    assert sum(not slot.cantrip for slot in definition.prepared_spells) == rank_one
    if definition is BATTLE_MAGIC_WIZARD_L2_CANTRIP_EXPANSION:
        assert level_up_spells <= {entry.spell_id for entry in definition.spell_substitution_book}
        notes = " ".join(definition.sheet_notes)
        assert "thirteen cantrips and seven rank-1 spells" in notes
        assert "eleven cantrips and seven rank-1 spells" not in notes
    else:
        assert level_up_spells <= {
            slot.spell_id for slot in definition.prepared_spells if not slot.cantrip
        }
        notes = " ".join(definition.sheet_notes)
        assert "ten divine cantrips and eight rank-1 spells" in notes
        assert "six rank-1 spells" not in notes


def test_witch_l2_familiar_learns_and_prepares_two_new_divine_rank_one_spells() -> None:
    from pf2e.witch import preparation_choices

    witch = FAITHS_FLAMEKEEPER_WITCH_L2_CANTRIP_EXPANSION
    rank_one_slot = next(slot for slot in witch.prepared_spells if not slot.cantrip)
    choices = preparation_choices(witch, rank_one_slot)
    assert {"harm", "protection"} <= set(choices)
    prepared = {slot.spell_id for slot in witch.prepared_spells if not slot.cantrip}
    assert {"harm", "protection"} <= prepared


def test_witch_l2_setup_uses_scaled_pet_fox_and_round_trips_a_public_command(
    monkeypatch: pytest.MonkeyPatch, tmp_path,
) -> None:
    _register(monkeypatch)
    game = Encounter.start(FAITHS_FLAMEKEEPER_WITCH_L2_CANTRIP_EXPANSION_SETUP, rolls=(20, 1))
    _settle_start_choices(game)
    fox = game._state.creatures["fox"]
    assert fox.definition_id == FAITHS_FLAMEKEEPER_FOX_L2.definition_id
    assert (fox.hp, fox.position) == (14, FAITHS_FLAMEKEEPER_WITCH_L2_CANTRIP_EXPANSION_SETUP.placements[1].position)
    assert (FAITHS_FLAMEKEEPER_FOX_L2.level, FAITHS_FLAMEKEEPER_FOX_L2.ac, FAITHS_FLAMEKEEPER_FOX_L2.perception) == (2, 16, 6)
    assert {modifier for _name, _rank, modifier in FAITHS_FLAMEKEEPER_FOX_L2.saves} == {6}
    assert dict((name, modifier) for name, _rank, modifier in FAITHS_FLAMEKEEPER_FOX_L2.skills)["acrobatics"] == 6
    assert dict((name, modifier) for name, _rank, modifier in FAITHS_FLAMEKEEPER_FOX_L2.skills)["arcana"] == 2

    command = game.execute(CommandFamiliar("fox", (FamiliarStride((Position(0, 2),)),)))
    assert command.status in {ResultStatus.COMPLETED, ResultStatus.PAUSED}
    _settle_start_choices(game)
    assert game._state.creatures["fox"].position == Position(0, 2)
    save_path = tmp_path / "witch-l2-fox.json"
    game.save(save_path)
    loaded = Encounter.load(save_path)
    assert loaded._state.creatures["fox"].definition_id == FAITHS_FLAMEKEEPER_FOX_L2.definition_id


def test_level_one_witch_and_reach_variant_reject_the_l2_familiar_spells_on_prepare_and_load(
    monkeypatch: pytest.MonkeyPatch, tmp_path,
) -> None:
    from pf2e.preparation import prepared_slot_rejection
    from pf2e.witch import preparation_choices
    from pf2e.witch_content import FAITHS_FLAMEKEEPER_WITCH

    for definition in (FAITHS_FLAMEKEEPER_WITCH, FAITHS_FLAMEKEEPER_WITCH_L1_REACH):
        rank_one_slot = next(slot for slot in definition.prepared_spells if not slot.cantrip)
        assert {"harm", "protection"}.isdisjoint(preparation_choices(definition, rank_one_slot))
        assert prepared_slot_rejection(None, definition, rank_one_slot, "harm") is not None

    _register(monkeypatch)
    game = Encounter.start(FAITHS_FLAMEKEEPER_WITCH_L1_REACH_SETUP, rolls=(20, 1))
    _settle_start_choices(game)
    witch = game._state.creatures["witch"]
    target_slot = next(slot for slot in witch.prepared_slots if not slot.cantrip)
    witch.prepared_slots = [
        replace(slot, spell_id="harm") if slot.slot_id == target_slot.slot_id else slot
        for slot in witch.prepared_slots
    ]
    save_path = tmp_path / "invalid-level-one-witch-harm.json"
    game.save(save_path)
    with pytest.raises(ValueError, match="prepared spells outside finite choices"):
        Encounter.load(save_path)


def test_wizard_l2_cantrip_expansion_uses_its_new_supported_prepared_spell_and_round_trips(
    monkeypatch: pytest.MonkeyPatch, tmp_path,
) -> None:
    _register(monkeypatch)
    game = Encounter.start(BATTLE_MAGIC_WIZARD_L2_CANTRIP_EXPANSION_SETUP, rolls=(20, 1, 10, 1))
    _settle_start_choices(game)
    assert game.inspect().turn_actor_id == "wizard"
    # The new literal slots must be accepted by the existing save/load policy
    # before their first cast. (A live Wizard Sigil has a separate, named
    # shared persistence-validation defect handed to the integration owner.)
    save_path = tmp_path / "wizard-l2-cantrip-expansion.json"
    game.save(save_path)
    loaded = Encounter.load(save_path)
    loaded_wizard = loaded._state.creatures["wizard"]
    assert loaded_wizard.definition_id == BATTLE_MAGIC_WIZARD_L2_CANTRIP_EXPANSION.definition_id
    assert tuple(loaded_wizard.prepared_slots) == tuple(game._state.creatures["wizard"].prepared_slots)

    cast = game.execute(Cast("sigil", target_id="wizard"))
    assert cast.status is ResultStatus.COMPLETED
    assert any(event.kind == "sigil_marked" for event in cast.events)
    # Cantrips never spend a rank-one resource; all four rank-one slots stay live.
    wizard = game._state.creatures["wizard"]
    assert sum(not slot.cantrip and not slot.spent for slot in wizard.prepared_slots) == 4

    detect_game = Encounter.start(BATTLE_MAGIC_WIZARD_L2_CANTRIP_EXPANSION_SETUP, rolls=(20, 1))
    _settle_start_choices(detect_game)
    detect = detect_game.execute(Cast("detect_magic"))
    assert detect.status is ResultStatus.PAUSED
    choice = detect_game.inspect().choice
    assert choice is not None and choice.kind == "detect_magic_known"
    resolved = detect_game.execute(Choose(choice.choice_id, "ignore_known", choice.owner_actor_id))
    assert resolved.status is ResultStatus.COMPLETED
    assert any(event.kind in {"detect_magic_present", "detect_magic_absent"} for event in resolved.events)


def test_witch_l2_cantrip_expansion_uses_its_added_void_warp_preparation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _register(monkeypatch)
    game = Encounter.start(FAITHS_FLAMEKEEPER_WITCH_L2_CANTRIP_EXPANSION_SETUP, rolls=(20, 1, 1, 4, 4, 4, 4))
    _settle_start_choices(game)
    assert game.inspect().turn_actor_id == "witch"

    cast = game.execute(Cast("void_warp", target_id="witch_target"))
    assert cast.status is ResultStatus.COMPLETED
    assert any(event.kind == "spell_damage" and "Void Warp" in event.text for event in cast.events)
    witch = game._state.creatures["witch"]
    assert sum(not slot.cantrip and not slot.spent for slot in witch.prepared_slots) == 3


def test_witch_l2_new_divine_spells_cast_and_protection_survives_save_load(
    monkeypatch: pytest.MonkeyPatch, tmp_path,
) -> None:
    _register(monkeypatch)
    setup = FAITHS_FLAMEKEEPER_WITCH_L2_CANTRIP_EXPANSION_SETUP

    harm_game = Encounter.start(setup, rolls=(20, 1, 1, 8))
    _settle_start_choices(harm_game)
    harm = harm_game.execute(Cast("harm", target_id="witch_target"))
    assert harm.status is ResultStatus.COMPLETED
    assert any(event.kind == "spell_save" for event in harm.events)
    assert any(event.kind == "spell_damage" and "Harm" in event.text for event in harm.events)
    assert sum(
        not slot.cantrip and not slot.spent
        for slot in harm_game._state.creatures["witch"].prepared_slots
    ) == 2

    protection_game = Encounter.start(setup, rolls=(20, 1))
    _settle_start_choices(protection_game)
    protection = protection_game.execute(Cast("protection", target_id="witch"))
    assert protection.status is ResultStatus.COMPLETED
    assert any(event.kind == "protection_applied" for event in protection.events)
    effect = next(effect for effect in protection_game._state.active_effects if effect.kind == "protection")
    assert (effect.source_actor_id, effect.target_actor_id, effect.value) == ("witch", "witch", 1)

    save_path = tmp_path / "witch-l2-protection.json"
    protection_game.save(save_path)
    loaded = Encounter.load(save_path)
    loaded_effect = next(effect for effect in loaded._state.active_effects if effect.kind == "protection")
    assert loaded_effect == effect
    assert loaded._effective_ac(loaded._state.creatures["witch"], state=loaded._state) == 17


def test_witch_l2_protection_recovers_cleanly_at_its_printed_one_minute_boundary(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _register(monkeypatch)
    game = Encounter.start(FAITHS_FLAMEKEEPER_WITCH_L2_CANTRIP_EXPANSION_SETUP, rolls=(20, 1))
    _settle_start_choices(game)
    assert game.execute(Cast("protection", target_id="witch")).status is ResultStatus.COMPLETED

    # The shared effect policy represents the spell's one-minute duration as
    # ten source turns and 60 world seconds. Walk both sides through exactly
    # that public turn boundary; nothing is manually removed.
    for _ in range(20):
        if not any(effect.kind == "protection" for effect in game._state.active_effects):
            break
        assert game.execute(EndTurn()).status in {ResultStatus.COMPLETED, ResultStatus.PAUSED}
        _settle_start_choices(game)
    assert not any(effect.kind == "protection" for effect in game._state.active_effects)


def test_terminal_offers_and_casts_the_admitted_witch_l2_protection() -> None:
    setup = content.get_setup(FAITHS_FLAMEKEEPER_WITCH_L2_CANTRIP_EXPANSION_SETUP.setup_id)
    transcript = BoundedTranscript(max_lines=300, max_chars=50_000)
    state = {"menu": "", "prompt": "", "cast": True}

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
            if state["cast"]:
                state["cast"] = False
                return choose("Cast")
            return choose("Quit")
        if prompt == "Spell number:":
            return choose("Protection", prefix=True)
        if prompt == "Casting mode:":
            return choose("2 actions")
        if prompt == "Prepared slot:":
            return "1"
        if prompt == "Target number:":
            return "1"  # The witch is its own willing touch-range target.
        raise AssertionError(f"unexpected terminal prompt: {prompt!r}")

    assert run_terminal(
        setup=setup,
        rolls=(20, 1),
        input_fn=BoundedInput(scripted_input, max_calls=35), output_fn=output,
    ) == 0
    rendered = "\n".join(transcript)
    assert "Rejected:" not in rendered, rendered
    assert "commits Protection" in rendered
    assert "gains +1 status to AC and all saves for 1 minute" in rendered


@pytest.mark.parametrize(
    ("setup", "actor_id", "spell_id", "target_id", "spell_mode"),
    (
        (BATTLE_MAGIC_WIZARD_L1_REACH_SETUP, "wizard", "enfeeble", "wizard_target", None),
        (FAITHS_FLAMEKEEPER_WITCH_L1_REACH_SETUP, "witch", "command", "witch_target", "stand"),
    ),
)
def test_human_natural_ambition_l1_reach_alternatives_use_the_existing_spellshape(
    monkeypatch: pytest.MonkeyPatch, setup, actor_id, spell_id, target_id, spell_mode,
) -> None:
    _register(monkeypatch)
    game = Encounter.start(setup, rolls=(20, 1, 10, 1))
    _settle_start_choices(game)
    assert game.inspect().turn_actor_id == actor_id

    assert game.execute(ReachSpell()).status is ResultStatus.COMPLETED
    result = game.execute(Cast(spell_id, target_id=target_id, spell_mode=spell_mode))
    assert result.status is ResultStatus.COMPLETED
    assert not game._state.creatures[actor_id].reach_spell_pending


def test_reach_alternatives_trade_natural_skill_for_human_natural_ambition() -> None:
    for definition in (BATTLE_MAGIC_WIZARD_L1_REACH, FAITHS_FLAMEKEEPER_WITCH_L1_REACH):
        assert {"Natural Ambition", "Reach Spell"} <= set(definition.feats)
        assert "Natural Skill" not in definition.feats
        assert {"athletics", "acrobatics"}.isdisjoint({skill for skill, _rank, _modifier in definition.skills})
        notes = " ".join(definition.sheet_notes)
        assert "Natural Skill grants Athletics and Acrobatics" not in notes
        assert "Natural Ambition selects Reach Spell in place of Natural Skill" in notes
