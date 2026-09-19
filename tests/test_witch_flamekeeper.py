from dataclasses import replace

import pf2e.content as content
from pf2e.content import FAITHS_FLAMEKEEPER_NEXT_SETUP, FAITHS_FLAMEKEEPER_SETUP
from pf2e.encounter import Encounter
from pf2e.model import Cast, Choose, EndTurn, Interact, Position, Strike, Stride, Sustain
from pf2e.persistence import load_encounter, save_encounter
from pf2e.terminal import _choose_cast_inputs
from pf2e.witch import CommandFamiliar, FamiliarPickup, FamiliarRelease, FamiliarStride, PatronsPuppet


def _first_witch_turn():
    game = Encounter.start(FAITHS_FLAMEKEEPER_SETUP, rolls=[20, 8, 7, 1])
    while game._state.pending_choice is not None:
        pending = game._state.pending_choice
        game.execute(Choose(pending.choice_id, "keep", pending.owner_actor_id))
    assert game.inspect().turn_actor_id == "witch"
    return game


def test_flamekeeper_familiar_command_stoke_restore_and_save(tmp_path):
    game = _first_witch_turn()
    state = game._state
    fox = state.creatures["fox"]
    witch = state.creatures["witch"]
    assert "fox" not in state.initiative_order
    assert "fox" in {actor.actor_id for actor in game.inspect().actors}
    assert fox.position == witch.position
    token = witch.held_items.pop()
    state.ground_items[Position(2, 2)] = [token]

    result = game.execute(CommandFamiliar("fox", (
        FamiliarStride((Position(2, 2),)), FamiliarPickup(token),
    )))
    assert result.status.value == "completed"
    assert game._state.creatures["fox"].held_items == [token]
    assert game._state.creatures["witch"].actions_remaining == 2
    assert game.execute(Cast("stoke_the_heart", target_id="ally")).status.value == "paused"
    pending = game._state.pending_choice
    assert pending is not None and pending.kind == "witch_restored_spirit_timing"

    save_path = tmp_path / "witch-pending.json"
    save_encounter(save_path, game._state, game._dice)
    resumed = Encounter.load(save_path)
    pending = resumed._state.pending_choice
    assert pending is not None
    assert resumed.execute(Choose(pending.choice_id, "after", "witch")).status.value == "paused"
    pending = resumed._state.pending_choice
    assert pending is not None and pending.kind == "witch_restored_spirit"
    assert resumed.execute(Choose(pending.choice_id, "ally", "witch")).status.value == "paused"
    pending = resumed._state.pending_choice
    assert pending is not None and pending.kind == "witch_restored_spirit_willingness"
    assert resumed.execute(Choose(pending.choice_id, "willing", "ally")).status.value == "completed"
    game = resumed
    assert game._state.creatures["ally"].temporary_hp == 2
    stoke = next(effect for effect in game._state.active_effects if effect.kind == "stoke_the_heart")
    assert game.execute(Sustain(stoke.effect_id)).status.value == "completed"

    save_path = tmp_path / "witch.json"
    save_encounter(save_path, game._state, game._dice)
    loaded, _dice = load_encounter(save_path)
    assert loaded.initiative_order == ["witch", "ally", "enemy"]
    assert loaded.creatures["fox"].held_items == [token]
    assert loaded.creatures["ally"].temporary_hp == 2
    assert any(effect.kind == "stoke_the_heart" for effect in loaded.active_effects)


def test_patrons_puppet_is_free_and_familiar_has_no_third_action():
    game = _first_witch_turn()
    state = game._state
    result = game.execute(PatronsPuppet("fox", (
        FamiliarStride((Position(2, 2),)), FamiliarStride((Position(1, 2),)),
    )))
    assert result.status.value == "paused"
    pending = game._state.pending_choice
    assert pending is not None and pending.kind == "witch_restored_spirit_timing"
    assert game.execute(Choose(pending.choice_id, "before:witch", "witch")).status.value == "completed"
    assert game._state.creatures["witch"].actions_remaining == 3
    assert game._state.creatures["witch"].focus_points == 0
    # Patron's Puppet is itself a hex, so a later hex Cast loses its action.
    before = game._state.creatures["witch"].actions_remaining
    assert game.execute(Cast("stoke_the_heart", target_id="ally")).status.value == "completed"
    assert game._state.creatures["witch"].actions_remaining == before - 1
    assert not any(effect.kind == "stoke_the_heart" for effect in game._state.active_effects)
    rejected = game.execute(PatronsPuppet("fox", (FamiliarStride((Position(2, 2),)),)))
    assert rejected.status.value == "rejected"


def test_restored_spirit_can_happen_before_stoke_resolution():
    game = _first_witch_turn()
    assert game.execute(Cast("stoke_the_heart", target_id="ally")).status.value == "paused"
    pending = game._state.pending_choice
    assert pending is not None and pending.kind == "witch_restored_spirit_timing"
    assert game.execute(Choose(pending.choice_id, "before:ally", "witch")).status.value == "paused"
    pending = game._state.pending_choice
    assert pending is not None and pending.kind == "witch_restored_spirit_willingness"
    result = game.execute(Choose(pending.choice_id, "willing", "ally"))
    assert result.status.value == "completed"
    assert game._state.creatures["ally"].temporary_hp == 2
    assert any(effect.kind == "stoke_the_heart" for effect in game._state.active_effects)


def test_stoke_blocks_later_patrons_puppet_without_spending_focus():
    game = _first_witch_turn()
    assert game.execute(Cast("stoke_the_heart", target_id="ally")).status.value == "paused"
    pending = game._state.pending_choice
    assert pending is not None
    assert game.execute(Choose(pending.choice_id, "before:witch", "witch")).status.value == "completed"
    result = game.execute(PatronsPuppet("fox", (FamiliarStride((Position(2, 2),)),)))
    assert result.status.value == "rejected"  # Puppet is only at turn start.
    assert game._state.creatures["witch"].focus_points == 1


def test_command_uses_common_speaking_target_will_save(tmp_path):
    game = _first_witch_turn()
    result = game.execute(Cast("command", target_id="enemy", spell_mode="stand"))
    assert result.status.value == "completed"
    assert any(event.kind == "command_save" for event in result.events)
    assert any(effect.kind == "commanded" for effect in game._state.condition_effects)

    save_path = tmp_path / "commanded.json"
    game.save(save_path)
    loaded = Encounter.load(save_path)
    assert any(effect.kind == "commanded" for effect in loaded._state.condition_effects)


def test_forbidding_ward_binds_one_ally_and_enemy_and_sustains_without_hex(tmp_path, monkeypatch):
    game = _first_witch_turn()
    result = game.execute(Cast("forbidding_ward", target_ids=("ally", "enemy")))
    assert result.status.value == "completed"
    ward = next(effect for effect in game._state.active_effects if effect.kind == "forbidding_ward")
    assert (ward.target_actor_id, ward.selected_enemy_actor_id, ward.value) == ("ally", "enemy", 1)
    immutable_limit = (ward.sustain_limit_source_start, ward.sustain_limit_world_time)

    save_path = tmp_path / "forbidding-ward.json"
    save_encounter(save_path, game._state, game._dice)
    state, dice = load_encounter(save_path)
    game = Encounter(state, dice)
    ward = next(effect for effect in game._state.active_effects if effect.kind == "forbidding_ward")
    assert (ward.target_actor_id, ward.selected_enemy_actor_id) == ("ally", "enemy")

    assert game.execute(EndTurn()).status.value == "completed"
    assert game.execute(EndTurn()).status.value == "completed"
    assert game.execute(Stride((Position(4, 2), Position(3, 2)))).status.value == "completed"
    strike = game.execute(Strike("ally", "club"))
    check = next(event.check for event in strike.events if event.kind == "strike")
    assert check is not None and check.dc == 16  # Ally's printed 15 AC + the Ward's status bonus.

    enemy_caster_setup = replace(
        FAITHS_FLAMEKEEPER_SETUP,
        setup_id="witch_forbidding_ward_enemy_save",
        placements=tuple(
            replace(placement, definition_id="faiths_flamekeeper_witch_level_1", label="Enemy Witch")
            if placement.actor_id == "enemy" else placement
            for placement in FAITHS_FLAMEKEEPER_SETUP.placements
        ),
    )
    monkeypatch.setattr(
        content,
        "_STAGED_SETUPS",
        content._STAGED_SETUPS | {enemy_caster_setup.setup_id: enemy_caster_setup},
    )
    enemy_caster_game = Encounter.start(enemy_caster_setup, rolls=[20, 8, 7, 1, 20])
    while enemy_caster_game._state.pending_choice is not None:
        pending = enemy_caster_game._state.pending_choice
        enemy_caster_game.execute(Choose(pending.choice_id, "keep", pending.owner_actor_id))
    assert enemy_caster_game.execute(
        Cast("forbidding_ward", target_ids=("ally", "enemy"))
    ).status.value == "completed"
    assert enemy_caster_game.execute(EndTurn()).status.value == "completed"
    assert enemy_caster_game.execute(EndTurn()).status.value == "completed"
    enemy_command = enemy_caster_game.execute(
        Cast("command", target_id="ally", spell_mode="stand")
    )
    save_check = next(event.check for event in enemy_command.events if event.kind == "command_save")
    assert save_check is not None
    assert any(modifier.source == "Forbidding Ward" for modifier in save_check.modifier_breakdown)

    assert game.execute(EndTurn()).status.value == "completed"
    refreshed = game.execute(Sustain(ward.effect_id))
    assert refreshed.status.value == "completed"
    assert game.inspect().choice is None
    ward = next(effect for effect in game._state.active_effects if effect.kind == "forbidding_ward")
    assert (ward.sustain_limit_source_start, ward.sustain_limit_world_time) == immutable_limit
    assert ward.sustain_expires_at_source_end == 3


def test_command_executes_each_selected_outcome_on_target_turn():
    for mode, expected_position, expected_prone in (
        ("approach", Position(3, 2), False),
        ("flee", Position(6, 2), False),
        ("release", Position(5, 2), False),
        ("prone", Position(5, 2), True),
        ("stand", Position(5, 2), True),
    ):
        game = _first_witch_turn()
        enemy = game._state.creatures["enemy"]
        released_item = None
        if mode == "release":
            released_item = game._state.creatures["witch"].held_items.pop()
            enemy.held_items.append(released_item)
        if mode == "stand":
            enemy.prone = True
        result = game.execute(Cast("command", target_id="enemy", spell_mode=mode))
        assert result.status.value == "completed"
        assert any(effect.command_mode == mode for effect in game._state.condition_effects)
        assert game.execute(EndTurn()).status.value == "completed"
        assert game.execute(EndTurn()).status.value == "completed"
        enemy = game._state.creatures["enemy"]
        assert enemy.position == expected_position
        assert enemy.prone is expected_prone
        assert enemy.actions_remaining == 0  # Critical failure spends all three actions obeying.
        if released_item is not None:
            assert released_item in game._state.ground_items[enemy.position]


def test_sigil_marks_a_touched_creature_and_round_trips(tmp_path):
    game = _first_witch_turn()
    slot = next(slot for slot in game._state.creatures["witch"].prepared_slots if slot.cantrip)
    slot.spell_id = "sigil"
    result = game.execute(Cast("sigil", target_id="ally"))
    assert result.status.value == "completed"
    effect = next(effect for effect in game._state.active_effects if effect.kind == "sigil" and effect.target_actor_id == "ally")
    effect_id = effect.effect_id
    assert game.execute(Interact("toggle_sigil", effect_id)).status.value == "completed"
    assert next(effect for effect in game._state.active_effects if effect.effect_id == effect_id).value == 2
    path = tmp_path / "sigil.json"
    game.save(path)
    loaded = Encounter.load(path)
    assert next(effect for effect in loaded._state.active_effects if effect.kind == "sigil").value == 2


def test_sigil_marks_a_touched_item_and_interact_toggles_visibility(tmp_path):
    game = _first_witch_turn()
    slot = next(slot for slot in game._state.creatures["witch"].prepared_slots if slot.cantrip)
    slot.spell_id = "sigil"
    item_id = game._state.creatures["witch"].held_items[0]
    result = game.execute(Cast("sigil", item_id=item_id))
    assert result.status.value == "completed"
    effect = next(effect for effect in game._state.active_item_effects if effect.kind == "sigil")
    assert effect.item_id == item_id and effect.visible
    path = tmp_path / "sigil-item.json"
    game.save(path)
    loaded = Encounter.load(path)
    effect = next(effect for effect in loaded._state.active_item_effects if effect.kind == "sigil")
    assert effect.item_id == item_id and effect.visible
    effect_id = effect.effect_id

    while loaded.inspect().turn_actor_id != "witch":
        assert loaded.execute(EndTurn()).status.value == "completed"
    result = loaded.execute(Interact("toggle_sigil", effect_id))
    assert result.status.value == "completed"
    assert not next(effect for effect in loaded._state.active_item_effects if effect.effect_id == effect_id).visible


def test_detect_magic_saves_known_magic_choice_and_can_ignore_own_sigil(tmp_path):
    game = _first_witch_turn()
    cantrips = [slot for slot in game._state.creatures["witch"].prepared_slots if slot.cantrip]
    cantrips[0].spell_id = "sigil"
    cantrips[1].spell_id = "detect_magic"
    assert game.execute(Cast("sigil", target_id="ally")).status.value == "completed"
    assert game.execute(EndTurn()).status.value == "completed"
    while game.inspect().turn_actor_id != "witch":
        assert game.execute(EndTurn()).status.value == "completed"
    result = game.execute(Cast("detect_magic"))
    assert result.status.value == "paused"
    pending = game._state.pending_choice
    assert pending is not None and pending.kind == "detect_magic_known"
    path = tmp_path / "detect-magic-pending.json"
    game.save(path)
    loaded = Encounter.load(path)
    pending = loaded._state.pending_choice
    assert pending is not None and pending.kind == "detect_magic_known"
    result = loaded.execute(Choose(pending.choice_id, "ignore_known", "witch"))
    assert result.status.value == "completed"
    assert any(event.kind == "detect_magic_absent" for event in result.events)


def test_terminal_collects_sigil_item_and_detect_magic_no_target_choices():
    game = _first_witch_turn()
    cantrips = [slot for slot in game._state.creatures["witch"].prepared_slots if slot.cantrip]
    cantrips[0].spell_id = "sigil"
    cantrips[1].spell_id = "detect_magic"
    spells = game._spell_options(game._state.creatures["witch"], game._state)
    item_id = game._state.creatures["witch"].held_items[0]

    sigil_answers = iter(("1", "1", "2", "1", "1"))
    sigil = _choose_cast_inputs(spells, game.inspect(), lambda: next(sigil_answers), lambda _line: None)
    assert sigil == ("sigil", None, 2, None, None, {"spell_mode": "visible", "item_id": item_id})

    detect_answers = iter(("2", "1"))
    detect = _choose_cast_inputs(spells, game.inspect(), lambda: next(detect_answers), lambda _line: None)
    assert detect == ("detect_magic", None, 2, None, None)


def test_healthy_witch_victory_refocuses_reprepares_saves_and_casts_next_scene(tmp_path):
    def settle(game):
        while game._state.pending_choice is not None:
            choice = game._state.pending_choice
            option = (
                "keep" if any(item.option_id == "keep" for item in choice.options)
                else "after" if any(item.option_id == "after" for item in choice.options)
                else "witch"
            )
            assert game.execute(Choose(choice.choice_id, option, choice.owner_actor_id)).status.value in {"completed", "paused"}

    game = Encounter.start(
        FAITHS_FLAMEKEEPER_SETUP,
        rolls=[20, 8, 7, 20, 1, 1, *([20] * 12)],
    )
    settle(game)
    assert game.execute(PatronsPuppet("fox", (FamiliarStride((Position(0, 2),)),))).status.value == "paused"
    settle(game)
    assert game._state.creatures["witch"].focus_points == 0

    # The Fist is normally nonlethal.  This explicit legal lethal intent is
    # what makes the ordinary opponent's completed encounter healthy for
    # public downtime without deciding the held unconscious-recovery rule.
    game._state.creatures["enemy"].hp = 1
    game._state.creatures["enemy"].position = Position(1, 1)
    assert game.execute(Strike("enemy", "fist", nonlethal=False)).status.value == "paused"
    settle(game)
    assert not game.inspect().in_progress
    assert game._state.creatures["enemy"].dead

    assert game.refocus("witch").status.value == "completed"
    assert game._state.creatures["witch"].focus_points == 1
    preparations = {}
    for actor_id in ("witch", "ally"):
        actor = game._state.creatures[actor_id]
        selected = {slot.slot_id: slot.spell_id for slot in actor.prepared_slots}
        if actor_id == "witch":
            cantrips = [slot for slot in actor.prepared_slots if slot.cantrip]
            selected[cantrips[0].slot_id] = "sigil"
            selected[cantrips[1].slot_id] = "detect_magic"
        preparations[actor_id] = selected
    assert game.record_rested(("witch", "ally"), day_number=2, elapsed_seconds=28_800).status.value == "completed"
    assert game.daily_prepare(("witch", "ally"), preparations).status.value == "completed"
    assert {slot.spell_id for slot in game._state.creatures["witch"].prepared_slots if slot.cantrip} >= {"sigil", "detect_magic"}

    path = tmp_path / "witch-continuous.json"
    game.save(path)
    game = Encounter.load(path)
    assert game.next_encounter(FAITHS_FLAMEKEEPER_NEXT_SETUP).status.value == "paused"
    settle(game)
    while game.inspect().turn_actor_id != "witch":
        assert game.execute(EndTurn()).status.value == "completed"
    assert game.execute(Cast("detect_magic")).status.value == "paused"
    pending = game._state.pending_choice
    assert pending is not None and pending.kind == "detect_magic_known"
    assert game.execute(Choose(pending.choice_id, "ignore_known", pending.owner_actor_id)).status.value == "completed"
