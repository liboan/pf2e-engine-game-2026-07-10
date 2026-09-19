# Swashbuckler: first public panache attack sequence

## Delivered behavior and remaining scope

**The first bounded sequence has passed independent review and combined integration. The independent process audit and retained-owner probe repair are complete. This bounded capability is accepted; full class admission remains pending.** The selected Braggart can use ordinary Demoralize for Bravado, gain lasting or temporary panache, move with its extra Speed and make an ordinary dagger Strike with Precise Strike. Full selected coverage still requires Tumble Through, Flying Blade thrown attacks and Confident Finisher. Keep the class staged.

Owner: Luna/xhigh `/root/swashbuckler_first_play`, session `01a0aae4-1136-7413-9b9d-78368cd1da69`, run `swashbuckler-first-play-2026-09-16`. No owner change occurred during repairs. First public probe was observed at15:58:56UTC September16; actual execution time was not separately supplied. It demonstrated a failed language-penalized Demoralize, temporary panache/+5ft Speed and ordinary dagger precision. Saved and completed-fight evidence followed.

## Execution handoff

- Staged setup: `staged_braggart_swashbuckler_vs_guard_dog`; definition: `swashbuckler_braggart_level_1`. Three daggers are tracked as real items.
- Runtime: `swashbuckler.is_braggart`, `apply_bravado_result`, `precise_strike_damage_term`, `effective_speed_ft`, `clear_panache`; `Encounter.effective_speed_ft`, ordinary damage, turn-end/encounter-end and inspection paths.
- State: `CreatureState.panache` / `panache_expires_at_end`; `ActorView.panache` / `speed_ft`.
- Tests: `tests/test_swashbuckler_first_play.py`, independent `tests/test_swashbuckler_play_review.py`. Existing ordinary Demoralize is reused rather than duplicated.
- Intimidating Glare is legally granted by the selected Warrior background. Simple, martial and unarmed weapon proficiency are all trained; dagger attack+7 matches that grant.

## Actual play and independent review

Owner/review focused selection: **56 passed in0.31s**. Saved ordinary Strike and Bravado choices, healthy-start victory, actual30-foot Stride, temporary expiry, immunity, terminal inspection and terminal victory were exercised. Terminal victory uses `BoundedInput(max_calls=40)`, `BoundedTranscript`, dice20,1,8,20,2,3 and finishes the dog at0/8HP.

Sol/high independently verified ordinary+2 typed precision before panache, agile MAP−4, natural1/no damage, natural20/doubled precision, Bravado failure through the end of the next turn, lasting success, actual six-square movement, literal expiry and class-specific immunity handling. Demoralize immunity suppresses frightened but still permits the Braggart's Bravado check; a normal Fighter's immune retry rejects without changes. The reviewer found **no remaining P0/P1** after retained-owner repairs.

The same periodic review added a Forensic encounter: actual critical enemy Strike from healthy→dying2; save/load Battle Medicine Hero choice; critical-failure damage→dying3, wounded0 and one-hour medic/recipient immunity; immediate retry is atomic. The separate stable-unconscious-at-zero positive-damage limit remains unchanged.

Review files: `tests/test_swashbuckler_play_review.py` and `tests/test_forensic_healing_play_review.py`. **5 independent tests passed in0.12s;27 with adjacent owner tests in0.19s**; compile/diff0. Coordinated integration: **765 passed in3.66s**, measured pytest4.084s, peak70,270,976bytes, compile/diff0. All reported processes exited synchronously with no yielded/background sessions; an independent inventory follows.

## Repairs and sources

The retained owner repaired immune targets incorrectly receiving frightened again, corrected expert proficiency labels and missing unarmed training, and removed a dormant finisher branch outside this slice. The correct dagger+7 number did not change. These were implementation repairs, not user-rule uncertainties.

Worker-checked sources: [Swashbuckler](https://2e.aonprd.com/Classes.aspx?ID=63), [styles](https://2e.aonprd.com/Styles.aspx), [Bravado](https://2e.aonprd.com/Traits.aspx?ID=801), [Demoralize](https://2e.aonprd.com/Actions.aspx?ID=2395), [Warrior](https://2e.aonprd.com/Backgrounds.aspx?ID=445), [Flying Blade](https://2e.aonprd.com/Feats.aspx?ID=6130). Medicine review also checked [Battle Medicine](https://2e.aonprd.com/Feats.aspx?ID=5125), [Forensic Medicine](https://2e.aonprd.com/Methodologies.aspx?ID=7), [Treat Wounds](https://2e.aonprd.com/Actions.aspx?ID=2399), and [dying damage](https://2e.aonprd.com/Rules.aspx?ID=374). Root has not opened these sources or inspected implementation.

## Existing handoff

Luna's read-only scout used the [existing source packet](swashbuckler-runtime-work.md) and reported:

- `skill_actions.py`: `Demoralize`, `_demoralize`, `_finish_demoralize`, `demoralize_outcome_from_check`.
- `model.py`: `Strike`; `Encounter._start_strike`, `_roll_attack_damage`; typed `DamageTerm` handling through `damage.roll_damage_terms`. Ranger and Rogue provide existing precision patterns.
- `CreatureDefinition.land_speed_ft` exists. Swashbuckler content/module, panache state/expiry, effective Speed and finisher lockout were absent at handoff.
- Routing through `family_martial._owner_module`, Encounter family dispatch/validation, model saved-check helpers, persistence, content and terminal needs integration. Leave `investigator.py` to its owner.
- Accepted test analogues: `test_public_demoralize_applies_frightened_and_source_target_immunity`, `test_thief_repeated_sneak_attack_and_critical_doubling_on_qualifying_hits`, and `test_transferred_weapon_requires_identity_selection_and_round_trips_saved_strike`.

The scout did not rerun a probe. Its suggestion of a separate class command is not a requirement: prefer the ordinary public Demoralize action with a narrow feature hook when appropriate, avoiding duplicated general actions.

## Acceptance sequence

Use the existing source packet and verify applicable current sources. First public checkpoint is a legal staged Braggart fixture → finalized Demoralize → panache → ordinary qualifying dagger Strike with2 precision damage. Include all mandatory modifiers, speed and lifetimes that affect this path; temporary versus retained panache and failed/critical attempts must follow sources.

Then prove saved checks and state, Hero finalization, language and source-target immunity, qualifying/nonqualifying attacks, miss/critical behavior, actual bounded terminal and one healthy-start fight through victory. Full Tumble/finisher/thrown support follows later; unsupported actions must not masquerade as delivered. No catalog admission or whole-class count increase is authorized from this first sequence alone.

Exact environment: project root, `.venv/bin/python -m pytest -q <focused files>`, pytest supplies `src`. Combined checkpoint765 tests, admitted51/36, staged10/3, save17. One broad integration follows coherent shared edits; focused checks remain available outside named hazards. Use bounded loops/input/capture/time and reconcile every process/session through exit.

## Handoff accounting

Closed scout run `swashbuckler-first-execution-handoff-2026-09-16`: Luna/xhigh,8requests,0compactions, **520,428 input (436,224 cached),7,416 output**. No code/doc edits, tests or probes. Delivery usage remains open separately.

## Process audit correction and closed review accounting

The independent09:24:18PDT inventory found two running copies of `/private/tmp/swash_terminal_probe.py` (PIDs73208/74963), exact project cwd, started09:02:24/09:05:19PDT, RSS753,984/66,720KB. Both were TERM'd explicitly and confirmed absent. Parent71132 was the shared app-server; command/cwd/timing support attribution, but no execution-session UUID appeared. Other task-owned jobs were absent and shared services were preserved. The owner's earlier “no leftovers” statement was incomplete. Its delivery remains open for session reconciliation, cause/correction and bounded-probe evidence.

Closed periodic review `swashbuckler-and-medicine-play-review-2026-09-16`: **5,822,828 input (5,721,216 cached),18,456 output**,39requests,0compactions, Sol/high. No reviewer process leftovers were found. The reviewer is now assigned a separate Knowledge review.

Closed audit `knowledge-swash-completion-process-audit-2026-09-16`: **994,322 input (983,552 cached),2,209 output**,6requests,0compactions, Luna/xhigh. Dollar costs unavailable. Delivery accounting remains open through the probe repair; no new Swash behavior is part of that repair.

### Resource repair accepted

The obsolete script used unbounded `inp()` and a normal growing output list, without a wall-clock timeout. A menu mismatch could retry indefinitely. The owner removed only that task-created script and confirmed both terminated PIDs absent with `kill -0`; host `ps` was denied to the owner, so the independent auditor's inventory remains the census evidence. Two checked-in bounded encounter paths were rerun using the existing30-second `timeout` command: **2 passed in0.12s**, synchronous exit0, diff clean. No production mechanics changed and no broad rerun was necessary.

Delivery `swashbuckler-first-play-2026-09-16` is now closed: **31,893,465 input (31,244,032 cached),90,606 output**,229requests,2compactions, Luna/xhigh. No owner changes. First executable observation15:58:56UTC is recorded above; exact time to first execution, explicit wait duration and exact elapsed delivery time were not supplied. Review repairs were immune fear reapplication, proficiency labels and probe resource discipline. The owner now has a separately registered melee-finisher assignment; these closed counts must not be recomputed from its later cumulative session.
