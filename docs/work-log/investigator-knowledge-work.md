# Investigator knowledge: bounded implementation contract

## What this adds

An authored encounter supplies the question, facts and difficulty. The engine rolls the relevant skill, returns the permitted information and remembers whether another attempt is allowed. The same procedure serves ordinary Recall Knowledge, Known Weaknesses during Devise, and the selected forensic examination. This avoids building a general mystery or automatic GM.

**Status: accepted as a bounded capability; full Investigator remains staged.** Luna/xhigh `/root/investigator_knowledge`, session `01a0aae3-7435-7923-bfdb-a7923293cd5a`, completed run `investigator-knowledge-delivery-2026-09-16` without a change of owner. The full Investigator remains staged. Forensic examination, Lead/Clue In and Skill Stratagem remain subsequent outcomes.

### Executed delivery evidence

- Public `RecallKnowledge(subject_key, question, skill, target_id)` consumes authored `EncounterSetup.knowledge` records. Normal supported non-Investigator actors can use it.
- Pending Hero choices round-trip through JSON; the finalized outcome controls subject-keyed history, increasing DCs and exhaustion. Embedded Known Weaknesses completes its check and benefits before drawing one Devise die.
- Own and communicated ally bonuses are target-specific; miss consumption, wrong-target preservation and expiry have focused checks. The generic saved-check fortune guard preserves Sure Strike/Devise behavior.
- A healthy-start continuous fight saves the pending knowledge Hero choice, reloads, applies an ally bonus and reaches blue victory. A cross-scene test preserves `{"guard_dog": 1}` history. Bounded terminal checks finish under40 input calls and show the authored answer and Devise die.
- Owner focused selection: **70 passed in0.27s**; carry/Sure Strike regressions: **13 passed in0.17s**. Compile/diff checks exit0.
- Coordinated checkpoint: **765 passed in3.66s**, measured pytest4.084s, peak70,270,976bytes, compile/diff0, synchronous exit0. Catalog51/36 admitted,10/3 staged, save17. This includes Swash and the independent Swash/Medicine cases; Knowledge review is still required.

The first executable result was observed by compact status at15:58:56UTC September16: `Encounter.start(... rolls=(20,1,2,14))`, then normal Recall Knowledge pauses for Hero; keep produces21vsDC16, an authored answer, one action spent and one recorded attempt. Save evidence came later and is not retroactively attributed to this first probe. The Society/DC16 guard-dog question is an explicit GM-authored question, **not** default Nature-based creature identification. Actual first-execution time was not separately supplied.

All owner commands reportedly exited synchronously; a separate process audit is in progress. Root summarizes worker evidence and does not read implementation or sources. Sol review `investigator-knowledge-play-review-2026-09-16` is complete with no P0/P1 defects. Its initial3 fixture expectations were corrected without production changes. Final evidence is below.

## Player-facing flow

In the terminal, choose Recall Knowledge, an available subject/question, and an eligible skill. The authored encounter supplies a short menu of meaningful questions; players do not need to enter difficulty values or construct internal records. The engine reports the permitted answer and any resulting bonus. During Devise, choose whether to use Known Weaknesses, resolve that knowledge check and any Hero decision, then see the stratagem die. Save/load must preserve whichever choice is pending.

The owner exercised these menus with bounded input. Independent review and full class admission remain separate gates.

## Shared procedure and authored context

Support normal one-action Recall Knowledge and embedded invocations without an additional action cost. Use an actual skill check with applicable conditions and typed modifiers. Success returns the authored truthful answer; critical success adds authored context; failure returns nothing. Default critical failure to the expressly permitted no-information result; an authored false answer may be supplied.

Keep the authored record small:

- Subject key and optional corresponding creature ID; question and allowed skill/DC pairs.
- Successive-attempt DCs and the terminal “incredibly hard” stage.
- Truthful answer, additional context and optional false answer.
- Investigation relevance and communication recipients.

The author determines whether a subject is a general category or an individual. Reject missing context before paying costs. Do not infer an ontology of creature facts. Forensic examination duration remains authored as the existing packet requires.

Persist attempts by investigator and subject, not by question or skill. Finalized success advances the authored difficulty. Finalized failure/critical failure or completing the terminal attempt exhausts the subject. A Hero reroll replaces the pending result before history changes. Critical-success follow-up information belongs to that one result. Exhausted knowledge cannot produce repeated critical-success bonuses; Devise without optional knowledge remains available.

## Devise integration and bonuses

Prevalidate both operations, commit Devise once, resolve optional knowledge and its Hero decision, finalize information/history/benefits, then draw Devise's d20. When Skill Stratagem is admitted, choose attack/skill after seeing that die; skill mode cannot improve the preceding knowledge check. Every saved pause resumes without another payment, attempt or die draw.

Known Weaknesses critical success grants each actually informed ally a target-specific +1 circumstance bonus to its next attack roll against the subject, consumed even on a miss. The grant expires at the Investigator's next turn start. The Investigator's own bonus applies only to the chosen attack stratagem. Apply ordinary circumstance stacking. A printed numerical damage weakness is not required.

Preserve the secret trait with the explicit open-roll presentation convention. The knowledge check may use Hero Points and does not inherit the later Strike's fortune. Persist reroll/fortune flags and prevent an additional fortune effect.

## Execution handoff

- `src/pf2e/investigator.py`: `DeviseStratagem`, `InvestigatorStratagemState`, `_handle_devise`, `handle_choice`, `validate_pending`.
- `src/pf2e/model.py`: `FamilyProcedureContext.prepare_skill_check`, `resolve_saved_check`, `reroll_saved_check`, `present_choice`; `SavedCheckContext`, `PendingChoice`, `ActionContinuation`.
- Analogue: `tests/test_skill_actions.py::test_public_trip_saved_hero_choice_round_trips_then_applies_damage_and_prone`.
- Metadata analogue: `skill_content.SkillActionContent`.
- Astra flags that `_reroll_saved_check` checks Sure Strike/reroll state but not the generic `fortune_used` flag; enforce the appropriate guard for the new procedure.

Verified invocation remains project-root `.venv/bin/python -m pytest -q <focused files>`; pytest supplies `src`. The latest accepted public prerequisite is staged Devise → save/load → Strike, with the independent first-sequence encounter. The original Astra design task ran no engine probe; the owner evidence above supersedes that prerequisite-only checkpoint.

## Sources and accounting

Astra checked [Recall Knowledge](https://2e.aonprd.com/Actions.aspx?ID=2367), [GM Core additional knowledge](https://2e.aonprd.com/Rules.aspx?ID=2638), [Known Weaknesses](https://2e.aonprd.com/Feats.aspx?ID=5936), [Devise](https://2e.aonprd.com/Actions.aspx?ID=2813), and [secret checks and fortune](https://2e.aonprd.com/Rules.aspx?ID=2263). The supervisor summarizes that report without inspecting sources or implementation.

Closed run `investigator-knowledge-contract-2026-09-16`: Astra/high, 8 requests, no compactions; **787,612 input (738,432 cached), 3,088 output**. No code/doc edits or test/probe processes were launched by the worker. Dollar cost unavailable.

## Independent review accepted

`tests/test_investigator_knowledge_play_review.py` adds four source-checked public cases:

1. A healthy fight saves/loads the pending embedded knowledge check; verifies Knowledge→Known Weaknesses→Devise ordering, one action, preserved fixed die and own/informed-ally bonuses; suffers actual enemy injury and wins. The next encounter carries subject history despite a changed question/skill and uses the increased DC after another save.
2. Trip and wrong-target Strikes preserve the bonus; a correct-target miss consumes it; the Investigator's next turn expires remaining grants.
3. A frightened ordinary Fighter receives the status penalty, uses a Hero Point on the explicitly open secret check, spends the point and becomes exhausted after finalized critical failure.
4. Rage rejects the Concentrate action without state or dice changes.

Owned4passed in0.19s; with owner/prior Investigator review24passed in0.23s; compile/diff0. All synchronous processes reportedly exited. Reviewer checked the sources above and found no production defect. This test-only addition follows the765-test integration; the next coherent broad checkpoint will include these four new cases. Full Investigator admission still waits for its remaining selected grants.

## Closed delivery, review and process accounting

The independent09:35:51PDT inventory found no completed Knowledge/Sol Python, pytest or temporary probes. Shared app/browser services were preserved; zero kills. The test-only4-case review follows the765-test full integration and joins the next coherent broad checkpoint.

- Delivery `investigator-knowledge-delivery-2026-09-16`: **35,278,459 input (34,594,048 cached),104,287 output**,235requests,2compactions; Luna/xhigh.
- Review `investigator-knowledge-play-review-2026-09-16`: **4,070,107 input (3,951,104 cached),21,354 output**,34requests,1compaction; Sol/high.
- Audit `knowledge-review-completion-process-audit-2026-09-16`: **349,646 input (334,336 cached),1,295 output**,2requests,0compactions; Luna/xhigh.

No owner change or production review repair was needed; the reviewer corrected three fixture expectations. Exact delivery elapsed time, first-execution timestamp and explicit wait durations were not separately provided. First executable observation remains15:58:56UTC above. Dollar cost unavailable. The owner is now registered separately for Forensic examination; do not recompute this closed assignment from its reused-session totals.
