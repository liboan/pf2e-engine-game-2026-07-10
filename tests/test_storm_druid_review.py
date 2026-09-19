"""Independent rules and actual-play review for the selected Storm Druid.

Sources checked 2026-09-18:

* Druid: https://2e.aonprd.com/Classes.aspx?ID=34
* Tempest Surge: https://2e.aonprd.com/Spells.aspx?ID=1860
* Storm Born: https://2e.aonprd.com/Feats.aspx?ID=4712
* Animal Empathy: https://2e.aonprd.com/Feats.aspx?ID=4709
* Diplomacy: https://2e.aonprd.com/Skills.aspx?ID=39
* Clumsy: https://2e.aonprd.com/Conditions.aspx?ID=61
"""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from types import MappingProxyType

import pytest

import pf2e.content as content
from pf2e.content import get_definition, get_setup
from pf2e.encounter import Encounter
from pf2e.investigator import RecallKnowledge
from pf2e.investigator_content import GUARD_DOG_KNOWLEDGE
from pf2e.model import Cast, EndTurn, Position, RaiseShield, ResultStatus, Strike, Stride
from pf2e.spells import SPELLS
from pf2e.terminal import run_terminal
from terminal_test_helpers import BoundedInput, BoundedTranscript


def _settle_choices(game: Encounter, option_id: str = "keep") -> None:
    for _ in range(12):
        choice = game.inspect().choice
        if choice is None:
            return
        options = {option.option_id for option in choice.options}
        selected = option_id if option_id in options else choice.options[0].option_id
        result = game.choose(choice.choice_id, selected, choice.owner_actor_id)
        assert result.status in {ResultStatus.PAUSED, ResultStatus.COMPLETED}
    raise AssertionError("bounded choice settlement did not finish")


def _actor(game: Encounter, actor_id: str):
    return next(actor for actor in game.inspect().actors if actor.actor_id == actor_id)


@pytest.mark.parametrize(
    ("save_roll", "degree", "damage", "clumsy"),
    ((20, "CRITICAL_SUCCESS", 0, False), (12, "SUCCESS", 3, False),
     (11, "FAILURE", 7, True), (1, "CRITICAL_FAILURE", 14, True)),
)
def test_tempest_surge_uses_basic_reflex_and_failure_rider_at_every_degree(
    save_roll: int,
    degree: str,
    damage: int,
    clumsy: bool,
) -> None:
    game = Encounter.start(
        get_setup("storm_druid_tempest_save"), rolls=(10, 9, save_roll, 7)
    )
    _settle_choices(game)
    before = _actor(game, "druid")
    result = game.execute(Cast("tempest_surge", target_id="wizard_target"))
    assert result.status is ResultStatus.PAUSED
    assert result.inspection.choice is not None
    assert result.inspection.choice.kind == "spell_save_hero_reroll"
    finished = game.choose(
        result.inspection.choice.choice_id,
        "keep",
        result.inspection.choice.owner_actor_id,
    )

    save = next(event.check for event in finished.events if event.kind == "spell_save")
    packet = next(event.damage for event in finished.events if event.kind == "spell_damage")
    target = _actor(game, "wizard_target")
    after = _actor(game, "druid")
    assert save is not None and save.degree.name == degree
    assert packet is not None and packet.total == damage
    assert any(effect.kind == "clumsy" and effect.value == 2 for effect in target.condition_effects) is clumsy
    assert after.focus_points == before.focus_points - 1
    assert [(slot.slot_id, slot.spent) for slot in after.prepared_slots] == [
        (slot.slot_id, slot.spent) for slot in before.prepared_slots
    ]
    assert not any("persistent" in event.kind for event in finished.events)


def test_storm_born_bypasses_weather_but_dim_and_weapon_concealment_remain(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    weather = get_setup("storm_druid_weather")
    dim_weather = replace(
        weather,
        setup_id="review_storm_druid_dim_weather",
        name="Review Storm Druid in dim weather",
        ambient_light="dim",
    )
    monkeypatch.setattr(
        content,
        "_STAGED_SETUPS",
        MappingProxyType({**content._STAGED_SETUPS, dim_weather.setup_id: dim_weather}),
    )

    game = Encounter.start(dim_weather, rolls=(10, 9, 4))
    _settle_choices(game)
    assert _actor(game, "druid").initiative == 17  # Perception +7; weather -2 is ignored.
    spell = game.execute(Cast("tangle_vine", target_id="dog"))
    assert spell.status is ResultStatus.PAUSED
    assert spell.inspection.choice is not None
    assert spell.inspection.choice.kind == "concealment_hero_reroll"
    assert spell.events[-1].kind == "concealment_flat_check"

    weapon_game = Encounter.start(weather, rolls=(10, 9, 4))
    _settle_choices(weapon_game)
    assert weapon_game.execute(Stride((Position(2, 2), Position(3, 2)))).status is ResultStatus.COMPLETED
    weapon = weapon_game.execute(Strike("dog", attack_id="staff"))
    assert weapon.status is ResultStatus.PAUSED
    assert weapon.inspection.choice is not None
    assert weapon.inspection.choice.kind == "concealment_hero_reroll"
    assert [event.kind for event in weapon.events] == ["concealment_flat_check"]


def test_continuous_shield_tempest_refocus_prepare_save_and_next_scene(
    tmp_path: Path,
) -> None:
    game = Encounter.start(
        get_setup("storm_druid_vs_guard_dog"),
        rolls=(20, 1, 15, 4, 1, 4, 20, 1),
    )
    _settle_choices(game)
    initial_hp = _actor(game, "druid").max_hp

    assert game.execute(Stride((Position(2, 2), Position(3, 2)))).status is ResultStatus.COMPLETED
    assert game.execute(RaiseShield()).status is ResultStatus.COMPLETED
    assert game.execute(EndTurn()).status is ResultStatus.COMPLETED
    strike = game.execute(Strike("druid", attack_id="jaws"))
    assert strike.status is ResultStatus.PAUSED
    assert strike.inspection.choice is not None and strike.inspection.choice.kind == "shield_block"
    pending_path = tmp_path / "review-storm-shield-pending.json"
    game.save(pending_path)
    game = Encounter.load(pending_path)
    choice = game.inspect().choice
    assert choice is not None
    blocked = game.choose(choice.choice_id, "block", choice.owner_actor_id)
    record = next(event.shield_block for event in blocked.events if event.shield_block is not None)
    assert record is not None and (record.incoming_damage, record.hardness, record.damage_to_actor) == (5, 5, 0)
    assert _actor(game, "druid").hp == initial_hp

    assert game.execute(EndTurn()).status is ResultStatus.COMPLETED
    victory = game.execute(Cast("tempest_surge", target_id="dog"))
    assert victory.status is ResultStatus.COMPLETED
    assert victory.inspection.winner_team == "blue"
    assert _actor(game, "druid").hp == initial_hp

    before_refocus = game.inspect().world_time_seconds
    assert game.refocus("druid").status is ResultStatus.COMPLETED
    assert game.inspect().world_time_seconds == before_refocus + 600
    assert _actor(game, "druid").focus_points == 1
    assert game.record_rested(("druid",), day_number=2, elapsed_seconds=1).status is ResultStatus.COMPLETED
    choices = {
        "druid": {
            "druid_electric_arc": "electric_arc",
            "druid_guidance": "guidance",
            "druid_stabilize": "stabilize",
            "druid_tangle_vine": "tangle_vine",
            "druid_light": "light",
            "druid_heal_one": "runic_weapon",
            "druid_runic_weapon_two": "runic_weapon",
        }
    }
    assert game.daily_prepare(("druid",), choices).status is ResultStatus.COMPLETED
    assert [slot.spell_id for slot in _actor(game, "druid").prepared_slots if not slot.cantrip] == [
        "runic_weapon", "runic_weapon"
    ]

    day_two = tmp_path / "review-storm-day-two.json"
    game.save(day_two)
    game = Encounter.load(day_two)
    assert game.next_encounter(get_setup("storm_druid_next_guard_dog")).status in {
        ResultStatus.PAUSED,
        ResultStatus.COMPLETED,
    }
    _settle_choices(game)
    cast = game.execute(
        Cast("runic_weapon", item_id="druid:staff", slot_id="druid_heal_one")
    )
    assert cast.status is ResultStatus.COMPLETED
    assert any(event.kind == "item_effect_applied" for event in cast.events)
    rank_one = [slot for slot in _actor(game, "druid").prepared_slots if not slot.cantrip]
    assert [(slot.slot_id, slot.spent) for slot in rank_one] == [
        ("druid_heal_one", True), ("druid_runic_weapon_two", False)
    ]


def test_fixed_sheet_has_complete_legal_chassis_and_no_wizard_fiction() -> None:
    definition = get_definition("storm_druid_level_1")
    assert definition.hp == 8 + 8 + dict(definition.ability_modifiers)["constitution"]
    assert len(definition.prepared_spells) == 7
    assert sum(slot.cantrip for slot in definition.prepared_spells) == 5
    assert definition.focus_points == definition.focus_capacity == 1
    assert definition.spell_substitution_book_id is None
    assert not definition.spell_substitution_book
    assert "spell_substitution" not in definition.abilities
    assert definition.background == "Scholar"
    assert definition.land_speed_ft == 30
    assert {"shield_block", "wildsong", "voice_of_nature", "animal_empathy", "storm_born", "tempest_surge", "assurance_nature"} <= set(definition.abilities)
    assert {"academia_lore", "athletics", "society", "medicine", "nature", "acrobatics"} <= {
        skill for skill, _rank, _modifier in definition.skills
    }
    assert {"Fleet", "Natural Skill", "Assurance (Nature)", "Storm Born", "Animal Empathy"} <= set(definition.feats)
    assert {"Natural Medicine", "Additional Lore"}.isdisjoint(definition.feats)
    assert {"herbalism_lore", "mushroom_lore"}.isdisjoint(
        skill for skill, _rank, _modifier in definition.skills
    )
    assert sum(dict(definition.ability_modifiers).values()) == 9
    assert SPELLS["tempest_surge"].traits == frozenset(
        {"air", "concentrate", "druid", "electricity", "focus", "manipulate", "uncommon"}
    )


def test_scholar_assurance_nature_is_an_actual_druid_action_without_a_die() -> None:
    game = Encounter.start(get_setup("storm_druid_vs_guard_dog"), rolls=(20, 1))
    _settle_choices(game)
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


def test_bounded_terminal_casts_refocuses_and_selects_duplicate_druid_slots() -> None:
    transcript = BoundedTranscript(max_lines=500, max_chars=80_000)
    state = {"menu": "", "prompt": "", "phase": "cast"}

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
            phase = state["phase"]
            if phase == "cast":
                state["phase"] = "refocus"
                return choose("Cast")
            if phase == "refocus":
                state["phase"] = "rest"
                return choose("Refocus", prefix=True)
            if phase == "rest":
                state["phase"] = "prepare"
                return choose("Record Rested Eligibility")
            if phase == "prepare":
                state["phase"] = "quit"
                return choose("Daily Preparation")
            return choose("Quit")
        if prompt == "Spell number:":
            return choose("Tempest Surge", prefix=True)
        if prompt == "Casting mode:":
            return choose("2 actions")
        if prompt == "Target number:":
            return "1"
        if prompt == "Refocus actor number:":
            return "1"
        if prompt == "Actor numbers:":
            return "1"
        if prompt == "Declared preparation day:":
            return "2"
        if prompt == "Externally adjudicated elapsed seconds:":
            return "1"
        if prompt.startswith("Daily preparation ") and prompt.endswith(" spell:"):
            spell = {
                "druid_electric_arc": "Electric Arc",
                "druid_guidance": "Guidance",
                "druid_stabilize": "Stabilize",
                "druid_tangle_vine": "Tangle Vine",
                "druid_light": "Light",
                "druid_heal_one": "Runic Weapon",
                "druid_runic_weapon_two": "Runic Weapon",
            }[prompt.removeprefix("Daily preparation ").removesuffix(" spell:")]
            return choose(spell)
        raise AssertionError(f"unexpected terminal prompt: {prompt!r}")

    assert run_terminal(
        setup=get_setup("storm_druid_vs_guard_dog"),
        rolls=(20, 1, 1, 12),
        input_fn=BoundedInput(scripted_input, max_calls=50),
        output_fn=output,
    ) == 0
    rendered = "\n".join(transcript)
    assert "Rejected:" not in rendered, rendered
    assert "commits Tempest Surge" in rendered
    assert "Refocuses for 10 minutes and regains 1 Focus Point" in rendered
    assert "Daily preparation completed" in rendered
    assert rendered.count("Runic Weapon") >= 2


def test_animal_empathy_impression_then_saved_request_follows_actual_victory(
    tmp_path: Path,
) -> None:
    game = Encounter.start(
        get_setup("storm_druid_animal_empathy"),
        rolls=(20, 9, 8, 1, 4, 20, 14),
    )
    _settle_choices(game)
    victory = game.execute(Cast("tempest_surge", target_id="hostile_dog"))
    assert victory.status is ResultStatus.COMPLETED
    assert victory.inspection.winner_team == "blue"

    before = game.inspect().world_time_seconds
    rejected = game.animal_empathy("druid", "kennel_guide", action="request")
    assert rejected.status is ResultStatus.REJECTED
    assert game.inspect().world_time_seconds == before

    impressed = game.animal_empathy("druid", "kennel_guide", action="make_impression")
    assert impressed.status is ResultStatus.COMPLETED
    check = impressed.events[0].check
    assert check is not None and check.degree.name == "CRITICAL_SUCCESS"
    assert game.inspect().world_time_seconds == before + 60
    assert game._state.creatures["druid"].druid_animal_empathy_attitudes == {
        "kennel_guide": "helpful"
    }

    path = tmp_path / "review-animal-empathy-impression.json"
    game.save(path)
    game = Encounter.load(path)
    requested = game.animal_empathy("druid", "kennel_guide", action="request")
    assert requested.status is ResultStatus.COMPLETED
    request_check = requested.events[0].check
    assert request_check is not None and request_check.degree.name == "SUCCESS"
    assert "leads toward the kennel gate" in requested.events[0].text
    recalled = game.animal_empathy_result("druid", "kennel_guide")
    assert recalled.status is ResultStatus.COMPLETED
    assert "leads toward the kennel gate" in recalled.events[0].text
    assert "combat command" in requested.events[0].details[-1]


def test_animal_empathy_request_critical_failure_decreases_attitude() -> None:
    game = Encounter.start(
        get_setup("storm_druid_animal_empathy"),
        rolls=(20, 9, 8, 1, 4, 12, 1),
    )
    _settle_choices(game)
    assert game.execute(Cast("tempest_surge", target_id="hostile_dog")).status is ResultStatus.COMPLETED
    impression = game.animal_empathy("druid", "kennel_guide", action="make_impression")
    assert impression.status is ResultStatus.COMPLETED
    assert game._state.creatures["druid"].druid_animal_empathy_attitudes == {
        "kennel_guide": "friendly"
    }
    request = game.animal_empathy("druid", "kennel_guide", action="request")
    assert request.status is ResultStatus.COMPLETED
    assert request.events[0].check is not None
    assert request.events[0].check.degree.name == "CRITICAL_FAILURE"
    assert game._state.creatures["druid"].druid_animal_empathy_attitudes == {
        "kennel_guide": "indifferent"
    }
