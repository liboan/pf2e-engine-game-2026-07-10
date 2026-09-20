from dataclasses import replace

import pytest

from pf2e.content import (
    BARBARIAN_PC_PAIR_SETUP,
    CREATURES,
    ANGELIC_FIRST_CAST_SETUP,
    BRAGGART_SWASHBUCKLER_SETUP,
    BATTLE_MAGIC_WIZARD_SETUP,
    BATTLE_MAGIC_WIZARD_DAZE_SETUP,
    BATTLE_MAGIC_WIZARD_SUPPRESSION_SPELLS_SETUP,
    STORM_DRUID_SETUP,
    LIFE_ORACLE_NUDGE_SETUP,
    FAITHS_FLAMEKEEPER_SETUP,
    FAITHS_FLAMEKEEPER_DAZE_SETUP,
    FAITHS_FLAMEKEEPER_SUPPRESSION_SPELLS_SETUP,
    MAESTRO_BARD_ANTHEM_SETUP,
    MAESTRO_BARD_FEAR_SETUP,
    MAESTRO_BARD_COUNTER_SETUP,
    BOMBER_ALCHEMIST_SETUP,
    JUSTICE_CHAMPION_SETUP,
    FORENSIC_INVESTIGATOR_VS_TWO_DOGS,
    FORENSIC_INVESTIGATOR_HEALING_SETUP,
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
    RANGER_PRECISION_BOW_SETUP,
    MONK_KAMA_FLURRY_SETUP,
    SURE_STRIKE_WARPRIEST_SETUP,
    STEEL_SHIELD_TEST_SETUP,
    SETUPS,
    L2_MARTIAL_SETUPS,
    L2_DIVINE_DEFINITIONS,
    L2_DIVINE_SETUPS,
    BOMBER_ALCHEMIST_LEVEL_2,
    BOMBER_ALCHEMIST_LEVEL_2_LONG_RANGE_SETUP,
    BOMBER_ALCHEMIST_LEVEL_2_ITEM_SUPPORT_SETUP,
    BOMBER_ALCHEMIST_LEVEL_2_ITEM_SUPPORT_NEXT_SETUP,
    BOMBER_ALCHEMIST_LEVEL_2_NEXT_SETUP,
    BOMBER_ALCHEMIST_LEVEL_2_SETUP,
    get_setup,
)
from pf2e.investigator_content import INVESTIGATOR_SETUPS
from pf2e.barbarian_content import (
    ANIMAL_BARBARIAN_SETUPS,
    BARBARIAN_TEST_SETUP,
    DRAGON_BARBARIAN_SETUPS,
)
from pf2e.typed_defense_content import TYPED_DEFENSE_SETUPS
from pf2e.encounter import Encounter
from pf2e.ranger_monk_content import MONK, RANGER_PRECISION
from pf2e.l2_horizontal_content import L2_HORIZONTAL_DEFINITIONS, L2_HORIZONTAL_SETUPS
from pf2e.l2_ranger_content import (
    RANGER_PRECISION_LEVEL_2,
    RANGER_PRECISION_LEVEL_2_HUNTERS_AIM_SETUP,
)
from pf2e.l2_prepared_content import L2_PREPARED_SETUPS
from pf2e.l2_reach_content import L2_REACH_DEFINITIONS, L2_REACH_SETUPS
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
    BRAGGART_SWASHBUCKLER_SETUP.setup_id,
    FORENSIC_INVESTIGATOR_VS_TWO_DOGS.setup_id,
    FORENSIC_INVESTIGATOR_HEALING_SETUP.setup_id,
    RANGER_PRECISION_BOW_SETUP.setup_id,
    MONK_KAMA_FLURRY_SETUP.setup_id,
    BATTLE_MAGIC_WIZARD_SETUP.setup_id,
    STORM_DRUID_SETUP.setup_id,
    LIFE_ORACLE_NUDGE_SETUP.setup_id,
    FAITHS_FLAMEKEEPER_SETUP.setup_id,
    MAESTRO_BARD_ANTHEM_SETUP.setup_id,
    MAESTRO_BARD_FEAR_SETUP.setup_id,
    MAESTRO_BARD_COUNTER_SETUP.setup_id,
    BOMBER_ALCHEMIST_SETUP.setup_id,
}


def test_catalog_keeps_existing_entries_and_admits_each_completed_setup_family() -> None:
    s2_ids = {setup.setup_id for setup in S2_INTERACTION_SETUPS}
    s3_ids = {setup.setup_id for setup in S3_INTERACTION_SETUPS}
    dragon_ids = set(DRAGON_BARBARIAN_SETUPS)
    animal_ids = set(ANIMAL_BARBARIAN_SETUPS)
    defense_ids = set(TYPED_DEFENSE_SETUPS)
    l2_horizontal_ids = set(L2_HORIZONTAL_SETUPS)
    l2_ranger_ids = {RANGER_PRECISION_LEVEL_2_HUNTERS_AIM_SETUP.setup_id}
    l2_reach_ids = {setup.setup_id for setup in L2_REACH_SETUPS}
    l2_expanded_ids = set(L2_MARTIAL_SETUPS) | {setup.setup_id for setup in L2_PREPARED_SETUPS}
    content_w1_spell_ids = {
        BATTLE_MAGIC_WIZARD_DAZE_SETUP.setup_id,
        FAITHS_FLAMEKEEPER_DAZE_SETUP.setup_id,
        BATTLE_MAGIC_WIZARD_SUPPRESSION_SPELLS_SETUP.setup_id,
        FAITHS_FLAMEKEEPER_SUPPRESSION_SPELLS_SETUP.setup_id,
    }
    remaining_l2_ids = (
        set(INVESTIGATOR_SETUPS)
        | set(L2_DIVINE_SETUPS)
        | {
            BOMBER_ALCHEMIST_LEVEL_2_SETUP.setup_id,
            BOMBER_ALCHEMIST_LEVEL_2_NEXT_SETUP.setup_id,
            BOMBER_ALCHEMIST_LEVEL_2_LONG_RANGE_SETUP.setup_id,
            BOMBER_ALCHEMIST_LEVEL_2_ITEM_SUPPORT_SETUP.setup_id,
            BOMBER_ALCHEMIST_LEVEL_2_ITEM_SUPPORT_NEXT_SETUP.setup_id,
        }
    )

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
    assert (
        s2_ids | s3_ids | _BASE_SETUP_IDS | dragon_ids | animal_ids | defense_ids
            | l2_horizontal_ids | l2_ranger_ids | l2_reach_ids
            | l2_expanded_ids | remaining_l2_ids | content_w1_spell_ids
        ) == SETUPS.keys()

    for setup in (*S2_INTERACTION_SETUPS, *S3_INTERACTION_SETUPS):
        assert get_setup(setup.setup_id) == setup
        assert all(placement.definition_id in CREATURES for placement in setup.placements)

    assert "fighter_fleet_shortsword_level_1" in CREATURES
    assert "elite_guard_dog_mc2924" in CREATURES
    assert "fighter_rapier_level_1" in CREATURES
    assert RANGER_PRECISION.definition_id in CREATURES
    assert MONK.definition_id in CREATURES
    for definition_id, definition in L2_HORIZONTAL_DEFINITIONS.items():
        assert CREATURES[definition_id] == definition
    assert CREATURES[RANGER_PRECISION_LEVEL_2.definition_id] == RANGER_PRECISION_LEVEL_2
    for definition in L2_REACH_DEFINITIONS:
        assert CREATURES[definition.definition_id] == definition
    for definition_id, definition in L2_DIVINE_DEFINITIONS.items():
        assert CREATURES[definition_id] == definition
    assert CREATURES[BOMBER_ALCHEMIST_LEVEL_2.definition_id] == BOMBER_ALCHEMIST_LEVEL_2


def test_catalogued_precision_ranger_combat_setup_starts_and_round_trips(tmp_path) -> None:
    setup = get_setup(RANGER_PRECISION_BOW_SETUP.setup_id)
    assert setup == RANGER_PRECISION_BOW_SETUP
    assert all(placement.definition_id in CREATURES for placement in setup.placements)

    game = Encounter.start(setup, seed=13)
    save_path = tmp_path / "precision-ranger-combat.json"
    game.save(save_path)
    restored = Encounter.load(save_path)

    assert restored.inspect().map_width == setup.width


def test_catalogued_monk_setup_starts_and_round_trips(tmp_path) -> None:
    setup = get_setup(MONK_KAMA_FLURRY_SETUP.setup_id)
    assert setup == MONK_KAMA_FLURRY_SETUP
    assert all(placement.definition_id in CREATURES for placement in setup.placements)

    game = Encounter.start(setup, seed=13)
    save_path = tmp_path / "monk-kama-flurry.json"
    game.save(save_path)
    restored = Encounter.load(save_path)

    assert restored.inspect().map_width == setup.width


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
    "setup_id",
    (
        "s2_fleet_diagonal_assault",
        "s3_long_lane_crossfire",
        "staged_ranger_precision_bow",
        "staged_monk_kama_flurry",
        "staged_life_oracle_nudge",
    ),
)
def test_terminal_accepts_catalogued_interaction_setup_by_name(monkeypatch, setup_id: str) -> None:
    seen = {}

    def capture_run(*, setup, seed, save_path):
        seen.update(setup=setup, seed=seed, save_path=save_path)
        return 0

    monkeypatch.setattr(terminal, "run_terminal", capture_run)

    assert terminal.main(["play", setup_id, "--seed", "27", "--save-path", "run.json"]) == 0
    assert seen == {"setup": get_setup(setup_id), "seed": 27, "save_path": "run.json"}
