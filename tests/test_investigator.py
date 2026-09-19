"""Focused checks for the bounded Investigator stratagem source packet."""

from types import SimpleNamespace

from pf2e.damage import roll_damage_terms
from pf2e.content import CREATURES, SETUPS, get_definition, get_setup
from pf2e.encounter import Encounter
from pf2e.investigator import (
    ATTACK_STRATAGEM,
    DEVISE_ABILITY,
    SKILL_STRATAGEM,
    DeviseStratagem,
    InvestigatorStratagemState,
    consume_stratagem,
    handle_action,
    intelligence_substitution_eligible,
    resolve_stratagem_check,
    strategic_strike_damage_term,
    stratagem_from_data,
    stratagem_for_attack,
    stratagem_to_data,
)
from pf2e.investigator_content import (
    FORENSIC_INVESTIGATOR,
    FORENSIC_INVESTIGATOR_HEALING_SETUP,
    FORENSIC_INVESTIGATOR_VS_TWO_DOGS,
)
import pf2e.terminal as terminal
from pf2e import family_martial
from pf2e.model import (
    AttackDefinition,
    Choose,
    CreatureState,
    EndTurn,
    FamilyProcedureContext,
    HealthMode,
    Position,
    ResultStatus,
    Strike,
)
from pf2e.persistence import DiceSource
from pf2e.terminal import run_terminal
from terminal_test_helpers import BoundedInput, BoundedTranscript


def _attack(*traits: str) -> AttackDefinition:
    return AttackDefinition(
        attack_id="test_weapon",
        name="Test weapon",
        modifier=6,
        reach_ft=5,
        traits=frozenset({"attack", *traits}),
        damage_type="piercing",
        damage_dice=(6,),
        damage_modifier=0,
    )


def _context(
    *, mode: str = ATTACK_STRATAGEM, free_action: bool = False, known_weaknesses: bool = False
):
    actor = CreatureState(
        actor_id="investigator",
        definition_id=FORENSIC_INVESTIGATOR.definition_id,
        label="Investigator",
        team="blue",
        position=Position(1, 1),
        hp=17,
        health_mode=HealthMode.PC,
        actions_remaining=3,
    )
    target = CreatureState(
        actor_id="foe",
        definition_id="foe",
        label="Foe",
        team="red",
        position=Position(2, 1),
        hp=10,
        health_mode=HealthMode.ORDINARY,
    )
    state = SimpleNamespace(
        creatures={actor.actor_id: actor, target.actor_id: target},
        round_number=1,
        actor_start_counts={actor.actor_id: 1},
        taking_cover=set(),
    )

    class _Encounter:
        @staticmethod
        def _commit_family_action(context, *, actions, attacks=0):
            context.actor.actions_remaining -= actions
            context.actor.strikes_this_turn += attacks
            context.state.taking_cover.discard(context.actor.actor_id)

        @staticmethod
        def _complete_action(state, actor, events, *, dice):
            return events

    context = FamilyProcedureContext(
        _Encounter(),
        state,
        DiceSource(rolls=(14,)),
        actor,
        FORENSIC_INVESTIGATOR,
        "martial",
        command=DeviseStratagem("foe", mode, free_action, known_weaknesses),
    )
    context.require_action_permitted = lambda *_args: None
    return context, actor, state


def test_selected_forensic_sheet_has_legal_first_play_facts() -> None:
    assert FORENSIC_INVESTIGATOR.class_name == "Investigator"
    assert FORENSIC_INVESTIGATOR.hp == 17
    assert FORENSIC_INVESTIGATOR.ability_modifiers[3] == ("intelligence", 4)
    assert "society" in {skill for skill, _rank, _modifier in FORENSIC_INVESTIGATOR.skills}
    skills = {skill for skill, _rank, _modifier in FORENSIC_INVESTIGATOR.skills}
    assert {"underworld_lore", "diplomacy", "deception", "survival", "intimidation"} <= skills
    assert DEVISE_ABILITY in FORENSIC_INVESTIGATOR.abilities
    assert FORENSIC_INVESTIGATOR.attacks[0].traits >= {"agile", "finesse"}
    assert FORENSIC_INVESTIGATOR.feats == (
        "Natural Skill", "Forensic Acumen", "Known Weaknesses", "Battle Medicine", "Streetwise"
    )
    assert len(FORENSIC_INVESTIGATOR.languages) == 6
    assert set(FORENSIC_INVESTIGATOR.languages[1:]) == {
        "Dwarven", "Elven", "Goblin", "Halfling", "Orcish"
    }


def test_devise_stores_preliminary_d20_and_commits_one_action() -> None:
    context, actor, state = _context()
    result = family_martial.handle_action(context)

    assert result is not None and result.rejection is None and result.unsupported is None
    assert actor.actions_remaining == 2
    assert actor.investigator_stratagem == InvestigatorStratagemState(
        target_id="foe", die=14, mode=ATTACK_STRATAGEM, round_number=1, turn_start=1
    )
    assert result.events[0].kind == "devise_stratagem"
    assert "preliminary d20 is 14" in result.events[0].text


def test_investigator_slice_is_catalogued_with_its_stable_ids(monkeypatch) -> None:
    setup_id = FORENSIC_INVESTIGATOR_VS_TWO_DOGS.setup_id
    definition_id = FORENSIC_INVESTIGATOR.definition_id

    assert setup_id in SETUPS
    assert FORENSIC_INVESTIGATOR_HEALING_SETUP.setup_id in SETUPS
    assert definition_id in CREATURES
    assert get_setup(setup_id).setup_id == setup_id
    assert get_definition(definition_id) == FORENSIC_INVESTIGATOR
    seen = {}

    def capture_run(*, setup, seed, save_path):
        seen.update(setup=setup, seed=seed, save_path=save_path)
        return 0

    monkeypatch.setattr(terminal, "run_terminal", capture_run)
    assert terminal.main(["play", setup_id, "--seed", "27", "--save-path", "investigator.json"]) == 0
    assert seen == {"setup": FORENSIC_INVESTIGATOR_VS_TWO_DOGS, "seed": 27, "save_path": "investigator.json"}


def test_devise_accepts_skill_and_rejects_unaware_free_mode_without_spending_again() -> None:
    skill_context, skill_actor, _state = _context(mode=SKILL_STRATAGEM)
    skill_result = handle_action(skill_context)
    assert skill_result is not None and skill_result.rejection is None and skill_result.unsupported is None
    assert skill_actor.actions_remaining == 2
    assert skill_actor.investigator_stratagem is not None
    assert skill_actor.investigator_stratagem.mode == SKILL_STRATAGEM

    free_context, free_actor, _state = _context(free_action=True)
    free_result = handle_action(free_context)
    assert free_result is not None and free_result.rejection is not None
    assert free_actor.actions_remaining == 3

    known_context, known_actor, _state = _context(known_weaknesses=True)
    known_result = handle_action(known_context)
    assert known_result is not None and known_result.unsupported is not None
    assert "Known Weaknesses" in known_result.unsupported
    assert known_actor.actions_remaining == 3
    assert known_actor.investigator_stratagem is None


def test_stratagem_consumes_exact_face_once_and_expires_at_owner_turn() -> None:
    context, actor, state = _context()
    handle_action(context)
    pending = stratagem_for_attack(
        actor, target_id="foe", round_number=1, turn_start=1
    )
    assert pending is not None and pending.die == 14
    consumed = consume_stratagem(
        actor, target_id="foe", round_number=1, turn_start=1
    )
    assert consumed is not None and consumed[0] == 14 and consumed[1].consumed
    assert consume_stratagem(
        actor, target_id="foe", round_number=1, turn_start=1
    ) is None
    assert stratagem_for_attack(
        actor, target_id="foe", round_number=1, turn_start=2
    ) is None

    check = resolve_stratagem_check(
        consumed[1],
        modifier=4,
        dc=18,
        attack_id="shortsword",
        attack_count=2,
        map_penalty=-4,
        traits=frozenset({"attack", "melee", "agile", "finesse"}),
    )
    assert (check.die, check.total, check.map_penalty) == (14, 18, -4)
    assert "fortune" in check.traits


def test_intelligence_substitution_gate_and_strategic_strike_precision() -> None:
    shortsword = _attack("melee", "agile", "finesse")
    plain_melee = _attack("melee")
    bow = _attack("ranged")
    plain_thrown = _attack("ranged", "thrown")
    assert intelligence_substitution_eligible(shortsword)
    assert not intelligence_substitution_eligible(plain_melee)
    assert intelligence_substitution_eligible(bow)
    assert not intelligence_substitution_eligible(plain_thrown)

    term = strategic_strike_damage_term(
        shortsword, used_intelligence=True, investigator_level=1
    )
    assert term is not None
    assert term.source == "investigator_strategic_strike"
    assert term.tags == frozenset({"precision"})
    assert term.dice == (6,)
    assert roll_damage_terms((term,), lambda _sides: 3).total == 3
    assert strategic_strike_damage_term(
        shortsword, used_intelligence=False, investigator_level=1
    ) is None
    assert strategic_strike_damage_term(
        plain_melee, used_intelligence=True, investigator_level=1
    ) is None


def test_stratagem_save_shape_round_trips_and_rejects_corrupt_faces() -> None:
    state = InvestigatorStratagemState(
        target_id="foe", die=14, mode=ATTACK_STRATAGEM,
        round_number=1, turn_start=1, consumed=True,
    )
    encoded = stratagem_to_data(state)
    assert encoded == {
        "target_id": "foe", "die": 14, "mode": "attack",
        "round_number": 1, "turn_start": 1, "consumed": True,
    }
    assert stratagem_from_data(encoded) == state
    try:
        stratagem_from_data({**encoded, "die": 21})
    except ValueError as error:
        assert "invalid Investigator stratagem" in str(error)
    else:
        raise AssertionError("an out-of-range saved d20 must be rejected")


def _public_investigator() -> Encounter:
    game = Encounter.start(
        get_setup("investigator_forensic_vs_two_guard_dogs"),
        rolls=(20, 1, 2, 14, 3, 4),
    )
    if game.inspect().choice is not None:
        assert game.inspect().choice.kind == "initiative_hero_reroll"
        assert game.execute(Choose(game.inspect().choice.choice_id, "keep")).status is ResultStatus.COMPLETED
    assert game.inspect().turn_actor_id == "forensic_investigator"
    return game


def test_public_devise_then_eligible_strike_uses_saved_roll_and_precision() -> None:
    game = _public_investigator()
    devise = game.execute(DeviseStratagem(target_id="investigator_guard_dog_a", mode=ATTACK_STRATAGEM))
    assert devise.status is ResultStatus.COMPLETED
    assert game._state.creatures["forensic_investigator"].actions_remaining == 2
    strike = game.execute(
        Strike(
            target_id="investigator_guard_dog_a",
            attack_id="shortsword",
            use_intelligence=True,
        )
    )
    assert strike.status is ResultStatus.COMPLETED
    attack = next(event for event in strike.events if event.kind == "strike")
    assert attack.check is not None
    assert (attack.check.die, attack.check.total, attack.check.traits) == (
        14, 21, ("agile", "attack", "finesse", "fortune", "melee", "weapon")
    )
    damage = next(event for event in strike.events if event.kind == "damage")
    assert damage.damage is not None and damage.damage.total == 7
    assert "investigator_strategic_strike" in damage.text
    assert game._state.creatures["investigator_guard_dog_a"].hp == 1
    assert game._state.creatures["forensic_investigator"].investigator_stratagem.consumed


def test_public_save_load_preserves_unconsumed_stratagem_before_strike(tmp_path) -> None:
    game = _public_investigator()
    assert game.execute(DeviseStratagem(target_id="investigator_guard_dog_a", mode=ATTACK_STRATAGEM)).status is ResultStatus.COMPLETED
    path = tmp_path / "investigator-before-strike.json"
    game.save(path)
    loaded = Encounter.load(path)
    saved = loaded._state.creatures["forensic_investigator"].investigator_stratagem
    assert saved is not None and saved.die == 14 and not saved.consumed
    result = loaded.execute(
        Strike(target_id="investigator_guard_dog_a", attack_id="shortsword", use_intelligence=True)
    )
    attack = next(event for event in result.events if event.kind == "strike")
    assert attack.check is not None and attack.check.die == 14
    assert loaded._state.creatures["forensic_investigator"].investigator_stratagem.consumed


def test_unused_stratagem_clears_at_the_investigators_next_turn() -> None:
    game = _public_investigator()
    assert game.execute(DeviseStratagem(target_id="investigator_guard_dog_a", mode=ATTACK_STRATAGEM)).status is ResultStatus.COMPLETED
    actor = game._state.creatures["forensic_investigator"]
    assert actor.investigator_stratagem is not None and not actor.investigator_stratagem.consumed

    assert game.execute(EndTurn()).status is ResultStatus.COMPLETED
    assert game.execute(EndTurn()).status is ResultStatus.COMPLETED
    assert game.execute(EndTurn()).status is ResultStatus.COMPLETED
    assert game.inspect().turn_actor_id == "forensic_investigator"
    assert game._state.creatures["forensic_investigator"].investigator_stratagem is None


def test_public_invalid_investigator_intent_is_atomic_and_unsupported_modes_reject() -> None:
    game = _public_investigator()
    skill = game.execute(
        DeviseStratagem(target_id="investigator_guard_dog_a", mode=SKILL_STRATAGEM)
    )
    assert skill.status is ResultStatus.COMPLETED
    assert game._state.creatures["forensic_investigator"].actions_remaining == 2
    assert game._state.creatures["forensic_investigator"].investigator_stratagem is not None
    invalid = game.execute(
        Strike(target_id="investigator_guard_dog_b", attack_id="shortsword", use_intelligence=True)
    )
    assert invalid.status is ResultStatus.REJECTED
    actor = game._state.creatures["forensic_investigator"]
    assert actor.actions_remaining == 2
    assert actor.investigator_stratagem is not None and not actor.investigator_stratagem.consumed
    same_round = game.execute(DeviseStratagem(target_id="investigator_guard_dog_b"))
    assert same_round.status is ResultStatus.REJECTED
    assert actor.actions_remaining == 2


def test_terminal_public_devise_save_load_and_strike_path_is_bounded(tmp_path) -> None:
    inputs = iter(
        (
            "2", "1",       # keep the deterministic initiative result
            "5", "2",       # Devise a Stratagem, Guard Dog A
            "2", "1",       # resolve the stored-die mode choice: Attack Stratagem
            "14", "",       # save the unconsumed stratagem
            "15", "",       # load it back
            "4", "1", "1", "1", "1",  # Strike, shortsword, Dog A, intent, Intelligence
            "17",            # quit from the bounded post-strike menu
        )
    )
    output = BoundedTranscript(max_lines=500, max_chars=100_000)
    bounded_input = BoundedInput(lambda: next(inputs), max_calls=40)
    status = run_terminal(
        setup=get_setup("investigator_forensic_vs_two_guard_dogs"),
        rolls=(20, 1, 2, 14, 3, 4),
        save_path=tmp_path / "investigator-terminal.json",
        input_fn=bounded_input,
        output_fn=output.append,
    )
    transcript = "\n".join(output)
    assert status == 0
    assert bounded_input.calls == 16
    assert "Devise a Stratagem" in transcript
    assert "preliminary d20 is 14" in transcript
    assert "Loaded encounter" in transcript
    assert "Attack: d20 14 + 7 = 21" in transcript
    assert "investigator_strategic_strike" in transcript
