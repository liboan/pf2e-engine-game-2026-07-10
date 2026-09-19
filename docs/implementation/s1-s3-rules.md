# S1–S3 rules and fixed roster

Implementation research, reviewed **2026-09-15**. Sources below are the Remaster Player Core (PC) and Monster Core (MC) entries actually read on Archives of Nethys. This note proposes content; it does not claim implementation or runtime verification. Stage ownership remains with the supervisor. Source URLs are attached to each dependency rather than an exhaustive book catalogue.

## S1: executable boundary and expected cases

Use the plan's synthetic two-actor 7×5 fixture, ordinary 5-foot reach, 25-foot Speed, one non-agile melee Strike, explicit numeric statistics, and prototype defeat at 0 HP. They are not PCs or shortened published monsters. Both are NPC-style for initiative ties: a documented GM setup-order tie choice is sufficient for this fixture.

| Rule and source | Required behavior / independent expected case |
|---|---|
| [Degree, PC401](https://2e.aonprd.com/Rules.aspx?ID=2286), [natural rolls](https://2e.aonprd.com/Rules.aspx?ID=2287) | Total at DC+10 critical success; DC through DC+9 success; DC−9 through DC−1 failure; DC−10 or below critical failure. Then natural20 raises one degree and natural1 lowers one, clamped. At DC20, totals10/11/19/20/29/30 yield CF/F/F/S/S/CS before natural adjustment. Natural20+0 vs DC40 is failure; natural1+29 vs DC20 is success. |
| [MAP, PC402](https://2e.aonprd.com/Rules.aspx?ID=2289) | Ordinary attacks use 0, −5, −10, −10; misses count. Agile uses 0/−4/−8 based on the CURRENT attack's trait. Intervening movement does not reset attacks. MAP applies during own turn. |
| [Damage, PC407](https://2e.aonprd.com/Rules.aspx?ID=2307) | Roll ordinary damage then double the complete total on critical Strike. Die4+modifier3 becomes14, not11. Critical-only extra dice are added afterward. Halving rounds down, except a positive1 halves to1. No damage dice on a miss. |
| [Stride](https://2e.aonprd.com/Actions.aspx?ID=2305), [Step](https://2e.aonprd.com/Actions.aspx?ID=2304), PC418 | Each costs1 and has move trait. Stride up to Speed; unused movement is lost. Step moves5 feet, requires land Speed≥10, cannot enter difficult terrain, exempts move/square-trigger reactions. |
| [Grid, PC421](https://2e.aonprd.com/Rules.aspx?ID=2356) | Straight steps cost5; diagonal steps alternate5/10 across ALL movement actions in the turn; reset at END turn. Four diagonals cost30. First diagonal Stride then diagonal Step is illegal because the next diagonal costs10. A straight step never resets parity. |
| [Reach, PC422](https://2e.aonprd.com/Rules.aspx?ID=2359) | Small/Medium occupy1 square, ordinary reach5. Adjacent diagonal is reachable. Two diagonal squares are15 feet. Distance/reach queries do not inherit the actor's movement parity. |
| [Initiative, PC435](https://2e.aonprd.com/Rules.aspx?ID=2423) | Rank d20+Perception descending; no degree comparison or natural20 promotion. Enemy beats a tied PC; tied PCs choose their order. Use separate PC/NPC facts, not team names. NPC–NPC ties use documented GM order. |
| [Start turn, PC435](https://2e.aonprd.com/Rules.aspx?ID=2428), [act, PC436](https://2e.aonprd.com/Rules.aspx?ID=2429) | Start-turn effects precede the final regain3 actions/1 reaction step. Third action completes then turn ends; early End Turn loses unused actions. No action or reaction accumulation. S1 attack count refreshes for new turn; initiative is not rerolled between rounds. |

Rejected paths, unavailable targets, insufficient actions, and stale choices preserve both state and random-generator state. Inspect/options are read-only. Save retains initiative/current turn, actions, attacks, diagonal count, HP, position, and full generator state. Compare uninterrupted execution with a restore before the second diagonal/attack and before the finishing blow.

## Fixed roster to admit in S2/S3

All PCs are level1, Medium human/humanoid, ordinary living creatures, Speed25, reach5, Common plus Goblin, initially fully healthy with1 Hero Point, no pre-cast effects, worn armor, no shields, no consumables, and no magic items. They start below their Bulk limits. They have complete selected class/ancestry/background choices; the engine still advertises a limited action menu, not complete PF2e or whole-class support.

### Shared ancestry/background

[Human, PC63](https://2e.aonprd.com/Ancestries.aspx?ID=64): 8 ancestry HP, two free ancestry boosts. [Skilled Human](https://2e.aonprd.com/Heritages.aspx?ID=261): one trained skill. [Natural Skill, PC64](https://2e.aonprd.com/Feats.aspx?ID=4479): two more trained skills. [Farmhand, PC86](https://2e.aonprd.com/Backgrounds.aspx?ID=422): one Con/Wis boost and one different free boost; trained Athletics/Farming Lore; [Assurance (Athletics), PC252](https://2e.aonprd.com/Feats.aspx?ID=5121). Assurance replaces a skill roll with10+proficiency, so all these PCs get13, without attribute/MAP/other modifiers; it is fortune and cannot combine with Hero reroll. Store it even while Athletics actions are outside the offered action boundary.

### M: melee fighter (S2)

Boosts: ancestry Str/Con; background Con/Str; class Str; final Str/Dex/Con/Wis. Final attributes **Str4 Dex1 Con3 Int0 Wis1 Cha0**.

[Fighter, PC136–138](https://2e.aonprd.com/Classes.aspx?ID=35): expert Perception/Fort/Reflex/simple/martial/unarmed, trained Will/all armor/class DC; class HP10+Con. Choose Acrobatics as the class's Athletics-or-Acrobatics training (background already gives Athletics); additional class skills Medicine, Survival, Intimidation; heritage Nature; Natural Skill Crafting and Society. All listed skills trained; other skills untrained.

| Statistic | Derivation |
|---|---|
| HP21 | ancestry8 + class10 + Con3 |
| AC18 | 10 + trained3 + breastplate4 + Dex1 |
| Fort8 / Ref6 / Will4 | Con3+expert5 / Dex1+expert5 / Wis1+trained3 |
| Perception6; fighter DC17 | Wis1+expert5; 10+Str4+trained3 |
| Longsword +9, 1d8+4 | Str4+expert5; choose slashing or piercing for each Strike |
| Basic unarmed +9, 1d4+4 B | Str4+expert5; agile, finesse, nonlethal, unarmed |

Own [breastplate, PC273](https://2e.aonprd.com/Armor.aspx?ID=47) (8gp, Bulk2) and [longsword, PC278](https://2e.aonprd.com/Weapons.aspx?ID=386) (1gp, Bulk1, one hand), plus6gp remaining starting money. Breastplate AC4/Dex cap1/check−2/Speed−5/Str3: meeting Str3 removes its check penalty and reduces Speed penalty by5 ([armor statistics](https://2e.aonprd.com/Rules.aspx?ID=2166)). No armor/weapon critical specialization is granted at level1.

Mandatory class abilities: Reactive Strike, Shield Block, one selected fighter feat **Vicious Swing**. Shield Block stays on the sheet with reason “requires a raised shield; this fixed loadout owns none.” Do not add shields to these encounters until their rules are supported.

[Vicious Swing, PC141](https://2e.aonprd.com/Feats.aspx?ID=4775): costs2, fighter/flourish; one melee Strike, extra one weapon damage die on a hit at level1, counts as TWO attacks for MAP. Apply prior MAP to this Strike, then increment count2 even on miss. First Vicious Swing +9 for2d8+4; following longsword Strike−10. Strike first then Swing uses−5 for Swing. Its critical damage doubles both ordinary dice and Str. Flourish once per round. It does not grant weapon critical specialization.

### R: shortbow fighter (S3)

Same ancestry/background/skill/feat/proficiency selections as M, except boosts: ancestry Dex/Con; background Con/Dex; class Dex; final Str/Dex/Con/Wis. **Str1 Dex4 Con3 Int0 Wis1 Cha0**. HP21; AC18=10+trained3+leather1+Dex4; Fort8/Ref9/Will4; Perception6; class DC17 (Dex key). Basic unarmed+9 (Dex),1d4+1 B. Longsword+6,1d8+1 S/P. Vicious Swing remains a real melee fallback with the carried longsword or supported unarmed attack; it never applies to the bow.

Own worn [leather armor](https://2e.aonprd.com/Armor.aspx?ID=41) (2gp, AC1/cap4, Bulk1, no Speed penalty; Str0 met removes check−1), [shortbow](https://2e.aonprd.com/Weapons.aspx?ID=437) (3gp, Bulk1), longsword1gp,20 [arrows](https://2e.aonprd.com/Weapons.aspx?ID=443) (2sp,2L), remaining8gp8sp. Start holding bow, other hand free; longsword worn. Shortbow **+9,1d6 piercing,60-foot increment,reload0,1+ hands,deadly d10**. It is neither propulsive nor volley. Critical:2×1d6 +1d10; no Str damage. After runes are ever added, ordinary striking does not increase deadly dice; greater striking does.

### C: Iomedaean warpriest (S3)

Boosts: ancestry Str/Wis; background Wis/Str; class Wis; final Str/Dex/Con/Wis. **Str3 Dex1 Con1 Int0 Wis4 Cha0**.

[Cleric, PC110–112](https://2e.aonprd.com/Classes.aspx?ID=33), [Warpriest first doctrine, PC112](https://2e.aonprd.com/Doctrines.aspx?ID=5): class HP8+Con; expert Fort/Will, trained Ref/Perception/simple weapons/unarmed/favored weapon/light-medium armor/spell attacks/spell DC/class DC. Skills: background Athletics/Farming Lore; class Religion, deity Intimidation, extras Medicine/Survival; heritage Nature; Natural Skill Crafting/Society. No focus spell or level1 cleric class-feat selection is granted by this doctrine. Shield Block retained but unusable without owned shield.

[Iomedae, PC36](https://2e.aonprd.com/Deities.aspx?ID=285): heal font, mandatory holy sanctification, trained Intimidation, favored longsword. Martial favored weapon means **no Deadly Simplicity**. Granted deity spells expand available preparation choices, not mandatory prepared slots; none selected. No divine boons/curses are automatically granted. Scenario premise: defending companions from hostile feral dogs; narrative anathema adjudication remains outside this encounter engine.

HP17=8+8+1; AC18=10+3+4+1; Fort6/Ref4/Will9; Perception7; spell attack+7/DC17 and class DC17; longsword+6,1d8+3 S/P; unarmed+6,1d4+3 B. Own breastplate8gp and longsword1gp, remaining6gp; Str3 meets armor requirement. Start sword held, other hand free.

**One casting model: prepared divine.** Five rank1 prepared cantrips: Divine Lance, Void Warp, Guidance, Stabilize, Read Aura. Two ordinary rank1 slots each prepare Heal; four additional font rank1 slots each prepare Heal. Preserve the ordinary/font source label and individual expended status even though all six currently hold the same spell. Cantrips are repeatable and never spend slots. This is a fixed day's preparation; no preparation editor, spontaneous repertoire, focus pool, or innate source. Read Aura has a one-minute casting time and therefore cannot be cast in encounters under [long casting times, PC300](https://2e.aonprd.com/Rules.aspx?ID=2233); expose that reason rather than silently deleting the fifth cantrip.

### Opponent: Guard Dog, MC102

[Complete stat block](https://2e.aonprd.com/Monsters.aspx?ID=2924): level−1 Small Animal; Perception6; low-light vision, imprecise scent30; Acrobatics5 Athletics4 Stealth5 Survival4; Str1 Dex2 Con2 Int−4 Wis1 Cha−1; AC15, Fort5/Ref7/Will4, HP8, Speed30; jaws+6,1d4+1 piercing, ordinary non-agile attack.

The jaws line prints NO agile or finesse trait (indeed no parenthesized weapon traits); MAP is explicitly +6/+1/−4. It is a melee unarmed Strike using Strength for attack and damage under [PC402](https://2e.aonprd.com/Rules.aspx?ID=2288) and [PC406](https://2e.aonprd.com/Rules.aspx?ID=2302). Keep the printed+6 rather than reconstructing NPC proficiency. [MC5](https://2e.aonprd.com/Rules.aspx?ID=3260) explains that creature attack modifiers include their usual abilities/gear. Enfeebled1 therefore yields+5/0/−5 and1d4+0; do not import the PC fist's agile/finesse/nonlethal traits into jaws.

**Pack Attack:** its Strikes add1d4 damage if the target is within reach of at least TWO of this dog's allies. The attacking dog does not count as its own ally. No requirement that those allies be dogs or that they flank. Extra damage doubles on a critical. Preserve the ability even when only two dogs are present. Test attacker+two allied dogs adjacent to target, then remove one qualifying ally. Low-light/scent are included but cannot alter targeting on the enforced bright, fully observed map. Rabies in the family sidebar is optional disease content, not a granted infectious bite.

S2 can use two M instances against two dogs; S3 uses M/R/C against three dogs. Additional three-dog positioning cases exercise Pack Attack. Ordinary hostile dogs die at0 from lethal damage, or become unconscious at0 from nonlethal attacks; they are not designated significant NPCs using PC dying. Save bodies/items as required by occupancy and targeting, rather than pretending a living unconscious dog vanished.

## S2 health, reactions, and equipment

### Health procedures and tests

- [Knockout, PC410](https://2e.aonprd.com/Rules.aspx?ID=2324): floor HP0. PCs move immediately before the TURN in which knocked out; a reaction's attacker does not replace that turn anchor. Lethal knockout gives dying1; attacker critical/own critical failure gives dying2; add current wounded on GAINING dying. Nonlethal gives unconscious0 without dying. Example wounded1 + critical KO => dying3.
- [Dying, PC411](https://2e.aonprd.com/Rules.aspx?ID=2325): dying4 dies. [Further damage](https://2e.aonprd.com/Rules.aspx?ID=2327) increases existing dying by1, or2 for attacker critical/own critical failure; wounded is not added again. [Massive damage, PC412](https://2e.aonprd.com/Rules.aspx?ID=2332) at least twice MAX HP in one blow kills immediately. Hero recovery does not prevent that independent instant-death rule.
- [Recovery, PC411](https://2e.aonprd.com/Rules.aspx?ID=2326): start-turn flat d20 vs10+dying, with ordinary degrees/natural adjustment; CS−2/S−1/F+1/CF+2. Dying1, die20 stabilizes; die11 stabilizes; die10 goes2; die1 goes3. Dying3,die1 kills unless heroic recovery prevents the increase.
- [Losing dying](https://2e.aonprd.com/Rules.aspx?ID=2328): reaching dying0 removes it and adds/increases wounded1; HP remains0/unconscious. Healing to≥1 removes dying/unconscious, also adds wounded once, leaves prone and dropped items. Stabilize follows this ordinary wounded rule. [Death](https://2e.aonprd.com/Rules.aspx?ID=2329) makes normal creature-targeted healing invalid.
- [Unconscious, PC446](https://2e.aonprd.com/Conditions.aspx?ID=95): cannot act; −4 status AC/Perception/Reflex, blinded/off-guard; gain prone and drop every held/wielded item. Worn armor stays. Unconscious M AC12=18−4−2; prone/off-guard do not impose two copies of−2. Ending unconscious removes its own dependent penalties, not prone. At0 stable, waking naturally requires at least10minutes; it is not next-round healing.
- [Prone, PC445](https://2e.aonprd.com/Conditions.aspx?ID=88): off-guard; −2 circumstance attacks; only Crawl/Stand move actions. Stand costs1, ends prone; moving-trigger reaction happens after standing. No Stand in a space shared by another creature. Conscious prone PC can still attack/cast and use reactions. Crawl costs1 and moves5 feet ([basic actions](https://2e.aonprd.com/Rules.aspx?ID=2343)).

### Hero Points: real saved choices

[PC413](https://2e.aonprd.com/Rules.aspx?ID=2333): start session1, cap3. Spending is not an action and is allowed while unable to act. One point rerolls a CHECK, must retain second result; fortune prohibits a second Hero reroll or combining with Assurance on that check. Damage is not a check. Supported check eligibility includes initiative, attacks, saves, and recovery.

Offer Keep / spend1 only when a PC owns a point and this check has not used fortune. Show original natural/total/degree before asking; apply no resulting damage, dying, or other effects until the choice closes. A saved prompt records original result, check context, paid action/slot/ammo cost, and generator state. Restore must neither repeat the original roll nor refund costs. Do not create a generic confirm-roll prompt for actors with no eligible choice.

[Heroic recovery, PC411](https://2e.aonprd.com/Rules.aspx?ID=2325): at start of own turn or when dying would increase, spend ALL remaining points (minimum1) to stabilize at0; no new wounded/increment, existing wounded retained; unconscious/prone stay. Offer before committing an increase, including otherwise fatal increases. Reroll and heroic recovery remain different choices: spending the last point on a failed reroll leaves no point for recovery. Recovery without healing is not permission to act. Test save at both prompt kinds, decline, worse second roll, last-point spending, and wounded preservation.

### Reactive Strike and basic positioning

[Reactive Strike, PC138](https://2e.aonprd.com/Actions.aspx?ID=2256): eligible creature within melee reach uses manipulate/move, makes ranged attack, or leaves a reachable square during movement. One reaction for melee Strike; ignores MAP and does not increment it, even on own turn. Critical disrupts only a manipulate trigger. A critical against movement alone does not halt movement unless its consequences make the mover unable to continue.

[Movement reactions, PC421](https://2e.aonprd.com/Rules.aspx?ID=2355): offer BEFORE leaving each reachable square; at most one reaction per move action per reacting creature. If no square is left (Stand), offer at action END. Entering the first reachable square alone does not trigger. Step exempt. Declining retains the reaction; save accepted/declined windows and paid costs. [Disruption, PC415](https://2e.aonprd.com/Rules.aspx?ID=2342): spend all committed activity actions and costs, effects do not occur. Alert-fixture GM policy grants the initial reaction before first turn; refresh1 as LAST start-turn step. Do not refresh reactions each round globally.

[Flanking, PC425](https://2e.aonprd.com/Rules.aspx?ID=2375): two able allies with valid melee/unarmed attacks and target in reach; line between centers crosses opposite sides/corners of target square. Gives off-guard only against their melee attacks. Unconscious ally cannot flank. Prone conscious ally can if otherwise eligible. [Cover, PC424](https://2e.aonprd.com/Rules.aspx?ID=2372): intervening creature on center-to-center line gives lesser cover +1 circumstance AC; never +Reflex. Bright open map has no wall/terrain cover or blocked line of effect. [Line of effect](https://2e.aonprd.com/Rules.aspx?ID=2382) is not blocked by an intervening creature. Document a consistent GM choice for exact boundary-touching lines.

[Occupancy, PC422](https://2e.aonprd.com/Rules.aspx?ID=2360): pass willing allies; unwilling living creatures require unsupported Tumble Through. End move on willing occupied square only if immediately using another move to leave; cannot end turn there. Can share with willing/unconscious/dead prone creature your size or smaller; such prone creature cannot Stand until space clear. Preserve this distinction in legal paths. Tiny/larger footprints remain unavailable.

[Interact, PC268](https://2e.aonprd.com/Rules.aspx?ID=2151) costs1/manipulate to draw, stow, swap one held item for one worn item, pick up a ground item, or add a hand. [Release, PC417](https://2e.aonprd.com/Actions.aspx?ID=2300) is free/manipulate to drop/remove a hand, but explicitly does NOT trigger reactions from manipulate. Offer these selected modes; handle interruption before transfer with unchanged item position as documented GM default. A recovered PC must pick up its dropped weapon. [Basic unarmed, PC275](https://2e.aonprd.com/Rules.aspx?ID=2191) and [fist traits, PC277](https://2e.aonprd.com/Weapons.aspx?ID=356): allow a fist with its hand free or an ordinary kick using same numbers; finesse may use Dex for attack, still Str damage; agile; nonlethal. Choosing lethal unarmed or nonlethal ordinary weapon takes−2 circumstance attack.

## S3 spell and ranged procedures

All listed spell ranks are1. No higher-rank behavior admitted. Cast costs actions and consumes chosen prepared slot before reaction continuation; disrupted prepared spells lose slot/actions. [Casting, PC299–300](https://2e.aonprd.com/Rules.aspx?ID=2233). No selected spell has a cost or locus. These spells do not impose an invented free-hand requirement merely for manipulate; the roster also starts C with a free hand.

| Spell | Complete applicable rank1 behavior |
|---|---|
| [Divine Lance, PC325](https://2e.aonprd.com/Spells.aspx?ID=1498) | 2 actions; attack/cantrip/concentrate/manipulate/sanctified/spirit;60 feet,1 creature, ranged spell attack+7 vsAC;2d4 spirit on hit,double critical. Counts/applies MAP. Iomedaean caster makes it holy via sanctified. No alignment restriction on targets. |
| [Void Warp, PC366](https://2e.aonprd.com/Spells.aspx?ID=1745) | 2 actions; cantrip/concentrate/manipulate/void;30 feet,1 living creature;2d4 void, basic Fort vs17. CF also enfeebled1 until START of caster's next turn. No attack trait/MAP increment. |
| [Guidance, PC334](https://2e.aonprd.com/Spells.aspx?ID=1549) | 1 action; cantrip/concentrate (NO manipulate);30 feet,1 creature;until START of caster's next turn. Target chooses BEFORE an eligible attack/Perception/save/skill roll to consume+1 STATUS; consuming ends spell. On use OR unused expiry, target becomes temporarily immune to Guidance1hour. Recovery is a flat check, not one of these eligible kinds. Persist immunity and choice, including when target is another PC. |
| [Stabilize, PC359](https://2e.aonprd.com/Spells.aspx?ID=1689) | 2 actions; cantrip/concentrate/healing/manipulate/vitality;30 feet,1 dying creature. Remove dying; remain unconscious0; normal wounded increment. |
| [Read Aura, PC352](https://2e.aonprd.com/Spells.aspx?ID=1646) | Prepared fifth cantrip;1-minute exploration casting, unavailable during encounter by casting rules. Not deleted from sheet. |
| [Heal, PC335](https://2e.aonprd.com/Spells.aspx?ID=1554) | Healing/manipulate/vitality. 1 action: touch,1 willing living creature heals1d8, or1 undead takes1d8 vitality basicFort. 2 actions adds concentrate;range30;living healing1d8+8;undead damage remains1d8. 3 actions adds concentrate;30-foot emanation,all living/undead therein;living heal1d8,undead basicFort1d8. All modes consume ONE chosen prepared slot. |

Select full Heal modes: its modest 30-foot emanation is the only area geometry required. [Area, PC428](https://2e.aonprd.com/Rules.aspx?ID=2384) measures from caster space in ordinary grid distance, independently of movement parity; caster chooses whether to include self, other qualifying creatures are affected (including enemies). Lesser creature cover does not apply to area saves. Current roster has living creatures only: reject undead definitions until void-healing/undead dependencies admitted; do not replace Heal's undead clause with ordinary healing.

For one-square caster and targets, distance in feet is5×(max(dx,dy)+floor(min(dx,dy)/2)); include other targets at≤30. Offsets(4,4),(5,3),(6,1) are30 and included; (6,2) is35 and excluded. The three-action mode heals all living creatures in the area regardless of team/willingness; it does not inherit the two-action+8. The one-/two-action modes require a willing living target. [Targets, PC426](https://2e.aonprd.com/Rules.aspx?ID=2380) explicitly lets a PC's controller decide willingness even while unconscious, so unconscious PCs are not invalid Heal targets. Caster self-inclusion for an emanation is a choice, not a mandatory global policy.

[Basic saves, PC404](https://2e.aonprd.com/Rules.aspx?ID=2297): CS0/S half/F full/CF double. Damage7 =>0/3/7/14. [Enfeebled, PC443](https://2e.aonprd.com/Conditions.aspx?ID=71): status penalty value to Str-based rolls/DCs and damage. Dog jaws is Str-based: enfeebled1 changes+6 to+5 and1d4+1 to1d4; it does not reduce bow damage or Dex-based unarmed attack roll (but does reduce its Str damage). No stacking same-type status penalties. Expiry is caster's start, not target's. [Durations, PC302](https://2e.aonprd.com/Rules.aspx?ID=2242) persist if caster is incapacitated/dead, using its initiative anchor.

[Reload, PC276](https://2e.aonprd.com/Rules.aspx?ID=2196): shortbow reload0 means drawing arrow and shooting are part of the Strike, not a separate action. [Hands](https://2e.aonprd.com/Rules.aspx?ID=2198):1+ requires holding bow in one hand and having second free to shoot; no added grip action per shot. [Ammunition](https://2e.aonprd.com/Rules.aspx?ID=2194): each fired arrow is destroyed even on miss. Hero reroll repeats check, not firing/ammo consumption. Bow Strike triggers Reactive Strike through ranged attack; critical reaction does not disrupt merely because of that trigger. Decline/unavailable reaction consumes nothing.

[Range penalty, PC403](https://2e.aonprd.com/Rules.aspx?ID=2290): shortbow60 feet no penalty;65–120 feet−2;max360 feet,>360 invalid. Spell range is a hard maximum, not weapon increments. Shortbow critical die4 plus deadly7 =>15 damage; a failed shot still removes one arrow. Ranged attack while adjacent has no invented disadvantage/−2; the danger is a reaction if the enemy owns one. Weapon/rune critical specialization is absent on these level1 sheets.

## Admission and verification boundary

Required available menu through S3: Inspect; Stride/Step/Strike; Vicious Swing; Reactive Strike decision; End Turn; Hero reroll/recovery; Interact selected held-item modes; Release; Stand/Crawl; selected spells/modes; Save/Load/Restart/Quit. Prone Take Cover is a small useful addition before promising all of prone's tactical choices: [PC418](https://2e.aonprd.com/Actions.aspx?ID=2307),1 action,+4 circumstance AC vs ranged until move/attack/unconscious/free dismissal. It does not remove off-guard.

Explicit prototype omissions: other basic/specialty actions and skill actions (including Aid, Ready/Delay, Seek/Hide/Sneak, maneuvers, Demoralize, Treat Wounds/First Aid), exploration/downtime, preparation changes, higher levels. Trained skill and Assurance facts are preserved and inspectable; no unsupported action returns a fake success. No S2/S3 claim that these optional actions became impossible in PF2e. The enforced map is bright/flat/open, all actors observed, Small/Medium grounded, with no object hazards or external conditions. Adding darkness, terrain, gear, or a creature is a new admission, not an engine fallback.

Minimum evidence before admission: source-backed ordinary boundary tests; full continuous S2 and S3 encounters; one alternate legal sequence; reaction accept and decline; KO/drop/heal/Stand/pickup continuation; Pack Attack with three dogs; spell attack and all basic-save degrees; all Heal modes and slot exhaustion; Guidance decline/use/expiry/immunity; bow ammo and deadly; invalid inputs unchanged; save/restore at reaction, original Hero reroll, heroic recovery, and Guidance selection prompts with identical continuation. Do not count manually patched-state runs as complete encounters.
