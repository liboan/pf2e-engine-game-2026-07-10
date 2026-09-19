"""Source-first direct Wizard spell checks.

Electric Arc (AoN 1509) is a two-action, one-or-two-target, 30-foot arcane
cantrip.  It rolls one 2d4 electricity damage result and each target makes a
separate basic Reflex save.  This first public probe saves at a target-owned
Hero decision before either recipient is finalized.
"""

from pf2e.content import get_definition, get_setup
from pf2e.encounter import Encounter
from pf2e.model import ActiveConditionEffect, Cast, EffectExpiration, EndTurn, Release, ResultStatus, Stride, Position
from pf2e.skill_actions import Escape
from pf2e.terminal import _choose_cast_inputs, run_terminal
from terminal_test_helpers import BoundedInput, BoundedTranscript


def test_tangle_vine_critical_save_escape_restores_ordinary_movement(tmp_path) -> None:
    # Initiative, critical spell attack, then the dog's successful Escape.
    game = Encounter.start(
        get_setup("staged_battle_magic_wizard_movement_spells_prepared"),
        rolls=(20, 1, 1, 20, 20),
    )
    while game.inspect().choice is not None:
        choice = game.inspect().choice
        assert choice is not None
        assert game.choose(choice.choice_id, "keep", choice.owner_actor_id).status is ResultStatus.COMPLETED

    paused = game.execute(Cast("tangle_vine", target_id="dog_a"))
    assert paused.status is ResultStatus.PAUSED
    choice = paused.inspection.choice
    assert choice is not None
    assert game.choose(choice.choice_id, "keep", choice.owner_actor_id).status is ResultStatus.COMPLETED
    assert game.effective_speed_ft("dog_a") == 20
    game.save(tmp_path / "tangle-vine-active.json")
    game = Encounter.load(tmp_path / "tangle-vine-active.json")

    assert game.execute(Cast("shield")).status is ResultStatus.COMPLETED
    result = game.execute(Escape(
        next(effect.effect_id for effect in game._state.condition_effects if effect.target_actor_id == "dog_a" and effect.kind == "immobilized"),
        "athletics",
    ))
    assert result.status is ResultStatus.PAUSED
    choice = result.inspection.choice
    assert choice is not None
    assert game.choose(choice.choice_id, "stay", choice.owner_actor_id).status is ResultStatus.COMPLETED
    assert game.effective_speed_ft("dog_a") == 30
    assert game.execute(Stride((Position(4, 1),))).status is ResultStatus.COMPLETED


def test_gale_blast_saves_each_recipient_then_pushes_after_damage() -> None:
    game = Encounter.start(
        get_setup("staged_battle_magic_wizard_movement_spells_prepared"),
        # Initiative, shared d6, Dog A's critically failed Fortitude save.
        rolls=(20, 1, 1, 4, 1),
    )
    while game.inspect().choice is not None:
        choice = game.inspect().choice
        assert choice is not None
        game.choose(choice.choice_id, "keep", choice.owner_actor_id)
    game._state.creatures["dog_a"].position = Position(2, 2)
    game._state.creatures["dog_b"].position = Position(6, 4)
    result = game.execute(Cast("gale_blast"))
    assert result.status is ResultStatus.PAUSED
    choice = result.inspection.choice
    assert choice is not None and choice.kind == "spell_self_inclusion"
    result = game.choose(choice.choice_id, "exclude", choice.owner_actor_id)
    assert result.status is ResultStatus.COMPLETED
    assert game._state.creatures["dog_a"].position == Position(4, 2)
    assert any(event.kind == "spell_damage" for event in result.events)
    assert any(event.kind == "forced_movement" for event in result.events)


def test_ordinary_tangle_escape_removes_only_its_linked_speed_effect() -> None:
    game = Encounter.start(get_setup("staged_battle_magic_wizard_movement_spells_prepared"), rolls=(20, 1, 1, 10, 20))
    while game.inspect().choice is not None:
        choice = game.inspect().choice
        assert choice is not None
        game.choose(choice.choice_id, "keep", choice.owner_actor_id)
    result = game.execute(Cast("tangle_vine", target_id="dog_a"))
    assert result.status is ResultStatus.PAUSED
    choice = result.inspection.choice
    assert choice is not None
    game.choose(choice.choice_id, "keep", choice.owner_actor_id)
    game._state.condition_effects.append(ActiveConditionEffect(
        "unrelated-grapple", "grabbed", "wizard", "dog_a", 1,
        EffectExpiration("wizard", "end", 2), 17,
    ))
    assert game.execute(Cast("shield")).status is ResultStatus.COMPLETED
    speed_id = next(effect.effect_id for effect in game._state.condition_effects if effect.kind == "speed_penalty")
    result = game.execute(Escape(speed_id, "athletics"))
    assert result.status is ResultStatus.PAUSED
    choice = result.inspection.choice
    assert choice is not None
    game.choose(choice.choice_id, "stay", choice.owner_actor_id)
    assert not any(effect.effect_id.startswith("tangle_vine:") for effect in game._state.condition_effects)
    assert any(effect.effect_id == "unrelated-grapple" for effect in game._state.condition_effects)


def test_gale_immobilized_external_force_check_uses_no_map_and_keeps_hold() -> None:
    game = Encounter.start(get_setup("staged_battle_magic_wizard_movement_spells_prepared"), rolls=(20, 1, 1, 1, 1, 20))
    while game.inspect().choice is not None:
        choice = game.inspect().choice
        assert choice is not None
        game.choose(choice.choice_id, "keep", choice.owner_actor_id)
    game._state.creatures["dog_a"].position = Position(2, 2)
    game._state.creatures["dog_b"].position = Position(6, 4)
    game._state.creatures["wizard"].strikes_this_turn = 2
    game._state.condition_effects.append(ActiveConditionEffect(
        "holding-vine", "immobilized", "wizard", "dog_a", 1, EffectExpiration("wizard", "start", 9), 17,
    ))
    result = game.execute(Cast("gale_blast", include_self=False))
    assert result.status is ResultStatus.COMPLETED
    assert game._state.creatures["dog_a"].position == Position(4, 2)
    assert any(effect.effect_id == "holding-vine" for effect in game._state.condition_effects)
    force_check = next(event.check for event in result.events if event.kind == "forced_movement")
    assert force_check is not None and (force_check.modifier, force_check.map_penalty) == (7, 0)
    assert game._state.creatures["wizard"].strikes_this_turn == 2


def test_movement_spells_complete_a_healthy_continuous_encounter() -> None:
    game = Encounter.start(
        get_setup("staged_battle_magic_wizard_movement_spells_prepared"),
        # Initiative; Tangle attack; then shared Gale d6 and each Fortitude save.
        rolls=(20, 1, 1, 10, 4, 1, 1),
    )
    while game.inspect().choice is not None:
        choice = game.inspect().choice
        assert choice is not None
        game.choose(choice.choice_id, "keep", choice.owner_actor_id)
    # This supported flat-grid fixture keeps both targets in the emanation for
    # the actual continuous spell sequence; no movement reaction is invoked.
    game._state.creatures["dog_a"].position = Position(2, 1)
    game._state.creatures["dog_b"].position = Position(2, 2)
    result = game.execute(Cast("tangle_vine", target_id="dog_a"))
    assert result.status is ResultStatus.PAUSED
    choice = result.inspection.choice
    assert choice is not None
    assert game.choose(choice.choice_id, "keep", choice.owner_actor_id).status is ResultStatus.COMPLETED
    assert game.execute(Cast("shield")).status is ResultStatus.COMPLETED
    assert game.execute(EndTurn()).status is ResultStatus.COMPLETED
    assert game.execute(EndTurn()).status is ResultStatus.COMPLETED
    result = game.execute(Cast("gale_blast", include_self=False))
    assert result.status is ResultStatus.COMPLETED
    assert not game.inspect().in_progress
    assert game._state.creatures["wizard"].hp == 16
    assert {event.target_id for event in result.events if event.kind == "forced_movement"} == {"dog_a", "dog_b"}


def test_bounded_terminal_gale_blast_includes_caster_and_resolves_damage() -> None:
    transcript = BoundedTranscript(max_lines=300, max_chars=40_000)
    state = {"menu": "", "prompt": "", "cast": True}

    def output(line: str) -> None:
        transcript.append(line)
        if line.startswith("1. "):
            state["menu"] = line
        if line.endswith(":"):
            state["prompt"] = line

    def choose(label: str) -> str:
        for row in state["menu"].splitlines():
            number, text = row.split(". ", 1)
            if text.startswith(label):
                return number
        raise AssertionError(f"missing terminal menu item {label!r}: {state['menu']!r}")

    def scripted_input() -> str:
        prompt = state["prompt"]
        if prompt == "Choice prompt action:":
            return choose("Resolve this choice")
        if prompt == "Choice option number:":
            return choose("Include self") if "Include self" in state["menu"] else choose("Keep")
        if prompt == "Choice:":
            if state["cast"]:
                state["cast"] = False
                return choose("Cast")
            return choose("Quit")
        if prompt == "Spell number:":
            return choose("Gale Blast")
        if prompt == "Casting mode:":
            return choose("2 actions")
        raise AssertionError(f"unexpected terminal prompt: {prompt!r}")

    assert run_terminal(
        setup=get_setup("staged_battle_magic_wizard_movement_spells_prepared"),
        # Initiative, shared d6, then the caster's Fortitude save.
        rolls=(20, 1, 1, 4, 1),
        input_fn=BoundedInput(scripted_input, max_calls=35), output_fn=output,
    ) == 0
    rendered = "\n".join(transcript)
    assert "Rejected:" not in rendered, rendered
    assert "Gale Blast deals 8 bludgeoning to Battle Magic Wizard." in rendered


def test_electric_arc_saves_before_each_recipient_resolves_once(tmp_path) -> None:
    game = Encounter.start(
        get_setup("staged_battle_magic_wizard_breathe_hero_save"),
        rolls=(20, 1, 1, 1, 3, 4, 10, 10),
    )
    while game.inspect().choice is not None:
        choice = game.inspect().choice
        assert choice is not None
        game.choose(choice.choice_id, "keep", choice.owner_actor_id)
    result = game.execute(Cast("electric_arc", target_ids=("wizard_ally", "dog_a")))
    assert result.status is ResultStatus.PAUSED
    assert game.inspect().choice is not None
    game.save(tmp_path / "electric-arc.json")
    restored = Encounter.load(tmp_path / "electric-arc.json")
    pending = restored.inspect().choice
    assert pending is not None and pending.kind == "spell_save_hero_reroll"
    result = restored.choose(pending.choice_id, "keep", pending.owner_actor_id)
    assert result.status is ResultStatus.COMPLETED
    damage = [
        (event.target_id, event.damage.total)
        for event in result.events
        if event.kind == "spell_damage" and event.damage is not None
    ]
    # One shared 3+4 roll: the ally fails and the dog succeeds (half seven).
    assert damage == [("wizard_ally", 7), ("dog_a", 3)]


def test_electric_arc_ends_a_healthy_continuous_encounter() -> None:
    """One shared 8-damage ordinary failure defeats both full-health dogs."""
    game = Encounter.start(
        get_setup("staged_battle_magic_wizard_telekinetic_projectile_prepared"),
        rolls=(20, 1, 1, 4, 4, 2, 2),
    )
    while game.inspect().choice is not None:
        choice = game.inspect().choice
        assert choice is not None
        game.choose(choice.choice_id, "keep", choice.owner_actor_id)

    result = game.execute(Cast("electric_arc", target_ids=("dog_a", "dog_b")))

    assert result.status is ResultStatus.COMPLETED
    assert not game.inspect().in_progress
    assert game.inspect().winner_team == "blue"
    assert game._state.creatures["wizard"].hp == 16
    assert all(game._state.creatures[actor_id].defeated for actor_id in ("dog_a", "dog_b"))
    damage = [event.damage for event in result.events if event.kind == "spell_damage"]
    assert [(entry.rolled_total, entry.total, entry.components[0].rolls) for entry in damage if entry] == [
        (8, 8, (4, 4)),
        (8, 8, (4, 4)),
    ]


def test_bounded_terminal_selects_electric_arc_and_two_distinct_recipients() -> None:
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
            return choose("Keep initiative")
        if prompt == "Choice:":
            if state["cast"]:
                state["cast"] = False
                return choose("Cast")
            return choose("Quit")
        if prompt == "Spell number:":
            return choose("Electric Arc", prefix=True)
        if prompt == "Casting mode:":
            return choose("2 actions")
        if prompt == "Prepared slot:":
            return "1"
        if prompt == "Target number:":
            return "1"
        raise AssertionError(f"unexpected terminal prompt: {prompt!r}")

    assert run_terminal(
        setup=get_setup("staged_battle_magic_wizard_vs_two_guard_dogs"),
        rolls=(20, 1, 1, 4, 4, 2, 2),
        input_fn=BoundedInput(scripted_input, max_calls=35), output_fn=output,
    ) == 0
    rendered = "\n".join(transcript)
    assert "Rejected:" not in rendered, rendered
    assert "commits Electric Arc" in rendered
    assert "Encounter finished." in rendered


def test_direct_spell_effects_persist_with_their_printed_rank_one_boundaries(tmp_path) -> None:
    def settled(spell_id: str, **kwargs):
        game = Encounter.start(
            get_setup("staged_battle_magic_wizard_vs_two_guard_dogs"),
            rolls=(20, 1, 1, 1, 3, 4),
        )
        while game.inspect().choice is not None:
            choice = game.inspect().choice
            assert choice is not None
            game.choose(choice.choice_id, "keep", choice.owner_actor_id)
        result = game.execute(Cast(spell_id, **kwargs))
        assert result.status is ResultStatus.COMPLETED
        return game

    frostbite = settled("frostbite", target_id="dog_a")
    frostbite.save(tmp_path / "frostbite.json")
    restored = Encounter.load(tmp_path / "frostbite.json")
    assert any(effect.kind == "frostbite_weakness" and effect.value == 1 for effect in restored._state.active_effects)

    enfeeble = settled("enfeeble", target_id="dog_a")
    assert enfeeble._enfeebled_value(enfeeble._state, "dog_a") == 3
    effect = next(effect for effect in enfeeble._state.active_effects if effect.kind == "enfeebled")
    assert effect.expires_at_source_start == enfeeble._state.actor_start_counts["wizard"] + 10

    runic_body = Encounter.start(
        get_setup("staged_battle_magic_wizard_runic_body_prepared"),
        rolls=(20, 1, 1, 1, 3, 4),
    )
    while runic_body.inspect().choice is not None:
        choice = runic_body.inspect().choice
        assert choice is not None
        runic_body.choose(choice.choice_id, "keep", choice.owner_actor_id)
    result = runic_body.execute(Cast("runic_body", target_id="wizard"))
    assert result.status is ResultStatus.COMPLETED
    wizard = runic_body._state.creatures["wizard"]
    profile = runic_body._weapon_rune_profile_for_attack(
        runic_body._state, wizard,
        next(attack for attack in get_definition(wizard.definition_id).attacks if attack.attack_id == "fist"),
    )
    assert profile is not None and profile.potency == 1 and profile.striking_dice == 2


def test_telekinetic_projectile_uses_a_released_ground_item_and_saved_spell_attack(tmp_path) -> None:
    game = Encounter.start(
        get_setup("staged_battle_magic_wizard_telekinetic_projectile_prepared"),
        rolls=(20, 1, 1, 20, 3, 4),
    )
    while game.inspect().choice is not None:
        choice = game.inspect().choice
        assert choice is not None
        game.choose(choice.choice_id, "keep", choice.owner_actor_id)
    assert game.execute(Release("wizard:bonded_staff")).status is ResultStatus.COMPLETED
    result = game.execute(Cast(
        "telekinetic_projectile", "dog_a", item_id="wizard:bonded_staff",
    ))
    assert result.status is ResultStatus.PAUSED
    check = next(event.check for event in result.events if event.check is not None)
    assert check is not None and check.attack_count == 1 and check.map_penalty == 0
    game.save(tmp_path / "telekinetic-projectile.json")
    restored = Encounter.load(tmp_path / "telekinetic-projectile.json")
    choice = restored.inspect().choice
    assert choice is not None and choice.kind == "spell_attack_hero_reroll"
    result = restored.choose(choice.choice_id, "keep", choice.owner_actor_id)
    assert result.status is ResultStatus.COMPLETED
    assert any(event.kind == "spell_damage" and event.damage is not None and event.damage.total == 14 for event in result.events)


def test_terminal_collects_the_ground_item_for_telekinetic_projectile() -> None:
    game = Encounter.start(
        get_setup("staged_battle_magic_wizard_telekinetic_projectile_prepared"), rolls=(20, 1, 1),
    )
    while game.inspect().choice is not None:
        choice = game.inspect().choice
        assert choice is not None
        game.choose(choice.choice_id, "keep", choice.owner_actor_id)
    assert game.execute(Release("wizard:bonded_staff")).status is ResultStatus.COMPLETED
    wizard = game._state.creatures["wizard"]
    answers = iter(("1", "1", "1", "1"))
    result = _choose_cast_inputs(
        game._spell_options(wizard, game._state), game.inspect(), lambda: next(answers), lambda _line: None,
    )
    assert result == ("telekinetic_projectile", "dog_a", 2, None, None, "wizard:bonded_staff")
