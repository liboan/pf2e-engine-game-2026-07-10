"""Independent review of the shared finite-preparation policy boundary.

Source packets:
* Wizard and Battle Magic: https://2e.aonprd.com/Classes.aspx?ID=39 and
  https://2e.aonprd.com/ArcaneSchools.aspx?ID=22
* Druid: https://2e.aonprd.com/Classes.aspx?ID=34
* Witch: https://2e.aonprd.com/Classes.aspx?ID=38
* The fixed Warpriest ledger is recorded in docs/implementation/s1-s3-rules.md.
"""

from __future__ import annotations

from copy import deepcopy
import json

import pytest

from pf2e.content import (
    FAITHS_FLAMEKEEPER_NEXT_SETUP,
    FAITHS_FLAMEKEEPER_SETUP,
    get_definition,
    get_setup,
)
from pf2e.encounter import Encounter
from pf2e.model import Cast, Choose, EndTurn, Position, ResultStatus, Strike
from pf2e.preparation import (
    has_variable_preparations,
    preparation_choices,
)
from pf2e.terminal import _choose_daily_preparations
from pf2e.witch import FamiliarStride, PatronsPuppet
from test_daily_preparation import _finished_spent_resources_game
from test_wizard_admission import _finished_game as _finished_unprepared_wizard
from test_wizard_substitution import _finished_wizard_game


def _settle(game: Encounter) -> None:
    while (choice := game.inspect().choice) is not None:
        option_ids = {option.option_id for option in choice.options}
        option_id = (
            "keep" if "keep" in option_ids
            else "after" if "after" in option_ids
            else "witch"
        )
        assert game.execute(
            Choose(choice.choice_id, option_id, choice.owner_actor_id)
        ).status in {ResultStatus.COMPLETED, ResultStatus.PAUSED}


def _write_payload(path, payload: dict) -> None:
    path.write_text(json.dumps(payload))


def _finished_rested_witch() -> Encounter:
    game = Encounter.start(
        FAITHS_FLAMEKEEPER_SETUP,
        rolls=(20, 8, 7, 20, 1, 1, *((20,) * 12)),
    )
    _settle(game)
    assert game.execute(
        PatronsPuppet("fox", (FamiliarStride((Position(0, 2),)),))
    ).status is ResultStatus.PAUSED
    _settle(game)
    game._state.creatures["enemy"].hp = 1
    game._state.creatures["enemy"].position = Position(1, 1)
    assert game.execute(Strike("enemy", "fist", nonlethal=False)).status is ResultStatus.PAUSED
    _settle(game)
    assert not game.inspect().in_progress
    assert game.refocus("witch").status is ResultStatus.COMPLETED
    assert game.record_rested(
        ("witch", "ally"), day_number=2, elapsed_seconds=28_800,
    ).status is ResultStatus.COMPLETED
    return game


def test_shared_terminal_menus_keep_order_duplicates_and_fixed_slots(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    wizard_game = Encounter.start(
        get_setup("staged_battle_magic_wizard_vs_two_guard_dogs"), rolls=(20, 1, 1),
    )
    wizard = wizard_game._state.creatures["wizard"]
    wizard_definition = get_definition(wizard.definition_id)
    curriculum_cantrip = wizard.prepared_slots[0]
    curriculum_ranked = next(
        slot for slot in wizard.prepared_slots if slot.source == "battle_magic_curriculum" and not slot.cantrip
    )
    assert has_variable_preparations(wizard_definition)
    assert preparation_choices(wizard, wizard_definition, curriculum_cantrip) == (
        "telekinetic_projectile", "shield",
    )
    assert preparation_choices(wizard, wizard_definition, curriculum_ranked) == (
        "breathe_fire", "force_barrage",
    )

    druid_game = Encounter.start(get_setup("storm_druid_vs_guard_dog"), rolls=(10, 9))
    druid = druid_game._state.creatures["druid"]
    druid_definition = get_definition(druid.definition_id)
    answers = iter(("2",) * len(druid.prepared_slots))
    shown: list[str] = []
    selected = _choose_daily_preparations(
        druid_game, ("druid",), lambda: next(answers), shown.append,
    )
    assert selected is not None
    assert selected["druid"]["druid_heal_one"] == "runic_weapon"
    assert selected["druid"]["druid_runic_weapon_two"] == "runic_weapon"
    assert sum("Runic Weapon" in line for line in shown) == 2
    assert preparation_choices(druid, druid_definition, druid.prepared_slots[0]) == (
        "electric_arc", "guidance", "stabilize", "tangle_vine", "light",
    )

    witch_game = Encounter.start(FAITHS_FLAMEKEEPER_SETUP, rolls=(20, 8, 7))
    witch = witch_game._state.creatures["witch"]
    witch_definition = get_definition(witch.definition_id)
    assert preparation_choices(witch, witch_definition, witch.prepared_slots[0]) == (
        "detect_magic", "divine_lance", "forbidding_ward", "guidance", "light",
        "shield", "sigil", "stabilize", "vitality_lash", "void_warp",
    )
    answers = iter(("1",) * len(witch.prepared_slots))
    selected = _choose_daily_preparations(
        witch_game, ("witch",), lambda: next(answers), lambda _line: None,
    )
    assert selected is not None
    assert tuple(selected["witch"].values()) == (
        "detect_magic", "detect_magic", "detect_magic", "detect_magic", "detect_magic",
        "command", "command",
    )

    fixed_game = _finished_spent_resources_game(monkeypatch)
    warpriest = fixed_game._state.creatures["warpriest"]
    warpriest_definition = get_definition(warpriest.definition_id)
    assert not has_variable_preparations(warpriest_definition)
    assert all(
        preparation_choices(warpriest, warpriest_definition, slot) == (slot.spell_id,)
        for slot in warpriest.prepared_slots
    )
    selected = _choose_daily_preparations(
        fixed_game,
        ("warpriest",),
        lambda: (_ for _ in ()).throw(AssertionError("fixed slots must not prompt")),
        lambda _line: None,
    )
    assert selected == {"warpriest": {
        slot.slot_id: slot.spell_id for slot in warpriest.prepared_slots
    }}


def test_load_rejects_altered_slot_shape_spent_cantrip_and_fixed_spell(
    monkeypatch: pytest.MonkeyPatch, tmp_path,
) -> None:
    druid = Encounter.start(get_setup("storm_druid_vs_guard_dog"), rolls=(10, 9))
    base_path = tmp_path / "druid-base.json"
    druid.save(base_path)
    base = json.loads(base_path.read_text())

    for label, mutate in (
        ("source", lambda row: row.__setitem__(1, "forged_source")),
        ("rank", lambda row: row.__setitem__(3, 2)),
        ("spent-cantrip", lambda row: row.__setitem__(5, True)),
    ):
        payload = deepcopy(base)
        row = payload["state"]["creatures"]["druid"]["prepared_slots"][0]
        mutate(row)
        path = tmp_path / f"druid-{label}.json"
        _write_payload(path, payload)
        with pytest.raises(ValueError, match="invalid prepared slot facts"):
            Encounter.load(path)

    fixed = _finished_spent_resources_game(monkeypatch)
    fixed_path = tmp_path / "fixed-base.json"
    fixed.save(fixed_path)
    payload = json.loads(fixed_path.read_text())
    row = next(
        row for row in payload["state"]["creatures"]["warpriest"]["prepared_slots"]
        if row[0] == "ordinary_heal_1"
    )
    row[2] = "force_barrage"
    _write_payload(fixed_path, payload)
    with pytest.raises(ValueError, match="invalid prepared slot facts"):
        Encounter.load(fixed_path)


def test_wizard_ranked_spell_in_curriculum_cantrip_slot_rejects_atomically() -> None:
    game = _finished_unprepared_wizard()
    choices = {
        slot.slot_id: slot.spell_id
        for slot in game._state.creatures["wizard"].prepared_slots
    }
    choices["wizard_shield"] = "breathe_fire"
    before = deepcopy(game._state)
    dice_before = game._dice.to_data()

    result = game.daily_prepare(("wizard",), {"wizard": choices})

    assert result.status is ResultStatus.REJECTED
    assert game._state == before
    assert game._dice.to_data() == dice_before


def test_wizard_load_defers_inventory_but_rejects_missing_book_curriculum_and_substitution(
    tmp_path,
) -> None:
    game = _finished_wizard_game()
    base_path = tmp_path / "wizard-base.json"
    game.save(base_path)
    base = json.loads(base_path.read_text())

    missing_book = deepcopy(base)
    missing_book["state"]["creatures"]["wizard"]["stowed_items"].remove(
        "wizard:spellbook"
    )
    book_position = missing_book["state"]["creatures"]["wizard"]["position"]
    ground_row = next(
        (
            row for row in missing_book["state"]["ground_items"]
            if row["position"] == book_position
        ),
        None,
    )
    if ground_row is None:
        missing_book["state"]["ground_items"].append({
            "position": book_position, "items": ["wizard:spellbook"],
        })
    else:
        ground_row["items"].append("wizard:spellbook")
    path = tmp_path / "wizard-missing-book.json"
    _write_payload(path, missing_book)
    with pytest.raises(ValueError, match="finite preparation policy"):
        Encounter.load(path)

    wrong_curriculum = deepcopy(base)
    row = next(
        row for row in wrong_curriculum["state"]["creatures"]["wizard"]["prepared_slots"]
        if row[0] == "wizard_force_barrage"
    )
    row[2] = "sure_strike"
    path = tmp_path / "wizard-wrong-curriculum.json"
    _write_payload(path, wrong_curriculum)
    with pytest.raises(ValueError, match="finite preparation policy"):
        Encounter.load(path)

    assert game.start_spell_substitution(
        "wizard", "wizard_force_barrage", "breathe_fire"
    ).status is ResultStatus.COMPLETED
    path = tmp_path / "wizard-substitution.json"
    game.save(path)
    payload = json.loads(path.read_text())
    payload["state"]["creatures"]["wizard"]["spell_substitution"][2] = "sure_strike"
    _write_payload(path, payload)
    with pytest.raises(ValueError, match="invalid Spell Substitution progress"):
        Encounter.load(path)


def test_invalid_witch_preparation_value_rejects_atomically() -> None:
    game = _finished_rested_witch()
    preparations = {
        actor_id: {
            slot.slot_id: slot.spell_id
            for slot in game._state.creatures[actor_id].prepared_slots
        }
        for actor_id in ("witch", "ally")
    }
    first_slot = game._state.creatures["witch"].prepared_slots[0].slot_id
    preparations["witch"][first_slot] = []  # type: ignore[assignment]
    before = deepcopy(game._state)
    dice_before = game._dice.to_data()

    result = game.daily_prepare(("witch", "ally"), preparations)

    assert result.status is ResultStatus.REJECTED
    assert game._state == before
    assert game._dice.to_data() == dice_before


def test_druid_duplicate_preparation_survives_save_and_casts_in_next_scene(tmp_path) -> None:
    game = Encounter.start(
        get_setup("storm_druid_vs_guard_dog"), rolls=(10, 9, 1, 12, 10, 9),
    )
    _settle(game)
    assert game.execute(Cast("tempest_surge", target_id="dog")).status is ResultStatus.COMPLETED
    assert game.refocus("druid").status is ResultStatus.COMPLETED
    assert game.record_rested(
        ("druid",), day_number=2, elapsed_seconds=1,
    ).status is ResultStatus.COMPLETED
    choices = {
        slot.slot_id: (
            "runic_weapon" if not slot.cantrip else slot.spell_id
        )
        for slot in game._state.creatures["druid"].prepared_slots
    }
    assert game.daily_prepare(
        ("druid",), {"druid": choices},
    ).status is ResultStatus.COMPLETED
    path = tmp_path / "druid-duplicate-next.json"
    game.save(path)
    game = Encounter.load(path)
    assert game.next_encounter(
        get_setup("storm_druid_next_guard_dog")
    ).status is ResultStatus.PAUSED
    _settle(game)
    cast = game.execute(Cast(
        "runic_weapon", item_id="druid:staff", slot_id="druid_heal_one",
    ))
    assert cast.status is ResultStatus.COMPLETED
    slots = game._state.creatures["druid"].prepared_slots
    assert next(slot for slot in slots if slot.slot_id == "druid_heal_one").spent
    assert not next(
        slot for slot in slots if slot.slot_id == "druid_runic_weapon_two"
    ).spent


def test_witch_changed_preparation_survives_save_and_casts_in_next_scene(tmp_path) -> None:
    game = _finished_rested_witch()
    preparations = {}
    for actor_id in ("witch", "ally"):
        actor = game._state.creatures[actor_id]
        selected = {slot.slot_id: slot.spell_id for slot in actor.prepared_slots}
        if actor_id == "witch":
            cantrips = [slot for slot in actor.prepared_slots if slot.cantrip]
            selected[cantrips[0].slot_id] = "sigil"
            selected[cantrips[1].slot_id] = "detect_magic"
        preparations[actor_id] = selected
    assert game.daily_prepare(
        ("witch", "ally"), preparations,
    ).status is ResultStatus.COMPLETED
    path = tmp_path / "witch-changed-next.json"
    game.save(path)
    game = Encounter.load(path)
    assert game.next_encounter(FAITHS_FLAMEKEEPER_NEXT_SETUP).status is ResultStatus.PAUSED
    _settle(game)
    while game.inspect().turn_actor_id != "witch":
        assert game.execute(EndTurn()).status is ResultStatus.COMPLETED
        _settle(game)
    cast = game.execute(Cast("detect_magic"))
    assert cast.status is ResultStatus.PAUSED
    choice = cast.inspection.choice
    assert choice is not None and choice.kind == "detect_magic_known"
    assert game.execute(
        Choose(choice.choice_id, "ignore_known", choice.owner_actor_id)
    ).status is ResultStatus.COMPLETED
