# Current status

## Delivered baseline — S1–S3 interaction expansion (historical checkpoint) — 2026-09-15

The local Python engine has a numbered terminal interface and no browser or server. The accepted fixed-build catalog has **21 setups**, including **16 added S2/S3 interaction encounters**. All sixteen encounter routes passed their focused modules and independent review. The committed `engine-only` baseline (`185e52b`) passed **211 full-suite tests**.

All sides are manually controlled. The fixed builds cover the existing low-level Fighter, Warpriest, Guard Dog, and selected spell rules. They are not whole-class or whole-book support. Start the accepted S3 setup with:

```sh
.venv/bin/python -m pf2e play s3 --seed 13
```

[README](README.md) has installation, controls, and the accepted catalog's boundaries. The 21/211 figures above are this pre-S3i checkpoint, not the current S3i working count.

## Current work and recovery

[Current work and recovery](docs/work-log/ACTIVE.md) is the single source for current verified counts, task/session ownership, dependencies, blockers, last executable checkpoints, and next actions. The [work-log index](docs/work-log/README.md) links to evidence and usage records. Read the active table first after interruption or compaction.

## Completed work — S3i roster generalization

The target remains one selected representative build for each of the 16 Player Core and Player Core 2 classes. Each representative needs its mandatory grants and selected rules behavior, an actual encounter, and saved continuation evidence. Every printed subclass and nested option is not required; unselected source inventories are reference material rather than delivery backlog. Feat, spell, school, domain, and Alchemy menus remain deliberately small. Explicitly granted, labeled above-level fundamental-rune test gear does not change character level. See the [scope and acceptance plan](docs/plan/06-class-and-content-expansion.md).

The authorized generalization and simplification phase is complete. It accepted three coherent groups: shared spell-save provenance across ten paths; finite preparation routing and validation across Wizard, Druid, Witch, and fixed preparations; and existing finite `BombFacts` adoption for two admitted bombs. Relevant defects were repaired and independently reviewed. All sixteen selected level-1 representatives are now accepted, including Counter Performance Maestro Bard and horizontal-only Monastic Weaponry Monk, at the 1,255-test canonical checkpoint. Final counts, compile/diff cleanliness, saved-continuation evidence, active level-2 bundles and supported boundaries are recorded in [ACTIVE](docs/work-log/ACTIVE.md).

Further recipient progression is deferred. The common save path covers the major risk, but remaining eligibility, completion, and rider behavior differs, so a generic iterator would mostly relocate branches. Revisit it only with a new actual adopter or demonstrated drift. Paired-policy and turn-walk work remain optional; poison, minion, and universal rules frameworks, unrelated content expansion, and wholesale rewrites remain outside scope.

Selected level-1 representatives are: existing Fighter; Bear, Cat, Frog and eight Dragon Barbarian builds; Iomedae Warpriest; Thief Rogue with Nimble Dodge; Precision Ranger with Hunted Shot; Monk with Monastic Weaponry (kama/fist); Justice Champion of Iomedae with Lay on Hands and Desperate Prayer; Forensic Medicine Investigator with Known Weaknesses; Braggart Swashbuckler with Flying Blade; Bomber Alchemist with Quick Bomber; Maestro Bard; Storm Druid with Animal Empathy; Life Oracle; Angelic Sorcerer; Faith's Flamekeeper Witch with Patron's Puppet; and Battle Magic Wizard with Spell Substitution. Shared Zeal/Weapon Surge and healing/Healer's Blessing domains are used only where legally granted. The approved roster preserves eleven accepted Barbarian builds and does not expand into every Animal, Bull, or other instinct.

The following accepted slices retain source-checked mandatory features and public evidence: the S1–S3 interaction encounters; eleven fixed Barbarian builds; Thief Rogue with Nimble Dodge; Steel Shield, initial fundamental runes, and Assurance; typed-damage defenses; and Feint and Warpriest casting. The [current work and recovery page](docs/work-log/ACTIVE.md) and its linked packets hold the detailed test, encounter, save/load, terminal, and performance evidence. Definitions and source packets alone never establish playable class coverage.

The Angelic Sorcerer level-1 first-cast setup is now admitted under the stable
`sorcerer_angelic_first_cast` ID. Its selected Human sheet and legal
item-capable ally have public encounter, saved continuation, and terminal
evidence for the bounded Halo/Blood Magic, Light, Heal, Fear, Runic Weapon,
focus, and spontaneous-resource paths. This is one curated setup; broader
Sorcerer options and offensive Heal against undead remain unsupported.

The Braggart Swashbuckler setup is now admitted under the stable
`staged_braggart_swashbuckler_vs_guard_dog` ID. Its selected Flying Blade
dagger play has public encounter, terminal, save/load, range-boundary, and
physical recovery evidence. Other Swashbuckler styles, weapons, returning
weapons, projectile paths, and level-2 options remain unsupported.

The Forensic Investigator setups `investigator_forensic_vs_two_guard_dogs`
and `investigator_forensic_healing_vs_ally` are now admitted with their stable
save IDs. The selected level-1 build has source-reviewed Devise, Known
Weaknesses, Battle Medicine, Forensic Acumen, On the Case, Skill Stratagem,
and Streetwise encounter/save/terminal evidence. Broader Investigator
methodologies, settlements, bribes, and level-2 options remain unsupported.

The Precision Ranger combat setup is now admitted under the stable
`staged_ranger_precision_bow` ID. The selected level-1 Versatile Human sheet
has Fleet movement, a Dexterity-based finesse fist attack with Strength damage,
and public combat, terminal, and save/load evidence for Hunt Prey, Precision,
ordinary shortbow Strikes, and Hunted Shot. Seek, Track, Forager, and
exploration procedures are recorded non-gating sheet facts and remain outside
this combat-only acceptance.

Historical note: an earlier public Demoralize → Void Warp probe exposed a frightened 2 omission in the dog's Fortitude save. Corrected caster attack, spell DC, and target-save condition inputs and saved validation are now tested in the accepted Thief checkpoint.

## Open rules questions and supported boundary

Three narrow limits remain active: when paired attacks commit broad resistance to a damage type, whether drawing an arrow for a reload-0 bow Strike counts as manipulation, and positive damage to a stable unconscious PC at 0 HP. Hag Sorcerer's Retributive Spite fallback timing is deferred and does not block the selected representative roster.

Positive damage to a stable, unconscious PC at 0 HP remains unsupported, including nonlethal damage. This boundary stays explicit until separately ruled on.

## Ongoing delivery direction

Keep accepted roster behavior and its boundaries intact. A coherent group keeps one Terra owner across runtime, save/load, terminal, and tests; Sol reviews each complete runnable group, while Astra resolves substantial design or rules questions. Focused executable checkpoints stay frequent, and ordinary repair remains with the same owner and reviewer. Current ownership and the next executable action remain in [ACTIVE](docs/work-log/ACTIVE.md).

The [durable work log](docs/work-log/README.md) links to run evidence and token records.
