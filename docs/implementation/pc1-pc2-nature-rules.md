# S3i nature rules: Druid, Ranger, companions, familiars, and forms

Source review: 2026-09-15. Scope: approved representatives are Storm Druid with Animal Empathy and Precision Ranger with Hunted Shot. Other druid orders and ranger edges remain source reference inventory. Implement selected level 1 representatives, then level 2. Player Core 2 adds no mandatory subclass to this family. This is an implementation specification and proposed evidence, not a claim that the engine implements or has exercised these rules.

## Source/version boundary

Use the remastered AoN entries linked below and [Paizo's current FAQ/errata](https://paizo.com/pathfinder/faq). The direct FAQ fetch returned HTTP 403; the official search extract exposed its current Player Core Spring 2026 and prior errata passages. [Paizo's Spring 2026 announcement](https://paizo.com/blog/spring-errata-2026) confirms the familiar/Pet replacement change and movement correction for mature companions.

Applicable corrections: **Tempest Surge has no persistent electricity damage**; familiar replacement uses Pet's downtime rule. Mature-companion movement errata is later-level and supplies no autonomous action to the young companions here. Do not import the legacy druid metal-armor prohibition, old Wild Shape name, Goodberry, or legacy focus-pool increases for Leaf/Storm.

Mandatory granted focus spells may be uncommon: their class grant supplies access. “Common optional content” constrains elective menus, not those fixed grants. Cultivation/Spore, Flame/Stone/Wave, and Vindication are outside this two-book subclass census.

## 1. Fixed class chassis and level-2 delta

| Statistic | Druid | Ranger |
|---|---|---|
| Key attribute | Wisdom | Strength or Dexterity |
| Class HP each level | 8 + Constitution | 10 + Constitution |
| Perception | Trained | Expert |
| Saves | Fortitude/Reflex trained; Will expert | Fortitude/Reflex expert; Will trained |
| Attacks | Simple and unarmed trained | Simple, martial, and unarmed trained |
| Defense | Light, medium, unarmored trained | Light, medium, unarmored trained |
| Class DC | Trained | Trained |
| Skills | Nature, order skill, 2 + Intelligence additional | Nature, Survival, 4 + Intelligence additional |

Druid uses Wisdom for trained primal spell attacks/DC. Prepare five cantrips and two rank-1 slots at level 1; level 2 gives three rank-1 slots. It also grants Shield Block, Wildsong, anathema, Voice of Nature, and the selected order package. Ranger grants Hunt Prey, the selected edge, and one selected level-1 ranger feat. Both gain a class feat and skill feat at level 2. Add level-based proficiency/HP normally; neither gets a skill increase or higher proficiency rank at level 2. Sources: [Druid](https://2e.aonprd.com/Classes.aspx?ID=34), [Ranger](https://2e.aonprd.com/Classes.aspx?ID=36).

Order focus spells use one shared focus pool, maximum `min(3, number of focus spells known)`. Their rank is `ceil(level / 2)`, hence rank 1 throughout this slice. Daily preparation replenishes the pool; each 10-minute Refocus regains one point, up to maximum. Untamed starts with **two** focus spells and a pool of 2; other initial orders have one. [Order/focus rules](https://2e.aonprd.com/DruidicOrders.aspx).

## 2. Selected Storm order: mandatory closure

The order table preserves source reference inventory; delivery exercises the Storm row with Animal Empathy. Other orders remain outside the selected representative roster.

| Order | Trained skill | Granted feat | Order spell | Additional anathema summary |
|---|---|---|---|---|
| Animal | Athletics | Animal Companion | Heal Animal | Needless animal killing or wanton cruelty; clean food kills/self-defense excepted |
| Leaf | Diplomacy | Leshy Familiar | Cornucopia | Needless plant/fungus killing or wanton cruelty; survival harvest/self-defense excepted |
| Storm | Acrobatics | Storm Born | Tempest Surge | Air pollution; allowing major polluters/climate disruptors to go unpunished, with printed safety/actual-harm qualifications |
| Untamed | Intimidation | Untamed Form | Untamed Shift | Becoming fully domesticated/reliant on civilization; temporary adventure stays and processed goods allowed |

If already trained in the order skill, choose a replacement skill. Source: [Orders](https://2e.aonprd.com/DruidicOrders.aspx).

Voice of Nature is a real choice of [Animal Empathy](https://2e.aonprd.com/Feats.aspx?ID=4709) or [Plant Empathy](https://2e.aonprd.com/Feats.aspx?ID=4711): rudimentary questions/answers and Diplomacy with the corresponding creatures. It does not grant automatic obedience, extra combat commands, or animal intelligence. Minimal authored builds can choose Animal Empathy, with a local dialogue/attitude input when exercised. Wildsong and anathema are character facts, not invented per-round checks. Base anathema: despoiling natural places, consuming more natural resources than needed for comfortable life, teaching Wildsong to non-druids. Repeated violations remove druid magic/order benefits until atonement; adjudicated violation state should be explicit if the local slice includes it.

### Animal

[Animal Companion](https://2e.aonprd.com/Feats.aspx?ID=4708) grants one young companion, not an independent party member. Use the wolf definition below.

[Heal Animal](https://2e.aonprd.com/Spells.aspx?ID=1855), rank 1: one willing living **animal**, not any ally or any companion. One action, manipulate, touch: heal 1d8. Two actions adds concentrate, range 30 feet, heal 1d8+8. No three-action mode. One Focus Point per casting; no prepared slot. A plant/fungus leshy familiar is not a valid target. A druid currently in Pest Form has the animal trait and can qualify if otherwise willing/living.

### Leaf

[Leshy Familiar](https://2e.aonprd.com/Feats.aspx?ID=4710) grants a Tiny familiar with a free plant **or** fungus ability, beyond its usual two daily choices. Use a plant-bodied familiar with Manual Dexterity and Tough initially; the common pool may also expose the corresponding fungus alternative without extra combat powers.

[Cornucopia](https://2e.aonprd.com/Spells.aspx?ID=1856), rank 1: two actions, concentrate/manipulate, one Focus Point; creates one piece of produce in a cornucopia in the caster's hands. A creature uses Interact to eat it and heals 1d6+4. Casting itself does not heal. Produce and horn expire after 10 minutes. Persist the created item, location/holder, origin, expiry, and consumed state. Passing/dropping/retrieving it uses ordinary item actions. There is no extra produce at character level 2; heightening waits for level 3.

### Storm

[Storm Born](https://2e.aonprd.com/Feats.aspx?ID=4712) removes **weather-caused circumstance penalties** to ranged spell attacks and Perception, and bypasses flat checks for targeted spells against weather-concealed targets. It does not bypass darkness, unrelated concealment, cover, or weather penalties on ordinary bow attacks. Tag penalty/concealment provenance in local environmental input.

[Tempest Surge](https://2e.aonprd.com/Spells.aspx?ID=1860), rank 1: two actions, concentrate/manipulate, 30 feet, one creature, one Focus Point; 1d12 electricity with basic Reflex. Failure adds clumsy 2 for one round. Apply clumsy also on critical failure by the [unlisted critical effect rule](https://2e.aonprd.com/Rules.aspx?ID=2286), with damage independently scaled by [basic saves](https://2e.aonprd.com/Rules.aspx?ID=2297). This is an explicit cross-reference interpretation to verify in rules review. No persistent electricity. Clumsy affects all Dexterity-based checks/DCs, including AC, Reflex, ranged attacks, finesse attacks using Dexterity, and relevant skills; it is not merely an AC flag.

### Untamed

The [Untamed Form feat](https://2e.aonprd.com/Feats.aspx?ID=4713) grants the spell of that name **in addition** to the order's Untamed Shift.

[Untamed Shift](https://2e.aonprd.com/Spells.aspx?ID=1862), rank 1: one action for the available claws, concentrate/manipulate/morph, one Focus Point, duration one minute. Claws are magical unarmed attacks, 1d6 slashing, agile and finesse. Use ordinary unarmed proficiency, Strength damage, and whichever legal attack attribute is selected. One free hand is needed to Strike; transformed hands can otherwise still hold/use items. This is not a battle form and does not prohibit ordinary casting. Other Shift modes require later feats absent at levels 1–2. [Morph](https://2e.aonprd.com/Traits.aspx?ID=657) governs overlapping transformations and same-body-part counteracting.

[Untamed Form](https://2e.aonprd.com/Spells.aspx?ID=1861), rank 1: two actions, concentrate/manipulate/polymorph, one Focus Point, Pest Form for 10 minutes. Animal Form only unlocks at **spell rank 2 / character level 3**. The spell's +2 status attack bonus applies only when legally using one's own attack modifier in a form that allows attacks; Pest Form grants no such attack.

[Pest Form](https://2e.aonprd.com/Spells.aspx?ID=1626): choose a rat for the minimal menu; cosmetic cat/lizard/insect selections have identical statistics. Tiny, animal trait, no Strikes, Speed 20 feet, AC `15 + character level`, physical weakness 5, low-light vision, imprecise scent 30 feet. Acrobatics/Stealth +10 or own modifier if higher; Athletics −4. Ignore armor check/Speed penalties. Dismiss is available. It grants no climbing/swimming/flying Speed at rank 1.

[Polymorph](https://2e.aonprd.com/Traits.aspx?ID=670) supplies the mandatory restrictions: battle-form special statistics allow circumstance/status bonuses and penalties only; casting, speaking, most hand-dependent manipulate actions, and item activations are unavailable. Gear merges while constant benefits continue. Replace Speeds with form Speeds. A second polymorph must counteract the first. Claw attacks cannot override Pest Form's Strike prohibition; adjudicate morph incompatibility explicitly instead of retaining a hidden attack. Restore original statistics, gear availability, and Speed on expiry/dismissal.

## 3. Selected Precision edge: Hunt Prey

The edge table preserves source reference inventory; delivery exercises the Precision row with Hunted Shot. Other edges remain outside the selected representative roster.

[Hunt Prey](https://2e.aonprd.com/Actions.aspx?ID=2257) costs one concentrate action. Target must be seen/heard, or tracked in exploration; no numeric 30-foot range restriction exists. One designated creature; new designation replaces old, lasting until next daily preparation. Apply +2 circumstance to Seek/Track checks specifically for prey. Ranged attacks against prey ignore the **second** increment penalty; farther increments keep their ordinary penalties. A 60-foot-increment bow therefore has 0 range penalty at 65–120 feet against prey, and −4 at 125–180 feet. Marking is not itself an attack and neither spends nor resets MAP.

| Edge | Required behavior at levels 1 and 2 | Source |
|---|---|---|
| Flurry | Attacks against prey have MAP −3/−6; agile −2/−4. Count all prior attacks normally, even those against other targets. Non-prey attacks keep normal MAP. Applies to attacks, not only weapon Strikes. | [Flurry](https://2e.aonprd.com/HuntersEdge.aspx?ID=4) |
| Outwit | +2 circumstance to Deception, Intimidation, Stealth checks against prey and Recall Knowledge about prey; +1 circumstance AC against prey attacks. Keep target context and usual bonus stacking. | [Outwit](https://2e.aonprd.com/HuntersEdge.aspx?ID=6) |
| Precision | First hit on hunted prey in a round adds 1d8 precision of the attack's damage type. Preserve immunity and critical doubling. Misses do not spend it; re-marking does not reset it. | [Precision](https://2e.aonprd.com/HuntersEdge.aspx?ID=5) |

The [Ranger Animal Companion feat](https://2e.aonprd.com/Feats.aspx?ID=4708) shares Hunt Prey's benefits and the edge with the companion. Each creature tracks its own attacks and first-hit precision use; the ranger's first hit does not consume the companion's precision. No shared MAP unless a separate rule, such as riding, actually requires it.

Minimal legal elective feats:

- [Hunted Shot](https://2e.aonprd.com/Feats.aspx?ID=4861), level 1: one action/flourish, reload-0 ranged weapon, two Strikes at prey; normal sequential MAP. If both hit, combine damage for resistance/weakness. Consume two ammunition units if both shots occur. Each subordinate Strike retains normal reaction/check handling; paying one action does not mean counting one attack.
- [Twin Takedown](https://2e.aonprd.com/Feats.aspx?ID=4864), level 1: same paired-Strike/MAP/damage-combination pattern, one different-hand melee weapon each. A useful small alternative to Hunted Shot; optional if the initial menu chooses only ranged or companion builds.
- [Hunter's Aim](https://2e.aonprd.com/Feats.aspx?ID=4867), level 2: two concentrate actions, one ranged weapon Strike at prey; +2 circumstance attack, ignores concealment and **lesser cover**. Standard/greater cover and hidden targeting checks remain. Current remaster includes lesser-cover bypass.

The selected Precision edge uses Hunted Shot at level 1 and Hunter's Aim at level 2. A companion route can take Animal Companion at level 1 and Hunted Shot at level 2 as reference inventory. Warden spells are elective here: none is a fixed edge grant. Do not add a spellcasting resource to ranger builds that did not select one.

## 4. Shared animal companion and minion rules

[Young companion rules](https://2e.aonprd.com/Rules.aspx?ID=2113): one companion, same level as owner; trained unarmed, unarmored, barding, all saves, Perception, Acrobatics, Athletics, plus type skill. HP = type HP + level × (6 + Constitution). Only item bonuses to Speed/AC apply, maximum AC item bonus +3. Mental limitations still apply. Dead companions may be replaced after a week of downtime at no cost.

[Command an Animal](https://2e.aonprd.com/Actions.aspx?ID=2400) is one auditory/concentrate action. For these companions/Pet-based familiars, no Nature roll: command grants their two actions on the owner's turn. [Minion](https://2e.aonprd.com/Traits.aspx?ID=653) acts once per owner turn, ordinarily has zero reactions, cannot command minions, and cannot gain a second full action allotment from repeated commands. Slowed/quickened change its allotment when granted. Uncommanded young companions have no routine free action; defensive/obvious-harm exceptions require explicit local adjudication, not an autonomous attack policy.

[Support](https://2e.aonprd.com/Actions.aspx?ID=2665) is one companion action. A support turn permits only basic move actions to reach supporting position as its other actions. An earlier Strike prevents Support; Support prevents a later Strike. Support is not a Strike, and a caster's saving-throw spell does not trigger a benefit that specifically requires their damaging Strike.

### Selected common companion: wolf

[Wolf](https://2e.aonprd.com/Companions.aspx?ID=83): Small; jaws 1d8 piercing/finesse; modifiers Str +2, Dex +3, Con +2, Int −4, Wis +1, Cha +0; ancestry HP 6; Survival trained; Speed 40; low-light, imprecise scent 30. No mount ability. No advanced Takedown at these levels.

Derived unarmored values:

| Level | HP | AC | Jaws attack/damage | Fort / Reflex / Will | Perception | Athletics / Acrobatics / Survival |
|---|---:|---:|---|---|---:|---|
| 1 | 14 | 16 | +6, 1d8+2 | +5 / +6 / +4 | +4 | +5 / +6 / +4 |
| 2 | 22 | 17 | +7, 1d8+2 | +6 / +7 / +5 | +5 | +6 / +7 / +5 |

Wolf Support lasts until owner's next turn starts: owner's damaging Strikes against creatures the wolf threatens give −5-foot **status** Speed penalty for one minute, or −10 on the Strike's critical success. Do not stack repeated status penalties; retain distinct expiry/source facts as needed. Current young wolf does not trip automatically.

Riding requires a companion at least one size larger than rider. Without mount, a ridden companion can use only land Speed and cannot move and Support on the same turn. Initial Medium PC + Small wolf deliberately has no legal riding path; mounts are elective deferred content, not a guessed riding implementation.

## 5. Shared familiar requirements (coordinate with arcane owner)

Use one shared familiar/Pet implementation for Druid, Witch, and Wizard. [Pet](https://2e.aonprd.com/Feats.aspx?ID=5186) gives Tiny minion, owner's level, 5 HP/level, low-light vision, land Speed 25, and AC/saves copied from owner's values before circumstance/status adjustments. Familiar has no own attributes or item bonuses. Pet skills are level only except Perception/Acrobatics/Stealth = level+3; [familiar rules](https://2e.aonprd.com/Rules.aspx?ID=2121) permit level+spellcasting attribute for those three if higher. Apply the familiar's own relevant conditions to its copied baseline.

Familiars cannot take attack actions except Escape/Force Open; an effect asking them to Strike does not give a Strike. They cannot flank without an eligible attack. Empathic communication with owner works within one mile but supplies no ordinary speech/language. Choose two familiar/master abilities at daily preparation, retaining innate required choices. Only one trait-changing ability is allowed. Replacement follows Pet: one week downtime, releasing the previous pet. Witch-specific replacement/abilities can override these defaults.

Reference-only Leaf familiar selection: free Plant ability, Manual Dexterity, Tough. Manual Dexterity permits up to two handlike limbs for manipulate actions; Tough adds 2 HP/level (total **7/14 HP** at levels 1/2). A Wisdom +4 druid yields familiar Perception/Acrobatics/Stealth +5/+6, other skills +1/+2. Use ordinary Interact handoff and movement for tangible utility. These abilities do not authorize magic-item activation or attacks. No flight, speech, independent action, or delivery-of-spells is silently supplied. Arcane source owner confirmed this shared grounded selection; its Witch/thesis-specific extra choices and replacement overrides belong in that family's contract.

## 6. Necessary geometry and state, without a new framework

Tiny creatures share squares with other Tiny and larger creatures; at least four Tiny fit a square. Their usual reach is zero. Small wolves use one 5-foot square and 5-foot reach. [Size/space rules](https://2e.aonprd.com/Rules.aspx?ID=2359). Form/familiar admission therefore requires size-aware occupancy; rejecting every occupied destination is no longer sufficient. Loss of ability to Strike must affect flanking eligibility.

All selected nature movement is grounded: Speed 20/25/40 and ordinary movement with Tiny occupancy. This family does not itself force flight, climbing Speed, swimming Speed, or Large footprints at levels 1–2. Other families may require those and should share the same core owner. Pest species labels must not confer unlisted movement modes.

Concrete core dependencies:

1. Owned creature IDs separate from ordinary initiative; persisted command/action allowance, subordinate continuation, independent MAP, and action restrictions. Save during minion movement/reaction and restore the owner's remaining actions.
2. Target-scoped Hunt Prey state, precision usage, circumstance modifiers, paired-Strike continuation, shared resistance/weakness application.
3. Prepared and focus sources; Refocus/daily preparation; focus count; expiry in rounds/minutes; correctly owned Dismiss/Sustain actions.
4. Reversible form/morph state queried by effective statistics, available actions, gear, size, senses, and movement. Keep original actor identity and HP.
5. Weather/concealment provenance; clumsy; timed typed Speed penalties; ordinary item transfer/consumption for Cornucopia.
6. Subordinate ownership/initial definitions and created item origins validated on load. A familiar must not get an independent three-action turn or automatically keep a defeated party active.

These are small feature/state requirements for the existing local engine. They do not require arbitrary stat-block ingestion or a generic effects DSL.

## 7. Minimal common elective spell/feat menu

The selected Storm Druid needs five actual prepared cantrips. A compact shared selection is [Electric Arc](https://2e.aonprd.com/Spells.aspx?ID=1509), [Guidance](https://2e.aonprd.com/Spells.aspx?ID=1549), [Stabilize](https://2e.aonprd.com/Spells.aspx?ID=1689), [Tangle Vine](https://2e.aonprd.com/Spells.aspx?ID=1713), and [Light](https://2e.aonprd.com/Spells.aspx?ID=1585). Slots can choose [Heal](https://2e.aonprd.com/Spells.aspx?ID=1554) and [Runic Weapon](https://2e.aonprd.com/Spells.aspx?ID=1658); duplicate preparation fills the third level-2 slot legally. Reuse the shared spell owner; every selected spell must be fully admitted, not just listed.

Additional closure from this particular cantrip selection: Electric Arc uses one/two targets in 30 feet, 2d4 electricity/basic Reflex; Tangle Vine uses a ranged spell attack, 30 feet, one round of −10-foot circumstance Speed penalty, adding immobilized on critical success, with Escape against spell DC; Light creates a mobile illumination orb, four-instance limit, attached/unattached state, Sustain movement, Dismiss, and until-preparation duration. If illumination is not in the shared slice, choose another source-reviewed common primal cantrip before admitting these builds.

At level 2, the selected Storm Druid can select [Reach Spell](https://2e.aonprd.com/Feats.aspx?ID=4577): one concentrate/spellshape action, immediately following Cast with range gains 30 feet (touch becomes 30). An intervening action/reaction or turn end loses it. It does not create a range for self-only Cornucopia/Form. Other order choices remain reference inventory. Skill-feat selection belongs to the shared curated menu and must meet its prerequisites.

## 8. Selected representative examples and reference inventory

The following are expected outcomes, **not executed tests**. Storm Druid and Precision Ranger bullets are selected-representative scope; Animal, Leaf, Untamed, Flurry, and Outwit bullets preserve source reference inventory only.

- Animal L1: Command wolf, wolf Strides then Supports, owner hits a threatened foe: one owner action spent, two wolf actions spent, Speed penalty applied; neither a wolf Strike nor a second command is legal afterward. On another turn wolf Strides/Strikes instead; its normal damage is 1d8+2. Heal Animal with d8=4 heals 12 at 30 feet, 4 at touch; Leaf familiar target rejected atomically.
- Ranger Precision with wolf: ranger and wolf each first hit prey in the round adds their own d8; the second hit of each does not. Miss then hit still grants precision. Switching prey after a hit does not restore it. Save/load retains those facts.
- Leaf L1: Cast Cornucopia creates one item, pass it, ally Interacts and heals 7 with d6=3. A second consumption fails; an uneaten item expires after ten minutes. Commanded familiar can move and transfer an item when actions/hands permit, but cannot Strike or flank.
- Storm L1: Tempest Surge with d12=7 gives damage 0/3/7/14 by save degree, clumsy 2 on failure/critical failure for one round; verify no persistent damage. Weather-concealed targeted spell skips flat check; same spell against non-weather concealment does not. Bow attacks retain normal restrictions.
- Untamed L1: pool 2 -> claws costs 1 -> Strike allowed with free hand, d6+Strength, agile MAP. Both hands occupied rejects claw attack without mutation. Pest Form costs remaining point, grants AC16/Speed20/physical weakness5, forbids Strikes/casting, and permits Tiny co-occupancy. Dismiss restores original state; Refocus 10 minutes returns one point. Do not add +2 attack to claws merely because Untamed Form is known.
- Ranger Flurry: first attack against non-prey, second agile attack against prey is −2, third non-agile prey attack −6; second attack against non-prey is ordinary −5/−4. A paired attack advances the attack count twice.
- Ranger Outwit: check/AC bonuses apply only to prey context; a +2 shield circumstance AC bonus does not stack with its +1. Seek/Track use Hunt Prey's bonuses, not an additional unrelated Outwit bonus.
- Range: 60-foot bow at 120 feet against prey has 0 range penalty; 125 feet has −4. Hearing a prey more than 30 feet away permits Hunt Prey when other conditions hold. Changing designation removes all target-specific benefits from old prey.
- Level 2: druid slots 3, still five cantrips/rank-1 focus values; Pest AC17; wolf HP22/attack+7/AC17; familiar Tough HP14. Hunter's Aim can ignore lesser cover/concealment but not standard cover or hidden checks. Reach Spell plus two-action Heal Animal reaches 60 feet within three owner actions.
- Each selected representative family needs an actual bounded encounter and meaningful mid-action save/load continuation comparison. For the selected Storm/Precision pair, combine focus expenditure, prey switching, and a later real victory through legal public commands. Companion and form routes remain reference scenarios until their representatives are selected.

## Run/handoff record

Author task: `/root/rules_nature_classes`; `CODEX_THREAD_ID=01a0a70d-bbcc-7243-a6a6-642f93ec3aa8`. Only this document authored; no runtime/test edits, tests, background probes, or subagents. Bounded shell reads exited. Token counters unavailable within this agent; supervisor should collect final run telemetry or record null with that reason.
