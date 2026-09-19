# Paired Strikes: resolution and the remaining allocation decision

Source/design investigation, 2026-09-15. No runtime edits or tests. Thread `01a0a728-f649-7162-b58f-3f18ea81ac95`. This note is an implementation handoff, not evidence that either activity works.

## Verdict

**Do not roll both Strikes, combine everything by target, and perform one HP/reaction event.** Combining is expressly for resistance and weakness. A shared defense group is useful arithmetic input; it is not a replacement for two Strike events. In particular, the second attack must observe intervening reactions, first-hit critical effects, knockout, and changed target legality.

The general sequential flow is supported by the rules below. However, the sources do **not** specify how the combined resistance/weakness adjustment is allocated between those sequential hits. A chronological allocation is a small, practical GM convention; it must be identified as such. A broad resistance that may cover different types on successive hits exposes a further choice-timing ambiguity that a cumulative-total subtraction alone cannot solve.

## Source facts

1. [Flurry of Blows, PC2 p.116](https://2e.aonprd.com/Classes.aspx?ID=60): two unarmed Strikes, ordinary sequential MAP; combine damage for resistance/weakness only when both hit the same creature. Neither same target nor same unarmed attack is required. This supports choosing the second legal attack and target when that subordinate Strike starts; no text requires declaring both up front.
2. [Hunted Shot, PC1 p.157](https://2e.aonprd.com/Feats.aspx?ID=4861): requires a ranged weapon with reload 0; both Strikes use the required weapon and target hunted prey. It uses normal MAP and the same combination clause. At these levels, with one prey, it does **not** grant arbitrary retargeting when prey drops. Choosing a new prey is another action and cannot be inserted.
3. [Actions, PC1 p.414](https://2e.aonprd.com/Rules.aspx?ID=2335): subordinate actions keep ordinary traits/effects except explicit modifications; their cost is already included. Finish one action before another; triggered reactions/free actions can occur inside another action. Thus neither attack requires another action payment, but both retain their own triggers.
4. [Spring 2026 PC1 p.408 errata](https://paizo.com/pathfinder/faq): each weakness/resistance applies once to an effect; subordinate actions normally have separate effects, with Hunted Shot explicitly cited as an exception. Broad resistance is used once, against a damage type chosen by the defender. Multiple resistances assigned to one type do not stack. Damage-type and material weaknesses may both apply. These rules establish the final shared defense arithmetic, not the chronology for committing two HP changes.
5. [Shield Block, PC1 p.262](https://2e.aonprd.com/Feats.aspx?ID=5212) responds to physical damage from an attack with a raised shield; it uses Hardness and damages the wielder and shield with the remainder. Hardness is not resistance. Combining for resistance does not make two Strikes one Shield Block trigger or authorize blocking their combined total. A first block can break the shield before Strike 2, changing AC.
6. [Justice/Retributive Strike, PC2 p.92](https://2e.aonprd.com/Causes.aspx?ID=11): enemy damaging ally is the trigger; aura requirements apply; resistance is specifically against the triggering damage, with a possible retaliatory Strike. Preserve the reaction's Strike origin and limited scope. Do not automatically extend newly granted resistance to a later attack. The interaction of this temporary, trigger-scoped resistance with a shared group needs the allocation convention below; the text does not explicitly settle it.
7. [Limitations on Triggers, PC1 p.415](https://2e.aonprd.com/Rules.aspx?ID=2339): one action per trigger per creature; multiple creatures may react. GM settles ambiguous simultaneous ordering. Two subordinate Strike triggers are not automatically one trigger. A first-hit reaction must resolve before advancing when it changes the actor, defender, or next attack.
8. [Reactive Strike](https://2e.aonprd.com/Actions.aspx?ID=2256) can trigger from each ranged attack; only a triggering manipulate action is disrupted by its critical hit. Its own Strike ignores and does not increase MAP. Do not add manipulate to Hunted Shot just because it shoots arrows. A reaction that incapacitates the attacker can prevent further attacks.
9. [Precision damage](https://2e.aonprd.com/Rules.aspx?ID=2308) shares the underlying attack's damage type but retains precision immunity eligibility. [Precision hunter's edge](https://2e.aonprd.com/HuntersEdge.aspx) applies to the first hit on prey in the round, even if defenses prevent its damage. Commit that use when the hit is final; misses and abandoned reroll results do not consume it. It is not one precision bonus per combined group chosen afterward.
10. [Getting Knocked Out](https://2e.aonprd.com/Rules.aspx?ID=2324) attaches dying/nonlethal consequences to the effect that reaches zero; the critical status of some other Strike cannot replace that provenance. [HP rules](https://2e.aonprd.com/Rules.aspx?ID=2319) require temporary HP first and describe unconsciousness, falling prone, and dropping held items. [Hero Points](https://2e.aonprd.com/Rules.aspx?ID=2333) preserve a reroll for each eligible check and recovery at each qualifying dying increase. Keep the pre-existing stable-unconscious-at-zero positive-damage boundary explicit.

## Smallest concrete flow

Use a two-step continuation around the existing ordinary Strike flow. No universal activity framework is required.

1. Validate activity eligibility and first Strike inputs, pay one action and mark flourish once. Create the parent continuation; do not pre-roll or reserve a second target/attack as authoritative.
2. Choose/validate Strike 1's weapon or unarmed attack, target, lethal/nonlethal choice, and any ordinary pre-roll options. Run ordinary ranged-trigger reactions and their continuations. Roll/check, offer permitted fortune/Hero options, finalize degree, and update MAP exactly once for the attack actually made.
3. On a hit, resolve its ordinary damage roll and critical-only terms separately. Consume first-hit features here. Preserve raw typed components and tags. Apply immunity per component/Strike; do not let one Strike's magical/material/nonlethal traits contaminate the other.
4. Resolve this Strike's defense allocation using the agreed policy below. If policy/choice is unresolved, pause before irreversible health/reaction consequences; do not secretly choose the largest component or roll Strike 2 to look ahead.
5. Offer and resolve this Strike's damage reactions using its own trigger and source context. Re-evaluate the mitigation as a reaction requires. A reaction scoped to this Strike is not a permanent addition to the target's defenses or to every component in the pair. Resolve Shield Block against this event, including shield HP/broken state. Preserve normal core ordering, with explicit GM ordering where simultaneous reactions conflict.
6. Apply this Strike's final temporary-HP/HP change once. Resolve knockout, Heroic Recovery, on-hit/critical effects and any resulting continuations at their ordinary rule timing. Do not defer an effect that affects Strike 2 merely because defense accounting remains open.
7. Only after Strike 1 is settled, expose the second-Strike selection. Recompute legal targets, attack profiles, range/reach, concealment, modifiers, AC, and current reaction availability. FoB may select another legal unarmed attack/target. Hunted Shot remains restricted to prey and its required weapon. If the actor cannot continue or no legal second Strike exists, end the remaining activity without refund; do not fabricate a second roll.
8. Run the same Strike flow for Strike 2. Join its defense ledger with Strike 1 only for the same recipient and two finalized hits. A miss/different recipient leaves the first mitigation intact. End the continuation after all second-hit consequences; retain a reviewable event record.

Steps 4–6 cannot be implemented by passing one aggregate damage number to the ordinary health function. Nor should a second critical hit retroactively double Strike 1 or change its knockout cause.

## Narrow adjudication needed before dependent implementation

### A. Recommended convention: chronological defense allocation

For a stable defense set with no unresolved broad-type choice, calculate mitigation of the first hit, commit that hit, then carry forward resistance capacity already used and weaknesses already applied. On a second hit to that recipient, apply only the remaining shared adjustment. This preserves the required aggregate total and sequential Strike events.

For pure, unchanged defenses, the arithmetic can be expressed as `M(D1)` followed by `M(D1 + D2) - M(D1)`, where `M` is combined immunity/weakness/resistance arithmetic. The difference is **before** Shield Block and other event-local consequences. Never subtract actual HP loss or blocked damage: doing so would give the second hit credit for damage already blocked. Track per-type and per-source allocation, not just totals, when reactions depend on damage type. This formula is not safe if a later choice/defense change revises mitigation assigned to Strike 1.

**This earliest-eligible allocation is recommended, not specified RAW.** It assigns shared weakness to the first eligible hit and exhausts resistance from early eligible damage. Confirm it once as a project ruling before claiming complete support for affected paths.

### B. Broad resistance with future types: do not hide the gap

Example: resistance all 5; hit 1 is 4 bludgeoning; hit 2 could later be 10 piercing, or could miss/be aimed elsewhere. If the final shared effect uses resistance on piercing, hit 1 deals 4; if it uses bludgeoning, hit 1 deals 0. Choosing after hit 2 can retroactively cause a knockout before its attack roll. Locking resistance to bludgeoning on hit 1 removes a defender choice the combined-effect text otherwise allows. Deferring all HP creates the original sequential-consequence problem.

No inspected primary text supplies a unique resolution. The concrete question is when a defender commits a broad resistance type across a sequential combined-damage pair, and how that commitment works if hit 2 misses/changes target. A declared campaign convention can answer this; a claim of exact RAW cannot.

**Recommended concrete adjudication, paired activities only:** at the first eligible damage event for a particular resistance on a particular recipient, the defender chooses from the eligible damage types actually present in that event. A sole eligible type locks implicitly. Record that type for this pair; apply available capacity to the earliest eligible components, and carry any remaining capacity forward only for that type. Do not revisit the choice after seeing the second attack, and never retroactively heal, restore a shield, or undo a condition. If the resistance did not apply to any first-hit component, its choice/capacity stays untouched until it first applies. Independent recipient ledgers never consume one another's capacity.

Examples under that policy:

- Resistance all 5, B4 then P10 against the same target: first locks B, prevents 4; second deals P10. One point of B capacity remains unused. Combined arithmetic for the committed B choice is 10 damage, exactly as required; the convention prevents changing to P after the second result is known.
- Resistance all 5, B4 then B10: prevent 4 then 1, leaving total 9.
- Resistance all 5, first hit B4+F3: defender chooses B or F before this hit's reactions/health. Choosing F leaves B4 now and prevents later F up to the remaining capacity. The engine does not optimize the choice.
- First hit has no component eligible for resistance fire 5; second hit adds F6: apply 5 there. No first-hit allocation was consumed.
- Second attack misses or changes target: the first allocation remains valid; the second target starts its own defenses.

The added rule is **first-event commitment and no later reassignment**, plus earliest-component allocation. The printed rule gives the defender the eligible-type choice for the combined effect and does not say when that choice is irrevocable. This policy therefore restricts the opportunity to choose with knowledge of later damage; it does not change the once-per-effect cap or allow a broad resistance to span multiple types. A defender never loses a choice among types present at the actual first choice point. FoB's attacker still chooses attack/target 2 only after the first Strike settles. This is a focused GM timing adjudication, not an assertion of uniquely correct RAW.

**One viable alternative adjudication:** retain separate Strike rolls, check choices, hit effects, reaction identities, and damage provenance, but defer the paired damage events until both outcomes are available. Let the defender choose the broad resistance type using the complete combined group, allocate the mitigation to chronological components, and then resolve distinct per-Strike damage reactions/HP commits in order. This preserves the full-information defense choice, but first-hit damage reactions and knockout cannot inform or interrupt the already-rolled second attack. It can change the second attack's AC/target legality and permit an attack that would otherwise be prevented. It is a broader timing override and is not recommended for this engine. Merely pooling the final HP change would add further avoidable errors even under this alternative.

**Decision requested:** adopt chronological allocation A plus first-event broad-type commitment B and trigger-scoped Champion resistance C as the paired-activity convention. Until answered, pause only materially dependent paired-defense cases; ordinary first-class and single-Strike work continues. Do not silently choose either policy as RAW.

### C. Trigger-scoped Champion resistance

Recommended convention: a Champion reaction attaches only to the triggering Strike's components; any overlap with persistent/shared resistance uses ordinary non-stacking rules on those components. Resolve its retaliation and conditions before Strike 2. A newly granted trigger-only defense must never retroactively alter Strike 1 when activated on Strike 2. Confirm this scoped interpretation together with A when shared resistance is also present. The current `DamageDefense` record has no explicit per-Strike scope; represent that scope in the caller or add a narrow scope field before passing it to a combined group.

Shield Block/Champion reaction ordering for different reactors is a separate ordinary GM simultaneous-trigger decision, already covered by the core trigger rules. A paired implementation should preserve the established core policy, not invent a new one.

## Facts that must survive save/load

- Parent activity identity, actor, paid-action/flourish flags, current Strike index/stage, and child continuation identity.
- Each actually selected Strike's target, attack/item identity and snapshot, lethal/nonlethal mode, MAP-at-roll, traits/materials, complete check and fortune outcome, and whether MAP/precision/ammunition were committed.
- Ordered raw damage results with actual dice, doubled and critical-only terms, precision tags, damage types and Strike origin; never reroll on resume.
- Per-recipient shared-defense group identity; defense snapshots and applicability/scope; allocations, used weakness entries and resistance capacity/type selections; policy identifier or pending adjudication.
- Distinct offered/accepted/declined reactions for each trigger, acting reactor, reaction resource consumption, child check/Strike progress, shield damage, and mitigation stage.
- Per-Strike pre-health mitigation, event-local prevention, temporary-HP/HP commit flags, knockout provenance, post-hit/critical effects committed, and pending Hero recovery.
- Strike 2 remains unchosen until its selection point. A UI may retain a suggestion, but must revalidate and allow all legal alternatives.

## Acceptance examples to implement (not executed here)

| Case | Required assertion |
|---|---|
| No defenses; first hit nonlethally drops A | A becomes unconscious/prone and drops items before FoB offers target/attack 2; B is selectable if legal. Further positive damage to stable A reaches the existing explicit boundary. |
| No defenses; hit 1 drops a dying-rules target lethally | Correct dying and Hero recovery happen before attack 2. A critical second hit does not redefine the first knockout as critical. |
| Ordinary hit then critical hit | Double only hit 2's ordinary terms; retain each critical-only term's origin. |
| Resistance B5; two B4 hits | Shared total is 3. Under convention A, first HP event is 0, second is 3; do not independently reduce both to zero. |
| Weakness B3; B4 then B6 | Shared total is 13. Convention A gives 7 then 6; a miss or different target on Strike 2 never removes the first weakness. |
| Shield H5; no R/W; hits 4 then 8 | Blocking hit 1 prevents 4 and causes no shield damage; hit 2 still deals 8 if no further reaction. A pooled block incorrectly damages the shield by 7. |
| First block breaks shield | Strike 2 uses the changed AC; first-hit shield damage is committed before its roll. |
| Justice reaction to hit 1; no prior resistance | Resistance is limited to its triggering damage; retaliation resolves before continuation and can incapacitate the attacker. No second attack is rolled if continuation becomes impossible. |
| Precision ranger: miss then critical | Precision goes on the second finalized hit and doubles normally. Hit then critical assigns precision to hit 1 instead. Immunity does not move first-hit eligibility later. |
| Mixed typed group; resistance all 5 | One chosen eligible type receives one reduction, not 5 per type. After adopting B, the first actual eligible event selects/locks the type; later type additions never rewrite the first event. Verify B4/P10 and B4/B10 examples above. |
| Two ranged shots near a reactive foe | Preserve a reaction opportunity per ranged attack if resources permit; a first-shot decline does not mean decline of the second trigger. Save/resume at both offers and Hero choices without replaying costs/rolls. |
| Hunted Shot prey removed after first hit | No arbitrary replacement target, free Hunt Prey, second ammunition consumption, or second MAP increase for an attack never made. |

Single-Strike integration, ordinary reaction continuations, and the no-shared-defense paired path can continue while the allocation decision is resolved. The complete roster must not be accepted on those partial paths alone.
