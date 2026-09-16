# Forensic Investigator: Battle Medicine

## Current state

**Accepted staged capability.** Battle Medicine now has actual healthy-start encounter, save/load, terminal and cross-scene cooldown evidence. The full Investigator remains staged. This slice adds its required in-combat healing with actual rolls, injury, toolkit/hand requirements and repeat-use limits. Forensic examination will use the next shared knowledge procedure; it is not included in this healing claim.

Luna/xhigh `/root/investigator_first_play` retained the bounded public behavior across runtime, persistence, terminal and tests through the added encounter proof. Run `investigator-forensic-healing-2026-09-16` is now closed. The prior first-sequence run was closed before this assignment was registered and dispatched. The supervisor writes this record from worker reports and compact task status, without implementation or rules reads.

## Inputs and acceptance sequence

Use the existing [Investigator source packet](investigator-runtime-work.md). The accepted public prerequisite is staged setup `investigator_forensic_vs_two_guard_dogs`: saved Devise d20 14 produces attack21, damage7 and targetHP1. Current accepted integration is 723 tests, save17.

1. Source-check Battle Medicine and the selected Forensic healing/cooldown modifications.
2. Produce the smallest actual public healing check with deterministic dice and meaningful save/load.
3. Cover success, failure and critical outcomes; per-medic/recipient timing; relevant toolkit, hand and reaction requirements; and invalid calls that preserve state and dice.
4. Exercise the actual bounded terminal and an encounter with genuine injury. Use existing input/transcript limits and finite turn loops.
5. Run focused checks first. Perform one broad integration after a coherent acceptance group, recording elapsed time, memory and process exits.

Reported execution pointers from earlier handoffs: `FamilyProcedureContext.prepare_skill_check`, saved-check resolve/reroll/choice helpers, `health.py` healing, persisted `condition_immunities`; analogous tests in `tests/test_skill_actions.py` and `tests/test_justice_play_review.py`. The owner must confirm exact current suitability instead of forcing an unsuitable abstraction.

## Earlier checkpoints and acceptance repair

The compact task snapshot records assignment start **2026-09-16 15:01:53 UTC**. A later worker progress report gives the first executable checkpoint: an authored three-actor encounter exposes `battle_medicine_targets=("healing_ally",)`, pauses on the Medicine check, saves/loads the typed Hero Point choice, then resolves d20 12+Medicine4=16. Healing dice3,4 plus Forensic level1 restore **8HP**. The one-hour immunity persists with expiry3600, and wounded is unchanged. This proves the first path, not the entire slice. The exact initial execution timestamp was not supplied; do not infer it from the time the supervisor recovered this local commentary.

The worker's initial progress was visible only in its local commentary, so the supervisor recovered a compact task status and reminded the owner to deliver substantive checkpoints through internal collaboration. Ownership and implementation continued unchanged. No source/code/output inspection was used for recovery.

Later owner checkpoint: **8/8 focused tests pass**, including a saved critical Reactive Strike interrupting Battle Medicine. The reaction deals10 damage, leaving the Investigator at7HP and two actions; no Medicine check, healing or immunity follows. The owner reports a narrow save-validation addition for a `family_action` continuation at `battle_medicine_check`, with a successful saved round trip. Earlier toolkit and fleeing-action corrections are included in this focused checkpoint. Full integration and terminal evidence are still pending.

The supervisor also requested a direct check that the medic/recipient cooldown survives the existing `game.next_encounter(next_setup)` path and its shared world-time clock. A scene change must not silently reset the one-hour limit. The existing unsupported stable-unconscious-zero positive-damage boundary remains explicit if a critical healing failure reaches it; no new dying-rule convention was authorized.

An earlier canonical checkpoint had **734 tests**, **3.413s**, peak **69,042,176 bytes (65.844MiB)**, compile/diff0, catalog51/36 accepted and9/2 staged, save17. Its integration process exited0 with no live session. That checkpoint lacked explicit complete-encounter evidence and is superseded by the accepted result below.

### Owner handoff and remaining encounter proof

The final owner handoff supplies `BattleMedicine` in `src/pf2e/investigator.py`, staged setup `investigator_forensic_healing_vs_ally`, target projection in `model.py`, and terminal/save/Encounter wiring. `tests/test_investigator_healing.py` covers critical success, failure, critical-failure damage, target-specific cooldowns, toolkit hand legality, the saved manipulate interruption, atomic invalid DC20 and bounded terminal execution. Its explicit `next_encounter` plus save/load case keeps expiry3600 in the new scene. The owner reports **69 focused passes in0.32s** and integration session10578 followed to exit0.

The handoff's HP10→18/Wounded1 example established a focused healing fixture but did not explicitly prove a healthy-start encounter with enemy injury, healing and victory. The same owner added that bounded test within the original assignment. No owner change or new production repair was required for this evidence gap.

Owner-checked sources: [Forensic Medicine](https://2e.aonprd.com/Methodologies.aspx?ID=7), [Battle Medicine](https://2e.aonprd.com/Feats.aspx?ID=5125), [Treat Wounds](https://2e.aonprd.com/Actions.aspx?ID=2399), [Healer's Toolkit](https://2e.aonprd.com/Equipment.aspx?ID=2727).

Independent process audit at **08:34:07PDT September16** found no Python/pytest, temporary game/terminal probes, Playwright, Chrome/Chromium or project-specific processes. No active cross-scene check was visible. Zero terminations; shared app MCP/Node remained untouched. Closed audit run: Luna/xhigh,2requests,0compactions, **314,411 input (310,784 cached),493 output**. This is a point-in-time inventory, not evidence that every future command has exited.

## Accepted final result

`tests/test_investigator_healing.py` now includes a continuous public encounter from the production staged setup `investigator_forensic_healing_vs_ally`:

1. Ally starts healthy at21/21HP. Guard Dog uses public Stride and Jaws; d20=12 and d4=4 reduce the ally to16HP.
2. Investigator starts Battle Medicine, saves the pending choice, loads and keeps Medicine12+4=16. Healing3+4+Forensic1 restores the ally to21HP.
3. Investigator and ally use public Stride, Strike and EndTurn to defeat the dog. The actual winner is team blue.

The same file retains `test_forensic_immunity_survives_next_encounter_and_save_load` and `test_terminal_routes_battle_medicine_and_quits_with_bounded_input`. Final selection: **11 passed in0.11s**. Canonical integration: **735 passed in3.07s**, measured `pytest_seconds=3.341`, peak **69,402,624 bytes (66.188MiB)**, compile/diff0, synchronous exit0 with no yielded session. Catalog51/36 admitted,9/2 staged, save17. This includes the new Champion/Sorcerer party encounter.

Critical-failure damage uses the shared health API; positive damage to an already stable unconscious PC at0HP still raises its explicit unsupported-rule result. No new death/dying convention was added. Examination, knowledge, leads and other missing Investigator grants remain outstanding.

Final independent inventory at **08:41:08PDT September16** found no Forensic Python/pytest, temporary probes, Playwright, Chrome/Chromium or project-specific process. New Node entries were shared app MCP services and were preserved. Zero terminations. The source-only Swashbuckler handoff was also left untouched.

## Closed usage and next work

The deterministic collector reports per-assignment usage; cached input is included in input, and dollar cost is unavailable.

| Assignment | Input | Cached input | Output | Requests / compactions |
|---|---:|---:|---:|---:|
| Luna/xhigh healing and ordinary acceptance repair | 28,476,506 | 27,831,552 | 104,757 | 187 / 3 |
| Earlier checkpoint process audit | 314,411 | 310,784 | 493 | 2 / 0 |
| Final post-encounter exit check | 319,529 | 315,904 | 448 | 2 / 0 |

No implementation owner change occurred. Exact time to first executable check and elapsed delivery time are unavailable; assignment start is recorded above, but local commentary delivery did not provide exact checkpoint timestamps. Next, a fresh bounded owner implements the ready [knowledge contract](investigator-knowledge-work.md). This is a new public behavior after accepted healing, not reassignment of unfinished repairs.
