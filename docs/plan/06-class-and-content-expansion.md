# S3i extension: sixteen representative classes, then level 2

## Goal and approved scope

Make all sixteen Player Core 1/2 classes playable in the local Python engine, using representative subclasses and limited common content. Finish the selected level-1 builds first, then their level-2 progression, then review the working implementation for useful simplification and reuse.

This user-approved scope replaces the earlier requirement to implement every printed subclass and nested option. Preserve already accepted content, including the eleven Barbarian builds. More animals, bloodlines, schools, domains, stances or research fields are optional future breadth; completing a list is not a reason to put them ahead of another class.

The smaller selection does not relax correctness. Each advertised choice needs its actual fixed grants, legal statistics/resources, applicable rules, complete encounter use and saved continuation. Ordinary selectable feats/spells/formulas use a curated menu. Printed starting counts still apply: a smaller catalog cannot leave a character's book or mandatory choices illegally empty.

## Acceptance categories

- **Accepted play:** executed public behavior with relevant saved decisions and a completed encounter. Keep exact supported build and environment limits visible.
- **Staged:** definitions, helper tests or source contracts exist, but the public class path is incomplete. Do not count these as playable classes.
- **Deferred:** an unselected subclass, nested choice or optional content item. Its source research may remain as reference; it is not an active completion obligation.

Class coverage means at least one correct representative per class at the active level. One or two examples suffice for nested menus. Optional second representatives do not gate acceptance. Preserve accepted level-1 variants while advancing the representative roster to level 2; inexpensive shared progression can cover more variants when it is actually tested.

## Representative roster

| Class | Selected representative | Required distinctive behavior and current state |
|---|---|---|
| Fighter | Existing melee/shield Fighter; retain accepted variants | Mandatory class package, selected Assurance and sheet corrections verified in the current fixed builds. |
| Barbarian | Preserve Bear, Cat, Frog and eight accepted Dragons | Accepted level-1 choices. Further animals/instincts are deferred. |
| Cleric | Existing Iomedae Warpriest | Accepted selected level-1 casting package, with actual Light and the legal Sure Strike alternate; offensive undead Heal remains explicitly unsupported. |
| Rogue | Thief, Nimble Dodge | Accepted fixed level-1 build: Sneak/Surprise, Dexterity damage, saved defensive reactions and completed API/terminal play. |
| Ranger | Precision, Hunted Shot | Staged helpers: Hunt Prey, per-round Precision, paired attacks, range and ammunition. |
| Monk | Monastic Weaponry, kama/fist preset | Staged helpers: Powerful Fist, Flurry, weapon substitution and kama Trip. |
| Champion | Justice, Iomedae, Lay on Hands, Desperate Prayer | Selected level-1 slice accepted after source-checked complete play: aura, holy attacks, protection/retaliation, allied Shield Block, saved Hero choices, caster-timed healing AC and focus/daily resources. Undead Lay on Hands remains unsupported. |
| Investigator | Forensic Medicine, Known Weaknesses | Staged: Devise/Strategic Strike and Forensic Battle Medicine have accepted complete-fight, saved-choice and terminal evidence; the healing cooldown also survives scene transfer. Shared Knowledge and Known Weaknesses have accepted independent saved-play evidence; Forensic examination is also accepted. Leads/Clue In, Skill Stratagem and selected Streetwise remain. Partial capabilities do not establish full class support. [Selected packet](../work-log/investigator-runtime-work.md). |
| Swashbuckler | Braggart, Flying Blade | [Selected packet](../work-log/swashbuckler-runtime-work.md): Demoralize/Tumble Through bravado, panache, Precise Strike, finisher and thrown attacks. The first Demoralize/panache/ordinary attack path passed source-checked independent play, integration and terminal-probe resource repair. Melee Confident Finisher is accepted; Tumble Through is the active next outcome. Tumble Through and thrown Flying Blade still gate full class admission. |
| Alchemist | Bomber, Quick Bomber | Staged resource/item helpers: finite formulas, preparation/vials, activations, splash and lifetimes. |
| Bard | Maestro | Repertoire, Courageous Anthem, Counter Performance, Soothe, Lingering Composition and focus capacity. |
| Druid | Storm, Animal Empathy | Prepared primal spells, Shield Block, Voice of Nature, Tempest Surge and tested Storm Born weather behavior. |
| Oracle | Life | Repertoire, Vitality Lash/Soothe, Life Link, Nudge the Scales, curse limits and healing penalty. |
| Sorcerer | Angelic | Selected level-1 package accepted and available in the ordinary CLI: grants, repertoire, Light/Heal, Halo, Blood Magic, Potency and recovery have source-checked public evidence, including a real command-line cast and pending-choice save/load. Offensive undead Heal remains unsupported. |
| Witch | Faith's Flamekeeper, Patron's Puppet | Prepared divine spells, Command/Stoke the Heart, a real familiar, temporary HP, hex limits and Sustain. |
| Wizard | Battle Magic, Spell Substitution | Curriculum, Force Bolt, legal spellbook/slots, Arcane Bond and ten-minute substitution. |

Rows without accepted evidence are selected work, not support claims. The [delivery state](../work-log/class-expansion-state.md) records current evidence. A Storm Druid needs actual weather behavior; a Witch needs a functioning familiar; Forensic Medicine needs its examination grant. Selection must not hide a costly fixed grant.

## Small shared content menu

### Domains

Use just **zeal / Weapon Surge** and **healing / Healer's Blessing** as the initial shared menu. Implement each spell once and validate legal deity/mystery/feature access where it is granted. The selected Warpriest, Justice Champion and Life Oracle do not automatically receive these spells. Do not build separate exhaustive domain catalogs per class or add a domain solely because its class can eventually choose one.

### Spells

Add batches needed by actual selected builds:

- Divine core: existing Divine Lance, Void Warp, Guidance, Stabilize and Heal; Light, Fear, Runic Weapon and Sure Strike. Use Light as the Warpriest's fifth prepared cantrip. Optional Read Aura/Identify Magic are deferred; neither is a required class grant.
- Shared next effects: Shield, Harm, Command, Soothe, Vitality Lash, Electric Arc and Tangle Vine.
- Battle Wizard: Force Barrage, Breathe Fire and Force Bolt, plus the smallest source-checked selections that complete its legal book. Ten chosen cantrips plus its distinct curriculum cantrip remain required; five prepared cantrips do not replace that knowledge count.
- Exactly the focus, composition, revelation and hex grants required by the selected roster.

Do not implement the union of every patron, bloodline or school. Utility spells chosen for a book still need bounded real behavior; unavailable placeholders do not satisfy the book count. The first Angelic repertoire can share existing divine cantrips, adding Light and the Heal gift, with Fear/Runic Weapon as its selected rank-1 choices.

### Alchemy and equipment

The Bomber's finite level-1 book has eight formulas: Bottled Lightning, Frost Vial, Minor Elixir of Life, Lesser Antidote, Lesser Antiplague, Lesser Bestial Mutagen, Lesser Cognitive Mutagen and Giant Centipede Venom. The first two supply its selected field pair. At level 2 add Lesser Alchemist's Fire and Black Adder Venom. These are ten specific formulas, not a requirement to implement the field's entire eligible catalog. Check printed grants and legality before admission.

Use only a few examples of each relevant item type. Their required splash, mutagen, treatment and affliction behavior must work; field eligibility alone does not make every item mandatory. More fields, poisons, potions, scrolls, summons and equipment are deferred unless selected work establishes a clear need.

Preserve accepted weapons, armor and steel shields. Finish initial weapon potency +1, striking, armor potency +1, resilient and invested handwraps. Higher-level equipment is explicitly granted to level-1 test builds. Add healer's and alchemist's toolkits where the selected procedures require them. Runed armor requires investment for magical benefits; uninvested armor keeps mundane protection.

## Delivery order

1. **Coherent runes and Assurance — complete.** Actual attack, damage, AC/save effects, investment, item identity and saved play pass. The existing Fighter's selected Assurance choice is executable in Python and the terminal. Preserve these paths as class coverage grows.
2. **Thief Rogue — complete for the fixed level-1 build.** Preserve legal grants, Sneak/Surprise, Dexterity damage and saved pre-roll Nimble Dodge. Qualifying/non-qualifying attacks, precision defenses, later-round play and victory have explicit evidence; keep pure damage checks distinct from public encounters.
3. **Angelic Sorcerer and narrow Warpriest cleanup.** Connect spontaneous slots, focus/refocus, Halo, Blood Magic and Potency. Verify strongest applicable status bonus, recipients/timing, saved checks and exhausted resources. Complete the small selected repertoire, including [real Light/Sustain and a minimal dim scene](../work-log/light-runtime-work.md). Dim targeting uses actual concealment checks and selected vision; the [skill/item packet](../work-log/dim-skill-item-work.md) connects maneuvers, Feint, Demoralize and Runic Weapon while preserving applicable actor-side benefits. Darkness/hidden-creature systems remain outside this first environment. Provide explicit local between-encounter recovery/preparation. Give the Warpriest the already-working Light cantrip in place of its optional Read Aura placeholder, then a legal alternate Sure Strike preparation without inventing a slot. The [preparation packet](../work-log/warpriest-utility-work.md) defers optional identification machinery; the [bounded caster handoff](../work-log/angelic-runtime-work.md) gives phased first-cast-to-complete-play acceptance.
4. **Justice Champion.** Use the [selected legal build and encounter packet](../work-log/justice-runtime-work.md) after shared focus/recovery. Protection applies even when retaliation cannot reach, using resistance for that damage event before the ordinary defenses and ally Shield Block. Saved retaliation must follow ordinary on-turn attack penalties rather than copying Reactive Strike’s exception. Grant Desperate Prayer at level 1 with its zero-focus turn-start trigger and turn-end expiry. Verify Lay on Hands, aura suppression, holy Strikes and shared reaction choices through completed fights.
5. **Other representative classes.** Follow the source-checked [Investigator](../work-log/investigator-runtime-work.md) and [Swashbuckler](../work-log/swashbuckler-runtime-work.md) packets for actual skill/context checks, medicine, panache, thrown items and Tumble Through. Investigator's first attack sequence and Forensic healing are accepted as staged capabilities. Following accepted Knowledge, deliver the [remaining selected grants](../work-log/investigator-remaining-grants-work.md) in bounded pieces: authored body examination and saved follow-up, leads/Clue In/free Devise, Skill Stratagem and selected Streetwise. The first Braggart attack/panache path is accepted; preserve accepted melee Confident Finisher, then implement Tumble Through and thrown Flying Blade over stable APIs, with coordinated narrow shared-file edits. Author limited GM context explicitly instead of building a general mystery system. Reuse shared procedures without a speculative movement framework. Sequential strikes bring Monk/Ranger: same-type pairs can proceed under settled rules, while only mixed-type/shared-resistance behavior waits for its pending decision. The bounded [rank-1 Soothe delivery](../work-log/soothe-shared-spell-work.md) can use already accepted caster APIs in parallel with skill-class work; it supplies common Bard/Oracle content without admitting those classes. Focus/sustained effects/casting bring Druid/Bard/Oracle/Wizard; familiar actions bring Witch; literal item activation/expiry/splash/afflictions bring Bomber.
6. **Level-1 acceptance.** All sixteen selected representatives have legal working grants, focused feature evidence, complete encounters, saved continuation, representative terminal play and bounded performance.
7. **Level-2 acceptance.** Apply actual HP/statistics/resources and legal selected class/skill feats; include Rogue/Investigator skill increases and class-specific learned-content deltas. Test changed behavior, not merely a level label.
8. **Generalization review.** After both levels pass, Astra reviews demonstrated duplication. Apply justified small simplifications, preserving relevant evidence; avoid speculative frameworks. One concrete input is keeping character-sheet proficiency labels consistent with actual roll bonuses: independent Justice and Swashbuckler reviews both found labels that disagreed with otherwise correct numbers. Record these examples for that review; they do not require a character-building rewrite now.

For each next bounded playable outcome, one Luna owner handles necessary runtime, persistence, terminal and tests through ordinary fixes and independent review. Helpers need a clear independent contribution without shared-file contention; do not split layers by default. Use existing packets to define the complete public acceptance sequence, prerequisites, adverse cases and exclusions. Early executable checkpoints diagnose progress rather than force handoffs. Preserve current owners and close Sorcerer/Warpriest before commissioning more future-class research. Do not accumulate an unexecuted rewrite or disconnected helpers.

## Current accepted baseline and active work

The [recovery page](../work-log/ACTIVE.md) holds the latest verified counts, active owners, blockers and next action. Preserve the accepted S1–S3 foundation, eleven Barbarian variants and fixed Thief/Fighter/current Warpriest slices. Definitions and source packets never imply whole-class acceptance. The current class sequence and selected menu above remain the scope; execution state is maintained once on the recovery page.

## Decisions and explicit limits

- **Resolved:** Escape preserves Feint's opening, including escape from the feinted holder. The actual public interaction test passes.
- **P1 asked, pending:** rare paired Strikes mixing damage types against broad resistance. Current errata lets the defender choose the protected type but does not settle the choice's timing between sequential Strikes. The [source packet](../work-log/paired-strike-boundaries.md) recommends initially deferring that combination while supporting same-type pairs; the alternative is an explicit commitment convention. Only dependent behavior waits.
- **Resolved by declared GM convention:** reload-0 bow drawing uses one combined draw/ranged reaction opportunity, then the Grabbed check, then launch. Critical disruption stops the remaining paired activity and retains unlaunched ammunition. The source packet distinguishes this timing convention from printed facts. Runtime implementation remains outstanding.
- **Still unsupported:** positive damage to an already stable unconscious PC at zero HP.
- **Asked, pending:** whether an enemy reaction before its first turn ends Surprise Attack eligibility. The proposed local convention keeps the opening until the first turn starts; no answer is assumed, and current Rogue scenarios cannot encounter the edge: Deception faces only a reactionless Guard Dog; Fighter/Warpriest fixtures use Perception. It gates future content rather than present acceptance.
- **Deferred:** Hag Retributive Spite fallback timing. Hag is not in the representative roster, so its unanswered question no longer blocks this milestone.

Do not silently approximate supported behavior. Reuse existing answers and ask only for a materially necessary unresolved P0/P1 decision.

## Small GM conventions used during implementation

The user delegated ordinary GM decisions. When a grabbed creature attempts manipulation, the engine will resolve its existing reaction window before the Grabbed flat check. This preserves ordinary interruption timing; the sources establish both checks but do not specify their relative order. If the reaction disrupts the action, no redundant flat check follows.

A failed attempt to drink an ordinary potion or elixir retains the item unless specific item text consumes it during the attempt or an explicit adjudication spills it. This is a literal convention for an unclear destruction boundary. Scroll casting and limited daily activations still spend their specifically stated costs. A failed draw or reload spends the action but does not destroy the item or ammunition. These choices avoid treating every inventory change as a cost. [Grabbed](https://2e.aonprd.com/Conditions.aspx?ID=77), [activities and disruption](https://2e.aonprd.com/Rules.aspx?ID=2342), [item activation](https://2e.aonprd.com/Rules.aspx?ID=3135).

For Feint, treat ordinary physical Trip and Grapple against the feinted creature as melee attacks: a committed attempt consumes an ordinary success opening, even if it fails. Off-guard still changes AC only, so those maneuvers receive no reduction to their save DC. This follows the general attack rules and their physical melee execution; it is a documented interpretation rather than a specific printed Feint–Athletics clarification. Melee spell attacks qualify as well. Scoundrel’s persistent effects do not disappear after one attempt. [Paizo attack clarification](https://paizo.com/pathfinder/faq), [Feint](https://2e.aonprd.com/Actions.aspx?ID=2390).

These are chosen behavior, not a claim that the printed text explicitly specifies the ordering, liquid loss or every melee classification. Mixed-type paired resistance remains pending; the bow convention is recorded above and in its source packet. Hag is deferred under the representative roster. The Escape ruling is settled.

For Shield Block, apply the character’s immunity/weakness/resistance first. If physical damage remains from an attack, apply Hardness once against the whole remaining attack total for the character. The ordinary steel shield retains its printed object immunities: separately exclude shield-immune damage before computing its HP loss. With remaining total D, shield-vulnerable total V and Hardness H, character damage is max(0, D−H), and shield HP loss is max(0, V−H). Apply character temporary HP afterward. There is no second Hardness pass. If no physical damage remains after character defenses, Block does not trigger.

This is a documented GM allocation convention: Hardness protects shield-vulnerable damage first, then any unused allowance protects the character against the remaining attack damage. It requires no extra damage-type choice and preserves the object immunity rules. Steel is immune to mental, poison, spirit, bleed, vitality and void damage, and to nonlethal attacks as a whole; use actual attack intent. Precision damage and critical hits are not general object immunities. For 8 slashing + 4 mental after character defenses, Hardness 5 leaves 7 character damage but only 3 shield damage. The exact allocation convention is not an explicit Paizo mixed-damage ruling. [Object immunities](https://2e.aonprd.com/Rules.aspx?ID=2161), [Shield Block](https://2e.aonprd.com/Feats.aspx?ID=5212), [Paizo FAQ](https://paizo.com/pathfinder/faq).

## Encounter and resource discipline

Expand S1/S2/S3 interactions around actual new decisions, not every class combination. Use healthy starting actors, deterministic supplied dice or seeds, a meaningful save point and a legitimate completed outcome. A changed seed is not another encounter. Fixed-grant and rejection branches use focused tests; representative terminal runs check actual numbered choices and useful output.

Run small related selections frequently and one broad suite at coherent checkpoints. Keep captures, commands, rounds and subprocess runtimes bounded. Sol periodically executes the real engine and checks source rules. Clean attributable worker processes; preserve app-shared services when ownership cannot be established. Follow the [working model](04-delivery-and-checks.md).

Family source inventories may describe unselected options. They are reference material, not the delivery target. The supervisor maintains accepted/staged/deferred state and actual per-run token metadata in the [work log](../work-log/README.md).
