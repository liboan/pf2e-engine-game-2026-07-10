# Investigator: remaining selected level-1 grants

## Design outcome and next delivery

Astra reviewed the existing source packet and delivered APIs. No new P0/P1 decision is needed. The next bounded outcome is **body examination → saved immediate follow-up → carry the clue into the next encounter**. Lead/Clue In/free Devise, Skill Stratagem and the selected Streetwise grant follow as separate coherent outcomes. These are required by the current fixed build; no whole Investigator admission is implied by this plan.

This is a source/API contract, not runtime evidence. Knowledge is accepted with the765-test integration and a subsequent4-case independent review. Examination implementation is now assigned to retained Knowledge owner Luna/xhigh `/root/investigator_knowledge`, session `01a0aae3-7435-7923-bfdb-a7923293cd5a`, new run `investigator-forensic-examination-2026-09-16`. Owner located the first integration gap: Choose rejects finished encounters and persistence rejects their pending choices. It is adding only the typed examination stages to those gates; no blanket permission for finished-combat actions. Its first executable checkpoint is pending; Lead/Clue In, Skill Stratagem and Streetwise are not part of this assignment.

## Body examination

Author a body/subject key, accessible-body fact, Medicine question/DC, ordinary duration, result information and permitted follow-up knowledge records. Use an outside-combat public method with transactional state/dice. Ordinary examination takes at least ten minutes; Forensic Acumen halves the authored duration, minimum five minutes. Advance `world_time_seconds` exactly once through `_advance_elapsed_time`; do not call `record_rested`, which grants unrelated rest eligibility.

Resolve an actual Medicine Recall Knowledge check. Finalized success/critical success offers an immediate optional relevant check with+2 circumstance and the permitted cause-of-injury/creature-type alternatives. Save the Hero decisions and follow-up choice. Declining ends the opportunity. Preserve shared subject-keyed attempt limits, including when the examination and follow-up use the same subject.

Current prerequisite: `_knowledge_target` requires a living nonself creature and result formatting dereferences it. Extend authored knowledge to a labeled subject with an optional actor reference. Do not invent a fake living creature for a body or clue. Sources: [Medicine](https://2e.aonprd.com/Skills.aspx?ID=42), [Forensic Acumen](https://2e.aonprd.com/Feats.aspx?ID=6483).

## Lead, Clue In and free Devise

Use literal authored case IDs/questions, clues, a larger-mystery fact, relevant check bindings and creatures known to help. Persist two active cases, abandoned cases and separate Lead/Clue In deadlines. Pursue spends60 seconds. A confirmed mystery starts the ten-minute restriction even if opening it is declined; inconsequential clues do not. Third-case entry requires explicit replacement. Abandoned cases reopen only after that actor's actual daily preparation. Solved cases retain benefits until closed. Applicable authored checks receive+1 circumstance, including approved nonmental checks.

Clue In pauses before another creature's relevant check, offering the Investigator use/decline. The recipient is that triggering creature. Persist reaction expenditure, ten-minute cooldown, communication eligibility/traits and the suspended check; retain typed stacking. Free Devise requires authored awareness and an active case; once-per-round frequency remains. Preserve paid/free intent through embedded Knowledge and saves. Sources: [Investigator](https://2e.aonprd.com/Classes.aspx?ID=59), [Devise](https://2e.aonprd.com/Actions.aspx?ID=2813).

## Skill Stratagem and Streetwise

After showing the stored die, offer attack/skill. Skill mode blocks all Strikes against that target until next turn, even after its bonus is consumed. The next qualifying target-related mental skill/Perception check receives+1 circumstance, or increases an applicable investigation bonus to+2. Consume once, preserve wrong-target checks, and never benefit the preceding embedded Knowledge check.

Streetwise requires Society-based Gather Information and settlement-familiarity-gated Society Recall Knowledge. Author familiarity, question, separate DCs, duration and results. Failed recall still permits gathering; gathering typically takes two hours and uses separate attempt handling. Optional bribe modeling is excluded. Sources: [Streetwise](https://2e.aonprd.com/Feats.aspx?ID=5218), [Gather Information](https://2e.aonprd.com/Actions.aspx?ID=2391).

## Compact execution handoff

Relevant files: investigator.py, investigator_content.py, model.py, encounter.py, persistence.py and terminal.py. Symbols: `RecallKnowledgeContent`, `_resolve_recall_knowledge`, `_finalize_knowledge`, `_handle_devise`, `_draw_devise_after_knowledge`, `handle_choice`, `validate_pending`, `FamilyProcedureContext.prepare_skill_check`, `Encounter.next_encounter`. Shared Knowledge review repairs must settle before dependent edits.

Analogous tests: `test_public_recall_knowledge_hero_choice_save_load_answer_and_history`, `test_finished_fight_refocus_save_load_next_encounter_and_finish`. Exact environment is the project root and `.venv/bin/python -m pytest -q ...`, with pytest supplying `src`; use explicit timeout and existing bounded helpers. Each slice needs focused atomicity/rule checks, saved pending choices, bounded terminal and continuous scene carry. Avoid a mystery framework or level-2 breadth.

## Research accounting

Closed `investigator-remaining-grants-contract-2026-09-16`: Astra/high,8requests,0compactions, **466,461 input (366,080 cached),2,499 output**. No edits, tests, probes or background processes. Root summarizes worker sources and API findings; it did not inspect them directly. Dollar cost unavailable.

## Examination owner delivery: independent review ready

Public `Encounter.forensic_examine` (aliases `examine`/`examine_body`) handles authored accessible bodies, actual Medicine checks, half duration/minimum5minutes, exactly one elapsed-time charge, saved Hero choices, immediate optional+2 relevant Knowledge, shared history/exhaustion and atomic invalid/live-body rejection. `ForensicExaminationContent`, setup packets, pending/completion state and terminal action provide content/save/interface support.

First public test `tests/test_investigator_examination.py::test_public_body_examination_saves_hero_decision_and_charges_time_once` passes in0.08s: d20=11 produces Medicine15vsDC15; saved Hero keep yields exactly+300seconds, body history/completion and a saved follow-up offer. Owned/regression86passed in0.31s, including Knowledge, healing, existing play/recovery/terminal checks. A transient finished-choice gate failure on ordinary initiative's `procedure_id=None` was corrected with the narrow fallback, then its38-test selection passed.

`test_healthy_fight_then_examination_and_saved_next_scene_have_legitimate_results` passes in0.10s: genuine healthy fight/victory→saved examination/follow-up→saved next encounter→DC18carried history and critical Knowledge. Compile/diff pass. No yielded/background sessions reported. This authorizes Sol's independent examination phase; it is still not a whole-class admission or a broad integration rerun.

## Examination accepted; leads now active

Independent examination2cases pass; group7cases/40withdirectownerchecks pass in0.26s. It verifies actual healthy injury/Battle Medicine/victory, saved examination/time300seconds once, saved immediate+2 Knowledge, cross-scene history/DCs, nonactor bodies, decline and atomic forged/repeated choices. The reviewer corrected its own Nature fixture expectation; no new examination runtime defect was found. Full799tests pass, measured3.818s/71,122,944bytes, compile/diff0; final10:22:43PDT audit clear.

Closed examination delivery: **28,226,293 input (27,697,920 cached),96,773 output**,189requests,2compactions, Luna/xhigh. Same owner throughout. Group review/audit are shared and recorded in the finisher packet and ledger, not duplicated as separate costs. The next [Lead/Clue In outcome](investigator-leads-work.md) is a new registered assignment. Skill Stratagem and Streetwise remain later.
