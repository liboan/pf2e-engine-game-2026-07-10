"""Public authored Recall Knowledge and Known Weaknesses coverage.

Sources checked 2026-09-16:

* https://2e.aonprd.com/Actions.aspx?ID=2367
* https://2e.aonprd.com/Rules.aspx?ID=2638
* https://2e.aonprd.com/Feats.aspx?ID=5936
* https://2e.aonprd.com/Actions.aspx?ID=2813
* https://2e.aonprd.com/Rules.aspx?ID=2263
"""

from dataclasses import replace
from pathlib import Path
import re

import pytest

import pf2e.content as content
from pf2e.encounter import Encounter
from pf2e.investigator import ATTACK_STRATAGEM, DeviseStratagem, RecallKnowledge
from pf2e.investigator_content import (
    FORENSIC_INVESTIGATOR_HEALING_SETUP,
    FORENSIC_INVESTIGATOR_VS_TWO_DOGS,
    GUARD_DOG_KNOWLEDGE,
)
from pf2e.model import EndTurn, Position, ResultStatus, Strike, Stride
from pf2e.terminal import run_terminal
from terminal_test_helpers import BoundedInput, BoundedTranscript


def _choose_keep(game: Encounter):
    choice = game.inspect().choice
    assert choice is not None
    result = game.choose(choice.choice_id, "keep", choice.owner_actor_id)
    assert result.status in {ResultStatus.COMPLETED, ResultStatus.PAUSED}
    return result


def _investigator_game(setup, monkeypatch: pytest.MonkeyPatch, *rolls: int) -> Encounter:
    monkeypatch.setattr(
        content,
        "SETUPS",
        content.SETUPS | {setup.setup_id: setup},
    )
    game = Encounter.start(setup, rolls=rolls)
    for _ in range(8):
        if game.inspect().choice is None:
            break
        _choose_keep(game)
    assert game.inspect().turn_actor_id == "forensic_investigator"
    return game


def test_public_recall_knowledge_hero_choice_save_load_answer_and_history(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    game = _investigator_game(
        FORENSIC_INVESTIGATOR_VS_TWO_DOGS,
        monkeypatch,
        20, 1, 2, 14,
    )
    started = game.execute(
        RecallKnowledge(
            subject_key="guard_dog",
            question=GUARD_DOG_KNOWLEDGE.question,
            skill="society",
            target_id="investigator_guard_dog_a",
        )
    )
    assert started.status is ResultStatus.PAUSED
    assert game.inspect().choice is not None
    assert game._state.creatures["forensic_investigator"].actions_remaining == 2
    assert game._state.creatures["forensic_investigator"].investigator_knowledge_attempts == {}

    pending_path = tmp_path / "recall-knowledge-pending.json"
    game.save(pending_path)
    game = Encounter.load(pending_path)
    resolved = _choose_keep(game)
    check_event = next(event for event in resolved.events if event.kind == "recall_knowledge")
    assert check_event.check is not None
    assert (check_event.check.die, check_event.check.total, check_event.check.dc) == (14, 21, 16)
    assert set(check_event.check.traits) == {"secret", "skill"}
    assert GUARD_DOG_KNOWLEDGE.answer in check_event.text
    assert game._state.creatures["forensic_investigator"].investigator_knowledge_attempts == {
        "guard_dog": 1
    }

    final_path = tmp_path / "recall-knowledge-final.json"
    game.save(final_path)
    restored = Encounter.load(final_path)
    assert restored._state.creatures["forensic_investigator"].investigator_knowledge_attempts == {
        "guard_dog": 1
    }
    assert restored._state.pending_choice is None


def test_recall_knowledge_hero_reroll_finalizes_replacement_before_history(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    game = _investigator_game(
        FORENSIC_INVESTIGATOR_VS_TWO_DOGS,
        monkeypatch,
        20, 1, 2, 1, 20,
    )
    started = game.execute(
        RecallKnowledge("guard_dog", GUARD_DOG_KNOWLEDGE.question, "society", "investigator_guard_dog_a")
    )
    assert started.status is ResultStatus.PAUSED
    choice = game.inspect().choice
    assert choice is not None
    rerolled = game.choose(choice.choice_id, "reroll", choice.owner_actor_id)
    assert rerolled.status is ResultStatus.COMPLETED
    event = next(item for item in rerolled.events if item.kind == "recall_knowledge")
    assert event.check is not None
    assert (event.check.die, event.check.total, event.check.degree.name) == (20, 27, "CRITICAL_SUCCESS")
    assert game._state.creatures["forensic_investigator"].hero_points == 0
    assert game._state.creatures["forensic_investigator"].investigator_knowledge_attempts == {
        "guard_dog": 1
    }


def test_recall_knowledge_uses_authored_successive_dcs_and_exhausts_subject(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Society +7 reaches the authored DC 16, 18, then 20 stages.
    game = _investigator_game(
        FORENSIC_INVESTIGATOR_VS_TWO_DOGS,
        monkeypatch,
        20, 1, 2, 9, 11, 13,
    )
    for expected_dc in (16, 18, 20):
        result = game.execute(
            RecallKnowledge(
                subject_key="guard_dog",
                question=GUARD_DOG_KNOWLEDGE.question,
                skill="society",
                target_id="investigator_guard_dog_a",
            )
        )
        assert result.status is ResultStatus.PAUSED
        result = _choose_keep(game)
        event = next(item for item in result.events if item.kind == "recall_knowledge")
        assert event.check is not None and event.check.dc == expected_dc
    actor = game._state.creatures["forensic_investigator"]
    assert actor.investigator_knowledge_attempts == {"guard_dog": 3}
    assert actor.investigator_knowledge_exhausted == {"guard_dog"}

    while game.inspect().turn_actor_id != "forensic_investigator":
        assert game.execute(EndTurn()).status is ResultStatus.COMPLETED
    before_actions = actor.actions_remaining
    before_dice = game._dice.to_data()
    rejected = game.execute(
        RecallKnowledge("guard_dog", GUARD_DOG_KNOWLEDGE.question, "society", "investigator_guard_dog_a")
    )
    assert rejected.status is ResultStatus.REJECTED
    assert actor.actions_remaining == before_actions
    assert game._dice.to_data() == before_dice


@pytest.mark.parametrize(
    "check_die,expected_degree",
    ((1, "CRITICAL_FAILURE"), (5, "FAILURE")),
)
def test_recall_knowledge_failure_returns_no_information_and_exhausts_atomically(
    monkeypatch: pytest.MonkeyPatch, check_die: int, expected_degree: str,
) -> None:
    game = _investigator_game(
        FORENSIC_INVESTIGATOR_VS_TWO_DOGS,
        monkeypatch,
        20, 1, 2, check_die,
    )
    result = game.execute(
        RecallKnowledge("guard_dog", GUARD_DOG_KNOWLEDGE.question, "society", "investigator_guard_dog_a")
    )
    assert result.status is ResultStatus.PAUSED
    result = _choose_keep(game)
    event = next(item for item in result.events if item.kind == "recall_knowledge")
    assert event.check is not None and event.check.degree.name == expected_degree
    assert GUARD_DOG_KNOWLEDGE.answer not in event.text
    assert any(item.kind == "recall_knowledge_no_information" for item in result.events)
    actor = game._state.creatures["forensic_investigator"]
    assert actor.investigator_knowledge_attempts == {"guard_dog": 1}
    assert actor.investigator_knowledge_exhausted == {"guard_dog"}


def test_authored_recall_knowledge_is_shared_with_another_supported_actor(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    game = _investigator_game(
        FORENSIC_INVESTIGATOR_HEALING_SETUP,
        monkeypatch,
        20, 1, 2, 12,
    )
    assert game.execute(EndTurn()).status is ResultStatus.COMPLETED
    assert game.execute(EndTurn()).status is ResultStatus.COMPLETED
    assert game.inspect().turn_actor_id == "healing_ally"
    assert game.options().recall_knowledge_targets == ("healing_dog",)
    result = game.execute(
        RecallKnowledge(
            subject_key="guard_dog",
            question=GUARD_DOG_KNOWLEDGE.question,
            skill="society",
            target_id="healing_dog",
        )
    )
    assert result.status is ResultStatus.PAUSED
    result = _choose_keep(game)
    event = next(item for item in result.events if item.kind == "recall_knowledge")
    assert event.check is not None and event.check.total == 15


def test_recall_knowledge_attempt_history_survives_next_encounter(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    setup = FORENSIC_INVESTIGATOR_VS_TWO_DOGS
    game = _investigator_game(setup, monkeypatch, 20, 1, 2, 14, 20, 1, 2)
    assert game.execute(
        RecallKnowledge("guard_dog", GUARD_DOG_KNOWLEDGE.question, "society", "investigator_guard_dog_a")
    ).status is ResultStatus.PAUSED
    _choose_keep(game)
    actor = game._state.creatures["forensic_investigator"]
    assert actor.investigator_knowledge_attempts == {"guard_dog": 1}

    # Finish the authored scene and carry the party through the existing
    # next_encounter API. Opponents get fresh actor ids; the PC identity and
    # authored subject key remain the same.
    for actor_id in ("investigator_guard_dog_a", "investigator_guard_dog_b"):
        game._state.creatures[actor_id].hp = 0
    game._state.in_progress = False
    game._state.winner_team = "blue"
    next_setup = replace(
        setup,
        setup_id="investigator_forensic_knowledge_next_scene",
        name="Forensic Investigator knowledge next scene",
        placements=tuple(
            replace(
                placement,
                actor_id={
                    "investigator_guard_dog_a": "next_guard_dog_a",
                    "investigator_guard_dog_b": "next_guard_dog_b",
                }.get(placement.actor_id, placement.actor_id),
            )
            for placement in setup.placements
        ),
    )
    monkeypatch.setattr(
        content,
        "_STAGED_SETUPS",
        content._STAGED_SETUPS | {next_setup.setup_id: next_setup},
    )
    transitioned = game.next_encounter(next_setup)
    assert transitioned.status is ResultStatus.PAUSED
    assert game._state.creatures["forensic_investigator"].investigator_knowledge_attempts == {
        "guard_dog": 1
    }


def test_known_weaknesses_orders_knowledge_before_devise_and_grants_targeted_ally_bonus(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    knowledge = replace(GUARD_DOG_KNOWLEDGE, communication_recipients=("healing_ally",))
    setup = replace(FORENSIC_INVESTIGATOR_HEALING_SETUP, knowledge=(knowledge,))
    game = _investigator_game(setup, monkeypatch, 20, 1, 2, 20, 14, 5, 4)
    started = game.execute(
        DeviseStratagem("healing_dog", mode=ATTACK_STRATAGEM, known_weaknesses=True)
    )
    assert started.status is ResultStatus.PAUSED
    assert game._state.creatures["forensic_investigator"].investigator_stratagem is None
    assert game._state.investigator_weakness_bonuses == []

    pending_path = tmp_path / "known-weaknesses-pending.json"
    game.save(pending_path)
    game = Encounter.load(pending_path)
    resolved = _choose_keep(game)
    kinds = [event.kind for event in resolved.events]
    assert kinds.index("recall_knowledge") < kinds.index("known_weaknesses") < kinds.index("devise_stratagem")
    assert resolved.events[-1].kind == "devise_stratagem"
    stratagem = game._state.creatures["forensic_investigator"].investigator_stratagem
    assert stratagem is not None and stratagem.die == 14
    assert game._state.creatures["forensic_investigator"].actions_remaining == 2
    bonuses = game._state.investigator_weakness_bonuses
    assert {(bonus.source_actor_id, bonus.target_actor_id, bonus.recipient_actor_id) for bonus in bonuses} == {
        ("forensic_investigator", "healing_dog", "forensic_investigator"),
        ("forensic_investigator", "healing_dog", "healing_ally"),
    }

    final_path = tmp_path / "known-weaknesses-final.json"
    game.save(final_path)
    game = Encounter.load(final_path)
    assert game.execute(EndTurn()).status is ResultStatus.COMPLETED
    assert game.execute(EndTurn()).status is ResultStatus.COMPLETED
    assert game.inspect().turn_actor_id == "healing_ally"
    assert game.execute(Stride((Position(3, 1),))).status is ResultStatus.COMPLETED
    ally_attack = game.execute(Strike("healing_dog", attack_id="longsword"))
    assert ally_attack.status is ResultStatus.PAUSED
    ally_check = next(event.check for event in ally_attack.events if event.kind == "strike")
    assert ally_check is not None
    assert any(item.source == "Known Weaknesses" and item.amount == 1 for item in ally_check.modifier_breakdown)
    assert not any(
        bonus.recipient_actor_id == "healing_ally"
        for bonus in game._state.investigator_weakness_bonuses
    )
    resolved_attack = _choose_keep(game)
    assert resolved_attack.status is ResultStatus.COMPLETED
    assert not game.inspect().in_progress
    assert game.inspect().winner_team == "blue"


def test_known_weaknesses_bonus_expires_at_investigator_next_turn_start(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    knowledge = replace(GUARD_DOG_KNOWLEDGE, communication_recipients=("healing_ally",))
    setup = replace(FORENSIC_INVESTIGATOR_HEALING_SETUP, knowledge=(knowledge,))
    game = _investigator_game(setup, monkeypatch, 20, 1, 2, 20, 14)
    assert game.execute(DeviseStratagem("healing_dog", mode=ATTACK_STRATAGEM, known_weaknesses=True)).status is ResultStatus.PAUSED
    _choose_keep(game)
    assert game._state.investigator_weakness_bonuses

    # Skip the rest of the Investigator turn, the dog turn, and the ally turn.
    assert game.execute(EndTurn()).status is ResultStatus.COMPLETED
    assert game.execute(EndTurn()).status is ResultStatus.COMPLETED
    assert game.execute(EndTurn()).status is ResultStatus.COMPLETED
    assert game.inspect().turn_actor_id == "forensic_investigator"
    assert game._state.investigator_weakness_bonuses == []


@pytest.mark.parametrize(
    "command",
    (
        RecallKnowledge("missing", target_id="investigator_guard_dog_a", skill="society"),
        RecallKnowledge("guard_dog", target_id="investigator_guard_dog_a", skill="arcana"),
        RecallKnowledge("guard_dog", question="not the authored question", target_id="investigator_guard_dog_a", skill="society"),
    ),
)
def test_invalid_recall_knowledge_requests_are_atomic(
    monkeypatch: pytest.MonkeyPatch, command: RecallKnowledge,
) -> None:
    game = _investigator_game(
        FORENSIC_INVESTIGATOR_VS_TWO_DOGS,
        monkeypatch,
        20, 1, 2, 14,
    )
    actor = game._state.creatures["forensic_investigator"]
    before_actions = actor.actions_remaining
    before_attempts = dict(actor.investigator_knowledge_attempts)
    before_dice = game._dice.to_data()
    rejected = game.execute(command)
    assert rejected.status is ResultStatus.REJECTED
    assert actor.actions_remaining == before_actions
    assert actor.investigator_knowledge_attempts == before_attempts
    assert game._dice.to_data() == before_dice


def test_terminal_exposes_authored_recall_knowledge_action_and_answer() -> None:
    transcript = BoundedTranscript(max_lines=500, max_chars=100_000)

    def next_input() -> str:
        joined = "\n".join(transcript)
        prompt = transcript[-1] if transcript else ""
        if prompt == "Choice prompt action:":
            return "2"  # resolve initiative or the knowledge Hero choice
        if prompt == "Choice option number:":
            recent = "\n".join(transcript[-15:])
            return "2" if "Keep the current result" in recent else "1"  # keep initiative, then keep knowledge result
        if prompt == "Target number:":
            return "1"
        if prompt == "Recall Knowledge skill:":
            return "1"
        if prompt == "Choice:":
            if GUARD_DOG_KNOWLEDGE.answer in joined:
                matches = re.findall(r"(?m)^(\d+)\. Quit$", joined)
                if matches:
                    return matches[-1]
            matches = re.findall(r"(?m)^(\d+)\. Recall Knowledge$", joined)
            if matches:
                return matches[-1]
            matches = re.findall(r"(?m)^(\d+)\. Quit$", joined)
            if matches:
                return matches[-1]
        raise AssertionError(f"unexpected terminal prompt: {prompt!r}\n{joined}")

    bounded = BoundedInput(next_input, max_calls=40, describe=lambda: transcript[-1] if transcript else "")
    status = run_terminal(
        setup=content.get_setup("investigator_forensic_vs_two_guard_dogs"),
        rolls=(20, 1, 2, 14),
        input_fn=bounded,
        output_fn=transcript.append,
    )
    assert status == 0
    assert bounded.calls < 40
    joined = "\n".join(transcript)
    assert "Recall Knowledge" in joined
    assert GUARD_DOG_KNOWLEDGE.answer in joined


def test_terminal_exposes_known_weaknesses_embedded_devise_path() -> None:
    transcript = BoundedTranscript(max_lines=500, max_chars=100_000)

    def next_input() -> str:
        joined = "\n".join(transcript)
        prompt = transcript[-1] if transcript else ""
        if prompt == "Choice prompt action:":
            return "2"
        if prompt == "Choice option number:":
            recent = "\n".join(transcript[-15:])
            return "2" if "Keep the current result" in recent else "1"
        if prompt == "Target number:":
            return "1"
        if prompt == "Choice:":
            if GUARD_DOG_KNOWLEDGE.answer in joined:
                matches = re.findall(r"(?m)^(\d+)\. Quit$", joined)
                if matches:
                    return matches[-1]
            matches = re.findall(r"(?m)^(\d+)\. Known Weaknesses \+ Devise$", joined)
            if matches:
                return matches[-1]
            matches = re.findall(r"(?m)^(\d+)\. Quit$", joined)
            if matches:
                return matches[-1]
        raise AssertionError(f"unexpected terminal prompt: {prompt!r}")

    bounded = BoundedInput(next_input, max_calls=40, describe=lambda: transcript[-1] if transcript else "")
    status = run_terminal(
        setup=content.get_setup("investigator_forensic_vs_two_guard_dogs"),
        rolls=(20, 1, 2, 20, 14),
        input_fn=bounded,
        output_fn=transcript.append,
    )
    assert status == 0
    assert bounded.calls < 40
    joined = "\n".join(transcript)
    assert "Known Weaknesses" in joined
    assert "after Known Weaknesses" in joined
    assert "preliminary d20 is 14" in joined
