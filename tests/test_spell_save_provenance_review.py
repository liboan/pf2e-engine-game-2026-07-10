"""Independent review of shared spell-save choice and provenance handling.

Rules sources:
* Guidance: https://2e.aonprd.com/Spells.aspx?ID=1549
* Tempest Surge: https://2e.aonprd.com/Spells.aspx?ID=1860
* Basic saves: https://2e.aonprd.com/Rules.aspx?ID=2296
* Hero Points: https://2e.aonprd.com/Rules.aspx?ID=2333
"""

from __future__ import annotations

import json
from types import MappingProxyType

import pytest

import pf2e.content as content
from pf2e.content import get_setup
from pf2e.encounter import Encounter
from pf2e.model import Cast, CreaturePlacement, EncounterSetup, EndTurn, Position, ResultStatus


def _settle(game: Encounter) -> None:
    while (choice := game.inspect().choice) is not None:
        option_ids = {option.option_id for option in choice.options}
        option_id = "keep" if "keep" in option_ids else choice.options[0].option_id
        assert game.choose(choice.choice_id, option_id, choice.owner_actor_id).status in {
            ResultStatus.PAUSED,
            ResultStatus.COMPLETED,
        }


def _register_setup(monkeypatch: pytest.MonkeyPatch, setup: EncounterSetup) -> None:
    monkeypatch.setattr(
        content,
        "_STAGED_SETUPS",
        MappingProxyType({**content._STAGED_SETUPS, setup.setup_id: setup}),
    )


def test_guided_tempest_round_trips_both_choices_and_applies_failure_rider_once(
    monkeypatch: pytest.MonkeyPatch, tmp_path
) -> None:
    setup = EncounterSetup(
        "review_guided_tempest",
        "Review Guided Tempest Surge",
        7,
        5,
        (
            CreaturePlacement(
                "caster", "storm_druid_level_1", "Storm Druid", "blue", Position(1, 2)
            ),
            CreaturePlacement(
                "target", "life_oracle_level_1_staged", "Life Oracle", "red", Position(4, 2)
            ),
        ),
    )
    _register_setup(monkeypatch, setup)
    # Target wins initiative, then the guided save is 8 + Reflex 4 + 1 = 13,
    # a failure against DC 17. Tempest Surge damage is the final 6.
    game = Encounter.start(setup, rolls=(1, 20, 8, 6))
    _settle(game)
    assert game.inspect().turn_actor_id == "target"
    assert game.execute(Cast("guidance", "target")).status is ResultStatus.COMPLETED
    assert game.execute(EndTurn()).status is ResultStatus.COMPLETED

    started = game.execute(Cast("tempest_surge", "target"))
    assert started.status is ResultStatus.PAUSED
    choice = started.inspection.choice
    assert choice is not None and choice.kind == "guidance_use"
    first_path = tmp_path / "guided-tempest.json"
    game.save(first_path)
    game = Encounter.load(first_path)

    choice = game.inspect().choice
    assert choice is not None and choice.kind == "guidance_use"
    guided = game.choose(choice.choice_id, "use", choice.owner_actor_id)
    assert guided.status is ResultStatus.PAUSED
    hero = guided.inspection.choice
    assert hero is not None and hero.kind == "spell_save_hero_reroll"
    pending = game._state.pending_choice
    assert pending is not None and pending.check is not None
    assert pending.check.total == 13
    assert [(term.amount, term.modifier_type, term.source) for term in pending.check.modifier_breakdown] == [
        (4, "untyped", "printed Reflex save"),
        (1, "status", "Guidance"),
    ]

    second_path = tmp_path / "guided-tempest-hero.json"
    game.save(second_path)
    game = Encounter.load(second_path)
    hero = game.inspect().choice
    assert hero is not None and hero.kind == "spell_save_hero_reroll"
    completed = game.choose(hero.choice_id, "keep", hero.owner_actor_id)
    assert completed.status is ResultStatus.COMPLETED
    assert game._state.creatures["caster"].focus_points == 0
    assert game._state.creatures["target"].hp == 12
    assert game._state.guidance_immunity_deadlines["target"] == 600
    assert not any(
        effect.kind == "guidance" and effect.target_actor_id == "target"
        for effect in game._state.active_effects
    )
    clumsy = [
        effect
        for effect in game._state.condition_effects
        if effect.kind == "clumsy" and effect.target_actor_id == "target"
    ]
    assert len(clumsy) == 1 and clumsy[0].value == 2


def test_spell_save_load_rejects_forged_check_arithmetic(tmp_path) -> None:
    game = Encounter.start(get_setup("storm_druid_tempest_save"), rolls=(20, 1, 8, 6))
    _settle(game)
    assert game.execute(Cast("tempest_surge", "wizard_target")).status is ResultStatus.PAUSED
    path = tmp_path / "forged-save-total.json"
    game.save(path)
    payload = json.loads(path.read_text())
    payload["state"]["pending_choice"]["check"]["total"] += 100
    path.write_text(json.dumps(payload))

    with pytest.raises(ValueError, match="pending check arithmetic"):
        Encounter.load(path)


def test_saved_guidance_choice_rejects_tampered_committed_focus_source(
    monkeypatch: pytest.MonkeyPatch, tmp_path
) -> None:
    setup = EncounterSetup(
        "review_tampered_guided_tempest",
        "Review Tampered Guided Tempest",
        7,
        5,
        (
            CreaturePlacement(
                "caster", "storm_druid_level_1", "Storm Druid", "blue", Position(1, 2)
            ),
            CreaturePlacement(
                "target", "life_oracle_level_1_staged", "Life Oracle", "red", Position(4, 2)
            ),
        ),
    )
    _register_setup(monkeypatch, setup)
    game = Encounter.start(setup, rolls=(1, 20, 8, 6))
    _settle(game)
    assert game.execute(Cast("guidance", "target")).status is ResultStatus.COMPLETED
    assert game.execute(EndTurn()).status is ResultStatus.COMPLETED
    paused = game.execute(Cast("tempest_surge", "target"))
    assert paused.status is ResultStatus.PAUSED
    assert paused.inspection.choice is not None
    assert paused.inspection.choice.kind == "guidance_use"

    path = tmp_path / "forged-guidance-source.json"
    game.save(path)
    payload = json.loads(path.read_text())
    pending = payload["state"]["pending_choice"]
    pending["slot_id"] = "druid_electric_arc"
    pending["continuation"]["slot_id"] = "druid_electric_arc"
    pending["continuation"]["spell_source_kind"] = "prepared"
    path.write_text(json.dumps(payload))

    with pytest.raises(ValueError, match="spell save source"):
        Encounter.load(path)


def test_spontaneous_cantrip_save_rejects_forged_ranked_slot_provenance(tmp_path) -> None:
    game = Encounter.start(
        get_setup("staged_life_oracle_vitality_lash"), rolls=(20, 1, 8, 6, 6)
    )
    _settle(game)
    assert game.execute(Cast("vitality_lash", "death_oracle", actions=2)).status is ResultStatus.PAUSED
    path = tmp_path / "forged-vitality-slot.json"
    game.save(path)
    payload = json.loads(path.read_text())
    pending = payload["state"]["pending_choice"]
    pending["slot_id"] = "oracle_rank1"
    pending["continuation"]["slot_id"] = "oracle_rank1"
    path.write_text(json.dumps(payload))

    with pytest.raises(ValueError, match="spontaneous spell save source"):
        Encounter.load(path)


def test_prepared_cantrip_save_rejects_forged_slot_provenance(tmp_path) -> None:
    game = Encounter.start(
        get_setup("staged_battle_magic_wizard_breathe_hero_save"),
        rolls=(20, 1, 1, 1, 3, 4, 10, 10),
    )
    _settle(game)
    paused = game.execute(Cast("electric_arc", target_ids=("wizard_ally", "dog_a")))
    assert paused.status is ResultStatus.PAUSED
    path = tmp_path / "forged-electric-arc-slot.json"
    game.save(path)
    payload = json.loads(path.read_text())
    pending = payload["state"]["pending_choice"]
    assert pending["slot_id"] is None
    assert pending["continuation"]["slot_id"] is None
    pending["slot_id"] = "wizard_electric_arc"
    pending["continuation"]["slot_id"] = "wizard_electric_arc"
    path.write_text(json.dumps(payload))

    with pytest.raises(ValueError, match="prepared spell save source"):
        Encounter.load(path)


def test_prepared_multi_recipient_save_resumes_shared_roll_and_second_target(tmp_path) -> None:
    game = Encounter.start(
        get_setup("staged_battle_magic_wizard_breathe_hero_save"),
        rolls=(20, 1, 1, 1, 3, 4, 10, 10),
    )
    _settle(game)
    paused = game.execute(Cast("electric_arc", target_ids=("wizard_ally", "dog_a")))
    assert paused.status is ResultStatus.PAUSED
    choice = paused.inspection.choice
    assert choice is not None and choice.kind == "spell_save_hero_reroll"
    path = tmp_path / "review-electric-arc.json"
    game.save(path)
    game = Encounter.load(path)

    choice = game.inspect().choice
    assert choice is not None
    completed = game.choose(choice.choice_id, "keep", choice.owner_actor_id)
    assert completed.status is ResultStatus.COMPLETED
    damage = [
        (event.target_id, event.damage.rolled_total, event.damage.total)
        for event in completed.events
        if event.kind == "spell_damage" and event.damage is not None
    ]
    assert damage == [("wizard_ally", 7, 7), ("dog_a", 7, 3)]


def test_multi_recipient_save_uses_shared_guidance_before_first_target_roll(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    setup = EncounterSetup(
        "review_guided_electric_arc",
        "Review Guided Electric Arc",
        7,
        5,
        (
            CreaturePlacement(
                "guide", "life_oracle_level_1_staged", "Guide", "blue", Position(1, 2)
            ),
            CreaturePlacement(
                "caster", "wizard_battle_magic_level_1_staged", "Wizard", "red", Position(3, 2)
            ),
            CreaturePlacement(
                "target", "wizard_battle_magic_level_1_staged", "Target", "blue", Position(4, 2)
            ),
            CreaturePlacement(
                "dog", "guard_dog_mc2924", "Dog", "blue", Position(5, 2)
            ),
        ),
    )
    _register_setup(monkeypatch, setup)
    # Initiative; shared 2d4; then the as-yet-unrolled guided Reflex save.
    game = Encounter.start(setup, rolls=(20, 10, 1, 2, 3, 4, 8, 10))
    _settle(game)
    assert game.inspect().turn_actor_id == "guide"
    assert game.execute(Cast("guidance", "target")).status is ResultStatus.COMPLETED
    assert game.execute(EndTurn()).status is ResultStatus.COMPLETED
    assert game.inspect().turn_actor_id == "caster"

    paused = game.execute(Cast("electric_arc", target_ids=("target", "dog")))
    assert paused.status is ResultStatus.PAUSED
    choice = paused.inspection.choice
    assert choice is not None and choice.kind == "guidance_use"
    assert choice.owner_actor_id == "target"
    first_save = game.choose(choice.choice_id, "use", choice.owner_actor_id)
    hero = first_save.inspection.choice
    assert hero is not None and hero.kind == "spell_save_hero_reroll"
    completed = game.choose(hero.choice_id, "keep", hero.owner_actor_id)
    assert completed.status is ResultStatus.COMPLETED
    dog_save = next(
        event.check
        for event in completed.events
        if event.kind == "spell_save" and event.target_id == "dog"
    )
    assert dog_save is not None
    assert all(term.source != "Guidance" for term in dog_save.modifier_breakdown)


def test_multi_recipient_save_offers_each_targets_distinct_guidance(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    setup = EncounterSetup(
        "review_two_guided_electric_arc_targets",
        "Review Two Guided Electric Arc Targets",
        7,
        5,
        (
            CreaturePlacement(
                "guide_a", "life_oracle_level_1_staged", "Guide A", "blue", Position(1, 1)
            ),
            CreaturePlacement(
                "guide_b", "life_oracle_level_1_staged", "Guide B", "blue", Position(1, 3)
            ),
            CreaturePlacement(
                "caster", "wizard_battle_magic_level_1_staged", "Wizard", "red", Position(3, 2)
            ),
            CreaturePlacement(
                "target_a", "wizard_battle_magic_level_1_staged", "Target A", "blue", Position(4, 1)
            ),
            CreaturePlacement(
                "target_b", "wizard_battle_magic_level_1_staged", "Target B", "blue", Position(4, 3)
            ),
        ),
    )
    _register_setup(monkeypatch, setup)
    # Initiatives; shared 2d4; target A's save. Target B's save must remain
    # unrolled until its own Guidance decision is made.
    game = Encounter.start(setup, rolls=(20, 19, 10, 2, 1, 1, 1, 20, 8))
    _settle(game)
    assert game.inspect().turn_actor_id == "guide_a"
    assert game.execute(Cast("guidance", "target_a")).status is ResultStatus.COMPLETED
    assert game.execute(EndTurn()).status is ResultStatus.COMPLETED
    assert game.inspect().turn_actor_id == "guide_b"
    assert game.execute(Cast("guidance", "target_b")).status is ResultStatus.COMPLETED
    assert game.execute(EndTurn()).status is ResultStatus.COMPLETED
    assert game.inspect().turn_actor_id == "caster"

    paused = game.execute(Cast("electric_arc", target_ids=("target_a", "target_b")))
    first_guidance = paused.inspection.choice
    assert first_guidance is not None and first_guidance.kind == "guidance_use"
    assert first_guidance.owner_actor_id == "target_a"
    rolled = game.choose(first_guidance.choice_id, "use", first_guidance.owner_actor_id)
    first_hero = rolled.inspection.choice
    assert first_hero is not None and first_hero.kind == "spell_save_hero_reroll"
    after_first = game.choose(first_hero.choice_id, "keep", first_hero.owner_actor_id)
    second_guidance = after_first.inspection.choice
    assert second_guidance is not None and second_guidance.kind == "guidance_use"
    assert second_guidance.owner_actor_id == "target_b"


def test_area_save_hero_pause_round_trips_current_recipient(tmp_path) -> None:
    game = Encounter.start(
        get_setup("staged_battle_magic_wizard_movement_spells_prepared"),
        rolls=(20, 1, 1, 3, 1),
    )
    _settle(game)
    game._state.creatures["dog_a"].position = Position(6, 4)
    game._state.creatures["dog_b"].position = Position(6, 3)
    paused = game.execute(Cast("gale_blast", include_self=True))
    assert paused.status is ResultStatus.PAUSED
    choice = paused.inspection.choice
    assert choice is not None and choice.kind == "spell_save_hero_reroll"
    assert choice.owner_actor_id == "wizard"

    path = tmp_path / "review-gale-hero.json"
    game.save(path)
    game = Encounter.load(path)
    choice = game.inspect().choice
    assert choice is not None and choice.kind == "spell_save_hero_reroll"
    completed = game.choose(choice.choice_id, "keep", choice.owner_actor_id)
    assert completed.status is ResultStatus.COMPLETED
    assert game._state.creatures["wizard"].hp == 10
