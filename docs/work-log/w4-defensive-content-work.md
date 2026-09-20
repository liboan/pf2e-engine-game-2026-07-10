# W4 lane 2 — defensive, mobility, and skill-linked level-1 feats

## Delivery

Implemented four distinct W4 level-1 class-feat variants and their playable
fixtures:

- Reactive Shield: saved pre-roll melee reaction, raises the held shield for
  the triggering attack, consumes the shared reaction, and round-trips through
  persistence.
- Point Blank Stance: one-action ranged stance with one-stance-per-round
  enforcement and +2 circumstance damage within the first range increment,
  excluding volley attacks.
- Overextending Feint: opt-in Feint replacement for the Rogue, with a typed
  -2 penalty against the Rogue's next/all attacks according to degree and
  source-relative expiry.
- You're Next: post-defeat reaction with a bounded 60-foot target menu and a
  no-action Demoralize carrying a +2 circumstance modifier.

Source checks (2026-09-20):

- https://2e.aonprd.com/Feats.aspx?ID=4772
- https://2e.aonprd.com/Feats.aspx?ID=4771
- https://2e.aonprd.com/Feats.aspx?ID=4917
- https://2e.aonprd.com/Feats.aspx?ID=4922

## Integration surface

- `src/pf2e/w4_defensive_content.py`: definitions and public setups.
- `src/pf2e/martial_defense.py`: Point Blank command and damage projection.
- `src/pf2e/skill_actions.py`: Overextending Feint and reaction Demoralize.
- `src/pf2e/encounter.py`: reaction pending choices, damage/stance/action
  integration, and public action menu.
- `src/pf2e/model.py`, `src/pf2e/persistence.py`: typed state and backward-
  compatible save/load fields.
- `src/pf2e/terminal.py`: Point Blank and Overextending Feint controls.
- `tests/test_w4_defensive_content.py`, `tests/test_interaction_catalog.py`.

## Verification

Environment: `/Library/Frameworks/Python.framework/Versions/3.11/bin/python3`,
`PYTHONPATH=src`, cwd is the W4 worktree. The broad synchronous check passed:

`/opt/homebrew/bin/timeout 300 /Library/Frameworks/Python.framework/Versions/3.11/bin/python3 -m pytest -q`

Result: **1460 passed in 8.55s**. No task-owned background processes remain.
