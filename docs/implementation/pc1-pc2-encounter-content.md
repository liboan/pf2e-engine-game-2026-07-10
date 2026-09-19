# PC1/PC2 common content and encounter handoff

Design/source handoff, 2026-09-15. This specifies proposed content and acceptance evidence; it does not claim implementation or test completion. Finish one approved representative build for each Player Core 1/2 class at level 1, then level 2, within S3i. Printed subclasses and nested options outside the approved roster remain reference inventory. Optional spell/feat/item menus are deliberately selected, with one or two nested examples. Neither character level grants rank-2 spells. A small encounter catalogue supplements, rather than replaces, targeted coverage of each selected representative's mandatory behavior.

Use the [core contract](pc1-pc2-core-contract.md) and the [martial](pc1-pc2-martial-rules.md), [divine](pc1-pc2-divine-rules.md), [nature](pc1-pc2-nature-rules.md), [alchemy](pc1-pc2-alchemy-rules.md), and [arcane](pc1-pc2-arcane-rules.md) source notes for authoritative grant lists and exact family behavior. These lists take priority over the optional shortlist below. Existing scenarios already exercise ordinary MAP, degrees, movement, cover, flank, reactions, recovery, bows, and the initial cleric spells; new scenarios must add an observable interaction.

## Version and rules dependencies

Use current individual Remaster entries together with [official Paizo errata](https://paizo.com/pathfinder/faq), including [Spring Errata 2026](https://paizo.com/blog/spring-errata-2026). Do not implement from old search snippets or legacy names alone. The family notes identify additional grant-specific corrections.

- [Bombs](https://2e.aonprd.com/Rules.aspx?ID=3181): use current thrown-bomb handling, without adding Strength to bomb/splash damage. Failure splashes only the target; success/critical success also affects nearby creatures; critical failure causes no splash. Splash is not doubled on a critical hit. Combine applicable initial same-type damage before defense; persistent damage is a later event.
- The 2026 category-defense clarification matters: a broad resistance is used once per effect, with an eligible component choice where applicable. Preserve components and effect identity until defenses resolve; do not subtract broad resistance from every component. Distinct applicable weaknesses can each apply once. The divine/core notes own this algorithm.
- A condition's source, target, value, duration, and expiration boundary are distinct data. Required sources already justify slowed (Zombie Shambler), stunned (Daze, Dizzying Colors, later Stunning Blows), and multiple source/target boundary expirations. No quickened implementation is requested by this matrix.
- [Bestial Mutagen](https://2e.aonprd.com/Equipment.aspx?ID=3315) uses the current drawbacks and explicit striking exclusion. Do not import the legacy AC penalty or allow striking to increase its granted attack dice.

## A usable spell catalogue, not placeholder knowledge

Implement fixed gifts, patron spells, focus spells, and selected curriculum spells first. Reuse their handlers across all traditions and cast sources; a granted off-tradition spell is available through that grant, not a general expansion of its tradition. Known, prepared, repertoire, granted, and available-to-learn are different sets.

Witch requires ten familiar-known cantrips and five chosen rank-1 spells **plus** its patron spell at level 1; add two known spells at level 2. Wizard requires ten chosen cantrips and five chosen rank-1 spells **plus** school additions; add two known spells at level 2. Use the arcane note's full ledger for school slots and Unified Magical Theory. Never fill these counts with names that cannot actually be cast or resolved.

### Small shared cantrip pools

These are legal ten-entry example pools. They are knowledge pools, not ten prepared spells. Wizard selections must exclude the selected school's extra curriculum cantrip, replacing it with a legal reserve so the school addition remains additional.

| Tradition | Ten reusable entries |
|---|---|
| Arcane | Detect Magic, Light, Read Aura, Daze, Shield, Void Warp, Electric Arc, Ignition, Figment, Tangle Vine |
| Divine | Detect Magic, Light, Read Aura, Daze, Shield, Void Warp, Guidance, Stabilize, Vitality Lash, Divine Lance |
| Occult | Detect Magic, Light, Read Aura, Daze, Shield, Void Warp, Figment, Message, Guidance, Forbidding Ward |
| Primal | Detect Magic, Light, Read Aura, Guidance, Stabilize, Vitality Lash, Electric Arc, Ignition, Tangle Vine, Frostbite |

The mandatory grant union already adds arcane reserves Message, Gouging Claw, Caustic Blast, Gale Blast, Scatter Scree, and Frostbite. Choose an explicit legal reserve when needed; do not unlock all spells or generate arbitrary presets. Forbidding Ward is a useful small additional handler that completes the occult pool and reuses typed AC/save modifiers.

Sources for common entries not fully specified in the family notes: [Detect Magic](https://2e.aonprd.com/Spells.aspx?ID=1485), [Light](https://2e.aonprd.com/Spells.aspx?ID=1585), [Read Aura](https://2e.aonprd.com/Spells.aspx?ID=1646), [Daze](https://2e.aonprd.com/Spells.aspx?ID=1482), [Shield](https://2e.aonprd.com/Spells.aspx?ID=1671), [Figment](https://2e.aonprd.com/Spells.aspx?ID=1528), [Message](https://2e.aonprd.com/Spells.aspx?ID=1598), [Forbidding Ward](https://2e.aonprd.com/Spells.aspx?ID=1535), [Tangle Vine](https://2e.aonprd.com/Spells.aspx?ID=1713). Family notes source the remaining gifts.

Utility entries need small real local operations: Detect Magic reveals permitted presence information; Read Aura completes its one-minute activity; Light changes lighting and maintains its object/creature attachment; Message supports the recipient's legal response; Figment supports Create a Diversion and disbelief. A successful no-op is not support. PFS-specific Figment commentary is not automatically a general-rule house ruling. Forbidding Ward selects an ally and enemy, giving its sustained +1 status AC/saves only against that enemy.

### Rank-1 chosen-spell pools

Each row leaves enough distinct legal choices for five chosen spells, an excluded fixed grant, and two level-2 additions. Selected Wizard curricula have further mandatory entries in the arcane note. Author concrete preset lists from these pools; assert count, uniqueness, tradition/grant legality, and handler availability at both levels.

| Tradition | Compact available pool |
|---|---|
| Arcane | Force Barrage, Fear, Runic Weapon, Runic Body, Command, Sure Strike, Enfeeble, Breathe Fire, Hydraulic Push, Pummeling Rubble; plus mandatory selected curriculum spells |
| Divine | Heal, Harm, Fear, Command, Enfeeble, Runic Weapon, Runic Body, Bless |
| Occult | Force Barrage, Fear, Command, Enfeeble, Sure Strike, Soothe, Runic Weapon, Runic Body, Bless, Phantasmal Minion |
| Primal | Heal, Fear, Runic Weapon, Runic Body, Breathe Fire, Gust of Wind, Summon Animal, Hydraulic Push, Pummeling Rubble, Tailwind, Thunderstrike |

The small optional additions are [Runic Body](https://2e.aonprd.com/Spells.aspx?ID=1657) and [Bless](https://2e.aonprd.com/Spells.aspx?ID=1451); [Runic Weapon](https://2e.aonprd.com/Spells.aspx?ID=1658) is already a mandatory grant. [Enfeeble](https://2e.aonprd.com/Spells.aspx?ID=1513) is arcane/divine/occult. Bless reuses a sustained emanation and status attack modifier; Runic Body reuses the same rune-dice logic as weapons with unarmed eligibility. Both runic spells last one minute at this rank. Exact other spell behaviors and citations belong to the family notes.

Do not drop mandatory less-combat-oriented grants such as Mindlink, Cleanse Cuisine, Illusory Disguise, Phantasmal Minion, or Pest Form to keep this list short. Resolve their bounded local use as specified by their owner. Optional Live Wire, more summons, additional forms, property runes, and a comprehensive spell list can wait.

## Common feats, gear, and consumables

Keep the small class-feat menus already selected in each family note. Favor families already needed by fixed grants: Raise a Shield/Shield Block; Feint, Create a Diversion, Demoralize, and Tumble Through; Trip/Grapple/Shove/Reposition/Disarm; Battle Medicine; Reach Spell. A generic social or exploration simulator is not a prerequisite for their bounded legal commands. Skill choices should be explicit (for example Battle Medicine, Intimidating Glare, or Assurance for one declared skill), with prerequisites checked. Mandatory feats still require their full applicable behavior.

Support equipment that makes those commands real: steel shield and buckler with Hardness/HP/broken state; healer's toolkit and required hands; ordinary ammunition and reload state; one-handed and two-handed weapon configurations; unarmed and finesse/agile traits; armor and free-hand eligibility. Reuse existing ordinary weapons where possible. The skeleton's scimitar additionally requires forceful and sweep.

For the selected Bomber, implement a finite few level-1 formula profiles and one level-2 formula. The wider field and formula profiles remain source reference inventory, not automatically known formulas or delivery backlog. Preserve each selected formula's legal fields and advancement choices without another bespoke item subsystem.

Two small common magical consumables reuse existing handlers: [minor Healing Potion](https://2e.aonprd.com/Equipment.aspx?ID=2943), item 1/4 gp, one hand, light Bulk, one-action manipulate activation, restores 1d8 HP and has vitality/healing traits; [rank-1 Magic Scroll](https://2e.aonprd.com/Equipment.aspx?ID=2962), item 1/4 gp, one hand, light Bulk, containing Heal or Runic Weapon. [Scroll casting](https://2e.aonprd.com/Rules.aspx?ID=3135) requires the spell on the caster's list, uses the caster's statistics and normal casting actions, consumes the scroll, and spends no slot. Consumed item identity, activation hands/actions, eligibility, and cast origin must be literal. Do not add new spell handlers merely to stock scrolls.

### Base fundamental runes

These are explicit user-authorized item grants when above the character's normal item access. Retain their published item level and price; never raise character level, inflate ordinary starting wealth, or relabel them level 1. A scenario's grant metadata should explain the exception.

| Published item/source | Level; price | Shared behavior |
|---|---|---|
| [Weapon potency +1](https://2e.aonprd.com/Equipment.aspx?ID=2830) | 2; 35 gp | +1 item attack bonus |
| [Striking](https://2e.aonprd.com/Equipment.aspx?ID=2829) | 4; 65 gp | Two base weapon damage dice; does not duplicate precision or other added dice |
| [Armor potency +1](https://2e.aonprd.com/Equipment.aspx?ID=2785) | 5; 160 gp | Increase the armor's item AC bonus by 1; do not compete a separate +1 against the base armor bonus |
| [Resilient](https://2e.aonprd.com/Equipment.aspx?ID=2786) | 8; 340 gp | +1 item bonus to saves; compete normally with other item save bonuses |
| [Handwraps of Mighty Blows](https://2e.aonprd.com/Equipment.aspx?ID=3086), +1 / +1 striking | 2/4; 35/100 gp | Invested worn gloves; rune benefit applies to eligible unarmed attacks |

No greater grades or property-rune catalogue is required. Spell-created +1 striking and permanent +1 striking do not add together. Bestial Mutagen claws/jaws explicitly ignore striking's die increase, including handwraps; its item attack bonus competes with potency. An ordinary fist or legal monk attack remains eligible. Save/load must preserve which physical item is invested, wielded, dropped, or carrying a temporary spell.

## Exactly two additional published opponent profiles

Use normal Monster Core profiles, not weak/elite adjustments. Their compact shared dependencies are useful to mandatory grants. Include all their listed abilities; optional family-sidebar variants are separate modifications and are not added automatically. Existing Guard Dog remains the compact living opponent and Summon Animal option; the arcane owner also supplies mandatory Phantasmal Minion. No third monster family is needed here.

### Skeleton Guard

[Monster Core, page 312](https://2e.aonprd.com/Monsters.aspx?ID=3193): level −1; Medium, Mindless, Skeleton, Undead, Unholy. Perception +2, darkvision; Acrobatics +6, Athletics +3. Str +2, Dex +4, Con +0, Int −5, Wis +0, Cha +0. AC 16; Fort +2, Ref +8, Will +2; HP 4; void healing. Immunities: bleed, death effects, disease, mental, paralyzed, poison, unconscious. Resistances: cold, electricity, fire, piercing, slashing, each 5. Speed 25 feet. Equipment: scimitar, shortbow, 20 arrows.

| One-action Strike | Attack; damage | Required traits |
|---|---|---|
| Scimitar | +6; 1d6+2 slashing | forceful, sweep |
| Claw | +6; 1d4+2 slashing | agile, finesse |
| Shortbow | +6; 1d6 piercing | deadly d10, range increment 60 feet, reload 0 |

Use ordinary MAP, including the agile claw adjustment. Implement forceful/sweep rather than silently removing the sword. Do not infer precision immunity. Purpose: typed physical/energy resistance, mindless immunity, undead targeting, and a complete Summon Undead option. Optional Collapse or Explosive Death is not part of this base profile.

### Zombie Shambler

[Monster Core, page 356](https://2e.aonprd.com/Monsters.aspx?ID=3249): level −1; Medium, Mindless, Undead, Unholy, Zombie. Perception +0, darkvision; Athletics +7. Str +3, Dex −2, Con +2, Int −5, Wis +0, Cha −2. AC 12; Fort +6, Ref +0, Will +2; HP 20; void healing. Immunities: bleed, death effects, disease, mental, paralyzed, poison, unconscious. Weaknesses: slashing 5, vitality 5. Speed 25 feet. Slow: permanently slowed 1 and cannot use reactions.

Fist Strike is +7, 1d6+3 bludgeoning plus Grab; it is not an agile/nonlethal PC fist. Zombie Bite costs one action, requires a grabbed/restrained target, and makes a jaws Strike (+7, 1d8+3 piercing) with normal MAP.

[Grab](https://2e.aonprd.com/MonsterAbilities.aspx?ID=45) is an additional action after the successful listed Strike: attempt Athletics to Grapple using that body part; this check neither applies nor increases MAP. An existing qualifying hold can instead be automatically extended to the end of the next turn. Do not implement automatic grab on the hit itself. Purpose: two-action turns, actual Grapple/Escape/Bite, slashing/vitality weakness, poison immunity, and mixed Heal/Harm areas. Optional zombie variants are excluded.

Both profiles need their actual undead/void-healing rules and destruction at 0 HP. Void damage does not inherently heal an undead creature; the healing effect must say that it heals undead. In particular, Void Warp targets a living creature and cannot be used as an undead heal.

## Twenty bounded level-1 encounter candidates

These are tactical cases, not every subclass permutation or renamed existing tests. S1 isolates core rule interactions, S2 combines the approved representative actor/action families, and S3 combines multiple actors/resources across continuous play. Each starts healthy, creates damage/conditions through public commands, uses deterministic rolls, checkpoints a consequential intermediate state, resumes, and asserts both immediate and later outcomes. Rows naming unselected branches (such as Animal/Leaf/Untamed, Mutagenist, Toxicologist, or Chirurgeon) are reference scenarios only, not acceptance gates for the selected roster. Synthetic S1 defense fixtures must be labeled synthetic; they are not invented published monsters.

| # / stage | Setup and distinct level-1 interaction | Consequential checkpoint and acceptance |
|---|---|---|
| 1 / S1 | Mixed physical/energy damage from a legal dragon-instinct Strike against a synthetic defender with broad and specific resistance; obtain temporary HP through a supported effect. | Save at defense-component selection. Resolve choice, exact HP/temp-HP and damage event once; chosen broad resistance is not independently applied to both components. Test alternate choice in a focused case. |
| 2 / S1 | Zombie's permanent slowed turn alongside a living target affected by Dizzying Colors; add Enfeeble's source-start expiry and a target-end effect through supported casts. | Save before a turn boundary. Assert stunned value versus stunned duration, unavailable actions/reactions, and source/target expiry separately. Zombie is mental-immune: never claim Colors stuns it. Focused synthetic overlap tests may combine already required slowed/stunned conditions. |
| 3 / S2 | Fighter with raised shield faces physical attack and a movement-trigger opportunity in the same round. | Save at reaction choice; choose Block, compute wielder/shield damage and broken state, then show the spent reaction prevents Reactive Strike. |
| 4 / S2 | Barbarian enters through Quick-Tempered, takes damage into rage temp HP, and uses its selected instinct's legal attack. | Save during active Rage; assert action restrictions, typed damage and remaining temp HP, then encounter-end transition/cooldown. |
| 5 / S2 | Ranger switches hunted prey while using the selected paired attack against a living opponent and skeleton. | Save after marking/first attack; edge applies only to eligible target, preserve paired-attack MAP timing and resistance grouping. |
| 6 / S2 | Monk stance and Flurry against skeleton, then Trip/Grapple or Escape against zombie. | Save between turn/activity boundaries; aggregate same-target Flurry defense correctly, reject second flourish, preserve stance and hand eligibility. |
| 7 / S2 | Rogue and Swashbuckler create an opening with Feint/Tumble Through; then precision attack and finisher. | Save with temporary off-guard/panache; assert target-specific eligibility, duration, finisher restrictions, and post-use resource state. |
| 8 / S2 | Investigator devises a known result, then chooses that target or another legal action/target. | Save after Devise; only its prescribed eligible attack consumes that stored die and gains Strategic Strike. Keep a failed-known-roll alternative meaningful. |
| 9 / S2 | Forensic Investigator rescues an ally injured/knocked out during actual combat using Battle Medicine. | Save with source-specific immunity active; assert restored HP, wounded unchanged, repeat refusal, and later legal treatment timing. |
| 10 / S3 | Wizard switches between spell attack, basic save, curriculum cast, and thesis/bond resource use. | Save after consuming a particular slot/resource; remaining known/prepared entries and cast origin survive; finish the encounter and exercise legal recovery. |
| 11 / S3 | Bard composition overlaps Bless/Guidance or another status effect; Soothe assists a living ally before a mental save. | Save with composition and healing aftermath; assert strongest eligible modifier, composition replacement/extension, and actual save result. Use living targets for mental effects. |
| 12 / S3 | Druid or Ranger commands the wolf companion while the owner moves/attacks; use Support or prey interaction. | Save after command; exactly the minion action allotment, real positioning/flank, Support restrictions, and actual resulting damage. |
| 13 / S3 | Reference-only Untamed/Leaf Druid variants use Untamed Shift/Pest Form or Cornucopia/familiar actions in a continuous encounter/recovery sequence. | If later selected, save in form or with produced consumable; preserve attacks, permitted actions, expiry, and consumed item. Pest Form does not become an Animal Form combat preset at L2. |
| 14 / S3 | Witch casts/Sustains a hex, positions its familiar, and triggers the patron effect before or after resolution. | Save before a trigger decision or during a timed extension; preserve once-per-round gate, effect-instance extension marker, and familiar state. |
| 15 / S3 | Cleric and Champion face zombie/skeleton plus a living creature; vary Heal/Harm action count and a cause reaction. | Save at reaction/area resolution; living healing and undead damage/healing differ correctly, immunity/weakness apply, and reduced damage alters actual survival. |
| 16 / S3 | Sorcerer uses a gift spell and a chosen spell sharing a handler, plus its focus spell. | Save with Blood Magic active; grant provenance controls its trigger, Potency applies only where legal, focus/slot pools remain separate. |
| 17 / S3 | Oracle mixes focus spell and cursebound ability while fighting living/undead targets. | Save at nonzero cursebound; assert limit, curse penalties, Nudge/Foretell or selected mystery's actual outcome, and recovery. |
| 18 / S3 | Selected Bomber uses bombs near allies/skeleton; Mutagenist mutagen attacks and striking-handwrap interaction remain reference inventory. | Save with the Bomber's persistent damage and formula state; initial/splash/resistance separation and end-turn recovery change real outcomes. The Mutagenist branch is future reference. |
| 19 / S3 | Reference-only Toxicologist and Chirurgeon face a living enemy and poison-immune undead; apply eligible field poison conversion and treatment. | If later selected, save during an affliction/coating or treatment immunity; purchased versus field poison origin, exposure/expiry, save stages, and healing resources remain correct. |
| 20 / S3 | Martial/caster pair uses ordinary versus permanent +1 striking equipment, Runic Weapon/Body, a supported spell scroll, and a drop/pick-up or investment boundary. | Save with temporary enhancement/item consumption; compare actual attack/damage/save outcomes, non-stacking, armor potency, resilient versus treatment item bonuses, and expiry. Above-level equipment is labeled as a test grant. |

Choose a small authored roster per row and only enough opponents to survive the required sequence; do not inflate published HP. When a low-HP skeleton dies, use another complete instance or put the unresolved property in a focused test. Scenario checks must not patch HP, inject preexisting damage, or silently replace a monster ability to keep a script moving.

## Level-2 deltas: reuse setups, count only new tactics

Advancement itself does not create twenty more encounter names. Reuse the above setups and record whether the replay exercises a new tactical branch or only an arithmetic/resource assertion.

| Cases | Level-2 addition | Evidence type |
|---|---|---|
| 4 | No Escape movement/reaction choice during Rage | New tactical branch using existing pursuit setup |
| 5 | Hunter's Aim action cost, bonus, and concealment interaction | New tactical branch |
| 6 | Stunning Blows after eligible same-target Flurry; save and incapacitation | New tactical branch; separate higher-level synthetic target focused check |
| 7 | Mobility suppresses reactions only within its movement limit; Tumble Behind supplies next-attack off-guard | Two bounded tactic assertions, not all Rogue × Swashbuckler combinations |
| 8–9 | Athletic Strategist consumes stored die on a maneuver without Strategic Strike; expert Medicine may select DC20 | New maneuver branch and focused medicine delta |
| 10–11, 14, 16 | Added ordinary rank-1 slots/known spells; selected Reach Spell or Wizard feat; required updated spellbook/familiar counts | Resource/preset assertions plus one public cast demonstrating the chosen feat |
| 12–14 | Companion/familiar progression and patron level scaling; still rank-1 forms/focus spells | Numerical assertions in existing setups; no new monster/form tier |
| 15 | Champion resistance scales; cleric's extra ordinary slot and selected Healing/Harming Hands affect real Heal/Harm dice | Numerical/resource assertions and changed outcome |
| 17 | Nudge damage, warning temp HP, extra slot/repertoire, selected cursebound feat | Numeric assertions plus a tactic only if the selected feat adds one |
| 18–19 | Selected Bomber's additional formula and feat; other field formulas and Mutagenist scaling remain reference inventory | Formula/feat branch within existing setup; preserve the selected acquisition counts |
| 20 | Potency becomes ordinary item-level access; higher runes remain explicit grants | Grant/access metadata assertion; no new rune grades |

Do not automatically grant all feats named in a row to one actor. Choose legal L2 presets and exercise alternatives in separate focused cases. Family notes specify the exact subclass values, advancement counts, and feat requirements.

## Prioritized acceptance and bounded execution

1. **Content legality:** every approved representative has a usable preset at each level and all of that preset's grants resolve; unselected subclass inventories are reference only. Keep complete monster profiles; exact known/prepared/repertoire/formula counts; no accidental rank 2, off-tradition unlock, early feat, or above-level ordinary purchase.
2. **Shared mechanics:** ordinary source-informed tests for degree/traits, typed modifier selection, effect-group defense, temporary HP, rune eligibility, conditions and expiration anchors, hand/action requirements, minion commands, cast provenance, and consumable/affliction lifetimes. Include resistance choice, Bestial + striking, undead Heal/Harm, mental/poison immunity, and current bomb failure/critical splash boundaries.
3. **Branch coverage:** a compact explicit table maps each approved representative's selected grant to at least one test that causes its real behavior. Spell count checks and constructor snapshots alone do not establish playability. Test fixed alternative outcomes/choices where the selected build requires them; do not use the encounter count as proof of unselected subclass coverage.
4. **Continuous play:** implement the twenty cases as bounded public-command sequences with deterministic rolls, actual injury, meaningful save/load, and asserted final outcomes. Continue through another encounter or recovery when persistence/cooldowns are the point. Reloaded choices must resolve once and match uninterrupted play.
5. **Integration:** after L1 completion and again after L2, run the serial focused suite and complete encounter catalogue, then review shared helpers for repeated family-specific machinery. Preserve a final limitation list and measured performance evidence; a benchmark or source note is not encounter evidence.

Reuse `tests/interaction_helpers.py`'s bounded EncounterHarness rather than introducing a combinatorial generator. Its existing default bounds (160 commands, 40 choices, 12 rounds, 2000 events) and failure diagnostics are a useful starting point; use a justified smaller or larger bound per authored case. Checkpointing must retain budgets. Keep checks serial, with no watch loops, background processes, or unbounded action-until-success helpers.
