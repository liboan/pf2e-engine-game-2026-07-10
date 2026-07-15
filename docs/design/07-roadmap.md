# Successor roadmap

**Status:** Proposed implementation sequence  
**Audience:** Product owner, rules reviewers, technical leads, and implementers  
**Read this when:** Choosing the next package or deciding whether a milestone may advance

## Start with one end-to-end walking skeleton

The first implementation milestone is one deliberately small encounter that runs through the entire real product path:

```text
source-backed definition -> minimal compiler -> engine -> save/resume
-> public API -> headless client -> inspectors and benchmarks -> encounter conclusion
```

Use authentic definitions under the selected rules profile. The slice needs only initiative, the three-action economy, Step or Stride, Strike, multiple attack penalty, typed damage, Hit Points, and defeat. Actors occupy one cell. The map distinguishes only clear and blocked cells, tests adjacency, and validates a basic submitted path; it has no larger footprints, reach, terrain costs, area shapes, or obstacle objects. Deterministic rolls and choices make it replayable. A minimal command-line or plain web client is enough, but it must use the same API intended for later play.

The skeleton also includes revisions, distinct `rejected` and `unsupported` results, atomic state changes, one intentional committed suspension saved and restored before continuation, focused inspection, and latency and payload measurement. Unknown required behavior blocks launch. It does not include a broad catalog, general expression language, specialized ability framework, polished UI, or compatibility with the predecessor.

Its purpose is to expose bad boundaries early. It is not yet a broad support claim: the first implementation may merge as experimental, then earns support only after unrelated adopters and independent verification.

The rationale for this order comes from [predecessor lessons](../lessons/predecessor.md). Product, rules, engine, proof, and performance contracts are in [00](00-product-charter.md), [01](01-rules-and-content.md), [02](02-engine-and-interfaces.md), [03](03-verification-strategy.md), and [04](04-performance-and-observability.md).

## Milestones

Milestones are dependency gates, not calendar estimates. Each milestone is implemented through the package state machine in [05-codex-delivery.md](05-codex-delivery.md).

### 1. Walking skeleton

**Build:** Approve the rules profile and a few oracle cases; create the isolated repository; choose language and package layout; implement the path above; add a benchmark harness and tiered CI.

**Exit:** One encounter starts legally and reaches its declared conclusion only through public commands. Clear, blocked, adjacent, and basic submitted-path cases behave as reviewed. Direct-engine and API results match. Rejected commands do not mutate state. Save/restore preserves the outcome. Default responses and normal commands meet provisional budgets.

**Stop or redesign:** Any predecessor runtime dependency, content-name branch, hidden state repair, full-future option enumeration, or inability to inspect exact rules state without inflating normal responses.

### 2. Prove reuse and stabilize the core

**Build:** Test the walking-skeleton capabilities against a second structurally different adopter, an interaction adopter, and a verifier-held published holdout. Harden immutable definitions versus mutable instances, ordered checks and damage, transaction boundaries, exact version/digest records, and focused state inspectors.

**Exit:** Renaming, reordering, changed speed/path length/damage, property tests, and deliberate rules mutations catch plausible overfitting. Adding already-covered content changes definitions and tests, not engine, API, or client rules. The narrow capability set may now move from `merged` to `support-accepted` at its assigned risk tier.

**Stop or redesign:** Expected results change merely to follow the code; a second adopter needs identity dispatch; one mechanic requires special cases in several layers.

### 3. Timing and lifecycle sentinel

**Build:** Add named timing moments, typed resumable frames, one reaction that interrupts and resumes movement or an action, and one effect with a turn-relative duration. Introduce a bounded rule module only when the printed behavior cannot be expressed by existing primitives. Modules are versioned with the deployed engine and use typed operations; there is no arbitrary embedded scripting.

**Exit:** Positive, negative, ordering, holdout, save-at-every-pause, and parent-revalidation cases pass. A short authentic encounter completes continuously through the public client within budgets.

**Stop or redesign:** Timing depends on registration order, a module mutates state directly, or a checkpoint substitutes for reaching the interaction legally.

### 4. Geometry and basic-save area sentinel

**Build:** Broaden the walking-skeleton geometry only as selected cases require: multi-cell footprints, obstacle geometry, reach, terrain costs, and one area shape. Add one save-based area effect using the PF2e basic-save results. Elevation and flight remain explicitly unsupported.

**Exit:** Translation, rotation where valid, size/reach changes, illegal-path cases, movement reactions, area targeting, all four basic-save degrees, and typed damage pass. The encounter completes continuously with focused queries and compact payloads.

**Stop or redesign:** The server enumerates every path or placement, map transforms alter rules unexpectedly, or speculative geometry work delays the selected flow.

### 5. First support-accepted release

**Build:** Run the ordinary combat, timing/lifecycle, and geometry/basic-save-area sentinels as one integrated portfolio. Finish the minimal player-facing flow, capability registry, exact content manifest, support exclusions, and release evidence.

**Exit:** Every declared capability and encounter passes its required independent evidence dimensions; all three encounters run from setup to conclusion; save/restore, mutation, latency, payload, and test-duration gates pass. A human plays each flow and approves the bounded product claim. Public distribution also requires license review.

**Stop:** A green focused suite conflicts with a continuous encounter, or merged packages are reported as supported before integrated acceptance.

### 6. First complex published adopter

**Build:** Select one encounter that combines accepted capabilities and adds at most one bounded specialized rule module. Hold it back from design work initially so it tests the architecture rather than teaching the implementation its answers.

**Exit:** Existing capabilities require no core, API, or client rule changes. New semantics use existing typed moments and operations. Rules, product, and performance acceptance pass.

**Redesign:** The encounter needs identity checks, unrestricted scripting, silent approximation, or parallel special cases across layers.

### 7. Controlled expansion

Add one reviewed capability slice or encounter at a time. Maintain a future integration holdout. Freeze expansion when two consecutive adopters change a supposedly stable core boundary, pull-request tests exceed the budget, unsupported branches accumulate, or latency and payload gates regress without an approved tradeoff.

## Evidence and integration rule

Every slice follows the same chain: reviewed oracle and boundary; smallest implementation; independent adversarial verification; real content through the compiler and API; affected continuous encounters; performance gates; then support acceptance.

Capability and encounter acceptance follows the independent evidence dimensions and risk obligations in [03-verification-strategy.md](03-verification-strategy.md); human review intensity follows [06-bloat-and-human-review.md](06-bloat-and-human-review.md). Continuous scenarios are selected by the integration suite from declared capability impact, plus a rotating unrelated case. Package authors cannot replace them with favorable segments, checkpoints, or edited expectations. Scenario changes receive separate review. This keeps acceptance resistant to cherry-picking while focused cases remain fast enough for diagnosis.

## Initial non-goals

- Bulk content import or an “all PF2e” claim.
- Compatibility with predecessor runtime, schema, or reports.
- A universal rules DSL, arbitrary content scripts, strategy AI, or automated GM judgment.
- Geometry beyond each milestone’s selected two-dimensional rules; elevation and flight.
- Polished art, account systems, encounter building, or broad character creation.

## Current decisions

All unresolved choices, current values, and the next gate are maintained in [STATUS.md](../../STATUS.md). Do not duplicate them in roadmap revisions.
