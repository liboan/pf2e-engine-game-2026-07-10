# Content W1 working model

This working model supersedes the historical Terra-only, native-subagent-only and completed-generalization-only execution rules. The user authorized reconciliation, a reasonable first expansion wave and implementation without another planning approval. Historical evidence is preserved in [the previous recovery snapshot](../work-log/archive/active-before-content-w1-2026-09-20.md) and [previous workflow](../work-log/archive/working-model-before-content-w1-2026-09-20.md); their execution instructions are not current.

## Team and checkouts

| Role | Model / effort | Ownership |
|---|---|---|
| Coordinator | gpt-6-astra / high | Guidance, bounded scope, task/peer recovery, acceptance decisions; no engine/source inspection |
| Spell family owner and integration lead | gpt-5.6-terra / high | One coherent spell family end to end, then assembled integration in the same checkout |
| Feat family owner | gpt-5.6-terra / high | One coherent feat family end to end |
| Finite item pilot | gpt-5.6-luna / high | Established-mechanic item family with limited source uncertainty |
| Spell/integration reviewer | gpt-5.6-sol / high | Independent complete spell-family and assembled interaction review |
| Feat/item reviewer | gpt-5.6-sol / high | Independent complete feat/item-family review |

All full Codex tasks use the exact title prefix `PF2e Content W1 — `, including descendants and renames. Native subagents are not the primary team. The standalone Luna/high app capability was demonstrated; do not conflate it with an old native-tool limitation. Report actual tool/model conflicts at the first substantive checkpoint, with no readiness ceremony. Retain useful work and escalate observed capability/quality problems.

Each task has one managed isolated worktree, reused through repairs. Start at the common committed guidance/baseline recorded in ACTIVE; worker creation may start at project main, but the first operation must advance to the explicit common baseline before edits. Never assume old uncommitted work or a copied virtual environment is present. Reviewers check out explicit delivered commits in their own checkout, preserving their own review artifacts. The integration lead merges/cherry-picks delivered commits, resolves ordinary conflicts, and owns assembled public validation. Other owners retain their family repairs. The coordinator can fast-forward its own checkout to the accepted assembled commit after evidence and recovery updates are ready.

## Select and execute

Start from existing source packets and accepted tests. Each owner briefly assesses a few candidates for useful shared mechanics, legal access, material differences, likely duplication and excluded expensive prerequisites. Select a small coherent playable family and immediately implement within the lane; report the selection with the first executable checkpoint. If a lane has no suitable candidate, send the smallest decision blocker. No exhaustive catalog or approval per feat.

Before adding content, improve touched structure when otherwise duplicating branches or mixed responsibilities. Cohesive extraction must have real multiple callers, delete replaced paths and preserve semantic distinctions. A split of oversized modules is authorized when directly useful to the delivered family. Existing spell-save/preparation/BombFacts mechanisms are preferred starting seams, not a ceiling on future simplification. Coordinate any shared abstraction with one named owner and explicit contract. Keep independent work parallel; isolate semantic conflicts despite separate worktrees.

Each owner supplies legal grants, execution, literal persistence validation, terminal access, meaningful source-informed tests and complete-play evidence. Do not count unselected inventories, placeholders or test-only definitions as delivery. Preserve documented class boundaries and pending GM rulings in the class plan.

## Review and validation

Before coding, translate easily confused source facts into a short note or meaningful tests. Before changing an assertion or rule to address failure, check the source and actual fixture. Reviewers may independently prepare relevant source/acceptance checks early, then end their turn. Full reviews operate on delivered runnable commits, with consolidated actionable findings. Owners and reviewers exchange repairs directly, keeping the same assignment and checkout. Optional coverage is distinguished from incorrect behavior or missing promised acceptance.

Coordinator-verified interpreter: `/Library/Frameworks/Python.framework/Versions/3.11/bin/python3`, Python 3.11.1, pytest 8.4.2; timeout `/opt/homebrew/bin/timeout`. Each worker verifies these in its actual cwd once. Focused invocation:

```sh
PYTHONPATH=src /opt/homebrew/bin/timeout 30s /Library/Frameworks/Python.framework/Versions/3.11/bin/python3 -m pytest -q <selection>
```

Canonical assembled invocation:

```sh
PYTHONPATH=src /Library/Frameworks/Python.framework/Versions/3.11/bin/python3 tools/integration_checkpoint.py
```

Use the checked-in runner for timing/peak memory/compile/diff checks; inspect its supported options locally rather than inventing flags. One synchronous pytest process per task, one broad integration at a time; focused checks need no global lock. Bound every terminal probe's time, input and capture. Reuse existing BoundedInput/BoundedTranscript helpers. A full suite took seconds at the inherited gate; do not assume it is an expensive bottleneck.

Acceptance requires focused/source review, full assembled suite, continuous public encounters, save/resume, actual terminal choices and bounded performance. Report what was exercised and what was not. At idle, handoff and integration, account for task-owned processes; inspect identity before stopping anything, gracefully stop only confirmed unused descendants and verify exit. Sandbox denial means unavailable inspection, not verified cleanup.

## Communication and turn ending

Direct `send_message_to_thread` exchanges are authorized to exact peer task IDs for scoped actionable work. Use native tools only for actual native subagents. Batch a decision blocker, changed shared contract, first runnable handoff, consolidated findings, repair ready to verify or accepted completion. Do not send acknowledgement-only replies, receipt requests, repeated status pings, per-test narration or routine coordinator relays.

**END YOUR TURN whenever only another task's work remains.** Reviewers finish useful inspection and report findings, then end until a delivered change arrives. Owners report a real dependency once and end unless independent useful work remains. Ending is not abandonment. No wait/sleep/status/transcript/commentary loops to stay active. Coordinator uses one roughly five-minute fallback heartbeat, inspects compact changed state once, acts and ends. No worker automation. Older coordinators and execution heartbeats remain paused. Pause this heartbeat at closure or user pause.

## Recovery and accounting

ACTIVE is the compact single recovery entry point: task ID/exact title, cwd, branch/base, owner/model, exact peer IDs, scope, blockers, last public checkpoint and next action. Plans and work logs belong to coordinator; owner source notes/tests and detailed outputs stay with owner. Handoffs include exact symbols/files, analogous test/helper, actual environment/cwd, last public probe (or none), contract and dependencies, normally in 250–400 words.

Cost monitoring remains in the audit task. Reuse the existing deterministic `python3 tools/log_agent_usage.py` for needed dispatch/completion/new reused-assignment/milestone bookkeeping; inspect its CLI help for exact standalone-session arguments. Do not build a second metrics system. `docs/work-log/agent-runs.json` is ignored local output; absence in fresh checkout is normal. Preserve deduplicated raw request identity and compactions, exclude inherited parent usage, retain model/effort and exact boundaries, and label unavailable values with null/reason. Repairs and checkpoints do not start new assignments. Accepted historical totals remain in the archived recovery record.

P0 blockers require the smallest structured user question; resolve P1 before dependent commitments. Routine reversible choices and source-supported repairs need no approval. Preserve independent work, meaningful assertions and supported limits while resolving failures.
