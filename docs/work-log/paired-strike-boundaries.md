# Paired Strikes and bow preparation

## Status and decision

Astra checked the existing packets, runtime boundaries and current primary rules. This is design evidence; no paired-Strike implementation or tests were added by this investigation.

Same-type paired damage has a small sequential implementation. **P1 remains for mixed damage types against a resistance spanning both types.** A September 16 source-only Astra recheck confirmed that Spring 2026 errata settles allocation but still does not specify sequential commitment timing. The structured thread question asks whether to leave only that rare combination unsupported initially (recommended), or authorize defender choice of the protected type before the first HP change. No convention has been adopted. Ordinary piercing Hunted Shot and same-type fist/fist or kama/kama Flurries can proceed independently; do not claim complete mixed kama/fist coverage against broad resistance. Current Investigator work is independent of this decision.

## Printed boundaries

Resolve separate Strikes with ordinary sequential MAP and individual reaction and health consequences. Combining for weakness/resistance does not merge them into one attack. [Hunted Shot](https://2e.aonprd.com/Feats.aspx?ID=4861), [Flurry](https://2e.aonprd.com/Classes.aspx?ID=60), [subordinate actions](https://2e.aonprd.com/Rules.aspx?ID=2335).

The source check verified Player Core Spring 2026 p.408 errata: each resistance applies once per effect, with Hunted Shot explicitly exempted from the ordinary separate-subordinate-effect treatment. For resistance spanning multiple damage types, the damaged creature chooses the protected type and may choose the most beneficial one. The text does not settle when that choice commits between sequential Strikes. [Paizo errata](https://paizo.com/pathfinder/faq).

For 4 bludgeoning followed by 10 slashing against resistance all 5, choosing bludgeoning gives total10; choosing slashing gives total9. Automatically committing to the first type removes the defender's later choice. It is an extra campaign restriction, not uniquely correct printed behavior. Changing the allocation retrospectively can change knockout and reaction eligibility, so do not implement silent rollback or pretend the ambiguity is resolved.

The source-only recheck supplies these examples, assuming both attacks hit and no other defenses apply:

| Combined damage | Resistance | Supported result |
|---|---|---|
| 4 piercing + 10 piercing | All damage 5 | 9 total |
| 4 bludgeoning + 10 slashing | All damage 5 | 9 if protecting slashing; 10 if protecting bludgeoning. Applying resistance separately to both, for 5 total, is wrong. |
| 4 bludgeoning + 4 slashing | All damage 5 | 4 total. Subtracting 5 from an untyped sum, for 3 total, is wrong. |

[Current resistance text](https://2e.aonprd.com/Rules.aspx?ID=2318) and the [Spring 2026 announcement](https://paizo.com/blog/spring-errata-2026) do not prescribe rollback, simultaneous HP application or advance commitment. The announcement's advice to favor the defender where handling is unclear does not settle those timing choices. [Monastic Weaponry](https://2e.aonprd.com/Feats.aspx?ID=5979) adds no timing rule. These findings leave accepted single-event Justice protection unchanged.

Closed recheck run `paired-resistance-ruling-2026-09-16`: Astra/high, 7 requests, 332,998 input tokens (276,096 cached), 1,927 output, no compaction. It read primary rules only and made no implementation or test changes; no background process was launched. Dollar cost is unavailable.

## Small implementation boundary

For a supported same-type sequence, keep a recipient-specific shared-defense record: apply each weakness once and carry unused resistance forward. Apply component immunities separately, retaining precision, material, magical and lethal/nonlethal facts. Separate recipients have independent defenses. A second miss or interruption preserves the first hit's ordinary result.

Precision shares the weapon's damage type while retaining its immunity tag. Ranger Precision belongs to the first finalized prey hit that round, even when defenses prevent its damage. [Precision](https://2e.aonprd.com/Rules.aspx?ID=2308), [Hunter's Edge](https://2e.aonprd.com/HuntersEdge.aspx?ID=5).

Shield Block remains per attack; breakage can change the next attack's AC. Justice resistance protects its triggering Strike only. Resolve retaliation and resulting incapacitation before continuing. Do not calculate shared resistance expenditure from HP lost after Shield Block. [Shield Block](https://2e.aonprd.com/Feats.aspx?ID=5212), [Justice](https://2e.aonprd.com/Causes.aspx?ID=11).

## Bow convention

Reload 0 includes drawing ammunition in shooting, but the printed rule does not explicitly settle inherited manipulation timing. Use the delegated GM convention: included draw is manipulation; offer one combined draw/ranged reaction opportunity per shot per reactor. Preserve the established reaction-before-Grabbed-check order. Critical Reactive Strike disrupts the draw before launch; otherwise resolve the Grabbed DC5 check, then launch and attack. Retain an unlaunched arrow. A disrupted draw ends the remaining Hunted Shot activity, retaining already-completed effects and its spent action/flourish. This ordering is declared game adjudication, not a uniquely specified printed sequence. [Reload](https://2e.aonprd.com/Rules.aspx?ID=2196), [Grabbed](https://2e.aonprd.com/Conditions.aspx?ID=77), [Reactive Strike](https://2e.aonprd.com/Actions.aspx?ID=2256).

## Proposed checks

1. First piercing hit: weapon4 + Precision3; second5; piercing weakness2/resistance5. Health damage events4 then5, total9. Second miss leaves4. With precision immunity instead, events1 then5, total6.
2. Two bludgeoning hits4 and10 against resistance5: events0 then9. Mixed bludgeoning/slashing against resistance all remains subject to the pending scope decision.
3. Hits4 and8, no other defenses, Hardness5 Block on the first: character loses0 then8; shield loses0. Separate attacks retain separate defense opportunities.
4. Grabbed bow: pay, reaction, DC5, launch. Critical disruption skips flat/attack dice and retains the arrow. Flat4 fails and retains it; flat5 permits firing.

Existing helpers lack the core subordinate-Strike connection and shared-defense record; grabbed reload-0 currently rejects. Add only the saved sequence/defense facts and draw check when this family is scheduled. No projectile framework is needed. Research commands exited; no code, tests or background processes were launched.
