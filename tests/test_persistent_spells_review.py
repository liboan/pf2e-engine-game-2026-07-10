"""Independent source-led review of persistent damage and staged cantrips.

Numerical expectations recorded before engine observation:

* Persistent damage is rolled at the end of each affected turn, followed by
  one DC 15 flat check per condition.  Different types coexist and their
  damage occurs at once, while IWR applies to each persistent condition.
* A fully negated initial hit usually negates the attached persistence.
* Ignition deals 2d4 fire at range or, by caster choice within melee reach,
  2d6 fire with a melee spell attack; a critical hit adds 1d4 persistent fire.
* Caustic Blast is a 5-foot burst for 1d8 acid with a basic Reflex save; a
  critical failure adds 1 persistent acid.
* Gouging Claw deals the caster's choice of 2d6 slashing or piercing plus 2
  persistent bleed, with both initial and bleed damage doubled on a critical.

Sources: Player Core pp. 445, 336, 319, and 333; AoN condition ID 86 and
spell IDs 1565, 1461, and 1546.
"""

from dataclasses import replace
import json
from types import MappingProxyType

import pytest

import pf2e.content as content
from pf2e.damage import DamageDefense
from pf2e.encounter import Encounter
from pf2e.model import (
    Cast,
    CreaturePlacement,
    EncounterSetup,
    EndTurn,
    PersistentDamageEffect,
    Position,
    ResultStatus,
    Stride,
)


def _settle(game: Encounter) -> None:
    while game.inspect().choice is not None:
        choice = game.inspect().choice
        assert choice is not None
        assert game.choose(
            choice.choice_id, "keep", choice.owner_actor_id
        ).status in {ResultStatus.COMPLETED, ResultStatus.PAUSED}


def _register(monkeypatch, setup: EncounterSetup, *definitions) -> None:
    monkeypatch.setattr(
        content,
        "_STAGED_CREATURES",
        MappingProxyType({
            **content._STAGED_CREATURES,
            **{definition.definition_id: definition for definition in definitions},
        }),
    )
    monkeypatch.setattr(
        content,
        "_STAGED_SETUPS",
        MappingProxyType({**content._STAGED_SETUPS, setup.setup_id: setup}),
    )


def _ward_setup(monkeypatch, *, definition_id: str, defenses) -> EncounterSetup:
    ward = replace(
        content.get_definition("guard_dog_mc2924"),
        definition_id=definition_id,
        hp=20,
        damage_defenses=defenses,
    )
    setup = EncounterSetup(
        setup_id=f"{definition_id}_setup",
        name="Persistent Damage Review Ward",
        width=5,
        height=3,
        placements=(
            CreaturePlacement(
                "wizard", "wizard_battle_magic_level_1_staged", "Wizard",
                "blue", Position(1, 1),
            ),
            CreaturePlacement(
                "ward", ward.definition_id, "Ward", "red", Position(3, 1),
            ),
        ),
    )
    _register(monkeypatch, setup, ward)
    return setup


def test_bleed_is_physical_while_fire_remains_separate(monkeypatch) -> None:
    setup = _ward_setup(
        monkeypatch,
        definition_id="persistent_review_physical_ward",
        defenses=(DamageDefense(
            "resistance", "physical", 2, source="review physical ward"
        ),),
    )
    game = Encounter.start(setup, rolls=(20, 1, 3, 15, 15))
    _settle(game)
    game._state.persistent_effects[:] = [
        PersistentDamageEffect(
            "fire", "wizard", "ward", "ignition", "fire", (4,), 0, 60
        ),
        PersistentDamageEffect(
            "bleed", "wizard", "ward", "gouging_claw", "bleed", (), 4, 60
        ),
    ]
    assert game.execute(EndTurn()).status is ResultStatus.COMPLETED
    result = game.execute(EndTurn())
    assert result.status is ResultStatus.COMPLETED
    damage = next(event.damage for event in result.events if event.kind == "persistent_damage")
    assert damage is not None
    assert [(part.damage_type, part.amount) for part in damage.components] == [
        ("fire", 3), ("bleed", 2)
    ]
    assert damage.total == 5


def test_resistance_all_applies_separately_to_each_persistent_condition(
    monkeypatch,
) -> None:
    setup = _ward_setup(
        monkeypatch,
        definition_id="persistent_review_all_ward",
        defenses=(DamageDefense(
            "resistance", "all", 2, source="review universal ward"
        ),),
    )
    game = Encounter.start(setup, rolls=(20, 1, 3, 15, 15))
    _settle(game)
    game._state.persistent_effects[:] = [
        PersistentDamageEffect(
            "fire", "wizard", "ward", "ignition", "fire", (4,), 0, 60
        ),
        PersistentDamageEffect(
            "bleed", "wizard", "ward", "gouging_claw", "bleed", (), 4, 60
        ),
    ]
    assert game.execute(EndTurn()).status is ResultStatus.COMPLETED
    result = game.execute(EndTurn())
    assert result.status is ResultStatus.COMPLETED
    damage = next(event.damage for event in result.events if event.kind == "persistent_damage")
    assert damage is not None
    assert [(part.damage_type, part.amount) for part in damage.components] == [
        ("fire", 1), ("bleed", 2)
    ]
    assert damage.total == 3


def test_fire_immunity_negates_critical_ignition_persistence(monkeypatch) -> None:
    setup = _ward_setup(
        monkeypatch,
        definition_id="persistent_review_fire_immune",
        defenses=(DamageDefense(
            "immunity", "fire", source="review fire immunity"
        ),),
    )
    game = Encounter.start(setup, rolls=(20, 1, 20, 4, 4))
    _settle(game)
    result = game.execute(Cast("ignition", "ward", spell_mode="ranged"))
    if result.status is ResultStatus.PAUSED:
        choice = game.inspect().choice
        assert choice is not None
        result = game.choose(choice.choice_id, "keep", choice.owner_actor_id)
    assert result.status is ResultStatus.COMPLETED
    assert game._state.creatures["ward"].hp == 20
    assert not game._state.persistent_effects


def test_save_rejects_a_forged_spell_damage_profile(tmp_path) -> None:
    game = Encounter.start(
        content.get_setup("staged_battle_magic_wizard_vs_two_guard_dogs"),
        rolls=(20, 1, 1),
    )
    _settle(game)
    game._state.persistent_effects.append(PersistentDamageEffect(
        "persistent:ignition:wizard:dog_a:review",
        "wizard", "dog_a", "ignition", "fire", (4,), 0, 60,
    ))
    path = tmp_path / "forged-persistent.json"
    game.save(path)
    payload = json.loads(path.read_text())
    payload["state"]["persistent_effects"][0][3] = "gouging_claw"
    path.write_text(json.dumps(payload))
    with pytest.raises(ValueError, match="persistent"):
        Encounter.load(path)


def test_save_rejects_a_forged_persistent_spell_deadline(tmp_path) -> None:
    game = Encounter.start(
        content.get_setup("staged_battle_magic_wizard_vs_two_guard_dogs"),
        rolls=(20, 1, 1),
    )
    _settle(game)
    game._state.persistent_effects.append(PersistentDamageEffect(
        "persistent:ignition:wizard:dog_a:review",
        "wizard", "dog_a", "ignition", "fire", (4,), 0, 60,
    ))
    path = tmp_path / "forged-persistent-deadline.json"
    game.save(path)
    payload = json.loads(path.read_text())
    payload["state"]["persistent_effects"][0][7] = 600
    path.write_text(json.dumps(payload))
    with pytest.raises(ValueError, match="persistent"):
        Encounter.load(path)


def test_save_rejects_reordered_recovery_progress(tmp_path) -> None:
    game = Encounter.start(
        content.get_setup("staged_battle_magic_wizard_vs_two_guard_dogs"),
        rolls=(20, 1, 1, 3, 14),
    )
    _settle(game)
    game._state.persistent_effects[:] = [
        PersistentDamageEffect(
            "fire", "wizard", "wizard", "ignition", "fire", (4,), 0, 60
        ),
        PersistentDamageEffect(
            "bleed", "wizard", "wizard", "gouging_claw", "bleed", (), 2, 60
        ),
    ]
    assert game.execute(EndTurn()).status is ResultStatus.PAUSED
    path = tmp_path / "reordered-recovery.json"
    game.save(path)
    payload = json.loads(path.read_text())
    continuation = payload["state"]["pending_choice"]["continuation"]
    continuation["target_ids"].reverse()
    path.write_text(json.dumps(payload))
    with pytest.raises(ValueError, match="persistent recovery"):
        Encounter.load(path)


def test_saved_ignition_attack_cannot_change_from_ranged_to_melee(tmp_path) -> None:
    game = Encounter.start(
        content.get_setup("staged_battle_magic_wizard_vs_two_guard_dogs"),
        rolls=(20, 1, 1, 9, 2, 3),
    )
    _settle(game)
    assert game.execute(Cast(
        "ignition", "dog_a", spell_mode="ranged"
    )).status is ResultStatus.PAUSED
    path = tmp_path / "changed-ignition-mode.json"
    game.save(path)
    payload = json.loads(path.read_text())
    payload["state"]["pending_choice"]["continuation"]["spell_mode"] = "melee"
    path.write_text(json.dumps(payload))
    with pytest.raises(ValueError, match="attack mode"):
        Encounter.load(path)


def test_saved_melee_ignition_keeps_d6_profile_after_public_movement(
    tmp_path,
) -> None:
    game = Encounter.start(
        content.get_setup("staged_battle_magic_wizard_vs_two_guard_dogs"),
        rolls=(20, 1, 1, 9, 2, 3),
    )
    _settle(game)
    assert game.execute(Stride((Position(2, 2),))).status is ResultStatus.COMPLETED
    assert game.execute(Cast(
        "ignition", "dog_b", spell_mode="melee"
    )).status is ResultStatus.PAUSED
    path = tmp_path / "melee-ignition.json"
    game.save(path)
    restored = Encounter.load(path)
    choice = restored.inspect().choice
    assert choice is not None
    result = restored.choose(choice.choice_id, "keep", choice.owner_actor_id)
    assert result.status is ResultStatus.COMPLETED
    damage = next(event.damage for event in result.events if event.kind == "spell_damage")
    assert damage is not None
    assert damage.components[0].dice == (6, 6)
    assert damage.total == 5


def test_saved_reaction_cannot_change_committed_ignition_mode(tmp_path) -> None:
    game = Encounter.start(
        content.get_setup("staged_battle_magic_wizard_reactive_strike"),
        rolls=(20, 1),
    )
    _settle(game)
    result = game.execute(Cast(
        "ignition", "reactive_fighter", spell_mode="ranged"
    ))
    assert result.status is ResultStatus.PAUSED
    assert game.inspect().choice is not None
    assert game.inspect().choice.kind == "reaction"
    path = tmp_path / "changed-reaction-ignition-mode.json"
    game.save(path)
    payload = json.loads(path.read_text())
    payload["state"]["pending_choice"]["continuation"]["spell_mode"] = "melee"
    path.write_text(json.dumps(payload))
    with pytest.raises(ValueError, match="persistent spell reaction mode"):
        Encounter.load(path)


def test_critical_ignition_persistence_can_finish_the_last_ordinary_enemy(
    monkeypatch,
) -> None:
    setup = EncounterSetup(
        setup_id="persistent_review_last_enemy",
        name="Persistent Damage Finishes Last Enemy",
        width=5,
        height=3,
        placements=(
            CreaturePlacement(
                "wizard", "wizard_battle_magic_level_1_staged", "Wizard",
                "blue", Position(1, 1),
            ),
            CreaturePlacement(
                "dog", "guard_dog_mc2924", "Dog", "red", Position(3, 1),
            ),
        ),
    )
    _register(monkeypatch, setup)
    game = Encounter.start(setup, rolls=(20, 1, 20, 1, 1, 4, 14, 20, 1))
    _settle(game)
    result = game.execute(Cast("ignition", "dog", spell_mode="ranged"))
    assert result.status is ResultStatus.PAUSED
    choice = game.inspect().choice
    assert choice is not None
    assert game.choose(
        choice.choice_id, "keep", choice.owner_actor_id
    ).status is ResultStatus.COMPLETED
    assert game._state.creatures["dog"].hp == 4
    assert game.execute(EndTurn()).status is ResultStatus.COMPLETED
    result = game.execute(EndTurn())
    assert result.status is ResultStatus.COMPLETED
    dog = game._state.creatures["dog"]
    assert dog.hp == 0 and dog.dead
    assert not game._state.persistent_effects
    assert not game.inspect().in_progress
    assert game.inspect().winner_team == "blue"
    transitioned = game.next_encounter(
        content.get_setup("staged_battle_magic_wizard_next_guard_dog")
    )
    _settle(game)
    assert transitioned.status in {ResultStatus.COMPLETED, ResultStatus.PAUSED}
