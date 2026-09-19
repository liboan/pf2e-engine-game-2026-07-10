# Performance and observability

**Status:** Proposed design  
**Audience:** Engine, API, client, test, and performance implementers  
**Read this when:** Designing command results, inspection, tracing, benchmarks, or performance gates

## Principle

Performance is part of playability, not cleanup after rules work. Normal play should validate one intent, commit the resulting changes, and return the next decision. Deep inspection remains available on demand so tests can prove rules behavior without making every command serialize full state, all options, or an unbounded trace.

The command and state contracts are in [02-engine-and-interfaces.md](02-engine-and-interfaces.md). [03-verification-strategy.md](03-verification-strategy.md) defines which operational evidence each risk tier requires.

## Provisional budgets and calibration gate

The walking skeleton must select a pinned reference machine, runtime/build mode, and benchmark corpus. It then ratifies or tightens these provisional gates before sentinel implementation:

| Surface | Provisional gate |
| --- | --- |
| Ordinary in-process command | p95 under 50 ms |
| Stress-sentinel in-process command | p95 under 100 ms |
| Ordinary local API command | p95 under 100 ms |
| Stress-sentinel local API command | p95 under 250 ms |
| Focused option, target, or path query | p95 under 150 ms |
| Create or load a sentinel from compiled content | p95 under 500 ms |
| Save, restore, and resume to the next decision | p95 under 750 ms |
| Headless input-to-next-decision flow | ordinary p95 under 250 ms; stress p95 under 500 ms |
| Default command response | p95 under 100 KB; none above 250 KB |
| Retained memory | under 10 MB growth after 1,000 replayed commands, excluding retained audit artifacts |
| Developer fast suite | under 30 seconds |
| Pull-request suite | under 5 minutes on its declared runner |

Report median, p95, maximum, sample count, serialized bytes, allocations where available, and retained memory. Cold compile/load is measured separately from warm commands. Instrumented and uninstrumented modes are separate results.

The headless player-flow timer starts when a chosen input is submitted and ends when the next renderable view or prompt is available; it includes the command, required projection, and at most one immediate focused query. The save/restore flow includes serialization, a fresh load, continuation validation, and resolution to the next decision.

After calibration, a budget change requires a short decision packet with user impact and before/after measurements, followed by an explicit registry approval entry. A milestone cannot waive a failure in its summary. The still-unresolved reference-machine choice belongs in [the project status](../../STATUS.md), not in competing benchmark documents.

## Keep commands and queries narrow

A command should:

1. validate revision, identity, and supplied input;
2. resolve until completion or one required suspension;
3. atomically publish its journal;
4. return outcome, revision, relevant events, compact state delta, and at most one immediate prompt.

It does not rebuild a full player view, enumerate legal futures, generate all paths or target combinations, or attach full history.

Queries are focused after intent: available action families for one actor, targets for one selected action, validation of one submitted path or placement, or the current prompt. A player view is fetched initially and then updated by revision deltas. Revision divergence triggers an explicit resynchronization snapshot. Large focused results use limits and cursors.

## Make state changes cheap

Load immutable definitions once and share them. Encounter state stores mutable instances and definition references, not authored descriptions, option catalogs, source metadata, or previous projections.

Execute a command with a transaction journal or copy-on-write draft. Accepted operations directly produce the response delta; do not deep-copy and diff full snapshots. Rejection discards the draft. A suspended result publishes only its committed prefix and compact frame. Occasional saves are deliberate snapshots, not a snapshot per step.

Derived action menus, reachability, projections, and target sets stay outside authoritative state. Add a cache only after a profile identifies repeated work. Cache keys include encounter revision, profile/content/module versions, query kind, and inputs. Cold and warm answers must be semantically identical; tests cover invalidation after every relevant mutation.

Keep long history in an append-only audit sink with retention limits. Active state contains only events and facts needed to continue play.

## On-demand inspection

The engine exposes pure, read-only inspectors for rules-relevant slices:

- selected actor resources, conditions, position, and equipment;
- effects matching subject, source, duration anchor, or capability;
- resolution frames, pending prompts, reaction offers, and committed steps;
- events and changed records for one command;
- a canonical fingerprint of selected or complete rules-relevant state.

Inspectors cannot resolve, mutate, repair, or advance time. Tests request only fields needed by the reviewed expected case. Fingerprints support determinism, rejection atomicity, direct/API equivalence, retry safety, and save/restore checks without embedding a large golden snapshot. Full-state fingerprints are computed only when requested, not on every gameplay command.

Debug endpoints may expose the same inspectors with explicit field selection, size limits, and pagination. Bulky maps, traces, profiles, and histories are separate resources identified by ID.

## Metrics and traces

**Always-on metrics** use low-cardinality counters and timers at stable boundaries: validation, rule resolution, suspension, transaction commit, geometry, projection, option query, serialization, cache hit/miss, event count, changed-record count, and response bytes. Never label them with actor, encounter, or command IDs. Their overhead must remain below 2% on the benchmark corpus.

**Diagnostic traces** are opt-in for one encounter and bounded command range. A trace records a tree of typed procedure phases, capability keys, timing decisions, inputs consulted, operation proposals, commits, and durations. It has byte and depth limits plus an explicit truncation marker. Gameplay responses carry only a trace ID. Trace-mode overhead is reported separately and never used for normal performance claims.

Assertions and diagnostics are independent: turning tracing off cannot remove semantic checks, and turning it on cannot change state fingerprints or events.

## Reproducible benchmark record

Every retained result has a compact manifest containing:

- source commit and dirty-state flag;
- build mode, dependency-lock digest, runtime and OS versions;
- rules profile, compiler, content, module, and serialization digests;
- scenario, command-stream, choice-stream, and roll-stream IDs or seeds;
- random-provider ID and version, seed or supplied-result digest, and starting position;
- machine CPU and memory profile, concurrency, process isolation, warmup, and sample count;
- instrumentation mode, exact command, budgets, results, and semantic fingerprint.

The executable reports its build identity; the harness fails if it imports a different tree. Semantic fingerprints must match across repeated runs, cold/warm cache states, direct/API execution, and save/restore. Timing will vary, so comparison uses a declared sample method and noise threshold rather than identical measurements.

A retained manifest plus checked-in benchmark definitions, deterministic generators, and seeds must be sufficient to regenerate the command, choice, and roll streams after CI artifacts expire. If a stream cannot be regenerated compactly, check in the minimal input itself. An expiring trace, profile, or raw sample may help diagnosis but can never be the only evidence needed to reproduce a claim.

Profiles, raw samples, and full traces are expiring CI artifacts. Git stores benchmark definitions, the current budget file, and small reproduction manifests—not a history of generated reports.

## Benchmark corpus and optimization workflow

Keep a small corpus aligned with real rule pressure:

- ordinary Strike, MAP, and damage;
- target query among many actors;
- walking-skeleton path validation for single-cell actors, clear or blocked cells, adjacency, and basic submitted paths;
- later semantic-stress geometry for footprints, obstacles, reach, terrain, areas, and reaction triggers only after each capability enters scope;
- nested reaction suspension and resumption;
- turn-boundary processing with many effects;
- content compile/load, projection, receipt-based retry, save/restore, and continued play;
- long replay for retained-memory growth.

Performance benchmarks run in isolation. Pull requests use stable smoke samples; scheduled and release runs use the full sample plan. A scheduled failure blocks the relevant playability claim even if rule tests pass.

When a budget fails, inspect phase timings, object counts, payload composition, and retained ownership before profiling the demonstrated hotspot. Every optimization change includes isolated before/after evidence and semantic-equivalence tests. It may change representation or move expensive diagnostics off the command path; it may not weaken rules assertions or hide work in an unmeasured background path.
