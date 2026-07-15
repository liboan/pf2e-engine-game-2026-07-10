# Behavior inventory contract

**Status:** Proposed companion design
**Authority:** [Rules and content strategy](../01-rules-and-content.md) owns the policy; this document fixes the record shape and reconciliation procedure but approves no profile, inventory, oracle, or support claim.

## Purpose and source boundary

A behavior inventory is an independent rules review of one immutable rules subject: a content definition or an engine-owned core procedure. It accounts for every potentially rules-relevant normalized fact before implementation is judged complete. It is neither a restatement of source prose nor a list written backward from implementation.

AoN is the sole rules source under accepted policy. Accepted source and profile records are immutable; this companion does not monitor later AoN changes. Future source-policy change requires human redesign. The examples are illustrative because no profile, source record, or inventory is approved.

## Fixed record shape

Every inventory uses this closed shape. `pf2e-successor-behavior-inventory.v1` rejects unknown or omitted keys, duplicate IDs, YAML aliases, non-UTF-8 input, and alternate scalar spellings. Semantically unordered lists are sorted before validation.

```yaml
schema: pf2e-successor-behavior-inventory.v1
id: <stable inventory ID>
state: draft | approved
supersedes:
  id: <prior inventory ID or null>
  digest: <prior inventory digest or null>
subject:
  kind: definition | core-procedure
  id: <stable registry ID>
rules_profile_id: <exact immutable profile ID>
source_record:
  id: <source-record ID>
  digest: sha256:<64 lowercase hex>
fact_set_digest: sha256:<64 lowercase hex>
inventory_digest: sha256:<64 lowercase hex>
review:
  inventory_author_principal_id: <registry principal>
  implementation_owner_principal_id: <registry principal>
  approving_principal_id: <registry principal>
  approval_entry_id: <registry approval ID or null while draft>
clauses:
  - id: <stable clause ID>
    source_fact_id: <stable normalized-fact ID>
    source_fact_digest: sha256:<64 lowercase hex>
    disposition: mapped | non-executable | excluded | unsupported
    mapping_targets:
      - kind: core-procedure | capability | rule-module
        id: <registry ID>
        version: <exact version>
        semantic_key: <core-procedure semantic key or null>
    reason_code: <fixed reason code or null>
    exclusion:
      boundary_id: <supported-use boundary ID or null>
      enforcement_policy_id: <versioned compiler/load/runtime policy ID or null>
    unsupported:
      missing_semantic_id: <capability/module/decision ID or null>
      blocker_note: <concise note or null>
```

The implemented schema is versioned by the exact `schema` value. `subject.kind` is closed: `definition` resolves a content-definition record and `core-procedure` an engine core-procedure record; IDs and routes never imply kind. The `supersedes` fields are both null or identify one prior approved inventory exactly. IDs, versions, enums, and reason codes are nonempty lowercase ASCII; digests match the shown pattern; notes are at most 240 Unicode scalar values; lists and nulls are explicit. `inventory_digest` hashes canonical JSON of the whole record with only itself omitted. Shape changes require a new schema value; consumers reject defaults and extra fields.

## Fixed facts, clauses, and digests

The rules reader splits a source record into normalized typed facts and ordering, not copied paragraphs. The source record declares the complete fact set, including later `non-executable` facts. Closure requires exactly one clause per declared fact ID and digest, with no omission, duplication, or extra fact. A fact ID names its role within that fixed record, such as `fact:pc.electric-arc.targeting`; a clause ID is allocated once per inventory and never reused. A changed split or meaning replaces the draft or passes replacement review, never rewriting an accepted record.

Each fact digest hashes canonical JSON: UTF-8, sorted object keys, preserved list order, JSON booleans/null, base-10 integers, and no insignificant whitespace. `fact_set_digest` hashes sorted `{id,digest}` pairs. The source-record digest binds locator, retrieval date, profile, fact set, and ambiguities. Any change invalidates approval and reconciliation; locators never refresh stored facts.

## Dispositions and independent control

- `mapped` requires nonempty `mapping_targets`. For a `definition` subject, each target is an exact core procedure, capability, or module dependency and `semantic_key` is null. For a `core-procedure` subject, each target repeats that subject's ID and exact version with a nonnull semantic key; those keys name reviewed procedure semantics, not DSL constructs or modules. `reason_code` and every exclusion/unsupported value are null.
- `non-executable` requires `mapping_targets: []`, `reason_code: presentation-only`, and null exclusion/unsupported values. The fact affects neither rules nor availability.
- `excluded` requires `mapping_targets: []`, `reason_code: outside-reviewed-use`, a boundary, a versioned enforcement policy, and null unsupported values. The policy blocks the behavior across compilation, loading, queries, and commands; scenario non-use is not enforcement.
- `unsupported` requires `mapping_targets: []`, `reason_code: missing-semantic` or `unresolved-decision`, a nonnull `missing_semantic_id`, and null exclusion values. It always blocks playable closure and cannot carry a speculative mapping.

Author, implementation owner, and approver are distinct registry principals. The author freezes facts and clauses before inspecting implementation; if it exists already, a new author reads only the source record. The approver reviews AoN facts and the split without compiler output. Tools may propose rows, but registry approval confers authority. Changed principals or approval references require reapproval.

## Implementation reconciliation and closure

For a `definition`, the compiler emits exact behavior dependencies, a construct source map, and enforced boundaries. For a `core-procedure`, the engine build emits its symbol/version, a semantic-key-to-code map with code-artifact digests, its actual lower-level dependency closure, and boundaries. This inventories engine code; it does not make the procedure a definition or module.

Closure is deterministic:

1. Validate the schema and resolve the exact profile, source record, typed subject, principals, and approval.
2. Recompute source-record, fact-set, fact, and inventory digests. Require a one-to-one match between the source record's declared inventory fact set and clauses, including `non-executable` rows.
3. Validate each disposition's allowed fields. Reject stale targets, unapproved `non-executable` reasons, and unenforced exclusions.
4. For a definition, compare mapped targets with compiler-derived behavior dependencies in both directions. For a core procedure, require each mapped clause's `(subject ID, version, semantic_key)` in the build's semantic-key-to-code map and require every emitted semantic key to be justified by a clause.
5. For a core procedure, separately compare actual lower-level code dependencies with the build manifest in both directions and resolve their exact accepted records. They are not clause mapping targets merely because the implementation uses them.
6. Require source-map coverage for every mapped clause, exact boundaries, and zero `unsupported` clauses. Hash the inventory, subject implementation, toolchain, dependency closure, source/semantic map, boundaries, and independent evidence into reconciliation. Content lifecycle and evidence gates remain separate.

Failure reports clause IDs and the smallest mismatch. Neither compiler nor build tooling reclassifies a clause.

## Complete illustrative draft

The [Stride](https://2e.aonprd.com/Actions.aspx?ID=2305) page identifies *Player Core* and gives it one action, the move trait, and movement up to Speed. The following complete v1-shaped draft inventories those three facts against the fixed engine-owned `core-procedure:stride` symbol. It is not a DSL entry or rule module, and it cannot approve anything because the project has no approved profile, source record, or inventory.

```yaml
schema: pf2e-successor-behavior-inventory.v1
id: example:inventory.pc.stride
state: draft
supersedes: {id: null, digest: null}
subject:
  kind: core-procedure
  id: core-procedure:stride
rules_profile_id: example:unapproved-remaster-profile
source_record:
  id: example:source.pc.stride
  digest: sha256:d0108d1bedf000e4abad1f162295a53a1c03aa563fe4caa0bd32015b16f9407a
fact_set_digest: sha256:7741a250249ec3342d6508b977ebec386a524515c3d2571ffc627a3826410128
inventory_digest: sha256:d5eb27aa1263fe43a02172e45eda807b190c916425773966e42f1ba51a1d8451
review:
  inventory_author_principal_id: example:principal.rules-reader
  implementation_owner_principal_id: example:principal.implementer
  approving_principal_id: example:principal.rules-approver
  approval_entry_id: null
clauses:
  - id: clause:stride.activation
    source_fact_id: fact:pc.stride.activation
    source_fact_digest: sha256:71b998bf7b7135c99f2dc59bd1b20d17b57a03c8c25fba21e435e2dc0ee405b0
    disposition: mapped
    mapping_targets: [{kind: core-procedure, id: "core-procedure:stride", version: "1", semantic_key: activation}]
    reason_code: null
    exclusion: {boundary_id: null, enforcement_policy_id: null}
    unsupported: {missing_semantic_id: null, blocker_note: null}
  - id: clause:stride.move-trait
    source_fact_id: fact:pc.stride.traits
    source_fact_digest: sha256:7b7e3d9b80f2ba49c86557977146677adf5d19951031ab0aa6fff0518c40bec1
    disposition: mapped
    mapping_targets: [{kind: core-procedure, id: "core-procedure:stride", version: "1", semantic_key: move-trait}]
    reason_code: null
    exclusion: {boundary_id: null, enforcement_policy_id: null}
    unsupported: {missing_semantic_id: null, blocker_note: null}
  - id: clause:stride.movement
    source_fact_id: fact:pc.stride.effect
    source_fact_digest: sha256:1b59d2b1836f71587ef82ad6e7af8f8d0af0914cbcf01a6aae12b9eb6f3f51e1
    disposition: mapped
    mapping_targets: [{kind: core-procedure, id: "core-procedure:stride", version: "1", semantic_key: movement-up-to-speed}]
    reason_code: null
    exclusion: {boundary_id: null, enforcement_policy_id: null}
    unsupported: {missing_semantic_id: null, blocker_note: null}
```

For a larger coverage example, the [Electric Arc](https://2e.aonprd.com/Spells.aspx?ID=1509) page shows activation and access metadata, one-or-two-creature targeting at 30 feet, basic Reflex defense, electricity damage, and heightening. An illustrative source draft might yield these seven rows; the digest prefixes are example-only because no approved records exist.

| Clause | Fact digest prefix | Disposition | Exact target or reason |
| --- | --- | --- | --- |
| `clause:electric-arc.activation` | `31f4c36589aa` | `mapped` | `capability:spell-activation@1`, `capability:trait-semantics@1` |
| `clause:electric-arc.access` | `39b35b1e69f4` | `mapped` | `capability:definition-access@1` |
| `clause:electric-arc.targeting` | `379daa999a64` | `mapped` | `capability:spell-targeting@1` |
| `clause:electric-arc.defense` | `4d564d3cbcc9` | `mapped` | `capability:basic-save@1` |
| `clause:electric-arc.damage` | `25144b4f172d` | `mapped` | `capability:typed-damage@1` |
| `clause:electric-arc.heightening` | `57d8d02fce22` | `mapped` | `capability:rank-heightening@1` |
| `clause:electric-arc.presentation` | `be2fc2c70664` | `non-executable` | `presentation-only` |

The row set is complete only relative to its reviewed source record. If, for example, targeting or heightening were absent from executable content, reconciliation would fail; relabeling either `excluded` requires an explicitly reviewed boundary and enforcement policy.

## Record immutability and corrections

Accepted profile, source-record, and inventory bytes are immutable. Before approval, a correction replaces the draft and recomputes every affected digest. Once an inventory is approved or referenced by another record, it is never edited in place; a necessary correction is a replacement with a new ID and digest whose `supersedes` fields bind the prior exact ID and digest and whose approval explicitly authorizes the replacement. The old record and every dependent remain bound to their original bytes. Supersession tells new work which corrected record to use; it neither rewrites dependencies nor defines a package or save migration.

This project does not design for later AoN changes or record migration. A future source-policy change, including any decision about already-published packages or saves, is outside scope and requires a new human decision and design.
