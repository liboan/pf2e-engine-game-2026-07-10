# Content W2 working model

**W2 accepted and closed.** The existing execution heartbeat is paused. These instructions preserve the operating model for future authorized work; no automatic next wave is authorized. Final evidence is in [ACTIVE](../work-log/ACTIVE.md).

This working model supersedes the historical Terra-only, native-subagent-only and completed-generalization-only execution rules. The user authorized Content W2 now, reusing the existing six tasks, roles/models and worktrees, with broader coherent families and corrected routing. W1 is accepted; W2 is a new assignment, not replacement tasks. No further planning approval is needed. Historical evidence is preserved in [the previous recovery snapshot](../work-log/archive/active-before-content-w1-2026-09-20.md) and [previous workflow](../work-log/archive/working-model-before-content-w1-2026-09-20.md); their execution instructions are not current.

## Team and checkouts

| Role | Model / effort | Ownership |
|---|---|---|
| Coordinator | gpt-6-astra / high | Guidance, bounded scope, task/peer recovery, acceptance decisions; no engine/source inspection |
| Spell family owner and integration lead | gpt-5.6-terra / high | One coherent spell family end to end, then assembled integration in the same checkout |
| Feat family owner | gpt-5.6-terra / high | One coherent feat family end to end |
| Established item family owner | gpt-5.6-luna / high | Established-mechanic item family with limited source uncertainty |
| Spell/integration reviewer | gpt-5.6-sol / high | Independent complete spell-family and assembled interaction review |
| Feat/item reviewer | gpt-5.6-sol / high | Independent complete feat/item-family review |

All full Codex tasks use the exact title prefix `PF2e Content W1 — `, including descendants and renames. Native subagents are not the primary team. The standalone Luna/high app capability was demonstrated; do not conflate it with an old native-tool limitation. Report an actual tool/model conflict only to the peer who can resolve it, escalating to coordinator if its decision is needed. No readiness ceremony. Retain useful work and escalate observed capability/quality problems.

Each retained task keeps its existing isolated worktree through W2 and repairs. Before new edits inspect its own status, preserve all old branch tips/review artifacts and any uncommitted work, and create a W2 assignment branch at the exact common accepted-W1-plus-guidance baseline recorded in dispatch. A detached task first preserves its old HEAD with a local branch. Do not reset away changes or overwrite another checkout; if uncommitted changes cannot be safely retained, report the specific blocker. Reusing a checkout does not require merging superseded W1 cherry-picked histories back into the accepted baseline. No replacement tasks, nested worktrees or extra mutable checkouts. Existing W1 title prefixes remain lineage.

Reviewers inspect explicit delivered commits in their own retained checkout, preserving review artifacts. The spell owner remains integration lead, incorporates accepted delivered commits/tests and resolves routine conflicts with owners. Land shared prerequisites before dependent integration. Coordinator merges the accepted assembled result into its own branch after final evidence; it does not inspect implementation or act as a separate integration translator. No copied virtual environment assumption.

## Select and execute

Start from existing source packets and accepted tests. Each owner briefly assesses a few candidates for useful shared mechanics, legal access, material differences, likely duplication and excluded expensive prerequisites. Select and implement a larger coherent related family within the assigned outcome, rather than defaulting to one spell or feat. Size by shared mechanics, uncertainty and playable usefulness, never an arbitrary count. Keep the candidate assessment concise with the owner; send it with actionable review material, not a separate coordinator update. If a lane has no suitable family or a scope/contract decision is needed, send the smallest actionable blocker to the appropriate peer. No exhaustive catalog or approval per feat.

Before adding content, improve touched structure when otherwise duplicating branches or mixed responsibilities. Cohesive extraction must have real multiple callers, delete replaced paths and preserve semantic distinctions. A split of oversized modules is authorized when directly useful to the delivered family. Existing spell-save/preparation/BombFacts and W1 basic-save damage/stun/timed-condition mechanisms are preferred starting seams, not a ceiling on future simplification. Coordinate any shared abstraction with one named owner and explicit contract. Keep independent work parallel; isolate semantic conflicts despite separate worktrees.

Each owner supplies legal grants, execution, literal persistence validation, terminal access, meaningful source-informed tests and complete-play evidence. Do not count unselected inventories, placeholders or test-only definitions as delivery. Preserve documented class boundaries and pending GM rulings in the class plan.

## Review and validation

Use W1 findings to inform W2 checks: melee/ranged legality and cost atomicity, critical initial/persistent damage versus splash, duration cleanup and own-save validity after rest. Do not create a separate requirements bureaucracy. Before coding, translate easily confused source facts into a short note or meaningful tests. Before changing an assertion or rule to address failure, check the source and actual fixture. Reviewers may independently prepare relevant source/acceptance checks early, then end their turn. Full reviews operate on delivered runnable commits, with consolidated actionable findings. Owners and reviewers exchange repairs directly, keeping the same assignment and checkout. Optional coverage is distinguished from incorrect behavior or missing promised acceptance.

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

Direct `send_message_to_thread` exchanges are authorized for scoped assigned work. Send a message only to the task whose next action changes. Routine runnable delivery and repair go owner ↔ assigned reviewer. The reviewer sends accepted commits/tests to the integration lead; owners do not duplicate acceptance reports. The integration lead contacts the coordinator for assembled acceptance or a decision it cannot resolve. Contact the coordinator earlier only for scope, priority, shared-contract decisions or unresolved blockers requiring coordinator action. Do not CC the coordinator for awareness, environment checks, ordinary checkpoints, repair-ready updates or per-family acceptance; do not forward a handoff already delivered directly. Exact peer IDs are in ACTIVE. This replaces the W1 instruction to send first checkpoints to both reviewer and coordinator. No acknowledgements, receipt requests, repeated status pings or per-test narration. Integration lead does not repeatedly request a review already delivered. Native tools are only for actual native subagents.

**END YOUR TURN whenever only another task's work remains.** Reviewers finish useful inspection and report findings, then end until a delivered change arrives. Owners report a real dependency once and end unless independent useful work remains. Ending is not abandonment. No wait/sleep/status/transcript/commentary loops to stay active. Coordinator resumes the existing `pf2e-content-w1-execution` heartbeat for W2 as the single roughly five-minute fallback, inspects compact changed state once, acts and ends. No worker automation. Older coordinators and execution heartbeats remain paused. Pause this heartbeat at closure or user pause.

## Recovery and accounting

Update central recovery only at meaningful milestones; do not wake the coordinator just for bookkeeping. ACTIVE is the compact single recovery entry point: task ID/exact title, cwd, branch/base, owner/model, exact peer IDs, scope, blockers, last public checkpoint and next action. Plans and work logs belong to coordinator; owner source notes/tests and detailed outputs stay with owner. Handoffs include exact symbols/files, analogous test/helper, actual environment/cwd, last public probe (or none), contract and dependencies, normally in 250–400 words.

Cost monitoring remains in the audit task. Reuse the existing deterministic `python3 tools/log_agent_usage.py` for needed dispatch/completion/new reused-assignment/milestone bookkeeping; inspect its CLI help for exact standalone-session arguments. Do not build a second metrics system. `docs/work-log/agent-runs.json` is ignored local output; absence in fresh checkout is normal. Preserve deduplicated raw request identity and compactions, exclude inherited parent usage, retain model/effort and exact boundaries, and label unavailable values with null/reason. Repairs and checkpoints do not start new assignments. Accepted historical totals remain in the archived recovery record.

P0 blockers require the smallest structured user question; resolve P1 before dependent commitments. Routine reversible choices and source-supported repairs need no approval. Preserve independent work, meaningful assertions and supported limits while resolving failures.
