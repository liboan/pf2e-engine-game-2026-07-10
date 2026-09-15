# Delivery, checks, and work records

## Operating model

The supervisor owns the plan, assignments, integration decisions, and durable work log. It synthesizes subagent findings without reading repository implementation or rules sources directly. Its exception is authoring and maintaining the plan and work log. Readers and implementers inspect the content needed for their bounded tasks.

| Work | Model and reasoning | Use |
|---|---|---|
| Straightforward scoped implementation, focused tests, small debugging, documentation integration | `gpt-5.6-luna`, `xhigh` | Default worker for clear tasks. |
| Open-ended targeted play, broader debugging, implementation critique | `gpt-5.6-sol`, `high` | Periodic review, substantially less frequent than ordinary implementation tasks. |
| High-level design, investigations, extensive rules-behavior critique | `gpt-6-astra`, `high` | Resolve genuinely open problems and define tractable scopes. |

Give each task a result, owned files, relevant context/source questions, focused checks, and a stopping condition. Keep ownership non-overlapping while agents work concurrently. Permit routine adjacent refactoring within the assigned slice; a newly needed field does not require a planning ceremony.

Use explicit model/effort overrides with no history fork or a bounded history fork. A full-history fork does not support those overrides. Verify actual configuration from usage metadata when available.

## Assignment and review cadence

An implementation slice starts with enough source research and expected cases to define its promised behavior. Then delegate bounded code and test tasks to Luna. Root integrates their findings and keeps the current state readable.

Use Sol after a meaningful runnable slice or a group of related changes, and when a failure needs broader exploration. Its job is to execute the actual Python engine, try relevant alternate choices, inspect resulting state, and verify applicable rules against sources. Do not commission a separate Sol review for every small change.

Use Astra for unresolved cross-cutting design or substantial rules uncertainty. Routine implementation questions remain with the worker. Reviews can challenge the plan; the supervisor resolves changes in the owning document rather than appending competing instructions.

S1–S3 now have actual runtime, saved-choice, complete-play, and performance evidence. Every later milestone must also execute the actual engine; plan-consistency checks never substitute for game, persistence, or performance evidence.

## Modular tests and integration cadence

Organize tests around the changed rule or encounter family. A worker runs the smallest relevant selection after an edit: a rule file, one named encounter, or that encounter's milestone checks. Run the entire suite at a meaningful integration/handoff checkpoint, including after related shared-core corrections affecting several families are ready. One passing broad run satisfies that checkpoint; repeat it only when new edits, failures, or unresolved concerns justify it. Independent full play follows a meaningful group of changes rather than every definition or test edit.

Each worker uses one synchronous pytest process at a time, with no parallel test workers or watch loop. Short focused runs can overlap; only one broad integration run should be active at a time. Keep ordinary pytest files and small shared Python helpers. Each encounter case names its setup, interaction to prove, expected observable milestones, deterministic dice or seed, and completion condition. Helpers may submit public commands, answer explicit choices, save/load, and check results. They do not recalculate rules, patch hidden state, silently choose around unsupported behavior, or retain every intermediate snapshot.

Bound command count, rounds, supplied dice, input, captured output, and any subprocess runtime. A limit failure reports the encounter and last relevant state and then releases its resources. Keep only a short diagnostic tail where complete output is unnecessary; required assertions must observe the actual results before they are discarded. Existing bounded terminal captures continue to fail before retaining excess output.

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

Own the lifecycle of every started test or probe. Record its PID or yielded command session and owning agent/run when it can outlive the immediate call. Stop timed-out or superseded work, wait for exit, and reap child processes before launching a replacement. Prefer synchronous bounded commands; do not launch background work merely to shorten a tool wait.

At integration checkpoints, when workers become idle or complete, and before final handoff, audit the processes started by those workers. Stop unused task-owned Python, Node, Playwright, Chrome, or other probes with a graceful signal, then confirm exit. Recheck process identity before signaling because a PID can be reused. Investigate a child by parent/group, start time, command, and working directory when needed; leave active or shared services alone when exclusive ownership is unclear. Never kill by process name or terminate every Node/Python process. Record cleanup outcomes or an unresolved attribution limit briefly in the work log.

This periodic cleanup is part of active supervision, not a scheduled automation or a background process manager. Simple execution records and bounded helpers are enough.

Measure save/load and memory behavior once saves exist; set workload-based budgets from that baseline. An outlier or failed budget triggers focused profiling of the affected path, not a new general performance framework.

Avoid generating all possible paths, full future turns, or unbounded history. Keep immutable content outside mutable encounter copies. Begin with simple snapshots and direct Python functions; introduce caching, indexing, or more elaborate transactions only for measured problems.

Keep one small repeatable benchmark and one current summary. Do not commit raw traces, repeated dashboards, videos, or large generated reports.

## Durable state and usage records

- [STATUS](../../STATUS.md) is the single latest project-state summary: what works, what does not, current blockers, and next action. Replace stale state rather than appending contradictory snapshots.
- [Work log](../work-log/README.md) gives a short human-readable chronology and the current work outcome without requiring implementation context.
- [Agent runs](../work-log/agent-runs.json) records each dispatched run, including follow-up runs, its task, model/effort, status, result, and measured usage.

Record a run when dispatched and update it when completed. Refresh status and the human summary at meaningful milestones and before handoff. During long work, keep thread updates concise and regular.

For every run store input tokens, cached input tokens, and output tokens. Cached input is a subset of input: do not add it a second time. Preserve requested and observed model/effort separately when available.

Use session usage metadata, not guesses. A reused subagent's totals are cumulative; subtract the recorded start counters to obtain each follow-up run's usage. Collect final counters after completion. While a run is active, mark counts provisional; if counters are unavailable, use null plus a reason, never fabricated zeros. The supervisor's own ongoing usage is likewise provisional until a later refresh can observe completion.

The collector may read only the identified sessions' configuration and usage metadata. It must not copy conversation text, tool transcripts, secrets, or unrelated session data into the work log. Keep local session paths out of the human summary.

## Uncertainty and stopping

P0 means a question prevents a safe or coherent next step, such as contradictory core rules or an unavailable required dependency. Record the exact question in STATUS and the owning plan segment, call it out with the in-thread question tool, and continue independent work only.

Clarify P1 uncertainty before a materially dependent design or product commitment. Routine reversible choices use agent judgment and a brief note. Do not manufacture approval gates for ordinary implementation or content already inside the user's authorized scope.

If a bespoke option requires disproportionate machinery, remove it from the proposed roster and continue. If a core mechanic or save/replay/performance check fails, isolate and fix the affected slice; do not label it supported or hide the failure with manual edits.

## Handoff

Report the concrete result, changed files, actual commands/check outcomes, measurements when available, known limitations, and next action. Link the plan, current state, and log. Do not claim merged or implemented work when only a plan was written. Git commits and changes in other worktrees require their own actual execution; this reset does neither implicitly.
