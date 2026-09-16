# Swashbuckler: Tumble Through

## Active bounded outcome

The selected Braggart's panache and melee finisher are accepted. This slice adds real Tumble Through movement through occupied enemy space, an actual Acrobatics check, normal reactions, saved continuation and terminal use. It is a shared action with the applicable Braggart benefits, not a special scenario exception. Thrown Flying Blade, level-2 Assurance (Acrobatics) and full class admission remain outside this assignment.

Owner Luna/xhigh `/root/swashbuckler_first_play`, session `01a0aae4-1136-7413-9b9d-78368cd1da69`, run `swashbuckler-tumble-through-2026-09-16`. Existing handoff is the [Swashbuckler source packet](swashbuckler-runtime-work.md), accepted swash/Stride/skill/reaction/save APIs and `tests/test_swashbuckler_first_play.py`. The latest public prerequisite is the saved melee finisher/healthy terminal victory in the799-test checkpoint. No Tumble executable result is claimed yet.

## Required sequence

Verify [Tumble Through](https://2e.aonprd.com/Actions.aspx?ID=2370), [Reactive Strike](https://2e.aonprd.com/Feats.aspx?ID=5832) and [Bravado](https://2e.aonprd.com/Traits.aspx?ID=801). Reuse ordinary Stride paths, map costs and departure reactions. Implement Acrobatics versus Reflex, doubled enemy-space movement cost, the source's insufficient-movement and failed-check results, normal reactions on success/failure, and applicable Stylish Combatant/panache/Speed. Tumble does not increase MAP. Resolve actual unsupported or unclear occupancy requirements explicitly rather than approximating them.

First checkpoint: a public staged Braggart action traverses an enemy's space, resolves a real check and reaches the correct cell with the proper panache result. Then test saved check/reaction, interruption, failed movement, ordinary non-Swash use, atomic invalid requests, healthy complete play and bounded terminal. Pair with the accepted melee finisher where useful. No speculative movement framework.

Coordinate short model/encounter/persistence/terminal edits with the Investigator lead owner. Use the verified project-root `.venv/bin/python` pytest environment with explicit30-second timeout and existing bounded input/capture. Reconcile every yielded session to exit; no unbounded temporary drivers. Root schedules broad integration after coherent changes and maintains this record without inspecting implementation.

## User stop checkpoint

Paused before implementation began. Owner confirms no new Tumble runtime changes or tests. Prior panache/finisher remains accepted; last focused31passes in0.18s under the30-second timeout, with799-test integration accepted afterward. No known live worker process or session remains. Resume with the actual traversal/check/save path described above, retaining the existing assignment boundary and owner.
