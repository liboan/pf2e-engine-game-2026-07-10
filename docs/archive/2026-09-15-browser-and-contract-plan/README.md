# PF2e encounter simulator successor

This repository is the design baseline for a new Pathfinder Second Edition encounter simulator. It promises **rules-faithful behavior inside an explicit, versioned support boundary**, continuous play through the same public interface a client uses, and interactive response times.

**Current status:** strategy only. No rules capability, content package, encounter, or runtime is supported yet. See [STATUS.md](STATUS.md) before starting work.

## Five non-negotiables

1. **Name the rules being implemented.** Every executable rule belongs to one exact rules profile and reusable source record. Ambiguity is recorded before code: agents may implement a visible provisional candidate, but human approval is required before support.
2. **Fail closed.** Content must account for every rule-relevant source element. Unknown or incomplete mandatory behavior is unsupported; it is never ignored, approximated, or treated as illegal play.
3. **Use one production path.** A source-backed definition must travel through the compiler, engine, save/resume path, public API, and headless client. Test-only state repair does not prove playability.
4. **Prove different claims separately.** Rule correctness, reuse across content, and uninterrupted encounter play are independent evidence. All required evidence and player-flow performance budgets must pass before support is claimed.
5. **Keep the system small.** Shared code contains PF2e concepts, never creature or encounter identities. Generated evidence expires outside Git; current documents replace superseded prose; work packages and handoffs stay compact.

## Terms in plain language

- **Support boundary:** the exact capabilities, variants, rules profile, and content the release has earned the right to run.
- **Rule oracle:** a reviewed record of what a rule should do, including legal and illegal examples, written independently of engine output.
- **Clause disposition:** each source clause is `mapped`, `non-executable`, `excluded`, or `unsupported`. This says what happened to the clause, not whether a definition is released.
- **Definition lifecycle:** a definition is `candidate`, `supported`, or `retired`. Production loads only supported definitions with closed clause inventories.
- **Evidence dimensions:** separate records for `source-reviewed`, `isolated`, `generalization`, `production-path`, `continuous`, `client`, and `performance`; only generalization may be `N/A` with a reason.
- **Adopter:** published content used to show that a rule implementation works beyond one example. A **holdout** is an independently selected adopter not used to shape the first implementation.
- **Declarative content:** a small data format that combines common engine operations. It is not a general programming language.
- **Rule module:** source-cited first-party code for unusual printed behavior. It receives an immutable view and may return only validated, typed operations.
- **Continuous encounter:** play from legal setup to the stated end through public commands, without checkpoints, hidden mutation, or repairs.
- **Merged:** code is on the integration branch. **Support-accepted:** independent evidence and required human approval have promoted the capability or content for production use. Merged is not accepted.

## Read by task

Read [STATUS.md](STATUS.md) first for every workflow. “Required” means the owning thread must read it; “optional” means consult it only when the named concern is affected.

| Workflow | Required | Optional when affected |
| --- | --- | --- |
| Decide scope or plan a milestone | [Charter](docs/design/00-product-charter.md), [roadmap](docs/design/07-roadmap.md) | [Predecessor lessons](docs/lessons/predecessor.md) |
| Implement a rule module | [Rules/content](docs/design/01-rules-and-content.md), [engine](docs/design/02-engine-and-interfaces.md), [verification](docs/design/03-verification-strategy.md), [oracle](docs/templates/rule-oracle.md), [work package](docs/templates/work-package.md) | [Performance](docs/design/04-performance-and-observability.md) |
| Add published content | [Rules/content](docs/design/01-rules-and-content.md), [verification](docs/design/03-verification-strategy.md), [registry](registry/README.md), [work package](docs/templates/work-package.md) | [Engine](docs/design/02-engine-and-interfaces.md) for a new semantic need |
| Verify or promote a capability | [Verification](docs/design/03-verification-strategy.md), its oracle, [registry](registry/README.md), [work package](docs/templates/work-package.md) | [Performance](docs/design/04-performance-and-observability.md) |
| Profile an API or player flow | [Engine](docs/design/02-engine-and-interfaces.md), [performance](docs/design/04-performance-and-observability.md), [work package](docs/templates/work-package.md) | [Verification](docs/design/03-verification-strategy.md) for semantic equivalence |
| Coordinate implementation or integration | [Codex delivery](docs/design/05-codex-delivery.md), [AGENTS.md](AGENTS.md), [registry](registry/README.md), [work package](docs/templates/work-package.md) | [Bloat/review](docs/design/06-bloat-and-human-review.md) |
| Request a human decision | [Bloat/review](docs/design/06-bloat-and-human-review.md), [decision proposal](docs/templates/decision-record.md), owning design section | [Decision history](docs/decisions/README.md) |

Every implementation starts with a work package. Add a rule oracle when rules truth is involved and a decision proposal when human judgment is requested. Canonical operational records live in the [registry](registry/README.md); durable decision rationale is indexed in [docs/decisions](docs/decisions/README.md).

## Authority and conflicts

The product charter owns the promise. Each numbered design document owns its named concern; the roadmap owns ordering; `STATUS.md` owns current values and unresolved decisions; the registry owns operational records. Decision packets preserve proposals and rationale; a registry approval entry records authority, and the owning design document states the resulting rule.

If two current documents conflict, stop implementation and reconcile the conflict in the owning document. Do not choose the convenient interpretation or add a compatibility layer. Git history preserves old text; only the current active document is authoritative.
