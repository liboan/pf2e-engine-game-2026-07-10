"""Public level-two play for the finite Justice, Warpriest, and Life Oracle group.

Sources:
* Champion / Divine Grace: https://2e.aonprd.com/Classes.aspx?ID=58 and
  https://2e.aonprd.com/Feats.aspx?ID=5892
* Cleric / Healing Hands: https://2e.aonprd.com/Classes.aspx?ID=33 and
  https://2e.aonprd.com/Feats.aspx?ID=4646
* Oracle / Reach Spell: https://2e.aonprd.com/Classes.aspx?ID=61 and
  https://2e.aonprd.com/Feats.aspx?ID=4577
* Protection: https://2e.aonprd.com/Spells.aspx?ID=1641
"""

from __future__ import annotations

from pathlib import Path

from pf2e.content import get_definition, get_setup
from pf2e.encounter import Encounter
from pf2e.model import Cast, EndTurn, ReachSpell, ResultStatus, Strike
from pf2e.terminal import run_terminal
from terminal_test_helpers import BoundedInput, BoundedTranscript


def _settle(game: Encounter) -> None:
    for _ in range(12):
        choice = game.inspect().choice
        if choice is None:
            return
        option = "keep" if any(item.option_id == "keep" for item in choice.options) else choice.options[0].option_id
        assert game.choose(choice.choice_id, option, choice.owner_actor_id).status in {
            ResultStatus.COMPLETED, ResultStatus.PAUSED,
        }
    raise AssertionError("initiative did not settle")


def _actor(game: Encounter, actor_id: str):
    return next(actor for actor in game.inspect().actors if actor.actor_id == actor_id)


def _to_turn(game: Encounter, actor_id: str) -> None:
    for _ in range(len(game._state.initiative_order) + 1):
        if game.inspect().turn_actor_id == actor_id:
            return
        assert game.execute(EndTurn()).status is ResultStatus.COMPLETED
        _settle(game)
    raise AssertionError(f"did not reach {actor_id}")


def _choose(game: Encounter, option_id: str):
    choice = game.inspect().choice
    assert choice is not None
    return game.choose(choice.choice_id, option_id, choice.owner_actor_id)


def test_l2_divine_sheets_keep_finite_legal_progression() -> None:
    champion = get_definition("justice_champion_iomedae_level_2_divine_grace")
    cleric = get_definition("warpriest_c_iomedae_level_2_healing_hands")
    oracle = get_definition("life_oracle_level_2_reach_spell")

    assert (champion.level, champion.hp, champion.ac, champion.spell_dc) == (2, 32, 19, 16)
    assert {"divine_grace", "justice_retributive_strike", "lay_on_hands"} <= set(champion.abilities)
    assert {"Divine Grace", "Quick Jump"} <= set(champion.feats)
    assert (cleric.level, cleric.hp, cleric.ac, cleric.spell_dc) == (2, 26, 19, 18)
    assert "healing_hands" in cleric.abilities and {"Healing Hands", "Quick Jump"} <= set(cleric.feats)
    assert len([slot for slot in cleric.prepared_spells if slot.source == "ordinary" and slot.spell_id == "heal"]) == 3
    assert len([slot for slot in cleric.prepared_spells if slot.source == "font" and slot.spell_id == "heal"]) == 4
    assert (oracle.level, oracle.hp, oracle.ac, oracle.spell_dc) == (2, 28, 16, 18)
    assert "reach_spell" in oracle.abilities and {"Reach Spell", "Quick Jump"} <= set(oracle.feats)
    assert [(slot.rank, slot.capacity) for slot in oracle.spontaneous_slots] == [(1, 4)]
    assert {spell.spell_id for spell in oracle.spontaneous_spells if not spell.cantrip} == {
        "heal", "fear", "runic_weapon", "soothe", "protection",
    }

    assert get_setup("l2_divine_party_protection_healing").setup_id == "l2_divine_party_protection_healing"
    assert get_setup("l2_life_oracle_reach_spell").setup_id == "l2_life_oracle_reach_spell"


def test_l2_party_protects_then_heals_with_d10_and_scaled_life_curse(tmp_path: Path) -> None:
    # Four initiatives, a critical dog bite and retaliation, then a d10 Heal.
    game = Encounter.start(
        get_setup("l2_divine_party_protection_healing"),
        rolls=(20, 15, 10, 5, 20, 1, 10, 1, 10, 10),
    )
    _settle(game)
    _to_turn(game, "dog")
    offered = game.execute(Strike("cleric", attack_id="jaws"))
    assert offered.status is ResultStatus.PAUSED
    assert offered.inspection.choice is not None and offered.inspection.choice.kind == "reaction"

    saved = tmp_path / "l2-divine-protection.json"
    game.save(saved)
    game = Encounter.load(saved)
    protected = _choose(game, "accept")
    events = protected.events
    if protected.inspection.choice is not None:
        retaliation = _choose(game, "keep")
        events = (*events, *retaliation.events)
    injury = next(event for event in events if event.kind == "damage")
    assert injury.original_damage is not None and injury.damage is not None
    assert injury.original_damage.total - injury.damage.total == 4
    assert any(event.kind == "retributive_strike" for event in events)

    _to_turn(game, "cleric")
    game._state.creatures["cleric"].hp = 1
    healing_offer = game.execute(Cast("heal", "cleric", actions=2, slot_id="ordinary_heal_1"))
    assert healing_offer.status is ResultStatus.PAUSED
    healed = _choose(game, "willing")
    event = next(item for item in healed.events if item.kind == "healing")
    assert "1d10 10 + 8" in event.text
    assert _actor(game, "cleric").hp == 19

    _to_turn(game, "oracle")
    game._state.creatures["oracle"].hp = 1
    game._state.creatures["oracle"].oracle_cursebound = 1
    nudge = game.nudge_the_scales("oracle", "oracle")
    assert nudge.status is ResultStatus.COMPLETED
    assert "for 4 healing" in nudge.events[0].text  # L2 base 6 minus recipient CB1 × 2.
    assert _actor(game, "oracle").hp == 5
    assert game._state.creatures["oracle"].oracle_cursebound == 2


def test_divine_grace_is_a_saved_pre_roll_spell_reaction(tmp_path: Path) -> None:
    game = Encounter.start(get_setup("l2_divine_grace_review"), rolls=(20, 5, 1))
    _settle(game)
    assert game.inspect().turn_actor_id == "oracle"
    assert game.execute(ReachSpell()).status is ResultStatus.COMPLETED
    offered = game.execute(Cast("fear", "champion", actions=2))
    assert offered.status is ResultStatus.PAUSED
    assert offered.inspection.choice is not None and offered.inspection.choice.kind == "divine_grace"

    path = tmp_path / "l2-divine-grace.json"
    game.save(path)
    game = Encounter.load(path)
    result = _choose(game, "use")
    assert result.status is ResultStatus.PAUSED
    assert any(event.kind == "divine_grace_used" for event in result.events)
    save = result.inspection.choice
    assert save is not None and save.kind == "spell_save_hero_reroll"
    check = save.options and game._state.pending_choice.check
    assert check is not None
    assert any(modifier.source == "Divine Grace" and modifier.amount == 2 for modifier in check.modifier_breakdown)
    assert _choose(game, "keep").status is ResultStatus.COMPLETED


def test_divine_grace_decline_keeps_reaction_and_does_not_add_bonus() -> None:
    game = Encounter.start(get_setup("l2_divine_grace_review"), rolls=(20, 5, 1))
    _settle(game)
    assert game.execute(ReachSpell()).status is ResultStatus.COMPLETED
    assert game.execute(Cast("fear", "champion", actions=2)).status is ResultStatus.PAUSED
    declined = _choose(game, "decline")
    assert any(event.kind == "divine_grace_declined" for event in declined.events)
    assert game._state.creatures["champion"].reaction_available
    pending = game.inspect().choice
    assert pending is not None and pending.kind == "spell_save_hero_reroll"
    check = game._state.pending_choice.check
    assert check is not None
    assert not any(modifier.source == "Divine Grace" for modifier in check.modifier_breakdown)


def test_terminal_opens_the_public_l2_divine_party_sheet() -> None:
    transcript = BoundedTranscript()
    menu = {"text": "", "prompt": ""}

    def output(line: str) -> None:
        transcript.append(line)
        if line.startswith("1. "):
            menu["text"] = line
        if line.endswith(":"):
            menu["prompt"] = line

    def menu_number(label: str) -> str:
        for row in menu["text"].splitlines():
            if ". " in row and row.split(". ", 1)[1] == label:
                return row.split(". ", 1)[0]
        raise AssertionError(f"missing terminal menu item {label!r}: {menu['text']!r}")

    def script() -> str:
        if menu["prompt"] == "Choice prompt action:":
            return menu_number("Resolve this choice")
        if menu["prompt"] == "Choice option number:":
            return menu_number("Keep initiative")
        if menu["prompt"] == "Choice:":
            return menu_number("Quit")
        raise AssertionError(f"unexpected terminal prompt: {menu['prompt']!r}")

    assert run_terminal(
        setup=get_setup("l2_divine_party_protection_healing"),
        rolls=(20, 15, 10, 5),
        input_fn=BoundedInput(script, max_calls=10),
        output_fn=output,
    ) == 0
    rendered = "\n".join(transcript)
    assert "Level 2 Justice Champion" in rendered
    assert "Level 2 Iomedaean Warpriest" in rendered
    assert "Level 2 Life Oracle" in rendered
    assert "Goodbye." in rendered


def test_l2_oracle_reach_spell_projects_the_existing_saved_cast_range() -> None:
    game = Encounter.start(get_setup("l2_divine_grace_review"), rolls=(20, 5, 1))
    _settle(game)
    assert game.execute(ReachSpell()).status is ResultStatus.COMPLETED
    cast = game.execute(Cast("fear", "champion", actions=2))
    assert cast.status is ResultStatus.PAUSED
    assert cast.inspection.choice is not None and cast.inspection.choice.kind == "divine_grace"
    assert game._state.pending_choice.continuation is not None
    assert game._state.pending_choice.continuation.reach_spell_effective_range_ft == 60
