"""Public Skill Stratagem checks for the selected Forensic Investigator.

Rules references:
* https://2e.aonprd.com/Classes.aspx?ID=59
* https://2e.aonprd.com/Actions.aspx?ID=2813

Those sources require the d20 before selecting attack or skill, prohibit
Strikes against the selected creature for Skill Stratagem's duration, and
grant its next relevant mental skill or Perception check a circumstance
benefit.  A Pursue a Lead bonus becomes +2 instead of stacking another +1.
"""

from pf2e.content import get_setup
from pf2e.encounter import Encounter
from pf2e.investigator import DeviseStratagem, InvestigationCheck, RecallKnowledge
from pf2e.model import Choose, EndTurn, ResultStatus, Strike
from pf2e.terminal import run_terminal
from terminal_test_helpers import BoundedInput, BoundedTranscript


TARGET = "investigator_guard_dog_a"
OTHER_TARGET = "investigator_guard_dog_b"
INVESTIGATOR = "forensic_investigator"


def _game(*, rolls: tuple[int, ...] = (20, 1, 2, 14, 11, 12, 13)) -> Encounter:
    game = Encounter.start(get_setup("investigator_forensic_vs_two_guard_dogs"), rolls=rolls)
    while game.inspect().choice is not None:
        choice = game.inspect().choice
        assert choice is not None and choice.kind == "initiative_hero_reroll"
        assert game.execute(Choose(choice.choice_id, "keep", choice.owner_actor_id)).status is ResultStatus.COMPLETED
    assert game.inspect().turn_actor_id == INVESTIGATOR
    return game


def _choose_skill(game: Encounter) -> None:
    choice = game.inspect().choice
    assert choice is not None
    assert choice.kind == "family_action"
    assert tuple(option.option_id for option in choice.options) == ("attack", "skill")
    selected = game.execute(Choose(choice.choice_id, "skill", choice.owner_actor_id))
    assert selected.status is ResultStatus.COMPLETED


def test_skill_stratagem_rolls_then_offers_a_saved_mode_choice(tmp_path) -> None:
    game = _game()

    opened = game.execute(DeviseStratagem(TARGET))

    assert opened.status is ResultStatus.PAUSED
    assert any("preliminary d20 is 14" in event.text for event in opened.events)
    path = tmp_path / "skill-stratagem-mode.json"
    game.save(path)
    loaded = Encounter.load(path)
    _choose_skill(loaded)
    state = loaded._state.creatures[INVESTIGATOR].investigator_stratagem
    assert state is not None and state.mode == "skill" and state.die == 14


def test_skill_stratagem_raises_lead_bonus_consumes_once_and_keeps_strike_lockout() -> None:
    game = _game()
    investigator = game._state.creatures[INVESTIGATOR]
    investigator.investigator_active_cases = {"guard_dog_case"}
    investigator.investigator_awareness = {TARGET}

    assert game.execute(DeviseStratagem(TARGET)).status is ResultStatus.PAUSED
    _choose_skill(game)
    assert all(TARGET not in strike.targets for strike in game.options().strikes)
    check = game.execute(InvestigationCheck("guard_dog_handler_marks", target_id=TARGET))

    assert check.status is ResultStatus.COMPLETED
    check_event = next(event for event in check.events if event.kind == "investigation_check")
    assert check_event.check is not None and check_event.check.modifier == 9
    assert any(
        modifier.modifier_type == "circumstance"
        and modifier.source == "Pursue a Lead (Skill Stratagem)"
        and modifier.amount == 2
        for modifier in check_event.check.modifier_breakdown
    )
    stored = game._state.creatures[INVESTIGATOR].investigator_stratagem
    assert stored is not None and stored.consumed

    blocked = game.execute(Strike(TARGET, attack_id="shortsword"))
    assert blocked.status is ResultStatus.REJECTED
    assert "Skill Stratagem" in blocked.message

    assert game.execute(EndTurn()).status is ResultStatus.COMPLETED
    assert game.execute(EndTurn()).status is ResultStatus.COMPLETED
    assert game.execute(EndTurn()).status is ResultStatus.COMPLETED
    assert game.inspect().turn_actor_id == INVESTIGATOR
    assert game._state.creatures[INVESTIGATOR].investigator_stratagem is None
    assert game.execute(Strike(TARGET, attack_id="shortsword")).status is not ResultStatus.REJECTED


def test_skill_stratagem_wrong_target_mental_check_preserves_its_bonus() -> None:
    game = _game(rolls=(20, 1, 2, 14, 11, 12, 13, 14))

    assert game.execute(DeviseStratagem(OTHER_TARGET)).status is ResultStatus.PAUSED
    _choose_skill(game)
    knowledge = game.execute(RecallKnowledge("guard_dog", skill="society", target_id=TARGET))
    assert knowledge.status is ResultStatus.PAUSED
    choice = game.inspect().choice
    assert choice is not None and choice.kind == "family_action"
    assert game.execute(Choose(choice.choice_id, "keep", choice.owner_actor_id)).status is ResultStatus.COMPLETED

    stored = game._state.creatures[INVESTIGATOR].investigator_stratagem
    assert stored is not None and stored.mode == "skill" and not stored.consumed


def test_known_weaknesses_embedded_check_precedes_skill_stratagem() -> None:
    game = _game(rolls=(20, 1, 2, 14, 11, 12, 13))

    opened = game.execute(DeviseStratagem(TARGET, known_weaknesses=True))
    assert opened.status is ResultStatus.PAUSED
    knowledge_choice = game.inspect().choice
    assert knowledge_choice is not None
    resolved = game.execute(Choose(knowledge_choice.choice_id, "keep", knowledge_choice.owner_actor_id))

    assert resolved.status is ResultStatus.PAUSED
    knowledge = next(event for event in resolved.events if event.kind == "recall_knowledge")
    assert knowledge.check is not None
    assert not any(
        modifier.source in {"Skill Stratagem", "Pursue a Lead (Skill Stratagem)"}
        for modifier in knowledge.check.modifier_breakdown
    )
    _choose_skill(game)


def test_terminal_offers_and_selects_skill_stratagem_with_bounded_input(tmp_path) -> None:
    inputs = iter((
        "2", "1",  # initiative Hero Point prompt, then keep
        "5", "2",  # Devise a Stratagem, Guard Dog A
        "2", "2",  # resolve the stored-die choice as Skill Stratagem
        "17",       # quit from the ordinary action menu
    ))
    output = BoundedTranscript(max_lines=400, max_chars=100_000)
    bounded_input = BoundedInput(lambda: next(inputs), max_calls=20)

    status = run_terminal(
        setup=get_setup("investigator_forensic_vs_two_guard_dogs"),
        rolls=(20, 1, 2, 14, 11),
        save_path=tmp_path / "skill-stratagem-terminal.json",
        input_fn=bounded_input,
        output_fn=output.append,
    )

    transcript = "\n".join(output)
    assert status == 0
    assert bounded_input.calls == 7
    assert "Choose an attack or skill stratagem" in transcript
    assert "Skill Stratagem" in transcript
