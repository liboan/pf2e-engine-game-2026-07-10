# Rule oracle: `<capability or ability>`

**Oracle ID:** `<stable-id>`  
**State:** `draft | approved | superseded`  
**Kind:** `core procedure | reusable capability | unique printed ability`  
**Risk tier:** `<tier from verification strategy>`  
**Rules profile:** `<exact immutable profile ID>`  
**Approval entry:** `<registry approval ID; reviewer metadata lives there>`

## Claim and boundary

**Supported claim:** `<one precise sentence>`

**Included variants:** `<list>`

**Excluded or unresolved variants:** `<list; unsupported, never approximated>`

## Canonical record references

Do not copy source locators, digests, inventory rows, or reviewer metadata here.

**Source record IDs:** `<registry IDs>`  
**Behavior inventory IDs:** `<one per affected definition>`  
**Capability record ID:** `<registry ID>`

Each referenced behavior inventory assigns every rule-relevant clause exactly one disposition: `mapped`, `non-executable`, `excluded`, or `unsupported`. An `unsupported` clause blocks playable status. Definition lifecycle is separate: `candidate`, `supported`, or `retired`; production loads only supported definitions with closed inventories.

**Clause IDs exercised by this oracle:** `<inventory element IDs>`

## Reviewed interpretation

Describe the outcome, ordering, costs, choices, reactions, and duration anchors in plain language. Mark project interpretations explicitly. Do not derive this text from engine output.

## Cases

| Case | Starting facts and supplied rolls | Command or choice | Expected events in order | Expected final facts/result |
| --- | --- | --- | --- | --- |
| `<positive>` | | | | |
| `<illegal inverse>` | | | | `rejected; same revision and state` |
| `<boundary/interaction>` | | | | |
| `<pause if relevant>` | | | | `committed/suspended; new revision and frame` |

## Independent evidence plan

| Dimension | Planned evidence or justified status |
| --- | --- |
| `source-reviewed` | `<approval entry and exact boundary>` |
| `isolated` | `<positive, illegal, edge, transformation, property, mutation cases>` |
| `generalization` | `<unlike adopters and verifier-owned holdout, or N/A with reason>` |
| `production-path` | `<definition -> compiler -> engine -> API evidence>` |
| `continuous` | `<sentinel or later encounter>` |
| `client` | `<headless/player flow>` |
| `performance` | `<named budgets and manifest>` |

For a unique ability, `generalization` may be `N/A` only with a reason; all other dimensions remain required.

## Change control

An implementation failure does not change this oracle. Correct factual errors through a new review recorded at **Approval entry**, then update affected cases and support state deliberately.
