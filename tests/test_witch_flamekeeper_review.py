"""Independent source and play review for the selected Flamekeeper Witch.

Sources checked 2026-09-18:

* Witch: https://2e.aonprd.com/Classes.aspx?ID=38
* Faith's Flamekeeper: https://2e.aonprd.com/Patrons.aspx?ID=12
* Patron's Puppet: https://2e.aonprd.com/Spells.aspx?ID=1882
* Stoke the Heart: https://2e.aonprd.com/Spells.aspx?ID=1892
* Forbidding Ward: https://2e.aonprd.com/Spells.aspx?ID=1535
* Command: https://2e.aonprd.com/Spells.aspx?ID=1470
* Fleeing: https://2e.aonprd.com/Conditions.aspx?ID=74
* Sigil: https://2e.aonprd.com/Spells.aspx?ID=1673
* Detect Magic: https://2e.aonprd.com/Spells.aspx?ID=1485
* Familiar and Pet: https://2e.aonprd.com/Rules.aspx?ID=2121 and
  https://2e.aonprd.com/Feats.aspx?ID=5186
* Release: https://2e.aonprd.com/Actions.aspx?ID=2300
* Sustain: https://2e.aonprd.com/Actions.aspx?ID=2317
* Temporary HP: https://2e.aonprd.com/Rules.aspx?ID=2321
* Hero Points: https://2e.aonprd.com/Rules.aspx?ID=2333

The familiar's otherwise-unspecified recovery clock uses the user-approved
local convention recorded in ``docs/work-log/witch-recovery-handoff.md``:
its passive start/end boundaries occur with the Witch's turns even when it is
uncommanded, without granting initiative, actions, or reactions.  The Witch
class itself supplies the remaining death contract: a dead familiar is
replaced at the Witch's next daily preparations, knows the same spells, and
does not remove spells the Witch already prepared.
"""

from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
from pathlib import Path
from types import MappingProxyType

import pytest
import pf2e.content as content
from pf2e.content import get_definition, get_setup
from pf2e.encounter import Encounter
from pf2e.model import (
    Cast,
    Choose,
    CreaturePlacement,
    EncounterSetup,
    EndTurn,
    Interact,
    Position,
    Release,
    ResultStatus,
    Strike,
    Sustain,
)
from pf2e.terminal import _choose_cast_inputs, run_terminal
from pf2e.witch import (
    CommandFamiliar,
    FamiliarPickup,
    FamiliarRelease,
    FamiliarStride,
    PatronsPuppet,
    RestoreSpirit,
)
from terminal_test_helpers import BoundedInput, BoundedTranscript


def _settle(game: Encounter) -> None:
    for _ in range(12):
        choice = game.inspect().choice
        if choice is None:
            return
        options = {option.option_id for option in choice.options}
        option_id = "keep" if "keep" in options else choice.options[0].option_id
        result = game.choose(choice.choice_id, option_id, choice.owner_actor_id)
        assert result.status in {ResultStatus.PAUSED, ResultStatus.COMPLETED}
    raise AssertionError("bounded choice settlement did not finish")


def _start(*, rolls: tuple[int, ...] = (20, 8, 7, 1, 1, 1)) -> Encounter:
    game = Encounter.start(get_setup("faiths_flamekeeper_first_play"), rolls=rolls)
    _settle(game)
    assert game.inspect().turn_actor_id == "witch"
    return game


def _lifecycle_setup(monkeypatch: pytest.MonkeyPatch) -> EncounterSetup:
    """Register a source-identical foe with only its HP shortened for review."""
    enemy = replace(
        get_definition("flamekeeper_common_speaker"),
        definition_id="review_flamekeeper_familiar_enemy",
        hp=1,
    )
    setup = EncounterSetup(
        setup_id="review_flamekeeper_familiar_lifecycle",
        name="Flamekeeper Familiar Lifecycle Review",
        width=5,
        height=4,
        placements=(
            CreaturePlacement(
                "witch", "faiths_flamekeeper_witch_level_1",
                "Flamekeeper Witch", "blue", Position(1, 2),
            ),
            CreaturePlacement(
                "fox", "faiths_flamekeeper_fox",
                "Flamekeeper Fox", "blue", Position(1, 2),
            ),
            CreaturePlacement(
                "ally", "faiths_flamekeeper_witch_level_1",
                "Witch Ally", "blue", Position(3, 2),
            ),
            CreaturePlacement(
                "enemy", enemy.definition_id,
                "Lifecycle Enemy", "red", Position(2, 1),
            ),
        ),
    )
    monkeypatch.setattr(
        content,
        "_STAGED_CREATURES",
        MappingProxyType({**content._STAGED_CREATURES, enemy.definition_id: enemy}),
    )
    monkeypatch.setattr(
        content,
        "_STAGED_SETUPS",
        MappingProxyType({**content._STAGED_SETUPS, setup.setup_id: setup}),
    )
    return setup


def _knock_out_review_fox(
    monkeypatch: pytest.MonkeyPatch,
    *, recovery_roll: int,
    tail: tuple[int, ...] = (8, 20, 1),
) -> Encounter:
    """Critically knock out the fox, then advance to its Witch-owned check."""
    setup = _lifecycle_setup(monkeypatch)
    game = Encounter.start(
        setup,
        # Witch/ally/enemy initiatives; enemy Club attack/damage; recovery.
        rolls=(1, 2, 20, 20, 2, recovery_roll, *tail),
    )
    _settle(game)
    assert game.inspect().turn_actor_id == "enemy"
    knocked_out = game.execute(Strike("fox", "club"))
    assert knocked_out.status is ResultStatus.PAUSED
    choice = knocked_out.inspection.choice
    assert choice is not None and choice.kind == "heroic_recovery_damage"
    assert choice.owner_actor_id == "witch"
    knocked_out = game.choose(choice.choice_id, "normal", choice.owner_actor_id)
    fox = game._state.creatures["fox"]
    assert (fox.hp, fox.dying, fox.unconscious, fox.dead) == (0, 2, True, False)
    assert game.execute(EndTurn()).status is ResultStatus.COMPLETED
    assert game.inspect().turn_actor_id == "ally"
    reached_witch = game.execute(EndTurn())
    assert reached_witch.status is ResultStatus.PAUSED
    choice = reached_witch.inspection.choice
    assert choice is not None and choice.kind == "recovery_start_heroic"
    assert choice.owner_actor_id == "witch"
    return game


def test_fixed_sheet_and_familiar_match_the_selected_source_contract() -> None:
    witch = get_definition("faiths_flamekeeper_witch_level_1")
    fox = get_definition("faiths_flamekeeper_fox")

    assert "faiths_flamekeeper_first_play" in content.SETUPS
    assert "faiths_flamekeeper_first_play" not in content._STAGED_SETUPS
    assert {
        "faiths_flamekeeper_witch_level_1",
        "faiths_flamekeeper_fox",
        "flamekeeper_common_speaker",
    } <= set(content.CREATURES)

    assert witch.ability_modifiers == (
        ("strength", 0), ("dexterity", 2), ("constitution", 2),
        ("intelligence", 4), ("wisdom", 0), ("charisma", 1),
    )
    assert (witch.hp, witch.ac, witch.perception, witch.land_speed_ft) == (16, 15, 3, 30)
    assert dict((name, modifier) for name, _rank, modifier in witch.saves) == {
        "fortitude": 5, "reflex": 5, "will": 5,
    }
    assert (witch.spell_attack, witch.spell_dc, witch.class_dc) == (7, 17, 17)
    assert witch.attacks[0].attack_attribute == "dexterity"
    assert witch.attacks[0].damage_attribute == "strength"
    assert len(witch.languages) == 6 and witch.languages[0] == "Common"
    assert {name for name, _rank, _modifier in witch.skills} == {
        "arcana", "crafting", "medicine", "occultism", "society", "stealth",
        "thievery", "nature", "academia_lore", "athletics", "acrobatics", "religion",
    }
    assert {slot.spell_id for slot in witch.prepared_spells if slot.cantrip} == {
        "divine_lance", "shield", "guidance", "light", "forbidding_ward",
    }
    assert [slot.spell_id for slot in witch.prepared_spells if not slot.cantrip] == [
        "command", "heal",
    ]
    assert {spell.spell_id for spell in witch.spontaneous_spells} == {"stoke_the_heart"}
    assert {spell.spell_id for spell in witch.focus_spells} == {"patrons_puppet"}
    assert witch.focus_points == witch.focus_capacity == 1

    assert (fox.hp, fox.ac, fox.perception, fox.land_speed_ft) == (7, 15, 5, 40)
    assert fox.size == "tiny" and fox.vision == "low_light" and fox.initiative_exempt
    assert fox.attacks == () and fox.languages == ()
    assert fox.ability_modifiers == ()
    assert {name: modifier for name, _rank, modifier in fox.skills} == {
        "acrobatics": 5,
        "arcana": 1,
        "athletics": 1,
        "crafting": 1,
        "deception": 1,
        "diplomacy": 1,
        "intimidation": 1,
        "medicine": 1,
        "nature": 1,
        "occultism": 1,
        "performance": 1,
        "religion": 1,
        "society": 1,
        "stealth": 5,
        "survival": 1,
        "thievery": 1,
    }
    assert dict((name, modifier) for name, _rank, modifier in fox.saves) == {
        "fortitude": 5, "reflex": 5, "will": 5,
    }
    assert {"manual_dexterity", "tough", "fast_movement", "restored_spirit"} <= set(
        fox.abilities
    )


def test_saved_before_and_after_restored_spirit_windows_resume_exactly_once(
    tmp_path: Path,
) -> None:
    before = _start()
    begun = before.execute(Cast("stoke_the_heart", target_id="ally"))
    assert begun.status is ResultStatus.PAUSED
    assert begun.inspection.choice is not None
    assert begun.inspection.choice.kind == "witch_restored_spirit_timing"
    committed = deepcopy(before._state)
    before_path = tmp_path / "witch-before-window.json"
    before.save(before_path)
    before = Encounter.load(before_path)
    choice = before.inspect().choice
    assert choice is not None
    offered = before.choose(choice.choice_id, "before:ally", choice.owner_actor_id)
    willingness = offered.inspection.choice
    assert willingness is not None and willingness.kind == "witch_restored_spirit_willingness"
    assert willingness.owner_actor_id == "ally"
    resolved = before.choose(willingness.choice_id, "willing", willingness.owner_actor_id)
    assert resolved.status is ResultStatus.COMPLETED
    assert before._state.creatures["witch"].actions_remaining == 2
    assert before._state.creatures["ally"].temporary_hp == 2
    assert before._state.creatures["witch"].witch_restored_spirit_used_start == 1
    assert len([effect for effect in before._state.active_effects if effect.kind == "stoke_the_heart"]) == 1
    assert before.inspect().choice is None
    assert committed.creatures["witch"].actions_remaining == 2

    after = _start()
    paused = after.execute(Cast("stoke_the_heart", target_id="ally"))
    choice = paused.inspection.choice
    assert choice is not None
    selected = after.choose(choice.choice_id, "after", choice.owner_actor_id)
    assert selected.status is ResultStatus.PAUSED
    assert selected.inspection.choice is not None
    assert selected.inspection.choice.kind == "witch_restored_spirit"
    assert after._state.creatures["ally"].temporary_hp == 0
    after_path = tmp_path / "witch-after-window.json"
    after.save(after_path)
    after = Encounter.load(after_path)
    choice = after.inspect().choice
    assert choice is not None
    offered = after.choose(choice.choice_id, "ally", choice.owner_actor_id)
    willingness = offered.inspection.choice
    assert willingness is not None and willingness.kind == "witch_restored_spirit_willingness"
    finished = after.choose(willingness.choice_id, "willing", willingness.owner_actor_id)
    assert finished.status is ResultStatus.COMPLETED
    assert after._state.creatures["ally"].temporary_hp == 2
    assert after._state.creatures["witch"].actions_remaining == 2
    assert len([effect for effect in after._state.active_effects if effect.kind == "stoke_the_heart"]) == 1

    gate_path = tmp_path / "witch-hex-gate.json"
    after.save(gate_path)
    after = Encounter.load(gate_path)
    blocked = after.execute(Cast("stoke_the_heart", target_id="ally"))
    assert blocked.status is ResultStatus.COMPLETED
    assert any(event.kind == "hex_cast_lost" for event in blocked.events)
    assert after._state.creatures["witch"].actions_remaining == 1
    assert len([effect for effect in after._state.active_effects if effect.kind == "stoke_the_heart"]) == 1


def test_familiar_gets_one_saved_two_action_allotment_and_release_is_free(
    tmp_path: Path,
) -> None:
    game = _start()
    witch = game._state.creatures["witch"]
    fox = game._state.creatures["fox"]
    item_id = witch.held_items.pop()
    fox.held_items.append(item_id)
    commanded = game.execute(CommandFamiliar("fox", (
        FamiliarRelease(item_id),
        FamiliarPickup(item_id),
        FamiliarStride((Position(2, 2),)),
    )))
    assert commanded.status is ResultStatus.COMPLETED
    fox = game._state.creatures["fox"]
    witch = game._state.creatures["witch"]
    assert fox.position == Position(2, 2) and fox.held_items == [item_id]
    assert witch.actions_remaining == 2
    save_path = tmp_path / "witch-minion-allotment.json"
    game.save(save_path)
    game = Encounter.load(save_path)
    duplicate = game.execute(CommandFamiliar(
        "fox", (FamiliarStride((Position(1, 2),)),)
    ))
    assert duplicate.status is ResultStatus.REJECTED
    fox = game._state.creatures["fox"]
    witch = game._state.creatures["witch"]
    assert fox.position == Position(2, 2) and witch.actions_remaining == 2


def test_familiar_is_targetable_without_receiving_initiative_or_actions() -> None:
    game = _start(rolls=(20, 8, 7, 20, 1))
    assert "fox" not in game._state.initiative_order
    assert "fox" in {actor.actor_id for actor in game.inspect().actors}
    assert game._state.creatures["fox"].actions_remaining == 0
    assert get_definition(game._state.creatures["fox"].definition_id).attacks == ()
    game._state.creatures["enemy"].position = Position(2, 1)

    assert game.execute(EndTurn()).status is ResultStatus.COMPLETED
    assert game.execute(EndTurn()).status is ResultStatus.COMPLETED
    assert game.inspect().turn_actor_id == "enemy"
    result = game.execute(Strike("fox", "club"))
    assert result.status is ResultStatus.COMPLETED
    assert any(event.kind == "strike" for event in result.events)
    assert game._state.creatures["fox"].hp == 1


def test_attackless_familiar_does_not_supply_a_flank() -> None:
    game = _start(rolls=(20, 8, 7, 10, 1))
    game._state.creatures["ally"].position = Position(0, 0)
    game._state.creatures["enemy"].position = Position(2, 2)
    game._state.creatures["fox"].position = Position(3, 2)

    result = game.execute(Strike("enemy", "fist"))
    assert result.status is ResultStatus.PAUSED
    check = next(event.check for event in result.events if event.kind == "strike")
    assert check is not None and check.dc == 15


def test_standalone_restored_spirit_is_rejected_atomically() -> None:
    game = _start()
    state_before = deepcopy(game._state)
    dice_before = game._dice.to_data()
    result = game.execute(RestoreSpirit("ally"))
    assert result.status is ResultStatus.REJECTED
    assert game._state == state_before
    assert game._dice.to_data() == dice_before


def test_release_closes_patrons_puppet_turn_begins_trigger() -> None:
    game = _start()
    item_id = game._state.creatures["witch"].held_items[0]
    released = game.execute(Release(item_id))
    assert released.status is ResultStatus.COMPLETED
    assert game._state.creatures["witch"].actions_remaining == 3

    state_before = deepcopy(game._state)
    result = game.execute(PatronsPuppet(
        "fox", (FamiliarStride((Position(2, 2),)),)
    ))
    assert result.status is ResultStatus.REJECTED
    assert game._state == state_before


def test_stoke_status_bonus_applies_to_an_allys_divine_lance_damage_roll() -> None:
    game = _start(rolls=(20, 8, 7, 8, 1, 1))
    cast = game.execute(Cast("stoke_the_heart", target_id="ally"))
    choice = cast.inspection.choice
    assert choice is not None and choice.kind == "witch_restored_spirit_timing"
    assert game.choose(choice.choice_id, "before:witch", choice.owner_actor_id).status is ResultStatus.COMPLETED
    assert game.execute(EndTurn()).status is ResultStatus.COMPLETED
    assert game.inspect().turn_actor_id == "ally"

    attack = game.execute(Cast("divine_lance", target_id="enemy"))
    assert attack.status is ResultStatus.PAUSED
    choice = attack.inspection.choice
    assert choice is not None and choice.kind == "spell_attack_hero_reroll"
    resolved = game.choose(choice.choice_id, "keep", choice.owner_actor_id)
    assert resolved.status is ResultStatus.COMPLETED
    damage = next(event.damage for event in resolved.events if event.damage is not None)
    assert damage.components[0].modifier == 2
    assert damage.rolled_total == 4
    assert damage.total == 4


def test_stoke_targets_any_creature_in_range_including_an_enemy() -> None:
    game = _start()
    option = next(
        spell for spell in game.options().spells
        if spell.spell_id == "stoke_the_heart"
    )
    targets = next(
        target_option.targets for target_option in option.target_options
        if target_option.actions == 1
    )
    assert set(targets) == {"witch", "fox", "ally", "enemy"}

    cast = game.execute(Cast("stoke_the_heart", target_id="enemy"))
    timing = cast.inspection.choice
    assert cast.status is ResultStatus.PAUSED
    assert timing is not None and timing.kind == "witch_restored_spirit_timing"
    finished = game.choose(timing.choice_id, "before:witch", timing.owner_actor_id)
    assert finished.status is ResultStatus.COMPLETED
    assert any(
        effect.kind == "stoke_the_heart" and effect.target_actor_id == "enemy"
        for effect in game._state.active_effects
    )


def test_unsustained_stoke_survives_the_next_turn_then_expires_at_source_end(
    tmp_path: Path,
) -> None:
    game = _start()
    cast = game.execute(Cast("stoke_the_heart", target_id="ally"))
    choice = cast.inspection.choice
    assert choice is not None
    assert game.choose(choice.choice_id, "before:witch", choice.owner_actor_id).status is ResultStatus.COMPLETED
    effect = next(item for item in game._state.active_effects if item.kind == "stoke_the_heart")
    assert effect.sustain_expires_at_source_end == 2

    for expected_actor in ("ally", "enemy", "witch"):
        assert game.execute(EndTurn()).status is ResultStatus.COMPLETED
        assert game.inspect().turn_actor_id == expected_actor
        assert any(item.effect_id == effect.effect_id for item in game._state.active_effects)

    path = tmp_path / "stoke-before-source-end.json"
    game.save(path)
    game = Encounter.load(path)
    assert game.execute(EndTurn()).status is ResultStatus.COMPLETED
    assert not any(item.effect_id == effect.effect_id for item in game._state.active_effects)


def test_sustain_never_moves_stokes_saved_one_minute_cast_cap(tmp_path: Path) -> None:
    game = _start()
    cast = game.execute(Cast("stoke_the_heart", target_id="ally"))
    choice = cast.inspection.choice
    assert choice is not None
    assert game.choose(choice.choice_id, "before:witch", choice.owner_actor_id).status is ResultStatus.COMPLETED
    effect = next(item for item in game._state.active_effects if item.kind == "stoke_the_heart")
    fixed_cap = (effect.expires_at_source_start, effect.expires_at_world_time)
    assert fixed_cap == (11, 60)

    # Move to the Witch's next turn, then Sustain on turns 2 through 10.
    for _actor_id in ("ally", "enemy"):
        assert game.execute(EndTurn()).status is ResultStatus.COMPLETED
    assert game.execute(EndTurn()).status is ResultStatus.COMPLETED
    assert game.inspect().turn_actor_id == "witch"

    for source_start in range(2, 11):
        current = next(item for item in game._state.active_effects if item.effect_id == effect.effect_id)
        sustained = game.execute(Sustain(current.effect_id))
        assert sustained.status in {ResultStatus.PAUSED, ResultStatus.COMPLETED}
        if (choice := game.inspect().choice) is not None:
            options = {option.option_id for option in choice.options}
            assert "decline" not in options
            assert "before:witch" in options
            assert game.choose(choice.choice_id, "before:witch", choice.owner_actor_id).status is ResultStatus.COMPLETED
        current = next(item for item in game._state.active_effects if item.effect_id == effect.effect_id)
        assert (current.expires_at_source_start, current.expires_at_world_time) == fixed_cap
        if source_start == 6:
            path = tmp_path / "stoke-fixed-cap.json"
            game.save(path)
            game = Encounter.load(path)
        for expected_actor in ("ally", "enemy", "witch"):
            assert game.execute(EndTurn()).status is ResultStatus.COMPLETED
            assert game.inspect().turn_actor_id == expected_actor

    assert not any(item.effect_id == effect.effect_id for item in game._state.active_effects)


def test_restored_spirit_survives_round_wrap_until_the_witchs_next_start(
    tmp_path: Path,
) -> None:
    game = Encounter.start(
        get_setup("faiths_flamekeeper_first_play"), rolls=(8, 20, 7, 1, 1, 1)
    )
    _settle(game)
    assert game.inspect().turn_actor_id == "ally"
    assert game.execute(EndTurn()).status is ResultStatus.COMPLETED
    assert game.inspect().turn_actor_id == "witch"

    cast = game.execute(Cast("stoke_the_heart", target_id="ally"))
    timing = cast.inspection.choice
    assert timing is not None and timing.kind == "witch_restored_spirit_timing"
    after = game.choose(timing.choice_id, "after", timing.owner_actor_id)
    recipient = after.inspection.choice
    assert recipient is not None and recipient.kind == "witch_restored_spirit"
    offered = game.choose(recipient.choice_id, "ally", recipient.owner_actor_id)
    willingness = offered.inspection.choice
    assert willingness is not None and willingness.kind == "witch_restored_spirit_willingness"
    assert game.choose(willingness.choice_id, "willing", willingness.owner_actor_id).status is ResultStatus.COMPLETED
    assert game._state.creatures["ally"].temporary_hp == 2

    path = tmp_path / "restored-spirit-source-start.json"
    game.save(path)
    game = Encounter.load(path)
    assert game.execute(EndTurn()).status is ResultStatus.COMPLETED
    assert game.inspect().turn_actor_id == "enemy"
    assert game.execute(EndTurn()).status is ResultStatus.COMPLETED
    assert game.inspect().turn_actor_id == "ally"
    assert game._state.creatures["ally"].temporary_hp == 2
    assert game.execute(EndTurn()).status is ResultStatus.COMPLETED
    assert game.inspect().turn_actor_id == "witch"
    assert game._state.creatures["ally"].temporary_hp == 0
    assert game._state.creatures["ally"].temporary_hp_source_id is None
    assert game._state.creatures["ally"].temporary_hp_expires_at_source_start == 0


def test_absorbed_restored_spirit_pool_clears_its_saved_source_start_deadline(
    tmp_path: Path,
) -> None:
    game = _start(rolls=(20, 8, 7, 20, 6, 6))
    cast = game.execute(Cast("stoke_the_heart", target_id="ally"))
    timing = cast.inspection.choice
    assert timing is not None
    after = game.choose(timing.choice_id, "after", timing.owner_actor_id)
    recipient = after.inspection.choice
    assert recipient is not None
    offered = game.choose(recipient.choice_id, "ally", recipient.owner_actor_id)
    willingness = offered.inspection.choice
    assert willingness is not None and willingness.kind == "witch_restored_spirit_willingness"
    assert game.choose(willingness.choice_id, "willing", willingness.owner_actor_id).status is ResultStatus.COMPLETED
    assert game._state.creatures["ally"].temporary_hp == 2

    game._state.creatures["enemy"].position = Position(3, 2)
    assert game.execute(EndTurn()).status is ResultStatus.COMPLETED
    assert game.execute(EndTurn()).status is ResultStatus.COMPLETED
    assert game.inspect().turn_actor_id == "enemy"
    strike = game.execute(Strike("ally", "club"))
    assert strike.status is ResultStatus.COMPLETED
    ally = game._state.creatures["ally"]
    assert ally.temporary_hp == 0
    assert ally.temporary_hp_source_id is None
    assert ally.temporary_hp_expires_at_source_start == 0

    path = tmp_path / "spent-restored-spirit-pool.json"
    game.save(path)
    loaded = Encounter.load(path)
    assert loaded._state.creatures["ally"].temporary_hp_expires_at_source_start == 0


def _stoke_until_next_witch_turn() -> tuple[Encounter, str]:
    game = _start()
    cast = game.execute(Cast("stoke_the_heart", target_id="witch"))
    timing = cast.inspection.choice
    assert timing is not None
    assert game.choose(timing.choice_id, "before:witch", timing.owner_actor_id).status is ResultStatus.COMPLETED
    effect = next(item for item in game._state.active_effects if item.kind == "stoke_the_heart")
    for expected_actor in ("ally", "enemy", "witch"):
        assert game.execute(EndTurn()).status is ResultStatus.COMPLETED
        assert game.inspect().turn_actor_id == expected_actor
    return game, effect.effect_id


def test_sustain_restored_spirit_before_and_after_windows_round_trip(
    tmp_path: Path,
) -> None:
    before, effect_id = _stoke_until_next_witch_turn()
    paused = before.execute(Sustain(effect_id))
    timing = paused.inspection.choice
    assert timing is not None and timing.kind == "witch_restored_spirit_timing"
    assert "decline" not in {option.option_id for option in timing.options}
    # The saved before window must still be before Sustain's effect.
    assert before._state.creatures["witch"].actions_remaining == 3
    effect = next(item for item in before._state.active_effects if item.effect_id == effect_id)
    assert effect.sustain_expires_at_source_end == 2
    before_path = tmp_path / "sustain-restored-before.json"
    before.save(before_path)
    before = Encounter.load(before_path)
    timing = before.inspect().choice
    assert timing is not None
    offered = before.choose(timing.choice_id, "before:ally", timing.owner_actor_id)
    willingness = offered.inspection.choice
    assert willingness is not None and willingness.kind == "witch_restored_spirit_willingness"
    assert before._state.creatures["witch"].actions_remaining == 3
    completed = before.choose(willingness.choice_id, "willing", willingness.owner_actor_id)
    assert completed.status is ResultStatus.COMPLETED
    assert before._state.creatures["ally"].temporary_hp == 2
    assert before._state.creatures["witch"].actions_remaining == 2
    effect = next(item for item in before._state.active_effects if item.effect_id == effect_id)
    assert effect.sustain_expires_at_source_end == 3

    after, effect_id = _stoke_until_next_witch_turn()
    paused = after.execute(Sustain(effect_id))
    timing = paused.inspection.choice
    assert timing is not None and timing.kind == "witch_restored_spirit_timing"
    selected = after.choose(timing.choice_id, "after", timing.owner_actor_id)
    recipient = selected.inspection.choice
    assert selected.status is ResultStatus.PAUSED
    assert recipient is not None and recipient.kind == "witch_restored_spirit"
    after_path = tmp_path / "sustain-restored-after.json"
    after.save(after_path)
    after = Encounter.load(after_path)
    recipient = after.inspect().choice
    assert recipient is not None
    offered = after.choose(recipient.choice_id, "ally", recipient.owner_actor_id)
    willingness = offered.inspection.choice
    assert willingness is not None and willingness.kind == "witch_restored_spirit_willingness"
    finished = after.choose(willingness.choice_id, "willing", willingness.owner_actor_id)
    assert finished.status is ResultStatus.COMPLETED
    assert after._state.creatures["ally"].temporary_hp == 2
    assert after._state.creatures["witch"].actions_remaining == 2
    effect = next(item for item in after._state.active_effects if item.effect_id == effect_id)
    assert effect.sustain_expires_at_source_end == 3


def test_patrons_puppet_restored_spirit_timing_uses_pre_or_post_move_recipients(
    tmp_path: Path,
) -> None:
    stride = FamiliarStride((
        Position(1, 1), Position(2, 1), Position(3, 1),
        Position(4, 1), Position(5, 1), Position(6, 1),
    ))

    before = _start()
    paused = before.execute(PatronsPuppet("fox", (stride,)))
    timing = paused.inspection.choice
    assert timing is not None and timing.kind == "witch_restored_spirit_timing"
    assert "decline" not in {option.option_id for option in timing.options}
    # The saved before window precedes the familiar movement and focus expenditure.
    assert before._state.creatures["fox"].position == Position(1, 2)
    assert before._state.creatures["witch"].focus_points == 1
    before_path = tmp_path / "puppet-restored-before.json"
    before.save(before_path)
    before = Encounter.load(before_path)
    timing = before.inspect().choice
    assert timing is not None
    offered = before.choose(timing.choice_id, "before:ally", timing.owner_actor_id)
    willingness = offered.inspection.choice
    assert willingness is not None and willingness.kind == "witch_restored_spirit_willingness"
    assert before._state.creatures["fox"].position == Position(1, 2)
    finished = before.choose(willingness.choice_id, "willing", willingness.owner_actor_id)
    assert finished.status is ResultStatus.COMPLETED
    assert before._state.creatures["ally"].temporary_hp == 2
    assert before._state.creatures["fox"].position == Position(6, 1)
    assert before._state.creatures["witch"].actions_remaining == 3
    assert before._state.creatures["witch"].focus_points == 0

    after = _start()
    paused = after.execute(PatronsPuppet("fox", (stride,)))
    timing = paused.inspection.choice
    assert timing is not None and timing.kind == "witch_restored_spirit_timing"
    selected = after.choose(timing.choice_id, "after", timing.owner_actor_id)
    recipient = selected.inspection.choice
    assert selected.status is ResultStatus.PAUSED
    assert after._state.creatures["fox"].position == Position(6, 1)
    assert recipient is not None and recipient.kind == "witch_restored_spirit"
    assert {option.option_id for option in recipient.options} == {"fox", "enemy"}
    after_path = tmp_path / "puppet-restored-after.json"
    after.save(after_path)
    after = Encounter.load(after_path)
    recipient = after.inspect().choice
    assert recipient is not None
    offered = after.choose(recipient.choice_id, "fox", recipient.owner_actor_id)
    willingness = offered.inspection.choice
    assert willingness is not None and willingness.kind == "witch_restored_spirit_willingness"
    finished = after.choose(willingness.choice_id, "willing", willingness.owner_actor_id)
    assert finished.status is ResultStatus.COMPLETED
    assert after._state.creatures["fox"].temporary_hp == 2
    assert after._state.creatures["witch"].actions_remaining == 3
    assert after._state.creatures["witch"].focus_points == 0


def test_restored_spirit_recipient_owns_saved_keep_or_replace_temp_hp_choice(
    tmp_path: Path,
) -> None:
    game = _start()
    ally = game._state.creatures["ally"]
    ally.temporary_hp = 5
    ally.temporary_hp_source_id = "review:existing-pool"
    ally.temporary_hp_expires_at_seconds = 600

    cast = game.execute(Cast("stoke_the_heart", target_id="witch"))
    timing = cast.inspection.choice
    assert timing is not None
    selected = game.choose(timing.choice_id, "after", timing.owner_actor_id)
    recipient = selected.inspection.choice
    assert recipient is not None
    replacing = game.choose(recipient.choice_id, "ally", recipient.owner_actor_id)
    replacement = replacing.inspection.choice
    assert replacing.status is ResultStatus.PAUSED
    assert replacement is not None and replacement.owner_actor_id == "ally"
    assert {option.option_id for option in replacement.options} == {"keep_existing", "gain_new"}

    path = tmp_path / "restored-spirit-temp-hp-choice.json"
    game.save(path)
    game = Encounter.load(path)
    replacement = game.inspect().choice
    assert replacement is not None
    kept = game.choose(replacement.choice_id, "keep_existing", replacement.owner_actor_id)
    assert kept.status is ResultStatus.COMPLETED
    ally = game._state.creatures["ally"]
    assert (
        ally.temporary_hp,
        ally.temporary_hp_source_id,
        ally.temporary_hp_expires_at_seconds,
        ally.temporary_hp_expires_at_source_start,
    ) == (5, "review:existing-pool", 600, 0)
    assert game._state.creatures["witch"].witch_restored_spirit_used_start == 1

    replaced = _start()
    ally = replaced._state.creatures["ally"]
    ally.temporary_hp = 5
    ally.temporary_hp_source_id = "review:existing-pool"
    ally.temporary_hp_expires_at_seconds = 600
    cast = replaced.execute(Cast("stoke_the_heart", target_id="witch"))
    timing = cast.inspection.choice
    assert timing is not None
    selected = replaced.choose(timing.choice_id, "after", timing.owner_actor_id)
    recipient = selected.inspection.choice
    assert recipient is not None
    replacing = replaced.choose(recipient.choice_id, "ally", recipient.owner_actor_id)
    replacement = replacing.inspection.choice
    assert replacement is not None
    gained = replaced.choose(replacement.choice_id, "gain_new", replacement.owner_actor_id)
    assert gained.status is ResultStatus.COMPLETED
    ally = replaced._state.creatures["ally"]
    assert ally.temporary_hp == 2
    assert ally.temporary_hp_source_id == "restored_spirit:witch:1"
    assert ally.temporary_hp_expires_at_seconds is None
    assert ally.temporary_hp_expires_at_source_start == 2


def test_puppet_before_existing_temp_hp_choice_resumes_the_exact_saved_command(
    tmp_path: Path,
) -> None:
    game = _start()
    ally = game._state.creatures["ally"]
    ally.temporary_hp = 5
    ally.temporary_hp_source_id = "review:existing-pool"
    ally.temporary_hp_expires_at_seconds = 600
    stride = FamiliarStride((
        Position(1, 1), Position(2, 1), Position(3, 1),
        Position(4, 1), Position(5, 1), Position(6, 1),
    ))

    paused = game.execute(PatronsPuppet("fox", (stride,)))
    timing = paused.inspection.choice
    assert timing is not None and game._state.creatures["fox"].position == Position(1, 2)
    selected = game.choose(timing.choice_id, "before:ally", timing.owner_actor_id)
    replacement = selected.inspection.choice
    assert replacement is not None and replacement.kind == "witch_restored_spirit_temp_hp"
    assert game._state.creatures["fox"].position == Position(1, 2)

    path = tmp_path / "puppet-before-existing-temp-hp.json"
    game.save(path)
    game = Encounter.load(path)
    replacement = game.inspect().choice
    assert replacement is not None
    finished = game.choose(
        replacement.choice_id, "keep_existing", replacement.owner_actor_id,
    )
    assert finished.status is ResultStatus.COMPLETED
    assert game._state.creatures["fox"].position == Position(6, 1)
    assert game._state.creatures["witch"].focus_points == 0
    assert game._state.creatures["witch"].actions_remaining == 3
    assert game._state.creatures["ally"].temporary_hp == 5


def test_restored_spirit_uses_target_owned_willingness_for_any_nearby_creature(
    tmp_path: Path,
) -> None:
    accepted = _start()
    accepted._state.creatures["enemy"].position = Position(4, 2)
    cast = accepted.execute(Cast("stoke_the_heart", target_id="witch"))
    timing = cast.inspection.choice
    assert timing is not None
    after = accepted.choose(timing.choice_id, "after", timing.owner_actor_id)
    recipient = after.inspection.choice
    assert recipient is not None and recipient.kind == "witch_restored_spirit"
    assert "enemy" in {option.option_id for option in recipient.options}
    offered = accepted.choose(recipient.choice_id, "enemy", recipient.owner_actor_id)
    willingness = offered.inspection.choice
    assert willingness is not None and willingness.owner_actor_id == "enemy"

    path = tmp_path / "enemy-restored-spirit-willingness.json"
    accepted.save(path)
    accepted = Encounter.load(path)
    willingness = accepted.inspect().choice
    assert willingness is not None
    finished = accepted.choose(
        willingness.choice_id, "willing", willingness.owner_actor_id,
    )
    assert finished.status is ResultStatus.COMPLETED
    assert accepted._state.creatures["enemy"].temporary_hp == 2

    refused = _start()
    cast = refused.execute(Cast("stoke_the_heart", target_id="witch"))
    timing = cast.inspection.choice
    assert timing is not None
    after = refused.choose(timing.choice_id, "after", timing.owner_actor_id)
    recipient = after.inspection.choice
    assert recipient is not None
    offered = refused.choose(recipient.choice_id, "ally", recipient.owner_actor_id)
    willingness = offered.inspection.choice
    assert willingness is not None
    declined = refused.choose(
        willingness.choice_id, "unwilling", willingness.owner_actor_id,
    )
    assert declined.status is ResultStatus.COMPLETED
    assert refused._state.creatures["ally"].temporary_hp == 0
    assert refused._state.creatures["witch"].witch_restored_spirit_used_start == 0
    effect = next(item for item in refused._state.active_effects if item.kind == "stoke_the_heart")
    retriggered = refused.execute(Sustain(effect.effect_id))
    assert retriggered.status is ResultStatus.PAUSED
    assert retriggered.inspection.choice is not None
    assert retriggered.inspection.choice.kind == "witch_restored_spirit_timing"


def test_forbidding_ward_pair_ac_sustain_cap_and_save_round_trip(
    tmp_path: Path,
) -> None:
    game = _start(rolls=(20, 8, 7, 10, 1, 1))
    rejected_before = deepcopy(game._state)
    rejected = game.execute(Cast(
        "forbidding_ward", target_ids=("witch", "enemy"),
    ))
    assert rejected.status is ResultStatus.REJECTED
    assert game._state == rejected_before

    cast = game.execute(Cast(
        "forbidding_ward", target_ids=("ally", "enemy"),
    ))
    assert cast.status is ResultStatus.COMPLETED
    assert cast.inspection.choice is None
    effect = next(
        item for item in game._state.active_effects
        if item.kind == "forbidding_ward"
    )
    assert effect.target_actor_id == "ally"
    assert effect.selected_enemy_actor_id == "enemy"
    assert effect.value == 1
    assert (
        effect.expires_at_source_start,
        effect.expires_at_world_time,
        effect.sustain_limit_source_start,
        effect.sustain_limit_world_time,
        effect.sustain_expires_at_source_end,
    ) == (11, 60, 11, 60, 2)
    game._state.creatures["enemy"].position = Position(3, 2)

    path = tmp_path / "forbidding-ward.json"
    game.save(path)
    game = Encounter.load(path)
    effect = next(item for item in game._state.active_effects if item.kind == "forbidding_ward")

    assert game.execute(EndTurn()).status is ResultStatus.COMPLETED
    assert game.inspect().turn_actor_id == "ally"
    assert game.execute(EndTurn()).status is ResultStatus.COMPLETED
    assert game.inspect().turn_actor_id == "enemy"
    attack = game.execute(Strike("ally", "club"))
    assert attack.status is ResultStatus.COMPLETED
    check = next(event.check for event in attack.events if event.kind == "strike")
    assert check is not None and check.dc == 16

    assert game.execute(EndTurn()).status is ResultStatus.COMPLETED
    assert game.inspect().turn_actor_id == "witch"
    sustained = game.execute(Sustain(effect.effect_id))
    assert sustained.status is ResultStatus.COMPLETED
    assert sustained.inspection.choice is None
    effect = next(item for item in game._state.active_effects if item.kind == "forbidding_ward")
    assert effect.sustain_expires_at_source_end == 3
    assert (
        effect.expires_at_source_start,
        effect.expires_at_world_time,
        effect.sustain_limit_source_start,
        effect.sustain_limit_world_time,
    ) == (11, 60, 11, 60)


def test_saved_failed_command_flee_uses_its_first_action_to_escape_expediently(
    tmp_path: Path,
) -> None:
    game = _start(rolls=(20, 8, 7, 8, 1, 1))
    game._state.creatures["ally"].position = Position(0, 0)
    game._state.creatures["enemy"].position = Position(3, 2)

    cast = game.execute(Cast("command", target_id="enemy", spell_mode="flee"))
    assert cast.status is ResultStatus.COMPLETED
    effect = next(item for item in game._state.condition_effects if item.kind == "commanded")
    assert effect.value == 1 and effect.command_mode == "flee"

    path = tmp_path / "command-flee.json"
    game.save(path)
    game = Encounter.load(path)
    effect = next(item for item in game._state.condition_effects if item.kind == "commanded")
    assert effect.value == 1 and effect.command_mode == "flee"

    assert game.execute(EndTurn()).status is ResultStatus.COMPLETED
    assert game.execute(EndTurn()).status is ResultStatus.COMPLETED
    enemy = game._state.creatures["enemy"]
    assert game.inspect().turn_actor_id == "enemy"
    assert enemy.actions_remaining == 2
    assert enemy.position == Position(6, 2)


def test_failed_command_locks_then_restores_a_targets_reaction_after_obedience(
    monkeypatch,
) -> None:
    setup = get_setup("faiths_flamekeeper_first_play")
    reaction_setup = replace(
        setup,
        setup_id="witch-command-reaction-review",
        placements=tuple(
            replace(placement, definition_id="fighter_m_level_1")
            if placement.actor_id == "enemy" else placement
            for placement in setup.placements
        ),
    )
    monkeypatch.setattr(
        content,
        "_STAGED_SETUPS",
        content._STAGED_SETUPS | {reaction_setup.setup_id: reaction_setup},
    )
    game = Encounter.start(reaction_setup, rolls=(20, 8, 7, 8, 1, 1))
    _settle(game)

    cast = game.execute(Cast("command", target_id="enemy", spell_mode="stand"))
    if cast.status is ResultStatus.PAUSED:
        choice = game.inspect().choice
        assert choice is not None and choice.kind == "counter_performance_save_choice"
        cast = game.execute(Choose(choice.choice_id, "keep", choice.owner_actor_id))
    assert cast.status is ResultStatus.COMPLETED
    enemy = game._state.creatures["enemy"]
    effect = next(item for item in game._state.condition_effects if item.kind == "commanded")
    assert effect.value == 1 and not enemy.reaction_available

    assert game.execute(EndTurn()).status is ResultStatus.COMPLETED
    enemy = game._state.creatures["enemy"]
    assert game.inspect().turn_actor_id == "enemy"
    assert enemy.actions_remaining == 2
    assert enemy.reaction_available
    assert not any(item.kind == "commanded" for item in game._state.condition_effects)


def test_critical_command_approach_uses_all_actions_to_reach_the_caster() -> None:
    game = _start()
    game._state.creatures["ally"].position = Position(0, 0)

    cast = game.execute(Cast("command", target_id="enemy", spell_mode="approach"))
    assert cast.status is ResultStatus.COMPLETED
    effect = next(item for item in game._state.condition_effects if item.kind == "commanded")
    assert effect.value == 3

    assert game.execute(EndTurn()).status is ResultStatus.COMPLETED
    assert game.execute(EndTurn()).status is ResultStatus.COMPLETED
    enemy = game._state.creatures["enemy"]
    assert game.inspect().turn_actor_id == "enemy"
    assert enemy.actions_remaining == 0
    assert enemy.position == Position(2, 2)


def test_failed_command_flee_routes_around_an_occupied_direct_square() -> None:
    game = _start(rolls=(20, 8, 7, 8, 1, 1))
    game._state.creatures["enemy"].position = Position(3, 2)
    game._state.creatures["ally"].position = Position(4, 2)

    cast = game.execute(Cast("command", target_id="enemy", spell_mode="flee"))
    assert cast.status is ResultStatus.COMPLETED
    assert game.execute(EndTurn()).status is ResultStatus.COMPLETED
    assert game.execute(EndTurn()).status is ResultStatus.COMPLETED
    enemy = game._state.creatures["enemy"]
    assert game.inspect().turn_actor_id == "enemy"
    assert enemy.actions_remaining == 2
    assert enemy.position.x > 3


def test_failed_command_stand_in_place_halts_without_clearing_prone() -> None:
    game = _start(rolls=(20, 8, 7, 8, 1, 1))
    enemy = game._state.creatures["enemy"]
    enemy.prone = True
    initial_position = enemy.position

    cast = game.execute(Cast("command", target_id="enemy", spell_mode="stand"))
    assert cast.status is ResultStatus.COMPLETED
    effect = next(item for item in game._state.condition_effects if item.kind == "commanded")
    assert effect.value == 1

    assert game.execute(EndTurn()).status is ResultStatus.COMPLETED
    assert game.execute(EndTurn()).status is ResultStatus.COMPLETED
    enemy = game._state.creatures["enemy"]
    assert game.inspect().turn_actor_id == "enemy"
    assert enemy.actions_remaining == 2
    assert enemy.position == initial_position
    assert enemy.prone


def test_item_sigil_follows_the_item_and_survives_a_week(
    tmp_path: Path,
) -> None:
    game = _start(rolls=(20, 8, 7, 20, 1, 1))
    cantrip = next(slot for slot in game._state.creatures["witch"].prepared_slots if slot.cantrip)
    cantrip.spell_id = "sigil"
    item_id = game._state.creatures["witch"].held_items[0]
    game._state.creatures["enemy"].position = Position(2, 1)
    game._state.creatures["enemy"].hp = 1

    assert game.execute(Cast("sigil", item_id=item_id)).status is ResultStatus.COMPLETED
    assert game.execute(Release(item_id)).status is ResultStatus.COMPLETED
    path = tmp_path / "transferred-item-sigil.json"
    game.save(path)
    game = Encounter.load(path)

    assert game.execute(EndTurn()).status is ResultStatus.COMPLETED
    assert game.inspect().turn_actor_id == "ally"
    assert game.execute(Interact("retrieve", item_id)).status is ResultStatus.COMPLETED
    effect = next(item for item in game._state.active_item_effects if item.kind == "sigil")
    ally_actions = game._state.creatures["ally"].actions_remaining
    assert game.execute(Interact("toggle_sigil", effect.effect_id)).status is ResultStatus.REJECTED
    assert game._state.creatures["ally"].actions_remaining == ally_actions
    assert game.execute(EndTurn()).status is ResultStatus.COMPLETED
    assert game.execute(EndTurn()).status is ResultStatus.COMPLETED
    assert game.inspect().turn_actor_id == "witch"
    assert game.execute(Interact("toggle_sigil", effect.effect_id)).status is ResultStatus.COMPLETED
    assert not next(
        item for item in game._state.active_item_effects if item.effect_id == effect.effect_id
    ).visible
    assert game.execute(Strike("enemy", "fist", nonlethal=False)).status is ResultStatus.PAUSED
    _settle(game)
    assert not game._state.in_progress
    enemy = game._state.creatures["enemy"]
    assert enemy.defeated and enemy.dead and not enemy.unconscious and enemy.dying == 0

    rested = game.record_rested(
        ("witch", "ally"), day_number=8, elapsed_seconds=604_801,
    )
    assert rested.status is ResultStatus.COMPLETED
    effect = next(item for item in game._state.active_item_effects if item.kind == "sigil")
    assert effect.item_id == item_id and not effect.visible
    after_week = tmp_path / "item-sigil-after-week.json"
    game.save(after_week)
    loaded = Encounter.load(after_week)
    assert any(
        item.kind == "sigil" and item.item_id == item_id
        for item in loaded._state.active_item_effects
    )
    before_scrub = loaded._state.world_time_seconds
    scrubbed = loaded.scrub_sigil("witch", effect.effect_id)
    assert scrubbed.status is ResultStatus.COMPLETED
    assert loaded._state.world_time_seconds == before_scrub + 300
    assert not any(
        item.effect_id == effect.effect_id for item in loaded._state.active_item_effects
    )


def test_sigil_can_start_invisible_and_each_caster_keeps_their_unique_mark() -> None:
    game = _start()
    for actor_id in ("witch", "ally"):
        cantrip = next(
            slot for slot in game._state.creatures[actor_id].prepared_slots if slot.cantrip
        )
        cantrip.spell_id = "sigil"
    item_id = game._state.creatures["witch"].held_items[0]

    first = game.execute(Cast(
        "sigil", item_id=item_id, spell_mode="invisible",
    ))
    assert first.status is ResultStatus.COMPLETED
    first_effect = next(item for item in game._state.active_item_effects if item.kind == "sigil")
    assert not first_effect.visible

    assert game.execute(EndTurn()).status is ResultStatus.COMPLETED
    second = game.execute(Cast(
        "sigil", item_id=item_id, spell_mode="visible",
    ))
    assert second.status is ResultStatus.COMPLETED
    marks = [item for item in game._state.active_item_effects if item.kind == "sigil"]
    assert {(item.source_actor_id, item.visible) for item in marks} == {
        ("witch", False), ("ally", True),
    }


def test_creature_sigil_fades_after_one_week_of_public_elapsed_time(
    tmp_path: Path,
) -> None:
    game = _start(rolls=(20, 8, 7, 20, 1, 1))
    cantrip = next(slot for slot in game._state.creatures["witch"].prepared_slots if slot.cantrip)
    cantrip.spell_id = "sigil"
    game._state.creatures["enemy"].position = Position(1, 1)
    game._state.creatures["enemy"].hp = 1

    assert game.execute(Cast(
        "sigil", target_id="ally", spell_mode="invisible",
    )).status is ResultStatus.COMPLETED
    effect = next(item for item in game._state.active_effects if item.kind == "sigil")
    assert effect.value == 2
    assert game.execute(Strike(
        "enemy", "fist", nonlethal=False,
    )).status is ResultStatus.PAUSED
    _settle(game)
    assert game._state.creatures["enemy"].dead

    assert game.record_rested(
        ("witch", "ally"), day_number=8, elapsed_seconds=604_800,
    ).status is ResultStatus.COMPLETED
    assert not any(item.kind == "sigil" for item in game._state.active_effects)
    path = tmp_path / "expired-creature-sigil.json"
    game.save(path)
    assert not any(
        item.kind == "sigil" for item in Encounter.load(path)._state.active_effects
    )


def test_detect_magic_reports_only_unknown_magic_inside_its_emanation(
    monkeypatch,
    tmp_path: Path,
) -> None:
    base = get_setup("faiths_flamekeeper_first_play")
    setups = {}
    for case, enemy_position in (("near", Position(5, 2)), ("far", Position(10, 2))):
        setup = replace(
            base,
            setup_id=f"witch-detect-magic-{case}-review",
            width=12,
            placements=tuple(
                replace(
                    placement,
                    definition_id="faiths_flamekeeper_witch_level_1",
                    position=enemy_position,
                )
                if placement.actor_id == "enemy" else placement
                for placement in base.placements
            ),
        )
        setups[setup.setup_id] = setup
    monkeypatch.setattr(content, "_STAGED_SETUPS", content._STAGED_SETUPS | setups)

    for case, expected_kind in (("near", "detect_magic_present"), ("far", "detect_magic_absent")):
        game = Encounter.start(setups[f"witch-detect-magic-{case}-review"], rolls=(20, 8, 7, 1, 1))
        _settle(game)
        witch_cantrip = next(
            slot for slot in game._state.creatures["witch"].prepared_slots if slot.cantrip
        )
        enemy_cantrip = next(
            slot for slot in game._state.creatures["enemy"].prepared_slots if slot.cantrip
        )
        witch_cantrip.spell_id = "detect_magic"
        enemy_cantrip.spell_id = "sigil"

        assert game.execute(EndTurn()).status is ResultStatus.COMPLETED
        assert game.execute(EndTurn()).status is ResultStatus.COMPLETED
        assert game.inspect().turn_actor_id == "enemy"
        assert game.execute(Cast("sigil", target_id="enemy")).status is ResultStatus.COMPLETED
        assert game.execute(EndTurn()).status is ResultStatus.COMPLETED
        cast = game.execute(Cast("detect_magic"))
        assert cast.status is ResultStatus.PAUSED

        path = tmp_path / f"detect-magic-{case}.json"
        game.save(path)
        game = Encounter.load(path)
        choice = game.inspect().choice
        assert choice is not None and choice.kind == "detect_magic_known"
        result = game.choose(choice.choice_id, "ignore_known", choice.owner_actor_id)
        assert result.status is ResultStatus.COMPLETED
        assert any(event.kind == expected_kind for event in result.events)
        event = next(event for event in result.events if event.kind == expected_kind)
        assert event.target_id is None and "Enemy" not in event.text


def test_detect_magic_registers_an_unknown_ongoing_shield_spell(monkeypatch) -> None:
    base = get_setup("faiths_flamekeeper_first_play")
    setup = replace(
        base,
        setup_id="witch-detect-magic-shield-review",
        placements=tuple(
            replace(placement, definition_id="faiths_flamekeeper_witch_level_1")
            if placement.actor_id == "enemy" else placement
            for placement in base.placements
        ),
    )
    monkeypatch.setattr(
        content, "_STAGED_SETUPS", content._STAGED_SETUPS | {setup.setup_id: setup},
    )
    game = Encounter.start(setup, rolls=(20, 8, 7, 1, 1))
    _settle(game)
    witch_cantrip = next(
        slot for slot in game._state.creatures["witch"].prepared_slots if slot.cantrip
    )
    enemy_cantrip = next(
        slot for slot in game._state.creatures["enemy"].prepared_slots if slot.cantrip
    )
    witch_cantrip.spell_id = "detect_magic"
    enemy_cantrip.spell_id = "shield"

    assert game.execute(EndTurn()).status is ResultStatus.COMPLETED
    assert game.execute(EndTurn()).status is ResultStatus.COMPLETED
    assert game.inspect().turn_actor_id == "enemy"
    assert game.execute(Cast("shield")).status is ResultStatus.COMPLETED
    assert game.execute(EndTurn()).status is ResultStatus.COMPLETED
    cast = game.execute(Cast("detect_magic"))
    assert cast.status is ResultStatus.PAUSED
    choice = game.inspect().choice
    assert choice is not None and choice.kind == "detect_magic_known"
    result = game.choose(choice.choice_id, "ignore_known", choice.owner_actor_id)
    assert result.status is ResultStatus.COMPLETED
    assert any(event.kind == "detect_magic_present" for event in result.events)


def test_bounded_terminal_collects_invisible_item_sigil_and_targetless_detection() -> None:
    game = _start()
    cantrips = [
        slot for slot in game._state.creatures["witch"].prepared_slots if slot.cantrip
    ]
    cantrips[0].spell_id = "sigil"
    cantrips[1].spell_id = "detect_magic"
    spells = game.options().spells
    sigil = next(spell for spell in spells if spell.spell_id == "sigil")
    detect = next(spell for spell in spells if spell.spell_id == "detect_magic")
    item_id = game._state.creatures["witch"].held_items[0]

    sigil_answers = iter(("1", "1", "2", "2", "1"))
    sigil_transcript = BoundedTranscript(max_lines=40, max_chars=8_000)
    sigil_input = BoundedInput(
        lambda: next(sigil_answers), max_calls=5,
        describe=lambda: sigil_transcript[-1] if sigil_transcript else "",
    )
    selected = _choose_cast_inputs(
        (sigil,), game.inspect(), sigil_input, sigil_transcript.append,
    )
    assert selected == (
        "sigil", None, 2, None, None,
        {"spell_mode": "invisible", "item_id": item_id},
    )
    rendered = "\n".join(sigil_transcript)
    assert "Sigil target:" in rendered
    assert "Sigil visibility:" in rendered
    assert "Sigil item number:" in rendered
    assert sigil_input.calls == 5

    detect_answers = iter(("1", "1"))
    detect_transcript = BoundedTranscript(max_lines=20, max_chars=4_000)
    detect_input = BoundedInput(
        lambda: next(detect_answers), max_calls=2,
        describe=lambda: detect_transcript[-1] if detect_transcript else "",
    )
    selected = _choose_cast_inputs(
        (detect,), game.inspect(), detect_input, detect_transcript.append,
    )
    assert selected == ("detect_magic", None, 2, None, None)
    assert "Target number:" not in "\n".join(detect_transcript)
    assert detect_input.calls == 2


def test_continuous_witch_reprepares_saves_and_terminal_casts_next_scene(
    tmp_path: Path,
) -> None:
    game = _start(rolls=(20, 8, 7, 20, 1, 1, *([20] * 16)))
    puppet = game.execute(PatronsPuppet(
        "fox", (FamiliarStride((Position(0, 2),)),),
    ))
    assert puppet.status is ResultStatus.PAUSED
    _settle(game)
    assert game._state.creatures["witch"].focus_points == 0

    enemy = game._state.creatures["enemy"]
    enemy.hp = 1
    enemy.position = Position(1, 1)
    assert game.execute(Strike(
        "enemy", "fist", nonlethal=False,
    )).status is ResultStatus.PAUSED
    _settle(game)
    assert game._state.creatures["enemy"].dead and not game.inspect().in_progress
    assert game.refocus("witch").status is ResultStatus.COMPLETED
    assert game._state.creatures["witch"].focus_points == 1

    preparations: dict[str, dict[str, str]] = {}
    for actor_id in ("witch", "ally"):
        actor = game._state.creatures[actor_id]
        chosen = {slot.slot_id: slot.spell_id for slot in actor.prepared_slots}
        if actor_id == "witch":
            cantrips = [slot for slot in actor.prepared_slots if slot.cantrip]
            chosen[cantrips[0].slot_id] = "sigil"
            chosen[cantrips[1].slot_id] = "detect_magic"
        preparations[actor_id] = chosen
    assert game.record_rested(
        ("witch", "ally"), day_number=2, elapsed_seconds=28_800,
    ).status is ResultStatus.COMPLETED
    assert game.daily_prepare(
        ("witch", "ally"), preparations,
    ).status is ResultStatus.COMPLETED

    finished_path = tmp_path / "witch-finished-prepared.json"
    game.save(finished_path)
    game = Encounter.load(finished_path)
    next_setup = get_setup("faiths_flamekeeper_next")
    assert game.next_encounter(next_setup).status is ResultStatus.PAUSED
    _settle(game)
    while game.inspect().turn_actor_id != "witch":
        assert game.execute(EndTurn()).status is ResultStatus.COMPLETED
    assert game._state.creatures["witch"].focus_points == 1
    assert "fox" not in game._state.initiative_order
    assert game._state.creatures["fox"].initiative == 0
    assert {
        slot.spell_id for slot in game._state.creatures["witch"].prepared_slots if slot.cantrip
    } >= {"sigil", "detect_magic"}

    terminal_path = tmp_path / "witch-next-scene.json"
    game.save(terminal_path)
    transcript = BoundedTranscript(max_lines=300, max_chars=60_000)
    state = {"menu": "", "prompt": "", "loaded": False, "cast": False}

    def output(line: str) -> None:
        transcript.append(line)
        if line.startswith("1. "):
            state["menu"] = line
        if line.startswith("Loaded encounter from "):
            state["loaded"] = True
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
            return choose("Resolve this choice") if state["loaded"] else choose("Load")
        if prompt.startswith("Load file ["):
            return ""
        if prompt == "Choice:":
            if not state["cast"]:
                state["cast"] = True
                return choose("Cast")
            return choose("Quit")
        if prompt == "Spell number:":
            return choose("Detect Magic", prefix=True)
        if prompt == "Casting mode:":
            return choose("2 actions")
        if prompt == "Choice option number:":
            return choose("Ignore magic already known to the caster")
        raise AssertionError(f"unexpected terminal prompt: {prompt!r}")

    bounded = BoundedInput(
        scripted_input, max_calls=15,
        describe=lambda: transcript[-1] if transcript else "",
    )
    assert run_terminal(
        setup=next_setup,
        rolls=(20, 8, 7, 1, 1, 1),
        save_path=terminal_path,
        input_fn=bounded,
        output_fn=output,
    ) == 0
    rendered = "\n".join(transcript)
    assert f"Loaded encounter from {terminal_path}." in rendered
    assert "Detect Magic registers no magic." in rendered
    assert bounded.calls < 15


def test_familiar_knockout_saved_witch_turn_recovery_and_heal_are_public(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    game = _knock_out_review_fox(monkeypatch, recovery_roll=20)
    assert "fox" not in game._state.initiative_order
    assert game._state.creatures["fox"].hero_points == 0

    before_check = tmp_path / "fox-before-recovery.json"
    game.save(before_check)
    game = Encounter.load(before_check)
    choice = game.inspect().choice
    assert choice is not None and choice.kind == "recovery_start_heroic"
    rolled = game.choose(choice.choice_id, "recovery_check", choice.owner_actor_id)
    assert rolled.status is ResultStatus.PAUSED
    reroll = rolled.inspection.choice
    assert reroll is not None and reroll.kind == "recovery_hero_reroll"
    assert reroll.owner_actor_id == "witch"

    after_roll = tmp_path / "fox-recovery-roll.json"
    game.save(after_roll)
    game = Encounter.load(after_roll)
    reroll = game.inspect().choice
    assert reroll is not None
    recovered = game.choose(reroll.choice_id, "keep", reroll.owner_actor_id)
    assert recovered.status is ResultStatus.COMPLETED
    fox = game._state.creatures["fox"]
    assert (fox.hp, fox.dying, fox.wounded, fox.unconscious, fox.dead) == (
        0, 0, 1, True, False,
    )
    assert game.inspect().turn_actor_id == "witch"
    assert (fox.actions_remaining, fox.reaction_available) == (0, False)

    heal = game.execute(Cast("heal", "fox", actions=2, slot_id="witch_heal"))
    assert heal.status is ResultStatus.PAUSED
    willingness = heal.inspection.choice
    assert willingness is not None and willingness.kind == "spell_willingness"
    healed = game.choose(
        willingness.choice_id, "willing", willingness.owner_actor_id,
    )
    assert healed.status is ResultStatus.COMPLETED
    fox = game._state.creatures["fox"]
    assert (fox.hp, fox.dying, fox.wounded, fox.unconscious, fox.dead) == (
        7, 0, 1, False, False,
    )
    assert (fox.actions_remaining, fox.reaction_available) == (0, False)
    assert "fox" not in game._state.initiative_order
    healed_path = tmp_path / "fox-healed.json"
    game.save(healed_path)
    assert Encounter.load(healed_path).inspect() == game.inspect()


def test_witch_can_fund_familiars_saved_heroic_recovery_at_knockout(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    setup = _lifecycle_setup(monkeypatch)
    game = Encounter.start(setup, rolls=(1, 2, 20, 20, 2))
    _settle(game)
    paused = game.execute(Strike("fox", "club"))
    assert paused.status is ResultStatus.PAUSED
    choice = paused.inspection.choice
    assert choice is not None and choice.kind == "heroic_recovery_damage"
    assert choice.owner_actor_id == "witch"

    path = tmp_path / "fox-knockout-heroic.json"
    game.save(path)
    game = Encounter.load(path)
    choice = game.inspect().choice
    assert choice is not None
    stabilized = game.choose(
        choice.choice_id, "heroic_recovery", choice.owner_actor_id,
    )
    assert stabilized.status is ResultStatus.COMPLETED
    witch = game._state.creatures["witch"]
    fox = game._state.creatures["fox"]
    assert witch.hero_points == 0 and fox.hero_points == 0
    assert (fox.hp, fox.dying, fox.wounded, fox.unconscious, fox.dead) == (
        0, 0, 0, True, False,
    )
    assert (fox.actions_remaining, fox.reaction_available) == (0, False)
    stable_path = tmp_path / "fox-knockout-heroic-resolved.json"
    game.save(stable_path)
    assert Encounter.load(stable_path).inspect() == game.inspect()


def test_dead_familiar_preserves_preparations_blocks_refocus_and_is_replaced(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    game = _knock_out_review_fox(
        monkeypatch, recovery_roll=1, tail=(20, 1),
    )
    prepared_before = tuple(game._state.creatures["witch"].prepared_slots)
    choice = game.inspect().choice
    assert choice is not None
    assert game.choose(
        choice.choice_id, "recovery_check", choice.owner_actor_id,
    ).status is ResultStatus.PAUSED
    reroll = game.inspect().choice
    assert reroll is not None and reroll.kind == "recovery_hero_reroll"

    dying_path = tmp_path / "fox-critical-recovery.json"
    game.save(dying_path)
    game = Encounter.load(dying_path)
    reroll = game.inspect().choice
    assert reroll is not None
    resolved = game.choose(reroll.choice_id, "keep", reroll.owner_actor_id)
    assert resolved.status is ResultStatus.COMPLETED
    fox = game._state.creatures["fox"]
    assert (fox.hp, fox.dying, fox.unconscious, fox.dead) == (0, 0, False, True)
    assert tuple(game._state.creatures["witch"].prepared_slots) == prepared_before

    final = game.execute(Strike("enemy", "fist", nonlethal=False))
    if final.inspection.choice is not None:
        choice = final.inspection.choice
        assert choice.kind == "attack_hero_reroll"
        final = game.choose(choice.choice_id, "keep", choice.owner_actor_id)
    assert final.status is ResultStatus.COMPLETED
    assert not game.inspect().in_progress and game.inspect().winner_team == "blue"

    before_refocus = deepcopy(game._state)
    dice_before = game._dice.to_data()
    refused = game.refocus("witch")
    assert refused.status is ResultStatus.REJECTED
    assert "familiar" in refused.message.lower()
    assert game._state == before_refocus and game._dice.to_data() == dice_before

    assert game.record_rested(
        ("witch",), day_number=2, elapsed_seconds=28_800,
    ).status is ResultStatus.COMPLETED
    witch = game._state.creatures["witch"]
    cantrips = [slot for slot in witch.prepared_slots if slot.cantrip]
    ranked = [slot for slot in witch.prepared_slots if not slot.cantrip]
    known_cantrips = (
        "void_warp", "stabilize", "vitality_lash", "sigil", "detect_magic",
    )
    known_ranked = ("fear", "runic_weapon")
    choices = {
        **{slot.slot_id: spell for slot, spell in zip(cantrips, known_cantrips)},
        **{slot.slot_id: spell for slot, spell in zip(ranked, known_ranked)},
    }
    replaced = game.daily_prepare(("witch",), {"witch": choices})
    assert replaced.status is ResultStatus.COMPLETED
    fox = game._state.creatures["fox"]
    assert (fox.hp, fox.dying, fox.wounded, fox.unconscious, fox.dead) == (
        7, 0, 0, False, False,
    )
    assert fox.definition_id == "faiths_flamekeeper_fox"
    assert (fox.actions_remaining, fox.reaction_available) == (0, False)
    assert "fox" not in game._state.initiative_order
    witch = game._state.creatures["witch"]
    assert tuple(slot.spell_id for slot in witch.prepared_slots) == (
        *known_cantrips, *known_ranked,
    )

    replacement_path = tmp_path / "fox-replaced.json"
    game.save(replacement_path)
    loaded = Encounter.load(replacement_path)
    assert loaded.inspect() == game.inspect()
    assert tuple(loaded._state.creatures["witch"].prepared_slots) == tuple(
        game._state.creatures["witch"].prepared_slots
    )


def test_uncommanded_familiar_persistent_damage_uses_saved_witch_turn_boundary(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    setup = EncounterSetup(
        setup_id="review_flamekeeper_familiar_persistent",
        name="Flamekeeper Familiar Persistent Review",
        width=5,
        height=4,
        placements=(
            CreaturePlacement(
                "witch", "faiths_flamekeeper_witch_level_1",
                "Flamekeeper Witch", "blue", Position(1, 2),
            ),
            CreaturePlacement(
                "fox", "faiths_flamekeeper_fox",
                "Flamekeeper Fox", "blue", Position(1, 2),
            ),
            CreaturePlacement(
                "enemy_wizard", "wizard_battle_magic_level_1_staged",
                "Enemy Wizard", "red", Position(3, 2),
            ),
        ),
    )
    monkeypatch.setattr(
        content,
        "_STAGED_SETUPS",
        MappingProxyType({**content._STAGED_SETUPS, setup.setup_id: setup}),
    )
    game = Encounter.start(
        setup,
        # Initiatives; critical ranged Ignition; 2d4 initial; persistent d4
        # and failed DC 15 flat recovery.
        rolls=(1, 20, 20, 1, 1, 2, 1),
    )
    _settle(game)
    assert game.inspect().turn_actor_id == "enemy_wizard"
    cast = game.execute(Cast("ignition", "fox", spell_mode="ranged"))
    assert cast.status is ResultStatus.PAUSED
    choice = cast.inspection.choice
    assert choice is not None and choice.kind == "spell_attack_hero_reroll"
    assert game.choose(
        choice.choice_id, "keep", choice.owner_actor_id,
    ).status is ResultStatus.COMPLETED
    assert game._state.creatures["fox"].hp == 3
    assert any(effect.target_actor_id == "fox" for effect in game._state.persistent_effects)
    reached_witch = game.execute(EndTurn())
    assert reached_witch.status is ResultStatus.PAUSED
    recovery = reached_witch.inspection.choice
    assert recovery is not None and recovery.kind == "persistent_recovery"
    assert recovery.owner_actor_id == "witch"
    assert game._state.pending_choice is not None
    assert game._state.pending_choice.target_id == "fox"

    boundary_path = tmp_path / "fox-persistent-witch-boundary.json"
    game.save(boundary_path)
    game = Encounter.load(boundary_path)
    recovery = game.inspect().choice
    assert recovery is not None
    kept = game.choose(recovery.choice_id, "keep", recovery.owner_actor_id)
    assert kept.status is ResultStatus.COMPLETED
    assert game.inspect().turn_actor_id == "witch"
    fox = game._state.creatures["fox"]
    assert fox.hp == 1
    assert (fox.actions_remaining, fox.reaction_available) == (0, False)
    assert "fox" not in game._state.initiative_order
    assert any(effect.target_actor_id == "fox" for effect in game._state.persistent_effects)
    assert game.execute(EndTurn()).status is ResultStatus.COMPLETED
    assert game._state.creatures["fox"].hp == 1


def test_persistent_knockout_heroic_recovery_resumes_the_witch_turn(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    setup = EncounterSetup(
        setup_id="review_flamekeeper_familiar_persistent_knockout",
        name="Flamekeeper Familiar Persistent Knockout Review",
        width=5,
        height=4,
        placements=(
            CreaturePlacement(
                "witch", "faiths_flamekeeper_witch_level_1",
                "Flamekeeper Witch", "blue", Position(1, 2),
            ),
            CreaturePlacement(
                "fox", "faiths_flamekeeper_fox",
                "Flamekeeper Fox", "blue", Position(1, 2),
            ),
            CreaturePlacement(
                "enemy_wizard", "wizard_battle_magic_level_1_staged",
                "Enemy Wizard", "red", Position(3, 2),
            ),
        ),
    )
    monkeypatch.setattr(
        content,
        "_STAGED_SETUPS",
        MappingProxyType({**content._STAGED_SETUPS, setup.setup_id: setup}),
    )
    game = Encounter.start(
        setup,
        # Initiatives; critical Ignition; 2d4 initial leaves 3 HP; persistent
        # d4 then knocks the fox out at the Witch's paired boundary.
        rolls=(1, 20, 20, 1, 1, 4),
    )
    _settle(game)
    cast = game.execute(Cast("ignition", "fox", spell_mode="ranged"))
    choice = cast.inspection.choice
    assert choice is not None and choice.kind == "spell_attack_hero_reroll"
    assert game.choose(
        choice.choice_id, "keep", choice.owner_actor_id,
    ).status is ResultStatus.COMPLETED
    paused = game.execute(EndTurn())
    assert paused.status is ResultStatus.PAUSED
    choice = paused.inspection.choice
    assert choice is not None and choice.kind == "heroic_recovery_damage"
    assert choice.owner_actor_id == "witch"
    assert game._state.pending_choice is not None
    assert game._state.pending_choice.transition_kind == "familiar_persistent_damage"

    path = tmp_path / "fox-persistent-knockout-heroic.json"
    game.save(path)
    game = Encounter.load(path)
    choice = game.inspect().choice
    assert choice is not None
    resumed = game.choose(
        choice.choice_id, "heroic_recovery", choice.owner_actor_id,
    )
    assert resumed.status is ResultStatus.COMPLETED
    witch = game._state.creatures["witch"]
    fox = game._state.creatures["fox"]
    assert witch.hero_points == 0 and fox.hero_points == 0
    assert (fox.hp, fox.dying, fox.wounded, fox.unconscious, fox.dead) == (
        0, 0, 0, True, False,
    )
    assert game.inspect().turn_actor_id == "witch"
    assert witch.actions_remaining == 3
    assert (fox.actions_remaining, fox.reaction_available) == (0, False)


def test_terminal_refuses_refocus_then_replaces_dead_familiar_during_preparation(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    game = _knock_out_review_fox(
        monkeypatch, recovery_roll=1, tail=(20, 1),
    )
    choice = game.inspect().choice
    assert choice is not None
    assert game.choose(
        choice.choice_id, "recovery_check", choice.owner_actor_id,
    ).status is ResultStatus.PAUSED
    reroll = game.inspect().choice
    assert reroll is not None
    assert game.choose(
        reroll.choice_id, "keep", reroll.owner_actor_id,
    ).status is ResultStatus.COMPLETED
    final = game.execute(Strike("enemy", "fist", nonlethal=False))
    choice = final.inspection.choice
    assert choice is not None and choice.kind == "attack_hero_reroll"
    final = game.choose(choice.choice_id, "keep", choice.owner_actor_id)
    assert final.status is ResultStatus.COMPLETED
    assert not game.inspect().in_progress and game._state.creatures["fox"].dead

    save_path = tmp_path / "terminal-dead-fox.json"
    game.save(save_path)
    setup = get_setup("review_flamekeeper_familiar_lifecycle")
    transcript = BoundedTranscript(max_lines=500, max_chars=80_000)
    state = {"menu": "", "prompt": "", "phase": "initial"}

    def output(line: str) -> None:
        transcript.append(line)
        if line.startswith("1. "):
            state["menu"] = line
        if line.endswith(":") or line.startswith(("Save file [", "Load file [")):
            state["prompt"] = line
        if line.startswith("Loaded encounter from "):
            state["phase"] = "loaded"
        elif "Refocus requires the Witch's living familiar" in line:
            state["phase"] = "refused"
        elif "Recorded externally adjudicated rest eligibility" in line:
            state["phase"] = "rested"
        elif "Daily preparation completed" in line:
            state["phase"] = "prepared"
        elif line.startswith("Saved encounter to "):
            state["phase"] = "saved"

    def choose(label: str, *, prefix: bool = False) -> str:
        for row in state["menu"].splitlines():
            number, text = row.split(". ", 1)
            if text.startswith(label) if prefix else text == label:
                return number
        raise AssertionError(f"missing terminal menu item {label!r}: {state['menu']!r}")

    preparation_by_prompt = {
        "Daily preparation witch_divine_lance spell:": "Void Warp",
        "Daily preparation witch_shield spell:": "Stabilize",
        "Daily preparation witch_guidance spell:": "Vitality Lash",
        "Daily preparation witch_light spell:": "Sigil",
        "Daily preparation witch_forbidding_ward spell:": "Detect Magic",
        "Daily preparation witch_command spell:": "Fear",
        "Daily preparation witch_heal spell:": "Runic Weapon",
    }

    def scripted_input() -> str:
        prompt = state["prompt"]
        phase = state["phase"]
        if prompt == "Choice prompt action:":
            return choose("Load")
        if prompt.startswith("Load file [") or prompt.startswith("Save file ["):
            return ""
        if prompt == "Choice:":
            return choose({
                "loaded": "Refocus (10 minutes)",
                "refused": "Record Rested Eligibility",
                "rested": "Daily Preparation",
                "prepared": "Save",
                "saved": "Quit",
            }[phase])
        if prompt == "Refocus actor number:":
            return choose("Flamekeeper Witch (witch)")
        if prompt == "Actor numbers:":
            return choose("Flamekeeper Witch (witch)")
        if prompt == "Declared preparation day:":
            return "2"
        if prompt == "Externally adjudicated elapsed seconds:":
            return "28800"
        if prompt in preparation_by_prompt:
            return choose(preparation_by_prompt[prompt])
        raise AssertionError(
            f"unexpected terminal prompt {prompt!r} in phase {phase!r}"
        )

    bounded = BoundedInput(
        scripted_input, max_calls=28,
        describe=lambda: "\n".join(transcript[-20:]) if transcript else "",
    )
    assert run_terminal(
        setup=setup,
        rolls=(1, 2, 20),
        save_path=save_path,
        input_fn=bounded,
        output_fn=output,
    ) == 0
    rendered = "\n".join(transcript)
    assert "Refocus requires the Witch's living familiar" in rendered
    assert "replaces the dead familiar during daily preparation" in rendered
    assert f"Saved encounter to {save_path}." in rendered
    assert bounded.calls < 28

    loaded = Encounter.load(save_path)
    fox = loaded._state.creatures["fox"]
    assert (fox.hp, fox.dead, fox.unconscious) == (7, False, False)
    assert tuple(
        slot.spell_id for slot in loaded._state.creatures["witch"].prepared_slots
    ) == (
        "void_warp", "stabilize", "vitality_lash", "sigil", "detect_magic",
        "fear", "runic_weapon",
    )
