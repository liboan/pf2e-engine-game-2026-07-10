# W4 offensive class-feat lane

Selected roster, checked 2026-09-20 against the current Archives of Nethys
feat entries:

- Fighter: Exacting Strike, Double Slice.
- Ranger: Twin Takedown.
- Rogue: Twin Feint.

Source packet: [Exacting Strike](https://2e.aonprd.com/Feats.aspx?ID=357),
[Double Slice](https://2e.aonprd.com/Feats.aspx?ID=356),
[Twin Takedown](https://2e.aonprd.com/Feats.aspx?ID=494), and
[Twin Feint](https://2e.aonprd.com/Feats.aspx?ID=552).

All four are genuinely new level-1 playable names in this checkout; W3
Snagging Strike, Combat Grab, Brutish Shove and the existing Vicious Swing are
not counted. The finite fixtures use held longsword/shortsword, shortsword/
dagger, or the corresponding ranger pair. No new weapon, poison, minion,
terrain, or universal rules framework is introduced.

Implementation contracts:

- `src/pf2e/w4_offensive.py` owns typed commands and paired-family routing.
- `src/pf2e/paired_strikes.py` owns the ordered continuation and refreshed
  second-Strike menu. Double Slice is a two-action same-target pair, resets the
  second Strike to the current MAP, applies its non-agile second-Strike penalty,
  and records two attacks after completion. Twin Feint is a two-action
  same-target pair and snapshots the target off-guard for its second Strike.
- `Encounter._start_w4_exacting_strike` reuses the ordinary Strike pipeline;
  an ordinary failure removes only that Strike's MAP increment, while a
  critical failure still counts.
- `src/pf2e/w4_offensive_content.py` owns four level-1 sheets and public
  guard-dog fixtures; `content.py` is the single admission point.

Deferred: critical-specialization riders, broader two-weapon equipment
selection, shared mixed-resistance/weakness allocation across paired damage,
and non-horizontal movement. The paired actions preserve ordinary reactions,
Hero choices, damage, save/load, and terminal action projection through
existing contracts.

Focused check: `PYTHONPATH=src /opt/homebrew/bin/timeout 30s
/Library/Frameworks/Python.framework/Versions/3.11/bin/python3 -m pytest -q
tests/test_w4_offensive_content.py`.
