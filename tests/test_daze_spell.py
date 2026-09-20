"""Public Daze delivery checks.

Sources checked 2026-09-20:

* Daze, Player Core p. 322: https://2e.aonprd.com/Spells.aspx?ID=1482
* Basic saving throws: https://2e.aonprd.com/Rules.aspx?ID=2247

Daze is a two-action, 60-foot arcane/divine/occult cantrip with a basic Will
save against 1d6 mental damage.  Only a critical failure also applies stunned
1.  Its mental and nonlethal traits must survive the ordinary damage route.
"""

from pathlib import Path

from pf2e.content import get_definition, get_setup
from pf2e.encounter import Encounter
from pf2e.model import Cast, EndTurn, ResultStatus
from pf2e.terminal import run_terminal
from terminal_test_helpers import BoundedInput, BoundedTranscript


def _settle(game: Encounter) -> None:
    while (choice := game.inspect().choice) is not None:
        assert game.choose(choice.choice_id, "keep", choice.owner_actor_id).status in {
            ResultStatus.COMPLETED,
            ResultStatus.PAUSED,
        }


def test_daze_uses_basic_will_damage_nonlethal_stun_and_saved_state(tmp_path: Path) -> None:
    # Initiative; target critical Will failure; 1d6 Daze damage.
    game = Encounter.start(
        get_setup("faiths_flamekeeper_daze_vs_common_speaker"),
        rolls=(20, 1, 1, 6),
    )
    _settle(game)

    result = game.execute(Cast("daze", "enemy"))

    assert result.status is ResultStatus.COMPLETED
    damage = next(event.damage for event in result.events if event.kind == "spell_damage")
    assert damage is not None and (damage.total, damage.components[0].damage_type) == (12, "mental")
    assert any(event.kind == "condition_applied" and "stunned 1" in event.text for event in result.events)
    target = game._state.creatures["enemy"]
    assert (target.hp, target.stunned, target.reaction_available) == (2, 1, False)

    path = tmp_path / "daze-stunned.json"
    game.save(path)
    restored = Encounter.load(path)
    target = restored._state.creatures["enemy"]
    assert (target.stunned, target.stunned_source_actor_id) == (1, "witch")

    next_turn = restored.execute(EndTurn())
    assert next_turn.status is ResultStatus.COMPLETED
    assert restored.inspect().turn_actor_id == "enemy"
    assert restored._state.creatures["enemy"].actions_remaining == 2
    assert any(event.kind == "stunned_actions_lost" for event in next_turn.events)


def test_daze_witch_finishes_a_continuous_public_encounter() -> None:
    # Initiative; first Daze save/damage; second Daze save/damage.
    game = Encounter.start(
        get_setup("faiths_flamekeeper_daze_vs_common_speaker"),
        rolls=(20, 1, 1, 6, 1, 6),
    )
    _settle(game)
    assert game.execute(Cast("daze", "enemy")).status is ResultStatus.COMPLETED
    assert game.execute(EndTurn()).status is ResultStatus.COMPLETED
    assert game.execute(EndTurn()).status is ResultStatus.COMPLETED

    result = game.execute(Cast("daze", "enemy"))

    assert result.status is ResultStatus.COMPLETED
    assert not game.inspect().in_progress
    assert game._state.creatures["witch"].hp == 16
    assert game._state.creatures["enemy"].defeated
    assert not game._state.creatures["enemy"].dead


def test_daze_is_a_learned_wizard_option_and_a_ten_cantrip_witch_replacement() -> None:
    wizard = get_definition("wizard_battle_magic_level_1_daze_prepared")
    witch = get_definition("faiths_flamekeeper_witch_level_1_daze_prepared")
    standard_witch = get_definition("faiths_flamekeeper_witch_level_1")

    assert [entry.spell_id for entry in wizard.spell_substitution_book].count("daze") == 1
    assert any(slot.spell_id == "daze" and slot.cantrip for slot in wizard.prepared_spells)
    assert "twelve cantrips" not in " ".join(get_definition("wizard_battle_magic_level_1_staged").sheet_notes)
    assert any("legally learned" in note for note in wizard.sheet_notes)
    assert any(slot.spell_id == "daze" and slot.cantrip for slot in witch.prepared_spells)
    assert "Daze" not in " ".join(standard_witch.sheet_notes)
    assert any("replaces Sigil" in note for note in witch.sheet_notes)


def test_terminal_casts_daze_from_the_normal_catalog_fixture() -> None:
    transcript = BoundedTranscript(max_lines=220, max_chars=30_000)
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
            return choose("Daze", prefix=True)
        if prompt == "Casting mode:":
            return choose("2 actions")
        if prompt == "Target number:":
            return "1"
        raise AssertionError(f"unexpected terminal prompt: {prompt!r}")

    assert run_terminal(
        setup=get_setup("battle_magic_wizard_daze_vs_guard_dog"),
        rolls=(20, 1, 1, 6),
        input_fn=BoundedInput(scripted_input, max_calls=30),
        output_fn=output,
    ) == 0
    rendered = "\n".join(transcript)
    assert "Rejected:" not in rendered, rendered
    assert "commits Daze" in rendered
    assert "Daze deals 12 mental" in rendered
