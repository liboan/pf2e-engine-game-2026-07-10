# Content W2 recovery

Status: W2 authorized; guidance committed before substantive dispatch to retained tasks. [Working model](../plan/04-delivery-and-checks.md), [W2 scope](../plan/06-class-and-content-expansion.md#content-w2-broader-related-families). W1 lineage titles and six task identities are retained; no replacement tasks or worktrees.

## Accepted baseline and W2 checkout contract

Coordinator starts clean at W1 closure `dd74a7df3ee39f76c47eb75c14f4d9a4d604acb6`, containing accepted implementation `2d76a1c2bb75dfb8252634549c630ec3f2b7924e`. W1 final **1,397 / 8.79s**, checkpoint **9.273s**, peak **86,786,048 bytes**, compile/diff 0; catalog **92/71** admitted, **22/11** staged, save18. This is inherited evidence, not a new W2 run. [Preserved W1 evidence, repairs and independent tests](archive/content-w1-accepted.md).

Each retained task advances its own existing checkout to the exact common W1-plus-W2-guidance commit supplied in dispatch before new edits. Preserve old branch tips, review tests and uncommitted work; use a fresh W2 branch in the same checkout rather than remerging superseded cherry-picked W1 histories. Detached item owner must preserve its old HEAD with a branch first. No destructive reset, replacement or nested worktree. Coordinator's source/test/tool tree remains the accepted W1 implementation.

Working directory root for table entries: `/Users/andrewlee/.codex/worktrees/<directory>/pf2e-engine-game-2026-07-10`. Interpreter `/Library/Frameworks/Python.framework/Versions/3.11/bin/python3` (3.11.1), pytest8.4.2, `PYTHONPATH=src`, timeout `/opt/homebrew/bin/timeout`; each task verifies once locally without a readiness report. See working model for focused and canonical invocations.

## Retained W2 assignments

| Exact lineage title | Task ID / model | Existing cwd / pre-W2 branch | Outcome / direct peers | Checkpoint / next action |
|---|---|---|---|---|
| PF2e Content W1 — Coordination | `01a0bc89-010f-7f33-8ea1-e359e6ed6a93` / Astra high | `d438` / `codex/pf2e-content-w1-coordination` | scope, guidance, milestones; integration lead below | common guidance then substantive dispatch; no ordinary repair relaying |
| PF2e Content W1 — Spells and integration | `01a0bc8d-f040-7c81-b59c-7edb1c1b0487` / Terra high | `d4ce` / `codex/content-w1-assembled` | related low-rank hostile spells; own spell seams + integration; spell reviewer, both peer owners | W1 accepted; advance baseline, brief candidates then family implementation |
| PF2e Content W1 — Combat feats | `01a0bc8e-3447-7b60-bbe6-d561d824d0f8` / Terra high | `c57e` / `codex/content-w1-martial-feats` | related L1/L2 defensive/positioning feats; feat/item reviewer, integration lead | W1 accepted; advance baseline, brief candidates then family implementation |
| PF2e Content W1 — Finite items pilot | `01a0bc8e-a45d-76b2-9f72-30c02d579e07` / Luna high | `99a6` / detached `5c41366` | related established healing/timed protective or mobility consumables; feat/item reviewer, integration lead | W1 accepted; preserve HEAD, advance baseline, candidates then family implementation |
| PF2e Content W1 — Spell and integration review | `01a0bc8d-0a0d-7952-b0a1-3a1506d1eaf5` / Sol high | `dbbb` / `codex/content-w1-assembled-review` | independent spells + assembled review; spell owner/integration lead | preserve W1 tests, advance baseline; bounded useful preparation then end until concrete handoff |
| PF2e Content W1 — Feat and item review | `01a0bc8d-49aa-7072-a253-35fc9635cce1` / Sol high | `7404` / `codex/content-w1-martial-review` | independent feats/items; respective owners and integration lead | preserve W1 tests, advance baseline; bounded useful preparation then end until concrete handoff |

## Action routing and recovery

Message only the task whose next action changes. Routine delivery/repair is owner ↔ assigned reviewer. Reviewer sends accepted commits/tests directly to integration lead; owner does not duplicate acceptance. Integration lead sends assembled acceptance or unresolved decisions to coordinator. Earlier coordinator contact is only for scope, priority, shared-contract or unresolved blocking decisions requiring its action. No coordinator CC for awareness, environment checks, ordinary checkpoints, repairs or family acceptance. Do not forward handoffs already sent directly. END when only another task's work remains; no waits/sleep/status/transcript loops or acknowledgements.

Central recovery updates occur at meaningful milestones. Detailed current output and ordinary review status remain with owners/reviewers. Exact W2 content selections and branch changes will be consolidated at an actionable integration/scope milestone, not through bookkeeping wakeups. All six tasks retain models/roles confirmed during W1; no current capability conflict known.

Resume existing heartbeat `pf2e-content-w1-execution` for W2, five-minute fallback only; pause at W2 acceptance/user pause. Older coordinators and execution heartbeats remain paused. Cost monitoring stays with audit task `01a0a8e5-7dec-7030-8679-120b66f70e44`. The local ignored usage ledger is absent; no new metrics framework or guessed usage. W2 is a new reused-task assignment; do not attribute cumulative W1 task lifetime to it.
