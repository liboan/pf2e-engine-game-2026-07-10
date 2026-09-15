"""S2A encounter-level PC health, initiative, and saved-choice coverage."""

from pathlib import Path

from pf2e.content import S2_SETUP
from pf2e.encounter import Encounter
from pf2e.model import EndTurn, Position, ResultStatus, Strike, Stride


def _choose_initiative_choices(game: Encounter, *, option: str = "keep") -> None:
    while game.inspect().choice is not None:
        choice = game.inspect().choice
        assert choice is not None
        if choice.kind != "initiative_hero_reroll":
            break
        game.choose(choice.choice_id, option)


def _run_to_fighter_a_knockout(
    recovery_rolls: tuple[int, ...] = (20,), tail: tuple[int, ...] = ()
) -> Encounter:
    # PC initiative is low; two dogs enter reach and land three critical jaws
    # Strikes on Fighter A. No encounter state is patched by the test.
    rolls = (1, 2, 20, 19, 20, 4, 20, 4, 20, 4, *recovery_rolls, *tail)
    game = Encounter.start(S2_SETUP, rolls=rolls)
    _choose_initiative_choices(game)
    assert game.inspect().turn_actor_id == "guard_dog_a"
    assert game.execute(Stride((Position(4, 1), Position(3, 1), Position(2, 1)))).status is ResultStatus.COMPLETED
    assert game.execute(Strike("fighter_a")).status is ResultStatus.COMPLETED
    assert game.execute(Strike("fighter_a")).status is ResultStatus.COMPLETED
    assert game.inspect().turn_actor_id == "guard_dog_b"
    assert game.execute(Stride((Position(4, 3), Position(3, 2), Position(2, 2)))).status is ResultStatus.COMPLETED
    result = game.execute(Strike("fighter_a"))
    assert result.status is ResultStatus.PAUSED
    assert result.inspection.choice is not None
    assert result.inspection.choice.kind == "heroic_recovery_damage"
    return game


def test_initiative_is_perception_total_and_pc_ties_are_a_saved_choice(tmp_path: Path) -> None:
    game = Encounter.start(S2_SETUP, rolls=(10, 10, 10, 10))
    choice = game.inspect().choice
    assert choice is not None and choice.kind == "initiative_hero_reroll"
    assert choice.details == ("Original: d20 10 + 6 = 16.",)

    first_path = tmp_path / "initiative-choice.json"
    game.save(first_path)
    restored = Encounter.load(first_path)
    assert restored.inspect() == game.inspect()

    for _ in range(2):
        choice = restored.inspect().choice
        assert choice is not None
        restored.choose(choice.choice_id, "keep")
    tie = restored.inspect().choice
    assert tie is not None and tie.kind == "initiative_tie"
    assert {option.option_id for option in tie.options} == {"fighter_a", "fighter_b"}

    tie_path = tmp_path / "initiative-tie.json"
    restored.save(tie_path)
    tie_loaded = Encounter.load(tie_path)
    assert tie_loaded.inspect() == restored.inspect()
    tie_loaded.choose(tie.choice_id, "fighter_b")
    order = [actor.actor_id for actor in tie_loaded.inspect().actors]
    assert order.index("fighter_b") < order.index("fighter_a")
    fighter_initiatives = {
        actor.actor_id: actor.initiative
        for actor in tie_loaded.inspect().actors
        if actor.actor_id in {"fighter_a", "fighter_b"}
    }
    assert fighter_initiatives == {"fighter_a": 16, "fighter_b": 16}


def test_initiative_hero_reroll_keeps_a_worse_new_result(tmp_path: Path) -> None:
    game = Encounter.start(S2_SETUP, rolls=(18, 10, 8, 9, 2))
    choice = game.inspect().choice
    assert choice is not None and choice.owner_actor_id == "fighter_a"
    assert "24" in choice.details[0]
    path = tmp_path / "before-initiative-reroll.json"
    game.save(path)
    restored = Encounter.load(path)

    result = restored.choose(choice.choice_id, "spend_hero_point", "fighter_a")
    assert result.status is ResultStatus.PAUSED  # Fighter B still owns their initiative choice.
    fighter_a = next(actor for actor in result.inspection.actors if actor.actor_id == "fighter_a")
    assert fighter_a.initiative == 8  # d20 2 + Perception 6, even though it is worse.
    assert fighter_a.hero_points == 0
    assert result.inspection.choice is not None
    assert result.inspection.choice.owner_actor_id == "fighter_b"


def test_initiative_natural_twenty_is_not_promoted_and_exhausted_reroll_rolls_back(tmp_path: Path) -> None:
    game = Encounter.start(S2_SETUP, rolls=(20, 1, 1, 2))
    choice = game.inspect().choice
    assert choice is not None and "20 + 6 = 26" in choice.details[0]
    fighter_a = next(actor for actor in game.inspect().actors if actor.actor_id == "fighter_a")
    assert fighter_a.initiative == 26  # initiative does not gain a degree for natural 20

    save_path = tmp_path / "exhausted-initiative-reroll.json"
    game.save(save_path)
    before = save_path.read_bytes()
    failed = game.choose(choice.choice_id, "spend_hero_point")
    assert failed.status is ResultStatus.REJECTED
    assert "sequence exhausted" in failed.message and "d20" in failed.message
    game.save(save_path)
    assert save_path.read_bytes() == before
    assert game.inspect().choice == choice


def test_strike_hero_choice_holds_effects_costs_once_and_restores(tmp_path: Path) -> None:
    game = Encounter.start(S2_SETUP, rolls=(20, 19, 1, 2, 10, 1))
    _choose_initiative_choices(game)
    assert game.inspect().turn_actor_id == "fighter_a"
    assert game.execute(Stride((Position(2, 1), Position(3, 1), Position(4, 1)))).status is ResultStatus.COMPLETED
    paused = game.execute(Strike("guard_dog_a"))
    assert paused.status is ResultStatus.PAUSED
    choice = paused.inspection.choice
    assert choice is not None and choice.kind == "attack_hero_reroll"
    fighter_a = next(actor for actor in paused.inspection.actors if actor.actor_id == "fighter_a")
    dog = next(actor for actor in paused.inspection.actors if actor.actor_id == "guard_dog_a")
    assert (fighter_a.actions_remaining, fighter_a.strikes_this_turn) == (1, 1)
    assert dog.hp == 8  # no damage while the first check is awaiting its choice

    save_path = tmp_path / "attack-choice.json"
    game.save(save_path)
    restored = Encounter.load(save_path)
    saved_bytes = save_path.read_bytes()
    stale = restored.choose(choice.choice_id + 1, "spend_hero_point")
    assert stale.status is ResultStatus.REJECTED
    assert stale.inspection == restored.inspect()
    wrong_owner = restored.choose(choice.choice_id, "spend_hero_point", "fighter_b")
    assert wrong_owner.status is ResultStatus.REJECTED
    restored.save(save_path)
    assert save_path.read_bytes() == saved_bytes
    assert Encounter.load(save_path).inspect() == paused.inspection

    rerolled = restored.choose(choice.choice_id, "spend_hero_point", "fighter_a")
    assert rerolled.status is ResultStatus.COMPLETED
    strike = next(event for event in rerolled.events if event.check is not None)
    assert strike.check.die == 1
    assert strike.check.attack_count == 1
    assert strike.check.map_penalty == 0
    after = next(actor for actor in rerolled.inspection.actors if actor.actor_id == "fighter_a")
    assert (after.actions_remaining, after.strikes_this_turn, after.hero_points) == (1, 1, 0)
    dog_after = next(actor for actor in rerolled.inspection.actors if actor.actor_id == "guard_dog_a")
    assert dog_after.hp == 8


def test_ordinary_attack_uses_saved_check_then_damages_after_keep(tmp_path: Path) -> None:
    game = Encounter.start(S2_SETUP, rolls=(20, 19, 1, 2, 20, 8))
    _choose_initiative_choices(game)
    game.execute(Stride((Position(2, 1), Position(3, 1), Position(4, 1))))
    paused = game.execute(Strike("guard_dog_a"))
    choice = paused.inspection.choice
    assert choice is not None
    save_path = tmp_path / "attack-keep.json"
    game.save(save_path)
    restored = Encounter.load(save_path)
    result = restored.choose(choice.choice_id, "keep")

    dog = next(actor for actor in result.inspection.actors if actor.actor_id == "guard_dog_a")
    assert dog.hp == 0 and dog.dead and dog.defeated
    assert next(event for event in result.events if event.damage is not None).damage.total == 24
    fighter = next(actor for actor in result.inspection.actors if actor.actor_id == "fighter_a")
    assert (fighter.actions_remaining, fighter.strikes_this_turn) == (1, 1)


def test_knockout_pauses_before_health_effects_then_saves_conditions_and_anchor(tmp_path: Path) -> None:
    game = _run_to_fighter_a_knockout()
    choice = game.inspect().choice
    assert choice is not None
    before = game.inspect()
    save_path = tmp_path / "knockout-choice.json"
    game.save(save_path)
    restored = Encounter.load(save_path)
    assert restored.inspect() == before
    wrong = restored.choose(choice.choice_id, "normal", "fighter_b")
    assert wrong.status is ResultStatus.REJECTED
    assert wrong.inspection == before

    result = restored.choose(choice.choice_id, "normal", "fighter_a")
    fighter_a = next(actor for actor in result.inspection.actors if actor.actor_id == "fighter_a")
    dog_b = next(actor for actor in result.inspection.actors if actor.actor_id == "guard_dog_b")
    assert (fighter_a.hp, fighter_a.dying, fighter_a.wounded) == (0, 2, 0)
    assert fighter_a.unconscious and fighter_a.prone and fighter_a.ac == 12
    assert fighter_a.held_items == () and fighter_a.worn_items == ("breastplate",)
    assert result.inspection.ground_items == ((Position(1, 1), ("longsword",)),)
    order = [actor.actor_id for actor in result.inspection.actors]
    assert order[order.index("fighter_a") + 1] == "guard_dog_b"
    assert result.inspection.turn_actor_id == "guard_dog_b"  # preserve the current turn anchor

    after_path = tmp_path / "knocked-out.json"
    restored.save(after_path)
    loaded = Encounter.load(after_path)
    assert loaded.inspect() == result.inspection
    assert dog_b.actions_remaining == 1


def test_heroic_recovery_at_knockout_spends_all_points_without_wounded() -> None:
    game = _run_to_fighter_a_knockout()
    choice = game.inspect().choice
    assert choice is not None
    result = game.choose(choice.choice_id, "heroic_recovery", "fighter_a")
    fighter_a = next(actor for actor in result.inspection.actors if actor.actor_id == "fighter_a")
    assert fighter_a.hp == 0
    assert fighter_a.dying == 0 and fighter_a.wounded == 0
    assert fighter_a.unconscious and fighter_a.prone
    assert fighter_a.hero_points == 0
    assert result.inspection.ground_items == ((Position(1, 1), ("longsword",)),)


def test_recovery_choice_saves_then_stabilizes_and_adds_wounded_once(tmp_path: Path) -> None:
    game = _run_to_fighter_a_knockout()
    choice = game.inspect().choice
    assert choice is not None
    game.choose(choice.choice_id, "normal")
    paused = game.execute(EndTurn())
    assert paused.status is ResultStatus.COMPLETED  # dog B
    assert game.execute(EndTurn()).status is ResultStatus.COMPLETED  # fighter B
    paused = game.execute(EndTurn())  # dog A; reaches Fighter A
    pre_recovery = paused.inspection.choice
    assert paused.status is ResultStatus.PAUSED
    assert pre_recovery is not None and pre_recovery.kind == "recovery_start_heroic"

    save_path = tmp_path / "pre-recovery.json"
    game.save(save_path)
    restored = Encounter.load(save_path)
    assert restored.inspect() == paused.inspection
    result = restored.choose(pre_recovery.choice_id, "recovery_check")
    recovery_reroll = result.inspection.choice
    assert result.status is ResultStatus.PAUSED
    assert recovery_reroll is not None and recovery_reroll.kind == "recovery_hero_reroll"
    assert recovery_reroll.details[0] == "Original: d20 20 vs DC 12."

    reroll_path = tmp_path / "recovery-reroll.json"
    restored.save(reroll_path)
    reloaded = Encounter.load(reroll_path)
    stabilized = reloaded.choose(recovery_reroll.choice_id, "keep")
    fighter_a = next(actor for actor in stabilized.inspection.actors if actor.actor_id == "fighter_a")
    assert (fighter_a.hp, fighter_a.dying, fighter_a.wounded) == (0, 0, 1)
    assert fighter_a.unconscious and fighter_a.prone
    assert fighter_a.hero_points == 1
    assert stabilized.inspection.choice is None  # no second, redundant recovery prompt


def test_spending_last_point_on_recovery_reroll_leaves_no_heroic_choice() -> None:
    game = _run_to_fighter_a_knockout((1, 1))
    choice = game.inspect().choice
    assert choice is not None
    game.choose(choice.choice_id, "normal")
    for _ in range(3):
        result = game.execute(EndTurn())
        if result.inspection.choice is not None:
            break
    pre_recovery = game.inspect().choice
    assert pre_recovery is not None and pre_recovery.kind == "recovery_start_heroic"
    game.choose(pre_recovery.choice_id, "recovery_check")
    roll_choice = game.inspect().choice
    assert roll_choice is not None and roll_choice.kind == "recovery_hero_reroll"
    result = game.choose(roll_choice.choice_id, "spend_hero_point")
    fighter_a = next(actor for actor in result.inspection.actors if actor.actor_id == "fighter_a")
    assert fighter_a.dead and fighter_a.hero_points == 0
    assert result.inspection.choice is None
    assert any(
        event.kind == "recovery" and "dies from the recovery check" in event.text
        for event in result.events
    )


def test_damage_to_stable_zero_hp_pc_is_unsupported_and_transactional(tmp_path: Path) -> None:
    game = _run_to_fighter_a_knockout(tail=(4,))
    choice = game.inspect().choice
    assert choice is not None
    game.choose(choice.choice_id, "normal")
    game.execute(EndTurn())
    game.execute(EndTurn())
    game.execute(EndTurn())
    recovery_start = game.inspect().choice
    assert recovery_start is not None and recovery_start.kind == "recovery_start_heroic"
    game.choose(recovery_start.choice_id, "heroic_recovery")
    assert game.inspect().turn_actor_id == "guard_dog_b"
    assert next(actor for actor in game.inspect().actors if actor.actor_id == "fighter_a").dying == 0

    before_path = tmp_path / "stable-before.json"
    after_path = tmp_path / "stable-after.json"
    game.save(before_path)
    unsupported = game.execute(Strike("fighter_a"))
    game.save(after_path)
    assert unsupported.status is ResultStatus.UNSUPPORTED
    assert "awaits a product ruling" in unsupported.message
    assert before_path.read_bytes() == after_path.read_bytes()
