"""Independent review checks for the first dim-targeting slice.

Rules sources checked 2026-09-16:
https://2e.aonprd.com/Rules.aspx?ID=2403 (dim light),
https://2e.aonprd.com/Conditions.aspx?ID=62 (concealed),
https://2e.aonprd.com/Rules.aspx?ID=2278 (flat checks),
https://2e.aonprd.com/Rules.aspx?ID=2333 (Hero Points), and
https://2e.aonprd.com/Spells.aspx?ID=1549 (Guidance).
"""

from __future__ import annotations

from dataclasses import fields, replace
from pathlib import Path
from types import MappingProxyType

import pytest

import pf2e.content as content
from pf2e import Cast, Encounter, Position, ResultStatus, Strike, Stride
from pf2e.content import ANGELIC_FIRST_CAST_SETUP, DIM_REACTION_SETUP, DIM_TARGETING_SETUP
from pf2e.model import CreatureDefinition, CreaturePlacement, EncounterSetup


def _settle_initiative(game: Encounter) -> None:
    while (choice := game.inspect().choice) is not None:
        assert choice.kind == "initiative_hero_reroll"
        game.choose(choice.choice_id, "keep", choice.owner_actor_id)


def _actor(game: Encounter, actor_id: str):
    return next(actor for actor in game.inspect().actors if actor.actor_id == actor_id)


def _dim_angelic_setup(monkeypatch: pytest.MonkeyPatch) -> EncounterSetup:
    setup = replace(
        ANGELIC_FIRST_CAST_SETUP,
        setup_id="review_dim_angelic_first_cast",
        ambient_light="dim",
    )
    monkeypatch.setattr(
        content,
        "_STAGED_SETUPS",
        MappingProxyType({**content._STAGED_SETUPS, setup.setup_id: setup}),
    )
    return setup


def test_real_self_guidance_survives_failed_concealment_check(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    game = Encounter.start(_dim_angelic_setup(monkeypatch), rolls=(20, 1, 1, 4))
    _settle_initiative(game)

    guidance = game.execute(Cast("guidance", "angelic_sorcerer"))
    assert guidance.status is ResultStatus.COMPLETED
    result = game.execute(Strike("sorcerer_ally", attack_id="fist"))

    assert result.status is ResultStatus.COMPLETED
    assert [event.kind for event in result.events] == [
        "concealment_flat_check",
        "concealment_failed",
    ]
    caster = _actor(game, "angelic_sorcerer")
    assert (caster.actions_remaining, caster.strikes_this_turn) == (1, 1)
    assert tuple(effect.kind for effect in caster.effects) == ("guidance",)
    assert caster.guidance_immune_until_round is None


def test_concealment_and_attack_hero_choices_round_trip_separately(tmp_path: Path) -> None:
    game = Encounter.start(DIM_TARGETING_SETUP, rolls=(20, 1, 4, 5, 1, 20, 6))
    _settle_initiative(game)
    game._state.creatures["fighter_a"].hero_points = 2

    flat = game.execute(Strike("guard_dog_a", attack_id="longsword"))
    assert flat.inspection.choice is not None
    after_flat = game.choose(
        flat.inspection.choice.choice_id,
        "spend_hero_point",
        flat.inspection.choice.owner_actor_id,
    )
    assert after_flat.inspection.choice is not None
    assert after_flat.inspection.choice.kind == "attack_hero_reroll"

    path = tmp_path / "separate-dim-hero-choices.json"
    game.save(path)
    restored = Encounter.load(path)
    assert restored.inspect() == after_flat.inspection
    result = restored.choose(
        restored.inspect().choice.choice_id,
        "spend_hero_point",
        restored.inspect().choice.owner_actor_id,
    )
    assert result.status is ResultStatus.COMPLETED
    assert [event.kind for event in result.events].count("strike") == 1
    assert _actor(restored, "fighter_a").hero_points == 0


def test_saved_reaction_concealment_failure_resumes_movement(tmp_path: Path) -> None:
    game = Encounter.start(DIM_REACTION_SETUP, rolls=(20, 1, 4))
    _settle_initiative(game)
    started = game.execute(Stride((Position(0, 1),)))
    assert started.inspection.choice is not None
    accepted = game.choose(
        started.inspection.choice.choice_id,
        "accept",
        started.inspection.choice.owner_actor_id,
    )
    assert accepted.inspection.choice is not None
    assert accepted.inspection.choice.kind == "concealment_hero_reroll"

    path = tmp_path / "dim-reaction-movement.json"
    game.save(path)
    restored = Encounter.load(path)
    result = restored.choose(
        restored.inspect().choice.choice_id,
        "keep",
        restored.inspect().choice.owner_actor_id,
    )
    assert result.status is ResultStatus.COMPLETED
    assert any(event.kind == "concealment_failed" for event in result.events)
    assert _actor(restored, "fighter_a").position == Position(0, 1)
    assert _actor(restored, "fighter_a").actions_remaining == 2
    assert _actor(restored, "fighter_b").reaction_available is False


def test_self_and_area_modes_are_valid_but_targeted_spell_rejects_before_cost(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    setup = _dim_angelic_setup(monkeypatch)
    area_game = Encounter.start(setup, rolls=(20, 1, 1, 4))
    _settle_initiative(area_game)
    area = area_game.execute(
        Cast("heal", actions=3, slot_id="angelic_rank1", include_self=True)
    )
    assert area.status is ResultStatus.COMPLETED
    assert _actor(area_game, "angelic_sorcerer").actions_remaining == 0

    targeted_game = Encounter.start(setup, rolls=(20, 1, 1, 4))
    _settle_initiative(targeted_game)
    targeted_game._state.creatures["angelic_sorcerer"].hero_points = 1
    before = _actor(targeted_game, "angelic_sorcerer")
    rejected = targeted_game.execute(Cast("divine_lance", "sorcerer_dog"))
    after = _actor(targeted_game, "angelic_sorcerer")
    assert rejected.status is ResultStatus.PAUSED
    assert rejected.inspection.choice is not None
    assert rejected.inspection.choice.kind == "concealment_hero_reroll"
    assert (after.actions_remaining, after.strikes_this_turn, after.spontaneous_slots) == (
        before.actions_remaining - 2,
        before.strikes_this_turn + 1,
        before.spontaneous_slots,
    )


def test_dim_runic_weapon_commits_before_item_concealment_gate(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    game = Encounter.start(_dim_angelic_setup(monkeypatch), rolls=(20, 1, 1, 4))
    _settle_initiative(game)
    game._state.creatures["angelic_sorcerer"].hero_points = 1
    before = _actor(game, "angelic_sorcerer")

    result = game.execute(
        Cast(
            "runic_weapon",
            item_id="sorcerer_ally:longsword",
            slot_id="angelic_rank1",
        )
    )
    after = _actor(game, "angelic_sorcerer")
    assert result.status is ResultStatus.PAUSED
    willingness = result.inspection.choice
    assert willingness is not None and willingness.kind == "spell_willingness"
    assert (after.actions_remaining, after.spontaneous_slots) == (
        before.actions_remaining - 2,
        tuple(
            replace(slot, remaining=slot.remaining - 1)
            if slot.slot_id == "angelic_rank1" else slot
            for slot in before.spontaneous_slots
        ),
    )
    accepted = game.choose(willingness.choice_id, "willing", willingness.owner_actor_id)
    assert accepted.status is ResultStatus.PAUSED
    assert accepted.inspection.choice is not None
    assert accepted.inspection.choice.kind == "concealment_hero_reroll"
    assert accepted.events[-1].check is not None and accepted.events[-1].check.die == 4


def test_undeclared_darkvision_cannot_enter_dim_runtime(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    base = content.MELEE_FIGHTER_M
    copied = {
        field.name: getattr(base, field.name)
        for field in fields(CreatureDefinition)
        if field.init and field.name not in {"definition_id", "name", "senses", "vision"}
    }
    undeclared = CreatureDefinition(
        definition_id="review_undeclared_darkvision",
        name="Undeclared Darkvision Review Actor",
        senses=("darkvision",),
        **copied,
    )
    setup = EncounterSetup(
        setup_id="review_undeclared_darkvision_dim",
        name="Undeclared darkvision dim admission review",
        width=4,
        height=3,
        placements=(
            CreaturePlacement("special", undeclared.definition_id, "Special", "blue", Position(1, 1)),
            CreaturePlacement(
                "ordinary",
                content.MELEE_FIGHTER_M.definition_id,
                "Ordinary",
                "red",
                Position(2, 1),
            ),
        ),
        ambient_light="dim",
    )
    monkeypatch.setattr(
        content,
        "_STAGED_CREATURES",
        MappingProxyType(
            {**content._STAGED_CREATURES, undeclared.definition_id: undeclared}
        ),
    )
    monkeypatch.setattr(
        content,
        "_STAGED_SETUPS",
        MappingProxyType({**content._STAGED_SETUPS, setup.setup_id: setup}),
    )

    with pytest.raises(ValueError, match="vision"):
        Encounter.start(setup, rolls=(20, 1))
