# Accepted W5: next-team checkpoint

W5 is complete at accepted integration **`f6639978cbc5fe09bd927de2a793256773fd2f7a`**. [ACTIVE](../work-log/ACTIVE.md) carries the publication receipt; [acceptance evidence](../work-log/archive/content-w5-accepted.md) and [working model](04-delivery-and-checks.md) govern recovery. No further milestone is authorized. Preserve current checkouts and use a fresh team for the next separately authorized substantial milestone.

## Delivered versus deferred

| Family | Genuinely new playable delivery |
|---|---|
| Monk | Tiger Stance and Wolf Stance, L1; horizontal Step/Trip and persistent bleed integration |
| Arms | Raging Thrower and Extravagant Parry, L1; Strong Arm explicitly L2 |
| Focus/font | Initiate Warden, Harming Hands and Hymn of Healing, L1; Gravity Weapon and Hymn of Healing spells |

This is eight new feats across seven classes, seven at L1, plus two spells. No new items or credit for existing-name configurations. Accepted catalog now 125 setups/102 creatures; staged 24/12 remain staged. Save version 18. Preserve accepted W2/W3/W4 and all earlier representatives and finite alternatives.

Deferred: Dragon Stance, Acute Vision, prior Dangerous Sorcery and unselected printed options. Boundaries: combat-only Ranger, horizontal-only Monk, finite menus, labeled above-level equipment and existing GM conventions. Vertical terrain/High Jump and positive damage to stable-unconscious-at-zero are unsupported. Paired mixed-resistance allocation and pre-first-turn Surprise Attack remain pending. No universal poison/minion/rules framework.

## Accepted helper and test pointers

Owner/reviewer-reported contracts below are the compact startup map. Future planners verify current signatures, source rules and actual fixtures before extending them; the coordinator has not inspected implementation.

- B shared `src/pf2e/strike_hooks.py`: `final_check_outcome` for Parry, `committed_first_weapon_attempt` for Gravity, `post_mitigation_damaging_critical` for Tiger. B owns semantic integration of these call sites. `ranged_profiles.py` and `w5_arms_content.py` cover admitted Arms profiles; `w5_arms_persistence.py` and `w5_arms_terminal.py` connect saves/menus. Analogues: `tests/test_w5_arms_content.py`, `test_w5_arms_independent_review.py`.
- A `src/pf2e/monk_stances.py`, `persistent_effects.py`, `w5_stance_content.py`, `w5_stance_persistence.py`, `w5_stance_terminal.py`. Tiger: agile/finesse/nonlethal d8 slashing, post-mitigation damaging critical adds 1d4 bleed; 10-foot Step requires Speed ≥ 20 and actual horizontal legality. Wolf: d8 piercing, backstabber uses off-guard but Trip requires actual flanking. Both retain ordinary fists; Crane exclusivity is not universal. Incomparable bleed retains a saved finite GM choice and the one-minute convention. Analogues: `tests/test_w5_monk_stances.py`, `test_w5_monk_independent_review.py`.
- C `src/pf2e/bard_compositions.py`, `focus_buffs.py`, `w5_focus_content.py`, `w5_focus_persistence.py`, `w5_focus_terminal.py`; typed-status/composition/sustain hooks reuse existing runtime. Gravity consumes the first weapon attempt per round, including misses/precast attempts; no recast reset or unarmed application. Hymn fast healing occurs at recipient start before dying, not immediately on cast; temporary HP is separate, with sustained duration/one-composition constraints. Harming Hands uses the admitted harmful-font Nethys Warpriest grants and living-target Harm path. Analogue: `tests/test_w5_focus_content.py`; detailed independent C evidence remains with the archived task/ref in acceptance evidence.

Last accepted assembled public probe: `tests/test_w5_assembled_independent_review.py`, independent reviewer commit `4b4fdc67146118219fcb30b1cdb2a461383824df`, integrated unchanged. It covers continuous A/B/C play to saved victory, Tiger/Parry, Tiger/Hymn, Gravity/Anthem, saved validity, numbered terminal choices and bounded mixed-effect option generation. The source-linked [adopted planning note](../work-log/w5-planning.md) is design input; final accepted tests/repairs take precedence over pre-repair wording.

## Environment and evidence

Team environment: Python 3.11.1 at `/Library/Frameworks/Python.framework/Versions/3.11/bin/python3`, pytest 8.4.2, `PYTHONPATH=src`, `/opt/homebrew/bin/timeout`. Verify once in a future assigned cwd. Bounded focus: `PYTHONPATH=src /opt/homebrew/bin/timeout 30s /Library/Frameworks/Python.framework/Versions/3.11/bin/python3 -m pytest -q <selection>`. Canonical: `PYTHONPATH=src /Library/Frameworks/Python.framework/Versions/3.11/bin/python3 tools/integration_checkpoint.py`.

Final canonical 1,533 passed/7.96s, checkpoint 8.370s, child RSS 90,275,840 bytes, compile/test/diff 0. Integration and final reviewer reported task-owned commands exited. Fresh tasks have no public probe until one runs. One synchronous pytest/task, no watch/xdist/background tests; integration lead owns final broad assembled validation.

The [task-creation RCA](../work-log/w5-task-creation-rca.md) documents a deleted-worktree model-catalog dependency. The durable saved-project catalog path is repaired, byte-identical and verified; automatic worktree cleanup remains disabled to preserve retained checkouts. Do not replace models or point shared catalogs into disposable worktrees. Cost monitoring remains in the existing audit task only.
