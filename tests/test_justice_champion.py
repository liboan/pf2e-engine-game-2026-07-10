"""Focused executable evidence for the admitted Justice Champion slice."""

from __future__ import annotations

import pytest

from pf2e.content import JUSTICE_CHAMPION, JUSTICE_CHAMPION_SETUP, get_definition
from pf2e.damage import DamageTerm, roll_damage_terms
from pf2e.encounter import Encounter
from pf2e.model import (
    EndTurn,
    FamilyProcedureContext,
    LayOnHands,
    ResumeAura,
    ResultStatus,
    Strike,
    SuppressAura,
)
from pf2e.terminal import build_action_menu, render_support_summary, run_terminal
from terminal_test_helpers import BoundedInput, BoundedTranscript


def _start(*, rolls: tuple[int, ...] = (10, 20, 1, 20, 4, 4, 4, 4, 4)) -> Encounter:
    game = Encounter.start(JUSTICE_CHAMPION_SETUP, rolls=rolls)
    while game.inspect().choice is not None:
        choice = game.inspect().choice
        assert choice is not None
        option_id = (
            "keep"
            if any(option.option_id == "keep" for option in choice.options)
            else choice.options[0].option_id
        )
        result = game.choose(choice.choice_id, option_id, choice.owner_actor_id)
        assert result.status is ResultStatus.COMPLETED or result.status is ResultStatus.PAUSED
    return game


def _to_turn(game: Encounter, actor_id: str) -> None:
    for _ in range(len(game._state.initiative_order) + 1):
        if game.inspect().turn_actor_id == actor_id:
            return
        assert game.inspect().choice is None
        result = game.execute(EndTurn())
        assert result.status is ResultStatus.COMPLETED
    raise AssertionError(f"did not reach {actor_id}")


def test_admitted_sheet_and_terminal_surface() -> None:
    assert JUSTICE_CHAMPION.definition_id in {
        placement.definition_id for placement in JUSTICE_CHAMPION_SETUP.placements
    }
    assert JUSTICE_CHAMPION.ancestry == "Human"
    assert JUSTICE_CHAMPION.heritage == "Skilled Human"
    assert JUSTICE_CHAMPION.background == "Farmhand"
    assert JUSTICE_CHAMPION.class_name == "Champion"
    assert JUSTICE_CHAMPION.deity == "Iomedae"
    assert JUSTICE_CHAMPION.hp == 20
    assert JUSTICE_CHAMPION.ac == 18
    assert JUSTICE_CHAMPION.focus_capacity == 1
    assert JUSTICE_CHAMPION.focus_points == 1
    saves = {save: (proficiency, modifier) for save, proficiency, modifier in JUSTICE_CHAMPION.saves}
    assert saves["fortitude"] == ("expert", 7)
    assert saves["will"] == ("expert", 5)
    assert dict(JUSTICE_CHAMPION.proficiencies)["fortitude"] == "expert"
    assert dict(JUSTICE_CHAMPION.proficiencies)["will"] == "expert"
    assert dict(JUSTICE_CHAMPION.proficiencies)["spell_attack"] == "trained"
    assert dict(JUSTICE_CHAMPION.proficiencies)["spell_dc"] == "trained"
    assert "justice_champion" in JUSTICE_CHAMPION.abilities
    assert "justice_retributive_strike" in JUSTICE_CHAMPION.abilities
    assert "lay_on_hands" in JUSTICE_CHAMPION.abilities
    assert "desperate_prayer" in JUSTICE_CHAMPION.abilities

    menu = build_action_menu(("lay_on_hands", "suppress_aura", "resume_aura", "end_turn"))
    assert menu[1:4] == (
        ("lay_on_hands", "Lay on Hands"),
        ("suppress_aura", "Suppress Aura"),
        ("resume_aura", "Resume Aura"),
    )
    assert render_support_summary(JUSTICE_CHAMPION_SETUP.setup_id).startswith(
        "Curated Justice level-1 Champion of Iomedae setup:"
    )


def test_lay_on_hands_heals_adds_ally_ac_and_round_trips(tmp_path) -> None:
    game = _start()
    _to_turn(game, "justice_champion")
    game._state.creatures["justice_ally"].hp = 5

    result = game.execute(LayOnHands("justice_ally"))

    assert result.status is ResultStatus.COMPLETED
    assert game._state.creatures["justice_champion"].focus_points == 0
    assert game._state.creatures["justice_ally"].hp == 11
    assert any(event.kind == "lay_on_hands_ac" for event in result.events)
    ally = next(actor for actor in result.inspection.actors if actor.actor_id == "justice_ally")
    assert ally.ac == 20

    path = tmp_path / "justice-lay-on-hands.json"
    game.save(path)
    restored = Encounter.load(path)
    assert restored.inspect() == game.inspect()

    # Raise a Shield expires at the ally's next turn start, while the one-
    # round status bonus lasts until the Champion's next turn starts.
    _to_turn(restored, "justice_ally")
    ally = next(actor for actor in restored.inspect().actors if actor.actor_id == "justice_ally")
    assert ally.ac == 20
    assert restored.execute(EndTurn()).status is ResultStatus.PAUSED
    prayer = restored.inspect().choice
    assert prayer is not None and prayer.kind == "desperate_prayer"
    assert restored.choose(prayer.choice_id, "decline", prayer.owner_actor_id).status is ResultStatus.COMPLETED
    ally = next(actor for actor in restored.inspect().actors if actor.actor_id == "justice_ally")
    assert ally.ac == 18


def test_divine_aura_can_be_suppressed_and_resumed() -> None:
    game = _start()
    _to_turn(game, "justice_champion")
    assert "justice_champion" in game._state.justice_aura_active

    suppressed = game.execute(SuppressAura())
    assert suppressed.status is ResultStatus.COMPLETED
    assert "justice_champion" not in game._state.justice_aura_active
    assert "resume_aura" in game.options().available_actions
    assert "suppress_aura" not in game.options().available_actions

    resumed = game.execute(ResumeAura())
    assert resumed.status is ResultStatus.COMPLETED
    assert "justice_champion" in game._state.justice_aura_active


def test_retributive_strike_protects_and_saves_pending_choice(tmp_path) -> None:
    game = _start()
    _to_turn(game, "justice_guard_dog")
    offered = game.execute(Strike("justice_ally", attack_id="jaws"))

    assert offered.status is ResultStatus.PAUSED
    choice = offered.inspection.choice
    assert choice is not None and choice.kind == "reaction"
    assert {option.option_id for option in choice.options} == {"accept", "decline"}

    path = tmp_path / "justice-retributive.json"
    game.save(path)
    restored = Encounter.load(path)
    assert restored.inspect() == game.inspect()
    choice = restored.inspect().choice
    assert choice is not None
    accepted = restored.choose(choice.choice_id, "accept", choice.owner_actor_id)
    assert accepted.status is ResultStatus.PAUSED
    assert any(event.kind == "retributive_strike_protection" for event in accepted.events)
    damage = next(event for event in accepted.events if event.kind == "damage")
    assert "before defenses" in damage.text
    assert restored._state.creatures["justice_champion"].reaction_available is False

    # The Champion has a Hero Point, so the retaliation attack exposes its
    # ordinary saved reroll choice. Keep the deterministic original result.
    reroll = accepted.inspection.choice
    assert reroll is not None and reroll.kind == "attack_hero_reroll"
    completed = restored.choose(reroll.choice_id, "keep", reroll.owner_actor_id)
    assert completed.status is ResultStatus.COMPLETED
    assert any(event.kind == "retributive_strike" for event in (*accepted.events, *completed.events))


def test_retributive_resistance_chooses_one_type_in_mixed_damage() -> None:
    game = _start(rolls=(10, 20, 1, 1, 4, 4, 4))
    _to_turn(game, "justice_guard_dog")
    dog = game._state.creatures["justice_guard_dog"]
    context = FamilyProcedureContext(
        game, game._state, game._dice, dog, get_definition(dog.definition_id), "diagnostic"
    )
    mixed = roll_damage_terms(
        (
            DamageTerm("slash", "slashing", (), modifier=6),
            DamageTerm("fire", "fire", (), modifier=2),
        ),
        lambda _sides: 1,
    )

    assert context.apply_family_damage(
        "justice_ally", mixed, source="mixed diagnostic", damage_type="slashing"
    ) == ()
    reaction = game.inspect().choice
    assert reaction is not None and reaction.kind == "reaction"
    accepted = game.choose(reaction.choice_id, "accept", reaction.owner_actor_id)
    defense = accepted.inspection.choice
    assert defense is not None and defense.kind == "damage_defense"
    assert {option.option_id for option in defense.options} == {"resist:slashing", "resist:fire"}

    resolved = game.choose(defense.choice_id, "resist:slashing", defense.owner_actor_id)
    damage = next(event for event in resolved.events if event.kind == "damage")
    assert damage.damage is not None and damage.damage.total == 5
    assert damage.original_damage is not None and damage.original_damage.total == 8


def test_retributive_strike_can_finish_the_healthy_encounter() -> None:
    # The triggering critical Jaws hit is reduced by resistance 3; the
    # deterministic critical retaliation then defeats the Guard Dog and
    # closes the encounter for the blue team.
    game = _start(rolls=(10, 20, 1, 20, 4, 20, 4))
    _to_turn(game, "justice_guard_dog")
    offered = game.execute(Strike("justice_ally", attack_id="jaws"))
    reaction = offered.inspection.choice
    assert reaction is not None and reaction.kind == "reaction"

    accepted = game.choose(reaction.choice_id, "accept", reaction.owner_actor_id)
    reroll = accepted.inspection.choice
    assert reroll is not None and reroll.kind == "attack_hero_reroll"
    finished = game.choose(reroll.choice_id, "keep", reroll.owner_actor_id)

    assert finished.status is ResultStatus.COMPLETED
    assert finished.inspection.in_progress is False
    assert finished.inspection.winner_team == "blue"
    assert game._state.creatures["justice_guard_dog"].hp == 0


def test_desperate_prayer_pending_save_load_and_turn_expiry(tmp_path) -> None:
    game = _start()
    _to_turn(game, "justice_champion")
    assert game.execute(LayOnHands("justice_ally")).status is ResultStatus.COMPLETED

    # Finish Champion, Guard Dog, and Shield Ally turns. The next Champion
    # start is the first exact point at which the once-per-day prompt exists.
    for _ in range(3):
        result = game.execute(EndTurn())
        assert result.status is ResultStatus.COMPLETED or result.status is ResultStatus.PAUSED
        if game.inspect().choice is not None:
            break
    choice = game.inspect().choice
    assert choice is not None and choice.kind == "desperate_prayer"

    path = tmp_path / "justice-prayer.json"
    game.save(path)
    restored = Encounter.load(path)
    assert restored.inspect() == game.inspect()
    choice = restored.inspect().choice
    assert choice is not None
    accepted = restored.choose(choice.choice_id, "accept", choice.owner_actor_id)
    assert accepted.status is ResultStatus.COMPLETED
    assert restored._state.creatures["justice_champion"].focus_points == 1
    assert "justice_champion" in restored._state.desperate_prayer_points

    restored.execute(EndTurn())
    assert restored._state.creatures["justice_champion"].focus_points == 0
    assert "justice_champion" not in restored._state.desperate_prayer_points


def test_champion_strike_is_holy_sanctified() -> None:
    game = _start()
    _to_turn(game, "justice_champion")
    result = game.execute(Strike("justice_guard_dog", attack_id="longsword"))
    assert result.status is ResultStatus.PAUSED
    choice = result.inspection.choice
    assert choice is not None and choice.kind == "attack_hero_reroll"
    result = game.choose(choice.choice_id, "keep", choice.owner_actor_id)
    damage = next(event for event in result.events if event.kind == "damage")
    assert damage.damage is not None
    assert damage.damage.components[0].tags == frozenset({"holy"})


def test_terminal_drives_justice_actions_and_quits_cleanly() -> None:
    # Seed 0 yields Shield Ally, Champion, Guard Dog. Resolve the two Hero
    # Point initiative offers, then use Lay on Hands, suppress/resume the aura,
    # and quit from the dog turn. These are the menu indices emitted by the
    # real terminal; no direct state mutation is used by this smoke path.
    output = BoundedTranscript()
    answers = iter(("2", "1", "2", "1", "9", "8", "1", "8", "8", "14"))
    input_fn = BoundedInput(
        lambda: next(answers),
        max_calls=32,
        describe=lambda: f"last_output={output[-1]!r}" if output else "no output",
    )

    result = run_terminal(
        setup=JUSTICE_CHAMPION_SETUP,
        seed=0,
        input_fn=input_fn,
        output_fn=output.append,
    )

    assert result == 0
    assert any(line.startswith("Curated Justice level-1 Champion of Iomedae setup:") for line in output)
    assert any("uses Lay on Hands" in line for line in output)
    assert any("suppresses the 15-foot divine aura" in line for line in output)
    assert any("resumes the 15-foot divine aura" in line for line in output)
    assert "Goodbye." in output


def test_terminal_script_policy_is_bounded_with_last_output_diagnostic() -> None:
    transcript = BoundedTranscript(max_lines=512)
    scripted = BoundedInput(
        lambda: "1",  # Repeatedly inspect the unresolved initiative choice.
        max_calls=12,
        describe=lambda: f"last_output={transcript[-1]!r}" if transcript else "no output",
    )

    with pytest.raises(AssertionError, match=r"input script exceeded its call limit \(12\)"):
        run_terminal(
            setup=JUSTICE_CHAMPION_SETUP,
            seed=0,
            input_fn=scripted,
            output_fn=transcript.append,
        )

    assert scripted.calls == 12
    assert transcript
