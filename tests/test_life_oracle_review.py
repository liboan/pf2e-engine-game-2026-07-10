"""Independent source review for the selected level-1 Life Oracle.

Sources checked 2026-09-18:

* Oracle: https://2e.aonprd.com/Classes.aspx?ID=61
* Life mystery: https://2e.aonprd.com/Mysteries.aspx?ID=17
* Nudge the Scales: https://2e.aonprd.com/Feats.aspx?ID=6055
* Life Link: https://2e.aonprd.com/Spells.aspx?ID=2081
* Damage: https://2e.aonprd.com/Rules.aspx?ID=2301
* Temporary HP: https://2e.aonprd.com/Rules.aspx?ID=2321
* Shield Block: https://2e.aonprd.com/Feats.aspx?ID=5212
* Scholar: https://2e.aonprd.com/Backgrounds.aspx?ID=440
* Natural Skill: https://2e.aonprd.com/Feats.aspx?ID=4479
* Fleet: https://2e.aonprd.com/Feats.aspx?ID=5150
"""

from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
from pathlib import Path
from types import MappingProxyType

import pytest

import pf2e.content as content
from pf2e.content import WARPRIEST_C, get_definition, get_setup
from pf2e.damage import DamageDefense
from pf2e.encounter import Encounter
from pf2e.investigator import BattleMedicine, RecallKnowledge
from pf2e.investigator_content import FORENSIC_INVESTIGATOR, GUARD_DOG_KNOWLEDGE
from pf2e.justice_content import JUSTICE_CHAMPION
from pf2e.model import (
    Cast,
    CreaturePlacement,
    Dismiss,
    EncounterSetup,
    EndTurn,
    LayOnHands,
    Position,
    RaiseShield,
    ResultStatus,
    Strike,
    Stride,
)


def _settle(game: Encounter) -> None:
    for _ in range(12):
        choice = game.inspect().choice
        if choice is None:
            return
        options = {option.option_id for option in choice.options}
        option_id = "keep" if "keep" in options else choice.options[0].option_id
        assert game.choose(choice.choice_id, option_id, choice.owner_actor_id).status in {
            ResultStatus.COMPLETED,
            ResultStatus.PAUSED,
        }
    raise AssertionError("bounded choice settlement did not finish")


def _actor(game: Encounter, actor_id: str):
    return next(actor for actor in game.inspect().actors if actor.actor_id == actor_id)


def _start_custom(
    monkeypatch: pytest.MonkeyPatch,
    setup: EncounterSetup,
    *,
    rolls: tuple[int, ...],
    definitions: tuple[object, ...] = (),
) -> Encounter:
    if definitions:
        monkeypatch.setattr(
            content,
            "_STAGED_CREATURES",
            MappingProxyType({
                **content._STAGED_CREATURES,
                **{definition.definition_id: definition for definition in definitions},
            }),
        )
    monkeypatch.setattr(
        content,
        "_STAGED_SETUPS",
        content._STAGED_SETUPS | {setup.setup_id: setup},
    )
    game = Encounter.start(setup, rolls=rolls)
    _settle(game)
    return game


def _to_turn(game: Encounter, actor_id: str) -> None:
    for _ in range(len(game._state.initiative_order) + 1):
        if game.inspect().turn_actor_id == actor_id:
            return
        assert game.execute(EndTurn()).status in {
            ResultStatus.COMPLETED,
            ResultStatus.PAUSED,
        }
        _settle(game)
    raise AssertionError(f"did not reach {actor_id}")


def test_life_oracle_sheet_records_every_selected_grant_and_finite_repertoire() -> None:
    definition = get_definition("life_oracle_level_1_staged")
    assert definition.ability_modifiers == (
        ("strength", 0), ("dexterity", 1), ("constitution", 2),
        ("intelligence", 0), ("wisdom", 2), ("charisma", 4),
    )
    assert (definition.hp, definition.ac, definition.perception, definition.land_speed_ft) == (
        18, 15, 5, 30,
    )
    assert dict((save, modifier) for save, _rank, modifier in definition.saves) == {
        "fortitude": 5, "reflex": 4, "will": 7,
    }
    assert {skill for skill, _rank, _modifier in definition.skills} == {
        "acrobatics", "athletics", "diplomacy", "intimidation", "medicine",
        "nature", "religion", "society", "academia_lore",
    }
    assert {"life_oracle", "nudge_the_scales", "life_link", "assurance_nature"} <= set(
        definition.abilities
    )
    assert {"Fleet", "Natural Skill", "Assurance (Nature)", "Nudge the Scales"} <= set(
        definition.feats
    )
    assert {spell.spell_id for spell in definition.spontaneous_spells if spell.cantrip} == {
        "divine_lance", "guidance", "stabilize", "light", "void_warp", "vitality_lash",
    }
    assert {spell.spell_id for spell in definition.spontaneous_spells if not spell.cantrip} == {
        "heal", "fear", "runic_weapon", "soothe",
    }
    assert [(slot.rank, slot.capacity) for slot in definition.spontaneous_slots] == [(1, 3)]
    assert [spell.spell_id for spell in definition.focus_spells] == ["life_link"]
    assert definition.focus_points == definition.focus_capacity == 1
    assert definition.held_items == ("staff",)
    assert definition.worn_items == ("leather_armor",)


def test_scholar_assurance_nature_is_an_actual_oracle_action_without_a_die() -> None:
    game = Encounter.start(get_setup("staged_life_oracle_nudge"), rolls=(20, 1))
    _settle(game)
    dice_before = game._dice.to_data()
    result = game.execute(RecallKnowledge(
        "guard_dog",
        GUARD_DOG_KNOWLEDGE.question,
        "nature",
        "dog",
        use_assurance=True,
    ))
    assert result.status is ResultStatus.COMPLETED
    event = next(event for event in result.events if event.kind == "recall_knowledge")
    assert event.check is not None
    assert (event.check.method, event.check.die, event.check.total, event.check.modifier) == (
        "assurance", None, 13, 3,
    )
    assert game.inspect().choice is None
    assert game._dice.to_data() == dice_before


def test_life_curse_penalizes_only_healing_restored_to_oracle() -> None:
    game = Encounter.start(
        get_setup("staged_life_oracle_nudge"),
        rolls=(1, 20, 20, 4, 14, 4),
    )
    _settle(game)
    assert game.execute(Stride((Position(3, 2), Position(2, 2)))).status is ResultStatus.COMPLETED
    assert game.execute(Strike("oracle", "jaws")).status is ResultStatus.COMPLETED
    assert game.execute(EndTurn()).status is ResultStatus.COMPLETED

    oracle_before = _actor(game, "oracle")
    assert game.nudge_the_scales("oracle", "oracle").status is ResultStatus.COMPLETED
    assert _actor(game, "oracle").hp == min(oracle_before.max_hp, oracle_before.hp + 4)
    assert game._state.creatures["oracle"].oracle_cursebound == 1

    assert game.execute(Strike("dog", "staff")).status is ResultStatus.PAUSED
    _settle(game)
    dog_before = _actor(game, "dog")
    assert dog_before.hp < dog_before.max_hp
    ally_heal = game.nudge_the_scales("oracle", "dog")
    assert ally_heal.status is ResultStatus.COMPLETED
    assert _actor(game, "dog").hp == min(dog_before.max_hp, dog_before.hp + 4)
    assert game._state.creatures["oracle"].oracle_cursebound == 2


def test_nudge_uses_the_recipient_oracles_curse_even_with_another_oracle_caster(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    setup = EncounterSetup(
        "review_nudge_to_other_cursed_oracle",
        "Review Nudge to another cursed Life Oracle",
        6,
        4,
        (
            CreaturePlacement(
                "caster", "life_oracle_level_1_staged", "Casting Oracle", "blue", Position(1, 1)
            ),
            CreaturePlacement(
                "recipient", "life_oracle_level_1_staged", "Recipient Oracle", "blue", Position(2, 1)
            ),
            CreaturePlacement(
                "dog", "guard_dog_mc2924", "Guard Dog", "red", Position(5, 3)
            ),
        ),
    )
    game = _start_custom(monkeypatch, setup, rolls=(20, 2, 1))
    recipient = game._state.creatures["recipient"]
    recipient.hp = 5
    recipient.oracle_cursebound = 2

    result = game.nudge_the_scales("caster", "recipient")

    assert result.status is ResultStatus.COMPLETED
    assert game._state.creatures["recipient"].hp == 7
    assert game._state.creatures["recipient"].oracle_cursebound == 2
    assert game._state.creatures["caster"].oracle_cursebound == 1


def test_refocus_reduces_cursebound_even_when_focus_is_full_and_round_trips(
    tmp_path: Path,
) -> None:
    game = Encounter.start(
        get_setup("staged_life_oracle_nudge"),
        rolls=(1, 20, 20, 4, 20, 4),
    )
    _settle(game)
    assert game.execute(Stride((Position(3, 2), Position(2, 2)))).status is ResultStatus.COMPLETED
    assert game.execute(Strike("oracle", "jaws")).status is ResultStatus.COMPLETED
    assert game.execute(EndTurn()).status is ResultStatus.COMPLETED
    assert game.nudge_the_scales("oracle", "oracle").status is ResultStatus.COMPLETED
    assert game.execute(Strike("dog", "staff")).status is ResultStatus.PAUSED
    _settle(game)
    assert game.inspect().winner_team == "blue"
    assert game._state.creatures["oracle"].oracle_cursebound == 1
    assert _actor(game, "oracle").focus_points == 1

    before_time = game.inspect().world_time_seconds
    result = game.refocus("oracle")
    assert result.status is ResultStatus.COMPLETED
    assert game.inspect().world_time_seconds == before_time + 600
    assert game._state.creatures["oracle"].oracle_cursebound == 0
    assert _actor(game, "oracle").focus_points == 1

    path = tmp_path / "life-oracle-refocused.json"
    game.save(path)
    restored = Encounter.load(path)
    assert restored.inspect() == game.inspect()
    assert restored._state.creatures["oracle"].oracle_cursebound == 0


def test_curse_cap_rejection_is_fully_atomic() -> None:
    game = Encounter.start(
        get_setup("staged_life_oracle_nudge"),
        rolls=(1, 20, 20, 4),
    )
    _settle(game)
    assert game.execute(Stride((Position(3, 2), Position(2, 2)))).status is ResultStatus.COMPLETED
    assert game.execute(Strike("oracle", "jaws")).status is ResultStatus.COMPLETED
    assert game.execute(EndTurn()).status is ResultStatus.COMPLETED
    assert game.nudge_the_scales("oracle", "oracle").status is ResultStatus.COMPLETED
    assert game.nudge_the_scales("oracle", "oracle").status is ResultStatus.COMPLETED
    before_state = deepcopy(game._state)
    before_dice = game._dice.to_data()
    rejected = game.nudge_the_scales("oracle", "oracle")
    assert rejected.status is ResultStatus.REJECTED
    assert game._state == before_state
    assert game._dice.to_data() == before_dice


@pytest.mark.parametrize(
    ("save_roll", "degree", "damage", "enfeebled"),
    (
        (20, "CRITICAL_SUCCESS", 0, False),
        (12, "SUCCESS", 3, False),
        (11, "FAILURE", 7, False),
        (1, "CRITICAL_FAILURE", 14, True),
    ),
)
def test_vitality_lash_is_a_two_action_basic_fortitude_cantrip_at_every_degree(
    save_roll: int,
    degree: str,
    damage: int,
    enfeebled: bool,
) -> None:
    game = Encounter.start(
        get_setup("staged_life_oracle_vitality_lash"),
        rolls=(20, 1, save_roll, 3, 4),
    )
    _settle(game)
    before = _actor(game, "oracle")
    target_before = _actor(game, "death_oracle")
    result = game.execute(Cast("vitality_lash", "death_oracle", actions=2))
    assert result.status is ResultStatus.PAUSED
    choice = result.inspection.choice
    assert choice is not None and choice.kind == "spell_save_hero_reroll"
    result = game.choose(choice.choice_id, "keep", choice.owner_actor_id)

    check = next(event.check for event in result.events if event.kind == "spell_save")
    packet = next(event.damage for event in result.events if event.kind == "spell_damage")
    after = _actor(game, "oracle")
    target_after = _actor(game, "death_oracle")
    assert check is not None and check.degree.name == degree
    assert packet is not None and packet.total == damage
    assert target_after.hp == target_before.hp - damage
    assert any(effect.kind == "enfeebled" and effect.value == 1 for effect in target_after.condition_effects) is enfeebled
    assert after.actions_remaining == before.actions_remaining - 2
    assert after.focus_points == before.focus_points
    assert after.spontaneous_slots == before.spontaneous_slots


def test_vitality_lash_rejects_an_ordinary_living_target_atomically() -> None:
    game = Encounter.start(
        get_setup("staged_life_oracle_nudge"),
        rolls=(20, 1),
    )
    _settle(game)
    before_state = deepcopy(game._state)
    before_dice = game._dice.to_data()
    result = game.execute(Cast("vitality_lash", "dog", actions=2))
    assert result.status is ResultStatus.REJECTED
    assert game._state == before_state
    assert game._dice.to_data() == before_dice


def test_vitality_lash_critical_failure_enfeebled_expires_at_caster_next_start() -> None:
    game = Encounter.start(
        get_setup("staged_life_oracle_vitality_lash"),
        rolls=(20, 1, 1, 1, 1),
    )
    _settle(game)
    paused = game.execute(Cast("vitality_lash", "death_oracle", actions=2))
    choice = paused.inspection.choice
    assert choice is not None
    result = game.choose(choice.choice_id, "keep", choice.owner_actor_id)
    assert result.status is ResultStatus.COMPLETED
    assert any(effect.kind == "enfeebled" for effect in _actor(game, "death_oracle").condition_effects)
    assert game.execute(EndTurn()).status is ResultStatus.COMPLETED
    assert any(effect.kind == "enfeebled" for effect in _actor(game, "death_oracle").condition_effects)
    assert game.execute(EndTurn()).status is ResultStatus.COMPLETED
    assert not any(effect.kind == "enfeebled" for effect in _actor(game, "death_oracle").condition_effects)


def test_lay_on_hands_applies_the_life_curse_of_its_oracle_recipient(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    setup = EncounterSetup(
        "review_lay_on_hands_to_cursed_oracle",
        "Review Lay on Hands to cursed Life Oracle",
        5,
        4,
        (
            CreaturePlacement(
                "champion", JUSTICE_CHAMPION.definition_id, "Champion", "blue", Position(1, 1)
            ),
            CreaturePlacement(
                "oracle", "life_oracle_level_1_staged", "Life Oracle", "blue", Position(1, 2)
            ),
            CreaturePlacement(
                "dog", "guard_dog_mc2924", "Guard Dog", "red", Position(4, 3)
            ),
        ),
    )
    game = _start_custom(monkeypatch, setup, rolls=(20, 2, 1))
    oracle = game._state.creatures["oracle"]
    oracle.hp = 5
    oracle.oracle_cursebound = 2

    result = game.execute(LayOnHands("oracle"))

    assert result.status is ResultStatus.COMPLETED
    assert game._state.creatures["champion"].focus_points == 0
    assert game._state.creatures["oracle"].hp == 9
    assert any(event.kind == "lay_on_hands_ac" for event in result.events)


def test_life_death_mode_requires_daily_preparation_and_persists_with_curse(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    setup = EncounterSetup(
        "review_oracle_mode_requires_daily_preparation",
        "Review Oracle mode daily preparation boundary",
        4,
        3,
        (
            CreaturePlacement(
                "oracle", "life_oracle_level_1_staged", "Life Oracle", "blue", Position(1, 1)
            ),
            CreaturePlacement(
                "dog", "guard_dog_mc2924", "Guard Dog", "red", Position(2, 1)
            ),
        ),
    )
    game = _start_custom(monkeypatch, setup, rolls=(20, 1, 20, 4))
    game._state.creatures["dog"].hp = 1
    assert game.nudge_the_scales("oracle", "oracle").status is ResultStatus.COMPLETED
    assert game.nudge_the_scales("oracle", "oracle").status is ResultStatus.COMPLETED
    assert game.execute(Strike("dog", "staff")).status in {
        ResultStatus.COMPLETED,
        ResultStatus.PAUSED,
    }
    _settle(game)
    assert game.inspect().winner_team == "blue"
    before = deepcopy(game._state)

    result = game.set_oracle_life_mode("oracle", "death")

    assert result.status is ResultStatus.REJECTED
    assert game._state == before

    assert game.record_rested(("oracle",), day_number=2, elapsed_seconds=1).status is ResultStatus.COMPLETED
    before_missing_choice = deepcopy(game._state)
    assert game.daily_prepare(("oracle",)).status is ResultStatus.REJECTED
    assert game._state == before_missing_choice
    assert game.set_oracle_life_mode("oracle", "death").status is ResultStatus.COMPLETED
    selected = deepcopy(game._state)
    assert game.set_oracle_life_mode("oracle", "life").status is ResultStatus.REJECTED
    assert game._state == selected

    assert game.daily_prepare(("oracle",)).status is ResultStatus.COMPLETED
    assert game._state.creatures["oracle"].oracle_life_mode == "death"
    assert game._state.creatures["oracle"].oracle_life_mode_selected_day == 2
    assert game._state.creatures["oracle"].oracle_cursebound == 2

    path = tmp_path / "oracle-death-mode-prepared.json"
    game.save(path)
    game = Encounter.load(path)
    assert game._state.creatures["oracle"].oracle_life_mode == "death"
    assert game._state.creatures["oracle"].oracle_life_mode_selected_day == 2
    assert game._state.creatures["oracle"].oracle_cursebound == 2
    assert game.refocus("oracle").status is ResultStatus.COMPLETED
    assert game._state.creatures["oracle"].oracle_cursebound == 1
    assert game._state.creatures["oracle"].oracle_life_mode == "death"


def test_oracle_curse_is_scoped_to_the_healing_recipient_in_both_directions(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    oracle_heals_ally = EncounterSetup(
        "review_cursed_oracle_heals_ally",
        "Review cursed Oracle heals an ordinary ally",
        6,
        4,
        (
            CreaturePlacement(
                "oracle", "life_oracle_level_1_staged", "Life Oracle", "blue", Position(1, 1)
            ),
            CreaturePlacement(
                "ally", "fighter_m_level_1", "Ordinary Ally", "blue", Position(2, 1)
            ),
            CreaturePlacement(
                "dog", "guard_dog_mc2924", "Guard Dog", "red", Position(5, 3)
            ),
        ),
    )
    game = _start_custom(monkeypatch, oracle_heals_ally, rolls=(20, 2, 1, 1))
    game._state.creatures["oracle"].oracle_cursebound = 2
    game._state.creatures["ally"].hp = 1
    cast = game.execute(Cast("heal", "ally", actions=2))
    assert cast.status in {ResultStatus.COMPLETED, ResultStatus.PAUSED}
    _settle(game)
    assert game._state.creatures["ally"].hp == 11
    assert game._state.creatures["oracle"].spontaneous_slots[0].remaining == 2

    cleric_heals_oracle = EncounterSetup(
        "review_cleric_heals_cursed_oracle",
        "Review Cleric heals a cursed Oracle",
        6,
        4,
        (
            CreaturePlacement(
                "cleric", WARPRIEST_C.definition_id, "Warpriest", "blue", Position(1, 1)
            ),
            CreaturePlacement(
                "oracle", "life_oracle_level_1_staged", "Life Oracle", "blue", Position(2, 1)
            ),
            CreaturePlacement(
                "dog", "guard_dog_mc2924", "Guard Dog", "red", Position(5, 3)
            ),
        ),
    )
    game = _start_custom(monkeypatch, cleric_heals_oracle, rolls=(20, 2, 1, 1))
    game._state.creatures["oracle"].hp = 5
    game._state.creatures["oracle"].oracle_cursebound = 2
    cast = game.execute(Cast("heal", "oracle", actions=2, slot_id="ordinary_heal_1"))
    assert cast.status in {ResultStatus.COMPLETED, ResultStatus.PAUSED}
    _settle(game)
    assert game._state.creatures["oracle"].hp == 12
    assert next(
        slot for slot in game._state.creatures["cleric"].prepared_slots
        if slot.slot_id == "ordinary_heal_1"
    ).spent


def test_death_mode_blocks_heal_and_void_warp_but_retains_soothe_and_nudge(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    cleric_and_oracle = EncounterSetup(
        "review_death_mode_spells",
        "Review death-mode spell matrix",
        6,
        4,
        (
            CreaturePlacement(
                "cleric", WARPRIEST_C.definition_id, "Warpriest", "blue", Position(1, 1)
            ),
            CreaturePlacement(
                "oracle", "life_oracle_level_1_staged", "Life Oracle", "blue", Position(2, 1)
            ),
            CreaturePlacement(
                "dog", "guard_dog_mc2924", "Guard Dog", "red", Position(5, 3)
            ),
        ),
    )
    game = _start_custom(monkeypatch, cleric_and_oracle, rolls=(20, 2, 1, 1))
    oracle = game._state.creatures["oracle"]
    oracle.hp = 5
    oracle.oracle_life_mode = "death"
    blocked = game.execute(Cast("heal", "oracle", actions=2, slot_id="ordinary_heal_1"))
    assert blocked.status in {ResultStatus.COMPLETED, ResultStatus.PAUSED}
    _settle(game)
    assert game._state.creatures["oracle"].hp == 5
    assert next(
        slot for slot in game._state.creatures["cleric"].prepared_slots
        if slot.slot_id == "ordinary_heal_1"
    ).spent

    void_warp = EncounterSetup(
        "review_death_mode_void_warp",
        "Review death-mode Void Warp immunity",
        6,
        4,
        (
            CreaturePlacement(
                "cleric", WARPRIEST_C.definition_id, "Warpriest", "blue", Position(1, 1)
            ),
            CreaturePlacement(
                "oracle", "life_oracle_level_1_staged", "Life Oracle", "red", Position(3, 1)
            ),
        ),
    )
    game = _start_custom(monkeypatch, void_warp, rolls=(20, 1, 1, 4, 4))
    game._state.creatures["oracle"].oracle_life_mode = "death"
    before_hp = game._state.creatures["oracle"].hp
    warped = game.execute(Cast("void_warp", "oracle", actions=2))
    assert warped.status is ResultStatus.PAUSED
    _settle(game)
    assert game._state.creatures["oracle"].hp == before_hp

    oracle_self = EncounterSetup(
        "review_death_mode_oracle_self_healing",
        "Review death-mode Oracle self healing",
        5,
        3,
        (
            CreaturePlacement(
                "oracle", "life_oracle_level_1_staged", "Life Oracle", "blue", Position(1, 1)
            ),
            CreaturePlacement(
                "dog", "guard_dog_mc2924", "Guard Dog", "red", Position(4, 2)
            ),
        ),
    )
    game = _start_custom(monkeypatch, oracle_self, rolls=(20, 1, 1))
    oracle = game._state.creatures["oracle"]
    oracle.hp = 5
    oracle.oracle_cursebound = 2
    oracle.oracle_life_mode = "death"
    soothed = game.execute(Cast("soothe", "oracle", actions=2))
    assert soothed.status in {ResultStatus.COMPLETED, ResultStatus.PAUSED}
    _settle(game)
    assert game._state.creatures["oracle"].hp == 8

    game = _start_custom(monkeypatch, oracle_self, rolls=(20, 1))
    oracle = game._state.creatures["oracle"]
    oracle.hp = 5
    oracle.oracle_life_mode = "death"
    assert game.nudge_the_scales("oracle", "oracle").status is ResultStatus.COMPLETED
    assert game._state.creatures["oracle"].hp == 9
    assert game._state.creatures["oracle"].oracle_cursebound == 1


def test_death_mode_blocks_lay_on_hands_but_not_actual_battle_medicine(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    champion_setup = EncounterSetup(
        "review_death_mode_lay_on_hands",
        "Review death-mode Lay on Hands",
        5,
        4,
        (
            CreaturePlacement(
                "champion", JUSTICE_CHAMPION.definition_id, "Champion", "blue", Position(1, 1)
            ),
            CreaturePlacement(
                "oracle", "life_oracle_level_1_staged", "Life Oracle", "blue", Position(1, 2)
            ),
            CreaturePlacement(
                "dog", "guard_dog_mc2924", "Guard Dog", "red", Position(4, 3)
            ),
        ),
    )
    game = _start_custom(monkeypatch, champion_setup, rolls=(20, 2, 1))
    oracle = game._state.creatures["oracle"]
    oracle.hp = 5
    oracle.oracle_cursebound = 2
    oracle.oracle_life_mode = "death"
    blocked = game.execute(LayOnHands("oracle"))
    assert blocked.status is ResultStatus.COMPLETED
    assert game._state.creatures["oracle"].hp == 5
    assert game._state.creatures["champion"].focus_points == 0
    assert any(event.kind == "lay_on_hands_ac" for event in blocked.events)

    medicine_setup = EncounterSetup(
        "review_death_mode_battle_medicine",
        "Review death-mode Battle Medicine",
        5,
        4,
        (
            CreaturePlacement(
                "investigator", FORENSIC_INVESTIGATOR.definition_id, "Investigator", "blue", Position(1, 1)
            ),
            CreaturePlacement(
                "oracle", "life_oracle_level_1_staged", "Life Oracle", "blue", Position(2, 1)
            ),
            CreaturePlacement(
                "dog", "guard_dog_mc2924", "Guard Dog", "red", Position(4, 3)
            ),
        ),
    )
    game = _start_custom(monkeypatch, medicine_setup, rolls=(20, 2, 1, 12, 1, 1))
    oracle = game._state.creatures["oracle"]
    oracle.hp = 5
    oracle.oracle_cursebound = 2
    oracle.oracle_life_mode = "death"
    treated = game.execute(BattleMedicine("oracle"))
    assert treated.status is ResultStatus.PAUSED
    _settle(game)
    assert game._state.creatures["oracle"].hp == 8


def test_life_link_is_a_one_action_focus_cast_with_vitality_healing_and_free_dismiss(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    setup = EncounterSetup(
        "review_life_link_cast",
        "Review Life Link cast",
        6,
        4,
        (
            CreaturePlacement(
                "oracle", "life_oracle_level_1_staged", "Life Oracle", "blue", Position(1, 1)
            ),
            CreaturePlacement(
                "ally", "fighter_m_level_1", "Linked Ally", "blue", Position(2, 1)
            ),
            CreaturePlacement(
                "dog", "guard_dog_mc2924", "Guard Dog", "red", Position(5, 3)
            ),
        ),
    )
    game = _start_custom(monkeypatch, setup, rolls=(20, 2, 1, 4))
    game._state.creatures["ally"].hp = 1
    before = _actor(game, "oracle")

    cast = game.execute(Cast("life_link", "ally", actions=1))

    assert cast.status is ResultStatus.COMPLETED
    assert game._state.creatures["ally"].hp == 5
    after = _actor(game, "oracle")
    assert (after.actions_remaining, after.focus_points) == (
        before.actions_remaining - 1,
        before.focus_points - 1,
    )
    effect = next(effect for effect in game._state.active_effects if effect.kind == "life_link")
    assert (effect.source_actor_id, effect.target_actor_id, effect.value) == (
        "oracle", "ally", 3,
    )
    before_actions = _actor(game, "oracle").actions_remaining
    dismissed = game.execute(Dismiss(effect_id=effect.effect_id))
    assert dismissed.status is ResultStatus.COMPLETED
    assert _actor(game, "oracle").actions_remaining == before_actions
    assert not any(effect.kind == "life_link" for effect in game._state.active_effects)

    death_setup = replace(
        setup,
        setup_id="review_life_link_death_mode_target",
        name="Review Life Link death-mode target",
        placements=(
            setup.placements[0],
            CreaturePlacement(
                "recipient", "life_oracle_level_1_staged", "Death-mode Oracle", "blue", Position(2, 1)
            ),
            setup.placements[2],
        ),
    )
    game = _start_custom(monkeypatch, death_setup, rolls=(20, 2, 1, 4))
    recipient = game._state.creatures["recipient"]
    recipient.hp = 5
    recipient.oracle_life_mode = "death"
    assert game.execute(Cast("life_link", "recipient", actions=1)).status is ResultStatus.COMPLETED
    assert game._state.creatures["recipient"].hp == 5
    assert any(
        effect.kind == "life_link" and effect.target_actor_id == "recipient"
        for effect in game._state.active_effects
    )


def test_life_link_transfers_once_per_round_before_temporary_hp_then_resets(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    setup = EncounterSetup(
        "review_life_link_round_and_temp_hp",
        "Review Life Link round and temporary HP",
        5,
        3,
        (
            CreaturePlacement(
                "oracle", "life_oracle_level_1_staged", "Life Oracle", "blue", Position(1, 1)
            ),
            CreaturePlacement(
                "ally", "fighter_m_level_1", "Linked Ally", "blue", Position(2, 1)
            ),
            CreaturePlacement(
                "dog", "guard_dog_mc2924", "Guard Dog", "red", Position(3, 1)
            ),
        ),
    )
    game = _start_custom(
        monkeypatch,
        setup,
        rolls=(20, 2, 1, 4, 12, 4, 17, 4, 12, 4),
    )
    assert game.execute(Cast("life_link", "ally", actions=1)).status is ResultStatus.COMPLETED
    ally = game._state.creatures["ally"]
    ally.temporary_hp = 6
    ally.temporary_hp_source_id = "review:temporary-hp"
    ally.temporary_hp_expires_at_seconds = 600
    assert game.execute(EndTurn()).status is ResultStatus.COMPLETED
    _to_turn(game, "dog")

    first = game.execute(Strike("ally", "jaws"))
    assert first.status is ResultStatus.COMPLETED
    ally = game._state.creatures["ally"]
    assert (game._state.creatures["oracle"].hp, ally.hp, ally.temporary_hp) == (15, 21, 4)
    assert len([event for event in first.events if event.kind == "life_link_transfer"]) == 1

    second = game.execute(Strike("ally", "jaws"))
    assert second.status is ResultStatus.COMPLETED
    ally = game._state.creatures["ally"]
    assert (game._state.creatures["oracle"].hp, ally.hp, ally.temporary_hp) == (15, 20, 0)
    assert not any(event.kind == "life_link_transfer" for event in second.events)

    assert game.execute(EndTurn()).status is ResultStatus.COMPLETED
    _to_turn(game, "dog")
    third = game.execute(Strike("ally", "jaws"))
    assert third.status is ResultStatus.COMPLETED
    ally = game._state.creatures["ally"]
    assert (game._state.creatures["oracle"].hp, ally.hp) == (12, 18)
    assert len([event for event in third.events if event.kind == "life_link_transfer"]) == 1


def test_zero_after_iwr_preserves_life_link_for_later_damage_that_round(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    resistant = replace(
        get_definition("fighter_m_level_1"),
        definition_id="review_life_link_resistant_ally",
        hero_points=0,
        damage_defenses=(DamageDefense("resistance", "all", 4, source="review ward"),),
    )
    setup = EncounterSetup(
        "review_life_link_after_iwr",
        "Review Life Link after IWR",
        5,
        3,
        (
            CreaturePlacement(
                "oracle", "life_oracle_level_1_staged", "Life Oracle", "blue", Position(1, 1)
            ),
            CreaturePlacement(
                "ally", resistant.definition_id, "Resistant Ally", "blue", Position(2, 1)
            ),
            CreaturePlacement(
                "dog", "guard_dog_mc2924", "Guard Dog", "red", Position(3, 1)
            ),
        ),
    )
    game = _start_custom(
        monkeypatch,
        setup,
        definitions=(resistant,),
        rolls=(20, 2, 1, 4, 12, 3, 17, 4),
    )
    assert game.execute(Cast("life_link", "ally", actions=1)).status is ResultStatus.COMPLETED
    effect = next(effect for effect in game._state.active_effects if effect.kind == "life_link")
    _to_turn(game, "dog")

    zero = game.execute(Strike("ally", "jaws"))
    assert zero.status is ResultStatus.COMPLETED
    assert game._state.creatures["oracle"].hp == 18
    assert game._state.creatures["ally"].hp == 21
    effect = next(effect for effect in game._state.active_effects if effect.kind == "life_link")
    assert effect.life_link_used_round == 0

    positive = game.execute(Strike("ally", "jaws"))
    assert positive.status is ResultStatus.COMPLETED
    assert game._state.creatures["oracle"].hp == 17
    assert game._state.creatures["ally"].hp == 21
    assert len([event for event in positive.events if event.kind == "life_link_transfer"]) == 1


@pytest.mark.parametrize(
    ("damage_roll", "expected_oracle_hp", "expected_shield_hp", "used"),
    ((1, 18, 20, False), (5, 15, 17, True)),
)
def test_shield_block_finishes_before_life_link_and_saved_choice_does_not_replay(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    damage_roll: int,
    expected_oracle_hp: int,
    expected_shield_hp: int,
    used: bool,
) -> None:
    dog_attack = get_definition("guard_dog_mc2924").attacks[0]
    attacker = replace(
        get_definition("guard_dog_mc2924"),
        definition_id=f"review_life_link_shield_attacker_{damage_roll}",
        attacks=(replace(dog_attack, damage_dice=(8,), damage_modifier=3),),
    )
    setup = EncounterSetup(
        f"review_life_link_shield_{damage_roll}",
        "Review Shield Block before Life Link",
        5,
        3,
        (
            CreaturePlacement(
                "oracle", "life_oracle_level_1_staged", "Life Oracle", "blue", Position(1, 1)
            ),
            CreaturePlacement(
                "fighter", "fighter_m_steel_shield_level_1", "Shield Fighter", "blue", Position(2, 1)
            ),
            CreaturePlacement(
                "dog", attacker.definition_id, "Guard Dog", "red", Position(3, 1)
            ),
        ),
    )
    game = _start_custom(
        monkeypatch,
        setup,
        definitions=(attacker,),
        rolls=(20, 19, 1, 4, 14, damage_roll),
    )
    assert game.execute(Cast("life_link", "fighter", actions=1)).status is ResultStatus.COMPLETED
    _to_turn(game, "fighter")
    assert game.execute(RaiseShield()).status is ResultStatus.COMPLETED
    _to_turn(game, "dog")
    offered = game.execute(Strike("fighter", "jaws"))
    assert offered.status is ResultStatus.PAUSED
    assert offered.inspection.choice is not None and offered.inspection.choice.kind == "shield_block"
    path = tmp_path / f"life-link-shield-{damage_roll}.json"
    game.save(path)
    game = Encounter.load(path)
    choice = game.inspect().choice
    assert choice is not None

    blocked = game.choose(choice.choice_id, "block", choice.owner_actor_id)

    assert blocked.status is ResultStatus.COMPLETED
    fighter = game._state.creatures["fighter"]
    shield = game._state.item_instances["fighter:steel_shield"]
    assert (game._state.creatures["oracle"].hp, fighter.hp, shield.hp) == (
        expected_oracle_hp,
        21,
        expected_shield_hp,
    )
    effect = next(effect for effect in game._state.active_effects if effect.kind == "life_link")
    assert (effect.life_link_used_round == game.inspect().round_number) is used


@pytest.mark.parametrize(
    ("option", "expected_dying", "expected_hero_points"),
    (("normal", 1, 1), ("heroic_recovery", 0, 0)),
)
def test_saved_target_health_choice_does_not_apply_life_link_twice(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    option: str,
    expected_dying: int,
    expected_hero_points: int,
) -> None:
    setup = EncounterSetup(
        "review_life_link_saved_health_choice",
        "Review saved Life Link health choice",
        5,
        3,
        (
            CreaturePlacement(
                "oracle", "life_oracle_level_1_staged", "Life Oracle", "blue", Position(1, 1)
            ),
            CreaturePlacement(
                "ally", "fighter_m_level_1", "Linked Ally", "blue", Position(2, 1)
            ),
            CreaturePlacement(
                "dog", "guard_dog_mc2924", "Guard Dog", "red", Position(3, 1)
            ),
        ),
    )
    game = _start_custom(monkeypatch, setup, rolls=(20, 2, 1, 4, 12, 4))
    assert game.execute(Cast("life_link", "ally", actions=1)).status is ResultStatus.COMPLETED
    game._state.creatures["ally"].hp = 1
    _to_turn(game, "dog")
    paused = game.execute(Strike("ally", "jaws"))
    assert paused.status is ResultStatus.PAUSED
    assert paused.inspection.choice is not None
    assert paused.inspection.choice.kind == "heroic_recovery_damage"
    assert game._state.creatures["oracle"].hp == 15
    effect = next(effect for effect in game._state.active_effects if effect.kind == "life_link")
    assert effect.life_link_used_round == game.inspect().round_number

    path = tmp_path / f"life-link-health-choice-{option}.json"
    game.save(path)
    game = Encounter.load(path)
    choice = game.inspect().choice
    assert choice is not None
    resolved = game.choose(choice.choice_id, option, choice.owner_actor_id)

    assert resolved.status is ResultStatus.COMPLETED
    assert game._state.creatures["oracle"].hp == 15
    assert game._state.creatures["ally"].hp == 0
    assert game._state.creatures["ally"].dying == expected_dying
    assert game._state.creatures["ally"].hero_points == expected_hero_points


def test_life_link_bypasses_oracle_temporary_hp_and_ends_on_unconsciousness(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    setup = EncounterSetup(
        "review_life_link_oracle_unconscious",
        "Review Life Link Oracle unconsciousness",
        5,
        3,
        (
            CreaturePlacement(
                "oracle", "life_oracle_level_1_staged", "Life Oracle", "blue", Position(1, 1)
            ),
            CreaturePlacement(
                "ally", "fighter_m_level_1", "Linked Ally", "blue", Position(2, 1)
            ),
            CreaturePlacement(
                "dog", "guard_dog_mc2924", "Guard Dog", "red", Position(3, 1)
            ),
        ),
    )
    game = _start_custom(monkeypatch, setup, rolls=(20, 2, 1, 4, 12, 2))
    assert game.execute(Cast("life_link", "ally", actions=1)).status is ResultStatus.COMPLETED
    oracle = game._state.creatures["oracle"]
    oracle.hp = 2
    oracle.temporary_hp = 5
    oracle.temporary_hp_source_id = "review:oracle-temp"
    oracle.temporary_hp_expires_at_seconds = 600
    _to_turn(game, "dog")

    result = game.execute(Strike("ally", "jaws"))

    assert result.status is ResultStatus.COMPLETED
    oracle = game._state.creatures["oracle"]
    assert (oracle.hp, oracle.temporary_hp, oracle.unconscious, oracle.dying) == (0, 5, True, 1)
    assert not any(effect.kind == "life_link" for effect in game._state.active_effects)


def test_life_link_expires_at_the_tenth_later_oracle_turn_start(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    setup = EncounterSetup(
        "review_life_link_one_minute",
        "Review Life Link one-minute duration",
        6,
        3,
        (
            CreaturePlacement(
                "oracle", "life_oracle_level_1_staged", "Life Oracle", "blue", Position(1, 1)
            ),
            CreaturePlacement(
                "ally", "fighter_m_level_1", "Linked Ally", "blue", Position(2, 1)
            ),
            CreaturePlacement(
                "dog", "guard_dog_mc2924", "Guard Dog", "red", Position(5, 1)
            ),
        ),
    )
    game = _start_custom(monkeypatch, setup, rolls=(20, 2, 1, 4))
    assert game.execute(Cast("life_link", "ally", actions=1)).status is ResultStatus.COMPLETED
    effect = next(effect for effect in game._state.active_effects if effect.kind == "life_link")
    assert effect.expires_at_source_start == game._state.actor_start_counts["oracle"] + 10

    for _ in range(9):
        assert game.execute(EndTurn()).status is ResultStatus.COMPLETED
        _to_turn(game, "oracle")
    assert game._state.actor_start_counts["oracle"] == 10
    assert any(effect.kind == "life_link" for effect in game._state.active_effects)

    assert game.execute(EndTurn()).status is ResultStatus.COMPLETED
    _to_turn(game, "oracle")
    assert game._state.actor_start_counts["oracle"] == 11
    assert not any(effect.kind == "life_link" for effect in game._state.active_effects)


def test_life_link_has_no_ongoing_range_requirement_after_its_legal_cast(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    setup = EncounterSetup(
        "review_life_link_no_ongoing_range",
        "Review Life Link without ongoing range",
        13,
        3,
        (
            CreaturePlacement(
                "oracle", "life_oracle_level_1_staged", "Life Oracle", "blue", Position(7, 1)
            ),
            CreaturePlacement(
                "ally", "fighter_m_level_1", "Linked Ally", "blue", Position(1, 1)
            ),
            CreaturePlacement(
                "dog", "guard_dog_mc2924", "Guard Dog", "red", Position(2, 1)
            ),
        ),
    )
    game = _start_custom(monkeypatch, setup, rolls=(20, 2, 1, 4, 12, 4))
    assert game.execute(Cast("life_link", "ally", actions=1)).status is ResultStatus.COMPLETED
    assert game.execute(Stride(tuple(Position(x, 1) for x in range(8, 13)))).status is ResultStatus.COMPLETED
    assert game.execute(EndTurn()).status is ResultStatus.COMPLETED
    assert game.execute(EndTurn()).status is ResultStatus.COMPLETED
    assert game.execute(Strike("ally", "jaws")).status is ResultStatus.COMPLETED
    assert game._state.creatures["oracle"].hp == 15
    assert game._state.creatures["ally"].hp == 19


def test_life_link_healthy_fight_refocus_save_and_actual_next_scene_cast(
    tmp_path: Path,
) -> None:
    game = Encounter.start(
        get_setup("staged_life_oracle_nudge"),
        rolls=(20, 1, 4, 20, 4, 20, 4, 20, 1, 4),
    )
    _settle(game)
    assert game.execute(Cast("life_link", "dog", actions=1)).status is ResultStatus.COMPLETED
    assert game.execute(Stride((Position(2, 2), Position(3, 2)))).status is ResultStatus.COMPLETED
    first = game.execute(Strike("dog", "staff"))
    assert first.status in {ResultStatus.COMPLETED, ResultStatus.PAUSED}
    _settle(game)
    assert game._state.creatures["oracle"].hp == 15
    effect = next(effect for effect in game._state.active_effects if effect.kind == "life_link")
    assert effect.life_link_used_round == game.inspect().round_number
    assert game.execute(EndTurn()).status is ResultStatus.COMPLETED
    second = game.execute(Strike("dog", "staff"))
    assert second.status in {ResultStatus.COMPLETED, ResultStatus.PAUSED}
    _settle(game)
    assert game.inspect().winner_team == "blue"
    assert game._state.creatures["oracle"].hp == 12
    assert game._state.creatures["oracle"].focus_points == 0

    assert game.refocus("oracle").status is ResultStatus.COMPLETED
    assert game._state.creatures["oracle"].focus_points == 1
    assert not any(effect.kind == "life_link" for effect in game._state.active_effects)
    path = tmp_path / "life-link-between-scenes.json"
    game.save(path)
    game = Encounter.load(path)
    assert game.next_encounter(get_setup("staged_life_oracle_next")).status is ResultStatus.PAUSED
    _settle(game)
    cast = game.execute(Cast("life_link", "next_dog", actions=1))
    assert cast.status is ResultStatus.COMPLETED
    assert game._state.creatures["oracle"].focus_points == 0
    assert any(
        effect.kind == "life_link" and effect.target_actor_id == "next_dog"
        for effect in game._state.active_effects
    )
