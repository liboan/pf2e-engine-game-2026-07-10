# Archived typed-damage handoff

## Current checkpoint

Feint and the existing warpriest casting procedure are accepted through public saved play. The last full run passed 415 tests in 1.04 seconds at about 53.6 MiB peak child memory; a final extension of the Feint encounter to victory then passed its focused test. The Dragon family subsequently passed 37 focused checks, including eight completed healthy encounters; Cat/Frog then passed their public fights and focused checks, bringing the accepted catalog to 34 setups. [Current delivery state](../class-expansion-state.md) distinguishes accepted content from active work.

## Active owners

| Owner | Files and result |
|---|---|
| `expansion_damage_runtime_finish` | Shared damage/model/encounter/persistence and catalog: Strike path now tested. Finish spell/family integration, defended temp-HP/Hero continuations and broad acceptance. |
| Barbarian family files released | Bear, Cat, Frog and all eight Dragons complete their current public slices. Dragon/defense interaction waits for core readiness and a short follow-up. |

The shared owner completed Dragon catalog admission, and the family’s canonical initial-state map is extended. Definitions alone are not accepted play evidence. Focused tests run throughout each owner’s work; the shared owner coordinates one coherent broad checkpoint. Do not edit each other’s files.

## Typed-damage finite handoff

The first public path passes 25 focused checks. `typed_defenses_diabolic_dragon_test` starts healthy; a Diabolic critical Strike rolls 24 slashing and 8 fire. Save at attacker Hero and defender all-resistance prompts; the target `waystone_sentinel` selects `resist:fire`. The original handoff used weakness 2, producing 26/6. During review, the authored weakness was deliberately raised to 3 so the public test no longer has equal weakness/resistance cancellation: current 24/8 becomes 27 slashing/6 fire, total 33. Selected fire resistance remains 2. Wrong chooser rejects atomically; the encounter reaches victory. Original and mitigated components remain distinct.

Sol has now connected Strike, spells and family damage to the shared path. New cases exercise resisted Divine Lance, immune Void Warp with enfeebled aftermath, saved defender/Heroic Recovery choices, Bear temporary HP once and direct family-context continuation. The broad checkpoint is pending. The pending model/serializer includes full component tags, critical mode, dice, flat-only components, mitigation marker and typed defense choices. No full suite ran on this implementation yet. The prior reported family catalog is 34 before the new defense fixture; verify actual inventory at the next checkpoint.

## Next serial slice

After typed defenses pass, integrate steel shields and initial fundamental runes. The [damage/equipment handoff](damage-equipment-handoff.md) contains the exact small state, behavior, source-reviewed GM convention and public proof cases. No generic reaction framework is required.

Ranger/Monk, Rogue and the remaining Barbarian instincts still require shared runtime hooks. Keep those changes serial until their existing prerequisites work. Do not build more disconnected helper layers to create artificial parallel work.

## Decisions

Escape preserves Feint’s opening, including escape from the feinted holder; this is user-approved and tested. Physical Trip/Grapple consume an ordinary opening on commitment but receive no save-DC reduction. Mixed-damage Shield Block has a documented GM convention in the damage handoff.

Hag spell timing, broad resistance across paired attacks, and reload-0 bow manipulation remain pending. Only dependent behavior waits. The existing stable-unconscious-at-zero damage limit remains explicit.

## Completed reference

The original [Feint/casting integration handoff](feint-casting-handoff.md) is archived so the active instructions stay short. The work log preserves exact executed evidence and token accounting.

Archived after the accepted 439-test checkpoint. Active ownership and next steps are in ../queued-runtime-work.md.
