"""Normal-catalog integration coverage for the selected level-two bundles."""

from __future__ import annotations

import json
from dataclasses import replace
from types import MappingProxyType

import pytest

import pf2e.content as content
from pf2e.encounter import Encounter
from pf2e.l2_horizontal_content import (
    BRAGGART_SWASHBUCKLER_LEVEL_2_TUMBLE_BEHIND_SETUP,
    THIEF_ROGUE_LEVEL_2_MOBILITY_SETUP,
)
from pf2e.l2_ranger_content import RANGER_PRECISION_LEVEL_2_HUNTERS_AIM_SETUP
from pf2e.l2_reach_content import L2_REACH_DEFINITIONS, L2_REACH_SETUPS, STORM_DRUID_L2_REACH_SETUP
from pf2e.model import (
    ActionContinuation, Cast, Choose, CreaturePlacement, EncounterSetup,
    EndTurn, Position, ReachSpell, ResultStatus, Stride,
)
from pf2e.ranger import HuntPrey
from pf2e.skill_actions import QuickJump, TumbleThrough
from pf2e.swashbuckler import ConfidentFinisher
from pf2e.terminal import run_terminal
from terminal_test_helpers import BoundedInput, BoundedTranscript


def _settle_to_turn(game: Encounter, actor_id: str) -> None:
    for _ in range(12):
        if game.inspect().choice is None:
            break
        choice = game.inspect().choice
        assert choice is not None
        option_id = "keep" if any(option.option_id == "keep" for option in choice.options) else choice.options[0].option_id
        assert game.choose(choice.choice_id, option_id, choice.owner_actor_id).status in {
            ResultStatus.PAUSED, ResultStatus.COMPLETED,
        }
    else:
        raise AssertionError("initiative choices did not settle")
    for _ in range(12):
        if game.inspect().turn_actor_id == actor_id:
            return
        assert game.execute(EndTurn()).status is ResultStatus.COMPLETED
    raise AssertionError(f"did not reach {actor_id}'s turn")


def _choose_keep(game: Encounter):
    choice = game.inspect().choice
    assert choice is not None
    return game.choose(choice.choice_id, "keep", choice.owner_actor_id)


def test_normal_catalog_admits_all_l2_setups_and_shared_actions() -> None:
    for setup in (
        THIEF_ROGUE_LEVEL_2_MOBILITY_SETUP,
        BRAGGART_SWASHBUCKLER_LEVEL_2_TUMBLE_BEHIND_SETUP,
        RANGER_PRECISION_LEVEL_2_HUNTERS_AIM_SETUP,
        *L2_REACH_SETUPS,
    ):
        assert content.get_setup(setup.setup_id) is setup
    for definition in L2_REACH_DEFINITIONS:
        assert content.CREATURES[definition.definition_id] is definition

    thief = Encounter.start(content.get_setup(THIEF_ROGUE_LEVEL_2_MOBILITY_SETUP.setup_id), rolls=(20, 1, 1))
    _settle_to_turn(thief, "thief")
    assert thief.execute(Stride((Position(1, 0), Position(2, 0)))).status is ResultStatus.COMPLETED
    assert thief.inspect().choice is None  # Mobility's validated half-Speed Stride.

    ranger = Encounter.start(content.get_setup(RANGER_PRECISION_LEVEL_2_HUNTERS_AIM_SETUP.setup_id), rolls=(20, 1, 1))
    _settle_to_turn(ranger, "ranger")
    assert ranger.execute(HuntPrey("prey")).status is ResultStatus.COMPLETED
    assert "hunter_aim" in ranger.options().available_actions

    druid = Encounter.start(content.get_setup(STORM_DRUID_L2_REACH_SETUP.setup_id), rolls=(20, 1, 1))
    _settle_to_turn(druid, "druid")
    # Unshaped touch remains an adjacent grid target, despite its rules-facing
    # range-0 representation; this same projection feeds the terminal.
    druid._state.creatures["druid_target"].position = Position(2, 2)
    heal = next(spell for spell in druid.options().spells if spell.spell_id == "heal")
    assert "druid_target" in next(mode.targets for mode in heal.target_options if mode.actions == 1)
    druid._state.creatures["druid_target"].position = Position(7, 2)
    assert druid.execute(ReachSpell()).status is ResultStatus.COMPLETED
    assert druid._state.creatures["druid"].reach_spell_pending
    heal = next(spell for spell in druid.options().spells if spell.spell_id == "heal")
    assert "druid_target" in next(mode.targets for mode in heal.target_options if mode.actions == 1)
    with pytest.raises(ValueError, match="Reach Spell"):
        druid._validate_committed_reach_spell_range(
            druid._state,
            ActionContinuation(
                kind="cast", actor_id="druid", spell_id="heal", spell_actions=1,
                reach_spell_effective_range_ft=999,
            ),
        )


def test_reach_spell_pending_codec_rejects_an_off_turn_marker(tmp_path) -> None:
    game = Encounter.start(content.get_setup(STORM_DRUID_L2_REACH_SETUP.setup_id), rolls=(20, 1, 1))
    _settle_to_turn(game, "druid")
    assert game.execute(ReachSpell()).status is ResultStatus.COMPLETED
    path = tmp_path / "forged-off-turn-reach.json"
    game.save(path)
    payload = json.loads(path.read_text())
    state = payload["state"]
    state["active_index"] = state["initiative_order"].index("druid_enemy")
    # Preserve the generic active-turn resource invariants so the rejected
    # marker is the relevant forged fact rather than an unrelated turn shape.
    state["creatures"]["druid"]["actions_remaining"] = 0
    state["creatures"]["druid_enemy"]["actions_remaining"] = 3
    path.write_text(json.dumps(payload))
    with pytest.raises(ValueError, match="Reach Spell"):
        Encounter.load(path)


def test_reach_spell_codec_rejects_forged_committed_range_on_saved_cast(tmp_path) -> None:
    """The save boundary reauthenticates a shaped cast, not just its marker."""
    game = Encounter.start(content.get_setup(STORM_DRUID_L2_REACH_SETUP.setup_id), rolls=(20, 1, 1))
    _settle_to_turn(game, "druid")
    # The ordinary L1 ally sheet predates physical item identities.  Give its
    # real, already catalogued staff instance to the target so this otherwise
    # normal Reach scene reaches the saved willingness continuation.
    game._state.creatures["druid"].held_items.remove("druid:staff")
    game._state.creatures["druid_target"].held_items.append("druid:staff")
    assert game.execute(ReachSpell()).status is ResultStatus.COMPLETED
    started = game.execute(Cast(
        "runic_weapon", item_id="druid:staff", slot_id="druid_runic_weapon_two",
    ))
    assert started.status is ResultStatus.PAUSED
    pending = game.inspect().choice
    assert pending is not None and pending.kind == "spell_willingness"
    assert game._state.pending_choice is not None
    assert game._state.pending_choice.continuation is not None
    assert game._state.pending_choice.continuation.reach_spell_effective_range_ft == 30

    path = tmp_path / "forged-reach-range.json"
    game.save(path)
    payload = json.loads(path.read_text())
    payload["state"]["pending_choice"]["continuation"]["reach_spell_effective_range_ft"] = 999
    path.write_text(json.dumps(payload))
    with pytest.raises(ValueError, match="Reach Spell"):
        Encounter.load(path)


def test_normal_catalog_braggart_tumble_persists_and_snapshots_thrown_attack(tmp_path) -> None:
    game = Encounter.start(
        content.get_setup(BRAGGART_SWASHBUCKLER_LEVEL_2_TUMBLE_BEHIND_SETUP.setup_id),
        rolls=(20, 1, 12, 5, 4, 6, 6),
    )
    _settle_to_turn(game, "braggart")
    assert game.execute(TumbleThrough((Position(1, 1), Position(2, 1)))).status is ResultStatus.PAUSED
    assert _choose_keep(game).status is ResultStatus.COMPLETED
    assert game._state.tumble_behind_exposures

    save_path = tmp_path / "normal-l2-tumble.json"
    game.save(save_path)
    restored = Encounter.load(save_path)
    paused = restored.execute(ConfidentFinisher(
        "braggart_dog", "dagger_thrown", item_id="braggart:dagger_1"
    ))
    assert paused.status is ResultStatus.PAUSED
    assert restored._state.tumble_behind_exposures == []
    events = list(paused.events)
    choice = restored.inspect().choice
    assert choice is not None and choice.kind == "attack_hero_reroll"
    resolved = restored.choose(choice.choice_id, "keep", choice.owner_actor_id)
    assert resolved.status is ResultStatus.PAUSED
    events.extend(resolved.events)
    choice = restored.inspect().choice
    assert choice is not None and choice.kind == "family_action"
    resolved = restored.choose(choice.choice_id, "full_damage", choice.owner_actor_id)
    assert resolved.status is ResultStatus.COMPLETED
    events.extend(resolved.events)
    attack = next(event.check for event in events if event.kind == "strike")
    assert attack is not None and (attack.total, attack.dc) == (13, 13)


@pytest.mark.parametrize("tamper", ("missing_feat", "future_expiry", "inactive_source", "allied_target"))
def test_tumble_behind_codec_rejects_forged_or_off_schedule_exposure(tmp_path, tamper: str) -> None:
    game = Encounter.start(
        content.get_setup(BRAGGART_SWASHBUCKLER_LEVEL_2_TUMBLE_BEHIND_SETUP.setup_id),
        rolls=(20, 1, 12),
    )
    _settle_to_turn(game, "braggart")
    assert game.execute(TumbleThrough((Position(1, 1), Position(2, 1)))).status is ResultStatus.PAUSED
    assert _choose_keep(game).status is ResultStatus.COMPLETED
    path = tmp_path / f"forged-tumble-{tamper}.json"
    game.save(path)
    payload = json.loads(path.read_text())
    state = payload["state"]
    effect = state["tumble_behind_exposures"][0]
    if tamper == "missing_feat":
        effect[1] = "braggart_dog"
        effect[2] = "braggart"
        effect[3][0] = "braggart_dog"
        effect[3][2] = state["actor_end_counts"]["braggart_dog"] + 1
    elif tamper == "future_expiry":
        effect[3][2] += 1
    elif tamper == "inactive_source":
        state["active_index"] = state["initiative_order"].index("braggart_dog")
    else:
        state["creatures"]["braggart_dog"]["team"] = "blue"
    path.write_text(json.dumps(payload))
    with pytest.raises(ValueError, match="Tumble Behind|inactive actors|does not match"):
        Encounter.load(path)


def _quick_jump_reaction_save(tmp_path, *, roll: int, nested: bool) -> tuple[object, dict]:
    game = Encounter.start(
        content.get_setup(THIEF_ROGUE_LEVEL_2_MOBILITY_SETUP.setup_id),
        rolls=(20, 1, roll, 20, 20),
    )
    _settle_to_turn(game, "thief")
    # This short Stride is independently protected by Mobility.  The later
    # Quick Jump intentionally has its own reaction pause to exercise the
    # saved movement continuation.
    assert game.execute(Stride((Position(1, 0), Position(2, 0)))).status is ResultStatus.COMPLETED
    assert game.execute(QuickJump((Position(1, 0),))).status is ResultStatus.PAUSED
    assert _choose_keep(game).status is ResultStatus.PAUSED
    choice = game.inspect().choice
    assert choice is not None and choice.kind == "reaction"
    if nested:
        assert game.choose(choice.choice_id, choice.options[0].option_id, choice.owner_actor_id).status is ResultStatus.PAUSED
        choice = game.inspect().choice
        assert choice is not None and choice.kind == "nimble_dodge"
    path = tmp_path / ("nested-quick-jump.json" if nested else "quick-jump.json")
    game.save(path)
    return path, json.loads(path.read_text())


def test_quick_jump_saved_reaction_rejects_kind_check_path_and_progress_tampering(tmp_path) -> None:
    """A saved Quick Jump cannot be changed into (or out of) a prone landing."""
    path, payload = _quick_jump_reaction_save(tmp_path, roll=20, nested=False)
    continuation = payload["state"]["pending_choice"]["continuation"]
    assert continuation["movement_kind"] == "quick_jump"
    assert continuation["quick_jump_saved_check"] is not None

    for tamper in ("kind", "check", "path", "progress"):
        forged = json.loads(json.dumps(payload))
        movement = forged["state"]["pending_choice"]["continuation"]
        if tamper == "kind":
            movement["movement_kind"] = "quick_jump_critical_failure"
        elif tamper == "check":
            movement["quick_jump_saved_check"]["result"]["die"] = 1
            movement["quick_jump_saved_check"]["result"]["dice"] = [1]
        elif tamper == "path":
            movement["path"] = [[4, 2]]
        else:
            movement["next_step"] = 1
        path.write_text(json.dumps(forged))
        with pytest.raises(ValueError, match="Quick Jump|pending check"):
            Encounter.load(path)

    critical_path, critical_payload = _quick_jump_reaction_save(tmp_path, roll=1, nested=False)
    critical = critical_payload["state"]["pending_choice"]["continuation"]
    assert critical["movement_kind"] == "quick_jump_critical_failure"
    critical["movement_kind"] = "quick_jump"
    critical_path.write_text(json.dumps(critical_payload))
    with pytest.raises(ValueError, match="Quick Jump"):
        Encounter.load(critical_path)


def test_nested_quick_jump_and_tumble_lead_in_save_tampering_are_rejected(tmp_path, monkeypatch) -> None:
    """Continuation-chain validation reaches reaction parents and Tumble lead-ins."""
    path, payload = _quick_jump_reaction_save(tmp_path, roll=20, nested=True)
    nested = payload["state"]["pending_choice"]["continuation"]
    # The pending Nimble Dodge decision serializes the interrupted reaction
    # Strike continuation, whose parent is the original Quick Jump movement.
    quick_jump = nested["parent_continuation"]
    assert quick_jump["movement_kind"] == "quick_jump"
    quick_jump["path"] = [[4, 2]]
    path.write_text(json.dumps(payload))
    with pytest.raises(ValueError, match="Quick Jump"):
        Encounter.load(path)

    source = BRAGGART_SWASHBUCKLER_LEVEL_2_TUMBLE_BEHIND_SETUP
    tumble_setup = EncounterSetup(
        "l2_braggart_tumble_lead_in_reaction",
        "Level 2 Braggart Tumble Through reactive lead-in",
        source.width,
        source.height,
        (
            source.placements[0],
            CreaturePlacement("tumble_fighter", "fighter_m_level_1", "Reactive Fighter", "red", Position(1, 1)),
        ),
    )
    monkeypatch.setattr(
        content, "_STAGED_SETUPS",
        MappingProxyType({**content._STAGED_SETUPS, tumble_setup.setup_id: tumble_setup}),
    )
    tumble = Encounter.start(tumble_setup, rolls=(20, 1, 12, 20, 20))
    _settle_to_turn(tumble, "braggart")
    assert tumble.execute(TumbleThrough((Position(1, 1), Position(2, 1)))).status is ResultStatus.PAUSED
    choice = tumble.inspect().choice
    assert choice is not None and choice.kind == "reaction"
    tumble_path = tmp_path / "tumble-lead-in.json"
    tumble.save(tumble_path)
    forged = json.loads(tumble_path.read_text())
    continuation = forged["state"]["pending_choice"]["continuation"]
    assert continuation["stage"] == "tumble_through_lead_in"
    continuation["tumble_origin"] = [3, 2]
    tumble_path.write_text(json.dumps(forged))
    with pytest.raises(ValueError, match="Tumble Through"):
        Encounter.load(tumble_path)


@pytest.mark.parametrize(
    ("setup_id", "main_actions", "paths", "rolls", "expected"),
    (
        (
            THIEF_ROGUE_LEVEL_2_MOBILITY_SETUP.setup_id,
            ("Stride", "Quick Jump", "Quit"),
            {"Stride path, in order (for example B2 C2 D3):": "B1 C1",
             "Quick Jump path, in order (for example B2 C2 D2):": "B1"},
            (20, 1, 20, 20, 20),
            ("Quick Jump",),
        ),
        (
            BRAGGART_SWASHBUCKLER_LEVEL_2_TUMBLE_BEHIND_SETUP.setup_id,
            ("Tumble Through", "Confident Finisher", "Quit"),
            {"Tumble Through path, in order (for example B2 C2 D2):": "B2 C2"},
            (20, 1, 12, 5, 4, 6, 6),
            ("Tumble Through", "Confident Finisher"),
        ),
    ),
)
def test_normal_catalog_terminal_executes_l2_horizontal_actions(
    setup_id, main_actions, paths, rolls, expected,
) -> None:
    """Drive ordinary catalog scenes through the actual shared terminal flow."""
    setup = content.get_setup(setup_id)
    transcript = BoundedTranscript(max_lines=240, max_chars=32_000)
    menu = {"text": "", "prompt": ""}
    action_index = 0

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
        nonlocal action_index
        if menu["prompt"] == "Choice:":
            label = main_actions[action_index]
            action_index += 1
            return menu_number(label)
        if menu["prompt"] in paths:
            return paths[menu["prompt"]]
        if menu["prompt"] == "Choice prompt action:":
            return "2"  # Resolve the pending initiative choice.
        if menu["prompt"] == "Choice option number:":
            if "Full damage" in menu["text"]:
                return menu_number("Full damage")
            if "Decline" in menu["text"]:
                return menu_number("Decline")
            return "1"
        if menu["prompt"] in {"Weapon / attack number:", "Target number:", "Damage intent:"}:
            return "1"
        raise AssertionError(f"unexpected terminal prompt: {menu['prompt']!r}")

    assert run_terminal(
        setup=setup, rolls=rolls,
        input_fn=BoundedInput(script), output_fn=output,
    ) == 0
    rendered = "\n".join(transcript)
    assert action_index == len(main_actions)
    assert all(label in rendered for label in expected), rendered
    if setup_id == THIEF_ROGUE_LEVEL_2_MOBILITY_SETUP.setup_id:
        # The first action is the legal 10-foot Stride past the reactive
        # fighter; Mobility suppresses its offer.  The later Quick Jump is
        # deliberately distinct and does offer a movement-trigger reaction.
        before_quick_jump = rendered.split("Quick Jump path,", 1)[0]
        assert "Reactive Strike against Thief Rogue" not in before_quick_jump


def test_normal_catalog_terminal_reach_spell_projects_the_extended_heal_target() -> None:
    """Reach Spell's normal terminal Cast menu exposes the legal 30-foot ally."""
    setup = content.get_setup(STORM_DRUID_L2_REACH_SETUP.setup_id)
    transcript = BoundedTranscript(max_lines=180, max_chars=28_000)
    menu = {"text": "", "prompt": "", "heal_targets": ""}
    main_actions = iter(("Reach Spell", "Cast", "Quit"))
    awaiting_heal_targets = False

    def output(line: str) -> None:
        nonlocal awaiting_heal_targets
        transcript.append(line)
        if line.startswith("1. "):
            menu["text"] = line
            if awaiting_heal_targets:
                menu["heal_targets"] = line
                awaiting_heal_targets = False
        if line.endswith(":"):
            menu["prompt"] = line
            if line == "Heal target:":
                awaiting_heal_targets = True

    def menu_number(label: str) -> str:
        for row in menu["text"].splitlines():
            if ". " in row and row.split(". ", 1)[1] == label:
                return row.split(". ", 1)[0]
        raise AssertionError(f"missing terminal menu item {label!r}: {menu['text']!r}")

    def containing(fragment: str) -> str:
        for row in menu["text"].splitlines():
            if ". " in row and fragment in row.split(". ", 1)[1]:
                return row.split(". ", 1)[0]
        raise AssertionError(f"missing terminal item containing {fragment!r}: {menu['text']!r}")

    def script() -> str:
        if menu["prompt"] == "Choice:":
            return menu_number(next(main_actions))
        if menu["prompt"] == "Choice prompt action:":
            return "2"
        if menu["prompt"] == "Choice option number:":
            return "1"
        if menu["prompt"] == "Spell number:":
            return containing("Heal")
        if menu["prompt"] == "Casting mode:":
            return containing("1 action")
        if menu["prompt"] == "Prepared slot:":
            return containing("druid_heal_one")
        if menu["prompt"] in {"Heal target:", "Target number:"}:
            return containing("Druid Ally")
        raise AssertionError(f"unexpected terminal prompt: {menu['prompt']!r}")

    assert run_terminal(
        setup=setup, rolls=(20, 1, 1, 4, 4, 4),
        input_fn=BoundedInput(script), output_fn=output,
    ) == 0
    assert "Druid Ally (druid_target)" in menu["heal_targets"]
    assert "Reach Spell" in "\n".join(transcript)
