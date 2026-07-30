# 0002: Foundational rules contracts and walking-skeleton boundaries

This record captures product-owner decisions made after the adversarial rules/design review. The owning current documents state the accepted direction. Registry formalization remains pending until the documentation branch is integrated and the product owner's stable registry principal ID is selected.

**Packet state:** `resolved`
**Date:** 2026-07-29
**Decision owner:** Product owner
**Owning current documents:** [Status](../../STATUS.md), [rules and content](../design/01-rules-and-content.md), [engine and interfaces](../design/02-engine-and-interfaces.md), and [roadmap](../design/07-roadmap.md)
**Registry approval entry:** Pending integration commit and stable approver ID
**Supersedes / superseded by:** none

## Resolved decision

- Definitions are semantic-graph roots. Engine-owned core procedures and fixed first-party rule modules are executable semantic nodes with exact versions, digests, semantic keys, and typed dependency edges. Capability records describe support over exact closed graphs and are not runtime dispatch objects.
- Spendable rights use typed grants, claims, reservations where suspension requires them, and committed receipts. Versioned engine procedures own accounting, stage order, commit boundaries, and mutation. Declarative content may supply typed data and invoke procedures but cannot redefine those semantics.
- The walking skeleton includes diagonal movement under a reviewed accounting oracle. Turn-scoped diagonal state must survive save/resume and reset only at its approved boundary.
- PC-category actors use dying and wounded rules. Ordinary creatures are defeated at 0 HP. Significant-NPC exceptions are outside the initial supported boundary.

These approvals settle architecture and initial scope only. They do not approve detailed schemas, PF2e oracle results, implementations, capabilities, content, encounters, or support claims.

## Why

The [rules/design stress test](../design/details/rules-design-stress-test.md) showed that local inventories and sealed final outcomes could still hide unreviewed dependencies, double-spent resources, reordered resolution, changed scene semantics, or inconsistent zero-HP results. The accepted direction adds a small semantic core and typed intermediate state without expanding the content format into a general rules language.

## Serious alternatives

1. **Runtime capability dispatch and a richer DSL:** rejected because it would blur support records with executable semantics and allow rules ordering to drift into content.
2. **Orthogonal-only movement and one generic zero-HP result:** rejected because they postpone stateful core rules and encourage walking-skeleton assumptions that later adopters must unwind.

## Revisit triggers

Create a superseding decision if an unrelated second adopter requires identity dispatch or content-authored stage order; the approved AoN oracle contradicts the stated diagonal or zero-HP boundary; or the typed graph/claim/procedure contracts cannot express a selected Tier 3 scenario without a parallel cross-layer special case.

## Resolution status

- [x] Record the product-owner answers.
- [x] Update the owning current documents and decision index.
- [ ] Write the detailed foundational contract packets and approve their exact schemas and algorithms.
- [ ] Add the registry approval entry after integration with the stable approver ID and exact affected records.
