# Delivery, checks, and work records

## Operating model

The supervisor owns the plan, assignments, integration decisions, and durable work log. It synthesizes subagent findings without reading repository implementation or rules sources directly. Its exception is authoring and maintaining the plan and work log. Readers and implementers inspect the content needed for their bounded tasks.

| Work | Model and reasoning | Use |
|---|---|---|
| Straightforward scoped implementation, focused tests, small debugging, documentation integration | `gpt-5.6-luna`, `xhigh` | Default worker for clear tasks. |
| Open-ended targeted play, broader debugging, implementation critique | `gpt-5.6-sol`, `high` | Periodic review, substantially less frequent than ordinary implementation tasks. |
| High-level design, investigations, extensive rules-behavior critique | `gpt-6-astra`, `high` | Resolve genuinely open problems and define tractable scopes. |

Name one bounded player-visible outcome for each assignment. Give one Luna owner responsibility across the necessary runtime, persistence, terminal and test files, and retain that owner through ordinary fixes and independent review. Do not automatically divide layers among workers. Launch a dependent helper only after its required API exists and a public probe passes; earlier help needs clearly independent useful work without shared-file contention. Separate filenames alone do not establish independence. This is continuity of responsibility, not an unbounded class rewrite.

Worker reports remain event-driven: a decision blocker, shared-contract change, first executable checkpoint or final evidence. The first five-minute report diagnoses progress: a concrete failing test, localized cause or passing partial path is useful. It does not end the assignment. An app progress snapshot can omit actual child activity; missing messages/tool markers do not establish a startup failure or lack of progress. Obtain a direct worker checkpoint before interrupting or changing ownership, and retain the worker when it is making progress. Split or reassign only for demonstrated scope expansion, unresolved dependency or repeated lack of progress, not elapsed time alone. Preserve productive workers and completed research when changing procedure. A final handoff is usually 250–400 words with commands/results/evidence; avoid acknowledgements and repeated status. Use absolute edit paths and permit routine adjacent refactoring within scope.

Use internal collaboration messages for worker reports. Do not use the app’s cross-task message tool as a reporting fallback: it creates user-visible messages in this conversation. If a worker lacks internal messaging, it returns a bounded final handoff; the supervisor relays dependencies and gives the user one consolidated update.

Use explicit model/effort overrides with no history fork or a bounded history fork. A full-history fork does not support those overrides. Verify actual configuration from usage metadata when available.

## Assignment and review cadence

Before dispatch, use the existing source packet to specify one complete public acceptance sequence, prerequisites, relevant rejection/interruption cases and explicit exclusions. Give its implementation to one Luna owner. Packet sequences are implementation milestones, not mandatory handoffs. Root integrates findings and keeps current state readable. Prioritize closing the active playable outcomes in ACTIVE; pause future-class research unless it resolves a current blocker or supplies a specifically needed next assignment. Retain existing packets for later use.

Relay a compact execution handoff from the outgoing owner: relevant files/exact symbols, one analogous test/helper, verified interpreter/PYTHONPATH/working-directory command, last successful public probe (or explicitly none), current API and unfinished dependencies. The supervisor does not inspect implementation to reconstruct these. Workers may inspect further, starting from those pointers rather than broad repeated file dumps. Use absolute paths. Prefer a focused checked-in test for an interactive probe; a finite file-backed calculation probe is appropriate when nested shell/Python quoting becomes fragile.

Use Sol at the agreed runnable acceptance boundary or after a meaningful group, with earlier consultation for a concrete uncertainty that would cause substantial rework. It executes the actual Python engine, tries relevant alternatives, inspects state and checks sources. Return ordinary review repairs to the same implementation owner. Do not commission a separate review for every small change; preserve complete play, saved continuation, broad integration and performance gates.

Use Astra for unresolved cross-cutting design or substantial rules uncertainty. Routine implementation questions remain with the worker. Reviews can challenge the plan; the supervisor resolves changes in the owning document rather than appending competing instructions.

The active class expansion accepts representative builds across all sixteen classes at level 1 before extending to level 2. Exhausting subclasses, domains or nested item/spell menus is not an acceptance criterion. Preserve accepted variants and check all grants of each selected option; staged helpers and source inventories are not playable coverage. After both levels work, commission an Astra review of demonstrated duplication and worthwhile simplification; this is not a prerequisite architecture rewrite.

S1–S3 now have actual runtime, saved-choice, complete-play, and performance evidence. Every later milestone must also execute the actual engine; plan-consistency checks never substitute for game, persistence, or performance evidence.

## Modular tests and integration cadence

A validation hold must name the specific reviewer or test group it applies to. The implementation owner continues focused checks throughout its authorized slice. Do not leave shared code accumulating untested changes because an independent reviewer is waiting for a stable handoff. If integration becomes open-ended, freeze a reviewable checkpoint and transfer it to a bounded Sol debugging pass.

Organize tests around the changed rule or encounter family. A worker runs the smallest relevant selection after an edit: a rule file, one named encounter, or that encounter's milestone checks. Run the entire suite at a meaningful integration/handoff checkpoint, including after related shared-core corrections affecting several families are ready. One passing broad run satisfies that checkpoint; repeat it only when new edits, failures, or unresolved concerns justify it. Independent full play follows a meaningful group of changes rather than every definition or test edit.

Each worker uses one bounded synchronous pytest process at a time, with no parallel test workers, watch loop or background launch. Permit focused checks whenever their required code is stable. Reserve holds for a named shared-change hazard or the single broad integration run, not a global test-slot lock; finish unstable prerequisites before dependent execution. A hold neither splits the assignment nor withholds unrelated safe focused feedback. Keep ordinary pytest files and small helpers. Each encounter names its setup, interaction, observations, deterministic dice/seed and completion condition. Helpers use public commands/choices/save-load; they do not recalculate rules, patch hidden state, silently avoid unsupported behavior or retain every snapshot.

Bound command count, rounds, supplied dice, input, captured output, and any subprocess runtime. These limits apply equally to temporary probes and terminal experiments outside pytest. Use the existing bounded terminal capture/input helpers in checked-in tests for interactive exploration. Do not create temporary terminal drivers with custom unbounded input functions or growing output lists. Every engine test/probe launch needs an explicit wall-clock bound as well as finite input/output; the established focused invocation can use `/opt/homebrew/bin/timeout 30s .venv/bin/python -m pytest -q ...`. The canonical integration command retains its own bounded runner. Do not repeatedly invent wrappers. A limit failure reports the encounter and last relevant state and then releases its resources. Keep only a short diagnostic tail where complete output is unnecessary; required assertions must observe the actual results before they are discarded. Existing bounded terminal captures continue to fail before retaining excess output.

Use a cheap focused tier for iteration and a complete-encounter tier for broader integration. Do not add combinatorial scenario generators or a separate testing framework. Reuse deterministic sequences and a small set of alternate seeds when they answer a real rules question. Save/load checks stay inside a continuing encounter; they do not reset progress to manufacture success.

## Correctness evidence

- Source-linked expected examples precede implementation of a new rules behavior. Include meaningful boundaries and adverse interactions, rather than tests that repeat the implementation.
- Focused unit tests check shared calculations and state transitions.
- Each encounter names the interaction it demonstrates. Merely placing relevant content on the map is not evidence that its rules were exercised.
- Each runnable slice includes complete encounters through the public Python interface and representative terminal interaction checks. Try legal alternatives, decline choices, invalid input, critical outcomes, and defeat where relevant.
- Save/load must preserve the continuation at each new kind of meaningful pause. Check that costs and rolls do not repeat and stale prompt answers are rejected.
- Rejected requests preserve state and random state. Read-only inspection does not change either.
- Seeded encounters and supplied-roll cases reproduce their outcomes. Do not patch state or restart from checkpoints and count the result as uninterrupted progress.
- New parameters using established behavior can reuse existing checks. Add independent counterexamples, properties, or mutations when they address a specific risk; no secret-test infrastructure is required.

The terminal contains no rules calculations. Test its input handling and useful output without maintaining a second network/API equivalence suite.

## Local performance

Measure actual Python work, including command resolution and the next focused query. Start with a representative small encounter, then grow the workload when supported play grows. Record the machine, Python version, workload, and sample count so results can be compared.

Working budgets are ordinary command-plus-query p95 below **100 ms** and scripted input-to-next-menu below **250 ms**, excluding human input time. Keep the focused development suite below **30 seconds** where practical. S1 and S3 measurements are recorded in the [work log](../work-log/README.md); compare equivalent workloads rather than treating these budgets as measured results.

Measure test memory as well as latency. Record full-suite peak memory and a bounded failure-path measurement when test input/capture changes. A passing short run does not prove that a stalled test is safe. Test limits must fail clearly and preserve meaningful assertions; they must not change game rules, silently discard required evidence, or hide incomplete play.

Own the lifecycle of every started test or probe. Record its PID or yielded command session and owning agent/run when it can outlive the immediate call. A tool response containing a running session is not an exit, and a later passing test does not close an earlier probe. Stop timed-out or superseded work, wait for exit, and reap child processes before launching a replacement. Before reporting no retained jobs, reconcile every launched session, including failed temporary probes. Prefer synchronous bounded commands; do not launch background work merely to shorten a tool wait.

At integration checkpoints, when workers become idle or complete, and before final handoff, audit the processes started by those workers. Distinguish the worker's exit report from an independently checked process inventory; if enumeration is unavailable, report that limitation instead of claiming an all-clear. Stop unused task-owned Python, Node, Playwright, Chrome, or other probes with a graceful signal, then confirm exit. Recheck process identity before signaling because a PID can be reused. Investigate a child by parent/group, start time, command, and working directory when needed; preserve the reported timezone or normalize it explicitly. Leave active or shared services alone when exclusive ownership is unclear. Never kill by process name or terminate every Node/Python process. Record cleanup outcomes or an unresolved attribution limit briefly in the work log.

This periodic cleanup is part of active supervision, not a scheduled automation or a background process manager. Simple execution records and bounded helpers are enough.

This Python-only project disables the standalone `playwright` and `node_repl` MCP servers in `.codex/config.toml`. Keep implementation and testing on Python/shell tools. This setting is not proof that a loaded desktop parent or existing workers stopped their servers: children can inherit the parent configuration, and the desktop adds its own REPL launch settings. Verify effective fresh-worker availability when possible; preserve shared app tools and do not use a host-wide reload as a project cleanup shortcut.

Measure save/load and memory behavior once saves exist; set workload-based budgets from that baseline. An outlier or failed budget triggers focused profiling of the affected path, not a new general performance framework.

Avoid generating all possible paths, full future turns, or unbounded history. Keep immutable content outside mutable encounter copies. Begin with simple snapshots and direct Python functions; introduce caching, indexing, or more elaborate transactions only for measured problems.

Keep one small repeatable benchmark and one current summary. Do not commit raw traces, repeated dashboards, videos, or large generated reports.

Reuse or minimally consolidate one checked-in integration command for pytest, elapsed time/peak memory and routine checks. Verify environment/path once, then reuse its exact invocation; do not repeatedly invent wrappers or create a framework. The current owner can consolidate the already-used bounded procedure if no equivalent command exists.

## Durable state, recovery and usage

[Current work](../work-log/ACTIVE.md) is the single compact recovery entry point. Its active table records the acceptance outcome, task/session, owner/model and necessary files, remaining blocker, last proof and next executable step. Update it on meaningful state changes. STATUS and README point there rather than duplicating the queue. Completed evidence and run history remain linked through the [work-log index](../work-log/README.md).

After compaction or interruption, read the active table and named packet. Query an individual worker or scoped prefix only when needed. Do not load broad historical agent lists, full old reports or whole session transcripts to reconstruct current ownership.

Use one deterministic collector CLI for dispatch, completion, reused-worker boundaries and milestone totals. The workflow must read identified session metadata, deduplicate per-request `token_usage_record` entries, exclude inherited parent records, and include compaction requests. Preserve observed model/effort and exact boundaries; cached input is a subset of input. Keep original history and its source labels when reconciling older event-token accounting. Missing values remain null with reasons; running counts remain provisional.

Record a fresh dispatch once its session identity is known. Capture a reused worker's boundary before a genuinely new assignment. Internal checkpoints, a test-window wait, or ordinary review fixes remain part of the same assignment; do not artificially complete/re-register them. Complete its accounting after acceptance or an actual reassignment, with accurate observed boundaries and process status. At milestone completion report elapsed time, total agent cost/usage, implementation handoffs, review repairs and accepted behavior. Preserve input/cached/output totals; if monetary cost is unavailable, say so rather than inventing a price. Print concise collector totals, not the whole ledger or bespoke bookkeeping scripts.

For the next two completed playable slices, also use existing logs to report time to first executable check and explicit dependency-wait time. Record owner changes and review repairs with total elapsed delivery time and accepted behavior. This is a small comparison in the existing packet/work log, not a new metrics workflow; label any unavailable timing honestly.

The collector entry point is `python3 tools/log_agent_usage.py`. Its normal calls are:

```sh
# After spawning; use --reused before a genuinely new assignment to an existing worker.
python3 tools/log_agent_usage.py dispatch --log docs/work-log/agent-runs.json \
  --run-id RUN_ID --agent-path /root/WORKER --fresh \
  --task 'Bounded assignment' --model gpt-5.6-luna --effort xhigh

# After acceptance (including ordinary review repairs) and the process cleanup report.
python3 tools/log_agent_usage.py complete --log docs/work-log/agent-runs.json \
  --run-id RUN_ID --agent-path /root/WORKER \
  --status complete --result 'Concrete result and check evidence'

# Compact evidence for one completed run.
python3 tools/log_agent_usage.py milestone --log docs/work-log/agent-runs.json \
  --run-id RUN_ID
```

Use the real assigned model and effort. Exact session IDs can replace agent-path discovery. Fresh registration counts local worker requests already emitted before registration; reused registration marks the boundary before the follow-up. Never re-register a reused run as fresh to fill a missing boundary. Keep older accounting labels and reconciliation evidence; missing metadata is not zero usage.

The collector handles usage/configuration metadata only. Do not copy conversation/tool text, secrets or unrelated sessions into the work log. Keep local session paths and raw identifiers out of the human summary except the compact recovery table’s necessary task/session identity.

Keep useful user progress updates and the first executable-checkpoint safeguard. Internal worker reports use collaboration messages or automatic final handoff, never cross-task app messages. The coordinator relays only actual dependencies and decisions, without acknowledgement-only traffic or redundant status polling.

## Uncertainty and stopping

P0 means a question prevents a safe or coherent next step, such as contradictory core rules or an unavailable required dependency. Record the exact question in ACTIVE and the owning packet, call it out with the in-thread question tool, and continue independent work only.

Clarify P1 uncertainty before a materially dependent design or product commitment. Routine reversible choices use agent judgment and a brief note. Do not manufacture approval gates for ordinary implementation or content already inside the user's authorized scope.

If a bespoke option requires disproportionate machinery, remove it from the proposed roster and continue. If a core mechanic or save/replay/performance check fails, isolate and fix the affected slice; do not label it supported or hide the failure with manual edits.

## Handoff

Report accepted behavior, changed files, actual checks and measurements, elapsed time, total agent cost/usage, handoffs, review repairs, known limits and next action. Link the plan, current state and log. Do not count unsupported boundaries as delivered or silently drop approved requirements to claim completion. Git commits and changes in other worktrees require their own actual execution.
