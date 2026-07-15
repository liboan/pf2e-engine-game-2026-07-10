# Project registry

The registry is the machine-readable routing and acceptance surface for the project. It links durable records without copying their content into status reports, packages, or rule definitions. [project.yaml](project.yaml) defines the accepted working product/rules boundary, routes, and fixed vocabularies.

## Fixed vocabularies

Use these terms only for their named concern:

- Clause disposition: `mapped`, `non-executable`, `excluded`, `unsupported`.
- Definition lifecycle: `candidate`, `supported`, `retired`.
- Evidence dimensions: `source-reviewed`, `isolated`, `generalization`, `production-path`, `continuous`, `client`, `performance`. Only `generalization` may contain `N/A`, with a reason.

Do not use a definition lifecycle value as an evidence result or a clause disposition as package status.

## Routes and ownership

| Route | Contents | Owner |
| --- | --- | --- |
| `rules-profiles/` | Immutable AoN cutoff, content allowlist, core-rule dependencies, and private-use boundary | Human-approved rules owner |
| `source-records/` | Compact source locators, normalized facts, ambiguity decisions, and digests | Rules reader; independent approver |
| `oracles/` | Reviewed support boundaries, expected cases, and source-record references | Rules reviewer; independent verifier |
| `definitions/<id>/behavior-inventory.yaml` | One disposition for every material source clause | Inventory reviewer independent of implementation |
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
2. its behavior inventory is closed: every clause has one disposition, every `mapped` clause reconciles with compiler-derived dependencies, every `excluded` clause is enforced and disclosed, and no clause is `unsupported`;
3. its exact profile, source, definition, module, package, and approval digests resolve; and
4. its required evidence dimensions point to accepted, reproducible manifests.

A `candidate` remains verification-only. A `retired` definition is unavailable to production unless an explicit migration produces a new `supported` definition.

## Holdout protection

All Codex agents and threads in one project may share the same filesystem. Therefore an unrevealed holdout and its expected answer must not be stored in this repository or a shared worktree. The shared holdout record contains an opaque ID, digest, scope, verifier, protected execution route, and reveal status. The verifier-owned store or CI job runs the case and publishes only a result manifest. Without protected storage, the verifier selects and evaluates the case only after the implementation commit is frozen and does not first write it to the shared workspace.

Once revealed, the verifier records the reveal, promotes the case to an ordinary regression, and selects a fresh holdout when the risk tier still requires one.

## Durable evidence

An evidence manifest identifies the source commit, profile and content digests, scenario or generator, random-provider identity, version and starting position, seed and typed input streams, exact command, environment, semantic fingerprint, and result. It must remain sufficient to regenerate evidence after temporary traces, profiles, and CI logs expire.
