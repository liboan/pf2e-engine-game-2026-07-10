"""Independent source and public-play review of the first Investigator slice.

Rules references:
- Investigator: https://2e.aonprd.com/Classes.aspx?ID=59
- Devise a Stratagem: https://2e.aonprd.com/Actions.aspx?ID=2813
- Hero Points: https://2e.aonprd.com/Rules.aspx?ID=2333
- Fortune: https://2e.aonprd.com/Rules.aspx?ID=2263
"""

from __future__ import annotations

from pathlib import Path

import pytest

import pf2e.content as content
from pf2e.encounter import Encounter
from pf2e.investigator import DeviseStratagem, SKILL_STRATAGEM
from pf2e.investigator_content import FORENSIC_INVESTIGATOR
from pf2e.model import (
    CreaturePlacement,
    EncounterSetup,
    EndTurn,
    Position,
    ResultStatus,
    Strike,
)


def _actor(game: Encounter, actor_id: str):
    return next(actor for actor in game.inspect().actors if actor.actor_id == actor_id)


def _choose(game: Encounter, option_id: str):
    choice = game.inspect().choice
    assert choice is not None
    return game.choose(choice.choice_id, option_id, choice.owner_actor_id)


def _settle_initiative(game: Encounter) -> None:
    for _ in range(4):
        choice = game.inspect().choice
        if choice is None:
            return
        assert choice.kind in {"initiative_hero_reroll", "initiative_tie"}
        option_id = (
            "keep"
            if any(option.option_id == "keep" for option in choice.options)
            else choice.options[0].option_id
        )
        assert _choose(game, option_id).status in {
            ResultStatus.PAUSED,
            ResultStatus.COMPLETED,
        }
    raise AssertionError("initiative did not settle within four choices")


def _investigator_game(*rolls: int) -> Encounter:
    game = Encounter.start(
        content.get_setup("investigator_forensic_vs_two_guard_dogs"),
        rolls=rolls,
    )
    _settle_initiative(game)
    assert game.inspect().turn_actor_id == "forensic_investigator"
    return game


def _nimble_setup(monkeypatch: pytest.MonkeyPatch) -> EncounterSetup:
    """Production definitions in a diagnostic reaction fixture, not a new class."""
    setup = EncounterSetup(
        setup_id="review_investigator_vs_nimble_rogue",
        name="Review Investigator fixed roll against Nimble Dodge",
        width=4,
        height=3,
        placements=(
            CreaturePlacement(
                "forensic_investigator",
                FORENSIC_INVESTIGATOR.definition_id,
                "Forensic Investigator",
                "blue",
                Position(1, 1),
            ),
            CreaturePlacement(
                "thief_rogue",
                content.ROGUE_THIEF_PLAYABLE.definition_id,
                "Thief Rogue",
                "red",
                Position(2, 1),
            ),
        ),
    )
    monkeypatch.setattr(
        content,
        "_STAGED_SETUPS",
        content._STAGED_SETUPS | {setup.setup_id: setup},
    )
    return setup


def test_selected_sheet_is_complete_but_stays_staged() -> None:
    investigator = FORENSIC_INVESTIGATOR
    assert (investigator.hp, investigator.ac, investigator.perception) == (17, 17, 6)
    assert dict(investigator.ability_modifiers) == {
        "strength": 0,
        "dexterity": 3,
        "constitution": 1,
        "intelligence": 4,
        "wisdom": 1,
        "charisma": 0,
    }
    assert dict((name, (rank, value)) for name, rank, value in investigator.saves) == {
        "fortitude": ("trained", 4),
        "reflex": ("expert", 8),
        "will": ("expert", 6),
    }
    trained = {name for name, rank, _value in investigator.skills if rank == "trained"}
    assert "underworld_lore" in trained
    assert len(trained) >= 13
    assert "Streetwise" in investigator.feats
    assert len(investigator.feats) >= 4
    assert investigator.languages[0] == "Common"
    assert len(set(investigator.languages)) == 6
    assert investigator.definition_id not in content.CREATURES
    assert investigator.definition_id in content._STAGED_CREATURES
    setup_id = "investigator_forensic_vs_two_guard_dogs"
    assert setup_id not in content.SETUPS and setup_id in content._STAGED_SETUPS


def test_complete_two_target_fight_keeps_stratagem_for_selected_target(
    tmp_path: Path,
) -> None:
    # Initiatives; Devise 14; other-target attack/damage; chosen-target
    # damage dice; dog miss; second Devise 20; critical damage dice.
    game = _investigator_game(20, 1, 2, 14, 10, 4, 3, 5, 1, 20, 1, 1)
    assert all(actor.hp == actor.max_hp for actor in game.inspect().actors)

    devised = game.execute(DeviseStratagem("investigator_guard_dog_a"))
    assert devised.status is ResultStatus.COMPLETED
    assert not any("recall" in (event.kind + event.text).lower() for event in devised.events)
    stored = game._state.creatures["forensic_investigator"].investigator_stratagem
    assert stored is not None and stored.die == 14 and not stored.consumed
    path = tmp_path / "investigator-unconsumed.json"
    game.save(path)
    game = Encounter.load(path)

    other = game.execute(Strike("investigator_guard_dog_b", attack_id="shortsword"))
    assert other.status is ResultStatus.PAUSED
    other_check = next(event.check for event in other.events if event.kind == "strike")
    assert other_check is not None
    assert (other_check.die, other_check.total, other_check.attack_count) == (10, 16, 1)
    assert "fortune" not in other_check.traits
    stored = game._state.creatures["forensic_investigator"].investigator_stratagem
    assert stored is not None and not stored.consumed
    assert _choose(game, "keep").status is ResultStatus.COMPLETED
    assert _actor(game, "investigator_guard_dog_b").hp == 4

    selected = game.execute(
        Strike(
            "investigator_guard_dog_a",
            attack_id="shortsword",
            use_intelligence=True,
        )
    )
    assert selected.status is ResultStatus.COMPLETED
    selected_check = next(event.check for event in selected.events if event.kind == "strike")
    assert selected_check is not None
    assert (
        selected_check.die,
        selected_check.total,
        selected_check.attack_count,
        selected_check.map_penalty,
    ) == (14, 17, 2, -4)
    assert "fortune" in selected_check.traits
    assert selected.inspection.choice is None
    damage = next(event.damage for event in selected.events if event.kind == "damage")
    assert damage is not None and damage.total == 8
    assert {component.source for component in damage.components} == {
        "shortsword",
        "investigator_strategic_strike",
    }
    assert _actor(game, "investigator_guard_dog_a").defeated

    assert game.inspect().turn_actor_id == "investigator_guard_dog_b"
    assert game.execute(
        Strike("forensic_investigator", attack_id="jaws")
    ).status is ResultStatus.COMPLETED
    assert _actor(game, "forensic_investigator").hp == 17
    assert game.execute(EndTurn()).status is ResultStatus.COMPLETED
    assert game.inspect().turn_actor_id == "forensic_investigator"

    assert game.execute(
        DeviseStratagem("investigator_guard_dog_b")
    ).status is ResultStatus.COMPLETED
    victory = game.execute(
        Strike(
            "investigator_guard_dog_b",
            attack_id="shortsword",
            use_intelligence=True,
        )
    )
    assert victory.status is ResultStatus.COMPLETED
    final_check = next(event.check for event in victory.events if event.kind == "strike")
    assert final_check is not None and final_check.die == 20
    final_damage = next(event.damage for event in victory.events if event.kind == "damage")
    assert final_damage is not None and final_damage.total == 4
    assert not game.inspect().in_progress and game.inspect().winner_team == "blue"


def test_fixed_natural_one_consumes_once_then_normal_attack_can_use_hero(
    tmp_path: Path,
) -> None:
    game = _investigator_game(20, 1, 2, 1, 20, 4)
    assert game.execute(
        DeviseStratagem("investigator_guard_dog_a")
    ).status is ResultStatus.COMPLETED
    failed = game.execute(
        Strike(
            "investigator_guard_dog_a",
            attack_id="shortsword",
            use_intelligence=True,
        )
    )
    assert failed.status is ResultStatus.COMPLETED
    failed_check = next(event.check for event in failed.events if event.kind == "strike")
    assert failed_check is not None
    assert (failed_check.die, failed_check.degree.name, failed_check.dice) == (
        1,
        "CRITICAL_FAILURE",
        (1,),
    )
    assert "fortune" in failed_check.traits
    assert not any(event.kind == "damage" for event in failed.events)
    assert _actor(game, "forensic_investigator").hero_points == 1

    ordinary = game.execute(Strike("investigator_guard_dog_a", attack_id="shortsword"))
    assert ordinary.status is ResultStatus.PAUSED
    ordinary_check = next(event.check for event in ordinary.events if event.kind == "strike")
    assert ordinary_check is not None
    assert (ordinary_check.die, ordinary_check.attack_count, ordinary_check.map_penalty) == (
        20,
        2,
        -4,
    )
    assert "fortune" not in ordinary_check.traits
    assert ordinary.inspection.choice is not None
    assert ordinary.inspection.choice.kind == "attack_hero_reroll"
    path = tmp_path / "investigator-normal-hero.json"
    game.save(path)
    game = Encounter.load(path)
    resolved = _choose(game, "keep")
    assert resolved.status is ResultStatus.COMPLETED
    damage = next(event.damage for event in resolved.events if event.kind == "damage")
    assert damage is not None and damage.total == 8


def test_declining_intelligence_keeps_fixed_die_but_has_no_precision() -> None:
    game = _investigator_game(20, 1, 2, 14, 3)
    assert game.execute(
        DeviseStratagem("investigator_guard_dog_a")
    ).status is ResultStatus.COMPLETED
    strike = game.execute(
        Strike(
            "investigator_guard_dog_a",
            attack_id="shortsword",
            use_intelligence=False,
        )
    )
    assert strike.status is ResultStatus.COMPLETED
    check = next(event.check for event in strike.events if event.kind == "strike")
    assert check is not None
    assert (check.die, check.modifier, check.total, check.dice) == (14, 6, 20, (14,))
    assert "fortune" in check.traits
    damage = next(event.damage for event in strike.events if event.kind == "damage")
    assert damage is not None and damage.total == 3
    assert [component.source for component in damage.components] == ["shortsword"]
    assert strike.inspection.choice is None


def test_unsupported_modes_known_weakness_frequency_and_expiry_are_atomic() -> None:
    game = _investigator_game(20, 1, 2, 14, 14)
    before = game.inspect()
    dice_before = game._dice.to_data()
    unsupported = game.execute(
        DeviseStratagem("investigator_guard_dog_a", mode=SKILL_STRATAGEM)
    )
    assert unsupported.status is ResultStatus.UNSUPPORTED
    assert game.inspect() == before and game._dice.to_data() == dice_before

    unsupported = game.execute(
        DeviseStratagem("investigator_guard_dog_a", free_action=True)
    )
    assert unsupported.status is ResultStatus.UNSUPPORTED
    assert game.inspect() == before and game._dice.to_data() == dice_before

    known = game.execute(
        DeviseStratagem("investigator_guard_dog_a", known_weaknesses=True)
    )
    assert known.status is ResultStatus.PAUSED
    assert game.inspect().choice is not None
    assert _choose(game, "keep").status is ResultStatus.COMPLETED
    assert game._state.creatures["forensic_investigator"].investigator_stratagem is not None

    once_before = game.inspect()
    once_dice = game._dice.to_data()
    repeated = game.execute(DeviseStratagem("investigator_guard_dog_b"))
    assert repeated.status is ResultStatus.REJECTED
    assert game.inspect() == once_before and game._dice.to_data() == once_dice

    assert game.execute(EndTurn()).status is ResultStatus.COMPLETED
    assert game.execute(EndTurn()).status is ResultStatus.COMPLETED
    assert game.execute(EndTurn()).status is ResultStatus.COMPLETED
    assert game.inspect().turn_actor_id == "forensic_investigator"
    assert game._state.creatures["forensic_investigator"].investigator_stratagem is None
    assert game.options().investigator_stratagem_target_id is None
    assert "devise_stratagem" in game.options().available_actions


def test_saved_nimble_dodge_precedes_fixed_roll_consumption(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    game = Encounter.start(_nimble_setup(monkeypatch), rolls=(20, 1, 14, 3, 4))
    _settle_initiative(game)
    assert game.execute(DeviseStratagem("thief_rogue")).status is ResultStatus.COMPLETED
    attack = game.execute(
        Strike("thief_rogue", attack_id="shortsword", use_intelligence=True)
    )
    assert attack.status is ResultStatus.PAUSED
    nimble = attack.inspection.choice
    assert nimble is not None and nimble.kind == "nimble_dodge"
    stored = game._state.creatures["forensic_investigator"].investigator_stratagem
    assert stored is not None and not stored.consumed
    path = tmp_path / "investigator-nimble.json"
    game.save(path)
    game = Encounter.load(path)
    assert game.inspect().choice == nimble

    resolved = _choose(game, "use")
    assert resolved.status is ResultStatus.COMPLETED
    check = next(event.check for event in resolved.events if event.kind == "strike")
    assert check is not None
    assert (check.die, check.total, check.dc, check.dice) == (14, 21, 20, (14,))
    assert "fortune" in check.traits
    assert resolved.inspection.choice is None
    damage = next(event.damage for event in resolved.events if event.kind == "damage")
    assert damage is not None and damage.total == 7
    stored = game._state.creatures["forensic_investigator"].investigator_stratagem
    assert stored is not None and stored.consumed
