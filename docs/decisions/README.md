# Decision packets

Decision packets preserve a proposal, evidence, alternatives, and rationale. They do not authorize a support claim or replace the current design.

## When to write one

Use the [template](../templates/decision-record.md) when a choice changes the product promise, rules profile, foundational engine or API contract, support claim, performance budget, licensing boundary, or an earlier decision. Routine implementation choices belong in code and tests.

Name files `NNNN-short-title.md` and allocate numbers in order.

## Packet states

- `draft`: being prepared;
- `ready-for-decision`: exact approval requested;
- `resolved`: the human answer and registry approval entry are linked;
- `superseded`: replaced by a named later packet;
- `withdrawn`: no decision will be requested.

After a human decides, write the authoritative [registry approval entry](../../registry/README.md) with approver, scope, integrated commit, affected record IDs, batch flag, and outcome. Then link it from the packet and update the owning file in `docs/design/` or `STATUS.md` in the same change. The owning file is the active specification; the registry proves who approved what; the packet explains why.

To replace a decision, create a new packet, mark the old one `superseded`, cross-link them, and update the owning document. Keep resolved packets because saved games or published claims may depend on their rationale.

## Index

| ID | Decision requested | Packet state | Registry approval | Owning document |
| --- | --- | --- | --- | --- |
| [0001](0001-initial-product-and-rules-boundary.md) | Initial product and rules boundary | `resolved` | Pending initial integration commit | [Charter](../design/00-product-charter.md), [rules/content](../design/01-rules-and-content.md) |
