# Rules and content strategy

**Status:** Proposed design  
**Audience:** Rules reviewers, content authors, and engine implementers  
**Read this when:** Adding a rules capability or published content

## Purpose

The simulator claims fidelity only against a frozen rules profile and a reviewed inventory of what each rules subject requires. Universal procedures are typed engine behavior; common printed content composes them through a small data format, while bounded printed exceptions use restricted typed modules. Content loads as playable only when every mandatory rule clause is accounted for.

The product promise is in [00-product-charter.md](00-product-charter.md); execution boundaries are in [02-engine-and-interfaces.md](02-engine-and-interfaces.md); evidence obligations are in [03-verification-strategy.md](03-verification-strategy.md). Canonical record routes and vocabularies are in the [project registry](../../registry/README.md).

## Rules-profile gate

Archives of Nethys (AoN) is the sole working rules authority for this private tool. The initial profile uses AoN as retrieved through **2026-07-10**. It does not reconcile AoN against PDFs, printings, or a separate Paizo errata stream.

The initial Remaster content allowlist is:

- [*Player Core* — AoN source 216](https://2e.aonprd.com/Sources.aspx?ID=216)
- [*Player Core 2* — AoN source 227](https://2e.aonprd.com/Sources.aspx?ID=227)
- [*Monster Core* — AoN source 221](https://2e.aonprd.com/Sources.aspx?ID=221)
- [*NPC Core* — AoN source 236](https://2e.aonprd.com/Sources.aspx?ID=236)

This allowlist controls imported player, creature, item, spell, feat, and similar content. Core encounter procedures may be sourced from other AoN pages when they are required to execute allowlisted content. Record each such dependency, but do not treat this as permission for a bulk *GM Core* or general-catalog import.

Legacy rules and content are outside the initial profile and are never mixed into it as silent fallbacks. Adding them is outside this design and requires a new human source-policy decision.

No definition is supported and no core procedure enters production before exact profile approval. Candidate rules code may proceed only with explicit unresolved assumptions.

The approved immutable profile record contains:

- profile ID and effective date;
- AoN authority and retrieval cutoff;
- allowlisted AoN source IDs and URLs;
- every required core-procedure AoN page outside that allowlist;
- treatment of legacy and optional material;
- project interpretations for known ambiguities;
- private-use boundary;
- approval entry ID.

Accepted profile bytes are immutable and always referenced by exact ID and digest. A candidate correction replaces the candidate record; correcting an accepted record requires an explicitly reviewed replacement. Nothing silently mutates or follows later AoN changes. Any future source-policy change is outside this design and requires a new human decision.

Foundry PF2e data is an optional engineering cross-check for identifiers, structure, or coverage. It is neither required nor rules authority and cannot change an AoN result.

## Ambiguity and GM judgment

The product owner is the final authority for genuinely ambiguous rule interpretations. An agent may propose an interpretation and may implement it before that decision only as a visible provisional or configurable choice. The source record, oracle, runtime result, and evidence must preserve the ambiguity and selected policy; provisional behavior cannot become supported merely because its tests pass.

When a rule explicitly gives the GM a bounded mechanical choice, the simulator may expose named, versioned policies. The selected policy is stored with the encounter and evidence so replay does not depend on an agent's hidden judgment.

When resolution depends on unbounded narrative judgment, the engine either suspends for an explicit ruling that can be represented safely or reports the behavior as unsupported. It does not invent a ruling invisibly.

## Source records

Every executable definition, engine-owned core procedure, fixed rule module, and reusable capability support claim points to a compact source record. It stores facts needed to reproduce a decision:

- rules profile and stable record ID;
- exact AoN URL, page title or kind, and numeric AoN ID when available;
- retrieval date and profile cutoff;
- concise normalized rule facts and ordering;
- ambiguity or exclusion notes;
- digest of the normalized facts;
- approval entry ID and record digest.

Quote only the minimum text necessary to resolve ambiguity. Do not store research transcripts or copied source pages. AoN controls rules truth for this profile; do not add PDF, printing, or separate errata reconciliation fields. Any future distribution remains a separate licensing and attribution decision.

## Independent behavior inventories

See [Behavior inventory contract](details/behavior-inventories.md) for the fixed record shape, reconciliation algorithm, and immutability rules; this companion is subordinate to this section and approves no profile, inventory, oracle, or support claim.

A content package cannot certify itself by listing only the capabilities its implementation happens to use.

Before implementation, a rules reader creates a **behavior inventory** from the source record. Each material clause receives exactly one disposition:

- `mapped` — implemented by an exact core-procedure or fixed-module semantic node;
- `non-executable` — presentation text with no rules behavior;
- `excluded` — deliberately outside the supported use and made mechanically unavailable; or
- `unsupported` — required behavior is missing, which blocks playable status.

Definitions are graph roots whose clauses map to exact core-procedure or fixed-module semantic nodes. Each node exposes versioned semantic keys and typed dependency edges; closure traverses the exact acyclic graph to source-reviewed leaves. Capabilities describe support over closed graphs and are never runtime dispatch objects. Neither path accepts authored `requires`.

Inventory and its implementation have separate digests and approval entries. A compiler or model may suggest an inventory, but cannot approve the inventory it will later satisfy.

An inventory is **closed** only when every source clause has one disposition, every `mapped` clause reconciles, every `excluded` clause is enforced and disclosed, and no clause is `unsupported`. “The scripted encounter never chooses it” is not an exclusion.

## Definitions, instances, and packages

See [Definitions, instances, and packages](details/definitions-instances-packages.md) for the package, loading, and save-reference contract; this companion is subordinate to this section and its source-grounded examples remain candidate-only.

A **definition** is immutable content such as an attack profile, spell, feat, creature, hazard, item, or module configuration. An **instance** is mutable encounter state such as current HP, position, resources, conditions, and ownership. Test fixtures may create and place instances; they may not redefine rule meaning.

Ship definitions in small versioned packages containing:

- rules-profile, source-record, and inventory digests;
- immutable definition IDs and content digests;
- compiler-derived semantic-node dependencies;
- registered module IDs, versions, and digests;
- definition lifecycle and allowed use cases.

Every executable definition has one lifecycle: `candidate`, `supported`, or `retired`. A `candidate` may run only in verification. Production loads only `supported` definitions with closed inventories. A `retired` definition cannot start or join production play; saved-game handling requires an explicit migration. Packages bind exact prerequisite-approval IDs and digests rather than copying reviewer names and dates into every definition; promotion approval remains an external registry join to the integrated package digest.

At load time, verify schema and profile compatibility, exact references, module availability, inventory closure, definition lifecycle, and definition digests. Any `unsupported` clause or non-`supported` definition blocks production launch with a precise report.

## Small data format and typed modules

See [Content format and rule-module detail](details/content-format-and-rule-modules.md) for the proposed closed YAML, compiler, fixed-registry, and typed-module shapes; this section remains authoritative and the companion approves no operation, module, definition, or support claim.

The declarative format is deliberately closed. It may compose engine-owned operations for:

- action and resource costs;
- typed targets, areas, and movement requests;
- checks, DCs, degree adjustments, and outcome tables;
- typed damage and healing;
- conditions and effects with explicit duration anchors;
- calls to registered modules.

The compiler parses, type-checks, resolves references, and emits compact immutable definitions. It does not implement PF2e procedures, accept arbitrary callbacks, or grow loops and unrestricted mutation.

Stride, Step, Strike, and other universal rules procedures are typed, engine-owned core procedures. They are neither DSL-authored definitions nor typed rule modules. Content may supply immutable profiles or configuration, and a closed plan may invoke a fixed compiler-known core-procedure symbol such as `core.stride@1`; content cannot define, override, or replace that symbol's semantics.

Bounded printed exceptions that do not fit cleanly become source-cited typed rule modules written in normal code. A module observes named engine moments and returns only the closed result types defined in [02-engine-and-interfaces.md](02-engine-and-interfaces.md). It cannot mutate state directly, select randomness, access files or networks, use wall-clock time, or select behavior by inspecting a name or raw identifier.

A unique ability may remain unique. Generalize only after unrelated printed consumers demonstrate the same rule concept. Similar wording is not enough.

## Adoption sequence

Adopt one capability-sized slice at a time:

1. Approve its source record, interpretation, behavior inventory, and risk tier.
2. Select unlike published adopters and any required independent holdout.
3. Implement the smallest primitive, declarative construct, or typed module.
4. Reconcile the subject-specific implementation manifest with the inventory.
5. Pass the required conformance, transformation, save/resume, continuous-play, and performance evidence.
6. Move only the proven definition use cases from `candidate` to `supported`; retain explicit `excluded` clauses.

Do not bulk-import the PF2e catalog. Content that uses only supported capabilities should add data and evidence, not core branches. If a second adopter needs another identity check or cross-layer special case, stop and revise the abstraction.
