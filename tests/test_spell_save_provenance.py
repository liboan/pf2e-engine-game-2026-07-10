from __future__ import annotations

from dataclasses import replace
import json
from types import MappingProxyType

import pytest

import pf2e.content as content
from pf2e.content import get_definition, get_setup
from pf2e.encounter import Encounter
from pf2e.model import (
    Cast,
    CreaturePlacement,
    EncounterSetup,
    EndTurn,
    Position,
    PreparedSpellDefinition,
    ResultStatus,
)


def _settle(game: Encounter) -> None:
    while (choice := game.inspect().choice) is not None:
        option_ids = {option.option_id for option in choice.options}
        option_id = "keep" if "keep" in option_ids else choice.options[0].option_id
        assert game.choose(choice.choice_id, option_id, choice.owner_actor_id).status in {
            ResultStatus.PAUSED,
            ResultStatus.COMPLETED,
        }


def test_prepared_fear_saved_hero_pause_loads_with_its_committed_slot(
    monkeypatch: pytest.MonkeyPatch, tmp_path
) -> None:
    witch = replace(
        get_definition("faiths_flamekeeper_witch_level_1"),
        definition_id="prepared_fear_witch",
        prepared_spells=(
            PreparedSpellDefinition("prepared_fear", "rank_1", "fear", rank=1),
        ),
    )
    setup = EncounterSetup(
        "prepared_fear_provenance", "Prepared Fear provenance", 7, 5,
        (
            CreaturePlacement("witch", witch.definition_id, "Witch", "blue", Position(1, 2)),
            CreaturePlacement("target", "fighter_m_level_1", "Target", "red", Position(5, 2)),
        ),
    )
    monkeypatch.setattr(
        content, "_STAGED_CREATURES",
        MappingProxyType({**content._STAGED_CREATURES, witch.definition_id: witch}),
    )
    monkeypatch.setattr(
        content, "_STAGED_SETUPS",
        MappingProxyType({**content._STAGED_SETUPS, setup.setup_id: setup}),
    )

    game = Encounter.start(setup, rolls=(20, 1, 8))
    _settle(game)
    cast = game.execute(Cast("fear", "target", slot_id="prepared_fear"))
    assert cast.status is ResultStatus.PAUSED
    hero = cast.inspection.choice
    assert hero is not None and hero.kind == "spell_save_hero_reroll"

    path = tmp_path / "prepared-fear-hero.json"
    game.save(path)
    restored = Encounter.load(path)
    choice = restored.inspect().choice
    assert choice is not None and choice.kind == "spell_save_hero_reroll"
    assert restored.choose(choice.choice_id, "keep", choice.owner_actor_id).status is ResultStatus.COMPLETED


@pytest.mark.parametrize(
    ("caster_definition_id", "target_definition_id", "spell_id"),
    (
        ("storm_druid_level_1", "life_oracle_level_1_staged", "tempest_surge"),
        ("life_oracle_level_1_staged", "life_oracle_death_mode_target_staged", "vitality_lash"),
    ),
)
def test_spell_save_offers_existing_target_guidance_before_hero_choice(
    caster_definition_id: str,
    target_definition_id: str,
    spell_id: str,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    setup = EncounterSetup(
        f"guided_{spell_id}", f"Guided {spell_id}", 7, 5,
        (
            CreaturePlacement("caster", caster_definition_id, "Caster", "blue", Position(1, 2)),
            CreaturePlacement("target", target_definition_id, "Target", "red", Position(4, 2)),
        ),
    )
    monkeypatch.setattr(
        content, "_STAGED_SETUPS",
        MappingProxyType({**content._STAGED_SETUPS, setup.setup_id: setup}),
    )
    game = Encounter.start(setup, rolls=(1, 20, 8, 6, 6))
    _settle(game)
    assert game.inspect().turn_actor_id == "target"
    assert game.execute(Cast("guidance", "target")).status is ResultStatus.COMPLETED
    assert game.execute(EndTurn()).status is ResultStatus.COMPLETED
    assert game.inspect().turn_actor_id == "caster"

    paused = game.execute(Cast(spell_id, "target"))
    assert paused.status is ResultStatus.PAUSED
    choice = paused.inspection.choice
    assert choice is not None and choice.kind == "guidance_use"
    used = game.choose(choice.choice_id, "use", choice.owner_actor_id)
    assert used.status is ResultStatus.PAUSED
    hero = used.inspection.choice
    assert hero is not None and hero.kind == "spell_save_hero_reroll"
    pending = game._state.pending_choice
    assert pending is not None and pending.check is not None
    assert any(modifier.source == "Guidance" for modifier in pending.check.modifier_breakdown)

    path = tmp_path / f"guided-{spell_id}.json"
    game.save(path)
    restored = Encounter.load(path)
    hero = restored.inspect().choice
    assert hero is not None and hero.kind == "spell_save_hero_reroll"
    assert restored.choose(hero.choice_id, "keep", hero.owner_actor_id).status is ResultStatus.COMPLETED
    assert restored._state.guidance_immunity_deadlines["target"] == 600


def test_saved_spell_save_rejects_an_uncommitted_source(tmp_path) -> None:
    game = Encounter.start(get_setup("storm_druid_tempest_save"), rolls=(10, 9, 7))
    _settle(game)
    assert game.execute(Cast("tempest_surge", "wizard_target")).status is ResultStatus.PAUSED
    path = tmp_path / "tampered-tempest.json"
    game.save(path)
    payload = json.loads(path.read_text())
    payload["state"]["pending_choice"]["continuation"]["spell_source_kind"] = "prepared"
    path.write_text(json.dumps(payload))

    with pytest.raises(ValueError, match="uncommitted .* prepared spell save source"):
        Encounter.load(path)
