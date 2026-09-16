# Operating workflow checkpoint

## Outcome

The engine work now resumes from one short [current-state page](ACTIVE.md). Past evidence remains archived and linked, rather than being loaded again to reconstruct ownership. AGENTS, README, STATUS and the delivery plan point to this working model.

Worker reports arrive at a decision, a shared interface change, the first executable checkpoint or completion. They use internal collaboration or normal final reports; the supervisor gives the user a consolidated account. Independent rules review, actual Python play, focused tests, saved decisions and bounded memory checks remain required.

One collector command handles assignment, completion and usage summaries. It reads per-request usage metadata, including compaction requests when present, instead of relying solely on older running totals. Fresh runs begin at local session metadata; reused workers receive a boundary before their follow-up. Original legacy evidence is retained. Missing raw records are unavailable, not zero or invented usage. The [delivery plan](../plan/04-delivery-and-checks.md) contains the commands.

## Verification

A separate Luna worker reproduced and repaired an inherited-parent identity edge: a record with a parent `session_id` and no `thread_id` could previously be charged to the child. The regression and remaining focused collector tests pass: **7 tests in 0.443 seconds**. The collector self-test passes.

The independent real-session check found 30 local request records with the observed Luna/xhigh configuration. Fresh accounting matched that session boundary. A reused boundary with no later requests did not charge the lifetime usage again. This real sample contained no compaction requests; compaction handling was tested with the focused fixtures, not demonstrated by that sample.

A later real spell-targeting run also reports one compaction request: `dim-core-spell-gate-2026-09-16` has 88 deduplicated requests, input 11,091,484, cached input 10,863,616 and output 52,321, with observed Luna/xhigh. Cached input is included in input, not an additional total. This is one reused assignment's measured usage, not the worker's lifetime total; its dispatch boundary was recorded before the follow-up. The ledger retains the raw accounting source and availability status.

A legacy session without raw request records retained its old token-count evidence in history and reported current raw usage unavailable. Older runs have not all been re-audited. The newly completed collector, documentation and identity-test rows were refreshed after the identity-filter repair.

Documentation validation checked **77 local links and one fragment**, with none broken. All reported checks were synchronous and exited; no background processes were launched. This is not a host-wide process census or a claim that desktop-owned MCP servers stopped.

## Continued use of this model

Subsequent Runic Weapon, Light, targeting, terminal and independent-play work uses the same collector. The updated [delivery guidance](../plan/04-delivery-and-checks.md) now keeps each bounded playable outcome with one Luna owner through runtime, saves, terminal, tests and ordinary review repairs. Only a genuinely new assignment creates a reused boundary; internal checkpoints and test waits do not close runs. Earlier records retain their accurate observed boundaries rather than being rewritten. Current ownership and executable evidence belong in ACTIVE, not this historical checkpoint.

At the Light checkpoint, a dedicated process worker obtained one scoped escalated inventory after ordinary `ps` was denied. It found no descendants attributable to the completed engine workers. Node/Playwright processes belonged to shared ChatGPT.app MCP services; the sole separate Python candidate belonged to an unrelated localclaw benchmark, verified by its working directory. No termination was warranted. Earlier sandbox-denied checks remain honestly recorded as unavailable; the later successful audit does not rewrite their evidence. Continue to use command, parent, start time and working directory before stopping anything, and never kill a shared service by name.
