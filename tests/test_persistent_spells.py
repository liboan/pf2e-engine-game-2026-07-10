"""Persistent Damage (AoN Conditions 86) and three source-grounded cantrips.

The probes keep the condition literal: one target/type record, one combined
end-turn damage event, then independent DC 15 recovery checks.
"""

from pf2e.content import get_setup
from pf2e.encounter import Encounter
from pf2e.model import Cast, EndTurn, PersistentDamageEffect, Position, ResultStatus
from pf2e.terminal import run_terminal
from terminal_test_helpers import BoundedInput, BoundedTranscript


def _settled_game(*, rolls):
    game = Encounter.start(get_setup("staged_battle_magic_wizard_vs_two_guard_dogs"), rolls=rolls)
    while game.inspect().choice is not None:
        choice = game.inspect().choice
        assert choice is not None
        assert game.choose(choice.choice_id, "keep", choice.owner_actor_id).status is ResultStatus.COMPLETED
    return game


def _keep_pending(game):
    choice = game.inspect().choice
    assert choice is not None
    return game.choose(choice.choice_id, "keep", choice.owner_actor_id)


def test_persistent_tick_saves_before_damage_and_rolls_one_combined_event(tmp_path) -> None:
    # Initiative, then Dog A's fire d4=3 and its recovery checks 15/14.
    game = _settled_game(rolls=(20, 1, 1, 3, 15, 14))
    state = game._state
    state.persistent_effects[:] = [
        PersistentDamageEffect("fire", "wizard", "dog_a", "ignition", "fire", (4,), 0, 60),
        PersistentDamageEffect("bleed", "wizard", "dog_a", "gouging_claw", "bleed", (), 2, 60),
    ]
    game.save(tmp_path / "before-persistent-tick.json")
    game = Encounter.load(tmp_path / "before-persistent-tick.json")

    assert game.execute(EndTurn()).status is ResultStatus.COMPLETED  # Wizard -> Dog A.
    result = game.execute(EndTurn())
    assert result.status is ResultStatus.COMPLETED
    applied = [event for event in result.events if event.kind == "persistent_damage"]
    assert len(applied) == 1
    assert applied[0].damage is not None and applied[0].damage.total == 5
    assert game._state.creatures["dog_a"].hp == 3
    assert [effect.effect_id for effect in game._state.persistent_effects] == ["bleed"]


def test_expired_persistent_record_is_purged_at_round_wrap_before_save(tmp_path) -> None:
    game = _settled_game(rolls=(20, 1, 1, 1, 14))
    game._state.persistent_effects.append(
        PersistentDamageEffect("expires-at-wrap", "wizard", "dog_b", "ignition", "fire", (4,), 0, 6)
    )
    # The next turn cycle advances the combat clock to six seconds just before
    # the Wizard's next start. The local one-minute convention uses this same
    # absolute-expiry boundary, so a save after wrap must stay loadable.
    assert game.execute(EndTurn()).status is ResultStatus.COMPLETED
    assert game.execute(EndTurn()).status is ResultStatus.COMPLETED
    assert game.execute(EndTurn()).status is ResultStatus.COMPLETED
    assert game._state.world_time_seconds == 6
    assert not game._state.persistent_effects
    game.save(tmp_path / "expired-persistent-purged.json")
    assert not Encounter.load(tmp_path / "expired-persistent-purged.json")._state.persistent_effects


def test_persistent_recovery_hero_save_does_not_repeat_committed_damage(tmp_path) -> None:
    # Wizard takes fire 3, keeps a 14, saves during the Hero prompt, then
    # rerolls a 15.  The restored prompt must not draw the d4 a second time.
    game = _settled_game(rolls=(20, 1, 1, 3, 14, 15))
    wizard = game._state.creatures["wizard"]
    wizard.hero_points = 1
    game._state.persistent_effects.append(
        PersistentDamageEffect("fire", "wizard", "wizard", "ignition", "fire", (4,), 0, 60)
    )
    result = game.execute(EndTurn())
    assert result.status is ResultStatus.PAUSED
    assert game._state.creatures["wizard"].hp == 13
    pending = game.inspect().choice
    assert pending is not None and pending.kind == "persistent_recovery"
    game.save(tmp_path / "persistent-recovery.json")
    restored = Encounter.load(tmp_path / "persistent-recovery.json")
    pending = restored.inspect().choice
    assert pending is not None
    result = restored.choose(pending.choice_id, "spend_hero_point", "wizard")
    assert result.status is ResultStatus.COMPLETED
    assert restored._state.creatures["wizard"].hp == 13
    assert not restored._state.persistent_effects
    assert not [event for event in result.events if event.kind == "persistent_damage"]


def test_persistent_same_type_stronger_replaces_and_recovers_without_old_effect() -> None:
    game = _settled_game(rolls=(20, 1, 1, 15))
    state = game._state
    target = state.creatures["dog_a"]
    caster = state.creatures["wizard"]
    game._apply_persistent_effect(state, caster, target, "gouging_claw", "bleed", flat=2)
    game._apply_persistent_effect(state, caster, target, "gouging_claw", "bleed", flat=4)
    assert [(effect.effect_id, effect.flat) for effect in state.persistent_effects] == [
        (state.persistent_effects[0].effect_id, 4)
    ]
    game.execute(EndTurn())
    result = game.execute(EndTurn())
    damage = next(event.damage for event in result.events if event.kind == "persistent_damage")
    assert damage is not None and damage.total == 4
    assert not game._state.persistent_effects


def test_ignition_gouging_claw_and_caustic_blast_cast_through_public_damage() -> None:
    ignition = _settled_game(rolls=(20, 1, 1, 9, 1, 1))
    result = ignition.execute(Cast("ignition", target_id="dog_a", spell_mode="ranged"))
    if result.status is ResultStatus.PAUSED:
        result = _keep_pending(ignition)
    assert result.status is ResultStatus.COMPLETED
    assert any(event.kind == "spell_damage" and event.damage and event.damage.total == 2 for event in result.events)

    ignition_critical = _settled_game(rolls=(20, 1, 1, 20, 1, 1))
    result = ignition_critical.execute(Cast("ignition", target_id="dog_a", spell_mode="ranged"))
    if result.status is ResultStatus.PAUSED:
        result = _keep_pending(ignition_critical)
    assert result.status is ResultStatus.COMPLETED
    assert any(effect.damage_type == "fire" and effect.dice == (4,) for effect in ignition_critical._state.persistent_effects)

    melee_ignition = _settled_game(rolls=(20, 1, 1, 9, 1, 1))
    melee_ignition._state.creatures["dog_a"].position = Position(
        melee_ignition._state.creatures["wizard"].position.x + 1,
        melee_ignition._state.creatures["wizard"].position.y,
    )
    result = melee_ignition.execute(Cast("ignition", target_id="dog_a", spell_mode="melee"))
    if result.status is ResultStatus.PAUSED:
        result = _keep_pending(melee_ignition)
    damage = next(event.damage for event in result.events if event.kind == "spell_damage")
    assert damage is not None and damage.components[0].dice == (6, 6)

    claw = _settled_game(rolls=(20, 1, 1, 9, 1, 1))
    claw._state.creatures["dog_a"].position = Position(
        claw._state.creatures["wizard"].position.x + 1,
        claw._state.creatures["wizard"].position.y,
    )
    result = claw.execute(Cast("gouging_claw", target_id="dog_a", spell_mode="slashing"))
    if result.status is ResultStatus.PAUSED:
        result = _keep_pending(claw)
    assert result.status is ResultStatus.COMPLETED
    assert any(effect.damage_type == "bleed" and effect.flat == 2 for effect in claw._state.persistent_effects)

    piercing_claw = _settled_game(rolls=(20, 1, 1, 9, 1, 1))
    piercing_claw._state.creatures["dog_a"].position = Position(
        piercing_claw._state.creatures["wizard"].position.x + 1,
        piercing_claw._state.creatures["wizard"].position.y,
    )
    result = piercing_claw.execute(Cast("gouging_claw", target_id="dog_a", spell_mode="piercing"))
    if result.status is ResultStatus.PAUSED:
        result = _keep_pending(piercing_claw)
    damage = next(event.damage for event in result.events if event.kind == "spell_damage")
    assert damage is not None and damage.components[0].damage_type == "piercing"

    caustic = _settled_game(rolls=(20, 1, 1, 4, 2, 2, 2))
    caustic._state.creatures["dog_a"].position = Position(
        caustic._state.creatures["wizard"].position.x + 1,
        caustic._state.creatures["wizard"].position.y,
    )
    result = caustic.execute(Cast("caustic_blast", target_id="dog_a"))
    while result.status is ResultStatus.PAUSED:
        result = _keep_pending(caustic)
    assert result.status is ResultStatus.COMPLETED
    assert {event.target_id for event in result.events if event.kind == "spell_damage"} >= {"wizard", "dog_a"}
    assert any(effect.target_actor_id == "wizard" and effect.damage_type == "acid" and effect.flat == 1 for effect in caustic._state.persistent_effects)


def test_bounded_terminal_selects_ignition_and_resolves_its_saved_attack() -> None:
    transcript = BoundedTranscript(max_lines=260, max_chars=40_000)
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
            return choose("Keep", prefix=True)
        if prompt == "Choice:":
            if state["cast"]:
                state["cast"] = False
                return choose("Cast")
            return choose("Quit")
        if prompt == "Spell number:":
            return choose("Ignition", prefix=True)
        if prompt == "Casting mode:":
            return choose("2 actions")
        if prompt == "Ignition form:":
            return choose("Ranged", prefix=True)
        if prompt == "Target number:":
            return "1"
        raise AssertionError(f"unexpected terminal prompt: {prompt!r}")

    assert run_terminal(
        setup=get_setup("staged_battle_magic_wizard_vs_two_guard_dogs"),
        rolls=(20, 1, 1, 9, 1, 1),
        input_fn=BoundedInput(scripted_input, max_calls=35), output_fn=output,
    ) == 0
    rendered = "\n".join(transcript)
    assert "Rejected:" not in rendered, rendered
    assert "commits Ignition" in rendered


def test_last_enemy_defeat_waits_for_healthy_persistent_target_then_allows_next_scene(tmp_path) -> None:
    # Two dogs fall to the shared arc.  The healthy Wizard still has a fire
    # condition, so initiative remains alive until their next end-turn tick.
    game = _settled_game(rolls=(20, 1, 1, 4, 4, 2, 2, 3, 15, 20, 1))
    game._state.persistent_effects.append(
        PersistentDamageEffect("fire", "dog_a", "wizard", "ignition", "fire", (4,), 0, 60)
    )
    result = game.execute(Cast("electric_arc", target_ids=("dog_a", "dog_b")))
    assert result.status is ResultStatus.COMPLETED
    assert game.inspect().in_progress
    result = game.execute(EndTurn())
    if result.status is ResultStatus.PAUSED:
        result = _keep_pending(game)
    assert result.status is ResultStatus.COMPLETED
    assert not game.inspect().in_progress
    assert game._state.creatures["wizard"].hp == 13
    assert not game._state.persistent_effects
    assert game.refocus("wizard").status is ResultStatus.COMPLETED
    game.save(tmp_path / "post-persistent-refocus.json")
    restored = Encounter.load(tmp_path / "post-persistent-refocus.json")
    transitioned = restored.next_encounter(get_setup("staged_battle_magic_wizard_next_guard_dog"))
    while transitioned.status is ResultStatus.PAUSED:
        transitioned = _keep_pending(restored)
    assert transitioned.status is ResultStatus.COMPLETED
