# Current status

## Delivered — 2026-09-15

**S1–S3 are implemented, independently reviewed, and available for local play.** A person controls every side through Python calls or a numbered terminal interface. There is no browser or server.

```sh
.venv/bin/python -m pf2e play s3 --seed 13
```

[README](README.md) contains installation steps, the Python API example, controls, and exact supported content.

## Delivered — S3i interaction expansion — 2026-09-15

The catalog and terminal expose eight additional S2 and eight additional S3 setup IDs, bringing the fixed catalog to 21 setups while retaining exact-definition admission. The additions use the Fleet/shortsword Fighter and elite Guard Dog in S2, plus a rapier Fighter in S3. Two S3 setups use a 15-by-5 grid to test range and emanation boundaries. All encounters remain manually controlled.

All 16 complete encounter routes passed in five focused scenario modules. Independent review accepted all 16 with no remaining scenario omissions or P0/P1 findings. The combined five-module selection passed 18 tests in 0.41 seconds (wrapper 0.6245 seconds; child peak RSS 45.70 MiB). Representative public-terminal checks also passed for an S2 shortsword Strike and a 65-foot S3 shortbow Strike, each followed by Save, Load, and clean exit.

The shared outcome policy ends an encounter when a team has no conscious, living combat-capable actor; a downed PC remains available for rescue while an ally can continue. Finished saves use the same predicate. A focused regression covers a spell-triggered Reactive Strike saved at the nested Hero Point choice; a critical result disrupts Heal without repeating its paid actions or slot.

## What works

- Prototype and reviewed starter encounters, plus a mixed melee fighter / bow fighter / warpriest party against three Guard Dogs.
- Turns, movement, attacks, reactions, equipment, ammunition, PC knockout/recovery, Hero Points, and the selected rank-1 spells and effects.
- Sixteen additional source-backed encounters for interactions among movement, MAP, weapon traits, flanking, Pack Attack, reactions, recovery, range, cover, healing, and spell effects.
- A team remains active while it has a conscious, living combat-capable actor. Unconscious PCs remain in state and can be rescued by an active ally; finished outcomes and load validation use the same rule.
- Individual supplied dice for checks and damage, or seeded automatic rolls. Saves preserve pending choices, spent resources, and the next die. Queries, rejected commands, and exhausted scripts do not silently consume or substitute rolls.
- Complete fights through both the public API and actual terminal, including saved spell/reaction decisions and knockout → Heal → Stand → retrieve.

## Verification

- **The pre-S3i baseline had 179 passing tests, including the shared S2/S3 memory guard.** Pytest exited **0** with **211 passed in 0.69 seconds** (wrapper wall time 0.912 seconds). The `/usr/bin/time -l` wrapper then exited 1 because the sandbox denied `sysctl kern.clockrate`; it returned no memory figures, so full-suite peak RSS and footprint are unavailable. The suite was not rerun.
- All 16 added encounter routes passed individually across five focused modules. The combined five-module selection passed **18 tests in 0.41 seconds** (wrapper 0.6245 seconds; child peak RSS **45.70 MiB**). This is scoped to the five-module selection, not the full suite.
- The central catalogue selection passed **6 tests** and the focused shared reaction/persistence/outcome/S3 casting selection passed **31 tests**:
  ```sh
  .venv/bin/python -m pytest -q tests/test_interaction_catalog.py
  .venv/bin/python -m pytest -q tests/test_spell_reaction_persistence.py tests/test_s2_reactions.py tests/test_s2_encounter.py tests/test_s3_core.py
  ```
- The two admitted-scope S2 and S3 terminal summary checks passed.
- Independent review passed 172 frozen-snapshot tests, decisive rule/save/resource boundaries, and two complete mixed-party fights with different seeds and routes. No P0/P1 implementation defect was found.
- A representative S3 startup/initiative/Guidance/Divine Lance/choice sequence measured **2.6444 ms median / 2.8115 ms p95** over 500 runs on Python 3.11.1, macOS arm64. This measures that small local sequence, not arbitrary large encounters.
- Compilation, `git diff --check`, and 35 local Markdown links/anchors across 11 active files pass. Archive inventory remains 27 preserved payload files plus its manifest.

## Scope and pending ruling

These are fixed catalogued builds and encounters on bright, flat **7×5 and 15×5 maps**, with manual control of all sides. Modified/ad hoc setups are rejected. Read Aura is unavailable during encounters; Shield Block is inactive with these shield-free loadouts. This is not whole-class or whole-book coverage.

The 15×5 range encounter now exercises shortbow range increments through 65 feet; the 15×5 emanation encounter checks the 30-foot Heal boundary. These supported cases do not imply arbitrary map sizes or custom setups.

**P1 user ruling remains pending:** whether further lethal damage to a stabilized, unconscious character at 0 HP causes a fresh knockout. Until that ruling is accepted, the engine rejects **any positive damage** to a stable unconscious PC at 0 HP, including nonlethal damage, before spending actions or dice. This explicit unsupported boundary does not block the delivered encounter scope.

## Next work and preservation

The baseline S3 implementation and the requested test-memory optimization are complete. Both reported Python processes were identified as stale S3 pytest runs, received SIGTERM, and were verified absent. The one-time cleanup also stopped an attributable Playwright MCP pair; no Chrome process was present, and uncertain/shared services were retained.

Dynamic S2/S3 terminal tests share a test-only capture limit that fails visibly instead of retaining unlimited output. That memory guard did not change production rules. The pre-S3i 179-test run measured **47.2 MiB peak RSS** and **37.5 MiB peak footprint**. The historical multi-gigabyte growth was not reproduced, so its exact cause remains unproven. The final read-only check confirmed all four cleaned PIDs remained absent, no repository pytest process remained, and whitespace checks passed. One older Python process using approximately 7 MiB was left untouched because ownership by the completed tests was unproven.

S3i is integrated and verified. Broader content remains a future increment; the [plan index](docs/plan/01-product-and-interface.md) describes the later stages.

Earlier uncommitted planning/archive work is preserved. Baseline HEAD remains `115a55d844021c479a2b9d140bc0e7bf92aee40c`; no commit or merge was made, and other worktrees remain out of scope. Completed subagent usage is recorded in the [durable work log](docs/work-log/README.md).
