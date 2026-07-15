# Bloat control and human review

**Status:** Proposed operating policy  
**Audience:** Product owner, maintainers, reviewers, and Codex coordinators  
**Read this when:** Adding durable code, tests, documents, artifacts, or approvals

## Summary

Keep only material that maintains supported behavior, reproduces evidence, or records a durable decision. Generated evidence expires outside Git, replaced documents are deleted, and agent handoffs report changed facts rather than retelling work. Agents handle routine review. Humans decide the small set of questions that define rules truth, architecture, public support, or licensing.

The product gates remain authoritative even when a size budget passes. Delivery states are defined in [05-codex-delivery.md](05-codex-delivery.md); proof requirements are in [03-verification-strategy.md](03-verification-strategy.md).

## Budgets are review triggers

These defaults are stop signals, not targets. Split work at a real responsibility or evidence boundary, never merely to satisfy a line count.

| Surface | Default budget |
| --- | --- |
| Production pull request | One coherent behavior or contract with one owner and one reviewable claim |
| Shared engine component | One named rules responsibility; stop if it accumulates unrelated phases or content identities |
| Typed rule module | One printed behavior or genuinely shared rule concept; stop if it hides a missing primitive |
| Main design document | 1,500 words |
| Decision packet | 500 words |
| Pull-request description | 500 words and one small results table |
| Status report or handoff | 600 words |
| Checked-in expected output | 100 KB per case |
| Agent task brief | 1,000 words, with links to the relevant design sections |

Review code growth at each sentinel. Pause feature work when a reviewer cannot explain a component's responsibility, a change touches several layers for one mechanic, or generated indirection hides the real implementation. Size never justifies weakening rules, continuous-play, or performance evidence.

## Put material in one proper home

### Code and content

Content using supported capabilities should add definitions and tests, not branches across the compiler, engine, API, and client. Shared code may not recognize creature, encounter, fixture, or test IDs. Delete replaced adapters and dead paths in the same change that makes them obsolete.

The declarative format remains small; unusual printed behavior belongs in a bounded rule module. Do not create layers that merely translate between near-identical internal shapes. A new layer must remove a real dependency or enforce a useful boundary.

Generated code must identify its generator and be reproducible. Otherwise, keep it out of Git. Exact content and engine versions are recorded by digest; avoid compatibility shims for unreleased formats.

### Documents, pull requests, and comments

Maintain one current document per concern. Add a document only when it has a distinct reader and decision; otherwise update the owning document. Delete superseded proposals from the active tree—Git preserves their history. Retain only release notes, source/license records, and decisions needed to interpret an old save or public claim.

A pull request states the claim changed, why it belongs now, evidence, exclusions, and any requested decision. It does not repeat project history or paste logs. Comments explain a source, invariant, ordering rule, or safety constraint. A TODO links to tracked work and names its removal condition.

### Tests, reports, and artifacts

Fixtures set mutable state, positions, choices, and deterministic rolls; they do not copy or redefine authentic content. Expected outputs assert meaningful events and focused state slices, not every serialized field. Generated cases are reproduced from seeds instead of checked in by the thousand.

Keep one current dashboard: evidence status by dimension, continuous encounters, failed gates, latency, payload size, and test duration. Do not commit snapshots of that dashboard. Full traces, profiles, screenshots, videos, mutation logs, and benchmark samples are CI or local artifacts with automatic expiry. Git may keep a compact reproduction manifest containing tool version, content digest, seed, command, and summary.

### Thread context

Each implementation thread receives one package brief: outcome, sources, allowed files, non-goals, gates, and output location. It retrieves only the relevant design chapter and rules record. Its handoff contains the patch or commit, commands run, failures, and one next action—never the transcript. The coordination ledger links evidence without duplicating it.

## Risk-tiered review

The same risk tier assigned under [03-verification-strategy.md](03-verification-strategy.md) sets both evidence burden and review depth. A tier is not a proof level: evidence dimensions remain independent, while the table below determines who reviews and how approvals are grouped.

| Tier | Typical work | Required review |
| --- | --- | --- |
| **Tier 1 — routine** | Unambiguous content using accepted capabilities; refactors with unchanged behavior; focused bug fixes | Automated gates plus independent agent review. Routine in-envelope support promotions may share one exact human batch approval. |
| **Tier 2 — material** | New capability inside stable boundaries; new typed rule module; meaningful performance or persistence change | Independent agent verification. Promotion of new behavior requires a focused human decision packet. |
| **Tier 3 — foundational** | Ambiguous PF2e interpretation; rules profile; command/result or timing contract; DSL/module boundary; public support claim; repeated abstraction failure; license decision | Focused human approval before the decision becomes authoritative. Do not batch unrelated questions. |

An implementation can merge before a support claim is accepted if unsupported behavior remains explicit and the integration branch stays honest. `merged` means code is present. `support-accepted` means the independent registry dimensions, continuous encounters, performance gates, and required approval pass on the integrated commit.

A batch may approve only named Tier 1 records that stay inside the same accepted rules profile, capability behavior, exclusions, and public wording—for example, ten unambiguous source records or several content definitions using one accepted primitive. The batch lists every record and exact integrated commit; failed or exceptional items are removed for focused review. A new capability, unique behavior, interpretation, exclusion, or public claim always receives focused approval.

A decision packet is a proposal, not the authority to promote support. After a human decides, the authoritative entry is written to the [canonical registry](../../registry/README.md) with approver, exact scope, integrated commit, and every affected source, oracle, capability, content, or encounter record. The packet links that entry. Do not ask a human to reread raw traces or approve a vague milestone.

The product owner is currently the final authority for ambiguous PF2e interpretations. Agents may prepare and implement a provisional or configurable candidate without waiting, but must label the ambiguity and cannot promote that behavior to support before the required decision. Explicitly bounded GM choices may instead use visible, versioned policies; unbounded narrative judgment suspends for a ruling or remains unsupported.

## Human decisions that cannot be delegated

Human attention is required for:

1. the rules release, source policy, and genuinely ambiguous interpretations;
2. the initial state/command contract, resumable timing model, and DSL/module boundary;
3. every support promotion: an exact batch for routine in-envelope records, or focused approval for new behavior or claims;
4. playing each sentinel and the first published encounter through the player-facing path;
5. choosing among narrowing support, adding a primitive, or revising architecture after two unrelated adopters break the same boundary; and
6. license and attribution approval before any future public distribution.

Agents prepare a one-page packet: recommendation, one meaningful alternative, evidence, risk, and exact approval requested. Human review should decide, not perform evidence collection.

## Incorporating feedback without drift

Record feedback durably only when it changes a contract, support claim, or milestone. A decision packet contains context, recommendation, at most two serious alternatives, evidence, consequence, owner, date, and revisit trigger. It preserves the rationale; the registry approval entry and updated owning document make the result authoritative. Amend or supersede the existing packet instead of starting another essay.

Every milestone review repeats the product goal, current gate, and non-goals from the [charter](00-product-charter.md). Feedback must identify whether it improves rules fidelity, continuous play, performance, or scope clarity. Valuable ideas that do not advance the current gate go to a short backlog. Local fixes may not silently redefine success.

## Decisions

- One active document and dashboard per concern.
- Generated evidence expires outside Git; compact reproduction data remains.
- Routine work receives automated and independent-agent review; exact in-envelope promotions may share a batch approval.
- Foundational rules, architecture, public claims, player acceptance, and licensing receive focused human review.
- `merged` code is not automatically `support-accepted`.
- Feedback changes direction only through an explicit decision.
