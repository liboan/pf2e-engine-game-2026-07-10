# Damage and equipment delivery

Archived after the reviewed 477-test equipment/Assurance checkpoint. The design and earlier delivery notes below remain historical reference; see [current state](../class-expansion-state.md) and [active queue](../queued-runtime-work.md).

## Purpose and order

Typed damage, steel shields and initial fundamental runes are implemented. The latest full suite passes 474 tests with 45 setups and 31 creature definitions; no current memory measurement was taken. The earlier shield checkpoint measured about 56.3 MiB. Feint/casting and eleven added Barbarian builds are preserved. The contracts below are reference for preserving behavior; Assurance terminal completion and periodic independent equipment review are next.

1. One typed-damage path for attacks, spells and family effects.
2. Steel shields and the initial fundamental rune grades, with actual equipment instances.

The latest implementation checkpoint is 45 setups and 474 tests; the memory measurement above belongs to the preceding shield run. Preserve deterministic rolls, saved choices, current health behavior and Bear temporary HP. The supervisor received this design from Astra without reading implementation or source content.

## Slice 1: defenses and health

Owner scope: damage.py, model.py, encounter.py, persistence.py, focused damage/persistence tests and a small fully authored living-opponent encounter. Coordinate catalog and terminal edits explicitly; no concurrent shared writers.

Astra identified three existing entry points that must share mitigation rather than changing temporary HP separately:

- `_resolve_attack_result`
- `apply_family_damage`
- `_apply_spell_damage`

Retain each caller’s normal aftermath. Use a named pre-health procedure and completion procedure, with original rolled damage plus the actual pending decision and current parent continuation. Avoid a generic event framework or a second health state machine.

Order: critical/basic-save arithmetic → immunity → weakness → resistance → qualifying Shield Block → temporary HP → ordinary health/Heroic Recovery. A single Strike/spell must obey once-per-effect defenses and defender choice for overlapping categories. The pending paired-attack ruling applies only to paired attacks.

Save the complete original DamageGroup, including each component’s tags, critical_mode and dice. The accepted serializer now retains those fields and flat-only components; preserve that coverage. Validate mitigation separately from original rolled totals. Restore a pending choice without rerolling or respending. Mark temporary HP absorption complete before later Heroic Recovery can pause; do not absorb twice.

Keep effect/condition immunity separate from damage immunity. A legal attempted mental effect is not automatically a free rejected action just because its target is immune. Specific target restrictions, such as Void Warp requiring living targets, still apply.

Proof: a fully authored living test profile with typed resistance, weakness and immunity, plus a single-effect broad-resistance choice; actual Strikes/spells and Bear temporary HP; compare uninterrupted and restored resolution; finish a healthy encounter. Do not admit published undead to get this proof cheaply.

## Slice 2: shield and fundamental equipment

Deliver this in two small checkpoints under one shared owner at a time. First finish the steel-shield fighter, stable shield identity/HP, Raise a Shield, actual Shield Block, reaction competition, breakage and saved play through a completed encounter. Then add the initial rune grades and handwrap behavior with their actual attack/AC/save/dice tests. Do not hold a working shield path unverified while wiring every rune. This changes delivery granularity, not the agreed equipment scope.

One stable item identity retains its definition, rune attachments and shield HP through held/worn/stowed/ground locations and transfers. Equipment lookup must not infer definition from instance names. Runed armor and handwraps record investment. Any armor rune grants the Invested trait; require worn and invested for potency/resilient benefits. Uninvested armor retains only its mundane armor bonus, Dex cap and penalties. [Investiture](https://2e.aonprd.com/Rules.aspx?ID=3163), [item traits](https://2e.aonprd.com/Rules.aspx?ID=3135). Higher-level test equipment is labeled as an explicit grant.

Start with steel shield only: +2 circumstance AC, Hardness 5, HP 20, Broken Threshold 10, price 2 gp. The existing melee fighter’s recorded 6 gp remainder can fund a shield, leaving 4 gp. Preserve its longsword, breastplate, Vicious Swing, Reactive Strike and Shield Block.

Raise a Shield spends one action and requires wielding an intact shield. Its benefit expires at the owner’s next turn start and ends on loss of wielding, breaking or destruction. Shield Block uses the same reaction resource as Reactive Strike. Save its real decision before shield HP, temporary HP or normal HP changes. Extend existing reaction refresh and save legality to recognize Shield Block.

Initial equipment: weapon potency +1, striking, armor potency +1, resilient and invested handwraps. Potency changes the typed item bonus on actual attacks/AC; resilient changes actual saves. Striking supplies two weapon dice; extra Vicious Swing, precision and deadly dice remain separate. Preserve the Bestial mutagen striking exception.

Proof: shield changes a hit outcome; saved Block accept/decline; shared reaction competition; breaking removes benefit; dropping/retrieval preserves shield damage. A separate explicit-grant encounter demonstrates attack/AC/save and weapon-dice changes and completes through public commands. Do not claim constructor snapshots as played equipment coverage.

Mixed Shield Block uses the corrected source-reviewed convention below. The original scalar “same damage to both” convention missed ordinary object immunities and is superseded.

1. Apply actor IWR. Block is eligible only if physical damage remains from an attack and other requirements hold.
2. Let D be the remaining attack total, V its subtotal not immune to the ordinary steel shield, and H shield Hardness.
3. Actor damage is max(0,D−H). Shield HP loss is max(0,V−H). Apply actor temporary HP afterward; it never protects the shield. Do not subtract Hardness or actor IWR again.

The allocation is an explicit GM convention: Hardness first covers shield-vulnerable damage, then unused allowance covers remaining attack damage for the actor. Preserve original and post-IWR components plus distinct Block prevention/actor/shield totals. No extra allocation choice or object simulator is needed.

Ordinary steel object immunities include mental, poison, spirit, bleed, vitality, void and whole nonlethal attacks. Use resolved attack intent, not merely the printed nonlethal weapon trait when a lethal attack was selected. Precision and critical hits are not generic object immunities; do not copy special hazard immunities. Spirit needs no soul model for an ordinary steel shield because printed immunity settles it.

Examples after actor IWR, Hardness 5: 8 slashing + 4 fire produces 7 actor/7 shield damage; 8 slashing + 4 mental/poison/spirit produces 7 actor/3 shield damage; 3 slashing + 8 poison produces 6 actor/0 shield damage. A 12-piercing hit against 10 temporary HP becomes 7 after Block: shield HP 20→13, character temporary HP 10→3, ordinary HP unchanged. Basic-save damage does not qualify merely because it is physical.

This corrects an incomplete prior convention; printed object immunities remain authoritative. Sources checked by Astra: [Object Immunities](https://2e.aonprd.com/Rules.aspx?ID=2161), [Shield Block](https://2e.aonprd.com/Feats.aspx?ID=5212), [damage/HP](https://2e.aonprd.com/Rules.aspx?ID=2263), [Paizo FAQ](https://paizo.com/pathfinder/faq).

## Massive Damage and temporary HP

The source check identified a health-boundary error after the accepted typed-damage checkpoint. Use damage after actor defenses and Block, before temporary HP, to compare with twice maximum HP. Use the post-temp remainder only for ordinary HP subtraction. The narrow health helper now takes `damage_taken` separately and passes 27 focused checks, including a hit entirely absorbed by temporary HP. Live callers and saved health validation now use both amounts. A real family-context packet after public Rage proves 46 incoming damage against maximum HP 23 kills even though 4 temporary HP leave only 42 ordinary HP damage. This is labeled shared-procedure evidence, not a public ordinary-attack scenario. No new user ruling is needed. [Massive Damage](https://2e.aonprd.com/Rules.aspx?ID=2332), [Temporary HP](https://2e.aonprd.com/Rules.aspx?ID=2321).

## Published opponents remain staged

Skeleton Guard additionally needs forceful/sweep, mental/effect immunity, void healing and appropriate Heal interaction, and undead destruction at zero HP even following nonlethal damage. Zombie Shambler additionally needs permanent slowed, no reactions, prior successful Fist eligibility for Grab without MAP and maintenance rules, and grabbed/restrained-only Bite with ordinary MAP. These are separate bounded opponent slices after their prerequisites work.

## Evidence and working model

Implementation owners run focused tests throughout each slice. One broad suite follows a coherent checkpoint. Representative complete public encounters and saved choices establish playability. Sol reviews periodically, with actual Python execution and source checks, rather than after each small edit. Keep memory bounded and clean only attributable idle/completed worker processes. Report sources, exact test evidence, limitations and ownership release; the supervisor maintains durable state and token accounting.
