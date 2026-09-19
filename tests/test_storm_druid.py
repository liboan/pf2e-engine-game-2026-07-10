from __future__ import annotations

from pathlib import Path

from pf2e.content import get_definition, get_setup
from pf2e.druid import preparation_choices, prepared_slot_rejection
from pf2e.spells import SPELLS
from pf2e.encounter import Encounter
from pf2e.investigator import RecallKnowledge
from pf2e.investigator_content import GUARD_DOG_KNOWLEDGE
from pf2e.model import Cast, EndTurn, Position, RaiseShield, ResultStatus, Strike, Stride
from pf2e.terminal import run_terminal
from terminal_test_helpers import BoundedInput, BoundedTranscript


def _finish_initial_choices(game: Encounter) -> None:
    while (choice := game.inspect().choice) is not None:
        assert game.choose(choice.choice_id, "keep", choice.owner_actor_id).status in {ResultStatus.COMPLETED, ResultStatus.PAUSED}


def test_tempest_surge_save_load_spends_focus_and_expires_clumsy_once(tmp_path: Path) -> None:
    game = Encounter.start(get_setup("storm_druid_tempest_save"), rolls=(10, 9, 7, 7))
    _finish_initial_choices(game)

    paused = game.execute(Cast("tempest_surge", target_id="wizard_target"))
    assert paused.status is ResultStatus.PAUSED
    assert paused.inspection.choice is not None
    assert paused.inspection.choice.kind == "spell_save_hero_reroll"
    assert game.inspect().actors[0].focus_points == 0
    assert all(slot.spent is False for slot in game.inspect().actors[0].prepared_slots if not slot.cantrip)

    path = tmp_path / "tempest-save.json"
    game.save(path)
    restored = Encounter.load(path)
    assert restored.inspect() == game.inspect()
    choice = restored.inspect().choice
    assert choice is not None
    resolved = restored.choose(choice.choice_id, "keep", choice.owner_actor_id)
    assert resolved.status is ResultStatus.COMPLETED
    target = next(actor for actor in restored.inspect().actors if actor.actor_id == "wizard_target")
    assert target.hp == 9
    assert any(effect.kind == "clumsy" and effect.value == 2 for effect in target.condition_effects)

    assert restored.execute(EndTurn()).status is ResultStatus.COMPLETED
    assert restored.execute(EndTurn()).status is ResultStatus.COMPLETED
    target = next(actor for actor in restored.inspect().actors if actor.actor_id == "wizard_target")
    assert not any(effect.kind == "clumsy" for effect in target.condition_effects)


def test_storm_druid_preparation_accepts_duplicate_rank_one_and_rejects_arcane_only_spell() -> None:
    definition = get_definition("storm_druid_level_1")
    assert (definition.hp, definition.ac, definition.land_speed_ft) == (18, 16, 30)
    assert definition.worn_items == ("leather_armor",)
    assert "Wildsong" in definition.languages
    assert dict(definition.ability_modifiers) == {
        "strength": 1, "dexterity": 2, "constitution": 2,
        "intelligence": 0, "wisdom": 4, "charisma": 0,
    }
    assert definition.attacks[0].damage_modifier == 1
    assert definition.background == "Scholar"
    assert {"Fleet", "Natural Skill", "Assurance (Nature)"}.issubset(definition.feats)
    assert "assurance_nature" in definition.abilities
    skills = {skill: modifier for skill, _rank, modifier in definition.skills}
    assert {"athletics", "society", "academia_lore"}.issubset(skills)
    assert "herbalism_lore" not in skills and "mushroom_lore" not in skills
    slot = definition.prepared_spells[-1]
    assert prepared_slot_rejection(None, definition, slot, "heal") is None
    assert prepared_slot_rejection(None, definition, slot, "runic_weapon") is None
    assert prepared_slot_rejection(None, definition, slot, "force_barrage") is not None
    assert SPELLS["tempest_surge"].traits == frozenset({"air", "concentrate", "druid", "electricity", "focus", "manipulate", "uncommon"})


def test_storm_druid_terminal_preparation_menu_allows_changed_duplicate_rank_one_choices() -> None:
    game = Encounter.start(get_setup("storm_druid_vs_guard_dog"), rolls=(10, 9))
    definition = get_definition("storm_druid_level_1")
    actor = game._state.creatures["druid"]
    assert preparation_choices(definition, actor.prepared_slots[0]) == (
        "electric_arc", "guidance", "stabilize", "tangle_vine", "light",
    )
    assert preparation_choices(definition, actor.prepared_slots[-1]) == ("heal", "runic_weapon")

    from pf2e.terminal import _choose_daily_preparations

    answers = iter(("2", "2", "2", "2", "2", "2", "2"))
    shown: list[str] = []
    choices = _choose_daily_preparations(game, ("druid",), lambda: next(answers), shown.append)
    assert choices == {"druid": {
        "druid_electric_arc": "guidance", "druid_guidance": "guidance",
        "druid_stabilize": "guidance", "druid_tangle_vine": "guidance",
        "druid_light": "guidance", "druid_heal_one": "runic_weapon",
        "druid_runic_weapon_two": "runic_weapon",
    }}
    assert sum("Runic Weapon" in line for line in shown) == 2


def test_storm_druid_assurance_nature_recall_knowledge_uses_no_die_or_hero_choice() -> None:
    game = Encounter.start(get_setup("storm_druid_vs_guard_dog"), rolls=(20, 1))
    _finish_initial_choices(game)
    dice_before = game._dice.to_data()
    result = game.execute(RecallKnowledge(
        "guard_dog", GUARD_DOG_KNOWLEDGE.question, "nature", "dog", use_assurance=True,
    ))
    assert result.status is ResultStatus.COMPLETED
    event = next(event for event in result.events if event.kind == "recall_knowledge")
    assert event.check is not None
    assert (event.check.method, event.check.die, event.check.total, event.check.modifier) == (
        "assurance", None, 13, 3,
    )
    assert game.inspect().choice is None and game._dice.to_data() == dice_before


def test_storm_born_removes_only_authored_weather_spell_penalty_and_concealment() -> None:
    game = Encounter.start(get_setup("storm_druid_weather"), rolls=(10, 9, 20, 4))
    _finish_initial_choices(game)
    assert game.target_is_concealed("druid", "dog")
    result = game.execute(Cast("tangle_vine", target_id="dog"))
    assert result.status is ResultStatus.PAUSED
    attack = next(event.check for event in result.events if event.kind == "spell_attack")
    assert attack is not None
    assert attack.modifier == 7
    assert all(event.kind != "concealment_flat_check" for event in result.events)


def test_storm_druid_wins_refocuses_changes_daily_choice_and_casts_in_next_scene(tmp_path: Path) -> None:
    game = Encounter.start(get_setup("storm_druid_vs_guard_dog"), rolls=(10, 9, 1, 12, 10, 9))
    _finish_initial_choices(game)
    victory = game.execute(Cast("tempest_surge", target_id="dog"))
    assert victory.status is ResultStatus.COMPLETED
    assert victory.inspection.winner_team == "blue"
    assert game.refocus("druid").status is ResultStatus.COMPLETED
    assert next(actor for actor in game.inspect().actors if actor.actor_id == "druid").focus_points == 1
    assert game.record_rested(("druid",), day_number=2, elapsed_seconds=1).status is ResultStatus.COMPLETED
    preparations = {"druid": {"druid_electric_arc": "electric_arc", "druid_guidance": "guidance", "druid_stabilize": "stabilize", "druid_tangle_vine": "tangle_vine", "druid_light": "light", "druid_heal_one": "runic_weapon", "druid_runic_weapon_two": "heal"}}
    assert game.daily_prepare(("druid",), preparations).status is ResultStatus.COMPLETED
    path = tmp_path / "storm-day-two.json"
    game.save(path)
    game = Encounter.load(path)
    assert game.next_encounter(get_setup("storm_druid_next_guard_dog")).status is ResultStatus.PAUSED
    _finish_initial_choices(game)
    cast = game.execute(Cast("runic_weapon", item_id="druid:staff", slot_id="druid_heal_one"))
    assert cast.status is ResultStatus.COMPLETED
    assert any(event.kind == "item_effect_applied" for event in cast.events)


def test_animal_empathy_uses_diplomacy_and_saves_the_authored_request_answer(tmp_path: Path) -> None:
    game = Encounter.start(get_setup("storm_druid_animal_empathy"), rolls=(10, 9, 8, 20, 20))
    _finish_initial_choices(game)
    game._state.in_progress = False  # Matches the existing authored social-scene test harness.
    game._state.creatures["hostile_dog"].hp = 0
    game._state.creatures["hostile_dog"].dead = True
    game._state.winner_team = "blue"
    for actor in game._state.creatures.values():
        actor.actions_remaining = 0
    rejected = game.animal_empathy("druid", "kennel_guide", action="request")
    assert rejected.status is ResultStatus.REJECTED
    result = game.animal_empathy("druid", "kennel_guide", action="make_impression")
    assert result.status is ResultStatus.COMPLETED
    event = result.events[0]
    assert event.check is not None and (event.check.total, event.check.dc) == (23, 15)
    assert any("wary but not coerced" in detail for detail in event.details)
    assert game.inspect().world_time_seconds == 60
    path = tmp_path / "animal-empathy.json"
    game.save(path)
    restored = Encounter.load(path)
    assert restored._state.creatures["druid"].druid_animal_empathy_attitudes == {"kennel_guide": "helpful"}
    requested = restored.animal_empathy("druid", "kennel_guide", action="request")
    assert requested.status is ResultStatus.COMPLETED
    assert restored.animal_empathy_result("druid", "kennel_guide").status is ResultStatus.COMPLETED


def test_animal_empathy_request_critical_failure_lowers_and_persists_attitude(tmp_path: Path) -> None:
    game = Encounter.start(get_setup("storm_druid_animal_empathy"), rolls=(10, 9, 8, 20, 1))
    _finish_initial_choices(game)
    game._state.in_progress = False
    game._state.creatures["hostile_dog"].hp = 0
    game._state.creatures["hostile_dog"].dead = True
    game._state.winner_team = "blue"
    for actor in game._state.creatures.values():
        actor.actions_remaining = 0
    assert game.animal_empathy("druid", "kennel_guide", action="make_impression").status is ResultStatus.COMPLETED
    failed_request = game.animal_empathy("druid", "kennel_guide", action="request")
    assert failed_request.status is ResultStatus.COMPLETED
    assert failed_request.events[0].check is not None
    assert failed_request.events[0].check.degree.name == "CRITICAL_FAILURE"
    assert "helpful → friendly" in failed_request.events[0].details[1]
    path = tmp_path / "animal-empathy-request-critical-failure.json"
    game.save(path)
    restored = Encounter.load(path)
    assert restored._state.creatures["druid"].druid_animal_empathy_attitudes == {"kennel_guide": "friendly"}


def test_bounded_terminal_selects_and_casts_tempest_surge() -> None:
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
            return choose("Tempest Surge", prefix=True)
        if prompt == "Casting mode:":
            return choose("2 actions")
        if prompt == "Target number:":
            return "1"
        raise AssertionError(f"unexpected terminal prompt: {prompt!r}")

    assert run_terminal(setup=get_setup("storm_druid_vs_guard_dog"), rolls=(20, 1, 1, 12), input_fn=BoundedInput(scripted_input, max_calls=35), output_fn=output) == 0
    rendered = "\n".join(transcript)
    assert "Rejected:" not in rendered, rendered
    assert "commits Tempest Surge" in rendered


def test_storm_druid_has_a_real_held_shield_block() -> None:
    game = Encounter.start(get_setup("storm_druid_vs_guard_dog"), rolls=(20, 1, 15, 4))
    _finish_initial_choices(game)
    assert game.execute(RaiseShield()).status is ResultStatus.COMPLETED
    assert game.execute(EndTurn()).status is ResultStatus.COMPLETED
    assert game.execute(Stride((Position(3, 2), Position(2, 2)))).status is ResultStatus.COMPLETED
    blocked = game.execute(Strike("druid", "jaws"))
    assert blocked.status is ResultStatus.PAUSED
    choice = blocked.inspection.choice
    assert choice is not None and choice.kind == "shield_block"
    resolved = game.choose(choice.choice_id, "block", choice.owner_actor_id)
    assert resolved.status is ResultStatus.COMPLETED
    druid = next(actor for actor in game.inspect().actors if actor.actor_id == "druid")
    assert druid.hp == 18
    assert druid.shields[0].instance_id == "druid:steel_shield"
