# PC1/PC2 arcane-family level 1–2 implementation brief

Source/design handoff, verified 2026-09-15. This document specifies work; it is **not evidence that these rules are implemented or tested**. Family: Bard, Witch, Wizard, Sorcerer. Use current Remaster text, including [Paizo errata](https://paizo.com/pathfinder/faq). No runtime or tests were changed by this source pass.

## Scope and shared dependencies

The approved arcane representatives are Maestro Bard, Faith's Flamekeeper Witch with Patron's Puppet, Battle Magic Wizard with Spell Substitution, and Angelic Sorcerer. Other muses, patrons, schools, theses, bloodlines, and nested influences remain source reference inventory. Use a limited caster spell/school menu and one or two nested examples; no 64-configuration matrix is required.

Implement each selected representative's mandatory grants and branch mechanisms. Optional selections may use a small explicit common catalogue. A legal local preset is sufficient; a general character builder is not required. Known-but-unimplemented mandatory spells are not acceptable substitutes for playable grants. School curriculum choices do not require every reference-listed spell to ship, but each selected preset must actually possess the mandated number of legal choices.

Shared engine requirements:

- Cast provenance: caster, tradition, class/source, spell/rank, prepared-slot identity or spontaneous rank pool, focus/cantrip/staff/bond origin, grant membership, target selections, and initial versus later damage. A spell name alone cannot determine Blood Magic or Sorcerous Potency.
- Literal known spells, prepared slots, repertoire entries, curriculum slots, staff charges, used daily resources, focus points, and local elapsed time. Save/load preserves all of them.
- Effect instances with owner, target, typed modifiers, exact turn-boundary expiry, Sustain state, immunity timers, linked conditions, consumed/extended flags, and reaction windows.
- Positioned familiars and summoned minions sharing the ordinary movement, targeting, damage, sensing, and command systems; no scenario-specific pets.
- Spellshape adjacency, variable-action casting, fortune replacement, incapacitation, hostile-action restrictions, attack batches with delayed MAP, and target-specific initial-resolution callbacks.
- Local preparation, 10-minute Refocus/substitution, learning, and staff replacement can be bounded explicit activities; no campaign simulation is needed.

### Common casting and advancement ledger

All listed spells remain rank 1 at both character levels. Cantrips/focus spells heighten at half level rounded up; character level 2 does not grant rank 2 spells. Signature spells start at level 3 for Bard/Sorcerer and must not be granted early.

| Class/source | Level 1 | Level 2 delta |
|---|---|---|
| [Bard](https://2e.aonprd.com/Classes.aspx?ID=32), occult, Charisma | 5 repertoire cantrips; 2 chosen rank-1 repertoire spells plus muse spell; 2 rank-1 slots; Counter Performance and Courageous Anthem | Third slot and another repertoire spell; class feat and skill feat |
| [Witch](https://2e.aonprd.com/Classes.aspx?ID=38), patron tradition, Intelligence | Familiar knows 10 cantrips, 5 chosen rank-1 spells, patron's additional spell; prepare 5 cantrips and 2 rank-1 slots; patron hex cantrip and one selected initial focus hex | Familiar learns 2 spells of available ranks; third rank-1 slot; class feat and skill feat |
| [Wizard](https://2e.aonprd.com/Classes.aspx?ID=39), arcane, Intelligence | Spellbook has 10 chosen cantrips and 5 chosen rank-1 spells, plus school additions; ordinary preparation 5 cantrips and 2 rank-1 slots; school/thesis/bond | Add 2 available-rank spells to book; third ordinary rank-1 slot; class feat and skill feat |
| [Sorcerer](https://2e.aonprd.com/Classes.aspx?ID=62), bloodline tradition, Charisma | 4 chosen cantrips + gift cantrip; 2 chosen rank-1 spells + gift spell; 3 rank-1 slots; initial bloodline focus spell and Blood Magic; Sorcerous Potency | Fourth slot and another chosen rank-1 repertoire spell; class feat and skill feat |

Prepared spells consume their particular slot. Spontaneous casting chooses a known entry and consumes the appropriate rank's pool. Neither an extra known spell nor a focus spell creates a slot. Bard/Sorcerer can swap one same-rank old repertoire spell while leveling; Sorcerer fixed bloodline spells cannot be swapped. The preset's learned-spell catalogue must meet these literal counts, even though only five Witch cantrips are prepared.

The shared `pc1-pc2-encounter-content.md` handoff owns the small legal ordinary-spell catalogue and concrete book/repertoire shortlists. Its presets must fill these counts with distinct known spells, including replacements where a baseline choice overlaps an additional patron/curriculum grant. They must also supply the two learned spells on advancement, rather than treating additional slots as additional knowledge. This document owns fixed grants and their required mechanisms; it does not expand optional selection to entire spell lists.

[Learn a Spell](https://2e.aonprd.com/Actions.aspx?ID=2366): tradition-matched skill, source available throughout, 1 hour per rank, rank-1/cantrip typical DC 15 and 2 gp materials. Critical success costs half, success full, failure none, critical failure half; failures prohibit another attempt until next level. Learning adds to book/familiar access, but does not immediately expand a spontaneous repertoire. Witch scroll consumption instead uses the class's one-hour ingestion rule; written learning and ingestion are distinct operations.

[Refocus](https://2e.aonprd.com/Actions.aspx?ID=2621) takes 10 minutes for 1 Focus Point, up to capacity. Repeat Refocus to refill a multi-point pool. Daily preparation refills it. Count focus spells, not focus cantrips, toward capacity (maximum 3). Bard starts with Counter Performance; Maestro additionally knows Lingering Composition and therefore has capacity 2. Witch/Wizard/Sorcerer ordinarily have capacity 1 here.

## Bard: selected Maestro representative (other muses are reference inventory)

[PC1 muse list](https://2e.aonprd.com/Muses.aspx). The table preserves the full source inventory; delivery exercises the selected Maestro row and its fixed grants.

| Muse | Mandatory spell | Mandatory feat and operational behavior |
|---|---|---|
| Enigma | Sure Strike | [Bardic Lore](https://2e.aonprd.com/Feats.aspx?ID=4573): trained special Lore usable for Recall Knowledge on any topic; not an unrestricted skill substitution |
| Maestro | Soothe | [Lingering Composition](https://2e.aonprd.com/Feats.aspx?ID=4575): grants its focus spell |
| Polymath | Phantasmal Minion | [Versatile Performance](https://2e.aonprd.com/Feats.aspx?ID=4578): Performance substitutes for Demoralize/Make an Impression and acting Performance for Impersonate; Performance rank qualifies for relevant skill-feat prerequisites |
| Warrior | Fear | [Martial Performance](https://2e.aonprd.com/Feats.aspx?ID=4576): damaging an enemy with a Strike extends the active Courageous Anthem by one round, once per casting; a hit dealing zero damage is insufficient |

All bards are trained in martial weapons. Do not retain legacy Warrior-only martial proficiency. Compositions permit one cast per turn and one active composition per caster; a new composition ends the prior one's ongoing effects. Reaction casting still participates in the active-composition rule.

- [Courageous Anthem](https://2e.aonprd.com/Spells.aspx?ID=1763): 1 action, 60-foot emanation, 1 round; caster/allies gain +1 status to attack rolls, damage rolls, and fear saves. Respect mental/emotion immunity and chosen performance sensory requirements.
- [Counter Performance](https://2e.aonprd.com/Spells.aspx?ID=1762): reaction plus 1 focus when caster/ally within 60 feet rolls a save versus auditory/visual effect. Matching Performance check; affected caster/allies can use its result if better than their save. It is a fortune effect. The trigger occurs at the roll, before applying the result.
- [Lingering Composition](https://2e.aonprd.com/Spells.aspx?ID=1769): free-action focus spellshape immediately before a 1-round composition cantrip. Performance versus standard DC for highest-level target (L1 15; L2 16 for equal-level groups), subject to explicit GM override. Critical success/success/failure: 4/3/1 rounds; failure spends no focus. It lacks the composition trait, so it does not consume the turn's composition allowance.

Level-2 minimal class-feat selection: Reach Spell. Broader muse feats, including Multifarious Muse, are optional catalogue extensions and are not required for the selected Maestro representative.

## Witch: selected Faith's Flamekeeper representative (other patrons are reference inventory)

[Patron trigger rule](https://2e.aonprd.com/Patrons.aspx): the familiar's special ability can occur once per round on Cast or Sustain of a hex; the witch chooses before or after that operation's effects. It costs no command action. Store the round gate separately from the once-per-turn hex-cast gate. Sustaining an existing hex does not cast another hex.

The selected Witch familiar has its fixed patron ability plus three selectable abilities. A grounded Tiny familiar with Manual Dexterity, Tough, and Fast Movement is a legal compact selection. The full patron table below remains source reference inventory; delivery exercises Faith's Flamekeeper.

| Patron/source | Tradition | Hex cantrip; additional familiar-known spell | Familiar trigger |
|---|---|---|---|
| [Faith's Flamekeeper](https://2e.aonprd.com/Patrons.aspx?ID=12) | Divine | Stoke the Heart; Command | One willing creature within 15 feet gains 2 + floor(level/2) temporary HP, until witch's next turn starts (2 at L1, 3 at L2) |
| [The Inscribed One](https://2e.aonprd.com/Patrons.aspx?ID=13) | Arcane | Discern Secrets; Runic Weapon | Until next turn starts, familiar can flank as if it could attack with 5-foot reach; visual effect; it still cannot Strike |
| [The Resentment](https://2e.aonprd.com/Patrons.aspx?ID=14) | Occult | Evil Eye; Enfeeble | Within 15 feet, extend one selected timed negative-condition instance by 1 round, only once for that instance; curse; other removal still works |
| [Silence in Snow](https://2e.aonprd.com/Patrons.aspx?ID=15) | Primal | Clinging Ice; Gust of Wind | 5-foot burst centered on a familiar-space square becomes difficult terrain until next turn starts |
| [Spinner of Threads](https://2e.aonprd.com/Patrons.aspx?ID=16) | Occult | Nudge Fate; Sure Strike | One creature within 15 feet: choose +1 status AC or −1 status AC until next turn starts |
| [Starless Shadow](https://2e.aonprd.com/Patrons.aspx?ID=17) | Occult | Shroud of Night; Fear | Adjacent enemy to which familiar is concealed/hidden/undetected becomes frightened 1 |
| [Wilding Steward](https://2e.aonprd.com/Patrons.aspx?ID=18) | Primal | Wilding Word; choose Summon Animal or Summon Plant or Fungus | Familiar gains imprecise scent/tremorsense/wavesense 60 feet until next turn starts, and can immediately Point Out free |

The Resentment row uses Spring 2026 errata. Frightened's ordinary decrement is not a timed duration to prolong. Do not repeatedly extend Enfeeble's same condition instance. The extension marker belongs to the instance and survives saves.

### Initial focus-hex choice and familiar dependence

The class grants a choice of [Patron's Puppet](https://2e.aonprd.com/Spells.aspx?ID=1882) or [Phase Familiar](https://2e.aonprd.com/Spells.aspx?ID=1884). Support both legal selections; no other patron branch changes.

- Puppet: free action when the witch's turn starts; 1 focus; commands familiar for its usual two actions, without auditory/concentrate command traits. It is a hex and occupies that turn's one hex cast. An ordinary command must not produce a second minion action allotment.
- Phase: reaction when familiar would take damage, 60-foot range; 1 focus; resistance 5 to all triggering damage and immunity to precision damage for that damage only. It is a hex on the triggering turn.
- Attempting a second hex on the same turn fails and loses its actions, per the explicit class rule; do not turn this into a cost-free generic validation rejection.
- Familiar need not be present for ordinary hex casting. It must be present to Refocus. Death leaves already prepared spells usable; replacement at next daily preparation knows the old familiar's spells. Preparing requires communing with the familiar.

### Rank-1 hex cantrips

All below cost one action, have 30-foot range and one creature target. Cantrips cost no focus. Preserve each entry's traits and saves.

| Spell/source | Required behavior |
|---|---|
| [Stoke the Heart](https://2e.aonprd.com/Spells.aspx?ID=1892) | Sustain up to 1 minute; +2 status damage. Does not stack with a weaker status damage bonus |
| [Discern Secrets](https://2e.aonprd.com/Spells.aspx?ID=1888) | Target immediately Recall Knowledge/Seek/Sense Motive free; +1 status to that roll's statistic while sustained up to 1 minute; target immune to this spell for 1 minute. Sustain does not grant another free check |
| [Evil Eye](https://2e.aonprd.com/Spells.aspx?ID=1889) | Will failure/critical failure gives sickened 1/2; while sustained (≤1 minute) and witch sees target, value cannot fall below 1 |
| [Clinging Ice](https://2e.aonprd.com/Spells.aspx?ID=1887) | Reflex: no/half/full/double 1d4 cold; failure/critical failure adds −5/−10-foot circumstance Speed penalty while sustained, ≤1 minute. Sustain does not repeat damage |
| [Nudge Fate](https://2e.aonprd.com/Spells.aspx?ID=1890) | 1 minute; only when +1 status would change failed check's degree from critical failure→failure or failure→success, apply it retroactively and consume effect. New cast ends caster's old Nudge Fate |
| [Shroud of Night](https://2e.aonprd.com/Spells.aspx?ID=1891) | Will success unaffected; failure treats bright light as dim and all creatures concealed unless greater darkvision; sustained ≤1 minute. Willing target may choose result |
| [Wilding Word](https://2e.aonprd.com/Spells.aspx?ID=1893) | Sustained ≤1 minute; animal/plant/fungus takes −1 circumstance to initial Will save. Critical success none; success −2 status on attacks/skill checks harming witch; failure additionally sickened 1 whenever it damages witch; critical failure sickened 2 |

Level 2 adds two familiar-known spells and one ordinary slot, not a new patron power. Choose Reach Spell as the bounded class feat; lessons and additional familiar abilities remain optional.

## Wizard: selected Battle Magic school and Spell Substitution thesis (other schools/theses are reference inventory)

[School rules](https://2e.aonprd.com/ArcaneSchools.aspx): each curriculum school adds one chosen curriculum cantrip and two chosen rank-1 curriculum spells to its book, prepares an extra curriculum cantrip, and receives one rank-1 curriculum-only slot. Thus ordinary schools prepare six cantrips and three/four total rank-1 slots at L1/L2. Curriculum spells must also be known. Unified Magical Theory is the exception.

The table lists the exact printed rank-0/rank-1 options as source reference inventory; bold choices form a minimal proposed package for the selected Battle Magic representative. Optional alternatives may remain outside the shipped catalogue. This table is not a claim that their spell effects are already specified or implemented.

| School/source | Curriculum cantrips | Rank-1 curriculum | Mandatory initial focus spell |
|---|---|---|---|
| [Ars Grammatica](https://2e.aonprd.com/ArcaneSchools.aspx?ID=16) | **Message**, Sigil | **Command**, Disguise Magic, Runic Body, **Runic Weapon** | Protective Wards |
| [Battle Magic](https://2e.aonprd.com/ArcaneSchools.aspx?ID=22) | **Shield**, Telekinetic Projectile | **Breathe Fire**, **Force Barrage**, Mystic Armor | Force Bolt |
| [Civic Wizardry](https://2e.aonprd.com/ArcaneSchools.aspx?ID=18) | Prestidigitation, **Read Aura** | **Hydraulic Push**, **Pummeling Rubble**, Summon Construct | Earthworks |
| [The Boundary](https://2e.aonprd.com/ArcaneSchools.aspx?ID=17) | Telekinetic Hand, **Void Warp** | **Grim Tendrils**, Phantasmal Minion, **Summon Undead** | Fortify Summoning |
| [Mentalism](https://2e.aonprd.com/ArcaneSchools.aspx?ID=19) | **Daze**, Figment | **Dizzying Colors**, Sleep, **Sure Strike** | Charming Push |
| [Protean Form](https://2e.aonprd.com/ArcaneSchools.aspx?ID=20) | **Gouging Claw**, Tangle Vine | **Jump**, Pest Form, **Spider Sting** | Scramble Body |
| [Unified Magical Theory](https://2e.aonprd.com/ArcaneSchools.aspx?ID=21) | No curriculum | Add one chosen rank-1 spell instead; one additional L1 wizard feat | Hand of the Apprentice |

Unified has no curriculum slots/cantrip, and no curriculum-specific benefits. It uses Drain Bonded Item once per available rank per day. At L1–2 only rank 1 exists: this is still one daily use. All schools receive their initial focus spell, including Unified; do not import the legacy feat-gated Hand of the Apprentice rule.

### School focus spells

All cost one focus. Values below are for rank 1.

| Spell/source | Actions; targeting; effect |
|---|---|
| [Protective Wards](https://2e.aonprd.com/Spells.aspx?ID=1894) | 1; caster-centered 5-foot emanation, sustained ≤1 minute; caster/allies +1 status AC; every Sustain grows radius 5 feet up to 30 |
| [Force Bolt](https://2e.aonprd.com/Spells.aspx?ID=1896) | 1; one creature 30 feet; automatic 1d4+1 force, no attack roll/MAP |
| [Earthworks](https://2e.aonprd.com/Spells.aspx?ID=1900) | 1/2/3; range 60 feet, 5/10/15-foot burst; ground difficult terrain for 1 minute; Interact clears one adjacent square |
| [Fortify Summoning](https://2e.aonprd.com/Spells.aspx?ID=1898) | 1; own summoned creature 30 feet; +1 status all checks/DCs including AC for remaining summoning, ≤1 minute; not bonus damage |
| [Charming Push](https://2e.aonprd.com/Spells.aspx?ID=1902) | 1; creature 30 feet, Will, incapacitation; critical success none; success −1 circumstance attacks/damage versus caster; failure forbids hostile actions versus caster; critical failure also stunned 1; ends caster's next turn start |
| [Scramble Body](https://2e.aonprd.com/Spells.aspx?ID=1904) | 2; living creature 30 feet, Fortitude; success none, failure sickened 1, critical failure sickened 2 and slowed 1 while sickened; no invented fixed duration |
| [Hand of the Apprentice](https://2e.aonprd.com/Spells.aspx?ID=1906) | 1; creature 500 feet; held trained melee weapon; spell attack, weapon melee-Strike damage with Intelligence instead of Strength; critical doubles damage and adds weapon critical specialization; weapon returns even on miss |

### Selected Spell Substitution thesis and resource rules

- [Experimental Spellshaping](https://2e.aonprd.com/ArcaneThesis.aspx?ID=6): grant one L1 spellshape wizard feat (minimal choice Reach Spell). The daily flexible feat does not start until level 4.
- [Improved Familiar Attunement](https://2e.aonprd.com/ArcaneThesis.aspx?ID=7): Familiar feat plus one extra ability (three total); Drain Familiar replaces Drain Bonded Item. This is one bond resource, not an additional daily cast. Preserve familiar ownership/presence; the inherited item's “on your person” requirement needs explicit familiar-equivalent handling, not arbitrary range.
- [Spell Blending](https://2e.aonprd.com/ArcaneThesis.aspx?ID=8): preparation trades two same-rank slots for one bonus slot up to two ranks higher, but only a rank normally castable, with distinct bonus ranks. At L1–2 no rank 2/3 may be created. It can instead exchange one slot for two extra prepared cantrips (only one such exchange). This provides a useful legal early-level branch.
- [Spell Substitution](https://2e.aonprd.com/ArcaneThesis.aspx?ID=9): 10 uninterrupted minutes swaps an unexpended prepared slot for another known spell of appropriate rank/type. Interruption leaves original prepared and resets progress; expended slots do not refill; curriculum restrictions persist.
- [Staff Nexus](https://2e.aonprd.com/ArcaneThesis.aspx?ID=10): makeshift staff holds one cantrip and one rank-1 spell from book. At preparation sacrifice one spell for rank-many charges (here one), lost after 24 hours; rank-1 cast costs one charge, cantrip none; hold staff and pay spell's usual actions. Destroyed staff can be replaced in one hour without charges. Merging with an acquired staff is possible during preparation, but no acquired staff is needed for minimal starting profiles. The makeshift staff's explicit charging provision is distinct from a purchased staff's free daily charges; do not award an extra free charge automatically.

[Arcane Bond](https://2e.aonprd.com/Classes.aspx?ID=39): select owned bonded item during daily prep. Drain Bonded Item is free, once daily, requires it on person; during that same turn recast one spell prepared today and already cast, without spending a slot. It still costs normal casting actions. Track the eligible history, turn-limited permission and daily use; do not refill a slot or permit next-turn banking. Staff-cast spells are not automatically eligible history.

[Staff casting rules](https://2e.aonprd.com/Rules.aspx?ID=3211): ordinary prepared staff belongs to preparer for casting; require spell on spell list and accessible rank, held staff, normal actions, caster's spell attack/DC. Cantrips cost no charges. Track staff provenance separately from slots. Acquired staff charge refresh clears old charges; no more than one staff per person/day or preparer per staff/day.

Minimal extra Unified feat: Reach Spell; if Experimental already grants Reach, take Familiar (ordinary two abilities, bonded item remains item). Minimal L2 Wizard feat: [Energy Ablation](https://2e.aonprd.com/Feats.aspx?ID=5026), 1-action spellshape before an energy-damaging spell, chosen energy resistance equal to rank until next turn ends, regardless of whether spell damages anyone. The selected Battle Magic/Spell Substitution preset does not require the remaining thesis matrix.

## Selected Angelic bloodline and nested example

[Bloodline rules](https://2e.aonprd.com/Bloodlines.aspx): initial focus spell costs one focus. Casting it with focus or a sorcerous gift with a slot triggers one selected known Blood Magic effect. Gift cantrip casting does **not** trigger it. Choose options/recipient before resolving the spell; apply Blood Magic after initial checks. Foe recipient requires a successful spell attack or failed save. For an area, designate caster or one area target. New benefit replaces the prior active Blood Magic benefit unless a supported feature explicitly permits more.

Sorcerous Potency: spells cast **from slots** gain rank-many status damage/healing, only initial resolution and once per creature per spell. At these levels +1. Cantrip/focus/staff casting gets none. Apply ordinary typed stacking; [Angelic Halo's clarification](https://2e.aonprd.com/Spells.aspx?ID=2093) explicitly says its healing status bonus and Potency do not add together. Persistent/later Sustain damage gains no Potency.

| Bloodline/source | Tradition; skills | Gift cantrip; rank-1 gift | Focus spell | Blood Magic at rank 1 |
|---|---|---|---|---|
| [Aberrant](https://2e.aonprd.com/Bloodlines.aspx?ID=19) | Occult; Intimidation, Occultism | Daze; Phantom Pain | Tentacular Limbs | Target −1 status Will or self +2 status Will, 1 round |
| [Angelic](https://2e.aonprd.com/Bloodlines.aspx?ID=20) | Divine; Diplomacy, Religion | Light; Heal | Angelic Halo | Self/target +1 status saves, 1 round |
| [Demonic](https://2e.aonprd.com/Bloodlines.aspx?ID=21) | Divine; Intimidation, Religion | Caustic Blast; Fear | Glutton's Jaws | Target −1 status AC or self +2 status Intimidation, 1 round |
| [Diabolic](https://2e.aonprd.com/Bloodlines.aspx?ID=22) | Divine; Deception, Religion | Ignition; Charm | Diabolic Edict | Target 1 fire damage or self +2 status Deception, 1 round |
| [Draconic](https://2e.aonprd.com/Bloodlines.aspx?ID=23) | Choose arcane/divine/occult/primal; Intimidation + corresponding tradition skill | Shield; Fear | Flurry of Claws | Self/target +1 status AC, 1 round |
| [Elemental](https://2e.aonprd.com/Bloodlines.aspx?ID=24) | Primal; Intimidation, Nature | Influence table below | Elemental Toss | Self +2 status Intimidation for 1 round or target 1 influence-type damage |
| [Fey](https://2e.aonprd.com/Bloodlines.aspx?ID=25) | Primal; Deception, Nature | Figment; Charm | Faerie Dust | Self +2 status Performance or concealed, 1 round; concealment cannot enable Hide |
| [Hag](https://2e.aonprd.com/Bloodlines.aspx?ID=26) | Occult; Deception, Occultism | Daze; Illusory Disguise | Jealous Hex | Retributive Spite: 4 mental, basic Will, to first damaging creature; otherwise 1 temporary HP; timing issue below |
| [Imperial](https://2e.aonprd.com/Bloodlines.aspx?ID=27) | Arcane; Arcana, Society | Detect Magic; Force Barrage | Ancestral Memories | Self +1 status AC or saves until next turn starts |
| [Undead](https://2e.aonprd.com/Bloodlines.aspx?ID=28) | Divine; Intimidation, Religion | Void Warp; Harm | Undeath's Blessing | Self 1 temporary HP until next turn starts or target 1 void damage |

Blood Magic added damage of the same type joins the spell's initial damage before weaknesses/resistances. Do not run a second weakness/resistance application for that addition. All gifted spells are cast in bloodline tradition even when absent from that tradition's ordinary list (e.g. Diabolic Charm/Ignition).

| Elemental influence | Gift cantrip | Rank-1 gift | Toss/Blood Magic damage |
|---|---|---|---|
| Air | Gale Blast | Tailwind | Slashing |
| Earth | Scatter Scree | Pummeling Rubble | Bludgeoning |
| Fire | Ignition | Breathe Fire | Fire |
| Metal | Electric Arc | Thunderstrike | Piercing |
| Water | Frostbite | Hydraulic Push | Bludgeoning |
| Wood | Tangle Vine | Cleanse Cuisine | Bludgeoning |

Draconic tradition choice is permanent and changes Flurry's secondary damage: arcane force, divine spirit, occult mental, primal fire. Specific dragon substitutions needing GM collaboration are not additional printed PC2 mandatory exemplars. Elemental influence is likewise fixed.

### Initial focus spells at rank 1

| Spell/source | Action and exact mechanism |
|---|---|
| [Tentacular Limbs](https://2e.aonprd.com/Spells.aspx?ID=2090) | 1 action, 1 minute; arm unarmed Strikes/touch spells reach 10 feet; weapons unchanged; adding one action to casting temporarily makes delivery reach 20 feet |
| [Angelic Halo](https://2e.aonprd.com/Spells.aspx?ID=2093) | 1 action, 15-foot aura, 1 minute; allies healed by Heal gain status HP bonus twice Heal's rank; do not stack with Potency |
| [Glutton's Jaws](https://2e.aonprd.com/Spells.aspx?ID=2096) | 2 actions, ranged spell attack at creature within 30 feet; hit 2d6 piercing and caster gains 1d4 temporary HP until next turn starts; use spell-attack critical damage, no legacy jaws weapon |
| [Diabolic Edict](https://2e.aonprd.com/Spells.aspx?ID=2099) | 1 action, willing living creature within 30 feet, 1 round; named task gives +1 status relevant attack/skill checks; refusal instead −1 status all attack/skill checks. Local commands must store a concrete task and refusal state |
| [Flurry of Claws](https://2e.aonprd.com/Spells.aspx?ID=2102) | 2 actions; two creatures within 30 feet and ≤10 feet apart; two spell attacks at same current MAP, increment MAP twice afterward; hit 1d8 slashing +1d4 tradition damage each |
| [Elemental Toss](https://2e.aonprd.com/Spells.aspx?ID=2105) | 1 action; 30-foot ranged spell attack; 1d8 influence damage, doubled on critical; element trait matches influence |
| [Faerie Dust](https://2e.aonprd.com/Spells.aspx?ID=2108) | 1–3 actions, 30-foot range, 5/10/15-foot burst, Will; success none, failure no reactions and −2 status Perception/Will for 1 round; critical failure additionally −1 Perception/Will for 1 minute (overlapping weaker penalty does not add) |
| [Jealous Hex](https://2e.aonprd.com/Spells.aspx?ID=2111) | 1 action, creature 30 feet, Will; success none, failure condition 1, critical failure condition 2; highest attribute maps Str→enfeebled, Dex→clumsy, Con→drained, mental attribute→stupefied; target chooses among ties. New Will save at every caster turn start can end it; maximum 1 minute. Despite name, it has no hex trait |
| [Ancestral Memories](https://2e.aonprd.com/Spells.aspx?ID=2114) | 1 action; choose self +1 status next spell attack this turn or enemy within 60 feet −1 status next save against caster's spell this turn; unused benefit expires at turn end |
| [Undeath's Blessing](https://2e.aonprd.com/Spells.aspx?ID=2117) | 1 action, touch living creature, 1 minute; Heal/Harm treat it as undead, Harm healing +2 status. Unwilling Will: critical success none; success half Heal healing/half Harm damage for 1 round; failure full effect. Does not generally change creature trait or other vitality/void interactions |

Level 2 only adds the ledger delta and selected feats here; no new bloodline power. Reach Spell is a legal minimal common choice.

## Mandatory ordinary spells and small local objects

Grant identities in the tables are requirements, not permission to replace them with a similar damage spell. The mandatory repertoire includes non-combat spells, whose bounded effects can act on explicit local actors/items rather than requiring a world simulator.

| Source spell | Rank-1 implementation checkpoint |
|---|---|
| [Sure Strike](https://2e.aonprd.com/Spells.aspx?ID=1709) | 1 action; next attack this turn rolls twice/better, ignores circumstance attack penalties and concealment/hidden flat checks; after use, 10-minute temporary immunity |
| [Soothe](https://2e.aonprd.com/Spells.aspx?ID=1678) | 2 actions, willing creature 30 feet; 1d10+4 healing and +2 status mental saves for 1 minute |
| [Fear](https://2e.aonprd.com/Spells.aspx?ID=1524) | 2 actions, creature 30 feet, Will: no/frightened 1/2/3; critical failure also fleeing 1 round |
| [Command](https://2e.aonprd.com/Spells.aspx?ID=1470) | 2 actions, creature 30 feet, auditory/linguistic/mental; Will success none; failure first next-turn action obeys; critical failure all next-turn actions obey; no Delay/reactions until obeyed. Commands: approach, flee, release held items, prone, stand in place |
| [Enfeeble](https://2e.aonprd.com/Spells.aspx?ID=1513) | 2 actions, creature 30 feet, Fortitude; critical success none, success enfeebled 1 until next caster-turn start, failure/critical failure enfeebled 2/3 for 1 minute |
| [Gust of Wind](https://2e.aonprd.com/Spells.aspx?ID=1550) | 2 actions, fixed 60-foot line until next caster-turn start; Large-or-smaller occupants/entrants Fortitude: critical success none, success cannot move against wind, failure prone (flying uses critical failure), critical failure pushed 30 feet/prone/2d6 bludgeoning; extinguishes small mundane flames/disperses fog; light objects affected |
| [Phantom Pain](https://2e.aonprd.com/Spells.aspx?ID=1632) | 2 actions, creature 30 feet, Will; critical success none; success full initial 2d4 mental only; failure also 1d4 persistent mental and sickened 1; critical failure sickened 2. Recovery from sickened ends spell/persistent damage; max 1 minute; nonlethal |
| [Charm](https://2e.aonprd.com/Spells.aspx?ID=1463) | 2 actions, creature 30 feet, incapacitation, Will, 1 hour; recently threatened target +4 circumstance save. Success unaffected; critical success also knows attempt; failure friendly (already-friendly becomes helpful), critical failure helpful; cannot act hostile against caster. Caster hostile action against target ends; Dismiss supported |
| [Illusory Disguise](https://2e.aonprd.com/Spells.aspx?ID=1568) | 2 actions, willing creature 30 feet, 1 hour; chosen similar-shaped appearance/voice, height within 6 inches and weight within 50 pounds; held items unchanged. +4 status to disguise Deception, adds level if untrained; no specific individual at rank 1; Dismiss |
| [Cleanse Cuisine](https://2e.aonprd.com/Spells.aspx?ID=1468) | 2 actions, 10 feet, one cubic foot food/drink; update appearance/taste and optionally remove contaminants/toxins; no nutrition increase or protection against later contamination |

Other mandatory gifts (their source links are on each bloodline page) are Light, Daze, Caustic Blast, Ignition, Shield, Figment, Detect Magic, Void Warp, Gale Blast, Scatter Scree, Electric Arc, Frostbite, Tangle Vine, Heal, Harm, Force Barrage, Tailwind, Pummeling Rubble, Breathe Fire, Thunderstrike, Hydraulic Push. School presets additionally require Message, Read Aura, Gouging Claw, Runic Weapon, Grim Tendrils, Dizzying Colors, Jump, Spider Sting. Their precise effect entries must be checked by their implementation owner before coding; this brief does not claim a complete spell-library specification. In particular, Spider Sting brings staged poison and delayed saves into the chosen Protean profile; choosing Pest Form instead brings battle-form rules. Neither may be replaced by an unprinted easy spell.

## Familiar/minion/staff minimum profiles

[Familiar](https://2e.aonprd.com/Rules.aspx?ID=2121) and [Pet](https://2e.aonprd.com/Feats.aspx?ID=5186) are one shared kernel. Tiny; level equals master; 5 HP/level (7 with Tough); AC/saves copy master before circumstance/status adjustments; no item bonuses. Perception/Acrobatics/Stealth use max(3, spellcasting attribute)+level; other skills level. Base land Speed 25 feet; low-light vision. Command: 1 action, no Nature check, two minion actions. No attack actions except Escape/Force Open. Manual Dexterity permits manipulate actions. Familiar abilities change at daily preparation but innate requirements cannot be removed. Ordinary familiar replacement is one week downtime; Witch's specific next-preparation rule overrides it. Choose grounded form to avoid requiring innate flight. A familiar does not ordinarily flank.

[Summon](https://2e.aonprd.com/Traits.aspx?ID=520), [Summoned](https://2e.aonprd.com/Traits.aspx?ID=706), [Minion](https://2e.aonprd.com/Traits.aspx?ID=653): common legal creature in unoccupied fitting space; initial casting grants immediate two actions, later Sustain grants its ordinary turn's minion allotment; no independent initiative/reactions or repeated command allotments. It vanishes at zero HP or summon expiry. Summoned creatures cannot summon, create valuables, or cast cost-bearing spells; casting a spell at least the summoning rank fails and ends the summon.

- [Phantasmal Minion spell](https://2e.aonprd.com/Spells.aspx?ID=1631): 3 actions, 60 feet, sustained; choose visible ephemeral/invisible. [Exact creature](https://2e.aonprd.com/Monsters.aspx?ID=2750): Medium force/mindless, AC13, HP4, Fort0/Ref4/Will0, fly30, Stealth8, Perception0/darkvision; no attack actions, can move/Interact but not pass solid objects. Preserve its printed immunities and resistance 5 except force/ghost touch. Minimum encounter: fetch a dropped item and return it while maintained, then disappear when not sustained.
- Wilding preset chooses [Summon Animal](https://2e.aonprd.com/Spells.aspx?ID=1694), rank1, 3 actions/30 feet/sustained ≤1 minute, common animal level −1. Minimal [Guard Dog](https://2e.aonprd.com/Monsters.aspx?ID=2924): Small, HP8/AC15, Fort5/Ref7/Will4, Speed30, jaws+6 1d4+1 piercing; Pack Attack adds 1d4 when target is in reach of at least two dog's allies. Keep full creature skills/senses/traits. The alternative [Summon Plant or Fungus](https://2e.aonprd.com/Spells.aspx?ID=1705) requires an independently verified legal level−1 profile; do not silently permit an arbitrary weak adjustment. It need not be the first selected grant.
- Boundary preset chooses [Summon Undead](https://2e.aonprd.com/Spells.aspx?ID=1706) and [Skeleton Guard](https://2e.aonprd.com/Monsters.aspx?ID=3193): level−1, Medium; HP4/AC16, Fort2/Ref8/Will2, Speed25, printed scimitar/claw/bow attacks, void healing, immunities, cold/electricity/fire/piercing/slashing resistance 5. No optional skeleton variants. This exercises a useful Fortify Summoning, not merely a decorative spell entry.
- Minimal Staff Nexus chooses a supported cantrip and Force Barrage from its book. Expend one ordinary rank-1 slot at preparation, cast via staff once, retain zero-charge cantrip access. Test absent-held-item and 24-hour expiry. A merged purchased staff is not necessary for starting equipment.

## Level-2 bounded feat policy

[Reach Spell](https://2e.aonprd.com/Feats.aspx?ID=4577) is the minimal common optional feat for Bard/Witch/Sorcerer, and mandatory Experimental/selected Unified Wizard profiles. It costs one action and increases the immediately following ranged spell's range by 30 feet (touch becomes 30 feet). It does not give range to an emanation or self-only spell. Any intervening action, free action, reaction, or turn end wastes the spellshape. Energy Ablation provides the Wizard's L2 feat. Optional feats outside this selection are rejected explicitly. Skill feats may reuse another supported common profile; they do not alter the subclass counts.

## Expected verification cases (not executed)

### Level 1 ordinary focused checks

1. Validate the four approved representatives, their exact fixed grants, traditions, ledger counts, selected curriculum slots and one or two nested choices. Keep unselected subclass inventories separate from representative acceptance.
2. Maestro Bard: Courageous Anthem buffs a Strike; Lingering Composition exercises its 1/3/4-round outcomes and focus refund; Counter Performance replaces a save result and ends an active composition. Other muse rows remain reference inventory.
3. Faith's Flamekeeper Witch: Stoke the Heart and the familiar trigger resolve once per round with chosen before/after ordering; Patron's Puppet commands the familiar without a second minion allotment; a second hex on the same turn rejects. Save/load preserves the familiar and selected hex state.
4. Battle Magic Wizard with Spell Substitution: Force Bolt and curriculum slot resolve; Substitution interruption preserves the prepared slot; a saved ten-minute swap resumes without spending an expended slot. Other school/thesis rows remain reference inventory.
5. Angelic Sorcerer: slot spells invoke Potency and selected Angelic gifts invoke Blood Magic; cantrip/focus/staff casts do not. Angelic Halo's healing bonus does not stack with Potency, and the selected focus/repertoire resources persist through save/load.
6. Angelic Heal: caster's slot heal in Halo gives higher +2 healing status bonus, not +3; ally outside aura gets Potency +1. Save/load preserves the selected slot, Halo, and Potency source.

### Level 2 deltas and continuous play

Repeat representative encounters after advancement and verify ordinary attack/DC/proficiency/HP scaling, extra rank-1 slots, knowledge/repertoire growth and feat actions. Spell rank remains 1. Faith's temporary HP rises from 2 to 3; basic focus spell damage remains unchanged. No automatic level3 signature spells or rank2 slots.

Run one serial bounded three-encounter route with Bard/Witch/Wizard/Sorcerer actors: expend ordinary slots, Sustain a minion, receive a familiar-triggered effect, save mid-round, reload, finish combat, Refocus, use ten-minute Spell Substitution, continue without daily reset, then perform daily preparations. Assert resources persist between encounters, turn/round gates resume correctly, expired effects vanish, and only intended daily resources refresh. Performance check should include several simultaneous minions/effects and bounded round count; do not claim throughput evidence until measured.

## Source questions and explicit limits

- **Deferred Hag fallback timing.** Current [Hag](https://2e.aonprd.com/Bloodlines.aspx?ID=26) says retaliation may occur before the end of the next turn, yet unused spite converts to temporary HP at the beginning of that next turn. That boundary is deferred from the selected representative roster; it is not a blocker. Keep the branch outside the shipped Angelic preset until a later ruling, rather than inventing a timing.
- **Drain Familiar preset boundary:** thesis says it functions identically to Drain Bonded Item except drawing from familiar, while item action requires the object on the caster's person. Keep the familiar on the caster for this supported preset. That permits the required thesis mechanism without resolving remote use; do not invent a 30/60-foot range or offer remote activation without further source support.
- The Wilding Steward row is reference inventory and is not part of the selected Witch representative. If that patron is selected later, Summon Animal is the first bounded grant; supporting every optional plant/fungus summon or familiar ability is not necessary. Likewise this document selects curriculum options rather than claiming all curriculum spells are supported.
- Detailed ordinary-spell implementation beyond the explicit rows remains a bounded downstream source task. Each selected fixed gift and selected curriculum spell must have an exercised path before claiming representative completion; purely informational labels do not satisfy the scope.
- This pass launched no background processes, pytest, or engine probes. All shell calls completed; one shell fetch failed because network access was unavailable, and source inspection continued through the web tool. No process remains to stop. Input/cached/output token metadata is unavailable inside this worker; supervisor should record null with this reason and refresh host-provided final counters if available.
