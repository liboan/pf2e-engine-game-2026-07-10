# Lessons from the predecessor

**Status:** Historical assessment informing the successor  
**Audience:** Anyone deciding why the successor is structured differently  
**Read this when:** A shortcut resembles the old approach, or a proposed abstraction needs historical context

## Bottom line

The predecessor became a strong PF2e research and regression laboratory, but not a reliably faithful, responsive encounter simulator. The main problem was not lack of effort. Content breadth, abstraction, tests, and reporting expanded before a small set of rules was proven across varied content and uninterrupted play.

The figures below describe an audited predecessor snapshot, not a current product claim: 1,021 commits reachable across the audit checkout's refs; 4,892 files and 792,203,797 tracked bytes at the audited commit; and 769,481,488 artifact bytes—about 97% of the tracked total.

## Audit provenance

The audit used the local predecessor at `/Users/andrewlee/Documents/projects/pf2e-engine-game-2026-05-05`. On 2026-07-10 its clean `HEAD` was exactly `4789fde115553518cd715da3f87b979ca85bc7ce`. No permanent remote repository URL is assumed.

Representative reproduction commands, run from that checkout:

```text
git rev-parse HEAD
git status --short
git rev-list --all --count
git ls-tree -r --name-only 4789fde1 | wc -l
git ls-tree -r -l 4789fde1 | awk '{s += $4} END {print s}'
git ls-tree -r -l 4789fde1 artifacts | awk '{s += $4} END {print s}'
git ls-tree -r --name-only 4789fde1 artifacts/tracking/snapshots | awk -F/ 'NF >= 4 {print $4}' | sort -u | wc -l
git show --shortstat --oneline 746ce452 --
git show 4789fde1:src/pf2e_engine/runtime/kernel.py | wc -l
```

Key evidence paths at that ref are `docs/generated-encounter-replay-tracker.md` and the final `artifacts/tracking/snapshots/tracking-zzzzzzzzzzzzzzz-post-pr87-snapshot-only-currentness-20260616T033446Z-1ffec0ab/rollups.md` for completion and branch counts; `tests/api_v1/test_segmented_replay_targets_generated_non_may19.py` for segmented checkpoint behavior; and `src/pf2e_engine/runtime/kernel.py` plus `src/pf2e_engine/runtime/services/reactions.py` for runtime shape. Use `git show 4789fde1:<path>` to inspect the audited version.

## Pitfalls and what they taught

### 1. Content arrived before stable meaning

Commit `746ce452` changed 1,560 files and recorded 110,158 insertions before runtime contracts were settled. That made later design changes migrations across a catalog, not small experiments.

**Lesson:** adopt only content needed by the next reviewed capability. Unknown mandatory behavior must block loading rather than enter as deferred or approximate data.

### 2. The language sat in the worst middle ground

The authoring format grew broad enough to be difficult to validate and compile, while its executable subset remained too narrow for unusual printed abilities. Exceptions then leaked into the compiler, runtime, API, and client.

**Lesson:** keep a small declarative format for common composition and use bounded, source-cited code modules for genuine exceptions. Do not turn content data into a second general-purpose rules engine.

### 3. Examples trained the implementation instead of testing the rule

Several cases passed because the code learned the chosen content:

- Commit `7d702c1e` introduced a generic-looking `press_choice` operation whose behavior was effectively Desperate Finisher: it spent a reaction and applied “No Reactions.”
- Step and Stride coverage relied on nearly the same training-yard shape, while a Huge dragon was represented as one square.
- A Twisting Tail case used fixed damage, but the selected shield canceled it, hiding the wrong value.
- One report assumed the relevant actor was `actors[0]` and broke when actors were reordered.
- Shared reaction handling recognized a literal Reactive Strike capability instead of letting the ability own that behavior.

**Lesson:** test unrelated adopters and a verifier-held example; rename and reorder identities; vary size, reach, values, and map placement; and deliberately insert plausible bugs to prove the suite notices.

### 4. Green totals combined incompatible claims

One generated suite reported 143 passing segments. Those segments began from prepared checkpoints and included commands expected to be rejected. In the same evidence snapshot, only 1 of 10 encounters completed five rounds strictly; repaired or checkpoint-assisted completion reached 4 of 10. Only 47 branches were proven executable while 1,349 remained manual or deferred.

Each result was useful, but together they sounded stronger than they were.

**Lesson:** report `source-reviewed`, `isolated`, `generalization`, `production-path`, `continuous`, `client`, and `performance` evidence separately. A checkpoint proves a local branch, not reachability or continued play.

### 5. The replacement rebuilt a central monolith

A cleaner typed replacement began small, then its main kernel grew to roughly 16,000 lines. Action resolution came to coordinate movement, targeting, resources, conditions, spells, reactions, and special cases. The same rule often needed parallel representations in content schema, runtime, serialization, API, and UI.

**Lesson:** shared procedures own common PF2e semantics; specialized abilities live in bounded modules; the API and UI do not reimplement rules. If ordinary content needs special changes across layers, stop and repair the boundary.

### 6. The interaction protocol created much of the performance problem

A measured dragon Stride took about 0.375 seconds of server work but returned 11.2 MB: 734 choices, 742 movement candidates, and 735 continuations. Returning the full state and possible future after each command made both server and client do unnecessary work.

**Lesson:** ask for the player’s intent, query only the next decision, validate submitted paths, and return compact changes. Full state, detailed inspection, and traces remain explicit tools rather than default payloads.

### 7. Evidence production became a second product

Artifacts accounted for about 97% of tracked bytes, including 41 full tracking snapshots. Hundreds of commit subjects recorded or refreshed process evidence. Agents spent substantial effort repairing currentness and reconciling reports without improving what a player could complete.

**Lesson:** keep tests, compact fixtures, a capability registry, and one current dashboard in Git. Let traces, profiles, videos, and generated reports expire in CI storage. Recompute acceptance from the integrated code instead of maintaining parallel narrative scoreboards.

### 8. The rules oracle was not independent enough

Many source records lacked a fixed printing, errata cutoff, and reviewed interpretation. Expected results were commonly maintained beside the implementation, so tests could preserve the same misunderstanding as the code.

**Lesson:** freeze a rules profile, write expected behavior before implementation, separate verifier and implementer, and reserve human review for ambiguous rules and public support claims.

## What should be preserved

The predecessor produced valuable techniques and cases:

- typed commands, stable identifiers, revisions, and meaningful events;
- injected deterministic rolls and replayable choices;
- explicit unsupported diagnostics and rejected-command atomicity;
- difficult reaction, timing, rollback, and negative-legality cases;
- measured profiling work and recognition that strict, repaired, and blocked evidence differ.

These are evidence to audit, not code to trust automatically. Port a small pure procedure or rule case only after checking its source, expected outcome, dependencies, and performance in the successor. Do not import the old runtime, compiler, schemas, compatibility layers, or trackers.

## How the successor responds

The [product charter](../design/00-product-charter.md) makes rules fidelity, continuous play, and responsiveness separate required gates. [Rules and content](../design/01-rules-and-content.md) defines strict sourcing and the data/module boundary. [Engine and interfaces](../design/02-engine-and-interfaces.md) narrows state and command responsibilities. [Verification](../design/03-verification-strategy.md) prevents example overfitting. [Performance](../design/04-performance-and-observability.md) keeps introspection off the normal path. The [roadmap](../design/07-roadmap.md) starts with one complete product slice and widens only after it survives unrelated adopters.
