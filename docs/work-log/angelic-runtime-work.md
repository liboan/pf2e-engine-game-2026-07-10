# Accepted caster: Angelic Sorcerer

## Purpose and boundaries

The selected level-1 Angelic build is accepted and available through the ordinary CLI. Its selected spell and recovery behavior has independent public-play evidence; the final admission also exercises real command-line Heal and a saved Blood Magic willingness choice. See the [admission record](angelic-admission-work.md) and [current work](ACTIVE.md). The detailed stages below retain the implementation history and source contract; they are not an outstanding delivery queue. Broader Sorcerer options and offensive undead Heal remain outside the accepted slice.

The first encounter uses supported living participants. Do not expand the monster catalog merely to demonstrate this class. Offensive Heal needs correct undead targeting and health behavior before it is advertised; keep that separate from claiming a completed living-party healing route. Read Aura and item identification are optional deferred content, replaced by shared Light in the selected Warpriest preparation. Record target boundaries explicitly rather than approximating them.

## Legal level-1 selection

- Angelic divine Sorcerer, Human/Skilled Human/Natural Skill and a legal Farmhand background with Assurance(Athletics).
- Proposed attributes: Str +1, Dex +2, Con +2, Int +0, Wis +0, Cha +4. HP 16, unarmored AC 15, spell attack +7/DC 17, Fort/Ref/Will +5. The owner must record legal boosts and distinct skill grants before admission.
- Cantrips: bloodline Light, plus Divine Lance, Void Warp, Guidance and Stabilize.
- Rank-1 repertoire: bloodline Heal, plus Fear and Runic Weapon. Three interchangeable rank-1 slots.
- Angelic Halo, one Focus Point. No ordinary level-1 Sorcerer class feat; reserve Reach Spell for level 2 rather than adding Natural Ambition now.
- No signature spells, automatic holy sanctification, deity obligations or later bloodline powers.

Sources: [Sorcerer](https://2e.aonprd.com/Classes.aspx?ID=62), [Angelic bloodline](https://2e.aonprd.com/Bloodlines.aspx?ID=20).

## Class rules that must be real

**Angelic Halo:** one action, concentrate, focus, holy and aura; no manipulate trait. Spend one focus point. For one minute, allies currently within the 15-foot emanation regain +2 status HP from rank-1 Heal. The caster is not their own ally, and another character's Heal can qualify. Evaluate the recipient's location when healing resolves. Do not inherit unrelated Champion aura suppression rules.

**Blood Magic:** Halo cast with focus and Heal cast with a slot trigger Divine Aura; Light, Fear and Runic Weapon do not. Choose caster or an eligible spell target before initial resolution, preserving that choice through interruptions and saves. After initial checks, grant +1 status saves for one round. An unwilling foe needs the appropriate successful attack or failed save. Preserve the selected source's replacement/expiry rule.

Independent review of the new concealment gate found and isolated a lost self benefit: a failed Heal targeting check prevents effects on that concealed target, but still permits Blood Magic explicitly selected for the caster. Critical action disruption prevents both. The public review uses actual injury and a saved failed flat check. A bounded repair now invokes the existing Blood Magic helper only for the caster recipient on this failure path; disruption remains unchanged. The expected-failure marker was removed: **all three review cases and 56 adjacent dim/persistence/Light checks pass**. [Blood Magic](https://2e.aonprd.com/Bloodlines.aspx), [Concealed](https://2e.aonprd.com/Conditions.aspx?ID=62), [Disrupting Actions](https://2e.aonprd.com/Rules.aspx?ID=2342). All review and repair pytest processes exited; host process enumeration was sandbox-denied.

**Sorcerous Potency:** initial slot-cast damage/healing gains +1 status per creature at rank 1. It does not apply to cantrips, focus spells or later attacks with Runic Weapon. Inside Halo the ally receives the stronger +2 status benefit, not +3; the Sorcerer's own Heal gets Potency but not their own Halo.

Sources: [Halo and stacking clarification](https://2e.aonprd.com/Spells.aspx?ID=2093), [Blood Magic timing](https://2e.aonprd.com/Bloodlines.aspx), [Sorcerous Potency](https://2e.aonprd.com/Classes.aspx?ID=62).

## Selected spells and shared mechanics

- **Heal:** retain ordinary action modes, willingness/self-inclusion choices, genuine targets and one resource spend. Two-action healing adds 8 and reaches 30 feet; touch does not. Three-action healing uses the 30-foot emanation and optional caster inclusion. Offensive undead use is a separate supported-target boundary until correct target/health semantics exist; never infer living status merely from positive HP. [Heal](https://2e.aonprd.com/Spells.aspx?ID=1554).
- **Fear:** the [bounded Fear/Flee packet](fear-runtime-work.md) defines real escape actions and a closed-scene convention. A rank-1 Will spell within 30 feet. Four outcomes give no condition/frightened 1/2/3; critical failure also flees for one round. Fleeing must constrain real actions and movement away from the source. A bounded grounded route is enough; no general opponent AI is needed. [Fear](https://2e.aonprd.com/Spells.aspx?ID=1524).
- **Runic Weapon:** touch a real unattended weapon or one wielded by a willing creature. For one minute it gains +1 item attack and two weapon dice. Do not add duplicate bonuses over existing runes or overwrite permanent attachments. Preserve the temporary benefit through item drop/retrieve/save and remove it at expiry. [Runic Weapon](https://2e.aonprd.com/Spells.aspx?ID=1658).
- **Light:** a real orb within 120 feet, bright 20 feet plus dim 20 feet, lasting until the caster's daily preparation. Support willing attachment, Sustain movement up to 60 feet, attach/detach, Dismiss, and choosing which old orb ends on the fifth cast. Save orb identity and position/attachment. Selected scene illumination must have an observable consequence; a decorative label is not sufficient. Keep unselected invisibility and illusion systems outside this slice. [Light](https://2e.aonprd.com/Spells.aspx?ID=1585).

The selected longsword and shortsword families now use stable saved physical-item identity through the existing equipment path. Runic Weapon follows that item across release, retrieval and a compatible new wielder; it does not use a floating actor bonus. Gear outside this finite conversion retains its existing representation. The [Runic packet](runic-weapon-work.md) records the implemented boundary and evidence.

## Small local recovery interface

The [concrete local recovery packet](local-recovery-work.md) selects commands, clock ownership, carried character state, health/equipment guards and staged tests. It reuses the same encounter handle, not a separate party or campaign layer.

Reuse existing casting-source, resource, access-validation and focus helpers. Extend the prepared-only public adapter to genuine spontaneous and focus spends without a second resource ledger.

Expose real out-of-combat Refocus and daily preparation, preserving resource state into another scene. Refocus advances ten minutes and restores one focus point up to capacity; it does not refill spell slots. Daily preparation requires explicit rested/once-per-day eligibility, refills the relevant resources and ends that caster's Lights. Daily preparation will use an explicit declaration of externally adjudicated rest eligibility, not pretend to simulate sleep, natural HP recovery, armor/fatigue or condition recovery. No campaign simulator is needed. The current save invariant tying elapsed world seconds directly to round number must be replaced with an explicit local elapsed-time fact; effect and immunity expiry must use that fact consistently.

Sources: [Refocus](https://2e.aonprd.com/Actions.aspx?ID=2621), [bloodline recovery](https://2e.aonprd.com/Bloodlines.aspx), [daily preparation](https://2e.aonprd.com/Rules.aspx?ID=2440&Redirected=1).

## Narrow Warpriest closure

The [concrete preparation packet](warpriest-utility-work.md) defines the legal Light substitution, alternate Sure Strike preparation, fortune integration and explicit unused-expiry interpretation. It is source-checked design, not implemented coverage.

**Use Light as the fifth cantrip.** Read Aura was an optional prepared placeholder with combat rejection; its exploration procedure was never implemented. Astra verified that no selected class/deity/ancestry/background grant requires it. Substitute common divine Light, preserving the other cantrips, statistics and slots, and test the prepared-caster route. Defer Read Aura/Identify Magic and their item-knowledge/secret-check machinery from S3i; retain the [source research as history](archive/warpriest-utility-before-cantrip-simplification.md). [Cleric](https://2e.aonprd.com/Classes.aspx?ID=33), [Light](https://2e.aonprd.com/Spells.aspx?ID=1585), [Iomedae](https://2e.aonprd.com/Deities.aspx?ID=285).

**Sure Strike:** one action, concentrate and fortune. The next attack before turn end rolls twice and chooses the better; it ignores circumstance attack penalties and concealed/hidden targeting flat checks. It does not ignore MAP, status penalties or cover's AC bonus. Preserve both dice and consumption through saves, enforce fortune incompatibility and ten-minute immunity. Existing Warpriest preparation has two ordinary Heals plus four font Heals: provide a legal alternate preparation replacing one ordinary Heal, not an extra slot. [Sure Strike](https://2e.aonprd.com/Spells.aspx?ID=1709).

## Ownership and phased acceptance

One Luna owner completes each bounded playable outcome across the necessary runtime, saved validation, terminal and tests, staying through ordinary review repairs. Family handlers may remain separate files; effects/resources stay authoritative in the engine and the terminal presents choices. The numbered phases below are implementation checkpoints rather than required handoffs. Reuse existing source packets and close the current caster milestone before new future-class research.

1. Legal staged Sorcerer; first real cantrip and spontaneous Heal with mandatory Potency and Blood Magic, saved at a genuine recipient/willingness choice with exactly one slot spent.
2. Halo and its interaction with Blood Magic, Potency, another caster’s Heal and focus exhaustion through real play.
3. Selected Fear, Runic Weapon and Light behavior, with the applicable supported-environment boundaries explicit.
4. Actual local recovery/preparation, prepared Warpriest Light and alternate Sure Strike preparation.
5. Complete healthy party combat with real incoming damage, Halo/healing, selected offensive/buff spells, saved decisions and victory. Refocus afterward preserves spent slots while restoring focus; a second scene proves persistence. Verify legal daily preparation separately.

Focused tests cover Halo 15/20-foot boundary, self exclusion and another caster's Heal; strongest status bonus; saved Blood Magic and expiry; fourth slot/second focus cast atomic rejection; Fear's actual fleeing; runic item expiry and identity; Light movement/replacement/preparation; Sure Strike fortune and immunity. Distinguish helper checks, targeted sequences and completed encounters. Run focused checks as each path works, then a serial broad/memory checkpoint when coherent.

## Next bounded slices and remaining aura evidence

Fear/Flee, Halo, the physical weapon bridge, actual Runic Weapon and Light's selected casting/control path have passed independent play and integration checkpoints. The remaining dim skill/item connections and local recovery are the next bounded assignments. The [Runic packet](runic-weapon-work.md) retains the item/casting evidence; the [Light packet](light-runtime-work.md) retains completed dim play; the [recovery packet](local-recovery-work.md) preserves the same party across scenes.

Preserve the completed Halo fight: real injury, strongest +2 status healing, saved Blood Magic recipient, one focus and one slot spent, victory. The later-initiative public duration test also preserves the aura at the round wrap and expires it at the caster’s turn. Cross-caster healing and actual recipient movement now have retained public evidence in `tests/test_halo_cross_caster_play.py`: a healthy-start fight uses two ordinary Angelic Sorcerers, an injured Fighter and the dog. The second caster's two-action Heal restores 14 HP inside the first caster's Halo, using only the +2 status benefit. After the Fighter Strides from 10 to 25 feet from the source and takes another actual injury, Heal restores 13 HP with only +1 Sorcerous Potency. The real willingness pause survives save/load, and the encounter ends through public Strike/Hero commands. The new case passes; its focused Halo group reports **18 passed**. All pytest processes exited. Existing focused self-exclusion/stacking tests remain distinct from this complete public encounter.

## Shared spell-condition repair completed

The Thief checkpoint corrected and tested live conditions in spell attacks, saves and caster DCs, including matching saved-check validation. The investigator’s public Demoralize → Void Warp case now uses 12+5−2=15 against DC 17 and deals 4 damage. Preserve these shared helpers when connecting the Sorcerer. Blood Magic must affect applicable saving throws and the corresponding defense DCs.

## Execution state

The [active recovery page](ACTIVE.md) holds current counts, owners and next action. Completed public evidence includes Halo healing after real injury, cross-caster healing and actual aura-boundary movement, Fear with saved reaction movement, Runic Weapon with saved casting/item transfer, and useful Light placement/Sustain in a completed dim fight. Skill/item dim targeting, preparation and local recovery have since passed their acceptance checks, and ordinary CLI admission is complete. The detailed history below is evidence, not an active queue.



The staged setup is `sorcerer_angelic_first_cast`: `angelic_sorcerer` blue at (1,2), `sorcerer_ally` blue at (2,2), and `sorcerer_dog` red at (5,2). Public casts use source `angelic_repertoire` and rank pool `angelic_rank1` with capacity 3. Resource inspection exposes `spontaneous_slots`. Three-action Heal choices proceed through self-inclusion, Blood Magic recipient and willingness as applicable. The save/load lookup accepts the staged setup without promoting it to playable catalog maps.

Preserve the review fixes: single/area Blood Magic, one active effect per caster including different-recipient replacement, rolled saves and save DCs, hostile living Heal recipient exclusion, exact saved resource/recipient validation, nine trained skills and fist +5. The first long implementation run was interrupted for a handoff; the later independent review is the acceptance evidence.


### Independent first-cast findings

Sol executed three-action Heal and confirmed one rank slot spent, saved self-inclusion/recipient ordering, and shared healing with Potency, but the selected Blood Magic effect was absent. Two-action Heal applied the effect, yet Fortitude/Reflex/Will DCs omitted its +1. Both are assigned narrow fixes with public regression cases. Source review also found one excess trained skill (Society) and an incorrect Farmhand boost note; the final attributes remain legal using Constitution/Charisma for the background. These findings prevent first-cast acceptance until repaired.


### Focused repair checkpoint

The independent reviewer reports 57 focused checks passing in 0.23 seconds across Sorcerer, casting, skills, Assurance and Feint. Area Heal now applies one shared die, one slot spend, Potency once per living recipient and the selected Blood Magic once. Rolled saves and defense DCs receive the effect, same-recipient refresh avoids duplicates, and saved validation checks exact value, source, duration, slot/Potency facts and willingness. The legal sheet now has nine trained skills, the correct Farmhand boost ledger and fist +5. Broad acceptance and a final distinct-recipient/resource probe are still pending.


### Halo split: first executed checkpoint

Both new owners independently ran the existing first-cast group: seven pass and one saved-continuation test fails. The exact mismatch is focus state added by the partial Halo pass: the live actor has one point/capacity one, while the loaded actor has zero/zero. The pending choice itself matches. Persistence now owns that concrete repair and seven-field timed-effect validation; runtime separately owns Halo recipients and range. No Halo cast completion is claimed from this test.


### Halo saved-duration guard

The persistence owner’s proposed initial check equated a Halo’s expiry to the current source-start count plus ten. The supervisor flagged that later-round saves must preserve the original deadline with fewer remaining turns. A later-caster-turn round trip is required; loading must neither reject a legitimate older aura nor refresh its duration. Halo’s focus continuation is distinct from Heal: `spell_source_kind=focus`, `slot_id=actor_focus_pool`, one action and zero Potency. The two owners are coordinating that explicit provenance.


### First real Halo cast delivered

The runtime owner reports a public cast that spends one focus point, offers caster/eligible ally recipients, and then applies Blood Magic and Halo; it auto-selects caster when no ally is eligible. Four focused runtime tests pass. The persistence owner reports eight prior Sorcerer cases restored and 36 focused checks passing, including eight Halo persistence cases. The independent test owner is now executing a healthy-start fight; do not count the four runtime cases as completed encounters.


### Halo persistence released

The persistence owner completed its bounded slice. A real cast/choice followed by three EndTurn calls reaches source-start count 2 and world second 6; save/load preserves Halo’s original source deadline 11 and absolute deadline 60, rather than refreshing it to 66. The combined persistence/runtime/first-cast group passes 23 checks. Separately, the runtime owner reports 52 focused checks and a public later-turn probe: aura active and save/load equal at second 54, expired at second 60. Files are being released for the continuous encounter test. These are targeted timing sequences, not another completed fight.
