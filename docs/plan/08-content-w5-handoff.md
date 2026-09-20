# Accepted W4 → fresh W5 handoff

Read [working model](04-delivery-and-checks.md) and [ACTIVE](../work-log/ACTIVE.md). Accepted W4 code/tests: `1f4d09315a86f6fc9d71e51eef607e83eb68967c`; evidence child `ed8e86fe4d02b4e4e3bace40918d3fc3f9b86c8d`. Published delivery ref and exact baseline live in ACTIVE. W2 `a58424b0f9e0e515e302c149500624580c925780` and W3 `832d44b6816cd42d2c9cc9d3cfc2753d906774d1` remain ancestors.

## Delivered and deferred

W4 delivers eleven genuinely new feats: Exacting Strike, Double Slice, Twin Takedown, Twin Feint; Reactive Shield, Point Blank Stance, Overextending Feint, You’re Next; Energy Ablation, Domain Initiate and Cackle. Existing W3 Widen is not a new name. Dangerous Sorcery and the illegal Divine Angelic Sorcerer/Breathe Fire alternative were excluded. No quota-driven replacement is needed. Next planning should broaden new L1 feats and worthwhile spell/item reuse, not repeat names as new delivery.

Preserve finite menus, sixteen selected L1/L2 representatives, eleven Barbarian builds, combat-only Ranger, horizontal-only Monk, above-level equipment labels and existing GM conventions. Vertical terrain/High Jump, stable-unconscious-at-zero positive damage, pending paired mixed-resistance allocation and pre-first-turn Surprise Attack remain excluded/pending. No universal poison/minion/rules framework.

## Actual reuse and test pointers

Owner-reported offense seams: `src/pf2e/w4_offensive.py` typed commands/routing; `paired_strikes.py` ordered continuation and refreshed second-Strike menu; `Encounter._start_w4_exacting_strike` ordinary Strike pipeline. Double Slice and Twin Feint use two actions/same target; Double Slice has non-agile second-Strike penalty, Twin Feint second-Strike off-guard; Exacting Strike preserves its reviewed Press/result-choice behavior. Public admissions in `w4_offensive_content.py` via `content.py`. Analogues: `tests/test_w4_offensive_content.py`, `test_w4_offensive_independent_review.py`.

Defense seams: `martial_defense.py` stance/damage projection; `skill_actions.py` Feint result choices and reaction Demoralize; narrow `encounter.py`/`model.py`/`persistence.py`/`terminal.py` integrations. Overextending Feint is a persisted post-success choice; Reactive Shield must survive special-Strike continuations and reject forged saved attacks. Analogues: `tests/test_w4_defensive_content.py`, `test_w4_defensive_independent_review.py`.

Caster fixtures: `wizard_battle_magic_level_2_energy_ablation`, `warpriest_c_domain_initiate_weapon_surge`, `faiths_flamekeeper_witch_level_1_cackle`. Relevant files: `spellshape.py`, `family_casting.py`, `witch.py`, `w4_caster_content.py`, `spells.py` and runtime/save/terminal seams. Energy Ablation finite selected resistance is independent of spell damage type; ineligible cast wastes its marker. Weapon Surge requires a held weapon and reviewed consumption/expiry. Cackle spends a Focus Point, respects once-per-turn and one-Hex-per-turn, preserves Stoke sustain and Restored Spirit. Analogues: `tests/test_w4_caster_feats.py`, `test_w4_caster_independent_review.py`, W3 caster tests.

Last accepted public probe: `tests/test_w4_assembled_independent_review.py` (five tests), continuous cross-family play plus terminal held-item/energy-type/Cackle choices, caster and defensive save/load, adverse checks and victory-save expiry. Source pointers live in W4 content files; owner notes under `docs/work-log/w4-*.md` are scoped history and may contain pre-repair wording. Final independent tests/accepted contracts take precedence. Planner must verify actual helper names/signatures and current source rules before proposing dependencies; coordinator has not inspected implementation.

## Environment and acceptance evidence

Verified team environment: `/Library/Frameworks/Python.framework/Versions/3.11/bin/python3` (3.11.1), pytest8.4.2, `PYTHONPATH=src`, `/opt/homebrew/bin/timeout`. Reverify once in each assigned fresh cwd. Focused command: `PYTHONPATH=src /opt/homebrew/bin/timeout 30s /Library/Frameworks/Python.framework/Versions/3.11/bin/python3 -m pytest -q <selection>`. Canonical: `PYTHONPATH=src /Library/Frameworks/Python.framework/Versions/3.11/bin/python3 tools/integration_checkpoint.py`.

Accepted W4 final canonical: 1,496 tests, 7.53s pytest /7.867s runner, peak88,342,528 bytes; compile/diff/test exits0, accepted117/94, staged24/12, save18. Independent repaired-caster/assembled focused gate26/26 in0.47s at exact accepted SHA. Owner reports task-owned processes exited; no global cleanup claim. Fresh tasks have no public probe until they run one. No broad baseline rerun needed merely for planning; inspect relevant implementation/source/tests and use bounded probes only when a consequential assumption requires evidence.

W5 planner returns compact named batches/new-versus-existing distinctions, real reuse/proportional refactors, file/API ownership/dependencies and a few source-grounded acceptance cases. Fresh Luna implements and fresh Sol independently verifies all assumptions. No old transcripts or exhaustive inventories. Reuse planner only for substantial unresolved decisions.
