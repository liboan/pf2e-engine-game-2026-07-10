"""Focused source-to-sheet checks for the first-wave martial L2 records."""

from pf2e import EndTurn
from pf2e.barbarian import Rage, no_escape_is_eligible
from pf2e.barbarian_content import BARBARIAN_SLICE1_CHARACTER
from pf2e.content import GUARD_DOG, MELEE_FIGHTER_M
from pf2e.fighter import sudden_charge_is_legal
from pf2e.l2_martial_content import build_l2_martial_content
from pf2e.monk import FlurryOfBlows, stunning_blows_is_eligible
from pf2e.encounter import Encounter
from pf2e.model import AttackDefinition, CreaturePlacement, EncounterSetup, PairedStrikeSelection, Position, ResultStatus, Stride
from pf2e.paired_strikes import _decode_selection
from pf2e.ranger_monk_content import MONK
from pf2e.fighter import SuddenCharge
from pf2e.terminal import run_terminal
from terminal_test_helpers import BoundedInput, BoundedTranscript
from dataclasses import replace
from types import MappingProxyType

import pytest
import pf2e.content as content


def _content():
    return build_l2_martial_content(
        fighter=MELEE_FIGHTER_M,
        barbarian=BARBARIAN_SLICE1_CHARACTER.definition,
        monk=MONK,
        enemy_definition_id=GUARD_DOG.definition_id,
    )


def _settle_initiative(game: Encounter) -> None:
    for _ in range(8):
        choice = game.inspect().choice
        if choice is None:
            return
        option_id = "keep" if any(option.option_id == "keep" for option in choice.options) else choice.options[0].option_id
        assert game.choose(choice.choice_id, option_id, choice.owner_actor_id).status in {
            ResultStatus.PAUSED, ResultStatus.COMPLETED,
        }
    raise AssertionError("initiative did not settle")


def _choose(game: Encounter, option_id: str):
    choice = game.inspect().choice
    assert choice is not None
    return game.choose(choice.choice_id, option_id, choice.owner_actor_id)


def _second_flurry_option(game: Encounter, target_id: str) -> str:
    choice = game.inspect().choice
    assert choice is not None and choice.kind == "family_action"
    for option in choice.options:
        selection = _decode_selection(option.option_id)
        if selection is not None and selection.target_id == target_id and selection.attack_id == "fist":
            return option.option_id
    raise AssertionError("same-target fist option was not offered")


def test_l2_martial_sheets_advance_only_level_based_statistics_and_selected_choices() -> None:
    definitions, setups = _content()
    fighter = definitions["fighter_m_level_2_sudden_charge"]
    barbarian = definitions["barbarian_animal_bear_level_2_no_escape"]
    barbarian_sudden_charge = definitions["barbarian_animal_bear_level_2_sudden_charge"]
    monk = definitions["monk_monastic_weaponry_level_2_stunning_blows"]

    assert (fighter.level, fighter.hp, fighter.ac, fighter.perception, fighter.class_dc) == (2, 34, 19, 7, 18)
    assert (barbarian.level, barbarian.hp, barbarian.ac, barbarian.perception, barbarian.class_dc) == (2, 38, 19, 7, 18)
    assert (monk.level, monk.hp, monk.ac, monk.perception, monk.class_dc) == (2, 32, 20, 5, 18)
    assert {"Sudden Charge", "Quick Jump"} <= set(fighter.feats)
    assert {"No Escape", "Quick Jump"} <= set(barbarian.feats)
    assert {"Sudden Charge", "Quick Jump"} <= set(barbarian_sudden_charge.feats)
    assert {"Stunning Blows", "Assurance (Athletics)"} <= set(monk.feats)
    assert {"sudden_charge", "no_escape", "stunning_blows"} <= {
        *fighter.abilities, *barbarian.abilities, *barbarian_sudden_charge.abilities, *monk.abilities,
    }
    assert set(setups) == {
        "staged_fighter_level_2_sudden_charge",
        "staged_barbarian_level_2_no_escape",
        "staged_barbarian_level_2_sudden_charge",
        "staged_monk_level_2_stunning_blows",
    }


def test_sudden_charge_requires_two_real_movement_legs_and_an_all_or_nothing_optional_strike() -> None:
    assert sudden_charge_is_legal(
        abilities=("sudden_charge",), actions_remaining=2,
        first_path=(Position(1, 1),), second_path=(Position(2, 1),),
        target_id=None, attack_id=None,
    )
    assert not sudden_charge_is_legal(
        abilities=("sudden_charge",), actions_remaining=2, first_path=(), second_path=(),
        target_id="dog", attack_id="longsword",
    )
    assert not sudden_charge_is_legal(
        abilities=("sudden_charge",), actions_remaining=2,
        first_path=(Position(1, 1),), second_path=(Position(2, 1),),
        target_id="dog", attack_id=None,
    )


def test_intimidating_strike_requires_the_admitted_grant_and_two_actions() -> None:
    assert intimidating_strike_is_legal(abilities=("intimidating_strike",), actions_remaining=2)
    assert not intimidating_strike_is_legal(abilities=(), actions_remaining=3)
    assert not intimidating_strike_is_legal(abilities=("intimidating_strike",), actions_remaining=1)


def test_intimidating_strike_rejects_a_ranged_attack_before_committing_costs(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from pf2e.content import get_setup

    definition = content.CREATURES["fighter_m_level_2_intimidating_strike"]
    ranged = AttackDefinition(
        "intimidating_review_bow", "Review Bow", 8, 0,
        frozenset({"attack", "ranged"}), "piercing", (6,), 0,
        range_increment_ft=30, max_range_ft=180,
    )
    monkeypatch.setattr(
        content,
        "CREATURES",
        MappingProxyType({
            **content.CREATURES,
            definition.definition_id: replace(definition, attacks=(*definition.attacks, ranged)),
        }),
    )
    game = Encounter.start(get_setup("staged_fighter_level_2_intimidating_strike"), rolls=(20, 1))
    _settle_initiative(game)
    result = game.execute(IntimidatingStrike("dog", "intimidating_review_bow"))
    assert result.status is ResultStatus.REJECTED
    fighter = game._state.creatures["fighter"]
    assert fighter.actions_remaining == 3 and fighter.strikes_this_turn == 0


def test_intimidating_strike_respects_the_printed_mindless_mental_immunity() -> None:
    """AoN feat 4782's mental trait cannot frighten a mindless creature."""
    from pf2e.model import CreatureState, EncounterState, FamilyProcedureContext
    from pf2e.opponent_content import SKELETON_GUARD

    fighter = CreatureState("fighter", "fighter_m_level_2_intimidating_strike", "Fighter", "blue", Position(0, 0), 34)
    skeleton = CreatureState("skeleton", SKELETON_GUARD.definition.definition_id, "Skeleton", "red", Position(1, 0), 4)
    context = FamilyProcedureContext(
        encounter=None,
        state=EncounterState(
            setup_id="fixture", map_width=2, map_height=1,
            creatures={"fighter": fighter, "skeleton": skeleton},
            initiative_order=[], active_index=0,
        ),
        dice=None,
        actor=fighter,
        definition=MELEE_FIGHTER_M,
        family_id="martial",
    )
    assert intimidating_strike_target_is_immune(context, "skeleton")


def test_intimidating_strike_uses_one_melee_attack_then_saves_frightened_result(
    tmp_path,
) -> None:
    """PC1/PC2 feat 368: hit + damage makes frightened 1; crit makes 2."""
    from pf2e.content import get_setup

    game = Encounter.start(
        get_setup("staged_fighter_level_2_intimidating_strike"), rolls=(20, 1, 12, 1),
    )
    _settle_initiative(game)
    assert "intimidating_strike" in game.options().available_actions
    paused = game.execute(IntimidatingStrike("dog", "longsword"))
    assert paused.status is ResultStatus.PAUSED
    assert game._state.creatures["fighter"].actions_remaining == 1
    assert game._state.creatures["fighter"].strikes_this_turn == 1
    assert game.inspect().choice is not None and game.inspect().choice.kind == "attack_hero_reroll"

    path = tmp_path / "fighter-intimidating-strike.json"
    game.save(path)
    game = Encounter.load(path)
    resolved = _choose(game, "keep")
    assert resolved.status is ResultStatus.COMPLETED
    assert any(event.kind == "condition_applied" and "frightened 1" in event.text for event in resolved.events)
    frightened = [effect for effect in game.inspect().actors[1].condition_effects if effect.kind == "frightened"]
    assert len(frightened) == 1 and frightened[0].value == 1

    critical = Encounter.start(
        get_setup("staged_fighter_level_2_intimidating_strike"), rolls=(20, 1, 20, 1),
    )
    _settle_initiative(critical)
    assert critical.execute(IntimidatingStrike("dog", "longsword")).status is ResultStatus.PAUSED
    result = _choose(critical, "keep")
    assert result.status is ResultStatus.COMPLETED and critical.inspect().winner_team == "blue"
    assert any(event.kind == "condition_applied" and "frightened 2" in event.text for event in result.events)
    dog = next(actor for actor in critical.inspect().actors if actor.actor_id == "dog")
    assert next(effect.value for effect in dog.condition_effects if effect.kind == "frightened") == 2


def test_barbarian_intimidating_strike_is_a_distinct_legal_grant() -> None:
    from pf2e.content import get_setup

    game = Encounter.start(
        get_setup("staged_barbarian_level_2_intimidating_strike"), rolls=(20, 1),
    )
    # This Bear can receive a Quick-Tempered initiative offer. Declining it
    # keeps the alternate feat's normal two-action availability observable.
    for _ in range(8):
        choice = game.inspect().choice
        if choice is None:
            break
        option = "decline" if any(item.option_id == "decline" for item in choice.options) else "keep"
        game.choose(choice.choice_id, option, choice.owner_actor_id)
    assert game.inspect().turn_actor_id == "barbarian"
    assert "intimidating_strike" in game.options().available_actions

def test_no_escape_and_stunning_blows_remain_narrow_trigger_predicates() -> None:
    assert no_escape_is_eligible(
        abilities=("no_escape",), rage_active=True, reaction_available=True,
        enemy_started_in_reach=True, enemy_is_moving_away=True,
    )
    assert not no_escape_is_eligible(
        abilities=("no_escape",), rage_active=False, reaction_available=True,
        enemy_started_in_reach=True, enemy_is_moving_away=True,
    )
    assert stunning_blows_is_eligible(
        abilities=("stunning_blows",), first_target_id="dog", second_target_id="dog",
        first_hit=False, second_hit=True, first_damage=None, second_damage=4,
    )
    assert not stunning_blows_is_eligible(
        abilities=("stunning_blows",), first_target_id="dog", second_target_id="other",
        first_hit=True, second_hit=True, first_damage=4, second_damage=4,
    )
    assert not stunning_blows_is_eligible(
        abilities=("stunning_blows",), first_target_id="dog", second_target_id="dog",
        first_hit=True, second_hit=False, first_damage=0, second_damage=None,
    )


def test_fighter_sudden_charge_is_paid_once_saved_at_final_strike_and_finishes_the_fight(tmp_path) -> None:
    from pf2e.content import get_setup

    game = Encounter.start(
        get_setup("staged_fighter_level_2_sudden_charge"), rolls=(20, 1, 20, 6),
    )
    _settle_initiative(game)
    started = game.execute(SuddenCharge(
        (Position(1, 1), Position(2, 1)), (Position(3, 1), Position(4, 1)),
        "dog", "longsword",
    ))
    assert started.status is ResultStatus.PAUSED
    assert any(event.kind == "sudden_charge_started" for event in started.events)
    assert game._state.creatures["fighter"].actions_remaining == 1
    assert game.inspect().choice is not None and game.inspect().choice.kind == "attack_hero_reroll"

    path = tmp_path / "fighter-sudden-charge-strike.json"
    game.save(path)
    game = Encounter.load(path)
    finished = _choose(game, "keep")
    assert finished.status is ResultStatus.COMPLETED
    assert game.inspect().winner_team == "blue"
    assert game._state.creatures["fighter"].strikes_this_turn == 1


def test_barbarian_sudden_charge_reuses_fighter_contract_and_saved_reaction_resumes(
    tmp_path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    setup = EncounterSetup(
        "test_l2_barbarian_sudden_charge_reactive_path",
        "Level 2 Barbarian Sudden Charge through Reactive Strike",
        5,
        3,
        (
            CreaturePlacement(
                "barbarian", "barbarian_animal_bear_level_2_sudden_charge", "Barbarian", "blue", Position(1, 1),
            ),
            CreaturePlacement("reactor", "fighter_m_level_1", "Reactive Fighter", "red", Position(2, 1)),
        ),
    )
    monkeypatch.setattr(
        content,
        "_STAGED_SETUPS",
        MappingProxyType({**content._STAGED_SETUPS, setup.setup_id: setup}),
    )
    game = Encounter.start(setup, rolls=(20, 1, 1))
    _settle_initiative(game)
    started = game.execute(SuddenCharge(
        (Position(1, 0),), (Position(0, 0),), None, None,
    ))
    assert started.status is ResultStatus.PAUSED
    assert game.inspect().choice is not None and game.inspect().choice.kind == "reaction"
    assert _choose(game, "accept").inspection.choice is not None
    assert game.inspect().choice.kind == "attack_hero_reroll"
    path = tmp_path / "barbarian-sudden-charge-reaction.json"
    game.save(path)
    game = Encounter.load(path)
    finished = _choose(game, "keep")
    assert finished.status is ResultStatus.COMPLETED
    assert game._state.creatures["barbarian"].position == Position(0, 0)
    assert game._state.creatures["barbarian"].actions_remaining == 1


def test_no_escape_requires_rage_and_saved_pursuit_spends_only_the_reaction(tmp_path) -> None:
    from pf2e.content import get_setup

    def begin_dog_departure(*, rage: bool) -> Encounter:
        game = Encounter.start(get_setup("staged_barbarian_level_2_no_escape"), rolls=(20, 1))
        # This retained Bear also has Quick-Tempered.  Decline its optional
        # initiative-time Rage so this test can prove both sides of No
        # Escape's explicit Rage prerequisite rather than treating the
        # inherited baseline prompt as a generic initiative choice.
        for _ in range(8):
            choice = game.inspect().choice
            if choice is None:
                break
            option_id = (
                "decline" if choice.kind == "family_action" and any(
                    option.option_id == "decline" for option in choice.options
                ) else "keep" if any(option.option_id == "keep" for option in choice.options)
                else choice.options[0].option_id
            )
            assert game.choose(choice.choice_id, option_id, choice.owner_actor_id).status in {
                ResultStatus.PAUSED, ResultStatus.COMPLETED,
            }
        else:
            raise AssertionError("initiative did not settle after declining Quick-Tempered")
        assert game.inspect().turn_actor_id == "barbarian"
        if rage:
            assert game.execute(Rage()).status is ResultStatus.COMPLETED
        assert game.execute(EndTurn()).status is ResultStatus.COMPLETED
        assert game.inspect().turn_actor_id == "dog"
        return game

    # The printed reaction has a Rage prerequisite; an otherwise identical
    # departure must remain an ordinary completed Stride.
    unraged = begin_dog_departure(rage=False)
    departed = unraged.execute(Stride((Position(4, 1),)))
    assert departed.status is ResultStatus.COMPLETED
    assert not any(event.kind == "no_escape_triggered" for event in departed.events)

    declined = begin_dog_departure(rage=True)
    assert declined.execute(Stride((Position(4, 1),))).status is ResultStatus.PAUSED
    declined_result = _choose(declined, "decline")
    assert any(event.kind == "no_escape_declined" for event in declined_result.events)
    assert declined._state.creatures["barbarian"].reaction_available
    assert declined._state.creatures["barbarian"].position == Position(2, 1)

    game = begin_dog_departure(rage=True)
    paused = game.execute(Stride((Position(4, 1),)))
    assert paused.status is ResultStatus.PAUSED
    assert any(event.kind == "no_escape_triggered" for event in paused.events)
    assert game.inspect().choice is not None and game.inspect().choice.kind == "no_escape"

    save_path = tmp_path / "no-escape-pending.json"
    game.save(save_path)
    game = Encounter.load(save_path)
    resumed = _choose(game, "pursue")
    barbarian = game._state.creatures["barbarian"]
    dog = game._state.creatures["dog"]
    assert any(event.kind == "no_escape_pursuit" for event in resumed.events)
    assert not barbarian.reaction_available
    assert barbarian.position != Position(2, 1)
    assert max(abs(barbarian.position.x - dog.position.x), abs(barbarian.position.y - dog.position.y)) == 1

    # A reaction-paid pursuit is not frozen at the first departure square:
    # the same move can continue, consuming only the original reaction while
    # the Bear follows with its remaining Speed.
    follow = begin_dog_departure(rage=True)
    assert follow.execute(Stride((Position(4, 1), Position(5, 1)))).status is ResultStatus.PAUSED
    followed = _choose(follow, "pursue")
    assert any(event.kind == "no_escape_follow" for event in followed.events)
    assert follow._state.creatures["barbarian"].position == Position(4, 0)
    assert follow._state.creatures["dog"].position == Position(5, 1)


def test_stunning_blows_uses_same_target_damage_then_serializes_stunned_state(tmp_path) -> None:
    from pf2e.content import get_setup

    # Initiative, two hits/d6 damage, then a natural 1 Fortitude save.  The
    # dog survives the paired Strikes so the post-Flurry saving throw is live.
    game = Encounter.start(get_setup("staged_monk_level_2_stunning_blows"), rolls=(20, 1, 12, 1, 12, 1, 1))
    _settle_initiative(game)
    assert game.inspect().turn_actor_id == "monk"
    assert game.execute(FlurryOfBlows(PairedStrikeSelection("dog", "fist"))).status is ResultStatus.PAUSED
    assert _choose(game, "keep").status is ResultStatus.PAUSED
    assert _choose(game, _second_flurry_option(game, "dog")).status is ResultStatus.PAUSED
    offered = _choose(game, "keep")
    assert offered.status is ResultStatus.PAUSED
    choice = game.inspect().choice
    assert choice is not None and choice.kind == "stunning_blows"
    result = _choose(game, "attempt")
    save_event = next(event for event in result.events if event.kind == "stunning_blows_save")
    assert save_event.check is not None and save_event.check.degree.label().lower() == "critical failure"
    assert any(event.kind == "condition_applied" for event in result.events)
    assert game._state.creatures["dog"].stunned == 3

    path = tmp_path / "stunning-blows-stunned.json"
    game.save(path)
    game = Encounter.load(path)
    dog = game._state.creatures["dog"]
    assert dog.stunned == 3 and dog.stunned_source_actor_id == "monk"
    next_turn = game.execute(EndTurn())
    assert any(event.kind == "stunned_actions_lost" for event in next_turn.events)
    dog = game._state.creatures["dog"]
    assert dog.stunned == 0 and dog.actions_remaining == 0


def test_stunning_blows_can_be_declined_and_a_stunned_pc_cannot_react(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    setup = EncounterSetup(
        "test_l2_stunning_blows_pc_reaction_boundary",
        "Level 2 Monk Stunning Blows against a reactive Fighter",
        5,
        3,
        (
            CreaturePlacement(
                "monk", "monk_monastic_weaponry_level_2_stunning_blows", "Level 2 Monk", "red", Position(1, 1),
            ),
            CreaturePlacement("fighter", "fighter_m_level_1", "Reactive Fighter", "blue", Position(2, 1)),
        ),
    )
    monkeypatch.setattr(
        content, "_STAGED_SETUPS", MappingProxyType({**content._STAGED_SETUPS, setup.setup_id: setup}),
    )
    game = Encounter.start(setup, rolls=(20, 1, 12, 1, 12, 1, 1))
    _settle_initiative(game)
    assert game.execute(FlurryOfBlows(PairedStrikeSelection("fighter", "fist"))).status is ResultStatus.PAUSED
    assert _choose(game, "keep").status is ResultStatus.PAUSED
    assert _choose(game, _second_flurry_option(game, "fighter")).status is ResultStatus.PAUSED
    assert _choose(game, "keep").status is ResultStatus.PAUSED
    assert game.inspect().choice is not None and game.inspect().choice.kind == "stunning_blows"

    # The printed rider is optional: declining it produces no Fortitude
    # check and leaves the target without the rider condition.
    declined = _choose(game, "decline")
    assert any(event.kind == "stunning_blows_declined" for event in declined.events)
    assert game._state.creatures["fighter"].stunned == 0

    game = Encounter.start(setup, rolls=(20, 1, 12, 1, 12, 1, 1))
    _settle_initiative(game)
    assert game.execute(FlurryOfBlows(PairedStrikeSelection("fighter", "fist"))).status is ResultStatus.PAUSED
    assert _choose(game, "keep").status is ResultStatus.PAUSED
    assert _choose(game, _second_flurry_option(game, "fighter")).status is ResultStatus.PAUSED
    assert _choose(game, "keep").status is ResultStatus.PAUSED
    assert _choose(game, "attempt").status is ResultStatus.PAUSED
    assert game.inspect().choice is not None and game.inspect().choice.kind == "stunning_blows_hero_reroll"
    resolved = _choose(game, "keep")
    assert any(event.kind == "condition_applied" for event in resolved.events)
    assert game._state.creatures["fighter"].stunned == 3
    assert not game._state.creatures["fighter"].reaction_available

    departure = game.execute(Stride((Position(0, 1),)))
    assert departure.status is ResultStatus.COMPLETED
    assert not any(event.kind == "reaction" for event in departure.events)


def test_terminal_exposes_normal_catalog_sudden_charge_and_its_ordinary_strike() -> None:
    from pf2e.content import get_setup

    transcript = BoundedTranscript(max_lines=160, max_chars=24_000)
    menu = {"text": "", "prompt": ""}
    main_actions = iter(("Sudden Charge", "Quit"))

    def output(line: str) -> None:
        transcript.append(line)
        if line.startswith("1. "):
            menu["text"] = line
        if line.endswith(":"):
            menu["prompt"] = line

    def menu_number_containing(label: str) -> str:
        for row in menu["text"].splitlines():
            if ". " in row and label in row.split(". ", 1)[1]:
                return row.split(". ", 1)[0]
        raise AssertionError(f"missing terminal menu item containing {label!r}: {menu['text']!r}")

    def script() -> str:
        prompt = menu["prompt"]
        if prompt == "Choice:":
            return menu_number_containing(next(main_actions))
        if prompt == "Choice prompt action:":
            return "2"
        if prompt == "Choice option number:":
            return menu_number_containing("Keep")
        if prompt == "Sudden Charge first Stride path (for example B2 C2):":
            return "B2 C2"
        if prompt == "Sudden Charge second Stride path (for example D2 E2):":
            return "D2 E2"
        if prompt == "Weapon / attack number:":
            return menu_number_containing("Longsword")
        if prompt == "Longsword target:":
            return menu_number_containing("Guard Dog")
        if prompt == "Damage intent:":
            return menu_number_containing("Use attack default")
        raise AssertionError(f"unexpected terminal prompt: {prompt!r}")

    assert run_terminal(
        setup=get_setup("staged_fighter_level_2_sudden_charge"), rolls=(20, 1, 20, 6),
        input_fn=BoundedInput(script, max_calls=40), output_fn=output,
    ) == 0
    rendered = "\n".join(transcript)
    assert "Sudden Charge" in rendered
    assert "Level 2 Fighter begins Sudden Charge" in rendered
    assert "Attack: d20 20" in rendered and "critical success" in rendered
