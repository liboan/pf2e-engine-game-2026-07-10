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

Use authentic definitions under the selected rules profile. The slice needs only initiative, the three-action economy, Step or Stride, Strike, multiple attack penalty, typed damage, Hit Points, and defeat. PC-category actors use dying/wounded rules; ordinary creatures are defeated at 0 HP; significant-NPC exceptions are unsupported. Its scene binds immutable topology bytes by digest. The general spatial contract does not assume one-cell, land-only, flat-world play, but this first capability supports only one-cell actors, clear or blocked cells, adjacency, and submitted paths including reviewed diagonal accounting whose turn-scoped state survives save/resume. Other variants fail closed. A minimal client uses the production API; deterministic rolls and choices make the flow replayable.

The skeleton also includes revisions, distinct `rejected` and `unsupported` results, atomic state changes, one intentional committed suspension saved and restored before continuation, focused inspection, and latency and payload measurement. Unknown required behavior blocks launch. It does not include a broad catalog, general expression language, specialized ability framework, polished UI, or compatibility with the predecessor.

Its purpose is to expose bad boundaries early. It is not yet a broad support claim: the first implementation may merge as experimental, then earns support only after unrelated adopters and independent verification.

The rationale for this order comes from [predecessor lessons](../lessons/predecessor.md). Product, rules, engine, proof, and performance contracts are in [00](00-product-charter.md), [01](01-rules-and-content.md), [02](02-engine-and-interfaces.md), [03](03-verification-strategy.md), and [04](04-performance-and-observability.md).

## Milestones

Milestones are dependency gates, not calendar estimates. Each milestone is implemented through the package state machine in [05-codex-delivery.md](05-codex-delivery.md).

### 0. Foundational rules contracts

**Design:** Specify the approved foundations before runtime work: a transitive semantic-closure graph; typed grants, claims, and commit receipts; a shared frame/choice/revalidation protocol used by separate engine-owned staged procedures; and immutable scene plus spatial/information boundaries. Define only the walking-skeleton variants of action accounting, checks/degrees, damage/healing, health transition, and scene identity. Design the broader spatial interface now, but do not implement unsupported geometry.

**Exit:** Stress probes S01–S06 in the [rules/design review](details/rules-design-stress-test.md#appendix-a-reproducible-scenario-index) trace unambiguously through compilation, canonical state, frames, save/retry, API projection, and evidence. The DSL supplies data and invokes registered procedures; it does not define stage order, accounting, geometry algorithms, or mutation. Modules remain bounded contributors at named moments.

**Stop or redesign:** A generic rule interpreter, arbitrary resource map, identity dispatch, module-owned transaction, or content-authored phase order is required.

### 1. Walking skeleton

**Build:** Approve the rules profile and selected oracle cases; implement the approved v1 contracts through the path above; add a local benchmark and evidence harness.

**Exit:** One encounter starts legally and reaches its declared conclusion only through public commands. Clear, blocked, adjacent, and basic submitted-path cases behave as reviewed. Direct-engine and API results match. Rejected commands do not mutate state. Save/restore preserves the outcome. Default responses and normal commands meet provisional budgets.

**Stop or redesign:** Any predecessor runtime dependency, content-name branch, hidden state repair, full-future option enumeration, or inability to inspect exact rules state without inflating normal responses.

### 2. Prove reuse and stabilize the core

**Build:** Test the walking-skeleton capabilities against a second structurally different adopter, an interaction adopter, and a verifier-held published holdout. Harden immutable definitions versus mutable instances, the approved staged procedures and transaction boundaries, exact version/digest records, and focused state inspectors.

**Exit:** Renaming, reordering, changed speed/path length/damage, property tests, and deliberate rules mutations catch plausible overfitting. Adding already-covered content changes definitions and tests, not engine, API, or client rules. The narrow capability set may now move from `merged` to `support-accepted` at its assigned risk tier.

**Stop or redesign:** Expected results change merely to follow the code; a second adopter needs identity dispatch; one mechanic requires special cases in several layers.

### 3. Timing and lifecycle sentinel

**Build:** Extend the v1 health transition into the approved effect/turn lifecycle schedule. Add one reaction that interrupts and resumes movement or an action, resolving the unsettled reaction oracles it requires. Introduce a bounded rule module only when printed behavior cannot use existing primitives.

**Exit:** Positive, negative, ordering, holdout, save-at-every-pause, and parent-revalidation cases pass. A short authentic encounter completes continuously through the public client within budgets.

**Stop or redesign:** Timing depends on registration order, a module mutates state directly, or a checkpoint substitutes for reaching the interaction legally.

### 4. Geometry and basic-save area sentinel

**Build:** Activate selected parts of the predesigned spatial contract: multi-cell footprints, obstacle geometry, reach, terrain costs, and one area shape. Add viewer-safe target projection and the fixed area dependency order before one save-based area effect. Elevation and flight remain unsupported.

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
- Runtime support for geometry beyond each milestone’s selected rules; elevation and flight remain unimplemented until explicitly selected.
- Polished art, account systems, encounter building, or broad character creation.

## Current decisions

All unresolved choices, current values, and the next gate are maintained in [STATUS.md](../../STATUS.md). Do not duplicate them in roadmap revisions.
