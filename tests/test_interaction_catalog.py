from dataclasses import replace

import pytest

from pf2e.content import (
    BARBARIAN_PC_PAIR_SETUP,
    CREATURES,
    ANGELIC_FIRST_CAST_SETUP,
    JUSTICE_CHAMPION_SETUP,
    S1_SETUP,
    FEINT_FIGHTER_DUEL_SETUP,
    S2_INTERACTION_SETUPS,
    S2_PACK_ATTACK_SETUP,
    S2_PC_DUEL_SETUP,
    S2_SETUP,
    S3_INTERACTION_SETUPS,
    S3_SETUP,
    ROGUE_THIEF_SETUP,
    ROGUE_THIEF_FIGHTER_SETUP,
    ROGUE_THIEF_WARPRIEST_SETUP,
    RUNE_WEAPON_TEST_SETUP,
    RUNE_ARMOR_AC_TEST_SETUP,
    RUNE_ARMOR_DC_TEST_SETUP,
    RUNE_ARMOR_SPELL_SAVE_TEST_SETUP,
    RUNE_HANDWRAP_TEST_SETUP,
    RUNE_HANDWRAP_UNINVESTED_TEST_SETUP,
    SURE_STRIKE_WARPRIEST_SETUP,
    STEEL_SHIELD_TEST_SETUP,
    SETUPS,
    get_setup,
)
from pf2e.barbarian_content import (
    ANIMAL_BARBARIAN_SETUPS,
    BARBARIAN_TEST_SETUP,
    DRAGON_BARBARIAN_SETUPS,
)
from pf2e.typed_defense_content import TYPED_DEFENSE_SETUPS
from pf2e.encounter import Encounter
import pf2e.terminal as terminal


_BASE_SETUP_IDS = {
    BARBARIAN_TEST_SETUP.setup_id,
    BARBARIAN_PC_PAIR_SETUP.setup_id,
    S1_SETUP.setup_id,
    S2_SETUP.setup_id,
    S2_PACK_ATTACK_SETUP.setup_id,
    S2_PC_DUEL_SETUP.setup_id,
    S3_SETUP.setup_id,
    ROGUE_THIEF_SETUP.setup_id,
    ROGUE_THIEF_FIGHTER_SETUP.setup_id,
    ROGUE_THIEF_WARPRIEST_SETUP.setup_id,
    FEINT_FIGHTER_DUEL_SETUP.setup_id,
    STEEL_SHIELD_TEST_SETUP.setup_id,
    RUNE_WEAPON_TEST_SETUP.setup_id,
    RUNE_ARMOR_AC_TEST_SETUP.setup_id,
    RUNE_ARMOR_DC_TEST_SETUP.setup_id,
    RUNE_ARMOR_SPELL_SAVE_TEST_SETUP.setup_id,
    RUNE_HANDWRAP_TEST_SETUP.setup_id,
    RUNE_HANDWRAP_UNINVESTED_TEST_SETUP.setup_id,
    SURE_STRIKE_WARPRIEST_SETUP.setup_id,
    ANGELIC_FIRST_CAST_SETUP.setup_id,
    JUSTICE_CHAMPION_SETUP.setup_id,
}


def test_catalog_keeps_existing_entries_and_admits_each_completed_setup_family() -> None:
    s2_ids = {setup.setup_id for setup in S2_INTERACTION_SETUPS}
    s3_ids = {setup.setup_id for setup in S3_INTERACTION_SETUPS}
    dragon_ids = set(DRAGON_BARBARIAN_SETUPS)
    animal_ids = set(ANIMAL_BARBARIAN_SETUPS)
    defense_ids = set(TYPED_DEFENSE_SETUPS)

    assert len(S2_INTERACTION_SETUPS) == 8
    assert len(S3_INTERACTION_SETUPS) == 8
    assert len(dragon_ids) == 8
    assert len(animal_ids) == 2
    assert len(defense_ids) == 4
    assert _BASE_SETUP_IDS <= SETUPS.keys()
    assert s2_ids.isdisjoint(s3_ids | _BASE_SETUP_IDS | dragon_ids | animal_ids | defense_ids)
    assert s3_ids.isdisjoint(_BASE_SETUP_IDS)
    assert dragon_ids.isdisjoint(_BASE_SETUP_IDS | s2_ids | s3_ids | animal_ids)
    assert animal_ids.isdisjoint(_BASE_SETUP_IDS | s2_ids | s3_ids | defense_ids)
    assert defense_ids.isdisjoint(_BASE_SETUP_IDS | s2_ids | s3_ids)
    assert s2_ids | s3_ids | _BASE_SETUP_IDS | dragon_ids | animal_ids | defense_ids == SETUPS.keys()

    for setup in (*S2_INTERACTION_SETUPS, *S3_INTERACTION_SETUPS):
        assert get_setup(setup.setup_id) == setup
        assert all(placement.definition_id in CREATURES for placement in setup.placements)

    assert "fighter_fleet_shortsword_level_1" in CREATURES
    assert "elite_guard_dog_mc2924" in CREATURES
    assert "fighter_rapier_level_1" in CREATURES


@pytest.mark.parametrize("setup_id", ("s3_long_lane_crossfire", "s3_emanation_edge"))
def test_catalogued_15_by_5_encounter_round_trips_without_changing_its_map(
    setup_id: str, tmp_path
) -> None:
    setup = get_setup(setup_id)
    assert (setup.width, setup.height) == (15, 5)

    game = Encounter.start(setup, seed=42)
    save_path = tmp_path / f"{setup_id}.json"
    game.save(save_path)
    restored = Encounter.load(save_path)

    inspection = restored.inspect()
    assert (inspection.map_width, inspection.map_height) == (15, 5)
    assert {actor.actor_id for actor in inspection.actors} == {
        placement.actor_id for placement in setup.placements
    }


def test_modified_catalogued_setup_is_still_rejected() -> None:
    setup = get_setup("s3_long_lane_crossfire")

    with pytest.raises(ValueError, match="match its catalogued definition"):
        Encounter.start(replace(setup, name="Uncatalogued rename"), seed=42)


@pytest.mark.parametrize(
    "setup_id", ("s2_fleet_diagonal_assault", "s3_long_lane_crossfire")
)
def test_terminal_accepts_catalogued_interaction_setup_by_name(monkeypatch, setup_id: str) -> None:
    seen = {}

    def capture_run(*, setup, seed, save_path):
        seen.update(setup=setup, seed=seed, save_path=save_path)
        return 0

    monkeypatch.setattr(terminal, "run_terminal", capture_run)

    assert terminal.main(["play", setup_id, "--seed", "27", "--save-path", "run.json"]) == 0
    assert seen == {"setup": get_setup(setup_id), "seed": 27, "save_path": "run.json"}
