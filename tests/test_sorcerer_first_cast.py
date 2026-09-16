"""Focused staged Angelic Sorcerer first-cast checks."""

from __future__ import annotations

import pytest

from pf2e.content import ANGELIC_FIRST_CAST_SETUP, ANGELIC_SORCERER_STAGED
from pf2e.encounter import Encounter
from pf2e.model import Cast, EndTurn, ResultStatus


def _finish_start_choices(game: Encounter) -> None:
    while game.inspect().choice is not None:
        choice = game.inspect().choice
        assert choice is not None
        option = "keep" if any(item.option_id == "keep" for item in choice.options) else choice.options[0].option_id
        result = game.choose(choice.choice_id, option, choice.owner_actor_id)
        assert result.status is ResultStatus.COMPLETED


def _first_cast_game(*, rolls: tuple[int, ...] = (20, 1, 1, 10, 1, 1, 4)) -> Encounter:
    game = Encounter.start(ANGELIC_FIRST_CAST_SETUP, rolls=rolls)
    _finish_start_choices(game)
    assert game.inspect().turn_actor_id == "angelic_sorcerer"
    return game


def _cast_heal_and_choose(game: Encounter, *, blood_recipient: str = "angelic_sorcerer"):
    result = game.execute(Cast("heal", "sorcerer_ally", actions=2))
    assert result.status is ResultStatus.PAUSED
    blood = result.inspection.choice
    assert blood is not None and blood.kind == "spell_blood_magic_recipient"
    result = game.choose(blood.choice_id, blood_recipient, blood.owner_actor_id)
    assert result.status is ResultStatus.PAUSED
    willingness = result.inspection.choice
    assert willingness is not None and willingness.kind == "spell_willingness"
    result = game.choose(willingness.choice_id, "willing", willingness.owner_actor_id)
    assert result.status is ResultStatus.COMPLETED
    return result


def test_staged_sheet_exposes_legal_repertoire_and_rank_pool() -> None:
    assert ANGELIC_SORCERER_STAGED.spell_attack == 7
    assert ANGELIC_SORCERER_STAGED.spell_dc == 17
    assert ANGELIC_SORCERER_STAGED.attacks[0].modifier == 5
    assert ANGELIC_SORCERER_STAGED.spell_tradition == "divine"
    assert {entry.spell_id for entry in ANGELIC_SORCERER_STAGED.spontaneous_spells} == {
        "light", "divine_lance", "void_warp", "guidance", "stabilize",
        "heal", "fear", "runic_weapon",
    }
    assert ANGELIC_SORCERER_STAGED.spontaneous_slots[0].capacity == 3
    assert "Natural Skill" in ANGELIC_SORCERER_STAGED.feats
    assert "Assurance (Athletics)" in ANGELIC_SORCERER_STAGED.feats
    assert len(ANGELIC_SORCERER_STAGED.skills) == 9
    assert "society" not in {skill for skill, _rank, _modifier in ANGELIC_SORCERER_STAGED.skills}


def test_public_cantrip_is_repeatable_and_slot_heal_spends_once_with_benefits() -> None:
    game = _first_cast_game()
    before = game.inspect()
    before_dice = game._dice._index
    rejected = game.execute(Cast("divine_lance", "sorcerer_dog", slot_id="angelic_rank1"))
    assert rejected.status is ResultStatus.REJECTED
    assert "Cantrips do not expend" in rejected.message
    assert game.inspect() == before
    assert game._dice._index == before_dice

    result = game.execute(Cast("divine_lance", "sorcerer_dog"))
    assert result.status is ResultStatus.COMPLETED
    assert any(event.kind == "spell_attack" for event in result.events)
    assert game._state.creatures["sorcerer_dog"].hp == 6
    assert game._state.creatures["angelic_sorcerer"].spontaneous_slots[0].remaining == 3

    # A damaged willing ally makes the +1 Potency healing observable.
    game.execute(EndTurn())
    game.execute(EndTurn())
    game.execute(EndTurn())
    assert game.inspect().turn_actor_id == "angelic_sorcerer"
    game._state.creatures["sorcerer_ally"].hp = 5
    result = _cast_heal_and_choose(game)
    assert any(event.kind == "blood_magic_applied" for event in result.events)
    healing = next(event for event in result.events if event.kind == "healing")
    assert "+ Sorcerous Potency 1 status" in healing.text
    assert game._state.creatures["sorcerer_ally"].hp == 18  # 5 + (1d8=4 + 8 + Potency 1)
    assert game._state.creatures["angelic_sorcerer"].spontaneous_slots[0].remaining == 2
    assert len([effect for effect in game._state.active_effects if effect.kind == "blood_magic"]) == 1


def test_blood_magic_save_bonus_uses_shared_fortitude_reflex_will_path_and_expires() -> None:
    game = _first_cast_game(rolls=(20, 1, 1, 4))
    _cast_heal_and_choose(game, blood_recipient="sorcerer_ally")
    target = game._state.creatures["sorcerer_ally"]
    continuation = game._state.active_effects
    assert any(effect.target_actor_id == target.actor_id for effect in continuation)
    from pf2e.model import ActionContinuation

    saved_cast = ActionContinuation(kind="cast", actor_id="angelic_sorcerer", spell_id="heal", spell_actions=2)
    for statistic in ("fortitude", "reflex", "will"):
        modifiers = game._spell_save_modifier_breakdown(
            game._state, target, saved_cast, "void_warp", statistic
        )
        assert any(
            modifier.amount == 1
            and modifier.modifier_type == "status"
            and "Angelic Blood Magic" in modifier.source
            for modifier in modifiers
        )
    assert {
        statistic: game._skill_dc(game._state, target.actor_id, statistic)
        for statistic in ("fortitude", "reflex", "will")
    } == {"fortitude": 19, "reflex": 17, "will": 15}

    # The effect lasts through the current turn and disappears at this caster's next start.
    game.execute(EndTurn())
    game.execute(EndTurn())
    game.execute(EndTurn())
    assert game.inspect().turn_actor_id == "angelic_sorcerer"
    assert not any(effect.kind == "blood_magic" for effect in game._state.active_effects)


def test_three_action_heal_uses_one_shared_roll_then_applies_selected_blood_magic() -> None:
    game = _first_cast_game(rolls=(20, 1, 1, 4))
    game._state.creatures["angelic_sorcerer"].hp = 5
    game._state.creatures["sorcerer_ally"].hp = 5
    game._state.creatures["sorcerer_dog"].hp = 1
    before_dice = game._dice._index

    offered = game.execute(Cast("heal", actions=3))
    assert offered.status is ResultStatus.PAUSED
    assert offered.inspection.choice is not None
    assert offered.inspection.choice.kind == "spell_self_inclusion"
    assert game._state.creatures["angelic_sorcerer"].spontaneous_slots[0].remaining == 2
    assert game._dice._index == before_dice

    inclusion = offered.inspection.choice
    recipient = game.choose(inclusion.choice_id, "include", inclusion.owner_actor_id)
    assert recipient.status is ResultStatus.PAUSED
    assert recipient.inspection.choice is not None
    assert recipient.inspection.choice.kind == "spell_blood_magic_recipient"
    assert {option.option_id for option in recipient.inspection.choice.options} == {
        "angelic_sorcerer", "sorcerer_ally",
    }
    assert game._dice._index == before_dice

    choice = recipient.inspection.choice
    completed = game.choose(choice.choice_id, "sorcerer_ally", choice.owner_actor_id)
    assert completed.status is ResultStatus.COMPLETED
    assert game._dice._index == before_dice + 1
    assert [game._state.creatures[actor_id].hp for actor_id in (
        "angelic_sorcerer", "sorcerer_ally", "sorcerer_dog",
    )] == [10, 10, 6]
    kinds = [event.kind for event in completed.events]
    assert kinds.count("heal_roll") == 1
    assert kinds.count("blood_magic_applied") == 1
    assert kinds.count("healing") == 3
    assert kinds.index("blood_magic_applied") < kinds.index("healing")
    effects = [effect for effect in game._state.active_effects if effect.kind == "blood_magic"]
    assert len(effects) == 1 and effects[0].target_actor_id == "sorcerer_ally"


def test_later_blood_magic_replaces_this_casters_earlier_recipient() -> None:
    game = _first_cast_game(rolls=(20, 1, 1, 2, 3))
    game._state.creatures["angelic_sorcerer"].hp = 5
    game._state.creatures["sorcerer_ally"].hp = 5

    first = game.execute(Cast("heal", "angelic_sorcerer", actions=1))
    blood = first.inspection.choice
    assert blood is not None and blood.kind == "spell_blood_magic_recipient"
    willingness_result = game.choose(blood.choice_id, "angelic_sorcerer", blood.owner_actor_id)
    willingness = willingness_result.inspection.choice
    assert willingness is not None and willingness.kind == "spell_willingness"
    game.choose(willingness.choice_id, "willing", willingness.owner_actor_id)
    assert [effect.target_actor_id for effect in game._state.active_effects if effect.kind == "blood_magic"] == [
        "angelic_sorcerer"
    ]

    second = game.execute(Cast("heal", "sorcerer_ally", actions=1))
    blood = second.inspection.choice
    assert blood is not None and blood.kind == "spell_blood_magic_recipient"
    willingness_result = game.choose(blood.choice_id, "sorcerer_ally", blood.owner_actor_id)
    willingness = willingness_result.inspection.choice
    assert willingness is not None and willingness.kind == "spell_willingness"
    game.choose(willingness.choice_id, "willing", willingness.owner_actor_id)
    assert [effect.target_actor_id for effect in game._state.active_effects if effect.kind == "blood_magic"] == [
        "sorcerer_ally"
    ]
    assert game._state.creatures["angelic_sorcerer"].spontaneous_slots[0].remaining == 1


def test_exhausted_spontaneous_pool_rejects_atomically() -> None:
    game = _first_cast_game(rolls=(20, 1, 1))
    sorcerer = game._state.creatures["angelic_sorcerer"]
    sorcerer.spontaneous_slots[0].remaining = 0
    before = game.inspect()
    before_dice = game._dice._index
    result = game.execute(Cast("heal", "sorcerer_ally", actions=2))
    assert result.status is ResultStatus.REJECTED
    assert "No unspent spontaneous rank slot" in result.message
    assert game.inspect() == before
    assert game._dice._index == before_dice


def test_saved_recipient_and_willingness_choices_resume_without_double_spend(tmp_path) -> None:
    game = _first_cast_game(rolls=(20, 1, 1, 4))
    offered = game.execute(Cast("heal", "sorcerer_ally", actions=2))
    assert offered.status is ResultStatus.PAUSED
    save_path = tmp_path / "angelic-first-cast.json"
    game.save(save_path)
    resumed = Encounter.load(save_path)
    assert resumed.inspect() == offered.inspection

    blood = resumed.inspect().choice
    assert blood is not None and blood.kind == "spell_blood_magic_recipient"
    chosen = resumed.choose(blood.choice_id, "angelic_sorcerer", blood.owner_actor_id)
    assert chosen.status is ResultStatus.PAUSED
    resumed.save(save_path)
    resumed = Encounter.load(save_path)
    assert resumed.inspect().choice is not None
    assert resumed.inspect().choice.kind == "spell_willingness"

    willingness = resumed.inspect().choice
    assert willingness is not None
    completed = resumed.choose(willingness.choice_id, "willing", willingness.owner_actor_id)
    assert completed.status is ResultStatus.COMPLETED
    assert resumed._state.creatures["angelic_sorcerer"].spontaneous_slots[0].remaining == 2


def test_saved_blood_magic_choice_rejects_tampered_cast_benefits(tmp_path) -> None:
    game = _first_cast_game(rolls=(20, 1, 1, 4))
    offered = game.execute(Cast("heal", "sorcerer_ally", actions=2))
    assert offered.status is ResultStatus.PAUSED
    continuation = game._state.pending_choice.continuation
    assert continuation is not None
    continuation.sorcerous_potency = 2
    path = tmp_path / "tampered-angelic-cast.json"
    game.save(path)
    with pytest.raises(ValueError, match="Blood Magic recipient choice"):
        Encounter.load(path)
