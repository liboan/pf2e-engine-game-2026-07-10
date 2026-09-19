# PC1/PC2 divine classes: level 1, then level 2

Source/design handoff, checked 2026-09-15. Owner: `rules_divine_classes`; thread `01a0a70d-53e9-7230-aafb-373de48b470e`. This document specifies behavior and proposed evidence; it does not claim runtime implementation or executed encounter coverage.

## Scope and source precedence

The approved divine representatives are Iomedae Warpriest, Justice Champion of Iomedae with Lay on Hands and Desperate Prayer, and Life Oracle. The wider Champion causes, Cleric doctrines, and Oracle mysteries remain source reference inventory, not required delivery. Fixed grants on selected representatives are mandatory even when a granted focus spell is uncommon. The optional menu stays deliberately small.

Use current individual AoN entries plus [Paizo FAQ/errata](https://paizo.com/pathfinder/faq). Search-index metadata on AoN source overview pages can lag the individual entries. The checked 2026 corrections include Oracle repertoire counts, Bones targeting, Flames resistance suppression, and Nudge the Scales targeting. Current Weapon Trance has a one-minute duration; do not copy the older sustained version. Current Grandeur gives an explicit end-of-next-turn expiry.

**Shared damage correction:** resistance covering a category (all damage, spells, physical) applies once per effect, to a chosen eligible damage type. It is not subtracted from every component. Distinct weaknesses can apply once each. See [Paizo's Spring 2026 explanation](https://paizo.com/blog/spring-errata-2026). This affects every protective Champion reaction and multi-type Tempest damage.

## Minimal local declarations

Design recommendation: persist a deity ID, source-backed allowed sanctifications, selected sanctification, favored weapon, divine skill, permitted font, and chosen domain. Validate these finite choices at character creation. Keep edicts/anathema as visible source-backed text and an explicit local GM adjudication record, not a behavior classifier. A GM-declared loss of divine powers must name the affected feature IDs and reason. Restoration requires an explicit completed-atonement adjudication. The class rules give the GM discretion about which powers are lost; do not automatically strip every ability after one inferred offense.

Small deity menu sufficient for the family:

| Deity | Sanctification | Font | Skill / favored weapon | Selected Cleric domain option |
|---|---|---|---|---|
| [Sarenrae](https://2e.aonprd.com/Deities.aspx?ID=292) | may choose holy; otherwise neither | heal | Medicine / scimitar | healing |
| [Iomedae](https://2e.aonprd.com/Deities.aspx?ID=285) | must choose holy | heal | Intimidation / longsword | zeal |
| [Urgathoa](https://2e.aonprd.com/Deities.aspx?ID=295) | must choose unholy | harm | Intimidation / scythe | do not offer Cloistered with this deity until one of her actual domain spells is supported |

This last restriction is an optional deity-menu restriction, not permission to omit a doctrine. Both doctrines must have functioning supported deity/domain choices. Champion deity choice does not grant the Cleric spell list. Cleric deity spells expand its preparation list, not its number of daily slots. If these three deities are offered to Clerics, their level-1 granted spell options are respectively breathe fire, sure strike, and goblin pox; implement the option or visibly omit that deity from the Cleric menu.

## Level 1: Champion

[Champion chassis](https://2e.aonprd.com/Classes.aspx?ID=58): Strength or Dexterity key boost; HP 10+Con each level; trained Perception, Reflex, simple/martial/unarmed attacks, all armor/unarmored, class DC and spell attacks/DC; expert Fortitude/Will. Religion, deity skill, and 2+Int additional trained skills. Spell attribute Charisma. Gain Shield Block, one class feat, one cause, one devotion spell. Deific Weapon increases a favored simple weapon's die one step, or a favored d4 unarmed attack to d6; advanced favored weapons use martial proficiency. Sanctification adds holy/unholy to Strikes. Aura is a 15-foot divine emanation; one concentrate action suppresses/resumes it; unconsciousness ends it. Devotion costs one Focus Point; initial pool 1; ten-minute Refocus restores 1; pool maximum equals focus spells known, capped 3. At levels 1 and 2 focus spells are rank 1. Choose shields of the spirit, or lay on hands for a heal-font deity, or touch of the void for a harm-font deity.

The selected level-1 Justice representative takes [Desperate Prayer](https://2e.aonprd.com/Feats.aspx?ID=5884): once per day, a free action triggered at turn start when focus is 0, granting one devotion-only point that expires at turn end.

### Champion causes and reactions (selected Justice row; other causes are reference inventory)

Every row costs **one reaction**. The ally is another creature, never the Champion themself. Aura must be active. These are divine Champion abilities, not spells; they do not spend focus. Do not grant level-9 relentless or level-11 exalted riders.

| Cause / source | Restriction | Trigger | Exact level 1–2 result |
|---|---|---|---|
| [Desecration](https://2e.aonprd.com/Causes.aspx?ID=8): Selfish Shield | unholy | enemy inside aura damages Champion | Resist triggering damage by `2+floor(level/2)` (2 at L1, 3 at L2). Champion's Strikes against that enemy gain 1 spirit damage until end of Champion's next turn. |
| [Grandeur](https://2e.aonprd.com/Causes.aspx?ID=9): Flash of Grandeur | holy | enemy damages ally; enemy and ally inside aura | Ally resistance `2+level` against this damage. Enemy affected by revealing light until end of Champion's next turn. |
| [Iniquity](https://2e.aonprd.com/Causes.aspx?ID=10): Destructive Vengeance | unholy | enemy inside aura damages Champion | Increase damage Champion takes by 1d6; deal 1d6 spirit to enemy. Champion's Strikes against that enemy gain 2 spirit until end of Champion's next turn. No saving throw. Do not recast the added incoming damage as spirit damage. |
| [Justice](https://2e.aonprd.com/Causes.aspx?ID=11): Retributive Strike | none | enemy damages ally; both inside aura | Ally resistance `2+level`. If enemy is within melee reach, Champion makes a melee Strike. Protection still works when enemy is out of reach. |
| [Liberation](https://2e.aonprd.com/Causes.aspx?ID=12): Liberating Step | none | enemy damages, grabs, or restrains ally; both inside aura | Resist `2+level` only on damage trigger. Ally may retry a save against one grabbing/restraining/immobilizing/paralyzing effect allowing saves, or Escape one effect as a free action. Then may Step as a free action if able to move, even if no escape was needed. |
| [Obedience](https://2e.aonprd.com/Causes.aspx?ID=13): Iron Command | none | enemy inside aura damages Champion | Emotion/mental. Enemy chooses free-action Drop Prone or take 1d6 mental damage. Either choice grants Champion +1 spirit damage on Strikes against it until end of Champion's next turn. |
| [Redemption](https://2e.aonprd.com/Causes.aspx?ID=14): Glimpse of Redemption | holy | enemy damages ally; both inside aura | Enemy chooses repent (ally takes none of triggering damage) or refuse (ally resistance `2+level`, then enemy enfeebled 2 until end of enemy's next turn). Mindless/unable-to-repent enemies use refuse. Enfeebled begins after triggering damage; never retroactively reduce that damage. |

[Revealing light](https://2e.aonprd.com/Spells.aspx?ID=1653) means dazzled, invisibility becomes concealed, and other concealment is removed. Grandeur supplies a fixed duration and directly says affected; it does not instruct a spell cast or saving throw. Do not add a rank-2 slot cost, Reflex roll, spell action cost, or the spell's longer save-dependent duration.

### Reaction transaction and actor choices

Implementation recommendation: freeze the triggering event before applying damage. Validate aura membership, reaction availability, and trigger; offer accept/decline; collect any enemy choice; apply preventive resistance/cancellation; apply triggering damage; then apply explicitly post-damage riders and subordinate actions. Preserve exact event and actor IDs through save/load. Never charge a reaction while merely presenting a menu.

Enemy choices in Redemption and Obedience belong to the enemy controller. Liberation's retry/Escape and Step belong to the ally controller. Persist pending prompts if the terminal allows interruption. Shield Block and Selfish Shield compete for the same ordinary reaction; do not silently spend both. For several eligible responders, use an explicit local resolution order, revalidating the event after each response; do not invent a universal initiative priority that the source does not state.

### Devotion options

| Spell | Actions / traits | Rank-1 effect |
|---|---|---|
| [Lay on hands](https://2e.aonprd.com/Spells.aspx?ID=2047) | 1; manipulate, healing, vitality; touch | Willing living target heals 6; if other than caster, +2 status AC for 1 round. Undead target: 1d6 vitality, basic Fortitude; failed save also −2 status AC for 1 round. |
| [Touch of the void](https://2e.aonprd.com/Spells.aspx?ID=2048) | 1; manipulate, void; touch | Willing undead heals 6; if caster targets self, +2 status damage for 1 round. Living target: 1d6 void, basic Fortitude; failed save also −2 status AC for 1 round. |
| [Shields of the spirit](https://2e.aonprd.com/Spells.aspx?ID=2049) | 1; concentrate, sanctified, spirit; requires wielded shield | Raise Shield as part of cast. Until start of next turn or shield ceases being raised, allies currently in aura gain +1 status AC. An enemy making an attack against such an ally takes 1d4 spirit even on a miss. Caster is not own ally. Membership updates on movement. |

Devotion tests: full resource rejection before mutation; Lay on Hands self-heal without AC bonus; Touch of Void living damage versus undead healing; status bonus non-stacking; aura entry/exit; shield dropped/broken and unconsciousness terminate dependent benefits; Shields retaliates on miss, but not attacks against caster.

## Level 1: Cleric

[Cleric chassis](https://2e.aonprd.com/Classes.aspx?ID=33): Wisdom key/casting attribute, HP 8+Con, trained Perception/Fortitude/Reflex/simple weapons/deity favored weapon/unarmed/unarmored/class DC/spells, expert Will. Religion, divine skill, 2+Int extra skills. Prepare five cantrips and two rank-1 spells; four additional rank-1 font slots hold only the chosen heal or harm. A deity offering both requires a fixed font choice. No normal class feat at level 1 beyond doctrine grants.

[Doctrines](https://2e.aonprd.com/Doctrines.aspx): Cloistered grants Domain Initiate. Warpriest instead gains light/medium armor training, expert Fortitude, Shield Block, and Deadly Simplicity if favored weapon is simple/unarmed. Warpriest does **not** gain general martial training until level 3. [Deadly Simplicity](https://2e.aonprd.com/Feats.aspx?ID=4642) increases favored simple weapon die one step; favored unarmed die below d6 becomes d6.

[Domain Initiate](https://2e.aonprd.com/Feats.aspx?ID=4644) chooses a listed deity domain, granting its initial focus spell and one focus capacity (maximum 3). Optional repeat selections require different domains. Ten-minute Refocus restores one point. Offer at least these functioning pairs:

- Sarenrae/healing: [Healer's blessing](https://2e.aonprd.com/Spells.aspx?ID=1808), one concentrate action, 30 feet, willing living creature, one minute. When a healing vitality spell restores HP, add 2, only once per individual spell. Does not itself heal; does not enhance Treat Wounds or Nudge the Scales.
- Iomedae/zeal: [Weapon surge](https://2e.aonprd.com/Spells.aspx?ID=1852), one manipulate action, own wielded weapon, until start next turn. Next Strike with that weapon gets +1 status attack and +1d6 spirit, and sanctified. Ends after that Strike, hit or miss, or when weapon leaves possession.

### Heal and harm, rank 1

[Heal](https://2e.aonprd.com/Spells.aspx?ID=1554) restores willing living targets by 1d8 or deals 1d8 vitality to undead with basic Fortitude. [Harm](https://2e.aonprd.com/Spells.aspx?ID=1552) reverses living/undead healing roles, dealing void. One action: manipulate, touch. Two: add concentrate, 30-foot range, **+8 only when healing**. Three: add concentrate, 30-foot emanation, all living/undead targets, no +8. Preserve caster exclusion option under emanation rules. Do not auto-exclude allies or undead allies; a selective-target feat is not a base class feature.

Tests: track font separately from ordinary prepared heal/harm; casting expends the chosen source only. Two-action offense does not add 8. Three-action mixed groups resolve each target's healing/damage eligibility and save separately. At L1 cloistered and warpriest both receive four font slots regardless of Charisma. Warpriest medium armor and Fortitude differ from Cloistered while spell rank/DC proficiency remains equal.

## Level 1: Oracle

[Oracle chassis](https://2e.aonprd.com/Classes.aspx?ID=61): Charisma key/casting attribute; HP 8+Con. Trained Perception/Fortitude/Reflex/simple/unarmed/light armor/unarmored/class DC/spells; expert Will. Religion, mystery skill(s), 3+Int other trained skills. Spontaneous divine casting: three chosen rank-1 spells and five chosen cantrips, plus mystery grants; three daily rank-1 slots. Initial focus spell/pool 1. Cursebound maximum 2. Resolution increases cursebound afterward; at maximum, reject further cursebound use. Focus casting alone does not increase it. Refocus ten minutes restores one focus and reduces cursebound one. Curse drawbacks cannot be removed or bypassed otherwise. No legacy mystery benefits, random Ancestors skill restrictions, or cursebound revelation spells.

### Mystery fixed grants and curse effects

Granted repertoire spells do not add spell slots. Each selected row grants its named initial focus spell and cursebound feat; the remaining rows are source reference inventory. Each curse's effects below apply only while cursebound; CB2 retains CB1.

| Mystery / source | Skill | Added cantrip / rank-1 spell | Initial focus / feat | CB1 → CB2 |
|---|---|---|---|---|
| [Ancestors](https://2e.aonprd.com/Mysteries.aspx?ID=12) | Society | guidance / ill omen | ancestral touch / Whispers of Weakness | clumsy equal to CB |
| [Battle](https://2e.aonprd.com/Mysteries.aspx?ID=13) | Athletics | shield / sure strike | weapon trance / Oracular Warning | weakness 2 to spell damage; suppress spell immunities/resistances → also −1 status saves against spells |
| [Bones](https://2e.aonprd.com/Mysteries.aspx?ID=14) | Medicine | void warp / grim tendrils | soul siphon / Nudge the Scales | weakness 2 vitality and void; suppress relevant immunity/resistance; targetable/damaged by both even normally ineligible → also −1 status Fortitude |
| [Cosmos](https://2e.aonprd.com/Mysteries.aspx?ID=15) | Nature | light / dizzying colors | spray of stars / Oracular Warning | enfeebled CB; status penalty CB to saves/DCs against forced movement |
| [Flames](https://2e.aonprd.com/Mysteries.aspx?ID=16) | Acrobatics | ignition / breathe fire | incendiary aura / Foretell Harm | persistent fire CB; fire immunity/resistance suppressed; torch light. Suppressed during Refocus or unconsciousness, resumes if Refocus interrupted or consciousness returns. Underwater does not remove it. |
| [Life](https://2e.aonprd.com/Mysteries.aspx?ID=17) | Medicine | vitality lash / soothe | life link / Nudge the Scales | magical HP recovery has status penalty `max(1,level)*CB` |
| [Lore](https://2e.aonprd.com/Mysteries.aspx?ID=18) | Occultism plus one Lore | read aura / mindlink | brain drain / Whispers of Weakness | status penalty CB to Perception checks and Will saves |
| [Tempest](https://2e.aonprd.com/Mysteries.aspx?ID=19) | Nature | electric arc / thunderstrike | tempest touch / Foretell Harm | electricity weakness 2; electricity effects treat Oracle as wearing metal; suppress relevant immunity/resistance → also −2 circumstance ranged attacks |

### Cursebound handler inventory (selected Life path)

- [Whispers of Weakness](https://2e.aonprd.com/Feats.aspx?ID=6057): one action; divine. One creature within 60 feet. Report its weaknesses and lowest save modifier; no Recall Knowledge roll. +2 status to next attack roll or skill check belonging to an attack against that creature before end of current turn. Target then immune for one day.
- [Oracular Warning](https://2e.aonprd.com/Feats.aspx?ID=6056): free action before Oracle rolls initiative; auditory/emotion/mental/divine. Allies within 20 feet get +2 status initiative and `floor(level/2)` temporary HP for one minute. Excludes self; ally must hear. At L1 this grants **zero** temporary HP, L2 grants 1. The stronger CB2 bonus cannot be reached at these levels because using another cursebound ability while already at cap is forbidden.
- [Nudge the Scales](https://2e.aonprd.com/Feats.aspx?ID=6055): one action, divine/healing/spirit; any creature within 30 feet heals `2+2*level` (4/6). Daily preparations choose life (vitality healing eligibility) or death (void healing and eligibility for effects healing undead). This does not make the character undead or grant its immunities. No focus/slot charge.
- [Foretell Harm](https://2e.aonprd.com/Feats.aspx?ID=6053): free action once per round, immediately after casting a non-cantrip spell that dealt damage. At each affected target's next turn start, deal twice spell rank with a matching damage type, then target immune 24 hours. Level 1–2 amount is 2. Focus spells qualify; cantrips do not. Paizo organized-play clarification linked by AoN permits all damaged area targets. For a spell with several damage types, require one matching type choice and preserve it; do not invent extra damage for each component.

These source-listed abilities use the pre-increment curse state for their effect. The selected Life Oracle exercises Nudge the Scales at CB0/CB1; the remaining handlers are reference inventory. In particular Life Oracle self-Nudge heals at CB0 without a curse penalty, then becomes CB1; a second self-Nudge at L1 heals 3 before reaching CB2. A third attempt is rejected. Temporary immunity belongs to the target and ability, not merely to the caster's record.

### Oracle revelation inventory (selected Life row)

Each source-listed entry costs **one Focus Point**, uses Charisma spell DC, is rank 1 at character levels 1 and 2, and has no cursebound trait. The table is reference inventory; delivery exercises the selected Life Oracle row and its fixed grants. `M` means manipulate and `C` concentrate. Normal trait immunities apply.

| Spell / source | Actions, range, traits | Rank-1 resolution |
|---|---|---|
| [Ancestral touch](https://2e.aonprd.com/Spells.aspx?ID=2066) | 1, touch living creature; M, emotion/fear/mental | 2d4 mental vs Will. Critical success none; success half; failure full+frightened1; critical failure double+frightened2. |
| [Weapon trance](https://2e.aonprd.com/Spells.aspx?ID=2069) | 1, self; C | Martial weapon proficiency equals simple weapon proficiency for one minute. No sustain or hit maintenance. |
| [Soul siphon](https://2e.aonprd.com/Spells.aspx?ID=2072) | 1, 30 feet living creature; M, void | 1d4 void vs Fortitude: critical success none; success half; failure full+drained1; critical failure double+drained2. Oracle gains temporary HP equal to HP actually lost, including drained HP loss. |
| [Spray of stars](https://2e.aonprd.com/Spells.aspx?ID=2075) | 2, 15-foot cone; C/M, fire/light | 2d4 fire vs Reflex. Critical success none; success half+dazzled1 round; failure full+dazzled3 rounds; critical failure double+dazzled1 minute. |
| [Incendiary aura](https://2e.aonprd.com/Spells.aspx?ID=2078) | 2, 10-foot emanation, 1 minute; C/M, fire/aura | Whenever a creature in aura takes fire damage, apply 2d4 persistent fire. Not enemy-only. Same-type persistent damage follows replacement rules, not additive stacking. |
| [Life link](https://2e.aonprd.com/Spells.aspx?ID=2081) | 1, 30 feet, another creature, 1 minute; M, healing/vitality | Initially heal 1d4. First damage to target each round reduces damage by up to3; Oracle loses that same amount, bypassing all mitigation. Dismissible; ends immediately when Oracle unconscious. |
| [Brain drain](https://2e.aonprd.com/Spells.aspx?ID=2084) | 2, 30 feet creature; C/M, mental | 1d8 mental/basic Will. Failed save permits one Recall Knowledge check using a chosen knowledge skill's modifier from the target. Requires actual target skill data or explicit GM-provided modifier, not caster's modifier. |
| [Tempest touch](https://2e.aonprd.com/Spells.aspx?ID=2087) | 1, touch creature; M, cold/water | 1d4 bludgeoning+1d4 cold vs Fortitude. Critical success none; success half and −5-foot circumstance Speeds; failure full and −10 feet; critical failure double and −10 feet. Speed penalty ends at end of Oracle's next turn. |

Soul Siphon source specifies **no duration for its temporary HP**. The general temporary-HP rule says most have a limited duration, without supplying a universal timeout. Do not invent a one-minute expiry. Accepted local interpretation: store no expiry until depleted/replaced; retain this interpretation for periodic rules review. No contradictory source was found and this is not a blocking user decision. Drained itself follows normal recovery and reduces max/current HP based on target level; never count pre-existing unchanged drained again as new loss.

### Fixed granted spell dependencies

The selected representatives' cantrips and rank-1 grants must be genuinely usable, including noncombat local operations. Names in a selected repertoire without handlers fail the representative acceptance gate. The remaining rows are source reference inventory. In particular:

- [Ill omen](https://2e.aonprd.com/Spells.aspx?ID=1566): two actions C/M, curse/misfortune, 30 feet, Will; success no effect; failure next attack/skill roll twice worse within one round; critical failure every attack/skill roll during that round. No save penalty.
- [Sure strike](https://2e.aonprd.com/Spells.aspx?ID=1709): one C action; next attack before turn end rolls twice better, ignores circumstance attack penalties and concealment/hidden flat checks; ten-minute temporary immunity. It cannot bypass Oracle curse drawbacks.
- [Grim tendrils](https://2e.aonprd.com/Spells.aspx?ID=1548): two C/M actions, void, 30-foot line, living targets, Fortitude. Critical success none; success half of 2d4 void/no bleed; failure 2d4 void+1 persistent bleed; critical failure double both components.
- [Dizzying colors](https://2e.aonprd.com/Spells.aspx?ID=1500): two C/M actions, illusion/incapacitation/visual, 15-foot cone, Will. Critical success none; success dazzled1 round; failure stunned1, blinded1 round, dazzled1 minute; critical failure stunned **for1 round** and blinded1 minute. Apply incapacitation to creatures above twice spell rank, so level3+ at rank1. Stunned1 and stunned-duration are distinct states.
- [Soothe](https://2e.aonprd.com/Spells.aspx?ID=1678): two C/M actions, emotion/healing/mental, willing creature within30 feet; restores1d10+4 immediately and +2 status saves against mental effects for1 minute. It has no vitality trait.
- [Mindlink](https://2e.aonprd.com/Spells.aspx?ID=1603): two C/M actions, mental, touch willing creature. Instantly communicates information equivalent to10 minutes of ordinary communication. Accept explicit local message/information IDs and record receipt; this is not a sustained telepathic channel or mind-reading.
- [Thunderstrike](https://2e.aonprd.com/Spells.aspx?ID=1721): two C/M actions, electricity/sonic, one creature within120 feet, basic Reflex, 1d12 electricity+1d4 sonic. Metal armor/body imposes −1 circumstance to save and, if damaged, clumsy1 for1 round. Tempest curse's treated-as-metal rule enables this rider.
- [Breathe fire](https://2e.aonprd.com/Spells.aspx?ID=1457): two C/M actions, fire, 15-foot cone, 2d6 fire/basic Reflex to every creature in area.

Fixed cantrips (rank1 at both character levels):

| Cantrip / source | Cost / range | Required behavior |
|---|---|---|
| [Guidance](https://2e.aonprd.com/Spells.aspx?ID=1549) | 1 C action / creature30 feet | Target elects +1 status before one attack, Perception, save, or skill roll; expires start caster next turn or on use; one-hour immunity afterward either way. |
| [Shield](https://2e.aonprd.com/Spells.aspx?ID=1671) | 1 C action / self | Force shield counts as Raise Shield, +1 circumstance AC until start next turn, no hand. Grants Shield Block at hardness5, including against magical nonphysical damage. Blocking ends spell and prevents recast10 minutes. |
| [Void warp](https://2e.aonprd.com/Spells.aspx?ID=1745) | 2 C/M actions / living creature30 feet | 2d4 void/basic Fortitude; critical failure also enfeebled1 until start caster next turn. |
| [Light](https://2e.aonprd.com/Spells.aspx?ID=1585) | 2 C/M actions /120 feet | Orb bright20-foot radius, then dim20 feet; until daily preparations. Optional attach to willing creature; Sustain moves up to60 feet and may attach/detach; Dismiss. On fifth active cast choose one existing orb to end. Requires real local illumination state. |
| [Ignition](https://2e.aonprd.com/Spells.aspx?ID=1565) | 2 C/M actions / creature30 feet | Spell attack2d4 fire; within reach may choose melee mode upgrading all dice to d6. Critical success doubles initial and adds1d4 persistent fire (1d6 melee). Uses MAP. |
| [Vitality lash](https://2e.aonprd.com/Spells.aspx?ID=1744) | 2 C/M actions / undead or void-healing creature30 feet | 2d6 vitality/basic Fortitude; critical failure also enfeebled1 until start caster next turn. It is not living-target healing. |
| [Read aura](https://2e.aonprd.com/Spells.aspx?ID=1646) | 1 minute exploration C/M, uninterrupted 60-second cast outside combat / one object within 30 feet | Report whether magical; caster and advised creatures gain +2 circumstance Identify Magic on item. The [long-casting-time rule](https://2e.aonprd.com/Rules.aspx?ID=2233) means an encounter cannot contain this cast: combat beginning disrupts it. Illusory object is detected only when illusion rank is strictly lower than this spell's rank. Local object metadata suffices. |
| [Electric arc](https://2e.aonprd.com/Spells.aspx?ID=1509) | 2 C/M actions / one or two creatures30 feet | 2d4 electricity/basic Reflex each. Both targets measured from caster, not from first target. |

Additional fixed-grant tests: Dizzying Colors level3 victim improves save outcome via incapacitation; blinded/stunned expire at their distinct times. Light tracks moving illumination and fifth-orb replacement through save/load. Read Aura uses an uninterrupted 60-second cast outside combat and preserves its object-specific magical flag and +2 circumstance Identify Magic benefit for the caster and advised recipients; if an encounter begins, the cast is disrupted. If illusion objects are admitted, detection requires the illusion rank to be strictly lower. Mindlink rejects unwilling/out-of-touch targets and preserves declared communication. Ignition melee critical uses persistent d6, while ranged mode uses d4. These are fixed dependencies, not optional flavor-only actions.

## Level 2 delta and bounded optional menus

All three classes gain one class feat and one skill feat. No new doctrine, cause upgrade, mystery, focus rank, or spell rank. HP increases by class HP+Con; trained/expert statistics increase normally with level.

- Champion: [Defensive Advance](https://2e.aonprd.com/Feats.aspx?ID=5882) remains a small reference option. Reaction resistance scales per table.
- Cleric: ordinary rank-1 slots rise from2 to3; font stays4. Offer [Healing Hands](https://2e.aonprd.com/Feats.aspx?ID=4646) for healing font and [Harming Hands](https://2e.aonprd.com/Feats.aspx?ID=4645) for harmful font: respective spell's d8s become d10s, including offensive use, without changing +8 two-action healing. Another Domain Initiate is legal only with a supported different deity domain.
- Oracle: daily rank-1 slots rise3→4; choose one additional rank-1 repertoire spell. Offer any of the other three already implemented common cursebound feats from the four-handler menu. This creates genuine selection without recursive feat scope. Nudge healing becomes6, Life curse multiplier becomes2, Warning temporary HP becomes1. Curse cap remains2.

All optional selections still enforce prerequisites and rarity. Ordinary common divine spell and equipment menus are shared engine content; do not infer that every printed spell/item is required. Fixed grants remain compulsory exceptions to a deliberately narrow selection menu.

## Required focused tests and continuous encounters

These are proposed tests, not executed results.

Only the Iomedae Warpriest, Justice Champion, and Life Oracle tests are delivery gates. The broader cause/doctrine/mystery cases below preserve source reference inventory for later selected representatives.

1. **Representative manifest:** build one valid playable character for each approved divine representative at L1, then L2. Assert every selected fixed grant has an executable handler. Keep unselected causes, doctrines, and mysteries as reference inventory. Illegal sanctification, deity, font and feat pairs fail before character mutation.
2. **Selected Justice corridor:** ally at15 feet, enemy at15 feet, then each at20 feet. Enemy hits ally; exercise Retributive Strike accept/decline and aura membership, including out-of-reach protection. Save through the chosen reaction and verify cached range is not reused.
3. **Reference-only other causes:** Selfish Shield, Obedience, Iniquity, Redemption, Grandeur, and Liberation preserve their authored trigger/choice scenarios for a later representative; they are not current acceptance gates.
4. **2026 multi-type packet (reference reaction matrix):** L1 protective Champion reaction against 6 slashing+2 fire reduces one eligible component by3, total5, not total3. The selected Justice resistance path must preserve this one-eligible-component ordering; other cause rows remain reference inventory.
5. **Selected Life curse cycle:** Life Oracle uses Nudge the Scales, its Life Link focus spell, and one legal cursebound action, then rejects cap overflow. Focus spell never increments curse. Refocus twice reaches CB0 without restoring daily slots. Save/load preserves curse effects, temporary immunities, pending choices, and focus spend.
6. **Selected healing:** Life Oracle self-Nudge at CB0/1; rank1 Heal and potion magical penalty; nonmagical Treat Wounds unaffected. The reference Bones offensive Heal/Harm case is not a delivery gate. A healing-mode cast must not silently also deal offensive damage.
7. **Reference-only Flames:** Flames curse suppression and Incendiary Aura preserve their source behavior for a later selected mystery; no current acceptance gate.
8. **Linked encounter:** Life link ally hit twice same round (transfer once), next round transfer again, then Oracle unconscious ends link. Persist the round marker through save/load. Link does not require target remain in original casting range absent such wording.
9. **Life revelation checks:** Life Link transfers damage once per round, Nudge the Scales uses its selected life/death alignment, and the selected focus/revelation resources persist through save/load. Other mystery rows remain reference inventory; no selected focus spell silently becomes a plain damage-only approximation.
10. **Two continuous scenes:** fight A uses Champion reaction, Oracle fixed focus and curse action, Cleric font; ten-minute recovery with save/load; fight B confirms restored focus/changed curse but depleted font and daily slots remain. Finish with daily preparation restoring slots, prayer availability, and explicit Nudge alignment choice. Exercise L1 roster before repeating L2 selection/slot deltas.

## Narrow interpretation points to keep visible

- Soul Siphon temporary-HP expiry is unspecified; literal no-expiry is documented above, not claimed as explicit timed source text.
- Foretell Harm multi-target use follows AoN's linked Paizo organized-play clarification; mixed-damage type selection needs an explicit matching-type choice.
- Anathema consequences and multiple simultaneous responder order need local GM input where play reaches those cases. They are not reasons to invent campaign tracking.
- Life-link transfer versus another simultaneous preventative effect is not given a universal ordering in these entries. Recommendation: when both are legally eligible and no rule supplies priority, save an explicit defender-owned ordering choice, then apply each prevention/transfer to the remaining damage in that order. Preserve the decision across save/load. A concrete rule contradiction should stop that interaction for review; no contradiction was identified in the checked entries.
- This note did not run Python tests or create background processes. Optional proposed encounters require actual engine execution by their implementation/review owners before acceptance.
