# Content W5 recovery

Status: **W4 fully accepted and published; W5 plan adopted; fresh implementation/review team dispatch is in progress.** Existing Astra/high coordinator `01a0bc89-010f-7f33-8ea1-e359e6ed6a93`, checkout `/Users/andrewlee/.codex/worktrees/d438/pf2e-engine-game-2026-07-10`, coordination branch `codex/content-w5-coordination`.

Read [working model](../plan/04-delivery-and-checks.md) and [accepted-W4 handoff](../plan/08-content-w5-handoff.md). W4 accepted code/tests `1f4d09315a86f6fc9d71e51eef607e83eb68967c`, evidence child `ed8e86fe4d02b4e4e3bace40918d3fc3f9b86c8d`. Accepted W2 `a58424b0f9e0e515e302c149500624580c925780` and W3 `832d44b6816cd42d2c9cc9d3cfc2753d906774d1` verified ancestors. Coordinator merge preserves exact accepted src/tests/tools.

W4 delivered eleven new feats; Widen remains W3-existing and Dangerous Sorcery deferred. Independent final repaired assembly accepted, canonical1,496 tests/7.53s, runner7.867s, peak88,342,528 bytes, compile/diff/test0, accepted117/94 staged24/12 save18. [Acceptance evidence](archive/content-w4-accepted.md); prior W4 IDs/models/checkouts preserved in [coordination archive](archive/content-w4-coordination.md). W4 tasks are closed for milestone purposes and will not be carried/forked into W5.

Publication verified: `codex/pf2e-content-w4-delivery` local/origin matched `120fa82267bae82abdba43042f9a2b1f0e99b489`, checkout clean, accepted W2/W3/W4 ancestry and exact accepted src/tests/tools preserved. No open PR at preflight; no new PR required. W4 delivery is closed at that verified head; W5 coordination now uses its own branch.

## W5 dispatch

Planner **PF2e Content W5 — Planning**, `01a0bef4-dfe3-7903-bb8c-a41606cc4770`, Astra/high, fresh checkout2979, completed at `55a5f39cc8810add5702cba66961354cc61eaf12`; note adopted as `fcf46c3`. Baseline was verified clean at `b4886d45d91bef192fc52796f82d996d927fc3f7`. Reuse planner only for substantial unresolved design/rules decisions; no status/debugging role.

Adopted [bounded plan](w5-planning.md): eight genuinely new feats across seven classes—Tiger Stance, Wolf Stance, Raging Thrower, Extravagant Parry, Initiate Warden, Harming Hands, Hymn of Healing (seven L1), plus explicitly L2 Strong Arm. New spells Gravity Weapon and Hymn of Healing; no new items required. No credit for existing configurations/incidental unplayed grants. Dragon Stance/Acute Vision deferred. Planner reports no substantial unresolved P1; fresh Sol reviewers independently verify all assumptions.

Dispatch three fresh Luna/high owners A Monk stances, B Arms and parry/integration, C Focus and font; three fresh Sol/high group reviewers plus a fourth fresh Sol/high final assembled reviewer. All new full tasks and isolated worktrees from published accepted W4 plus adopted plan/guidance; no W4 conversations/forks. Exact identities/checkouts will be recorded after creation.

B owns the shared Strike notification contract and single save-version decision, integrates accepted B→A→C families, and runs final canonical gate after separate assembled acceptance. A owns stance/Step/Trip/persistent helpers; C owns composition/sustain/typed-status helpers. Narrow shared call sites only; B integrates semantic overlap. Planner note supplies exact verified symbols, analogous tests, source decisions and review cases. Every assignment reads it plus the accepted-W4 handoff. No replacement tasks through ordinary repairs.

One actual family owner leads integration. Ordinary owner↔reviewer delivery/repairs; reviewer→lead accepted commits/tests; lead→coordinator only real decisions or full assembled acceptance. No CC/ack/status loops, duplicate handoffs or repeat review requests. End promptly when only autonomous peer work remains.

Existing `pf2e-content-w1-execution` heartbeat stays ACTIVE through W5 and pauses at full W5 closure/user pause; no new schedules. Older coordinators/heartbeats remain paused. Cost audit remains `01a0a8e5-7dec-7030-8679-120b66f70e44` only. W5 publication authorized at full closure with accepted W2/W3/W4/W5 ancestry, exact remote/local head and clean checkout; no force/main merge/unrelated overwrite. Remaining supported boundaries in handoff/model remain binding.
