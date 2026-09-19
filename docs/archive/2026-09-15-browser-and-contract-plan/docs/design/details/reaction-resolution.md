# Reaction resolution detail

**Status:** Proposed architecture detail; no reaction oracle or capability is approved
**Audience:** Rules reviewers, engine implementers, and verifiers
**Owner:** [Engine and interfaces](../02-engine-and-interfaces.md#reaction-resolution)

## Boundary and sources

This document fixes the architecture of interruptible resolution, not PF2e answers that still need an oracle. The project profile cutoff is **2026-07-10**; these live Archives of Nethys pages were checked on **2026-07-15**. Any rules-bearing difference from the cutoff must create or amend a source record before implementation.

Grounding scenarios come from [Understanding Actions](https://2e.aonprd.com/Rules.aspx?ID=2021), [Chapter 8 action and trigger rules](https://2e.aonprd.com/Rules.aspx?ID=2263), [Reactive Strike](https://2e.aonprd.com/Actions.aspx?ID=2256), [Step](https://2e.aonprd.com/Rules.aspx?ID=2343), [Shield Block](https://2e.aonprd.com/MonsterAbilities.aspx?ID=75), [Orc Ferocity](https://2e.aonprd.com/Feats.aspx?ID=4514), [Second Shield](https://2e.aonprd.com/Feats.aspx?ID=6438), and Monster Core's [Improved Grab](https://2e.aonprd.com/MonsterAbilities.aspx?ID=66). They show, without resolving every edge case, that reactions and triggered free actions can occur inside another action, that Step suppresses a class of triggers, and that a child can alter damage, item state, a pending action, or the acting creature.

## Approved architecture principles

The product owner approved these principles as direction for this proposed design. They do not approve a PF2e oracle, an implementation contract, a capability, or a support claim; the Tier 3 approval gate still applies.

1. Timing uses **named, versioned moments**, never module registration order or prose matching.
2. Every suspension stores **serializable parent and child frames**. Frames contain typed data, not closures.
3. Reactions and triggered free actions use **one trigger mechanism**; action kind, resource claims, and response-to-trigger accounting remain distinct typed fields.
4. GM ordering and same-trigger choices use explicit named policies, and the selected policy, offered choices, and decision are stored for replay.
5. Each trigger window exposes immutable **pre-event facts** and **post-event facts**. For an uncommitted event, post-facts are a projected result, not canonical state.
6. Availability uses **typed resource claims**. A reaction normally claims the standard reaction refreshed at the start of the creature's turn and may also claim a frequency or granted-reaction resource. A triggered free action does not claim that standard reaction. Both action kinds claim the per-creature right to respond once to the same trigger; availability is never a Boolean attached to a module.
7. A child never rolls back its parent. After the child commits, the parent revalidates through a **closed, typed result**, with no arbitrary state patch or hidden repair.
8. Nesting has a **versioned support-bound limit**. Supported packages must be verified within it; exceeding it at runtime is an invariant failure, not permission to skip an offer.

## Fixed data shapes

Names below are contract shapes; field encoding remains part of the unresolved implementation decision.

```text
TriggerMoment {
  kind, version, window_id, cause_event_id, parent_frame_id,
  commit_boundary, subjects[], pre_facts, post_facts
}

TriggerOffer {
  offer_id, trigger_key, trigger_version,
  action_kind: reaction | triggered_free_action,
  reactor_ref, source_ref, module_key, module_version,
  resource_claims[], response_claim, choice_owner, payload
}

ResolutionFrame {
  frame_id, procedure_key, procedure_version, parent_frame_id,
  window_id?, step, committed_points[], remaining_plan,
  resolved_offer_ids[], consumed_response_claims[],
  consulted_fact_digest, continuation_data
}

OrderingDecision {
  window_id, policy_key, policy_version, eligible_offer_ids[],
  decision_owner, decision_scope, choice: offer_id | pass,
  resolved_offer_ids[], consumed_response_claims[], state_revision
}
```

Every shape above is a closed, versioned, serializable record. `payload`, `remaining_plan`, and `continuation_data` are phase-specific tagged unions, never arbitrary maps, closures, or unrestricted module state. `pre_facts` and `post_facts` are moment-specific records, not general snapshots. A movement moment might carry origin, candidate destination, movement kind, and traits. A damage moment might carry typed damage after the prior stage and its projected recipients. Modules receive only the facts declared for that moment.

## Window algorithm and invariants

The parent reaches a moment and creates a stable `window_id` before asking modules for offers. The engine gives each offer a stable identity that includes the window, trigger, reactor, source, and module version. It validates the trigger predicate, all resource claims, the per-creature response claim, and the support boundary against canonical state. It sorts offers only by a profile policy; when that policy assigns a player or GM choice, it commits a suspension and stores the prompt and complete ordering context.

Selecting an offer consumes its response claim, commits its declared resource claims at the reviewed commit point, and pushes a child frame. Thus a triggered free action spends no standard reaction but still prevents that creature from taking another action in response to the same trigger. A pass stores the exact offers and decision scope it resolves; it consumes no action resource or response claim, but those offers are not repeated. Nested windows use the same mechanism. After the child commits, the parent receives a closed revalidation result and continues, changes its remaining typed plan, or ends according to its oracle. It does not restore pre-child state.

Required invariants:

- `(window_id, offer_id)` is stable across retry and save/restore and is resolved at most once.
- A pass or choice records its exact scope, so reopening a frame cannot repeat an offer or prompt.
- Offers depend only on the moment facts, canonical state, fixed registry, and versioned policies.
- Each declared commit point publishes its resource receipts and child effects atomically.
- Pre/post fact digests and ordering decisions are sufficient to explain replay without source prose.
- Repeating the same parent step, rules-fact digest, and ordered eligible offers is a cycle failure.
- An invariant abort discards only the unpublished journal of its dispatch; it never rewinds an earlier published parent or child prefix.

## Verification matrix

| Case | Minimum assertions |
| --- | --- |
| Offer and pass/choose | Stable window and offer IDs; resource and response-claim eligibility; stored policy, decision scope, and no repeated prompt. |
| Parent/child interruption | Ordered pre/post facts; each published child prefix commits exactly once; no rollback; closed parent revalidation. |
| Same or nested trigger | Per-creature one-response accounting across both action kinds; profile order; cycle signature; nesting-bound behavior. |
| Persistence/retry | Save around every suspension; identical stack and prompt; receipt retry consumes no offer, claim, resource, or draw twice. |
| Hostile transformation | Rename and reorder identities without semantic change; vary a typed fact and observe the reviewed change. |
| Mutation | Registration-order fallback, omitted pass scope, duplicate offer, stale facts, rollback, or skipped bound must fail. |

## Source-grounded stress scenarios

| Scenario | Architecture exercised | Oracle boundary |
| --- | --- | --- |
| Reactive Strike observes a move action or a creature leaving a square; Step says it does not trigger such reactions. | Versioned movement moments must distinguish action start and square transition, and expose movement kind. | The live page describes square-exit timing, but the cutoff-specific source record and exact before/after facts are unsettled. |
| Reactive Strike critically hits on a manipulate trigger and disrupts the triggering action. | Child result can alter a parent plan; committed child damage is not rolled back. | Exact disruption and parent outcome require an oracle. |
| Shield Block applies to pending physical-attack damage; both creature and shield can take the remainder. | Damage pre/post facts, typed mitigation, multiple recipients, and item-state consequences. | Exact ordering among damage stages and other reactions is unsettled. |
| Second Shield triggers when Shield Block breaks or destroys the shield. | A triggered free action can open from a reaction child using the same trigger machinery. | Initial triggered-free-action coverage is unsettled. |
| Orc Ferocity triggers when damage would reduce the reactor to 0 HP and replaces that result with 1 HP plus wounded. | A child acts on projected post-facts before a pending state transition commits. | Interaction with other same-event choices requires an oracle. |
| Improved Grab is a free action triggered by the initial Strike hitting. | Action kind differs, but offer identity, choice storage, suspension, and nesting do not. | Which triggered free actions enter the first support boundary is unsettled. |

## UNSETTLED—HUMAN REVIEW REQUIRED

None of the following has an approved answer; each blocks the affected support claim:

1. **Exact movement-trigger position:** after confirming the cutoff source record, which named moment and before/after square facts encode “uses a move action” versus “leaves a square.”
2. **Incapacitation/pending action:** what happens to the unfinished action when an interrupting child leaves its actor unable to act.
3. **Same-trigger equivalence:** when two textual triggers count as the same trigger, especially for the one-triggered-free-action limit.
4. **Simultaneous ordering:** exact player/GM ownership and ordering policy when multiple actors or action kinds are eligible.
5. **Shield Block ordering:** its exact place within damage calculation, mitigation, HP loss, shield damage, breakage, and follow-on triggers.
6. **Revalidation outcome:** the exact closed result set and outcome for each changed parent assumption.
7. **Nesting bound:** the numeric bound, whether it counts frames or windows, and its profile/version placement.
8. **Initial triggered-free-action coverage:** the allowlisted abilities included in the first supported trigger mechanism.

These decisions require source records, reviewed cases, and focused human approval before implementation can claim fidelity.
