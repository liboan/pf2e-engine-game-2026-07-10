# Codex delivery strategy

**Status:** Proposed operating model  
**Audience:** Maintainers, rules reviewers, implementers, and Codex coordinators  
**Read this when:** Planning, assigning, reviewing, or integrating work

## Summary

Deliver the successor as small work packages with explicit rules, product, and performance claims. One thread owns each package; another verifies it. Parallel work is useful for independent research and modules, but shared contracts change one at a time. A merge makes code available; it does **not** make a capability supported. Support is accepted only after its full evidence and continuous-encounter gates pass.

This process applies the [product charter](00-product-charter.md), [verification strategy](03-verification-strategy.md), and [roadmap](07-roadmap.md). Repository and human-review limits are in [06-bloat-and-human-review.md](06-bloat-and-human-review.md).

This chapter is the authority for package states, transitions, and work-in-progress limits. [STATUS.md](../../STATUS.md) reports only current values and the next gate. The live package ledger, evidence references, approvals, and support entries are in the [canonical registry](../../registry/README.md).

## The unit of work

A work package should normally fit one focused pull request and state:

- the observable behavior and exact support boundary;
- source-backed rule cases and unresolved interpretations;
- interfaces and files it may change;
- positive, negative, interaction, and holdout evidence required;
- affected continuous encounters and performance budgets;
- dependencies, exclusions, owner, verifier, and human-review tier.

Split a package when its behavior cannot be explained in a few sentences. Do not split work that must repeatedly edit the same contract; give that contract one owner instead.

## Package state and work-in-progress limits

Every package has one state in the coordination ledger:

| State | Meaning |
| --- | --- |
| `proposed` | Scope and evidence plan are being drafted; implementation has not started. |
| `ready` | Contract, evidence plan, ownership, dependencies, and base commit are fixed. |
| `active` | One implementer owns the branch and files. |
| `verify` | Implementation is frozen except for verifier-requested fixes. |
| `merged` | Code is on the integration branch; no support claim is implied. |
| `support-accepted` | Required registry dimensions, continuous encounters, performance gates, and the exact human approval entry all pass on the integrated commit. |
| `blocked` | A named decision or dependency prevents useful work; the return state is recorded. |
| `retired` | The package will not proceed or its supported execution was withdrawn. |

Normal flow is `proposed -> ready -> active -> verify -> merged`; capability and content packages may then become `support-accepted`. The WIP limits are:

- at most three packages in `active` or `verify` combined;
- within that total, at most one package changing a shared contract;
- at most two disjoint implementation packages; and
- at most one package in independent integration or verification.

Do not start new implementation while integration has an unexplained red gate. Research that edits no product files may run concurrently.

## Agent roles

Use separate roles so implementation convenience does not define correctness:

1. **Reader:** extracts authoritative sources, interpretations, and adversarial cases. It returns a compact rules record, not code or a research transcript.
2. **Implementer:** works from the accepted record, writes the smallest change, and owns focused tests and measurements.
3. **Verifier:** starts from the contract and diff, not the implementer’s story. It checks hidden assumptions, unsupported approximations, identity-based branches, atomicity, pause/resume, and plausible wrong implementations.
4. **Integrator:** reproduces evidence on the current integration commit, runs cross-package gates, and changes package state.

One coordinator owns the plan and conclusions. Use a durable Codex task for a package that spans commits or handoffs; use subagents for bounded parallel reads, checks, and critiques inside that package. Do not create a lasting task for every clerical step. Subagents receive exact inputs, allowed outputs, and a size limit. Keep delegation trees shallow: a child may delegate a narrow source scan or mechanical check, but conclusions should not pass through several summaries. The coordinator reads the returned evidence, not every source corpus.

Parallelize source extraction, independent holdout design, disjoint rule modules, benchmark investigation, and adversarial review. Serialize shared contract work and changes to continuous scenarios. Competing designs are disposable experiments with one named decision owner; they are not both merged.

## Model and reasoning routing

Choose the least expensive route that reliably passes the package gate:

| Work | Model slug | Starting reasoning effort |
| --- | --- | --- |
| Architecture, ambiguous PF2e interpretation, cross-system failures, adversarial design review | `gpt-5.6-sol` | `high` |
| Normal implementation, focused debugging, integration synthesis, substantive code review | `gpt-5.6-terra` | `medium` |
| Bounded extraction, test execution, structured comparison, simple coordination | `gpt-5.6-terra` | `low` |
| Deterministic clerical work such as formatting or exact renames | `gpt-5.6-luna` | `low` |

**Availability snapshot (2026-07-15):** the callable new-task schema on this host offered `gpt-5.6-sol` and `gpt-5.6-terra` with efforts `{low, medium, high, xhigh, max, ultra}`; `gpt-5.6-luna` with efforts `{low, medium, high, xhigh, max}`; and `gpt-5.5`, `gpt-5.4`, `gpt-5.4-mini`, and `gpt-5.3-codex-spark` with efforts `{low, medium, high, xhigh}`. This is an availability note, not a permanent contract. Immediately before launch, the coordinator must revalidate both the exact slug and effort against the current `create_thread` schema; if either is unavailable, stop and update the routing record rather than guessing a replacement.

This table applies only when a coordinator creates a new durable task through a `create_thread` interface that accepts model and reasoning selections. The current collaboration `spawn_agent` interface exposes neither selection, so a subagent cannot choose or switch to another route; sending a later message also does not apply this table retroactively.

Do not use `gpt-5.6-luna` for rule interpretation or code judgment. Escalate after evidence of a missed source, unstable design, repeated test error, unresolved interaction, or weak review—not merely because the package is important.

## Branches, reviews, and integration

Each package starts from a clean, current integration commit in its own branch or worktree. Record the base. Do not mix another package, generated reports, or unrelated cleanup into it. Shared-contract packages merge before dependents; dependents refresh their base and rerun their complete gates.

The handoff is compact and reproducible:

- base and head commits;
- changed claim and known exclusions;
- source and case identifiers;
- exact test and benchmark commands with summarized results;
- holdout and continuous-encounter results;
- one blocker or next action, if any.

Link retained CI artifacts; never paste full logs. The integrator recomputes evidence rather than trusting a branch summary. A semantic conflict is resolved in the contract, not hidden in a mechanical merge.

## Continuous encounters that resist selective proof

Continuous acceptance scenarios belong to the integration suite, not to individual packages. They start from legal encounter setup and proceed only through public commands to a declared end. No package may substitute checkpoints, state repair, or a hand-picked segment for the full scenario.

CI selects every scenario whose declared capability set intersects the change, plus one rotating unrelated scenario. The package author cannot narrow that selection. Scenario definitions, decision streams, roll streams, and expected rules outcomes are versioned separately from implementation; changing them with the behavior under test requires independent verification. The runner binds IDs returned by earlier commands but may not inspect computed outcomes to choose a favorable branch.

This prevents a package from earning acceptance by cherry-picking easy steps. Focused tests still diagnose local behavior, while continuous scenarios prove reachability, composition, and continuation.

## Status communication

Keep the package ledger in the [canonical registry](../../registry/README.md), with package, owner, state, dependency, base commit, and evidence link. Report only exact state changes and gate events: entered `ready`, `active`, or `verify`; gate passed or failed; decision needed; `merged`; `support-accepted`; `blocked`; or `retired`. `STATUS.md` summarizes current counts and the immediate gate; it does not redefine this state machine. Do not create parallel scoreboards or recurring narrative reports.

## Decisions

- One owner and one independent verifier per package.
- One shared-contract change at a time; disjoint work may proceed in parallel.
- Merged and support accepted are separate states.
- Package state, evidence, support, and human approval are recorded in the canonical registry.
- Integration owns continuous scenarios and chooses affected coverage automatically.
- Model escalation follows failed evidence gates.
- Handoffs contain reproducible facts, not conversation history.
