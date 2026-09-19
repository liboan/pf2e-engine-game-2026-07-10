from pf2e.content import get_definition, get_setup
from pf2e.encounter import Encounter
from pf2e.investigator import RecallKnowledge
from pf2e.investigator_content import GUARD_DOG_KNOWLEDGE
from pf2e.model import Cast, Dismiss, EndTurn, Flee, Position, ResultStatus, Strike, Stride
from pf2e.terminal import run_terminal
from terminal_test_helpers import BoundedInput, BoundedTranscript


def _settle(game: Encounter) -> None:
    while game.inspect().choice is not None:
        choice = game.inspect().choice
        assert choice is not None
        assert game.choose(choice.choice_id, "keep", choice.owner_actor_id).status in {ResultStatus.COMPLETED, ResultStatus.PAUSED}


def test_life_oracle_nudge_curse_cap_is_atomic_and_round_trips(tmp_path) -> None:
    game = Encounter.start(get_setup("staged_life_oracle_nudge"), rolls=(1, 20, 20, 4))
    _settle(game)
    assert game.inspect().turn_actor_id == "dog"
    assert game.execute(Stride((Position(3, 2), Position(2, 2)))).status is ResultStatus.COMPLETED
    assert game.execute(Strike("oracle", "jaws")).status is ResultStatus.COMPLETED
    assert game.execute(EndTurn()).status is ResultStatus.COMPLETED
    oracle = next(actor for actor in game.inspect().actors if actor.actor_id == "oracle")
    assert oracle.hp < oracle.max_hp
    assert game.nudge_the_scales("oracle", "oracle").status is ResultStatus.COMPLETED
    assert game.nudge_the_scales("oracle", "oracle").status is ResultStatus.COMPLETED
    before = game.inspect()
    assert game.nudge_the_scales("oracle", "oracle").status is ResultStatus.REJECTED
    assert game.inspect() == before
    path = tmp_path / "oracle-nudge.json"
    game.save(path)
    loaded = Encounter.load(path)
    assert loaded.inspect() == game.inspect()
    assert loaded._state.creatures["oracle"].oracle_cursebound == 2


def test_life_oracle_fixed_sheet_is_legal() -> None:
    definition = get_definition("life_oracle_level_1_staged")
    assert (definition.hp, definition.ac, definition.land_speed_ft, definition.spell_attack, definition.spell_dc) == (18, 15, 30, 7, 17)
    assert definition.background == "Scholar"
    assert {"Fleet", "Natural Skill", "Assurance (Nature)"}.issubset(definition.feats)


def test_life_oracle_assurance_nature_is_an_actual_authored_action() -> None:
    game = Encounter.start(get_setup("staged_life_oracle_nudge"), rolls=(20, 1))
    _settle(game)
    dice_before = game._dice.to_data()
    result = game.execute(RecallKnowledge("guard_dog", GUARD_DOG_KNOWLEDGE.question, "nature", "dog", use_assurance=True))
    assert result.status is ResultStatus.COMPLETED
    event = next(event for event in result.events if event.kind == "recall_knowledge")
    assert event.check is not None and (event.check.method, event.check.die, event.check.total) == ("assurance", None, 13)
    assert game.inspect().choice is None and game._dice.to_data() == dice_before


def test_life_link_focus_cast_transfers_once_before_temporary_hp_and_round_trips(tmp_path) -> None:
    game = Encounter.start(get_setup("staged_life_oracle_nudge"), rolls=(20, 1, 4, 20, 4))
    _settle(game)
    assert game.execute(Cast("life_link", "dog", actions=1)).status is ResultStatus.COMPLETED
    oracle = game._state.creatures["oracle"]
    dog = game._state.creatures["dog"]
    assert (oracle.focus_points, oracle.actions_remaining) == (0, 2)
    effect = next(effect for effect in game._state.active_effects if effect.kind == "life_link")
    path = tmp_path / "life-link.json"
    game.save(path)
    game = Encounter.load(path)
    assert game.execute(Stride((Position(2, 2), Position(3, 2)))).status is ResultStatus.COMPLETED
    assert game.execute(Strike("dog", "staff")).status in {ResultStatus.COMPLETED, ResultStatus.PAUSED}
    _settle(game)
    assert (game._state.creatures["oracle"].hp, game._state.creatures["dog"].hp) == (15, 3)
    effect = next(effect for effect in game._state.active_effects if effect.kind == "life_link")
    assert effect.life_link_used_round == game.inspect().round_number
    if game.inspect().turn_actor_id != "oracle":
        assert game.execute(EndTurn()).status is ResultStatus.COMPLETED
    assert game.inspect().turn_actor_id == "oracle"
    assert game.execute(Dismiss(effect_id=effect.effect_id)).status is ResultStatus.COMPLETED


def test_life_link_keeps_void_healing_target_legal_without_initial_vitality_healing() -> None:
    game = Encounter.start(get_setup("staged_life_oracle_vitality_lash"), rolls=(20, 1, 4))
    _settle(game)
    target = game._state.creatures["death_oracle"]
    target.hp = 5
    result = game.execute(Cast("life_link", "death_oracle", actions=1))
    assert result.status is ResultStatus.COMPLETED
    assert target.hp == 5
    assert any(event.kind == "healing_ignored" for event in result.events)
    assert any(effect.kind == "life_link" for effect in game._state.active_effects)


def test_bounded_terminal_casts_and_selects_self_nudge() -> None:
    transcript = BoundedTranscript(max_lines=200, max_chars=30_000)
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
        raise AssertionError(f"missing {label!r}: {state['menu']!r}")
    def input_fn() -> str:
        if state["prompt"] == "Choice prompt action:":
            return choose("Resolve this choice")
        if state["prompt"] == "Choice option number:":
            return choose("Keep initiative")
        if state["prompt"] == "Choice:":
            if state["phase"] == "cast":
                state["phase"] = "nudge"
                return choose("Cast")
            if state["phase"] == "nudge":
                state["phase"] = "quit"
                return choose("Nudge the Scales")
            return choose("Quit")
        if state["prompt"] == "Spell number:":
            return choose("Runic Weapon", prefix=True)
        if state["prompt"] == "Casting mode:":
            return choose("2 actions")
        if state["prompt"] == "Prepared slot:":
            return "1"
        if state["prompt"] == "Item number:":
            return "1"
        if state["prompt"] == "Target number:":
            return "1"
        raise AssertionError(state["prompt"])
    assert run_terminal(setup=get_setup("staged_life_oracle_nudge"), rolls=(20, 1), input_fn=BoundedInput(input_fn, max_calls=30), output_fn=output) == 0
    rendered = "\n".join(transcript)
    assert "commits Runic Weapon" in rendered
    assert "cursebound is now 1" in rendered


def test_bounded_terminal_casts_and_dismisses_life_link() -> None:
    transcript = BoundedTranscript(max_lines=200, max_chars=30_000)
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
        raise AssertionError(f"missing {label!r}: {state['menu']!r}")

    def input_fn() -> str:
        prompt = state["prompt"]
        if prompt == "Choice prompt action:":
            return choose("Resolve this choice")
        if prompt == "Choice option number:":
            return choose("Keep initiative")
        if prompt == "Choice:":
            if state["phase"] == "cast":
                state["phase"] = "dismiss"
                return choose("Cast")
            if state["phase"] == "dismiss":
                state["phase"] = "quit"
                return choose("Dismiss Life Link")
            return choose("Quit")
        if prompt == "Spell number:":
            return choose("Life Link", prefix=True)
        if prompt == "Casting mode:":
            return choose("1 action")
        if prompt == "Target number:":
            return "1"
        raise AssertionError(prompt)

    assert run_terminal(
        setup=get_setup("staged_life_oracle_nudge"), rolls=(20, 1, 4),
        input_fn=BoundedInput(input_fn, max_calls=24), output_fn=output,
    ) == 0
    rendered = "\n".join(transcript)
    assert "links life to Guard Dog" in rendered
    assert "dismisses Life Link" in rendered


def test_bounded_terminal_refocuses_and_prepares_selected_oracle_mode(monkeypatch) -> None:
    game = Encounter.start(get_setup("staged_life_oracle_nudge"), rolls=(20, 1, 1, 20, 4, 4, 20, 4, 4, 20, 4, 4))
    _settle(game)
    assert game.execute(Cast("runic_weapon", actions=2, item_id="oracle:staff")).status is ResultStatus.COMPLETED
    assert game.execute(EndTurn()).status is ResultStatus.COMPLETED
    assert game.execute(EndTurn()).status is ResultStatus.COMPLETED
    assert game.nudge_the_scales("oracle", "oracle").status is ResultStatus.COMPLETED
    assert game.nudge_the_scales("oracle", "oracle").status is ResultStatus.COMPLETED
    assert game.execute(EndTurn()).status is ResultStatus.COMPLETED
    assert game.execute(EndTurn()).status is ResultStatus.COMPLETED
    assert game.execute(Stride((Position(2, 2), Position(3, 2)))).status is ResultStatus.COMPLETED
    assert game.execute(EndTurn()).status is ResultStatus.COMPLETED
    assert game.execute(EndTurn()).status is ResultStatus.COMPLETED
    for _ in range(2):
        assert game.execute(Strike("dog", "staff")).status in {ResultStatus.COMPLETED, ResultStatus.PAUSED}
        _settle(game)
    assert not game.inspect().in_progress
    monkeypatch.setattr(Encounter, "start", classmethod(lambda _cls, *args, **kwargs: game))

    transcript = BoundedTranscript(max_lines=350, max_chars=50_000)
    state = {"menu": "", "prompt": "", "phase": "refocus"}

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
        raise AssertionError(f"missing {label!r}: {state['menu']!r}")

    def input_fn() -> str:
        prompt = state["prompt"]
        if prompt == "Choice:":
            phase = state["phase"]
            if phase == "refocus":
                state["phase"] = "rest"
                return choose("Refocus", prefix=True)
            if phase == "rest":
                state["phase"] = "mode"
                return choose("Record Rested Eligibility")
            if phase == "mode":
                state["phase"] = "prepare"
                return choose("Choose Oracle Life/Death Mode")
            if phase == "prepare":
                state["phase"] = "quit"
                return choose("Daily Preparation")
            return choose("Quit")
        if prompt in {"Refocus actor number:", "Actor numbers:"}:
            return "1"
        if prompt == "Declared preparation day:":
            return "2"
        if prompt == "Externally adjudicated elapsed seconds:":
            return "1"
        if prompt == "Oracle mode (life/death):":
            return "death"
        raise AssertionError(prompt)

    assert run_terminal(
        setup=get_setup("staged_life_oracle_nudge"),
        input_fn=BoundedInput(input_fn, max_calls=35),
        output_fn=output,
    ) == 0
    rendered = "\n".join(transcript)
    assert "Refocuses for 10 minutes" in rendered
    assert "selects death mode" in rendered
    assert "Daily preparation completed" in rendered


def test_oracle_victory_refocus_save_and_next_scene_keeps_spent_slot(tmp_path) -> None:
    game = Encounter.start(get_setup("staged_life_oracle_nudge"), rolls=(20, 1, 1, 20, 4, 4, 20, 4, 4, 20, 4, 4))
    _settle(game)
    assert game.execute(Cast("runic_weapon", actions=2, item_id="oracle:staff")).status is ResultStatus.COMPLETED
    assert game.execute(EndTurn()).status is ResultStatus.COMPLETED
    assert game.execute(EndTurn()).status is ResultStatus.COMPLETED
    assert game.nudge_the_scales("oracle", "oracle").status is ResultStatus.COMPLETED
    assert game.nudge_the_scales("oracle", "oracle").status is ResultStatus.COMPLETED
    assert game.execute(Cast("life_link", "dog", actions=1)).status is ResultStatus.COMPLETED
    if game.inspect().turn_actor_id != "oracle":
        assert game.execute(EndTurn()).status is ResultStatus.COMPLETED
    assert game.inspect().turn_actor_id == "oracle"
    assert game.execute(Stride((Position(2, 2), Position(3, 2)))).status is ResultStatus.COMPLETED
    assert game.execute(EndTurn()).status is ResultStatus.COMPLETED
    assert game.execute(EndTurn()).status is ResultStatus.COMPLETED
    link = next(effect for effect in game._state.active_effects if effect.kind == "life_link")
    assert game.execute(Dismiss(effect_id=link.effect_id)).status is ResultStatus.COMPLETED
    assert game.execute(Strike("dog", "staff")).status in {ResultStatus.COMPLETED, ResultStatus.PAUSED}
    _settle(game)
    if game.inspect().in_progress:
        assert game.execute(Strike("dog", "staff")).status in {ResultStatus.COMPLETED, ResultStatus.PAUSED}
        _settle(game)
    assert not game.inspect().in_progress
    assert game.refocus("oracle").status is ResultStatus.COMPLETED
    assert game.refocus("oracle").status is ResultStatus.COMPLETED
    assert game._state.creatures["oracle"].oracle_cursebound == 0
    path = tmp_path / "oracle-recovery.json"
    game.save(path)
    game = Encounter.load(path)
    assert game._state.creatures["oracle"].spontaneous_slots[0].remaining == 2
    assert game.next_encounter(get_setup("staged_life_oracle_next")).status is ResultStatus.PAUSED
    _settle(game)
    assert game._state.creatures["oracle"].spontaneous_slots[0].remaining == 2
    cast = game.execute(Cast("divine_lance", "next_dog", actions=2))
    assert cast.status in {ResultStatus.COMPLETED, ResultStatus.PAUSED}
    _settle(game)


def test_vitality_lash_uses_basic_fortitude_and_saved_hero_choice(tmp_path) -> None:
    game = Encounter.start(get_setup("staged_life_oracle_vitality_lash"), rolls=(20, 1, 1, 6, 6))
    _settle(game)
    cast = game.execute(Cast("vitality_lash", "death_oracle", actions=2))
    assert cast.status is ResultStatus.PAUSED
    path = tmp_path / "vitality-lash.json"
    game.save(path)
    restored = Encounter.load(path)
    choice = restored.inspect().choice
    assert choice is not None and choice.kind == "spell_save_hero_reroll"
    resolved = restored.choose(choice.choice_id, "keep", choice.owner_actor_id)
    assert resolved.status in {ResultStatus.COMPLETED, ResultStatus.PAUSED}
    assert any(effect.kind == "enfeebled" and effect.value == 1 for effect in restored.inspect().actors[1].condition_effects)
