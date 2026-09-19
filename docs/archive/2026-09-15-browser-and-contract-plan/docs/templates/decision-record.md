# NNNN: `<decision title>`

This file is a proposal and human decision packet. It preserves rationale but does not itself authorize a support claim or contract. The authoritative approval entry belongs in the [canonical registry](../../registry/README.md), and the owning current document remains the active specification.

**Packet state:** `draft | ready-for-decision | resolved | superseded | withdrawn`  
**Date:** `YYYY-MM-DD`  
**Decision owner:** `<person/role>`  
**Owning current document:** `<design or STATUS link>`  
**Registry approval entry:** `<approval ID/link after decision, or pending>`  
**Supersedes / superseded by:** `<packet link or none>`

## Decision requested

State the exact approval requested, its scope, and why it is needed now. Name the affected rules profile, contract, source records, or support entries. Link evidence; do not paste logs or retell project history.

For a proposed batch, list every record explicitly. A batch may contain only routine in-envelope records sharing the same accepted capability behavior, exclusions, public wording, and exact integrated commit. Remove exceptions for focused review.

## Recommendation

Write the proposed behavior or policy precisely enough to update the owning current document.

## Serious alternatives

1. **`<alternative>`:** `<why it was not recommended>`
2. **`<optional alternative>`:** `<why it was not recommended>`

List no more than two genuinely viable alternatives.

## Evidence and risk

- **Evidence:** `<source, oracle, experiment, benchmark, review, or registry link>`
- **Main risk:** `<plausible consequence of a wrong decision>`
- **Benefits:** `<what the recommendation enables>`
- **Costs:** `<what becomes harder or unsupported>`
- **Not changed:** `<nearby concerns outside this decision>`

## Revisit trigger

Reopen only when `<measurable event, new rules source, failed adopter, budget breach, or date>` occurs. Do not use “if needed.”

## Resolution steps

After the human decision:

- [ ] Write the registry approval entry with approver, exact scope, integrated commit, and every affected source, oracle, capability, content, encounter, or package record.
- [ ] Link that registry entry above and record whether the recommendation was approved, modified, or rejected.
- [ ] Update the owning current document in the same change when an approved decision changes it.
- [ ] Cross-link superseded packets.
- [ ] Remove the resolved question from `STATUS.md`, or replace it with the precise next unresolved decision.

The packet explains why. The registry entry proves who approved exactly what, and the owning current document states the resulting rule.
