"""Public level-2 Forensic Investigator Medicine progression.

Sources checked 2026-09-19:

* https://2e.aonprd.com/Classes.aspx?ID=59
* https://2e.aonprd.com/Methodologies.aspx?ID=7
* https://2e.aonprd.com/Feats.aspx?ID=5121
* https://2e.aonprd.com/Actions.aspx?ID=2399
"""

from dataclasses import replace
from pathlib import Path

import pytest

import pf2e.content as content
from pf2e.content import get_definition, get_setup
from pf2e.encounter import Encounter
from pf2e.investigator import (
    ATTACK_STRATAGEM,
    BattleMedicine,
    DeviseStratagem,
    PERSON_OF_INTEREST_COOLDOWN_SECONDS,
    PERSON_OF_INTEREST_DURATION_SECONDS,
    PersonOfInterest,
    PersonOfInterestState,
    person_of_interest_grant_allows_free_devise,
    person_of_interest_target_ids,
    validate_person_of_interest_state,
)
from pf2e.investigator_content import FORENSIC_INVESTIGATOR_LEVEL_2
from pf2e.model import CreaturePlacement, EncounterSetup, EndTurn, Position, ResultStatus, Strike, Stride
from pf2e.terminal import run_terminal
from terminal_test_helpers import BoundedInput, BoundedTranscript


def _settle_initiative(game: Encounter) -> None:
    for _ in range(8):
        choice = game.inspect().choice
        if choice is None:
            return
        option_id = "keep" if any(option.option_id == "keep" for option in choice.options) else choice.options[0].option_id
        assert game.choose(choice.choice_id, option_id, choice.owner_actor_id).status in {
            ResultStatus.PAUSED,
            ResultStatus.COMPLETED,
        }
    raise AssertionError("initiative did not settle")


def test_l2_forensic_assurance_medicine_heals_real_damage_and_saves_immunity(
    tmp_path: Path,
) -> None:
    definition = get_definition(FORENSIC_INVESTIGATOR_LEVEL_2.definition_id)
    assert definition == FORENSIC_INVESTIGATOR_LEVEL_2
    assert (definition.level, definition.hp, definition.ac, definition.perception, definition.class_dc) == (2, 26, 18, 7, 18)
    assert ("medicine", "expert", 7) in definition.skills
    assert "Assurance (Medicine)" in definition.feats

    # Initiative gives the dog the first turn. It deals actual Strike damage;
    # the test does not alter the ally's HP directly.
    game = Encounter.start(
        get_setup("staged_investigator_forensic_level_2_assurance_medicine"),
        rolls=(1, 2, 20, 20, 4, 3, 4),
    )
    _settle_initiative(game)
    for actor in game._state.creatures.values():
        actor.hero_points = 0
    assert game.inspect().turn_actor_id == "healing_dog"
    assert game.execute(Stride((Position(3, 2),))).status is ResultStatus.COMPLETED
    assert game.execute(Strike("healing_ally", attack_id="jaws")).status is ResultStatus.COMPLETED
    injured = game._state.creatures["healing_ally"]
    assert injured.hp < 21

    assert game.execute(EndTurn()).status is ResultStatus.COMPLETED
    assert game.inspect().turn_actor_id == "forensic_investigator"
    healed = game.execute(BattleMedicine("healing_ally", use_assurance=True))
    assert healed.status is ResultStatus.COMPLETED
    check = next(event.check for event in healed.events if event.kind == "battle_medicine_check")
    assert check is not None
    assert (check.method, check.die, check.modifier, check.total, check.degree.name) == (
        "assurance", None, 6, 16, "SUCCESS",
    )
    healing = next(event for event in healed.events if event.kind == "battle_medicine")
    assert "2d8 3, 4 + 2 Forensic Medicine" in healing.text
    assert game._state.creatures["healing_ally"].hp == 20

    path = tmp_path / "l2-investigator-assurance-immunity.json"
    game.save(path)
    restored = Encounter.load(path)
    immunity = restored._state.condition_immunities
    assert len(immunity) == 1
    assert (immunity[0].kind, immunity[0].source_actor_id, immunity[0].target_actor_id, immunity[0].expires_at_seconds) == (
        "battle_medicine", "forensic_investigator", "healing_ally", 3600,
    )
    repeated = restored.execute(BattleMedicine("healing_ally", use_assurance=True))
    assert repeated.status is ResultStatus.REJECTED
    assert "immune" in repeated.message.lower()


def test_l2_assurance_intent_survives_a_saved_manipulate_reaction(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    reactor = replace(
        content.MELEE_FIGHTER_M,
        definition_id="l2_investigator_assurance_reactor",
        hero_points=0,
    )
    setup = EncounterSetup(
        "test_l2_investigator_assurance_reaction",
        "Level 2 Investigator Assurance through reaction",
        4,
        3,
        (
            CreaturePlacement(
                "forensic_investigator", FORENSIC_INVESTIGATOR_LEVEL_2.definition_id,
                "Level 2 Investigator", "blue", Position(1, 1),
            ),
            CreaturePlacement("healing_ally", content.GUARD_DOG.definition_id, "Healing Ally", "blue", Position(2, 1)),
            CreaturePlacement("reactive_fighter", reactor.definition_id, "Reactive Fighter", "red", Position(1, 2)),
        ),
    )
    monkeypatch.setattr(
        content, "_STAGED_CREATURES", content._STAGED_CREATURES | {reactor.definition_id: reactor},
    )
    monkeypatch.setattr(
        content, "_STAGED_SETUPS", content._STAGED_SETUPS | {setup.setup_id: setup},
    )
    game = Encounter.start(setup, rolls=(20, 1, 2, 3, 4))
    _settle_initiative(game)
    for actor in game._state.creatures.values():
        actor.hero_points = 0
    assert game.inspect().turn_actor_id == "forensic_investigator"
    game._state.creatures["healing_ally"].hp = 3

    started = game.execute(BattleMedicine("healing_ally", use_assurance=True))
    assert started.status is ResultStatus.PAUSED
    choice = started.inspection.choice
    assert choice is not None and choice.kind == "reaction"
    path = tmp_path / "l2-investigator-assurance-reaction.json"
    game.save(path)
    restored = Encounter.load(path)
    resumed = restored.choose(choice.choice_id, "decline", choice.owner_actor_id)
    assert resumed.status is ResultStatus.COMPLETED
    check = next(event.check for event in resumed.events if event.kind == "battle_medicine_check")
    assert check is not None and (check.method, check.die, check.total) == ("assurance", None, 16)


def test_l2_person_of_interest_selects_its_required_class_feat_and_target_predicate() -> None:
    definition = get_definition(FORENSIC_INVESTIGATOR_LEVEL_2.definition_id)
    assert "Person of Interest" in definition.feats
    assert "investigator_person_of_interest" in definition.abilities
    assert PERSON_OF_INTEREST_DURATION_SECONDS == 60
    assert PERSON_OF_INTEREST_COOLDOWN_SECONDS == 600

    # The predicate uses only the authored active-case awareness, matching
    # the feat's "to your knowledge" wording. It does not pretend every
    # creature in the scene is already tied to an investigation.
    game = Encounter.start(
        get_setup("staged_investigator_forensic_level_2_assurance_medicine"),
        rolls=(1, 2, 3),
    )
    actor = game._state.creatures["forensic_investigator"]
    assert person_of_interest_target_ids(game, game._state, actor, definition) == (
        "healing_ally", "healing_dog",
    )
    actor.investigator_awareness.add("healing_dog")
    assert person_of_interest_target_ids(game, game._state, actor, definition) == ("healing_ally",)

    grant = PersonOfInterestState("healing_dog", expires_at_seconds=60)
    validate_person_of_interest_state(grant)
    assert person_of_interest_grant_allows_free_devise(
        grant, target_id="healing_dog", now_seconds=59
    )
    assert not person_of_interest_grant_allows_free_devise(
        grant, target_id="healing_ally", now_seconds=59
    )
    assert not person_of_interest_grant_allows_free_devise(
        grant, target_id="healing_dog", now_seconds=60
    )
    with pytest.raises(ValueError, match="non-empty actor id"):
        validate_person_of_interest_state(PersonOfInterestState("", expires_at_seconds=60))


def test_l2_person_of_interest_saved_free_devise_strike_and_scene_recovery(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    game = Encounter.start(
        get_setup("staged_investigator_forensic_level_2_assurance_medicine"),
        rolls=(20, 1, 1, 20, 6, 6, 20, 1, 1),
    )
    _settle_initiative(game)
    assert game.inspect().turn_actor_id == "forensic_investigator"
    assert game.execute(PersonOfInterest("healing_dog")).status is ResultStatus.COMPLETED
    actor = game._state.creatures["forensic_investigator"]
    assert actor.actions_remaining == 2
    assert actor.investigator_person_of_interest is not None

    path = tmp_path / "l2-person-of-interest-before-devise.json"
    game.save(path)
    restored = Encounter.load(path)
    assert restored.execute(DeviseStratagem("healing_ally", free_action=True)).status is ResultStatus.REJECTED
    assert restored.execute(Stride((Position(2, 0), Position(3, 1)))).status is ResultStatus.COMPLETED
    devised = restored.execute(
        DeviseStratagem("healing_dog", mode=ATTACK_STRATAGEM, free_action=True)
    )
    assert devised.status is ResultStatus.COMPLETED
    assert restored._state.creatures["forensic_investigator"].actions_remaining == 1
    strike = restored.execute(
        Strike("healing_dog", attack_id="shortsword", use_intelligence=True)
    )
    assert strike.status is ResultStatus.COMPLETED
    attack = next(event.check for event in strike.events if event.kind == "strike")
    assert attack is not None and (attack.die, attack.total, attack.degree.name) == (20, 28, "CRITICAL_SUCCESS")
    assert restored._state.creatures["healing_dog"].defeated
    assert not restored._state.in_progress and restored._state.winner_team == "blue"

    base = get_setup("staged_investigator_forensic_level_2_assurance_medicine")
    next_setup = replace(
        base,
        setup_id="l2_investigator_person_of_interest_recovery",
        placements=tuple(
            placement if placement.actor_id != "healing_dog" else replace(
                placement, actor_id="fresh_healing_dog"
            )
            for placement in base.placements
        ),
    )
    monkeypatch.setattr(
        content,
        "_STAGED_SETUPS",
        content._STAGED_SETUPS | {next_setup.setup_id: next_setup},
    )
    transitioned = restored.next_encounter(next_setup)
    assert transitioned.status in {ResultStatus.COMPLETED, ResultStatus.PAUSED}
    _settle_initiative(restored)
    assert restored.inspect().turn_actor_id == "forensic_investigator"
    carried = restored._state.creatures["forensic_investigator"]
    assert carried.investigator_person_of_interest is not None
    assert carried.investigator_person_of_interest.target_id == "healing_dog"
    restored._advance_elapsed_time(restored._state, 60)
    assert carried.investigator_person_of_interest is None
    assert carried.investigator_person_of_interest_cooldown_until == 600
    assert "person_of_interest" not in restored.options().available_actions
    restored._advance_elapsed_time(restored._state, 540)
    assert "person_of_interest" in restored.options().available_actions


def test_terminal_selects_l2_person_of_interest() -> None:
    transcript = BoundedTranscript()
    menu = {"text": "", "prompt": ""}

    def output(line: str) -> None:
        transcript.append(line)
        if line.startswith("1. "):
            menu["text"] = line
        if line.endswith(":"):
            menu["prompt"] = line

    def menu_number(label: str) -> str:
        for row in menu["text"].splitlines():
            if ". " in row and row.split(". ", 1)[1] == label:
                return row.split(". ", 1)[0]
        raise AssertionError(f"missing terminal menu item {label!r}: {menu['text']!r}")

    def script() -> str:
        if menu["prompt"] == "Choice prompt action:":
            return menu_number("Resolve this choice")
        if menu["prompt"] == "Choice option number:":
            return menu_number("Keep initiative")
        if menu["prompt"] == "Choice:":
            if "Person of Interest" in menu["text"]:
                return menu_number("Person of Interest")
            return menu_number("Quit")
        if menu["prompt"] == "Target number:":
            return "2"
        raise AssertionError(f"unexpected terminal prompt: {menu['prompt']!r}")

    assert run_terminal(
        setup=get_setup("staged_investigator_forensic_level_2_assurance_medicine"),
        rolls=(20, 1, 1),
        input_fn=BoundedInput(script, max_calls=20),
        output_fn=output,
    ) == 0
    rendered = "\n".join(transcript)
    assert "Person of Interest target:" in rendered
    assert "marks Guard Dog as a Person of Interest" in rendered
