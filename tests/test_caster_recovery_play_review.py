"""Combined public-play review for recovery, dim skills, Light, and Runic Weapon.

Primary rules reviewed for this packet:

* Refocus: https://2e.aonprd.com/Actions.aspx?ID=2621
* Guidance: https://2e.aonprd.com/Spells.aspx?ID=1549
* Light: https://2e.aonprd.com/Spells.aspx?ID=1585
* Concealed: https://2e.aonprd.com/Conditions.aspx?ID=62
* Assurance: https://2e.aonprd.com/Feats.aspx?ID=5121
* Demoralize: https://2e.aonprd.com/Actions.aspx?ID=2395
* Scoundrel: https://2e.aonprd.com/Rackets.aspx?ID=8
* Runic Weapon: https://2e.aonprd.com/Spells.aspx?ID=1658
* Start-of-turn duration tracking: https://2e.aonprd.com/Rules.aspx?ID=436

The two composite setups below use existing reviewed creature definitions. They
are legal test scenes, not additional implemented class builds.
"""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from types import MappingProxyType

import pytest

import pf2e.content as content
from pf2e import Cast, Encounter, EndTurn, Position, ResultStatus, Strike, Stride
from pf2e.skill_actions import Trip


def _actor(game: Encounter, actor_id: str):
    return next(actor for actor in game.inspect().actors if actor.actor_id == actor_id)


def _settle_initiative(game: Encounter) -> None:
    while (choice := game.inspect().choice) is not None:
        assert choice.kind in {"initiative_hero_reroll", "initiative_tie"}
        option_id = (
            "keep"
            if any(option.option_id == "keep" for option in choice.options)
            else choice.options[0].option_id
        )
        result = game.choose(choice.choice_id, option_id, choice.owner_actor_id)
        assert result.status in {ResultStatus.PAUSED, ResultStatus.COMPLETED}


def _choose(game: Encounter, option_id: str):
    choice = game.inspect().choice
    assert choice is not None
    result = game.choose(choice.choice_id, option_id, choice.owner_actor_id)
    assert result.status in {ResultStatus.PAUSED, ResultStatus.COMPLETED}
    return result


def _register_setup(monkeypatch: pytest.MonkeyPatch, setup) -> None:
    monkeypatch.setattr(
        content,
        "_STAGED_SETUPS",
        MappingProxyType({**content._STAGED_SETUPS, setup.setup_id: setup}),
    )


def _register_definition(monkeypatch: pytest.MonkeyPatch, definition) -> None:
    monkeypatch.setattr(
        content,
        "_STAGED_CREATURES",
        MappingProxyType(
            {**content._STAGED_CREATURES, definition.definition_id: definition}
        ),
    )


def _warpriest_angelic_setup(monkeypatch: pytest.MonkeyPatch):
    setup = replace(
        content.ANGELIC_FIRST_CAST_SETUP,
        setup_id="caster_recovery_warpriest_review",
        name="Caster recovery and Warpriest Light review fixture",
        placements=tuple(
            replace(
                placement,
                actor_id="warpriest",
                definition_id=content.WARPRIEST_C.definition_id,
                label="Iomedaean Warpriest",
            )
            if placement.actor_id == "sorcerer_ally"
            else placement
            for placement in content.ANGELIC_FIRST_CAST_SETUP.placements
        ),
    )
    _register_setup(monkeypatch, setup)
    return setup


def _dim_warpriest_setup(monkeypatch: pytest.MonkeyPatch):
    setup = replace(
        content.DIM_TARGETING_SETUP,
        setup_id="dim_warpriest_skill_review",
        name="Dim Warpriest skill review fixture",
        placements=(
            replace(
                content.DIM_TARGETING_SETUP.placements[0],
                actor_id="warpriest",
                definition_id=content.WARPRIEST_C.definition_id,
                label="Iomedaean Warpriest",
            ),
            content.DIM_TARGETING_SETUP.placements[1],
        ),
    )
    _register_setup(monkeypatch, setup)
    return setup


def test_injury_spent_resources_prepared_light_refocus_and_save_load(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """A healthy-start fight carries literal state through ten-minute recovery."""
    setup = _warpriest_angelic_setup(monkeypatch)
    # Initiative; two critical jaws hits; two Warpriest hits and damage; Heal.
    game = Encounter.start(
        setup,
        rolls=(20, 1, 10, 20, 3, 20, 3, 15, 1, 4, 15, 1),
    )
    assert all(actor.hp == actor.max_hp for actor in game.inspect().actors)
    _settle_initiative(game)
    assert game.inspect().turn_actor_id == "angelic_sorcerer"
    initial_prepared_slots = _actor(game, "warpriest").prepared_slots

    halo = game.execute(Cast("angelic_halo", actions=1))
    assert halo.status is ResultStatus.PAUSED
    assert halo.inspection.choice is not None
    assert halo.inspection.choice.kind == "spell_blood_magic_recipient"
    assert _choose(game, "warpriest").status is ResultStatus.COMPLETED
    assert _actor(game, "angelic_sorcerer").focus_points == 0

    assert game.inspect().turn_actor_id == "angelic_sorcerer"
    assert game.execute(EndTurn()).status is ResultStatus.COMPLETED
    assert game.inspect().turn_actor_id == "sorcerer_dog"
    assert game.execute(Stride((Position(4, 2), Position(3, 2)))).status is ResultStatus.COMPLETED
    assert game.execute(Strike("warpriest", attack_id="jaws")).status is ResultStatus.COMPLETED
    assert game.execute(Strike("warpriest", attack_id="jaws")).status is ResultStatus.COMPLETED
    assert _actor(game, "warpriest").hp == 1
    assert game.inspect().turn_actor_id == "warpriest"

    light = game.execute(
        Cast(
            "light",
            point=Position(2, 2),
            color="sun-gold",
            attachment_actor_id="warpriest",
        )
    )
    assert light.status is ResultStatus.PAUSED
    assert light.inspection.choice is not None
    assert light.inspection.choice.kind == "spell_willingness"
    assert _choose(game, "willing").status is ResultStatus.COMPLETED
    assert _actor(game, "warpriest").prepared_slots == initial_prepared_slots

    first_strike = game.execute(Strike("sorcerer_dog", attack_id="longsword"))
    assert first_strike.status is ResultStatus.PAUSED
    assert first_strike.inspection.choice is not None
    assert first_strike.inspection.choice.kind == "attack_hero_reroll"
    assert _choose(game, "keep").status is ResultStatus.COMPLETED
    assert _actor(game, "sorcerer_dog").hp == 4
    assert game.inspect().turn_actor_id == "angelic_sorcerer"

    heal = game.execute(Cast("heal", "warpriest", actions=2))
    assert heal.status is ResultStatus.PAUSED
    assert heal.inspection.choice is not None
    assert heal.inspection.choice.kind == "spell_blood_magic_recipient"
    assert _choose(game, "angelic_sorcerer").status is ResultStatus.PAUSED
    assert game.inspect().choice is not None
    assert game.inspect().choice.kind == "spell_willingness"
    assert _choose(game, "willing").status is ResultStatus.COMPLETED
    assert _actor(game, "warpriest").hp == 15
    assert _actor(game, "angelic_sorcerer").spontaneous_slots[0].remaining == 2

    guidance = game.execute(Cast("guidance", "warpriest"))
    assert guidance.status is ResultStatus.COMPLETED
    assert game.inspect().turn_actor_id == "sorcerer_dog"
    assert game.execute(EndTurn()).status is ResultStatus.COMPLETED
    assert game.inspect().turn_actor_id == "warpriest"

    final_strike = game.execute(Strike("sorcerer_dog", attack_id="longsword"))
    assert final_strike.status is ResultStatus.PAUSED
    assert final_strike.inspection.choice is not None
    assert final_strike.inspection.choice.kind == "guidance_use"
    kept_guidance = _choose(game, "keep")
    assert kept_guidance.status is ResultStatus.PAUSED
    assert kept_guidance.inspection.choice is not None
    assert kept_guidance.inspection.choice.kind == "attack_hero_reroll"
    victory = _choose(game, "keep")
    assert victory.status is ResultStatus.COMPLETED
    assert not game.inspect().in_progress
    assert game.inspect().winner_team == "blue"

    before = game.inspect()
    before_sorcerer = _actor(game, "angelic_sorcerer")
    before_warpriest = _actor(game, "warpriest")
    before_orbs = before.light_orbs
    assert before.world_time_seconds == 6
    assert before_sorcerer.focus_points == 0
    assert before_sorcerer.spontaneous_slots[0].remaining == 2
    assert before_warpriest.hp == 15
    assert len(before_orbs) == 1 and before_orbs[0].attached_actor_id == "warpriest"
    assert any(effect.kind == "guidance" for effect in before_warpriest.effects)

    refocused = game.refocus("angelic_sorcerer")
    assert refocused.status is ResultStatus.COMPLETED
    assert refocused.inspection.world_time_seconds == 606
    after_sorcerer = _actor(game, "angelic_sorcerer")
    after_warpriest = _actor(game, "warpriest")
    assert after_sorcerer.focus_points == 1
    assert after_sorcerer.hp == before_sorcerer.hp
    assert after_sorcerer.spontaneous_slots == before_sorcerer.spontaneous_slots
    assert after_warpriest.hp == before_warpriest.hp
    assert after_warpriest.prepared_slots == before_warpriest.prepared_slots
    assert game.inspect().light_orbs == before_orbs
    assert not after_sorcerer.effects and not after_warpriest.effects
    # Guidance was cast at world time 6 and expired at its caster's next-start
    # boundary at 12. Its ten-minute immunity therefore ends at 612, rather
    # than being restarted when Refocus ends at 606.
    assert after_warpriest.guidance_immune_until_seconds == 612

    save_path = tmp_path / "caster-recovery-review.json"
    game.save(save_path)
    restored = Encounter.load(save_path)
    assert restored.inspect() == game.inspect()


def test_dim_assurance_target_save_preserves_guidance_and_commits_map_once(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """A real Warpriest loses targeting, keeps Guidance, then wins at MAP 2."""
    setup = _dim_warpriest_setup(monkeypatch)
    # Initiative; failed Trip targeting; passed Strike targeting; Strike and damage.
    game = Encounter.start(setup, rolls=(20, 1, 4, 5, 20, 1))
    assert all(actor.hp == actor.max_hp for actor in game.inspect().actors)
    _settle_initiative(game)
    assert game.inspect().turn_actor_id == "warpriest"
    assert game.execute(Cast("guidance", "warpriest")).status is ResultStatus.COMPLETED

    trip = game.execute(Trip("guard_dog_a", use_assurance=True))
    assert trip.status is ResultStatus.PAUSED
    choice = trip.inspection.choice
    assert choice is not None and choice.kind == "concealment_hero_reroll"
    pending = game._state.pending_choice
    assert pending is not None and pending.saved_check is not None
    assert pending.saved_check.result is not None
    assert pending.saved_check.result.method == "assurance"
    assert pending.saved_check.result.die is None
    assert pending.saved_check.attack_count_committed
    assert _actor(game, "warpriest").strikes_this_turn == 1

    save_path = tmp_path / "dim-warpriest-assurance-target.json"
    game.save(save_path)
    restored = Encounter.load(save_path)
    assert restored.inspect() == trip.inspection
    missed = _choose(restored, "keep")
    assert missed.status is ResultStatus.COMPLETED
    assert not any(event.kind == "trip_check" for event in missed.events)
    assert any(effect.kind == "guidance" for effect in _actor(restored, "warpriest").effects)
    assert (_actor(restored, "warpriest").actions_remaining,
            _actor(restored, "warpriest").strikes_this_turn) == (1, 1)

    strike = restored.execute(Strike("guard_dog_a", attack_id="longsword"))
    assert strike.status is ResultStatus.PAUSED
    assert strike.inspection.choice is not None
    assert strike.inspection.choice.kind == "concealment_hero_reroll"
    events = list(strike.events)
    passed_target = _choose(restored, "keep")
    events.extend(passed_target.events)
    assert passed_target.status is ResultStatus.PAUSED
    assert passed_target.inspection.choice is not None
    assert passed_target.inspection.choice.kind == "guidance_use"
    used_guidance = _choose(restored, "use")
    events.extend(used_guidance.events)
    assert used_guidance.status is ResultStatus.PAUSED
    assert used_guidance.inspection.choice is not None
    assert used_guidance.inspection.choice.kind == "attack_hero_reroll"
    victory = _choose(restored, "keep")
    events.extend(victory.events)
    assert victory.status is ResultStatus.COMPLETED
    attack = next(
        event.check
        for event in events
        if event.check is not None and event.check.attack_id == "longsword"
    )
    assert attack is not None
    assert (attack.attack_count, attack.map_penalty) == (2, -5)
    assert any(
        modifier.modifier_type == "status" and modifier.source == "Guidance"
        for modifier in attack.modifier_breakdown
    )
    assert _actor(restored, "warpriest").strikes_this_turn == 2
    assert not restored.inspect().in_progress
    assert restored.inspect().winner_team == "blue"


def test_dim_runic_external_item_saves_flat_check_strikes_and_expires(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """The external physical-item route survives its saved targeting stage."""
    # Hero Points are a session resource, not a class feature. The staged
    # Sorcerer fixture predates that session allocation and starts at 0, so
    # this diagnostic copy grants the ordinary 1 point needed to exercise the
    # real saved reroll route. No class, spell, or statistic fact changes.
    runic_sorcerer = replace(
        content.ANGELIC_SORCERER_STAGED,
        definition_id="angelic_sorcerer_runic_hero_review",
        name="Angelic Sorcerer (Runic Hero Point Review)",
        hero_points=1,
        sheet_notes=content.ANGELIC_SORCERER_STAGED.sheet_notes + (
            "Diagnostic session fixture: starts with 1 Hero Point for the saved Runic Weapon targeting reroll.",
        ),
    )
    _register_definition(monkeypatch, runic_sorcerer)
    setup = replace(
        content.ANGELIC_FIRST_CAST_SETUP,
        setup_id="dim_runic_external_item_review",
        name="Dim external-item Runic Weapon review fixture",
        ambient_light="dim",
        placements=tuple(
            replace(placement, definition_id=runic_sorcerer.definition_id)
            if placement.actor_id == "angelic_sorcerer"
            else placement
            for placement in content.ANGELIC_FIRST_CAST_SETUP.placements
        ),
    )
    _register_setup(monkeypatch, setup)
    # Initiative; failed Runic item targeting and its Hero reroll; Strike
    # targeting, attack, and 2d8 damage.
    game = Encounter.start(setup, rolls=(20, 1, 1, 4, 5, 5, 20, 1, 1))
    assert all(actor.hp == actor.max_hp for actor in game.inspect().actors)
    _settle_initiative(game)

    halo = game.execute(Cast("angelic_halo", actions=1))
    assert halo.status is ResultStatus.PAUSED
    assert halo.inspection.choice is not None
    assert halo.inspection.choice.kind == "spell_blood_magic_recipient"
    assert _choose(game, "angelic_sorcerer").status is ResultStatus.COMPLETED

    runic = game.execute(
        Cast(
            "runic_weapon",
            item_id="sorcerer_ally:longsword",
            slot_id="angelic_rank1",
        )
    )
    assert runic.status is ResultStatus.PAUSED
    assert runic.inspection.choice is not None
    assert runic.inspection.choice.kind == "spell_willingness"
    assert _actor(game, "angelic_sorcerer").spontaneous_slots[0].remaining == 2
    targeting = _choose(game, "willing")
    assert targeting.status is ResultStatus.PAUSED
    assert targeting.inspection.choice is not None
    assert targeting.inspection.choice.kind == "concealment_hero_reroll"

    save_path = tmp_path / "dim-runic-item-target.json"
    game.save(save_path)
    restored = Encounter.load(save_path)
    assert restored.inspect() == targeting.inspection
    applied = _choose(restored, "spend_hero_point")
    assert applied.status is ResultStatus.COMPLETED
    assert _actor(restored, "angelic_sorcerer").hero_points == 0
    effect = next(
        effect
        for effect in restored._state.active_item_effects
        if effect.kind == "runic_weapon"
    )
    assert effect.item_id == "sorcerer_ally:longsword"
    assert effect.expires_at_world_time == 60
    assert restored.inspect().turn_actor_id == "sorcerer_dog"

    assert restored.execute(EndTurn()).status is ResultStatus.COMPLETED
    assert restored.inspect().turn_actor_id == "sorcerer_ally"
    assert restored.execute(Stride((Position(3, 2), Position(4, 2)))).status is ResultStatus.COMPLETED
    strike = restored.execute(
        Strike(
            "sorcerer_dog",
            attack_id="longsword",
            item_id="sorcerer_ally:longsword",
        )
    )
    assert strike.status is ResultStatus.PAUSED
    assert strike.inspection.choice is not None
    assert strike.inspection.choice.kind == "concealment_hero_reroll"
    events = list(strike.events)
    after_target = _choose(restored, "keep")
    events.extend(after_target.events)
    assert after_target.status is ResultStatus.PAUSED
    assert after_target.inspection.choice is not None
    assert after_target.inspection.choice.kind == "attack_hero_reroll"
    victory = _choose(restored, "keep")
    events.extend(victory.events)
    assert victory.status is ResultStatus.COMPLETED
    damage = next(event.damage for event in events if event.damage is not None)
    assert damage.components[0].dice == (8, 8)
    assert damage.components[0].rolls == (1, 1)
    assert not restored.inspect().in_progress

    # Refocus provides the real public ten-minute elapsed-time transition.
    assert restored.refocus("angelic_sorcerer").status is ResultStatus.COMPLETED
    assert restored.inspect().world_time_seconds == 600
    assert _actor(restored, "angelic_sorcerer").focus_points == 1
    assert _actor(restored, "angelic_sorcerer").spontaneous_slots[0].remaining == 2
    assert not restored._state.active_item_effects
