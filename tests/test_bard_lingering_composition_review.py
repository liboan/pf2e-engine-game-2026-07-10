"""Independent source/play review of Maestro Lingering Composition.

Sources checked 2026-09-16:

* Bard, Composition, and Spellshape: https://2e.aonprd.com/Classes.aspx?ID=32
* Maestro muse: https://2e.aonprd.com/Muses.aspx
* Lingering Composition feat: https://2e.aonprd.com/Feats.aspx?ID=4575
* Lingering Composition spell: https://2e.aonprd.com/Spells.aspx?ID=1769
* Focus spells: https://2e.aonprd.com/Rules.aspx?ID=2228
* Level-based DCs: https://2e.aonprd.com/Rules.aspx?ID=2629
* Bard spell repertoire: https://2e.aonprd.com/Classes.aspx?ID=32
* Forbidding Ward: https://2e.aonprd.com/Spells.aspx?ID=1535
* Shield: https://2e.aonprd.com/Spells.aspx?ID=1671
* Fear: https://2e.aonprd.com/Spells.aspx?ID=1524
* Stabilize: https://2e.aonprd.com/Spells.aspx?ID=1689

The source numbers are Performance against the standard DC for the highest
affected target (level 1 DC 15; level 2 DC 16), with 4 rounds on critical
success, 3 on success, and 1 on failure or critical failure. Failure does not
spend Lingering's Focus Point. The selected Bard's Performance modifier is +7,
so d20 results 20/8/7/1 against DC 15 demonstrate those four outcomes. Bard
grants Counter Performance and a one-point pool; Maestro's Lingering feat adds
a second qualifying focus spell, so the level-1 build's pool maximum is 2.
"""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from types import MappingProxyType

import pytest

import pf2e.content as content
import pf2e.encounter as encounter_module
from pf2e.bard_content import MAESTRO_BARD_ANTHEM_SETUP, MAESTRO_BARD_STAGED
from pf2e.encounter import Encounter
from pf2e.model import (
    Cast,
    CreaturePlacement,
    DismissCover,
    EndTurn,
    EncounterSetup,
    LingeringComposition,
    Position,
    ResultStatus,
    Step,
    Strike,
    TakeCover,
)
from pf2e.skill_actions import Trip
from pf2e.spells import SPELLS
from pf2e.terminal import run_terminal
from terminal_test_helpers import BoundedInput, BoundedTranscript


def _settle_start_choices(game: Encounter) -> None:
    for _ in range(10):
        choice = game.inspect().choice
        if choice is None:
            return
        option_ids = {option.option_id for option in choice.options}
        option_id = "keep" if "keep" in option_ids else choice.options[0].option_id
        result = game.choose(choice.choice_id, option_id, choice.owner_actor_id)
        assert result.status in {ResultStatus.PAUSED, ResultStatus.COMPLETED}
    raise AssertionError("initiative choices did not settle")


def _finish_keep_choices(game: Encounter, result):
    for _ in range(10):
        if result.status is not ResultStatus.PAUSED:
            return result
        choice = result.inspection.choice
        assert choice is not None
        option_ids = {option.option_id for option in choice.options}
        assert "keep" in option_ids
        result = game.choose(choice.choice_id, "keep", choice.owner_actor_id)
    raise AssertionError("action choices did not settle")


def _advance_to_start(game: Encounter, actor_id: str, start_count: int) -> None:
    for _ in range(20):
        if (
            game.inspect().turn_actor_id == actor_id
            and game._state.actor_start_counts[actor_id] == start_count
        ):
            return
        assert game.execute(EndTurn()).status is ResultStatus.COMPLETED
    raise AssertionError(f"did not reach {actor_id} start {start_count}")


def test_selected_maestro_has_two_chosen_rank_one_spells_plus_muse_soothe() -> None:
    # Player Core's level-1 repertoire grants two chosen rank-1 occult spells.
    # Maestro then adds Soothe to that repertoire; it does not replace either
    # choice. The selected build uses Fear and Runic Weapon for those choices.
    ordinary_cantrips = {
        spell.spell_id
        for spell in MAESTRO_BARD_STAGED.spontaneous_spells
        if spell.cantrip and spell.spell_id != "courageous_anthem"
    }
    rank_one_spells = {
        spell.spell_id
        for spell in MAESTRO_BARD_STAGED.spontaneous_spells
        if not spell.cantrip
    }

    assert ordinary_cantrips == {
        "light",
        "guidance",
        "void_warp",
        "forbidding_ward",
        "shield",
    }
    assert rank_one_spells == {"fear", "runic_weapon", "soothe"}
    assert MAESTRO_BARD_STAGED.spontaneous_slots[0].capacity == 2
    assert {spell.spell_id for spell in MAESTRO_BARD_STAGED.focus_spells} == {
        "counter_performance",
        "lingering_composition",
    }
    assert (MAESTRO_BARD_STAGED.focus_points, MAESTRO_BARD_STAGED.focus_capacity) == (2, 2)


def test_selected_maestro_sheet_grants_are_legal_and_literal() -> None:
    definition = MAESTRO_BARD_STAGED
    assert (
        definition.ancestry,
        definition.heritage,
        definition.background,
        definition.class_name,
    ) == ("Human", "Versatile Human", "Farmhand", "Bard")
    assert (definition.perception, definition.land_speed_ft, definition.vision) == (5, 30, "ordinary")
    assert {
        statistic: (rank, modifier)
        for statistic, rank, modifier in definition.saves
    }["will"] == ("expert", 5)
    assert {
        statistic: (rank, modifier)
        for statistic, rank, modifier in definition.skills
        if statistic in {"athletics", "farming_lore", "medicine", "society"}
    } == {
        "athletics": ("trained", 4),
        "farming_lore": ("trained", 3),
        "medicine": ("trained", 3),
        "society": ("trained", 3),
    }
    assert {"Fleet", "Natural Skill", "Assurance (Athletics)"} <= set(definition.feats)
    assert (definition.hero_points, definition.held_items) == (1, ("rapier",))
    assert SPELLS["fear"].traits == frozenset({
        "concentrate", "emotion", "fear", "manipulate", "mental",
    })


def test_assurance_then_fear_uses_public_maneuver_reaction_save_and_resources(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    setup = EncounterSetup(
        setup_id="review_bard_assurance_fear",
        name="Review Bard Assurance and Fear",
        width=4,
        height=3,
        placements=(
            CreaturePlacement(
                "maestro_bard", MAESTRO_BARD_STAGED.definition_id,
                "Maestro Bard", "blue", Position(1, 1),
            ),
            CreaturePlacement(
                "reactive_fighter", "fighter_m_level_1",
                "Reactive Fighter", "red", Position(2, 1),
            ),
        ),
    )
    monkeypatch.setattr(
        content,
        "_STAGED_SETUPS",
        MappingProxyType({**content._STAGED_SETUPS, setup.setup_id: setup}),
    )
    game = Encounter.start(setup, rolls=(20, 1, 8))
    _settle_start_choices(game)
    bard_view = next(actor for actor in game.inspect().actors if actor.actor_id == "maestro_bard")
    assert bard_view.held_items == ("rapier",)
    assert "trip_assurance" in game.options().available_actions
    assert any(strike.attack_id == "rapier" for strike in game.options().strikes)

    trip = game.execute(Trip("reactive_fighter", use_assurance=True))
    check = next(event.check for event in trip.events if event.kind == "trip_check")
    assert trip.status is ResultStatus.COMPLETED
    assert check is not None
    assert (check.method, check.die, check.modifier, check.total) == (
        "assurance", None, 3, 13,
    )

    fear = game.execute(Cast("fear", "reactive_fighter", slot_id="bard_rank1"))
    assert fear.status is ResultStatus.PAUSED
    reaction = fear.inspection.choice
    assert reaction is not None and reaction.kind == "reaction"
    assert reaction.owner_actor_id == "reactive_fighter"
    reaction_path = tmp_path / "bard-fear-reaction.json"
    game.save(reaction_path)
    game = Encounter.load(reaction_path)
    fear_save = game.choose(reaction.choice_id, "decline", reaction.owner_actor_id)
    assert fear_save.status is ResultStatus.PAUSED
    hero = fear_save.inspection.choice
    assert hero is not None and hero.kind == "spell_save_hero_reroll"
    resolved = game.choose(hero.choice_id, "keep", hero.owner_actor_id)
    save_event = next(event for event in resolved.events if event.kind == "spell_save")
    assert resolved.status is ResultStatus.COMPLETED
    assert save_event.check is not None and save_event.check.die == 8
    assert any(
        effect.kind == "frightened"
        and effect.target_actor_id == "reactive_fighter"
        and effect.value == 2
        for effect in game._state.condition_effects
    )
    assert game._state.creatures["maestro_bard"].spontaneous_slots[0].remaining == 1


def test_legal_replacement_cantrips_execute_and_round_trip(
    tmp_path: Path,
) -> None:
    game = Encounter.start(MAESTRO_BARD_ANTHEM_SETUP, rolls=(20, 1, 1))
    _settle_start_choices(game)
    ward = game.execute(Cast(
        "forbidding_ward", target_ids=("bard_ally", "bard_dog"),
    ))
    assert ward.status is ResultStatus.COMPLETED
    shield = game.execute(Cast("shield"))
    assert shield.status is ResultStatus.COMPLETED
    bard = game._state.creatures["maestro_bard"]
    assert bard.magic_shield_expires_at_start == 2
    assert bard.reaction_available
    effect = next(item for item in game._state.active_effects if item.kind == "forbidding_ward")
    assert (effect.target_actor_id, effect.selected_enemy_actor_id, effect.value) == (
        "bard_ally", "bard_dog", 1,
    )

    path = tmp_path / "bard-replacement-cantrips.json"
    game.save(path)
    loaded = Encounter.load(path)
    loaded_bard = loaded._state.creatures["maestro_bard"]
    assert loaded_bard.held_items == ["rapier"]
    assert loaded_bard.magic_shield_expires_at_start == 2
    assert loaded_bard.reaction_available
    loaded_effect = next(
        item for item in loaded._state.active_effects if item.kind == "forbidding_ward"
    )
    assert loaded_effect == effect


def test_terminal_inspection_displays_corrected_selected_maestro_sheet() -> None:
    transcript = BoundedTranscript(max_lines=300, max_chars=75_000)
    state = {"menu": "", "prompt": "", "phase": "inspect"}

    def output(line: str) -> None:
        transcript.append(line)
        if line.startswith("1. "):
            state["menu"] = line
        elif state["menu"] and line[:1].isdigit() and ". " in line:
            state["menu"] += "\n" + line
        if line.endswith(":"):
            state["prompt"] = line

    def choose(label: str, *, prefix: bool = False) -> str:
        for row in state["menu"].splitlines():
            number, text = row.split(". ", 1)
            if text.startswith(label) if prefix else text == label:
                return number
        raise AssertionError(f"missing {label!r}: {state['menu']!r}")

    def scripted_input() -> str:
        prompt = state["prompt"]
        if prompt == "Choice prompt action:":
            return choose("Resolve this choice")
        if prompt == "Choice option number:":
            return choose("Keep", prefix=True)
        if prompt == "Choice:":
            if state["phase"] == "inspect":
                state["phase"] = "quit"
                return choose("Inspect", prefix=True)
            return choose("Quit")
        raise AssertionError(f"unexpected terminal prompt: {prompt!r}")

    assert run_terminal(
        setup=MAESTRO_BARD_ANTHEM_SETUP,
        rolls=(20, 1, 1),
        input_fn=BoundedInput(scripted_input, max_calls=20),
        output_fn=output,
    ) == 0
    rendered = "\n".join(transcript)
    assert "Identity: Human · Versatile Human · Farmhand · Bard" in rendered
    assert "Perception 5 · Speed 30 ft" in rendered
    assert "Will expert +5" in rendered
    assert "Athletics trained +4" in rendered
    assert "Medicine trained +3" in rendered
    assert "Held: rapier" in rendered


def test_actual_spent_bard_resources_restore_on_declared_daily_preparation(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    frail_dog = replace(
        content.GUARD_DOG,
        definition_id="review_bard_daily_prepare_dog",
        hp=1,
    )
    setup = EncounterSetup(
        setup_id="review_bard_daily_prepare",
        name="Review Bard Daily Preparation",
        width=4,
        height=3,
        placements=(
            CreaturePlacement(
                "maestro_bard", MAESTRO_BARD_STAGED.definition_id,
                "Maestro Bard", "blue", Position(1, 1),
            ),
            CreaturePlacement(
                "bard_dog", frail_dog.definition_id,
                "Guard Dog", "red", Position(2, 1),
            ),
        ),
    )
    monkeypatch.setattr(
        content,
        "_STAGED_CREATURES",
        MappingProxyType({**content._STAGED_CREATURES, frail_dog.definition_id: frail_dog}),
    )
    monkeypatch.setattr(
        content,
        "_STAGED_SETUPS",
        MappingProxyType({**content._STAGED_SETUPS, setup.setup_id: setup}),
    )
    game = Encounter.start(setup, rolls=(20, 1, 8, 20, 20, 1, 1))
    _settle_start_choices(game)
    assert game.execute(LingeringComposition()).status is ResultStatus.COMPLETED
    assert _finish_keep_choices(
        game, game.execute(Cast("courageous_anthem")),
    ).status is ResultStatus.COMPLETED
    assert game.execute(Cast("fear", "bard_dog", slot_id="bard_rank1")).status is ResultStatus.COMPLETED
    bard = game._state.creatures["maestro_bard"]
    assert (bard.focus_points, bard.spontaneous_slots[0].remaining) == (1, 1)

    assert game.inspect().turn_actor_id == "bard_dog"
    assert game.execute(EndTurn()).status is ResultStatus.COMPLETED
    assert game.inspect().turn_actor_id == "maestro_bard"
    victory = _finish_keep_choices(
        game, game.execute(Strike("bard_dog", attack_id="rapier")),
    )
    assert victory.status is ResultStatus.COMPLETED
    assert not victory.inspection.in_progress and victory.inspection.winner_team == "blue"

    assert game.record_rested(
        ("maestro_bard",), day_number=2, elapsed_seconds=1,
    ).status is ResultStatus.COMPLETED
    prepared = game.daily_prepare(("maestro_bard",))
    assert prepared.status is ResultStatus.COMPLETED
    bard = game._state.creatures["maestro_bard"]
    assert (bard.focus_points, bard.spontaneous_slots[0].remaining) == (2, 2)
    assert bard.held_items == ["rapier"]

    path = tmp_path / "bard-prepared.json"
    game.save(path)
    loaded = Encounter.load(path)
    loaded_bard = loaded._state.creatures["maestro_bard"]
    assert (loaded_bard.focus_points, loaded_bard.spontaneous_slots[0].remaining) == (2, 2)
    assert loaded_bard.held_items == ["rapier"]


@pytest.mark.parametrize(
    ("performance_die", "expected_rounds", "expected_focus"),
    ((20, 4, 1), (8, 3, 1), (7, 1, 2), (1, 1, 2)),
)
def test_source_outcomes_spend_once_or_refund_and_use_exact_expiry(
    performance_die: int,
    expected_rounds: int,
    expected_focus: int,
) -> None:
    game = Encounter.start(
        MAESTRO_BARD_ANTHEM_SETUP,
        rolls=(20, 1, 1, performance_die),
    )
    _settle_start_choices(game)
    bard = game._state.creatures["maestro_bard"]
    assert (bard.focus_points, bard.focus_capacity) == (2, 2)
    assert bard.composition_cast_at_start == 0

    assert game.execute(LingeringComposition()).status is ResultStatus.COMPLETED
    bard = game._state.creatures["maestro_bard"]
    assert (bard.focus_points, bard.composition_cast_at_start) == (1, 0)
    resolved = _finish_keep_choices(game, game.execute(Cast("courageous_anthem")))

    assert resolved.status is ResultStatus.COMPLETED
    bard = game._state.creatures["maestro_bard"]
    checks = [
        event.check
        for event in resolved.events
        if event.kind == "lingering_composition_resolved"
    ]
    assert len(checks) == 1
    assert checks[0] is not None
    assert (checks[0].modifier, checks[0].dc) == (7, 15)
    assert bard.focus_points == expected_focus
    assert {
        (effect.expires_at_source_start, effect.expires_at_world_time)
        for effect in game._state.active_effects
        if effect.kind == "courageous_anthem"
    } == {(1 + expected_rounds, expected_rounds * 6)}


def test_rejected_input_is_atomic_and_actual_step_wastes_spellshape() -> None:
    game = Encounter.start(MAESTRO_BARD_ANTHEM_SETUP, rolls=(20, 1, 1, 8))
    _settle_start_choices(game)
    bard = game._state.creatures["maestro_bard"]

    bard.focus_points = 0
    before, dice_before = game.inspect(), game._dice.to_data()
    rejected = game.execute(LingeringComposition())
    assert rejected.status is ResultStatus.REJECTED
    assert game.inspect() == before and game._dice.to_data() == dice_before

    bard.focus_points = 2
    assert game.execute(LingeringComposition()).status is ResultStatus.COMPLETED
    bard = game._state.creatures["maestro_bard"]
    before, dice_before = game.inspect(), game._dice.to_data()
    repeated = game.execute(LingeringComposition())
    assert repeated.status is ResultStatus.REJECTED
    assert game.inspect() == before and game._dice.to_data() == dice_before
    assert (bard.focus_points, bard.lingering_composition_pending) == (1, True)

    before, dice_before = game.inspect(), game._dice.to_data()
    rejected_step = game.execute(Step(Position(-1, 1)))
    assert rejected_step.status is ResultStatus.REJECTED
    assert game.inspect() == before and game._dice.to_data() == dice_before
    assert bard.lingering_composition_pending

    assert game.execute(Step(Position(1, 2))).status is ResultStatus.COMPLETED
    bard = game._state.creatures["maestro_bard"]
    assert not bard.lingering_composition_pending
    dice_before_cast = game._dice.to_data()
    cast = game.execute(Cast("courageous_anthem"))
    assert cast.status is ResultStatus.COMPLETED
    assert not any(
        event.kind.startswith("lingering_composition") for event in cast.events
    )
    assert game._dice.to_data() == dice_before_cast
    assert bard.focus_points == 1
    assert {
        effect.expires_at_source_start
        for effect in game._state.active_effects
        if effect.kind == "courageous_anthem"
    } == {2}


def test_intervening_free_action_wastes_spellshape() -> None:
    game = Encounter.start(MAESTRO_BARD_ANTHEM_SETUP, rolls=(20, 1, 1, 8))
    _settle_start_choices(game)
    game._state.creatures["maestro_bard"].prone = True
    assert game.execute(TakeCover()).status is ResultStatus.COMPLETED
    assert game.execute(LingeringComposition()).status is ResultStatus.COMPLETED
    assert game._state.creatures["maestro_bard"].lingering_composition_pending

    dismissed = game.execute(DismissCover())

    assert dismissed.status is ResultStatus.COMPLETED
    assert not game._state.creatures["maestro_bard"].lingering_composition_pending
    dice_before_cast = game._dice.to_data()
    cast = game.execute(Cast("courageous_anthem"))
    assert cast.status is ResultStatus.COMPLETED
    assert game._dice.to_data() == dice_before_cast
    assert not any(
        event.kind.startswith("lingering_composition") for event in cast.events
    )
    assert game._state.creatures["maestro_bard"].focus_points == 1


def test_saved_hero_reroll_keeps_cost_pending_then_uses_second_result(
    tmp_path: Path,
) -> None:
    # Initiatives; first Performance failure; Hero reroll success.
    game = Encounter.start(MAESTRO_BARD_ANTHEM_SETUP, rolls=(20, 1, 1, 7, 8))
    _settle_start_choices(game)
    bard = game._state.creatures["maestro_bard"]
    bard.hero_points = 1
    assert game.execute(LingeringComposition()).status is ResultStatus.COMPLETED
    paused = game.execute(Cast("courageous_anthem"))
    assert paused.status is ResultStatus.PAUSED
    bard = game._state.creatures["maestro_bard"]
    assert (bard.focus_points, bard.hero_points) == (1, 1)
    assert {
        effect.expires_at_source_start
        for effect in game._state.active_effects
        if effect.kind == "courageous_anthem"
    } == {2}

    path = tmp_path / "review-lingering-hero.json"
    game.save(path)
    game = Encounter.load(path)
    choice = game.inspect().choice
    assert choice is not None
    assert choice.kind == "lingering_composition_hero_reroll"
    assert "Lingering Composition Performance check" in choice.prompt
    assert {option.option_id for option in choice.options} == {
        "keep",
        "spend_hero_point",
    }
    saved_check = game._state.pending_choice.check
    assert saved_check is not None
    assert (saved_check.dice, saved_check.total, saved_check.dc) == ((7,), 14, 15)
    resolved = game.choose(choice.choice_id, "spend_hero_point", choice.owner_actor_id)

    assert resolved.status is ResultStatus.COMPLETED
    check = next(
        event.check
        for event in resolved.events
        if event.kind == "lingering_composition_resolved"
    )
    assert check is not None
    assert (check.dice, check.total, check.dc) == ((8,), 15, 15)
    bard = game._state.creatures["maestro_bard"]
    assert (bard.focus_points, bard.hero_points) == (1, 0)
    assert {
        effect.expires_at_source_start
        for effect in game._state.active_effects
        if effect.kind == "courageous_anthem"
    } == {4}


def test_saved_pending_spellshape_accepts_a_legally_depleted_focus_pool(
    tmp_path: Path,
) -> None:
    # Initiatives; first Performance success. The second use spends the pool's
    # remaining point before its qualifying composition is cast.
    game = Encounter.start(MAESTRO_BARD_ANTHEM_SETUP, rolls=(20, 1, 1, 8))
    _settle_start_choices(game)
    assert game.execute(LingeringComposition()).status is ResultStatus.COMPLETED
    assert _finish_keep_choices(
        game, game.execute(Cast("courageous_anthem")),
    ).status is ResultStatus.COMPLETED
    _advance_to_start(game, "maestro_bard", 4)
    assert game._state.creatures["maestro_bard"].focus_points == 1
    assert not any(
        effect.kind == "courageous_anthem" for effect in game._state.active_effects
    )
    assert game.execute(LingeringComposition()).status is ResultStatus.COMPLETED
    bard = game._state.creatures["maestro_bard"]
    assert (bard.focus_points, bard.lingering_composition_pending) == (0, True)

    path = tmp_path / "review-lingering-depleted-pending.json"
    game.save(path)
    loaded = Encounter.load(path)
    bard = loaded._state.creatures["maestro_bard"]
    assert (bard.focus_points, bard.lingering_composition_pending) == (0, True)


def test_resolved_extended_anthem_survives_save_with_exact_expiry(
    tmp_path: Path,
) -> None:
    game = Encounter.start(MAESTRO_BARD_ANTHEM_SETUP, rolls=(20, 1, 1, 8))
    _settle_start_choices(game)
    assert game.execute(LingeringComposition()).status is ResultStatus.COMPLETED
    assert _finish_keep_choices(
        game, game.execute(Cast("courageous_anthem")),
    ).status is ResultStatus.COMPLETED
    path = tmp_path / "review-lingering-extended.json"
    game.save(path)

    loaded = Encounter.load(path)

    assert loaded._state.creatures["maestro_bard"].focus_points == 1
    assert {
        (effect.expires_at_source_start, effect.expires_at_world_time)
        for effect in loaded._state.active_effects
        if effect.kind == "courageous_anthem"
    } == {(4, 18)}


def test_highest_affected_target_level_sets_dc_not_bard_level(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original_get_definition = encounter_module.get_definition
    level_two_ally = replace(original_get_definition("fighter_m_level_1"), level=2)

    def review_get_definition(definition_id: str):
        if definition_id == level_two_ally.definition_id:
            return level_two_ally
        return original_get_definition(definition_id)

    monkeypatch.setattr(encounter_module, "get_definition", review_get_definition)
    game = Encounter.start(MAESTRO_BARD_ANTHEM_SETUP, rolls=(20, 1, 1, 9))
    _settle_start_choices(game)
    assert game.execute(LingeringComposition()).status is ResultStatus.COMPLETED
    resolved = _finish_keep_choices(game, game.execute(Cast("courageous_anthem")))

    assert resolved.status is ResultStatus.COMPLETED
    check = next(
        event.check
        for event in resolved.events
        if event.kind == "lingering_composition_resolved"
    )
    assert check is not None
    assert (check.modifier, check.total, check.dc) == (7, 16, 16)
    assert {
        effect.target_actor_id
        for effect in game._state.active_effects
        if effect.kind == "courageous_anthem"
    } == {"maestro_bard", "bard_ally"}


def test_three_round_success_boosts_later_round_strike_then_expires_exactly(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    base = MAESTRO_BARD_ANTHEM_SETUP
    setup = replace(
        base,
        setup_id="review_lingering_later_round_strike",
        name="Review Lingering later-round Strike",
        placements=base.placements
        + (
            replace(
                base.placements[2],
                actor_id="bard_dog_b",
                label="Second Guard Dog",
                position=Position(4, 1),
            ),
        ),
    )
    monkeypatch.setattr(
        content,
        "_STAGED_SETUPS",
        content._STAGED_SETUPS | {setup.setup_id: setup},
    )
    # Four initiatives; Performance success; later ally Strike and damage.
    game = Encounter.start(setup, rolls=(20, 10, 5, 1, 8, 10, 4))
    _settle_start_choices(game)
    assert game.execute(LingeringComposition()).status is ResultStatus.COMPLETED
    assert _finish_keep_choices(
        game, game.execute(Cast("courageous_anthem")),
    ).status is ResultStatus.COMPLETED
    assert {
        effect.expires_at_source_start
        for effect in game._state.active_effects
        if effect.kind == "courageous_anthem"
    } == {4}

    _advance_to_start(game, "maestro_bard", 2)
    assert any(
        effect.kind == "courageous_anthem" for effect in game._state.active_effects
    )
    assert game.execute(EndTurn()).status is ResultStatus.COMPLETED
    assert game.inspect().turn_actor_id == "bard_ally"
    strike = _finish_keep_choices(game, game.execute(Strike("bard_dog", "longsword")))
    assert strike.status is ResultStatus.COMPLETED
    check = next(event.check for event in strike.events if event.kind == "strike")
    assert check is not None and check.modifier == 10
    damage = next(event.damage for event in strike.events if event.damage is not None)
    assert damage is not None and damage.total == 9

    _advance_to_start(game, "maestro_bard", 3)
    assert any(
        effect.kind == "courageous_anthem" for effect in game._state.active_effects
    )
    _advance_to_start(game, "maestro_bard", 4)
    assert not any(
        effect.kind == "courageous_anthem" for effect in game._state.active_effects
    )
