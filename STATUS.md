# Project status

**Updated:** 2026-07-10  
**State:** Design baseline only; implementation has not begun.

## Current values

- Accepted rules profiles: **0**
- Supported capabilities, content definitions, and encounters: **0**
- Packages in `active` or `verify`: **0**
- Packages `merged` or `support-accepted`: **0**
- Executable engine, public API, client, and benchmark baseline: **none**

## Accepted baseline

- Product: **private, single-client tool**. Public distribution and multi-client operation are outside the initial target.
- Rules authority: **Archives of Nethys as retrieved through 2026-07-10**. The initial Remaster content allowlist is *Player Core* (AoN 216), *Player Core 2* (227), *Monster Core* (221), and *NPC Core* (236). The immutable profile record has not yet been created, so accepted rules profiles remain at zero.
- Rules dependencies: core encounter procedures may come from other AoN pages when required to execute allowlisted content. This does not authorize a bulk import of *GM Core* or any other source's content. Foundry is optional engineering reference only.
- Rules judgment: the product owner is the final authority for ambiguous interpretations. Agents may propose and implement visible provisional choices; bounded GM discretion may use a named, versioned policy. Narrative judgment is never guessed silently.

The accepted rationale is recorded in [decision 0001](docs/decisions/0001-initial-product-and-rules-boundary.md).

The [canonical registry](registry/README.md) is the source of truth for these values, package records, evidence, approvals, and support. The package state machine and work-in-progress limits are defined only in [Codex delivery](docs/design/05-codex-delivery.md).

## Current gate

The next gate is one end-to-end walking skeleton from the [roadmap](docs/design/07-roadmap.md):

```text
source record -> minimal compiler -> engine -> save/resume
              -> public API -> headless client -> inspectors and benchmarks
```

It must finish one small encounter through public commands with compact responses and reproducible evidence. It is an architecture probe, not a support claim. The first implementation package cannot become `ready` until its applicable decisions below, oracle, owner, verifier, base commit, and selected gates are recorded.

## Unresolved decisions

1. **Implementation:** language, package layout, canonical snapshot/persistence format, and retry identity format.
2. **Initial geometry:** confirm single-cell actors, adjacency, clear-or-blocked cells, and basic submitted paths for the walking skeleton. Larger footprints, obstacles, reach, terrain costs, areas, elevation, and flight remain outside that gate.
3. **Content and evidence:** walking-skeleton definition and oracle; unlike adopters; verifier-held holdout; and the ordinary-combat, timing/lifecycle, and geometry/basic-save-area sentinels.
4. **Performance and CI:** reference hardware, provisional-budget calibration rule, CI artifact store, retention enforcement, and release-evidence access.
5. **Human roles:** named approvers for foundational architecture, player acceptance, support promotion, and any future licensing decision; who may issue exact batched approvals for routine in-envelope records.

Resolve a question through a decision packet and record the authoritative approval in the canonical registry. Remove the question here when the owning document and registry have been updated.
