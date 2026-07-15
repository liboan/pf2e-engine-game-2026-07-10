# Rules/design stress test

**Status:** Bounded independent reviewer artifact; no rules oracle, profile, capability, definition, or support approval

**Baseline:** `c112144de538d269e2ae5df3aa09b1bcdc7596c7`

**Package:** `docs-design-deepening-v1`

## Scope, method, and source boundary

This review read the complete tracked documentation and registry at the baseline above. It tested the proposed source, compiler, engine, frame, persistence, API, client, and evidence contracts with interacting PF2e cases. Archives of Nethys (AoN) was the sole rules authority; no Foundry or other rules implementation was used as authority.

The project cutoff is 2026-07-10. The linked AoN pages were checked live on 2026-07-15. Because no immutable profile or source records are approved, the links identify candidate facts but do not prove the bytes served at the cutoff. A material difference must go through the existing source-record and oracle process.

**P0** means the current foundational or walking-skeleton contract would permit false closure. **P1** means a named later milestone or already-proposed operation family lacks a sufficient contract. Unsupported future behavior is not a defect merely because it is absent. Appendix A fixes each probe's inputs and expected result; each finding traces it through compilation, resolution/frame state, save/API behavior, and evidence.

## Prioritized findings

| ID | Priority | Root deficiency | Consequence |
| --- | --- | --- | --- |
| F01 | P0 | No transitive semantic-closure record | A definition can close while inherited rules semantics remain unreviewed. |
| F02 | P0 | No typed turn-action ledger | Cost commitment, suspension, refresh, and later activity/result semantics have no common state. |
| F03 | P0 | No ordered check/degree pipeline | MAP, fortune/misfortune, natural-roll shifts, and later degree changes can resolve differently. |
| F04 | P0 | No first-class damage/healing packet | Component grouping, I/W/R, choices, mitigation, and healing duals are under-specified. |
| F05 | P0 | No immutable scene/map identity | Restore can change path legality while all named package digests still match. |
| F06 | P0 | No typed health transition; later lifecycle is unscheduled | The walking skeleton cannot close zero HP/defeat, and later phase order, conditions, and dying cannot compose. |
| F07 | P1 | No viewer-relative information-state contract | Target queries, prompts, receipts, and deltas can disclose hidden facts. |
| F08 | P1 | No area-resolution dependency graph | Shapes can ignore footprints, line of effect, cover, or defense ordering. |
| F09 | P1 | No spell/item resource provenance | Disruption, shared pools, grants, item transfer, and restore can spend or derive the wrong source. |

Findings are ordered by priority and dependency. F01 controls review closure; F02–F06 block foundational or walking-skeleton closure; F07–F09 build on those foundations.

## Findings

### F01 — Rules authority cannot close transitively (P0)

**Design and sources.** [Source records](../01-rules-and-content.md#source-records) require a record for every reusable capability, but [inventory subjects](behavior-inventories.md#fixed-record-shape) are only `definition` or `core-procedure` and bind one `source_record`; [package manifests](definitions-instances-packages.md#package-manifest-and-digests) can bind many records without defining semantic closure. S01 combines [Electric Arc](https://2e.aonprd.com/Spells.aspx?ID=1509), [basic saves](https://2e.aonprd.com/Rules.aspx?ID=2297), [degrees](https://2e.aonprd.com/Rules.aspx?ID=2286), and [damage](https://2e.aonprd.com/Rules.aspx?ID=2301).

**Failure.** Compiler-derived capability names prove linkage, not independent source review. A local definition inventory can close while leaf semantics have no clause dispositions, or general rules must be duplicated into each definition. Loader closure and `source-reviewed` evidence can therefore be false before execution.

**Smallest packet/decision.** `authority-and-semantic-closure`: immutable multi-record fact sets, typed transitive edges, cycle/digest rules, and one closeable subject for every executable leaf. Decide whether reusable capabilities become inventory subjects or must terminate in inventoried core-procedure semantic keys. Compiler output, registry joins, package loading, and source-reviewed evidence must reconcile the same graph. This is an architecture choice, not a PF2e interpretation.

### F02 — Turn actions lack one canonical ledger (P0)

**Design and sources.** [Canonical state](../02-engine-and-interfaces.md#canonical-state) names generic resources and excludes traces; [frames](../02-engine-and-interfaces.md#resolution-frames-and-timing) can preserve a parent plan without action-credit identity. The [walking skeleton](../07-roadmap.md#start-with-one-end-to-end-walking-skeleton) needs three actions now. S02 also pressure-tests later [action/activity rules](https://2e.aonprd.com/Rules.aspx?ID=2335), [quickened](https://2e.aonprd.com/Conditions.aspx?ID=89), [slowed](https://2e.aonprd.com/Conditions.aspx?ID=92), [Lurching Charge](https://2e.aonprd.com/Monsters.aspx?ID=3088), [Grab](https://2e.aonprd.com/MonsterAbilities.aspx?ID=45), and [Rend](https://2e.aonprd.com/MonsterAbilities.aspx?ID=73).

**Failure.** Even the narrow slice has no fixed refresh, spend, commit, and retry record. Later, a flat integer cannot distinguish restricted credits from an outer activity, subordinate actions, or expiring prior-result facts. A restored engine would need replay, a hidden cache, or identity-specific logic for Grab/Rend.

**Smallest packet/decision.** `action-activity-and-turn-economy`: v1 must define normal credits, refresh, commit receipts, frame ownership, rejection, save/retry, and MAP handoff; later versions add typed restrictions, atomic activity cost, subordinate provenance, disruption, and expiring `ActionResultToken`s. API option queries/deltas and Tier 3 save-at-each-boundary mutations use the same ledger. Only the v1 subset blocks the walking skeleton; later examples are design pressure, not present support claims. Approve the shared command contract; keep exact reaction disruption/revalidation as separate oracles.

### F03 — Checks and degrees have no ordered pipeline (P0)

**Design and sources.** Checks and degree changes are named primitives in the [content strategy](../01-rules-and-content.md#small-data-format-and-typed-modules), illustrative [`MomentSpec`s](../02-engine-and-interfaces.md#momentspec-contract), and Tier 3 work in [verification](../03-verification-strategy.md#tier-3-foundational-or-cross-cutting-behavior), but no closed stage record exists. S03 uses [Ready](https://2e.aonprd.com/Rules.aspx?ID=2343), [MAP](https://2e.aonprd.com/Rules.aspx?ID=2289), [fortune/misfortune](https://2e.aonprd.com/Traits.aspx?ID=612), and [degrees](https://2e.aonprd.com/Rules.aspx?ID=2286).

**Failure.** The design does not fix modifier stacking, MAP capture/increment, fortune selection ownership and cancellation, draw commitment, natural 20/1 adjustment, later degree adjustments, or secret publication. Module order or a restore point can change the degree while every individual output remains typed.

**Smallest packet/decision.** `check-and-degree-resolution`: check/DC provenance, modifier collection/stacking, fortune selection/cancellation, random receipt, natural-roll shift, ordered later shifts, MAP context/snapshot, and public/secret outcome. Persist stage, candidates, choices, and provider position; test stage-order mutations, retries, and unlike adopters. Approve the architecture; disputed printed adjustments receive focused oracles.

### F04 — Damage and healing need a first-class packet (P0)

**Design and sources.** The [content format](../01-rules-and-content.md#small-data-format-and-typed-modules) promises typed damage/healing; [`damage pending`](../02-engine-and-interfaces.md#momentspec-contract) and module adjustments do not define the effect boundary. S04 uses [damage](https://2e.aonprd.com/Rules.aspx?ID=2301), [immunity](https://2e.aonprd.com/Rules.aspx?ID=2313), [weakness](https://2e.aonprd.com/Rules.aspx?ID=2317), [resistance](https://2e.aonprd.com/Rules.aspx?ID=2318), [Heal](https://2e.aonprd.com/Spells.aspx?ID=1554), [Harm](https://2e.aonprd.com/Spells.aspx?ID=1552), and [Shield Block](https://2e.aonprd.com/MonsterAbilities.aspx?ID=75).

**Failure.** Flattening loses component characteristics and provenance; splitting one effect can activate defenses repeatedly. Generic adjustments do not state stage order, category-resistance choice, multi-recipient mitigation, or whether a living/undead result is healing or damage. Frames cannot preserve activation ledgers and prompts; tests can pass a favorable component order.

**Smallest packet/decision.** `damage-and-healing-resolution`: effect/source identity, recipients, typed components, precision/material/trait provenance, effect grouping, critical transform, I/W/R activations and choices, mitigation, healing, and a typed committed result handed to F06. Compiler dependencies, frames, API explanations, and split/merge/reorder mutations bind that packet. Approve the architecture. Shield Block's exact stage remains the already named PF2e oracle; production must reject the dependent path until that oracle is approved, not approximate or prompt for it at runtime.

### F05 — Map semantics lack immutable identity (P0)

**Design and sources.** [Instances](definitions-instances-packages.md#mutable-instances) contain a bare `map_id`; [geometry](../02-engine-and-interfaces.md#geometry-boundary) validates submitted paths; [on-demand inspection](../04-performance-and-observability.md#on-demand-inspection) leaves bulky maps as ID-addressed resources. [Grid movement](https://2e.aonprd.com/Rules.aspx?ID=2356) and [terrain](https://2e.aonprd.com/Rules.aspx?ID=2365) establish that scene bytes affect rules results.

**Failure.** S05 restores a save against different bytes behind the same ID. Profile, package, compiler, module, and definition digests can all match while a blocked destination becomes clear. Command validation, preflight queries, fingerprints, and continuous replay then disagree.

**Smallest packet/decision.** `scene-identity-and-state`: immutable topology/geometry digest and package binding, mutable scene facts in canonical state, query/command parity, snapshot/delta fields, and changed-scene rejection. Evidence must change map bytes without changing the ID. This is architecture, not a PF2e ambiguity. Diagonal accounting is a separate unresolved scope decision recorded under non-findings below.

### F06 — Health transitions and the later effect lifecycle lack a schedule (P0)

**Design and sources.** [Canonical state](../02-engine-and-interfaces.md#canonical-state) names effects and duration anchors, while [`MomentSpec`](../02-engine-and-interfaces.md#momentspec-contract) promises deterministic order; only reactions have a concrete ordering record. S06 uses [start turn](https://2e.aonprd.com/Rules.aspx?ID=2428), [end turn](https://2e.aonprd.com/Rules.aspx?ID=2430), [fast healing](https://2e.aonprd.com/Rules.aspx?ID=2322), [recovery](https://2e.aonprd.com/Rules.aspx?ID=2326), [losing dying](https://2e.aonprd.com/Rules.aspx?ID=2328), [conditions](https://2e.aonprd.com/Rules.aspx?ID=2455), [knockout](https://2e.aonprd.com/Rules.aspx?ID=2324), [Orc Ferocity](https://2e.aonprd.com/Feats.aspx?ID=4514), [Stench](https://2e.aonprd.com/MonsterAbilities.aspx?ID=76), and [Frightful Presence](https://2e.aonprd.com/MonsterAbilities.aspx?ID=64).

**Failure.** The current slice has no typed handoff from damage to actor-category-specific zero-HP, defeat/destruction/dying, initiative, and reaction results. It can therefore close the walking skeleton with different state transitions across engine, save, API, and client. Later, a fixed total order can contradict an owned phase choice; effective-only conditions lose latent contributions/durations; and the wrong effect identity makes immunity too broad or narrow.

**Smallest packet/decision.** `effect-turn-and-health-lifecycle`: v1 defines the damage-result handoff, actor category, zero-HP result, defeat/destruction/dying and initiative transition, reaction boundary, save/retry, and public delta. Later versions add the phase DAG and owner, `PhaseOrderDecision`, condition contributions/effective projection, effect equivalence/immunity scope, duration anchors, and simultaneous groups. Select walking-skeleton actor categories and significant-NPC policy, then approve v1; discretionary simultaneous/duration interpretations remain focused oracles.

### F07 — Targeting lacks viewer-relative information state (P1)

**Design and sources.** [Public queries and player views](../02-engine-and-interfaces.md#public-api-and-persistence) have no observer-relative or redaction shape. S07 uses [Detecting Creatures](https://2e.aonprd.com/Rules.aspx?ID=2414), [Targets](https://2e.aonprd.com/Rules.aspx?ID=2380), [Hidden](https://2e.aonprd.com/Conditions.aspx?ID=79), [Undetected](https://2e.aonprd.com/Conditions.aspx?ID=96), and [Concealed](https://2e.aonprd.com/Conditions.aspx?ID=62).

**Failure.** An actor-ID target list, detailed rejection, prompt, delta, or random receipt can reveal a secret location or failure cause. Canonical state does not name observer/subject knowledge, suspected squares, prompt audience, or secret result projection. The client cannot safely reconstruct any of these.

**Smallest packet/decision.** `targeting-and-information-state`: senses, observer-relative state, actor/square/area targets, suspected locations, secret random receipts, audience-specific prompts/events/deltas, persistence, and noninterference tests. Compile target-kind dependencies and test identical public output for distinct hidden failure causes. GM-discretion targeting variants remain explicit oracle/unsupported boundaries.

### F08 — Area geometry lacks a dependency graph (P1)

**Design and sources.** The [geometry boundary](../02-engine-and-interfaces.md#geometry-boundary) defers footprints, areas, and line/cover, but [milestone 4](../07-roadmap.md#4-geometry-and-basic-save-area-sentinel) adds obstacles and an area without naming their dependency order. S08 combines [area](https://2e.aonprd.com/Rules.aspx?ID=2384), [size/space](https://2e.aonprd.com/Rules.aspx?ID=2359), [line of effect](https://2e.aonprd.com/Rules.aspx?ID=2382), [cover](https://2e.aonprd.com/Rules.aspx?ID=2372), and [basic saves](https://2e.aonprd.com/Rules.aspx?ID=2297).

**Failure.** A shape-only sentinel can affect through a wall, omit cover, or miss a creature whose footprint intersects by one cell. If the compiler, query, engine, and client each infer dependencies, they can disagree before the defense roll.

**Smallest packet/decision.** `area-and-spatial-resolution`: origin/range, shape, footprint intersection, line of effect, cover, information-safe target projection, and ordering before defenses/damage. Either add the dependencies to milestone 4 or enforce a disclosed open-map boundary at compile/load/query/command. Complex gaps, reach/footprints beyond the selected size set, elevation, and 3D remain explicit later decisions.

### F09 — Spell and item resources lack provenance (P1)

**Design and sources.** [Mutable instances](definitions-instances-packages.md#mutable-instances) use a string-to-amount resource map, while frames preserve committed prefixes without typed grants. S09 uses [focus spells](https://2e.aonprd.com/Rules.aspx?ID=2228), [innate spells](https://2e.aonprd.com/Rules.aspx?ID=2232), [casting](https://2e.aonprd.com/Rules.aspx?ID=2233), [disrupted spells](https://2e.aonprd.com/Rules.aspx?ID=2236), and [limited item activations](https://2e.aonprd.com/Rules.aspx?ID=3143).

**Failure.** The map cannot distinguish pool, grant, owner, casting entry, rank/tradition/DC, reset anchor, or idempotent claim. A disrupted prepared casting can spend an innate use, focus spells can use the wrong source statistics, and item transfer can refresh an actor-owned counter after restore.

**Smallest packet/decision.** `spell-item-resource-provenance`: typed owner/pool/grant/casting entry, rank/statistic source, reset anchor, item transfer, reserve/commit receipt, and disruption. Compiler output derives grants/pools; frames retain exact claims; API prompts identify the selected source; persistence/retry tests disrupt and transfer at each boundary. Approve this architecture. Counteract is cleanly unsupported future scope, addressed below rather than folded into this packet.

## Cross-cutting patterns and authoring order

1. Rules-bearing provenance belongs in canonical state, not a trace: MAP snapshots, action-result qualifiers, damage components, effect sources, scene digests, observer knowledge, and resource grants all decide future legality.
2. Determinism includes owned choices. Record a legal partial order, owner, selected step, and prompt; do not replace choice with module or registration order.
3. Closed public outcomes need closed intermediate records. A sealed result union is insufficient if its check, damage packet, phase order, knowledge state, or resource claim is an untyped map.
4. Evidence should mutate grouping, provenance, redaction, and restore points—not only final totals.

Recommended authoring sequence:

1. `authority-and-semantic-closure`;
2. `action-activity-and-turn-economy`, then `check-and-degree-resolution`;
3. `damage-and-healing-resolution`, then `effect-turn-and-health-lifecycle`;
4. `scene-identity-and-state`;
5. `targeting-and-information-state`, then `area-and-spatial-resolution`;
6. `spell-item-resource-provenance`.

Use the reaction companion's pattern in each: fixed serializable shapes, ordered algorithm and commits, revalidation, API/persistence mapping, verification matrix, source scenarios, and a separate unsettled-oracle section.

## Explicit non-findings and unsupported boundaries

- The [reaction companion](reaction-resolution.md) is structurally strong: stable moment/offer identity, typed claims, committed children, no rollback, pass scopes, cycles, save/restore, and retry. Its movement trigger, simultaneous order, Shield Block, sibling-offer revalidation, and nesting questions are correctly unsettled. The final revalidation decision should distinguish a latched historical trigger from mutable requirements and target validity; this completes the named oracle, not a second reaction architecture.
- [Package loading](definitions-instances-packages.md#atomic-loading-and-precise-failure) fails closed on unsupported inventories, missing capabilities, and digest mismatch. [Evidence dimensions](../03-verification-strategy.md#independent-evidence-dimensions) correctly separate source, isolation, generalization, production, continuous, client, and performance proof.
- Larger footprints, reach, terrain costs, areas, elevation, flight, climb, swim, and other movement modes are explicitly outside the first gate. That is not a defect. Initial diagonal movement remains a [STATUS scope decision](../../../STATUS.md#unresolved-decisions): if excluded, queries/commands must reject diagonal steps; if included, S05b requires a turn-wide diagonal ledger that survives save and resets only at end turn.
- Counteract is absent from the closed operation families and roadmap, so its absence is not F09. Keep it unsupported until a separate `core.counteract@1` packet can reproduce B01 from [Counteracting](https://2e.aonprd.com/Rules.aspx?ID=3280) and [Dispel Magic](https://2e.aonprd.com/Spells.aspx?ID=1493); do not compose ad hoc check/effect operations in content.
- Continuous evidence already begins from a reviewed legal setup and changes state only through public commands. Exploration-to-encounter and encounter-to-exploration transitions are therefore unpromised, not a defect. If expanded later, B02 shows the need for typed begin/end procedures, secret initiative projections, tie prompts, and mode-preserving saves. Sources: [Encounter Mode](https://2e.aonprd.com/Rules.aspx?ID=2421), [Roll Initiative](https://2e.aonprd.com/Rules.aspx?ID=2423), [Avoid Notice](https://2e.aonprd.com/Actions.aspx?ID=2622), [End Encounter](https://2e.aonprd.com/Rules.aspx?ID=2426).

## Appendix A — Reproducible scenario index

| ID | Fixed input and sequence | Expected result or decision exposed |
| --- | --- | --- |
| S01 | Inventory Electric Arc from its entry only; compile basic-save, degree, and damage dependencies. | Closure fails unless every linked semantic leaf has an approved inventory/fact-set path. |
| S02 | Start with 3 normal actions. Begin Stride, commit its cost, suspend for a reaction, save/retry/resume, then use two Strikes and attempt a fourth action. Later probe: slowed 2 plus one Stride/Strike-only quickened credit attempts Lurching Charge; save after qualifying Grab/Rend Strikes and insert miss/retarget/intervening-action/round variants. | Resume retains 2 credits and retry never double-spends; the fourth action rejects unchanged. The restricted credit cannot fund the activity. Later result tokens expire on the named negative variants. |
| S03 | Attack modifier +15, agile weapon, AC 30. Make one Strike and Ready the agile Strike. Branch A has one fortune and one misfortune; supply d20=20. Branch B has two eligible fortune providers whose test receipts return 5 and 20; save before the owner selects F2 and before its draw, then select F2. | In A the effects cancel automatically; stored second-attack agile MAP is -4; total 31 succeeds, then natural 20 raises it to critical success. In B F2 returns 20; the owner selection, provider position, and draw persist, so retry neither reprompts nor redraws. |
| S04 | One effect: 7 slashing + 3 precision slashing + fire additions 4 and 2. Target: precision immunity, weakness slashing 3, weakness fire 5, resistance physical 8, resistance all 5; choose all-resistance against fire. Separately, rank-1 two-action Heal/Harm with d8=4 targets a living/undead creature at 5/20 HP. | Precision is removed; each weakness activates once; results are 2 slashing + 6 fire = 8 total. Heal a living creature or Harm a willing undead for 12, ending at 17 HP. Production rejects Shield Block-dependent content until its ordering oracle is approved; a candidate-only test may use an explicitly provisional policy without support credit. |
| S05 | Save beside cell B in `map:test` where B is blocked; restore in another process where the same ID marks B clear. Conditional S05b: Speed 20, move one diagonal, save, then submit three diagonals in the same turn and again after end turn. | Restore rejects the changed scene digest. If diagonals enter scope, the second path costs 25 and is illegal; after reset, three diagonals cost 20 and are legal. |
| S06 | At start turn, dying 3 with fast healing 1 and a supplied recovery critical failure; choose healing-first and recovery-first branches. Separately, critically reduce wounded 1 and wounded 2 PCs to 0. Also track slowed 2/1 with 1-/6-round durations, and compare Stench immunity across sources with source-specific Frightful Presence immunity. | Healing first yields HP 1, removes dying/unconscious, and gains wounded 1; recovery first kills. Wounded 1 offers Orc Ferocity; on decline, move initiative, gain dying 2, then add wounded to reach dying 3. Wounded 2 is immediately killed and receives no Orc Ferocity offer. Latent slowed 1 emerges; reduction affects both contributions. Immunity scopes differ as printed. |
| S07 | Enemy at `[4,4]`: hidden to A, undetected to B, concealed to C. A supplies flat 12 then attack 10 at +10 vs AC 20. Run three B branches: target wrong square `[4,3]`; target `[4,4]` with flat 10; target `[4,4]` with flat 12 then attack 9 at +10. C supplies flat 4. Save before every secret check. | A passes DC 11 and hits. All three B branches emit the identical public miss receipt despite wrong-square, failed-flat, and missed-attack causes. C fails DC 5 and spends the action. Views/restores expose no location, cause, or draw. |
| S08 | DC 20, 20-foot burst, fixed damage 20. A Large creature overlaps by one cell but a solid wall blocks it. Another target has Reflex +8 and standard cover, supplied d20=10. A third target is undetected but unblocked. | Wall-blocked creature is excluded. Covered target totals 20 and succeeds for 10 damage. Undetected target is included without a targeted-attack flat check. |
| S09 | Actor has prepared rank-3 divine Heal (DC 25), innate rank-1 primal Heal (DC 17), and one shared Focus Point for a divine focus grant (DC 25) and primal focus grant (DC 21). Branch A casts the two-action prepared Heal; Reactive Strike critically disrupts it; save at the reaction. Branch B uses innate one-action Heal against hostile undead: Fortitude total 18, d8=6. Branch C queries both focus grants, casts the divine spell, then attempts the primal one. Separately spend and transfer a once/day item, then restore. | A spends only the prepared slot and two actions and produces no effect. B uses rank 1/primal/DC 17 and deals 3 after the successful basic save. C reports each grant's own tradition/DC, spends the single shared point, and rejects the second cast. Retry is idempotent; the transferred item remains spent. |
| B01 | Counteract rank 3 targets rank-4 effect at DC 24; supply total 24. | Current AoN result is success and rank limit +1 permits counteraction. This remains unsupported until a typed procedure and oracle exist. |
| B02 | From exploration, one PC Avoids Notice, two PCs tie initiative, and an enemy is undetected to one viewer; save at tie order, then later end by truce. | Future-only probe: begin/end commands would need secret projections, an owned tie prompt, exact mode/state persistence, and no erased ongoing facts. |
| B03 | One Interact gives two creatures Reactive Strike offers; the first critical hit disrupts the parent and opens a nested zero-HP reaction. | Existing reaction design preserves committed children and blocks support until sibling trigger-latch/requirement/target revalidation receives its named oracle. |

## Appendix B — Consulted AoN page index

- **Actions/checks:** [Actions](https://2e.aonprd.com/Rules.aspx?ID=2335), [Ready](https://2e.aonprd.com/Rules.aspx?ID=2343), [MAP](https://2e.aonprd.com/Rules.aspx?ID=2289), [Degrees](https://2e.aonprd.com/Rules.aspx?ID=2286), [Fortune](https://2e.aonprd.com/Traits.aspx?ID=612), [Quickened](https://2e.aonprd.com/Conditions.aspx?ID=89), [Slowed](https://2e.aonprd.com/Conditions.aspx?ID=92).
- **Damage/health/effects:** [Damage](https://2e.aonprd.com/Rules.aspx?ID=2301), [Immunity](https://2e.aonprd.com/Rules.aspx?ID=2313), [Weakness](https://2e.aonprd.com/Rules.aspx?ID=2317), [Resistance](https://2e.aonprd.com/Rules.aspx?ID=2318), [Knockout](https://2e.aonprd.com/Rules.aspx?ID=2324), [Recovery](https://2e.aonprd.com/Rules.aspx?ID=2326), [Losing Dying](https://2e.aonprd.com/Rules.aspx?ID=2328), [Conditions](https://2e.aonprd.com/Rules.aspx?ID=2455), [Start Turn](https://2e.aonprd.com/Rules.aspx?ID=2428), [End Turn](https://2e.aonprd.com/Rules.aspx?ID=2430), [Fast Healing](https://2e.aonprd.com/Rules.aspx?ID=2322), [Persistent Damage](https://2e.aonprd.com/Conditions.aspx?ID=86), [Heal](https://2e.aonprd.com/Spells.aspx?ID=1554), [Harm](https://2e.aonprd.com/Spells.aspx?ID=1552).
- **Space/information:** [Grid Movement](https://2e.aonprd.com/Rules.aspx?ID=2356), [Terrain](https://2e.aonprd.com/Rules.aspx?ID=2365), [Size/Space/Reach](https://2e.aonprd.com/Rules.aspx?ID=2359), [Area](https://2e.aonprd.com/Rules.aspx?ID=2384), [Line of Effect](https://2e.aonprd.com/Rules.aspx?ID=2382), [Cover](https://2e.aonprd.com/Rules.aspx?ID=2372), [Targets](https://2e.aonprd.com/Rules.aspx?ID=2380), [Detection](https://2e.aonprd.com/Rules.aspx?ID=2414), [Hidden](https://2e.aonprd.com/Conditions.aspx?ID=79), [Undetected](https://2e.aonprd.com/Conditions.aspx?ID=96), [Concealed](https://2e.aonprd.com/Conditions.aspx?ID=62).
- **Spells/resources/transitions:** [Spell Chapter](https://2e.aonprd.com/Rules.aspx?ID=2221), [Focus Spells](https://2e.aonprd.com/Rules.aspx?ID=2228), [Innate Spells](https://2e.aonprd.com/Rules.aspx?ID=2232), [Casting](https://2e.aonprd.com/Rules.aspx?ID=2233), [Disruption](https://2e.aonprd.com/Rules.aspx?ID=2236), [Limited Activations](https://2e.aonprd.com/Rules.aspx?ID=3143), [Counteracting](https://2e.aonprd.com/Rules.aspx?ID=3280), [Encounter Mode](https://2e.aonprd.com/Rules.aspx?ID=2421), [Initiative](https://2e.aonprd.com/Rules.aspx?ID=2423), [End Encounter](https://2e.aonprd.com/Rules.aspx?ID=2426), [Avoid Notice](https://2e.aonprd.com/Actions.aspx?ID=2622).
- **Published stressors:** [Electric Arc](https://2e.aonprd.com/Spells.aspx?ID=1509), [Dispel Magic](https://2e.aonprd.com/Spells.aspx?ID=1493), [Reactive Strike](https://2e.aonprd.com/Actions.aspx?ID=2256), [Shield Block](https://2e.aonprd.com/MonsterAbilities.aspx?ID=75), [Orc Ferocity](https://2e.aonprd.com/Feats.aspx?ID=4514), [Grab](https://2e.aonprd.com/MonsterAbilities.aspx?ID=45), [Rend](https://2e.aonprd.com/MonsterAbilities.aspx?ID=73), [Stench](https://2e.aonprd.com/MonsterAbilities.aspx?ID=76), [Frightful Presence](https://2e.aonprd.com/MonsterAbilities.aspx?ID=64), [Lurching Charge](https://2e.aonprd.com/Monsters.aspx?ID=3088).
