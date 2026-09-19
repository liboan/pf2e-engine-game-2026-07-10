# Codex working rules

These rules apply to every Codex thread and subagent in this repository. The detailed operating model is [docs/design/05-codex-delivery.md](docs/design/05-codex-delivery.md); do not repeat it in task prompts.

## Before work

1. Read [README.md](README.md), [STATUS.md](STATUS.md), the assigned [work package](docs/templates/work-package.md), the relevant records in the [registry](registry/README.md), and only the design chapter and rule oracle needed for the task.
2. Confirm the package is `ready`, its base commit is current, the worktree is clean, dependencies are merged, and file ownership does not overlap another active package.
3. State the package result, exclusions, permitted files, required evidence, and stop conditions. One thread owns the package; readers and reviewers return bounded artifacts.

## Scope and architecture

- Build the successor independently. Do not import the predecessor runtime, compiler, schemas, trackers, or compatibility layers. An audited rule case or small pure procedure may be ported only through a named package and new tests.
- Shared code may branch on typed PF2e facts. Modules may carry opaque instance references to identify sources and targets, but may not compare names or IDs to select behavior for a creature, action, fixture, encounter, or definition.
- Use the small declarative format for common composition and first-party typed modules for specialized printed behavior. Do not add arbitrary scripting, dynamic module loading, or fallback execution.
- Modules receive immutable context and return only the phase's closed result type. The engine validates operations and orders modules deterministically.
- A paused command is a committed suspension: advance the state revision and store a serializable frame. Only rejected or unsupported requests leave canonical state unchanged.
- Keep rules logic out of the service and client. Use revision-bound prompts, idempotent retries, compact deltas, focused option queries, and explicit inspectors.

## Rules and evidence

- Implement only against an approved exact rules profile and reusable source records. Each definition's behavior inventory assigns every rule-relevant clause one disposition: `mapped`, `non-executable`, `excluded`, or `unsupported`. Any `unsupported` clause blocks playable status.
- Definition lifecycle is separate: `candidate`, `supported`, or `retired`. Production loads only `supported` definitions whose behavior inventories close without unsupported clauses.
- The oracle precedes code. An implementer may challenge it but may not silently change an expected result. Material changes return to rules review.
- Record evidence dimensions separately as `source-reviewed`, `isolated`, `generalization`, `production-path`, `continuous`, `client`, and `performance`. Only `generalization` may be `N/A`, with a reason. Apply the oracle's risk tier: shared rules need unlike adopters, an independent holdout, and targeted mutations.
- Every supported path runs through source content, compiler, engine, save/resume, public API, and headless client. Checkpoints may isolate defects but never count as uninterrupted encounter progress.
- Run focused tests while developing, then the package's independent, continuous-play, persistence, and player-flow performance gates before handoff. Recompute evidence from the integration branch.

## Keep outputs small

- Follow [bloat budgets](docs/design/06-bloat-and-human-review.md). Do not commit raw traces, profiles, videos, repeated dashboards, generated snapshots, or superseded documents.
- A handoff contains only package ID and state, base/head commits, changed claim, files, exact commands and results, measurements, exclusions, and next action. Link artifacts; never paste transcripts or full logs.
- Comments explain a source, invariant, ordering, or safety constraint. Delete replaced paths and prose in the same change.

## Stop and escalate

Stop the package when the rules profile is unclear; a source interpretation is disputed; a shared contract must change outside scope; unsupported behavior would be approximated; a second adopter needs another special branch; deterministic replay, save/resume, or a budget fails; or the baseline is no longer current. Record the failed gate and smallest decision needed. Do not widen the package to work around it.

Human approval is reserved for the decisions listed in [human review policy](docs/design/06-bloat-and-human-review.md). Routine approvals should be batched; merged code is not support-accepted behavior.
