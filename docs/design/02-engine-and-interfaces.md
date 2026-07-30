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

- The **compiler** type-checks content, resolves references, derives dependencies, and emits immutable definitions. It does not resolve PF2e rules.
- The **engine** owns legality, timing, rule procedures, transactions, and canonical encounter state. It knows PF2e concepts but never selects behavior by creature or encounter identity.
- **Rule modules** implement bounded exceptional behavior through a sealed interface.
- The **geometry component** answers pure spatial questions under a declared geometry capability.
- The **service API** owns encounter identity, revisions, retries, persistence, and projections. It contains no rule calculations.
- The **client** collects intent and displays choices, events, and state. It does not infer legality.

Rules and packaging: [01](01-rules-and-content.md). Evidence: [03](03-verification-strategy.md). Budgets: [04](04-performance-and-observability.md).

## Canonical state

Canonical state stores only facts needed to continue play:

- exact rules profile, content, compiler, and module versions;
- stable instances referencing immutable definitions;
- positions, initiative, typed grants and claims, committed receipts, active effects, and duration anchors;
- current revision and any suspended resolution stack;
- deterministic random-provider identity, version, and exact position or state.

Definitions, projections, menus, caches, traces, and source prose are not copied into state. Actors, items, effects, hazards, and areas are typed instances, not loose dictionaries.

Checks, damage, health, targeting, movement, costs, and other universal rules are versioned staged engine procedures. The DSL can invoke them but cannot define accounting, stage order, commits, or mutation. Stride, Step, and Strike are core code; content supplies immutable profiles, never replacement semantics.

## Commands and closed outcomes

A command carries intent, unique ID, expected revision, acting subject, and typed inputs. Clients submit choices and paths, never outcomes.

Every command returns exactly one public outcome:

- **Committed:** resolution completed; returns the new revision, rules events, and state delta.
- **Suspended:** a legal prefix committed and needs a typed choice, roll, or reaction; returns its revision, events, delta, continuation ID, and one prompt.
- **Rejected:** understood but illegal, unavailable, stale, or malformed; returns the unchanged revision and a stable reason code.
- **Unsupported:** the requested semantics are outside the loaded support boundary; returns the unchanged revision and missing capability details.

Rejected and unsupported commands never mutate state. Suspension may follow a spent cost or completed movement. That prefix is canonical, the revision advances, and a typed frame records only the remainder; suspension is not rollback.

An invariant violation is not a fifth outcome. The service publishes nothing, records a diagnostic, and marks the encounter for investigation.

Between commit points, a dispatch publishes its whole journal and suspended frame or nothing. Mandatory unsupported content is caught at load; finding it after a committed prefix is an invariant failure.

A continuation supplies a new command ID, expected revision, continuation ID, and requested input. It is revision-bound, one-use, frame-validated, and preserved exactly by save/restore.

## Randomness

The engine issues typed random requests with ID, purpose, dice expression, and frame. The provider advances only with a committed outcome and receipt. Rejection or invariant abort consumes nothing; suspension consumes only committed-prefix draws. Tests may supply typed results. Save/restore preserves provider identity and position; receipt retry never redraws.

## Resolution frames and timing

A resolution frame names its procedure and version, source and targets, current step, completed commit points, remaining typed plan, consulted inputs, and parent frame. Frames contain no executable closures or unrestricted module state, so they serialize deterministically.

### `MomentSpec` contract

A `MomentSpec` is an engine-owned, named, versioned, reaction-neutral phase contract. It declares one closed immutable input type, its allowed output union and callable engine operations, deterministic ordering, and whether its facts are provisional or committed. Provisional facts are projections: evaluation cannot publish them. The engine validates outputs and publishes only at the spec's commit point. When a child may intervene, the spec also names the parent facts and cancellation status that the parent must re-read after the child commits, plus the closed revalidation outcomes allowed before continuing; revalidation never rolls back a committed child. Trigger discovery is one consumer. Examples include action proposed, movement segment entered, check result proposed, damage pending, effect expiring, and turn ending. Registration order and string matching never decide timing.

## Rule-module contract

A module receives a read-only rules view, a typed moment, and its versioned configuration. At the broadest level, module results fall into a sealed set:

- `Pass` — no contribution;
- `Contribute` — typed constraints, modifiers, degree adjustments, damage adjustments, or trigger declarations;
- `Invoke` — a typed engine plan for a check, damage, movement, effect, or resource procedure;
- `Suspend` — a typed prompt plus serializable continuation data;
- `Cancel` — a source-backed cancellation of the current procedure.

Each named moment exposes its own closed subset. Modifier collection accepts only typed modifiers or `Pass`; damage mitigation accepts only its defined adjustments; cancellation exists only where the reviewed procedure permits it. Results are not state patches: the engine validates and commits them. Adding a result or operation is a shared-contract change requiring unrelated adopters and independent review.

Modules receive opaque instance references plus typed facts such as traits, size, position, and resources. They may carry a reference into an operation or compare references for a rule relationship such as source equals target. They cannot inspect names or raw IDs, or select behavior because a particular instance or definition ID matches. They also cannot mutate state, choose randomness, read files or networks, or use wall-clock time.

Initial modules are trusted first-party code outside the core engine and injected from a fixed build registry; there is no runtime loading or uploaded code. An external versioned descriptor binds the exact module artifact digest to reviewed authority and its allowed engine interface. Checks reject undeclared imports, dependencies, symbols, moments, semantic keys, or results. Descriptor and acyclic evidence details are in [Content format and rule-module detail](details/content-format-and-rule-modules.md#module-authority-descriptor-and-evaluation).

## Reaction resolution

Trigger windows consume `MomentSpec` inputs; they never define moments. The engine, not modules, owns stable offers, ordering, action accounting, child frames, and parent revalidation. Reactions and triggered free actions share the mechanism but retain typed action kinds. Each offer declares resource claims and a per-creature response claim: triggered free actions spend no standard reaction, while either kind consumes the right to one response to that trigger.

Every choice or pass commits a serializable decision scope, and every selected child resolves on the stored frame stack. A committed child is never rolled back; the parent recomputes eligibility and receives only a closed revalidation result. Profile policies own simultaneous ordering, choice ownership, same-trigger equivalence, and the reviewed nesting bound. Registration order is never a fallback. Repeated cycle signatures, inconsistent offer reuse, or an exceeded bound abort only the unpublished journal of the current dispatch and never revert an earlier published prefix.

The fixed offer, accounting, frame, ordering, and verification shapes are in [Reaction resolution detail](details/reaction-resolution.md), which separates approved architecture direction from PF2e timing questions marked **UNSETTLED—HUMAN REVIEW REQUIRED**.

## Geometry boundary

The walking skeleton supports only a 2D square grid, single-cell actors, clear or blocked cells, adjacency, and basic submitted paths. Pure operations answer cell passability, adjacency, and the first invalid path segment. The service validates a submitted path; it never enumerates every path.

Multi-cell footprints, obstacle objects or edges, reach beyond adjacency, terrain costs, areas, line or cover, elevation, and other movement modes enter later semantic-stress slices one reviewed capability at a time. Content needing any absent geometry fails closed. Coordinates and geometry-capability IDs remain canonical data.

## Public API and persistence

Commands use an envelope like `{encounter_id, command_id, expected_revision, kind, input}`. The service computes a canonical `request_digest`. It atomically persists `command_id`, `request_digest`, the complete outcome receipt, and the resulting revision with any state and provider changes. The same ID and digest returns that receipt; the same ID with another digest is rejected. Rejected and unsupported outcomes also retain a receipt against the unchanged revision.

Queries are non-mutating and intent-specific: current actor actions, targets for one selected action, validation of one placement or path, current prompt, changes since a revision, or an explicit full snapshot. Large results are bounded and paginated. Normal replies contain IDs, changed fields, and relevant events—not repeated definitions, full history, or future command trees.

Snapshots record encounter and lineage IDs, snapshot ID, revision, receipt boundary, provider identity and position, canonical state, and exact profile, content, compiler, module, and serialization versions. Same-identity crash recovery restores state, provider, and receipts to one durable point; arbitrary rewind under that identity is forbidden. Loading an old snapshot for new play creates a new encounter identity linked to the source snapshot, so old command IDs cannot collide. Identity or digest mismatch fails closed. Direct-engine and API execution of the same command stream must produce the same rules-relevant fingerprint and events.
