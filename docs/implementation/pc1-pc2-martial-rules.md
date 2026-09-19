# PC1/PC2 martial family: levels 1 and 2

Source/design handoff, 2026-09-15. This note specifies behavior; it is not evidence that any new behavior has been implemented or tested. Scope: selected representatives are Fighter, the accepted Bear/Cat/Frog/Dragon Barbarian builds, Monk with Monastic Weaponry, Thief Rogue with Nimble Dodge, Forensic Medicine Investigator with Known Weaknesses, and Braggart Swashbuckler with Flying Blade. Other subclasses and instincts remain source reference inventory. Finish the selected level-1 representatives before adding level 2. Optional feats are a small selected menu. No runtime files or tests were changed by this research task.

## Current source baseline

Use [Paizo's official errata](https://paizo.com/pathfinder/faq), including Spring 2026, over older printing text. AoN's PC2 source page still labels its collection as December 2024; individual pages can already incorporate newer changes. Relevant verified corrections:

- Frog tongue is d6; dragon and spirit barbarian damage choices occur when Rage starts.
- Devise a Stratagem itself is not fortune. The substituted Strike is fortune. The revised eligibility includes ranged unarmed attacks; melee weapons, melee unarmed attacks, and thrown weapons require agile/finesse for the Intelligence substitution.
- Qi Spells can be selected repeatedly with a different spell each time. This matters only if that optional feat enters the supported menu.
- Fencer uses Create a Diversion.
- Thief Dexterity damage explicitly requires a melee Strike. It does not apply to thrown attacks.
- Spring 2025 condition clarification: clumsy also penalizes Dexterity-based damage rolls, including thief damage.

The six barbarian instincts below are the PC2 list. Exclude Elemental, Bloodrager, Decay, Ligneous, and additional Howl of the Wild animals. Exclude rogue Avenger and legacy Eldritch Trickster, investigator Esoterica, and later supplements. Fighter and monk have no subclass selection in these books; their feat choices are not mandatory subclass lists.

## Sheet and progression requirements

T = trained, E = expert. Listed HP is class HP per level, plus Constitution; ancestry HP is added once. All six class DCs begin trained and use the chosen class key attribute. Unless a feature says otherwise, level 2 changes trained/expert numerical bonuses through the added level, not proficiency rank.

| Class/source | Key; HP | Perception; Fort/Ref/Will | Weapons; defenses | Initial class skill grants |
|---|---|---|---|---|
| [Fighter](https://2e.aonprd.com/Classes.aspx?ID=35) | Str or Dex; 10 | E; E/E/T | E simple/martial/unarmed, T advanced; T all armor/unarmored | Acrobatics or Athletics, plus 3+Int |
| [Barbarian](https://2e.aonprd.com/Classes.aspx?ID=57) | Str; 12 | E; E/T/E | T simple/martial/unarmed; T light/medium/unarmored | Athletics, plus 3+Int |
| [Monk](https://2e.aonprd.com/Classes.aspx?ID=60) | Str or Dex; 10 | T; E/E/E | T simple/unarmed; E unarmored, untrained armor | 4+Int |
| [Rogue](https://2e.aonprd.com/Classes.aspx?ID=37) | Dex or racket option; 8 | E; T/E/E | T simple/martial/unarmed; T light/unarmored | Stealth, racket skills, plus 7+Int |
| [Investigator](https://2e.aonprd.com/Classes.aspx?ID=59) | Int; 8 | E; T/E/E | T simple/martial/unarmed; T light/unarmored | Society, methodology skills, plus 4+Int |
| [Swashbuckler](https://2e.aonprd.com/Classes.aspx?ID=63) | Dex; 10 | E; T/E/E | T simple/martial/unarmed; T light/unarmored | Acrobatics, style skill, plus 4+Int |

Each gets a class feat at 1 and 2. Each gets a skill feat at 2; rogue also gets one at 1. Rogue and investigator gain a skill increase at 2 (untrained to trained or trained to expert). No other class in this family gains a level 2 skill increase. Fury additionally grants a level 1 barbarian feat. Keep subclass grants separate from ordinary feat selections.

## Fighter: level 1 requirements

- [Reactive Strike](https://2e.aonprd.com/Actions.aspx?ID=2256): reaction; creature in reach uses manipulate/move, makes a ranged attack, or leaves a square during its own move action. Make a melee Strike. Ignore MAP, and do not increase MAP. Critical hit disrupts a triggering manipulate action. Preserve existing movement exceptions and reaction interruption/resumption.
- [Shield Block](https://2e.aonprd.com/Feats.aspx?ID=5212) is an automatic feat. With shield raised, reaction to physical attack damage: reduce by Hardness; remaining damage is dealt to both wielder and shield. This shares the ordinary reaction with Reactive Strike.
- No subclass, critical specialization, or Bravery at level 1/2.

Suggested optional selections: existing Vicious Swing at 1; Sudden Charge at 2 (a lower-level feat remains selectable). Both require actual action execution, not merely feat strings.

## Barbarian: level 1 requirements

[Rage and Quick-Tempered](https://2e.aonprd.com/Classes.aspx?ID=57): Rage costs one action, has concentrate/emotion/mental traits, requires not fatigued and not already raging. Gain temporary HP equal to level+Constitution. Base bonus is +2 to melee Strike damage, halved for agile attacks (round down). Concentrate actions are prohibited unless also rage; Seek is allowed. No AC penalty. Rage ends after one minute, unconsciousness, or encounter end, and cannot be voluntarily ended. Remove remaining Rage temporary HP on ending; for one minute afterward, Rage cannot grant temporary HP again. Re-entry itself has no one-minute prohibition. Quick-Tempered is an optional free action triggered by initiative, requiring neither encumbered nor heavy armor; it uses Rage and its requirements.

Record rage start/end, chosen mode, temporary-HP source, and next temporary-HP eligibility. Do not reset cooldowns at encounter boundaries.

### Selected Barbarian instincts

The table retains all printed PC2 instincts as source reference inventory; delivery preserves the accepted Bear, Cat, Frog, and eight Dragon representatives. Other instincts are not required for this roster.

| Instinct | Mandatory level 1 behavior and choice timing |
|---|---|
| [Animal](https://2e.aonprd.com/Instincts.aspx?ID=8) | Choose animal at creation. While raging, gain its listed unarmed attacks in brawling group and cannot use weapons. Rage gains morph/primal. Base +2 rage damage; agile attack gets +1. |
| [Dragon](https://2e.aonprd.com/Instincts.aspx?ID=9) | Choose dragon at creation. Each Rage choose base mode or +4 typed damage matching dragon; changed mode adds tradition and applicable damage trait to Rage. Choice persists for that Rage. |
| [Fury](https://2e.aonprd.com/Instincts.aspx?ID=10) | Rage bonus becomes +3 and gain an additional level 1 barbarian feat. Agile halves to +1. |
| [Giant](https://2e.aonprd.com/Instincts.aspx?ID=11) | Small/Medium can use Large weapons; other sizes can use one size larger. Start with a qualifying free weapon, base price ≤9 gp, common or accessible; no resale value before runes. Oversized weapon has its actual Bulk. Wielding it in combat gives unremovable clumsy 1 even outside Rage; while raging it raises bonus to +6. This does not enlarge the actor or increase weapon die/reach. |
| [Spirit](https://2e.aonprd.com/Instincts.aspx?ID=12) | Each Rage choose normal +2 or +3 spirit damage. Spirit mode also gives weapon/unarmed ghost touch and makes Rage divine/spirit. Implement incorporeal interaction when such a target is admitted. |
| [Superstition](https://2e.aonprd.com/Instincts.aspx?ID=13) | While raging: +2 status to saves against magic; +3 rage damage, or +4 against a creature witnessed Casting a Spell in last hour. Rage heals HP equal to the temporary HP actually gained, at most once per 10 minutes. Willingly accepting magic while raging produces frightened 1 with a floor of 1 while that effect remains. Learning/casting spells or wielding/using an item activatable to Cast a Spell violates anathema: disable instinct abilities and dependent feats until one downtime day recentering. Other barbarian abilities remain. |

Animal table (all attacks unarmed; B/P/S denote physical types):

| Choice | Primary attack | Additional attack |
|---|---|---|
| Ape | fist d10 B, grapple | — |
| Bear | jaws d10 P | claw d6 S, agile |
| Bull | horn d10 P, shove | — |
| Cat | jaws d10 P | claw d6 S, agile |
| Deer | antler d10 P, grapple | — |
| Frog | jaws d10 B | tongue d6 B, agile |
| Shark | jaws d10 P, grapple | — |
| Snake | fangs d10 P, grapple | — |
| Wolf | jaws d10 P, trip | — |

Dragon table: Adamantine primal/bludgeoning; Conspirator occult/poison; Diabolic divine/fire; Empyreal divine/spirit; Fortune arcane/force; Horned primal/poison; Mirage arcane/mental; Omen occult/mental. This is a damage/tradition choice, not a level 1 breath weapon.

No instinct specialization or resistance at levels 1/2. No Furious Footfalls until 3. Superstition witness history, willing acceptance, anathema adjudication, and recentering can use explicit context inputs with timestamps; do not guess them from prose.

## Monk: level 1 requirements

[Flurry of Blows and Powerful Fist](https://2e.aonprd.com/Classes.aspx?ID=60): one action, flourish, two unarmed Strikes with normal sequential MAP. May target different creatures. If both hit the same creature, combine damage for resistance/weakness application. One flourish per turn; record its use. Fist becomes d6; lethal unarmed attacks ignore the usual –2 circumstance penalty. No automatic speed bonus or magical unarmed attacks before level 3.

No mandatory stance or qi spell exists. Selected stance support must enforce one-action entry, requirements, and exit on unconsciousness, violated requirements, encounter end, replacement stance, or Dismiss. Cannot enter another stance for one round. Recommended menu: Dragon Stance (1), Stunning Blows (2), detailed below. Do not describe unsupplied stances as supported subclasses.

## Rogue: level 1 requirements

[Class features](https://2e.aonprd.com/Classes.aspx?ID=37): Sneak Attack adds 1d6 precision to eligible Strikes against targets off-guard to the rogue. Eligible: agile/finesse melee weapon or unarmed, ranged weapon/unarmed; thrown melee weapon additionally needs agile/finesse. Precision shares attack damage type and is doubled on a critical hit. Surprise Attack applies only in round 1, only after Stealth/Deception initiative, and only against creatures that have not acted. There is no once-per-turn Sneak Attack limit. No Deny Advantage before 3.

### Selected Rogue racket

The racket table retains source reference inventory; delivery exercises Thief with Nimble Dodge. Other rackets are not required for this roster.

The [racket rules](https://2e.aonprd.com/Rackets.aspx) provide these creation choices:

- **Mastermind:** trained Society plus Arcana/Nature/Occultism/Religion choice; optionally Int key. Successfully identifying a creature with Recall Knowledge makes it off-guard to your attacks until your next turn starts; critical success lasts one minute. Context must distinguish identifying a creature from unrelated knowledge.
- **Ruffian:** trained Intimidation and medium armor; optionally Str key. Additional Sneak Attack eligibility: simple weapon die ≤d8, martial/advanced ≤d6 after ordinary die-size adjustments. These weapons gain critical specialization against an off-guard target on a critical hit. Fatal's critical die change does not invalidate this eligibility. Keep original agile/finesse eligibility independently.
- **Scoundrel:** trained Deception/Diplomacy; optionally Cha key. Successful Feint makes target off-guard to your melee attacks through end of your next turn; critical success applies to all melee attackers. Feint while wielding agile/finesse melee weapon permits immediate free Step, resolved after the check.
- **Thief:** trained Thievery. Melee Strike with finesse weapon/unarmed may use Dex damage in place of Str. Thrown damage still uses Str.

Ruffian requires actual supported weapon-group critical specialization. Admit fixtures using supported groups or implement the group effect before claiming that fixture playable. A feat/racket label alone is not coverage.

## Investigator: level 1 requirements

[Pursue a Lead](https://2e.aonprd.com/Actions.aspx?ID=2811): concentrate/exploration, one minute examining an identified detail. Explicit GM context confirms a larger mystery or no further information. When a mystery exists, opening an investigation is optional and imposes a ten-minute Pursue cooldown. Maintain at most two investigations; a third replaces a chosen one. Abandoned investigation cannot be reopened before next daily preparation. Relevant Perception/skill checks receive +1 circumstance. Solving does not remove benefits until closed/Dismissed; a larger mystery can update the question. Persist question, relevant subjects/checks, cooldown, closed/abandoned status, and known clues.

[Clue In](https://2e.aonprd.com/Actions.aspx?ID=2812): concentrate reaction, once per ten minutes, when another creature attempts a check relevant to an active investigation. Add the investigation circumstance bonus (+1 here), before resolving the check. Context determines communication traits and relevance. This uses the reaction resource.

[Devise a Stratagem](https://2e.aonprd.com/Actions.aspx?ID=2813): concentrate; once per round; choose visible creature. One action, or free if actor knows target could help answer an active investigation. Roll d20, then choose attack or skill mode. Attack: first Strike against that target before next turn uses stored die, gains fortune, and may substitute Int; eligibility for Int is agile/finesse on melee weapon, melee unarmed, or thrown weapon. Other ranged attacks qualify. Skill mode prohibits Striking that target until next turn starts; next Int/Wis/Cha skill or Perception check involving it gets +1 circumstance, or increases applicable investigation bonus by 1. Store die, mode, target, and consumption; do not precompute final attack total before later MAP/modifiers.

[Strategic Strike](https://2e.aonprd.com/Classes.aspx?ID=59) adds 1d6 precision only when a Strike actually uses Int because of Devise a Stratagem. Subsequent normal Strikes gain no extra damage. It is not Sneak Attack and does not require off-guard.

### Selected Investigator methodology

The methodology table retains source reference inventory; delivery exercises Forensic Medicine with Known Weaknesses. Other methodologies are not required for this roster.

- [Alchemical Sciences](https://2e.aonprd.com/Methodologies.aspx?ID=5): Crafting trained; Alchemical Crafting fixed grant; formula book includes four formulas from that feat plus two common level 1 elixir/tool formulas. Every level adds one common elixir/tool formula that can be created. Daily versatile vials = Int modifier; no automatic ten-minute refill from this feature. **Quick Tincture** one action/manipulate, costs one vial, requires known eligible formula, worn/held alchemist toolkit, free hand. Make one elixir/tool of level ≤actor; no Craft check/material payment; infused and activatable only through end of current turn. Making it does not drink/apply it. Share actual item effects with alchemist owner; at minimum select a useful implemented elixir and tool. Formula selections can be a disclosed subset.
- [Empiricism](https://2e.aonprd.com/Methodologies.aspx?ID=6): one Int skill trained; That's Odd fixed grant. **Expeditious Inspection** free action once per ten minutes: Recall Knowledge, Seek, or Sense Motive with ordinary action's check/traits.
- [Forensic Medicine](https://2e.aonprd.com/Methodologies.aspx?ID=7): Medicine trained; Forensic Acumen and Battle Medicine fixed grants. Successful Battle Medicine adds level HP; recipient immune to this actor's Battle Medicine for only one hour. Persist source/recipient immunity, including on failures.
- [Interrogation](https://2e.aonprd.com/Methodologies.aspx?ID=8): Diplomacy trained; No Cause for Alarm fixed grant. May Pursue a Lead while Making an Impression by asking relevant question. **Pointed Question** one action, auditory/concentrate/linguistic/mental; visible non-ally, Diplomacy vs Will DC; one-hour target immunity. Success forces an answer, not truth; Perception DC against their Lie gets +2 (+4 critical). Target is off-guard to the Devise Strike this turn. Failure permits refusal; critical failure also worsens attitude one step. Actual answer/attitude is explicit context.

### Fixed methodology grants must execute

- [That's Odd](https://2e.aonprd.com/Feats.aspx?ID=5938): entering new location reveals one non-obvious suspicious object/area chosen by context, not its explanation and not suspicious creatures. Allows Pursue that clue despite ten-minute cooldown. Repeat entry normally gives nothing; explicit major change can qualify.
- [Alchemical Crafting](https://2e.aonprd.com/Feats.aspx?ID=5117): add four common level 1 formulas and permit Craft alchemical items. Downtime Craft remains a separately bounded activity; do not claim it works if unavailable. The fixed formula grant and Quick Tincture cannot be skipped.
- [Forensic Acumen](https://2e.aonprd.com/Feats.aspx?ID=6483): forensic examination takes half ordinary time, minimum five minutes; success allows immediate relevant Recall Knowledge at +2 circumstance. This is not a universal +2 knowledge bonus.
- [Battle Medicine](https://2e.aonprd.com/Feats.aspx?ID=5125): one action, healing/manipulate, worn/held healer toolkit; Medicine at [Treat Wounds](https://2e.aonprd.com/Actions.aspx?ID=2399) DC. Trained DC15 restores 2d8/4d8 on success/critical; critical failure deals d8; failure does nothing. Level 2 expert may choose DC20 for +10 healing. Does not remove wounded or share Treat Wounds immunity. Ordinary immunity one day; forensic version one hour and +level on success. Apply ordinary toolkit hand requirements.
- [No Cause for Alarm](https://2e.aonprd.com/Feats.aspx?ID=5184): three actions, auditory/concentrate/emotion/linguistic/mental; one Diplomacy roll vs each frightened creature's Will DC in ten-foot emanation. Success lowers frightened 1, critical lowers 2; each becomes immune for one hour. Respect condition floors.

## Swashbuckler: level 1 requirements

[Class](https://2e.aonprd.com/Classes.aspx?ID=63): Precise Strike adds 2 precision damage to agile/finesse melee weapon/unarmed Strikes even without panache. Finisher instead adds 2d6. Stylish Combatant gives +1 circumstance on bravado skill checks in combat, independently of panache; panache grants +5-foot status to all Speeds. Panache ends with encounter. Confident Finisher is one action, makes an eligible Strike, and on ordinary failure deals half the 2d6 precise damage (rounded down), of attack damage type. Critical failure deals none.

[Bravado](https://2e.aonprd.com/Traits.aspx?ID=801): success/critical grants panache; ordinary failure grants panache only through end of next turn; critical failure grants none. This can apply even when target immunity prevents another effect. Keep a lasting-panache state separate from failure-only expiry; failure must not shorten existing lasting panache. All swashbucklers give Tumble Through bravado.

[Finisher](https://2e.aonprd.com/Traits.aspx?ID=802): requires panache and an attack eligible for Precise Strike. Lose panache immediately after performing it. No further attack-trait actions that turn, including Grapple/Trip/Dirty Trick, even after regaining panache. On success player may elect the failure effect instead; this choice belongs after degree/result is known. Preserve reaction/fortune timing.

### Selected Swashbuckler style

The style table retains source reference inventory; delivery exercises Braggart with Flying Blade. Other styles are not required for this roster.

[Styles](https://2e.aonprd.com/Styles.aspx), chosen at creation:

| Style | Trained skill | Actions gaining bravado | Fixed feat |
|---|---|---|---|
| Battledancer | Performance | Perform | Fascinating Performance |
| Braggart | Intimidation | Demoralize | — |
| Fencer | Deception | Create a Diversion, Feint | — |
| Gymnast | Athletics | Grapple, Reposition, Shove, Trip | — |
| Rascal | Thievery | Dirty Trick | Dirty Trick |
| Wit | Diplomacy | Bon Mot | Bon Mot |

No exemplary finishers, Opportune Riposte, or Vivacious Speed at level 1/2.

- [Dirty Trick](https://2e.aonprd.com/Feats.aspx?ID=6472): one action, attack/manipulate; free hand, melee reach. Thievery vs Reflex DC, normal MAP. Success gives clumsy 1 for one round or until target Interacts to remove it; critical success has no automatic expiry. Critical failure makes user prone. Failure has no target effect but can still generate temporary panache.
- [Bon Mot](https://2e.aonprd.com/Feats.aspx?ID=6466): one action, auditory/concentrate/emotion/linguistic/mental; foe within 30 feet; Diplomacy vs Will DC. Success gives –2 status Perception/Will, critical –3, for one minute. Retort ends it: one concentrate action or context-approved skill action requiring ≥one action. Critical failure gives user –2 until one minute or their next successful Bon Mot. This is not frightened.
- [Fascinating Performance](https://2e.aonprd.com/Feats.aspx?ID=5147): choose observer before Perform roll, compare to Will DC; success fascinates one round. Combat requires critical success and adds incapacitation. Each attempted target immune one hour. Expert Performance allows four observers (normally not available to swash at 2 without another source). Fascination ends under ordinary hostile-action rules; panache is independent of whether fascination sticks.

## Required skill actions and context

All durations use ordinary turn/round clocks, not an arbitrary decrement after every action. Secret checks can consume controlled dice in deterministic tests while user output withholds secret result.

| Action/source | Required execution |
|---|---|
| [Tumble Through](https://2e.aonprd.com/Actions.aspx?ID=2370) | One move action; Stride and attempt one enemy space, Acrobatics vs Reflex DC on entry. Success crosses enemy squares as difficult terrain; insufficient movement to exit acts as failure. Failure stops and triggers reactions as leaving starting square. |
| [Feint](https://2e.aonprd.com/Actions.aspx?ID=2390) | One mental action, trained Deception, melee reach, vs Perception DC. Success: off-guard to next melee attack this turn; critical: all user's melee attacks through end next turn. Critical failure reverses exposure to target's melee attacks through end next turn. Apply scoundrel replacement. |
| [Create a Diversion](https://2e.aonprd.com/Actions.aspx?ID=2387) | One mental action; visual trick adds manipulate, speech adds auditory/linguistic. One Deception roll vs observer Perception DCs. Success hides actor from successful observers through turn end or disallowed action; Strike gets off-guard then reveals. Step/Hide/Sneak preserve it. Every attempted observer gains +4 circumstance against repeats for one minute. |
| [Demoralize](https://2e.aonprd.com/Actions.aspx?ID=2395) | One auditory/concentrate/emotion/fear/mental action; aware target within 30 feet; Intimidation vs Will DC; –4 circumstance without understood speech. Success frightened 1, critical 2; immunity against same actor ten minutes regardless of outcome. |
| [Grapple](https://2e.aonprd.com/Actions.aspx?ID=2376) | One attack action; Athletics vs Fortitude DC; free hand unless already holding target; target ≤one size larger. Success grabbed, critical restrained, through end next turn unless user moves or target Escapes. Failure ends user's existing hold. Critical failure also offers target grab-user or make-user-prone choice. |
| [Reposition](https://2e.aonprd.com/Actions.aspx?ID=2379) | One attack; Athletics vs Fortitude DC; hand free or own grab/restraint; ≤one size larger. Success move target ≤5 feet, critical ≤10, entirely within reach without obstacles. Critical failure target may move user ≤5 feet. Forced movement does not trigger move reactions. |
| [Shove](https://2e.aonprd.com/Actions.aspx?ID=2380) | One attack; Athletics vs Fortitude DC; hand free; ≤one size larger. Success pushes 5 feet, critical up to 10. Optional follow Stride same distance/direction. Critical failure user prone. Forced target movement and voluntary follower movement differ for reactions. |
| [Trip](https://2e.aonprd.com/Actions.aspx?ID=2382) | One attack; Athletics vs Reflex DC; free hand, ≤one size larger. Success target prone; critical also d6 B. Critical failure user prone. Appropriate weapon/unarmed maneuver traits provide their documented hand/reach/item-bonus alternatives. |
| [Perform](https://2e.aonprd.com/Actions.aspx?ID=2401) | One concentrate action; Performance against context-provided reasonable DC. Use Fascinating Performance's chosen observer DC where applicable. Do not hardcode a universally trivial bravado DC. |
| [Recall Knowledge](https://2e.aonprd.com/Actions.aspx?ID=2367) | One concentrate/secret action; choose question/skill before commitment; GM/context supplies DC, relevance, answer. Success accurate answer, critical additional context/followup; failure no useful information, critical failure false information or none. |

Narrative context is literal input, not automatic world inference: investigation relevance, clue/no clue, target attitude/answer, Perform DC, identification result, optional daring bravado action, magical effect acceptance, and observed spellcast. Validate mechanical outcomes after accepting the input. Missing required adjudication pauses before committing dependent outcomes.

## Selected optional feats: executable small menu

These are recommendations for supported fixtures. Fixed grants above remain mandatory regardless of this shortlist. A level 2 slot can select a level 1 feat.

| Feat | Suggested use | Execution/source |
|---|---|---|
| Sudden Charge (1) | Fighter; Barbarian; Fury's second feat | Two actions, flourish; Stride twice, then optional melee Strike if an enemy is within your melee reach. [Source](https://2e.aonprd.com/Feats.aspx?ID=4774). |
| Raging Intimidation (1) | Barbarian | Demoralize gets rage while raging. Automatically gain Intimidating Glare when trained in Intimidation; implement that grant, not just a name. Scare to Death prerequisites cannot be met at 1/2. [Source](https://2e.aonprd.com/Feats.aspx?ID=5810). [Glare](https://2e.aonprd.com/Feats.aspx?ID=5162) replaces auditory with visual and removes language penalty. |
| No Escape (2) | Barbarian | Rage reaction when enemy in reach tries moving away; follow via Stride up to Speed, maintaining reach throughout, stop when enemy stops or movement used. [Source](https://2e.aonprd.com/Feats.aspx?ID=5815). |
| Dragon Stance (1) | Monk | One stance action, unarmored; d10 B dragon tail, backswing/nonlethal/unarmed, brawling; ignore first difficult-terrain square during Stride. [Source](https://2e.aonprd.com/Feats.aspx?ID=5977). Implement backswing or choose a different verified feat. |
| Stunning Blows (2) | Monk | When both Flurry Strikes target same creature and either hits/deals damage, optional Fortitude save vs class DC; failure stunned 1, critical failure stunned 3; incapacitation. No effect on success/critical. [Source](https://2e.aonprd.com/Feats.aspx?ID=5989). |
| Nimble Dodge (1) | Rogue | Reaction when visible creature targets user with attack, before roll; requires not encumbered; +2 circumstance AC for that attack. [Source](https://2e.aonprd.com/Feats.aspx?ID=4916). |
| Mobility (2) | Rogue | Stride moving ≤half Speed triggers no reactions. Preserve half-speed limit and terrain costs. [Source](https://2e.aonprd.com/Feats.aspx?ID=4926). |
| Known Weaknesses (1) | Investigator | Optional Recall Knowledge as part of Devise, before its d20. Critical success gives allies +1 circumstance on next attack against target before user's next turn, and user's attack stratagem roll too. [Source](https://2e.aonprd.com/Feats.aspx?ID=5936). |
| Athletic Strategist (2) | Investigator | Trained Athletics; first eligible Strike/Disarm/Grapple/Reposition/Shove/Trip against stratagem target must consume stored attack die. May use Int for maneuver, subject to weapon eligibility if used. No Strategic Strike precision on a maneuver. [Source](https://2e.aonprd.com/Feats.aspx?ID=5940). |
| Flying Blade (1) | Swashbuckler | Extend Precise Strike and eligible finishers to agile/finesse thrown weapon attacks within first range increment. [Source](https://2e.aonprd.com/Feats.aspx?ID=6130). |
| Tumble Behind (2) | Swashbuckler | Successful Tumble Through makes that foe off-guard to next attack before turn end. [Source](https://2e.aonprd.com/Feats.aspx?ID=6142). |

Suggested skill-feat subset: Battle Medicine, Intimidating Glare, Assurance for a declared skill, and class fixed grants. Other selections must be disclosed as unsupported before character confirmation; no substitution without player choice.

## Level 2 delta and acceptance gates

All six gain class HP+Con and one class/skill feat, with ordinary proficiency +1 from level. Rogue/investigator also choose one skill increase. Alchemical Sciences gains one eligible formula. Sneak Attack/Strategic Strike stay d6; Precise Strike stays 2/2d6; rage/instinct damage stays unchanged; no new automatic martial reactions or movement bonuses.

Suggested source-informed assertions (proposals, not executed evidence):

1. **Rage clocks:** level 1 Con+3 gains 4 temporary HP, +2 base melee, +1 agile; normal AC unchanged. Knock unconscious, wake, re-Rage within minute: no temporary HP. Superstition healing likewise uses actual temporary HP gained and its separate ten-minute lock. Save/load mid-cooldown preserves it.
2. **Approved instinct coverage:** preserve the accepted Bear, Cat, Frog and eight Dragon builds. Other Animal variants and Fury/Giant/Spirit/Superstition remain reference inventory unless separately selected. Frog tongue is d6; Dragon +4 fire is separate from slashing weapon damage.
3. **Flurry:** two successful 5-point physical hits vs resistance 3 inflict 7 total, not 4; split targets each apply their own resistance. MAP increments twice. A second flourish is rejected. Level 2 Stunning Blows saves once; higher-level target gets incapacitation degree adjustment.
4. **Selected racket:** Thief's finesse melee damage uses Dex; thrown uses Str. Nimble Dodge is a one-reaction AC choice. Other racket-specific branches remain reference inventory.
5. **Devise:** controlled d20=4 is displayed before mode choice. Attack mode stores 4 and uses current MAP at Strike; next Strike rolls normally. Skill mode blocks only selected target's Strikes, allows other target, consumes bonus only on next eligible check. Free cost requires recorded known relevance. Reload saved state between d20 and mode selection and before substituted Strike.
6. **Selected methodology:** Forensic Medicine's Battle Medicine success adds level and has one-hour source-specific immunity; wounded remains unchanged. The selected Forensic Acumen and Known Weaknesses paths preserve their declared follow-up checks. Other methodology actions remain reference inventory.
7. **Selected style:** execute Braggart actions and Flying Blade. Other style actions, including Rascal Dirty Trick, remain reference inventory. Bravado ordinary failure grants expiring panache even with no debuff; critical failure does not. Finisher uses MAP, loses panache even on miss, and blocks later Trip/Strike.
8. **Selected fixed feats:** exercise Known Weaknesses, Nimble Dodge, Flying Blade, Forensic Acumen, and Forensic Medicine's Battle Medicine with actual checks and saved continuation. A declaration-only fixture does not satisfy these gates; unselected feat rows remain reference inventory.

## Continuous encounter proposals

Selected representative encounter proposals are the delivery scope; the remaining bullets preserve reference scenarios for unselected branches.

- **Courtyard pursuit:** selected Fighter, Bear Barbarian, and Monk versus melee guard and archer. Start via Stealth initiative; Quick-Tempered choice; Tumble/Feint to establish off-guard; Flurry into resistance; reactive movement. Conclude, recover, and immediately start a second fight to test cooldown carryover.
- **Mage's archive (reference for unselected instincts):** Superstition/Spirit variants rotate through otherwise identical local fixtures, with a caster and incorporeal opponent. Record seen spellcast, willing buff acceptance, save bonuses, damage types, ghost touch, and interrupted Rage only if a later representative selects those instincts.
- **Forensic ledger:** selected Forensic Medicine Investigator enters an authored room, Pursues a Lead, uses Known Weaknesses and Battle Medicine, then fights that known lead. Save between clue and fight and after the stored die.
- **Six-style duel (reference inventory):** one fixture per Swashbuckler style remains source inventory; selected Braggart coverage uses its Intimidation/Flying Blade path. Other style actions await explicit selection.

Run focused tests serially during implementation; then coherent scripted encounters, save/load, full suite, and broader actual-engine play at integration. Every coverage claim must identify exercised paths. This research task launched no test/probe/background process; all source reads were bounded foreground commands.

## Core-owner handoff

Keep behavior in existing local Python state/command resolution. Needed extensions are concrete: damage components with precision flags; source-relative and next-attack off-guard; turn/real-time expiries and immunity keys; initiative free actions; rage mode and temporary-HP provenance; stored stratagem die/post-roll choice; panache expiry/finisher attack lock; grouped strike damage; maneuver checks and forced movement; formula/vial/item activation state; optional context records. Existing dataclass commands, choice pauses, events, and persistence are suitable seams. No service, browser, registry, or distributed state is needed.

Outstanding implementation prerequisites are explicit rather than silent approximations: ruffian weapon-group critical effects, incorporeal/ghost-touch damage, toolkit hand semantics, fascinated/incapacitation, alchemical elixir/tool activation, and downtime Craft if claimed playable. No unresolved source conflict was found for the mandatory level 1/2 class features. Optional expanded menus require their own bounded source verification.
