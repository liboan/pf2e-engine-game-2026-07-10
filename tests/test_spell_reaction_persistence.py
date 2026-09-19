"""Focused save/load regressions for spell-triggered reactions and outcomes."""

import json
from pathlib import Path

import pytest

from pf2e.content import S2_PC_DUEL_SETUP, S3_SETUP, get_setup
from pf2e.encounter import Encounter
from pf2e.model import Cast, EndTurn, HealthMode, Position, ResultStatus, Strike, Stride


def _keep_initiative(game: Encounter) -> None:
    while game.inspect().choice is not None:
        choice = game.inspect().choice
        assert choice is not None
        assert choice.kind in {"initiative_hero_reroll", "initiative_tie"}
        option = "keep" if any(item.option_id == "keep" for item in choice.options) else choice.options[0].option_id
        game.choose(choice.choice_id, option)


def _actor(game: Encounter, actor_id: str):
    return next(actor for actor in game.inspect().actors if actor.actor_id == actor_id)


def _pending_cast_reaction(tmp_path: Path) -> tuple[Encounter, Path, int]:
    game = Encounter.start(
        get_setup("s3_interrupted_preparation"),
        # Five initiative checks, then a critical Reactive Strike and its d6.
        rolls=(1, 2, 20, 19, 3, 20, 3, 1),
    )
    _keep_initiative(game)
    assert game.inspect().turn_actor_id == "cleric_c"

    cast = game.execute(Cast("heal", "cleric_c", actions=2, slot_id="ordinary_heal_1"))
    reaction = cast.inspection.choice
    assert cast.status is ResultStatus.PAUSED
    assert reaction is not None and reaction.kind == "reaction"
    assert reaction.owner_actor_id == "rapier_fighter"
    attack = game.choose(reaction.choice_id, "accept")
    choice = attack.inspection.choice
    assert attack.status is ResultStatus.PAUSED
    assert choice is not None and choice.kind == "attack_hero_reroll"

    caster = _actor(game, "cleric_c")
    assert caster.actions_remaining == 1
    assert next(slot for slot in caster.prepared_slots if slot.slot_id == "ordinary_heal_1").spent
    path = tmp_path / "cast-reaction-pending.json"
    game.save(path)
    return game, path, choice.choice_id


def test_cast_parent_reaction_hero_choice_round_trips_and_disrupts_once(tmp_path: Path) -> None:
    game, path, choice_id = _pending_cast_reaction(tmp_path)
    saved = json.loads(path.read_text(encoding="utf-8"))
    pending = saved["state"]["pending_choice"]
    parent = pending["continuation"]
    assert pending["is_reaction"] is True
    assert parent["kind"] == "cast"
    assert parent["actor_id"] == parent["target_id"] == "cleric_c"
    assert parent["reaction_trigger"] == "manipulate"
    assert parent["must_disrupt_on_critical"] is True
    assert "rapier_fighter" in parent["seen_reactors"]
    assert parent["spell_id"] == "heal"
    assert parent["slot_id"] == "ordinary_heal_1" and parent["spell_actions"] == 2

    restored = Encounter.load(path)
    assert restored.inspect() == game.inspect()
    round_trip = tmp_path / "cast-reaction-round-trip.json"
    restored.save(round_trip)
    assert json.loads(round_trip.read_text(encoding="utf-8")) == saved

    resolved = restored.choose(choice_id, "keep")
    assert resolved.status is ResultStatus.COMPLETED
    assert any(event.kind == "disrupted" for event in resolved.events)
    assert not any(event.kind in {"healing", "spell_willingness", "heal_roll"} for event in resolved.events)
    check = next(event.check for event in resolved.events if event.check is not None)
    damage = next(event.damage for event in resolved.events if event.damage is not None)
    assert check is not None and check.die == 20
    assert damage is not None
    assert damage.components[0].rolls == (3,) and damage.components[-1].rolls == (1,)
    assert damage.total == 9

    caster = _actor(restored, "cleric_c")
    assert caster.hp == 8 and caster.actions_remaining == 1
    assert next(slot for slot in caster.prepared_slots if slot.slot_id == "ordinary_heal_1").spent
    after = tmp_path / "cast-reaction-resolved.json"
    restored.save(after)
    resolved_data = json.loads(after.read_text(encoding="utf-8"))
    assert resolved_data["dice"]["index"] == 8  # no Heal dice were drawn after the saved Strike.


@pytest.mark.parametrize(
    ("corruption", "message"),
    [
        ("missing_parent", "pending reaction Strike without its parent action"),
        ("mismatched_trigger", "pending reaction Strike without its parent action"),
        ("wrong_disruption", "inconsistent pending reaction disruption"),
    ],
)
def test_loader_rejects_orphaned_or_mismatched_cast_reaction_parent(
    tmp_path: Path, corruption: str, message: str,
) -> None:
    _game, path, _choice_id = _pending_cast_reaction(tmp_path)
    saved = json.loads(path.read_text(encoding="utf-8"))
    pending = saved["state"]["pending_choice"]
    if corruption == "missing_parent":
        pending["continuation"] = None
    elif corruption == "mismatched_trigger":
        pending["continuation"]["reaction_trigger"] = "ranged"
    else:
        pending["continuation"]["must_disrupt_on_critical"] = False
    path.write_text(json.dumps(saved), encoding="utf-8")

    with pytest.raises(ValueError, match=message):
        Encounter.load(path)


def test_nonlethal_pc_knockout_finishes_and_saves_the_winner(tmp_path: Path) -> None:
    game = Encounter.start(S2_PC_DUEL_SETUP, rolls=(20, 19, 20, 4, 20, 1))
    _keep_initiative(game)
    assert game.inspect().turn_actor_id == "fighter_a"

    for _ in range(2):
        result = game.execute(Strike("fighter_b", attack_id="fist", nonlethal=True))
        choice = result.inspection.choice
        assert result.status is ResultStatus.PAUSED
        assert choice is not None and choice.kind == "attack_hero_reroll"
        result = game.choose(choice.choice_id, "keep")

    assert result.inspection.in_progress is False
    assert result.inspection.winner_team == "blue"
    downed = _actor(game, "fighter_b")
    assert (downed.hp, downed.unconscious, downed.prone, downed.dead, downed.defeated) == (
        0, True, True, False, False,
    )
    assert downed.health_mode is HealthMode.PC

    path = tmp_path / "nonlethal-pc-outcome.json"
    game.save(path)
    restored = Encounter.load(path)
    assert restored.inspect() == game.inspect()
    assert not restored.inspect().in_progress and restored.inspect().winner_team == "blue"
    assert (_actor(restored, "fighter_b").hp, _actor(restored, "fighter_b").unconscious) == (0, True)


def test_unconscious_pc_with_active_ally_remains_rescuable_after_load(tmp_path: Path) -> None:
    game = Encounter.start(S3_SETUP, rolls=(20, 19, 10, 1, 2, 3, 20, 8, 8, 1))
    _keep_initiative(game)
    assert game.inspect().turn_actor_id == "fighter_m"
    assert game.execute(Stride((Position(1, 1),))).status is ResultStatus.COMPLETED

    hit = game.execute(Strike("fighter_r", attack_id="longsword"))
    choice = hit.inspection.choice
    assert hit.status is ResultStatus.PAUSED
    assert choice is not None and choice.kind == "attack_hero_reroll"
    health = game.choose(choice.choice_id, "keep")
    choice = health.inspection.choice
    assert choice is not None and choice.kind == "heroic_recovery_damage"
    knocked_out = game.choose(choice.choice_id, "normal")
    fighter = _actor(game, "fighter_r")
    assert fighter.unconscious and fighter.dying == 2
    assert knocked_out.inspection.in_progress and knocked_out.inspection.winner_team is None
    assert game.execute(EndTurn()).status is ResultStatus.COMPLETED
    assert game.inspect().turn_actor_id == "cleric_c"

    save = tmp_path / "active-ally-with-unconscious-pc.json"
    game.save(save)
    restored = Encounter.load(save)
    assert restored.inspect() == game.inspect()
    heal = restored.execute(Cast("heal", "fighter_r", actions=2, slot_id="ordinary_heal_1"))
    choice = heal.inspection.choice
    assert heal.status is ResultStatus.PAUSED
    assert choice is not None and choice.kind == "spell_willingness"
    restored.save(save)
    restored = Encounter.load(save)
    assert restored.inspect() == heal.inspection
    restored.choose(choice.choice_id, "willing")
    fighter = _actor(restored, "fighter_r")
    assert fighter.hp > 0 and not fighter.unconscious and fighter.wounded == 1
    assert restored.inspect().in_progress and restored.inspect().winner_team is None
