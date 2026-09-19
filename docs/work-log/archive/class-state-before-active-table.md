# Archived: Class expansion: current delivery state

Historical snapshot. Use [ACTIVE](../ACTIVE.md) for current ownership and next action. Original accounting figures below retain their old event-token source; raw-request reconciliation includes compaction and is recorded separately in the ledger.

## Summary

The latest verified checkpoint has **48 accepted setups, 32 accepted creature definitions and 551 passing tests in 2.07 seconds**. The same run measured **2.374516 seconds wall time and 63,209,472 bytes (60.3 MiB) peak child memory**. Thief Rogue is accepted in its fixed level-1 build. The shared spell-condition bugs are corrected and tested.

The approved goal is **representative playable builds across all sixteen Player Core 1/2 classes**, level 1 first, then level 2, followed by a generalization review. Every selected option must be legal and correct; unused subclasses and nested choices are deferred. Preserve the eleven accepted Barbarian builds. The [plan](../../plan/06-class-and-content-expansion.md) lists the selected roster and small shared domain/spell/item menus.

## Accepted play

The staged Angelic first-cast runtime also passed review: public cantrip and saved spontaneous Heal, exact rank pool spending, Potency and Blood Magic across area/single-target paths, saved replacement/expiry, and atomic depleted/illegal requests. The initial casting checks are now supplemented by two complete public fights: Halo healing after real injury (21→5, then Heal for 14 to 19), and later-initiative Fear with a saved Reactive Strike during flight. Terminal, Hero decisions and source-turn expiry save checks also pass. This build still remains outside the accepted picker until its selected remaining spells and recovery work.

- Original S1–S3 and the first sixteen added interaction encounters remain accepted.
- The level-1 Thief has actual Deception/Surprise/Sneak, Dexterity damage and saved Nimble Dodge across weapon, spell and reaction attacks. Two complete runs cover its canonical fight through API and terminal; other fixtures provide targeted continuation evidence.
- Bear, Cat, Frog and all eight Dragon Barbarian choices complete public fights and saved Rage/attack choices. The Dragon typed-defense interaction also passes.
- Trip, Grapple, Escape, Demoralize and Feint work through public commands. Feint's scope/expiry/consumption and the user's Escape-preserves-opening ruling are tested.
- The current Warpriest uses one authoritative casting-resource ledger. Saved slot/Heal choices and 30-foot versus 35-foot Heal range boundaries pass. This is a fixed casting slice, not whole Cleric completion.
- Typed Strike/spell/family damage shares defenses, temporary HP and health. Saved defense/Hero choices apply once. Damage diagnostics distinguish completed fights from targeted family-context sequences.
- Steel shields have actual Raise/AC/expiry, saved Block/Decline, reaction competition, breakage, damaged drop/retrieve/save and completed fights. Terminal behavior is accepted in the 458-test checkpoint.
- Fighter's mandatory level-1 class package is source-checked. Assurance(Athletics) now works through public Trip/Grapple/Athletics Escape and numbered terminal choices. A saved complete duel passes; independent public Guidance/MAP sequences and source review also pass.
- Initial weapon/armor potency, striking, resilient and invested handwraps have six admitted test setups. Worn/invested gates, stowed spare armor, Vicious Swing extra dice and saved equipment identity pass. Higher-level equipment is explicitly granted for these tests.
- Massive Damage uses post-defense/Block damage before temporary HP. A real family-context packet after public Rage proves 46 damage against maximum HP 23 kills despite 4 temporary HP leaving 42 ordinary HP damage. This is explicitly not a public ordinary-attack claim.

## Active implementation

| Slice | Owner and current evidence | Still needed |
|---|---|---|
| Runic Weapon prerequisite | Luna owns stable physical weapon transfer/attack resolution after the 551-test Fear checkpoint | Actual transfer and saved item selection, followed by spell enchantment |



The completed rune slice corrects the Feint fighter's trained Deception +2→+3 and training/money notes; affected Feint checks pass. These are data corrections, not new class features.

## Selected but not yet accepted

| Class | Representative | Starting evidence |
|---|---|---|
| Sorcerer | Angelic | Actual spontaneous/focus/Halo/Fear paths and two completed fights; Runic Weapon, Light and local recovery remain |
| Champion | Justice / Lay on Hands / Desperate Prayer | [Selected source packet](../justice-runtime-work.md) ready, including six proposed encounter routes; follows Sorcerer focus/recovery |
| Ranger | Precision / Hunted Shot | Staged helper tests; actual prey, range, damage and paired runtime still needed |
| Monk | Monastic Weaponry / kama and fist | Staged helper tests; actual Powerful Fist/Flurry/weapon interactions still needed |
| Investigator | Forensic Medicine / Known Weaknesses | Source brief; medicine, stratagem and examination behavior needed |
| Swashbuckler | Braggart / Flying Blade | Source brief; panache, bravado, finisher and thrown behavior needed |
| Bard | Maestro | Source brief; spontaneous/composition/reaction/focus behavior needed |
| Druid | Storm / Animal Empathy | Source brief; prepared/focus/nature and actual weather behavior needed |
| Oracle | Life | Source brief; cursebound/focus/healing and damage redirection needed |
| Witch | Faith's Flamekeeper / Patron's Puppet | Source brief; actual familiar, hex, Sustain and preparation needed |
| Wizard | Battle Magic / Spell Substitution | Source brief; legal books/resources and substitution needed |
| Alchemist | Bomber / Quick Bomber | Staged resources and item helpers; finite selected formula activations/lifetimes still needed |

Existing Iomedae Warpriest additionally needs advertised Read Aura/Sure Strike and remaining selected declarations/targeting before broader acceptance. Definitions and helper counts are not class completion. The class research inventories remain references, not requirements to implement unselected rows.

## Deferred choices and relevant decisions

Additional Barbarian animals/instincts, other Rogue rackets, extra doctrines, bloodlines, schools/theses, patrons, causes, mysteries, research fields and domains are not milestone prerequisites. The Animal maneuver/Bull research is archived for potential shared-mechanic value. Preserve accepted variants; do not remove them to match a narrower target.

The initial shared domain menu is zeal/Weapon Surge and healing/Healer's Blessing, only through legal grants. The Bomber's concrete eight level-1 plus two level-2 formulas and selected caster menus are in the plan; neither expands recursively to a whole eligible catalog.

- Paired broad resistance still matters for Monk/Ranger.
- Reload-0 bow manipulation still affects an admitted Fighter choice and the selected Ranger.
- Positive damage at already stable unconscious zero HP remains explicitly unsupported.
- Hag fallback timing is deferred with Hag, not a blocker.
- Escape preserving Feint is resolved and tested.

## Acceptance order and working model

Runes/Assurance and the selected Thief are complete. Continue Angelic Sorcerer with narrow Warpriest cleanup, and Justice Champion. Complete the other selected level-1 classes through actual encounters and saves, then actual level-2 progression and selected feats, then the planned Astra simplification review.

One owner edits shared model/encounter/persistence files. Independent family work uses distinct files and an explicit small integration contract. Local focused checks run frequently; broad integration and Sol play/source review happen at meaningful checkpoints. Keep test resources bounded and clean only attributable worker processes. Current owners and exact next steps are in the [queue](../queued-runtime-work.md); actual per-run tokens are in the [ledger](../agent-runs.json).
