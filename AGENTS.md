# Working rules

## Direction and ownership

- Build a local Python PF2e engine with a simple terminal interface. Keep state literal and local; do not add browser, server, network, or distributed-state machinery.
- The supervisor assigns bounded slices, tracks progress, and integrates results. It does not read repository implementation or rules-source content. Its exception is authoring `docs/plan/*.md` and `docs/work-log/*`, and reading those files it wrote.
- Give each bounded public behavior one Terra owner across the necessary runtime, persistence, terminal and tests, retaining that owner through ordinary review fixes. Do not split by layer or assign an unbounded class rewrite. Launch a dependent helper only after its required API exists and a public probe passes, unless it has clearly independent useful work without shared-file contention. Routine adjacent refactors need no registry package, package approval or separate review.
- Supply a compact execution handoff: relevant files and exact symbols, one analogous test/helper, verified interpreter/PYTHONPATH/working directory, last successful public probe (or explicitly none), current API contract and unfinished dependencies. Workers provide these pointers in their normal handoff; the supervisor relays them without inspecting implementation. Start from existing source packets rather than another general planning pass.
- Do not edit plan or work-log files unless you are the supervisor assigned to author them. Leave unrelated worktrees and branches alone.

## Current S3i scope after generalization

- Preserve the accepted fixed-build S1–S3 baseline: 21 catalogued setups, 211 passing tests at the pre-expansion integration checkpoint, and sixteen accepted interaction encounters. Do not present the new roster as implemented based on its plan, source notes, or definitions alone.
- The approved roster still covers representative builds for all 16 Player Core and Player Core 2 classes, without requiring every printed subclass or nested option. Preserve the selected roster and supported boundaries in `STATUS.md`, including the eleven accepted Barbarian builds; unselected source inventories remain reference, not delivery backlog. Keep the small shared domain menu, limited caster spell/school lists, finite Alchemy items, and one or two nested subclass examples.
- The authorized generalization and simplification phase is complete. Its accepted coherent groups share spell-save provenance across ten paths, finite preparation routing and validation across Wizard, Druid, Witch, and fixed preparations, and existing finite `BombFacts` adoption for two admitted bombs; the relevant defects were repaired and independently reviewed. The phase applied only to demonstrated repeated mechanics, correctness risk, and likely reuse, with real caller adoption and deletion of replaced paths. Current verified coverage, validation, and ownership remain in [the active recovery table](docs/work-log/ACTIVE.md) rather than being copied here.
- Recipient progression is deferred: the current common save handling covers the major risk, while remaining eligibility, completion, and rider behavior differs and a generic iterator would mostly relocate branches. Revisit it only when a new actual adopter or demonstrated drift supplies evidence. Paired-policy and turn-walk work remain optional; poison, minion, and universal rules frameworks are outside scope, as are unrelated content expansion and wholesale rewrites.
- Explicitly granted and clearly labeled above-level fundamental-rune test equipment is permitted. It does not raise character level or make the equipment an ordinary starting purchase.
- Ranger acceptance is combat-only: exploration, foraging, Seek, and Track grants remain recorded sheet facts and do not gate the selected combat build's admission.
- Keep the remaining stable-unconscious-at-zero positive-damage boundary explicit until separately ruled on. The user approved the documented Counter Performance natural-die and fortune/Hero conventions and horizontal-only Monk admission; vertical terrain and High Jump remain unsupported until the engine has verticality. The active scope and recovery state are in [the class and content expansion plan](docs/plan/06-class-and-content-expansion.md) and [ACTIVE](docs/work-log/ACTIVE.md).

## Model choice

- Use `gpt-5.6-terra` with `high` reasoning for one coherent implementation group, retaining one owner across runtime, save/load, terminal, and tests. Verify native desktop adoption before dispatch; if unavailable, stop and report the blocker rather than silently falling back.
- Use `gpt-5.6-sol` with `high` reasoning to review each complete, runnable group against the actual Python engine and applicable rules sources.
- Use `gpt-6-astra` with `high` reasoning for substantial unresolved design or rules questions. The completed generalization coordinator was `task01a0b6ce-40ce-7f51-8042-b9f2b8956421`, and its `pf2e-generalization-execution` heartbeat is paused at closure. The earlier content-expansion coordinator `task01a0a4ea-653e-7fe0-b902-044bc77b041f` and `pf2e-content-expansion-execution` automation remain paused and must not be resumed.
- When setting model overrides for subagents, use `fork_turns: "none"` or a positive number; do not use `"all"`.

## Correctness and evidence

- Implement applicable supported PF2e rules accurately. Defer costly bespoke content when it is not needed for the current playable slice. Cite the rules sources used. Do not silently approximate unsupported behavior; state the limit and stop where it affects play.
- Keep rules behavior in the engine, not in a growing set of one-off scenario exceptions.
- Use source-informed ordinary tests, then verify continuous local encounters, save/load, and performance as each capability becomes available. Do not claim evidence for a path that was not exercised.
- Keep durable run records in `docs/work-log/agent-runs.json`. The deterministic usage collector records identified runs from raw metadata, deduplicates per-request `token_usage_record` entries, includes compaction requests, and excludes inherited parent records. Preserve observed model/effort and exact run boundaries; cached input is a subset of input. If a value is unavailable, record `null` with the reason, and distinguish per-run counts from cumulative reused-worker totals.

## Test and process cadence

- During implementation, run the smallest relevant test selection for the changed rule, content family, or encounter. Keep cheap focused checks frequent; run complete scripted encounters after a coherent group of changes, and run the full suite plus broader end-to-end play at integration checkpoints and handoff.
- Keep checks bounded: one synchronous pytest process per worker, no `xdist`, watch loops or background launches. Permit focused tests when their required code is stable; reserve execution holds for a named shared-change hazard or broad integration run, not a global test-slot lock. Keep one broad integration active. Retain meaningful assertions and bounded output; timeout/capture failure names the case and last useful state.
- Reuse or minimally consolidate one checked-in integration command for pytest, elapsed time/peak memory and routine checks. Verify paths/environment once and reuse the exact invocation. Use a file-backed probe when nested shell/Python quoting becomes fragile; do not repeatedly author wrappers or create a test framework.
- At integration checkpoints, when agents go idle or complete, and before handoff, audit their reported test and probe processes. Stop only confirmed unused task-owned descendants; verify process identity (PID, start time, command, and working directory when needed), request graceful exit, and confirm exit. Never kill by process name or stop a shared service with unclear ownership.

## Reporting and recovery

- Worker reports are event-driven: a decision blocker, shared-contract change, first executable checkpoint or final evidence. The roughly five-minute checkpoint is a non-disruptive progress diagnosis; a localized failing executable check is useful. It does not complete or reassign the task. Split only for demonstrated scope/dependency trouble or repeated lack of progress. A final handoff is usually 250–400 words with execution pointers, commands/results, evidence, limits and next action.
- Use internal collaboration and final reports for worker coordination. Do not use cross-task app messages as a reporting channel. Avoid acknowledgement-only traffic and repeated status polling.
- Keep focused internal checkpoints frequent. Send ordinary repair work directly through `followup_task` to the same owner and reviewer, retaining the existing accounting; only a demonstrated boundary change or failure to progress justifies reassignment. The supervisor ends its turn when only autonomous work remains.
- Keep `docs/work-log/ACTIVE.md` as the single compact recovery entry point. Its table records task/session, owner/model, owned files, dependencies or blockers, last executable checkpoint, and next action. README and STATUS point to that page for current counts and ownership; they do not duplicate the active queue.
- Use one deterministic usage CLI for dispatch, completion, genuinely new reused-worker assignments and milestone summaries. Register fresh identity and accurate boundaries; keep checkpoints, waits and ordinary review fixes inside the same assignment, closing accounting at acceptance or actual reassignment. Print concise totals without inventing flags or another bookkeeping layer. For the next two completed playable slices, use existing logs to report owner changes, time to first executable check, explicit dependency waits, review repairs and elapsed delivery time alongside accepted behavior and total agent cost/usage; unavailable values remain labeled unavailable.
- Reporting and accounting changes do not change model routing or lower the acceptance bar: source-checked rules, focused and core tests, actual play, save/load, performance, and attributable process cleanup remain required evidence.

## Decisions and stopping

- Treat a P0 blocker as a stop condition and ask for clarification with the available structured question tool. Resolve P1 questions before making materially dependent decisions. Use judgment for routine, reversible choices.
- Stop and report the smallest decision needed when a source is unclear, a rule would have to be guessed, a check fails, or the slice would exceed its agreed scope. Keep the result and evidence reviewable before escalating.
