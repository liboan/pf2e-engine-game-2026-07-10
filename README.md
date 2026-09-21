# PF2e Python engine

This is a local Python PF2e engine with a numbered terminal interface. You choose actions for every actor on both teams and resolve each choice; opponent turns are not automated.

## Project state and scope

The approved S3i roster remains in scope: one selected representative build for each of the 16 Player Core and Player Core 2 classes, with complete supported rules behavior and actual encounter/save evidence for every accepted slice. The authorized generalization phase is complete: shared spell-save provenance now serves ten paths; finite preparation routing and validation serve Wizard, Druid, Witch, and fixed preparations; and the existing finite `BombFacts` model serves two admitted bombs. The changes were adopted by real callers, replaced paths were removed, relevant defects were repaired, and an independent review completed. Every printed subclass and nested option remains out of scope, and feat, spell, school, domain, and Alchemy menus stay deliberately small. Explicitly granted, labeled above-level fundamental-rune test gear is allowed. See the [approved roster and scope](docs/plan/06-class-and-content-expansion.md).

Further recipient progression is deferred until a new actual adopter or demonstrated drift justifies it: common save handling already covers the major risk, while remaining eligibility, completion, and rider behavior differs. Paired-policy and turn-walk work are optional. Poison, minion, and universal rules frameworks, unrelated content expansion, and wholesale rewrites remain outside scope.

The [current work and recovery page](docs/work-log/ACTIVE.md) is the source for verified working counts, accepted and partial roster state, active owners, dependencies, blockers, last executable checkpoints, and next actions. [STATUS](STATUS.md) summarizes delivered evidence and current limits; it does not replace that recovery table.

The pre-S3i `engine-only` baseline (`185e52b`) is historical: 21 supported setups, 16 accepted added interaction encounters, and 211 passing full-suite tests. It remains a reference checkpoint, not the current S3i working count.

Historical note: an earlier public Demoralize → Void Warp probe exposed a frightened 2 omission in the dog's Fortitude save. Corrected caster attack, spell DC, and target-save condition inputs and saved validation are now tested in the accepted Thief checkpoint.

## Run locally

Use Python 3.11 or newer. From the repository root:

```sh
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e .
python -m pf2e play s3 --seed 13
python -m pf2e play s2_fleet_diagonal_assault --seed 13
python -m pf2e play s3_long_lane_crossfire --seed 13
python -m pf2e play sorcerer_angelic_first_cast --seed 13
python -m pf2e play staged_braggart_swashbuckler_vs_guard_dog --seed 13
python -m pf2e play investigator_forensic_vs_two_guard_dogs --seed 13
python -m pf2e play staged_ranger_precision_bow --seed 13
```

Each run starts with initiative Hero Point choices; resolve each before the first turn. Choose `Quit` in the menu to exit.

The S2 and S3 catalogs each add eight named interaction encounters, bringing the fixed catalog to 21 setups. They reuse the supported low-level Fighter, Warpriest, Guard Dog, and rank-1 spell rules, with Fleet/shortsword Fighter and elite Guard Dog variants in S2, and a rapier Fighter in S3. The encounters cover movement, MAP, weapon traits, flanking, Pack Attack, reactions, knockout/recovery, ranged attacks, cover, spell choices, healing, and effects. All sides remain manually controlled. Two S3 encounters use a 15-by-5 open grid for range and emanation boundaries; the other encounters use a 7-by-5 grid. Modified or ad hoc setups are still rejected.

The original S3 setup remains a level-1 melee Fighter M, shortbow Fighter R, and Iomedaean Warpriest C against three Guard Dogs. Its selected actions and rank-1 Heal, Divine Lance, Void Warp, Guidance, Stabilize, and Light spells are supported. Read Aura remains deferred because its one-minute cast is outside encounter play and is no longer part of this fixed Warpriest preparation. Shield Block remains on the sheets but cannot be used with these shield-free loadouts. This is a narrow content boundary, not support for every PF2e class, creature, or action. Positive damage to a stable, unconscious PC at 0 HP, including nonlethal damage, remains unsupported pending a product ruling.

An encounter ends when a team has no conscious, living combat-capable actors. If no team retains one, the encounter ends with no winner. An unconscious PC remains in the encounter and can be healed while a conscious teammate keeps their team active. A nonlethal PC knockout can therefore end a one-on-one fight without marking that PC dead or defeated.

The terminal accepts short aliases `s1`, `s2`, and `s3`, as well as catalogued setup IDs such as `s2_fleet_diagonal_assault` and `s3_long_lane_crossfire`.

The curated `sorcerer_angelic_first_cast` setup admits one level-1 Human Angelic
Sorcerer sheet with its selected divine repertoire, Angelic Halo and Blood
Magic, plus a legal item-capable ally. Its bounded play covers Light, Heal,
Fear, Runic Weapon, focus and spontaneous resources, saved choices, and the
existing recovery/carry path. Broader Sorcerer and Angelic options remain
outside scope, including offensive Heal against undead; above-level granted
gear used by diagnostic fixtures remains explicitly labeled.

The curated `staged_braggart_swashbuckler_vs_guard_dog` ID remains stable for
existing saves and now selects the level-1 Braggart Swashbuckler from the normal
catalog. Its admitted play covers Braggart Panache, Tumble Through, ordinary
and first-increment Flying Blade dagger Strikes, Confident Finisher, physical
dagger landing/recovery, and saved choices. Other styles, weapons, returning
weapons, projectile paths, and level-2 Swashbuckler options remain outside scope.

The curated `investigator_forensic_vs_two_guard_dogs` and
`investigator_forensic_healing_vs_ally` IDs now select the level-1 Forensic
Investigator from the normal catalog. Their bounded play includes Devise a
Stratagem, Known Weaknesses, Battle Medicine, Forensic Acumen, Pursue a Lead,
Skill Stratagem, and the authored Streetwise Recall/Gather paths with saved
results. Other Investigator methodologies, settlements, bribes, and level-2
options remain outside scope.

The curated `staged_ranger_precision_bow` ID now selects the level-1 Precision
Ranger from the normal catalog. Its combat-only play covers Fleet movement,
Hunt Prey, Precision damage, ordinary shortbow Strikes, Hunted Shot, range,
reactions, Grabbed reload-0 handling, and saved continuations. Seek, Track,
Forager, and exploration procedures remain outside this accepted combat slice.

`--seed` selects repeatable automatic rolls. For controlled checks, the public `Encounter.start(setup, rolls=...)` API accepts individual die faces in draw order. For example, `rolls=(20, 19, 20, 4, 1)` on `S2_PC_DUEL_SETUP` supplies Fighter A's and Fighter B's initiative d20s, then a Strike d20, its fist d4 damage roll, and the next Strike d20. Queries and rejected commands do not consume faces. Saves preserve the sequence cursor, so `Encounter.load(path)` resumes at the next face. If a requested roll exhausts the sequence, the action is rejected and the cursor stays put; the engine does not fall back to random dice.

## Tests

The 16 added encounter routes are split across five focused modules so a changed rule family can be checked without running every fight. Run one named test while iterating, the relevant module after a coherent change, and the full suite at an integration checkpoint:

```sh
.venv/bin/python -m pytest -q tests/test_s2_interaction_encounters.py tests/test_s2_interaction_recovery.py tests/test_s3_interaction_encounters.py tests/test_s3_interaction_effects.py tests/test_s3_interaction_reactions.py
.venv/bin/python -m pytest -q
```

Acceptance also requires the checked-in quality and size gate. Install its
pinned dependencies and the worktree-local pre-push hook, then run the same
complete checkpoint used by CI:

```text
.venv/bin/python -m pip install -r requirements-quality.txt
.venv/bin/python tools/install_git_hooks.py
PYTHONPATH=src .venv/bin/python tools/integration_checkpoint.py
```

See [code-size and quality enforcement](docs/quality-enforcement.md) for the
measured budgets, trusted-policy ratchet, hook safety, and consolidation-target
process.

## Current direction

- [Product and interface](docs/plan/01-product-and-interface.md)
- [Engine and content](docs/plan/02-engine-and-content.md)
- [Rules and stages](docs/plan/03-rules-and-stages.md)
- [Delivery and checks](docs/plan/04-delivery-and-checks.md)
- [Interaction encounters](docs/plan/05-interaction-encounters.md)
- [Class and content expansion](docs/plan/06-class-and-content-expansion.md)

## Project records

- [Current status](STATUS.md)
- [Current work and recovery](docs/work-log/ACTIVE.md)
- [Work log](docs/work-log/README.md)
- [Archived browser and contract plan](docs/archive/2026-09-15-browser-and-contract-plan/ARCHIVE.md)
