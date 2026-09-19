# Investigator: leads, Clue In and free Devise

## Active bounded outcome

Shared Knowledge and actual Forensic examination are accepted. The next slice uses small authored case records to support Pursue a Lead, investigation bonuses, Clue In and paid/free Devise. It does not build a general mystery system. Skill Stratagem, Streetwise, level2 and full class admission remain later.

Owner Luna/xhigh `/root/investigator_knowledge`, session `01a0aae3-7435-7923-bfdb-a7923293cd5a`, run `investigator-leads-clue-in-2026-09-16`. The [Astra contract](investigator-remaining-grants-work.md) and existing knowledge/examination APIs are the handoff. Relevant existing primitives include saved `FamilyProcedureContext` checks, world time, `next_encounter` and actual `daily_prepare`. Accepted799-test public evidence includes saved examinations and knowledge history across scenes. No Lead executable result is claimed yet.

## Required behavior

Author literal case IDs/questions, clues, larger-mystery facts, relevant check bindings and creatures known to help. Persist two active cases, abandoned cases and separate Lead/Clue In deadlines. Pursue takes60seconds. A confirmed mystery starts the ten-minute restriction even if opening it is declined; an inconsequential clue does not. Third-case entry needs explicit replacement. Abandoned cases reopen only after that actor's actual daily preparation; solved cases retain benefits until closed. Appropriate authored Perception/skill checks receive the source's+1 circumstance bonus with normal stacking.

Clue In pauses before another creature's relevant check. That creature is the recipient; the Investigator chooses use/decline. Preserve reaction expenditure, ten-minute cooldown, communication/traits, the underlying check and every saved decision. Free Devise requires an active case and authored awareness, retains once-per-round frequency, and preserves paid/free intent through embedded Known Weaknesses and saves. Sources: [Investigator](https://2e.aonprd.com/Classes.aspx?ID=59), [Devise](https://2e.aonprd.com/Actions.aspx?ID=2813).

First checkpoint: public authored Pursue advances60seconds once and yields an applicable bonus after save/load. Follow with free Devise and a real ally Clue In check. Verify cooldowns, decline/replacement, atomic invalid requests, genuine declared rest/preparation reopening, saved nested choices, healthy encounters/scene carry and bounded terminal. Report any mandatory coupling that would exceed this slice rather than quietly adding later features.

Coordinate narrow shared-file edits with Tumble Through. Use the verified project-root `.venv/bin/python` pytest environment, explicit30-second wall bound, finite checked-in input/capture and reconciled process exits. Focused checks remain available on stable paths; one broad integration follows coherent changes. Root coordinates and writes documentation only.

## Current evidence

Accepted after retained-owner repair, independent source-checked continuous play and the 826-test canonical integration checkpoint. Public commands `PursueLead` and `InvestigationCheck`; authored `INVESTIGATOR_CLUE_ROOM`; methods `Encounter.pursue_lead`, `close_investigation`, `mark_investigation_solved`. Runtime/content pointers are `src/pf2e/investigator.py` and `src/pf2e/investigator_content.py`, with encounter/persistence integration. Save version remains 17.

[Owner evidence](../../tests/test_investigator_leads.py): 11 passing cases; coherent focused owner/review group 94 passed in 0.43s, compile/diff clean. Owner reports case lifecycle, authored bonuses, Clue In use/decline, paid/free Devise, cooldowns, daily preparation, saved choices/scene carry and bounded postcombat terminal Pursue. Independent review now proves the original continuous-play and choice examples; no complete-class acceptance is claimed. Shared Tumble menu compatibility was repaired by its retained owner while preserving the Investigator terminal test's intended actions.

Owner reports every command ended synchronously and no retained process/session. Independent process audit at 13:05:43 PDT found no task-owned jobs; subsequent tests/integration exited synchronously, with local process enumeration denied. Accounting is closed.

[Independent review](../../tests/test_investigator_leads_play_review.py) found Clue In wrongly required the recipient to be in free Devise awareness; the owner repaired `_find_investigation_owner` and added an explicit no-awareness assertion. Final healthy sequence: actual injury and Battle Medicine, victory, Pursue (+60 seconds), save/load, scene carry, saved free Known Weaknesses/Devise, fixed Intelligence Strike (+8 attack including Known Weaknesses, 2 damage without Intelligence), saved allied Clue In with communication/reaction/bonus/cooldown, then a second victory. A separate real multi-day rest/preparation path reopens an abandoned case and rejects early attempts atomically. Reviewer errors in the attack expectation and occupied-square movement were corrected separately.

Grouped review: 27 passed in 0.19s; Lead plus prior paid Devise/Knowledge review: 23 passed in 0.21s. First canonical integration exposed four Tumble menu scripts; retained Tumble owner repaired them. Justified final rerun: 826 passed, measured 4.344 seconds, 72,925,184-byte peak, compile/diff clean, 51/36 admitted and 11/4 staged, save 17.

Run usage: 34,535,923 input / 33,719,040 cached input / 109,204 output; 233 requests, 2 compactions. Original owner retained. Shared Sol review: 12,701,653 input / 12,481,152 cached / 28,094 output, 84 requests, no compactions; record this shared cost only once. Audit: 510,331 input / 354,560 cached / 1,256 output, 3 requests. Full group totals and timing limits are in ACTIVE.
