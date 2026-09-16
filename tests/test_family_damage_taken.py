"""Internal shared-family damage packet probes for temp HP / massive damage ordering.

The damage amount is a labelled direct family-context packet rather than a
playable creature attack: supported level-1 attacks in the current catalog do
not reach the twice-max-HP threshold after Shield Block.
"""

from copy import deepcopy

from pf2e import Encounter, FamilyProcedureContext, Rage
from pf2e.content import get_definition, get_setup
from pf2e.damage import DamageComponent, DamageGroup, DamageResult
from pf2e.model import DamageResolution
from pf2e.persistence import DiceSource


def test_raging_family_context_massive_damage_uses_pre_temp_amount() -> None:
    game = Encounter.start(get_setup("barbarian_rage_test"), rolls=(20, 1))
    while (choice := game.inspect().choice) is not None:
        if choice.kind == "initiative_hero_reroll":
            game.choose(choice.choice_id, "keep")
        else:
            assert choice.kind == "family_action"
            game.choose(choice.choice_id, "decline")
    assert game.inspect().turn_actor_id == "barbarian_test"
    game.execute(Rage())
    assert next(
        actor for actor in game.inspect().actors if actor.actor_id == "barbarian_test"
    ).temporary_hp == 4

    # 46 reaches the massive-damage threshold for this 23 HP PC. Rage temp HP
    # absorbs 4, leaving 42 for ordinary HP subtraction, below that threshold.
    state = deepcopy(game._state)
    actor = state.creatures["barbarian_test"]
    family_context = FamilyProcedureContext(
        game,
        state,
        DiceSource(seed=1),
        actor,
        get_definition(actor.definition_id),
        "martial",
    )
    amount = 46
    component = DamageComponent("direct family test packet", "slashing", 0, (), 0, amount)
    damage = DamageResult((component,), rolled_total=amount, multiplier=1, total=amount)
    resolution = DamageResolution(
        source_kind="family",
        group=DamageGroup("massive-family-probe", (damage,), "family"),
        actor_id="barbarian_guard",
        target_id="barbarian_test",
        source="direct family-context packet",
        damage_type="slashing",
    )

    events = family_context.encounter._resolve_damage_to_health(
        family_context.state,
        family_context.dice,
        resolution,
        resumed=False,
    )

    dead_barbarian = family_context.state.creatures["barbarian_test"]
    assert dead_barbarian.dead
    assert dead_barbarian.hp == 0
    assert dead_barbarian.temporary_hp == 0
    assert dead_barbarian.hero_points == 1
    assert family_context.state.pending_choice is None
    assert any(event.kind == "defeated" for event in events)
