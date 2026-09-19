# Completed class handoff: Thief Rogue
Archived after the reviewed 492-test Thief checkpoint. The design below remains reference; [current state](../class-expansion-state.md) and the [active queue](../queued-runtime-work.md) track new work.

## Purpose

After equipment and Assurance acceptance, make one legal level-1 Thief playable in a complete saved encounter. This is an Astra source/design handoff, not executed evidence. Preserve other rackets as staged references. Root received these findings through delegation.

## Selected character

Use shortsword, fist and leather armor. The staged dagger would require a thrown-weapon release/recovery path and a missing versatile mode; that inventory work is unnecessary for this first Rogue.

- Str +2, Dex +4, Con +2, Int +1, Wis +0, Cha +0; HP 18, AC 18, Speed 25.
- Perception +5; Fort +5, Ref +9, Will +5; class DC 17.
- Shortsword +7, d6+4 piercing/slashing; fist +7, d4+4 bludgeoning. No sword critical specialization at level 1.
- Skilled Human grants Medicine; Natural Skill grants Crafting and Society.
- Warrior background grants Intimidation, Warfare Lore and Intimidating Glare.
- Rogue grants Stealth, Thievery and eight other skills: Acrobatics, Athletics, Deception, Diplomacy, Nature, Occultism, Religion, Survival.
- Assurance(Athletics) is the selected Rogue skill feat; Nimble Dodge the class feat. Add one legal language for Intelligence +1.
- Background boosts Con/Dex, ancestry Str/Dex, class Dex, free Str/Dex/Con/Int. Leather plus shortsword leaves 12 gp, 1 sp.

Sources reviewed by Astra: [Rogue](https://2e.aonprd.com/Classes.aspx?ID=37), [Thief](https://2e.aonprd.com/Rackets.aspx?ID=9), [Warrior](https://2e.aonprd.com/Backgrounds.aspx?ID=445), [shortsword](https://2e.aonprd.com/Weapons.aspx?ID=398).

## Small runtime changes

1. Author the initiative statistic on each encounter placement, defaulting to Perception. The first Rogue setup uses **Deception in an observed social confrontation**. Keep this fact in state, display it at the roll/Hero choice and validate saved data against the setup. Merely selecting Stealth does not implement Avoid Notice and detection; do not advertise that broader exploration behavior.
2. Use one attacker-relative off-guard determination for conditions, prone/unconscious, flanking, Feint and Surprise Attack. Carry that fact through the Strike and Hero continuation because Feint is consumed before damage. Surprise applies in round one after Deception/Stealth initiative against a creature that has not acted.
3. Add Sneak Attack's tagged d6 precision term on every qualifying hit. Double it on critical hits; keep it separate from striking weapon dice. Existing damage defenses remove precision or resist the combined attack normally.
4. Thief changes eligible finesse melee weapon/unarmed damage to Dexterity. Keep the existing thrown-Strength distinction tested without advertising thrown inventory play. Apply condition penalties using the attack's actual damage attribute: **Clumsy 2 changes d6+4 to d6+2**, while Enfeebled does not penalize that Dexterity damage. Avoid subtracting Enfeebled twice.

Sources: [initiative](https://2e.aonprd.com/Rules.aspx?ID=2263), [Avoid Notice](https://2e.aonprd.com/Rules.aspx?ID=2442), [precision damage](https://2e.aonprd.com/Rules.aspx?ID=2308), [Remaster Clumsy](https://2e.aonprd.com/Conditions.aspx?ID=61).

## Nimble Dodge

Offer the defender a saved Use/Decline choice **before the attack die**, when the visible attacker targets the Rogue, a reaction remains and the Rogue is not encumbered. Use costs the shared reaction and adds +2 circumstance AC against that attack only. Decline preserves the reaction. Preserve the decision through the attacker's Hero reroll and nested Reactive Strike continuation; do not offer or charge twice. Include ordinary weapon attacks and Divine Lance, but not save-only spells. Respect existing circumstance stacking and actual carried Bulk.

Source: [Nimble Dodge](https://2e.aonprd.com/Feats.aspx?ID=4916).

## Evidence and delivery

One owner has the shared encounter/model/save/catalog files. First execute a real Sneak Attack with the legal sheet, then add pre-roll Nimble choices and saved continuation. Run focused tests after each working path. The terminal needs only the appropriate initiative label and existing numbered choice handling unless execution shows another gap.

Focused checks cover qualifying versus ordinary hits, repeated Sneak Attack, critical doubling, precision defenses, Dexterity damage/Clumsy, first-round expiry, reaction availability, encumbrance, circumstance stacking and spell/reaction attacks. Save at Nimble, then at the attacker's Hero choice, and compare restored/uninterrupted dice, events, reaction, MAP and HP.

Complete one healthy encounter through Deception initiative, first-round Surprise hit, enemy attack with saved Nimble, later-round expiry, Feint or flanking restoring Sneak Attack, and victory. A short targeted sequence is not a completed encounter. One serial broad integration run follows the coherent slice.

## Unverified edge

Whether reacting before a creature's first turn ends Surprise Attack's “has not acted” eligibility remains unverified. A structured question is pending with the user; the recommended local convention keeps eligibility until the first turn starts, but no answer is assumed. The initial encounter can avoid this edge. Resolve it before admitting a scenario that depends on it; ordinary first-turn count evidence does not settle it.
