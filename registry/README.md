# Project registry

The registry is the machine-readable routing and acceptance surface for the project. It links durable records without copying their content into status reports, packages, or rule definitions. [project.yaml](project.yaml) defines the accepted working product/rules boundary, routes, and fixed vocabularies.

## Fixed vocabularies

Use these terms only for their named concern:

- Clause disposition: `mapped`, `non-executable`, `excluded`, `unsupported`.
- Behavior-inventory subject kind: `definition`, `core-procedure`.
- Definition lifecycle: `candidate`, `supported`, `retired`.
- Evidence dimensions: `source-reviewed`, `isolated`, `generalization`, `production-path`, `continuous`, `client`, `performance`. Only `generalization` may contain `N/A`, with a reason.

Do not use a definition lifecycle value as an evidence result or a clause disposition as package status.

## Routes and ownership

| Route | Contents | Owner |
| --- | --- | --- |
| `rules-profiles/` | Immutable AoN cutoff, content allowlist, core-rule dependencies, and private-use boundary | Human-approved rules owner |
| `source-records/` | Compact source locators, normalized facts, ambiguity decisions, and digests | Rules reader; independent approver |
| `core-procedures/` | Engine-owned procedure symbol, version, implementation digest, source references, and inventory ID | Engine owner; independent rules verifier |
| `oracles/` | Reviewed support boundaries, expected cases, and source-record references | Rules reviewer; independent verifier |
| `behavior-inventories/<inventory-id>.yaml` | Closed-shape inventory for one explicitly typed `definition` or `core-procedure` subject, with one disposition for every material source clause | Inventory reviewer independent of implementation |
| `capabilities/` | Capability boundary, risk tier, exact evidence-manifest IDs, and support exclusions | Verifier and integrator |
| `packages/` | Exact definition, profile, compiler, module, approval, and inventory digests | Content/package owner |
| `project.yaml#live_ledger` | Current work packages, owners, integration commit, and acceptance state | Integrator |
| `approvals/` | Human and delegated approvals referenced by ID | Named approver |
| `evidence/` | Small durable manifests sufficient to reproduce accepted evidence | Verifier or CI evidence owner |
| `holdouts/` | Opaque verifier-owned holdout metadata and reveal history, never unrevealed payloads | Independent verifier |

The paths are routing contracts; create a record only when the corresponding work begins.

Each approval entry records its ID, approver, exact scope, integration commit, affected record IDs, whether it is a coherent batch, and outcome. Approval applies only to those named records and commit.

Do not invent a commit identifier for a decision accepted before the repository's first integration commit. Record the resolved packet and update its owning current document, then add the approval entry and index it immediately after the first commit exists. Until then, the packet must say that registry formalization is pending.

## Production gate

Production may load a definition only when:

1. its lifecycle is `supported`;
2. its behavior inventory and every invoked core procedure's inventory are closed: every clause has one disposition, every `mapped` clause reconciles with the subject-specific implementation manifest, every `excluded` clause is enforced and disclosed, and no clause is `unsupported`;
3. its exact profile, source, definition, module, package, and approval digests resolve; and
4. its required evidence dimensions point to accepted, reproducible manifests.

A `candidate` remains verification-only. A `retired` definition is unavailable to production unless an explicit migration produces a new `supported` definition.

## Holdout protection

All Codex agents and threads in one project may share the same filesystem. Therefore an unrevealed holdout and its expected answer must not be stored in this repository or a shared worktree. The shared holdout record contains an opaque ID, digest, scope, verifier, protected execution route, and reveal status. The verifier-owned store or CI job runs the case and publishes only a result manifest. Without protected storage, the verifier selects and evaluates the case only after the implementation commit is frozen and does not first write it to the shared workspace.

Once revealed, the verifier records the reveal, promotes the case to an ordinary regression, and selects a fresh holdout when the risk tier still requires one.

## Durable evidence

An evidence manifest identifies the source commit, profile and content digests, scenario or generator, random-provider identity, version and starting position, seed and typed input streams, exact command, environment, semantic fingerprint, and result. It must remain sufficient to regenerate evidence after temporary traces, profiles, and CI logs expire.

## Illustrative join example

The following is **example-only and non-authoritative**. It is a compact join map, not an installed schema or a claim about PF2e support. Every `example-*`, `EXAMPLE_*`, and `sha256:EXAMPLE_*` value is deliberately non-resolving. Real records live at the routes above and retain their own content rather than copying it into related records. The shown inventories have `definition` subjects; an inventory for an engine-owned procedure uses the same route and shape with `subject: {kind: core-procedure, id: <core-procedure registry ID>}`.

```yaml
profile:
  id: example-profile-remaster-v1
  digest: sha256:EXAMPLE_PROFILE
  approval_id: example-approval-profile
  approval_digest: sha256:EXAMPLE_APPROVAL_PROFILE

source_record:
  id: example-source-action-v1
  profile_id: example-profile-remaster-v1
  locator: EXAMPLE_AON_LOCATOR
  digest: sha256:EXAMPLE_SOURCE
  approval_id: example-approval-rules
  approval_digest: sha256:EXAMPLE_APPROVAL_RULES

oracle:
  id: example-oracle-action-v1
  profile_id: example-profile-remaster-v1
  source_record_ids: [example-source-action-v1]
  behavior_inventory_ids: [example-inventory-candidate-v1, example-inventory-supported-v1]
  capability_id: example-capability-action-v1
  approval_id: example-approval-rules
  approval_digest: sha256:EXAMPLE_APPROVAL_RULES

behavior_inventories:
  - id: example-inventory-candidate-v1
    subject: {kind: definition, id: example-definition-candidate-v1}
    source_record_id: example-source-action-v1
    clauses:
      - id: example-candidate-clause-1
        disposition: unsupported
        unsupported: {missing_semantic_id: example-core-procedure-candidate-gap-v1}
    digest: sha256:EXAMPLE_INVENTORY_CANDIDATE
  - id: example-inventory-supported-v1
    subject: {kind: definition, id: example-definition-supported-v1}
    source_record_id: example-source-action-v1
    clauses:
      - id: example-supported-clause-1
        disposition: mapped
        mapping_targets: [{kind: core-procedure, id: example-core-procedure-action-v1, version: 1, semantic_key: resolve}]
    digest: sha256:EXAMPLE_INVENTORY_SUPPORTED
    approval_id: example-approval-rules
    approval_digest: sha256:EXAMPLE_APPROVAL_RULES

capability:
  id: example-capability-action-v1
  semantic_roots: [{kind: core-procedure, id: example-core-procedure-action-v1, version: 1, semantic_key: resolve}]
  profile_id: example-profile-remaster-v1
  oracle_id: example-oracle-action-v1
  source_record_ids: [example-source-action-v1]
  evidence_manifest_ids:
    source-reviewed: example-evidence-source-reviewed
    isolated: example-evidence-isolated
    generalization: example-evidence-generalization
    production-path: example-evidence-production-path
    continuous: example-evidence-continuous
    client: example-evidence-client
    performance: example-evidence-performance
  approval_id: example-approval-rules
  approval_digest: sha256:EXAMPLE_APPROVAL_RULES

definitions:
  - id: example-definition-candidate-v1
    lifecycle: candidate
    inventory_id: example-inventory-candidate-v1
    package_id: example-content-package-candidate-v1
    digest: sha256:EXAMPLE_DEFINITION_CANDIDATE
  - id: example-definition-supported-v1
    lifecycle: supported
    inventory_id: example-inventory-supported-v1
    package_id: example-content-package-supported-v1
    digest: sha256:EXAMPLE_DEFINITION_SUPPORTED

packages:
  - id: example-content-package-candidate-v1
    profile_id: example-profile-remaster-v1
    profile_digest: sha256:EXAMPLE_PROFILE
    source_record_ids: [example-source-action-v1]
    source_digests: ["sha256:EXAMPLE_SOURCE"]
    behavior_inventory_ids: [example-inventory-candidate-v1]
    inventory_digests: ["sha256:EXAMPLE_INVENTORY_CANDIDATE"]
    definition_ids: [example-definition-candidate-v1]
    definition_digests: ["sha256:EXAMPLE_DEFINITION_CANDIDATE"]
    compiler_digest: sha256:EXAMPLE_COMPILER
    module_digests: []
    digest: sha256:EXAMPLE_PACKAGE_CANDIDATE
  - id: example-content-package-supported-v1
    profile_id: example-profile-remaster-v1
    profile_digest: sha256:EXAMPLE_PROFILE
    source_record_ids: [example-source-action-v1]
    source_digests: ["sha256:EXAMPLE_SOURCE"]
    behavior_inventory_ids: [example-inventory-supported-v1]
    inventory_digests: ["sha256:EXAMPLE_INVENTORY_SUPPORTED"]
    definition_ids: [example-definition-supported-v1]
    definition_digests: ["sha256:EXAMPLE_DEFINITION_SUPPORTED"]
    compiler_digest: sha256:EXAMPLE_COMPILER
    module_digests: []
    prerequisite_approval_refs:
      - {id: example-approval-profile, digest: "sha256:EXAMPLE_APPROVAL_PROFILE"}
      - {id: example-approval-rules, digest: "sha256:EXAMPLE_APPROVAL_RULES"}
    digest: sha256:EXAMPLE_PACKAGE_SUPPORTED

evidence:
  source_commit: EXAMPLE_INTEGRATION_COMMIT
  package_id: example-content-package-supported-v1
  package_digest: sha256:EXAMPLE_PACKAGE_SUPPORTED
  profile_digest: sha256:EXAMPLE_PROFILE
  content_digest: sha256:EXAMPLE_DEFINITION_SUPPORTED
  manifests:
    source-reviewed: example-evidence-source-reviewed
    isolated: example-evidence-isolated
    generalization: example-evidence-generalization
    production-path: example-evidence-production-path
    continuous: example-evidence-continuous
    client: example-evidence-client
    performance: example-evidence-performance

approvals:
  - id: example-approval-profile
    digest: sha256:EXAMPLE_APPROVAL_PROFILE
    approver: example-human-rules-owner
    scope: example-profile-remaster-v1
    commit: EXAMPLE_INTEGRATION_COMMIT
    affected_record_ids: [example-profile-remaster-v1]
    batch: false
    outcome: approved
  - id: example-approval-rules
    digest: sha256:EXAMPLE_APPROVAL_RULES
    approver: example-independent-rules-reviewer
    scope: example-action-v1-records
    commit: EXAMPLE_INTEGRATION_COMMIT
    affected_record_ids: [example-source-action-v1, example-oracle-action-v1, example-inventory-supported-v1, example-capability-action-v1]
    batch: false
    outcome: approved
  - id: example-approval-promotion
    digest: sha256:EXAMPLE_APPROVAL_PROMOTION
    approver: example-human-promotion-owner
    scope: example-definition-supported-v1
    commit: EXAMPLE_INTEGRATION_COMMIT
    affected_record_ids:
      - example-definition-supported-v1
      - example-content-package-supported-v1
      - example-evidence-source-reviewed
      - example-evidence-isolated
      - example-evidence-generalization
      - example-evidence-production-path
      - example-evidence-continuous
      - example-evidence-client
      - example-evidence-performance
    batch: false
    outcome: approved

live_ledger_package:
  id: example-work-package-v1
  state: support-accepted
  base_commit: EXAMPLE_BASE_COMMIT
  integration_commit: EXAMPLE_INTEGRATION_COMMIT
  package_id: example-content-package-supported-v1
  package_digest: sha256:EXAMPLE_PACKAGE_SUPPORTED
  evidence_manifest_ids:
    source-reviewed: example-evidence-source-reviewed
    isolated: example-evidence-isolated
    generalization: example-evidence-generalization
    production-path: example-evidence-production-path
    continuous: example-evidence-continuous
    client: example-evidence-client
    performance: example-evidence-performance
  approval_id: example-approval-promotion
  approval_digest: sha256:EXAMPLE_APPROVAL_PROMOTION
```

The candidate and supported records demonstrate separate boundaries. `example-definition-candidate-v1` remains verification-only because its inventory contains `unsupported`. The supported package is an immutable integrated-content manifest: it includes only prerequisite approvals, never the evidence or promotion approval produced against its digest. The external evidence, promotion approval, and `live_ledger_package` row instead join that exact package digest, the same integration commit, and all seven named evidence dimensions. The final node is only a projected join row; a real row lives exclusively under `project.yaml#live_ledger`, never inside a package or another durable record. None of these example records exists in `project.yaml`, so none changes the project's current zero-support state.
