# Swashbuckler: Tumble Through

## Active bounded outcome

The selected Braggart's panache and melee finisher are accepted. This slice adds real Tumble Through movement through occupied enemy space, an actual Acrobatics check, normal reactions, saved continuation and terminal use. It is a shared action with the applicable Braggart benefits, not a special scenario exception. Thrown Flying Blade, level-2 Assurance (Acrobatics) and full class admission remain outside this assignment.

Owner Luna/xhigh `/root/swashbuckler_first_play`, session `01a0aae4-1136-7413-9b9d-78368cd1da69`, run `swashbuckler-tumble-through-2026-09-16`. Existing handoff is the [Swashbuckler source packet](swashbuckler-runtime-work.md), accepted swash/Stride/skill/reaction/save APIs and `tests/test_swashbuckler_first_play.py`. The latest public prerequisite is the saved melee finisher/healthy terminal victory in the799-test checkpoint. No Tumble executable result is claimed yet.

## Required sequence

Verify [Tumble Through](https://2e.aonprd.com/Actions.aspx?ID=2370), [Reactive Strike](https://2e.aonprd.com/Feats.aspx?ID=5832) and [Bravado](https://2e.aonprd.com/Traits.aspx?ID=801). Reuse ordinary Stride paths, map costs and departure reactions. Implement Acrobatics versus Reflex, doubled enemy-space movement cost, the source's insufficient-movement and failed-check results, normal reactions on success/failure, and applicable Stylish Combatant/panache/Speed. Tumble does not increase MAP. Resolve actual unsupported or unclear occupancy requirements explicitly rather than approximating them.

First checkpoint: a public staged Braggart action traverses an enemy's space, resolves a real check and reaches the correct cell with the proper panache result. Then test saved check/reaction, interruption, failed movement, ordinary non-Swash use, atomic invalid requests, healthy complete play and bounded terminal. Pair with the accepted melee finisher where useful. No speculative movement framework.

Coordinate short model/encounter/persistence/terminal edits with the Investigator lead owner. Use the verified project-root `.venv/bin/python` pytest environment with explicit30-second timeout and existing bounded input/capture. Reconcile every yielded session to exit; no unbounded temporary drivers. Root schedules broad integration after coherent changes and maintains this record without inspecting implementation.

## Current evidence

Accepted after source-checked independent play and the 826-test canonical integration checkpoint. Public setup `content.get_setup("staged_braggart_swashbuckler_vs_guard_dog")`, action `Encounter.execute(TumbleThrough((Position(...), ...)))`. Runtime pointers: `skill_actions.TumbleThrough`, `_tumble_target`, `_tumble_remaining_path`, `_finish_tumble_through`; `Encounter._advance_continuation` saves prepared command/check through movement and reactions.

Existing evidence: [owner tests](../../tests/test_swashbuckler_tumble_play.py) and [independent tests](../../tests/test_tumble_play_review.py), 14 combined passing cases; 65 coherent Swash/review/catalog/Investigator-menu checks; 79 supporting terminal/persistence/movement/reaction checks; compile/diff passed. Healthy terminal victory is exercised. Sol found a missed source requirement: failure erased clear movement before enemy entry. The retained owner repaired prefix movement and departure-reaction ordering, including saved interruption, and added a regression. The adjacent Investigator terminal script was corrected for menu positions while preserving its actual Devise/save/load/Strike assertions.

Large/multi-space occupancy remains explicitly unsupported; thrown Flying Blade, level-2 Assurance and full class admission remain outside this assignment. Every owner engine invocation ended synchronously without a retained session; no scratch probes were created. One invocation naming nonexistent `tests/test_persistence.py` exited 4 before the corrected checks. Owner process enumeration was denied. Independent inventory at 13:05:43 PDT found no task-owned jobs and terminated none; later checks exited synchronously. Accounting is closed.

Final review independently proved healthy saved Tumble through dagger victory and failed entry retaining completed lead-in movement. Two review cases passed in 0.12s; 32 combined checks passed in 0.20s. Four later integration failures were shifted Angelic/Assurance/Justice terminal scripts; the same owner corrected intended menu selections without weakening behavior assertions (26 focused passes). Final full checkpoint: 826 passed, 4.344 seconds measured, 72,925,184-byte peak, compile/diff clean. Supported scope is one enemy/one-square ground traversal; Climb/Fly/Swim and multi-enemy paths are not delivered.

Run usage: 32,416,472 input / 31,832,832 cached input / 99,614 output; 210 requests, 2 compactions. Original owner retained. The shared review/audit costs are recorded once in ACTIVE and the ledger. Native collaboration was reported unexposed in this worker; final handoff fallback succeeded.
