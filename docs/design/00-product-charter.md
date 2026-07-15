# Product charter

**Status:** Proposed foundation  
**Audience:** Product owner, rules reviewers, implementers, and test authors  
**Read this when:** Deciding what the simulator promises or whether a milestone is complete

## Goal

Build a Pathfinder Second Edition encounter simulator that is **rules-faithful inside an explicit support boundary** and **responsive enough for interactive play**.

Rules-faithful means that each supported behavior is tied to a fixed rules profile, an independently reviewed interpretation, and tests that cover its choices, timing, events, and final state. Playable means a person can finish supported encounters through the public client without checkpoints, state repair, test-only commands, or long waits.

The product must advance three independent qualities:

- **Fidelity:** supported commands produce the reviewed PF2e result.
- **Continuity:** supported encounters run legally from setup to conclusion through public commands.
- **Responsiveness:** commands, focused choice queries, and payloads meet published budgets.

Passing one does not imply either of the others. The evidence model is defined in [03-verification-strategy.md](03-verification-strategy.md).

## Product promise

Every release names a rules profile and publishes a capability registry. A claim is specific, such as “Reactive Strike supports these trigger and interruption cases under profile X,” rather than “reactions work.”

The engine distinguishes:

- a legal command that completes;
- a legal command whose committed progress is suspended for a choice, roll, or reaction;
- an illegal or stale command;
- content or behavior outside the supported boundary.

Illegal, stale, and unsupported requests do not mutate state. A suspended resolution may commit the portion that has already happened under the rules, then stores an exact continuation. See [02-engine-and-interfaces.md](02-engine-and-interfaces.md).

Unknown mandatory behavior fails closed. The simulator never silently ignores a trait, invents a default, or substitutes a rough approximation.

## Implementation strategy

Build an isolated successor. The previous project is a source of cases and lessons, not a runtime dependency. Port only a rule case or small pure procedure after it is checked against the new rules profile and interfaces.

### First: a walking skeleton

Before building broad rule foundations, complete the smallest end-to-end path:

```text
source record + behavior inventory -> content package -> compiler -> encounter state
-> focused query -> command -> result/delta -> save/restore -> thin client
```

This skeleton runs one deliberately small authentic encounter to its declared conclusion through the public client. It includes only the minimum combat capabilities named in [07-roadmap.md](07-roadmap.md), one real suspension, and a reproducible test and benchmark result. Its purpose is to prove boundaries, packaging, persistence, and tooling—not to claim that those capabilities generalize across PF2e content.

The skeleton prevents months of isolated engine work from hardening around assumptions that fail at the compiler, API, persistence, or client boundary.

### Then: a semantic stress slice

Grow a few short sentinel encounters that collectively pressure the expensive foundations:

- turn order and the three-action economy;
- checks, degree of success, modifier stacking, and multiple attack penalty;
- submitted-path movement, footprints, reach, and a reaction to movement;
- typed damage, mitigation, Hit Points, and defeat;
- a save-based area effect;
- an interrupting reaction that suspends and resumes its parent action;
- an effect crossing a meaningful turn boundary.

Use authentic content through the production compiler and API. Keep content count small, but use unlike adopters so an implementation cannot succeed by recognizing a particular creature, action, or fixture.

### Expand by capability, not catalog size

A capability starts with a source-backed contract and independent behavior inventory. Common behavior uses shared engine primitives and a deliberately small declarative format. A genuinely unusual printed ability uses a restricted typed rule module. Adding content that uses supported capabilities should change content and tests, not the engine, API, or UI.

If two consecutive adopters require changes to a supposedly stable core boundary, pause expansion and redesign or narrow the support claim. Detailed sequencing and stop conditions belong in [07-roadmap.md](07-roadmap.md).

## Initial scope

The initial product is a private tool for one client. It does not initially require public distribution, accounts, shared encounters, or multi-client synchronization. The service boundary remains because it keeps rules resolution, persistence, and presentation separate.

The first supported release targets several small authentic encounters, not the full rules catalog. It includes only capabilities that have passed their required evidence and performance gates under the approved Remaster rules profile.

The first release does not attempt to:

- implement every PF2e option or automate Game Master judgment;
- infer executable behavior from arbitrary rules prose;
- provide combat strategy, encounter balancing, or a full character builder;
- support legacy rules or content;
- support public distribution or multiple simultaneous clients;
- preserve the previous engine or content format;
- encode every printed exception in a universal data language;
- treat a merged change, a green aggregate, or a generated report as acceptance.

## Acceptance gates

The walking skeleton is accepted when the encounter reaches its declared conclusion through the end-to-end path and deterministic save/restore, compact responses, and reproducible benchmarks work. Reusable support is earned later against unlike adopters and independent verification.

The sentinel milestone is accepted only when:

- the rules profile and relevant source records are approved;
- required content inventories close without unsupported clauses;
- each capability meets its risk-tiered evidence obligations;
- sentinel encounters complete continuously through the public API and thin client;
- rejected requests are atomic and every suspension restores exactly;
- latency, payload, memory, and normal test-time budgets pass.

The first published encounter adds one more condition: content using already-supported capabilities requires no new rule logic in the engine, service, or client.

## Product measures

Keep the current dashboard small:

- capability status by independent evidence dimension;
- continuously completed encounters;
- explicit unsupported content and exclusions;
- command/query latency, payload size, memory stability, and test duration;
- reproducibility status for tests, saves, and benchmarks.

Generated traces, profiles, and repeated snapshots are temporary artifacts. Repository and review limits are defined in [06-bloat-and-human-review.md](06-bloat-and-human-review.md); Codex delivery practices are in [05-codex-delivery.md](05-codex-delivery.md).

## Design authority

- [01-rules-and-content.md](01-rules-and-content.md) owns rules profiles, source records, content inventories, packaging, and the data/module split.
- [02-engine-and-interfaces.md](02-engine-and-interfaces.md) owns state, resolution, timing, geometry, module, and public API contracts.
- [03-verification-strategy.md](03-verification-strategy.md) owns evidence dimensions, risk tiers, and promotion.
- [04-performance-and-observability.md](04-performance-and-observability.md) owns budgets, inspection, measurement, and reproducibility.
