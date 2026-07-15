# Engine and interfaces

**Status:** Proposed architecture contract  
**Audience:** Engine, content, API, persistence, and client implementers  
**Read this when:** Adding a subsystem or deciding where rule behavior belongs

## System boundary

```text
reviewed sources + inventory -> strict compiler -> immutable definitions
                                                     |
client -> focused query -> typed command -> engine -> result + compact delta
                                           |    |
                                  rule modules  geometry
```

- The **compiler** type-checks content, resolves references, derives capability dependencies, and produces immutable definitions. It does not resolve PF2e rules.
- The **engine** owns legality, timing, rule procedures, transactions, and canonical encounter state. It knows PF2e concepts but never selects behavior by creature or encounter identity.
- **Rule modules** implement bounded exceptional behavior through a sealed interface.
- The **geometry component** answers pure spatial questions under a declared geometry capability.
- The **service API** owns encounter identity, revisions, retries, persistence, and projections. It contains no rule calculations.
- The **client** collects intent and displays choices, events, and state. It does not infer legality.

Rules and packaging are defined in [01-rules-and-content.md](01-rules-and-content.md). Evidence and budgets are defined in [03-verification-strategy.md](03-verification-strategy.md) and [04-performance-and-observability.md](04-performance-and-observability.md).

## Canonical state

Canonical encounter state contains only facts needed to continue play:

- exact rules profile, content, compiler, and module versions;
- stable instances referencing immutable definitions;
- positions, initiative, resources, active effects, and duration anchors;
- current revision and any suspended resolution stack;
- deterministic random-provider identity, version, and exact position or state.

Definitions, projections, action menus, caches, traces, and source prose are not copied into state. Every actor, item, effect, hazard, and area is a typed instance rather than a loosely shaped dictionary.

Checks and modifiers, ordered damage stages, effects and durations, targeting, movement, and resource costs are engine-owned procedures. A narrow first release may support only some variants, but it cannot replace these with content-shaped shortcuts.

## Commands and closed outcomes

A command carries intent, a unique command ID, expected revision, acting subject, and typed inputs. Clients submit choices and proposed paths, never calculated outcomes.

Every command returns exactly one public outcome:

- **Committed:** resolution completed; returns the new revision, rules events, and state delta.
- **Suspended:** a legal prefix committed and resolution now needs a typed choice, roll, or reaction; returns the new revision, committed events and delta, an opaque continuation ID, and one focused prompt.
- **Rejected:** understood but illegal, unavailable, stale, or malformed; returns the unchanged revision and a stable reason code.
- **Unsupported:** the requested semantics are outside the loaded support boundary; returns the unchanged revision and missing capability details.

Rejected and unsupported commands never mutate state. Suspension is different: PF2e may spend a cost or complete movement before a reaction or later choice. Those completed steps are canonical, the revision advances, and a typed resolution frame records only what remains. The client must not treat suspension as rollback.

An invariant violation is not a fifth rules outcome. The service publishes nothing, records a diagnostic, and marks the encounter for investigation.

Each dispatch is transactional between commit points: it publishes its whole journal and suspended frame or nothing. Mandatory unsupported content is caught at load; finding it after a committed prefix is an invariant failure.

A continuation response supplies a new command ID, expected revision, continuation ID, and only the requested input. Continuations are revision-bound, one-use, and validated against the stored frame. Save/restore preserves them exactly.

## Randomness

The engine issues typed random requests with request ID, rules purpose such as attack check, save, damage, or flat check, dice expression, and frame reference. Provider consumption is journaled: it advances only when outcome and receipt commit. Rejection or invariant abort consumes nothing; suspension commits only draws in its committed prefix. Tests may supply exact typed results. Save/restore preserves provider identity and position; receipt-based retry never draws again.

## Resolution frames and timing

A resolution frame names its procedure and version, source and targets, current step, completed commit points, remaining typed plan, consulted inputs, and parent frame. Frames contain no executable closures or unrestricted module state, so they serialize deterministically.

Rules expose named moments such as action proposed, movement segment entered, check result proposed, damage about to apply, effect expiring, and turn ending. Each moment defines allowed contributions and ordering. Registration order and string matching never decide PF2e timing.

After a child frame resolves, its parent revalidates assumptions that could have changed: target availability, position, reach, remaining movement, resources, and cancellation state.

## Rule-module contract

A module receives a read-only rules view, a typed moment, and its versioned configuration. At the broadest level, module results fall into a sealed set:

- `Pass` — no contribution;
- `Contribute` — typed constraints, modifiers, degree adjustments, damage adjustments, or trigger declarations;
- `Invoke` — a typed engine plan for a check, damage, movement, effect, or resource procedure;
- `Suspend` — a typed prompt plus serializable continuation data;
- `Cancel` — a source-backed cancellation of the current procedure.

Each named moment exposes its own closed subset. Modifier collection accepts only typed modifiers or `Pass`; damage mitigation accepts only its defined adjustments; cancellation exists only where the reviewed procedure permits it. Results are not state patches: the engine validates and commits them. Adding a result or operation is a shared-contract change requiring unrelated adopters and independent review.

Modules receive opaque instance references plus typed facts such as traits, size, position, and resources. They may carry a reference into an operation or compare references for a rule relationship such as source equals target. They cannot inspect names or raw IDs, or select behavior because a particular instance or definition ID matches. They also cannot mutate state, choose randomness, read files or networks, or use wall-clock time.

Initial modules are trusted first-party code compiled into the service and selected from a fixed registry; there is no runtime loading or uploaded code. Each declares exact moment and capability dependencies and receives only those typed interfaces. The build compares linked capability symbols with the declaration; registration and contract tests reject unavailable dependencies or disallowed results.

## Reaction resolution

The engine, not individual reaction modules, owns this algorithm:

1. Enter a named trigger moment with its cause, subjects, current commit boundary, and stable window ID.
2. Ask registered modules for typed trigger declarations; validate current eligibility and reaction resources.
3. Give every offer a stable ID derived from its window, trigger, reacting instance, and module; order eligible offers using the rules profile's timing and tie policy. If a player or GM must choose, suspend with one focused prompt.
4. Record pass or selection against that window so the same offer is not repeated. On selection, resolve the reaction as a child frame and spend its resource at the source-defined commit point.
5. Resolve any nested windows in stack order, then commit the child result.
6. Recompute eligibility from canonical state and revalidate the parent after every child.
7. Resume, modify, or cancel the parent; close the moment when no eligible offer remains.

The profile must define simultaneous-trigger ordering and when choice belongs to a player or GM. Module registration order is never a fallback. The engine tracks a signature of parent step, window kind, rules-relevant state, and ordered eligible offer IDs. Repeating a signature, reusing an offer ID inconsistently, or exceeding the reviewed nesting bound is an engine invariant failure: abort the current dispatch without publishing its journal and surface a diagnostic. Never skip a legal reaction or break a loop silently. This algorithm is tested at every suspension and restoration boundary.

## Geometry boundary

The walking skeleton supports only a 2D square grid, single-cell actors, clear or blocked cells, adjacency, and basic submitted paths. Pure operations answer cell passability, adjacency, and the first invalid path segment. The service validates a submitted path; it never enumerates every path.

Multi-cell footprints, obstacle objects or edges, reach beyond adjacency, terrain costs, areas, line or cover, elevation, and other movement modes enter later semantic-stress slices one reviewed capability at a time. Content needing any absent geometry fails closed. Coordinates and geometry-capability IDs remain canonical data.

## Public API and persistence

Commands use an envelope like `{encounter_id, command_id, expected_revision, kind, input}`. The service computes a canonical `request_digest`. It atomically persists `command_id`, `request_digest`, the complete outcome receipt, and the resulting revision with any state and provider changes. The same ID and digest returns that receipt; the same ID with another digest is rejected. Rejected and unsupported outcomes also retain a receipt against the unchanged revision.

Queries are non-mutating and intent-specific: current actor actions, targets for one selected action, validation of one placement or path, current prompt, changes since a revision, or an explicit full snapshot. Large results are bounded and paginated. Normal replies contain IDs, changed fields, and relevant events—not repeated definitions, full history, or future command trees.

Snapshots record encounter and lineage IDs, snapshot ID, revision, receipt boundary, provider identity and position, canonical state, and exact profile, content, compiler, module, and serialization versions. Same-identity crash recovery restores state, provider, and receipts to one durable point; arbitrary rewind under that identity is forbidden. Loading an old snapshot for new play creates a new encounter identity linked to the source snapshot, so old command IDs cannot collide. Identity or digest mismatch fails closed. Direct-engine and API execution of the same command stream must produce the same rules-relevant fingerprint and events.
