# Alchemist: Player Core 2, levels 1–2

Research handoff, verified 2026-09-15. This document specifies rules and proposed checks; it does **not** report implemented or exercised behavior. Scope: approved Bomber representative with Quick Bomber through level 2, plus a finite few items per Alchemy type. Other research fields remain source reference inventory until selected. No runtime, tests, plans, or work logs were changed by this research owner.

## Source precedence

Use Player Core 2 Remaster entries and [Paizo's official FAQ/errata](https://paizo.com/pathfinder/faq), especially **Player Core 2 Errata (Spring 2026, 1st Printing)**, pp. 59, 61–64, and **GM Core Errata (Spring 2026, 1st Printing)**, p. 244. The [Spring 2026 announcement](https://paizo.com/blog/spring-errata-2026) confirms the affected Alchemist features. Paizo's FAQ was accessible through indexed results while direct fetch returned 403; the current AoN individual entries independently contain the changes. Search snippets and source-index version labels can lag behind those individual entries.

Changes that matter here: distinguish item activation deadlines from effect durations; apply relevant Crafting or Medicine modifiers to Chirurgeon substitutions; Mutagenist suppression lasts one minute; Toxicologist bundles obtaining and applying injury poison; Revivifying Mutagen scales with character level. Bombs explicitly have thrown even where omitted from their trait lists, and both bomb and splash prevent Strength damage. The sections below use the corrected individual entries.

## Level gates and resources

[Alchemist, PC2 pp. 56–60](https://2e.aonprd.com/Classes.aspx?ID=56):

| Level | Required class state |
|---|---|
| 1 | Intelligence key attribute; 8 + Constitution HP/level; trained Perception, Will, Crafting, 3 + Intelligence additional skills, simple weapons, bombs, unarmed attacks, light/medium/unarmored defense, class DC; expert Fortitude/Reflex; alchemy; research field; class feat. |
| 2 | Another class feat and skill feat; two additional common formulas of creatable level; normal HP/proficiency-by-level increase. |

Formula book: two common level-1 formulas, plus four from [Alchemical Crafting](https://2e.aonprd.com/Feats.aspx?ID=5117), plus the field's two. A base formula covers upgraded types, subject to level and prerequisites; functionally distinct types can require separate formulas. Known-formula alchemical items are automatically identified.

| Resource | Creation/refresh | Lifetime |
|---|---|---|
| Advanced Alchemy | Daily; up to 4 + Intelligence consumables; known formula, item level ≤ character level; toolkit suffices; no check, raw-material cost, or downtime days. | Infused; earlier of 24 hours or next daily preparations. |
| Stored versatile vials | Daily maximum 2 + Intelligence; recover two per ten exploration minutes, capped; other exploration activities allowed. | Infused; destroyed at next daily preparations; no duplication/preservation. |

Levels 1–2 use lesser versatile vials: 1d6 acid initial damage, 1 acid splash, negligible Bulk, one hand. No level-2 vial upgrade or discovery. Powerful Alchemy arrives at 5: **do not replace item DCs with class DC at levels 1–2**, including Toxicologist.

## Quick Alchemy and activation

[Quick Alchemy, PC2 p. 59](https://2e.aonprd.com/Actions.aspx?ID=2801) is one action, alchemist/manipulate, requiring worn/held alchemist's toolkit and a free hand.

| Mode | Cost | Result | Latest activation boundary |
|---|---|---|---|
| Create Consumable | One stored versatile vial | One known alchemical consumable, item level ≤ character level; infused; no Crafting check/material payment. | Before creator's next turn starts. |
| Quick Vial | No stored vial | Temporary versatile vial for bomb or own field-vial use only. Cannot fuel Create Consumable. | Before current turn ends. |

An activated Quick Alchemy effect is capped at ten minutes if its ordinary duration is longer. This does not mean every effect ends at the next turn. Ordinary short durations remain short. Applied Quick Alchemy injury poison can remain on its weapon for ten minutes. An affliction delivered before that deadline can continue afterward. Model an unopened item, a weapon coating, and an afflicted creature separately.

[Infused](https://2e.aonprd.com/Traits.aspx?ID=797): nonpermanent effects end at the creator's next daily preparations, except afflictions such as slow-acting poisons. Permanent healing is not reversed. Preparation must expire items/effects wherever they were transferred, not just in the creator's current inventory.

[Elixir activation](https://2e.aonprd.com/Rules.aspx?ID=3184) normally costs one Interact action and one hand: drink, or feed to a creature in reach that is willing or unable to prevent it. Drawing a separately carried consumable and activating it are distinct actions unless an ability combines them. Quick Alchemy itself does not drink an elixir or throw a bomb. Preserve manipulate reaction opportunities and explicit item/hand ownership.

## Approved Bomber field (other fields are reference inventory)

Only the Bomber field and Quick Bomber are selected delivery scope. The Chirurgeon, Mutagenist, and Toxicologist sections below preserve source reference inventory for possible later representatives.

### Bomber

[Bomber, PC2 p. 61](https://2e.aonprd.com/ResearchFields.aspx?ID=5): choose two common level-1 bomb formulas. On throwing a splash bomb, optionally restrict splash to the primary target. This is a choice per throw, not immunity for allies or an always-on area removal. Versatile-vial Strikes may use acid, cold, electricity, or fire damage. Apply the chosen type consistently to initial and splash damage. Intelligence-based splash is a level-5 discovery, unavailable here.

### Chirurgeon

[Chirurgeon, PC2 p. 61](https://2e.aonprd.com/ResearchFields.aspx?ID=6): choose two common level-1 healing elixirs. Crafting rank substitutes for Medicine rank, including prerequisites; Crafting modifier may replace Medicine on every Medicine check. Relevant Crafting **or** Medicine bonuses/penalties apply; ordinary same-type stacking still applies. Narrow bonuses retain their action restrictions: an alchemical-crafting-only lab bonus does not help Treat Wounds. The substitution does not waive the action's tool/time requirements.

Field vial: heal a living creature for initial vial damage (1d6 here); drink it, or Interact to throw it at a willing creature within 20 feet. The throw is not a Strike and uses no attack roll/MAP. Remove acid/splash; add healing/coagulant; drinking additionally adds elixir. No splash healing. No temporary HP discovery at these levels.

[Coagulant](https://2e.aonprd.com/Traits.aspx?ID=796): after actually healing HP from a coagulant item, the recipient cannot heal HP from any coagulant item for ten minutes. Other effects still apply. Track immunity on the recipient across sources and saves. Ordinary Elixir of Life lacks coagulant and remains usable. A full-HP recipient that restores zero HP has not triggered the stated healing condition.

### Mutagenist

[Mutagenist, PC2 p. 61](https://2e.aonprd.com/ResearchFields.aspx?ID=7): choose two common level-1 mutagen formulas. Using a mutagen grants temporary HP equal to max(Intelligence, 0) + floor(level/2), lasting at most one minute and no longer than that mutagen. Cannot gain this temporary HP again for one minute. At Intelligence +4 this is 4 HP at level 1, 5 HP at level 2. These are temporary HP, not healing, and do not stack with another temporary-HP pool.

Drink a field vial to suppress one current mutagen's drawback for **one minute**. Remove acid/bomb/splash; add elixir. This removes the selected mutagen's full Drawback entry, not just one numeric penalty. Attach suppression to that effect instance; drinking a replacement mutagen must not silently inherit it. No physical resistance or Fortitude reroll feature yet.

### Toxicologist

[Toxicologist, PC2 p. 62](https://2e.aonprd.com/ResearchFields.aspx?ID=8): choose two common level-1 alchemical poisons. One action activates an injury poison onto a held weapon, carried ammunition, or ammunition loaded in a held weapon; includes drawing an eligible poison or creating it with Quick Alchemy. Creation still satisfies Quick Alchemy requirements/costs. This does not include the subsequent Strike.

The creator's infused poison-trait items affect poison-immune creatures. Poison damage becomes acid against poison immunity, or when acid is more detrimental (GM determination). Other independent immunities still apply. Ordinary purchased poisons lack this infused benefit.

Field vials replace acid trait/damage with poison, while retaining the field-benefit conversion. They may coat weapon/ammunition as injury poison: add initial vial damage to its first successful Strike, then consume the coating. It expires at **end of current turn**, including coatings made from stored vials. No splash damage, save, affliction stages, or persistent damage from this coating at levels 1–2. Follow injury exposure requirements below; no level-5 resistance or level-11 persistent rider.

## Selected common formula catalog

Catalog is intentionally finite: a few selected level-1 formulas and one level-2 formula for the approved Bomber. A character selects its legal starting formulas from this pool; do not grant the whole catalog automatically. Select two additional previously unknown formulas at level 2. The other field inventories remain reference material.

All listed items have alchemical/consumable traits and Bulk L. Bombs: one hand, Strike activation. Elixirs: one hand, one manipulate action. Injury poisons: two hands and two manipulate actions before Toxicologist compression. Arsenic: one hand, one manipulate action. The sources in each row give the remaining traits.

| Formula/type | Level; price | Exact behavior needed |
|---|---|---|
| [Alchemist's Fire, lesser](https://2e.aonprd.com/Equipment.aspx?ID=3287) | 1; 3 gp | 1d8 fire initial; 1 persistent fire; 1 fire splash. |
| [Acid Flask, lesser](https://2e.aonprd.com/Equipment.aspx?ID=3286) | 1; 3 gp | 1 acid initial; 1d6 persistent acid; 1 acid splash. Do not replace initial damage with 1d6. |
| [Bottled Lightning, lesser](https://2e.aonprd.com/Equipment.aspx?ID=3290) | 1; 3 gp | 1d6 electricity + 1 electricity splash; hit makes target off-guard until thrower's next turn starts. |
| [Frost Vial, lesser](https://2e.aonprd.com/Equipment.aspx?ID=3293) | 1; 3 gp | 1d6 cold + 1 cold splash; hit gives −5-foot status penalty to all Speeds until target's next turn ends. |
| [Elixir of Life, minor](https://2e.aonprd.com/Equipment.aspx?ID=3308) | 1; 3 gp | Living drinker heals 1d6 HP; +1 item bonus to poison/disease saves for ten minutes. Healing/elixir; no vitality trait and no coagulant. |
| [Antidote, lesser](https://2e.aonprd.com/Equipment.aspx?ID=3296) | 1; 3 gp | Healing/elixir; +2 item bonus to Fortitude saves against poison for six hours (Quick Alchemy: ten minutes). Does not cure existing poison or give an immediate save. |
| [Antiplague, lesser](https://2e.aonprd.com/Equipment.aspx?ID=3297) | 1; 3 gp | Healing/elixir; +2 item bonus to Fortitude saves against disease for 24 hours, including progression saves (Quick Alchemy: ten minutes; infused cleanup still applies). |
| [Bestial Mutagen, lesser](https://2e.aonprd.com/Equipment.aspx?ID=3315) | 1; 4 gp | One minute; +1 item Athletics/unarmed attacks; agile claws 1d4 slashing, jaws 1d6 piercing. Drawback: untyped −2 Reflex, Acrobatics, Stealth. **No AC penalty. Striking runes do not modify these attacks.** |
| [Cognitive Mutagen, lesser](https://2e.aonprd.com/Equipment.aspx?ID=3316) | 1; 4 gp | One minute; +1 item Arcana/Crafting/Lore/Occultism/Society/all Recall Knowledge; Recall Knowledge critical failures become failures. Drawback: untyped −2 weapon/unarmed attacks, Athletics, Acrobatics; encumbrance threshold −2 Bulk, maximum carry −4 Bulk. |
| [Giant Centipede Venom](https://2e.aonprd.com/Equipment.aspx?ID=3334) | 1; 4 gp | Injury; DC 17 Fortitude; max six rounds; one-round stages: 1 = 1d4 poison; 2 = 1d4 poison + fatigued; 3 = 1d4 poison + fatigued + clumsy 1. |
| [Arsenic](https://2e.aonprd.com/Equipment.aspx?ID=3322) | 1; 3 gp | Ingested; DC 18 Fortitude; ten-minute onset, five-minute maximum duration; one-minute stages: 1 = 1d4 poison + sickened 1; 2 = 1d6 + sickened 2; 3 = 1d8 + sickened 3. Sickened cannot be reduced while affected. |
| [Black Adder Venom](https://2e.aonprd.com/Equipment.aspx?ID=3324) | 2; 6 gp | Injury; DC 18 Fortitude; max three rounds; one-round stages deal 1d4/1d6/1d8 poison respectively. |

Source-reference field-formula pairs are Bomber acid flask/bottled lightning; Chirurgeon antidote/antiplague; Mutagenist bestial/cognitive; and Toxicologist arsenic/centipede. The selected Bomber uses only its disclosed finite pair; the wider catalogue is not an implementation requirement for this slice.

## Shared damage, defense, and duration rules

### Bomb Strikes

[Current bomb rules, GM Core p. 244](https://2e.aonprd.com/Rules.aspx?ID=3181): martial thrown weapons, normal ranged weapon attack against AC, 20-foot increment; one hand; activation is the Strike. Bombs cannot benefit from runes or talismans, including transferred runes. Applicable general attack/thrown-weapon bonuses can apply. Never add Strength damage, even for a bomb without splash. Current bomb Strikes do not acquire manipulate merely for being bombs; drawing and Quick Alchemy still do. A ranged attack can independently trigger a reaction.

[Splash](https://2e.aonprd.com/Traits.aspx?ID=699):

| Degree | Primary target | Other creatures within 5 feet |
|---|---|---|
| Critical failure | Nothing | Nothing |
| Failure | Splash only | Nothing |
| Success | Initial + splash; applicable hit effects | Splash |
| Critical success | Doubled initial; doubled applicable persistent damage; unchanged splash | Unchanged splash |

Merge primary same-type initial and splash before resistance/weakness. Apply each bystander's defenses independently. Bomber targeting restricts the last column to none. No save is invented for splash; no on-hit condition follows from a miss that dealt splash.

[Persistent damage](https://2e.aonprd.com/Conditions.aspx?ID=86): roll damage at each affected creature's turn end, then DC 15 recovery flat check. Same-type sources use the greater amount; different types coexist. Apply defenses separately from the initial hit. Simultaneous persistent types count as one damage event for triggers such as increasing dying. Assisted recovery and ambiguous greater-amount comparisons require the existing GM-resolution boundary; do not invent item-specific shortcuts. Typical natural expiration is one minute, but the rule expressly assigns that duration to the GM.

### Injury and ingested exposure

[Alchemical poisons, GM Core p. 248](https://2e.aonprd.com/Rules.aspx?ID=3185): applying consumes the poison into a coating. Only one injury poison per weapon/ammunition. A successful piercing/slashing Strike exposes the target; a failure retains the coating; critical failure or a Strike otherwise dealing no piercing/slashing damage spends it without exposure. Resolve resistance before deciding whether the required damage occurred. A coating is distinct from ammunition, which follows normal ammunition consumption. Arsenic is applied to food/drink or directly into a living creature's mouth, and exposure occurs on consumption; it is not an injury-poison substitute.

[Afflictions, Player Core pp. 430–431](https://2e.aonprd.com/Rules.aspx?ID=2389): initial success/critical success prevents infection; failure starts stage 1 and critical failure stage 2 after onset, if any. At each interval, success lowers stage by one, critical success by two, failure raises one, critical failure raises two; below stage 1 ends the affliction, and exceeding maximum stage repeats its effects. Apply entered-stage damage immediately. Re-exposure to poison can advance the existing instance without resetting onset or maximum duration. Affliction damage is not persistent damage and uses no recovery flat check.

[Stage conditions](https://2e.aonprd.com/Rules.aspx?ID=2396) retain their ordinary duration rules. Conditions lacking their own duration, such as clumsy, are tied to the stage. Do not indiscriminately erase every condition when poison ends: fatigued has its own recovery rule, and sickened normally persists until reduced. Arsenic's prohibition on reducing sickened ends with its affliction.

Condition-helper dependencies: [clumsy](https://2e.aonprd.com/Conditions.aspx?ID=61) applies its value as a status penalty to Dexterity-based checks/DCs, including AC and Reflex. [Fatigued](https://2e.aonprd.com/Conditions.aspx?ID=73) applies −1 status AC/all saves, prohibits exploration activities performed while traveling, and ends after a full night's rest. [Sickened](https://2e.aonprd.com/Conditions.aspx?ID=91) applies its value as a status penalty to all checks/DCs and prevents willing ingestion, including elixirs. Its ordinary one-action retch uses Fortitude against the originating effect DC; success/critical success reduces value by one/two. Arsenic blocks that reduction until its affliction ends. Retain the originating DC after affliction cleanup.

### Mutagen compatibility

[Mutagen](https://2e.aonprd.com/Traits.aspx?ID=808) and [polymorph](https://2e.aonprd.com/Traits.aspx?ID=670): another polymorph attempts to counteract the active effect; do not freely stack or automatically replace two mutagens at these levels. A mutagen uses its item's level and the level-based DC minus ten as its check modifier. For nonspells, [counteract rank](https://2e.aonprd.com/Rules.aspx?ID=3280) is half level rounded up. A successful counteract replaces the original; a failed counteract leaves it in place. Bestial granted Strikes are magical under polymorph; this does not make the mutagen a spell or a battle form. Apply ordinary Strength damage and agile MAP to its unarmed attacks; don't impose battle-form hand/gear restrictions.

## Selected feat choices through level 2

These are selectable content, not automatic field benefits. At level 1 expose Quick Bomber and Far Lobber; at level 2 also expose the three options below. This supplies legal choices while keeping optional content bounded.

| Feat | Needed mechanics |
|---|---|
| [Quick Bomber, 1](https://2e.aonprd.com/Feats.aspx?ID=5764) | One action: draw bomb, draw versatile vial, or Quick Alchemy a bomb, then Strike. Quick Vial is eligible; creation prerequisites/costs remain. Only the Strike advances MAP. |
| [Far Lobber, 1](https://2e.aonprd.com/Feats.aspx?ID=5763) | Bomb range increment 30 feet. Does not turn Chirurgeon's fixed-range Interact healing into a 30-foot ability. |
| [Revivifying Mutagen, 2](https://2e.aonprd.com/Feats.aspx?ID=5769) | One concentrate action, requires active mutagen; ends it and heals 1d6 per two character levels (1d6 here). Also end benefits, drawbacks, and temporary HP tied to that mutagen. No coagulant restriction is added. |
| [Pernicious Poison, 2](https://2e.aonprd.com/Feats.aspx?ID=5768) | Additive on a Quick Alchemy consumable poison: ordinary initial save success deals poison damage equal to item level; critical success none. Not a new splash area/trait. Once/round additive limit, one additive/item, never Quick Vial. |
| [Improvise Admixture, 2](https://2e.aonprd.com/Feats.aspx?ID=5767) | One concentrate/manipulate action, once/day, toolkit worn/held, below vial maximum. Crafting against level-based DC, normally DC 16 at level 2; critical success/success/failure/critical failure recover 3/2/1/0, capped. |

## Proposed source-informed assertions (Bomber acceptance first; other fields reference)

Not run. Use fixed roll streams so each degree, transition, and defense result is inspectable. Cross-references above establish the rule oracle; test effects through public actions rather than calling item-specific exceptions.

1. **Creation isolation:** spending the full Advanced Alchemy budget leaves the stored-vial budget intact. Unknown formulas, excessive item levels, missing toolkit/free hand, and attempting to fuel Create Consumable with Quick Vial fail validation without partial state mutation.
2. **Four lifetime boundaries:** save/load unopened Quick Consumable before creator's next turn, Quick Vial before turn end, activated antidote, and applied injury poison. Advance across each deadline. Only the corresponding unopened item/effect expires; affliction delivery before coating expiry remains valid afterward.
3. **No critical splash multiplication:** lesser acid flask critical hit produces primary immediate acid 3 and persistent acid 2d6; adjacent creature gets acid 1. Failure gives primary acid 1 only. Test resistance 2: the critical primary immediate packet becomes 1, not separately reduced to 0 twice. Test weakness once on that packet.
4. **Bomber choices:** repeat a hit next to an ally with area enabled/disabled; change vial element against an appropriate resistance/weakness. Verify no Intelligence splash at either supported level.
5. **Reference-only Chirurgeon:** Quick Vial then ranged Interact restores HP without attack/MAP; repeat before immunity ends fails to heal, but ordinary Elixir of Life works. Exercise living/willing/range boundaries. Medicine substitutions use Intelligence/Crafting, action-specific bonus filtering, and same-type stacking.
6. **Bestial:** compare AC unchanged, three −2 penalties active, claws agile and jaws non-agile, fixed dice despite striking. Suppress then advance time; consume Revivifying Mutagen at level 2 and remove tied temporary HP. Consume another mutagen inside the temporary-HP cooldown and exercise successful/failed counteraction.
7. **Reference-only Toxicologist:** from worn toolkit and free hand, create/apply centipede poison in one action, then Strike. Non-Toxicologist pays ordinary creation/application costs. Check miss retention, critical-miss loss, piercing immunity causing no exposure, coating expiry, and ordinary save vs critical save outcomes.
8. **Poison immunity:** infused poison affects poison-immune target using acid damage; repeat with noninfused poison and with separate immunity to a stage condition. Preserve condition effects that remain legal. Log explicit GM choice when acid is more detrimental without immunity.
9. **Poison stages:** fixed initial critical failure enters stage 2 immediately; then a successful interval save reaches stage 1 and deals its damage. Re-exposure escalates without extending the maximum duration. Arsenic advances the clock through onset and minute intervals, with no retch reduction while active.
10. **Daily continuity:** ten-minute exploration restores capped vials during another legal exploration activity. Daily preparation invalidates old stock transferred to another actor and old nonpermanent infused buffs, while retaining already-inflicted afflictions and restored HP. Save/load must retain ownership/provenance and deadline identity.
11. **Level-2 gates:** reject Black Adder at 1; allow it at 2 with known formula. Verify its fixed DC, shorter maximum duration, and Pernicious success damage. Level 2 must not accidentally unlock moderate bombs/mutagens or new proficiency ranks.

## Continuous encounter proposals (Bomber delivery; other fields reference)

Run the four research-field characters through two consecutive small encounters with a ten-minute exploration interval, a save/load in that interval, and daily preparation afterward. Use existing source-backed opponents; the following roles are test setup, not new monster statistics.

- **Bomber:** clustered opponents and an adjacent ally; throw bottled lightning, follow with an ally attack before off-guard expires, then exercise an ordinary miss and an element switch.
- **Reference-only Chirurgeon:** heal a wounded frontliner at range, then feed an elixir in reach after coagulant immunity; use Crafting-backed Treat Wounds during exploration and confirm concurrent vial refresh.
- **Reference-only Mutagenist:** drink bestial, enter melee with claws/jaws, suppress drawbacks, face a Reflex save; in the level-2 pass consume the mutagen for healing before an opponent attacks the reduced temporary-HP pool.
- **Reference-only Toxicologist:** begin with an Advanced Alchemy poisoned weapon, deliver or retain its coating, then create/apply a fresh poison during combat. Include one poison-immune target where available and an Arsenic ingestion/time-advance probe outside combat. Level 2 adds Black Adder/Pernicious checks.

These encounter runs should produce action/resource/deadline/condition traces and fail with the last useful state on timeout. The research owner launched no engine or test processes; process-audit responsibility remains with the implementation/integration owner.

## Explicit limits and decisions

- **Automatic toolkit retrieval is an unsupported convenience, not a blocker.** [Toolkit](https://2e.aonprd.com/Equipment.aspx?ID=2702) permits drawing/replacing its tools as part of use; the class permits keeping versatile vials inside it. Neither consulted entry unambiguously grants free retrieval for every bomb/drink/healing activation. The supervisor selected explicit held-item/draw paths, the expressly bundled draw in Quick Bomber/Toxicologist, and Quick Vial followed by activation. Those legal paths cover the selected Bomber's mandatory features. Do not expose an automatic-toolkit-retrieval shortcut.
- **GM choices need literal input:** “more detrimental” acid conversion, ambiguous persistent-damage comparison/recovery, and circumstances changing Improvise Admixture DC are not universal optimization formulas. Request/record the concrete ruling when needed; do not emulate unknown target information as character knowledge.
- **Field-vial poison uses injury delivery.** The general piercing/slashing gate remains applicable because the feature calls it an injury poison and gives no explicit override. Its direct added damage and end-turn expiry replace an ordinary poison's save/stages/coating lifetime. Do not add a fictitious save.
- **No unsupported approximation:** unselected formulas, higher-level discoveries, Combine Elixirs, inhaled/contact poisons, and other optional feats remain unavailable until separately implemented. The selected Bomber's mandatory field features remain required; the other research fields are reference inventory until separately selected.
