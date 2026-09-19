# Superseded exhaustive S3i scope

Archived after the user approved representative coverage across all sixteen classes. This is historical planning, not the active delivery requirement. See the [current plan](../../plan/06-class-and-content-expansion.md).

# S3i extension: every Player Core class, then level 2

## Outcome in plain language

Make every class and subclass printed in Player Core and Player Core 2 playable in the local Python engine. Finish level 1 first, then level 2. Add useful combat feats, spells, equipment and encounters as those classes need them. After both levels work, review the actual implementation for worthwhile simplification and reuse.

This extends the existing S3i milestone. The first increment remains accepted: sixteen added interaction encounters, 21 catalogued setups and 211 passing tests. The expansion described here is **in implementation, not yet supported content**.

## Scope decisions

- **All sixteen classes and every printed PC1/PC2 subclass.** Later-book subclasses are outside this selection.
- **Complete class features through the active level.** Fixed named grants, such as a patron hex or cause reaction, must actually work. Ordinary “choose a feat/spell/formula” menus contain a curated useful subset. We do not recursively implement every option in those menus.
- **Level 1, then level 2.** Spell rank remains 1 at both levels. The second pass adds actual progression changes and selected combat feats; it is not a label change on the same statistics.
- **Common equipment includes fundamental combat runes.** The user approved explicitly granted test equipment whose item level exceeds the character level. Labels preserve that distinction; it does not raise the PC level cap or pretend the gear is an ordinary starting purchase.
- **Local state and explicit choices.** Daily preparation, learning, Refocus, recovery and GM context use ordinary local inputs. No campaign simulator, server or browser is required.
- **Astra judges optional content scope.** Required class grants take priority. Useful common rules come next. A rare optional feat or spell may be omitted rather than forcing a disproportionate subsystem.
- The existing unsupported boundary for positive damage to a stable unconscious PC at 0 HP stays explicit. This extension does not silently select the unanswered ruling.

The user confirmed the subclass and equipment decisions in thread. One narrow P1 ruling is pending for Hag sorcerer: Retributive Spite’s printed retaliation window ends after the next turn, but its fallback temporary HP is awarded before that turn. The user has been asked to choose a consistent boundary. Only that behavior waits; other implementation continues. [Source](https://2e.aonprd.com/Bloodlines.aspx?ID=26).

Paired attacks also need a narrow timing convention when broad resistance can protect one of several damage types. The proposed convention preserves ordinary sequential hits, requires the defender to commit the protected type on the first eligible hit, and carries remaining resistance only for that type. This preserves first-hit consequences but restricts when the choice is made; the user question remains pending. [Delegated rules analysis](../../implementation/paired-strike-resolution.md).

A third P1 question concerns reload-0 bows: whether their included arrow draw is a manipulate step. The recommended source interpretation adds the Grabbed flat check and permits a critical Reactive Strike to stop that draw before firing; the alternative retains ranged-Strike-only behavior. Because this changes an existing common combat path, the user has been asked. Only this bow branch waits. [Reload](https://2e.aonprd.com/Rules.aspx?ID=2196), [subordinate actions](https://2e.aonprd.com/Rules.aspx?ID=2335).

The user resolved the Feint/Escape classification: **Escape preserves Feint’s opening**, including Escape from the feinted creature’s physical grab. The rules do not expressly classify every Escape as a melee attack against its holder; this is the chosen consistent game ruling. The accepted public interaction tests exercise Grapple → Feint → Escape → Strike. [Feint](https://2e.aonprd.com/Actions.aspx?ID=2390), [Escape](https://2e.aonprd.com/Rules.aspx?ID=2343).

## Small GM conventions used during implementation

The user delegated ordinary GM decisions. When a grabbed creature attempts manipulation, the engine will resolve its existing reaction window before the Grabbed flat check. This preserves ordinary interruption timing; the sources establish both checks but do not specify their relative order. If the reaction disrupts the action, no redundant flat check follows.

A failed attempt to drink an ordinary potion or elixir retains the item unless specific item text consumes it during the attempt or an explicit adjudication spills it. This is a literal convention for an unclear destruction boundary. Scroll casting and limited daily activations still spend their specifically stated costs. A failed draw or reload spends the action but does not destroy the item or ammunition. These choices avoid treating every inventory change as a cost. [Grabbed](https://2e.aonprd.com/Conditions.aspx?ID=77), [activities and disruption](https://2e.aonprd.com/Rules.aspx?ID=2342), [item activation](https://2e.aonprd.com/Rules.aspx?ID=3135).

For Feint, treat ordinary physical Trip and Grapple against the feinted creature as melee attacks: a committed attempt consumes an ordinary success opening, even if it fails. Off-guard still changes AC only, so those maneuvers receive no reduction to their save DC. This follows the general attack rules and their physical melee execution; it is a documented interpretation rather than a specific printed Feint–Athletics clarification. Melee spell attacks qualify as well. Scoundrel’s persistent effects do not disappear after one attempt. [Paizo attack clarification](https://paizo.com/pathfinder/faq), [Feint](https://2e.aonprd.com/Actions.aspx?ID=2390).

These are chosen behavior, not a claim that the printed text explicitly specifies the ordering, liquid loss or every melee classification. The separate Hag, paired-resistance and bow questions above remain pending. The Escape ruling is settled.

For Shield Block, apply the character’s immunity/weakness/resistance first. If physical damage remains from an attack, apply Hardness once against the whole remaining attack total for the character. The ordinary steel shield retains its printed object immunities: separately exclude shield-immune damage before computing its HP loss. With remaining total D, shield-vulnerable total V and Hardness H, character damage is max(0, D−H), and shield HP loss is max(0, V−H). Apply character temporary HP afterward. There is no second Hardness pass. If no physical damage remains after character defenses, Block does not trigger.

This is a documented GM allocation convention: Hardness protects shield-vulnerable damage first, then any unused allowance protects the character against the remaining attack damage. It requires no extra damage-type choice and preserves the object immunity rules. Steel is immune to mental, poison, spirit, bleed, vitality and void damage, and to nonlethal attacks as a whole; use actual attack intent. Precision damage and critical hits are not general object immunities. For 8 slashing + 4 mental after character defenses, Hardness 5 leaves 7 character damage but only 3 shield damage. The exact allocation convention is not an explicit Paizo mixed-damage ruling. [Object immunities](https://2e.aonprd.com/Rules.aspx?ID=2161), [Shield Block](https://2e.aonprd.com/Feats.aspx?ID=5212), [Paizo FAQ](https://paizo.com/pathfinder/faq).

## Class coverage target

Each row needs correct statistics, resources, prerequisites and actual behavior. Listing a name in the catalog is not completion.

| Class | Printed subclasses or choices in scope | Distinctive feature families |
|---|---|---|
| Bard | Enigma, Maestro, Polymath, Warrior | Repertoire, compositions, focus, muse grants. |
| Cleric | Cloistered Cleric, Warpriest | Preparation, font, doctrine, deity and devotion choices. |
| Druid | Animal, Leaf, Storm, Untamed | Preparation, order focus spells, companion/familiar/form, nature features, Shield Block. |
| Fighter | No subclass | Reactive Strike, Shield Block, selected combat feats. |
| Ranger | Flurry, Outwit, Precision | Hunt Prey, edge-specific benefits and selected feats. |
| Rogue | Mastermind, Ruffian, Scoundrel, Thief | Sneak/Surprise Attack, skill actions, racket behavior and applicable critical specialization. |
| Witch | Faith’s Flamekeeper, The Inscribed One, The Resentment, Silence in Snow, Spinner of Threads, Starless Shadow, Wilding Steward | Familiar preparation, hexes, patron familiar benefits, Sustain and detection. |
| Wizard | Seven schools and five theses below | Spellbook/preparation, curriculum, school spells, bonded item and thesis behavior. |
| Alchemist | Bomber, Chirurgeon, Mutagenist, Toxicologist | Formula book, daily/quick alchemy, versatile vials and field rules. |
| Barbarian | Animal, Dragon, Fury, Giant, Spirit, Superstition | Rage, Quick-Tempered, instinct attacks/damage/restrictions. |
| Champion | Desecration, Grandeur, Iniquity, Justice, Liberation, Obedience, Redemption | Cause reactions, aura, devotion spells, deity weapon and Shield Block. |
| Investigator | Alchemical Sciences, Empiricism, Forensic Medicine, Interrogation | Leads, Clue In, attack/skill stratagem, Strategic Strike, methodology. |
| Monk | No subclass; selected combat feats | Flurry of Blows, Powerful Fist and selected combat feats. |
| Oracle | Ancestors, Battle, Bones, Cosmos, Flames, Life, Lore, Tempest | Repertoire, revelations, mystery curse and fixed cursebound grants. |
| Sorcerer | Aberrant, Angelic, Demonic, Diabolic, Draconic, Elemental, Fey, Hag, Imperial, Undead | Repertoire, bloodline focus, blood magic and Sorcerous Potency. |
| Swashbuckler | Battledancer, Braggart, Fencer, Gymnast, Rascal, Wit | Panache, Precise Strike, Stylish Combatant, finisher and style actions. |

Wizard schools: Ars Grammatica, Battle Magic, Civic Wizardry, Mentalism, Protean Form, the Boundary, Unified Magical Theory. Theses: Experimental Spellshaping, Improved Familiar Attunement, Spell Blending, Spell Substitution, Staff Nexus. Compose compatible choices as data; do not write 35 separate engines or generate every possible encounter combination.

At level 2, all classes gain their applicable HP/statistic/resource changes and class/skill feat selections. Rogue and Investigator gain a skill increase. Casting, learned spells and alchemical formulas change according to each class. Source notes define the exact deltas.

## Delivery segments

1. **Shared rules required now.** Checked conditions and statistics, damage components and defenses, casting sources/resources, item instances/activations, and demanded geometry. Keep helpers small and preserve current entry points.
2. **Level-1 martial families.** Skill actions, shields, Rage, Flurry, Hunt Prey, precision, stratagems, panache and their class definitions. Keep complete encounters running during integration.
3. **Level-1 casting and reaction families.** Prepared/repertoire/focus/innate sources, required spells, compositions, causes, curses and blood magic.
4. **Level-1 owned actors and preparation.** Required companions, familiars, summons, forms, theses and alchemy. Admit every remaining subclass without stubs.
5. **Level-1 acceptance.** Every class/subclass has legal playable choices, focused feature evidence, additional complete encounters, saved continuation, representative terminal use and bounded performance evidence.
6. **Level-2 pass and acceptance.** Correct progression and selected new content; test changed numerical boundaries, resources and new feat interactions. Repeat the integrated review at this milestone.
7. **Generalization review.** After both levels pass, Astra identifies demonstrated duplication and useful shared operations. Apply small justified simplifications with relevant tests; avoid speculative machinery for future levels.

Segments are integration checkpoints, not excuses to defer a mandatory feature outside this milestone. One owner controls shared encounter/model/persistence changes at a time. Independent helpers and family content use separate owned modules.

Within these segments, finish small playable paths. The first Barbarian path is Bear with Raging Intimidation; its ordinary Rage, initiative-triggered Rage, temporary HP, restrictions and saved decisions must work before broadening to the remaining instincts. The first casting integration uses the existing admitted warpriest and its current spell slots, preserving existing public commands and saves. The reviewed casting helpers calculate access and expenditure; they do not introduce a second copy of those slots. Feint uses attacker-specific off-guard effects so it cannot accidentally help every combatant. These are concrete uses of the existing procedures, not a new engine architecture.

## Shared mechanics checkpoints

Feint, the existing casting connection, **typed damage defenses** and **steel shields** are accepted. Finish **fundamental runes and handwraps** as the next playable checkpoint. Use the existing helpers and reaction resource. Attack, spell and family damage must all pass through the same mitigation and health procedure so temporary HP and knockout are applied once.

The damage sequence is rolled damage and critical/basic-save arithmetic, immunity, weakness, resistance, qualifying Shield Block, temporary HP, then ordinary health. Save the original damage and any real pending decision. Preserve the current attack or spell continuation; do not add an event subscription framework. Single-effect overlapping resistance choices can work independently of the unanswered paired-attack question. Source interpretation places Shield Block after defenses because its trigger is damage the actor would take; for mixed damage, use the GM convention in the section above. Massive Damage compares post-defense, post-Block damage before temporary HP absorbs any of it. Keep that amount separate from ordinary HP subtraction in both live and saved health transitions.

Finish the steel-shield path as its own tested checkpoint before integrating all rune effects. Start with a steel-shield variant of the existing fighter, funded from its recorded remaining money. Its shield uses one stable item identity, keeps its damage through dropping and retrieval, and shares the ordinary reaction resource with Reactive Strike. Initial rune grades are weapon potency +1, striking, armor potency +1 and resilient, plus invested handwraps where appropriate. Higher-level items are explicitly granted test equipment on level-1 characters. Rune effects must change real checks and damage dice. Runed armor and handwraps require investment for magical benefits; wearing uninvested armor preserves only its mundane protection.

Use a fully authored living test opponent for initial resistance, weakness and immunity encounters. Published Skeleton Guard and Zombie Shambler remain staged: their mandatory weapon abilities, undead healing/defeat rules and other abilities require separate implementation. Do not equate immunity with an illegal target or silently suppress those abilities to admit the published monster. The first encounters demonstrate defenses with Rage temporary HP, a shield breaking and reaction competition, and actual rune effects through a completed fight and saved continuation.

Bear, Cat, Frog and all eight Dragon variants have now completed their public encounter checkpoints; the Dragon typed-defense fight also passes. After runes, close the existing Fighter background Assurance (Athletics) choice, then finish Ape, Deer, Shark, Snake and Wolf through one extension that lets existing Grapple/Trip select an exact natural attack. It uses that attack's trait, reach and applicable potency bonus, persists the selection, and never offers to drop a body part on critical failure. Ordinary free-hand maneuvers do not substitute for those grants. Bull follows with Shove displacement and optional following movement. Then finish Fury, Giant, Spirit and Superstition in bounded playable slices. Ranger/Monk, Rogue and the remaining instincts retain serial shared-runtime dependencies. Use parallel work only where it can reach a tested public decision without conflicting shared edits.

## Content selection and tests

Required class and subclass spells come first. The initial elective shortlist includes shields; Trip, Grapple, Escape, Feint, Tumble Through and Demoralize; useful healing and intimidation feats; multi-target/basic-save/area spells; Runic Weapon/Body; healing potions/elixirs; representative bombs, mutagens and poisons; scrolls; and fundamental runes. Source readers and implementation evidence may narrow optional selections while keeping all required grants intact.

The initial encounter design proposes about twenty new routes, organized by interaction rather than every possible class combination:

- **S1 mechanisms:** mixed damage defenses and temporary HP, plus action limits and timed conditions.
- **S2 class tactics:** shield breaking, Rage and temporary HP, hunted targets, Flurry and maneuvers, rogue openings and finishers, stratagem choices, and field medicine.
- **S3 mixed parties:** arcane multi-target casting, overlapping compositions/bonuses, companion command/flanking, forms/focus, patron/familiar effects, divine protection, blood magic, curses, bombs/mutagens, poison/treatment, and scroll/rune use.

These are proposals until played. Every accepted new encounter starts healthy, creates its relevant state through legal public commands, saves at a meaningful boundary, and continues to a real outcome. Subclass-specific focused tests cover branches that a shared encounter does not directly demonstrate. A changed seed is not another encounter.

Use the existing bounded harness and small family test modules. Check rejected requests, exact costs, resource ownership, expiry, deterministic rolls and restored continuation. Compare resumed actions against uninterrupted play, not just matching inspection output. Run small selections frequently; run a single broad integration check at meaningful acceptance checkpoints. Audit and reap worker-owned processes as specified in the [working model](../../plan/04-delivery-and-checks.md).

## Sources and completeness record

Research uses current Remaster entries on Archives of Nethys plus official Paizo errata. Family source notes record exact edition/source, actions, timing, choices and expected tests. Spring 2026 corrections to bombs, defenses and class features take precedence over older text.

The supervisor records acceptance by class/subclass and feature family from delegated evidence. The implementation owners maintain source notes and tests. No class is called supported solely because its definition exists. Scope and progress are summarized in the [work log](../README.md).
