# Verification strategy

**Status:** Proposed design  
**Audience:** Rules reviewers, content authors, implementers, and verifiers  
**Read this when:** Defining evidence or accepting a capability support claim

## Claim model

The engine does not claim “PF2e correctness” as one score. For a named rules profile and stated use cases, it claims that reviewed semantics are implemented, complete content runs through production boundaries, legal play reaches and composes those semantics, and the result remains reproducible and responsive.

Expected behavior is written before implementation in a reusable **rule oracle**: an approved support boundary plus source-record references and reviewed cases. Content definitions link to it rather than copying its interpretation or reviewer metadata. Engine output, prior traces, and actual-play transcripts may suggest cases but cannot certify their own correctness.

The [project registry](../../registry/README.md) routes rule oracles, inventories, support records, approvals, evidence manifests, and verifier-owned holdouts.

## Independent evidence dimensions

Each capability and encounter records a durable evidence-manifest ID for each dimension. A missing manifest means the dimension is not met. Only `generalization` may be `N/A`, with a reason:

| Dimension | What it establishes |
| --- | --- |
| `source-reviewed` | Rules profile, source records, oracle, closed behavior inventory, exclusions, and approvals are accepted. |
| `isolated` | Positive, illegal, boundary, ordering, and state-transition cases match reviewed expectations. |
| `generalization` | Unlike adopters, transformations, and any required holdout show that reusable behavior is not keyed to selected content; a truly unique ability may record `N/A`. |
| `production-path` | `supported` definitions with closed inventories run through the real compiler, engine, persistence, and public API. |
| `continuous` | The state is reached legally and play proceeds through the declared end without repair or skipped steps. |
| `client` | The player-facing client completes the supported flow and exposes the required choices clearly. |
| `performance` | Latency, payload, memory, test-time, and reproducibility gates pass. |

These are not levels and do not roll up into a percentage. A checkpoint may supply `isolated` evidence while `continuous` is absent. A replay may supply `continuous` evidence while `source-reviewed` remains absent. `generalization: N/A` does not waive interaction, production, client, or performance evidence.

The capability registry shows the exact support boundary, clause exclusions, evidence IDs, and date. A public support claim requires every dimension, with only the stated `generalization: N/A` exception. An aggregate green test count is never sufficient.

## Risk-tiered obligations

Assign risk before implementation based on rules ambiguity, semantic novelty, timing and state impact, reuse, and blast radius. The tier changes evidence depth, not dimension names or lifecycle terms. A verifier may raise it after hidden complexity appears; lowering it requires independent approval.

### Tier 1: composition of proven behavior

Use when content only combines already-supported primitives without new timing, geometry, persistence, or state semantics.

Required evidence: approved source and inventory; focused positive and illegal cases; compiler dependency reconciliation; production content/API and client execution; a relevant continuous encounter; regression and budget checks.

### Tier 2: bounded new behavior

Use for a new declarative construct, reusable module, or unique ability through stable interfaces.

Add: unlike published adopters for reusable behavior; hostile transformations; relevant property tests; a plausible mutation that the suite must catch; independent verifier review; save/restore at every new suspension; interaction coverage with an existing rule.

A unique printed ability does not need fake adopters. It needs source-backed positive, negative, edge, production-path, continuation, and encounter-interaction cases. Its generalization claim is only that the shared interfaces remain identity-independent.

### Tier 3: foundational or cross-cutting behavior

Use for command outcomes, transactions, timing, reactions, checks and degree changes, damage order, durations, geometry, persistence, the DSL/module boundary, or rules-profile changes.

Add: human approval of the rule or architecture contract; verifier-selected blind holdouts; multiple unlike interactions; mutation and generated-property suites; deterministic save/resume across every commit and suspension boundary; all affected continuous sentinels; isolated performance and memory evidence. A Tier 3 change cannot be promoted on a focused pull-request suite alone.

Human review policy and decision packets are defined in [06-bloat-and-human-review.md](06-bloat-and-human-review.md).

## Reviewed rule cases

Each case records:

- capability key, risk tier, rules profile, and source-record ID;
- supported use case and explicit exclusions;
- minimal initial state and authentic definition references;
- player choices and supplied rolls;
- expected commit or suspension boundaries, typed prompts, rules-relevant public events, and final state;
- expected reason and unchanged fingerprint for illegal or unsupported cases.

The expected-case author or rules reviewer is independent of the implementation. The implementer may challenge an expected answer with source evidence, but cannot silently edit it to pass. Material changes return to review and invalidate affected evidence.

## Test techniques

Use the smallest combination that satisfies the assigned tier.

**Exact examples** assert intermediate timing, costs, prompts, events, and selected final state—not only HP or the last result.

**Hostile transformations** rename and reorder actors, targets, effects, declarations, and IDs; reuse one definition for different actors; translate or rotate valid maps; and vary one meaningful fact such as reach, size, resistance, reaction availability, or degree adjustment. Invariant changes must preserve results; semantic changes must alter them predictably.

**Properties** generate legal states and check determinism, reference integrity, atomic rejection, monotonic revisions, nonnegative resources, stable damage order, expiration, and committed-prefix behavior. Rejection and abort must not advance the random provider; receipt retry must not draw twice; save/restore must preserve provider identity and position. Geometry properties enter with each later geometry capability.

**Mutations** introduce plausible mistakes—remove MAP, ignore modifier types, reverse mitigation order, skip an expiration, reuse a spent reaction, resume from stale state, or omit a large footprint. The expected evidence must fail for the expected reason.

**Continuation matrices** exercise every response: choose, pass, invalid input, stale revision, save before response, restore and answer, retry the same command ID, and nested suspension where supported. They also distinguish same-identity crash recovery from loading a snapshot as a new encounter identity. Committed prefixes and random draws must execute exactly once.

## Encounter portfolio

The walking skeleton in [00-product-charter.md](00-product-charter.md) proves the product path with only single-cell actors, clear or blocked cells, adjacency, and basic submitted paths. The later semantic-stress portfolio adds short authentic sentinels for an interrupting reaction; a spell or duration boundary; footprints, obstacles, reach, terrain, and areas as they enter scope; a basic-save area effect; and a specialized printed ability when introduced.

Each encounter starts from a reviewed definition and legal setup. A deterministic decision script may bind IDs returned by earlier commands, but may not inspect engine-computed outcomes to choose a convenient branch. All later changes occur through public commands. Save/restore is tested for equivalence, never used to jump ahead. The run ends at its declared objective or natural conclusion.

Keep future content as an integration holdout owned by the verifier, who controls selection, expected results, access, execution, reveal, and replacement. A separate Codex thread does not provide secrecy because threads share workspaces. Keep the payload and expected answer in a verifier-only store or protected CI job; the shared registry contains only an opaque ID, owner, scope, and digest. If protected storage is unavailable, the verifier selects and evaluates the case only after the implementation commit is frozen, without first writing it to the shared workspace. The verifier returns a result and evidence digest. After reveal or failure, move the exposed case into the normal regression suite, record the reveal, and select a new independently reviewed holdout before promotion.

## Promotion workflow

1. Approve the source record, independent inventory, expected cases, supported use case, and risk tier.
2. Implement the smallest change and focused tests without redefining the expected answers.
3. Have an independent verifier run the required transformations, properties, mutations, and holdouts.
4. Reconcile the content inventory with compiler-derived dependencies.
5. Run production content through compiler, engine, API, persistence, and relevant continuous sentinels.
6. Reproduce operational evidence using [04-performance-and-observability.md](04-performance-and-observability.md).
7. Record each required evidence dimension separately, then move qualifying definitions from `candidate` to `supported`; retain `excluded` clauses.

On failure, fix the lowest broken dimension. Do not add repair checkpoints, weaken an expected answer, or relabel an unsupported clause to preserve status.
