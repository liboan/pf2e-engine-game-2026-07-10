# Project status

**Updated:** 2026-07-29
**State:** Design baseline only; implementation has not begun.

## Current values

- Accepted rules profiles: **0**
- Supported capabilities, content definitions, and encounters: **0**
- Packages in `active` or `verify`: **1** (`docs-design-deepening-v1` in `verify`)
- Packages `merged` or `support-accepted`: **0**
- Executable engine, public API, client, and benchmark baseline: **none**

## Accepted baseline

- Product: **private, single-client tool**. Public distribution and multi-client operation are outside the initial target.
- Implementation: **Python monorepo**, canonical **JSON snapshots**, and unique command/retry IDs with committed receipts. Development and validation run locally on **macOS**; GitHub Actions is outside scope.
- Rules authority: **Archives of Nethys as retrieved through 2026-07-10**. The initial Remaster content allowlist is *Player Core* (AoN 216), *Player Core 2* (227), *Monster Core* (221), and *NPC Core* (236). The immutable profile record has not yet been created, so accepted rules profiles remain at zero.
- Rules dependencies: core encounter procedures may come from other AoN pages when required to execute allowlisted content. This does not authorize a bulk import of *GM Core* or any other source's content. Foundry is optional engineering reference only.
- Rules judgment: the product owner is the final authority for ambiguous interpretations. Agents may propose and implement visible provisional choices; bounded GM discretion may use a named, versioned policy. Narrative judgment is never guessed silently.
- Human approval: the product owner is the sole human approver. Rules readers, implementers, and independent verifiers may be delegated evidence roles but cannot confer human approval.
- Geometry: design the general contract for footprints, placements, reach, terrain costs, blocking edges and objects, areas, elevation, and movement modes before implementation. The walking skeleton implements only its declared narrow subset; unsupported variants fail closed rather than shaping the data model.
- Semantic architecture: definitions are graph roots; core procedures and fixed rule modules are executable semantic nodes; capabilities are support claims over exact closed graphs, not runtime dispatch objects.
- Execution architecture: spendable rights use typed grants, claims, and committed receipts. Versioned engine procedures own stage order, commits, and mutation; declarative content may invoke them but cannot redefine those semantics.
- Walking-skeleton rules: include reviewed diagonal accounting that persists through save/resume. PC-category actors use dying/wounded rules, ordinary creatures are defeated at 0 HP, and significant-NPC exceptions remain unsupported.

The accepted rationale is recorded in [decision 0001](docs/decisions/0001-initial-product-and-rules-boundary.md) and [decision 0002](docs/decisions/0002-foundational-rules-contracts.md).

The [canonical registry](registry/README.md) is the source of truth for these values, package records, evidence, approvals, and support. The package state machine and work-in-progress limits are defined only in [Codex delivery](docs/design/05-codex-delivery.md).

## Current gate

The next gate is the foundational-contract gate in the [roadmap](docs/design/07-roadmap.md), followed by one end-to-end walking skeleton:

```text
source record -> minimal compiler -> engine -> save/resume
              -> public API -> headless client -> inspectors and benchmarks
```

The contract gate closes the P0 gaps identified by the [rules/design stress test](docs/design/details/rules-design-stress-test.md) without adding a general rules DSL. The walking skeleton must then finish one small encounter through public commands with compact responses and reproducible evidence. It is an architecture probe, not a support claim. The first implementation package cannot become `ready` until its applicable decisions below, oracle, owner, verifier, base commit, and selected gates are recorded.

## Unresolved decisions

1. **Walking-skeleton content and evidence:** select the encounter, source records, oracle cases, unlike adopters, and verifier-held holdout.
2. **Later contracts:** decide when viewer-relative information, area resolution, effect scheduling, and spell/item provenance become required detailed designs; their foundational state and interface boundaries must not be contradicted earlier.
3. **Performance and evidence:** choose the reference Mac, provisional-budget calibration rule, local evidence location, retention enforcement, and release-evidence access.
4. **Approval records:** choose the product owner's stable registry principal ID and whether routine in-envelope approvals may be recorded in coherent batches; formalize decisions 0001 and 0002 after integration.

Resolve a question through a decision packet and record the authoritative approval in the canonical registry. Remove the question here when the owning document and registry have been updated.
